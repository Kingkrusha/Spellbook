"""The Add Spells dialog, the granted spells dialog and the character spell panel's attack / save DC boxes."""

import time

import pytest

from character import CharacterSpellList, ClassLevel, update_subclass_spells
from spell_manager import SpellManager


def make(classes, **kw):
    return CharacterSpellList(name="Tester", classes=[ClassLevel.from_dict(
        {"class": c[0], "level": c[1], "subclass": c[2] if len(c) > 2 else ""}) for c in classes], **kw)


@pytest.fixture(scope="module")
def spells():
    manager = SpellManager()
    manager.load_spells()
    return manager


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def names(dialog):
    return [s.name for s in dialog.matching()]


@pytest.fixture
def dialogs(tk_root):
    made = []
    yield made
    for d in made:
        try:
            d.destroy()
        except Exception:
            pass


def open_dialog(tk_root, dialogs, character, spells, **kw):
    from ui.add_spells_dialog import AddSpellsDialog
    d = AddSpellsDialog(tk_root, character, spells, **kw)
    dialogs.append(d)
    pump(tk_root, 0.1)
    return d


def test_the_dialog_lists_only_what_the_character_can_learn_until_the_switch_is_turned_off(tk_root, dialogs, spells):
    d = open_dialog(tk_root, dialogs, make([("Wizard", 5)]), spells)
    d.only_var.set(True)
    d._refresh()
    learnable = names(d)
    assert "Fireball" in learnable and "Shield" in learnable
    assert "Wish" not in learnable and "Cure Wounds" not in learnable
    assert all(s.level <= 3 for s in d.matching())
    d.only_var.set(False)
    d._refresh()
    everything = names(d)
    assert "Wish" in everything and "Cure Wounds" in everything and len(everything) > len(learnable)


def test_searching_narrows_by_name_and_level(tk_root, dialogs, spells):
    d = open_dialog(tk_root, dialogs, make([("Wizard", 5)]), spells)
    d.query.set("magic mis")
    d._refresh()
    found = names(d)
    assert "Magic Missile" in found and all("magic" in n.lower() and "mis" in n.lower() for n in found)
    d.query.set("")
    d.level_menu.set("Cantrips")
    d._refresh()
    found = d.matching()
    assert found and all(s.level == 0 for s in found)
    assert "Fire Bolt" in [s.name for s in found]


def test_known_spells_are_left_out_and_adding_updates_the_list(tk_root, dialogs, spells):
    c = make([("Wizard", 5)])
    c.add_spell("Shield")
    added = []
    d = open_dialog(tk_root, dialogs, c, spells, add_fn=lambda s: added.append(s.name) or c.add_spell(s.name))
    assert "Shield" not in names(d)
    target = next(s for s in d.matching() if s.name == "Magic Missile")
    d._add(target, None)
    assert added == ["Magic Missile"] and d.added == ["Magic Missile"]
    assert "Magic Missile" not in names(d)


def test_a_warlocks_list_includes_their_patrons_spells(tk_root, dialogs, spells):
    d = open_dialog(tk_root, dialogs, make([("Warlock", 5, "Fiend Patron")]), spells)
    assert "Burning Hands" in names(d) and "Hex" in names(d)
    plain = open_dialog(tk_root, dialogs, make([("Warlock", 5)]), spells)
    assert "Burning Hands" not in names(plain) and "Hex" in names(plain)


def test_a_pick_dialog_offers_only_what_the_pick_allows_and_returns_the_choice(tk_root, dialogs, spells):
    import spell_grants as grants
    c = make([("Fighter", 1)], feats=["Magic Initiate (Cleric)"])
    pick = grants.build_report(c).picks[0]                    # two Cleric cantrips
    d = open_dialog(tk_root, dialogs, c, spells, pick=pick)
    found = names(d)
    assert "Guidance" in found and "Fire Bolt" not in found and "Cure Wounds" not in found
    for spell in [s for s in d.matching() if s.name in ("Guidance", "Light", "Resistance")]:
        d._toggle_choice(spell)
    assert len(d._chosen) == 2                                # a third choice pushes the oldest out
    d._done()
    assert d.result == d._chosen and len(d.result) == 2


def test_the_granted_spells_dialog_makes_the_choices_that_decide_the_spells(tk_root, dialogs, spells):
    from ui.granted_spells_dialog import GrantedSpellsDialog
    c = make([("Wizard", 3)], lineage="Elf")
    changed = []
    d = GrantedSpellsDialog(tk_root, c, spells, on_change=lambda: changed.append(1))
    dialogs.append(d)
    pump(tk_root, 0.1)
    assert not c.subclass_spells
    d._set_option("lineage:Elf", "Drow")
    assert {"Dancing Lights", "Faerie Fire"} <= set(c.subclass_spells) and changed
    assert c.spell_sources["Faerie Fire"] == "Species: Elf"


