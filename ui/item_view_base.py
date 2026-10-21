"""
The pages for equipment and magic items are the same page with different columns, so they share one
implementation: :class:`ItemViewBase` (the browse page, with filtering, add / edit / delete and the
right-click "add to character") and :class:`ItemDetailBase` (the detail pane's property chips and
description).

A subclass names its manager, panels and editor, adds the widgets that are its own to the filter bar,
and says what its extra filters are. See ``ui/equipment_view.py`` and ``ui/magic_item_view.py``.
"""

from typing import List, Optional

import customtkinter as ctk
from tkinter import messagebox

from typography import ui_font
from equipment import parse_cost_to_copper
from settings import get_settings_manager
from theme import get_theme_manager
from ui.text_import_flow import announce_added, import_from_pasted_text
from ui.bulk_actions import BulkActionsMixin
from ui.collection_page import CollectionPageMixin
from ui.label_text import LabeledLabel
from ui.filter_widgets import SourceFilterMode, TagFilterDialog, TagFilterMode
from ui.tooltip import HoverTooltip


class ItemDetailBase(ctk.CTkFrame):
    """The detail pane. Subclasses build their widgets in ``_create_widgets`` (which must create
    ``properties_frame``, ``_properties_chip_area``, ``desc_frame``, ``source_label`` ...) and lay a
    shown item out in ``show_item``."""

    def __init__(self, parent):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._current_item = None
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)

    def _create_widgets(self):
        raise NotImplementedError

    # ---- the pieces both panels build (a subclass calls them in its own order)

    def _add_scroll_and_name(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)

        self.name_label = ctk.CTkLabel(
            self.scroll_frame, text="Select an item",
            font=ui_font("title", bold=True), wraplength=400
        )
        self.name_label.pack(anchor="w", pady=(0, 5))

    def _add_stats_label(self):
        self.stats_label = LabeledLabel(
            self.scroll_frame, text="",
            font=ui_font("body", 13),
            text_color=self.theme.get_text_secondary(),
            anchor="w", justify="left"
        )

    def _add_source_label(self):
        self.source_label = LabeledLabel(
            self.scroll_frame, text="",
            font=ui_font("small"),
            text_color=self.theme.get_text_secondary()
        )

    def _add_tags_label(self):
        self.tags_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ui_font("body"),
            text_color=self.theme.get_current_color('accent_primary'),
            wraplength=400, justify="left"
        )

    def _add_properties_and_description(self):
        # Named properties: each keyword renders as a chip; hovering it shows
        # the property's description in a tooltip.
        self.properties_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._properties_header = ctk.CTkLabel(
            self.properties_frame, text="Properties",
            font=ui_font("body", bold=True),
            text_color=self.theme.get_text_secondary(), anchor="w",
        )
        self._properties_header.pack(anchor="w", pady=(0, 4))
        self._properties_chip_area = ctk.CTkFrame(self.properties_frame, fg_color="transparent")
        self._properties_chip_area.pack(fill="x", anchor="w")
        self._property_tooltips = []

        self.desc_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._desc_widgets = []

    def _update_colors(self):
        raise NotImplementedError

    def _on_theme_changed(self):
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._update_colors()

    def _clear_description(self):
        for widget in self._desc_widgets:
            widget.destroy()
        self._desc_widgets = []

    def _render_properties(self, properties):
        """Lay out property keywords as hover-for-description chips."""
        for widget in self._properties_chip_area.winfo_children():
            widget.destroy()
        self._property_tooltips = []

        clean = [p for p in (properties or []) if p.get("name")]
        if not clean:
            self.properties_frame.pack_forget()
            return

        theme = self.theme
        row = ctk.CTkFrame(self._properties_chip_area, fg_color="transparent")
        row.pack(fill="x", anchor="w")
        used = 0
        for prop in clean:
            def _make_chip(parent):
                c = ctk.CTkLabel(
                    parent, text=prop["name"], font=ui_font("body"),
                    fg_color=theme.get_current_color('bg_secondary'),
                    text_color=theme.get_current_color('text_primary'),
                    corner_radius=10, padx=10, pady=3,
                )
                c.pack(side="left", padx=(0, 5), pady=2)
                c.update_idletasks()
                return c

            chip = _make_chip(row)
            width = chip.winfo_reqwidth() + 5
            if used and used + width > 380:
                chip.destroy()
                row = ctk.CTkFrame(self._properties_chip_area, fg_color="transparent")
                row.pack(fill="x", anchor="w")
                chip = _make_chip(row)
                used = width
            else:
                used += width

            desc = prop.get("description") or "(no description)"
            self._property_tooltips.append(HoverTooltip(chip, desc))

        self.properties_frame.pack(fill="x", anchor="w", pady=(0, 10))

    def _render_description(self, text: str):
        from ui.rich_text_utils import render_description_blocks

        self._clear_description()
        if not text:
            self.desc_frame.pack_forget()
            return

        self.desc_frame.pack(fill="x", anchor="w", pady=(10, 0))
        self._desc_widgets.extend(render_description_blocks(self.desc_frame, text, self.theme))

    def _show_source_footer(self, item):
        """Source is shown last, as a footer under everything else."""
        if item.source:
            source_text = f"Source: {item.source}"
            if not item.is_official:
                source_text += " (Unofficial)"
            self.source_label.configure(text=source_text)
            self.source_label.pack(anchor="w", pady=(14, 0))


