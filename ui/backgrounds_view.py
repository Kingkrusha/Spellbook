"""
Backgrounds View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of backgrounds with details panel.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional, Callable
from background import Background, BackgroundFeature, BackgroundManager, get_background_manager
from theme import get_theme_manager
from settings import get_settings_manager


class BackgroundListPanel(ctk.CTkFrame):
    """A scrollable list panel for displaying and selecting backgrounds."""
    
    def __init__(self, parent, on_select: Callable[[Optional[Background]], None],
                 on_right_click: Optional[Callable[[Background, int, int], None]] = None):
        super().__init__(parent, corner_radius=10)
        
        self.on_select = on_select
        self.on_right_click = on_right_click
        self._backgrounds: List[Background] = []
        self._selected_index: Optional[int] = None
        self._background_buttons: List[ctk.CTkButton] = []
        self.theme = get_theme_manager()
        
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)
    
    def _on_theme_changed(self):
        """Handle theme changes."""
        self._refresh_buttons()
    
    def _create_widgets(self):
        """Create the scrollable background list."""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header_frame, text="Backgrounds", 
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        text_secondary = self.theme.get_text_secondary()
        self.count_label = ctk.CTkLabel(header_frame, text="0 backgrounds",
                                         font=ctk.CTkFont(size=12),
                                         text_color=text_secondary)
        self.count_label.pack(side="right")
        
        # Scrollable frame for background list
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _create_background_button(self, background: Background, index: int) -> ctk.CTkButton:
        """Create a button for a background."""
        display_name = background.name
        if background.is_custom:
            display_name = f"* {display_name}"
        
        btn = ctk.CTkButton(
            self.scroll_frame,
            text=display_name,
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color=("transparent" if index != self._selected_index 
                      else self.theme.get_current_color('accent_primary')),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            font=ctk.CTkFont(size=13),
            command=lambda i=index: self._on_background_click(i)
        )
        btn.pack(fill="x", pady=2)
        
        # Bind right-click event
        if self.on_right_click:
            btn.bind("<Button-3>", lambda e, i=index: self._on_background_right_click(e, i))
            for child in btn.winfo_children():
                child.bind("<Button-3>", lambda e, i=index: self._on_background_right_click(e, i))
        
        return btn
    
    def _on_background_right_click(self, event, index: int):
        """Handle right-click on a background button - show context menu only."""
        if self.on_right_click and 0 <= index < len(self._backgrounds):
            self.on_right_click(self._backgrounds[index], event.x_root, event.y_root)
    
    def _on_background_click(self, index: int):
        """Handle background selection."""
        if self._selected_index is not None and self._selected_index < len(self._background_buttons):
            self._background_buttons[self._selected_index].configure(fg_color="transparent")
        
        self._selected_index = index
        if index < len(self._background_buttons):
            self._background_buttons[index].configure(
                fg_color=self.theme.get_current_color('accent_primary')
            )
        
        if 0 <= index < len(self._backgrounds):
            self.on_select(self._backgrounds[index])
        else:
            self.on_select(None)
    
    def set_backgrounds(self, backgrounds: List[Background], reset_scroll: bool = True, 
                        preserve_selection: Optional[str] = None):
        """Update the list of backgrounds."""
        self._backgrounds = backgrounds
        
        # Find preserved selection
        new_selected_index = None
        if preserve_selection:
            for i, background in enumerate(backgrounds):
                if background.name == preserve_selection:
                    new_selected_index = i
                    break
        
        self._selected_index = new_selected_index
        
        # Clear existing buttons
        for btn in self._background_buttons:
            btn.destroy()
        self._background_buttons = []
        
        # Create new buttons
        for i, background in enumerate(backgrounds):
            btn = self._create_background_button(background, i)
            self._background_buttons.append(btn)
        
        # Update count
        self.count_label.configure(text=f"{len(backgrounds)} background{'s' if len(backgrounds) != 1 else ''}")
        
        # Restore selection if found
        if new_selected_index is not None:
            self._on_background_click(new_selected_index)
        elif reset_scroll and self.scroll_frame.winfo_children():
            self.scroll_frame._parent_canvas.yview_moveto(0)
    
    def _refresh_buttons(self):
        """Refresh button colors after theme change."""
        for i, btn in enumerate(self._background_buttons):
            if i == self._selected_index:
                btn.configure(fg_color=self.theme.get_current_color('accent_primary'))
            else:
                btn.configure(fg_color="transparent")
            btn.configure(
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary')
            )
    
    def get_selected_background(self) -> Optional[Background]:
        """Get the currently selected background."""
        if self._selected_index is not None and self._selected_index < len(self._backgrounds):
            return self._backgrounds[self._selected_index]
        return None
    
    def select_background(self, name: str) -> bool:
        """Select a background by name. Returns True if found."""
        for i, background in enumerate(self._backgrounds):
            if background.name.lower() == name.lower():
                self._on_background_click(i)
                return True
        return False


class BackgroundDetailPanel(ctk.CTkFrame):
    """Panel displaying detailed information about a background."""
    
    def __init__(self, parent):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self._current_background: Optional[Background] = None
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
        
        # Background name
        self.name_label = ctk.CTkLabel(
            self.scroll_frame, text="Select a background",
            font=ctk.CTkFont(size=24, weight="bold"),
            wraplength=800
        )
        self.name_label.pack(anchor="w", pady=(0, 5))
        
        # Source info
        self.source_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_text_secondary()
        )
        self.source_label.pack(anchor="w", pady=(0, 10))
        
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
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.ability_key.pack(side="left")
        self.ability_value = ctk.CTkLabel(
            self.ability_row, text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.ability_value.pack(side="left", fill="x")
        
        # Skills row
        self.skills_row = ctk.CTkFrame(self.stats_inner, fg_color="transparent")
        self.skills_row.pack(fill="x", anchor="w", pady=1)
        self.skills_key = ctk.CTkLabel(
            self.skills_row, text="Skills: ",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.skills_key.pack(side="left")
        self.skills_value = ctk.CTkLabel(
            self.skills_row, text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.skills_value.pack(side="left", fill="x")
        
        # Tool Proficiencies row
        self.prof_row = ctk.CTkFrame(self.stats_inner, fg_color="transparent")
        self.prof_row.pack(fill="x", anchor="w", pady=1)
        self.prof_key = ctk.CTkLabel(
            self.prof_row, text="Tool Proficiencies: ",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.prof_key.pack(side="left")
        self.prof_value = ctk.CTkLabel(
            self.prof_row, text="",
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        self.prof_value.pack(side="left", fill="x")
        
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
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.equipment_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ctk.CTkFont(size=12),
            wraplength=800,
            justify="left"
        )
        
        # Description
        self.desc_header = ctk.CTkLabel(
            self.scroll_frame, text="Description",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        
        # Description container for rich text rendering
        self.description_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self._desc_widgets = []
        
        # Features section
        self.features_header = ctk.CTkLabel(
            self.scroll_frame, text="Features",
            font=ctk.CTkFont(size=14, weight="bold")
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
    
    def _get_renderer(self):
        """Get or create the rich text renderer."""
        if not hasattr(self, '_renderer'):
            from ui.rich_text_utils import RichTextRenderer
            self._renderer = RichTextRenderer(self.theme)
        return self._renderer
    
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
                font=ctk.CTkFont(size=20, weight="bold")
            ).pack(anchor="w", pady=(0, 10))
            
            if feat.type:
                ctk.CTkLabel(
                    content, text=f"Type: {feat.type}",
                    font=ctk.CTkFont(size=12),
                    text_color=self.theme.get_text_secondary()
                ).pack(anchor="w")
            
            if feat.has_prereq and feat.prereq:
                ctk.CTkLabel(
                    content, text=f"Prerequisite: {feat.prereq}",
                    font=ctk.CTkFont(size=12),
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
            font=ctk.CTkFont(size=13, weight="bold"),
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
    
    def _clear_description(self):
        """Clear all description widgets."""
        for widget in self._desc_widgets:
            widget.destroy()
        self._desc_widgets = []
    
    def _render_description(self, text: str):
        """Render description with table and spell link support."""
        self._clear_description()
        
        if not text:
            return
        
        desc_container = ctk.CTkFrame(self.description_container, fg_color="transparent")
        desc_container.pack(fill="x", expand=True)
        self._desc_widgets.append(desc_container)
        
        renderer = self._get_renderer()
        renderer.render_formatted_text(
            desc_container, text,
            on_spell_click=lambda s: renderer.show_spell_popup(desc_container, s),
            wraplength=500
        )
    
    def show_background(self, background: Optional[Background]):
        """Display details for a background."""
        self._current_background = background
        
        if background is None:
            self.name_label.configure(text="Select a background")
            self.source_label.configure(text="")
            self.stats_frame.pack_forget()
            self.feat_frame.pack_forget()
            self._clear_feats()
            self.equipment_header.pack_forget()
            self.equipment_label.pack_forget()
            self.desc_header.pack_forget()
            self._clear_description()
            self.description_container.pack_forget()
            self.features_header.pack_forget()
            self.features_container.pack_forget()
            self._clear_features()
            return
        
        # Name (with custom indicator)
        name_text = f"* {background.name}" if background.is_custom else background.name
        self.name_label.configure(text=name_text)
        
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
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            )
            feat_label.pack(side="left", padx=(0, 10))
            self._feat_widgets.append(feat_label)
            
            for i, feat_name in enumerate(background.feats):
                if i > 0:
                    # Add "or" between multiple feats
                    or_label = ctk.CTkLabel(
                        self.feat_inner, text="or",
                        font=ctk.CTkFont(size=12, slant="italic"),
                        text_color=self.theme.get_text_secondary()
                    )
                    or_label.pack(side="left", padx=5)
                    self._feat_widgets.append(or_label)
                
                feat_btn = ctk.CTkButton(
                    self.feat_inner, text=feat_name,
                    font=ctk.CTkFont(size=12),
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
            self.equipment_label.configure(text=background.equipment)
            self.equipment_label.pack(anchor="w", pady=(0, 10))
        else:
            self.equipment_header.pack_forget()
            self.equipment_label.pack_forget()
        
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


class BackgroundsView(ctk.CTkFrame):
    """Main view for browsing and managing backgrounds."""
    
    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        
        self.background_manager = get_background_manager()
        self.character_manager = character_manager
        self.settings_manager = get_settings_manager()
        self.on_back = on_back
        self._all_backgrounds: List[Background] = []
        self._filtered_backgrounds: List[Background] = []
        self._compare_mode = False
        self._compare_background: Optional[Background] = None
        self._context_background: Optional[Background] = None
        
        self._create_widgets()
        self._create_context_menu()
        self._create_compare_panel()
        self._load_backgrounds()
        self.theme.add_listener(self._on_theme_changed)
    
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
        
        # Background list panel (left)
        self.list_panel = BackgroundListPanel(
            self.left_container, 
            on_select=self._on_background_selected,
            on_right_click=self._on_background_right_click
        )
        self.list_panel.pack(fill="both", expand=True)
        
        # Background detail panel (right)
        self.detail_panel = BackgroundDetailPanel(self.paned)
        
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
            placeholder_text="Search backgrounds...",
            textvariable=self.search_var
        )
        search_entry.pack(side="left", padx=(0, 15))
        
        # Source filter dropdown
        ctk.CTkLabel(filter_bar, text="Source:").pack(side="left", padx=(0, 5))
        
        self.source_var = ctk.StringVar(value="All Sources")
        self.source_combo = ctk.CTkComboBox(
            filter_bar, width=180, height=35,
            values=["All Sources"],
            variable=self.source_var,
            command=lambda _: self._apply_filters(),
            state="readonly"
        )
        self.source_combo.pack(side="left", padx=(0, 15))
        
        # Add background button (right side)
        add_btn = ctk.CTkButton(
            filter_bar, text="+ Add Background",
            width=140, height=35,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_add_background
        )
        add_btn.pack(side="right")
        
        # Edit/Delete buttons
        self.delete_btn = ctk.CTkButton(
            filter_bar, text="Delete",
            width=80, height=35,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._on_delete_background
        )
        self.delete_btn.pack(side="right", padx=(0, 5))
        
        self.edit_btn = ctk.CTkButton(
            filter_bar, text="Edit",
            width=80, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_edit_background
        )
        self.edit_btn.pack(side="right", padx=(0, 5))
    
    def _create_context_menu(self):
        """Create the right-click context menu for backgrounds."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self._update_context_menu_colors()
        self.context_menu.add_command(
            label="Set as Character Background",
            command=self._context_set_background
        )
        self.context_menu.add_command(
            label="Compare",
            command=self._context_compare
        )
    
    def _create_compare_panel(self):
        """Create the compare background panel (hidden initially)."""
        self.compare_container = ctk.CTkFrame(self.left_container, corner_radius=10)
        
        # Header with close button
        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text="Compare Backgrounds",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")
        
        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._close_compare
        ).pack(side="right")
        
        # Compare detail panel
        self.compare_detail = BackgroundDetailPanel(self.compare_container)
        self.compare_detail.pack(fill="both", expand=True, padx=5, pady=5)
    
    def _load_backgrounds(self):
        """Load all backgrounds from manager."""
        self._all_backgrounds = self.background_manager.backgrounds.copy()
        self._update_filter_options()
        self._apply_filters()
    
    def _update_filter_options(self):
        """Update filter dropdown options based on loaded backgrounds."""
        # Update source options
        sources = self.background_manager.get_all_sources()
        source_options = ["All Sources"] + sources
        self.source_combo.configure(values=source_options)
    
    def _apply_filters(self):
        """Apply current filters to the background list."""
        search = self.search_var.get().lower()
        source_filter = self.source_var.get()
        
        # Get legacy filter from settings
        legacy_filter = self.settings_manager.settings.legacy_content_filter
        
        filtered = []
        for background in self._all_backgrounds:
            # Search filter
            if search and search not in background.name.lower():
                if not any(search in skill.lower() for skill in background.skills):
                    if not any(search in feat.lower() for feat in background.feats):
                        continue
            
            # Source filter
            if source_filter != "All Sources" and background.source != source_filter:
                continue
            
            # Legacy filter from settings
            if legacy_filter == "no_legacy" and background.is_legacy:
                continue
            elif legacy_filter == "legacy_only" and not background.is_legacy:
                continue
            
            filtered.append(background)
        
        self._filtered_backgrounds = filtered
        
        # Preserve selection if possible
        current = self.list_panel.get_selected_background()
        preserve = current.name if current else None
        
        self.list_panel.set_backgrounds(filtered, preserve_selection=preserve)
    
    def _on_background_selected(self, background: Optional[Background]):
        """Handle background selection."""
        self.detail_panel.show_background(background)
    
    def _on_background_right_click(self, background: Background, x: int, y: int):
        """Handle right-click on background - show context menu."""
        self._context_background = background
        self.context_menu.tk_popup(x, y)
    
    def _context_set_background(self):
        """Set background for current character from context menu."""
        if self._context_background and self.character_manager:
            char = self.character_manager.get_active_character()
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
            else:
                messagebox.showwarning(
                    "No Character",
                    "No active character selected.",
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
        dialog = BackgroundEditorDialog(self.winfo_toplevel(), self.background_manager)
        dialog.grab_set()
        self.wait_window(dialog)
        
        if dialog.result:
            self._load_backgrounds()
            self.list_panel.select_background(dialog.result.name)
    
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
            self.list_panel.select_background(dialog.result.name)
    
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


class BackgroundEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing backgrounds."""
    
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
        ctk.CTkLabel(self.scroll, text="Name: *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(self.scroll, width=400, height=35)
        self.name_entry.pack(fill="x", pady=(5, 15))
        
        # Row for source and legacy
        source_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        source_row.pack(fill="x", pady=(0, 15))
        
        # Source
        source_frame = ctk.CTkFrame(source_row, fg_color="transparent")
        source_frame.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(source_frame, text="Source: *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.source_entry = ctk.CTkEntry(source_frame, width=250, height=35)
        self.source_entry.pack()
        
        # Is Legacy
        legacy_frame = ctk.CTkFrame(source_row, fg_color="transparent")
        legacy_frame.pack(side="left")
        ctk.CTkLabel(legacy_frame, text="Content Type:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.legacy_var = ctk.BooleanVar(value=False)
        self.legacy_check = ctk.CTkCheckBox(
            legacy_frame, text="Legacy (2014) Content",
            variable=self.legacy_var
        )
        self.legacy_check.pack(anchor="w", pady=5)
        
        # Ability Scores
        ctk.CTkLabel(self.scroll, text="Ability Scores (comma-separated):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.ability_scores_entry = ctk.CTkEntry(self.scroll, width=400, height=35,
                                                  placeholder_text="e.g., Strength, Dexterity, Charisma")
        self.ability_scores_entry.pack(fill="x", pady=(5, 15))
        
        # Skills
        ctk.CTkLabel(self.scroll, text="Skill Proficiencies (comma-separated):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.skills_entry = ctk.CTkEntry(self.scroll, width=400, height=35,
                                          placeholder_text="e.g., Insight, Religion")
        self.skills_entry.pack(fill="x", pady=(5, 15))
        
        # Other Proficiencies
        ctk.CTkLabel(self.scroll, text="Tool Proficiencies (comma-separated):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.proficiencies_entry = ctk.CTkEntry(self.scroll, width=400, height=35,
                                                 placeholder_text="e.g., Calligrapher's Supplies")
        self.proficiencies_entry.pack(fill="x", pady=(5, 15))
        
        # Feats
        ctk.CTkLabel(self.scroll, text="Origin Feat(s) (comma-separated for multiple options):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.feats_entry = ctk.CTkEntry(self.scroll, width=400, height=35,
                                         placeholder_text="e.g., Magic Initiate (Cleric)")
        self.feats_entry.pack(fill="x", pady=(5, 15))
        
        # Equipment
        ctk.CTkLabel(self.scroll, text="Equipment:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.equipment_text = ctk.CTkTextbox(self.scroll, height=60)
        self.equipment_text.pack(fill="x", pady=(5, 15))
        
        # Description
        ctk.CTkLabel(self.scroll, text="Description: *", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        self.desc_text = ctk.CTkTextbox(self.scroll, height=100)
        self.desc_text.pack(fill="x", pady=(5, 15))
        
        # Features section
        features_header = ctk.CTkFrame(self.scroll, fg_color="transparent")
        features_header.pack(fill="x", pady=(10, 5))
        
        ctk.CTkLabel(features_header, text="Features:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        ctk.CTkButton(
            features_header, text="+ Add Feature", width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            command=self._add_feature
        ).pack(side="right")
        
        # Container for feature entries
        self.features_container = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.features_container.pack(fill="x", pady=(5, 15))
        
        # Buttons
        btn_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))
        
        ctk.CTkButton(
            btn_frame, text="Save",
            width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_secondary'),
            command=self._save
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_frame, text="Cancel",
            width=100,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(side="left")
    
    def _add_feature(self, name: str = "", description: str = ""):
        """Add a feature entry."""
        from ui.rich_text_utils import RichTextEditor
        
        frame = ctk.CTkFrame(
            self.features_container,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        frame.pack(fill="x", pady=5)
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=10)
        
        # Header with remove button
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(header, text="Feature Name:", font=ctk.CTkFont(size=12)).pack(side="left")
        
        remove_btn = ctk.CTkButton(
            header, text="✕", width=25, height=25,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=lambda f=frame: self._remove_feature(f)
        )
        remove_btn.pack(side="right")
        
        name_entry = ctk.CTkEntry(inner, height=30)
        name_entry.pack(fill="x", pady=(5, 10))
        name_entry.insert(0, name)
        
        ctk.CTkLabel(inner, text="Description:", font=ctk.CTkFont(size=12)).pack(anchor="w")
        
        desc_entry = ctk.CTkTextbox(inner, height=80)
        
        # Add rich text toolbar
        rich_editor = RichTextEditor(self, desc_entry, self.theme)
        toolbar = rich_editor.create_toolbar(inner)
        toolbar.pack(fill="x", pady=(5, 5))
        
        desc_entry.pack(fill="x", pady=(0, 0))
        desc_entry.insert("1.0", description)
        
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
    
    def _save(self):
        """Save the background."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Name is required.", parent=self)
            return
        
        source = self.source_entry.get().strip()
        if not source:
            messagebox.showerror("Error", "Source is required.", parent=self)
            return
        
        description = self.desc_text.get("1.0", "end-1c").strip()
        if not description:
            messagebox.showerror("Error", "Description is required.", parent=self)
            return
        
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
        
        background = Background(
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
        
        self.background_manager.add_background(background)
        self.result = background
        self.destroy()
