"""
Random tables (d100 tables and the like): what a table is, reading one from pasted text, and rolling on it.

A table has a die (``d100``, ``d20``, ``2d6``...) and entries, each covering a range of results::

    01-05  A merchant caravan
    06-20  {1d4} wolves
    21-00  Nothing. Roll on {table: Weather} instead.

An entry's text can roll dice of its own (``{2d6}``) and roll on another table (``{table: Name}``); both are
rolled with the entry, so one click gives the whole result.

The tables live in the database (``random_tables``) with the rest of the content, so the search index finds
them by their entries' text too. Rolling uses lan.dice, the session chat's dice.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from collection_manager import DbBackedManager

DEFAULT_DICE = "d100"
MAX_NESTING = 5               # {table: ...} inside {table: ...}, at most this deep
MAX_ENTRIES = 1000

_DASHES = "–—‒−"
# "01-05", "1–5", "96-00", "7", "10+" at the start of a line, then a separator ("." ":" "|" ")" or spaces)
_LINE_RE = re.compile(
    rf"^\s*\|?\s*(?P<low>\d{{1,4}})\s*(?:(?:[-{_DASHES}]|to)\s*(?P<high>\d{{1,4}})|(?P<plus>\+))?"
    r"\s*(?:[.:|)\]]\s*|\s+)(?P<text>.*?)\s*\|?\s*$", re.IGNORECASE)
INLINE_RE = re.compile(r"\{\s*(?:(?P<table>table)\s*:\s*(?P<name>[^{}]+?)|(?P<dice>[0-9dDkKhHlL%+\-\s]+?))\s*\}")


# --------------------------------------------------------------------------- #
# Dice ranges
# --------------------------------------------------------------------------- #

def dice_range(dice: str) -> Tuple[int, int]:
    """The lowest and highest total of a dice expression (``"2d6"`` -> ``(2, 12)``). Raises DiceError."""
    from lan.dice import parse_expression
    low = high = 0
    for t in parse_expression(dice or DEFAULT_DICE):
        if t.is_dice:
            n = t.keep_n if t.keep else t.count
            lo, hi = n, n * t.sides
        else:
            lo = hi = t.value
        if t.sign < 0:
            lo, hi = -hi, -lo
        low += lo
        high += hi
    return low, high


def valid_dice(dice: str) -> bool:
    try:
        dice_range(dice)
        return True
    except ValueError:
        return False


def format_range(low: int, high: int, top: int = 100) -> str:
    """``(1, 5)`` -> ``"01-05"`` on a d100 (whose 100 is written ``00``), ``"1-5"`` otherwise."""
    if top == 100 and low >= 1:
        def pad(n):
            return "00" if n == 100 else f"{n:02d}"
    else:
        pad = str
    return pad(low) if low == high else f"{pad(low)}–{pad(high)}"


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #

@dataclass
class TableEntry:
    low: int
    high: int
    text: str

    def covers(self, value: int) -> bool:
        return self.low <= value <= self.high

    def to_dict(self) -> dict:
        return {"low": self.low, "high": self.high, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict) -> "TableEntry":
        low = int(d.get("low", 0) or 0)
        high = int(d.get("high", low) or low)
        return cls(min(low, high), max(low, high), str(d.get("text", "")))


@dataclass
class RandomTable:
    name: str
    dice: str = DEFAULT_DICE
    entries: List[TableEntry] = field(default_factory=list)
    category: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = ""
    is_official: bool = False
    is_custom: bool = True
    id: Optional[int] = None                   # the database row (not exported)

    @property
    def range(self) -> Tuple[int, int]:
        try:
            return dice_range(self.dice)
        except ValueError:
            return (1, 100)

    def entry_for(self, value: int) -> Optional[TableEntry]:
        for entry in self.entries:
            if entry.covers(value):
                return entry
        return None

    def index_for(self, value: int) -> Optional[int]:
        for i, entry in enumerate(self.entries):
            if entry.covers(value):
                return i
        return None

    def range_text(self, entry: TableEntry) -> str:
        return format_range(entry.low, entry.high, self.range[1])

    def problems(self) -> List[str]:
        """What is wrong with the entries: results no entry covers, results two entries cover, entries the die
        can't reach."""
        return coverage_problems(self.entries, *self.range)

    def entries_text(self) -> str:
        """The entries as the editor shows them, one per line."""
        top = self.range[1]
        return "\n".join(f"{format_range(e.low, e.high, top)}  {e.text}" for e in self.entries)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "dice": self.dice, "category": self.category,
            "description": self.description, "entries": [e.to_dict() for e in self.entries],
            "tags": list(self.tags), "source": self.source,
            "is_official": self.is_official, "is_custom": self.is_custom,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RandomTable":
        entries = d.get("entries") or []
        if isinstance(entries, str):
            try:
                entries = json.loads(entries)
            except ValueError:
                entries = []
        return cls(
            name=str(d.get("name", "")).strip(),
            dice=str(d.get("dice") or DEFAULT_DICE).strip(),
            entries=[TableEntry.from_dict(e) for e in entries if isinstance(e, dict)][:MAX_ENTRIES],
            category=str(d.get("category", "") or ""),
            description=str(d.get("description", "") or ""),
            tags=[str(t) for t in (d.get("tags") or [])],
            source=str(d.get("source", "") or ""),
            is_official=bool(d.get("is_official", False)),
            is_custom=bool(d.get("is_custom", True)),
            id=d.get("id"),
        )


