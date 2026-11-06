"""
The "Your fields" filter on the built-in collection pages (spells, feats, classes, ...).

Fields someone added to a built-in collection (custom_collections.py) can be filtered on, like a new collection's
own fields. A page doesn't have room for one drop-down per field, so it gets one button that opens a small window
with them; the button says how many are set. It hides itself while the collection has no field to filter on.

A page uses it in three places::

    self.extra_filter = ExtraFieldFilter(self, "feats", on_change=lambda: self._on_filter_changed(immediate=True))
    self.extra_filter.button(bar).pack(side="left", padx=(0, 15))      # in the filter bar
    ...
    if not self.extra_filter.passes(feat.name): continue               # in the page's filtering
    ...
    self.extra_filter.clear()                                          # in Clear Filters
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import custom_collections as cc
from theme import get_theme_manager
from typography import ui_font

ANY = "Any"


class ExtraFieldFilter:
    def __init__(self, page, collection: str, on_change: Callable[[], None]):
        self.page = page
        self.collection = collection
        self.on_change = on_change
        self.mgr = cc.get_collection_manager()
        self.wanted: Dict[str, str] = {}          # field id -> the value chosen (absent = any)
        self._values: Optional[Dict[str, dict]] = None
        self._button: Optional[ctk.CTkButton] = None
        self._pack: Optional[dict] = None
        self._window: Optional[ctk.CTkToplevel] = None
        self.mgr.add_listener(self._definitions_changed)
        self.mgr.add_value_listener(self._values_changed)
        page.bind("<Destroy>", self._destroyed, add="+")

    # ---- the filter itself

    def fields(self) -> List[cc.FieldDef]:
        return [f for f in self.mgr.builtin_fields(self.collection) if f.filterable]

    @property
    def active(self) -> bool:
        return bool(self.wanted)

    def passes(self, name: str) -> bool:
        """Whether the entry called ``name`` has every chosen value."""
        if not self.wanted:
            return True
        if self._values is None:
            self._values = self.mgr.extra_values_by_name(self.collection)
        values = self._values.get((name or "").lower(), {})
        fields = {f.id: f for f in self.fields()}
        return all(cc.value_matches(fields[fid], values.get(fid), wanted)
                   for fid, wanted in self.wanted.items() if fid in fields)

    def set(self, field_id: str, value: str):
        if value in ("", ANY, None):
            self.wanted.pop(field_id, None)
        else:
            self.wanted[field_id] = value
        self._update_button()
        self.on_change()

    def clear(self):
        """Back to "any" for every field (Clear Filters). Doesn't call on_change: the page refilters itself."""
        self.wanted.clear()
        self._update_button()
        if self._window is not None:
            self._close_window()

    # ---- the button

    def button(self, parent, **pack) -> ctk.CTkButton:
        """The "Your fields" button. Pack it with ``pack`` given here (not .pack()), so it can hide itself."""
        theme = get_theme_manager()
        self._button = ctk.CTkButton(parent, text="Your fields ▾", width=110, height=30,
                                     fg_color=theme.get_current_color('button_normal'),
                                     hover_color=theme.get_current_color('button_hover'),
                                     text_color=theme.get_current_color('text_primary'),
                                     font=ui_font("body"), command=self.open)
        self._pack = pack
        self._update_button()
        return self._button

    def _update_button(self):
        b = self._button
        if b is None:
            return
        try:
            if not b.winfo_exists():
                return
        except tk.TclError:
            return
        shown = bool(self.fields())
        if shown:
            b.configure(text=f"Your fields ({len(self.wanted)}) ▾" if self.wanted else "Your fields ▾")
            if not b.winfo_manager() and self._pack is not None:
                b.pack(**self._pack)
        elif b.winfo_manager():
            b.pack_forget()

    # ---- the window with one drop-down per field

    def open(self):
        if self._window is not None:
            try:
                self._window.lift()
                return
            except tk.TclError:
                self._window = None
        fields = self.fields()
        if not fields:
            return
        theme = get_theme_manager()
        win = ctk.CTkToplevel(self.page)
        win.title("Filter by your fields")
        win.resizable(False, False)
        win.transient(self.page.winfo_toplevel())
        self._window = win
        win.protocol("WM_DELETE_WINDOW", self._close_window)
        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=14)
        ctk.CTkLabel(body, text="Show only entries with:", font=ui_font("body", bold=True),
                     anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self._combos = {}
        for i, f in enumerate(fields, start=1):
            ctk.CTkLabel(body, text=f"{f.label}:", font=ui_font("body"), anchor="w").grid(
                row=i, column=0, sticky="w", padx=(0, 10), pady=3)
            options = [ANY] + self.mgr.extra_field_options(self.collection, f)
            var = ctk.StringVar(value=self.wanted.get(f.id, ANY))
            combo = ctk.CTkComboBox(body, values=options, variable=var, width=200, state="readonly",
                                    command=lambda value, fid=f.id: self.set(fid, value))
            combo.grid(row=i, column=1, sticky="w", pady=3)
            self._combos[f.id] = var
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ctk.CTkButton(row, text="Any for all", width=100, fg_color=theme.get_current_color('button_normal'),
                      hover_color=theme.get_current_color('button_hover'),
                      command=self._reset).pack(side="left")
        ctk.CTkButton(row, text="Done", width=80, command=self._close_window).pack(side="right")
        try:
            from ui.window_utils import center_on_parent
            center_on_parent(win, self.page)
        except Exception:
            pass

    def _reset(self):
        self.wanted.clear()
        for var in getattr(self, "_combos", {}).values():
            var.set(ANY)
        self._update_button()
        self.on_change()

    def _close_window(self):
        win, self._window = self._window, None
        if win is not None:
            try:
                win.destroy()
            except tk.TclError:
                pass

    # ---- keeping up

    def _definitions_changed(self):
        known = {f.id for f in self.fields()}
        dropped = [fid for fid in self.wanted if fid not in known]
        for fid in dropped:
            self.wanted.pop(fid, None)
        self._values = None
        self._update_button()
        if dropped:
            self.on_change()

    def _values_changed(self, collection: str, _name: str):
        if collection == self.collection:
            self._values = None
            if self.wanted:
                self.on_change()

    def _destroyed(self, event):
        if event.widget is self.page:
            self.mgr.remove_listener(self._definitions_changed)
            self.mgr.remove_value_listener(self._values_changed)
            self._close_window()
