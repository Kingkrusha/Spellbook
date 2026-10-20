"""
Lineages View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of lineages with details panel.
"""

import customtkinter as ctk
from typography import ui_font
from ui.text_import_flow import announce_added, import_from_pasted_text
from ui.versioned_detail import VersionedDetailBase
from ui.label_text import LabeledLabel
from tkinter import messagebox
from typing import List, Optional
from lineage import Lineage, LineageTrait, LineageManager, get_lineage_manager
from theme import get_theme_manager
from settings import get_settings_manager
from legacy_content import legacy_pair_key
from content_versions import VersionCatalog, display_name
from ui.filter_widgets import SourceFilterMode
from ui.virtual_list import VirtualListPanel
from ui.editor_host import DialogWindow, EditorBody, EmbeddedWindow
from ui.bulk_actions import BulkActionsMixin
from ui.collection_page import CollectionPageMixin
from ui.review_banner import add_review_banner, outline_fields


def _list_name(name: str) -> str:
    """A lineage's name in the list: one entry for all its versions, so no "(Legacy)" tag."""
    return display_name(name)


class LineageListPanel(VirtualListPanel):
    """The virtualized, selectable list of lineages."""

    TITLE = "Lineages"
    NOUN = "lineage"
    KEY = staticmethod(legacy_pair_key)   # one entry stands for all the versions of a lineage

    def row_text(self, lineage: Lineage) -> str:
        name = _list_name(lineage.name)
        return f"* {name}" if lineage.is_custom else name

    def set_lineages(self, lineages: List[Lineage], reset_scroll: bool = True,
                     preserve_selection: Optional[str] = None):
        # Only an explicitly preserved entry stays selected, and it is shown again in the detail panel
        self.set_items(lineages, reset_scroll, keep=preserve_selection, keep_current=False, notify=True)

    def get_selected_lineage(self) -> Optional[Lineage]:
        return self.get_selected()

    def select_lineage(self, name: str, version: Optional[Lineage] = None) -> bool:
        """Select a lineage by name. "Orc (Legacy: VGM)" selects the Orc entry; ``version`` is
        the exact version to show in it."""
        return self.select_by_name(name, version)


