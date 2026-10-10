"""Drawing chat lines into a Tk text widget: timestamps, names, whispers, dice rolls and
clickable ``[[category:Name]]`` object links. Shared by the Session page and the chat overlay.

Links are rendered from the markup in the message (``[[spell:Fireball]]``), resolved by
name on *this* machine, so a link to homebrew the reader doesn't have simply says so
when clicked - nothing in a chat message is ever executed or fetched.
"""

from __future__ import annotations

import time
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Dict, List, Optional

from object_links import LINK_MARKUP_RE, parse_link_markup
from theme import get_theme_manager

CRIT_COLOR = "#3fb950"      # natural 20 / natural 1: fixed so they read on every theme
FUMBLE_COLOR = "#f85149"


class ChatLog:
    """Renders :class:`lan.service.SessionService` chat lines into ``text`` (a ``tk.Text``)."""

    def __init__(self, text: tk.Text, service, popup_parent: Optional[Callable[[], object]] = None):
        self.text = text
        self.service = service
        self._popup_parent = popup_parent or (lambda: text.winfo_toplevel())
        self.theme = get_theme_manager()
        self._link_n = 0
        self._bold = tkfont.Font(font=text.cget("font"))
        self._bold.configure(weight="bold")
        self._configure_tags()
        self.theme.add_listener(self._configure_tags)
        text.bind("<Destroy>", self._on_destroy, add="+")

    def _on_destroy(self, event):
        if event.widget is self.text:
            self.theme.remove_listener(self._configure_tags)

    def _configure_tags(self):
        t, theme = self.text, self.theme
        try:
            t.tag_config("system", foreground=theme.get_text_secondary())
            t.tag_config("time", foreground=theme.get_text_disabled())
            t.tag_config("name", foreground=theme.get_current_color('text_primary'))
            t.tag_config("me", foreground=theme.get_current_color('text_label'))
            t.tag_config("dm", foreground=theme.get_current_color('text_warning'))
            t.tag_config("roll", foreground=theme.get_current_color('text_label'))
            t.tag_config("total", foreground=theme.get_current_color('text_primary'), font=self._bold)
            t.tag_config("nat20", foreground=CRIT_COLOR, font=self._bold)
            t.tag_config("nat1", foreground=FUMBLE_COLOR, font=self._bold)
            t.tag_config("obj_link", foreground=theme.get_current_color('spell_link'), underline=True)
            t.tag_raise("obj_link")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ public

    def set_lines(self, lines: List[dict]) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        for line in lines:
            self.append(line, scroll=False)
        self.text.see("end")

    def append(self, line: dict, scroll: bool = True) -> None:
        t = self.text
        at_bottom = t.yview()[1] >= 0.999
        stamp = time.strftime("%H:%M", time.localtime(line["ts"]))
        kind = line["kind"]
        t.configure(state="normal")
        if kind == "system":
            t.insert("end", f"{stamp}  ", "time")
            self._insert_rich(line["text"], "system")
        elif kind == "dm":
            s = self.service
            who = (f"You → {s.peer_name(line['to']) or 'them'}" if line["from"] == s.my_id
                   else f"{line['name']} → you")
            t.insert("end", f"{stamp}  ", "time")
            t.insert("end", f"(whisper) {who}: ", "dm")
            self._insert_rich(line["text"], "dm")
        elif kind == "roll":
            self._insert_roll(stamp, line)
        else:
            t.insert("end", f"{stamp}  ", "time")
            t.insert("end", f"{line['name']}: ", "me" if line["mine"] else "name")
            self._insert_rich(line["text"])
        t.insert("end", "\n")
        t.configure(state="disabled")
        if scroll and (at_bottom or line.get("mine")):
            t.see("end")

    # ---------------------------------------------------------------- internals

    def _insert_roll(self, stamp: str, line: dict) -> None:
        t = self.text
        r = line.get("roll") or {}
        t.insert("end", f"{stamp}  ", "time")
        who = "You" if line["mine"] else line["name"]
        private = "(private) " if r.get("private") else ""
        t.insert("end", f"🎲 {private}{who} rolled {r.get('expr', '')}", "roll")
        if r.get("label"):
            t.insert("end", f" ({r['label']})", "roll")
        t.insert("end", f": {r.get('detail', '')} = ", "roll")
        crit = r.get("crit") or ""
        total_tags = ("total", crit) if crit else ("total",)
        t.insert("end", str(r.get("total", "")), total_tags)
        if crit:
            t.insert("end", "  natural 20!" if crit == "nat20" else "  natural 1…", crit)

    def _insert_rich(self, text: str, *tags: str) -> None:
        """Insert ``text``, turning ``[[...]]`` markup into clickable links."""
        pos = 0
        for m in LINK_MARKUP_RE.finditer(text):
            if m.start() > pos:
                self.text.insert("end", text[pos:m.start()], tags)
            category, name, display = parse_link_markup(m.group(1))
            self._insert_link(category, name, display, tags)
            pos = m.end()
        if pos < len(text):
            self.text.insert("end", text[pos:], tags)

    def _insert_link(self, category: str, name: str, display: str, tags) -> None:
        tag = f"chatlink{self._link_n}"
        self._link_n += 1
        self.text.insert("end", display, tuple(tags) + ("obj_link", tag))
        self.text.tag_bind(tag, "<Button-1>", lambda _e, c=category, n=name: self._open(c, n))
        self.text.tag_bind(tag, "<Enter>", lambda _e: self.text.configure(cursor="hand2"))
        self.text.tag_bind(tag, "<Leave>", lambda _e: self.text.configure(cursor=""))

    def _open(self, category: str, name: str) -> None:
        try:
            from ui.object_link_widgets import open_link_popup
            open_link_popup(self._popup_parent(), category, name)
        except Exception as e:
            print(f"Could not open link: {e}")
