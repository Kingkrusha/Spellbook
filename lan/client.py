"""The joining side of a LAN session (a player's app).

``connect`` blocks until the host has admitted us (or refused), so call it from a
worker thread, not the UI thread. After that everything arrives on :attr:`events`:

* ``chat`` - ``seq, from, name, text, ts``
* ``dm`` - ``from, name, to, text, ts``
* ``peer_joined`` / ``peer_left`` - ``peer``
* ``error`` - ``code, message`` (a soft error; the session continues)
* ``disconnected`` - ``reason`` (always the last event)
"""

from __future__ import annotations

import asyncio
import secrets
import ssl
import time
from typing import Dict, List, Optional

from lan import protocol as P
from lan.protocol import LanError, ProtocolError
from lan.runtime import EventQueue, LoopThread
from lan.security import client_context

# The host may wait up to a minute for the DM to approve us
CONNECT_TIMEOUT = 75.0


class LanClient:
    def __init__(self, name: str, client_id: Optional[str] = None, password: str = "",
                 app_version: str = "", schema: int = 0):
        self.name = P.clean_name(name)
        self.client_id = client_id or secrets.token_hex(8)
        self._password = password or ""
        self.app_version = app_version
        self.schema = schema

        self.events = EventQueue()
        self.peer_id = ""
        self.host_info: Dict[str, object] = {}
        self._peers: Dict[str, dict] = {}
        self._runner = LoopThread("lan-client")
        self._writer: Optional[asyncio.StreamWriter] = None
        self._send_lock: Optional[asyncio.Lock] = None
        self._closed = False
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and not self._closed

    def peers(self) -> List[dict]:
        return list(self._peers.values())

    # ------------------------------------------------------------------ lifecycle

    def connect(self, host: str, port: int, fingerprint: str, timeout: float = CONNECT_TIMEOUT) -> dict:
        """Join the session. Returns the host's ``welcome`` body. Raises :class:`LanError`."""
        self._runner.start()
        try:
            return self._runner.call(self._connect(host, port, fingerprint), timeout)
        except LanError:
            self._runner.stop()
            raise
        except (asyncio.TimeoutError, TimeoutError):
            self._runner.stop()
            raise LanError("timeout", "The host did not answer in time.")
        except Exception as e:                       # concurrent.futures.TimeoutError and the like
            self._runner.stop()
            if type(e).__name__ == "TimeoutError":
                raise LanError("timeout", "The host did not answer in time.")
            raise LanError("connect", f"Could not join: {e}")

    async def _connect(self, host: str, port: int, fingerprint: str) -> dict:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=client_context(),
                                        ssl_handshake_timeout=P.HANDSHAKE_TIMEOUT),
                P.HANDSHAKE_TIMEOUT + 2)
        except (OSError, asyncio.TimeoutError, ssl.SSLError) as e:
            raise LanError("connect", f"Could not connect to {host}:{port} ({e or 'timed out'}). "
                                      "Check the address and that the host's firewall allows Spellbook.")

        # Nothing is sent until the certificate matches the invite
        if not P.pinned_fingerprint_ok(writer, fingerprint):
            writer.close()
            raise LanError("fingerprint", "The host's security code doesn't match the invite. "
                                          "Either the invite is wrong or someone is pretending to be the host.")
        self._writer = writer
        self._send_lock = asyncio.Lock()
        try:
            await self._send({"type": "hello", "body": {
                "proto": P.PROTOCOL_VERSION, "name": self.name, "client_id": self.client_id,
                "password": self._password, "app_version": self.app_version, "schema": self.schema}})
            frame = await asyncio.wait_for(P.read_frame(reader, P.MAX_FRAME), CONNECT_TIMEOUT)
        except (ProtocolError, OSError, asyncio.TimeoutError) as e:
            writer.close()
            raise LanError("connect", f"The host closed the connection ({e}).")
        body = frame.get("body") if isinstance(frame.get("body"), dict) else {}
        if frame["type"] == "error":
            writer.close()
            raise LanError(str(body.get("code") or "error"), str(body.get("message") or "The host refused."))
        if frame["type"] != "welcome":
            writer.close()
            raise LanError("protocol", "Unexpected reply from the host.")

        self.peer_id = str(body.get("peer_id") or "")
        self.name = str(body.get("name") or self.name)
        self.host_info = body.get("host") if isinstance(body.get("host"), dict) else {}
        self._peers = {p["peer_id"]: p for p in body.get("peers", []) if isinstance(p, dict) and "peer_id" in p}
        self._connected = True
        asyncio.ensure_future(self._read_loop(reader))
        asyncio.ensure_future(self._ping_loop())
        return body

    def close(self) -> None:
        """Leave the session (safe to call more than once)."""
        if self._closed:
            return
        if self._connected:
            try:
                self._runner.call(self._say_bye(), 3)
            except Exception:
                pass
        self._closed = True
        self._connected = False
        self._runner.stop()

    async def _say_bye(self) -> None:
        try:
            await self._send({"type": "bye", "body": {}})
        finally:
            if self._writer is not None:
                self._writer.close()

    # ------------------------------------------------------------- thread-safe API

    def send_chat(self, text: str) -> None:
        text = P.clean_text(text, P.MAX_CHAT)
        if text and self.connected:
            self._runner.submit(self._send_quiet({"type": "chat", "body": {"text": text}}))

    def send_dm(self, peer_id: str, text: str) -> None:
        text = P.clean_text(text, P.MAX_CHAT)
        if text and self.connected:
            self._runner.submit(self._send_quiet({"type": "dm", "body": {"to": peer_id, "text": text}}))

    def send(self, msg_type: str, body: Optional[dict] = None) -> None:
        """Send any other message type (used by later phases)."""
        if self.connected:
            self._runner.submit(self._send_quiet({"type": msg_type, "body": body or {}}))

    # ---------------------------------------------------------------- internals

    async def _send(self, msg: dict) -> None:
        data = P.encode_frame(msg)
        assert self._writer is not None and self._send_lock is not None
        async with self._send_lock:
            self._writer.write(data)
            await asyncio.wait_for(self._writer.drain(), 10)

    async def _send_quiet(self, msg: dict) -> None:
        try:
            await self._send(msg)
        except Exception:
            pass

    async def _ping_loop(self) -> None:
        while self._connected:
            await asyncio.sleep(P.PING_INTERVAL)
            await self._send_quiet({"type": "ping", "body": {}})

    async def _read_loop(self, reader) -> None:
        reason = "The connection was lost."
        try:
            while True:
                msg = await asyncio.wait_for(P.read_frame(reader), P.IDLE_TIMEOUT)
                kind = msg["type"]
                body = msg.get("body") if isinstance(msg.get("body"), dict) else {}
                if kind == "bye":
                    reason = str(body.get("reason") or "The host closed the session.")
                    break
                self._dispatch(kind, msg, body)
        except asyncio.CancelledError:
            reason = "You left the session."
        except (ProtocolError, OSError, asyncio.TimeoutError):
            pass
        finally:
            was_connected = self._connected
            self._connected = False
            if self._writer is not None:
                self._writer.close()
            if was_connected:
                self.events.put("disconnected", reason=reason)

    def _dispatch(self, kind: str, msg: dict, body: dict) -> None:
        sender = str(msg.get("from") or "")
        ts = msg.get("ts") or time.time()
        if kind == "chat":
            self.events.put("chat", seq=body.get("seq", 0), **{"from": sender},
                            name=str(body.get("name") or ""), text=str(body.get("text") or ""), ts=ts)
        elif kind == "dm":
            self.events.put("dm", **{"from": sender}, name=str(body.get("name") or ""),
                            to=str(body.get("to") or ""), text=str(body.get("text") or ""), ts=ts)
        elif kind == "presence":
            peer = body.get("peer")
            if isinstance(peer, dict) and "peer_id" in peer:
                if body.get("event") == "join":
                    self._peers[peer["peer_id"]] = peer
                    self.events.put("peer_joined", peer=peer)
                elif body.get("event") == "leave":
                    self._peers.pop(peer["peer_id"], None)
                    self.events.put("peer_left", peer=peer, reason="")
        elif kind == "error":
            self.events.put("error", code=str(body.get("code") or ""), message=str(body.get("message") or ""))
        elif kind == "pong":
            pass
        else:
            self.events.put("message", kind=kind, sender=sender, body=body, ts=ts)
