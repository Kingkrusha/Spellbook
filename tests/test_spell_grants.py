"""Spells given by species, feats and features; what a character can learn; the spell attack / save DC numbers."""

import pytest

import spell_access as access
import spell_grants as grants
from character import CharacterSpellList, ClassLevel, update_subclass_spells
from character_rolls import Lookups, spell_numbers
from character_sheet import AbilityScore, CharacterSheet
from spell import CharacterClass


def make(classes, **kw):
    return CharacterSpellList(name="T", classes=[ClassLevel.from_dict(
        {"class": c[0], "level": c[1], "subclass": c[2] if len(c) > 2 else ""}) for c in classes], **kw)


def granted(character):
    update_subclass_spells(character)
    return set(character.subclass_spells)


# ----------------------------------------------------------------------------- feats and species

def test_a_feat_gives_its_set_spell_and_it_is_not_counted_against_prepared_spells():
    c = make([("Wizard", 3)], feats=["Fey Touched"])
    assert "Misty Step" in granted(c)
    assert c.has_spell("Misty Step") and c.is_prepared("Misty Step")
    assert c.get_prepared_count() == 0
    assert c.spell_sources["Misty Step"] == "Feat: Fey Touched"


def test_taking_a_feat_away_takes_its_spell_away():
    c = make([("Wizard", 3)], feats=["Fey Touched"])
    granted(c)
    c.feats = []
    assert "Misty Step" not in granted(c)
    assert not c.has_spell("Misty Step")


def test_a_species_variant_decides_the_spells_and_levels_decide_when_they_arrive():
    c = make([("Wizard", 2)], lineage="Elf")
    assert granted(c) == set()                         # no lineage chosen yet
    c.grant_options["lineage:Elf"] = "Drow"
    assert granted(c) == {"Dancing Lights"}
    c.classes[0].level = 3
    assert granted(c) == {"Dancing Lights", "Faerie Fire"}
    c.classes[0].level = 5
    assert {"Dancing Lights", "Faerie Fire", "Darkness"} <= granted(c)
    c.grant_options["lineage:Elf"] = "High Elf"
    result = granted(c)
    assert "Dancing Lights" not in result and {"Prestidigitation", "Detect Magic", "Misty Step"} <= result


def test_a_species_without_variants_just_gives_its_spells():
    c = make([("Fighter", 5)], lineage="Faerie")
    assert granted(c) == {"Druidcraft", "Faerie Fire", "Enlarge/Reduce"}
    assert make([("Fighter", 1)], lineage="Aasimar").classes and granted(make([("Fighter", 1)], lineage="Aasimar")) == {"Light"}


def test_chosen_spells_are_granted_and_the_unchosen_are_offered():
    c = make([("Fighter", 1)], feats=["Magic Initiate (Cleric)"])
    report = grants.build_report(c)
    assert [(p.spell_level, p.count) for p in report.picks] == [(0, 2), (1, 1)]
    assert report.unresolved() == 3
    c.grant_choices["feat:Magic Initiate (Cleric):0"] = ["Guidance", "Light"]
    assert {"Guidance", "Light"} <= granted(c)
    assert grants.build_report(c).unresolved() == 1
    assert c.get_prepared_count() == 0


def test_a_pick_is_limited_to_its_list_and_level():
    from spell_manager import SpellManager
    manager = SpellManager()
    manager.load_spells()
    pick = grants.build_report(make([("Fighter", 1)], feats=["Magic Initiate (Cleric)"])).picks[0]
    assert pick.allows(manager.get_spell("Guidance"))            # a Cleric cantrip
    assert not pick.allows(manager.get_spell("Fire Bolt"))       # not a Cleric spell
    assert not pick.allows(manager.get_spell("Cure Wounds"))     # not a cantrip


def test_a_feat_does_not_ask_for_a_pick_it_already_filled():
    # Cold Caster names Ray of Frost, so its "one cantrip" is that one
    report = grants.build_report(make([("Wizard", 1)], feats=["Cold Caster"]))
    assert [g.spell for g in report.fixed] == ["Ray of Frost"] and not report.picks


def test_class_and_subclass_features_give_spells_from_the_level_they_arrive():
    c = make([("Wizard", 2, "Transmuter")])
    assert granted(c) == set()                          # nothing before the subclass is chosen
    c.classes[0].level = 3
    assert "Alter Self" in granted(c)
    c.classes[0].level = 10
    assert {"Alter Self", "Polymorph"} <= granted(c)
    assert "Subclass: Transmuter" in c.spell_sources["Polymorph"]
    druid = make([("Druid", 2)])
    assert {"Speak with Animals", "Find Familiar"} <= granted(druid)
    assert make([("Barbarian", 3, "Path of the Wild Heart")]).classes and \
        granted(make([("Barbarian", 3, "Path of the Wild Heart")])) == {"Beast Sense", "Speak with Animals"}


