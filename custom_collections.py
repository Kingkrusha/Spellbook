"""
Collections you shape yourself: extra fields on the built-in collections, and brand-new collections.

Two things can be changed, and neither touches what ships with the app:

* **Added fields on a built-in collection** (Spells, Feats, ... Rules). A field is a label and a kind (short
  text, long text, number, yes/no, a choice from a list, a list of words). The collection's own properties
  (a spell's level, a monster's AC ...) are its *default properties*: they are listed but cannot be removed
  or renamed. The value an entry has for an added field lives in ``custom_field_values`` keyed by the
  collection and the entry's name, so it works on official content too and survives the official tables
  being reseeded. Triggers on the content tables follow a rename (see :func:`ensure_triggers`).
* **New collections** ("Deities", "Factions" ...). Each has a name, an icon, a short description and its
  fields. Every new collection's entries have the same default properties - Name, Description, Source and
  Tags - which cannot be removed; everything else is one of its fields. The entries live in
  ``custom_entries`` (one table for every new collection, the values as JSON).

Nothing here imports tkinter: the pages are ``ui/custom_collection_view.py`` and ``ui/collection_type_editor.py``.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from collection_manager import LazyDatabase

CUSTOM_PREFIX = "custom:"          # a new collection's page key is "custom:<key>"

# kind -> what the field editor calls it
FIELD_KINDS: "OrderedDict[str, str]" = OrderedDict([
    ("text", "Short text"),
    ("long_text", "Long text"),
    ("number", "Number"),
    ("yes_no", "Yes / No"),
    ("choice", "Choice from a list"),
    ("list", "List of words"),
])

# The kinds whose values can be filtered on a collection page.
FILTERABLE_KINDS = ("choice", "yes_no", "list")

# Every new collection's entries have these; they can't be removed.
CUSTOM_DEFAULTS = ("Name", "Description", "Source", "Tags")

# key -> (shown name, icon, table, the default properties its entries have)
BUILTIN_TYPES: "OrderedDict[str, Tuple[str, str, str, Tuple[str, ...]]]" = OrderedDict([
    ("spells", ("Spells", "📜", "spells",
                ("Name", "Level", "School", "Casting Time", "Range", "Components", "Duration", "Concentration",
                 "Ritual", "Classes", "Description", "Source", "Tags"))),
    ("feats", ("Feats", "⚔️", "feats",
               ("Name", "Type", "Prerequisite", "Spellcasting", "Description", "Source", "Roll effects"))),
    ("lineages", ("Lineages", "🧬", "lineages",
                  ("Name", "Creature Type", "Size", "Speed", "Traits", "Description", "Source"))),
    ("magic_items", ("Magic Items", "✨", "magic_items",
                     ("Name", "Type", "Rarity", "Attunement", "Cost", "Weight", "Properties", "Tags",
                      "Description", "Source", "Roll effects"))),
    ("classes", ("Classes", "🎭", "classes",
                 ("Name", "Hit Die", "Primary Ability", "Saving Throws", "Proficiencies", "Features",
                  "Subclasses", "Spellcasting", "Source"))),
    ("backgrounds", ("Backgrounds", "📖", "backgrounds",
                     ("Name", "Ability Scores", "Feat", "Skill Proficiencies", "Tool Proficiencies", "Equipment",
                      "Features", "Description", "Source"))),
    ("equipment", ("Equipment", "🛡️", "equipment",
                   ("Name", "Type", "Cost", "Weight", "Properties", "Tags", "Crafting", "Description", "Source"))),
    ("monsters", ("Monsters", "👹", "monsters",
                  ("Name", "Size", "Type", "Alignment", "Armor Class", "Hit Points", "Speed", "Ability Scores",
                   "Challenge", "Traits", "Actions", "Description", "Source"))),
    ("rules", ("Rules", "📚", "rules", ("Name", "Category", "Description", "Tags", "Source"))),
])

# the entry classes the PDF export and the pages hand over -> their collection
BUILTIN_CLASS_KEYS = {
    "Spell": "spells", "Feat": "feats", "Lineage": "lineages", "MagicItem": "magic_items",
    "CharacterClassDefinition": "classes", "Background": "backgrounds", "Equipment": "equipment",
    "Monster": "monsters", "RulePage": "rules",
}

MAX_NAME = 80
MAX_FIELDS = 40
MAX_CHOICES = 60
DEFAULT_ICON = "🗂️"


class CollectionError(ValueError):
    """A change that can't be made (the message is meant for the person reading it)."""


# --------------------------------------------------------------------------- #
# Definitions
# --------------------------------------------------------------------------- #

