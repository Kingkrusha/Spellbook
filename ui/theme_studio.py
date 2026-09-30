"""
Theme Studio: browse every colour theme, and create/edit custom ones.

Clicking a theme applies it to the whole app straight away (the window stays
open beside the app, so edits are visible live). Custom themes are editable
colour by colour, separately for light and dark mode, with a mock-up that shows
the result.
"""

import json
from tkinter import filedialog, messagebox
from typing import Callable, Dict, Optional

import customtkinter as ctk

from settings import get_settings_manager
from theme import (COLOR_GROUPS, ThemeColors, get_theme_manager, is_custom_key)
from typography import ui_font
from ui.busy import run_busy
from ui.color_picker import ColorSwatch, ask_color
from ui.restyle import flush_restyle


class ThemePreview(ctk.CTkFrame):
    """A small mock-up of the app painted with an arbitrary ThemeColors."""

    def __init__(self, parent):
        super().__init__(parent, corner_radius=10, border_width=1)
        self.window = ctk.CTkFrame(self, corner_radius=8)
        self.window.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_bar = ctk.CTkFrame(self.window, corner_radius=0, height=34)
        self.tab_bar.pack(fill="x")
        self.tab_active = ctk.CTkLabel(self.tab_bar, text="Spells", corner_radius=6, width=80, height=24,
                                       font=ui_font("small", bold=True))
        self.tab_active.pack(side="left", padx=(8, 4), pady=5)
        self.tab_idle = ctk.CTkLabel(self.tab_bar, text="Characters", width=90, height=24,
                                     font=ui_font("small"))
        self.tab_idle.pack(side="left", padx=4, pady=5)

        self.body = ctk.CTkFrame(self.window, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=10, pady=8)

        self.card = ctk.CTkFrame(self.body, corner_radius=8)
        self.card.pack(fill="x")
        self.heading = ctk.CTkLabel(self.card, text="Fireball", anchor="w", font=ui_font("heading", bold=True))
        self.heading.pack(fill="x", padx=12, pady=(10, 0))
        self.sub = ctk.CTkLabel(self.card, text="3rd-level evocation", anchor="w",
                                font=ui_font("small"))
        self.sub.pack(fill="x", padx=12)
        field_row = ctk.CTkFrame(self.card, fg_color="transparent")
        field_row.pack(fill="x", padx=12, pady=(4, 0))
        self.field_label = ctk.CTkLabel(field_row, text="Casting Time:", font=ui_font("body", bold=True))
        self.field_label.pack(side="left")
        self.field_value = ctk.CTkLabel(field_row, text="1 action", font=ui_font("body"))
        self.field_value.pack(side="left", padx=(6, 0))
        self.text = ctk.CTkLabel(self.card, anchor="w", justify="left", wraplength=300,
                                 text="A bright streak flashes from your finger, then blossoms into an explosion of flame.",
                                 font=ui_font("body"))
        self.text.pack(fill="x", padx=12, pady=(6, 0))
        self.link = ctk.CTkLabel(self.card, text="See also: Delayed Blast Fireball", anchor="w",
                                 font=ui_font("body", underline=True))
        self.link.pack(fill="x", padx=12, pady=(4, 0))
        self.warn = ctk.CTkLabel(self.card, text="Encumbered: speed reduced", anchor="w", font=ui_font("small"))
        self.warn.pack(fill="x", padx=12, pady=(2, 8))

        buttons = ctk.CTkFrame(self.body, fg_color="transparent")
        buttons.pack(fill="x", pady=(8, 0))
        self.btn_normal = ctk.CTkButton(buttons, text="Button", width=70, height=26)
        self.btn_accent = ctk.CTkButton(buttons, text="Accent", width=70, height=26)
        self.btn_danger = ctk.CTkButton(buttons, text="Delete", width=70, height=26)
        self.btn_success = ctk.CTkButton(buttons, text="Save", width=70, height=26)
        for b in (self.btn_normal, self.btn_accent, self.btn_danger, self.btn_success):
            b.pack(side="left", padx=(0, 6))

        self.entry = ctk.CTkEntry(self.body, placeholder_text="Search…", height=28)
        self.entry.pack(fill="x", pady=(8, 0))

        self.chips_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        self.chips_frame.pack(fill="x", pady=(8, 0))
        self.chips = []
        for i, name in enumerate(["C", "1", "2", "3", "4", "5", "6", "7", "8", "9"]):
            chip = ctk.CTkLabel(self.chips_frame, text=name, width=24, height=20, corner_radius=4,
                                font=ui_font("small", bold=True))
            chip.pack(side="left", padx=1)
            self.chips.append(chip)

    def _set(self, widget, **options):
        """configure() only what changed - every configure redraws the widget, and a
        colour drag changes one or two colours out of thirty."""
        applied = self._applied.setdefault(id(widget), {})
        changed = {k: v for k, v in options.items() if applied.get(k) != v}
        if changed:
            applied.update(changed)
            widget.configure(**changed)

    def show(self, colors: ThemeColors, mode: str):
        if not hasattr(self, "_applied"):
            self._applied = {}
        i = 0 if mode == "light" else 1
        c = lambda name: getattr(colors, name)[i]
        self._set(self, fg_color=c("bg_primary"), border_color=c("border"))
        self._set(self.window, fg_color=c("bg_primary"))
        self._set(self.tab_bar, fg_color=c("tab_bar"))
        self._set(self.tab_active, fg_color=c("accent_primary"), text_color=c("text_on_accent"))
        self._set(self.tab_idle, text_color=c("text_secondary"))
        self._set(self.card, fg_color=c("bg_secondary"))
        self._set(self.heading, text_color=c("text_primary"))
        self._set(self.sub, text_color=c("text_secondary"))
        self._set(self.text, text_color=c("text_primary"))
        self._set(self.field_label, text_color=c("text_label"))
        self._set(self.field_value, text_color=c("text_primary"))
        self._set(self.link, text_color=c("spell_link"))
        self._set(self.warn, text_color=c("text_warning"))
        for btn, bg, hv, fg in (
            (self.btn_normal, "button_normal", "button_hover", "text_primary"),
            (self.btn_accent, "accent_primary", "accent_hover", "text_on_accent"),
            (self.btn_danger, "button_danger", "button_danger_hover", "text_on_accent"),
            (self.btn_success, "button_success", "button_success_hover", "text_on_accent"),
        ):
            self._set(btn, fg_color=c(bg), hover_color=c(hv), text_color=c(fg))
        self._set(self.entry, fg_color=c("bg_input"), border_color=c("border"), text_color=c("text_primary"),
                  placeholder_text_color=c("text_secondary"))
        names = ["level_cantrip"] + [f"level_{n}" for n in range(1, 10)]
        for chip, name in zip(self.chips, names):
            self._set(chip, fg_color=c(name), text_color=c("text_primary"))


