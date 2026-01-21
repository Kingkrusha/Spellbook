"""
Main application window for D&D Spellbook (CustomTkinter version).
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from typing import List, Optional
from spell_manager import SpellManager
from character_manager import CharacterManager
from spell import Spell, CharacterClass, AdvancedFilters, TagFilterMode
from settings import SettingsManager, get_settings_manager
from validation import validate_spell_for_character
from theme import get_theme_manager


class TagFilterDialog(ctk.CTkToplevel):
    """Dialog for selecting multiple tags to filter by."""
    
    def __init__(self, parent, available_tags: List[str], selected_tags: List[str], 
                 current_mode: TagFilterMode = TagFilterMode.HAS_ALL):
        super().__init__(parent)
        
        self.result: List[str] = selected_tags.copy()
        self.result_mode: TagFilterMode = current_mode
        self._tag_vars = {}
        
        self.title("Select Tags")
        self.geometry("350x500")
        self.minsize(300, 400)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Create widgets
        self._create_widgets(available_tags, selected_tags, current_mode)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self, available_tags: List[str], selected_tags: List[str], current_mode: TagFilterMode):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Header
        ctk.CTkLabel(
            container,
            text="Select tags to filter by:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", pady=(0, 10))

        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        
        # Filter mode selector
        mode_frame = ctk.CTkFrame(container, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            mode_frame,
            text="Filter mode:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 10))
        
        self._mode_var = ctk.StringVar(value=current_mode.value)
        mode_combo = ctk.CTkComboBox(
            mode_frame,
            values=["has_all", "has_any", "has_none"],
            variable=self._mode_var,
            width=150,
            state="readonly",
            command=self._on_mode_changed
        )
        mode_combo.pack(side="left")
        
        # Mode description label
        self._mode_desc_label = ctk.CTkLabel(
            container,
            text=self._get_mode_description(current_mode.value),
            font=ctk.CTkFont(size=11),
            text_color=text_secondary
        )
        self._mode_desc_label.pack(fill="x", pady=(0, 15))

        if not available_tags:
            ctk.CTkLabel(
                container,
                text="No tags found in your spell collection.",
                font=ctk.CTkFont(size=13),
                text_color=text_secondary
            ).pack(pady=30)
        else:
            # Scrollable tag list
            scroll = ctk.CTkScrollableFrame(container)
            scroll.pack(fill="both", expand=True, pady=(0, 15))

            selected_lower = [t.lower() for t in selected_tags]

            for tag in sorted(available_tags):
                var = ctk.BooleanVar(value=tag.lower() in selected_lower)
                self._tag_vars[tag] = var

                cb = ctk.CTkCheckBox(
                    scroll, text=tag, variable=var,
                    font=ctk.CTkFont(size=13)
                )
                cb.pack(fill="x", pady=3)

        # Button frame
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        # Theme-aware buttons
        danger = theme.get_current_color('button_danger')
        danger_hover = theme.get_current_color('button_danger_hover')
        btn_text = theme.get_current_color('text_primary')

        ctk.CTkButton(btn_frame, text="Clear All", width=90,
                      fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
                      text_color=btn_text,
                      command=self._clear_all).pack(side="left")

        ctk.CTkButton(btn_frame, text="Cancel", width=80,
                      fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
                      text_color=btn_text,
                      command=self._on_cancel).pack(side="right", padx=(10, 0))

        ctk.CTkButton(btn_frame, text="Apply", width=80,
                      fg_color=theme.get_current_color('accent_primary'), hover_color=theme.get_current_color('accent_hover'),
                      text_color=btn_text,
                      command=self._on_apply).pack(side="right")
    
    def _get_mode_description(self, mode: str) -> str:
        """Get the description text for a filter mode."""
        descriptions = {
            "has_all": "Spells must have ALL selected tags",
            "has_any": "Spells must have at least ONE selected tag",
            "has_none": "Spells must NOT have any selected tags"
        }
        return descriptions.get(mode, "")
    
    def _on_mode_changed(self, value: str):
        """Update description when mode changes."""
        self._mode_desc_label.configure(text=self._get_mode_description(value))
    
    def _clear_all(self):
        """Clear all tag selections."""
        for var in self._tag_vars.values():
            var.set(False)
    
    def _on_apply(self):
        """Apply selection and close."""
        self.result = [tag for tag, var in self._tag_vars.items() if var.get()]
        self.result_mode = TagFilterMode(self._mode_var.get())
        self.destroy()
    
    def _on_cancel(self):
        """Cancel and close."""
        self.destroy()


class MainWindow(ctk.CTkFrame):
    """Main application window with tabs, toolbar, and paned layout."""
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        # Initialize managers
        self.spell_manager = SpellManager()
        self.spell_manager.load_spells()
        
        self.character_manager = CharacterManager()
        self.character_manager.load_characters()
        
        self.settings_manager = get_settings_manager()
        
        # On first run, mark all existing spells as "Official" and seed stat blocks
        if not self.settings_manager.settings.initial_official_tag_applied:
            if len(self.spell_manager.spells) > 0:
                count = self.spell_manager.mark_all_spells_official()
                print(f"First run: marked {count} spells as Official.")
            
            # Seed official stat blocks for summoning spells
            try:
                from seed_stat_blocks import seed_stat_blocks
                stat_block_count = seed_stat_blocks()
                print(f"First run: added {stat_block_count} official stat blocks.")
            except Exception as e:
                print(f"Warning: Could not seed stat blocks: {e}")
            
            self.settings_manager.settings.initial_official_tag_applied = True
            self.settings_manager.save()
        
        # Apply appearance mode from settings
        ctk.set_appearance_mode(self.settings_manager.settings.appearance_mode)
        # Register for theme change notifications
        theme = get_theme_manager()
        theme.add_listener(self._on_theme_changed)
        # keep a reference for cleanup on destroy
        self._theme = theme
        # Apply base background to root and this frame so transparent children show themed bg
        try:
            parent.configure(fg_color=theme.get_current_color('bg_primary'))
        except Exception:
            pass
        try:
            self.configure(fg_color=theme.get_current_color('bg_primary'))
        except Exception:
            pass

        # State
        self._advanced_expanded = False
        self._current_tab = "spells"
        self._selected_tags: List[str] = []
        self._tag_filter_mode: TagFilterMode = TagFilterMode.HAS_ALL
        self._compare_mode = False  # Whether compare panel is shown
        self._compare_spell: Optional[Spell] = None  # Spell in compare panel
        self._filter_debounce_id: Optional[str] = None  # For debouncing filter changes
        self._filter_debounce_delay = 200  # Milliseconds to wait before applying filters
        
        # Build UI
        self._create_tab_bar()
        self._create_spells_view()
        self._create_spell_lists_view()
        self._create_settings_view()
        self._create_context_menu()
        
        # Bind spell manager updates
        self.spell_manager.add_listener(self._on_spells_changed)
        
        # Initial refresh
        self._refresh_spell_list()
        self._show_tab("spells")

    def destroy(self):
        """Clean up listeners to avoid leaks when the main window is destroyed."""
        try:
            if hasattr(self, '_theme'):
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass

        try:
            self.spell_manager.remove_listener(self._on_spells_changed)
        except Exception:
            pass

        super().destroy()
    
    def _create_tab_bar(self):
        """Create the tab bar for switching between views."""
        theme = get_theme_manager()
        # Theme-aware tab bar colors
        tab_bar = ctk.CTkFrame(self, fg_color=theme.get_current_color('tab_bar'), corner_radius=0, height=50)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)
        
        # Tab container
        tabs_container = ctk.CTkFrame(tab_bar, fg_color="transparent")
        tabs_container.pack(side="left", padx=15, pady=8)
        
        # Get text color for tab buttons
        btn_text = theme.get_current_color('text_primary')
        
        # Spells tab
        self.spells_tab_btn = ctk.CTkButton(
            tabs_container, text="Spells", width=100, height=34,
            corner_radius=8,
            text_color=btn_text,
            command=lambda: self._show_tab("spells")
        )
        self.spells_tab_btn.pack(side="left", padx=(0, 5))
        
        # Spell Lists tab
        self.lists_tab_btn = ctk.CTkButton(
            tabs_container, text="Spell Lists", width=100, height=34,
            corner_radius=8,
            fg_color="transparent", hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=lambda: self._show_tab("spell_lists")
        )
        self.lists_tab_btn.pack(side="left", padx=(0, 5))
        
        # Settings tab (on the right side)
        self.settings_tab_btn = ctk.CTkButton(
            tab_bar, text="⚙ Settings", width=100, height=34,
            corner_radius=8,
            fg_color="transparent", hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=lambda: self._show_tab("settings")
        )
        self.settings_tab_btn.pack(side="right", padx=15, pady=8)
    
    def _show_tab(self, tab_name: str):
        """Switch to the specified tab."""
        self._current_tab = tab_name
        theme = get_theme_manager()
        
        # Reset all tab button styles
        self.spells_tab_btn.configure(fg_color="transparent")
        self.lists_tab_btn.configure(fg_color="transparent")
        self.settings_tab_btn.configure(fg_color="transparent")
        
        # Hide all views
        self.spells_view.pack_forget()
        self.spell_lists_view.pack_forget()
        self.settings_view.pack_forget()

        # Show selected tab
        active_color = theme.get_current_color('accent_primary')
        if tab_name == "spells":
            self.spells_tab_btn.configure(fg_color=active_color)
            self.spells_view.pack(fill="both", expand=True)
        elif tab_name == "spell_lists":
            self.lists_tab_btn.configure(fg_color=active_color)
            self.spell_lists_view.pack(fill="both", expand=True)
        elif tab_name == "settings":
            self.settings_tab_btn.configure(fg_color=active_color)
            self.settings_view.pack(fill="both", expand=True)
            self.settings_view.refresh_from_settings()
    
    def _navigate_to_spell(self, spell_name: str):
        """Navigate to the spells tab and select a specific spell."""
        # Switch to spells tab
        self._show_tab("spells")
        
        # Clear filters to ensure spell is visible
        self.search_var.set("")
        self.level_var.set("All")
        self.class_var.set("All")
        self._clear_advanced_filters()
        
        # Refresh and select the spell
        self._refresh_spell_list()
        self.spell_list.select_spell(spell_name)
    
    def _create_spells_view(self):
        """Create the spells view (main spell browser)."""
        self.spells_view = ctk.CTkFrame(self, fg_color="transparent")
        
        self._create_toolbar()
        self._create_advanced_filters()
        self._create_main_content()
    
    def _create_spell_lists_view(self):
        """Create the spell lists view."""
        from ui.spell_lists_view import SpellListsView
        self.spell_lists_view = SpellListsView(
            self, self.character_manager, self.spell_manager,
            on_navigate_to_spell=self._navigate_to_spell,
            settings_manager=self.settings_manager
        )
    
    def _create_settings_view(self):
        """Create the settings view."""
        from ui.settings_view import SettingsView
        self.settings_view = SettingsView(
            self, self.settings_manager,
            on_appearance_changed=self._on_appearance_changed
        )
    
    def _on_appearance_changed(self, mode: str):
        """Handle appearance mode change from settings."""
        # Update theme-dependent widgets that use tk (not ctk)
        self._update_context_menu_colors()
        self._update_paned_colors()
        
        # Update spell detail description colors
        if hasattr(self, 'spell_detail'):
            self.spell_detail._update_description_colors()
        if hasattr(self, 'compare_detail'):
            self.compare_detail._update_description_colors()
        
        # Update spell lists view paned window
        if hasattr(self, 'spell_lists_view'):
            self.spell_lists_view.update_paned_colors()

    def _on_theme_changed(self):
        """Handle ThemeManager changes (colors updated or custom theme saved)."""
        theme = get_theme_manager()
        # Update widgets that rely on TK colors or CTkFrame backgrounds
        self._update_context_menu_colors()
        self._update_paned_colors()

        # Update root and main frame backgrounds so transparent widgets reflect the theme
        try:
            self.configure(fg_color=theme.get_current_color('bg_primary'))
        except Exception:
            pass

        # Reconfigure key tab/toolbar buttons to pick up new hover/fg colors
        try:
            self.spells_tab_btn.configure(hover_color=theme.get_current_color('button_hover'))
            self.lists_tab_btn.configure(hover_color=theme.get_current_color('button_hover'))
            self.settings_tab_btn.configure(hover_color=theme.get_current_color('button_hover'))
        except Exception:
            pass

        try:
            self.advanced_btn.configure(fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'))
        except Exception:
            pass

        # Update input widgets (entries / combos) to pick up input/background colors
        try:
            input_bg = theme.get_current_color('bg_input')
            input_text = theme.get_current_color('text_primary')
            border_col = theme.get_current_color('border')

            if hasattr(self, 'search_entry'):
                try:
                    self.search_entry.configure(fg_color=input_bg, text_color=input_text, border_color=border_col)
                except Exception:
                    pass
            if hasattr(self, 'min_range_combo'):
                try:
                    self.min_range_combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                except Exception:
                    pass
            if hasattr(self, 'level_combo'):
                try:
                    self.level_combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                except Exception:
                    pass
            if hasattr(self, 'class_combo'):
                try:
                    self.class_combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                except Exception:
                    pass
            # Advanced filter combos
            for combo_name in ('ritual_combo','conc_combo','verbal_combo','somatic_combo','material_combo','costly_combo',
                               'cast_time_combo','duration_combo','source_combo'):
                if hasattr(self, combo_name):
                    try:
                        combo = getattr(self, combo_name)
                        combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                    except Exception:
                        pass
        except Exception:
            pass

        # Notify subviews
        try:
            if hasattr(self, 'spell_lists_view'):
                self.spell_lists_view.update_paned_colors()
        except Exception:
            pass

        try:
            if hasattr(self, 'spell_detail'):
                # SpellDetailPanel provides its own description color updater
                self.spell_detail._update_description_colors()
        except Exception:
            pass
    
    def _update_context_menu_colors(self):
        """Update context menu colors based on current theme."""
        # Guard: context_menu may not be created yet when listener is registered
        if not hasattr(self, 'context_menu'):
            return
        theme = get_theme_manager()
        bg, fg, active_bg, active_fg = theme.get_menu_colors()
        self.context_menu.configure(
            bg=bg, fg=fg,
            activebackground=active_bg, activeforeground=active_fg,
            relief="flat", borderwidth=1
        )
    
    def _update_paned_colors(self):
        """Update PanedWindow sash colors based on current theme."""
        theme = get_theme_manager()
        self.main_paned.configure(bg=theme.get_current_color('pane_sash'))
    
    def _create_toolbar(self):
        """Create the toolbar with search, filters, and action buttons."""
        toolbar = ctk.CTkFrame(self.spells_view, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(15, 10))

        # Left side - Search and filters
        left_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_frame.pack(side="left", fill="x", expand=True)

        # Search entry
        search_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(search_frame, text="Search:", font=ctk.CTkFont(size=13)).pack(
            side="left", padx=(0, 8))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var,
                                         width=160, placeholder_text="Search spells...")
        self.search_entry.pack(side="left")

        # Level filter
        level_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        level_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(level_frame, text="Level:", font=ctk.CTkFont(size=13)).pack(
            side="left", padx=(0, 8))
        self.level_var = ctk.StringVar(value="All")
        level_options = ["All", "Cantrip"] + [str(i) for i in range(1, 10)]
        self.level_combo = ctk.CTkComboBox(level_frame, variable=self.level_var,
                                           values=level_options, width=90,
                                           command=lambda x: self._on_filter_changed(immediate=True))
        self.level_combo.pack(side="left")

        # Class filter
        class_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        class_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(class_frame, text="Class:", font=ctk.CTkFont(size=13)).pack(
            side="left", padx=(0, 8))
        self.class_var = ctk.StringVar(value="All")
        class_options = ["All"] + [c.value for c in CharacterClass.all_classes()]
        self.class_combo = ctk.CTkComboBox(class_frame, variable=self.class_var,
                                           values=class_options, width=110,
                                           command=lambda x: self._on_filter_changed(immediate=True))
        self.class_combo.pack(side="left")

        # Advanced filters toggle button
        theme = get_theme_manager()
        self.advanced_btn = ctk.CTkButton(
            left_frame, text="▼ Filters", width=90,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._toggle_advanced_filters
        )
        self.advanced_btn.pack(side="left")

        # Right side - Action buttons
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(btn_frame, text="+ New Spell", width=100,
                      text_color=theme.get_current_color('text_primary'),
                      command=self._on_new_spell).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="Import", width=70,
                      fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
                      text_color=theme.get_current_color('text_primary'),
                      command=self._on_import).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="Export All", width=80,
                      fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
                      text_color=theme.get_current_color('text_primary'),
                      command=self._on_export_all).pack(side="left")
    
    def _create_advanced_filters(self):
        """Create the collapsible advanced filters panel."""
        # Container frame (hidden by default)
        theme = get_theme_manager()
        self.advanced_frame = ctk.CTkFrame(self.spells_view, corner_radius=10)
        # Don't pack yet - will be shown/hidden by toggle
        
        # Inner content with padding
        content = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=15)
        
        # Row 1: Ritual, Concentration, Min Range
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))
        
        # Ritual filter
        ritual_frame = ctk.CTkFrame(row1, fg_color="transparent")
        ritual_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(ritual_frame, text="Ritual:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.ritual_var = ctk.StringVar(value="Any")
        self.ritual_combo = ctk.CTkComboBox(ritual_frame, variable=self.ritual_var,
                                            values=["Any", "Ritual Only", "Non-Ritual"],
                                            width=110, command=lambda x: self._on_filter_changed(immediate=True))
        self.ritual_combo.pack(side="left")
        
        # Concentration filter
        conc_frame = ctk.CTkFrame(row1, fg_color="transparent")
        conc_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(conc_frame, text="Concentration:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.conc_var = ctk.StringVar(value="Any")
        self.conc_combo = ctk.CTkComboBox(conc_frame, variable=self.conc_var,
                                          values=["Any", "Concentration", "Non-Concentration"],
                                          width=140, command=lambda x: self._on_filter_changed(immediate=True))
        self.conc_combo.pack(side="left")
        
        # Minimum Range
        range_frame = ctk.CTkFrame(row1, fg_color="transparent")
        range_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(range_frame, text="Min Range:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.min_range_var = ctk.StringVar(value="Self")
        self._range_display_to_value = {"Self": 0}  # Will be populated by _update_filter_dropdowns
        self.min_range_combo = ctk.CTkComboBox(range_frame, variable=self.min_range_var,
                                               values=["Self"],
                                               width=100, command=lambda x: self._on_filter_changed(immediate=True))
        self.min_range_combo.pack(side="left")
        
        # Get text_secondary color for later use
        text_secondary = theme.get_text_secondary()
        
        # Row 2: Component filters
        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(row2, text="Components:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 15))
        
        # Verbal filter
        self.verbal_var = ctk.StringVar(value="Any")
        self.verbal_combo = ctk.CTkComboBox(row2, variable=self.verbal_var,
                                            values=["Any", "Has V", "No V"],
                                            width=80, command=lambda x: self._on_filter_changed(immediate=True))
        self.verbal_combo.pack(side="left", padx=(0, 10))
        
        # Somatic filter
        self.somatic_var = ctk.StringVar(value="Any")
        self.somatic_combo = ctk.CTkComboBox(row2, variable=self.somatic_var,
                                             values=["Any", "Has S", "No S"],
                                             width=80, command=lambda x: self._on_filter_changed(immediate=True))
        self.somatic_combo.pack(side="left", padx=(0, 10))
        
        # Material filter
        self.material_var = ctk.StringVar(value="Any")
        self.material_combo = ctk.CTkComboBox(row2, variable=self.material_var,
                                              values=["Any", "Has M", "No M"],
                                              width=80, command=lambda x: self._on_filter_changed(immediate=True))
        self.material_combo.pack(side="left", padx=(0, 20))
        
        # Costly component filter
        self.costly_var = ctk.StringVar(value="Any")
        ctk.CTkLabel(row2, text="GP Cost:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.costly_combo = ctk.CTkComboBox(row2, variable=self.costly_var,
                                            values=["Any", "Has GP Cost", "No GP Cost"],
                                            width=120, command=lambda x: self._on_filter_changed(immediate=True))
        self.costly_combo.pack(side="left")
        
        # Row 3: Casting Time, Duration, Source
        row3 = ctk.CTkFrame(content, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 12))
        
        # Casting Time filter
        cast_frame = ctk.CTkFrame(row3, fg_color="transparent")
        cast_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(cast_frame, text="Casting Time:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.cast_time_var = ctk.StringVar(value="Any")
        self.cast_time_combo = ctk.CTkComboBox(cast_frame, variable=self.cast_time_var,
                                                values=["Any"], width=120,
                                                command=lambda x: self._on_filter_changed(immediate=True))
        self.cast_time_combo.pack(side="left")
        
        # Duration filter
        dur_frame = ctk.CTkFrame(row3, fg_color="transparent")
        dur_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(dur_frame, text="Duration:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.duration_var = ctk.StringVar(value="Any")
        self.duration_combo = ctk.CTkComboBox(dur_frame, variable=self.duration_var,
                                               values=["Any"], width=130,
                                               command=lambda x: self._on_filter_changed(immediate=True))
        self.duration_combo.pack(side="left")
        
        # Source filter
        source_frame = ctk.CTkFrame(row3, fg_color="transparent")
        source_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(source_frame, text="Source:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.source_var = ctk.StringVar(value="Any")
        self.source_combo = ctk.CTkComboBox(source_frame, variable=self.source_var,
                                             values=["Any"], width=150,
                                             command=lambda x: self._on_filter_changed(immediate=True))
        self.source_combo.pack(side="left")
        
        # Row 4: Tags filter and Clear button
        row4 = ctk.CTkFrame(content, fg_color="transparent")
        row4.pack(fill="x")
        
        # Tags filter
        tags_frame = ctk.CTkFrame(row4, fg_color="transparent")
        tags_frame.pack(side="left")
        ctk.CTkLabel(tags_frame, text="Tags:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 8))
        
        self.tags_btn = ctk.CTkButton(
            tags_frame, text="Select Tags...", width=120,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            command=self._open_tag_filter
        )
        self.tags_btn.pack(side="left", padx=(0, 10))
        
        self.tags_label = ctk.CTkLabel(
            tags_frame, text="None selected",
            font=ctk.CTkFont(size=11),
            text_color=text_secondary
        )
        self.tags_label.pack(side="left")
        
        # Clear filters button (use themed danger color)
        theme = get_theme_manager()
        danger = theme.get_current_color('button_danger')
        danger_hover = theme.get_current_color('button_danger_hover')
        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(row4, text="Clear All Filters", width=120,
                      fg_color=danger, hover_color=danger_hover,
                      text_color=btn_text,
                      command=self._clear_advanced_filters).pack(side="right")

        # Update dropdown values
        self._update_filter_dropdowns()
    
    def _open_tag_filter(self):
        """Open the tag filter dialog."""
        available_tags = self.spell_manager.get_all_tags()
        dialog = TagFilterDialog(
            self.winfo_toplevel(),
            available_tags,
            self._selected_tags,
            self._tag_filter_mode
        )
        self.wait_window(dialog)
        
        self._selected_tags = dialog.result
        self._tag_filter_mode = dialog.result_mode
        self._update_tags_label()
        self._on_filter_changed(immediate=True)
    
    def _update_tags_label(self):
        """Update the tags label with selected tag count and mode."""
        count = len(self._selected_tags)
        mode_labels = {
            TagFilterMode.HAS_ALL: "all",
            TagFilterMode.HAS_ANY: "any",
            TagFilterMode.HAS_NONE: "none"
        }
        mode_str = mode_labels.get(self._tag_filter_mode, "")
        
        if count == 0:
            self.tags_label.configure(text="None selected")
        elif count == 1:
            self.tags_label.configure(text=f"1 tag ({mode_str}): {self._selected_tags[0]}")
        else:
            self.tags_label.configure(text=f"{count} tags ({mode_str})")
    
    def _toggle_advanced_filters(self):
        """Toggle the advanced filters panel visibility."""
        self._advanced_expanded = not self._advanced_expanded
        
        if self._advanced_expanded:
            self.advanced_btn.configure(text="▲ Filters")
            self.advanced_frame.pack(fill="x", padx=15, pady=(0, 10), before=self._main_content)
            self._update_filter_dropdowns()
        else:
            self.advanced_btn.configure(text="▼ Filters")
            self.advanced_frame.pack_forget()
    
    def _update_filter_dropdowns(self):
        """Update the casting time, duration, and source dropdowns with current values."""
        # Preserve current selections
        current_cast_time = self.cast_time_var.get()
        current_duration = self.duration_var.get()
        current_source = self.source_var.get()
        current_min_range = self.min_range_var.get()
        
        # Casting times
        cast_times = ["Any"] + self.spell_manager.get_all_casting_times()
        self.cast_time_combo.configure(values=cast_times)
        # Restore selection if still valid, otherwise reset to "Any"
        if current_cast_time in cast_times:
            self.cast_time_var.set(current_cast_time)
        else:
            self.cast_time_var.set("Any")
        
        # Durations
        durations = ["Any"] + self.spell_manager.get_all_durations()
        self.duration_combo.configure(values=durations)
        if current_duration in durations:
            self.duration_var.set(current_duration)
        else:
            self.duration_var.set("Any")
        
        # Sources
        sources = ["Any"] + self.spell_manager.get_all_sources()
        self.source_combo.configure(values=sources)
        if current_source in sources:
            self.source_var.set(current_source)
        else:
            self.source_var.set("Any")
        
        # Range values
        ranges = self.spell_manager.get_all_ranges_for_display()
        self._range_display_to_value = {label: value for value, label in ranges}
        range_labels = [label for _, label in ranges]
        self.min_range_combo.configure(values=range_labels)
        if current_min_range in range_labels:
            self.min_range_var.set(current_min_range)
        else:
            self.min_range_var.set("Self")
    
    def _clear_advanced_filters(self):
        """Reset all advanced filters to their default values."""
        self.ritual_var.set("Any")
        self.conc_var.set("Any")
        self.min_range_var.set("Self")
        self.verbal_var.set("Any")
        self.somatic_var.set("Any")
        self.material_var.set("Any")
        self.costly_var.set("Any")
        self.cast_time_var.set("Any")
        self.duration_var.set("Any")
        self.source_var.set("Any")
        self._selected_tags = []
        self._tag_filter_mode = TagFilterMode.HAS_ALL
        self._update_tags_label()
        self._on_filter_changed(immediate=True)
    
    def _create_main_content(self):
        """Create the main content area with resizable two-panel layout."""
        # Main content frame
        self._main_content = ctk.CTkFrame(self.spells_view, fg_color="transparent")
        self._main_content.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Create a PanedWindow for resizable panels
        # opaqueresize=False for smooth dragging (shows ghost line, resizes on release)
        self.main_paned = tk.PanedWindow(
            self._main_content,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            handlesize=0,
            opaqueresize=False,
            sashcursor="sb_h_double_arrow"
        )
        # Set initial color based on current theme
        self._update_paned_colors()
        self.main_paned.pack(fill="both", expand=True)
        
        # Left panel container (for spell list or compare panel)
        self.left_container = ctk.CTkFrame(self.main_paned, fg_color="transparent")
        
        # Left panel - Spell list
        from ui.spell_list import SpellListPanel
        self.spell_list = SpellListPanel(
            self.left_container, 
            self._on_spell_selected,
            on_right_click=self._on_spell_right_click
        )
        self.spell_list.pack(fill="both", expand=True)
        
        # Right panel - Spell detail
        from ui.spell_detail import SpellDetailPanel
        self.spell_detail = SpellDetailPanel(
            self.main_paned, 
            on_edit=self._on_edit_spell,
            on_delete=self._on_delete_spell,
            on_export=self._on_export_spell,
            on_add_to_list=self._on_add_to_list,
            character_manager=self.character_manager,
            spell_manager=self.spell_manager
        )
        
        # Add panes with minimum sizes
        self.main_paned.add(self.left_container, minsize=280, stretch="always")
        self.main_paned.add(self.spell_detail, minsize=400, stretch="always")
        
        # Set initial sash position (roughly 1:2 ratio)
        self.after(100, lambda: self.main_paned.sash_place(0, 320, 0))
        
        # Compare panel (created but not shown initially)
        self._create_compare_panel()
    
    def _create_compare_panel(self):
        """Create the compare spell panel (hidden initially)."""
        from ui.spell_detail import SpellDetailPanel
        
        # Container frame that will replace the spell list when comparing
        self.compare_container = ctk.CTkFrame(self.left_container, corner_radius=10)
        
        # Header with close button
        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text="Compare Spell",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")
        
        theme = get_theme_manager()
        close_btn = ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color=theme.get_current_color('button_danger'), hover_color=theme.get_current_color('button_danger_hover'),
            command=self._close_compare_panel
        )
        close_btn.pack(side="right")
        
        # The detail panel for comparing
        self.compare_detail = SpellDetailPanel(
            self.compare_container,
            on_edit=self._on_edit_spell,
            on_delete=self._on_delete_spell,
            on_export=self._on_export_spell,
            on_add_to_list=self._on_add_to_list,
            character_manager=self.character_manager,
            spell_manager=self.spell_manager
        )
        self.compare_detail.pack(fill="both", expand=True)
    
    def _create_context_menu(self):
        """Create the right-click context menu for spells."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self._update_context_menu_colors()
        self.context_menu.add_command(
            label="Add to Spell List",
            command=self._context_add_to_list
        )
        self.context_menu.add_command(
            label="View and Compare",
            command=self._context_view_compare
        )
        
        # Store reference to the spell being acted on
        self._context_spell: Optional[Spell] = None
    
    def _on_spell_right_click(self, spell: Spell, x: int, y: int):
        """Handle right-click on a spell in the list."""
        self._context_spell = spell
        try:
            self.context_menu.tk_popup(x, y)
        finally:
            self.context_menu.grab_release()
    
    def _context_add_to_list(self):
        """Context menu: Add spell to a character's list."""
        if self._context_spell and self.character_manager:
            from ui.spell_detail import AddToListDialog, SpellWarningDialog
            from spell_slots import get_max_cantrips, get_max_spell_level, get_character_classes
            
            characters = self.character_manager.characters
            dialog = AddToListDialog(
                self.winfo_toplevel(),
                self._context_spell.name,
                characters
            )
            self.wait_window(dialog)
            
            if dialog.result:
                # Get the selected character
                character = self.character_manager.get_character(dialog.result)
                if character:
                    # Check for warnings
                    warnings = self._validate_spell_for_character(
                        self._context_spell, character
                    )
                    
                    if warnings:
                        # Show warning dialog
                        warning_dialog = SpellWarningDialog(
                            self.winfo_toplevel(),
                            self._context_spell.name,
                            warnings
                        )
                        self.wait_window(warning_dialog)
                        
                        if not warning_dialog.result:
                            return  # User cancelled
                    
                    # Add the spell
                    self._on_add_to_list(self._context_spell, dialog.result)
    
    def _validate_spell_for_character(self, spell: Spell, character) -> List[str]:
        """Validate if a spell is appropriate for a character.
        Respects settings for which warnings to show.
        """
        # Use shared validation utility with settings filtering
        return validate_spell_for_character(
            spell, character,
            spell_manager=self.spell_manager,
            settings=self.settings_manager.settings
        )
    
    def _context_view_compare(self):
        """Context menu: View and compare spell."""
        if self._context_spell:
            # Check if the primary detail panel has a spell
            primary_spell = self.spell_detail._current_spell
            
            if primary_spell is None:
                # No spell in primary panel - open there instead
                self.spell_list.select_spell(self._context_spell.name)
            else:
                # Show compare panel
                self._show_compare_panel(self._context_spell)
    
    def _show_compare_panel(self, spell: Spell):
        """Show the compare panel with the given spell."""
        self._compare_mode = True
        self._compare_spell = spell
        
        # Hide spell list, show compare panel
        self.spell_list.pack_forget()
        self.compare_container.pack(fill="both", expand=True)
        
        # Set the spell in compare panel
        self.compare_detail.set_spell(spell)
        
        # Apply comparison coloring to both panels (if enabled in settings)
        if self.settings_manager.settings.show_comparison_highlights:
            primary_spell = self.spell_detail._current_spell
            if primary_spell:
                # Primary panel compares against compare spell
                self.spell_detail.apply_comparison(spell, is_primary=True)
                # Compare panel compares against primary spell
                self.compare_detail.apply_comparison(primary_spell, is_primary=False)
    
    def _close_compare_panel(self):
        """Close the compare panel and return to spell list."""
        self._compare_mode = False
        self._compare_spell = None
        
        # Clear comparison coloring from primary panel
        self.spell_detail.clear_comparison()
        
        # Clear comparison from compare panel
        self.compare_detail.clear_comparison()
        
        # Hide compare panel, show spell list
        self.compare_container.pack_forget()
        self.spell_list.pack(fill="both", expand=True)
    
    def _get_current_filters(self):
        """Get current filter values including advanced filters."""
        search_text = self.search_var.get()
        
        # Level filter
        level_str = self.level_var.get()
        if level_str == "All":
            level_filter = -1
        elif level_str == "Cantrip":
            level_filter = 0
        else:
            level_filter = int(level_str)
        
        # Class filter
        class_str = self.class_var.get()
        if class_str == "All":
            class_filter = None
        else:
            class_filter = CharacterClass.from_string(class_str)
        
        # Build advanced filters
        advanced = AdvancedFilters()
        
        # Ritual filter
        ritual_val = self.ritual_var.get()
        if ritual_val == "Ritual Only":
            advanced.ritual_filter = True
        elif ritual_val == "Non-Ritual":
            advanced.ritual_filter = False
        
        # Concentration filter
        conc_val = self.conc_var.get()
        if conc_val == "Concentration":
            advanced.concentration_filter = True
        elif conc_val == "Non-Concentration":
            advanced.concentration_filter = False
        
        # Minimum range - look up the selected display label to get the actual value
        range_label = self.min_range_var.get()
        if range_label in self._range_display_to_value:
            advanced.min_range = self._range_display_to_value[range_label]
        else:
            advanced.min_range = 0  # Default to Self
        
        # Component filters
        verbal_val = self.verbal_var.get()
        if verbal_val == "Has V":
            advanced.has_verbal = True
        elif verbal_val == "No V":
            advanced.has_verbal = False
        
        somatic_val = self.somatic_var.get()
        if somatic_val == "Has S":
            advanced.has_somatic = True
        elif somatic_val == "No S":
            advanced.has_somatic = False
        
        material_val = self.material_var.get()
        if material_val == "Has M":
            advanced.has_material = True
        elif material_val == "No M":
            advanced.has_material = False
        
        # Costly component filter
        costly_val = self.costly_var.get()
        if costly_val == "Has GP Cost":
            advanced.costly_component = True
        elif costly_val == "No GP Cost":
            advanced.costly_component = False
        
        # Casting time filter
        cast_time_val = self.cast_time_var.get()
        if cast_time_val != "Any":
            advanced.casting_time_filter = cast_time_val
        
        # Duration filter
        duration_val = self.duration_var.get()
        if duration_val != "Any":
            advanced.duration_filter = duration_val
        
        # Source filter
        source_val = self.source_var.get()
        if source_val != "Any":
            advanced.source_filter = source_val
        
        # Tags filter
        advanced.tags_filter = self._selected_tags.copy()
        advanced.tags_filter_mode = self._tag_filter_mode
        
        return search_text, level_filter, class_filter, advanced
    
    def _refresh_spell_list(self, reset_scroll: bool = True):
        """Refresh the spell list with current filters.
        
        Args:
            reset_scroll: If True, scroll position resets to top (default True)
        """
        search_text, level_filter, class_filter, advanced = self._get_current_filters()
        filtered_spells = self.spell_manager.get_filtered_spells(
            search_text, level_filter, class_filter, advanced
        )
        self.spell_list.set_spells(filtered_spells, reset_scroll=reset_scroll)
    
    def _on_filter_changed(self, immediate: bool = False):
        """Called when any filter value changes.
        Uses debouncing to avoid excessive database queries during typing.
        
        Args:
            immediate: If True, apply filters immediately without debouncing
        """
        # Cancel any pending debounced call
        if self._filter_debounce_id is not None:
            self.after_cancel(self._filter_debounce_id)
            self._filter_debounce_id = None
        
        if immediate:
            # Apply immediately (for dropdown selections, etc.)
            self._refresh_spell_list()
        else:
            # Debounce text input to avoid excessive queries
            self._filter_debounce_id = self.after(
                self._filter_debounce_delay,
                self._apply_debounced_filter
            )
    
    def _apply_debounced_filter(self):
        """Apply the filter after debounce delay."""
        self._filter_debounce_id = None
        self._refresh_spell_list()
    
    def _on_spells_changed(self):
        """Called when the spell collection changes."""
        self._update_filter_dropdowns()
        self._refresh_spell_list()
    
    def _on_spell_selected(self, spell):
        """Called when a spell is selected in the list."""
        self.spell_detail.set_spell(spell)
        
        # If in compare mode, update comparison (if enabled in settings)
        if self._compare_mode and self._compare_spell and spell:
            if self.settings_manager.settings.show_comparison_highlights:
                self.spell_detail.apply_comparison(self._compare_spell, is_primary=True)
                self.compare_detail.apply_comparison(spell, is_primary=False)
    
    def _on_new_spell(self):
        """Open dialog to create a new spell."""
        from ui.spell_editor import SpellEditorDialog
        dialog = SpellEditorDialog(self.winfo_toplevel(), "New Spell")
        self.wait_window(dialog)
        
        if dialog.result:
            if self.spell_manager.add_spell(dialog.result):
                self.spell_list.select_spell(dialog.result.name)
            else:
                messagebox.showerror("Error", 
                    f"A spell named '{dialog.result.name}' already exists.")
    
    def _on_edit_spell(self, spell):
        """Open dialog to edit an existing spell."""
        from ui.spell_editor import SpellEditorDialog
        dialog = SpellEditorDialog(self.winfo_toplevel(), "Edit Spell", spell)
        self.wait_window(dialog)
        
        if dialog.result:
            if self.spell_manager.update_spell(spell.name, dialog.result):
                self.spell_list.select_spell(dialog.result.name)
            else:
                messagebox.showerror("Error", 
                    f"A spell named '{dialog.result.name}' already exists.")
    
    def _on_delete_spell(self, spell):
        """Delete the selected spell."""
        # Check if deletion of official spells is allowed
        if spell.is_official and not self.settings_manager.settings.allow_delete_official_spells:
            messagebox.showwarning(
                "Cannot Delete Official Spell",
                f"'{spell.name}' is an official spell and cannot be deleted.\n\n"
                "You can enable deletion of official spells in Settings if needed."
            )
            return
        
        if messagebox.askyesno("Confirm Delete", 
                               f"Are you sure you want to delete '{spell.name}'?"):
            self.spell_manager.delete_spell(spell.name)
            self.spell_detail.set_spell(None)
    
    def _on_export_spell(self, spell):
        """Export a single spell to a file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{spell.name.replace(' ', '_')}.txt"
        )
        
        if file_path:
            if self.spell_manager.export_spells(file_path, [spell]):
                messagebox.showinfo("Success", f"Spell exported to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export spell.")
    
    def _on_add_to_list(self, spell, character_name: str):
        """Add a spell to a character's known spells."""
        if self.character_manager.add_spell_to_character(character_name, spell.name):
            if self.settings_manager.settings.show_spell_added_notification:
                messagebox.showinfo("Success", 
                    f"'{spell.name}' added to {character_name}'s spell list.")
        else:
            # Always show if already exists (this is a different type of feedback)
            messagebox.showinfo("Info", 
                f"'{spell.name}' is already in {character_name}'s spell list.")
    
    def _on_import(self):
        """Import spells from a file."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            # Ask whether to merge or replace
            result = messagebox.askyesnocancel(
                "Import Options",
                "Do you want to replace all existing spells?\n\n"
                "Yes = Replace all spells\n"
                "No = Merge (add new spells only)\n"
                "Cancel = Abort import"
            )
            
            if result is not None:  # Not cancelled
                count = self.spell_manager.import_spells(file_path, replace=result)
                messagebox.showinfo("Import Complete", 
                    f"Imported {count} spell(s).")
    
    def _on_export_all(self):
        """Export all spells to a file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="spells_export.txt"
        )
        
        if file_path:
            if self.spell_manager.export_spells(file_path):
                messagebox.showinfo("Success", 
                    f"Exported {len(self.spell_manager.spells)} spell(s) to {file_path}")
            else:
                messagebox.showerror("Error", "Failed to export spells.")
