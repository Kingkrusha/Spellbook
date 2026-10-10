"""Sending characters and homebrew between players (headless: no widgets, no sockets).

A transfer payload is one JSON object::

    {"format": "spellbook-transfer", "version": 1, "kind": "character" | "content",
     "app_version": "...", "characters": {<character_io bundle>}, "content": {<content_io bundle>}}

* ``kind == "character"``: the characters (sheet + spell list + portrait) in ``characters`` and the
  homebrew they depend on in ``content``. Official content never travels - the receiver has it.
* ``kind == "content"``: just a ``content`` bundle (spells, feats, classes, ... the sender picked).

Nothing here is applied on its own. :func:`parse_payload` validates what arrived, :func:`plan_transfer`
says what it would clash with, and :func:`apply_transfer` writes it using the choices the receiving
player made (replace / keep both / skip, per item). Received content goes through the same import
engine as a file (``content_io``), so official content is never overwritten.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import character_io
import content_io

FORMAT = "spellbook-transfer"
VERSION = 1
KIND_CHARACTER, KIND_CONTENT = "character", "content"

MAX_RECORDS = 500                 # homebrew records in one transfer
MAX_CHARACTERS = 20
MAX_CLOSURE_ROUNDS = 8

# [[category:Name]] link categories -> content_io kinds
_CATEGORY_KIND = {cat: kind for kind, cat in content_io._LINK_CATEGORY.items()}


class TransferError(ValueError):
    """The payload can't be used (the message is meant for the person reading it)."""


# ---------------------------------------------------------------------------
# Building a payload (sender)
# ---------------------------------------------------------------------------

def _app_version() -> str:
    try:
        from version import __version__
        return __version__
    except Exception:
        return ""


def _usable(obj) -> bool:
    """True for something worth sending: the user's own object, not an official one or a
    spell-only summon (those travel with their spell)."""
    if obj is None or content_io._is_official(obj):
        return False
    return not getattr(obj, "spell_only", False)


def _record_refs(kind: str, record: dict) -> Iterable[Tuple[str, str]]:
    """(kind, name) of everything a homebrew record refers to: ``[[links]]`` anywhere in its text,
    plus the spells named by class lists, subclass spells and feat grants."""
    for category, name in content_io.find_links(record):
        k = _CATEGORY_KIND.get(category)
        if k:
            yield k, name
    for spell in record.get("spell_list") or []:
        yield "spells", str(spell)
    for s in record.get("subclass_spells") or []:
        yield "spells", str(s.get("spell_name", "") if isinstance(s, dict) else s)
    for spell in record.get("set_spells") or []:
        yield "spells", str(spell)
    for sub in record.get("subclasses") or []:
        if isinstance(sub, dict):
            yield from _record_refs("subclasses", sub)
    if kind == "subclasses" and record.get("parent_class"):
        yield "classes", str(record["parent_class"])


def homebrew_closure(seeds: Iterable[Tuple[str, str]], spell_manager=None
                     ) -> "OrderedDict[str, list]":
    """The user's own objects named by ``seeds`` ((kind, name) pairs) and, recursively, by each
    other. Names that are official, or aren't installed, are simply not included."""
    found: Dict[Tuple[str, str], object] = {}
    queue: List[Tuple[str, str]] = list(seeds)
    rounds = 0
    while queue and rounds < MAX_CLOSURE_ROUNDS * 50:
        rounds += 1
        kind, name = queue.pop()
        name = (name or "").strip()
        key = (kind, name.lower())
        if not name or key in found:
            continue
        try:
            obj = content_io._existing(kind, name, spell_manager)
        except Exception:
            obj = None
        if not _usable(obj):
            found[key] = None
            continue
        found[key] = obj
        try:
            record = content_io._record(kind, obj, spell_manager)
        except Exception:
            continue
        queue.extend(_record_refs(kind, record))
    out: "OrderedDict[str, list]" = OrderedDict()
    for (kind, _), obj in found.items():
        if obj is not None:
            out.setdefault(kind, []).append(obj)
    # a subclass inside an exported custom class travels with the class (as in a normal export)
    if "subclasses" in out and "classes" in out:
        nested = {c.name for c in out["classes"]}
        out["subclasses"] = [s for s in out["subclasses"] if s.parent_class not in nested]
        if not out["subclasses"]:
            del out["subclasses"]
    return out


