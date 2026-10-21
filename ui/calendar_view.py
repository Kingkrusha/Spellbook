"""
Calendar page (Game Tools): each campaign's calendar and clock.

The current date and time sit at the top with buttons that move the clock on (10 minutes, an hour, a long
rest, a day, a week, or any amount). Below, the month is drawn on one canvas (holidays and events written in
their days); beside it are the selected day's events and the campaign's progress trackers, whose bars move
on with the clock unless they are set to manual.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from calendar_state import (PRESETS, UNITS, Campaign, CalendarConfig, Event, Tracker, get_calendar_store,
                            new_campaign, parse_months)
from theme import get_theme_manager
from typography import ui_font
from ui.theme_listener import ThemeListenerMixin
from ui.window_utils import add_cancel_save, center_on_parent

ADVANCE_UNITS = ["minutes", "hours", "days", "weeks"]
SAVE_DELAY_MS = 600


def _color(theme, role: str) -> str:
    value = theme.get_current_color(role)
    return value[1] if isinstance(value, tuple) else str(value)


# --------------------------------------------------------------------------- #
# Small form dialog
# --------------------------------------------------------------------------- #

class FormDialog(ctk.CTkToplevel):
    """A dialog of labelled fields. ``fields``: (key, label, kind, default[, options]) with kind one of
    "entry", "check", "option", "text". ``validate(values)`` returns an error message or None."""

    def __init__(self, parent, title: str, fields: list, validate: Optional[Callable[[dict], Optional[str]]] = None,
                 hint: str = "", width: int = 460, confirm: str = "Save"):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.title(title)
        self.transient(parent)
        self.resizable(True, True)
        self.result: Optional[dict] = None
        self._validate = validate
        self._getters = {}

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=18)
        if hint:
            ctk.CTkLabel(frame, text=hint, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                         justify="left", wraplength=width - 40).pack(anchor="w", pady=(0, 8))
        first = None
        for spec in fields:
            key, label, kind, default = spec[:4]
            options = spec[4] if len(spec) > 4 else None
            if kind == "check":
                var = ctk.BooleanVar(value=bool(default))
                ctk.CTkCheckBox(frame, text=label, variable=var).pack(anchor="w", pady=(4, 6))
                self._getters[key] = var.get
                continue
            ctk.CTkLabel(frame, text=label, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
            if kind == "option":
                var = ctk.StringVar(value=str(default))
                ctk.CTkOptionMenu(frame, variable=var, values=list(options)).pack(anchor="w", pady=(0, 8))
                self._getters[key] = var.get
            elif kind == "text":
                box = ctk.CTkTextbox(frame, height=options or 120, wrap="none")
                box.insert("1.0", str(default or ""))
                box.pack(fill="both", expand=True, pady=(0, 8))
                self._getters[key] = lambda b=box: b.get("1.0", "end").strip()
                first = first or box
            else:
                entry = ctk.CTkEntry(frame, width=width - 40)
                entry.insert(0, str(default if default is not None else ""))
                entry.pack(fill="x", pady=(0, 8))
                entry.bind("<Return>", lambda _e: self._ok())
                self._getters[key] = entry.get
                first = first or entry
        self.error_label = ctk.CTkLabel(frame, text="", font=ui_font("small"), justify="left",
                                        wraplength=width - 40,
                                        text_color=self.theme.get_current_color('text_warning'))
        self.error_label.pack(anchor="w")
        bottom = ctk.CTkFrame(frame, fg_color="transparent")
        bottom.pack(fill="x", pady=(8, 0))
        add_cancel_save(bottom, self.theme, self.destroy, self._ok, confirm_text=confirm)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        self.geometry(f"{width}x{max(200, self.winfo_reqheight())}")
        center_on_parent(self, parent, clamp=True)
        self._first = first
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            if self._first is not None:
                self._first.focus_set()
        except tk.TclError:
            pass

    def values(self) -> dict:
        return {k: get() for k, get in self._getters.items()}

    def _ok(self):
        values = self.values()
        error = self._validate(values) if self._validate else None
        if error:
            self.error_label.configure(text=error)
            return
        self.result = values
        self.destroy()


def ask_form(parent, *args, **kwargs) -> Optional[dict]:
    dialog = FormDialog(parent, *args, **kwargs)
    parent.wait_window(dialog)
    return dialog.result


def _int(text, default=None):
    try:
        return int(str(text).strip())
    except ValueError:
        return default


def _float(text, default=None):
    try:
        return float(str(text).strip())
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# The month, drawn on a canvas
# --------------------------------------------------------------------------- #

class MonthCanvas(ThemeListenerMixin, tk.Canvas):
    """One month as a grid of days (a week per row when the month has weekdays)."""

    def __init__(self, parent, on_select: Callable[[Tuple[int, int, int]], None]):
        self.theme = get_theme_manager()
        super().__init__(parent, highlightthickness=0, borderwidth=0, height=360)
        self.on_select = on_select
        self.campaign: Optional[Campaign] = None
        self.year = 1
        self.month = 0
        self.selected: Optional[Tuple[int, int, int]] = None
        self._cells: List[Tuple[int, int, int, int, int]] = []    # x0, y0, x1, y1, day
        self.bind("<Configure>", lambda _e: self.redraw(), add="+")
        self.bind("<Button-1>", self._on_click, add="+")
        self.theme.add_listener(self._on_theme_changed)

    def _on_theme_changed(self):
        self.redraw()

    def show(self, campaign: Optional[Campaign], year: int, month: int,
             selected: Optional[Tuple[int, int, int]] = None):
        self.campaign, self.year, self.month, self.selected = campaign, year, month, selected
        self.redraw()

    def redraw(self):
        try:
            self._draw()
        except tk.TclError:
            pass

    def _draw(self):
        th = self.theme
        self.delete("all")
        self._cells = []
        bg = _color(th, "bg_primary")
        self.configure(bg=bg)
        c = self.campaign
        if c is None:
            return
        cfg = c.config
        m = cfg.months[self.month]
        days = m.length(self.year)
        width, height = max(self.winfo_width(), 200), max(self.winfo_height(), 160)
        pad = 6
        weekdays = cfg.weekdays if (m.moves_weekday and cfg.weekdays) else []
        columns = len(weekdays) if weekdays else min(7, max(1, days))
        head_h = 0
        f_small = ui_font("small")
        f_day = ui_font("body", bold=True)
        if weekdays:
            head_h = f_small.metrics("linespace") + 8
            col_w = (width - 2 * pad) / columns
            for i, name in enumerate(weekdays):
                label = name if f_small.measure(name) < col_w - 6 else name[:3]
                self.create_text(pad + col_w * (i + 0.5), pad + head_h / 2, text=label, font=f_small,
                                 fill=_color(th, "text_secondary"))
        if days <= 0:
            self.create_text(width / 2, height / 2, text=f"{m.name} has no days in {cfg.year_text(self.year)}.",
                             font=ui_font("body"), fill=_color(th, "text_secondary"))
            return
        first_col = cfg.weekday(self.year, self.month, 1) if weekdays else 0
        first_col = first_col or 0
        rows = (first_col + days + columns - 1) // columns
        col_w = (width - 2 * pad) / columns
        row_h = max(34, (height - 2 * pad - head_h) / max(rows, 1))
        today = (c.year, c.month, c.day)
        line = f_small.metrics("linespace")
        for day in range(1, days + 1):
            index = first_col + day - 1
            r, col = divmod(index, columns)
            x0 = pad + col * col_w + 2
            y0 = pad + head_h + r * row_h + 2
            x1, y1 = x0 + col_w - 4, y0 + row_h - 4
            ymd = (self.year, self.month, day)
            events = c.events_on(*ymd)
            fill = _color(th, "bg_tertiary") if ymd == self.selected else _color(th, "bg_secondary")
            outline = _color(th, "accent_primary") if ymd == today else _color(th, "border")
            self.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=3 if ymd == today else 1)
            self.create_text(x0 + 6, y0 + 4, text=str(day) + ("  today" if ymd == today else ""), anchor="nw",
                             font=f_day, fill=_color(th, "text_primary"))
            y = y0 + 4 + f_day.metrics("linespace")
            for e in events:
                if y + line > y1 - 2:
                    self.create_text(x1 - 4, y1 - 2, text="…", anchor="se", font=f_small,
                                     fill=_color(th, "text_secondary"))
                    break
                text = self._fit(("★ " if e.is_holiday else "• ") + e.name, f_small, x1 - x0 - 10)
                self.create_text(x0 + 6, y, text=text, anchor="nw", font=f_small,
                                 fill=_color(th, "accent_secondary" if e.is_holiday else "text_label"))
                y += line
            self._cells.append((int(x0), int(y0), int(x1), int(y1), day))

    @staticmethod
    def _fit(text: str, font, width: float) -> str:
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text + "…" if text else ""

    def _on_click(self, event):
        for x0, y0, x1, y1, day in self._cells:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self.on_select((self.year, self.month, day))
                return


# --------------------------------------------------------------------------- #
# The page
# --------------------------------------------------------------------------- #

class CalendarView(ctk.CTkFrame):
    """The Calendar page."""

    def __init__(self, parent, state: Optional[dict] = None, on_back=None, store=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.state = state if state is not None else {}
        self.store = store or get_calendar_store()
        self.on_back = on_back
        self._save_job: Optional[str] = None
        self._view: Tuple[int, int] = (1, 0)               # the month on screen (year, month)
        self._selected: Optional[Tuple[int, int, int]] = None
        self._tracker_rows: list = []
        self._create_widgets()
        self.refresh()

    def destroy(self):
        self._flush_save()
        super().destroy()

    @property
    def campaign(self) -> Optional[Campaign]:
        return self.store.active

    # ------------------------------------------------------------------ saving

    def _changed(self):
        """Something changed: save soon (a run of clicks on +1 hour is one write)."""
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
        self._save_job = self.after(SAVE_DELAY_MS, self._flush_save)

    def _flush_save(self):
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
            self._save_job = None
            self.store.save()

    # ------------------------------------------------------------------ layout

    def _button(self, parent, text, command, width=90, kind="normal", height=32):
        colors = {"normal": ("button_normal", "button_hover"), "accent": ("accent_primary", "accent_hover"),
                  "danger": ("button_danger", "button_danger_hover")}[kind]
        return ctk.CTkButton(parent, text=text, width=width, height=height, command=command,
                             fg_color=self.theme.get_current_color(colors[0]),
                             hover_color=self.theme.get_current_color(colors[1]),
                             text_color=self.theme.get_current_color(
                                 'text_primary' if kind == "normal" else 'text_on_accent'),
                             text_color_disabled=self.theme.get_text_secondary())

    def _create_widgets(self):
        th = self.theme
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        if self.on_back:
            self._button(header, "← Game Tools", self.on_back, width=120).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(header, text="Calendar", font=ui_font("title", 28, bold=True)).pack(side="left")
        self.delete_btn = self._button(header, "Delete", self._on_delete_campaign, width=70, kind="danger")
        self.delete_btn.pack(side="right")
        self.edit_btn = self._button(header, "Edit Calendar", self._on_edit_campaign, width=110)
        self.edit_btn.pack(side="right", padx=(0, 8))
        self._button(header, "+ New Calendar", self._on_new_campaign, width=120, kind="accent").pack(
            side="right", padx=(0, 8))
        self.campaign_var = ctk.StringVar(value="")
        self.campaign_menu = ctk.CTkOptionMenu(header, variable=self.campaign_var, values=[""], width=200,
                                               command=self._on_pick_campaign)
        self.campaign_menu.pack(side="right", padx=(0, 12))

        self.empty = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.empty, text="No calendars yet", font=ui_font("heading", bold=True)).pack(pady=(60, 6))
        ctk.CTkLabel(self.empty, text="Make one for each campaign: its months, weeks and holidays, the date "
                                      "and time in the game, and trackers for things that take days.",
                     font=ui_font("body"), text_color=th.get_text_secondary(), wraplength=460).pack(pady=(0, 14))
        self._button(self.empty, "+ New Calendar", self._on_new_campaign, width=150, kind="accent").pack()

        self.main = ctk.CTkFrame(self, fg_color="transparent")

        # -- now
        now = ctk.CTkFrame(self.main, fg_color=th.get_current_color('bg_secondary'), corner_radius=12)
        now.pack(fill="x", pady=(0, 10))
        top = ctk.CTkFrame(now, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))
        self.date_label = ctk.CTkLabel(top, text="", font=ui_font("title", 22, bold=True), anchor="w")
        self.date_label.pack(side="left")
        self.time_label = ctk.CTkLabel(top, text="", font=ui_font("title", 22, bold=True),
                                       text_color=th.get_current_color('accent_primary'))
        self.time_label.pack(side="left", padx=(16, 0))
        self._button(top, "Set Date…", self._on_set_date, width=90).pack(side="right")
        self.notice_label = ctk.CTkLabel(now, text="", font=ui_font("small"), anchor="w", justify="left",
                                         text_color=th.get_current_color('text_label'))
        self.notice_label.pack(fill="x", padx=16)

        steps = ctk.CTkFrame(now, fg_color="transparent")
        steps.pack(fill="x", padx=16, pady=(4, 12))
        for text, amount, unit in (("+10 min", 10, "minutes"), ("+1 hour", 1, "hours"), ("+8 hours", 8, "hours"),
                                   ("+1 day", 1, "days"), ("+1 week", 1, "weeks")):
            self._button(steps, text, lambda a=amount, u=unit: self.advance(a, u), width=78).pack(
                side="left", padx=(0, 6))
        ctk.CTkLabel(steps, text="or", font=ui_font("small"), text_color=th.get_text_secondary()).pack(
            side="left", padx=(6, 6))
        self.amount_entry = ctk.CTkEntry(steps, width=60)
        self.amount_entry.insert(0, "3")
        self.amount_entry.pack(side="left")
        self.unit_var = ctk.StringVar(value="days")
        ctk.CTkOptionMenu(steps, variable=self.unit_var, values=list(ADVANCE_UNITS), width=95).pack(
            side="left", padx=(6, 6))
        self._button(steps, "Forward", lambda: self._advance_custom(1), width=76, kind="accent").pack(side="left")
        self._button(steps, "Back", lambda: self._advance_custom(-1), width=60).pack(side="left", padx=(6, 0))

        # -- month + side panel
        body = ctk.CTkFrame(self.main, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=th.get_current_color('bg_primary'), corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        nav = ctk.CTkFrame(left, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(10, 0))
        self._button(nav, "◀", lambda: self._step_month(-1), width=34).pack(side="left")
        self.month_label = ctk.CTkLabel(nav, text="", font=ui_font("heading", bold=True))
        self.month_label.pack(side="left", padx=10)
        self._button(nav, "▶", lambda: self._step_month(1), width=34).pack(side="left")
        self._button(nav, "Today", self._go_today, width=64).pack(side="right")
        self.canvas = MonthCanvas(left, on_select=self._on_select_day)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)

        side = ctk.CTkFrame(body, fg_color=th.get_current_color('bg_primary'), corner_radius=10, width=340)
        side.grid(row=0, column=1, sticky="nsew")
        side.pack_propagate(False)
        self.day_label = ctk.CTkLabel(side, text="", font=ui_font("subheading", bold=True), anchor="w",
                                      justify="left", wraplength=310)
        self.day_label.pack(fill="x", padx=12, pady=(12, 2))
        day_bar = ctk.CTkFrame(side, fg_color="transparent")
        day_bar.pack(fill="x", padx=12)
        self._button(day_bar, "+ Event", self._on_add_event, width=80, height=28).pack(side="left")
        self.make_today_btn = self._button(day_bar, "Make This Today", self._on_make_today, width=120, height=28)
        self.make_today_btn.pack(side="left", padx=(6, 0))
        self.events_frame = ctk.CTkFrame(side, fg_color="transparent")
        self.events_frame.pack(fill="x", padx=12, pady=(6, 6))

        head = ctk.CTkFrame(side, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(head, text="Trackers", font=ui_font("subheading", bold=True)).pack(side="left")
        self._button(head, "+ Tracker", self._on_add_tracker, width=80, height=28).pack(side="right")
        ctk.CTkLabel(side, text="Auto: moves on as time passes. Untick it while the work is paused.",
                     font=ui_font("small"), text_color=th.get_text_secondary(), wraplength=310,
                     justify="left").pack(anchor="w", padx=12)
        self.trackers_frame = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.trackers_frame.pack(fill="both", expand=True, padx=6, pady=(4, 10))

    # ------------------------------------------------------------------ showing

    def refresh(self):
        """Redraw everything from the store."""
        campaigns = self.store.campaigns
        if not campaigns:
            self.main.pack_forget()
            self.empty.pack(fill="both", expand=True, padx=20)
            self.campaign_menu.configure(values=[""])
            self.campaign_var.set("")
            for w in (self.edit_btn, self.delete_btn, self.campaign_menu):
                w.configure(state="disabled")
            return
        self.empty.pack_forget()
        self.main.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        for w in (self.edit_btn, self.delete_btn, self.campaign_menu):
            w.configure(state="normal")
        self.campaign_menu.configure(values=self._campaign_labels())
        c = self.campaign
        self.campaign_var.set(self._label_of(c))
        self._view = (c.year, c.month)
        if self._selected is None or not self._valid_date(self._selected):
            self._selected = (c.year, c.month, c.day)
        self._show_now()
        self._show_month()
        self._show_day()
        self._show_trackers()

    def _campaign_labels(self) -> List[str]:
        return [self._label_of(c) for c in self.store.campaigns]

    def _label_of(self, campaign: Campaign) -> str:
        same = [c for c in self.store.campaigns if c.name == campaign.name]
        if len(same) > 1:
            return f"{campaign.name} ({same.index(campaign) + 1})"
        return campaign.name

    def _valid_date(self, ymd) -> bool:
        c = self.campaign
        y, m, d = ymd
        return 0 <= m < len(c.config.months) and 1 <= d <= c.config.months[m].length(y)

    def _show_now(self):
        c = self.campaign
        self.date_label.configure(text=c.date_text())
        self.time_label.configure(text=c.time_text())

    def _show_month(self):
        c = self.campaign
        year, month = self._view
        m = c.config.months[month]
        label = f"{m.name} {c.config.year_text(year)}"
        if m.outside:
            label += "  (outside the months)"
        self.month_label.configure(text=label)
        sel = self._selected if self._selected and self._selected[:2] == (year, month) else None
        self.canvas.show(c, year, month, sel)

    def _show_day(self):
        c = self.campaign
        for w in self.events_frame.winfo_children():
            w.destroy()
        if self._selected is None:
            self.day_label.configure(text="")
            return
        y, m, d = self._selected
        is_today = self._selected == (c.year, c.month, c.day)
        self.day_label.configure(text=c.config.date_text(y, m, d) + ("  (today)" if is_today else ""))
        self.make_today_btn.configure(state="disabled" if is_today else "normal")
        events = c.events_on(y, m, d)
        if not events:
            ctk.CTkLabel(self.events_frame, text="Nothing on this day.", font=ui_font("small"),
                         text_color=self.theme.get_text_secondary()).pack(anchor="w")
        for e in events:
            row = ctk.CTkFrame(self.events_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            text = f"{'★' if e.is_holiday else '•'} {e.name}" + (f"\n{e.description}" if e.description else "")
            ctk.CTkLabel(row, text=text, font=ui_font("body"), anchor="w", justify="left",
                         wraplength=240).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="×", width=26, height=24, fg_color="transparent", border_width=1,
                          text_color=self.theme.get_current_color('text_primary'),
                          command=lambda ev=e: self._on_delete_event(ev)).pack(side="right")
            ctk.CTkButton(row, text="✎", width=26, height=24, fg_color="transparent", border_width=1,
                          text_color=self.theme.get_current_color('text_primary'),
                          command=lambda ev=e: self._on_edit_event(ev)).pack(side="right", padx=(0, 4))

    def _show_trackers(self):
        c = self.campaign
        for w in self.trackers_frame.winfo_children():
            w.destroy()
        self._tracker_rows = []
        if not c.trackers:
            ctk.CTkLabel(self.trackers_frame, text="No trackers. Add one for crafting, travel, training...",
                         font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                         wraplength=290, justify="left").pack(anchor="w", padx=6)
            return
        for t in c.trackers:
            self._tracker_rows.append(self._tracker_row(t))

    def _tracker_row(self, t: Tracker):
        th = self.theme
        row = ctk.CTkFrame(self.trackers_frame, fg_color=th.get_current_color('bg_secondary'), corner_radius=8)
        row.pack(fill="x", padx=4, pady=4)
        top = ctk.CTkFrame(row, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(top, text=t.name, font=ui_font("body", bold=True), anchor="w").pack(side="left")
        ctk.CTkButton(top, text="×", width=24, height=22, fg_color="transparent", border_width=1,
                          text_color=self.theme.get_current_color('text_primary'),
                      command=lambda: self._on_delete_tracker(t)).pack(side="right")
        ctk.CTkButton(top, text="✎", width=24, height=22, fg_color="transparent", border_width=1,
                          text_color=self.theme.get_current_color('text_primary'),
                      command=lambda: self._on_edit_tracker(t)).pack(side="right", padx=(0, 4))
        bar = ctk.CTkProgressBar(row, height=12,
                                 progress_color=th.get_current_color(
                                     'button_success' if t.done else 'accent_primary'))
        bar.set(t.fraction)
        bar.pack(fill="x", padx=8, pady=(4, 2))
        bottom = ctk.CTkFrame(row, fg_color="transparent")
        bottom.pack(fill="x", padx=8, pady=(0, 6))
        text = ctk.CTkLabel(bottom, text=t.progress_text(), font=ui_font("small"), anchor="w")
        text.pack(side="left")
        auto = ctk.BooleanVar(value=t.auto)
        ctk.CTkCheckBox(bottom, text="Auto", variable=auto, width=60, checkbox_width=18, checkbox_height=18,
                        command=lambda: self._on_toggle_auto(t, auto.get())).pack(side="right")
        ctk.CTkButton(bottom, text="+1", width=30, height=22, fg_color="transparent", border_width=1,
                          text_color=self.theme.get_current_color('text_primary'),
                      command=lambda: self._nudge_tracker(t, 1)).pack(side="right", padx=(0, 6))
        ctk.CTkButton(bottom, text="−1", width=30, height=22, fg_color="transparent", border_width=1,
                          text_color=self.theme.get_current_color('text_primary'),
                      command=lambda: self._nudge_tracker(t, -1)).pack(side="right", padx=(0, 4))
        if t.notes:
            ctk.CTkLabel(row, text=t.notes, font=ui_font("small"), text_color=th.get_text_secondary(),
                         anchor="w", justify="left", wraplength=280).pack(fill="x", padx=8, pady=(0, 6))
        return row, bar, text

    def _update_tracker_rows(self):
        """Move the bars without rebuilding the rows (the clock buttons can be clicked quickly)."""
        c = self.campaign
        if len(self._tracker_rows) != len(c.trackers):
            self._show_trackers()
            return
        for t, (_row, bar, text) in zip(c.trackers, self._tracker_rows):
            bar.set(t.fraction)
            bar.configure(progress_color=self.theme.get_current_color(
                'button_success' if t.done else 'accent_primary'))
            text.configure(text=t.progress_text())

    # ------------------------------------------------------------------ the clock

    def _unit_minutes(self, unit: str) -> int:
        cfg = self.campaign.config
        return {"minutes": 1, "hours": cfg.minutes_per_hour, "days": cfg.minutes_per_day,
                "weeks": cfg.minutes_per_day * (len(cfg.weekdays) or 7)}[unit]

    def advance(self, amount: float, unit: str = "minutes"):
        """Move the clock (and the automatic trackers) on by ``amount`` of ``unit``."""
        c = self.campaign
        if c is None:
            return None
        minutes = int(round(amount * self._unit_minutes(unit)))
        was_view_today = self._view == (c.year, c.month)
        report = c.advance(minutes)
        if was_view_today:
            self._view = (c.year, c.month)
        self._selected = (c.year, c.month, c.day)
        messages = report.messages(c.config)
        self.notice_label.configure(text="  ·  ".join(messages))
        self._show_now()
        self._show_month()
        self._show_day()
        self._update_tracker_rows()
        self._changed()
        return report

    def _advance_custom(self, sign: int):
        amount = _float(self.amount_entry.get())
        if amount is None or amount <= 0:
            self.notice_label.configure(text="Type how much time passes (a number) first.")
            return
        self.advance(sign * amount, self.unit_var.get())

    def _on_set_date(self):
        c = self.campaign
        cfg = c.config
        months = [m.name for m in cfg.months]

        def validate(v):
            year, day = _int(v["year"]), _int(v["day"])
            if year is None:
                return "The year must be a whole number."
            month = months.index(v["month"])
            length = cfg.months[month].length(year)
            if length <= 0:
                return f"{v['month']} has no days in {cfg.year_text(year)}."
            if day is None or not 1 <= day <= length:
                return f"The day must be between 1 and {length}."
            if self._parse_time(v["time"]) is None:
                return f"Write the time as hours:minutes, e.g. 08:30 (up to {cfg.hours_per_day - 1}:" \
                       f"{cfg.minutes_per_hour - 1})."
            return None

        values = ask_form(self.winfo_toplevel(), "Set Date and Time", [
            ("year", "Year", "entry", c.year),
            ("month", "Month", "option", months[c.month], months),
            ("day", "Day", "entry", c.day),
            ("time", "Time", "entry", c.time_text()),
            ("move", "Count it as time passing (moves the automatic trackers)", "check", False),
        ], validate=validate)
        if not values:
            return
        report = c.set_datetime(int(values["year"]), months.index(values["month"]), int(values["day"]),
                                self._parse_time(values["time"]), move_trackers=values["move"])
        self.notice_label.configure(text="  ·  ".join(report.messages(cfg)))
        self._selected = None
        self.refresh()
        self._changed()

    def _parse_time(self, text: str) -> Optional[int]:
        cfg = self.campaign.config
        parts = str(text).strip().split(":")
        if len(parts) == 1:
            parts.append("0")
        if len(parts) != 2:
            return None
        h, m = _int(parts[0]), _int(parts[1])
        if h is None or m is None or not 0 <= h < cfg.hours_per_day or not 0 <= m < cfg.minutes_per_hour:
            return None
        return h * cfg.minutes_per_hour + m

    # ------------------------------------------------------------------ browsing

    def _step_month(self, delta: int):
        c = self.campaign
        year, month = self._view
        n = len(c.config.months)
        for _ in range(n + 1):                         # skip a leap-only month in a year it has no days
            month += delta
            if month >= n:
                month, year = 0, year + 1
            elif month < 0:
                month, year = n - 1, year - 1
            if c.config.months[month].length(year) > 0:
                break
        self._view = (year, month)
        self._show_month()

    def _go_today(self):
        c = self.campaign
        self._view = (c.year, c.month)
        self._selected = (c.year, c.month, c.day)
        self._show_month()
        self._show_day()

    def _on_select_day(self, ymd):
        self._selected = ymd
        self._show_month()
        self._show_day()

    def _on_make_today(self):
        if self._selected is None:
            return
        c = self.campaign
        y, m, d = self._selected
        if messagebox.askyesno("Change the date", f"Make {c.config.date_text(y, m, d)} today?\n\n"
                               "The automatic trackers move on (or back) by the time in between.", parent=self):
            report = c.set_datetime(y, m, d, move_trackers=True)
            self.notice_label.configure(text="  ·  ".join(report.messages(c.config)))
            self.refresh()
            self._changed()

    # ------------------------------------------------------------------ events

    def _event_form(self, title, event: Optional[Event]):
        return ask_form(self.winfo_toplevel(), title, [
            ("name", "Name", "entry", event.name if event else ""),
            ("description", "Notes", "entry", event.description if event else ""),
            ("holiday", "Every year (a holiday)", "check", event.is_holiday if event else False),
        ], validate=lambda v: None if v["name"].strip() else "Give it a name.")

    def _on_add_event(self):
        if self._selected is None:
            return
        values = self._event_form("Add Event", None)
        if not values:
            return
        y, m, d = self._selected
        self.campaign.events.append(Event(values["name"].strip(), m, d, None if values["holiday"] else y,
                                          values["description"].strip()))
        self._after_events_changed()

    def _on_edit_event(self, event: Event):
        values = self._event_form("Edit Event", event)
        if not values:
            return
        event.name, event.description = values["name"].strip(), values["description"].strip()
        if values["holiday"]:
            event.year = None
        elif event.year is None:
            event.year = self._selected[0] if self._selected else self.campaign.year
        self._after_events_changed()

    def _on_delete_event(self, event: Event):
        what = "holiday" if event.is_holiday else "event"
        if messagebox.askyesno(f"Delete {what}", f"Delete '{event.name}'?", parent=self):
            self.campaign.events = [e for e in self.campaign.events if e.id != event.id]
            self._after_events_changed()

    def _after_events_changed(self):
        self._show_month()
        self._show_day()
        self._changed()

    # ------------------------------------------------------------------ trackers

    def _tracker_form(self, title, t: Optional[Tracker]):
        def validate(v):
            if not v["name"].strip():
                return "Give the tracker a name."
            total = _float(v["total"])
            if total is None or total <= 0:
                return "How long it takes must be a number above 0."
            if _float(v["progress"]) is None:
                return "The progress so far must be a number."
            return None
        return ask_form(self.winfo_toplevel(), title, [
            ("name", "Name", "entry", t.name if t else ""),
            ("total", "How long it takes", "entry", (f"{t.total:g}" if t else "5")),
            ("unit", "In", "option", t.unit if t else "days", UNITS),
            ("progress", "Done so far", "entry", f"{t.progress:g}" if t else "0"),
            ("auto", "Auto: moves on as time passes", "check", t.auto if t else True),
            ("notes", "Notes", "entry", t.notes if t else ""),
        ], validate=validate)

    def _on_add_tracker(self):
        values = self._tracker_form("Add Tracker", None)
        if not values:
            return
        t = Tracker(values["name"].strip(), float(values["total"]), values["unit"], auto=values["auto"],
                    notes=values["notes"].strip())
        t.add(float(values["progress"]))
        self.campaign.trackers.append(t)
        self._show_trackers()
        self._changed()

    def _on_edit_tracker(self, t: Tracker):
        values = self._tracker_form("Edit Tracker", t)
        if not values:
            return
        t.name, t.total, t.unit = values["name"].strip(), float(values["total"]), values["unit"]
        t.auto, t.notes = values["auto"], values["notes"].strip()
        t.progress = 0.0
        t.add(float(values["progress"]))
        self._show_trackers()
        self._changed()

    def _on_delete_tracker(self, t: Tracker):
        if messagebox.askyesno("Delete tracker", f"Delete the tracker '{t.name}'?", parent=self):
            self.campaign.trackers = [x for x in self.campaign.trackers if x.id != t.id]
            self._show_trackers()
            self._changed()

    def _on_toggle_auto(self, t: Tracker, on: bool):
        t.auto = on
        self._changed()

    def _nudge_tracker(self, t: Tracker, amount: float):
        if t.add(amount):
            self.notice_label.configure(text=f"Finished: {t.name}")
        self._update_tracker_rows()
        self._changed()

    # ------------------------------------------------------------------ campaigns

    def _on_pick_campaign(self, label: str):
        labels = self._campaign_labels()
        if label in labels:
            self._flush_save()
            self.store.active_id = self.store.campaigns[labels.index(label)].id
            self.store.save()
            self._selected = None
            self.notice_label.configure(text="")
            self.refresh()

    def _on_new_campaign(self):
        def validate(v):
            if not v["name"].strip():
                return "Give the calendar a name (the campaign's, say)."
            if _int(v["year"]) is None:
                return "The starting year must be a whole number."
            return None
        values = ask_form(self.winfo_toplevel(), "New Calendar", [
            ("name", "Campaign name", "entry", ""),
            ("preset", "Start from", "option", PRESETS[0], PRESETS),
            ("year", "Starting year", "entry", 1),
            ("suffix", "Year suffix (optional, e.g. AR)", "entry", ""),
        ], validate=validate, hint="Pick a calendar to start from; its months, weekdays and hours can all be "
                                   "changed afterwards with Edit Calendar.")
        if not values:
            return
        campaign = new_campaign(values["name"].strip(), values["preset"], int(values["year"]))
        campaign.config.year_suffix = values["suffix"].strip()
        self._flush_save()
        self.store.add(campaign)
        self._selected = None
        self.refresh()

    def _on_edit_campaign(self):
        c = self.campaign
        if c is None:
            return
        cfg = c.config

        def validate(v):
            if not v["name"].strip():
                return "Give the calendar a name."
            months, problems = parse_months(v["months"])
            if problems:
                return " ".join(problems[:3])
            for key, label in (("hours", "Hours per day"), ("minutes", "Minutes per hour")):
                n = _int(v[key])
                if n is None or not 1 <= n <= 1000:
                    return f"{label} must be a whole number from 1 to 1000."
            if _int(v["offset"]) is None:
                return "The weekday shift must be a whole number."
            return None

        values = ask_form(self.winfo_toplevel(), "Edit Calendar", [
            ("name", "Campaign name", "entry", c.name),
            ("suffix", "Year suffix", "entry", cfg.year_suffix),
            ("months", "Months (one per line: name and days; add \"outside\" for days outside the months, "
                       "\"leap 4\" for a day more every 4 years)", "text", cfg.months_text(), 180),
            ("weekdays", "Weekdays (one per line; leave empty for no weeks)", "text", "\n".join(cfg.weekdays), 110),
            ("hours", "Hours per day", "entry", cfg.hours_per_day),
            ("minutes", "Minutes per hour", "entry", cfg.minutes_per_hour),
            ("offset", "Weekday shift (moves every date to a later weekday)", "entry", cfg.weekday_offset),
        ], validate=validate, width=560)
        if not values:
            return
        months, _ = parse_months(values["months"])
        weekdays = [w.strip() for w in values["weekdays"].replace(",", "\n").splitlines() if w.strip()]
        old_minute_frac = c.minute / cfg.minutes_per_day
        c.name = values["name"].strip()
        c.config = CalendarConfig(months, weekdays, int(values["hours"]), int(values["minutes"]),
                                  values["suffix"].strip(), int(values["offset"]))
        c.minute = int(old_minute_frac * c.config.minutes_per_day)
        c.events = [e for e in c.events if e.month < len(months)]
        c.clamp()
        self._selected = None
        self._changed()
        self.refresh()

    def _on_delete_campaign(self):
        c = self.campaign
        if c is None:
            return
        if not messagebox.askyesno("Delete calendar", f"Delete the calendar '{c.name}', with its events and "
                                   "trackers? This can't be undone.", parent=self):
            return
        self._flush_save()
        self.store.remove(c.id)
        self._selected = None
        self.refresh()
