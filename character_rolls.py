"""
What a character's rolls look like in numbers: skills, saves, attacks and spells turned into probability
distributions, with the character's features and magic items applied.

Pure logic (no UI). ``CharacterAnalyzer(character, sheet, lookups).rolls()`` lists everything the sheet can roll;
each :class:`RollOption` says which situational options apply to it (advantage, Bless, Rage, a magic weapon, ...) and
``analyze(state)`` returns the result views to show.

The numbers come from the sheet itself (ability scores, proficiencies, the attacks entered on it), so they match
what the character sheet displays; what the sheet cannot say is read from the character's classes, feats and
lineage and from its linked magic items. The tables of what each feature does are in ``character_rules`` (d20
rolls and damage) and ``item_effects`` (magic items); ``roll_rules`` holds the d20 maths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from character_context import ABBR, ABILITIES, ABILITY_NAMES, FEATURES, Ctx
from character_rules import D20_RULES, DAMAGE_RULES, DmgCtx
from character_sheet import Skill
from dice_analyzer import DiceError, DiceTerm, Dist, Expression, parse_expression, reroll_lowest_distribution
from item_effects import ItemInfo, parse_items
from roll_effects import collect
from roll_rules import D20, Eff, Rescue, Rule, RollInfo, attack_outcomes, rescued_total

MAX_SPELL_SLOT = 9
MODES = ["Normal", "Advantage", "Disadvantage", "Double advantage", "Double disadvantage", "Emphasis"]
SAVE_VS = {"Anything else": "", "Charmed": "charmed", "Frightened": "frightened", "Poisoned": "poisoned",
           "Spells and magic": "magic"}
PRIMAL_KNOWLEDGE_SKILLS = ("Acrobatics", "Intimidation", "Perception", "Stealth", "Survival")

BONUS_DIE_SIDES = (4, 6, 8, 10, 12, 20)
BONUS_PRESETS = [            # name -> (sign, count, sides): starting points for the "Bonus dice" list
    ("Bardic Inspiration (d6)", 1, 1, 6), ("Bardic Inspiration (d8)", 1, 1, 8),
    ("Bardic Inspiration (d10)", 1, 1, 10), ("Bardic Inspiration (d12)", 1, 1, 12),
    ("Guidance (d4)", 1, 1, 4), ("Resistance (d4)", 1, 1, 4), ("Bless (d4)", 1, 1, 4),
    ("Bane (-d4)", -1, 1, 4), ("Mind Sliver (-d4)", -1, 1, 4), ("Psionic Energy die (d6)", 1, 1, 6),
    ("Superiority die (d8)", 1, 1, 8), ("Other die", 1, 1, 6),
]


# ----------------------------------------------------------------------------- results

@dataclass
class Option:
    """A situational choice the user can make for a roll."""
    key: str
    label: str
    kind: str = "bool"                 # "bool" | "choice" | "int" | "text" | "dice" (a list of bonus dice)
    default: object = False
    choices: List[str] = field(default_factory=list)
    help: str = ""


@dataclass
class View:
    """One result to show: a distribution and the facts that go with it."""
    key: str
    title: str
    dist: Dist
    unit: str = "roll"                 # "roll" | "damage" | "healing"
    facts: List[Tuple[str, str]] = field(default_factory=list)
    target: str = ""                   # "dc" / "ac" when "chance to reach X" makes sense for this view


@dataclass
class Analysis:
    formula: str
    views: List[View]
    notes: List[str] = field(default_factory=list)       # what was applied automatically
    warnings: List[str] = field(default_factory=list)
    bonus: int = 0                                      # the flat modifier of the roll (for summaries)


@dataclass
class Lookups:
    """How to find things the sheet only knows by name (injected so this module stays UI-free)."""
    spell: Callable[[str], object] = lambda name: None
    equipment: Callable[[str], object] = lambda name: None
    class_def: Callable[[str], object] = lambda name: None
    magic_item: Callable[[str], object] = lambda name: None
    feat: Callable[[str], object] = lambda name: None          # homebrew feats with roll effects
    lineage: Callable[[str], object] = lambda name: None       # homebrew species traits with roll effects


@dataclass
class RollOption:
    key: str
    group: str                         # "Checks" / "Skills" / "Saves" / "Attacks" / "Spells"
    name: str
    summary: str                       # e.g. "+7"
    options: List[Option]
    run: Callable[[Dict[str, object]], Analysis]
    meta: Dict[str, object] = field(default_factory=dict)      # e.g. {"ability": "DEX", "level": 2 (expertise)}

    def analyze(self, state: Optional[Dict[str, object]] = None) -> Analysis:
        merged = {o.key: o.default for o in self.options}
        merged.update(state or {})
        return self.run(merged)


# ----------------------------------------------------------------------------- applying rules to a d20

def _present(ctx: Ctx, rule: Rule) -> bool:
    return (not rule.feature or ctx.has(rule.feature)) and (rule.when is None or bool(rule.when(ctx)))


def all_rules(ctx: Ctx) -> List[Rule]:
    rules = list(D20_RULES) + list(ctx.extra_rules)
    for item in ctx.active_items:
        rules.extend(item.rules)
    return rules


def damage_rules(ctx: Ctx) -> List:
    rules = list(DAMAGE_RULES) + list(ctx.extra_damage_rules)
    for item in ctx.active_items:
        rules.extend(item.damage_rules)
    return rules


def rule_options(ctx: Ctx, roll: RollInfo) -> List[Option]:
    """The situational choices (Vow of Enmity, Lucky, an item's conditional advantage ...) for a roll."""
    out = []
    for rule in all_rules(ctx):
        if rule.toggle and _present(ctx, rule) and rule.matches(roll, ignore_vs=True):
            out.append(Option(rule.option_key, rule.toggle_label or rule.label, "bool", rule.default))
    return out


def has_save_vs(ctx: Ctx, roll: RollInfo) -> bool:
    return any(r.vs and _present(ctx, r) and r.matches(roll, ignore_vs=True) for r in all_rules(ctx))


def _short(label: str) -> str:
    return label.split(":")[0].strip()


def _value(v, ctx: Ctx):
    return v(ctx) if callable(v) else v


def _apply_eff(d20: D20, ctx: Ctx, rule: Rule, eff: Eff) -> None:
    k, label = eff.kind, rule.label
    if k == "adv":
        d20.adv.append(_short(label))
    elif k == "dis":
        d20.dis.append(_short(label))
    elif k == "flat":
        d20.add(_short(label), int(_value(eff.value, ctx)))
    elif k == "die":
        count, sides, sign = eff.value
        d20.add_die(_short(label), count, sides, sign)
    elif k == "min":
        d20.minimum = max(d20.minimum, int(eff.value))
        d20.notes.append(label)
    elif k == "reroll":
        d20.reroll_max = max(d20.reroll_max, int(eff.value))
        d20.notes.append(label)
    elif k == "floor_total":
        d20.floor_total = max(d20.floor_total, int(_value(eff.value, ctx)))
        d20.notes.append(label)
    elif k == "crit":
        d20.crit_min = min(d20.crit_min, int(eff.value))
        d20.notes.append(label)
    elif k == "copies":
        d20.extra_copies += int(eff.value)
        d20.notes.append(label)
    elif k == "copies_if_adv":
        d20.copies_if_adv = max(d20.copies_if_adv, int(eff.value))
        d20.notes.append(label)
    elif k == "fixed_d20":
        d20.fixed = int(eff.value)
        d20.notes.append(label)
    elif k == "dc":
        d20.dc_bonus += int(eff.value)
        d20.notes.append(label)
    elif k == "rescue_add":
        count, sides, bonus = eff.value(ctx) if callable(eff.value) else eff.value
        d20.rescues.append(Rescue("add", _short(label), (count, sides, int(_value(bonus, ctx)))))
    elif k == "rescue_reroll":
        d20.rescues.append(Rescue("reroll", _short(label), bonus=int(_value(eff.value, ctx) or 0)))
    elif k == "rescue_set20":
        d20.rescues.append(Rescue("set20", _short(label)))
    elif k == "rescue_succeed":
        d20.rescues.append(Rescue("succeed", _short(label)))


_SIMPLE = ("adv", "dis", "flat", "die", "rescue_add", "rescue_reroll", "rescue_set20", "rescue_succeed")


def apply_rules(d20: D20, ctx: Ctx, roll: RollInfo, state: Dict[str, object]) -> None:
    for rule in all_rules(ctx):
        if not _present(ctx, rule) or not rule.matches(roll):
            continue
        if rule.toggle and not state.get(rule.option_key, rule.default):
            continue
        for eff in rule.effects:
            _apply_eff(d20, ctx, rule, eff)
        if rule.toggle and all(e.kind in _SIMPLE for e in rule.effects):
            d20.notes.append(rule.label)


def bonus_dice_from(value) -> List[Tuple[str, int, int, int]]:
    """The "bonus_dice" option as [(label, count, sides, sign)], ignoring anything unusable."""
    out = []
    for item in value or []:
        try:
            count, sides = int(item.get("count", 1)), int(item.get("sides", 6))
            sign = -1 if int(item.get("sign", 1)) < 0 else 1
        except (AttributeError, TypeError, ValueError):
            continue
        if count >= 1 and sides >= 2:
            out.append((str(item.get("label") or "Bonus die"), min(count, 50), sides, sign))
    return out


def apply_user(d20: D20, state: Dict[str, object]) -> None:
    """What the user chose for this roll: how it is rolled, bonus dice, a flat bonus."""
    mode = str(state.get("mode", "Normal"))
    if mode in ("Advantage", "Double advantage"):
        d20.adv.append("your choice")
        d20.user_adv = 2 if mode == "Double advantage" else 1
    elif mode in ("Disadvantage", "Double disadvantage"):
        d20.dis.append("your choice")
        d20.user_dis = 2 if mode == "Double disadvantage" else 1
    elif mode == "Emphasis":
        d20.emphasis = True
    for label, count, sides, sign in bonus_dice_from(state.get("bonus_dice")):
        d20.add_die(label, count, sides, sign)
    try:
        d20.add("Extra bonus", int(state.get("bonus", 0) or 0))
    except (TypeError, ValueError):
        pass


def _mode_option() -> Option:
    return Option("mode", "Rolling with", "choice", "Normal", list(MODES),
                  "Double advantage rolls three d20s and keeps the highest; Emphasis rolls two and keeps the one "
                  "furthest from 10.")


def common_options(ctx: Ctx, roll: RollInfo, pre: Optional[List[Option]] = None,
                   post: Optional[List[Option]] = None) -> List[Option]:
    opts = list(pre or [])
    opts.append(_mode_option())
    if roll.kind == "save" and has_save_vs(ctx, roll):
        opts.append(Option("save_vs", "Save against", "choice", "Anything else", list(SAVE_VS)))
    opts += rule_options(ctx, roll)
    opts += list(post or [])
    opts.append(Option("bonus_dice", "Bonus dice", "dice", [],
                       help="Dice added to the roll or taken from it: Bardic Inspiration, Guidance, Bless, Bane, "
                            "Mind Sliver, a psionic die..."))
    opts.append(Option("bonus", "Extra flat bonus", "int", 0))
    return opts


def _target(state) -> Optional[int]:
    t = state.get("target")
    try:
        return None if t in (None, "") else int(t)
    except (TypeError, ValueError):
        return None


def _finish_d20(ctx: Ctx, d20: D20, title: str, state, target_kind: str = "dc") -> Analysis:
    natural, notes = d20.natural()
    bonus = d20.bonus()
    target = _target(state)
    if d20.rescues and target is not None:
        total = rescued_total(d20, natural, bonus, target)
        notes.append("If it fails: " + "; ".join(r.label for r in d20.rescues) + f" (against {target}).")
    else:
        total = natural + bonus
        if d20.floor_total:
            total = total.clamp_min(d20.floor_total)
        if d20.rescues:
            notes.append("The 'if it fails' options need a target number: enter one under 'Chance to reach'.")
    facts = []
    if target is not None:
        facts.append((f"Chance to reach {target}", f"{total.at_least(target) * 100:.1f}%"))
    return Analysis(d20.formula(), [View("roll", title, total, "roll", facts, target_kind)],
                    d20.breakdown() + d20.notes + notes, bonus=d20.flat_total())


def _half_proficiency(ctx: Ctx, ability: str) -> Tuple[int, str]:
    best, why = 0, ""
    if ctx.has("jack_of_all_trades"):
        best, why = ctx.prof // 2, "Jack of All Trades"
    if ctx.has("remarkable_athlete") and ctx.is_legacy("Fighter") and ability in ("STR", "DEX", "CON"):
        v = (ctx.prof + 1) // 2
        if v > best:
            best, why = v, "Remarkable Athlete (half proficiency, rounded up)"
    if ctx.has("kefnets_blessing") and ability == "INT":
        v = ctx.prof // 2
        if v > best:
            best, why = v, "Kefnet's Blessing"
    return best, why


def _bespoke_check_options(ctx: Ctx, ability: str, skill: str = "") -> List[Option]:
    out = []
    if skill == "Acrobatics" and ctx.has("bladesong"):
        out.append(Option("bladesong", "Bladesong active", "bool", False, "Advantage on Dexterity (Acrobatics) checks."))
    primal = ctx.has("primal_knowledge") and skill in PRIMAL_KNOWLEDGE_SKILLS
    if ctx.lvl("Barbarian") and (ability == "STR" or primal):
        out.append(Option("rage", "Raging", "bool", False,
                          "Advantage on Strength checks" + (
                              "; Acrobatics, Intimidation, Perception, Stealth and Survival use Strength instead "
                              "(Primal Knowledge)." if primal else ".")))
    return out


# ----------------------------------------------------------------------------- skills, checks, initiative

def _skill_option(ctx: Ctx, skill: Skill) -> RollOption:
    default_ability = ABBR[skill.ability]
    level = ctx.skill_level(skill)
    name = skill.display_name
    base_roll = RollInfo("skill", default_ability, name, proficient=bool(level))

    def build(state) -> D20:
        d20 = D20()
        ability = str(state.get("ability") or default_ability)
        if ability not in ABILITIES:
            ability = default_ability
        raging = bool(state.get("rage")) and ctx.lvl("Barbarian") >= 1
        if raging and ctx.has("primal_knowledge") and name in PRIMAL_KNOWLEDGE_SKILLS \
                and ability == default_ability and default_ability != "STR":
            ability = "STR"
            d20.notes.append(f"Rage (Primal Knowledge): {name} is rolled with Strength instead of "
                             f"{ABILITY_NAMES[default_ability]}.")
        elif ability != default_ability:
            d20.notes.append(f"{name} uses {ABILITY_NAMES[ability]} instead of {ABILITY_NAMES[default_ability]}.")
        d20.add(f"{ability} modifier", ctx.mod(ability))
        if level:
            d20.add({1: "Proficiency", 2: "Expertise"}[level], ctx.prof * level)
        else:
            half, why = _half_proficiency(ctx, ability)
            if half:
                d20.add(why.split(" (")[0], half)
                d20.notes.append(f"{why}: +{half}.")
        if state.get("bladesong") and name == "Acrobatics":
            d20.adv.append("Bladesong")
        if raging and ability == "STR":
            d20.adv.append("Rage")
        roll = RollInfo("skill", ability, name, proficient=bool(level))
        apply_rules(d20, ctx, roll, state)
        apply_user(d20, state)
        return d20

    def run(state):
        return _finish_d20(ctx, build(state), f"{name} check", state)

    pre = [Option("ability", "Based on", "choice", default_ability, list(ABILITIES),
                  f"{name} normally uses {ABILITY_NAMES[default_ability]}. Pick another ability when the DM allows "
                  f"it (for example Strength for Intimidation).")]
    opts = common_options(ctx, base_roll, pre, _bespoke_check_options(ctx, default_ability, name))
    opts.append(Option("target", "Target DC", "int", 15))
    return RollOption(f"skill:{skill.name}", "Skills", name, f"{build({}).flat_total():+d}", opts, run,
                      {"ability": default_ability, "level": level})


def _ability_option(ctx: Ctx, ability: str) -> RollOption:
    base_roll = RollInfo("check", ability)

    def build(state) -> D20:
        d20 = D20()
        d20.add(f"{ability} modifier", ctx.mod(ability))
        half, why = _half_proficiency(ctx, ability)
        if half:
            d20.add(why.split(" (")[0], half)
            d20.notes.append(f"{why}: +{half}.")
        if state.get("rage") and ability == "STR" and ctx.lvl("Barbarian"):
            d20.adv.append("Rage")
        apply_rules(d20, ctx, base_roll, state)
        apply_user(d20, state)
        return d20

    def run(state):
        return _finish_d20(ctx, build(state), f"{ABILITY_NAMES[ability]} check", state)

    opts = common_options(ctx, base_roll, None, _bespoke_check_options(ctx, ability))
    opts.append(Option("target", "Target DC", "int", 15))
    return RollOption(f"check:{ability}", "Checks", f"{ABILITY_NAMES[ability]} check", f"{build({}).flat_total():+d}",
                      opts, run, {"ability": ability, "level": 0})


def _initiative_option(ctx: Ctx) -> RollOption:
    base_roll = RollInfo("initiative", "DEX")

    def build(state) -> D20:
        d20 = D20()
        d20.add("DEX modifier", ctx.mod("DEX"))
        d20.add("Initiative bonus", getattr(ctx.sheet, "initiative_bonus", 0))
        half, why = _half_proficiency(ctx, "DEX")
        if half:
            d20.add(why.split(" (")[0], half)
            d20.notes.append(f"{why}: +{half} (initiative is a Dexterity check).")
        apply_rules(d20, ctx, base_roll, state)
        apply_user(d20, state)
        return d20

    def run(state):
        return _finish_d20(ctx, build(state), "Initiative", state)

    opts = common_options(ctx, base_roll)
    opts.append(Option("target", "Target (to beat)", "int", 12))
    return RollOption("initiative", "Checks", "Initiative", f"{build({}).flat_total():+d}", opts, run,
                      {"ability": "DEX", "level": 0})


# ----------------------------------------------------------------------------- saving throws

def _save_option(ctx: Ctx, ability: str, concentration: bool = False) -> RollOption:
    base_roll = RollInfo("save", ability, concentration=concentration)
    proficient = ctx.save_proficient(ability)

    def build(state) -> D20:
        d20 = D20()
        d20.add(f"{ability} modifier", ctx.mod(ability))
        if proficient:
            d20.add("Proficiency", ctx.prof)
        if state.get("rage") and ability == "STR" and ctx.lvl("Barbarian"):
            d20.adv.append("Rage")
        if concentration and state.get("bladesong") and ctx.has("bladesong"):
            bonus = max(1, ctx.mod("INT"))
            d20.add("Bladesong", bonus)
            d20.notes.append(f"Bladesong: +{bonus} (Intelligence modifier, min +1) to concentration saves.")
        roll = RollInfo("save", ability, concentration=concentration,
                        save_vs=SAVE_VS.get(str(state.get("save_vs", "Anything else")), ""))
        apply_rules(d20, ctx, roll, state)
        apply_user(d20, state)
        return d20

    def run(state):
        title = "Concentration save (Constitution)" if concentration else f"{ABILITY_NAMES[ability]} saving throw"
        return _finish_d20(ctx, build(state), title, state)

    post = []
    if ability == "STR" and ctx.lvl("Barbarian"):
        post.append(Option("rage", "Raging", "bool", False, "Advantage on Strength saves."))
    if concentration and ctx.has("bladesong"):
        post.append(Option("bladesong", "Bladesong active", "bool", False,
                           "+INT modifier (min +1) to Constitution saves to maintain concentration."))
    opts = common_options(ctx, base_roll, None, post)
    opts.append(Option("target", "Save DC", "int", 12 if concentration else 15))
    summary = f"{build({}).flat_total():+d}"
    meta = {"ability": ability, "level": int(proficient)}
    if concentration:
        meta["concentration"] = True
        return RollOption("save:CON:concentration", "Saves", "Concentration save", summary, opts, run, meta)
    return RollOption(f"save:{ability}", "Saves", f"{ABILITY_NAMES[ability]} save", summary, opts, run, meta)


# ----------------------------------------------------------------------------- damage text

_DAMAGE_TOKEN = re.compile(r"([+-]?)\s*(\d*d\d+|\d+)", re.IGNORECASE)
DAMAGE_TYPES = ("acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison", "psychic",
                "radiant", "slashing", "thunder")


def parse_damage(text: str) -> Tuple[List[DiceTerm], int, str]:
    """Read a sheet's damage entry ("1d8+3 piercing", "2d6 +4 slashing + 1d6 fire") into dice, a flat bonus and the
    damage type words. Raises :class:`DiceError` if there is nothing to roll."""
    cleaned = re.sub(r"\([^)]*\)", " ", text or "")
    terms: List[DiceTerm] = []
    flat = 0
    for sign_text, body in _DAMAGE_TOKEN.findall(cleaned):
        sign = -1 if sign_text == "-" else 1
        if "d" in body.lower():
            count, _, sides = body.lower().partition("d")
            term = DiceTerm(int(count or 1), int(sides), sign)
            term.validate()
            terms.append(term)
        else:
            flat += sign * int(body)
    words = " ".join(re.findall(r"[A-Za-z]+", re.sub(r"\d*d\d+", " ", cleaned)))
    if not terms and not flat:
        raise DiceError(f"No damage found in '{text}'.")
    return terms, flat, words.strip()


def parse_bonus(text) -> Optional[int]:
    """A sheet's attack bonus entry ("+5", "7", "-1") as a number."""
    m = re.search(r"[+-]?\s*\d+", str(text or ""))
    return int(m.group(0).replace(" ", "")) if m else None


def _clone(term: DiceTerm, **changes) -> DiceTerm:
    new = DiceTerm(**term.__dict__)
    for k, v in changes.items():
        setattr(new, k, v)
    return new


def _doubled(terms: List[DiceTerm]) -> List[DiceTerm]:
    out = []
    for t in terms:
        d = _clone(t, count=t.count * 2)
        if d.keep:
            d.keep_n = min(d.count, t.keep_n * 2)
        out.append(d)
    return out


@dataclass
class DamagePlan:
    """How an attack's damage is built, so it can be rolled normally and as a critical hit."""
    weapon: List[DiceTerm]
    always: List[DiceTerm] = field(default_factory=list)        # extra dice on every hit (doubled on a crit)
    once: List[DiceTerm] = field(default_factory=list)          # extra dice on the first hit of the turn
    flat: int = 0
    savage: bool = False                                        # roll the weapon dice twice, keep the better
    piercer: bool = False                                       # reroll the lowest weapon die once
    crit_extra: int = 0                                         # extra weapon dice on a critical hit (not doubled)

    def dist(self, crit: bool, with_once: bool = True) -> Dist:
        terms = _doubled(self.weapon) if crit else self.weapon
        if terms:
            if self.piercer and with_once and len(terms) == 1 and not terms[0].keep:
                t = terms[0]
                total = reroll_lowest_distribution(t.single(), t.count, 1)
            else:
                total = Expression(terms, 0).distribution()
            if crit and self.crit_extra and self.weapon:
                big = max(self.weapon, key=lambda x: x.sides)
                total = total + _clone(big, count=self.crit_extra, keep="", keep_n=0).distribution()
            if self.savage and with_once:
                total = total.max_with(total)
        else:
            total = Dist.point(0)
        extras = list(self.always) + (list(self.once) if with_once else [])
        if extras:
            total = total + Expression(_doubled(extras) if crit else extras, 0).distribution()
        return total.shift(self.flat)


def _per_turn(d20: D20, natural: Dist, bonus: Dist, ac: int, first: DamagePlan, later: DamagePlan,
              attacks: int) -> Dist:
    """Damage over ``attacks`` attacks, where the once-per-turn bonuses go on the first hit."""
    miss, hit, crit = attack_outcomes(d20, natural, bonus, ac)
    hit_first, crit_first = first.dist(False), first.dist(True)
    hit_later, crit_later = later.dist(False, with_once=False), later.dist(True, with_once=False)
    states: Dict[bool, Tuple[float, Dist]] = {False: (1.0, Dist.point(0))}
    for _ in range(attacks):
        nxt: Dict[bool, List[Tuple[float, Dist]]] = {False: [], True: []}
        for used, (weight, dist) in states.items():
            nxt[used].append((weight * miss, dist))
            h, c = (hit_later, crit_later) if used else (hit_first, crit_first)
            nxt[True].append((weight * hit, dist + h))
            nxt[True].append((weight * crit, dist + c))
        states = {}
        for used, parts in nxt.items():
            total = sum(w for w, _ in parts)
            if total > 1e-15:
                states[used] = (total, Dist.mixture([(w, d) for w, d in parts]))
    return Dist.mixture([(w, d) for w, d in states.values()])


# ----------------------------------------------------------------------------- attacks

def _attack_use_default(name: str, equipment) -> str:
    low = name.lower()
    typ = str(getattr(equipment, "type", "") or "").lower()
    if "ranged" in typ or any(w in low for w in ("bow", "sling", "blowgun", "musket", "pistol")):
        return "Ranged"
    return "Melee"


def _weapon_is_heavy(equipment) -> Optional[bool]:
    if equipment is None:
        return None
    props = getattr(equipment, "properties", []) or []
    return any(str(p.get("name", "")).strip().lower() == "heavy" for p in props if isinstance(p, dict))


def _matching_weapon(items: List[ItemInfo], attack_name: str) -> Optional[ItemInfo]:
    low = attack_name.lower()
    for item in items:
        if item.weapon and item.weapon.keywords and item.weapon.keywords[0] in low:
            return item
    for item in items:
        if item.weapon and any(len(k) > 3 and k in low for k in item.weapon.keywords[1:]):
            return item
    if "unarmed" in low or "punch" in low or "martial arts" in low:
        for item in items:
            if item.weapon and item.weapon.unarmed:
                return item
    return None


def _damage_rule_options(ctx: Ctx, dctxs: List[DmgCtx]) -> List[Option]:
    out = []
    for r in damage_rules(ctx):
        if r.feature and not ctx.has(r.feature):
            continue
        if r.when is not None and not r.when(ctx):
            continue
        if any(r.applies(ctx, d) for d in dctxs):
            out.append(Option(f"dmg:{r.id}", r.toggle_label or r.label, "bool", r.default,
                              "once per turn" if r.once and dctxs[0].kind == "weapon" else ""))
    return out


def _apply_damage_rules(ctx: Ctx, dctx: DmgCtx, state, notes: List[str]):
    """(dice every hit, dice once per turn, flat) from the damage rules the character has switched on."""
    always: List[DiceTerm] = []
    once: List[DiceTerm] = []
    flat_total = 0
    for r in damage_rules(ctx):
        if (r.feature and not ctx.has(r.feature)) or (r.when and not r.when(ctx)) or not r.applies(ctx, dctx):
            continue
        if not state.get(f"dmg:{r.id}", r.default):
            continue
        if r.dice:
            count, sides = r.dice(ctx)
            if count >= 1:
                (once if r.once else always).append(DiceTerm(count, sides, minimum=r.minimum))
        flat_total += r.flat(ctx, dctx) if callable(r.flat) else r.flat
        notes.append(r.label)
    return always, once, flat_total


def _attack_option(ctx: Ctx, index: int, entry: Dict[str, str], lookups: Lookups) -> Optional[RollOption]:
    name = (entry.get("name") or "").strip()
    bonus_value = parse_bonus(entry.get("attack_bonus"))
    if not name or bonus_value is None:
        return None
    try:
        terms, flat, damage_text = parse_damage(entry.get("damage", ""))
        has_damage = True
    except DiceError:
        terms, flat, damage_text, has_damage = [], 0, "", False
    damage_types = [w for w in damage_text.lower().split() if w in DAMAGE_TYPES]
    dtype = damage_types[0] if damage_types else ""
    equipment = lookups.equipment(name)
    heavy = _weapon_is_heavy(equipment)
    weapon_items = [i for i in ctx.active_items if i.weapon]
    default_item = _matching_weapon(weapon_items, name)
    base_roll = RollInfo("attack", "STR", ranged=False)
    pre: List[Option] = [Option("use", "Attack with", "choice", _attack_use_default(name, equipment),
                                ["Melee", "Ranged", "Thrown"])]
    if weapon_items:
        pre.append(Option("magic_weapon", "Magic weapon", "choice", default_item.name if default_item else "None",
                          ["None"] + [i.name for i in weapon_items],
                          "Adds the item's bonus and extra damage on top of the sheet's numbers: choose None if the "
                          "sheet's attack bonus and damage already include it."))
    post: List[Option] = []
    if ctx.lvl("Barbarian"):
        post.append(Option("reckless", "Reckless Attack (advantage)", "bool", False))
        post.append(Option("rage", "Raging (Strength melee)", "bool", False, f"+{ctx.rage_damage()} damage."))
    if ctx.has("great_weapon_master") and ctx.feat_legacy("great_weapon_master"):
        post.append(Option("power_attack", "Power attack (-5 to hit, +10 damage)", "bool", False,
                           "Great Weapon Master (2014), heavy melee weapon."))
    elif ctx.has("great_weapon_master") and has_damage:
        post.append(Option("heavy_mastery", "Heavy weapon on your turn (+proficiency damage)", "bool",
                           bool(heavy) if heavy is not None else True,
                           "Great Weapon Master: + proficiency bonus damage with a Heavy weapon."))
    if ctx.feat("sharpshooter") and ctx.feat_legacy("sharpshooter"):
        post.append(Option("sharp_power", "Sharpshooter power shot (-5 to hit, +10 damage)", "bool", False))
    if has_damage:
        if ctx.has("sneak_attack"):
            post.append(Option("sneak", "Sneak Attack", "bool", False, f"{ctx.sneak_dice()}d6 once per turn."))
        if ctx.has("divine_smite"):
            post.append(Option("smite", "Divine Smite (slot level)", "choice", "None", ["None", "1", "2", "3", "4", "5"]))
        if ctx.has("eldritch_smite"):
            post.append(Option("pact_smite", "Eldritch Smite (pact slot level)", "choice", "None",
                               ["None", "1", "2", "3", "4", "5"]))
        if ctx.has("brutal_strike"):
            post.append(Option("brutal", "Brutal Strike (forgo Reckless Attack advantage)", "bool", False,
                               "+1d10 damage (2d10 from level 17)."))
        if ctx.has("great_weapon_fighting"):
            post.append(Option("gwf", "Wielded two-handed (Great Weapon Fighting)", "bool", True,
                               "1s and 2s on the weapon's damage dice count as 3 (2014: rerolled once)."))
        if ctx.has("savage_attacker"):
            post.append(Option("savage", "Savage Attacker (once per turn)", "bool", True,
                               "Roll the weapon's damage dice twice and use either."))
        if ctx.has("piercer") and dtype == "piercing":
            post.append(Option("piercer", "Piercer: reroll one damage die (once per turn)", "bool", True))
        post += _damage_rule_options(ctx, [DmgCtx("weapon", damage_type=dtype),
                                           DmgCtx("weapon", ranged=True, damage_type=dtype),
                                           DmgCtx("weapon", ranged=True, thrown=True, damage_type=dtype)])
        for item in weapon_items:
            for i, ex in enumerate(item.weapon.extras):
                post.append(Option(f"xtra:{item.name}:{i}", f"{ex.label} {ex.condition}".strip(), "bool", ex.default))
        for item in ctx.active_items:
            for i, ex in enumerate(item.global_extras):
                post.append(Option(f"gxtra:{item.name}:{i}", f"{ex.label} {ex.condition}".strip(), "bool", ex.default))
        post.append(Option("dmg_bonus", "Extra damage (flat)", "int", 0))
        post.append(Option("dmg_dice", "Extra damage dice (e.g. 1d6)", "text", ""))
    opts = common_options(ctx, base_roll, pre, post)
    opts.append(Option("target", "Target AC", "int", 15))
    opts.append(Option("attacks", "Attacks per turn", "int", ctx.attacks_per_turn()))

    def build_d20(state) -> Tuple[D20, Optional[ItemInfo]]:
        d20 = D20()
        d20.add("Attack bonus", bonus_value)
        use = str(state.get("use", "Melee"))
        roll = RollInfo("attack", "STR", ranged=(use == "Ranged"))
        item = None
        chosen = state.get("magic_weapon")
        if chosen and chosen != "None":
            item = next((i for i in weapon_items if i.name == chosen), None)
        if item is not None:
            d20.add(item.name, item.weapon.bonus)
            d20.crit_min = min(d20.crit_min, item.weapon.crit_min)
            if item.weapon.bonus:
                d20.notes.append(f"{item.name}: +{item.weapon.bonus} to attack and damage rolls.")
        if ctx.crit_min() < 20:
            d20.crit_min = min(d20.crit_min, ctx.crit_min())
            d20.notes.append(f"Critical hits on a natural {ctx.crit_min()}-20.")
        if state.get("power_attack") or state.get("sharp_power"):
            d20.add("Power attack", -5)
        if state.get("reckless") and ctx.lvl("Barbarian"):
            d20.adv.append("Reckless Attack")
        if state.get("brutal") and ctx.has("brutal_strike") and "Reckless Attack" in d20.adv:
            d20.adv.remove("Reckless Attack")
            d20.notes.append("Brutal Strike: the Reckless Attack advantage is given up for this attack.")
        apply_rules(d20, ctx, roll, state)
        apply_user(d20, state)
        return d20, item

    def build_damage(state, item: Optional[ItemInfo], notes: List[str]) -> Tuple[DamagePlan, DamagePlan]:
        use = str(state.get("use", "Melee"))
        dctx = DmgCtx("weapon", ranged=use in ("Ranged", "Thrown"), thrown=use == "Thrown",
                      unarmed="unarmed" in name.lower(), damage_type=dtype)
        weapon = [_clone(t) for t in terms]
        flat_total = flat
        always: List[DiceTerm] = []
        once: List[DiceTerm] = []
        savage = piercer = False
        if state.get("rage") and ctx.lvl("Barbarian"):
            flat_total += ctx.rage_damage()
            notes.append(f"Rage: +{ctx.rage_damage()} damage.")
        if state.get("sneak") and ctx.has("sneak_attack") and ctx.sneak_dice() >= 1:
            minimum = 3 if ctx.has("dread_incarnate") else 1
            once.append(DiceTerm(ctx.sneak_dice(), 6, minimum=minimum))
            notes.append(f"Sneak Attack: +{ctx.sneak_dice()}d6, once per turn (on the first hit)"
                         + (" (1s and 2s count as 3)." if minimum == 3 else "."))
        slot = str(state.get("smite", "None"))
        if slot.isdigit() and ctx.has("divine_smite"):
            always.append(DiceTerm(min(5, int(slot) + 1), 8))
            notes.append(f"Divine Smite: +{min(5, int(slot) + 1)}d8 radiant.")
        slot = str(state.get("pact_smite", "None"))
        if slot.isdigit() and ctx.has("eldritch_smite"):
            once.append(DiceTerm(int(slot) + 1, 8))
            notes.append(f"Eldritch Smite: +{int(slot) + 1}d8 force, once per turn.")
        if state.get("brutal") and ctx.has("brutal_strike"):
            always.append(DiceTerm(2 if ctx.lvl("Barbarian") >= 17 else 1, 10))
            notes.append("Brutal Strike: extra d10 damage.")
        if ctx.has("great_weapon_master") and not ctx.feat_legacy("great_weapon_master") and state.get("heavy_mastery"):
            flat_total += ctx.prof
            notes.append(f"Great Weapon Master: +{ctx.prof} damage (proficiency bonus) with a Heavy weapon.")
        if state.get("power_attack") or state.get("sharp_power"):
            flat_total += 10
            notes.append("Power attack: +10 damage (and -5 to hit).")
        if state.get("gwf") and ctx.has("great_weapon_fighting"):
            old = ctx.feat_legacy("great weapon fighting")
            for t in weapon:
                if old:
                    t.reroll_max, t.reroll_once = max(t.reroll_max, 2), True
                else:
                    t.minimum = max(t.minimum, 3)
            notes.append("Great Weapon Fighting: 1s and 2s on the weapon's dice "
                         + ("are rerolled once." if old else "count as 3."))
        if state.get("savage") and ctx.has("savage_attacker"):
            savage = True
            notes.append("Savage Attacker: the weapon's damage dice are rolled twice, you keep either (once per turn).")
        if state.get("piercer") and ctx.has("piercer") and dtype == "piercing":
            piercer = True
            notes.append("Piercer: one weapon damage die is rerolled once per turn (the lowest).")
        rule_always, rule_once, rule_flat = _apply_damage_rules(ctx, dctx, state, notes)
        always += rule_always
        once += rule_once
        flat_total += rule_flat
        if item is not None:
            flat_total += item.weapon.bonus
            for i, ex in enumerate(item.weapon.extras):
                if state.get(f"xtra:{item.name}:{i}", ex.default):
                    always.append(DiceTerm(ex.count, ex.sides))
                    notes.append(f"{ex.label} {ex.condition}".strip())
        for it in ctx.active_items:
            for i, ex in enumerate(it.global_extras):
                if state.get(f"gxtra:{it.name}:{i}", ex.default):
                    always.append(DiceTerm(ex.count, ex.sides))
                    notes.append(f"{ex.label} {ex.condition}".strip())
        try:
            flat_total += int(state.get("dmg_bonus", 0) or 0)
        except (TypeError, ValueError):
            pass
        text = str(state.get("dmg_dice", "") or "").strip()
        if text:
            extra = parse_expression(text)
            always.extend(extra.terms)
            flat_total += extra.flat
            notes.append(f"Extra damage: {text}.")
        crit_extra = 0                      # extra weapon dice on a critical hit (Brutal Critical, Savage Attacks ...)
        if ctx.has("brutal_critical"):
            lvl = ctx.lvl("Barbarian")
            crit_extra += 3 if lvl >= 17 else 2 if lvl >= 13 else 1
            notes.append(f"Brutal Critical: +{crit_extra} weapon dice on a critical hit.")
        if ctx.has("savage_attacks") and not dctx.ranged:
            crit_extra += 1
            notes.append("Savage Attacks: one extra weapon die on a melee critical hit.")
        if ctx.has("piercer") and dtype == "piercing" and state.get("piercer", True):
            crit_extra += 1
            notes.append("Piercer: one extra damage die on a piercing critical hit.")
        first = DamagePlan(weapon, always, once, flat_total, savage, piercer, crit_extra)
        later = DamagePlan(weapon, always, [], flat_total, False, False, crit_extra)
        return first, later

    def run(state):
        d20, item = build_d20(state)
        notes: List[str] = []
        natural, mode_notes = d20.natural()
        bonus = d20.bonus()
        ac = int(state.get("target", 15) or 15)
        miss, hit, crit = attack_outcomes(d20, natural, bonus, ac)
        views = [View("attack", "Attack roll", natural + bonus, "roll",
                      [("Chance to hit", f"{(hit + crit) * 100:.1f}%"), ("Critical hit", f"{crit * 100:.1f}%"),
                       (f"vs AC {ac}", f"miss {miss * 100:.1f}%")], "ac")]
        if d20.rescues:
            notes.append("If it misses: " + "; ".join(r.label for r in d20.rescues) + ".")
        if has_damage:
            first, later = build_damage(state, item, notes)
            hit_with, crit_with = first.dist(False), first.dist(True)
            on_hit = Dist.mixture([(hit, hit_with), (crit, crit_with)]) if hit + crit > 0 else Dist.point(0)
            per_attack = Dist.mixture([(miss, Dist.point(0)), (hit, hit_with), (crit, crit_with)])
            views.append(View("damage", "Damage when it hits", on_hit, "damage",
                              [("Average when it hits", f"{on_hit.mean():.2f}"),
                               ("Normal hit", f"{hit_with.mean():.2f}"), ("Critical hit", f"{crit_with.mean():.2f}")]))
            views.append(View("per_attack", "Damage per attack", per_attack, "damage",
                              [("Average per attack", f"{per_attack.mean():.2f}"),
                               ("Chance to deal damage", f"{(hit + crit) * 100:.1f}%")]))
            n = max(1, min(8, int(state.get("attacks", 1) or 1)))
            if n > 1:
                turn = _per_turn(d20, natural, bonus, ac, first, later, n)
                views.append(View("per_turn", f"Damage per turn ({n} attacks)", turn, "damage",
                                  [(f"Average over {n} attacks", f"{turn.mean():.2f}")]))
            if damage_types:
                notes.append(f"Damage type: {', '.join(damage_types)}.")
        return Analysis(d20.formula(), views, d20.breakdown() + notes + d20.notes + mode_notes, bonus=d20.flat_total())

    summary = f"{bonus_value:+d}" + (f", {entry.get('damage', '').strip()}" if has_damage else "")
    return RollOption(f"attack:{index}", "Attacks", name, summary, opts, run)


# ----------------------------------------------------------------------------- spells

_ABILITY_WORDS = "|".join(ABILITY_NAMES.values())
_DAMAGE_RE = re.compile(r"(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?\s+(?:\w+\s+)?damage", re.IGNORECASE)
_TYPED_DAMAGE_RE = re.compile(r"(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?\s+([A-Za-z]+)\s+damage", re.IGNORECASE)
_HEAL_RE = re.compile(r"regains?[^.]*?(\d+)d(\d+)", re.IGNORECASE)
_SAVE_RE = re.compile(rf"({_ABILITY_WORDS})\s+saving throw", re.IGNORECASE)
_SLOT_RE = re.compile(r"(?:damage|healing)\s+increases\s+by\s+(\d+)d(\d+)\s+for\s+each\s+(?:spell\s+)?slot\s+level\s+above\s+(\d+)",
                      re.IGNORECASE)
_CANTRIP_TIER_RE = re.compile(r"(\d+)\s*\((\d+)d(\d+)(?:\s+or\s+\d+d\d+)?\)")
SCHOOLS = ("abjuration", "conjuration", "divination", "enchantment", "evocation", "illusion", "necromancy",
           "transmutation")

# spells that throw several separate attacks/darts: name -> (base slot level, count at base, per slot above, auto-hit)
_MULTI_HIT = {
    "magic missile": (1, 3, 1, True),
    "scorching ray": (2, 3, 1, False),
}


@dataclass
class SpellInfo:
    name: str
    level: int
    attack: bool = False
    save: str = ""
    half: bool = False
    dice: Optional[Tuple[int, int, int]] = None       # count, sides, flat
    damage_type: str = ""
    healing: bool = False
    add_mod: bool = False
    school: str = ""
    slot_step: Optional[Tuple[int, int, int]] = None  # extra dice per slot level above: count, sides, base level
    cantrip_dice: List[Tuple[int, int, int]] = field(default_factory=list)   # (character level, count, sides)
    beams: Optional[List[Tuple[int, int]]] = None     # (character level, beams) for Eldritch Blast style


def parse_spell(spell) -> Optional[SpellInfo]:
    """Read a spell's description for what it rolls. ``None`` if it has no damage or healing dice."""
    text = (getattr(spell, "description", "") or "").replace("\\", "\n")
    info = SpellInfo(spell.name, spell.level)
    info.attack = bool(re.search(r"spell attack", text, re.IGNORECASE))
    tags = [str(t).lower() for t in (getattr(spell, "tags", []) or [])]
    info.school = next((t for t in tags if t in SCHOOLS), "")
    m = _SAVE_RE.search(text)
    if m:
        info.save = next(k for k, v in ABILITY_NAMES.items() if v.lower() == m.group(1).lower())
    info.half = bool(re.search(r"half as much damage", text, re.IGNORECASE))
    m = _TYPED_DAMAGE_RE.search(text) or _DAMAGE_RE.search(text)
    if m:
        flat = int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
        info.dice = (int(m.group(1)), int(m.group(2)), flat)
        dtype = m.group(5).lower() if m.lastindex and m.lastindex >= 5 and m.group(5) else ""
        info.damage_type = dtype if dtype in DAMAGE_TYPES else next((t for t in tags if t in DAMAGE_TYPES), "")
    else:
        h = _HEAL_RE.search(text)
        if not h:
            return None
        info.healing = True
        info.dice = (int(h.group(1)), int(h.group(2)), 0)
        info.add_mod = bool(re.search(r"plus your spellcasting ability modifier", text, re.IGNORECASE))
    s = _SLOT_RE.search(text)
    if s:
        info.slot_step = (int(s.group(1)), int(s.group(2)), int(s.group(3)))
    if spell.level == 0:
        up = re.search(r"Cantrip Upgrade[^\n]*", text, re.IGNORECASE)
        if up:
            tiers = [(int(lv), int(c), int(sd)) for lv, c, sd in _CANTRIP_TIER_RE.findall(up.group(0))]
            info.cantrip_dice = tiers
            beam = re.search(r"two beams at level 5, three beams at level 11, and four beams at level 17", text,
                             re.IGNORECASE)
            if beam:
                info.beams = [(5, 2), (11, 3), (17, 4)]
    return info


def _spellcasting(ctx: Ctx, lookups: Lookups) -> List[Tuple[str, str]]:
    """[(class name, casting ability)] for the character's spellcasting classes."""
    out = []
    for name in ctx.levels:
        ability = ""
        cd = lookups.class_def(name)
        if cd is not None:
            ability = (getattr(cd, "spellcasting_ability", "") or "").upper()
        if not ability:
            sub = ctx.subclasses.get(name, "")
            if "eldritch knight" in sub or "arcane trickster" in sub:
                ability = "INT"
            elif "mystic arts" in sub:                                      # Warrior of the Mystic Arts casts with Wisdom
                ability = "WIS"
        if ability in ABILITIES:
            out.append((name, ability))
    return out


@dataclass
class SpellStat:
    """A spellcasting ability's numbers: the spell attack modifier and the spell save DC."""
    label: str                         # "Wizard", "Cleric / Druid", "Species and feat spells"
    ability: str                       # "INT"
    attack: int
    dc: int
    notes: List[str] = field(default_factory=list)       # what magic items add, or why they do not count


def spell_numbers(character, sheet, lookups: Optional[Lookups] = None, extra_casters: bool = False) -> List[SpellStat]:
    """The spell attack modifier and spell save DC of each of the character's spellcasting classes, with the
    bonuses of linked magic items (attuned ones only; the rest are noted). Classes that cast with the same ability
    and get the same numbers share one entry. ``extra_casters`` adds the best of Intelligence, Wisdom and Charisma
    for a character whose only spells come from a species or a feat."""
    lookups = lookups or Lookups()
    items = parse_items(sheet, lookups.magic_item)
    ctx = Ctx(character, sheet, None, items)
    casters = _spellcasting(ctx, lookups)
    entries: List[SpellStat] = []
    if not casters and extra_casters:
        best = max(("INT", "WIS", "CHA"), key=lambda a: ctx.mod(a))
        casters = [("Species and feat spells", best)]
    for name, ability in casters:
        stat = SpellStat(name, ability, ctx.spell_attack_bonus(ability, name), ctx.spell_dc(ability, name))
        for it in items:
            if not (it.spell_attack or it.spell_dc):
                continue
            if it.spell_class and it.spell_class.lower() != name.lower():
                continue
            bonus = f"+{it.spell_attack} attack, +{it.spell_dc} DC"
            if it in ctx.active_items:
                stat.notes.append(f"{it.name}: {bonus}")
            else:
                stat.notes.append(f"{it.name}: {bonus} (not counted: {it.reason or 'not usable'})")
        for other in entries:
            if (other.ability, other.attack, other.dc) == (stat.ability, stat.attack, stat.dc):
                other.label += f" / {name}"
                other.notes += [n for n in stat.notes if n not in other.notes]
                break
        else:
            entries.append(stat)
    return entries


def _spell_option(ctx: Ctx, info: SpellInfo, casters: List[Tuple[str, str]]) -> RollOption:
    multi = _MULTI_HIT.get(info.name.lower())
    by_ability: Dict[str, str] = {}
    for cls, ab in casters:
        by_ability.setdefault(ab, cls)
    abilities = sorted(by_ability or {"INT": "", "WIS": "", "CHA": ""}, key=lambda a: -ctx.mod(a))
    base_level = info.level
    base_roll = RollInfo("spell", abilities[0], spell_class=by_ability.get(abilities[0], ""))
    dctx = DmgCtx("spell", spell_name=info.name, cantrip=info.level == 0, level=info.level, school=info.school,
                  healing=info.healing, damage_type=info.damage_type, attack_roll=info.attack)

    opts: List[Option] = []
    if base_level > 0 and (info.slot_step or multi or info.healing):
        opts.append(Option("slot", "Cast at slot level", "choice", str(base_level),
                           [str(n) for n in range(base_level, MAX_SPELL_SLOT + 1)]))
    if len(abilities) > 1:
        opts.append(Option("ability", "Spellcasting ability", "choice", abilities[0], abilities))
    if info.attack:
        opts += common_options(ctx, base_roll)
        opts.append(Option("target", "Target AC", "int", 15))
    elif info.save:
        opts.append(Option("target", "Target's save bonus", "int", 2))
        opts.append(Option("target_mode", "Target rolls", "choice", "Normal", ["Normal", "Advantage", "Disadvantage"]))
        opts += rule_options(ctx, base_roll)                 # Innate Sorcery's +1 DC and the like
    else:
        opts += rule_options(ctx, base_roll)
    opts.append(Option("reroll", "Reroll damage dice showing at most (once)", "int", 0))
    opts.append(Option("minimum", "Damage dice below this count as it", "int", 1))
    if ctx.has("elemental_adept") and not info.healing:
        opts.append(Option("adept", "Elemental Adept applies (1s count as 2)", "bool", True))
    if ctx.has("flames_of_phlegethos") and info.damage_type == "fire":
        opts.append(Option("flames", "Flames of Phlegethos (reroll 1s)", "bool", True))
    if ctx.has("empowered_spell") and not info.healing:
        opts.append(Option("empowered", "Empowered Spell (reroll up to your Charisma modifier dice)", "bool", True))
    opts += _damage_rule_options(ctx, [dctx])
    opts.append(Option("dmg_bonus", "Extra damage (flat)", "int", 0))
    opts.append(Option("dmg_dice", "Extra damage dice (e.g. 1d6)", "text", ""))

    def run(state):
        notes: List[str] = []
        ability = str(state.get("ability", abilities[0]))
        spell_class = by_ability.get(ability, "")
        roll = RollInfo("spell", ability, spell_class=spell_class)
        mod = ctx.mod(ability)
        d20 = D20()
        apply_rules(d20, ctx, roll, state)
        attack_bonus = ctx.spell_attack_bonus(ability, spell_class)
        dc = ctx.spell_dc(ability, spell_class) + d20.dc_bonus
        notes.append(f"Spellcasting: {ability} {mod:+d}, proficiency +{ctx.prof}: attack {attack_bonus:+d}, save DC {dc}.")
        for it in ctx.active_items:
            if it.spell_attack or it.spell_dc:
                notes.append(f"{it.name}: +{it.spell_attack} spell attack, +{it.spell_dc} spell save DC.")

        slot = int(state.get("slot", base_level) or base_level)
        dice_count, sides, flat = info.dice
        if info.level == 0 and info.cantrip_dice:
            for level, count, side in sorted(info.cantrip_dice):
                if ctx.total_level >= level:
                    dice_count, sides = count, side
            notes.append(f"Cantrip damage at character level {ctx.total_level}: {dice_count}d{sides}.")
        if info.slot_step and slot > base_level:
            step_count, step_sides, from_level = info.slot_step
            extra = (slot - max(base_level, from_level)) * step_count
            dice_count += max(0, extra)
            if extra > 0:
                notes.append(f"Slot level {slot}: +{extra}d{step_sides}.")
        projectiles = 1
        if multi:
            m_base, m_count, m_per, m_auto = multi
            projectiles = m_count + (slot - m_base) * m_per
            notes.append(f"{projectiles} {'darts' if m_auto else 'rays'}.")
        if info.beams:
            projectiles = 1
            for level, beams in info.beams:
                if ctx.total_level >= level:
                    projectiles = beams
            notes.append(f"{projectiles} beam{'s' if projectiles != 1 else ''} at character level {ctx.total_level}.")
        spell_ctx = DmgCtx("spell", spell_name=info.name, cantrip=info.level == 0, level=slot, school=info.school,
                           healing=info.healing, damage_type=info.damage_type, attack_roll=info.attack)

        term = DiceTerm(dice_count, sides)
        try:
            term.reroll_max = max(0, int(state.get("reroll", 0) or 0))
            term.minimum = max(1, int(state.get("minimum", 1) or 1))
        except (TypeError, ValueError):
            pass
        if state.get("adept") and ctx.has("elemental_adept"):
            term.minimum = max(term.minimum, 2)
            notes.append("Elemental Adept: damage dice showing 1 count as 2.")
        if state.get("flames") and ctx.has("flames_of_phlegethos"):
            term.reroll_max = max(term.reroll_max, 1)
            notes.append("Flames of Phlegethos: fire damage dice showing 1 are rerolled.")
        supreme = False
        if info.healing:
            if ctx.has("supreme_healing"):
                term.minimum, supreme = sides, True
                notes.append("Supreme Healing: healing dice count as their highest number.")
            elif ctx.has("healer") and not ctx.feat_legacy("healer"):
                term.reroll_max = max(term.reroll_max, 1)
                notes.append("Healer: healing dice showing 1 are rerolled.")
            if info.name.lower() == "cure wounds" and ctx.has("greater_mark_healing"):
                term.minimum = max(term.minimum, 3)
                notes.append("Greater Mark of Healing: 1s and 2s on Cure Wounds count as 3.")
        if term.reroll_max:
            notes.append(f"Damage dice of {term.reroll_max} or less are rerolled once.")
        if term.minimum > 1 and not supreme:
            notes.append(f"Damage dice below {term.minimum} count as {term.minimum}.")
        empowered = bool(state.get("empowered")) and ctx.has("empowered_spell") and not info.healing
        bonus = flat
        if info.add_mod:
            bonus += mod
            notes.append(f"Healing includes your spellcasting modifier ({mod:+d}).")
        try:
            bonus += int(state.get("dmg_bonus", 0) or 0)
        except (TypeError, ValueError):
            pass
        always_extra: List[DiceTerm] = []
        once_extra: List[DiceTerm] = []
        once_flat = beam_flat = 0
        for r in damage_rules(ctx):
            if (r.feature and not ctx.has(r.feature)) or (r.when and not r.when(ctx)) or not r.applies(ctx, spell_ctx):
                continue
            if not state.get(f"dmg:{r.id}", r.default):
                continue
            if r.dice:
                count, side = r.dice(ctx)
                if count >= 1:
                    (once_extra if r.once else always_extra).append(DiceTerm(count, side))
            add = r.flat(ctx, spell_ctx) if callable(r.flat) else r.flat
            if r.per_projectile:
                beam_flat += add
            else:
                once_flat += add
            notes.append(r.label)
        extra_text = str(state.get("dmg_dice", "") or "").strip()
        if extra_text and not info.healing:
            ex = parse_expression(extra_text)
            always_extra.extend(ex.terms)
            bonus += ex.flat
        if empowered:
            notes.append(f"Empowered Spell: up to {max(1, ctx.mod('CHA'))} damage dice are rerolled (the lowest, "
                         f"and only if they show less than average).")

        def base_dice(crit: bool) -> Dist:
            t = _clone(term, count=term.count * (2 if crit else 1))
            if empowered and not term.reroll_max:
                return reroll_lowest_distribution(_clone(t, count=1).single(), t.count, max(1, ctx.mod("CHA")))
            return t.distribution()

        def damage(crit: bool) -> Dist:
            total = base_dice(crit).shift(bonus + beam_flat)
            extras = always_extra + once_extra
            if extras:
                total = total + Expression(_doubled(extras) if crit else extras, 0).distribution()
            return total.shift(once_flat)

        unit = "healing" if info.healing else "damage"
        kind_word = "Healing" if info.healing else "Damage"
        formula = f"{dice_count}d{sides}" + (f" {flat:+d}" if flat else "") + (f" {info.damage_type}" if info.damage_type else "")
        if projectiles > 1:
            formula = f"{projectiles} x ({formula})"
        views: List[View] = []

        def project(one: Dist) -> Dist:
            return one.power(projectiles) if projectiles > 1 else one

        if info.healing:
            one = damage(False)
            views.append(View("heal", "Healing", one, "healing", [("Average healing", f"{one.mean():.2f}")]))
            return Analysis(formula, views, notes)

        if info.attack:
            apply_user(d20, state)
            natural, mode_notes = d20.natural()
            ac = int(state.get("target", 15) or 15)
            d20.add("Spell attack bonus", attack_bonus)
            bonus_d = d20.bonus()
            miss, hit, crit = attack_outcomes(d20, natural, bonus_d, ac)
            views.append(View("attack", "Spell attack roll", natural + bonus_d, "roll",
                              [("Chance to hit", f"{(hit + crit) * 100:.1f}%"), ("Critical hit", f"{crit * 100:.1f}%")], "ac"))
            normal, critical = damage(False), damage(True)
            on_hit = Dist.mixture([(hit, normal), (crit, critical)]) if hit + crit > 0 else Dist.point(0)
            one = Dist.mixture([(miss, Dist.point(0)), (hit, normal), (crit, critical)])
            views.append(View("damage", f"{kind_word} when it hits", on_hit, unit,
                              [("Average when it hits", f"{on_hit.mean():.2f}")]))
            total = project(one)
            title = f"{kind_word} per cast" + (f" ({projectiles} attacks)" if projectiles > 1 else "")
            views.append(View("per_cast", title, total, unit,
                              [("Average per cast", f"{total.mean():.2f}"),
                               ("Chance to deal damage", f"{(1 - miss ** projectiles) * 100:.1f}%")]))
            return Analysis(formula, views, notes + d20.breakdown() + d20.notes + mode_notes)

        if info.save:
            target_bonus = int(state.get("target", 2) or 0)
            mode = state.get("target_mode", "Normal")
            copies, pick = (2, "high") if mode == "Advantage" else (2, "low") if mode == "Disadvantage" else (1, "high")
            roll_d = DiceTerm(1, 20, copies=copies, pick=pick).distribution().shift(target_bonus)
            fail = 1.0 - roll_d.at_least(dc)
            full = damage(False)
            success = damage(False).halved() if info.half else Dist.point(0)
            one = Dist.mixture([(fail, full), (1 - fail, success)])
            views.append(View("failed", f"{kind_word} on a failed save", full, unit,
                              [("Save DC", str(dc)), ("Average", f"{full.mean():.2f}")]))
            total = project(one)
            views.append(View("expected", f"{kind_word} per cast (target bonus {target_bonus:+d})", total, unit,
                              [("Chance the target fails", f"{fail * 100:.1f}%"),
                               ("Average per cast", f"{total.mean():.2f}"),
                               ("On a success", "half damage" if info.half else "no damage")]))
            return Analysis(formula, views, notes + d20.notes)

        one = damage(False)
        total = project(one)
        views.append(View("auto", f"{kind_word} (automatic)", total, unit, [("Average", f"{total.mean():.2f}")]))
        return Analysis(formula, views, notes)

    label = "Cantrip" if info.level == 0 else f"Level {info.level}"
    kind = "attack" if info.attack else (f"{info.save} save" if info.save else "healing" if info.healing else "auto")
    return RollOption(f"spell:{info.name}", "Spells", info.name, f"{label}, {kind}", opts, run)


# ----------------------------------------------------------------------------- everything

class CharacterAnalyzer:
    """Builds the analyzable rolls for one character."""

    def __init__(self, character, sheet, lookups: Optional[Lookups] = None,
                 manual_features: Optional[Set[str]] = None, disabled_items: Optional[Set[str]] = None):
        self.lookups = lookups or Lookups()
        self.items: List[ItemInfo] = parse_items(sheet, self.lookups.magic_item)
        self.ctx = Ctx(character, sheet, manual_features, self.items, disabled_items)
        homebrew = collect(self.ctx, self.lookups)                 # what custom feats, traits and features do
        self.ctx.extra_rules = homebrew.rules
        self.ctx.extra_damage_rules = homebrew.damage_rules
        self.homebrew_labels = homebrew.labels
        self.character = character
        self.sheet = sheet

    def feature_report(self, all_features: bool = False) -> List[Tuple[str, str, str]]:
        """[(feature id, label, "sheet" | "manual" | "")]: every feature found on the sheet, then the ones that can
        be ticked by hand (every feature the analyzer knows, when ``all_features`` is set, for a search)."""
        out = []
        for fid, f in FEATURES.items():
            src = self.ctx.source(fid)
            if src == "sheet" or src == "manual" or (not src and (f.manual or all_features)):
                out.append((fid, f.label, src))
        for i, label in enumerate(self.homebrew_labels):                    # homebrew with roll effects
            out.append((f"homebrew:{i}", f"{label} (homebrew)", "sheet"))
        return out

    def item_report(self) -> List[Tuple[str, bool, str, str]]:
        """[(item name, counts, why not, what it does)] for the linked magic items that change rolls."""
        out = []
        for it in self.items:
            if not it.does_anything:
                continue
            bits = []
            if it.ability_sets:
                bits.append(", ".join(f"{k} {v}" for k, v in it.ability_sets.items()))
            if it.spell_attack or it.spell_dc:
                bits.append(f"spells +{it.spell_attack}/+{it.spell_dc}")
            if it.weapon:
                bits.append(f"weapon +{it.weapon.bonus}" if it.weapon.bonus else "weapon")
            if it.rules:
                bits.append(f"{len(it.rules)} roll effect{'s' if len(it.rules) != 1 else ''}")
            out.append((it.name, it.usable and it.name not in self.ctx.disabled_items, it.reason, ", ".join(bits)))
        return out

    def spells(self) -> List[SpellInfo]:
        names: List[str] = []
        for attr in ("known_spells", "prepared_spells", "subclass_spells", "class_feature_spells"):
            for n in getattr(self.character, attr, []) or []:
                if n not in names:
                    names.append(n)
        out = []
        for n in names:
            spell = self.lookups.spell(n)
            if spell is None:
                continue
            info = parse_spell(spell)
            if info is not None:
                out.append(info)
        return sorted(out, key=lambda i: (i.level, i.name))

    def rolls(self) -> List[RollOption]:
        ctx = self.ctx
        out: List[RollOption] = []
        for entry_index, entry in enumerate(getattr(self.sheet, "attacks", []) or []):
            opt = _attack_option(ctx, entry_index, entry, self.lookups)
            if opt:
                out.append(opt)
        casters = _spellcasting(ctx, self.lookups)
        for info in self.spells():
            out.append(_spell_option(ctx, info, casters))
        out.append(_initiative_option(ctx))
        for skill in Skill:
            out.append(_skill_option(ctx, skill))
        for ability in ABILITIES:
            out.append(_save_option(ctx, ability))
        if casters:
            out.append(_save_option(ctx, "CON", concentration=True))
        for ability in ABILITIES:
            out.append(_ability_option(ctx, ability))
        return out


def _outcomes(natural: Dist, bonus: Dist, armor_class: int, crit_min: int) -> Tuple[float, float, float]:
    """Hit chances for tests and callers that only need them: (miss, hit, crit)."""
    return attack_outcomes(D20(crit_min=crit_min), natural, bonus, armor_class)
