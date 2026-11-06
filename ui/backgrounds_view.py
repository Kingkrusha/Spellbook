"""
Backgrounds View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of backgrounds with details panel.
"""

import customtkinter as ctk
from typography import ui_font
from ui.versioned_detail import VersionedDetailBase
from tkinter import messagebox
from typing import List, Optional
from background import Background, BackgroundFeature, BackgroundManager, get_background_manager
from theme import get_theme_manager
from ui.rich_text_utils import follow_width
from settings import get_settings_manager
from legacy_content import legacy_pair_key
from content_versions import VersionCatalog, display_name
from ui.filter_widgets import SourceFilterMode
from ui.virtual_list import VirtualListPanel
from ui.editor_host import DialogWindow, EditorBody, EmbeddedWindow
from ui.bulk_actions import BulkActionsMixin
from ui.collection_page import CollectionPageMixin
from ui.extra_fields import show_extra_fields


def _list_name(name: str) -> str:
    """A background's name in the list: no "(Legacy)" tag, its versions are switched in the detail panel."""
    return display_name(name)


class BackgroundListPanel(VirtualListPanel):
    """The virtualized, selectable list of backgrounds."""

    TITLE = "Backgrounds"
    NOUN = "background"
    KEY = staticmethod(legacy_pair_key)   # one entry stands for all the versions of a background

    def row_text(self, background: Background) -> str:
        name = _list_name(background.name)
        return f"* {name}" if background.is_custom else name

    def set_backgrounds(self, backgrounds: List[Background], reset_scroll: bool = True,
                        preserve_selection: Optional[str] = None):
        # Only an explicitly preserved entry stays selected, and it is shown again in the detail panel
        self.set_items(backgrounds, reset_scroll, keep=preserve_selection, keep_current=False, notify=True)

    def get_selected_background(self) -> Optional[Background]:
        return self.get_selected()

    def select_background(self, name: str, version: Optional[Background] = None) -> bool:
        """Select a background by name; ``version`` is the exact version to show in its entry."""
        return self.select_by_name(name, version)


