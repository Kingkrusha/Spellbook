"""
Equipment View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of equipment with a details panel,
laid out the same way as the Spells/Feats pages.
"""

import re
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Callable

from equipment import Equipment, EQUIPMENT_TYPE_OPTIONS, DEFAULT_EQUIPMENT_TYPE, get_equipment_manager
from theme import get_theme_manager
from settings import get_settings_manager
from ui.tag_editor import TagEditor
from ui.properties_editor import PropertiesEditor
from ui.tooltip import HoverTooltip


class EquipmentListPanel(ctk.CTkFrame):
    """A scrollable list panel for displaying and selecting equipment."""

    BATCH_SIZE = 15
    BATCH_DELAY_MS = 5

    def __init__(self, parent, on_select: Callable[[Optional[Equipment]], None]):
        super().__init__(parent, corner_radius=10)

        self.on_select = on_select
        self._items: List[Equipment] = []
        self._selected_index: Optional[int] = None
        self._item_buttons: List[ctk.CTkButton] = []
        self._pending_after_id: Optional[str] = None
        self.theme = get_theme_manager()
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))

        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)

    def _on_theme_changed(self):
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._refresh_buttons()

    def _create_widgets(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(header_frame, text="Equipment",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        self.count_label = ctk.CTkLabel(header_frame, text="0 items",
                                        font=ctk.CTkFont(size=12),
                                        text_color=self.theme.get_text_secondary())
        self.count_label.pack(side="right")

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _button_text(self, item: Equipment) -> str:
        name = f"* {item.name}" if item.is_custom else item.name
        return f"{name}  ({item.type})" if item.type else name

    def _create_item_button(self, item: Equipment, index: int) -> ctk.CTkButton:
        btn = ctk.CTkButton(
            self.scroll_frame,
            text=self._button_text(item),
            anchor="w", height=40, corner_radius=8,
            fg_color=("transparent" if index != self._selected_index
                      else self.theme.get_current_color('accent_primary')),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            font=ctk.CTkFont(size=13),
            command=lambda i=index: self._on_item_click(i)
        )
        btn.pack(fill="x", pady=2)
        return btn

    def _on_item_click(self, index: int):
        old_index = self._selected_index
        self._selected_index = index

        if old_index is not None and old_index < len(self._item_buttons):
            self._item_buttons[old_index].configure(fg_color="transparent")

        if index < len(self._item_buttons):
            self._item_buttons[index].configure(
                fg_color=self.theme.get_current_color('accent_primary')
            )

        if 0 <= index < len(self._items):
            self.on_select(self._items[index])

    def _update_item_button(self, btn: ctk.CTkButton, item: Equipment, index: int):
        btn.configure(
            text=self._button_text(item),
            fg_color=("transparent" if index != self._selected_index
                      else self.theme.get_current_color('accent_primary')),
            command=lambda i=index: self._on_item_click(i)
        )

    def _cancel_pending_load(self):
        if self._pending_after_id is not None:
            try:
                self.after_cancel(self._pending_after_id)
            except Exception:
                pass
            self._pending_after_id = None

    def set_items(self, items: List[Equipment], reset_scroll: bool = True):
        self._cancel_pending_load()

        current_name = None
        if self._selected_index is not None and self._selected_index < len(self._items):
            current_name = self._items[self._selected_index].name

        self._items = items

        new_selected_index = None
        if current_name:
            for i, item in enumerate(items):
                if item.name == current_name:
                    new_selected_index = i
                    break
        self._selected_index = new_selected_index

        self.count_label.configure(text=f"{len(items)} item{'s' if len(items) != 1 else ''}")

        if reset_scroll and self.scroll_frame.winfo_children():
            try:
                self.scroll_frame._parent_canvas.yview_moveto(0)
            except Exception:
                pass

        self._load_batch(0)

    def _load_batch(self, start_index: int):
        if not self.winfo_exists():
            return

        current_count = len(self._item_buttons)
        total = len(self._items)
        end_index = min(start_index + self.BATCH_SIZE, total)

        for i in range(start_index, end_index):
            if i < current_count:
                btn = self._item_buttons[i]
                self._update_item_button(btn, self._items[i], i)
                if not btn.winfo_ismapped():
                    btn.pack(fill="x", pady=2)
            else:
                btn = self._create_item_button(self._items[i], i)
                self._item_buttons.append(btn)

        if end_index >= total:
            for i in range(total, current_count):
                self._item_buttons[i].pack_forget()
            self._pending_after_id = None
        else:
            self._pending_after_id = self.after(self.BATCH_DELAY_MS, lambda: self._load_batch(end_index))

    def _refresh_buttons(self):
        for i, btn in enumerate(self._item_buttons):
            btn.configure(
                fg_color=(self.theme.get_current_color('accent_primary')
                          if i == self._selected_index else "transparent"),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary')
            )

    def get_selected_item(self) -> Optional[Equipment]:
        if self._selected_index is not None and self._selected_index < len(self._items):
            return self._items[self._selected_index]
        return None

    def select_item(self, name: str) -> bool:
        for i, item in enumerate(self._items):
            if item.name.lower() == name.lower():
                self._on_item_click(i)
                return True
        return False


class EquipmentDetailPanel(ctk.CTkFrame):
    """Panel displaying detailed information about an equipment item.

    Any optional field left blank on the item (source, crafting materials,
    crafting tool, tags) is simply not shown - its row's frame is never
    packed rather than being packed empty.
    """

    def __init__(self, parent):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._current_item: Optional[Equipment] = None
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)

    def _on_theme_changed(self):
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._update_colors()

    def _create_widgets(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)

        self.name_label = ctk.CTkLabel(
            self.scroll_frame, text="Select an item",
            font=ctk.CTkFont(size=24, weight="bold"), wraplength=400
        )
        self.name_label.pack(anchor="w", pady=(0, 5))

        self.type_badge = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5, padx=8, pady=2
        )

        self.stats_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=13),
            text_color=self.theme.get_text_secondary(),
            anchor="w", justify="left"
        )

        self.source_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_text_secondary()
        )

        self.crafting_frame = ctk.CTkFrame(
            self.scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8
        )
        # A link-aware text box (not a plain label) so crafting tool names can
        # be clicked to open that tool.
        from ui.rich_text_utils import DynamicText
        self.crafting_text = DynamicText(self.crafting_frame, self.theme, bg_color='bg_secondary')
        self.crafting_text.pack(fill="x", padx=10, pady=8)

        self.tags_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_current_color('accent_primary'),
            wraplength=400, justify="left"
        )

        # Named properties: each keyword renders as a chip; hovering it shows
        # the property's description in a tooltip.
        self.properties_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._properties_header = ctk.CTkLabel(
            self.properties_frame, text="Properties",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme.get_text_secondary(), anchor="w",
        )
        self._properties_header.pack(anchor="w", pady=(0, 4))
        self._properties_chip_area = ctk.CTkFrame(self.properties_frame, fg_color="transparent")
        self._properties_chip_area.pack(fill="x", anchor="w")
        self._property_tooltips = []

        self.desc_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._desc_widgets = []

    def _update_colors(self):
        self.type_badge.configure(fg_color=self.theme.get_current_color('accent_primary'))
        self.crafting_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
        self.tags_label.configure(text_color=self.theme.get_current_color('accent_primary'))

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
                    parent, text=prop["name"], font=ctk.CTkFont(size=12),
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

    @staticmethod
    def _crafting_tool_markup(text: str) -> str:
        """Turn a crafting-tool string into text with [[equipment:...]] links.

        The field is free text ("Smith's Tools", "Carpenter's Tools or
        Woodcarver's Tools"), so each name is only linked when it matches an
        equipment item; anything else (homebrew wording) is left as plain text.
        """
        manager = get_equipment_manager()

        def link(name: str) -> str:
            name = name.strip()
            item = manager.get_item(name) if name else None
            return f"[[equipment:{item.name}|{name}]]" if item else name

        whole = manager.get_item(text.strip())
        if whole:
            return link(text)
        parts = [p for p in re.split(r"\s+or\s+|,\s*(?:or\s+)?", text) if p.strip()]
        if len(parts) <= 1:
            return link(text)
        # Preserve the author's separators: re-join with " or ".
        return " or ".join(link(p) for p in parts)

    def _render_description(self, text: str):
        from ui.rich_text_utils import render_description_blocks

        self._clear_description()
        if not text:
            self.desc_frame.pack_forget()
            return

        self.desc_frame.pack(fill="x", anchor="w", pady=(10, 0))
        self._desc_widgets.extend(render_description_blocks(self.desc_frame, text, self.theme))

    def show_item(self, item: Optional[Equipment]):
        self._current_item = item

        # Detach every dynamic row first, then re-pack the ones we need in a
        # fixed order - so a row's position never depends on which item was
        # shown before this one.
        for w in (self.type_badge, self.stats_label, self.crafting_frame,
                  self.tags_label, self.properties_frame, self.desc_frame,
                  self.source_label):
            w.pack_forget()
        self._clear_description()

        if item is None:
            self.name_label.configure(text="Select an item")
            self._render_properties(None)
            return

        name_text = f"* {item.name}" if item.is_custom else item.name
        self.name_label.configure(text=name_text)

        self.type_badge.configure(text=item.type or DEFAULT_EQUIPMENT_TYPE)
        self.type_badge.pack(anchor="w", pady=(0, 5))

        stats_parts = []
        if item.cost:
            stats_parts.append(f"Cost: {item.cost}")
        stats_parts.append(f"Weight: {item.display_weight()}")
        self.stats_label.configure(text="   •   ".join(stats_parts))
        self.stats_label.pack(anchor="w", pady=(0, 10))

        crafting_lines = []
        if item.crafting_materials:
            crafting_lines.append(f"Crafting Materials: {', '.join(item.crafting_materials)}")
        if item.crafting_tool:
            crafting_lines.append(f"Crafting Tool: {self._crafting_tool_markup(item.crafting_tool)}")
        if crafting_lines:
            self.crafting_text.set_text("\n".join(crafting_lines))
            self.crafting_frame.pack(fill="x", pady=(0, 10))

        if item.tags:
            self.tags_label.configure(text=item.display_tags())
            self.tags_label.pack(anchor="w", pady=(0, 10))

        self._render_properties(item.properties)

        self._render_description(item.description)

        # Source is shown last, as a footer under everything else.
        if item.source:
            source_text = f"Source: {item.source}"
            if not item.is_official:
                source_text += " (Unofficial)"
            self.source_label.configure(text=source_text)
            self.source_label.pack(anchor="w", pady=(14, 0))


