"""
Stat Block data model for D&D Spellbook Application.
Handles creature stat blocks that can be linked to summoning spells.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import json


@dataclass
class Ability:
    """Represents a single ability score with its modifier and save."""
    score: int
    modifier: int
    save: int
    
    @classmethod
    def from_score(cls, score: int, proficiency_bonus: int = 0) -> "Ability":
        """Create an Ability from just the score."""
        modifier = (score - 10) // 2
        save = modifier + proficiency_bonus
        return cls(score=score, modifier=modifier, save=save)
    
    def display(self) -> str:
        """Format as 'score (mod/save)' e.g., '14 (+2/+2)'."""
        mod_sign = "+" if self.modifier >= 0 else ""
        save_sign = "+" if self.save >= 0 else ""
        return f"{self.score} ({mod_sign}{self.modifier}/{save_sign}{self.save})"
    
    def to_dict(self) -> dict:
        return {"score": self.score, "modifier": self.modifier, "save": self.save}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Ability":
        return cls(score=data["score"], modifier=data["modifier"], save=data["save"])


@dataclass
class AbilityScores:
    """Container for all six ability scores."""
    strength: Ability
    dexterity: Ability
    constitution: Ability
    intelligence: Ability
    wisdom: Ability
    charisma: Ability
    
    @classmethod
    def from_scores(cls, str_: int, dex: int, con: int, int_: int, wis: int, cha: int, 
                   proficiency_bonus: int = 0) -> "AbilityScores":
        """Create AbilityScores from raw scores."""
        return cls(
            strength=Ability.from_score(str_, proficiency_bonus),
            dexterity=Ability.from_score(dex, proficiency_bonus),
            constitution=Ability.from_score(con, proficiency_bonus),
            intelligence=Ability.from_score(int_, proficiency_bonus),
            wisdom=Ability.from_score(wis, proficiency_bonus),
            charisma=Ability.from_score(cha, proficiency_bonus)
        )
    
    def to_dict(self) -> dict:
        return {
            "strength": self.strength.to_dict(),
            "dexterity": self.dexterity.to_dict(),
            "constitution": self.constitution.to_dict(),
            "intelligence": self.intelligence.to_dict(),
            "wisdom": self.wisdom.to_dict(),
            "charisma": self.charisma.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AbilityScores":
        return cls(
            strength=Ability.from_dict(data["strength"]),
            dexterity=Ability.from_dict(data["dexterity"]),
            constitution=Ability.from_dict(data["constitution"]),
            intelligence=Ability.from_dict(data["intelligence"]),
            wisdom=Ability.from_dict(data["wisdom"]),
            charisma=Ability.from_dict(data["charisma"])
        )


@dataclass
class StatBlockFeature:
    """A trait, action, bonus action, reaction, or legendary action."""
    name: str
    description: str
    
    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description}
    
    @classmethod
    def from_dict(cls, data: dict) -> "StatBlockFeature":
        return cls(name=data["name"], description=data["description"])


@dataclass
class StatBlock:
    """
    Represents a D&D 5e creature stat block.
    
    Fields support dynamic values using placeholders:
    - {spell_level} - the level of the spell slot used
    - {spell_attack} - "your spell attack modifier"
    - {spell_dc} - "your spell save DC"
    - {pb} - "your proficiency bonus"
    """
    # Identity
    name: str
    size: str  # Tiny, Small, Medium, Large, Huge, Gargantuan
    creature_type: str  # e.g., "Beast", "Fiend", "Construct"
    creature_subtype: str = ""  # e.g., "Celestial, Fey, or Fiend (Your Choice)"
    alignment: str = "Neutral"
    
    # Core stats - these can contain formulas like "11 + the spell's level"
    armor_class: str = ""  # e.g., "13", "11 + the spell's level", "13 (natural armor)"
    hit_points: str = ""  # e.g., "30 + 10 for each spell level above 3"
    speed: str = ""  # e.g., "30 ft., Fly 60 ft."
    
    # Ability scores
    abilities: Optional[AbilityScores] = None
    
    # Defenses
    damage_resistances: str = ""
    damage_immunities: str = ""
    condition_immunities: str = ""
    
    # Senses and languages
    senses: str = ""  # e.g., "Darkvision 60 ft., Passive Perception 10"
    languages: str = ""  # e.g., "Telepathy 1 mile (works only with you)"
    
    # Challenge
    challenge_rating: str = ""  # e.g., "None (XP 0; PB equals your Proficiency Bonus)"
    
    # Features
    traits: List[StatBlockFeature] = field(default_factory=list)
    actions: List[StatBlockFeature] = field(default_factory=list)
    bonus_actions: List[StatBlockFeature] = field(default_factory=list)
    reactions: List[StatBlockFeature] = field(default_factory=list)
    legendary_actions: List[StatBlockFeature] = field(default_factory=list)
    
    # Database tracking
    id: Optional[int] = None  # Database ID
    spell_id: Optional[int] = None  # Foreign key to spells table
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON/database storage."""
        return {
            "id": self.id,
            "spell_id": self.spell_id,
            "name": self.name,
            "size": self.size,
            "creature_type": self.creature_type,
            "creature_subtype": self.creature_subtype,
            "alignment": self.alignment,
            "armor_class": self.armor_class,
            "hit_points": self.hit_points,
            "speed": self.speed,
            "abilities": self.abilities.to_dict() if self.abilities else None,
            "damage_resistances": self.damage_resistances,
            "damage_immunities": self.damage_immunities,
            "condition_immunities": self.condition_immunities,
            "senses": self.senses,
            "languages": self.languages,
            "challenge_rating": self.challenge_rating,
            "traits": [t.to_dict() for t in self.traits],
            "actions": [a.to_dict() for a in self.actions],
            "bonus_actions": [b.to_dict() for b in self.bonus_actions],
            "reactions": [r.to_dict() for r in self.reactions],
            "legendary_actions": [l.to_dict() for l in self.legendary_actions]
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: dict) -> "StatBlock":
        """Create from dictionary."""
        abilities = None
        if data.get("abilities"):
            abilities = AbilityScores.from_dict(data["abilities"])
        
        return cls(
            id=data.get("id"),
            spell_id=data.get("spell_id"),
            name=data.get("name", ""),
            size=data.get("size", "Medium"),
            creature_type=data.get("creature_type", ""),
            creature_subtype=data.get("creature_subtype", ""),
            alignment=data.get("alignment", "Neutral"),
            armor_class=data.get("armor_class", ""),
            hit_points=data.get("hit_points", ""),
            speed=data.get("speed", ""),
            abilities=abilities,
            damage_resistances=data.get("damage_resistances", ""),
            damage_immunities=data.get("damage_immunities", ""),
            condition_immunities=data.get("condition_immunities", ""),
            senses=data.get("senses", ""),
            languages=data.get("languages", ""),
            challenge_rating=data.get("challenge_rating", ""),
            traits=[StatBlockFeature.from_dict(t) for t in data.get("traits", [])],
            actions=[StatBlockFeature.from_dict(a) for a in data.get("actions", [])],
            bonus_actions=[StatBlockFeature.from_dict(b) for b in data.get("bonus_actions", [])],
            reactions=[StatBlockFeature.from_dict(r) for r in data.get("reactions", [])],
            legendary_actions=[StatBlockFeature.from_dict(l) for l in data.get("legendary_actions", [])]
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "StatBlock":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def get_type_line(self) -> str:
        """Get the creature type line, e.g., 'Medium Undead, Neutral'."""
        parts = [self.size, self.creature_type]
        if self.creature_subtype:
            parts.append(self.creature_subtype)
        type_str = " ".join(parts)
        if self.alignment:
            type_str += f", {self.alignment}"
        return type_str
    
    def has_content(self) -> bool:
        """Check if this stat block has any meaningful content."""
        return bool(self.name and (self.armor_class or self.hit_points or self.actions))
