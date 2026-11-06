"""The guided character builder: its rules (character_builder.py) and the page on the Characters page
(ui/character_builder_view.py), walked through from the first step to a saved character."""

import os

import pytest

import character_builder as cb


@pytest.fixture(scope="module")
def src():
    return cb.Sources.default()


# ---------------------------------------------------------------------------------------------- the rules

def test_steps_skip_what_does_not_apply(src):
    level1_fighter = cb.Draft(name="A", level=1, class_name="Fighter")
    steps = cb.steps_for(level1_fighter, src)
    assert "subclass" not in steps and "feats" not in steps and "spells" not in steps
    assert steps[0] == "start" and steps[-1] == "review"

    wizard5 = cb.Draft(name="B", level=5, class_name="Wizard")
    steps = cb.steps_for(wizard5, src)
    assert {"subclass", "feats", "spells"} <= set(steps)
    assert cb.spell_counts(wizard5, src) == (4, 9)


def test_eldritch_knight_gets_spells_from_its_subclass(src):
    draft = cb.Draft(name="C", level=3, class_name="Fighter", subclass="Eldritch Knight")
    cantrips, prepared = cb.spell_counts(draft, src)
    assert cantrips >= 2 and prepared >= 3
    assert "spells" in cb.steps_for(draft, src)


def test_feat_slots_follow_the_class_table(src):
    assert cb.feat_slot_levels(src.class_def("Fighter"), 20) == [4, 6, 8, 12, 14, 16, 19]
    draft = cb.Draft(level=8, class_name="Wizard")
    cb.sync_feat_slots(draft, src)
    assert [s.level for s in draft.feat_slots] == [4, 8]
    draft.feat_slots[0].feat = "Alert"
    draft.level = 4
    cb.sync_feat_slots(draft, src)
    assert [(s.level, s.feat) for s in draft.feat_slots] == [(4, "Alert")]   # choices are kept


def test_scores_add_the_background_and_improvements(src):
    draft = cb.Draft(background="Sage", bonus_plus2="intelligence", bonus_plus1="constitution")
    draft.base_scores = dict(zip(cb.ABILITIES, [8, 14, 13, 15, 12, 10]))
    draft.feat_slots = [cb.FeatSlot(4, plus=["intelligence", "intelligence"])]
    scores = cb.final_scores(draft, src)
    assert scores["intelligence"] == 19 and scores["constitution"] == 14 and scores["strength"] == 8
    draft.bonus_mode = "1/1/1"
    assert cb.background_bonuses(draft, src) == {"strength": 0, "dexterity": 0, "constitution": 1,
                                                 "intelligence": 1, "wisdom": 1, "charisma": 0}
    # nothing goes above 20
    draft.base_scores["intelligence"] = 20
    assert cb.final_scores(draft, src)["intelligence"] == 20


def test_point_buy_and_standard_array_helpers():
    assert cb.points_spent({a: 8 for a in cb.ABILITIES}) == 0
    assert cb.points_spent(dict(zip(cb.ABILITIES, [15, 15, 15, 8, 8, 8]))) == 27
    assert cb.standard_array_left({"strength": 15, "dexterity": 8}) == [14, 13, 12, 10]
    draft = cb.Draft()
    draft.set_score_method("point_buy")
    assert set(draft.base_scores.values()) == {8}


def test_each_step_says_what_is_missing(src):
    draft = cb.Draft()
    assert cb.problems(draft, "start", src)
    draft.name = "Taken"
    assert cb.problems(draft, "start", src, existing_names=["Taken"])
    draft.name = "Free"
    assert cb.problems(draft, "start", src) == []
    assert cb.problems(draft, "class", src)
    draft.class_name = "Rogue"
    assert cb.problems(draft, "skills", src) == ["Choose 4 more skills."]
    draft.background = "Sage"
    assert cb.problems(draft, "background", src)            # +2 / +1 not chosen yet
    draft.bonus_plus2 = draft.bonus_plus1 = "wisdom"
    assert "different" in cb.problems(draft, "background", src)[0]


def test_skills_from_the_background_are_not_picked_twice(src):
    draft = cb.Draft(class_name="Wizard", background="Sage", class_skills=["Arcana", "Insight", "Medicine"])
    cb.tidy_skills(draft, src)
    assert draft.class_skills == ["Insight", "Medicine"]      # Arcana comes from Sage


