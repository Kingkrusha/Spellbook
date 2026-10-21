"""
Declarative table definitions and the generic CRUD behind the content collections.

Lineages, feats, equipment, magic items, backgrounds and rules pages are all "a table with a unique
name plus some columns", and each used to have its own hand-written ``get_all`` / ``get_by_name`` /
``insert`` / ``update`` / ``delete`` / row-to-dict. Here each is described once as a
:class:`Collection` (its columns, how each is written and read back) and :class:`CollectionStoreMixin`
supplies the SQL. ``SpellDatabase`` mixes it in and keeps its named per-collection methods
(``insert_feat`` ...) as one-line wrappers, so callers are unaffected.

A :class:`Column` owns both directions for one dict key, so writing and reading cannot drift apart:

* ``to_db(data)``  - the value to store, from the dict the caller passed (missing keys take a default)
* ``from_db(row)`` - the value to put in the dict, from the ``sqlite3.Row``
"""

import json
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple


def safe_json_list(row, key) -> list:
    """Read a JSON-list column that may be absent on older rows/schemas."""
    try:
        raw = row[key]
    except (IndexError, KeyError):
        return []
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def row_flag(row, key, default=False) -> bool:
    """Read a boolean column that may be absent on an older row/schema."""
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return default if value is None else bool(value)


@dataclass(frozen=True)
class Column:
    key: str                              # key in the dict the app works with
    column: str                           # column in the table
    to_db: Callable[[dict], Any]
    from_db: Optional[Callable[[Any], Any]] = None   # None: written by this module, read back by the caller
    insert_only: bool = False                        # not touched by an update (e.g. a subclass's class_id)


def text(key: str, default: Any = '', column: Optional[str] = None) -> Column:
    """A text (or int) column; an empty stored value reads back as ``default``."""
    column = column or key
    return Column(key, column, lambda d: d.get(key, default), lambda r: r[column] or default)


def real(key: str, default: float = 0.0) -> Column:
    """A numeric column where 0 is a real value (only NULL reads back as ``default``)."""
    return Column(key, key, lambda d: d.get(key, default),
                  lambda r: r[key] if r[key] is not None else default)


def flag(key: str, default: bool = False) -> Column:
    """A boolean stored as 0/1."""
    return Column(key, key, lambda d: 1 if d.get(key, default) else 0, lambda r: bool(r[key]))


def json_col(key: str, default: Callable[[], Any] = list, *, safe: bool = False,
             falsy_is_empty: bool = False) -> Column:
    """A JSON-encoded column stored as ``<key>_json``.

    ``safe`` tolerates the column being absent or malformed (see :func:`safe_json_list`);
    ``falsy_is_empty`` stores ``None`` as an empty value instead of ``null``.
    """
    column = f"{key}_json"
    if falsy_is_empty:
        to_db = lambda d: json.dumps(d.get(key, default()) or default())
    else:
        to_db = lambda d: json.dumps(d.get(key, default()))
    if safe:
        from_db = lambda r: safe_json_list(r, column)
    else:
        from_db = lambda r: json.loads(r[column]) if r[column] else default()
    return Column(key, column, to_db, from_db)


NAME = Column('name', 'name', lambda d: d['name'], lambda r: r['name'])