class BackgroundDetailPanel(VersionedDetailBase):
    """Panel displaying detailed information about a background."""
    IMAGE_KIND = "backgrounds"

    CURRENT_ATTR = "_current_background"
    
    def _create_widgets(self):
        """Create the detail view widgets."""
        self._add_scroll_and_title("Select a background", 800)

        # Source info (a drop-down when there are several versions)
        self._add_version_bar()
        
        # Stats frame (ability scores, skills, etc.)
        self.stats_frame = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        
        self.stats_inner = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
        self.stats_inner.pack(fill="x", padx=10, pady=8)
        
        # Create stats rows with inline bold labels
        # Ability Scores row
        self.ability_row = ctk.CTkFrame(self.stats_inner, fg_color="transparent")
        self.ability_row.pack(fill="x", anchor="w", pady=1)
        self.ability_key = ctk.CTkLabel(
            self.ability_row, text="Ability Scores: ",
            font=ui_font("body", bold=True),
            text_color=get_theme_manager().get_current_color('text_label'),
            anchor="w"
        )
        self.ability_key.pack(side="left")
        self.ability_value = ctk.CTkLabel(
            self.ability_row, text="",
            font=ui_font("body"),
            anchor="w", justify="left"
        )
        self.ability_value.pack(side="left", fill="x")
        follow_width(self.ability_row, self.ability_value, margin=200)  # wrap to what is left of the row
        
        # Skills row
        self.skills_row = ctk.CTkFrame(self.stats_inner, fg_color="transparent")
        self.skills_row.pack(fill="x", anchor="w", pady=1)
        self.skills_key = ctk.CTkLabel(
            self.skills_row, text="Skills: ",
            font=ui_font("body", bold=True),
            text_color=get_theme_manager().get_current_color('text_label'),
            anchor="w"
        )
        self.skills_key.pack(side="left")
        self.skills_value = ctk.CTkLabel(
            self.skills_row, text="",
            font=ui_font("body"),
            anchor="w", justify="left"
        )
        self.skills_value.pack(side="left", fill="x")
        follow_width(self.skills_row, self.skills_value, margin=200)  # wrap to what is left of the row
        
        # Tool Proficiencies row
        self.prof_row = ctk.CTkFrame(self.stats_inner, fg_color="transparent")
        self.prof_row.pack(fill="x", anchor="w", pady=1)
        self.prof_key = ctk.CTkLabel(
            self.prof_row, text="Tool Proficiencies: ",
            font=ui_font("body", bold=True),
            text_color=get_theme_manager().get_current_color('text_label'),
            anchor="w"
        )
        self.prof_key.pack(side="left")
        self.prof_value = ctk.CTkLabel(
            self.prof_row, text="",
            font=ui_font("body"),
            anchor="w", justify="left"
        )
        self.prof_value.pack(side="left", fill="x")
        follow_width(self.prof_row, self.prof_value, margin=200)  # wrap to what is left of the row
        
        # Feat frame - will contain clickable feat buttons
        self.feat_frame = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        self.feat_inner = ctk.CTkFrame(self.feat_frame, fg_color="transparent")
        self.feat_inner.pack(fill="x", padx=10, pady=8)
        self._feat_widgets = []
        
        # Equipment
        self.equipment_header = ctk.CTkLabel(
            self.scroll_frame, text="Equipment",
            font=ui_font("subheading", bold=True)
        )
        # Equipment can contain [[equipment:Name]] links, so it is rendered by
        # the link-aware DynamicText (built in _render_equipment) rather than a
        # plain label that would show the raw markup.
        self.equipment_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._equipment_text_widget = None
        
        # Description
        self.desc_header = ctk.CTkLabel(
            self.scroll_frame, text="Description",
            font=ui_font("subheading", bold=True)
        )
        
        # Description container for rich text rendering
        self.description_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._desc_widgets = []
        
        # Features section
        self.features_header = ctk.CTkLabel(
            self.scroll_frame, text="Features",
            font=ui_font("subheading", bold=True)
        )
        
        # Container for feature widgets
        self.features_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._feature_widgets = []
    
    def _update_colors(self):
        """Update colors after theme change."""
        self.stats_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
        self.feat_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
    
    def _clear_features(self):
        """Clear all feature widgets."""
        for widget in self._feature_widgets:
            widget.destroy()
        self._feature_widgets = []
    
    def _clear_feats(self):
        """Clear feat widgets."""
        for widget in self._feat_widgets:
            widget.destroy()
        self._feat_widgets = []
    
    def _show_feat_popup(self, feat_name: str):
        """Show a popup with the feat description."""
        from feat import get_feat_manager
        
        feat_manager = get_feat_manager()
        feat = feat_manager.get_feat(feat_name)
        
        if not feat:
            # Try partial match (e.g., "Magic Initiate (Cleric)" -> search for "Magic Initiate")
            base_name = feat_name.split('(')[0].strip()
            feat = feat_manager.get_feat(base_name)
        
        if feat:
            # Create popup window
            popup = ctk.CTkToplevel(self.winfo_toplevel())
            popup.title(feat.name)
            popup.geometry("500x400")
            popup.transient(self.winfo_toplevel())
            
            # Center on parent
            popup.update_idletasks()
            x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() - 500) // 2
            y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() - 400) // 2
            popup.geometry(f"+{x}+{y}")
            
            # Content
            content = ctk.CTkScrollableFrame(popup, fg_color="transparent")
            content.pack(fill="both", expand=True, padx=20, pady=20)
            
            ctk.CTkLabel(
                content, text=feat.name,
                font=ui_font("heading", 20, bold=True)
            ).pack(anchor="w", pady=(0, 10))
            
            if feat.type:
                ctk.CTkLabel(
                    content, text=f"Type: {feat.type}",
                    font=ui_font("body"),
                    text_color=self.theme.get_text_secondary()
                ).pack(anchor="w")
            
            if feat.has_prereq and feat.prereq:
                ctk.CTkLabel(
                    content, text=f"Prerequisite: {feat.prereq}",
                    font=ui_font("body"),
                    text_color=self.theme.get_current_color('button_danger')
                ).pack(anchor="w", pady=(5, 0))
            
            if feat.description:
                # Use rich text renderer for proper bold formatting
                # Feats use single asterisk *text* for bold
                desc_container = ctk.CTkFrame(content, fg_color="transparent")
                desc_container.pack(fill="x", anchor="w", pady=(10, 0))
                renderer = self._get_renderer()
                renderer.render_formatted_text(
                    desc_container, feat.description,
                    on_spell_click=lambda s: renderer.show_spell_popup(popup, s),
                    wraplength=450,
                    bold_pattern=r'\*([^*]+)\*'
                )
            
            # Close button
            ctk.CTkButton(
                popup, text="Close",
                width=100,
                command=popup.destroy
            ).pack(pady=10)
            
            popup.grab_set()
        else:
            messagebox.showinfo(
                "Feat Not Found",
                f"Could not find feat: {feat_name}",
                parent=self.winfo_toplevel()
            )
    
    def _render_feature(self, feature: BackgroundFeature):
        """Render a single feature."""
        # Feature frame
        feature_frame = ctk.CTkFrame(
            self.features_container,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        feature_frame.pack(fill="x", pady=2)
        self._feature_widgets.append(feature_frame)
        
        inner = ctk.CTkFrame(feature_frame, fg_color="transparent")
        inner.pack(fill="x", expand=True, padx=10, pady=6)
        
        # Feature name
        name_label = ctk.CTkLabel(
            inner, text=feature.name,
            font=ui_font("subheading", 13, bold=True),
            anchor="w"
        )
        name_label.pack(fill="x", anchor="w")
        
        # Feature description using renderer for table and spell link support
        if feature.description:
            desc_container = ctk.CTkFrame(inner, fg_color="transparent")
            desc_container.pack(fill="x", expand=True, pady=(5, 0))
            
            renderer = self._get_renderer()
            renderer.render_formatted_text(
                desc_container, feature.description,
                on_spell_click=lambda s: renderer.show_spell_popup(desc_container, s),
                wraplength=500
            )
    
    def _render_equipment(self, text: str):
        """Show the equipment list, with any [[...]] links clickable."""
        from ui.rich_text_utils import DynamicText

        if self._equipment_text_widget is not None:
            self._equipment_text_widget.destroy()
        dt = DynamicText(self.equipment_container, self.theme, bg_color='bg_primary')
        dt.set_text(text)
        dt.pack(fill="x", expand=True)
        self._equipment_text_widget = dt

    def _render_description(self, text: str):
        """Render description with dynamic resizing and bold text support."""
        from ui.rich_text_utils import DynamicText
        
        self._clear_description()
        
        if not text:
            return
        
        from ui.rich_text_utils import render_description_blocks

        # Paragraphs and tables; a lone *text* is bold in this collection's text
        self._desc_widgets.extend(render_description_blocks(
            self.description_container, text, self.theme, bold_pattern=r'\*([^*]+)\*', pady=(3, 3)))
    
    def _show_item(self, item, versions=None):
        self.show_background(item, versions)

    def show_background(self, background: Optional[Background], versions: Optional[List[Background]] = None):
        """Display a background, then the fields the user added to Backgrounds (custom_collections.py)."""
        self._show_background(background, versions)
        show_extra_fields(self, "backgrounds", background.name if background else None)

    def _show_background(self, background: Optional[Background], versions: Optional[List[Background]] = None):
        """Display details for a background (``versions``: every version offered in the Source drop-down)."""
        self._current_background = background
        self._versions = list(versions or [])
        
        if background is None:
            self.name_label.configure(text="Select a background")
            self._show_picture(None)
            self.source_label.configure(text="")
            self.stats_frame.pack_forget()
            self.feat_frame.pack_forget()
            self._clear_feats()
            self.equipment_header.pack_forget()
            self.equipment_container.pack_forget()
            self.desc_header.pack_forget()
            self._clear_description()
            self.description_container.pack_forget()
            self.features_header.pack_forget()
            self.features_container.pack_forget()
            self._clear_features()
            return
        
        # Name (with custom indicator)
        name_text = f"* {display_name(background.name)}" if background.is_custom else display_name(background.name)
        self.name_label.configure(text=name_text)
        self._show_picture(display_name(background.name))
        
        # Source
        if background.source:
            source_text = f"Source: {background.source}"
            if not background.is_official:
                source_text += " (Unofficial)"
            if background.is_legacy:
                source_text += " [Legacy]"
            self.source_label.configure(text=source_text)
        else:
            self.source_label.configure(text="")
        if len(self._versions) > 1:
            self.source_label.set_versions(self._versions, background)
        
        # Stats (ability scores, skills, proficiencies)
        if background.ability_scores:
            self.ability_value.configure(text=background.get_ability_scores_summary())
            self.ability_row.pack(fill="x", anchor="w", pady=1)
        else:
            self.ability_value.configure(text="")
            self.ability_row.pack_forget()
        
        if background.skills:
            self.skills_value.configure(text=background.get_skills_summary())
            self.skills_row.pack(fill="x", anchor="w", pady=1)
        else:
            self.skills_value.configure(text="")
            self.skills_row.pack_forget()
        
        if background.other_proficiencies:
            prof_text = ", ".join(background.other_proficiencies)
            self.prof_value.configure(text=prof_text)
            self.prof_row.pack(fill="x", anchor="w", pady=1)
        else:
            self.prof_value.configure(text="")
            self.prof_row.pack_forget()
        
        self.stats_frame.pack(fill="x", pady=(0, 15))
        
        # Feats (clickable buttons)
        self._clear_feats()
        if background.feats:
            feat_label = ctk.CTkLabel(
                self.feat_inner, text="Feat:",
                font=ui_font("body", bold=True),
                text_color=get_theme_manager().get_current_color('text_label'),
                anchor="w"
            )
            feat_label.pack(side="left", padx=(0, 10))
            self._feat_widgets.append(feat_label)
            
            for i, feat_name in enumerate(background.feats):
                if i > 0:
                    # Add "or" between multiple feats
                    or_label = ctk.CTkLabel(
                        self.feat_inner, text="or",
                        font=ui_font("body", italic=True),
                        text_color=self.theme.get_text_secondary()
                    )
                    or_label.pack(side="left", padx=5)
                    self._feat_widgets.append(or_label)
                
                feat_btn = ctk.CTkButton(
                    self.feat_inner, text=feat_name,
                    font=ui_font("body"),
                    fg_color=self.theme.get_current_color('accent_primary'),
                    hover_color=self.theme.get_current_color('accent_hover'),
                    height=28,
                    command=lambda fn=feat_name: self._show_feat_popup(fn)
                )
                feat_btn.pack(side="left", padx=2)
                self._feat_widgets.append(feat_btn)
            
            self.feat_frame.pack(fill="x", pady=(0, 15))
        else:
            self.feat_frame.pack_forget()
        
        # Equipment
        if background.equipment:
            self.equipment_header.pack(anchor="w", pady=(10, 5))
            self._render_equipment(background.equipment)
            self.equipment_container.pack(fill="x", anchor="w", pady=(0, 10))
        else:
            self.equipment_header.pack_forget()
            self.equipment_container.pack_forget()
        
        # Description
        if background.description:
            self.desc_header.pack(anchor="w", pady=(10, 5))
            self._render_description(background.description)
            self.description_container.pack(fill="x", pady=(0, 10))
        else:
            self.desc_header.pack_forget()
            self._clear_description()
            self.description_container.pack_forget()
        
        # Features
        self._clear_features()
        if background.features:
            self.features_header.pack(anchor="w", pady=(10, 5))
            self.features_container.pack(fill="x")
            for feature in background.features:
                self._render_feature(feature)
        else:
            self.features_header.pack_forget()
            self.features_container.pack_forget()


class BackgroundsView(BulkActionsMixin, CollectionPageMixin, ctk.CTkFrame):
    """Main view for browsing and managing backgrounds."""

    MANAGER_ATTR = "background_manager"
    PLURAL = "backgrounds"
    
    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        
        self.background_manager = get_background_manager()
        self.character_manager = character_manager
        self.settings_manager = get_settings_manager()
        self.on_back = on_back
        self._all_backgrounds: List[Background] = []
        self._catalog = VersionCatalog([])
        self._filtered_backgrounds: List[Background] = []
        self._compare_mode = False
        self._compare_background: Optional[Background] = None
        self._context_background: Optional[Background] = None

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
        self._load_backgrounds()
        self.theme.add_listener(self._on_theme_changed)
    
    def _create_filter_bar(self):
        """Create the filter bar at the top."""
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)

        self._add_back_button(filter_bar)
        self._add_search_entry(filter_bar, "Search backgrounds...", 200)
        self._add_source_filter(filter_bar, end_padx=(0, 15))
        self._add_action_buttons(filter_bar, "+ Add Background", 140, self._on_add_background,
                                 self._on_edit_background, self._on_delete_background)

        # Second row: official content, skill, clear
        filter_bar2 = self._filter_row()
        self._add_content_filter(filter_bar2)
        self._add_filter_combo(filter_bar2, "skill", "Grants Skill:", "All Skills", ["All Skills"], 160, (0, 20))
        self._add_clear_button(filter_bar2)

    def _create_context_menu(self):
        """Create the right-click context menu for backgrounds."""
        self._build_context_menu([
            ("Set as Character Background", self._context_set_background),
            ("Compare", self._context_compare),
        ])

    def _create_panes(self):
        self._create_panes_with_container(
            BackgroundListPanel, BackgroundDetailPanel, self._on_background_selected,
            self._on_background_right_click)

    def _create_compare_panel(self):
        """Create the compare background panel (hidden initially)."""
        self._build_compare_panel("Compare Backgrounds", BackgroundDetailPanel, self._close_compare)

    BULK_ACTIONS = ("source",)
    BULK_NOUN, BULK_PLURAL = "background", "backgrounds"

    def _bulk_fetch(self, name: str):
        return self.background_manager.get_background(name)

    def _bulk_store(self, entries: list) -> int:
        with self.background_manager.batch():
            return sum(bool(self.background_manager.add_background(e)) for e in entries)

    def _bulk_reload(self):
        self._load_backgrounds()

    def _bulk_all_sources(self) -> List[str]:
        return self.background_manager.get_all_sources()

    def _load_backgrounds(self):
        """Load all backgrounds from manager."""
        self._all_backgrounds = self.background_manager.backgrounds.copy()
        self._catalog = VersionCatalog(self._all_backgrounds)
        self._update_filter_options()
        self._on_filter_changed(immediate=True)
    
    def _update_filter_options(self):
        """Update filter dropdown options based on loaded backgrounds."""
        # Update skill options
        skills = self.background_manager.get_all_skills()
        skill_options = ["All Skills"] + skills
        self.skill_combo.configure(values=skill_options)

    def _clear_filters(self):
        """Reset every filter to its default value."""
        self.search_var.set("")
        self.titles_var.set(False)
        self.official_var.set("Any Content")
        self.skill_var.set("All Skills")
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._update_source_label()
        self._on_filter_changed(immediate=True)

    def _apply_filters(self):
        """Apply current filters to the background list."""
        search = self.search_var.get().lower()
        official_filter = self.official_var.get()
        skill_filter = self.skill_var.get()

        # Get legacy filter from settings
        legacy_filter = self.settings_manager.settings.legacy_content_filter

        filtered = []
        for background in self._all_backgrounds:
            # Search filter
            if not self._passes_search(search, background.name, [*background.skills, *background.feats]):
                continue

            # Source filter
            if not self._passes_source_filter(background.source):
                continue

            # Official content filter
            if not self._passes_official_filter(background.is_official, official_filter):
                continue

            # Grants skill filter
            if skill_filter != "All Skills" and skill_filter not in background.skills:
                continue

            filtered.append(background)

        # One entry per background: its versions (2024, 2014) are switched in the detail panel's Source
        # drop-down; the Legacy content setting decides which are offered
        filtered = self._catalog.collapse(filtered, legacy_filter)
        
        self._filtered_backgrounds = filtered
        
        # Preserve selection if possible
        current = self.list_panel.get_selected_background()
        preserve = current.name if current else None
        
        self.list_panel.set_backgrounds(filtered, preserve_selection=preserve)
    
    def _on_background_selected(self, background: Optional[Background]):
        """Handle background selection."""
        setting = self.settings_manager.settings.legacy_content_filter
        self.detail_panel.show_background(
            background, self._catalog.options(background, setting) if background else None)
    
    def _on_background_right_click(self, background: Background, x: int, y: int):
        """Handle right-click on background - show context menu."""
        self._context_background = background
        try:
            self.context_menu.tk_popup(x, y)
        finally:
            self.context_menu.grab_release()
    
    def _context_set_background(self):
        """Set background for current character from context menu."""
        if self._context_background and self.character_manager:
            char = self._active_character()
            if char:
                # Update character sheet background
                from ui.character_sheet_view import get_sheet_manager
                sheet_manager = get_sheet_manager()
                sheet = sheet_manager.get_or_create_sheet(char.name, char)
                sheet.background = self._context_background.name
                sheet_manager.update_sheet(char.name, sheet)
                
                messagebox.showinfo(
                    "Background Set",
                    f"Set {char.name}'s background to {self._context_background.name}.",
                    parent=self
                )
    
    def _context_compare(self):
        """Show compare panel from context menu."""
        if self._context_background:
            self._show_compare(self._context_background)
    
    def _show_compare(self, background: Background):
        """Show compare panel with the given background."""
        self._compare_mode = True
        self._compare_background = background
        
        # Hide list, show compare
        self.list_panel.pack_forget()
        self.compare_container.pack(fill="both", expand=True)
        self.compare_detail.show_background(background)
    
    def _close_compare(self):
        """Close the compare panel."""
        self._compare_mode = False
        self._compare_background = None
        
        self.compare_container.pack_forget()
        self.list_panel.pack(fill="both", expand=True)
    
    def _on_add_background(self):
        """Open dialog to add a new background."""
        from ui.studio_launch import open_in_studio
        if open_in_studio(self, "backgrounds"):
            return
        dialog = BackgroundEditorDialog(self.winfo_toplevel(), self.background_manager)
        dialog.grab_set()
        self.wait_window(dialog)
        
        if dialog.result:
            self._load_backgrounds()
            self.list_panel.select_when_listed(dialog.result.name)
    
    def _on_edit_background(self):
        """Edit the selected background."""
        background = self.list_panel.get_selected_background()
        if not background:
            messagebox.showwarning("No Selection", "Please select a background to edit.", parent=self)
            return
        
        if background.is_official and not background.is_custom:
            messagebox.showwarning(
                "Cannot Edit",
                "Official backgrounds cannot be edited. You can create a copy instead.",
                parent=self
            )
            return
        
        dialog = BackgroundEditorDialog(
            self.winfo_toplevel(), self.background_manager, background=background
        )
        dialog.grab_set()
        self.wait_window(dialog)
        
        if dialog.result:
            self._load_backgrounds()
            self.list_panel.select_when_listed(dialog.result.name)
    
    def _on_delete_background(self):
        """Delete the selected background."""
        background = self.list_panel.get_selected_background()
        if not background:
            messagebox.showwarning("No Selection", "Please select a background to delete.", parent=self)
            return
        
        if background.is_official and not background.is_custom:
            messagebox.showwarning(
                "Cannot Delete",
                "Official backgrounds cannot be deleted.",
                parent=self
            )
            return
        
        if messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{background.name}'?",
            parent=self
        ):
            self.background_manager.remove_background(background.name)
            self._load_backgrounds()
    
    def refresh(self):
        """Refresh the background list."""
        self._load_backgrounds()
    
    def select_background(self, name: str) -> bool:
        """Select a background by name. Returns True if found."""
        return self.list_panel.select_background(name, self._catalog.find(name))


