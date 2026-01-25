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

# Eldritch Knight spell slots by Fighter level (third caster)
# Format: {fighter_level: {spell_level: num_slots}}
ELDRITCH_KNIGHT_SLOTS = {
    3:  {1: 2},
    4:  {1: 3},
    5:  {1: 3},
    6:  {1: 3},
    7:  {1: 4, 2: 2},
    8:  {1: 4, 2: 2},
    9:  {1: 4, 2: 2},
    10: {1: 4, 2: 3},
    11: {1: 4, 2: 3},
    12: {1: 4, 2: 3},
    13: {1: 4, 2: 3, 3: 2},
    14: {1: 4, 2: 3, 3: 2},
    15: {1: 4, 2: 3, 3: 2},
    16: {1: 4, 2: 3, 3: 3},
    17: {1: 4, 2: 3, 3: 3},
    18: {1: 4, 2: 3, 3: 3},
    19: {1: 4, 2: 3, 3: 3, 4: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 1},
}

# Eldritch Knight prepared spells by Fighter level
ELDRITCH_KNIGHT_PREPARED = {
    3: 3, 4: 4, 5: 4, 6: 4, 7: 5, 8: 6, 9: 6, 10: 7,
    11: 8, 12: 8, 13: 9, 14: 10, 15: 10, 16: 11, 17: 11, 18: 11, 19: 12, 20: 13
}

# Eldritch Knight cantrips by Fighter level
ELDRITCH_KNIGHT_CANTRIPS = {
    3: 2, 10: 3  # 2 cantrips at level 3, 3 at level 10
}

# Custom class is handled separately with user-defined spell slots


def calculate_multiclass_caster_level(class_levels: List[Tuple[CharacterClass, int]], eldritch_knight_level: int = 0) -> int:
    """
    Calculate the effective caster level for multiclass spell slot calculation.
    
    - Full casters: count full levels
    - Half casters: count half levels (round up)
    - Third casters (Eldritch Knight): count third levels (round up)
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
        # Warlock and Fighter (not EK) are not counted for multiclass spell slots
    
    # Add Eldritch Knight contribution (third caster)
    if eldritch_knight_level >= 3:
        # Third casters: round up (level 3 = 1, level 6 = 2, level 9 = 3, etc.)
        total += (eldritch_knight_level + 2) // 3
    
    return min(total, 20)  # Cap at 20


def get_max_spell_slots(class_levels: List[Tuple[CharacterClass, int]], eldritch_knight_level: int = 0) -> Dict[int, int]:
    """
    Get the maximum spell slots for each spell level based on class levels.
    
    Returns a dict of {spell_level: max_slots} for levels 1-9.
    Warlock slots are handled separately.
    
    Args:
        class_levels: List of (class, level) tuples
        eldritch_knight_level: Fighter level if character has Eldritch Knight subclass
    """
    caster_level = calculate_multiclass_caster_level(class_levels, eldritch_knight_level)
    
    if caster_level == 0:
        # Check if only Eldritch Knight (no other casters)
        if eldritch_knight_level >= 3:
            return ELDRITCH_KNIGHT_SLOTS.get(eldritch_knight_level, {}).copy()
        return {}
    
    return FULL_CASTER_SLOTS.get(caster_level, {}).copy()


def get_eldritch_knight_slots(fighter_level: int) -> Dict[int, int]:
    """Get spell slots for Eldritch Knight at a given Fighter level."""
    if fighter_level < 3:
        return {}
    return ELDRITCH_KNIGHT_SLOTS.get(min(fighter_level, 20), {}).copy()


def get_eldritch_knight_prepared(fighter_level: int) -> int:
    """Get max prepared spells for Eldritch Knight at a given Fighter level."""
    if fighter_level < 3:
        return 0
    return ELDRITCH_KNIGHT_PREPARED.get(min(fighter_level, 20), 0)


def get_eldritch_knight_cantrips(fighter_level: int) -> int:
    """Get number of cantrips for Eldritch Knight at a given Fighter level."""
    if fighter_level < 3:
        return 0
    cantrips = 0
    for threshold_level, num_cantrips in sorted(ELDRITCH_KNIGHT_CANTRIPS.items()):
        if fighter_level >= threshold_level:
            cantrips = num_cantrips
    return cantrips


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


def get_max_cantrips(class_levels: List[Tuple[CharacterClass, int]], eldritch_knight_level: int = 0) -> int:
    """
    Get the maximum number of cantrips for a character.
    Multiclass characters get cantrips from ALL their classes combined.
    """
    total_cantrips = 0
    for char_class, level in class_levels:
        total_cantrips += get_cantrips_for_class(char_class, level)
    
    # Add Eldritch Knight cantrips
    if eldritch_knight_level >= 3:
        total_cantrips += get_eldritch_knight_cantrips(eldritch_knight_level)
    
    return total_cantrips


def get_max_spell_level(class_levels: List[Tuple[CharacterClass, int]], eldritch_knight_level: int = 0) -> int:
    """
    Get the maximum spell level the character can cast.
    Considers both regular spell slots and warlock pact magic/mystic arcanum.
    """
    max_level = 0
    
    # Check regular spell slots (including Eldritch Knight)
    spell_slots = get_max_spell_slots(class_levels, eldritch_knight_level)
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

