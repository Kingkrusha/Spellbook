"""Armor Class, hit point maximum, initiative and the spell attack / save DC: worked out (items and features counted),
explained on hover, and typed over when the player wants."""

import time
from types import SimpleNamespace

import pytest

import sheet_stats as S
from character import CharacterSpellList, ClassLevel
from character_rolls import Lookups
from character_sheet import AbilityScore, CharacterSheet


def character(classes=(("Fighter", 5),), **kw) -> CharacterSpellList:
    return CharacterSpellList(name="Tester", classes=[ClassLevel.from_dict({"class": c, "level": l}) for c, l in classes],
                              **kw)


def sheet_for(char, **scores) -> CharacterSheet:
    sheet = CharacterSheet(character_name=char.name)
    sheet.proficiency_bonus = 2 + (sum(c.level for c in char.classes) - 1) // 4
    for ab, value in scores.items():
        sheet.ability_scores.set(AbilityScore[ab.upper()], value)
    return sheet


def magic(**items):
    """A lookup for magic items by name: {name: description}."""
    return lambda name: SimpleNamespace(description=items[name], type="Ring", requires_attunement=False,
                                        attunement_optional=False, rarity=SimpleNamespace(value="Rare"),
                                        roll_effects=[]) if name in items else None


def lookups(items=None, feats=None, lineages=None, classes=None) -> Lookups:
    feats = feats or {}
    return Lookups(magic_item=magic(**(items or {})),
                   feat=lambda n: SimpleNamespace(description=feats[n]) if n in feats else None,
                   lineage=lambda n: SimpleNamespace(traits=[SimpleNamespace(name=t, description=d)
                                                             for t, d in (lineages or {}).get(n, [])])
                   if n in (lineages or {}) else None,
                   class_def=lambda n: (classes or {}).get(n))


# --------------------------------------------------------------------------- reading text

@pytest.mark.parametrize("text, expected", [
    ("You gain a +1 bonus to AC and saving throws while wearing this ring.", [("armor_class", 1, "")]),
    ("While you are wearing armor, you gain a +1 bonus to Armor Class.", [("armor_class", 1, "armored")]),
    ("You gain a +2 bonus to AC if you are wearing no armor and using no shield.",
     [("armor_class", 2, "unarmored,no_shield")]),
    ("Your Armor Class increases by 1.", [("armor_class", 1, "")]),
    ("You gain a +5 bonus to initiative.", [("initiative", 5, "")]),
    ("When you roll Initiative, you can add your Proficiency Bonus to the roll.", [("initiative", 3, "")]),
    ("Your Hit Point maximum increases by an amount equal to twice your character level.", [("hp_max", 10, "")]),
    ("Your hit point maximum increases by 1, and it increases by 1 every time you gain a level.", [("hp_max", 5, "")]),
    ("Your hit point maximum increases by 20.", [("hp_max", 20, "")]),
])
def test_plain_bonuses_are_read(text, expected):
    assert S.read_bonuses(text, source="x", level=5, prof=3) == expected


@pytest.mark.parametrize("text", [
    "As a reaction, you gain a +5 bonus to AC until the start of your next turn.",
    "You gain a +1 bonus to AC while you are raging.",
    "For example, you could gain a +2 bonus to Armor Class.",
    "Until the end of your next turn, the target gains a +2 bonus to AC.",
    "While you are holding a double-bladed scimitar with two hands, you gain a +1 bonus to Armor Class.",
    "You can use your action to give an ally a +2 bonus to AC.",
    "The tavern smells of smoke.",
])
def test_temporary_conditional_and_unrelated_text_is_left_alone(text):
    assert S.read_bonuses(text, source="x", level=5, prof=3) == []


# --------------------------------------------------------------------------- the numbers

def test_ac_parts_add_up_and_name_their_source():
    c = character()
    sheet = sheet_for(c, dexterity=16)
    sheet.armor_type = "Breastplate"
    sheet.shield_bonus = 2
    sheet.magic_items = [{"name": "Ring of Protection", "attuned": True, "requires_attunement": True}]
    look = lookups(items={"Ring of Protection": "You gain a +1 bonus to AC and saving throws while wearing this ring."})
    ac = S.auto_ac(c, sheet, look)
    assert ac.value == 14 + 2 + 2 + 1                       # breastplate, Dexterity capped at +2, shield, ring
    text = ac.explain()
    assert "14 Breastplate" in text and "+2 Dexterity (capped at +2)" in text and "+2 shield" in text
    assert "+1 Ring of Protection" in text


