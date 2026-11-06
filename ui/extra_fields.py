"""
Added fields on the pages: the inputs a field is edited with, the box that shows a built-in entry's added fields
in its detail pane, and the small window that edits them. See custom_collections.py for what a field is.

Every built-in detail pane makes one :class:`ExtraFieldsBox` and calls ``show(name)`` whenever it shows another
entry. The box takes no room at all while its collection has no added fields.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import custom_collections as cc
from theme import get_theme_manager
from typography import ui_font
from ui.window_utils import add_cancel_save, center_on_parent

NONE_CHOICE = "(none)"


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

class FieldInput:
    """The widget(s) one field is edited with. ``frame`` holds them; ``get()`` returns the value in the field's
    shape (raises CollectionError for a number that isn't one)."""

    def __init__(self, parent, fdef: cc.FieldDef, value=None, owner=None):
        self.fdef = fdef
        self.theme = get_theme_manager()
        self.frame = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(self.frame, text=fdef.label, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        kind = fdef.kind
        self.widget = None
        if kind == "long_text":
            self.widget = ctk.CTkTextbox(self.frame, height=90, wrap="word")
            self.widget.pack(fill="x", pady=(2, 10))
            if value:
                self.widget.insert("1.0", str(value))
            try:            # [[links]] typed here get the same suggestions as a description
                from ui.rich_text_utils import RichTextEditor
                self._rich = RichTextEditor(owner or parent, self.widget, self.theme)
            except Exception:
                self._rich = None
        elif kind == "yes_no":
            self.var = ctk.BooleanVar(value=bool(value))
            self.widget = ctk.CTkCheckBox(self.frame, text="Yes", variable=self.var)
            self.widget.pack(anchor="w", pady=(2, 10))
        elif kind == "choice":
            values = [NONE_CHOICE] + list(fdef.choices)
            current = str(value) if value else NONE_CHOICE
            if current not in values:            # a value from before the choice was removed stays offered
                values.append(current)
            self.var = ctk.StringVar(value=current)
            self.widget = ctk.CTkComboBox(self.frame, values=values, variable=self.var, state="readonly",
                                          width=260)
            self.widget.pack(anchor="w", pady=(2, 10))
        else:
            hint = {"number": "A number, e.g. 3 or 2.5", "list": "Separate the words with commas"}.get(kind, "")
            self.widget = ctk.CTkEntry(self.frame, placeholder_text=hint or None)
            self.widget.pack(fill="x", pady=(2, 10))
            text = fdef.display(value) if value not in (None, "", []) else ""
            if text:
                self.widget.insert(0, text)

    def get(self):
        kind = self.fdef.kind
        if kind == "long_text":
            raw = self.widget.get("1.0", "end-1c")
        elif kind == "yes_no":
            raw = self.var.get()
        elif kind == "choice":
            raw = self.var.get()
            raw = "" if raw == NONE_CHOICE else raw
        else:
            raw = self.widget.get()
        try:
            return self.fdef.clean(raw)
        except cc.CollectionError as e:
            raise cc.CollectionError(f"{self.fdef.label}: {e}")


def build_inputs(parent, fields: List[cc.FieldDef], values: Dict, owner=None) -> List[FieldInput]:
    inputs = []
    for fdef in fields:
        inp = FieldInput(parent, fdef, (values or {}).get(fdef.id), owner=owner)
        inp.frame.pack(fill="x")
        inputs.append(inp)
    return inputs


def read_inputs(inputs: List[FieldInput]) -> Dict:
    """The values the inputs hold, by field id (raises CollectionError naming a bad field)."""
    return {inp.fdef.id: inp.get() for inp in inputs}


# --------------------------------------------------------------------------- #
# Showing values
# --------------------------------------------------------------------------- #

def render_values(parent, fields: List[cc.FieldDef], values: Dict, theme=None, wraplength: int = 420,
                  bg_color: str = "bg_primary") -> List:
    """Labelled values, one per filled-in field: short values as "Label: value" lines, long text below its label
    with the same formatting as a description. Returns the widgets made."""
    theme = theme or get_theme_manager()
    widgets = []
    for fdef in fields:
        value = (values or {}).get(fdef.id)
        if fdef.is_empty(value):
            continue
        if fdef.kind == "long_text":
            head = ctk.CTkLabel(parent, text=fdef.label, font=ui_font("body", bold=True), anchor="w")
            head.pack(anchor="w", pady=(4, 0))
            widgets.append(head)
            from ui.rich_text_utils import render_description_blocks
            widgets.extend(render_description_blocks(parent, str(value), theme, bg_color=bg_color))
            continue
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", anchor="w", pady=1)
        ctk.CTkLabel(row, text=f"{fdef.label}:", font=ui_font("body", bold=True)).pack(side="left", anchor="n")
        ctk.CTkLabel(row, text=fdef.display(value), font=ui_font("body"), wraplength=wraplength,
                     justify="left", anchor="w").pack(side="left", padx=(6, 0), anchor="n", fill="x")
        widgets.append(row)
    return widgets


class ExtraFieldsBox(ctk.CTkFrame):
    """A built-in entry's added fields, in its detail pane, with an Edit button. Empty (and 1 px high) while the
    collection has no added fields."""

    def __init__(self, parent, collection: str, wraplength: int = 420, bg_color: str = "bg_primary", **kwargs):
        super().__init__(parent, fg_color="transparent", height=1, **kwargs)
        self.collection = collection
        self.wraplength = wraplength
        self.bg_color = bg_color
        self.theme = get_theme_manager()
        self.mgr = cc.get_collection_manager()
        self.name: Optional[str] = None
        self._widgets: List = []
        self.mgr.add_listener(self._on_definitions_changed)
        self.mgr.add_value_listener(self._on_values_changed)

    def destroy(self):
        self.mgr.remove_listener(self._on_definitions_changed)
        self.mgr.remove_value_listener(self._on_values_changed)
        super().destroy()

    def _alive(self) -> bool:
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _on_definitions_changed(self):
        if self._alive():
            self.show(self.name)

    def _on_values_changed(self, collection: str, name: str):
        if self._alive() and collection == self.collection and (name or "").lower() == (self.name or "").lower():
            self.show(self.name)

    def _clear(self):
        for w in self._widgets:
            try:
                w.destroy()
            except tk.TclError:
                pass
        self._widgets = []
        self.configure(height=1)

    def show(self, name: Optional[str]):
        """Show the added fields of the entry called ``name`` (None: nothing)."""
        self.name = name
        self._clear()
        if not name:
            return
        try:
            fields = self.mgr.builtin_fields(self.collection)
        except Exception as e:
            print(f"Could not read the added fields of {self.collection}: {e}")
            return
        if not fields:
            return
        values = self.mgr.extra_values(self.collection, name)
        card = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        card.pack(fill="x", pady=(4, 8))
        self._widgets.append(card)
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(head, text="Your fields", font=ui_font("small", bold=True),
                     text_color=self.theme.get_text_secondary()).pack(side="left")
        ctk.CTkButton(head, text="✎ Edit", width=60, height=22, font=ui_font("small"),
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'),
                      command=self.edit).pack(side="right")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=10, pady=(0, 8))
        shown = render_values(body, fields, values, self.theme, self.wraplength, bg_color='bg_secondary')
        if not shown:
            ctk.CTkLabel(body, text="Nothing filled in yet.", font=ui_font("small"),
                         text_color=self.theme.get_text_secondary()).pack(anchor="w")

    def edit(self):
        if not self.name:
            return
        dialog = ExtraValuesDialog(self.winfo_toplevel(), self.collection, self.name)
        self.wait_window(dialog)


class ExtraValuesDialog(ctk.CTkToplevel):
    """Edit the added fields of one built-in entry (official ones too: the values are the user's own)."""

    def __init__(self, parent, collection: str, name: str):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.mgr = cc.get_collection_manager()
        self.collection, self.name = collection, name
        self.saved = False
        self.title(f"Your fields: {name}")
        self.geometry("480x520")
        self.minsize(380, 300)
        self.transient(parent)

        ctk.CTkLabel(self, text=name, font=ui_font("heading", bold=True), anchor="w").pack(
            fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(self, text=f"Fields you added to {cc.BUILTIN_TYPES[collection][0]}",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary(), anchor="w").pack(
            fill="x", padx=20)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=20, pady=(8, 16))
        add_cancel_save(buttons, self.theme, self.destroy, self._save, outlined=True)
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=14, pady=(10, 0))
        self.inputs = build_inputs(scroll, self.mgr.builtin_fields(collection),
                                   self.mgr.extra_values(collection, name), owner=self)
        center_on_parent(self, parent, clamp=True)
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _save(self):
        try:
            values = read_inputs(self.inputs)
        except cc.CollectionError as e:
            messagebox.showerror("Your fields", str(e), parent=self)
            return
        self.mgr.set_extra_values(self.collection, self.name, values)
        self.saved = True
        self.destroy()


def show_extra_fields(panel, collection: str, name: Optional[str], parent=None, **pack):
    """Show ``name``'s added fields at the end of ``parent`` (default: the panel's ``scroll_frame``).

    The box is made the first time and moved to the end of its parent every time, so it always follows whatever
    the panel has just laid out. ``pack`` overrides how it is packed (default: full width)."""
    box = getattr(panel, "_extra_fields_box", None)
    try:
        alive = box is not None and box.winfo_exists()
    except tk.TclError:
        alive = False
    if not alive:
        box = ExtraFieldsBox(parent if parent is not None else panel.scroll_frame, collection)
        panel._extra_fields_box = box
    box.pack_forget()
    box.pack(**({"fill": "x", "anchor": "w"} | pack))
    box.show(name)
    return box
