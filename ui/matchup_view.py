"""Matchup page: pick two creatures or characters and see how a one-on-one fight between them is likely to go.

Each side can be a character (from the Characters page), a monster (from the Monsters collection, searchable) or a
creature typed in by hand. The fight itself is worked out in ``matchup``; this page only collects the two sides and
shows the odds, the damage each does to the other, the spells of casters (average damage per spell level and per slot
level) and the tide turners - the things averages cannot capture.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import matchup as M
from theme import get_theme_manager
from typography import ui_font
from ui.lazy_destroy import destroy_later

TRIALS = 4000
DEBOUNCE_MS = 450
KINDS = ["Character", "Monster", "Custom"]


class WinBar(tk.Canvas):
    """The chance each side wins, as one bar."""

    def __init__(self, parent, **kw):
        self.theme = get_theme_manager()
        super().__init__(parent, height=34, highlightthickness=0, bd=0, bg=self._c("bg_secondary"), **kw)
        self.values = (0.0, 0.0, 0.0)
        self.names = ("A", "B")
        self.bind("<Configure>", lambda e: self.draw())
        self.theme.add_listener(self._on_theme)
        self.bind("<Destroy>", self._gone, add="+")

    def _c(self, role: str) -> str:
        return str(self.theme.get_current_color(role))

    def _on_theme(self):
        try:
            self.configure(bg=self._c("bg_secondary"))
            self.draw()
        except tk.TclError:
            pass

    def _gone(self, event):
        if event.widget is self:
            self.theme.remove_listener(self._on_theme)

    def set(self, a: float, b: float, draw: float, names):
        self.values, self.names = (a, b, draw), names
        self.draw()

    def draw(self):
        try:
            self.delete("all")
            w = self.winfo_width()
        except tk.TclError:
            return
        if w < 50:
            return
        a, b, d = self.values
        x = 4
        usable = w - 8
        for value, color, text in ((a, self._c("accent_primary"), self.names[0]),
                                   (d, self._c("bg_tertiary"), "draw"),
                                   (b, self._c("text_label"), self.names[1])):
            width = usable * value
            if width < 1:
                continue
            self.create_rectangle(x, 4, x + width, 30, fill=color, outline="")
            label = f"{text} {value * 100:.0f}%" if width > 90 else (f"{value * 100:.0f}%" if width > 28 else "")
            if label:
                self.create_text(x + width / 2, 17, text=label, fill=self._c("text_on_accent") if color != self._c(
                    "bg_tertiary") else self._c("text_primary"), font=ui_font("small", 12, bold=True))
            x += width


class _SideCard(ctk.CTkFrame):
    """The picker for one combatant."""

    def __init__(self, view: "MatchupView", parent, key: str):
        super().__init__(parent, fg_color=view.theme.get_current_color("bg_secondary"), corner_radius=10)
        self.view, self.key = view, key
        self.theme = view.theme
        c = self.theme.get_current_color
        st = view.state.setdefault(key, {})
        st.setdefault("kind", "Character")
        self.state = st
        ctk.CTkLabel(self, text="Creature A" if key == "a" else "Creature B",
                     font=ui_font("subheading", 14, bold=True), text_color=c("text_label")).pack(anchor="w", padx=12,
                                                                                                  pady=(10, 2))
        self.kind = ctk.CTkSegmentedButton(self, values=KINDS, command=self._kind_changed)
        self.kind.pack(fill="x", padx=12, pady=(0, 6))
        self.kind.set(st["kind"])
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="x", padx=12, pady=(0, 6))
        self.info = ctk.CTkLabel(self, text="", font=ui_font("small", 12), text_color=c("text_secondary"),
                                 justify="left", anchor="w", wraplength=420)
        self.info.pack(fill="x", padx=12, pady=(0, 10))
        self._widgets: Dict[str, object] = {}
        self._build_body()

    # ---- layout per kind
    def _kind_changed(self, kind: str):
        self.state["kind"] = kind
        self._build_body()
        self.view.changed()

    def _clear(self):
        for child in self.body.winfo_children():
            destroy_later(child)
        self._widgets = {}

    def _entry(self, parent, key, label, width=80, default="", placeholder=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)
        ctk.CTkLabel(row, text=label, width=130, anchor="w", font=ui_font("small", 12)).pack(side="left")
        e = ctk.CTkEntry(row, width=width, height=26, placeholder_text=placeholder or None, justify="center")
        value = self.state.get(key, default)
        if value not in (None, ""):
            e.insert(0, str(value))
        e.pack(side="left", fill="x" if width > 150 else None, expand=width > 150)
        e.bind("<KeyRelease>", lambda _e, k=key: self._typed(k))
        self._widgets[key] = e
        return e

    def _typed(self, key):
        self.state[key] = self._widgets[key].get()
        self.view.changed()

    def _check(self, key, label, default=False):
        var = tk.BooleanVar(value=bool(self.state.get(key, default)))
        ctk.CTkCheckBox(self.body, text=label, variable=var, checkbox_width=18, checkbox_height=18,
                        command=lambda k=key, v=var: self._flag(k, v)).pack(anchor="w", pady=1)
        self._widgets[key] = var

    def _flag(self, key, var):
        self.state[key] = bool(var.get())
        self.view.changed()

    def _defences(self):
        self._entry(self.body, "resist", "Resistances", 220, placeholder="fire, cold")
        self._entry(self.body, "immune", "Damage immunities", 220, placeholder="poison")
        self._entry(self.body, "cond_immune", "Condition immunities", 220, placeholder="Charmed, Frightened")

    def _build_body(self):
        self._clear()
        kind = self.state["kind"]
        if kind == "Character":
            search = ctk.CTkEntry(self.body, height=28, placeholder_text="Search characters...")
            search.pack(fill="x")
            if self.state.get("character_query"):
                search.insert(0, self.state["character_query"])
            search.bind("<KeyRelease>", lambda _e: self._character_search())
            menu = ctk.CTkOptionMenu(self.body, values=["-"], height=28, command=self._character_picked,
                                     dynamic_resizing=False)
            menu.pack(fill="x", pady=(4, 0))
            self._widgets.update(character_search=search, character_menu=menu)
            self._character_search(initial=True)
            hp =ctk.CTkSegmentedButton(self.body, values=["Max HP", "Current HP"], command=self._hp_mode)
            hp.pack(fill="x", pady=(6, 2))
            hp.set(self.state.get("hp_mode", "Max HP"))
            self._check("boosts", "Use class damage boosts (Sneak Attack, Rage)", True)
            self._check("use_slots", "Use spell slots", True)
            self._check("raging", "Raging (Barbarian): resists weapon damage", False)
            self._defences()
        elif kind == "Monster":
            search = ctk.CTkEntry(self.body, height=28, placeholder_text="Search monsters...")
            search.pack(fill="x")
            if self.state.get("monster_query"):
                search.insert(0, self.state["monster_query"])
            search.bind("<KeyRelease>", lambda _e: self._monster_search())
            menu = ctk.CTkOptionMenu(self.body, values=["-"], height=28, command=self._monster_picked,
                                     dynamic_resizing=False)
            menu.pack(fill="x", pady=(4, 0))
            self._widgets.update(monster_search=search, monster_menu=menu)
            self._monster_search(initial=True)
            self._defences()
        else:
            self._entry(self.body, "c_name", "Name", 180, "Custom creature")
            self._entry(self.body, "c_ac", "Armor Class", 60, "14")
            self._entry(self.body, "c_hp", "Hit points", 60, "40")
            self._entry(self.body, "c_bonus", "Attack bonus", 60, "5")
            self._entry(self.body, "c_damage", "Damage per hit", 100, "1d8+3", "2d6+4")
            self._entry(self.body, "c_attacks", "Attacks per round", 60, "2")
            self._entry(self.body, "c_type", "Damage type", 100, "slashing")
            self._entry(self.body, "c_speed", "Speed (ft.)", 60, "30")
            self._entry(self.body, "c_range", "Range (ft., 0 = melee)", 60, "0")
            self._defences()
        self.refresh_info()

    # ---- characters and monsters
    def _hp_mode(self, value):
        self.state["hp_mode"] = value
        self.view.changed()

    def _character_picked(self, name):
        self.state["character"] = name
        self.view.changed()

    def _character_search(self, initial: bool = False):
        entry = self._widgets["character_search"]
        words = entry.get().lower().split()
        self.state["character_query"] = entry.get().strip()
        everything = self.view.character_names()
        names = [n for n in everything if all(w in n.lower() for w in words)]
        chosen = self.state.get("character")
        menu = self._widgets["character_menu"]
        menu.configure(values=names or ["(no match)"])
        if chosen not in names:
            chosen = names[0] if names else ""
        menu.set(chosen or ("(no match)" if everything else "(no characters)"))
        if chosen != self.state.get("character"):
            self.state["character"] = chosen
            if not initial:
                self.view.changed()
        elif not initial:
            self.view.changed()

    def _monster_search(self, initial: bool = False):
        entry = self._widgets["monster_search"]
        query = entry.get().strip().lower()
        self.state["monster_query"] = entry.get().strip()
        everything = self.view.monster_names()
        names = [n for n in everything if query in n.lower()][:60]
        chosen = self.state.get("monster")
        if chosen and chosen not in names and chosen in everything and query in chosen.lower():
            names.insert(0, chosen)                              # the one already picked stays in the list
        menu = self._widgets["monster_menu"]
        menu.configure(values=names or ["(no match)"])
        if chosen not in names:
            chosen = names[0] if names else ""
        menu.set(chosen or "(no match)")
        if chosen != self.state.get("monster"):
            self.state["monster"] = chosen
            if not initial:
                self.view.changed()
        elif not initial:
            self.view.changed()
        self.refresh_info()

    def _monster_picked(self, name):
        self.state["monster"] = name
        self.view.changed()
        self.refresh_info()

    def refresh_info(self, side: Optional[M.Side] = None):
        if side is None:
            self.info.configure(text="")
            return
        speeds = ", ".join(f"{k} {v} ft." for k, v in side.speeds.items())
        bits = [f"AC {side.ac}", f"HP {side.hp}", speeds, f"initiative {side.initiative:+d}"]
        if side.cr_text:
            bits.insert(0, side.cr_text)
        if side.level_text:
            bits.insert(0, side.level_text)
        extra = []
        if side.resist:
            extra.append("resists " + ", ".join(sorted(side.resist)))
        if side.immune:
            extra.append("immune " + ", ".join(sorted(side.immune)))
        if side.vulnerable:
            extra.append("vulnerable " + ", ".join(sorted(side.vulnerable)))
        if side.condition_immunities:
            extra.append("condition immunities " + ", ".join(sorted(side.condition_immunities)))
        if side.legendary_resistance:
            extra.append(f"Legendary Resistance {side.legendary_resistance}/day")
        self.info.configure(text="  •  ".join(bits) + ("\n" + "; ".join(extra) if extra else ""))

    # ---- build the Side
    def build(self) -> M.Side:
        kind = self.state["kind"]
        if kind == "Character":
            name = self.state.get("character")
            loaded = self.view.load_character(name) if name else None
            if not loaded:
                raise ValueError("Pick a character.")
            character, sheet = loaded
            opts = {"hp": "current" if self.state.get("hp_mode") == "Current HP" else "max",
                    "boosts": bool(self.state.get("boosts", True)), "use_slots": bool(self.state.get("use_slots", True)),
                    "raging": bool(self.state.get("raging")), "resist": self.state.get("resist", ""),
                    "immune": self.state.get("immune", ""), "cond_immune": self.state.get("cond_immune", "")}
            return M.side_from_character(character, sheet, self.view.lookups, opts)
        if kind == "Monster":
            name = self.state.get("monster")
            monster = self.view.get_monster(name) if name else None
            if monster is None:
                raise ValueError("Pick a monster.")
            side = M.side_from_monster(monster, self.view.lookups.spell)
        else:
            def num(key, default, what):
                raw = str(self.state.get(key, "") or "").strip().replace("−", "-")
                try:
                    return int(raw) if raw else default
                except ValueError:
                    raise ValueError(f"{what} must be a whole number.")
            from dice_analyzer import DiceError
            try:
                side = M.side_from_custom(
                    str(self.state.get("c_name") or "Custom creature"), num("c_ac", 14, "Armor Class"),
                    max(1, num("c_hp", 40, "Hit points")), num("c_bonus", 5, "The attack bonus"),
                    str(self.state.get("c_damage") or "1d8+3"), max(1, num("c_attacks", 2, "Attacks per round")),
                    num("c_speed", 30, "Speed"), 5, max(0, num("c_range", 0, "Range")),
                    str(self.state.get("c_type") or "slashing").strip().lower())
            except DiceError as e:
                raise ValueError(str(e))
        side.resist |= M._parse_types(self.state.get("resist", ""))
        side.immune |= M._parse_types(self.state.get("immune", ""))
        side.condition_immunities |= M._parse_conditions(self.state.get("cond_immune", ""))
        return side


class MatchupView(ctk.CTkFrame):
    def __init__(self, parent, state: dict, character_names: Callable[[], List[str]],
                 load_character: Callable[[str], Optional[tuple]], lookups, monster_names: Callable[[], List[str]],
                 get_monster: Callable[[str], object], on_back: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.state = state
        self.character_names = character_names
        self.load_character = load_character
        self.lookups = lookups
        self.monster_names = monster_names
        self.get_monster = get_monster
        self.on_back = on_back
        self._job = None
        self._poll_job = None
        self._token = 0
        self._done: "queue.Queue" = queue.Queue()
        self.result: Optional[M.Result] = None
        self._sides: List[M.Side] = []
        c = self.theme.get_current_color

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=16)
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.pack(fill="x", pady=(0, 10))
        if on_back:
            ctk.CTkButton(head, text="← Game Tools", width=110, height=32, fg_color=c("button_normal"),
                          hover_color=c("button_hover"), command=on_back).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(head, text="Matchup", font=ui_font("title", 28, bold=True)).pack(side="left")
        ctk.CTkButton(head, text="⇄ Swap", width=80, height=32, fg_color=c("button_normal"),
                      hover_color=c("button_hover"), text_color=c("text_primary"), command=self._swap
                      ).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)
        cards = ctk.CTkFrame(self.scroll, fg_color="transparent")
        cards.pack(fill="x")
        cards.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        self.card_a = _SideCard(self, cards, "a")
        self.card_a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.card_b = _SideCard(self, cards, "b")
        self.card_b.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.status = ctk.CTkLabel(self.scroll, text="", font=ui_font("body"), anchor="w", justify="left",
                                   text_color=c("text_secondary"), wraplength=900)
        self.status.pack(fill="x", pady=(10, 0))
        self.results = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.results.pack(fill="x", pady=(6, 0))
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.changed(now=True)

    # ---- running it
    def _swap(self):
        a, b = self.state.get("a", {}), self.state.get("b", {})
        self.state["a"], self.state["b"] = b, a
        self.card_a.destroy()
        self.card_b.destroy()
        cards = self.card_a.master
        self.card_a = _SideCard(self, cards, "a")
        self.card_a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.card_b = _SideCard(self, cards, "b")
        self.card_b.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.changed(now=True)

    def changed(self, now: bool = False):
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except (tk.TclError, ValueError):
                pass
        try:
            self._job = self.after(1 if now else DEBOUNCE_MS, self._start)
        except tk.TclError:
            self._job = None

    def _start(self):
        self._job = None
        try:
            a, b = self.card_a.build(), self.card_b.build()
        except ValueError as e:
            self.status.configure(text=str(e))
            return
        except Exception as e:
            self.status.configure(text=f"Could not read that creature ({type(e).__name__}: {e}).")
            return
        self.card_a.refresh_info(a)
        self.card_b.refresh_info(b)
        self._token += 1
        token = self._token
        self.status.configure(text="Working out the fight...")

        def work():
            try:
                self._done.put((token, ("ok", M.analyze(a, b, TRIALS))))
            except Exception as e:                       # a bug must not leave the page on "Working out"
                self._done.put((token, ("err", f"Something went wrong ({type(e).__name__}: {e}).")))

        threading.Thread(target=work, daemon=True).start()
        self._poll()

    def _poll(self):
        if self._poll_job is not None:
            return
        self._poll_job = self.after(60, self._poll_tick)

    def _poll_tick(self):
        self._poll_job = None
        latest = None
        try:
            while True:
                latest = self._done.get_nowait()
        except queue.Empty:
            pass
        if latest is not None and latest[0] == self._token:
            kind, payload = latest[1]
            if kind == "ok":
                self.result = payload
                self._render(payload)
            else:
                self.status.configure(text=payload)
            return
        if self._token and (latest is None or latest[0] != self._token):
            self._poll()

    # ---- showing it
    def _label(self, parent, text, bold=False, size=12, color=None, wrap=860, pady=(0, 0)):
        c = self.theme.get_current_color
        lab = ctk.CTkLabel(parent, text=text, font=ui_font("subheading", 14, bold=True) if bold else ui_font("body", size),
                           anchor="w", justify="left", wraplength=wrap,
                           text_color=c(color) if color else c("text_primary"))
        lab.pack(fill="x", pady=pady)
        return lab

    @staticmethod
    def _chance_headline(plan: M.Plan, foe: M.Side) -> str:
        """How likely the side's usual turn is to land against ``foe``."""
        rows = plan.chances()
        if not rows:
            return f"{plan.name} cannot miss"
        kinds = {w for _n, _c, w in rows}
        percents = {round(c * 100) for _n, c, _w in rows}
        if len(percents) == 1 and kinds == {"hit"}:
            return f"Chance to hit {foe.name} (AC {foe.ac}): {percents.pop()}%"
        if len(percents) == 1 and kinds == {"fail"}:
            return f"Chance {foe.name} fails the save: {percents.pop()}%"
        return f"Chance to land against {foe.name} (AC {foe.ac}): {plan.chance_text()}"

    def _render(self, r: M.Result):
        for child in self.results.winfo_children():
            destroy_later(child)
        c = self.theme.get_current_color
        a, b = r.a.side, r.b.side
        sim = r.sim
        self.status.configure(text="")
        box = ctk.CTkFrame(self.results, fg_color=c("bg_secondary"), corner_radius=10)
        box.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        verdict = (f"{a.name} is favoured" if sim["a"] > sim["b"] + 0.1 else
                   f"{b.name} is favoured" if sim["b"] > sim["a"] + 0.1 else "A close fight")
        ctk.CTkLabel(inner, text=verdict, font=ui_font("heading", 20, bold=True), anchor="w").pack(fill="x")
        bar = WinBar(inner)
        bar.pack(fill="x", pady=(6, 6))
        bar.set(sim["a"], sim["b"], sim["draw"], (a.name, b.name))
        def kill_text(who, other, rounds):
            if rounds == float("inf"):
                return f"{who.name} cannot damage {other.name} on its own"
            return f"{who.name} needs about {rounds:.1f} rounds of sustained damage to kill {other.name}"
        lines = [
            f"A decisive fight lasts about {sim['rounds_mean']:.1f} rounds (median {sim['rounds_median']}).",
            f"{a.name} goes first {sim['first_a'] * 100:.0f}% of the time.",
            f"{kill_text(a, b, r.kill_rounds['a'])}; {kill_text(b, a, r.kill_rounds['b'])}.",
        ]
        if sim["a"]:
            lines.append(f"When {a.name} wins it has about {sim['a_left']:.0f} of {a.hp} hit points left.")
        if sim["b"]:
            lines.append(f"When {b.name} wins it has about {sim['b_left']:.0f} of {b.hp} hit points left.")
        if sim["draw"] > 0.005:
            lines.append(f"{sim['draw'] * 100:.0f}% of fights are still going after {M.MAX_ROUNDS} rounds or end together.")
        self._label(inner, "\n".join(lines), size=13, wrap=860)

        cols = ctk.CTkFrame(self.results, fg_color="transparent")
        cols.pack(fill="x")
        cols.grid_columnconfigure((0, 1), weight=1, uniform="res")
        for i, (prep, foe, key) in enumerate(((r.a, b, "a"), (r.b, a, "b"))):
            col = ctk.CTkFrame(cols, fg_color=c("bg_secondary"), corner_radius=10)
            col.grid(row=0, column=i, sticky="nsew", padx=(0, 6) if i == 0 else (6, 0), pady=(0, 10))
            body = ctk.CTkFrame(col, fg_color="transparent")
            body.pack(fill="both", expand=True, padx=12, pady=10)
            self._label(body, f"{prep.side.name} against {foe.name}", bold=True, wrap=420)
            self._label(body, f"Sustained damage {prep.sustained():.1f} per round  •  best single round "
                              f"{prep.best():.1f}", color="text_secondary", size=12, wrap=420)
            main = prep.main_plan()
            if main is not None:
                self._label(body, self._chance_headline(main, foe), size=13, wrap=420, pady=(2, 0))
            plans = sorted(prep.plans, key=lambda p: -p.avg)[:10]
            for plan in plans:
                row = ctk.CTkFrame(body, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text=f"{plan.avg:.1f}", width=50, anchor="e", font=ui_font("body", 12, bold=True)
                             ).pack(side="left")
                text = plan.name + (" (limited)" if plan.resource else "")
                ctk.CTkLabel(row, text=text, anchor="w", justify="left", wraplength=250,
                             font=ui_font("small", 12)).pack(side="left", padx=8)
                ctk.CTkLabel(row, text=plan.chance_text(), anchor="e", justify="right", wraplength=120,
                             font=ui_font("small", 11), text_color=c("text_secondary")).pack(side="right")
            if prep.blocked:
                self._label(body, "No effect: " + ", ".join(prep.blocked), color="compare_worse", size=12, wrap=420,
                            pady=(4, 0))
            if prep.spells_table:
                self._label(body, "Spells (average damage against this opponent)", bold=True, wrap=420, pady=(10, 0))
                head = ctk.CTkFrame(body, fg_color="transparent")
                head.pack(fill="x")
                for text, w in (("Lvl", 36), ("Best", 110), ("Avg", 50), ("Per slot level", 90)):
                    ctk.CTkLabel(head, text=text, width=w, anchor="w", font=ui_font("small", 11),
                                 text_color=c("text_secondary")).pack(side="left")
                for lvl in sorted(prep.spell_levels):
                    row = prep.spell_levels[lvl]
                    line = ctk.CTkFrame(body, fg_color="transparent")
                    line.pack(fill="x")
                    ctk.CTkLabel(line, text="C" if lvl == 0 else str(lvl), width=36, anchor="w",
                                 font=ui_font("small", 12)).pack(side="left")
                    ctk.CTkLabel(line, text=row["name"], width=110, anchor="w", font=ui_font("small", 12)).pack(side="left")
                    ctk.CTkLabel(line, text=f"{row['avg']:.1f}", width=50, anchor="w", font=ui_font("small", 12)
                                 ).pack(side="left")
                    per = "-" if row["per_slot"] is None else f"{row['per_slot']:.1f}"
                    if row.get("upcast"):
                        per += f"  (level {row['upcast'][0]}: {row['upcast'][2]:.1f})"
                    ctk.CTkLabel(line, text=per, anchor="w", font=ui_font("small", 12)).pack(side="left")
                others = [x for x in prep.spells_table if prep.spell_levels.get(x["level"]) is not x]
                if others:
                    self._label(body, "Also: " + ", ".join(f"{x['name']} {x['avg']:.0f}" for x in others[:10]),
                                color="text_secondary", size=11, wrap=420, pady=(2, 0))

        tt = ctk.CTkFrame(self.results, fg_color=c("bg_secondary"), corner_radius=10)
        tt.pack(fill="x", pady=(0, 10))
        tb = ctk.CTkFrame(tt, fg_color="transparent")
        tb.pack(fill="x", padx=14, pady=12)
        self._label(tb, "Tide turners", bold=True)
        self._label(tb, "Things the averages cannot capture: conditions and debuffs, defensive abilities, healing, and "
                        "differences in speed or range.", color="text_secondary", size=12)
        grid = ctk.CTkFrame(tb, fg_color="transparent")
        grid.pack(fill="x", pady=(6, 0))
        grid.grid_columnconfigure((0, 1), weight=1, uniform="tt")
        for i, (side, key) in enumerate(((a, "a"), (b, "b"))):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=0, column=i, sticky="nsew", padx=(0, 8) if i == 0 else (8, 0))
            self._label(cell, side.name, bold=True, wrap=420)
            items = r.turners[key]
            self._label(cell, "\n".join(f"• {t}" for t in items) if items else "Nothing notable.", size=12,
                        color=None if items else "text_secondary", wrap=420)
        notes = ctk.CTkFrame(self.results, fg_color="transparent")
        notes.pack(fill="x", pady=(0, 20))
        self._label(notes, "How this was worked out", bold=True)
        self._label(notes, "\n".join(f"• {n}" for n in r.notes), size=11, color="text_secondary")

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        self._token += 1
        for job in (self._job, self._poll_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
