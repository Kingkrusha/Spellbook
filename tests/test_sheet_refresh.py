"""Character sheet updates: a change to a class, level, subclass or feat updates only the parts of the sheet that
follow from it (the rest of the sheet keeps its widgets), each change writes the data files once, and leaving a
box without changing it does no work."""

import time

import pytest

import atomic_io
from atomic_io import HeldSaves
from character import CharacterSpellList, ClassLevel
from character_manager import CharacterManager
from character_sheet import AbilityScore


def pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def make_view(tk_root, classes):
    import customtkinter as ctk
    from ui.character_sheet_view import CharacterSheetView
    from spell_manager import SpellManager
    tk_root.geometry("1500x1000")
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    manager = CharacterManager()
    name = f"Refresh {int(time.time() * 1000) % 100000}"
    character = CharacterSpellList(name=name, classes=[ClassLevel.from_dict(c) for c in classes])
    manager.add_character(character)
    sm = SpellManager()
    sm.load_spells()
    view = CharacterSheetView(frame, manager, spell_manager=sm)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.2)
    view.select_character(name)
    pump(tk_root, 0.4)
    return frame, manager, view


@pytest.fixture
def sheet(tk_root):
    made = []

    def build(*classes):
        frame, manager, view = make_view(tk_root, classes or [{"class": "Fighter", "level": 5}])
        made.append((frame, manager, view))
        return view

    yield build
    from ui.character_sheet_view import get_sheet_manager
    for frame, manager, view in made:
        name = view.current_character.name
        try:
            get_sheet_manager().delete_sheet(name)
        except Exception:
            pass
        manager.delete_character(name)
        frame.destroy()
    tk_root.update()


@pytest.fixture
def writes(monkeypatch):
    """Counts the data files written, by file name."""
    counts = {}
    original = atomic_io.atomic_write_text

    def counting(path, *args, **kwargs):
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        counts[name] = counts.get(name, 0) + 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(atomic_io, "atomic_write_text", counting)
    return counts


def set_level(view, index, level):
    view.class_level_widgets[index][1].set(str(level))
    view._on_class_level_change(index, str(level))


def kept(widget):
    """The widget was not destroyed and rebuilt."""
    return widget.winfo_exists()


def test_a_level_change_updates_what_follows_from_it_and_keeps_the_rest(sheet, tk_root):
    v = sheet({"class": "Fighter", "level": 5})
    untouched = (v.ac_entry, v.proficiencies_text, v.death_widget, v.ability_widgets[AbilityScore.STRENGTH],
                 v.save_widgets[AbilityScore.STRENGTH], v.lineage_combo)
    class_features_before = v._class_features_host.winfo_children()
    assert v.prof_label.cget("text") == "+3"

    set_level(v, 0, 9)

    assert v.current_character.classes[0].level == 9
    assert v.prof_label.cget("text") == "+4" and v.current_sheet.proficiency_bonus == 4
    assert all(kept(w) for w in untouched)
    assert not any(w.winfo_exists() for w in class_features_before)        # class features were rebuilt
    assert v._hit_dice_vars["d10"][1] == 9                                   # hit dice follow the level
    # the save and skill numbers use the new proficiency bonus
    assert v.save_widgets[AbilityScore.STRENGTH].mod_label.cget("text") == \
        f"{v.current_sheet.get_saving_throw_bonus(AbilityScore.STRENGTH):+d}"
    assert v.current_sheet.hit_points.maximum == v._auto_stats()["hp_max"].value


def test_a_level_change_writes_each_file_once(sheet, writes):
    v = sheet({"class": "Fighter", "level": 5})
    writes.clear()
    set_level(v, 0, 6)
    assert writes == {"characters.json": 1, "character_sheets.json": 1}


def test_leaving_a_level_box_unchanged_does_nothing(sheet, writes):
    v = sheet({"class": "Fighter", "level": 5})
    features = v._class_features_host.winfo_children()
    writes.clear()
    v._on_class_level_change(0, "5")
    assert writes == {}
    assert all(w.winfo_exists() for w in features)
    # a level above 20 is capped; when that is the level it already had, the box shows it and nothing else happens
    set_level(v, 0, 20)
    writes.clear()
    set_level(v, 0, 25)
    assert writes == {} and v.class_level_widgets[0][1].get() == "20"


def test_reaching_the_subclass_level_adds_the_subclass_box(sheet):
    v = sheet({"class": "Fighter", "level": 2})
    assert v.subclass_widgets == []
    level_box_var = v.class_level_widgets[0][1]
    set_level(v, 0, 3)
    assert len(v.subclass_widgets) == 1
    # going 3 -> 4 keeps the class row as it is
    level_box_var = v.class_level_widgets[0][1]
    combo = v.subclass_widgets[0][2]
    set_level(v, 0, 4)
    assert combo.winfo_exists() and v.class_level_widgets[0][1] is level_box_var


def test_picking_a_subclass_shows_its_features_without_rebuilding_the_sheet(sheet):
    v = sheet({"class": "Fighter", "level": 3})
    ac_entry = v.ac_entry
    _, _, combo = v.subclass_widgets[0]
    subclass = next(name for name in combo.cget("values") if name != "(None)")
    v._on_subclass_change(0, subclass)
    assert v.current_character.classes[0].subclass == subclass
    assert kept(ac_entry)
    _, subclass_features = v._get_organized_features()
    assert subclass_features                                   # the features section lists the subclass's features
    # picking the same one again does nothing
    features = v._features_frame.winfo_children()
    v._on_subclass_change(0, subclass)
    assert all(w.winfo_exists() for w in features)


