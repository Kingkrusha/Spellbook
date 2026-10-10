"""The Source line of a detail panel, as a version drop-down when the entry has several versions.

``VersionBar`` is a drop-in for the ``LabeledLabel`` the panels used for "Source: ...": with one
version it looks and behaves the same; with several (see content_versions.py) the source becomes a
drop-down button and picking an entry calls ``on_select(item)``.
"""

from typing import Callable, List, Optional

import customtkinter as ctk

from content_versions import version_label
from typography import ui_font
from ui.label_text import LabeledLabel
from ui.scrollable_combobox import ScrollableComboBox


def unique_labels(items: List) -> List[str]:
    """version_label for each item, made distinct (two printings can share a source)."""
    labels, seen = [], {}
    for item in items:
        text = version_label(item)
        seen[text] = seen.get(text, 0) + 1
        labels.append(text if seen[text] == 1 else f"{text} ({seen[text]})")
    return labels


class VersionBar(ctk.CTkFrame):
    """``captionless=True`` is for rows that already have their own "Source:" caption (the spell
    panel): the plain state is just the source text and the drop-down has no caption."""

    def __init__(self, parent, text: str = "", font=None, text_color=None, label: str = "Source",
                 on_select: Optional[Callable] = None, captionless: bool = False, wraplength: int = 0,
                 **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._font = font or ui_font("small")
        self._text_color = text_color
        self._caption = label
        self._captionless = captionless
        self.on_select = on_select
        self._versions: List = []
        self._labels: List[str] = []

        if captionless:
            self._plain = ctk.CTkLabel(self, text=text, font=self._font, anchor="w", wraplength=wraplength,
                                       **({"text_color": text_color} if text_color else {}))
            self._caption_label = None
        else:
            self._plain = LabeledLabel(self, text=text, font=self._font, text_color=text_color)
            self._caption_label = LabeledLabel(self, text=f"{label}:", font=self._font, text_color=text_color)
        self._plain.pack(anchor="w", fill="x" if captionless else None)
        self._var = ctk.StringVar()
        self._combo = ScrollableComboBox(
            self, values=[""], variable=self._var, state="readonly", height=24, width=380,
            font=self._font, dropdown_font=self._font, command=self._picked)

    # -- LabeledLabel-style API (the panels already call these) -------------------

    def configure(self, require_redraw=False, **kwargs):
        if "text" in kwargs:
            self._show_plain(kwargs.pop("text"))
        if "text_color" in kwargs:
            self._text_color = kwargs.pop("text_color")
            self._plain.configure(text_color=self._text_color)
            if self._caption_label is not None:
                self._caption_label.configure(text_color=self._text_color)
        if "wraplength" in kwargs and self._captionless:
            self._plain.configure(wraplength=kwargs.pop("wraplength"))
        kwargs.pop("wraplength", None)
        kwargs.pop("font", None)
        if kwargs:
            super().configure(require_redraw=require_redraw, **kwargs)

    def cget(self, attribute_name):
        if attribute_name == "wraplength":
            return self._plain.cget("wraplength") if self._captionless else 0
        return super().cget(attribute_name)

    # -- the two states ---------------------------------------------------------------

    def _show_plain(self, text: str):
        self._versions = []
        self._combo.pack_forget()
        if self._caption_label is not None:
            self._caption_label.pack_forget()
        self._plain.configure(text=text)
        self._plain.pack(anchor="w", fill="x" if self._captionless else None)

    def set_versions(self, versions: List, current, on_select: Optional[Callable] = None):
        """Show the drop-down for ``versions`` with ``current`` selected (one version = plain label)."""
        if on_select is not None:
            self.on_select = on_select
        if len(versions) < 2:
            if current is None:
                self._show_plain("")
            else:
                text = version_label(current)
                self._show_plain(text if self._captionless else f"{self._caption}: {text}")
            return
        self._versions = list(versions)
        self._labels = unique_labels(self._versions)
        index = next((i for i, v in enumerate(self._versions)
                      if v is current or getattr(v, "name", None) == getattr(current, "name", 0)), 0)
        self._plain.pack_forget()
        if self._caption_label is not None:
            self._caption_label.pack(side="left", padx=(0, 6))
        self._combo.configure(values=self._labels)
        self._var.set(self._labels[index])
        self._combo.pack(side="left")

    def has_versions(self) -> bool:
        return len(self._versions) > 1

    def current_label(self) -> str:
        return self._var.get()

    def _picked(self, label: str):
        if label in self._labels and self.on_select:
            self.on_select(self._versions[self._labels.index(label)])
