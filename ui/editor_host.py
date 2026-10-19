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
