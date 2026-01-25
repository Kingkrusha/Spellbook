"""
Character Spell List data model for D&D Spellbook Application.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional
from spell import CharacterClass


@dataclass
class ClassLevel:
    """Represents a class and its level for a character."""
    character_class: CharacterClass
    level: int
    subclass: str = ""  # Name of the subclass (e.g., "Path of the Berserker")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "class": self.character_class.value,
            "level": self.level,
            "subclass": self.subclass
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClassLevel":
        """Create from dictionary."""
        return cls(
            character_class=CharacterClass.from_string(data["class"]),
            level=data["level"],
            subclass=data.get("subclass", "")
        )


@dataclass
class CharacterSpellList:
    """Represents a character's known spell list."""
    name: str
    classes: List[ClassLevel] = field(default_factory=list)
    known_spells: List[str] = field(default_factory=list)  # Spell names
    prepared_spells: List[str] = field(default_factory=list)  # Prepared spell names
    subclass_spells: List[str] = field(default_factory=list)  # Spells from subclasses (always prepared)
    class_feature_spells: List[str] = field(default_factory=list)  # Spells from class features (e.g., Mending for Artificer)
    current_slots: Dict[int, int] = field(default_factory=dict)  # {spell_level: current_count}
    warlock_slots_current: int = 0  # Current warlock pact magic slots
    mystic_arcanum_used: List[int] = field(default_factory=list)  # Spell levels used
    # Custom class settings (only used when class is CUSTOM)
    custom_max_slots: Dict[int, int] = field(default_factory=dict)  # {spell_level: max_slots}
    custom_max_cantrips: int = 0  # Maximum cantrips for custom class
    
    @property
    def primary_class(self) -> Optional[ClassLevel]:
        """Return the primary (first) class."""
        if self.classes:
            return self.classes[0]
        return None
    
    @property
    def total_level(self) -> int:
        """Return the sum of all class levels."""
        return sum(cl.level for cl in self.classes)
    
    @property
    def is_multiclass(self) -> bool:
        """Check if character has multiple classes."""
        return len(self.classes) > 1
    
    @property
    def has_custom_class(self) -> bool:
        """Check if character has the Custom class."""
        return any(cl.character_class == CharacterClass.CUSTOM for cl in self.classes)
    
    def get_class_levels_tuple(self) -> List[Tuple[CharacterClass, int]]:
        """Return class levels as list of tuples for spell slot calculation."""
        return [(cl.character_class, cl.level) for cl in self.classes]
    
    def get_class_levels_with_subclass(self) -> List[Tuple[CharacterClass, int, Optional[str]]]:
        """Return class levels with subclass info for spell slot calculation."""
        return [(cl.character_class, cl.level, cl.subclass) for cl in self.classes]
    
    def has_eldritch_knight(self) -> bool:
        """Check if character has the Eldritch Knight subclass."""
        return any(cl.character_class == CharacterClass.FIGHTER and cl.subclass == "Eldritch Knight" for cl in self.classes)
    
    def get_eldritch_knight_level(self) -> int:
        """Get the Fighter level if character has Eldritch Knight subclass, 0 otherwise."""
        for cl in self.classes:
            if cl.character_class == CharacterClass.FIGHTER and cl.subclass == "Eldritch Knight":
                return cl.level
        return 0
    
    def display_classes(self) -> str:
        """Return formatted string of all classes and levels."""
        if not self.classes:
            return "No class"
        return " / ".join(f"{cl.character_class.value} {cl.level}" for cl in self.classes)
    
    def add_class(self, character_class: CharacterClass, level: int = 1):
        """Add a new class to the character."""
        # Check if class already exists
        for cl in self.classes:
            if cl.character_class == character_class:
                return False
        self.classes.append(ClassLevel(character_class, level))
        return True
    
    def remove_class(self, character_class: CharacterClass) -> bool:
        """Remove a class from the character."""
        for i, cl in enumerate(self.classes):
            if cl.character_class == character_class:
                del self.classes[i]
                return True
        return False
    
    def set_class_level(self, character_class: CharacterClass, level: int) -> bool:
        """Set the level for a specific class."""
        for cl in self.classes:
            if cl.character_class == character_class:
                cl.level = max(1, min(20, level))
                return True
        return False
    
    def add_spell(self, spell_name: str) -> bool:
        """Add a spell to the known spells list."""
        if spell_name.lower() not in [s.lower() for s in self.known_spells]:
            self.known_spells.append(spell_name)
            return True
        return False
    
    def remove_spell(self, spell_name: str) -> bool:
        """Remove a spell from the known spells list."""
        for i, name in enumerate(self.known_spells):
            if name.lower() == spell_name.lower():
                del self.known_spells[i]
                # Also remove from prepared if present
                self.unprepare_spell(spell_name)
                return True
        return False
    
    def has_spell(self, spell_name: str) -> bool:
        """Check if a spell is in the known spells list."""
        return spell_name.lower() in [s.lower() for s in self.known_spells]
    
    def prepare_spell(self, spell_name: str) -> bool:
        """Mark a spell as prepared."""
        if spell_name.lower() not in [s.lower() for s in self.prepared_spells]:
            self.prepared_spells.append(spell_name)
            return True
        return False
    
    def unprepare_spell(self, spell_name: str) -> bool:
        """Remove a spell from prepared list. Cannot unprepare subclass spells."""
        # Check if it's a subclass spell (always prepared)
        if self.is_subclass_spell(spell_name):
            return False
        for i, name in enumerate(self.prepared_spells):
            if name.lower() == spell_name.lower():
                del self.prepared_spells[i]
                return True
        return False
    
    def is_prepared(self, spell_name: str) -> bool:
        """Check if a spell is prepared (includes subclass spells)."""
        return (spell_name.lower() in [s.lower() for s in self.prepared_spells] or 
                self.is_subclass_spell(spell_name))
    
    def is_subclass_spell(self, spell_name: str) -> bool:
        """Check if a spell is from a subclass (always prepared)."""
        return spell_name.lower() in [s.lower() for s in self.subclass_spells]
    
    def add_subclass_spell(self, spell_name: str) -> bool:
        """Add a spell as a subclass spell (always prepared)."""
        if spell_name.lower() not in [s.lower() for s in self.subclass_spells]:
            self.subclass_spells.append(spell_name)
            # Also add to known spells if not present
            if not self.has_spell(spell_name):
                self.known_spells.append(spell_name)
            return True
        return False
    
    def remove_subclass_spell(self, spell_name: str) -> bool:
        """Remove a spell from subclass spells list."""
        for i, name in enumerate(self.subclass_spells):
            if name.lower() == spell_name.lower():
                del self.subclass_spells[i]
                return True
        return False
    
    def get_prepared_count(self) -> int:
        """Get count of prepared spells NOT counting subclass spells."""
        # Count prepared spells that aren't subclass spells
        count = 0
        for spell in self.prepared_spells:
            if not self.is_subclass_spell(spell):
                count += 1
        return count
    
    def set_current_slots(self, spell_level: int, count: int):
        """Set current spell slots for a level."""
        self.current_slots[spell_level] = max(0, count)
    
    def get_current_slots(self, spell_level: int) -> int:
        """Get current spell slots for a level."""
        return self.current_slots.get(spell_level, 0)
    
    def use_mystic_arcanum(self, spell_level: int):
        """Mark a mystic arcanum as used."""
        if spell_level not in self.mystic_arcanum_used:
            self.mystic_arcanum_used.append(spell_level)
    
    def reset_mystic_arcanum(self, spell_level: int):
        """Reset a mystic arcanum (mark as available)."""
        if spell_level in self.mystic_arcanum_used:
            self.mystic_arcanum_used.remove(spell_level)
    
    def is_mystic_arcanum_available(self, spell_level: int) -> bool:
        """Check if a mystic arcanum is available."""
        return spell_level not in self.mystic_arcanum_used
    
    def long_rest(self, max_slots: Dict[int, int], warlock_max_slots: int):
        """Restore all spell slots and mystic arcanum on long rest."""
        # Restore regular spell slots
        for level, max_count in max_slots.items():
            self.current_slots[level] = max_count
        
        # Restore warlock slots
        self.warlock_slots_current = warlock_max_slots
        
        # Reset all mystic arcanum
        self.mystic_arcanum_used = []
    
    def short_rest(self, warlock_max_slots: int):
        """Restore warlock spell slots on short rest."""
        self.warlock_slots_current = warlock_max_slots
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "classes": [cl.to_dict() for cl in self.classes],
            "known_spells": self.known_spells,
            "prepared_spells": self.prepared_spells,
            "subclass_spells": self.subclass_spells,
            "class_feature_spells": self.class_feature_spells,
            "current_slots": {str(k): v for k, v in self.current_slots.items()},
            "warlock_slots_current": self.warlock_slots_current,
            "mystic_arcanum_used": self.mystic_arcanum_used,
            "custom_max_slots": {str(k): v for k, v in self.custom_max_slots.items()},
            "custom_max_cantrips": self.custom_max_cantrips
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CharacterSpellList":
        """Create from dictionary."""
        # Convert current_slots keys back to int
        current_slots = {}
        for k, v in data.get("current_slots", {}).items():
            current_slots[int(k)] = v
        
        # Convert custom_max_slots keys back to int
        custom_max_slots = {}
        for k, v in data.get("custom_max_slots", {}).items():
            custom_max_slots[int(k)] = v
        
        return cls(
            name=data["name"],
            classes=[ClassLevel.from_dict(c) for c in data.get("classes", [])],
            known_spells=data.get("known_spells", []),
            prepared_spells=data.get("prepared_spells", []),
            subclass_spells=data.get("subclass_spells", []),
            class_feature_spells=data.get("class_feature_spells", []),
            current_slots=current_slots,
            warlock_slots_current=data.get("warlock_slots_current", 0),
            mystic_arcanum_used=data.get("mystic_arcanum_used", []),
            custom_max_slots=custom_max_slots,
            custom_max_cantrips=data.get("custom_max_cantrips", 0)
        )


