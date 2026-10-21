"""A horizontal bar chart with one clickable row per roll (one canvas, so one window handle).

Used for the Dice Analyzer's character overview: every saving throw and skill as a bar of its average
(or median) result. Rows are grouped under headings; hovering a row shows its range, clicking opens it.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from typography import ui_font
from ui.chart_canvas import ChartCanvas
from ui.distribution_chart import nice_step

ROW_H = 26
HEAD_H = 34
LABEL_W = 190
PAD_R = 150
PAD_T = 8


@dataclass
class BarRow:
    key: str
    label: str
    value: float
    tag: str = ""            # shown after the label, e.g. "●" proficient or "◆" expertise
    hint: str = ""           # shown on hover, e.g. "median 14 • range 3 to 23"


class BarListChart(ChartCanvas):
    def __init__(self, parent, on_click: Optional[Callable[[str], None]] = None, **kw):
        super().__init__(parent, **kw)
        self.on_click = on_click
        self.sections: List[Tuple[str, List[BarRow]]] = []
        self.unit = "average"
        self._hover: Optional[str] = None
        self._hit: List[Tuple[float, float, str]] = []         # (top, bottom, key)
        self.bind("<Button-1>", self._on_press)

    # ---- public
    def set_rows(self, sections: List[Tuple[str, List[BarRow]]], unit: str = "average"):
        self.sections = sections
        self.unit = unit
        rows = sum(len(r) for _, r in sections)
        self.configure(height=PAD_T + len(sections) * HEAD_H + rows * ROW_H + 30)
        self._schedule()

    # ---- plumbing
    # ---- drawing
    def _draw(self):
        self._job = None
        try:
            self.delete("all")
            w = self.winfo_width()
        except tk.TclError:
            return
        self._hit = []
        if w < 200:
            return
        values = [r.value for _, rows in self.sections for r in rows]
        if not values:
            self.create_text(w / 2, 40, text="Nothing to show", fill=self._c("text_secondary"), font=ui_font("body"))
            return
        text1, text2 = self._c("text_primary"), self._c("text_secondary")
        grid, accent, hot = self._c("bg_tertiary"), self._c("accent_primary"), self._c("accent_hover")
        label_color = self._c("text_label")
        top_v = max(max(values), 1.0) * 1.05
        step = nice_step(top_v, 6)
        top_v = max(step, -(-top_v // step) * step)
        x0, x1 = LABEL_W, w - PAD_R
        total_h = PAD_T + len(self.sections) * HEAD_H + sum(len(r) for _, r in self.sections) * ROW_H
        small = ui_font("small", 11)

        v = 0
        while v <= top_v:
            gx = x0 + v / top_v * (x1 - x0)
            self.create_line(gx, PAD_T, gx, total_h, fill=grid)
            v += step
        y = PAD_T
        for title, rows in self.sections:
            self.create_text(10, y + HEAD_H - 8, text=title, anchor="sw", fill=label_color,
                             font=ui_font("subheading", 14, bold=True))
            y += HEAD_H
            for row in rows:
                hovered = row.key == self._hover
                if hovered:
                    self.create_rectangle(0, y, w, y + ROW_H, fill=self._c("bg_tertiary"), outline="")
                self.create_text(10, y + ROW_H / 2, text=row.label, anchor="w", fill=text1, font=ui_font("body", 12))
                if row.tag:
                    self.create_text(LABEL_W - 8, y + ROW_H / 2, text=row.tag, anchor="e", fill=label_color,
                                     font=ui_font("body", 13, bold=True))
                bar_w = max(1.0, max(0.0, row.value) / top_v * (x1 - x0))
                self.create_rectangle(x0, y + 4, x0 + bar_w, y + ROW_H - 4, fill=hot if hovered else accent, outline="")
                self.create_text(x0 + bar_w + 6, y + ROW_H / 2, text=f"{row.value:.1f}".rstrip("0").rstrip("."),
                                 anchor="w", fill=text1, font=ui_font("body", 12, bold=True))
                if hovered and row.hint:
                    self.create_text(w - 8, y + ROW_H / 2, text=row.hint, anchor="e", fill=text2, font=small)
                self._hit.append((y, y + ROW_H, row.key))
                y += ROW_H
        self.create_text(x0, total_h + 8, text=f"bars show the {self.unit} result (click a row for the full graph)",
                         anchor="nw", fill=text2, font=small)

    # ---- mouse
    def _row_at(self, y: float) -> Optional[str]:
        for top, bottom, key in self._hit:
            if top <= y < bottom:
                return key
        return None

    def _on_motion(self, event):
        key = self._row_at(event.y)
        self.configure(cursor="hand2" if key else "")
        self._set_hover(key)

    def _set_hover(self, key: Optional[str]):
        if key != self._hover:
            self._hover = key
            self._schedule()

    def _on_press(self, event):
        key = self._row_at(event.y)
        if key and self.on_click:
            self.on_click(key)
