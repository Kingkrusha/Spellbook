"""The tabletop on a screen and over a LAN session: the backends a map page runs against.

* :class:`LocalTable` (the DM's app) edits any scene directly.
* :class:`TableHostLink` (the DM's app, while hosting) sends every connected player *their own view* of the
  scene they're shown whenever it changes (hidden tokens and other people's hit points are left out on the
  DM's computer, so they never reach a player's), runs the commands players send as that player, and hands
  out the pictures a player's view needs (only those). After a change a player whose app can take it gets
  only what changed in their view (``table_patch.py``), not the whole map again.
* :class:`RemoteTable` (a player's app) holds the last view the DM sent and turns "move this token" or
  "draw this" into a command. A moved token jumps to where it was dropped straight away; the DM's answer
  then confirms it (or puts it back, if it wasn't allowed).

Both backends offer the same small interface to the page: ``role``, ``view()``, ``dispatch(cmd)``,
``listen(fn)`` / ``unlisten(fn)``, ``asset_path(id)``, ``ping(x, y)`` and ``on_ping(fn)``.

No widgets here; ``schedule`` (a tkinter ``after``) is optional.
"""

from __future__ import annotations

import base64
import hashlib
import json
import marshal
from typing import Callable, Dict, List, Optional

import table_patch as TP
import tabletop as T


class _Listeners:
    def __init__(self):
        self._fns: List[Callable] = []

    def add(self, fn: Callable) -> None:
        if fn not in self._fns:
            self._fns.append(fn)

    def remove(self, fn: Callable) -> None:
        if fn in self._fns:
            self._fns.remove(fn)

    def call(self, *args) -> None:
        for fn in list(self._fns):
            try:
                fn(*args)
            except Exception as e:
                print(f"Tabletop listener failed: {e}")


# Pings on the DM's side: the DM's own and the ones players send come through here, so the DM's page and the
# host link (which passes them on to the players) both hear every one.
dm_pings = _Listeners()


class LocalTable:
    """The DM's own tabletop: any scene, everything visible, every command allowed."""

    role = "dm"

    def __init__(self, table: Optional[T.Tabletop] = None, assets: Optional[T.AssetStore] = None,
                 name: str = "DM"):
        self.table = table or T.get_tabletop()
        self.assets = assets or T.get_assets()
        self.name = name
        self.scene_id = self.table.shown or (self.table.order[0] if self.table.order else "")
        self._view: Optional[tuple] = None        # (what it was made for, the view)
        self._listeners = _Listeners()
        self._pings = _Listeners()
        self.table.add_listener(self._changed)
        dm_pings.add(self._pinged)

    def close(self) -> None:
        self.table.remove_listener(self._changed)
        dm_pings.remove(self._pinged)

    def _changed(self, _scene_id) -> None:
        if self.scene_id not in self.table.scenes:
            self.scene_id = self.table.order[0] if self.table.order else ""
        self._listeners.call()

    def _pinged(self, ping: dict) -> None:
        if ping.get("scene") == self.scene_id:
            self._pings.call(ping)

    # ---- the interface
    def view(self) -> dict:
        # The page asks for the view many times after one change (the map, the lists beside it, the menus),
        # and each answer is a copy of the whole map: one copy per change is kept. Nobody changes a view.
        key = (self.table.rev, self.scene_id, self.table.turn)
        if self._view is None or self._view[0] != key:
            self._view = (key, T.project(self.table.scene(self.scene_id), T.DM, rev=self.table.rev,
                                         turn=self.table.turn))
        return self._view[1]

    def select_scene(self, scene_id: str) -> None:
        if scene_id in self.table.scenes and scene_id != self.scene_id:
            self.scene_id = scene_id
            self._listeners.call()

    def dispatch(self, cmd: dict) -> dict:
        cmd = dict(cmd)
        cmd.setdefault("scene", self.scene_id)
        result = self.table.apply(cmd, T.DM, self.name)
        if result.get("scene") and cmd.get("op") in ("scene_new", "scene_duplicate"):
            self.select_scene(result["scene"])
        return result

    def undo(self) -> bool:
        return self.table.undo()

    def listen(self, fn: Callable[[], None]) -> None:
        self._listeners.add(fn)

    def unlisten(self, fn: Callable[[], None]) -> None:
        self._listeners.remove(fn)

    def asset_path(self, asset_id: str) -> Optional[str]:
        return self.assets.path(asset_id)

    def ping(self, x: float, y: float) -> None:
        dm_pings.call({"scene": self.scene_id, "x": float(x), "y": float(y), "name": self.name,
                       "color": "#F1C40F"})

    def on_ping(self, fn: Callable[[dict], None]) -> None:
        self._pings.add(fn)


