"""
Feats View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of feats with details panel.
"""

from ui.text_import_flow import announce_added, import_from_pasted_text
from ui.versioned_detail import VersionedDetailBase
from ui.window_utils import add_cancel_save, center_on_parent
import customtkinter as ctk
from typography import ui_font
from ui.label_text import LabeledLabel
from tkinter import messagebox
from typing import List, Optional
from feat import Feat, get_feat_manager
from legacy_content import legacy_pair_key
from content_versions import VersionCatalog, display_name
from theme import get_theme_manager
from settings import get_settings_manager
from ui.filter_widgets import SourceFilterMode
from ui.virtual_list import VirtualListPanel
from ui.editor_host import DialogWindow, EditorBody, EmbeddedWindow
from ui.bulk_actions import BulkActionsMixin
from ui.collection_page import CollectionPageMixin
from ui.review_banner import add_review_banner, outline_fields
from ui.extra_fields import show_extra_fields


def _list_name(name: str) -> str:
    """A feat's name in the list: no "(Legacy)" tag, its versions are switched in the detail panel."""
    return display_name(name)


class FeatListPanel(VirtualListPanel):
    """The virtualized, selectable list of feats."""

    TITLE = "Feats"
    NOUN = "feat"
    KEY = staticmethod(legacy_pair_key)   # one entry stands for all the versions of a feat

    def row_text(self, feat: Feat) -> str:
        name = _list_name(feat.name)
        if feat.is_custom:
            name = f"* {name}"
        indicators = []
        if feat.type:
            indicators.append(feat.type)
        if feat.is_spellcasting:
            indicators.append("\u2728")
        return f"{name}  ({', '.join(indicators)})" if indicators else name

    def set_feats(self, feats: List[Feat], reset_scroll: bool = True):
        self.set_items(feats, reset_scroll)

    def get_selected_feat(self) -> Optional[Feat]:
        return self.get_selected()

    def select_feat(self, name: str, version: Optional[Feat] = None) -> bool:
        """Select a feat by name. "Alert (Legacy)" selects the Alert entry; ``version`` is the
        exact version to show in it."""
        return self.select_by_name(name, version)


