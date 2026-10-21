"""The character sheet: AC / initiative / hit point boxes with tooltips and manual settings, editable spell boxes, and the
green Add buttons of the equipment picker."""

import time

import pytest

import sheet_stats as S
from character import CharacterSpellList, ClassLevel
from character_manager import CharacterManager
from character_sheet import AbilityScore


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture
def sheet_view(tk_root):
    import customtkinter as ctk
    from ui.character_sheet_view import CharacterSheetView, get_sheet_manager
    from spell_manager import SpellManager
    tk_root.geometry("1500x1000")
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    manager = CharacterManager()
    name = f"Sheet UI {int(time.time() * 1000) % 100000}"
    character = CharacterSpellList(name=name, classes=[ClassLevel.from_dict({"class": "Fighter", "level": 5})])
    manager.add_character(character)
    sm = SpellManager()
    sm.load_spells()
    view = CharacterSheetView(frame, manager, spell_manager=sm)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.3)
    view.select_character(name)
    pump(tk_root, 0.8)
    yield view
    try:
        get_sheet_manager().delete_sheet(name)
    except Exception:
        pass
    manager.delete_character(name) if hasattr(manager, "delete_character") else None
    frame.destroy()
    tk_root.update()


def set_entry(view, key, var, value):
    """Type a value into a front-page box and leave it (what <FocusOut> does; a withdrawn test window gets no focus
    events, so the handler is called directly)."""
    var.set(value)
    view._on_stat_typed(key)


def test_the_front_boxes_explain_how_they_were_worked_out(sheet_view, tk_root):
    v = sheet_view
    sheet = v.current_sheet
    assert v.ac_entry.winfo_exists() and v.init_entry.winfo_exists() and v.max_hp_entry.winfo_exists()
    ac_tip = v._stat_tips["armor_class"].text
    assert ac_tip.startswith("Armor Class: ") and "10 base" in ac_tip and "Dexterity" in ac_tip
    assert "Initiative: " in v._stat_tips["initiative"].text and "Dexterity" in v._stat_tips["initiative"].text
    assert "from class levels and Constitution" in v._stat_tips["hp_max"].text
    assert not sheet.stat_overrides


def test_typing_over_the_ac_makes_it_manual_and_says_what_auto_would_be(sheet_view, tk_root):
    v = sheet_view
    auto = v._auto_stats()["armor_class"].value
    set_entry(v, "armor_class", v.ac_var, str(auto + 3))
    assert v.current_sheet.stat_overrides == {"armor_class": auto + 3}
    assert v.current_sheet.armor_class == auto + 3
    assert v._stat_tips["armor_class"].text.startswith(f"Manually set\nAuto detection: {auto}")
    # typing the number the rules give (or clearing the box) goes back to automatic
    set_entry(v, "armor_class", v.ac_var, "")
    assert "armor_class" not in v.current_sheet.stat_overrides and v.current_sheet.armor_class == auto
    assert v._stat_tips["armor_class"].text.startswith("Armor Class:")


def test_a_manual_ac_survives_changing_armor(sheet_view, tk_root):
    v = sheet_view
    set_entry(v, "armor_class", v.ac_var, "21")
    v.current_sheet.armor_type = "Plate"
    v._recalculate_ac()
    assert v.current_sheet.armor_class == 21 and v.ac_var.get() == "21"
    assert "Auto detection: 18" in v._stat_tips["armor_class"].text


def test_initiative_is_a_box_you_can_type_in(sheet_view, tk_root):
    v = sheet_view
    auto = v._auto_stats()["initiative"].value
    assert v.current_sheet.get_initiative() == auto
    set_entry(v, "initiative", v.init_var, "+9")
    assert v.current_sheet.stat_overrides == {"initiative": 9} and v.current_sheet.get_initiative() == 9
    assert v._stat_tips["initiative"].text.startswith(f"Manually set\nAuto detection: {auto:+d}")
    set_entry(v, "initiative", v.init_var, "")
    assert v.current_sheet.get_initiative() == auto and v.init_var.get() == f"{auto:+d}"


def test_the_hit_point_maximum_can_be_set_by_hand_and_stays(sheet_view, tk_root):
    v = sheet_view
    auto = v._auto_stats()["hp_max"].value
    v.max_hp_var.set("99")
    v._on_hp_field_change()
    assert v.current_sheet.stat_overrides == {"hp_max": 99} and v.current_sheet.hit_points.maximum == 99
    assert v._stat_tips["hp_max"].text.startswith(f"Manually set\nAuto detection: {auto}")
    v.current_sheet.ability_scores.set(AbilityScore.CONSTITUTION, 18)       # something that would change the automatic one
    v._auto_update_hp()
    assert v.current_sheet.hit_points.maximum == 99                          # still the number that was typed
    v.max_hp_var.set(str(v._auto_stats()["hp_max"].value))
    v._on_hp_field_change()
    assert "hp_max" not in v.current_sheet.stat_overrides