@dataclass(frozen=True)
class Collection:
    table: str
    columns: Tuple[Column, ...]           # NAME first; ``id`` is implicit
    order_by: str = "name"
    skip_on_seed: Tuple[str, ...] = ()    # keys the bundled seed files do not carry (left to the table default)

    # ---- SQL

    def insert_statement(self, or_ignore: bool = False, skip: Tuple[str, ...] = ()) -> str:
        columns = [c.column for c in self.columns if c.key not in skip]
        verb = "INSERT OR IGNORE" if or_ignore else "INSERT"
        return f"{verb} INTO {self.table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"

    @property
    def insert_sql(self) -> str:
        return self.insert_statement()

    @property
    def update_sql(self) -> str:
        sets = ", ".join(f"{c.column} = ?" for c in self.columns if not c.insert_only)
        return f"UPDATE {self.table} SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"

    @property
    def seed_sql(self) -> str:
        """What loads a bundled row: ``INSERT OR IGNORE`` (the table's name column is UNIQUE)."""
        return self.insert_statement(or_ignore=True, skip=self.skip_on_seed)

    def update_by_name_sql(self, *columns: str) -> str:
        """``UPDATE`` of just these columns of the row with a given name (parameters: the values, then the name)."""
        sets = ", ".join(f"{c} = ?" for c in columns)
        return f"UPDATE {self.table} SET {sets} WHERE name = ? COLLATE NOCASE"

    # ---- values

    def values(self, data: dict, skip: Tuple[str, ...] = ()) -> list:
        """The parameters for ``insert_sql``."""
        return [c.to_db(data) for c in self.columns if c.key not in skip]

    def column_values(self, data: dict, *columns: str) -> list:
        """The parameters for just these columns, in the order given."""
        by_column = {c.column: c for c in self.columns}
        return [by_column[name].to_db(data) for name in columns]

    def update_values(self, data: dict) -> list:
        """The parameters for ``update_sql`` (without the trailing row id)."""
        return [c.to_db(data) for c in self.columns if not c.insert_only]

    def seed_values(self, item: dict) -> list:
        """The parameters for ``seed_sql``: a bundled row, whose name may be missing."""
        return self.values({'name': '', **item}, skip=self.skip_on_seed)

    def to_dict(self, row) -> dict:
        result = {'id': row['id']}
        for c in self.columns:
            result[c.key] = c.from_db(row)
        return result


LINEAGES = Collection('lineages', (
    NAME,
    text('description'),
    text('creature_type', 'Humanoid'),
    text('size', 'Medium'),
    text('speed', 30),
    json_col('traits'),
    text('source'),
    flag('is_official', True),
    flag('is_custom'),
    flag('is_legacy'),
))


def _spells_num_from_db(row) -> dict:
    raw = json.loads(row['spells_num_json']) if row['spells_num_json'] else {}
    return {int(k): v for k, v in raw.items()} if raw else {}


FEATS = Collection('feats', (
    NAME,
    text('type'),
    flag('is_spellcasting'),
    json_col('spell_lists'),
    Column('spells_num', 'spells_num_json',
           lambda d: json.dumps(d.get('spells_num', {})), _spells_num_from_db),
    flag('has_prereq'),
    text('prereq'),
    json_col('set_spells'),
    text('description'),
    text('source'),
    flag('is_official', True),
    flag('is_custom'),
    flag('is_legacy'),
    json_col('roll_effects', safe=True, falsy_is_empty=True),
), skip_on_seed=('roll_effects',))

EQUIPMENT = Collection('equipment', (
    NAME,
    text('type', 'Adventuring Gear'),
    text('cost'),
    real('weight'),
    text('source'),
    json_col('crafting_materials'),
    text('crafting_tool'),
    text('description'),
    json_col('tags'),
    json_col('properties', safe=True),
    flag('is_official', True),
    flag('is_custom'),
))

MAGIC_ITEMS = Collection('magic_items', (
    NAME,
    text('type', 'Wondrous Item'),
    text('cost'),
    real('weight'),
    text('source'),
    json_col('enchanting_materials'),
    text('description'),
    json_col('tags'),
    json_col('properties', safe=True),
    text('rarity', 'Common'),
    Column('requires_attunement', 'requires_attunement',
           lambda d: 1 if d.get('requires_attunement', bool(d.get('attunement_requirement'))) else 0,
           lambda r: row_flag(r, 'requires_attunement', bool((r['attunement_requirement'] or '').strip()))),
    text('attunement_requirement'),
    flag('attunement_optional'),
    flag('is_official', True),
    flag('is_custom'),
    json_col('roll_effects', safe=True, falsy_is_empty=True),
), skip_on_seed=('roll_effects',))

BACKGROUNDS = Collection('backgrounds', (
    NAME,
    text('source'),
    flag('is_legacy'),
    text('description'),
    json_col('skills'),
    json_col('other_proficiencies'),
    json_col('ability_scores'),
    json_col('feats'),
    text('equipment'),
    json_col('features'),
    flag('is_official', True),
    flag('is_custom'),
))

RULES = Collection('rules', (
    NAME,
    text('category'),
    text('description'),
    text('source'),
    json_col('tags', safe=True),
    Column('order', 'sort_order', lambda d: int(d.get('order', 0) or 0), lambda r: r['sort_order'] or 0),
    flag('is_official', True),
    flag('is_custom'),
), order_by="(sort_order = 0), sort_order, name COLLATE NOCASE")

