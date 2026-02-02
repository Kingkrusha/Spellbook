"""
Spell Editor Dialog for D&D Spellbook (CustomTkinter version).
Dialog for creating and editing spells.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, List
from spell import Spell, CharacterClass, PROTECTED_TAGS, is_protected_tag
from theme import get_theme_manager


class TagSelectionDialog(ctk.CTkToplevel):
    """Dialog for selecting tags from existing tags or adding new ones."""
    
    def __init__(self, parent, available_tags: List[str], selected_tags: List[str]):
        super().__init__(parent)
        
        self.result: Optional[str] = None  # Tag to add
        self._tag_vars = {}
        
        self.title("Select Tag")
        self.geometry("350x450")
        self.minsize(300, 350)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Create widgets
        self._create_widgets(available_tags, selected_tags)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self, available_tags: List[str], selected_tags: List[str]):
        """Create dialog widgets."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        
        # Add New Tag section
        ctk.CTkLabel(
            container,
            text="Add New Tag:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", pady=(0, 5))
        
        new_tag_frame = ctk.CTkFrame(container, fg_color="transparent")
        new_tag_frame.pack(fill="x", pady=(0, 15))
        
        self._new_tag_entry = ctk.CTkEntry(
            new_tag_frame, height=35,
            placeholder_text="Enter new tag name"
        )
        self._new_tag_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(
            new_tag_frame, text="Add", width=60,
            fg_color=theme.get_current_color('button_success'),
            hover_color=theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_add_new
        ).pack(side="right")
        
        # Divider
        ctk.CTkFrame(container, height=2, fg_color=theme.get_current_color('border')).pack(fill="x", pady=10)
        
        # Existing tags section
        ctk.CTkLabel(
            container,
            text="Or select existing tag:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            container,
            text="(Click a tag to add it)",
            font=ctk.CTkFont(size=11),
            text_color=text_secondary
        ).pack(fill="x", pady=(0, 10))
        
        # Filter out already selected and protected tags
        selected_lower = [t.lower() for t in selected_tags]
        available = [t for t in available_tags if t.lower() not in selected_lower and not is_protected_tag(t)]
        
        if not available:
            ctk.CTkLabel(
                container,
                text="No additional tags available.",
                font=ctk.CTkFont(size=13),
                text_color=text_secondary
            ).pack(pady=30)
        else:
            # Scrollable tag list
            scroll = ctk.CTkScrollableFrame(container)
            scroll.pack(fill="both", expand=True, pady=(0, 15))

            for tag in sorted(available):
                btn = ctk.CTkButton(
                    scroll, text=tag, anchor="w",
                    fg_color="transparent",
                    hover_color=theme.get_current_color('accent_primary'),
                    text_color=theme.get_current_color('text_primary'),
                    text_color_disabled="black",
                    font=ctk.CTkFont(size=13),
                    command=lambda t=tag: self._on_select_existing(t)
                )
                btn.pack(fill="x", pady=2)

        # Cancel button
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(btn_frame, text="Cancel", width=80,
                      fg_color=theme.get_current_color('button_normal'),
                      hover_color=theme.get_current_color('button_hover'),
                      text_color=btn_text,
                      command=self._on_cancel).pack(side="right")
    
    def _on_add_new(self):
        """Add a new tag from the entry field."""
        tag = self._new_tag_entry.get().strip()
        if not tag:
            messagebox.showwarning("Warning", "Please enter a tag name.", parent=self)
            return
        if is_protected_tag(tag):
            messagebox.showwarning("Warning", f"'{tag}' is a protected tag and cannot be added manually.", parent=self)
            return
        self.result = tag
        self.destroy()
    
    def _on_select_existing(self, tag: str):
        """Select an existing tag."""
        self.result = tag
        self.destroy()
    
    def _on_cancel(self):
        """Cancel and close."""
        self.destroy()


