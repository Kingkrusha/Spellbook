"""
Spell List Panel for D&D Spellbook (CustomTkinter version).
Displays a scrollable list of spells with selection support.
"""

import customtkinter as ctk
import tkinter as tk
from typing import List, Callable, Optional
from spell import Spell
from theme import get_theme_manager


class SpellListPanel(ctk.CTkFrame):
    """A scrollable list panel for displaying and selecting spells."""
    
    def __init__(self, parent, on_select: Callable[[Optional[Spell]], None],
                 on_right_click: Optional[Callable[[Spell, int, int], None]] = None):
        super().__init__(parent, corner_radius=10)
        
        self.on_select = on_select
        self.on_right_click = on_right_click  # Callback for right-click (spell, x, y)
        self._spells: List[Spell] = []
        self._selected_index: Optional[int] = None
        self._spell_buttons: List[ctk.CTkButton] = []
        
        self._create_widgets()
        # Register theme listener so this panel updates live when theme changes
        try:
            self._theme = get_theme_manager()
            self._theme.add_listener(self._on_theme_changed)
        except Exception:
            self._theme = None
    
    def _create_widgets(self):
        """Create the scrollable spell list."""
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))
        
        ctk.CTkLabel(header_frame, text="Spells", 
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        self.count_label = ctk.CTkLabel(header_frame, text="0 spells",
                                         font=ctk.CTkFont(size=12),
                                         text_color=text_secondary)
        self.count_label.pack(side="right")
        
        # Scrollable frame for spell list
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _create_spell_button(self, spell: Spell, index: int) -> ctk.CTkButton:
        """Create a button for a spell."""
        theme = get_theme_manager()

        # Build display text with indicators
        # Use display_name which adds asterisk for modified official spells
        display_name = spell.display_name
        indicators = []
        if spell.ritual:
            indicators.append("R")
        if spell.concentration:
            indicators.append("C")

        if indicators:
            indicator_text = f"  ({', '.join(indicators)})"
        else:
            indicator_text = ""

        # Level indicator (unused in button but kept for clarity)
        if spell.level == 0:
            level_text = "Cantrip"
        else:
            level_text = f"Lvl {spell.level}"

        btn = ctk.CTkButton(
            self.scroll_frame,
            text=f"{display_name}{indicator_text}",
            anchor="w",
            height=40,
            corner_radius=8,
            fg_color=("transparent" if index != self._selected_index else theme.get_current_color('accent_primary')),
            hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            font=ctk.CTkFont(size=13),
            command=lambda i=index: self._on_spell_click(i)
        )
        btn.pack(fill="x", pady=2)

        # Bind right-click event
        if self.on_right_click:
            btn.bind("<Button-3>", lambda e, i=index: self._on_spell_right_click(e, i))
            # Also bind to the internal button label for better coverage
            for child in btn.winfo_children():
                child.bind("<Button-3>", lambda e, i=index: self._on_spell_right_click(e, i))

        return btn
    
    def _on_spell_right_click(self, event, index: int):
        """Handle right-click on a spell button."""
        if self.on_right_click and 0 <= index < len(self._spells):
            # Get screen coordinates for the menu
            x = event.x_root
            y = event.y_root
            self.on_right_click(self._spells[index], x, y)
    
    def _on_spell_click(self, index: int):
        """Handle spell button click."""
        theme = get_theme_manager()
        
        # Update selection
        old_index = self._selected_index
        self._selected_index = index
        
        # Update button colors
        if old_index is not None and old_index < len(self._spell_buttons):
            self._spell_buttons[old_index].configure(fg_color="transparent")
        
        if index < len(self._spell_buttons):
            self._spell_buttons[index].configure(fg_color=theme.get_current_color('accent_primary'))
        
        # Notify callback
        if 0 <= index < len(self._spells):
            self.on_select(self._spells[index])
    
    def set_spells(self, spells: List[Spell], reset_scroll: bool = True):
        """Set the list of spells to display.
        
        Args:
            spells: List of spells to display
            reset_scroll: If True, scroll position resets to top
        """
        # Remember current selection name
        current_name = None
        if self._selected_index is not None and self._selected_index < len(self._spells):
            current_name = self._spells[self._selected_index].name
        
        self._spells = spells
        self._selected_index = None
        
        # Clear existing buttons
        for btn in self._spell_buttons:
            btn.destroy()
        self._spell_buttons = []
        
        # Find new index for previously selected spell
        new_selected_index = None
        if current_name:
            for i, spell in enumerate(spells):
                if spell.name.lower() == current_name.lower():
                    new_selected_index = i
                    break
        
        self._selected_index = new_selected_index
        
        # Create new buttons
        for i, spell in enumerate(spells):
            btn = self._create_spell_button(spell, i)
            self._spell_buttons.append(btn)
        
        # Update count
        count = len(spells)
        self.count_label.configure(text=f"{count} spell{'s' if count != 1 else ''}")
        # Refresh count label color in case theme changed
        try:
            theme = get_theme_manager()
            self.count_label.configure(text_color=theme.get_text_secondary())
        except Exception:
            pass
        
        # Reset scroll position to top
        if reset_scroll:
            self.scroll_to_top()
        
        # Don't notify if selection was lost due to filtering
        # The detail panel should keep showing the current spell
    
    def select_spell(self, name: str) -> bool:
        """Select a spell by name. Returns True if found."""
        for i, spell in enumerate(self._spells):
            if spell.name.lower() == name.lower():
                self._on_spell_click(i)
                return True
        return False
    
    def get_selected_spell(self) -> Optional[Spell]:
        """Return the currently selected spell, or None."""
        if self._selected_index is not None and self._selected_index < len(self._spells):
            return self._spells[self._selected_index]
        return None
    
    def clear_selection(self):
        """Clear the current selection."""
        if self._selected_index is not None and self._selected_index < len(self._spell_buttons):
            self._spell_buttons[self._selected_index].configure(fg_color="transparent")
        self._selected_index = None
        self.on_select(None)
    
    def scroll_to_top(self):
        """Scroll the spell list to the top."""
        # CTkScrollableFrame uses an internal canvas for scrolling
        # Access it via _parent_canvas attribute
        try:
            self.scroll_frame._parent_canvas.yview_moveto(0)
        except (AttributeError, tk.TclError):
            pass  # Ignore if canvas not available yet

    def _on_theme_changed(self):
        """Reconfigure spell buttons and labels when the theme changes."""
        try:
            theme = get_theme_manager()
            # Update count label color
            try:
                self.count_label.configure(text_color=theme.get_text_secondary())
            except Exception:
                pass

            # Update each button's hover/text colors and fg selection
            for i, btn in enumerate(self._spell_buttons):
                try:
                    btn.configure(hover_color=theme.get_current_color('button_hover'), text_color=theme.get_current_color('text_primary'))
                    if i == self._selected_index:
                        btn.configure(fg_color=theme.get_current_color('accent_primary'))
                    else:
                        btn.configure(fg_color="transparent")
                except Exception:
                    pass
            # Ensure scroll frame background is transparent so main bg shows through
            try:
                if hasattr(self, 'scroll_frame'):
                    self.scroll_frame.configure(fg_color="transparent")
            except Exception:
                pass
        except Exception:
            pass

    def destroy(self):
        """Clean up theme listener when panel is destroyed."""
        try:
            if hasattr(self, '_theme') and self._theme:
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()