def test_starting_equipment_is_read_from_the_text():
    options = cb.equipment_options("Choose A or B: (A) [[equipment:Robe]], 2 Daggers, Book (prayers), and 5 GP; "
                                   "or (B) 55 GP")
    assert options == [("A", ["Robe", "2 Daggers", "Book (prayers)", "5 GP"]), ("B", ["55 GP"])]
    assert cb.equipment_options("A holy symbol, a pouch containing 15gp") == [
        ("A", ["A holy symbol", "a pouch containing 15gp"])]


def test_items_are_matched_to_the_equipment_collection(src):
    find = lambda n: cb._find_equipment(src, n)
    dagger = cb.read_item("2 Daggers", find)
    assert (dagger.name, dagger.quantity) == ("Dagger", 2)
    arrows = cb.read_item("20 Arrows", find)
    assert (arrows.name, arrows.quantity, arrows.note) == ("Arrows", 1, "Arrows: 20")   # one bundle of 20
    focus = cb.read_item("Arcane Focus (Quarterstaff)", find)
    assert focus.name == "Arcane Focus" and focus.note == "Arcane Focus: Quarterstaff"
    assert cb.read_item("8 GP", find).coins == ("gp", 8)
    assert cb.read_item("a pouch containing 15gp", find).coins == ("gp", 15)
    assert cb.read_item("Musical Instrument of your choice of a dragon", find).name == ""


def test_classes_without_lettered_options_still_have_equipment(src):
    for name in ("Rogue", "Wizard"):
        options = cb.class_equipment_options(src.class_def(name))
        assert [letter for letter, _items in options] == ["A", "B"], name


def test_create_character_fills_in_the_sheet(src, tmp_path):
    from character_manager import CharacterManager
    from ui.character_sheet_view import CharacterSheetManager
    characters = CharacterManager(str(tmp_path / "characters.json"))
    sheets = CharacterSheetManager(str(tmp_path / "sheets.json"))

    draft = cb.Draft(name="Brakka", level=1, class_name="Fighter", lineage="Dwarf", background="Soldier",
                     bonus_plus2="strength", bonus_plus1="constitution", class_equipment="A",
                     background_equipment="A", class_skills=["Perception", "Survival"])
    draft.base_scores = dict(zip(cb.ABILITIES, [15, 13, 14, 8, 12, 10]))
    for step in cb.steps_for(draft, src):
        assert cb.problems(draft, step, src) == [], step
    character = cb.create_character(draft, src, characters, sheets)

    assert characters.get_character("Brakka") is character
    assert character.lineage == "Dwarf" and character.classes[0].level == 1
    sheet = sheets.get_sheet("Brakka")
    assert sheet.background == "Soldier"
    assert sheet.ability_scores.strength == 17 and sheet.ability_scores.constitution == 15
    assert sheet.saving_throws.strength and sheet.saving_throws.constitution
    from character_sheet import Skill
    assert sheet.skills.get(Skill.PERCEPTION) == 1 and sheet.skills.get(Skill.ATHLETICS) == 1   # Soldier
    assert sheet.armor_type == "Chain Mail" and sheet.armor_class == 16
    names = {row["name"] for row in sheet.equipment_items}
    assert {"Chain Mail", "Greatsword", "Javelin"} <= names
    assert sheet.gold > 0
    assert sheet.hit_points.maximum == sheet.hit_points.current >= 12   # d10 + CON + Dwarven Toughness
    assert sheet.proficiency_bonus == 2
    assert os.path.exists(tmp_path / "characters.json") and os.path.exists(tmp_path / "sheets.json")


def test_spells_are_known_and_prepared(src, tmp_path):
    from character_manager import CharacterManager
    from ui.character_sheet_view import CharacterSheetManager
    from spell_manager import SpellManager
    spell_manager = SpellManager()
    spell_manager.load_spells()
    spells = spell_manager.spells
    draft = cb.Draft(name="Iri", level=1, class_name="Cleric", lineage="Human", background="Acolyte")
    cantrips, leveled = cb.learnable_spells(draft, spells)
    assert cantrips and all(s.level == 0 for s in cantrips)
    assert leveled and all(s.level == 1 for s in leveled)
    draft.cantrips = [s.name for s in cantrips[:3]]
    draft.spells = [s.name for s in leveled[:4]]
    character = cb.create_character(draft, src, CharacterManager(str(tmp_path / "c.json")),
                                    CharacterSheetManager(str(tmp_path / "s.json")))
    assert set(draft.cantrips + draft.spells) <= set(character.known_spells)
    assert set(draft.spells) == set(character.prepared_spells)


