"""
Level-by-level feature editing for the class and subclass editors.

Instead of adding features one at a time through pop-up dialogs, every level the editor cares about is a section that
is already there (a class has levels 1-20, a subclass has the levels its class gives subclass features at). A section
opens to show its features as cards - a title and a description, edited in place - with **+ Add feature** at the bottom
and **Details...** on each card for everything the card does not show (tables, roll effects, formatting tools).

Sections are built when they are first opened, so a class with a hundred features does not create a thousand widgets up
front; features in sections that were never opened are kept as they were.
"""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Sequence

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font


class _Card:
    """The widgets of one feature."""

    def __init__(self, feature, frame, title, text):
        self.feature = feature
        self.frame = frame
        self.title = title
        self.text = text


class _Section:
    def __init__(self, level: int, wrapper, header, body_holder, extra=None):
        self.level = level
        self.wrapper = wrapper
        self.header = header
        self.holder = body_holder           # frame the cards live in (None until the section is first opened)
        self.extra = extra
        self.cards: List[_Card] = []
        self.built = False
        self.open = False
        self.add_button = None


class FeatureSections(ctk.CTkScrollableFrame):
    """A collapsible section per level, each with editable feature cards."""

    def __init__(self, parent, *, levels: Sequence[int], features: Dict[int, list],
                 new_feature: Callable[[int], object], level_title: Callable[[int], str],
                 level_extra: Optional[Callable[[tk.Misc, int], Optional[tk.Misc]]] = None,
                 edit_details: Optional[Callable[[object], Optional[object]]] = None,
                 hidden: Callable[[object], bool] = lambda f: False,
                 blank_cards: bool = False, open_levels: Sequence[int] = (), hint: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.theme = get_theme_manager()
        self.new_feature = new_feature
        self.level_title = level_title
        self.level_extra = level_extra
        self.edit_details = edit_details
        self.hidden = hidden
        self.blank_cards = blank_cards
        self._model: Dict[int, list] = {lvl: [copy.copy(f) for f in features.get(lvl, [])] for lvl in levels}
        for lvl, feats in features.items():              # features at levels that are not in ``levels`` are kept too
            if lvl not in self._model:
                self._model[lvl] = [copy.copy(f) for f in feats]
        self._sections: Dict[int, _Section] = {}
        if hint:
            ctk.CTkLabel(self, text=hint, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                         anchor="w", justify="left", wraplength=620).pack(fill="x", padx=4, pady=(0, 8))
        self._holder = ctk.CTkFrame(self, fg_color="transparent")
        self._holder.pack(fill="x")
        for lvl in sorted(self._model):
            self._make_section(lvl)
        for lvl in open_levels:
            if lvl in self._sections:
                self.open_section(lvl)

    # ------------------------------------------------------------------ sections

    def levels(self) -> List[int]:
        return sorted(self._sections)

    def add_level(self, level: int, open_it: bool = True) -> None:
        """A section for a level that was not there (a feature at an unusual level)."""
        if level in self._sections:
            self.open_section(level)
            return
        self._model.setdefault(level, [])
        self._make_section(level)
        for lvl in self.levels():                          # keep the sections in level order
            self._sections[lvl].wrapper.pack_forget()
        for lvl in self.levels():
            self._sections[lvl].wrapper.pack(fill="x", pady=(0, 4))
        if open_it:
            self.open_section(level)

    def _make_section(self, level: int):
        c = self.theme.get_current_color
        wrapper = ctk.CTkFrame(self._holder, fg_color=c("bg_secondary"), corner_radius=8)
        wrapper.pack(fill="x", pady=(0, 4))
        head = ctk.CTkFrame(wrapper, fg_color="transparent")
        head.pack(fill="x")
        button = ctk.CTkButton(head, text="", anchor="w", height=34, fg_color="transparent",
                               hover_color=c("button_hover"), text_color=c("text_primary"),
                               font=ui_font("subheading", 13, bold=True),
                               command=lambda l=level: self.toggle(l))
        button.pack(side="left", fill="x", expand=True)
        extra = self.level_extra(head, level) if self.level_extra else None
        if extra is not None:
            extra.pack(side="right", padx=(0, 10))
        section = _Section(level, wrapper, button, None, extra)
        self._sections[level] = section
        self._refresh_header(section)

    def _count(self, section: _Section) -> int:
        if section.built:
            return sum(1 for card in section.cards if card.title.get().strip() or card.text.get("1.0", "end-1c").strip())
        return sum(1 for f in self._model.get(section.level, []) if not self.hidden(f))

    def _refresh_header(self, section: _Section):
        count = self._count(section)
        arrow = "▾" if section.open else "▸"
        noun = "feature" if count == 1 else "features"
        section.header.configure(text=f"{arrow}  {self.level_title(section.level)}   ·   {count} {noun}")

    def refresh_headers(self):
        for section in self._sections.values():
            self._refresh_header(section)

    def toggle(self, level: int):
        section = self._sections[level]
        if section.open:
            section.holder.pack_forget()
            section.open = False
        else:
            self.open_section(level)
            return
        self._refresh_header(section)

    def open_section(self, level: int):
        section = self._sections[level]
        if not section.built:
            self._build_body(section)
        if not section.open:
            section.holder.pack(fill="x", padx=8, pady=(0, 8))
            section.open = True
        self._refresh_header(section)

    def _build_body(self, section: _Section):
        c = self.theme.get_current_color
        section.holder = ctk.CTkFrame(section.wrapper, fg_color="transparent")
        section.built = True
        shown = [f for f in self._model.get(section.level, []) if not self.hidden(f)]
        for feature in shown:
            self._make_card(section, feature)
        if not shown and self.blank_cards:
            self._make_card(section, self.new_feature(section.level))
        section.add_button = ctk.CTkButton(section.holder, text="+ Add feature", width=120, height=28,
                                           fg_color=c("button_success"), hover_color=c("button_success_hover"),
                                           text_color=c("text_primary"),
                                           command=lambda l=section.level: self.add_feature(l))
        section.add_button.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------------ cards

    def _make_card(self, section: _Section, feature, focus: bool = False) -> _Card:
        c = self.theme.get_current_color
        frame = ctk.CTkFrame(section.holder, fg_color=c("bg_tertiary"), corner_radius=8)
        if section.add_button is not None:                      # new cards go above the "+ Add feature" button
            frame.pack(fill="x", pady=(0, 6), before=section.add_button)
        else:
            frame.pack(fill="x", pady=(0, 6))
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 2))
        title = ctk.CTkEntry(top, placeholder_text="Feature name (e.g. Extra Attack)")
        title.pack(side="left", fill="x", expand=True)
        title.insert(0, getattr(feature, "title", "") or "")
        card = _Card(feature, frame, title, None)
        ctk.CTkButton(top, text="✕", width=28, height=28, fg_color="transparent", hover_color=c("button_danger"),
                      text_color=c("text_primary"), command=lambda: self._remove_card(section, card)
                      ).pack(side="right", padx=(4, 0))
        if self.edit_details is not None:
            ctk.CTkButton(top, text="Details...", width=76, height=28, fg_color=c("button_normal"),
                          hover_color=c("button_hover"), text_color=c("text_primary"),
                          command=lambda: self._details(section, card)).pack(side="right", padx=(6, 0))
        text = ctk.CTkTextbox(frame, height=96, wrap="word", font=ui_font("body"))
        text.pack(fill="x", padx=8, pady=(0, 8))
        text.insert("1.0", getattr(feature, "description", "") or "")
        try:
            from ui.object_link_widgets import attach_object_linking
            attach_object_linking(text, self.theme, get_popup_parent=lambda: self.winfo_toplevel())
        except Exception:
            pass
        card.text = text
        for widget in (title, text):
            widget.bind("<FocusOut>", lambda _e: self._refresh_header(section), add="+")
        section.cards.append(card)
        if focus:
            title.focus_set()
        return card

    def add_feature(self, level: int):
        self.open_section(level)
        section = self._sections[level]
        self._make_card(section, self.new_feature(level), focus=True)
        self._refresh_header(section)

    def _remove_card(self, section: _Section, card: _Card):
        has_text = card.title.get().strip() or card.text.get("1.0", "end-1c").strip()
        if has_text and not messagebox.askyesno("Remove feature", "Remove this feature?",
                                                parent=self.winfo_toplevel()):
            return
        section.cards.remove(card)
        card.frame.destroy()
        self._refresh_header(section)

    def _details(self, section: _Section, card: _Card):
        """The full feature dialog (tables, roll effects, formatting tools) for one card."""
        feature = self._read_card(card)
        replaced = self.edit_details(feature)
        if replaced is None:
            return
        card.feature = replaced
        card.title.delete(0, "end")
        card.title.insert(0, getattr(replaced, "title", "") or "")
        card.text.delete("1.0", "end")
        card.text.insert("1.0", getattr(replaced, "description", "") or "")
        self._refresh_header(section)

    # ------------------------------------------------------------------ reading it back

    @staticmethod
    def _read_card(card: _Card):
        feature = copy.copy(card.feature)
        feature.title = card.title.get().strip()
        feature.description = card.text.get("1.0", "end-1c").strip()
        return feature

    def get_features(self, strict: bool = False) -> Dict[int, list]:
        """The features of every level, as the sections show them now. Strict: ValueError if one is incomplete."""
        out: Dict[int, list] = {}
        for level in sorted(self._sections):
            section = self._sections[level]
            if not section.built:
                out[level] = list(self._model.get(level, []))
                continue
            feats = []
            for card in section.cards:
                feature = self._read_card(card)
                if not feature.title and not feature.description:
                    continue                                          # an empty card is just an empty card
                if strict and not feature.title:
                    raise ValueError(f"Level {level}: a feature has a description but no name.")
                if strict and not feature.description:
                    raise ValueError(f"Level {level}: '{feature.title}' needs a description.")
                feats.append(feature)
            feats += [f for f in self._model.get(level, []) if self.hidden(f)]     # placeholders stay as they were
            out[level] = feats
        return out

    def set_features(self, features: Dict[int, list]):
        """Replace everything (used when the whole form is filled in from an existing object)."""
        for lvl in list(features):
            if lvl not in self._sections:
                self.add_level(lvl, open_it=False)
        for lvl, section in self._sections.items():
            self._model[lvl] = [copy.copy(f) for f in features.get(lvl, [])]
            if section.built:
                for card in list(section.cards):
                    card.frame.destroy()
                section.cards = []
                section.holder.destroy()
                section.holder, section.built, section.add_button = None, False, None
                was_open = section.open
                section.open = False
                if was_open:
                    self.open_section(lvl)
            self._refresh_header(section)
