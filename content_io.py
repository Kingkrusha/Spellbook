"""
One import/export path for user (unofficial) content.

Every content kind the app stores - spells, feats, lineages, backgrounds,
classes, subclasses, equipment and magic items - goes through the functions
here, so the Import/Export dialogs, the single-spell export and the managers'
``import_from_json`` helpers all behave the same way.

File format
-----------
A UTF-8 JSON object. The header is optional (older exports and the bundled
``*.json`` sources have none); each content kind is a list under its own key::

    {"format": "spellbook-content", "version": 1, "exported_at": "...",
     "spells": [...], "feats": [...], "lineages": [...], "backgrounds": [...],
     "classes": [...], "subclasses": [...], "equipment": [...], "magic_items": [...]}

Classes may also be a ``{"Name": {...}}`` dict (what ``classes.json`` and the
old per-manager export used). Spells may carry a ``stat_blocks`` list (summon
spells). Text fields may contain ``[[category:Name|shown]]`` object links; they
travel with the content untouched and resolve by name on the importing side.

Rules
-----
* Imported content is always custom/unofficial.
* An import never overwrites official content: a record whose name is already
  taken by an official one is skipped and reported. A record that matches an
  earlier *custom* import is updated, so re-importing a file is safe.
* Optionally (default on) plain mentions of other objects in the imported text
  are linked with the same conservative sweep the bundled content uses
  (object_link_sweep), including links between the records of the file itself.
* Afterwards the report lists references that point at things which are not
  installed (spells missing from a subclass list, links to absent objects, ...).
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

FORMAT_NAME = "spellbook-content"
FORMAT_VERSION = 1

# json key -> label. The order is the import order: classes first (so custom
# class names exist when spells and subclasses refer to them), spells before
# the things that reference spells.
KINDS: "OrderedDict[str, str]" = OrderedDict([
    ("classes", "Classes"),
    ("subclasses", "Subclasses"),
    ("spells", "Spells"),
    ("feats", "Feats"),
    ("lineages", "Lineages"),
    ("backgrounds", "Backgrounds"),
    ("equipment", "Equipment"),
    ("magic_items", "Magic Items"),
])

# Order shown to users (dialogs, summaries).
DISPLAY_ORDER = ["spells", "feats", "classes", "subclasses", "lineages",
                 "backgrounds", "equipment", "magic_items"]

# sweep category used for each kind (object_link_sweep / object_links)
_LINK_CATEGORY = {
    "spells": "spell", "feats": "feat", "lineages": "lineage",
    "backgrounds": "background", "classes": "class", "subclasses": "subclass",
    "equipment": "equipment", "magic_items": "magic_item",
}

ProgressFn = Callable[[str, float], None]


def label(kind: str) -> str:
    return KINDS.get(kind, kind.replace("_", " ").title())


_SINGULAR = {
    "spells": "Spell", "feats": "Feat", "lineages": "Lineage", "backgrounds": "Background",
    "classes": "Class", "subclasses": "Subclass", "equipment": "Equipment item",
    "magic_items": "Magic item",
}


def singular(kind: str) -> str:
    return _SINGULAR.get(kind, label(kind))


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class ImportReport:
    added: Counter = field(default_factory=Counter)
    updated: Counter = field(default_factory=Counter)
    skipped: List[Tuple[str, str, str]] = field(default_factory=list)   # (kind, name, why)
    failed: List[Tuple[str, str, str]] = field(default_factory=list)    # (kind, name, error)
    warnings: List[str] = field(default_factory=list)
    links_added: int = 0
    # records whose [[links]] still have to be checked (see finalize_link_check)
    pending_links: List[Tuple[str, dict]] = field(default_factory=list)

    @property
    def imported(self) -> int:
        return sum(self.added.values()) + sum(self.updated.values())

    def merge(self, other: "ImportReport") -> "ImportReport":
        self.added.update(other.added)
        self.updated.update(other.updated)
        self.skipped += other.skipped
        self.failed += other.failed
        self.warnings += [w for w in other.warnings if w not in self.warnings]
        self.links_added += other.links_added
        self.pending_links += other.pending_links
        return self

    def summary_lines(self) -> List[str]:
        lines = []
        for kind in DISPLAY_ORDER:
            a, u = self.added.get(kind, 0), self.updated.get(kind, 0)
            if a or u:
                bit = f"{a} new" if a and not u else (f"{u} updated" if u and not a else f"{a} new, {u} updated")
                lines.append(f"{label(kind)}: {bit}")
        if self.links_added:
            lines.append(f"{self.links_added} mention(s) linked to other content")
        return lines

    def problem_lines(self, limit: int = 12) -> List[str]:
        out: List[str] = []
        if self.skipped:
            official = [s for s in self.skipped if s[2] == "official"]
            other = [s for s in self.skipped if s[2] != "official"]
            if official:
                names = ", ".join(f"{n}" for _, n, _ in official[:6])
                more = f" and {len(official) - 6} more" if len(official) > 6 else ""
                out.append(f"Skipped {len(official)} entr{'y' if len(official) == 1 else 'ies'} "
                           f"whose name is already used by official content: {names}{more}")
            for kind, name, why in other[:limit]:
                out.append(f"Skipped {singular(kind).lower()} '{name}': {why}")
        for kind, name, err in self.failed[:limit]:
            out.append(f"Could not import '{name}' ({label(kind)}): {err}")
        if len(self.failed) > limit:
            out.append(f"... and {len(self.failed) - limit} more that could not be imported")
        out.extend(self.warnings)
        return out


# ---------------------------------------------------------------------------
# Manager access
# ---------------------------------------------------------------------------

def _mgr(kind: str):
    if kind == "feats":
        from feat import get_feat_manager
        return get_feat_manager()
    if kind == "lineages":
        from lineage import get_lineage_manager
        return get_lineage_manager()
    if kind == "backgrounds":
        from background import get_background_manager
        return get_background_manager()
    if kind in ("classes", "subclasses"):
        from character_class import get_class_manager
        return get_class_manager()
    if kind == "equipment":
        from equipment import get_equipment_manager
        return get_equipment_manager()
    if kind == "magic_items":
        from magic_item import get_magic_item_manager
        return get_magic_item_manager()
    raise KeyError(kind)


def _is_official(obj: Any) -> bool:
    """True for content that ships with the app (never overwritten by an import)."""
    if hasattr(obj, "is_official") and not hasattr(obj, "is_custom"):
        return bool(obj.is_official)                      # spells
    return bool(getattr(obj, "is_official", True)) and not bool(getattr(obj, "is_custom", False))


def unofficial_objects(kind: str, spell_manager=None) -> list:
    """The user's own (non-official) objects of one kind."""
    if kind == "spells":
        return [s for s in (spell_manager.spells if spell_manager else []) if not s.is_official]
    m = _mgr(kind)
    if kind == "feats":
        return m.get_unofficial_feats()
    if kind == "lineages":
        return m.get_unofficial_lineages()
    if kind == "backgrounds":
        return m.get_unofficial_backgrounds()
    if kind == "classes":
        return m.get_unofficial_classes()
    if kind == "subclasses":
        return m.get_unofficial_subclasses()
    return m.get_unofficial_items()          # equipment, magic_items


