"""
Homebrew roll effects: a small, structured way for a custom feat, species trait, class or subclass feature or magic item
to tell the Dice Analyzer what it does to a character's dice.

An effect is a plain dict (so it is stored with the object, exported and imported with it):

    {"affects": "skill",            # what it changes: see AFFECTS
     "limit": "Stealth, Perception",  # optional: only these skills / abilities / "concentration" / "ranged" / damage types ...
     "does": "advantage",           # what it does: see DOES
     "value": 2, "count": 1, "sides": 4,   # the numbers that go with it
     "scales": "proficiency bonus", # optional: add a number that grows with the character
     "choice": False, "default_on": False,  # a choice you switch on for the roll, instead of always applying
     "once": False,                 # damage: once per turn
     "label": ""}                   # optional name shown in the notes

``build_effects`` turns a list of them into the analyzer's own :class:`Rule` / :class:`DmgRule` objects, so a homebrew
feature works exactly like the built-in ones. ``collect`` finds the effects a character has (feats, species traits,
class and subclass features, magic items).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from roll_rules import (ADV, DIS, Eff, RESCUE_SET20, RESCUE_SUCCEED, DmgRule, Rule, die, flat, fs, minimum, reroll)

ABILITIES = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
ABILITY_WORDS = {"strength": "STR", "dexterity": "DEX", "constitution": "CON", "intelligence": "INT", "wisdom": "WIS",
                 "charisma": "CHA"}
SKILLS = ["Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception", "History", "Insight", "Intimidation",
          "Investigation", "Medicine", "Nature", "Perception", "Performance", "Persuasion", "Religion",
          "Sleight of Hand", "Stealth", "Survival"]
DAMAGE_TYPES = ["acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison", "psychic",
                "radiant", "slashing", "thunder"]
SCHOOLS = ["abjuration", "conjuration", "divination", "enchantment", "evocation", "illusion", "necromancy",
           "transmutation"]

# what an effect can change (key -> menu text)
AFFECTS: Dict[str, str] = {
    "skill": "Skill checks",
    "check": "Any ability check (skills, ability checks, initiative)",
    "initiative": "Initiative",
    "save": "Saving throws",
    "attack": "Weapon attack rolls",
    "spell": "Spell attack rolls and save DCs",
    "weapon damage": "Weapon damage",
    "spell damage": "Spell damage",
    "healing": "Healing from spells",
    "item spell attack": "Spell attack bonus (magic items)",
    "item spell dc": "Spell save DC bonus (magic items)",
    "item weapon bonus": "Bonus to attack and damage with this weapon (magic items)",
    "item set ability": "Sets an ability score (magic items)",
}
D20_AFFECTS = ("skill", "check", "initiative", "save", "attack", "spell")
DAMAGE_AFFECTS = ("weapon damage", "spell damage", "healing")
ITEM_AFFECTS = ("item spell attack", "item spell dc", "item weapon bonus", "item set ability")

# what it does (key -> menu text) and which kinds of effect it makes sense for
DOES: Dict[str, str] = {
    "advantage": "Advantage",
    "disadvantage": "Disadvantage",
    "bonus": "Add a number",
    "dice": "Add dice",
    "penalty dice": "Subtract dice",
    "minimum": "A low d20 counts as a higher number",
    "reroll": "Reroll a low d20 (once)",
    "crit": "Critical hits on a lower roll",
    "extra d20": "Roll an extra d20 and keep the best",
    "total at least": "The total counts as at least a number",
    "fail add": "If the roll fails: add dice",
    "fail reroll": "If the roll fails: reroll the d20",
    "fail succeed": "If the roll fails: it succeeds",
    "fail twenty": "If the roll fails: the d20 becomes a 20",
    "extra damage": "Extra damage / healing (dice and / or a number)",
    "set": "Sets it to a number",
}
DOES_FOR = {
    "skill": ["advantage", "disadvantage", "bonus", "dice", "penalty dice", "minimum", "reroll", "extra d20",
              "total at least", "fail add", "fail reroll", "fail succeed", "fail twenty"],
    "check": ["advantage", "disadvantage", "bonus", "dice", "penalty dice", "minimum", "reroll", "extra d20",
              "total at least", "fail add", "fail reroll", "fail succeed", "fail twenty"],
    "initiative": ["advantage", "disadvantage", "bonus", "dice", "penalty dice", "minimum", "reroll", "extra d20"],
    "save": ["advantage", "disadvantage", "bonus", "dice", "penalty dice", "minimum", "reroll", "extra d20",
             "fail add", "fail reroll", "fail succeed", "fail twenty"],
    "attack": ["advantage", "disadvantage", "bonus", "dice", "penalty dice", "minimum", "reroll", "crit", "extra d20",
               "fail add", "fail reroll", "fail succeed", "fail twenty"],
    "spell": ["advantage", "disadvantage", "bonus", "dice", "penalty dice", "extra d20", "reroll", "crit",
              "fail add", "fail reroll", "fail succeed", "fail twenty"],
    "weapon damage": ["extra damage"],
    "spell damage": ["extra damage"],
    "healing": ["extra damage"],
    "item spell attack": ["bonus"],
    "item spell dc": ["bonus"],
    "item weapon bonus": ["bonus"],
    "item set ability": ["set"],
}
SCALES = ["", "proficiency bonus", "half proficiency bonus", "character level", "half character level"] + \
         [f"{a} modifier" for a in ABILITIES] + [f"{a} modifier (min +1)" for a in ABILITIES]
LIMIT_HELP = {
    "skill": "Skills, e.g. Stealth, Perception (blank = every skill). Add 'proficient' for proficient skills only.",
    "check": "Skills or abilities, e.g. Stealth, STR (blank = every check).",
    "initiative": "",
    "save": "Abilities, 'concentration', or what it is against: charmed, frightened, poisoned, magic "
            "(blank = every save).",
    "attack": "'ranged' or 'melee' (blank = every weapon attack).",
    "spell": "",
    "weapon damage": "Damage types, 'ranged', 'melee', 'thrown' or 'unarmed' (blank = every weapon hit).",
    "spell damage": "Damage types, a school such as evocation, 'cantrip' (blank = every damaging spell).",
    "healing": "",
    "item spell attack": "",
    "item spell dc": "",
    "item weapon bonus": "",
    "item set ability": "The ability: STR, DEX, CON, INT, WIS or CHA.",
}


# ----------------------------------------------------------------------------- reading an effect

def blank_effect(affects: str = "skill") -> dict:
    return {"affects": affects, "limit": "", "does": DOES_FOR[affects][0], "value": 0, "count": 1, "sides": 4,
            "scales": "", "choice": False, "default_on": False, "once": False, "label": ""}


def _int(v, default=0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def validate(effect: dict) -> str:
    """"" when the effect makes sense, otherwise what is wrong with it."""
    affects, does = effect.get("affects"), effect.get("does")
    if affects not in AFFECTS:
        return "Choose what the effect changes."
    if does not in DOES_FOR[affects]:
        return f"'{DOES.get(does, does)}' does not apply to {AFFECTS[affects].lower()}."
    if does in ("dice", "penalty dice", "fail add") or (does == "extra damage" and _int(effect.get("count")) > 0):
        if not 1 <= _int(effect.get("count"), 1) <= 50 or not 2 <= _int(effect.get("sides"), 4) <= 100:
            return "Dice need a count from 1 to 50 and between 2 and 100 sides."
    if does in ("minimum", "reroll", "crit", "total at least"):
        v = _int(effect.get("value"))
        if does == "crit" and not 2 <= v <= 20:
            return "A critical hit range must start between 2 and 20."
        if does in ("minimum", "total at least") and v < 1:
            return "Enter a number of 1 or more."
        if does == "reroll" and not 1 <= v <= 19:
            return "Reroll d20s showing between 1 and 19 or less."
    if affects == "item set ability" and effect.get("limit", "").strip().upper()[:3] not in ABILITIES:
        return "Name the ability the item sets (STR, DEX, CON, INT, WIS or CHA)."
    if effect.get("scales", "") not in SCALES:
        return "Unknown way of scaling."
    return ""


@dataclass
class Limits:
    skills: List[str] = field(default_factory=list)
    abilities: List[str] = field(default_factory=list)
    conc: bool = False
    proficient: bool = False
    ranged: Optional[bool] = None
    thrown: bool = False
    unarmed: bool = False
    vs: str = ""
    types: List[str] = field(default_factory=list)
    schools: List[str] = field(default_factory=list)
    cantrip: bool = False


def parse_limit(text: str) -> Limits:
    """Read the free-text "only for" box leniently: skills, abilities, damage types and the few keywords."""
    out = Limits()
    low = (text or "").lower()
    for skill in SKILLS:
        if skill.lower() in low:
            out.skills.append(skill)
    for word, ab in ABILITY_WORDS.items():
        if re.search(rf"\b{word}\b", low) and ab not in out.abilities:
            out.abilities.append(ab)
    for ab in ABILITIES:
        if re.search(rf"\b{ab.lower()}\b", low) and ab not in out.abilities:
            out.abilities.append(ab)
    out.conc = "concentration" in low
    out.proficient = "proficien" in low
    if re.search(r"\branged\b", low):
        out.ranged = True
    elif re.search(r"\bmelee\b", low):
        out.ranged = False
    out.thrown = "thrown" in low
    out.unarmed = "unarmed" in low
    for vs in ("charmed", "frightened", "poisoned"):
        if vs in low:
            out.vs = vs
    if re.search(r"\bmagic|\bspells?\b", low):
        out.vs = out.vs or "magic"
    out.types = [t for t in DAMAGE_TYPES if t in low]
    out.schools = [s for s in SCHOOLS if s in low]
    out.cantrip = "cantrip" in low
    return out


def _scaled(effect: dict) -> Callable:
    """fn(ctx) -> the effect's number: ``value`` plus whatever it scales with."""
    base = _int(effect.get("value"))
    scale = effect.get("scales", "") or ""

    def fn(ctx):
        extra = 0
        if scale == "proficiency bonus":
            extra = ctx.prof
        elif scale == "half proficiency bonus":
            extra = ctx.prof // 2
        elif scale == "character level":
            extra = ctx.total_level
        elif scale == "half character level":
            extra = ctx.total_level // 2
        elif scale.endswith("modifier") or scale.endswith("modifier (min +1)"):
            ab = scale.split()[0]
            extra = ctx.mod(ab)
            if "min +1" in scale:
                extra = max(1, extra)
        return base + extra
    return fn


