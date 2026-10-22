"""Browser players: the web server in the DM's app (lan/web.py), its WebSocket, and the QR code."""

import base64
import hashlib
import json
import os
import socket
import struct
import time

import pytest

from lan import protocol as P
from lan import qr
from lan import web as W
from lan.client import LanClient
from lan.host import LanHost
from lan.protocol import LanError


def wait_for(events, kind, timeout=15.0, where=None):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ev = events.get(timeout=0.2)
        if ev and ev["type"] == kind and (where is None or where(ev)):
            return ev
    raise AssertionError(f"no {kind!r} event within {timeout}s")


# --------------------------------------------------------------------------- a tiny browser

def http_get(port, path, host_header=None, extra=""):
    """``(status, headers, body)`` of one plain GET."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall((f"GET {path} HTTP/1.1\r\nHost: {host_header or f'127.0.0.1:{port}'}\r\n{extra}"
                   "Connection: close\r\n\r\n").encode("latin-1"))
        data = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split(" ")[1])
    headers = {k.strip().lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:])}
    return status, headers, body


class Browser:
    """A WebSocket client the way a browser speaks it: masked frames, JSON text messages."""

    def __init__(self, port, origin=True, host_header=None):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host = host_header or f"127.0.0.1:{port}"
        origin_line = f"Origin: http://{host}\r\n" if origin is True else (f"Origin: {origin}\r\n" if origin else "")
        self.sock.sendall((f"GET /ws HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n{origin_line}\r\n"
                           ).encode("latin-1"))
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1)
            if not chunk:
                break
            head += chunk
        self.status = int(head.split(b" ")[1]) if head else 0
        if self.status == 101:
            accept = hashlib.sha1((key + W.WS_GUID).encode()).digest()
            assert base64.b64encode(accept) in head
        self._buf = b""

    def send_raw(self, payload: bytes, opcode=0x1, fin=True, masked=True):
        n = len(payload)
        b0 = (0x80 if fin else 0) | opcode
        if n < 126:
            head = struct.pack(">BB", b0, (0x80 if masked else 0) | n)
        elif n < 65536:
            head = struct.pack(">BBH", b0, (0x80 if masked else 0) | 126, n)
        else:
            head = struct.pack(">BBQ", b0, (0x80 if masked else 0) | 127, n)
        if masked:
            mask = os.urandom(4)
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            head += mask
        self.sock.sendall(head + payload)

    def send(self, msg_type, body=None):
        self.send_raw(json.dumps({"type": msg_type, "body": body or {}}).encode("utf-8"))

    def _read(self, n):
        while len(self._buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def recv_frame(self):
        b0, b1 = self._read(2)
        n = b1 & 0x7F
        if n == 126:
            (n,) = struct.unpack(">H", self._read(2))
        elif n == 127:
            (n,) = struct.unpack(">Q", self._read(8))
        assert not b1 & 0x80, "the server must not mask"
        return b0 & 0x0F, self._read(n)

    def recv(self, msg_type=None, timeout=15.0, where=None):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.sock.settimeout(max(0.1, deadline - time.time()))
            opcode, data = self.recv_frame()
            if opcode == 0x8:
                raise ConnectionError("closed by the server")
            if opcode != 0x1:
                continue
            msg = json.loads(data.decode("utf-8"))
            if (msg_type is None or msg["type"] == msg_type) and (where is None or where(msg)):
                return msg
        raise AssertionError(f"no {msg_type!r} message within {timeout}s")

    def hello(self, name="Robin", client_id="abc123", password=""):
        self.send("hello", {"proto": P.PROTOCOL_VERSION, "name": name, "client_id": client_id,
                            "password": password, "app_version": "browser"})

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


@pytest.fixture()
def host():
    h = LanHost("Dungeon Master", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    h.start_web(port=0, bind="127.0.0.1")
    yield h
    h.stop()


# --------------------------------------------------------------------------- the page

def test_the_page_and_its_files_are_served_with_safe_headers(host):
    status, headers, body = http_get(host.web_port, "/")
    assert status == 200 and b"Spellbook Tabletop" in body
    assert headers["content-type"].startswith("text/html")
    assert "default-src 'self'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"
    for path in ("/table.js", "/table.css"):
        assert http_get(host.web_port, path)[0] == 200
    assert http_get(host.web_port, "/../lan/host.py")[0] == 404
    assert http_get(host.web_port, "/nothing")[0] == 404


def test_info_tells_the_join_page_about_the_session(host):
    status, _h, body = http_get(host.web_port, "/info")
    info = json.loads(body)
    assert status == 200
    assert info == {"name": "Dungeon Master", "password": False, "approval": False,
                    "proto": P.PROTOCOL_VERSION, "app": "", "full": False}


def test_a_public_host_name_is_refused(host):
    """A page on the internet can't reach the DM's server through a player's browser (DNS rebinding)."""
    assert http_get(host.web_port, "/", host_header="evil.example.com")[0] == 421
    assert http_get(host.web_port, "/", host_header="spellbook-pc.local:8742")[0] == 200
    assert http_get(host.web_port, "/", host_header="dm-laptop")[0] == 200


