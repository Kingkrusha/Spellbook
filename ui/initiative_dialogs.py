"""Small windows used by the initiative tracker: stats, conditions, adding combatants, settings.

They talk to a backend (``dispatch(command)``), never to the tracker state directly, so the same
windows work for the DM and for a player editing their own character.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import conditions as C
import initiative_sources as S
import initiative_state as T
from theme import get_theme_manager
from typography import ui_font


def _theme():
    return get_theme_manager()


def _near(win: ctk.CTkToplevel, anchor, width: int, height: int):
    """Open ``win`` just below ``anchor`` (a widget or an (x, y) screen point), kept on screen."""
    win.update_idletasks()
    if isinstance(anchor, tuple):
        x, y = anchor
    else:
        x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 4
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(8, min(x, sw - width - 8))
    y = max(8, min(y, sh - height - 48))
    win.geometry(f"{width}x{height}+{x}+{y}")


def _keep_above(win: ctk.CTkToplevel, owner):
    """A window opened from an always-on-top tracker window must itself be on top to be seen."""
    try:
        if owner.winfo_toplevel().attributes("-topmost"):
            win.attributes("-topmost", True)
    except Exception:
        pass


def _error(parent, text: str):
    messagebox.showwarning("Initiative tracker", text, parent=parent.winfo_toplevel())


def _to_int(text: str) -> Optional[int]:
    try:
        return int(str(text).strip())
    except ValueError:
        return None


class PromptDialog(ctk.CTkToplevel):
    """One line of text: rename, group name, an initiative number, a note."""

    def __init__(self, parent, title: str, label: str, initial: str, on_ok: Callable[[str], None],
                 multiline: bool = False):
        super().__init__(parent)
        t = _theme()
        self.title(title)
        self.transient(parent.winfo_toplevel())
        _keep_above(self, parent)
        self.geometry(f"{380}x{200 if multiline else 130}")
        self.resizable(False, False)
        self._on_ok, self._multi = on_ok, multiline
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=16, pady=14)
        ctk.CTkLabel(box, text=label, font=ui_font("body")).pack(anchor="w")
        if multiline:
            self.entry = ctk.CTkTextbox(box, height=90)
            self.entry.insert("1.0", initial)
            self.entry.pack(fill="x", pady=(4, 8))
        else:
            self.entry = ctk.CTkEntry(box, height=32)
            self.entry.insert(0, initial)
            self.entry.pack(fill="x", pady=(4, 8))
            self.entry.bind("<Return>", lambda _e: self._ok())
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="OK", width=80, fg_color=t.get_current_color('accent_primary'),
                      hover_color=t.get_current_color('accent_hover'), command=self._ok).pack(side="left")
        ctk.CTkButton(row, text="Cancel", width=80, fg_color=t.get_current_color('button_normal'),
                      hover_color=t.get_current_color('button_hover'), command=self.destroy).pack(side="right")
        self.after(80, lambda: (self.entry.focus_force(), None))

    def _ok(self):
        text = self.entry.get("1.0", "end-1c") if self._multi else self.entry.get()
        self.destroy()
        self._on_ok(text)


class StatsPopover(ctk.CTkToplevel):
    """Damage / heal / set the numbers of one combatant."""

    def __init__(self, parent, anchor, backend, row):
        super().__init__(parent)
        t = _theme()
        self.backend, self.row_id = backend, row.id
        self.title(row.name)
        self.transient(parent.winfo_toplevel())
        _keep_above(self, parent)
        self.resizable(False, False)
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=14, pady=12)

        head = f"{row.name}   HP {row.hp} / {row.hp_max}" + (f"  (+{row.hp_temp} temp)" if row.hp_temp else "")
        ctk.CTkLabel(box, text=head, font=ui_font("body", bold=True)).pack(anchor="w")

        line = ctk.CTkFrame(box, fg_color="transparent")
        line.pack(fill="x", pady=(10, 6))
        self.amount = ctk.CTkEntry(line, width=80, height=32, placeholder_text="Amount")
        self.amount.pack(side="left")
        self.amount.bind("<Return>", lambda _e: self._delta(-1))
        ctk.CTkButton(line, text="Damage", width=80, height=32, fg_color=t.get_current_color('button_danger'),
                      hover_color=t.get_current_color('button_danger_hover'),
                      command=lambda: self._delta(-1)).pack(side="left", padx=(8, 4))
        ctk.CTkButton(line, text="Heal", width=70, height=32, fg_color=t.get_current_color('button_success'),
                      hover_color=t.get_current_color('button_success_hover'),
                      command=lambda: self._delta(+1)).pack(side="left")

        ctk.CTkLabel(box, text="Or set the values directly:", font=ui_font("small"),
                     text_color=t.get_text_secondary()).pack(anchor="w", pady=(8, 2))
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(fill="x")
        self.fields: Dict[str, ctk.CTkEntry] = {}
        for i, (key, label, value) in enumerate((("hp", "HP", row.hp), ("hp_temp", "Temp", row.hp_temp),
                                                  ("hp_max", "Max HP", row.hp_max),
                                                  ("ac", "AC", row.ac if row.ac is not None else ""))):
            ctk.CTkLabel(grid, text=label, font=ui_font("small")).grid(row=0, column=i, padx=4)
            e = ctk.CTkEntry(grid, width=62, height=30)
            e.insert(0, str(value))
            e.grid(row=1, column=i, padx=4)
            e.bind("<Return>", lambda _e: self._apply())
            self.fields[key] = e
        self._original = {k: e.get() for k, e in self.fields.items()}
        ctk.CTkButton(box, text="Apply", height=32, fg_color=t.get_current_color('accent_primary'),
                      hover_color=t.get_current_color('accent_hover'),
                      command=self._apply).pack(fill="x", pady=(10, 0))
        _near(self, anchor, 330, 220)
        self.after(80, self.amount.focus_force)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _run(self, cmd: dict):
        try:
            self.backend.dispatch(cmd)
        except T.CommandError as e:
            _error(self, e.message)
            return
        self.destroy()

    def _delta(self, sign: int):
        n = _to_int(self.amount.get())
        if n is None or n < 0:
            _error(self, "Type a whole number first.")
            return
        if n:
            self._run({"type": "hp_delta", "id": self.row_id, "delta": sign * n})
        else:
            self.destroy()

    def _apply(self):
        cmd = {"type": "set_stats", "id": self.row_id}
        for key, entry in self.fields.items():
            if entry.get().strip() != self._original[key] and entry.get().strip() != "":
                n = _to_int(entry.get())
                if n is None:
                    _error(self, "Those need to be whole numbers.")
                    return
                cmd[key] = n
        if len(cmd) > 2:
            self._run(cmd)
        else:
            self.destroy()


class ConditionsPopover(ctk.CTkToplevel):
    """Toggle conditions on one combatant; each click applies straight away."""

    def __init__(self, parent, anchor, backend, row_id: str):
        super().__init__(parent)
        self.backend, self.row_id = backend, row_id
        self.theme = _theme()
        self.transient(parent.winfo_toplevel())
        _keep_above(self, parent)
        self.resizable(False, False)
        row = self._row()
        self.title(f"Conditions - {row.name}" if row else "Conditions")

        self.box = ctk.CTkFrame(self, fg_color="transparent")
        self.box.pack(fill="both", expand=True, padx=12, pady=10)
        self._rounds_text = ""
        self.rounds = None
        self._build()
        _near(self, anchor, 470, 330)
        self.bind("<Escape>", lambda _e: self.destroy())
        backend.listen(self._build)
        self.bind("<Destroy>", lambda e: backend.unlisten(self._build) if e.widget is self else None, add="+")

    def _row(self):
        return next((r for r in self.backend.table().rows if r.id == self.row_id), None)

    def _active(self) -> Dict[str, dict]:
        row = self._row()
        return {c["name"].lower(): c for c in (row.conditions if row else [])}

    def _build(self):
        if not self.winfo_exists():
            return
        t = self.theme
        if self.rounds is not None and self.rounds.winfo_exists():
            self._rounds_text = self.rounds.get()           # keep what was typed across rebuilds
        for w in self.box.winfo_children():
            w.destroy()
        active = self._active()
        grid = ctk.CTkFrame(self.box, fg_color="transparent")
        grid.pack(fill="x")
        for i, name in enumerate(C.CONDITIONS):
            cond = active.get(name.lower())
            on = cond is not None
            text = name if not (on and name == C.EXHAUSTION) else f"{name} {cond.get('level', 1)}"
            btn = ctk.CTkButton(grid, text=text, width=140, height=28, font=ui_font("small"),
                                fg_color=t.get_current_color('accent_primary') if on
                                else t.get_current_color('button_normal'),
                                hover_color=t.get_current_color('accent_hover') if on
                                else t.get_current_color('button_hover'),
                                command=lambda n=name, on=on: self._toggle(n, on))
            btn.grid(row=i // 3, column=i % 3, padx=3, pady=3)
        if C.EXHAUSTION.lower() in active:
            lvl = active[C.EXHAUSTION.lower()].get("level", 1)
            line = ctk.CTkFrame(self.box, fg_color="transparent")
            line.pack(fill="x", pady=(4, 0))
            ctk.CTkLabel(line, text="Exhaustion level", font=ui_font("small")).pack(side="left")
            for d, sym in ((-1, "−"), (+1, "+")):
                ctk.CTkButton(line, text=sym, width=28, height=26, fg_color=t.get_current_color('button_normal'),
                              hover_color=t.get_current_color('button_hover'),
                              command=lambda d=d, lvl=lvl: self._exhaustion(lvl + d)).pack(side="left", padx=3)

        extra = ctk.CTkFrame(self.box, fg_color="transparent")
        extra.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(extra, text="Other:", font=ui_font("small")).pack(side="left")
        self.custom = ctk.CTkEntry(extra, width=150, height=28, placeholder_text="Concentrating, Hexed…")
        self.custom.pack(side="left", padx=4)
        self.custom.bind("<Return>", lambda _e: self._add_custom())
        ctk.CTkButton(extra, text="Add", width=50, height=28, fg_color=t.get_current_color('accent_primary'),
                      hover_color=t.get_current_color('accent_hover'),
                      command=self._add_custom).pack(side="left")
        self.rounds = ctk.CTkEntry(extra, width=64, height=28, placeholder_text="rounds")
        self.rounds.pack(side="left", padx=(10, 0))
        if self._rounds_text:
            self.rounds.insert(0, self._rounds_text)

        known = {c.lower() for c in C.CONDITIONS}
        custom_active = [c for n, c in active.items() if n not in known]
        if custom_active:
            chips = ctk.CTkFrame(self.box, fg_color="transparent")
            chips.pack(fill="x", pady=(8, 0))
            for c in custom_active:
                ctk.CTkButton(chips, text=f"{C.label(c)}  ✕", height=26, font=ui_font("small"),
                              fg_color=t.get_current_color('bg_tertiary'),
                              hover_color=t.get_current_color('button_danger'),
                              command=lambda n=c["name"]: self._remove(n)).pack(side="left", padx=2)

    def _rounds(self) -> Optional[int]:
        n = _to_int(self.rounds.get()) if self.rounds is not None and self.rounds.winfo_exists() else None
        return n if n and n > 0 else None

    def _run(self, cmd: dict):
        try:
            self.backend.dispatch(cmd)
        except T.CommandError as e:
            _error(self, e.message)

    def _toggle(self, name: str, on: bool):
        if on:
            self._remove(name)
        else:
            self._run({"type": "add_condition", "id": self.row_id, "name": name, "rounds": self._rounds()})

    def _remove(self, name: str):
        self._run({"type": "remove_condition", "id": self.row_id, "name": name})

    def _exhaustion(self, level: int):
        if level < 1:
            self._remove(C.EXHAUSTION)
        else:
            self._run({"type": "add_condition", "id": self.row_id, "name": C.EXHAUSTION,
                       "level": min(level, C.MAX_EXHAUSTION)})

    def _add_custom(self):
        name = self.custom.get().strip()
        if name:
            self._run({"type": "add_condition", "id": self.row_id, "name": name, "rounds": self._rounds()})
            self.custom.delete(0, "end")


class SettingsPopover(ctk.CTkToplevel):
    """The DM's visibility settings: what players may see of monsters."""

    HP = {"Exact numbers": "number", "Health bar only": "bar", "Hidden": "hidden"}
    AC = {"Shown": "shown", "Hidden": "hidden"}

    def __init__(self, parent, anchor, backend):
        super().__init__(parent)
        t = _theme()
        self.backend = backend
        self.title("Tracker settings")
        self.transient(parent.winfo_toplevel())
        _keep_above(self, parent)
        self.resizable(False, False)
        s = backend.view().get("settings", {})
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=16, pady=14)
        ctk.CTkLabel(box, text="What players see", font=ui_font("heading", 15, bold=True)).pack(anchor="w")

        def option(label, mapping, key, current):
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, font=ui_font("body"), width=170, anchor="w").pack(side="left")
            names = list(mapping)
            var = ctk.StringVar(value=next((n for n, v in mapping.items() if v == current), names[0]))
            ctk.CTkOptionMenu(row, values=names, variable=var, width=150, height=28,
                              command=lambda n: self._set(key, mapping[n])).pack(side="left")

        option("Monster HP", self.HP, "monster_hp", s.get("monster_hp", "number"))
        option("Monster AC", self.AC, "monster_ac", s.get("monster_ac", "shown"))
        option("Other players' HP", self.HP, "player_hp", s.get("player_hp", "number"))

        def check(label, key, current):
            var = ctk.BooleanVar(value=bool(current))
            ctk.CTkCheckBox(box, text=label, variable=var,
                            command=lambda: self._set(key, var.get())).pack(anchor="w", pady=(8, 0))

        check("Players can add their own characters", "players_can_add", s.get("players_can_add", True))
        check("Skip defeated monsters on their turn", "skip_defeated", s.get("skip_defeated", True))
        ctk.CTkLabel(box, text="Hide or reveal one creature's HP/AC from its ⋯ menu.", font=ui_font("small"),
                     text_color=t.get_text_secondary()).pack(anchor="w", pady=(12, 0))
        _near(self, anchor, 400, 290)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _set(self, key: str, value):
        try:
            self.backend.dispatch({"type": "set_settings", key: value})
        except T.CommandError as e:
            _error(self, e.message)


