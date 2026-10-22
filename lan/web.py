"""Browser players: a small web server inside the DM's app.

While the DM has "Let browsers join" switched on, :class:`WebServer` answers plain HTTP on the local network.
It hands out one page (the files in ``lan/web/``) and accepts a WebSocket on ``/ws``. A browser on that
socket speaks the same JSON messages as the app does over TLS, so once the DM approves it, it is an ordinary
session member: :meth:`lan.host.LanHost.accept` admits and serves it like any app player, and everything the
DM's side already does for players (their filtered view of the map, the turn order, chat and dice) reaches it.

Only the Python standard library is used. The server runs on the session's own event loop thread.

Limits that keep it safe on a shared network:

* it answers only addresses on the local network (private ranges, link-local, loopback and the
  100.64.0.0/10 range VPNs such as Tailscale use);
* the WebSocket must come from the page itself (its ``Origin`` matches the ``Host``), and ``Host`` must be
  an address or a local name, so a web page on the internet can't reach it through the player's browser;
* requests are small and short-lived, and a browser may send only the message types in ``WEB_TYPES``
  (see ``lan/host.py``): no characters or homebrew.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import json
import os
import struct
from typing import Dict, Optional, Tuple

from lan import protocol as P
from lan.protocol import ConnectionClosed, ProtocolError

DEFAULT_WEB_PORT = 8742
MAX_REQUEST = 8 * 1024             # request line and headers
MAX_WEB_FRAME = 256 * 1024         # largest message a browser may send (a long freehand line is ~20 KB)
REQUEST_TIMEOUT = 10.0
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# The page and its files: published path -> (file in lan/web, content type)
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/table.css": ("table.css", "text/css; charset=utf-8"),
    "/table.js": ("table.js", "text/javascript; charset=utf-8"),
    "/geometry.js": ("geometry.js", "text/javascript; charset=utf-8"),
    "/tabletop.js": ("tabletop.js", "text/javascript; charset=utf-8"),
}

_CGNAT = ipaddress.ip_network("100.64.0.0/10")

SECURITY_HEADERS = (
    "X-Content-Type-Options: nosniff\r\n"
    "Referrer-Policy: no-referrer\r\n"
    "X-Frame-Options: DENY\r\n"
    "Content-Security-Policy: default-src 'self'; img-src 'self' blob: data:; connect-src 'self'; "
    "style-src 'self'; script-src 'self'; frame-ancestors 'none'\r\n"
)


def web_folder() -> str:
    from paths import resource_path
    return resource_path(os.path.join("lan", "web"))


def is_local_address(address: str) -> bool:
    """Whether a connection comes from the local network (or this computer)."""
    try:
        ip = ipaddress.ip_address(str(address).split("%")[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_private or ip.is_loopback or ip.is_link_local or (ip.version == 4 and ip in _CGNAT)


def local_host_name(host_header: str) -> bool:
    """Whether a ``Host`` header names this computer the way a local player would: an IP address, or a
    name with no dots (``localhost``, a computer's name) or ending ``.local`` / ``.lan`` / ``.home``.
    A public name (which is what a "DNS rebinding" trick needs) is refused."""
    host = (host_header or "").strip().lower()
    if not host:
        return False
    if host.startswith("["):                                # [ipv6]:port
        host = host[1:host.find("]")] if "]" in host else ""
    elif host.count(":") == 1:
        host = host.split(":")[0]
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    return "." not in host or host.endswith((".local", ".lan", ".home", ".internal"))


# --------------------------------------------------------------------------- #
# WebSocket framing (RFC 6455): text frames, ping/pong, close
# --------------------------------------------------------------------------- #

def accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode("ascii")).digest()).decode("ascii")


def encode_ws(payload: bytes, opcode: int = 0x1) -> bytes:
    """One unmasked frame from the server."""
    n = len(payload)
    if n < 126:
        head = struct.pack(">BB", 0x80 | opcode, n)
    elif n < 65536:
        head = struct.pack(">BBH", 0x80 | opcode, 126, n)
    else:
        head = struct.pack(">BBQ", 0x80 | opcode, 127, n)
    return head + payload


async def read_ws_frame(reader: asyncio.StreamReader, max_size: int) -> Tuple[bool, int, bytes]:
    """``(final, opcode, payload)`` of one frame from a browser (which must mask what it sends)."""
    try:
        b0, b1 = await reader.readexactly(2)
        n = b1 & 0x7F
        if n == 126:
            (n,) = struct.unpack(">H", await reader.readexactly(2))
        elif n == 127:
            (n,) = struct.unpack(">Q", await reader.readexactly(8))
        if not b1 & 0x80:
            raise ProtocolError("a browser's frames must be masked")
        if n > max_size:
            raise ProtocolError(f"frame of {n} bytes is too large")
        mask = await reader.readexactly(4)
        data = await reader.readexactly(n)
    except asyncio.IncompleteReadError:
        raise ConnectionClosed("connection closed")
    except (ConnectionError, OSError) as e:
        raise ConnectionClosed(str(e))
    if b0 & 0x70:
        raise ProtocolError("unexpected extension bits")
    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(data)) if n < 4096 else _unmask(data, mask)
    return bool(b0 & 0x80), b0 & 0x0F, payload


def _unmask(data: bytes, mask: bytes) -> bytes:
    """XOR a long payload with its mask, a machine word at a time."""
    n = len(data)
    key = int.from_bytes((mask * (n // 4 + 1))[:n], "big")
    return (int.from_bytes(data, "big") ^ key).to_bytes(n, "big")


class WebSocketChannel:
    """A browser player's connection, with the same interface as ``lan.host.StreamChannel``."""

    web = True
    max_frame = MAX_WEB_FRAME

    def __init__(self, reader, writer, address: str):
        self.reader = reader
        self.writer = writer
        self.address = address
        self._lock = asyncio.Lock()
        self._closed = False

    async def read(self, max_size: int = MAX_WEB_FRAME) -> dict:
        """The next JSON message (pings are answered and skipped; a long message may come in pieces)."""
        parts = []
        size = 0
        while True:
            final, opcode, payload = await read_ws_frame(self.reader, min(max_size, MAX_WEB_FRAME))
            if opcode == 0x8:
                raise ConnectionClosed("the browser closed the connection")
            if opcode == 0x9:
                await self._send_raw(encode_ws(payload[:125], 0xA))
                continue
            if opcode == 0xA:
                continue
            if opcode not in (0x0, 0x1, 0x2) or (opcode == 0x0) != bool(parts):
                raise ProtocolError("unexpected frame")
            size += len(payload)
            if size > max_size:
                raise ProtocolError("message too large")
            parts.append(payload)
            if final:
                return P.decode_payload(b"".join(parts))

    async def write(self, msg: dict) -> None:
        data = json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(data) > P.MAX_FRAME:
            raise ProtocolError("message too large to send")
        await self._send_raw(encode_ws(data))

    async def _send_raw(self, frame: bytes) -> None:
        async with self._lock:
            self.writer.write(frame)
            await asyncio.wait_for(self.writer.drain(), 10)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.writer.write(encode_ws(b"", 0x8))
        except Exception:
            pass
        try:
            self.writer.close()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# The HTTP side
# --------------------------------------------------------------------------- #

def parse_request(raw: bytes) -> Tuple[str, str, Dict[str, str]]:
    """``(method, path, headers)`` from a request's head. Header names are lower-cased."""
    try:
        text = raw.decode("latin-1")
    except UnicodeDecodeError:
        raise ProtocolError("bad request")
    lines = text.split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) != 3 or not parts[2].startswith("HTTP/1."):
        raise ProtocolError("bad request line")
    headers: Dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        name, sep, value = line.partition(":")
        if not sep:
            raise ProtocolError("bad header")
        headers[name.strip().lower()] = value.strip()
    path = parts[1].split("?", 1)[0].split("#", 1)[0]
    return parts[0], path, headers


