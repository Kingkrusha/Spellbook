"""
The "Sort:" drop-down and its ascending/descending button on the collection pages.

The choices and the sorting itself are in ``collection_sort.py``. The last choice is remembered per collection.
A page uses it in two places::

    self.sorter = SortControl(bar, "feats", lambda: collection_sort.sorts_for("feats"),
                              on_change=lambda: self._on_filter_changed(immediate=True))
    self.sorter.pack(side="left", padx=(0, 15))
    ...
    filtered = self.sorter.sort(filtered)                 # in the page's filtering

The choices are read again when the person adds, renames or removes one of their own fields, and the page is
re-sorted when a value of the field it is sorted by changes.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

import collection_sort as cs
from settings import get_settings_manager
from theme import get_theme_manager
from typography import ui_font

UP = "↑"
DOWN = "↓"


class SortControl(ctk.CTkFrame):
    def __init__(self, parent, collection: str, fields: Callable[[], List[cs.SortField]],
                 on_change: Callable[[], None], settings_manager=None, watch_fields: bool = True,
                 height: int = 35):
        super().__init__(parent, fg_color="transparent")
        self.collection = collection
        self._fields_fn = fields
        self.on_change = on_change
        self.settings_manager = settings_manager or get_settings_manager()
        self._fields: List[cs.SortField] = fields()
        label, self.descending = cs.remembered(self.settings_manager.settings, collection)
        if cs.find(self._fields, label) is None:
            label = cs.default_for(collection) if cs.find(self._fields, cs.default_for(collection)) else cs.NAME
        theme = get_theme_manager()

        ctk.CTkLabel(self, text="Sort:").pack(side="left", padx=(0, 5))
        self.var = ctk.StringVar(value=label)
        self.combo = ctk.CTkComboBox(self, width=140, height=height, values=self._labels(), variable=self.var,
                                     state="readonly", command=lambda _v: self._changed())
        self.combo.pack(side="left", padx=(0, 4))
        self.direction_btn = ctk.CTkButton(
            self, text="", width=36, height=height, font=ui_font("body", bold=True),
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self.toggle_direction)
        self.direction_btn.pack(side="left")
        self.flow_with_previous = False
        self.direction_btn.flow_with_previous = True     # (ui/flow_bar.py: stays beside the drop-down)
        self._tooltip = None
        try:
            from ui.tooltip import HoverTooltip
            self._tooltip = HoverTooltip(self.direction_btn, "")
        except Exception:
            pass
        self._show_direction()

        self._mgr = None
        if watch_fields:
            try:
                import custom_collections as cc
                self._mgr = cc.get_collection_manager()
                self._mgr.add_listener(self._definitions_changed)
                self._mgr.add_value_listener(self._values_changed)
            except Exception:
                self._mgr = None
        self.bind("<Destroy>", self._destroyed, add="+")

    # ---- reading the choice

    @property
    def field(self) -> Optional[cs.SortField]:
        return cs.find(self._fields, self.var.get())

    def sort(self, entries) -> list:
        """``entries`` in the chosen order."""
        return cs.sort_entries(entries, self.field, self.descending)

    def set(self, label: str, descending: bool = False):
        """Choose a sort (as if the person had), e.g. back to Name on Clear Filters."""
        if cs.find(self._fields, label) is None:
            label = cs.NAME
        self.var.set(label)
        self.descending = bool(descending)
        self._show_direction()
        self._changed()

    def toggle_direction(self):
        self.descending = not self.descending
        self._show_direction()
        self._changed()

    # ---- inside

    def _labels(self) -> List[str]:
        return [f.label for f in self._fields]

    def _changed(self):
        cs.remember(self.settings_manager, self.collection, self.var.get(), self.descending)
        self.on_change()

    def _show_direction(self):
        self.direction_btn.configure(text=DOWN if self.descending else UP)
        if self._tooltip is not None:
            self._tooltip.text = ("Largest first (Z to A, highest first). Click for smallest first."
                                  if self.descending else
                                  "Smallest first (A to Z, lowest first). Click for largest first.")

    def refresh_fields(self):
        """Read the choices again (an added field was made, renamed or removed)."""
        self._fields = self._fields_fn()
        self.combo.configure(values=self._labels())
        if cs.find(self._fields, self.var.get()) is None:
            self.var.set(cs.NAME)
            self.on_change()

    def _definitions_changed(self):
        try:
            if self.winfo_exists():
                self.refresh_fields()
        except tk.TclError:
            pass

    def _values_changed(self, collection: str, _name: str):
        if collection != self.collection:
            return
        # The added-field values are read once per list of choices: read them again, and re-sort if the
        # list is sorted by anything but its name
        self._fields = self._fields_fn()
        if self.var.get() != cs.NAME:
            try:
                if self.winfo_exists():
                    self.on_change()
            except tk.TclError:
                pass

    def _destroyed(self, event):
        if event.widget is self and self._mgr is not None:
            self._mgr.remove_listener(self._definitions_changed)
            self._mgr.remove_value_listener(self._values_changed)
            self._mgr = None

