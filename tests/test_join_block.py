"""The join prompt's third answer: Block keeps a device out for the rest of the session (ui/session_widgets.py)."""

import customtkinter as ctk

from ui.session_widgets import ApprovalDialog


def buttons(widget):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            yield child
        yield from buttons(child)


def test_the_prompt_lets_in_denies_or_blocks(tk_root):
    answers = []
    for label in ("Let them in", "Deny", "Block"):
        dialog = ApprovalDialog(tk_root, "Mallory", "192.168.1.9", lambda *a: answers.append(a))
        tk_root.update()
        found = {b.cget("text"): b for b in buttons(dialog)}
        assert set(found) == {"Let them in", "Deny", "Block"}
        found[label].invoke()
        tk_root.update()
    assert answers == [(True,), (False,), (False, True)]

