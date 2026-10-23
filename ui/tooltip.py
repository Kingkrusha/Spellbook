"""
Lightweight hover tooltip for CustomTkinter widgets.

Attach one to any widget to show a small wrapped-text popup after the pointer
rests on it briefly. Used, for example, to reveal a property/keyword's full
description when hovering its chip in a detail view.
"""

import customtkinter as ctk

from typography import ui_font
from theme import get_theme_manager
from ui.popup_window import PopupWindow, pointer_over, watch_hover


class HoverTooltip:
    """Show `text` in a borderless popup while the pointer hovers `widget`."""

    def __init__(self, widget, text: str, delay_ms: int = 350, wraplength: int = 320):
        self.widget = widget
        self.text = text or ""
        self.delay_ms = delay_ms
        self.wraplength = wraplength
        self._after_id = None
        self._tip = None
        self._watch = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def update_text(self, text: str):
        self.text = text or ""
        if not self.text:
            self._hide()

    def _schedule(self, _event=None):
        self._cancel()
        if self.text:
            self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        self._after_id = None
        if self._tip is not None or not self.text:
            return
        try:
            if not self.widget.winfo_viewable():
                return
        except Exception:
            return
        if not pointer_over(self.widget):
            return                         # the pointer left without a <Leave> reaching us

        theme = get_theme_manager()
        # Use real theme keys (there is no 'card' colour in the palette - asking
        # for one returns the black/white fallback, which is what made the tip
        # render as a white box).
        fg = theme.get_current_color('bg_tertiary')
        border = theme.get_current_color('border')
        text_color = theme.get_current_color('text_primary')

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        self._tip = PopupWindow(self.widget, fg_color=fg)
        # Paint the bare Toplevel too, so no default-white edge shows through
        # behind the rounded frame.
        try:
            self._tip.configure(fg_color=fg)
            self._tip["background"] = fg
        except Exception:
            pass

        frame = ctk.CTkFrame(self._tip, fg_color=fg, border_color=border,
                             border_width=1, corner_radius=6)
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(
            frame, text=self.text, justify="left", wraplength=self.wraplength,
            font=ui_font("body"), text_color=text_color,
        ).pack(padx=10, pady=6)

        self._tip.geometry(f"+{x}+{y}")
        self._tip.deiconify()
        self._watch = watch_hover(self.widget, self._tip, self._hide)

    def _hide(self, _event=None):
        self._cancel()
        if self._watch is not None:
            self._watch.cancel()
            self._watch = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None
