"""
Fitting things to the width of the window.

``FlowBar`` - a row of controls that wraps onto further rows when the window is too narrow for it.

The filter bars of the collection pages are built the plain way: each control packed to the left, the action
buttons (Add, Edit, Delete) packed to the right. Packed like that, whatever doesn't fit is squeezed to nothing,
and it is the action buttons - packed last - that vanish first: on the Monsters page that already happened at
the window's default size.

``FlowBar(bar)`` takes such a bar once it is built and lays its controls out itself: the right-hand group stays
at the right of the first row, the others run from the left and carry on underneath when the row is full. A label
stays with the control it names. Controls that are shown and hidden later with ``pack`` / ``pack_forget`` (the
"Your fields" button) keep working: those two calls are taken over for the bar's controls.

``SidewaysBox`` - a holder for something with a least width (a table): it scrolls sideways when there is less room
than that, instead of losing its right-hand columns.
"""

from __future__ import annotations

import tkinter as tk
from typing import List, Optional

import customtkinter as ctk

ROW_GAP = 5          # pixels between rows (before scaling)
SIDE_GAP = 8         # the least room between the left-hand controls and the right-hand group


def _pads(value) -> tuple:
    """A pack ``padx`` as (before, after) in pixels."""
    parts = list(value) if isinstance(value, (tuple, list)) else str(value).split()
    try:
        nums = [int(float(str(p))) for p in parts]
    except (TypeError, ValueError):
        nums = [0]
    return (nums[0], nums[0]) if len(nums) == 1 else (nums[0], nums[1])


class _Item:
    __slots__ = ("widget", "side", "before", "after", "shown")

    def __init__(self, widget, side: str, pads: tuple, shown: bool):
        self.widget = widget
        self.side = side
        self.before, self.after = pads
        self.shown = shown


