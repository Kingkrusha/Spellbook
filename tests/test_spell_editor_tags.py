"""The spell editor's tag section (the shared TagEditor): what is editable, what is kept aside, what the picker offers."""

import time

import pytest


def pump(root, n=8):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


@pytest.fixture()
def editor_for(tk_root):
    import ui.spell_editor as spell_editor
    from spell import is_protected_tag
    from spell_manager import SpellManager

    manager = SpellManager()
    manager.load_spells()
    made = []

    def build(spell=None):
        host = spell_editor.ctk.CTkFrame(tk_root)
        host.pack(fill="both", expand=True)
        panel = spell_editor.SpellEditorPanel(host, "Edit" if spell else "New", spell=spell, spell_manager=manager)
        panel.pack(fill="both", expand=True)
        pump(tk_root)
        made.append(host)
        return panel

    yield build, manager, is_protected_tag
    for host in made:
        host.destroy()


def official_spell(manager):
    return next(s for s in manager.spells if s.name == "Fireball")


def test_an_official_spells_tags_split_into_protected_and_editable(editor_for):
    build, manager, is_protected_tag = editor_for
    spell = official_spell(manager)
    editor = build(spell)

    protected = [t for t in spell.tags if is_protected_tag(t)]
    editable = [t for t in spell.tags if not is_protected_tag(t)]
    assert protected, "an official spell carries the protected Official tag"
    assert editor.tag_editor.get_tags() == editable                     # only the editable ones are in the form

    result = editor.build_result(strict=False)
    assert result.tags == protected + editable                           # saving puts the protected ones back


def test_added_and_removed_tags_reach_the_result(editor_for, monkeypatch):
    build, manager, is_protected_tag = editor_for
    editor = build(None)
    import ui.tag_editor as tag_editor

    picked = {}

    class Picker:
        def __init__(self, parent, available, selected, is_protected=None):
            picked["available"], picked["selected"], picked["is_protected"] = available, list(selected), is_protected
            self.result = "Homebrew Tag"

    monkeypatch.setattr(tag_editor, "TagPickerDialog", Picker)
    editor.wait_window = lambda w: None
    editor.tag_editor.wait_window = lambda w: None

    editor.tag_editor._on_add_tag()
    assert picked["is_protected"] is is_protected_tag                    # the picker refuses the protected tags
    assert picked["available"] == manager.get_all_tags()                 # and offers the tags in use
    assert editor.tag_editor.get_tags() == ["Homebrew Tag"]
    assert "Homebrew Tag" in editor.build_result(strict=False).tags

    editor.tag_editor._remove_tag("Homebrew Tag")
    assert editor.tag_editor.get_tags() == []
    assert "Homebrew Tag" not in editor.build_result(strict=False).tags


def test_the_tag_picker_leaves_out_protected_tags_and_refuses_them_when_typed(tk_root, monkeypatch):
    from tkinter import messagebox
    from spell import is_protected_tag
    from ui.tag_editor import TagPickerDialog

    warned = []
    monkeypatch.setattr(messagebox, "showwarning", lambda title, message, **k: warned.append(message))

    picker = TagPickerDialog(tk_root, ["Fire", "Official", "Cold"], ["Cold"], is_protected=is_protected_tag)
    pump(tk_root)
    try:
        assert picker._available == ["Fire"]                              # not "Official" (protected), not "Cold" (taken)
        picker._new_tag_entry.insert(0, "Official")
        picker._on_add_new()
        assert picker.result is None and "protected tag" in warned[-1]
    finally:
        picker.destroy()

    plain = TagPickerDialog(tk_root, ["Fire", "Official"], [])
    pump(tk_root)
    try:
        assert plain._available == ["Fire", "Official"]                  # no rule given: nothing is protected
    finally:
        plain.destroy()
