"""
Spell validation utilities for D&D Spellbook Application.
Shared validation logic for spell compatibility checks.
"""

from typing import List, Optional
from spell import Spell, CharacterClass
from spell_slots import (
    get_max_cantrips, get_max_spell_level, get_character_classes
)


def validate_spell_for_character(
    spell: Spell,
    character,  # CharacterSpellList
    spell_manager=None,
    settings=None
) -> List[str]:
    """
    Validate if a spell is appropriate for a character.
    
    Args:
        spell: The spell to validate
        character: The CharacterSpellList to validate against
        spell_manager: Optional SpellManager for counting cantrips
        settings: Optional AppSettings to check which warnings to show
    
    Returns:
        A list of warning messages (empty if no issues)
    """
    warnings = []
    class_levels = character.get_class_levels_tuple()
    
    # Get Eldritch Knight level for spell slot and cantrip calculations
    ek_level = character.get_eldritch_knight_level()
    
    # Check if character has Custom class - skip class-related warnings
    has_custom_class = character.has_custom_class
    
    # Determine which checks to perform based on settings
    warn_wrong_class = True
    warn_spell_too_high_level = True
    warn_too_many_cantrips = True
    
    if settings is not None:
        warn_wrong_class = settings.warn_wrong_class
        warn_spell_too_high_level = settings.warn_spell_too_high_level
        warn_too_many_cantrips = settings.warn_too_many_cantrips
    
    # Check 1: Class compatibility (skip for Custom class)
    if warn_wrong_class and not has_custom_class:
        char_classes = get_character_classes(class_levels)
        spell_classes = spell.classes
        
        # Check for Eldritch Knight Fighter subclass - can cast Wizard spells
        has_eldritch_knight = character.has_eldritch_knight()
        
        # Check for Bard's Magical Secrets (level 10+)
        # Disables ALL class warnings - Bard can learn spells from any class
        has_magical_secrets = False
        for char_class, level in class_levels:
            if char_class == CharacterClass.BARD and level >= 10:
                has_magical_secrets = True
                break
        
        # Check for Bard subclass features that allow cross-class spells
        # College of Lore's Magical Discoveries (level 6+) - allows Cleric/Druid/Wizard spells
        # College of the Moon's Primal Lore (level 3+) - allows Druid spells
        has_magical_discoveries = False
        has_primal_lore = False
        for char_class, level in class_levels:
            if char_class == CharacterClass.BARD:
                # Get subclass from character
                for cl in character.classes:
                    if cl.character_class == CharacterClass.BARD:
                        if cl.subclass == "College of Lore" and level >= 6:
                            has_magical_discoveries = True
                        elif cl.subclass == "College of the Moon" and level >= 3:
                            has_primal_lore = True
                        break
        
        # Magical Secrets disables all class warnings
        if has_magical_secrets:
            pass  # Skip all class warnings
        # Eldritch Knight allows Wizard spells
        elif has_eldritch_knight:
            if CharacterClass.WIZARD in spell_classes:
                pass  # Eldritch Knight can cast Wizard spells
            elif not any(c in char_classes for c in spell_classes):
                class_names = ", ".join(c.value for c in spell_classes)
                char_class_names = ", ".join(c.value for c in char_classes)
                warnings.append(
                    f"This spell is for {class_names}, but this character is a {char_class_names}."
                )
        # Magical Discoveries allows Cleric/Druid/Wizard spells
        elif has_magical_discoveries:
            magical_discoveries_classes = {CharacterClass.CLERIC, CharacterClass.DRUID, CharacterClass.WIZARD}
            if any(c in magical_discoveries_classes for c in spell_classes):
                pass  # Magical Discoveries allows these spells
            elif not any(c in char_classes for c in spell_classes):
                class_names = ", ".join(c.value for c in spell_classes)
                char_class_names = ", ".join(c.value for c in char_classes)
                warnings.append(
                    f"This spell is for {class_names}, but this character is a {char_class_names}."
                )
        # Primal Lore allows Druid spells
        elif has_primal_lore:
            if CharacterClass.DRUID in spell_classes:
                pass  # Primal Lore allows Druid spells
            elif not any(c in char_classes for c in spell_classes):
                class_names = ", ".join(c.value for c in spell_classes)
                char_class_names = ", ".join(c.value for c in char_classes)
                warnings.append(
                    f"This spell is for {class_names}, but this character is a {char_class_names}."
                )
        elif not any(c in char_classes for c in spell_classes):
            class_names = ", ".join(c.value for c in spell_classes)
            char_class_names = ", ".join(c.value for c in char_classes)
            warnings.append(
                f"This spell is for {class_names}, but this character is a {char_class_names}."
            )
    
    # Check 2: Spell level too high (use custom_max_slots for Custom class)
    if warn_spell_too_high_level and spell.level > 0:  # Not a cantrip
        if has_custom_class and character.custom_max_slots:
            # Use custom max spell level
            max_level = max(character.custom_max_slots.keys()) if character.custom_max_slots else 0
        else:
            max_level = get_max_spell_level(class_levels, ek_level)
        
        if spell.level > max_level:
            if max_level == 0:
                warnings.append(
                    f"This is a level {spell.level} spell, but this character "
                    f"cannot cast any leveled spells yet."
                )
            else:
                warnings.append(
                    f"This is a level {spell.level} spell, but this character "
                    f"can only cast spells up to level {max_level}."
                )
    
    # Check 3: Too many cantrips (use custom_max_cantrips for Custom class)
    if warn_too_many_cantrips and spell.level == 0:  # Cantrip
        if has_custom_class:
            # Use custom max cantrips
            max_cantrips = character.custom_max_cantrips
        else:
            max_cantrips = get_max_cantrips(class_levels, ek_level)
        
        if max_cantrips == 0 and not has_custom_class:
            # Only warn if not a custom class (custom class with 0 means unlimited)
            warnings.append(
                f"This is a cantrip, but this character's class(es) "
                f"cannot learn cantrips."
            )
        elif spell_manager is not None and max_cantrips > 0:
            # Count current cantrips (excluding class feature spells like Mending for Artificer)
            class_feature_spells = getattr(character, 'class_feature_spells', [])
            current_cantrips = 0
            for known_spell_name in character.known_spells:
                # Don't count class feature spells against the limit
                if known_spell_name in class_feature_spells:
                    continue
                known_spell = spell_manager.get_spell(known_spell_name)
                if known_spell and known_spell.level == 0:
                    current_cantrips += 1
            
            if current_cantrips >= max_cantrips:
                warnings.append(
                    f"This character already knows {current_cantrips} cantrip(s), "
                    f"which is the maximum ({max_cantrips}) for their class(es) and level."
                )
    
    return warnings

