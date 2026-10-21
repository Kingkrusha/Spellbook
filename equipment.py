"""
Equipment data structures and manager for D&D 5e Spellbook Application.
Represents mundane gear: weapons, armor, tools, consumables, and general items.
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from collection_manager import ItemManagerBase


# Suggested equipment types. The field is free text (so homebrew items aren't
# boxed in), but the editor offers these as a starting point and defaults to
# "Adventuring Gear" for anything that doesn't clearly fit elsewhere.
DEFAULT_EQUIPMENT_TYPE = "Adventuring Gear"

EQUIPMENT_TYPE_OPTIONS = [
    "Adventuring Gear",
    "Ammunition",
    "Armor",
    "Clothing",
    "Container",
    "Food and Drink",
    "Melee Weapon",
    "Mount and Vehicle",
    "Potion",
    "Ranged Weapon",
    "Shield",
    "Tool",
    "Trade Good",
]

# All 5e damage types (the 3 physical + 10 elemental/magical ones).
DAMAGE_TYPES = [
    "Bludgeoning", "Piercing", "Slashing",
    "Acid", "Cold", "Fire", "Force", "Lightning", "Necrotic",
    "Poison", "Psychic", "Radiant", "Thunder",
]

# Suggested tags covering the vocabulary called out for weapons/armor. Tags
# are otherwise free-form (same convention as Spell.tags) - the tag editor
# always lets the user type a brand-new tag too - this list only seeds the
# "pick an existing tag" UI, it isn't an enforced set.
SUGGESTED_EQUIPMENT_TAGS = [
    "Simple Weapon", "Martial Weapon",
    "Light Armor", "Medium Armor", "Heavy Armor",
    *DAMAGE_TYPES,
    "d4", "d6", "d8", "d10", "d12",
    "Finesse", "Versatile", "Two-Handed", "Reach", "Thrown", "Light", "Heavy",
    "Artisan Tool", "Other Tool", "Gaming Set", "Musical Instrument",
    "Strength", "Dexterity", "Intelligence", "Wisdom", "Charisma",
]


def _clean_properties(raw) -> List[dict]:
    """Normalise a raw properties value into a list of {name, description} dicts.

    Accepts the stored list-of-dicts form, tolerates missing keys, and drops
    entries with no name. Blank/empty input yields an empty list.
    """
    result: List[dict] = []
    if not raw:
        return result
    for entry in raw:
        if isinstance(entry, dict):
            name = str(entry.get("name", "")).strip()
            desc = str(entry.get("description", "")).strip()
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            name = str(entry[0]).strip()
            desc = str(entry[1]).strip()
        else:
            continue
        if name:
            result.append({"name": name, "description": desc})
    return result


# Copper-piece value of each coin, for converting a cost string to one
# comparable number (D&D's coin denominations, smallest to largest).
_COIN_TO_COPPER = {"cp": 1, "sp": 10, "ep": 50, "gp": 100, "pp": 1000}
_COST_PATTERN = re.compile(r"^([\d,]+)\s*(cp|sp|ep|gp|pp)$", re.IGNORECASE)


def parse_cost_to_copper(cost: str) -> Optional[int]:
    """Parse a cost string like ``"15 gp"`` or ``"2,000 gp"`` into copper pieces.

    Returns ``None`` for anything that isn't a plain "<number> <coin>" value
    (blank costs, and non-numeric ones like magic items' "Varies") so callers
    can treat those as "unknown price" rather than zero.
    """
    if not cost:
        return None
    match = _COST_PATTERN.match(cost.strip())
    if not match:
        return None
    amount = int(match.group(1).replace(",", ""))
    return amount * _COIN_TO_COPPER[match.group(2).lower()]


def copper_to_gp(copper: int) -> float:
    """Convert a copper-piece amount back to gold pieces (may be fractional)."""
    return copper / _COIN_TO_COPPER["gp"]


class ItemDisplayMixin:
    """Display helpers shared by Equipment and MagicItem (both have description, weight and tags)."""

    def plain_description(self) -> str:
        """Description with [[link]] markup replaced by its visible text (for searching)."""
        from object_link_sweep import strip_links
        return strip_links(self.description)

    def display_weight(self) -> str:
        """Format weight, dropping a pointless trailing '.0'."""
        w = self.weight
        text = f"{w:g}" if w == int(w) else f"{w}"
        return f"{text} lb{'s' if w != 1 else ''}"

    def display_tags(self) -> str:
        """Comma-separated, alphabetised tag list."""
        return ", ".join(sorted(self.tags, key=lambda t: t.lower()))


@dataclass
class Equipment(ItemDisplayMixin):
    """Represents a piece of mundane D&D equipment."""
    name: str
    type: str = DEFAULT_EQUIPMENT_TYPE
    cost: str = ""
    weight: float = 0.0
    source: str = ""
    crafting_materials: List[str] = field(default_factory=list)
    crafting_tool: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    # Named properties/keywords with their own descriptions, e.g. weapon
    # properties like Finesse or Versatile. Each entry is a dict with a
    # "name" and a "description"; the list may be empty.
    properties: List[dict] = field(default_factory=list)
    is_official: bool = True   # True for official content, False for homebrew
    is_custom: bool = False    # True if user-created

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "type": self.type,
            "cost": self.cost,
            "weight": self.weight,
            "source": self.source,
            "crafting_materials": self.crafting_materials,
            "crafting_tool": self.crafting_tool,
            "description": self.description,
            "tags": self.tags,
            "properties": self.properties,
            "is_official": self.is_official,
            "is_custom": self.is_custom,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Equipment":
        """Create Equipment from dictionary."""
        return cls(
            name=data.get("name", "Unknown"),
            type=data.get("type", DEFAULT_EQUIPMENT_TYPE) or DEFAULT_EQUIPMENT_TYPE,
            cost=data.get("cost", ""),
            weight=float(data.get("weight", 0.0) or 0.0),
            source=data.get("source", ""),
            crafting_materials=data.get("crafting_materials", []),
            crafting_tool=data.get("crafting_tool", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            properties=_clean_properties(data.get("properties", [])),
            is_official=data.get("is_official", True),
            is_custom=data.get("is_custom", False),
        )


class EquipmentManager(ItemManagerBase):
    """Manages the equipment database using SQLite."""

    _instance: Optional["EquipmentManager"] = None

    LABEL_PLURAL = "equipment"
    JSON_KEY = "equipment"
    MODEL = Equipment
    TYPE_OPTIONS = EQUIPMENT_TYPE_OPTIONS
    SUGGESTED_TAGS = SUGGESTED_EQUIPMENT_TAGS

    def _db_get_all(self): return self.db.get_all_equipment()
    def _db_get_by_name(self, name): return self.db.get_equipment_by_name(name)
    def _db_insert(self, data): return self.db.insert_equipment(data)
    def _db_update(self, row_id, data): return self.db.update_equipment(row_id, data)
    def _db_delete(self, row_id): return self.db.delete_equipment(row_id)

    def get_all_crafting_tools(self) -> List[str]:
        """Get all unique crafting tools in use."""
        tools = {i.crafting_tool for i in self.items if i.crafting_tool}
        return sorted(tools)

    def get_all_crafting_materials(self) -> List[str]:
        """Get all unique crafting materials in use."""
        return self._all_of("crafting_materials")


def get_equipment_manager() -> EquipmentManager:
    """Get the singleton EquipmentManager instance."""
    return EquipmentManager.get_instance()
