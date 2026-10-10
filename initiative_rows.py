"""What the tracker table draws: one :class:`Row` per line, built from a projected view.

Both the DM's view (full entries, from ``project(state, DM)``) and a player's view (filtered entries)
are turned into the same ``Row`` objects, so one table widget serves both. No widgets in here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import conditions as C


@dataclass
class Row:
    id: str
    kind: str
    name: str
    initiative: Optional[int] = None
    group: str = ""                       # opaque id; "" when not grouped
    group_name: str = ""
    group_index: int = -1                 # 0, 1, 2... by order of appearance (for colouring)
    first_in_group: bool = False
    last_in_group: bool = False
    hidden: bool = False
    defeated: bool = False
    mine: bool = False                    # a player's own entry
    can_edit: bool = False                # may this viewer change HP / AC / conditions?
    active: bool = False
    conditions: List[dict] = field(default_factory=list)
    hp_mode: str = "number"               # number | bar | hidden
    hp: int = 0
    hp_max: int = 0
    hp_temp: int = 0
    hp_frac: Optional[float] = None       # 0..1 when a bar can be drawn
    ac: Optional[int] = None              # None = not shown to this viewer
    notes: str = ""
    source: Dict[str, str] = field(default_factory=dict)
    owner: str = ""
    hp_override: Optional[str] = None     # the DM's per-entry HP visibility override
    ac_override: Optional[str] = None

    @property
    def is_event(self) -> bool:
        return self.kind == "event"

    @property
    def condition_text(self) -> str:
        return ", ".join(C.label(c) for c in self.conditions)


@dataclass
class TableView:
    rows: List[Row]
    role: str                             # "dm" | "player"
    started: bool = False
    round: int = 0
    active_id: str = ""
    can_add: bool = False                 # players: may add their own character
    settings: dict = field(default_factory=dict)
    stored_order: List[str] = field(default_factory=list)   # DM only: ids in stored (non-rotated) order
    rotated: bool = False                 # DM only: is the display currently rotated from stored order?
    my_count: int = 0


def build(view: dict) -> TableView:
    """Turn ``project(...)`` output into rows."""
    role = view.get("role", "player")
    entries = view.get("entries") or []
    active = view.get("active") or ""
    group_names = view.get("group_names") or {}
    rows: List[Row] = []
    order: Dict[str, int] = {}

    for i, e in enumerate(entries):
        r = Row(id=e["id"], kind=e.get("kind", "custom"), name=e.get("name", ""),
                initiative=e.get("initiative"), defeated=bool(e.get("defeated")),
                conditions=list(e.get("conditions") or []), active=(e["id"] == active))
        g = e.get("group") or ""
        if g:
            r.group = g
            r.group_name = group_names.get(g, "")
            if g not in order:
                order[g] = len(order)
            r.group_index = order[g]
        if role == "dm":
            r.hidden = bool(e.get("hidden"))
            r.can_edit = not r.is_event
            r.mine = False
            r.hp, r.hp_max, r.hp_temp = int(e.get("hp", 0)), int(e.get("hp_max", 0)), int(e.get("hp_temp", 0))
            r.hp_mode = "number" if not r.is_event else "hidden"
            r.hp_frac = (r.hp / r.hp_max) if r.hp_max > 0 else 0.0
            r.ac = None if r.is_event else int(e.get("ac", 10))
            r.notes = e.get("notes", "")
            r.source = dict(e.get("source") or {})
            r.owner = e.get("owner", "")
            r.hp_override = e.get("hp_mode")
            r.ac_override = e.get("ac_mode")
        else:
            r.mine = bool(e.get("mine"))
            r.hidden = bool(e.get("hidden"))          # only ever true for the viewer's own hidden entry
            r.can_edit = r.mine and not r.is_event
            r.hp_mode = e.get("hp_mode", "hidden") if not r.is_event else "hidden"
            if r.hp_mode == "number":
                r.hp, r.hp_max, r.hp_temp = e.get("hp", 0), e.get("hp_max", 0), e.get("hp_temp", 0)
                r.hp_frac = (r.hp / r.hp_max) if r.hp_max > 0 else 0.0
            elif r.hp_mode == "bar":
                r.hp_frac = e.get("hp_frac")
            r.ac = e.get("ac")
        rows.append(r)

    # group brackets: first / last member of each run
    for i, r in enumerate(rows):
        if r.group:
            prev_same = i > 0 and rows[i - 1].group == r.group
            next_same = i + 1 < len(rows) and rows[i + 1].group == r.group
            r.first_in_group, r.last_in_group = not prev_same, not next_same

    tv = TableView(rows=rows, role=role, started=bool(view.get("started")), round=int(view.get("round", 0)),
                   active_id=active, can_add=bool(view.get("can_add")), settings=dict(view.get("settings") or {}),
                   my_count=sum(1 for r in rows if r.mine))
    stored = list(view.get("order") or [])
    if stored:
        tv.stored_order = stored
        first_unit_active = tv.started and active and stored and stored[0] != active
        tv.rotated = bool(first_unit_active)
    return tv


def move_before(tv: TableView, display_index: int) -> Optional[str]:
    """The ``before`` id for a ``move`` command that drops a unit at ``display_index`` of the
    displayed (rotated) list: the row that is currently there, or - past the end - the active unit
    (the end of the displayed list is just before the active unit in stored order), or None when the
    display isn't rotated (the end of both lists is the same place)."""
    if display_index < len(tv.rows):
        return tv.rows[display_index].id
    return tv.active_id if tv.rotated else None