def unofficial_sources(kind: Optional[str] = None, spell_manager=None) -> List[str]:
    """Sorted sources of the user's own content (one kind, or all kinds)."""
    kinds = [kind] if kind and kind != "all" else list(DISPLAY_ORDER)
    out = set()
    for k in kinds:
        for obj in unofficial_objects(k, spell_manager):
            src = getattr(obj, "source", "")
            if src:
                out.add(src)
    return sorted(out)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _spell_record(spell, spell_manager) -> dict:
    rec = spell_manager._spell_to_dict(spell)
    try:
        blocks = spell_manager._db.get_stat_blocks_for_spell_by_name(spell.name)
    except Exception:
        blocks = []
    if blocks:
        rec["stat_blocks"] = [{k: v for k, v in b.items() if k not in ("id", "spell_id")} for b in blocks]
    return rec


def _record(kind: str, obj, spell_manager=None) -> dict:
    if kind == "spells":
        return _spell_record(obj, spell_manager)
    return obj.to_dict()


def collect_export(spell_manager=None, kinds: Optional[Iterable[str]] = None,
                   source: Optional[str] = None) -> "OrderedDict[str, list]":
    """The objects an export would contain, by kind (source filter optional)."""
    wanted = [k for k in DISPLAY_ORDER if not kinds or k in set(kinds)]
    out: "OrderedDict[str, list]" = OrderedDict()
    for kind in wanted:
        objs = [o for o in unofficial_objects(kind, spell_manager)
                if not source or getattr(o, "source", "") == source]
        if objs:
            out[kind] = objs
    # Subclasses nested inside an exported custom class travel with the class.
    if "subclasses" in out and "classes" in out:
        nested = {c.name for c in out["classes"]}
        out["subclasses"] = [s for s in out["subclasses"] if s.parent_class not in nested]
        if not out["subclasses"]:
            del out["subclasses"]
    return out


