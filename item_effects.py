"""
What a character's linked magic items do to their rolls.

The sheet keeps a list of magic items (name, attuned, extra properties). Each one is read here - from its
description in the Magic Items collection, so homebrew items work too - and turned into :class:`Rule` objects
for ``character_rolls`` to apply: bonuses to saves, checks, spell attacks and spell save DCs, advantage on skills
or initiative, ability scores an item sets (Gauntlets of Ogre Power), and magic weapons (their bonus and extra
damage dice).

Only what the text says plainly is read (``+1 bonus to ... saving throws``, ``you have Advantage on Dexterity
(Stealth) checks``); anything subtler is left out rather than guessed. An item that needs attunement counts only
while the sheet marks it attuned, and each item can be switched off on the page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from roll_rules import ADV, Eff, Rule, flat, fs, minimum, rescue_reroll, reroll

ABILITY = {"strength": "STR", "dexterity": "DEX", "constitution": "CON", "intelligence": "INT", "wisdom": "WIS",
           "charisma": "CHA"}
SKILLS = ["Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception", "History", "Insight", "Intimidation",
          "Investigation", "Medicine", "Nature", "Perception", "Performance", "Persuasion", "Religion",
          "Sleight of Hand", "Stealth", "Survival"]
GIANT_SCORES = {"hill": 21, "frost": 23, "stone": 23, "fire": 25, "cloud": 27, "storm": 29}
RARITY_BONUS = {"uncommon": 1, "rare": 2, "very rare": 3, "legendary": 3}
ARMOR_RARITY_BONUS = {"rare": 1, "very rare": 2, "legendary": 3}
DAMAGE_TYPES = ["acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison",
                "psychic", "radiant", "slashing", "thunder"]
CONDITIONS = {"poisoned": "poisoned", "charmed": "charmed", "frightened": "frightened"}


@dataclass
class ItemExtra:
    """Extra damage dice a magic weapon adds when it hits."""
    label: str
    count: int
    sides: int
    damage_type: str = ""
    condition: str = ""             # "" = always; otherwise shown as a choice ("vs Giants")
    default: bool = True


@dataclass
class WeaponItem:
    name: str
    bonus: int = 0                  # to attack and damage rolls
    extras: List[ItemExtra] = field(default_factory=list)
    crit_min: int = 20
    unarmed: bool = False
    keywords: List[str] = field(default_factory=list)       # words that identify the attack on the sheet


@dataclass
class ItemInfo:
    name: str
    usable: bool = True
    needs_attunement: bool = False
    reason: str = ""                # why it does not count (needs attunement ...)
    rules: List[Rule] = field(default_factory=list)
    ability_sets: Dict[str, int] = field(default_factory=dict)
    spell_attack: int = 0
    spell_dc: int = 0
    spell_class: str = ""
    weapon: Optional[WeaponItem] = None
    global_extras: List[ItemExtra] = field(default_factory=list)       # extra damage on any weapon hit (a cloak ...)
    damage_rules: List = field(default_factory=list)                   # homebrew spell damage / healing extras
    notes: List[str] = field(default_factory=list)

    @property
    def does_anything(self) -> bool:
        return bool(self.rules or self.ability_sets or self.spell_attack or self.spell_dc or self.weapon
                    or self.global_extras or self.damage_rules)


# ----------------------------------------------------------------------------- reading text

_LINK = re.compile(r"\[\[[a-z_]+:([^\]|]+)(\|([^\]]*))?\]\]")


def clean(text: str) -> str:
    text = _LINK.sub(lambda m: m.group(3) or m.group(1), text or "")
    return re.sub(r"[ \t]+", " ", text.replace("\\", "\n"))


def sentences(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", clean(text)) if p.strip()]


def _skills_in(phrase: str) -> List[str]:
    return [s for s in SKILLS if re.search(rf"\b{re.escape(s)}\b", phrase, re.IGNORECASE)]


_SKILL_CHECK = re.compile(r"(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s*\(([^)]+)\)\s*checks?",
                          re.IGNORECASE)


def _bonus_value(item_name: str, extra: str, rarity: str, item_type: str, text: str) -> int:
    """How big a "+N" item is: written on the sheet, in the name, or set by the item's rarity."""
    m = re.search(r"\+\s*(\d)", extra or "")
    if m:
        return int(m.group(1))
    names = re.findall(r"\+\s*(\d)", item_name or "")
    if len(names) == 1:
        return int(names[0])
    rarity = (rarity or "").strip().lower()
    table = ARMOR_RARITY_BONUS if (item_type or "").lower().startswith("armor") and "shield" not in (item_type or "").lower() \
        else RARITY_BONUS
    return table.get(rarity, 1)


