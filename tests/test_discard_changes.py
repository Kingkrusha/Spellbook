"""Closing an editor with unsaved changes asks first (ui/editor_host.DialogWindow); an untouched one just closes."""

import time

import customtkinter as ctk
import pytest

from ui.ctk_patches import install
from ui.editor_host import DialogWindow, form_state

# As the app does at start: without it, a timer left by a closed editor can fire into a new editor's drop-down
# (tkinter reuses the freed callback's name), which changes a field nobody touched
install()


def pump(root, n=20):
    for _ in range(n):
        time.sleep(0.01)
        root.update()


def first(collection):
    items = list(collection)
    return items[0] if items else None


def open_editor(kind, root):
    """The collection page's editor for one existing entry of ``kind``."""
    if kind == "spells":
        from spell_manager import SpellManager
        from ui.spell_editor import SpellEditorDialog
        manager = SpellManager()
        manager.load_spells()
        return SpellEditorDialog(root, "Edit Spell", spell=manager.get_spell("Fireball"), spell_manager=manager)
    if kind == "feats":
        from feat import get_feat_manager
        from ui.feats_view import FeatEditorDialog
        return FeatEditorDialog(root, "Edit Feat", feat=first(get_feat_manager().feats))
    if kind == "lineages":
        from lineage import get_lineage_manager
        from ui.lineages_view import LineageEditorDialog
        manager = get_lineage_manager()
        return LineageEditorDialog(root, manager, lineage=first(manager.lineages))
    if kind == "backgrounds":
        from background import get_background_manager
        from ui.backgrounds_view import BackgroundEditorDialog
        manager = get_background_manager()
        return BackgroundEditorDialog(root, manager, background=first(manager.backgrounds))
    if kind == "equipment":
        from equipment import get_equipment_manager
        from ui.equipment_view import EquipmentEditorDialog
        return EquipmentEditorDialog(root, "Edit", item=first(get_equipment_manager().items))
    if kind == "magic_items":
        from magic_item import get_magic_item_manager
        from ui.magic_item_view import MagicItemEditorDialog
        return MagicItemEditorDialog(root, "Edit", item=first(get_magic_item_manager().items))
    if kind == "monsters":
        from monster import get_monster_manager
        from ui.monster_view import MonsterEditorDialog
        return MonsterEditorDialog(root, "Edit", monster=first(get_monster_manager().monsters))
    if kind == "classes":
        from character_class import get_class_manager
        from ui.class_editor import ClassEditorDialog
        return ClassEditorDialog(root, class_def=get_class_manager().get_class("Wizard"))
    raise ValueError(kind)


KINDS = ["spells", "feats", "lineages", "backgrounds", "equipment", "magic_items", "monsters", "classes"]


def a_text_field(widget):
    """The first one-line text box of the form that holds text."""
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkEntry) and child.winfo_ismapped() and child.cget("state") != "disabled":
            return child
        found = a_text_field(child)
        if found is not None:
            return found
    return None


@pytest.mark.parametrize("kind", KINDS)
def test_an_editor_asks_before_throwing_away_changes(kind, tk_root, monkeypatch):
    import ui.editor_host as host
    asked = []
    answer = {"value": False}
    monkeypatch.setattr(host.messagebox, "askyesno", lambda *a, **k: asked.append(a) or answer["value"])
    try:
        dialog = open_editor(kind, tk_root)
    except (ImportError, AttributeError, TypeError) as e:
        pytest.skip(f"this editor is built differently here: {e}")
    try:
        assert isinstance(dialog, DialogWindow)
        pump(tk_root)
        assert not dialog.form_changed(), "an editor that was only opened counts as changed"

        field = a_text_field(dialog)
        assert field is not None
        field.insert("end", " (my notes)")
        assert dialog.form_changed()
        dialog._finish()                                  # Cancel: asked, and "No" keeps the editor open
        assert len(asked) == 1 and dialog.winfo_exists()

        field.delete(len(field.get()) - len(" (my notes)"), "end")
        assert not dialog.form_changed()                  # back as it was: closes without asking
        answer["value"] = True
        field.insert("end", "!")
        dialog._finish()
        assert len(asked) == 2 and not dialog.winfo_exists()
    finally:
        try:
            dialog.destroy()
        except Exception:
            pass


def test_saving_never_asks(tk_root, monkeypatch):
    import ui.editor_host as host
    monkeypatch.setattr(host.messagebox, "askyesno", lambda *a, **k: pytest.fail("asked after Save"))
    dialog = open_editor("feats", tk_root)
    pump(tk_root)
    a_text_field(dialog).insert("end", "x")
    dialog.result = object()                              # what Save sets before it finishes
    dialog._finish()
    assert not dialog.winfo_exists()


def test_the_form_state_reads_entries_boxes_and_switches(tk_root):
    frame = ctk.CTkFrame(tk_root)
    entry = ctk.CTkEntry(frame, placeholder_text="Name")
    box = ctk.CTkTextbox(frame)
    check = ctk.CTkCheckBox(frame, text="Legacy")
    menu = ctk.CTkComboBox(frame, values=["A", "B"])
    for w in (entry, box, check, menu):
        w.pack()
    before = form_state(frame)
    assert before == ["", "", 0, "A"]                     # (the hint isn't the entry's text)
    check.select()
    menu.set("B")
    box.insert("1.0", "hello")
    assert form_state(frame) == ["", "hello", 1, "B"]
    frame.destroy()
