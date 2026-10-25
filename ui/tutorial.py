"""
The guided tour: a box of text that points at one part of the window at a time, with the rest of the
window dimmed around it.

How it is drawn (plain Tk, nothing extra to install):

* four borderless, semi-transparent windows dim the app around the highlighted widget, leaving a hole
  over it, so the widget stays visible and can still be clicked;
* four thin strips in the accent colour draw a frame round the hole;
* the text box is a ``PopupWindow`` (see ``ui/popup_window.py``) with Back / Next and Skip tour.

A step says where to go (``prepare``), what to point at (``target``) and what to tidy up when the tour
moves on (``leave``). The steps themselves are in ``ui/tutorial_steps.py``.

The tour checks a few times a second, like the other pop-ups: it follows the widget when the window is
moved, resized or scrolled, and hides itself while the app is minimised, in the background, or a dialog
of the app's own is open (so it never covers that dialog), then comes back.
"""

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.popup_window import PopupWindow, remove_binding

TICK_MS = 150
FIND_TRIES = 25          # how many times (100 ms apart) a step looks for its widget while the page builds
SHADE_ALPHA = 0.55
CALLOUT_WIDTH = 380

Rect = Tuple[int, int, int, int]   # x, y, width, height in screen pixels


@dataclass
class Step:
    section: str
    title: str
    text: str
    target: Optional[Callable[[], Optional[tk.Misc]]] = None   # the widget to highlight (None: no highlight)
    prepare: Optional[Callable[[], None]] = None               # go to the right page, open the right panel
    leave: Optional[Callable[[], None]] = None                 # undo what prepare opened
    wait_ms: int = 60                                          # time for the page to draw after prepare


# ---------------------------------------------------------------------------------------------- helpers

def find_named(root, name: str):
    """The first widget under ``root`` that a page named ``name`` (``ui.restyle.style_name``)."""
    todo = [root]
    while todo:
        widget = todo.pop(0)
        if getattr(widget, "_sb_name", None) == name:
            return widget
        try:
            todo.extend(widget.winfo_children())
        except tk.TclError:
            pass
    return None


def viewable(widget) -> bool:
    try:
        return bool(widget is not None and widget.winfo_exists() and widget.winfo_viewable())
    except Exception:
        return False


def scroll_into_view(widget, margin: int = 40):
    """Scroll every CTkScrollableFrame around ``widget`` so its top is on screen."""
    try:
        widget.update_idletasks()
    except tk.TclError:
        return
    w = getattr(widget, "master", None)
    while w is not None:
        canvas = getattr(w, "_parent_canvas", None)
        if isinstance(w, ctk.CTkScrollableFrame) and canvas is not None:
            try:
                total = max(1, w.winfo_height())
                top = widget.winfo_rooty() - w.winfo_rooty()
                shown_top = canvas.canvasy(0)
                shown_height = canvas.winfo_height()
                bottom = top + widget.winfo_height()
                if top < shown_top or bottom > shown_top + shown_height:
                    canvas.yview_moveto(max(0.0, (top - margin) / total))
                    widget.update_idletasks()
            except (tk.TclError, AttributeError):
                pass
        w = getattr(w, "master", None)


def _scaling(widget) -> float:
    try:
        return float(ctk.ScalingTracker.get_window_scaling(widget))
    except Exception:
        return 1.0