def _qualifier(text: str) -> str:
    text = text.strip(" .,;")
    return text if text else ""


# ----------------------------------------------------------------------------- the parser

def parse_item(entry: dict, magic=None) -> ItemInfo:
    """Read one linked magic item. ``entry`` is the sheet's row (name, attuned, extra_properties ...); ``magic`` the
    item from the Magic Items collection, if it can be found (its description is more complete than the snapshot)."""
    name = str(entry.get("name", "")).strip() or "Magic item"
    extra = str(entry.get("extra_properties", "") or "")
    text = (getattr(magic, "description", "") or entry.get("description", "") or "")
    item_type = str(getattr(magic, "type", "") or "")
    rarity = getattr(getattr(magic, "rarity", None), "value", None) or str(getattr(magic, "rarity", "") or "")
    requires = bool(entry.get("requires_attunement", getattr(magic, "requires_attunement", False)))
    if getattr(magic, "attunement_optional", False):
        requires = False
    info = ItemInfo(name, needs_attunement=requires)
    if requires and not entry.get("attuned", False):
        info.usable = False
        info.reason = "not attuned"
    structured = getattr(magic, "roll_effects", None)
    if structured:                              # a homebrew item that says what it does: believe it, do not guess
        return _item_from_effects(info, name, structured)
    lowname = name.lower()
    counter = [0]

    def rule(label: str, kinds, effects, *, skills=None, abilities=None, vs="", conc=None, toggle_label="",
             toggle=False, default=False, spell_class="") -> None:
        counter[0] += 1
        info.rules.append(Rule(id=f"item:{name}:{counter[0]}", label=label, kinds=tuple(kinds), skills=skills,
                               abilities=abilities, vs=vs, conc=conc, effects=tuple(effects), toggle=toggle,
                               toggle_label=toggle_label or label, default=default, spell_class=spell_class))

    bonus = _bonus_value(name, extra, rarity, item_type, text)
    weapon_like = item_type.lower().startswith("weapon") or "weapon" in lowname
    weapon = WeaponItem(name, keywords=_keywords(name))

    for s in sentences(text):
        low = s.lower()

        # ---- "+N bonus to ..."
        for m in re.finditer(r"\+(\d+)\s+bonus to ([^.;]*)", s, re.IGNORECASE):
            v, phrase = int(m.group(1)), re.split(r",\s*(?:and\s+)?you\b|\s+and you\b", m.group(2))[0]
            pl = phrase.lower()
            if re.search(r"attack (rolls? )?and damage rolls?|attack rolls? and damage rolls? made with|"
                         r"attack and damage rolls", pl):
                weapon.bonus = max(weapon.bonus, v)
                if "unarmed" in pl:
                    weapon.unarmed = True
                continue
            sk = _SKILL_CHECK.search(phrase)
            if sk:
                names = _skills_in(sk.group(2))
                qual = _qualifier(phrase[sk.end():])
                rule(f"{name}: +{v} {', '.join(names)}", ("check",), [flat(v)], skills=fs(*names),
                     toggle=bool(qual), toggle_label=f"{name}: +{v} to {', '.join(names)} checks {qual}".strip())
                continue
            kinds = []
            if "ability check" in pl:
                kinds.append("check")
            if "saving throw" in pl and "saving throw dc" not in pl:
                kinds.append("save")
            if kinds:
                rule(f"{name}: +{v}", kinds, [flat(v)])
            if "spell attack" in pl:
                info.spell_attack = max(info.spell_attack, v)
            if "saving throw dc" in pl or "spell save dc" in pl:
                info.spell_dc = max(info.spell_dc, v)
            if "initiative" in pl:
                rule(f"{name}: +{v} initiative", ("initiative",), [flat(v)])

        # ---- "a bonus to spell attack rolls ... determined by the item's rarity"
        if re.search(r"bonus to spell attack rolls", low) and not re.search(r"\+\d+\s+bonus to spell attack", low):
            info.spell_attack = max(info.spell_attack, bonus)
            if "saving throw dc" in low:
                info.spell_dc = max(info.spell_dc, bonus)
            m = re.search(r"of your (\w+) spells", s, re.IGNORECASE)
            if m:
                info.spell_class = m.group(1)
        m = re.search(r"spell save DC and spell attack bonus each increase by (\d+)", s, re.IGNORECASE)
        if m:
            info.spell_dc = max(info.spell_dc, int(m.group(1)))
            info.spell_attack = max(info.spell_attack, int(m.group(1)))

        # ---- "a bonus to attack rolls and damage rolls ... determined by rarity" (Weapon, +1, +2 or +3)
        if re.search(r"(you have|gain) a bonus to attack rolls and damage rolls", low) and "unarmed" in low:
            weapon.bonus = max(weapon.bonus, bonus)
            weapon.unarmed = True
        elif re.search(r"you have a bonus to attack rolls and damage rolls made with", low) and weapon_like:
            weapon.bonus = max(weapon.bonus, bonus)

        # ---- advantage
        if (re.search(r"\byou (?:also )?(?:have|gain) advantage on\b", low) and not low.startswith("while you have the ")
                and lowname not in _COMPLEX_ITEMS):
            _parse_advantage(s, name, rule)

        # ---- abilities an item sets
        m = re.search(r"\bYour (Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)(?: score)? is (\d+)\b",
                      s, re.IGNORECASE)
        if m:
            info.ability_sets[ABILITY[m.group(1).lower()]] = int(m.group(2))

        # ---- initiative dice, d20 tricks
        m = re.search(r"add (\d+)d(\d+) to your Initiative", s, re.IGNORECASE)
        if m:
            rule(f"{name}: +{m.group(1)}d{m.group(2)} initiative", ("initiative",),
                 [Eff("die", (int(m.group(1)), int(m.group(2)), 1))])
        if re.search(r"reroll one failed d20 test", low):
            rule(f"{name}: reroll a failed d20 test", ("check", "save", "attack"), [rescue_reroll()],
                 toggle=True, toggle_label=f"{name}: reroll a failed roll")
        if re.search(r"when you roll a 1 on a saving throw or ability check", low) and "reroll" in low:
            rule(f"{name}: reroll a 1", ("check", "save"), [reroll(1)])
        if re.search(r"when you make an attack roll .*forgo rolling the d20 to get a 10", low):
            rule(f"{name}: take 10 on an attack", ("attack",), [Eff("fixed_d20", 10)], toggle=True,
                 toggle_label=f"{name}: forgo rolling, the d20 is a 10")
        m = re.search(r"critical hit on a roll of (\d+) or (\d+)", low)
        if m:
            weapon.crit_min = min(weapon.crit_min, int(m.group(1)))
        m = re.search(r"treat a d20 roll of (\d+) or lower as a (\d+)", low)
        if m and "death saving" not in low:
            skills = _skills_in(s) or (["Arcana", "History", "Investigation", "Nature", "Religion"]
                                       if "intelligence" in low else None)
            rule(f"{name}: a d20 of {m.group(1)} or less counts as {m.group(2)}", ("check",),
                 [minimum(int(m.group(2)))], abilities=fs("INT") if "intelligence" in low else None,
                 toggle=True, toggle_label=f"{name}: treat a d20 of {m.group(1)} or less as {m.group(2)}")

        # ---- extra damage on a hit
        for ex in _parse_extras(s, name):
            weapon.extras.append(ex)

    if weapon.bonus or weapon.crit_min < 20 or weapon.unarmed or (weapon.extras and weapon_like):
        info.weapon = weapon
    elif weapon.extras:
        info.global_extras = weapon.extras
    # staffs, rods and wands that are also weapons are matched by their own name; a plain weapon by its name too
    return info