class ThemeStudioDialog(ctk.CTkToplevel):
    """Non-modal window for picking and editing colour themes."""

    def __init__(self, parent, on_theme_applied: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.title("Theme Studio")
        self.geometry("1060x720")
        self.minsize(900, 560)
        self.tm = get_theme_manager()
        self.settings_manager = get_settings_manager()
        self._on_theme_applied = on_theme_applied
        self._variant = "light" if ctk.get_appearance_mode().lower() == "light" else "dark"
        self._selected = self.tm.current_theme_name
        self._swatches: Dict[str, ColorSwatch] = {}
        self._hex_labels: Dict[str, ctk.CTkLabel] = {}
        self._list_rows: Dict[str, ctk.CTkFrame] = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_list_panel()
        self._build_editor_panel()
        self._rebuild_list()
        self._load_editor()
        self.tm.add_listener(self._on_external_theme_change)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(150, self.lift)

    def _close(self):
        self.tm.remove_listener(self._on_external_theme_change)
        self.destroy()

    # -- left: theme list ------------------------------------------------------

    def _build_list_panel(self):
        left = ctk.CTkFrame(self, width=290, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsw")
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="Themes", font=ui_font("heading", bold=True)).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        self.list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=6)
        bottom = ctk.CTkFrame(left, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(bottom, text="+ New theme", command=self._new_theme).pack(fill="x")
        ctk.CTkButton(bottom, text="Import…", height=26, command=self._import_theme,
                      fg_color="transparent", border_width=1).pack(fill="x", pady=(6, 0))

    def _mini_strip(self, parent, colors: ThemeColors):
        i = 0 if ctk.get_appearance_mode().lower() == "light" else 1
        strip = ctk.CTkFrame(parent, fg_color="transparent")
        for name in ("bg_primary", "bg_secondary", "accent_primary", "text_primary"):
            ctk.CTkFrame(strip, width=14, height=22, corner_radius=4, border_width=1,
                         border_color=colors.border[i],
                         fg_color=getattr(colors, name)[i]).pack(side="left", padx=1)
        return strip

    def _rebuild_list(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._list_rows.clear()
        themes = self.tm.list_themes()
        custom = [t for t in themes if t[2]]
        builtin = [t for t in themes if not t[2]]
        if custom:
            self._list_heading("My themes")
            for key, name, _ in custom:
                self._list_row(key, name)
        self._list_heading("Built-in themes")
        for key, name, _ in builtin:
            self._list_row(key, name)

    def _list_heading(self, text: str):
        ctk.CTkLabel(self.list_frame, text=text.upper(), anchor="w", font=ui_font("small", bold=True),
                     text_color=self.tm.get_current_color("text_secondary")).pack(fill="x", padx=8, pady=(10, 2))

    def _list_row(self, key: str, name: str):
        selected = key == self._selected
        row = ctk.CTkFrame(self.list_frame, corner_radius=8, height=38,
                           fg_color=self.tm.get_current_color("accent_primary") if selected else "transparent")
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)
        strip = self._mini_strip(row, self.tm.get_theme_colors(key))
        strip.pack(side="left", padx=(8, 8))
        label = ctk.CTkLabel(row, text=name, anchor="w", font=ui_font("body", bold=selected),
                             text_color=self.tm.get_current_color("text_on_accent" if selected else "text_primary"))
        label.pack(side="left", fill="x", expand=True)
        for w in (row, strip, label) + tuple(strip.winfo_children()):
            w.bind("<Button-1>", lambda e, k=key: self._select(k))
        self._list_rows[key] = row

    # -- right: editor ---------------------------------------------------------

    def _build_editor_panel(self):
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=14, pady=12)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(right, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        self.name_var = ctk.StringVar()
        self.name_entry = ctk.CTkEntry(top, textvariable=self.name_var, width=240, height=32,
                                       font=ui_font("subheading", bold=True))
        self.name_entry.pack(side="left")
        self.name_entry.bind("<Return>", lambda e: self._commit_name())
        self.name_entry.bind("<FocusOut>", lambda e: self._commit_name())
        self.variant_switch = ctk.CTkSegmentedButton(top, values=["Light", "Dark"], width=150,
                                                     command=self._on_variant)
        self.variant_switch.set(self._variant.title())
        self.variant_switch.pack(side="right")
        ctk.CTkLabel(top, text="Editing:", font=ui_font("small"),
                     text_color=self.tm.get_current_color("text_secondary")).pack(side="right", padx=(0, 8))

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        self.duplicate_btn = ctk.CTkButton(actions, text="Duplicate", width=90, height=28,
                                           command=self._duplicate)
        self.duplicate_btn.pack(side="left")
        self.export_btn = ctk.CTkButton(actions, text="Export…", width=80, height=28,
                                        command=self._export, fg_color="transparent", border_width=1)
        self.export_btn.pack(side="left", padx=6)
        self.delete_btn = ctk.CTkButton(actions, text="Delete", width=80, height=28, command=self._delete,
                                        fg_color=self.tm.get_current_color("button_danger"),
                                        hover_color=self.tm.get_current_color("button_danger_hover"),
                                        text_color="#ffffff")
        self.delete_btn.pack(side="left")
        self.note_label = ctk.CTkLabel(actions, text="", font=ui_font("small"), anchor="e",
                                       text_color=self.tm.get_current_color("text_warning"))
        self.note_label.pack(side="right")

        body = ctk.CTkFrame(right, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_rowconfigure(0, weight=1)
        self.colors_frame = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self.colors_frame.grid(row=0, column=0, sticky="nsew")
        preview_col = ctk.CTkFrame(body, fg_color="transparent", width=340)
        preview_col.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        ctk.CTkLabel(preview_col, text="Preview", font=ui_font("subheading", bold=True), anchor="w").pack(fill="x")
        self.preview = ThemePreview(preview_col)
        self.preview.pack(fill="x", pady=(6, 0))
        self._build_color_rows()

    def _build_color_rows(self):
        muted = self.tm.get_current_color("text_secondary")
        for group, entries in COLOR_GROUPS.items():
            ctk.CTkLabel(self.colors_frame, text=group.upper(), anchor="w", font=ui_font("small", bold=True),
                         text_color=muted).pack(fill="x", padx=4, pady=(12, 2))
            grid = ctk.CTkFrame(self.colors_frame, fg_color="transparent")
            grid.pack(fill="x")
            grid.grid_columnconfigure((0, 1), weight=1, uniform="cols")
            for i, (role, label) in enumerate(entries):
                cell = ctk.CTkFrame(grid, fg_color="transparent")
                cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=4, pady=2)
                swatch = ColorSwatch(cell, "#808080", command=lambda r=role: self._pick(r), width=38, height=26)
                swatch.pack(side="left")
                text = ctk.CTkFrame(cell, fg_color="transparent")
                text.pack(side="left", padx=8)
                ctk.CTkLabel(text, text=label, anchor="w", font=ui_font("body")).pack(anchor="w")
                hx = ctk.CTkLabel(text, text="", anchor="w", font=ui_font("small"), text_color=muted)
                hx.pack(anchor="w")
                self._swatches[role] = swatch
                self._hex_labels[role] = hx

    # -- state ------------------------------------------------------------------

    def _colors(self) -> ThemeColors:
        return self.tm.get_theme_colors(self._selected)

    def _is_custom(self) -> bool:
        return is_custom_key(self._selected)

    def _load_editor(self):
        colors = self._colors()
        i = 0 if self._variant == "light" else 1
        custom = self._is_custom()
        self.name_var.set(self.tm.display_name(self._selected))
        self.name_entry.configure(state="normal" if custom else "disabled")
        self.delete_btn.configure(state="normal" if custom else "disabled")
        self.note_label.configure(
            text="" if custom else "Built-in theme – duplicate it to change colours")
        for role, swatch in self._swatches.items():
            value = getattr(colors, role)[i]
            swatch.set_color(value)
            swatch.configure(state="normal" if custom else "disabled")
            self._hex_labels[role].configure(text=value)
        self.preview.show(colors, self._variant)

    def _select(self, key: str):
        self._commit_name()
        self._selected = key

        def apply():
            self.tm.set_theme(key)
            self.settings_manager.update(theme_name=key)
            flush_restyle()

        run_busy("theme", "Applying theme…", apply)
        if self._on_theme_applied:
            self._on_theme_applied(key)
        self._rebuild_list()
        self._load_editor()

    def _on_external_theme_change(self):
        """The theme changed elsewhere (settings dropdown, restyle...)."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if self.tm.current_theme_name != self._selected:
            self._selected = self.tm.current_theme_name
            self._rebuild_list()
            self._load_editor()

    def _on_variant(self, value: str):
        self._variant = value.lower()
        self._load_editor()

    # -- editing ----------------------------------------------------------------

    def _pick(self, role: str):
        if not self._is_custom():
            return
        key = self._selected
        light = self._variant == "light"
        initial = getattr(self._colors(), role)[0 if light else 1]

        def live(color: str):
            # cheap: the swatch and the preview panel follow the picker...
            self.tm.set_custom_color(key, role, light=color if light else None,
                                     dark=None if light else color, notify=False, save=False)
            self._swatches[role].set_color(color)
            self._hex_labels[role].configure(text=color)
            self.preview.show(self._colors(), self._variant)

        def settle(color: str):
            # ...and the whole app is recoloured once the colour stops moving
            def apply():
                self.tm.notify()
                flush_restyle()
            run_busy("theme", "Applying colour…", apply)

        swatches = []
        colors = self._colors()
        i = 0 if light else 1
        for name in ("bg_primary", "bg_secondary", "bg_tertiary", "accent_primary", "text_primary",
                     "text_secondary", "button_normal", "spell_link"):
            swatches.append((name, getattr(colors, name)[i]))
        status, _ = ask_color(self, initial, title=f"Choose a colour – {self._label(role)}",
                              on_change=live, on_settle=settle, swatches=swatches)
        self.tm.save_custom_themes()
        self._load_editor()

    @staticmethod
    def _label(role: str) -> str:
        from theme import ROLE_LABELS
        return ROLE_LABELS.get(role, role)

    def _commit_name(self):
        if not self._is_custom():
            return
        name = self.name_var.get().strip()
        if name and name != self.tm.display_name(self._selected):
            self.tm.rename_custom_theme(self._selected, name)
            self.name_var.set(self.tm.display_name(self._selected))
            self._rebuild_list()
            self._notify_settings()

    def _notify_settings(self):
        if self._on_theme_applied:
            self._on_theme_applied(self._selected)

    # -- theme management --------------------------------------------------------

    def _new_theme(self):
        dialog = ctk.CTkInputDialog(text="Name for the new theme (it starts as a copy of the selected one):",
                                    title="New theme")
        name = dialog.get_input()
        if name is None:
            return
        key = self.tm.create_custom_theme(name.strip() or "My Theme", self._selected)
        self._select(key)

    def _duplicate(self):
        name = self.tm.display_name(self._selected) + " copy"
        key = self.tm.create_custom_theme(name, self._selected)
        self._select(key)

    def _delete(self):
        if not self._is_custom():
            return
        name = self.tm.display_name(self._selected)
        if not messagebox.askyesno("Delete theme", f"Delete the theme “{name}”? This cannot be undone.",
                                   parent=self):
            return
        self.tm.delete_custom_theme(self._selected)
        self._selected = self.tm.current_theme_name
        self.settings_manager.update(theme_name=self._selected)
        self._rebuild_list()
        self._load_editor()
        self._notify_settings()

    def _export(self):
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".json", filetypes=[("Spellbook theme", "*.json")],
            initialfile=self.tm.display_name(self._selected).replace(" ", "_") + ".json")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.tm.export_theme(self._selected), f, indent=2)
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self)

    def _import_theme(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Spellbook theme", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                key = self.tm.import_theme(json.load(f))
        except Exception as e:
            messagebox.showerror("Import failed", f"Could not read that theme:\n{e}", parent=self)
            return
        if key is None:
            messagebox.showerror("Import failed", "That file isn't a Spellbook theme.", parent=self)
            return
        self._select(key)
