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
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "class": self.character_class.value,
            "level": self.level
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClassLevel":
        """Create from dictionary."""
        return cls(
            character_class=CharacterClass.from_string(data["class"]),
            level=data["level"]
        )


@dataclass
class CharacterSpellList:
    """Represents a character's known spell list."""
    name: str
    classes: List[ClassLevel] = field(default_factory=list)
    known_spells: List[str] = field(default_factory=list)  # Spell names
    prepared_spells: List[str] = field(default_factory=list)  # Prepared spell names
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
        """Remove a spell from prepared list."""
        for i, name in enumerate(self.prepared_spells):
            if name.lower() == spell_name.lower():
                del self.prepared_spells[i]
                return True
        return False
    
    def is_prepared(self, spell_name: str) -> bool:
        """Check if a spell is prepared."""
        return spell_name.lower() in [s.lower() for s in self.prepared_spells]
    
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
            current_slots=current_slots,
            warlock_slots_current=data.get("warlock_slots_current", 0),
            mystic_arcanum_used=data.get("mystic_arcanum_used", []),
            custom_max_slots=custom_max_slots,
            custom_max_cantrips=data.get("custom_max_cantrips", 0)
        )
