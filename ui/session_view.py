"""Session page (Game Tools > Session): host or join a LAN game, and chat.

The page is only a view. The connection, peers and chat log belong to the app's
:class:`lan.service.SessionService`, so closing or navigating away from this tab does
not end the session, and opening it again shows the same chat.
"""

import time
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from lan import protocol as P
from lan.protocol import LanError
from lan.service import CLIENT, HOSTING, JOINING, NONE
from theme import get_theme_manager
from typography import ui_font
from ui.scrollable_combobox import ScrollableComboBox

EVERYONE = "Everyone"


class SessionView(ctk.CTkFrame):
    def __init__(self, parent, service, on_back: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.service = service
        self.on_back = on_back

        self._rendered_role: Optional[str] = None
        self._chat_box: Optional[ctk.CTkTextbox] = None
        self._peers_frame: Optional[ctk.CTkFrame] = None
        self._to_var = ctk.StringVar(value=EVERYONE)
        self._to_combo: Optional[ScrollableComboBox] = None
        self._msg_entry: Optional[ctk.CTkEntry] = None
        self._error_label: Optional[ctk.CTkLabel] = None

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        if on_back:
            ctk.CTkButton(
                header, text="← Game Tools", width=110, height=32,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                command=on_back).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(header, text="Session", font=ui_font("title", 28, bold=True)).pack(side="left")
        self._leave_btn = ctk.CTkButton(
            header, text="", width=130, height=34,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=self._on_leave)

        self.body = ctk.CTkFrame(outer, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        service.add_listener(self._on_event)
        self._render()

    def destroy(self):
        try:
            self.service.remove_listener(self._on_event)
        except Exception:
            pass
        super().destroy()

    # ------------------------------------------------------------------ events

    def _on_event(self, kind: str, **data):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if kind == "line":
            self._append_line(data["line"])
        elif kind == "state":
            if self.service.role != self._rendered_role:
                self._render()
            else:
                self._refresh_peers()

    def _on_leave(self):
        if self.service.role == JOINING:
            self.service.cancel_join()
        else:
            self.service.leave()

    # ------------------------------------------------------------------ render

    def _render(self):
        for child in self.body.winfo_children():
            child.destroy()
        self._chat_box = self._peers_frame = self._to_combo = self._msg_entry = self._error_label = None
        role = self.service.role
        self._rendered_role = role
        if role in (HOSTING, CLIENT):
            self._leave_btn.configure(text="End session" if role == HOSTING else "Leave session")
            self._leave_btn.pack(side="right")
            self._build_active()
        elif role == JOINING:
            self._leave_btn.pack_forget()
            self._build_joining()
        else:
            self._leave_btn.pack_forget()
            self._build_idle()

    def _card(self, parent, title: str, blurb: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=12)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=18)
        ctk.CTkLabel(inner, text=title, font=ui_font("heading", 20, bold=True)).pack(anchor="w")
        ctk.CTkLabel(inner, text=blurb, font=ui_font("body"), text_color=self.theme.get_text_secondary(),
                     wraplength=340, justify="left").pack(anchor="w", pady=(4, 12))
        return inner

    def _field(self, parent, label: str, value: str = "", show: str = "", placeholder: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, font=ui_font("small"),
                     text_color=self.theme.get_text_secondary()).pack(anchor="w", pady=(6, 1))
        entry = ctk.CTkEntry(parent, height=32, show=show, placeholder_text=placeholder)
        entry.pack(fill="x")
        if value:
            entry.insert(0, value)
        return entry

    # ------------------------------------------------------------------ idle

    def _build_idle(self):
        s = self.service
        top = ctk.CTkFrame(self.body, fg_color="transparent")
        top.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(top, text="Your name in the session", font=ui_font("body")).pack(side="left", padx=(0, 10))
        self._name_entry = ctk.CTkEntry(top, width=220, height=32)
        self._name_entry.pack(side="left")
        self._name_entry.insert(0, s.default_name())

        if s.last_end_reason:
            ctk.CTkLabel(self.body, text=s.last_end_reason, font=ui_font("body"),
                         text_color=self.theme.get_current_color('text_warning'),
                         wraplength=760, justify="left").pack(anchor="w", pady=(0, 10))

        cards = ctk.CTkFrame(self.body, fg_color="transparent")
        cards.pack(fill="x", anchor="n")
        cards.grid_columnconfigure((0, 1), weight=1, uniform="cards")

        # --- host
        host = self._card(cards, "🏰 Host a session",
                          "You are the DM. Players join with an invite you share with them. "
                          "Everything is encrypted, and you approve each player.")
        host.master.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._port_entry = self._field(host, "Port", str(s.saved("lan_port", P.DEFAULT_PORT)))
        self._pw_entry = self._field(host, "Session password (optional)", show="•")
        self._approve_var = ctk.BooleanVar(value=bool(s.saved("lan_require_approval", True)))
        ctk.CTkCheckBox(host, text="Ask me to approve each player", variable=self._approve_var
                        ).pack(anchor="w", pady=(10, 4))
        ctk.CTkButton(host, text="Start session", height=36,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      hover_color=self.theme.get_current_color('accent_hover'),
                      command=self._on_start_host).pack(anchor="w", pady=(12, 0))
        self._host_error = ctk.CTkLabel(host, text="", font=ui_font("small"), wraplength=340, justify="left",
                                        text_color=self.theme.get_current_color('text_warning'))
        self._host_error.pack(anchor="w", pady=(6, 0))

        # --- join
        join = self._card(cards, "🎲 Join a session",
                          "Paste the invite your DM sent you, for example 192.168.1.20:5150#ABCDE-FGHIJ-…")
        join.master.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._invite_entry = self._field(join, "Invite", str(s.saved("lan_last_invite", "")),
                                         placeholder="address:port#code")
        self._join_pw_entry = self._field(join, "Session password (if the DM set one)", show="•")
        ctk.CTkButton(join, text="Join session", height=36,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      hover_color=self.theme.get_current_color('accent_hover'),
                      command=self._on_join).pack(anchor="w", pady=(16, 0))
        self._join_error = ctk.CTkLabel(join, text="", font=ui_font("small"), wraplength=340, justify="left",
                                        text_color=self.theme.get_current_color('text_warning'))
        self._join_error.pack(anchor="w", pady=(6, 0))

        ctk.CTkLabel(
            self.body,
            text="Tip: the first time you host, your firewall may ask whether to allow Spellbook on "
                 "private networks. Say yes, or players won't be able to connect.",
            font=ui_font("small"), text_color=self.theme.get_text_secondary(),
            wraplength=760, justify="left").pack(anchor="w", pady=(14, 0))

    def _on_start_host(self):
        self._host_error.configure(text="")
        try:
            port = int(self._port_entry.get().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self._host_error.configure(text="The port must be a number between 1 and 65535.")
            return
        try:
            self.service.start_host(self._name_entry.get(), self._pw_entry.get(),
                                    self._approve_var.get(), port)
        except LanError as e:
            self._host_error.configure(text=e.message)

    def _on_join(self):
        self._join_error.configure(text="")
        invite = self._invite_entry.get().strip()
        if not invite:
            self._join_error.configure(text="Paste the invite from your DM first.")
            return
        try:
            self.service.join(invite, self._name_entry.get(), self._join_pw_entry.get())
        except LanError as e:
            self._join_error.configure(text=e.message)

    # --------------------------------------------------------------- joining

    def _build_joining(self):
        box = ctk.CTkFrame(self.body, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=12)
        box.pack(anchor="n", pady=30)
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(padx=40, pady=30)
        ctk.CTkLabel(inner, text="Connecting…", font=ui_font("heading", 20, bold=True)).pack()
        ctk.CTkLabel(inner, text="Waiting for the host. If they approve players by hand, this can take a moment.",
                     font=ui_font("body"), text_color=self.theme.get_text_secondary(),
                     wraplength=380).pack(pady=(6, 14))
        ctk.CTkButton(inner, text="Cancel", width=100, command=self.service.cancel_join,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover')).pack()

    # ---------------------------------------------------------------- active

    def _build_active(self):
        s = self.service
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_columnconfigure(1, weight=0)
        self.body.grid_rowconfigure(0, weight=1)

        # chat column
        left = ctk.CTkFrame(self.body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self._chat_box = ctk.CTkTextbox(left, wrap="word", state="disabled", font=ui_font("body"),
                                        fg_color=self.theme.get_current_color('bg_secondary'))
        self._chat_box.pack(fill="both", expand=True)
        text = self._chat_box._textbox
        text.tag_config("system", foreground=self.theme.get_text_secondary())
        text.tag_config("name", foreground=self.theme.get_current_color('text_primary'))
        text.tag_config("me", foreground=self.theme.get_current_color('text_label'))
        text.tag_config("dm", foreground=self.theme.get_current_color('text_warning'))
        text.tag_config("time", foreground=self.theme.get_text_disabled())
        for line in s.chat:
            self._append_line(line, scroll=False)
        self._chat_box.see("end")

        row = ctk.CTkFrame(left, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        self._to_combo = ScrollableComboBox(row, width=130, height=34, variable=self._to_var,
                                            values=[EVERYONE], state="readonly")
        self._to_combo.pack(side="left", padx=(0, 6))
        self._msg_entry = ctk.CTkEntry(row, height=34, placeholder_text="Say something…")
        self._msg_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._msg_entry.bind("<Return>", lambda _e: self._send())
        ctk.CTkButton(row, text="Send", width=70, height=34,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      hover_color=self.theme.get_current_color('accent_hover'),
                      command=self._send).pack(side="left")

        # side column
        side = ctk.CTkFrame(self.body, fg_color=self.theme.get_current_color('bg_secondary'),
                            corner_radius=12, width=290)
        side.grid(row=0, column=1, sticky="ns")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="In this session", font=ui_font("heading", 16, bold=True)
                     ).pack(anchor="w", padx=16, pady=(14, 4))
        self._peers_frame = ctk.CTkFrame(side, fg_color="transparent")
        self._peers_frame.pack(fill="x", padx=12)
        if s.role == HOSTING:
            self._build_invite_panel(side)
        self._refresh_peers()
        self._msg_entry.focus_set()

    def _build_invite_panel(self, parent):
        s = self.service
        ctk.CTkLabel(parent, text="Invite players", font=ui_font("heading", 16, bold=True)
                     ).pack(anchor="w", padx=16, pady=(18, 2))
        ctk.CTkLabel(parent, text="Send a player the invite for the address they can reach you on "
                                  "(the first is usually right; use a VPN address if you play over a VPN).",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     wraplength=250, justify="left").pack(anchor="w", padx=16)
        for address, invite in s.invites()[:4]:
            ctk.CTkLabel(parent, text=address, font=ui_font("small", bold=True)
                         ).pack(anchor="w", padx=16, pady=(8, 0))
            line = ctk.CTkFrame(parent, fg_color="transparent")
            line.pack(fill="x", padx=12)
            entry = ctk.CTkEntry(line, height=28, font=ui_font("small"))
            entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
            entry.insert(0, invite)
            entry.configure(state="readonly")
            btn = ctk.CTkButton(line, text="Copy", width=52, height=28,
                                fg_color=self.theme.get_current_color('button_normal'),
                                hover_color=self.theme.get_current_color('button_hover'))
            btn.configure(command=lambda t=invite, b=btn: self._copy(t, b))
            btn.pack(side="left")
        if s.password:
            ctk.CTkLabel(parent, text=f"Password: {s.password}", font=ui_font("small"),
                         text_color=self.theme.get_text_secondary()).pack(anchor="w", padx=16, pady=(8, 0))

    def _copy(self, text: str, button: ctk.CTkButton):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            button.configure(text="Copied")
            self.after(1500, lambda: button.winfo_exists() and button.configure(text="Copy"))
        except Exception:
            pass

    def _refresh_peers(self):
        if self._peers_frame is None:
            return
        s = self.service
        for child in self._peers_frame.winfo_children():
            child.destroy()
        names: Dict[str, str] = {}
        for p in s.peers:
            row = ctk.CTkFrame(self._peers_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            you = " (you)" if p["peer_id"] == s.my_id else ""
            crown = "👑 " if p.get("is_host") else ""
            ctk.CTkLabel(row, text=f"{crown}{p['name']}{you}", font=ui_font("body"), anchor="w"
                         ).pack(side="left", padx=(4, 0))
            if p["peer_id"] != s.my_id:
                names[p["name"]] = p["peer_id"]
                if s.is_host:
                    ctk.CTkButton(row, text="Remove", width=62, height=22, font=ui_font("small"),
                                  fg_color=self.theme.get_current_color('button_danger'),
                                  hover_color=self.theme.get_current_color('button_danger_hover'),
                                  command=lambda pid=p["peer_id"]: s.kick(pid)).pack(side="right", padx=(4, 0))
                ctk.CTkButton(row, text="Whisper", width=62, height=22, font=ui_font("small"),
                              fg_color=self.theme.get_current_color('button_normal'),
                              hover_color=self.theme.get_current_color('button_hover'),
                              command=lambda n=p["name"]: self._to_var.set(n)).pack(side="right")
        self._names_to_ids = names
        if self._to_combo is not None:
            self._to_combo.configure(values=[EVERYONE] + sorted(names))
            if self._to_var.get() not in names:
                self._to_var.set(EVERYONE)

    # ------------------------------------------------------------------ chat

    def _send(self):
        if self._msg_entry is None:
            return
        text = self._msg_entry.get().strip()
        if not text:
            return
        target = self._to_var.get()
        if target != EVERYONE and target in getattr(self, "_names_to_ids", {}):
            self.service.send_dm(self._names_to_ids[target], text)
        else:
            self.service.send_chat(text)
        self._msg_entry.delete(0, "end")

    def _append_line(self, line: dict, scroll: bool = True):
        box = self._chat_box
        if box is None:
            return
        text = box._textbox
        at_bottom = box.yview()[1] >= 0.999
        stamp = time.strftime("%H:%M", time.localtime(line["ts"]))
        box.configure(state="normal")
        if line["kind"] == "system":
            text.insert("end", f"{stamp}  {line['text']}\n", "system")
        elif line["kind"] == "dm":
            s = self.service
            if line["from"] == s.my_id:
                who = f"You → {s.peer_name(line['to']) or 'them'}"
            else:
                who = f"{line['name']} → you"
            text.insert("end", f"{stamp}  ", "time")
            text.insert("end", f"(whisper) {who}: ", "dm")
            text.insert("end", f"{line['text']}\n", "dm")
        else:
            text.insert("end", f"{stamp}  ", "time")
            text.insert("end", f"{line['name']}: ", "me" if line["mine"] else "name")
            text.insert("end", f"{line['text']}\n")
        box.configure(state="disabled")
        if scroll and (at_bottom or line.get("mine")):
            box.see("end")
