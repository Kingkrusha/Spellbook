"""
Where an editor lives: a pop-up dialog (the collection pages) or a panel inside another page (the Homebrew Studio).

The content editors (spell, feat, magic item, monster...) were written as ``CTkToplevel`` dialogs. Each is now a
*body* class holding all of its behaviour, plus two thin classes built from it::

    class MagicItemEditorBody: ...                                   # the form and what Save / Cancel do
    class MagicItemEditorDialog(MagicItemEditorBody, DialogWindow)   # the dialog the collection page opens
    class MagicItemEditorPanel(MagicItemEditorBody, EmbeddedWindow)  # the same form, inside the Studio

A body only calls window methods that both kinds understand (``title``, ``geometry``, ``transient``, ``grab_set``,
``destroy`` ...), and ends with ``self._finish()`` instead of ``self.destroy()`` so the host decides what finishing
means: a dialog closes, an embedded editor reports to the page that holds it.

Every body also has ``build_result(strict)``: the object the form currently describes. ``strict=True`` is what Save
uses (it raises ``ValueError`` with a readable message when the form is incomplete); ``strict=False`` fills in
anything missing, so the Studio can keep a half-written draft and compare it with the rest of the collection.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

from typography import ui_font


class EditorBody:
    """What every editor body does when Save is pressed.

    The form's ``build_result(strict=True)`` raises ``ValueError`` with a readable message when it is incomplete;
    that is shown as an error box and nothing else happens. Otherwise the result is handed to ``_accept`` (a body
    that must also register it, e.g. with a manager, overrides that) and the editor finishes."""

    ERROR_TITLE = "Error"

    def _accept(self, result):
        self.result = result

    def _save(self):
        try:
            result = self.build_result(strict=True)
        except ValueError as e:
            messagebox.showerror(self.ERROR_TITLE, str(e), parent=self)
            return
        self._accept(result)
        self._finish()

    # ---- small pieces of form every editor builds

    @staticmethod
    def _field_label(parent, text: str, **pack):
        """The bold heading above a field (``pack`` overrides ``anchor="w"``'s company, e.g. ``pady``)."""
        ctk.CTkLabel(parent, text=text, font=ui_font("subheading", 13, bold=True)).pack(anchor="w", **pack)

    def _add_description_editor(self, scroll, height: int = 200):
        """The "Description" heading, the rich-text toolbar and the text box (``self.desc_text``)."""
        from ui.rich_text_utils import RichTextEditor

        self._field_label(scroll, "Description", pady=(10, 0))
        self.desc_text = ctk.CTkTextbox(scroll, height=height)
        self._rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(scroll)
        toolbar.pack(fill="x", pady=(5, 5))
        self.desc_text.pack(fill="x", pady=(0, 10))

    def _add_entry_field(self, parent, label: str, *, width: int = 400, height: int = 35,
                         placeholder: Optional[str] = None, pady=(5, 15)):
        """A heading over a full-width one-line field; returns the entry."""
        self._field_label(parent, label)
        options = {} if placeholder is None else {"placeholder_text": placeholder}
        entry = ctk.CTkEntry(parent, width=width, height=height, **options)
        entry.pack(fill="x", pady=pady)
        return entry

    def _add_section_header(self, parent, label: str, add_text: str, command):
        """A section heading with a green "+ Add ..." button on the right (traits, features ...)."""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(10, 5))

        ctk.CTkLabel(header, text=label, font=ui_font("subheading", 13, bold=True)).pack(side="left")

        ctk.CTkButton(
            header, text=add_text, width=100,
            fg_color=self.theme.get_current_color('button_success'),
            hover_color=self.theme.get_current_color('button_success_hover'),
            command=command
        ).pack(side="right")

    def _add_card(self, container, name_label: str, on_remove, name: str, description: str):
        """One entry of a list a form edits (a trait, a feature): a card with a remove button, a name field and a
        rich-text description. Returns ``(frame, inner, name_entry, desc_entry)``; ``inner`` takes anything more."""
        from ui.rich_text_utils import RichTextEditor

        frame = ctk.CTkFrame(
            container,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=8
        )
        frame.pack(fill="x", pady=5)

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=10)

        # Header with remove button
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x")

        ctk.CTkLabel(header, text=name_label, font=ui_font("body")).pack(side="left")

        remove_btn = ctk.CTkButton(
            header, text="✕", width=25, height=25,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=lambda f=frame: on_remove(f)
        )
        remove_btn.pack(side="right")

        name_entry = ctk.CTkEntry(inner, height=30)
        name_entry.pack(fill="x", pady=(5, 10))
        name_entry.insert(0, name)

        ctk.CTkLabel(inner, text="Description:", font=ui_font("body")).pack(anchor="w")

        desc_entry = ctk.CTkTextbox(inner, height=80)

        # Add rich text toolbar
        rich_editor = RichTextEditor(self, desc_entry, self.theme)
        toolbar = rich_editor.create_toolbar(inner)
        toolbar.pack(fill="x", pady=(5, 5))

        desc_entry.pack(fill="x", pady=(0, 0))
        desc_entry.insert("1.0", description)
        return frame, inner, name_entry, desc_entry

    def _add_save_buttons_left(self, parent):
        """The Save / Cancel row of the longer forms (lineages, backgrounds): both on the left."""
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))

        ctk.CTkButton(
            btn_frame, text="Save",
            width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_secondary'),
            command=self._save
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame, text="Cancel",
            width=100,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self._finish
        ).pack(side="left")

    def _add_save_buttons(self, scroll):
        """The editor's Cancel / Save row at the bottom of the form."""
        from ui.window_utils import add_cancel_save

        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        add_cancel_save(btn_frame, self.theme, self._finish, self._save, outlined=True)


