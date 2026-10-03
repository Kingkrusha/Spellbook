"""Discovery: probe/reply over UDP on loopback, using a private port per test."""

import json
import socket
import time

import pytest

from lan import discovery as D
from lan import protocol as P
from lan.client import LanClient
from lan.host import LanHost
from lan.service import SessionService
from tests.test_lan import wait_for  # noqa: F401  (shared helper)


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def dport():
    return free_udp_port()


def reply_bytes(**over):
    msg = {"m": "SBK1", "name": "DM", "port": 5150, "fp": "A" * 26, "app": "1.0", "players": 2,
           "pw": True, "ap": False, "id": "abc"}
    msg.update(over)
    return json.dumps(msg).encode()


def test_parse_reply_accepts_valid_and_cleans_fields():
    s = D.parse_reply(reply_bytes(name="  The\x00 DM "), "10.0.0.5")
    assert (s.name, s.address, s.port, s.players, s.password, s.approval) == ("The DM", "10.0.0.5", 5150, 2, True, False)
    assert s.invite().encode().startswith("10.0.0.5:5150#")
    assert len(s.security_code.replace("-", "")) == 10


@pytest.mark.parametrize("bad", [
    b"", b"garbage", b"[]", b'{"m":"nope"}',
    reply_bytes(port=0), reply_bytes(port=70000), reply_bytes(port="5150"), reply_bytes(port=True),
    reply_bytes(fp="TOO-SHORT"), reply_bytes(fp=None),
    b"x" * 600,
])
def test_parse_reply_rejects_bad_input(bad):
    assert D.parse_reply(bad, "10.0.0.5") is None


def test_the_address_comes_from_the_packet_not_the_payload():
    s = D.parse_reply(reply_bytes(address="6.6.6.6", ip="6.6.6.6"), "10.0.0.5")
    assert s.address == "10.0.0.5"


def test_responder_answers_probes_and_ignores_the_rest(dport):
    r = D.DiscoveryResponder(lambda: {"name": "DM", "port": 5150, "fp": "B" * 26}, port=dport, bind="127.0.0.1")
    assert r.start()
    try:
        found = D.scan(timeout=1.0, port=dport, targets=["127.0.0.1"])
        assert [(f.name, f.port) for f in found] == [("DM", 5150)]

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.6)
        for junk in (b"hello", D.PROBE, b"x" * 100):             # short / unpadded / wrong magic
            sock.sendto(junk, ("127.0.0.1", dport))
            with pytest.raises(socket.timeout):
                sock.recvfrom(1024)
        sock.close()
    finally:
        r.stop()


def test_responder_rate_limits_each_asker(dport):
    r = D.DiscoveryResponder(lambda: {"name": "DM", "port": 5150, "fp": "B" * 26}, port=dport, bind="127.0.0.1")
    assert r.start()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        for _ in range(5):
            sock.sendto(D.make_probe(), ("127.0.0.1", dport))
        got = 0
        try:
            while True:
                sock.recvfrom(1024)
                got += 1
        except socket.timeout:
            pass
        assert got == 1
        sock.close()
    finally:
        r.stop()


def test_responder_start_fails_quietly_when_port_is_taken(dport):
    a = D.DiscoveryResponder(lambda: {}, port=dport, bind="127.0.0.1")
    assert a.start()
    try:
        # SO_REUSEADDR lets a second one bind on Windows; on others it fails. Either way: no exception
        b = D.DiscoveryResponder(lambda: {}, port=dport, bind="127.0.0.1")
        b.start()
        b.stop()
    finally:
        a.stop()


def test_scan_with_nobody_there_returns_nothing(dport):
    assert D.scan(timeout=0.5, port=dport, targets=["127.0.0.1"]) == []


def test_broadcast_targets():
    t = D.broadcast_targets(["192.168.50.123", "10.1.2.3", "weird"])
    assert t == ["255.255.255.255", "192.168.50.255", "10.1.2.255"]


def test_host_is_found_and_can_be_joined_through_discovery(dport):
    host = LanHost("Zed the DM", require_approval=False, password="pw", discovery_port=dport)
    host.start(port=0, bind="127.0.0.1")
    client = None
    try:
        assert host.discovery_active
        found = D.scan(timeout=1.0, port=dport, targets=["127.0.0.1"])
        assert len(found) == 1
        f = found[0]
        assert f.name == "Zed the DM" and f.password and not f.approval and f.port == host.port
        assert f.fingerprint == host.fingerprint
        client = LanClient("Alice", password="pw")
        client.connect(f.address, f.port, f.fingerprint, timeout=10)
        wait_for(host.events, "peer_joined")
        # the player count is advertised
        assert D.scan(timeout=1.0, port=dport, targets=["127.0.0.1"])[0].players == 1
    finally:
        if client:
            client.close()
        host.stop()
    time.sleep(0.2)
    assert D.scan(timeout=0.6, port=dport, targets=["127.0.0.1"]) == []     # gone when the session ends


def test_a_forged_advertisement_fails_the_certificate_check(dport):
    """Someone advertises the real host's address but with their own fingerprint: connecting refuses."""
    host = LanHost("Real DM", require_approval=False)
    host.start(port=0, bind="127.0.0.1")
    try:
        forged = D.parse_reply(reply_bytes(port=host.port, fp="Q" * 26), "127.0.0.1")
        with pytest.raises(P.LanError) as exc:
            LanClient("Alice").connect(forged.address, forged.port, forged.fingerprint, timeout=10)
        assert exc.value.code == "fingerprint"
    finally:
        host.stop()


def test_service_scan_and_join_found(dport):
    host, guest = SessionService(), SessionService()
    host.start_host("DM", require_approval=False, port=0, bind="127.0.0.1",
                    discoverable=True, discovery_port=dport)
    try:
        assert host.discovery_visible
        guest.scan(timeout=1.0, port=dport, targets=["127.0.0.1"])
        assert guest.scanning and guest.needs_pump
        deadline = time.time() + 5
        while guest.scanning and time.time() < deadline:
            guest.pump()
            time.sleep(0.05)
        assert [d.name for d in guest.discovered] == ["DM"]
        guest.join_found(guest.discovered[0], "Alice")
        deadline = time.time() + 8
        while guest.role != "client" and time.time() < deadline:
            guest.pump()
            host.pump()
            time.sleep(0.05)
        assert guest.role == "client" and guest.host_name == "DM"
    finally:
        host.shutdown()
        guest.shutdown()


def test_not_discoverable_means_not_found(dport):
    host = SessionService()
    host.start_host("DM", require_approval=False, port=0, bind="127.0.0.1",
                    discoverable=False, discovery_port=dport)
    try:
        assert not host.discovery_visible
        assert D.scan(timeout=0.6, port=dport, targets=["127.0.0.1"]) == []
    finally:
        host.shutdown()
