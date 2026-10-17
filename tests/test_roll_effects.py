"""Homebrew roll effects: validation, turning them into rules, and a character picking them up."""

from types import SimpleNamespace

import pytest

from character import CharacterSpellList, ClassLevel
from character_rolls import CharacterAnalyzer, Lookups
from character_sheet import AbilityScore, CharacterSheet, Skill
from roll_effects import blank_effect, build_effects, describe, parse_limit, validate


def effect(**kw):
    base = blank_effect(kw.pop("affects", "skill"))
    base.update(kw)
    return base


def make(classes=(("Fighter", 3),), lineage="Human", feats=(), scores=None, prof=2, attacks=(), lookups=None,
         magic_items=(), subclass=""):
    ch = CharacterSpellList(name="T", lineage=lineage, classes=[
        ClassLevel.from_dict({"class": n, "level": lv, "subclass": subclass}) for n, lv in classes])
    ch.feats = list(feats)
    sheet = CharacterSheet(character_name="T")
    sheet.proficiency_bonus = prof
    for ab, v in (scores or {}).items():
        sheet.ability_scores.set(ab, v)
    sheet.attacks = list(attacks)
    sheet.magic_items = list(magic_items)
    return CharacterAnalyzer(ch, sheet, lookups), ch


def run(analyzer, key, state=None):
    return {r.key: r for r in analyzer.rolls()}[key].analyze(state or {})


def mean(analysis):
    return analysis.views[0].dist.mean()


# ----------------------------------------------------------------------------- the effect itself

def test_validation_explains_what_is_wrong():
    assert validate(effect(does="advantage")) == ""
    assert "does not apply" in validate(effect(affects="weapon damage", does="advantage"))
    assert "Dice need" in validate(effect(does="dice", count=0))
    assert "critical hit" in validate(effect(affects="attack", does="crit", value=1))
    assert "ability" in validate(effect(affects="item set ability", does="set", value=19, limit="banana"))
    assert validate({"affects": "nonsense"})


def test_the_limit_box_is_read_leniently():
    lim = parse_limit("Stealth, perception and Strength; proficient")
    assert lim.skills == ["Perception", "Stealth"] and lim.abilities == ["STR"] and lim.proficient
    assert parse_limit("concentration").conc and parse_limit("ranged").ranged is True
    assert parse_limit("fire, evocation cantrip").types == ["fire"]
    assert parse_limit("charmed").vs == "charmed" and parse_limit("against magic").vs == "magic"


def test_describe_reads_like_a_sentence():
    text = describe(effect(does="dice", count=2, sides=6, limit="Stealth", choice=True))
    assert "Add dice (2d6)" in text and "only Stealth" in text and "[a choice]" in text
    assert "proficiency bonus" in describe(effect(does="bonus", scales="proficiency bonus"))


# ----------------------------------------------------------------------------- a homebrew feat

def feat_lookup(**feats):
    return lambda name: SimpleNamespace(name=name, roll_effects=feats[name]) if name in feats else None


def test_a_homebrew_feat_with_an_advantage_effect():
    lookups = Lookups(feat=feat_lookup(**{"Eagle Eye": [effect(does="advantage", limit="Perception")]}))
    a, _ = make(feats=["Eagle Eye"], lookups=lookups)
    assert mean(run(a, "skill:PERCEPTION")) == pytest.approx(13.825)
    assert mean(run(a, "skill:STEALTH")) == pytest.approx(10.5)
    plain, _ = make(lookups=lookups)
    assert mean(run(plain, "skill:PERCEPTION")) == pytest.approx(10.5)
    assert ("homebrew:0", "Feat: Eagle Eye (homebrew)", "sheet") in a.feature_report()


def test_a_choice_effect_becomes_a_toggle_and_scaling_follows_the_character():
    eff = effect(affects="save", does="bonus", scales="WIS modifier (min +1)", choice=True, limit="WIS")
    lookups = Lookups(feat=feat_lookup(**{"Steady Mind": [eff]}))
    a, _ = make(feats=["Steady Mind"], scores={AbilityScore.WISDOM: 18}, lookups=lookups)
    opt = [o for o in {r.key: r for r in a.rolls()}["save:WIS"].options if o.key.startswith("rule:hb:")]
    assert len(opt) == 1 and opt[0].default is False
    assert mean(run(a, "save:WIS")) == pytest.approx(10.5 + 4)               # the WIS mod itself, no extra
    assert mean(run(a, "save:WIS", {opt[0].key: True})) == pytest.approx(10.5 + 4 + 4)
    assert not [o for o in {r.key: r for r in a.rolls()}["save:STR"].options if o.key.startswith("rule:hb:")]


