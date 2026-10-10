"""The session as the rest of the app sees it: one object, owned by ``MainWindow``.

Pages come and go as tabs navigate, but a game session must not end when a tab does,
so the connection, the peer list and the chat log live here instead of in any page.
Pages (and the status bar) subscribe with :meth:`SessionService.add_listener`.

Everything on this class is called from the UI thread. The network threads only fill
their event queues; :meth:`pump` (called every ~100 ms while a session is active)
empties them, updates the state below and notifies listeners, so listeners may touch
widgets freely.

Listener events - ``listener(kind, **data)``:

* ``state``            - the role or the peer list changed
* ``line``             - ``line`` was appended to :attr:`chat` (a dict, see :meth:`_add_line`);
                         a dice roll has ``kind == "roll"`` and a ``roll`` dict
* ``approval_request`` - host only: ``request_id, name, address``
* ``approval_done``    - host only: ``request_id`` (answered, so close any prompt)
* ``scan_done``        - discovery finished; the results are in :attr:`discovered`
* ``inbox``            - something arrived (or left) :attr:`inbox`; ``item`` is the new entry, if any
* ``join_failed``      - ``message``
* ``ended``            - the session is over; ``reason`` says why
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from lan import discovery
from lan import protocol as P
from lan.client import LanClient
from lan.host import HOST_ID, LanHost
from lan.protocol import LanError
from lan.runtime import EventQueue

NONE, HOSTING, JOINING, CLIENT = "none", "host", "joining", "client"

MAX_CHAT_LINES = 1000
MAX_INBOX_ITEMS = 20
MAX_INBOX_BYTES = 24 * 1024 * 1024       # of received payloads waiting for a decision


def local_addresses() -> List[str]:
    """This machine's IPv4 addresses worth putting in an invite, best guess first.

    The first entry is the address the OS would use to reach the internet/LAN gateway,
    which is nearly always the one players on the same network (or a VPN such as
    Tailscale) can reach. Loopback and link-local addresses are left out.
    """
    found: List[str] = []

    def add(ip: str) -> None:
        if ip and ip not in found and not ip.startswith(("127.", "169.254.", "0.")):
            found.append(ip)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))        # no packet is sent; it just picks a route
            add(s.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass
    return found


class SessionService:
    def __init__(self, settings_manager=None, app_version: str = "", schema: int = 0):
        self._settings = settings_manager
        self.app_version = app_version
        self.schema = schema

        self.role = NONE
        self.my_id = ""                               # our peer id (HOST_ID when hosting)
        self.my_name = ""
        self.host_name = ""                           # the DM's display name
        self.peers: List[dict] = []                   # {peer_id, name, is_host}
        self.chat: List[dict] = []
        self.password = ""                            # what the host asked for (shown to the DM only)
        self.require_approval = True
        self.port = 0
        self.last_end_reason = ""
        self.discovered: List[discovery.FoundSession] = []
        self.scanning = False
        self.inbox: List[dict] = []                 # received transfers waiting for a decision
        self.outbox: Dict[str, dict] = {}           # xfer_id -> what we sent and how it went
        self.discovery_visible = False              # hosting AND answering discovery probes
        self.security_code = ""                     # short form of the certificate fingerprint

        self._host: Optional[LanHost] = None
        self._client: Optional[LanClient] = None
        self._local = EventQueue()                    # results of the join thread
        self._listeners: List[Callable[..., None]] = []
        self._pump_wake: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------- state

    @property
    def active(self) -> bool:
        """True while a session exists or is being joined (the UI keeps pumping)."""
        return self.role != NONE

    @property
    def is_host(self) -> bool:
        return self.role == HOSTING

    @property
    def needs_pump(self) -> bool:
        return self.active or self.scanning

    @property
    def in_session(self) -> bool:
        return self.role in (HOSTING, CLIENT)

    def set_wake(self, callback: Callable[[], None]) -> None:
        """``callback()`` is called (on the UI thread) whenever pumping needs to start."""
        self._pump_wake = callback

    def add_listener(self, callback: Callable[..., None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[..., None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, kind: str, **data) -> None:
        for listener in list(self._listeners):
            try:
                listener(kind, **data)
            except Exception as e:                    # a broken page must not stop the session
                print(f"Session listener error: {e}")

    def peer_name(self, peer_id: str) -> str:
        for p in self.peers:
            if p["peer_id"] == peer_id:
                return p["name"]
        return ""

    # ---------------------------------------------------------------- settings

    def default_name(self) -> str:
        name = getattr(getattr(self._settings, "settings", None), "lan_display_name", "") if self._settings else ""
        if name:
            return name
        import getpass
        try:
            return P.clean_name(getpass.getuser(), "Player")
        except Exception:
            return "Player"

    def saved(self, key: str, default=None):
        """A remembered ``lan_*`` setting (e.g. ``lan_port``)."""
        s = getattr(self._settings, "settings", None) if self._settings else None
        return getattr(s, key, default) if s is not None else default

    def client_id(self) -> str:
        """Stable random id for this install (created and saved on first use)."""
        import secrets
        s = getattr(self._settings, "settings", None) if self._settings else None
        if s is None:
            return secrets.token_hex(8)
        if not s.lan_client_id:
            self._settings.update(lan_client_id=secrets.token_hex(8))
        return s.lan_client_id

    def _remember(self, **values) -> None:
        if self._settings is not None:
            try:
                self._settings.update(**values)
            except Exception:
                pass

    # ----------------------------------------------------------------- hosting

    def start_host(self, name: str, password: str = "", require_approval: bool = True,
                   port: int = P.DEFAULT_PORT, bind: str = "0.0.0.0",
                   discoverable: Optional[bool] = None,
                   discovery_port: int = discovery.DISCOVERY_PORT) -> int:
        """Begin hosting. Raises :class:`LanError` (e.g. the port is taken).

        ``discoverable`` (default: the saved setting, on) lets players on the same network find the
        session without an invite; the invite still works either way."""
        if self.active:
            raise LanError("busy", "A session is already running.")
        name = P.clean_name(name, "DM")
        if discoverable is None:
            discoverable = bool(self.saved("lan_discovery", True))
        host = LanHost(name, password=password, require_approval=require_approval,
                       app_version=self.app_version, schema=self.schema,
                       discovery_port=discovery_port if discoverable else None)
        self.port = host.start(port=port, bind=bind)
        self._host = host
        self.discovery_visible = host.discovery_active
        self.security_code = P.format_fingerprint(host.fingerprint[:10])
        self.role = HOSTING
        self.my_id, self.my_name, self.host_name = HOST_ID, host.display_name, host.display_name
        self.password, self.require_approval = password, require_approval
        self.peers = host.peers()
        self.chat = []
        self.last_end_reason = ""
        self._remember(lan_display_name=name, lan_port=port, lan_require_approval=require_approval,
                       lan_discovery=bool(discoverable))
        self._add_line("system", "Session started. Share an invite with your players.")
        self._wake()
        self._notify("state")
        return self.port

    def invites(self) -> List[Tuple[str, str]]:
        """``[(address, invite text)]`` for every address players might reach this machine on."""
        if self._host is None:
            return []
        return [(ip, self._host.invite(ip).encode()) for ip in local_addresses()] or \
               [("this computer", self._host.invite("<your IP address>").encode())]

    def resolve_approval(self, request_id: str, accept: bool, reason: str = "The DM declined.") -> None:
        if self._host is not None:
            self._host.resolve_approval(request_id, accept, reason)
        self._notify("approval_done", request_id=request_id)

    def kick(self, peer_id: str) -> None:
        if self._host is not None:
            self._host.kick(peer_id)

    # ---------------------------------------------------------------- transfers

    def send_transfer(self, peer_id: str, payload: dict, title: str) -> Optional[str]:
        """Send characters/homebrew (a ``transfer.py`` payload) to one player. Returns the transfer
        id, or None if we aren't in a session or that player isn't here."""
        if not self.in_session or peer_id == self.my_id or not self.peer_name(peer_id):
            return None
        xfer_id = secrets.token_hex(8)
        title = P.clean_text(title, P.MAX_TITLE) or "something"
        to_name = self.peer_name(peer_id)
        self.outbox[xfer_id] = {"to": peer_id, "to_name": to_name, "title": title, "status": "sending"}
        if self._host is not None:
            self._host.send_xfer(peer_id, xfer_id, title, payload)
        elif self._client is not None:
            self._client.send_xfer(peer_id, xfer_id, title, payload)
        self._add_line("system", f"Sending \"{title}\" to {to_name}...")
        return xfer_id

    def send_transfer_to_all(self, payload: dict, title: str) -> int:
        """Send the same payload to everyone else in the session. Returns how many it went to."""
        count = 0
        for p in list(self.peers):
            if p["peer_id"] != self.my_id and self.send_transfer(p["peer_id"], payload, title):
                count += 1
        return count

    def _inbox_bytes(self) -> int:
        return sum(item["size"] for item in self.inbox)

    def get_item(self, item_id: str) -> Optional[dict]:
        return next((i for i in self.inbox if i["item_id"] == item_id), None)

    def decline_item(self, item_id: str, detail: str = "") -> None:
        """Throw a received transfer away (the sender is told)."""
        self._finish_item(item_id, "declined", detail)

    def finish_item(self, item_id: str, status: str = "imported", detail: str = "") -> None:
        """A received transfer was dealt with (``imported``, or ``failed``); the sender is told."""
        self._finish_item(item_id, status, detail)

    def _finish_item(self, item_id: str, status: str, detail: str) -> None:
        item = self.get_item(item_id)
        if item is None:
            return
        self.inbox.remove(item)
        self._reply(item["from"], item["item_id"], status, detail)
        self._notify("inbox", item=None)

    def _reply(self, peer_id: str, xfer_id: str, status: str, detail: str = "") -> None:
        if self._host is not None:
            self._host.send_xfer_reply(peer_id, xfer_id, status, detail)
        elif self._client is not None and self.role == CLIENT:
            self._client.send_xfer_reply(peer_id, xfer_id, status, detail)

    # --------------------------------------------------------------- discovery

    def scan(self, timeout: float = 1.5, port: int = discovery.DISCOVERY_PORT,
             targets: Optional[List[str]] = None) -> None:
        """Look for sessions on the network in the background; ``scan_done`` fires when finished."""
        if self.scanning or self.active:
            return
        self.scanning = True

        def work():
            try:
                found = discovery.scan(timeout=timeout, port=port, targets=targets)
            except Exception:
                found = []
            self._local.put("scan_done", found=found)

        threading.Thread(target=work, name="lan-scan", daemon=True).start()
        self._wake()

    def join_found(self, found: "discovery.FoundSession", name: str, password: str = "") -> None:
        """Join a session the scan found (the caller has had the player check its security code)."""
        self.join(found.invite().encode(), name, password)

    # ----------------------------------------------------------------- joining

    def join(self, invite_text: str, name: str, password: str = "") -> None:
        """Start joining; the result arrives later as ``state`` (success) or ``join_failed``."""
        if self.active:
            raise LanError("busy", "You are already in a session.")
        try:
            invite = P.Invite.parse(invite_text)
        except ValueError as e:
            raise LanError("invite", str(e))
        name = P.clean_name(name)
        client = LanClient(name, client_id=self.client_id(), password=password,
                           app_version=self.app_version, schema=self.schema)
        self._client = client
        self.security_code = P.format_fingerprint(invite.fingerprint[:10])
        self.role = JOINING
        self.my_name = name
        self._remember(lan_display_name=name, lan_last_invite=invite_text.strip())

        def work():
            try:
                welcome = client.connect(invite.host, invite.port, invite.fingerprint)
                self._local.put("join_ok", welcome=welcome)
            except LanError as e:
                self._local.put("join_failed", message=e.message, code=e.code)
            except Exception as e:                    # never leave the UI waiting
                self._local.put("join_failed", message=str(e), code="error")

        threading.Thread(target=work, name="lan-join", daemon=True).start()
        self._wake()
        self._notify("state")

    def cancel_join(self) -> None:
        if self.role == JOINING:
            self._teardown()
            self._notify("state")

    # ------------------------------------------------------------------ leaving

    def leave(self, reason: str = "") -> None:
        """Leave (or, as host, end) the session."""
        if self.role == NONE:
            return
        was_host = self.role == HOSTING
        self._teardown()
        self.last_end_reason = reason or ("You ended the session." if was_host else "You left the session.")
        self._add_line("system", self.last_end_reason)
        self._notify("ended", reason=self.last_end_reason)
        self._notify("state")

    def shutdown(self) -> None:
        """App is closing: stop all networking without notifying pages."""
        self._listeners.clear()
        self._teardown()

    def _teardown(self) -> None:
        host, client = self._host, self._client
        self._host = self._client = None
        self.role = NONE
        self.peers = []
        self.my_id = ""
        self.discovery_visible = False
        for obj in (host, client):
            if obj is not None:
                try:
                    obj.stop() if isinstance(obj, LanHost) else obj.close()
                except Exception:
                    pass

    # ----------------------------------------------------------------- talking

    def send_chat(self, text: str) -> None:
        if self._host is not None:
            self._host.send_chat(text)
        elif self._client is not None and self.role == CLIENT:
            self._client.send_chat(text)

    def send_dm(self, peer_id: str, text: str) -> None:
        if self._host is not None:
            self._host.send_dm(peer_id, text)
        elif self._client is not None and self.role == CLIENT:
            self._client.send_dm(peer_id, text)

    # --------------------------------------------------------------------- pump

    def _wake(self) -> None:
        if self._pump_wake is not None:
            self._pump_wake()

    def pump(self) -> int:
        """Handle everything the network threads have queued. Returns how many events."""
        count = 0
        for ev in self._local.drain():
            count += 1
            self._on_local(ev)
        source = self._host.events if self._host is not None else (
            self._client.events if self._client is not None else None)
        if source is not None:
            for ev in source.drain():
                count += 1
                self._on_net(ev)
        return count

    def _on_local(self, ev: Dict[str, Any]) -> None:
        if ev["type"] == "scan_done":
            self.scanning = False
            self.discovered = ev["found"] if self.role == NONE else []
            self._notify("scan_done")
            return
        if self.role != JOINING:
            return              # cancelled while connecting: the teardown already hung up
        if ev["type"] == "join_ok" and self._client is not None:
            welcome = ev["welcome"]
            self.role = CLIENT
            self.my_id = self._client.peer_id
            self.my_name = self._client.name
            host = welcome.get("host") or {}
            self.host_name = str(host.get("name") or "the DM")
            self.peers = self._client.peers()
            self.chat = []
            self.last_end_reason = ""
            self._add_line("system", f"Joined {self.host_name}'s session.")
            self._notify("state")
        else:
            message = ev.get("message") or "Could not join the session."
            self._teardown()
            self.last_end_reason = message
            self._notify("join_failed", message=message)
            self._notify("state")

    def _on_net(self, ev: Dict[str, Any]) -> None:
        kind = ev["type"]
        if kind == "chat":
            self._add_line("chat", ev["text"], name=ev["name"], sender=ev["from"], ts=ev["ts"])
        elif kind == "dm":
            self._add_line("dm", ev["text"], name=ev["name"], sender=ev["from"], to=ev.get("to", ""), ts=ev["ts"])
        elif kind == "roll":
            roll = {k: ev.get(k) for k in ("expr", "detail", "total", "label", "crit", "private")}
            self._add_line("roll", "", name=ev["name"], sender=ev["from"], ts=ev["ts"], roll=roll)
        elif kind == "xfer":
            self._on_xfer(ev)
        elif kind == "xfer_status":
            self._on_xfer_status(ev)
        elif kind == "xfer_reply":
            self._on_xfer_reply(ev)
        elif kind == "peer_joined":
            self._set_peer(ev["peer"])
            self._add_line("system", f"{ev['peer']['name']} joined.")
            self._notify("state")
        elif kind == "peer_left":
            self._drop_peer(ev["peer"])
            why = f" ({ev['reason']})" if ev.get("reason") else ""
            self._add_line("system", f"{ev['peer']['name']} left{why}.")
            self._notify("state")
        elif kind == "approval_request":
            self._notify("approval_request", request_id=ev["request_id"], name=ev["name"], address=ev["address"])
        elif kind == "error":
            self._add_line("system", ev.get("message") or "Something went wrong.")
        elif kind == "disconnected":
            self.leave(ev.get("reason") or "The connection was lost.")

    def _on_xfer(self, ev: Dict[str, Any]) -> None:
        try:
            size = len(json.dumps(ev["payload"], separators=(",", ":")))
        except (TypeError, ValueError):
            return
        if len(self.inbox) >= MAX_INBOX_ITEMS or self._inbox_bytes() + size > MAX_INBOX_BYTES:
            self._reply(ev["from"], ev["xfer_id"], "declined", "Their inbox is full.")
            self._add_line("system", f"{ev['name']} tried to send you something but your inbox is full.")
            return
        item = {"item_id": ev["xfer_id"], "from": ev["from"], "name": ev["name"],
                "title": ev["title"] or "something", "payload": ev["payload"], "size": size,
                "ts": ev["ts"]}
        self.inbox.append(item)
        self._add_line("system", f"{ev['name']} sent you \"{item['title']}\". Open the Inbox on the "
                                 "Session page to look at it - nothing is added until you accept.",
                       alert=True)
        self._notify("inbox", item=item)

    def _on_xfer_status(self, ev: Dict[str, Any]) -> None:
        sent = self.outbox.get(ev["xfer_id"])
        if sent is None:
            return
        if ev["status"] == "delivered":
            sent["status"] = "delivered"
            self._add_line("system", f"\"{sent['title']}\" reached {sent['to_name']}. "
                                     "They choose whether to add it.")
        else:
            sent["status"] = "failed"
            self._add_line("system", f"Could not send \"{sent['title']}\" to {sent['to_name']}: "
                                     f"{ev.get('detail') or 'it failed'}")

    def _on_xfer_reply(self, ev: Dict[str, Any]) -> None:
        sent = self.outbox.get(ev["xfer_id"])
        if sent is None:
            return
        sent["status"] = ev["status"]
        who = ev.get("name") or sent["to_name"]
        text = {"imported": f"{who} added \"{sent['title']}\".",
                "accepted": f"{who} accepted \"{sent['title']}\".",
                "declined": f"{who} declined \"{sent['title']}\"."
                            + (f" ({ev['detail']})" if ev.get("detail") else ""),
                "failed": f"{who} could not add \"{sent['title']}\": {ev.get('detail') or 'it failed'}"}
        self._add_line("system", text.get(ev["status"], f"{who}: {ev['status']}"))

    def _set_peer(self, peer: dict) -> None:
        self.peers = [p for p in self.peers if p["peer_id"] != peer["peer_id"]] + [peer]

    def _drop_peer(self, peer: dict) -> None:
        self.peers = [p for p in self.peers if p["peer_id"] != peer["peer_id"]]

    def note(self, text: str) -> None:
        """A system line only this user sees (e.g. the ``/help`` text)."""
        self._add_line("system", text)

    def _add_line(self, kind: str, text: str, name: str = "", sender: str = "", to: str = "",
                  ts: Optional[float] = None, roll: Optional[dict] = None, alert: bool = False) -> None:
        line = {"kind": kind, "text": text, "name": name, "from": sender, "to": to,
                "ts": ts or time.time(), "mine": bool(sender) and sender == self.my_id}
        if alert:
            line["alert"] = True            # worth an unread badge even though it is a system line
        if roll is not None:
            line["roll"] = roll
        self.chat.append(line)
        if len(self.chat) > MAX_CHAT_LINES:
            del self.chat[:len(self.chat) - MAX_CHAT_LINES]
        self._notify("line", line=line)
