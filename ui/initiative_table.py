"""The initiative table: the widget the DM page and the player pop-up both draw.

It renders ``backend.table()`` (see ``initiative_rows``) and reports what the person did through
callbacks; it never changes the tracker itself. Rows are kept per combatant id and updated in place,
so a change that touches one number redraws one label, not the table.

Columns: stripe | marker | initiative | name | HP (number + bar) | AC | conditions | DM tools.
An event is one label spanning name..conditions.
"""

from __future__ import annotations

import tkinter as tk
from typing import Dict, List, Optional, Set

import customtkinter as ctk

import conditions as C
import initiative_rows as R
from theme import get_theme_manager
from typography import ui_font

GROUP_COLORS = ["#4f8cff", "#e0a030", "#4fbf80", "#c060d0", "#e0605a", "#40b8c8"]
BAR_W, BAR_H = 96, 7
COL_STRIPE, COL_MARKER, COL_INIT, COL_NAME, COL_HP, COL_AC, COL_COND, COL_TOOLS = range(8)


def hp_color(frac: float) -> str:
    return "#3fb950" if frac > 0.5 else ("#d29922" if frac > 0.25 else "#f85149")


def _columns(frame) -> None:
    """The one column layout shared by the header and every row."""
    frame.grid_columnconfigure(COL_STRIPE, minsize=6)
    frame.grid_columnconfigure(COL_MARKER, minsize=22)
    frame.grid_columnconfigure(COL_INIT, minsize=44)
    # "uniform" sizes the two flexible columns by their weights alone, so a long condition list in
    # one row can't push that row's HP/AC out of line with the others.
    frame.grid_columnconfigure(COL_NAME, weight=3, minsize=120, uniform="flex")
    frame.grid_columnconfigure(COL_HP, minsize=BAR_W + 40)
    frame.grid_columnconfigure(COL_AC, minsize=42)
    frame.grid_columnconfigure(COL_COND, weight=2, minsize=90, uniform="flex")