def callout_position(size: Tuple[int, int], hole: Optional[Rect], area: Rect, gap: int = 14) -> Tuple[int, int]:
    """Where the text box goes: below the hole, else above, right, left, and failing those over the
    bottom of the hole. With no hole it sits in the middle. Always inside ``area``."""
    cw, ch = size
    ax, ay, aw, ah = area

    def clamp(x, y):
        x = max(ax + 8, min(x, ax + aw - cw - 8))
        y = max(ay + 8, min(y, ay + ah - ch - 8))
        return int(x), int(y)

    if hole is None:
        return clamp(ax + (aw - cw) // 2, ay + (ah - ch) // 2)
    hx, hy, hw, hh = hole
    centre_x = hx + hw // 2 - cw // 2
    centre_y = hy + hh // 2 - ch // 2
    if hy + hh + gap + ch <= ay + ah:
        return clamp(centre_x, hy + hh + gap)
    if hy - gap - ch >= ay:
        return clamp(centre_x, hy - gap - ch)
    if hx + hw + gap + cw <= ax + aw:
        return clamp(hx + hw + gap, centre_y)
    if hx - gap - cw >= ax:
        return clamp(hx - gap - cw, centre_y)
    return clamp(hx + hw - cw - 24, hy + hh - ch - 24)


def shade_rects(hole: Optional[Rect], area: Rect) -> List[Rect]:
    """The four dimmed rectangles around ``hole`` (top, bottom, left, right); all of ``area`` with no hole."""
    ax, ay, aw, ah = area
    if hole is None:
        return [(ax, ay, aw, ah), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0)]
    hx, hy, hw, hh = hole
    return [
        (ax, ay, aw, hy - ay),
        (ax, hy + hh, aw, ay + ah - (hy + hh)),
        (ax, hy, hx - ax, hh),
        (hx + hw, hy, ax + aw - (hx + hw), hh),
    ]


def clip(rect: Rect, area: Rect) -> Optional[Rect]:
    x, y, w, h = rect
    ax, ay, aw, ah = area
    left, top = max(x, ax), max(y, ay)
    right, bottom = min(x + w, ax + aw), min(y + h, ay + ah)
    if right - left < 4 or bottom - top < 4:
        return None
    return left, top, right - left, bottom - top


# ---------------------------------------------------------------------------------------------- windows

class _Pane:
    """A plain borderless window used as one dimmed rectangle or one side of the frame."""

    def __init__(self, root, color: str, alpha: Optional[float]):
        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.configure(bg=color, highlightthickness=0, bd=0)
        for option, value in (("-topmost", True), ("-alpha", alpha)):
            if value is None:
                continue
            try:
                self.win.attributes(option, value)
            except tk.TclError:
                pass
        self.rect: Optional[Rect] = None

    def place(self, rect: Optional[Rect]) -> bool:
        """Show the pane over ``rect``. True when it was just put on screen (so it is now on top)."""
        if rect is None or rect[2] <= 0 or rect[3] <= 0:
            self.hide()
            return False
        mapped = False
        if rect != self.rect or not self.win.winfo_ismapped():
            x, y, w, h = rect
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            if not self.win.winfo_ismapped():
                self.win.deiconify()
                mapped = True
        self.rect = rect
        return mapped

    def hide(self):
        if self.rect is not None or self.win.winfo_ismapped():
            self.win.withdraw()
        self.rect = None

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class _Callout(PopupWindow):
    """The text box: where we are in the tour, the step's text, and the buttons."""

    def __init__(self, root, on_back, on_next, on_skip):
        super().__init__(root)
        theme = get_theme_manager()
        c = theme.get_current_color
        self.configure(fg_color=c("accent_primary"))
        box = ctk.CTkFrame(self, fg_color=c("bg_secondary"), corner_radius=10)
        box.pack(fill="both", expand=True, padx=2, pady=2)
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=14)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        self.section = ctk.CTkLabel(top, text="", font=ui_font("small", bold=True), text_color=c("accent_primary"))
        self.section.pack(side="left")
        self.count = ctk.CTkLabel(top, text="", font=ui_font("small"), text_color=theme.get_text_secondary())
        self.count.pack(side="right")

        self.title_label = ctk.CTkLabel(inner, text="", font=ui_font("heading", 17, bold=True),
                                        wraplength=CALLOUT_WIDTH - 32, justify="left", anchor="w")
        self.title_label.pack(fill="x", pady=(4, 6))
        self.body = ctk.CTkLabel(inner, text="", font=ui_font("body"), wraplength=CALLOUT_WIDTH - 32,
                                 justify="left", anchor="w")
        self.body.pack(fill="x")

        buttons = ctk.CTkFrame(inner, fg_color="transparent")
        buttons.pack(fill="x", pady=(14, 0))
        self.skip_button = ctk.CTkButton(buttons, text="Skip tour", width=80, height=30, fg_color="transparent",
                                         hover_color=c("button_hover"), text_color=theme.get_text_secondary(),
                                         command=on_skip)
        self.skip_button.pack(side="left")
        self.next_button = ctk.CTkButton(buttons, text="Next ▶", width=96, height=30, fg_color=c("accent_primary"),
                                         hover_color=c("accent_hover"), text_color=c("text_on_accent"),
                                         command=on_next)
        self.next_button.pack(side="right")
        self.back_button = ctk.CTkButton(buttons, text="◀ Back", width=80, height=30, fg_color=c("button_normal"),
                                         hover_color=c("button_hover"), text_color=c("text_primary"),
                                         command=on_back)
        self.back_button.pack(side="right", padx=(0, 6))

    def show_step(self, step: Step, index: int, total: int):
        self.section.configure(text=step.section.upper())
        self.count.configure(text=f"{index + 1} of {total}")
        self.title_label.configure(text=step.title)
        self.body.configure(text=step.text)
        self.back_button.configure(state="normal" if index > 0 else "disabled")
        self.next_button.configure(text="Finish ✓" if index == total - 1 else "Next ▶")

    def size(self) -> Tuple[int, int]:
        self.update_idletasks()
        return self.winfo_reqwidth(), self.winfo_reqheight()

    def move(self, x: int, y: int):
        # Position only (CTkToplevel.geometry would rescale it); Tk takes "+-10" for a negative position
        tk.Wm.wm_geometry(self, f"+{x}+{y}")


