"""SessionService: the UI-thread view of a session, driven by pump() like the real app."""

import time

import pytest

from lan import protocol as P
from lan.protocol import LanError
from lan.service import CLIENT, HOSTING, JOINING, NONE, SessionService, local_addresses


def pump_until(cond, *services, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for s in services:
            s.pump()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached")


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
            lan_display_name = ""
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
        assert fake.settings.lan_display_name == "Zed"
        assert svc.default_name() == "Zed"
    finally:
        svc.shutdown()