def bundle_of(objects: "Dict[str, list]", spell_manager=None) -> Tuple[dict, "OrderedDict[str, int]"]:
    """Build the JSON-ready file contents (and per-kind counts) for explicit objects."""
    try:
        from version import __version__ as app_version
    except Exception:
        app_version = ""
    data: dict = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "app_version": app_version,
    }
    counts: "OrderedDict[str, int]" = OrderedDict()
    for kind in DISPLAY_ORDER:
        objs = objects.get(kind)
        if objs:
            data[kind] = [_record(kind, o, spell_manager) for o in objs]
            counts[kind] = len(objs)
    return data, counts


def export_bundle(spell_manager=None, kinds: Optional[Iterable[str]] = None,
                  source: Optional[str] = None) -> Tuple[dict, "OrderedDict[str, int]"]:
    """Build the JSON-ready export of the user's own content, and the per-kind counts."""
    return bundle_of(collect_export(spell_manager, kinds, source), spell_manager)


def export_objects(path: str, objects: "Dict[str, list]", spell_manager=None) -> "OrderedDict[str, int]":
    """Write specific objects (e.g. one spell) to an importable file."""
    data, counts = bundle_of(objects, spell_manager)
    if counts:
        write_bundle(path, data)
    return counts


def write_bundle(path: str, data: dict) -> None:
    from atomic_io import atomic_write_json
    atomic_write_json(path, data, ensure_ascii=False)


def export_to_file(path: str, spell_manager=None, kinds: Optional[Iterable[str]] = None,
                   source: Optional[str] = None) -> "OrderedDict[str, int]":
    data, counts = export_bundle(spell_manager, kinds, source)
    if counts:
        write_bundle(path, data)
    return counts


# ---------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------

def load_bundle_file(path: str) -> dict:
    """Read and sanity-check an import file. Raises ValueError with a readable message."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Not a valid JSON file ({e})")
    if not isinstance(data, dict):
        raise ValueError("The file must contain a JSON object with keys such as "
                         "'spells', 'feats' or 'magic_items'.")
    if "character_sheets" in data or "character_spell_lists" in data:
        raise ValueError("This is a character-sheet export. Use 'Char Import' for it.")
    if not any(k in data for k in KINDS):
        raise ValueError("No recognised content found. Expected at least one of: "
                         + ", ".join(DISPLAY_ORDER))
    fmt = data.get("format")
    if fmt not in (None, FORMAT_NAME):
        raise ValueError(f"Unknown file format '{fmt}'.")
    ver = data.get("version")
    if isinstance(ver, int) and ver > FORMAT_VERSION:
        raise ValueError("This file was made by a newer version of Spellbook. Please update the app.")
    return data


def normalize_bundle(data: dict, report: Optional[ImportReport] = None) -> "OrderedDict[str, List[dict]]":
    """{kind: [record dicts]} for every kind present, accepting dict-shaped kinds."""
    out: "OrderedDict[str, List[dict]]" = OrderedDict()
    for kind in KINDS:
        raw = data.get(kind)
        if raw is None:
            continue
        if isinstance(raw, dict):
            recs = []
            for name, val in raw.items():
                if isinstance(val, dict):
                    val = dict(val)
                    val.setdefault("name", name)
                    recs.append(val)
        elif isinstance(raw, list):
            recs = raw
        else:
            if report is not None:
                report.warnings.append(f"'{kind}' should be a list; ignored.")
            continue
        out[kind] = recs
    return out


def count_bundle(data: dict) -> "OrderedDict[str, int]":
    return OrderedDict((k, len(v)) for k, v in normalize_bundle(data).items() if v)


# ---------------------------------------------------------------------------
# Link support
# ---------------------------------------------------------------------------

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _walk_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_strings(v)


def find_links(obj: Any) -> List[Tuple[str, str]]:
    """Every (category, name) object link in any string inside ``obj``."""
    from object_links import parse_link_markup
    found: List[Tuple[str, str]] = []
    for s in _walk_strings(obj):
        if "[[" not in s:
            continue
        for m in _LINK_RE.finditer(s):
            cat, name, _display = parse_link_markup(m.group(1))
            found.append((cat, name))
    return found


def dangling_links(obj: Any, known: Optional[set] = None) -> List[Tuple[str, str]]:
    """Links inside ``obj`` whose target isn't installed (deduplicated, in order)."""
    links = find_links(obj)
    if not links:
        return []
    if known is None:
        from object_links import get_link_targets
        known = {(t.category, t.name.lower()) for t in get_link_targets(enabled_only=False)}
    seen, out = set(), []
    for cat, name in links:
        key = (cat, name.lower())
        if key not in known and key not in seen:
            seen.add(key)
            out.append((cat, name))
    return out