def test_a_ring_that_needs_attunement_only_counts_when_attuned():
    c = character()
    sheet = sheet_for(c, dexterity=14)
    sheet.magic_items = [{"name": "Ring of Protection", "attuned": False, "requires_attunement": True}]
    look = lookups(items={"Ring of Protection": "You gain a +1 bonus to AC and saving throws while wearing this ring."})
    ac = S.auto_ac(c, sheet, look)
    assert ac.value == 12 and "not counted: not attuned" in ac.explain()
    sheet.magic_items[0]["attuned"] = True
    assert S.auto_ac(c, sheet, look).value == 13


def test_features_that_need_armor_or_none_are_checked_against_what_is_worn():
    c = character(feats=["Defense"])
    sheet = sheet_for(c, dexterity=10)
    look = lookups(feats={"Defense": "While you are wearing armor, you gain a +1 bonus to Armor Class."})
    assert S.auto_ac(c, sheet, look).value == 10                    # no armor: nothing
    assert "needs armor" in S.auto_ac(c, sheet, look).explain()
    sheet.armor_type = "Chain Mail"
    assert S.auto_ac(c, sheet, look).value == 16 + 1


def test_initiative_counts_dexterity_the_sheet_bonus_and_features():
    c = character(feats=["Alert"])
    sheet = sheet_for(c, dexterity=14)
    sheet.initiative_bonus = 1
    look = lookups(feats={"Alert": "Initiative Proficiency. When you roll Initiative, you can add your Proficiency Bonus to the roll."})
    init = S.auto_initiative(c, sheet, look)
    assert init.value == 2 + 1 + 3                                  # Dexterity, entered bonus, proficiency
    assert [label for _a, label in init.parts] == ["Dexterity", "bonus entered on the sheet", "Alert"]
    assert S.initiative_extra(c, sheet, look) == 3
    sheet.initiative_auto_bonus = S.initiative_extra(c, sheet, look)
    assert sheet.get_initiative() == 6                              # what the initiative tracker reads


def test_hit_points_count_tough_species_traits_and_items():
    c = character((("Fighter", 5),), feats=["Tough"], lineage="Hill Dwarf")
    sheet = sheet_for(c, constitution=14)
    look = lookups(lineages={"Hill Dwarf": [("Dwarven Toughness", "Your hit point maximum increases by 1, and it "
                                                                   "increases by 1 every time you gain a level.")]},
                   feats={"Tough": "Your Hit Point maximum increases by an amount equal to twice your character level "
                                   "when you gain this feat."})
    hp = S.auto_hp_max(c, sheet, look)
    base = 10 + 2 + 4 * (6 + 2)                                     # d10 first level, then the average, +2 each
    assert hp.value == base + 10 + 5                                # Tough once (not twice), Dwarven Toughness
    assert "Tough (+2 per level)" in hp.explain() and "Dwarven Toughness" in hp.explain()


def test_class_features_only_count_up_to_the_levels_the_character_has():
    from character_class import ClassAbility, ClassLevel as CL, CharacterClassDefinition
    cls = CharacterClassDefinition(name="Fighter", levels={
        1: CL(level=1, abilities=[ClassAbility("Stout", "Your hit point maximum increases by 2.")]),
        9: CL(level=9, abilities=[ClassAbility("Iron Will", "You gain a +1 bonus to initiative.")])})
    c = character((("Fighter", 5),))
    sheet = sheet_for(c)
    bonuses = S.find_bonuses(c, sheet, lookups(classes={"Fighter": cls}))
    assert [(b.stat, b.amount, b.source) for b in bonuses] == [("hp_max", 2, "Stout")]