def test_local_addresses_and_names():
    for ok in ("192.168.1.20", "10.0.0.7", "172.16.4.2", "127.0.0.1", "100.101.5.6", "fe80::1", "::1",
               "::ffff:192.168.0.2", "fd12::5"):
        assert W.is_local_address(ok), ok
    for bad in ("8.8.8.8", "1.2.3.4", "2001:4860::8888", "nonsense"):
        assert not W.is_local_address(bad), bad
    assert W.local_host_name("192.168.1.20:8742") and W.local_host_name("[fe80::1]:8742")
    assert not W.local_host_name("") and not W.local_host_name("spellbook.example.org")


def test_only_get_is_answered(host):
    with socket.create_connection(("127.0.0.1", host.web_port), timeout=10) as s:
        s.sendall(f"POST / HTTP/1.1\r\nHost: 127.0.0.1:{host.web_port}\r\nContent-Length: 0\r\n\r\n".encode())
        assert b" 405 " in s.recv(4096)


# --------------------------------------------------------------------------- joining from a browser

def test_a_browser_joins_and_is_an_ordinary_session_member(host):
    app = LanClient("Ada")
    app.connect("127.0.0.1", host.port, host.fingerprint, timeout=20)
    b = Browser(host.web_port)
    assert b.status == 101
    b.hello("Robin", "deadbeef")
    welcome = b.recv("welcome")
    assert welcome["body"]["name"] == "Robin"
    joined = wait_for(host.events, "peer_joined", where=lambda e: e["peer"]["name"] == "Robin")
    assert joined["client_id"] == "web:deadbeef"          # never mistaken for an app install's id
    assert joined["peer"]["web"] is True and joined["peer"]["app"] == "browser"
    # the app player hears about the browser player
    ev = wait_for(app.events, "peer_joined", where=lambda e: e["peer"]["name"] == "Robin")
    assert ev["peer"].get("web") is True
    # chat both ways
    b.send("chat", {"text": "hello from a phone"})
    assert wait_for(app.events, "chat")["text"] == "hello from a phone"
    app.send_chat("welcome!")
    assert b.recv("chat", where=lambda m: m["body"]["text"] == "welcome!")["body"]["name"] == "Ada"
    # a ping is answered, and so is a WebSocket ping
    b.send("ping")
    assert b.recv("pong")
    b.send_raw(b"hi", opcode=0x9)
    assert b.recv_frame() == (0xA, b"hi")
    app.close()
    b.close()


def test_a_browser_cant_send_characters_or_homebrew(host):
    b = Browser(host.web_port)
    b.hello()
    b.recv("welcome")
    b.send("xfer", {"xfer_id": "x1", "title": "Sneaky", "to": "host", "payload": {"kind": "spells"}})
    err = b.recv("error")
    assert err["body"]["code"] == "unknown_type"
    b.close()