def coverage_problems(entries: List[TableEntry], low: int, high: int) -> List[str]:
    problems: List[str] = []
    if not entries:
        return ["The table has no entries."]
    owner: Dict[int, int] = {}
    overlaps: List[int] = []
    outside: List[TableEntry] = []
    for i, e in enumerate(entries):
        if e.high < low or e.low > high:
            outside.append(e)
        for v in range(max(e.low, low), min(e.high, high) + 1):
            if v in owner:
                overlaps.append(v)
            else:
                owner[v] = i
    missing = [v for v in range(low, high + 1) if v not in owner]
    top = high
    if missing:
        problems.append("No entry for " + _ranges_text(missing, top) + ".")
    if overlaps:
        problems.append("More than one entry for " + _ranges_text(sorted(set(overlaps)), top) + ".")
    for e in outside:
        problems.append(f"The die can't roll {format_range(e.low, e.high, top)} ({low}–{high}).")
    return problems


def _ranges_text(values: List[int], top: int, limit: int = 6) -> str:
    runs: List[Tuple[int, int]] = []
    for v in values:
        if runs and v == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], v)
        else:
            runs.append((v, v))
    parts = [format_range(a, b, top) for a, b in runs[:limit]]
    if len(runs) > limit:
        parts.append(f"and {len(runs) - limit} more")
    return ", ".join(parts)


# --------------------------------------------------------------------------- #
# Reading pasted text
# --------------------------------------------------------------------------- #

def _is_markdown_rule(line: str) -> bool:
    s = line.strip()
    return bool(s) and set(s) <= set("|-: ") and "-" in s


def parse_entries(text: str, dice: Optional[str] = None) -> Tuple[List[TableEntry], str]:
    """Entries from pasted text, and the die they suit.

    Understands numbered lines (``01-05 text``, ``1. text``, ``96–00 | text``, ``10+ text``) and markdown
    tables (``| 01-05 | text |``; header and rule rows are skipped). A line without a number continues the
    entry above it. If no line is numbered, each line is one entry, numbered from 1, and the die is
    ``d<number of lines>``. ``dice`` is the table's die when known: it decides what ``00`` and ``10+`` mean.
    """
    lines = [l.rstrip() for l in (text or "").splitlines()]
    numbered: List[Tuple[str, Optional[str], bool, str]] = []
    plain: List[str] = []
    for line in lines:
        if not line.strip() or _is_markdown_rule(line):
            continue
        m = _LINE_RE.match(line)
        if m:
            numbered.append((m.group("low"), m.group("high"), bool(m.group("plus")), m.group("text").strip()))
            continue
        if line.strip().startswith("|") and not numbered:
            continue                                  # a markdown header row
        cleaned = line.strip().strip("|").strip()
        cleaned = re.sub(r"^[-*•]\s+", "", cleaned)
        if numbered:
            low, high, plus, prev = numbered[-1]
            numbered[-1] = (low, high, plus, f"{prev} {cleaned}".strip())
        else:
            plain.append(cleaned)

    if not numbered:
        entries = [TableEntry(i + 1, i + 1, t) for i, t in enumerate(plain[:MAX_ENTRIES])]
        return entries, (dice or (f"d{len(entries)}" if len(entries) >= 2 else DEFAULT_DICE))

    # The die: the one given, or the smallest common die that fits the highest number written
    top_written = 0
    for low, high, _plus, _t in numbered:
        for n in (low, high):
            if n is not None:
                top_written = max(top_written, 100 if n.strip("0") == "" else int(n))
    if dice is None:
        dice = next((f"d{s}" for s in (4, 6, 8, 10, 12, 20, 100) if top_written <= s), f"d{top_written}")
    try:
        hi_die = dice_range(dice)[1]
    except ValueError:
        hi_die = max(top_written, 1)

    def value(n: str) -> int:
        v = int(n)
        if v == 0 and hi_die >= 100 and len(n) >= 2:
            return 100                                # "00" on a d100
        return v

    entries = []
    for low, high, plus, t in numbered[:MAX_ENTRIES]:
        a = value(low)
        b = hi_die if plus else (value(high) if high is not None else a)
        if b < a and high is not None and int(high) == 0:
            b = 100
        entries.append(TableEntry(min(a, b), max(a, b), t))
    return entries, dice


# --------------------------------------------------------------------------- #
# Rolling
# --------------------------------------------------------------------------- #

