"""
Utility script to normalize spell tags:
- Keep only tags that already exist in the legacy data (spells.txt), plus the allowed
  exceptions: Summon (for stat-block summons) and Temp HP (for temporary hit points).
- Remove any other tags that were introduced during recent batch imports.
- Add the Temp HP tag to any spell whose description grants temporary hit points.
"""

import os
from typing import List, Set

from spell_manager import SpellManager
from spell import Spell


def load_allowed_tags() -> Set[str]:
    """Derive the allowed tags from the legacy spells file, plus permitted exceptions."""
    base: Set[str] = set()
    legacy_path = "spells.txt"

    if os.path.exists(legacy_path):
        with open(legacy_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    spell = Spell.from_file_line(line)
                    base.update(spell.tags)
                except Exception:
                    # Skip malformed lines; the DB already holds the authoritative copy.
                    continue

    # Allowed exceptions beyond the legacy tag set.
    base.update({"Summon", "Temp HP"})
    return base


def gives_temp_hp(spell: Spell) -> bool:
    """Heuristic: detect temporary hit points mentioned in the description."""
    text = (spell.description or "").lower()
    return "temporary hit point" in text


def copy_with_tags(spell: Spell, tags: List[str]) -> Spell:
    """Create a new Spell instance with updated tags while preserving other fields."""
    return Spell(
        name=spell.name,
        level=spell.level,
        casting_time=spell.casting_time,
        ritual=spell.ritual,
        range_value=spell.range_value,
        components=spell.components,
        duration=spell.duration,
        concentration=spell.concentration,
        classes=spell.classes,
        description=spell.description,
        source=spell.source,
        tags=tags,
    )


def main():
    allowed = load_allowed_tags()

    manager = SpellManager()
    manager.load_spells()

    changed = []
    added_temp_hp = []

    for spell in manager.spells:
        # Filter tags to allowed list, preserving original order and uniqueness.
        new_tags = []
        for tag in spell.tags:
            if tag in allowed and tag not in new_tags:
                new_tags.append(tag)

        # Temp HP tagging.
        if gives_temp_hp(spell) and "Temp HP" not in new_tags:
            new_tags.append("Temp HP")
            added_temp_hp.append(spell.name)

        if new_tags != spell.tags:
            updated_spell = copy_with_tags(spell, new_tags)
            success = manager.update_spell(spell.name, updated_spell)
            if success:
                changed.append((spell.name, spell.tags, new_tags))

    print({
        "changed": len(changed),
        "temp_hp_added": added_temp_hp,
        "details": changed,
    })


if __name__ == "__main__":
    main()