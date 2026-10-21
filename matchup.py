"""
One-on-one fight analysis: two creatures or characters, what they do to each other, and who is likely to win.

No UI. A :class:`Side` is a combatant (a monster, a character sheet or a hand-typed creature). Facing an opponent it
becomes a :class:`Prepared` side: the plans it can use on its turn (a multiattack, a breath weapon, a spell, a
cantrip, the character's attacks), each with the damage distribution it deals *to that opponent* - armor class,
saving throws, damage resistances, immunities and vulnerabilities all counted. ``analyze(a, b)`` then simulates the
fight many times (initiative, recharge, daily uses, spell slots, legendary resistance, regeneration) and reports the
odds, how long it takes, and the "tide turners": things that cannot be reduced to an average, such as conditions the
creatures can inflict, spells that debuff, legendary resistance, healing, or a big difference in speed or range.

Characters reuse the Dice Analyzer's engine (``character_rolls``), so their attack and spell numbers match what that
tool shows, including features and linked magic items.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from dice_analyzer import DiceTerm, Dist

CONDITIONS = ["Blinded", "Charmed", "Deafened", "Frightened", "Grappled", "Incapacitated", "Invisible", "Paralyzed",
              "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious", "Exhaustion"]
DAMAGE_TYPES = ["acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison",
                "psychic", "radiant", "slashing", "thunder"]
ABILITIES = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
ABILITY_WORDS = {"strength": "STR", "dexterity": "DEX", "constitution": "CON", "intelligence": "INT",
                 "wisdom": "WIS", "charisma": "CHA"}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10}
MAX_ROUNDS = 30


# ----------------------------------------------------------------------------- defences

@dataclass
class Defender:
    """What an attacker has to get through."""
    name: str
    ac: int = 10
    hp: int = 1
    saves: Dict[str, int] = field(default_factory=dict)        # ability -> save bonus
    resist: Set[str] = field(default_factory=set)               # damage types (lower case)
    immune: Set[str] = field(default_factory=set)
    vulnerable: Set[str] = field(default_factory=set)
    condition_immunities: Set[str] = field(default_factory=set)  # capitalised condition names
    legendary_resistance: int = 0
    magic_resistance: bool = False                              # advantage on saves against spells
    regeneration: int = 0

    def factor(self, damage_type: str) -> float:
        t = (damage_type or "").lower()
        if t in self.immune:
            return 0.0
        factor = 1.0
        if t in self.resist:
            factor *= 0.5
        if t in self.vulnerable:
            factor *= 2.0
        return factor


def _scaled(dist: Dist, k: int) -> Dist:
    """Every value times ``k`` (k = 2 for vulnerability)."""
    lo = dist.lo * k
    probs = [0.0] * ((len(dist.probs) - 1) * k + 1)
    for i, p in enumerate(dist.probs):
        probs[i * k] += p
    return Dist(lo, probs, dist.approx)


def adjust(dist: Dist, damage_type: str, target: Defender) -> Dist:
    """The damage after the target's resistance, immunity or vulnerability to ``damage_type``."""
    f = target.factor(damage_type)
    if f == 0.0:
        return Dist.point(0)
    if f == 0.5:
        return dist.halved()
    if f == 2.0:
        return _scaled(dist, 2)
    return dist


def save_success_chance(bonus: int, dc: int, advantage: bool = False) -> float:
    """P(d20 + bonus >= dc), with advantage if asked."""
    need = dc - bonus
    p = min(1.0, max(0.0, (21 - need) / 20.0))
    return 1 - (1 - p) ** 2 if advantage else p


# ----------------------------------------------------------------------------- one thing a creature can do

@dataclass
class Strike:
    """A single attack, breath weapon, spell... a creature can use, in terms of its raw numbers."""
    name: str
    kind: str = "attack"                    # "attack" | "save" | "auto"
    attack_bonus: int = 0
    save_ability: str = ""
    save_dc: int = 0
    half_on_save: bool = False
    components: List[Tuple[int, int, int, str]] = field(default_factory=list)   # (count, sides, flat, damage type)
    melee: bool = True
    reach: int = 5
    range_ft: int = 0
    uses: str = "at will"                   # "at will" | "recharge" | "day" | "slot"
    recharge: int = 0
    per_day: int = 0
    slot_level: int = 0
    is_spell: bool = False
    conditions: List[str] = field(default_factory=list)
    area: bool = False
    text: str = ""


@dataclass
class Action:
    """A strike worked out against a particular opponent."""
    name: str
    avg: float
    dist: Dist                              # damage per use (misses included)
    kind: str = "attack"
    hit_chance: float = 0.0
    fail_dist: Optional[Dist] = None        # save-based: damage on a failed save
    success_dist: Optional[Dist] = None
    p_save: float = 0.0                     # chance the target saves
    uses: str = "at will"
    recharge: int = 0
    per_day: int = 0
    slot_level: int = 0
    conditions: List[str] = field(default_factory=list)
    is_spell: bool = False
    melee: bool = True
    reach: int = 5
    range_ft: int = 0
    note: str = ""


@dataclass
class Plan:
    """What a creature does with its turn: some actions together (a multiattack counts as one plan)."""
    name: str
    parts: List[Tuple[Action, int]]
    resource: str = ""                      # "" (free), "recharge:<name>", "day:<name>", "slot:<n>"
    note: str = ""

    @property
    def avg(self) -> float:
        return sum(a.avg * n for a, n in self.parts)

    def chances(self) -> List[Tuple[str, float, str]]:
        """(action name, chance, "hit" or "fail") for each distinct action of the plan that can miss or be saved
        against; automatic damage has no chance to show."""
        found: Dict[str, Tuple[str, float, str]] = {}
        for act, _n in self.parts:
            if act.kind == "attack":
                found.setdefault(act.name, (act.name, act.hit_chance, "hit"))
            elif act.kind == "save":
                found.setdefault(act.name, (act.name, 1.0 - act.p_save, "fail"))
        return list(found.values())

    def chance_text(self) -> str:
        """The chance to land this plan's attacks, e.g. "75% to hit" or "55% to fail the save"."""
        rows = self.chances()
        if not rows:
            return "auto-hit"
        words = {"hit": "to hit", "fail": "to fail the save"}
        if len({(round(c, 3), w) for _n, c, w in rows}) == 1:
            _n, c, w = rows[0]
            return f"{c * 100:.0f}% {words[w]}"
        return "; ".join(f"{n} {c * 100:.0f}% {words[w]}" for n, c, w in rows)


