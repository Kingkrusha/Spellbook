"""
Spell slot tables and calculation for D&D Spellbook Application.
"""

from typing import Dict, List, Tuple
from spell import CharacterClass


# Full caster spell slots by level (Bard, Cleric, Druid, Sorcerer, Wizard)
# Format: {caster_level: {spell_level: num_slots}}
FULL_CASTER_SLOTS = {
    1:  {1: 2},
    2:  {1: 3},
    3:  {1: 4, 2: 2},
    4:  {1: 4, 2: 3},
    5:  {1: 4, 2: 3, 3: 2},
    6:  {1: 4, 2: 3, 3: 3},
    7:  {1: 4, 2: 3, 3: 3, 4: 1},
    8:  {1: 4, 2: 3, 3: 3, 4: 2},
    9:  {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}

# Warlock Pact Magic slots by level
# Format: {warlock_level: (num_slots, slot_level)}
WARLOCK_PACT_SLOTS = {
    1:  (1, 1),
    2:  (2, 1),
    3:  (2, 2),
    4:  (2, 2),
    5:  (2, 3),
    6:  (2, 3),
    7:  (2, 4),
    8:  (2, 4),
    9:  (2, 5),
    10: (2, 5),
    11: (3, 5),
    12: (3, 5),
    13: (3, 5),
    14: (3, 5),
    15: (3, 5),
    16: (3, 5),
    17: (4, 5),
    18: (4, 5),
    19: (4, 5),
    20: (4, 5),
}

# Warlock Mystic Arcanum levels
# Format: {warlock_level: spell_level_unlocked}
WARLOCK_MYSTIC_ARCANUM = {
    11: 6,
    13: 7,
    15: 8,
    17: 9,
}

# Classes that count as full casters
FULL_CASTER_CLASSES = {
    CharacterClass.BARD,
    CharacterClass.CLERIC,
    CharacterClass.DRUID,
    CharacterClass.SORCERER,
    CharacterClass.WIZARD,
}

# Classes that count as half casters
HALF_CASTER_CLASSES = {
    CharacterClass.ARTIFICER,
    CharacterClass.PALADIN,
    CharacterClass.RANGER,
}

# Custom class is handled separately with user-defined spell slots


def calculate_multiclass_caster_level(class_levels: List[Tuple[CharacterClass, int]]) -> int:
    """
    Calculate the effective caster level for multiclass spell slot calculation.
    
    - Full casters: count full levels
    - Half casters: count half levels (round up)
    - Warlock: NOT counted (uses Pact Magic separately)
    
    Returns the effective caster level for the full caster spell slot table.
    """
    total = 0
    
    for char_class, level in class_levels:
        if char_class in FULL_CASTER_CLASSES:
            total += level
        elif char_class in HALF_CASTER_CLASSES:
            # Half casters: round up (e.g., level 1 = 1, level 2 = 1, level 3 = 2)
            total += (level + 1) // 2
        # Warlock is not counted for multiclass spell slots
    
    return min(total, 20)  # Cap at 20


def get_max_spell_slots(class_levels: List[Tuple[CharacterClass, int]]) -> Dict[int, int]:
    """
    Get the maximum spell slots for each spell level based on class levels.
    
    Returns a dict of {spell_level: max_slots} for levels 1-9.
    Warlock slots are handled separately.
    """
    caster_level = calculate_multiclass_caster_level(class_levels)
    
    if caster_level == 0:
        return {}
    
    return FULL_CASTER_SLOTS.get(caster_level, {}).copy()


def get_warlock_level(class_levels: List[Tuple[CharacterClass, int]]) -> int:
    """Get the warlock level from class levels, or 0 if not a warlock."""
    for char_class, level in class_levels:
        if char_class == CharacterClass.WARLOCK:
            return level
    return 0


def get_warlock_pact_slots(warlock_level: int) -> Tuple[int, int]:
    """
    Get warlock pact magic slots.
    
    Returns (num_slots, slot_level) or (0, 0) if not a warlock.
    """
    if warlock_level <= 0:
        return (0, 0)
    return WARLOCK_PACT_SLOTS.get(min(warlock_level, 20), (0, 0))


def get_warlock_mystic_arcanum_levels(warlock_level: int) -> List[int]:
    """
    Get the spell levels for which the warlock has Mystic Arcanum.
    
    Returns a list of spell levels (6, 7, 8, 9) that the warlock can use.
    """
    arcanum_levels = []
    for required_level, spell_level in WARLOCK_MYSTIC_ARCANUM.items():
        if warlock_level >= required_level:
            arcanum_levels.append(spell_level)
    return arcanum_levels


def is_multiclass_caster(class_levels: List[Tuple[CharacterClass, int]]) -> bool:
    """Check if the character has multiple spellcasting classes."""
    caster_count = 0
    for char_class, level in class_levels:
        if char_class in FULL_CASTER_CLASSES or char_class in HALF_CASTER_CLASSES:
            caster_count += 1
    
    # Check if warlock + another caster
    warlock_level = get_warlock_level(class_levels)
    if warlock_level > 0 and caster_count > 0:
        return True
    
    return caster_count > 1


# Cantrips known by class and level
# Format: {class: {level: num_cantrips}}
CANTRIPS_BY_CLASS = {
    CharacterClass.ARTIFICER: {
        1: 2, 10: 3, 14: 4
    },
    CharacterClass.BARD: {
        1: 2, 4: 3, 10: 4
    },
    CharacterClass.CLERIC: {
        1: 3, 4: 4, 10: 5
    },
    CharacterClass.CUSTOM: {},  # Custom class uses character-specific settings
    CharacterClass.DRUID: {
        1: 2, 4: 3, 10: 4
    },
    CharacterClass.SORCERER: {
        1: 4, 4: 5, 10: 6
    },
    CharacterClass.WARLOCK: {
        1: 2, 4: 3, 10: 4
    },
    CharacterClass.WIZARD: {
        1: 3, 4: 4, 10: 5
    },
    # Paladin and Ranger don't get cantrips
    CharacterClass.PALADIN: {},
    CharacterClass.RANGER: {},
}


def get_cantrips_for_class(char_class: CharacterClass, level: int) -> int:
    """Get the number of cantrips known for a class at a given level."""
    class_cantrips = CANTRIPS_BY_CLASS.get(char_class, {})
    if not class_cantrips:
        return 0
    
    # Find the highest threshold that applies
    cantrips = 0
    for threshold_level, num_cantrips in sorted(class_cantrips.items()):
        if level >= threshold_level:
            cantrips = num_cantrips
    
    return cantrips


def get_max_cantrips(class_levels: List[Tuple[CharacterClass, int]]) -> int:
    """
    Get the maximum number of cantrips for a character.
    Multiclass characters get cantrips from ALL their classes combined.
    """
    total_cantrips = 0
    for char_class, level in class_levels:
        total_cantrips += get_cantrips_for_class(char_class, level)
    return total_cantrips


def get_max_spell_level(class_levels: List[Tuple[CharacterClass, int]]) -> int:
    """
    Get the maximum spell level the character can cast.
    Considers both regular spell slots and warlock pact magic/mystic arcanum.
    """
    max_level = 0
    
    # Check regular spell slots
    spell_slots = get_max_spell_slots(class_levels)
    if spell_slots:
        max_level = max(spell_slots.keys())
    
    # Check warlock pact magic
    warlock_level = get_warlock_level(class_levels)
    if warlock_level > 0:
        _, slot_level = get_warlock_pact_slots(warlock_level)
        max_level = max(max_level, slot_level)
        
        # Check mystic arcanum
        arcanum_levels = get_warlock_mystic_arcanum_levels(warlock_level)
        if arcanum_levels:
            max_level = max(max_level, max(arcanum_levels))
    
    return max_level


def get_character_classes(class_levels: List[Tuple[CharacterClass, int]]) -> List[CharacterClass]:
    """Get list of character classes from class levels."""
    return [char_class for char_class, _ in class_levels]