def _dump(view: dict) -> Optional[bytes]:
    """``view`` written out in full with ``marshal`` (format 2), or None when it holds something marshal
    can't write. Some 25 times quicker than JSON, and this runs for every player after every change."""
    try:
        return marshal.dumps(view, 2)
    except ValueError:
        return None


def _digest(view: dict) -> str:
    """A fingerprint of a view, to tell whether a player already has it."""
    data = _dump(view)
    if data is None:                            # something marshal can't write: the slow way
        data = json.dumps(view, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(data).hexdigest()


def _copy(view: dict) -> dict:
    """A copy of a view sharing nothing with it (or with the scene it was made from)."""
    data = _dump(view)
    return marshal.loads(data) if data is not None else json.loads(json.dumps(view, default=str))


def _player_key(service, peer_id: str) -> str:
    """The id a player's tokens are owned by: their install id (it survives reconnecting)."""
    return service.client_ids.get(peer_id) or f"peer:{peer_id}"


class TableHostLink:
    """Keeps every connected player's map current and runs their commands (the DM's app, while hosting)."""

    COALESCE_MS = 60
    SAVE_MS = 4000                  # a change is on disk at the latest this long after it was made
    PING_COLORS = ["#3498DB", "#2ECC71", "#E67E22", "#9B59B6", "#1ABC9C", "#E74C3C", "#F1C40F", "#EC407A"]

    def __init__(self, service, table: Optional[T.Tabletop] = None, assets: Optional[T.AssetStore] = None,
                 schedule: Optional[Callable[[int, Callable[[], None]], object]] = None):
        self.service = service
        self.table = table or T.get_tabletop()
        self.assets = assets or T.get_assets()
        self._schedule = schedule
        self._pending = False
        self._closed = False
        self._sent: Dict[str, str] = {}           # peer id -> digest of the last view sent
        self._last: Dict[str, dict] = {}          # peer id -> a copy of that view (to send only what changes)
        self._seq: Dict[str, int] = {}            # peer id -> the number of the last view sent
        self._patching: set = set()               # players whose app takes changes ("table_sync" said so)
        self._touched: set = set()                # maps changed since the last send (None: something else did)
        self._shown = self.table.shown            # the map the players were shown at the last send
        self._saving = False
        self.table.add_listener(self._changed)
        service.add_listener(self._on_service)
        dm_pings.add(self._forward_ping)
        self.send_all()

    def close(self) -> None:
        self._closed = True
        self.table.remove_listener(self._changed)
        self.service.remove_listener(self._on_service)
        dm_pings.remove(self._forward_ping)
        if self._schedule is not None and (self.table.dirty or self.table.explored_dirty):
            self.table.save()

    # ---- outbound
    def _changed(self, scene_id) -> None:
        self._touched.add(scene_id or None)
        if self._schedule is None:
            self._send_changes()
            return
        if not self._pending:
            self._pending = True
            self._schedule(self.COALESCE_MS, self._flush)
        if not self._saving:
            self._saving = True
            self._schedule(self.SAVE_MS, self._save)

    def _flush(self) -> None:
        self._pending = False
        if not self._closed:
            self._send_changes()

    def _send_changes(self) -> None:
        """Send the players their views after a change, unless it can't have changed them: they only ever
        see the map they're shown, so the DM working on another one costs nothing here."""
        touched, self._touched = self._touched, set()
        shown, self._shown = self._shown, self.table.shown
        if None in touched or shown != self.table.shown or self.table.shown in touched:
            self.send_all()

    def _save(self) -> None:
        """Players' moves are kept even with the tabletop page closed. Not after every one of them: the
        file holds every map, and writing it stops the window for a moment each time."""
        self._saving = False
        if not self._closed and (self.table.dirty or self.table.explored_dirty):
            self.table.save()

    def _players(self) -> List[str]:
        return [p["peer_id"] for p in list(self.service.peers) if p["peer_id"] != self.service.my_id]

    def send_all(self) -> None:
        for peer_id in self._players():
            self.send_one(peer_id)

    def send_one(self, peer_id: str, force: bool = False) -> None:
        """Bring one player's map up to date: only what changed when their app takes that and it's clearly
        smaller, otherwise the whole view. ``force`` sends the whole view even if they should have it."""
        view = self.table.view_for(_player_key(self.service, peer_id))
        body = {k: v for k, v in view.items() if k != "rev"}
        data = _dump(body)
        digest = hashlib.sha1(data).hexdigest() if data is not None else _digest(body)
        if not force and self._sent.get(peer_id) == digest:
            return
        self._sent[peer_id] = digest
        seq = self._seq.get(peer_id, 0) + 1
        self._seq[peer_id] = seq
        last = self._last.get(peer_id) if peer_id in self._patching and not force else None
        if peer_id in self._patching:
            self._last[peer_id] = marshal.loads(data) if data is not None else _copy(body)
            self._last[peer_id]["rev"] = view.get("rev")
        ops = TP.diff_view(last, view) if last is not None else None
        # (the marshal size stands in for the JSON one: near enough to tell "a few changes" from "most of it")
        if ops is not None and TP.worth_it(ops, len(data) if data is not None else 1 << 30):
            self.service.send_table_patch(peer_id, ops, seq - 1, seq)
        else:
            self.service.send_table_state(peer_id, view, seq=seq)

    def _forget(self, peer_id: str) -> None:
        for d in (self._sent, self._last, self._seq):
            d.pop(peer_id, None)
        self._patching.discard(peer_id)

    def _forward_ping(self, ping: dict) -> None:
        if ping.get("scene") != self.table.shown:
            return                              # a ping on a map the players can't see
        for peer_id in self._players():
            self.service.send_table_ping(peer_id, ping)

    # ---- inbound
    def _on_service(self, kind: str, **data) -> None:
        if self._closed:
            return
        if kind == "peer_joined":
            self._forget(data["peer"]["peer_id"])
            self.send_one(data["peer"]["peer_id"], force=True)
        elif kind == "peer_left":
            self._forget(data["peer"]["peer_id"])
        elif kind == "table_sync":                  # a player's app takes changes, or lost track: the whole view
            self._patching.add(data["peer_id"])
            self.send_one(data["peer_id"], force=True)
        elif kind == "table_cmd":
            self.apply(data["peer_id"], data["name"], data["cmd"], data.get("seq"))
        elif kind == "table_asset_req":
            self.send_assets(data["peer_id"], data["ids"])

    def apply(self, peer_id: str, name: str, cmd: dict, seq: Optional[int] = None) -> bool:
        key = _player_key(self.service, peer_id)
        if isinstance(cmd, dict) and cmd.get("op") == "ping":
            players = self._players()
            color = self.PING_COLORS[players.index(peer_id) % len(self.PING_COLORS)] if peer_id in players else \
                self.PING_COLORS[0]
            dm_pings.call({"scene": self.table.shown, "x": T._num(cmd.get("x")), "y": T._num(cmd.get("y")),
                           "name": T._text(name, 32), "color": color})
            return True
        try:
            self.table.apply(cmd, key, name)
        except T.CommandError as e:
            self.service.send_table_error(peer_id, str(e), seq)
            self.send_one(peer_id, force=True)          # puts back a token that was moved and refused
            return False
        except Exception as e:                          # a malformed command must never stop the host
            print(f"Tabletop: a player's command failed: {e}")
            self.service.send_table_error(peer_id, "That couldn't be done.", seq)
            return False
        return True

    def send_assets(self, peer_id: str, ids: List[str]) -> int:
        """Send the pictures a player asked for: only ones in what they can see."""
        allowed = set(T.asset_ids_in(self.table.view_for(_player_key(self.service, peer_id)).get("scene")))
        sent = 0
        for asset_id in ids:
            if asset_id not in allowed:
                continue
            data = self.assets.read(asset_id)
            if not data:
                continue
            parts = list(T.chunks(data))
            for i, part in enumerate(parts):
                self.service.send_table_asset(peer_id, asset_id, i, len(parts),
                                              base64.b64encode(part).decode("ascii"))
            sent += 1
        return sent


class RemoteTable:
    """A player's tabletop: the DM's view of the shown scene, and commands sent back to the DM."""

    role = "player"
    MAX_PARTS = 16

    def __init__(self, service, assets: Optional[T.AssetStore] = None):
        self.service = service
        self.assets = assets or T.get_assets()
        self._view: dict = {"rev": 0, "scene": None, "role": "player"}
        self._listeners = _Listeners()
        self._pings = _Listeners()
        self._errors = _Listeners()
        self._requested: set = set()
        self._parts: Dict[str, Dict[int, bytes]] = {}
        self._seq = 0
        self._view_seq: Optional[int] = None     # the number of the view we hold (for the DM's patches)
        self._syncing = False                     # asked for the whole view and waiting for it
        service.add_listener(self._on_service)
        # the whole view now (it may have come before we were listening), and patches from here on
        sync = getattr(service, "request_table_sync", None)
        if sync is not None:
            self._syncing = bool(sync())

    def close(self) -> None:
        self.service.remove_listener(self._on_service)

    @property
    def my_key(self) -> str:
        return self.service.client_id() or ""

    # ---- the interface
    def view(self) -> dict:
        return self._view

    def dispatch(self, cmd: dict) -> dict:
        scene = self._view.get("scene")
        if scene is None:
            raise T.CommandError("The DM isn't showing a map.")
        cmd = dict(cmd)
        cmd["scene"] = scene["id"]
        if cmd.get("op") == "token_move":           # move it here at once; the DM's answer confirms it
            for t in scene["tokens"]:
                if t["id"] == cmd.get("id"):
                    t["x"], t["y"] = float(cmd["x"]), float(cmd["y"])
                    if cmd.get("z") is not None:
                        t["z"] = float(cmd["z"])
            self._listeners.call()
        self._seq += 1
        if not self.service.send_table_cmd(cmd, self._seq):
            raise T.CommandError("You're not connected to the DM.")
        return {}

    def undo(self) -> bool:
        return False

    def listen(self, fn: Callable[[], None]) -> None:
        self._listeners.add(fn)

    def unlisten(self, fn: Callable[[], None]) -> None:
        self._listeners.remove(fn)

    def on_error(self, fn: Callable[[str], None]) -> None:
        self._errors.add(fn)

    def asset_path(self, asset_id: str) -> Optional[str]:
        return self.assets.path(asset_id)

    def ping(self, x: float, y: float) -> None:
        if self._view.get("scene") is not None:
            self.service.send_table_cmd({"op": "ping", "x": float(x), "y": float(y)})

    def on_ping(self, fn: Callable[[dict], None]) -> None:
        self._pings.add(fn)

    # ---- from the DM
    def _on_service(self, kind: str, **data) -> None:
        if kind == "table_state":
            view = data.get("view")
            if valid_view(view):
                self._view = view
                self._view_seq = data.get("seq")
                self._syncing = False
                self._fetch_missing()
                self._listeners.call()
        elif kind == "table_patch":
            self._patch(data)
        elif kind == "table_asset":
            self._receive_part(data)
        elif kind == "table_error":
            self._errors.call(data.get("message") or "")
        elif kind == "table_ping":
            ping = data.get("ping") or {}
            scene = self._view.get("scene")
            if scene is not None and isinstance(ping, dict):
                self._pings.call({"scene": scene["id"], "x": T._num(ping.get("x")), "y": T._num(ping.get("y")),
                                  "name": T._text(ping.get("name"), 32),
                                  "color": T._color(ping.get("color"), "#3498DB")})

    def _patch(self, data: dict) -> None:
        """What changed since the view we hold. Made on a copy, so a patch that doesn't fit leaves the map as it
        was; then (or if we missed one) we ask for the whole view again."""
        seq = data.get("seq")
        if self._syncing:
            return                                      # the whole view is on its way
        view = None
        if self._view_seq is not None and data.get("base") == self._view_seq and isinstance(seq, int):
            view = _copy(self._view)
            if not TP.apply_ops(view, data.get("ops")) or not valid_view(view):
                view = None
        if view is None:
            self._view_seq = None
            self._syncing = bool(self.service.request_table_sync())
            return
        self._view = view
        self._view_seq = seq
        self._fetch_missing()
        self._listeners.call()

    def _fetch_missing(self) -> None:
        missing = [i for i in T.asset_ids_in(self._view.get("scene"))
                   if not self.assets.has(i) and i not in self._requested]
        if missing:
            self._requested.update(missing)
            self.service.request_table_assets(missing)

    def _receive_part(self, data: dict) -> None:
        asset_id, part, parts = data.get("id"), data.get("part"), data.get("parts")
        if not T.valid_asset_id(asset_id) or not isinstance(part, int) or not isinstance(parts, int):
            return
        if not (0 < parts <= self.MAX_PARTS and 0 <= part < parts) or asset_id not in self._requested:
            return
        try:
            chunk = base64.b64decode(data.get("data") or "", validate=True)
        except (ValueError, TypeError):
            return
        got = self._parts.setdefault(asset_id, {})
        got[part] = chunk
        if len(got) == parts:
            blob = b"".join(got[i] for i in range(parts))
            del self._parts[asset_id]
            if self.assets.add_received(asset_id, blob):
                self._listeners.call()
            else:
                self._requested.discard(asset_id)


def valid_view(view) -> bool:
    """A cheap shape check on a view that came over the network."""
    if not isinstance(view, dict):
        return False
    scene = view.get("scene")
    if scene is None:
        return True
    if not isinstance(scene, dict) or not isinstance(scene.get("id"), str):
        return False
    tokens, drawings = scene.get("tokens"), scene.get("drawings")
    if not isinstance(tokens, list) or not isinstance(drawings, list) or len(tokens) > T.MAX_TOKENS:
        return False
    if len(drawings) > T.MAX_DRAWINGS or not isinstance(scene.get("grid"), dict):
        return False
    if not isinstance(scene.get("fog"), dict) or not isinstance(scene["fog"].get("ops"), list):
        return False
    for t in tokens:
        if not isinstance(t, dict) or not isinstance(t.get("id"), str) or not isinstance(t.get("name"), str):
            return False
        if not all(isinstance(t.get(k), (int, float)) for k in ("x", "y", "size")):
            return False
    for d in drawings:
        if not isinstance(d, dict) or not isinstance(d.get("pts"), list):
            return False
    areas, zones = scene.get("areas", []), scene.get("zones", [])
    if not isinstance(areas, list) or not isinstance(zones, list):
        return False
    for a in areas:
        if not isinstance(a, dict) or a.get("shape") not in T.AREA_SHAPES or not isinstance(a.get("id"), str):
            return False
        if not all(isinstance(a.get(k), (int, float)) for k in ("x", "y", "size", "dir", "pitch", "dz", "width")):
            return False
    for z in zones:
        if not isinstance(z, dict) or not isinstance(z.get("pts"), list) or not isinstance(z.get("elev"), (int, float)):
            return False
    return True
