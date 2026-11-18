"""
Which spells a character can learn.

``learn_rules`` reads a character (classes, subclasses, feats, species) and answers "may this spell be added to
their spell list?": the spell must be on the spell list of one of the character's classes (plus the lists some
features open up) and be of a level the character can cast. Warlock patrons and species with a "Spells of the
Mark" trait add spells to the class's list, which is why they count here.

Pure logic: the managers are passed in or found lazily, nothing here draws anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from legacy_content import strip_legacy_suffix
from spell import CharacterClass

_LINK = re.compile(r"\[\[spell:([^\]|]+)(?:\|[^\]]*)?\]\]")
_EXPANDS = re.compile(r"(added to (?:the|that|your|this)[^.]{0,80}spell list|expanded (?:list of )?spells?)", re.I)
_ORDINAL = re.compile(r"^\d+(?:st|nd|rd|th)$", re.I)


def _names_in(text: str) -> Set[str]:
    return {m.strip().lower() for m in _LINK.findall(text or "")}


def _names_in_tables(tables) -> Set[str]:
    """Spell names in a feature's tables: their cells hold plain names, several to a cell."""
    found: Set[str] = set()
    for table in tables or []:
        for row in table.get("rows", []) if isinstance(table, dict) else []:
            for cell in row:
                text = str(cell)
                found |= _names_in(text)
                if "[[" in text:
                    continue
                for part in text.split(","):
                    part = part.strip()
                    if part and not _ORDINAL.match(part) and not part.isdigit():
                        found.add(part.lower())
    return found


def expanding_text(text: str) -> bool:
    """True when a description says some spells are added to the character's spell list."""
    return bool(_EXPANDS.search(text or ""))


@dataclass
class LearnRules:
    """What a character may learn: ``allows(spell)``."""
    classes: Set[str] = field(default_factory=set)         # lower-case class names whose spell lists count
    any_class: bool = False                                # a Custom class (or Magical Secrets): any list
    max_level: int = 0                                     # highest level of spell the character can cast
    expanded: Set[str] = field(default_factory=set)        # lower-case names of spells added to the lists
    class_labels: List[str] = field(default_factory=list)  # for messages
    # lower-case spell list -> highest level that list's class can prepare on its own. A multiclass character
    # prepares each class's spells as if they had that class alone: a Wizard 3 / Cleric 3 has 3rd-level slots
    # but prepares spells of 2nd level at most. Empty: only ``max_level`` counts.
    list_levels: Dict[str, int] = field(default_factory=dict)

    def class_ok(self, spell) -> bool:
        if self.any_class or spell.name.lower() in self.expanded:
            return True
        names = {strip_legacy_suffix(c).strip().lower() for c in spell.get_class_names()}
        return bool(names & self.classes)

    def level_limit(self, spell) -> int:
        """The highest level this spell could have for the character to prepare it (from the lists it is on)."""
        if self.any_class or not self.list_levels or spell.name.lower() in self.expanded:
            return self.max_level
        names = {strip_legacy_suffix(c).strip().lower() for c in spell.get_class_names()}
        levels = [self.list_levels[n] for n in names if n in self.list_levels]
        return min(self.max_level, max(levels)) if levels else self.max_level

    def level_ok(self, spell) -> bool:
        return spell.level == 0 or spell.level <= self.level_limit(spell)

    def allows(self, spell) -> bool:
        return self.class_ok(spell) and self.level_ok(spell)

    def why_not(self, spell) -> str:
        if not self.class_ok(spell):
            return "not on " + (" / ".join(self.class_labels) or "the character's") + " spell list"
        if not self.level_ok(spell):
            limit = self.level_limit(spell)
            if limit < self.max_level:
                return (f"level {spell.level} is above what this character's classes on its list can prepare "
                        f"(up to level {limit})")
            return f"level {spell.level} is above the highest level this character can cast ({self.max_level})"
        return ""


# ----------------------------------------------------------------------------- the pieces

def _third_caster_entries(character):
    """[(class level, spell list, ability)] for third-caster subclasses, 2014 versions included."""
    from character import THIRD_CASTERS, _plain
    found = []
    for cl in character.classes:
        base = strip_legacy_suffix(cl.get_class_name()).strip().lower()
        key = (base, _plain(cl.subclass))
        if key in THIRD_CASTERS and cl.level >= 3:
            found.append((cl,) + THIRD_CASTERS[key])
    return found


def max_spell_level(character) -> int:
    """The highest spell level the character can cast (0 when they cannot cast leveled spells)."""
    from spell_slots import get_max_spell_level, ELDRITCH_KNIGHT_SLOTS
    levels = []
    for cl in character.classes:
        enum = cl.character_class
        if enum == CharacterClass.CUSTOM and cl.custom_class_name:            # "Wizard (Legacy)" casts like a Wizard
            enum = CharacterClass.from_string(strip_legacy_suffix(cl.custom_class_name))
        levels.append((enum, cl.level))
    third = max([cl.level for cl, _l, _a in _third_caster_entries(character)] or [0])
    top = get_max_spell_level(levels, third)
    if third and not top:                                                       # a third caster on their own
        slots = ELDRITCH_KNIGHT_SLOTS.get(min(third, 20), {})
        top = max(slots) if slots else 0
    custom = getattr(character, "custom_max_slots", None) or {}
    if custom:
        top = max(top, max(custom))
    return top