def format_dangling(missing: List[Tuple[str, str]], limit: int = 8) -> str:
    names = ", ".join(f"{n}" for _c, n in missing[:limit])
    more = f" and {len(missing) - limit} more" if len(missing) > limit else ""
    return names + more


def _build_universe(bundle: "OrderedDict[str, List[dict]]", spell_manager=None):
    """Names of everything installed plus everything in the file, for the link sweep."""
    import object_link_sweep as sweep

    names: Dict[str, set] = {c: set() for c in _LINK_CATEGORY.values()}
    if spell_manager is not None:
        names["spell"].update(s.name for s in spell_manager.spells)
    names["feat"].update(f.name for f in _mgr("feats").feats)
    names["lineage"].update(l.name for l in _mgr("lineages").lineages)
    names["background"].update(b.name for b in _mgr("backgrounds").backgrounds)
    cm = _mgr("classes")
    for c in cm.classes:
        names["class"].add(c.name)
        names["subclass"].update(s.name for s in c.subclasses)
    # Mount animals are left out on purpose (see tools/link_sweep.py)
    names["equipment"].update(i.name for i in _mgr("equipment").items if "Mount" not in (i.tags or []))
    names["magic_item"].update(i.name for i in _mgr("magic_items").items)
    for kind, recs in bundle.items():
        cat = _LINK_CATEGORY[kind]
        for r in recs:
            if isinstance(r, dict) and r.get("name"):
                if kind == "equipment" and "Mount" in (r.get("tags") or []):
                    continue
                names[cat].add(str(r["name"]).strip())
        if kind == "classes":
            for r in recs:
                for s in (r.get("subclasses") or []) if isinstance(r, dict) else []:
                    if isinstance(s, dict) and s.get("name"):
                        names["subclass"].add(str(s["name"]).strip())
    return sweep.Universe(names)


def link_record(kind: str, rec: dict, universe) -> int:
    """Link mentions inside one record dict (in place); returns the number of links added."""
    import object_link_sweep as sweep
    changes: list = []
    try:
        if kind == "spells":
            sweep.sweep_spell(rec, universe, changes)
        elif kind == "feats":
            sweep.sweep_feat(rec, universe, changes)
        elif kind == "lineages":
            sweep.sweep_lineage(rec, universe, changes)
        elif kind == "backgrounds":
            sweep.sweep_background(rec, universe, changes)
        elif kind == "equipment":
            sweep.sweep_equipment(rec, universe, changes)
        elif kind == "magic_items":
            sweep.sweep_magic_item(rec, universe, changes)
        elif kind == "subclasses":
            sweep.sweep_subclass(rec, universe, changes)
        elif kind == "classes":
            sweep.sweep_class_levels(rec.get("levels") or {}, rec.get("name", ""), universe, changes)
            for sub in rec.get("subclasses") or []:
                if isinstance(sub, dict):
                    sweep.sweep_subclass(sub, universe, changes)
    except Exception:
        return 0            # linking is a nicety; never let it break an import
    return sum(len(c.get("links", [])) for c in changes)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _clean_name(rec: Any) -> str:
    return str(rec.get("name", "")).strip() if isinstance(rec, dict) else ""