def test_slippery_mind_ticks_the_wisdom_and_charisma_saves(sheet):
    v = sheet({"class": "Rogue", "level": 14})
    for ability in (AbilityScore.WISDOM, AbilityScore.CHARISMA):
        v.current_sheet.saving_throws.set_proficiency(ability, False)
    v._sync_proficiency_widgets()
    set_level(v, 0, 15)                                          # used to raise AttributeError (set_proficiency)
    for ability in (AbilityScore.WISDOM, AbilityScore.CHARISMA):
        assert v.current_sheet.saving_throws.is_proficient(ability)
        assert v.save_widgets[ability].prof_var.get() is True
    set_level(v, 0, 14)
    for ability in (AbilityScore.WISDOM, AbilityScore.CHARISMA):
        assert v.save_widgets[ability].prof_var.get() is False


def test_adding_and_removing_a_class(sheet, monkeypatch):
    v = sheet({"class": "Fighter", "level": 5})
    ac_entry = v.ac_entry

    class Picked:
        result = "Wizard"

    monkeypatch.setattr("ui.character_sheet_view.AddClassDialog", lambda *a, **k: Picked())
    monkeypatch.setattr(v, "wait_window", lambda *a: None)
    v._show_add_class_dialog()
    assert [cl.get_class_name() for cl in v.current_character.classes] == ["Fighter", "Wizard"]
    assert len(v.class_level_widgets) == 2 and kept(ac_entry)
    assert v.current_sheet.proficiency_bonus == 3                          # level 6 in all
    assert set(v._hit_dice_vars) == {"d10", "d6"}

    monkeypatch.setattr("ui.character_sheet_view.messagebox.showinfo", lambda *a, **k: None)
    monkeypatch.setattr("ui.character_sheet_view.messagebox.askyesno", lambda *a, **k: True)
    v._on_class_level_change(1, "0")
    assert [cl.get_class_name() for cl in v.current_character.classes] == ["Fighter"]
    assert len(v.class_level_widgets) == 1 and kept(ac_entry)
    assert set(v._hit_dice_vars) == {"d10"}


def test_a_feat_change_updates_the_feat_list_only(sheet):
    v = sheet({"class": "Fighter", "level": 5})
    ac_entry, saves = v.ac_entry, v.save_widgets[AbilityScore.DEXTERITY]
    v.current_character.feats = ["Alert"]
    v._feats_changed()
    assert kept(ac_entry) and kept(saves)
    assert v.init_var.get() == f"{v.current_sheet.get_initiative():+d}"


def test_leaving_an_ability_box_unchanged_does_nothing(sheet, writes):
    v = sheet({"class": "Fighter", "level": 5})
    widget = v.ability_widgets[AbilityScore.CONSTITUTION]
    writes.clear()
    widget._on_score_change()
    assert writes == {}
    widget.score_var.set("16")
    widget._on_score_change()
    assert v.current_sheet.ability_scores.get(AbilityScore.CONSTITUTION) == 16
    assert writes.get("character_sheets.json") == 1


def test_an_equipment_quantity_updates_its_row_without_rebuilding_the_tab(sheet, tk_root):
    v = sheet({"class": "Fighter", "level": 5})
    v.current_sheet.equipment_items = [{"name": "Rope", "quantity": 1, "weight": 10}]
    v._show_sheet_tab("inventory")
    pump(tk_root, 0.1)
    qty_var, label = v._equipment_rows[0]
    qty_var.set("3")
    v._save_equipment_item_quantity(0, "3")
    assert v.current_sheet.equipment_items[0]["quantity"] == 3
    assert kept(label) and label.cget("text") == "10 lb each (30 lb total)"
    qty_var.set("nonsense")
    v._save_equipment_item_quantity(0, "nonsense")
    assert v.current_sheet.equipment_items[0]["quantity"] == 1 and qty_var.get() == "1"
    v._show_sheet_tab("front")


# --------------------------------------------------------------------------- pieces


class Store(HeldSaves):
    _HELD_SAVE = "write"

    def __init__(self):
        self.written = 0

    def write(self):
        if self._hold_save():
            return True
        self.written += 1
        return True


def test_held_saves_write_once_when_the_outer_hold_ends():
    store = Store()
    store.write()
    assert store.written == 1
    with store.saves_held():
        store.write()
        with store.saves_held():
            store.write()
            store.write()
        assert store.written == 1                                   # still held by the outer one
    assert store.written == 2
    with store.saves_held():
        pass
    assert store.written == 2                                       # nothing changed: nothing written


def test_held_saves_still_write_when_the_change_fails():
    store = Store()
    with pytest.raises(RuntimeError):
        with store.saves_held():
            store.write()
            raise RuntimeError("boom")
    assert store.written == 1


def test_a_new_scrollbar_never_flushes_the_whole_window(tk_root, monkeypatch):
    import customtkinter as ctk
    from ui import ctk_patches
    ctk_patches.install()
    flushed = []
    monkeypatch.setattr(ctk.CTkCanvas, "update_idletasks", lambda self: flushed.append(self), raising=False)
    box = ctk.CTkTextbox(tk_root, height=40)              # a text box makes two scrollbars, which draw at once
    try:
        assert flushed == []
    finally:
        box.destroy()
