"""Parts of a long scrolling page that are built only when they come near the view.

A class page has some 40 features, each a title and several paragraphs and tables: about 1,700 widgets, two and a
half seconds to build, most of them far below what the window shows. ``LazySections`` keeps, for each part, an
empty frame of about the right height (``estimate_text_height``) and fills it in when it scrolls within a screen
of the view. A part filled in above the view changes the page's height above what is shown: the view is moved
by the difference, so what is on screen stays where it is.

    lazy = LazySections(scrollable_frame)
    holder = lazy.add(parent, build=lambda frame: ..., height=estimate)   # packs the holder in ``parent``
    lazy.clear()                                                          # when the page is rebuilt
"""

from __future__ import annotations

import time
from typing import Callable, List, Optional

import customtkinter as ctk

BUDGET = 0.03            # seconds of building per pass, so scrolling stays smooth
AHEAD = 1.0              # build this many screens below the view (and the screen above), so scrolling finds them ready


class _Part:
    __slots__ = ("holder", "build")

    def __init__(self, holder, build):
        self.holder = holder
        self.build = build


def estimate_text_height(text: str, width_px: int, font, extra_lines: int = 0) -> int:
    """About how tall ``text`` is when wrapped to ``width_px`` in ``font`` (a Tk or CTk font), in pixels."""
    try:
        line = max(1, int(font.metrics("linespace")))
        char = max(1, font.measure("abcdefghijklmnopqrstuvwxyz") / 26)
    except Exception:
        line, char = 18, 7
    per_line = max(10, int(max(100, width_px) / char))
    lines = extra_lines
    for paragraph in (text or "").split("\n"):
        lines += max(1, -(-len(paragraph) // per_line))
    return int(lines * line * 1.15)


class LazySections:
    """Builds the parts of ``scroll`` (a CTkScrollableFrame) that come near its view; see the module's notes."""

    def __init__(self, scroll: ctk.CTkScrollableFrame):
        self.scroll = scroll
        self.canvas = scroll._parent_canvas
        self._parts: List[_Part] = []
        self._after: Optional[str] = None
        previous = self.canvas.cget("yscrollcommand")
        self.canvas.configure(yscrollcommand=lambda first, last: self._scrolled(previous, first, last))
        self.canvas.bind("<Configure>", lambda _e: self.schedule(), add="+")

    # ------------------------------------------------------------------ parts

    def add(self, parent, build: Callable[[ctk.CTkFrame], None], height: int, **pack) -> ctk.CTkFrame:
        """An empty frame ``height`` pixels tall, packed in ``parent``; ``build(frame)`` fills it in later."""
        scale = ctk.ScalingTracker.get_widget_scaling(parent) or 1.0
        holder = ctk.CTkFrame(parent, fg_color="transparent", height=max(1, height / scale))
        holder.pack_propagate(False)
        holder.pack(**(pack or {"fill": "x"}))
        self._parts.append(_Part(holder, build))
        self.schedule()
        return holder

    @property
    def pending(self) -> int:
        return len(self._parts)

    def clear(self):
        """Forget the parts not built yet (their page is going away)."""
        self._parts = []
        if self._after is not None:
            try:
                self.canvas.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

    def build_all(self):
        """Build every part now (before searching or jumping into the page)."""
        while self._parts:
            self._fill(self._parts.pop(0))

    # ------------------------------------------------------------------ when to build

    def _scrolled(self, previous, first, last):
        if previous:
            try:
                self.canvas.tk.call(previous, first, last)
            except Exception:
                pass
        self.schedule()

    def schedule(self):
        if self._parts and self._after is None:
            try:
                self._after = self.canvas.after(15, self._run)
            except Exception:
                self._after = None

    def _run(self):
        self._after = None
        try:
            if not self.canvas.winfo_exists() or not self.canvas.winfo_ismapped():
                return
        except Exception:
            return
        try:
            self.scroll.update_idletasks()                # (parts added since the last pass have no place yet)
        except Exception:
            return
        view_top = self.canvas.winfo_rooty()
        view_height = max(1, self.canvas.winfo_height())
        low, high = view_top - view_height * AHEAD, view_top + view_height * (1 + AHEAD)
        deadline = time.perf_counter() + BUDGET
        shift = 0
        built_any = more = False
        for part in list(self._parts):
            if time.perf_counter() > deadline:
                more = True
                break
            try:
                if not part.holder.winfo_exists():
                    self._parts.remove(part)
                    continue
                y, h = part.holder.winfo_rooty(), part.holder.winfo_height()
            except Exception:
                self._parts.remove(part)
                continue
            if y + h < low:
                continue
            if y > high:
                break                                    # the parts are in page order: the rest are further down
            self._parts.remove(part)
            above = y < view_top
            self._fill(part)
            built_any = True
            if above:
                try:
                    part.holder.update_idletasks()
                    shift += part.holder.winfo_height() - h
                except Exception:
                    pass
        if shift:
            self._move_view(shift)
        if built_any or more:
            # more may be near the view now (a part came out shorter than its estimate), or the budget ran out
            self.schedule()

    def _fill(self, part: _Part):
        try:
            part.build(part.holder)
            part.holder.pack_propagate(True)
            part.holder.configure(height=1)
        except Exception as e:
            print(f"Could not build part of the page: {e}")

    def _move_view(self, pixels: int):
        """Scroll by ``pixels`` (positive: down), for a part above the view that grew."""
        try:
            self.scroll.update_idletasks()
            region = [float(v) for v in str(self.canvas.cget("scrollregion")).split()]
            total = region[3] - region[1] if len(region) == 4 else 0
            if total <= 0:
                return
            top = self.canvas.canvasy(0) - region[1]
            # (Tk rounds the view's place to the scroll step, up to 30 pixels here: not while moving it back)
            step = self.canvas.cget("yscrollincrement")
            self.canvas.configure(yscrollincrement=0)
            self.canvas.yview_moveto(max(0.0, (top + pixels) / total))
            self.canvas.configure(yscrollincrement=step)
        except Exception:
            pass
