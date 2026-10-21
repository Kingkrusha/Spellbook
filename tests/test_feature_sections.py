"""Class and subclass editors: levels are sections that are already there, features are edited as cards in them."""

import time

import pytest


def pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture
def host(tk_root):
    import customtkinter as ctk
    tk_root.geometry("1100x900")
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    yield frame
    frame.destroy()
    tk_root.update()


def class_panel(host, root, class_def=None):
    from ui.class_editor import ClassEditorPanel
    panel = ClassEditorPanel(host, class_def=class_def)
    panel.pack(fill="both", expand=True)
    pump(root, 0.3)
    return panel


def open_features_tab(panel, root):
    panel.tabview.set("Level Features")
    panel._on_tab_change("Level Features")
    pump(root, 0.3)
    return panel.level_sections


# --------------------------------------------------------------------------- levels the class gives subclass features at

def test_defaults_follow_the_subclass_level():
    from ui.class_editor import default_subclass_levels
    assert default_subclass_levels(3) == [3, 6, 10, 14]
    assert default_subclass_levels(1) == [1, 6, 10, 14]
    assert default_subclass_levels(2) == [2, 6, 10, 14]
    assert default_subclass_levels(6) == [6, 10, 14]


def test_subclass_levels_are_read_from_the_class():
    from character_class import get_class_manager
    from ui.class_editor import subclass_feature_levels
    cm = get_class_manager()
    assert subclass_feature_levels(cm.get_class("Fighter")) == [3, 7, 10, 15, 18]
    assert subclass_feature_levels(cm.get_class("Cleric")) == [3, 6, 10, 14, 17]
    assert subclass_feature_levels(cm.get_class("Bard")) == [3, 6, 14]


def test_a_class_without_placeholders_falls_back_on_its_subclass_level():
    from character_class import CharacterClassDefinition
    from ui.class_editor import subclass_feature_levels
    assert subclass_feature_levels(CharacterClassDefinition(name="Plain", subclass_level=3)) == [3, 6, 10, 14]
    assert subclass_feature_levels(CharacterClassDefinition(name="Early", subclass_level=1)) == [1, 6, 10, 14]


# --------------------------------------------------------------------------- the class editor

def test_a_new_class_has_every_level_ready_with_the_standard_features(host, tk_root):
    panel = class_panel(host, tk_root)
    sections = open_features_tab(panel, tk_root)
    assert sections.levels() == list(range(1, 21))
    feats = sections.get_features()
    assert [f.title for f in feats[4]] == ["Ability Score Improvement"]
    assert [f.title for f in feats[19]] == ["Epic Boon"]
    assert feats[1] == [] and feats[5] == []
    assert panel._subclass_levels == {3, 6, 10, 14}
    assert [lvl for lvl, var in panel._subclass_vars.items() if var.get()] == [3, 6, 10, 14]


def test_moving_the_subclass_level_moves_the_ticks(host, tk_root):
    panel = class_panel(host, tk_root)
    open_features_tab(panel, tk_root)
    panel.subclass_level_var.set("1")
    panel._on_subclass_level_changed()
    assert panel._subclass_levels == {1, 6, 10, 14}
    assert panel._subclass_vars[1].get() and not panel._subclass_vars[3].get()
    # once a level is ticked by hand the editor stops guessing
    panel._subclass_vars[8].set(True)
    panel._toggle_subclass_level(8)
    panel.subclass_level_var.set("3")
    panel._on_subclass_level_changed()
    assert panel._subclass_levels == {1, 6, 8, 10, 14}


def test_features_are_typed_into_cards_and_saved(host, tk_root):
    panel = class_panel(host, tk_root)
    sections = open_features_tab(panel, tk_root)
    panel.name_entry.insert(0, "Cardwright")
    sections.add_feature(1)
    sections.add_feature(1)
    pump(tk_root, 0.2)
    cards = sections._sections[1].cards
    assert len(cards) == 2
    cards[0].title.insert(0, "Deal")
    cards[0].text.insert("1.0", "You draw a card.")
    cards[1].title.insert(0, "Shuffle")
    cards[1].text.insert("1.0", "You shuffle the deck.")
    sections.add_feature(2)
    sections._sections[2].cards[0].title.insert(0, "Empty one")     # no description: not allowed on a real save
    cls = panel.build_result(strict=False)
    assert [f.title for f in cls.levels[1].abilities] == ["Deal", "Shuffle"]
    assert [f.description for f in cls.levels[1].abilities] == ["You draw a card.", "You shuffle the deck."]
    assert [f.title for f in cls.levels[4].abilities] == ["Ability Score Improvement"]
    with pytest.raises(ValueError, match="Empty one"):
        panel.build_result(strict=True)
    sections._sections[2].cards[0].text.insert("1.0", "Nothing happens.")
    assert panel.build_result(strict=True).levels[2].abilities[0].title == "Empty one"


def test_empty_cards_are_ignored(host, tk_root):
    panel = class_panel(host, tk_root)
    sections = open_features_tab(panel, tk_root)
    panel.name_entry.insert(0, "Tidy")
    sections.add_feature(5)
    assert panel.build_result(strict=True).levels[5].abilities == []


def test_subclass_levels_become_placeholders_in_the_saved_class(host, tk_root):
    panel = class_panel(host, tk_root)
    open_features_tab(panel, tk_root)
    panel.name_entry.insert(0, "Placeholder")
    cls = panel.build_result(strict=False)
    marked = [lvl for lvl, level in cls.levels.items() if any(a.is_subclass_feature for a in level.abilities)]
    assert marked == [3, 6, 10, 14]