# ---------------------------------------------------------------------------------------------- the page

def test_the_builder_page_walks_through_to_a_new_character(tk_root):
    from character_manager import CharacterManager
    from spell_manager import SpellManager
    from ui.characters_view import CharactersView
    from ui.character_sheet_view import get_sheet_manager

    manager = CharacterManager()
    opened = []
    spell_manager = SpellManager()
    spell_manager.load_spells()
    view = CharactersView(tk_root, manager, spell_manager=spell_manager,
                          on_open=lambda name, new_tab=False: opened.append(name))
    view.pack(fill="both", expand=True)
    tk_root.update()
    builder = view.open_builder()
    tk_root.update()
    assert not view.outer.winfo_ismapped() or not view.outer.winfo_manager()

    builder.next()                                            # no name yet: stays put and says why
    assert builder.step == "start" and builder.problem_label.cget("text")

    d = builder.draft
    d.name, d.level = "Builder Test Wizard", 3
    expected = ["class", "subclass", "lineage", "background", "abilities", "skills", "spells", "equipment",
                "review"]
    d.class_name = "Wizard"
    builder.next()
    choices = {"subclass": lambda: setattr(d, "subclass", "Evoker"),
               "lineage": lambda: setattr(d, "lineage", "Gnome"),
               "background": lambda: (setattr(d, "background", "Sage"), setattr(d, "bonus_plus2", "intelligence"),
                                      setattr(d, "bonus_plus1", "constitution")),
               "abilities": builder._suggest_scores,
               "skills": lambda: setattr(d, "class_skills", ["Investigation", "Medicine"])}
    seen = []
    while builder.step != "review":
        seen.append(builder.step)
        tk_root.update()
        if builder.step == "spells":
            builder.spell_available.selection_set(0)
            builder.spell_add()
            assert len(d.cantrips) == 1
        choices.get(builder.step, lambda: None)()
        builder.next()
        assert builder.problem_label.cget("text") == "", builder.step
    seen.append("review")
    assert seen == expected
    assert "Evoker" in builder.summary() and "Sage" in builder.summary()

    builder.next()                                            # Create Character
    tk_root.update()
    assert view.builder is None and opened == ["Builder Test Wizard"]
    character = manager.get_character("Builder Test Wizard")
    assert character is not None and character.classes[0].subclass == "Evoker"
    assert get_sheet_manager().get_sheet("Builder Test Wizard").ability_scores.intelligence == 17
    manager.delete_character("Builder Test Wizard")
    get_sheet_manager().delete_sheet("Builder Test Wizard")
    view.destroy()


def test_going_back_to_level_1_drops_the_subclass(tk_root):
    from character_manager import CharacterManager
    from ui.character_builder_view import CharacterBuilderView
    builder = CharacterBuilderView(tk_root, CharacterManager())
    builder.draft.name, builder.draft.level, builder.draft.class_name = "X", 3, "Cleric"
    builder.draft.subclass = "Life Domain"
    builder.show_step("class")
    builder.draft.level = 1
    builder.show_step("lineage")
    assert builder.draft.subclass == "" and "subclass" not in builder.steps()
    builder.destroy()


def test_create_goes_back_to_a_step_that_came_undone(tk_root):
    from character_manager import CharacterManager
    from ui.character_builder_view import CharacterBuilderView
    manager = CharacterManager()
    builder = CharacterBuilderView(tk_root, manager)
    d = builder.draft
    d.name, d.class_name, d.lineage, d.background = "Undone", "Rogue", "Human", "Criminal"
    d.bonus_plus2, d.bonus_plus1 = "dexterity", "constitution"
    builder._suggest_scores()
    builder.show_step("review")
    builder.next()                                            # Create: the Rogue's skills were never chosen
    assert builder.step == "skills" and "skill" in builder.problem_label.cget("text")
    assert manager.get_character("Undone") is None
    builder.destroy()
