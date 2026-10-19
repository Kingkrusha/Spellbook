"""
What follows from what on a monster's stat block (no UI).

The Monster editor works like a character sheet: a monster's *Challenge Rating* sets its proficiency bonus, its
*size* sets its hit die, its hit points come from its hit dice and Constitution, and an attack is a core stat plus the
proficiency bonus to hit and the stat's modifier to the damage. This module holds those rules and writes the stat block
text that results ("Melee Attack Roll: +7, reach 5 ft. Hit: 13 (2d6 + 4) Slashing damage."), so the editor can show
the numbers, say where each one comes from, and keep them in step when a score or the CR changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

ABILITIES = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
ABILITY_NAMES = {"STR": "Strength", "DEX": "Dexterity", "CON": "Constitution", "INT": "Intelligence",
                 "WIS": "Wisdom", "CHA": "Charisma"}
_NAME_TO_ABILITY = {v.lower(): k for k, v in ABILITY_NAMES.items()}

DAMAGE_TYPES = ["Acid", "Bludgeoning", "Cold", "Fire", "Force", "Lightning", "Necrotic", "Piercing", "Poison",
                "Psychic", "Radiant", "Slashing", "Thunder"]

# the hit die of each size, as in the Monster Manual
SIZE_HIT_DIE = {"Tiny": 4, "Small": 6, "Medium": 8, "Large": 10, "Huge": 12, "Gargantuan": 20}

ATTACK_KINDS = {"melee": "Melee", "ranged": "Ranged", "both": "Melee or Ranged"}


def hit_die_for_size(size: str) -> int:
    return SIZE_HIT_DIE.get((size or "").strip().title(), 8)


def modifier(score: int) -> int:
    return (int(score) - 10) // 2


def signed(n: int) -> str:
    return f"+{n}" if n >= 0 else f"-{abs(n)}"


def hit_points(count: int, die: int, con_mod: int) -> int:
    """Average hit points: each die averages half its faces plus a half, plus the Constitution modifier."""
    if count <= 0:
        return 1
    return max(1, (count * (die + 1)) // 2 + count * con_mod)


def hit_dice_text(count: int, die: int, con_mod: int) -> str:
    """'6d10 + 12'."""
    if count <= 0:
        return ""
    bonus = count * con_mod
    if bonus > 0:
        return f"{count}d{die} + {bonus}"
    if bonus < 0:
        return f"{count}d{die} - {abs(bonus)}"
    return f"{count}d{die}"


_HD = re.compile(r"^\s*(\d+)\s*d\s*(\d+)\s*(?:([+-])\s*(\d+))?\s*$", re.I)


def parse_hit_dice(text: str) -> Optional[Tuple[int, int, int]]:
    """(count, die, bonus) from '18d12 + 90', or None."""
    m = _HD.match(text or "")
    if not m:
        return None
    bonus = int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
    return int(m.group(1)), int(m.group(2)), bonus


_DICE = re.compile(r"^\s*(\d+)\s*d\s*(\d+)\s*$", re.I)


def parse_dice(text: str) -> Optional[Tuple[int, int]]:
    m = _DICE.match(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def dice_average(n: int, sides: int, bonus: int = 0) -> int:
    return (n * (sides + 1)) // 2 + bonus


@dataclass
class Stats:
    """What an attack needs to know about its monster."""
    prof: int = 2
    mods: Dict[str, int] = field(default_factory=lambda: {a: 0 for a in ABILITIES})
    cr: str = "0"


@dataclass
class Built:
    """A generated stat block entry and where its numbers came from."""
    text: str = ""
    bonus: Optional[int] = None            # to hit
    dc: Optional[int] = None
    average: Optional[int] = None          # damage on a hit / failed save
    expression: str = ""                    # "2d6 + 4"
    tip_bonus: str = ""
    tip_damage: str = ""
    tip_dc: str = ""
    problem: str = ""


def _mod_text(mod: int) -> str:
    return f" + {mod}" if mod > 0 else (f" - {abs(mod)}" if mod < 0 else "")


def _damage_clause(dice: str, dtype: str, mod: int = 0) -> Tuple[str, Optional[int], str]:
    """('13 (2d6 + 4) Slashing damage', 13, '2d6 + 4') for ``dice``, with ``mod`` added; blank dice -> ''."""
    parsed = parse_dice(dice)
    if not parsed:
        return "", None, ""
    n, sides = parsed
    avg = dice_average(n, sides, mod)
    expr = f"{n}d{sides}{_mod_text(mod)}"
    return f"{avg} ({expr}) {(dtype or 'Slashing').title()} damage", avg, expr


def attack_built(build: dict, stats: Stats) -> Built:
    """An attack: the stat plus the proficiency bonus to hit, the stat's modifier once to the damage."""
    ability = build.get("ability", "STR")
    mod = stats.mods.get(ability, 0)
    prof = stats.prof if build.get("proficient", True) else 0
    bonus = mod + prof
    out = Built(bonus=bonus)
    name = ABILITY_NAMES.get(ability, ability)
    out.tip_bonus = f"{signed(mod)} from {name}" + (f", {signed(prof)} from proficiency" if prof else "")
    kind = build.get("kind", "melee")
    reach = str(build.get("reach") or "5").strip()
    rng = str(build.get("range") or "").strip()
    if kind == "ranged":
        where = f"range {rng or '80/320'} ft."
    elif kind == "both":
        where = f"reach {reach} ft. or range {rng or '20/60'} ft."
    else:
        where = f"reach {reach} ft."
    head = f"{ATTACK_KINDS.get(kind, 'Melee')} Attack Roll: {signed(bonus)}, {where}"
    primary, avg, expr = _damage_clause(build.get("dice", ""), build.get("type", ""), mod)
    out.average, out.expression = avg, expr
    if primary:
        out.tip_damage = (f"{signed(mod)} from {name} is added to the damage" if mod
                          else f"{name} modifier is +0, so nothing is added") + f"; {expr} averages {avg}"
    extra, _a, _e = _damage_clause(build.get("extra_dice", ""), build.get("extra_type", ""), 0)
    hit = primary
    if primary and extra:
        hit = f"{primary} plus {extra}"
    elif extra:
        hit = extra
    effect = (build.get("effect") or "").strip()
    out.text = f"{head} {_join_effect('Hit: ', hit, effect)}"
    return out