class LineageDetailPanel(VersionedDetailBase):
    """Panel displaying detailed information about a lineage."""

    CURRENT_ATTR = "_current_lineage"
    
    def _create_widgets(self):
        """Create the detail view widgets."""
        self._add_scroll_and_title("Select a lineage", 800)

        # Source info (a drop-down when there are several versions)
        self._add_version_bar()
        
        # Stats frame (creature type, size, speed)
        self.stats_frame = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        
        self.stats_inner = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        self.stats_inner.pack(fill="x", padx=10, pady=8)
        
        # Create stats labels - left aligned
        self.creature_type_label = LabeledLabel(
            self.stats_inner, text="",
            font=ui_font("body"),
            anchor="w"
        )
        self.creature_type_label.pack(fill="x", anchor="w", pady=1)
        
        self.size_label = LabeledLabel(
            self.stats_inner, text="",
            font=ui_font("body"),
            anchor="w"
        )
        self.size_label.pack(fill="x", anchor="w", pady=1)
        
        self.speed_label = LabeledLabel(
            self.stats_inner, text="",
            font=ui_font("body"),
            anchor="w"
        )
        self.speed_label.pack(fill="x", anchor="w", pady=1)
        
        # Description
        self.desc_header = ctk.CTkLabel(
            self.scroll_frame, text="Description",
            font=ui_font("subheading", bold=True)
        )
        
        # Description container for rich text rendering
        self.description_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._desc_widgets = []
        
        # Traits section
        self.traits_header = ctk.CTkLabel(
            self.scroll_frame, text="Traits",
            font=ui_font("subheading", bold=True)
        )
        
        # Container for trait widgets
        self.traits_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._trait_widgets = []
    
    def _update_colors(self):
        """Update colors after theme change."""
        self.stats_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
    
    def _clear_traits(self):
        """Clear all trait widgets."""
        for widget in self._trait_widgets:
            widget.destroy()
        self._trait_widgets = []
    
    def _render_trait(self, trait: LineageTrait):
        """Render a single trait with support for markdown tables and spell links."""
        # Trait frame
        trait_frame = ctk.CTkFrame(
            self.traits_container,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        trait_frame.pack(fill="x", pady=2)
        self._trait_widgets.append(trait_frame)
        
        inner = ctk.CTkFrame(trait_frame, fg_color="transparent")
        inner.pack(fill="x", expand=True, padx=10, pady=6)
        
        # Trait name
        name_label = ctk.CTkLabel(
            inner, text=trait.name,
            font=ui_font("subheading", 13, bold=True),
            anchor="w"
        )
        name_label.pack(fill="x", anchor="w")
        
        # Trait description with dynamic resizing
        if trait.description:
            from ui.rich_text_utils import render_description_blocks
            render_description_blocks(inner, trait.description, self.theme, bg_color='bg_secondary')
    
    def _render_description(self, text: str):
        """Render description with bold text and dynamic resizing."""
        from ui.rich_text_utils import DynamicText
        
        self._clear_description()
        
        if not text:
            return
        
        from ui.rich_text_utils import render_description_blocks
        self._desc_widgets.extend(render_description_blocks(self.description_container, text, self.theme))
    
    def _show_item(self, item, versions=None):
        self.show_lineage(item, versions)

    def show_lineage(self, lineage: Optional[Lineage], versions: Optional[List[Lineage]] = None):
        """Display details for a lineage (``versions``: every version offered in the Source drop-down)."""
        self._current_lineage = lineage
        self._versions = list(versions or [])
        
        if lineage is None:
            self.name_label.configure(text="Select a lineage")
            self.source_label.configure(text="")
            self.stats_frame.pack_forget()
            self.desc_header.pack_forget()
            self._clear_description()
            self.description_container.pack_forget()
            self.traits_header.pack_forget()
            self.traits_container.pack_forget()
            self._clear_traits()
            return
        
        # Name (with custom indicator)
        name_text = f"* {display_name(lineage.name)}" if lineage.is_custom else display_name(lineage.name)
        self.name_label.configure(text=name_text)
        
        # Source
        if lineage.source:
            source_text = f"Source: {lineage.source}"
            if not lineage.is_official:
                source_text += " (Unofficial)"
            if lineage.is_legacy:
                source_text += " [Legacy]"
            self.source_label.configure(text=source_text)
        else:
            self.source_label.configure(text="")
        if len(self._versions) > 1:
            self.source_label.set_versions(self._versions, lineage)
        
        # Stats
        self.creature_type_label.configure(text=f"Creature Type: {lineage.creature_type}")
        self.size_label.configure(text=f"Size: {lineage.size}")
        self.speed_label.configure(text=f"Speed: {lineage.speed} feet")
        self.stats_frame.pack(fill="x", pady=(0, 15))
        
        # Description - render with RichTextRenderer for bold and spell popups
        if lineage.description:
            self.desc_header.pack(anchor="w", pady=(10, 5))
            self._render_description(lineage.description)
            self.description_container.pack(fill="x", pady=(0, 10))
        else:
            self.desc_header.pack_forget()
            self._clear_description()
            self.description_container.pack_forget()
        
        # Traits
        self._clear_traits()
        if lineage.traits:
            self.traits_header.pack(anchor="w", pady=(10, 5))
            self.traits_container.pack(fill="x")
            for trait in lineage.traits:
                self._render_trait(trait)
        else:
            self.traits_header.pack_forget()
            self.traits_container.pack_forget()


class LineagesView(BulkActionsMixin, CollectionPageMixin, ctk.CTkFrame):
    """Main view for browsing and managing lineages."""

    MANAGER_ATTR = "lineage_manager"
    PLURAL = "lineages"
    
    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        
        self.lineage_manager = get_lineage_manager()
        self.character_manager = character_manager
        self.settings_manager = get_settings_manager()
        self.on_back = on_back
        self._all_lineages: List[Lineage] = []
        self._catalog = VersionCatalog([])
        self._filtered_lineages: List[Lineage] = []
        self._compare_mode = False
        self._compare_lineage: Optional[Lineage] = None
        self._context_lineage: Optional[Lineage] = None

        # Source and official-content filter state
        self._selected_sources: List[str] = []
        self._source_filter_mode: SourceFilterMode = SourceFilterMode.INCLUDE

        # Debouncing for filter changes
        self._filter_debounce_id: Optional[str] = None
        self._filter_debounce_delay = 150  # ms for text input
        
        self._create_widgets()
        self._setup_bulk_actions()
        self._create_context_menu()
        self._create_compare_panel()
        self._load_lineages()
        self.theme.add_listener(self._on_theme_changed)
    
    def _create_filter_bar(self):
        """Create the filter bar at the top."""
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)

        self._add_back_button(filter_bar)
        self._add_search_entry(filter_bar, "Search lineages...", 200)
        self._add_filter_combo(filter_bar, "size", "Size:", "All Sizes", ["All Sizes"], 150)
        self._add_filter_combo(filter_bar, "type", "Type:", "All Types", ["All Types"], 150)
        self._add_action_buttons(filter_bar, "+ Add Lineage", 120, self._on_add_lineage,
                                 self._on_edit_lineage, self._on_delete_lineage)

        # Second row: source, official content, min speed, clear
        filter_bar2 = self._filter_row()
        self._add_source_filter(filter_bar2)
        self._add_content_filter(filter_bar2)
        self._add_filter_combo(filter_bar2, "min_speed", "Min Speed:", "Any", ["Any"], 90, (0, 20))
        self._add_clear_button(filter_bar2)

    def _create_context_menu(self):
        """Create the right-click context menu for lineages."""
        self._build_context_menu([
            ("Set as Character Lineage", self._context_set_lineage),
            ("Compare", self._context_compare),
        ])

    def _create_panes(self):
        self._create_panes_with_container(
            LineageListPanel, LineageDetailPanel, self._on_lineage_selected, self._on_lineage_right_click)

    def _create_compare_panel(self):
        """Create the compare lineage panel (hidden initially)."""
        self._build_compare_panel("Compare Lineages", LineageDetailPanel, self._close_compare)

    BULK_ACTIONS = ("source",)
    BULK_NOUN, BULK_PLURAL = "lineage", "lineages"

    def _bulk_fetch(self, name: str):
        return self.lineage_manager.get_lineage(name)

    def _bulk_store(self, entries: list) -> int:
        with self.lineage_manager.batch():
            return sum(bool(self.lineage_manager.add_lineage(e)) for e in entries)

    def _bulk_reload(self):
        self._load_lineages()

    def _bulk_all_sources(self) -> List[str]:
        return self.lineage_manager.get_all_sources()

    def _load_lineages(self):
        """Load all lineages from manager."""
        self._all_lineages = self.lineage_manager.lineages.copy()
        self._catalog = VersionCatalog(self._all_lineages)
        self._update_filter_options()
        self._on_filter_changed(immediate=True)
    
    def _update_filter_options(self):
        """Update filter dropdown options based on loaded lineages."""
        # Update size options
        sizes = self.lineage_manager.get_all_sizes()
        size_options = ["All Sizes"] + sizes
        self.size_combo.configure(values=size_options)

        # Update type options
        types = self.lineage_manager.get_all_creature_types()
        type_options = ["All Types"] + types
        self.type_combo.configure(values=type_options)

        # Update min speed options, preserving the current selection if valid
        current_speed = self.min_speed_var.get()
        speed_options = ["Any"] + [str(s) for s in self.lineage_manager.get_all_speeds()]
        self.min_speed_combo.configure(values=speed_options)
        self.min_speed_var.set(current_speed if current_speed in speed_options else "Any")

    def _clear_filters(self):
        """Reset every filter (search, size, type, source, content, speed) to defaults."""
        self.search_var.set("")
        self.titles_var.set(False)
        self.size_var.set("All Sizes")
        self.type_var.set("All Types")
        self.official_var.set("Any Content")
        self.min_speed_var.set("Any")
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._update_source_label()
        self._on_filter_changed(immediate=True)

    def _apply_filters(self):
        """Apply current filters to the lineage list."""
        search = self.search_var.get().lower()
        size_filter = self.size_var.get()
        type_filter = self.type_var.get()
        official_filter = self.official_var.get()
        min_speed = self.min_speed_var.get()

        filtered = []
        for lineage in self._all_lineages:
            # Search filter
            if not self._passes_search(search, lineage.name, [t.name for t in lineage.traits]):
                continue

            # Size filter
            if size_filter != "All Sizes" and lineage.size != size_filter:
                # Handle "Small or Medium" type sizes
                if size_filter not in lineage.size:
                    continue

            # Type filter
            if type_filter != "All Types" and lineage.creature_type != type_filter:
                continue

            # Source filter
            if not self._passes_source_filter(lineage.source):
                continue

            # Official content filter
            if not self._passes_official_filter(lineage.is_official, official_filter):
                continue

            # Min speed filter
            if min_speed != "Any" and lineage.speed < int(min_speed):
                continue

            filtered.append(lineage)

        # One entry per lineage: its versions (2024, 2014, a 2014 book's update) are switched in the
        # detail panel's Source drop-down; the Legacy content setting decides which are offered
        filtered = self._catalog.collapse(filtered, self.settings_manager.settings.legacy_content_filter)
        
        self._filtered_lineages = filtered
        
        # Preserve selection if possible
        current = self.list_panel.get_selected_lineage()
        preserve = current.name if current else None
        
        self.list_panel.set_lineages(filtered, preserve_selection=preserve)
    
    def _on_lineage_selected(self, lineage: Optional[Lineage]):
        """Handle lineage selection."""
        setting = self.settings_manager.settings.legacy_content_filter
        self.detail_panel.show_lineage(lineage, self._catalog.options(lineage, setting) if lineage else None)
    
    def _on_lineage_right_click(self, lineage: Lineage, x: int, y: int):
        """Handle right-click on lineage - show context menu."""
        self._context_lineage = lineage
        self.context_menu.tk_popup(x, y)
    
    def _context_set_lineage(self):
        """Set lineage for current character from context menu."""
        if self._context_lineage and self.character_manager:
            char = self._active_character()
            if char:
                char.lineage = self._context_lineage.name
                try:
                    from character import update_subclass_spells
                    update_subclass_spells(char)               # a species can give spells
                except Exception as e:
                    print(f"Could not update granted spells: {e}")
                self.character_manager.save_characters()
                messagebox.showinfo(
                    "Lineage Set",
                    f"Set {char.name}'s lineage to {self._context_lineage.name}.",
                    parent=self
                )
    
    def _context_compare(self):
        """Show compare panel from context menu."""
        if self._context_lineage:
            self._show_compare(self._context_lineage)
    
    def _show_compare(self, lineage: Lineage):
        """Show compare panel with the given lineage."""
        self._compare_mode = True
        self._compare_lineage = lineage
        
        # Hide list, show compare
        self.list_panel.pack_forget()
        self.compare_container.pack(fill="both", expand=True)
        self.compare_detail.show_lineage(lineage)
    
    def _close_compare(self):
        """Close the compare panel."""
        self._compare_mode = False
        self._compare_lineage = None
        
        self.compare_container.pack_forget()
        self.list_panel.pack(fill="both", expand=True)
    
    def _on_add_lineage(self):
        """Open dialog to add a new lineage (manual entry or auto-detect from text)."""
        from ui.lineage_text_import import AddLineageSourceDialog

        source_dialog = AddLineageSourceDialog(self.winfo_toplevel())
        self.wait_window(source_dialog)
        if source_dialog.result is None:
            return
        if source_dialog.result == "auto":
            self._on_add_lineage_from_text()
            return

        from ui.studio_launch import open_in_studio
        if open_in_studio(self, "lineages"):
            return

        dialog = LineageEditorDialog(self.winfo_toplevel(), self.lineage_manager)
        dialog.grab_set()
        self.wait_window(dialog)

        if dialog.result:
            self._load_lineages()
            self.list_panel.select_when_listed(dialog.result.name)

    def _on_add_lineage_from_text(self):
        """Paste a block of text, auto-detect lineage fields, and review each draft."""
        from ui.lineage_text_import import LineageTextImportDialog

        def load_converter():
            from text_import.lineage_parser import to_lineage
            return to_lineage

        def make_editor(draft, review, progress):
            editor = LineageEditorDialog(
                self.winfo_toplevel(), self.lineage_manager,
                prefill_lineage=draft, review_fields=review, batch_progress=progress,
            )
            editor.grab_set()
            return editor

        # LineageEditorDialog._save() already persists via the manager, so there is nothing more to add.
        added = import_from_pasted_text(
            self, import_cls=LineageTextImportDialog, load_converter=load_converter, noun="lineage",
            noun_phrase="a lineage", make_editor=make_editor, add=lambda lineage: True)

        if added:
            self._load_lineages()
            self.list_panel.select_when_listed(added[-1])
            announce_added(added, "lineages")

    def _on_edit_lineage(self):
        """Edit the selected lineage."""
        lineage = self.list_panel.get_selected_lineage()
        if not lineage:
            messagebox.showwarning("No Selection", "Please select a lineage to edit.", parent=self)
            return
        
        if lineage.is_official and not lineage.is_custom:
            messagebox.showwarning(
                "Cannot Edit",
                "Official lineages cannot be edited. You can create a copy instead.",
                parent=self
            )
            return
        
        dialog = LineageEditorDialog(
            self.winfo_toplevel(), self.lineage_manager, lineage=lineage
        )
        dialog.grab_set()
        self.wait_window(dialog)
        
        if dialog.result:
            self._load_lineages()
            self.list_panel.select_when_listed(dialog.result.name)
    
    def _on_delete_lineage(self):
        """Delete the selected lineage."""
        lineage = self.list_panel.get_selected_lineage()
        if not lineage:
            messagebox.showwarning("No Selection", "Please select a lineage to delete.", parent=self)
            return
        
        if lineage.is_official and not lineage.is_custom:
            messagebox.showwarning(
                "Cannot Delete",
                "Official lineages cannot be deleted.",
                parent=self
            )
            return
        
        if messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{lineage.name}'?",
            parent=self
        ):
            self.lineage_manager.remove_lineage(lineage.name)
            self._load_lineages()
    
    def refresh(self):
        """Refresh the lineage list."""
        self._load_lineages()
    
    def select_lineage(self, name: str) -> bool:
        """Select a lineage by name. Returns True if found."""
        return self.list_panel.select_lineage(name, self._catalog.find(name))