def test_homebrew_if_it_fails_effects_use_the_target():
    eff = effect(affects="check", does="fail add", count=1, sides=8, choice=True)
    a, _ = make(feats=["Second Wind of Fate"], lookups=Lookups(feat=feat_lookup(**{"Second Wind of Fate": [eff]})))
    key = [o.key for o in {r.key: r for r in a.rolls()}["check:STR"].options if o.key.startswith("rule:hb:")][0]
    out = run(a, "check:STR", {key: True, "target": 15})
    assert dict(out.views[0].facts)["Chance to reach 15"] != "30.0%"


# ----------------------------------------------------------------------------- species, class and subclass features

def test_species_traits_and_class_features_apply_when_the_character_has_them():
    trait = SimpleNamespace(name="Keen Senses", roll_effects=[effect(does="bonus", value=2, limit="Perception")])
    lineage = SimpleNamespace(name="Skyborn", traits=[trait])
    feature = SimpleNamespace(title="Fleet", roll_effects=[effect(affects="initiative", does="bonus", value=3)],
                              is_subclass_feature=False)
    sub_feature = SimpleNamespace(title="Storm Step", level=5, roll_effects=[effect(affects="save", does="advantage",
                                                                                limit="DEX")])
    cdef = SimpleNamespace(levels={3: SimpleNamespace(abilities=[feature])},
                           subclasses=[SimpleNamespace(name="Path of Storms", features=[sub_feature])],
                           compat_subclasses=[])
    lookups = Lookups(lineage=lambda n: lineage if n == "Skyborn" else None,
                      class_def=lambda n: cdef if n == "Stormer" else None)
    a, _ = make(classes=(("Stormer", 5),), lineage="Skyborn", lookups=lookups, subclass="Path of Storms")
    assert mean(run(a, "skill:PERCEPTION")) == pytest.approx(12.5)
    assert mean(run(a, "initiative")) == pytest.approx(13.5)
    assert mean(run(a, "save:DEX")) == pytest.approx(13.825)
    low, _ = make(classes=(("Stormer", 2),), lineage="Human", lookups=lookups, subclass="Path of Storms")
    assert mean(run(low, "initiative")) == pytest.approx(10.5)               # level 3 feature, level 2 character
    assert mean(run(low, "save:DEX")) == pytest.approx(10.5)
    wrong_path, _ = make(classes=(("Stormer", 5),), lookups=lookups, subclass="Path of Calm")
    assert mean(run(wrong_path, "save:DEX")) == pytest.approx(10.5)


# ----------------------------------------------------------------------------- damage

def test_homebrew_damage_effects_for_weapons_and_spells():
    weapon = effect(affects="weapon damage", does="extra damage", count=1, sides=6, limit="fire, melee", once=True)
    spell = effect(affects="spell damage", does="extra damage", count=0, value=0, scales="CHA modifier", limit="evocation")
    lookups = Lookups(feat=feat_lookup(**{"Flame Touched": [weapon, spell]}),
                      spell={"Fire Bolt": SimpleNamespace(name="Fire Bolt", level=0, tags=["Evocation", "Fire"],
                                                          description="Make a ranged spell attack. On a hit, the "
                                                                      "target takes 1d10 Fire damage.")}.get)
    a, ch = make(feats=["Flame Touched"], lookups=lookups, scores={AbilityScore.CHARISMA: 16},
                 attacks=[{"name": "Torch", "attack_bonus": "+5", "damage": "1d4+2 fire"},
                          {"name": "Dagger", "attack_bonus": "+5", "damage": "1d4+2 piercing"}])
    ch.known_spells = ["Fire Bolt"]
    normal = lambda key: float(dict(run(a, key, {"target": 1}).views[1].facts)["Normal hit"])
    assert normal("attack:0") == pytest.approx(4.5 + 3.5)                    # fire melee: +1d6
    assert normal("attack:1") == pytest.approx(4.5)                          # piercing: not covered
    spell_hit = float(dict(run(a, "spell:Fire Bolt", {"target": 1}).views[1].facts)["Average when it hits"])
    assert spell_hit == pytest.approx(8.789, abs=0.01)                  # (5.5 + 3 CHA once), with the 5% crits mixed in


