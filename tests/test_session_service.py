"""SessionService: the UI-thread view of a session, driven by pump() like the real app."""

import time

import pytest

from tests.lan_wait import stall_report

from lan import protocol as P
from lan.protocol import LanError
from lan.service import CLIENT, HOSTING, JOINING, NONE, SessionService, local_addresses


def pump_until(cond, *services, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for s in services:
            s.pump()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached\n" + stall_report(services))


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, kind, **data):
        self.events.append((kind, data))

    def kinds(self):
        return [k for k, _ in self.events]


@pytest.fixture()
def pair():
    host, guest = SessionService(), SessionService()
    port = host.start_host("The DM", require_approval=False, port=0, bind="127.0.0.1")
    invite = P.Invite("127.0.0.1", port, host._host.fingerprint).encode()
    yield host, guest, invite
    host.shutdown()
    guest.shutdown()


def test_local_addresses_are_usable():
    for ip in local_addresses():
        assert not ip.startswith(("127.", "169.254."))


def test_host_state(pair):
    host, _, _ = pair
    assert host.role == HOSTING and host.is_host and host.in_session
    assert [p["name"] for p in host.peers] == ["The DM"]
    assert host.chat[0]["kind"] == "system"
    assert host.invites() and "#" in host.invites()[0][1]


def test_join_chat_and_leave(pair):
    host, guest, invite = pair
    h_rec, g_rec = Recorder(), Recorder()
    host.add_listener(h_rec)
    guest.add_listener(g_rec)

    guest.join(invite, "Alice")
    assert guest.role == JOINING and guest.active and not guest.in_session
    pump_until(lambda: guest.role == CLIENT, host, guest)
    assert guest.host_name == "The DM" and guest.my_name == "Alice"
    pump_until(lambda: len(host.peers) == 2, host, guest)
    assert {p["name"] for p in guest.peers} == {"The DM", "Alice"}

    guest.send_chat("hi everyone")
    pump_until(lambda: any(l["kind"] == "chat" for l in host.chat) and
               any(l["kind"] == "chat" for l in guest.chat), host, guest)
    mine = [l for l in guest.chat if l["kind"] == "chat"][0]
    theirs = [l for l in host.chat if l["kind"] == "chat"][0]
    assert mine["mine"] and not theirs["mine"] and theirs["name"] == "Alice"

    host.send_dm(guest.my_id, "secret")
    pump_until(lambda: any(l["kind"] == "dm" for l in guest.chat), host, guest)
    dm = [l for l in guest.chat if l["kind"] == "dm"][0]
    assert dm["text"] == "secret" and dm["to"] == guest.my_id and dm["name"] == "The DM"

    guest.leave()
    assert guest.role == NONE and guest.peers == [] and "ended" in g_rec.kinds()
    pump_until(lambda: len(host.peers) == 1, host)
    assert any("Alice left" in l["text"] for l in host.chat)


def test_host_ending_ends_the_guests_session(pair):
    host, guest, invite = pair
    guest.join(invite, "Alice")
    pump_until(lambda: guest.role == CLIENT, host, guest)
    host.leave()
    assert host.role == NONE
    pump_until(lambda: guest.role == NONE, guest)
    assert "closed" in guest.last_end_reason.lower() or "host" in guest.last_end_reason.lower()


def test_join_failures_are_reported(pair):
    host, guest, invite = pair
    rec = Recorder()
    guest.add_listener(rec)

    with pytest.raises(LanError) as exc:
        guest.join("not an invite", "Alice")
    assert exc.value.code == "invite" and guest.role == NONE

    wrong = P.Invite("127.0.0.1", host.port, "A" * P.FINGERPRINT_CHARS).encode()
    guest.join(wrong, "Alice")
    pump_until(lambda: guest.role == NONE, guest)
    assert "join_failed" in rec.kinds()
    assert "security code" in rec.events[-2][1]["message"] or "security code" in guest.last_end_reason
    # and it can try again
    guest.join(invite, "Alice")
    pump_until(lambda: guest.role == CLIENT, host, guest)


