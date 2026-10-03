"""The hosting side of a LAN session (the DM's app).

Every client connects here; the host admits them, relays chat and direct messages,
and is the only place game state will live. All of this runs on the host's private
event-loop thread - the UI talks to it through the thread-safe methods below and
reads :attr:`LanHost.events`.

Events put on ``events`` (all plain dicts with a ``type``):

* ``peer_joined`` / ``peer_left`` - ``peer`` is ``{peer_id, name, is_host}``
* ``chat`` - ``seq, from, name, text, ts`` (includes the host's own messages)
* ``roll`` - ``seq, from, name, expr, detail, total, label, crit, private, ts``
* ``error`` - ``code, message`` (the host typed something invalid, e.g. a bad ``/roll``)
* ``dm`` - ``from, name, to, text, ts`` (only DMs sent to or by the host)
* ``approval_request`` - ``request_id, name, address``; answer with :meth:`resolve_approval`
"""

from __future__ import annotations

import asyncio
import hmac
import secrets
import time
from typing import Awaitable, Callable, Dict, List, Optional

from lan import dice
from lan import protocol as P
from lan.protocol import LanError, ProtocolError
from lan.runtime import EventQueue, LoopThread
from lan.security import generate_session_cert, server_context

HOST_ID = "host"
MAX_PENDING = 8                 # connections still being admitted
APPROVAL_TIMEOUT = 60.0         # how long the DM has to say yes
MAX_STRIKES = 20                # rate-limit violations before a peer is dropped

Handler = Callable[["LanHost", "_Peer", dict], Awaitable[None]]


class _Bucket:
    """Token bucket: ``rate`` messages per second with a burst allowance."""

    def __init__(self, rate: float = 5.0, burst: float = 10.0):
        self.rate, self.burst = rate, burst
        self.tokens = burst
        self.stamp = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.burst, self.tokens + (now - self.stamp) * self.rate)
        self.stamp = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class _Peer:
    def __init__(self, peer_id: str, name: str, client_id: str, reader, writer, address: str):
        self.peer_id = peer_id
        self.name = name
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.address = address
        self.bucket = _Bucket()
        self.strikes = 0
        self.dropped = False
        self._lock = asyncio.Lock()

    def public(self) -> dict:
        return {"peer_id": self.peer_id, "name": self.name, "is_host": False}

    async def send(self, msg: dict) -> None:
        data = P.encode_frame(msg)
        async with self._lock:
            self.writer.write(data)
            await asyncio.wait_for(self.writer.drain(), 10)

    def close(self) -> None:
        try:
            self.writer.close()
        except Exception:
            pass


