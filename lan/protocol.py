"""Wire format shared by host and client: framing, limits, invite codes.

A frame is a 4-byte big-endian length followed by that many bytes of UTF-8 JSON. The
JSON is an object with at least a string ``type``. The host stamps ``from`` and ``ts``
on everything it relays, so a client can never claim to be someone else.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import re
import struct
from dataclasses import dataclass
from typing import Optional

PROTOCOL_VERSION = 1
DEFAULT_PORT = 5150

MAX_FRAME = 4 * 1024 * 1024        # largest frame we will ever read (object transfers, later)
MAX_PREAUTH_FRAME = 4 * 1024       # before a peer is admitted nobody gets to send more than this
MAX_CHAT = 2000                    # characters in one chat message
MAX_TITLE = 80                     # characters in a transfer's title
MAX_NAME = 32                      # characters in a display name

HANDSHAKE_TIMEOUT = 10.0           # seconds to finish TLS + hello
IDLE_TIMEOUT = 60.0                # no frame at all for this long: the peer is gone
PING_INTERVAL = 15.0


class ProtocolError(Exception):
    """A frame was malformed or too large. The connection should be dropped."""


class ConnectionClosed(ProtocolError):
    """The other side hung up."""


class LanError(Exception):
    """A failure the user should be told about. ``code`` is machine-readable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------

def encode_frame(msg: dict) -> bytes:
    data = json.dumps(msg, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_FRAME:
        raise ProtocolError("message too large to send")
    return struct.pack(">I", len(data)) + data


def decode_payload(data: bytes) -> dict:
    try:
        msg = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ProtocolError(f"not valid JSON: {e}")
    if not isinstance(msg, dict) or not isinstance(msg.get("type"), str):
        raise ProtocolError("a frame must be a JSON object with a string 'type'")
    return msg


async def read_frame(reader: asyncio.StreamReader, max_size: int = MAX_FRAME) -> dict:
    """Read one frame. The size is checked *before* the body is read."""
    try:
        header = await reader.readexactly(4)
        (length,) = struct.unpack(">I", header)
        if length == 0 or length > max_size:
            raise ProtocolError(f"frame of {length} bytes is outside the allowed size")
        data = await reader.readexactly(length)
    except asyncio.IncompleteReadError:
        raise ConnectionClosed("connection closed")
    except (ConnectionError, OSError) as e:
        raise ConnectionClosed(str(e))
    return decode_payload(data)


def clean_text(value, max_len: int) -> str:
    """Printable text only (newline and tab allowed), trimmed and capped."""
    if not isinstance(value, str):
        return ""
    text = "".join(ch for ch in value if ch in "\n\t" or (ch >= " " and ch != "\x7f"))
    return text.strip()[:max_len]


def clean_name(value, fallback: str = "Player") -> str:
    name = " ".join(clean_text(value, MAX_NAME * 2).split())[:MAX_NAME].strip()
    return name or fallback


# ---------------------------------------------------------------------------
# Invite codes
# ---------------------------------------------------------------------------
# The invite carries the host's address and a fingerprint of its (throwaway) TLS
# certificate. The joining client refuses to talk to a server whose certificate does
# not match, which is what stops someone else on the network from posing as the DM.

FINGERPRINT_BYTES = 16     # 128 bits of the SHA-256 of the certificate
FINGERPRINT_CHARS = 26     # the same, as unpadded base32


def fingerprint_of(der_cert: bytes) -> str:
    """26 base32 characters identifying a DER certificate."""
    digest = hashlib.sha256(der_cert).digest()[:FINGERPRINT_BYTES]
    return base64.b32encode(digest).decode("ascii").rstrip("=")


def normalize_fingerprint(text: str) -> str:
    return re.sub(r"[^A-Za-z2-7]", "", text or "").upper()


def format_fingerprint(fp: str) -> str:
    fp = normalize_fingerprint(fp)
    return "-".join(fp[i:i + 5] for i in range(0, len(fp), 5))


def fingerprints_match(a: str, b: str) -> bool:
    return hmac.compare_digest(normalize_fingerprint(a).encode(), normalize_fingerprint(b).encode())


_INVITE_RE = re.compile(r"^\s*(?:spellbook://)?(?P<host>\[[^\]]+\]|[^\s:#/\[\]]+)(?::(?P<port>\d{1,5}))?"
                        r"\s*[#/]\s*(?P<code>[A-Za-z2-7\- ]+?)\s*$")


@dataclass(frozen=True)
class Invite:
    host: str
    port: int
    fingerprint: str

    def encode(self) -> str:
        host = f"[{self.host}]" if ":" in self.host and not self.host.startswith("[") else self.host
        return f"{host}:{self.port}#{format_fingerprint(self.fingerprint)}"

    @classmethod
    def parse(cls, text: str) -> "Invite":
        """Accepts ``host:port#CODE`` (also ``spellbook://host:port/CODE``). Raises ValueError."""
        m = _INVITE_RE.match(text or "")
        if not m:
            raise ValueError("That doesn't look like an invite. Expected something like "
                             "192.168.1.20:5150#ABCDE-FGHIJ-...")
        host = m.group("host").strip("[]")
        port = int(m.group("port") or DEFAULT_PORT)
        if not 1 <= port <= 65535:
            raise ValueError("The port in the invite is out of range.")
        fp = normalize_fingerprint(m.group("code"))
        if len(fp) != FINGERPRINT_CHARS:
            raise ValueError("The code in the invite is the wrong length.")
        return cls(host, port, fp)


def pinned_fingerprint_ok(writer: asyncio.StreamWriter, expected: str) -> bool:
    """True if the TLS peer's certificate matches ``expected`` (a fingerprint)."""
    ssl_obj = writer.get_extra_info("ssl_object")
    if ssl_obj is None:
        return False
    der: Optional[bytes] = ssl_obj.getpeercert(binary_form=True)
    return bool(der) and fingerprints_match(fingerprint_of(der), expected)