class BackgroundEditorBody(EditorBody):
    """Dialog for creating/editing backgrounds. (the form; see ui/editor_host.py)"""
    
    def __init__(self, parent, background_manager: BackgroundManager, background: Optional[Background] = None):
        super().__init__(parent)
        
        self.background_manager = background_manager
        self.editing_background = background
        self.result: Optional[Background] = None
        self.theme = get_theme_manager()
        self._feature_entries = []  # List of (name_entry, desc_entry, frame) tuples
        
        self.title("Edit Background" if background else "Add Background")
        self.geometry("750x800")
        self.minsize(650, 600)
        
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 750) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 800) // 2
        self.geometry(f"+{x}+{y}")
        
        self._create_widgets()
        
        if background:
            self._populate_from_background(background)
    
    def _create_widgets(self):
        """Create the editor UI."""
        # Main scrollable container
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=20)

        # Name
        self.name_entry = self._add_entry_field(self.scroll, "Name: *")

        # Row for source and legacy
        source_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        source_row.pack(fill="x", pady=(0, 15))

        # Source
        source_frame = ctk.CTkFrame(source_row, fg_color="transparent")
        source_frame.pack(side="left", padx=(0, 20))
        self._field_label(source_frame, "Source: *")
        self.source_entry = ctk.CTkEntry(source_frame, width=250, height=35)
        self.source_entry.pack()

        # Is Legacy
        legacy_frame = ctk.CTkFrame(source_row, fg_color="transparent")
        legacy_frame.pack(side="left")
        self._field_label(legacy_frame, "Content Type:")
        self.legacy_var = ctk.BooleanVar(value=False)
        self.legacy_check = ctk.CTkCheckBox(
            legacy_frame, text="Legacy (2014) Content",
            variable=self.legacy_var
        )
        self.legacy_check.pack(anchor="w", pady=5)

        self.ability_scores_entry = self._add_entry_field(
            self.scroll, "Ability Scores (comma-separated):", placeholder="e.g., Strength, Dexterity, Charisma")
        self.skills_entry = self._add_entry_field(
            self.scroll, "Skill Proficiencies (comma-separated):", placeholder="e.g., Insight, Religion")
        self.proficiencies_entry = self._add_entry_field(
            self.scroll, "Tool Proficiencies (comma-separated):", placeholder="e.g., Calligrapher's Supplies")
        self.feats_entry = self._add_entry_field(
            self.scroll, "Origin Feat(s) (comma-separated for multiple options):",
            placeholder="e.g., Magic Initiate (Cleric)")

        # Equipment
        self._field_label(self.scroll, "Equipment:")
        self.equipment_text = ctk.CTkTextbox(self.scroll, height=60)
        self.equipment_text.pack(fill="x", pady=(5, 15))
        from ui.object_link_widgets import attach_object_linking
        attach_object_linking(self.equipment_text, self.theme)

        # Description
        self._field_label(self.scroll, "Description: *")
        self.desc_text = ctk.CTkTextbox(self.scroll, height=100)
        self.desc_text.pack(fill="x", pady=(5, 15))

        # Features section
        self._add_section_header(self.scroll, "Features:", "+ Add Feature", self._add_feature)

        # Container for feature entries
        self.features_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.features_container.pack(fill="x", pady=(5, 15))

        self._add_save_buttons_left(self.scroll)

    def _add_feature(self, name: str = "", description: str = ""):
        """Add a feature entry."""
        frame, _inner, name_entry, desc_entry = self._add_card(
            self.features_container, "Feature Name:", self._remove_feature, name, description)
        self._feature_entries.append((name_entry, desc_entry, frame))

    def _remove_feature(self, frame):
        """Remove a feature entry."""
        for i, (name_e, desc_e, f) in enumerate(self._feature_entries):
            if f == frame:
                frame.destroy()
                del self._feature_entries[i]
                break
    
    def _populate_from_background(self, background: Background):
        """Populate fields from existing background."""
        self.name_entry.insert(0, background.name)
        self.source_entry.insert(0, background.source)
        self.legacy_var.set(background.is_legacy)
        
        if background.ability_scores:
            self.ability_scores_entry.insert(0, ", ".join(background.ability_scores))
        
        if background.skills:
            self.skills_entry.insert(0, ", ".join(background.skills))
        
        if background.other_proficiencies:
            self.proficiencies_entry.insert(0, ", ".join(background.other_proficiencies))
        
        if background.feats:
            self.feats_entry.insert(0, ", ".join(background.feats))
        
        if background.equipment:
            self.equipment_text.insert("1.0", background.equipment)
        
        if background.description:
            self.desc_text.insert("1.0", background.description)
        
        for feature in background.features:
            self._add_feature(feature.name, feature.description)
    
    def build_result(self, strict: bool = True) -> Background:
        """The background the form describes (strict: ValueError if incomplete; otherwise gaps are filled in)."""
        name = self.name_entry.get().strip()
        source = self.source_entry.get().strip()
        description = self.desc_text.get("1.0", "end-1c").strip()
        if strict:
            if not name:
                raise ValueError("Name is required.")
            if not source:
                raise ValueError("Source is required.")
            if not description:
                raise ValueError("Description is required.")
        
        # Parse comma-separated fields
        ability_scores = [s.strip() for s in self.ability_scores_entry.get().split(",") if s.strip()]
        skills = [s.strip() for s in self.skills_entry.get().split(",") if s.strip()]
        proficiencies = [s.strip() for s in self.proficiencies_entry.get().split(",") if s.strip()]
        feats = [s.strip() for s in self.feats_entry.get().split(",") if s.strip()]
        equipment = self.equipment_text.get("1.0", "end-1c").strip()
        
        # Gather features
        features = []
        for name_entry, desc_entry, _ in self._feature_entries:
            feature_name = name_entry.get().strip()
            feature_desc = desc_entry.get("1.0", "end-1c").strip()
            if feature_name:
                features.append(BackgroundFeature(name=feature_name, description=feature_desc))
        
        return Background(
            name=name,
            source=source,
            is_legacy=self.legacy_var.get(),
            description=description,
            skills=skills,
            other_proficiencies=proficiencies,
            ability_scores=ability_scores,
            feats=feats,
            equipment=equipment,
            features=features,
            is_official=False,
            is_custom=True
        )

    def _accept(self, background):
        if not self.EMBEDDED:
            self.background_manager.add_background(background)
        super()._accept(background)

class BackgroundEditorDialog(BackgroundEditorBody, DialogWindow):
    """Dialog for creating/editing backgrounds."""


class BackgroundEditorPanel(BackgroundEditorBody, EmbeddedWindow):
    """The BackgroundEditorDialog form inside the Homebrew Studio."""
