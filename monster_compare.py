"""
View and Compare for monsters: which of two monsters comes out ahead on each number in their stat blocks.

Everything here is worked out from the Monster fields and the text of its actions, without Tk:

    numbers = monster_numbers(monster)            # {"ac": 19, "hp": 256, "damage": 52.5, ...}
    result = compare_monsters(dragon, giant)      # {"ac": -1, "hp": 1, ...}: -1 = the first is better

Damage per round is the best of: the Multiattack (each attack it names, times how many, by the average damage
in that action's "Hit: 13 (1d10 + 8)" text) and any single action (a breath weapon's "Failure: 59 (17d6)").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from character_sheet import AbilityScore
from monster import Monster, cr_to_number


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    higher_is_better: bool = True
    extra: bool = False          # not a line of the stat block: shown in the comparison box instead


ABILITIES = list(AbilityScore)

METRICS: List[Metric] = [
    Metric("ac", "Armor Class"),
    Metric("hp", "Hit Points"),
    Metric("speed", "Speed"),
    Metric("initiative", "Initiative"),
    *[Metric(f"score_{a.name.lower()}", AbilityScore.short_name(a)) for a in ABILITIES],
    *[Metric(f"save_{a.name.lower()}", f"{AbilityScore.short_name(a)} save") for a in ABILITIES],
    Metric("skills", "Skills"),
    Metric("vulnerabilities", "Vulnerabilities", higher_is_better=False),
    Metric("resistances", "Resistances"),
    Metric("immunities", "Immunities"),
    Metric("senses", "Senses"),
    Metric("languages", "Languages"),
    Metric("cr", "Challenge Rating"),
    Metric("damage", "Damage per round", extra=True),
    Metric("attack", "Best attack bonus", extra=True),
    Metric("save_dc", "Best save DC", extra=True),
    Metric("legendary_resistance", "Legendary Resistance", extra=True),
    Metric("legendary_actions", "Legendary Actions", extra=True),
]
METRIC_BY_KEY = {m.key: m for m in METRICS}

_NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                 "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twice": 2, "thrice": 3}
_AVERAGE_DAMAGE = re.compile(r"(\d+)\s*\(\s*\d+\s*d\s*\d+[^)]*\)\s*[A-Za-z]*\s*damage", re.IGNORECASE)
_FLAT_DAMAGE = re.compile(r"\b(\d+)\s+[A-Za-z]+\s+damage", re.IGNORECASE)
_ATTACK_BONUS = re.compile(r"attack(?:\s+roll)?\s*:\s*\+(\d+)|\+(\d+)\s+to\s+hit", re.IGNORECASE)
_SAVE_DC = re.compile(r"\bDC\s*(\d+)", re.IGNORECASE)
_SENSE_RANGE = re.compile(r"(\d+)\s*(?:ft|feet)", re.IGNORECASE)
_LEGENDARY_RESISTANCE = re.compile(r"legendary resistance\s*\((\d+)\s*/\s*day", re.IGNORECASE)


def _plain(text: str) -> str:
    """Text with [[link]] markup reduced to what it shows."""
    def show(m):
        inner = m.group(1)
        inner = inner.split("|", 1)[-1] if "|" in inner else inner
        return inner.split(":", 1)[-1]
    return re.sub(r"\[\[([^\]]+)\]\]", show, text or "")


def action_damage(description: str) -> float:
    """Average damage of one use of an action: every "13 (1d10 + 8) Slashing damage" in it added up (the
    first one only after "Failure:" / "Success:" splits, so half damage on a success isn't counted)."""
    text = _plain(description)
    text = re.split(r"\bSuccess\s*:", text, maxsplit=1, flags=re.IGNORECASE)[0]
    numbers = [int(n) for n in _AVERAGE_DAMAGE.findall(text)]
    if not numbers:
        numbers = [int(n) for n in _FLAT_DAMAGE.findall(text)]
    return float(sum(numbers))


def _multiattack_damage(monster: Monster, per_action: Dict[str, float]) -> float:
    multi = next((a for a in monster.actions if a.name.lower().startswith("multiattack")), None)
    if multi is None:
        return 0.0
    text = _plain(multi.description).lower()
    total = 0.0
    names = sorted(per_action, key=len, reverse=True)
    for m in re.finditer(r"\b(a|an|one|two|three|four|five|six|seven|eight|nine|ten|twice|thrice|\d+)\s+"
                         r"([a-z' -]+?)\s+attacks?\b", text):
        count_word, what = m.group(1), m.group(2).strip()
        count = int(count_word) if count_word.isdigit() else _NUMBER_WORDS[count_word]
        name = next((n for n in names if n.lower() in what), None)
        if name is not None:
            total += count * per_action[name]
    if total == 0 and names:
        # "makes three attacks" without naming one: use the best attack
        m = re.search(r"\b(two|three|four|five|six|\d+)\s+(?:\w+\s+)?attacks\b", text)
        if m:
            count = int(m.group(1)) if m.group(1).isdigit() else _NUMBER_WORDS[m.group(1)]
            attacks = [per_action[n] for n in names if "attack" in n.lower() or per_action[n]]
            total = count * max(attacks) if attacks else 0.0
    return total


def damage_per_round(monster: Monster) -> float:
    per_action = {a.name: action_damage(a.description) for a in monster.actions
                  if not a.name.lower().startswith("multiattack")}
    best_single = max(per_action.values(), default=0.0)
    return max(best_single, _multiattack_damage(monster, per_action))


def _all_features(monster: Monster):
    return [*monster.traits, *monster.actions, *monster.bonus_actions, *monster.reactions,
            *monster.legendary_actions]


def best_attack_bonus(monster: Monster) -> int:
    best = 0
    for feature in _all_features(monster):
        for a, b in _ATTACK_BONUS.findall(feature.description or ""):
            best = max(best, int(a or b))
    return best


def best_save_dc(monster: Monster) -> int:
    best = 0
    for feature in _all_features(monster):
        for dc in _SAVE_DC.findall(feature.description or ""):
            best = max(best, int(dc))
    return best


def legendary_resistance(monster: Monster) -> int:
    for trait in monster.traits:
        m = _LEGENDARY_RESISTANCE.search(f"{trait.name} {trait.description}")
        if m:
            return int(m.group(1))
    return 0


def monster_numbers(monster: Monster) -> Dict[str, float]:
    """Every compared number for one monster (see METRICS)."""
    speeds = [feet for feet in (monster.speeds or {}).values() if feet]
    numbers: Dict[str, float] = {
        "ac": monster.ac,
        "hp": monster.hp,
        # the fastest speed counts first; more ways of moving (fly, swim...) break a tie
        "speed": max(speeds, default=0) + sum(speeds) / 10000.0,
        "initiative": monster.get_initiative() if monster.show_initiative else 0,
        "skills": sum(1 for v in _skill_values(monster) if v),
        "vulnerabilities": len(monster.damage_vulnerabilities),
        "resistances": len(monster.damage_resistances),
        "immunities": len(monster.damage_immunities) + len(monster.condition_immunities),
        "senses": sum(int(r) for s in monster.senses for r in _SENSE_RANGE.findall(s))
                  + monster.get_passive_perception() / 1000.0,
        "languages": len([l for l in monster.languages if l and l.lower() not in ("none", "—", "-")]),
        "cr": cr_to_number(monster.challenge_rating),
        "damage": damage_per_round(monster),
        "attack": best_attack_bonus(monster),
        "save_dc": best_save_dc(monster),
        "legendary_resistance": legendary_resistance(monster),
        "legendary_actions": monster.legendary_action_uses if monster.legendary_actions else 0,
    }
    for a in ABILITIES:
        numbers[f"score_{a.name.lower()}"] = monster.ability_scores.get(a)
        numbers[f"save_{a.name.lower()}"] = monster.get_save_bonus(a)
    return numbers


def _skill_values(monster: Monster):
    from character_sheet import Skill
    return [monster.skills.get(skill) for skill in Skill]


def compare_monsters(first: Monster, second: Monster) -> Dict[str, int]:
    """For each metric: -1 when ``first`` is better, 1 when ``second`` is, 0 when they're even."""
    a, b = monster_numbers(first), monster_numbers(second)
    result = {}
    for metric in METRICS:
        x, y = a[metric.key], b[metric.key]
        if not metric.higher_is_better:
            x, y = -x, -y
        result[metric.key] = -1 if x > y else 1 if x < y else 0
    return result


def format_number(key: str, value: float) -> str:
    """How a number reads in the comparison box."""
    if key == "damage":
        return f"{value:g}"
    if key == "attack":
        return f"+{int(value)}" if value else "—"
    if key in ("save_dc",):
        return f"DC {int(value)}" if value else "—"
    if key in ("legendary_resistance",):
        return f"{int(value)}/Day" if value else "—"
    if key == "legendary_actions":
        return str(int(value)) if value else "—"
    return f"{value:g}"
