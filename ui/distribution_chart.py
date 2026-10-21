"""A bar chart of a probability distribution (one canvas, so it costs one window handle).

Bars are the chance of each total (several totals share a bar when there are too many to draw),
or - in "at least" mode - the chance of rolling that total or more. A marker shows the average, and
an optional target colours the totals that reach it. Hovering a bar says what it is.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import List, Optional, Tuple

from dice_analyzer import Dist
from ui.chart_canvas import ChartCanvas
from typography import ui_font

PAD_L, PAD_R, PAD_T, PAD_B = 52, 16, 26, 34
MAX_BARS = 160


def nice_step(span: float, ticks: int) -> int:
    """A round step (1, 2, 5, 10 ...) so about ``ticks`` labels cover ``span``."""
    raw = max(1.0, span / max(1, ticks))
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return int(m * mag)
    return int(10 * mag)


def percent_text(p: float) -> str:
    pct = p * 100
    if pct >= 10:
        return f"{pct:.1f}%"
    if pct >= 0.1:
        return f"{pct:.2f}%"
    if pct > 0:
        return f"{pct:.3f}%" if pct >= 0.001 else "<0.001%"
    return "0%"


class DistributionChart(ChartCanvas):
    def __init__(self, parent, height: int = 300, **kw):
        super().__init__(parent, height=height, **kw)
        self.dist: Optional[Dist] = None
        self.cumulative = False              # False: chance of each total; True: chance of this total or more
        self.target: Optional[int] = None    # totals at or above it are drawn in the accent colour
        self.unit = ""
        self._bars: List[Tuple[int, int, float]] = []
        self._geom: Tuple[float, float, float, float, float] = (0, 0, 0, 0, 0)

    # ---- public
    def set_dist(self, dist: Optional[Dist], cumulative: Optional[bool] = None, target: Optional[int] = None,
                 unit: str = ""):
        self.dist = dist
        if cumulative is not None:
            self.cumulative = cumulative
        self.target = target
        self.unit = unit
        self._bars = dist.binned(MAX_BARS) if dist is not None else []
        self._hover = None
        self._schedule()

    # ---- plumbing
    # ---- drawing
    def _bar_value(self, i: int) -> float:
        lo, hi, p = self._bars[i]
        if not self.cumulative:
            return p
        return self.dist.at_least(lo)

    def _draw(self):
        self._job = None
        try:
            self.delete("all")
            w, h = self.winfo_width(), self.winfo_height()
        except tk.TclError:
            return
        if w < 80 or h < 80:
            return
        text2 = self._c("text_secondary")
        grid = self._c("bg_tertiary")
        if self.dist is None or not self._bars:
            self.create_text(w / 2, h / 2, text="Nothing to show yet", fill=text2, font=ui_font("body"))
            return

        small = ui_font("small", 11)
        x0, x1, y0, y1 = PAD_L, w - PAD_R, PAD_T, h - PAD_B
        n = len(self._bars)
        values = [self._bar_value(i) for i in range(n)]
        peak = max(values) or 1.0
        # a round top for the y axis
        top = peak * 1.08
        step = nice_step(top * 100, 4) / 100
        top = max(step, math.ceil(top / step) * step)
        slot = (x1 - x0) / n

        # grid + y labels
        y = 0.0
        while y <= top + 1e-12:
            py = y1 - (y / top) * (y1 - y0)
            self.create_line(x0, py, x1, py, fill=grid)
            self.create_text(x0 - 6, py, text=f"{y * 100:g}%", anchor="e", fill=text2, font=small)
            y += step

        accent, dim, hot = self._c("accent_primary"), self._c("button_normal"), self._c("accent_hover")
        for i, (lo, hi, _p) in enumerate(self._bars):
            bx0 = x0 + i * slot + (1 if slot > 4 else 0)
            bx1 = x0 + (i + 1) * slot - (1 if slot > 4 else 0)
            by = y1 - (values[i] / top) * (y1 - y0)
            color = accent if (self.target is None or hi >= self.target) else dim
            if i == self._hover:
                color = hot
            self.create_rectangle(bx0, by, max(bx1, bx0 + 1), y1, fill=color, outline="")
        self._geom = (x0, x1, y0, y1, top)

        # x labels
        lo_v, hi_v = self._bars[0][0], self._bars[-1][1]
        span = hi_v - lo_v + 1
        every = nice_step(span, max(3, int((x1 - x0) / 60)))
        v = lo_v + (-lo_v) % every
        while v <= hi_v:
            px = x0 + self._x_of(v + 0.5) * (x1 - x0)
            self.create_line(px, y1, px, y1 + 4, fill=text2)
            self.create_text(px, y1 + 6, text=str(v), anchor="n", fill=text2, font=small)
            v += every

        # the average
        mean = self.dist.mean()
        mx = x0 + self._x_of(mean + 0.5) * (x1 - x0)
        label = self._c("text_label")
        self.create_line(mx, y0 - 6, mx, y1, fill=label, dash=(4, 3), width=2)
        side, anchor = (mx + 5, "w") if mx < (x0 + x1) / 2 else (mx - 5, "e")
        self.create_text(side, y0 - 12, text=f"average {mean:.2f}", anchor=anchor, fill=label, font=ui_font("small", 11, bold=True))

        if self.target is not None and lo_v <= self.target <= hi_v + 1:
            tx = x0 + self._x_of(self.target) * (x1 - x0)
            self.create_line(tx, y0, tx, y1, fill=self._c("compare_better"), width=2)

        title = "chance of rolling this or higher" if self.cumulative else "chance of each total"
        self.create_text(x0 - 6, 8, text=title, anchor="w", fill=text2, font=small)
        if self._hover is not None:
            self._draw_tip(self._hover, values)

    def _x_of(self, value: float) -> float:
        """0..1 position of a total along the axis (the left edge of its bar)."""
        lo_v, hi_v = self._bars[0][0], self._bars[-1][1]
        span = hi_v - lo_v + 1
        return min(1.0, max(0.0, (value - lo_v) / span)) if span > 0 else 0.0

    def _draw_tip(self, i: int, values: List[float]):
        lo, hi, p = self._bars[i]
        x0, x1, y0, y1, top = self._geom
        slot = (x1 - x0) / len(self._bars)
        rng = str(lo) if lo == hi else f"{lo}-{hi}"
        lines = [f"{rng}: {percent_text(p)}"]
        if self.dist is not None:
            lines.append(f"{rng} or more: {percent_text(self.dist.at_least(lo))}")
            lines.append(f"{hi} or less: {percent_text(self.dist.at_most(hi))}")
        cx = x0 + (i + 0.5) * slot
        font = ui_font("small", 11)
        text_w = max(len(s) for s in lines) * 7 + 14
        tx = min(max(cx - text_w / 2, 4), (x1 + PAD_R) - text_w - 2)
        ty = y0 + 4
        self.create_rectangle(tx, ty, tx + text_w, ty + 16 * len(lines) + 8, fill=self._c("bg_primary"),
                              outline=self._c("text_secondary"))
        for k, line in enumerate(lines):
            self.create_text(tx + 7, ty + 6 + k * 16, text=line, anchor="nw", fill=self._c("text_primary"), font=font)

    # ---- hover
    def _on_motion(self, event):
        if not self._bars:
            return
        x0, x1 = self._geom[0], self._geom[1]
        if x1 <= x0 or not (x0 <= event.x <= x1):
            self._set_hover(None)
            return
        i = int((event.x - x0) / ((x1 - x0) / len(self._bars)))
        self._set_hover(min(max(i, 0), len(self._bars) - 1))

    def _set_hover(self, i: Optional[int]):
        if i != self._hover:
            self._hover = i
            self._schedule()
