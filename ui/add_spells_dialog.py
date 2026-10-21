"""
Search-and-add dialog for a character's spells.

Opened from the Spells section of a character sheet (and the Spell Lists page): type to search the spell
collection, filter by level, and add spells to the character without leaving the page. A switch limits the list
to what the character can actually learn - spells on their class's list, up to the highest level they can cast,
including the extra spells a Warlock patron or a feature adds to the list (see ``spell_access``).

The same dialog also picks the spells a feat or species lets a character choose (Magic Initiate's cantrips):
pass a ``spell_grants.Pick`` and it shows only the spells that pick allows and returns the chosen names.
"""

from __future__ import annotations

import tkinter as tk
from ui.window_utils import center_on_parent
from typing import Callable, List, Optional

import customtkinter as ctk

from spell_access import learn_rules
from theme import get_theme_manager
from typography import ui_font

DEBOUNCE_MS = 150
MAX_ROWS = 50                          # widgets per row are costly: searching narrows the list instead of paging
LEVELS = ["All levels", "Cantrips"] + [f"Level {n}" for n in range(1, 10)]

# the switch's last position, so a second visit opens the way the first one was left
_remembered = {"only_learnable": True}


def level_from_label(label: str) -> Optional[int]:
    if label == "Cantrips":
        return 0
    if label.startswith("Level "):
        return int(label.split()[1])
    return None