class DialogWindow(ctk.CTkToplevel):
    """The window a stand-alone editor dialog is: finishing closes it."""

    EMBEDDED = False

    def _finish(self):
        self.destroy()


class EmbeddedWindow(ctk.CTkFrame):
    """A frame that answers the window calls an editor makes, so the editor can sit inside a page.

    Anything about the window itself (title, size, position, modality) is ignored; the page decides those.
    ``on_finish(result)`` is called when the form's Save (result is the object) or Cancel (None) is pressed;
    until a host sets it, finishing just destroys the frame."""

    EMBEDDED = True

    def __init__(self, parent, *args, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, *args, **kwargs)
        self.on_finish: Optional[Callable[[Any], None]] = None
        self._embedded_title = ""

    # ---- the Toplevel calls editors make (all no-ops here)
    def title(self, text: Optional[str] = None):
        if text is not None:
            self._embedded_title = text
        return self._embedded_title

    def geometry(self, *args, **kwargs):
        return ""

    def minsize(self, *args, **kwargs):
        return None

    def maxsize(self, *args, **kwargs):
        return None

    def resizable(self, *args, **kwargs):
        return None

    def transient(self, *args, **kwargs):
        return None

    def protocol(self, *args, **kwargs):
        return None

    def attributes(self, *args, **kwargs):
        return None

    def iconbitmap(self, *args, **kwargs):
        return None

    def overrideredirect(self, *args, **kwargs):
        return None

    def grab_set(self):
        return None

    def grab_release(self):
        return None

    def withdraw(self):
        return None

    def deiconify(self):
        return None

    def state(self, *args, **kwargs):
        return "normal"

    # ---- finishing
    def _finish(self):
        callback = self.on_finish
        if callback is not None:
            callback(getattr(self, "result", None))
        else:
            self.destroy()


def form_text(root: tk.Misc) -> List[str]:
    """The text of every text box and entry under ``root`` (placeholders left out) - a quick, editor-independent
    way to see what a form says."""
    out: List[str] = []

    def walk(w: tk.Misc):
        for child in w.winfo_children():
            if isinstance(child, tk.Text):
                try:
                    out.append(child.get("1.0", "end-1c"))
                except tk.TclError:
                    pass
            elif isinstance(child, tk.Entry):
                try:
                    out.append(child.get())
                except tk.TclError:
                    pass
            walk(child)
    walk(root)
    return [t for t in out if t and t.strip()]
