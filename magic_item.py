"""
Magic item data structures and manager for D&D 5e Spellbook Application.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from collection_manager import ItemManagerBase
from equipment import EQUIPMENT_TYPE_OPTIONS, SUGGESTED_EQUIPMENT_TAGS, ItemDisplayMixin, _clean_properties


class Rarity(Enum):
    """Magic item rarity."""
    COMMON = "Common"
    UNCOMMON = "Uncommon"
    RARE = "Rare"
    VERY_RARE = "Very Rare"
    LEGENDARY = "Legendary"
    ARTIFACT = "Artifact"
    VARIES = "Varies"

    @classmethod
    def from_string(cls, value: str) -> "Rarity":
        """Convert a string to a Rarity, defaulting to Common if unrecognized."""
        if not value:
            return cls.COMMON
        value_upper = value.strip().upper().replace("-", " ")
        for member in cls:
            if member.name.replace("_", " ") == value_upper or member.value.upper() == value_upper:
                return member
        return cls.COMMON

    @classmethod
    def all_values(cls) -> List[str]:
        """Return all rarity display strings, in ascending order of rarity."""
        return [r.value for r in cls]


# Magic items are usually "Wondrous Item", but can be any mundane category too
# (a magic sword is still a Melee Weapon, for filtering/tag purposes).
DEFAULT_MAGIC_ITEM_TYPE = "Wondrous Item"

MAGIC_ITEM_TYPE_OPTIONS = [DEFAULT_MAGIC_ITEM_TYPE] + EQUIPMENT_TYPE_OPTIONS


@dataclass
class MagicItem(ItemDisplayMixin):
    """Represents a D&D 5e magic item."""
    name: str
    type: str = DEFAULT_MAGIC_ITEM_TYPE
    cost: str = ""
    weight: float = 0.0
    source: str = ""
    enchanting_materials: List[str] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    # Named properties/keywords with their own descriptions (same shape as
    # Equipment.properties): each entry is a {"name", "description"} dict and
    # the list may be empty.
    properties: List[dict] = field(default_factory=list)
    rarity: Rarity = Rarity.COMMON
    # Whether the item needs attunement at all. `attunement_requirement` is the
    # optional class/kind restriction ("by a Wizard", "by a Spellcaster") - it
    # is blank for a bare "Requires Attunement".
    requires_attunement: bool = False
    attunement_requirement: str = ""
    attunement_optional: bool = False  # only meaningful when requires_attunement
    is_official: bool = True   # True for official content, False for homebrew
    is_custom: bool = False    # True if user-created
    roll_effects: List[dict] = field(default_factory=list)  # homebrew: what it does to the Dice Analyzer's rolls

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "name": self.name,
            "type": self.type,
            "cost": self.cost,
            "weight": self.weight,
            "source": self.source,
            "enchanting_materials": self.enchanting_materials,
            "description": self.description,
            "tags": self.tags,
            "properties": self.properties,
            "rarity": self.rarity.value,
            "requires_attunement": self.requires_attunement,
            "attunement_requirement": self.attunement_requirement,
            "attunement_optional": self.attunement_optional,
            "is_official": self.is_official,
            "is_custom": self.is_custom,
        }
        if self.roll_effects:
            data["roll_effects"] = self.roll_effects
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "MagicItem":
        """Create MagicItem from dictionary."""
        return cls(
            name=data.get("name", "Unknown"),
            type=data.get("type", DEFAULT_MAGIC_ITEM_TYPE) or DEFAULT_MAGIC_ITEM_TYPE,
            cost=data.get("cost", ""),
            weight=float(data.get("weight", 0.0) or 0.0),
            source=data.get("source", ""),
            enchanting_materials=data.get("enchanting_materials", []),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            properties=_clean_properties(data.get("properties", [])),
            rarity=Rarity.from_string(data.get("rarity", "Common")),
            requires_attunement=bool(data.get("requires_attunement",
                                              bool(data.get("attunement_requirement", "")))),
            attunement_requirement=data.get("attunement_requirement", ""),
            attunement_optional=data.get("attunement_optional", False),
            is_official=data.get("is_official", True),
            is_custom=data.get("is_custom", False),
            roll_effects=data.get("roll_effects", []) or [],
        )

    def display_attunement(self) -> str:
        """Human-readable attunement line, or '' if none is required."""
        if not self.requires_attunement:
            return ""
        text = "Requires Attunement"
        if self.attunement_requirement:
            text += f" {self.attunement_requirement}"
        if self.attunement_optional:
            text += " (optional)"
        return text


class MagicItemManager(ItemManagerBase):
    """Manages the magic item database using SQLite."""

    _instance: Optional["MagicItemManager"] = None

    LABEL_PLURAL = "magic items"
    JSON_KEY = "magic_items"
    MODEL = MagicItem
    TYPE_OPTIONS = MAGIC_ITEM_TYPE_OPTIONS
    SUGGESTED_TAGS = SUGGESTED_EQUIPMENT_TAGS

    def _db_get_all(self): return self.db.get_all_magic_items()
    def _db_get_by_name(self, name): return self.db.get_magic_item_by_name(name)
    def _db_insert(self, data): return self.db.insert_magic_item(data)
    def _db_update(self, row_id, data): return self.db.update_magic_item(row_id, data)
    def _db_delete(self, row_id): return self.db.delete_magic_item(row_id)

    def get_items_by_rarity(self, rarity: Rarity) -> List[MagicItem]:
        """Get all magic items of a specific rarity."""
        return [i for i in self.items if i.rarity == rarity]

    def get_all_enchanting_materials(self) -> List[str]:
        """Get all unique enchanting materials in use."""
        return self._all_of("enchanting_materials")


def get_magic_item_manager() -> MagicItemManager:
    """Get the singleton MagicItemManager instance."""
    return MagicItemManager.get_instance()
