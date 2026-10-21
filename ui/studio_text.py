"""
A small read-only rich text box for the Studio's side panels.

The Insights panel shows a dozen search results, each with a title, a line of detail, the reason it matched and an
excerpt with the shared words lit up. Building those from labels and buttons would create (and later destroy)
around a hundred CustomTkinter widgets every time the draft changes; one ``tk.Text`` with tags does it in a few
milliseconds. Write with ``add(text, *tags)``; give a run a click handler with ``link(tag, callback)``.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font


# Status colours for text (the theme's button colours are backgrounds, too dark to read as text). Like the rarity
# colours they are fixed per light / dark mode rather than part of the colour theme.
STATUS_COLORS = {"good": ("#1e7e34", "#5fcf7a"), "warn": ("#9a5b00", "#f2b54a"), "bad": ("#b02a37", "#ff8585")}


def status_color(name: str) -> str:
    light, dark = STATUS_COLORS[name]
    return light if ctk.get_appearance_mode().lower() == "light" else dark


class StudioText(ctk.CTkFrame):
    """A scrolling, read-only text area with named styles and clickable runs."""

    def __init__(self, parent, bg_role: str = "bg_primary", font_size: int = 12, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.theme = get_theme_manager()
        self.bg_role = bg_role
        self.font_size = font_size
        self._links: Dict[str, Callable[[], None]] = {}
        self._link_count = 0
        self.text = tk.Text(self, wrap="word", relief="flat", borderwidth=0, highlightthickness=0, padx=10, pady=8,
                            cursor="arrow", state="disabled", takefocus=0, spacing1=0, spacing2=2, spacing3=0,
                            undo=False, width=10, height=4)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Button-1>", lambda _e: self.text.focus_set(), add="+")
        self._apply()
        self.theme.add_listener(self._apply)
        self.bind("<Destroy>", self._on_destroy, add="+")

    # ---- colours and styles

    def _color(self, role: str) -> str:
        value = self.theme.get_current_color(role)
        return value[1] if isinstance(value, tuple) else str(value)

    def _apply(self):
        try:
            t = self.text
            fg = self._color("text_primary")
            t.configure(bg=self._color(self.bg_role), fg=fg, insertbackground=fg,
                        selectbackground=self._color("accent_primary"), selectforeground=self._color("text_on_accent"),
                        inactiveselectbackground=self._color("accent_primary"), font=ui_font("body", self.font_size))
            size = self.font_size
            t.tag_configure("title", font=ui_font("subheading", size + 1, bold=True), spacing1=10)
            t.tag_configure("heading", font=ui_font("subheading", size + 2, bold=True), spacing1=6, spacing3=2)
            t.tag_configure("bold", font=ui_font("body", size, bold=True))
            t.tag_configure("small", font=ui_font("small", max(9, size - 1)), foreground=self._color("text_secondary"))
            t.tag_configure("muted", foreground=self._color("text_secondary"))
            t.tag_configure("label", foreground=self._color("text_label"), font=ui_font("body", size, bold=True))
            t.tag_configure("accent", foreground=self._color("accent_primary"), font=ui_font("body", size, bold=True))
            t.tag_configure("good", foreground=status_color("good"))
            t.tag_configure("warn", foreground=status_color("warn"))
            t.tag_configure("bad", foreground=status_color("bad"))
            t.tag_configure("score", font=ui_font("small", max(9, size - 1), bold=True),
                            foreground=self._color("accent_primary"))
            t.tag_configure("hit", background=self._color("level_9"), foreground=self._color("text_primary"))
            t.tag_configure("link", foreground=self._color("spell_link"), underline=True)
            t.tag_configure("indent", lmargin1=14, lmargin2=14)
            t.tag_configure("card", lmargin1=0, lmargin2=0, spacing3=0)
            t.tag_configure("gap", font=ui_font("body", 5), spacing1=0, spacing3=0)
            t.tag_configure("rule", font=ui_font("body", 3), background=self._color("border"))
            t.tag_raise("hit")
            t.tag_raise("sel")
        except tk.TclError:
            pass

    def _on_destroy(self, event):
        if event.widget is self:
            try:
                self.theme.remove_listener(self._apply)
            except Exception:
                pass

    # ---- writing

    def clear(self):
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.configure(state="disabled")
        for tag in self._links:
            try:
                t.tag_delete(tag)
            except tk.TclError:
                pass
        self._links = {}

    def add(self, text: str, *tags: str):
        t = self.text
        t.configure(state="normal")
        t.insert("end", text, tags)
        t.configure(state="disabled")

    def add_highlighted(self, text: str, spans: List[tuple], *tags: str):
        """``text`` with the character ranges in ``spans`` lit up."""
        pos = 0
        for a, b in sorted(spans):
            if a < pos:
                continue
            if a > pos:
                self.add(text[pos:a], *tags)
            self.add(text[a:b], "hit", *tags)
            pos = b
        if pos < len(text):
            self.add(text[pos:], *tags)

    def link(self, text: str, callback: Callable[[], None], *tags: str):
        """A run of text that calls ``callback`` when clicked."""
        self._link_count += 1
        name = f"lnk{self._link_count}"
        self._links[name] = callback
        t = self.text
        t.tag_configure(name)
        t.tag_bind(name, "<Button-1>", lambda _e, n=name: self._click(n))
        t.tag_bind(name, "<Enter>", lambda _e: t.configure(cursor="hand2"))
        t.tag_bind(name, "<Leave>", lambda _e: t.configure(cursor="arrow"))
        self.add(text, "link", name, *tags)

    def _click(self, name: str):
        callback = self._links.get(name)
        if callback is not None:
            callback()

    def to_top(self):
        self.text.yview_moveto(0)

    def plain(self) -> str:
        return self.text.get("1.0", "end-1c")