class FeatDetailPanel(VersionedDetailBase):
    """Panel displaying detailed information about a feat."""
    IMAGE_KIND = "feats"

    CURRENT_ATTR = "_current_feat"
    
    def _create_widgets(self):
        """Create the detail view widgets."""
        self._add_scroll_and_title("Select a feat", 400)
        
        # Type badge
        self.type_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.type_frame.pack(anchor="w", pady=(0, 5))
        
        self.type_badge = ctk.CTkLabel(
            self.type_frame, text="",
            font=ui_font("small"),
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5,
            padx=8, pady=2
        )
        
        # Source info (a drop-down when there are several versions)
        self._add_version_bar()
        
        # Prerequisites
        # height=1: an empty CTkFrame is 200 px high, which left a gap under the Source line of feats
        # without a prerequisite
        self.prereq_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", height=1)
        self.prereq_frame.pack(fill="x", pady=(0, 10))
        
        self.prereq_label = LabeledLabel(
            self.prereq_frame, text="",
            font=ui_font("body"),
            text_color=self.theme.get_current_color('button_danger'),
            wraplength=400,
            justify="left"
        )
        
        # Spellcasting info
        self.spell_frame = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        
        self.spell_info_label = LabeledLabel(
            self.spell_frame, text="",
            font=ui_font("body"),
            wraplength=380,
            justify="left"
        )
        self.spell_info_label.pack(padx=10, pady=8)
        
        # Description container frame
        self.desc_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.desc_frame.pack(fill="x", anchor="w", pady=(10, 0))
        
        # List to track description widgets for cleanup
        self._desc_widgets = []
    
    def _update_colors(self):
        """Update colors after theme change."""
        self.type_badge.configure(fg_color=self.theme.get_current_color('accent_primary'))
        self.spell_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
    
    def _render_description(self, text: str):
        """Render description with bold text support and dynamic resizing."""
        from ui.rich_text_utils import DynamicText
        
        self._clear_description()
        
        if not text:
            return
        
        # Split by paragraphs (double newlines)
        paragraphs = text.split('\n\n')
        
        for para_idx, paragraph in enumerate(paragraphs):
            if not paragraph.strip():
                continue

            # A markdown table block (Adept spell lists, roll tables, ...) is drawn as a real table
            if paragraph.strip().startswith('|'):
                from ui.rich_text_utils import render_description_blocks
                self._desc_widgets.extend(render_description_blocks(
                    self.desc_frame, paragraph, self.theme, bold_pattern=r'\*([^*]+)\*'))
                continue

            # Create a DynamicText for this paragraph with single asterisk bold pattern
            dt = DynamicText(
                self.desc_frame, self.theme,
                bg_color='bg_primary'  # Use theme color key for proper theme switching
            )
            # Use single asterisk pattern for bold (feats use *text* format)
            dt.set_text(paragraph.strip(), bold_pattern=r'\*([^*]+)\*')
            dt.pack(fill="x", expand=True, pady=(2, 2))
            self._desc_widgets.append(dt)
            
            # Add spacing between paragraphs
            if para_idx < len(paragraphs) - 1:
                spacer = ctk.CTkLabel(self.desc_frame, text="", height=5)
                spacer.pack()
                self._desc_widgets.append(spacer)
    
    def _show_item(self, item, versions=None):
        self.show_feat(item, versions)

    def show_feat(self, feat: Optional[Feat], versions: Optional[List[Feat]] = None):
        """Display details for a feat (``versions``: every version offered in the Source drop-down)."""
        self._current_feat = feat
        self._versions = list(versions or [])
        
        if feat is None:
            self.name_label.configure(text="Select a feat")
            self._show_picture(None)
            self.type_badge.pack_forget()
            self.source_label.configure(text="")
            self.prereq_label.pack_forget()
            self.spell_frame.pack_forget()
            self._clear_description()
            show_extra_fields(self, "feats", None)
            return
        
        # Name (with custom indicator)
        name_text = f"* {display_name(feat.name)}" if feat.is_custom else display_name(feat.name)
        self.name_label.configure(text=name_text)
        self._show_picture(display_name(feat.name))
        
        # Type badge
        if feat.type:
            self.type_badge.configure(text=feat.type)
            self.type_badge.pack(anchor="w")
        else:
            self.type_badge.configure(text="General")
            self.type_badge.pack(anchor="w")
        
        # Source
        if feat.source:
            source_text = f"Source: {feat.source}"
            if not feat.is_official:
                source_text += " (Unofficial)"
            if feat.is_legacy:
                source_text += " [Legacy]"
            self.source_label.configure(text=source_text)
        else:
            self.source_label.configure(text="")
        if len(self._versions) > 1:
            self.source_label.set_versions(self._versions, feat)
        
        # Prerequisites
        if feat.has_prereq and feat.prereq:
            self.prereq_label.configure(text=f"Prerequisite: {feat.prereq}")
            self.prereq_label.pack(anchor="w")
        else:
            self.prereq_label.pack_forget()
            self.prereq_frame.configure(height=1)
        
        # Spellcasting info
        if feat.is_spellcasting:
            spell_summary = feat.get_spells_summary()
            if spell_summary:
                self.spell_info_label.configure(text=f"✨ Spellcasting: {spell_summary}")
                self.spell_frame.pack(fill="x", pady=(5, 0))
            else:
                self.spell_frame.pack_forget()
        else:
            self.spell_frame.pack_forget()
        
        # Description - render with bold text support
        self._render_description(feat.description)

        # The fields the user added to Feats (custom_collections.py)
        show_extra_fields(self, "feats", feat.name)