RANDOM_TABLES = Collection('random_tables', (
    NAME,
    text('category'),
    text('dice', 'd100'),
    text('description'),
    json_col('entries', safe=True),
    json_col('tags', safe=True),
    text('source'),
    flag('is_official'),
    flag('is_custom', True),
), order_by="name COLLATE NOCASE")


def _written(key: str, column: str, to_db, insert_only: bool = False) -> Column:
    return Column(key, column, to_db, None, insert_only)


def _json_written(key: str, column: str = "") -> Column:
    return _written(key, column or f"{key}_json", lambda d: json.dumps(d.get(key, [])))


# Classes and subclasses are only *written* through this module; SpellDatabase reads them back with its own
# row converters (a class carries its subclasses, and the subclass JSON is unpacked).
CLASSES = Collection('classes', (
    NAME,
    _written('hit_die', 'hit_die', lambda d: d.get('hit_die', 8)),
    _written('primary_ability', 'primary_ability', lambda d: d.get('primary_ability', '')),
    _json_written('saving_throws'),
    _json_written('armor_proficiencies'),
    _json_written('weapon_proficiencies'),
    _json_written('tool_proficiencies'),
    _json_written('skill_proficiencies'),
    _written('num_skills', 'num_skills', lambda d: d.get('num_skills', 2)),
    _json_written('starting_equipment'),
    _json_written('class_features'),
    _written('spellcasting', 'spellcasting_json',
             lambda d: json.dumps(d.get('spellcasting')) if d.get('spellcasting') else 'null'),
    _written('subclass_name', 'subclass_name', lambda d: d.get('subclass_name', '')),
    _written('subclass_level', 'subclass_level', lambda d: d.get('subclass_level', 3)),
    _json_written('class_table_columns'),
    _json_written('trackable_features'),
    _json_written('class_spells'),
    _written('unarmored_defense', 'unarmored_defense', lambda d: d.get('unarmored_defense', '')),
    _written('source', 'source', lambda d: d.get('source', '')),
    _written('is_official', 'is_official', lambda d: 1 if d.get('is_official', True) else 0),
    _written('is_custom', 'is_custom', lambda d: 1 if d.get('is_custom', False) else 0),
    _written('is_legacy', 'is_legacy', lambda d: 1 if d.get('is_legacy', False) else 0),
))


def _subclass_features_json(d: dict) -> str:
    """A subclass keeps everything but its basics in one JSON column."""
    return json.dumps({
        'features': d.get('features', []),
        'subclass_spells': d.get('subclass_spells', []),
        'armor_proficiencies': d.get('armor_proficiencies', []),
        'weapon_proficiencies': d.get('weapon_proficiencies', []),
        'unarmored_defense': d.get('unarmored_defense', ''),
        'trackable_features': d.get('trackable_features', []),
    })


SUBCLASSES = Collection('subclasses', (
    NAME,
    _written('class_id', 'class_id', lambda d: d['class_id'], insert_only=True),
    _written('description', 'description', lambda d: d.get('description', '')),
    _written('features', 'features_json', _subclass_features_json),
    _written('source', 'source', lambda d: d.get('source', '')),
    _written('is_official', 'is_official', lambda d: 1 if d.get('is_official', True) else 0),
    _written('is_custom', 'is_custom', lambda d: 1 if d.get('is_custom', False) else 0),
    _written('is_legacy', 'is_legacy', lambda d: 1 if d.get('is_legacy', False) else 0),
))


class CollectionStoreMixin:
    """Generic CRUD over a :class:`Collection`; needs ``get_connection()`` from the host class."""

    def _coll_get_all(self, coll: Collection) -> List[dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {coll.table} ORDER BY {coll.order_by}")
            return [coll.to_dict(row) for row in cursor.fetchall()]

    def _coll_get_by_name(self, coll: Collection, name: str) -> Optional[dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {coll.table} WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            return coll.to_dict(row) if row else None

    def _coll_insert(self, coll: Collection, data: dict) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(coll.insert_sql, coll.values(data))
            return cursor.lastrowid or 0

    def _coll_update(self, coll: Collection, row_id: int, data: dict) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(coll.update_sql, coll.update_values(data) + [row_id])
            return cursor.rowcount > 0

    def _coll_delete(self, coll: Collection, row_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM {coll.table} WHERE id = ?", (row_id,))
            return cursor.rowcount > 0