def describe(effect: dict) -> str:
    """A one-line summary for the editors' lists."""
    affects = AFFECTS.get(effect.get("affects"), "?")
    does = effect.get("does", "")
    limit = (effect.get("limit") or "").strip()
    count, sides, value = _int(effect.get("count"), 1), _int(effect.get("sides"), 4), _int(effect.get("value"))
    scale = effect.get("scales") or ""
    num = f"{value:+d}" if value or not scale else ""
    if scale:
        num = (num + " " if num else "") + f"+ {scale}"
    if does in ("dice", "fail add"):
        what = f"{count}d{sides}" + (f" {value:+d}" if value else "")
    elif does == "penalty dice":
        what = f"-{count}d{sides}"
    elif does == "extra damage":
        what = " + ".join(x for x in ([f"{count}d{sides}"] if count else []) + ([num] if num else []))
    elif does in ("bonus", "set"):
        what = num or str(value)
    elif does in ("minimum", "reroll", "crit", "total at least"):
        what = str(value)
    else:
        what = ""
    text = f"{DOES.get(does, does)}" + (f" ({what})" if what else "") + f": {affects.lower()}"
    if limit:
        text += f" - only {limit}"
    if effect.get("choice"):
        text += " [a choice]"
    if effect.get("once"):
        text += " [once per turn]"
    return text


