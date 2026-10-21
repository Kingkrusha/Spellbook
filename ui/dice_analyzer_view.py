"""Dice Analyzer page: work out the odds of a roll, either one you build or one your character can make.

Custom mode builds an expression from rows of dice (or takes one typed in) and shows the distribution
of the total. Character mode lists what a character sheet can roll - skills, saves, attacks, spells -
with the character's features applied (see ``character_rolls``) and the situational choices for it.

The maths can take a moment for big rolls, so it runs on a worker thread; only the newest request is
shown. Everything the page remembers lives in the ``state`` dict it is given, which the main window
keeps, so leaving the page and coming back finds it as it was.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from character_rolls import (BONUS_DIE_SIDES, BONUS_PRESETS, MODES, Analysis, CharacterAnalyzer, Lookups, Option,
                             RollOption, View)
from dice_analyzer import DiceError, DiceTerm, Expression, parse_expression, summarize
from theme import get_theme_manager
from typography import ui_font
from ui.background_work import BackgroundWorkMixin
from ui.bar_list_chart import BarListChart, BarRow
from ui.distribution_chart import DistributionChart, percent_text
from ui.lazy_destroy import destroy_later

MAX_ROWS = 12
LEFT_WIDTH = 440
DEBOUNCE_MS = 260
COMMON_DICE = [4, 6, 8, 10, 12, 20, 100]
KINDS = ["Normal", "Advantage", "Disadvantage", "Double advantage", "Double disadvantage", "Emphasis"]
KIND_DICE = {"Normal": (1, "high"), "Advantage": (2, "high"), "Disadvantage": (2, "low"),
             "Double advantage": (3, "high"), "Double disadvantage": (3, "low"), "Emphasis": (2, "emph")}
KEEPS = ["All dice", "Highest", "Lowest"]
CATEGORIES = ["Attacks", "Spells", "Skills", "Saves", "Checks"]
EXAMPLES = {
    "Examples...": "",
    "Attack with advantage: d20 + 7": "d20adv+7",
    "Reliable Talent check: d20 (min 10) + 9": "d20min10+9",
    "Halfling Luck check: d20 reroll 1s + 5": "d20r1+5",
    "Rolling ability scores: 4d6 drop the lowest": "4d6kh3",
    "Fireball: 8d6": "8d6",
    "Great Weapon Fighting: 2d6 + 4 (reroll 1s and 2s)": "2d6r2+4",
    "Sneak Attack at level 11: 1d8 + 6d6 + 4": "1d8+6d6+4",
    "Elven Accuracy: three d20, keep best, + 8": "d20elf+8",
    "A big pile: 200d6 + 80d10 + 30": "200d6+80d10+30",
}


class _Row:
    """One kind of dice in the builder."""

    def __init__(self, view: "DiceAnalyzerView", parent):
        self.view = view
        theme = view.theme
        self.frame = ctk.CTkFrame(parent, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=6, pady=(6, 2))
        self.sign = ctk.CTkButton(top, text="+", width=30, height=28, command=self._flip_sign,
                                  fg_color=theme.get_current_color('button_normal'),
                                  hover_color=theme.get_current_color('button_hover'))
        self.sign.pack(side="left")
        self.count = self._entry(top, 62, "1")
        self.count.pack(side="left", padx=(6, 0))
        ctk.CTkLabel(top, text="d", font=ui_font("heading", 16, bold=True)).pack(side="left", padx=4)
        self.sides = self._entry(top, 62, "6")
        self.sides.pack(side="left")
        ctk.CTkButton(top, text="✕", width=28, height=28, command=lambda: view._remove_row(self),
                      fg_color=theme.get_current_color('button_danger'),
                      hover_color=theme.get_current_color('button_danger_hover')).pack(side="right")
        low = ctk.CTkFrame(self.frame, fg_color="transparent")
        low.pack(fill="x", padx=6, pady=(0, 6))
        ctk.CTkLabel(low, text="Reroll ≤", font=ui_font("small", 11)).pack(side="left")
        self.reroll = self._entry(low, 40, "", "0")
        self.reroll.pack(side="left", padx=(3, 6))
        ctk.CTkLabel(low, text="Min", font=ui_font("small", 11)).pack(side="left")
        self.minimum = self._entry(low, 40, "", "1")
        self.minimum.pack(side="left", padx=(3, 6))
        self.kind = ctk.CTkOptionMenu(low, values=KINDS, width=104, height=26, dynamic_resizing=False, command=lambda _v: view._rows_changed())
        self.kind.pack(side="left")
        self.keep = ctk.CTkOptionMenu(low, values=KEEPS, width=82, height=26, command=lambda _v: view._rows_changed())
        self.keep.pack(side="left", padx=(6, 3))
        self.keep_n = self._entry(low, 36, "", "n")
        self.keep_n.pack(side="left")
        self._negative = False

    def _entry(self, parent, width, text, placeholder=""):
        e = ctk.CTkEntry(parent, width=width, height=26, placeholder_text=placeholder or None, justify="center")
        if text:
            e.insert(0, text)
        e.bind("<KeyRelease>", lambda _e: self.view._rows_changed())
        return e

    def _flip_sign(self):
        self._negative = not self._negative
        self.sign.configure(text="−" if self._negative else "+")
        self.view._rows_changed()

    @staticmethod
    def _int(entry, default: int, what: str) -> int:
        raw = entry.get().strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            raise DiceError(f"{what} must be a whole number.")

    def term(self) -> DiceTerm:
        t = DiceTerm(self._int(self.count, 1, "The number of dice"), self._int(self.sides, 6, "The number of sides"),
                     -1 if self._negative else 1)
        raw = self.reroll.get().strip()
        if raw:
            t.reroll_once = not raw.endswith("!")
            try:
                t.reroll_max = int(raw.rstrip("!"))
            except ValueError:
                raise DiceError("Reroll must be a number (add ! to keep rerolling).")
        t.minimum = self._int(self.minimum, 1, "The minimum")
        kind = self.kind.get()
        t.copies, t.pick = KIND_DICE[kind]
        keep = self.keep.get()
        if keep != KEEPS[0]:
            t.keep = "high" if keep == "Highest" else "low"
            t.keep_n = self._int(self.keep_n, 1, "The number of dice to keep")
        t.validate()
        return t

    def load(self, t: DiceTerm):
        def put(entry, text):
            entry.delete(0, "end")
            entry.insert(0, text)
        put(self.count, str(t.count))
        put(self.sides, str(t.sides))
        self._negative = t.sign < 0
        self.sign.configure(text="−" if self._negative else "+")
        put(self.reroll, (str(t.reroll_max) + ("" if t.reroll_once else "!")) if t.reroll_max else "")
        put(self.minimum, str(t.minimum) if t.minimum > 1 else "")
        self.kind.set({v: k for k, v in KIND_DICE.items()}.get((t.copies, t.pick), "Normal"))
        self.keep.set(KEEPS[0] if not t.keep else ("Highest" if t.keep == "high" else "Lowest"))
        put(self.keep_n, str(t.keep_n) if t.keep else "")


class _BonusDice:
    """The "Bonus dice" list: any number of dice added to (or subtracted from) a roll."""

    def __init__(self, view: "DiceAnalyzerView", parent, items, on_change: Callable[[], None]):
        self.view = view
        self.on_change = on_change
        c = view.theme.get_current_color
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.rows: List[dict] = []
        self.rows_frame = ctk.CTkFrame(self.frame, fg_color="transparent", height=1)
        self.rows_frame.pack(fill="x")
        names = ["Add a bonus die..."] + [p[0] for p in BONUS_PRESETS]
        self.menu = ctk.CTkOptionMenu(self.frame, values=names, height=26, command=self._add_preset)
        self.menu.pack(fill="x", pady=(2, 0))
        for item in items or []:
            self._add(item.get("label", "Bonus die"), int(item.get("sign", 1)), int(item.get("count", 1)),
                      int(item.get("sides", 6)), notify=False)

    def _add_preset(self, name: str):
        self.menu.set("Add a bonus die...")
        for label, sign, count, sides in BONUS_PRESETS:
            if label == name:
                self._add(label.split(" (")[0], sign, count, sides)
                return

    def _add(self, label: str, sign: int, count: int, sides: int, notify: bool = True):
        c = self.view.theme.get_current_color
        frame = ctk.CTkFrame(self.rows_frame, fg_color="transparent")
        frame.pack(fill="x", pady=1)
        row = {"frame": frame, "label": label, "negative": sign < 0}
        sign_btn = ctk.CTkButton(frame, text="−" if sign < 0 else "+", width=28, height=26,
                                 fg_color=c('button_normal'), hover_color=c('button_hover'), text_color=c('text_primary'))
        sign_btn.pack(side="left")
        count_entry = ctk.CTkEntry(frame, width=40, height=26, justify="center")
        count_entry.insert(0, str(count))
        count_entry.pack(side="left", padx=(4, 0))
        die = ctk.CTkOptionMenu(frame, values=[f"d{n}" for n in BONUS_DIE_SIDES], width=70, height=26,
                                command=lambda _v: self.on_change())
        die.set(f"d{sides}" if sides in BONUS_DIE_SIDES else "d6")
        die.pack(side="left", padx=4)
        ctk.CTkLabel(frame, text=label, font=ui_font("small", 11), anchor="w",
                     text_color=c('text_secondary')).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(frame, text="✕", width=26, height=26, fg_color=c('button_danger'),
                      hover_color=c('button_danger_hover'), command=lambda r=row: self._remove(r)).pack(side="right")

        def flip(r=row, b=sign_btn):
            r["negative"] = not r["negative"]
            b.configure(text="−" if r["negative"] else "+")
            self.on_change()
        sign_btn.configure(command=flip)
        count_entry.bind("<KeyRelease>", lambda _e: self.on_change())
        row.update(count=count_entry, die=die)
        self.rows.append(row)
        if notify:
            self.on_change()

    def _remove(self, row: dict):
        if row in self.rows:
            self.rows.remove(row)
            destroy_later(row["frame"])
        self.on_change()

    def value(self) -> List[dict]:
        out = []
        for r in self.rows:
            try:
                count = max(1, int(r["count"].get().strip() or 1))
            except ValueError:
                count = 1
            out.append({"label": r["label"], "sign": -1 if r["negative"] else 1, "count": count,
                        "sides": int(r["die"].get()[1:])})
        return out


class DiceAnalyzerView(BackgroundWorkMixin, ctk.CTkFrame):
    POLL_MS = 40

    def __init__(self, parent, state: dict, character_names: Callable[[], List[str]],
                 load_character: Callable[[str], Optional[tuple]], lookups: Lookups,
                 on_back: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.state = state
        self.character_names = character_names
        self.load_character = load_character
        self.lookups = lookups
        self.on_back = on_back

        state.setdefault("mode", "Custom")
        state.setdefault("expr", "2d6+4")
        state.setdefault("roll_twice", "Roll once")
        state.setdefault("cumulative", False)
        state.setdefault("target", 15)
        state.setdefault("options", {})
        state.setdefault("manual", {})

        self._rows: List[_Row] = []
        self._syncing = False
        self._init_background_work()
        self._analysis: Optional[Analysis] = None
        self._view_key: Optional[str] = None
        self._analyzer: Optional[CharacterAnalyzer] = None
        self._rolls: List[RollOption] = []
        self._roll: Optional[RollOption] = None
        self._option_widgets: Dict[str, Callable[[], object]] = {}
        self._opt_vars: Dict[str, tk.BooleanVar] = {}
        self._bonus_lists: Dict[str, "_BonusDice"] = {}
        self._features_built = False
        self._feature_query = ""
        self._feature_job = None
        self._feature_vars: Dict[str, tk.BooleanVar] = {}
        self._item_vars: Dict[str, tk.BooleanVar] = {}
        self._pending_error = ""

        self._build()
        self._set_mode(state["mode"], first=True)

    # ------------------------------------------------------------------ layout
    def _build(self):
        c = self.theme.get_current_color
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=16)

        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        if self.on_back:
            ctk.CTkButton(head, text="← Game Tools", width=110, height=32, fg_color=c('button_normal'),
                          hover_color=c('button_hover'), command=self.on_back).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(head, text="Dice Analyzer", font=ui_font("title", 28, bold=True)).pack(side="left")
        self.mode_switch = ctk.CTkSegmentedButton(head, values=["Custom", "Character"], command=self._set_mode)
        self.mode_switch.pack(side="right")

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkScrollableFrame(body, fg_color=c('bg_secondary'), corner_radius=10, width=LEFT_WIDTH - 24)
        self.left.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        self.right = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self.right.grid(row=0, column=1, sticky="nsew")
        self.detail = ctk.CTkFrame(self.right, fg_color="transparent")        # one roll in full
        self.overview = ctk.CTkFrame(self.right, fg_color="transparent")      # every save and skill as bars

        self._build_custom_panel()
        self._build_character_panel()
        self._build_results()
        self._build_overview()

    def _heading(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=ui_font("subheading", 14, bold=True),
                     text_color=self.theme.get_current_color('text_label')).pack(anchor="w", pady=(8, 2))

    def _build_custom_panel(self):
        c = self.theme.get_current_color
        self.custom = ctk.CTkFrame(self.left, fg_color="transparent")
        p = self.custom
        self._heading(p, "Roll")
        self.expr = ctk.CTkEntry(p, height=34, font=ui_font("heading", 16),
                                 placeholder_text="2d6+4, 4d6kh3, d20adv+5 ...")
        self.expr.pack(fill="x")
        self.expr.insert(0, self.state["expr"])
        self.expr.bind("<KeyRelease>", lambda _e: self._expr_typed())
        self.expr_hint = ctk.CTkLabel(p, text="", font=ui_font("small", 11), justify="left", anchor="w",
                                      wraplength=LEFT_WIDTH - 60, text_color=c('text_secondary'))
        self.expr_hint.pack(fill="x", pady=(3, 0))

        self.examples = ctk.CTkOptionMenu(p, values=list(EXAMPLES), command=self._example, height=28)
        self.examples.pack(fill="x", pady=(6, 0))

        self._heading(p, "Dice")
        quick = ctk.CTkFrame(p, fg_color="transparent")
        quick.pack(fill="x")
        for sides in COMMON_DICE:
            ctk.CTkButton(quick, text=f"d{sides}", width=48, height=28, fg_color=c('button_normal'),
                          hover_color=c('button_hover'), text_color=c('text_primary'),
                          command=lambda s=sides: self._quick_add(s)).pack(side="left", padx=(0, 4))
        self.rows_frame = ctk.CTkFrame(p, fg_color="transparent")
        self.rows_frame.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(p, text="+ Add another kind of dice", height=28, fg_color=c('button_normal'),
                      hover_color=c('button_hover'), text_color=c('text_primary'),
                      command=lambda: self._quick_add(6, new_row=True)).pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(p, text="Reroll ≤ N rerolls dice showing N or less once (add ! to keep rerolling). "
                             "Min N makes any lower die count as N (Reliable Talent is Min 10 on a d20). "
                             "Highest/Lowest keeps only the n best/worst dice.",
                     font=ui_font("small", 11), text_color=c('text_secondary'), justify="left", anchor="w",
                     wraplength=LEFT_WIDTH - 60).pack(fill="x", pady=(8, 0))

        self._heading(p, "Flat modifier")
        self.flat = ctk.CTkEntry(p, width=90, height=30, justify="center", placeholder_text="+0")
        self.flat.pack(anchor="w")
        self.flat.bind("<KeyRelease>", lambda _e: self._rows_changed())
        self._heading(p, "Whole roll")
        self.twice = ctk.CTkOptionMenu(p, values=["Roll once", "Roll twice, keep higher", "Roll twice, keep lower"],
                                       command=self._twice_changed, height=28)
        self.twice.pack(fill="x")
        self.twice.set(self.state["roll_twice"])

    def _build_character_panel(self):
        c = self.theme.get_current_color
        self.char = ctk.CTkFrame(self.left, fg_color="transparent")
        p = self.char
        self._heading(p, "Character")
        line = ctk.CTkFrame(p, fg_color="transparent")
        line.pack(fill="x")
        self.char_menu = ctk.CTkOptionMenu(line, values=[""], command=self._pick_character, height=30)
        self.char_menu.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(line, text="↻", width=34, height=30, fg_color=c('button_normal'), hover_color=c('button_hover'),
                      text_color=c('text_primary'), command=self._reload_character).pack(side="left", padx=(6, 0))
        self.char_note = ctk.CTkLabel(p, text="", font=ui_font("small", 11), text_color=c('text_secondary'),
                                      justify="left", anchor="w", wraplength=LEFT_WIDTH - 60)
        self.char_note.pack(fill="x", pady=(3, 0))

        # overview: what applies to every bar
        self.overview_left = ctk.CTkFrame(p, fg_color="transparent")
        # detail: one roll, its options
        d = self.detail_left = ctk.CTkFrame(p, fg_color="transparent")
        ctk.CTkButton(d, text="← Saves and skills", height=30, fg_color=c('button_normal'),
                      hover_color=c('button_hover'), text_color=c('text_primary'),
                      command=self._show_overview).pack(fill="x", pady=(10, 0))
        self._heading(d, "Roll")
        self.cat_menu = ctk.CTkOptionMenu(d, values=CATEGORIES, command=self._pick_category, height=30)
        self.cat_menu.pack(fill="x")
        self.roll_menu = ctk.CTkOptionMenu(d, values=[""], command=self._pick_roll, height=30, dynamic_resizing=False)
        self.roll_menu.pack(fill="x", pady=(6, 0))
        self.roll_summary = ctk.CTkLabel(d, text="", font=ui_font("small", 11), text_color=c('text_secondary'),
                                         justify="left", anchor="w", wraplength=LEFT_WIDTH - 60)
        self.roll_summary.pack(fill="x", pady=(3, 0))

        self._heading(d, "Situation")
        self.options_frame = ctk.CTkFrame(d, fg_color="transparent")
        self.options_frame.pack(fill="x")

        self.features_button = ctk.CTkButton(p, text="Character features  ▸", height=30, anchor="w",
                                             fg_color=c('button_normal'), hover_color=c('button_hover'),
                                             text_color=c('text_primary'), command=self._toggle_features)
        self.features_button.pack(fill="x", pady=(14, 0))
        self.features_frame = ctk.CTkFrame(p, fg_color="transparent")
        self._features_open = False

    def _build_results(self):
        c = self.theme.get_current_color
        r = self.detail
        self.result_title = ctk.CTkLabel(r, text="", font=ui_font("heading", 20, bold=True), anchor="w")
        self.result_title.pack(fill="x")
        self.formula_label = ctk.CTkLabel(r, text="", font=ui_font("small", 12), text_color=c('text_secondary'),
                                          anchor="w")
        self.formula_label.pack(fill="x")
        self.views_switch = ctk.CTkSegmentedButton(r, values=["-"], command=self._pick_view)
        self.error_label = ctk.CTkLabel(r, text="", font=ui_font("body"), text_color=c('compare_worse'), anchor="w",
                                        justify="left", wraplength=600)
        self.warn_label = ctk.CTkLabel(r, text="", font=ui_font("small", 12), text_color=c('text_warning'), anchor="w",
                                       justify="left", wraplength=600)

        stats = ctk.CTkFrame(r, fg_color=c('bg_secondary'), corner_radius=10)
        stats.pack(fill="x", pady=(8, 8))
        self._stat_labels: Dict[str, ctk.CTkLabel] = {}
        names = ["Average", "Std. deviation", "Lowest", "Highest", "Median", "Most likely"]
        for i, name in enumerate(names):
            cell = ctk.CTkFrame(stats, fg_color="transparent")
            cell.grid(row=0, column=i, padx=10, pady=8, sticky="w")
            stats.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(cell, text=name, font=ui_font("small", 11), text_color=c('text_secondary')).pack(anchor="w")
            lab = ctk.CTkLabel(cell, text="-", font=ui_font("heading", 18, bold=True))
            lab.pack(anchor="w")
            self._stat_labels[name] = lab
        self.spread_label = ctk.CTkLabel(r, text="", font=ui_font("small", 12), text_color=c('text_secondary'),
                                         anchor="w")
        self.spread_label.pack(fill="x")
        self.facts_label = ctk.CTkLabel(r, text="", font=ui_font("body"), anchor="w", justify="left", wraplength=600)
        self.facts_label.pack(fill="x", pady=(2, 0))

        self.chart = DistributionChart(r, height=320)
        self.chart.pack(fill="x", pady=(8, 6))

        ctl = ctk.CTkFrame(r, fg_color="transparent")
        ctl.pack(fill="x")
        self.cum_switch = ctk.CTkSegmentedButton(ctl, values=["Each total", "This or higher"],
                                                 command=self._cumulative_changed)
        self.cum_switch.pack(side="left")
        self.cum_switch.set("This or higher" if self.state["cumulative"] else "Each total")
        ctk.CTkLabel(ctl, text="Chance to reach").pack(side="left", padx=(18, 6))
        self.target_entry = ctk.CTkEntry(ctl, width=70, height=28, justify="center")
        self.target_entry.pack(side="left")
        self.target_entry.insert(0, str(self.state["target"]))
        self.target_entry.bind("<KeyRelease>", lambda _e: self._target_typed())
        self.target_label = ctk.CTkLabel(r, text="", font=ui_font("body"), anchor="w", justify="left", wraplength=600)
        self.target_label.pack(fill="x", pady=(6, 0))

        self.notes_title = ctk.CTkLabel(r, text="What was counted", font=ui_font("subheading", 14, bold=True),
                                        text_color=c('text_label'), anchor="w")
        self.notes_label = ctk.CTkLabel(r, text="", font=ui_font("small", 12), text_color=c('text_secondary'),
                                        anchor="w", justify="left", wraplength=600)
        self.notes_title.pack(fill="x", pady=(12, 2))
        self.notes_label.pack(fill="x")
        self.right.bind("<Configure>", self._on_right_resize, add="+")

    def _on_right_resize(self, event):
        wrap = max(300, event.width - 40)
        for lab in (self.facts_label, self.target_label, self.notes_label, self.error_label, self.warn_label):
            try:
                lab.configure(wraplength=wrap)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------ modes
    def _set_mode(self, mode: str, first: bool = False):
        self.state["mode"] = mode
        self.mode_switch.set(mode)
        self.custom.pack_forget()
        self.char.pack_forget()
        if mode == "Custom":
            self.custom.pack(fill="both", expand=True, padx=8, pady=6)
            self._rows_from_text(self.expr.get())
            self._rows_changed(from_text=True)
        else:
            if not first:
                self.state["char_view"] = "overview"          # opening Character mode starts at the overview
            self.char.pack(fill="both", expand=True, padx=8, pady=6)
            self._fill_characters()
        self._apply_visibility()
        self._changed(now=True)

    # ------------------------------------------------------------------ character overview
    def _char_view(self) -> str:
        return self.state.get("char_view", "overview")

    def _apply_visibility(self):
        """Show the overview or the detail on each side, for the current mode."""
        character = self.state["mode"] == "Character"
        overview = character and self._char_view() == "overview"
        self.overview.pack_forget()
        self.detail.pack_forget()
        (self.overview if overview else self.detail).pack(fill="both", expand=True)
        self.overview_left.pack_forget()
        self.detail_left.pack_forget()
        if character:
            (self.overview_left if overview else self.detail_left).pack(fill="x", before=self.features_button)

    def _build_overview(self):
        c = self.theme.get_current_color
        o = self.overview
        self.ov_title = ctk.CTkLabel(o, text="", font=ui_font("heading", 20, bold=True), anchor="w")
        self.ov_title.pack(fill="x")
        bar = ctk.CTkFrame(o, fg_color="transparent")
        bar.pack(fill="x", pady=(6, 6))
        ctk.CTkLabel(bar, text="Show the", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.metric_switch = ctk.CTkSegmentedButton(bar, values=["Average", "Median"], command=self._metric_changed)
        self.metric_switch.pack(side="left")
        self.metric_switch.set(self.state.setdefault("metric", "Average"))
        self.ov_legend = ctk.CTkLabel(bar, text="● proficient   ◆ expertise", font=ui_font("small", 12),
                                      text_color=c('text_secondary'))
        self.ov_legend.pack(side="right")
        ctk.CTkLabel(o, text="Other rolls", font=ui_font("subheading", 14, bold=True), anchor="w",
                     text_color=c('text_label')).pack(fill="x", pady=(8, 4))
        self.ov_buttons = ctk.CTkFrame(o, fg_color="transparent")
        self.ov_buttons.pack(fill="x", pady=(0, 10))
        self._ov_button_widgets: Dict[str, ctk.CTkButton] = {}
        for key in ("Attacks", "Spells", "Concentration", "Initiative", "Checks"):
            self._ov_button_widgets[key] = ctk.CTkButton(
                self.ov_buttons, text=key, height=34, width=170, fg_color=c('accent_primary'),
                hover_color=c('accent_hover'), command=lambda k=key: self._open_group(k))
        self.ov_chart = BarListChart(o, on_click=self._open_roll, height=400)
        self.ov_chart.pack(fill="x")

    def _build_overview_left(self):
        """What applies to every bar: the way you roll, Rage, Bladesong (only what the character has)."""
        for child in self.overview_left.winfo_children():
            destroy_later(child)
        c = self.theme.get_current_color
        ov = self.state.setdefault("overview", {})
        p = self.overview_left
        self._heading(p, "Situation for every bar")
        line = ctk.CTkFrame(p, fg_color="transparent")
        line.pack(fill="x", pady=2)
        ctk.CTkLabel(line, text="Rolling with", font=ui_font("small", 12)).pack(side="left")
        menu = ctk.CTkOptionMenu(line, values=list(MODES), width=150, height=26,
                                 command=lambda v: self._overview_option("mode", v))
        menu.set(ov.get("mode", "Normal"))
        menu.pack(side="right")
        ctx = self._analyzer.ctx if self._analyzer else None
        self._ov_vars = {}
        toggles = []
        if ctx is not None and ctx.lvl("Barbarian"):
            toggles.append(("rage", "Raging", "Advantage on Strength checks and saves; with Acrobatics, Intimidation, "
                                              "Perception, Stealth and Survival Strength is used instead (level 3)."))
        if ctx is not None and ctx.has("bladesong"):
            toggles.append(("bladesong", "Bladesong active", "Advantage on Acrobatics (the concentration bonus is "
                                                             "under Other rolls)."))
        for key, label, helptext in toggles:
            var = tk.BooleanVar(value=bool(ov.get(key)))
            self._ov_vars[key] = var
            ctk.CTkCheckBox(p, text=label, variable=var, checkbox_width=20, checkbox_height=20,
                            command=lambda k=key: self._overview_option(k, self._ov_vars[k].get())
                            ).pack(anchor="w", pady=(4, 0))
            ctk.CTkLabel(p, text=helptext, font=ui_font("small", 11), text_color=c('text_secondary'), anchor="w",
                         justify="left", wraplength=LEFT_WIDTH - 90).pack(anchor="w", padx=(26, 0))
        ctk.CTkLabel(p, text="Click a bar (or a button) to open that roll with every option, bonus dice and the "
                             "full graph.", font=ui_font("small", 11), text_color=c('text_secondary'), anchor="w",
                     justify="left", wraplength=LEFT_WIDTH - 60).pack(anchor="w", pady=(12, 0))

    def _overview_option(self, key: str, value):
        self.state.setdefault("overview", {})[key] = value
        self._refresh_overview()

    def _metric_changed(self, value: str):
        self.state["metric"] = value
        self._refresh_overview()

    def _refresh_overview(self):
        if self._analyzer is None:
            self.ov_title.configure(text="No character to show")
            self.ov_chart.set_rows([])
            for b in self._ov_button_widgets.values():
                b.pack_forget()
            return
        ov = dict(self.state.get("overview", {}))
        use_median = self.state.get("metric", "Average") == "Median"
        saves: List[BarRow] = []
        skills: List[BarRow] = []
        marks = {0: "", 1: "●", 2: "◆"}
        for r in self._rolls:
            if r.group == "Saves" and not r.meta.get("concentration"):
                bucket, label = saves, r.name.replace(" save", "")
            elif r.group == "Skills":
                bucket, label = skills, f"{r.name} ({r.meta.get('ability', '')})"
            else:
                continue
            try:
                dist = r.analyze(ov).views[0].dist
            except Exception:
                continue
            lo, hi = dist.support()
            mean, median = dist.mean(), dist.median()
            value = float(median) if use_median else mean
            hint = (f"average {mean:.1f}  •  median {median}  •  range {lo} to {hi}" if use_median
                    else f"median {median}  •  range {lo} to {hi}")
            bucket.append(BarRow(r.key, label, value, marks.get(int(r.meta.get("level", 0)), ""), hint))
        self.ov_chart.set_rows([("Saving throws", saves), ("Skills", skills)],
                               "median" if use_median else "average")
        self.ov_title.configure(text=f"{self.state.get('character', '')}: saving throws and skills")
        counts = {k: sum(1 for r in self._rolls if r.group == k) for k in ("Attacks", "Spells")}
        wanted = []
        if counts["Attacks"]:
            wanted.append(("Attacks", f"⚔  Attacks ({counts['Attacks']})"))
        if counts["Spells"]:
            wanted.append(("Spells", f"✦  Spells ({counts['Spells']})"))
        if any(r.meta.get("concentration") for r in self._rolls):
            wanted.append(("Concentration", "◎  Concentration save"))
        wanted.append(("Initiative", "⚡ Initiative"))
        wanted.append(("Checks", "Ability checks"))
        for b in self._ov_button_widgets.values():
            b.pack_forget()
        for key, text in wanted:
            self._ov_button_widgets[key].configure(text=text)
            self._ov_button_widgets[key].pack(side="left", padx=(0, 8), pady=2)

    def _open_group(self, key: str):
        """One of the buttons under the bars."""
        if key == "Concentration":
            self._open_roll("save:CON:concentration")
        elif key == "Initiative":
            self._open_roll("initiative")
        else:
            first = next((r for r in self._rolls if r.group == key and r.key != "initiative"), None)
            if first:
                self._open_roll(first.key)

    def _open_roll(self, key: str):
        roll = next((r for r in self._rolls if r.key == key), None)
        if roll is None:
            return
        # what was set for every bar carries over into the roll's own options
        saved = self.state["options"].setdefault(f"{self.state.get('character')}|{key}", {})
        wanted = {o.key for o in roll.options}
        for k, v in self.state.get("overview", {}).items():
            if k in wanted:
                saved[k] = v
        self.state["roll"] = key
        self.state["category"] = roll.group
        self.state["char_view"] = "detail"
        self.cat_menu.set(roll.group)
        self._pick_category(roll.group, keep_roll=True)
        self._apply_visibility()
        self._changed(now=True)

    def _show_overview(self):
        self.state["char_view"] = "overview"
        self._apply_visibility()
        self._refresh_overview()

    # ------------------------------------------------------------------ custom mode
    def _expr_typed(self):
        if self._syncing:
            return
        text = self.expr.get()
        self.state["expr"] = text
        try:
            expr = parse_expression(text)
        except DiceError as e:
            self.expr_hint.configure(text=str(e), text_color=self.theme.get_current_color('compare_worse'))
            self._changed()
            return
        self.expr_hint.configure(text="", text_color=self.theme.get_current_color('text_secondary'))
        self._rows_from_expression(expr)
        self._changed()

    def _rows_from_text(self, text: str):
        try:
            expr = parse_expression(text)
        except DiceError as e:
            self.expr_hint.configure(text=str(e), text_color=self.theme.get_current_color('compare_worse'))
            return
        self._rows_from_expression(expr)

    def _rows_from_expression(self, expr: Expression):
        self._syncing = True
        try:
            while len(self._rows) > len(expr.terms):
                row = self._rows.pop()
                destroy_later(row.frame)
            for i, term in enumerate(expr.terms[:MAX_ROWS]):
                if i >= len(self._rows):
                    self._add_row()
                self._rows[i].load(term)
            self.flat.delete(0, "end")
            if expr.flat:
                self.flat.insert(0, f"{expr.flat:+d}")
            if len(expr.terms) > MAX_ROWS:
                self.expr_hint.configure(text=f"The builder shows the first {MAX_ROWS} kinds of dice, "
                                              f"the whole expression is still used.")
        finally:
            self._syncing = False

    def _add_row(self) -> _Row:
        row = _Row(self, self.rows_frame)
        row.frame.pack(fill="x", pady=(0, 6))
        self._rows.append(row)
        return row

    def _quick_add(self, sides: int, new_row: bool = False):
        if len(self._rows) >= MAX_ROWS:
            return
        if not new_row:
            for row in self._rows:
                try:
                    plain = (row.sides.get().strip() == str(sides) and not row._negative and not row.reroll.get().strip()
                             and not row.minimum.get().strip() and row.kind.get() == "Normal"
                             and row.keep.get() == KEEPS[0])
                    if plain:
                        more = int(row.count.get() or 1) + 1
                        row.count.delete(0, "end")
                        row.count.insert(0, str(more))
                        self._rows_changed()
                        return
                except ValueError:
                    pass
        row = self._add_row()
        row.sides.delete(0, "end")
        row.sides.insert(0, str(sides))
        self._rows_changed()

    def _remove_row(self, row: _Row):
        if row in self._rows:
            self._rows.remove(row)
            destroy_later(row.frame)
        self._rows_changed()

    def _rows_changed(self, from_text: bool = False):
        """Rows -> expression text -> new calculation."""
        if self._syncing:
            return
        try:
            expr = Expression([r.term() for r in self._rows], self._flat_value())
        except DiceError as e:
            self.expr_hint.configure(text=str(e), text_color=self.theme.get_current_color('compare_worse'))
            self._pending_error = str(e)
            self._changed()
            return
        self._pending_error = ""
        self.expr_hint.configure(text="", text_color=self.theme.get_current_color('text_secondary'))
        self._syncing = True
        try:
            if not from_text:
                self.expr.delete(0, "end")
                self.expr.insert(0, expr.text())
                self.state["expr"] = expr.text()
        finally:
            self._syncing = False
        self._changed()

    def _flat_value(self) -> int:
        raw = self.flat.get().strip().replace(" ", "").replace("−", "-")
        if not raw:
            return 0
        try:
            return int(raw)
        except ValueError:
            raise DiceError("The flat modifier must be a whole number such as +4 or -12.")

    def _example(self, label: str):
        text = EXAMPLES.get(label, "")
        if not text:
            return
        self.examples.set("Examples...")
        self.expr.delete(0, "end")
        self.expr.insert(0, text)
        self._expr_typed()

    def _twice_changed(self, value: str):
        self.state["roll_twice"] = value
        self._changed()

    # ------------------------------------------------------------------ character mode
    def _fill_characters(self):
        names = self.character_names()
        if not names:
            self.char_menu.configure(values=["(no characters)"])
            self.char_menu.set("(no characters)")
            self.char_note.configure(text="Create a character first - its sheet is what this analyzes.")
            self._analyzer, self._rolls, self._roll = None, [], None
            self._clear_options()
            self.roll_menu.configure(values=[""])
            self.roll_menu.set("")
            return
        self.char_menu.configure(values=names)
        chosen = self.state.get("character")
        if chosen not in names:
            chosen = names[0]
        self.char_menu.set(chosen)
        self._pick_character(chosen)

    def _pick_character(self, name: str, keep_roll: bool = False):
        self.state["character"] = name
        loaded = self.load_character(name)
        if not loaded:
            self.char_note.configure(text="That character could not be loaded.")
            return
        character, sheet = loaded
        manual = set(self.state["manual"].get(name, []))
        off = set(self.state.setdefault("items_off", {}).get(name, []))
        self._analyzer = CharacterAnalyzer(character, sheet, self.lookups, manual, off)
        self._rolls = self._analyzer.rolls()
        levels = ", ".join(f"{cl.get_class_name()} {cl.level}" for cl in character.classes) or "no class"
        self.char_note.configure(text=f"{levels}  •  proficiency +{sheet.proficiency_bonus}  •  "
                                      + ("this character has no sheet yet, so ability scores are all 10"
                                         if getattr(sheet, "_unsaved", False)
                                         else "numbers come straight from the sheet"))
        self._features_built = False
        if self._features_open:
            self._build_features()
        by_cat = {c: [r for r in self._rolls if r.group == c] for c in CATEGORIES}
        cats = [c for c in CATEGORIES if by_cat[c]]
        self.cat_menu.configure(values=cats)
        category = self.state.get("category")
        if category not in cats:
            category = next((c for c in ("Attacks", "Spells") if by_cat[c]), "Skills")
        self.cat_menu.set(category)
        self._pick_category(category, keep_roll=True)
        self._build_overview_left()
        if self._char_view() == "overview":
            self._refresh_overview()

    def _reload_character(self):
        name = self.state.get("character")
        if name:
            self._pick_character(name)
            self._changed(now=True)

    def _roll_label(self, r: RollOption) -> str:
        return f"{r.name}   ({r.summary})"

    def _pick_category(self, category: str, keep_roll: bool = False):
        self.state["category"] = category
        rolls = [r for r in self._rolls if r.group == category]
        labels = [self._roll_label(r) for r in rolls]
        self.roll_menu.configure(values=labels or [""])
        wanted = self.state.get("roll")
        pick = next((r for r in rolls if r.key == wanted), rolls[0] if rolls else None)
        if pick:
            self.roll_menu.set(self._roll_label(pick))
            self._select_roll(pick)
        if not keep_roll:
            self._changed(now=True)

    def _pick_roll(self, label: str):
        for r in self._rolls:
            if self._roll_label(r) == label and r.group == self.state.get("category"):
                self._select_roll(r)
                self._changed(now=True)
                return

    def _select_roll(self, roll: RollOption):
        self._roll = roll
        self.state["roll"] = roll.key
        self.roll_summary.configure(text=f"{roll.group}: {roll.name}  {roll.summary}")
        if self._char_view() == "detail":
            self._build_options(roll)

    def _clear_options(self):
        for child in self.options_frame.winfo_children():
            destroy_later(child)
        self._option_widgets = {}
        self._opt_vars = {}
        self._bonus_lists = {}

    def _build_options(self, roll: RollOption):
        self._clear_options()
        saved: Dict[str, object] = self.state["options"].setdefault(
            f"{self.state.get('character')}|{roll.key}", {})
        # the generic "Chance to reach" box drives the target of checks and saves, so those do not repeat it
        hide_target = roll.group in ("Skills", "Checks", "Saves")
        c = self.theme.get_current_color
        for opt in roll.options:
            if opt.key == "target" and hide_target:
                continue
            value = saved.get(opt.key, opt.default)
            wrap = ctk.CTkFrame(self.options_frame, fg_color="transparent")
            wrap.pack(fill="x", pady=2)
            row = ctk.CTkFrame(wrap, fg_color="transparent")
            row.pack(fill="x")
            if opt.kind == "bool":
                var = tk.BooleanVar(value=bool(value))
                ctk.CTkCheckBox(row, text=opt.label, variable=var, command=lambda o=opt: self._option_changed(o),
                                checkbox_width=20, checkbox_height=20).pack(anchor="w")
                self._option_widgets[opt.key] = var.get
                self._opt_vars[opt.key] = var
            elif opt.kind == "dice":
                ctk.CTkLabel(row, text=opt.label, font=ui_font("small", 12), anchor="w").pack(anchor="w")
                dice = _BonusDice(self, wrap, value if isinstance(value, list) else [],
                                  lambda o=opt: self._option_changed(o))
                dice.frame.pack(fill="x")
                self._option_widgets[opt.key] = dice.value
                self._bonus_lists[opt.key] = dice
            elif opt.kind == "choice":
                ctk.CTkLabel(row, text=opt.label, font=ui_font("small", 12), anchor="w").pack(side="left")
                menu = ctk.CTkOptionMenu(row, values=opt.choices, width=110, height=26,
                                         command=lambda _v, o=opt: self._option_changed(o))
                menu.set(str(value) if str(value) in opt.choices else opt.choices[0])
                menu.pack(side="right")
                self._option_widgets[opt.key] = menu.get
            else:
                ctk.CTkLabel(row, text=opt.label, font=ui_font("small", 12), anchor="w").pack(side="left")
                entry = ctk.CTkEntry(row, width=(150 if opt.kind == "text" else 64), height=26, justify="center")
                entry.insert(0, "" if value is None or value is False else str(value))
                entry.pack(side="right")
                entry.bind("<KeyRelease>", lambda _e, o=opt: self._option_changed(o))
                self._option_widgets[opt.key] = entry.get
            if opt.help:
                ctk.CTkLabel(wrap, text=opt.help, font=ui_font("small", 11), text_color=c('text_secondary'),
                             anchor="w", justify="left", wraplength=LEFT_WIDTH - 90).pack(anchor="w", padx=(26, 0))
        if not roll.options:
            ctk.CTkLabel(self.options_frame, text="Nothing to choose for this roll.", font=ui_font("small", 12),
                         text_color=c('text_secondary')).pack(anchor="w")

    def _option_changed(self, opt: Option):
        self._changed()

    def _collect_options(self) -> Dict[str, object]:
        out: Dict[str, object] = {}
        for opt in (self._roll.options if self._roll else []):
            getter = self._option_widgets.get(opt.key)
            if getter is None:
                continue
            raw = getter()
            if opt.kind == "int":
                try:
                    out[opt.key] = int(str(raw).strip().replace("−", "-") or 0)
                except ValueError:
                    raise DiceError(f"'{opt.label}' must be a whole number.")
            elif opt.kind == "bool":
                out[opt.key] = bool(raw)
            else:
                out[opt.key] = raw
        if self._roll:
            self.state["options"][f"{self.state.get('character')}|{self._roll.key}"] = dict(out)
        return out

    # ---- features
    def _toggle_features(self):
        self._features_open = not self._features_open
        self.features_button.configure(text="Character features  " + ("▾" if self._features_open else "▸"))
        if self._features_open:
            if not self._features_built:
                self._build_features()
            self.features_frame.pack(fill="x", pady=(6, 0))
        else:
            self.features_frame.pack_forget()

    def _build_features(self):
        for child in self.features_frame.winfo_children():
            destroy_later(child)
        self._features_built = True
        self._feature_vars = {}
        self._item_vars = {}
        if self._analyzer is None:
            return
        c = self.theme.get_current_color
        self.feature_search = ctk.CTkEntry(self.features_frame, height=30,
                                           placeholder_text="Search features and items...")
        self.feature_search.pack(fill="x", pady=(0, 4))
        if self._feature_query:
            self.feature_search.insert(0, self._feature_query)
        self.feature_search.bind("<KeyRelease>", lambda _e: self._feature_search_typed())
        self.features_body = ctk.CTkFrame(self.features_frame, fg_color="transparent")
        self.features_body.pack(fill="x")
        self._render_features_body()

    def _feature_search_typed(self):
        self._feature_query = self.feature_search.get().strip()
        if self._feature_job is not None:
            try:
                self.after_cancel(self._feature_job)
            except (tk.TclError, ValueError):
                pass
        self._feature_job = self.after(200, self._render_features_body)

    def _render_features_body(self):
        """The lists under the search box: what was found, what can be ticked, and the linked items - narrowed to what
        matches the search. With nothing typed it is the short list of things a sheet cannot show; with a search it
        covers every feature the analyzer knows."""
        self._feature_job = None
        if self._analyzer is None:
            return
        self._feature_vars = {}
        self._item_vars = {}
        for child in self.features_body.winfo_children():
            destroy_later(child)
        c = self.theme.get_current_color
        wrap = LEFT_WIDTH - 60
        q = self._feature_query.lower()
        body = self.features_body
        report = self._analyzer.feature_report(all_features=bool(q))
        match = (lambda text: q in text.lower()) if q else (lambda text: True)

        def heading(text):
            ctk.CTkLabel(body, text=text, font=ui_font("small", 12, bold=True), anchor="w",
                         text_color=c('text_label')).pack(fill="x", pady=(8, 2))

        shown = 0
        found = [label for _fid, label, source in report if source == "sheet" and match(label)]
        if found or not q:
            heading("Found on the sheet (applied automatically)")
            ctk.CTkLabel(body, text=("✓ " + "   ✓ ".join(found)) if found else "Nothing the analyzer knows.",
                         font=ui_font("small", 11), anchor="w", justify="left", wraplength=wrap,
                         text_color=c('compare_better' if found else 'text_secondary')).pack(fill="x")
            shown += len(found)
        manual = [(fid, label, source) for fid, label, source in report if source != "sheet" and match(label)]
        limit = 40
        if manual:
            heading("Tick any the sheet does not show" if not q else "Features you can tick")
            for fid, label, source in manual[:limit]:
                var = tk.BooleanVar(value=(source == "manual"))
                self._feature_vars[fid] = var
                ctk.CTkCheckBox(body, text=label, variable=var, checkbox_width=18, checkbox_height=18,
                                command=self._features_changed).pack(anchor="w", pady=1)
            if len(manual) > limit:
                ctk.CTkLabel(body, text=f"{len(manual) - limit} more match: type a little more to narrow it down.",
                             font=ui_font("small", 11), anchor="w", text_color=c('text_secondary')).pack(fill="x")
            shown += min(len(manual), limit)
        items = [i for i in self._analyzer.item_report() if match(i[0]) or match(i[3])]
        if items or not q:
            heading("Linked magic items")
            if not items:
                ctk.CTkLabel(body, text="None of the sheet's magic items change rolls.", font=ui_font("small", 11),
                             anchor="w", justify="left", wraplength=wrap, text_color=c('text_secondary')).pack(fill="x")
        for name, counts, reason, what in items:
            var = tk.BooleanVar(value=counts)
            self._item_vars[name] = var
            ctk.CTkCheckBox(body, text=f"{name}" + (f"  ({reason})" if reason else ""), variable=var,
                            checkbox_width=18, checkbox_height=18, command=self._items_changed,
                            state="disabled" if reason else "normal").pack(anchor="w", pady=(2, 0))
            ctk.CTkLabel(body, text=what, font=ui_font("small", 11), anchor="w", justify="left",
                         wraplength=wrap - 26, text_color=c('text_secondary')).pack(anchor="w", padx=(26, 0))
            shown += 1
        if q and not shown:
            ctk.CTkLabel(body, text="Nothing matches that search.", font=ui_font("small", 11), anchor="w",
                         text_color=c('text_secondary')).pack(fill="x", pady=(6, 0))

    def _items_changed(self):
        name = self.state.get("character")
        usable = {n for n, _counts, reason, _what in self._analyzer.item_report() if not reason}
        off = set(self.state.setdefault("items_off", {}).get(name, []))
        for n, var in self._item_vars.items():              # only the rows shown can change (the search may hide some)
            if n in usable:
                (off.discard if var.get() else off.add)(n)
        self.state["items_off"][name] = sorted(off)
        self._pick_character(name)
        self._changed(now=True)

    def _features_changed(self):
        name = self.state.get("character")
        ticked = set(self.state["manual"].get(name, []))
        for fid, var in self._feature_vars.items():
            (ticked.add if var.get() else ticked.discard)(fid)
        self.state["manual"][name] = sorted(ticked)
        self._pick_character(name)
        self._changed(now=True)

    # ------------------------------------------------------------------ results
    def _cumulative_changed(self, value: str):
        self.state["cumulative"] = value == "This or higher"
        self._show()

    def _target_typed(self):
        try:
            self.state["target"] = int(self.target_entry.get().strip().replace("−", "-"))
        except ValueError:
            return
        if self.state["mode"] == "Character":
            self._changed()
        else:
            self._show()

    def _pick_view(self, title: str):
        if self._analysis:
            for v in self._analysis.views:
                if v.title == title:
                    self._view_key = v.key
        self._show()

    def _changed(self, now: bool = False):
        self._debounce(self._compute, DEBOUNCE_MS, now)

    def _work_error_text(self, exc: Exception) -> str:
        if isinstance(exc, DiceError):
            return str(exc)
        # a bug must not leave the page stuck on "Calculating"
        return f"Something went wrong working that out ({type(exc).__name__}: {exc})."

    def _on_work_done(self, analysis: Analysis):
        self._analysis = analysis
        keys = [v.key for v in analysis.views]
        if self._view_key not in keys:
            self._view_key = keys[0]
        self._show()

    def _on_work_failed(self, message: str):
        self._show_error(message)

    def _compute(self):
        self._job = None
        if self.state["mode"] == "Character" and self._char_view() == "overview":
            self._refresh_overview()
            return
        try:
            job = self._make_job()
        except DiceError as e:
            self._show_error(str(e))
            return
        if job is None:
            return
        self.result_title.configure(text="Calculating...")
        self._run_in_thread(job)

    def _make_job(self) -> Optional[Callable[[], Analysis]]:
        if self.state["mode"] == "Custom":
            if self._pending_error:
                raise DiceError(self._pending_error)
            expr = parse_expression(self.expr.get())
            twice = self.twice.get()
            expr.roll_twice = "high" if "higher" in twice else "low" if "lower" in twice else ""

            def run() -> Analysis:
                dist = expr.distribution()
                text = expr.text() + (" (roll twice, keep higher)" if expr.roll_twice == "high" else
                                      " (roll twice, keep lower)" if expr.roll_twice == "low" else "")
                return Analysis(text, [View("roll", "Result", dist)])
            return run
        if self._roll is None:
            raise DiceError("Pick a character with something to roll." if not self._rolls
                            else "Pick something to roll.")
        state = self._collect_options()
        if "target" not in state:
            state["target"] = self.state["target"]
        roll = self._roll
        return lambda: roll.analyze(state)

    def _show_error(self, message: str):
        self._analysis = None
        self.error_label.configure(text=message)
        self.error_label.pack(fill="x", after=self.formula_label)
        self.warn_label.pack_forget()
        self.result_title.configure(text="")
        self.formula_label.configure(text="")
        self.chart.set_dist(None)
        for lab in self._stat_labels.values():
            lab.configure(text="-")
        for lab in (self.spread_label, self.facts_label, self.target_label, self.notes_label):
            lab.configure(text="")
        self.views_switch.pack_forget()

    def _current_view(self) -> Optional[View]:
        if not self._analysis:
            return None
        for v in self._analysis.views:
            if v.key == self._view_key:
                return v
        return self._analysis.views[0]

    def _show(self):
        a = self._analysis
        view = self._current_view()
        if a is None or view is None:
            return
        titles = [v.title for v in a.views]
        if len(titles) > 1:
            self.views_switch.configure(values=titles)
            self.views_switch.set(view.title)
            self.views_switch.pack(fill="x", pady=(6, 0), after=self.formula_label)
        else:
            self.views_switch.pack_forget()
        self.result_title.configure(text=view.title if self.state["mode"] == "Character" else "Distribution")
        self.formula_label.configure(text=a.formula)

        dist = view.dist
        s = summarize(dist)
        unit_dec = 2 if (s.high - s.low) < 400 else 1
        self._stat_labels["Average"].configure(text=f"{s.mean:.{unit_dec}f}")
        self._stat_labels["Std. deviation"].configure(text=f"{s.std:.{unit_dec}f}")
        self._stat_labels["Lowest"].configure(text=f"{s.low:,}")
        self._stat_labels["Highest"].configure(text=f"{s.high:,}")
        self._stat_labels["Median"].configure(text=f"{s.median:,}")
        modes = dist.modes()
        mode = (", ".join(f"{m:,}" for m in modes) if len(modes) <= 2
                else "all equal" if len(modes) == s.high - s.low + 1 else "several")
        self._stat_labels["Most likely"].configure(text=mode)
        self.spread_label.configure(
            text=f"Middle 50% of results: {s.percentiles[25]:,} to {s.percentiles[75]:,}   •   "
                 f"Middle 80%: {s.percentiles[10]:,} to {s.percentiles[90]:,}")
        facts = "   •   ".join(f"{k}: {v}" for k, v in view.facts)
        self.facts_label.configure(text=facts)

        target = self.state["target"]
        t = int(target)
        self.target_label.configure(
            text=f"{t:,} or more: {percent_text(dist.at_least(t))}   •   less than {t:,}: "
                 f"{percent_text(1 - dist.at_least(t))}   •   exactly {t:,}: {percent_text(dist.pmf(t))}")
        self.chart.set_dist(dist, cumulative=self.state["cumulative"], target=t, unit=view.unit)

        notes = list(a.notes)
        self.notes_label.configure(text="\n".join(f"• {n}" for n in notes) if notes else "Just the dice.")
        warnings = list(a.warnings)
        if dist.approx:
            warnings.append("This is so large (or complicated) that the chart is an approximation - the average and "
                            "spread are accurate, the exact odds of individual totals are close but not exact.")
        if warnings:
            self.warn_label.configure(text="\n".join(warnings))
            self.warn_label.pack(fill="x", pady=(4, 0), after=self.formula_label)
        else:
            self.warn_label.pack_forget()
        self.error_label.pack_forget()

    # ------------------------------------------------------------------ lifecycle