def test_an_existing_class_keeps_everything_it_had(host, tk_root):
    from character_class import get_class_manager
    fighter = get_class_manager().get_class("Fighter")
    panel = class_panel(host, tk_root, fighter)
    sections = open_features_tab(panel, tk_root)
    built = [lvl for lvl, s in sections._sections.items() if s.built]
    assert built == [1]                                  # sections are built when opened, not all at once
    before = {lvl: [(f.title, f.description, f.is_subclass_feature) for f in level.abilities]
              for lvl, level in fighter.levels.items()}
    result = panel.build_result(strict=False)
    after = {lvl: [(f.title, f.description, f.is_subclass_feature) for f in level.abilities]
             for lvl, level in result.levels.items()}
    assert after == before
    assert sections.get_features()[3] != []              # subclass placeholders are not shown but not lost
    assert [f.title for f in result.levels[3].abilities] == [f.title for f in fighter.levels[3].abilities]


def test_editing_a_card_does_not_change_the_original_class(host, tk_root):
    from character_class import get_class_manager
    fighter = get_class_manager().get_class("Fighter")
    original = fighter.levels[1].abilities[0].description
    panel = class_panel(host, tk_root, fighter)
    sections = open_features_tab(panel, tk_root)
    card = sections._sections[1].cards[0]
    card.text.insert("end", " EDITED")
    assert panel.build_result(strict=False).levels[1].abilities[0].description.endswith("EDITED")
    assert fighter.levels[1].abilities[0].description == original


def test_a_level_can_be_opened_and_closed(host, tk_root):
    panel = class_panel(host, tk_root)
    sections = open_features_tab(panel, tk_root)
    sections.toggle(4)
    assert sections._sections[4].open and sections._sections[4].built
    assert "Ability Score Improvement" in [c.title.get() for c in sections._sections[4].cards]
    assert "1 feature" in sections._sections[4].header.cget("text")
    sections.toggle(4)
    assert not sections._sections[4].open


# --------------------------------------------------------------------------- the subclass editor

def subclass_panel(host, root, parent_name="Fighter", subclass=None):
    from character_class import get_class_manager
    from ui.class_editor import SubclassEditorPanel
    panel = SubclassEditorPanel(host, get_class_manager().get_class(parent_name), subclass=subclass)
    panel.pack(fill="both", expand=True)
    pump(root, 0.3)
    return panel


def test_a_new_subclass_has_a_section_for_each_of_the_classs_levels(host, tk_root):
    panel = subclass_panel(host, tk_root, "Fighter")
    sections = panel.feature_sections
    assert sections.levels() == [3, 7, 10, 15, 18]
    assert all(s.open and s.built and len(s.cards) == 1 for s in sections._sections.values())   # a blank card each
    panel2 = subclass_panel(host, tk_root, "Bard")
    assert panel2.feature_sections.levels() == [3, 6, 14]


def test_subclass_features_are_typed_into_the_levels(host, tk_root):
    panel = subclass_panel(host, tk_root, "Fighter")
    panel.name_entry.insert(0, "Card Shark")
    sections = panel.feature_sections
    first = sections._sections[3].cards[0]
    first.title.insert(0, "Stacked Deck")
    first.text.insert("1.0", "You always draw the card you want.")
    sections.add_feature(7)
    second = sections._sections[7].cards[-1]
    second.title.insert(0, "Cold Read")
    second.text.insert("1.0", "You know what they hold.")
    sub = panel.build_result(strict=True)
    assert [(f.level, f.title) for f in sub.features] == [(3, "Stacked Deck"), (7, "Cold Read")]
    assert sub.parent_class == "Fighter"


def test_untouched_blank_cards_are_not_saved(host, tk_root):
    panel = subclass_panel(host, tk_root, "Fighter")
    panel.name_entry.insert(0, "Empty Shell")
    assert panel.build_result(strict=True).features == []


def test_an_existing_subclass_shows_its_features_in_their_levels(host, tk_root):
    from character_class import get_class_manager
    fighter = get_class_manager().get_class("Fighter")
    champion = next(s for s in fighter.subclasses if s.features)
    panel = subclass_panel(host, tk_root, "Fighter", champion)
    got = panel.build_result(strict=False)
    assert [(f.level, f.title, f.description) for f in got.features] == \
        [(f.level, f.title, f.description) for f in champion.features]
    for feature in champion.features:
        assert any(c.title.get() == feature.title for c in panel.feature_sections._sections[feature.level].cards)


def test_a_feature_at_an_unusual_level_gets_its_own_section(host, tk_root):
    from character_class import SubclassDefinition, SubclassFeature
    odd = SubclassDefinition(name="Odd Timing", parent_class="Fighter", features=[
        SubclassFeature(level=5, title="Early Bloomer", description="Arrives at level 5.")])
    panel = subclass_panel(host, tk_root, "Fighter", odd)
    assert 5 in panel.feature_sections.levels()
    assert "not one of the class's subclass levels" in panel.feature_sections._sections[5].header.cget("text")
    assert [f.level for f in panel.build_result(strict=False).features] == [5]
    panel._add_extra_level("12")
    assert 12 in panel.feature_sections.levels()


def test_the_studio_creates_the_same_sections(host, tk_root):
    import studio_store as SS
    from ui.studio_view import make_editor
    draft = SS.Draft(id="x", kind="subclasses", name="", parent="Cleric")
    panel = make_editor("subclasses", host, draft, None, None)
    panel.pack(fill="both", expand=True)
    pump(tk_root, 0.3)
    assert panel.feature_sections.levels() == [3, 6, 10, 14, 17]
