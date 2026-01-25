"""
Spell Detail Panel for D&D Spellbook (CustomTkinter version).
Displays detailed information about a selected spell.
"""

import customtkinter as ctk
import tkinter as tk
import re
from typing import Callable, Optional, List, Dict
from spell import Spell, CharacterClass, SpellComparison
from stat_block import StatBlock
from theme import get_theme_manager
from validation import validate_spell_for_character
from character_manager import CharacterManager
from spell_manager import SpellManager
from database import SpellDatabase
from ui.stat_block_display import StatBlockDisplay
from ui.stat_block_editor import StatBlockEditorDialog


class SpellWarningDialog(ctk.CTkToplevel):
    """Dialog for warning about spell compatibility issues."""
    
    def __init__(self, parent, spell_name: str, warnings: List[str]):
        super().__init__(parent)
        
        self.result: bool = False  # True = proceed, False = cancel
        
        self.title("Spell Warning")
        self.geometry("500x400")
        self.minsize(450, 350)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets(spell_name, warnings)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self, spell_name: str, warnings: List[str]):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Warning icon and header
        header_frame = ctk.CTkFrame(container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            header_frame, text="⚠️",
            font=ctk.CTkFont(size=32)
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkLabel(
            header_frame,
            text=f"Warning: Adding '{spell_name}'",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        ).pack(side="left", fill="x", expand=True)
        
        # Warning messages
        theme = get_theme_manager()
        warning_color = theme.get_current_color("button_warning")
        text_secondary = theme.get_text_secondary()

        warnings_frame = ctk.CTkScrollableFrame(container, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
        warnings_frame.pack(fill="both", expand=True, pady=(0, 15))

        for i, warning in enumerate(warnings):
            warning_label = ctk.CTkLabel(
                warnings_frame,
                text=f"• {warning}",
                font=ctk.CTkFont(size=13),
                text_color=warning_color,
                anchor="w",
                wraplength=380,
                justify="left"
            )
            warning_label.pack(fill="x", padx=10, pady=5)
        
        # Question
        ctk.CTkLabel(
            container,
            text="Do you still want to add this spell?",
            font=ctk.CTkFont(size=13),
            text_color=text_secondary
        ).pack(pady=(0, 10))
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            command=self._on_cancel
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_frame, text="Add Anyway", width=100,
            fg_color=theme.get_current_color('button_warning'), hover_color=theme.get_current_color('button_warning_hover'),
            command=self._on_proceed
        ).pack(side="right")
    
    def _on_cancel(self):
        """Cancel adding the spell."""
        self.result = False
        self.destroy()
    
    def _on_proceed(self):
        """Proceed with adding the spell."""
        self.result = True
        self.destroy()


class AddToListDialog(ctk.CTkToplevel):
    """Dialog for selecting which character list to add a spell to."""
    
    def __init__(self, parent, spell_name: str, characters: list):
        super().__init__(parent)
        
        self.result: Optional[str] = None  # Character name selected
        
        self.title(f"Add '{spell_name}' to List")
        self.geometry("350x400")
        self.minsize(300, 300)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Create widgets
        self._create_widgets(spell_name, characters)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self, spell_name: str, characters: list):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        ctk.CTkLabel(
            container, 
            text=f"Select a character to add\n'{spell_name}' to:",
            font=ctk.CTkFont(size=14),
            justify="center"
        ).pack(pady=(0, 15))
        
        if not characters:
            theme = get_theme_manager()
            text_secondary = theme.get_text_secondary()
            ctk.CTkLabel(
                container,
                text="No characters found.\n\nGo to the 'Spell Lists' tab\nto create a character first.",
                font=ctk.CTkFont(size=13),
                text_color=text_secondary,
                justify="center"
            ).pack(pady=30)
            
            btn_text = theme.get_current_color('text_primary')
            ctk.CTkButton(container, text="Close", width=100,
                          text_color=btn_text,
                          command=self.destroy).pack(pady=10)
            return
        
        # Character list
        theme = get_theme_manager()
        scroll = ctk.CTkScrollableFrame(container)
        scroll.pack(fill="both", expand=True, pady=(0, 15))

        btn_text = theme.get_current_color('text_primary')
        for char in characters:
            char_btn = ctk.CTkButton(
                scroll,
                text=f"{char.name}\n{char.display_classes()}",
                height=50,
                anchor="w",
                fg_color=theme.get_current_color('bg_secondary'),
                hover_color=theme.get_current_color('button_hover'),
                text_color=btn_text,
                command=lambda c=char: self._select_character(c.name)
            )
            char_btn.pack(fill="x", pady=3)

        # Cancel button
        ctk.CTkButton(container, text="Cancel", width=100,
                      fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
                      text_color=btn_text,
                      command=self.destroy).pack()
    
    def _select_character(self, name: str):
        """Select a character and close dialog."""
        self.result = name
        self.destroy()


