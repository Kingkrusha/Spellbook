"""
The "Roll effects" part of the object editors (feats, species traits, class and subclass features, magic items).

``RollEffectsEditor`` is a small list of the effects an object has, with Add / Edit / Remove; ``RollEffectDialog`` is
the form for one effect. The effects are plain dicts (see ``roll_effects``), stored with the object, and the Dice
Analyzer applies them to any character that has the object.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

import roll_effects as RE
from theme import get_theme_manager
from typography import ui_font


class RollEffectsEditor(ctk.CTkFrame):
    """A list of roll effects with Add / Edit / Remove, for embedding in an editor dialog."""

    def __init__(self, parent, effects: Optional[List[dict]] = None, allow_item_effects: bool = False,
                 on_change: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.allow_item_effects = allow_item_effects
        self.on_change = on_change
        self._effects: List[dict] = [dict(e) for e in (effects or [])]
        c = self.theme.get_current_color

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Roll effects (Dice Analyzer)", font=ui_font("subheading", 13, bold=True)
                     ).pack(side="left")
        ctk.CTkButton(head, text="+ Add effect", width=100, height=28, command=self._add,
                      fg_color=c('accent_primary'), hover_color=c('accent_hover')).pack(side="right")
        ctk.CTkLabel(self, text="Tell the Dice Analyzer what this does to a character's rolls (advantage, bonuses, extra "
                                "damage, 'if the roll fails' options ...). It is used for every character that has it.",
                     font=ui_font("small"), text_color=c('text_secondary'), justify="left", anchor="w",
                     wraplength=520).pack(fill="x", pady=(2, 4))
        self.rows = ctk.CTkFrame(self, fg_color="transparent")
        self.rows.pack(fill="x")
        self._render()

    # ---- public
    def get(self) -> List[dict]:
        return [dict(e) for e in self._effects]

    def set(self, effects: Optional[List[dict]]):
        self._effects = [dict(e) for e in (effects or [])]
        self._render()

    # ---- rows
    def _render(self):
        for child in self.rows.winfo_children():
            child.destroy()
        c = self.theme.get_current_color
        if not self._effects:
            ctk.CTkLabel(self.rows, text="No roll effects.", font=ui_font("small"),
                         text_color=c('text_secondary')).pack(anchor="w")
        for i, eff in enumerate(self._effects):
            row = ctk.CTkFrame(self.rows, fg_color=c('bg_secondary'), corner_radius=6)
            row.pack(fill="x", pady=2)
            ctk.CTkButton(row, text="✕", width=26, height=26, fg_color=c('button_danger'),
                          hover_color=c('button_danger_hover'), command=lambda i=i: self._remove(i)
                          ).pack(side="right", padx=(2, 6), pady=4)
            ctk.CTkButton(row, text="Edit", width=44, height=26, fg_color=c('button_normal'),
                          hover_color=c('button_hover'), text_color=c('text_primary'),
                          command=lambda i=i: self._edit(i)).pack(side="right", padx=2, pady=4)
            ctk.CTkLabel(row, text=RE.describe(eff), font=ui_font("small", 12), anchor="w", justify="left",
                         wraplength=400).pack(side="left", fill="x", expand=True, padx=8, pady=4)

    def _changed(self):
        self._render()
        if self.on_change:
            self.on_change()

    def _add(self):
        result = self._ask(None)
        if result:
            self._effects.append(result)
            self._changed()

    def _edit(self, index: int):
        result = self._ask(self._effects[index])
        if result:
            self._effects[index] = result
            self._changed()

    def _remove(self, index: int):
        del self._effects[index]
        self._changed()

    def _ask(self, effect: Optional[dict]) -> Optional[dict]:
        dialog = RollEffectDialog(self.winfo_toplevel(), effect, self.allow_item_effects)
        dialog.wait_window()
        try:                                              # the editor around this one grabbed input: take it back
            self.winfo_toplevel().grab_set()
        except Exception:
            pass
        return dialog.result


class RollEffectDialog(ctk.CTkToplevel):
    """The form for one roll effect."""

    def __init__(self, parent, effect: Optional[dict] = None, allow_item_effects: bool = False):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.result: Optional[dict] = None
        self.allow_item_effects = allow_item_effects
        self.title("Roll effect")
        self.geometry("560x640")
        self.minsize(520, 560)
        self.transient(parent)
        try:
            self.grab_set()
        except Exception:
            pass
        self._effect = dict(effect) if effect else RE.blank_effect("skill")
        self._affects_names = {RE.AFFECTS[k]: k for k in RE.AFFECTS
                               if allow_item_effects or k not in RE.ITEM_AFFECTS}
        self._build()
        self._load(self._effect)
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - 560) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - 640) // 2)
        self.geometry(f"+{x}+{y}")

    # ---- layout
    def _label(self, parent, text, bold=False):
        ctk.CTkLabel(parent, text=text, font=ui_font("subheading", 13, bold=True) if bold else ui_font("body"),
                     anchor="w").pack(fill="x", pady=(8, 2))

    def _build(self):
        c = self.theme.get_current_color
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(12, 0))
        self._label(body, "What does it change?", True)
        self.affects_menu = ctk.CTkOptionMenu(body, values=list(self._affects_names), command=self._affects_changed)
        self.affects_menu.pack(fill="x")
        self._label(body, "Only for (optional)", True)
        self.limit_entry = ctk.CTkEntry(body, height=30)
        self.limit_entry.pack(fill="x")
        self.limit_entry.bind("<KeyRelease>", lambda _e: self._preview())
        self.limit_help = ctk.CTkLabel(body, text="", font=ui_font("small"), text_color=c('text_secondary'),
                                       anchor="w", justify="left", wraplength=480)
        self.limit_help.pack(fill="x")
        self._label(body, "What does it do?", True)
        self.does_menu = ctk.CTkOptionMenu(body, values=["-"], command=lambda _v: self._does_changed())
        self.does_menu.pack(fill="x")

        self.numbers = ctk.CTkFrame(body, fg_color="transparent")
        self.numbers.pack(fill="x", pady=(8, 0))
        self.value_row = ctk.CTkFrame(self.numbers, fg_color="transparent")
        self.value_label = ctk.CTkLabel(self.value_row, text="Number", width=110, anchor="w")
        self.value_label.pack(side="left")
        self.value_entry = ctk.CTkEntry(self.value_row, width=80, height=28, justify="center")
        self.value_entry.pack(side="left")
        self.value_entry.bind("<KeyRelease>", lambda _e: self._preview())
        self.dice_row = ctk.CTkFrame(self.numbers, fg_color="transparent")
        ctk.CTkLabel(self.dice_row, text="Dice", width=110, anchor="w").pack(side="left")
        self.count_entry = ctk.CTkEntry(self.dice_row, width=50, height=28, justify="center")
        self.count_entry.pack(side="left")
        ctk.CTkLabel(self.dice_row, text=" d ", width=20).pack(side="left")
        self.sides_entry = ctk.CTkEntry(self.dice_row, width=60, height=28, justify="center")
        self.sides_entry.pack(side="left")
        for e in (self.count_entry, self.sides_entry):
            e.bind("<KeyRelease>", lambda _e: self._preview())
        self.scale_row = ctk.CTkFrame(self.numbers, fg_color="transparent")
        ctk.CTkLabel(self.scale_row, text="Plus", width=110, anchor="w").pack(side="left")
        self.scale_menu = ctk.CTkOptionMenu(self.scale_row, values=[s or "nothing extra" for s in RE.SCALES], width=240,
                                            command=lambda _v: self._preview())
        self.scale_menu.pack(side="left")

        self.applies = ctk.CTkFrame(body, fg_color="transparent")
        self.applies.pack(fill="x", pady=(10, 0))
        self.choice_var = ctk.BooleanVar(value=False)
        self.default_var = ctk.BooleanVar(value=False)
        self.once_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.applies, text="A choice I switch on for the roll (not always on)", variable=self.choice_var,
                        command=self._preview).pack(anchor="w", pady=2)
        ctk.CTkCheckBox(self.applies, text="...and it starts switched on", variable=self.default_var,
                        command=self._preview).pack(anchor="w", padx=(24, 0), pady=2)
        self.once_box = ctk.CTkCheckBox(self.applies, text="Once per turn (damage)", variable=self.once_var,
                                        command=self._preview)
        self._label(body, "Name (optional)", True)
        self.label_entry = ctk.CTkEntry(body, height=30, placeholder_text="shown in the notes under the graph")
        self.label_entry.pack(fill="x")

        self.preview = ctk.CTkLabel(self, text="", font=ui_font("body", 13, bold=True), anchor="w", justify="left",
                                    wraplength=500, text_color=c('text_label'))
        self.preview.pack(fill="x", padx=16, pady=(8, 0))
        self.error = ctk.CTkLabel(self, text="", font=ui_font("small"), anchor="w", justify="left", wraplength=500,
                                  text_color=c('compare_worse'))
        self.error.pack(fill="x", padx=16)
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=12)
        ctk.CTkButton(btns, text="Cancel", width=90, fg_color=c('button_normal'), hover_color=c('button_hover'),
                      text_color=c('text_primary'), command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btns, text="Save", width=90, fg_color=c('button_success'),
                      hover_color=c('button_success_hover'), text_color=c('text_primary'),
                      command=self._save).pack(side="right")

    # ---- state
    def _affects_key(self) -> str:
        return self._affects_names.get(self.affects_menu.get(), "skill")

    def _does_key(self) -> str:
        names = {RE.DOES[k]: k for k in RE.DOES}
        return names.get(self.does_menu.get(), "advantage")

    def _load(self, eff: dict):
        affects = eff.get("affects", "skill")
        if affects not in RE.AFFECTS or (affects in RE.ITEM_AFFECTS and not self.allow_item_effects):
            affects = "skill"
        self.affects_menu.set(RE.AFFECTS[affects])
        self._refresh_does(affects, eff.get("does"))
        self.limit_entry.insert(0, eff.get("limit", "") or "")
        self.value_entry.insert(0, str(eff.get("value", 0) or 0))
        self.count_entry.insert(0, str(eff.get("count", 1) or 0))
        self.sides_entry.insert(0, str(eff.get("sides", 4) or 4))
        self.scale_menu.set(eff.get("scales") or "nothing extra")
        self.choice_var.set(bool(eff.get("choice")))
        self.default_var.set(bool(eff.get("default_on")))
        self.once_var.set(bool(eff.get("once")))
        self.label_entry.insert(0, eff.get("label", "") or "")
        self._does_changed()

    def _affects_changed(self, _value=None):
        self._refresh_does(self._affects_key(), None)
        self._does_changed()

    def _refresh_does(self, affects: str, current: Optional[str]):
        options = RE.DOES_FOR[affects]
        self.does_menu.configure(values=[RE.DOES[k] for k in options])
        self.does_menu.set(RE.DOES[current] if current in options else RE.DOES[options[0]])
        self.limit_help.configure(text=RE.LIMIT_HELP.get(affects, ""))

    def _does_changed(self):
        does, affects = self._does_key(), self._affects_key()
        for w in (self.value_row, self.dice_row, self.scale_row):
            w.pack_forget()
        if does in ("bonus", "fail reroll"):
            self.value_label.configure(text="Number" if does == "bonus" else "Bonus to the new roll")
            self.value_row.pack(fill="x", pady=2)
            self.scale_row.pack(fill="x", pady=2)
        elif does in ("minimum", "reroll", "crit", "total at least", "set"):
            self.value_label.configure(text={"minimum": "Counts as (at least)", "reroll": "Rerolls this or less",
                                             "crit": "Critical on this or more", "total at least": "Total at least",
                                             "set": "Becomes"}[does])
            self.value_row.pack(fill="x", pady=2)
        elif does in ("dice", "penalty dice"):
            self.dice_row.pack(fill="x", pady=2)
        elif does == "fail add":
            self.dice_row.pack(fill="x", pady=2)
            self.value_label.configure(text="Plus a number")
            self.value_row.pack(fill="x", pady=2)
        elif does == "extra damage":
            self.dice_row.pack(fill="x", pady=2)
            self.value_label.configure(text="Plus a number")
            self.value_row.pack(fill="x", pady=2)
            self.scale_row.pack(fill="x", pady=2)
        is_dmg = affects in RE.DAMAGE_AFFECTS
        if is_dmg:
            self.once_box.pack(anchor="w", pady=2)
        else:
            self.once_box.pack_forget()
        self.applies.pack_forget() if affects in RE.ITEM_AFFECTS else self.applies.pack(fill="x", pady=(10, 0),
                                                                                         after=self.numbers)
        self._preview()

    def _collect(self) -> dict:
        def num(entry, default=0):
            try:
                return int(entry.get().strip().replace("−", "-") or default)
            except ValueError:
                return default
        scale = self.scale_menu.get()
        return {"affects": self._affects_key(), "limit": self.limit_entry.get().strip(), "does": self._does_key(),
                "value": num(self.value_entry), "count": num(self.count_entry, 1), "sides": num(self.sides_entry, 4),
                "scales": "" if scale == "nothing extra" else scale, "choice": bool(self.choice_var.get()),
                "default_on": bool(self.default_var.get()) and bool(self.choice_var.get()),
                "once": bool(self.once_var.get()), "label": self.label_entry.get().strip()}

    def _preview(self):
        eff = self._collect()
        self.preview.configure(text=RE.describe(eff))
        self.error.configure(text=RE.validate(eff))

    def _save(self):
        eff = self._collect()
        problem = RE.validate(eff)
        if problem:
            self.error.configure(text=problem)
            return
        self.result = eff
        self.destroy()
