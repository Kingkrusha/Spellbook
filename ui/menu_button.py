"""A drop-down made of one button and a pop-up menu.

``CTkOptionMenu`` is slow to build (about 30 ms each; a form with dozens of them takes a second or more to open) and
holds a menu for as long as it lives. This one is a plain button that opens a ``tk.Menu`` only while it is open.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Sequence

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font


class MenuButton(ctk.CTkButton):
    def __init__(self, parent, values: Sequence[str], variable: tk.StringVar, width: int = 110, height: int = 28,
                 command: Optional[Callable[[str], None]] = None, **kwargs):
        c = get_theme_manager().get_current_color
        kwargs.setdefault("fg_color", c("button_normal"))
        kwargs.setdefault("hover_color", c("button_hover"))
        kwargs.setdefault("text_color", c("text_primary"))
        kwargs.setdefault("font", ui_font("body"))
        super().__init__(parent, text="", width=width, height=height, anchor="w",
                         command=self._open, **kwargs)
        self.values = list(values)
        self.variable = variable
        self.pick = command
        self._trace = variable.trace_add("write", lambda *_: self._sync())
        self._sync()
        self.bind("<Destroy>", self._forget, add="+")

    def _sync(self):
        try:
            self.configure(text=f"{self.variable.get()}  ▾")
        except tk.TclError:
            pass

    def _forget(self, event):
        if event.widget is self:
            try:
                self.variable.trace_remove("write", self._trace)
            except Exception:
                pass

    def configure_values(self, values: Sequence[str]):
        self.values = list(values)

    def _open(self):
        menu = tk.Menu(self, tearoff=0)
        for value in self.values:
            menu.add_command(label=value, command=lambda v=value: self._choose(v))
        try:
            menu.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        finally:
            menu.grab_release()

    def _choose(self, value: str):
        self.variable.set(value)
        if self.pick:
            self.pick(value)