def test_the_character_list_search_in_the_add_to_list_dialog(tk_root, dialogs):
    from ui.spell_detail import AddToListDialog
    chars = [make([("Wizard", 5)]), make([("Cleric", 3)]), make([("Fighter", 2)])]
    chars[0].name, chars[1].name, chars[2].name = "Elowen", "Brother Tuck", "Garrick"
    d = AddToListDialog(tk_root, "Fireball", chars)
    dialogs.append(d)
    pump(tk_root, 0.1)
    assert len(d._scroll.winfo_children()) == 3
    d._search_var.set("tuck")
    assert [c.name for c in d._matching()] == ["Brother Tuck"]
    d._search_var.set("wizard")                                 # the classes are searched too
    assert [c.name for c in d._matching()] == ["Elowen"]
    d._search_var.set("zzz")
    assert d._matching() == []
    d._search_var.set("gar")
    d._pick_only_match()
    assert d.result == "Garrick"


def labels(widget):
    out = []
    for child in widget.winfo_children():
        try:
            out.append(child.cget("text"))
        except Exception:
            pass
        out.extend(labels(child))
    return out


def test_the_spell_panel_shows_the_spell_attack_and_save_dc(tk_root, spells):
    import customtkinter as ctk
    from character_rolls import SpellStat
    from ui.spell_lists_view import CharacterSpellsPanel

    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    tk_root.geometry("1000x800")
    saved = []

    class Manager:
        def update_character(self, name, character):
            saved.append(name)

    panel = CharacterSpellsPanel(frame, spells, Manager(), on_remove_spell=lambda n: None,
                                 stats_provider=lambda ch: [SpellStat("Wizard", "INT", 7, 15, ["Wand of the War Mage: +1 attack, +0 DC"])])
    panel.pack(fill="both", expand=True)
    c = make([("Wizard", 5)], lineage="Faerie", feats=["Fey Touched"])
    c.add_spell("Fireball")
    panel.set_character(c)
    pump(tk_root, 0.2)
    texts = labels(panel.stats_frame)
    values = []

    def entries(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkEntry):
                values.append(child.get())
            entries(child)
    entries(panel.stats_frame)
    assert values == ["+7", "15"] and "Spell attack" in texts and "Spell save DC" in texts
    assert any("War Mage" in t for t in texts)
    assert "Wizard • INT" in texts
    assert panel.add_btn.winfo_manager() == "pack"
    # the species and feat spells were added when the list was opened, and are always prepared
    assert {"Druidcraft", "Faerie Fire", "Misty Step"} <= set(c.subclass_spells)
    assert saved
    assert c.get_prepared_count() == 0
    assert panel.grants_btn.winfo_manager() == "pack" and "to choose" in panel.grants_btn.cget("text")   # Fey Touched's pick
    panel.set_character(None)
    assert not panel.stats_frame.winfo_manager()
    frame.destroy()


def test_a_custom_species_can_name_the_spells_a_trait_gives(tk_root):
    from lineage import Lineage, LineageTrait, get_lineage_manager
    from ui.lineages_view import LineageEditorDialog
    lineage = Lineage(name="Starborn Spell Test", traits=[
        LineageTrait("Star Magic", "x", spells=[{"spell": "Light", "level": 1}, {"spell": "Misty Step", "level": 3}]),
        LineageTrait("Plain", "y")])
    editor = LineageEditorDialog(tk_root, get_lineage_manager(), lineage)
    boxes = [t._spells_text for _n, _d, t in editor._trait_entries]
    assert boxes[0].get("1.0", "end-1c") == "Light, 1\nMisty Step, 3" and boxes[1].get("1.0", "end-1c") == ""
    boxes[0].insert("end", "\nFireball, 5, Fire")
    editor._save()
    assert editor.result is not None
    assert editor.result.traits[0].spells == [{"spell": "Light", "level": 1}, {"spell": "Misty Step", "level": 3},
                                              {"spell": "Fireball", "level": 5, "option": "Fire"}]
    assert editor.result.traits[1].spells == []
    again = get_lineage_manager().get_lineage("Starborn Spell Test")
    assert again.traits[0].spells[2]["option"] == "Fire"          # it was stored with the species
    c = CharacterSpellList(name="T", lineage="Starborn Spell Test",
                           classes=[ClassLevel.from_dict({"class": "Wizard", "level": 3})])
    update_subclass_spells(c)
    assert {"Light", "Misty Step"} <= set(c.subclass_spells) and "Fireball" not in c.subclass_spells
    get_lineage_manager().remove_lineage("Starborn Spell Test")
    editor.destroy()