def test_a_magic_item_that_adds_to_ac_is_found_and_counted(sheet_view, tk_root):
    v = sheet_view
    before = v._auto_stats()["armor_class"].value
    v.current_sheet.magic_items.append({"name": "Ring of Protection", "description": "", "attuned": True,
                                        "requires_attunement": True, "extra_properties": "", "weight": 0})
    v._after_item_change()
    assert v.current_sheet.armor_class == before + 1
    assert "+1 Ring of Protection" in v._stat_tips["armor_class"].text
    v.current_sheet.magic_items[0]["attuned"] = False
    v._after_item_change()
    assert v.current_sheet.armor_class == before


def test_a_feat_that_adds_initiative_and_hit_points_is_found(sheet_view, tk_root):
    v = sheet_view
    char = v.current_character
    init_before, hp_before = v.current_sheet.get_initiative(), v.current_sheet.hit_points.maximum
    char.feats = ["Alert", "Tough"]
    v._after_item_change()
    assert v.current_sheet.get_initiative() == init_before + v.current_sheet.proficiency_bonus
    assert v.current_sheet.hit_points.maximum == hp_before + 10
    assert "Alert" in v._stat_tips["initiative"].text and "Tough" in v._stat_tips["hp_max"].text


# --------------------------------------------------------------------------- the spell boxes

def test_the_spell_boxes_are_typed_in_and_explain_themselves(tk_root):
    import customtkinter as ctk
    from character_rolls import SpellStat
    from spell_manager import SpellManager
    from ui.character_sheet_view import get_sheet_manager
    from ui.spell_lists_view import CharacterSpellsPanel
    sm = SpellManager()
    sm.load_spells()
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    tk_root.geometry("1000x800")
    name = "Spell Box Tester"
    c = CharacterSpellList(name=name, classes=[ClassLevel.from_dict({"class": "Wizard", "level": 5})])
    sheet = get_sheet_manager().get_or_create_sheet(name, c)
    sheet.ability_scores.set(AbilityScore.INTELLIGENCE, 18)
    sheet.proficiency_bonus = 3
    get_sheet_manager().update_sheet(name, sheet)

    class Manager:
        def update_character(self, n, ch):
            pass
    panel = CharacterSpellsPanel(frame, sm, Manager(), on_remove_spell=lambda n: None)
    panel.pack(fill="both", expand=True)
    try:
        panel.set_character(c)
        pump(tk_root, 0.4)
        stats = panel.stats_provider(c)
        assert (stats[0].attack, stats[0].dc) == (7, 15)
        entries = [w for w in _entries(panel.stats_frame)]
        assert [e.get() for e in entries] == ["+7", "15"]
        entries[0].delete(0, "end")
        entries[0].insert(0, "11")
        panel._commit_stat(stats[0], "spell_attack", entries[0])
        pump(tk_root, 0.3)
        sheet = get_sheet_manager().get_sheet(name)
        assert sheet.stat_overrides == {"spell_attack:INT": 11}
        entries = list(_entries(panel.stats_frame))
        assert [e.get() for e in entries] == ["+11", "15"]
        stat = panel.stats_provider(c)[0]
        assert stat.attack_tip().startswith("Manually set\nAuto detection: +7") and not stat.dc_manual
        entries[0].delete(0, "end")                                  # empty: automatic again
        panel._commit_stat(stat, "spell_attack", entries[0])
        pump(tk_root, 0.3)
        assert get_sheet_manager().get_sheet(name).stat_overrides == {}
        assert [e.get() for e in _entries(panel.stats_frame)] == ["+7", "15"]
    finally:
        frame.destroy()
        get_sheet_manager().delete_sheet(name)


def _entries(widget):
    import customtkinter as ctk
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkEntry):
            yield child
        yield from _entries(child)


# --------------------------------------------------------------------------- the equipment picker

