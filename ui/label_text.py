"""
LabeledLabel: a drop-in for CTkLabel that shows the "Label:" part of a
"Label: value" line in the theme's field-label colour.

Detail panels build lines like ``"Cost: 5 gp   •   Weight: 2 lb"`` or
``"Source: Player's Handbook"`` as one string. This widget splits such a string
into its label/value segments (the label is whatever precedes the first colon of
a segment, when it is short and looks like a name) and draws each label in
``text_label``, so those lines match the coloured labels elsewhere on an object.
Text without a label is shown as plain value text.

It supports what those panels use of CTkLabel: ``configure(text=..., text_color=...,
font=...)``, ``pack``/``grid``/``pack_forget``, and the usual constructor options
(``font``, ``text_color``, ``anchor``, ``justify``, ``wraplength``).
"""

import re
from typing import List, Optional, Tuple

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font

SEPARATOR = "•"
_LABEL_RE = re.compile(r"^\s*([^:\n]{1,32}?):(?:\s+|$)(.*)$", re.S)


def split_segments(text: str) -> List[Tuple[str, str]]:
    """[(label, value), ...] for ``text``; label is "" for text that has none."""
    if not text:
        return []
    parts = re.split(r"\s+" + SEPARATOR + r"\s+", text) if SEPARATOR in text else [text]
    segments: List[Tuple[str, str]] = []
    for part in parts:
        m = _LABEL_RE.match(part)
        if m and not any(ch in m.group(1) for ch in "[]()<>{}/") and len(m.group(1).split()) <= 4:
            segments.append((m.group(1) + ":", m.group(2)))
        else:
            segments.append(("", part))
    return segments


def _bold(font):
    """The bold version of a role font (labels are set in bold, like the coloured labels elsewhere)."""
    spec = getattr(font, "spec", None)
    if spec:
        role, size, _bold_flag, italic, underline = spec
        return ui_font(role, size, bold=True, italic=italic, underline=underline)
    return font


class LabeledLabel(ctk.CTkFrame):
    def __init__(self, parent, text: str = "", font=None, text_color=None, label_font=None,
                 anchor: str = "w", justify: str = "left", wraplength: int = 0, **kwargs):
        super().__init__(parent, fg_color=kwargs.pop("fg_color", "transparent"), **{
            k: v for k, v in kwargs.items() if k in ("width", "height", "corner_radius", "bg_color")})
        self._text = ""
        self._font = font or ui_font("body")
        self._label_font = label_font          # default: the value font, bold
        self._text_color = text_color
        self._anchor = anchor
        self._justify = justify
        self._wraplength = wraplength
        self._rebuild(text)

    # -- CTkLabel-style API ---------------------------------------------------------

    def configure(self, require_redraw=False, **kwargs):
        rebuild = False
        if "text" in kwargs:
            self._text = kwargs.pop("text") or ""
            rebuild = True
        if "font" in kwargs:
            self._font = kwargs.pop("font")
            rebuild = True
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            rebuild = True
        for key, attr in (("anchor", "_anchor"), ("justify", "_justify"), ("wraplength", "_wraplength")):
            if key in kwargs:
                setattr(self, attr, kwargs.pop(key))
                rebuild = True
        if kwargs:
            super().configure(require_redraw=require_redraw, **kwargs)
        if rebuild:
            self._rebuild(self._text)

    def cget(self, attribute_name: str):
        if attribute_name == "text":
            return self._text
        if attribute_name == "font":
            return self._font
        if attribute_name == "text_color":
            return self._text_color
        return super().cget(attribute_name)

    # -- drawing --------------------------------------------------------------------

    def _rebuild(self, text: str):
        self._text = text or ""
        for child in self.winfo_children():
            child.destroy()
        theme = get_theme_manager()
        label_color = theme.get_current_color("text_label")
        value_kwargs = {"font": self._font, "anchor": "w", "justify": self._justify}
        if self._text_color is not None:
            value_kwargs["text_color"] = self._text_color
        segments = split_segments(self._text)
        for i, (label, value) in enumerate(segments):
            if i > 0:
                ctk.CTkLabel(self, text=f" {SEPARATOR} ", font=self._font, text_color=self._text_color
                             or theme.get_current_color("text_secondary")).pack(side="left")
            if label:
                ctk.CTkLabel(self, text=label + (" " if value else ""), font=self._label_font or _bold(self._font),
                             text_color=label_color, anchor="w").pack(side="left", anchor="n")
            if value:
                kw = dict(value_kwargs)
                if self._wraplength:
                    kw["wraplength"] = self._wraplength
                ctk.CTkLabel(self, text=value, **kw).pack(side="left", anchor="n", fill="x", expand=True)
