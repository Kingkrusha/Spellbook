"""
Named stat block entries for D&D Spellbook Application.

A creature's traits, actions, bonus actions, reactions, legendary actions and
lair actions are all lists of these (see monster.py).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class StatBlockFeature:
    """A trait, action, bonus action, reaction, legendary action or lair action.

    ``build`` is set for an attack or saving throw effect that the Monster editor works out from the creature's own
    stats (ability, proficiency, dice: see ``monster_rules``); ``description`` is then the text it wrote. Entries
    without it (all the official ones) are plain text."""
    name: str
    description: str
    build: Optional[dict] = None

    def to_dict(self) -> dict:
        data = {"name": self.name, "description": self.description}
        if self.build:
            data["build"] = dict(self.build)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "StatBlockFeature":
        build = data.get("build")
        return cls(name=data["name"], description=data["description"], build=dict(build) if build else None)