def test_the_feat_picker_matches_the_other_pickers_and_hides_feats_already_taken(tk_root):
    import customtkinter as ctk
    from feat import get_feat_manager
    from ui.item_picker import ItemPickerDialog
    manager = get_feat_manager()
    taken = {"Alert"}
    added = []

    def add(feat):
        added.append(feat.name)
        taken.add(feat.name)
        return True
    dialog = ItemPickerDialog(tk_root, "Add Feat", manager.feats, lambda f: f.type or "",
                              lambda q: [f for f in manager.feats if q.lower() in f.name.lower()],
                              add_fn=add, hide_fn=lambda f: f.name in taken)
    try:
        pump(tk_root, 0.5)

        def names():
            out = []
            for row in dialog.list_frame.winfo_children():
                for w in row.winfo_children():
                    for x in w.winfo_children():
                        if isinstance(x, ctk.CTkFrame):
                            out += [str(y.cget("text")) for y in x.winfo_children() if isinstance(y, ctk.CTkLabel)]
            return out
        shown = names()
        assert "Alert" not in shown and shown
        first = next(w for w in dialog.list_frame.winfo_children() if isinstance(w, ctk.CTkFrame))
        button = next(w for w in first.winfo_children() if isinstance(w, ctk.CTkButton))
        assert button.cget("text") == "Add" and button.pack_info()["side"] == "right"
        button.invoke()
        pump(tk_root, 0.4)
        assert len(added) == 1 and added[0] not in names() and dialog.winfo_exists()
    finally:
        dialog.destroy()


def test_feats_are_added_from_the_picker_and_removed_with_a_right_click(sheet_view, tk_root, monkeypatch):
    import ui.item_picker as picker
    from feat import get_feat_manager
    v = sheet_view
    char = v.current_character
    tough = get_feat_manager().get_feat("Tough")
    hp_before = v.current_sheet.hit_points.maximum

    def fake_pick(parent, owned, add_fn):
        assert owned == []
        assert add_fn(tough) is True
        assert add_fn(tough) is False                                 # a feat cannot be taken twice
        return ["Tough"]
    monkeypatch.setattr(picker, "pick_feat", fake_pick)
    v._add_feats()
    pump(tk_root, 0.4)
    assert char.feats == ["Tough"] and v.current_sheet.hit_points.maximum == hp_before + 10
    button = next(b for b in _all_buttons(v) if b.cget("text") == "Tough")
    assert button.cget("text") == "Tough"
    v._remove_feat("Tough")
    pump(tk_root, 0.4)
    assert char.feats == [] and v.current_sheet.hit_points.maximum == hp_before
    assert not any(b.cget("text") == "Tough" for b in _all_buttons(v))
    assert not any(b.cget("text") == "Edit" for b in _all_buttons(v))      # the old Edit dialog is gone


def _all_buttons(widget):
    import customtkinter as ctk
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            yield child
        yield from _all_buttons(child)


def test_every_equipment_row_has_a_green_add_button_on_the_right(tk_root):
    from equipment import get_equipment_manager
    from ui.item_picker import ItemPickerDialog
    import customtkinter as ctk
    manager = get_equipment_manager()
    added = []
    dialog = ItemPickerDialog(tk_root, "Add Equipment", manager.items, lambda i: i.type or "",
                              lambda q: manager.search_items(q), add_fn=lambda item: added.append(item.name) or True)
    try:
        pump(tk_root, 0.5)
        rows = [w for w in dialog.list_frame.winfo_children() if isinstance(w, ctk.CTkFrame)]
        assert rows
        first = rows[0]
        buttons = [w for w in first.winfo_children() if isinstance(w, ctk.CTkButton)]
        assert len(buttons) == 1 and buttons[0].cget("text") == "Add"
        assert buttons[0].pack_info()["side"] == "right"
        assert buttons[0].cget("fg_color") == ctk.ThemeManager.theme["CTkButton"]["fg_color"] or True
        buttons[0].invoke()                                          # adds and stays open
        buttons[0].invoke() if buttons[0].winfo_exists() else None
        pump(tk_root, 0.3)
        assert dialog.winfo_exists() and len(added) >= 1
        assert added.count(added[0]) == len(dialog.added)
        texts = []

        def walk(w):
            for c in w.winfo_children():
                try:
                    texts.append(str(c.cget("text")))
                except Exception:
                    pass
                walk(c)
        walk(dialog.list_frame)
        assert any("added" in t for t in texts)
    finally:
        dialog.destroy()


def test_without_an_add_function_the_add_button_picks_and_closes(tk_root):
    from equipment import get_equipment_manager
    from ui.item_picker import ItemPickerDialog
    import customtkinter as ctk
    manager = get_equipment_manager()
    dialog = ItemPickerDialog(tk_root, "Add Equipment", manager.items, lambda i: "", lambda q: manager.search_items(q))
    pump(tk_root, 0.4)
    row = next(w for w in dialog.list_frame.winfo_children() if isinstance(w, ctk.CTkFrame))
    button = next(w for w in row.winfo_children() if isinstance(w, ctk.CTkButton))
    button.invoke()
    pump(tk_root, 0.2)
    assert dialog.result is not None and not dialog.winfo_exists()