def _item_from_effects(info: ItemInfo, name: str, effects) -> ItemInfo:
    """An item whose author listed its roll effects (see ``roll_effects``)."""
    from roll_effects import build_effects
    built = build_effects(effects, name, f"item:{name}")
    info.rules = built.rules
    info.damage_rules = built.damage_rules
    info.ability_sets = dict(built.ability_sets)
    info.spell_attack, info.spell_dc = built.spell_attack, built.spell_dc
    if built.weapon_bonus:
        info.weapon = WeaponItem(name, bonus=built.weapon_bonus, keywords=_keywords(name))
    return info


def _keywords(name: str) -> List[str]:
    base = re.sub(r"[+,()]|\b\d\b", " ", name.lower())
    words = [w for w in base.split() if len(w) > 2 and w not in ("the", "and", "weapon", "of")]
    return [name.lower()] + words


def _parse_advantage(sentence: str, item: str, rule: Callable) -> None:
    m = re.search(r"advantage on (.*)", sentence, re.IGNORECASE)
    if not m:
        return
    phrase = m.group(1)
    low = phrase.lower()
    toggle_prefix = f"{item}: advantage"
    parts = re.split(r"\band on\b", phrase, flags=re.IGNORECASE)
    for part in parts:
        pl = part.lower()
        if "initiative" in pl:
            rule(f"{item}: advantage on initiative", ("initiative",), [ADV])
            continue
        sk = _SKILL_CHECK.search(part)
        if sk:
            names = _skills_in(sk.group(2))
            qual = _qualifier(part[sk.end():].split(".")[0])
            qual = re.sub(r"\bwhile .*$", "", qual).strip(" ,")
            rule(f"{item}: advantage on {', '.join(names)}", ("check",), [ADV], skills=fs(*names),
                 toggle=bool(qual), toggle_label=f"{item}: advantage on {', '.join(names)} {qual}".strip())
            continue
        if "saving throw" in pl:
            vs = ""
            for word, key in CONDITIONS.items():
                if word in pl:
                    vs = key
            if re.search(r"against spells|against .*magical effects", pl):
                vs = "magic"
            if vs:
                rule(f"{item}: advantage on saves vs {vs}", ("save",), [ADV], vs=vs)     # chosen with "Save against"
            elif re.search(r"against", pl):
                what = re.split(r",|\.", pl.split("against", 1)[1])[0].strip()[:60]
                rule(f"{item}: advantage on saves against {what}", ("save",), [ADV], toggle=True,
                     toggle_label=f"{item}: advantage on saves against {what}")
            else:
                rule(f"{item}: advantage on saves", ("save",), [ADV])
            continue
        if "d20 test" in pl:
            rule(f"{item}: advantage on d20 tests", ("check", "save", "attack"), [ADV], toggle=True,
                 toggle_label=f"{item}: advantage on d20 tests (while its light lasts)")
            continue
        if re.search(r"attack roll", pl):
            qual = _qualifier(part.split("attack roll", 1)[1].split(".")[0])[:60]
            rule(f"{item}: advantage on attacks", ("attack",), [ADV], toggle=True,
                 toggle_label=f"{item}: advantage on attack rolls {qual}".strip())
            continue
        if "ability check" in pl or "checks" in pl:
            rule(f"{item}: advantage on checks", ("check",), [ADV], toggle=True,
                 toggle_label=f"{item}: advantage on ability checks ({part.strip()[:50]})")


