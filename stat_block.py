"""
Named stat block entries for D&D Spellbook Application.

A creature's traits, actions, bonus actions, reactions, legendary actions and
lair actions are all lists of these (see monster.py).
"""

from dataclasses import dataclass


@dataclass
class StatBlockFeature:
    """A trait, action, bonus action, reaction, legendary action or lair action."""
    name: str
    description: str

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description}

    @classmethod
    def from_dict(cls, data: dict) -> "StatBlockFeature":
        return cls(name=data["name"], description=data["description"])