def test_2014_content_gets_its_own_2014_spells():
    c = make([("Wizard (Legacy)", 10, "School of Transmutation")], lineage="Dark Elf", feats=["Eldritch Sight"])
    result = granted(c)
    assert {"Polymorph (Legacy)", "Dancing Lights (Legacy)", "Faerie Fire (Legacy)", "Detect Magic (Legacy)"} <= result
    assert "Polymorph" not in result


def test_a_homebrew_species_trait_can_name_spells():
    from lineage import Lineage, LineageTrait

    class Manager:
        def get_lineage(self, name):
            return Lineage(name="Starborn", is_custom=True, traits=[LineageTrait(
                "Star Magic", "x", spells=[{"spell": "Light", "level": 1}, {"spell": "Misty Step", "level": 3},
                                           {"spell": "Fireball", "level": 5, "option": "Fire"}])])

    c = make([("Fighter", 3)], lineage="Starborn")
    report = grants.build_report(c, lineage_manager=Manager())
    assert [g.spell for g in report.fixed] == ["Light", "Misty Step"]
    assert report.options[0].options == ["Fire"] and not report.options[0].selected


def test_the_grant_fields_survive_saving():
    c = make([("Fighter", 1)], feats=["Fey Touched"])
    c.grant_options["lineage:Elf"] = "Drow"
    c.grant_choices["feat:Fey Touched:1"] = ["Bless"]
    granted(c)
    again = CharacterSpellList.from_dict(c.to_dict())
    assert again.grant_options == c.grant_options and again.grant_choices == c.grant_choices
    assert again.spell_sources == c.spell_sources


# ----------------------------------------------------------------------------- what a character can learn

@pytest.fixture(scope="module")
def spells():
    from spell_manager import SpellManager
    manager = SpellManager()
    manager.load_spells()
    return manager


def test_a_wizard_can_learn_wizard_spells_up_to_the_level_they_can_cast(spells):
    rules = access.learn_rules(make([("Wizard", 5)]))
    assert rules.max_level == 3
    assert rules.allows(spells.get_spell("Fireball"))
    assert rules.allows(spells.get_spell("Fire Bolt"))                      # cantrips are always in reach
    assert not rules.allows(spells.get_spell("Wish"))
    assert "level 9" in rules.why_not(spells.get_spell("Wish"))
    assert not rules.allows(spells.get_spell("Cure Wounds"))
    assert "not on" in rules.why_not(spells.get_spell("Cure Wounds"))


def test_multiclass_characters_can_learn_from_each_list(spells):
    rules = access.learn_rules(make([("Wizard", 3), ("Cleric", 3)]))
    assert rules.allows(spells.get_spell("Cure Wounds")) and rules.allows(spells.get_spell("Shield"))


def test_a_warlock_can_also_learn_the_spells_their_patron_adds(spells):
    plain = access.learn_rules(make([("Warlock", 5)]))
    patron = access.learn_rules(make([("Warlock", 5, "Fiend Patron")]))
    assert patron.max_level == 3
    assert not plain.allows(spells.get_spell("Burning Hands"))            # a Fiend spell, not a Warlock one
    assert patron.allows(spells.get_spell("Burning Hands"))
    assert not patron.allows(spells.get_spell("Meteor Swarm"))            # still too high a level


def test_a_2014_patrons_expanded_spell_list_counts(spells):
    c = make([("Warlock (Legacy)", 5, "The Archfey")])
    rules = access.learn_rules(c)
    assert "faerie fire (legacy)" in rules.expanded and rules.max_level == 3
    assert rules.allows(spells.get_spell("Faerie Fire (Legacy)"))
    assert rules.allows(spells.get_spell("Eldritch Blast (Legacy)")) or rules.allows(spells.get_spell("Eldritch Blast"))


def test_a_mark_of_eberron_adds_its_spells_to_the_list(spells):
    plain = access.learn_rules(make([("Wizard", 5)]))
    marked = access.learn_rules(make([("Wizard", 5)], feats=["Mark of Detection"]))
    spell = spells.get_spell("See Invisibility")
    assert marked.allows(spell) or "see invisibility" in marked.expanded
    assert len(marked.expanded) > len(plain.expanded)


def test_third_casters_and_custom_classes(spells):
    knight = access.learn_rules(make([("Fighter", 7, "Eldritch Knight")]))
    assert knight.max_level == 2 and knight.allows(spells.get_spell("Shield"))
    trickster = access.learn_rules(make([("Rogue", 7, "Arcane Trickster")]))
    assert trickster.max_level == 2 and trickster.allows(spells.get_spell("Disguise Self"))
    custom = make([("Custom", 3)])
    assert access.learn_rules(custom).allows(spells.get_spell("Wish"))


def test_bards_get_magical_secrets(spells):
    rules = access.learn_rules(make([("Bard", 10)]))
    assert rules.allows(spells.get_spell("Cure Wounds")) and rules.allows(spells.get_spell("Shield"))


# ----------------------------------------------------------------------------- spell attack and save DC