@dataclass
class Prepared:
    """A side as it fights one particular opponent."""
    side: "Side"
    plans: List[Plan]
    legendary: List[Action] = field(default_factory=list)       # used once per round, after the opponent's turn
    spells_table: List[dict] = field(default_factory=list)      # per-spell numbers for casters
    spell_levels: Dict[int, dict] = field(default_factory=dict)
    blocked: List[str] = field(default_factory=list)            # plans that do no damage at all to this opponent
    notes: List[str] = field(default_factory=list)

    def main_plan(self) -> Optional[Plan]:
        """The plan used every round: the free one that does the most damage."""
        free = [p for p in self.plans if not p.resource]
        return max(free, key=lambda p: p.avg) if free else None

    def sustained(self) -> float:
        """Average damage per round with what is available every round."""
        free = [p.avg for p in self.plans if not p.resource]
        return max(free) if free else 0.0

    def best(self) -> float:
        return max([p.avg for p in self.plans] or [0.0])


# ----------------------------------------------------------------------------- reading a monster's stat block

_ATTACK = re.compile(r"(melee or ranged|melee|ranged)(?:\s+(?:weapon|spell))?\s+attack(?:\s+roll)?\s*:\s*([+-]\s*\d+)",
                     re.IGNORECASE)
_SAVE = re.compile(r"(strength|dexterity|constitution|intelligence|wisdom|charisma)\s+saving\s+throw\s*:\s*DC\s*(\d+)",
                   re.IGNORECASE)
