"""
Spell Lists View for D&D Spellbook.
Displays and manages character spell lists.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional, List, Dict
from character import CharacterSpellList, get_max_prepared_spells
from character_manager import CharacterManager
from spell_manager import SpellManager
from spell import Spell, CharacterClass
from spell_slots import (
    get_max_spell_slots, get_warlock_level, get_warlock_pact_slots,
    get_warlock_mystic_arcanum_levels, is_multiclass_caster, get_max_cantrips
)
from settings import SettingsManager, get_settings_manager
from theme import get_theme_manager


def get_effective_max_slots(character: CharacterSpellList) -> Dict[int, int]:
    """Get effective max spell slots, using custom slots for Custom class characters."""
    if character.has_custom_class and character.custom_max_slots:
        return character.custom_max_slots.copy()
    class_levels = character.get_class_levels_tuple()
    ek_level = character.get_eldritch_knight_level()
    return get_max_spell_slots(class_levels, ek_level)


def get_effective_max_cantrips(character: CharacterSpellList) -> int:
    """Get effective max cantrips, using custom value for Custom class characters."""
    if character.has_custom_class:
        # For custom class, 0 means unlimited (return a large number)
        return character.custom_max_cantrips if character.custom_max_cantrips > 0 else 999
    class_levels = character.get_class_levels_tuple()
    ek_level = character.get_eldritch_knight_level()
    return get_max_cantrips(class_levels, ek_level)


class CharacterCard(ctk.CTkFrame):
    """A card widget displaying a character's spell list summary."""
    def __init__(self, parent, character: CharacterSpellList,
                 on_select: Callable[["CharacterCard"], None],
                 on_edit: Callable[[CharacterSpellList], None],
                 on_delete: Callable[[CharacterSpellList], None],
                 is_selected: bool = False):
        # Use theme manager for colors so the card updates with theme changes
        self.theme = get_theme_manager()
        selected_color = self.theme.get_current_color('accent_primary')
        unselected_color = self.theme.get_current_color('bg_secondary')
        super().__init__(parent, corner_radius=10,
                         fg_color=selected_color if is_selected else unselected_color,
                         cursor="hand2")
        
        self.character = character
        self.on_select = on_select
        self.on_edit = on_edit
        self.on_delete = on_delete
        self._is_selected = is_selected
        
        self._create_widgets()
        
        # Bind click events
        self.bind("<Button-1>", self._on_click)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._on_click)
    
    def _create_widgets(self):
        """Create the card content."""
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=12)
        
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x", pady=(0, 8))
        
        self.name_label = ctk.CTkLabel(
            header, text=self.character.name,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.name_label.pack(side="left", fill="x", expand=True)
        self.name_label.bind("<Button-1>", self._on_click)
        
        btn_text = self.theme.get_current_color('text_primary')
        edit_btn = ctk.CTkButton(header, text="Edit", width=50, height=28,
                                  fg_color=self.theme.get_current_color('button_normal'), hover_color=self.theme.get_current_color('button_hover'),
                                  text_color=btn_text,
                                  command=lambda: self.on_edit(self.character))
        edit_btn.pack(side="right", padx=(5, 0))
        
        delete_btn = ctk.CTkButton(header, text="✕", width=28, height=28,
                                    fg_color=self.theme.get_current_color('button_danger'), hover_color=self.theme.get_current_color('button_danger_hover'),
                                    text_color=btn_text,
                                    command=lambda: self.on_delete(self.character))
        delete_btn.pack(side="right")
        
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        class_label = ctk.CTkLabel(
            content, text=self.character.display_classes(),
            font=ctk.CTkFont(size=13),
            text_color=text_secondary,
            anchor="w"
        )
        class_label.pack(fill="x", pady=(0, 5))
        class_label.bind("<Button-1>", self._on_click)
        
        spell_count = len(self.character.known_spells)
        count_label = ctk.CTkLabel(
            content, 
            text=f"{spell_count} spell{'s' if spell_count != 1 else ''} known",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary,
            anchor="w"
        )
        count_label.pack(fill="x")
        count_label.bind("<Button-1>", self._on_click)
    
    def _on_click(self, event=None):
        self.on_select(self)
    
    def set_selected(self, selected: bool):
        self._is_selected = selected
        # Update using theme manager so selection reflects current theme
        # Reconfigure background based on selection
        try:
            self.configure(fg_color=(self.theme.get_current_color('accent_primary') if selected else self.theme.get_current_color('bg_secondary')))
        except Exception:
            pass


class CharacterSpellsPanel(ctk.CTkFrame):
    """Panel showing the spells known by a selected character."""
    
    def __init__(self, parent, spell_manager: SpellManager,
                 character_manager: CharacterManager,
                 on_remove_spell: Callable[[str], None],
                 on_spell_click: Optional[Callable[[str], None]] = None,
                 on_character_updated: Optional[Callable[[], None]] = None,
                 settings_manager: Optional[SettingsManager] = None,
                 scrollable: bool = True):
        super().__init__(parent, corner_radius=10)
        
        self.spell_manager = spell_manager
        self.character_manager = character_manager
        self.on_remove_spell = on_remove_spell
        self.on_spell_click = on_spell_click
        self.on_character_updated = on_character_updated
        self.settings_manager = settings_manager or get_settings_manager()
        self._scrollable = scrollable  # Whether to use scrollable frame
        # Theme manager for dynamic colors
        self.theme = get_theme_manager()
        # Listen for theme changes to update appearance
        try:
            self.theme.add_listener(self._on_theme_changed)
            self._theme = self.theme
        except Exception:
            self._theme = None
        self._current_character: Optional[CharacterSpellList] = None
        
        # Widget tracking
        self._level_sections: Dict[int, dict] = {}  # {level: {'header': frame, 'spells': {name: row_data}}}
        self._slot_vars: Dict[int, ctk.StringVar] = {}
        self._slot_entries: Dict[int, ctk.CTkEntry] = {}
        self._prepared_vars: Dict[str, ctk.BooleanVar] = {}
        self._arcanum_vars: Dict[int, ctk.BooleanVar] = {}
        self._show_prepared_only = False
        self._is_building = False
        
        self._create_widgets()
        self.set_character(None)
    
    def _create_widgets(self):
        """Create the panel widgets."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        self.title_label = ctk.CTkLabel(
            header, text="Known Spells",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_label.pack(side="left")
        
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        self.count_label = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        )
        self.count_label.pack(side="right")
        
        # Prepared spells count label (for prepared casters)
        self.prepared_label = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        )
        self.prepared_label.pack(side="right", padx=(0, 15))
        
        # Button bar
        self.button_bar = ctk.CTkFrame(self, fg_color="transparent")
        
        btn_text = self.theme.get_current_color('text_primary')
        self.long_rest_btn = ctk.CTkButton(
            self.button_bar, text="Long Rest", width=90,
            fg_color=self.theme.get_current_color('button_success'), hover_color=self.theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_long_rest
        )
        self.long_rest_btn.pack(side="left", padx=(0, 8))
        
        self.short_rest_btn = ctk.CTkButton(
            self.button_bar, text="Short Rest", width=90,
            fg_color=self.theme.get_current_color('button_warning'), hover_color=self.theme.get_current_color('button_warning_hover'),
            text_color=btn_text,
            command=self._on_short_rest
        )
        
        self.filter_btn = ctk.CTkButton(
            self.button_bar, text="Show All", width=100,
            fg_color=self.theme.get_current_color('button_normal'), hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self._toggle_prepared_filter
        )
        self.filter_btn.pack(side="left")
        
        # Configure Slots button (for Custom class characters)
        self.config_slots_btn = ctk.CTkButton(
            self.button_bar, text="Configure Slots", width=110,
            fg_color=self.theme.get_current_color('button_normal'), hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self._on_configure_slots
        )
        # Will be packed/unpacked based on whether character has Custom class
        
        # Warlock frame
        self.warlock_frame = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('warlock_panel'), corner_radius=8)
        
        # Hint text
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        self.hint_label = ctk.CTkLabel(
            self, text="Click a spell name to view details",
            font=ctk.CTkFont(size=11),
            text_color=text_secondary
        )
        
        # Scrollable spell list or regular frame based on setting
        if self._scrollable:
            self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        else:
            self.scroll_frame = ctk.CTkFrame(self, fg_color="transparent")
        
        # Placeholder
        self.placeholder = ctk.CTkLabel(
            self,
            text="Select a character to view their spells",
            font=ctk.CTkFont(size=14),
            text_color=text_secondary
        )

    def destroy(self):
        """Clean up listeners when panel is destroyed."""
        try:
            if hasattr(self, '_theme') and self._theme:
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()

    def _on_theme_changed(self):
        """Reconfigure color-sensitive widgets when theme changes."""
        theme = get_theme_manager()
        try:
            # Button colors
            if hasattr(self, 'long_rest_btn'):
                self.long_rest_btn.configure(fg_color=theme.get_current_color('button_success'), hover_color=theme.get_current_color('button_success_hover'))
            if hasattr(self, 'short_rest_btn'):
                self.short_rest_btn.configure(fg_color=theme.get_current_color('button_warning'), hover_color=theme.get_current_color('button_warning_hover'))
            if hasattr(self, 'filter_btn'):
                # Preserve text state
                txt = self.filter_btn.cget('text')
                if txt == 'Prepared Only':
                    self.filter_btn.configure(fg_color=theme.get_current_color('accent_primary'))
                else:
                    self.filter_btn.configure(fg_color=theme.get_current_color('button_normal'))
                self.filter_btn.configure(hover_color=theme.get_current_color('button_hover'))

            # Warlock frame background
            if hasattr(self, 'warlock_frame'):
                try:
                    self.warlock_frame.configure(fg_color=theme.get_current_color('warlock_panel'))
                except Exception:
                    pass

            # Update any slot/warlock entry widgets (input backgrounds)
            try:
                input_bg = theme.get_current_color('bg_input')
                input_text = theme.get_current_color('text_primary')
                border_col = theme.get_current_color('border')
                # Warlock entry
                if hasattr(self, 'warlock_entry'):
                    try:
                        self.warlock_entry.configure(fg_color=input_bg, text_color=input_text, border_color=border_col)
                    except Exception:
                        pass
                # Per-level slot entries
                for lvl, entry in getattr(self, '_slot_entries', {}).items():
                    try:
                        entry.configure(fg_color=input_bg, text_color=input_text, border_color=border_col)
                    except Exception:
                        pass
            except Exception:
                pass

            # Hint and placeholder text color
            text_secondary = theme.get_text_secondary()
            if hasattr(self, 'hint_label'):
                self.hint_label.configure(text_color=text_secondary)
            if hasattr(self, 'placeholder'):
                self.placeholder.configure(text_color=text_secondary)

            # Update existing spell rows' backgrounds and text colors
            for level, section in self._level_sections.items():
                for spell_name, row_data in section.get('spells', {}).items():
                    row = row_data.get('row')
                    if row:
                        try:
                            row.configure(fg_color=theme.get_current_color('spell_row'))
                        except Exception:
                            pass
                        # Update labels inside row (approximate)
                        for child in row.winfo_children():
                            try:
                                # For CTkLabel children, update text_color if possible
                                if isinstance(child, ctk.CTkLabel):
                                    child.configure(text_color=theme.get_current_color('text_primary'))
                            except Exception:
                                pass

            # Update level header frames and child labels
            for level, section in self._level_sections.items():
                header = section.get('header')
                if header:
                    try:
                        header.configure(fg_color=theme.get_current_color('level_header'))
                    except Exception:
                        pass
                    # header -> header_content -> nested frames/labels
                    for child in header.winfo_children():
                        for sub in child.winfo_children():
                            try:
                                if isinstance(sub, ctk.CTkLabel):
                                    txt = sub.cget('text')
                                    if txt and txt.strip() == 'Prepared':
                                        sub.configure(text_color=theme.get_text_secondary())
                                    else:
                                        sub.configure(text_color=theme.get_current_color('text_primary'))
                            except Exception:
                                pass

            # Update labels inside the warlock frame (if present)
            try:
                if hasattr(self, 'warlock_frame'):
                    for child in self.warlock_frame.winfo_children():
                        for sub in child.winfo_children():
                            try:
                                if isinstance(sub, ctk.CTkLabel):
                                    # use secondary color for small helper labels
                                    sub.configure(text_color=theme.get_text_secondary())
                            except Exception:
                                pass
            except Exception:
                pass

        except Exception:
            pass
    
    def _on_long_rest(self):
        """Handle long rest button click."""
        if not self._current_character:
            return
        
        max_slots = get_effective_max_slots(self._current_character)
        class_levels = self._current_character.get_class_levels_tuple()
        warlock_level = get_warlock_level(class_levels)
        warlock_slots, _ = get_warlock_pact_slots(warlock_level)
        
        self._current_character.long_rest(max_slots, warlock_slots)
        self._save_character()
        
        # Update displays without rebuild
        self._update_all_slot_displays()
        
        if self.settings_manager.settings.show_rest_notification:
            messagebox.showinfo("Long Rest", "All spell slots and Mystic Arcanum restored!")
    
    def _on_short_rest(self):
        """Handle short rest button click."""
        if not self._current_character:
            return
        
        class_levels = self._current_character.get_class_levels_tuple()
        warlock_level = get_warlock_level(class_levels)
        warlock_slots, _ = get_warlock_pact_slots(warlock_level)
        
        self._current_character.short_rest(warlock_slots)
        self._save_character()
        
        # Update warlock display
        if hasattr(self, 'warlock_slot_var'):
            self.warlock_slot_var.set(str(self._current_character.warlock_slots_current))
        
        if self.settings_manager.settings.show_rest_notification:
            messagebox.showinfo("Short Rest", "Warlock spell slots restored!")
    
    def _on_configure_slots(self):
        """Handle Configure Slots button click for Custom class characters."""
        if not self._current_character or not self._current_character.has_custom_class:
            return
        
        from ui.character_editor import CustomSpellSlotsDialog
        dialog = CustomSpellSlotsDialog(self.winfo_toplevel(), self._current_character)
        self.wait_window(dialog)
        
        if dialog.result:
            # Update the character
            self._current_character.custom_max_slots = dialog.result.custom_max_slots
            self._current_character.custom_max_cantrips = dialog.result.custom_max_cantrips
            self._save_character()
            
            # Reinitialize slots with new max values
            self._initialize_slots(self._current_character)
            self._save_character()
            
            # Clear and rebuild the spell list to reflect new slot limits
            for widget in self.scroll_frame.winfo_children():
                widget.destroy()
            self._level_sections.clear()
            self._slot_vars.clear()
            self._slot_entries.clear()
            self._prepared_vars.clear()
            self._arcanum_vars.clear()
            self._build_spell_list()
    
    def _update_all_slot_displays(self):
        """Update all slot displays without rebuilding."""
        if not self._current_character:
            return
        
        # Update regular slots
        for level, var in self._slot_vars.items():
            var.set(str(self._current_character.get_current_slots(level)))
        
        # Update warlock slots
        if hasattr(self, 'warlock_slot_var'):
            self.warlock_slot_var.set(str(self._current_character.warlock_slots_current))
        
        # Update mystic arcanum
        for level, var in self._arcanum_vars.items():
            var.set(self._current_character.is_mystic_arcanum_available(level))
    
    def _update_prepared_count(self):
        """Update the prepared spells count display."""
        if not self._current_character:
            self.prepared_label.configure(text="")
            return
        
        max_prepared = get_max_prepared_spells(self._current_character)
        if max_prepared is None:
            # Not a prepared caster
            self.prepared_label.configure(text="")
            return
        
        # Count prepared spells (not including subclass spells)
        prepared_count = self._current_character.get_prepared_count()
        
        # Color code: red if over limit, normal if under
        theme = get_theme_manager()
        if prepared_count > max_prepared:
            color = theme.get_current_color('button_danger')
        elif prepared_count == max_prepared:
            color = theme.get_current_color('accent_primary')
        else:
            color = theme.get_text_secondary()
        
        self.prepared_label.configure(
            text=f"Prepared: {prepared_count}/{max_prepared}",
            text_color=color
        )
    
    def _toggle_prepared_filter(self):
        """Toggle showing only prepared spells using visibility, not rebuild."""
        self._show_prepared_only = not self._show_prepared_only
        
        if self._show_prepared_only:
            # Use accent for prepared-only state
            self.filter_btn.configure(text="Prepared Only", fg_color=self.theme.get_current_color('accent_primary'))
        else:
            # Use normal button style for default
            self.filter_btn.configure(text="Show All", fg_color=self.theme.get_current_color('button_normal'))
        
        self._apply_prepared_filter()
    
    def _apply_prepared_filter(self):
        """Show/hide spell rows based on prepared filter."""
        if not self._current_character:
            return
        
        visible_count = 0
        levels_with_visible = set()
        
        for level, section in self._level_sections.items():
            level_visible = 0
            for spell_name, row_data in section.get('spells', {}).items():
                row = row_data['row']
                is_prepared = self._current_character.is_prepared(spell_name)
                
                if self._show_prepared_only and not is_prepared:
                    row.pack_forget()
                else:
                    # Re-pack the row
                    row.pack(fill="x", pady=1, padx=5)
                    level_visible += 1
                    visible_count += 1
            
            # Show/hide level header based on whether it has visible spells
            header = section.get('header')
            if header:
                if level_visible > 0:
                    header.pack(fill="x", pady=(4, 1), padx=5)
                    levels_with_visible.add(level)
                else:
                    header.pack_forget()
        
        # Reorder widgets to maintain proper order
        self._reorder_widgets()
        
        self.count_label.configure(text=f"{visible_count} spell{'s' if visible_count != 1 else ''}")
    
    def _reorder_widgets(self):
        """Reorder all widgets in the scroll frame to maintain level order."""
        # Unpack all
        for level in sorted(self._level_sections.keys()):
            section = self._level_sections[level]
            header = section.get('header')
            if header:
                header.pack_forget()
            for row_data in section.get('spells', {}).values():
                row_data['row'].pack_forget()
        
        # Repack in order
        for level in sorted(self._level_sections.keys()):
            section = self._level_sections[level]
            has_visible = False
            
            # Check if any spell in this level should be visible
            for spell_name, row_data in section.get('spells', {}).items():
                is_prepared = self._current_character.is_prepared(spell_name) if self._current_character else False
                if not self._show_prepared_only or is_prepared:
                    has_visible = True
                    break
            
            if has_visible:
                header = section.get('header')
                if header:
                    header.pack(fill="x", pady=(4, 1), padx=5)
                
                # Pack spells in sorted order
                sorted_spells = sorted(section.get('spells', {}).items(), key=lambda x: x[0].lower())
                for spell_name, row_data in sorted_spells:
                    is_prepared = self._current_character.is_prepared(spell_name) if self._current_character else False
                    if not self._show_prepared_only or is_prepared:
                        row_data['row'].pack(fill="x", pady=1, padx=5)
    
    def _save_character(self):
        """Save the current character."""
        if self._current_character:
            self.character_manager.update_character(
                self._current_character.name, self._current_character
            )
    
    def set_character(self, character: Optional[CharacterSpellList]):
        """Set the character whose spells to display."""
        self._current_character = character
        self._clear_all()
        
        if character is None:
            self.scroll_frame.pack_forget()
            self.hint_label.pack_forget()
            self.button_bar.pack_forget()
            self.warlock_frame.pack_forget()
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            self.title_label.configure(text="Known Spells")
            self.count_label.configure(text="")
            self.prepared_label.configure(text="")
            return
        
        self.placeholder.place_forget()
        self._initialize_slots(character)
        
        # Show button bar
        self.button_bar.pack(fill="x", padx=15, pady=(0, 10))
        
        # Show/hide short rest
        class_levels = character.get_class_levels_tuple()
        warlock_level = get_warlock_level(class_levels)
        if warlock_level > 0:
            self.short_rest_btn.pack(side="left", padx=(0, 15), after=self.long_rest_btn)
        else:
            self.short_rest_btn.pack_forget()
        
        # Show/hide Configure Slots button for Custom class
        if character.has_custom_class:
            self.config_slots_btn.pack(side="left", padx=(8, 0), after=self.filter_btn)
        else:
            self.config_slots_btn.pack_forget()
        
        self._setup_warlock_display(character)
        
        self.hint_label.pack(padx=15, anchor="w")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        self.title_label.configure(text=f"{character.name}'s Spells")
        
        self._build_spell_list()
    
    def _initialize_slots(self, character: CharacterSpellList):
        """Initialize spell slots to max if not set."""
        max_slots = get_effective_max_slots(character)
        
        for level, max_count in max_slots.items():
            if level not in character.current_slots:
                character.current_slots[level] = max_count
        
        class_levels = character.get_class_levels_tuple()
        warlock_level = get_warlock_level(class_levels)
        if warlock_level > 0:
            warlock_slots, _ = get_warlock_pact_slots(warlock_level)
            if character.warlock_slots_current == 0:
                character.warlock_slots_current = warlock_slots
    
    def _setup_warlock_display(self, character: CharacterSpellList):
        """Setup the warlock pact magic display."""
        class_levels = character.get_class_levels_tuple()
        warlock_level = get_warlock_level(class_levels)
        
        for widget in self.warlock_frame.winfo_children():
            widget.destroy()
        
        if warlock_level <= 0:
            self.warlock_frame.pack_forget()
            return
        
        self.warlock_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        warlock_slots, slot_level = get_warlock_pact_slots(warlock_level)
        is_multiclass = is_multiclass_caster(class_levels)
        
        title_text = "Warlock Pact Magic" if is_multiclass else "Pact Magic"
        text_primary = self.theme.get_current_color('text_primary')
        text_secondary = self.theme.get_text_secondary()
        ctk.CTkLabel(
            self.warlock_frame, text=title_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=text_primary
        ).pack(pady=(10, 5))
        
        slots_row = ctk.CTkFrame(self.warlock_frame, fg_color="transparent")
        slots_row.pack(pady=(0, 5))

        slot_label = "Warlock Spell Slots:" if is_multiclass else "Spell Slots:"
        ctk.CTkLabel(slots_row, text=slot_label, font=ctk.CTkFont(size=12), text_color=text_primary).pack(side="left", padx=(0, 8))

        self.warlock_slot_var = ctk.StringVar(value=str(character.warlock_slots_current))
        self.warlock_entry = ctk.CTkEntry(
            slots_row, textvariable=self.warlock_slot_var,
            width=40, justify="center",
            fg_color=self.theme.get_current_color('bg_input'),
            text_color=self.theme.get_current_color('text_primary'),
            border_color=self.theme.get_current_color('border')
        )
        self.warlock_entry.pack(side="left")
        self.warlock_entry.bind("<FocusOut>", lambda e: self._on_warlock_slot_change())
        self.warlock_entry.bind("<Return>", lambda e: self._on_warlock_slot_change())
        
        ctk.CTkLabel(slots_row, text=f"/ {warlock_slots}", font=ctk.CTkFont(size=12), text_color=text_secondary).pack(side="left", padx=(2, 0))

        level_row = ctk.CTkFrame(self.warlock_frame, fg_color="transparent")
        level_row.pack(pady=(0, 5))

        level_label = "Warlock Spell Level:" if is_multiclass else "Spell Slot Level:"
        ctk.CTkLabel(level_row, text=f"{level_label} {slot_level}", font=ctk.CTkFont(size=12), text_color=text_secondary).pack()
        
        arcanum_levels = get_warlock_mystic_arcanum_levels(warlock_level)
        if arcanum_levels:
            ctk.CTkLabel(
                self.warlock_frame, text="Mystic Arcanum:",
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(pady=(5, 3))
            
            arcanum_row = ctk.CTkFrame(self.warlock_frame, fg_color="transparent")
            arcanum_row.pack(pady=(0, 10))
            
            for spell_level in arcanum_levels:
                var = ctk.BooleanVar(value=character.is_mystic_arcanum_available(spell_level))
                self._arcanum_vars[spell_level] = var

                cb = ctk.CTkCheckBox(
                    arcanum_row, text=f"{spell_level}th",
                    variable=var, width=60,
                    command=lambda sl=spell_level: self._on_arcanum_change(sl)
                )
                cb.pack(side="left", padx=5)
    
    def _on_warlock_slot_change(self):
        """Handle warlock slot value change."""
        if not self._current_character or self._is_building:
            return
        try:
            value = int(self.warlock_slot_var.get())
            class_levels = self._current_character.get_class_levels_tuple()
            warlock_level = get_warlock_level(class_levels)
            max_slots, _ = get_warlock_pact_slots(warlock_level)
            self._current_character.warlock_slots_current = max(0, min(value, max_slots))
            self.warlock_slot_var.set(str(self._current_character.warlock_slots_current))
            self._save_character()
        except ValueError:
            pass
    
    def _on_arcanum_change(self, spell_level: int):
        """Handle mystic arcanum checkbox change."""
        if not self._current_character or self._is_building:
            return
        var = self._arcanum_vars.get(spell_level)
        if var:
            if var.get():
                self._current_character.reset_mystic_arcanum(spell_level)
            else:
                self._current_character.use_mystic_arcanum(spell_level)
            self._save_character()
    
    def _clear_all(self):
        """Clear all spell widgets."""
        for level, section in self._level_sections.items():
            header = section.get('header')
            if header:
                header.destroy()
            for row_data in section.get('spells', {}).values():
                row_data['row'].destroy()
        
        self._level_sections = {}
        self._slot_vars = {}
        self._prepared_vars = {}
        self._arcanum_vars = {}
    
    def _build_spell_list(self):
        """Build the spell list widgets."""
        if not self._current_character:
            return
        
        self._is_building = True
        
        character = self._current_character
        max_slots = get_effective_max_slots(character)
        
        # Group spells by level
        spells_by_level: Dict[int, List[Spell]] = {}
        for spell_name in character.known_spells:
            spell = self.spell_manager.get_spell(spell_name)
            if spell:
                level = spell.level
                if level not in spells_by_level:
                    spells_by_level[level] = []
                spells_by_level[level].append(spell)
        
        # Count total
        total = sum(len(spells) for spells in spells_by_level.values())
        self.count_label.configure(text=f"{total} spell{'s' if total != 1 else ''}")
        
        # Update prepared count for prepared casters
        self._update_prepared_count()
        
        # Build sections
        for level in sorted(spells_by_level.keys()):
            self._build_level_section(level, spells_by_level[level], max_slots, character)
        
        self._is_building = False
        
        # Apply filter if active
        if self._show_prepared_only:
            self._apply_prepared_filter()
    
    def _build_level_section(self, level: int, spells: List[Spell],
                              max_slots: Dict[int, int], character: CharacterSpellList):
        """Build a level section with header and spells."""
        # Initialize section storage
        self._level_sections[level] = {'header': None, 'spells': {}}
        
        # Header frame
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color=self.theme.get_current_color('level_header'), corner_radius=4, height=32)
        header_frame.pack(fill="x", pady=(4, 1), padx=5)
        header_frame.pack_propagate(False)  # Fix the height
        self._level_sections[level]['header'] = header_frame

        header_content = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_content.pack(fill="both", expand=True, padx=8)

        level_text = "Cantrips" if level == 0 else f"Level {level}"
        ctk.CTkLabel(
            header_content, text=level_text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.theme.get_current_color('text_primary')
        ).pack(side="left")

        # Right side container
        right_frame = ctk.CTkFrame(header_content, fg_color="transparent")
        right_frame.pack(side="right")

        # Spell slots
        if level > 0 and level in max_slots:
            slots_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
            slots_frame.pack(side="left", padx=(0, 20))

            ctk.CTkLabel(slots_frame, text="Slots:", font=ctk.CTkFont(size=11), text_color=self.theme.get_current_color('text_primary')).pack(side="left", padx=(0, 5))

            slot_var = ctk.StringVar(value=str(character.get_current_slots(level)))
            self._slot_vars[level] = slot_var
            slot_entry = ctk.CTkEntry(
                slots_frame, textvariable=slot_var,
                width=35, justify="center", height=25,
                fg_color=self.theme.get_current_color('bg_input'),
                text_color=self.theme.get_current_color('text_primary'),
                border_color=self.theme.get_current_color('border')
            )
            slot_entry.pack(side="left")
            slot_entry.bind("<FocusOut>", lambda e, l=level: self._on_slot_change(l))
            slot_entry.bind("<Return>", lambda e, l=level: self._on_slot_change(l))
            # Keep reference so we can reconfigure on theme change
            try:
                self._slot_entries[level] = slot_entry
            except Exception:
                pass

            ctk.CTkLabel(
                slots_frame, text=f"/ {max_slots[level]}",
                font=ctk.CTkFont(size=11),
                text_color=self.theme.get_text_secondary()
            ).pack(side="left", padx=(2, 0))

        # Mystic Arcanum for warlock levels 6+
        class_levels = character.get_class_levels_tuple()
        warlock_level = get_warlock_level(class_levels)
        arcanum_levels = get_warlock_mystic_arcanum_levels(warlock_level)

        if level >= 6 and level in arcanum_levels and level not in max_slots:
            arcanum_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
            arcanum_frame.pack(side="left", padx=(0, 20))

            var = ctk.BooleanVar(value=character.is_mystic_arcanum_available(level))
            self._arcanum_vars[level] = var

            cb = ctk.CTkCheckBox(
                arcanum_frame, text="Mystic Arcanum",
                variable=var, height=25,
                command=lambda sl=level: self._on_arcanum_change(sl)
            )
            cb.pack(side="left")

        # "Prepared" header
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        ctk.CTkLabel(
            right_frame, text="Prepared",
            font=ctk.CTkFont(size=10),
            text_color=text_secondary,
            width=60
        ).pack(side="right")

        # Spells
        for spell in sorted(spells, key=lambda s: s.name.lower()):
            self._build_spell_row(spell, character, level)
    
    def _build_spell_row(self, spell: Spell, character: CharacterSpellList, level: int):
        """Build a row for a spell."""
        theme = self.theme
        row = ctk.CTkFrame(self.scroll_frame, fg_color=theme.get_current_color('spell_row'), corner_radius=4, height=30)
        row.pack(fill="x", pady=1, padx=5)
        row.pack_propagate(False)  # Fix the height

        # Remove button
        remove_btn = ctk.CTkButton(
            row, text="✕", width=22, height=22,
            fg_color=theme.get_current_color('button_danger'), hover_color=theme.get_current_color('button_danger_hover'),
            command=lambda sn=spell.name: self.on_remove_spell(sn)
        )
        remove_btn.pack(side="left", padx=(4, 0))

        # Spell name (using label with click binding for compactness)
        hover_color = theme.get_current_color('accent_hover')
        default_text = theme.get_current_color('text_primary')
        
        name_label = ctk.CTkLabel(
            row, text=spell.name,
            font=ctk.CTkFont(size=12),
            anchor="w",
            cursor="hand2",
            text_color=default_text
        )
        name_label.pack(side="left", fill="x", expand=True, padx=(6, 8))
        name_label.bind("<Button-1>", lambda e, sn=spell.name: self._on_spell_name_click(sn))
        name_label.bind("<Enter>", lambda e, hc=hover_color: name_label.configure(text_color=hc))
        name_label.bind("<Leave>", lambda e, dt=default_text: name_label.configure(text_color=dt))
        
        # Indicators
        indicators = []
        if spell.ritual:
            indicators.append("R")
        if spell.concentration:
            indicators.append("C")
        
        if indicators:
            text_secondary = theme.get_text_secondary()
            ctk.CTkLabel(
                row, text=f"({', '.join(indicators)})",
                font=ctk.CTkFont(size=10),
                text_color=text_secondary
            ).pack(side="left", padx=(0, 4))
        
        # Check if this is a subclass spell (always prepared)
        is_subclass_spell = character.is_subclass_spell(spell.name)
        is_cantrip = (spell.level == 0)
        
        # Only show prepared checkbox for non-cantrip spells
        if not is_cantrip:
            # Prepared checkbox
            prepared_var = ctk.BooleanVar(value=character.is_prepared(spell.name))
            self._prepared_vars[spell.name] = prepared_var
            
            prepared_cb = ctk.CTkCheckBox(
                row, text="", variable=prepared_var, width=20,
                checkbox_width=16, checkbox_height=16,
                command=lambda sn=spell.name: self._on_prepared_change(sn)
            )
            prepared_cb.pack(side="right", padx=(0, 15))
            
            # Disable checkbox for subclass spells (always prepared)
            if is_subclass_spell:
                prepared_cb.configure(state="disabled")
                prepared_var.set(True)  # Always checked
                # Add "(Always Prepared)" indicator
                ctk.CTkLabel(
                    row, text="★",
                    font=ctk.CTkFont(size=10),
                    text_color=self.theme.get_current_color('accent_primary')
                ).pack(side="right", padx=(0, 2))
        else:
            # Cantrips - add small spacer for alignment
            prepared_var = ctk.BooleanVar(value=True)  # Cantrips always "prepared"
            self._prepared_vars[spell.name] = prepared_var
            ctk.CTkFrame(row, width=35, fg_color="transparent").pack(side="right")
        
        # Store row data
        self._level_sections[level]['spells'][spell.name] = {
            'row': row,
            'prepared_var': prepared_var,
            'is_subclass_spell': is_subclass_spell,
            'is_cantrip': is_cantrip
        }
    
    def _on_slot_change(self, level: int):
        """Handle spell slot value change."""
        if not self._current_character or self._is_building:
            return
        var = self._slot_vars.get(level)
        if not var:
            return
        try:
            value = int(var.get())
            max_slots = get_effective_max_slots(self._current_character)
            max_val = max_slots.get(level, 0)
            self._current_character.set_current_slots(level, min(value, max_val))
            var.set(str(self._current_character.get_current_slots(level)))
            self._save_character()
        except ValueError:
            pass
    
    def _on_prepared_change(self, spell_name: str):
        """Handle prepared checkbox change."""
        if not self._current_character or self._is_building:
            return
        var = self._prepared_vars.get(spell_name)
        if var:
            if var.get():
                self._current_character.prepare_spell(spell_name)
                # Check if over-prepared and show warning
                self._check_over_prepared_warning()
            else:
                self._current_character.unprepare_spell(spell_name)
            self._save_character()
            # Update prepared count display
            self._update_prepared_count()
    
    def _check_over_prepared_warning(self):
        """Check if character has too many spells prepared and show warning."""
        if not self._current_character:
            return
        
        # Check settings
        settings = get_settings_manager()
        if not settings.settings.warn_too_many_prepared:
            return
        
        max_prepared = get_max_prepared_spells(self._current_character)
        if max_prepared is None:
            return  # Not a prepared caster
        
        prepared_count = self._current_character.get_prepared_count()
        if prepared_count > max_prepared:
            from tkinter import messagebox
            messagebox.showwarning(
                "Too Many Spells Prepared",
                f"You have {prepared_count} spells prepared, but your maximum is {max_prepared}.\n\n"
                f"Consider unpreparing some spells.\n\n"
                f"(You can disable this warning in Settings)"
            )
    
    def _on_spell_name_click(self, spell_name: str):
        """Handle spell name click."""
        if self.on_spell_click:
            self.on_spell_click(spell_name)


class SpellListsView(ctk.CTkFrame):
    """Main view for managing character spell lists."""
    
    def __init__(self, parent, character_manager: CharacterManager,
                 spell_manager: SpellManager,
                 on_navigate_to_spell: Optional[Callable[[str], None]] = None,
                 settings_manager: Optional[SettingsManager] = None):
        super().__init__(parent, fg_color="transparent")
        
        self.character_manager = character_manager
        self.spell_manager = spell_manager
        self.on_navigate_to_spell = on_navigate_to_spell
        self.settings_manager = settings_manager or get_settings_manager()
        self._selected_card: Optional[CharacterCard] = None
        self._character_cards: List[CharacterCard] = []
        
        self._create_widgets()
        
        self.character_manager.add_listener(self._refresh_characters)
        self._refresh_characters()
        # Listen for theme changes to update colors live
        theme = get_theme_manager()
        theme.add_listener(self._on_theme_changed)
        # keep reference for cleanup
        self._theme = theme

    def destroy(self):
        """Clean up listeners when the view is destroyed."""
        try:
            if hasattr(self, '_theme'):
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass

        try:
            self.character_manager.remove_listener(self._refresh_characters)
        except Exception:
            pass

        super().destroy()

    def _on_theme_changed(self):
        """Handle theme changes by refreshing color-sensitive UI."""
        # Update paned colors and rebuild character cards (they use theme for fg_color)
        self.update_paned_colors()
        # Update text color for count label
        theme = get_theme_manager()
        self.char_count_label.configure(text_color=theme.get_text_secondary())
        # Rebuild character cards to pick up any fg_color/bg changes
        self._refresh_characters()
    
    def _create_widgets(self):
        """Create the view widgets."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header, text="Character Spell Lists",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        
        theme = get_theme_manager()
        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(header, text="+ New Character", width=130,
                      text_color=btn_text,
                      command=self._on_new_character).pack(side="right")
        
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Create a PanedWindow for resizable panels
        # opaqueresize=False for smooth dragging (shows ghost line, resizes on release)
        self.paned = tk.PanedWindow(
            content,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            handlesize=0,
            opaqueresize=False,
            sashcursor="sb_h_double_arrow"
        )
        self.paned.pack(fill="both", expand=True)
        self.update_paned_colors()
        
        left_panel = ctk.CTkFrame(self.paned, corner_radius=10)
        
        char_header = ctk.CTkFrame(left_panel, fg_color="transparent")
        char_header.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(char_header, text="Characters",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        self.char_count_label = ctk.CTkLabel(
            char_header, text="0 characters",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary
        )
        self.char_count_label.pack(side="right")
        
        self.cards_frame = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self.cards_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.empty_placeholder = ctk.CTkLabel(
            self.cards_frame,
            text="No characters yet.\nClick '+ New Character' to create one.",
            font=ctk.CTkFont(size=13),
            text_color=text_secondary,
            justify="center"
        )
        
        self.spells_panel = CharacterSpellsPanel(
            self.paned, self.spell_manager, self.character_manager,
            self._on_remove_spell,
            on_spell_click=self._on_spell_click,
            on_character_updated=self._on_character_updated,
            settings_manager=self.settings_manager
        )
        
        # Add panes with minimum sizes
        self.paned.add(left_panel, minsize=280, stretch="always")
        self.paned.add(self.spells_panel, minsize=400, stretch="always")
        
        # Set initial sash position (roughly 1:2 ratio)
        self.after(100, lambda: self.paned.sash_place(0, 320, 0))
    
    def update_paned_colors(self):
        """Update PanedWindow sash colors based on current theme."""
        # Use ThemeManager so the sash/background updates with selected theme
        theme = get_theme_manager()
        sash_color = theme.get_current_color("pane_sash")
        self.paned.configure(bg=sash_color)
    
    def _refresh_characters(self):
        """Refresh the character cards list."""
        for card in self._character_cards:
            card.destroy()
        self._character_cards = []
        
        characters = self.character_manager.characters
        
        count = len(characters)
        self.char_count_label.configure(
            text=f"{count} character{'s' if count != 1 else ''}"
        )
        
        if not characters:
            self.empty_placeholder.pack(pady=50)
            self._selected_card = None
            self.spells_panel.set_character(None)
            return
        
        self.empty_placeholder.pack_forget()
        
        selected_name = None
        if self._selected_card:
            selected_name = self._selected_card.character.name
        
        new_selected = None
        for char in characters:
            is_selected = bool(selected_name and char.name.lower() == selected_name.lower())
            card = CharacterCard(
                self.cards_frame, char,
                on_select=self._on_card_select,
                on_edit=self._on_edit_character,
                on_delete=self._on_delete_character,
                is_selected=is_selected
            )
            card.pack(fill="x", pady=5)
            self._character_cards.append(card)
            
            if is_selected:
                new_selected = card
        
        self._selected_card = new_selected
        if new_selected:
            updated_char = self.character_manager.get_character(new_selected.character.name)
            if updated_char:
                new_selected.character = updated_char
            self.spells_panel.set_character(new_selected.character)
        else:
            self.spells_panel.set_character(None)
    
    def _on_card_select(self, card: CharacterCard):
        if self._selected_card and self._selected_card != card:
            self._selected_card.set_selected(False)
        
        card.set_selected(True)
        self._selected_card = card
        
        updated_char = self.character_manager.get_character(card.character.name)
        if updated_char:
            card.character = updated_char
        self.spells_panel.set_character(card.character)
    
    def _on_spell_click(self, spell_name: str):
        if self.on_navigate_to_spell:
            self.on_navigate_to_spell(spell_name)
    
    def _on_character_updated(self):
        """Called when character data is updated."""
        pass
    
    def _on_new_character(self):
        from ui.character_editor import CharacterEditorDialog
        dialog = CharacterEditorDialog(self.winfo_toplevel(), "New Character")
        self.wait_window(dialog)
        
        if dialog.result:
            if self.character_manager.add_character(dialog.result):
                self._refresh_characters()
                for card in self._character_cards:
                    if card.character.name == dialog.result.name:
                        self._on_card_select(card)
                        break
            else:
                messagebox.showerror("Error",
                    f"A character named '{dialog.result.name}' already exists.")
    
    def _on_edit_character(self, character: CharacterSpellList):
        from ui.character_editor import CharacterEditorDialog
        dialog = CharacterEditorDialog(self.winfo_toplevel(), "Edit Character", character)
        self.wait_window(dialog)
        
        if dialog.result:
            if self.character_manager.update_character(character.name, dialog.result):
                self._refresh_characters()
            else:
                messagebox.showerror("Error",
                    f"A character named '{dialog.result.name}' already exists.")
    
    def _on_delete_character(self, character: CharacterSpellList):
        if messagebox.askyesno("Confirm Delete",
                               f"Are you sure you want to delete '{character.name}'?\n\n"
                               f"This will remove all {len(character.known_spells)} known spells."):
            self.character_manager.delete_character(character.name)
    
    def _on_remove_spell(self, spell_name: str):
        if self._selected_card:
            self.character_manager.remove_spell_from_character(
                self._selected_card.character.name, spell_name
            )
            updated_char = self.character_manager.get_character(
                self._selected_card.character.name
            )
            if updated_char:
                self._selected_card.character = updated_char
                self.spells_panel.set_character(updated_char)