class _RowWidget(ctk.CTkFrame):
    """One combatant. Built once; :meth:`show` updates only what changed."""

    def __init__(self, table: "InitiativeTable", row: R.Row):
        t = table.theme
        bg = t.get_current_color('bg_secondary')
        super().__init__(table.body, fg_color=bg, corner_radius=6, border_width=0, height=34)
        self.table = table
        self.row_id = row.id
        self.is_event = row.is_event
        self._key = None
        _columns(self)

        self.stripe = tk.Frame(self, width=4, bg=bg, highlightthickness=0)
        self.stripe.grid(row=0, column=COL_STRIPE, sticky="ns", padx=(2, 0), pady=3)
        self.marker = ctk.CTkLabel(self, text="", width=20, font=ui_font("body", bold=True),
                                   text_color=t.get_current_color('text_label'))
        self.marker.grid(row=0, column=COL_MARKER)
        self.init = ctk.CTkLabel(self, text="", width=40, font=ui_font("body", bold=True), anchor="e")
        self.init.grid(row=0, column=COL_INIT, padx=(0, 6))

        self.hp_frame = self.hp_text = self.hp_bar = self.ac = self.cond = None
        if row.is_event:
            self.name = ctk.CTkLabel(self, text="", width=10, font=ui_font("body", bold=True), anchor="center")
            self.name.grid(row=0, column=COL_NAME, columnspan=4, sticky="ew", padx=6, pady=4)
            self._clickables = [self.init, self.name]
            self._editable = []
        else:
            self.name = ctk.CTkLabel(self, text="", width=10, font=ui_font("body", bold=True), anchor="w")
            self.name.grid(row=0, column=COL_NAME, sticky="ew", padx=4, pady=4)
            self.hp_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.hp_frame.grid(row=0, column=COL_HP, padx=6)
            self.hp_text = ctk.CTkLabel(self.hp_frame, text="", font=ui_font("body"), anchor="w")
            self.hp_text.pack(anchor="w")
            self.hp_bar = tk.Canvas(self.hp_frame, width=BAR_W, height=BAR_H, highlightthickness=0, bd=0,
                                    bg=bg)
            self.hp_bar.pack(anchor="w", pady=(0, 3))
            self.ac = ctk.CTkLabel(self, text="", width=40, font=ui_font("body"))
            self.ac.grid(row=0, column=COL_AC, padx=4)
            self.cond = ctk.CTkLabel(self, text="", width=10, font=ui_font("small"), anchor="w",
                                     text_color=t.get_text_secondary())
            self.cond.grid(row=0, column=COL_COND, sticky="ew", padx=6)
            self._editable = [self.hp_frame, self.hp_text, self.hp_bar, self.ac, self.cond]
            self._clickables = [self.init, self.name] + self._editable

        self.tools = None
        if table.dm:
            self.tools = ctk.CTkFrame(self, fg_color="transparent")
            self.tools.grid(row=0, column=COL_TOOLS, padx=(2, 6))
            self.handle = ctk.CTkLabel(self.tools, text="⠿", width=20, font=ui_font("heading", 16),
                                       text_color=t.get_text_secondary(), cursor="fleur")
            self.handle.pack(side="left")
            self.eye = ctk.CTkButton(self.tools, text="", width=28, height=24, font=ui_font("small"),
                                     fg_color="transparent", hover_color=t.get_current_color('bg_tertiary'),
                                     text_color=t.get_current_color('text_primary'),
                                     command=lambda: table.callbacks.on_hide_toggle(self.row_id))
            self.eye.pack(side="left", padx=1)
            self.menu = ctk.CTkButton(self.tools, text="⋯", width=28, height=24, font=ui_font("body", bold=True),
                                      fg_color="transparent", hover_color=t.get_current_color('bg_tertiary'),
                                      text_color=t.get_current_color('text_primary'), command=self._open_menu)
            self.menu.pack(side="left", padx=1)
            for event, fn in (("<ButtonPress-1>", lambda e: table._drag_start(self.row_id, e)),
                              ("<B1-Motion>", table._drag_move), ("<ButtonRelease-1>", table._drag_end)):
                self.handle.bind(event, fn)

        self._bind_clicks()

    # ------------------------------------------------------------------ input

    @staticmethod
    def _raw(w):
        """The tk widget CustomTkinter draws a control on (events must be bound there)."""
        return getattr(w, "_canvas", w)

    def _bind_clicks(self):
        t = self.table
        for w in [self] + self._clickables:
            raw = self._raw(w)
            raw.bind("<Button-1>", lambda e, w=w: t._clicked(self.row_id, w, e), add="+")
            raw.bind("<Button-3>", lambda e: t._right_clicked(self.row_id, e), add="+")
            raw.bind("<Button-2>", lambda e: t._right_clicked(self.row_id, e), add="+")
        for w in self._clickables:
            raw = self._raw(w)
            raw.bind("<Enter>", lambda e, w=w: self._hover(w, True), add="+")
            raw.bind("<Leave>", lambda e, w=w: self._hover(w, False), add="+")

    def _hover(self, w, inside: bool):
        r = self.table.row_of(self.row_id)
        clickable = r is not None and ((r.can_edit and w in self._editable) or (self.table.dm and w is self.init))
        try:
            self._raw(w).configure(cursor="hand2" if (inside and clickable) else "")
        except tk.TclError:
            pass

    def _open_menu(self):
        self.table.callbacks.on_context(self.row_id, self.menu.winfo_rootx(), self.menu.winfo_rooty() + 24)

    # ------------------------------------------------------------------ drawing

    def show(self, r: R.Row, selected: bool, compact: bool):
        t = self.table.theme
        key = (r.name, r.initiative, r.group, r.group_index, r.first_in_group, r.hidden, r.defeated, r.mine,
               r.can_edit, r.active, tuple((c.get("name"), c.get("level"), c.get("rounds")) for c in r.conditions),
               r.hp_mode, r.hp, r.hp_max, r.hp_temp, r.hp_frac, r.ac, selected, compact, r.group_name)
        if key == self._key:
            return
        self._key = key

        bg = t.get_current_color('bg_tertiary' if r.active else 'bg_secondary')
        self.configure(fg_color=bg, border_width=2 if selected else 0,
                       border_color=t.get_current_color('accent_primary'))
        self.stripe.configure(bg=GROUP_COLORS[r.group_index % len(GROUP_COLORS)] if r.group else bg)
        self.marker.configure(text="▶" if r.active else "")
        color = t.get_text_disabled() if r.defeated else t.get_current_color('text_primary')
        init_text = "" if r.initiative is None else str(r.initiative)
        self.init.configure(text=init_text or "–",
                            text_color=color if init_text else t.get_text_secondary())

        if r.is_event:
            self.name.configure(text=f"⚑  {r.name}" + ("   (hidden)" if r.hidden else ""), text_color=color)
        else:
            name = r.name
            if r.group and r.first_in_group and r.group_name:
                name += f"   ·  {r.group_name}"
            if r.mine and not self.table.dm:
                name += "  (you)"
            if r.hidden:
                name += "   (hidden)" if self.table.dm else "   (hidden from others)"
            if r.defeated:
                name = "☠ " + name
            self.name.configure(text=name, text_color=color)
            self.hp_bar.configure(bg=bg)
            self._draw_hp(r, color)
            self.ac.configure(text="" if r.ac is None else str(r.ac), text_color=color)
            (self.ac.grid_remove if compact else self.ac.grid)()
            cond = r.condition_text
            if compact and r.conditions:
                cond = ", ".join(C.ABBREVIATIONS.get(c.get("name", ""), c.get("name", "")) for c in r.conditions)
            self.cond.configure(text=cond or "—")
        if self.tools is not None:
            self.eye.configure(text="🙈" if r.hidden else "👁")

    def _draw_hp(self, r: R.Row, color: str):
        t = self.table.theme
        if r.hp_mode == "number":
            self.hp_text.configure(text=f"{r.hp} / {r.hp_max}" + (f"  +{r.hp_temp}" if r.hp_temp else ""),
                                   text_color=color)
        elif r.hp_mode == "bar":
            self.hp_text.configure(text="", text_color=color)
        else:
            self.hp_text.configure(text="—", text_color=t.get_text_secondary())

        bar = self.hp_bar
        if r.hp_frac is None or r.hp_mode == "hidden":
            if bar.winfo_manager():
                bar.pack_forget()
            return
        if not bar.winfo_manager():
            bar.pack(anchor="w", pady=(0, 3))
        bar.delete("all")
        bar.create_rectangle(0, 0, BAR_W, BAR_H, fill=t.get_current_color('bg_input'), width=0)
        if r.hp_frac > 0:
            bar.create_rectangle(0, 0, max(2, int(BAR_W * min(r.hp_frac, 1.0))), BAR_H,
                                 fill=hp_color(r.hp_frac), width=0)


