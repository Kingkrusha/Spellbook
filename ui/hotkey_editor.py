"""
Settings > Keyboard Shortcuts: see and change every shortcut (hotkeys.py).

One group of actions is shown at a time (picked from a drop-down), which keeps
the number of widgets small. Clicking a shortcut opens a small window that
records the next key combination pressed.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

import hotkeys
from theme import get_theme_manager
from typography import ui_font


class KeyCaptureDialog(ctk.CTkToplevel):
    """Waits for a key combination. ``result`` is the key, "" to clear, or None if cancelled."""

    def __init__(self, parent, action: hotkeys.Action, table: dict):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.action = action
        self.table = table
        self.result: Optional[str] = None
        self._key = ""

        self.title("Change Shortcut")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)
        ctk.CTkLabel(body, text=f"Press the new shortcut for “{action.label}”",
                     font=ui_font("subheading")).pack(anchor="w")
        self._key_label = ctk.CTkLabel(body, text="…", font=ui_font("heading", 18, bold=True))
        self._key_label.pack(pady=(12, 4))
        self._note = ctk.CTkLabel(body, text="Esc cancels.", font=ui_font("small"),
                                  text_color=self.theme.get_text_secondary(), wraplength=320,
                                  justify="center")
        self._note.pack(pady=(0, 12))

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        self._save_btn = ctk.CTkButton(buttons, text="Save", width=90, state="disabled",
                                       command=self._save)
        self._save_btn.pack(side="right")
        ctk.CTkButton(buttons, text="No shortcut", width=110,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'),
                      command=self._clear).pack(side="right", padx=(0, 8))
        ctk.CTkButton(buttons, text="Cancel", width=90,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'),
                      command=self.destroy).pack(side="left")

        self.bind("<KeyPress>", self._on_key)
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def _on_key(self, event):
        if event.keysym == "Escape" and not (event.state & 0x000D):
            self.destroy()
            return "break"
        key = hotkeys.from_event(event.keysym, event.state)
        if not key:
            return "break"
        self._key = key
        self._key_label.configure(text=hotkeys.display(key))
        if key in hotkeys.RESERVED:
            self._note.configure(text="That key is kept for copy, paste, undo and so on.")
            self._save_btn.configure(state="disabled")
        elif not hotkeys.is_usable(key):
            self._note.configure(text="Use Ctrl or Alt with the key (function keys work alone).")
            self._save_btn.configure(state="disabled")
        else:
            owner = next((a for a, k in self.table.items() if k == key and a != self.action.id), None)
            if owner:
                self._note.configure(
                    text=f"Already used by “{hotkeys.ACTIONS_BY_ID[owner].label}”, "
                         "which will lose it.")
            else:
                self._note.configure(text="")
            self._save_btn.configure(state="normal")
        return "break"

    def _save(self):
        self.result = self._key
        self.destroy()

    def _clear(self):
        self.result = ""
        self.destroy()


class HotkeyEditor(ctk.CTkFrame):
    """The list of shortcuts in one group, with a drop-down to pick the group."""

    def __init__(self, parent, settings_manager, on_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.settings_manager = settings_manager
        self.on_changed = on_changed
        self.theme = get_theme_manager()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
        self._group_var = ctk.StringVar(value=hotkeys.GROUPS[0])
        ctk.CTkOptionMenu(top, values=hotkeys.GROUPS, variable=self._group_var, width=180,
                          command=lambda _v: self._show_group()).pack(side="left")
        ctk.CTkButton(top, text="Reset All Shortcuts", width=160,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'),
                      text_color=self.theme.get_current_color('text_primary'),
                      command=self._reset_all).pack(side="right")

        self._rows = ctk.CTkFrame(self, fg_color="transparent")
        self._rows.pack(fill="x")
        self._show_group()

    # -- data

    @property
    def overrides(self) -> dict:
        return dict(getattr(self.settings_manager.settings, 'hotkeys', {}) or {})

    def _store(self, overrides: dict):
        self.settings_manager.update(hotkeys=overrides)
        manager = hotkeys.get_manager()
        if manager is not None:
            manager.apply(overrides)
        if self.on_changed:
            self.on_changed()
        self._show_group()

    # -- view

    def refresh(self):
        self._show_group()

    def _show_group(self):
        for child in self._rows.winfo_children():
            child.destroy()
        table = hotkeys.bindings(self.overrides)
        secondary = self.theme.get_text_secondary()
        for action in hotkeys.actions_in(self._group_var.get()):
            key = table.get(action.id, "")
            row = ctk.CTkFrame(self._rows, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=action.label, font=ui_font("subheading"), anchor="w").pack(side="left")
            changed = key != hotkeys.normalize(action.default)
            if changed:
                ctk.CTkButton(row, text="↺", width=30,
                              fg_color="transparent", text_color=secondary,
                              hover_color=self.theme.get_current_color('button_hover'),
                              command=lambda a=action.id: self._reset(a)).pack(side="right", padx=(6, 0))
            ctk.CTkButton(row, text=hotkeys.display(key) or "None", width=150,
                          fg_color=self.theme.get_current_color('button_normal'),
                          hover_color=self.theme.get_current_color('button_hover'),
                          text_color=self.theme.get_current_color('text_primary') if key else secondary,
                          command=lambda a=action: self._edit(a)).pack(side="right")

    def _edit(self, action: hotkeys.Action):
        dialog = KeyCaptureDialog(self, action, hotkeys.bindings(self.overrides))
        self.wait_window(dialog)
        if dialog.result is None:
            return
        self._store(hotkeys.set_binding(self.overrides, action.id, dialog.result))

    def _reset(self, action_id: str):
        self._store(hotkeys.reset_binding(self.overrides, action_id))

    def _reset_all(self):
        self._store({})
