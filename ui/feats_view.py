"""
Feats View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of feats with details panel.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Callable
from feat import Feat, FeatManager, get_feat_manager
from theme import get_theme_manager
from settings import get_settings_manager


class FeatListPanel(ctk.CTkFrame):
    """A scrollable list panel for displaying and selecting feats."""
    
    def __init__(self, parent, on_select: Callable[[Optional[Feat]], None],
                 on_right_click: Optional[Callable[[Feat, int, int], None]] = None):
        super().__init__(parent, corner_radius=10)
        
        self.on_select = on_select
        self.on_right_click = on_right_click  # Callback for right-click (feat, x, y)
        self._feats: List[Feat] = []
        self._selected_index: Optional[int] = None
        self._feat_buttons: List[ctk.CTkButton] = []
        self.theme = get_theme_manager()
        
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self._refresh_buttons()
    
    def _create_widgets(self):
        """Create the scrollable feat list."""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header_frame, text="Feats", 
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        text_secondary = self.theme.get_text_secondary()
        self.count_label = ctk.CTkLabel(header_frame, text="0 feats",
                                         font=ctk.CTkFont(size=12),
                                         text_color=text_secondary)
        self.count_label.pack(side="right")
        
        # Scrollable frame for feat list
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _create_feat_button(self, feat: Feat, index: int) -> ctk.CTkButton:
        """Create a button for a feat."""
        # Build display text with type indicator
        display_name = feat.name
        if feat.is_custom:
            display_name = f"* {display_name}"
        
        indicators = []
        if feat.type:
            indicators.append(feat.type)
        if feat.is_spellcasting:
            indicators.append("✨")
        
        if indicators:
            indicator_text = f"  ({', '.join(indicators)})"
        else:
            indicator_text = ""
        
        btn = ctk.CTkButton(
            self.scroll_frame,
            text=f"{display_name}{indicator_text}",
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color=("transparent" if index != self._selected_index 
                      else self.theme.get_current_color('accent_primary')),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            font=ctk.CTkFont(size=13),
            command=lambda i=index: self._on_feat_click(i)
        )
        btn.pack(fill="x", pady=2)
        
        # Bind right-click event
        if self.on_right_click:
            btn.bind("<Button-3>", lambda e, i=index: self._on_feat_right_click(e, i))
            # Also bind to the internal button label for better coverage
            for child in btn.winfo_children():
                child.bind("<Button-3>", lambda e, i=index: self._on_feat_right_click(e, i))
        
        return btn
    
    def _on_feat_right_click(self, event, index: int):
        """Handle right-click on a feat button."""
        if self.on_right_click and 0 <= index < len(self._feats):
            # Get screen coordinates for the menu
            x = event.x_root
            y = event.y_root
            self.on_right_click(self._feats[index], x, y)
    
    def _on_feat_click(self, index: int):
        """Handle feat button click."""
        # Update selection
        old_index = self._selected_index
        self._selected_index = index
        
        # Update button colors
        if old_index is not None and old_index < len(self._feat_buttons):
            self._feat_buttons[old_index].configure(fg_color="transparent")
        
        if index < len(self._feat_buttons):
            self._feat_buttons[index].configure(
                fg_color=self.theme.get_current_color('accent_primary')
            )
        
        # Notify callback
        if 0 <= index < len(self._feats):
            self.on_select(self._feats[index])
    
    def set_feats(self, feats: List[Feat], reset_scroll: bool = True):
        """Set the list of feats to display."""
        # Remember current selection name
        current_name = None
        if self._selected_index is not None and self._selected_index < len(self._feats):
            current_name = self._feats[self._selected_index].name
        
        self._feats = feats
        self._selected_index = None
        
        # Clear existing buttons
        for btn in self._feat_buttons:
            btn.destroy()
        self._feat_buttons = []
        
        # Find new index for previously selected feat
        new_selected_index = None
        if current_name:
            for i, feat in enumerate(feats):
                if feat.name == current_name:
                    new_selected_index = i
                    break
        
        # Create new buttons
        for i, feat in enumerate(feats):
            btn = self._create_feat_button(feat, i)
            self._feat_buttons.append(btn)
        
        # Update count
        self.count_label.configure(text=f"{len(feats)} feat{'s' if len(feats) != 1 else ''}")
        
        # Restore selection if found
        if new_selected_index is not None:
            self._on_feat_click(new_selected_index)
        elif reset_scroll and self.scroll_frame.winfo_children():
            self.scroll_frame._parent_canvas.yview_moveto(0)
    
    def _refresh_buttons(self):
        """Refresh button colors after theme change."""
        for i, btn in enumerate(self._feat_buttons):
            if i == self._selected_index:
                btn.configure(fg_color=self.theme.get_current_color('accent_primary'))
            else:
                btn.configure(fg_color="transparent")
            btn.configure(
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary')
            )
    
    def get_selected_feat(self) -> Optional[Feat]:
        """Get the currently selected feat."""
        if self._selected_index is not None and self._selected_index < len(self._feats):
            return self._feats[self._selected_index]
        return None
    
    def select_feat(self, name: str) -> bool:
        """Select a feat by name. Returns True if found."""
        for i, feat in enumerate(self._feats):
            if feat.name.lower() == name.lower():
                self._on_feat_click(i)
                return True
        return False


class FeatDetailPanel(ctk.CTkFrame):
    """Panel displaying detailed information about a feat."""
    
    def __init__(self, parent):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self._current_feat: Optional[Feat] = None
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self._update_colors()
    
    def _create_widgets(self):
        """Create the detail view widgets."""
        # Scrollable content
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Feat name
        self.name_label = ctk.CTkLabel(
            self.scroll_frame, text="Select a feat",
            font=ctk.CTkFont(size=24, weight="bold"),
            wraplength=400
        )
        self.name_label.pack(anchor="w", pady=(0, 5))
        
        # Type badge
        self.type_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.type_frame.pack(anchor="w", pady=(0, 5))
        
        self.type_badge = ctk.CTkLabel(
            self.type_frame, text="",
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5,
            padx=8, pady=2
        )
        
        # Source info
        self.source_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_text_secondary()
        )
        self.source_label.pack(anchor="w", pady=(0, 10))
        
        # Prerequisites
        self.prereq_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.prereq_frame.pack(fill="x", pady=(0, 10))
        
        self.prereq_label = ctk.CTkLabel(
            self.prereq_frame, text="",
            font=ctk.CTkFont(size=12),
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
        
        self.spell_info_label = ctk.CTkLabel(
            self.spell_frame, text="",
            font=ctk.CTkFont(size=12),
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
    
    def _clear_description(self):
        """Clear all description widgets."""
        for widget in self._desc_widgets:
            widget.destroy()
        self._desc_widgets = []
    
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
    
    def show_feat(self, feat: Optional[Feat]):
        """Display details for a feat."""
        self._current_feat = feat
        
        if feat is None:
            self.name_label.configure(text="Select a feat")
            self.type_badge.pack_forget()
            self.source_label.configure(text="")
            self.prereq_label.pack_forget()
            self.spell_frame.pack_forget()
            self._clear_description()
            return
        
        # Name (with custom indicator)
        name_text = f"* {feat.name}" if feat.is_custom else feat.name
        self.name_label.configure(text=name_text)
        
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
            self.source_label.configure(text=source_text)
        else:
            self.source_label.configure(text="")
        
        # Prerequisites
        if feat.has_prereq and feat.prereq:
            self.prereq_label.configure(text=f"Prerequisite: {feat.prereq}")
            self.prereq_label.pack(anchor="w")
        else:
            self.prereq_label.pack_forget()
        
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


class FeatsView(ctk.CTkFrame):
    """Main view for browsing and managing feats."""
    
    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        
        self.feat_manager = get_feat_manager()
        self.character_manager = character_manager
        self.settings_manager = get_settings_manager()
        self.on_back = on_back  # Callback for back button
        self._all_feats: List[Feat] = []
        self._filtered_feats: List[Feat] = []
        self._compare_mode = False
        self._compare_feat: Optional[Feat] = None
        self._context_feat: Optional[Feat] = None
        
        self._create_widgets()
        self._create_context_menu()
        self._create_compare_panel()
        self._load_feats()
        self.theme.add_listener(self._on_theme_changed)
    
    def set_character_manager(self, character_manager):
        """Set the character manager for add-to-character functionality."""
        self.character_manager = character_manager
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._update_context_menu_colors()
        if hasattr(self, 'paned'):
            self._update_paned_colors()
    
    def _update_context_menu_colors(self):
        """Update context menu colors for theme."""
        if not hasattr(self, 'context_menu'):
            return
        bg_color = self.theme.get_current_color('bg_secondary')
        fg_color = self.theme.get_current_color('text_primary')
        self.context_menu.configure(
            bg=bg_color,
            fg=fg_color,
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=fg_color
        )
    
    def _create_widgets(self):
        """Create the main layout."""
        # Top bar with search and filters
        self._create_filter_bar()
        
        # Main content area with list and detail panels
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Create a PanedWindow for resizable panels
        self.paned = tk.PanedWindow(
            self.content,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            handlesize=0,
            opaqueresize=False,
            sashcursor="sb_h_double_arrow"
        )
        self.paned.pack(fill="both", expand=True)
        self._update_paned_colors()
        
        # Left container to hold list or compare panel
        self.left_container = ctk.CTkFrame(self.paned, fg_color="transparent")
        
        # Feat list panel (left)
        self.list_panel = FeatListPanel(
            self.left_container, 
            on_select=self._on_feat_selected,
            on_right_click=self._on_feat_right_click
        )
        self.list_panel.pack(fill="both", expand=True)
        
        # Feat detail panel (right)
        self.detail_panel = FeatDetailPanel(self.paned)
        
        # Add panes with minimum sizes
        self.paned.add(self.left_container, minsize=280, stretch="always")
        self.paned.add(self.detail_panel, minsize=400, stretch="always")
        
        # Set initial sash position (roughly 1:2 ratio)
        self.after(100, lambda: self.paned.sash_place(0, 320, 0))
    
    def _update_paned_colors(self):
        """Update PanedWindow sash colors based on current theme."""
        sash_color = self.theme.get_current_color("pane_sash")
        self.paned.configure(bg=sash_color)
    
    def _create_filter_bar(self):
        """Create the filter bar at the top."""
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)
        
        # Back button to return to collections
        if self.on_back:
            back_btn = ctk.CTkButton(
                filter_bar, text="← Collections", width=110,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                command=self.on_back
            )
            back_btn.pack(side="left", padx=(0, 15))
        
        # Search box
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._apply_filters())
        
        search_entry = ctk.CTkEntry(
            filter_bar, width=250, height=35,
            placeholder_text="Search feats...",
            textvariable=self.search_var
        )
        search_entry.pack(side="left", padx=(0, 15))
        
        # Type filter dropdown
        ctk.CTkLabel(filter_bar, text="Type:").pack(side="left", padx=(0, 5))
        
        # Get all types from feat manager (auto-populated)
        all_types = self.feat_manager.get_all_types()
        type_options = ["All Types"] + [t if t else "General" for t in all_types]
        self.type_var = ctk.StringVar(value="All Types")
        self.type_combo = ctk.CTkComboBox(
            filter_bar, width=180, height=35,
            values=type_options,
            variable=self.type_var,
            command=lambda _: self._apply_filters(),
            state="readonly"
        )
        self.type_combo.pack(side="left", padx=(0, 15))
        
        # Spellcasting filter
        self.spellcasting_var = ctk.BooleanVar(value=False)
        self.spellcasting_check = ctk.CTkCheckBox(
            filter_bar, text="Spellcasting Only",
            variable=self.spellcasting_var,
            command=self._apply_filters
        )
        self.spellcasting_check.pack(side="left", padx=(0, 15))
        
        # Add feat button (right side)
        add_btn = ctk.CTkButton(
            filter_bar, text="+ Add Feat",
            width=100, height=35,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_add_feat
        )
        add_btn.pack(side="right")
        
        # Edit/Delete buttons
        self.delete_btn = ctk.CTkButton(
            filter_bar, text="Delete",
            width=80, height=35,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._on_delete_feat
        )
        self.delete_btn.pack(side="right", padx=(0, 5))
        
        self.edit_btn = ctk.CTkButton(
            filter_bar, text="Edit",
            width=80, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_edit_feat
        )
        self.edit_btn.pack(side="right", padx=(0, 5))
    
    def _create_context_menu(self):
        """Create the right-click context menu for feats."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self._update_context_menu_colors()
        self.context_menu.add_command(
            label="Add to Character",
            command=self._context_add_to_character
        )
        self.context_menu.add_command(
            label="View and Compare",
            command=self._context_view_compare
        )
    
    def _create_compare_panel(self):
        """Create the compare feat panel (hidden initially)."""
        # Container frame that will replace the feat list when comparing
        self.compare_container = ctk.CTkFrame(self.left_container, corner_radius=10)
        
        # Header with close button
        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text="Compare Feat",
            font=ctk.CTkFont(size=14, weight="bold")
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
        
        if not self.character_manager:
            messagebox.showwarning("No Characters", "No character manager available.")
            return
        
        characters = self.character_manager.characters
        if not characters:
            messagebox.showwarning("No Characters", "No characters available. Create a character first.")
            return
        
        # Show dialog to select character
        dialog = AddFeatToCharacterDialog(
            self.winfo_toplevel(),
            self._context_feat.name,
            characters
        )
        self.wait_window(dialog)
        
        if dialog.result:
            character = self.character_manager.get_character(dialog.result)
            if character:
                # Check if feat is already on character
                if self._context_feat.name in character.feats:
                    messagebox.showinfo("Already Added", 
                                       f"'{self._context_feat.name}' is already on {character.name}'s feat list.")
                    return
                
                # Add the feat
                character.feats.append(self._context_feat.name)
                self.character_manager.save_characters()
                messagebox.showinfo("Success", 
                                   f"Added '{self._context_feat.name}' to {character.name}'s feats!")
    
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
    
    def _load_feats(self):
        """Load feats from the manager."""
        self._all_feats = sorted(self.feat_manager.feats, key=lambda f: f.name.lower())
        # Refresh type dropdown with all available types
        all_types = self.feat_manager.get_all_types()
        type_options = ["All Types"] + [t if t else "General" for t in all_types]
        self.type_combo.configure(values=type_options)
        self._apply_filters()
    
    def _apply_filters(self):
        """Apply current filters to the feat list."""
        search_text = self.search_var.get().lower()
        type_filter = self.type_var.get()
        spellcasting_only = self.spellcasting_var.get()
        legacy_filter = self.settings_manager.settings.legacy_content_filter
        
        filtered = []
        for feat in self._all_feats:
            # Search filter
            if search_text:
                if (search_text not in feat.name.lower() and 
                    search_text not in feat.description.lower()):
                    continue
            
            # Type filter
            if type_filter != "All Types":
                feat_type = feat.type if feat.type else "General"
                if feat_type != type_filter:
                    continue
            
            # Spellcasting filter
            if spellcasting_only and not feat.is_spellcasting:
                continue
            
            filtered.append(feat)
        
        # Apply legacy content filter
        if legacy_filter == "no_legacy":
            # Only show non-legacy feats
            filtered = [f for f in filtered if not f.is_legacy]
        elif legacy_filter == "legacy_only":
            # Only show legacy feats
            filtered = [f for f in filtered if f.is_legacy]
        elif legacy_filter == "show_unupdated":
            # Show non-legacy feats + legacy feats that don't have a non-legacy version
            non_legacy_names = {f.name.lower() for f in filtered if not f.is_legacy}
            filtered = [f for f in filtered if not f.is_legacy or f.name.lower() not in non_legacy_names]
        # "show_all" - no filtering needed
        
        self._filtered_feats = filtered
        self.list_panel.set_feats(filtered)
    
    def _on_feat_selected(self, feat: Optional[Feat]):
        """Handle feat selection."""
        self.detail_panel.show_feat(feat)
        
        # Enable/disable edit/delete based on selection and custom status
        if feat:
            self.edit_btn.configure(state="normal" if feat.is_custom else "disabled")
            self.delete_btn.configure(state="normal" if feat.is_custom else "disabled")
        else:
            self.edit_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")
    
    def _on_add_feat(self):
        """Open dialog to add a new feat."""
        dialog = FeatEditorDialog(self, "Add Feat")
        self.wait_window(dialog)
        
        if dialog.result:
            dialog.result.is_custom = True
            if self.feat_manager.add_feat(dialog.result):
                self._load_feats()
                messagebox.showinfo("Success", f"Feat '{dialog.result.name}' added!")
            else:
                messagebox.showerror("Error", f"A feat named '{dialog.result.name}' already exists.")
    
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


