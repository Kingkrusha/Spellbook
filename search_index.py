"""
Full-text search index for every collection.

One SQLite FTS5 table (``search_index``) holds the name and readable text of
every spell, lineage, feat, background, class, subclass, piece of equipment,
magic item, monster, rules page and random table. It uses the trigram tokenizer, so a search still
matches any part of a word ("ball" finds "Fireball"), the same as the old
``LIKE '%...%'`` scans did, but each word is looked up in the index instead
of reading every row, parsing its JSON and stripping its links.

Triggers on the content tables keep the index up to date on every insert,
update and delete, so nothing else in the app has to remember to refresh it.
The text that goes into the index comes from ``search_text()``, a Python
function registered on each connection (``register_functions``): it strips
``[[category:Name|shown]]`` link markup and pulls the readable strings out of
the JSON columns (trait names and descriptions, not their keys).

FTS5 and the trigram tokenizer come with SQLite itself (3.34 or newer), so the
index adds nothing to the download. If the SQLite build in use lacks them,
``ensure()`` returns False and callers fall back to their plain LIKE searches.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Dict, List, Optional, Sequence

# Bump when the indexed text or the table layout changes: the index is then
# rebuilt the next time the app starts.
INDEX_VERSION = 3

TABLE = "search_index"
META_TABLE = "search_index_meta"

# section shown in results -> (table, columns whose text is indexed as the body,
# optional WHERE clause that decides which rows are searchable)
SOURCES: Dict[str, tuple] = {
    "Spells": ("spells", ("description",), None),
    "Lineages": ("lineages", ("description", "traits_json"), None),
    "Feats": ("feats", ("prereq", "description"), None),
    "Backgrounds": ("backgrounds", ("description", "features_json"), None),
    "Classes": ("classes", ("class_features_json",), None),
    "Subclasses": ("subclasses", ("description", "features_json"), None),
    "Equipment": ("equipment", ("type", "description", "properties_json"), None),
    "Magic Items": ("magic_items", ("type", "rarity", "description", "properties_json"), None),
    "Rules": ("rules", ("category", "description"), None),
    "Random Tables": ("random_tables", ("category", "description", "entries_json"), None),
    # Entries of the collections people make themselves (custom_collections.py); the results are labelled with
    # their collection's name by SpellDatabase.global_search.
    "Custom": ("custom_entries", ("description", "tags_json", "values_json"), None),
    # Summoned creatures (spell_only) only exist inside their spell, so they are not searchable.
    "Monsters": ("monsters", ("creature_type", "description", "traits_json", "actions_json",
                              "bonus_actions_json", "reactions_json", "legendary_actions_json"),
                 "spell_only = 0"),
}


# ---------------------------------------------------------------------------
# Text extraction


def _json_strings(value, out: List[str]):
    """Collect the string values (never the keys) of parsed JSON."""
    if isinstance(value, str):
        if value.strip():
            out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _json_strings(v, out)
    elif isinstance(value, list):
        for v in value:
            _json_strings(v, out)


def search_text(*values) -> str:
    """The readable text of some column values, as one string for the index.

    JSON columns contribute their string values; plain text has its link
    markup replaced by the text the link shows.
    """
    from object_link_sweep import strip_links

    parts: List[str] = []
    for value in values:
        if value is None:
            continue
        text = str(value)
        stripped = text.lstrip()
        if stripped[:1] in ("[", "{") and not stripped.startswith("[["):
            try:
                strings: List[str] = []
                _json_strings(json.loads(text), strings)
                parts.extend(strip_links(s) for s in strings)
                continue
            except (ValueError, TypeError):
                pass
        if text.strip():
            parts.append(strip_links(text))
    return "\n".join(parts)


def register_functions(conn: sqlite3.Connection):
    """Make ``search_text`` callable from SQL (the triggers use it)."""
    conn.create_function("search_text", -1, search_text, deterministic=True)


# ---------------------------------------------------------------------------
# Building the index


def is_supported(conn: sqlite3.Connection) -> bool:
    """True when this SQLite build has FTS5 with the trigram tokenizer."""
    try:
        conn.execute("CREATE VIRTUAL TABLE temp._fts_probe USING fts5(x, tokenize='trigram')")
        conn.execute("DROP TABLE temp._fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _table_columns(conn: sqlite3.Connection, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _body_expr(prefix: str, columns: Sequence[str]) -> str:
    return "search_text(" + ", ".join(f"{prefix}{c}" for c in columns) + ")"


def _drop(conn: sqlite3.Connection):
    for section, (table, _cols, _where) in SOURCES.items():
        for event in ("ai", "au", "ad"):
            conn.execute(f"DROP TRIGGER IF EXISTS {TABLE}_{table}_{event}")
    conn.execute(f"DROP TABLE IF EXISTS {TABLE}")


def _build(conn: sqlite3.Connection):
    """Create the index and its triggers, then fill it from the content tables."""
    _drop(conn)
    conn.execute(f"""
        CREATE VIRTUAL TABLE {TABLE} USING fts5(
            section UNINDEXED, item_id UNINDEXED, name, body,
            tokenize = 'trigram', detail = 'none'
        )
    """)
    for section, (table, columns, where) in SOURCES.items():
        present = _table_columns(conn, table)
        if not present:
            continue
        columns = [c for c in columns if c in present]
        filter_new = f"WHERE {where.replace('spell_only', 'NEW.spell_only')}" if where else ""
        insert_new = (f"INSERT INTO {TABLE} (section, item_id, name, body) "
                      f"SELECT '{section}', NEW.id, NEW.name, {_body_expr('NEW.', columns)} {filter_new};")
        delete_old = f"DELETE FROM {TABLE} WHERE section = '{section}' AND item_id = OLD.id;"
        conn.execute(f"CREATE TRIGGER {TABLE}_{table}_ai AFTER INSERT ON {table} BEGIN {insert_new} END")
        conn.execute(f"CREATE TRIGGER {TABLE}_{table}_ad AFTER DELETE ON {table} BEGIN {delete_old} END")
        # Only the indexed columns: the spells table bumps its own updated_at in a trigger,
        # and that second UPDATE should not re-index the row again.
        watched = ", ".join(["name"] + columns + (["spell_only"] if where else []))
        conn.execute(f"CREATE TRIGGER {TABLE}_{table}_au AFTER UPDATE OF {watched} ON {table} "
                     f"BEGIN {delete_old} {insert_new} END")
        conn.execute(
            f"INSERT INTO {TABLE} (section, item_id, name, body) "
            f"SELECT '{section}', id, name, {_body_expr('', columns)} FROM {table}"
            + (f" WHERE {where}" if where else ""))
    conn.execute(f"CREATE TABLE IF NOT EXISTS {META_TABLE} (version INTEGER NOT NULL)")
    conn.execute(f"DELETE FROM {META_TABLE}")
    conn.execute(f"INSERT INTO {META_TABLE} (version) VALUES (?)", (INDEX_VERSION,))


def _expected_triggers(conn: sqlite3.Connection) -> int:
    return 3 * sum(1 for table, _c, _w in SOURCES.values() if _table_columns(conn, table))


def ensure(conn: sqlite3.Connection) -> bool:
    """Make sure the index exists and is current. Returns False when it can't be used."""
    if not is_supported(conn):
        _drop(conn)  # triggers left by a newer SQLite would fail on every edit here
        return False
    try:
        row = conn.execute(f"SELECT version FROM {META_TABLE} LIMIT 1").fetchone()
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (TABLE,)).fetchone()
        # A migration that rebuilds a content table drops that table's triggers with it,
        # so a missing trigger also means the index has to be built again.
        triggers = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger' AND name LIKE ?",
            (f"{TABLE}_%",)).fetchone()[0]
        if row and row[0] == INDEX_VERSION and exists and triggers == _expected_triggers(conn):
            return True
    except sqlite3.OperationalError:
        pass
    _build(conn)
    return True


