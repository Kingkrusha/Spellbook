"""Finding sessions on the local network, so players don't have to type an address.

How it works: a *host* answers UDP "probe" packets sent to the discovery port; a *player*
broadcasts a probe and collects the replies for a moment. (Probe-and-reply rather than the host
broadcasting continuously, so the player's firewall never has to accept unsolicited inbound
traffic - only the host's does, and that machine has already allowed Spellbook to listen.)

What it cannot do: broadcasts do not cross routers or most VPNs (Tailscale, Hamachi, ZeroTier), and
some guest/"client isolation" Wi-Fi blocks them. The manual invite always still works.

Trust: a reply is unauthenticated, so anyone on the network can forge one. Replies therefore only
*suggest* where to connect. The advertised certificate fingerprint is shown to the player as a short
security code to compare with what the DM sees, before anything (such as a password) is sent - a
forged advertisement carries the forger's code, which won't match. The source address is taken from
the packet, never from its contents.
"""

from __future__ import annotations

import json
import select
import socket
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from lan import protocol as P

DISCOVERY_PORT = 5151
PROBE = b"SPELLBOOK-PROBE-1"
PROBE_SIZE = 64                  # probes are padded so a reply is never a big amplification of one
REPLY_TAG = "SBK1"
MAX_REPLY = 512
REPLY_GAP = 0.25                 # seconds: at most this often per asker


def make_probe() -> bytes:
    return PROBE.ljust(PROBE_SIZE, b"\0")


def is_probe(data: bytes) -> bool:
    return len(data) >= PROBE_SIZE and data.startswith(PROBE)


@dataclass(frozen=True)
class FoundSession:
    name: str
    address: str
    port: int
    fingerprint: str
    app_version: str = ""
    players: int = 0
    password: bool = False
    approval: bool = True
    session_id: str = ""

    @property
    def security_code(self) -> str:
        """The first 10 characters of the fingerprint, grouped - short enough to compare by eye."""
        return P.format_fingerprint(self.fingerprint[:10])

    def invite(self) -> P.Invite:
        return P.Invite(self.address, self.port, self.fingerprint)


def parse_reply(data: bytes, source_ip: str) -> Optional[FoundSession]:
    """A validated session from a reply packet, or None for anything malformed."""
    if not data or len(data) > MAX_REPLY:
        return None
    try:
        msg = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(msg, dict) or msg.get("m") != REPLY_TAG:
        return None
    port, fp = msg.get("port"), P.normalize_fingerprint(str(msg.get("fp") or ""))
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        return None
    if len(fp) != P.FINGERPRINT_CHARS:
        return None
    players = msg.get("players")
    return FoundSession(
        name=P.clean_name(msg.get("name"), "Session"),
        address=source_ip,
        port=port,
        fingerprint=fp,
        app_version=P.clean_text(msg.get("app"), 20),
        players=players if isinstance(players, int) and 0 <= players < 1000 else 0,
        password=bool(msg.get("pw")),
        approval=bool(msg.get("ap", True)),
        session_id=P.clean_text(msg.get("id"), 32),
    )


# ---------------------------------------------------------------------------
# Host side
# ---------------------------------------------------------------------------

class DiscoveryResponder:
    """Answers probes with ``info_fn()`` (a dict: name, port, fp, app, players, pw, ap, id)."""

    def __init__(self, info_fn: Callable[[], Dict], port: int = DISCOVERY_PORT, bind: str = ""):
        self._info_fn = info_fn
        self.port = port
        self._bind = bind
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_reply: Dict[str, float] = {}

    def start(self) -> bool:
        """Begin answering. Returns False (quietly) if the port can't be used - e.g. another
        Spellbook on this machine already answers on it; the session itself still works."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self._bind, self.port))
        except OSError:
            return False
        self._sock = sock
        self._thread = threading.Thread(target=self._run, name="lan-discovery", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(2)

    def _run(self) -> None:
        sock = self._sock
        while not self._stop.is_set():
            try:
                ready, _, _ = select.select([sock], [], [], 0.4)
                if not ready:
                    continue
                data, addr = sock.recvfrom(1024)
            except (OSError, ValueError):
                return
            if not is_probe(data):
                continue
            now = time.monotonic()
            if now - self._last_reply.get(addr[0], 0.0) < REPLY_GAP:
                continue
            self._last_reply[addr[0]] = now
            if len(self._last_reply) > 256:
                self._last_reply = {k: v for k, v in self._last_reply.items() if now - v < 5}
            try:
                reply = json.dumps({"m": REPLY_TAG, **self._info_fn()}, separators=(",", ":")).encode("utf-8")
                if len(reply) <= MAX_REPLY:
                    sock.sendto(reply, addr)
            except Exception:
                continue


# ---------------------------------------------------------------------------
# Player side
# ---------------------------------------------------------------------------

def broadcast_targets(local_ips: Optional[List[str]] = None) -> List[str]:
    """Where to send a probe: the limited broadcast plus, for every local address, its /24's
    broadcast address (the limited one only leaves through the default network adapter)."""
    if local_ips is None:
        from lan.service import local_addresses
        local_ips = local_addresses()
    targets = ["255.255.255.255"]
    for ip in local_ips:
        parts = ip.split(".")
        if len(parts) == 4:
            targets.append(".".join(parts[:3] + ["255"]))
    return list(dict.fromkeys(targets))


def scan(timeout: float = 1.5, port: int = DISCOVERY_PORT, targets: Optional[List[str]] = None,
         rounds: int = 2) -> List[FoundSession]:
    """Look for sessions. Blocks for about ``timeout`` seconds - call it from a worker thread."""
    targets = targets if targets is not None else broadcast_targets() + ["127.0.0.1"]
    found: Dict[tuple, FoundSession] = {}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        return []
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", 0))
        probe = make_probe()
        deadline = time.monotonic() + timeout
        next_send, sent = 0.0, 0
        while True:
            now = time.monotonic()
            if now >= deadline:
                break
            if sent < rounds and now >= next_send:
                for target in targets:
                    try:
                        sock.sendto(probe, (target, port))
                    except OSError:
                        pass
                sent += 1
                next_send = now + timeout / (rounds + 1)
            ready, _, _ = select.select([sock], [], [], 0.1)
            if not ready:
                continue
            try:
                data, addr = sock.recvfrom(2048)
            except OSError:
                continue
            session = parse_reply(data, addr[0])
            if session is not None:
                found[(session.address, session.port)] = session
    finally:
        sock.close()
    # A host on this very machine answers on both its LAN address and loopback: show it once
    by_id: Dict[str, FoundSession] = {}
    out: List[FoundSession] = []
    for s in found.values():
        if not s.session_id:
            out.append(s)
        elif s.session_id not in by_id or by_id[s.session_id].address.startswith("127."):
            by_id[s.session_id] = s
    out.extend(by_id.values())
    return sorted(out, key=lambda s: (s.name.lower(), s.address))
