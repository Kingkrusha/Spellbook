"""
Equipment data structures and manager for D&D 5e Spellbook Application.
Represents mundane gear: weapons, armor, tools, consumables, and general items.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional


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


@dataclass
class Equipment:
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


class EquipmentManager:
    """Manages the equipment database using SQLite."""

    _instance: Optional["EquipmentManager"] = None

    def __init__(self):
        self._db = None
        self._equipment_cache: Optional[List[Equipment]] = None

    @classmethod
    def get_instance(cls) -> "EquipmentManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def db(self):
        """Get database instance, initializing if needed."""
        if self._db is None:
            from database import SpellDatabase
            self._db = SpellDatabase()
            self._db.initialize()
        return self._db

    @property
    def items(self) -> List[Equipment]:
        """Get all equipment, using cache if available."""
        if self._equipment_cache is None:
            self._reload_cache()
        return self._equipment_cache or []

    def _reload_cache(self):
        """Reload equipment from database into cache."""
        self._equipment_cache = [
            self._dict_to_equipment(d) for d in self.db.get_all_equipment()
        ]

    def _invalidate_cache(self):
        """Invalidate the cache to force reload on next access."""
        self._equipment_cache = None

    def _dict_to_equipment(self, data: dict) -> Equipment:
        """Convert database dict to Equipment object."""
        return Equipment(
            name=data.get("name", ""),
            type=data.get("type", DEFAULT_EQUIPMENT_TYPE) or DEFAULT_EQUIPMENT_TYPE,
            cost=data.get("cost", ""),
            weight=data.get("weight", 0.0),
            source=data.get("source", ""),
            crafting_materials=data.get("crafting_materials", []),
            crafting_tool=data.get("crafting_tool", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            properties=_clean_properties(data.get("properties", [])),
            is_official=data.get("is_official", True),
            is_custom=data.get("is_custom", False),
        )

    def _equipment_to_dict(self, item: Equipment) -> dict:
        """Convert Equipment object to dict for database."""
        return {
            "name": item.name,
            "type": item.type,
            "cost": item.cost,
            "weight": item.weight,
            "source": item.source,
            "crafting_materials": item.crafting_materials,
            "crafting_tool": item.crafting_tool,
            "description": item.description,
            "tags": item.tags,
            "properties": item.properties,
            "is_official": item.is_official,
            "is_custom": item.is_custom,
        }

    def load(self) -> bool:
        """Reload equipment from database (for compatibility)."""
        self._invalidate_cache()
        return True

    def save(self) -> bool:
        """No-op for database backend (saves happen immediately)."""
        return True

    def get_item(self, name: str) -> Optional[Equipment]:
        """Get an equipment item by name."""
        data = self.db.get_equipment_by_name(name)
        return self._dict_to_equipment(data) if data else None

    def get_items_by_type(self, item_type: str) -> List[Equipment]:
        """Get all equipment of a specific type."""
        return [i for i in self.items if i.type == item_type]

    def add_item(self, item: Equipment) -> bool:
        """Add a new equipment item or update an existing one (by name)."""
        existing = self.db.get_equipment_by_name(item.name)
        item_dict = self._equipment_to_dict(item)

        if existing:
            self.db.update_equipment(existing["id"], item_dict)
        else:
            self.db.insert_equipment(item_dict)

        self._invalidate_cache()
        return True

    def update_item(self, name: str, updated_item: Equipment) -> bool:
        """Update an existing equipment item."""
        existing = self.db.get_equipment_by_name(name)
        if not existing:
            return False

        result = self.db.update_equipment(existing["id"], self._equipment_to_dict(updated_item))
        self._invalidate_cache()
        return result

    def delete_item(self, name: str) -> bool:
        """Delete an equipment item by name. Only custom items can be removed."""
        existing = self.db.get_equipment_by_name(name)
        if not existing:
            return False

        if not existing.get("is_custom"):
            return False  # Can't delete official items

        result = self.db.delete_equipment(existing["id"])
        self._invalidate_cache()
        return result

    def search_items(self, query: str, item_type: Optional[str] = None) -> List[Equipment]:
        """Search equipment by name, description, or tags."""
        query_lower = query.lower()
        results = []

        for item in self.items:
            if item_type is not None and item.type != item_type:
                continue

            if (query_lower in item.name.lower()
                    or query_lower in item.plain_description().lower()
                    or any(query_lower in t.lower() for t in item.tags)):
                results.append(item)

        return results

    def get_all_types(self) -> List[str]:
        """Get all unique equipment types including custom ones."""
        types = set(EQUIPMENT_TYPE_OPTIONS)
        for item in self.items:
            if item.type:
                types.add(item.type)
        return sorted(types)

    def get_all_tags(self) -> List[str]:
        """Get all unique tags in use, merged with the suggested set."""
        tags = set(SUGGESTED_EQUIPMENT_TAGS)
        for item in self.items:
            tags.update(item.tags)
        return sorted(tags)

    def get_all_properties(self) -> dict:
        """Map every property name in use to a representative description.

        Aggregated across all equipment so an editor can autofill a property's
        description when the user picks a name that already exists on another
        item. The first non-empty description seen for a name wins.
        """
        result: dict = {}
        for item in self.items:
            for prop in (item.properties or []):
                name = str(prop.get("name", "")).strip()
                if not name:
                    continue
                desc = str(prop.get("description", "")).strip()
                if name not in result or (not result[name] and desc):
                    result[name] = desc
        return result

    def get_all_sources(self) -> List[str]:
        """Get all unique sources from equipment."""
        sources = {i.source for i in self.items if i.source}
        return sorted(sources)

    def get_unofficial_sources(self) -> List[str]:
        """Get sources that have unofficial (non-official/custom) equipment."""
        sources = {i.source for i in self.items if (not i.is_official or i.is_custom) and i.source}
        return sorted(sources)

    def get_unofficial_items(self) -> List[Equipment]:
        """Get all equipment that is not official."""
        return [i for i in self.items if not i.is_official or i.is_custom]

    def export_to_json(self, file_path: str, items: Optional[List[Equipment]] = None) -> int:
        """Export equipment to a JSON file."""
        if items is None:
            items = self.get_unofficial_items()

        try:
            from atomic_io import atomic_write_json
            data = {"equipment": [i.to_dict() for i in items]}
            atomic_write_json(file_path, data)
            return len(items)
        except Exception as e:
            print(f"Error exporting equipment to JSON: {e}")
            return 0

    def import_from_json(self, file_path: str) -> int:
        """Import equipment from a JSON file; returns how many were added or updated.

        Goes through content_io, so an entry whose name belongs to official content
        is skipped instead of overwritten.
        """
        import content_io

        try:
            report = content_io.import_file(file_path, kinds=["equipment"], link_mentions=False)
        except Exception as e:
            print(f"Error importing equipment from JSON: {e}")
            return 0
        return report.added["equipment"] + report.updated["equipment"]



def get_equipment_manager() -> EquipmentManager:
    """Get the singleton EquipmentManager instance."""
    return EquipmentManager.get_instance()
