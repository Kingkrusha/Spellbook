"""Text boxes that grow with the text size.

Entries, combo boxes and text boxes are made with a fixed size in pixels that fits the normal text size. With larger
text (Settings > Typography) the same size cuts the text off: the border runs through "30" in the sheet's Speed box
and a text box shows a line less than it was made for. Every such box remembers the size it was made with and is
grown by as much as its font is bigger than CustomTkinter's normal font at the size the call site asked for:

- entries and combo boxes get the extra line height on top of their height, and small entries (number boxes, up to
  ``SMALL_WIDTH``) also get wider by as much as the text is wider;
- text boxes get taller in proportion, so they keep showing the same number of lines.

Nothing gets smaller than it was made, and at the normal text size everything stays exactly as it was. Drop-down
widths are handled by ``ui/dropdown_width.py`` (combo boxes get both).

``restyle.install_creation_hook`` calls ``install()`` (which wraps ``configure``) and ``track()`` for every new box.
A change to the text settings makes new fonts, which the restyle pass gives each widget with ``configure(font=...)``:
that refits it.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import customtkinter as ctk

SMALL_WIDTH = 160                   # (wider entries already have room, and growing them could push a row apart)
MAX_LINE_RATIO = 3.0

_installed = False
_lines: Dict[str, Tuple[int, int]] = {}     # font name -> (its line height, the normal font's at the same size)


def _font_of(widget):
    try:
        return widget.cget("font")
    except Exception:
        return None


def line_heights(font) -> Tuple[int, int]:
    """(line height of ``font``, line height of CustomTkinter's normal font at the size the call site asked for).
    Both the same for a font that isn't one of the app's role fonts (nothing to grow for)."""
    spec = getattr(font, "spec", None)
    name = getattr(font, "name", None)
    if spec is None or name is None:
        return (1, 1)
    found = _lines.get(name)
    if found is None:
        try:
            from typography import default_family
            own = int(font.metrics("linespace"))
            description = (default_family(), -abs(int(spec[1])), "bold" if spec[2] else "normal")
            normal = int(font._tk.call("font", "metrics", description, "-linespace"))
            found = (max(own, normal), max(1, normal))
        except Exception:
            found = (1, 1)
        _lines[name] = found
    return found


def extra_height(font) -> int:
    own, normal = line_heights(font)
    return max(0, own - normal)


def line_ratio(font) -> float:
    own, normal = line_heights(font)
    return max(1.0, min(MAX_LINE_RATIO, own / normal))


def _kind(widget) -> str:
    if isinstance(widget, ctk.CTkTextbox):
        return "textbox"
    if isinstance(widget, ctk.CTkComboBox):
        return "combo"
    return "entry"


def wanted(widget, font=None) -> Tuple[Optional[int], Optional[int]]:
    """(width, height) for ``widget`` with ``font`` (its own when not given); None = leave that one alone."""
    font = font if font is not None else _font_of(widget)
    base_w = getattr(widget, "_fit_base_width", None)
    base_h = getattr(widget, "_fit_base_height", None)
    kind = _kind(widget)
    width = height = None
    if kind == "textbox":
        if base_h:                                       # (a hidden 0-high box stays hidden)
            height = int(round(base_h * line_ratio(font)))
    else:
        if base_h is not None:
            height = base_h + extra_height(font)
        if kind == "entry" and base_w is not None and base_w <= SMALL_WIDTH:
            from ui.dropdown_width import text_ratio
            width = int(round(base_w * text_ratio(font)))
    return width, height


_original_configure: Dict[type, object] = {}


def _base_class(widget) -> type:
    for cls in (ctk.CTkTextbox, ctk.CTkComboBox, ctk.CTkEntry):
        if isinstance(widget, cls):
            return cls
    return type(widget)


def fit(widget) -> None:
    """Give ``widget`` the size it was made with, grown for its font."""
    width, height = wanted(widget)
    changes = {}
    try:
        if width is not None and int(widget._desired_width) != width:
            changes["width"] = width
        if height is not None and int(widget._desired_height) != height:
            changes["height"] = height
    except Exception:
        return
    if changes:
        try:
            _original_configure[_base_class(widget)](widget, **changes)
        except Exception:
            pass


def track(widget, kwargs: dict) -> None:
    """Remember the size ``widget`` was made with (from its constructor's ``kwargs``) and fit it."""
    try:
        widget._fit_base_width = int(kwargs["width"]) if kwargs.get("width") is not None \
            else int(widget._desired_width)
        widget._fit_base_height = int(kwargs["height"]) if kwargs.get("height") is not None \
            else int(widget._desired_height)
    except Exception:
        return
    fit(widget)


def install() -> None:
    global _installed
    if _installed:
        return
    _installed = True
    for cls in (ctk.CTkEntry, ctk.CTkComboBox, ctk.CTkTextbox):
        original = cls.configure
        _original_configure[cls] = original

        def make(orig):
            def configure(self, require_redraw=False, **kwargs):
                tracked = getattr(self, "_fit_base_height", None) is not None
                if tracked and ("width" in kwargs or "height" in kwargs):
                    if kwargs.get("width") is not None:
                        self._fit_base_width = int(kwargs["width"])
                    if kwargs.get("height") is not None:
                        self._fit_base_height = int(kwargs["height"])
                    width, height = wanted(self, kwargs.get("font"))
                    if "width" in kwargs and width is not None:
                        kwargs["width"] = width
                    if "height" in kwargs and height is not None:
                        kwargs["height"] = height
                orig(self, require_redraw=require_redraw, **kwargs)
                if tracked and "font" in kwargs:
                    fit(self)
            return configure

        cls.configure = make(original)


def _pad(value) -> int:
    """Total of a pack padding (``3`` or ``(5, 0)``, as pack_info gives it)."""
    try:
        if isinstance(value, (tuple, list)):
            return sum(int(float(v)) for v in value) if len(value) > 1 else 2 * int(float(value[0]))
        text = str(value).split()
        return sum(int(float(v)) for v in text) if len(text) > 1 else 2 * int(float(text[0]))
    except Exception:
        return 0


def _needed(child) -> Tuple[int, int]:
    """The room a child needs: a label's own text (a CTkLabel asks for 28 pixels however small its text, room that
    a fixed card was made without)."""
    inner = getattr(child, "_text_label", None) if isinstance(child, ctk.CTkLabel) else None
    if inner is None and isinstance(child, ctk.CTkLabel):
        inner = getattr(child, "_label", None)
    if inner is not None:
        return inner.winfo_reqwidth(), inner.winfo_reqheight()
    return child.winfo_reqwidth(), child.winfo_reqheight()


def grow_with_content(frame, min_width: int, min_height: int):
    """A card with a fixed size (``pack_propagate(False)``) keeps ``min_width`` x ``min_height`` as its smallest size
    but grows to fit what is packed in it when its text gets bigger (a fixed card cut off its bottom line).

    Call it once the card's children are packed. It refits when a child changes size, after the rest of the change
    is done (one refit for the lot), so it costs nothing until the text size changes."""
    state = {"job": None}

    def refit():
        state["job"] = None
        try:
            if not frame.winfo_exists():
                return
            across = down = 0
            for child in frame.pack_slaves():
                info = child.pack_info()
                w, h = _needed(child)
                w += _pad(info.get("padx", 0)) + 2 * int(info.get("ipadx", 0) or 0)
                h += _pad(info.get("pady", 0)) + 2 * int(info.get("ipady", 0) or 0)
                if info.get("side") in ("left", "right"):
                    across += w
                    down = max(down, h)
                else:
                    across = max(across, w)
                    down += h
            scale = frame._get_widget_scaling() if hasattr(frame, "_get_widget_scaling") else 1.0
            width = max(min_width, int(round(across / scale)))
            height = max(min_height, int(round(down / scale)))
            if (width, height) != (int(frame.cget("width")), int(frame.cget("height"))):
                frame.configure(width=width, height=height)
        except Exception:
            pass

    def schedule(_event=None):
        if state["job"] is None:
            try:
                state["job"] = frame.after_idle(refit)
            except Exception:
                pass

    for child in frame.pack_slaves():
        child.bind("<Configure>", schedule, add="+")
    schedule()
    return schedule             # (to ask for a refit by hand)