# Prepared spell calculation constants
# All spellcasters now use prepared spells in 2024 rules
PREPARED_CASTER_CLASSES = {
    CharacterClass.ARTIFICER: "INT",  # Uses table value, not formula
    CharacterClass.BARD: "CHA",       # Uses table value (spells_prepared column)
    CharacterClass.CLERIC: "WIS",     # Level + WIS modifier
    CharacterClass.DRUID: "WIS",      # Level + WIS modifier
    CharacterClass.PALADIN: "CHA",    # Level/2 + CHA modifier (minimum 1)
    CharacterClass.RANGER: "WIS",     # Uses table value (spells_prepared column)
    CharacterClass.SORCERER: "CHA",   # Uses table value (spells_prepared column)
    CharacterClass.WARLOCK: "CHA",    # Uses table value (spells_prepared column)  
    CharacterClass.WIZARD: "INT",     # Level + INT modifier
}

# Classes that know a fixed number of spells - deprecated in 2024 rules
# Keeping for backwards compatibility but empty
SPELLS_KNOWN_CLASSES: set = set()


def get_max_prepared_spells(character: CharacterSpellList, class_manager=None) -> Optional[int]:
    """
    Calculate the maximum number of spells a character can prepare.
    
    For prepared casters, this is based on class level and ability modifier.
    For "spells known" casters, returns None as they don't prepare spells.
    
    Args:
        character: The character to calculate for
        class_manager: Optional ClassManager instance (for Artificer table lookup)
    
    Returns:
        Maximum prepared spells, or None if not a prepared caster
    """
    if not character.classes:
        return None
    
    # Check for Eldritch Knight (Fighter with spellcasting subclass)
    ek_level = character.get_eldritch_knight_level()
    if ek_level >= 3:
        from spell_slots import get_eldritch_knight_prepared
        return get_eldritch_knight_prepared(ek_level)
    
    # For simplicity, use primary class for now
    # TODO: Handle multiclass prepared spell calculation
    primary = character.primary_class
    if not primary:
        return None
    
    char_class = primary.character_class
    level = primary.level
    
    # Check if this is a "spells known" class (not prepared)
    if char_class in SPELLS_KNOWN_CLASSES:
        return None
    
    # Check if this is a prepared caster
    if char_class not in PREPARED_CASTER_CLASSES:
        return None
    
    # Artificer uses a fixed table value
    if char_class == CharacterClass.ARTIFICER:
        return _get_artificer_prepared_spells(level, class_manager)
    
    # Bard uses a fixed table value
    if char_class == CharacterClass.BARD:
        return _get_bard_prepared_spells(level)
    
    # Ranger uses a fixed table value  
    if char_class == CharacterClass.RANGER:
        return _get_ranger_prepared_spells(level)
    
    # Sorcerer uses a fixed table value
    if char_class == CharacterClass.SORCERER:
        return _get_sorcerer_prepared_spells(level)
    
    # Warlock uses a fixed table value
    if char_class == CharacterClass.WARLOCK:
        return _get_warlock_prepared_spells(level)
    
    # Paladin has a different formula (half level rounded down + modifier)
    if char_class == CharacterClass.PALADIN:
        # Minimum of 1 for Paladin
        return max(1, (level // 2))  # Without ability modifier for now
    
    # Other prepared casters: Level + ability modifier
    # Without ability scores, we just return the level
    return level


def _get_artificer_prepared_spells(level: int, class_manager=None) -> int:
    """Get Artificer's max prepared spells from the class table."""
    # Artificer prepared spells by level (from the class table)
    artificer_prepared = {
        1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 6, 7: 7, 8: 7, 9: 9, 10: 9,
        11: 10, 12: 10, 13: 11, 14: 11, 15: 12, 16: 12, 17: 14, 18: 14, 19: 15, 20: 15
    }
    return artificer_prepared.get(level, 2)


def _get_bard_prepared_spells(level: int) -> int:
    """Get Bard's max prepared spells from the class table (2024 rules)."""
    bard_prepared = {
        1: 4, 2: 5, 3: 6, 4: 7, 5: 9, 6: 10, 7: 11, 8: 12, 9: 14, 10: 15,
        11: 16, 12: 16, 13: 17, 14: 17, 15: 18, 16: 18, 17: 19, 18: 20, 19: 21, 20: 22
    }
    return bard_prepared.get(level, 4)


def _get_ranger_prepared_spells(level: int) -> int:
    """Get Ranger's max prepared spells from the class table (2024 rules)."""
    ranger_prepared = {
        1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 6, 7: 7, 8: 7, 9: 9, 10: 9,
        11: 10, 12: 10, 13: 11, 14: 11, 15: 12, 16: 12, 17: 14, 18: 14, 19: 15, 20: 15
    }
    return ranger_prepared.get(level, 2)


def _get_sorcerer_prepared_spells(level: int) -> int:
    """Get Sorcerer's max prepared spells from the class table (2024 rules)."""
    sorcerer_prepared = {
        1: 2, 2: 4, 3: 6, 4: 7, 5: 9, 6: 10, 7: 11, 8: 12, 9: 14, 10: 15,
        11: 16, 12: 16, 13: 17, 14: 17, 15: 18, 16: 18, 17: 19, 18: 20, 19: 21, 20: 22
    }
    return sorcerer_prepared.get(level, 2)


def _get_warlock_prepared_spells(level: int) -> int:
    """Get Warlock's max prepared spells from the class table (2024 rules)."""
    warlock_prepared = {
        1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10, 10: 10,
        11: 11, 12: 11, 13: 12, 14: 12, 15: 13, 16: 13, 17: 14, 18: 14, 19: 15, 20: 15
    }
    return warlock_prepared.get(level, 2)


# Class feature spells that are granted by specific class features
# Format: {class_name: [(spell_name, min_level_required)]}
CLASS_FEATURE_SPELLS = {
    "Artificer": [("Mending", 1)],  # Tinker's Magic grants Mending at level 1
    "Bard": [("Power Word Heal", 20), ("Power Word Kill", 20)],  # Words of Creation grants these at level 20
}


def update_subclass_spells(character: CharacterSpellList, class_manager=None) -> None:
    """
    Update a character's subclass spells and class feature spells based on their class/subclass selections.
    
    This should be called when:
    - A character's subclass changes
    - A character's level changes
    - A character is first created
    
    Args:
        character: The character to update
        class_manager: Optional ClassManager instance
    """
    if class_manager is None:
        from character_class import get_class_manager
        class_manager = get_class_manager()
    
    # Store old spells for comparison
    old_subclass_spells = character.subclass_spells.copy()
    old_class_feature_spells = character.class_feature_spells.copy()
    
    # Clear and rebuild
    character.subclass_spells.clear()
    character.class_feature_spells.clear()
    
    # Add subclass spells and class feature spells for each class
    for class_level in character.classes:
        class_name = class_level.character_class.value
        
        # Get the class definition
        class_def = class_manager.get_class(class_name)
        
        # Add class feature spells from class definition (e.g., Divine Smite, Find Steed for Paladin)
        if class_def and hasattr(class_def, 'class_spells') and class_def.class_spells:
            for class_spell in class_def.class_spells:
                if class_level.level >= class_spell.level_gained:
                    spell_name = class_spell.spell_name
                    if spell_name not in character.class_feature_spells:
                        character.class_feature_spells.append(spell_name)
                    # Also add to subclass_spells so they're always prepared and don't count against limit
                    if spell_name not in character.subclass_spells:
                        character.subclass_spells.append(spell_name)
                    # Also add to known spells if not present
                    if not character.has_spell(spell_name):
                        character.known_spells.append(spell_name)
                    # Auto-prepare if always_prepared is True
                    if class_spell.always_prepared and spell_name not in character.prepared_spells:
                        character.prepared_spells.append(spell_name)
        
        # Add class feature spells from hardcoded dict (e.g., Mending for Artificer, Power Word spells for Bard)
        if class_name in CLASS_FEATURE_SPELLS:
            for spell_name, min_level in CLASS_FEATURE_SPELLS[class_name]:
                if class_level.level >= min_level:
                    if spell_name not in character.class_feature_spells:
                        character.class_feature_spells.append(spell_name)
                    # Also add to subclass_spells so they're always prepared and don't count against limit
                    if spell_name not in character.subclass_spells:
                        character.subclass_spells.append(spell_name)
                    # Also add to known spells if not present
                    if not character.has_spell(spell_name):
                        character.known_spells.append(spell_name)
                    # Auto-prepare these spells
                    if spell_name not in character.prepared_spells:
                        character.prepared_spells.append(spell_name)
        
        # Skip subclass spells if no subclass selected
        if not class_level.subclass:
            continue
        
        # class_def already retrieved above
        if not class_def:
            continue
        
        # Find the subclass
        subclass_def = None
        for sc in class_def.subclasses:
            if sc.name == class_level.subclass:
                subclass_def = sc
                break
        
        if not subclass_def:
            continue
        
        # Get spells available at this level
        spells = subclass_def.get_spells_at_level(class_level.level)
        for spell in spells:
            if spell.spell_name not in character.subclass_spells:
                character.subclass_spells.append(spell.spell_name)
                # Also add to known spells if not present
                if not character.has_spell(spell.spell_name):
                    character.known_spells.append(spell.spell_name)
                # Auto-prepare subclass spells
                if spell.spell_name not in character.prepared_spells:
                    character.prepared_spells.append(spell.spell_name)
    
    # Remove old subclass spells that are no longer granted
    for spell in old_subclass_spells:
        if spell not in character.subclass_spells:
            # Remove from prepared if it was auto-prepared by subclass
            if spell in character.prepared_spells:
                character.prepared_spells.remove(spell)
            # Also remove from known spells (they came from subclass)
            if spell in character.known_spells:
                character.known_spells.remove(spell)
    
    # Remove old class feature spells that are no longer granted (e.g., lost Artificer levels)
    for spell in old_class_feature_spells:
        if spell not in character.class_feature_spells:
            if spell in character.prepared_spells:
                character.prepared_spells.remove(spell)
            if spell in character.known_spells:
                character.known_spells.remove(spell)
