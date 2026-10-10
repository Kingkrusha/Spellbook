"""Transfers over the network: relay through the host, the inbox, replies and limits."""

import time

import pytest

from lan import protocol as P
from lan import service as svc
from lan.client import LanClient
from lan.host import LanHost
from lan.service import CLIENT, SessionService
from tests.test_lan import no_event, wait_for

PAYLOAD = {"format": "spellbook-transfer", "version": 1, "kind": "content",
           "content": {"spells": [{"name": "Zzz"}]}}


def pump_until(cond, *services, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for s in services:
            s.pump()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached")


@pytest.fixture()
def trio():
    host = SessionService()
    port = host.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
    invite = P.Invite("127.0.0.1", port, host._host.fingerprint).encode()
    alice, bob = SessionService(), SessionService()
    for g, name in ((alice, "Alice"), (bob, "Bob")):
        g.join(invite, name)
        pump_until(lambda g=g: g.role == CLIENT, host, g)
    pump_until(lambda: len(host.peers) == 3 and len(alice.peers) == 3 and len(bob.peers) == 3,
               host, alice, bob)
    yield host, alice, bob
    for s in (host, alice, bob):
        s.shutdown()


def id_of(service, name):
    return next(p["peer_id"] for p in service.peers if p["name"] == name)


def test_player_to_player_through_the_host(trio):
    host, alice, bob = trio
    xfer = alice.send_transfer(id_of(alice, "Bob"), PAYLOAD, "Zzz Bolt")
    assert xfer
    pump_until(lambda: bob.inbox and alice.outbox[xfer]["status"] == "delivered", host, alice, bob)
    item = bob.inbox[0]
    assert (item["name"], item["title"], item["payload"]) == ("Alice", "Zzz Bolt", PAYLOAD)
    assert item["from"] == alice.my_id and not host.inbox                 # the host relays, it doesn't keep
    assert any("Alice sent you" in l["text"] for l in bob.chat)

    bob.finish_item(item["item_id"])                                       # accepted and imported
    assert bob.inbox == []
    pump_until(lambda: alice.outbox[xfer]["status"] == "imported", host, alice, bob)
    assert any("Bob added" in l["text"] for l in alice.chat)


def test_declining_tells_the_sender(trio):
    host, alice, bob = trio
    xfer = alice.send_transfer(id_of(alice, "Bob"), PAYLOAD, "A thing")
    pump_until(lambda: bob.inbox, host, alice, bob)
    bob.decline_item(bob.inbox[0]["item_id"], "Not now")
    pump_until(lambda: alice.outbox[xfer]["status"] == "declined", host, alice, bob)
    assert any("Bob declined" in l["text"] and "Not now" in l["text"] for l in alice.chat)


def test_host_can_send_and_receive(trio):
    host, alice, bob = trio
    host.send_transfer(id_of(host, "Alice"), PAYLOAD, "From the DM")
    pump_until(lambda: alice.inbox, host, alice)
    assert alice.inbox[0]["name"] == "DM" and alice.inbox[0]["from"] == "host"

    xfer = alice.send_transfer("host", PAYLOAD, "To the DM")
    pump_until(lambda: host.inbox, host, alice)
    assert host.inbox[0]["name"] == "Alice"
    host.finish_item(host.inbox[0]["item_id"])
    pump_until(lambda: alice.outbox[xfer]["status"] == "imported", host, alice)


def test_send_to_everyone(trio):
    host, alice, bob = trio
    assert host.send_transfer_to_all(PAYLOAD, "Handout") == 2
    pump_until(lambda: alice.inbox and bob.inbox, host, alice, bob)
    assert alice.send_transfer_to_all(PAYLOAD, "Hi") == 2                  # host + bob


def test_cannot_send_to_yourself_or_a_stranger(trio):
    host, alice, bob = trio
    assert alice.send_transfer(alice.my_id, PAYLOAD, "x") is None
    assert alice.send_transfer("nobody", PAYLOAD, "x") is None
    # a peer that left between the click and the send is reported by the host
    gone = id_of(alice, "Bob")
    bob.leave()
    pump_until(lambda: not alice.peer_name(gone), host, alice)
    assert alice.send_transfer(gone, PAYLOAD, "x") is None


def test_host_reports_a_recipient_that_vanished(trio):
    host, alice, bob = trio
    bob_id = id_of(alice, "Bob")
    xfer = alice.send_transfer(bob_id, PAYLOAD, "Late")
    host.kick(bob_id)                                                      # race: gone before the relay
    pump_until(lambda: alice.outbox[xfer]["status"] in ("delivered", "failed"), host, alice)


def test_inbox_limits(trio, monkeypatch):
    host, alice, bob = trio
    monkeypatch.setattr(svc, "MAX_INBOX_ITEMS", 2)
    xfers = [alice.send_transfer(id_of(alice, "Bob"), PAYLOAD, f"item {i}") for i in range(3)]
    pump_until(lambda: alice.outbox[xfers[2]]["status"] == "declined", host, alice, bob)
    assert len(bob.inbox) == 2
    assert any("inbox is full" in l["text"] for l in bob.chat)
    assert any("inbox is full" in l["text"].lower() for l in alice.chat)


def test_inbox_byte_limit(trio, monkeypatch):
    host, alice, bob = trio
    monkeypatch.setattr(svc, "MAX_INBOX_BYTES", 500)
    big = {**PAYLOAD, "content": {"spells": [{"name": "x" * 800}]}}
    xfer = alice.send_transfer(id_of(alice, "Bob"), big, "big")
    pump_until(lambda: alice.outbox[xfer]["status"] == "declined", host, alice, bob)
    assert bob.inbox == []


def test_transfers_are_rate_limited_per_sender():
    h = LanHost("DM", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    a = LanClient("Alice")
    a.connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
    try:
        statuses = []
        for i in range(8):
            a.send_xfer("host", f"id{i}", "t", PAYLOAD)
        deadline = time.time() + 5
        while len(statuses) < 8 and time.time() < deadline:
            ev = a.events.get(timeout=0.2)
            if ev and ev["type"] == "xfer_status":
                statuses.append(ev["status"])
        assert statuses.count("delivered") == 4                            # the burst allowance
        assert statuses.count("failed") == 4
    finally:
        a.close()
        h.stop()


def test_malformed_transfers_are_rejected():
    h = LanHost("DM", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    a = LanClient("Alice")
    a.connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
    try:
        a.send("xfer", {"to": "host", "xfer_id": "", "payload": PAYLOAD})
        assert wait_for(a.events, "xfer_status")["status"] == "failed"
        a.send("xfer", {"to": "host", "xfer_id": "abc", "payload": "not a dict"})
        assert wait_for(a.events, "xfer_status")["status"] == "failed"
        a.send("xfer", {"to": "ghost", "xfer_id": "abc", "payload": PAYLOAD})
        assert wait_for(a.events, "xfer_status")["detail"]
        a.send("xfer_reply", {"to": "host", "xfer_id": "abc", "status": "hacked"})      # unknown status
        assert no_event(h.events, "xfer_reply", 0.4)
        assert no_event(h.events, "xfer", 0.1)
    finally:
        a.close()
        h.stop()


def test_peer_versions_are_visible():
    host = SessionService(app_version="9.9")
    port = host.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
    guest = SessionService(app_version="1.2")
    try:
        guest.join(P.Invite("127.0.0.1", port, host._host.fingerprint).encode(), "Alice")
        pump_until(lambda: guest.role == CLIENT, host, guest)
        pump_until(lambda: len(host.peers) == 2, host, guest)
        assert {p["name"]: p.get("app") for p in host.peers} == {"DM": "9.9", "Alice": "1.2"}
    finally:
        host.shutdown()
        guest.shutdown()
