"""
The "▼ Filters" button of a collection page and the panel of further filters it folds open.

Every collection page keeps a short top bar (back, search, the one or two filters used most, Sort and the
action buttons); the rest of its filters sit in a panel under it that is folded away until "▼ Filters" is
clicked, as the Spells page always did. That keeps the header to one row.

While any filter in the panel is set (it differs from how the page started), the button shows a dot and takes
the accent colour, so a folded panel can't quietly hide why entries are missing.

    folding = FoldingFilters(page, top_bar)
    row = folding.row()                          # a row of filters inside the panel
    ...
    folding.add_button()                         # after the top bar's left-hand controls
    folding.set_before(page.content)             # the panel opens just above this
    folding.remember()                           # once every filter is built: "how the page started"
    folding.refresh()                            # after each filter change
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from theme import get_theme_manager

OPEN, CLOSED = "▲ Filters", "▼ Filters"
SET_MARK = "  •"


class FoldingFilters:
    """The folding filters panel of one page (see the module docstring)."""

    def __init__(self, page, top_bar, on_open: Optional[Callable[[], None]] = None,
                 padx: int = 10, pady=(0, 10)):
        self.page = page
        self.top_bar = top_bar
        self.on_open = on_open
        self.padx, self.pady = padx, pady
        self.expanded = False
        self.button: Optional[ctk.CTkButton] = None
        self._before = None
        self._start: Optional[tuple] = None
        self._set = False
        theme = get_theme_manager()
        self.frame = ctk.CTkFrame(page, corner_radius=10, fg_color=theme.get_current_color('bg_secondary'))
        self.content = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.content.pack(fill="x", padx=12, pady=10)
        theme.add_listener(self._on_theme_changed)
        self.frame.bind("<Destroy>", self._destroyed, add="+")

    # ------------------------------------------------------------------ building

    def row(self, pady=(0, 6)) -> ctk.CTkFrame:
        """A further row of filters in the panel."""
        row = ctk.CTkFrame(self.content, fg_color="transparent")
        row.pack(fill="x", pady=pady)
        return row

    @property
    def rows(self) -> list:
        return [w for w in self.content.winfo_children() if isinstance(w, ctk.CTkFrame)]

    def add_button(self, bar=None, padx=(0, 0), height: int = 35) -> ctk.CTkButton:
        """The "▼ Filters" button, packed at the left of ``bar`` (the top bar) after what is already there."""
        theme = get_theme_manager()
        self.button = ctk.CTkButton(
            bar or self.top_bar, text=CLOSED, width=90, height=height,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self.toggle)
        self.button.pack(side="left", padx=padx)
        return self.button

    def set_before(self, widget):
        """The panel opens just above ``widget`` (the page's list and details)."""
        self._before = widget

    # ------------------------------------------------------------------ open / closed

    def toggle(self):
        self.set_open(not self.expanded)

    def set_open(self, value: bool):
        self.expanded = bool(value)
        if self.expanded:
            pack = {"fill": "x", "padx": self.padx, "pady": self.pady}
            if self._before is not None and self._before.winfo_exists():
                pack["before"] = self._before
            self.frame.pack(**pack)
            if self.on_open:
                self.on_open()
        else:
            self.frame.pack_forget()
        self._paint()

    # ------------------------------------------------------------------ "a filter in here is set"

    def _values(self) -> tuple:
        """What every control in the panel shows now (choices, ticks, typed text, "2 sources (include)" ...)."""
        out = []
        stack = [self.content]
        while stack:
            widget = stack.pop(0)
            for child in widget.winfo_children():
                stack.append(child)
                try:
                    if isinstance(child, (ctk.CTkComboBox, ctk.CTkOptionMenu, ctk.CTkCheckBox,
                                          ctk.CTkSwitch)):
                        out.append(child.get())
                    elif isinstance(child, ctk.CTkEntry):
                        shared = getattr(child, "_shared", None)      # ui/placeholder_entry.py
                        out.append(shared.get() if shared is not None else child.get())
                    elif isinstance(child, (ctk.CTkLabel, ctk.CTkButton)):
                        out.append(child.cget("text"))
                except Exception:
                    out.append(None)
        return tuple(out)

    def remember(self):
        """Take the panel as it is now as "nothing set" (call it once the page is built)."""
        self._start = self._values()
        self._set = False
        self._paint()

    def refresh(self):
        """Show whether any filter in the panel is set."""
        if self._start is None or not self.frame.winfo_exists():
            return
        now = self._values()
        if len(now) != len(self._start):        # (the panel was rebuilt)
            self._start = now
        self._set = now != self._start
        self._paint()

    @property
    def is_set(self) -> bool:
        return self._set

    def _paint(self):
        if self.button is None:
            return
        try:
            if not self.button.winfo_exists():
                return
        except Exception:
            return
        theme = get_theme_manager()
        text = (OPEN if self.expanded else CLOSED) + (SET_MARK if self._set else "")
        self.button.configure(
            text=text, width=100 if self._set else 90,
            fg_color=theme.get_current_color('accent_primary' if self._set else 'button_normal'),
            hover_color=theme.get_current_color('accent_hover' if self._set else 'button_hover'))

    def _on_theme_changed(self, *_args):
        try:
            self.frame.configure(fg_color=get_theme_manager().get_current_color('bg_secondary'))
        except Exception:
            return
        self._paint()

    def _destroyed(self, event):
        if event.widget is not self.frame:
            return
        try:
            get_theme_manager().remove_listener(self._on_theme_changed)
        except Exception:
            pass
