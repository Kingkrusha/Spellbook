"""
The "Auto-detected from text - please review" banner the content editors show when a draft was
filled in by the text importer (equipment, magic items, feats, lineages, spells).

Each editor used to carry its own copy of this code; they differed only in the note at the bottom,
the width the text wraps at, and which widgets get outlined, so those are the parameters.
"""

from typing import Callable, Dict, Iterable, Mapping, Optional

import customtkinter as ctk

from typography import ui_font


def add_review_banner(editor, scroll, review_fields: Iterable[str], field_labels: Mapping[str, str],
                      batch_progress: str, note: str, *, theme=None, padx: int = 20,
                      wraplength: int = 520) -> tuple:
    """Pack the banner into ``editor`` above ``scroll``; returns ``(banner, warning_colour)``."""
    theme = theme or editor.theme
    try:
        warn = theme.get_current_color('button_warning')
    except Exception:
        warn = "#d4a017"

    banner = ctk.CTkFrame(editor, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
    try:
        banner.pack(fill="x", padx=padx, pady=(12, 0), before=scroll)
    except Exception:
        banner.pack(fill="x", padx=padx, pady=(12, 0))

    heading = "Auto-detected from text - please review before saving"
    if batch_progress:
        heading = f"{heading}   ({batch_progress})"
    ctk.CTkLabel(banner, text="⚠  " + heading,
                 font=ui_font("subheading", 13, bold=True),
                 text_color=warn, anchor="w",
                 justify="left", wraplength=wraplength).pack(fill="x", padx=12, pady=(8, 2))

    review = [f for f in review_fields if f in field_labels]
    if review:
        names = ", ".join(sorted(field_labels[f] for f in review))
        msg = f"Fields to double-check (outlined below): {names}"
    else:
        msg = "All fields were detected with high confidence, but a quick check is still wise."
    ctk.CTkLabel(banner, text=msg, font=ui_font("small"),
                 text_color=theme.get_text_secondary(), anchor="w",
                 justify="left", wraplength=wraplength).pack(fill="x", padx=12, pady=(0, 2))

    ctk.CTkLabel(
        banner, text=note,
        font=ui_font("small"), text_color=theme.get_text_secondary(),
        anchor="w", justify="left", wraplength=wraplength,
    ).pack(fill="x", padx=12, pady=(0, 8))
    return banner, warn


def outline_fields(widgets: Mapping[str, Optional[object]], review_fields: Iterable[str], warn: str):
    """Outline the widget of each uncertain field (``widgets`` maps field name -> widget)."""
    for field_name in review_fields:
        w = widgets.get(field_name)
        if w is None:
            continue
        try:
            w.configure(border_color=warn, border_width=2)
        except Exception:
            pass

