"""
Shared plumbing for the managers of database-backed content collections.

Every collection manager (equipment, magic items, feats, lineages, backgrounds, monsters, rules)
used to carry its own copy of the same boilerplate: a lazily opened database handle, a
singleton accessor, a cache that is rebuilt after any change, and no-op ``load``/``save`` kept
for compatibility. :class:`DbBackedManager` is that boilerplate.

:class:`ItemManagerBase` goes one step further for equipment and magic items, which are the same
shape (a name, type, cost, weight, tags, properties ...) and so share their whole manager API.
"""

from contextlib import contextmanager
from typing import List, Optional


class LazyDatabase:
    """The app's database, opened (and migrated) the first time ``self.db`` is used.

    The class sets ``self._db = None`` in its ``__init__``; tests (and callers with a database of their own) can
    assign ``_db`` to use another one."""

    _db = None

    @property
    def db(self):
        """Get database instance, initializing if needed."""
        if self._db is None:
            from database import SpellDatabase
            self._db = SpellDatabase()
            self._db.initialize()
        return self._db

    @contextmanager
    def batch(self):
        """The writes made inside share one transaction (a bulk edit of many rows), see ``SpellDatabase.batch``."""
        with self.db.batch():
            yield


class DbBackedManager(LazyDatabase):
    """A singleton over one content collection, with the database opened on first use."""

    _instance = None

    def __init__(self):
        self._db = None
        self._cache: Optional[list] = None

    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- cache --------------------------------------------------------------

    def _load_all(self) -> list:
        """Every object in the collection, read from the database. Subclasses implement this."""
        raise NotImplementedError

    def _cached(self) -> list:
        """The cached objects, loading them on first use."""
        if self._cache is None:
            self._reload_cache()
        return self._cache or []

    def _reload_cache(self):
        """Reload the collection from the database into the cache."""
        self._cache = self._load_all()

    def _invalidate_cache(self):
        """Invalidate the cache to force reload on next access."""
        self._cache = None

    # ---- compatibility with the old file-backed managers ---------------------

    def load(self) -> bool:
        """Reload from the database (for compatibility)."""
        self._invalidate_cache()
        return True

    def save(self) -> bool:
        """No-op for database backend (saves happen immediately)."""
        return True