class LineageEditorBody(EditorBody):
    """Dialog for creating/editing lineages. (the form; see ui/editor_host.py)"""
    
    def __init__(self, parent, lineage_manager: LineageManager, lineage: Optional[Lineage] = None,
                 prefill_lineage: Optional[Lineage] = None, review_fields: Optional[List[str]] = None,
                 batch_progress: str = ""):
        super().__init__(parent)

        self.lineage_manager = lineage_manager
        self.editing_lineage = lineage
        self.result: Optional[Lineage] = None
        self.theme = get_theme_manager()
        self._trait_entries = []  # List of (name_entry, desc_entry, frame) tuples
        # Auto-detect pre-fill: populate the form from parsed text but keep this
        # a brand-new lineage, and mark fields for the reviewer to double-check.
        self._review_fields = set(review_fields or [])
        self._batch_progress = batch_progress

        self.title("Edit Lineage" if lineage else "Add Lineage")
        self.geometry("700x700")
        self.minsize(600, 500)

        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 700) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 700) // 2
        self.geometry(f"+{x}+{y}")

        self._create_widgets()

        if lineage:
            self._populate_from_lineage(lineage)
        elif prefill_lineage:
            self._populate_from_lineage(prefill_lineage)
            self._apply_review_highlights()
    
    def _create_widgets(self):
        """Create the editor UI."""
        # Main scrollable container
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)

        # Name
        self.name_entry = self._add_entry_field(self.scroll, "Name:")

        # Row for creature type, size, speed
        stats_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 15))

        # Creature Type
        type_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        type_frame.pack(side="left", padx=(0, 20))
        self._field_label(type_frame, "Creature Type:")
        self.creature_type_entry = ctk.CTkEntry(type_frame, width=150, height=35)
        self.creature_type_entry.pack()
        self.creature_type_entry.insert(0, "Humanoid")

        # Size
        size_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        size_frame.pack(side="left", padx=(0, 20))
        self._field_label(size_frame, "Size:")
        self.size_combo = ctk.CTkComboBox(
            size_frame, width=150, height=35,
            values=["Small", "Medium", "Large", "Small or Medium"],
            state="readonly"
        )
        self.size_combo.pack()
        self.size_combo.set("Medium")

        # Speed
        speed_frame = ctk.CTkFrame(stats_frame, fg_color="transparent")
        speed_frame.pack(side="left")
        self._field_label(speed_frame, "Speed (feet):")
        self.speed_entry = ctk.CTkEntry(speed_frame, width=80, height=35)
        self.speed_entry.pack()
        self.speed_entry.insert(0, "30")

        # Source
        self._field_label(self.scroll, "Source:")
        self.source_entry = ctk.CTkEntry(self.scroll, width=300, height=35)
        self.source_entry.pack(anchor="w", pady=(5, 15))

        # Description
        self._field_label(self.scroll, "Description:")

        self.desc_text = ctk.CTkTextbox(self.scroll, height=100)

        # Add rich text toolbar for description
        from ui.rich_text_utils import RichTextEditor
        self._desc_rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        desc_toolbar = self._desc_rich_editor.create_toolbar(self.scroll)
        desc_toolbar.pack(fill="x", pady=(5, 5))

        self.desc_text.pack(fill="x", pady=(0, 15))

        # Traits section
        self._add_section_header(self.scroll, "Traits:", "+ Add Trait", self._add_trait)

        # Container for trait entries
        self.traits_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.traits_container.pack(fill="x", pady=(5, 15))

        self._add_save_buttons_left(self.scroll)

    def _add_trait(self, name: str = "", description: str = "", roll_effects=None, spells=None):
        """Add a trait entry."""
        frame, inner, name_entry, desc_entry = self._add_card(
            self.traits_container, "Trait Name:", self._remove_trait, name, description)

        from spell_grants import format_trait_spells
        ctk.CTkLabel(inner, text="Spells this trait gives (optional):", font=ui_font("body")).pack(anchor="w", pady=(10, 0))
        ctk.CTkLabel(inner, text="One per line: Spell, character level, variant. For example \"Misty Step, 3\"; "
                                 "add a variant name when the trait offers a choice. They are always prepared and "
                                 "do not count against the spells a character can prepare.",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary(), anchor="w", justify="left",
                     wraplength=560).pack(fill="x")
        frame._spells_text = ctk.CTkTextbox(inner, height=60)
        frame._spells_text.pack(fill="x", pady=(2, 0))
        frame._spells_text.insert("1.0", format_trait_spells(spells))

        from ui.roll_effects_editor import RollEffectsEditor
        frame._roll_editor = RollEffectsEditor(inner, roll_effects)
        frame._roll_editor.pack(fill="x", pady=(10, 0))

        self._trait_entries.append((name_entry, desc_entry, frame))

    def _remove_trait(self, frame):
        """Remove a trait entry."""
        for i, (name_e, desc_e, f) in enumerate(self._trait_entries):
            if f == frame:
                frame.destroy()
                del self._trait_entries[i]
                break
    
    def _populate_from_lineage(self, lineage: Lineage):
        """Populate fields from existing lineage."""
        self.name_entry.insert(0, lineage.name)
        self.creature_type_entry.delete(0, "end")
        self.creature_type_entry.insert(0, lineage.creature_type)
        self.size_combo.set(lineage.size)
        self.speed_entry.delete(0, "end")
        self.speed_entry.insert(0, str(lineage.speed))
        self.source_entry.insert(0, lineage.source)
        self.desc_text.insert("1.0", lineage.description)
        
        for trait in lineage.traits:
            self._add_trait(trait.name, trait.description, trait.roll_effects, trait.spells)

    _REVIEW_FIELD_LABELS = {
        "name": "Name", "creature_type": "Creature Type", "size": "Size",
        "speed": "Speed", "source": "Source", "description": "Description",
        "traits": "Traits",
    }

    def _apply_review_highlights(self):
        """Add the auto-detect disclaimer banner and outline uncertain fields."""
        banner, warn = add_review_banner(
            self, self.scroll, self._review_fields, self._REVIEW_FIELD_LABELS, self._batch_progress,
            ("Auto-detection is rule-based, not perfect - accuracy drops for "
            "irregularly formatted text. Splitting the description from its "
            "traits is a best guess. Nothing is saved until you click Save."),
            padx=20, wraplength=620)
        widgets = {
            "name": self.name_entry,
            "creature_type": self.creature_type_entry,
            "size": self.size_combo,
            "speed": self.speed_entry,
            "source": self.source_entry,
        }
        outline_fields(widgets, self._review_fields, warn)

        if "traits" in self._review_fields:
            for _name_e, _desc_e, frame in self._trait_entries:
                try:
                    frame.configure(border_color=warn, border_width=2)
                except Exception:
                    pass

    def build_result(self, strict: bool = True) -> Lineage:
        """The lineage the form describes (strict: ValueError if incomplete; otherwise gaps are filled in)."""
        name = self.name_entry.get().strip()
        if not name and strict:
            raise ValueError("Name is required.")

        try:
            speed = int(self.speed_entry.get())
        except ValueError:
            if strict:
                raise ValueError("Speed must be a number.")
            speed = 30
        
        # Gather traits
        from spell_grants import default_lookup, parse_trait_spells
        traits = []
        for name_entry, desc_entry, trait_frame in self._trait_entries:
            trait_name = name_entry.get().strip()
            trait_desc = desc_entry.get("1.0", "end-1c").strip()
            editor = getattr(trait_frame, "_roll_editor", None)
            spells_box = getattr(trait_frame, "_spells_text", None)
            trait_spells = []
            if spells_box is not None:
                trait_spells, problems = parse_trait_spells(spells_box.get("1.0", "end-1c"), default_lookup())
                if problems and strict:
                    raise ValueError(f"Trait spells - {trait_name or 'A trait'}:\n" + "\n".join(problems))
            if trait_name:
                traits.append(LineageTrait(name=trait_name, description=trait_desc,
                                           roll_effects=editor.get() if editor else [], spells=trait_spells))
        
        return Lineage(
            name=name,
            description=self.desc_text.get("1.0", "end-1c").strip(),
            creature_type=self.creature_type_entry.get().strip() or "Humanoid",
            size=self.size_combo.get(),
            speed=speed,
            traits=traits,
            source=self.source_entry.get().strip(),
            is_official=False,
            is_custom=True,
            is_legacy=False
        )

    def _accept(self, lineage):
        if not self.EMBEDDED:
            self.lineage_manager.add_lineage(lineage)
        super()._accept(lineage)

class LineageEditorDialog(LineageEditorBody, DialogWindow):
    """Dialog for creating/editing lineages."""


class LineageEditorPanel(LineageEditorBody, EmbeddedWindow):
    """The LineageEditorDialog form inside the Homebrew Studio."""