def test_a_long_message_in_pieces_is_put_back_together(host):
    b = Browser(host.web_port)
    b.hello()
    b.recv("welcome")
    data = json.dumps({"type": "chat", "body": {"text": "x" * 300}}).encode()
    b.send_raw(data[:100], fin=False)
    b.send_raw(data[100:200], opcode=0x0, fin=False)
    b.send_raw(data[200:], opcode=0x0)
    assert wait_for(host.events, "chat")["text"] == "x" * 300
    b.close()


def test_unmasked_or_oversized_frames_end_the_connection(host):
    b = Browser(host.web_port)
    b.hello()
    b.recv("welcome")
    b.send_raw(b'{"type":"chat","body":{"text":"hi"}}', masked=False)
    wait_for(host.events, "peer_left")
    b.close()
    b = Browser(host.web_port)
    b.hello(client_id="other")
    b.recv("welcome")
    b.send_raw(b"x" * (W.MAX_WEB_FRAME + 10))
    wait_for(host.events, "peer_left")
    b.close()


def test_the_websocket_must_come_from_the_page_itself(host):
    assert Browser(host.web_port, origin="http://evil.example.com").status == 403
    assert Browser(host.web_port, origin=False).status == 101          # (no Origin: not a browser page)


def test_the_password_and_the_dms_approval_apply_to_browsers():
    h = LanHost("DM", password="owlbear", require_approval=True)
    h.start(port=0, bind="127.0.0.1")
    try:
        h.start_web(port=0, bind="127.0.0.1")
        b = Browser(h.web_port)
        b.hello(password="wrong")
        assert b.recv("error")["body"]["code"] == "password"
        b.close()
        b = Browser(h.web_port)
        b.hello(name="Robin", password="owlbear")
        ask = wait_for(h.events, "approval_request")
        assert ask["web"] is True and ask["name"] == "Robin"
        h.resolve_approval(ask["request_id"], False, "Not tonight.")
        assert b.recv("error")["body"]["message"] == "Not tonight."
        b.close()
    finally:
        h.stop()


def test_browsers_can_be_turned_off_again():
    h = LanHost("DM", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    try:
        port = h.start_web(port=0, bind="127.0.0.1")
        assert h.start_web(port=0) == port                 # already on
        b = Browser(port)
        b.hello()
        b.recv("welcome")
        h.stop_web()
        assert h.web_port == 0
        with pytest.raises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=3).close()
        # the browser already in stays in
        b.send("chat", {"text": "still here"})
        assert wait_for(h.events, "chat")["text"] == "still here"
        b.close()
    finally:
        h.stop()


def test_starting_the_web_page_needs_a_session():
    with pytest.raises(LanError):
        LanHost("DM").start_web(0)


def test_the_session_service_offers_browser_addresses(tmp_path):
    from lan.service import SessionService
    s = SessionService()
    s.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
    try:
        assert s.web_addresses() == [] and s.web_port == 0
        port = s.start_web(port=0)
        assert port and all(a.startswith("http://") and a.endswith(f":{port}") for a in s.web_addresses())
        s.stop_web()
        assert s.web_port == 0
    finally:
        s.leave()


def test_transfers_are_never_offered_to_browser_players():
    from lan.service import SessionService
    s = SessionService()
    s.peers = [{"peer_id": "host", "name": "DM", "is_host": True}, {"peer_id": "p1", "name": "Robin", "web": True}]
    s.role, s.my_id = "host", "host"
    assert s.send_transfer("p1", {"kind": "x"}, "Spells") is None
    assert s.send_transfer_to_all({"kind": "x"}, "Spells") == 0
    s.role = "none"


# --------------------------------------------------------------------------- WebSocket framing

