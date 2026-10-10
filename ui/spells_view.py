"""
Spells page: the spell browser (search, filters, list, detail panel, compare panel).

Every tab that opens the Spells collection gets its own SpellsView, so tabs keep their
own search text, filters, selection and scroll position.
"""

import customtkinter as ctk
from typography import ui_font
import tkinter as tk
from tkinter import messagebox, filedialog
from typing import Callable, List, Optional
from spell import Spell, CharacterClass, AdvancedFilters, TagFilterMode, SourceFilterMode
from validation import validate_spell_for_character
from theme import get_theme_manager
from ui.filter_widgets import TagFilterDialog, SourceFilterDialog


class SpellsView(ctk.CTkFrame):
    """The spell browser for one tab."""

    def __init__(self, parent, spell_manager, character_manager, settings_manager,
                 on_back: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")

        self.spell_manager = spell_manager
        self.character_manager = character_manager
        self.settings_manager = settings_manager
        self.on_back = on_back  # the toolbar's back button (to the Collections page)

        # State
        self._advanced_expanded = False
        self._selected_tags: List[str] = []
        self._tag_filter_mode: TagFilterMode = TagFilterMode.HAS_ALL
        self._selected_sources: List[str] = []
        self._source_filter_mode: SourceFilterMode = SourceFilterMode.INCLUDE
        self._compare_mode = False  # Whether compare panel is shown
        self._compare_spell: Optional[Spell] = None  # Spell in compare panel
        self._filter_debounce_id: Optional[str] = None  # For debouncing filter changes
        self._filter_debounce_delay = 200  # Milliseconds to wait before applying filters

        self._create_toolbar()
        self._create_advanced_filters()
        self._create_main_content()
        self._create_context_menu()

        # Follow changes to the spell collection
        self.spell_manager.add_listener(self._on_spells_changed)
        self._refresh_spell_list()

    def _go_back(self):
        if self.on_back:
            self.on_back()

    def select_spell(self, name: str):
        """Select a spell in the list (for navigation from elsewhere)."""
        self.spell_list.select_spell(name, self.spell_manager.version_catalog.find(name))

    def reload(self):
        """Pick up freshly imported content."""
        self.refresh_class_filter()
        self._refresh_spell_list()

    def apply_theme(self):
        """Repaint the parts that do not recolour themselves (called when the theme changes)."""
        theme = get_theme_manager()
        self._update_context_menu_colors()
        self._update_paned_colors()

        try:
            self.advanced_btn.configure(fg_color=theme.get_current_color('button_normal'),
                                        hover_color=theme.get_current_color('button_hover'))
        except Exception:
            pass

        # These "card" panels are created with an explicit fg_color (not
        # "transparent"), so they need to be repainted explicitly too.
        card_bg = theme.get_current_color('bg_secondary')
        for attr in ('advanced_frame', 'compare_container'):
            try:
                getattr(self, attr).configure(fg_color=card_bg)
            except Exception:
                pass

        # Update input widgets (entries / combos) to pick up input/background colors
        input_bg = theme.get_current_color('bg_input')
        input_text = theme.get_current_color('text_primary')
        border_col = theme.get_current_color('border')
        try:
            self.search_entry.configure(fg_color=input_bg, text_color=input_text, border_color=border_col)
        except Exception:
            pass
        for combo_name in ('min_range_combo', 'level_combo', 'class_combo',
                           'ritual_combo', 'conc_combo', 'verbal_combo', 'somatic_combo',
                           'material_combo', 'costly_combo', 'cast_time_combo', 'duration_combo',
                           'source_combo'):
            combo = getattr(self, combo_name, None)
            if combo is not None:
                try:
                    combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                except Exception:
                    pass

        # SpellDetailPanel provides its own description color updater
        for attr in ('spell_detail', 'compare_detail'):
            try:
                getattr(self, attr)._update_description_colors()
            except Exception:
                pass

    def destroy(self):
        try:
            self.spell_manager.remove_listener(self._on_spells_changed)
        except Exception:
            pass
        if self._filter_debounce_id is not None:
            try:
                self.after_cancel(self._filter_debounce_id)
            except Exception:
                pass
            self._filter_debounce_id = None
        super().destroy()

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
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(15, 10))

        # Left side - Back button, Search and filters
        left_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_frame.pack(side="left", fill="x", expand=True)
        
        # Back to Collections button
        theme = get_theme_manager()
        ctk.CTkButton(
            left_frame, text="← Collections", width=110,
            fg_color=theme.get_current_color('button_normal'), 
            hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._go_back
        ).pack(side="left", padx=(0, 15))

        # Search entry
        search_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(search_frame, text="Search:", font=ui_font("body", 13)).pack(
            side="left", padx=(0, 8))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var,
                                         width=160, placeholder_text="Search spells...")
        self.search_entry.pack(side="left")

        # Level filter
        level_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        level_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(level_frame, text="Level:", font=ui_font("body", 13)).pack(
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

        ctk.CTkLabel(class_frame, text="Class:", font=ui_font("body", 13)).pack(
            side="left", padx=(0, 8))
        self.class_var = ctk.StringVar(value="All")
        class_options = ["All"] + CharacterClass.spellcasting_class_names()
        self.class_combo = ctk.CTkComboBox(class_frame, variable=self.class_var,
                                           values=class_options, width=110,
                                           command=lambda x: self._on_filter_changed(immediate=True))
        self.class_combo.pack(side="left")

        # Advanced filters toggle button
        self.advanced_btn = ctk.CTkButton(
            left_frame, text="▼ Filters", width=90,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._toggle_advanced_filters
        )
        self.advanced_btn.pack(side="left")

        # Right side - New Spell button only
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(btn_frame, text="+ New Spell", width=100,
                      text_color=theme.get_current_color('text_primary'),
                      command=self._on_new_spell).pack(side="left")
    
    def _create_advanced_filters(self):
        """Create the collapsible advanced filters panel."""
        # Container frame (hidden by default)
        theme = get_theme_manager()
        self.advanced_frame = ctk.CTkFrame(self, corner_radius=10,
                                            fg_color=theme.get_current_color('bg_secondary'))
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
        ctk.CTkLabel(ritual_frame, text="Ritual:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.ritual_var = ctk.StringVar(value="Any")
        self.ritual_combo = ctk.CTkComboBox(ritual_frame, variable=self.ritual_var,
                                            values=["Any", "Ritual Only", "Non-Ritual"],
                                            width=110, command=lambda x: self._on_filter_changed(immediate=True))
        self.ritual_combo.pack(side="left")
        
        # Concentration filter
        conc_frame = ctk.CTkFrame(row1, fg_color="transparent")
        conc_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(conc_frame, text="Concentration:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.conc_var = ctk.StringVar(value="Any")
        self.conc_combo = ctk.CTkComboBox(conc_frame, variable=self.conc_var,
                                          values=["Any", "Concentration", "Non-Concentration"],
                                          width=140, command=lambda x: self._on_filter_changed(immediate=True))
        self.conc_combo.pack(side="left")
        
        # Minimum Range
        range_frame = ctk.CTkFrame(row1, fg_color="transparent")
        range_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(range_frame, text="Min Range:", font=ui_font("body")).pack(side="left", padx=(0, 8))
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
        
        ctk.CTkLabel(row2, text="Components:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 15))
        
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
        ctk.CTkLabel(row2, text="GP Cost:", font=ui_font("body")).pack(side="left", padx=(0, 8))
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
        ctk.CTkLabel(cast_frame, text="Casting Time:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.cast_time_var = ctk.StringVar(value="Any")
        self.cast_time_combo = ctk.CTkComboBox(cast_frame, variable=self.cast_time_var,
                                                values=["Any"], width=120,
                                                command=lambda x: self._on_filter_changed(immediate=True))
        self.cast_time_combo.pack(side="left")
        
        # Duration filter
        dur_frame = ctk.CTkFrame(row3, fg_color="transparent")
        dur_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(dur_frame, text="Duration:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.duration_var = ctk.StringVar(value="Any")
        self.duration_combo = ctk.CTkComboBox(dur_frame, variable=self.duration_var,
                                               values=["Any"], width=130,
                                               command=lambda x: self._on_filter_changed(immediate=True))
        self.duration_combo.pack(side="left")
        
        # Source filter (button opens multi-select dialog)
        source_frame = ctk.CTkFrame(row3, fg_color="transparent")
        source_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(source_frame, text="Source:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 8))
        
        self.source_btn = ctk.CTkButton(
            source_frame, text="Select Sources...", width=130,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            command=self._open_source_filter
        )
        self.source_btn.pack(side="left", padx=(0, 10))
        
        self.source_label = ctk.CTkLabel(
            source_frame, text="None selected",
            font=ui_font("small"),
            text_color=text_secondary
        )
        self.source_label.pack(side="left")
        
        # Row 4: Tags filter and Clear button
        row4 = ctk.CTkFrame(content, fg_color="transparent")
        row4.pack(fill="x")
        
        # Tags filter
        tags_frame = ctk.CTkFrame(row4, fg_color="transparent")
        tags_frame.pack(side="left")
        ctk.CTkLabel(tags_frame, text="Tags:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 8))
        
        self.tags_btn = ctk.CTkButton(
            tags_frame, text="Select Tags...", width=120,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            command=self._open_tag_filter
        )
        self.tags_btn.pack(side="left", padx=(0, 10))
        
        self.tags_label = ctk.CTkLabel(
            tags_frame, text="None selected",
            font=ui_font("small"),
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
    
    def _open_source_filter(self):
        """Open the source filter dialog."""
        available_sources = self.spell_manager.get_all_sources()
        dialog = SourceFilterDialog(
            self.winfo_toplevel(),
            available_sources,
            self._selected_sources,
            self._source_filter_mode
        )
        self.wait_window(dialog)
        
        self._selected_sources = dialog.result
        self._source_filter_mode = dialog.result_mode
        self._update_source_label()
        self._on_filter_changed(immediate=True)
    
    def _update_source_label(self):
        """Update the source label with selected source count and mode."""
        count = len(self._selected_sources)
        mode_labels = {
            SourceFilterMode.INCLUDE: "include",
            SourceFilterMode.EXCLUDE: "exclude"
        }
        mode_str = mode_labels.get(self._source_filter_mode, "")
        
        if count == 0:
            self.source_label.configure(text="None selected")
        elif count == 1:
            self.source_label.configure(text=f"1 source ({mode_str}): {self._selected_sources[0]}")
        else:
            self.source_label.configure(text=f"{count} sources ({mode_str})")
    
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
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._update_source_label()
        self._selected_tags = []
        self._tag_filter_mode = TagFilterMode.HAS_ALL
        self._update_tags_label()
        self._on_filter_changed(immediate=True)
    
    def _create_main_content(self):
        """Create the main content area with resizable two-panel layout."""
        # Main content frame
        self._main_content = ctk.CTkFrame(self, fg_color="transparent")
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
            spell_manager=self.spell_manager,
            on_restore=self._on_restore_spell
        )
        # Picking another version in the Source drop-down makes it the list's selected spell
        self.spell_detail.on_version_change = self.spell_list.replace_selected
        
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
        theme = get_theme_manager()

        # Container frame that will replace the spell list when comparing
        self.compare_container = ctk.CTkFrame(self.left_container, corner_radius=10,
                                               fg_color=theme.get_current_color('bg_secondary'))
        
        # Header with close button
        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text="Compare Spell",
            font=ui_font("subheading", bold=True)
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
        
        # Class filter - use class name string directly (for custom class support)
        class_str = self.class_var.get()
        class_name_filter = "" if class_str == "All" else class_str
        
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
        
        # Source filter (multi-select)
        advanced.source_filter = self._selected_sources.copy()
        advanced.source_filter_mode = self._source_filter_mode
        
        # Tags filter
        advanced.tags_filter = self._selected_tags.copy()
        advanced.tags_filter_mode = self._tag_filter_mode
        
        return search_text, level_filter, class_name_filter, advanced
    
    def _refresh_spell_list(self, reset_scroll: bool = True):
        """Refresh the spell list with current filters.
        
        Args:
            reset_scroll: If True, scroll position resets to top (default True)
        """
        search_text, level_filter, class_name_filter, advanced = self._get_current_filters()
        legacy_filter = self.settings_manager.settings.legacy_content_filter
        filtered_spells = self.spell_manager.get_filtered_spells(
            search_text, level_filter, class_name_filter, advanced, legacy_filter,
            collapse_versions=True  # one row per spell; its versions are in the detail panel's Source drop-down
        )
        self.spell_list.set_spells(filtered_spells, reset_scroll=reset_scroll)
    
    def _on_filter_changed(self, immediate: bool = False):
        """Called when any filter value changes.
        Uses debouncing to avoid excessive database queries during typing.
        
        Args:
            immediate: If True, apply filters with minimal delay (for dropdowns)
        """
        # Cancel any pending debounced call
        if self._filter_debounce_id is not None:
            self.after_cancel(self._filter_debounce_id)
            self._filter_debounce_id = None
        
        if immediate:
            # Apply with minimal delay to allow UI to update first
            self._filter_debounce_id = self.after(10, self._apply_debounced_filter)
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
    
    def refresh_class_filter(self):
        """Refresh the class filter dropdown to include newly imported custom classes."""
        if hasattr(self, 'class_combo'):
            current_value = self.class_var.get()
            class_options = ["All"] + CharacterClass.spellcasting_class_names()
            self.class_combo.configure(values=class_options)
            # Preserve current selection if still valid
            if current_value not in class_options:
                self.class_var.set("All")

    def _on_spells_changed(self):
        """Called when the spell collection changes."""
        self._update_filter_dropdowns()
        self._refresh_spell_list()
    
    def _on_spell_selected(self, spell):
        """Called when a spell is selected in the list."""
        versions = None
        if spell:
            setting = self.settings_manager.settings.legacy_content_filter
            versions = self.spell_manager.version_catalog.options(spell, setting)
        self.spell_detail.set_spell(spell, versions)
        
        # If in compare mode, update comparison (if enabled in settings)
        if self._compare_mode and self._compare_spell and spell:
            if self.settings_manager.settings.show_comparison_highlights:
                self.spell_detail.apply_comparison(self._compare_spell, is_primary=True)
                self.compare_detail.apply_comparison(spell, is_primary=False)
    
    def _on_new_spell(self):
        """Open dialog to create a new spell (manual entry or auto-detect from text)."""
        from ui.spell_editor import SpellEditorDialog
        from ui.spell_text_import import AddSpellSourceDialog

        source_dialog = AddSpellSourceDialog(self.winfo_toplevel())
        self.wait_window(source_dialog)
        if source_dialog.result is None:
            return
        if source_dialog.result == "auto":
            self._on_new_spell_from_text()
            return

        dialog = SpellEditorDialog(self.winfo_toplevel(), "New Spell", spell_manager=self.spell_manager)
        self.wait_window(dialog)

        if dialog.result:
            if self.spell_manager.add_spell(dialog.result):
                self.spell_list.select_spell(dialog.result.name)
            else:
                messagebox.showerror("Error",
                    f"A spell named '{dialog.result.name}' already exists.")

    def _on_new_spell_from_text(self):
        """Paste a block of text, auto-detect spell fields, and review each draft."""
        from ui.spell_editor import SpellEditorDialog
        from ui.spell_text_import import SpellTextImportDialog

        import_dialog = SpellTextImportDialog(self.winfo_toplevel())
        self.wait_window(import_dialog)
        parsed_list = import_dialog.result
        if not parsed_list:
            return

        try:
            from text_import.spell_parser import to_spell
        except Exception as exc:
            messagebox.showerror("Auto-Detect Unavailable",
                                 f"Could not load the text importer:\n{exc}")
            return

        added = []
        total = len(parsed_list)
        for idx, parsed in enumerate(parsed_list, 1):
            try:
                draft = to_spell(parsed)
            except Exception as exc:
                messagebox.showerror("Parse Error",
                                     f"Could not build spell {idx} of {total}:\n{exc}")
                continue

            review = sorted(set(parsed.needs_review()) | set(parsed.uncertain_fields()))
            progress = f"{idx} of {total}" if total > 1 else ""

            editor = SpellEditorDialog(
                self.winfo_toplevel(),
                f"Review Spell: {draft.name or 'Untitled'}",
                spell_manager=self.spell_manager,
                prefill_spell=draft, review_fields=review, batch_progress=progress,
            )
            self.wait_window(editor)

            if editor.result:
                if self.spell_manager.add_spell(editor.result):
                    added.append(editor.result.name)
                else:
                    messagebox.showerror(
                        "Error",
                        f"A spell named '{editor.result.name}' already exists. "
                        "It was not added.")
            elif idx < total:
                if not messagebox.askyesno(
                        "Continue?",
                        "Skip this spell and continue reviewing the remaining "
                        f"{total - idx} spell(s)?"):
                    break

        if added:
            self.spell_list.select_spell(added[-1])
            if len(added) > 1:
                messagebox.showinfo("Spells Added",
                                    f"Added {len(added)} spells:\n" + "\n".join(added))


    def _on_edit_spell(self, spell):
        """Open dialog to edit an existing spell."""
        from ui.spell_editor import SpellEditorDialog
        dialog = SpellEditorDialog(self.winfo_toplevel(), "Edit Spell", spell, spell_manager=self.spell_manager)
        self.wait_window(dialog)
        
        if dialog.result:
            if self.spell_manager.update_spell(spell.name, dialog.result):
                self.spell_list.select_spell(dialog.result.name)
            else:
                messagebox.showerror("Error", 
                    f"A spell named '{dialog.result.name}' already exists.")
    
    def _on_restore_spell(self, spell):
        """Restore a modified official spell to its default values."""
        if self.spell_manager.restore_spell_to_default(spell.name):
            # Refresh the spell list and detail view
            self._refresh_spell_list(reset_scroll=False)
            # Re-select the restored spell to show updated details
            self.spell_list.select_spell(spell.name)
            messagebox.showinfo("Success", 
                f"'{spell.name}' has been restored to its original version.")
        else:
            messagebox.showerror("Error", 
                f"Failed to restore '{spell.name}'.")
    
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
        """Export a single spell to an importable JSON file (Collections > Import reads it back)."""
        import content_io

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{spell.name.replace(' ', '_')}.json"
        )
        
        if not file_path:
            return
        try:
            content_io.export_objects(file_path, {"spells": [spell]}, self.spell_manager)
            messagebox.showinfo("Success", f"Spell exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export spell:\n{e}")
    
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