_SIMPLE = {
    # kind: (class import path, getter name on the manager, adder name)
    "feats": ("feat", "Feat", "get_feat", "add_feat"),
    "lineages": ("lineage", "Lineage", "get_lineage", "add_lineage"),
    "backgrounds": ("background", "Background", "get_background", "add_background"),
    "equipment": ("equipment", "Equipment", "get_item", "add_item"),
    "magic_items": ("magic_item", "MagicItem", "get_item", "add_item"),
}


def _import_simple(kind: str, recs: List[dict], report: ImportReport, tick: Callable[[str], None]):
    import importlib
    module, cls_name, getter, adder = _SIMPLE[kind]
    cls = getattr(importlib.import_module(module), cls_name)
    mgr = _mgr(kind)
    for rec in recs:
        name = _clean_name(rec)
        tick(name or "(unnamed)")
        if not name:
            report.failed.append((kind, "(unnamed)", "missing a name"))
            continue
        try:
            obj = cls.from_dict(rec)
        except Exception as e:
            report.failed.append((kind, name, str(e)))
            continue
        existing = getattr(mgr, getter)(name)
        if existing is not None and _is_official(existing):
            report.skipped.append((kind, name, "official"))
            continue
        obj.is_custom = True
        obj.is_official = False
        try:
            getattr(mgr, adder)(obj)
        except Exception as e:
            report.failed.append((kind, name, str(e)))
            continue
        (report.updated if existing is not None else report.added)[kind] += 1


_SPELL_DEFAULTS = {"level": 0, "casting_time": "Action", "range_value": 0,
                   "components": "", "duration": "Instantaneous"}


def _import_spells(recs: List[dict], report: ImportReport, spell_manager, tick):
    if spell_manager is None:
        report.warnings.append("Spells were skipped because the spell list isn't available.")
        return
    to_add, add_names, to_update = [], [], []
    stat_blocks: Dict[str, list] = {}
    for rec in recs:
        name = _clean_name(rec)
        tick(name or "(unnamed)")
        if not name:
            report.failed.append(("spells", "(unnamed)", "missing a name"))
            continue
        rec = dict(rec)
        for k, v in _SPELL_DEFAULTS.items():
            rec.setdefault(k, v)
        try:
            spell = spell_manager._dict_to_spell(rec)
        except Exception as e:
            report.failed.append(("spells", name, str(e)))
            continue
        existing = spell_manager.get_spell(name)
        if existing is not None and existing.is_official:
            report.skipped.append(("spells", name, "official"))
            continue
        tags = [t for t in spell.tags if t != "Official"]
        if "Unofficial" not in tags:
            tags.append("Unofficial")
        spell.tags = tags
        if rec.get("stat_blocks"):
            stat_blocks[name.lower()] = rec["stat_blocks"]
        if existing is not None:
            to_update.append(spell)
        else:
            to_add.append(spell)
            add_names.append(name)

    for spell in to_update:
        try:
            if spell_manager.update_spell(spell.name, spell):
                report.updated["spells"] += 1
            else:
                report.failed.append(("spells", spell.name, "could not update"))
        except Exception as e:
            report.failed.append(("spells", spell.name, str(e)))
    if to_add:
        inserted = spell_manager.bulk_add_spells(to_add)
        report.added["spells"] += inserted
        if inserted < len(to_add):
            for n in add_names:
                if spell_manager.get_spell(n) is None:
                    report.failed.append(("spells", n, "could not be saved"))

    # Summon spells: replace the spell's stat blocks with the file's
    db = spell_manager._db
    for spell in to_add + to_update:
        blocks = stat_blocks.get(spell.name.lower())
        if not blocks:
            continue
        spell_id = db.get_spell_id_by_name(spell.name)
        if spell_id is None:
            continue
        try:
            for old in db.get_stat_blocks_for_spell(spell_id):
                db.delete_stat_block(old["id"])
            for sb in blocks:
                sb = {k: v for k, v in sb.items() if k not in ("id", "spell_id")}
                sb["spell_id"] = spell_id
                if sb.get("name"):
                    db.insert_stat_block(sb)
        except Exception as e:
            report.warnings.append(f"Stat block for '{spell.name}' could not be saved: {e}")