class WebServer:
    """Serves the browser page and its WebSocket for one hosted session (runs on the host's loop)."""

    def __init__(self, host):
        self.host = host                        # the LanHost that admits and serves browser players
        self.port = 0
        self._server: Optional[asyncio.AbstractServer] = None
        self._folder = web_folder()

    async def start(self, bind: str = "0.0.0.0", port: int = DEFAULT_WEB_PORT) -> int:
        self._server = await asyncio.start_server(self._on_connect, bind, port, limit=MAX_REQUEST * 2)
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None

    @property
    def running(self) -> bool:
        return self._server is not None

    async def _on_connect(self, reader, writer) -> None:
        address = (writer.get_extra_info("peername") or ("?",))[0]
        if not is_local_address(address):
            writer.close()
            return
        try:
            try:
                raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), REQUEST_TIMEOUT)
            except (asyncio.LimitOverrunError, asyncio.IncompleteReadError, asyncio.TimeoutError):
                writer.close()
                return
            if len(raw) > MAX_REQUEST:
                await self._respond(writer, 431, "text/plain", b"Request too large.")
                return
            try:
                method, path, headers = parse_request(raw)
            except ProtocolError:
                await self._respond(writer, 400, "text/plain", b"Bad request.")
                return
            if not local_host_name(headers.get("host", "")):
                await self._respond(writer, 421, "text/plain", b"Open this page by the address the DM gave you.")
                return
            if method != "GET":
                await self._respond(writer, 405, "text/plain", b"Only GET is allowed.", extra="Allow: GET\r\n")
                return
            if path == "/ws":
                await self._websocket(reader, writer, headers, address)
                return
            if path == "/info":
                await self._respond(writer, 200, "application/json", json.dumps(self.info()).encode("utf-8"))
                return
            await self._file(writer, path)
        except (ConnectionError, OSError, asyncio.TimeoutError):
            pass
        finally:
            if not writer.is_closing():
                writer.close()

    def info(self) -> dict:
        """What the join page shows before anyone joins."""
        host = self.host
        return {"name": host.display_name, "password": bool(host._password), "approval": host.require_approval,
                "proto": P.PROTOCOL_VERSION, "app": host.app_version,
                "full": len(host._peers) >= host.max_peers}

    async def _file(self, writer, path: str) -> None:
        entry = FILES.get(path)
        if entry is None:
            await self._respond(writer, 404, "text/plain", b"Not found.")
            return
        name, kind = entry
        try:
            with open(os.path.join(self._folder, name), "rb") as f:
                data = f.read()
        except OSError:
            await self._respond(writer, 404, "text/plain", b"Not found.")
            return
        await self._respond(writer, 200, kind, data)

    @staticmethod
    async def _respond(writer, status: int, kind: str, body: bytes, extra: str = "") -> None:
        reason = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed",
                  421: "Misdirected Request", 426: "Upgrade Required",
                  431: "Request Header Fields Too Large"}.get(status, "Error")
        head = (f"HTTP/1.1 {status} {reason}\r\nContent-Type: {kind}\r\nContent-Length: {len(body)}\r\n"
                f"Cache-Control: no-cache\r\nConnection: close\r\n{SECURITY_HEADERS}{extra}\r\n")
        writer.write(head.encode("latin-1") + body)
        await asyncio.wait_for(writer.drain(), 10)

    async def _websocket(self, reader, writer, headers: Dict[str, str], address: str) -> None:
        key = headers.get("sec-websocket-key", "")
        if headers.get("upgrade", "").lower() != "websocket" or "upgrade" not in headers.get("connection", "").lower() \
                or not key or headers.get("sec-websocket-version") != "13":
            await self._respond(writer, 426, "text/plain", b"This address is for the Spellbook page's connection.",
                                extra="Sec-WebSocket-Version: 13\r\n")
            return
        origin = headers.get("origin", "")
        if origin and origin.split("://", 1)[-1].rstrip("/").lower() != headers.get("host", "").lower():
            await self._respond(writer, 403, "text/plain", b"Only the Spellbook page may connect here.")
            return
        writer.write(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept_key(key)}\r\n\r\n").encode("latin-1"))
        await asyncio.wait_for(writer.drain(), 10)
        await self.host.accept(WebSocketChannel(reader, writer, address))