# ----------------------------------------------------------------------------- turning effects into rules

@dataclass
class Built:
    """The analyzer's objects for a list of effects."""
    rules: List[Rule] = field(default_factory=list)
    damage_rules: List[DmgRule] = field(default_factory=list)
    spell_attack: int = 0
    spell_dc: int = 0
    weapon_bonus: int = 0
    ability_sets: Dict[str, int] = field(default_factory=dict)
    weapon_extras: List[Tuple[str, int, int, str, str, bool]] = field(default_factory=list)   # label,count,sides,type,cond,default


def build_effects(effects: List[dict], owner: str, owner_id: str,
                  present: Optional[Callable] = None) -> Built:
    """Rules for ``effects`` owned by ``owner`` (a feat, a trait, a magic item ...). ``present(ctx)`` says whether the
    character has it; an item's rules leave it out (they are listed in the item's own ItemInfo)."""
    built = Built()
    for i, eff in enumerate(effects or []):
        if validate(eff):
            continue
        affects, does = eff["affects"], eff["does"]
        lim = parse_limit(eff.get("limit", ""))
        label = (eff.get("label") or "").strip()
        rid = f"hb:{owner_id}:{i}"
        text = label or f"{owner}: {describe(eff)}"
        toggle = bool(eff.get("choice"))
        default = bool(eff.get("default_on"))
        value_fn = _scaled(eff)
        count, sides = _int(eff.get("count"), 1), _int(eff.get("sides"), 4)

        if affects in ITEM_AFFECTS:
            v = _int(eff.get("value"))
            if affects == "item spell attack":
                built.spell_attack += v
            elif affects == "item spell dc":
                built.spell_dc += v
            elif affects == "item weapon bonus":
                built.weapon_bonus = max(built.weapon_bonus, v)
            else:
                built.ability_sets[(eff.get("limit") or "").strip().upper()[:3]] = v
            continue

        if affects in DAMAGE_AFFECTS:
            dice = (count, sides) if _int(eff.get("count"), 0) > 0 else None
            kind = "weapon" if affects == "weapon damage" else "spell"
            healing_only = affects == "healing"

            def applies(c, d, lim=lim, kind=kind, healing_only=healing_only):
                if d.kind != kind:
                    return False
                if kind == "spell":
                    if healing_only != d.healing:
                        return False
                    if lim.cantrip and not d.cantrip:
                        return False
                    if lim.schools and d.school not in lim.schools:
                        return False
                else:
                    if lim.ranged is True and not d.ranged:
                        return False
                    if lim.ranged is False and d.ranged:
                        return False
                    if lim.thrown and not d.thrown:
                        return False
                    if lim.unarmed and not d.unarmed:
                        return False
                if lim.types and d.damage_type not in lim.types:
                    return False
                return True

            flat_fn = (lambda c, d, fn=value_fn: fn(c)) if (_int(eff.get("value")) or eff.get("scales")) else 0
            built.damage_rules.append(DmgRule(
                id=rid, label=text, feature="", when=present, applies=applies,
                dice=(lambda c, d=dice: d) if dice else None, flat=flat_fn, once=bool(eff.get("once")),
                toggle=toggle, default=default if toggle else True, toggle_label=text))
            continue

        # ---- d20 rules
        kinds = (affects,) if affects != "check" else ("check",)
        effects_list: List[Eff] = []
        if does == "advantage":
            effects_list.append(ADV)
        elif does == "disadvantage":
            effects_list.append(DIS)
        elif does == "bonus":
            effects_list.append(flat(value_fn))
        elif does == "dice":
            effects_list.append(die(count, sides, 1))
        elif does == "penalty dice":
            effects_list.append(die(count, sides, -1))
        elif does == "minimum":
            effects_list.append(minimum(_int(eff.get("value"))))
        elif does == "reroll":
            effects_list.append(reroll(_int(eff.get("value"))))
        elif does == "crit":
            effects_list.append(Eff("crit", _int(eff.get("value"))))
        elif does == "extra d20":
            effects_list.append(Eff("copies", 1))
        elif does == "total at least":
            effects_list.append(Eff("floor_total", _int(eff.get("value"))))
        elif does == "fail add":
            effects_list.append(Eff("rescue_add", (count, sides, _int(eff.get("value")))))
        elif does == "fail reroll":
            effects_list.append(Eff("rescue_reroll", value_fn))
        elif does == "fail succeed":
            effects_list.append(RESCUE_SUCCEED)
        elif does == "fail twenty":
            effects_list.append(RESCUE_SET20)
        rule = Rule(id=rid, label=text, feature="", kinds=kinds,
                    skills=fs(*lim.skills) if lim.skills else None,
                    abilities=fs(*lim.abilities) if lim.abilities else None,
                    conc=True if (affects == "save" and lim.conc) else None,
                    proficient=True if lim.proficient else None,
                    ranged=lim.ranged if affects == "attack" else None,
                    vs=lim.vs if affects == "save" else "", effects=tuple(effects_list), toggle=toggle,
                    toggle_label=text, default=default, when=present)
        built.rules.append(rule)
    return built


