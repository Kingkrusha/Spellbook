"""
The plumbing of the Dice Analyzer's charts: each is one ``tk.Canvas`` (one window handle however many bars it
draws) that redraws on a short timer after it is resized or the theme changes, follows the mouse for hover hints,
and lets the theme manager go when it is destroyed. A chart subclasses :class:`ChartCanvas`, draws in ``_draw`` and
handles ``_on_motion`` / ``_set_hover``.
"""

import tkinter as tk

from theme import get_theme_manager


class ChartCanvas(tk.Canvas):
    def __init__(self, parent, **kw):
        self.theme = get_theme_manager()
        super().__init__(parent, highlightthickness=0, bd=0, bg=self._c("bg_secondary"), **kw)
        self._hover = None
        self._job = None
        self.bind("<Configure>", lambda e: self._schedule())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.theme.add_listener(self._on_theme)
        self.bind("<Destroy>", self._on_destroy, add="+")

    # ---- what a chart provides

    def _draw(self):
        raise NotImplementedError

    def _on_motion(self, event):
        raise NotImplementedError

    def _set_hover(self, value):
        raise NotImplementedError

    # ---- plumbing

    def _c(self, role: str) -> str:
        return str(self.theme.get_current_color(role))

    def _on_theme(self):
        try:
            self.configure(bg=self._c("bg_secondary"))
            self._schedule()
        except tk.TclError:
            pass

    def _on_destroy(self, event):
        if event.widget is self:
            self.theme.remove_listener(self._on_theme)
            if self._job is not None:
                try:
                    self.after_cancel(self._job)
                except tk.TclError:
                    pass

    def _schedule(self):
        if self._job is None:
            try:
                self._job = self.after(30, self._draw)
            except tk.TclError:
                pass