def character_seeds(character, sheet) -> List[Tuple[str, str]]:
    """Everything by name that a character (spell list + sheet) refers to."""
    seeds: List[Tuple[str, str]] = []
    if character is not None:
        for cl in character.classes:
            seeds.append(("classes", cl.get_class_name()))
            if cl.subclass:
                seeds.append(("subclasses", cl.subclass))
        for spell in (character.known_spells + character.prepared_spells
                      + character.subclass_spells + character.class_feature_spells):
            seeds.append(("spells", spell))
        seeds += [("feats", f) for f in character.feats]
        if character.lineage:
            seeds.append(("lineages", character.lineage))
    if sheet is not None:
        if sheet.background:
            seeds.append(("backgrounds", sheet.background))
        if sheet.race:
            seeds.append(("lineages", sheet.race))
        seeds += [("equipment", i.get("name", "")) for i in sheet.equipment_items if isinstance(i, dict)]
        seeds += [("magic_items", i.get("name", "")) for i in sheet.magic_items if isinstance(i, dict)]
        for category, name in content_io.find_links(sheet.to_dict()):
            if category in _CATEGORY_KIND:
                seeds.append((_CATEGORY_KIND[category], name))
    return seeds


def build_character_payload(names: Iterable[str], character_manager, sheet_manager,
                            spell_manager=None) -> dict:
    """A payload carrying the named characters and the homebrew they use."""
    names = [n for n in names if n]
    data, lists, sheets = character_io.build_export(names, character_manager, sheet_manager)
    if not (lists or sheets):
        raise TransferError("Those characters could not be found.")
    seeds: List[Tuple[str, str]] = []
    for name in names:
        seeds += character_seeds(character_manager.get_character(name), sheet_manager.get_sheet(name))
    objects = homebrew_closure(seeds, spell_manager)
    content, _counts = content_io.bundle_of(objects, spell_manager) if objects else ({}, {})
    payload = {"format": FORMAT, "version": VERSION, "kind": KIND_CHARACTER,
               "app_version": _app_version(), "characters": data}
    if content:
        payload["content"] = content
    return payload


def build_content_payload(objects: Dict[str, list], spell_manager=None) -> dict:
    """A payload carrying explicit homebrew objects (``{kind: [objects]}``, see ``content_io``)."""
    objects = {k: list(v) for k, v in objects.items() if v}
    if not objects:
        raise TransferError("Nothing was selected.")
    content, _counts = content_io.bundle_of(objects, spell_manager)
    return {"format": FORMAT, "version": VERSION, "kind": KIND_CONTENT,
            "app_version": _app_version(), "content": content}


# ---------------------------------------------------------------------------
# Reading a payload (receiver)
# ---------------------------------------------------------------------------

@dataclass
class Parsed:
    kind: str
    app_version: str = ""
    characters: Optional[character_io.CharacterBundle] = None
    content: Optional[dict] = None
    character_names: List[str] = field(default_factory=list)
    content_counts: "OrderedDict[str, int]" = field(default_factory=OrderedDict)
    content_names: Dict[str, List[str]] = field(default_factory=dict)


def parse_payload(payload) -> Parsed:
    """Validate a received payload. Raises :class:`TransferError`; never touches any data."""
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise TransferError("That isn't a Spellbook transfer.")
    if isinstance(payload.get("version"), int) and payload["version"] > VERSION:
        raise TransferError("This was sent from a newer version of Spellbook. Please update the app.")
    kind = payload.get("kind")
    if kind not in (KIND_CHARACTER, KIND_CONTENT):
        raise TransferError("Unknown kind of transfer.")
    parsed = Parsed(kind=kind, app_version=str(payload.get("app_version") or "")[:20])

    if payload.get("characters") is not None:
        try:
            parsed.characters = character_io.parse_bundle(payload["characters"])
        except character_io.CharacterBundleError as e:
            raise TransferError(str(e))
        parsed.character_names = parsed.characters.names
        if len(parsed.character_names) > MAX_CHARACTERS:
            raise TransferError(f"Too many characters in one transfer (limit {MAX_CHARACTERS}).")
    if kind == KIND_CHARACTER and parsed.characters is None:
        raise TransferError("The transfer says it has characters but none came with it.")

    if payload.get("content") is not None:
        try:
            parsed.content = content_io.check_bundle(payload["content"])
        except ValueError as e:
            raise TransferError(str(e))
        bundle = content_io.normalize_bundle(parsed.content)
        total = 0
        for k, recs in bundle.items():
            names = [str(r.get("name", "")).strip() for r in recs if isinstance(r, dict)]
            names = [n for n in names if n]
            if names:
                parsed.content_counts[k] = len(names)
                parsed.content_names[k] = names
                total += len(names)
        if total > MAX_RECORDS:
            raise TransferError(f"Too much content in one transfer (limit {MAX_RECORDS} items).")
    if kind == KIND_CONTENT and not parsed.content_counts:
        raise TransferError("There is no content in this transfer.")
    return parsed