class EquipmentEditorDialog(ctk.CTkToplevel):
    """Dialog for creating or editing an equipment item."""

    def __init__(self, parent, title: str, item: Optional[Equipment] = None,
                 prefill_item: Optional[Equipment] = None, review_fields: Optional[List[str]] = None,
                 batch_progress: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x820")
        self.minsize(550, 650)
        self.transient(parent)
        self.grab_set()

        self.theme = get_theme_manager()
        self.equipment_manager = get_equipment_manager()
        self.result: Optional[Equipment] = None
        self._editing_item = item
        # Auto-detect pre-fill: populate the form from parsed text but keep
        # this a brand-new item, and mark fields for the reviewer to check.
        self._review_fields = set(review_fields or [])
        self._batch_progress = batch_progress

        self._create_widgets()
        if item:
            self._populate_from_item(item)
        elif prefill_item:
            self._populate_from_item(prefill_item)
            self._apply_review_highlights()

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        from ui.rich_text_utils import RichTextEditor

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        self._scroll = scroll

        ctk.CTkLabel(scroll, text="Name *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(scroll, width=400)
        self.name_entry.pack(fill="x", pady=(0, 10))

        row1 = ctk.CTkFrame(scroll, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))

        type_col = ctk.CTkFrame(row1, fg_color="transparent")
        type_col.pack(side="left", padx=(0, 15))
        ctk.CTkLabel(type_col, text="Type", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        type_options = sorted(set(EQUIPMENT_TYPE_OPTIONS) | set(self.equipment_manager.get_all_types()))
        self.type_var = ctk.StringVar(value=DEFAULT_EQUIPMENT_TYPE)
        self.type_combo = ctk.CTkComboBox(type_col, width=200, values=type_options, variable=self.type_var)
        self.type_combo.pack()

        cost_col = ctk.CTkFrame(row1, fg_color="transparent")
        cost_col.pack(side="left", padx=(0, 15))
        ctk.CTkLabel(cost_col, text="Cost", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.cost_entry = ctk.CTkEntry(cost_col, width=100, placeholder_text="e.g. 5 gp")
        self.cost_entry.pack()

        weight_col = ctk.CTkFrame(row1, fg_color="transparent")
        weight_col.pack(side="left")
        ctk.CTkLabel(weight_col, text="Weight (lb)", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.weight_entry = ctk.CTkEntry(weight_col, width=80, placeholder_text="0")
        self.weight_entry.pack()

        ctk.CTkLabel(scroll, text="Source", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.source_entry = ctk.CTkEntry(scroll, width=400, placeholder_text="e.g., Homebrew, Custom Campaign")
        self.source_entry.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Crafting Materials (comma-separated)",
                     font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.crafting_materials_entry = ctk.CTkEntry(
            scroll, width=400, placeholder_text="e.g., Iron, Leather Strips")
        self.crafting_materials_entry.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Crafting Tool", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.crafting_tool_entry = ctk.CTkEntry(scroll, width=400, placeholder_text="e.g., Smith's Tools")
        self.crafting_tool_entry.pack(fill="x", pady=(0, 10))

        self.tag_editor = TagEditor(scroll, get_available_tags=self.equipment_manager.get_all_tags)
        self.tag_editor.pack(fill="x", pady=(0, 10))

        self.properties_editor = PropertiesEditor(
            scroll, get_suggestions=self.equipment_manager.get_all_properties)
        self.properties_editor.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Description", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
        self.desc_text = ctk.CTkTextbox(scroll, height=200)
        self._rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(scroll)
        toolbar.pack(fill="x", pady=(5, 5))
        self.desc_text.pack(fill="x", pady=(0, 10))

        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1,
            command=self.destroy
        ).pack(side="right", padx=(5, 0))

        ctk.CTkButton(
            btn_frame, text="Save", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            command=self._save
        ).pack(side="right")

    def _populate_from_item(self, item: Equipment):
        self.name_entry.insert(0, item.name)
        self.type_var.set(item.type or DEFAULT_EQUIPMENT_TYPE)
        if item.cost:
            self.cost_entry.insert(0, item.cost)
        self.weight_entry.insert(0, str(item.weight) if item.weight else "0")
        if item.source:
            self.source_entry.insert(0, item.source)
        if item.crafting_materials:
            self.crafting_materials_entry.insert(0, ", ".join(item.crafting_materials))
        if item.crafting_tool:
            self.crafting_tool_entry.insert(0, item.crafting_tool)
        self.tag_editor.set_tags(item.tags)
        self.properties_editor.set_properties(item.properties)
        self.desc_text.insert("1.0", item.description)

    _REVIEW_FIELD_LABELS = {
        "name": "Name", "type": "Type", "cost": "Cost", "weight": "Weight",
        "source": "Source", "crafting_materials": "Crafting Materials",
        "crafting_tool": "Crafting Tool", "description": "Description", "tags": "Tags",
        "properties": "Properties",
    }

    def _apply_review_highlights(self):
        """Add the auto-detect disclaimer banner and outline uncertain fields."""
        try:
            warn = self.theme.get_current_color('button_warning')
        except Exception:
            warn = "#d4a017"

        banner = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_secondary'),
                              corner_radius=8)
        try:
            banner.pack(fill="x", padx=20, pady=(12, 0), before=self._scroll)
        except Exception:
            banner.pack(fill="x", padx=20, pady=(12, 0))

        heading = "Auto-detected from text - please review before saving"
        if self._batch_progress:
            heading = f"{heading}   ({self._batch_progress})"
        ctk.CTkLabel(banner, text="⚠  " + heading,
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=warn, anchor="w",
                     justify="left", wraplength=520).pack(fill="x", padx=12, pady=(8, 2))

        review = [f for f in self._review_fields if f in self._REVIEW_FIELD_LABELS]
        if review:
            names = ", ".join(sorted(self._REVIEW_FIELD_LABELS[f] for f in review))
            msg = f"Fields to double-check (outlined below): {names}"
        else:
            msg = "All fields were detected with high confidence, but a quick check is still wise."
        ctk.CTkLabel(banner, text=msg, font=ctk.CTkFont(size=11),
                     text_color=self.theme.get_text_secondary(), anchor="w",
                     justify="left", wraplength=520).pack(fill="x", padx=12, pady=(0, 2))

        ctk.CTkLabel(
            banner,
            text=("Auto-detection is rule-based, not perfect - accuracy drops for "
                  "irregularly formatted text. Nothing is saved until you click Save."),
            font=ctk.CTkFont(size=11), text_color=self.theme.get_text_secondary(),
            anchor="w", justify="left", wraplength=520,
        ).pack(fill="x", padx=12, pady=(0, 8))

        widget_map = {
            "name": self.name_entry,
            "type": self.type_combo,
            "cost": self.cost_entry,
            "weight": self.weight_entry,
            "source": self.source_entry,
            "crafting_materials": self.crafting_materials_entry,
            "crafting_tool": self.crafting_tool_entry,
        }
        for field_name in self._review_fields:
            w = widget_map.get(field_name)
            if w is None:
                continue
            try:
                w.configure(border_color=warn, border_width=2)
            except Exception:
                pass

    def _save(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Name is required.", parent=self)
            return

        weight_text = self.weight_entry.get().strip() or "0"
        try:
            weight = float(weight_text)
            if weight < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Weight must be a non-negative number.", parent=self)
            return

        crafting_materials_text = self.crafting_materials_entry.get().strip()
        crafting_materials = [m.strip() for m in crafting_materials_text.split(",") if m.strip()]

        self.result = Equipment(
            name=name,
            type=self.type_var.get().strip() or DEFAULT_EQUIPMENT_TYPE,
            cost=self.cost_entry.get().strip(),
            weight=weight,
            source=self.source_entry.get().strip(),
            crafting_materials=crafting_materials,
            crafting_tool=self.crafting_tool_entry.get().strip(),
            description=self.desc_text.get("1.0", "end-1c").strip(),
            tags=self.tag_editor.get_tags(),
            properties=self.properties_editor.get_properties(),
            is_official=False,
            is_custom=True,
        )
        self.destroy()


class EquipmentView(ctk.CTkFrame):
    """Main view for browsing and managing equipment."""

    def __init__(self, parent, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))

        self.equipment_manager = get_equipment_manager()
        self.settings_manager = get_settings_manager()
        self.on_back = on_back
        self._all_items: List[Equipment] = []
        self._filter_debounce_id: Optional[str] = None
        self._filter_debounce_delay = 150

        self._create_widgets()
        self._load_items()
        self.theme.add_listener(self._on_theme_changed)

    def _on_theme_changed(self):
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        if hasattr(self, 'paned'):
            self._update_paned_colors()

    def _create_widgets(self):
        self._create_filter_bar()

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.paned = tk.PanedWindow(
            self.content, orient=tk.HORIZONTAL, sashwidth=8, sashrelief=tk.RAISED,
            handlesize=0, opaqueresize=False, sashcursor="sb_h_double_arrow"
        )
        self.paned.pack(fill="both", expand=True)
        self._update_paned_colors()

        self.list_panel = EquipmentListPanel(self.paned, on_select=self._on_item_selected)
        self.detail_panel = EquipmentDetailPanel(self.paned)

        self.paned.add(self.list_panel, minsize=280, stretch="always")
        self.paned.add(self.detail_panel, minsize=400, stretch="always")

        self.after(100, lambda: self.paned.sash_place(0, 320, 0))

    def _update_paned_colors(self):
        self.paned.configure(bg=self.theme.get_current_color("pane_sash"))

    def _create_filter_bar(self):
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)

        if self.on_back:
            ctk.CTkButton(
                filter_bar, text="← Collections", width=110,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                command=self.on_back
            ).pack(side="left", padx=(0, 15))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        ctk.CTkEntry(
            filter_bar, width=220, height=35,
            placeholder_text="Search equipment...", textvariable=self.search_var
        ).pack(side="left", padx=(0, 15))

        ctk.CTkLabel(filter_bar, text="Type:").pack(side="left", padx=(0, 5))
        self.type_var = ctk.StringVar(value="All Types")
        self.type_combo = ctk.CTkComboBox(
            filter_bar, width=170, height=35, values=["All Types"],
            variable=self.type_var, command=lambda _: self._on_filter_changed(immediate=True),
            state="readonly"
        )
        self.type_combo.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(filter_bar, text="Tag:").pack(side="left", padx=(0, 5))
        self.tag_var = ctk.StringVar(value="All Tags")
        self.tag_combo = ctk.CTkComboBox(
            filter_bar, width=150, height=35, values=["All Tags"],
            variable=self.tag_var, command=lambda _: self._on_filter_changed(immediate=True),
            state="readonly"
        )
        self.tag_combo.pack(side="left")

        ctk.CTkButton(
            filter_bar, text="+ Add Equipment", width=130, height=35,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_add_item
        ).pack(side="right")

        self.delete_btn = ctk.CTkButton(
            filter_bar, text="Delete", width=80, height=35,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._on_delete_item
        )
        self.delete_btn.pack(side="right", padx=(0, 5))

        self.edit_btn = ctk.CTkButton(
            filter_bar, text="Edit", width=80, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_edit_item
        )
        self.edit_btn.pack(side="right", padx=(0, 5))

        self.edit_btn.configure(state="disabled")
        self.delete_btn.configure(state="disabled")

    def _load_items(self):
        self._all_items = sorted(self.equipment_manager.items, key=lambda i: i.name.lower())

        type_options = ["All Types"] + self.equipment_manager.get_all_types()
        self.type_combo.configure(values=type_options)

        tag_options = ["All Tags"] + self.equipment_manager.get_all_tags()
        self.tag_combo.configure(values=tag_options)

        self._on_filter_changed(immediate=True)

    def _on_filter_changed(self, immediate: bool = False):
        if self._filter_debounce_id is not None:
            self.after_cancel(self._filter_debounce_id)
            self._filter_debounce_id = None

        delay = 10 if immediate else self._filter_debounce_delay
        self._filter_debounce_id = self.after(delay, self._apply_filters)

    def _apply_filters(self):
        search_text = self.search_var.get().lower()
        type_filter = self.type_var.get()
        tag_filter = self.tag_var.get()

        filtered = []
        for item in self._all_items:
            if search_text:
                if (search_text not in item.name.lower()
                        and search_text not in item.plain_description().lower()
                        and not any(search_text in t.lower() for t in item.tags)):
                    continue

            if type_filter != "All Types" and item.type != type_filter:
                continue

            if tag_filter != "All Tags" and tag_filter not in item.tags:
                continue

            filtered.append(item)

        self.list_panel.set_items(filtered)

    def _on_item_selected(self, item: Optional[Equipment]):
        self.detail_panel.show_item(item)
        if item:
            self.edit_btn.configure(state="normal" if item.is_custom else "disabled")
            self.delete_btn.configure(state="normal" if item.is_custom else "disabled")
        else:
            self.edit_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")

    def _on_add_item(self):
        """Open dialog to add a new item (manual entry or auto-detect from text)."""
        from ui.equipment_text_import import AddEquipmentSourceDialog

        source_dialog = AddEquipmentSourceDialog(self.winfo_toplevel())
        self.wait_window(source_dialog)
        if source_dialog.result is None:
            return
        if source_dialog.result == "auto":
            self._on_add_item_from_text()
            return

        dialog = EquipmentEditorDialog(self.winfo_toplevel(), "Add Equipment")
        self.wait_window(dialog)

        if dialog.result:
            if self.equipment_manager.add_item(dialog.result):
                self._load_items()
                self.list_panel.select_item(dialog.result.name)

    def _on_add_item_from_text(self):
        """Paste a block of text, auto-detect item fields, and review each draft."""
        from ui.equipment_text_import import EquipmentTextImportDialog

        import_dialog = EquipmentTextImportDialog(self.winfo_toplevel())
        self.wait_window(import_dialog)
        parsed_list = import_dialog.result
        if not parsed_list:
            return

        try:
            from text_import.equipment_parser import to_equipment
        except Exception as exc:
            messagebox.showerror("Auto-Detect Unavailable",
                                 f"Could not load the text importer:\n{exc}")
            return

        added = []
        total = len(parsed_list)
        for idx, parsed in enumerate(parsed_list, 1):
            try:
                draft = to_equipment(parsed)
            except Exception as exc:
                messagebox.showerror("Parse Error",
                                     f"Could not build item {idx} of {total}:\n{exc}")
                continue

            review = sorted(set(parsed.needs_review()) | set(parsed.uncertain_fields()))
            progress = f"{idx} of {total}" if total > 1 else ""

            editor = EquipmentEditorDialog(
                self.winfo_toplevel(), f"Review Item: {draft.name or 'Untitled'}",
                prefill_item=draft, review_fields=review, batch_progress=progress,
            )
            self.wait_window(editor)

            if editor.result:
                if self.equipment_manager.add_item(editor.result):
                    added.append(editor.result.name)
                else:
                    messagebox.showerror(
                        "Error",
                        f"An item named '{editor.result.name}' already exists. "
                        "It was not added.")
            elif idx < total:
                if not messagebox.askyesno(
                        "Continue?",
                        "Skip this item and continue reviewing the remaining "
                        f"{total - idx} item(s)?"):
                    break

        if added:
            self._load_items()
            self.list_panel.select_item(added[-1])
            if len(added) > 1:
                messagebox.showinfo("Items Added",
                                    f"Added {len(added)} items:\n" + "\n".join(added))

    def _on_edit_item(self):
        item = self.list_panel.get_selected_item()
        if not item or not item.is_custom:
            return

        dialog = EquipmentEditorDialog(self.winfo_toplevel(), "Edit Equipment", item)
        self.wait_window(dialog)

        if dialog.result:
            if self.equipment_manager.update_item(item.name, dialog.result):
                self._load_items()
                self.list_panel.select_item(dialog.result.name)

    def _on_delete_item(self):
        item = self.list_panel.get_selected_item()
        if not item or not item.is_custom:
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{item.name}'?"):
            if self.equipment_manager.delete_item(item.name):
                self._load_items()
                self.detail_panel.show_item(None)

    def refresh(self):
        self._load_items()

    def select_item(self, name: str) -> bool:
        return self.list_panel.select_item(name)