def test_cannot_start_twice(pair):
    host, _, _ = pair
    with pytest.raises(LanError):
        host.start_host("x", port=0, bind="127.0.0.1")


def test_approval_round_trip():
    host, guest = SessionService(), SessionService()
    port = host.start_host("DM", require_approval=True, port=0, bind="127.0.0.1")
    invite = P.Invite("127.0.0.1", port, host._host.fingerprint).encode()
    rec = Recorder()
    host.add_listener(rec)
    try:
        guest.join(invite, "Alice")
        pump_until(lambda: "approval_request" in rec.kinds(), host, guest)
        req = [d for k, d in rec.events if k == "approval_request"][0]
        assert req["name"] == "Alice"
        host.resolve_approval(req["request_id"], True)
        pump_until(lambda: guest.role == CLIENT, host, guest)
        assert "approval_done" in rec.kinds()
    finally:
        host.shutdown()
        guest.shutdown()


def test_settings_are_remembered():
    class FakeSettings:
        class settings:
            lan_player_name = ""
            lan_port = 5150
            lan_require_approval = True
            lan_client_id = ""
            lan_last_invite = ""

        def update(self, **kw):
            for k, v in kw.items():
                setattr(self.settings, k, v)

    fake = FakeSettings()
    svc = SessionService(fake)
    cid = svc.client_id()
    assert cid and svc.client_id() == cid                       # created once, then stable
    svc.start_host("Zed", port=0, bind="127.0.0.1", require_approval=False)
    try:
        assert fake.settings.lan_player_name == "Zed"
        assert svc.default_name() == "Zed"
    finally:
        svc.shutdown()


def test_the_name_is_never_taken_from_the_computer(monkeypatch):
    """No account/user name is read to suggest or fill in a name: the player is always asked."""
    import getpass
    import os

    def boom(*a, **k):
        raise AssertionError("the session read the computer's user name")

    monkeypatch.setattr(getpass, "getuser", boom)
    monkeypatch.setattr(os, "getlogin", boom)
    monkeypatch.setenv("USERNAME", "SomebodyReal")
    monkeypatch.setenv("USER", "SomebodyReal")

    svc = SessionService()                          # nothing saved yet
    assert svc.default_name() == ""

    class FakeSettings:
        class settings:
            lan_player_name = ""
            lan_port = 5150
            lan_require_approval = True
            lan_client_id = ""
            lan_last_invite = ""

        def update(self, **kw):
            for k, v in kw.items():
                setattr(self.settings, k, v)

    assert SessionService(FakeSettings()).default_name() == ""


def test_a_blank_name_is_refused_for_hosting_and_joining():
    svc = SessionService()
    for blank in ("", "   ", "\t\n", None):
        with pytest.raises(LanError) as e:
            svc.start_host(blank, port=0, bind="127.0.0.1", require_approval=False, discoverable=False)
        assert e.value.code == "name"
        with pytest.raises(LanError) as e:
            svc.join("127.0.0.1:5150#" + "A" * 26, blank)
        assert e.value.code == "name"
    assert svc.role == NONE and not svc.active


def test_players_tell_the_dm_who_they_play(pair):
    import base64
    import io
    from PIL import Image
    host, guest, invite = pair
    other = SessionService()
    try:
        picture = io.BytesIO()
        Image.new("RGB", (40, 40), (200, 30, 30)).save(picture, "JPEG")
        guest.set_my_character({"name": "Aria", "hp": 31, "ac": 15, "summary": "Level 5 Elf Wizard",
                                "portrait": base64.b64encode(picture.getvalue()).decode("ascii")})
        guest.join(invite, "Alice")                    # the character is sent as soon as we're in
        other.join(invite, "Bob")
        pump_until(lambda: guest.role == CLIENT and other.role == CLIENT, host, guest, other)
        pump_until(lambda: host.player_character(guest.my_id).get("name") == "Aria", host, guest, other)
        aria = host.player_character(guest.my_id)
        assert aria["hp"] == aria["hp_max"] == 31 and aria["ac"] == 15 and aria["player"] == "Alice"
        assert aria["client_id"] == host.client_ids[guest.my_id] and aria["portrait"]
        assert any("Alice is playing Aria" in line["text"] for line in host.chat)
        # the other players see the name (not the picture or the numbers)
        pump_until(lambda: any(p.get("character") == "Aria" for p in other.peers), host, guest, other)
        # changing character, then playing nobody
        guest.set_my_character({"name": "Brakka"})
        pump_until(lambda: host.player_character(guest.my_id).get("name") == "Brakka", host, guest, other)
        guest.set_my_character(None)
        pump_until(lambda: not host.player_character(guest.my_id), host, guest, other)
        guest.leave()
        pump_until(lambda: guest.my_id not in host.player_characters and len(host.peers) == 2, host, other)
    finally:
        other.shutdown()


