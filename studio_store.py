"""
Drafts for the Homebrew Studio.

A draft is a piece of homebrew that is still being written. It lives in ``studio.json`` in the user-data folder
(never in the collections), as a record in the same shape the import / export files use, so publishing a draft is
just importing that record. Nothing here touches the UI.

``studio.json``::

    {"version": 1, "drafts": [{"id", "kind", "name", "record", "created", "updated", "published_as", "parent"}],
     "panels": [{"category", "name", "section"}], "last_draft": "<id>"}
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from atomic_io import atomic_write_json
from paths import user_data_path

FILE_NAME = "studio.json"
VERSION = 1

# the kinds the Studio can write: content_io key -> (singular label, hint for a blank draft's name)
KINDS: Dict[str, str] = {
    "spells": "Spell",
    "feats": "Feat",
    "classes": "Class",
    "subclasses": "Subclass",
    "lineages": "Lineage",
    "backgrounds": "Background",
    "equipment": "Equipment",
    "magic_items": "Magic item",
    "monsters": "Monster",
    "rules": "Rules page",
}

KIND_ICONS = {"spells": "📜", "feats": "⚔️", "classes": "🎭", "subclasses": "🎭", "lineages": "🧬",
              "backgrounds": "📖", "equipment": "🛡️", "magic_items": "✨", "monsters": "👹", "rules": "📚"}


@dataclass
class Draft:
    id: str
    kind: str
    name: str
    record: dict = field(default_factory=dict)         # content_io record; empty for a blank draft
    created: float = 0.0
    updated: float = 0.0
    published_as: str = ""                             # the name it has in the collection once published
    parent: str = ""                                   # subclasses: the class they belong to

    def title(self) -> str:
        return self.name or f"Untitled {KINDS.get(self.kind, self.kind).lower()}"

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "name": self.name, "record": self.record, "created": self.created,
                "updated": self.updated, "published_as": self.published_as, "parent": self.parent}

    @classmethod
    def from_dict(cls, data: dict) -> "Draft":
        return cls(id=str(data.get("id") or uuid.uuid4().hex[:10]), kind=str(data.get("kind", "")),
                   name=str(data.get("name", "")), record=dict(data.get("record") or {}),
                   created=float(data.get("created") or 0), updated=float(data.get("updated") or 0),
                   published_as=str(data.get("published_as", "")), parent=str(data.get("parent", "")))


# --------------------------------------------------------------------------- objects <-> records

_SPELL_DEFAULTS = {"level": 0, "casting_time": "Action", "range_value": 0, "components": "",
                   "duration": "Instantaneous", "description": ""}


def object_to_record(kind: str, obj, spell_manager=None) -> dict:
    """The content_io record for an object an editor produced."""
    if kind == "spells":
        if spell_manager is not None:
            return spell_manager._spell_to_dict(obj)
        from spell_manager import SpellManager
        return SpellManager._spell_to_dict(None, obj)       # a pure function of the spell
    return obj.to_dict()


def record_to_object(kind: str, record: dict, spell_manager=None):
    """The object an editor shows for a record."""
    if kind == "spells":
        rec = dict(_SPELL_DEFAULTS)
        rec.update(record)
        rec.setdefault("name", "")
        if spell_manager is not None:
            return spell_manager._dict_to_spell(rec)
        from spell_manager import SpellManager
        return SpellManager._dict_to_spell(None, rec)
    if kind == "classes":
        from character_class import CharacterClassDefinition
        return CharacterClassDefinition.from_dict(record)
    if kind == "subclasses":
        from character_class import SubclassDefinition
        return SubclassDefinition.from_dict(record)
    import importlib
    module, cls_name = {
        "feats": ("feat", "Feat"), "lineages": ("lineage", "Lineage"), "backgrounds": ("background", "Background"),
        "equipment": ("equipment", "Equipment"), "magic_items": ("magic_item", "MagicItem"),
        "monsters": ("monster", "Monster"), "rules": ("rules", "RulePage"),
    }[kind]
    return getattr(importlib.import_module(module), cls_name).from_dict(record)


def blank_name(kind: str, drafts: List[Draft]) -> str:
    """A name for a new draft that no other draft of the kind uses."""
    base = f"New {KINDS.get(kind, kind).lower()}"
    taken = {d.name.lower() for d in drafts if d.kind == kind}
    if base.lower() not in taken:
        return base
    n = 2
    while f"{base} {n}".lower() in taken:
        n += 1
    return f"{base} {n}"


# --------------------------------------------------------------------------- the store

class StudioStore:
    """All drafts, kept on disk."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or user_data_path(FILE_NAME)
        self.drafts: List[Draft] = []
        self.panels: List[dict] = []
        self.last_draft: str = ""
        self.load()

    # ---- persistence

    def load(self) -> None:
        import json
        import os
        self.drafts, self.panels, self.last_draft = [], [], ""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print(f"Studio: could not read {self.path}: {e}")
            return
        if not isinstance(data, dict):
            return
        for raw in data.get("drafts") or []:
            if isinstance(raw, dict) and raw.get("kind") in KINDS:
                self.drafts.append(Draft.from_dict(raw))
        self.panels = [p for p in (data.get("panels") or []) if isinstance(p, dict)]
        self.last_draft = str(data.get("last_draft") or "")

    def save(self) -> bool:
        data = {"version": VERSION, "drafts": [d.to_dict() for d in self.drafts], "panels": self.panels,
                "last_draft": self.last_draft}
        try:
            atomic_write_json(self.path, data, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Studio: could not save {self.path}: {e}")
            return False

    # ---- drafts

    def get(self, draft_id: str) -> Optional[Draft]:
        return next((d for d in self.drafts if d.id == draft_id), None)

    def new(self, kind: str, name: str = "", record: Optional[dict] = None, parent: str = "") -> Draft:
        now = time.time()
        draft = Draft(id=uuid.uuid4().hex[:10], kind=kind, name=name, record=dict(record or {}),
                      created=now, updated=now, parent=parent)
        self.drafts.append(draft)
        self.last_draft = draft.id
        return draft

    def update(self, draft: Draft, name: str, record: dict) -> bool:
        """Store a new version of a draft; returns True if anything changed."""
        if draft.name == name and draft.record == record:
            return False
        draft.name, draft.record, draft.updated = name, record, time.time()
        return True

    def delete(self, draft_id: str) -> None:
        self.drafts = [d for d in self.drafts if d.id != draft_id]
        if self.last_draft == draft_id:
            self.last_draft = self.drafts[-1].id if self.drafts else ""

    def duplicate(self, draft: Draft) -> Draft:
        import copy
        name = f"{draft.name} (copy)" if draft.name else ""
        return self.new(draft.kind, name, copy.deepcopy(draft.record), draft.parent)

    def sorted(self) -> List[Draft]:
        return sorted(self.drafts, key=lambda d: -d.updated)


# --------------------------------------------------------------------------- publishing

def publish(draft: Draft, spell_manager=None, link_mentions: bool = True):
    """Add the draft to the real collection (the same path as importing a file). Returns the ImportReport.

    An official entry of the same name is never replaced; one of the user's own is updated."""
    import content_io
    record = dict(draft.record)
    record["name"] = draft.name
    bundle = {draft.kind: [record]}
    report = content_io.import_bundle(bundle, spell_manager, link_mentions=link_mentions)
    if report.imported:
        draft.published_as = draft.name
    return report


def clash(draft: Draft, spell_manager=None) -> Tuple[str, str]:
    """('official' | 'custom' | '', name): whether the draft's name is already taken in the collection."""
    import content_io
    if not draft.name.strip():
        return "", ""
    try:
        existing = content_io._existing(draft.kind, draft.name.strip(), spell_manager)
    except Exception:
        return "", ""
    if existing is None:
        return "", ""
    return ("official" if content_io._is_official(existing) else "custom"), draft.name.strip()