# ----------------------------------------------------------------------------- magic items

def item_lookup(**items):
    return lambda name: SimpleNamespace(description="", type="Wondrous Item", rarity="Rare", requires_attunement=True,
                                        attunement_optional=False, roll_effects=items[name]) if name in items else None


def test_a_homebrew_magic_item_says_what_it_does():
    effects = [effect(affects="save", does="bonus", value=2),
               effect(affects="item spell attack", does="bonus", value=1),
               effect(affects="item spell dc", does="bonus", value=1),
               effect(affects="item set ability", does="set", value=19, limit="CON"),
               effect(affects="weapon damage", does="extra damage", count=1, sides=4, choice=True)]
    lookups = Lookups(magic_item=item_lookup(**{"Warden's Torc": effects}))
    sheet_item = {"name": "Warden's Torc", "attuned": True, "requires_attunement": True}
    a, _ = make(lookups=lookups, magic_items=[sheet_item], scores={AbilityScore.CONSTITUTION: 10})
    assert mean(run(a, "save:WIS")) == pytest.approx(12.5)
    assert mean(run(a, "save:CON")) == pytest.approx(10.5 + 4 + 2)                # CON 19 and the +2
    assert a.ctx.spell_attack_bonus("INT") == a.ctx.prof + a.ctx.mod("INT") + 1
    assert a.ctx.spell_dc("INT") == 8 + a.ctx.prof + a.ctx.mod("INT") + 1
    off, _ = make(lookups=lookups, magic_items=[dict(sheet_item, attuned=False)])
    assert mean(run(off, "save:WIS")) == pytest.approx(10.5)
    assert [r[:3] for r in a.item_report()][0][:2] == ("Warden's Torc", True)


def test_homebrew_effects_survive_the_database_round_trip():
    from feat import Feat, get_feat_manager
    from magic_item import MagicItem, get_magic_item_manager
    eff = effect(does="advantage", limit="Stealth", choice=True)
    manager = get_feat_manager()
    name = "Roll Effects Round Trip Feat"
    manager.add_feat(Feat(name=name, description="x", is_official=False, is_custom=True, roll_effects=[eff]))
    assert manager.get_feat(name).roll_effects == [eff]
    manager.update_feat(name, Feat(name=name, description="y", is_official=False, is_custom=True, roll_effects=[]))
    assert manager.get_feat(name).roll_effects == []
    manager.delete_feat(name)
    items = get_magic_item_manager()
    iname = "Roll Effects Round Trip Item"
    items.add_item(MagicItem(name=iname, is_official=False, is_custom=True, roll_effects=[eff]))
    assert items.get_item(iname).roll_effects == [eff]
    items.delete_item(iname)


def test_traits_and_class_features_keep_their_effects_in_dict_form():
    from character_class import ClassAbility, SubclassFeature
    from lineage import LineageTrait
    eff = effect(does="advantage", limit="Stealth")
    assert LineageTrait.from_dict(LineageTrait("T", "d", [eff]).to_dict()).roll_effects == [eff]
    assert ClassAbility.from_dict(ClassAbility("A", "d", roll_effects=[eff]).to_dict()).roll_effects == [eff]
    assert SubclassFeature.from_dict(SubclassFeature(3, "S", "d", roll_effects=[eff]).to_dict()).roll_effects == [eff]
    assert "roll_effects" not in ClassAbility("A").to_dict()                   # official content stays unchanged


# ----------------------------------------------------------------------------- the editors

def test_the_effect_form_builds_and_validates_an_effect(tk_root):
    from ui.roll_effects_editor import RollEffectDialog
    import roll_effects as RE
    dialog = RollEffectDialog(tk_root)
    dialog.affects_menu.set(RE.AFFECTS["save"])
    dialog._affects_changed()
    dialog.limit_entry.insert(0, "WIS, charmed")
    dialog.does_menu.set(RE.DOES["fail add"])
    dialog._does_changed()
    dialog.count_entry.delete(0, "end")
    dialog.count_entry.insert(0, "2")
    dialog.sides_entry.delete(0, "end")
    dialog.sides_entry.insert(0, "6")
    dialog.choice_var.set(True)
    dialog.default_var.set(True)
    dialog._preview()
    assert "If the roll fails: add dice (2d6)" in dialog.preview.cget("text") and not dialog.error.cget("text")
    dialog._save()
    assert dialog.result["affects"] == "save" and dialog.result["does"] == "fail add"
    assert dialog.result["count"] == 2 and dialog.result["sides"] == 6 and dialog.result["default_on"] is True
    assert RE.validate(dialog.result) == ""
    bad = RollEffectDialog(tk_root)
    bad.does_menu.set(RE.DOES["dice"])
    bad._does_changed()
    bad.count_entry.delete(0, "end")
    bad.count_entry.insert(0, "0")
    bad._save()
    assert bad.result is None and "Dice need" in bad.error.cget("text")
    dialog.destroy()
    bad.destroy()