class LanHost:
    def __init__(self, display_name: str = "DM", password: str = "", require_approval: bool = True,
                 max_peers: int = 12, app_version: str = "", schema: int = 0):
        self.display_name = P.clean_name(display_name, "DM")
        self._password = password or ""
        self.require_approval = require_approval
        self.max_peers = max_peers
        self.app_version = app_version
        self.schema = schema

        self.events = EventQueue()
        self.fingerprint = ""
        self.port = 0

        self._runner = LoopThread("lan-host")
        self._server: Optional[asyncio.AbstractServer] = None
        self._peers: Dict[str, _Peer] = {}
        self._approvals: Dict[str, "asyncio.Future[tuple]"] = {}
        self._handlers: Dict[str, Handler] = {}
        self._pending = 0
        self._seq = 0
        self._public: List[dict] = []          # snapshot for other threads
        self._started = False

        self.register_handler("chat", self._on_chat)
        self.register_handler("dm", self._on_dm)

    # ------------------------------------------------------------------ lifecycle

    def start(self, port: int = P.DEFAULT_PORT, bind: str = "0.0.0.0") -> int:
        """Begin listening (``port=0`` picks a free one). Returns the port. Raises LanError."""
        cert_pem, key_pem, self.fingerprint = generate_session_cert()
        ctx = server_context(cert_pem, key_pem)
        self._runner.start()
        try:
            self.port = self._runner.call(self._listen(bind, port, ctx), 10)
        except OSError as e:
            self._runner.stop()
            raise LanError("listen", f"Could not start the session on port {port}: {e}")
        self._started = True
        self._refresh_public()
        return self.port

    async def _listen(self, bind: str, port: int, ctx) -> int:
        self._server = await asyncio.start_server(
            self._on_connect, bind, port, ssl=ctx, ssl_handshake_timeout=P.HANDSHAKE_TIMEOUT)
        return self._server.sockets[0].getsockname()[1]

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        try:
            self._runner.call(self._shutdown(), 8)
        except Exception:
            pass
        self._runner.stop()

    async def _shutdown(self) -> None:
        if self._server is not None:
            self._server.close()
        for fut in list(self._approvals.values()):
            if not fut.done():
                fut.set_result((False, "The session closed."))
        for peer in list(self._peers.values()):
            await self._drop(peer, "The host closed the session.", notify=True)

    @property
    def running(self) -> bool:
        return self._started

    def invite(self, address: str) -> P.Invite:
        """The invite a player needs; ``address`` is this machine's LAN/VPN address."""
        return P.Invite(address, self.port, self.fingerprint)

    def peers(self) -> List[dict]:
        """Everyone in the session including the host (safe from any thread)."""
        return list(self._public)

    def _refresh_public(self) -> None:
        self._public = [{"peer_id": HOST_ID, "name": self.display_name, "is_host": True}] + \
                       [p.public() for p in self._peers.values()]

    def register_handler(self, msg_type: str, handler: Handler) -> None:
        """Handle an extra message type from clients (runs on the host thread)."""
        self._handlers[msg_type] = handler

    # ------------------------------------------------------------- thread-safe API

    def send_chat(self, text: str) -> None:
        """Say something as the host (``/roll`` and friends are handled in a later phase)."""
        text = P.clean_text(text, P.MAX_CHAT)
        if text and self._started:
            self._runner.call_soon(lambda: self._handle_text(HOST_ID, self.display_name, text))

    def send_dm(self, peer_id: str, text: str) -> None:
        text = P.clean_text(text, P.MAX_CHAT)
        if text and self._started:
            self._runner.submit(self._host_dm(peer_id, text))

    def kick(self, peer_id: str, reason: str = "You were removed from the session.") -> None:
        if self._started:
            self._runner.submit(self._kick(peer_id, reason))

    def resolve_approval(self, request_id: str, accept: bool, reason: str = "The DM declined.") -> None:
        def go():
            fut = self._approvals.get(request_id)
            if fut is not None and not fut.done():
                fut.set_result((accept, reason))
        if self._started:
            self._runner.call_soon(go)

    # ----------------------------------------------------------- loop-thread internals

    def _emit(self, kind: str, **fields) -> None:
        self.events.put(kind, **fields)

    async def _on_connect(self, reader, writer) -> None:
        if self._pending >= MAX_PENDING:
            writer.close()
            return
        self._pending += 1
        peer: Optional[_Peer] = None
        try:
            try:
                peer = await self._admit(reader, writer)
            except LanError as e:
                try:
                    writer.write(P.encode_frame({"type": "error", "body": {"code": e.code, "message": e.message}}))
                    await asyncio.wait_for(writer.drain(), 3)
                except Exception:
                    pass
                writer.close()
                return
            except (ProtocolError, asyncio.TimeoutError, OSError):
                writer.close()
                return
        finally:
            self._pending -= 1

        try:
            await self._serve(peer)
        except (ProtocolError, asyncio.TimeoutError, OSError):
            pass
        finally:
            await self._drop(peer, "")

    async def _admit(self, reader, writer) -> _Peer:
        hello = await asyncio.wait_for(P.read_frame(reader, P.MAX_PREAUTH_FRAME), P.HANDSHAKE_TIMEOUT)
        body = hello.get("body")
        if hello["type"] != "hello" or not isinstance(body, dict):
            raise LanError("protocol", "Expected a hello message.")
        if body.get("proto") != P.PROTOCOL_VERSION:
            raise LanError("version", "This session uses a different version of the Spellbook network "
                                      "protocol. Please make sure everyone is on the same app version.")
        if self._password:
            given = str(body.get("password") or "")
            if not hmac.compare_digest(given.encode("utf-8"), self._password.encode("utf-8")):
                await asyncio.sleep(0.5)               # slows down guessing
                raise LanError("password", "Wrong session password.")
        if len(self._peers) >= self.max_peers:
            raise LanError("full", "The session is full.")

        name = P.clean_name(body.get("name"))
        client_id = P.clean_text(body.get("client_id"), 64) or secrets.token_hex(8)
        address = (writer.get_extra_info("peername") or ("?",))[0]

        if self.require_approval:
            accepted, reason = await self._ask_dm(name, address)
            if not accepted:
                raise LanError("declined", reason)

        # The same install reconnecting replaces its stale connection
        for old in [p for p in self._peers.values() if p.client_id == client_id]:
            await self._drop(old, "Replaced by a new connection.", notify=True)

        peer = _Peer(self._new_peer_id(), self._unique_name(name), client_id, reader, writer, address)
        await peer.send({"type": "welcome", "from": HOST_ID, "ts": time.time(), "body": {
            "peer_id": peer.peer_id,
            "name": peer.name,
            "host": {"peer_id": HOST_ID, "name": self.display_name, "app_version": self.app_version,
                     "schema": self.schema},
            "peers": self.peers() + [peer.public()],
            "protocol": P.PROTOCOL_VERSION,
        }})
        self._peers[peer.peer_id] = peer
        self._refresh_public()
        await self._broadcast({"type": "presence", "from": HOST_ID, "ts": time.time(),
                               "body": {"event": "join", "peer": peer.public()}}, exclude=peer.peer_id)
        self._emit("peer_joined", peer=peer.public())
        return peer

    async def _ask_dm(self, name: str, address: str):
        request_id = secrets.token_hex(6)
        fut: "asyncio.Future[tuple]" = asyncio.get_running_loop().create_future()
        self._approvals[request_id] = fut
        self._emit("approval_request", request_id=request_id, name=name, address=address)
        try:
            return await asyncio.wait_for(fut, APPROVAL_TIMEOUT)
        except asyncio.TimeoutError:
            return False, "The DM did not answer in time."
        finally:
            self._approvals.pop(request_id, None)

    def _new_peer_id(self) -> str:
        while True:
            pid = secrets.token_hex(4)
            if pid not in self._peers and pid != HOST_ID:
                return pid

    def _unique_name(self, name: str) -> str:
        taken = {p.name.lower() for p in self._peers.values()} | {self.display_name.lower()}
        if name.lower() not in taken:
            return name
        n = 2
        while f"{name} ({n})".lower() in taken:
            n += 1
        return f"{name} ({n})"

    async def _serve(self, peer: _Peer) -> None:
        while not peer.dropped:
            msg = await asyncio.wait_for(P.read_frame(peer.reader), P.IDLE_TIMEOUT)
            kind = msg["type"]
            body = msg.get("body")
            body = body if isinstance(body, dict) else {}
            if kind == "bye":
                return
            if kind == "ping":
                await peer.send({"type": "pong", "from": HOST_ID, "ts": time.time(), "body": {}})
                continue
            if not peer.bucket.allow():
                peer.strikes += 1
                if peer.strikes >= MAX_STRIKES:
                    raise ProtocolError("too many messages")
                await peer.send({"type": "error", "from": HOST_ID, "ts": time.time(),
                                 "body": {"code": "rate_limited", "message": "You are sending too fast."}})
                continue
            handler = self._handlers.get(kind)
            if handler is None:
                await peer.send({"type": "error", "from": HOST_ID, "ts": time.time(),
                                 "body": {"code": "unknown_type", "message": f"Unknown message type '{kind[:30]}'."}})
                continue
            await handler(self, peer, body)

    async def _drop(self, peer: _Peer, reason: str, notify: bool = False) -> None:
        if peer.dropped:
            return
        peer.dropped = True
        if notify:
            try:
                await asyncio.wait_for(peer.send({"type": "bye", "from": HOST_ID, "ts": time.time(),
                                                  "body": {"reason": reason}}), 1.5)
            except Exception:
                pass
        peer.close()
        if self._peers.get(peer.peer_id) is peer:
            del self._peers[peer.peer_id]
            self._refresh_public()
            self._emit("peer_left", peer=peer.public(), reason=reason)
            await self._broadcast({"type": "presence", "from": HOST_ID, "ts": time.time(),
                                   "body": {"event": "leave", "peer": peer.public()}})

    async def _kick(self, peer_id: str, reason: str) -> None:
        peer = self._peers.get(peer_id)
        if peer is not None:
            await self._drop(peer, reason, notify=True)

    async def _broadcast(self, msg: dict, exclude: Optional[str] = None) -> None:
        targets = [p for p in list(self._peers.values()) if p.peer_id != exclude and not p.dropped]
        results = await asyncio.gather(*(p.send(msg) for p in targets), return_exceptions=True)
        for peer, result in zip(targets, results):
            if isinstance(result, Exception):
                asyncio.ensure_future(self._drop(peer, "connection lost"))

    def _post_chat(self, sender_id: str, sender_name: str, text: str) -> None:
        self._seq += 1
        ts = time.time()
        body = {"seq": self._seq, "name": sender_name, "text": text}
        asyncio.ensure_future(self._broadcast({"type": "chat", "from": sender_id, "ts": ts, "body": body}))
        self._emit("chat", seq=self._seq, **{"from": sender_id}, name=sender_name, text=text, ts=ts)

    # ----------------------------------------------------------------- built-in handlers

    async def _on_chat(self, host: "LanHost", peer: _Peer, body: dict) -> None:
        text = P.clean_text(body.get("text"), P.MAX_CHAT)
        if text:
            self._handle_text(peer.peer_id, peer.name, text)

    ROLL = ("/roll", "/r")
    GM_ROLL = ("/gmroll", "/gr")

    def _handle_text(self, sender_id: str, name: str, text: str) -> None:
        """Chat text from anyone (including the host): a plain message or a ``/command``."""
        cmd, rest = dice.split_command(text)
        if not cmd:
            self._post_chat(sender_id, name, text)
        elif cmd in self.ROLL + self.GM_ROLL:
            try:
                result = dice.roll(rest)
            except dice.DiceError as e:
                self._tell(sender_id, "bad_roll", str(e))
                return
            self._post_roll(sender_id, name, result, private=cmd in self.GM_ROLL)
        else:
            self._tell(sender_id, "unknown_command",
                       f"Unknown command {cmd[:20]}. Try /roll 2d6+3, /roll d20+5 adv, or /gmroll d20 "
                       "(only you and the DM see a /gmroll).")

    def _tell(self, peer_id: str, code: str, message: str) -> None:
        """Send a private error notice to one participant."""
        if peer_id == HOST_ID:
            self._emit("error", code=code, message=message)
        elif peer_id in self._peers:
            asyncio.ensure_future(self._send_quiet(self._peers[peer_id], {
                "type": "error", "from": HOST_ID, "ts": time.time(),
                "body": {"code": code, "message": message}}))

    async def _send_quiet(self, peer: _Peer, msg: dict) -> None:
        try:
            await peer.send(msg)
        except Exception:
            await self._drop(peer, "connection lost")

    def _post_roll(self, sender_id: str, name: str, result: "dice.Roll", private: bool) -> None:
        self._seq += 1
        ts = time.time()
        body = {**result.to_body(), "seq": self._seq, "name": name, "private": private}
        msg = {"type": "roll", "from": sender_id, "ts": ts, "body": body}
        if not private:
            asyncio.ensure_future(self._broadcast(msg))
        elif sender_id in self._peers:                 # a /gmroll: only the roller and the host
            asyncio.ensure_future(self._send_quiet(self._peers[sender_id], msg))
        self._emit("roll", **{"from": sender_id}, **body, ts=ts)

    async def _on_dm(self, host: "LanHost", peer: _Peer, body: dict) -> None:
        text = P.clean_text(body.get("text"), P.MAX_CHAT)
        to = body.get("to")
        if not text:
            return
        ts = time.time()
        msg = {"type": "dm", "from": peer.peer_id, "ts": ts,
               "body": {"name": peer.name, "to": to, "text": text}}
        if to == HOST_ID:
            self._emit("dm", **{"from": peer.peer_id}, name=peer.name, to=HOST_ID, text=text, ts=ts)
        elif isinstance(to, str) and to in self._peers and to != peer.peer_id:
            try:
                await self._peers[to].send(msg)
            except Exception:
                asyncio.ensure_future(self._drop(self._peers[to], "connection lost"))
        else:
            await peer.send({"type": "error", "from": HOST_ID, "ts": ts,
                             "body": {"code": "unknown_peer", "message": "That player is not in the session."}})
            return
        await peer.send(msg)            # echo, so the sender's log has it in order

    async def _host_dm(self, peer_id: str, text: str) -> None:
        peer = self._peers.get(peer_id)
        if peer is None:
            return
        ts = time.time()
        msg = {"type": "dm", "from": HOST_ID, "ts": ts,
               "body": {"name": self.display_name, "to": peer_id, "text": text}}
        try:
            await peer.send(msg)
        except Exception:
            await self._drop(peer, "connection lost")
            return
        self._emit("dm", **{"from": HOST_ID}, name=self.display_name, to=peer_id, text=text, ts=ts)