class ItemManagerBase(DbBackedManager):
    """The manager API shared by equipment and magic items.

    A subclass names its collection and wires the five database calls and the two converters::

        MODEL = MagicItem; LABEL_PLURAL = "magic items"; JSON_KEY = "magic_items"; TYPE_OPTIONS = [...]
        _db_get_all / _db_get_by_name / _db_insert / _db_update / _db_delete
    """

    MODEL = None                            # the item class (its from_dict / to_dict convert to and from a database dict)
    LABEL_PLURAL = "items"                  # in messages: "Error exporting {LABEL_PLURAL} ..."
    JSON_KEY = "items"                      # key in export files, and the content_io kind
    TYPE_OPTIONS: List[str] = []
    SUGGESTED_TAGS: List[str] = []

    # ---- subclass hooks -------------------------------------------------------

    def _db_get_all(self) -> List[dict]:
        raise NotImplementedError

    def _db_get_by_name(self, name: str) -> Optional[dict]:
        raise NotImplementedError

    def _db_insert(self, data: dict) -> int:
        raise NotImplementedError

    def _db_update(self, row_id: int, data: dict) -> bool:
        raise NotImplementedError

    def _db_delete(self, row_id: int) -> bool:
        raise NotImplementedError

    def _dict_to_item(self, data: dict):
        return self.MODEL.from_dict(data)

    def _item_to_dict(self, item) -> dict:
        return item.to_dict()

    # ---- reading --------------------------------------------------------------

    def _load_all(self) -> list:
        return [self._dict_to_item(d) for d in self._db_get_all()]

    @property
    def items(self) -> list:
        """Get all items, using cache if available."""
        return self._cached()

    def get_item(self, name: str):
        """Get an item by name."""
        data = self._db_get_by_name(name)
        return self._dict_to_item(data) if data else None

    def get_items_by_type(self, item_type: str) -> list:
        """Get all items of a specific type."""
        return [i for i in self.items if i.type == item_type]

    def search_items(self, query: str, item_type: Optional[str] = None) -> list:
        """Search items by name, description, or tags."""
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

    # ---- writing --------------------------------------------------------------

    def add_item(self, item) -> bool:
        """Add a new item or update an existing one (by name)."""
        existing = self._db_get_by_name(item.name)
        item_dict = self._item_to_dict(item)

        if existing:
            self._db_update(existing["id"], item_dict)
        else:
            self._db_insert(item_dict)

        self._invalidate_cache()
        return True

    def update_item(self, name: str, updated_item) -> bool:
        """Update an existing item."""
        existing = self._db_get_by_name(name)
        if not existing:
            return False

        result = self._db_update(existing["id"], self._item_to_dict(updated_item))
        self._invalidate_cache()
        return result

    def delete_item(self, name: str) -> bool:
        """Delete an item by name. Only custom items can be removed."""
        existing = self._db_get_by_name(name)
        if not existing:
            return False

        if not existing.get("is_custom"):
            return False  # Can't delete official items

        result = self._db_delete(existing["id"])
        self._invalidate_cache()
        return result

    # ---- what's in use ----------------------------------------------------------

    def get_all_types(self) -> List[str]:
        """Get all unique item types including custom ones."""
        types = set(self.TYPE_OPTIONS)
        for item in self.items:
            if item.type:
                types.add(item.type)
        return sorted(types)

    def get_all_tags(self) -> List[str]:
        """Get all unique tags in use, merged with the suggested set."""
        tags = set(self.SUGGESTED_TAGS)
        for item in self.items:
            tags.update(item.tags)
        return sorted(tags)

    def get_all_properties(self) -> dict:
        """Map every property name in use to a representative description.

        Aggregated across all items so an editor can autofill a property's
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
        """Get all unique sources."""
        sources = {i.source for i in self.items if i.source}
        return sorted(sources)

    def get_unofficial_sources(self) -> List[str]:
        """Get sources that have unofficial (non-official/custom) items."""
        sources = {i.source for i in self.items if (not i.is_official or i.is_custom) and i.source}
        return sorted(sources)

    def get_unofficial_items(self) -> list:
        """Get all items that are not official."""
        return [i for i in self.items if not i.is_official or i.is_custom]

    def _all_of(self, attr: str) -> List[str]:
        """Every distinct value in use of a list-valued field (e.g. ``crafting_materials``)."""
        values = set()
        for item in self.items:
            values.update(getattr(item, attr))
        return sorted(values)

    # ---- import / export ----------------------------------------------------------

    def export_to_json(self, file_path: str, items: Optional[list] = None) -> int:
        """Export items to a JSON file."""
        if items is None:
            items = self.get_unofficial_items()

        try:
            from atomic_io import atomic_write_json
            data = {self.JSON_KEY: [i.to_dict() for i in items]}
            atomic_write_json(file_path, data)
            return len(items)
        except Exception as e:
            print(f"Error exporting {self.LABEL_PLURAL} to JSON: {e}")
            return 0

    def import_from_json(self, file_path: str) -> int:
        """Import items from a JSON file; returns how many were added or updated.

        Goes through content_io, so an entry whose name belongs to official content
        is skipped instead of overwritten.
        """
        import content_io

        try:
            report = content_io.import_file(file_path, kinds=[self.JSON_KEY], link_mentions=False)
        except Exception as e:
            print(f"Error importing {self.LABEL_PLURAL} from JSON: {e}")
            return 0
        return report.added[self.JSON_KEY] + report.updated[self.JSON_KEY]
