"""
Magic item data structures and manager for D&D 5e Spellbook Application.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from equipment import EQUIPMENT_TYPE_OPTIONS, SUGGESTED_EQUIPMENT_TAGS, _clean_properties


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
class MagicItem:
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

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
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


class MagicItemManager:
    """Manages the magic item database using SQLite."""

    _instance: Optional["MagicItemManager"] = None

    def __init__(self):
        self._db = None
        self._items_cache: Optional[List[MagicItem]] = None

    @classmethod
    def get_instance(cls) -> "MagicItemManager":
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
    def items(self) -> List[MagicItem]:
        """Get all magic items, using cache if available."""
        if self._items_cache is None:
            self._reload_cache()
        return self._items_cache or []

    def _reload_cache(self):
        """Reload magic items from database into cache."""
        self._items_cache = [
            self._dict_to_item(d) for d in self.db.get_all_magic_items()
        ]

    def _invalidate_cache(self):
        """Invalidate the cache to force reload on next access."""
        self._items_cache = None

    def _dict_to_item(self, data: dict) -> MagicItem:
        """Convert database dict to MagicItem object."""
        return MagicItem(
            name=data.get("name", ""),
            type=data.get("type", DEFAULT_MAGIC_ITEM_TYPE) or DEFAULT_MAGIC_ITEM_TYPE,
            cost=data.get("cost", ""),
            weight=data.get("weight", 0.0),
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
        )

    def _item_to_dict(self, item: MagicItem) -> dict:
        """Convert MagicItem object to dict for database."""
        return {
            "name": item.name,
            "type": item.type,
            "cost": item.cost,
            "weight": item.weight,
            "source": item.source,
            "enchanting_materials": item.enchanting_materials,
            "description": item.description,
            "tags": item.tags,
            "properties": item.properties,
            "rarity": item.rarity.value,
            "requires_attunement": item.requires_attunement,
            "attunement_requirement": item.attunement_requirement,
            "attunement_optional": item.attunement_optional,
            "is_official": item.is_official,
            "is_custom": item.is_custom,
        }

    def load(self) -> bool:
        """Reload magic items from database (for compatibility)."""
        self._invalidate_cache()
        return True

    def save(self) -> bool:
        """No-op for database backend (saves happen immediately)."""
        return True

    def get_item(self, name: str) -> Optional[MagicItem]:
        """Get a magic item by name."""
        data = self.db.get_magic_item_by_name(name)
        return self._dict_to_item(data) if data else None

    def get_items_by_type(self, item_type: str) -> List[MagicItem]:
        """Get all magic items of a specific type."""
        return [i for i in self.items if i.type == item_type]

    def get_items_by_rarity(self, rarity: Rarity) -> List[MagicItem]:
        """Get all magic items of a specific rarity."""
        return [i for i in self.items if i.rarity == rarity]

    def add_item(self, item: MagicItem) -> bool:
        """Add a new magic item or update an existing one (by name)."""
        existing = self.db.get_magic_item_by_name(item.name)
        item_dict = self._item_to_dict(item)

        if existing:
            self.db.update_magic_item(existing["id"], item_dict)
        else:
            self.db.insert_magic_item(item_dict)

        self._invalidate_cache()
        return True

    def update_item(self, name: str, updated_item: MagicItem) -> bool:
        """Update an existing magic item."""
        existing = self.db.get_magic_item_by_name(name)
        if not existing:
            return False

        result = self.db.update_magic_item(existing["id"], self._item_to_dict(updated_item))
        self._invalidate_cache()
        return result

    def delete_item(self, name: str) -> bool:
        """Delete a magic item by name. Only custom items can be removed."""
        existing = self.db.get_magic_item_by_name(name)
        if not existing:
            return False

        if not existing.get("is_custom"):
            return False  # Can't delete official items

        result = self.db.delete_magic_item(existing["id"])
        self._invalidate_cache()
        return result

    def search_items(self, query: str, item_type: Optional[str] = None) -> List[MagicItem]:
        """Search magic items by name, description, or tags."""
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
        """Get all unique magic item types including custom ones."""
        types = set(MAGIC_ITEM_TYPE_OPTIONS)
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

        Aggregated across all magic items so an editor can autofill a
        property's description when the user picks an existing name. The first
        non-empty description seen for a name wins.
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
        """Get all unique sources from magic items."""
        sources = {i.source for i in self.items if i.source}
        return sorted(sources)

    def get_all_enchanting_materials(self) -> List[str]:
        """Get all unique enchanting materials in use."""
        materials = set()
        for item in self.items:
            materials.update(item.enchanting_materials)
        return sorted(materials)

    def get_unofficial_sources(self) -> List[str]:
        """Get sources that have unofficial (non-official/custom) magic items."""
        sources = {i.source for i in self.items if (not i.is_official or i.is_custom) and i.source}
        return sorted(sources)

    def get_unofficial_items(self) -> List[MagicItem]:
        """Get all magic items that are not official."""
        return [i for i in self.items if not i.is_official or i.is_custom]

    def export_to_json(self, file_path: str, items: Optional[List[MagicItem]] = None) -> int:
        """Export magic items to a JSON file."""
        if items is None:
            items = self.get_unofficial_items()

        try:
            from atomic_io import atomic_write_json
            data = {"magic_items": [i.to_dict() for i in items]}
            atomic_write_json(file_path, data)
            return len(items)
        except Exception as e:
            print(f"Error exporting magic items to JSON: {e}")
            return 0

    def import_from_json(self, file_path: str) -> int:
        """Import magic items from a JSON file; returns how many were added or updated.

        Goes through content_io, so an entry whose name belongs to official content
        is skipped instead of overwritten.
        """
        import content_io

        try:
            report = content_io.import_file(file_path, kinds=["magic_items"], link_mentions=False)
        except Exception as e:
            print(f"Error importing magic items from JSON: {e}")
            return 0
        return report.added["magic_items"] + report.updated["magic_items"]



def get_magic_item_manager() -> MagicItemManager:
    """Get the singleton MagicItemManager instance."""
    return MagicItemManager.get_instance()