# ----------------------------------------------------------------------------- finding a character's effects

def _has(effects) -> bool:
    return bool(effects)


@dataclass
class Collected:
    rules: List[Rule] = field(default_factory=list)
    damage_rules: List[DmgRule] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)       # owners that contribute, for the "found on the sheet" list


def collect(ctx, lookups) -> Collected:
    """The homebrew effects a character has: custom feats, species traits, class and subclass features.
    (Magic items are handled with the other items, in ``item_effects``.)"""
    out = Collected()

    def add(owner: str, owner_id: str, effects, present):
        built = build_effects(effects, owner, owner_id, present)
        if built.rules or built.damage_rules:
            out.rules += built.rules
            out.damage_rules += built.damage_rules
            out.labels.append(owner)

    feat_lookup = getattr(lookups, "feat", None)
    if feat_lookup:
        for name in getattr(ctx.character, "feats", []) or []:
            feat = feat_lookup(name)
            if feat is not None and getattr(feat, "roll_effects", None):
                key = re.sub(r"\s*\(legacy[^)]*\)", "", name, flags=re.IGNORECASE).strip().lower()
                add(f"Feat: {feat.name}", f"feat:{feat.name}", feat.roll_effects, (lambda k: lambda c: c.feat(k))(key))

    lineage_lookup = getattr(lookups, "lineage", None)
    lineage_name = (getattr(ctx.character, "lineage", "") or "").strip()
    if lineage_lookup and lineage_name:
        lineage = lineage_lookup(lineage_name)
        if lineage is not None:
            for trait in getattr(lineage, "traits", []) or []:
                if getattr(trait, "roll_effects", None):
                    add(f"{lineage.name}: {trait.name}", f"lineage:{lineage.name}:{trait.name}", trait.roll_effects,
                        (lambda n: lambda c: c.lineage_has(n))(lineage.name.lower()))

    class_lookup = getattr(lookups, "class_def", None)
    if class_lookup:
        for original, base, level, subclass in ctx.class_entries:
            cdef = class_lookup(original)
            if cdef is None:
                continue
            for lvl, cl in (getattr(cdef, "levels", {}) or {}).items():
                for ability in getattr(cl, "abilities", []) or []:
                    if getattr(ability, "roll_effects", None) and not getattr(ability, "is_subclass_feature", False):
                        add(f"{base}: {ability.title}", f"class:{base}:{lvl}:{ability.title}", ability.roll_effects,
                            (lambda b, n: lambda c: c.lvl(b) >= n)(base, int(lvl)))
            if subclass:
                subs = list(getattr(cdef, "subclasses", []) or []) + list(getattr(cdef, "compat_subclasses", []) or [])
                for sub in subs:
                    if re.sub(r"\s*\(legacy[^)]*\)", "", sub.name, flags=re.IGNORECASE).strip().lower() != subclass:
                        continue
                    for feature in getattr(sub, "features", []) or []:
                        if getattr(feature, "roll_effects", None):
                            add(f"{sub.name}: {feature.title}", f"sub:{base}:{sub.name}:{feature.title}",
                                feature.roll_effects,
                                (lambda b, n, s: lambda c: c.lvl(b) >= n and c.sub_has(b, s))(base, feature.level, subclass))
    return out