class TableCallbacks:
    """What the table asks its owner to do. Every one is optional."""

    def __init__(self, **kw):
        noop = lambda *a, **k: None          # noqa: E731
        self.on_select = noop                # (selected_ids: set)
        self.on_stats = noop                 # (row_id, anchor_widget)
        self.on_conditions = noop            # (row_id, anchor_widget)
        self.on_initiative = noop            # (row_id)
        self.on_context = noop               # (row_id, x_root, y_root)
        self.on_hide_toggle = noop           # (row_id)
        self.on_move = noop                  # (row_id, before_id_or_None)
        self.on_add_me = noop                # ()
        for k, v in kw.items():
            setattr(self, k, v)


class InitiativeTable(ctk.CTkFrame):
    def __init__(self, parent, backend, callbacks: Optional[TableCallbacks] = None, compact: bool = False):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.backend = backend
        self.callbacks = callbacks or TableCallbacks()
        self.compact = compact
        self.role = backend.role
        self.dm = self.role == "dm"

        self._rows: Dict[str, _RowWidget] = {}
        self._tv: R.TableView = R.TableView(rows=[], role=self.role)
        self.selected: Set[str] = set()
        self._anchor_id: Optional[str] = None
        self._drag_id: Optional[str] = None
        self._drop_index: Optional[int] = None
        self._refresh_after = None

        self._build_header()
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)
        self.body.grid_columnconfigure(0, weight=1)
        self.empty = ctk.CTkLabel(self.body, text="", font=ui_font("body"), justify="center",
                                  text_color=self.theme.get_text_secondary())
        self._empty_btn: Optional[ctk.CTkButton] = None

        backend.listen(self.schedule_refresh)
        self.refresh()

    def _build_header(self):
        t = self.theme
        head = ctk.CTkFrame(self, fg_color=t.get_current_color('bg_tertiary'), corner_radius=6, height=28)
        head.pack(fill="x", pady=(0, 4), padx=(0, 14))
        _columns(head)
        for col, text, anchor in ((COL_INIT, "Init", "e"), (COL_NAME, "Name", "w"), (COL_HP, "HP", "w"),
                                  (COL_AC, "AC", "center"), (COL_COND, "Conditions", "w")):
            lbl = ctk.CTkLabel(head, text=text, width=10, font=ui_font("small", bold=True),
                               text_color=t.get_text_secondary(), anchor=anchor)
            lbl.grid(row=0, column=col, sticky="ew", padx=4, pady=3)
            if col == COL_AC:
                self._ac_head = lbl
        if self.dm:
            ctk.CTkLabel(head, text="", width=84).grid(row=0, column=COL_TOOLS)

    def destroy(self):
        try:
            self.backend.unlisten(self.schedule_refresh)
        except Exception:
            pass
        if self._refresh_after is not None:
            try:
                self.after_cancel(self._refresh_after)
            except Exception:
                pass
        super().destroy()

    # ------------------------------------------------------------------ refresh

    def schedule_refresh(self):
        """Changes can arrive in bursts (a group roll touches many rows): redraw once."""
        if self._refresh_after is None:
            self._refresh_after = self.after(15, self._do_refresh)

    def _do_refresh(self):
        self._refresh_after = None
        if self.winfo_exists():
            self.refresh()

    def set_compact(self, compact: bool):
        if compact != self.compact:
            self.compact = compact
            for w in self._rows.values():
                w._key = None
            self.refresh()

    def row_of(self, row_id: str) -> Optional[R.Row]:
        return next((r for r in self._tv.rows if r.id == row_id), None)

    @property
    def view(self) -> R.TableView:
        return self._tv

    def widget_of(self, row_id: str):
        return self._rows.get(row_id)

    def refresh(self):
        tv = self.backend.table()
        self._tv = tv
        keep = {r.id for r in tv.rows}
        self.selected &= keep
        for gone in [i for i in self._rows if i not in keep]:
            self._rows.pop(gone).destroy()
        for i, r in enumerate(tv.rows):
            w = self._rows.get(r.id)
            if w is not None and w.is_event != r.is_event:
                w.destroy()
                w = None
            if w is None:
                w = self._rows[r.id] = _RowWidget(self, r)
            w.show(r, r.id in self.selected, self.compact)
            info = w.grid_info()
            if not info or int(info.get("row", -1)) != i:
                w.grid(row=i, column=0, sticky="ew", pady=1)
        (self._ac_head.grid_remove if self.compact else self._ac_head.grid)()
        self._show_empty(tv)

    def _show_empty(self, tv: R.TableView):
        if tv.rows:
            self.empty.grid_forget()
            if self._empty_btn is not None:
                self._empty_btn.destroy()
                self._empty_btn = None
            return
        if self.dm:
            text = "Nobody is in the fight yet.\nUse “＋ Add” to bring in monsters, characters or events."
        elif tv.can_add:
            text = "Nothing in the initiative order yet."
        else:
            text = "Waiting for the DM to start the encounter…"
        self.empty.configure(text=text)
        self.empty.grid(row=0, column=0, pady=40)
        if not self.dm and tv.can_add and self._empty_btn is None:
            self._empty_btn = ctk.CTkButton(self.body, text="＋ Add my character", height=34,
                                            fg_color=self.theme.get_current_color('accent_primary'),
                                            hover_color=self.theme.get_current_color('accent_hover'),
                                            command=self.callbacks.on_add_me)
            self._empty_btn.grid(row=1, column=0)

    # ------------------------------------------------------------------ input

    def _clicked(self, row_id: str, widget, event):
        r, w = self.row_of(row_id), self._rows.get(row_id)
        if r is None or w is None:
            return
        if widget is w.init and self.dm:
            self.callbacks.on_initiative(row_id)
            return
        if r.can_edit and not r.is_event:
            if widget in (w.hp_frame, w.hp_text, w.hp_bar, w.ac):
                self.callbacks.on_stats(row_id, widget)
                return
            if widget is w.cond:
                self.callbacks.on_conditions(row_id, widget)
                return
        if self.dm:
            self._select(row_id, event)

    def _right_clicked(self, row_id: str, event):
        if self.dm:
            if row_id not in self.selected:
                self._select(row_id, None)
            self.callbacks.on_context(row_id, event.x_root, event.y_root)

    def _select(self, row_id: str, event):
        ctrl = bool(event and (event.state & 0x0004))
        shift = bool(event and (event.state & 0x0001))
        ids = [r.id for r in self._tv.rows]
        if shift and self._anchor_id in ids:
            a, b = sorted((ids.index(self._anchor_id), ids.index(row_id)))
            self.selected = set(ids[a:b + 1])
        elif ctrl:
            self.selected ^= {row_id}
            self._anchor_id = row_id
        else:
            self.selected = {row_id}
            self._anchor_id = row_id
        self.refresh()
        self.callbacks.on_select(set(self.selected))

    def select(self, ids) -> None:
        self.selected = set(ids)
        self.refresh()
        self.callbacks.on_select(set(self.selected))

    def clear_selection(self):
        if self.selected:
            self.select(())

    # ------------------------------------------------------------------ drag to reorder

    def _drag_start(self, row_id: str, event):
        self._drag_id = row_id
        self._drop_index = None

    def _index_at(self, y_root: int) -> int:
        """The position in the displayed list that a drop at this screen height means."""
        index = 0
        for r in self._tv.rows:
            w = self._rows.get(r.id)
            if w is not None and w.winfo_ismapped() and y_root > w.winfo_rooty() + w.winfo_height() / 2:
                index += 1
        return index

    def _drag_move(self, event):
        if self._drag_id is None:
            return
        index = self._index_at(event.y_root)
        if index == self._drop_index:
            return
        self._drop_index = index
        rows = self._tv.rows
        target = rows[min(index, len(rows) - 1)].id if rows else None
        accent = self.theme.get_current_color('accent_primary')
        for r in rows:
            w = self._rows.get(r.id)
            if w is not None:
                w.configure(border_width=2 if (r.id == target or r.id in self.selected) else 0,
                            border_color=accent)

    def _drag_end(self, event):
        row_id, index = self._drag_id, self._drop_index
        self._drag_id = self._drop_index = None
        for w in self._rows.values():
            w._key = None                       # redraw borders from scratch
        rows = self._tv.rows
        src = next((i for i, r in enumerate(rows) if r.id == row_id), None)
        if row_id is not None and index is not None and src is not None and index not in (src, src + 1):
            self.callbacks.on_move(row_id, R.move_before(self._tv, index))
        else:
            self.refresh()