def _import_classes(recs: List[dict], report: ImportReport, tick):
    from character_class import CharacterClassDefinition
    from spell import CharacterClass
    cm = _mgr("classes")
    for rec in recs:
        name = _clean_name(rec)
        tick(name or "(unnamed)")
        if not name:
            report.failed.append(("classes", "(unnamed)", "missing a name"))
            continue
        try:
            cls = CharacterClassDefinition.from_dict(rec)
        except Exception as e:
            report.failed.append(("classes", name, str(e)))
            continue
        existing = cm.get_class(name)
        if existing is not None and _is_official(existing):
            report.skipped.append(("classes", name, "official"))
            continue
        cls.is_custom = True
        had = {s.name.lower() for s in existing.subclasses} if existing is not None else set()
        for sub in cls.subclasses:
            sub.is_custom = True
            sub.parent_class = cls.name
        try:
            cm.add_class(cls)
            CharacterClass.register_custom_class(cls.name)
        except Exception as e:
            report.failed.append(("classes", name, str(e)))
            continue
        (report.updated if existing is not None else report.added)["classes"] += 1
        for sub in cls.subclasses:
            (report.updated if sub.name.lower() in had else report.added)["subclasses"] += 1


def _import_subclasses(recs: List[dict], report: ImportReport, tick):
    from character_class import SubclassDefinition
    cm = _mgr("classes")
    for rec in recs:
        name = _clean_name(rec)
        tick(name or "(unnamed)")
        if not name:
            report.failed.append(("subclasses", "(unnamed)", "missing a name"))
            continue
        try:
            sub = SubclassDefinition.from_dict(rec)
        except Exception as e:
            report.failed.append(("subclasses", name, str(e)))
            continue
        sub.is_custom = True
        try:
            result = cm.save_subclass(sub)
        except Exception as e:
            report.failed.append(("subclasses", name, str(e)))
            continue
        if result == "added":
            report.added["subclasses"] += 1
        elif result == "updated":
            report.updated["subclasses"] += 1
        elif result == "official":
            report.skipped.append(("subclasses", name, "official"))
        elif result == "missing_parent":
            report.skipped.append(("subclasses", name,
                                   f"its class '{sub.parent_class}' isn't installed - import the class first"))


def _reference_warnings(bundle: "OrderedDict[str, List[dict]]", report: ImportReport, spell_manager):
    """Report references to spells / classes that aren't installed."""
    if spell_manager is None:
        return
    known_spells = {s.name.lower() for s in spell_manager.spells}
    seen = set()

    def missing_spell(owner_kind: str, owner: str, spell: str):
        key = (owner_kind, owner, spell.lower())
        if spell and spell.lower() not in known_spells and key not in seen:
            seen.add(key)
            report.warnings.append(f"{singular(owner_kind)} '{owner}' refers to the spell '{spell}', "
                                   f"which isn't installed.")

    for rec in bundle.get("subclasses", []):
        for s in (rec.get("subclass_spells") or []) if isinstance(rec, dict) else []:
            missing_spell("subclasses", _clean_name(rec), s.get("spell_name", "") if isinstance(s, dict) else str(s))
    for rec in bundle.get("classes", []):
        if not isinstance(rec, dict):
            continue
        for sp in rec.get("spell_list") or []:
            missing_spell("classes", _clean_name(rec), str(sp))
        for sub in rec.get("subclasses") or []:
            for s in (sub.get("subclass_spells") or []) if isinstance(sub, dict) else []:
                missing_spell("subclasses", _clean_name(sub), s.get("spell_name", "") if isinstance(s, dict) else str(s))
    for rec in bundle.get("feats", []):
        for sp in (rec.get("set_spells") or []) if isinstance(rec, dict) else []:
            missing_spell("feats", _clean_name(rec), str(sp))

    # A spell whose classes are all unknown stays hidden until one of them is installed.
    try:
        from spell import CharacterClass
        valid = {c.lower() for c in CharacterClass.all_class_names_with_custom()}
        for rec in bundle.get("spells", []):
            classes = [str(c) for c in (rec.get("classes") or [])] if isinstance(rec, dict) else []
            if classes and not any(c.lower() in valid for c in classes):
                report.warnings.append(f"Spell '{_clean_name(rec)}' is only on the spell list of "
                                       f"{', '.join(classes)}, which isn't installed, so it stays hidden "
                                       f"until that class is imported.")
    except Exception:
        pass


