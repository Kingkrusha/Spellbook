"""LAN transport tests: framing, invite codes, and real TLS sessions over loopback."""

import asyncio
import json
import struct
import time

import pytest

from lan import protocol as P
from lan import security
from lan.client import LanClient
from lan.host import LanHost
from lan.protocol import LanError


# ---------------------------------------------------------------- helpers

def wait_for(events, kind, timeout=5.0, where=None):
    """Drain ``events`` until one of type ``kind`` (matching ``where``) arrives."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ev = events.get(timeout=0.2)
        if ev and ev["type"] == kind and (where is None or where(ev)):
            return ev
    raise AssertionError(f"no {kind!r} event within {timeout}s")


def no_event(events, kind, wait=0.4):
    deadline = time.time() + wait
    while time.time() < deadline:
        ev = events.get(timeout=0.1)
        if ev and ev["type"] == kind:
            return False
    return True


@pytest.fixture()
def host():
    h = LanHost("Dungeon Master", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    yield h
    h.stop()


def join(host, name, **kw):
    c = LanClient(name, **kw)
    c.connect("127.0.0.1", host.port, host.fingerprint, timeout=10)
    return c


# ---------------------------------------------------------------- protocol

def test_frame_roundtrip():
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(P.encode_frame({"type": "chat", "body": {"text": "héllo ⚔"}}))
        return await P.read_frame(reader)
    assert asyncio.run(run())["body"]["text"] == "héllo ⚔"


@pytest.mark.parametrize("raw", [
    struct.pack(">I", 0),                                   # empty
    struct.pack(">I", P.MAX_FRAME + 1),                     # too big (body never read)
    struct.pack(">I", 5) + b"[1,2]",                        # not an object
    struct.pack(">I", 8) + b'{"a": 1}',                     # no type
    struct.pack(">I", 3) + b"\xff\xfe\xfd",                 # not UTF-8
])
def test_bad_frames_rejected(raw):
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(raw)
        reader.feed_eof()
        await P.read_frame(reader)
    with pytest.raises(P.ProtocolError):
        asyncio.run(run())


def test_preauth_frame_limit():
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(struct.pack(">I", P.MAX_PREAUTH_FRAME + 1))
        await P.read_frame(reader, P.MAX_PREAUTH_FRAME)
    with pytest.raises(P.ProtocolError):
        asyncio.run(run())


def test_clean_text_and_names():
    assert P.clean_text("a\x00b\x07c\nd", 50) == "abc\nd"
    assert P.clean_text(12, 5) == ""
    assert P.clean_text("x" * 100, 10) == "x" * 10
    assert P.clean_name("   ") == "Player"
    assert P.clean_name("A\x00l  ice") == "Al ice"
    assert len(P.clean_name("n" * 99)) == P.MAX_NAME


def test_invite_roundtrip_and_errors():
    cert, key, fp = security.generate_session_cert()
    assert len(fp) == P.FINGERPRINT_CHARS
    inv = P.Invite("192.168.1.20", 5150, fp)
    assert P.Invite.parse(inv.encode()) == inv
    assert P.Invite.parse("spellbook://192.168.1.20:5150/" + P.format_fingerprint(fp).lower()) == inv
    assert P.Invite.parse(f"192.168.1.20#{fp}").port == P.DEFAULT_PORT
    assert P.Invite.parse(P.Invite("::1", 9, fp).encode()).host == "::1"
    for bad in ("", "nonsense", "1.2.3.4:5150", "1.2.3.4:5150#ABC", "1.2.3.4:99999#" + fp):
        with pytest.raises(ValueError):
            P.Invite.parse(bad)


# ---------------------------------------------------------------- sessions

def test_join_and_chat(host):
    a = join(host, "Alice")
    b = join(host, "Bob")
    try:
        assert {p["name"] for p in a.peers()} >= {"Dungeon Master", "Alice"}
        wait_for(host.events, "peer_joined", where=lambda e: e["peer"]["name"] == "Bob")
        wait_for(a.events, "peer_joined", where=lambda e: e["peer"]["name"] == "Bob")

        a.send_chat("hello table")
        for events in (host.events, a.events, b.events):
            ev = wait_for(events, "chat")
            assert ev["text"] == "hello table" and ev["name"] == "Alice"
            assert ev["from"] == a.peer_id

        host.send_chat("welcome")
        ev = wait_for(b.events, "chat", where=lambda e: e["text"] == "welcome")
        assert ev["from"] == "host" and ev["name"] == "Dungeon Master"
    finally:
        a.close()
        b.close()


def test_chat_is_ordered_by_host_sequence(host):
    a = join(host, "Alice")
    try:
        for i in range(5):
            a.send_chat(f"m{i}")
        seqs = [wait_for(a.events, "chat")["seq"] for _ in range(5)]
        assert seqs == sorted(seqs) and len(set(seqs)) == 5
    finally:
        a.close()


def test_direct_messages(host):
    a = join(host, "Alice")
    b = join(host, "Bob")
    c = join(host, "Cara")
    try:
        a.send_dm(b.peer_id, "psst")
        ev = wait_for(b.events, "dm")
        assert ev["text"] == "psst" and ev["from"] == a.peer_id
        wait_for(a.events, "dm")                           # echo to the sender
        assert no_event(c.events, "dm") and no_event(host.events, "dm")

        a.send_dm("host", "for the DM")
        assert wait_for(host.events, "dm")["text"] == "for the DM"

        host.send_dm(c.peer_id, "from the DM")
        assert wait_for(c.events, "dm")["from"] == "host"

        a.send_dm("nobody", "x")
        assert wait_for(a.events, "error")["code"] == "unknown_peer"
    finally:
        for x in (a, b, c):
            x.close()


def test_duplicate_names_are_made_unique(host):
    a = join(host, "Alice")
    b = join(host, "Alice")
    c = join(host, "Dungeon Master")
    try:
        assert (a.name, b.name, c.name) == ("Alice", "Alice (2)", "Dungeon Master (2)")
    finally:
        for x in (a, b, c):
            x.close()


def test_leave_is_announced(host):
    a = join(host, "Alice")
    b = join(host, "Bob")
    try:
        b.close()
        assert wait_for(host.events, "peer_left")["peer"]["name"] == "Bob"
        assert wait_for(a.events, "peer_left")["peer"]["name"] == "Bob"
    finally:
        a.close()


def test_reconnect_replaces_stale_connection(host):
    a = join(host, "Alice", client_id="same-install")
    a2 = join(host, "Alice", client_id="same-install")
    try:
        assert a2.name == "Alice"                               # not "Alice (2)"
        assert wait_for(a.events, "disconnected")
        assert [p["name"] for p in host.peers()].count("Alice") == 1
    finally:
        a.close()
        a2.close()


def test_wrong_fingerprint_is_refused_before_anything_is_sent(host):
    _, _, other_fp = security.generate_session_cert()
    c = LanClient("Mallory")
    with pytest.raises(LanError) as exc:
        c.connect("127.0.0.1", host.port, other_fp, timeout=10)
    assert exc.value.code == "fingerprint"
    time.sleep(0.2)
    assert [p["name"] for p in host.peers()] == ["Dungeon Master"]
    assert no_event(host.events, "peer_joined", 0.2)


def test_password():
    h = LanHost("DM", password="swordfish", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    try:
        with pytest.raises(LanError) as exc:
            LanClient("A", password="wrong").connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
        assert exc.value.code == "password"
        ok = LanClient("A", password="swordfish")
        ok.connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
        ok.close()
    finally:
        h.stop()


def test_approval_flow():
    h = LanHost("DM", require_approval=True)
    h.start(port=0, bind="127.0.0.1")
    try:
        import threading
        result = {}

        def attempt(name, key):
            try:
                c = LanClient(name)
                c.connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
                result[key] = c
            except LanError as e:
                result[key] = e

        t1 = threading.Thread(target=attempt, args=("Alice", "a"))
        t1.start()
        req = wait_for(h.events, "approval_request")
        assert req["name"] == "Alice"
        h.resolve_approval(req["request_id"], True)
        t1.join(10)
        assert result["a"].name == "Alice"
        result["a"].close()

        t2 = threading.Thread(target=attempt, args=("Mallory", "m"))
        t2.start()
        req = wait_for(h.events, "approval_request")
        h.resolve_approval(req["request_id"], False, "Not on the list.")
        t2.join(10)
        assert isinstance(result["m"], LanError) and result["m"].code == "declined"
        assert result["m"].message == "Not on the list."
    finally:
        h.stop()


def test_session_full():
    h = LanHost("DM", require_approval=False, max_peers=1)
    h.start(port=0, bind="127.0.0.1")
    try:
        a = LanClient("A")
        a.connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
        with pytest.raises(LanError) as exc:
            LanClient("B").connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
        assert exc.value.code == "full"
        a.close()
    finally:
        h.stop()


def test_kick(host):
    a = join(host, "Alice")
    try:
        host.kick(a.peer_id, "Out you go.")
        ev = wait_for(a.events, "disconnected")
        assert ev["reason"] == "Out you go."
    finally:
        a.close()


def test_host_stop_disconnects_clients():
    h = LanHost("DM", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    a = LanClient("A")
    a.connect("127.0.0.1", h.port, h.fingerprint, timeout=10)
    h.stop()
    assert wait_for(a.events, "disconnected")["reason"]
    a.close()


def test_rate_limit_drops_flooders(host):
    a = join(host, "Alice")
    try:
        for i in range(60):
            a.send_chat(f"spam {i}")
        wait_for(a.events, "error", where=lambda e: e["code"] == "rate_limited", timeout=8)
    finally:
        a.close()


def test_unknown_message_type_is_reported(host):
    a = join(host, "Alice")
    try:
        a.send("make_me_dm", {})
        assert wait_for(a.events, "error")["code"] == "unknown_type"
    finally:
        a.close()


def test_custom_handler_registration(host):
    seen = []

    async def handler(h, peer, body):
        seen.append((peer.name, body))

    host.register_handler("note", handler)
    a = join(host, "Alice")
    try:
        a.send("note", {"x": 1})
        deadline = time.time() + 3
        while not seen and time.time() < deadline:
            time.sleep(0.05)
        assert seen == [("Alice", {"x": 1})]
    finally:
        a.close()


# ---------------------------------------------------------------- hostile peers

async def _raw(host_port, fingerprint, frames=(), plaintext=False):
    """Open a connection by hand and return whatever the host sends back."""
    from lan.security import client_context
    if plaintext:
        reader, writer = await asyncio.open_connection("127.0.0.1", host_port)
    else:
        reader, writer = await asyncio.open_connection("127.0.0.1", host_port, ssl=client_context())
    for f in frames:
        writer.write(f)
    await writer.drain()
    try:
        data = await asyncio.wait_for(reader.read(65536), 3)
    except Exception:
        data = b""
    writer.close()
    return data


def test_plaintext_client_gets_nothing(host):
    data = asyncio.run(_raw(host.port, host.fingerprint, [b"hello?" * 10], plaintext=True))
    assert b"welcome" not in data
    assert [p["name"] for p in host.peers()] == ["Dungeon Master"]


def test_oversized_preauth_frame_is_dropped(host):
    data = asyncio.run(_raw(host.port, host.fingerprint, [struct.pack(">I", 3 * 1024 * 1024)]))
    assert data == b""


def test_wrong_protocol_version_gets_readable_error(host):
    hello = P.encode_frame({"type": "hello", "body": {"proto": 99, "name": "Old"}})
    data = asyncio.run(_raw(host.port, host.fingerprint, [hello]))
    err = json.loads(data[4:])
    assert err["type"] == "error" and err["body"]["code"] == "version"


def test_garbage_hello_is_rejected(host):
    for payload in (b'{"type":"chat","body":{}}', b'{"type":"hello","body":"x"}'):
        data = asyncio.run(_raw(host.port, host.fingerprint, [struct.pack(">I", len(payload)) + payload]))
        err = json.loads(data[4:]) if data else {"type": "error"}
        assert err["type"] == "error"
    assert [p["name"] for p in host.peers()] == ["Dungeon Master"]
