"""
The page of a collection someone made (Collections > a card they created): a searchable, filterable list of its
entries beside the selected entry's details, with add / edit / duplicate / delete, the Select bar (tags, source,
Export PDF) and the collection's Fields button. Its filters come from the collection's own fields.
"""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox
from typing import Dict, List, Optional

import customtkinter as ctk

import custom_collections as cc
from theme import get_theme_manager
from typography import ui_font
from ui.bulk_actions import BulkActionsMixin
from ui.collection_page import CollectionPageMixin
from ui.extra_fields import build_inputs, read_inputs, render_values
from ui.filter_widgets import SourceFilterMode
from ui.theme_listener import ThemeListenerMixin
from ui.virtual_list import VirtualListPanel
from ui.window_utils import add_cancel_save, center_on_parent

ANY = "Any"
MAX_FILTERS_PER_ROW = 4


class CustomEntryList(VirtualListPanel):
    TITLE = "Entries"
    NOUN = "entry"

    def __init__(self, parent, ctype: cc.CollectionType, **kwargs):
        self.ctype = ctype
        self.TITLE = ctype.name
        super().__init__(parent, **kwargs)

    def _count_text(self, n: int) -> str:
        return f"{n} entr{'y' if n == 1 else 'ies'}"

    def row_text(self, entry: cc.CustomEntry) -> str:
        hints = []
        for f in self.ctype.fields:
            if f.kind in ("choice", "text", "number") and not f.is_empty(entry.values.get(f.id)):
                text = f.display(entry.values[f.id])
                if text and len(text) <= 30:
                    hints.append(text)
            if len(hints) == 2:
                break
        return f"{entry.name}  ({', '.join(hints)})" if hints else entry.name


class CustomEntryDetail(ThemeListenerMixin, ctk.CTkFrame):
    """The selected entry: its name, collection and source, tags, field values and description."""

    def __init__(self, parent, ctype: cc.CollectionType):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self.ctype = ctype
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=15, pady=15)
        self._widgets: List = []
        self.entry: Optional[cc.CustomEntry] = None
        self.theme.add_listener(self._on_theme_changed)
        self.show(None)

    def _on_theme_changed(self):
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))

    def _add(self, widget, **pack):
        widget.pack(**({"anchor": "w"} | pack))
        self._widgets.append(widget)
        return widget

    def show(self, entry: Optional[cc.CustomEntry]):
        self.entry = entry
        for w in self._widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._widgets = []
        if entry is None:
            self._add(ctk.CTkLabel(self.scroll, text=f"Select an entry", font=ui_font("title", bold=True)))
            if not self.ctype.fields:
                self._add(ctk.CTkLabel(
                    self.scroll, text="Tip: press ⚙ Fields to give this collection fields of its own "
                                      "(a choice, a number, yes / no ...).",
                    font=ui_font("small"), text_color=self.theme.get_text_secondary(), wraplength=420,
                    justify="left"), pady=(8, 0))
            return
        self._add(ctk.CTkLabel(self.scroll, text=entry.name, font=ui_font("title", bold=True), wraplength=440,
                               justify="left"))
        line = self.ctype.title + (f"  ·  Source: {entry.source}" if entry.source else "")
        self._add(ctk.CTkLabel(self.scroll, text=line, font=ui_font("small"),
                               text_color=self.theme.get_text_secondary()), pady=(0, 6))
        if entry.tags:
            self._add(ctk.CTkLabel(self.scroll, text="Tags: " + ", ".join(entry.tags), font=ui_font("small"),
                                   text_color=self.theme.get_text_secondary(), wraplength=440, justify="left"),
                      pady=(0, 6))
        values = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self._add(values, fill="x", pady=(0, 8))
        render_values(values, self.ctype.fields, entry.values, self.theme)
        if not values.winfo_children():
            values.configure(height=1)
        if entry.description:
            from ui.rich_text_utils import render_description_blocks
            self._widgets.extend(render_description_blocks(self.scroll, entry.description, self.theme))