def _join_effect(lead: str, damage: str, effect: str) -> str:
    """'Hit: 9 (1d6 + 3) Slashing damage.' plus whatever follows it. An effect that starts with a comma or a period
    carries on the sentence as written (', and the target is Prone.'); any other starts a sentence of its own."""
    if not damage and not effect:
        return f"{lead}—"
    if not damage:
        return f"{lead}{effect}"
    if not effect:
        return f"{lead}{damage}."
    if effect[0] in ",.;":
        return f"{lead}{damage}{effect}"
    return f"{lead}{damage}. {effect}"


def save_built(build: dict, stats: Stats) -> Built:
    """A saving throw effect: DC is 8 + proficiency + the stat's modifier."""
    dc_ability = build.get("dc_ability", "CON")
    mod = stats.mods.get(dc_ability, 0)
    dc = 8 + stats.prof + mod
    out = Built(dc=dc)
    name = ABILITY_NAMES.get(dc_ability, dc_ability)
    out.tip_dc = f"8 + {signed(mod)[1:] if mod >= 0 else signed(mod)} from {name} + {stats.prof} from proficiency " \
                 f"(CR {stats.cr}) = {dc}"
    save = ABILITY_NAMES.get(build.get("save", "DEX"), "Dexterity")
    area = (build.get("area") or "").strip().rstrip(".")
    head = f"{save} Saving Throw: DC {dc}" + (f", {area}" if area else "") + "."
    clause, avg, expr = _damage_clause(build.get("dice", ""), build.get("type", ""), 0)
    out.average, out.expression = avg, expr
    if clause:
        out.tip_damage = f"{expr} averages {avg}"
    effect = (build.get("effect") or "").strip()
    out.text = f"{head} {_join_effect('Failure: ', clause, effect)}"
    success = (build.get("success") or "").strip()
    if success:
        out.text += f" Success: {success}"
    elif build.get("half", True) and clause:
        out.text += " Success: Half damage."
    after = (build.get("after") or "").strip()
    if after:
        out.text += f" {after}"
    return out


def built(build: dict, stats: Stats) -> Built:
    """The generated entry for a ``build`` dict (mode 'attack' or 'save')."""
    return save_built(build, stats) if build.get("mode") == "save" else attack_built(build, stats)


# --------------------------------------------------------------------------- reading an existing entry

_ATTACK = re.compile(r"^\s*(Melee or Ranged|Melee|Ranged)(?: Weapon| Spell)? Attack(?: Roll)?:\s*([+-]\d+)", re.I)
_HIT = re.compile(r"Hit:\s*(\d+)\s*\((\d+d\d+)(?:\s*([+-])\s*(\d+))?\)\s*([A-Za-z]+)\s+damage", re.I)
_PLUS = re.compile(r"plus\s*(\d+)\s*\((\d+d\d+)(?:\s*[+-]\s*\d+)?\)\s*([A-Za-z]+)\s+damage", re.I)
_SAVE = re.compile(r"^\s*(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+Saving Throw:\s*DC\s*(\d+)"
                   r"(?:,\s*([^.]*))?\.", re.I)