class AddCombatantDialog(ctk.CTkToplevel):
    """Bring monsters, characters, custom creatures and events into the fight."""

    def __init__(self, parent, backend, get_managers: Optional[Callable[[], object]] = None):
        super().__init__(parent)
        self.t = _theme()
        self.backend = backend
        self.get_managers = get_managers
        self.title("Add to the fight")
        self.geometry("560x620")
        self.minsize(520, 560)
        self.transient(parent.winfo_toplevel())
        _keep_above(self, parent)
        self._monsters: list = []
        self._characters: list = []

        self.tabs = ctk.CTkTabview(self, height=360)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(12, 6))
        self._monster_tab(self.tabs.add("Monster"))
        self._character_tab(self.tabs.add("Character"))
        self._custom_tab(self.tabs.add("Custom"))
        self._event_tab(self.tabs.add("Event"))

        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.pack(fill="x", padx=18, pady=(0, 4))
        ctk.CTkLabel(opts, text="How many", font=ui_font("small")).grid(row=0, column=0, sticky="w")
        self.count = ctk.CTkEntry(opts, width=60, height=28)
        self.count.insert(0, "1")
        self.count.grid(row=1, column=0, padx=(0, 14))
        ctk.CTkLabel(opts, text="Initiative (blank = roll)", font=ui_font("small")).grid(row=0, column=1, sticky="w")
        self.init = ctk.CTkEntry(opts, width=90, height=28)
        self.init.grid(row=1, column=1, padx=(0, 14))
        self.group_var = ctk.BooleanVar(value=True)
        self.hidden_var = ctk.BooleanVar(value=False)
        self.rollhp_var = ctk.BooleanVar(value=False)
        self.roll_var = ctk.BooleanVar(value=True)
        checks = ctk.CTkFrame(opts, fg_color="transparent")
        checks.grid(row=0, column=2, rowspan=2, sticky="w")
        for text, var in (("Group several together", self.group_var), ("Add hidden from players", self.hidden_var),
                          ("Roll monster HP from its dice", self.rollhp_var), ("Roll initiative now", self.roll_var)):
            ctk.CTkCheckBox(checks, text=text, variable=var, font=ui_font("small"), height=22,
                            checkbox_width=18, checkbox_height=18).pack(anchor="w")

        self.status = ctk.CTkLabel(self, text="", font=ui_font("small"), text_color=self.t.get_text_secondary(),
                                   anchor="w")
        self.status.pack(fill="x", padx=18)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(4, 12))
        ctk.CTkButton(row, text="＋ Add", width=110, height=34, fg_color=self.t.get_current_color('accent_primary'),
                      hover_color=self.t.get_current_color('accent_hover'), command=self._add).pack(side="left")
        ctk.CTkButton(row, text="Done", width=90, height=34, fg_color=self.t.get_current_color('button_normal'),
                      hover_color=self.t.get_current_color('button_hover'),
                      command=self.destroy).pack(side="right")

    # ------------------------------------------------------------------ tabs

    def _listbox(self, parent):
        t = self.t
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, pady=(6, 0))
        lb = tk.Listbox(frame, activestyle="none", exportselection=False, relief="flat", highlightthickness=0,
                        bg=t.get_current_color('bg_input'), fg=t.get_current_color('text_primary'),
                        selectbackground=t.get_current_color('accent_primary'), font=("Segoe UI", 10))
        sb = ctk.CTkScrollbar(frame, command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        return lb

    def _monster_tab(self, tab):
        line = ctk.CTkFrame(tab, fg_color="transparent")
        line.pack(fill="x")
        self.m_search = ctk.CTkEntry(line, height=30, placeholder_text="Search monsters…")
        self.m_search.pack(side="left", fill="x", expand=True)
        self.m_search.bind("<KeyRelease>", lambda _e: self._fill_monsters())
        self.m_summons = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(line, text="Summons", variable=self.m_summons, font=ui_font("small"), width=80,
                        command=self._fill_monsters).pack(side="left", padx=8)
        self.m_list = self._listbox(tab)
        self.m_list.bind("<Double-Button-1>", lambda _e: self._add())
        self.m_info = ctk.CTkLabel(tab, text="", font=ui_font("small"), anchor="w",
                                   text_color=self.t.get_text_secondary())
        self.m_info.pack(fill="x", pady=(4, 0))
        self.m_list.bind("<<ListboxSelect>>", lambda _e: self._monster_info())
        self.after(50, self._fill_monsters)

    def _fill_monsters(self):
        try:
            from monster import get_monster_manager
            mm = get_monster_manager()
            pool = list(mm.monsters if self.m_summons.get() else mm.browsable)
        except Exception:
            pool = []
        q = self.m_search.get().strip().lower()
        pool = [m for m in pool if q in m.name.lower()] if q else pool
        pool.sort(key=lambda m: m.name.lower())
        self._monsters = pool[:400]
        self.m_list.delete(0, "end")
        for m in self._monsters:
            cr = m.cr_text or m.challenge_rating
            self.m_list.insert("end", f"{m.name}    CR {cr}   AC {m.ac}   HP {m.hp}")

    def _monster_info(self):
        m = self._selected(self.m_list, self._monsters)
        if m:
            init = m.get_initiative()
            self.m_info.configure(text=f"{m.name}: AC {m.ac}, HP {m.hp}"
                                       + (f" ({m.hit_dice})" if m.hit_dice else "")
                                       + f", initiative {'+' if init >= 0 else ''}{init}")

    def _character_tab(self, tab):
        ctk.CTkLabel(tab, text="One of your own characters, as an NPC or a stand-in player:",
                     font=ui_font("small"), text_color=self.t.get_text_secondary()).pack(anchor="w")
        self.c_list = self._listbox(tab)
        self.c_list.bind("<Double-Button-1>", lambda _e: self._add())
        try:
            self._characters = sorted(self.get_managers().character_manager.characters, key=lambda c: c.name.lower())
        except Exception:
            self._characters = []
        for c in self._characters:
            classes = ", ".join(f"{cl.get_class_name()} {cl.level}" for cl in c.classes)
            self.c_list.insert("end", c.name + (f"    {classes}" if classes else ""))

    def _custom_tab(self, tab):
        grid = ctk.CTkFrame(tab, fg_color="transparent")
        grid.pack(anchor="w", pady=10)
        self.cu = {}
        for i, (key, label, width, default) in enumerate((("name", "Name", 220, ""), ("hp", "HP", 70, "10"),
                                                           ("ac", "AC", 70, "12"), ("bonus", "Init bonus", 70, "0"))):
            ctk.CTkLabel(grid, text=label, font=ui_font("small")).grid(row=0, column=i, sticky="w", padx=4)
            e = ctk.CTkEntry(grid, width=width, height=30)
            e.insert(0, default)
            e.grid(row=1, column=i, padx=4)
            self.cu[key] = e
        ctk.CTkLabel(tab, text="For anything that isn't in the monster collection: a bandit mob, a horse, a\n"
                               "summoned creature. HP and AC here only exist in the tracker.",
                     font=ui_font("small"), justify="left", text_color=self.t.get_text_secondary()).pack(anchor="w", padx=4)

    def _event_tab(self, tab):
        ctk.CTkLabel(tab, text="Event name", font=ui_font("small")).pack(anchor="w", padx=4, pady=(10, 0))
        self.ev_name = ctk.CTkEntry(tab, height=30, placeholder_text="Lair action, the bridge collapses…")
        self.ev_name.pack(fill="x", padx=4)
        ctk.CTkLabel(tab, text="It takes its place in the order at the initiative number below, like a creature, "
                               "and shows as one line across the table.", font=ui_font("small"), justify="left",
                     wraplength=480, text_color=self.t.get_text_secondary()).pack(anchor="w", padx=4, pady=8)

    # ------------------------------------------------------------------ adding

    @staticmethod
    def _selected(listbox, items):
        sel = listbox.curselection()
        return items[sel[0]] if sel and sel[0] < len(items) else None

    def _add(self):
        tab = self.tabs.get()
        count = _to_int(self.count.get())
        if count is None or not 1 <= count <= T.MAX_ADD_AT_ONCE:
            self.status.configure(text=f"How many must be between 1 and {T.MAX_ADD_AT_ONCE}.")
            return
        hidden = self.hidden_var.get()
        try:
            if tab == "Monster":
                m = self._selected(self.m_list, self._monsters)
                if m is None:
                    self.status.configure(text="Pick a monster first.")
                    return
                cmd = S.from_monster(m, roll_hp=self.rollhp_var.get(), hidden=hidden)
                label = m.name
            elif tab == "Character":
                c = self._selected(self.c_list, self._characters)
                if c is None:
                    self.status.configure(text="Pick a character first.")
                    return
                sheet = self.get_managers().sheet_manager.get_sheet(c.name)
                if sheet is None:
                    from character_sheet import CharacterSheet
                    sheet = CharacterSheet(character_name=c.name)
                cmd = S.from_sheet(sheet, hidden=hidden)
                cmd["name"], label = c.name, c.name
            elif tab == "Custom":
                name = self.cu["name"].get().strip()
                hp, ac, bonus = (_to_int(self.cu[k].get()) for k in ("hp", "ac", "bonus"))
                if not name or hp is None or ac is None or bonus is None:
                    self.status.configure(text="Give it a name, and whole numbers for HP, AC and initiative bonus.")
                    return
                cmd, label = S.custom(name, hp=hp, ac=ac, init_bonus=bonus, hidden=hidden), name
            else:
                name = self.ev_name.get().strip()
                if not name:
                    self.status.configure(text="Give the event a name.")
                    return
                cmd, label, count = S.event(name, hidden=hidden), name, 1
            init = _to_int(self.init.get())
            if init is not None:
                cmd["initiative"] = init
            if count > 1:
                cmd = S.several(cmd, count, group=self.group_var.get())
            self.backend.dispatch(cmd)
            if self.roll_var.get() and init is None and tab != "Event":
                ids = list(self.backend.hub.tracker.state.last_added) if hasattr(self.backend, "hub") else None
                self.backend.dispatch({"type": "roll_initiative", "ids": ids} if ids else {"type": "roll_initiative"})
        except T.CommandError as e:
            self.status.configure(text=e.message)
            return
        self.status.configure(text=f"Added {label}" + (f" ×{count}" if count > 1 else "") + ".")


class AddMyCharacterDialog(ctk.CTkToplevel):
    """A player picks one of their characters to put into the initiative order.

    The tracker gets a *copy* of its HP, AC and initiative bonus; changing them in the tracker never
    changes the character sheet."""

    def __init__(self, parent, backend, get_managers: Optional[Callable[[], object]] = None):
        super().__init__(parent)
        t = _theme()
        self.backend, self.get_managers = backend, get_managers
        self.title("Add my character")
        self.geometry("360x340")
        self.transient(parent.winfo_toplevel())
        _keep_above(self, parent)
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=14, pady=12)
        ctk.CTkLabel(box, text="Which character?", font=ui_font("body", bold=True)).pack(anchor="w")
        try:
            self._characters = sorted(get_managers().character_manager.characters, key=lambda c: c.name.lower())
        except Exception:
            self._characters = []
        frame = ctk.CTkFrame(box, fg_color="transparent")
        frame.pack(fill="both", expand=True, pady=6)
        self.list = tk.Listbox(frame, activestyle="none", exportselection=False, relief="flat",
                               highlightthickness=0, bg=t.get_current_color('bg_input'),
                               fg=t.get_current_color('text_primary'),
                               selectbackground=t.get_current_color('accent_primary'), font=("Segoe UI", 10))
        self.list.pack(fill="both", expand=True)
        for c in self._characters:
            classes = ", ".join(f"{cl.get_class_name()} {cl.level}" for cl in c.classes)
            self.list.insert("end", c.name + (f"    {classes}" if classes else ""))
        if not self._characters:
            self.list.insert("end", "You have no characters yet.")
        self.list.bind("<Double-Button-1>", lambda _e: self._add())
        self.status = ctk.CTkLabel(box, text="", font=ui_font("small"),
                                   text_color=t.get_current_color('text_warning'))
        self.status.pack(anchor="w")
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Add", width=90, fg_color=t.get_current_color('accent_primary'),
                      hover_color=t.get_current_color('accent_hover'), command=self._add).pack(side="left")
        ctk.CTkButton(row, text="Cancel", width=90, fg_color=t.get_current_color('button_normal'),
                      hover_color=t.get_current_color('button_hover'), command=self.destroy).pack(side="right")

    def _add(self):
        sel = self.list.curselection()
        if not sel or sel[0] >= len(self._characters):
            self.status.configure(text="Pick a character first.")
            return
        c = self._characters[sel[0]]
        try:
            sheet = self.get_managers().sheet_manager.get_sheet(c.name)
            if sheet is None:
                from character_sheet import CharacterSheet
                sheet = CharacterSheet(character_name=c.name)
            cmd = S.as_me(S.from_sheet(sheet))
            cmd["name"] = c.name
            self.backend.dispatch(cmd)
        except T.CommandError as e:
            self.status.configure(text=e.message)
            return
        self.destroy()
