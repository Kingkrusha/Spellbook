"""Turning characters, monsters and ad-hoc creatures into tracker entries.

Each function returns an ``add_entry`` / ``add_me`` command dict holding *copies* of the numbers
(HP, AC, initiative bonus) taken at that moment. The tracker never writes back to the sheet or
monster they came from, so a goblin dropping to 0 HP or a player taking damage in a fight leaves the
collection and the character sheet exactly as they were.
"""

from __future__ import annotations

import random
from typing import Optional

import initiative_state as T


def from_sheet(sheet, owner: str = "", hidden: bool = False) -> dict:
    """An ``add_entry`` command for a :class:`character_sheet.CharacterSheet`."""
    hp = sheet.hit_points
    return {
        "type": "add_entry", "kind": T.KIND_PLAYER, "name": sheet.character_name or "Unnamed",
        "hp": hp.current, "hp_max": hp.maximum, "hp_temp": hp.temporary,
        "ac": sheet.armor_class, "init_bonus": sheet.get_initiative(),
        "owner": owner, "hidden": hidden,
        "source": {"type": "character", "name": sheet.character_name or ""},
    }


def as_me(command: dict) -> dict:
    """The ``add_me`` form a player sends for their own character (``from_sheet``'s output)."""
    keep = ("name", "hp", "hp_max", "hp_temp", "ac", "init_bonus", "source")
    return {"type": "add_me", **{k: command[k] for k in keep if k in command}}


def roll_hit_dice(hit_dice: str, rng: Optional[random.Random] = None) -> Optional[int]:
    """Roll a monster's hit dice (``"18d12 + 90"``). None if the text isn't a dice expression."""
    from lan import dice
    try:
        return max(1, dice.roll(hit_dice.replace(" ", ""), rng).total)
    except (dice.DiceError, AttributeError):
        return None


def from_monster(monster, roll_hp: bool = False, rng: Optional[random.Random] = None,
                 hidden: bool = False) -> dict:
    """An ``add_entry`` command for a :class:`monster.Monster`.

    HP is the monster's average unless ``roll_hp`` is set and it has parseable hit dice. Summoned
    creatures whose HP/AC scale with a spell level keep the best-effort number stored on them; the
    DM can correct it in the tracker."""
    hp = monster.hp
    if roll_hp and getattr(monster, "hit_dice", ""):
        rolled = roll_hit_dice(monster.hit_dice, rng)
        if rolled is not None:
            hp = rolled
    return {
        "type": "add_entry", "kind": T.KIND_MONSTER, "name": monster.name,
        "hp": hp, "hp_max": hp, "ac": monster.ac, "init_bonus": monster.get_initiative(),
        "hidden": hidden, "source": {"type": "monster", "name": monster.name},
    }


def custom(name: str, hp: int = 1, ac: int = 10, init_bonus: int = 0, hidden: bool = False) -> dict:
    """An ad-hoc creature that isn't a monster in the collection."""
    return {"type": "add_entry", "kind": T.KIND_CUSTOM, "name": name, "hp": hp, "hp_max": hp,
            "ac": ac, "init_bonus": init_bonus, "hidden": hidden}


def event(name: str, initiative: Optional[int] = None, hidden: bool = False) -> dict:
    """A named event on the initiative order (a lair action, a collapsing bridge...)."""
    return {"type": "add_entry", "kind": T.KIND_EVENT, "name": name, "initiative": initiative,
            "hidden": hidden}


def several(command: dict, count: int, group: bool = False, group_name: str = "") -> dict:
    """``command`` repeated ``count`` times (named "Goblin 1", "Goblin 2"...), optionally grouped so
    they take their turns together."""
    return {**command, "count": count, "group": group, "group_name": group_name}
