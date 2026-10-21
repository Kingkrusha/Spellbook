"""Tabletop tokens linked to the initiative tracker.

A token that has been added to initiative carries the tracker entry's id in its ``entry`` field. From
then on the two stay in step, both ways:

* hit points (current and maximum) and conditions follow whichever side was changed last;
* the token (or tokens) whose turn it is gets a highlight ring on the map, for the DM and the players;
* removing the entry from the tracker unlinks the token (the token itself stays on the map).

Everything here runs on the DM's machine against the app's one tracker and one tabletop, so a player's
change reaches the other side through the DM's copy. No widgets and no network in here.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import conditions as C
import initiative_state as I
import tabletop as T

# (token, scene) -> an add_entry command with the creature's real stats, or None to use the token's own
Lookup = Callable[[dict], Optional[dict]]


def _cond_names(entry: I.Entry) -> List[str]:
    return [c["name"] for c in entry.conditions]


def _same_conditions(token_names: List[str], entry: I.Entry) -> bool:
    return sorted(n.lower() for n in token_names) == sorted(n.lower() for n in _cond_names(entry))


def active_entries(state: I.TrackerState) -> List[str]:
    """Ids of every entry in the unit whose turn it is (none when combat hasn't started)."""
    if not state.started or not state.active:
        return []
    for unit in I.units(state):
        if any(e.id == state.active for e in unit):
            return [e.id for e in unit]
    return []


class InitiativeLink:
    def __init__(self, table: T.Tabletop, tracker: I.Tracker, lookup: Optional[Lookup] = None):
        self.table = table
        self.tracker = tracker
        self.lookup = lookup
        self._busy = False
        tracker.add_listener(self._tracker_changed)
        table.add_listener(self._table_changed)
        self._tracker_changed(tracker.state)          # catch up on anything changed while unlinked

    def close(self) -> None:
        self.tracker.remove_listener(self._tracker_changed)
        self.table.remove_listener(self._table_changed)

    # ---- adding

    def entry_command(self, token: dict) -> dict:
        """The ``add_entry`` command for one token."""
        cmd = None
        if self.lookup is not None:
            try:
                cmd = self.lookup(token)
            except Exception:
                cmd = None
        if cmd is None:
            kind = I.KIND_PLAYER if token.get("kind") == "pc" else I.KIND_MONSTER
            cmd = {"type": "add_entry", "kind": kind, "name": token["name"]}
        cmd = dict(cmd)
        cmd["name"] = token["name"]                   # the map's name wins ("Goblin 3", not "Goblin")
        if token.get("hp_max"):
            cmd["hp_max"] = token["hp_max"]
            cmd["hp"] = max(0, min(token["hp_max"], token.get("hp") if token.get("hp") is not None
                                   else token["hp_max"]))
        elif token.get("hp") is not None:
            cmd["hp"] = cmd["hp_max"] = max(0, token["hp"])
        cmd["hidden"] = bool(token.get("hidden"))
        if token.get("owner"):
            cmd["owner"] = token["owner"]
        cmd["conditions"] = [C.make_condition(n) for n in token.get("conditions") or []]
        return cmd

    def addable(self, scene_id: str) -> List[dict]:
        """Tokens on a map that could go into initiative: not props, not already in."""
        scene = self.table.scene(scene_id)
        if scene is None:
            return []
        return [t for t in scene["tokens"] if t.get("kind") != "prop" and not self.entry_for(t)]

    def add(self, scene_id: str, token_ids: List[str]) -> int:
        """Add these tokens to the tracker and link them. Returns how many were added.
        Raises :class:`initiative_state.CommandError` (e.g. the tracker is full)."""
        scene = self.table.scene(scene_id)
        if scene is None:
            return 0
        added = 0
        links: Dict[str, str] = {}
        for t in scene["tokens"]:
            if t["id"] not in token_ids or t.get("kind") == "prop" or self.entry_for(t):
                continue
            self._busy = True
            try:
                state = self.tracker.dispatch(I.DM, self.entry_command(t))
            finally:
                self._busy = False
            if state.last_added:
                links[t["id"]] = state.last_added[0]
                added += 1
        if links:
            self.table.link_tokens(scene_id, {tid: {"entry": eid} for tid, eid in links.items()})
            self._tracker_changed(self.tracker.state)
        return added

    def unlink(self, scene_id: str, token_id: str, remove_entry: bool = False) -> None:
        scene = self.table.scene(scene_id)
        token = next((t for t in scene["tokens"] if t["id"] == token_id), None) if scene else None
        if token is None:
            return
        entry = token.get("entry")
        self.table.link_tokens(scene_id, {token_id: {"entry": ""}})
        if remove_entry and entry and self.tracker.state.get(entry):
            self._busy = True
            try:
                self.tracker.dispatch(I.DM, {"type": "remove", "id": entry})
            finally:
                self._busy = False
            self._tracker_changed(self.tracker.state)

    def entry_for(self, token: dict) -> Optional[I.Entry]:
        entry = token.get("entry")
        return self.tracker.state.get(entry) if entry else None

    def next_turn(self) -> None:
        self.tracker.dispatch(I.DM, {"type": "next_turn"})

    # ---- keeping in step

    def _linked(self) -> List[Tuple[str, dict]]:
        return [(sid, t) for sid in list(self.table.order) for t in self.table.scenes[sid]["tokens"]
                if t.get("entry")]

    def _tracker_changed(self, state: I.TrackerState) -> None:
        """The tracker changed: copy HP and conditions onto the tokens and move the turn ring."""
        if self._busy:
            return
        self._busy = True
        try:
            by_scene: Dict[str, Dict[str, dict]] = {}
            for sid, t in self._linked():
                e = state.get(t["entry"])
                if e is None:
                    by_scene.setdefault(sid, {})[t["id"]] = {"entry": ""}
                    continue
                fields = {}
                if e.kind != I.KIND_EVENT and (e.hp_max or t.get("hp") is not None):
                    if t.get("hp") != e.hp:
                        fields["hp"] = e.hp
                    if t.get("hp_max") != e.hp_max:
                        fields["hp_max"] = e.hp_max
                if not _same_conditions(t.get("conditions") or [], e):
                    fields["conditions"] = _cond_names(e)
                if fields:
                    by_scene.setdefault(sid, {})[t["id"]] = fields
            for sid, changes in by_scene.items():
                self.table.link_tokens(sid, changes)
            self.table.set_turn(active_entries(state))
        finally:
            self._busy = False

    def _table_changed(self, scene_id: Optional[str]) -> None:
        """A token changed on the map: copy its HP and conditions into the tracker."""
        if self._busy:
            return
        self._busy = True
        pushed = False
        try:
            for sid, t in self._linked():
                if scene_id and sid != scene_id:
                    continue
                e = self.tracker.state.get(t["entry"])
                if e is None or e.kind == I.KIND_EVENT:
                    continue
                stats = {}
                if t.get("hp_max") is not None and t["hp_max"] != e.hp_max:
                    stats["hp_max"] = max(0, t["hp_max"])
                if t.get("hp") is not None and t["hp"] != e.hp:
                    stats["hp"] = max(0, t["hp"])
                try:
                    if stats:
                        self.tracker.dispatch(I.DM, {"type": "set_stats", "id": e.id, **stats})
                        pushed = True
                    if not _same_conditions(t.get("conditions") or [], e):
                        keep = {c["name"].lower(): c for c in e.conditions}
                        new = [keep.get(n.lower()) or C.make_condition(n) for n in t.get("conditions") or []]
                        self.tracker.dispatch(I.DM, {"type": "set_conditions", "id": e.id, "conditions": new})
                        pushed = True
                except (I.CommandError, ValueError):
                    pass
        finally:
            self._busy = False
        if pushed:          # the tracker may have adjusted a value (HP above the maximum): copy it back
            self._tracker_changed(self.tracker.state)
