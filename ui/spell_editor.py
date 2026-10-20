"""
Spell Editor Dialog for D&D Spellbook (CustomTkinter version).
Dialog for creating and editing spells.
"""

from ui.window_utils import center_on_parent
from ui.theme_listener import ThemeListenerMixin
import customtkinter as ctk
from typography import ui_font
from tkinter import messagebox
from typing import Optional, List
from spell import Spell, CharacterClass, PROTECTED_TAGS, is_protected_tag
from theme import get_theme_manager
from ui.editor_host import DialogWindow, EditorBody, EmbeddedWindow
from ui.review_banner import add_review_banner, outline_fields
from ui.tag_editor import TagEditor


class SpellEditorBody(EditorBody, ThemeListenerMixin):
    """A dialog for creating or editing a spell. (the form; see ui/editor_host.py)"""

    ERROR_TITLE = "Validation Error"
    
    def __init__(self, parent, title: str, spell: Optional[Spell] = None, spell_manager=None,
                 prefill_spell: Optional[Spell] = None, review_fields: Optional[List[str]] = None,
                 batch_progress: str = ""):
        super().__init__(parent)

        self.result: Optional[Spell] = None
        self._editing = spell is not None
        self._original_spell = spell
        self._spell_manager = spell_manager
        # Auto-detect pre-fill: populate the form from parsed text but keep this
        # a brand-new spell (no _original_spell), and mark fields to double-check.
        self._prefill_spell = prefill_spell
        self._review_fields = set(review_fields or [])
        self._batch_progress = batch_progress

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
        elif prefill_spell:
            self._populate_from_spell(prefill_spell)
            self._apply_review_highlights()

        # Center on parent
        center_on_parent(self, parent, root_coords=False)
        
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
                     font=ui_font("subheading", 13, bold=True)).pack(
            fill="x", pady=(0, 5))
        self.name_entry = ctk.CTkEntry(container, height=35,
                                        placeholder_text="Enter spell name...")
        self.name_entry.pack(fill="x", pady=(0, 15))

        # Level row
        level_frame = ctk.CTkFrame(container, fg_color="transparent")
        level_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(level_frame, text="Level *",
                     font=ui_font("subheading", 13, bold=True)).pack(side="left")
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
                     font=ui_font("subheading", 13, bold=True)).pack(
            fill="x", pady=(0, 5))
        self.casting_time_entry = ctk.CTkEntry(cast_left, height=35,
                                                placeholder_text="e.g., 1 action")
        self.casting_time_entry.pack(fill="x")
        
        self.ritual_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(cast_frame, text="Ritual", variable=self.ritual_var,
                        font=ui_font("body", 13)).pack(side="right", padx=(20, 0))
        
        # Range row
        range_frame = ctk.CTkFrame(container, fg_color="transparent")
        range_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(range_frame, text="Range *",
                     font=ui_font("subheading", 13, bold=True)).pack(side="left")
        self.range_entry = ctk.CTkEntry(range_frame, width=100, height=35,
                                         placeholder_text="0")
        self.range_entry.pack(side="left", padx=(15, 10))
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        ctk.CTkLabel(range_frame, text="(0=Self, 1=Sight, 2=Special, 3=Touch, + ft, - miles)",
                     font=ui_font("small"),
                     text_color=text_secondary).pack(side="left")
        
        # Components section
        ctk.CTkLabel(container, text="Components",
                     font=ui_font("subheading", 13, bold=True)).pack(
            fill="x", pady=(0, 8))
        
        comp_frame = ctk.CTkFrame(container, fg_color="transparent")
        comp_frame.pack(fill="x", pady=(0, 10))
        
        self.comp_v_var = ctk.BooleanVar(value=False)
        self.comp_s_var = ctk.BooleanVar(value=False)
        self.comp_m_var = ctk.BooleanVar(value=False)
        
        ctk.CTkCheckBox(comp_frame, text="V (Verbal)", variable=self.comp_v_var,
                        font=ui_font("body")).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(comp_frame, text="S (Somatic)", variable=self.comp_s_var,
                        font=ui_font("body")).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(comp_frame, text="M (Material)", variable=self.comp_m_var,
                        font=ui_font("body")).pack(side="left")
        
        # Material details
        theme = get_theme_manager()
        text_secondary = theme.get_text_secondary()
        ctk.CTkLabel(container, text="Material Details (optional)",
                     font=ui_font("small"),
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
                     font=ui_font("subheading", 13, bold=True)).pack(
            fill="x", pady=(0, 5))
        self.duration_entry = ctk.CTkEntry(dur_left, height=35,
                                            placeholder_text="e.g., Instantaneous")
        self.duration_entry.pack(fill="x")
        
        self.concentration_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(dur_frame, text="Concentration",
                        variable=self.concentration_var,
                        font=ui_font("body", 13)).pack(side="right", padx=(20, 0))
        
        # Classes section (only show spellcasting classes)
        ctk.CTkLabel(container, text="Classes *",
                     font=ui_font("subheading", 13, bold=True)).pack(
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
                                  font=ui_font("body"))
            cb.grid(row=row, column=col, sticky="w", pady=3)
        
        # Source
        ctk.CTkLabel(container, text="Source",
                     font=ui_font("subheading", 13, bold=True)).pack(
            fill="x", pady=(0, 5))
        self.source_entry = ctk.CTkEntry(container, height=35,
                                          placeholder_text="e.g., Player's Handbook")
        self.source_entry.pack(fill="x", pady=(0, 10))
        
        # Legacy content checkbox
        self.legacy_var = ctk.BooleanVar(value=False)
        self.legacy_checkbox = ctk.CTkCheckBox(
            container, text="Legacy Content (2014 Rules)",
            variable=self.legacy_var,
            font=ui_font("body")
        )
        self.legacy_checkbox.pack(anchor="w", pady=(0, 15))
        
        # Tags: the ones the user can edit (the protected Official/Unofficial tag is kept apart)
        self.tag_editor = TagEditor(
            container, get_available_tags=self._available_tags, is_protected=is_protected_tag)
        self.tag_editor.pack(fill="x", pady=(0, 15))
        
        # Description
        ctk.CTkLabel(container, text="Description *",
                     font=ui_font("subheading", 13, bold=True)).pack(
            fill="x", pady=(0, 5))
        text_secondary = theme.get_text_secondary()
        ctk.CTkLabel(container, text="Use \\ for paragraph breaks. Use [[SpellName]] for spell links.",
                     font=ui_font("small"),
                     text_color=text_secondary).pack(fill="x", pady=(0, 5))
        
        self.description_text = ctk.CTkTextbox(
            container, height=150, corner_radius=8,
            font=ui_font("body", 13)
        )
        
        # Add rich text toolbar for tables, spell links, and bold
        from ui.rich_text_utils import RichTextEditor
        self._rich_editor = RichTextEditor(self, self.description_text, theme)
        toolbar = self._rich_editor.create_toolbar(container)
        toolbar.pack(fill="x", pady=(0, 5))
        
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
                                      command=self._save)
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

    def _available_tags(self) -> List[str]:
        """Every tag in use, for the tag picker."""
        return self._spell_manager.get_all_tags() if self._spell_manager else []

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
        self.tag_editor.set_tags([t for t in spell.tags if not is_protected_tag(t)])
        self.description_text.insert("1.0", spell.description)

    # Human-readable labels for the review banner / field map for highlighting.
    _REVIEW_FIELD_LABELS = {
        "name": "Name", "level": "Level", "casting_time": "Casting Time",
        "ritual": "Ritual", "range": "Range", "components": "Components",
        "duration": "Duration", "concentration": "Concentration",
        "classes": "Classes", "source": "Source", "tags": "Tags",
        "description": "Description",
    }

    def _apply_review_highlights(self):
        """Add the auto-detect disclaimer banner and outline uncertain fields."""
        banner, warn = add_review_banner(
            self, self.scroll_frame, self._review_fields, self._REVIEW_FIELD_LABELS, self._batch_progress,
            ("Auto-detection is rule-based, not perfect - accuracy drops for "
             "irregularly formatted text. Nothing is saved until you click Save Spell."),
            theme=get_theme_manager(), padx=15)
        self._review_banner = banner

        widgets = {
            "name": self.name_entry,
            "level": self.level_combo,
            "casting_time": self.casting_time_entry,
            "range": self.range_entry,
            "components": self.material_entry,
            "duration": self.duration_entry,
            "source": self.source_entry,
        }
        outline_fields(widgets, self._review_fields, warn)

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
    
    def _problems(self) -> List[str]:
        """What is wrong with the form (empty if it can be saved)."""
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
        
        return errors
    
    def build_result(self, strict: bool = True) -> Spell:
        """The spell the form describes (strict: ValueError listing what is missing; otherwise gaps are filled in)."""
        if strict:
            errors = self._problems()
            if errors:
                raise ValueError("\n".join(errors))

        # Parse level
        level_str = self.level_var.get()
        try:
            level = 0 if level_str.startswith("0") else int(level_str)
        except ValueError:
            level = 0
        try:
            range_value = int(self.range_entry.get().strip())
        except ValueError:
            range_value = 0
        
        # Get selected classes
        classes = [
            char_class for char_class, var in self.class_vars.items()
            if var.get()
        ]
        
        # Use selected tags from the new tag UI (already filtered for protected tags)
        user_tags = self.tag_editor.get_tags()
        
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
        return Spell(
            name=self.name_entry.get().strip(),
            level=level,
            casting_time=self.casting_time_entry.get().strip(),
            ritual=self.ritual_var.get(),
            range_value=range_value,
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

    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = None
        self._finish()


class SpellEditorDialog(SpellEditorBody, DialogWindow):
    """A dialog for creating or editing a spell."""


class SpellEditorPanel(SpellEditorBody, EmbeddedWindow):
    """The SpellEditorDialog form inside the Homebrew Studio."""