class AddSpellsDialog(ctk.CTkToplevel):
    """``add_fn(spell) -> bool`` adds a spell to the character (the caller saves and refreshes)."""

    def __init__(self, parent, character, spell_manager, add_fn: Optional[Callable[[object], bool]] = None,
                 settings=None, pick=None, title: Optional[str] = None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.character = character
        self.spell_manager = spell_manager
        self.add_fn = add_fn
        self.settings = settings
        self.pick = pick
        self.result: Optional[List[str]] = None
        self.added: List[str] = []
        self._chosen: List[str] = list(pick.chosen) if pick else []
        self._job: Optional[str] = None
        self._rules = learn_rules(character) if pick is None else None
        legacy = getattr(settings, "legacy_content_filter", "show_all") if settings is not None else "show_all"
        if legacy == "show_all" and not any(
                cl.get_class_name().lower().endswith("(legacy)") for cl in character.classes) and pick is None:
            legacy = "show_unupdated"             # a 2024 character is not offered every spell twice
        self._all = sorted(spell_manager.get_filtered_spells(legacy_filter=legacy),
                           key=lambda s: (s.level, s.name.lower()))

        if title is None:
            title = f"Choose spells: {pick.source}" if pick else f"Add spells to {character.name}"
        self.title(title)
        self.geometry("560x680")
        self.minsize(460, 520)
        self.resizable(True, True)
        self.transient(parent)
        try:
            self.grab_set()
        except tk.TclError:                                       # not viewable yet (headless/testing)
            pass
        self._build(title)
        try:
            center_on_parent(self, parent, clamp=True)
        except tk.TclError:
            pass
        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._refresh()

    # ------------------------------------------------------------------ layout
    def _build(self, title: str):
        c = self.theme.get_current_color
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=15, pady=15)
        ctk.CTkLabel(outer, text=title, font=ui_font("heading", 16, bold=True), anchor="w").pack(fill="x")
        self.summary = ctk.CTkLabel(outer, text="", font=ui_font("small", 12), text_color=c("text_secondary"),
                                    anchor="w", justify="left", wraplength=500)
        self.summary.pack(fill="x", pady=(2, 8))

        controls = ctk.CTkFrame(outer, fg_color="transparent")
        controls.pack(fill="x")
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_a: self._schedule())
        self.search = ctk.CTkEntry(controls, textvariable=self.query, height=32, placeholder_text="Search spells...")
        self.search.pack(side="left", fill="x", expand=True)
        self.level_menu = ctk.CTkOptionMenu(controls, values=LEVELS, width=120, height=32, command=lambda _v: self._refresh())
        self.level_menu.pack(side="left", padx=(8, 0))
        self.level_menu.set(LEVELS[0])
        self.search.focus_set()

        if self.pick is None:
            self.only_var = tk.BooleanVar(value=_remembered["only_learnable"])
            ctk.CTkSwitch(outer, text="Only spells this character can learn", variable=self.only_var,
                          command=self._learnable_toggled).pack(anchor="w", pady=(8, 0))
        else:
            self.only_var = tk.BooleanVar(value=False)

        self.count_label = ctk.CTkLabel(outer, text="", font=ui_font("small", 11), text_color=c("text_secondary"),
                                        anchor="w")
        self.count_label.pack(fill="x", pady=(6, 2))
        self.list_frame = ctk.CTkScrollableFrame(outer, fg_color=c("bg_secondary"))
        self.list_frame.pack(fill="both", expand=True)

        bar = ctk.CTkFrame(outer, fg_color="transparent")
        bar.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(bar, text="Done" if self.pick is None else "Save choice", width=110,
                      fg_color=c("accent_primary"), hover_color=c("accent_hover"), text_color=c("text_on_accent"),
                      command=self._done).pack(side="right")
        if self.pick is not None:
            ctk.CTkButton(bar, text="Cancel", width=90, fg_color=c("button_normal"), hover_color=c("button_hover"),
                          text_color=c("text_primary"), command=self._cancel).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------------ what is shown
    def _learnable_toggled(self):
        _remembered["only_learnable"] = bool(self.only_var.get())
        self._refresh()

    def _schedule(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
        try:
            self._job = self.after(DEBOUNCE_MS, self._refresh)
        except tk.TclError:
            self._job = None

    def _is_known(self, spell) -> bool:
        if self.pick is not None:
            return False
        return self.character.has_spell(spell.name)

    def matching(self) -> List[object]:
        """The spells that pass the search, the level menu and the learnable switch (known ones are left out)."""
        words = self.query.get().lower().split()
        level = level_from_label(self.level_menu.get())
        found = []
        for spell in self._all:
            if level is not None and spell.level != level:
                continue
            if words and not all(w in spell.name.lower() for w in words):
                continue
            if self._is_known(spell):
                continue
            if self.pick is not None:
                if not self.pick.allows(spell):
                    continue
            elif self.only_var.get() and not self._rules.allows(spell):
                continue
            found.append(spell)
        return found

    def _summary_text(self) -> str:
        if self.pick is not None:
            left = self.pick.count - len(self._chosen)
            what = self.pick.label
            lists = ", ".join(self.pick.lists)
            where = f" from the {lists} spell list{'s' if len(self.pick.lists) > 1 else ''}" if self.pick.lists and not self.pick.names else ""
            return f"{what}{where}: {len(self._chosen)} of {self.pick.count} chosen" + ("" if left else " (done)")
        r = self._rules
        if not self.only_var.get():
            return "Showing every spell. Adding one that is off the character's list or too high a level asks first."
        lists = " / ".join(r.class_labels) if r.class_labels else "any class"
        if r.any_class and not r.class_labels:
            lists = "any class"
        top = "cantrips only" if r.max_level == 0 else f"up to level {r.max_level}"
        extra = f", plus {len(r.expanded)} added by features" if r.expanded else ""
        return f"{lists} spell list{'s' if len(r.class_labels) > 1 else ''}, {top}{extra}."

    def _refresh(self):
        self._job = None
        self.summary.configure(text=self._summary_text())
        for child in self.list_frame.winfo_children():
            child.destroy()
        found = self.matching()
        shown = found[:MAX_ROWS]
        if not found:
            hint = "" if self.pick is not None or not self.only_var.get() else "\nTurn the switch off to see every spell."
            ctk.CTkLabel(self.list_frame, text="No spells match." + hint, justify="center",
                         text_color=self.theme.get_text_secondary()).pack(pady=30)
        for spell in shown:
            self._row(spell)
        self.count_label.configure(
            text=(f"Showing {len(shown)} of {len(found)}: type to narrow the list." if len(found) > len(shown)
                  else f"{len(found)} spell{'s' if len(found) != 1 else ''}"))

    def _subtitle(self, spell) -> str:
        level = "Cantrip" if spell.level == 0 else f"Level {spell.level}"
        schools = [t for t in spell.tags if t in SCHOOLS]
        bits = [level] + schools[:1]
        classes = ", ".join(sorted({c for c in spell.get_class_names()}))
        if classes:
            bits.append(classes)
        flags = ("R" if spell.ritual else "") + ("C" if spell.concentration else "")
        if flags:
            bits.append("/".join(flags))
        return "  •  ".join(bits)

    def _row(self, spell):
        c = self.theme.get_current_color
        row = ctk.CTkFrame(self.list_frame, fg_color=c("spell_row"), corner_radius=6)
        row.pack(fill="x", pady=2, padx=2)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=(10, 4), pady=4)
        ctk.CTkLabel(text, text=spell.name, font=ui_font("body", 13, bold=True), anchor="w").pack(fill="x")
        sub = self._subtitle(spell)
        warn = ""
        if self.pick is None and not self._rules.allows(spell):
            warn = "  •  " + self._rules.why_not(spell)
        ctk.CTkLabel(text, text=sub + warn, font=ui_font("small", 11), anchor="w", justify="left", wraplength=360,
                     text_color=c("text_warning") if warn else c("text_secondary")).pack(fill="x")
        if self.pick is not None:
            chosen = spell.name in self._chosen
            btn = ctk.CTkButton(row, text="Chosen ✓" if chosen else "Choose", width=84, height=28,
                                fg_color=c("accent_primary") if chosen else c("button_normal"),
                                hover_color=c("accent_hover") if chosen else c("button_hover"),
                                text_color=c("text_on_accent") if chosen else c("text_primary"),
                                command=lambda s=spell: self._toggle_choice(s))
        else:
            btn = ctk.CTkButton(row, text="Add", width=64, height=28, fg_color=c("button_success"),
                                hover_color=c("button_success_hover"), text_color=c("text_primary"))
            btn.configure(command=lambda s=spell, b=btn: self._add(s, b))
        btn.pack(side="right", padx=8, pady=4)

    # ------------------------------------------------------------------ acting on it
    def _add(self, spell, button):
        if self.add_fn is None:
            return
        from validation import validate_spell_for_character
        warnings = validate_spell_for_character(spell, self.character, spell_manager=self.spell_manager,
                                                settings=self.settings)
        if warnings:
            from ui.spell_detail import SpellWarningDialog
            dialog = SpellWarningDialog(self, spell.name, warnings)
            self.wait_window(dialog)
            if not dialog.result:
                return
        if self.add_fn(spell):
            self.added.append(spell.name)
            self._refresh()

    def _toggle_choice(self, spell):
        if spell.name in self._chosen:
            self._chosen.remove(spell.name)
        elif len(self._chosen) < self.pick.count:
            self._chosen.append(spell.name)
        else:                                                      # one more than allowed: the oldest choice goes
            self._chosen.pop(0)
            self._chosen.append(spell.name)
        self._refresh()

    def _done(self):
        if self.pick is not None:
            self.result = list(self._chosen)
        self._close()

    def _cancel(self):
        self.result = None
        self._close()

    def _close(self):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
            self._job = None
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


SCHOOLS = {"Abjuration", "Conjuration", "Divination", "Enchantment", "Evocation", "Illusion", "Necromancy",
           "Transmutation"}
