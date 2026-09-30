"""
A font-family drop-down that shows every family name *in its own typeface*.

Long lists (a typical Windows install has several hundred families) are drawn
virtually - only the rows in view exist - so opening the list is instant. The
popup belongs to the main window rather than to the widget that opened it:
CustomTkinter scrolls a page whenever the mouse wheel turns over any
descendant of that page's scroll area, and a popup parented to a control inside
the page counted as one.
"""

import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, List, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import installed_families
from typography import ui_font

ROW_H = 32
VISIBLE_ROWS = 9
PREVIEW_SIZE = 14
_MAX_CACHED_FONTS = 300


class FontPicker(ctk.CTkFrame):
    """Button-style picker: click to open a filterable list of font families.

    ``special`` is an optional first entry that is not a font (for example
    "(Base font)"), returned by :meth:`get` exactly as shown.
    """

    def __init__(self, parent, value: str = "", special: Optional[str] = None, width: int = 190,
                 height: int = 28, command: Optional[Callable[[str], None]] = None):
        super().__init__(parent, fg_color="transparent", width=width, height=height)
        self._special = special
        self._command = command
        self._value = value
        self._popup = None
        self._families: Optional[List[str]] = None
        self._preview_fonts = {}
        theme = get_theme_manager()

        self._button = ctk.CTkButton(
            self, text=value, anchor="w", width=width - 28, height=height, corner_radius=6,
            fg_color=theme.get_current_color("bg_input"), hover_color=theme.get_current_color("button_hover"),
            text_color=theme.get_current_color("text_primary"), border_width=1,
            border_color=theme.get_current_color("border"), command=self._toggle)
        self._button.pack(side="left")
        self._arrow = ctk.CTkButton(
            self, text="▾", width=28, height=height, corner_radius=6,
            fg_color=theme.get_current_color("bg_input"), hover_color=theme.get_current_color("button_hover"),
            text_color=theme.get_current_color("text_secondary"), border_width=1,
            border_color=theme.get_current_color("border"), command=self._toggle)
        self._arrow.pack(side="left", padx=(2, 0))
        self.pack_propagate(False)
        self._show_value()

    # -- value ------------------------------------------------------------------

    def get(self) -> str:
        return self._value

    def set(self, value: str):
        self._value = value
        self._show_value()

    def configure(self, **kwargs):
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs:
            super().configure(**kwargs)

    def _families_list(self) -> List[str]:
        if self._families is None:
            self._families = installed_families()
        return self._families

    def _preview_font(self, family: str, size: int = PREVIEW_SIZE):
        key = (family, size)
        font = self._preview_fonts.get(key)
        if font is None:
            if len(self._preview_fonts) > _MAX_CACHED_FONTS:
                self._preview_fonts.clear()
            font = tkfont.Font(family=family, size=size)
            self._preview_fonts[key] = font
        return font

    def _show_value(self):
        """The button shows the current name in that font."""
        is_font = bool(self._value) and self._value != self._special and not self._value.startswith("(")
        try:
            if is_font:
                self._button.configure(text=self._value, font=ctk.CTkFont(family=self._value, size=13))
            else:
                self._button.configure(text=self._value, font=ui_font("body"))
        except Exception:
            pass

    # -- popup ------------------------------------------------------------------

    def _toggle(self):
        if self._popup is not None:
            self._close()
        else:
            self._open()

    def _open(self):
        theme = get_theme_manager()
        self._all = ([self._special] if self._special else []) + self._families_list()
        self._items = list(self._all)
        self._hover = -1

        top = self.winfo_toplevel()
        popup = ctk.CTkToplevel(top)          # child of the window, not of this widget (see module docstring)
        popup.withdraw()
        popup.overrideredirect(True)
        try:
            popup.attributes("-topmost", True)
        except Exception:
            pass
        width = max(self.winfo_width(), 280)
        height = VISIBLE_ROWS * ROW_H + 50
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        # keep it on screen
        screen_h = self.winfo_screenheight()
        if y + height > screen_h - 40:
            y = max(10, self.winfo_rooty() - height - 2)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        outer = ctk.CTkFrame(popup, fg_color=theme.get_current_color("bg_secondary"), border_width=1,
                             border_color=theme.get_current_color("border"), corner_radius=0)
        outer.pack(fill="both", expand=True)

        self._filter_var = tk.StringVar()
        self._filter_entry = ctk.CTkEntry(outer, textvariable=self._filter_var, height=28,
                                          placeholder_text="Type to filter fonts…")
        self._filter_entry.pack(fill="x", padx=6, pady=(6, 4))

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=(6, 2), pady=(0, 6))
        self._bg = theme.get_current_color("bg_secondary")
        self._fg = theme.get_current_color("text_primary")
        self._hl = theme.get_current_color("accent_primary")
        self._hl_fg = theme.get_current_color("text_on_accent")
        self._canvas = tk.Canvas(body, highlightthickness=0, bd=0, bg=str(self._bg), yscrollincrement=ROW_H)
        self._scroll = ctk.CTkScrollbar(body, command=self._canvas.yview)
        self._scroll.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.configure(yscrollcommand=self._on_yview)

        # wheel / motion / click stay inside the popup
        for widget in (self._canvas, self._filter_entry):
            widget.bind("<MouseWheel>", self._on_wheel)
        self._canvas.bind("<Button-4>", lambda e: self._scroll_rows(-3) or "break")
        self._canvas.bind("<Button-5>", lambda e: self._scroll_rows(3) or "break")
        self._canvas.bind("<Motion>", self._on_motion)
        self._canvas.bind("<Leave>", lambda e: self._set_hover(-1))
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Configure>", lambda e: self._redraw())
        popup.bind("<Escape>", lambda e: self._close())
        self._filter_entry.bind("<Return>", lambda e: self._pick_index(0) if self._items else None)
        self._filter_var.trace_add("write", lambda *_a: self._on_filter())
        popup.bind("<FocusOut>", self._on_focus_out)

        self._popup = popup
        self._apply_scrollregion()
        # start with the current value in view
        try:
            idx = self._items.index(self._value)
            self._canvas.yview_moveto(max(0, idx - 3) / max(1, len(self._items)))
        except ValueError:
            pass
        popup.deiconify()
        popup.after(20, self._focus_filter)
        self._redraw()

    def _focus_filter(self):
        try:
            self._popup.lift()
            self._filter_entry.focus_set()
        except Exception:
            pass

    def _on_focus_out(self, event=None):
        self.after(150, self._close_if_unfocused)

    def _close_if_unfocused(self):
        if self._popup is None:
            return
        try:
            focused = self.focus_get()
        except Exception:
            focused = None
        w = focused
        while w is not None:
            if w == self._popup:
                return
            w = getattr(w, "master", None)
        self._close()

    def _close(self):
        popup, self._popup = self._popup, None
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    def destroy(self):
        self._close()
        super().destroy()

    # -- list drawing -----------------------------------------------------------

    def _apply_scrollregion(self):
        self._canvas.configure(scrollregion=(0, 0, 1, max(len(self._items), 1) * ROW_H))

    def _on_filter(self):
        needle = self._filter_var.get().strip().lower()
        self._items = [f for f in self._all if needle in f.lower()] if needle else list(self._all)
        self._apply_scrollregion()
        self._canvas.yview_moveto(0)
        self._hover = -1
        self._redraw()

    def _on_yview(self, lo, hi):
        self._scroll.set(lo, hi)
        self._redraw()

    def _first_row(self) -> int:
        return max(0, int(self._canvas.canvasy(0) // ROW_H))

    def _redraw(self):
        if self._popup is None:
            return
        canvas = self._canvas
        canvas.delete("row")
        width = max(canvas.winfo_width(), 100)
        first = self._first_row()
        rows = int(canvas.winfo_height() // ROW_H) + 2
        for i in range(first, min(len(self._items), first + rows)):
            name = self._items[i]
            y = i * ROW_H
            selected = i == self._hover
            if selected:
                canvas.create_rectangle(0, y, width, y + ROW_H, fill=self._hl, outline="", tags="row")
            is_font = name != self._special
            font = self._preview_font(name) if is_font else self._preview_font(installed_default(), 12)
            current = name == self._value
            text = ("✓ " if current else "   ") + name
            canvas.create_text(8, y + ROW_H // 2, text=text, anchor="w", font=font,
                               fill=self._hl_fg if selected else self._fg, tags="row")

    def _row_at(self, y: int) -> int:
        idx = int((self._canvas.canvasy(y)) // ROW_H)
        return idx if 0 <= idx < len(self._items) else -1

    def _set_hover(self, idx: int):
        if idx != self._hover:
            self._hover = idx
            self._redraw()

    def _on_motion(self, event):
        self._set_hover(self._row_at(event.y))

    def _on_click(self, event):
        idx = self._row_at(event.y)
        if idx >= 0:
            self._pick_index(idx)
        return "break"

    def _pick_index(self, idx: int):
        if not (0 <= idx < len(self._items)):
            return
        value = self._items[idx]
        self._close()
        self.set(value)
        if self._command:
            self._command(value)

    def _scroll_rows(self, rows: int):
        self._canvas.yview_scroll(rows, "units")

    def _on_wheel(self, event):
        step = -3 if event.delta > 0 else 3
        self._scroll_rows(step)
        return "break"          # nothing behind the popup may scroll


def installed_default() -> str:
    from typography import default_family
    return default_family()
