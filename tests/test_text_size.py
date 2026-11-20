"""Larger text: boxes grow to fit it (ui/text_fit.py), and Settings applies font changes together (Apply, or on
leaving Settings) instead of rebuilding the app after every click."""

import time

import customtkinter as ctk
import pytest

import typography
from typography import get_font_manager, ui_font
from ui import text_fit
from ui.restyle import install_creation_hook

install_creation_hook()


def pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture
def text_size():
    """Set every role's text size (points over the normal size) for a test, and put it back after."""
    manager = get_font_manager()
    before = manager.settings.to_dict()

    def set_delta(delta):
        for role, style in manager.settings.roles.items():
            style.size = typography.ROLE_STOCK_SIZE[role] + delta
        manager.apply(save=False)

    set_delta(0)
    yield set_delta
    manager.settings = typography.FontSettings.from_dict(before)
    manager.apply(save=False)


def test_the_normal_text_size_keeps_the_size_boxes_were_made_with(tk_root, text_size):
    entry = ctk.CTkEntry(tk_root, width=50, height=24, font=ui_font("body"))
    box = ctk.CTkTextbox(tk_root, height=80, font=ui_font("small"))
    combo = ctk.CTkComboBox(tk_root, width=150, height=26, values=["A"], font=ui_font("body"))
    assert (entry._desired_width, entry._desired_height) == (50, 24)
    assert box._desired_height == 80
    assert combo._desired_height == 26
    for w in (entry, box, combo):
        w.destroy()


def test_larger_text_grows_entries_and_text_boxes_and_back_again(tk_root, text_size):
    entry = ctk.CTkEntry(tk_root, width=50, height=24, font=ui_font("body"))
    wide = ctk.CTkEntry(tk_root, width=400, height=24, font=ui_font("body"))
    box = ctk.CTkTextbox(tk_root, height=80, font=ui_font("small"))
    hidden = ctk.CTkTextbox(tk_root, height=0, font=ui_font("small"))
    text_size(6)
    for w, role in ((entry, "body"), (wide, "body"), (box, "small"), (hidden, "small")):
        w.configure(font=ui_font(role))                     # (what the restyle pass does after a change)
    assert entry._desired_height > 24 + 4 and entry._desired_width > 50 * 1.2
    assert wide._desired_width == 400 and wide._desired_height == entry._desired_height
    assert box._desired_height > 80 * 1.3                   # (still shows as many lines)
    assert hidden._desired_height == 0
    entry.configure(height=30)                              # a new size is grown the same way
    assert entry._desired_height == 30 + text_fit.extra_height(entry.cget("font"))
    text_size(0)
    for w, role in ((entry, "body"), (box, "small")):
        w.configure(font=ui_font(role))
    assert (entry._desired_width, entry._desired_height) == (50, 30)
    assert box._desired_height == 80
    for w in (entry, wide, box, hidden):
        w.destroy()


def test_a_fixed_card_grows_to_fit_its_contents(tk_root, text_size):
    card = ctk.CTkFrame(tk_root, width=65, height=60)
    card.pack()
    card.pack_propagate(False)
    label = ctk.CTkLabel(card, text="SPEED", font=ui_font("small", 9, bold=True))
    label.pack(pady=(5, 0))
    entry = ctk.CTkEntry(card, width=40, height=26, font=ui_font("subheading", bold=True))
    entry.pack(pady=3)
    refit = text_fit.grow_with_content(card, 65, 60)
    pump(tk_root)
    assert (int(card.cget("width")), int(card.cget("height"))) == (65, 60)
    text_size(10)
    label.configure(font=ui_font("small", 9, bold=True))
    entry.configure(font=ui_font("subheading", bold=True))
    refit()                             # (a hidden test window gets no <Configure> events)
    pump(tk_root)
    assert int(card.cget("height")) > 60 and int(card.cget("width")) > 65
    card.destroy()


# -- Settings > Typography waits for Apply ------------------------------------------------------------------

@pytest.fixture
def editor(tk_root, text_size, monkeypatch):
    from ui import typography_editor as te
    monkeypatch.setattr(te, "run_busy", lambda key, text, work: work())
    monkeypatch.setattr(get_font_manager(), "save", lambda: True)
    ed = te.TypographyEditor(tk_root, te.GlobalTypographyModel())
    ed.pack()
    pump(tk_root, 0.1)
    yield ed
    ed.destroy()


def test_size_changes_wait_for_apply_and_show_in_the_samples(editor, tk_root):
    manager = get_font_manager()
    body = manager.settings.roles["body"].size
    sample = editor._rows["body"]["sample"]
    before = sample.cget("font").cget("size")
    editor._nudge("body", 2)
    editor._nudge("body", 1)
    assert manager.settings.roles["body"].size == body               # the app is untouched
    assert editor._rows["body"]["size"].cget("text") == str(body + 3)
    assert abs(sample.cget("font").cget("size")) > abs(before)       # ... but the sample shows it
    assert editor.has_pending() and editor.apply_btn.cget("state") == "normal"
    editor.apply_pending()
    assert manager.settings.roles["body"].size == body + 3
    assert not editor.has_pending() and editor.apply_btn.cget("state") == "disabled"


def test_undo_forgets_changes_not_applied(editor):
    manager = get_font_manager()
    body = manager.settings.roles["body"].size
    editor._nudge("body", 4)
    editor._on_preset("Classic Serif (Georgia)")
    editor.discard_pending()
    assert not editor.has_pending()
    assert manager.settings.roles["body"].size == body and manager.settings.family == ""
    assert editor._rows["body"]["size"].cget("text") == str(body)


def test_closing_the_app_saves_changes_without_restyling(editor, monkeypatch):
    manager = get_font_manager()
    applied = []
    monkeypatch.setattr(manager, "apply", lambda save=True: applied.append(save))
    editor._nudge("small", 2)
    editor.apply_pending(restyle=False)
    assert manager.settings.roles["small"].size == typography.ROLE_STOCK_SIZE["small"] + 2
    assert applied == []