def describe(parsed: Parsed) -> List[str]:
    """Plain-language lines for the inbox."""
    lines: List[str] = []
    if parsed.character_names:
        shown = ", ".join(parsed.character_names[:6])
        more = f" and {len(parsed.character_names) - 6} more" if len(parsed.character_names) > 6 else ""
        n = len(parsed.character_names)
        lines.append(f"{n} character{'s' if n != 1 else ''}: {shown}{more}")
    for kind in content_io.DISPLAY_ORDER:
        names = parsed.content_names.get(kind)
        if names:
            shown = ", ".join(names[:5]) + (f" and {len(names) - 5} more" if len(names) > 5 else "")
            lines.append(f"{content_io.label(kind)} ({len(names)}): {shown}")
    return lines


# ---------------------------------------------------------------------------
# Applying (only after the receiving player has chosen)
# ---------------------------------------------------------------------------

@dataclass
class Managers:
    character_manager: object
    sheet_manager: object
    spell_manager: object = None


@dataclass
class TransferPlan:
    character_conflicts: List[str] = field(default_factory=list)       # characters you already have
    content: Optional[content_io.BundlePreview] = None                 # homebrew clashes / new / official


@dataclass
class TransferResult:
    characters: Optional[character_io.CharacterImportReport] = None
    content: Optional[content_io.ImportReport] = None

    def lines(self) -> List[str]:
        out: List[str] = []
        if self.content is not None:
            out += self.content.summary_lines()
        if self.characters is not None:
            c = self.characters
            if c.sheets or c.spell_lists:
                out.append(f"Characters: {c.sheets} sheet(s), {c.spell_lists} spell list(s)")
            for old, new in c.renamed.items():
                out.append(f"'{old}' was kept as '{new}' because you already have a '{old}'.")
            if c.skipped:
                out.append("Skipped (kept yours): " + ", ".join(c.skipped))
        return out

    def problems(self) -> List[str]:
        out: List[str] = []
        if self.content is not None:
            out += self.content.problem_lines()
        if self.characters is not None:
            out += self.characters.warnings
        return out


def plan_transfer(parsed: Parsed, mgrs: Managers) -> TransferPlan:
    plan = TransferPlan()
    if parsed.characters is not None:
        plan.character_conflicts = character_io.plan_import(
            parsed.characters, mgrs.character_manager, mgrs.sheet_manager).conflicts
    if parsed.content is not None:
        plan.content = content_io.preview_bundle(parsed.content, mgrs.spell_manager)
    return plan


def apply_transfer(parsed: Parsed, mgrs: Managers,
                   content_decisions: Optional[Dict[Tuple[str, str], str]] = None,
                   character_policies: Optional[Dict[str, str]] = None,
                   content_default: Optional[str] = None,
                   character_default: str = character_io.RENAME) -> TransferResult:
    """Write the transfer. Homebrew goes in first so a character's links and spells resolve.

    ``content_default`` is what happens to homebrew whose name you already use when you made no
    explicit choice: *skip* (keep yours) when it arrived with a character - the character then uses
    your version of that name - and *keep both* when it was sent on its own."""
    result = TransferResult()
    if content_default is None:
        content_default = (content_io.CLASH_SKIP if parsed.kind == KIND_CHARACTER
                           else content_io.CLASH_RENAME)
    if parsed.content is not None:
        resolved = content_io.resolve_bundle(parsed.content, content_decisions, default=content_default,
                                             spell_manager=mgrs.spell_manager)
        if any(k in resolved for k in content_io.KINDS):
            result.content = content_io.import_bundle(resolved, mgrs.spell_manager)
    if parsed.characters is not None:
        result.characters = character_io.apply_import(
            parsed.characters, mgrs.character_manager, mgrs.sheet_manager, mgrs.spell_manager,
            policies=character_policies, default_policy=character_default)
    return result