class CustomCollectionView(BulkActionsMixin, CollectionPageMixin, ctk.CTkFrame):
    """The page of one collection someone made (``key`` is its key, without the "custom:" prefix)."""

    MANAGER_ATTR = "_sources_provider"
    PLURAL = "entries"
    BULK_ACTIONS = ("tags", "source")
    BULK_NOUN, BULK_PLURAL = "entry", "entries"

    def __init__(self, parent, key: str, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))
        self.key = key
        self.mgr = cc.get_collection_manager()
        self.character_manager = character_manager
        self.on_back = on_back
        self._selected_sources: List[str] = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._filter_debounce_id: Optional[str] = None
        self._filter_debounce_delay = 150
        self._field_vars: Dict[str, ctk.StringVar] = {}
        self._all: List[cc.CustomEntry] = []
        self._context_entry: Optional[cc.CustomEntry] = None
        self._sources_provider = self
        self.ctype: Optional[cc.CollectionType] = None
        self._build()
        self.theme.add_listener(self._on_theme_changed)
        self.mgr.add_listener(self._on_definitions_changed)

    def destroy(self):
        self.mgr.remove_listener(self._on_definitions_changed)
        try:
            self.theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()

    # the source filter asks its "manager" for every source
    def get_all_sources(self) -> List[str]:
        return self.mgr.all_sources(self.key)

    # ------------------------------------------------------------------ building

    def _build(self, keep: Optional[str] = None):
        for child in self.winfo_children():
            child.destroy()
        self._field_vars = {}
        self.ctype = self.mgr.custom_type(self.key)
        self._shown_definition = self.ctype.to_dict() if self.ctype else None
        if self.ctype is None:
            self._build_gone()
            return
        self.BULK_NOUN, self.BULK_PLURAL = "entry", "entries"
        self._create_widgets()
        self._setup_bulk_actions()
        self._build_context_menu([("Edit", self._context_edit), ("Duplicate", self._context_duplicate),
                                  ("Delete", self._context_delete)])
        self._load(keep)

    def _build_gone(self):
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(expand=True)
        ctk.CTkLabel(box, text="This collection was deleted.", font=ui_font("heading", bold=True)).pack(pady=8)
        if self.on_back:
            ctk.CTkButton(box, text="← Collections", command=self.on_back).pack()

    def _create_filter_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=10)
        self._add_back_button(bar)
        self._add_search_entry(bar, f"Search {self.ctype.name.lower()}...", 200)
        self._add_action_buttons(bar, "+ Add Entry", 110, self._on_add, self._on_edit, self._on_delete,
                                 start_disabled=True)
        ctk.CTkButton(bar, text="⚙ Fields", width=90, height=35,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'),
                      command=self._edit_fields).pack(side="right", padx=(0, 10))

        row = self._filter_row()
        self._add_source_filter(row)
        tags = self.mgr.all_tags(self.key)
        if tags:
            self._add_filter_combo(row, "tag", "Tag:", ANY, [ANY] + tags, 140)
        filters = [f for f in self.ctype.fields if f.filterable]
        count = 1 if tags else 0
        for f in filters:
            if count >= MAX_FILTERS_PER_ROW:
                row = self._filter_row()
                count = 0
            name = f"field_{len(self._field_vars)}"
            options = [ANY] + self.mgr.field_options(self.key, f)
            self._add_filter_combo(row, name, f"{f.label}:", ANY, options, 130)
            self._field_vars[f.id] = getattr(self, f"{name}_var")
            count += 1
        self._add_clear_button(row)

    def _create_panes(self):
        self.list_panel = CustomEntryList(self.paned, self.ctype, on_select=self._on_selected,
                                          on_right_click=self._on_right_click)
        self.detail_panel = CustomEntryDetail(self.paned, self.ctype)
        self.paned.add(self.list_panel, minsize=280, stretch="always")
        self.paned.add(self.detail_panel, minsize=400, stretch="always")

    def _on_definitions_changed(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        now = self.mgr.custom_type(self.key)
        if now is not None and self.ctype is not None and now.to_dict() == self._shown_definition:
            # another collection changed, or an import came in: only the entries may differ
            self.ctype = now
            self.refresh()
            return
        selected = self.list_panel.get_selected() if hasattr(self, "list_panel") else None
        self._build(selected.name if selected else None)

    # ------------------------------------------------------------------ data

    def _load(self, keep: Optional[str] = None):
        self._all = self.mgr.entries(self.key)
        if keep:
            self.list_panel.select_when_listed(keep)
        self._on_filter_changed(immediate=True)

    def refresh(self):
        selected = self.list_panel.get_selected() if hasattr(self, "list_panel") else None
        if self.ctype is None or self.mgr.custom_type(self.key) is None:
            self._build()
            return
        self._load(selected.name if selected else None)

    def _clear_filters(self):
        self.search_var.set("")
        self.titles_var.set(False)
        if hasattr(self, "tag_var"):
            self.tag_var.set(ANY)
        for var in self._field_vars.values():
            var.set(ANY)
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._update_source_label()
        self._on_filter_changed(immediate=True)

    def _matches_field(self, f: cc.FieldDef, value, wanted: str) -> bool:
        if wanted == ANY:
            return True
        if f.kind == "yes_no":
            return bool(value) == (wanted == "Yes")
        if isinstance(value, list):
            return any(str(v).lower() == wanted.lower() for v in value)
        return str(value or "").lower() == wanted.lower()

    def _apply_filters(self):
        self._filter_debounce_id = None
        if self.ctype is None:
            return
        search = self.search_var.get().lower().strip()
        tag = self.tag_var.get() if hasattr(self, "tag_var") else ANY
        fields = {f.id: f for f in self.ctype.fields}
        out = []
        for e in self._all:
            texts = lambda e=e: [e.plain_description(), " ".join(e.tags)] + [
                fields[k].display(v) for k, v in e.values.items() if k in fields]
            if not self._passes_search(search, e.name, texts):
                continue
            if not self._passes_source_filter(e.source):
                continue
            if tag != ANY and tag.lower() not in {t.lower() for t in e.tags}:
                continue
            if not all(self._matches_field(fields[fid], e.values.get(fid), var.get())
                       for fid, var in self._field_vars.items() if fid in fields):
                continue
            out.append(e)
        self.list_panel.set_items(out)

    # ------------------------------------------------------------------ selection and actions

    def _on_selected(self, entry: Optional[cc.CustomEntry]):
        self.detail_panel.show(entry)
        state = "normal" if entry else "disabled"
        self.edit_btn.configure(state=state)
        self.delete_btn.configure(state=state)

    def _on_right_click(self, entry, x: int, y: int):
        self._context_entry = entry
        try:
            self.context_menu.tk_popup(x, y)
        finally:
            self.context_menu.grab_release()

    def _edit_fields(self):
        from ui.collection_type_editor import CollectionTypeEditor
        dialog = CollectionTypeEditor(self.winfo_toplevel(), self.mgr.custom_type(self.key))
        self.wait_window(dialog)
        if dialog.deleted and self.on_back:
            self.on_back()

    def _open_editor(self, title: str, entry: Optional[cc.CustomEntry]) -> Optional[cc.CustomEntry]:
        dialog = CustomEntryEditor(self.winfo_toplevel(), title, self.ctype, entry,
                                   sources=self.mgr.all_sources(self.key))
        self.wait_window(dialog)
        return dialog.result

    def _on_add(self):
        result = self._open_editor(f"New {self.ctype.name} entry", None)
        if result is None:
            return
        if not self.mgr.add_entry(result):
            messagebox.showerror("Add entry", f"There is already an entry called '{result.name}'.", parent=self)
            return
        self._load(result.name)

    def _edit(self, entry: Optional[cc.CustomEntry]):
        if entry is None:
            return
        result = self._open_editor(f"Edit {entry.name}", entry)
        if result is None:
            return
        if not self.mgr.update_entry(entry.name, result):
            messagebox.showerror("Edit entry", f"There is already an entry called '{result.name}'.", parent=self)
            return
        self._load(result.name)

    def _on_edit(self):
        self._edit(self.list_panel.get_selected())

    def _delete(self, entry: Optional[cc.CustomEntry]):
        if entry is None:
            return
        if not messagebox.askyesno("Delete entry", f"Delete '{entry.name}'?", parent=self):
            return
        self.mgr.delete_entry(self.key, entry.name)
        self.detail_panel.show(None)
        self._on_selected(None)
        self._load()

    def _on_delete(self):
        self._delete(self.list_panel.get_selected())

    def _context_edit(self):
        self._edit(self._context_entry)

    def _context_delete(self):
        self._delete(self._context_entry)

    def _context_duplicate(self):
        entry = self._context_entry
        if entry is None:
            return
        twin = copy.deepcopy(entry)
        n = 2
        while self.mgr.get_entry(self.key, f"{entry.name} ({n})") is not None:
            n += 1
        twin.name, twin.id = f"{entry.name} ({n})", 0
        self.mgr.add_entry(twin)
        self._load(twin.name)

    def select_entry(self, name: str) -> bool:
        return self.list_panel.select_by_name(name)

    # ------------------------------------------------------------------ the Select bar

    def _bulk_fetch(self, name: str):
        return self.mgr.get_entry(self.key, name)

    def _bulk_store(self, entries: list) -> int:
        with self.mgr.batch():
            return sum(bool(self.mgr.update_entry(e.name, e)) for e in entries)

    def _bulk_reload(self):
        self._load()

    def _bulk_all_tags(self) -> List[str]:
        return self.mgr.all_tags(self.key)

    def _bulk_all_sources(self) -> List[str]:
        return self.mgr.all_sources(self.key)

    def _bulk_give(self, character, entries: list):
        return None


class CustomEntryEditor(ctk.CTkToplevel):
    """Add or edit one entry. ``result`` is the entry the form describes once Save is pressed (not yet stored)."""

    def __init__(self, parent, title: str, ctype: cc.CollectionType, entry: Optional[cc.CustomEntry] = None,
                 sources: Optional[List[str]] = None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.ctype = ctype
        self.entry = entry
        self.result: Optional[cc.CustomEntry] = None
        self.title(title)
        self.geometry("620x720")
        self.minsize(480, 420)
        self.transient(parent)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=20, pady=(8, 16))
        add_cancel_save(buttons, self.theme, self.destroy, self._save, outlined=True)
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=14, pady=(14, 0))

        def heading(text):
            ctk.CTkLabel(scroll, text=text, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")

        heading("Name")
        self.name_entry = ctk.CTkEntry(scroll)
        self.name_entry.pack(fill="x", pady=(2, 10))
        heading("Source")
        self.source_var = ctk.StringVar(value=entry.source if entry else "")
        ctk.CTkComboBox(scroll, values=sources or [""], variable=self.source_var).pack(fill="x", pady=(2, 10))
        heading("Tags")
        self.tags_entry = ctk.CTkEntry(scroll, placeholder_text="Separate tags with commas")
        self.tags_entry.pack(fill="x", pady=(2, 10))

        self.inputs = build_inputs(scroll, ctype.fields, entry.values if entry else {}, owner=self)

        heading("Description")
        self.desc_text = ctk.CTkTextbox(scroll, height=200, wrap="word")
        from ui.rich_text_utils import RichTextEditor
        self._rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        self._rich_editor.create_toolbar(scroll).pack(fill="x", pady=(4, 4))
        self.desc_text.pack(fill="x", pady=(0, 10))

        if entry:
            self.name_entry.insert(0, entry.name)
            if entry.tags:
                self.tags_entry.insert(0, ", ".join(entry.tags))
            if entry.description:
                self.desc_text.insert("1.0", entry.description)
        center_on_parent(self, parent, clamp=True)
        self.after(50, self._grab)
        self.name_entry.focus_set()

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def build_result(self) -> cc.CustomEntry:
        name = self.name_entry.get().strip()
        if not name:
            raise cc.CollectionError("The entry needs a name.")
        values = read_inputs(self.inputs)
        return cc.CustomEntry(collection=self.ctype.key, name=name,
                              description=self.desc_text.get("1.0", "end-1c").strip(),
                              source=self.source_var.get().strip(),
                              tags=[t.strip() for t in self.tags_entry.get().split(",") if t.strip()],
                              values=values, id=self.entry.id if self.entry else 0)

    def _save(self):
        try:
            self.result = self.build_result()
        except cc.CollectionError as e:
            messagebox.showerror("Entry", str(e), parent=self)
            return
        self.destroy()