class ItemViewBase(BulkActionsMixin, CollectionPageMixin, ctk.CTkFrame):
    """A searchable, filterable list of items with a detail pane."""

    MANAGER_ATTR = "item_manager"
    BULK_ACTIONS = ("add", "tags", "source")
    BULK_NOUN, BULK_PLURAL = "item", "items"

    # Subclass configuration -------------------------------------------------
    MANAGER_GETTER = None            # callable returning the manager
    LIST_PANEL = None                # VirtualListPanel subclass
    DETAIL_PANEL = None              # ItemDetailBase subclass
    EDITOR_DIALOG = None             # the editor dialog class
    ADD_TITLE = "Add Item"
    EDIT_TITLE = "Edit Item"
    STUDIO_KIND = ""                 # the Homebrew Studio's name for this collection
    MATERIAL_NOUN = "crafting"       # "Select Crafting Materials", "No crafting materials found ..."
    PLURAL = "items"

    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))

        self.item_manager = self.MANAGER_GETTER()
        self.settings_manager = get_settings_manager()
        self.character_manager = character_manager
        self.on_back = on_back
        self._all_items: List = []
        self._context_item = None
        self._filter_debounce_id: Optional[str] = None
        self._filter_debounce_delay = 150

        # Source, tag, and material filter state
        self._selected_sources: List[str] = []
        self._source_filter_mode: SourceFilterMode = SourceFilterMode.INCLUDE
        self._selected_tags: List[str] = []
        self._tag_filter_mode: TagFilterMode = TagFilterMode.HAS_ALL
        self._selected_materials: List[str] = []
        self._material_filter_mode: TagFilterMode = TagFilterMode.HAS_ALL

        self._create_widgets()
        self._setup_bulk_actions()
        self._create_context_menu()
        self._load_items()
        self.theme.add_listener(self._on_theme_changed)

    # ---- hooks -----------------------------------------------------------------

    def _item_materials(self, item) -> List[str]:
        """The crafting / enchanting materials of an item (what the materials filter looks at)."""
        raise NotImplementedError

    def _all_materials(self) -> List[str]:
        raise NotImplementedError

    def _add_to_sheet(self, sheet, item):
        """Put ``item`` in the right inventory list of a character sheet."""
        raise NotImplementedError

    def _extra_filter(self):
        """A predicate ``item -> bool`` for this page's own filters, or None."""
        return None

    def _clear_extra_filters(self):
        pass

    def _load_extra_options(self):
        pass

    def _text_import(self):
        """``(source_dialog_cls, import_dialog_cls, to_draft)`` for "add from pasted text"."""
        raise NotImplementedError

    # ---- layout -----------------------------------------------------------------

    def _create_panes(self):
        self.list_panel = self.LIST_PANEL(
            self.paned, on_select=self._on_item_selected, on_right_click=self._on_item_right_click
        )
        self.detail_panel = self.DETAIL_PANEL(self.paned)

        self.paned.add(self.list_panel, minsize=280, stretch="always")
        self.paned.add(self.detail_panel, minsize=400, stretch="always")

    def _add_search_and_type(self, bar, placeholder: str, search_width: int, search_padx,
                             type_width: int, type_padx):
        self._add_search_entry(bar, placeholder, search_width, search_padx)
        self._add_filter_combo(bar, "type", "Type:", "All Types", ["All Types"], type_width, type_padx)

    def _add_tags_filter(self, bar, end_padx):
        ctk.CTkLabel(bar, text="Tags:").pack(side="left", padx=(0, 5))
        self.tags_btn = ctk.CTkButton(
            bar, text="Select Tags...", width=120, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._open_tag_filter
        )
        self.tags_btn.pack(side="left", padx=(0, 8))
        self.tags_label = ctk.CTkLabel(
            bar, text="None selected",
            font=ui_font("small"), text_color=self.theme.get_text_secondary()
        )
        self.tags_label.pack(side="left", padx=end_padx)

    def _add_price_filter(self, bar):
        """Materials filter, price range and the clear button (the page's last row)."""
        ctk.CTkLabel(bar, text=f"{self.MATERIAL_NOUN.capitalize()} Materials:").pack(side="left", padx=(0, 5))
        self.materials_btn = ctk.CTkButton(
            bar, text="Select Materials...", width=140, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._open_material_filter
        )
        self.materials_btn.pack(side="left", padx=(0, 8))
        self.materials_label = ctk.CTkLabel(
            bar, text="None selected",
            font=ui_font("small"), text_color=self.theme.get_text_secondary()
        )
        self.materials_label.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(bar, text="Price (gp):").pack(side="left", padx=(0, 5))
        self.min_price_var = ctk.StringVar()
        self.min_price_var.trace_add("write", lambda *args: self._on_filter_changed())
        ctk.CTkEntry(
            bar, width=70, height=35, placeholder_text="Min", textvariable=self.min_price_var
        ).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(bar, text="-").pack(side="left", padx=(0, 5))
        self.max_price_var = ctk.StringVar()
        self.max_price_var.trace_add("write", lambda *args: self._on_filter_changed())
        ctk.CTkEntry(
            bar, width=70, height=35, placeholder_text="Max", textvariable=self.max_price_var
        ).pack(side="left", padx=(0, 20))

        self._add_clear_button(bar)

    # ---- context menu ----------------------------------------------------------------

    def _create_context_menu(self):
        """Create the right-click context menu."""
        self._build_context_menu([("Add to Character", self._context_add_to_character)])

    def _on_item_right_click(self, item, x: int, y: int):
        """Handle right-click on an item - show context menu."""
        self._context_item = item
        try:
            self.context_menu.tk_popup(x, y)
        finally:
            self.context_menu.grab_release()

    def _context_add_to_character(self):
        """Context menu: add this item to a character's inventory."""
        if not self._context_item:
            return
        character = self._pick_character(f"Add '{self._context_item.name}' to:")
        if not character:
            return

        from ui.character_sheet_view import get_sheet_manager
        sheet_manager = get_sheet_manager()
        sheet = sheet_manager.get_or_create_sheet(character.name, character)
        self._add_to_sheet(sheet, self._context_item)
        sheet_manager.update_sheet(character.name, sheet)
        messagebox.showinfo(
            "Added", f"Added '{self._context_item.name}' to {character.name}'s inventory."
        )

    # ---- bulk actions ---------------------------------------------------------------------

    def _bulk_fetch(self, name: str):
        return self.item_manager.get_item(name)

    def _bulk_store(self, entries: list) -> int:
        with self.item_manager.batch():
            return sum(bool(self.item_manager.update_item(e.name, e)) for e in entries)

    def _bulk_reload(self):
        self._load_items()

    def _bulk_all_tags(self) -> List[str]:
        return self.item_manager.get_all_tags()

    def _bulk_all_sources(self) -> List[str]:
        return self.item_manager.get_all_sources()

    def _bulk_give(self, character, entries: list) -> str:
        from ui.character_sheet_view import get_sheet_manager
        sheet_manager = get_sheet_manager()
        sheet = sheet_manager.get_or_create_sheet(character.name, character)
        for item in entries:
            self._add_to_sheet(sheet, item)
        sheet_manager.update_sheet(character.name, sheet)
        return f"Added {self._bulk_count_text(len(entries))} to {character.name}'s inventory."

    # ---- filtering ------------------------------------------------------------------------

    def _load_items(self):
        self._all_items = sorted(self.item_manager.items, key=lambda i: i.name.lower())

        type_options = ["All Types"] + self.item_manager.get_all_types()
        self.type_combo.configure(values=type_options)

        self._load_extra_options()

        self._on_filter_changed(immediate=True)

    @staticmethod
    def _summary(selected: List[str], mode: TagFilterMode, singular: str) -> str:
        count = len(selected)
        if count == 0:
            return "None selected"
        mode_str = {"has_all": "all", "has_any": "any", "has_none": "none"}[mode.value]
        if count == 1:
            return f"1 {singular} ({mode_str}): {selected[0]}"
        return f"{count} {singular}s ({mode_str})"

    def _open_tag_filter(self):
        available_tags = self.item_manager.get_all_tags()
        dialog = TagFilterDialog(
            self.winfo_toplevel(), available_tags, self._selected_tags, self._tag_filter_mode,
            noun="tags", empty_message=f"No tags found in your {self.PLURAL}."
        )
        self.wait_window(dialog)
        self._selected_tags = dialog.result
        self._tag_filter_mode = dialog.result_mode
        self._update_tags_label()
        self._on_filter_changed(immediate=True)

    def _update_tags_label(self):
        self.tags_label.configure(text=self._summary(self._selected_tags, self._tag_filter_mode, "tag"))

    def _open_material_filter(self):
        noun = self.MATERIAL_NOUN
        dialog = TagFilterDialog(
            self.winfo_toplevel(), self._all_materials(), self._selected_materials, self._material_filter_mode,
            window_title=f"Select {noun.capitalize()} Materials", prompt=f"Select {noun} materials to filter by:",
            noun="materials", empty_message=f"No {noun} materials found in your {self.PLURAL}."
        )
        self.wait_window(dialog)
        self._selected_materials = dialog.result
        self._material_filter_mode = dialog.result_mode
        self._update_materials_label()
        self._on_filter_changed(immediate=True)

    def _update_materials_label(self):
        self.materials_label.configure(
            text=self._summary(self._selected_materials, self._material_filter_mode, "material"))

    def _clear_filters(self):
        self.search_var.set("")
        self.titles_var.set(False)
        self.type_var.set("All Types")
        self.official_var.set("Any Content")
        self._clear_extra_filters()
        self.min_price_var.set("")
        self.max_price_var.set("")
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._selected_tags = []
        self._tag_filter_mode = TagFilterMode.HAS_ALL
        self._selected_materials = []
        self._material_filter_mode = TagFilterMode.HAS_ALL
        self._update_source_label()
        self._update_tags_label()
        self._update_materials_label()
        self._on_filter_changed(immediate=True)

    def _matches_tag_filter(self, item_values: List[str], selected: List[str], mode: TagFilterMode) -> bool:
        """Check an item's tags/materials list against a multi-select filter."""
        if not selected:
            return True
        values_lower = [v.lower() for v in item_values]
        selected_lower = [s.lower() for s in selected]
        if mode == TagFilterMode.HAS_ALL:
            return all(s in values_lower for s in selected_lower)
        if mode == TagFilterMode.HAS_ANY:
            return any(s in values_lower for s in selected_lower)
        # HAS_NONE
        return not any(s in values_lower for s in selected_lower)

    @staticmethod
    def _price_field_to_copper(text: str) -> Optional[int]:
        """Parse a min/max price entry (gp, possibly fractional) into copper."""
        text = text.strip()
        if not text:
            return None
        try:
            return round(float(text) * 100)  # 1 gp = 100 cp
        except ValueError:
            return None

    def _apply_filters(self):
        search_text = self.search_var.get().lower()
        type_filter = self.type_var.get()
        official_filter = self.official_var.get()
        extra = self._extra_filter()

        min_price_cp = self._price_field_to_copper(self.min_price_var.get())
        max_price_cp = self._price_field_to_copper(self.max_price_var.get())

        filtered = []
        for item in self._all_items:
            if not self._passes_search(search_text, item.name,
                                       lambda: [item.plain_description(), *item.tags]):
                continue

            if type_filter != "All Types" and item.type != type_filter:
                continue

            if extra is not None and not extra(item):
                continue

            if not self._matches_tag_filter(item.tags, self._selected_tags, self._tag_filter_mode):
                continue

            if not self._matches_tag_filter(self._item_materials(item), self._selected_materials,
                                            self._material_filter_mode):
                continue

            if not self._passes_source_filter(item.source):
                continue

            if not self._passes_official_filter(item.is_official, official_filter):
                continue

            if min_price_cp is not None or max_price_cp is not None:
                item_cp = parse_cost_to_copper(item.cost)
                if item_cp is None:
                    continue  # Unknown/"Varies" price can't satisfy a numeric bound
                if min_price_cp is not None and item_cp < min_price_cp:
                    continue
                if max_price_cp is not None and item_cp > max_price_cp:
                    continue

            filtered.append(item)

        self.list_panel.set_items(filtered)

    # ---- selection and editing ---------------------------------------------------------------

    def _on_item_selected(self, item):
        self.detail_panel.show_item(item)
        state = "normal" if item and item.is_custom else "disabled"
        self.edit_btn.configure(state=state)
        self.delete_btn.configure(state=state)

    def _on_add_item(self):
        """Open dialog to add a new item (manual entry or auto-detect from text)."""
        source_cls, _import_cls, _to_draft = self._text_import()

        source_dialog = source_cls(self.winfo_toplevel())
        self.wait_window(source_dialog)
        if source_dialog.result is None:
            return
        if source_dialog.result == "auto":
            self._on_add_item_from_text()
            return

        from ui.studio_launch import open_in_studio
        if open_in_studio(self, self.STUDIO_KIND):
            return

        dialog = self.EDITOR_DIALOG(self.winfo_toplevel(), self.ADD_TITLE)
        self.wait_window(dialog)

        if dialog.result:
            if self.item_manager.add_item(dialog.result):
                self._load_items()
                self.list_panel.select_when_listed(dialog.result.name)

    def _on_add_item_from_text(self):
        """Paste a block of text, auto-detect item fields, and review each draft."""
        _source_cls, import_cls, to_draft = self._text_import()

        added = import_from_pasted_text(
            self, import_cls=import_cls, load_converter=to_draft, noun="item", noun_phrase="an item",
            make_editor=lambda draft, review, progress: self.EDITOR_DIALOG(
                self.winfo_toplevel(), f"Review Item: {draft.name or 'Untitled'}",
                prefill_item=draft, review_fields=review, batch_progress=progress),
            add=self.item_manager.add_item)

        if added:
            self._load_items()
            self.list_panel.select_when_listed(added[-1])
            announce_added(added, "items")

    def _on_edit_item(self):
        item = self.list_panel.get_selected_item()
        if not item or not item.is_custom:
            return

        dialog = self.EDITOR_DIALOG(self.winfo_toplevel(), self.EDIT_TITLE, item)
        self.wait_window(dialog)

        if dialog.result:
            if self.item_manager.update_item(item.name, dialog.result):
                self._load_items()
                self.list_panel.select_when_listed(dialog.result.name)

    def _on_delete_item(self):
        item = self.list_panel.get_selected_item()
        if not item or not item.is_custom:
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{item.name}'?"):
            if self.item_manager.delete_item(item.name):
                self._load_items()
                self.detail_panel.show_item(None)

    def refresh(self):
        self._load_items()

    def select_item(self, name: str) -> bool:
        return self.list_panel.select_item(name)
