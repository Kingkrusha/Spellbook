"""
Challenge Rating check for a homebrew monster.

No UI. ``analyze(monster)`` reads the numbers off a stat block - armor class, hit points (counting resistances,
immunities and regeneration as extra hit points), damage per round, attack bonus and save DC - and compares
them with the "Monster Statistics by Challenge Rating" table that the Dungeon Master's Guide builds creatures
from, and with the monsters already in the collection.

* The **defensive CR** comes from effective hit points, moved up or down one step per two points of armor class
  above or below what that CR expects.
* The **offensive CR** comes from damage per round, moved by the attack bonus (or save DC) in the same way.
* The **suggested CR** is the average of the two.

The stat block is read with the same parser the Matchup tool uses (``matchup.parse_strike`` and friends), so
Multiattack, recharge powers, daily uses and spells in a Spellcasting entry are understood the same way.
If the monster's own CR is set, the report also lists every number that is higher (or lower) than is typical
for it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import matchup as M
from monster import CR_OPTIONS, Monster, cr_to_number, normalize_cr

# --------------------------------------------------------------------------- the table

@dataclass(frozen=True)
class Row:
    cr: str
    prof: int
    ac: int
    hp_lo: int
    hp_hi: int
    attack: int
    dmg_lo: int
    dmg_hi: int
    dc: int


# CR, proficiency bonus, armor class, hit points (low, high), attack bonus, damage per round (low, high), save DC
_TABLE = """
0   2 13 1   6    3  0   1   13
1/8 2 13 7   35   3  2   3   13
1/4 2 13 36  49   3  4   5   13
1/2 2 13 50  70   3  6   8   13
1   2 13 71  85   3  9   14  13
2   2 13 86  100  3  15  20  13
3   2 13 101 115  4  21  26  13
4   2 14 116 130  5  27  32  14
5   3 15 131 145  6  33  38  15
6   3 15 146 160  6  39  44  15
7   3 15 161 175  6  45  50  15
8   3 16 176 190  7  51  56  16
9   4 16 191 205  7  57  62  16
10  4 17 206 220  7  63  68  16
11  4 17 221 235  8  69  74  17
12  4 17 236 250  8  75  80  17
13  5 18 251 265  8  81  86  18
14  5 18 266 280  8  87  92  18
15  5 18 281 295  8  93  98  18
16  5 18 296 310  9  99  104 18
17  6 19 311 325  10 105 110 19
18  6 19 326 340  10 111 116 19
19  6 19 341 355  10 117 122 19
20  6 19 356 400  10 123 140 19
21  7 19 401 445  11 141 158 20
22  7 19 446 490  11 159 176 20
23  7 19 491 535  11 177 194 20
24  7 19 536 580  12 195 212 21
25  8 19 581 625  12 213 230 21
26  8 19 626 670  12 231 248 21
27  8 19 671 715  13 249 266 22
28  8 19 716 760  13 267 284 22
29  9 19 761 805  13 285 302 22
30  9 19 806 850  14 303 320 23
"""

TABLE: List[Row] = []
for _line in _TABLE.strip().splitlines():
    _p = _line.split()
    TABLE.append(Row(_p[0], *[int(x) for x in _p[1:]]))
assert [r.cr for r in TABLE] == CR_OPTIONS, "the table must list every CR"


def row_for(cr) -> Row:
    return TABLE[CR_OPTIONS.index(normalize_cr(cr))]


def cr_label(index: float) -> str:
    return CR_OPTIONS[max(0, min(len(CR_OPTIONS) - 1, int(round(index))))]


def _n(x: float) -> str:
    """A number for a sentence: whole when it nearly is, else one decimal."""
    return f"{x:.0f}" if abs(x - round(x)) < 0.25 else f"{x:.1f}"


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


# How many "pretend" monsters the DMG table counts for next to the real ones in the collection. The table is the
# only guide for CRs that few (or no) real monsters have; where the collection has dozens it takes over.
TABLE_WEIGHT = 6


@dataclass
class Band:
    """What is typical for one CR on one measure."""
    lo: float
    med: float
    hi: float
    n: int = 0              # real monsters behind it


def _quantile(values: Sequence[float], q: float) -> float:
    vals = sorted(values)
    if not vals:
        return 0.0
    pos = q * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = min(len(vals) - 1, lo + 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


class Reference:
    """The numbers a monster of each CR is expected to have.

    It starts from the DMG's table and, when given the official monsters of the collection, leans towards what they
    actually have: the 2024 Monster Manual keeps hit points well under the table at low levels, so judging a
    homebrew CR 1 against 71-85 hit points would call every real CR 1 monster weak. Each figure is a blend of
    the monsters' median and the table's value, weighted by how many monsters the CR has (``TABLE_WEIGHT`` of them
    stand for the table).
    """

    KEYS = ("ehp", "dmg", "ac", "attack", "dc")

    def __init__(self, monsters: Sequence[Monster] = (), spell_lookup: Callable[[str], object] = lambda n: None):
        self.samples: List[List[Tuple[Monster, dict]]] = [[] for _ in CR_OPTIONS]
        for m in monsters:
            if m.spell_only or not m.is_official:
                continue
            try:
                nums = monster_numbers(m, spell_lookup)
            except Exception:
                continue
            self.samples[CR_OPTIONS.index(normalize_cr(m.challenge_rating))].append((m, nums))
        self._bands: Dict[Tuple[int, str], Band] = {}
        self._mono: Dict[str, List[float]] = {}

    @property
    def official_count(self) -> int:
        return sum(len(s) for s in self.samples)

    def values(self, index: int, key: str) -> List[float]:
        return [n[key] for _m, n in self.samples[index] if n.get(key) is not None]

    @staticmethod
    def _table_band(row: Row, key: str) -> Tuple[float, float, float]:
        if key == "ehp":
            return row.hp_lo, (row.hp_lo + row.hp_hi) / 2.0, row.hp_hi
        if key == "dmg":
            return row.dmg_lo, (row.dmg_lo + row.dmg_hi) / 2.0, row.dmg_hi
        value = {"ac": row.ac, "attack": row.attack, "dc": row.dc}[key]
        return value - 1.0, float(value), value + 1.0

    def band(self, cr, key: str) -> Band:
        index = cr if isinstance(cr, int) else CR_OPTIONS.index(normalize_cr(cr))
        cached = self._bands.get((index, key))
        if cached is not None:
            return cached
        t_lo, t_med, t_hi = self._table_band(TABLE[index], key)
        vals = self.values(index, key)
        n = len(vals)
        if n == 0:
            band = Band(t_lo, t_med, t_hi, 0)
        else:
            w = n / (n + TABLE_WEIGHT)
            med = _quantile(vals, 0.5)
            if key in ("ehp", "dmg") and med > 0 and t_med > 0:
                blended = math.exp(w * math.log(med) + (1 - w) * math.log(t_med))
            else:
                blended = w * med + (1 - w) * t_med
            if n >= 4:
                lo = w * _quantile(vals, 0.10) + (1 - w) * t_lo
                hi = w * _quantile(vals, 0.90) + (1 - w) * t_hi
            else:
                lo, hi = t_lo, t_hi
            band = Band(min(lo, blended), blended, max(hi, blended), n)
        self._bands[(index, key)] = band
        return band

    def medians(self, key: str) -> List[float]:
        """The typical value for each CR, never falling as the CR rises (a rising curve to read a CR off)."""
        cached = self._mono.get(key)
        if cached is None:
            cached, top = [], 0.0
            for i in range(len(CR_OPTIONS)):
                top = max(top, self.band(i, key).med)
                cached.append(top)
            self._mono[key] = cached
        return cached

    def index_for(self, key: str, value: float) -> int:
        """The CR whose typical ``key`` is closest to ``value`` (comparing ratios for hit points and damage)."""
        meds = self.medians(key)
        best, best_gap = 0, None
        for i, med in enumerate(meds):
            if key in ("ehp", "dmg") and med > 0 and value > 0:
                gap = abs(math.log(value / med))
            else:
                gap = abs(value - med) / max(1.0, med)
            if best_gap is None or gap < best_gap - 1e-9:
                best, best_gap = i, gap
        # a value past the end of a flat stretch belongs to its first CR
        return best

    def peers(self, cr, exclude: str = "") -> List[Tuple[Monster, dict]]:
        index = CR_OPTIONS.index(normalize_cr(cr))
        return [(m, n) for m, n in self.samples[index] if m.name != exclude]


def _shift(diff: float) -> int:
    """One CR step per two points off, rounded towards zero."""
    return int(diff / 2)


# --------------------------------------------------------------------------- reading the stat block

# how much of the damage a typical party deals is of each type (for resistances and immunities that are
# not limited to non-magical attacks); the figures only need the right order of magnitude
_TYPE_SHARE = {"slashing": 0.17, "piercing": 0.15, "bludgeoning": 0.12, "fire": 0.14, "cold": 0.05, "lightning": 0.06,
               "thunder": 0.03, "acid": 0.03, "poison": 0.05, "necrotic": 0.05, "radiant": 0.06, "psychic": 0.04,
               "force": 0.05}
_PHYSICAL = ("bludgeoning", "piercing", "slashing")


def _mentions(items: Sequence[str]) -> Tuple[set, bool]:
    """(damage types named, whether the list limits itself to non-magical attacks)."""
    types, nonmagical = set(), False
    for item in items:
        low = item.lower()
        types |= {t for t in M.DAMAGE_TYPES if t in low}
        if "nonmagical" in low or "non-magical" in low or "not silvered" in low or "nonsilvered" in low \
                or "non-silvered" in low or "from nonmagical" in low:
            nonmagical = True
    return types, nonmagical


def _nonmagical_factor(cr_index: int) -> float:
    """DMG: resistance or immunity to non-magical weapon damage multiplies hit points by this much."""
    cr = cr_to_number(CR_OPTIONS[cr_index])
    if cr <= 4:
        return 2.0
    if cr <= 10:
        return 1.5
    if cr <= 16:
        return 1.25
    return 1.0


@dataclass
class Offense:
    per_round: float = 0.0               # average damage per round, every attack landing (the table's measure)
    best_plan: str = ""
    attack_bonus: Optional[int] = None   # of the attacks that matter
    save_dc: Optional[int] = None
    uses_attacks: bool = False
    uses_saves: bool = False
    detected: bool = False
    limited: List[str] = field(default_factory=list)       # recharge / daily powers worth a mention
    plan_text: str = ""                                    # "Multiattack (Slam x2)"
    conditions: List[str] = field(default_factory=list)    # conditions its attacks can inflict
    notes: List[str] = field(default_factory=list)


def _strike_raw(strike: M.Strike) -> float:
    """Average damage of one use if it lands in full (no misses, saves failed)."""
    total = 0.0
    for count, sides, flat, _dtype in strike.components:
        total += count * (sides + 1) / 2.0 + flat
    return total


def read_offense(monster: Monster, spell_lookup: Callable[[str], object] = lambda n: None) -> Offense:
    """Damage per round and the attack bonus / save DC behind it."""
    off = Offense()
    try:
        side = M.side_from_monster(monster, spell_lookup)
    except Exception as e:                                  # an odd stat block must not stop the editor
        off.notes.append(f"The attacks could not be read ({e}).")
        return off
    strikes = {s.name: s for s in side.strikes}
    if not strikes:
        off.notes.append("No damaging attacks could be read from the actions, so the CR is judged on defences alone.")
        return off
    off.detected = True

    plans: List[Tuple[str, float, str, List[Tuple[M.Strike, int]]]] = []       # (name, damage, resource, parts)
    used = set()
    for combo in side.multiattack:
        parts = [(strikes[n], c) for n, c in combo if n in strikes]
        if not parts:
            continue
        used |= {s.name for s, _ in parts}
        plans.append(("Multiattack", sum(_strike_raw(s) * c for s, c in parts), "", parts))
    for name, s in strikes.items():
        if s.uses == "at will" and (not side.multiattack or name not in used):
            plans.append((name, _strike_raw(s), "", [(s, 1)]))
        elif s.uses != "at will":
            plans.append((name, _strike_raw(s), s.uses, [(s, 1)]))
    free = [p for p in plans if not p[2]]
    limited = [p for p in plans if p[2]]
    best_free = max(free, key=lambda p: p[1]) if free else None
    best_limited = max(limited, key=lambda p: p[1]) if limited else None
    sustained = best_free[1] if best_free else 0.0
    if best_limited and best_limited[1] > sustained:
        # the DMG averages the first three rounds: the limited power once, then what is always available
        per_round = (best_limited[1] + 2 * sustained) / 3.0
        best = best_limited
        off.limited.append(best_limited[0])
    else:
        per_round = sustained
        best = best_free or best_limited
    # legendary actions: one extra attack a round, as the Matchup tool counts them
    legend = [strikes[n] for n in side.legendary if n in strikes]
    if legend:
        extra = max(_strike_raw(s) for s in legend)
        per_round += extra
        off.notes.append(f"Legendary actions add about {extra:.0f} damage a round.")
    off.per_round = per_round
    off.conditions = sorted({c for st in strikes.values() for c in st.conditions})
    if best:
        off.best_plan = best[0]
        parts = best[3]
        listing = ", ".join(f"{st.name} x{n}" if n > 1 else st.name for st, n in parts)
        off.plan_text = f"{best[0]} ({listing})" if best[0] == "Multiattack" else best[0]
        off.uses_attacks = any(s.kind == "attack" for s, _ in parts)
        off.uses_saves = any(s.kind == "save" for s, _ in parts)
        attacks = [s.attack_bonus for s, _ in parts if s.kind == "attack"]
        dcs = [s.save_dc for s, _ in parts if s.kind == "save" and s.save_dc]
        off.attack_bonus = max(attacks) if attacks else None
        off.save_dc = max(dcs) if dcs else None
    if off.attack_bonus is None:
        every = [s.attack_bonus for s in strikes.values() if s.kind == "attack"]
        off.attack_bonus = max(every) if every else None
    if off.save_dc is None:
        every = [s.save_dc for s in strikes.values() if s.kind == "save" and s.save_dc]
        off.save_dc = max(every) if every else None
    return off


@dataclass
class Defense:
    ac: int = 10
    hp: int = 1
    effective_hp: float = 1.0
    effective_ac: float = 10.0
    hp_multiplier: float = 1.0
    notes: List[str] = field(default_factory=list)
    resist_count: int = 0
    immune_count: int = 0
    condition_immunities: int = 0
    save_proficiencies: int = 0


def read_defense(monster: Monster) -> Defense:
    d = Defense(ac=int(monster.ac), hp=int(monster.hp))
    d.effective_hp = float(max(1, monster.hp))
    d.effective_ac = float(monster.ac)
    provisional = table_reference().index_for("ehp", d.effective_hp)

    res_types, res_nonmagic = _mentions(monster.damage_resistances)
    imm_types, imm_nonmagic = _mentions(monster.damage_immunities)
    d.resist_count, d.immune_count = len(res_types), len(imm_types)
    d.condition_immunities = len(monster.condition_immunities)

    multiplier = 1.0
    nonmagical_phys = (res_nonmagic and res_types & set(_PHYSICAL)) or (imm_nonmagic and imm_types & set(_PHYSICAL))
    if nonmagical_phys:
        factor = _nonmagical_factor(provisional)
        if factor > 1.0:
            multiplier *= factor
            d.notes.append(f"Resistance or immunity to non-magical weapon damage counts as x{factor:g} hit points "
                           f"at this level.")
        elif factor == 1.0:
            d.notes.append("Resistance to non-magical weapon damage does not add hit points at this level "
                           "(characters have magic weapons by now).")
    # everything else: how much of the damage a party deals is turned away
    reduction = 0.0
    total = sum(_TYPE_SHARE.values())
    for t, share in _TYPE_SHARE.items():
        if nonmagical_phys and t in _PHYSICAL:
            continue
        if t in imm_types:
            reduction += share / total * 0.9
        elif t in res_types:
            reduction += share / total * 0.5
    if any("all damage" in s.lower() for s in monster.damage_resistances):
        reduction = max(reduction, 0.45)
    if reduction > 0.04:
        factor = 1.0 / (1.0 - min(reduction, 0.7))
        multiplier *= factor
        names = sorted((res_types | imm_types) - (set(_PHYSICAL) if nonmagical_phys else set()))
        d.notes.append(f"Resistances and immunities ({', '.join(names)}) turn away about {reduction * 100:.0f}% of a "
                       f"typical party's damage: x{factor:.2f} hit points.")

    regen = 0
    text = " ".join(f"{f.name} {f.description}" for f in monster.traits)
    m = re.search(r"regenerat\w*[^.]{0,80}?(\d+)\s+hit points", text, re.I)
    if m:
        regen = int(m.group(1))
        d.notes.append(f"Regeneration of {regen} hit points a round counts as about {regen * 3} more hit points over a "
                       f"three-round fight.")

    d.hp_multiplier = multiplier
    d.effective_hp = max(1.0, monster.hp * multiplier + regen * 3)

    saves = sum(1 for a in __import__("character_sheet").AbilityScore if monster.saving_throws.is_proficient(a))
    d.save_proficiencies = saves
    if saves >= 5:
        d.effective_ac += 4
        d.notes.append("Proficiency in five or six saving throws counts as +4 armor class.")
    elif saves >= 3:
        d.effective_ac += 2
        d.notes.append("Proficiency in three or four saving throws counts as +2 armor class.")
    return d


# --------------------------------------------------------------------------- numbers of a monster

_NUMBERS_CACHE: Dict[tuple, dict] = {}


def monster_numbers(monster: Monster, spell_lookup=lambda n: None) -> dict:
    """The comparable numbers of a monster: armor class, hit points, effective hit points, damage per round."""
    key = (monster.name, monster.hp, monster.ac, len(monster.actions), monster.is_official)
    if monster.is_official:
        cached = _NUMBERS_CACHE.get(key)
        if cached is not None:
            return cached
    off = read_offense(monster, spell_lookup)
    de = read_defense(monster)
    nums = {"ac": monster.ac, "hp": monster.hp, "ehp": de.effective_hp, "dmg": off.per_round if off.detected else None,
            "attack": off.attack_bonus, "dc": off.save_dc,
            "resists": bool(monster.damage_resistances or monster.damage_immunities),
            "cond_imm": len(monster.condition_immunities)}
    if monster.is_official:
        _NUMBERS_CACHE[key] = nums
    return nums


def percentile(value: float, samples: Sequence[float]) -> Optional[float]:
    """Share of ``samples`` that are below ``value`` (ties count half), 0-100."""
    vals = [v for v in samples if v is not None]
    if len(vals) < 4:
        return None
    below = sum(1 for v in vals if v < value) + 0.5 * sum(1 for v in vals if v == value)
    return 100.0 * below / len(vals)


_DEFAULT_REFERENCE: Optional[Reference] = None


def table_reference() -> Reference:
    """A reference that is only the DMG table (no collection)."""
    global _DEFAULT_REFERENCE
    if _DEFAULT_REFERENCE is None:
        _DEFAULT_REFERENCE = Reference()
    return _DEFAULT_REFERENCE


_COLLECTION_REFERENCE: Optional[Tuple[tuple, Reference]] = None


def collection_reference(monsters: Sequence[Monster], spell_lookup: Callable[[str], object] = lambda n: None
                         ) -> Reference:
    """The reference built from the official monsters of the collection (cached while they are unchanged)."""
    global _COLLECTION_REFERENCE
    official = [m for m in monsters if m.is_official and not m.spell_only]
    signature = (len(official), sum(m.hp for m in official), sum(len(m.actions) for m in official))
    if _COLLECTION_REFERENCE is None or _COLLECTION_REFERENCE[0] != signature:
        _COLLECTION_REFERENCE = (signature, Reference(official, spell_lookup))
    return _COLLECTION_REFERENCE[1]


# --------------------------------------------------------------------------- the report

@dataclass
class Stat:
    key: str                    # "ac" | "hp" | "damage" | "attack" | "dc"
    label: str
    value: str
    typical: str                # "131 - 145"
    status: str                 # "low" | "ok" | "high"
    note: str = ""              # the sentence shown when it is off
    peers: str = ""             # "higher than 90% of the CR 5 monsters in the collection"
    guideline: str = ""         # the DMG table's figure


@dataclass
class Report:
    name: str
    declared: str
    declared_set: bool          # the CR in the editor looks deliberate (not the blank form's 0)
    suggested: str
    defensive: str
    offensive: str
    defense: Defense
    offense: Offense
    stats: List[Stat] = field(default_factory=list)       # compared with the CR in ``compared_with``
    compared_with: str = ""
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    peer_count: int = 0
    steps: List[str] = field(default_factory=list)        # how the suggestion was reached
    read: List[Tuple[str, str]] = field(default_factory=list)   # what was read from the stat block

    @property
    def matches(self) -> bool:
        return self.declared == self.suggested


def _range_text(lo: float, hi: float) -> str:
    return f"{lo:,.0f} - {hi:,.0f}"


def analyze(monster: Monster, *, compare_to: Optional[str] = None, reference: Optional[Reference] = None,
            spell_lookup: Callable[[str], object] = lambda n: None) -> Report:
    """Suggest a CR for ``monster`` and compare its numbers with ``compare_to`` (default: its own CR if it looks
    deliberate, otherwise the suggestion). ``reference`` is what is typical (see :func:`collection_reference`);
    without one the DMG table alone is used."""
    ref = reference or table_reference()
    off = read_offense(monster, spell_lookup)
    de = read_defense(monster)
    steps: List[str] = []

    # --- defensive CR
    hp_idx = ref.index_for("ehp", de.effective_hp)
    expected_ac = ref.band(hp_idx, "ac").med
    ac_diff = de.effective_ac - expected_ac
    def_idx = max(0, min(len(TABLE) - 1, hp_idx + _shift(ac_diff)))
    hp_text = f"{de.effective_hp:,.0f}" if abs(de.effective_hp - monster.hp) > 0.5 else f"{monster.hp:,}"
    steps.append(f"Hit points {hp_text} are what a CR {CR_OPTIONS[hp_idx]} creature typically has.")
    if _shift(ac_diff):
        steps.append(f"Armor class {_n(de.effective_ac)} is {_n(abs(ac_diff))} {'above' if ac_diff > 0 else 'below'} the "
                     f"{_n(expected_ac)} expected at CR {CR_OPTIONS[hp_idx]}: defensive CR moves "
                     f"{'up' if ac_diff > 0 else 'down'} {abs(_shift(ac_diff))}, to CR {CR_OPTIONS[def_idx]}.")
    else:
        steps.append(f"Armor class {_n(de.effective_ac)} is close to the {_n(expected_ac)} expected: "
                     f"defensive CR {CR_OPTIONS[def_idx]}.")

    # --- offensive CR
    if off.detected:
        dmg_idx = ref.index_for("dmg", off.per_round)
        steps.append(f"Damage of about {off.per_round:.0f} a round is typical of CR {CR_OPTIONS[dmg_idx]}.")
        shift = 0
        if off.uses_attacks and off.attack_bonus is not None:
            expected = ref.band(dmg_idx, "attack").med
            shift = _shift(off.attack_bonus - expected)
            if shift:
                steps.append(f"An attack bonus of +{off.attack_bonus} against the +{_n(expected)} expected moves it "
                             f"{'up' if shift > 0 else 'down'} {abs(shift)}.")
        elif off.uses_saves and off.save_dc is not None:
            expected = ref.band(dmg_idx, "dc").med
            shift = _shift(off.save_dc - expected)
            if shift:
                steps.append(f"A save DC of {off.save_dc} against the {_n(expected)} expected moves it "
                             f"{'up' if shift > 0 else 'down'} {abs(shift)}.")
        off_idx = max(0, min(len(TABLE) - 1, dmg_idx + shift))
        final = _round_half_up((def_idx + off_idx) / 2.0)
        steps.append(f"Offensive CR {CR_OPTIONS[off_idx]}, defensive CR {CR_OPTIONS[def_idx]}: the average is "
                     f"CR {CR_OPTIONS[final]}.")
    else:
        off_idx = def_idx
        final = def_idx
        steps.append("No damage could be read, so only the defensive CR counts.")
    suggested = CR_OPTIONS[final]

    declared = normalize_cr(monster.challenge_rating)
    # the blank form says CR 0; that is only deliberate for a creature that is as feeble as CR 0 is
    declared_set = declared != "0" or (de.effective_hp <= 6 and off.per_round <= 1)
    target = normalize_cr(compare_to) if compare_to else (declared if declared_set else suggested)

    report = Report(name=monster.name, declared=declared, declared_set=declared_set, suggested=suggested,
                    defensive=CR_OPTIONS[def_idx], offensive=CR_OPTIONS[off_idx] if off.detected else "",
                    defense=de, offense=off, compared_with=target, steps=steps)
    report.read = _read_lines(monster, de, off)
    _compare(report, monster, target, ref)
    report.notes.extend(de.notes)
    report.notes.extend(off.notes)
    _extras(report, monster)
    return report


def _read_lines(monster: Monster, de: Defense, off: Offense) -> List[Tuple[str, str]]:
    """The numbers taken from the stat block, as (label, text) lines."""
    lines: List[Tuple[str, str]] = [("Armor Class", str(monster.ac) + (f" (counts as {_n(de.effective_ac)})"
                                                                     if de.effective_ac != monster.ac else ""))]
    hp = f"{monster.hp:,}"
    if abs(de.effective_hp - monster.hp) > 0.5:
        hp += f" (counts as {de.effective_hp:,.0f})"
    lines.append(("Hit Points", hp))
    if off.detected:
        text = f"{off.per_round:.0f}"
        if off.plan_text:
            text += f"  ({off.plan_text})"
        lines.append(("Damage per round", text))
        if off.attack_bonus is not None and off.uses_attacks:
            lines.append(("Attack bonus", f"+{off.attack_bonus}"))
        if off.save_dc is not None:
            lines.append(("Save DC", str(off.save_dc)))
    else:
        lines.append(("Damage per round", "none could be read"))
    for label, items in (("Resistances", monster.damage_resistances), ("Immunities", monster.damage_immunities),
                         ("Vulnerabilities", monster.damage_vulnerabilities),
                         ("Condition immunities", monster.condition_immunities)):
        lines.append((label, ", ".join(items) if items else "none"))
    if off.conditions:
        lines.append(("Can inflict", ", ".join(off.conditions)))
    return lines


def _compare(report: Report, monster: Monster, target: str, ref: Reference) -> None:
    index = CR_OPTIONS.index(target)
    row = TABLE[index]
    de, off = report.defense, report.offense
    group = ref.peers(target, exclude=monster.name)
    report.peer_count = len(group)

    def peer_text(key: str, value: float) -> str:
        pct = percentile(value, [n[key] for _m, n in group]) if group else None
        if pct is None:
            return ""
        if pct >= 85:
            return f"higher than {pct:.0f}% of the {len(group)} CR {target} monsters in the collection"
        if pct <= 15:
            return f"lower than {100 - pct:.0f}% of the {len(group)} CR {target} monsters in the collection"
        return f"about typical of the {len(group)} CR {target} monsters in the collection"

    def limits(key: str, gap: float):
        """(low, high) of what counts as typical: the band for hit points and damage; for the small numbers the band
        widened to at least ``gap`` either side of the middle."""
        band = ref.band(index, key)
        if key in ("ehp", "dmg"):
            return band.lo, band.hi
        return min(band.lo, band.med - gap), max(band.hi, band.med + gap)

    def add(key, stat_key, label, shown, value, guideline, noun, gap=2, plus=False):
        lo, hi = limits(key, gap)
        status = "high" if value > hi else "low" if value < lo else "ok"
        if key in ("ehp", "dmg"):
            typical = _range_text(lo, hi)
        else:
            typical = f"{'+' if plus else ''}{_n(lo)} - {'+' if plus else ''}{_n(hi)}"
        s = Stat(stat_key, label, shown, typical, status, peers=peer_text(key, value), guideline=guideline)
        if status != "ok":
            word = "higher" if status == "high" else "lower"
            s.note = f"{noun} {shown} {'are' if noun.endswith('Points') else 'is'} {word} than is typical for CR {target} ({typical})."
        report.stats.append(s)

    ac_shown = f"{monster.ac}" + (f" (counts as {_n(de.effective_ac)})" if de.effective_ac != monster.ac else "")
    add("ac", "ac", "Armor Class", ac_shown, de.effective_ac, str(row.ac), "Armor Class")

    hp_shown = f"{monster.hp:,}" + (f" (counts as {de.effective_hp:,.0f})"
                                    if abs(de.effective_hp - monster.hp) > 0.5 else "")
    add("ehp", "hp", "Hit Points", hp_shown, de.effective_hp, _range_text(row.hp_lo, row.hp_hi), "Hit Points")

    if off.detected:
        add("dmg", "damage", "Damage per round", f"{off.per_round:.0f}", off.per_round,
            _range_text(row.dmg_lo, row.dmg_hi), "Damage per round")
        if off.uses_attacks and off.attack_bonus is not None:
            add("attack", "attack", "Attack bonus", f"+{off.attack_bonus}", off.attack_bonus, f"+{row.attack}",
                "An attack bonus of", plus=True)
        if off.uses_saves and off.save_dc is not None:
            add("dc", "dc", "Save DC", str(off.save_dc), off.save_dc, str(row.dc), "A save DC of")

    report.warnings = [s.note for s in report.stats if s.note and s.status == "high"]
    report.notes += [s.note for s in report.stats if s.note and s.status == "low"]
    if report.declared_set and report.compared_with == report.declared and report.declared != report.suggested:
        direction = "above" if CR_OPTIONS.index(report.suggested) > CR_OPTIONS.index(report.declared) else "below"
        report.notes.insert(0, f"Overall the numbers suggest CR {report.suggested}, {direction} the "
                               f"CR {report.declared} set.")


def _extras(report: Report, monster: Monster) -> None:
    """Things the table has no column for, worth a designer's attention."""
    de = report.defense
    if de.condition_immunities >= 4:
        report.notes.append(f"Immune to {de.condition_immunities} conditions: that takes many spells and abilities "
                            f"away from a party.")
    text = " ".join(f"{f.name} {f.description}" for g in (monster.traits, monster.reactions) for f in g).lower()
    m = re.search(r"legendary resistance\s*\((\d+)", text)
    if m:
        report.notes.append(f"Legendary Resistance ({m.group(1)}/Day) makes saving-throw spells much less reliable; "
                            f"it usually belongs to a CR 10+ creature.")
    if "magic resistance" in text:
        report.notes.append("Magic Resistance: advantage on saves against spells is worth about +2 armor class "
                            "against casters.")
    if re.search(r"\bevasion\b", text):
        report.notes.append("Evasion halves the effect of most area damage on this creature.")
    flying = (monster.speeds or {}).get("fly", 0)
    if flying and report.suggested and cr_to_number(report.suggested) < 5:
        report.notes.append("Flying below CR 5 makes melee-only parties struggle; the numbers do not count that.")
    if monster.legendary_actions and cr_to_number(report.suggested or "0") < 10:
        report.notes.append("Legendary actions below CR 10 are unusual.")


def closest(monster: Monster, reference: Reference, spell_lookup: Callable[[str], object] = lambda n: None,
            exclude: str = "", count: int = 5) -> List[Tuple[Monster, dict]]:
    """The official monsters whose numbers are nearest to this one's (hit points, damage, armor class)."""
    mine = monster_numbers(monster, spell_lookup)
    scored = []
    for samples in reference.samples:
        for other, nums in samples:
            if other.name.lower() == (exclude or "").lower():
                continue
            gap = abs(math.log(max(1.0, nums["ehp"]) / max(1.0, mine["ehp"])))
            if mine["dmg"] is not None and nums["dmg"] is not None:
                gap += 0.8 * abs(math.log((nums["dmg"] + 4.0) / (mine["dmg"] + 4.0)))
            gap += 0.06 * abs(nums["ac"] - mine["ac"])
            if monster.creature_type and other.creature_type == monster.creature_type:
                gap -= 0.08
            scored.append((gap, other, nums))
    scored.sort(key=lambda r: r[0])
    return [(m, n) for _g, m, n in scored[:count]]
