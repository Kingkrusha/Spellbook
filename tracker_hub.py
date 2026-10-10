"""The app's one initiative tracker, and the "backends" the screens talk to.

:class:`TrackerHub` owns the :class:`initiative_state.Tracker` (state + undo), keeps it saved in
``initiative_state.json`` so a crash or an early close doesn't lose a long fight, and hands out
backends. A *backend* is what a tracker screen needs and nothing more: ``table()`` (what to draw for
this viewer), ``dispatch(command)`` (do something, as this viewer), and change notifications. The
local backends here run against the hub's tracker directly; a player's computer will use one that
sends commands to the host and receives its projections instead - the screens don't care which.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

import initiative_rows as R
import initiative_state as T

FILE_NAME = "initiative_state.json"
SAVE_DELAY_MS = 600


class LocalBackend:
    """A viewer of the hub's own tracker: the DM, or a player (to preview what they see)."""

    def __init__(self, hub: "TrackerHub", actor: T.Actor):
        self.hub = hub
        self.actor = actor
        self._wrappers: Dict[Callable, Callable] = {}

    @property
    def role(self) -> str:
        return "dm" if self.actor.is_dm else "player"

    # -- reading
    def view(self) -> dict:
        return T.project(self.hub.tracker.state, self.actor)

    def table(self) -> R.TableView:
        tv = R.build(self.view())
        online = self.hub.online_owners() if (self.actor.is_dm and self.hub.online_owners) else None
        if online is not None:
            for r in tv.rows:
                r.offline = r.kind == T.KIND_PLAYER and bool(r.owner) and r.owner not in online
        return tv

    @property
    def can_undo(self) -> bool:
        return self.actor.is_dm and self.hub.tracker.can_undo

    # -- acting
    def dispatch(self, cmd: dict) -> None:
        """Run a command as this viewer. Raises :class:`initiative_state.CommandError`."""
        self.hub.tracker.dispatch(self.actor, cmd)

    def undo(self) -> None:
        self.hub.tracker.dispatch(self.actor, {"type": "undo"})

    # -- listening
    def listen(self, fn: Callable[[], None]) -> None:
        wrapper = lambda _state, fn=fn: fn()           # noqa: E731
        self._wrappers[fn] = wrapper
        self.hub.tracker.add_listener(wrapper)

    def unlisten(self, fn: Callable[[], None]) -> None:
        wrapper = self._wrappers.pop(fn, None)
        if wrapper is not None:
            self.hub.tracker.remove_listener(wrapper)

    def owners(self) -> List[Tuple[str, str]]:
        """``[(owner id, a name of theirs)]`` for everyone who owns an entry (to preview as)."""
        seen: Dict[str, str] = {}
        for e in self.hub.tracker.state.entries:
            if e.kind == T.KIND_PLAYER and e.owner and e.owner not in seen:
                seen[e.owner] = e.name
        return list(seen.items())


class TrackerHub:
    def __init__(self, path: Optional[str] = None,
                 schedule: Optional[Callable[[int, Callable[[], None]], object]] = None,
                 cancel: Optional[Callable[[object], None]] = None):
        if path is None:
            from paths import user_data_path
            path = user_data_path(FILE_NAME)
        self.path = path
        loaded = T.load_state(path)
        self.tracker = T.Tracker(loaded)
        self.resumed = bool(loaded and loaded.entries)     # there was an encounter on disk
        self._schedule, self._cancel = schedule, cancel
        self._pending: object = None
        self._dirty = False
        self.save_error = ""
        # Set while hosting a session: who is connected right now (install ids), else None = unknown
        self.online_owners: Optional[Callable[[], set]] = None
        self.tracker.add_listener(self._changed)

    # -- backends
    def dm(self) -> LocalBackend:
        return LocalBackend(self, T.DM)

    def player(self, owner_id: str) -> LocalBackend:
        return LocalBackend(self, T.Actor("player", owner_id))

    # -- saving
    def _changed(self, _state) -> None:
        self._dirty = True
        if self._schedule is None:
            self.flush()
        elif self._pending is None:
            self._pending = self._schedule(SAVE_DELAY_MS, self._autosave)

    def _autosave(self) -> None:
        self._pending = None
        self.flush()

    def flush(self) -> bool:
        """Write the encounter now if it changed. Returns False (and sets ``save_error``) on failure."""
        if self._pending is not None and self._cancel is not None:
            try:
                self._cancel(self._pending)
            except Exception:
                pass
            self._pending = None
        if not self._dirty:
            return True
        try:
            T.save_state(self.tracker.state, self.path)
            self._dirty = False
            self.save_error = ""
            return True
        except Exception as e:
            self.save_error = str(e)
            return False
