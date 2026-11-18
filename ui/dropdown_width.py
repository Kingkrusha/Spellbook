"""Drop-downs that grow with the text size.

A drop-down (CTkComboBox, CTkOptionMenu) is given a width that fits its choices at the normal text size. With
larger text (Settings > Typography) or a wider font, the same width cuts long choices off ("All Alignme...").
Every drop-down remembers the width it was made with and is widened by as much as its font's text is wider than
the normal font at the same nominal size. It never gets narrower than it was made, and the normal text size
looks exactly as before.

``restyle.install_creation_hook`` calls ``install()`` (which wraps ``configure``) and ``track()`` for every new
drop-down. A change to the text settings makes new fonts, which the restyle pass gives each widget with
``configure(font=...)``: that refits it.
"""

from __future__ import annotations

from typing import Dict, Optional

import customtkinter as ctk

SAMPLE = "All Alignments Abc 123"
MAX_GROWTH = 2.5                   # (a huge text size shouldn't make one drop-down fill the window)

_installed = False
_ratios: Dict[str, float] = {}      # font name -> how much wider its text is than the normal font's


def _font_of(widget):
    try:
        return widget.cget("font")
    except Exception:
        return None


def text_ratio(font) -> float:
    """How much wider ``font`` writes than CustomTkinter's normal font at the size the caller asked for
    (1.0 for a font that isn't one of the app's role fonts)."""
    spec = getattr(font, "spec", None)
    name = getattr(font, "name", None)
    if spec is None or name is None:
        return 1.0
    ratio = _ratios.get(name)
    if ratio is None:
        try:
            from typography import default_family
            normal = _normal_font(default_family(), int(spec[1]), bool(spec[2]))
            ratio = max(1.0, min(MAX_GROWTH, font.measure(SAMPLE) / max(1, normal.measure(SAMPLE))))
        except Exception:
            ratio = 1.0
        _ratios[name] = ratio
    return ratio


_normal_fonts: Dict[tuple, object] = {}


def _normal_font(family: str, size: int, bold: bool):
    """CustomTkinter's normal font at ``size`` (made like a CTkFont, so sizes compare like for like)."""
    key = (family, size, bold)
    font = _normal_fonts.get(key)
    if font is None:
        font = _normal_fonts[key] = ctk.CTkFont(family=family, size=size, weight="bold" if bold else "normal")
    return font


_original_configure: Dict[type, object] = {}


def _base_class(widget) -> type:
    return ctk.CTkComboBox if isinstance(widget, ctk.CTkComboBox) else ctk.CTkOptionMenu


def fit(widget) -> None:
    """Give ``widget`` the width it was made with, grown for its font."""
    base = getattr(widget, "_base_width", None)
    if base is None:
        return
    want = int(round(base * text_ratio(_font_of(widget))))
    try:
        if int(widget._desired_width) != want:
            _original_configure[_base_class(widget)](widget, width=want)
    except Exception:
        pass


def track(widget, width: Optional[int]) -> None:
    widget._base_width = int(width)
    fit(widget)


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    for cls in (ctk.CTkComboBox, ctk.CTkOptionMenu):
        original = cls.configure
        _original_configure[cls] = original

        def make(orig):
            def configure(self, require_redraw=False, **kwargs):
                width = kwargs.get("width")
                if width is not None and getattr(self, "_base_width", None) is not None:
                    self._base_width = int(width)
                    kwargs["width"] = int(round(int(width) * text_ratio(kwargs.get("font") or _font_of(self))))
                orig(self, require_redraw=require_redraw, **kwargs)
                if "font" in kwargs and getattr(self, "_base_width", None) is not None:
                    fit(self)
            return configure

        cls.configure = make(original)
