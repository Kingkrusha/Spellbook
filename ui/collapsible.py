"""A titled section of a long form that folds away (a header you click, and a body that shows or hides)."""

from __future__ import annotations

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font


class CollapsibleSection(ctk.CTkFrame):
    """``section.body`` is where the contents go; clicking the title shows or hides it.

    The contents stay alive while hidden, so a form can still be read."""

    def __init__(self, parent, title: str, open: bool = True, note: str = ""):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.title = title
        self.note = note
        self._open = False
        c = self.theme.get_current_color
        self.header = ctk.CTkButton(
            self, text="", anchor="w", height=30, fg_color="transparent", hover_color=c("button_hover"),
            text_color=c("accent_primary"), font=ui_font("subheading", 15, bold=True), command=self.toggle)
        self.header.pack(fill="x", pady=(10, 0))
        self.rule = ctk.CTkFrame(self, height=2, fg_color=c("border"))
        self.rule.pack(fill="x", pady=(0, 6))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.set_open(open)

    @property
    def is_open(self) -> bool:
        return self._open

    def set_open(self, value: bool):
        self._open = bool(value)
        if self._open:
            self.body.pack(fill="x")
        else:
            self.body.pack_forget()
        arrow = "▾" if self._open else "▸"
        self.header.configure(text=f"{arrow}  {self.title}" + (f"   {self.note}" if self.note and not self._open else ""))

    def toggle(self):
        self.set_open(not self._open)