# ---------------------------------------------------------------------------------------------- the tour

class Tour:
    """Runs a list of steps. ``on_end(finished)`` is called once, when the tour is finished or skipped."""

    def __init__(self, root, steps: List[Step], on_end: Optional[Callable[[bool], None]] = None):
        self.root = root
        self.steps = steps
        self.on_end = on_end
        self.index = -1
        self.running = False
        self._target = None
        self._token = 0
        self._job = None
        self._find_job = None
        self._unfocused = 0
        self._hidden = False
        self._bindings = []
        self._shades: List[_Pane] = []
        self._ring: List[_Pane] = []
        self._callout: Optional[_Callout] = None

    # ---- life cycle

    def start(self, index: int = 0):
        if self.running or not self.steps:
            return
        self.running = True
        theme = get_theme_manager()
        self._shades = [_Pane(self.root, "#000000", SHADE_ALPHA) for _ in range(4)]
        self._ring = [_Pane(self.root, theme.get_current_color("accent_primary"), None) for _ in range(4)]
        self._callout = _Callout(self.root, self.back, self.next, self.skip)
        keys = (("<Escape>", self._key_skip), ("<Right>", self._key_next),
                ("<Return>", self._key_next), ("<Left>", self._key_back))
        for sequence, handler in keys:
            self._bindings.append((sequence, self.root.bind(sequence, handler, add="+")))
        # Showing the tour's own windows can give them the keyboard focus (Windows does when they appear),
        # so they take the keys too; they go with the tour, so there is nothing to unbind
        for window in [self._callout] + [pane.win for pane in self._shades + self._ring]:
            for sequence, handler in keys:
                window.bind(sequence, handler, add="+")
        self._go(index)
        self._job = self.root.after(TICK_MS, self._tick)

    def skip(self):
        self.end(finished=False)

    def end(self, finished: bool = False):
        if not self.running:
            return
        self.running = False
        self._token += 1
        for job in (self._job, self._find_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
        self._job = self._find_job = None
        self._leave_step()
        for sequence, funcid in self._bindings:
            remove_binding(self.root, sequence, funcid)
        self._bindings = []
        for pane in self._shades + self._ring:
            pane.destroy()
        self._shades, self._ring = [], []
        if self._callout is not None:
            try:
                self._callout.destroy()
            except tk.TclError:
                pass
            self._callout = None
        if self.on_end is not None:
            try:
                self.on_end(finished)
            except Exception as e:
                print(f"Tour clean-up failed: {e}")

    def next(self):
        if not self.running:
            return
        if self.index >= len(self.steps) - 1:
            self.end(finished=True)
        else:
            self._go(self.index + 1)

    def back(self):
        if self.running and self.index > 0:
            self._go(self.index - 1)

    def lift(self):
        """Bring the tour back to the front (Start tour pressed while it is already running)."""
        self._hidden = True
        self._place()

    # ---- keys (left alone while typing in a text box)

    @staticmethod
    def _typing(event) -> bool:
        widget = getattr(event, "widget", None)
        try:
            # (and the tabletop map, where Esc stops drawing a wall)
            return widget.winfo_class() in ("Entry", "TEntry", "Text", "Spinbox", "TCombobox", "Canvas")
        except Exception:
            return False

    def _key_skip(self, event):
        if self.running and not self._hidden and not self._typing(event):
            self.skip()

    def _key_next(self, event):
        if self.running and not self._hidden and not self._typing(event):
            self.next()

    def _key_back(self, event):
        if self.running and not self._hidden and not self._typing(event):
            self.back()

    # ---- steps

    def _leave_step(self):
        if 0 <= self.index < len(self.steps):
            leave = self.steps[self.index].leave
            if leave is not None:
                try:
                    leave()
                except Exception as e:
                    print(f"Tour step clean-up failed: {e}")

    def _go(self, index: int):
        self._leave_step()
        self._token += 1
        token = self._token
        self.index = index
        step = self.steps[index]
        self._target = None
        self._callout.show_step(step, index, len(self.steps))
        if step.prepare is not None:
            try:
                step.prepare()
            except Exception as e:
                print(f"Tour step '{step.title}' could not open its page: {e}")
        if self._find_job is not None:
            try:
                self.root.after_cancel(self._find_job)
            except (tk.TclError, ValueError):
                pass
        self._find_job = self.root.after(max(1, step.wait_ms), lambda: self._find(token, FIND_TRIES))

    def _find(self, token: int, tries: int):
        self._find_job = None
        if token != self._token or not self.running:
            return
        step = self.steps[self.index]
        widget = None
        if step.target is not None:
            try:
                widget = step.target()
            except Exception:
                widget = None
            if not viewable(widget) and tries > 0:
                self._find_job = self.root.after(100, lambda: self._find(token, tries - 1))
                return
            if viewable(widget):
                scroll_into_view(widget)
            else:
                widget = None
        self._target = widget
        self._place()

    # ---- drawing

    def _area(self) -> Rect:
        r = self.root
        return r.winfo_rootx(), r.winfo_rooty(), r.winfo_width(), r.winfo_height()

    def _hole(self, area: Rect) -> Optional[Rect]:
        widget = self._target
        if not viewable(widget):
            return None
        pad = int(6 * _scaling(self.root))
        rect = (widget.winfo_rootx() - pad, widget.winfo_rooty() - pad,
                widget.winfo_width() + 2 * pad, widget.winfo_height() + 2 * pad)
        return clip(rect, area)

    def _place(self):
        if not self.running or self._callout is None:
            return
        try:
            area = self._area()
            hole = self._hole(area)
        except tk.TclError:
            return
        restack = self._hidden
        for pane, rect in zip(self._shades, shade_rects(hole, area)):
            restack = pane.place(rect) or restack
        t = max(2, int(3 * _scaling(self.root)))
        if hole is None:
            for pane in self._ring:
                pane.hide()
        else:
            hx, hy, hw, hh = hole
            for pane, rect in zip(self._ring, ((hx - t, hy - t, hw + 2 * t, t), (hx - t, hy + hh, hw + 2 * t, t),
                                               (hx - t, hy, t, hh), (hx + hw, hy, t, hh))):
                restack = pane.place(rect) or restack
        x, y = callout_position(self._callout.size(), hole, area)
        self._callout.move(x, y)
        if not self._callout.winfo_ismapped():
            self._callout.deiconify()
            restack = True
        if restack:
            # a pane that was just shown went on top: keep the frame over the shade and the text over both
            for pane in self._ring:
                if pane.rect is not None:
                    pane.win.lift()
            self._callout.lift()
        self._hidden = False

    def _hide(self):
        if self._hidden:
            return
        self._hidden = True
        for pane in self._shades + self._ring:
            pane.hide()
        if self._callout is not None:
            self._callout.withdraw()

    def _own(self, toplevel) -> bool:
        if toplevel is self.root or toplevel is self._callout:
            return True
        return any(toplevel is pane.win for pane in self._shades + self._ring)

    def _app_active(self) -> bool:
        """Whether the tour should be on screen: the app is not minimised or in the background, and no
        other window of the app (a dialog) is in front."""
        try:
            if self.root.state() in ("iconic", "withdrawn"):
                return False
            focus = self.root.focus_get()
        except KeyError:                    # focus is on a Tk-internal widget: still ours
            return True
        except Exception:
            focus = None
        if focus is None:
            # Two ticks in a row, so a focus hand-over between windows doesn't count
            self._unfocused += 1
            return self._unfocused < 3
        self._unfocused = 0
        try:
            return self._own(focus.winfo_toplevel())
        except Exception:
            return True

    def _tick(self):
        self._job = None
        if not self.running:
            return
        try:
            if self._app_active():
                self._place()
            else:
                self._hide()
        except tk.TclError:
            pass
        if self.running:
            self._job = self.root.after(TICK_MS, self._tick)


# ---------------------------------------------------------------------------------------------- first start

class TourOffer(ctk.CTkToplevel):
    """The small window that offers the tour to a new user (once)."""

    def __init__(self, root, on_start: Callable[[], None]):
        super().__init__(root)
        self.on_start = on_start
        theme = get_theme_manager()
        c = theme.get_current_color
        self.title("Welcome to Spellbook")
        self.resizable(False, False)
        self.transient(root)

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=24, pady=20)
        ctk.CTkLabel(box, text="New to Spellbook?", font=ui_font("heading", 20, bold=True)).pack(anchor="w")
        ctk.CTkLabel(box, text="Take a short guided tour: it points out the collections, what the character "
                               "sheets do for you, and the Game Tools, one part at a time. You can skip it "
                               "at any time.\n\nYou can also start it later from Settings > Help, or with F1.",
                     font=ui_font("body"), wraplength=380, justify="left", anchor="w").pack(fill="x", pady=(8, 18))
        buttons = ctk.CTkFrame(box, fg_color="transparent")
        buttons.pack(fill="x")
        ctk.CTkButton(buttons, text="Start the tour", width=140, fg_color=c("accent_primary"),
                      hover_color=c("accent_hover"), text_color=c("text_on_accent"),
                      command=self._start).pack(side="right")
        ctk.CTkButton(buttons, text="Not now", width=100, fg_color=c("button_normal"),
                      hover_color=c("button_hover"), text_color=c("text_primary"),
                      command=self.destroy).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda _e: self.destroy())
        from ui.window_utils import center_on_parent
        center_on_parent(self, root, clamp=True)
        self.lift()
        self.focus_force()

    def _start(self):
        self.destroy()
        # after the window has gone, so the tour sees the main window in front
        self.master.after(50, self.on_start)