def test_ws_frames_of_every_length_round_trip():
    import asyncio

    async def run(n):
        reader = asyncio.StreamReader()
        payload = bytes(range(256)) * (n // 256 + 1)
        payload = payload[:n]
        mask = b"\x01\x02\x03\x04"
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        if n < 126:
            head = struct.pack(">BB", 0x81, 0x80 | n)
        elif n < 65536:
            head = struct.pack(">BBH", 0x81, 0x80 | 126, n)
        else:
            head = struct.pack(">BBQ", 0x81, 0x80 | 127, n)
        reader.feed_data(head + mask + masked)
        return await W.read_ws_frame(reader, 1 << 20)

    for n in (0, 5, 125, 126, 4095, 4096, 65535, 70000):
        final, opcode, data = __import__("asyncio").run(run(n))
        assert final and opcode == 1 and len(data) == n and data == (bytes(range(256)) * (n // 256 + 1))[:n]
    assert W.encode_ws(b"x" * 70000)[:2] == bytes([0x81, 127])
    assert W.accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="      # RFC 6455's example


# --------------------------------------------------------------------------- the QR code

def _bits(rows):
    return "".join("1" if v else "0" for row in rows for v in row)


def test_qr_codes_match_a_reference_encoder():
    # Matrices made with the python-qrcode package (byte mode, level M, the given mask), stored as hashes
    cases = {
        ("http://192.168.1.20:8742", 2): (25, "743a7cfe3dca086324c4c61a675f165df2001218"),
        ("Spellbook " * 15, 5): (49, "408c50df42f71ec0a40beee403bb07da4f13ae33"),      # version 8: two block sizes
    }
    for (text, mask), (size, digest) in cases.items():
        rows = qr.make(text, mask)
        assert len(rows) == size
        assert hashlib.sha1(_bits(rows).encode()).hexdigest() == digest


def test_qr_codes_have_their_fixed_patterns():
    rows = qr.make("http://192.168.1.20:8742")
    n = len(rows)
    assert n == 25                                           # version 2
    for r0, c0 in ((0, 0), (0, n - 7), (n - 7, 0)):          # the three finder squares
        assert all(rows[r0][c0 + i] for i in range(7)) and all(rows[r0 + 6][c0 + i] for i in range(7))
        assert not rows[r0 + 1][c0 + 1] and rows[r0 + 3][c0 + 3]
    assert [rows[6][c] for c in range(8, n - 8)] == [c % 2 == 0 for c in range(8, n - 8)]   # timing
    assert rows[n - 8][8]                                    # the dark module
    long = qr.make("x" * 200)
    assert len(long) == 57                                   # version 10
    with pytest.raises(ValueError):
        qr.make("x" * 300)


def test_qr_image_has_a_quiet_border():
    img = qr.to_image(qr.make("hi"), scale=2, border=4)
    assert img.size == ((21 + 8) * 2,) * 2
    assert img.getpixel((0, 0)) == (255, 255, 255) and img.getpixel((8, 8)) == (0, 0, 0)


# --------------------------------------------------------------------------- the DM's Session page

def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def test_the_session_page_offers_browsers_an_address_and_a_qr_code(tk_root):
    import customtkinter as ctk
    from lan.service import SessionService
    from ui.session_view import SessionView
    svc = SessionService()
    svc.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
    start = svc.start_web
    svc.start_web = lambda port=None: start(0)              # any free port in a test
    view = SessionView(tk_root, svc)
    view.pack(fill="both", expand=True)
    try:
        tk_root.update()
        switch = next(w for w in _walk(view) if isinstance(w, ctk.CTkSwitch) and w.cget("text") == "Let browsers join")
        switch.toggle()
        for _ in range(5):
            tk_root.update()
        assert svc.web_port
        entries = [w.get() for w in _walk(view) if isinstance(w, ctk.CTkEntry)]
        assert any(e.startswith("http://") and e.endswith(f":{svc.web_port}") for e in entries)
        assert any(isinstance(w, ctk.CTkLabel) and w.cget("image") is not None for w in _walk(view))   # the QR code
        switch = next(w for w in _walk(view) if isinstance(w, ctk.CTkSwitch) and w.cget("text") == "Let browsers join")
        assert switch.get() == 1
        switch.toggle()
        for _ in range(5):
            tk_root.update()
        assert svc.web_port == 0
        assert not any(w.get().startswith("http://") for w in _walk(view) if isinstance(w, ctk.CTkEntry))
    finally:
        view.destroy()
        svc.shutdown()


# --------------------------------------------------------------------------- chat, dice and turn order

def test_a_browser_player_rolls_and_uses_the_turn_order(tmp_path):
    """What the side panel sends: /roll in chat, a whisper to the DM, and their own tracker commands."""
    import threading
    from lan.service import SessionService
    from tracker_hub import TrackerHub
    from tracker_net import TrackerHostLink
    s = SessionService()
    s.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
    port = s.start_web(port=0)
    hub = TrackerHub(str(tmp_path / "tracker.json"))
    TrackerHostLink(hub, s)
    dm = hub.dm()
    dm.dispatch({"type": "add_entry", "kind": "custom", "name": "Ogre", "hp": 59, "ac": 11, "initiative": 4})
    dm.dispatch({"type": "set_settings", "monster_hp": "bar", "players_can_add": True})
    stop = threading.Event()

    def pump_events():                  # what the app's Tk loop does
        while not stop.is_set():
            s.pump()
            time.sleep(0.02)

    pump = threading.Thread(target=pump_events, daemon=True)
    pump.start()
    b = Browser(port)
    try:
        b.hello("Robin", "deadbeef")
        b.recv("welcome")
        first = b.recv("tracker_state")["body"]["view"]
        ogre = first["entries"][0]
        assert ogre["name"] == "Ogre" and "hp" not in ogre and ogre["hp_frac"] == 1.0   # only a bar for monsters
        assert first["can_add"]
        # dice are rolled by the DM's app
        b.send("chat", {"text": "/roll d20+3 adv Stealth"})
        roll = b.recv("roll")["body"]
        assert roll["expr"] == "2d20kh1+3 adv" and roll["label"] == "Stealth" and 4 <= roll["total"] <= 23
        b.send("dm", {"to": "host", "text": "psst"})
        assert b.recv("dm")["body"]["text"] == "psst"
        # joining the turn order, then taking damage and a condition on their own character
        b.send("tracker_cmd", {"cmd": {"type": "add_me", "name": "Robin the Bold", "hp": 24, "hp_max": 24, "ac": 14},
                               "seq": 1})
        mine = lambda m: any(e.get("mine") for e in m["body"]["view"]["entries"])
        me = next(e for e in b.recv("tracker_state", where=mine)["body"]["view"]["entries"] if e["mine"])
        assert me["hp"] == 24 and me["ac"] == 14
        b.send("tracker_cmd", {"cmd": {"type": "hp_delta", "id": me["id"], "delta": -5}, "seq": 2})
        b.send("tracker_cmd", {"cmd": {"type": "add_condition", "id": me["id"], "name": "Blessed"}, "seq": 3})
        b.recv("tracker_state", where=lambda m: any(c["name"] == "Blessed" for e in m["body"]["view"]["entries"]
                                                    for c in e["conditions"]))
        state = next(e for e in hub.tracker.state.entries if e.name == "Robin the Bold")
        assert state.hp == 19 and state.owner == "web:deadbeef"
        # but not the Ogre's
        b.send("tracker_cmd", {"cmd": {"type": "hp_delta", "id": ogre["id"], "delta": -50}, "seq": 4})
        assert "your own" in b.recv("tracker_error")["body"]["message"]
        assert next(e for e in hub.tracker.state.entries if e.name == "Ogre").hp == 59
    finally:
        b.close()
        stop.set()
        pump.join(2)
        s.leave()


def test_the_side_panel_script_is_served(host):
    status, headers, body = http_get(host.web_port, "/side.js")
    assert status == 200 and headers["content-type"].startswith("text/javascript")
    page = http_get(host.web_port, "/")[2]
    for needed in (b'src="side.js"', b'id="chat-log"', b'id="turn-list"', b'id="dice-buttons"'):
        assert needed in page


def test_hosting_starts_even_if_the_browser_page_cant(monkeypatch):
    """Turning on "Let browsers join" is remembered; if the page can't open next time, the session still starts."""
    from lan.service import HOSTING, SessionService
    s = SessionService()
    monkeypatch.setattr(s, "saved", lambda key, default=None: True if key == "lan_web" else default)

    def broken(port=None):
        raise RuntimeError("no luck")
    monkeypatch.setattr(s, "start_web", broken)
    try:
        s.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
        assert s.role == HOSTING
        assert any("no luck" in line.get("text", "") for line in s.chat)
    finally:
        s.leave()
