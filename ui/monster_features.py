"""
The lists of traits, actions, reactions... in the Monster editor.

An entry is plain text, or - for an action, bonus action, reaction or legendary action - an **attack** or a **saving
throw effect** that the editor works out from the monster's own stats: the attack bonus is a core stat plus the
proficiency bonus, the damage adds the stat's modifier, the DC is 8 + proficiency + a stat. Change the monster's Strength
or CR and every linked attack follows. Hovering a number says where it comes from.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import monster_rules as MR
from stat_block import StatBlockFeature
from theme import get_theme_manager
from typography import ui_font
from ui.menu_button import MenuButton
from ui.tooltip import HoverTooltip

TEXT, ATTACK, SAVE = "Text", "Attack", "Saving throw"
KIND_LABELS = list(MR.ATTACK_KINDS.values())
_KIND_BY_LABEL = {v: k for k, v in MR.ATTACK_KINDS.items()}


def _default_attack() -> dict:
    return {"mode": "attack", "kind": "melee", "ability": "STR", "proficient": True, "reach": "5", "range": "",
            "dice": "1d6", "type": "Slashing", "extra_dice": "", "extra_type": "Fire", "effect": ""}


def _default_save() -> dict:
    return {"mode": "save", "save": "DEX", "dc_ability": "CON", "area": "each creature in a 15-foot Cone",
            "dice": "4d6", "type": "Fire", "half": True, "effect": ""}


class StatFeatureList(ctk.CTkFrame):
    """An ordered list of named stat block entries, some of them linked to the monster's stats."""

    def __init__(self, parent, label: str, hint: str = "", stats: Optional[Callable[[], MR.Stats]] = None,
                 builder: bool = False, on_change: Optional[Callable[[], None]] = None):
        theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.theme = theme
        self._stats = stats or (lambda: MR.Stats())
        self._builder = builder
        self._on_change = on_change or (lambda: None)
        self._rows: List[dict] = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 3))
        ctk.CTkLabel(header, text=label, font=ui_font("subheading", 13, bold=True)).pack(side="left")
        ctk.CTkButton(
            header, text="+ Add", width=70,
            fg_color=theme.get_current_color('button_success'),
            hover_color=theme.get_current_color('button_success_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=lambda: self.add_feature(focus=True),
        ).pack(side="right")
        if hint:
            ctk.CTkLabel(self, text=hint, font=ui_font("small"), anchor="w", justify="left",
                         text_color=theme.get_text_secondary(), wraplength=560).pack(fill="x")

        self._card = ctk.CTkFrame(self, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
        self._card.pack(fill="x")
        self._empty_label = ctk.CTkLabel(self._card, text="None added.", font=ui_font("body"),
                                         text_color=theme.get_text_secondary())
        self._sync_empty_label()

    # ------------------------------------------------------------------ rows

    def _sync_empty_label(self):
        if self._rows:
            self._empty_label.pack_forget()
        else:
            self._empty_label.pack(anchor="w", padx=10, pady=8)

    def _repack(self):
        for row in self._rows:
            row["frame"].pack_forget()
        for row in self._rows:
            row["frame"].pack(fill="x", padx=8, pady=4)
        self._sync_empty_label()

    def add_feature(self, name: str = "", description: str = "", focus: bool = False,
                    build: Optional[dict] = None):
        theme = self.theme
        c = theme.get_current_color
        frame = ctk.CTkFrame(self._card, fg_color=c('bg_tertiary'), corner_radius=8)
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 2))
        name_entry = ctk.CTkEntry(top, placeholder_text="Name (e.g. Multiattack)")
        name_entry.pack(side="left", fill="x", expand=True)
        row = {"frame": frame, "name": name_entry, "mode": ctk.StringVar(value=TEXT), "attack": None, "save": None,
               "keep": {}, "tips": {}}

        for text, command, hover in (
                ("×", lambda: self._remove(row), c('button_danger')),
                ("▼", lambda: self._move(row, 1), c('button_hover')),
                ("▲", lambda: self._move(row, -1), c('button_hover'))):
            ctk.CTkButton(top, text=text, width=26, height=26, fg_color="transparent",
                          hover_color=hover, text_color=c('text_primary'),
                          command=command).pack(side="right", padx=(2, 0))
        if self._builder:
            menu = MenuButton(top, [TEXT, ATTACK, SAVE], row["mode"], width=118, height=26,
                              command=lambda v, r=row: self._set_mode(r, v))
            menu.pack(side="right", padx=(6, 6))
            row["mode_menu"] = menu

        row["text_frame"] = ctk.CTkFrame(frame, fg_color="transparent")
        desc_box = ctk.CTkTextbox(row["text_frame"], height=70, wrap="word")
        desc_box.pack(fill="x", padx=8, pady=(0, 8))
        desc_box.insert("1.0", description)
        row["desc"] = desc_box
        row["text_frame"].pack(fill="x")
        row["link_button"] = None
        if self._builder:
            row["link_button"] = ctk.CTkButton(
                row["text_frame"], text="Link to stats", width=110, height=24, fg_color=c('button_normal'),
                hover_color=c('button_hover'), text_color=c('text_primary'), font=ui_font("small"),
                command=lambda r=row: self._link(r))
            row["link_button"].pack(anchor="w", padx=8, pady=(0, 8))
            HoverTooltip(row["link_button"],
                         "Turns an attack or saving throw written as text into one worked out from this monster's "
                         "stats (only when its numbers already follow from them).")
        row["preview"] = ctk.CTkLabel(frame, text="", font=ui_font("small"), anchor="w", justify="left",
                                      text_color=theme.get_text_secondary(), wraplength=540)
        name_entry.insert(0, name)

        self._rows.append(row)
        self._repack()
        if build:
            self._set_mode(row, ATTACK if build.get("mode") != "save" else SAVE, build=build)
        if focus:
            name_entry.focus_set()

    def _remove(self, row: dict):
        if row in self._rows:
            self._rows.remove(row)
            row["frame"].destroy()
            self._sync_empty_label()
            self._on_change()

    def _move(self, row: dict, delta: int):
        index = self._rows.index(row)
        target = index + delta
        if 0 <= target < len(self._rows):
            self._rows[index], self._rows[target] = self._rows[target], self._rows[index]
            self._repack()

    # ------------------------------------------------------------------ modes

    def _set_mode(self, row: dict, mode: str, build: Optional[dict] = None):
        previous = row.get("shown", TEXT)
        row["mode"].set(mode)
        if mode == TEXT:
            if previous in (ATTACK, SAVE):                    # keep the text the attack had written
                text = self._built(row).text
                row["desc"].delete("1.0", "end")
                row["desc"].insert("1.0", text)
            row["text_frame"].pack(fill="x")
            for key in ("attack", "save"):
                if row[key]:
                    row[key]["frame"].pack_forget()
            row["preview"].pack_forget()
        else:
            row["text_frame"].pack_forget()
            fresh = (row["attack"] is None) if mode == ATTACK else (row["save"] is None)
            if mode == ATTACK and row["attack"] is None:
                self._make_attack(row)
            if mode == SAVE and row["save"] is None:
                self._make_save(row)
            if build is None and previous == TEXT:
                guess = MR.guess_build(row["desc"].get("1.0", "end-1c"), self._stats())
                if guess and guess.get("mode") == ("save" if mode == SAVE else "attack"):
                    build = guess
            if build is None and fresh:
                build = _default_save() if mode == SAVE else _default_attack()
            for key in ("attack", "save"):
                if row[key]:
                    row[key]["frame"].pack_forget()
            current = row["attack"] if mode == ATTACK else row["save"]
            current["frame"].pack(fill="x", padx=8, pady=(0, 4))
            row["preview"].pack(fill="x", padx=12, pady=(0, 8))
            if build is not None:
                self._load_build(row, build)
        row["shown"] = mode
        self._refresh_row(row)
        self._on_change()

    def _link(self, row: dict):
        text = row["desc"].get("1.0", "end-1c")
        guess = MR.guess_build(text, self._stats())
        if not guess:
            messagebox.showinfo(
                "Link to stats",
                "This entry cannot be linked as it stands: it is not an attack or a saving throw effect, its numbers "
                "do not follow from this monster's stats, or its wording is unusual.\n\nChoose Attack or Saving throw "
                "to build one from the stats instead.", parent=self.winfo_toplevel())
            return
        self._set_mode(row, SAVE if guess["mode"] == "save" else ATTACK, build=guess)

    # ---- the attack form

    def _entry(self, parent, width, placeholder="", text=""):
        entry = ctk.CTkEntry(parent, width=width, height=28, placeholder_text=placeholder)
        if text:
            entry.insert(0, text)
        entry.bind("<KeyRelease>", lambda _e: self._changed(), add="+")
        return entry

    def _menu(self, parent, values, var, width):
        return MenuButton(parent, values, var, width=width, height=28, command=lambda _v: self._changed())

    def _label(self, parent, text):
        return ctk.CTkLabel(parent, text=text, font=ui_font("small"), text_color=self.theme.get_text_secondary())

    def _chip(self, parent, row: dict, key: str):
        label = ctk.CTkLabel(parent, text="", font=ui_font("body", 12, bold=True), corner_radius=6,
                             fg_color=self.theme.get_current_color("bg_secondary"), padx=8, pady=2)
        row["tips"][key] = HoverTooltip(label, "")
        return label

    def _make_attack(self, row: dict):
        frame = ctk.CTkFrame(row["frame"], fg_color="transparent")
        w = {"frame": frame, "kind": ctk.StringVar(value="Melee"), "ability": ctk.StringVar(value="STR"),
             "proficient": ctk.BooleanVar(value=True), "type": ctk.StringVar(value="Slashing"),
             "extra_type": ctk.StringVar(value="Fire")}
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=2)
        self._menu(line, KIND_LABELS, w["kind"], 140).pack(side="left")
        self._label(line, "  uses").pack(side="left")
        self._menu(line, MR.ABILITIES, w["ability"], 72).pack(side="left", padx=(4, 8))
        ctk.CTkCheckBox(line, text="Proficient", variable=w["proficient"], width=90, font=ui_font("small"),
                        checkbox_width=18, checkbox_height=18, command=self._changed).pack(side="left")
        self._label(line, "  reach").pack(side="left")
        w["reach"] = self._entry(line, 44, text="5")
        w["reach"].pack(side="left", padx=(2, 6))
        self._label(line, "range").pack(side="left")
        w["range"] = self._entry(line, 74, "80/320")
        w["range"].pack(side="left", padx=(2, 0))
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=2)
        self._label(line, "Damage").pack(side="left")
        w["dice"] = self._entry(line, 64, "1d8")
        w["dice"].pack(side="left", padx=(4, 4))
        self._menu(line, MR.DAMAGE_TYPES, w["type"], 118).pack(side="left")
        self._label(line, "  plus").pack(side="left")
        w["extra_dice"] = self._entry(line, 64, "2d6")
        w["extra_dice"].pack(side="left", padx=(4, 4))
        self._menu(line, MR.DAMAGE_TYPES, w["extra_type"], 118).pack(side="left")
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=2)
        self._label(line, "Then").pack(side="left")
        w["effect"] = self._entry(line, 200, "e.g. The target has the Prone condition.")
        w["effect"].pack(side="left", fill="x", expand=True, padx=(6, 0))
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=(4, 2))
        w["bonus_chip"] = self._chip(line, row, "bonus")
        w["bonus_chip"].pack(side="left")
        w["damage_chip"] = self._chip(line, row, "damage")
        w["damage_chip"].pack(side="left", padx=(8, 0))
        row["attack"] = w

    def _make_save(self, row: dict):
        frame = ctk.CTkFrame(row["frame"], fg_color="transparent")
        w = {"frame": frame, "save": ctk.StringVar(value="DEX"), "dc_ability": ctk.StringVar(value="CON"),
             "type": ctk.StringVar(value="Fire"), "half": ctk.BooleanVar(value=True)}
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=2)
        self._label(line, "Target saves with").pack(side="left")
        self._menu(line, MR.ABILITIES, w["save"], 72).pack(side="left", padx=(4, 10))
        self._label(line, "DC from").pack(side="left")
        self._menu(line, MR.ABILITIES, w["dc_ability"], 72).pack(side="left", padx=(4, 0))
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=2)
        self._label(line, "Area / target").pack(side="left")
        w["area"] = self._entry(line, 200, "e.g. each creature in a 30-foot Cone")
        w["area"].pack(side="left", fill="x", expand=True, padx=(6, 0))
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=2)
        self._label(line, "Damage").pack(side="left")
        w["dice"] = self._entry(line, 64, "10d10")
        w["dice"].pack(side="left", padx=(4, 4))
        self._menu(line, MR.DAMAGE_TYPES, w["type"], 118).pack(side="left")
        ctk.CTkCheckBox(line, text="Half damage on a success", variable=w["half"], font=ui_font("small"),
                        checkbox_width=18, checkbox_height=18, command=self._changed).pack(side="left", padx=(12, 0))
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=2)
        self._label(line, "Then").pack(side="left")
        w["effect"] = self._entry(line, 200, "e.g. The target has the Frightened condition until the end of its next turn.")
        w["effect"].pack(side="left", fill="x", expand=True, padx=(6, 0))
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x", pady=(4, 2))
        w["dc_chip"] = self._chip(line, row, "dc")
        w["dc_chip"].pack(side="left")
        w["damage_chip"] = self._chip(line, row, "damage")
        w["damage_chip"].pack(side="left", padx=(8, 0))
        row["save"] = w

    @staticmethod
    def _put(entry: ctk.CTkEntry, value):
        entry.delete(0, "end")
        if value not in (None, ""):
            entry.insert(0, str(value))

    def _load_build(self, row: dict, build: dict):
        row["keep"] = {k: build[k] for k in ("success", "after") if build.get(k)}
        if build.get("mode") == "save":
            w = row["save"]
            w["save"].set(build.get("save", "DEX"))
            w["dc_ability"].set(build.get("dc_ability", "CON"))
            w["type"].set(str(build.get("type", "Fire")).title())
            w["half"].set(bool(build.get("half", True)))
            for key in ("area", "dice", "effect"):
                self._put(w[key], build.get(key, ""))
        else:
            w = row["attack"]
            w["kind"].set(MR.ATTACK_KINDS.get(build.get("kind", "melee"), "Melee"))
            w["ability"].set(build.get("ability", "STR"))
            w["proficient"].set(bool(build.get("proficient", True)))
            w["type"].set(str(build.get("type", "Slashing")).title())
            w["extra_type"].set(str(build.get("extra_type", "Fire")).title())
            for key in ("reach", "range", "dice", "extra_dice", "effect"):
                self._put(w[key], build.get(key, ""))

    def _read_build(self, row: dict) -> Optional[dict]:
        mode = row.get("shown", TEXT)
        if mode == ATTACK and row["attack"]:
            w = row["attack"]
            build = {"mode": "attack", "kind": _KIND_BY_LABEL.get(w["kind"].get(), "melee"),
                     "ability": w["ability"].get(), "proficient": bool(w["proficient"].get()),
                     "reach": w["reach"].get().strip(), "range": w["range"].get().strip(),
                     "dice": w["dice"].get().strip(), "type": w["type"].get(),
                     "extra_dice": w["extra_dice"].get().strip(), "extra_type": w["extra_type"].get(),
                     "effect": w["effect"].get().strip()}
        elif mode == SAVE and row["save"]:
            w = row["save"]
            build = {"mode": "save", "save": w["save"].get(), "dc_ability": w["dc_ability"].get(),
                     "area": w["area"].get().strip(), "dice": w["dice"].get().strip(), "type": w["type"].get(),
                     "half": bool(w["half"].get()), "effect": w["effect"].get().strip()}
        else:
            return None
        build.update(row.get("keep") or {})
        return build

    # ------------------------------------------------------------------ keeping the numbers current

    def _changed(self):
        for row in self._rows:
            self._refresh_row(row)
        self._on_change()

    def refresh(self):
        """The monster's stats changed: work every linked entry out again."""
        for row in self._rows:
            self._refresh_row(row)

    def _built(self, row: dict) -> MR.Built:
        build = self._read_build(row)
        return MR.built(build, self._stats()) if build else MR.Built()

    def _refresh_row(self, row: dict):
        build = self._read_build(row)
        if build is None:
            return
        result = MR.built(build, self._stats())
        row["preview"].configure(text=result.text)
        if build["mode"] == "attack":
            w = row["attack"]
            w["bonus_chip"].configure(text=f"{MR.signed(result.bonus)} to hit")
            row["tips"]["bonus"].update_text(result.tip_bonus)
            w["damage_chip"].configure(text=f"{result.average} damage" if result.average is not None else "no damage")
            row["tips"]["damage"].update_text(result.tip_damage or "No damage dice entered.")
        else:
            w = row["save"]
            w["dc_chip"].configure(text=f"DC {result.dc}")
            row["tips"]["dc"].update_text(result.tip_dc)
            w["damage_chip"].configure(text=f"{result.average} damage" if result.average is not None else "no damage")
            row["tips"]["damage"].update_text(result.tip_damage or "No damage dice entered.")

    # ------------------------------------------------------------------ data in and out

    def set_features(self, features: List[StatBlockFeature]):
        for row in self._rows:
            row["frame"].destroy()
        self._rows = []
        for feature in features:
            self.add_feature(feature.name, feature.description, build=getattr(feature, "build", None))
        self._sync_empty_label()

    def _read(self):
        for row in self._rows:
            name = row["name"].get().strip()
            build = self._read_build(row)
            if build is not None:
                yield name, MR.built(build, self._stats()).text, build
            else:
                yield name, row["desc"].get("1.0", "end-1c").strip(), None

    def get_features(self) -> List[StatBlockFeature]:
        return [StatBlockFeature(n, d, b) for n, d, b in self._read() if n or (d and b is None) or b]

    def has_unnamed(self) -> bool:
        return any((d or b) and not n for n, d, b in self._read())
