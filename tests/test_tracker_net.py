"""The initiative tracker over a real encrypted session (loopback): what players receive, what they
may do, and that nothing hidden ever reaches a player's computer."""

import json
import time

import pytest

import initiative_sources as S
import initiative_state as T
from lan import protocol as P
from lan.service import CLIENT, SessionService
from tracker_hub import TrackerHub
from tracker_net import RemoteBackend, TrackerHostLink, valid_view


def pump_until(cond, *services, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for s in services:
            s.pump()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached")


class Table:
    """A DM (with a hub and link) and any number of players, all in one process."""

    def __init__(self, tmp_path):
        self.hub = TrackerHub(str(tmp_path / "state.json"))
        self.host = SessionService()
        port = self.host.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
        self.invite = P.Invite("127.0.0.1", port, self.host._host.fingerprint).encode()
        self.link = TrackerHostLink(self.hub, self.host)
        self.players = {}
        self.dm = self.hub.dm()

    def join(self, name, client_id=None):
        svc = SessionService()
        if client_id:
            svc._client_id_cache = client_id
        svc.join(self.invite, name)
        pump_until(lambda: svc.role == CLIENT, self.host, svc)
        backend = RemoteBackend(svc)
        self.players[name] = (svc, backend)
        pump_until(lambda: backend.view()["rev"] >= self.hub.tracker.state.rev, self.host, *self._svcs())
        return svc, backend

    def _svcs(self):
        return [s for s, _ in self.players.values()]

    def settle(self, cond=None, timeout=5.0):
        pump_until(cond or (lambda: True), self.host, *self._svcs(), timeout=timeout)
        # let any in-flight messages land
        for _ in range(10):
            for s in [self.host] + self._svcs():
                s.pump()
            time.sleep(0.02)

    def cid(self, name):
        return self.players[name][0].client_id()

    def close(self):
        self.link.close()
        for s in self._svcs():
            s.shutdown()
        self.host.shutdown()


@pytest.fixture()
def table(tmp_path):
    t = Table(tmp_path)
    yield t
    t.close()


def rows(backend):
    return {r.name: r for r in backend.table().rows}


def test_a_joining_player_gets_the_current_encounter(table):
    table.dm.dispatch(S.custom("Ogre", hp=59, ac=11))
    table.dm.dispatch(S.event("Avalanche", 10))
    table.dm.dispatch({"type": "start"})
    svc, remote = table.join("Alice")
    r = rows(remote)
    assert set(r) == {"Ogre", "Avalanche"} and remote.view()["started"] is True
    assert r["Ogre"].hp == 59 and r["Ogre"].ac == 11 and not r["Ogre"].can_edit


def test_dm_changes_reach_players_as_they_happen(table):
    svc, remote = table.join("Alice")
    seen = []
    remote.listen(lambda: seen.append(remote.view()["rev"]))
    table.dm.dispatch(S.custom("Goblin", hp=7, ac=15))
    table.settle(lambda: "Goblin" in rows(remote))
    ogre = next(r for r in table.dm.table().rows if r.name == "Goblin")
    table.dm.dispatch({"type": "hp_delta", "id": ogre.id, "delta": -3})
    table.settle(lambda: rows(remote)["Goblin"].hp == 4)
    assert seen == sorted(seen) and len(seen) >= 2


def test_a_player_edits_their_own_character_through_the_host(table):
    svc, remote = table.join("Alice")
    remote.dispatch({"type": "add_me", "name": "Aria", "hp": 24, "hp_max": 30, "ac": 17, "init_bonus": 3})
    table.settle(lambda: "Aria" in rows(remote))
    me = rows(remote)["Aria"]
    assert me.mine and me.can_edit
    assert next(e for e in table.hub.tracker.state.entries if e.name == "Aria").owner == table.cid("Alice")

    remote.dispatch({"type": "hp_delta", "id": me.id, "delta": -9})
    remote.dispatch({"type": "add_condition", "id": me.id, "name": "Prone"})
    table.settle(lambda: rows(remote)["Aria"].hp == 15 and rows(remote)["Aria"].conditions)
    dm_row = next(r for r in table.dm.table().rows if r.name == "Aria")
    assert dm_row.hp == 15 and dm_row.conditions[0]["name"] == "Prone"          # the DM's table updated too


def test_players_cannot_do_dm_things_or_touch_others(table):
    table.dm.dispatch({"type": "add_entry", "kind": "player", "name": "Bob's Hero", "owner": "someone-else",
                       "hp": 20, "hp_max": 20, "ac": 15, "initiative": 12})
    table.dm.dispatch(S.custom("Ogre", hp=59))
    svc, remote = table.join("Alice")
    errors = []
    remote.set_error_handler(errors.append)
    other = rows(remote)["Bob's Hero"]
    ogre = rows(remote)["Ogre"]
    for cmd in ({"type": "hp_delta", "id": other.id, "delta": -5}, {"type": "hp_delta", "id": ogre.id, "delta": -5},
                {"type": "start"}, {"type": "remove", "id": ogre.id}, {"type": "set_hidden", "id": ogre.id,
                                                                       "hidden": True},
                {"type": "set_settings", "monster_hp": "hidden"}, {"type": "undo"}, {"type": "clear"}):
        remote.dispatch(cmd)
    table.settle(lambda: len(errors) >= 8)
    assert len(errors) == 8 and all("DM" in e or "your own" in e for e in errors)
    state = table.hub.tracker.state
    assert not state.started and len(state.entries) == 2
    assert all(e.hp in (20, 59) for e in state.entries) and state.settings.monster_hp == "number"


def test_hidden_things_never_reach_the_players_computer(table):
    """Look at every view the client received, as raw JSON, for anything the DM hid."""
    table.dm.dispatch(S.custom("Visible Ogre", hp=59, ac=11))
    table.dm.dispatch({"type": "add_entry", "kind": "custom", "name": "SECRET-AMBUSHER", "hp": 33, "ac": 18,
                       "hidden": True, "notes": "SECRET-NOTE"})
    table.dm.dispatch({"type": "set_settings", "monster_hp": "bar", "monster_ac": "hidden"})
    svc, remote = table.join("Alice")
    seen = []
    remote.listen(lambda: seen.append(json.dumps(remote.view())))
    table.dm.dispatch({"type": "start"})
    table.dm.dispatch({"type": "next_turn"})
    table.dm.dispatch({"type": "next_turn"})                                   # the hidden one's turn comes up
    hidden = next(e for e in table.hub.tracker.state.entries if e.name == "SECRET-AMBUSHER")
    table.dm.dispatch({"type": "hp_delta", "id": hidden.id, "delta": -10})
    table.settle(lambda: remote.view()["rev"] == table.hub.tracker.state.rev)
    blobs = seen + [json.dumps(remote.view())]
    assert blobs
    for blob in blobs:
        assert "SECRET" not in blob and hidden.id not in blob
    ogre = rows(remote)["Visible Ogre"]
    assert ogre.hp_mode == "bar" and ogre.ac is None and ogre.hp_frac == 1.0   # bar, not the number


def test_unhiding_reveals_it_and_hiding_removes_it(table):
    table.dm.dispatch({"type": "add_entry", "kind": "custom", "name": "Lurker", "hp": 9, "ac": 12, "hidden": True})
    svc, remote = table.join("Alice")
    assert "Lurker" not in rows(remote)
    lurker = table.hub.tracker.state.entries[0].id
    table.dm.dispatch({"type": "set_hidden", "id": lurker, "hidden": False})
    table.settle(lambda: "Lurker" in rows(remote))
    table.dm.dispatch({"type": "set_hidden", "id": lurker, "hidden": True})
    table.settle(lambda: "Lurker" not in rows(remote))


def test_each_player_gets_their_own_view(table):
    table.dm.dispatch({"type": "add_entry", "kind": "player", "name": "Hidden Spy", "hp": 8, "hp_max": 8,
                       "ac": 12, "hidden": True})
    a_svc, a = table.join("Alice")
    b_svc, b = table.join("Bob")
    spy_id = next(e.id for e in table.hub.tracker.state.entries if e.name == "Hidden Spy")
    table.dm.dispatch({"type": "set_field", "id": spy_id, "field": "owner", "value": table.cid("Bob")})
    table.settle(lambda: "Hidden Spy" in rows(b))
    assert "Hidden Spy" in rows(b) and rows(b)["Hidden Spy"].mine           # a hidden player still sees themselves
    assert "Hidden Spy" not in rows(a)                                      # ...and Alice does not


def test_a_late_or_reconnecting_player_keeps_their_character(table):
    svc, remote = table.join("Alice", client_id="alice-install")
    remote.dispatch({"type": "add_me", "name": "Aria", "hp": 20, "hp_max": 20, "ac": 15})
    table.settle(lambda: "Aria" in rows(remote))
    svc.leave()
    table.settle()
    svc2, remote2 = table.join("Alice again", client_id="alice-install")        # same install, new session
    table.settle(lambda: "Aria" in rows(remote2))
    assert rows(remote2)["Aria"].mine and rows(remote2)["Aria"].can_edit


def test_players_can_be_added_by_the_dm_and_removed(table):
    svc, remote = table.join("Alice")
    peer_id = next(p["peer_id"] for p in table.host.peers if p["name"] == "Alice")
    table.dm.dispatch({"type": "add_entry", "kind": "player", "name": "Alice's Fighter", "hp": 40, "hp_max": 40,
                       "ac": 18, "owner": table.host.client_ids[peer_id]})
    table.settle(lambda: "Alice's Fighter" in rows(remote))
    assert rows(remote)["Alice's Fighter"].can_edit
    fighter = rows(remote)["Alice's Fighter"]
    table.dm.dispatch({"type": "remove", "id": fighter.id})
    table.settle(lambda: "Alice's Fighter" not in rows(remote))


def test_malformed_and_oversized_commands_are_refused(table):
    svc, remote = table.join("Alice")
    errors = []
    remote.set_error_handler(errors.append)
    svc._client.send("tracker_cmd", {"cmd": "not a dict"})
    svc._client.send("tracker_cmd", {"cmd": {"type": "add_me", "name": "x" * 20000}})
    svc._client.send("tracker_cmd", {})
    table.settle(lambda: len(errors) >= 3)
    assert len(errors) == 3
    assert table.hub.tracker.state.entries == []


def test_views_are_validated_and_stale_ones_ignored(table):
    svc, remote = table.join("Alice")
    assert not valid_view(None) and not valid_view({"entries": "x"})
    assert not valid_view({"entries": [{"id": 1, "name": "x"}]})
    assert valid_view({"entries": [{"id": "a", "name": "x"}]})
    table.dm.dispatch(S.custom("A"))
    table.settle(lambda: "A" in rows(remote))
    rev = remote.view()["rev"]
    remote._on_service("tracker_state", view={**remote.view(), "rev": rev - 1, "entries": []})   # stale
    assert "A" in rows(remote)
    remote._on_service("tracker_state", view={"entries": [{"id": 5}]})                           # junk
    assert "A" in rows(remote)


def test_the_player_view_clears_when_the_session_ends(table):
    table.dm.dispatch(S.custom("A"))
    svc, remote = table.join("Alice")
    assert rows(remote)
    table.host.leave()
    pump_until(lambda: not rows(remote), table.host, svc)
    assert remote.view()["entries"] == []
    with pytest.raises(T.CommandError):
        remote.dispatch({"type": "start"})