_FAIL_DAMAGE = re.compile(r"\s*(\d+)\s*\((\d+d\d+)(?:\s*[+-]\s*\d+)?\)\s*([A-Za-z]+)\s+damage", re.I)


def _tidy_effect(text: str) -> str:
    """What follows a damage clause, as written ('. The target is Prone.' keeps its leading period)."""
    text = (text or "").strip()
    return text


def guess_build(text: str, stats: Stats) -> Optional[dict]:
    """A ``build`` dict that reproduces ``text`` from the monster's stats, or None if it is not an attack or a save
    effect, or its numbers do not follow from the stats (so linking it would change them)."""
    text = text or ""
    m = _ATTACK.match(text)
    if m:
        bonus = int(m.group(2))
        kind = {"melee": "melee", "ranged": "ranged", "melee or ranged": "both"}[m.group(1).lower()]
        hit = _HIT.search(text)
        mod_in_text = None
        if hit:
            mod_in_text = int(hit.group(4) or 0) * (-1 if hit.group(3) == "-" else 1)
        choice = None
        for ability in ABILITIES:
            mod = stats.mods.get(ability, 0)
            if mod_in_text is not None and mod != mod_in_text:
                continue
            if bonus == mod + stats.prof:
                choice = (ability, True)
                break
            if bonus == mod and choice is None:
                choice = (ability, False)
        if choice is None:
            return None
        build = {"mode": "attack", "kind": kind, "ability": choice[0], "proficient": choice[1], "reach": "5",
                 "range": "", "dice": "", "type": "Slashing", "extra_dice": "", "extra_type": "Fire", "effect": ""}
        reach = re.search(r"reach\s+(\d+)\s*ft", text, re.I)
        rng = re.search(r"range\s+(\d+(?:/\d+)?)\s*ft", text, re.I)
        if reach:
            build["reach"] = reach.group(1)
        if rng:
            build["range"] = rng.group(1)
        end = m.end()
        if hit:
            build["dice"], build["type"] = hit.group(2), hit.group(5).title()
            end = hit.end()
            plus = _PLUS.search(text, end)
            if plus and text[end:plus.start()].strip() == "":
                build["extra_dice"], build["extra_type"] = plus.group(2), plus.group(3).title()
                end = plus.end()
            build["effect"] = _tidy_effect(text[end:])
        else:
            tail = re.search(r"Hit:\s*(.*)$", text, re.S)
            build["effect"] = _tidy_effect(tail.group(1)) if tail else ""
        return _only_if_exact(build, text, stats)
    m = _SAVE.match(text)
    if m:
        dc = int(m.group(2))
        choice = None
        for ability in ("CON",) + tuple(a for a in ABILITIES if a != "CON"):
            if 8 + stats.prof + stats.mods.get(ability, 0) == dc:
                choice = ability
                break
        if choice is None:
            return None
        build = {"mode": "save", "save": _NAME_TO_ABILITY[m.group(1).lower()], "dc_ability": choice,
                 "area": (m.group(3) or "").strip(), "dice": "", "type": "Fire", "half": False, "effect": ""}
        body = text[m.end():]
        start = re.search(r"Failure:\s*", body)
        rest = body[start.end():] if start else ""
        both = re.search(r"Failure or Success:", rest)
        after = rest[both.start():].strip() if both else ""
        rest = rest[:both.start()] if both else rest
        success = re.search(r"Success:\s*", rest)
        success_text = rest[success.end():].strip() if success else ""
        failure_text = rest[:success.start()] if success else rest
        damage = _FAIL_DAMAGE.match(failure_text)
        if damage:
            build["dice"], build["type"] = damage.group(2), damage.group(3).title()
            failure_text = failure_text[damage.end():]
        build["effect"] = _tidy_effect(failure_text)
        if success_text.lower() == "half damage.":
            build["half"] = True
        elif success_text:
            build["success"] = success_text
        if after:
            build["after"] = after
        return _only_if_exact(build, text, stats)
    return None


def _only_if_exact(build: dict, text: str, stats: Stats) -> Optional[dict]:
    """The build, if it writes ``text`` back word for word (linking an entry must not rewrite it)."""
    again = built(build, stats).text
    return build if re.sub(r"\s+", " ", again).strip() == re.sub(r"\s+", " ", text).strip() else None
