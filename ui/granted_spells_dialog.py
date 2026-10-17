"""
The spells a character's species, feats and features give them (see ``spell_grants``).

Fixed spells are listed with where they come from; this is also where the choices are made that decide which
spells arrive: the variant of a species trait (an Elf's lineage, a Tiefling's legacy) and the spells a feat or
species lets the character pick (Magic Initiate's cantrips). Choosing writes to the character and re-runs
``update_subclass_spells``, so the picks appear in the spell list like any other granted spell.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from spell_grants import build_report
from theme import get_theme_manager
from typography import ui_font


class GrantedSpellsDialog(ctk.CTkToplevel):
    def __init__(self, parent, character, spell_manager, on_change: Optional[Callable[[], None]] = None,
                 settings=None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.character = character
        self.spell_manager = spell_manager
        self.on_change = on_change
        self.settings = settings
        self.title(f"Granted spells: {character.name}")
        self.geometry("540x600")
        self.minsize(440, 420)
        self.transient(parent)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        c = self.theme.get_current_color
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=15, pady=15)
        ctk.CTkLabel(outer, text="Granted spells", font=ui_font("heading", 16, bold=True), anchor="w").pack(fill="x")
        ctk.CTkLabel(outer, text="Spells your species, feats and features give you. They are always prepared and "
                                 "do not count against the spells you can prepare.",
                     font=ui_font("small", 12), text_color=c("text_secondary"), anchor="w", justify="left",
                     wraplength=480).pack(fill="x", pady=(2, 8))
        self.body = ctk.CTkScrollableFrame(outer, fg_color=c("bg_secondary"))
        self.body.pack(fill="both", expand=True)
        bar = ctk.CTkFrame(outer, fg_color="transparent")
        bar.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(bar, text="Close", width=90, fg_color=c("accent_primary"), hover_color=c("accent_hover"),
                      text_color=c("text_on_accent"), command=self.destroy).pack(side="right")
        self.bind("<Escape>", lambda _e: self.destroy())
        self._render()

    # ------------------------------------------------------------------ showing it
    def _render(self):
        c = self.theme.get_current_color
        for child in self.body.winfo_children():
            child.destroy()
        report = build_report(self.character)
        sources = []
        for g in report.fixed:
            for src in g.source.split(", "):
                if src not in sources:
                    sources.append(src)
        for o in report.options:
            if o.source not in sources:
                sources.append(o.source)
        for p in report.picks:
            if p.source not in sources:
                sources.append(p.source)
        if not sources:
            ctk.CTkLabel(self.body, text="Nothing grants this character spells yet.",
                         text_color=self.theme.get_text_secondary()).pack(pady=30)
            return
        for source in sources:
            card = ctk.CTkFrame(self.body, fg_color=c("spell_row"), corner_radius=8)
            card.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(card, text=source, font=ui_font("subheading", 13, bold=True), anchor="w").pack(
                fill="x", padx=10, pady=(8, 2))
            for option in [o for o in report.options if o.source == source]:
                self._option_row(card, option)
            names = [g for g in report.fixed if source in g.source.split(", ")]
            if names:
                ctk.CTkLabel(card, text=", ".join(g.spell for g in names), font=ui_font("body", 12), anchor="w",
                             justify="left", wraplength=450).pack(fill="x", padx=10, pady=(0, 4))
            for pick in [p for p in report.picks if p.source == source]:
                self._pick_row(card, pick)
            ctk.CTkFrame(card, height=4, fg_color="transparent").pack()

    def _option_row(self, card, option):
        c = self.theme.get_current_color
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=option.label + ":", font=ui_font("small", 12), anchor="w").pack(side="left")
        menu = ctk.CTkOptionMenu(row, values=option.options, width=170, height=28,
                                 command=lambda v, k=option.key: self._set_option(k, v))
        menu.pack(side="left", padx=8)
        if option.selected:
            menu.set(option.selected)
        else:
            menu.set("Choose...")
            ctk.CTkLabel(row, text="Pick one to receive its spells", font=ui_font("small", 11),
                         text_color=c("text_warning")).pack(side="left")

    def _pick_row(self, card, pick):
        c = self.theme.get_current_color
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        done = len(pick.chosen) >= pick.count
        text = ", ".join(pick.chosen) if pick.chosen else "none chosen yet"
        ctk.CTkLabel(row, text=f"{pick.label}: {text}", font=ui_font("small", 12), anchor="w", justify="left",
                     wraplength=330, text_color=c("text_primary") if done else c("text_warning")
                     ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Change" if pick.chosen else "Choose", width=84, height=28,
                      fg_color=c("button_normal"), hover_color=c("button_hover"), text_color=c("text_primary"),
                      command=lambda p=pick: self._choose(p)).pack(side="right")

    # ------------------------------------------------------------------ acting on it
    def _refresh(self):
        from character import update_subclass_spells
        update_subclass_spells(self.character)
        if self.on_change:
            self.on_change()
        self._render()

    def _set_option(self, key: str, value: str):
        self.character.grant_options[key] = value
        self._refresh()

    def _choose(self, pick):
        from ui.add_spells_dialog import AddSpellsDialog
        dialog = AddSpellsDialog(self, self.character, self.spell_manager, settings=self.settings, pick=pick)
        self.wait_window(dialog)
        if dialog.result is not None:
            self.character.grant_choices[pick.key] = dialog.result
            self._refresh()
