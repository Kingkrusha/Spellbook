"""
A small "please wait" card shown over the main window while a slow visual change
(theme, fonts, light/dark) is applied.

Tk cannot repaint while Python is busy, so the card is drawn *before* the work
starts. To avoid flashing it for changes that finish instantly, it is shown only
when the last change of the same kind took a noticeable time (and always the
first time, when nothing is known yet).
"""

import time
import tkinter
from typing import Callable, Dict, Optional, TypeVar

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font

T = TypeVar("T")

SHOW_ABOVE_SECONDS = 0.25
_last_duration: Dict[str, float] = {}
_card: Optional[ctk.CTkFrame] = None


def _main_window():
    return getattr(tkinter, "_default_root", None)


def show(text: str = "Applying changes…"):
    """Put the card on screen and paint it right away."""
    global _card
    root = _main_window()
    if root is None:
        return
    hide()
    theme = get_theme_manager()
    try:
        card = ctk.CTkFrame(root, corner_radius=0, border_width=2,
                            fg_color=theme.get_current_color("bg_secondary"),
                            border_color=theme.get_current_color("accent_primary"))
        ctk.CTkLabel(card, text=text, font=ui_font("heading", bold=True)).pack(padx=34, pady=(22, 4))
        ctk.CTkLabel(card, text="This only takes a moment.", font=ui_font("small"),
                     text_color=theme.get_current_color("text_secondary")).pack(padx=34, pady=(0, 10))
        ctk.CTkFrame(card, height=14, fg_color="transparent").pack()
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.lift()
        _card = card
        root.update_idletasks()      # paint it before the blocking work starts
    except Exception:
        _card = None


def hide():
    global _card
    card, _card = _card, None
    if card is not None:
        try:
            card.destroy()
        except Exception:
            pass


def run_busy(kind: str, text: str, work: Callable[[], T], force: bool = False) -> T:
    """Run ``work`` with the card up if this kind of change has been slow."""
    show_card = force or _last_duration.get(kind, 1.0) > SHOW_ABOVE_SECONDS
    if show_card:
        show(text)
    started = time.time()
    try:
        return work()
    finally:
        _last_duration[kind] = time.time() - started
        if show_card:
            hide()