def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s[:40] or "item"


@dataclass
class FieldDef:
    """One added field. ``id`` never changes, so renaming the label keeps every value."""
    id: str
    label: str
    kind: str = "text"
    choices: List[str] = field(default_factory=list)      # "choice" only
    filter: bool = True                                    # offered as a filter on the page (filterable kinds)

    def to_dict(self) -> dict:
        d = {"id": self.id, "label": self.label, "kind": self.kind, "filter": bool(self.filter)}
        if self.kind == "choice":
            d["choices"] = list(self.choices)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Optional["FieldDef"]:
        if not isinstance(d, dict):
            return None
        label = str(d.get("label") or "").strip()[:MAX_NAME]
        fid = str(d.get("id") or "").strip()[:60] or ("f_" + slug(label))
        if not label:
            return None
        kind = d.get("kind") if d.get("kind") in FIELD_KINDS else "text"
        choices = [str(c).strip()[:MAX_NAME] for c in (d.get("choices") or []) if str(c).strip()]
        return cls(fid, label, kind, _unique(choices)[:MAX_CHOICES], bool(d.get("filter", True)))

    @property
    def filterable(self) -> bool:
        return self.kind in FILTERABLE_KINDS and self.filter

    # ---- values

    def clean(self, value: Any) -> Any:
        """``value`` in this field's shape; empty values come back as "" / [] / False / None."""
        if self.kind == "yes_no":
            if isinstance(value, str):
                return value.strip().lower() in ("yes", "true", "1", "y")
            return bool(value)
        if self.kind == "number":
            return parse_number(value)
        if self.kind == "list":
            if isinstance(value, str):
                value = value.split(",")
            if not isinstance(value, (list, tuple)):
                return []
            return _unique(str(v).strip() for v in value if str(v).strip())
        return "" if value is None else str(value).strip() if self.kind != "long_text" else str(value).rstrip()

    def is_empty(self, value: Any) -> bool:
        if self.kind == "yes_no":
            return value is None
        return value in (None, "", [])

    def display(self, value: Any) -> str:
        """How the value reads on a page or in a PDF."""
        if self.kind == "yes_no":
            return "Yes" if value else "No"
        if self.kind == "number":
            return format_number(value)
        if self.kind == "list":
            return ", ".join(value or [])
        return str(value or "")


def parse_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        raise CollectionError(f"'{value}' isn't a number.")
    return int(number) if number.is_integer() else number


