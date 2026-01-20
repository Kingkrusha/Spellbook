"""
Character Editor Dialog for D&D Spellbook.
Dialog for creating and editing character spell lists.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, List, Callable
from character import CharacterSpellList, ClassLevel
from spell import CharacterClass
from theme import get_theme_manager


class ClassLevelRow(ctk.CTkFrame):
    """A row widget for editing a class and its level."""
    
    def __init__(self, parent, class_level: Optional[ClassLevel] = None, 
                 on_delete: Optional[Callable[..., None]] = None, is_primary: bool = False):
        super().__init__(parent, fg_color="transparent")
        
        self.on_delete = on_delete
        self.is_primary = is_primary
        
        # Class dropdown
        self.class_var = ctk.StringVar(
            value=class_level.character_class.value if class_level else "Wizard"
        )
        class_combo = ctk.CTkComboBox(
            self, variable=self.class_var,
            values=[c.value for c in CharacterClass.all_classes()],
            width=120
        )
        class_combo.pack(side="left", padx=(0, 10))
        self.class_combo = class_combo
        
        # Level label and spinbox-like controls
        ctk.CTkLabel(self, text="Level:", font=ctk.CTkFont(size=12)).pack(
            side="left", padx=(0, 5))
        
        self.level_var = ctk.StringVar(
            value=str(class_level.level if class_level else 1)
        )
        
        theme = get_theme_manager()
        btn_text = theme.get_current_color('text_primary')
        
        # Decrease button
        ctk.CTkButton(self, text="-", width=30, height=30,
                      text_color=btn_text,
                      command=self._decrease_level).pack(side="left")
        
        # Level entry
        self.level_entry = ctk.CTkEntry(self, textvariable=self.level_var, 
                                         width=50, justify="center")
        self.level_entry.pack(side="left", padx=5)
        
        # Increase button
        ctk.CTkButton(self, text="+", width=30, height=30,
                      text_color=btn_text,
                      command=self._increase_level).pack(side="left")
        
        # Delete button (not shown for primary class)
        if not is_primary:
            # Use themed danger colors for delete
            self.delete_btn = ctk.CTkButton(self, text="✕", width=30, height=30,
                                            fg_color=theme.get_current_color('button_danger'), hover_color=theme.get_current_color('button_danger_hover'),
                                            text_color=btn_text,
                                            command=self._on_delete)
            self.delete_btn.pack(side="left", padx=(15, 0))
        else:
            # Primary label
            text_secondary = theme.get_text_secondary()
            self.primary_label = ctk.CTkLabel(self, text="(Primary)", font=ctk.CTkFont(size=11),
                                              text_color=text_secondary)
            self.primary_label.pack(side="left", padx=(15, 0))

    def apply_theme(self, theme):
        """Apply theme colors to widgets in this row."""
        try:
            input_bg = theme.get_current_color('bg_input')
            input_text = theme.get_current_color('text_primary')
            border = theme.get_current_color('border')

            try:
                self.class_combo.configure(fg_color=input_bg, text_color=input_text, border_color=border)
            except Exception:
                pass

            try:
                self.level_entry.configure(fg_color=input_bg, text_color=input_text, border_color=border)
            except Exception:
                pass

            if hasattr(self, 'delete_btn'):
                try:
                    self.delete_btn.configure(fg_color=theme.get_current_color('button_danger'))
                except Exception:
                    pass

            if hasattr(self, 'primary_label'):
                try:
                    self.primary_label.configure(text_color=theme.get_text_secondary())
                except Exception:
                    pass
        except Exception:
            pass
    
    def _decrease_level(self):
        """Decrease the level by 1."""
        try:
            level = int(self.level_var.get())
            if level > 1:
                self.level_var.set(str(level - 1))
        except ValueError:
            self.level_var.set("1")
    
    def _increase_level(self):
        """Increase the level by 1."""
        try:
            level = int(self.level_var.get())
            if level < 20:
                self.level_var.set(str(level + 1))
        except ValueError:
            self.level_var.set("1")
    
    def _on_delete(self):
        """Handle delete button click."""
        if self.on_delete:
            self.on_delete(self)
    
    def get_class_level(self) -> ClassLevel:
        """Get the ClassLevel from current values."""
        try:
            level = int(self.level_var.get())
            level = max(1, min(20, level))
        except ValueError:
            level = 1
        
        return ClassLevel(
            character_class=CharacterClass.from_string(self.class_var.get()),
            level=level
        )


class CharacterEditorDialog(ctk.CTkToplevel):
    """A dialog for creating or editing a character spell list."""
    
    def __init__(self, parent, title: str, character: Optional[CharacterSpellList] = None):
        super().__init__(parent)
        
        self.result: Optional[CharacterSpellList] = None
        self._editing = character is not None
        self._original_character = character
        self._class_rows: List[ClassLevelRow] = []
        
        # Window setup
        self.title(title)
        self.geometry("500x450")
        self.minsize(450, 400)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Create widgets
        self._create_widgets()
        
        # Populate if editing
        if character:
            self._populate_from_character(character)
        else:
            # Add default primary class row
            self._add_class_row(is_primary=True)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        # Focus on name entry
        self.name_entry.focus_set()
    
    def _create_widgets(self):
        """Create all dialog widgets."""
        # Main container - use grid for better control
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        container.grid_rowconfigure(2, weight=1)  # Classes frame expands
        container.grid_columnconfigure(0, weight=1)
        
        # Name section
        name_frame = ctk.CTkFrame(container, fg_color="transparent")
        name_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        ctk.CTkLabel(name_frame, text="Character Name *",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(
            fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(name_frame, height=38,
                                        placeholder_text="Enter character name...")
        self.name_entry.pack(fill="x")
        
        # Classes header
        classes_header = ctk.CTkFrame(container, fg_color="transparent")
        classes_header.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        ctk.CTkLabel(classes_header, text="Classes *",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        
        self.add_class_btn = ctk.CTkButton(
            classes_header, text="+ Add Class", width=100,
            fg_color=get_theme_manager().get_current_color('button_success'), hover_color=get_theme_manager().get_current_color('button_success_hover'),
            command=lambda: self._add_class_row(is_primary=False)
        )
        self.add_class_btn.pack(side="right")
        
        # Classes container (scrollable)
        self.classes_frame = ctk.CTkScrollableFrame(container, height=120)
        self.classes_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 15))
        
        # Button frame - at bottom, doesn't expand
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.grid(row=3, column=0, sticky="ew")

        # Action buttons
        theme = get_theme_manager()
        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(button_frame, text="Cancel", width=100,
                      fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
                      text_color=btn_text,
                      command=self._on_cancel).pack(side="right", padx=(10, 0))
        ctk.CTkButton(button_frame, text="Save Character", width=120,
                      text_color=btn_text,
                      command=self._on_save).pack(side="right")
        # Register for theme changes so open dialog updates live
        try:
            self._theme = get_theme_manager()
            self._theme.add_listener(self._on_theme_changed)
            # apply immediately
            self._on_theme_changed()
        except Exception:
            self._theme = None
    
    def _add_class_row(self, class_level: Optional[ClassLevel] = None, is_primary: bool = False):
        """Add a new class row to the classes list."""
        row = ClassLevelRow(
            self.classes_frame,
            class_level=class_level,
            on_delete=self._remove_class_row,
            is_primary=is_primary
        )
        row.pack(fill="x", pady=5)
        self._class_rows.append(row)
        
        # Update add button state (max 9 classes for multiclass)
        if len(self._class_rows) >= 9:
            self.add_class_btn.configure(state="disabled")
    
    def _remove_class_row(self, row: ClassLevelRow):
        """Remove a class row from the list."""
        if row in self._class_rows:
            self._class_rows.remove(row)
            row.destroy()
            
            # Re-enable add button
            if len(self._class_rows) < 9:
                self.add_class_btn.configure(state="normal")
    
    def _populate_from_character(self, character: CharacterSpellList):
        """Populate form fields from an existing character."""
        self.name_entry.insert(0, character.name)
        
        # Add class rows
        for i, class_level in enumerate(character.classes):
            self._add_class_row(class_level=class_level, is_primary=(i == 0))
    
    def _validate(self) -> bool:
        """Validate form inputs. Returns True if valid."""
        errors = []
        
        if not self.name_entry.get().strip():
            errors.append("Character name is required")
        
        if not self._class_rows:
            errors.append("At least one class is required")
        
        # Check for duplicate classes
        classes_seen = set()
        for row in self._class_rows:
            class_name = row.class_var.get()
            if class_name in classes_seen:
                errors.append(f"Duplicate class: {class_name}")
                break
            classes_seen.add(class_name)
        
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return False
        
        return True
    
    def _on_save(self):
        """Handle save button click."""
        if not self._validate():
            return
        
        # Get classes
        classes = [row.get_class_level() for row in self._class_rows]
        
        # Preserve known spells and custom settings if editing
        known_spells = []
        prepared_spells = []
        current_slots = {}
        warlock_slots_current = 0
        mystic_arcanum_used = []
        custom_max_slots = {}
        custom_max_cantrips = 0
        
        if self._original_character:
            known_spells = self._original_character.known_spells
            prepared_spells = self._original_character.prepared_spells
            current_slots = self._original_character.current_slots
            warlock_slots_current = self._original_character.warlock_slots_current
            mystic_arcanum_used = self._original_character.mystic_arcanum_used
            custom_max_slots = self._original_character.custom_max_slots
            custom_max_cantrips = self._original_character.custom_max_cantrips
        
        # Create character object
        self.result = CharacterSpellList(
            name=self.name_entry.get().strip(),
            classes=classes,
            known_spells=known_spells,
            prepared_spells=prepared_spells,
            current_slots=current_slots,
            warlock_slots_current=warlock_slots_current,
            mystic_arcanum_used=mystic_arcanum_used,
            custom_max_slots=custom_max_slots,
            custom_max_cantrips=custom_max_cantrips
        )
        
        self.destroy()
    
    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.destroy()

    def _on_theme_changed(self):
        """Reconfigure dialog widgets when theme changes."""
        try:
            theme = get_theme_manager()
            input_bg = theme.get_current_color('bg_input')
            input_text = theme.get_current_color('text_primary')
            border = theme.get_current_color('border')

            try:
                self.name_entry.configure(fg_color=input_bg, text_color=input_text, border_color=border)
            except Exception:
                pass

            try:
                self.add_class_btn.configure(fg_color=theme.get_current_color('button_success'), hover_color=theme.get_current_color('button_success_hover'))
            except Exception:
                pass

            try:
                self.classes_frame.configure(fg_color="transparent")
            except Exception:
                pass

            for row in self._class_rows:
                try:
                    row.apply_theme(theme)
                except Exception:
                    pass
        except Exception:
            pass

    def destroy(self):
        """Remove theme listener and destroy the dialog."""
        try:
            if hasattr(self, '_theme') and self._theme:
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()


class CustomSpellSlotsDialog(ctk.CTkToplevel):
    """Dialog for editing custom spell slot limits for Custom class characters."""
    
    def __init__(self, parent, character: CharacterSpellList):
        super().__init__(parent)
        
        self.result: Optional[CharacterSpellList] = None
        self._character = character
        
        # Window setup
        self.title(f"Custom Spell Slots - {character.name}")
        self.geometry("400x550")
        self.minsize(350, 500)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Create widgets
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        """Create all dialog widgets."""
        theme = get_theme_manager()
        
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Instructions
        ctk.CTkLabel(
            container,
            text="Set maximum spell slots for this Custom class character.\n"
                 "Leave at 0 to disable that spell level.",
            font=ctk.CTkFont(size=12),
            text_color=theme.get_text_secondary(),
            justify="left"
        ).pack(fill="x", pady=(0, 15))
        
        # Cantrips section
        cantrip_frame = ctk.CTkFrame(container, fg_color="transparent")
        cantrip_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            cantrip_frame, text="Max Cantrips:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")
        
        self.cantrip_var = ctk.StringVar(value=str(self._character.custom_max_cantrips))
        self.cantrip_entry = ctk.CTkEntry(
            cantrip_frame, textvariable=self.cantrip_var,
            width=60, justify="center"
        )
        self.cantrip_entry.pack(side="left", padx=(10, 0))
        
        ctk.CTkLabel(
            cantrip_frame, text="(0 = unlimited)",
            font=ctk.CTkFont(size=11),
            text_color=theme.get_text_secondary()
        ).pack(side="left", padx=(10, 0))
        
        # Spell slots section
        ctk.CTkLabel(
            container, text="Maximum Spell Slots by Level:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(fill="x", pady=(0, 10))
        
        # Slots frame
        slots_frame = ctk.CTkFrame(container, fg_color=theme.get_current_color('bg_secondary'))
        slots_frame.pack(fill="x", pady=(0, 15))
        
        self.slot_vars = {}
        self.slot_entries = {}
        
        for level in range(1, 10):
            row = ctk.CTkFrame(slots_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=5)
            
            ctk.CTkLabel(
                row, text=f"Level {level}:",
                font=ctk.CTkFont(size=12),
                width=70, anchor="w"
            ).pack(side="left")
            
            current_max = self._character.custom_max_slots.get(level, 0)
            var = ctk.StringVar(value=str(current_max))
            self.slot_vars[level] = var
            
            entry = ctk.CTkEntry(row, textvariable=var, width=60, justify="center")
            entry.pack(side="left", padx=(10, 0))
            self.slot_entries[level] = entry
        
        # Buttons
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(15, 0))
        
        btn_text = theme.get_current_color('text_primary')
        
        ctk.CTkButton(
            button_frame, text="Cancel", width=100,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=self._on_cancel
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            button_frame, text="Save", width=100,
            text_color=btn_text,
            command=self._on_save
        ).pack(side="right")
    
    def _on_save(self):
        """Save the custom spell slot configuration."""
        try:
            # Parse cantrips
            cantrips = int(self.cantrip_var.get() or 0)
            cantrips = max(0, cantrips)
            
            # Parse slots
            custom_slots = {}
            for level in range(1, 10):
                value = int(self.slot_vars[level].get() or 0)
                if value > 0:
                    custom_slots[level] = value
            
            # Update character
            self._character.custom_max_cantrips = cantrips
            self._character.custom_max_slots = custom_slots
            
            self.result = self._character
            self.destroy()
            
        except ValueError:
            messagebox.showerror("Invalid Input", 
                "Please enter valid numbers for all fields.", parent=self)
    
    def _on_cancel(self):
        """Cancel without saving."""
        self.result = None
        self.destroy()
