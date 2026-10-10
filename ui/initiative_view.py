"""The DM's initiative tracker page: turn controls, the table, and everything the DM can do to it.

Everything here goes through ``backend.dispatch`` - the rules (and who may do what) live in
``initiative_state``; this page only turns clicks into commands.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional, Set

import customtkinter as ctk

import initiative_state as T
from theme import get_theme_manager
from typography import ui_font
from ui.initiative_dialogs import (AddCombatantDialog, ConditionsPopover, PromptDialog, SettingsPopover,
                                   StatsPopover)
from ui.initiative_table import InitiativeTable, TableCallbacks


class InitiativeView(ctk.CTkFrame):
    def __init__(self, parent, hub, get_managers: Optional[Callable[[], object]] = None,
                 on_back: Optional[Callable[[], None]] = None,
                 open_window: Optional[Callable[[str], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.hub = hub
        self.backend = hub.dm()
        self.get_managers = get_managers
        self.on_back = on_back
        self.open_window = open_window
        self._selected: Set[str] = set()
        self._change_after = None

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=16)

        # ---- header
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        if on_back:
            ctk.CTkButton(head, text="← Game Tools", width=110, height=32,
                          fg_color=self.theme.get_current_color('button_normal'),
                          hover_color=self.theme.get_current_color('button_hover'),
                          command=on_back).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(head, text="Initiative Tracker", font=ui_font("title", 28, bold=True)).pack(side="left")
        self.round_label = ctk.CTkLabel(head, text="", font=ui_font("heading", 18, bold=True),
                                        text_color=self.theme.get_current_color('text_label'))
        self.round_label.pack(side="right")

        # ---- toolbar: turns, then editing
        bar = ctk.CTkFrame(outer, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=10)
        bar.pack(fill="x", pady=(0, 8))
        r1 = ctk.CTkFrame(bar, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=(8, 4))
        r2 = ctk.CTkFrame(bar, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=(0, 8))

        accent = dict(fg_color=self.theme.get_current_color('accent_primary'),
                      hover_color=self.theme.get_current_color('accent_hover'))
        normal = dict(fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'))
        danger = dict(fg_color=self.theme.get_current_color('button_danger'),
                      hover_color=self.theme.get_current_color('button_danger_hover'))

        def button(parent, text, command, style=normal, width=96):
            b = ctk.CTkButton(parent, text=text, width=width, height=32, command=command, **style)
            b.pack(side="left", padx=3)
            return b

        self.next_btn = button(r1, "▶ Start", lambda: self._do({"type": "next_turn"}), accent, 130)
        self.prev_btn = button(r1, "◀ Back", lambda: self._do({"type": "prev_turn"}), normal, 80)
        self.end_btn = button(r1, "■ End", self._end, normal, 80)
        ctk.CTkLabel(r1, text="  ").pack(side="left")
        self.undo_btn = button(r1, "↶ Undo", self._undo, normal, 84)
        self.settings_btn = button(r1, "⚙ Settings", self._settings, normal, 104)
        button(r1, "🗔 Pop out", lambda: self._pop_out("dm"), normal, 100)
        self.preview_btn = button(r1, "👁 Preview ▾", self._preview_menu, normal, 112)

        self.add_btn = button(r2, "＋ Add…", self._add, accent, 96)
        self.roll_btn = button(r2, "🎲 Roll initiative ▾", self._roll_menu, normal, 150)
        button(r2, "⇅ Sort", lambda: self._do({"type": "sort"}), normal, 76)
        self.group_btn = button(r2, "⛓ Group", self._group, normal, 90)
        self.ungroup_btn = button(r2, "Ungroup", self._ungroup, normal, 84)
        self.hide_btn = button(r2, "🙈 Hide / show", self._hide_selected, normal, 118)
        self.remove_btn = button(r2, "🗑 Remove", self._remove_selected, danger, 100)

        # ---- table
        self.table = InitiativeTable(outer, self.backend, TableCallbacks(
            on_select=self._on_select, on_stats=self._stats, on_conditions=self._conditions,
            on_initiative=self._initiative, on_context=self._context_menu,
            on_hide_toggle=self._hide_toggle, on_move=self._move))
        self.table.pack(fill="both", expand=True)

        self.hint = ctk.CTkLabel(
            outer, font=ui_font("small"), text_color=self.theme.get_text_secondary(), anchor="w",
            text="Click HP, AC or conditions to change them · click the initiative number to set it · "
                 "drag ⠿ to reorder · right-click or ⋯ for more · Ctrl/Shift-click to select several")
        self.hint.pack(fill="x", pady=(6, 0))

        self.backend.listen(self._schedule_change)
        self._on_change()

    def destroy(self):
        try:
            self.backend.unlisten(self._schedule_change)
        except Exception:
            pass
        if self._change_after is not None:
            try:
                self.after_cancel(self._change_after)
            except Exception:
                pass
        super().destroy()

    # ------------------------------------------------------------------ state

    def _schedule_change(self):
        if self._change_after is None:
            self._change_after = self.after(20, self._run_change)

    def _run_change(self):
        self._change_after = None
        if self.winfo_exists():
            self._on_change()

    def _on_change(self):
        tv = self.backend.table()
        self.round_label.configure(text=f"Round {tv.round}" if tv.started else "Not started")
        self.next_btn.configure(text="▶▶ Next turn" if tv.started else "▶ Start")
        state = "normal" if tv.started else "disabled"
        self.prev_btn.configure(state=state)
        self.end_btn.configure(state=state)
        self.undo_btn.configure(state="normal" if self.backend.can_undo else "disabled")
        self._on_select(self.table.selected if hasattr(self, "table") else set())

    def _on_select(self, ids: Set[str]):
        self._selected = set(ids)
        rows = {r.id: r for r in self.table.view.rows} if hasattr(self, "table") else {}
        chosen = [rows[i] for i in self._selected if i in rows]
        self.group_btn.configure(state="normal" if len(chosen) >= 2 else "disabled")
        self.ungroup_btn.configure(state="normal" if any(r.group for r in chosen) else "disabled")
        for b in (self.hide_btn, self.remove_btn):
            b.configure(state="normal" if chosen else "disabled")

    def _do(self, cmd: dict) -> bool:
        try:
            self.backend.dispatch(cmd)
            return True
        except T.CommandError as e:
            messagebox.showwarning("Initiative tracker", e.message, parent=self.winfo_toplevel())
            return False

    def _row(self, row_id: str):
        return self.table.row_of(row_id)

    # ------------------------------------------------------------------ toolbar

    def _end(self):
        if messagebox.askyesno("End the encounter?", "Stop combat and reset the round counter?\n"
                               "Everyone stays in the list.", parent=self.winfo_toplevel()):
            self._do({"type": "end"})

    def _undo(self):
        try:
            self.backend.undo()
        except T.CommandError as e:
            messagebox.showinfo("Undo", e.message, parent=self.winfo_toplevel())

    def _settings(self):
        SettingsPopover(self.winfo_toplevel(), self.settings_btn, self.backend)

    def _add(self):
        AddCombatantDialog(self.winfo_toplevel(), self.backend, self.get_managers)

    def _roll_menu(self):
        menu = self._menu()
        menu.add_command(label="Roll for everyone without a number", command=lambda: self._do(
            {"type": "roll_initiative", "only_missing": True}))
        menu.add_command(label="Re-roll everyone", command=lambda: self._do(
            {"type": "roll_initiative", "only_missing": False}))
        if self._selected:
            menu.add_command(label="Roll for the selected", command=lambda: self._do(
                {"type": "roll_initiative", "ids": list(self._selected), "only_missing": False}))
        self._popup(menu, self.roll_btn)

    def _preview_menu(self):
        menu = self._menu()
        menu.add_command(label="As an observer (no character)", command=lambda: self._pop_out("player:"))
        owners = self.backend.owners()
        if owners:
            menu.add_separator()
        for owner, name in owners:
            menu.add_command(label=f"As {name}'s player", command=lambda o=owner: self._pop_out(f"player:{o}"))
        self._popup(menu, self.preview_btn)

    def _pop_out(self, which: str):
        if self.open_window:
            self.open_window(which)

    def _group(self):
        ids = [r.id for r in self.table.view.rows if r.id in self._selected]
        if len(ids) < 2:
            return
        names = {r.name.rstrip("0123456789 ") for r in self.table.view.rows if r.id in self._selected}
        initial = names.pop() + "s" if len(names) == 1 else ""
        PromptDialog(self.winfo_toplevel(), "Group", "Name for the group (optional):", initial,
                     lambda text: self._do({"type": "group", "ids": ids, "name": text.strip()}))

    def _ungroup(self):
        for r in self.table.view.rows:
            if r.id in self._selected and r.group:
                if self._do({"type": "ungroup", "id": r.id}):
                    break

    def _hide_selected(self):
        rows = [r for r in self.table.view.rows if r.id in self._selected]
        if rows:
            hide = not all(r.hidden for r in rows)
            self._do({"type": "set_hidden", "ids": [r.id for r in rows], "hidden": hide})

    def _remove_selected(self):
        rows = [r for r in self.table.view.rows if r.id in self._selected]
        if not rows:
            return
        what = rows[0].name if len(rows) == 1 else f"{len(rows)} combatants"
        if messagebox.askyesno("Remove", f"Remove {what} from the tracker?", parent=self.winfo_toplevel()):
            self._do({"type": "remove", "ids": [r.id for r in rows]})
            self.table.clear_selection()

    # ------------------------------------------------------------------ table callbacks

    def _stats(self, row_id: str, anchor):
        row = self._row(row_id)
        if row:
            StatsPopover(self.winfo_toplevel(), anchor, self.backend, row)

    def _conditions(self, row_id: str, anchor):
        ConditionsPopover(self.winfo_toplevel(), anchor, self.backend, row_id)

    def _initiative(self, row_id: str):
        row = self._row(row_id)
        if row is None:
            return

        def apply(text: str):
            text = text.strip()
            if text and not text.lstrip("-").isdigit():
                messagebox.showwarning("Initiative", "That needs to be a whole number.",
                                       parent=self.winfo_toplevel())
                return
            self._do({"type": "set_initiative", "id": row_id, "value": int(text) if text else None})

        PromptDialog(self.winfo_toplevel(), "Initiative", f"Initiative for {row.name} (blank clears it):",
                     "" if row.initiative is None else str(row.initiative), apply)

    def _hide_toggle(self, row_id: str):
        row = self._row(row_id)
        if row is None:
            return
        ids = [r.id for r in self.table.view.rows if r.id in self._selected] if row_id in self._selected else [row_id]
        self._do({"type": "set_hidden", "ids": ids, "hidden": not row.hidden})

    def _move(self, row_id: str, before: Optional[str]):
        self._do({"type": "move", "id": row_id, "before": before})

    # ------------------------------------------------------------------ context menu

    def _menu(self) -> tk.Menu:
        t = self.theme
        return tk.Menu(self, tearoff=0, bg=t.get_current_color('bg_secondary'),
                       fg=t.get_current_color('text_primary'), activebackground=t.get_current_color('accent_primary'),
                       activeforeground=t.get_current_color('text_on_accent'), bd=0)

    def _popup(self, menu: tk.Menu, anchor):
        x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _context_menu(self, row_id: str, x: int, y: int):
        row = self._row(row_id)
        if row is None:
            return
        many = len(self._selected) > 1 and row_id in self._selected
        ids = list(self._selected) if many else [row_id]
        menu = self._menu()
        label = f"{len(ids)} selected" if many else row.name
        menu.add_command(label=label, state="disabled")
        menu.add_separator()
        if not many:
            menu.add_command(label="Rename…", command=lambda: PromptDialog(
                self.winfo_toplevel(), "Rename", "Name:", row.name,
                lambda text: self._do({"type": "set_field", "id": row_id, "field": "name", "value": text})))
            menu.add_command(label="Set initiative…", command=lambda: self._initiative(row_id))
            if not row.is_event:
                menu.add_command(label="Change HP / AC…", command=lambda: StatsPopover(
                    self.winfo_toplevel(), (x, y), self.backend, row))
                menu.add_command(label="Conditions…", command=lambda: ConditionsPopover(
                    self.winfo_toplevel(), (x, y), self.backend, row_id))
                menu.add_command(label="Notes (only you see these)…", command=lambda: PromptDialog(
                    self.winfo_toplevel(), "Notes", f"Notes for {row.name}:", row.notes,
                    lambda text: self._do({"type": "set_field", "id": row_id, "field": "notes", "value": text}),
                    multiline=True))
            menu.add_separator()
        rows = [r for r in self.table.view.rows if r.id in ids]
        hide = not all(r.hidden for r in rows)
        menu.add_command(label="Hide from players" if hide else "Show to players",
                         command=lambda: self._do({"type": "set_hidden", "ids": ids, "hidden": hide}))
        if not all(r.is_event for r in rows):
            defeated = not all(r.defeated for r in rows)
            menu.add_command(label="Mark defeated" if defeated else "Restore",
                             command=lambda: [self._do({"type": "set_field", "id": i, "field": "defeated",
                                                        "value": defeated}) for i in ids])
            for title, field, choices in (
                    ("HP shown to players", "hp_mode", (("Follow the setting", None), ("Exact numbers", "number"),
                                                        ("Health bar", "bar"), ("Hidden", "hidden"))),
                    ("AC shown to players", "ac_mode", (("Follow the setting", None), ("Shown", "shown"),
                                                        ("Hidden", "hidden")))):
                sub = self._menu()
                for text, value in choices:
                    sub.add_command(label=text, command=lambda v=value, f=field: [
                        self._do({"type": "set_field", "id": i, "field": f, "value": v}) for i in ids])
                menu.add_cascade(label=title, menu=sub)
        menu.add_separator()
        if many and len(ids) >= 2:
            menu.add_command(label="Group these", command=self._group)
        if any(r.group for r in rows):
            menu.add_command(label="Ungroup", command=self._ungroup)
        if not many and row.source.get("type") == "monster":
            menu.add_command(label="View stat block", command=lambda: self._stat_block(row.source.get("name", "")))
        menu.add_separator()
        menu.add_command(label="Remove", command=lambda: (self._do({"type": "remove", "ids": ids}),
                                                          self.table.clear_selection()))
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _stat_block(self, name: str):
        try:
            from ui.object_link_widgets import open_link_popup
            open_link_popup(self.winfo_toplevel(), "monster", name)
        except Exception as e:
            messagebox.showwarning("Stat block", f"Could not open it: {e}", parent=self.winfo_toplevel())