class FeatsView(BulkActionsMixin, CollectionPageMixin, ctk.CTkFrame):
    """Main view for browsing and managing feats."""

    MANAGER_ATTR = "feat_manager"
    PLURAL = "feats"
    
    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        
        self.feat_manager = get_feat_manager()
        self.character_manager = character_manager
        self.settings_manager = get_settings_manager()
        self.on_back = on_back  # Callback for back button
        self._all_feats: List[Feat] = []
        self._catalog = VersionCatalog([])
        self._filtered_feats: List[Feat] = []
        self._compare_mode = False
        self._compare_feat: Optional[Feat] = None
        self._context_feat: Optional[Feat] = None

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
        self._load_feats()
        self.theme.add_listener(self._on_theme_changed)
    
    def _create_filter_bar(self):
        """Create the filter bar at the top."""
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)

        self._add_back_button(filter_bar)
        self._add_search_entry(filter_bar, "Search feats...", 200)

        # Type filter, from the feat manager (auto-populated)
        type_options = ["All Types"] + [t if t else "General" for t in self.feat_manager.get_all_types()]
        self._add_filter_combo(filter_bar, "type", "Type:", "All Types", type_options, 180)

        # Spellcasting filter
        self.spellcasting_var = ctk.BooleanVar(value=False)
        self.spellcasting_check = ctk.CTkCheckBox(
            filter_bar, text="Spellcasting Only",
            variable=self.spellcasting_var,
            command=lambda: self._on_filter_changed(immediate=True)
        )
        self.spellcasting_check.pack(side="left", padx=(0, 15))

        self._add_action_buttons(filter_bar, "+ Add Feat", 100, self._on_add_feat,
                                 self._on_edit_feat, self._on_delete_feat)

        # Second row: source, official content, prerequisite, clear
        filter_bar2 = self._filter_row()
        self._add_source_filter(filter_bar2)
        self._add_content_filter(filter_bar2)
        self._add_filter_combo(filter_bar2, "prereq", "Prerequisite:", "Any",
                               ["Any", "Has Prerequisite", "No Prerequisite"], 110, (0, 20))
        self._add_clear_button(filter_bar2)

    def _create_context_menu(self):
        """Create the right-click context menu for feats."""
        self._build_context_menu([
            ("Add to Character", self._context_add_to_character),
            ("View and Compare", self._context_view_compare),
        ])

    def _create_panes(self):
        self._create_panes_with_container(
            FeatListPanel, FeatDetailPanel, self._on_feat_selected, self._on_feat_right_click)

    def _create_compare_panel(self):
        """Create the compare feat panel (hidden initially)."""
        # Container frame that will replace the feat list when comparing
        self.compare_container = ctk.CTkFrame(
            self.left_container, corner_radius=10,
            fg_color=self.theme.get_current_color('bg_secondary'))
        
        # Header with close button
        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text="Compare Feat",
            font=ui_font("subheading", bold=True)
        ).pack(side="left")
        
        close_btn = ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color=self.theme.get_current_color('button_danger') if hasattr(self.theme, 'get_current_color') else "#c0392b",
            hover_color=self.theme.get_current_color('button_danger_hover') if hasattr(self.theme, 'get_current_color') else "#a93226",
            command=self._close_compare_panel
        )
        close_btn.pack(side="right")
        
        # The detail panel for comparing (no color highlights for feats)
        self.compare_detail = FeatDetailPanel(self.compare_container)
        self.compare_detail.pack(fill="both", expand=True)
    
    def _on_feat_right_click(self, feat: Feat, x: int, y: int):
        """Handle right-click on a feat in the list."""
        self._context_feat = feat
        try:
            self.context_menu.tk_popup(x, y)
        finally:
            self.context_menu.grab_release()
    
    def _context_add_to_character(self):
        """Context menu: Add feat to a character."""
        if not self._context_feat:
            return
        character = self._pick_character(f"Add '{self._context_feat.name}' to:")
        if not character:
            return

        # Check if feat is already on character
        if self._context_feat.name in character.feats:
            messagebox.showinfo("Already Added",
                                f"'{self._context_feat.name}' is already on {character.name}'s feat list.")
            return

        # Add the feat
        character.feats.append(self._context_feat.name)
        self.character_manager.save_characters()
        messagebox.showinfo("Success", f"Added '{self._context_feat.name}' to {character.name}'s feats!")
    
    def _context_view_compare(self):
        """Context menu: View and compare feat."""
        if not self._context_feat:
            return
        
        # Check if the primary detail panel has a feat
        primary_feat = self.detail_panel._current_feat if hasattr(self.detail_panel, '_current_feat') else None
        
        if primary_feat is None:
            # No feat in primary panel - select it there instead
            self.list_panel.select_feat(self._context_feat.name)
        else:
            # Show compare panel
            self._show_compare_panel(self._context_feat)
    
    def _show_compare_panel(self, feat: Feat):
        """Show the compare panel with the given feat."""
        self._compare_mode = True
        self._compare_feat = feat
        
        # Hide feat list, show compare panel
        self.list_panel.pack_forget()
        self.compare_container.pack(fill="both", expand=True)
        
        # Set the feat in compare panel (no color highlighting for feats)
        self.compare_detail.show_feat(feat)
    
    def _close_compare_panel(self):
        """Close the compare panel and return to feat list."""
        self._compare_mode = False
        self._compare_feat = None
        
        # Hide compare panel, show feat list
        self.compare_container.pack_forget()
        self.list_panel.pack(fill="both", expand=True)
    
    BULK_ACTIONS = ("add", "source")
    BULK_NOUN, BULK_PLURAL = "feat", "feats"

    def _bulk_fetch(self, name: str):
        return self.feat_manager.get_feat(name)

    def _bulk_store(self, entries: list) -> int:
        with self.feat_manager.batch():
            return sum(bool(self.feat_manager.update_feat(e.name, e)) for e in entries)

    def _bulk_reload(self):
        self._load_feats()

    def _bulk_all_sources(self) -> List[str]:
        return self.feat_manager.get_all_sources()

    def _bulk_give(self, character, entries: list) -> str:
        new = [f.name for f in entries if f.name not in character.feats]
        character.feats.extend(new)
        if new:
            self.character_manager.save_characters()
        already = len(entries) - len(new)
        return (f"Added {self._bulk_count_text(len(new))} to {character.name}'s feats."
                + (f"\n{already} {'was' if already == 1 else 'were'} already there." if already else ""))

    def _load_feats(self):
        """Load feats from the manager."""
        self._all_feats = sorted(self.feat_manager.feats, key=lambda f: f.name.lower())
        self._catalog = VersionCatalog(self._all_feats)
        # Refresh type dropdown with all available types
        all_types = self.feat_manager.get_all_types()
        type_options = ["All Types"] + [t if t else "General" for t in all_types]
        self.type_combo.configure(values=type_options)
        self._on_filter_changed(immediate=True)
    
    def _clear_filters(self):
        """Reset every filter to its default value."""
        self.search_var.set("")
        self.titles_var.set(False)
        self.type_var.set("All Types")
        self.spellcasting_var.set(False)
        self.official_var.set("Any Content")
        self.prereq_var.set("Any")
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._update_source_label()
        self._on_filter_changed(immediate=True)

    def _apply_filters(self):
        """Apply current filters to the feat list."""
        search_text = self.search_var.get().lower()
        type_filter = self.type_var.get()
        spellcasting_only = self.spellcasting_var.get()
        official_filter = self.official_var.get()
        prereq_filter = self.prereq_var.get()
        legacy_filter = self.settings_manager.settings.legacy_content_filter

        filtered = []
        for feat in self._all_feats:
            # Search filter
            if not self._passes_search(search_text, feat.name, lambda: [feat.plain_description()]):
                continue

            # Type filter
            if type_filter != "All Types":
                feat_type = feat.type if feat.type else "General"
                if feat_type != type_filter:
                    continue

            # Spellcasting filter
            if spellcasting_only and not feat.is_spellcasting:
                continue

            # Source filter
            if not self._passes_source_filter(feat.source):
                continue

            # Official content filter
            if not self._passes_official_filter(feat.is_official, official_filter):
                continue

            # Prerequisite filter
            if prereq_filter == "Has Prerequisite" and not feat.has_prereq:
                continue
            if prereq_filter == "No Prerequisite" and feat.has_prereq:
                continue

            filtered.append(feat)
        
        # One entry per feat: its versions (2024, 2014) are switched in the detail panel's Source
        # drop-down; the Legacy content setting decides which are offered
        filtered = self._catalog.collapse(filtered, legacy_filter)

        self._filtered_feats = filtered
        self.list_panel.set_feats(filtered)
    
    def _on_feat_selected(self, feat: Optional[Feat]):
        """Handle feat selection."""
        setting = self.settings_manager.settings.legacy_content_filter
        self.detail_panel.show_feat(feat, self._catalog.options(feat, setting) if feat else None)
        
        # Enable/disable edit/delete based on selection and custom status
        if feat:
            self.edit_btn.configure(state="normal" if feat.is_custom else "disabled")
            self.delete_btn.configure(state="normal" if feat.is_custom else "disabled")
        else:
            self.edit_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")
    
    def _on_add_feat(self):
        """Open dialog to add a new feat (manual entry or auto-detect from text)."""
        from ui.feat_text_import import AddFeatSourceDialog

        source_dialog = AddFeatSourceDialog(self)
        self.wait_window(source_dialog)
        if source_dialog.result is None:
            return
        if source_dialog.result == "auto":
            self._on_add_feat_from_text()
            return

        from ui.studio_launch import open_in_studio
        if open_in_studio(self, "feats"):
            return

        dialog = FeatEditorDialog(self, "Add Feat")
        self.wait_window(dialog)

        if dialog.result:
            dialog.result.is_custom = True
            if self.feat_manager.add_feat(dialog.result):
                self._load_feats()
                messagebox.showinfo("Success", f"Feat '{dialog.result.name}' added!")
            else:
                messagebox.showerror("Error", f"A feat named '{dialog.result.name}' already exists.")

    def _on_add_feat_from_text(self):
        """Paste a block of text, auto-detect feat fields, and review each draft."""
        from ui.feat_text_import import FeatTextImportDialog

        def load_converter():
            from text_import.feat_parser import to_feat
            return to_feat

        def mark_custom(feat):
            feat.is_custom = True

        added = import_from_pasted_text(
            self, import_cls=FeatTextImportDialog, load_converter=load_converter, noun="feat",
            noun_phrase="a feat", dialog_parent=self,
            make_editor=lambda draft, review, progress: FeatEditorDialog(
                self, f"Review Feat: {draft.name or 'Untitled'}",
                prefill_feat=draft, review_fields=review, batch_progress=progress),
            add=self.feat_manager.add_feat, prepare=mark_custom)

        if added:
            self._load_feats()
            if len(added) > 1:
                announce_added(added, "feats")
            else:
                messagebox.showinfo("Success", f"Feat '{added[0]}' added!")

    def _on_edit_feat(self):
        """Edit the selected feat."""
        feat = self.list_panel.get_selected_feat()
        if not feat or not feat.is_custom:
            return
        
        dialog = FeatEditorDialog(self, "Edit Feat", feat)
        self.wait_window(dialog)
        
        if dialog.result:
            dialog.result.is_custom = True
            if self.feat_manager.update_feat(feat.name, dialog.result):
                self._load_feats()
                messagebox.showinfo("Success", f"Feat '{dialog.result.name}' updated!")
    
    def _on_delete_feat(self):
        """Delete the selected feat."""
        feat = self.list_panel.get_selected_feat()
        if not feat or not feat.is_custom:
            return
        
        if messagebox.askyesno("Confirm Delete", 
                               f"Are you sure you want to delete '{feat.name}'?"):
            if self.feat_manager.delete_feat(feat.name):
                self._load_feats()
                self.detail_panel.show_feat(None)
                messagebox.showinfo("Success", f"Feat '{feat.name}' deleted!")
    
    def refresh(self):
        """Refresh the view."""
        self._load_feats()
    
    def select_feat(self, name: str) -> bool:
        """Select a feat by name. Returns True if found."""
        return self.list_panel.select_feat(name, self._catalog.find(name))