class FeatEditorDialog(ctk.CTkToplevel):
    """Dialog for adding/editing a feat."""
    
    def __init__(self, parent, title: str, feat: Optional[Feat] = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("600x750")
        self.transient(parent)
        self.grab_set()
        
        self.theme = get_theme_manager()
        self.result: Optional[Feat] = None
        self._editing_feat = feat
        
        self._create_widgets()
        
        if feat:
            self._populate_from_feat(feat)
        
        # Center dialog
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create the editor widgets."""
        from ui.rich_text_utils import RichTextEditor
        
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.feat_manager = get_feat_manager()
        
        # Name
        ctk.CTkLabel(scroll, text="Name:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(scroll, width=400)
        self.name_entry.pack(fill="x", pady=(0, 10))
        
        # Type (editable combobox for custom types)
        ctk.CTkLabel(scroll, text="Type:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        ctk.CTkLabel(scroll, text="Select or type a custom type (blank = General)",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
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
        ctk.CTkLabel(scroll, text="Source:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
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
        ctk.CTkLabel(scroll, text="Description:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10, 0))
        
        self.desc_text = ctk.CTkTextbox(scroll, height=200)
        self._rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(scroll)
        toolbar.pack(fill="x", pady=(5, 5))
        
        self.desc_text.pack(fill="x", pady=(0, 10))
        
        # Buttons
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
    
    def _save(self):
        """Save the feat."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Feat name is required.")
            return
        
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
        
        self.result = Feat(
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
            is_legacy=False
        )
        
        self.destroy()


class AddFeatToCharacterDialog(ctk.CTkToplevel):
    """Dialog for selecting which character to add a feat to."""
    
    def __init__(self, parent, feat_name: str, characters: list):
        super().__init__(parent)
        self.title("Add Feat to Character")
        self.geometry("350x200")
        self.transient(parent)
        self.grab_set()
        
        self.result: Optional[str] = None
        self.theme = get_theme_manager()
        
        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            content, 
            text=f"Add '{feat_name}' to:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 15))
        
        # Character dropdown
        character_names = [c.name for c in characters]
        self.char_var = ctk.StringVar(value=character_names[0] if character_names else "")
        
        self.char_combo = ctk.CTkComboBox(
            content, width=280, height=35,
            values=character_names,
            variable=self.char_var,
            state="readonly"
        )
        self.char_combo.pack(fill="x", pady=(0, 20))
        
        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1,
            command=self.destroy
        ).pack(side="right", padx=(5, 0))
        
        ctk.CTkButton(
            btn_frame, text="Add", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            command=self._on_add
        ).pack(side="right")
        
        # Center dialog
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _on_add(self):
        """Handle add button click."""
        self.result = self.char_var.get()
        self.destroy()