class SpellEditorDialog(ctk.CTkToplevel):
    """A dialog for creating or editing a spell."""
    
    def __init__(self, parent, title: str, spell: Optional[Spell] = None, spell_manager=None):
        super().__init__(parent)
        
        self.result: Optional[Spell] = None
        self._editing = spell is not None
        self._original_spell = spell
        self._spell_manager = spell_manager
        self._selected_tags: List[str] = []  # User-editable tags (non-protected)
        
        # Window setup
        self.title(title)
        self.geometry("600x800")
        self.minsize(550, 700)
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Create widgets
        self._create_widgets()
        
        # Populate if editing
        if spell:
            self._populate_from_spell(spell)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        # Focus on name entry
        self.name_entry.focus_set()
    
    def _create_widgets(self):
        """Create all dialog widgets."""
        # Main scrollable frame
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=(15, 0))
        
        container = self.scroll_frame
        
        # Name
        ctk.CTkLabel(container, text="Name *", 
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(container, height=35,
                                        placeholder_text="Enter spell name...")
        self.name_entry.pack(fill="x", pady=(0, 15))

        # Level row
        level_frame = ctk.CTkFrame(container, fg_color="transparent")
        level_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(level_frame, text="Level *",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.level_var = ctk.StringVar(value="0 (Cantrip)")
        self.level_combo = ctk.CTkComboBox(
            level_frame, variable=self.level_var,
            values=["0 (Cantrip)"] + [str(i) for i in range(1, 10)],
            width=130
        )
        self.level_combo.pack(side="left", padx=(15, 0))
        
        # Casting Time + Ritual row
        cast_frame = ctk.CTkFrame(container, fg_color="transparent")
        cast_frame.pack(fill="x", pady=(0, 15))
        
        cast_left = ctk.CTkFrame(cast_frame, fg_color="transparent")
        cast_left.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(cast_left, text="Casting Time *",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", pady=(0, 5))
        self.casting_time_entry = ctk.CTkEntry(cast_left, height=35,
                                                placeholder_text="e.g., 1 action")
        self.casting_time_entry.pack(fill="x")
        
        self.ritual_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(cast_frame, text="Ritual", variable=self.ritual_var,
                        font=ctk.CTkFont(size=13)).pack(side="right", padx=(20, 0))
        
        # Range row
        range_frame = ctk.CTkFrame(container, fg_color="transparent")
        range_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(range_frame, text="Range *",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        self.range_entry = ctk.CTkEntry(range_frame, width=100, height=35,
                                         placeholder_text="0")
        self.range_entry.pack(side="left", padx=(15, 10))
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        ctk.CTkLabel(range_frame, text="(0=Self, 1=Sight, 2=Special, 3=Touch, + ft, - miles)",
                     font=ctk.CTkFont(size=11),
                     text_color=text_secondary).pack(side="left")
        
        # Components section
        ctk.CTkLabel(container, text="Components",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", pady=(0, 8))
        
        comp_frame = ctk.CTkFrame(container, fg_color="transparent")
        comp_frame.pack(fill="x", pady=(0, 10))
        
        self.comp_v_var = ctk.BooleanVar(value=False)
        self.comp_s_var = ctk.BooleanVar(value=False)
        self.comp_m_var = ctk.BooleanVar(value=False)
        
        ctk.CTkCheckBox(comp_frame, text="V (Verbal)", variable=self.comp_v_var,
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(comp_frame, text="S (Somatic)", variable=self.comp_s_var,
                        font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(comp_frame, text="M (Material)", variable=self.comp_m_var,
                        font=ctk.CTkFont(size=12)).pack(side="left")
        
        # Material details
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        ctk.CTkLabel(container, text="Material Details (optional)",
                     font=ctk.CTkFont(size=11),
                     text_color=text_secondary).pack(fill="x", pady=(0, 5))
        self.material_entry = ctk.CTkEntry(container, height=35,
                                            placeholder_text="e.g., a tiny ball of bat guano")
        self.material_entry.pack(fill="x", pady=(0, 15))
        
        # Duration + Concentration row
        dur_frame = ctk.CTkFrame(container, fg_color="transparent")
        dur_frame.pack(fill="x", pady=(0, 15))
        
        dur_left = ctk.CTkFrame(dur_frame, fg_color="transparent")
        dur_left.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(dur_left, text="Duration *",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", pady=(0, 5))
        self.duration_entry = ctk.CTkEntry(dur_left, height=35,
                                            placeholder_text="e.g., Instantaneous")
        self.duration_entry.pack(fill="x")
        
        self.concentration_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(dur_frame, text="Concentration",
                        variable=self.concentration_var,
                        font=ctk.CTkFont(size=13)).pack(side="right", padx=(20, 0))
        
        # Classes section (only show spellcasting classes)
        ctk.CTkLabel(container, text="Classes *",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", pady=(0, 10))
        
        self.class_vars = {}
        classes_frame = ctk.CTkFrame(container, fg_color="transparent")
        classes_frame.pack(fill="x", pady=(0, 15))
        
        # Configure grid for 3 columns
        classes_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Only show spellcasting classes (excludes Barbarian, Fighter, Monk, Rogue)
        spellcasting_classes = CharacterClass.spellcasting_classes()
        for i, char_class in enumerate(spellcasting_classes):
            var = ctk.BooleanVar(value=False)
            self.class_vars[char_class] = var
            col = i % 3
            row = i // 3
            cb = ctk.CTkCheckBox(classes_frame, text=char_class.value, variable=var,
                                  font=ctk.CTkFont(size=12))
            cb.grid(row=row, column=col, sticky="w", pady=3)
        
        # Source
        ctk.CTkLabel(container, text="Source",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", pady=(0, 5))
        self.source_entry = ctk.CTkEntry(container, height=35,
                                          placeholder_text="e.g., Player's Handbook")
        self.source_entry.pack(fill="x", pady=(0, 10))
        
        # Legacy content checkbox
        self.legacy_var = ctk.BooleanVar(value=False)
        self.legacy_checkbox = ctk.CTkCheckBox(
            container, text="Legacy Content (2014 Rules)",
            variable=self.legacy_var,
            font=ctk.CTkFont(size=12)
        )
        self.legacy_checkbox.pack(anchor="w", pady=(0, 15))
        
        # Tags section with selection UI
        tags_header_frame = ctk.CTkFrame(container, fg_color="transparent")
        tags_header_frame.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(tags_header_frame, text="Tags",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        
        theme = get_theme_manager()
        btn_text = theme.get_current_color('text_primary')
        
        self._add_tag_btn = ctk.CTkButton(
            tags_header_frame, text="+ Add Tag", width=90,
            fg_color=theme.get_current_color('button_success'),
            hover_color=theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_add_tag
        )
        self._add_tag_btn.pack(side="right")
        
        # Tags display frame
        self._tags_display_frame = ctk.CTkFrame(container, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
        self._tags_display_frame.pack(fill="x", pady=(0, 15))
        
        self._tags_content_frame = ctk.CTkFrame(self._tags_display_frame, fg_color="transparent")
        self._tags_content_frame.pack(fill="x", padx=10, pady=10)
        
        self._no_tags_label = ctk.CTkLabel(
            self._tags_content_frame,
            text="No tags added. Click '+ Add Tag' to add tags.",
            font=ctk.CTkFont(size=12),
            text_color=theme.get_text_secondary()
        )
        self._no_tags_label.pack(anchor="w")
        
        # Description
        ctk.CTkLabel(container, text="Description *",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(
            fill="x", pady=(0, 5))
        text_secondary = theme.get_text_secondary()
        ctk.CTkLabel(container, text="Use \\ for paragraph breaks",
                     font=ctk.CTkFont(size=11),
                     text_color=text_secondary).pack(fill="x", pady=(0, 5))
        
        self.description_text = ctk.CTkTextbox(
            container, height=150, corner_radius=8,
            font=ctk.CTkFont(size=13)
        )
        self.description_text.pack(fill="both", expand=True, pady=(0, 10))
        
        # Button frame (outside scroll area)
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=15)
        theme = get_theme_manager()
        btn_text = theme.get_current_color('text_primary')
        self.cancel_btn = ctk.CTkButton(button_frame, text="Cancel", width=100,
                                         fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
                                         text_color=btn_text,
                                         command=self._on_cancel)
        self.cancel_btn.pack(side="right", padx=(10, 0))
        self.save_btn = ctk.CTkButton(button_frame, text="Save Spell", width=100,
                                      text_color=btn_text,
                                      command=self._on_save)
        self.save_btn.pack(side="right")

        # Register for theme changes so open dialog updates live
        try:
            self._theme = get_theme_manager()
            self._theme.add_listener(self._on_theme_changed)
        except Exception:
            self._theme = None

    def _on_theme_changed(self):
        """Reconfigure dialog widgets when theme changes."""
        try:
            theme = get_theme_manager()
            input_bg = theme.get_current_color('bg_input')
            input_text = theme.get_current_color('text_primary')
            border_col = theme.get_current_color('border')

            for name in ('name_entry', 'casting_time_entry', 'range_entry', 'material_entry', 'duration_entry', 'source_entry'):
                w = getattr(self, name, None)
                if w:
                    try:
                        w.configure(fg_color=input_bg, text_color=input_text, border_color=border_col)
                    except Exception:
                        pass

            # Combo box
            if hasattr(self, 'level_combo'):
                try:
                    self.level_combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg, border_color=border_col)
                except Exception:
                    pass

            # Textbox
            if hasattr(self, 'description_text'):
                try:
                    self.description_text.configure(fg_color=input_bg, text_color=input_text)
                except Exception:
                    pass

            # Scroll frame background
            if hasattr(self, 'scroll_frame'):
                try:
                    self.scroll_frame.configure(fg_color="transparent")
                except Exception:
                    pass
            # Buttons
            try:
                if hasattr(self, 'cancel_btn'):
                    self.cancel_btn.configure(fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'))
                if hasattr(self, 'save_btn'):
                    self.save_btn.configure(fg_color=theme.get_current_color('accent_primary'))
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
    
    def _on_add_tag(self):
        """Open the tag selection dialog."""
        # Get available tags from spell_manager
        available_tags = []
        if self._spell_manager:
            available_tags = self._spell_manager.get_all_tags()
        
        dialog = TagSelectionDialog(
            self,
            available_tags,
            self._selected_tags
        )
        self.wait_window(dialog)
        
        if dialog.result:
            if dialog.result not in self._selected_tags:
                self._selected_tags.append(dialog.result)
                self._refresh_tags_display()
    
    def _remove_tag(self, tag: str):
        """Remove a tag from the selected list."""
        if tag in self._selected_tags:
            self._selected_tags.remove(tag)
            self._refresh_tags_display()
    
    def _refresh_tags_display(self):
        """Refresh the tags display based on selected tags."""
        # Clear current content
        for widget in self._tags_content_frame.winfo_children():
            widget.destroy()
        
        if not self._selected_tags:
            # Show placeholder
            theme = get_theme_manager()
            self._no_tags_label = ctk.CTkLabel(
                self._tags_content_frame,
                text="No tags added. Click '+ Add Tag' to add tags.",
                font=ctk.CTkFont(size=12),
                text_color=theme.get_text_secondary()
            )
            self._no_tags_label.pack(anchor="w")
        else:
            # Show tags as removable chips with wrapping
            theme = get_theme_manager()
            
            # Use a flow layout with wrapping - create rows as needed
            current_row = ctk.CTkFrame(self._tags_content_frame, fg_color="transparent")
            current_row.pack(fill="x", anchor="w")
            
            for tag in sorted(self._selected_tags):
                tag_frame = ctk.CTkFrame(
                    current_row,
                    fg_color=theme.get_current_color('accent_primary'),
                    corner_radius=12
                )
                tag_frame.pack(side="left", padx=(0, 5), pady=2)
                
                ctk.CTkLabel(
                    tag_frame,
                    text=tag,
                    font=ctk.CTkFont(size=12),
                    text_color=theme.get_current_color('text_primary')
                ).pack(side="left", padx=(10, 5), pady=4)
                
                remove_btn = ctk.CTkButton(
                    tag_frame,
                    text="×",
                    width=20,
                    height=20,
                    fg_color="transparent",
                    hover_color=theme.get_current_color('button_danger'),
                    text_color=theme.get_current_color('text_primary'),
                    font=ctk.CTkFont(size=14, weight="bold"),
                    command=lambda t=tag: self._remove_tag(t)
                )
                remove_btn.pack(side="left", padx=(0, 5), pady=2)
                
                # Check if we need to wrap to a new row
                # Update the frame to get its width
                tag_frame.update_idletasks()
                current_row.update_idletasks()
                if current_row.winfo_reqwidth() > 450:  # Max width before wrapping
                    # Move this tag to a new row
                    tag_frame.pack_forget()
                    current_row = ctk.CTkFrame(self._tags_content_frame, fg_color="transparent")
                    current_row.pack(fill="x", anchor="w")
                    tag_frame = ctk.CTkFrame(
                        current_row,
                        fg_color=theme.get_current_color('accent_primary'),
                        corner_radius=12
                    )
                    tag_frame.pack(side="left", padx=(0, 5), pady=2)
                    ctk.CTkLabel(
                        tag_frame,
                        text=tag,
                        font=ctk.CTkFont(size=12),
                        text_color=theme.get_current_color('text_primary')
                    ).pack(side="left", padx=(10, 5), pady=4)
                    remove_btn = ctk.CTkButton(
                        tag_frame,
                        text="×",
                        width=20,
                        height=20,
                        fg_color="transparent",
                        hover_color=theme.get_current_color('button_danger'),
                        text_color=theme.get_current_color('text_primary'),
                        font=ctk.CTkFont(size=14, weight="bold"),
                        command=lambda t=tag: self._remove_tag(t)
                    )
                    remove_btn.pack(side="left", padx=(0, 5), pady=2)
    
    def _populate_from_spell(self, spell: Spell):
        """Populate form fields from an existing spell."""
        self.name_entry.insert(0, spell.name)
        
        if spell.level == 0:
            self.level_var.set("0 (Cantrip)")
        else:
            self.level_var.set(str(spell.level))
        
        self.casting_time_entry.insert(0, spell.casting_time)
        self.ritual_var.set(spell.ritual)
        
        self.range_entry.insert(0, str(spell.range_value))
        
        # Parse components
        components = spell.components.upper()
        self.comp_v_var.set("V" in components)
        self.comp_s_var.set("S" in components)
        self.comp_m_var.set("M" in components)
        
        # Extract material details if present
        if "(" in spell.components and ")" in spell.components:
            start = spell.components.index("(") + 1
            end = spell.components.index(")")
            self.material_entry.insert(0, spell.components[start:end])
        
        self.duration_entry.insert(0, spell.duration)
        self.concentration_var.set(spell.concentration)
        
        # Classes
        for char_class in spell.classes:
            if char_class in self.class_vars:
                self.class_vars[char_class].set(True)
        
        self.source_entry.insert(0, spell.source)
        # Legacy content checkbox
        self.legacy_var.set(spell.is_legacy)
        # Filter out protected tags (Official/Unofficial) and populate tag list
        self._selected_tags = [t for t in spell.tags if not is_protected_tag(t)]
        self._refresh_tags_display()
        self.description_text.insert("1.0", spell.description)
    
    def _build_components_string(self) -> str:
        """Build the components string from checkboxes."""
        parts = []
        if self.comp_v_var.get():
            parts.append("V")
        if self.comp_s_var.get():
            parts.append("S")
        if self.comp_m_var.get():
            material = self.material_entry.get().strip()
            if material:
                parts.append(f"M ({material})")
            else:
                parts.append("M")
        
        return ", ".join(parts)
    
    def _validate(self) -> bool:
        """Validate form inputs. Returns True if valid."""
        errors = []
        
        if not self.name_entry.get().strip():
            errors.append("Name is required")
        
        if not self.casting_time_entry.get().strip():
            errors.append("Casting time is required")
        
        range_str = self.range_entry.get().strip()
        if not range_str:
            errors.append("Range is required")
        else:
            try:
                range_val = int(range_str)
                # Special values: 0=Self, 1=Sight, 2=Special, 3=Touch
                # Negative values = miles
                # Positive values > 3 should be multiples of 5 (feet)
                if range_val > 3 and range_val % 5 != 0:
                    errors.append("Range must be 0 (Self), 1 (Sight), 2 (Special), 3 (Touch), negative (miles), or a multiple of 5 (feet)")
            except ValueError:
                errors.append("Range must be a number")
        
        if not self.duration_entry.get().strip():
            errors.append("Duration is required")
        
        # Check at least one class selected
        if not any(var.get() for var in self.class_vars.values()):
            errors.append("At least one class must be selected")
        
        if not self.description_text.get("1.0", "end").strip():
            errors.append("Description is required")
        
        if errors:
            messagebox.showerror("Validation Error", "\n".join(errors))
            return False
        
        return True
    
    def _on_save(self):
        """Handle save button click."""
        if not self._validate():
            return
        
        # Parse level
        level_str = self.level_var.get()
        if level_str.startswith("0"):
            level = 0
        else:
            level = int(level_str)
        
        # Get selected classes
        classes = [
            char_class for char_class, var in self.class_vars.items()
            if var.get()
        ]
        
        # Use selected tags from the new tag UI (already filtered for protected tags)
        user_tags = self._selected_tags.copy()
        
        # Preserve protected tags from the original spell (case-insensitive check)
        if self._original_spell:
            protected = [t for t in self._original_spell.tags if is_protected_tag(t)]
            tags = protected + user_tags
            # Preserve is_modified flag from original
            is_modified = self._original_spell.is_modified
        else:
            tags = user_tags
            is_modified = False
        
        # Create spell object
        self.result = Spell(
            name=self.name_entry.get().strip(),
            level=level,
            casting_time=self.casting_time_entry.get().strip(),
            ritual=self.ritual_var.get(),
            range_value=int(self.range_entry.get().strip()),
            components=self._build_components_string(),
            duration=self.duration_entry.get().strip(),
            concentration=self.concentration_var.get(),
            classes=classes,
            description=self.description_text.get("1.0", "end").strip(),
            source=self.source_entry.get().strip(),
            tags=tags,
            is_modified=is_modified,
            is_legacy=self.legacy_var.get()
        )
        
        self.destroy()
    
    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.destroy()