@dataclass
class TableRoll:
    table: RandomTable
    total: int
    detail: str                                # the dice behind the total, e.g. "[4, 3]"
    entry: Optional[TableEntry]
    index: Optional[int]
    text: str                                  # the entry's text with its {dice} and {table: ...} rolled
    nested: List["TableRoll"] = field(default_factory=list)

    def summary(self) -> str:
        if self.entry is None:
            return f"{self.table.name}: {self.total} (no entry)"
        return f"{self.table.name}: {self.total} → {self.text}"


def roll_table(table: RandomTable, lookup: Optional[Callable[[str], Optional[RandomTable]]] = None,
               rng: Optional[random.Random] = None, _depth: int = 0) -> TableRoll:
    """Roll the table's die and find the entry. Raises DiceError if the die is not valid."""
    from lan.dice import roll
    r = roll(table.dice or DEFAULT_DICE, rng)
    total = r.total
    index = table.index_for(total)
    entry = table.entries[index] if index is not None else None
    nested: List[TableRoll] = []
    text = expand_inline(entry.text, lookup, rng, _depth, nested) if entry else ""
    return TableRoll(table, total, r.detail, entry, index, text, nested)


def expand_inline(text: str, lookup=None, rng=None, depth: int = 0, nested: Optional[list] = None) -> str:
    """``{2d6}`` -> the total rolled; ``{table: Name}`` -> a result rolled on that table."""
    from lan.dice import DiceError, roll

    def replace(m):
        if m.group("table"):
            name = m.group("name").strip()
            other = lookup(name) if lookup else None
            if other is None or depth >= MAX_NESTING:
                return m.group(0)
            sub = roll_table(other, lookup, rng, depth + 1)
            if nested is not None:
                nested.append(sub)
            return sub.text if sub.entry else m.group(0)
        try:
            return str(roll(m.group("dice").replace(" ", ""), rng).total)
        except DiceError:
            return m.group(0)
    return INLINE_RE.sub(replace, text or "")


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #

class RandomTablesManager(DbBackedManager):
    """The random tables stored in the database."""

    _instance: Optional["RandomTablesManager"] = None

    def __init__(self):
        super().__init__()
        self._by_name: Dict[str, RandomTable] = {}

    def _load_all(self) -> list:
        tables = [RandomTable.from_dict(d) for d in self.db.get_all_random_tables()]
        self._by_name = {t.name.lower(): t for t in tables}
        return tables

    @property
    def tables(self) -> List[RandomTable]:
        return self._cached()

    def get_table(self, name: str) -> Optional[RandomTable]:
        self._cached()
        return self._by_name.get((name or "").strip().lower())

    def categories(self) -> List[str]:
        return sorted({t.category for t in self.tables if t.category}, key=str.lower)

    def add_table(self, table: RandomTable) -> bool:
        """Add a table, or replace the one with the same name."""
        existing = self.db.get_random_table_by_name(table.name)
        if existing:
            self.db.update_random_table(existing["id"], table.to_dict())
        else:
            self.db.insert_random_table(table.to_dict())
        self._invalidate_cache()
        return True

    def update_table(self, old_name: str, table: RandomTable) -> bool:
        existing = self.db.get_random_table_by_name(old_name)
        if not existing:
            return False
        ok = self.db.update_random_table(existing["id"], table.to_dict())
        self._invalidate_cache()
        return ok

    def delete_table(self, name: str) -> bool:
        existing = self.db.get_random_table_by_name(name)
        if not existing:
            return False
        ok = self.db.delete_random_table(existing["id"])
        self._invalidate_cache()
        return ok

    def search(self, query: str) -> List[RandomTable]:
        """Tables whose name, category, description or entries contain every word of ``query``; name matches
        first."""
        words = [w for w in (query or "").lower().split() if w]
        if not words:
            return list(self.tables)
        ids = self.db.random_table_search_ids(query)
        tables = self.tables
        if ids is not None:
            by_id = set(ids)
            found = [t for t in tables if t.id in by_id]
        else:
            def haystack(t):
                return " ".join([t.name, t.category, t.description] + [e.text for e in t.entries]).lower()
            found = [t for t in tables if all(w in haystack(t) for w in words)]
        found.sort(key=lambda t: (0 if all(w in t.name.lower() for w in words) else 1, t.name.lower()))
        return found

    def roll(self, table: RandomTable, rng=None) -> TableRoll:
        return roll_table(table, self.get_table, rng)

    # ---- files

    def export_to_json(self, file_path: str, tables: Optional[List[RandomTable]] = None) -> int:
        from atomic_io import atomic_write_json
        tables = self.tables if tables is None else tables
        atomic_write_json(file_path, {"random_tables": [t.to_dict() for t in tables]})
        return len(tables)

    def import_from_json(self, file_path: str) -> int:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        records = data.get("random_tables", []) if isinstance(data, dict) else data
        count = 0
        for rec in records if isinstance(records, list) else []:
            if not isinstance(rec, dict):
                continue
            table = RandomTable.from_dict(rec)
            if not table.name:
                continue
            table.is_custom, table.is_official = True, False
            self.add_table(table)
            count += 1
        return count


def get_random_tables_manager() -> RandomTablesManager:
    return RandomTablesManager.get_instance()
