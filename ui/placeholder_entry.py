"""
A text box that shows its grey hint ("Search monsters...") although it is tied to a variable.

CustomTkinter writes the hint into the box itself, so it gives the hint up as soon as the box has a ``textvariable``:
the hint would end up in the variable, and the page would search for "Search monsters...". Nearly every search box
and Min / Max box of the app has a variable, so none of them ever showed its hint.

``PlaceholderEntry`` gives the box a variable of its own and keeps the two in step, leaving the hint out: the
variable the page handed over only ever holds what was really typed.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class PlaceholderEntry(ctk.CTkEntry):
    """``ctk.CTkEntry`` whose ``placeholder_text`` shows with a ``textvariable`` too."""

    def __init__(self, master, textvariable=None, **kwargs):
        super().__init__(master, **kwargs)
        self._shared = textvariable
        self._shared_trace = ""
        self._syncing = False
        if textvariable is None:
            return
        # The box's own variable starts as what the box shows (the hint), so tying it on changes nothing.
        self._inner = tk.StringVar(master=self, value=self._entry.get())
        self._entry.configure(textvariable=self._inner)
        self._inner.trace_add("write", self._typed)
        self._shared_trace = textvariable.trace_add("write", self._set_from_outside)
        if textvariable.get():
            self._set_from_outside()

    def _typed(self, *_args):
        """The box changed: pass it on, unless it is the hint coming or going."""
        if self._syncing or self._placeholder_text_active:
            return
        value = self._inner.get()
        if self._shared.get() != value:
            self._syncing = True
            try:
                self._shared.set(value)
            finally:
                self._syncing = False

    def _set_from_outside(self, *_args):
        """The page set the variable (Clear Filters, a remembered search): show that."""
        if self._syncing:
            return
        value = self._shared.get()
        if value == self.get():
            return
        self._syncing = True
        try:
            self.delete(0, "end")                # (brings the hint back when nothing is left and nobody is typing)
            if value:
                self.insert(0, value)
        except tk.TclError:
            pass
        finally:
            self._syncing = False

    def destroy(self):
        if self._shared is not None and self._shared_trace:
            try:
                self._shared.trace_remove("write", self._shared_trace)
            except (tk.TclError, ValueError):
                pass
            self._shared_trace = ""
        super().destroy()
