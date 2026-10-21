"""Keyboard shortcuts: the key handling in hotkeys.py and the bindings it makes in Tk."""

import time

import pytest

import hotkeys


def test_normalize_writes_keys_one_way():
    assert hotkeys.normalize("shift+ctrl+f") == "Ctrl+Shift+F"
    assert hotkeys.normalize("Cmd+,") == "Ctrl+,"
    assert hotkeys.normalize("f5") == "F5"
    assert hotkeys.normalize("alt+home") == "Alt+Home"
    assert hotkeys.normalize("Ctrl") == ""
    assert hotkeys.normalize("Ctrl+Banana") == ""
    assert hotkeys.normalize("") == ""


def test_usable_keys():
    assert hotkeys.is_usable("Ctrl+T")
    assert hotkeys.is_usable("F5")
    assert not hotkeys.is_usable("T")             # would fire while typing
    assert not hotkeys.is_usable("Shift+T")
    assert not hotkeys.is_usable("Ctrl+C")        # copy stays copy
    assert not hotkeys.is_usable("Ctrl+Z")


def test_every_default_is_usable_and_unique():
    defaults = {a.id: hotkeys.normalize(a.default) for a in hotkeys.ACTIONS if a.default}
    assert all(hotkeys.is_usable(k) for k in defaults.values())
    assert hotkeys.conflicts(defaults) == {}
    assert len(hotkeys.ACTIONS_BY_ID) == len(hotkeys.ACTIONS)


def test_tk_sequences(monkeypatch):
    monkeypatch.setattr(hotkeys, "IS_MAC", False)
    assert hotkeys.tk_sequences("Ctrl+T") == ["<Control-KeyPress-t>", "<Control-KeyPress-T>"]
    assert hotkeys.tk_sequences("Ctrl+Shift+L") == ["<Control-Shift-KeyPress-L>"]
    assert hotkeys.tk_sequences("Ctrl+,") == ["<Control-KeyPress-comma>"]
    assert hotkeys.tk_sequences("F5") == ["<KeyPress-F5>"]
    monkeypatch.setattr(hotkeys, "IS_MAC", True)
    assert hotkeys.tk_sequences("Ctrl+Alt+1") == ["<Command-Option-KeyPress-1>"]


def test_from_event(monkeypatch):
    monkeypatch.setattr(hotkeys, "IS_MAC", False)
    monkeypatch.setattr(hotkeys.sys, "platform", "linux")
    assert hotkeys.from_event("t", 0x0004) == "Ctrl+T"
    assert hotkeys.from_event("T", 0x0004 | 0x0001) == "Ctrl+Shift+T"
    assert hotkeys.from_event("comma", 0x0004) == "Ctrl+,"
    assert hotkeys.from_event("exclam", 0x0004 | 0x0001) == "Ctrl+Shift+1"
    assert hotkeys.from_event("F5", 0) == "F5"
    assert hotkeys.from_event("Control_L", 0x0004) == ""
    monkeypatch.setattr(hotkeys.sys, "platform", "win32")
    assert hotkeys.from_event("t", 0x0004 | 0x0008) == "Ctrl+T"     # Num Lock is not Alt
    assert hotkeys.from_event("t", 0x0004 | 0x20000) == "Ctrl+Alt+T"


def test_set_binding_moves_a_key_and_keeps_only_changes():
    overrides = hotkeys.set_binding({}, "page.spells", "Ctrl+T")       # Ctrl+T was "New tab"
    table = hotkeys.bindings(overrides)
    assert table["page.spells"] == "Ctrl+T"
    assert table["tab.new"] == ""
    assert hotkeys.conflicts(table) == {}
    # Putting New tab back on its default takes the key back and drops both overrides
    overrides = hotkeys.reset_binding(overrides, "tab.new")
    assert hotkeys.bindings(overrides)["tab.new"] == "Ctrl+T"
    assert hotkeys.bindings(overrides)["page.spells"] == ""
    assert "tab.new" not in overrides
    # Clearing a default is remembered as ""
    assert hotkeys.set_binding({}, "tab.close", "") == {"tab.close": ""}


def test_settings_keep_hotkeys(tmp_path):
    from settings import SettingsManager
    sm = SettingsManager(str(tmp_path / "settings.json"))
    sm.load()
    sm.update(hotkeys={"tab.new": "Ctrl+Shift+N"})
    again = SettingsManager(str(tmp_path / "settings.json"))
    again.load()
    assert again.settings.hotkeys == {"tab.new": "Ctrl+Shift+N"}


# ---------------------------------------------------------------------------
# In Tk


def _pump(root, n=10):
    for _ in range(n):
        root.update()
        time.sleep(0.01)


@pytest.fixture()
def manager(tk_root, monkeypatch):
    monkeypatch.setattr(hotkeys, "IS_MAC", False)
    calls = []
    handlers = {
        "tab.new": lambda: calls.append("new"),
        "view.global_search": lambda: calls.append("search"),
        "text.bold": lambda: False,   # "not here": the key keeps its normal meaning
    }
    m = hotkeys.HotkeyManager(tk_root, handlers, {})
    yield m, calls
    m.apply({"tab.new": "", "view.global_search": "", "text.bold": ""})


def test_shortcut_runs_its_action(tk_root, manager):
    m, calls = manager
    tk_root.deiconify()
    tk_root.focus_force()
    _pump(tk_root)
    tk_root.event_generate("<Control-KeyPress-t>")
    _pump(tk_root)
    assert calls == ["new"]


def test_shortcut_wins_over_text_box_emacs_keys(tk_root, manager):
    import tkinter as tk
    m, calls = manager
    text = tk.Text(tk_root)
    text.pack()
    text.insert("1.0", "keep this line")
    text.mark_set("insert", "1.0")
    text.focus_force()
    _pump(tk_root)
    text.event_generate("<Control-KeyPress-k>")   # Tk's Text would delete to the end of the line
    _pump(tk_root)
    assert calls == ["search"]
    assert text.get("1.0", "end-1c") == "keep this line"
    text.destroy()


def test_rebinding_restores_the_text_box_key(tk_root, manager):
    m, _calls = manager
    original = tk_root.bind_class("Text", "<Control-KeyPress-k>")
    assert original                                   # ours, while bound
    m.apply({"view.global_search": ""})
    restored = tk_root.bind_class("Text", "<Control-KeyPress-k>")
    assert restored != original
    m.apply({})


def test_keys_in_a_dialog_are_left_alone(tk_root, manager):
    import tkinter as tk
    m, calls = manager
    dialog = tk.Toplevel(tk_root)
    entry = tk.Entry(dialog)
    entry.pack()
    entry.focus_force()
    _pump(tk_root)
    entry.event_generate("<Control-KeyPress-t>")
    _pump(tk_root)
    assert calls == []
    dialog.destroy()


def test_bold_shortcut_in_a_description_editor(tk_root):
    import customtkinter as ctk
    from ui.rich_text_utils import RichTextEditor
    from ui.hotkey_actions import focused_rich_editor

    box = ctk.CTkTextbox(tk_root)
    box.pack()
    editor = RichTextEditor(tk_root, box)
    box.insert("1.0", "hello world")
    box._textbox.tag_add("sel", "1.0", "1.5")
    box._textbox.focus_force()
    _pump(tk_root)
    found = focused_rich_editor(tk_root)
    assert found is editor
    found.insert_bold()
    assert box.get("1.0", "end-1c") == "**hello** world"
    box.destroy()
