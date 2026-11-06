"""
The window that shapes a collection: a new collection's name, icon and fields, or the fields added to a built-in
collection. The collection's own properties are listed with a lock: they can't be removed or renamed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import List, Optional

import customtkinter as ctk

import custom_collections as cc
from theme import get_theme_manager
from typography import ui_font
from ui.window_utils import add_cancel_save, center_on_parent

ICON_CHOICES = ["🗂️", "⚡", "🏰", "🐉", "🗺️", "👑", "⚜️", "🔮", "🌿", "💀", "🧪", "🎲", "🛡️", "📜", "🌙", "🔥"]
KIND_LABELS = list(cc.FIELD_KINDS.values())
KIND_BY_LABEL = {v: k for k, v in cc.FIELD_KINDS.items()}


class _FieldRow:
    """One added field in the editor: its name, kind, choices (for a choice) and whether it is a filter."""

    def __init__(self, editor: "CollectionTypeEditor", fdef: Optional[cc.FieldDef]):
        self.editor = editor
        self.fdef = fdef                                   # None: a field added in this window
        theme = editor.theme
        self.frame = ctk.CTkFrame(editor.fields_frame, fg_color=theme.get_current_color('bg_secondary'),
                                  corner_radius=8)
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        self.label_entry = ctk.CTkEntry(top, placeholder_text="Field name, e.g. Domain", width=200)
        self.label_entry.pack(side="left", fill="x", expand=True)
        if fdef:
            self.label_entry.insert(0, fdef.label)
        self.kind_var = ctk.StringVar(value=cc.FIELD_KINDS[fdef.kind if fdef else "text"])
        ctk.CTkComboBox(top, values=KIND_LABELS, variable=self.kind_var, state="readonly", width=170,
                        command=lambda _v: self._kind_changed()).pack(side="left", padx=(6, 0))
        for text, command in (("↑", lambda: editor.move(self, -1)), ("↓", lambda: editor.move(self, 1)),
                              ("✕", lambda: editor.remove(self))):
            ctk.CTkButton(top, text=text, width=28, height=28, command=command,
                          fg_color=(theme.get_current_color('button_danger') if text == "✕"
                                    else theme.get_current_color('button_normal')),
                          hover_color=(theme.get_current_color('button_danger_hover') if text == "✕"
                                       else theme.get_current_color('button_hover'))).pack(side="left", padx=(4, 0))
        self.extra = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.extra.pack(fill="x", padx=8, pady=(0, 8))
        self.choices_entry = ctk.CTkEntry(self.extra, placeholder_text="Choices, separated by commas")
        if fdef and fdef.choices:
            self.choices_entry.insert(0, ", ".join(fdef.choices))
        self.filter_var = ctk.BooleanVar(value=fdef.filter if fdef else True)
        self.filter_box = ctk.CTkCheckBox(self.extra, text="Offer as a filter on the page", variable=self.filter_var)
        self._kind_changed()

    @property
    def kind(self) -> str:
        return KIND_BY_LABEL.get(self.kind_var.get(), "text")

    def _kind_changed(self):
        self.choices_entry.pack_forget()
        self.filter_box.pack_forget()
        if self.kind == "choice":
            self.choices_entry.pack(fill="x", pady=(0, 4))
        if self.kind in cc.FILTERABLE_KINDS:
            self.filter_box.pack(anchor="w")
        if self.kind not in cc.FILTERABLE_KINDS and self.kind != "choice":
            self.extra.configure(height=1)

    def to_field(self, taken_ids: List[str]) -> cc.FieldDef:
        label = self.label_entry.get().strip()
        choices = [c.strip() for c in self.choices_entry.get().split(",") if c.strip()]
        fid = self.fdef.id if self.fdef else cc.new_field_id(label or "field", taken_ids)
        return cc.FieldDef(fid, label, self.kind, choices if self.kind == "choice" else [], self.filter_var.get())


class CollectionTypeEditor(ctk.CTkToplevel):
    """Edit ``ctype`` (a copy is edited; nothing is stored until Save). ``ctype`` None: a new collection.

    After the window closes, ``result`` is the stored collection, or ``deleted`` is True."""

    def __init__(self, parent, ctype: Optional[cc.CollectionType] = None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.mgr = cc.get_collection_manager()
        self.original = ctype
        self.builtin = bool(ctype and ctype.builtin)
        self.result: Optional[cc.CollectionType] = None
        self.deleted = False
        self.rows: List[_FieldRow] = []

        if ctype is None:
            title = "New collection"
        elif self.builtin:
            title = f"Fields of {ctype.name}"
        else:
            title = f"Edit {ctype.name}"
        self.title(title)
        self.geometry("620x680")
        self.minsize(520, 420)
        self.transient(parent)

        ctk.CTkLabel(self, text=title, font=ui_font("heading", bold=True), anchor="w").pack(
            fill="x", padx=20, pady=(16, 0))
        intro = ("Add your own fields to this collection. Every entry gets them, official ones too."
                 if self.builtin else
                 "A collection of your own: give it a name and the fields its entries should have.")
        ctk.CTkLabel(self, text=intro, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     anchor="w", justify="left", wraplength=560).pack(fill="x", padx=20)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=20, pady=(8, 16))
        add_cancel_save(buttons, self.theme, self.destroy, self._save, outlined=True,
                        confirm_text="Create" if ctype is None else "Save")
        if ctype is not None and not self.builtin:
            ctk.CTkButton(buttons, text="Delete collection", width=140,
                          fg_color=self.theme.get_current_color('button_danger'),
                          hover_color=self.theme.get_current_color('button_danger_hover'),
                          command=self._delete).pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=14, pady=(10, 0))
        if not self.builtin:
            self._build_identity(ctype)
        self._build_defaults(ctype)

        head = ctk.CTkFrame(self.scroll, fg_color="transparent")
        head.pack(fill="x", pady=(14, 4))
        ctk.CTkLabel(head, text="Your fields", font=ui_font("subheading", bold=True)).pack(side="left")
        ctk.CTkButton(head, text="+ Add field", width=100,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      hover_color=self.theme.get_current_color('accent_hover'),
                      command=self.add_row).pack(side="right")
        self.fields_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.fields_frame.pack(fill="x")
        self.empty_label = ctk.CTkLabel(self.fields_frame, text="No fields yet. Press + Add field.",
                                        font=ui_font("small"), text_color=self.theme.get_text_secondary())
        for fdef in (ctype.fields if ctype else []):
            self.add_row(fdef, focus=False)
        self._layout()

        center_on_parent(self, parent, clamp=True)
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    # ---- the parts of the form

    def _build_identity(self, ctype: Optional[cc.CollectionType]):
        ctk.CTkLabel(self.scroll, text="Name", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", pady=(2, 8))
        self.icon_var = ctk.StringVar(value=ctype.icon if ctype else cc.DEFAULT_ICON)
        ctk.CTkComboBox(row, values=ICON_CHOICES, variable=self.icon_var, width=80).pack(side="left")
        self.name_entry = ctk.CTkEntry(row, placeholder_text="e.g. Deities, Factions, Locations")
        self.name_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        if ctype:
            self.name_entry.insert(0, ctype.name)
        ctk.CTkLabel(self.scroll, text="Short description (shown on its card)",
                     font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.desc_entry = ctk.CTkEntry(self.scroll, placeholder_text="e.g. The gods of my campaign")
        self.desc_entry.pack(fill="x", pady=(2, 8))
        if ctype and ctype.description:
            self.desc_entry.insert(0, ctype.description)

    def _build_defaults(self, ctype: Optional[cc.CollectionType]):
        props = ctype.default_properties if ctype else cc.CUSTOM_DEFAULTS
        box = ctk.CTkFrame(self.scroll, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        box.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(box, text="🔒 Built-in properties (always there, can't be removed)",
                     font=ui_font("small", bold=True), text_color=self.theme.get_text_secondary()).pack(
            anchor="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(box, text="  ·  ".join(props), font=ui_font("body"), wraplength=540, justify="left",
                     anchor="w").pack(anchor="w", padx=10, pady=(0, 8))

    # ---- rows

    def add_row(self, fdef: Optional[cc.FieldDef] = None, focus: bool = True):
        if len(self.rows) >= cc.MAX_FIELDS:
            messagebox.showinfo("Fields", f"A collection can have at most {cc.MAX_FIELDS} added fields.", parent=self)
            return
        row = _FieldRow(self, fdef)
        self.rows.append(row)
        self._layout()
        if focus:
            row.label_entry.focus_set()
            self.after(50, lambda: self._scroll_to_end())

    def _scroll_to_end(self):
        try:
            self.scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _layout(self):
        for row in self.rows:
            row.frame.pack_forget()
        self.empty_label.pack_forget()
        if not self.rows:
            self.empty_label.pack(anchor="w", pady=4)
        for row in self.rows:
            row.frame.pack(fill="x", pady=3)

    def move(self, row: _FieldRow, step: int):
        i = self.rows.index(row)
        j = max(0, min(len(self.rows) - 1, i + step))
        if i != j:
            self.rows[i], self.rows[j] = self.rows[j], self.rows[i]
            self._layout()

    def remove(self, row: _FieldRow):
        label = row.label_entry.get().strip() or "this field"
        if row.fdef is not None and not messagebox.askyesno(
                "Remove field", f"Remove '{label}'?\n\nWhat entries have filled in for it is hidden, not deleted: "
                                f"add a field with the same name again to bring it back.", parent=self):
            return
        self.rows.remove(row)
        row.frame.destroy()
        self._layout()

    # ---- saving

    def build(self) -> cc.CollectionType:
        taken = [r.fdef.id for r in self.rows if r.fdef]
        fields = []
        for row in self.rows:
            f = row.to_field(taken)
            taken.append(f.id)
            fields.append(f)
        if self.builtin:
            return cc.CollectionType(key=self.original.key, name=self.original.name, icon=self.original.icon,
                                     builtin=True, fields=fields, order=self.original.order)
        return cc.CollectionType(key=self.original.key if self.original else "",
                                 name=self.name_entry.get().strip(), icon=self.icon_var.get().strip(),
                                 description=self.desc_entry.get().strip(), fields=fields,
                                 order=self.original.order if self.original else 0)

    def _save(self):
        try:
            self.result = self.mgr.save_type(self.build())
        except cc.CollectionError as e:
            messagebox.showerror("Collection", str(e), parent=self)
            return
        self.destroy()

    def _delete(self):
        ctype = self.original
        count = self.mgr.entry_count(ctype.key)
        what = f" and its {count} entr{'y' if count == 1 else 'ies'}" if count else ""
        if not messagebox.askyesno("Delete collection",
                                   f"Delete the collection '{ctype.name}'{what}?\n\nThis can't be undone "
                                   f"(a backup or an export keeps a copy).", icon="warning", parent=self):
            return
        self.mgr.delete_type(ctype.key)
        self.deleted = True
        self.destroy()
