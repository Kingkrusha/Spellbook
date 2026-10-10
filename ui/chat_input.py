"""The chat entry box: Enter to send, up/down for earlier messages, a 🔗 button to link an
object (spell, item, monster...), ``/w Name message`` whispers and ``/help``.

``/roll`` and ``/gmroll`` are plain text here - the host handles them (``lan.host``) so
every roll is made, and can be trusted, in one place.
"""

from __future__ import annotations

from typing import Callable, List, Optional

import customtkinter as ctk

from object_links import (LINK_MARKUP_RE, find_target, format_link_markup, get_link_targets,
                          parse_link_markup, search_links)
from theme import get_theme_manager
from typography import ui_font

HELP_TEXT = (
    "Commands: /roll 2d6+3 · /roll d20+5 adv Perception (adv / dis for advantage / disadvantage, "
    "4d6kh3 keeps the best 3) · /gmroll d20 (only you and the DM see it) · /w Name message (whisper). "
    "Link a spell, item or monster with the 🔗 button; everyone can click it to read it."
)


def qualify_links(text: str) -> str:
    """``[[Fireball]]`` means a spell. If the name is really something else (``[[Longsword]]``),
    spell out its category so everyone resolves it the same way."""
    def fix(m):
        inner = m.group(1)
        if ":" in inner.split("|", 1)[0]:
            return m.group(0)
        _cat, name, display = parse_link_markup(inner)
        try:
            if find_target("spell", name) is not None:
                return m.group(0)
            for t in get_link_targets(enabled_only=False):
                if t.name.lower() == name.lower():
                    return f"[[{format_link_markup(t.category, t.name, display)}]]"
        except Exception:
            pass
        return m.group(0)
    return LINK_MARKUP_RE.sub(fix, text)


class LinkPicker(ctk.CTkToplevel):
    """Small search window: type a name, click a result, and its link markup is inserted."""

    def __init__(self, parent, on_pick: Callable[[str], None]):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self._on_pick = on_pick
        self._after = None
        self.title("Link an object")
        self.geometry("360x330")
        self.attributes("-topmost", True)
        self.transient(parent.winfo_toplevel())

        self.entry = ctk.CTkEntry(self, height=32, placeholder_text="Search spells, items, monsters, feats…")
        self.entry.pack(fill="x", padx=12, pady=(12, 6))
        self.results = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.results.pack(fill="both", expand=True, padx=8, pady=(0, 10))
        self.entry.bind("<KeyRelease>", lambda _e: self._debounce())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(120, self.entry.focus_force)
        self._targets = None

    def _debounce(self):
        if self._after is not None:
            self.after_cancel(self._after)
        self._after = self.after(150, self._search)

    def _search(self):
        self._after = None
        for child in self.results.winfo_children():
            child.destroy()
        query = self.entry.get().strip()
        if len(query) < 2:
            return
        if self._targets is None:
            self._targets = get_link_targets(enabled_only=False)
        for t in search_links(query, self._targets, limit=10):
            ctk.CTkButton(
                self.results, anchor="w", height=28, font=ui_font("body"),
                text=f"{t.name}   ({t.category_label}{' · ' + t.subtitle if t.subtitle else ''})",
                fg_color="transparent", hover_color=self.theme.get_current_color('accent_primary'),
                text_color=self.theme.get_current_color('text_primary'),
                command=lambda t=t: self._pick(t)).pack(fill="x", pady=1)

    def _pick(self, target):
        self._on_pick(f"[[{format_link_markup(target.category, target.name, target.name)}]]")
        self.destroy()


class ChatInput(ctk.CTkFrame):
    def __init__(self, parent, service, get_whisper_target: Optional[Callable[[], Optional[str]]] = None,
                 height: int = 34, bg=None, **kwargs):
        super().__init__(parent, fg_color=bg if bg is not None else "transparent", **kwargs)
        self.service = service
        self._target = get_whisper_target or (lambda: None)
        self._history: List[str] = []
        self._hist_pos = 0
        theme = get_theme_manager()

        self.entry = ctk.CTkEntry(self, height=height, placeholder_text="Say something, or /help…")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda _e: self.submit())
        self.entry.bind("<Up>", lambda _e: self._recall(-1))
        self.entry.bind("<Down>", lambda _e: self._recall(1))
        self.entry.bind("<Button-1>", lambda _e: self.entry.focus_force(), add="+")

        ctk.CTkButton(self, text="🔗", width=34, height=height,
                      fg_color=theme.get_current_color('button_normal'),
                      hover_color=theme.get_current_color('button_hover'),
                      command=self._open_picker).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self, text="Send", width=64, height=height,
                      fg_color=theme.get_current_color('accent_primary'),
                      hover_color=theme.get_current_color('accent_hover'),
                      command=self.submit).pack(side="left")

    def focus(self):
        self.entry.focus_force()

    def _open_picker(self):
        LinkPicker(self, self._insert)

    def _insert(self, markup: str):
        self.entry.insert("insert", markup)
        self.entry.focus_force()

    def _recall(self, step: int):
        if not self._history:
            return "break"
        self._hist_pos = max(0, min(len(self._history), self._hist_pos + step))
        self.entry.delete(0, "end")
        if self._hist_pos < len(self._history):
            self.entry.insert(0, self._history[self._hist_pos])
        return "break"

    def submit(self):
        text = qualify_links(self.entry.get().strip())
        if not text:
            return
        self._history.append(text)
        self._history = self._history[-50:]
        self._hist_pos = len(self._history)
        self.entry.delete(0, "end")

        cmd = text.split(" ", 1)[0].lower()
        rest = text[len(cmd):].strip()
        if cmd in ("/help", "/?"):
            self.service.note(HELP_TEXT)
        elif cmd in ("/w", "/whisper", "/msg"):
            self._whisper(rest)
        else:
            target = self._target()
            if target and not text.startswith("/"):
                self.service.send_dm(target, text)
            else:
                self.service.send_chat(text)

    def _whisper(self, rest: str):
        """``/w Name message`` - the name may contain spaces, so match the longest peer name."""
        s = self.service
        best = None
        for p in s.peers:
            if p["peer_id"] == s.my_id:
                continue
            name = p["name"].lower()
            if rest.lower().startswith(name + " ") and (best is None or len(name) > len(best["name"])):
                best = p
        if best is None:
            s.note("Whisper to whom? Use /w Name message, with the name as shown in the player list.")
        else:
            s.send_dm(best["peer_id"], rest[len(best["name"]):].strip())