class FeatEditorBody(EditorBody):
    """Dialog for adding/editing a feat. (the form; see ui/editor_host.py)"""
    
    def __init__(self, parent, title: str, feat: Optional[Feat] = None,
                 prefill_feat: Optional[Feat] = None, review_fields: Optional[List[str]] = None,
                 batch_progress: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x750")
        self.transient(parent)
        self.grab_set()

        self.theme = get_theme_manager()
        self.result: Optional[Feat] = None
        self._editing_feat = feat
        # Auto-detect pre-fill: populate the form from parsed text but keep this
        # a brand-new feat, and mark fields for the reviewer to double-check.
        self._review_fields = set(review_fields or [])
        self._batch_progress = batch_progress

        self._create_widgets()

        if feat:
            self._populate_from_feat(feat)
        elif prefill_feat:
            self._populate_from_feat(prefill_feat)
            self._apply_review_highlights()

        # Center dialog
        center_on_parent(self, parent)
    
    def _create_widgets(self):
        """Create the editor widgets."""
        from ui.rich_text_utils import RichTextEditor
        
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        self._scroll = scroll

        self.feat_manager = get_feat_manager()
        
        # Name
        ctk.CTkLabel(scroll, text="Name:", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(scroll, width=400)
        self.name_entry.pack(fill="x", pady=(0, 10))
        
        # Type (editable combobox for custom types)
        ctk.CTkLabel(scroll, text="Type:", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        ctk.CTkLabel(scroll, text="Select or type a custom type (blank = General)",
                     font=ui_font("small"), text_color="gray").pack(anchor="w")
        # Get all types from feat manager (auto-populated)
        all_types = self.feat_manager.get_all_types()
        type_options = [t if t else "General" for t in all_types]
        self.type_var = ctk.StringVar(value="General")
        self.type_combo = ctk.CTkComboBox(
            scroll, width=200, values=type_options,
            variable=self.type_var  # Removed state="readonly" to allow custom types
        )
        self.type_combo.pack(anchor="w", pady=(0, 10))
        
        # Source
        ctk.CTkLabel(scroll, text="Source:", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.source_entry = ctk.CTkEntry(scroll, width=400, placeholder_text="e.g., Homebrew, Custom Campaign")
        self.source_entry.pack(fill="x", pady=(0, 10))
        
        # Prerequisites
        self.prereq_var = ctk.BooleanVar(value=False)
        self.prereq_check = ctk.CTkCheckBox(
            scroll, text="Has Prerequisites",
            variable=self.prereq_var,
            command=self._toggle_prereq
        )
        self.prereq_check.pack(anchor="w", pady=(0, 5))
        
        self.prereq_entry = ctk.CTkEntry(scroll, width=400, placeholder_text="Prerequisite description")
        self.prereq_entry.pack(fill="x", pady=(0, 10))
        self.prereq_entry.configure(state="disabled")
        
        # Spellcasting
        self.spell_var = ctk.BooleanVar(value=False)
        self.spell_check = ctk.CTkCheckBox(
            scroll, text="Grants Spellcasting",
            variable=self.spell_var,
            command=self._toggle_spellcasting
        )
        self.spell_check.pack(anchor="w", pady=(0, 5))
        
        # Spellcasting frame (hidden by default)
        self.spell_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        
        ctk.CTkLabel(self.spell_frame, text="Spell Lists (comma-separated classes):").pack(anchor="w")
        self.spell_lists_entry = ctk.CTkEntry(self.spell_frame, width=400, 
                                               placeholder_text="e.g., Wizard, Cleric, Druid")
        self.spell_lists_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(self.spell_frame, text="Spells Granted (format: level:count, comma-separated):").pack(anchor="w")
        self.spells_num_entry = ctk.CTkEntry(self.spell_frame, width=400,
                                              placeholder_text="e.g., 0:2, 1:1 for 2 cantrips and 1 first-level")
        self.spells_num_entry.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(self.spell_frame, text="Set Spells (specific spells, comma-separated):").pack(anchor="w")
        self.set_spells_entry = ctk.CTkEntry(self.spell_frame, width=400,
                                              placeholder_text="e.g., Misty Step, Shield")
        self.set_spells_entry.pack(fill="x", pady=(0, 10))
        
        # Description with rich text toolbar
        ctk.CTkLabel(scroll, text="Description:", font=ui_font("subheading", 13, bold=True)).pack(anchor="w", pady=(10, 0))
        
        self.desc_text = ctk.CTkTextbox(scroll, height=200)
        self._rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(scroll)
        toolbar.pack(fill="x", pady=(5, 5))
        
        self.desc_text.pack(fill="x", pady=(0, 10))

        from ui.roll_effects_editor import RollEffectsEditor
        self.roll_editor = RollEffectsEditor(scroll)
        self.roll_editor.pack(fill="x", pady=(0, 10))

        # Buttons
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        
        add_cancel_save(btn_frame, self.theme, self._finish, self._save, outlined=True)
    
    def _toggle_prereq(self):
        """Toggle prerequisite entry state."""
        if self.prereq_var.get():
            self.prereq_entry.configure(state="normal")
        else:
            self.prereq_entry.configure(state="disabled")
    
    def _toggle_spellcasting(self):
        """Toggle spellcasting fields visibility."""
        if self.spell_var.get():
            self.spell_frame.pack(fill="x", pady=(0, 10), after=self.spell_check)
        else:
            self.spell_frame.pack_forget()
    
    def _populate_from_feat(self, feat: Feat):
        """Populate fields from existing feat."""
        self.name_entry.insert(0, feat.name)
        self.type_var.set(feat.type if feat.type else "General")
        
        # Source
        if feat.source:
            self.source_entry.insert(0, feat.source)
        
        self.prereq_var.set(feat.has_prereq)
        if feat.has_prereq:
            self.prereq_entry.configure(state="normal")
            self.prereq_entry.insert(0, feat.prereq)
        
        self.spell_var.set(feat.is_spellcasting)
        if feat.is_spellcasting:
            self._toggle_spellcasting()
            self.spell_lists_entry.insert(0, ", ".join(feat.spell_lists))
            spells_num_str = ", ".join(f"{k}:{v}" for k, v in feat.spells_num.items())
            self.spells_num_entry.insert(0, spells_num_str)
            self.set_spells_entry.insert(0, ", ".join(feat.set_spells))
        
        self.desc_text.insert("1.0", feat.description)
        self.roll_editor.set(feat.roll_effects)

    _REVIEW_FIELD_LABELS = {
        "name": "Name", "type": "Type", "prereq": "Prerequisite",
        "has_prereq": "Has Prerequisites", "source": "Source",
        "description": "Description", "is_spellcasting": "Grants Spellcasting",
        "spell_lists": "Spell Lists", "spells_num": "Spells Granted",
        "set_spells": "Set Spells",
    }

    def _apply_review_highlights(self):
        """Add the auto-detect disclaimer banner and outline uncertain fields."""
        banner, warn = add_review_banner(
            self, self._scroll, self._review_fields, self._REVIEW_FIELD_LABELS, self._batch_progress,
            ("Auto-detection is rule-based, not perfect - accuracy drops for "
            "irregularly formatted text, and feats vary a lot. Spellcasting "
            "fields especially are a best guess. Nothing is saved until you "
            "click Save."),
            padx=20, wraplength=520)
        widgets = {
            "name": self.name_entry,
            "type": self.type_combo,
            "prereq": self.prereq_entry,
            "source": self.source_entry,
            "spell_lists": self.spell_lists_entry,
            "spells_num": self.spells_num_entry,
            "set_spells": self.set_spells_entry,
        }
        outline_fields(widgets, self._review_fields, warn)

    def build_result(self, strict: bool = True) -> Feat:
        """The feat the form describes (strict: ValueError if incomplete; otherwise gaps are filled in)."""
        name = self.name_entry.get().strip()
        if not name and strict:
            raise ValueError("Feat name is required.")
        
        feat_type = self.type_var.get()
        if feat_type == "General":
            feat_type = ""
        
        has_prereq = self.prereq_var.get()
        prereq = self.prereq_entry.get().strip() if has_prereq else ""
        
        is_spellcasting = self.spell_var.get()
        spell_lists = []
        spells_num = {}
        set_spells = []
        
        if is_spellcasting:
            # Parse spell lists
            spell_lists_text = self.spell_lists_entry.get().strip()
            if spell_lists_text:
                spell_lists = [s.strip() for s in spell_lists_text.split(",") if s.strip()]
            
            # Parse spells_num
            spells_num_text = self.spells_num_entry.get().strip()
            if spells_num_text:
                for part in spells_num_text.split(","):
                    if ":" in part:
                        try:
                            level, count = part.strip().split(":")
                            spells_num[int(level)] = int(count)
                        except ValueError:
                            pass
            
            # Parse set spells
            set_spells_text = self.set_spells_entry.get().strip()
            if set_spells_text:
                set_spells = [s.strip() for s in set_spells_text.split(",") if s.strip()]
        
        description = self.desc_text.get("1.0", "end-1c").strip()
        
        # Get source (custom feats are always unofficial and non-legacy)
        source = self.source_entry.get().strip()
        
        return Feat(
            name=name,
            type=feat_type,
            is_spellcasting=is_spellcasting,
            spell_lists=spell_lists,
            spells_num=spells_num,
            has_prereq=has_prereq,
            prereq=prereq,
            set_spells=set_spells,
            description=description,
            source=source,
            is_official=False,
            is_custom=True,
            is_legacy=False,
            roll_effects=self.roll_editor.get()
        )

class FeatEditorDialog(FeatEditorBody, DialogWindow):
    """Dialog for adding/editing a feat."""


class FeatEditorPanel(FeatEditorBody, EmbeddedWindow):
    """The FeatEditorDialog form inside the Homebrew Studio."""


