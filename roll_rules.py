"""
The building blocks of a character's d20 roll (no UI, no data): what a rule can do to a roll, the d20 as it is
built up feature by feature, and the maths for "if the roll fails" options (reroll it, add a die, turn it into
a success...).

A :class:`Rule` says "when this feature is on the character and the roll looks like this, apply these
effects". The tables of rules live in ``character_rules`` (class, feat and species features) and
``item_effects`` (magic items); ``character_rolls`` applies them.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple, Union

from dice_analyzer import DiceTerm, Dist

# ----------------------------------------------------------------------------- effects and rules

Num = Union[int, Callable[..., int]]


@dataclass(frozen=True)
class Eff:
    """One thing a rule does. ``kind`` is one of:

    adv / dis            advantage or disadvantage (any number of sources do not stack)
    flat                 add ``value`` (a number, or ``fn(ctx)``)
    die                  add a die: ``value`` = (count, sides, sign)
    min                  a d20 showing less than ``value`` counts as ``value`` (Reliable Talent: 10)
    reroll               a d20 showing ``value`` or less is rerolled once (Halfling Luck: 1)
    floor_total          the total counts as at least ``value`` (number or ``fn(ctx)``)
    crit                 critical hits on ``value`` or higher
    copies               roll this many extra d20s and keep the best (Elven Accuracy, a Luck point)
    rescue_add           if the roll fails, add ``value`` = (count, sides, flat) (or ``fn(ctx)`` returning it)
    copies_if_adv        roll this many extra d20s when the roll has advantage (Elven Accuracy)
    fixed_d20            the d20 is this number without rolling (Clockwork Amulet: 10)
    dc                   add to the spell save DC (Innate Sorcery)
    rescue_reroll        if the roll fails, reroll the d20 (adding ``value``, a number or ``fn(ctx)``, to it)
    rescue_set20         if the roll fails, the d20 becomes a 20
    rescue_succeed       if the roll fails, it succeeds instead
    """
    kind: str
    value: object = None


ADV = Eff("adv")
DIS = Eff("dis")
RESCUE_SET20 = Eff("rescue_set20")
RESCUE_SUCCEED = Eff("rescue_succeed")


def flat(value: Num) -> Eff:
    return Eff("flat", value)


def die(count: int, sides: int, sign: int = 1) -> Eff:
    return Eff("die", (count, sides, sign))


def minimum(value: int = 10) -> Eff:
    return Eff("min", value)


def reroll(value: int = 1) -> Eff:
    return Eff("reroll", value)


def rescue_add(count: int, sides: int, bonus: Num = 0) -> Eff:
    return Eff("rescue_add", (count, sides, bonus))


def rescue_reroll(bonus: Num = 0) -> Eff:
    return Eff("rescue_reroll", bonus)


@dataclass
class RollInfo:
    """What kind of roll is being made, so rules can say whether they apply."""
    kind: str                       # "skill" | "check" | "initiative" | "save" | "attack" | "spell"
    ability: str = ""               # STR DEX CON INT WIS CHA (the ability the roll actually uses)
    skill: str = ""                 # display name of the skill, if any
    proficient: bool = False        # proficient (or expert) in the skill
    concentration: bool = False
    save_vs: str = ""               # "charmed" | "frightened" | "poisoned" | "magic" | "" (what the save is against)
    ranged: bool = False
    spell_class: str = ""           # for spell attack rolls: the class the spell is cast as, if known


@dataclass
class Rule:
    id: str
    label: str
    feature: str = ""               # the character feature this needs ("" = always there, such as an item)
    kinds: Tuple[str, ...] = ("check",)
    skills: Optional[FrozenSet[str]] = None
    abilities: Optional[FrozenSet[str]] = None
    conc: Optional[bool] = None     # True = only concentration saves, False = never those
    proficient: Optional[bool] = None
    ranged: Optional[bool] = None   # for attacks: True = only ranged attacks, False = only melee
    vs: str = ""                    # for saves: only when the save is against this
    effects: Tuple[Eff, ...] = ()
    toggle: bool = False            # shown as a choice ("situational") instead of always applied
    toggle_label: str = ""
    default: bool = False
    when: Optional[Callable[..., bool]] = None       # extra condition on the character: fn(ctx)
    spell_class: str = ""           # only for spells cast as this class

    def matches(self, roll: RollInfo, ignore_vs: bool = False) -> bool:
        if roll.kind not in self._kinds():
            return False
        if self.skills is not None and roll.skill not in self.skills:
            return False
        if self.abilities is not None and roll.ability not in self.abilities:
            return False
        if self.conc is not None and bool(self.conc) != roll.concentration:
            return False
        if self.proficient is not None and bool(self.proficient) != roll.proficient:
            return False
        if self.ranged is not None and bool(self.ranged) != roll.ranged:
            return False
        if self.vs and not ignore_vs and roll.save_vs != self.vs:
            return False
        if self.spell_class and roll.spell_class and roll.spell_class.lower() != self.spell_class.lower():
            return False
        return True

    def _kinds(self) -> Tuple[str, ...]:
        out = []
        for k in self.kinds:
            if k == "check":
                out += ["skill", "check", "initiative"]
            else:
                out.append(k)
        return tuple(out)

    @property
    def option_key(self) -> str:
        return f"rule:{self.id}"


def fs(*names: str) -> FrozenSet[str]:
    return frozenset(names)


# ----------------------------------------------------------------------------- the d20

@dataclass
class Rescue:
    kind: str                       # "add" | "reroll" | "set20" | "succeed"
    label: str
    dice: Tuple[int, int, int] = (0, 6, 0)     # for "add": (count, sides, flat)
    bonus: int = 0                  # for "reroll": added to the new roll


@dataclass
class D20:
    """Everything that shapes one d20 test, built up feature by feature."""
    flat: List[Tuple[str, int]] = field(default_factory=list)
    dice: List[Tuple[str, int, int, int]] = field(default_factory=list)      # (why, count, sides, sign)
    adv: List[str] = field(default_factory=list)
    dis: List[str] = field(default_factory=list)
    user_adv: int = 0               # 1 advantage, 2 double advantage (chosen by the user)
    user_dis: int = 0
    emphasis: bool = False
    reroll_max: int = 0
    minimum: int = 1
    extra_copies: int = 0
    floor_total: int = 0
    rescues: List[Rescue] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    crit_min: int = 20
    fixed: Optional[int] = None     # the d20 is not rolled
    dc_bonus: int = 0
    copies_if_adv: int = 0          # extra d20s kept when the roll has advantage (Elven Accuracy)

    def add(self, why: str, value: int):
        if value:
            self.flat.append((why, int(value)))

    def add_die(self, why: str, count: int, sides: int, sign: int = 1):
        self.dice.append((why, count, sides, sign))

    # ---- advantage, disadvantage and their double / emphasis forms
    def level(self) -> int:
        """Net advantage: +1 advantage, +2 double advantage, -1 disadvantage, -2 double disadvantage, 0 none.
        Sources of the same kind do not stack; advantage and disadvantage cancel one for one."""
        a = max(self.user_adv, 1 if self.adv else 0)
        d = max(self.user_dis, 1 if self.dis else 0)
        return max(-2, min(2, a - d))

    def natural(self) -> Tuple[Dist, List[str]]:
        """The d20 that is finally used (rerolls, minimum, advantage and so on applied) and notes about it."""
        notes: List[str] = []
        if self.fixed is not None:
            return Dist.point(self.fixed), [f"The d20 is not rolled: it counts as {self.fixed}."]
        net = self.level()
        a_src, d_src = ", ".join(self.adv), ", ".join(self.dis)
        if self.adv and self.dis and net == 0:
            notes.append(f"Advantage ({a_src}) and disadvantage ({d_src}) cancel out.")
        elif net > 0:
            notes.append(("Double advantage" if net == 2 else "Advantage") + (f": {a_src}." if a_src else "."))
            if self.dis:
                notes.append(f"Disadvantage ({d_src}) took one level of advantage away.")
        elif net < 0:
            notes.append(("Double disadvantage" if net == -2 else "Disadvantage") + (f": {d_src}." if d_src else "."))
            if self.adv:
                notes.append(f"Advantage ({a_src}) took one level of disadvantage away.")
        if net > 0:
            copies, pick = 1 + net + self.extra_copies + self.copies_if_adv, "high"
        elif net < 0:
            copies, pick = 1 + (-net), "low"
        elif self.emphasis:
            copies, pick = 2, "emph"
            notes.append("Emphasis: two d20s, the one furthest from 10 is used (a tie keeps the higher).")
        else:
            copies, pick = 1 + self.extra_copies, "high"
        if self.emphasis and net != 0:
            notes.append("Emphasis was not used because advantage or disadvantage already applies.")
        term = DiceTerm(1, 20, copies=copies, pick=pick, reroll_max=self.reroll_max, reroll_once=True,
                        minimum=self.minimum)
        return term.distribution(), notes

    def bonus(self) -> Dist:
        """Flat modifiers and extra dice, as a distribution."""
        total = sum(v for _, v in self.flat)
        dist = Dist.point(total)
        for _why, count, sides, sign in self.dice:
            part = DiceTerm(count, sides).distribution()
            dist = dist + (part if sign > 0 else part.negate())
        return dist

    def formula(self) -> str:
        total = sum(v for _, v in self.flat)
        bits = ["d20"]
        if total:
            bits.append(f"{'+' if total > 0 else '-'} {abs(total)}")
        for _why, count, sides, sign in self.dice:
            bits.append(f"{'+' if sign > 0 else '-'} {count}d{sides}")
        return " ".join(bits)

    def flat_total(self) -> int:
        return sum(v for _, v in self.flat)

    def breakdown(self) -> List[str]:
        return [f"{why} {'+' if v > 0 else '-'}{abs(v)}" for why, v in self.flat if v]


# ----------------------------------------------------------------------------- "if the roll fails"

def _pairs(dist: Dist) -> List[Tuple[int, float]]:
    return [(dist.lo + i, p) for i, p in enumerate(dist.probs) if p > 0.0]


def _rescue_dice(r: Rescue) -> Dist:
    count, sides, flat_bonus = r.dice
    d = DiceTerm(count, sides).distribution() if count > 0 else Dist.point(0)
    return d.shift(flat_bonus)


def rescued_total(d20: D20, natural: Dist, bonus: Dist, target: int) -> Dist:
    """The distribution of a check or save when the character uses its "if I fail" options (``d20.rescues``) against a
    DC of ``target``: a failed roll is reroll / boosted / turned into a success by each option in turn, but an option
    is only used when it could actually turn the failure into a success."""
    rescues = d20.rescues
    floor = d20.floor_total
    acc: Dict[int, float] = defaultdict(float)
    nat_pairs = _pairs(natural)
    dice_cache = {id(r): _pairs(_rescue_dice(r)) for r in rescues if r.kind == "add"}

    def total_of(n: int, b: int) -> int:
        return max(n + b, floor) if floor else n + b

    def resolve(n: int, b: int, p: float, i: int):
        t = total_of(n, b)
        if t >= target or i >= len(rescues):
            acc[t] += p
            return
        r = rescues[i]
        if r.kind == "succeed":
            acc[target] += p
        elif r.kind == "set20":
            resolve(20, b, p, i + 1)
        elif r.kind == "add":
            pairs = dice_cache[id(r)]
            if t + pairs[-1][0] < target:                       # even the best roll would not be enough
                resolve(n, b, p, i + 1)
            else:
                for v, pv in pairs:
                    resolve(n, b + v, p * pv, i + 1)
        elif r.kind == "reroll":
            for n2, pn2 in nat_pairs:
                resolve(n2, b + r.bonus, p * pn2, i + 1)
        else:
            resolve(n, b, p, i + 1)

    for n, pn in nat_pairs:
        for b, pb in _pairs(bonus):
            resolve(n, b, pn * pb, 0)
    lo, hi = min(acc), max(acc)
    return Dist(lo, [acc.get(v, 0.0) for v in range(lo, hi + 1)]).trimmed()


def attack_outcomes(d20: D20, natural: Dist, bonus: Dist, armor_class: int) -> Tuple[float, float, float]:
    """(miss, hit, crit) probabilities for an attack against ``armor_class``: a natural 1 always misses, a natural
    20 always hits, a natural ``d20.crit_min`` or more is a critical hit, and the "if I miss" options in
    ``d20.rescues`` are used on a miss when they could turn it into a hit."""
    crit_min = max(2, d20.crit_min)
    rescues = d20.rescues
    out = [0.0, 0.0, 0.0]                       # miss, hit, crit
    nat_pairs = _pairs(natural)
    dice_cache = {id(r): _pairs(_rescue_dice(r)) for r in rescues if r.kind == "add"}

    def outcome(n: int, b: int) -> int:
        if n == 1:
            return 0
        if n >= crit_min:
            return 2
        return 1 if n + b >= armor_class else 0

    def resolve(n: int, b: int, p: float, i: int):
        o = outcome(n, b)
        if o or i >= len(rescues):
            out[o] += p
            return
        r = rescues[i]
        if r.kind == "succeed":
            out[1] += p
        elif r.kind == "set20":
            out[2] += p
        elif r.kind == "add":
            pairs = dice_cache[id(r)]
            if n == 1 or n + b + pairs[-1][0] < armor_class:
                resolve(n, b, p, i + 1)
            else:
                for v, pv in pairs:
                    resolve(n, b + v, p * pv, i + 1)
        elif r.kind == "reroll":
            for n2, pn2 in nat_pairs:
                resolve(n2, b + r.bonus, p * pn2, i + 1)
        else:
            resolve(n, b, p, i + 1)

    for n, pn in nat_pairs:
        for b, pb in _pairs(bonus):
            resolve(n, b, pn * pb, 0)
    total = math.fsum(out) or 1.0
    return out[0] / total, out[1] / total, out[2] / total


# ----------------------------------------------------------------------------- damage rules
@dataclass
class DmgCtx:
    """What an attack or spell is, so damage rules can say whether they apply."""
    kind: str                       # "weapon" | "spell"
    ranged: bool = False
    thrown: bool = False
    unarmed: bool = False
    damage_type: str = ""
    spell_name: str = ""
    cantrip: bool = False
    level: int = 0
    school: str = ""
    healing: bool = False
    attack_roll: bool = False
    spell_class: str = ""


@dataclass
class DmgRule:
    id: str
    label: str
    feature: str = ""
    when: Optional[Callable[..., bool]] = None
    applies: Callable[..., bool] = lambda c, d: True
    dice: Optional[Callable[..., Tuple[int, int]]] = None        # (count, sides)
    flat: Union[int, Callable[..., int]] = 0
    once: bool = False              # once per turn (weapons) / once per cast (spells)
    toggle: bool = True
    default: bool = True
    toggle_label: str = ""
    crit_doubles: bool = True
    minimum: int = 1
    per_projectile: bool = False    # spells: added to every beam, not once per cast