def test_a_typed_number_is_manual_unless_it_is_the_automatic_one():
    sheet = CharacterSheet(character_name="T")
    assert S.set_override(sheet, "armor_class", "17", 15) == 17 and sheet.stat_overrides == {"armor_class": 17}
    assert S.set_override(sheet, "armor_class", "+15", 15) is None and sheet.stat_overrides == {}
    S.set_override(sheet, "initiative", "-1", 2)
    assert sheet.get_initiative() == -1
    assert S.set_override(sheet, "initiative", "", 2) is None and "initiative" not in sheet.stat_overrides
    with pytest.raises(ValueError):
        S.set_override(sheet, "hp_max", "lots", 40)


def test_manual_numbers_say_so_and_what_auto_detection_gives():
    assert S.manual_tip("+7").startswith("Manually set\nAuto detection: +7")


def test_overrides_are_saved_with_the_sheet():
    sheet = CharacterSheet(character_name="T")
    assert "stat_overrides" not in sheet.to_dict() and "initiative_auto_bonus" not in sheet.to_dict()
    sheet.stat_overrides = {"armor_class": 19, "spell_dc:INT": 16}
    sheet.initiative_auto_bonus = 3
    again = CharacterSheet.from_dict(sheet.to_dict())
    assert again.stat_overrides == {"armor_class": 19, "spell_dc:INT": 16} and again.initiative_auto_bonus == 3


# --------------------------------------------------------------------------- spell attack and save DC

def wizard():
    c = character((("Wizard", 5),))
    sheet = sheet_for(c, intelligence=18)
    return c, sheet


def numbers(c, sheet, items=None):
    from character_class import get_class_manager
    from character_rolls import spell_numbers
    look = Lookups(class_def=lambda n: get_class_manager().get_class(n), magic_item=magic(**(items or {})))
    return spell_numbers(c, sheet, look)


def test_the_spell_numbers_explain_themselves():
    c, sheet = wizard()
    stat = numbers(c, sheet)[0]
    assert (stat.attack, stat.dc) == (7, 15) and not stat.attack_manual and not stat.dc_manual
    assert stat.attack_tip() == "Spell attack modifier\n+3 proficiency, +4 Intelligence"
    assert stat.dc_tip() == "Spell save DC\n8, +3 proficiency, +4 Intelligence"


def test_magic_items_show_up_in_the_explanation():
    c, sheet = wizard()
    sheet.magic_items = [{"name": "Rod of the Pact Keeper", "attuned": True, "requires_attunement": True}]
    items = {"Rod of the Pact Keeper": "You gain a +1 bonus to spell attack rolls and to the saving throw DCs of your spells."}
    stat = numbers(c, sheet, items)[0]
    assert (stat.attack, stat.dc) == (8, 16)
    assert "+1 Rod of the Pact Keeper" in stat.attack_tip() and "+1 Rod of the Pact Keeper" in stat.dc_tip()


def test_a_typed_spell_attack_replaces_the_automatic_one_and_the_tooltip_says_so():
    c, sheet = wizard()
    S.set_override(sheet, S.spell_key("spell_attack", "INT"), "10", 7)
    stat = numbers(c, sheet)[0]
    assert stat.attack == 10 and stat.attack_manual and not stat.dc_manual
    assert stat.attack_tip().startswith("Manually set\nAuto detection: +7")
    assert stat.dc == 15
    S.set_override(sheet, S.spell_key("spell_dc", "INT"), "17", 15)
    assert numbers(c, sheet)[0].dc_tip().startswith("Manually set\nAuto detection: 15")
    S.set_override(sheet, S.spell_key("spell_attack", "INT"), "", 7)
    assert not numbers(c, sheet)[0].attack_manual


def test_the_dice_analyzer_uses_the_typed_spell_numbers_too():
    from character_context import Ctx
    c, sheet = wizard()
    S.set_override(sheet, S.spell_key("spell_dc", "INT"), "18", 15)
    ctx = Ctx(c, sheet)
    assert ctx.spell_dc("INT") == 18 and ctx.spell_dc("INT", raw=True) == 15
    assert ctx.spell_attack_bonus("INT") == 7


def test_a_stat_without_overrides_keeps_working_as_before():
    from character_rolls import SpellStat
    stat = SpellStat("Wizard", "INT", 7, 15, ["note"])
    assert not stat.attack_manual and not stat.dc_manual and (stat.auto_attack, stat.auto_dc) == (7, 15)
