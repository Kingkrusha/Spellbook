"""The initiative pop-up: a resizable window that stays on top of everything, even when it isn't the
focused window, so a player can keep an eye on the turn order while using other apps.

It is a view of one backend: a player's own view (they edit their own HP, AC and conditions), the DM's
view on a second monitor (with a Next turn button), or the DM previewing what a player sees.

Position, size, pinning, opacity and compact mode are remembered per kind of window.
"""

from __future__ import annotations

import json
import sys
from typing import Callable, Optional

import customtkinter as ctk

import initiative_sources as S
import initiative_state as T
from theme import get_theme_manager
from typography import ui_font
from ui.initiative_dialogs import ConditionsPopover, StatsPopover
from ui.initiative_table import InitiativeTable, TableCallbacks

DEFAULT_GEOMETRY = "460x420"
MIN_W, MIN_H = 300, 180


def _flash(window) -> None:
    """Windows: make the taskbar button blink until the window is used (a no-op elsewhere)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("hwnd", wintypes.HWND), ("dwFlags", wintypes.DWORD),
                        ("uCount", wintypes.UINT), ("dwTimeout", wintypes.DWORD)]

        hwnd = ctypes.windll.user32.GetAncestor(window.winfo_id(), 2)
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x0003 | 0x000C, 3, 0)   # tray + caption, until focus
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


class InitiativeWindow(ctk.CTkToplevel):
    def __init__(self, parent, backend, settings_manager=None, kind: str = "player",
                 title: str = "Initiative", get_managers: Optional[Callable[[], object]] = None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.backend = backend
        self.settings_manager = settings_manager
        self.kind = kind
        self.get_managers = get_managers
        self._was_my_turn = False
        self._save_after = None
        self._closing = False

        saved = self._load_state()
        self.pinned = bool(saved.get("pinned", True))
        self.compact = bool(saved.get("compact", False))
        self.alpha = float(saved.get("alpha", 1.0))

        self.title(title)
        self.minsize(MIN_W, MIN_H)
        self.geometry(self._usable_geometry(saved.get("geo") or DEFAULT_GEOMETRY))
        self.protocol("WM_DELETE_WINDOW", self.close)

        t = self.theme
        top = ctk.CTkFrame(self, fg_color=t.get_current_color('bg_secondary'), corner_radius=0)
        top.pack(fill="x")
        self.banner = ctk.CTkLabel(top, text="", font=ui_font("heading", 16, bold=True), anchor="w")
        self.banner.pack(side="left", padx=10, pady=6)

        tools = ctk.CTkFrame(top, fg_color="transparent")
        tools.pack(side="right", padx=6)
        self.pin_btn = ctk.CTkButton(tools, text="", width=34, height=26, command=self._toggle_pin,
                                     fg_color=t.get_current_color('button_normal'),
                                     hover_color=t.get_current_color('button_hover'))
        self.pin_btn.pack(side="right", padx=2)
        self.compact_btn = ctk.CTkButton(tools, text="", width=34, height=26, command=self._toggle_compact,
                                         fg_color=t.get_current_color('button_normal'),
                                         hover_color=t.get_current_color('button_hover'))
        self.compact_btn.pack(side="right", padx=2)
        self.alpha_slider = ctk.CTkSlider(tools, from_=0.4, to=1.0, width=70, command=self._set_alpha)
        self.alpha_slider.set(self.alpha)
        self.alpha_slider.pack(side="right", padx=(2, 8))

        # (an empty CTkFrame is 200 px tall by default; height=0 lets it collapse when it has no buttons)
        self.action_row = ctk.CTkFrame(self, fg_color="transparent", height=0)
        self.action_row.pack(fill="x", padx=8, pady=(6, 0))
        self.add_btn = ctk.CTkButton(self.action_row, text="＋ Add my character", height=28,
                                     fg_color=t.get_current_color('accent_primary'),
                                     hover_color=t.get_current_color('accent_hover'), command=self._add_me)
        self.next_btn = ctk.CTkButton(self.action_row, text="▶▶ Next turn", height=28,
                                      fg_color=t.get_current_color('accent_primary'),
                                      hover_color=t.get_current_color('accent_hover'),
                                      command=lambda: self._run({"type": "next_turn"}))

        self.table = InitiativeTable(self, backend, TableCallbacks(
            on_stats=self._stats, on_conditions=self._conditions, on_add_me=self._add_me),
            compact=self.compact)
        self.table.pack(fill="both", expand=True, padx=8, pady=8)

        backend.listen(self._on_change)
        self._refresh_chrome()
        self._on_change(first=True)

        # CustomTkinter finishes setting up a window ~200 ms after creating it, and would undo an
        # earlier "topmost"; apply ours after that, and once more in case it was slower.
        for ms in (320, 800):
            self.after(ms, self._apply_pin)
        self.bind("<Configure>", self._on_configure, add="+")

    # ------------------------------------------------------------------ saved state

    def _all_state(self) -> dict:
        try:
            data = json.loads(getattr(self.settings_manager.settings, "tracker_window_state", "") or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_state(self) -> dict:
        state = self._all_state().get(self.kind)
        return state if isinstance(state, dict) else {}

    def _save_state(self):
        self._save_after = None
        if self.settings_manager is None or self._closing:
            return
        try:
            data = self._all_state()
            data[self.kind] = {"geo": self.geometry(), "pinned": self.pinned, "compact": self.compact,
                               "alpha": round(self.alpha, 2)}
            self.settings_manager.update(tracker_window_state=json.dumps(data))
        except Exception:
            pass

    def _save_soon(self):
        if self._save_after is None:
            self._save_after = self.after(700, self._save_state)

    def _on_configure(self, event):
        if event.widget is self:
            self._save_soon()

    def _usable_geometry(self, geo: str) -> str:
        """A saved position might be on a monitor that has since been unplugged: keep it on screen."""
        try:
            size, _, rest = geo.partition("+")
            if not rest:
                return geo
            x, _, y = rest.partition("+")
            w, h = (int(v) for v in size.split("x"))
            x, y = int(x), int(y)
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            x = max(0, min(x, sw - 80))
            y = max(0, min(y, sh - 80))
            return f"{min(w, sw)}x{min(h, sh)}+{x}+{y}"
        except Exception:
            return DEFAULT_GEOMETRY

    # ------------------------------------------------------------------ window behaviour

    def _apply_pin(self):
        if self._closing:
            return
        try:
            self.attributes("-topmost", bool(self.pinned))
            self.attributes("-alpha", self.alpha)
        except Exception:
            pass

    def _toggle_pin(self):
        self.pinned = not self.pinned
        self._apply_pin()
        self._refresh_chrome()
        self._save_soon()

    def _toggle_compact(self):
        self.compact = not self.compact
        self.table.set_compact(self.compact)
        self._refresh_chrome()
        self._save_soon()

    def _set_alpha(self, value):
        self.alpha = float(value)
        self._apply_pin()
        self._save_soon()

    def _refresh_chrome(self):
        self.pin_btn.configure(text="📌" if self.pinned else "📍")
        self.compact_btn.configure(text="▤" if self.compact else "▦")

    def close(self):
        self._save_state()
        self._closing = True
        try:
            self.backend.unlisten(self._on_change)
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------------------ content

    def _on_change(self, first: bool = False):
        if self._closing or not self.winfo_exists():
            return
        tv = self.backend.table()
        t = self.theme
        mine_active = any(r.active and r.mine for r in tv.rows)
        if tv.role == "dm":
            text = f"Round {tv.round}" if tv.started else "Not started"
        elif mine_active:
            text = "▶  YOUR TURN"
        elif tv.started:
            current = next((r for r in tv.rows if r.active), None)
            text = f"Round {tv.round}" + (f"  ·  {current.name}'s turn" if current else "")
        else:
            text = "Waiting to start"
        self.banner.configure(text=text, text_color="#3fb950" if mine_active
                              else t.get_current_color('text_primary'))
        self.title(("▶ YOUR TURN - " if mine_active else "") + "Initiative")

        if mine_active and not self._was_my_turn and not first:
            self._your_turn()
        self._was_my_turn = mine_active

        # the buttons that make sense for this viewer
        for b in (self.add_btn, self.next_btn):
            b.pack_forget()
        if tv.role == "dm":
            self.next_btn.configure(text="▶▶ Next turn" if tv.started else "▶ Start")
            self.next_btn.pack(side="left")
        elif tv.can_add and tv.my_count == 0:
            self.add_btn.pack(side="left")

    def _your_turn(self):
        """The turn came round to one of this player's characters. Visible without taking focus."""
        try:
            if bool(getattr(self.settings_manager.settings, "tracker_turn_beep", True)):
                self.bell()
        except Exception:
            pass
        _flash(self)

    # ------------------------------------------------------------------ actions

    def _run(self, cmd: dict):
        try:
            self.backend.dispatch(cmd)
        except T.CommandError as e:
            from tkinter import messagebox
            messagebox.showwarning("Initiative", e.message, parent=self)

    def _stats(self, row_id: str, anchor):
        row = self.table.row_of(row_id)
        if row:
            StatsPopover(self, anchor, self.backend, row)

    def _conditions(self, row_id: str, anchor):
        ConditionsPopover(self, anchor, self.backend, row_id)

    def _add_me(self):
        """Put one of this player's characters into the order (their own HP and AC, copied now)."""
        from ui.initiative_dialogs import AddMyCharacterDialog
        AddMyCharacterDialog(self, self.backend, self.get_managers)