def test_item_only_effects_are_offered_for_magic_items_only(tk_root):
    from ui.roll_effects_editor import RollEffectDialog
    import roll_effects as RE
    plain = RollEffectDialog(tk_root, None, False)
    item = RollEffectDialog(tk_root, None, True)
    assert RE.AFFECTS["item set ability"] not in plain.affects_menu.cget("values")
    assert RE.AFFECTS["item set ability"] in item.affects_menu.cget("values")
    plain.destroy()
    item.destroy()


def test_the_effects_list_adds_edits_and_removes(tk_root, monkeypatch):
    from ui.roll_effects_editor import RollEffectsEditor
    editor = RollEffectsEditor(tk_root, [effect(does="advantage", limit="Stealth")])
    answers = iter([effect(does="bonus", value=2, limit="Perception"), None, effect(does="bonus", value=5)])
    monkeypatch.setattr(editor, "_ask", lambda current: next(answers))
    editor._add()
    assert len(editor.get()) == 2
    editor._add()                                           # cancelled: nothing changes
    assert len(editor.get()) == 2
    editor._edit(0)
    assert editor.get()[0]["value"] == 5 and editor.get()[1]["limit"] == "Perception"
    editor._remove(1)
    assert [e["limit"] for e in editor.get()] == [""]
    editor.destroy()


def test_the_feat_editor_saves_roll_effects(tk_root):
    from feat import Feat
    from ui.feats_view import FeatEditorDialog
    eff = effect(does="advantage", limit="Stealth")
    old = Feat(name="Sneaky", description="You are sneaky.", is_official=False, is_custom=True, roll_effects=[eff])
    dialog = FeatEditorDialog(tk_root, "Edit", old)
    assert dialog.roll_editor.get() == [eff]
    dialog.roll_editor.set([eff, effect(does="bonus", value=1)])
    dialog._save()
    assert [e["does"] for e in dialog.result.roll_effects] == ["advantage", "bonus"]
    dialog.destroy()


def test_every_editor_carries_roll_effects(tk_root):
    from character_class import ClassAbility, SubclassFeature
    from lineage import Lineage, LineageTrait, get_lineage_manager
    from magic_item import MagicItem
    from ui.class_editor import FeatureEditorDialog, SubclassFeatureEditorDialog
    from ui.lineages_view import LineageEditorDialog
    from ui.magic_item_view import MagicItemEditorDialog
    eff = effect(does="advantage", limit="Stealth")
    item = MagicItemEditorDialog(tk_root, "Edit", MagicItem(name="Cap", description="x", roll_effects=[eff]))
    assert item.roll_editor.get() == [eff] and item.roll_editor.allow_item_effects
    item._save()
    assert item.result.roll_effects == [eff]
    item.destroy()
    lineage = Lineage(name="Skyborn", traits=[LineageTrait("Keen", "Sharp eyes.", [eff]), LineageTrait("Plain", "x")])
    editor = LineageEditorDialog(tk_root, get_lineage_manager(), lineage)
    editor.name_entry.delete(0, "end")
    editor.name_entry.insert(0, "Skyborn Roll Effects Test")
    saved = [t._roll_editor.get() for _n, _d, t in editor._trait_entries]
    assert saved == [[eff], []]
    editor._save()
    assert [t.roll_effects for t in editor.result.traits] == [[eff], []]
    get_lineage_manager().remove_lineage("Skyborn Roll Effects Test")
    editor.destroy()
    feature = FeatureEditorDialog(tk_root, "Edit", ClassAbility("Fleet", "Fast.", roll_effects=[eff]))
    feature._on_save()
    assert feature.result.roll_effects == [eff]
    feature.destroy()
    sub = SubclassFeatureEditorDialog(tk_root, 3, SubclassFeature(3, "Storm Step", "Zap.", roll_effects=[eff]))
    sub._on_save()
    assert sub.result.roll_effects == [eff]
    sub.destroy()