_EXTRA = re.compile(r"extra\s+(\d+)d(\d+)\s*(?:(" + "|".join(DAMAGE_TYPES) + r")\s+)?damage", re.IGNORECASE)
CREATURE_TYPES = ("aberration|beast|celestial|construct|dragon|elemental|fey|fiend|giant|humanoid|monstrosity|ooze|"
                  "plant|undead|fiends?|undeads?|giants?|dragons?|constructs?|elementals?")
_COMPLEX_ITEMS = ("moonblade", "rod of lordly might", "eye and hand of vecna", "ioun stone", "deck of many things",
                  "ammunition of slaying", "dream weaver")


def _parse_extras(sentence: str, item: str) -> List[ItemExtra]:
    """Extra damage dice on a hit, with the condition for them ("vs Undead", "while it is ablaze")."""
    low = sentence.lower()
    if item.lower() in _COMPLEX_ITEMS:
        return []
    if "charge" in low or "roll a 20" in low or "rolled a 20" in low or "critical hit" in low:
        return []
    if "creature of that type" in low or "chosen type" in low:
        return []
    clauses = re.split(r",?\s+(?=(?:or|and)\s+(?:an?\s+)?(?:extra|additional))", sentence)
    out: List[ItemExtra] = []
    first: Optional[ItemExtra] = None
    for clause in clauses:
        cl = clause.lower()
        m = _EXTRA.search(clause)
        if not m or "object" in cl:
            continue
        count, sides = int(m.group(1)), int(m.group(2))
        dtype = (m.group(3) or "").lower()
        condition = _extra_condition(clause)
        replaces = bool(re.match(r"\s*or\b", clause, re.IGNORECASE)) and first is not None
        if replaces and first.sides == sides and count > first.count:
            count -= first.count                       # "an extra 1d8, or 2d8 vs Giants": the Giants get 1d8 more
        elif replaces:
            continue
        label = f"{item}: +{count}d{sides}" + (f" {dtype}" if dtype else "")
        extra = ItemExtra(label, count, sides, dtype or (first.damage_type if first else ""), condition,
                          default=(condition == "while it is ablaze"))
        if first is None:
            first = extra
        out.append(extra)
    return out