class SpellDetailPanel(ctk.CTkFrame):
    """A panel for displaying detailed spell information."""
    
    def __init__(self, parent, on_edit: Callable[[Spell], None],
                 on_delete: Callable[[Spell], None],
                 on_export: Callable[[Spell], None],
                on_add_to_list: Optional[Callable[[Spell, str], None]] = None,
                character_manager: Optional[CharacterManager] = None,
                spell_manager: Optional[SpellManager] = None,
                on_restore: Optional[Callable[[Spell], None]] = None):
        super().__init__(parent, corner_radius=10)
        
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_export = on_export
        self.on_add_to_list = on_add_to_list
        self.on_restore = on_restore
        self.character_manager = character_manager
        self.spell_manager = spell_manager
        self._current_spell: Optional[Spell] = None
        self._comparison_active = False
        self._comparison_results: Optional[Dict[str, int]] = None
        self._is_primary = True  # Primary panel or compare panel
        self._tooltip_label: Optional[ctk.CTkLabel] = None  # For modified spell tooltip
        
        self._create_widgets()
        self.set_spell(None)
        # Register for theme changes to update colors live
        try:
            self._theme = get_theme_manager()
            self._theme.add_listener(self._on_theme_changed)
        except Exception:
            self._theme = None
    
    def _create_widgets(self):
        """Create the detail view widgets."""
        # Main scrollable container
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Content container
        self.content_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Spell name (title)
        self.name_label = ctk.CTkLabel(
            self.content_frame, text="",
            font=ctk.CTkFont(size=24, weight="bold"),
            anchor="w"
        )
        self.name_label.pack(fill="x", pady=(0, 5))
        
        # Level with colored badge
        self.level_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.level_frame.pack(fill="x", pady=(0, 15))
        
        self.level_badge = ctk.CTkLabel(
            self.level_frame, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=get_theme_manager().get_current_color('accent_primary'),
            corner_radius=6,
            padx=10, pady=3
        )
        self.level_badge.pack(side="left")
        
        # Properties grid (without source and tags)
        self.props_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.props_frame.pack(fill="x", pady=(0, 15))
        
        # Create property rows
        self.prop_labels = {}
        
        # Casting Time row (with separate ritual label)
        ct_row = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        ct_row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            ct_row, text="Casting Time:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, anchor="w"
        ).pack(side="left")
        self.prop_labels["casting_time"] = ctk.CTkLabel(
            ct_row, text="", font=ctk.CTkFont(size=13), anchor="w"
        )
        self.prop_labels["casting_time"].pack(side="left")
        # Ritual label (separate for independent coloring)
        self.ritual_label = ctk.CTkLabel(
            ct_row, text=", Ritual", font=ctk.CTkFont(size=13), anchor="w"
        )
        # Will be packed/unpacked based on spell
        
        # Range row
        range_row = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        range_row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            range_row, text="Range:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, anchor="w"
        ).pack(side="left")
        self.prop_labels["range"] = ctk.CTkLabel(
            range_row, text="", font=ctk.CTkFont(size=13), anchor="w"
        )
        self.prop_labels["range"].pack(side="left", fill="x", expand=True)
        
        # Components row
        comp_row = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        comp_row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            comp_row, text="Components:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, anchor="w"
        ).pack(side="left")
        self.prop_labels["components"] = ctk.CTkLabel(
            comp_row, text="", font=ctk.CTkFont(size=13), anchor="w", wraplength=400
        )
        self.prop_labels["components"].pack(side="left", fill="x", expand=True)
        
        # Duration row (with separate concentration label)
        dur_row = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        dur_row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            dur_row, text="Duration:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, anchor="w"
        ).pack(side="left")
        # Concentration label (separate for independent coloring)
        self.concentration_label = ctk.CTkLabel(
            dur_row, text="Concentration, up to ", font=ctk.CTkFont(size=13), anchor="w"
        )
        # Will be packed/unpacked based on spell
        self.prop_labels["duration"] = ctk.CTkLabel(
            dur_row, text="", font=ctk.CTkFont(size=13), anchor="w"
        )
        self.prop_labels["duration"].pack(side="left", fill="x", expand=True)
        
        # Classes row
        class_row = ctk.CTkFrame(self.props_frame, fg_color="transparent")
        class_row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            class_row, text="Classes:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, anchor="w"
        ).pack(side="left")
        self.prop_labels["classes"] = ctk.CTkLabel(
            class_row, text="", font=ctk.CTkFont(size=13), anchor="w", wraplength=400
        )
        self.prop_labels["classes"].pack(side="left", fill="x", expand=True)
        
        # Separator
        theme = get_theme_manager()
        separator_color = theme.get_current_color("separator")
        separator = ctk.CTkFrame(self.content_frame, height=2, fg_color=separator_color)
        separator.pack(fill="x", pady=15)
        
        # Description container with background
        desc_bg_color = theme.get_current_color('description_bg')
        self.description_frame = ctk.CTkFrame(
            self.content_frame,
            fg_color=desc_bg_color,
            corner_radius=8
        )
        self.description_frame.pack(fill="x", pady=(0, 15))
        
        # Description text using Text widget for colored dice support
        # Colors will be updated based on theme
        self.description_text = tk.Text(
            self.description_frame,
            font=("Segoe UI", 11),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=10,
            pady=10,
            cursor="arrow",
            state=tk.DISABLED,
            height=1,  # Will auto-expand
            borderwidth=0,
            highlightthickness=0
        )
        self.description_text.pack(fill="x", expand=True)
        
        # Configure tags for colored dice - will be updated by _update_description_colors()
        # Apply theme-aware colors to the text widget
        self._update_description_colors()
        
        # Bind to update wraplength dynamically on resize
        self.description_frame.bind("<Configure>", self._on_content_resize)
        
        # Source and Tags section (after description)
        self.meta_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.meta_frame.pack(fill="x", pady=(0, 15))
        
        # Source row
        source_row = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        source_row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            source_row, text="Source:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, anchor="w"
        ).pack(side="left")
        self.source_label = ctk.CTkLabel(
            source_row, text="",
            font=ctk.CTkFont(size=13),
            anchor="w",
            wraplength=400
        )
        self.source_label.pack(side="left", fill="x", expand=True)
        
        # Tags row
        tags_row = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        tags_row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            tags_row, text="Tags:",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=120, anchor="w"
        ).pack(side="left")
        self.tags_label = ctk.CTkLabel(
            tags_row, text="",
            font=ctk.CTkFont(size=13),
            anchor="w",
            wraplength=400
        )
        self.tags_label.pack(side="left", fill="x", expand=True)
        
        # Stat Blocks section (collapsible)
        self._db = SpellDatabase()  # For fetching stat blocks
        self.stat_blocks_section = None  # Will be created when needed
        self._stat_blocks_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self._stat_blocks_frame.pack(fill="x", pady=(0, 15))
        
        # Action buttons
        self.button_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.button_frame.pack(fill="x")
        
        # Left side buttons
        left_btns = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        left_btns.pack(side="left")
        
        self.edit_btn = ctk.CTkButton(
            left_btns, text="Edit", width=80,
            command=self._on_edit_click
        )
        self.edit_btn.pack(side="left", padx=(0, 8))
        
        self.delete_btn = ctk.CTkButton(
            left_btns, text="Delete", width=80,
            fg_color=get_theme_manager().get_current_color('button_danger'), hover_color=get_theme_manager().get_current_color('button_danger_hover'),
            command=self._on_delete_click
        )
        self.delete_btn.pack(side="left", padx=(0, 8))
        
        self.export_btn = ctk.CTkButton(
            left_btns, text="Export", width=80,
            fg_color=get_theme_manager().get_current_color('button_normal'), hover_color=get_theme_manager().get_current_color('button_hover'),
            command=self._on_export_click
        )
        self.export_btn.pack(side="left", padx=(0, 8))
        
        # Restore button (only visible for modified official spells)
        self.restore_btn = ctk.CTkButton(
            left_btns, text="Restore", width=80,
            fg_color=get_theme_manager().get_current_color('button_normal'),
            hover_color=get_theme_manager().get_current_color('button_hover'),
            command=self._on_restore_click
        )
        # Don't pack initially - will be shown/hidden based on spell
        
        # Add to List button (right side)
        if self.on_add_to_list and self.character_manager:
            self.add_to_list_btn = ctk.CTkButton(
                self.button_frame, text="+ Add to List", width=110,
                fg_color=get_theme_manager().get_current_color('button_success'), hover_color=get_theme_manager().get_current_color('button_success_hover'),
                command=self._on_add_to_list_click
            )
            self.add_to_list_btn.pack(side="right")
        
        # Placeholder for when no spell is selected
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        self.placeholder = ctk.CTkLabel(
            self, 
            text="Select a spell to view details",
            font=ctk.CTkFont(size=16),
            text_color=text_secondary
        )
    
    def _bind_modified_tooltip(self, widget, show: bool):
        """Bind or unbind tooltip for modified official spells."""
        if show:
            def show_tooltip(event):
                if self._tooltip_label:
                    self._tooltip_label.destroy()
                self._tooltip_label = ctk.CTkLabel(
                    self.winfo_toplevel(),
                    text="* This official spell has been modified",
                    font=ctk.CTkFont(size=11),
                    fg_color=get_theme_manager().get_current_color('bg_secondary'),
                    corner_radius=4,
                    padx=8, pady=4
                )
                x = event.x_root - self.winfo_toplevel().winfo_x() + 10
                y = event.y_root - self.winfo_toplevel().winfo_y() + 10
                self._tooltip_label.place(x=x, y=y)
            
            def hide_tooltip(event):
                if self._tooltip_label:
                    self._tooltip_label.destroy()
                    self._tooltip_label = None
            
            widget.bind("<Enter>", show_tooltip)
            widget.bind("<Leave>", hide_tooltip)
        else:
            widget.unbind("<Enter>")
            widget.unbind("<Leave>")
            if self._tooltip_label:
                self._tooltip_label.destroy()
                self._tooltip_label = None
    
    def set_spell(self, spell: Optional[Spell]):
        """Set the spell to display, or None to show placeholder."""
        self._current_spell = spell
        self._comparison_active = False
        self._comparison_results = None
        
        if spell is None:
            # Hide content, show placeholder
            self.scroll_frame.pack_forget()
            self.placeholder.place(relx=0.5, rely=0.5, anchor="center")
            return
        
        # Hide placeholder, show content
        self.placeholder.place_forget()
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Update labels - use display_name for asterisk on modified official spells
        display_text = spell.display_name.upper()
        self.name_label.configure(text=display_text)
        
        # Update tooltip if spell is modified
        if spell.is_official and spell.is_modified:
            # Bind tooltip for modified official spell
            self._bind_modified_tooltip(self.name_label, True)
            # Show restore button for modified official spells
            if self.on_restore:
                self.restore_btn.pack(side="left")
        else:
            self._bind_modified_tooltip(self.name_label, False)
            # Hide restore button for non-modified spells
            self.restore_btn.pack_forget()
        
        # Level badge with theme-aware color based on spell level
        level_text = spell.display_level()
        theme = get_theme_manager()
        badge_color_tuple = theme.get_level_color(spell.level)
        mode = ctk.get_appearance_mode().lower()
        badge_color = badge_color_tuple[0] if mode == "light" else badge_color_tuple[1]
        
        self.level_badge.configure(text=level_text, fg_color=badge_color)
        
        # Get theme-aware text color
        theme = get_theme_manager()
        text_color = theme.get_current_color("text_primary")
        
        # Update property values (reset colors)
        # Casting time (without ritual suffix)
        self.prop_labels["casting_time"].configure(
            text=spell.casting_time,
            text_color=text_color
        )
        # Show/hide ritual label
        if spell.ritual:
            self.ritual_label.pack(side="left", after=self.prop_labels["casting_time"])
            self.ritual_label.configure(text_color=text_color)
        else:
            self.ritual_label.pack_forget()
        
        self.prop_labels["range"].configure(
            text=spell.display_range(),
            text_color=text_color
        )
        self.prop_labels["components"].configure(
            text=spell.components or "—",
            text_color=text_color
        )
        
        # Duration (without concentration prefix)
        # Show/hide concentration label
        if spell.concentration:
            self.concentration_label.pack(side="left", before=self.prop_labels["duration"])
            self.concentration_label.configure(text_color=text_color)
            self.prop_labels["duration"].configure(text=spell.duration, text_color=text_color)
        else:
            self.concentration_label.pack_forget()
            self.prop_labels["duration"].configure(text=spell.duration, text_color=text_color)
        
        self.prop_labels["classes"].configure(
            text=spell.display_classes() or "—",
            text_color=text_color
        )
        
        # Update source and tags (now below description)
        self.source_label.configure(
            text=spell.source or "—",
            text_color=text_color
        )
        self.tags_label.configure(
            text=spell.display_tags() or "—",
            text_color=text_color
        )
        
        # Update stat blocks section
        self._update_stat_blocks_section(spell)
        
        # Update description
        self._update_description(spell.display_description())
    
    def _update_description(self, text: str, damage_color: Optional[str] = None):
        """Update description text, optionally coloring damage dice."""
        self.description_text.configure(state=tk.NORMAL)
        self.description_text.delete("1.0", tk.END)
        
        if damage_color:
            # Get the "better" color from theme for comparison
            theme = get_theme_manager()
            better_color = theme.get_current_color("compare_better")
            
            # Find and color damage dice
            dice_pattern = r'\d+d\d+'
            last_end = 0
            for match in re.finditer(dice_pattern, text, re.IGNORECASE):
                # Insert text before the dice
                if match.start() > last_end:
                    self.description_text.insert(tk.END, text[last_end:match.start()], "normal")
                # Insert the dice with color - use "better" tag if it's the better color
                tag = "better" if damage_color == better_color else "worse"
                self.description_text.insert(tk.END, match.group(), tag)
                last_end = match.end()
            # Insert remaining text
            if last_end < len(text):
                self.description_text.insert(tk.END, text[last_end:], "normal")
        else:
            self.description_text.insert(tk.END, text, "normal")
        
        self.description_text.configure(state=tk.DISABLED)
        
        # Auto-resize height
        self._resize_description_text()
    
    def _resize_description_text(self):
        """Resize description text widget to fit content."""
        self.description_text.configure(state=tk.NORMAL)
        # Count lines needed
        self.description_text.update_idletasks()
        try:
            # Count display lines, respecting word wrap
            result = self.description_text.count("1.0", "end-1c", "displaylines")
            if result:
                line_count = result[0]
            else:
                raise tk.TclError  # Fallback if count returns None/empty
        except tk.TclError:
            # Fallback to logical lines if count is unavailable
            line_count = int(self.description_text.index('end-1c').split('.')[0])
        # Set height to fit all content (no maximum cap)
        height = max(3, line_count + 1)
        self.description_text.configure(height=height, state=tk.DISABLED)
    
    def apply_comparison(self, other_spell: Spell, is_primary: bool = True):
        """Apply comparison coloring against another spell."""
        if not self._current_spell:
            return
        
        self._comparison_active = True
        self._is_primary = is_primary
        
        # Get comparison results comparing this panel's spell against the other
        # -1 means self._current_spell is better (green for this panel)
        # 1 means other_spell is better (red for this panel)
        # 0 means equal (no color)
        results = SpellComparison.compare_all(self._current_spell, other_spell)
        
        self._comparison_results = results
        
        # Apply colors
        self._apply_comparison_colors()
    
    def _apply_comparison_colors(self):
        """Apply comparison colors to property labels."""
        if not self._current_spell or not self._comparison_results:
            return
        
        spell = self._current_spell
        results = self._comparison_results
        
        # Get colors from theme
        theme = get_theme_manager()
        better_color = theme.get_current_color("compare_better")
        worse_color = theme.get_current_color("compare_worse")
        default_color = theme.get_current_color("text_primary")
        
        # Helper to get color
        def get_color(result: int) -> Optional[str]:
            if result < 0:
                return better_color  # This spell is better
            elif result > 0:
                return worse_color   # Other spell is better
            return None  # Equal
        
        # Casting time (separate from ritual)
        ct_color = get_color(results.get('casting_time', 0))
        self.prop_labels["casting_time"].configure(
            text_color=ct_color if ct_color else default_color
        )
        
        # Ritual (separate coloring)
        if spell.ritual:
            ritual_result = results.get('ritual', 0)
            if ritual_result < 0:  # This spell has ritual advantage
                self.ritual_label.configure(text_color=better_color)
            elif ritual_result > 0:  # Other spell has ritual, this one doesn't (shouldn't happen if this has ritual)
                self.ritual_label.configure(text_color=worse_color)
            else:
                self.ritual_label.configure(text_color=default_color)
        
        # Range
        range_color = get_color(results.get('range', 0))
        self.prop_labels["range"].configure(
            text_color=range_color if range_color else default_color
        )
        
        # Components - combine component count and cost
        comp_result = results.get('components', 0)
        cost_result = results.get('component_cost', 0)
        # If either is better, use that; if one better and one worse, prioritize cost
        if cost_result < 0:
            comp_color = better_color
        elif cost_result > 0:
            comp_color = worse_color
        elif comp_result < 0:
            comp_color = better_color
        elif comp_result > 0:
            comp_color = worse_color
        else:
            comp_color = None
        self.prop_labels["components"].configure(
            text_color=comp_color if comp_color else default_color
        )
        
        # Duration (separate from concentration)
        dur_result = results.get('duration', 0)
        dur_color = get_color(dur_result)
        self.prop_labels["duration"].configure(
            text_color=dur_color if dur_color else default_color
        )
        
        # Concentration (separate coloring)
        if spell.concentration:
            conc_result = results.get('concentration', 0)
            if conc_result < 0:  # This spell doesn't have concentration disadvantage (shouldn't happen)
                self.concentration_label.configure(text_color=better_color)
            elif conc_result > 0:  # This spell has concentration, other doesn't
                self.concentration_label.configure(text_color=worse_color)
            else:  # Both have concentration
                self.concentration_label.configure(text_color=default_color)
        
        # Damage in description
        damage_result = results.get('damage', 0)
        if damage_result != 0:
            damage_color = better_color if damage_result < 0 else worse_color
            self._update_description(spell.display_description(), damage_color)
        else:
            self._update_description(spell.display_description())
    
    def clear_comparison(self):
        """Clear comparison coloring and reset to normal display."""
        self._comparison_active = False
        self._comparison_results = None
        
        if self._current_spell:
            # Get theme-aware text color
            theme = get_theme_manager()
            text_color = theme.get_current_color("text_primary")
            
            # Reset colors to theme default
            self.prop_labels["casting_time"].configure(text_color=text_color)
            self.ritual_label.configure(text_color=text_color)
            self.prop_labels["range"].configure(text_color=text_color)
            self.prop_labels["components"].configure(text_color=text_color)
            self.prop_labels["duration"].configure(text_color=text_color)
            self.concentration_label.configure(text_color=text_color)
            self.prop_labels["classes"].configure(text_color=text_color)
            self.source_label.configure(text_color=text_color)
            self.tags_label.configure(text_color=text_color)
            
            # Reset description
            self._update_description(self._current_spell.display_description())

    def _on_theme_changed(self):
        """Reconfigure labels, buttons, and description colors on theme change."""
        try:
            theme = get_theme_manager()
            text_color = theme.get_current_color('text_primary')

            # Update labels and property text colors
            try:
                self.name_label.configure(text_color=text_color)
            except Exception:
                pass

            for key, lbl in self.prop_labels.items():
                try:
                    lbl.configure(text_color=text_color)
                except Exception:
                    pass

            try:
                self.source_label.configure(text_color=text_color)
                self.tags_label.configure(text_color=text_color)
            except Exception:
                pass

            # Action buttons
            try:
                self.edit_btn.configure(fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'))
                self.delete_btn.configure(fg_color=theme.get_current_color('button_danger'), hover_color=theme.get_current_color('button_danger_hover'))
                self.export_btn.configure(fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'))
                if hasattr(self, 'add_to_list_btn'):
                    self.add_to_list_btn.configure(fg_color=theme.get_current_color('button_success'), hover_color=theme.get_current_color('button_success_hover'))
            except Exception:
                pass

            # Update description text tags and background
            self._update_description_colors()
            # Update description frame background
            try:
                self.description_frame.configure(fg_color=theme.get_current_color('description_bg'))
            except Exception:
                pass

            # Ensure scroll frame background uses transparent so root shows through
            try:
                if hasattr(self, 'scroll_frame'):
                    self.scroll_frame.configure(fg_color="transparent")
            except Exception:
                pass

            # Update placeholder color
            try:
                self.placeholder.configure(text_color=theme.get_text_secondary())
            except Exception:
                pass

            # Update level badge color for current spell (if any)
            try:
                if self._current_spell is not None:
                    badge_color_tuple = theme.get_level_color(self._current_spell.level)
                    mode = ctk.get_appearance_mode().lower()
                    badge_color = badge_color_tuple[0] if mode == 'light' else badge_color_tuple[1]
                    self.level_badge.configure(fg_color=badge_color)
            except Exception:
                pass
        except Exception:
            pass

    def destroy(self):
        """Remove theme listener when destroyed."""
        try:
            if hasattr(self, '_theme') and self._theme:
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()
    
    def _on_content_resize(self, event):
        """Update description text widget width when description frame is resized."""
        # Account for padding - resize the text widget width
        new_width = max(100, event.width - 20)
        self.description_text.configure(width=new_width // 8)  # Approximate character width
        self._resize_description_text()
    
    def _update_description_colors(self):
        """Update description text widget colors based on current theme."""
        theme = get_theme_manager()

        # Use current appearance colors
        bg_color = theme.get_current_color('description_bg')
        fg_color = theme.get_current_color('text_primary')
        better = theme.get_current_color('compare_better')
        worse = theme.get_current_color('compare_worse')

        self.description_text.configure(bg=bg_color, fg=fg_color)
        self.description_text.tag_configure("normal", foreground=fg_color)
        self.description_text.tag_configure("better", foreground=better)
        self.description_text.tag_configure("worse", foreground=worse)
    
    def _on_edit_click(self):
        """Handle edit button click."""
        if self._current_spell:
            self.on_edit(self._current_spell)
    
    def _on_delete_click(self):
        """Handle delete button click."""
        if self._current_spell:
            self.on_delete(self._current_spell)
    
    def _on_export_click(self):
        """Handle export button click."""
        if self._current_spell:
            self.on_export(self._current_spell)
    
    def _on_restore_click(self):
        """Handle restore button click for modified official spells."""
        if self._current_spell and self.on_restore:
            if self._current_spell.is_official and self._current_spell.is_modified:
                # Confirm restoration
                from tkinter import messagebox
                if messagebox.askyesno(
                    "Restore Spell",
                    f"Restore '{self._current_spell.name}' to its original official version?\n\n"
                    "This will undo any modifications you made.",
                    parent=self.winfo_toplevel()
                ):
                    self.on_restore(self._current_spell)
    
    def _on_add_to_list_click(self):
        """Handle add to list button click."""
        if self._current_spell and self.character_manager:
            characters = self.character_manager.characters
            dialog = AddToListDialog(
                self.winfo_toplevel(),
                self._current_spell.name,
                characters
            )
            self.wait_window(dialog)
            
            if dialog.result:
                # Get the selected character
                character = self.character_manager.get_character(dialog.result)
                if character:
                    # Check for warnings
                    warnings = self._validate_spell_for_character(
                        self._current_spell, character
                    )
                    
                    if warnings:
                        # Show warning dialog
                        warning_dialog = SpellWarningDialog(
                            self.winfo_toplevel(),
                            self._current_spell.name,
                            warnings
                        )
                        self.wait_window(warning_dialog)
                        
                        if not warning_dialog.result:
                            return  # User cancelled
                    
                    # Add the spell (if callback provided)
                    if self.on_add_to_list:
                        self.on_add_to_list(self._current_spell, dialog.result)
    
    def _on_edit_stat_block(self, stat_block: StatBlock):
        """Handle edit button click on a stat block."""
        if not stat_block or not self._current_spell:
            return
        
        # Open the stat block editor dialog
        dialog = StatBlockEditorDialog(
            self.winfo_toplevel(),
            title=f"Edit Stat Block: {stat_block.name}",
            stat_block=stat_block
        )
        self.wait_window(dialog)
        
        if dialog.result:
            # Get the edited stat block
            edited_stat_block = dialog.result
            
            # Update the stat block in the database
            if edited_stat_block.id:
                success = self._db.update_stat_block(
                    edited_stat_block.id,
                    edited_stat_block.to_dict()
                )
                
                if success:
                    # If this is an official spell, mark it as modified
                    if self._current_spell.is_official and self.spell_manager:
                        # Create a new spell with is_modified=True
                        modified_spell = Spell(
                            name=self._current_spell.name,
                            level=self._current_spell.level,
                            casting_time=self._current_spell.casting_time,
                            ritual=self._current_spell.ritual,
                            range_value=self._current_spell.range_value,
                            components=self._current_spell.components,
                            duration=self._current_spell.duration,
                            concentration=self._current_spell.concentration,
                            classes=list(self._current_spell.classes),
                            description=self._current_spell.description,
                            source=self._current_spell.source,
                            tags=list(self._current_spell.tags),
                            is_modified=True  # Mark as modified
                        )
                        self.spell_manager.update_spell(
                            self._current_spell.name, 
                            modified_spell
                        )
                        # Update the current spell reference
                        self._current_spell = modified_spell
                    
                    # Refresh the stat blocks section
                    self._update_stat_blocks_section(self._current_spell)
    
    def _validate_spell_for_character(self, spell: Spell, character) -> List[str]:
        """
        Validate if a spell is appropriate for a character.
        Returns a list of warning messages, empty if no issues.
        """
        # Use shared validation utility (no settings filtering here - that's done in main_window)
        return validate_spell_for_character(spell, character, self.spell_manager)
    
    def _update_stat_blocks_section(self, spell: Spell):
        """Update the stat blocks section for the given spell."""
        # Clear existing stat block widgets
        for widget in self._stat_blocks_frame.winfo_children():
            widget.destroy()
        
        # Load stat blocks for this spell
        stat_blocks = self._db.get_stat_blocks_for_spell_by_name(spell.name)
        
        if not stat_blocks:
            # No stat blocks - hide the section
            self._stat_blocks_frame.pack_forget()
            return
        
        # Show the frame
        self._stat_blocks_frame.pack(fill="x", pady=(0, 10), after=self.tags_label.master)
        
        # Create header with collapse toggle
        header_frame = ctk.CTkFrame(self._stat_blocks_frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(3, 0))
        
        # Section title
        title_label = ctk.CTkLabel(
            header_frame,
            text=f"SUMMONED CREATURES ({len(stat_blocks)})",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        title_label.pack(side="left")
        
        # Collapse toggle button
        self._stat_blocks_expanded = True
        toggle_btn = ctk.CTkButton(
            header_frame,
            text="▼",
            width=30,
            height=25,
            fg_color="transparent",
            hover_color=("gray70", "gray30"),
            command=lambda: self._toggle_stat_blocks()
        )
        toggle_btn.pack(side="right")
        self._stat_blocks_toggle_btn = toggle_btn
        
        # Container for stat blocks (can be collapsed) - minimal padding
        self._stat_blocks_container = ctk.CTkFrame(self._stat_blocks_frame, fg_color="transparent")
        self._stat_blocks_container.pack(fill="x", pady=(2, 0))
        
        # Add each stat block (convert from dict to StatBlock object)
        for stat_block_dict in stat_blocks:
            stat_block_obj = StatBlock.from_dict(stat_block_dict)
            display = StatBlockDisplay(
                self._stat_blocks_container,
                stat_block=stat_block_obj,
                on_edit=self._on_edit_stat_block,
                collapsed=len(stat_blocks) > 1  # Collapse by default if multiple
            )
            display.pack(fill="x", pady=(2, 2))
    
    def _toggle_stat_blocks(self):
        """Toggle visibility of stat blocks section."""
        self._stat_blocks_expanded = not self._stat_blocks_expanded
        
        if self._stat_blocks_expanded:
            self._stat_blocks_container.pack(fill="x", pady=(5, 0))
            self._stat_blocks_toggle_btn.configure(text="▼")
        else:
            self._stat_blocks_container.pack_forget()
            self._stat_blocks_toggle_btn.configure(text="▶")


class SpellPopupDialog(ctk.CTkToplevel):
    """Read-only popup dialog for viewing spell details."""
    
    def __init__(self, parent, spell: Spell):
        super().__init__(parent)
        
        self.spell = spell
        self.theme = get_theme_manager()
        
        self.title(spell.name)
        self.geometry("550x650")
        self.minsize(450, 500)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        # Bind Escape to close
        self.bind("<Escape>", lambda e: self.destroy())
    
    def _render_formatted_text(self, parent, text: str):
        """Render text with *bold* markdown formatting."""
        import re
        
        # Split by double newlines to get paragraphs
        paragraphs = text.split('\n\n')
        
        for para_idx, paragraph in enumerate(paragraphs):
            lines = paragraph.strip().split('\n')
            combined_text = ' '.join(line.strip() for line in lines if line.strip())
            
            if not combined_text:
                continue
            
            # Check for bullet points
            if combined_text.startswith('•') or combined_text.startswith('-'):
                bullet_text = combined_text.lstrip('•- ')
                combined_text = f"  • {bullet_text}"
            
            pady = (6, 2) if para_idx > 0 else (2, 2)
            
            # Find all *text* patterns for bold
            pattern = r'\*([^*]+)\*'
            parts = re.split(pattern, combined_text)
            
            if len(parts) == 1:
                # No formatting found, just render plain text
                ctk.CTkLabel(
                    parent,
                    text=combined_text,
                    font=ctk.CTkFont(size=12),
                    wraplength=480,
                    justify="left"
                ).pack(anchor="w", pady=pady)
            else:
                # Has formatting - use a Text widget for proper inline rendering
                text_widget = tk.Text(
                    parent,
                    wrap="word",
                    font=ctk.CTkFont(size=12),
                    bg=self.theme.get_current_color('bg_secondary'),
                    fg=self.theme.get_current_color('text_primary'),
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=0,
                    padx=0,
                    pady=2,
                    cursor="arrow"
                )
                
                # Configure tags
                text_widget.tag_configure("bold", font=ctk.CTkFont(size=12, weight="bold", slant="italic"))
                text_widget.tag_configure("normal", font=ctk.CTkFont(size=12))
                
                # Insert parts with formatting
                for i, part in enumerate(parts):
                    if not part:
                        continue
                    is_bold = (i % 2 == 1)
                    tag = "bold" if is_bold else "normal"
                    text_widget.insert("end", part, tag)
                
                # Calculate height
                text_widget.update_idletasks()
                total_chars = sum(len(p) for p in parts if p)
                estimated_lines = max(1, (total_chars // 60) + 1)
                
                text_widget.configure(state="disabled", height=estimated_lines)
                text_widget.pack(fill="x", anchor="w", pady=pady)
    
    def _create_widgets(self):
        """Create dialog widgets."""
        spell = self.spell
        
        # Main scrollable container
        scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Spell name (title)
        ctk.CTkLabel(
            scroll_frame,
            text=spell.name.upper(),
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w"
        ).pack(fill="x", pady=(0, 5))
        
        # Level badge
        level_text = spell.display_level()
        badge_color_tuple = self.theme.get_level_color(spell.level)
        mode = ctk.get_appearance_mode().lower()
        badge_color = badge_color_tuple[0] if mode == "light" else badge_color_tuple[1]
        
        badge_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        badge_frame.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(
            badge_frame,
            text=level_text,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=badge_color,
            text_color="white",
            corner_radius=5,
            padx=8, pady=2
        ).pack(side="left")
        
        # Properties section
        props_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        props_frame.pack(fill="x", pady=(0, 12))
        
        props = [
            ("Casting Time", spell.casting_time + (" (Ritual)" if spell.ritual else "")),
            ("Range", spell.display_range()),
            ("Components", spell.components or "—"),
            ("Duration", ("Concentration, " if spell.concentration else "") + spell.duration),
        ]
        
        for i, (label, value) in enumerate(props):
            row = ctk.CTkFrame(props_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            
            ctk.CTkLabel(
                row, text=f"{label}:",
                font=ctk.CTkFont(size=12, weight="bold"),
                width=100, anchor="w"
            ).pack(side="left")
            
            ctk.CTkLabel(
                row, text=value,
                font=ctk.CTkFont(size=12),
                anchor="w",
                wraplength=350
            ).pack(side="left", fill="x", expand=True)
        
        # Classes section
        if spell.classes:
            classes_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            classes_frame.pack(fill="x", pady=(0, 12))
            
            ctk.CTkLabel(
                classes_frame, text="Classes:",
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            ).pack(side="left")
            
            classes_text = ", ".join(c.value for c in spell.classes)
            ctk.CTkLabel(
                classes_frame, text=classes_text,
                font=ctk.CTkFont(size=12),
                anchor="w",
                wraplength=400
            ).pack(side="left", padx=(5, 0))
        
        # Description
        desc_label = ctk.CTkLabel(
            scroll_frame, text="Description",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        desc_label.pack(fill="x", pady=(0, 5))
        
        # Create a frame for the formatted description
        desc_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        desc_frame.pack(fill="both", expand=True, pady=(0, 12), padx=2)
        
        # Render description with formatting
        desc_text = spell.description or ""
        if desc_text:
            inner_frame = ctk.CTkFrame(desc_frame, fg_color="transparent")
            inner_frame.pack(fill="both", expand=True, padx=10, pady=10)
            self._render_formatted_text(inner_frame, desc_text)
        
        # Source
        if spell.source:
            source_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            source_frame.pack(fill="x", pady=(0, 5))
            
            ctk.CTkLabel(
                source_frame, text="Source:",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.theme.get_text_secondary(),
                anchor="w"
            ).pack(side="left")
            
            ctk.CTkLabel(
                source_frame, text=spell.source,
                font=ctk.CTkFont(size=11),
                text_color=self.theme.get_text_secondary(),
                anchor="w"
            ).pack(side="left", padx=(5, 0))
        
        # Close button
        btn_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Close", width=100,
            command=self.destroy
        ).pack()

