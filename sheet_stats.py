"""
Where a character sheet's front-page numbers come from (no UI).

Armor Class, hit point maximum and initiative are worked out from the character - armor, ability scores, class levels -
*plus* whatever a magic item or a feature says it adds: a Ring of Protection's +1 to AC, the Defense fighting style, the
Tough feat, Dwarven Toughness, Alert's bonus to initiative. Each ``auto_*`` function returns the number together with the
list of its parts, so the sheet can say "10 base, +3 Dexterity, +1 Ring of Protection" when you hover it, and can show
the automatic number next to one that was set by hand.

Features and items are read from their text (the same way the Dice Analyzer reads magic items), so homebrew content
that says "you gain a +1 bonus to AC" works too. Only plain, always-on statements count: anything that needs a reaction,
lasts "until" something, or only applies while raging, in a spell and so on is left alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from character_sheet import AbilityScore, ArmorType, calculate_hp_maximum, calculate_ac

ABILITY_ENUM = {"strength": AbilityScore.STRENGTH, "dexterity": AbilityScore.DEXTERITY,
                "constitution": AbilityScore.CONSTITUTION, "intelligence": AbilityScore.INTELLIGENCE,
                "wisdom": AbilityScore.WISDOM, "charisma": AbilityScore.CHARISMA}

# the keys of CharacterSheet.stat_overrides
AC, HP_MAX, INITIATIVE = "armor_class", "hp_max", "initiative"


def spell_key(kind: str, ability: str) -> str:
    """'spell_attack:INT' / 'spell_dc:WIS'."""
    return f"{kind}:{ability}"


@dataclass
class Bonus:
    stat: str                      # AC | HP_MAX | INITIATIVE
    amount: int
    source: str                    # "Ring of Protection", "Alert", "Fighter: Fighting Style"
    counted: bool = True
    reason: str = ""               # why it is not counted ("not attuned", "needs armor")


@dataclass
class AutoStat:
    """A worked-out number and what it is made of."""
    value: int
    parts: List[Tuple[int, str]] = field(default_factory=list)       # (amount, label), in the order they add up
    notes: List[str] = field(default_factory=list)                   # things found but not counted

    def explain(self, lead: str = "") -> str:
        bits = []
        for i, (amount, label) in enumerate(self.parts):
            bits.append(f"{amount} {label}" if i == 0 else f"{'+' if amount >= 0 else '-'}{abs(amount)} {label}")
        text = ", ".join(bits)
        return (f"{lead}{text}" if lead else text) + "".join(f"\n{n}" for n in self.notes)


def set_override(sheet, key: str, text: str, auto: int) -> Optional[int]:
    """Record what the player typed in a box. An empty box, or the number the rules give anyway, means "automatic"
    (the override is removed); anything else is a manual setting. Returns the override, or None for automatic.
    Raises ValueError if the text is not a whole number."""
    text = (text or "").strip().replace("\u2212", "-")
    overrides = sheet.stat_overrides
    if not text:
        overrides.pop(key, None)
        return None
    try:
        value = int(text.replace(" ", ""))
    except ValueError:
        raise ValueError(f"'{text}' is not a whole number.")
    if value == auto:
        overrides.pop(key, None)
        return None
    overrides[key] = value
    return value


def manual_tip(auto_text: str) -> str:
    """What a box says when its number was typed in by hand."""
    return f"Manually set\nAuto detection: {auto_text}\n(Clear the box to go back to automatic.)"


# --------------------------------------------------------------------------- reading text

_LINK = re.compile(r"\[\[[a-z_]+:([^\]|]+)(\|([^\]]*))?\]\]")
# a sentence with one of these describes something temporary, conditional on an action, or an effect on someone else
_CONDITIONAL = re.compile(
    r"\b(reaction|until|for 1 minute|for the duration|for up to|bonus action|as an action|rag(?:e|ing)|"
    r"bladesong|wild shape|concentration|when you cast|spell slot|ally|allies|each creature|a creature|the target|"
    r"temporary|on a hit|when you hit|once per|per turn|short rest|long rest|you can use|you can expend|transfer|"
    r"shift\w*|astral|manifest\w*|steel defender|companion|familiar|in each hand|for example|(?:wielding|holding) (?:a|an|two|one)\b(?! shield))\b", re.I)


def _sentences(text: str) -> List[str]:
    cleaned = _LINK.sub(lambda m: m.group(3) or m.group(1), text or "")
    cleaned = cleaned.replace("*", "")
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned) if s.strip()]


_AC_PATTERNS = [
    re.compile(r"\+(\d+)\s+bonus to (?:your )?(?:AC|Armor Class)\b", re.I),
    re.compile(r"(?:AC|Armor Class) (?:increases?|is increased) by (\d+)\b", re.I),
    re.compile(r"(?:gain|have|get) a bonus of (\d+) to (?:your )?(?:AC|Armor Class)\b", re.I),
]
_INIT_PATTERNS = [
    re.compile(r"\+(\d+)\s+bonus to (?:your )?initiative\b", re.I),
    re.compile(r"bonus to (?:your )?initiative (?:rolls? )?(?:of|equal to) \+?(\d+)\b", re.I),
    re.compile(r"(?:gain|have|get) a \+?(\d+) (?:bonus )?to (?:your )?initiative\b", re.I),
]
_INIT_ADD = re.compile(r"add (?:your )?(proficiency bonus|(strength|dexterity|constitution|intelligence|wisdom|charisma) "
                       r"modifier) to (?:your )?(?:initiative|the roll)", re.I)
_HP_PER_LEVEL = re.compile(r"hit point maximum (?:increases?|is increased) by (?:an amount equal to )?(twice )?your "
                           r"(?:character |class |total )?level", re.I)
_HP_FIRST_THEN = re.compile(r"hit point maximum (?:increases?|is increased) by (\d+),? and (?:it )?increases? by "
                            r"(\d+) (?:again )?(?:every time|whenever|each time) you gain a level", re.I)
_HP_PER_EACH_LEVEL = re.compile(r"hit point maximum (?:increases?|is increased) by (\d+) for each level", re.I)
_HP_FLAT = re.compile(r"hit point maximum (?:increases?|is increased) by (\d+)\b(?!,? and)", re.I)


def _armor_condition(sentence: str) -> str:
    """'armored' / 'unarmored' / 'shield' / 'no_shield' / '' - what the sentence needs the character to be wearing."""
    low = sentence.lower()
    conditions = []
    if re.search(r"(?:not wearing|wearing no|without|no) armor|unarmored", low):
        conditions.append("unarmored")
    elif re.search(r"wearing[^.]*armor|wearing (?:light|medium|heavy)|this armor", low):
        conditions.append("armored")
    if re.search(r"(?:using|wielding|with) no shield|without a shield|no shield", low):
        conditions.append("no_shield")
    elif re.search(r"(?:wielding|using|holding) (?:this |a )?shield", low):
        conditions.append("shield")
    return ",".join(conditions)


def read_bonuses(text: str, *, source: str, level: int = 1, prof: int = 2,
                 mods: Optional[Dict[str, int]] = None, skip_tough: bool = False) -> List[Tuple[str, int, str]]:
    """(stat, amount, condition) for each plain bonus to AC, hit point maximum or initiative in ``text``."""
    mods = mods or {}
    found: List[Tuple[str, int, str]] = []
    for s in _sentences(text):
        if _CONDITIONAL.search(s) and not re.search(r"\binitiative\b", s, re.I):
            # "when you roll Initiative, you can add your Proficiency Bonus" is the one conditional wording that is
            # really a standing bonus (Alert); everything else with these words is temporary
            continue
        for pat in _AC_PATTERNS:
            m = pat.search(s)
            if m:
                found.append((AC, int(m.group(1)), _armor_condition(s)))
                break
        for pat in _INIT_PATTERNS:
            m = pat.search(s)
            if m:
                found.append((INITIATIVE, int(m.group(1)), ""))
                break
        else:
            m = _INIT_ADD.search(s)
            if m and re.search(r"\binitiative\b", s, re.I) and not re.search(r"\b(advantage|reroll|1d|d4|d6)\b", s, re.I):
                if m.group(1).lower() == "proficiency bonus":
                    found.append((INITIATIVE, prof, ""))
                else:
                    found.append((INITIATIVE, mods.get(m.group(2).lower()[:3].upper(), 0), ""))
        m = _HP_FIRST_THEN.search(s)
        if m:
            found.append((HP_MAX, int(m.group(1)) + int(m.group(2)) * max(0, level - 1), ""))
            continue
        m = _HP_PER_EACH_LEVEL.search(s)
        if m:
            found.append((HP_MAX, int(m.group(1)) * level, ""))
            continue
        m = _HP_PER_LEVEL.search(s)
        if m:
            if not skip_tough:
                found.append((HP_MAX, (2 if m.group(1) else 1) * level, ""))
            continue
        m = _HP_FLAT.search(s)
        if m:
            found.append((HP_MAX, int(m.group(1)), ""))
    return found


# --------------------------------------------------------------------------- what a character has

def _strip_legacy(name: str) -> str:
    from legacy_content import strip_legacy_suffix
    return strip_legacy_suffix(name or "")


def _mods(sheet) -> Dict[str, int]:
    return {a[:3].upper(): sheet.ability_scores.modifier(e) for a, e in ABILITY_ENUM.items()}


def _sources(character, sheet, lookups) -> List[Tuple[str, str, int, bool]]:
    """(label, text, level the numbers scale with, is a feat) for every feature, feat and species trait."""
    out: List[Tuple[str, str, int, bool]] = []
    total = sum(cl.level for cl in character.classes) or 1
    for cl in character.classes:
        class_def = lookups.class_def(cl.get_class_name())
        if class_def is None:
            continue
        for level in sorted(class_def.levels):
            if level > cl.level:
                continue
            for ab in class_def.levels[level].abilities:
                if not ab.is_subclass_feature and ab.description:
                    out.append((f"{ab.title}", ab.description, cl.level, False))
        sub = _strip_legacy(getattr(cl, "subclass", "") or "").lower()
        if sub:
            for s in getattr(class_def, "subclasses", []) or []:
                if _strip_legacy(s.name).lower() == sub:
                    for f in s.features:
                        if f.level <= cl.level and f.description:
                            out.append((f.title, f.description, cl.level, False))
    for name in getattr(character, "feats", []) or []:
        feat = lookups.feat(name)
        if feat is not None and getattr(feat, "description", ""):
            out.append((_strip_legacy(name), feat.description, total, True))
    lineage = lookups.lineage(getattr(character, "lineage", "") or "") if getattr(character, "lineage", "") else None
    if lineage is not None:
        for t in getattr(lineage, "traits", []) or []:
            if t.description:
                out.append((t.name, t.description, total, False))
    return out


def find_bonuses(character, sheet, lookups) -> List[Bonus]:
    """Every bonus to AC, hit point maximum and initiative the character gets from magic items and features."""
    from item_effects import parse_item
    prof, mods = sheet.proficiency_bonus, _mods(sheet)
    armored = ArmorType.from_name(sheet.armor_type) != ArmorType.NONE
    shield = bool(getattr(sheet, "shield_bonus", 0)) or bool(getattr(sheet, "has_shield", False))
    bonuses: List[Bonus] = []
    total_level = sum(cl.level for cl in character.classes) or 1

    def condition_ok(cond: str) -> str:
        """'' if the condition holds, else why not."""
        for c in filter(None, cond.split(",")):
            if c == "armored" and not armored:
                return "needs armor"
            if c == "unarmored" and armored:
                return "only while wearing no armor"
            if c == "shield" and not shield:
                return "needs a shield"
            if c == "no_shield" and shield:
                return "only while using no shield"
        return ""

    for entry in getattr(sheet, "magic_items", None) or []:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        magic = lookups.magic_item(entry["name"])
        info = parse_item(entry, magic)
        text = getattr(magic, "description", "") or entry.get("description", "") or ""
        for stat, amount, cond in read_bonuses(text, source=info.name, level=total_level, prof=prof, mods=mods):
            why = "" if info.usable else (info.reason or "not usable")
            why = why or condition_ok(cond)
            bonuses.append(Bonus(stat, amount, info.name, counted=not why, reason=why))
    for label, text, level, is_feat in _sources(character, sheet, lookups):
        for stat, amount, cond in read_bonuses(text, source=label, level=level, prof=prof, mods=mods,
                                               skip_tough=is_feat and label.lower() == "tough"):
            why = condition_ok(cond)
            bonuses.append(Bonus(stat, amount, label, counted=not why, reason=why))
        if label.lower() in ("jack of all trades", "remarkable athlete") and prof // 2:
            bonuses.append(Bonus(INITIATIVE, prof // 2, label))
    seen, unique = set(), []
    for b in bonuses:
        key = (b.stat, b.amount, b.source)
        if key not in seen:
            seen.add(key)
            unique.append(b)
    return unique


def _apply(stat: AutoStat, bonuses: List[Bonus], which: str) -> None:
    for b in bonuses:
        if b.stat != which or not b.amount:
            continue
        if b.counted:
            stat.parts.append((b.amount, b.source))
            stat.value += b.amount
        else:
            stat.notes.append(f"{b.source}: {b.amount:+d} (not counted: {b.reason})")


# --------------------------------------------------------------------------- the numbers

def auto_ac(character, sheet, lookups, bonuses: Optional[List[Bonus]] = None) -> AutoStat:
    armor = ArmorType.from_name(sheet.armor_type)
    scores = sheet.ability_scores
    dex, con = scores.modifier(AbilityScore.DEXTERITY), scores.modifier(AbilityScore.CONSTITUTION)
    wis, cha = scores.modifier(AbilityScore.WISDOM), scores.modifier(AbilityScore.CHARISMA)
    shield = sheet.shield_bonus if hasattr(sheet, "shield_bonus") else (2 if sheet.has_shield else 0)
    base = calculate_ac(armor_type=armor, dex_modifier=dex, has_shield=False, unarmored_defense=sheet.unarmored_defense,
                        con_modifier=con, wis_modifier=wis, cha_modifier=cha, shield_bonus=shield)
    stat = AutoStat(base)
    ud = sheet.unarmored_defense or ""
    if armor == ArmorType.NONE:
        if ud and "DEX + CON" in ud:
            stat.parts = [(10, "base"), (dex, "Dexterity"), (con, "Constitution (unarmored defense)")]
        elif ud and "DEX + WIS" in ud:
            stat.parts = [(10, "base"), (dex, "Dexterity"), (wis, "Wisdom (unarmored defense)")]
        elif ud and "DEX + CHA" in ud:
            stat.parts = [(10, "base"), (dex, "Dexterity"), (cha, "Charisma (unarmored defense)")]
        else:
            stat.parts = [(10, "base"), (dex, "Dexterity")]
    else:
        parts = [(armor.base_ac, armor.display_name)]
        if armor.adds_dex:
            capped = dex if armor.max_dex_bonus is None else min(dex, armor.max_dex_bonus)
            parts.append((capped, "Dexterity" + (f" (capped at +{armor.max_dex_bonus})"
                                                  if armor.max_dex_bonus is not None and dex > armor.max_dex_bonus else "")))
        stat.parts = parts
    if shield > 0:
        stat.parts.append((shield, "shield"))
    _apply(stat, bonuses if bonuses is not None else find_bonuses(character, sheet, lookups), AC)
    return stat


def auto_initiative(character, sheet, lookups, bonuses: Optional[List[Bonus]] = None) -> AutoStat:
    dex = sheet.ability_scores.modifier(AbilityScore.DEXTERITY)
    stat = AutoStat(dex, [(dex, "Dexterity")])
    if sheet.initiative_bonus:
        stat.parts.append((sheet.initiative_bonus, "bonus entered on the sheet"))
        stat.value += sheet.initiative_bonus
    _apply(stat, bonuses if bonuses is not None else find_bonuses(character, sheet, lookups), INITIATIVE)
    return stat


def auto_hp_max(character, sheet, lookups, bonuses: Optional[List[Bonus]] = None) -> AutoStat:
    class_levels = [(cl.get_class_name(), cl.level) for cl in character.classes]
    con = sheet.get_effective_ability_modifier(AbilityScore.CONSTITUTION, max_score=25)
    feats = list(getattr(character, "feats", []) or [])
    base = calculate_hp_maximum(class_levels, con, [f for f in feats if f.lower() != "tough"])
    stat = AutoStat(base, [(base, f"from class levels and Constitution ({con:+d} per level)")])
    if any(f.lower() == "tough" for f in feats):
        extra = 2 * (sum(l for _n, l in class_levels) or 1)
        stat.parts.append((extra, "Tough (+2 per level)"))
        stat.value += extra
    _apply(stat, bonuses if bonuses is not None else find_bonuses(character, sheet, lookups), HP_MAX)
    return stat


def initiative_extra(character, sheet, lookups, bonuses: Optional[List[Bonus]] = None) -> int:
    """What items and features add to initiative on top of Dexterity and the sheet's own bonus."""
    bonuses = bonuses if bonuses is not None else find_bonuses(character, sheet, lookups)
    return sum(b.amount for b in bonuses if b.stat == INITIATIVE and b.counted)


def tooltip_for(auto_text: str, auto_stat: Optional[AutoStat], overridden: bool, lead: str) -> str:
    """The hover text of a box: how the number is made, or - if it was typed in - that, and what it would be."""
    if overridden:
        return manual_tip(auto_text)
    if auto_stat is None:
        return lead
    return f"{lead}\n{auto_stat.explain()}" if lead else auto_stat.explain()