def class_spell_levels(character) -> Dict[str, int]:
    """{lower-case spell list: the highest spell level the class (or subclass) that casts from it gives on its
    own}, for a character with more than one spellcasting class. Empty when one class (or none) casts spells,
    as then the combined slots and the class's own are the same."""
    from spell_slots import (ELDRITCH_KNIGHT_SLOTS, get_max_spell_level, FULL_CASTER_CLASSES,
                             HALF_CASTER_CLASSES)
    levels: Dict[str, int] = {}

    def give(name: str, level: int):
        if level > 0:
            levels[name] = max(levels.get(name, 0), level)

    casters = 0
    thirds = {id(cl): (lst, cl.level) for cl, lst, _a in _third_caster_entries(character)}
    for cl in character.classes:
        enum = cl.character_class
        if enum == CharacterClass.CUSTOM and cl.custom_class_name:
            enum = CharacterClass.from_string(strip_legacy_suffix(cl.custom_class_name))
        if enum == CharacterClass.CUSTOM:
            return {}                                         # a Custom class: its own slot limits decide
        base = strip_legacy_suffix(cl.get_class_name()).strip().lower()
        sub = strip_legacy_suffix(getattr(cl, "subclass", "") or "").strip().lower()
        if id(cl) in thirds:
            spell_list, at = thirds[id(cl)]
            slots = ELDRITCH_KNIGHT_SLOTS.get(min(at, 20), {})
            give(spell_list.lower(), max(slots) if slots else 0)
            casters += 1
            continue
        if enum not in FULL_CASTER_CLASSES and enum not in HALF_CASTER_CLASSES and enum != CharacterClass.WARLOCK:
            continue
        casters += 1
        top = get_max_spell_level([(enum, cl.level)])
        give(base, top)
        if base == "bard" and (cl.level >= 10 or (sub == "college of lore" and cl.level >= 6)):
            for other in ("cleric", "druid", "wizard"):       # Magical Secrets: those lists at the Bard's level
                give(other, top)
        if base == "bard" and sub == "college of the moon" and cl.level >= 3:
            give("druid", top)
        if base == "sorcerer" and sub == "divine soul":
            give("cleric", top)
    return levels if casters > 1 else {}


def _class_lists(character) -> (Set[str], bool, List[str]):
    classes: Set[str] = set()
    labels: List[str] = []
    any_class = False
    for cl in character.classes:
        name = cl.get_class_name()
        base = strip_legacy_suffix(name).strip()
        legacy = name.strip().lower().endswith("(legacy)")
        if cl.character_class == CharacterClass.CUSTOM and not cl.custom_class_name:
            any_class = True                                                    # the "Custom" class
            continue
        classes.add(base.lower())
        labels.append(base)
        sub = strip_legacy_suffix(getattr(cl, "subclass", "") or "").strip().lower()
        if base.lower() == "bard":
            if cl.level >= 10:                                                  # Magical Secrets
                if legacy:
                    any_class = True
                else:
                    classes.update({"cleric", "druid", "wizard"})
            if sub == "college of lore" and cl.level >= 6:                      # Magical Discoveries / Additional Secrets
                if legacy:
                    any_class = True
                else:
                    classes.update({"cleric", "druid", "wizard"})
            if sub == "college of the moon" and cl.level >= 3:                  # Primal Lore
                classes.add("druid")
        if base.lower() == "sorcerer" and sub == "divine soul":                 # Divine Magic: the Cleric list too
            classes.add("cleric")
            labels.append("Cleric")
    for _cl, spell_list, _ability in _third_caster_entries(character):          # their spells come from the Wizard list
        classes.add(spell_list.lower())                                         # (the Sorcerer list for the Mystic Arts)
        labels.append(spell_list)
    return classes, any_class, labels


def expanded_spells(character, class_manager=None, feat_manager=None, lineage_manager=None) -> Set[str]:
    """Lower-case names of the spells features add to the character's spell lists: a Warlock patron's expanded
    spells, the spells of a Mark of Eberron ..."""
    from spell_grants import _managers
    class_manager, feat_manager, lineage_manager = _managers(class_manager, feat_manager, lineage_manager)
    found: Set[str] = set()
    for cl in character.classes:
        sub_name = (getattr(cl, "subclass", "") or "").strip()
        if not sub_name:
            continue
        class_def = class_manager.get_class(cl.get_class_name())
        sub = class_def.find_subclass(sub_name) if class_def else None
        if sub is None:
            continue
        is_warlock = strip_legacy_suffix(cl.get_class_name()).strip().lower() == "warlock"
        for feature in sub.features:
            if expanding_text(feature.title) or expanding_text(feature.description):
                found |= _names_in(feature.description) | _names_in_tables(feature.tables)
        if is_warlock:                                                          # patron spells open the list up
            found |= {s.spell_name.lower() for s in sub.subclass_spells}
    for feat_name in getattr(character, "feats", []) or []:
        feat = feat_manager.get_feat(feat_name) if feat_manager else None
        if feat is not None and expanding_text(feat.description):
            found |= _names_in(feat.description)
    lineage = lineage_manager.get_lineage(getattr(character, "lineage", "") or "") if lineage_manager else None
    for trait in getattr(lineage, "traits", []) or []:
        if expanding_text(trait.description):
            found |= _names_in(trait.description)
    return found


def learn_rules(character, class_manager=None, feat_manager=None, lineage_manager=None) -> LearnRules:
    """The rules for what ``character`` (a CharacterSpellList) may add to their spell list."""
    classes, any_class, labels = _class_lists(character)
    if getattr(character, "has_custom_class", False) and not classes:
        any_class = True
    max_level = max_spell_level(character)
    if any_class and not max_level:
        max_level = 9                                                           # "Custom": nothing limits it
    return LearnRules(classes, any_class, max_level,
                      expanded_spells(character, class_manager, feat_manager, lineage_manager),
                      list(dict.fromkeys(labels)), {} if any_class else class_spell_levels(character))