def rebuild(conn: sqlite3.Connection) -> bool:
    """Throw the index away and build it again (repairs a damaged index)."""
    if not is_supported(conn):
        return False
    _build(conn)
    return True


# ---------------------------------------------------------------------------
# Searching


def _terms(query: str) -> List[str]:
    return [t for t in query.lower().split() if t]


def matching_rowids(conn: sqlite3.Connection, query: str,
                    section: Optional[str] = None) -> Optional[set]:
    """Index rows whose name or text contains every word of ``query``
    (each word anywhere, as a substring). None when there are no words.

    Each word is looked up on its own, in the name and the text separately:
    that way every lookup is a single LIKE, which the trigram index answers
    directly (an ESCAPE clause, an OR, or a word under three letters would
    make SQLite read the whole table instead; that is still correct, just
    slower). ``%`` and ``_`` in a word act as LIKE wildcards.
    """
    terms = _terms(query)
    if not terms:
        return None
    where_section = " AND section = ?" if section else ""
    extra = [section] if section else []
    found: Optional[set] = None
    # Longest words first: they match the fewest rows, so the set shrinks fastest.
    for term in sorted(terms, key=len, reverse=True):
        pattern = f"%{term}%"
        ids = set()
        for column in ("name", "body"):
            ids.update(r[0] for r in conn.execute(
                f"SELECT rowid FROM {TABLE} WHERE {column} LIKE ?{where_section}",
                [pattern] + extra))
        found = ids if found is None else found & ids
        if not found:
            break
    return found


def search(conn: sqlite3.Connection, query: str, limit: int = 50) -> List[dict]:
    """Every item whose name or text contains all the words of ``query``.

    Results are dicts with ``section``, ``id``, ``name`` and ``in_name`` (True
    when the name itself matched). Name matches come first: names that start
    with the query, then other name matches, then text-only matches, each
    alphabetical.
    """
    rowids = matching_rowids(conn, query)
    if not rowids:
        return []
    terms = _terms(query)
    phrase = " ".join(terms)
    hits = []
    ids = sorted(rowids)
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        rows = conn.execute(
            f"SELECT section, item_id, name FROM {TABLE} WHERE rowid IN ({','.join('?' * len(chunk))})",
            chunk).fetchall()
        for section, item_id, name in rows:
            lowered = (name or "").lower()
            in_name = all(t in lowered for t in terms)
            rank = (0 if lowered.startswith(phrase) else 1) if in_name else 2
            hits.append((rank, lowered, {"section": section, "id": item_id, "name": name,
                                         "in_name": in_name}))
    hits.sort(key=lambda h: (h[0], h[1]))
    return [h[2] for h in hits[:limit]]


def item_ids(conn: sqlite3.Connection, query: str, section: str) -> List[int]:
    """Ids of the items of one section whose name or text contains every word of ``query``."""
    rowids = matching_rowids(conn, query, section)
    if not rowids:
        return []
    ids = sorted(rowids)
    out: List[int] = []
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        out.extend(r[0] for r in conn.execute(
            f"SELECT item_id FROM {TABLE} WHERE rowid IN ({','.join('?' * len(chunk))})", chunk))
    return out