_COMPONENT = re.compile(r"(\d+)\s*\(\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*\)\s*([A-Za-z]+)\s+damage", re.IGNORECASE)
_FLAT_COMPONENT = re.compile(r"(?<![\d(d+-])(\d+)\s+([A-Za-z]+)\s+damage", re.IGNORECASE)
_RECHARGE = re.compile(r"recharge\s*(\d)", re.IGNORECASE)
_PER_DAY = re.compile(r"\((\d+)\s*/\s*day", re.IGNORECASE)
_COUNT = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+([A-Z][A-Za-z' -]*?)\s+attacks?",
                    re.IGNORECASE)
_USES = re.compile(r"\buses?\s+([A-Z][A-Za-z' -]+?)(?=[,.;]|\s+(?:or|and|in)\b|$)")


def _components(text: str) -> List[Tuple[int, int, int, str]]:
    """Damage components in a hit / failure sentence: [(count, sides, flat, type)]."""
    out = []
    seen_spans = []
    matches = list(_COMPONENT.finditer(text))
    for i, m in enumerate(matches):
        stop = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        tail = text[m.end():stop].lower()
        if "if the attack roll had advantage" in tail:          # conditional extra damage: not counted
            continue
        flat = int(m.group(5) or 0) * (-1 if m.group(4) == "-" else 1)
        dtype = m.group(6).lower()
        if dtype not in DAMAGE_TYPES:
            continue
        out.append((int(m.group(2)), int(m.group(3)), flat, dtype))
        seen_spans.append((m.start(), m.end()))
    for m in _FLAT_COMPONENT.finditer(text):
        if any(a <= m.start() < b for a, b in seen_spans):
            continue
        dtype = m.group(2).lower()
        if dtype in DAMAGE_TYPES:
            out.append((0, 2, int(m.group(1)), dtype))
    return out


def _conditions_in(text: str) -> List[str]:
    return [c for c in CONDITIONS if re.search(rf"\b{c}\b", text, re.IGNORECASE)
            and re.search(rf"(has|have|gains?|becomes?|is|with)\s+the\s+{c}\b|\b{c}\s+condition", text, re.IGNORECASE)]


def parse_strike(name: str, text: str) -> Optional[Strike]:
    """An attack or a saving-throw effect with damage in a stat block entry, or ``None``."""
    clean = re.sub(r"\[\[[a-z_]+:([^\]|]+)(\|[^\]]*)?\]\]", r"\1", text or "")
    base = re.sub(r"\s*\(.*$", "", name).strip() or name
    strike = Strike(name=base, text=clean)
    m = _RECHARGE.search(name)
    if m:
        strike.uses, strike.recharge = "recharge", int(m.group(1))
    d = _PER_DAY.search(name)
    if d:
        strike.uses, strike.per_day = "day", int(d.group(1))
    attack = _ATTACK.search(clean)
    save = _SAVE.search(clean)
    if attack:
        strike.kind = "attack"
        strike.attack_bonus = int(attack.group(2).replace(" ", ""))
        kind = attack.group(1).lower()
        strike.melee = kind != "ranged"
        reach = re.search(r"reach\s+(\d+)", clean, re.IGNORECASE)
        rng = re.search(r"range\s+(\d+)", clean, re.IGNORECASE)
        strike.reach = int(reach.group(1)) if reach else (5 if strike.melee else 0)
        strike.range_ft = int(rng.group(1)) if rng else 0
        if not strike.melee and not strike.range_ft:
            strike.range_ft = 30
        hit = re.search(r"hit\s*:\s*(.*)", clean, re.IGNORECASE | re.DOTALL)
        body = hit.group(1) if hit else clean
        strike.components = _components(body)
        strike.conditions = _conditions_in(body)
    elif save:
        strike.kind = "save"
        strike.save_ability = ABILITY_WORDS[save.group(1).lower()]
        strike.save_dc = int(save.group(2))
        fail = re.search(r"failure\s*:\s*(.*?)(?=\s+Success\b|\s+Failure or Success|$)", clean,
                         re.IGNORECASE | re.DOTALL)
        body = fail.group(1) if fail else clean[save.end():]
        strike.components = _components(body)
        strike.conditions = _conditions_in(body)
        strike.half_on_save = bool(re.search(r"success\s*:\s*half damage", clean, re.IGNORECASE))
        strike.area = bool(re.search(r"each creature|cone|line|emanation|sphere|cube|cylinder", clean, re.IGNORECASE))
        strike.range_ft = int(re.search(r"(\d+)-foot", clean).group(1)) if re.search(r"(\d+)-foot", clean) else 0
    else:
        return None
    if not strike.components and not strike.conditions:
        return None
    return strike


def parse_multiattack(text: str, strikes: Dict[str, Strike]) -> List[List[Tuple[str, int]]]:
    """The ways a Multiattack can be used: a list of plans, each [(strike name, count)]."""
    clean = re.sub(r"\[\[[a-z_]+:([^\]|]+)(\|[^\]]*)?\]\]", r"\1", text or "")
    by_low = {n.lower(): n for n in strikes}

    def find(raw: str) -> Optional[str]:
        raw = raw.strip().lower()
        if raw in by_low:
            return by_low[raw]
        for low, real in by_low.items():
            if low in raw or raw in low:
                return real
        return None

    counted: List[Tuple[str, int]] = []
    for m in _COUNT.finditer(clean):
        word = m.group(1).lower()
        count = NUMBER_WORDS.get(word) or (int(word) if word.isdigit() else 1)
        real = find(m.group(2))
        if real:
            counted.append((real, count))
    for m in _USES.finditer(clean):
        real = find(m.group(1))
        if real and all(real != c[0] for c in counted):
            counted.append((real, 1))
    first = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b", clean, re.IGNORECASE)
    other = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+other\s+attacks?", clean, re.IGNORECASE)
    if other and counted:                                   # "one Bite and three other attacks, using Claw or Tail"
        word = other.group(1).lower()
        extra = NUMBER_WORDS.get(word) or (int(word) if word.isdigit() else 1)
        taken = {c[0] for c in counted}
        alts = [n for n in strikes if n not in taken and re.search(rf"\b{re.escape(n)}\b", clean)]
        if alts:
            return [counted + [(a, extra)] for a in alts]
    if "in any combination" in clean.lower() or re.search(r"\b\w+ or \w+", clean) and " attacks" in clean.lower() \
            and not counted:
        total = NUMBER_WORDS.get(first.group(1).lower(), 1) if first else 1
        names = [n for n in strikes if re.search(rf"\b{re.escape(n)}\b", clean)]
        return [[(n, total)] for n in names] or []
    if counted:
        return [counted]
    if first and strikes:
        total = NUMBER_WORDS.get(first.group(1).lower(), 1)
        return [[(n, total)] for n in strikes]
    return []


def number_after(text: str, pattern: str, default: int = 0) -> int:
    m = re.search(pattern, text or "", re.IGNORECASE)
    return int(m.group(1)) if m else default


# ----------------------------------------------------------------------------- sides

@dataclass
class Side:
    """A combatant before it meets an opponent."""
    name: str
    kind: str                                   # "monster" | "character" | "custom"
    ac: int = 10
    hp: int = 1
    speeds: Dict[str, int] = field(default_factory=lambda: {"walk": 30})
    initiative: int = 0
    saves: Dict[str, int] = field(default_factory=dict)
    resist: Set[str] = field(default_factory=set)
    immune: Set[str] = field(default_factory=set)
    vulnerable: Set[str] = field(default_factory=set)
    condition_immunities: Set[str] = field(default_factory=set)
    legendary_resistance: int = 0
    magic_resistance: bool = False
    regeneration: int = 0
    strikes: List[Strike] = field(default_factory=list)
    multiattack: List[List[Tuple[str, int]]] = field(default_factory=list)
    legendary: List[str] = field(default_factory=list)          # names of strikes used as legendary actions
    traits: List[Tuple[str, str]] = field(default_factory=list)  # (name, text) of traits/bonus/reactions for notes
    # characters:
    prepare_character: Optional[Callable[["Defender"], "Prepared"]] = None
    spell_slots: Dict[int, int] = field(default_factory=dict)
    features: List[str] = field(default_factory=list)           # notable feature names, for tide turners
    spells_known: List[object] = field(default_factory=list)    # SpellInfo for casters
    spell_texts: Dict[str, str] = field(default_factory=dict)   # spell name -> description (for conditions)
    spell_levels: Dict[str, int] = field(default_factory=dict)  # spell name -> level
    level_text: str = ""
    cr_text: str = ""
    note: List[str] = field(default_factory=list)

    @property
    def defender(self) -> Defender:
        return Defender(self.name, self.ac, self.hp, dict(self.saves), set(self.resist), set(self.immune),
                        set(self.vulnerable), set(self.condition_immunities), self.legendary_resistance,
                        self.magic_resistance, self.regeneration)

    def best_reach(self) -> int:
        reaches = [s.reach for s in self.strikes if s.melee and s.kind == "attack"]
        return max(reaches or [5])

    def best_range(self) -> int:
        ranges = [s.range_ft for s in self.strikes if s.range_ft and (s.kind == "attack" or s.area)]
        return max(ranges or [0])


def side_from_monster(monster, spell_lookup: Callable[[str], object] = lambda n: None) -> Side:
    """A :class:`Side` from a Monster (the collection's stat block)."""
    from character_sheet import AbilityScore
    prof = monster.proficiency_bonus
    side = Side(name=monster.name, kind="monster", ac=monster.ac, hp=monster.hp,
                speeds={k: v for k, v in (monster.speeds or {"walk": 30}).items() if v},
                initiative=monster.get_initiative(), cr_text=f"CR {monster.challenge_rating}")
    for ab, enum in (("STR", AbilityScore.STRENGTH), ("DEX", AbilityScore.DEXTERITY), ("CON", AbilityScore.CONSTITUTION),
                     ("INT", AbilityScore.INTELLIGENCE), ("WIS", AbilityScore.WISDOM), ("CHA", AbilityScore.CHARISMA)):
        side.saves[ab] = monster.get_save_bonus(enum)

    def types(items: Sequence[str]) -> Set[str]:
        out: Set[str] = set()
        for item in items:
            out |= {t for t in DAMAGE_TYPES if t in item.lower()}
        return out

    side.resist = types(monster.damage_resistances)
    side.immune = types(monster.damage_immunities)
    side.vulnerable = types(monster.damage_vulnerabilities)
    side.condition_immunities = {c for c in CONDITIONS for ci in monster.condition_immunities
                                 if c.lower() in ci.lower()}
    strikes: Dict[str, Strike] = {}
    for f in monster.actions:
        if f.name.lower().startswith("multiattack"):
            continue
        s = parse_strike(f.name, f.description)
        if s:
            strikes[s.name] = s
    for f in monster.actions:
        if f.name.lower().startswith("multiattack"):
            side.multiattack = parse_multiattack(f.description, strikes)
        elif f.name.lower().startswith("spellcasting"):
            _spellcasting(side, f.description, spell_lookup, strikes)
    side.strikes = list(strikes.values())
    for f in monster.legendary_actions or []:
        clean = f.description
        for name in strikes:
            if re.search(rf"\b{re.escape(name)}\b", clean) and re.search(r"makes? (one|an?)\b|attack", clean, re.I):
                side.legendary.append(name)
                break
    for group in (monster.traits, monster.bonus_actions, monster.reactions):
        for f in group or []:
            side.traits.append((f.name, f.description))
    for name, text in side.traits:
        low = name.lower()
        m = re.search(r"legendary resistance\s*\((\d+)", low)
        if m:
            side.legendary_resistance = int(m.group(1))
        if low.startswith("magic resistance"):
            side.magic_resistance = True
        if low.startswith("regeneration"):
            side.regeneration = number_after(text, r"regains?\s+(\d+)\s+hit points", 0)
    return side


def _spellcasting(side: Side, text: str, spell_lookup, strikes: Dict[str, Strike]) -> None:
    """The spells in a monster's Spellcasting entry that deal damage, as strikes with their daily uses."""
    from character_rolls import parse_spell
    dc = number_after(text, r"spell save DC\s*(\d+)", 0)
    atk = number_after(text, r"\+(\d+)\s*to hit with spell attacks", 0)
    usage = "at will"
    per_day = 0
    for line in re.split(r"\n", text):
        head = re.match(r"\s*(at will|\d+\s*/\s*day(?: each)?)\s*:", line, re.IGNORECASE)
        if head:
            h = head.group(1).lower()
            usage = "at will" if h.startswith("at") else "day"
            per_day = number_after(h, r"(\d+)", 0)
        for m in re.finditer(r"\[\[spell:([^\]|]+)(?:\|[^\]]*)?\]\](?:\s*\(level (\d+) version\))?", line):
            name = m.group(1).strip()
            spell = spell_lookup(name)
            side.spell_texts[name] = getattr(spell, "description", "") if spell else ""
            info = parse_spell(spell) if spell else None
            if info is None or info.healing or not info.dice:
                continue
            level = int(m.group(2)) if m.group(2) else max(1, info.level)
            count, sides, flat = info.dice
            if info.slot_step and level > info.level:
                step_c, step_s, from_level = info.slot_step
                count += (level - max(info.level, from_level)) * step_c
            strike = Strike(name=f"{name} (spell)", kind="attack" if info.attack else ("save" if info.save else "auto"),
                            attack_bonus=atk, save_ability=info.save, save_dc=dc, half_on_save=info.half,
                            components=[(count, sides, flat, info.damage_type or "force")], melee=False,
                            range_ft=60, uses=usage, per_day=per_day, is_spell=True,
                            slot_level=0)
            strikes[strike.name] = strike


def side_from_custom(name: str, ac: int, hp: int, attack_bonus: int, damage: str, attacks: int = 1,
                     speed: int = 30, reach: int = 5, range_ft: int = 0, damage_type: str = "slashing") -> Side:
    """A creature typed in by hand: one kind of attack, repeated."""
    from character_rolls import parse_damage
    terms, flat, words = parse_damage(damage)
    comps = [(t.count, t.sides, 0, damage_type) for t in terms]
    if comps:
        c, s, _f, t = comps[0]
        comps[0] = (c, s, flat, t)
    else:
        comps = [(0, 2, flat, damage_type)]
    strike = Strike(name="Attack", attack_bonus=attack_bonus, components=comps, melee=not range_ft, reach=reach,
                    range_ft=range_ft)
    return Side(name=name, kind="custom", ac=ac, hp=hp, speeds={"walk": speed}, strikes=[strike],
                multiattack=[[("Attack", max(1, attacks))]])


# ----------------------------------------------------------------------------- working a strike out against a target

def _term_dist(count: int, sides: int, flat: int) -> Dist:
    base = DiceTerm(count, sides).distribution() if count > 0 else Dist.point(0)
    return base.shift(flat)


def component_dist(components, target: Defender, crit: bool = False) -> Dist:
    total = Dist.point(0)
    for count, sides, flat, dtype in components:
        c = count * 2 if crit else count
        part = _term_dist(c, sides, flat)
        total = total + adjust(part, dtype, target)
    return total


def attack_chances(bonus: int, ac: int) -> Tuple[float, float, float]:
    """(miss, hit, crit) for an attack with ``bonus`` against ``ac``: a 1 misses, a 20 hits and crits."""
    hit = sum(1 for n in range(2, 20) if n + bonus >= ac) / 20.0
    return 1.0 - hit - 0.05, hit, 0.05


def make_action(strike: Strike, target: Defender) -> Action:
    act = Action(name=strike.name, avg=0.0, dist=Dist.point(0), kind=strike.kind, uses=strike.uses,
                 recharge=strike.recharge, per_day=strike.per_day, slot_level=strike.slot_level,
                 conditions=list(strike.conditions), is_spell=strike.is_spell, melee=strike.melee, reach=strike.reach,
                 range_ft=strike.range_ft)
    if strike.kind == "attack":
        miss, hit, crit = attack_chances(strike.attack_bonus, target.ac)
        normal = component_dist(strike.components, target, False)
        crit_d = component_dist(strike.components, target, True)
        act.dist = Dist.mixture([(miss, Dist.point(0)), (hit, normal), (crit, crit_d)])
        act.hit_chance = hit + crit
    elif strike.kind == "save":
        full = component_dist(strike.components, target, False)
        success = full.halved() if strike.half_on_save else Dist.point(0)
        bonus = target.saves.get(strike.save_ability, 0)
        p_save = save_success_chance(bonus, strike.save_dc, target.magic_resistance and strike.is_spell)
        act.fail_dist, act.success_dist, act.p_save = full, success, p_save
        act.dist = Dist.mixture([(1 - p_save, full), (p_save, success)])
    else:
        act.dist = component_dist(strike.components, target, False)
    act.avg = act.dist.mean()
    return act


def plans_for_monster(side: Side, target: Defender) -> Prepared:
    actions: Dict[str, Action] = {s.name: make_action(s, target) for s in side.strikes}
    plans: List[Plan] = []
    used_in_multi: Set[str] = set()
    for combo in side.multiattack:
        parts = [(actions[n], c) for n, c in combo if n in actions]
        if not parts:
            continue
        used_in_multi |= {a.name for a, _ in parts}
        label = "Multiattack: " + ", ".join(f"{a.name} x{c}" if c > 1 else a.name for a, c in parts)
        plans.append(Plan(label, parts))
    for name, act in actions.items():
        free = act.uses == "at will"
        if act.uses == "recharge":
            plans.append(Plan(act.name + f" (Recharge {act.recharge}+)", [(act, 1)], f"recharge:{act.name}"))
        elif act.uses == "day":
            plans.append(Plan(act.name + f" ({act.per_day}/day)", [(act, 1)], f"day:{act.name}"))
        elif not side.multiattack or name not in used_in_multi:
            plans.append(Plan(act.name, [(act, 1)]))
        elif free and not any(p.name == name for p in plans):
            plans.append(Plan(act.name, [(act, 1)]))
    prepared = Prepared(side, [p for p in plans if p.avg > 0 or any(a.conditions for a, _ in p.parts)])
    prepared.blocked = [p.name for p in plans if p.avg <= 0 and not any(a.conditions for a, _ in p.parts)]
    prepared.legendary = [actions[n] for n in side.legendary if n in actions]
    if not prepared.plans:
        prepared.notes.append("No damaging attacks could be read from this stat block.")
    return prepared


# ----------------------------------------------------------------------------- the fight

@dataclass
class _State:
    hp: int
    prepared: Prepared
    defender: Defender
    lr: int
    recharged: Dict[str, bool] = field(default_factory=dict)
    day_left: Dict[str, int] = field(default_factory=dict)
    slots: Dict[int, int] = field(default_factory=dict)


def _initial_state(p: Prepared, hp: int) -> _State:
    st = _State(hp, p, p.side.defender, p.side.legendary_resistance)
    st.slots = dict(p.side.spell_slots)
    for plan in p.plans:
        kind, _, key = plan.resource.partition(":")
        if kind == "recharge":
            st.recharged[key] = True
        elif kind == "day":
            st.day_left[key] = plan.parts[0][0].per_day or 1
    return st


def _available(plan: Plan, st: _State) -> bool:
    kind, _, key = plan.resource.partition(":")
    if kind == "recharge":
        return st.recharged.get(key, False)
    if kind == "day":
        return st.day_left.get(key, 0) > 0
    if kind == "slot":
        return st.slots.get(int(key), 0) > 0
    return True


def _use_action(act: Action, user: _State, target: _State, rng: random.Random) -> int:
    if act.kind == "save" and act.fail_dist is not None:
        if rng.random() < act.p_save:
            return act.success_dist.sample(rng) if act.success_dist else 0
        if target.lr > 0:                                  # legendary resistance: choose to succeed
            target.lr -= 1
            return act.success_dist.sample(rng) if act.success_dist else 0
        return act.fail_dist.sample(rng)
    return act.dist.sample(rng)


def _take_turn(me: _State, foe: _State, rng: random.Random) -> None:
    if me.defender.regeneration:
        me.hp = min(me.prepared.side.hp, me.hp + me.defender.regeneration)
    for key in list(me.recharged):                         # recharge rolls at the start of the turn
        if not me.recharged[key]:
            need = next((a.recharge for p in me.prepared.plans for a, _ in p.parts if a.name == key), 6)
            if rng.randint(1, 6) >= need:
                me.recharged[key] = True
    options = [p for p in me.prepared.plans if _available(p, me)]
    if not options:
        return
    plan = max(options, key=lambda p: p.avg)
    kind, _, key = plan.resource.partition(":")
    if kind == "recharge":
        me.recharged[key] = False
    elif kind == "day":
        me.day_left[key] -= 1
    elif kind == "slot":
        me.slots[int(key)] -= 1
    for act, count in plan.parts:
        for _ in range(count):
            if foe.hp <= 0:
                return
            foe.hp -= _use_action(act, me, foe, rng)


def simulate(a: Prepared, b: Prepared, trials: int = 4000, seed: int = 20240601, hp_a: Optional[int] = None,
             hp_b: Optional[int] = None) -> dict:
    """Run the fight ``trials`` times. Initiative, recharge and daily uses are rolled; the creatures always do their
    best available plan. Returns win counts, round counts and what is left."""
    rng = random.Random(seed)
    wins = {"a": 0, "b": 0, "draw": 0}
    rounds_win: List[int] = []
    left_a: List[int] = []
    left_b: List[int] = []
    first = 0
    for _ in range(trials):
        sa = _initial_state(a, hp_a if hp_a is not None else a.side.hp)
        sb = _initial_state(b, hp_b if hp_b is not None else b.side.hp)
        ia = rng.randint(1, 20) + a.side.initiative
        ib = rng.randint(1, 20) + b.side.initiative
        a_first = ia > ib or (ia == ib and (a.side.initiative > b.side.initiative or (
            a.side.initiative == b.side.initiative and rng.random() < 0.5)))
        first += a_first
        order = [(sa, sb), (sb, sa)] if a_first else [(sb, sa), (sa, sb)]
        rounds = 0
        while sa.hp > 0 and sb.hp > 0 and rounds < MAX_ROUNDS:
            rounds += 1
            for me, foe in order:
                if me.hp <= 0 or foe.hp <= 0:
                    continue
                _take_turn(me, foe, rng)
                if foe.hp > 0 and foe.prepared.legendary and me.hp > 0:   # the other side's legendary action
                    for act in foe.prepared.legendary[:1]:
                        me.hp -= _use_action(act, foe, me, rng)
        if sa.hp <= 0 and sb.hp <= 0:
            wins["draw"] += 1
        elif sb.hp <= 0 < sa.hp:
            wins["a"] += 1
            rounds_win.append(rounds)
            left_a.append(sa.hp)
        elif sa.hp <= 0 < sb.hp:
            wins["b"] += 1
            rounds_win.append(rounds)
            left_b.append(sb.hp)
        else:
            wins["draw"] += 1
    n = float(trials)
    return {"a": wins["a"] / n, "b": wins["b"] / n, "draw": wins["draw"] / n, "trials": trials,
            "first_a": first / n,
            "rounds_mean": (sum(rounds_win) / len(rounds_win)) if rounds_win else float(MAX_ROUNDS),
            "rounds_median": sorted(rounds_win)[len(rounds_win) // 2] if rounds_win else MAX_ROUNDS,
            "rounds": rounds_win,
            "a_left": (sum(left_a) / len(left_a)) if left_a else 0.0,
            "b_left": (sum(left_b) / len(left_b)) if left_b else 0.0}


# ----------------------------------------------------------------------------- characters

# resistances a species gives that a sheet does not record
SPECIES_RESISTANCES = {"dwarf": "poison", "duergar": "poison", "stout": "poison", "tiefling": "fire",
                       "aasimar": "necrotic, radiant", "warforged": "poison", "yuan-ti": "poison",
                       "autognome": "poison", "plasmoid": "acid, poison", "firenewt": "", "hill dwarf": "poison"}

# class features worth listing as tide turners: (feature id in character_context, what to say)
FEATURE_NOTES = [
    ("rage", "Rage: resistance to bludgeoning, piercing and slashing damage and bonus damage while raging."),
    ("danger_sense", "Danger Sense: advantage on Dexterity saves."),
    ("sneak_attack", "Sneak Attack: big extra damage when it has advantage or an ally nearby."),
    ("indomitable", "Indomitable: can reroll a failed saving throw."),
    ("indomitable_might", "Indomitable Might."),
    ("stroke_of_luck", "Stroke of Luck: can turn a missed d20 test into a 20."),
    ("halfling_luck", "Halfling Luck: rerolls natural 1s."),
    ("lucky", "Lucky: Luck Points give advantage / rerolls on key rolls."),
    ("disciplined_survivor", "Disciplined Survivor: proficient in every save and can reroll failed ones."),
    ("mage_slayer", "Mage Slayer: can turn a failed Int, Wis or Cha save into a success."),
    ("tactical_mind", "Tactical Mind: Second Wind can rescue a failed ability check."),
    ("noble_scion", "Noble Scion: can turn a failed d20 test into a success."),
    ("tides_of_chaos", "Tides of Chaos: advantage on a d20 test."),
    ("divine_smite", "Divine Smite: burst damage by spending spell slots."),
    ("aura_of_protection", "Aura of Protection: bonus to saving throws."),
    ("stroke_of_luck", "Stroke of Luck."),
    ("hexblades_curse", "Hexblade's Curse: extra damage and critical hits on 19-20 against its target."),
    ("empowered_spell", "Empowered Spell: rerolls damage dice."),
]
FEATURE_TURNERS = {
    "Stunning Strike": "Monk: Stunning Strike can stun (Constitution save).",
    "Lay on Hands": "Lay on Hands: a pool of healing it can use in a fight.",
    "Second Wind": "Second Wind: heals itself in the fight.",
    "Action Surge": "Action Surge: an extra action for burst damage.",
    "Uncanny Dodge": "Uncanny Dodge: halves one hit.",
    "Evasion": "Evasion: takes no damage from many area effects it saves against.",
    "Wild Shape": "Wild Shape: a second set of hit points and attacks.",
    "Cunning Strike": "Cunning Strike: Sneak Attack dice can inflict poison, trip or daze.",
    "Channel Divinity": "Channel Divinity: situational powers (turn undead, smiting, healing).",
    "Bardic Inspiration": "Bardic Inspiration: bonus dice.",
    "Relentless Rage": "Relentless Rage: can stay up at 0 hit points.",
    "Second Chance": "Second Chance.",
}


def _parse_types(text: str) -> Set[str]:
    return {t for t in DAMAGE_TYPES if t in (text or "").lower()}


def _parse_conditions(text: str) -> Set[str]:
    return {c for c in CONDITIONS if c.lower() in (text or "").lower()}


def side_from_character(character, sheet, lookups, options: Optional[dict] = None) -> Side:
    """A :class:`Side` from a character and its sheet, using the Dice Analyzer's engine for every number."""
    from character_rolls import CharacterAnalyzer, parse_damage
    from character_context import ABILITIES as ABS
    opts = {"hp": "max", "boosts": True, "raging": False, "use_slots": True, "resist": "", "immune": "",
            "cond_immune": ""}
    opts.update(options or {})
    analyzer = CharacterAnalyzer(character, sheet, lookups)
    ctx = analyzer.ctx
    hp = sheet.hit_points.current if opts["hp"] == "current" else sheet.hit_points.maximum
    side = Side(name=character.name, kind="character", ac=sheet.armor_class, hp=max(1, hp),
                speeds={"walk": sheet.speed},
                initiative=ctx.mod("DEX") + getattr(sheet, "initiative_bonus", 0),
                level_text=character.display_classes())
    for ab in ABS:
        side.saves[ab] = ctx.mod(ab) + (ctx.prof if ctx.save_proficient(ab) else 0)
    resist = _parse_types(opts["resist"])
    for key, text in SPECIES_RESISTANCES.items():
        if key in ctx.lineage:
            resist |= _parse_types(text)
    if opts["raging"] and ctx.lvl("Barbarian"):
        resist |= {"bludgeoning", "piercing", "slashing"}
    side.resist = resist
    side.immune = _parse_types(opts["immune"])
    side.condition_immunities = _parse_conditions(opts["cond_immune"])
    side.magic_resistance = ctx.has("spell_resistance")
    slots = _spell_slots(character)
    side.spell_slots = slots if opts["use_slots"] else {}
    infos = analyzer.spells()
    side.spells_known = infos
    names = []
    for attr in ("known_spells", "prepared_spells", "subclass_spells"):
        for n in getattr(character, attr, []) or []:
            if n not in names:
                names.append(n)
    for n in names:
        spell = lookups.spell(n)
        if spell is not None:
            side.spell_texts[n] = getattr(spell, "description", "") or ""
            side.spell_levels[n] = int(getattr(spell, "level", 0) or 0)
    side.features = _character_features(analyzer)

    def prepare(defender: Defender) -> Prepared:
        return _prepare_character(side, analyzer, sheet, defender, opts)

    side.prepare_character = prepare
    return side


def _spell_slots(character) -> Dict[int, int]:
    """Spell slots by level (pact slots counted at their level)."""
    out: Dict[int, int] = {}
    try:
        from spell_slots import get_max_spell_slots, get_warlock_level, get_warlock_pact_slots
        levels = character.get_class_levels_tuple()
        out = dict(get_max_spell_slots(levels, character.get_eldritch_knight_level()))
        w = get_warlock_level(levels)
        if w:
            count, level = get_warlock_pact_slots(w)
            out[level] = out.get(level, 0) + count
    except Exception:
        out = {}
    custom = getattr(character, "custom_max_slots", None)
    if custom:
        out = {int(k): int(v) for k, v in custom.items() if int(v) > 0}
    return out


def _character_features(analyzer) -> List[str]:
    ctx = analyzer.ctx
    out = []
    seen = set()
    for fid, text in FEATURE_NOTES:
        if text not in seen and ctx.has(fid):
            out.append(text)
            seen.add(text)
    for fid, label, source in analyzer.feature_report():
        if source == "sheet" and label in FEATURE_TURNERS and FEATURE_TURNERS[label] not in seen:
            out.append(FEATURE_TURNERS[label])
    if ctx.lvl("Monk") >= 5:
        out.append(FEATURE_TURNERS["Stunning Strike"])
    if ctx.lvl("Paladin") >= 1:
        out.append(FEATURE_TURNERS["Lay on Hands"])
    if ctx.lvl("Fighter") >= 1:
        out.append(FEATURE_TURNERS["Second Wind"])
    if ctx.lvl("Fighter") >= 2:
        out.append(FEATURE_TURNERS["Action Surge"])
    if ctx.lvl("Rogue") >= 5:
        out.append(FEATURE_TURNERS["Uncanny Dodge"])
    if ctx.lvl("Rogue") >= 7 or ctx.lvl("Monk") >= 7:
        out.append(FEATURE_TURNERS["Evasion"])
    if ctx.lvl("Druid") >= 2:
        out.append(FEATURE_TURNERS["Wild Shape"])
    if ctx.lvl("Rogue") >= 5:
        out.append(FEATURE_TURNERS["Cunning Strike"])
    if ctx.lvl("Barbarian") >= 11:
        out.append(FEATURE_TURNERS["Relentless Rage"])
    return list(dict.fromkeys(out))


def _view(analysis, *keys):
    for key in keys:
        for v in analysis.views:
            if v.key == key:
                return v
    return analysis.views[-1]


def _percent(facts, label: str) -> float:
    for k, v in facts:
        if k.startswith(label):
            try:
                return float(str(v).rstrip("%")) / 100.0
            except ValueError:
                return 0.0
    return 0.0


def _prepare_character(side: Side, analyzer, sheet, defender: Defender, opts: dict) -> Prepared:
    from character_rolls import parse_damage
    ctx = analyzer.ctx
    rolls = {r.key: r for r in analyzer.rolls()}
    prepared = Prepared(side, [])
    boost = {}
    if opts["boosts"]:
        boost = {"sneak": True, "rage": bool(opts["raging"]) or True}
    n_attacks = ctx.attacks_per_turn()
    # ---- the weapon attacks on the sheet
    for index, entry in enumerate(getattr(sheet, "attacks", []) or []):
        r = rolls.get(f"attack:{index}")
        if r is None:
            continue
        try:
            _t, _f, words = parse_damage(entry.get("damage", ""))
        except Exception:
            words = ""
        dtype = next((w for w in words.lower().split() if w in DAMAGE_TYPES), "slashing")
        state = {k: v for k, v in boost.items() if any(o.key == k for o in r.options)}
        state.update(target=defender.ac, attacks=n_attacks)
        analysis = r.analyze(state)
        view = _view(analysis, "per_turn", "per_attack", "attack")
        if view.key == "attack":
            continue
        dist = adjust(view.dist, dtype, defender)
        ranged = next((o.default for o in r.options if o.key == "use"), "Melee") == "Ranged"
        hit = _percent(analysis.views[0].facts, "Chance to hit")
        act = Action(name=r.name, avg=dist.mean(), dist=dist, kind="attack", hit_chance=hit, melee=not ranged,
                     reach=5, range_ft=80 if ranged else 0)
        label = f"{r.name} x{n_attacks}" if n_attacks > 1 and view.key == "per_turn" else r.name
        prepared.plans.append(Plan(label, [(act, 1)]))
    # ---- spells
    max_slot = max(side.spell_slots or {0: 0})
    for info in side.spells_known:
        r = rolls.get(f"spell:{info.name}")
        if r is None or info.healing:
            continue
        variants = [info.level] if info.level == 0 else [info.level]
        if info.level and info.slot_step and max_slot > info.level and side.spell_slots:
            variants.append(max_slot)
        rows = []
        for level in dict.fromkeys(variants):
            if info.level and not side.spell_slots.get(level):
                if level == info.level:
                    continue
            state = {"slot": str(level)} if info.level else {}
            if info.attack:
                state["target"] = defender.ac
            elif info.save:
                state["target"] = defender.saves.get(info.save, 0)
                state["target_mode"] = "Advantage" if defender.magic_resistance else "Normal"
            analysis = r.analyze(state)
            view = _view(analysis, "per_cast", "expected", "auto")
            dist = adjust(view.dist, info.damage_type, defender)
            act = Action(name=info.name + (f" (level {level})" if level != info.level else ""), avg=dist.mean(),
                         dist=dist, kind="attack" if info.attack else ("save" if info.save else "auto"),
                         is_spell=True, slot_level=level if info.level else 0, melee=False, range_ft=60)
            if info.attack:
                act.hit_chance = _percent(analysis.views[0].facts, "Chance to hit")
            elif info.save:
                failed = _view(analysis, "failed")
                dc = int(dict(failed.facts).get("Save DC", 10))
                act.fail_dist = adjust(failed.dist, info.damage_type, defender)
                act.success_dist = act.fail_dist.halved() if info.half else Dist.point(0)
                act.p_save = save_success_chance(defender.saves.get(info.save, 0), dc, defender.magic_resistance)
                act.dist = Dist.mixture([(1 - act.p_save, act.fail_dist), (act.p_save, act.success_dist)])
                act.avg = act.dist.mean()
            resource = f"slot:{level}" if info.level else ""
            prepared.plans.append(Plan(act.name, [(act, 1)], resource))
            rows.append((level, act))
        base = rows[0][1] if rows else None
        if base is not None:
            row = {"name": info.name, "level": info.level, "avg": base.avg,
                   "per_slot": (base.avg / info.level) if info.level else None,
                   "kind": base.kind, "damage_type": info.damage_type}
            if len(rows) > 1:
                top = rows[-1]
                row["upcast"] = (top[0], top[1].avg, top[1].avg / top[0])
            prepared.spells_table.append(row)
    prepared.spells_table.sort(key=lambda r: (r["level"], -r["avg"]))
    for row in prepared.spells_table:
        cur = prepared.spell_levels.get(row["level"])
        if cur is None or row["avg"] > cur["avg"]:
            prepared.spell_levels[row["level"]] = row
    prepared.blocked = [p.name for p in prepared.plans if p.avg <= 0]
    prepared.plans = [p for p in prepared.plans if p.avg > 0]
    if not prepared.plans:
        prepared.notes.append("This character has no attacks or damaging spells to use: add attacks to its sheet.")
    return prepared


# ----------------------------------------------------------------------------- tide turners

CONTROL_SPELL_WORDS = ["banish", "polymorph", "imprison", "maze", "plane shift", "forcecage", "wall of force",
                       "power word", "finger of death", "disintegrate", "sleep", "fear", "slow", "blind", "hold ",
                       "confus", "dominate", "charm", "command", "web", "entangle", "hypnotic", "color spray",
                       "stinking", "hideous", "feeblemind", "counterspell", "dispel", "silence", "sleet", "faerie fire",
                       "hex", "bane", "tasha", "glyph", "grease"]
HEALING_WORDS = ["regenerat", "rejuvenat", "heal", "second wind", "lay on hands", "regains", "reform", "life drain",
                 "drain life", "vampiric", "revive"]
DEFENCE_WORDS = ["legendary resistance", "magic resistance", "parry", "shield", "evasion", "uncanny dodge",
                 "damage threshold", "absorb", "reflect", "protective", "mirror", "displace", "blur", "invisib",
                 "incorporeal", "ethereal", "teleport", "misty step", "shadow step", "phase", "flyby", "nimble escape"]


def _speed(side: Side) -> Tuple[int, int]:
    walk = side.speeds.get("walk", 0)
    best = max(side.speeds.values() or [walk])
    return walk, best


def tide_turners(a: Prepared, b: Prepared) -> Dict[str, List[str]]:
    """Things that can swing the fight but are not in the averages, for each side (``a`` and ``b``)."""
    out: Dict[str, List[str]] = {"a": [], "b": []}
    sides = {"a": (a, b), "b": (b, a)}
    for key, (me, foe) in sides.items():
        side, other = me.side, foe.side
        notes = out[key]
        # conditions its actions can inflict
        for plan in me.plans:
            for act, _ in plan.parts:
                if act.conditions:
                    conds = ", ".join(act.conditions)
                    immune = [c for c in act.conditions if c in other.condition_immunities]
                    extra = ""
                    if act.kind == "save":
                        extra = " (a failed save)"
                    elif act.kind == "attack":
                        extra = " (on a hit)"
                    flag = f"  [{other.name} is immune to {', '.join(immune)}]" if immune else ""
                    notes.append(f"{act.name} can inflict {conds}{extra}.{flag}")
        for strike in side.strikes:
            pass
        # debuff and control spells (characters list every spell they know)
        for name, text in side.spell_texts.items():
            conds = [c for c in CONDITIONS if re.search(rf"\b{c}\b", text or "", re.IGNORECASE)
                     and re.search(rf"(has|have|gains?|becomes?|is|with)\s+the\s+{c}\b|\b{c}\s+condition", text or "",
                                   re.IGNORECASE)]
            lowname = name.lower() + " "
            keyword = any(w in lowname for w in CONTROL_SPELL_WORDS)
            if conds or keyword:
                immune = [c for c in conds if c in other.condition_immunities]
                flag = f"  [{other.name} is immune to {', '.join(immune)}]" if immune else ""
                level = side.spell_levels.get(name)
                lvl = "cantrip" if level == 0 else f"level {level}" if level else "spell"
                save = re.search(r"(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma) saving throw",
                                 text or "", re.IGNORECASE)
                how = f", {save.group(1)} save" if save else ""
                effect = f" - inflicts {', '.join(conds)}" if conds else " - a control or debuff spell"
                notes.append(f"Spell: {name} ({lvl}{how}){effect}.{flag}")
        for text in side.features:
            notes.append(text)
        # traits and abilities by name
        for name, text in side.traits:
            low = name.lower()
            if low.startswith("legendary resistance"):
                notes.append(f"{name}: can choose to succeed on failed saving throws, so save-or-suck effects often "
                             f"fail.")
            elif any(w in low for w in HEALING_WORDS):
                amount = f" ({side.regeneration} hit points a turn)" if low.startswith("regeneration") and \
                    side.regeneration else ""
                notes.append(f"{name}: recovers hit points{amount}.")
            elif any(w in low for w in DEFENCE_WORDS):
                notes.append(f"{name}: a defensive ability the averages ignore.")
            elif _parse_conditions(text) and "saving throw" in (text or "").lower() and not low.startswith("multiattack"):
                notes.append(f"{name}: involves {', '.join(sorted(_parse_conditions(text)))}.")
        # burst abilities
        for plan in me.plans:
            if plan.resource.startswith(("recharge", "day")):
                notes.append(f"{plan.name}: averages {plan.avg:.0f} damage on a use - it can open or end the fight.")
        # damage it cannot do to the other side
        for name in me.blocked:
            notes.append(f"{name} does no damage to {other.name} (it is immune).")
        # mobility and range
        walk_a, best_a = _speed(side)
        walk_b, best_b = _speed(other)
        if "fly" in side.speeds and "fly" not in other.speeds and other.best_range() < 30:
            notes.append(f"Flies ({side.speeds['fly']} ft.) while {other.name} has no ranged attack: it can stay out of "
                         f"reach.")
        elif best_a - best_b >= 20 and walk_a - walk_b >= 10:
            notes.append(f"Much faster ({walk_a} ft. against {walk_b} ft.): it can choose when to fight or flee.")
        if side.best_range() >= 30 and other.best_range() < 30 and other.best_reach() <= 10 and not any(
                "fly" in s.speeds for s in (other,)):
            notes.append(f"Has a ranged attack ({side.best_range()} ft.) and {other.name} does not: it can attack "
                         f"from a distance.")
        if side.best_reach() >= other.best_reach() + 5 and side.best_reach() > 5:
            notes.append(f"Longer reach ({side.best_reach()} ft. against {other.best_reach()} ft.).")
    for key in out:
        out[key] = list(dict.fromkeys(out[key]))
    return out


# ----------------------------------------------------------------------------- putting it together

@dataclass
class Result:
    a: Prepared
    b: Prepared
    sim: dict
    turners: Dict[str, List[str]]
    kill_rounds: Dict[str, float]          # rounds each side needs on average (hit points / sustained damage)
    notes: List[str] = field(default_factory=list)


def prepare(side: Side, opponent: Side) -> Prepared:
    if side.prepare_character is not None:
        return side.prepare_character(opponent.defender)
    return plans_for_monster(side, opponent.defender)


def analyze(a: Side, b: Side, trials: int = 4000, seed: int = 20240601) -> Result:
    pa, pb = prepare(a, b), prepare(b, a)
    sim = simulate(pa, pb, trials, seed)
    kills = {"a": (b.hp / pa.sustained()) if pa.sustained() > 0 else math.inf,
             "b": (a.hp / pb.sustained()) if pb.sustained() > 0 else math.inf}
    notes = list(pa.notes) + list(pb.notes)
    notes.append("Each creature uses its best available plan every round: attacks and multiattacks for free, "
                 "breath weapons when they recharge, daily abilities and spell slots until they run out.")
    notes.append("Bonus actions, reactions, terrain, movement, positioning and abilities that need a decision (healing "
                 "an ally, a grapple, a shove) are not simulated: see the tide turners.")
    if a.legendary_resistance or b.legendary_resistance:
        notes.append("Legendary Resistance is used on every failed saving throw until it runs out.")
    return Result(pa, pb, sim, tide_turners(pa, pb), kills, notes)