def format_number(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _unique(items: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


@dataclass
class CollectionType:
    """A new collection, or the added fields of a built-in one (``builtin``)."""
    key: str
    name: str
    icon: str = DEFAULT_ICON
    description: str = ""
    builtin: bool = False
    fields: List[FieldDef] = field(default_factory=list)
    order: int = 0

    @property
    def page_key(self) -> str:
        """What the main window calls its page ("feats", or "custom:deities")."""
        return self.key if self.builtin else CUSTOM_PREFIX + self.key

    @property
    def default_properties(self) -> Tuple[str, ...]:
        return BUILTIN_TYPES[self.key][3] if self.builtin and self.key in BUILTIN_TYPES else CUSTOM_DEFAULTS

    @property
    def title(self) -> str:
        return f"{self.icon} {self.name}".strip()

    def field(self, field_id: str) -> Optional[FieldDef]:
        return next((f for f in self.fields if f.id == field_id), None)

    def to_dict(self) -> dict:
        d = {"key": self.key, "name": self.name, "fields": [f.to_dict() for f in self.fields]}
        if self.builtin:
            d["builtin"] = True
        else:
            d.update(icon=self.icon, description=self.description)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CollectionType":
        if not isinstance(d, dict):
            raise CollectionError("A collection must be a JSON object.")
        builtin = bool(d.get("builtin"))
        key = str(d.get("key") or "").strip()
        name = str(d.get("name") or "").strip()[:MAX_NAME]
        if builtin:
            if key not in BUILTIN_TYPES:
                key = next((k for k, v in BUILTIN_TYPES.items() if v[0].lower() == name.lower()), "")
            if key not in BUILTIN_TYPES:
                raise CollectionError(f"There is no built-in collection called '{name or key}'.")
            name = BUILTIN_TYPES[key][0]
        elif not name:
            raise CollectionError("A collection needs a name.")
        else:
            key = slug(key or name)
        fields = [f for f in (FieldDef.from_dict(x) for x in (d.get("fields") or [])) if f]
        return cls(key=key, name=name, icon=str(d.get("icon") or DEFAULT_ICON).strip()[:8] or DEFAULT_ICON,
                   description=str(d.get("description") or "").strip()[:300], builtin=builtin,
                   fields=fields[:MAX_FIELDS])

    def clean_values(self, values: Optional[dict]) -> dict:
        """The values of this collection's fields (unknown fields dropped, each in its field's shape)."""
        out = {}
        for f in self.fields:
            if values and f.id in values:
                value = f.clean(values[f.id])
                if not f.is_empty(value) or f.kind == "yes_no":
                    out[f.id] = value
        return out


def validate_fields(ctype: CollectionType):
    """Raise CollectionError when the fields can't be saved as they are."""
    if len(ctype.fields) > MAX_FIELDS:
        raise CollectionError(f"A collection can have at most {MAX_FIELDS} added fields.")
    reserved = {p.lower() for p in ctype.default_properties}
    seen_labels, seen_ids = set(), set()
    for f in ctype.fields:
        label = f.label.strip()
        if not label:
            raise CollectionError("Every field needs a name.")
        if label.lower() in reserved:
            raise CollectionError(f"'{label}' is already one of the collection's own properties. "
                                  f"Pick another name.")
        if label.lower() in seen_labels:
            raise CollectionError(f"There are two fields called '{label}'.")
        if f.kind not in FIELD_KINDS:
            raise CollectionError(f"'{label}' has an unknown kind of value.")
        if f.kind == "choice" and not f.choices:
            raise CollectionError(f"'{label}' is a choice from a list: add at least one choice.")
        if f.id in seen_ids:
            raise CollectionError(f"Two fields share the id '{f.id}'.")
        seen_labels.add(label.lower())
        seen_ids.add(f.id)


def new_field_id(label: str, taken: Iterable[str]) -> str:
    taken = set(taken)
    base = "f_" + slug(label)
    fid, n = base, 2
    while fid in taken:
        fid, n = f"{base}_{n}", n + 1
    return fid


# --------------------------------------------------------------------------- #
# Entries of a new collection
# --------------------------------------------------------------------------- #

@dataclass
class CustomEntry:
    collection: str                       # the collection's key
    name: str
    description: str = ""
    source: str = ""
    tags: List[str] = field(default_factory=list)
    values: Dict[str, Any] = field(default_factory=dict)
    id: int = 0
    # what the shared page code (filters, bulk edits, imports) asks of every entry
    is_custom: bool = True
    is_official: bool = False

    def to_dict(self) -> dict:
        return {"collection": self.collection, "name": self.name, "description": self.description,
                "source": self.source, "tags": list(self.tags), "values": dict(self.values)}

    @classmethod
    def from_dict(cls, d: dict) -> "CustomEntry":
        tags = d.get("tags") or []
        if isinstance(tags, str):
            tags = tags.split(",")
        return cls(collection=str(d.get("collection") or ""), name=str(d.get("name") or "").strip()[:200],
                   description=str(d.get("description") or ""), source=str(d.get("source") or "").strip(),
                   tags=_unique(str(t).strip() for t in tags if str(t).strip()),
                   values=dict(d.get("values") or {}) if isinstance(d.get("values"), dict) else {})

    def plain_description(self) -> str:
        try:
            from object_link_sweep import strip_links
            return strip_links(self.description or "")
        except Exception:
            return self.description or ""


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #

TABLES_SQL = (
    """CREATE TABLE IF NOT EXISTS collection_types (
        key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        icon TEXT DEFAULT '',
        description TEXT DEFAULT '',
        builtin INTEGER NOT NULL DEFAULT 0,
        fields_json TEXT DEFAULT '[]',
        sort_order INTEGER NOT NULL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS custom_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        collection TEXT NOT NULL,
        name TEXT NOT NULL COLLATE NOCASE,
        description TEXT DEFAULT '',
        source TEXT DEFAULT '',
        tags_json TEXT DEFAULT '[]',
        values_json TEXT DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(collection, name)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_custom_entries_collection ON custom_entries(collection)",
    """CREATE TABLE IF NOT EXISTS custom_field_values (
        collection TEXT NOT NULL,
        name TEXT NOT NULL COLLATE NOCASE,
        values_json TEXT DEFAULT '{}',
        PRIMARY KEY (collection, name)
    )""",
)


def create_tables(cursor):
    """Create the tables (run on every start, like the other content tables)."""
    for sql in TABLES_SQL:
        cursor.execute(sql)


def _trigger_name(table: str) -> str:
    return f"custom_values_{table}_rename"


def ensure_triggers(cursor):
    """Keep an entry's added-field values with it when it is renamed.

    A value row already sitting under the new name (left by an entry that was deleted) is dropped first, so the
    rename can never clash with it. There is deliberately no delete trigger: the official tables are sometimes
    cleared and reseeded, and the values should still be there afterwards."""
    tables = {r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    for key, (_name, _icon, table, _props) in BUILTIN_TYPES.items():
        if table not in tables:
            continue
        cursor.execute(f"""
            CREATE TRIGGER IF NOT EXISTS {_trigger_name(table)} AFTER UPDATE OF name ON {table}
            WHEN OLD.name IS NOT NEW.name
            BEGIN
                DELETE FROM custom_field_values WHERE collection = '{key}' AND name = NEW.name
                    AND NOT (name = OLD.name);
                UPDATE custom_field_values SET name = NEW.name WHERE collection = '{key}' AND name = OLD.name;
            END""")


# --------------------------------------------------------------------------- #
# The manager
# --------------------------------------------------------------------------- #

class CollectionTypeManager(LazyDatabase):
    """Every collection definition, the entries of the new collections and the added-field values."""

    _instance = None

    def __init__(self):
        self._db = None
        self._types: Optional["OrderedDict[str, CollectionType]"] = None     # custom and builtin rows
        self._entries: Dict[str, List[CustomEntry]] = {}
        self._listeners: List[Callable[[], None]] = []
        self._value_listeners: List[Callable[[str, str], None]] = []
        self._muted = 0

    @classmethod
    def get_instance(cls) -> "CollectionTypeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ---- listeners (the Collections page redraws its cards, open pages their fields)

    def add_listener(self, fn: Callable[[], None]):
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[], None]):
        if fn in self._listeners:
            self._listeners.remove(fn)

    @contextmanager
    def muted(self):
        """No listener is told about the changes made inside (an import tells them once, at the end)."""
        self._muted += 1
        try:
            yield
        finally:
            self._muted -= 1

    def _notify(self):
        if self._muted:
            return
        for fn in list(self._listeners):
            try:
                fn()
            except Exception as e:
                print(f"A collection listener failed: {e}")

    def reload(self):
        """Forget what is cached (after an import or a backup restore) and tell the pages."""
        self._types = None
        self._entries = {}
        self._notify()

    # ---- definitions

    def _load_types(self) -> "OrderedDict[str, CollectionType]":
        if self._types is None:
            types: "OrderedDict[str, CollectionType]" = OrderedDict()
            with self.db.get_connection() as conn:
                rows = conn.execute("SELECT * FROM collection_types ORDER BY sort_order, name COLLATE NOCASE")
                for row in rows.fetchall():
                    try:
                        fields = json.loads(row["fields_json"] or "[]")
                    except ValueError:
                        fields = []
                    ctype = CollectionType.from_dict({
                        "key": row["key"], "name": row["name"], "icon": row["icon"],
                        "description": row["description"], "builtin": bool(row["builtin"]), "fields": fields})
                    if not ctype.builtin:
                        ctype.key = row["key"][len(CUSTOM_PREFIX):] if row["key"].startswith(CUSTOM_PREFIX) \
                            else row["key"]
                    ctype.order = row["sort_order"] or 0
                    types[self._type_id(ctype.key, ctype.builtin)] = ctype
            self._types = types
        return self._types

    @staticmethod
    def _type_id(key: str, builtin: bool) -> str:
        return key if builtin else CUSTOM_PREFIX + key

    def custom_types(self) -> List[CollectionType]:
        """The new collections, in the order they were made."""
        return [t for t in self._load_types().values() if not t.builtin]

    def builtin_type(self, key: str) -> CollectionType:
        """A built-in collection with its added fields (none yet: an empty definition)."""
        found = self._load_types().get(key)
        if found is not None:
            return found
        name, icon, _table, _props = BUILTIN_TYPES[key]
        return CollectionType(key=key, name=name, icon=icon, builtin=True)

    def builtin_fields(self, key: str) -> List[FieldDef]:
        found = self._load_types().get(key)
        return list(found.fields) if found is not None else []

    def all_types(self) -> List[CollectionType]:
        """Every built-in collection (with its added fields) and then the new ones."""
        return [self.builtin_type(k) for k in BUILTIN_TYPES] + self.custom_types()

    def get_type(self, page_key: str) -> Optional[CollectionType]:
        """The collection a page shows: "feats", or "custom:deities"."""
        if page_key in BUILTIN_TYPES:
            return self.builtin_type(page_key)
        if page_key.startswith(CUSTOM_PREFIX):
            return self._load_types().get(page_key)
        return None

    def custom_type(self, key: str) -> Optional[CollectionType]:
        return self._load_types().get(CUSTOM_PREFIX + key)

    def type_by_name(self, name: str) -> Optional[CollectionType]:
        low = (name or "").strip().lower()
        return next((t for t in self.custom_types() if t.name.lower() == low), None)

    def _free_key(self, name: str) -> str:
        base = slug(name)
        key, n = base, 2
        taken = {t.key for t in self.custom_types()}
        while key in taken:
            key, n = f"{base}_{n}", n + 1
        return key

    def save_type(self, ctype: CollectionType) -> CollectionType:
        """Store a collection (new when its key is empty or unknown). Returns it as stored."""
        validate_fields(ctype)
        if ctype.builtin:
            if ctype.key not in BUILTIN_TYPES:
                raise CollectionError("Unknown built-in collection.")
            ctype.name, ctype.icon = BUILTIN_TYPES[ctype.key][0], BUILTIN_TYPES[ctype.key][1]
        else:
            ctype.name = (ctype.name or "").strip()[:MAX_NAME]
            if not ctype.name:
                raise CollectionError("The collection needs a name.")
            builtin_names = {v[0].lower() for v in BUILTIN_TYPES.values()} | {"random tables", "subclasses"}
            if ctype.name.lower() in builtin_names:
                raise CollectionError(f"'{ctype.name}' is already one of the app's collections.")
            other = self.type_by_name(ctype.name)
            if other is not None and other.key != ctype.key:
                raise CollectionError(f"There is already a collection called '{other.name}'.")
            if not ctype.key or self.custom_type(ctype.key) is None:
                ctype.key = self._free_key(ctype.name)
                ctype.order = max([t.order for t in self.custom_types()] + [0]) + 1
            ctype.icon = (ctype.icon or "").strip()[:8] or DEFAULT_ICON
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO collection_types (key, name, icon, description, builtin, fields_json, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET name = excluded.name, "
                "icon = excluded.icon, description = excluded.description, builtin = excluded.builtin, "
                "fields_json = excluded.fields_json, sort_order = excluded.sort_order, "
                "updated_at = CURRENT_TIMESTAMP",
                (self._row_key(ctype), ctype.name, ctype.icon, ctype.description, int(ctype.builtin),
                 json.dumps([f.to_dict() for f in ctype.fields]), ctype.order))
        self._types = None
        self._entries.pop(ctype.key, None)
        self._notify()
        return self.get_type(ctype.page_key)

    @staticmethod
    def _row_key(ctype: CollectionType) -> str:
        """Built-in rows are keyed by the collection ("feats"); new collections by "custom:<key>" in the table
        too, so a new collection can never take a built-in's row."""
        return ctype.key if ctype.builtin else CUSTOM_PREFIX + ctype.key

    def delete_type(self, key: str) -> int:
        """Delete a new collection and all its entries. Returns how many entries went with it."""
        with self.db.get_connection() as conn:
            n = conn.execute("DELETE FROM custom_entries WHERE collection = ?", (key,)).rowcount
            conn.execute("DELETE FROM collection_types WHERE key = ?", (CUSTOM_PREFIX + key,))
        self._types = None
        self._entries.pop(key, None)
        self._notify()
        return n

    def entry_count(self, key: str) -> int:
        with self.db.get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM custom_entries WHERE collection = ?", (key,)).fetchone()[0]

    # ---- entries of new collections

    @staticmethod
    def _entry_from_row(row) -> CustomEntry:
        def load(col, default):
            try:
                value = json.loads(row[col] or "")
                return value if isinstance(value, type(default)) else default
            except (ValueError, TypeError):
                return default
        return CustomEntry(collection=row["collection"], name=row["name"], description=row["description"] or "",
                           source=row["source"] or "", tags=load("tags_json", []), values=load("values_json", {}),
                           id=row["id"])

    def entries(self, key: str) -> List[CustomEntry]:
        if key not in self._entries:
            with self.db.get_connection() as conn:
                rows = conn.execute("SELECT * FROM custom_entries WHERE collection = ? ORDER BY name COLLATE NOCASE",
                                    (key,)).fetchall()
            self._entries[key] = [self._entry_from_row(r) for r in rows]
        return list(self._entries[key])

    def all_entries(self) -> List[CustomEntry]:
        out = []
        for t in self.custom_types():
            out.extend(self.entries(t.key))
        return out

    def get_entry(self, key: str, name: str) -> Optional[CustomEntry]:
        low = (name or "").strip().lower()
        return next((e for e in self.entries(key) if e.name.lower() == low), None)

    def get_entry_by_id(self, entry_id: int) -> Optional[CustomEntry]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM custom_entries WHERE id = ?", (entry_id,)).fetchone()
        return self._entry_from_row(row) if row else None

    def _clean_entry(self, entry: CustomEntry) -> CustomEntry:
        ctype = self.custom_type(entry.collection)
        if ctype is None:
            raise CollectionError(f"The collection '{entry.collection}' doesn't exist.")
        entry.name = (entry.name or "").strip()
        if not entry.name:
            raise CollectionError("An entry needs a name.")
        entry.values = ctype.clean_values(entry.values)
        entry.tags = _unique(t.strip() for t in entry.tags if t and t.strip())
        return entry

    def _write_entry(self, conn, entry: CustomEntry, row_id: Optional[int]):
        params = (entry.name, entry.description or "", entry.source or "", json.dumps(entry.tags),
                  json.dumps(entry.values))
        if row_id:
            conn.execute("UPDATE custom_entries SET name = ?, description = ?, source = ?, tags_json = ?, "
                         "values_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", params + (row_id,))
            return row_id
        return conn.execute("INSERT INTO custom_entries (name, description, source, tags_json, values_json, "
                            "collection) VALUES (?, ?, ?, ?, ?, ?)", params + (entry.collection,)).lastrowid

    def add_entry(self, entry: CustomEntry, replace: bool = False) -> bool:
        """Add an entry. False when the name is taken (``replace``: the existing one is overwritten instead)."""
        entry = self._clean_entry(entry)
        existing = self.get_entry(entry.collection, entry.name)
        if existing is not None and not replace:
            return False
        with self.db.get_connection() as conn:
            entry.id = self._write_entry(conn, entry, existing.id if existing else None)
        self._entries.pop(entry.collection, None)
        if existing is None:
            self._notify()              # the Collections page shows how many entries each collection has
        return True

    def update_entry(self, old_name: str, entry: CustomEntry) -> bool:
        """Store an edited entry (it may have been renamed). False when it's gone or the new name is taken."""
        entry = self._clean_entry(entry)
        existing = self.get_entry(entry.collection, old_name)
        if existing is None:
            return False
        clash = self.get_entry(entry.collection, entry.name)
        if clash is not None and clash.id != existing.id:
            return False
        with self.db.get_connection() as conn:
            self._write_entry(conn, entry, existing.id)
        entry.id = existing.id
        self._entries.pop(entry.collection, None)
        return True

    def delete_entry(self, key: str, name: str) -> bool:
        with self.db.get_connection() as conn:
            n = conn.execute("DELETE FROM custom_entries WHERE collection = ? AND name = ?", (key, name)).rowcount
        self._entries.pop(key, None)
        if n:
            self._notify()
        return n > 0

    def all_sources(self, key: str) -> List[str]:
        return sorted({e.source for e in self.entries(key) if e.source}, key=str.lower)

    def all_tags(self, key: str) -> List[str]:
        return sorted({t for e in self.entries(key) for t in e.tags}, key=str.lower)

    def field_options(self, key: str, fdef: FieldDef) -> List[str]:
        """The values a filter on ``fdef`` can offer (choices first, then anything else entries hold)."""
        if fdef.kind == "yes_no":
            return ["Yes", "No"]
        found = []
        for e in self.entries(key):
            value = e.values.get(fdef.id)
            found.extend(value if isinstance(value, list) else [value] if value else [])
        extra = sorted({str(v) for v in found} - set(fdef.choices), key=str.lower)
        return list(fdef.choices) + extra

    # ---- values of added fields on built-in entries

    def extra_values(self, collection: str, name: str) -> dict:
        if not name or not self.builtin_fields(collection):
            return {}
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT values_json FROM custom_field_values WHERE collection = ? AND name = ?",
                               (collection, name)).fetchone()
        if not row:
            return {}
        try:
            values = json.loads(row[0] or "{}")
        except ValueError:
            return {}
        return values if isinstance(values, dict) else {}

    def set_extra_values(self, collection: str, name: str, values: dict, merge: bool = False):
        """Store an entry's added-field values (``merge``: keep the ones not given)."""
        ctype = self.builtin_type(collection)
        current = self.extra_values(collection, name) if merge else {}
        # values of fields that were removed are kept: putting the field back brings them back
        old = self._raw_extra(collection, name)
        cleaned = ctype.clean_values({**current, **(values or {})})
        stored = {k: v for k, v in old.items() if ctype.field(k) is None}
        stored.update(cleaned)
        with self.db.get_connection() as conn:
            if stored:
                conn.execute("INSERT INTO custom_field_values (collection, name, values_json) VALUES (?, ?, ?) "
                             "ON CONFLICT(collection, name) DO UPDATE SET values_json = excluded.values_json",
                             (collection, name, json.dumps(stored)))
            else:
                conn.execute("DELETE FROM custom_field_values WHERE collection = ? AND name = ?", (collection, name))
        self._notify_values(collection, name)

    def _raw_extra(self, collection: str, name: str) -> dict:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT values_json FROM custom_field_values WHERE collection = ? AND name = ?",
                               (collection, name)).fetchone()
        try:
            values = json.loads(row[0]) if row else {}
        except ValueError:
            values = {}
        return values if isinstance(values, dict) else {}

    def all_extra_values(self) -> List[Tuple[str, str, dict]]:
        """(collection, entry name, values) for every built-in entry that has some."""
        with self.db.get_connection() as conn:
            rows = conn.execute("SELECT collection, name, values_json FROM custom_field_values "
                                "ORDER BY collection, name COLLATE NOCASE").fetchall()
        out = []
        for collection, name, raw in rows:
            try:
                values = json.loads(raw or "{}")
            except ValueError:
                continue
            if isinstance(values, dict) and values and collection in BUILTIN_TYPES:
                out.append((collection, name, values))
        return out

    # the detail panes that show an entry redraw when its values change elsewhere (another tab)
    def add_value_listener(self, fn: Callable[[str, str], None]):
        if fn not in self._value_listeners:
            self._value_listeners.append(fn)

    def remove_value_listener(self, fn: Callable[[str, str], None]):
        if fn in self._value_listeners:
            self._value_listeners.remove(fn)

    def _notify_values(self, collection: str, name: str):
        if self._muted:
            return
        for fn in list(self._value_listeners):
            try:
                fn(collection, name)
            except Exception as e:
                print(f"A field value listener failed: {e}")

    # ---- the printable / searchable form of an entry's added fields

    def extra_lines(self, collection: str, name: str) -> List[Tuple[str, str]]:
        """("Label", "value") for every added field a built-in entry has filled in."""
        fields = self.builtin_fields(collection)
        if not fields:
            return []
        values = self.extra_values(collection, name)
        return value_lines(fields, values)


def value_lines(fields: Iterable[FieldDef], values: dict) -> List[Tuple[str, str]]:
    out = []
    for f in fields:
        if f.id in values and not f.is_empty(values[f.id]):
            text = f.display(values[f.id])
            if text:
                out.append((f.label, text))
    return out


def get_collection_manager() -> CollectionTypeManager:
    return CollectionTypeManager.get_instance()


def page_title(page_key: str) -> str:
    """The name a tab shows for a collection page key ("custom:deities" -> "Deities")."""
    if page_key in BUILTIN_TYPES:
        return BUILTIN_TYPES[page_key][0]
    try:
        ctype = get_collection_manager().get_type(page_key)
    except Exception:
        ctype = None
    return ctype.name if ctype else "Collections"


# --------------------------------------------------------------------------- #
# Moving collections between installs (content_io: files, backups, LAN)
# --------------------------------------------------------------------------- #

@dataclass
class FieldValues:
    """The added-field values of one built-in entry, as content_io exports them."""
    collection: str
    name: str
    values: Dict[str, Any] = field(default_factory=dict)
    source: str = ""

    is_official = False          # never official: always the user's own
    is_custom = True

    def to_dict(self) -> dict:
        return {"collection": self.collection, "name": self.name, "values": dict(self.values)}


# a definition is never official either (content_io asks)
CollectionType.is_official = False
CollectionType.is_custom = True


def exportable_types() -> List[CollectionType]:
    """The new collections, and the built-in ones that have added fields."""
    mgr = get_collection_manager()
    return [t for t in mgr.all_types() if not t.builtin or t.fields]


def exportable_values() -> List[FieldValues]:
    return [FieldValues(c, n, v) for c, n, v in get_collection_manager().all_extra_values()]


def entry_label(collection_name: str, name: str) -> str:
    """How an entry of a new collection is named in import previews ("Deities › Zeus")."""
    return f"{collection_name} › {name}" if collection_name else name


class Importer:
    """Brings collection definitions, entries and field values into this install, in that order.

    Definitions are matched by name: a new collection with the name of one already here is merged into it (its
    fields are added to the ones there; a field with the same name is the same field). Entries and values then
    follow wherever their collection and fields ended up, so nothing is lost when ids differ between installs."""

    def __init__(self, mgr: Optional[CollectionTypeManager] = None):
        self.mgr = mgr or get_collection_manager()
        self.type_map: Dict[str, str] = {}                      # incoming key -> key here (new collections)
        self.field_map: Dict[Tuple[str, str], str] = {}        # (type id here, incoming field id) -> id here
        self.warnings: List[str] = []

    @staticmethod
    def _tid(ctype: CollectionType) -> str:
        return ctype.page_key

    def import_type(self, rec: dict) -> str:
        """Returns "added", "updated" or raises CollectionError."""
        incoming = CollectionType.from_dict(rec)
        incoming_key = str(rec.get("key") or incoming.key)
        if incoming.builtin:
            current = self.mgr.builtin_type(incoming.key)
        else:
            current = self.mgr.type_by_name(incoming.name)
        merged, added_any = self._merge(current, incoming)
        stored = self.mgr.save_type(merged)
        if not incoming.builtin:
            self.type_map[incoming_key] = stored.key
        # fields matched by name keep the id they have here
        for f_in in incoming.fields:
            here = next((f for f in stored.fields if f.label.lower() == f_in.label.lower()), None)
            if here is not None:
                self.field_map[(stored.page_key, f_in.id)] = here.id
        if current is None or (current.builtin and not current.fields and added_any):
            return "added"
        return "updated"

    def _merge(self, current: Optional[CollectionType], incoming: CollectionType) -> Tuple[CollectionType, bool]:
        if current is None:
            base = CollectionType(key="", name=incoming.name, icon=incoming.icon,
                                  description=incoming.description, builtin=False)
        else:
            base = CollectionType(key=current.key, name=current.name, icon=current.icon,
                                  description=current.description, builtin=current.builtin,
                                  fields=list(current.fields), order=current.order)
            if not base.builtin:
                base.icon = incoming.icon or base.icon
                base.description = incoming.description or base.description
        reserved = {p.lower() for p in base.default_properties}
        added = False
        for f_in in incoming.fields:
            if f_in.label.lower() in reserved:
                self.warnings.append(f"The field '{f_in.label}' of {incoming.name} was left out: "
                                     f"it has the name of one of the collection's own properties.")
                continue
            same = next((f for f in base.fields if f.label.lower() == f_in.label.lower()), None)
            if same is not None:
                if same.kind == "choice" and f_in.kind == "choice":
                    same.choices = _unique(list(same.choices) + list(f_in.choices))[:MAX_CHOICES]
                continue
            if len(base.fields) >= MAX_FIELDS:
                self.warnings.append(f"{incoming.name} already has {MAX_FIELDS} fields: '{f_in.label}' was left out.")
                continue
            fid = f_in.id if all(f.id != f_in.id for f in base.fields) else new_field_id(
                f_in.label, [f.id for f in base.fields])
            base.fields.append(FieldDef(fid, f_in.label, f_in.kind, list(f_in.choices), f_in.filter))
            added = True
        return base, added

    def _remap(self, type_id: str, values: dict) -> dict:
        return {self.field_map.get((type_id, k), k): v for k, v in (values or {}).items()}

    def entry_type(self, rec: dict) -> Optional[CollectionType]:
        incoming = str(rec.get("collection") or "")
        key = self.type_map.get(incoming)
        if key is not None:
            return self.mgr.custom_type(key)
        return self.mgr.custom_type(incoming)

    def import_entry(self, rec: dict) -> str:
        """Returns "added" or "updated"; raises CollectionError."""
        ctype = self.entry_type(rec)
        if ctype is None:
            raise CollectionError("its collection isn't installed")
        entry = CustomEntry.from_dict(rec)
        entry.collection = ctype.key
        entry.values = self._remap(ctype.page_key, entry.values)
        existed = self.mgr.get_entry(ctype.key, entry.name) is not None
        self.mgr.add_entry(entry, replace=True)
        return "updated" if existed else "added"

    def import_values(self, rec: dict) -> str:
        collection = str(rec.get("collection") or "")
        name = str(rec.get("name") or "").strip()
        if collection not in BUILTIN_TYPES or not name:
            raise CollectionError("it doesn't name a built-in collection and entry")
        if not self.mgr.builtin_fields(collection):
            raise CollectionError(f"{BUILTIN_TYPES[collection][0]} has no added fields here")
        values = rec.get("values") if isinstance(rec.get("values"), dict) else {}
        existed = bool(self.mgr.extra_values(collection, name))
        self.mgr.set_extra_values(collection, name, self._remap(collection, values), merge=True)
        return "updated" if existed else "added"
