"""
Random Tables page (Game Tools): a searchable list of d100 tables (or d20, 2d6...) with the selected table
beside it. Roll shows the result at the top and lights up its entry in the table below; an entry's own
``{2d6}`` dice and ``{table: Name}`` rolls are rolled with it. In a LAN session the result can be shared in
the chat.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional

import customtkinter as ctk

from random_tables import (INLINE_RE, DEFAULT_DICE, RandomTable, TableRoll, get_random_tables_manager, parse_entries,
                           valid_dice)
from theme import get_theme_manager
from typography import ui_font
from ui.theme_listener import ThemeListenerMixin
from ui.virtual_list import VirtualListPanel
from ui.window_utils import add_cancel_save, center_on_parent

ALL_CATEGORIES = "All Categories"
ROLL_COUNTS = ["×1", "×2", "×3", "×5", "×10"]
HISTORY_LIMIT = 30
# The page scrolls when the window is shorter than this, so Recent rolls is never cut off.
MIN_PAGE_HEIGHT = 620
HISTORY_HEIGHT = 190      # Recent rolls height before the divider is dragged
HISTORY_MIN, TABLE_MIN = 70, 120


def _color(theme, role: str) -> str:
    value = theme.get_current_color(role)
    return value[1] if isinstance(value, tuple) else str(value)


class RandomTablesList(VirtualListPanel):
    TITLE = "Tables"
    NOUN = "table"

    def row_text(self, item) -> str:
        return ("* " if item.is_custom else "") + item.name


class TableTextView(ThemeListenerMixin, tk.Frame):
    """The entries of a table as two columns (range, result), with rolled entries lit up."""

    def __init__(self, parent):
        self.theme = get_theme_manager()
        super().__init__(parent, highlightthickness=0, borderwidth=0)
        self.text = tk.Text(self, wrap="word", relief="flat", borderwidth=0, highlightthickness=0,
                            padx=12, pady=8, cursor="arrow", state="disabled", takefocus=0, spacing1=3,
                            spacing3=3, undo=False)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self._table: Optional[RandomTable] = None
        self.apply_theme()
        self.theme.add_listener(self._on_theme_changed)

    def _on_theme_changed(self):
        self.apply_theme()

    def apply_theme(self):
        try:
            bg = _color(self.theme, "bg_secondary")
            fg = _color(self.theme, "text_primary")
            self.configure(bg=bg)
            t = self.text
            t.configure(bg=bg, fg=fg, font=ui_font("body"), selectbackground=_color(self.theme, "accent_primary"))
            t.tag_configure("range", foreground=_color(self.theme, "text_label"), font=ui_font("body", bold=True))
            t.tag_configure("odd", background=_color(self.theme, "bg_tertiary"))
            t.tag_configure("hit", background=_color(self.theme, "accent_primary"),
                            foreground=_color(self.theme, "text_on_accent"))
            t.tag_configure("roll", foreground=_color(self.theme, "spell_link"))
            t.tag_raise("hit")
            self._set_tabs()
        except tk.TclError:
            pass

    def _set_tabs(self):
        width = ui_font("body", bold=True).measure("00–00") + 24
        self.text.configure(tabs=(width,), lmargin2=width + 12)

    def show(self, table: Optional[RandomTable]):
        self._table = table
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        if table is not None:
            for i, entry in enumerate(table.entries):
                row = f"e{i}"
                t.insert("end", table.range_text(entry), ("range", row))
                t.insert("end", "\t", (row,))
                pos = 0
                for m in INLINE_RE.finditer(entry.text):      # {2d6} and {table: ...} stand out
                    t.insert("end", entry.text[pos:m.start()], (row,))
                    t.insert("end", m.group(0), (row, "roll"))
                    pos = m.end()
                t.insert("end", entry.text[pos:] + "\n", (row,))
                if i % 2:
                    t.tag_add("odd", f"{row}.first", f"{row}.last")
        t.configure(state="disabled")
        t.yview_moveto(0)

    def highlight(self, indexes: List[int]):
        t = self.text
        t.tag_remove("hit", "1.0", "end")
        for i in indexes:
            ranges = t.tag_ranges(f"e{i}")
            if ranges:
                t.tag_add("hit", ranges[0], ranges[-1])
        if indexes:
            ranges = t.tag_ranges(f"e{indexes[-1]}")
            if ranges:
                t.see(ranges[0])


class RandomTablesView(ThemeListenerMixin, ctk.CTkFrame):
    """The Random Tables page."""

    def __init__(self, parent, state: Optional[dict] = None, service=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.manager = get_random_tables_manager()
        self.state = state if state is not None else {}
        self.state.setdefault("history", [])
        self.service = service
        self.on_back = on_back
        self._table: Optional[RandomTable] = None
        self._filter_job: Optional[str] = None
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)
        self.refresh()
        wanted = self.state.get("selected")
        if wanted:
            self.select_table(wanted)
        self._show_history()

    def destroy(self):
        if self._filter_job is not None:
            try:
                self.after_cancel(self._filter_job)
            except Exception:
                pass
        super().destroy()

    # ------------------------------------------------------------------ layout

    def _button(self, parent, text, command, width=110, kind="normal"):
        colors = {"normal": ("button_normal", "button_hover"), "accent": ("accent_primary", "accent_hover"),
                  "danger": ("button_danger", "button_danger_hover")}[kind]
        return ctk.CTkButton(parent, text=text, width=width, height=32, command=command,
                             fg_color=self.theme.get_current_color(colors[0]),
                             hover_color=self.theme.get_current_color(colors[1]),
                             text_color=self.theme.get_current_color(
                                 'text_primary' if kind == "normal" else 'text_on_accent'),
                             text_color_disabled=self.theme.get_text_secondary())

    def _create_scroll_area(self):
        """A page that fills the window, or scrolls when the window is shorter than MIN_PAGE_HEIGHT."""
        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._vbar = ctk.CTkScrollbar(self, orientation="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vbar.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        self.page = ctk.CTkFrame(self._canvas, fg_color="transparent", corner_radius=0)
        self._page_id = self._canvas.create_window(0, 0, window=self.page, anchor="nw")
        self._canvas.bind("<Configure>", self._fit_page, add="+")
        self._bar_shown = False
        self._color_canvas()

    def _color_canvas(self):
        try:
            color = self._apply_appearance_mode(self._detect_color_of_master())
            self._canvas.configure(bg=color)
            self.page.configure(fg_color=color)
        except Exception:
            pass

    def _on_theme_changed(self):
        self._color_canvas()
        try:
            self.split.configure(bg=_color(self.theme, 'pane_sash'))
        except Exception:
            pass

    def _fit_page(self, event=None):
        canvas = self._canvas
        width, height = canvas.winfo_width(), canvas.winfo_height()
        page_h = max(height, MIN_PAGE_HEIGHT)
        canvas.itemconfigure(self._page_id, width=width, height=page_h)
        canvas.configure(scrollregion=(0, 0, width, page_h))
        need = page_h > height + 1
        if need != self._bar_shown:
            self._bar_shown = need
            if need:
                self._vbar.pack(side="right", fill="y", before=canvas)
            else:
                self._vbar.pack_forget()
                canvas.yview_moveto(0)

    def _on_wheel(self, event):
        if not self._bar_shown:
            return None
        if getattr(event, "num", None) == 4:
            step = -1
        elif getattr(event, "num", None) == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(step * 3, "units")
        return "break"

    def _bind_wheel(self, widget, skip):
        """Let the mouse wheel scroll the page over everything except the widgets that scroll themselves."""
        if widget in skip:
            return
        tags = widget.bindtags()
        if "RandomTablesPageWheel" not in tags:
            widget.bindtags(("RandomTablesPageWheel",) + tags)
        for child in widget.winfo_children():
            self._bind_wheel(child, skip)

    def _create_widgets(self):
        theme = self.theme
        self._create_scroll_area()
        root = self.page
        header = ctk.CTkFrame(root, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        if self.on_back:
            self._button(header, "← Game Tools", self.on_back, width=120).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(header, text="Random Tables", font=ui_font("title", 28, bold=True)).pack(side="left")
        self._button(header, "Export", self._on_export, width=80).pack(side="right")
        self._button(header, "Import", self._on_import, width=80).pack(side="right", padx=(0, 8))
        self._button(header, "+ New Table", self._on_new, kind="accent").pack(side="right", padx=(0, 8))

        body = ctk.CTkFrame(root, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent", width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_propagate(False)
        left.pack_propagate(False)
        # (no textvariable: a CTkEntry with one never shows its placeholder)
        self.search_entry = ctk.CTkEntry(left, height=34, placeholder_text="Search names and entries...")
        if self.state.get("query"):
            self.search_entry.insert(0, self.state["query"])
        self.search_entry.pack(fill="x", pady=(0, 6))
        self.search_entry.bind("<KeyRelease>", lambda _e: self._schedule_filter(), add="+")
        self.search_entry.bind("<Return>", lambda _e: self._roll_selected_from_search())
        self.category_var = ctk.StringVar(value=self.state.get("category", ALL_CATEGORIES))
        self.category_menu = ctk.CTkOptionMenu(left, variable=self.category_var, values=[ALL_CATEGORIES],
                                               command=lambda _v: self._apply_filter(), height=32)
        self.category_menu.pack(fill="x", pady=(0, 6))
        self.list_panel = RandomTablesList(left, on_select=self._on_select)
        self.list_panel.pack(fill="both", expand=True)

        right = ctk.CTkFrame(body, fg_color=theme.get_current_color('bg_primary'), corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew")
        self._right = right

        top = ctk.CTkFrame(right, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=(15, 4))
        self.name_label = ctk.CTkLabel(top, text="Select a table", font=ui_font("title", bold=True),
                                       anchor="w", justify="left")
        self.name_label.pack(side="left")
        self.delete_btn = self._button(top, "Delete", self._on_delete, width=70, kind="danger")
        self.delete_btn.pack(side="right")
        self.edit_btn = self._button(top, "Edit", self._on_edit, width=70)
        self.edit_btn.pack(side="right", padx=(0, 6))

        self.meta_label = ctk.CTkLabel(right, text="", font=ui_font("small"), anchor="w",
                                       text_color=theme.get_text_secondary())
        self.meta_label.pack(fill="x", padx=15)
        self.desc_label = ctk.CTkLabel(right, text="", font=ui_font("body"), anchor="w", justify="left",
                                       wraplength=600)
        self.desc_label.pack(fill="x", padx=15, pady=(2, 6))
        right.bind("<Configure>", lambda e: self.desc_label.configure(wraplength=max(200, e.width - 40)), add="+")

        actions = ctk.CTkFrame(right, fg_color="transparent")
        actions.pack(fill="x", padx=15, pady=(0, 8))
        self.roll_btn = ctk.CTkButton(actions, text="🎲 Roll", width=140, height=38, font=ui_font("subheading", bold=True),
                                      fg_color=theme.get_current_color('accent_primary'),
                                      hover_color=theme.get_current_color('accent_hover'),
                                      text_color=theme.get_current_color('text_on_accent'), command=self.roll)
        self.roll_btn.pack(side="left")
        self.count_var = ctk.StringVar(value=self.state.get("count", ROLL_COUNTS[0]))
        ctk.CTkOptionMenu(actions, variable=self.count_var, values=ROLL_COUNTS, width=70, height=38,
                          command=lambda v: self.state.__setitem__("count", v)).pack(side="left", padx=(8, 0))
        self.share_var = ctk.BooleanVar(value=self.state.get("share", False))
        self.share_check = ctk.CTkCheckBox(actions, text="Share in session chat", variable=self.share_var,
                                           command=lambda: self.state.__setitem__("share", self.share_var.get()))
        self.share_check.pack(side="left", padx=(14, 0))

        self.result_frame = ctk.CTkFrame(right, fg_color=theme.get_current_color('bg_secondary'), corner_radius=10)
        self.result_frame.pack(fill="x", padx=15, pady=(0, 8))
        self.result_total = ctk.CTkLabel(self.result_frame, text="", font=ui_font("title", 30, bold=True), width=70)
        self.result_total.pack(side="left", padx=(12, 6), pady=10)
        self.result_text = ctk.CTkLabel(self.result_frame, text="Roll to get a result.", font=ui_font("subheading"),
                                        anchor="w", justify="left", wraplength=520)
        self.result_text.pack(side="left", fill="x", expand=True, padx=(4, 12), pady=10)
        self.result_frame.bind("<Configure>",
                               lambda e: self.result_text.configure(wraplength=max(200, e.width - 120)), add="+")

        # The table and Recent rolls share the rest of the panel; drag the divider between them to resize.
        self.split = tk.PanedWindow(right, orient=tk.VERTICAL, sashwidth=8, sashrelief=tk.FLAT, handlesize=0,
                                    borderwidth=0, opaqueresize=True, sashcursor="sb_v_double_arrow",
                                    bg=_color(theme, 'pane_sash'))
        self.split.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        self.table_view = TableTextView(self.split)
        self.split.add(self.table_view, minsize=TABLE_MIN, stretch="always")

        hist = ctk.CTkFrame(self.split, fg_color=theme.get_current_color('bg_primary'), corner_radius=0)
        self.split.add(hist, minsize=HISTORY_MIN, stretch="never",
                       height=int(self.state.get("history_height", HISTORY_HEIGHT)))
        hist_top = ctk.CTkFrame(hist, fg_color="transparent")
        hist_top.pack(fill="x", pady=(6, 4))
        ctk.CTkLabel(hist_top, text="Recent rolls", font=ui_font("small", bold=True)).pack(side="left")
        ctk.CTkButton(hist_top, text="Clear", width=50, height=22, font=ui_font("small"),
                      fg_color="transparent", border_width=1,
                      text_color=self.theme.get_current_color('text_primary'),
                      command=self._clear_history).pack(side="right")
        self.history_box = ctk.CTkTextbox(hist, font=ui_font("small"), wrap="word")
        self.history_box.pack(fill="both", expand=True)
        self.split.bind("<ButtonRelease-1>", self._remember_split, add="+")
        self.history_box.configure(state="disabled")
        self._bind_wheel(self, {self.table_view, self.history_box, self.list_panel})
        self.bind_class("RandomTablesPageWheel", "<MouseWheel>", self._on_wheel)
        self.bind_class("RandomTablesPageWheel", "<Button-4>", self._on_wheel)
        self.bind_class("RandomTablesPageWheel", "<Button-5>", self._on_wheel)
        self._update_buttons()

    def _remember_split(self, _event=None):
        """Keep the Recent rolls height for the next visit to this page."""
        try:
            total = self.split.winfo_height()
            y = self.split.sash_coord(0)[1]
            self.state["history_height"] = max(HISTORY_MIN, total - y - 8)
        except Exception:
            pass

    # ------------------------------------------------------------------ list

    def refresh(self):
        """Reload the tables (after an edit, or F5)."""
        self.manager.load()
        categories = [ALL_CATEGORIES] + self.manager.categories()
        self.category_menu.configure(values=categories)
        if self.category_var.get() not in categories:
            self.category_var.set(ALL_CATEGORIES)
        self._apply_filter()
        self._update_buttons()                  # (a session may have started since)

    def _schedule_filter(self):
        if self._filter_job is not None:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(150, self._apply_filter)

    def _apply_filter(self):
        self._filter_job = None
        query = self.search_text().strip()
        category = self.category_var.get()
        self.state["query"], self.state["category"] = query, category
        tables = self.manager.search(query)
        if category != ALL_CATEGORIES:
            tables = [t for t in tables if t.category == category]
        keep = self._table.name if self._table else None
        self.list_panel.set_items(tables, keep=keep)
        if self._table is None and tables and query:
            self.list_panel.select_by_name(tables[0].name)

    def search_text(self) -> str:
        return self.search_entry.get()

    def set_search(self, text: str):
        self.search_entry.delete(0, "end")
        if text:
            self.search_entry.insert(0, text)
        self._apply_filter()

    def _clear_filters(self):
        self.search_entry.delete(0, "end")
        self.category_var.set(ALL_CATEGORIES)
        self._apply_filter()

    def select_table(self, name: str) -> bool:
        """Show the table called ``name`` (from the global search or a restored tab)."""
        if not self.list_panel.select_by_name(name):
            self._clear_filters()
            return self.list_panel.select_by_name(name)
        return True

    def _on_select(self, table: Optional[RandomTable]):
        if table is None:
            return
        fresh = self.manager.get_table(table.name) or table
        self._show(fresh)

    def _show(self, table: Optional[RandomTable]):
        self._table = table
        self.state["selected"] = table.name if table else None
        if table is None:
            self.name_label.configure(text="Select a table")
            self.meta_label.configure(text="")
            self.desc_label.configure(text="")
            self.table_view.show(None)
        else:
            self.name_label.configure(text=table.name)
            bits = [table.dice, f"{len(table.entries)} entries"]
            if table.category:
                bits.append(table.category)
            if table.source:
                bits.append(table.source)
            problems = table.problems()
            if problems:
                bits.append("⚠ " + problems[0])
            self.meta_label.configure(text="  ·  ".join(bits))
            self.desc_label.configure(text=table.description)
            self.table_view.show(table)
            self.roll_btn.configure(text=f"🎲 Roll {table.dice}")
        self.result_total.configure(text="")
        self.result_text.configure(text="Roll to get a result.")
        self._update_buttons()

    def _update_buttons(self):
        has = self._table is not None
        for btn in (self.roll_btn, self.edit_btn, self.delete_btn):
            btn.configure(state="normal" if has else "disabled")
        in_session = bool(self.service is not None and getattr(self.service, "in_session", False))
        self.share_check.configure(state="normal" if in_session else "disabled")

    def _roll_selected_from_search(self):
        if self._table is None:
            item = self.list_panel.get_selected()
            if item is None:
                return
            self._show(item)
        self.roll()

    # ------------------------------------------------------------------ rolling

    def roll(self) -> List[TableRoll]:
        """Roll on the shown table (as many times as the ×N menu says) and show the results."""
        if self._table is None:
            return []
        from lan.dice import DiceError
        try:
            count = int(self.count_var.get().lstrip("×"))
        except ValueError:
            count = 1
        try:
            rolls = [self.manager.roll(self._table) for _ in range(count)]
        except DiceError as e:
            messagebox.showerror("Can't roll", f"The die '{self._table.dice}' isn't valid: {e}", parent=self)
            return []
        self._show_rolls(rolls)
        return rolls

    def _show_rolls(self, rolls: List[TableRoll]):
        if len(rolls) == 1:
            r = rolls[0]
            self.result_total.configure(text=str(r.total))
            self.result_text.configure(text=r.text if r.entry else f"No entry covers {r.total}.")
        else:
            self.result_total.configure(text=f"×{len(rolls)}")
            self.result_text.configure(text="\n".join(
                f"{r.total}: {r.text if r.entry else '(no entry)'}" for r in rolls))
        self.table_view.highlight([r.index for r in rolls if r.index is not None])
        history = self.state["history"]
        for r in rolls:
            history.insert(0, r.summary())
        del history[HISTORY_LIMIT:]
        self._show_history()
        if self.share_var.get() and self.service is not None and getattr(self.service, "in_session", False):
            try:
                for r in rolls:
                    self.service.send_chat(f"🎲 {r.summary()}")
            except Exception as e:
                print(f"Could not share the roll: {e}")

    def _show_history(self):
        box = self.history_box
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", "\n".join(self.state.get("history", [])))
        box.configure(state="disabled")

    def _clear_history(self):
        self.state["history"] = []
        self._show_history()

    # ------------------------------------------------------------------ editing

    def _on_new(self):
        self._open_editor(None)

    def _on_edit(self):
        if self._table is not None:
            self._open_editor(self._table)

    def _open_editor(self, table: Optional[RandomTable]):
        dialog = RandomTableEditor(self.winfo_toplevel(), table, self.manager.categories(),
                                   name_taken=lambda n: (self.manager.get_table(n) is not None
                                                         and (table is None or n.lower() != table.name.lower())))
        self.wait_window(dialog)
        result = dialog.result
        if result is None:
            return
        if table is None:
            self.manager.add_table(result)
        else:
            self.manager.update_table(table.name, result)
        self._table = None
        self.refresh()
        self.select_table(result.name)

    def _on_delete(self):
        if self._table is None:
            return
        if not messagebox.askyesno("Delete table", f"Delete the table '{self._table.name}'?", parent=self):
            return
        self.manager.delete_table(self._table.name)
        self._show(None)
        self.refresh()

    def _on_import(self):
        path = filedialog.askopenfilename(parent=self, title="Import random tables",
                                          filetypes=[("Random tables", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            count = self.manager.import_from_json(path)
        except Exception as e:
            messagebox.showerror("Import failed", f"Could not read that file: {e}", parent=self)
            return
        self.refresh()
        messagebox.showinfo("Import", f"Imported {count} table{'s' if count != 1 else ''}.", parent=self)

    def _on_export(self):
        path = filedialog.asksaveasfilename(parent=self, title="Export random tables", defaultextension=".json",
                                            initialfile="random_tables.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        tables = list(self.list_panel._items)
        try:
            count = self.manager.export_to_json(path, tables)
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self)
            return
        messagebox.showinfo("Export", f"Exported {count} table{'s' if count != 1 else ''} (the ones listed).",
                            parent=self)


class RandomTableEditor(ctk.CTkToplevel):
    """Add or edit a table. The entries are plain text, one per line, so a table can be pasted from a book or
    a website as it is."""

    HINT = ("One entry per line: a number or range, then the result (\"01-05 A wandering merchant\", "
            "\"96-00 ...\", or a markdown table). Lines without numbers are numbered for you. "
            "Use {2d6} to roll dice in a result and {table: Name} to roll on another table.")

    def __init__(self, parent, table: Optional[RandomTable], categories: List[str], name_taken=None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.title("Edit Table" if table else "New Table")
        self.geometry("640x720")
        self.minsize(520, 560)
        self.transient(parent)
        self.result: Optional[RandomTable] = None
        self._editing = table
        self._name_taken = name_taken or (lambda n: False)
        self._check_job = None

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        def label(text):
            ctk.CTkLabel(frame, text=text, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")

        label("Name *")
        self.name_entry = ctk.CTkEntry(frame)
        self.name_entry.pack(fill="x", pady=(0, 8))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        col1 = ctk.CTkFrame(row, fg_color="transparent")
        col1.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(col1, text="Die", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.dice_var = ctk.StringVar(value=DEFAULT_DICE)
        self.dice_entry = ctk.CTkComboBox(col1, width=110, variable=self.dice_var,
                                          values=["d4", "d6", "d8", "d10", "d12", "d20", "d100", "2d6", "3d6"],
                                          command=lambda _v: self._schedule_check())
        self.dice_entry.pack()
        self.dice_var.trace_add("write", lambda *_: self._schedule_check())
        col2 = ctk.CTkFrame(row, fg_color="transparent")
        col2.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ctk.CTkLabel(col2, text="Category", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.category_var = ctk.StringVar(value="")
        ctk.CTkComboBox(col2, variable=self.category_var, values=categories or ["Homebrew"]).pack(fill="x")
        col3 = ctk.CTkFrame(row, fg_color="transparent")
        col3.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(col3, text="Source", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.source_entry = ctk.CTkEntry(col3, placeholder_text="e.g., My Campaign")
        self.source_entry.pack(fill="x")

        label("Description")
        self.desc_text = ctk.CTkTextbox(frame, height=60, wrap="word")
        self.desc_text.pack(fill="x", pady=(0, 8))

        label("Entries *")
        ctk.CTkLabel(frame, text=self.HINT, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     justify="left", wraplength=580).pack(anchor="w", pady=(0, 4))
        self.entries_text = ctk.CTkTextbox(frame, wrap="none")
        self.entries_text.pack(fill="both", expand=True)
        self.entries_text.bind("<KeyRelease>", lambda _e: self._schedule_check(), add="+")
        self.entries_text.bind("<<Paste>>", lambda _e: self.after(10, self._schedule_check), add="+")

        self.check_label = ctk.CTkLabel(frame, text="", font=ui_font("small"), anchor="w", justify="left",
                                        wraplength=580)
        self.check_label.pack(fill="x", pady=(4, 0))

        bottom = ctk.CTkFrame(frame, fg_color="transparent")
        bottom.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(bottom, text="Tidy Numbers", width=120,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'),
                      text_color=self.theme.get_current_color('text_primary'),
                      command=self._tidy).pack(side="left")
        add_cancel_save(bottom, self.theme, self.destroy, self._save)

        if table is not None:
            self.name_entry.insert(0, table.name)
            self.dice_var.set(table.dice)
            self.category_var.set(table.category)
            self.source_entry.insert(0, table.source)
            self.desc_text.insert("1.0", table.description)
            self.entries_text.insert("1.0", table.entries_text())
        self._check()
        center_on_parent(self, parent, clamp=True)
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.name_entry.focus_set()
        except tk.TclError:
            pass

    def _parsed(self):
        dice = self.dice_var.get().strip() or None
        text = self.entries_text.get("1.0", "end")
        return parse_entries(text, dice if dice and valid_dice(dice) else None)

    def _schedule_check(self):
        if self._check_job is not None:
            self.after_cancel(self._check_job)
        self._check_job = self.after(250, self._check)

    def _check(self):
        self._check_job = None
        entries, dice = self._parsed()
        typed = self.dice_var.get().strip()
        if typed and not valid_dice(typed):
            self._set_check(f"⚠ '{typed}' isn't a die this can roll (try d100, d20 or 2d6).", warn=True)
            return
        table = RandomTable(name="", dice=typed or dice, entries=entries)
        problems = table.problems()
        if not entries:
            self._set_check("Add some entries.", warn=True)
        elif problems:
            self._set_check("⚠ " + " ".join(problems), warn=True)
        else:
            self._set_check(f"✓ {len(entries)} entries cover every result of {table.dice}.", warn=False)

    def _set_check(self, text: str, warn: bool):
        self.check_label.configure(text=text, text_color=self.theme.get_current_color(
            'text_warning' if warn else 'text_secondary'))

    def _tidy(self):
        """Rewrite the entries in the standard form (and fill in the die if it was empty)."""
        entries, dice = self._parsed()
        if not self.dice_var.get().strip() or not valid_dice(self.dice_var.get().strip()):
            self.dice_var.set(dice)
        table = RandomTable(name="", dice=self.dice_var.get().strip(), entries=entries)
        self.entries_text.delete("1.0", "end")
        self.entries_text.insert("1.0", table.entries_text())
        self._check()

    def _save(self):
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Give the table a name.", parent=self)
            return
        if self._name_taken(name):
            messagebox.showwarning("Name taken", f"There is already a table called '{name}'.", parent=self)
            return
        entries, dice = self._parsed()
        if not entries:
            messagebox.showwarning("No entries", "Add at least one entry.", parent=self)
            return
        typed = self.dice_var.get().strip()
        if typed and not valid_dice(typed):
            messagebox.showwarning("Die", f"'{typed}' isn't a die this can roll.", parent=self)
            return
        old = self._editing
        self.result = RandomTable(
            name=name, dice=typed or dice, entries=entries, category=self.category_var.get().strip(),
            description=self.desc_text.get("1.0", "end").strip(), source=self.source_entry.get().strip(),
            tags=list(old.tags) if old else [],
            is_official=old.is_official if old else False, is_custom=old.is_custom if old else True)
        self.destroy()