class FlowBar:
    """Lays out the controls of ``bar`` (already packed left and right) in rows that wrap."""

    def __init__(self, bar):
        self.bar = bar
        self.items: List[_Item] = []
        self._job: Optional[str] = None
        self._placed: dict = {}          # widget -> (x, y) last placed
        self._height: Optional[int] = None
        self._alive = True
        packed = bar.pack_slaves()
        for w in packed:
            info = w.pack_info()
            side = info.get("side", "top")
            if side not in ("left", "right"):
                side = "left"
            self._adopt(w, side, _pads(info.get("padx", 0)), True)
        made = bar.winfo_children()
        for n, w in enumerate(made):                         # made, but not showing yet: it goes where it was made,
            if w not in packed and w.winfo_manager() == "":  # after the controls that were made before it
                before = [i for i, item in enumerate(self.items) if item.widget in made[:n]]
                self._adopt(w, "left", (0, 0), False, at=before[-1] + 1 if before else 0)
        for item in self.items:                              # ours to place from now on
            if item.shown:
                tk.Pack.pack_forget(item.widget)
        try:
            bar.pack_propagate(False)
        except tk.TclError:
            pass
        tk.Misc.bind(bar, "<Configure>", self._changed, add="+")
        tk.Misc.bind(bar, "<Destroy>", self._destroyed, add="+")
        self.layout()

    # ---- the bar's controls

    def _adopt(self, widget, side: str, pads: tuple, shown: bool, at: Optional[int] = None):
        item = _Item(widget, side, pads, shown)
        self.items.insert(len(self.items) if at is None else at, item)

        def pack(*_args, **kw):                              # the page shows it (again)
            side = kw.get("side", item.side)
            item.side = side if side in ("left", "right") else "left"
            if "padx" in kw:
                scale = self._scale(widget)
                before, after = _pads(kw["padx"])
                item.before, item.after = int(round(before * scale)), int(round(after * scale))
            item.shown = True
            self.schedule()

        def pack_forget(*_args, **_kw):                      # the page hides it
            item.shown = False
            try:
                widget.place_forget()
            except tk.TclError:
                pass
            self._placed.pop(widget, None)
            self.schedule()

        widget.pack = pack
        widget.pack_forget = pack_forget
        tk.Misc.bind(widget, "<Configure>", self._changed, add="+")

    @staticmethod
    def _scale(widget) -> float:
        get = getattr(widget, "_get_widget_scaling", None)
        try:
            return float(get()) if get else 1.0
        except Exception:
            return 1.0

    # ---- laying out

    def _destroyed(self, event):
        if event.widget is self.bar:
            self._alive = False

    def _changed(self, _event=None):
        self.schedule()

    def schedule(self):
        if self._job is None and self._alive:
            try:
                self._job = self.bar.after_idle(self._run)
            except tk.TclError:
                self._job = None

    def _run(self):
        self._job = None
        if self._alive:
            try:
                self.layout()
            except tk.TclError:
                pass                                         # (the page was closed meanwhile)

    @staticmethod
    def _kind(widget) -> str:
        """How a control sits among its neighbours: a "caption" names the control after it ("Type:"), a "between"
        joins the controls on either side ("-" in a range), a "joins" belongs to the one before it (the summary
        after a button, a spacer, "Titles only" after the search box), anything else stands alone."""
        if getattr(widget, "flow_with_previous", False):
            return "joins"
        if isinstance(widget, ctk.CTkLabel):
            try:
                text = str(widget.cget("text")).strip()
            except (tk.TclError, ValueError):
                text = ""
            if text.endswith(":"):
                return "caption"
            return "between" if text in ("-", "\u2013", "to") else "joins"
        if isinstance(widget, ctk.CTkFrame) and not widget.pack_slaves() and not widget.grid_slaves():
            return "joins"                                   # an empty frame: a spacer
        return "control"

    def _units(self, items: List[_Item]) -> List[List[_Item]]:
        """The left-hand controls in groups that stay on one row together."""
        units: List[List[_Item]] = []
        pull = False                                         # the next control belongs with the one before it
        for item in items:
            kind = self._kind(item.widget)
            if units and (pull or kind in ("joins", "between")):
                units[-1].append(item)
            else:
                units.append([item])
            pull = kind in ("caption", "between")
        return units

    def layout(self):
        bar = self.bar
        shown = [i for i in self.items if i.shown]
        right = [i for i in shown if i.side == "right"]
        left = [i for i in shown if i.side == "left"]

        def w_of(item):
            return item.widget.winfo_reqwidth()

        def h_of(item):
            return item.widget.winfo_reqheight()

        def full(item):
            return item.before + w_of(item) + item.after

        right_width = sum(full(item) for item in right)
        width = bar.winfo_width()
        if width <= 1:                                       # not on screen yet: one row, as it was packed
            width = max(bar.winfo_reqwidth(), right_width + sum(full(item) for item in left))
        rows: List[List[tuple]] = [[]]                       # rows of (item, x)
        x = 0
        limit = width                                        # the first row shares its width with the right group
        if right:
            limit = max(0, width - right_width - int(round(SIDE_GAP * self._scale(bar))))
        for unit in self._units(left):
            unit_width = sum(full(i) for i in unit)
            last = unit[-1]                                  # the room after the last control doesn't need to fit
            trailing = full(last) if len(unit) > 1 and self._kind(last.widget) == "joins" and isinstance(
                last.widget, ctk.CTkFrame) else last.after
            if x + unit_width - trailing > limit and (rows[-1] or (right and len(rows) == 1)):
                rows.append([])                              # (an empty first row is left to the right-hand group)
                x, limit = 0, width
            for item in unit:
                rows[-1].append((item, x + item.before))
                x += item.before + w_of(item) + item.after

        gap = int(round(ROW_GAP * self._scale(bar)))
        heights = []
        for n, row in enumerate(rows):
            tallest = max([h_of(i) for i, _x in row] + ([h_of(i) for i in right] if n == 0 else []) + [0])
            heights.append(tallest)
        positions = {}
        y = 0
        for n, row in enumerate(rows):
            for item, item_x in row:
                positions[item.widget] = (item_x, y + (heights[n] - h_of(item)) // 2)
            if n == 0:
                rx = width
                for item in right:                           # the first one packed is the one furthest right
                    rx -= item.after + w_of(item)
                    positions[item.widget] = (max(0, rx), y + (heights[0] - h_of(item)) // 2)
                    rx -= item.before
            y += heights[n] + (gap if n < len(rows) - 1 else 0)
        total = max(1, y)

        for widget, (px, py) in positions.items():
            if self._placed.get(widget) != (px, py) or widget.winfo_manager() != "place":
                scale = self._scale(widget) if hasattr(widget, "_apply_argument_scaling") else 1.0
                widget.place(x=px / scale, y=py / scale)
                self._placed[widget] = (px, py)
        if total != self._height:
            self._height = total
            scale = self._scale(bar)
            bar.configure(height=max(1, int(round(total / scale))))


class SidewaysBox(ctk.CTkFrame):
    """Holds something that needs ``least_width`` (a table). With less room than that it scrolls sideways under a
    scrollbar; with more, the content is as wide as the box. Fill ``self.inner``."""

    INSET = 3

    def __init__(self, master, least_width: int, **kwargs):
        kwargs.setdefault("corner_radius", 8)
        super().__init__(master, **kwargs)
        self._least = least_width
        colour = self._apply_appearance_mode(self._fg_color)
        self._view = tk.Canvas(self, highlightthickness=0, bd=0, height=1, bg=colour)
        self._view.pack(fill="x", padx=self._apply_widget_scaling(self.INSET),
                        pady=self._apply_widget_scaling(self.INSET))
        self.inner = ctk.CTkFrame(self._view, fg_color=self._fg_color, corner_radius=0)
        self._window = self._view.create_window(0, 0, anchor="nw", window=self.inner)
        self._bar = ctk.CTkScrollbar(self, orientation="horizontal", command=self._view.xview, height=14)
        self._view.configure(xscrollcommand=self._bar.set)
        self._bar_shown = False
        self._size = None
        tk.Misc.bind(self.inner, "<Configure>", self._fit, add="+")
        self._view.bind("<Configure>", self._fit, add="+")

    def _fit(self, _event=None):
        have = self._view.winfo_width()
        least = int(round(self._least * self._get_widget_scaling()))
        width = max(have, least)
        height = max(1, self.inner.winfo_reqheight())
        if (width, height) != self._size:
            self._size = (width, height)
            self._view.itemconfigure(self._window, width=width)
            self._view.configure(height=height, scrollregion=(0, 0, width, height))
        needed = have > 1 and least > have
        if needed != self._bar_shown:
            self._bar_shown = needed
            if needed:
                self._bar.pack(fill="x", padx=self._apply_widget_scaling(self.INSET + 3),
                               pady=(0, self._apply_widget_scaling(self.INSET)))
            else:
                self._bar.pack_forget()
                self._view.xview_moveto(0)