def test_a_character_is_cleaned_up():
    assert P.clean_character({"name": "  "}) == {}
    c = P.clean_character({"name": "A\x00ria " * 20, "hp": 1e9, "ac": True, "portrait": "bm90IGEgcGljdHVyZQ=="})
    assert len(c["name"]) <= 40 and c["hp"] == 9999 and c["ac"] is None and "portrait" not in c
    assert P.clean_character({"name": "Aria", "init": 3})["init"] == 3
    assert P.clean_character({"name": "Aria", "init": -99})["init"] == -20
    assert P.clean_character({"name": "Aria", "init": "fast"})["init"] is None


def test_a_player_keeps_the_dms_copy_of_their_character_current():
    """After a sheet is saved, the player's app re-sends their character only when what the DM sees changed."""
    from types import SimpleNamespace

    from lan.protocol import clean_character
    from lan.service import CLIENT
    from ui.main_window import MainWindow

    info = {"name": "Aria", "hp": 20, "hp_max": 31, "ac": 15, "init": 2, "summary": "Elf Rogue 3 " * 12}
    sent = []
    session = SimpleNamespace(role=CLIENT, my_character=clean_character(info), set_my_character=sent.append)
    app = SimpleNamespace(session=session, _session_character_info=lambda name: dict(info),
                          _played_refresh_after="job")
    MainWindow._refresh_played_character(app)
    assert sent == [] and app._played_refresh_after is None      # (a long summary is cut the same way)
    info["hp"], info["init"] = 12, 3
    MainWindow._refresh_played_character(app)
    assert sent[-1]["hp"] == 12 and sent[-1]["init"] == 3


def test_a_player_gets_only_the_changes_to_the_map(pair, tmp_path):
    import json

    import tabletop as T
    import tabletop_net as N
    host, guest, invite = pair
    table = T.Tabletop(str(tmp_path / "tabletop.json"))
    scene = table.apply({"op": "scene_new", "scene_data": {"name": "Cave", "w": 2000, "h": 2000}})["scene"]
    table.apply({"op": "scene_show", "scene": scene})
    for i in range(20):
        table.apply({"op": "token_add", "scene": scene, "token": {"name": f"Goblin {i}", "x": 25 + 50 * i, "y": 25}})
    link = N.TableHostLink(host, table, T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c")))
    sent = []
    real = host.send_table_patch
    host.send_table_patch = lambda *a: sent.append(a) or real(*a)
    guest.join(invite, "Alice")
    pump_until(lambda: guest.role == CLIENT, host, guest)
    remote = N.RemoteTable(guest, T.AssetStore(str(tmp_path / "pa"), str(tmp_path / "pc")))
    pump_until(lambda: (remote.view().get("scene") or {}).get("id") == scene and remote._view_seq is not None,
               host, guest)
    pump_until(lambda: not remote._syncing, host, guest)
    token = table.scenes[scene]["tokens"][5]["id"]
    table.apply({"op": "token_move", "scene": scene, "id": token, "x": 525, "y": 525})
    want = json.loads(json.dumps(table.view_for(N._player_key(host, guest.my_id))))
    pump_until(lambda: remote.view() == want, host, guest)
    assert sent                                        # it came as a patch
    link.close()
    remote.close()