def import_bundle(data: dict, spell_manager=None, *, link_mentions: bool = True,
                  kinds: Optional[Iterable[str]] = None,
                  progress: Optional[ProgressFn] = None,
                  defer_link_check: bool = False) -> ImportReport:
    """Import one file's worth of content. Never raises for bad records: they are reported.

    With ``defer_link_check`` the "links to content that isn't installed" check is left for
    ``finalize_link_check`` - use it when importing several files in a row, so a link from
    one file to something in the next isn't reported as missing."""
    report = ImportReport()
    bundle = normalize_bundle(data, report)
    if kinds:
        keep = set(kinds)
        bundle = OrderedDict((k, v) for k, v in bundle.items() if k in keep)
    bundle = OrderedDict((k, [r for r in v]) for k, v in bundle.items())
    total = sum(len(v) for v in bundle.values()) or 1
    done = 0

    def emit(text: str):
        if progress:
            progress(text, min(done / total, 1.0))

    # 1. link mentions (records are copied first: the caller's data isn't modified)
    if link_mentions and bundle:
        emit("Linking mentions...")
        try:
            universe = _build_universe(bundle, spell_manager)
            for kind, recs in bundle.items():
                fresh = []
                for r in recs:
                    if isinstance(r, dict):
                        r = copy.deepcopy(r)
                        report.links_added += link_record(kind, r, universe)
                    fresh.append(r)
                bundle[kind] = fresh
        except Exception as e:                       # pragma: no cover - defensive
            report.warnings.append(f"Mentions could not be linked automatically: {e}")

    # 2. import, kind by kind
    for kind in KINDS:
        recs = bundle.get(kind)
        if not recs:
            continue

        def tick(name: str, _kind=kind):
            nonlocal done
            done += 1
            emit(f"Importing {label(_kind).lower()}: {name}")

        if kind == "classes":
            _import_classes(recs, report, tick)
        elif kind == "subclasses":
            _import_subclasses(recs, report, tick)
        elif kind == "spells":
            _import_spells(recs, report, spell_manager, tick)
        else:
            _import_simple(kind, recs, report, tick)

    # 3. class spell lists refer to spells, so they are applied once spells exist
    if spell_manager is not None:
        for rec in bundle.get("classes", []):
            if isinstance(rec, dict) and rec.get("spell_list"):
                try:
                    spell_manager._db.add_class_to_spells(_clean_name(rec), [str(s) for s in rec["spell_list"]])
                except Exception as e:
                    report.warnings.append(f"Spell list of class '{_clean_name(rec)}' could not be applied: {e}")
        if bundle.get("classes"):
            try:
                spell_manager.load_spells()
            except Exception:
                pass

    # 4. things the file refers to that aren't installed
    emit("Checking references...")
    _reference_warnings(bundle, report, spell_manager)
    for kind, recs in bundle.items():
        for rec in recs:
            if isinstance(rec, dict) and find_links(rec):
                report.pending_links.append((kind, rec))
    if not defer_link_check:
        finalize_link_check(report)
    if progress:
        progress("Import complete!", 1.0)
    return report


def finalize_link_check(report: ImportReport) -> ImportReport:
    """Warn about object links, in what was imported, whose target is not installed."""
    if not report.pending_links:
        return report
    try:
        from object_links import get_link_targets
        known = {(t.category, t.name.lower()) for t in get_link_targets(enabled_only=False)}
        for kind, rec in report.pending_links:
            missing = dangling_links(rec, known)
            if missing:
                report.warnings.append(f"{singular(kind)} '{_clean_name(rec)}' links to content that "
                                       f"isn't installed: {format_dangling(missing)}")
    except Exception:
        pass
    report.pending_links = []
    return report


def import_file(path: str, spell_manager=None, *, link_mentions: bool = True,
                kinds: Optional[Iterable[str]] = None,
                progress: Optional[ProgressFn] = None,
                defer_link_check: bool = False) -> ImportReport:
    """Read ``path`` and import it. Raises ValueError for an unusable file."""
    return import_bundle(load_bundle_file(path), spell_manager, link_mentions=link_mentions,
                         kinds=kinds, progress=progress, defer_link_check=defer_link_check)
