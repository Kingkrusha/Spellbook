"""
What the Homebrew Studio knows about the rest of the collection, without any UI.

* the similarity index (built on a worker thread, rebuilt when the collections change),
* a list of every openable object for the reference panels' search boxes,
* ``analyze()``: everything the Insights panel shows for a draft - the entries it resembles, the checks (name
  already used, links to content that is not installed) and, for a monster, the CR report.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import homebrew_index as HI
from homebrew_index import Entry, Match, Unit
from studio_store import StudioStore, object_to_record

# link category -> the index family it belongs to
CATEGORY_FAMILY = {"spell": "spells", "feat": "feats", "class": "class_features", "subclass": "class_features",
                   "lineage": "lineages", "background": "backgrounds", "magic_item": "magic_items",
                   "equipment": "equipment", "monster": "monsters", "rule": "rules"}


@dataclass
class Hit:
    """A search result in a reference panel: a whole object, or one feature inside one."""
    title: str
    detail: str
    family: str
    category: str                 # object-link category of the owner
    name: str                     # what to open (``Page#Section`` for rules)
    entry: Optional[Entry] = None  # set when it is one feature of the owner
    section: str = ""


@dataclass
class Strictness:
    """How readily the Insights call something similar (the Settings page and the Insights panel set these)."""
    min_words: int = 1                 # words in common an insight needs
    max_matches: int = 0               # a part of the draft with more matches than this is standard wording (0 = no limit)
    hide_exact: bool = False           # leave out content whose text is exactly the draft's
    include_unofficial: bool = True    # compare with content that is not tagged official too
    min_score: float = 14.0            # how alike (0-100) it has to read; the Studio uses 30, which drops chance overlaps

    @classmethod
    def from_settings(cls, include_unofficial: Optional[bool] = None) -> "Strictness":
        try:
            from settings import get_settings_manager
            st = get_settings_manager().settings
        except Exception:
            return cls(4, 10, True, False if include_unofficial is None else include_unofficial, 30.0)
        return cls(min_words=max(1, int(getattr(st, "studio_min_words", 4) or 1)),
                   max_matches=max(0, int(getattr(st, "studio_max_matches", 10) or 0)),
                   hide_exact=bool(getattr(st, "studio_hide_exact", True)),
                   include_unofficial=(bool(getattr(st, "studio_include_unofficial", False))
                                       if include_unofficial is None else include_unofficial),
                   min_score=30.0)


@dataclass
class DraftAnalysis:
    units: List[Unit] = field(default_factory=list)
    omitted: List[Tuple[str, int]] = field(default_factory=list)    # parts left out as standard wording
    matches: List[Match] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)          # worth fixing before publishing
    cr: Optional[object] = None                                 # monster_cr.Report
    closest: List[Tuple[object, dict]] = field(default_factory=list)       # monsters with the nearest numbers
    token: int = 0


# --------------------------------------------------------------------------- what a draft says

def _join(*parts: str) -> str:
    return "\n".join(p for p in parts if p and p.strip())


def _props(obj) -> str:
    return "\n".join(f"{p.get('name', '')}: {p.get('description', '')}" for p in (getattr(obj, "properties", None) or [])
                     if isinstance(p, dict))


def units_for(kind: str, obj) -> List[Unit]:
    """The parts of a draft worth comparing one by one."""
    name = getattr(obj, "name", "") or ""
    units: List[Unit] = []
    if kind in ("spells", "feats"):
        units.append(Unit(name, obj.description))
    elif kind in ("magic_items", "equipment"):
        units.append(Unit(name, _join(obj.description, _props(obj))))
    elif kind == "lineages":
        for t in obj.traits:
            units.append(Unit(t.name, t.description))
        if len(HI.plain(obj.description)) > 60:
            units.append(Unit(name, obj.description))
    elif kind == "backgrounds":
        for f in obj.features:
            units.append(Unit(f.name, f.description))
        if len(HI.plain(obj.description)) > 60:
            units.append(Unit(name, obj.description))
    elif kind == "classes":
        from character_class import STANDARD_FEATURES
        for level in sorted(obj.levels):
            for ab in obj.levels[level].abilities:
                if not ab.is_subclass_feature and (ab.title, ab.description) not in STANDARD_FEATURES:
                    units.append(Unit(ab.title, ab.description))
    elif kind == "subclasses":
        for f in obj.features:
            units.append(Unit(f.title, f.description))
    elif kind == "monsters":
        for attr in ("traits", "actions", "bonus_actions", "reactions", "legendary_actions", "lair_actions"):
            for f in getattr(obj, attr, None) or []:
                units.append(Unit(f.name, HI.strip_attack_formula(f.description)))
    elif kind == "rules":
        units.append(Unit(name, obj.description))
    return [u for u in units if len(HI.plain(u.text)) >= 12]


def comparison_text(units: Sequence[Unit]) -> str:
    return "\n".join(f"{u.title}\n{u.text}" for u in units)


# --------------------------------------------------------------------------- the service

class StudioService:
    """Drafts, the similarity index and the lookups the Studio's panels need."""

    def __init__(self, spell_manager=None, store: Optional[StudioStore] = None):
        self.spell_manager = spell_manager
        self.store = store or StudioStore()
        self.index: HI.HomebrewIndex = HI.HomebrewIndex()
        self._dirty = True
        self._targets: List = []
        self._target_map: Dict[Tuple[str, str], object] = {}
        self._building = False
        self._error = ""
        self._token = 0
        self._lock = threading.Lock()

    # ---- the index

    @property
    def ready(self) -> bool:
        return self.index.ready and bool(self._targets)

    @property
    def building(self) -> bool:
        return self._building

    def is_stale(self) -> bool:
        return self._dirty or not self.index.ready or self.index.is_stale(self.spell_manager)

    def invalidate(self) -> None:
        """Content changed (a draft was published, a file imported): the next ``ensure_index`` rebuilds."""
        self._dirty = True

    def ensure_index(self, on_done: Optional[Callable[[], None]] = None, wait: bool = False) -> bool:
        """Start building the index if it is missing or out of date. Returns True if it is usable right now
        (an out-of-date index stays usable while the new one is built)."""
        if not self.is_stale():
            if on_done:
                on_done()
            return True
        with self._lock:
            if self._building:
                return self.ready
            self._building = True

        def work():
            try:
                fresh = HI.HomebrewIndex().build(self.spell_manager)
                from object_links import get_link_targets
                targets = get_link_targets(enabled_only=False)
                self._targets = targets
                self._target_map = {(t.category, t.name.lower()): t for t in targets}
                self.index = fresh
                self._dirty = False
                self._error = ""
            except Exception as e:                     # shown in the panel instead of failing silently
                self._error = str(e)
                print(f"Studio: could not build the index: {e}")
            finally:
                self._building = False

        if wait:
            work()
            if on_done:
                on_done()
            return self.ready
        threading.Thread(target=work, daemon=True, name="studio-index").start()
        return self.ready

    @property
    def error(self) -> str:
        return self._error

    # ---- searching for something to open

    def target(self, category: str, name: str):
        """The link target for an object (cached; falls back to a full lookup)."""
        found = self._target_map.get((category, name.strip().lower()))
        if found is not None:
            return found
        from object_links import find_target
        return find_target(category, name)

    def search(self, query: str, families: Optional[Iterable[str]] = None, limit: int = 14) -> List[Hit]:
        """Objects and features whose name matches ``query``, objects first."""
        q = (query or "").strip()
        if not q:
            return []
        wanted = set(families) if families else None
        from object_links import search_links
        hits: List[Hit] = []
        seen: Set[Tuple[str, str]] = set()
        targets = [t for t in self._targets if wanted is None or CATEGORY_FAMILY.get(t.category) in wanted]
        for t in search_links(q, targets, limit=limit):
            hits.append(Hit(t.label, t.subtitle or t.category_label, CATEGORY_FAMILY.get(t.category, ""),
                            t.category, t.name))
            seen.add((t.category, t.name.lower()))
        index = self.index
        if index.ready and len(hits) < limit:
            for e in index.find_title(q, wanted, limit=limit * 2):
                key = (e.category, e.target.lower())
                whole = e.title.lower() == e.owner.lower()
                if key in seen or (whole and (e.category, e.owner.lower()) in seen):
                    continue
                seen.add(key)
                hits.append(Hit(e.title, e.detail, e.family, e.category, e.target, entry=e, section=e.section))
                if len(hits) >= limit:
                    break
        return hits[:limit]

    # ---- looking at a draft

    def exclusion(self, kind: str, name: str) -> Callable[[Entry], bool]:
        """Entries that are the draft itself (a copy already published under the same name)."""
        low = (name or "").strip().lower()
        family = HI.KIND_FAMILY.get(kind, "")

        def exclude(e: Entry) -> bool:
            return bool(low) and e.family == family and e.owner.lower() == low and e.custom
        return exclude

    def analyze(self, kind: str, obj, record: dict, *, families: Optional[Iterable[str]] = None,
                include_legacy: bool = True, token: int = 0, compare_to: Optional[str] = None,
                strict: Optional[Strictness] = None) -> DraftAnalysis:
        """Everything the Insights panel shows. Safe to call from a worker thread."""
        out = DraftAnalysis(token=token)
        out.units = units_for(kind, obj)
        name = getattr(obj, "name", "") or ""
        index = self.index
        if index.ready and out.units:
            strict = strict or Strictness()
            found = index.similar_to_draft(
                out.units, families=families, exclude=self.exclusion(kind, name), limit=14,
                include_legacy=include_legacy, min_words=strict.min_words, hide_exact=strict.hide_exact,
                include_unofficial=strict.include_unofficial, max_matches=strict.max_matches,
                min_score=strict.min_score)
            out.matches, out.omitted = list(found), list(found.omitted)
        out.problems = self.checks(kind, name, record)
        if kind == "monsters":
            try:
                import monster_cr
                from monster import get_monster_manager
                lookup = self.spell_manager.get_spell if self.spell_manager is not None else (lambda n: None)
                monsters = get_monster_manager().monsters
                ref = monster_cr.collection_reference(monsters, lookup)
                out.cr = monster_cr.analyze(obj, compare_to=compare_to, reference=ref, spell_lookup=lookup)
                out.closest = monster_cr.closest(obj, ref, lookup, exclude=name)
            except Exception as e:
                print(f"Studio: CR check failed: {e}")
        return out

    def checks(self, kind: str, name: str, record: dict) -> List[str]:
        """Things to fix before this goes into the collection."""
        import content_io
        problems: List[str] = []
        name = (name or "").strip()
        if not name:
            problems.append("The draft has no name yet.")
        else:
            try:
                existing = content_io._existing(kind, name, self.spell_manager)
            except Exception:
                existing = None
            if existing is not None:
                if content_io._is_official(existing):
                    problems.append(f"'{name}' is the name of official content, so publishing would be skipped. "
                                    f"Choose another name.")
                else:
                    problems.append(f"You already have {content_io.singular(kind).lower()} called '{name}': "
                                    f"publishing will replace it.")
        try:
            missing = content_io.dangling_links(record)
        except Exception:
            missing = []
        if missing:
            problems.append("Links to content that is not installed: " + content_io.format_dangling(missing))
        return problems
