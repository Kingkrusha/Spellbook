"""
Character Sheet View for D&D 5e Spellbook Application.
Provides a full character sheet interface with D&D 5e standard layout.
"""
# pyright: reportOptionalMemberAccess=false

import customtkinter as ctk
import re
from tkinter import messagebox
from typing import Optional, Callable, List, Dict
from character import CharacterSpellList
from character_manager import CharacterManager
from character_sheet import (
    CharacterSheet, AbilityScore, Skill, HitPoints, DeathSaves,
    CLASS_HIT_DICE, get_hit_dice_for_classes, calculate_hp_maximum, get_default_proficiencies,
    calculate_proficiency_bonus, ArmorType, COMMON_ARMOR_OPTIONS, SHIELD_OPTIONS, calculate_ac
)
from spell import CharacterClass
from settings import get_settings_manager
from theme import get_theme_manager
from character_class import get_class_manager, ClassAbility
from feat import get_feat_manager
import json
import os


class CharacterSheetManager:
    """Manages character sheet persistence."""
    
    DEFAULT_FILE = "character_sheets.json"
    
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or self.DEFAULT_FILE
        self._sheets: Dict[str, CharacterSheet] = {}  # character_name -> CharacterSheet
    
    def load(self) -> bool:
        """Load character sheets from file."""
        if not os.path.exists(self.file_path):
            self._sheets = {}
            return True
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._sheets = {
                    name: CharacterSheet.from_dict(sheet_data)
                    for name, sheet_data in data.get("sheets", {}).items()
                }
            return True
        except Exception as e:
            print(f"Error loading character sheets: {e}")
            self._sheets = {}
            return False
    
    def save(self) -> bool:
        """Save character sheets to file."""
        try:
            data = {
                "sheets": {
                    name: sheet.to_dict() for name, sheet in self._sheets.items()
                }
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving character sheets: {e}")
            return False
    
    def get_sheet(self, character_name: str) -> Optional[CharacterSheet]:
        """Get character sheet by name."""
        return self._sheets.get(character_name)
    
    def get_or_create_sheet(self, character_name: str, character: Optional['CharacterSpellList'] = None) -> CharacterSheet:
        """Get existing sheet or create new one for character."""
        if character_name not in self._sheets:
            sheet = CharacterSheet(character_name=character_name)
            
            # Auto-apply saving throw proficiencies from starting class
            if character and character.classes:
                from settings import get_settings_manager
                if get_settings_manager().settings.auto_apply_saving_throws:
                    from character_class import get_class_manager
                    from character_sheet import AbilityScore
                    
                    class_manager = get_class_manager()
                    # Use first class (starting class) for saving throws
                    first_class = character.classes[0].character_class.value
                    class_def = class_manager.get_class(first_class)
                    
                    if class_def:
                        for save in class_def.saving_throw_proficiencies:
                            ability = None
                            if save == "STR":
                                ability = AbilityScore.STRENGTH
                            elif save == "DEX":
                                ability = AbilityScore.DEXTERITY
                            elif save == "CON":
                                ability = AbilityScore.CONSTITUTION
                            elif save == "INT":
                                ability = AbilityScore.INTELLIGENCE
                            elif save == "WIS":
                                ability = AbilityScore.WISDOM
                            elif save == "CHA":
                                ability = AbilityScore.CHARISMA
                            
                            if ability:
                                sheet.saving_throws.set_proficiency(ability, True)
                        
                        # Also apply unarmored defense if class has it
                        if class_def.unarmored_defense:
                            sheet.unarmored_defense = class_def.unarmored_defense
            
            self._sheets[character_name] = sheet
            self.save()
        return self._sheets[character_name]
    
    def update_sheet(self, character_name: str, sheet: CharacterSheet):
        """Update or create a character sheet."""
        self._sheets[character_name] = sheet
        self.save()
    
    def delete_sheet(self, character_name: str):
        """Delete a character sheet."""
        if character_name in self._sheets:
            del self._sheets[character_name]
            self.save()
    
    def rename_sheet(self, old_name: str, new_name: str):
        """Rename a character sheet."""
        if old_name in self._sheets:
            sheet = self._sheets.pop(old_name)
            sheet.character_name = new_name
            self._sheets[new_name] = sheet
            self.save()


# Global sheet manager instance
_sheet_manager: Optional[CharacterSheetManager] = None

def get_sheet_manager() -> CharacterSheetManager:
    """Get or create the global sheet manager."""
    global _sheet_manager
    if _sheet_manager is None:
        _sheet_manager = CharacterSheetManager()
        _sheet_manager.load()
    return _sheet_manager


class AbilityScoreWidget(ctk.CTkFrame):
    """Widget displaying a single ability score with modifier."""
    
    def __init__(self, parent, ability: AbilityScore, score: int = 10,
                 on_change: Optional[Callable[[AbilityScore, int], None]] = None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_secondary'),
                         corner_radius=8, width=80, height=100)
        self.pack_propagate(False)
        
        self.ability = ability
        self.on_change = on_change
        
        # Ability name
        ctk.CTkLabel(
            self, text=AbilityScore.short_name(ability),
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=(8, 2))
        
        # Score entry
        self.score_var = ctk.StringVar(value=str(score))
        self.score_entry = ctk.CTkEntry(
            self, width=50, height=28,
            textvariable=self.score_var,
            justify="center",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.score_entry.pack(pady=2)
        self.score_entry.bind("<FocusOut>", self._on_score_change)
        self.score_entry.bind("<Return>", self._on_score_change)
        
        # Modifier display
        modifier = (score - 10) // 2
        mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
        self.modifier_label = ctk.CTkLabel(
            self, text=mod_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        )
        self.modifier_label.pack(pady=(2, 8))
    
    def _on_score_change(self, event=None):
        """Handle score change."""
        try:
            score = int(self.score_var.get())
            score = max(1, min(30, score))
            self.score_var.set(str(score))
            
            # Update modifier display
            modifier = (score - 10) // 2
            mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
            self.modifier_label.configure(text=mod_text)
            
            if self.on_change:
                self.on_change(self.ability, score)
        except ValueError:
            pass
    
    def set_score(self, score: int):
        """Set the ability score."""
        self.score_var.set(str(score))
        modifier = (score - 10) // 2
        mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
        self.modifier_label.configure(text=mod_text)


class SavingThrowWidget(ctk.CTkFrame):
    """Widget for a saving throw with proficiency checkbox."""
    
    def __init__(self, parent, ability: AbilityScore, modifier: int,
                 proficient: bool = False, on_change: Optional[Callable[[AbilityScore, bool], None]] = None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        
        self.ability = ability
        self.on_change = on_change
        
        # Proficiency checkbox
        self.prof_var = ctk.BooleanVar(value=proficient)
        self.checkbox = ctk.CTkCheckBox(
            self, text="", width=20, height=20,
            variable=self.prof_var,
            command=self._on_change
        )
        self.checkbox.pack(side="left", padx=(0, 5))
        
        # Modifier display
        mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
        self.mod_label = ctk.CTkLabel(
            self, text=mod_text, width=35,
            font=ctk.CTkFont(size=12)
        )
        self.mod_label.pack(side="left", padx=(0, 5))
        
        # Ability name
        ctk.CTkLabel(
            self, text=ability.value,
            font=ctk.CTkFont(size=12)
        ).pack(side="left")
    
    def _on_change(self):
        if self.on_change:
            self.on_change(self.ability, self.prof_var.get())
    
    def update_modifier(self, modifier: int):
        """Update the displayed modifier."""
        mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
        self.mod_label.configure(text=mod_text)
    
    def set_proficient(self, proficient: bool):
        self.prof_var.set(proficient)


class SkillWidget(ctk.CTkFrame):
    """Widget for a skill with proficiency/expertise toggle."""
    
    def __init__(self, parent, skill: Skill, modifier: int,
                 prof_level: int = 0, on_change: Optional[Callable[[Skill, int], None]] = None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        
        self.skill = skill
        self.on_change = on_change
        self.prof_level = prof_level
        
        # Proficiency button (cycles: none -> proficient -> expertise)
        self.prof_btn = ctk.CTkButton(
            self, text=self._get_prof_symbol(),
            width=24, height=24,
            font=ctk.CTkFont(size=10),
            fg_color=self._get_prof_color(),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._cycle_proficiency
        )
        self.prof_btn.pack(side="left", padx=(0, 5))
        
        # Modifier display
        mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
        self.mod_label = ctk.CTkLabel(
            self, text=mod_text, width=35,
            font=ctk.CTkFont(size=11)
        )
        self.mod_label.pack(side="left", padx=(0, 5))
        
        # Skill name with ability abbreviation
        ability_short = AbilityScore.short_name(skill.ability)
        ctk.CTkLabel(
            self, text=f"{skill.display_name} ({ability_short})",
            font=ctk.CTkFont(size=11)
        ).pack(side="left")
    
    def _get_prof_symbol(self) -> str:
        if self.prof_level == 0:
            return "○"
        elif self.prof_level == 1:
            return "●"
        else:
            return "◉"
    
    def _get_prof_color(self) -> str:
        if self.prof_level == 0:
            return self.theme.get_current_color('bg_tertiary')
        elif self.prof_level == 1:
            return self.theme.get_current_color('accent_primary')
        else:
            return self.theme.get_current_color('accent_secondary')
    
    def _cycle_proficiency(self):
        self.prof_level = (self.prof_level + 1) % 3
        self.prof_btn.configure(text=self._get_prof_symbol(), fg_color=self._get_prof_color())
        if self.on_change:
            self.on_change(self.skill, self.prof_level)
    
    def update_modifier(self, modifier: int):
        mod_text = f"+{modifier}" if modifier >= 0 else str(modifier)
        self.mod_label.configure(text=mod_text)
    
    def set_prof_level(self, level: int):
        self.prof_level = level
        self.prof_btn.configure(text=self._get_prof_symbol(), fg_color=self._get_prof_color())


class HitPointsWidget(ctk.CTkFrame):
    """Widget for hit point tracking."""
    
    def __init__(self, parent, hp: HitPoints, on_change: Optional[Callable[[HitPoints], None]] = None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_secondary'),
                         corner_radius=8)
        
        self.hp = hp
        self.on_change = on_change
        
        self._create_widgets()
    
    def _create_widgets(self):
        # Title
        ctk.CTkLabel(
            self, text="HIT POINTS",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=(10, 5))
        
        # Main HP row
        hp_row = ctk.CTkFrame(self, fg_color="transparent")
        hp_row.pack(fill="x", padx=15, pady=5)
        
        # Current HP
        ctk.CTkLabel(hp_row, text="Current:", font=ctk.CTkFont(size=11)).pack(side="left")
        self.current_var = ctk.StringVar(value=str(self.hp.current))
        current_entry = ctk.CTkEntry(
            hp_row, width=50, height=28,
            textvariable=self.current_var,
            justify="center"
        )
        current_entry.pack(side="left", padx=5)
        current_entry.bind("<FocusOut>", self._on_change)
        current_entry.bind("<Return>", self._on_change)
        
        ctk.CTkLabel(hp_row, text="/", font=ctk.CTkFont(size=14)).pack(side="left")
        
        # Max HP
        self.max_var = ctk.StringVar(value=str(self.hp.maximum))
        max_entry = ctk.CTkEntry(
            hp_row, width=50, height=28,
            textvariable=self.max_var,
            justify="center"
        )
        max_entry.pack(side="left", padx=5)
        max_entry.bind("<FocusOut>", self._on_change)
        max_entry.bind("<Return>", self._on_change)
        
        # Temp HP row
        temp_row = ctk.CTkFrame(self, fg_color="transparent")
        temp_row.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(temp_row, text="Temp HP:", font=ctk.CTkFont(size=11)).pack(side="left")
        self.temp_var = ctk.StringVar(value=str(self.hp.temporary))
        temp_entry = ctk.CTkEntry(
            temp_row, width=50, height=28,
            textvariable=self.temp_var,
            justify="center"
        )
        temp_entry.pack(side="left", padx=5)
        temp_entry.bind("<FocusOut>", self._on_change)
        temp_entry.bind("<Return>", self._on_change)
        
        # Hit Dice row
        dice_row = ctk.CTkFrame(self, fg_color="transparent")
        dice_row.pack(fill="x", padx=15, pady=(5, 10))
        
        ctk.CTkLabel(dice_row, text="Hit Dice:", font=ctk.CTkFont(size=11)).pack(side="left")
        self.dice_remaining_var = ctk.StringVar(value=str(self.hp.hit_dice_remaining))
        dice_remaining_entry = ctk.CTkEntry(
            dice_row, width=40, height=28,
            textvariable=self.dice_remaining_var,
            justify="center"
        )
        dice_remaining_entry.pack(side="left", padx=5)
        dice_remaining_entry.bind("<FocusOut>", self._on_change)
        dice_remaining_entry.bind("<Return>", self._on_change)
        
        ctk.CTkLabel(dice_row, text="/", font=ctk.CTkFont(size=12)).pack(side="left")
        
        self.dice_total_var = ctk.StringVar(value=str(self.hp.hit_dice_total))
        dice_total_entry = ctk.CTkEntry(
            dice_row, width=40, height=28,
            textvariable=self.dice_total_var,
            justify="center"
        )
        dice_total_entry.pack(side="left", padx=5)
        dice_total_entry.bind("<FocusOut>", self._on_change)
        dice_total_entry.bind("<Return>", self._on_change)
        
        self.dice_type_var = ctk.StringVar(value=self.hp.hit_die_type)
        dice_type_combo = ctk.CTkComboBox(
            dice_row, width=60, height=28,
            values=["d6", "d8", "d10", "d12"],
            variable=self.dice_type_var,
            command=lambda _: self._on_change()
        )
        dice_type_combo.pack(side="left", padx=5)
    
    def _on_change(self, event=None):
        try:
            self.hp.current = max(0, int(self.current_var.get() or "0"))
            self.hp.maximum = max(1, int(self.max_var.get() or "1"))
            self.hp.temporary = max(0, int(self.temp_var.get() or "0"))
            self.hp.hit_dice_remaining = max(0, int(self.dice_remaining_var.get() or "0"))
            self.hp.hit_dice_total = max(1, int(self.dice_total_var.get() or "1"))
            self.hp.hit_die_type = self.dice_type_var.get()
            
            if self.on_change:
                self.on_change(self.hp)
        except ValueError:
            pass
    
    def set_hp(self, hp: HitPoints):
        self.hp = hp
        self.current_var.set(str(hp.current))
        self.max_var.set(str(hp.maximum))
        self.temp_var.set(str(hp.temporary))
        self.dice_remaining_var.set(str(hp.hit_dice_remaining))
        self.dice_total_var.set(str(hp.hit_dice_total))
        self.dice_type_var.set(hp.hit_die_type)


class DeathSavesWidget(ctk.CTkFrame):
    """Widget for death saving throws and inspiration."""
    
    def __init__(self, parent, death_saves: DeathSaves, inspiration: bool = False,
                 on_change: Optional[Callable[[DeathSaves], None]] = None,
                 on_inspiration_change: Optional[Callable[[bool], None]] = None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_secondary'),
                         corner_radius=8)
        
        self.death_saves = death_saves
        self.on_change = on_change
        self.on_inspiration_change = on_inspiration_change
        self.inspiration = inspiration
        
        self._create_widgets()
    
    def _create_widgets(self):
        # Main container with two columns
        main_row = ctk.CTkFrame(self, fg_color="transparent")
        main_row.pack(fill="x", padx=10, pady=8)
        
        # Left column: Death Saves
        death_col = ctk.CTkFrame(main_row, fg_color="transparent")
        death_col.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(
            death_col, text="DEATH SAVES",
            font=ctk.CTkFont(size=10, weight="bold")
        ).pack(anchor="w")
        
        # Successes row - aligned checkboxes
        success_row = ctk.CTkFrame(death_col, fg_color="transparent")
        success_row.pack(fill="x", pady=2)
        ctk.CTkLabel(success_row, text="Successes", font=ctk.CTkFont(size=9), width=60).pack(side="left")
        
        self.success_vars = []
        for i in range(3):
            var = ctk.BooleanVar(value=i < self.death_saves.successes)
            self.success_vars.append(var)
            ctk.CTkCheckBox(
                success_row, text="", width=20, height=20,
                variable=var, command=self._on_success_change
            ).pack(side="left", padx=2)
        
        # Failures row - aligned checkboxes
        fail_row = ctk.CTkFrame(death_col, fg_color="transparent")
        fail_row.pack(fill="x", pady=2)
        ctk.CTkLabel(fail_row, text="Failures", font=ctk.CTkFont(size=9), width=60).pack(side="left")
        
        self.fail_vars = []
        for i in range(3):
            var = ctk.BooleanVar(value=i < self.death_saves.failures)
            self.fail_vars.append(var)
            ctk.CTkCheckBox(
                fail_row, text="", width=20, height=20,
                variable=var, command=self._on_fail_change
            ).pack(side="left", padx=2)
        
        # Right column: Inspiration
        insp_col = ctk.CTkFrame(main_row, fg_color="transparent")
        insp_col.pack(side="right", padx=(10, 0))
        
        ctk.CTkLabel(
            insp_col, text="INSPIRATION",
            font=ctk.CTkFont(size=10, weight="bold")
        ).pack(anchor="center")
        
        self.inspiration_var = ctk.BooleanVar(value=self.inspiration)
        insp_check = ctk.CTkCheckBox(
            insp_col, text="", width=30, height=30,
            variable=self.inspiration_var,
            command=self._on_inspiration_change,
            checkbox_width=24, checkbox_height=24
        )
        insp_check.pack(pady=5)
    
    def _on_success_change(self):
        self.death_saves.successes = sum(1 for v in self.success_vars if v.get())
        if self.on_change:
            self.on_change(self.death_saves)
    
    def _on_fail_change(self):
        self.death_saves.failures = sum(1 for v in self.fail_vars if v.get())
        if self.on_change:
            self.on_change(self.death_saves)
    
    def _on_inspiration_change(self):
        if self.on_inspiration_change:
            self.on_inspiration_change(self.inspiration_var.get())
    
    def set_values(self, death_saves: DeathSaves, inspiration: bool):
        """Update the widget values (used during long rest)."""
        self.death_saves = death_saves
        self.inspiration = inspiration
        
        # Update success checkboxes
        for i, var in enumerate(self.success_vars):
            var.set(i < death_saves.successes)
        
        # Update failure checkboxes
        for i, var in enumerate(self.fail_vars):
            var.set(i < death_saves.failures)
        
        # Update inspiration checkbox
        self.inspiration_var.set(inspiration)


class CharacterSheetView(ctk.CTkFrame):
    """Main character sheet view with D&D 5e standard layout."""
    
    # Race options for dropdown
    RACE_OPTIONS = [
        "", "Dragonborn", "Dwarf", "Elf", "Gnome", "Half-Elf", 
        "Half-Orc", "Halfling", "Human", "Tiefling", "Aarakocra",
        "Aasimar", "Firbolg", "Genasi", "Goliath", "Kenku", 
        "Lizardfolk", "Tabaxi", "Triton", "Custom"
    ]
    
    # Background options for dropdown
    BACKGROUND_OPTIONS = [
        "", "Acolyte", "Charlatan", "Criminal", "Entertainer", 
        "Folk Hero", "Guild Artisan", "Hermit", "Noble", "Outlander",
        "Sage", "Sailor", "Soldier", "Urchin", "Custom"
    ]
    
    def __init__(self, parent, character_manager: CharacterManager,
                 spell_manager=None, on_navigate_to_spell=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        
        self.character_manager = character_manager
        self.spell_manager = spell_manager
        self.on_navigate_to_spell = on_navigate_to_spell
        self.sheet_manager = get_sheet_manager()
        self.current_character: Optional[CharacterSpellList] = None
        self.current_sheet: Optional[CharacterSheet] = None
        self._current_tab = "front"  # front, inventory, spells
        self._rebuilding_ui = False  # Flag to prevent saves during UI rebuild
        
        self._create_widgets()
    
    def _get_jack_of_all_trades_bonus(self) -> int:
        """Get Jack of All Trades bonus (half proficiency, rounded down) if character has the feature.
        
        Returns half proficiency bonus if character is a Bard level 2+, otherwise 0.
        """
        if not self.current_character or not self.current_sheet:
            return 0
        
        for cl in self.current_character.classes:
            if cl.character_class.value == "Bard" and cl.level >= 2:
                return self.current_sheet.proficiency_bonus // 2
        return 0
    
    def _require_character(self) -> CharacterSpellList:
        """Get current character, raising if not available."""
        if self.current_character is None:
            raise RuntimeError("No character selected")
        return self.current_character
    
    def _require_sheet(self) -> CharacterSheet:
        """Get current sheet, raising if not available."""
        if self.current_sheet is None:
            raise RuntimeError("No sheet for character")
        return self.current_sheet
    
    def _save_sheet(self):
        """Save current sheet to storage."""
        if self.current_character and self.current_sheet:
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def _get_filtered_subclasses(self, class_def) -> list:
        """Get subclass names filtered by legacy setting."""
        if not class_def or not class_def.subclasses:
            return ["(None)"]
        
        settings = get_settings_manager().settings
        legacy_filter = settings.legacy_content_filter
        all_subclasses = class_def.subclasses
        
        if legacy_filter == "no_legacy":
            filtered = [s for s in all_subclasses if not s.is_legacy]
        elif legacy_filter == "legacy_only":
            filtered = [s for s in all_subclasses if s.is_legacy]
        elif legacy_filter == "show_unupdated":
            non_legacy_names = {s.name.lower() for s in all_subclasses if not s.is_legacy}
            filtered = [s for s in all_subclasses if not s.is_legacy or s.name.lower() not in non_legacy_names]
        else:  # show_all
            filtered = all_subclasses
        
        return ["(None)"] + [s.name for s in filtered]

    def _create_widgets(self):
        """Create the main layout using grid for precise control."""
        # Configure grid weights - row 1 (content) expands, rows 0 and 2 (bars) don't
        self.grid_rowconfigure(0, weight=0)  # Top bar - fixed height
        self.grid_rowconfigure(1, weight=1)  # Content - expands
        self.grid_rowconfigure(2, weight=0)  # Bottom bar - fixed height
        self.grid_columnconfigure(0, weight=1)  # Full width
        
        # Top bar with character selector
        self._create_top_bar()
        
        # Main content area (scrollable) - middle section
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=1, column=0, sticky="nsew")
        
        self.content_scroll = ctk.CTkScrollableFrame(
            self.content_frame, fg_color="transparent"
        )
        self.content_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Bottom tab bar - created AFTER content, placed in row 2
        self._create_bottom_bar()
        
        # Placeholder when no character selected
        self.placeholder = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        self.placeholder.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            self.placeholder,
            text="Select a character from the dropdown above\nor click '+ New Character' to create one.",
            font=ctk.CTkFont(size=16),
            text_color=self.theme.get_text_secondary()
        ).pack(expand=True, pady=100)
        
        # Character sheet content (hidden initially)
        self.sheet_content = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        
        # Inventory content (hidden initially)
        self.inventory_content = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        
        # Spell list content (hidden initially)
        self.spells_content = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
    
    def _create_top_bar(self):
        """Create the top bar with character selector."""
        top_bar = ctk.CTkFrame(
            self, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=0, height=60
        )
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.grid_propagate(False)
        
        container = ctk.CTkFrame(top_bar, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(
            container, text="Character:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=(0, 10))
        
        # Character dropdown
        self.char_var = ctk.StringVar(value="Select a character...")
        self.char_combo = ctk.CTkComboBox(
            container, width=250, height=35,
            variable=self.char_var,
            values=self._get_character_names(),
            command=self._on_character_selected,
            state="readonly"
        )
        self.char_combo.pack(side="left", padx=(0, 15))
        
        # New Character button
        new_char_btn = ctk.CTkButton(
            container, text="+ New Character",
            width=120, height=35,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_new_character
        )
        new_char_btn.pack(side="left", padx=(0, 10))
        
        # Delete Character button
        self.delete_char_btn = ctk.CTkButton(
            container, text="🗑",
            width=35, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color="#c0392b",  # Red for delete
            command=self._on_delete_character
        )
        self.delete_char_btn.pack(side="left", padx=(0, 10))
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            container, text="↻",
            width=35, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._refresh_character_list
        )
        refresh_btn.pack(side="left")
    
    def _create_bottom_bar(self):
        """Create the bottom tab bar."""
        self.bottom_bar = ctk.CTkFrame(
            self, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=0, height=50
        )
        self.bottom_bar.grid(row=2, column=0, sticky="ew")
        self.bottom_bar.grid_propagate(False)
        
        container = ctk.CTkFrame(self.bottom_bar, fg_color="transparent")
        container.pack(expand=True, pady=8)
        
        btn_text = self.theme.get_current_color('text_primary')
        
        # Front (Main page) tab
        self.front_tab_btn = ctk.CTkButton(
            container, text="📋 Front",
            width=100, height=34,
            corner_radius=8,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=lambda: self._show_sheet_tab("front")
        )
        self.front_tab_btn.pack(side="left", padx=5)
        
        # Inventory tab
        self.inventory_tab_btn = ctk.CTkButton(
            container, text="🎒 Inventory",
            width=100, height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=lambda: self._show_sheet_tab("inventory")
        )
        self.inventory_tab_btn.pack(side="left", padx=5)
        
        # Spell List tab (only shown for spellcasters)
        self.spells_tab_btn = ctk.CTkButton(
            container, text="✨ Spells",
            width=100, height=34,
            corner_radius=8,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=btn_text,
            command=lambda: self._show_sheet_tab("spells")
        )
        # Initially hidden - will be shown if character is spellcaster
        
    def _show_sheet_tab(self, tab_name: str):
        """Switch between sheet tabs (front, inventory, spells)."""
        self._current_tab = tab_name
        
        # Reset all button styles
        self.front_tab_btn.configure(fg_color="transparent")
        self.inventory_tab_btn.configure(fg_color="transparent")
        self.spells_tab_btn.configure(fg_color="transparent")
        
        # Hide all content
        self.sheet_content.pack_forget()
        self.inventory_content.pack_forget()
        self.spells_content.pack_forget()
        
        active_color = self.theme.get_current_color('accent_primary')
        
        if tab_name == "front":
            self.front_tab_btn.configure(fg_color=active_color)
            if self.current_character:
                self.sheet_content.pack(fill="both", expand=True)
        elif tab_name == "inventory":
            self.inventory_tab_btn.configure(fg_color=active_color)
            if self.current_character:
                self._create_inventory_content()
                self.inventory_content.pack(fill="both", expand=True)
        elif tab_name == "spells":
            self.spells_tab_btn.configure(fg_color=active_color)
            if self.current_character:
                self._create_spells_content()
                self.spells_content.pack(fill="both", expand=True)
    
    def _update_spell_tab_visibility(self):
        """Show or hide the spells tab based on character classes."""
        if not self.current_character:
            self.spells_tab_btn.pack_forget()
            return
        
        # Check if any class is a spellcaster or has a spellcasting subclass
        has_spellcaster = any(
            cl.character_class.is_spellcaster() 
            for cl in self.current_character.classes
        )
        
        # Also check for spellcasting subclasses (e.g., Eldritch Knight, Arcane Trickster)
        if not has_spellcaster:
            has_spellcaster = any(
                cl.subclass == "Eldritch Knight" or cl.subclass == "Arcane Trickster"
                for cl in self.current_character.classes
            )
        
        # Check for subclasses with subclass_spells (e.g., Warrior of Shadow, Warrior of the Elements)
        if not has_spellcaster:
            class_manager = get_class_manager()
            for cl in self.current_character.classes:
                if cl.subclass:
                    class_def = class_manager.get_class(cl.character_class.value)
                    if class_def:
                        for subclass_def in class_def.subclasses:
                            if subclass_def.name == cl.subclass and subclass_def.subclass_spells:
                                # Check if character has reached the level to gain subclass spells
                                for spell in subclass_def.subclass_spells:
                                    if cl.level >= spell.level_gained:
                                        has_spellcaster = True
                                        break
                            if has_spellcaster:
                                break
                if has_spellcaster:
                    break
        
        if has_spellcaster:
            # Make sure it's packed after inventory
            self.spells_tab_btn.pack(side="left", padx=5)
        else:
            self.spells_tab_btn.pack_forget()
    
    def _get_character_names(self) -> List[str]:
        """Get list of character names."""
        return [c.name for c in self.character_manager.characters]
    
    def _refresh_character_list(self):
        """Refresh the character dropdown."""
        names = self._get_character_names()
        self.char_combo.configure(values=names if names else ["No characters found"])
        if self.current_character and self.current_character.name not in names:
            self.current_character = None
            self.current_sheet = None
            self._show_placeholder()
    
    def _on_new_character(self):
        """Show dialog to create a new character."""
        dialog = NewCharacterDialog(self, self.character_manager)
        self.wait_window(dialog)
        
        if dialog.result:
            # Refresh and select the new character
            self._refresh_character_list()
            self.char_var.set(dialog.result.name)
            self._on_character_selected(dialog.result.name)
    
    def _on_delete_character(self):
        """Delete the currently selected character."""
        if not self.current_character:
            messagebox.showwarning("No Character", "Please select a character to delete.")
            return
        
        char_name = self.current_character.name
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Delete Character",
            f"Are you sure you want to delete '{char_name}'?\n\n"
            "This will permanently remove the character and their sheet.\n"
            "This action cannot be undone.",
            icon='warning'
        )
        
        if result:
            # Delete character from manager
            self.character_manager.delete_character(char_name)
            
            # Delete the character sheet
            self.sheet_manager.delete_sheet(char_name)
            
            # Clear current selection
            self.current_character = None
            self.current_sheet = None
            
            # Refresh the list and show placeholder
            self._refresh_character_list()
            self.char_var.set("Select a character...")
            self._show_placeholder()
            
            messagebox.showinfo("Deleted", f"Character '{char_name}' has been deleted.")
    
    def _on_character_selected(self, name: str):
        """Handle character selection."""
        if name == "Select a character..." or name == "No characters found":
            return
        
        # Find the character
        for char in self.character_manager.characters:
            if char.name == name:
                self.current_character = char
                # Pass character to get_or_create_sheet for auto-applying class features
                self.current_sheet = self.sheet_manager.get_or_create_sheet(name, char)
                self._update_spell_tab_visibility()
                self._show_character_sheet()
                break
    
    def _show_placeholder(self):
        """Show the placeholder when no character selected."""
        self.sheet_content.pack_forget()
        self.inventory_content.pack_forget()
        self.spells_content.pack_forget()
        self.placeholder.pack(fill="both", expand=True)
    
    def _show_character_sheet(self):
        """Show the character sheet for the selected character."""
        self.placeholder.pack_forget()
        
        # Set flag to prevent callbacks during widget destruction/recreation
        self._rebuilding_ui = True
        
        # Clear existing content
        for widget in self.sheet_content.winfo_children():
            widget.destroy()
        for widget in self.inventory_content.winfo_children():
            widget.destroy()
        for widget in self.spells_content.winfo_children():
            widget.destroy()
        
        # Show loading indicator
        self._loading_frame = ctk.CTkFrame(self.content_scroll, fg_color="transparent")
        self._loading_frame.pack(fill="both", expand=True)
        self._loading_label = ctk.CTkLabel(
            self._loading_frame,
            text="Loading character sheet...",
            font=ctk.CTkFont(size=18),
            text_color=self.theme.get_text_secondary()
        )
        self._loading_label.pack(expand=True, pady=100)
        
        # Force update to show loading before heavy work
        self.update_idletasks()
        
        try:
            self._create_sheet_layout()
        finally:
            # Remove loading indicator
            if hasattr(self, '_loading_frame') and self._loading_frame.winfo_exists():
                self._loading_frame.pack_forget()
                self._loading_frame.destroy()
            # Clear rebuilding flag after layout is complete
            self._rebuilding_ui = False
        
        # Show appropriate tab
        self._show_sheet_tab(self._current_tab)
    
    def _create_sheet_layout(self):
        """Create the D&D 5e character sheet layout."""
        if not self.current_sheet or not self.current_character:
            return
        
        sheet = self.current_sheet
        
        # Auto-fill on new sheet creation if setting enabled
        settings = get_settings_manager().settings
        if settings.auto_fill_proficiencies and not sheet.other_proficiencies:
            class_levels = [(cl.character_class.value, cl.level) for cl in self.current_character.classes]
            default_profs = get_default_proficiencies(class_levels)
            if default_profs:
                default_profs += "\n\nLanguages: Common"
            else:
                default_profs = "Languages: Common"
            sheet.other_proficiencies = default_profs
        
        # Auto-calculate proficiency bonus from total level
        total_level = sum(cl.level for cl in self.current_character.classes)
        sheet.proficiency_bonus = calculate_proficiency_bonus(total_level)
        
        # Auto-calculate HP maximum if new sheet or changed
        if settings.auto_calculate_hp:
            class_levels = [(cl.character_class.value, cl.level) for cl in self.current_character.classes]
            con_mod = sheet.ability_scores.modifier(AbilityScore.CONSTITUTION)
            calculated_hp = calculate_hp_maximum(class_levels, con_mod, self.current_character.feats)
            # Only update if it looks like a fresh sheet (default HP)
            if sheet.hit_points.maximum in (0, 1, 10):
                sheet.hit_points.maximum = calculated_hp
                sheet.hit_points.current = calculated_hp
        
        # Auto-apply unarmored defense from class - check all classes with unarmored defense
        if self.current_character.classes:
            class_manager = get_class_manager()
            # Check all classes for unarmored defense (first one found wins)
            for cl in self.current_character.classes:
                class_def = class_manager.get_class(cl.character_class.value)
                if class_def and class_def.unarmored_defense:
                    sheet.unarmored_defense = class_def.unarmored_defense
                    break
                # Also check subclass for unarmored defense (e.g., Noble Genie Paladin, College of Dance Bard)
                if cl.subclass and class_def:
                    for subclass_def in class_def.subclasses:
                        if subclass_def.name == cl.subclass and subclass_def.unarmored_defense:
                            sheet.unarmored_defense = subclass_def.unarmored_defense
                            break
        
        # Recalculate AC and speed if auto-calculate is enabled (handles unarmored defense/movement)
        if settings.auto_calculate_ac:
            self._recalculate_ac()
            self._recalculate_speed()
        
        self.sheet_manager.update_sheet(self.current_character.name, sheet)
        
        # ===== ROW 1: Basic Info =====
        self._create_basic_info_section(sheet)
        
        # ===== ROW 2: Main content columns =====
        main_row = ctk.CTkFrame(self.sheet_content, fg_color="transparent")
        main_row.pack(fill="x", pady=5)
        
        # Use grid for the columns to have better control over sizing
        main_row.grid_columnconfigure(0, weight=0, minsize=270)  # Left column - fixed width
        main_row.grid_columnconfigure(1, weight=0, minsize=290)  # Middle column - fixed width
        main_row.grid_columnconfigure(2, weight=1)  # Right column - expands
        main_row.grid_rowconfigure(0, weight=1)  # Single row expands
        
        # Left column: Ability Scores, Saving Throws, Skills
        left_col = ctk.CTkFrame(main_row, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        self._create_ability_scores_section(left_col, sheet)
        self._create_saving_throws_section(left_col, sheet)
        self._create_skills_section(left_col, sheet)
        
        # Middle column: Combat stats, Class Features (scrollable), Attacks
        middle_col = ctk.CTkFrame(main_row, fg_color="transparent")
        middle_col.grid(row=0, column=1, sticky="nsew", padx=5)
        
        # Create combat section at the top
        self._create_combat_section(middle_col, sheet)
        
        # Create a container for class features (no fixed height - scales with content)
        middle_scrollable = ctk.CTkFrame(
            middle_col, fg_color="transparent"
        )
        middle_scrollable.pack(fill="x", pady=2)
        
        self._create_class_features_section(middle_scrollable, sheet)
        
        # Attacks at the bottom - always visible
        self._create_attacks_section(middle_col, sheet)
        
        # Right column: Features & Traits (large), Other Proficiencies, Notes, Personality
        right_col = ctk.CTkFrame(main_row, fg_color="transparent")
        right_col.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        
        self._create_features_section(right_col, sheet)
        self._create_proficiencies_section(right_col, sheet)
        self._create_notes_section(right_col, sheet)
        self._create_personality_section(right_col, sheet)
    
    def _create_section_header(self, parent, title: str) -> ctk.CTkFrame:
        """Create a section header."""
        header = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5, height=24
        )
        header.pack(fill="x", pady=(5, 3))
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text=title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white"
        ).pack(side="left", padx=8, pady=3)
        
        return header
    
    def _create_basic_info_section(self, sheet: CharacterSheet):
        """Create the basic info section with dynamic sizing."""
        character = self._require_character()
        
        info_frame = ctk.CTkFrame(
            self.sheet_content,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        info_frame.pack(fill="x", pady=(0, 5))
        
        # Row 1: Name, Classes with editable levels, Race
        row1 = ctk.CTkFrame(info_frame, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=(4, 2))
        
        # Character name
        name_frame = ctk.CTkFrame(row1, fg_color="transparent")
        name_frame.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(name_frame, text="Name", font=ctk.CTkFont(size=9)).pack(anchor="w")
        
        self.name_var = ctk.StringVar(value=sheet.character_name or character.name)
        name_entry = ctk.CTkEntry(
            name_frame, textvariable=self.name_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            width=150, height=26
        )
        name_entry.pack()
        name_entry.bind("<FocusOut>", lambda e: self._save_field("character_name", self.name_var.get()))
        
        # Classes section with editable levels and subclass selection
        class_frame = ctk.CTkFrame(row1, fg_color="transparent")
        class_frame.pack(side="left", padx=8)
        ctk.CTkLabel(class_frame, text="Class & Level", font=ctk.CTkFont(size=9)).pack(anchor="w")
        
        classes_container = ctk.CTkFrame(class_frame, fg_color="transparent")
        classes_container.pack(anchor="w")
        
        self.class_level_widgets = []
        self.subclass_widgets = []
        class_manager = get_class_manager()
        
        for i, cl in enumerate(character.classes):
            cl_row = ctk.CTkFrame(classes_container, fg_color="transparent")
            cl_row.pack(side="left", padx=(0, 8))
            
            # Class name label
            ctk.CTkLabel(cl_row, text=cl.character_class.value, 
                        font=ctk.CTkFont(size=11)).pack(side="left")
            
            # Level entry
            level_var = ctk.StringVar(value=str(cl.level))
            level_entry = ctk.CTkEntry(
                cl_row, textvariable=level_var,
                width=35, height=22, justify="center"
            )
            level_entry.pack(side="left", padx=2)
            level_entry.bind("<FocusOut>", lambda e, idx=i, var=level_var: self._on_class_level_change(idx, var.get()))
            level_entry.bind("<Return>", lambda e, idx=i, var=level_var: self._on_class_level_change(idx, var.get()))
            
            self.class_level_widgets.append((cl.character_class, level_var))
            
            # Check if subclass selection should be shown
            class_def = class_manager.get_class(cl.character_class.value)
            if class_def and class_def.subclasses and cl.level >= class_def.subclass_level:
                # Get filtered subclass options based on legacy setting
                subclass_names = self._get_filtered_subclasses(class_def)
                current_subclass = cl.subclass if cl.subclass else "(None)"
                
                # Only show dropdown if there are subclasses (more than just "(None)")
                if len(subclass_names) > 1:
                    # Subclass dropdown
                    subclass_var = ctk.StringVar(value=current_subclass)
                    subclass_combo = ctk.CTkComboBox(
                        cl_row, width=120, height=22,
                        values=subclass_names,
                        variable=subclass_var,
                        font=ctk.CTkFont(size=10),
                        command=lambda val, idx=i: self._on_subclass_change(idx, val)
                    )
                    subclass_combo.pack(side="left", padx=2)
                    self.subclass_widgets.append((i, subclass_var, subclass_combo))
        
        # Add class button
        add_class_btn = ctk.CTkButton(
            classes_container, text="+", width=22, height=22,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._show_add_class_dialog
        )
        add_class_btn.pack(side="left", padx=2)
        
        # Lineage dropdown (auto-populated from lineage manager)
        lineage_frame = ctk.CTkFrame(row1, fg_color="transparent")
        lineage_frame.pack(side="left", padx=8)
        ctk.CTkLabel(lineage_frame, text="Lineage", font=ctk.CTkFont(size=9)).pack(anchor="w")
        
        from lineage import get_lineage_manager
        lineage_manager = get_lineage_manager()
        lineage_names = ["(None)"] + lineage_manager.get_lineage_names()
        current_lineage = character.lineage if character.lineage else "(None)"
        
        self.lineage_var = ctk.StringVar(value=current_lineage)
        self.lineage_combo = ctk.CTkComboBox(
            lineage_frame, width=130, height=24,
            values=lineage_names,
            variable=self.lineage_var,
            command=self._on_lineage_change
        )
        self.lineage_combo.pack()
        
        # Row 2: Background, Alignment, Experience
        row2 = ctk.CTkFrame(info_frame, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=(2, 4))
        
        # Background dropdown (auto-populated from background manager)
        bg_frame = ctk.CTkFrame(row2, fg_color="transparent")
        bg_frame.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(bg_frame, text="Background", font=ctk.CTkFont(size=9)).pack(anchor="w")
        
        from background import get_background_manager
        background_manager = get_background_manager()
        background_names = ["(None)"] + background_manager.get_background_names()
        current_background = sheet.background if sheet.background else "(None)"
        
        self.background_var = ctk.StringVar(value=current_background)
        bg_combo = ctk.CTkComboBox(
            bg_frame, width=130, height=24,
            values=background_names,
            variable=self.background_var,
            command=self._on_background_change
        )
        bg_combo.pack()
        
        # Alignment
        align_frame = ctk.CTkFrame(row2, fg_color="transparent")
        align_frame.pack(side="left", padx=8)
        ctk.CTkLabel(align_frame, text="Alignment", font=ctk.CTkFont(size=9)).pack(anchor="w")
        self.alignment_var = ctk.StringVar(value=sheet.alignment)
        align_combo = ctk.CTkComboBox(
            align_frame, width=120, height=24,
            values=["", "Lawful Good", "Neutral Good", "Chaotic Good",
                    "Lawful Neutral", "True Neutral", "Chaotic Neutral",
                    "Lawful Evil", "Neutral Evil", "Chaotic Evil"],
            variable=self.alignment_var,
            command=lambda _: self._save_field("alignment", self.alignment_var.get())
        )
        align_combo.pack()
        
        # Experience Points
        xp_frame = ctk.CTkFrame(row2, fg_color="transparent")
        xp_frame.pack(side="left", padx=8)
        ctk.CTkLabel(xp_frame, text="XP", font=ctk.CTkFont(size=9)).pack(anchor="w")
        self.xp_var = ctk.StringVar(value=str(sheet.experience_points))
        xp_entry = ctk.CTkEntry(xp_frame, textvariable=self.xp_var, width=70, height=24)
        xp_entry.pack()
        xp_entry.bind("<FocusOut>", lambda e: self._save_int_field("experience_points", self.xp_var.get()))
        
        # Age
        age_frame = ctk.CTkFrame(row2, fg_color="transparent")
        age_frame.pack(side="left", padx=8)
        ctk.CTkLabel(age_frame, text="Age", font=ctk.CTkFont(size=9)).pack(anchor="w")
        self.age_var = ctk.StringVar(value=sheet.age or "")
        age_entry = ctk.CTkEntry(age_frame, textvariable=self.age_var, width=50, height=24)
        age_entry.pack()
        age_entry.bind("<FocusOut>", lambda e: self._save_field("age", self.age_var.get()))
        
        # Height
        height_frame = ctk.CTkFrame(row2, fg_color="transparent")
        height_frame.pack(side="left", padx=8)
        ctk.CTkLabel(height_frame, text="Height", font=ctk.CTkFont(size=9)).pack(anchor="w")
        self.height_var = ctk.StringVar(value=sheet.height or "")
        height_entry = ctk.CTkEntry(height_frame, textvariable=self.height_var, width=60, height=24)
        height_entry.pack()
        height_entry.bind("<FocusOut>", lambda e: self._save_field("height", self.height_var.get()))
        
        # Weight
        weight_frame = ctk.CTkFrame(row2, fg_color="transparent")
        weight_frame.pack(side="left", padx=8)
        ctk.CTkLabel(weight_frame, text="Weight", font=ctk.CTkFont(size=9)).pack(anchor="w")
        self.weight_var = ctk.StringVar(value=sheet.weight or "")
        weight_entry = ctk.CTkEntry(weight_frame, textvariable=self.weight_var, width=60, height=24)
        weight_entry.pack()
        weight_entry.bind("<FocusOut>", lambda e: self._save_field("weight", self.weight_var.get()))
        
        # Long Rest button
        long_rest_btn = ctk.CTkButton(
            row2, text="🌙 Long Rest", width=100, height=28,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            command=self._on_long_rest
        )
        long_rest_btn.pack(side="right", padx=8)
    
    def _on_subclass_change(self, class_index: int, subclass_name: str):
        """Handle subclass selection change."""
        character = self._require_character()
        sheet = self._require_sheet()
        
        if class_index >= len(character.classes):
            return
        
        class_manager = get_class_manager()
        class_level = character.classes[class_index]
        class_def = class_manager.get_class(class_level.character_class.value)
        
        # Get old subclass definition to potentially remove its grants
        old_subclass_name = class_level.subclass
        old_subclass_def = None
        if old_subclass_name and class_def:
            for sc in class_def.subclasses:
                if sc.name == old_subclass_name:
                    old_subclass_def = sc
                    break
        
        # Update the subclass
        if subclass_name == "(None)":
            character.classes[class_index].subclass = ""
        else:
            character.classes[class_index].subclass = subclass_name
        
        # Get new subclass definition
        new_subclass_def = None
        if subclass_name and subclass_name != "(None)" and class_def:
            for sc in class_def.subclasses:
                if sc.name == subclass_name:
                    new_subclass_def = sc
                    break
        
        # Handle subclass-granted proficiencies
        # Remove old subclass proficiencies from other_proficiencies tracking
        if old_subclass_def:
            # Clear unarmored defense if it came from the old subclass
            if old_subclass_def.unarmored_defense and sheet.unarmored_defense == old_subclass_def.unarmored_defense:
                sheet.unarmored_defense = ""
        
        # Apply new subclass proficiencies
        if new_subclass_def:
            # Apply subclass unarmored defense if character doesn't have one and subclass provides it
            if new_subclass_def.unarmored_defense and not sheet.unarmored_defense:
                sheet.unarmored_defense = new_subclass_def.unarmored_defense
        
        # Update subclass spells
        from character import update_subclass_spells
        update_subclass_spells(character)
        
        # Save changes
        self.character_manager.save_characters()
        self._save_sheet()
        
        # Update spell tab visibility (for Eldritch Knight and other spellcasting subclasses)
        self._update_spell_tab_visibility()
        
        # Refresh the sheet to update features
        self._show_character_sheet()
    
    def _on_lineage_change(self, value: str):
        """Handle lineage selection change."""
        character = self._require_character()
        sheet = self._require_sheet()
        if not character or not sheet:
            return
        
        lineage_name = value if value != "(None)" else ""
        character.lineage = lineage_name
        
        # Update speed from lineage if selected
        if lineage_name:
            from lineage import get_lineage_manager
            lineage = get_lineage_manager().get_lineage(lineage_name)
            if lineage and lineage.speed:
                sheet.speed = lineage.speed
                # Update speed display if widget exists
                if hasattr(self, 'speed_var'):
                    self.speed_var.set(str(lineage.speed))
                # Save sheet
                self.sheet_manager.save()
        
        self.character_manager.save_characters()
        
        # Refresh just the features section instead of whole sheet
        self._refresh_lineage_traits_section()
    
    def _on_background_change(self, value: str):
        """Handle background selection change."""
        sheet = self._require_sheet()
        if not sheet:
            return
        
        background_name = value if value != "(None)" else ""
        sheet.background = background_name
        self.sheet_manager.save()
    
    def _on_class_level_change(self, class_index: int, level_str: str):
        """Handle class level change."""
        character = self._require_character()
        sheet = self._require_sheet()
        
        try:
            new_level = int(level_str) if level_str.strip() else 0
            new_level = min(20, new_level)  # Cap at 20, but allow 0
            
            if class_index >= len(character.classes):
                return
            
            # Check if trying to remove a non-primary class (set level to 0)
            if new_level <= 0 and class_index > 0:
                # This is a multiclass removal
                settings = get_settings_manager().settings
                class_to_remove = character.classes[class_index]
                
                if settings.warn_multiclass_removal:
                    # Show warning dialog
                    result = messagebox.askyesno(
                        "Remove Multiclass",
                        f"Setting {class_to_remove.character_class.value} to level 0 will remove this class "
                        f"from the character.\n\nThis will also remove any class-specific features and "
                        f"spells associated with this class.\n\nAre you sure you want to continue?",
                        icon='warning'
                    )
                    if not result:
                        # User cancelled - restore the old value
                        self.class_level_widgets[class_index][1].set(str(class_to_remove.level))
                        return
                
                # Remove the multiclass
                self._remove_multiclass(class_index)
                return
            
            # Don't allow primary class to go below 1
            if class_index == 0:
                new_level = max(1, new_level)
            else:
                new_level = max(1, new_level)  # Non-primary also min 1 (0 is handled above)
            
            character.classes[class_index].level = new_level
            
            # Update subclass spells (may lose spells if level dropped below requirement)
            from character import update_subclass_spells
            update_subclass_spells(character)
            
            # Handle Slippery Mind (Rogue level 15) - auto-apply WIS and CHA saving throw proficiencies
            sheet = self._require_sheet()
            if sheet:
                self._update_slippery_mind(character, sheet, class_index, new_level)
            
            self.character_manager.save_characters()
            
            # Update proficiency bonus and HP
            self._recalculate_from_level_change()
            
            # Refresh the sheet to update class features widget
            self._show_character_sheet()
        except ValueError:
            pass
    
    def _remove_multiclass(self, class_index: int):
        """Remove a multiclass from the character."""
        character = self._require_character()
        sheet = self._require_sheet()
        
        if class_index <= 0 or class_index >= len(character.classes):
            return
        
        removed_class = character.classes[class_index]
        class_name = removed_class.character_class.value
        
        # Remove the class
        del character.classes[class_index]
        
        # Update subclass spells and class feature spells (this will remove spells like Mending for Artificer)
        from character import update_subclass_spells
        update_subclass_spells(character)
        
        # Remove class-specific spells if this was a spellcasting class
        if removed_class.character_class.is_spellcaster():
            # Get spells that are exclusive to this class
            from spell_manager import SpellManager
            spell_manager = self.spell_manager if hasattr(self, 'spell_manager') and self.spell_manager else SpellManager()
            if spell_manager:
                spells_to_remove = []
                remaining_classes = {cl.character_class for cl in character.classes}
                
                for spell_name in list(character.known_spells):
                    spell = spell_manager.get_spell(spell_name)
                    if spell:
                        # Check if any remaining class can cast this spell
                        spell_classes = set(spell.classes)
                        if not spell_classes.intersection(remaining_classes):
                            spells_to_remove.append(spell_name)
                
                for spell_name in spells_to_remove:
                    character.remove_spell(spell_name)
        
        # Remove class feature uses for this class
        keys_to_remove = [k for k in sheet.class_feature_uses.keys() 
                         if k.startswith(f"{class_name}:")]
        for key in keys_to_remove:
            del sheet.class_feature_uses[key]
        
        # Update hit dice tracking
        self._update_hit_dice_for_classes()
        
        # Recalculate HP if auto-calc is enabled
        settings = get_settings_manager().settings
        if settings.auto_calculate_hp:
            self._auto_update_hp()
        
        # Save changes
        self.character_manager.save_characters()
        self.sheet_manager.update_sheet(character.name, sheet)
        
        # Refresh the entire sheet
        self._update_spell_tab_visibility()
        self._show_character_sheet()
        
        messagebox.showinfo("Class Removed", f"{class_name} has been removed from {character.name}.")
    
    def _update_hit_dice_for_classes(self):
        """Update hit dice tracking based on current classes."""
        if not self.current_sheet or not self.current_character:
            return
        
        class_levels = [(cl.character_class.value, cl.level) for cl in self.current_character.classes]
        hit_dice = get_hit_dice_for_classes(class_levels)
        
        # Update total
        total_dice = sum(hit_dice.values())
        self.current_sheet.hit_points.hit_dice_total = total_dice
        
        # Update hit dice by type - preserve remaining counts where possible
        old_by_type = self.current_sheet.hit_points.hit_dice_by_type.copy()
        new_by_type = {}
        
        for die_type, count in hit_dice.items():
            # Keep the min of old remaining and new total for this die type
            old_remaining = old_by_type.get(die_type, count)
            new_by_type[die_type] = min(old_remaining, count)
        
        self.current_sheet.hit_points.hit_dice_by_type = new_by_type
        self.current_sheet.hit_points.hit_dice_remaining = sum(new_by_type.values())
    
    def _show_add_class_dialog(self):
        """Show dialog to add a new class (multiclass)."""
        character = self._require_character()
        
        # Get classes not already taken
        taken_classes = {cl.character_class for cl in character.classes}
        available = [c for c in CharacterClass.all_classes() if c not in taken_classes and c != CharacterClass.CUSTOM]
        
        if not available:
            messagebox.showinfo("No Classes Available", "Character already has all available classes.")
            return
        
        dialog = AddClassDialog(self, available)
        self.wait_window(dialog)
        
        if dialog.result:
            # Check if this is the first class (starting class)
            is_first_class = len(character.classes) == 0
            
            character.add_class(dialog.result, 1)
            
            # Apply class feature spells (e.g., Mending for Artificer)
            from character import update_subclass_spells
            update_subclass_spells(character)
            
            # If this is the first class and auto-apply saving throws is enabled
            if is_first_class and get_settings_manager().settings.auto_apply_saving_throws:
                self._apply_class_features(dialog.result.value)
            
            self.character_manager.save_characters()
            self._update_spell_tab_visibility()
            self._show_character_sheet()
    
    def _apply_class_features(self, class_name: str):
        """Apply class features like saving throws and unarmored defense for a starting class."""
        if not self.current_character or not self.current_sheet:
            return
        
        class_manager = get_class_manager()
        class_def = class_manager.get_class(class_name)
        
        if not class_def:
            return
        
        sheet = self.current_sheet
        
        # Apply saving throw proficiencies
        for save in class_def.saving_throw_proficiencies:
            ability = None
            if save == "STR":
                ability = AbilityScore.STRENGTH
            elif save == "DEX":
                ability = AbilityScore.DEXTERITY
            elif save == "CON":
                ability = AbilityScore.CONSTITUTION
            elif save == "INT":
                ability = AbilityScore.INTELLIGENCE
            elif save == "WIS":
                ability = AbilityScore.WISDOM
            elif save == "CHA":
                ability = AbilityScore.CHARISMA
            
            if ability:
                sheet.saving_throws.set_proficiency(ability, True)
        
        # Apply unarmored defense if class has it
        if class_def.unarmored_defense:
            sheet.unarmored_defense = class_def.unarmored_defense
            # Recalculate AC and speed if auto-calculate is on
            if get_settings_manager().settings.auto_calculate_ac:
                self._recalculate_ac()
                self._recalculate_speed()
        
        # Save changes
        self.sheet_manager.update_sheet(self.current_character.name, sheet)
        self.character_manager.save_characters()
    
    def _recalculate_from_level_change(self):
        """Recalculate stats when level changes."""
        if not self.current_sheet or not self.current_character:
            return
        
        # Update proficiency bonus
        total_level = sum(cl.level for cl in self.current_character.classes)
        self.current_sheet.proficiency_bonus = calculate_proficiency_bonus(total_level)
        if hasattr(self, 'prof_label'):
            self.prof_label.configure(text=f"+{self.current_sheet.proficiency_bonus}")
        
        # Update hit dice
        self._update_hit_dice_for_classes()
        
        # Check for Primal Champion (Barbarian level 20)
        self._update_primal_champion()
        
        # Check for Body and Mind (Monk level 20)
        self._update_body_and_mind()
        
        # Update HP if auto-calc is on
        settings = get_settings_manager().settings
        if settings.auto_calculate_hp:
            self._auto_update_hp()
        
        # Recalculate speed (Monk's Unarmored Movement changes with level)
        if settings.auto_calculate_ac:
            self._recalculate_speed()
        
        self._update_derived_stats()
        self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def _create_ability_scores_section(self, parent, sheet: CharacterSheet):
        """Create the ability scores section."""
        self._create_section_header(parent, "ABILITY SCORES")
        
        scores_frame = ctk.CTkFrame(parent, fg_color="transparent")
        scores_frame.pack(fill="x", pady=5)
        
        # Create ability score widgets in 2 rows of 3
        self.ability_widgets = {}
        row1 = ctk.CTkFrame(scores_frame, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        row2 = ctk.CTkFrame(scores_frame, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        
        abilities_row1 = [AbilityScore.STRENGTH, AbilityScore.DEXTERITY, AbilityScore.CONSTITUTION]
        abilities_row2 = [AbilityScore.INTELLIGENCE, AbilityScore.WISDOM, AbilityScore.CHARISMA]
        
        for ability in abilities_row1:
            widget = AbilityScoreWidget(
                row1, ability, sheet.ability_scores.get(ability),
                on_change=self._on_ability_change
            )
            widget.pack(side="left", padx=3)
            self.ability_widgets[ability] = widget
        
        for ability in abilities_row2:
            widget = AbilityScoreWidget(
                row2, ability, sheet.ability_scores.get(ability),
                on_change=self._on_ability_change
            )
            widget.pack(side="left", padx=3)
            self.ability_widgets[ability] = widget
    
    def _create_saving_throws_section(self, parent, sheet: CharacterSheet):
        """Create the saving throws section."""
        self._create_section_header(parent, "SAVING THROWS")
        
        saves_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        saves_frame.pack(fill="x", pady=3)
        
        self.save_widgets = {}
        for ability in AbilityScore:
            modifier = sheet.get_saving_throw_bonus(ability)
            proficient = sheet.saving_throws.is_proficient(ability)
            
            widget = SavingThrowWidget(
                saves_frame, ability, modifier, proficient,
                on_change=self._on_save_change
            )
            widget.pack(fill="x", padx=8, pady=1)
            self.save_widgets[ability] = widget
    
    def _create_skills_section(self, parent, sheet: CharacterSheet):
        """Create the skills section."""
        self._create_section_header(parent, "SKILLS")
        
        # Regular frame (not scrollable) for skills
        skills_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        skills_frame.pack(fill="x", pady=3)
        
        # Get Jack of All Trades bonus for non-proficient skills
        jack_bonus = self._get_jack_of_all_trades_bonus()
        
        self.skill_widgets = {}
        for skill in Skill:
            modifier = sheet.get_skill_bonus(skill, jack_bonus)
            prof_level = sheet.skills.get(skill)
            
            widget = SkillWidget(
                skills_frame, skill, modifier, prof_level,
                on_change=self._on_skill_change
            )
            widget.pack(fill="x", padx=8, pady=0)
            self.skill_widgets[skill] = widget
    
    def _create_combat_section(self, parent, sheet: CharacterSheet):
        """Create the combat stats section."""
        self._create_section_header(parent, "COMBAT")
        
        combat_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        combat_frame.pack(fill="x", pady=3)
        
        # Row of combat stats
        stats_row = ctk.CTkFrame(combat_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=8, pady=8)
        
        # Armor Class
        ac_frame = ctk.CTkFrame(stats_row, fg_color=self.theme.get_current_color('bg_tertiary'),
                                corner_radius=8, width=65, height=60)
        ac_frame.pack(side="left", padx=3)
        ac_frame.pack_propagate(False)
        ctk.CTkLabel(ac_frame, text="AC", font=ctk.CTkFont(size=9, weight="bold")).pack(pady=(5, 0))
        self.ac_var = ctk.StringVar(value=str(sheet.armor_class))
        ac_entry = ctk.CTkEntry(
            ac_frame, width=40, height=26,
            textvariable=self.ac_var, justify="center",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        ac_entry.pack(pady=3)
        ac_entry.bind("<FocusOut>", lambda e: self._save_int_field("armor_class", self.ac_var.get()))
        
        # Initiative
        init_frame = ctk.CTkFrame(stats_row, fg_color=self.theme.get_current_color('bg_tertiary'),
                                  corner_radius=8, width=65, height=60)
        init_frame.pack(side="left", padx=3)
        init_frame.pack_propagate(False)
        ctk.CTkLabel(init_frame, text="INIT", font=ctk.CTkFont(size=9, weight="bold")).pack(pady=(5, 0))
        init_mod = sheet.get_initiative()
        init_text = f"+{init_mod}" if init_mod >= 0 else str(init_mod)
        self.init_label = ctk.CTkLabel(
            init_frame, text=init_text,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.init_label.pack(pady=3)
        
        # Speed
        speed_frame = ctk.CTkFrame(stats_row, fg_color=self.theme.get_current_color('bg_tertiary'),
                                   corner_radius=8, width=65, height=60)
        speed_frame.pack(side="left", padx=3)
        speed_frame.pack_propagate(False)
        ctk.CTkLabel(speed_frame, text="SPEED", font=ctk.CTkFont(size=9, weight="bold")).pack(pady=(5, 0))
        self.speed_var = ctk.StringVar(value=str(sheet.speed))
        speed_entry = ctk.CTkEntry(
            speed_frame, width=40, height=26,
            textvariable=self.speed_var, justify="center",
            font=ctk.CTkFont(size=12)
        )
        speed_entry.pack(pady=3)
        speed_entry.bind("<FocusOut>", lambda e: self._save_int_field("speed", self.speed_var.get()))
        
        # Proficiency Bonus (auto-calculated from level, displayed as label)
        prof_frame = ctk.CTkFrame(stats_row, fg_color=self.theme.get_current_color('bg_tertiary'),
                                  corner_radius=8, width=65, height=60)
        prof_frame.pack(side="left", padx=3)
        prof_frame.pack_propagate(False)
        ctk.CTkLabel(prof_frame, text="PROF", font=ctk.CTkFont(size=9, weight="bold")).pack(pady=(5, 0))
        
        # Display proficiency as label (auto-calculated)
        prof_text = f"+{sheet.proficiency_bonus}"
        self.prof_label = ctk.CTkLabel(
            prof_frame, text=prof_text,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.prof_label.pack(pady=3)
        self.prof_var = ctk.StringVar(value=str(sheet.proficiency_bonus))
        
        # Armor and Shield dropdowns (only if auto-calculate AC is enabled)
        if get_settings_manager().settings.auto_calculate_ac:
            self._create_armor_dropdowns(combat_frame, sheet)
        
        # Hit Points widget with auto-calculation support
        self._create_hp_section(combat_frame, sheet)
        
        # Death Saves widget with inspiration
        self.death_widget = DeathSavesWidget(
            combat_frame, sheet.death_saves,
            inspiration=sheet.inspiration,
            on_change=self._on_death_saves_change,
            on_inspiration_change=self._on_inspiration_change
        )
        self.death_widget.pack(fill="x", padx=8, pady=(3, 8))
    
    def _create_armor_dropdowns(self, parent, sheet: CharacterSheet):
        """Create armor and shield dropdowns for AC calculation."""
        # Armor row
        armor_frame = ctk.CTkFrame(parent, fg_color="transparent")
        armor_frame.pack(fill="x", padx=8, pady=(0, 3))
        
        # Armor dropdown
        ctk.CTkLabel(armor_frame, text="Armor:", font=ctk.CTkFont(size=10)).pack(side="left")
        
        # Build armor options list
        armor_options = [opt[0] for opt in COMMON_ARMOR_OPTIONS]
        
        # Find current armor in list
        current_armor = sheet.armor_type if sheet.armor_type else "None"
        # Match to display name
        current_display = "None"
        for display, armor_type in COMMON_ARMOR_OPTIONS:
            if armor_type.display_name == current_armor:
                current_display = display
                break
        
        self.armor_var = ctk.StringVar(value=current_display)
        armor_dropdown = ctk.CTkComboBox(
            armor_frame, values=armor_options,
            variable=self.armor_var, width=180, height=24,
            font=ctk.CTkFont(size=10),
            command=self._on_armor_change
        )
        armor_dropdown.pack(side="left", padx=(5, 10))
        
        # Show unarmored defense info if applicable
        if sheet.unarmored_defense:
            ud_label = ctk.CTkLabel(
                armor_frame, 
                text=f"Unarmored: {sheet.unarmored_defense}",
                font=ctk.CTkFont(size=9),
                text_color=self.theme.get_current_color('text_secondary')
            )
            ud_label.pack(side="left", padx=5)
        
        # Shield row (separate row to avoid text cutoff)
        shield_frame = ctk.CTkFrame(parent, fg_color="transparent")
        shield_frame.pack(fill="x", padx=8, pady=(0, 5))
        
        ctk.CTkLabel(shield_frame, text="Shield:", font=ctk.CTkFont(size=10)).pack(side="left")
        
        # Build shield options list
        shield_options = [opt[0] for opt in SHIELD_OPTIONS]
        
        # Find current shield in list
        current_shield_bonus = sheet.shield_bonus if hasattr(sheet, 'shield_bonus') else (2 if sheet.has_shield else 0)
        current_shield_display = "None"
        for display, bonus in SHIELD_OPTIONS:
            if bonus == current_shield_bonus:
                current_shield_display = display
                break
        
        self.shield_var = ctk.StringVar(value=current_shield_display)
        shield_dropdown = ctk.CTkComboBox(
            shield_frame, values=shield_options,
            variable=self.shield_var, width=120, height=24,
            font=ctk.CTkFont(size=10),
            command=self._on_shield_change
        )
        shield_dropdown.pack(side="left", padx=(5, 10))
    
    def _on_armor_change(self, choice: str):
        """Handle armor dropdown change."""
        if not self.current_sheet:
            return
        
        # Find the armor type from the display choice
        armor_type = ArmorType.NONE
        for display, at in COMMON_ARMOR_OPTIONS:
            if display == choice:
                armor_type = at
                break
        
        # Save the armor type name
        self.current_sheet.armor_type = armor_type.display_name
        
        # Recalculate AC and speed (Monk's Unarmored Movement)
        self._recalculate_ac()
        self._recalculate_speed()
    
    def _on_shield_change(self, choice: str):
        """Handle shield dropdown change."""
        if not self.current_sheet:
            return
        
        # Find the shield bonus from the display choice
        shield_bonus = 0
        for display, bonus in SHIELD_OPTIONS:
            if display == choice:
                shield_bonus = bonus
                break
        
        # Update sheet
        self.current_sheet.shield_bonus = shield_bonus
        self.current_sheet.has_shield = shield_bonus > 0  # Keep legacy field in sync
        
        # Recalculate AC and speed (Monk's Unarmored Movement)
        self._recalculate_ac()
        self._recalculate_speed()
    
    def _recalculate_ac(self):
        """Recalculate AC based on armor, shield, and abilities."""
        if not self.current_sheet:
            return
        
        sheet = self.current_sheet
        
        # Get armor type
        armor_type = ArmorType.from_name(sheet.armor_type)
        
        # Get ability modifiers
        dex_mod = sheet.ability_scores.modifier(AbilityScore.DEXTERITY)
        con_mod = sheet.ability_scores.modifier(AbilityScore.CONSTITUTION)
        wis_mod = sheet.ability_scores.modifier(AbilityScore.WISDOM)
        cha_mod = sheet.ability_scores.modifier(AbilityScore.CHARISMA)
        
        # Get shield bonus
        shield_bonus = sheet.shield_bonus if hasattr(sheet, 'shield_bonus') else (2 if sheet.has_shield else 0)
        
        # Calculate AC
        new_ac = calculate_ac(
            armor_type=armor_type,
            dex_modifier=dex_mod,
            has_shield=False,  # Use shield_bonus instead
            unarmored_defense=sheet.unarmored_defense,
            con_modifier=con_mod,
            wis_modifier=wis_mod,
            cha_modifier=cha_mod,
            shield_bonus=shield_bonus
        )
        
        # Update sheet and UI
        sheet.armor_class = new_ac
        if hasattr(self, 'ac_var'):
            self.ac_var.set(str(new_ac))
        
        # Save
        if self.current_character:
            self.sheet_manager.update_sheet(self.current_character.name, sheet)
            self.character_manager.save_characters()
    
    def _recalculate_speed(self):
        """Recalculate speed based on armor and Monk's Unarmored Movement."""
        if not self.current_sheet or not self.current_character:
            return
        
        sheet = self.current_sheet
        armor_type = ArmorType.from_name(sheet.armor_type)
        shield_bonus = sheet.shield_bonus if hasattr(sheet, 'shield_bonus') else (2 if sheet.has_shield else 0)
        
        # Start with base speed
        speed = sheet.base_speed
        
        # Check if character has Monk class with Unarmored Movement
        # Only applies when not wearing armor AND not wielding a shield
        if armor_type == ArmorType.NONE and shield_bonus == 0:
            class_manager = get_class_manager()
            for class_level in self.current_character.classes:
                if class_level.character_class.value == "Monk":
                    # Get Monk class definition
                    monk_class = class_manager.get_class("Monk")
                    if monk_class and monk_class.levels:
                        # Get the class_specific data for the Monk's current level
                        # levels dict uses int keys
                        level_key = class_level.level
                        if level_key in monk_class.levels:
                            level_data = monk_class.levels[level_key]
                            # ClassLevel object has class_specific attribute
                            class_specific = getattr(level_data, 'class_specific', {})
                            
                            unarmored_movement = class_specific.get("Unarmored Movement", "-")
                            if unarmored_movement and unarmored_movement != "-":
                                # Parse the bonus (e.g., "+10 ft." -> 10)
                                match = re.search(r'\+(\d+)', unarmored_movement)
                                if match:
                                    speed_bonus = int(match.group(1))
                                    speed += speed_bonus
                    break  # Only one Monk class matters
        
        # Update sheet and UI
        sheet.speed = speed
        if hasattr(self, 'speed_var'):
            self.speed_var.set(str(speed))
        
        # Save
        if self.current_character:
            self.sheet_manager.update_sheet(self.current_character.name, sheet)
            self.character_manager.save_characters()
    
    def _create_hp_section(self, parent, sheet: CharacterSheet):
        """Create the HP section."""
        hp_frame = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_tertiary'),
                                corner_radius=8)
        hp_frame.pack(fill="x", padx=8, pady=5)
        
        # Title row
        title_row = ctk.CTkFrame(hp_frame, fg_color="transparent")
        title_row.pack(fill="x", padx=8, pady=(5, 3))
        
        ctk.CTkLabel(
            title_row, text="HIT POINTS",
            font=ctk.CTkFont(size=10, weight="bold")
        ).pack(side="left")
        
        # Main HP row
        hp_row = ctk.CTkFrame(hp_frame, fg_color="transparent")
        hp_row.pack(fill="x", padx=8, pady=3)
        
        # Current HP
        ctk.CTkLabel(hp_row, text="Current:", font=ctk.CTkFont(size=10)).pack(side="left")
        self.current_hp_var = ctk.StringVar(value=str(sheet.hit_points.current))
        current_entry = ctk.CTkEntry(
            hp_row, width=45, height=24,
            textvariable=self.current_hp_var,
            justify="center"
        )
        current_entry.pack(side="left", padx=3)
        current_entry.bind("<FocusOut>", self._on_hp_field_change)
        current_entry.bind("<Return>", self._on_hp_field_change)
        
        ctk.CTkLabel(hp_row, text="/", font=ctk.CTkFont(size=12)).pack(side="left")
        
        # Max HP
        self.max_hp_var = ctk.StringVar(value=str(sheet.hit_points.maximum))
        max_entry = ctk.CTkEntry(
            hp_row, width=45, height=24,
            textvariable=self.max_hp_var,
            justify="center"
        )
        max_entry.pack(side="left", padx=3)
        max_entry.bind("<FocusOut>", self._on_hp_field_change)
        max_entry.bind("<Return>", self._on_hp_field_change)
        
        # Temp HP
        ctk.CTkLabel(hp_row, text="Temp:", font=ctk.CTkFont(size=10)).pack(side="left", padx=(10, 0))
        self.temp_hp_var = ctk.StringVar(value=str(sheet.hit_points.temporary))
        temp_entry = ctk.CTkEntry(
            hp_row, width=40, height=24,
            textvariable=self.temp_hp_var,
            justify="center"
        )
        temp_entry.pack(side="left", padx=3)
        temp_entry.bind("<FocusOut>", self._on_hp_field_change)
        temp_entry.bind("<Return>", self._on_hp_field_change)
        
        # Hit Dice section - separate counters for each die type
        dice_header = ctk.CTkFrame(hp_frame, fg_color="transparent")
        dice_header.pack(fill="x", padx=8, pady=(5, 2))
        ctk.CTkLabel(dice_header, text="Hit Dice:", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left")
        
        # Get hit dice from character classes
        class_levels = [(cl.character_class.value, cl.level) for cl in self.current_character.classes]
        hit_dice = get_hit_dice_for_classes(class_levels)
        
        # Initialize hit_dice_by_type if not set
        if not sheet.hit_points.hit_dice_by_type:
            sheet.hit_points.hit_dice_by_type = {die: count for die, count in hit_dice.items()}
        
        # Store for tracking
        self._hit_dice_vars = {}
        self._hit_dice_breakdown = hit_dice
        self._total_hit_dice = sum(hit_dice.values())
        
        # Create a row for each die type
        dice_container = ctk.CTkFrame(hp_frame, fg_color="transparent")
        dice_container.pack(fill="x", padx=8, pady=(0, 8))
        
        # Sort by die size for consistent display (d6, d8, d10, d12)
        die_order = {"d6": 1, "d8": 2, "d10": 3, "d12": 4}
        sorted_dice = sorted(hit_dice.items(), key=lambda x: die_order.get(x[0], 5))
        
        for die_type, total_count in sorted_dice:
            die_frame = ctk.CTkFrame(dice_container, fg_color=self.theme.get_current_color('bg_secondary'),
                                     corner_radius=6)
            die_frame.pack(side="left", padx=2, pady=2)
            
            inner = ctk.CTkFrame(die_frame, fg_color="transparent")
            inner.pack(padx=6, pady=4)
            
            # Die type label
            ctk.CTkLabel(inner, text=die_type, font=ctk.CTkFont(size=10, weight="bold")).pack()
            
            # Current/Max row
            value_row = ctk.CTkFrame(inner, fg_color="transparent")
            value_row.pack()
            
            # Get current remaining for this die type
            remaining = sheet.hit_points.hit_dice_by_type.get(die_type, total_count)
            
            die_var = ctk.StringVar(value=str(remaining))
            die_entry = ctk.CTkEntry(
                value_row, textvariable=die_var,
                width=28, height=22, justify="center",
                font=ctk.CTkFont(size=11)
            )
            die_entry.pack(side="left")
            die_entry.bind("<FocusOut>", lambda e, dt=die_type, v=die_var, m=total_count: self._on_hit_die_change(dt, v.get(), m))
            die_entry.bind("<Return>", lambda e, dt=die_type, v=die_var, m=total_count: self._on_hit_die_change(dt, v.get(), m))
            
            ctk.CTkLabel(value_row, text=f"/{total_count}", font=ctk.CTkFont(size=10)).pack(side="left")
            
            self._hit_dice_vars[die_type] = (die_var, total_count)
    
    def _on_hit_die_change(self, die_type: str, value_str: str, max_value: int):
        """Handle change to a specific hit die type."""
        if not self.current_sheet:
            return
        try:
            value = max(0, min(max_value, int(value_str or "0")))
            self.current_sheet.hit_points.hit_dice_by_type[die_type] = value
            # Update total remaining
            self.current_sheet.hit_points.hit_dice_remaining = sum(
                self.current_sheet.hit_points.hit_dice_by_type.values()
            )
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
        except ValueError:
            pass
    
    def _recalculate_hp(self):
        """Recalculate HP maximum based on class levels and CON modifier."""
        if not self.current_sheet or not self.current_character:
            return
        
        class_levels = [(cl.character_class.value, cl.level) for cl in self.current_character.classes]
        con_mod = self.current_sheet.ability_scores.modifier(AbilityScore.CONSTITUTION)
        
        new_max = calculate_hp_maximum(class_levels, con_mod, self.current_character.feats)
        self.max_hp_var.set(str(new_max))
        
        # Also update current if it exceeds new max
        current = int(self.current_hp_var.get() or "0")
        if current > new_max:
            self.current_hp_var.set(str(new_max))
        
        # Update hit dice total
        total_dice = sum(get_hit_dice_for_classes(class_levels).values())
        self.current_sheet.hit_points.hit_dice_total = total_dice
        
        self._on_hp_field_change()
        
        messagebox.showinfo("HP Recalculated", 
                           f"HP Maximum set to {new_max}\n(Based on class levels + CON modifier)")
    
    def _on_hp_field_change(self, event=None):
        """Handle HP field changes."""
        if self.current_sheet:
            try:
                self.current_sheet.hit_points.current = max(0, int(self.current_hp_var.get() or "0"))
                self.current_sheet.hit_points.maximum = max(1, int(self.max_hp_var.get() or "1"))
                self.current_sheet.hit_points.temporary = max(0, int(self.temp_hp_var.get() or "0"))
                self.current_sheet.hit_points.hit_dice_total = self._total_hit_dice
                
                # Update hit die type based on primary class
                if self.current_character.classes:
                    primary_class = self.current_character.classes[0].character_class.value
                    self.current_sheet.hit_points.hit_die_type = CLASS_HIT_DICE.get(primary_class, "d8")
                
                self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            except ValueError:
                pass
    
    def _on_long_rest(self):
        """Handle long rest - restore HP, hit dice, spell slots, and class features."""
        if not self.current_sheet or not self.current_character:
            return
        
        # Get settings for hit dice restoration
        settings = get_settings_manager().settings
        hit_dice_mode = settings.long_rest_hit_dice  # "all", "half", or "none"
        
        # 1. Restore HP to maximum
        self.current_sheet.hit_points.current = self.current_sheet.hit_points.maximum
        self.current_hp_var.set(str(self.current_sheet.hit_points.maximum))
        
        # 2. Restore hit dice based on settings
        hit_dice_message = ""
        if hit_dice_mode == "all":
            # Restore all hit dice to max
            for die_type, (var, max_value) in self._hit_dice_vars.items():
                self.current_sheet.hit_points.hit_dice_by_type[die_type] = max_value
                var.set(str(max_value))
            self.current_sheet.hit_points.hit_dice_remaining = sum(
                self.current_sheet.hit_points.hit_dice_by_type.values()
            )
            hit_dice_message = "• Hit dice fully restored"
        elif hit_dice_mode == "half":
            # Restore half hit dice (distributed across types)
            total_dice = self._total_hit_dice
            dice_to_restore = max(1, total_dice // 2)
            
            # Distribute restoration across die types proportionally
            for die_type, (var, max_value) in self._hit_dice_vars.items():
                current = self.current_sheet.hit_points.hit_dice_by_type.get(die_type, 0)
                # Restore proportionally based on this die type's share
                type_restore = max(1, dice_to_restore * max_value // total_dice) if total_dice > 0 else 1
                new_value = min(max_value, current + type_restore)
                self.current_sheet.hit_points.hit_dice_by_type[die_type] = new_value
                var.set(str(new_value))
            
            self.current_sheet.hit_points.hit_dice_remaining = sum(
                self.current_sheet.hit_points.hit_dice_by_type.values()
            )
            hit_dice_message = "• Hit dice partially restored (half)"
        else:  # "none"
            hit_dice_message = "• Hit dice not restored"
        
        # 3. Reset death saves
        self.current_sheet.death_saves.successes = 0
        self.current_sheet.death_saves.failures = 0
        if hasattr(self, 'death_widget'):
            self.death_widget.set_values(self.current_sheet.death_saves, self.current_sheet.inspiration)
        
        # 4. Restore all class feature uses to max
        if hasattr(self, '_feature_use_widgets'):
            for key, (var, max_value) in self._feature_use_widgets.items():
                var.set(str(max_value))
                self.current_sheet.class_feature_uses[key] = max_value
        
        # 5. Restore spell slots and mystic arcanum via character
        if self.current_character:
            # Reset spell slots to max
            from spell_slots import get_max_spell_slots
            class_levels = [(cl.character_class, cl.level) for cl in self.current_character.classes]
            max_slots = get_max_spell_slots(class_levels)
            self.current_character.current_slots = dict(max_slots)
            
            # Reset warlock pact magic slots
            warlock_level = sum(cl.level for cl in self.current_character.classes 
                               if cl.character_class == CharacterClass.WARLOCK)
            if warlock_level > 0:
                warlock_slots = min(4, 1 + (warlock_level - 1) // 2)  # 1 at 1, 2 at 2, 3 at 11, 4 at 17
                if warlock_level >= 17:
                    warlock_slots = 4
                elif warlock_level >= 11:
                    warlock_slots = 3
                elif warlock_level >= 2:
                    warlock_slots = 2
                else:
                    warlock_slots = 1
                self.current_character.warlock_slots_current = warlock_slots
            
            # Clear mystic arcanum used
            self.current_character.mystic_arcanum_used = []
            
            # Save character changes
            self.character_manager.save_characters()
        
        # Save sheet changes
        self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
        
        # Refresh the spells tab if it's showing
        if hasattr(self, 'spell_detail_panel') and self._current_tab == "spells":
            self._create_spells_content()
        
        messagebox.showinfo("Long Rest", 
                           f"Long rest complete!\n\n"
                           f"• HP restored to maximum\n"
                           f"{hit_dice_message}\n"
                           f"• Death saves reset\n"
                           f"• Class features restored\n"
                           f"• Spell slots restored\n"
                           f"• Mystic Arcanum restored")
    
    def _create_attacks_section(self, parent, sheet: CharacterSheet):
        """Create the attacks section with name, attack bonus, damage columns."""
        self._create_section_header(parent, "ATTACKS")
        
        attacks_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        attacks_frame.pack(fill="both", expand=True, pady=3)
        
        # Header row
        header_row = ctk.CTkFrame(attacks_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=8, pady=(8, 2))
        
        ctk.CTkLabel(header_row, text="Name", font=ctk.CTkFont(size=9, weight="bold"), width=100).pack(side="left", padx=2)
        ctk.CTkLabel(header_row, text="Atk Bonus", font=ctk.CTkFont(size=9, weight="bold"), width=60).pack(side="left", padx=2)
        ctk.CTkLabel(header_row, text="Damage/Type", font=ctk.CTkFont(size=9, weight="bold"), width=100).pack(side="left", padx=2)
        
        # Initialize attacks if empty
        if not sheet.attacks or len(sheet.attacks) < 5:
            while len(sheet.attacks) < 5:
                sheet.attacks.append({"name": "", "attack_bonus": "", "damage": ""})
        
        self.attack_entries = []
        for i, attack in enumerate(sheet.attacks[:5]):  # Max 5 attacks
            row = ctk.CTkFrame(attacks_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)
            
            # Name entry
            name_var = ctk.StringVar(value=attack.get("name", ""))
            name_entry = ctk.CTkEntry(row, textvariable=name_var, width=100, height=24)
            name_entry.pack(side="left", padx=2)
            name_entry.bind("<FocusOut>", lambda e, idx=i, var=name_var: self._save_attack_field(idx, "name", var.get()))
            
            # Attack bonus entry
            bonus_var = ctk.StringVar(value=attack.get("attack_bonus", ""))
            bonus_entry = ctk.CTkEntry(row, textvariable=bonus_var, width=60, height=24, justify="center")
            bonus_entry.pack(side="left", padx=2)
            bonus_entry.bind("<FocusOut>", lambda e, idx=i, var=bonus_var: self._save_attack_field(idx, "attack_bonus", var.get()))
            
            # Damage entry
            damage_var = ctk.StringVar(value=attack.get("damage", ""))
            damage_entry = ctk.CTkEntry(row, textvariable=damage_var, width=100, height=24)
            damage_entry.pack(side="left", padx=2)
            damage_entry.bind("<FocusOut>", lambda e, idx=i, var=damage_var: self._save_attack_field(idx, "damage", var.get()))
            
            self.attack_entries.append({"name": name_var, "bonus": bonus_var, "damage": damage_var})
    
    def _save_attack_field(self, index: int, field: str, value: str):
        """Save an attack field."""
        if self.current_sheet and index < len(self.current_sheet.attacks):
            self.current_sheet.attacks[index][field] = value
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    # ===== Class Feature Calculation Functions =====
    
    def _get_barbarian_features(self, level: int) -> dict:
        """Get barbarian rage uses and damage bonus for a given level."""
        # Rage uses: lvl 1-2: 2, lvl 3-5: 3, lvl 6-11: 4, lvl 12-16: 5, lvl 17-20: 6
        if level >= 17:
            rages = 6
        elif level >= 12:
            rages = 5
        elif level >= 6:
            rages = 4
        elif level >= 3:
            rages = 3
        else:
            rages = 2
        
        # Rage damage: lvl 1-8: +2, lvl 9-15: +3, lvl 16-20: +4
        if level >= 16:
            damage = "+4"
        elif level >= 9:
            damage = "+3"
        else:
            damage = "+2"
        
        return {"rages": rages, "rage_damage": damage}
    
    def _get_bard_features(self, level: int, charisma_mod: int) -> dict:
        """Get bard bardic inspiration uses and die for a given level."""
        uses = max(1, charisma_mod)  # Minimum 1
        
        # Inspiration die: lvl 1-4: d6, lvl 5-9: d8, lvl 10-14: d10, lvl 15+: d12
        if level >= 15:
            die = "d12"
        elif level >= 10:
            die = "d10"
        elif level >= 5:
            die = "d8"
        else:
            die = "d6"
        
        return {"uses": uses, "die": die}
    
    def _get_cleric_features(self, level: int) -> dict:
        """Get cleric channel divinity uses for a given level."""
        # Channel Divinity: lvl 1: 0, lvl 2-5: 1, lvl 6-17: 2, lvl 18+: 3
        if level >= 18:
            uses = 3
        elif level >= 6:
            uses = 2
        elif level >= 2:
            uses = 1
        else:
            uses = 0
        
        return {"channel_divinity": uses}
    
    def _get_druid_features(self, level: int, subclass_name: str = "") -> dict:
        """Get druid wild shape uses and max CR for a given level."""
        # Wild Shape uses: lvl 1: 0, lvl 2-5: 2, lvl 6-16: 2, lvl 17+: 4 (infinite at 20)
        if level >= 20:
            uses = "∞"
        elif level >= 17:
            uses = 4
        elif level >= 2:
            uses = 2
        else:
            uses = 0
        
        # Circle of the Moon: Max CR = Druid level / 3 (round down)
        if subclass_name == "Circle of the Moon" and level >= 3:
            moon_cr = level // 3
            max_cr = str(moon_cr)
        # Standard Druid: Max CR: lvl 2: 1/4, lvl 4: 1/2, lvl 8+: 1
        elif level >= 8:
            max_cr = "1"
        elif level >= 4:
            max_cr = "1/2"
        elif level >= 2:
            max_cr = "1/4"
        else:
            max_cr = "—"
        
        return {"wild_shape_uses": uses, "max_cr": max_cr}
    
    def _get_fighter_features(self, level: int) -> dict:
        """Get fighter second wind, action surge, and indomitable uses."""
        # Second Wind: lvl 1: 2, lvl 4: 3, lvl 10: 4
        if level >= 10:
            second_wind = 4
        elif level >= 4:
            second_wind = 3
        else:
            second_wind = 2
        
        # Action Surge: lvl 2: 1, lvl 17: 2
        if level >= 17:
            action_surge = 2
        elif level >= 2:
            action_surge = 1
        else:
            action_surge = 0
        
        # Indomitable: lvl 9: 1, lvl 13: 2, lvl 17: 3
        if level >= 17:
            indomitable = 3
        elif level >= 13:
            indomitable = 2
        elif level >= 9:
            indomitable = 1
        else:
            indomitable = 0
        
        return {"second_wind": second_wind, "action_surge": action_surge, "indomitable": indomitable}
    
    def _get_monk_features(self, level: int) -> dict:
        """Get monk focus points and martial arts die."""
        # Focus Points: starts at 2 at level 2, equals monk level
        if level >= 2:
            focus_points = level
        else:
            focus_points = 0
        
        # Martial Arts die: lvl 1: d6, lvl 5: d8, lvl 11: d10, lvl 17: d12
        if level >= 17:
            die = "d12"
        elif level >= 11:
            die = "d10"
        elif level >= 5:
            die = "d8"
        else:
            die = "d6"
        
        return {"focus_points": focus_points, "martial_arts_die": die}
    
    def _get_paladin_features(self, level: int) -> dict:
        """Get paladin channel divinity uses and lay on hands pool."""
        # Channel Divinity: lvl 3+: 2
        if level >= 3:
            channel_divinity = 2
        else:
            channel_divinity = 0
        
        # Lay on Hands: 5 × paladin level
        lay_on_hands = 5 * level
        
        return {"channel_divinity": channel_divinity, "lay_on_hands": lay_on_hands}
    
    def _get_ranger_features(self, level: int) -> dict:
        """Get ranger favored enemy uses."""
        # Uses: starts at 2, increases at prof bonus increase levels (5, 9, 13, 17)
        if level >= 17:
            uses = 6
        elif level >= 13:
            uses = 5
        elif level >= 9:
            uses = 4
        elif level >= 5:
            uses = 3
        else:
            uses = 2
        
        return {"favored_enemy_uses": uses}
    
    def _get_rogue_features(self, level: int) -> dict:
        """Get rogue sneak attack damage."""
        # Sneak Attack: 1d6 at level 1, +1d6 every odd level
        dice = (level + 1) // 2
        
        return {"sneak_attack": f"{dice}d6"}
    
    def _get_sorcerer_features(self, level: int) -> dict:
        """Get sorcerer sorcery points."""
        # Sorcery Points: starts at 2 at level 2, equals sorcerer level
        if level >= 2:
            points = level
        else:
            points = 0
        
        return {"sorcery_points": points}
    
    def _get_warlock_features(self, level: int) -> dict:
        """Get warlock eldritch invocations known."""
        # Invocations: 1@1, 3@2, 5@5, 6@7, 7@9, 8@12, 9@15, 10@18
        if level >= 18:
            invocations = 10
        elif level >= 15:
            invocations = 9
        elif level >= 12:
            invocations = 8
        elif level >= 9:
            invocations = 7
        elif level >= 7:
            invocations = 6
        elif level >= 5:
            invocations = 5
        elif level >= 2:
            invocations = 3
        else:
            invocations = 1
        
        return {"invocations": invocations}
    
    def _get_wizard_features(self, level: int) -> dict:
        """Get wizard arcane recovery spell slot levels."""
        # Arcane Recovery: half wizard level, rounded up
        import math
        recovery = math.ceil(level / 2)
        
        return {"arcane_recovery": recovery}
    
    def _get_artificer_features(self, level: int) -> dict:
        """Get artificer plans known and magic items created."""
        # Plans Known: follows the Artificer Features table
        # Level 2: 4, Level 6: 5, Level 10: 6, Level 14: 7, Level 18: 8
        if level < 2:
            plans_known = 0
        elif level < 6:
            plans_known = 4
        elif level < 10:
            plans_known = 5
        elif level < 14:
            plans_known = 6
        elif level < 18:
            plans_known = 7
        else:
            plans_known = 8
        
        # Magic Items created at end of Long Rest
        # Level 2: 2, Level 6: 3, Level 10: 4, Level 14: 5, Level 18: 6
        if level < 2:
            magic_items = 0
        elif level < 6:
            magic_items = 2
        elif level < 10:
            magic_items = 3
        elif level < 14:
            magic_items = 4
        elif level < 18:
            magic_items = 5
        else:
            magic_items = 6
        
        # Attunement slots: Base 3, +1 at 10 (Magic Item Adept), +1 at 14 (Advanced Artifice), +1 at 18 (Magic Item Master)
        attunement_slots = 3
        if level >= 10:
            attunement_slots = 4
        if level >= 14:
            attunement_slots = 5
        if level >= 18:
            attunement_slots = 6
        
        return {"plans_known": plans_known, "magic_items": magic_items, "attunement_slots": attunement_slots}
    
    def _create_class_features_section(self, parent, sheet: CharacterSheet):
        """Create the class-specific features section beneath combat."""
        if not self.current_character or not self.current_character.classes:
            return
        
        # Don't show for Custom class alone
        non_custom_classes = [cl for cl in self.current_character.classes 
                             if cl.character_class != CharacterClass.CUSTOM]
        if not non_custom_classes:
            return
        
        self._create_section_header(parent, "CLASS FEATURES")
        
        features_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        features_frame.pack(fill="x", pady=3)
        
        # Store feature entry widgets for long rest reset
        self._feature_use_widgets = {}
        
        # Create widget for each class (multiclass shows multiple)
        for class_level in non_custom_classes:
            char_class = class_level.character_class
            level = class_level.level
            subclass = class_level.subclass
            
            self._create_single_class_feature_widget(features_frame, char_class, level, sheet, subclass)
    
    def _create_single_class_feature_widget(self, parent, char_class: CharacterClass, level: int, sheet: CharacterSheet, subclass_name: str = ""):
        """Create feature tracking widget for a single class."""
        class_frame = ctk.CTkFrame(parent, fg_color="transparent")
        class_frame.pack(fill="x", padx=8, pady=6)
        
        # Class name header (include subclass if set)
        header_text = f"{char_class.value} {level}"
        if subclass_name:
            header_text += f" ({subclass_name})"
        ctk.CTkLabel(
            class_frame, text=header_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.theme.get_current_color('accent_primary')
        ).pack(anchor="w", pady=(0, 4))
        
        # Stats container - use grid for wrapping when many features
        stats_row = ctk.CTkFrame(class_frame, fg_color="transparent")
        stats_row.pack(fill="x", pady=2)
        
        # Track column position for grid layout
        self._feature_col = 0
        self._feature_row = 0
        self._max_cols = 3  # Wrap after 3 items
        
        if char_class == CharacterClass.BARBARIAN:
            features = self._get_barbarian_features(level)
            self._create_feature_use_stat(stats_row, char_class, "Rages", features["rages"], sheet)
            self._create_feature_display_stat(stats_row, "Rage Dmg", features["rage_damage"])
        
        elif char_class == CharacterClass.BARD:
            cha_mod = sheet.ability_scores.modifier(AbilityScore.CHARISMA)
            features = self._get_bard_features(level, cha_mod)
            self._create_feature_use_stat(stats_row, char_class, "Inspiration", features["uses"], sheet)
            self._create_feature_display_stat(stats_row, "Die", features["die"])
        
        elif char_class == CharacterClass.CLERIC:
            features = self._get_cleric_features(level)
            if features["channel_divinity"] > 0:
                self._create_feature_use_stat(stats_row, char_class, "Channel Divinity", features["channel_divinity"], sheet)
        
        elif char_class == CharacterClass.DRUID:
            features = self._get_druid_features(level, subclass_name)
            if features["wild_shape_uses"] != 0:
                if features["wild_shape_uses"] == "∞":
                    self._create_feature_display_stat(stats_row, "Wild Shape", "∞")
                else:
                    self._create_feature_use_stat(stats_row, char_class, "Wild Shape", features["wild_shape_uses"], sheet)
            self._create_feature_display_stat(stats_row, "Max CR", features["max_cr"])
        
        elif char_class == CharacterClass.FIGHTER:
            features = self._get_fighter_features(level)
            self._create_feature_use_stat(stats_row, char_class, "Second Wind", features["second_wind"], sheet)
            if features["action_surge"] > 0:
                self._create_feature_use_stat(stats_row, char_class, "Action Surge", features["action_surge"], sheet)
            if features["indomitable"] > 0:
                self._create_feature_use_stat(stats_row, char_class, "Indomitable", features["indomitable"], sheet)
        
        elif char_class == CharacterClass.MONK:
            features = self._get_monk_features(level)
            if features["focus_points"] > 0:
                self._create_feature_use_stat(stats_row, char_class, "Focus Points", features["focus_points"], sheet)
            self._create_feature_display_stat(stats_row, "Martial Arts", features["martial_arts_die"])
        
        elif char_class == CharacterClass.PALADIN:
            features = self._get_paladin_features(level)
            if features["channel_divinity"] > 0:
                self._create_feature_use_stat(stats_row, char_class, "Channel Divinity", features["channel_divinity"], sheet)
            self._create_feature_use_stat(stats_row, char_class, "Lay on Hands", features["lay_on_hands"], sheet, suffix=" HP")
        
        elif char_class == CharacterClass.RANGER:
            features = self._get_ranger_features(level)
            self._create_feature_use_stat(stats_row, char_class, "Favored Enemy", features["favored_enemy_uses"], sheet)
        
        elif char_class == CharacterClass.ROGUE:
            features = self._get_rogue_features(level)
            self._create_feature_display_stat(stats_row, "Sneak Attack", features["sneak_attack"])
        
        elif char_class == CharacterClass.SORCERER:
            features = self._get_sorcerer_features(level)
            if features["sorcery_points"] > 0:
                self._create_feature_use_stat(stats_row, char_class, "Sorcery Points", features["sorcery_points"], sheet)
        
        elif char_class == CharacterClass.WARLOCK:
            features = self._get_warlock_features(level)
            self._create_feature_display_stat(stats_row, "Invocations", str(features["invocations"]))
        
        elif char_class == CharacterClass.WIZARD:
            features = self._get_wizard_features(level)
            self._create_feature_use_stat(stats_row, char_class, "Arcane Recovery", features["arcane_recovery"], sheet, suffix=" lvls")
        
        elif char_class == CharacterClass.ARTIFICER:
            features = self._get_artificer_features(level)
            self._create_feature_display_stat(stats_row, "Plans", str(features["plans_known"]))
            self._create_feature_display_stat(stats_row, "Items", str(features["magic_items"]))
            # Flash of Genius at level 7+ (INT modifier uses, minimum 1)
            if level >= 7:
                int_mod = max(1, sheet.ability_scores.modifier(AbilityScore.INTELLIGENCE))
                self._create_feature_use_stat(stats_row, char_class, "Flash of Genius", int_mod, sheet)
        
        # Add trackable features from class definition (like Flash of Genius for Artificer)
        self._add_definition_trackable_features(stats_row, char_class, level, sheet, subclass_name)
    
    def _add_definition_trackable_features(self, parent, char_class: CharacterClass, level: int, sheet: CharacterSheet, subclass_name: str = ""):
        """Add trackable features from class and subclass definitions.
        
        Note: Features that are already handled in the hardcoded class sections
        should be skipped here to avoid duplication.
        """
        class_manager = get_class_manager()
        class_def = class_manager.get_class(char_class.value)
        
        if not class_def:
            return
        
        # Features that are handled in hardcoded sections - skip to avoid duplication
        # This includes all features that use ability modifiers or have special logic
        hardcoded_features = {
            # Artificer
            "Flash of Genius", "Tinker's Magic",
            # Barbarian
            "Rages", "Rage",
            # Bard
            "Bardic Inspiration", "Inspiration",
            # Cleric
            "Channel Divinity",
            # Druid
            "Wild Shape",
            # Fighter
            "Second Wind", "Action Surge", "Indomitable",
            # Monk
            "Ki Points", "Focus Points",
            # Paladin
            "Lay on Hands",
            # Ranger
            "Favored Enemy",
            # Sorcerer
            "Sorcery Points",
            # Wizard
            "Arcane Recovery",
        }
        
        # Get trackable features from class definition (skip hardcoded ones)
        for feature in class_def.trackable_features:
            if feature.title in hardcoded_features:
                continue
            if feature.has_uses:
                # Check if level qualifies (based on level_scaling)
                min_level = min(feature.level_scaling.keys()) if feature.level_scaling else 1
                if level >= min_level:
                    max_uses = feature.get_max_uses_at_level(level)
                    if max_uses > 0:
                        self._create_feature_use_stat(parent, char_class, feature.title, max_uses, sheet)
        
        # Get trackable features from subclass definition
        if subclass_name:
            subclass_def = None
            for sc in class_def.subclasses:
                if sc.name == subclass_name:
                    subclass_def = sc
                    break
            
            if subclass_def and hasattr(subclass_def, 'trackable_features'):
                for feature in subclass_def.trackable_features:
                    if feature.has_uses:
                        # Check if level qualifies (based on level_scaling)
                        min_level = min(feature.level_scaling.keys()) if feature.level_scaling else 1
                        if level >= min_level:
                            max_uses = feature.get_max_uses_at_level(level)
                            if max_uses > 0:
                                self._create_feature_use_stat(parent, char_class, feature.title, max_uses, sheet)
    
    def _create_feature_use_stat(self, parent, char_class: CharacterClass, label: str, max_value: int, sheet: CharacterSheet, suffix: str = ""):
        """Create a feature stat with editable current/max values."""
        key = f"{char_class.value}:{label}"
        
        # Get current value from sheet, default to max
        current = sheet.class_feature_uses.get(key, max_value)
        
        frame = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_tertiary'),
                            corner_radius=6)
        # Use grid for wrapping layout
        frame.grid(row=self._feature_row, column=self._feature_col, padx=3, pady=2, sticky="nsew")
        self._feature_col += 1
        if self._feature_col >= self._max_cols:
            self._feature_col = 0
            self._feature_row += 1
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=8, pady=5)
        
        # Label
        ctk.CTkLabel(
            inner, text=label,
            font=ctk.CTkFont(size=10),
            text_color=self.theme.get_text_secondary()
        ).pack(anchor="center")
        
        # Current/Max row
        value_row = ctk.CTkFrame(inner, fg_color="transparent")
        value_row.pack(anchor="center", pady=2)
        
        # Current value entry
        current_var = ctk.StringVar(value=str(current))
        current_entry = ctk.CTkEntry(
            value_row, textvariable=current_var,
            width=35, height=24, justify="center",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        current_entry.pack(side="left")
        current_entry.bind("<FocusOut>", lambda e, k=key, v=current_var, m=max_value: self._save_feature_use(k, v.get(), m))
        
        # Store widget reference for long rest
        self._feature_use_widgets[key] = (current_var, max_value)
        
        # Slash and max
        max_text = f"/ {max_value}{suffix}"
        ctk.CTkLabel(
            value_row, text=max_text,
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=(2, 0))
    
    def _create_feature_display_stat(self, parent, label: str, value: str):
        """Create a display-only feature stat (no uses to track)."""
        frame = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_tertiary'),
                            corner_radius=6)
        # Use grid for wrapping layout
        frame.grid(row=self._feature_row, column=self._feature_col, padx=3, pady=2, sticky="nsew")
        self._feature_col += 1
        if self._feature_col >= self._max_cols:
            self._feature_col = 0
            self._feature_row += 1
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=8, pady=5)
        
        ctk.CTkLabel(
            inner, text=label,
            font=ctk.CTkFont(size=10),
            text_color=self.theme.get_text_secondary()
        ).pack(anchor="center")
        
        ctk.CTkLabel(
            inner, text=value,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="center", pady=2)
    
    def _save_feature_use(self, key: str, value_str: str, max_value: int):
        """Save a feature use value."""
        if self.current_sheet:
            try:
                value = max(0, min(max_value, int(value_str or "0")))
                self.current_sheet.class_feature_uses[key] = value
                self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            except ValueError:
                pass

    def _create_features_section(self, parent, sheet: CharacterSheet):
        """Create the features and traits section with clickable class features."""
        self._create_section_header(parent, "FEATURES & TRAITS")
        
        # Store reference for targeted refresh
        self._features_parent = parent
        self._features_sheet = sheet
        
        features_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        features_frame.pack(fill="x", pady=3)
        
        # Store reference for refresh
        self._features_frame = features_frame
        
        self._populate_features_frame(features_frame, sheet)
    
    def _populate_features_frame(self, features_frame, sheet: CharacterSheet):
        """Populate the features frame with all feature subsections."""
        # Clear existing content
        for widget in features_frame.winfo_children():
            widget.destroy()
        
        # Get all features organized by category
        class_features, subclass_features = self._get_organized_features()
        
        has_class_features = len(class_features) > 0
        has_subclass_features = len(subclass_features) > 0
        has_other_features = bool(sheet.features_and_traits.strip())
        
        # Initialize collapsed sections
        self._collapsed_sections = getattr(self, '_collapsed_sections', {})
        
        # Class Features subsection (only if not empty)
        if has_class_features:
            class_features_frame = ctk.CTkFrame(features_frame, fg_color="transparent")
            class_features_frame.pack(fill="x", padx=8, pady=(8, 0))
            
            # Header with collapse button
            class_header = ctk.CTkFrame(class_features_frame, fg_color="transparent")
            class_header.pack(fill="x", pady=(0, 4))
            
            is_collapsed = self._collapsed_sections.get('class_features', False)
            
            collapse_btn = ctk.CTkButton(
                class_header,
                text="▼" if not is_collapsed else "▶",
                width=20, height=20,
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=10),
                command=lambda: self._toggle_section_collapse('class_features', None)
            )
            collapse_btn.pack(side="left", padx=(0, 4))
            
            header_label = ctk.CTkLabel(
                class_header, text="Class Features",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.theme.get_current_color('text_primary')
            )
            header_label.pack(side="left")
            
            # Bind right-click to show all hidden
            header_label.bind("<Button-3>", lambda e: self._show_all_features_menu(e, 'class'))
            
            # Content frame
            if not is_collapsed:
                self._populate_feature_buttons(class_features_frame, class_features, 'class')
        
        # Subclass Features subsection (only if not empty)
        if has_subclass_features:
            # Add separator if there are class features above
            if has_class_features:
                sep = ctk.CTkFrame(features_frame, fg_color=self.theme.get_current_color('bg_tertiary'), height=1)
                sep.pack(fill="x", padx=8, pady=8)
            
            subclass_features_frame = ctk.CTkFrame(features_frame, fg_color="transparent")
            subclass_features_frame.pack(fill="x", padx=8, pady=(8 if not has_class_features else 0, 0))
            
            # Header with collapse button
            subclass_header = ctk.CTkFrame(subclass_features_frame, fg_color="transparent")
            subclass_header.pack(fill="x", pady=(0, 4))
            
            is_collapsed = self._collapsed_sections.get('subclass_features', False)
            
            collapse_btn = ctk.CTkButton(
                subclass_header,
                text="▼" if not is_collapsed else "▶",
                width=20, height=20,
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=10),
                command=lambda: self._toggle_section_collapse('subclass_features', None)
            )
            collapse_btn.pack(side="left", padx=(0, 4))
            
            header_label = ctk.CTkLabel(
                subclass_header, text="Subclass Features",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.theme.get_current_color('text_primary')
            )
            header_label.pack(side="left")
            
            # Bind right-click to show all hidden
            header_label.bind("<Button-3>", lambda e: self._show_all_features_menu(e, 'subclass'))
            
            # Content frame
            if not is_collapsed:
                self._populate_feature_buttons(subclass_features_frame, subclass_features, 'subclass')
        
        # Lineage Traits subsection
        lineage_traits = self._get_lineage_traits()
        has_lineage_traits = len(lineage_traits) > 0
        
        if has_lineage_traits:
            # Add separator if there are features above
            if has_class_features or has_subclass_features:
                sep = ctk.CTkFrame(features_frame, fg_color=self.theme.get_current_color('bg_tertiary'), height=1)
                sep.pack(fill="x", padx=8, pady=8)
            
            lineage_frame = ctk.CTkFrame(features_frame, fg_color="transparent")
            lineage_frame.pack(fill="x", padx=8, pady=(8 if not has_class_features and not has_subclass_features else 0, 0))
            
            # Header with collapse/expand button
            lineage_header = ctk.CTkFrame(lineage_frame, fg_color="transparent")
            lineage_header.pack(fill="x", pady=(0, 4))
            
            lineage_name = self.current_character.lineage if self.current_character else ""
            is_collapsed = self._collapsed_sections.get('lineage_traits', False)
            
            collapse_btn = ctk.CTkButton(
                lineage_header,
                text="▼" if not is_collapsed else "▶",
                width=20, height=20,
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=10),
                command=lambda: self._toggle_section_collapse('lineage_traits', lineage_content)
            )
            collapse_btn.pack(side="left", padx=(0, 4))
            
            header_label = ctk.CTkLabel(
                lineage_header, text=f"Lineage Traits ({lineage_name})",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.theme.get_current_color('text_primary')
            )
            header_label.pack(side="left")
            
            # Bind right-click to show all hidden traits
            header_label.bind("<Button-3>", lambda e: self._show_all_traits_menu(e, 'lineage'))
            
            # Content frame
            lineage_content = ctk.CTkFrame(lineage_frame, fg_color="transparent")
            if not is_collapsed:
                lineage_content.pack(fill="x")
            
            self._populate_lineage_traits(lineage_content, lineage_traits)
        
        # Other Features subsection (only if not empty)
        if has_other_features or (not has_class_features and not has_subclass_features and not has_lineage_traits and not self._get_character_feats()):
            # Add separator if there are features above
            if has_class_features or has_subclass_features or has_lineage_traits:
                sep = ctk.CTkFrame(features_frame, fg_color=self.theme.get_current_color('bg_tertiary'), height=1)
                sep.pack(fill="x", padx=8, pady=8)
            
            other_features_frame = ctk.CTkFrame(features_frame, fg_color="transparent")
            other_features_frame.pack(fill="x", padx=8, pady=(8 if not has_class_features and not has_subclass_features and not has_lineage_traits else 0, 8))
            
            ctk.CTkLabel(
                other_features_frame, text="Other Features",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.theme.get_current_color('text_primary')
            ).pack(anchor="w", pady=(0, 4))
            
            self.features_text = ctk.CTkTextbox(
                other_features_frame, height=120,
                font=ctk.CTkFont(size=11)
            )
            self.features_text.pack(fill="x", pady=(0, 0))
            self.features_text.insert("1.0", sheet.features_and_traits)
            self._bind_autosave(self.features_text, "features_and_traits")
        else:
            # Still create the text box for future entry, just hidden with 0 height
            self.features_text = ctk.CTkTextbox(
                features_frame, height=0,
                font=ctk.CTkFont(size=11)
            )
            self.features_text.insert("1.0", sheet.features_and_traits)
        
        # Feats subsection
        character_feats = self._get_character_feats()
        has_feats = len(character_feats) > 0
        
        # Add separator if there are features above
        if has_class_features or has_subclass_features or has_lineage_traits or has_other_features:
            sep = ctk.CTkFrame(features_frame, fg_color=self.theme.get_current_color('bg_tertiary'), height=1)
            sep.pack(fill="x", padx=8, pady=8)
        
        feats_frame = ctk.CTkFrame(features_frame, fg_color="transparent")
        feats_frame.pack(fill="x", padx=8, pady=(0, 8))
        
        # Header row with title and add button
        feats_header = ctk.CTkFrame(feats_frame, fg_color="transparent")
        feats_header.pack(fill="x", pady=(0, 4))
        
        ctk.CTkLabel(
            feats_header, text="Feats",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.theme.get_current_color('text_primary')
        ).pack(side="left")
        
        # Add/Edit feats button
        ctk.CTkButton(
            feats_header, text="Edit",
            font=ctk.CTkFont(size=10),
            width=50, height=20,
            fg_color=self.theme.get_current_color('bg_tertiary'),
            hover_color=self.theme.get_current_color('accent'),
            text_color=self.theme.get_current_color('text_primary'),
            command=self._show_feat_editor
        ).pack(side="right")
        
        if has_feats:
            self._populate_feat_buttons(feats_frame, character_feats)
        else:
            ctk.CTkLabel(
                feats_frame, text="No feats selected",
                font=ctk.CTkFont(size=10),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(anchor="w")
    
    def _bind_autosave(self, textbox: ctk.CTkTextbox, field_name: str):
        """Bind autosave to a textbox with a small delay."""
        textbox.bind("<FocusOut>", lambda e: self._save_text_field(
            field_name, textbox.get("1.0", "end-1c")
        ))
    
    def _refresh_features_section(self):
        """Refresh only the features section without reloading the whole sheet."""
        if hasattr(self, '_features_frame') and self._features_frame and hasattr(self, '_features_sheet'):
            self._populate_features_frame(self._features_frame, self._features_sheet)
        else:
            # Fall back to full refresh if references not available
            self._show_character_sheet()
    
    def _get_organized_features(self):
        """Get class and subclass features organized into separate lists."""
        if not self.current_character:
            return [], []
        
        # Features to hide from the display (common across all classes)
        HIDDEN_FEATURES = {
            "Ability Score Improvement",
            "Epic Boon",
            # Subclass choice features (these just explain subclass selection, not actual features)
            "Paladin Subclass",
            "Druid Subclass",
            "Monk Subclass",
            "Bard College",
            "Ranger Subclass",
            "Rogue Subclass",
            "Sorcerer Subclass",
            "Wizard Subclass",
            "Warlock Subclass",
        }
        
        # Extra Attack feature hierarchy - later features supersede earlier ones
        EXTRA_ATTACK_FEATURES = {
            "Extra Attack": 1,
            "Two Extra Attacks": 2,
            "Three Extra Attacks": 3,
        }
        
        class_manager = get_class_manager()
        
        # Collect features separately
        class_features = []
        subclass_features = []
        
        for class_level in self.current_character.classes:
            class_name = class_level.character_class.value
            level = class_level.level
            subclass_name = class_level.subclass
            
            class_def = class_manager.get_class(class_name)
            if class_def:
                # Class features
                abilities = class_def.get_all_abilities_up_to_level(level)
                for ability in abilities:
                    if ability.title in HIDDEN_FEATURES:
                        continue
                    if ability.is_subclass_feature:
                        continue
                    class_features.append((class_name, ability))
                
                # Subclass features
                if subclass_name:
                    for subclass_def in class_def.subclasses:
                        if subclass_def.name == subclass_name:
                            sub_features = subclass_def.get_all_features_up_to_level(level)
                            for feature in sub_features:
                                if feature.title in HIDDEN_FEATURES:
                                    continue
                                from character_class import ClassAbility
                                ability = ClassAbility(
                                    title=feature.title,
                                    description=feature.description,
                                    is_subclass_feature=True,
                                    subclass_name=subclass_name,
                                    tables=feature.tables
                                )
                                subclass_features.append((f"{class_name} ({subclass_name})", ability))
                            break
        
        # Filter Extra Attack features - only show the highest tier
        highest_extra_attack_priority = 0
        highest_extra_attack_feature = None
        
        for class_name, ability in class_features:
            if ability.title in EXTRA_ATTACK_FEATURES:
                priority = EXTRA_ATTACK_FEATURES[ability.title]
                if priority > highest_extra_attack_priority:
                    highest_extra_attack_priority = priority
                    highest_extra_attack_feature = (class_name, ability)
        
        if highest_extra_attack_priority > 0:
            class_features = [
                (class_name, ability) for class_name, ability in class_features
                if ability.title not in EXTRA_ATTACK_FEATURES or (class_name, ability) == highest_extra_attack_feature
            ]
        
        return class_features, subclass_features
    
    def _populate_feature_buttons(self, parent, features, feature_type: str = "class"):
        """Populate feature buttons in a wrap layout.
        
        Args:
            parent: Parent widget
            features: List of (class_name, ability) tuples
            feature_type: Type for hiding ('class', 'subclass', etc.)
        """
        if not features:
            return
        
        features_container = ctk.CTkFrame(parent, fg_color="transparent")
        features_container.pack(fill="x")
        
        row_frame = None
        items_in_row = 0
        max_items_per_row = 3
        
        for class_name, ability in features:
            # Check if feature is hidden
            feature_id = f"{feature_type}:{ability.title}"
            if self.current_character and feature_id in self.current_character.hidden_features:
                continue
            
            if items_in_row == 0 or items_in_row >= max_items_per_row:
                row_frame = ctk.CTkFrame(features_container, fg_color="transparent")
                row_frame.pack(fill="x", pady=1)
                items_in_row = 0
            
            btn = ctk.CTkButton(
                row_frame,
                text=ability.title,
                font=ctk.CTkFont(size=10),
                fg_color=self.theme.get_current_color('bg_tertiary'),
                hover_color=self.theme.get_current_color('accent'),
                text_color=self.theme.get_current_color('text_primary'),
                corner_radius=4,
                height=24,
                command=lambda a=ability, c=class_name: self._show_feature_popup(a, c)
            )
            btn.pack(side="left", padx=2, pady=1)
            
            # Bind right-click to hide feature
            btn.bind("<Button-3>", lambda e, a=ability, ft=feature_type: self._show_feature_context_menu(e, a.title, ft))
            
            items_in_row += 1
    
    def _populate_class_features(self, parent):
        """Populate class features from class definitions (legacy method for compatibility)."""
        # Clear existing widgets
        for widget in parent.winfo_children():
            widget.destroy()
        
        class_features, subclass_features = self._get_organized_features()
        all_features = class_features + subclass_features
        
        if not all_features:
            ctk.CTkLabel(
                parent, text="No class features yet",
                font=ctk.CTkFont(size=10),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(anchor="w")
            return
        
        self._populate_feature_buttons(parent, all_features)
    
    def _show_feature_popup(self, ability: ClassAbility, class_name: str):
        """Show a popup with the full feature description."""
        popup = FeaturePopupDialog(self, ability, class_name)
        popup.focus()
    
    def _get_lineage_traits(self):
        """Get the list of LineageTrait objects for the current character's lineage."""
        if not self.current_character or not self.current_character.lineage:
            return []
        
        from lineage import get_lineage_manager
        lineage_manager = get_lineage_manager()
        lineage = lineage_manager.get_lineage(self.current_character.lineage)
        
        if lineage:
            return lineage.traits
        return []
    
    def _populate_lineage_traits(self, parent, traits):
        """Populate lineage trait buttons."""
        if not traits:
            return
        
        traits_container = ctk.CTkFrame(parent, fg_color="transparent")
        traits_container.pack(fill="x")
        
        row_frame = None
        items_in_row = 0
        max_items_per_row = 3
        
        for trait in traits:
            # Check if trait is hidden
            trait_id = f"lineage:{trait.name}"
            if self.current_character and trait_id in self.current_character.hidden_features:
                continue
            
            if items_in_row == 0 or items_in_row >= max_items_per_row:
                row_frame = ctk.CTkFrame(traits_container, fg_color="transparent")
                row_frame.pack(fill="x", pady=1)
                items_in_row = 0
            
            btn = ctk.CTkButton(
                row_frame,
                text=trait.name,
                font=ctk.CTkFont(size=10),
                fg_color=self.theme.get_current_color('accent_primary'),
                hover_color=self.theme.get_current_color('accent'),
                text_color=self.theme.get_current_color('text_primary'),
                corner_radius=4,
                height=24,
                command=lambda t=trait: self._show_lineage_trait_popup(t)
            )
            btn.pack(side="left", padx=2, pady=1)
            
            # Bind right-click to hide trait
            btn.bind("<Button-3>", lambda e, t=trait: self._show_trait_context_menu(e, t, 'lineage'))
            
            items_in_row += 1
    
    def _show_lineage_trait_popup(self, trait):
        """Show a popup with the full lineage trait description."""
        popup = LineageTraitPopupDialog(self, trait)
        popup.focus()
    
    def _refresh_lineage_traits_section(self):
        """Refresh the features section to update lineage traits display."""
        self._refresh_features_section()
    
    def _toggle_section_collapse(self, section_key: str, content_frame):
        """Toggle collapse state of a section."""
        if not hasattr(self, '_collapsed_sections'):
            self._collapsed_sections = {}
        
        is_collapsed = self._collapsed_sections.get(section_key, False)
        self._collapsed_sections[section_key] = not is_collapsed
        
        # Refresh only the features section
        self._refresh_features_section()
    
    def _show_trait_context_menu(self, event, trait, trait_type: str):
        """Show context menu for hiding a trait."""
        # Use tkinter Menu for more reliable context menu behavior
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        
        menu.configure(
            bg=self.theme.get_current_color('bg_secondary'),
            fg=self.theme.get_current_color('text_primary'),
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=self.theme.get_current_color('text_primary')
        )
        
        def hide_trait():
            if self.current_character:
                trait_id = f"{trait_type}:{trait.name}"
                if trait_id not in self.current_character.hidden_features:
                    self.current_character.hidden_features.append(trait_id)
                    self.character_manager.save_characters()
                    self._refresh_features_section()
        
        menu.add_command(label="Hide Trait", command=hide_trait)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _show_all_traits_menu(self, event, trait_type: str):
        """Show context menu for showing all hidden traits of a type."""
        # Use tkinter Menu for more reliable context menu behavior
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        
        menu.configure(
            bg=self.theme.get_current_color('bg_secondary'),
            fg=self.theme.get_current_color('text_primary'),
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=self.theme.get_current_color('text_primary')
        )
        
        def show_all_traits():
            if self.current_character:
                # Remove all hidden features of this type
                prefix = f"{trait_type}:"
                self.current_character.hidden_features = [
                    f for f in self.current_character.hidden_features
                    if not f.startswith(prefix)
                ]
                self.character_manager.save_characters()
                
                # Also uncollapse the section
                if hasattr(self, '_collapsed_sections'):
                    section_key = f"{trait_type}_traits"
                    self._collapsed_sections[section_key] = False
                
                self._refresh_features_section()
        
        menu.add_command(label="Show All Hidden Traits", command=show_all_traits)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _show_feature_context_menu(self, event, feature_name: str, feature_type: str):
        """Show context menu for hiding a class/subclass feature."""
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        
        menu.configure(
            bg=self.theme.get_current_color('bg_secondary'),
            fg=self.theme.get_current_color('text_primary'),
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=self.theme.get_current_color('text_primary')
        )
        
        def hide_feature():
            if self.current_character:
                feature_id = f"{feature_type}:{feature_name}"
                if feature_id not in self.current_character.hidden_features:
                    self.current_character.hidden_features.append(feature_id)
                    self.character_manager.save_characters()
                    self._refresh_features_section()
        
        menu.add_command(label="Hide Feature", command=hide_feature)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def _show_all_features_menu(self, event, feature_type: str):
        """Show context menu for showing all hidden features of a type."""
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        
        menu.configure(
            bg=self.theme.get_current_color('bg_secondary'),
            fg=self.theme.get_current_color('text_primary'),
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=self.theme.get_current_color('text_primary')
        )
        
        def show_all_features():
            if self.current_character:
                # Remove all hidden features of this type
                prefix = f"{feature_type}:"
                self.current_character.hidden_features = [
                    f for f in self.current_character.hidden_features
                    if not f.startswith(prefix)
                ]
                self.character_manager.save_characters()
                
                # Also uncollapse the section
                if hasattr(self, '_collapsed_sections'):
                    section_key = f"{feature_type}_features"
                    self._collapsed_sections[section_key] = False
                
                self._refresh_features_section()
        
        menu.add_command(label="Show All Hidden Features", command=show_all_features)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _get_character_feats(self):
        """Get the list of Feat objects for the current character."""
        if not self.current_character or not self.current_character.feats:
            return []
        
        feat_manager = get_feat_manager()
        feats = []
        for feat_name in self.current_character.feats:
            feat = feat_manager.get_feat(feat_name)
            if feat:
                feats.append(feat)
        return feats
    
    def _populate_feat_buttons(self, parent, feats):
        """Populate feat buttons in a wrap layout."""
        if not feats:
            return
        
        feats_container = ctk.CTkFrame(parent, fg_color="transparent")
        feats_container.pack(fill="x")
        
        row_frame = None
        items_in_row = 0
        max_items_per_row = 3
        
        for feat in feats:
            if items_in_row == 0 or items_in_row >= max_items_per_row:
                row_frame = ctk.CTkFrame(feats_container, fg_color="transparent")
                row_frame.pack(fill="x", pady=1)
                items_in_row = 0
            
            # Determine button color based on feat type
            if feat.is_spellcasting:
                btn_color = self.theme.get_current_color('accent_primary')
            else:
                btn_color = self.theme.get_current_color('bg_tertiary')
            
            btn = ctk.CTkButton(
                row_frame,
                text=feat.name,
                font=ctk.CTkFont(size=10),
                fg_color=btn_color,
                hover_color=self.theme.get_current_color('accent'),
                text_color=self.theme.get_current_color('text_primary'),
                corner_radius=4,
                height=24,
                command=lambda f=feat: self._show_feat_popup(f)
            )
            btn.pack(side="left", padx=2, pady=1)
            items_in_row += 1
    
    def _show_feat_popup(self, feat):
        """Show a popup with the full feat description."""
        popup = FeatPopupDialog(self, feat)
        popup.focus()
    
    def _show_feat_editor(self):
        """Show dialog to add/remove feats from character."""
        if not self.current_character:
            return
        
        dialog = CharacterFeatEditorDialog(self, self.current_character)
        self.wait_window(dialog)
        
        if dialog.result is not None:
            # Update character feats
            self.current_character.feats = dialog.result
            # Save the character
            self.character_manager.update_character(self.current_character.name, self.current_character)
            self.character_manager.save_characters()
            # Refresh the view
            self.refresh()
            # Update spell tab visibility based on feats
            self._update_spell_tab_for_feats()
    
    def _update_spell_tab_for_feats(self):
        """Update spell tab visibility based on character's spellcasting feats."""
        if not self.current_character:
            return
        
        # Check if character has any spellcasting feats
        has_spellcasting_feat = False
        feat_manager = get_feat_manager()
        for feat_name in self.current_character.feats:
            feat = feat_manager.get_feat(feat_name)
            if feat and feat.is_spellcasting:
                has_spellcasting_feat = True
                break
        
        # If has spellcasting feat, notify parent to show spells tab
        if has_spellcasting_feat and hasattr(self, 'on_spellcasting_feat_changed'):
            self.on_spellcasting_feat_changed(True)

    def _create_proficiencies_section(self, parent, sheet: CharacterSheet):
        """Create the other proficiencies & languages section."""
        self._create_section_header(parent, "OTHER PROFICIENCIES & LANGUAGES")
        
        prof_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        prof_frame.pack(fill="x", pady=3)
        
        self.proficiencies_text = ctk.CTkTextbox(
            prof_frame, height=80,
            font=ctk.CTkFont(size=11)
        )
        self.proficiencies_text.pack(fill="x", padx=8, pady=8)
        self.proficiencies_text.insert("1.0", sheet.other_proficiencies)
        self.proficiencies_text.bind("<FocusOut>", lambda e: self._save_text_field(
            "other_proficiencies", self.proficiencies_text.get("1.0", "end-1c")
        ))
    
    def _auto_fill_proficiencies(self):
        """Auto-fill proficiencies based on character classes."""
        if not self.current_character:
            return
        
        class_levels = [(cl.character_class.value, cl.level) for cl in self.current_character.classes]
        default_profs = get_default_proficiencies(class_levels)
        
        # Add Languages line
        if default_profs:
            default_profs += "\n\nLanguages: Common"
        else:
            default_profs = "Languages: Common"
        
        # Update the text
        self.proficiencies_text.delete("1.0", "end")
        self.proficiencies_text.insert("1.0", default_profs)
        self._save_text_field("other_proficiencies", default_profs)
    
    def _create_personality_section(self, parent, sheet: CharacterSheet):
        """Create the personality section (smaller, in middle column)."""
        self._create_section_header(parent, "PERSONALITY")
        
        personality_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        personality_frame.pack(fill="both", expand=True, pady=3)
        
        fields = [
            ("Personality Traits", "personality_traits", sheet.personality_traits),
            ("Ideals", "ideals", sheet.ideals),
            ("Bonds", "bonds", sheet.bonds),
            ("Flaws", "flaws", sheet.flaws)
        ]
        
        self.personality_texts = {}
        for label, field, value in fields:
            ctk.CTkLabel(
                personality_frame, text=label,
                font=ctk.CTkFont(size=9, weight="bold")
            ).pack(anchor="w", padx=8, pady=(5, 1))
            
            text = ctk.CTkTextbox(personality_frame, height=40, font=ctk.CTkFont(size=10))
            text.pack(fill="x", padx=8, pady=(0, 3))
            text.insert("1.0", value)
            text.bind("<FocusOut>", lambda e, f=field, t=text: self._save_text_field(
                f, t.get("1.0", "end-1c")
            ))
            self.personality_texts[field] = text
    
    def _create_notes_section(self, parent, sheet: CharacterSheet):
        """Create the notes section."""
        self._create_section_header(parent, "NOTES")
        
        notes_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        notes_frame.pack(fill="both", expand=True, pady=3)
        
        self.notes_text = ctk.CTkTextbox(
            notes_frame, height=100,
            font=ctk.CTkFont(size=11)
        )
        self.notes_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.notes_text.insert("1.0", sheet.notes)
        self.notes_text.bind("<FocusOut>", lambda e: self._save_text_field(
            "notes", self.notes_text.get("1.0", "end-1c")
        ))
    
    # ===== Save handlers =====
    
    def _save_field(self, field: str, value: str):
        """Save a string field."""
        if self._rebuilding_ui:
            return  # Don't save during UI rebuild
        if self.current_sheet:
            setattr(self.current_sheet, field, value)
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def _save_int_field(self, field: str, value: str):
        """Save an integer field."""
        if self._rebuilding_ui:
            return  # Don't save during UI rebuild
        if self.current_sheet:
            try:
                setattr(self.current_sheet, field, int(value or "0"))
                self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            except ValueError:
                pass
    
    def _save_text_field(self, field: str, value: str):
        """Save a text field."""
        self._save_field(field, value)
    
    def _on_ability_change(self, ability: AbilityScore, score: int):
        """Handle ability score change."""
        if self.current_sheet:
            self.current_sheet.ability_scores.set(ability, score)
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            self._update_derived_stats()
            
            # If CON changed and auto-calc is on, recalculate HP
            if ability == AbilityScore.CONSTITUTION:
                settings = get_settings_manager().settings
                if settings.auto_calculate_hp:
                    self._auto_update_hp()
            
            # Recalculate AC when any relevant stat changes
            # For unarmored defense, this could be DEX + CON, DEX + WIS, DEX + CHA, etc.
            settings = get_settings_manager().settings
            if settings.auto_calculate_ac:
                # Always recalculate if DEX changes (affects all AC)
                # Or if character has unarmored defense (any stat could affect AC)
                if ability == AbilityScore.DEXTERITY or self.current_sheet.unarmored_defense:
                    self._recalculate_ac()
    
    def _on_save_change(self, ability: AbilityScore, proficient: bool):
        """Handle saving throw proficiency change."""
        if self.current_sheet:
            self.current_sheet.saving_throws.set_proficiency(ability, proficient)
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            self._update_derived_stats()
    
    def _on_skill_change(self, skill: Skill, prof_level: int):
        """Handle skill proficiency change."""
        if self.current_sheet:
            self.current_sheet.skills.set(skill, prof_level)
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            self._update_derived_stats()
    
    def _on_hp_change(self, hp: HitPoints):
        """Handle HP change."""
        if self.current_sheet:
            self.current_sheet.hit_points = hp
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def _on_death_saves_change(self, death_saves: DeathSaves):
        """Handle death saves change."""
        if self.current_sheet:
            self.current_sheet.death_saves = death_saves
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def _on_inspiration_change(self, inspiration: bool):
        """Handle inspiration change."""
        if self.current_sheet:
            self.current_sheet.inspiration = inspiration
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def _on_proficiency_change(self, event=None):
        """Handle proficiency bonus change."""
        if self.current_sheet:
            try:
                self.current_sheet.proficiency_bonus = int(self.prof_var.get() or "2")
                self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
                self._update_derived_stats()
            except ValueError:
                pass
    
    def _update_primal_champion(self):
        """Check and apply/remove Primal Champion bonus for level 20 Barbarians."""
        if not self.current_sheet or not self.current_character:
            return
        
        # Check if character is a level 20 Barbarian
        has_primal_champion_feature = False
        for cl in self.current_character.classes:
            if cl.character_class.value == "Barbarian" and cl.level >= 20:
                has_primal_champion_feature = True
                break
        
        # Apply or remove bonus as needed
        if has_primal_champion_feature:
            if not self.current_sheet.has_primal_champion():
                self.current_sheet.apply_primal_champion()
                # Update ability score widgets to show new effective scores
                self._refresh_ability_score_widgets()
        else:
            if self.current_sheet.has_primal_champion():
                self.current_sheet.remove_primal_champion()
                # Update ability score widgets
                self._refresh_ability_score_widgets()
    
    def _update_body_and_mind(self):
        """Check and apply/remove Body and Mind bonus for level 20 Monks."""
        if not self.current_sheet or not self.current_character:
            return
        
        # Check if character is a level 20 Monk
        has_body_and_mind_feature = False
        for cl in self.current_character.classes:
            if cl.character_class.value == "Monk" and cl.level >= 20:
                has_body_and_mind_feature = True
                break
        
        # Apply or remove bonus as needed
        if has_body_and_mind_feature:
            if not self.current_sheet.has_body_and_mind():
                self.current_sheet.apply_body_and_mind()
                # Update ability score widgets to show new effective scores
                self._refresh_ability_score_widgets()
        else:
            if self.current_sheet.has_body_and_mind():
                self.current_sheet.remove_body_and_mind()
                # Update ability score widgets
                self._refresh_ability_score_widgets()
    
    def _update_slippery_mind(self, character, sheet: CharacterSheet, class_index: int, new_level: int):
        """Handle Slippery Mind (Rogue level 15) saving throw proficiencies.
        
        When a Rogue reaches level 15, they gain proficiency in Wisdom and Charisma saving throws.
        If they lose this feature (level drops below 15), the proficiencies are removed.
        """
        if class_index >= len(character.classes):
            return
        
        class_level = character.classes[class_index]
        if class_level.character_class.value != "Rogue":
            return
        
        # Check if character has Slippery Mind (level 15+)
        has_slippery_mind = new_level >= 15
        
        # Track whether we applied slippery mind saves using class_feature_uses dict
        # Value of 1 means we applied the saves, 0 means we removed them
        key = "Rogue:Slippery Mind Saves"
        previously_applied = sheet.class_feature_uses.get(key, 0) == 1
        
        if has_slippery_mind:
            # Apply WIS and CHA saving throw proficiencies if not already proficient
            changed = False
            if not sheet.saving_throws.is_proficient(AbilityScore.WISDOM):
                sheet.saving_throws.set_proficiency(AbilityScore.WISDOM, True)
                changed = True
            if not sheet.saving_throws.is_proficient(AbilityScore.CHARISMA):
                sheet.saving_throws.set_proficiency(AbilityScore.CHARISMA, True)
                changed = True
            
            # Mark that we applied slippery mind saves
            sheet.class_feature_uses[key] = 1
            
            if changed:
                self.sheet_manager.update_sheet(character.name, sheet)
                # Refresh the saving throws section if it exists
                if hasattr(self, 'save_widgets'):
                    for ability in [AbilityScore.WISDOM, AbilityScore.CHARISMA]:
                        if ability in self.save_widgets:
                            modifier = sheet.get_saving_throw_bonus(ability)
                            self.save_widgets[ability].set_proficiency(True)
                            self.save_widgets[ability].set_modifier(modifier)
        else:
            # Remove WIS and CHA saving throw proficiencies if we applied them
            if previously_applied:
                changed = False
                # Only remove if we were the ones who applied them
                if sheet.saving_throws.is_proficient(AbilityScore.WISDOM):
                    sheet.saving_throws.set_proficiency(AbilityScore.WISDOM, False)
                    changed = True
                if sheet.saving_throws.is_proficient(AbilityScore.CHARISMA):
                    sheet.saving_throws.set_proficiency(AbilityScore.CHARISMA, False)
                    changed = True
                
                sheet.class_feature_uses[key] = 0
                
                if changed:
                    self.sheet_manager.update_sheet(character.name, sheet)
                    # Refresh the saving throws section if it exists
                    if hasattr(self, 'save_widgets'):
                        for ability in [AbilityScore.WISDOM, AbilityScore.CHARISMA]:
                            if ability in self.save_widgets:
                                modifier = sheet.get_saving_throw_bonus(ability)
                                self.save_widgets[ability].set_proficiency(False)
                                self.save_widgets[ability].set_modifier(modifier)

    def _refresh_ability_score_widgets(self):
        """Refresh ability score widgets to show effective scores."""
        if not self.current_sheet or not hasattr(self, 'ability_widgets'):
            return
        
        for ability, widget in self.ability_widgets.items():
            # Get effective score (base + bonuses)
            effective_score = self.current_sheet.get_effective_ability_score(ability, max_score=25)
            widget.set_score(effective_score)
    
    def _update_derived_stats(self):
        """Update all derived statistics after a change."""
        if not self.current_sheet:
            return
        
        sheet = self.current_sheet
        
        # Update saving throw modifiers
        for ability, widget in self.save_widgets.items():
            modifier = sheet.get_saving_throw_bonus(ability)
            widget.update_modifier(modifier)
        
        # Update skill modifiers (with Jack of All Trades bonus if applicable)
        jack_bonus = self._get_jack_of_all_trades_bonus()
        for skill, widget in self.skill_widgets.items():
            modifier = sheet.get_skill_bonus(skill, jack_bonus)
            widget.update_modifier(modifier)
        
        # Update initiative
        init_mod = sheet.get_initiative()
        init_text = f"+{init_mod}" if init_mod >= 0 else str(init_mod)
        self.init_label.configure(text=init_text)
    
    def _auto_update_hp(self):
        """Automatically update HP when CON or level changes (no dialog)."""
        if not self.current_sheet or not self.current_character:
            return
        
        class_levels = [(cl.character_class.value, cl.level) for cl in self.current_character.classes]
        # Use effective CON modifier (includes bonuses like Primal Champion)
        con_mod = self.current_sheet.get_effective_ability_modifier(AbilityScore.CONSTITUTION, max_score=25)
        
        new_max = calculate_hp_maximum(class_levels, con_mod, self.current_character.feats)
        old_max = self.current_sheet.hit_points.maximum
        
        # Calculate current HP proportionally
        if old_max > 0:
            hp_ratio = self.current_sheet.hit_points.current / old_max
            new_current = max(1, min(new_max, int(new_max * hp_ratio)))
        else:
            new_current = new_max
        
        # Update the values
        self.current_sheet.hit_points.maximum = new_max
        self.current_sheet.hit_points.current = new_current
        
        # Update UI
        self.max_hp_var.set(str(new_max))
        self.current_hp_var.set(str(new_current))
        
        # Update hit dice total
        total_dice = sum(get_hit_dice_for_classes(class_levels).values())
        self.current_sheet.hit_points.hit_dice_total = total_dice
        self._total_hit_dice = total_dice
        
        self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def refresh(self):
        """Refresh the view."""
        self._refresh_character_list()
        if self.current_character:
            self._update_spell_tab_visibility()
            self._show_character_sheet()
    
    def select_character(self, character_name: str):
        """Select a character by name (for external navigation)."""
        self.char_var.set(character_name)
        self._on_character_selected(character_name)
    
    def _create_inventory_content(self):
        """Create the inventory tab content with equipment and magic items."""
        # Clear existing content
        for widget in self.inventory_content.winfo_children():
            widget.destroy()
        
        if not self.current_sheet:
            return
        
        # Equipment Section (no nested scrolling)
        self._create_inventory_equipment_section(self.inventory_content)
        
        # Magic Items Section  
        self._create_inventory_magic_items_section(self.inventory_content)
    
    def _create_inventory_equipment_section(self, parent):
        """Create the equipment section in inventory tab."""
        # Header
        header = ctk.CTkFrame(
            parent, 
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5, height=30
        )
        header.pack(fill="x", padx=10, pady=(10, 5))
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="EQUIPMENT",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white"
        ).pack(side="left", padx=10, pady=5)
        
        # Equipment frame
        equip_frame = ctk.CTkFrame(
            parent, fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        equip_frame.pack(fill="x", padx=10, pady=(0, 15))
        
        # Currency row
        currency_row = ctk.CTkFrame(equip_frame, fg_color="transparent")
        currency_row.pack(fill="x", padx=10, pady=8)
        
        currencies = [
            ("CP", "copper", self.current_sheet.copper),
            ("SP", "silver", self.current_sheet.silver),
            ("EP", "electrum", self.current_sheet.electrum),
            ("GP", "gold", self.current_sheet.gold),
            ("PP", "platinum", self.current_sheet.platinum)
        ]
        
        self.currency_vars = {}
        for abbr, field, value in currencies:
            frame = ctk.CTkFrame(currency_row, fg_color="transparent")
            frame.pack(side="left", expand=True)
            ctk.CTkLabel(frame, text=abbr, font=ctk.CTkFont(size=10, weight="bold")).pack()
            var = ctk.StringVar(value=str(value))
            self.currency_vars[field] = var
            entry = ctk.CTkEntry(frame, width=55, height=26, textvariable=var, justify="center")
            entry.pack()
            entry.bind("<FocusOut>", lambda e, f=field, v=var: self._save_int_field(f, v.get()))
        
        # Equipment text
        ctk.CTkLabel(
            equip_frame, text="Equipment List:",
            font=ctk.CTkFont(size=10, weight="bold")
        ).pack(anchor="w", padx=10, pady=(5, 2))
        
        self.equipment_text = ctk.CTkTextbox(
            equip_frame, height=120,
            font=ctk.CTkFont(size=11)
        )
        self.equipment_text.pack(fill="x", padx=10, pady=(0, 10))
        self.equipment_text.insert("1.0", self.current_sheet.equipment)
        self.equipment_text.bind("<FocusOut>", lambda e: self._save_text_field(
            "equipment", self.equipment_text.get("1.0", "end-1c")
        ))
    
    def _create_inventory_magic_items_section(self, parent):
        """Create the magic items section in inventory tab."""
        # Header
        header = ctk.CTkFrame(
            parent, 
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5, height=30
        )
        header.pack(fill="x", padx=10, pady=(0, 5))
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, text="MAGIC ITEMS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white"
        ).pack(side="left", padx=10, pady=5)
        
        # Add item button
        add_btn = ctk.CTkButton(
            header, text="+ Add Item", width=80, height=24,
            fg_color="white", text_color=self.theme.get_current_color('accent_primary'),
            hover_color="#e0e0e0",
            command=self._add_magic_item
        )
        add_btn.pack(side="right", padx=10, pady=3)
        
        # Attunement info
        attunement_count = sum(1 for item in self.current_sheet.magic_items if item.get("attuned", False))
        attunement_limit = self._get_attunement_limit()
        info_label = ctk.CTkLabel(
            parent,
            text=f"Attuned: {attunement_count}/{attunement_limit}",
            font=ctk.CTkFont(size=11),
            text_color=self.theme.get_text_secondary()
        )
        info_label.pack(anchor="w", padx=10, pady=(0, 5))
        self._attunement_label = info_label
        
        # Items container frame
        items_frame = ctk.CTkFrame(parent, fg_color="transparent")
        items_frame.pack(fill="x")
        
        # Initialize magic items if empty
        if not self.current_sheet.magic_items:
            self.current_sheet.magic_items = []
        
        self._magic_item_widgets = []
        self._magic_items_container = items_frame
        for i, item in enumerate(self.current_sheet.magic_items):
            self._create_magic_item_row(items_frame, i, item)
    
    def _create_magic_item_row(self, parent, index: int, item: dict):
        """Create a row for a magic item."""
        row = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        row.pack(fill="x", pady=3, padx=5)
        
        content = ctk.CTkFrame(row, fg_color="transparent")
        content.pack(fill="x", padx=10, pady=8)
        
        # Item name
        name_var = ctk.StringVar(value=item.get("name", ""))
        name_entry = ctk.CTkEntry(
            content, textvariable=name_var,
            width=200, height=26,
            font=ctk.CTkFont(size=12, weight="bold"),
            placeholder_text="Item Name"
        )
        name_entry.pack(side="left", padx=(0, 10))
        name_entry.bind("<FocusOut>", lambda e, idx=index, var=name_var: self._save_magic_item_field(idx, "name", var.get()))
        
        # Description
        desc_var = ctk.StringVar(value=item.get("description", ""))
        desc_entry = ctk.CTkEntry(
            content, textvariable=desc_var,
            width=300, height=26,
            placeholder_text="Description"
        )
        desc_entry.pack(side="left", padx=(0, 10), fill="x", expand=True)
        desc_entry.bind("<FocusOut>", lambda e, idx=index, var=desc_var: self._save_magic_item_field(idx, "description", var.get()))
        
        # Attuned checkbox
        attuned_var = ctk.BooleanVar(value=item.get("attuned", False))
        attuned_check = ctk.CTkCheckBox(
            content, text="Attuned",
            variable=attuned_var,
            command=lambda idx=index, var=attuned_var: self._save_magic_item_attuned(idx, var.get())
        )
        attuned_check.pack(side="left", padx=10)
        
        # Delete button
        del_btn = ctk.CTkButton(
            content, text="✕", width=26, height=26,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=lambda idx=index: self._delete_magic_item(idx)
        )
        del_btn.pack(side="right")
        
        self._magic_item_widgets.append((row, name_var, desc_var, attuned_var))
    
    def _add_magic_item(self):
        """Add a new magic item."""
        if not self.current_sheet:
            return
        
        self.current_sheet.magic_items.append({"name": "", "description": "", "attuned": False})
        self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
        self._create_inventory_content()
    
    def _save_magic_item_field(self, index: int, field: str, value: str):
        """Save a magic item field."""
        if self.current_sheet and index < len(self.current_sheet.magic_items):
            self.current_sheet.magic_items[index][field] = value
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
    
    def _save_magic_item_attuned(self, index: int, attuned: bool):
        """Save magic item attunement status."""
        if self.current_sheet and index < len(self.current_sheet.magic_items):
            # Check if at attunement limit
            attunement_limit = self._get_attunement_limit()
            if attuned:
                current_attuned = sum(1 for i, item in enumerate(self.current_sheet.magic_items) 
                                     if item.get("attuned", False) and i != index)
                if current_attuned >= attunement_limit:
                    messagebox.showwarning("Attunement Limit", f"You can only attune to {attunement_limit} magic items at a time.")
                    # Reset the checkbox
                    self._create_inventory_content()
                    return
            
            self.current_sheet.magic_items[index]["attuned"] = attuned
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            
            # Update attunement count
            attunement_count = sum(1 for item in self.current_sheet.magic_items if item.get("attuned", False))
            self._attunement_label.configure(text=f"Attuned: {attunement_count}/{attunement_limit}")
    
    def _get_attunement_limit(self) -> int:
        """Get the attunement limit for the current character.
        
        Base limit is 3. Artificers get bonus slots from:
        - Magic Item Adept (level 10): +1 (total 4)
        - Advanced Artifice (level 14): +1 (total 5)  
        - Magic Item Master (level 18): +1 (total 6)
        
        Thief Rogues (level 13+) can attune to 4 items via Use Magic Device.
        """
        base_limit = 3
        
        if not self.current_character or not self.current_character.classes:
            return base_limit
        
        # Check for Artificer class
        for class_level in self.current_character.classes:
            if class_level.character_class == CharacterClass.ARTIFICER:
                features = self._get_artificer_features(class_level.level)
                return features.get("attunement_slots", base_limit)
        
        # Check for Thief Rogue with Use Magic Device (level 13+)
        for class_level in self.current_character.classes:
            if class_level.character_class == CharacterClass.ROGUE:
                if class_level.subclass == "Thief" and class_level.level >= 13:
                    return 4  # Use Magic Device grants 4 attunement slots
        
        return base_limit
    
    def _delete_magic_item(self, index: int):
        """Delete a magic item."""
        if self.current_sheet and index < len(self.current_sheet.magic_items):
            del self.current_sheet.magic_items[index]
            self.sheet_manager.update_sheet(self.current_character.name, self.current_sheet)
            self._create_inventory_content()
    
    def _create_spells_content(self):
        """Create the spells tab content (embedded spell list)."""
        # Clear existing content
        for widget in self.spells_content.winfo_children():
            widget.destroy()
        
        if not self.current_character or not self.spell_manager:
            ctk.CTkLabel(
                self.spells_content,
                text="No spell manager available" if not self.spell_manager else "No character selected",
                font=ctk.CTkFont(size=14),
                text_color=self.theme.get_text_secondary()
            ).pack(expand=True, pady=50)
            return
        
        # Import spell lists view components
        from ui.spell_lists_view import CharacterSpellsPanel
        
        # Create the spell list detail panel for this character
        # Use scrollable=False since the parent content_scroll already handles scrolling
        self.spell_detail_panel = CharacterSpellsPanel(
            self.spells_content,
            spell_manager=self.spell_manager,
            character_manager=self.character_manager,
            on_remove_spell=self._on_remove_spell,
            on_spell_click=self._show_spell_popup,  # Use popup instead of navigation
            on_character_updated=self._on_character_spells_updated,
            scrollable=False  # Parent already scrolls
        )
        self.spell_detail_panel.pack(fill="both", expand=True)
        
        # Set the current character on the panel
        self.spell_detail_panel.set_character(self.current_character)
    
    def _show_spell_popup(self, spell_name: str):
        """Show a popup dialog with spell details."""
        if not self.spell_manager:
            return
        
        spell = self.spell_manager.get_spell(spell_name)
        if spell:
            from ui.spell_detail import SpellPopupDialog
            SpellPopupDialog(self.winfo_toplevel(), spell)
    
    def _on_remove_spell(self, spell_name: str):
        """Handle spell removal from the character's spell list."""
        if self.current_character:
            self.current_character.remove_spell(spell_name)
            self.character_manager.update_character(self.current_character.name, self.current_character)
            self._create_spells_content()  # Refresh the spell list
    
    def _on_character_spells_updated(self):
        """Handle when character spells are updated."""
        if self.current_character:
            self.character_manager.update_character(self.current_character.name, self.current_character)


class NewCharacterDialog(ctk.CTkToplevel):
    """Dialog for creating a new character."""
    
    def __init__(self, parent, character_manager: CharacterManager):
        super().__init__(parent)
        
        self.character_manager = character_manager
        self.result: Optional[CharacterSpellList] = None
        self.theme = get_theme_manager()
        
        self.title("New Character")
        self.geometry("420x380")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            container, text="Create New Character",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(0, 20))
        
        # Name
        ctk.CTkLabel(container, text="Character Name:").pack(anchor="w")
        self.name_var = ctk.StringVar()
        name_entry = ctk.CTkEntry(container, textvariable=self.name_var, width=300)
        name_entry.pack(fill="x", pady=(0, 15))
        name_entry.focus()
        
        # Class selection
        ctk.CTkLabel(container, text="Starting Class:").pack(anchor="w")
        self.class_var = ctk.StringVar(value="Fighter")
        class_combo = ctk.CTkComboBox(
            container, width=300,
            values=[c.value for c in CharacterClass.all_classes() if c != CharacterClass.CUSTOM],
            variable=self.class_var
        )
        class_combo.pack(fill="x", pady=(0, 15))
        
        # Starting level
        ctk.CTkLabel(container, text="Starting Level:").pack(anchor="w")
        self.level_var = ctk.StringVar(value="1")
        level_entry = ctk.CTkEntry(container, textvariable=self.level_var, width=100)
        level_entry.pack(anchor="w", pady=(0, 20))
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Create", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_create
        ).pack(side="right")
    
    def _on_create(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a character name.")
            return
        
        # Check for duplicate name
        if any(c.name == name for c in self.character_manager.characters):
            messagebox.showerror("Error", "A character with that name already exists.")
            return
        
        try:
            level = max(1, min(20, int(self.level_var.get())))
        except ValueError:
            level = 1
        
        # Create character
        char_class = CharacterClass.from_string(self.class_var.get())
        character = CharacterSpellList(name=name)
        character.add_class(char_class, level)
        
        # Apply class feature spells (e.g., Mending for Artificer)
        from character import update_subclass_spells
        update_subclass_spells(character)
        
        self.character_manager.add_character(character)
        self.result = character
        self.destroy()


class AddClassDialog(ctk.CTkToplevel):
    """Dialog for adding a new class (multiclassing)."""
    
    def __init__(self, parent, available_classes: List[CharacterClass]):
        super().__init__(parent)
        
        self.available_classes = available_classes
        self.result: Optional[CharacterClass] = None
        self.theme = get_theme_manager()
        
        self.title("Add Class")
        self.geometry("300x150")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            container, text="Select class to add:",
            font=ctk.CTkFont(size=14)
        ).pack(anchor="w", pady=(0, 10))
        
        self.class_var = ctk.StringVar(value=self.available_classes[0].value if self.available_classes else "")
        class_combo = ctk.CTkComboBox(
            container, width=260,
            values=[c.value for c in self.available_classes],
            variable=self.class_var
        )
        class_combo.pack(fill="x", pady=(0, 20))
        
        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=80,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            btn_frame, text="Add", width=80,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_add
        ).pack(side="right")
    
    def _on_add(self):
        class_name = self.class_var.get()
        if class_name:
            self.result = CharacterClass.from_string(class_name)
        self.destroy()


class FeaturePopupDialog(ctk.CTkToplevel):
    """Dialog for displaying class feature details with formatted description."""
    
    def __init__(self, parent, ability: ClassAbility, class_name: str):
        super().__init__(parent)
        
        from ui.rich_text_utils import RichTextRenderer
        
        self.ability = ability
        self.class_name = class_name
        self.theme = get_theme_manager()
        self._renderer = RichTextRenderer(self.theme)
        
        self.title(f"{ability.title}")
        self.geometry("550x450")
        self.resizable(True, True)
        self.minsize(450, 350)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _render_formatted_text(self, parent, text: str):
        """Render text with rich formatting using global utilities."""
        # Use single * for italic/bold in class features (legacy format)
        self._renderer.render_formatted_text(
            parent, text, 
            on_spell_click=lambda s: self._renderer.show_spell_popup(self, s),
            bold_pattern=r'\*([^*]+)\*'
        )
    
    def _render_table(self, parent, table: dict):
        """Render a table from ability.tables."""
        title = table.get("title", "")
        # Support both 'headers' and 'columns' keys for backwards compatibility
        columns = table.get("headers", table.get("columns", []))
        rows = table.get("rows", [])
        
        if title:
            ctk.CTkLabel(
                parent, text=title,
                font=ctk.CTkFont(size=12, weight="bold")
            ).pack(anchor="w", pady=(8, 4))
        
        if not columns or not rows:
            return
        
        # Use global renderer for tables
        self._renderer.render_table(
            parent, columns, rows,
            on_spell_click=lambda s: self._renderer.show_spell_popup(self, s)
        )
    
    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_primary'))
        container.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'),
                              corner_radius=0)
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header, text=self.ability.title,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left", padx=15, pady=10)
        
        ctk.CTkLabel(
            header, text=f"({self.class_name})",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(side="left", padx=5, pady=10)
        
        # Close button
        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=5, pady=5)
        
        # Scrollable content
        scroll_frame = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Description with formatted text
        desc_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'),
                                  corner_radius=8)
        desc_frame.pack(fill="x")
        
        inner_frame = ctk.CTkFrame(desc_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=10, pady=10)
        
        if self.ability.description:
            self._render_formatted_text(inner_frame, self.ability.description)
        else:
            ctk.CTkLabel(
                inner_frame, text="No description available.",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(anchor="w")
        
        # Render tables if present
        if hasattr(self.ability, 'tables') and self.ability.tables:
            tables_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
            tables_frame.pack(fill="x", pady=(10, 0))
            
            for table in self.ability.tables:
                self._render_table(tables_frame, table)
        
        # OK button at bottom
        ctk.CTkButton(
            container, text="OK", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self.destroy
        ).pack(pady=15)


class FeatPopupDialog(ctk.CTkToplevel):
    """Dialog for displaying feat details with formatted description."""
    
    def __init__(self, parent, feat):
        super().__init__(parent)
        
        from ui.rich_text_utils import RichTextRenderer
        
        self.feat = feat
        self.theme = get_theme_manager()
        self._renderer = RichTextRenderer(self.theme)
        
        self.title(f"{feat.name}")
        self.geometry("550x450")
        self.resizable(True, True)
        self.minsize(450, 350)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _render_formatted_text(self, parent, text: str):
        """Render text with rich formatting using global utilities."""
        # Use single * for italic/bold in feats (legacy format)
        self._renderer.render_formatted_text(
            parent, text, 
            on_spell_click=lambda s: self._renderer.show_spell_popup(self, s),
            bold_pattern=r'\*([^*]+)\*'
        )
    
    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_primary'))
        container.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'),
                              corner_radius=0)
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header, text=self.feat.name,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left", padx=15, pady=10)
        
        # Type badge
        if self.feat.type:
            type_text = self.feat.type
        else:
            type_text = "General"
        
        ctk.CTkLabel(
            header, text=f"({type_text})",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(side="left", padx=5, pady=10)
        
        # Close button
        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=5, pady=5)
        
        # Scrollable content
        scroll_frame = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Prerequisite warning if applicable
        if self.feat.has_prereq and self.feat.prereq:
            prereq_frame = ctk.CTkFrame(scroll_frame, fg_color="#4a3000", corner_radius=8)
            prereq_frame.pack(fill="x", pady=(0, 10))
            
            ctk.CTkLabel(
                prereq_frame, text=f"⚠️ Prerequisite: {self.feat.prereq}",
                font=ctk.CTkFont(size=11),
                text_color="#ffcc00"
            ).pack(padx=10, pady=8)
        
        # Spellcasting info if applicable
        if self.feat.is_spellcasting:
            spell_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_current_color('accent_primary'), corner_radius=8)
            spell_frame.pack(fill="x", pady=(0, 10))
            
            spell_info = "🔮 Spellcasting Feat"
            if self.feat.spell_lists:
                spell_info += f"\nSpell Lists: {', '.join(self.feat.spell_lists)}"
            if self.feat.spells_num:
                spell_info += f"\nSpells: {self.feat.get_spells_summary()}"
            if self.feat.set_spells:
                spell_info += f"\nGranted Spells: {', '.join(self.feat.set_spells)}"
            
            ctk.CTkLabel(
                spell_frame, text=spell_info,
                font=ctk.CTkFont(size=11),
                justify="left"
            ).pack(padx=10, pady=8, anchor="w")
        
        # Description
        desc_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'),
                                  corner_radius=8)
        desc_frame.pack(fill="x")
        
        inner_frame = ctk.CTkFrame(desc_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=10, pady=10)
        
        if self.feat.description:
            self._render_formatted_text(inner_frame, self.feat.description)
        else:
            ctk.CTkLabel(
                inner_frame, text="No description available.",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(anchor="w")
        
        # OK button at bottom
        ctk.CTkButton(
            container, text="OK", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self.destroy
        ).pack(pady=15)


class LineageTraitPopupDialog(ctk.CTkToplevel):
    """Dialog for displaying lineage trait details."""
    
    def __init__(self, parent, trait):
        super().__init__(parent)
        
        from lineage import LineageTrait
        from ui.rich_text_utils import RichTextRenderer
        
        self.trait: LineageTrait = trait
        self.theme = get_theme_manager()
        self._renderer = RichTextRenderer(self.theme)
        
        self.title(f"{trait.name}")
        self.geometry("600x500")
        self.resizable(True, True)
        self.minsize(500, 350)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _render_formatted_text(self, parent, text: str):
        """Render text with rich formatting using global utilities."""
        self._renderer.render_formatted_text(
            parent, text, 
            on_spell_click=lambda s: self._renderer.show_spell_popup(self, s)
        )
    
    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_primary'))
        container.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'),
                              corner_radius=0)
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header, text=self.trait.name,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left", padx=15, pady=10)
        
        ctk.CTkLabel(
            header, text="(Lineage Trait)",
            font=ctk.CTkFont(size=12),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(side="left", padx=5, pady=10)
        
        # Close button
        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=5, pady=5)
        
        # Scrollable content
        scroll_frame = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Description
        desc_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'),
                                  corner_radius=8)
        desc_frame.pack(fill="x")
        
        inner_frame = ctk.CTkFrame(desc_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=10, pady=10)
        
        if self.trait.description:
            self._render_formatted_text(inner_frame, self.trait.description)
        else:
            ctk.CTkLabel(
                inner_frame, text="No description available.",
                font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(anchor="w")
        
        # OK button at bottom
        ctk.CTkButton(
            container, text="OK", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self.destroy
        ).pack(pady=15)


class CharacterFeatEditorDialog(ctk.CTkToplevel):
    """Dialog for adding/removing feats from a character."""
    
    def __init__(self, parent, character: CharacterSpellList):
        super().__init__(parent)
        
        self.character = character
        self.result = None
        self.theme = get_theme_manager()
        self.feat_manager = get_feat_manager()
        
        # Current feats (copy to allow cancel)
        self.selected_feats = list(character.feats) if character.feats else []
        
        self.title(f"Edit Feats - {character.name}")
        self.geometry("700x550")
        self.resizable(True, True)
        self.minsize(600, 450)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_primary'))
        container.pack(fill="both", expand=True, padx=15, pady=15)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=0)
        container.grid_columnconfigure(2, weight=1)
        container.grid_rowconfigure(1, weight=1)
        
        # Left side: Available feats
        ctk.CTkLabel(
            container, text="Available Feats",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        # Search and filter
        filter_frame = ctk.CTkFrame(container, fg_color="transparent")
        filter_frame.grid(row=0, column=0, sticky="e", pady=(0, 5))
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_feats())
        
        search_entry = ctk.CTkEntry(
            filter_frame, textvariable=self.search_var,
            placeholder_text="Search...", width=150
        )
        search_entry.pack(side="left", padx=(0, 5))
        
        # Available feats list
        self.available_frame = ctk.CTkScrollableFrame(
            container, fg_color=self.theme.get_current_color('bg_secondary')
        )
        self.available_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        
        # Middle: Add/Remove buttons
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.grid(row=1, column=1, padx=10)
        
        ctk.CTkButton(
            button_frame, text="Add →", width=80,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            command=self._add_selected_feat
        ).pack(pady=5)
        
        ctk.CTkButton(
            button_frame, text="← Remove", width=80,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._remove_selected_feat
        ).pack(pady=5)
        
        # Right side: Character's feats
        ctk.CTkLabel(
            container, text="Character's Feats",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=2, sticky="w", pady=(0, 5))
        
        self.selected_frame = ctk.CTkScrollableFrame(
            container, fg_color=self.theme.get_current_color('bg_secondary')
        )
        self.selected_frame.grid(row=1, column=2, sticky="nsew", pady=5)
        
        # Bottom buttons
        bottom_frame = ctk.CTkFrame(container, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        
        ctk.CTkButton(
            bottom_frame, text="Cancel", width=100,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._on_cancel
        ).pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            bottom_frame, text="Save", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_save
        ).pack(side="right")
        
        # Populate lists
        self._populate_available_feats()
        self._populate_selected_feats()
        
        # Track selected items
        self.selected_available_feat = None
        self.selected_character_feat = None
    
    def _populate_available_feats(self):
        """Populate the available feats list."""
        # Clear existing
        for widget in self.available_frame.winfo_children():
            widget.destroy()
        
        # Get search filter
        search = self.search_var.get().lower().strip()
        
        # Get all feats not already selected
        available = [f for f in self.feat_manager.feats if f.name not in self.selected_feats]
        
        # Apply search filter
        if search:
            available = [f for f in available if search in f.name.lower() or search in f.type.lower()]
        
        # Sort by name
        available.sort(key=lambda f: f.name)
        
        for feat in available:
            self._create_feat_row(self.available_frame, feat, is_available=True)
    
    def _populate_selected_feats(self):
        """Populate the character's feats list."""
        # Clear existing
        for widget in self.selected_frame.winfo_children():
            widget.destroy()
        
        for feat_name in self.selected_feats:
            feat = self.feat_manager.get_feat(feat_name)
            if feat:
                self._create_feat_row(self.selected_frame, feat, is_available=False)
    
    def _create_feat_row(self, parent, feat, is_available: bool):
        """Create a row for a feat in the list."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2, padx=5)
        
        # Radio-like selection
        var_name = f"available_{feat.name}" if is_available else f"selected_{feat.name}"
        
        btn = ctk.CTkButton(
            row,
            text=feat.name,
            font=ctk.CTkFont(size=11),
            fg_color=self.theme.get_current_color('bg_tertiary'),
            hover_color=self.theme.get_current_color('accent'),
            text_color=self.theme.get_current_color('text_primary'),
            anchor="w",
            height=28,
            command=lambda f=feat, a=is_available: self._select_feat(f, a)
        )
        btn.pack(side="left", fill="x", expand=True)
        
        # Store reference for selection highlighting
        setattr(self, var_name.replace(" ", "_"), btn)
        
        # Type badge
        if feat.type:
            type_colors = {
                "Origin": "#2d5a27",
                "Fighting Style": "#5a2727",
                "Eldritch Invocation": "#3d275a",
                "Epic Boon": "#5a4827",
                "Aberrant Dragonmark": "#275a5a"
            }
            badge_color = type_colors.get(feat.type, self.theme.get_current_color('bg_tertiary'))
            
            ctk.CTkLabel(
                row, text=feat.type[:3],
                font=ctk.CTkFont(size=9),
                fg_color=badge_color,
                corner_radius=4,
                width=30
            ).pack(side="right", padx=2)
        
        # Spellcasting indicator
        if feat.is_spellcasting:
            ctk.CTkLabel(
                row, text="🔮",
                font=ctk.CTkFont(size=10)
            ).pack(side="right", padx=2)
    
    def _select_feat(self, feat, is_available: bool):
        """Handle feat selection."""
        if is_available:
            self.selected_available_feat = feat.name
            self.selected_character_feat = None
        else:
            self.selected_character_feat = feat.name
            self.selected_available_feat = None
    
    def _add_selected_feat(self):
        """Add the selected available feat to character."""
        if self.selected_available_feat and self.selected_available_feat not in self.selected_feats:
            self.selected_feats.append(self.selected_available_feat)
            self.selected_available_feat = None
            self._populate_available_feats()
            self._populate_selected_feats()
    
    def _remove_selected_feat(self):
        """Remove the selected feat from character."""
        if self.selected_character_feat and self.selected_character_feat in self.selected_feats:
            self.selected_feats.remove(self.selected_character_feat)
            self.selected_character_feat = None
            self._populate_available_feats()
            self._populate_selected_feats()
    
    def _filter_feats(self):
        """Filter available feats based on search."""
        self._populate_available_feats()
    
    def _on_save(self):
        """Save the selected feats."""
        self.result = self.selected_feats
        self.destroy()
    
    def _on_cancel(self):
        """Cancel without saving."""
        self.result = None
        self.destroy()