def sheet(prof=3, **scores):
    s = CharacterSheet(character_name="T")
    s.proficiency_bonus = prof
    for ab, v in scores.items():
        s.ability_scores.set(getattr(AbilityScore, ab), v)
    return s


def test_spell_numbers_are_proficiency_plus_the_casting_modifier():
    c = make([("Wizard", 5)])
    from character_class import get_class_manager
    lk = Lookups(class_def=get_class_manager().get_class)
    [stat] = spell_numbers(c, sheet(INTELLIGENCE=18), lk)
    assert (stat.label, stat.ability, stat.attack, stat.dc) == ("Wizard", "INT", 7, 15)


def test_multiclass_casters_with_different_abilities_get_their_own_numbers():
    c = make([("Wizard", 3), ("Cleric", 2)])
    from character_class import get_class_manager
    lk = Lookups(class_def=get_class_manager().get_class)
    stats = spell_numbers(c, sheet(INTELLIGENCE=16, WISDOM=14), lk)
    assert {(s.label, s.ability): (s.attack, s.dc) for s in stats} == {("Wizard", "INT"): (6, 14),
                                                                       ("Cleric", "WIS"): (5, 13)}


def test_magic_items_add_to_the_numbers_only_while_attuned():
    from character_class import get_class_manager
    from magic_item import get_magic_item_manager
    lk = Lookups(class_def=get_class_manager().get_class, magic_item=get_magic_item_manager().get_item)
    c = make([("Wizard", 5)])
    s = sheet(INTELLIGENCE=16)
    s.magic_items = [{"name": "Wand of the War Mage, +1, +2 or +3", "attuned": True, "requires_attunement": True,
                      "extra_properties": ""}]
    [on] = spell_numbers(c, s, lk)
    assert (on.attack, on.dc) == (7, 14) and any("War Mage" in n for n in on.notes)    # +1 to attack rolls only
    s.magic_items[0]["attuned"] = False
    [off] = spell_numbers(c, s, lk)
    assert (off.attack, off.dc) == (6, 14) and any("not counted" in n for n in off.notes)


def test_a_character_whose_spells_come_only_from_a_species_gets_the_best_mental_ability():
    c = make([("Fighter", 3)], lineage="Faerie")
    assert spell_numbers(c, sheet(CHARISMA=14), Lookups()) == []
    [stat] = spell_numbers(c, sheet(CHARISMA=14, WISDOM=8), Lookups(), extra_casters=True)
    assert (stat.ability, stat.attack, stat.dc) == ("CHA", 5, 13)


# ----------------------------------------------------------------------------- third-caster subclasses

def test_arcane_tricksters_and_mystic_arts_monks_cast_like_eldritch_knights(spells):
    from character import get_max_prepared_spells
    from spell_slots import get_max_spell_slots
    from ui.spell_lists_view import get_effective_max_cantrips, get_effective_max_slots
    knight = make([("Fighter", 7, "Eldritch Knight")])
    trickster = make([("Rogue", 7, "Arcane Trickster")])
    monk = make([("Monk", 7, "Warrior of the Mystic Arts")])
    for c in (knight, trickster, monk):
        assert c.get_eldritch_knight_level() == 7
        assert get_effective_max_slots(c) == {1: 4, 2: 2}
        assert get_max_prepared_spells(c) == 5
    assert get_effective_max_cantrips(knight) == 2 and get_effective_max_cantrips(monk) == 2
    assert get_effective_max_cantrips(trickster) == 3                      # Mage Hand on top
    assert make([("Rogue", 2, "Arcane Trickster")]).get_eldritch_knight_level() == 0
    assert get_max_spell_slots([(CharacterClass.ROGUE, 7)], 0) == {}


def test_third_casters_learn_from_their_own_list(spells):
    monk = access.learn_rules(make([("Monk", 9, "Warrior of the Mystic Arts")]))
    assert monk.max_level == 2 and monk.allows(spells.get_spell("Magic Missile"))        # a Sorcerer spell
    assert not monk.allows(spells.get_spell("Cure Wounds"))
    trickster = access.learn_rules(make([("Rogue", 9, "Arcane Trickster")]))
    assert trickster.allows(spells.get_spell("Magic Missile")) and trickster.max_level == 2


def test_the_warrior_of_the_mystic_arts_casts_with_wisdom():
    from character_class import get_class_manager
    lk = Lookups(class_def=get_class_manager().get_class)
    [stat] = spell_numbers(make([("Monk", 5, "Warrior of the Mystic Arts")]), sheet(WISDOM=16, INTELLIGENCE=8), lk)
    assert (stat.ability, stat.attack, stat.dc) == ("WIS", 6, 14)


def test_a_divine_soul_can_learn_cleric_spells(spells):
    rules = access.learn_rules(make([("Sorcerer (Legacy)", 5, "Divine Soul")]))
    assert rules.allows(spells.get_spell("Cure Wounds (Legacy)")) or rules.allows(spells.get_spell("Cure Wounds"))
