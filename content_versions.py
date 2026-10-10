"""Several versions of one piece of content, shown as one entry.

A 2014 entry whose name 2024 content already uses is stored as "Name (Legacy)", and species the
2014 books printed more than once as "Name (Legacy: MPMM)", "Name (Legacy: VGM)" (see
legacy_content.py). In the browsing views they are not separate list entries: the list shows the name
once and the detail panel's Source line becomes a drop-down that switches between the versions - the
2024 one, the 2014 one, or a 2014 book's reprint (Monsters of the Multiverse updated many species and
is still 2014 content, just like the older versions).

This module is the logic only (grouping, ordering, which versions the Legacy content setting lets
through); ui/version_bar.py is the drop-down.
"""

import re
from typing import Callable, Dict, Iterable, List, Optional, TypeVar

from legacy_content import legacy_pair_key, strip_legacy_suffix

T = TypeVar("T")

# Roughly when each book came out; newest first inside a group of 2014 versions, so the most recent
# printing is the one shown by default. Unknown sources sort last (then alphabetically).
_SOURCE_YEAR = [
    ("Monsters of the Multiverse", 2022), ("Wayfinder", 2023), ("Planescape", 2023),
    ("Bigby Presents", 2023), ("Book of Many Things", 2023), ("Spelljammer", 2022),
    ("Dragonlance", 2022), ("Witchlight", 2022), ("Van Richten", 2021), ("Fizban", 2021),
    ("Strixhaven", 2021), ("Mythic Odysseys", 2020), ("Tasha", 2020), ("Wildemount", 2020),
    ("Rising from the Last War", 2019), ("Acquisitions", 2019), ("Locathah", 2019),
    ("Mordenkainen's Tome", 2018), ("Guildmaster", 2018), ("Xanathar", 2017), ("Tortle", 2017),
    ("One Grung", 2017), ("Plane Shift", 2017), ("Volo", 2016), ("Sword Coast", 2015),
    ("Elemental Evil", 2015), ("Player's Handbook (2014)", 2014), ("Dungeon Master's Guide (2014)", 2014),
]


def source_year(source: str) -> int:
    for needle, year in _SOURCE_YEAR:
        if needle.lower() in (source or "").lower():
            return year
    return 0


def display_name(name: str) -> str:
    """The name without its version suffix; a trailing "*" (modified official spell) is kept."""
    star = "*" if (name or "").endswith("*") else ""
    return strip_legacy_suffix((name or "").rstrip("*")) + star


def version_label(item) -> str:
    """How a version is named in the drop-down: its source, flagged when legacy / unofficial."""
    text = getattr(item, "source", "") or "Unknown source"
    if getattr(item, "is_official", True) is False:
        text += " (Unofficial)"
    if getattr(item, "is_legacy", False):
        text += " [Legacy]"
    return text


def visible_in(versions: List[T], legacy_filter: str, is_legacy: Callable[[T], bool]) -> List[T]:
    """The versions of one entry that the Legacy content setting lets through.

    show_all        every version
    no_legacy       the 2024 version
    legacy_only     the 2014 versions
    show_unupdated  the 2024 version if there is one, else the 2014 versions
    """
    if legacy_filter == "no_legacy":
        return [v for v in versions if not is_legacy(v)]
    if legacy_filter == "legacy_only":
        return [v for v in versions if is_legacy(v)]
    if legacy_filter == "show_unupdated":
        current = [v for v in versions if not is_legacy(v)]
        return current or list(versions)
    return list(versions)


def collapse_search_results(results: List[dict]) -> List[dict]:
    """Global-search hits with the versions of one thing merged into a single hit.

    ``results`` are {"name", "section", ...} dicts. "Fireball" and "Fireball (Legacy)" become one hit
    (the current version's name is kept for navigating; the list shows the plain name under "label").
    Subclass hits are left alone: their names carry the class they belong to.
    """
    out: List[dict] = []
    where: Dict[tuple, int] = {}
    for hit in results:
        hit = dict(hit)
        if hit.get("section") == "Subclasses":
            hit["label"] = hit["name"]
            out.append(hit)
            continue
        key = (hit.get("section"), legacy_pair_key(hit["name"]))
        if key in where:
            kept = out[where[key]]
            if strip_legacy_suffix(kept["name"]) != kept["name"] and strip_legacy_suffix(hit["name"]) == hit["name"]:
                hit["label"] = display_name(hit["name"])
                out[where[key]] = hit            # prefer the version that has the plain name
            continue
        hit["label"] = display_name(hit["name"])
        where[key] = len(out)
        out.append(hit)
    return out


class VersionCatalog:
    """All the items of one kind, grouped into entries that have several versions."""

    def __init__(self, items: Iterable[T],
                 name: Callable[[T], str] = lambda i: i.name,
                 is_legacy: Callable[[T], bool] = lambda i: bool(i.is_legacy),
                 source: Callable[[T], str] = lambda i: i.source or ""):
        self._name, self._is_legacy, self._source = name, is_legacy, source
        self._groups: Dict[str, List[T]] = {}
        self._order: Dict[str, int] = {}
        for index, item in enumerate(items):
            self._order[self._ident(item)] = index
            self._groups.setdefault(legacy_pair_key(name(item)), []).append(item)
        for group in self._groups.values():
            group.sort(key=self._sort_key)

    def _ident(self, item) -> str:
        # Items are told apart by name (unique per kind), so an equal copy of an item - a spell freshly
        # read from the database, say - counts as the same item
        return self._name(item).lower()

    def _sort_key(self, item):
        # 2024 first, then 2014 printings newest to oldest; ties keep the order the items came in
        return (self._is_legacy(item), -source_year(self._source(item)), self._order.get(self._ident(item), 0))

    # ----------------------------------------------------------------- lookups

    def key(self, item) -> str:
        return legacy_pair_key(self._name(item))

    def versions(self, item) -> List[T]:
        """Every version of this item's entry, in drop-down order (includes the item itself)."""
        return list(self._groups.get(self.key(item), [item]))

    def options(self, item, legacy_filter: str = "show_all") -> List[T]:
        """The versions to offer in the drop-down: what the setting allows, and always ``item`` itself."""
        shown = visible_in(self.versions(item), legacy_filter, self._is_legacy)
        if not any(self._ident(v) == self._ident(item) for v in shown):
            shown.append(item)
            shown.sort(key=self._sort_key)
        return shown

    def find(self, name: str) -> Optional[T]:
        """The item stored under exactly this (case-insensitive) name."""
        wanted = (name or "").strip().lower()
        for group in self._groups.values():
            for item in group:
                if self._name(item).lower() == wanted:
                    return item
        return None

    def same_entry(self, a, b) -> bool:
        return self.key(a) == self.key(b)

    # ---------------------------------------------------------------- the list

    def collapse(self, matches: Iterable[T], legacy_filter: str = "show_all") -> List[T]:
        """One item per entry for a list: the default version among those that matched.

        ``matches`` is whatever passed the search/filters (every version, not yet narrowed by the
        Legacy setting). An entry is listed when at least one version the setting allows matched;
        the first allowed one (2024 before 2014, newest 2014 printing first) represents it.
        """
        matches = list(matches)
        matched = {self._ident(m): m for m in matches}
        out, seen = [], set()
        for item in matches:
            key = self.key(item)
            if key in seen:
                continue
            seen.add(key)
            allowed = visible_in(self.versions(item), legacy_filter, self._is_legacy)
            rep = next((matched[self._ident(v)] for v in allowed if self._ident(v) in matched), None)
            if rep is not None:
                out.append(rep)
        return out
