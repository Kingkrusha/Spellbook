"""
A small colour picker used by the theme studio, the typography editor and the
character-sheet style inspector.

    ColorPickerDialog(parent, initial="#3b8ed0", on_change=fn, swatches=[...])

``on_change(hex)`` fires while the user drags (for live preview); ``result`` is
the chosen colour after the dialog closes, or ``None`` if cancelled (the caller
gets ``on_change(initial)`` back on cancel so a live preview can be undone).
"""

import colorsys
import re
import tkinter as tk
from typing import Callable, List, Optional, Sequence, Tuple

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")

# Colours picked earlier this session, newest first.
_recent: List[str] = []

SV_W, SV_H = 240, 160          # saturation/value square
HUE_H = 18


def normalize_hex(value: str) -> Optional[str]:
    """'#abc' / 'AABBCC' -> '#aabbcc'; None if it isn't a colour."""
    m = _HEX_RE.match((value or "").strip())
    if not m:
        return None
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h


def hex_to_hsv(value: str) -> Tuple[float, float, float]:
    h = normalize_hex(value) or "#000000"
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)


def hsv_to_hex(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def remember_color(value: str):
    value = normalize_hex(value)
    if not value:
        return
    if value in _recent:
        _recent.remove(value)
    _recent.insert(0, value)
    del _recent[12:]


class ColorSwatch(ctk.CTkButton):
    """A small button showing a colour; clicking it runs ``command``."""

    def __init__(self, parent, color: str = "#808080", command: Optional[Callable] = None,
                 width: int = 34, height: int = 24, **kwargs):
        theme = get_theme_manager()
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", theme.get_current_color("border"))
        kwargs.setdefault("corner_radius", 5)
        super().__init__(parent, text="", width=width, height=height,
                         fg_color=color, hover_color=color, command=command, **kwargs)
        self._swatch = color

    def set_color(self, color: str):
        self._swatch = color
        try:
            # plain strings on purpose: a swatch must show exactly this colour
            self.configure(fg_color=str(color), hover_color=str(color))
        except Exception:
            pass

    @property
    def color(self) -> str:
        return self._swatch


class ColorPickerDialog(ctk.CTkToplevel):
    """Modal colour picker."""

    def __init__(self, parent, initial: str = "#3b8ed0", title: str = "Choose a colour",
                 on_change: Optional[Callable[[str], None]] = None,
                 swatches: Optional[Sequence[Tuple[str, str]]] = None,
                 allow_clear: bool = False, clear_text: str = "Reset",
                 on_settle: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[str] = None
        self.cleared = False
        self._on_change = on_change          # every tweak: keep this cheap
        self._on_settle = on_settle          # once the colour stops changing: may be expensive
        self._settle_job = None
        self._settle_color: Optional[str] = None
        self._initial = normalize_hex(initial) or "#808080"
        self._swatches = list(swatches or [])
        self._h, self._s, self._v = hex_to_hsv(self._initial)
        self._sv_image: Optional[tk.PhotoImage] = None
        self._hue_image: Optional[tk.PhotoImage] = None
        self._sv_hue_drawn = -1.0
        self._dragging = None
        self._allow_clear = allow_clear
        self._clear_text = clear_text

        theme = get_theme_manager()
        self.configure(fg_color=theme.get_current_color("bg_primary"))
        self._build()
        self._refresh(update_hex=True, emit=False)

        self.transient(parent.winfo_toplevel())
        self.after(120, self._grab)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._ok())

    def _grab(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    # -- layout -----------------------------------------------------------------

    def _build(self):
        theme = get_theme_manager()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(padx=16, pady=14)

        self.sv_canvas = tk.Canvas(pad, width=SV_W, height=SV_H, highlightthickness=1,
                                   highlightbackground=theme.get_current_color("border"),
                                   bd=0, cursor="crosshair")
        self.sv_canvas.pack()
        self.sv_canvas.bind("<Button-1>", lambda e: self._start_drag("sv", e))
        self.sv_canvas.bind("<B1-Motion>", self._drag)
        self.sv_canvas.bind("<ButtonRelease-1>", self._end_drag)

        self.hue_canvas = tk.Canvas(pad, width=SV_W, height=HUE_H, highlightthickness=1,
                                    highlightbackground=theme.get_current_color("border"),
                                    bd=0, cursor="sb_h_double_arrow")
        self.hue_canvas.pack(pady=(10, 0))
        self.hue_canvas.bind("<Button-1>", lambda e: self._start_drag("hue", e))
        self.hue_canvas.bind("<B1-Motion>", self._drag)
        self.hue_canvas.bind("<ButtonRelease-1>", self._end_drag)
        self._build_hue_image()

        row = ctk.CTkFrame(pad, fg_color="transparent")
        row.pack(fill="x", pady=(12, 0))
        self.old_swatch = ColorSwatch(row, self._initial, command=self._reset_to_initial, width=44)
        self.old_swatch.pack(side="left")
        ctk.CTkLabel(row, text="→", font=ui_font("body")).pack(side="left", padx=6)
        self.new_swatch = ColorSwatch(row, self._initial, width=44)
        self.new_swatch.configure(state="disabled")
        self.new_swatch.pack(side="left")
        self.hex_var = tk.StringVar()
        self.hex_entry = ctk.CTkEntry(row, textvariable=self.hex_var, width=100,
                                      font=ui_font("body"), justify="center")
        self.hex_entry.pack(side="right")
        self.hex_entry.bind("<KeyRelease>", self._on_hex_typed)
        ctk.CTkLabel(row, text="Hex", font=ui_font("small"),
                     text_color=theme.get_current_color("text_secondary")).pack(side="right", padx=(0, 6))

        if self._swatches:
            self._swatch_row("Theme colours", self._swatches, pad)
        if _recent:
            self._swatch_row("Recent", [("Recent", c) for c in _recent], pad)

        buttons = ctk.CTkFrame(pad, fg_color="transparent")
        buttons.pack(fill="x", pady=(14, 0))
        ctk.CTkButton(buttons, text="OK", width=80, command=self._ok).pack(side="right")
        ctk.CTkButton(buttons, text="Cancel", width=80, command=self._cancel,
                      fg_color=theme.get_current_color("button_normal"),
                      hover_color=theme.get_current_color("button_hover"),
                      text_color=theme.get_current_color("text_primary")).pack(side="right", padx=(0, 8))
        if self._allow_clear:
            ctk.CTkButton(buttons, text=self._clear_text, width=80, command=self._clear,
                          fg_color=theme.get_current_color("button_danger"),
                          hover_color=theme.get_current_color("button_danger_hover"),
                          text_color="#ffffff").pack(side="left")

    def _swatch_row(self, title: str, colors: Sequence[Tuple[str, str]], parent):
        theme = get_theme_manager()
        ctk.CTkLabel(parent, text=title, font=ui_font("small"), anchor="w",
                     text_color=theme.get_current_color("text_secondary")).pack(fill="x", pady=(12, 3))
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x")
        per_row = 9
        seen = set()
        i = 0
        for label, color in colors:
            color = normalize_hex(color)
            if not color or color in seen:
                continue
            seen.add(color)
            sw = ColorSwatch(grid, color, command=lambda c=color: self._set_hex(c), width=22, height=22,
                             corner_radius=4)
            sw.grid(row=i // per_row, column=i % per_row, padx=2, pady=2)
            i += 1

    # -- pictures -----------------------------------------------------------------

    def _build_hue_image(self):
        img = tk.PhotoImage(width=SV_W, height=HUE_H)
        row = "{" + " ".join(hsv_to_hex(x / SV_W, 1, 1) for x in range(SV_W)) + "}"
        img.put(" ".join([row] * HUE_H))
        self._hue_image = img
        self.hue_canvas.create_image(0, 0, image=img, anchor="nw")
        self.hue_canvas.create_rectangle(0, 0, 4, HUE_H, outline="white", width=2, tags="hue_marker")

    def _draw_sv(self):
        """Saturation (x) / value (y) square for the current hue, drawn at half
        resolution and doubled (integer maths per pixel keeps hue drags smooth)."""
        if abs(self._sv_hue_drawn - self._h) < 0.002 and self._sv_image is not None:
            return
        self._sv_hue_drawn = self._h
        w, h = SV_W // 2, SV_H // 2
        r0, g0, b0 = (c * 255 for c in colorsys.hsv_to_rgb(self._h, 1, 1))
        columns = []
        for x in range(w):
            s = x / (w - 1)
            columns.append(((1 - s) * 255 + s * r0, (1 - s) * 255 + s * g0, (1 - s) * 255 + s * b0))
        rows = []
        for y in range(h):
            v = 1 - y / (h - 1)
            rows.append("{" + " ".join("#%02x%02x%02x" % (int(r * v), int(g * v), int(b * v))
                                       for r, g, b in columns) + "}")
        img = tk.PhotoImage(width=w, height=h)
        img.put(" ".join(rows))
        self._sv_image = img.zoom(2, 2)
        self.sv_canvas.delete("sv_image")
        self.sv_canvas.create_image(0, 0, image=self._sv_image, anchor="nw", tags="sv_image")
        self.sv_canvas.tag_lower("sv_image")

    # -- interaction --------------------------------------------------------------

    def _start_drag(self, which: str, event):
        self._dragging = which
        self._drag(event)

    def _end_drag(self, event=None):
        if self._dragging is not None:
            self._settle_now()
        self._dragging = None

    def _drag(self, event):
        if self._dragging == "sv":
            self._s = min(1.0, max(0.0, event.x / (SV_W - 1)))
            self._v = 1.0 - min(1.0, max(0.0, event.y / (SV_H - 1)))
        elif self._dragging == "hue":
            self._h = min(0.9999, max(0.0, event.x / (SV_W - 1)))
        else:
            return
        self._refresh(update_hex=True)

    def _on_hex_typed(self, event=None):
        value = normalize_hex(self.hex_var.get())
        if value:
            self._h, self._s, self._v = hex_to_hsv(value)
            self._refresh(update_hex=False)

    def _set_hex(self, value: str):
        self._h, self._s, self._v = hex_to_hsv(value)
        self._refresh(update_hex=True)

    def _reset_to_initial(self):
        self._set_hex(self._initial)

    def _current(self) -> str:
        return hsv_to_hex(self._h, self._s, self._v)

    def _refresh(self, update_hex: bool, emit: bool = True):
        self._draw_sv()
        x = self._s * (SV_W - 1)
        y = (1 - self._v) * (SV_H - 1)
        self.sv_canvas.delete("sv_marker")
        self.sv_canvas.create_oval(x - 6, y - 6, x + 6, y + 6, outline="white", width=2, tags="sv_marker")
        self.sv_canvas.create_oval(x - 7, y - 7, x + 7, y + 7, outline="black", width=1, tags="sv_marker")
        hx = self._h * (SV_W - 1)
        self.hue_canvas.coords("hue_marker", hx - 2, 0, hx + 2, HUE_H)
        color = self._current()
        self.new_swatch.set_color(color)
        if update_hex:
            self.hex_var.set(color)
        if emit:
            if self._on_change:
                try:
                    self._on_change(color)
                except Exception:
                    pass
            self._schedule_settle(color)

    def _schedule_settle(self, color: str):
        if not self._on_settle:
            return
        self._settle_color = color
        if self._settle_job is not None:
            try:
                self.after_cancel(self._settle_job)
            except Exception:
                pass
        # typing a hex value or clicking a swatch settles quickly; a drag settles on release
        self._settle_job = self.after(600 if self._dragging else 250, self._settle_now)

    def _settle_now(self):
        if self._settle_job is not None:
            try:
                self.after_cancel(self._settle_job)
            except Exception:
                pass
            self._settle_job = None
        color, self._settle_color = self._settle_color, None
        if color and self._on_settle:
            try:
                self._on_settle(color)
            except Exception:
                pass

    # -- finishing ----------------------------------------------------------------

    def _ok(self):
        self.result = self._current()
        self._settle_color = self.result
        self._settle_now()
        remember_color(self.result)
        self._close()

    def _cancel(self):
        self.result = None
        if self._settle_job is not None:
            try:
                self.after_cancel(self._settle_job)
            except Exception:
                pass
            self._settle_job = None
        for callback in (self._on_change, self._on_settle):
            if callback:
                try:
                    callback(self._initial)
                except Exception:
                    pass
        self._close()

    def _clear(self):
        self.cleared = True
        self.result = None
        self._close()

    def _close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


def ask_color(parent, initial: str, title: str = "Choose a colour",
              on_change: Optional[Callable[[str], None]] = None,
              swatches: Optional[Sequence[Tuple[str, str]]] = None,
              allow_clear: bool = False, clear_text: str = "Reset",
              on_settle: Optional[Callable[[str], None]] = None):
    """Open the picker modally. Returns ("ok", hex), ("clear", None) or ("cancel", None)."""
    dialog = ColorPickerDialog(parent, initial, title, on_change, swatches, allow_clear, clear_text, on_settle)
    parent.wait_window(dialog)
    if dialog.cleared:
        return "clear", None
    if dialog.result:
        return "ok", dialog.result
    return "cancel", None