def _extra_condition(clause: str) -> str:
    low = clause.lower()
    m = re.search(r"if the target is (?:an? |any )?([^.,]+)", clause, re.IGNORECASE)
    if m:
        return f"vs {m.group(1).strip()}"
    m = re.search(r"when you hit (?:an? )?(" + CREATURE_TYPES + r")\b", clause, re.IGNORECASE)
    if m:
        return f"vs {m.group(1)}"
    if "sworn enemy" in low:
        return "vs your sworn enemy"
    if re.search(r"any humanoid", low):
        return "vs a Humanoid"
    if "ablaze" in low or "blazing" in low:
        return "while it is ablaze"
    if "ranged attack" in low:
        return "on a ranged hit"
    return ""


# ----------------------------------------------------------------------------- the whole list

def belt_score(name: str, extra: str) -> Optional[int]:
    text = f"{name} {extra}".lower()
    if "giant strength" not in text and "belt" not in text:
        return None
    for key, score in GIANT_SCORES.items():
        if key in text:
            return score
    return None


def parse_items(sheet, magic_lookup: Callable[[str], object] = lambda n: None) -> List[ItemInfo]:
    """Every linked magic item on the sheet, read."""
    out = []
    for entry in getattr(sheet, "magic_items", None) or []:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        magic = magic_lookup(entry["name"])
        info = parse_item(entry, magic)
        if "belt of" in info.name.lower() and "giant strength" in info.name.lower() or info.name.lower() == "belt of giant strength":
            score = belt_score(info.name, str(entry.get("extra_properties", "")))
            info.ability_sets["STR"] = score or GIANT_SCORES["hill"]
            if score is None:
                info.notes.append("Belt of Giant Strength: Hill Giant (21) assumed; write the giant on the sheet.")
        out.append(info)
    return out
