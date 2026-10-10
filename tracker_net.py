"""The initiative tracker over a session: the DM's side and a player's side.

* :class:`TrackerHostLink` (DM's app) watches the encounter and, whenever it changes, sends every
  connected player *their own projection* of it - hidden creatures and numbers are filtered out here, on
  the host, so they never reach a player's machine. It also applies the commands players send, as that
  player (so the same rules decide what they may change as for a local player).
* :class:`RemoteBackend` (a player's app) is the backend a player's screens run against: it holds the
  last view the host sent, and turns "do this" into a command message. Nothing happens locally until
  the host answers with the new view, so what a player sees is always what the DM's rules produced.

No widgets in this module; ``schedule`` (a tkinter ``after``) is optional.
"""

from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional

import initiative_rows as R
import initiative_state as T

# Longest a player's command may be (the host also caps it on receipt)
MAX_COMMAND_BYTES = 8192

EMPTY_VIEW: dict = {"role": "player", "rev": 0, "started": False, "round": 0, "active": "",
                    "can_add": False, "group_names": {}, "entries": []}


def valid_view(view) -> bool:
    """A cheap shape check on a view that came over the network (the host is the DM, but a view is
    still data from another computer)."""
    if not isinstance(view, dict) or not isinstance(view.get("entries"), list) or len(view["entries"]) > 200:
        return False
    for e in view["entries"]:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not isinstance(e.get("name"), str):
            return False
    return True


class TrackerHostLink:
    """Keeps every connected player's tracker view current, and runs their commands."""

    COALESCE_MS = 40

    def __init__(self, hub, service, schedule: Optional[Callable[[int, Callable[[], None]], object]] = None):
        self.hub = hub
        self.service = service
        self._schedule = schedule
        self._pending = False
        self._closed = False
        hub.tracker.add_listener(self._changed)
        service.add_listener(self._on_service)
        hub.online_owners = lambda: set(service.client_ids.values())
        self.send_all()                      # players already connected get the current encounter

    def close(self) -> None:
        self._closed = True
        self.hub.online_owners = None
        self.hub.tracker.remove_listener(self._changed)
        self.service.remove_listener(self._on_service)
        self.hub.tracker.notify()            # the DM's table forgets who was "offline"

    # ------------------------------------------------------------------ outbound

    def _changed(self, _state) -> None:
        """The encounter changed: tell everyone, once per burst of changes."""
        if self._schedule is None:
            self.send_all()
        elif not self._pending:
            self._pending = True
            self._schedule(self.COALESCE_MS, self._flush)

    def _flush(self) -> None:
        self._pending = False
        if not self._closed:
            self.send_all()

    def send_all(self) -> None:
        for p in list(self.service.peers):
            if p["peer_id"] != self.service.my_id:
                self.send_one(p["peer_id"])

    def send_one(self, peer_id: str) -> None:
        client_id = self.service.client_ids.get(peer_id)
        if client_id is None:
            return
        view = T.project(self.hub.tracker.state, T.Actor("player", client_id))
        self.service.send_tracker_state(peer_id, view)

    # ------------------------------------------------------------------ inbound

    def _on_service(self, kind: str, **data) -> None:
        if kind == "peer_joined":
            self.send_one(data["peer"]["peer_id"])
        elif kind == "state":
            self.hub.tracker.notify()        # someone joined or left: refresh the "offline" markers
        elif kind == "tracker_cmd":
            self.apply(data["peer_id"], data["cmd"], data.get("seq"))

    def apply(self, peer_id: str, cmd: dict, seq: Optional[int] = None) -> bool:
        """Run a player's command *as that player*. Returns False (and tells them why) if refused."""
        client_id = self.service.client_ids.get(peer_id)
        if not client_id or not isinstance(cmd, dict):
            return False
        if len(json.dumps(cmd, separators=(",", ":"))) > MAX_COMMAND_BYTES:
            self.service.send_tracker_error(peer_id, "That command is too large.", seq)
            return False
        try:
            self.hub.tracker.dispatch(T.Actor("player", client_id), cmd)
        except T.CommandError as e:
            self.service.send_tracker_error(peer_id, e.message, seq)
            return False
        except Exception as e:                      # a bad command must never take the DM's app down
            self.service.send_tracker_error(peer_id, "The command could not be run.", seq)
            print(f"Tracker command from {peer_id} failed: {e}")
            return False
        return True


class RemoteBackend:
    """A player's backend: the host's projection in, command messages out."""

    role = "player"
    can_undo = False

    def __init__(self, service):
        self.service = service
        self._view: dict = dict(EMPTY_VIEW)
        self._listeners: List[Callable[[], None]] = []
        self._error_handler: Optional[Callable[[str], None]] = None
        self.last_error = ""
        service.add_listener(self._on_service)

    def close(self) -> None:
        self.service.remove_listener(self._on_service)

    # -- the backend interface the screens use
    def view(self) -> dict:
        return self._view

    def table(self) -> R.TableView:
        return R.build(self._view)

    def dispatch(self, cmd: dict) -> None:
        if not self.service.send_tracker_cmd(cmd):
            raise T.CommandError("offline", "You are not connected to a session.")

    def undo(self) -> None:
        raise T.CommandError("forbidden", "Only the DM can do that.")

    def owners(self) -> list:
        return []

    def listen(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def unlisten(self, fn: Callable[[], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def set_error_handler(self, fn: Optional[Callable[[str], None]]) -> None:
        """``fn(message)`` is called when the host refuses something we asked for."""
        self._error_handler = fn

    # -- events from the session
    def _notify(self) -> None:
        for fn in list(self._listeners):
            try:
                fn()
            except Exception as e:
                print(f"Tracker listener error: {e}")

    def _on_service(self, kind: str, **data) -> None:
        if kind == "tracker_state":
            view = data.get("view")
            if not valid_view(view):
                return
            if isinstance(view.get("rev"), int) and view["rev"] < self._view.get("rev", 0):
                return                              # an older snapshot that arrived late
            self._view = view
            self._notify()
        elif kind == "tracker_error":
            self.last_error = data.get("message", "")
            if self._error_handler is not None:
                self._error_handler(self.last_error)
        elif kind == "ended":
            self._view = dict(EMPTY_VIEW)
            self._notify()
