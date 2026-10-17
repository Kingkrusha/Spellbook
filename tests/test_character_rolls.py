"""Character roll analysis: features applied to the numbers the sheet already shows."""

from types import SimpleNamespace

import pytest

from character import CharacterSpellList, ClassLevel
from character_rolls import (CharacterAnalyzer, Lookups, SpellInfo, parse_bonus, parse_damage, parse_spell,
                             _outcomes)
from character_sheet import AbilityScore, CharacterSheet, Skill
from dice_analyzer import DiceError, DiceTerm, Dist
from spell import CharacterClass


def make(classes, lineage="Human", feats=(), scores=None, prof=2, attacks=(), skills=None, subclass=None,
         lookups=None, manual=None, magic_items=(), disabled=None):
    ch = CharacterSpellList(name="T", lineage=lineage,
                            classes=[ClassLevel.from_dict({"class": n, "level": lv, "subclass": ""})
                                     for n, lv in classes])
    for cl in ch.classes:
        for key, value in (subclass or {}).items():
            if key in cl.get_class_name():
                cl.subclass = value
    ch.feats = list(feats)
    sheet = CharacterSheet(character_name="T")
    sheet.proficiency_bonus = prof
    for ab, v in (scores or {}).items():
        sheet.ability_scores.set(ab, v)
    for sk, lv in (skills or {}).items():
        sheet.skills.set(sk, lv)
    sheet.attacks = list(attacks)
    sheet.magic_items = list(magic_items)
    return CharacterAnalyzer(ch, sheet, lookups, manual, disabled), ch, sheet


def roll(analyzer, key, state=None):
    return {r.key: r for r in analyzer.rolls()}[key].analyze(state or {})


def main(analysis):
    return analysis.views[0].dist


# ----------------------------------------------------------------------------- checks and skills

def test_a_plain_proficient_skill_matches_the_sheet():
    a, ch, sheet = make([("Fighter", 3)], scores={AbilityScore.STRENGTH: 16}, prof=2,
                        skills={Skill.ATHLETICS: 1})
    d = main(roll(a, "skill:ATHLETICS"))
    assert d.mean() == pytest.approx(10.5 + sheet.get_skill_bonus(Skill.ATHLETICS))
    assert d.support() == (1 + 5, 20 + 5)


def test_expertise_doubles_proficiency():
    a, _, sheet = make([("Rogue", 3)], scores={AbilityScore.DEXTERITY: 14}, prof=2, skills={Skill.STEALTH: 2})
    assert main(roll(a, "skill:STEALTH")).mean() == pytest.approx(10.5 + 2 + 4)


def test_jack_of_all_trades_adds_half_proficiency_only_where_not_proficient():
    a, *_ = make([("Bard", 2)], prof=3, skills={Skill.PERSUASION: 1})
    assert main(roll(a, "skill:ARCANA")).mean() == pytest.approx(10.5 + 1)        # 3 // 2
    assert main(roll(a, "skill:PERSUASION")).mean() == pytest.approx(10.5 + 3)    # proficiency, no half on top
    plain, *_ = make([("Fighter", 2)], prof=3)
    assert main(roll(plain, "skill:ARCANA")).mean() == pytest.approx(10.5)


def test_reliable_talent_floors_the_d20_for_proficient_skills_only():
    a, *_ = make([("Rogue", 7)], prof=3, skills={Skill.STEALTH: 1})
    stealth = main(roll(a, "skill:STEALTH"))
    assert stealth.support()[0] == 10 + 3
    assert stealth.mean() == pytest.approx(12.75 + 3)
    assert main(roll(a, "skill:ARCANA")).support()[0] == 1
    low, *_ = make([("Rogue", 6)], prof=3, skills={Skill.STEALTH: 1})
    assert main(roll(low, "skill:STEALTH")).support()[0] == 1 + 3


def test_halfling_luck_rerolls_a_one():
    a, *_ = make([("Fighter", 1)], lineage="Halfling")
    assert main(roll(a, "check:STR")).mean() == pytest.approx(10.975)
    human, *_ = make([("Fighter", 1)], lineage="Human")
    assert main(roll(human, "check:STR")).mean() == pytest.approx(10.5)


def test_halfling_rogue_combines_luck_and_reliable_talent_in_the_right_order():
    a, *_ = make([("Rogue", 7)], lineage="Halfling", skills={Skill.STEALTH: 1})
    d = main(roll(a, "skill:STEALTH"))
    # the 1 is rerolled (a second 1 stands), then anything under 10 becomes 10:
    # P(10) = P(1) + 9 * P(2..9, 10 each) = 1/400 + 9 * (1/20 + 1/400)
    assert d.pmf(10 + 2) == pytest.approx(1 / 400 + 9 * (1 / 20 + 1 / 400))


def test_advantage_and_disadvantage_cancel():
    a, *_ = make([("Barbarian", 7)], scores={AbilityScore.DEXTERITY: 10})
    adv = roll(a, "skill:ACROBATICS", {"mode": "Advantage"})
    assert main(adv).mean() == pytest.approx(13.825)
    # Danger Sense (advantage on DEX saves) against disadvantage chosen by the user: a straight roll
    s = roll(a, "save:DEX", {"mode": "Disadvantage"})
    assert main(s).mean() == pytest.approx(10.5)
    assert any("cancel" in n for n in s.notes)


def test_bonus_dice_add_and_subtract_and_stack():
    a, *_ = make([("Fighter", 1)])
    inspired = [{"label": "Bardic Inspiration", "sign": 1, "count": 1, "sides": 8},
                {"label": "Guidance", "sign": 1, "count": 1, "sides": 4}]
    assert main(roll(a, "check:STR", {"bonus_dice": inspired})).mean() == pytest.approx(10.5 + 4.5 + 2.5)
    sliver = inspired + [{"label": "Mind Sliver", "sign": -1, "count": 1, "sides": 4}]
    d = main(roll(a, "check:STR", {"bonus_dice": sliver}))
    assert d.mean() == pytest.approx(10.5 + 4.5)                     # +d8 +d4 -d4
    assert d.support() == (1 + 1 + 1 - 4, 20 + 8 + 4 - 1)
    two = main(roll(a, "check:STR", {"bonus_dice": [{"count": 2, "sides": 6, "sign": 1}]}))
    assert two.mean() == pytest.approx(10.5 + 7)
    # unusable entries are ignored rather than crashing
    assert main(roll(a, "check:STR", {"bonus_dice": [{"count": "x"}, None, {"count": 0, "sides": 6}]})).mean() == pytest.approx(10.5)


def test_a_skill_can_be_based_on_a_different_ability():
    a, *_ = make([("Fighter", 1)], prof=2, scores={AbilityScore.STRENGTH: 18, AbilityScore.CHARISMA: 8},
                 skills={Skill.INTIMIDATION: 1})
    default = main(roll(a, "skill:INTIMIDATION"))
    assert default.mean() == pytest.approx(10.5 - 1 + 2)                       # CHA -1, proficiency +2
    swapped = roll(a, "skill:INTIMIDATION", {"ability": "STR"})
    assert main(swapped).mean() == pytest.approx(10.5 + 4 + 2)
    assert any("Strength instead of Charisma" in n for n in swapped.notes)


def test_rage_lets_a_barbarian_use_strength_for_primal_knowledge_skills():
    a, *_ = make([("Barbarian", 3)], prof=2, scores={AbilityScore.STRENGTH: 18, AbilityScore.DEXTERITY: 10},
                 skills={Skill.STEALTH: 1})
    calm = roll(a, "skill:STEALTH")
    raging = roll(a, "skill:STEALTH", {"rage": True})
    assert main(calm).mean() == pytest.approx(10.5 + 0 + 2)
    # Strength +4 and advantage on Strength checks while raging
    assert main(raging).mean() == pytest.approx(13.825 + 4 + 2)
    assert any("Primal Knowledge" in n for n in raging.notes)
    # not for other skills, and not before level 3
    assert main(roll(a, "skill:ARCANA", {"rage": True})).mean() == pytest.approx(10.5)
    low, *_ = make([("Barbarian", 2)], scores={AbilityScore.STRENGTH: 18}, skills={Skill.STEALTH: 1})
    assert main(roll(low, "skill:STEALTH", {"rage": True})).mean() == pytest.approx(10.5 + 2)
    # picking an ability by hand wins over the Rage swap
    manual = roll(a, "skill:STEALTH", {"rage": True, "ability": "CON"})
    assert main(manual).mean() == pytest.approx(10.5 + 0 + 2)


def test_bladesong_gives_acrobatics_advantage_and_concentration_bonus():
    a, *_ = make([("Wizard", 3)], scores={AbilityScore.INTELLIGENCE: 18, AbilityScore.CONSTITUTION: 10},
                 subclass={"Wizard": "Bladesinging"}, prof=2,
                 lookups=Lookups(class_def=lambda n: SimpleNamespace(spellcasting_ability="INT")))
    assert main(roll(a, "skill:ACROBATICS", {"bladesong": True})).mean() == pytest.approx(13.825)
    off = roll(a, "save:CON:concentration")
    on = roll(a, "save:CON:concentration", {"bladesong": True})
    assert main(on).mean() - main(off).mean() == pytest.approx(4)         # +INT modifier


def test_paladin_aura_of_protection_adds_charisma_to_saves():
    a, *_ = make([("Paladin", 6)], scores={AbilityScore.CHARISMA: 16, AbilityScore.WISDOM: 10})
    assert main(roll(a, "save:WIS")).mean() == pytest.approx(10.5 + 3)


def test_champion_remarkable_athlete_2014_adds_half_proficiency_to_physical_checks():
    a, *_ = make([("Fighter (Legacy)", 7)], subclass={"Fighter": "Champion"}, prof=3)
    assert main(roll(a, "skill:ACROBATICS")).mean() == pytest.approx(10.5 + 2)    # half of 3, rounded up
    assert main(roll(a, "skill:ARCANA")).mean() == pytest.approx(10.5)            # INT: not covered
    early, *_ = make([("Fighter (Legacy)", 6)], subclass={"Fighter": "Champion"}, prof=3)
    assert main(roll(early, "skill:ACROBATICS")).mean() == pytest.approx(10.5)


def test_champion_remarkable_athlete_2024_is_advantage_on_athletics_and_initiative():
    a, *_ = make([("Fighter", 3)], subclass={"Fighter": "Champion"}, prof=2)
    assert main(roll(a, "skill:ATHLETICS")).mean() == pytest.approx(13.825)
    assert main(roll(a, "initiative")).mean() == pytest.approx(13.825)
    assert main(roll(a, "skill:ACROBATICS")).mean() == pytest.approx(10.5)


def test_alert_adds_proficiency_to_initiative():
    a, *_ = make([("Fighter", 1)], feats=["Alert"], prof=3, scores={AbilityScore.DEXTERITY: 14})
    assert main(roll(a, "initiative")).mean() == pytest.approx(10.5 + 2 + 3)
    old, *_ = make([("Fighter", 1)], feats=["Alert (Legacy)"], prof=3, scores={AbilityScore.DEXTERITY: 14})
    assert main(roll(old, "initiative")).mean() == pytest.approx(10.5 + 2 + 5)


def test_manual_features_can_be_switched_on():
    plain, *_ = make([("Fighter", 5)])
    assert main(roll(plain, "check:STR")).mean() == pytest.approx(10.5)
    manual, *_ = make([("Fighter", 5)], manual={"halfling_luck", "improved_critical"})
    assert main(roll(manual, "check:STR")).mean() == pytest.approx(10.975)
    report = {fid: src for fid, _label, src in manual.feature_report()}
    assert report["halfling_luck"] == "manual" and report["lucky"] == ""


# ----------------------------------------------------------------------------- attacks

SWORD = {"name": "Longsword", "attack_bonus": "+5", "damage": "1d8+3 slashing"}


def test_hit_chance_and_average_damage_by_hand():
    a, *_ = make([("Fighter", 1)], attacks=[SWORD])
    an = roll(a, "attack:0", {"target": 15})
    miss = 9 / 20
    crit = 1 / 20
    normal = 10 / 20                           # a 10 to a 19 hits, a 20 is a crit
    per_attack = normal * (4.5 + 3) + crit * (9 + 3)
    assert next(v for v in an.views if v.key == "per_attack").dist.mean() == pytest.approx(per_attack)
    assert next(v for v in an.views if v.key == "damage").dist.mean() == pytest.approx(per_attack / (1 - miss))


def test_natural_one_always_misses_and_natural_twenty_always_hits():
    nat = Dist.uniform(20)
    miss, hit, crit = _outcomes(nat, Dist.point(30), 10, 20)       # +30 vs AC 10
    assert miss == pytest.approx(1 / 20) and crit == pytest.approx(1 / 20) and hit == pytest.approx(18 / 20)
    miss, hit, crit = _outcomes(nat, Dist.point(0), 40, 20)        # cannot hit an AC of 40 except on a 20
    assert hit == 0 and crit == pytest.approx(1 / 20) and miss == pytest.approx(19 / 20)


def test_champion_crits_on_nineteen():
    a, *_ = make([("Fighter", 3)], subclass={"Fighter": "Champion"}, attacks=[SWORD])
    an = roll(a, "attack:0", {"target": 15})
    assert an.views[0].facts[1] == ("Critical hit", "10.0%")


def test_great_weapon_master_2024_adds_proficiency_to_heavy_weapon_damage():
    a, *_ = make([("Fighter", 4)], feats=["Great Weapon Master"], prof=3,
                 attacks=[{"name": "Greatsword", "attack_bonus": "+6", "damage": "2d6+4 slashing"}],
                 lookups=Lookups(equipment=lambda n: SimpleNamespace(properties=[{"name": "Heavy"}])))
    plain = roll(a, "attack:0", {"target": 12, "heavy_mastery": False, "attacks": 1})
    mastered = roll(a, "attack:0", {"target": 12, "heavy_mastery": True, "attacks": 1})
    gain = (next(v for v in mastered.views if v.key == "damage").dist.mean()
            - next(v for v in plain.views if v.key == "damage").dist.mean())
    assert gain == pytest.approx(3)                          # +3 on every hit, critical or not (a flat bonus is not doubled)


def test_great_weapon_master_2014_trades_accuracy_for_damage():
    a, *_ = make([("Fighter", 4)], feats=["Great Weapon Master (Legacy)"], prof=3,
                 attacks=[{"name": "Greatsword", "attack_bonus": "+6", "damage": "2d6+4 slashing"}])
    off = roll(a, "attack:0", {"target": 14, "attacks": 1})
    on = roll(a, "attack:0", {"target": 14, "attacks": 1, "power_attack": True})
    hit_off = float(off.views[0].facts[0][1].rstrip("%"))
    hit_on = float(on.views[0].facts[0][1].rstrip("%"))
    assert hit_on == pytest.approx(hit_off - 25)
    assert next(v for v in on.views if v.key == "damage").dist.mean() > next(v for v in off.views if v.key == "damage").dist.mean() + 9


def test_great_weapon_fighting_raises_the_average_of_a_greataxe_die():
    a, *_ = make([("Fighter", 1)], manual={"great_weapon_fighting"},
                 attacks=[{"name": "Greataxe", "attack_bonus": "+5", "damage": "1d12+3"}])
    base = roll(a, "attack:0", {"gwf": False, "target": 5})
    gwf = roll(a, "attack:0", {"gwf": True, "target": 5})
    pick = lambda an: next(v for v in an.views if v.key == "damage").dist.mean()
    assert pick(gwf) > pick(base)


def test_sneak_attack_is_added_once_per_turn():
    a, *_ = make([("Rogue", 5)], scores={AbilityScore.DEXTERITY: 16}, prof=3,
                 attacks=[{"name": "Shortsword", "attack_bonus": "+6", "damage": "1d6+3"}])
    off = roll(a, "attack:0", {"target": 1, "attacks": 2})
    on = roll(a, "attack:0", {"target": 1, "attacks": 2, "sneak": True})
    turn = lambda an: next(v for v in an.views if v.key == "per_turn").dist.mean()
    # AC 1: only the natural 1 misses. Sneak Attack (3d6) lands on the first hit, never twice.
    gain = turn(on) - turn(off)
    assert 10.5 * 0.9 < gain < 10.5 * 1.3
    assert gain < 2 * 10.5 * 0.9


def test_savage_attacker_rolls_the_weapon_dice_twice():
    a, *_ = make([("Fighter", 1)], feats=["Savage Attacker"],
                 attacks=[{"name": "Greatsword", "attack_bonus": "+5", "damage": "2d6+3"}])
    off = roll(a, "attack:0", {"savage": False, "target": 5})
    on = roll(a, "attack:0", {"savage": True, "target": 5})
    pick = lambda an: next(v for v in an.views if v.key == "damage").dist.mean()
    assert pick(on) > pick(off) + 1


def test_lucky_2024_gives_advantage_and_2014_an_extra_d20():
    a, *_ = make([("Fighter", 1)], feats=["Lucky"])
    assert main(roll(a, "check:STR")).mean() == pytest.approx(10.5)
    assert main(roll(a, "check:STR", {"rule:lucky_2024": True})).mean() == pytest.approx(13.825)    # a Luck Point = Advantage
    old, *_ = make([("Fighter", 1)], feats=["Lucky (Legacy)"])
    assert main(roll(old, "check:STR", {"rule:lucky_2014": True})).mean() == pytest.approx(13.825)  # an extra d20
    # with Advantage already, the 2024 Luck Point adds nothing but the 2014 one is a third d20
    assert main(roll(a, "check:STR", {"rule:lucky_2024": True, "mode": "Advantage"})).mean() == pytest.approx(13.825)
    assert main(roll(old, "check:STR", {"rule:lucky_2014": True, "mode": "Advantage"})).mean() == pytest.approx(15.4875)


def test_rage_adds_damage_and_strength_advantage():
    a, *_ = make([("Barbarian", 1)], attacks=[SWORD])
    off = roll(a, "attack:0", {"target": 5})
    on = roll(a, "attack:0", {"target": 5, "rage": True})
    pick = lambda an: next(v for v in an.views if v.key == "damage").dist.mean()
    assert pick(on) - pick(off) == pytest.approx(2)
    assert main(roll(a, "check:STR", {"rage": True})).mean() == pytest.approx(13.825)


def test_elven_accuracy_only_with_advantage():
    a, *_ = make([("Ranger", 1)], feats=["Elven Accuracy"], attacks=[SWORD])
    plain = roll(a, "attack:0", {"target": 15, "attacks": 1})
    adv = roll(a, "attack:0", {"target": 15, "attacks": 1, "mode": "Advantage"})
    nothing, *_ = make([("Ranger", 1)], attacks=[SWORD])
    adv_no_feat = roll(nothing, "attack:0", {"target": 15, "attacks": 1, "mode": "Advantage"})
    hit = lambda an: float(an.views[0].facts[0][1].rstrip("%"))
    assert hit(plain) < hit(adv_no_feat) < hit(adv)


def test_attack_entries_without_numbers_are_skipped_and_damage_is_optional():
    a, *_ = make([("Fighter", 1)], attacks=[{"name": "Mystery", "attack_bonus": "", "damage": ""},
                                            {"name": "Poke", "attack_bonus": "+4", "damage": ""}])
    keys = [r.key for r in a.rolls() if r.group == "Attacks"]
    assert keys == ["attack:1"]
    assert [v.key for v in roll(a, "attack:1").views] == ["attack"]


def test_damage_and_bonus_parsing():
    terms, flat, words = parse_damage("2d6 + 4 slashing + 1d4 fire (versatile 1d10)")
    assert [(t.count, t.sides) for t in terms] == [(2, 6), (1, 4)] and flat == 4
    assert "slashing" in words and "fire" in words
    assert parse_damage("5")[1] == 5 and parse_damage("1d8-1")[1] == -1
    with pytest.raises(DiceError):
        parse_damage("lots")
    assert parse_bonus("+7") == 7 and parse_bonus("-1") == -1 and parse_bonus("4 (with bless)") == 4
    assert parse_bonus("") is None


# ----------------------------------------------------------------------------- spells

def spell(name, level, text):
    return SimpleNamespace(name=name, level=level, description=text)


FIREBALL = spell("Fireball", 3, "Each creature in a 20-foot-radius Sphere makes a Dexterity saving throw. "
                 "On a failed save, a target takes 8d6 Fire damage, or half as much damage on a successful one.\\"
                 "Using a Higher-Level Spell Slot. The damage increases by 1d6 for each spell slot level above 3.")
FIRE_BOLT = spell("Fire Bolt", 0, "Make a ranged spell attack. On a hit, the target takes 1d10 Fire damage.\\"
                  "Cantrip Upgrade. The damage increases by 1d10 when you reach levels 5 (2d10), 11 (3d10), and 17 (4d10).")
CURE = spell("Cure Wounds", 1, "A creature you touch regains a number of Hit Points equal to 2d8 plus your "
             "spellcasting ability modifier.\\Using a Higher-Level Spell Slot. The healing increases by 2d8 for each "
             "spell slot level above 1.")


def test_spell_descriptions_are_read():
    f = parse_spell(FIREBALL)
    assert f.save == "DEX" and f.half and f.dice == (8, 6, 0) and f.damage_type == "fire"
    assert f.slot_step == (1, 6, 3)
    b = parse_spell(FIRE_BOLT)
    assert b.attack and b.dice == (1, 10, 0) and [t[0] for t in b.cantrip_dice] == [5, 11, 17]
    c = parse_spell(CURE)
    assert c.healing and c.dice == (2, 8, 0) and c.add_mod
    assert parse_spell(spell("Light", 0, "A rod glows brightly.")) is None


def caster(lookup_spells, level=5, **kw):
    spells = {s.name: s for s in lookup_spells}
    a, ch, sheet = make([("Wizard", level)], scores={AbilityScore.INTELLIGENCE: 18}, prof=3,
                        lookups=Lookups(spell=spells.get,
                                        class_def=lambda n: SimpleNamespace(spellcasting_ability="INT")), **kw)
    ch.known_spells = list(spells)
    return a


def test_fireball_uses_the_sheets_save_dc_and_slot_scaling():
    a = caster([FIREBALL])
    an = roll(a, "spell:Fireball", {"target": 0})
    failed = next(v for v in an.views if v.key == "failed")
    assert failed.dist.mean() == pytest.approx(28) and ("Save DC", "15") in failed.facts       # 8 + 3 + 4
    upcast = roll(a, "spell:Fireball", {"target": 0, "slot": "5"})
    assert next(v for v in upcast.views if v.key == "failed").dist.mean() == pytest.approx(35)
    expected = next(v for v in an.views if v.key == "expected").dist.mean()
    fail = 1 - 6 / 20          # d20 + 0 must reach 15: 6 values (15..20); the target fails otherwise
    assert expected == pytest.approx(fail * 28 + (1 - fail) * 14, abs=0.5)


def test_cantrip_damage_grows_with_character_level():
    for level, dice in ((1, 1), (5, 2), (11, 3), (17, 4)):
        a = caster([FIRE_BOLT], level=level)
        an = roll(a, "spell:Fire Bolt", {"target": 10})
        assert an.formula.startswith(f"{dice}d10")


def test_healing_adds_the_spellcasting_modifier():
    a = caster([CURE])
    an = roll(a, "spell:Cure Wounds")
    assert an.views[0].dist.mean() == pytest.approx(9 + 4)
    assert roll(a, "spell:Cure Wounds", {"slot": "3"}).views[0].dist.mean() == pytest.approx(27 + 4)    # 6d8 + 4


def test_spell_attack_uses_proficiency_plus_ability():
    a = caster([FIRE_BOLT], level=1)
    an = roll(a, "spell:Fire Bolt", {"target": 15})
    assert an.views[0].dist.mean() == pytest.approx(10.5 + 7)        # prof 3 + INT 4
    assert an.views[0].facts[0][1] == "65.0%"                          # needs 8 or more


def test_a_character_without_spellcasting_still_gets_spell_rolls_from_the_list():
    a, ch, _ = make([("Fighter", 1)], lookups=Lookups(spell={"Fire Bolt": FIRE_BOLT}.get))
    ch.known_spells = ["Fire Bolt"]
    assert any(r.key == "spell:Fire Bolt" for r in a.rolls())


def test_real_spell_database_entries_parse():
    from spell_manager import SpellManager
    sm = SpellManager()
    sm.load_spells()
    for name, check in (("Fireball", lambda i: i.save == "DEX" and i.dice == (8, 6, 0)),
                        ("Fire Bolt", lambda i: i.attack and i.dice == (1, 10, 0) and len(i.cantrip_dice) == 3),
                        ("Cure Wounds", lambda i: i.healing and i.add_mod)):
        s = sm.get_spell(name)
        assert s is not None, name
        assert check(parse_spell(s)), name


def test_every_roll_for_a_busy_character_evaluates():
    from spell_manager import SpellManager
    sm = SpellManager()
    sm.load_spells()
    names = ["Fireball", "Fire Bolt", "Eldritch Blast", "Magic Missile", "Cure Wounds", "Scorching Ray",
             "Sacred Flame", "Guiding Bolt", "Burning Hands"]
    a, ch, _ = make([("Wizard", 11), ("Rogue", 7)], lineage="Halfling", feats=["Lucky", "Alert"],
                    scores={AbilityScore.INTELLIGENCE: 20, AbilityScore.DEXTERITY: 16}, prof=4,
                    attacks=[SWORD], skills={Skill.STEALTH: 2},
                    lookups=Lookups(spell=sm.get_spell, class_def=lambda n: SimpleNamespace(
                        spellcasting_ability="INT" if n == "Wizard" else "")))
    ch.known_spells = names
    for r in a.rolls():
        an = r.analyze({})
        assert an.views and all(v.dist.total() == pytest.approx(1, abs=1e-9) for v in an.views), r.key


# ----------------------------------------------------------------------------- how a roll is made

@pytest.mark.parametrize("mode,mean", [("Normal", 10.5), ("Advantage", 13.825), ("Disadvantage", 7.175),
                                       ("Double advantage", 15.4875), ("Double disadvantage", 5.5125),
                                       ("Emphasis", 11.2)])
def test_every_way_of_rolling_a_d20(mode, mean):
    a, *_ = make([("Fighter", 1)])
    assert main(roll(a, "check:STR", {"mode": mode})).mean() == pytest.approx(mean)


def test_double_advantage_loses_a_level_to_a_disadvantage_and_emphasis_needs_a_plain_roll():
    a, *_ = make([("Barbarian", 7)], scores={AbilityScore.DEXTERITY: 10})
    # Danger Sense (advantage) against the user's Double disadvantage leaves a single disadvantage
    s = roll(a, "save:DEX", {"mode": "Double disadvantage"})
    assert main(s).mean() == pytest.approx(7.175) and any("took one level" in n for n in s.notes)
    both = roll(a, "save:DEX", {"mode": "Emphasis"})                   # Danger Sense gives advantage: emphasis unused
    assert main(both).mean() == pytest.approx(13.825) and any("Emphasis was not used" in n for n in both.notes)
    # advantage from a feature and the user's Double advantage do not add up beyond double
    assert main(roll(a, "save:DEX", {"mode": "Double advantage"})).mean() == pytest.approx(15.4875)


def fact(analysis, view_key, label):
    view = next(v for v in analysis.views if v.key == view_key)
    return dict(view.facts)[label]


def test_if_it_fails_options_use_the_target_number():
    # Indomitable (Fighter 9): reroll a failed save with + Fighter level
    a, *_ = make([("Fighter", 9)], scores={AbilityScore.DEXTERITY: 10})
    plain = roll(a, "save:DEX", {"target": 15})
    used = roll(a, "save:DEX", {"target": 15, "rule:indomitable": True})
    assert fact(plain, "roll", "Chance to reach 15") == "30.0%"
    assert fact(used, "roll", "Chance to reach 15") == "82.5%"                      # 0.3 + 0.7 * P(d20 + 9 >= 15) = 0.3 + 0.7 * 0.75
    # Stroke of Luck turns the failed d20 into a 20
    rogue_, *_ = make([("Rogue", 20)])
    assert fact(roll(rogue_, "check:STR", {"target": 15, "rule:stroke_of_luck": True}), "roll",
                "Chance to reach 15") == "100.0%"
    # Tactical Mind: +1d10 only when it can turn the failure around
    f, *_ = make([("Fighter", 2)])
    tm = roll(f, "check:STR", {"target": 15, "rule:tactical_mind": True})
    assert fact(tm, "roll", "Chance to reach 15") == "57.5%"
    # without a target there is nothing to measure it against
    assert any("target number" in n for n in roll(f, "check:STR", {"target": "", "rule:tactical_mind": True}).notes)


def test_a_missed_attack_can_be_turned_into_a_hit():
    a, *_ = make([("Fighter", 1)], feats=["Boon of Combat Prowess"], attacks=[SWORD])
    plain = roll(a, "attack:0", {"target": 15})
    boon = roll(a, "attack:0", {"target": 15, "rule:boon_of_combat_prowess": True})
    assert fact(plain, "attack", "Chance to hit") == "55.0%" and fact(boon, "attack", "Chance to hit") == "100.0%"


def test_great_weapon_fighting_counts_ones_and_twos_as_three_in_2024_and_rerolls_in_2014():
    attack = [{"name": "Greatsword", "attack_bonus": "+5", "damage": "2d6+4 slashing"}]
    new, *_ = make([("Fighter", 1)], feats=["Great Weapon Fighting"], attacks=attack)
    old, *_ = make([("Fighter", 1)], feats=["Great Weapon Fighting (Legacy)"], attacks=attack)
    none, *_ = make([("Fighter", 1)], attacks=attack)
    normal = lambda a, **kw: float(fact(roll(a, "attack:0", {"target": 1, **kw}), "damage", "Normal hit"))
    assert normal(none) == pytest.approx(11)
    assert normal(new, gwf=True) == pytest.approx(12)                       # a die is 4 on average: (3+3+3+4+5+6)/6
    assert normal(old, gwf=True) == pytest.approx(4 + 2 * (18 / 6 + 7 / 6), abs=0.01)   # reroll 1s and 2s once


# ----------------------------------------------------------------------------- the feature sweep

def test_dragonmark_dice_and_the_greater_mark_do_not_stack():
    a, *_ = make([("Fighter", 1)], feats=["Mark of Finding"])
    assert main(roll(a, "skill:PERCEPTION")).mean() == pytest.approx(10.5 + 2.5)
    assert main(roll(a, "skill:ARCANA")).mean() == pytest.approx(10.5)
    both, *_ = make([("Fighter", 1)], feats=["Mark of Finding", "Greater Mark of Finding"])
    assert main(roll(both, "skill:PERCEPTION")).mean() == pytest.approx(10.5 + 3.5)
    species, *_ = make([("Fighter", 1)], lineage="Human (Mark of Finding)")
    assert main(roll(species, "skill:SURVIVAL")).mean() == pytest.approx(10.5 + 2.5)


def test_fey_wanderer_adds_wisdom_to_charisma_checks():
    a, *_ = make([("Ranger", 3)], subclass={"Ranger": "Fey Wanderer"}, scores={AbilityScore.WISDOM: 16})
    assert main(roll(a, "skill:PERSUASION")).mean() == pytest.approx(10.5 + 3)
    assert main(roll(a, "check:CHA")).mean() == pytest.approx(10.5 + 3)
    assert main(roll(a, "skill:ARCANA")).mean() == pytest.approx(10.5)


def test_species_saving_throw_advantages():
    gnome, *_ = make([("Fighter", 1)], lineage="Gnome")
    assert main(roll(gnome, "save:WIS")).mean() == pytest.approx(13.825)
    assert main(roll(gnome, "save:STR")).mean() == pytest.approx(10.5)
    rock, *_ = make([("Fighter", 1)], lineage="Rock Gnome")                  # the 2014 gnome: only against magic
    assert main(roll(rock, "save:WIS")).mean() == pytest.approx(10.5)
    assert main(roll(rock, "save:WIS", {"save_vs": "Spells and magic"})).mean() == pytest.approx(13.825)
    elf, *_ = make([("Fighter", 1)], lineage="Elf")
    assert main(roll(elf, "save:WIS")).mean() == pytest.approx(10.5)
    assert main(roll(elf, "save:WIS", {"save_vs": "Charmed"})).mean() == pytest.approx(13.825)
    plain, *_ = make([("Fighter", 1)], lineage="Human")
    assert "save_vs" not in [o.key for o in {r.key: r for r in plain.rolls()}["save:WIS"].options]


def test_class_extras_on_weapon_hits():
    sword = [{"name": "Longsword", "attack_bonus": "+5", "damage": "1d8+3 slashing"}]
    normal = lambda a, **kw: float(fact(roll(a, "attack:0", {"target": 1, "attacks": 1, **kw}), "damage", "Normal hit"))
    paladin, *_ = make([("Paladin", 11)], attacks=sword)
    assert normal(paladin) == pytest.approx(7.5 + 4.5)                        # Radiant Strikes
    duelist, *_ = make([("Fighter", 1)], feats=["Dueling"], attacks=sword)
    assert normal(duelist) == pytest.approx(7.5 + 2)
    cleric, *_ = make([("Cleric", 7)], attacks=sword)
    assert normal(cleric) == pytest.approx(7.5 + 4.5)                         # Divine Strike, once per turn
    twice = roll(cleric, "attack:0", {"target": 1, "attacks": 2})
    turn = next(v for v in twice.views if v.key == "per_turn").dist.mean()
    cleric_none, *_ = make([("Fighter", 1)], attacks=sword)
    plain_turn = next(v for v in roll(cleric_none, "attack:0", {"target": 1, "attacks": 2}).views
                      if v.key == "per_turn").dist.mean()
    assert 4.0 < turn - plain_turn < 5.0                                      # only one of the two hits gets +1d8
    # the 2014 half-orc rolls an extra weapon die on a melee critical hit
    orc, *_ = make([("Fighter", 1)], lineage="Half-Orc", attacks=sword)
    crit = float(fact(roll(orc, "attack:0", {"target": 1}), "damage", "Critical hit"))
    assert crit == pytest.approx(3 + 4.5 * 3)


def test_legacy_class_names_are_understood():
    barb, *_ = make([("Barbarian (Legacy)", 9)], attacks=[{"name": "Greataxe", "attack_bonus": "+5",
                                                           "damage": "1d12+3 slashing"}])
    crit = float(fact(roll(barb, "attack:0", {"target": 1}), "damage", "Critical hit"))
    assert crit == pytest.approx(3 + 6.5 * 3)                                 # 2d12 doubled + Brutal Critical
    assert main(roll(barb, "save:DEX")).mean() == pytest.approx(13.825)       # Danger Sense


EB_SPELL = SimpleNamespace(name="Eldritch Blast", level=0, tags=["Evocation", "Force"],
                     description="Make a ranged spell attack. On a hit, the target takes 1d10 Force damage.\\"
                                 "Cantrip Upgrade. The spell creates two beams at level 5, three beams at level 11, "
                                 "and four beams at level 17.")
CURE_SPELL = SimpleNamespace(name="Cure Wounds", level=1, tags=["Healing"],
                       description="A creature you touch regains a number of Hit Points equal to 2d8 plus your "
                                   "spellcasting ability modifier.\\Using a Higher-Level Spell Slot. The healing "
                                   "increases by 2d8 for each spell slot level above 1.")
FIRE_BOLT_SPELL = SimpleNamespace(name="Fire Bolt", level=0, tags=["Evocation", "Fire"],
                            description="Make a ranged spell attack. On a hit, the target takes 1d10 Fire damage.")


def spell_caster(classes, spells, scores, ability="CHA", **kw):
    table = {s.name: s for s in spells}
    a, ch, sheet = make(classes, scores=scores, prof=3,
                        lookups=Lookups(spell=table.get,
                                        class_def=lambda n: SimpleNamespace(spellcasting_ability=ability)), **kw)
    ch.known_spells = list(table)
    return a


def test_spell_damage_features():
    scores = {AbilityScore.CHARISMA: 18, AbilityScore.INTELLIGENCE: 18, AbilityScore.WISDOM: 16}
    hit_avg = lambda a, name: float(fact(roll(a, f"spell:{name}", {"target": 1}), "damage", "Average when it hits"))
    warlock = spell_caster([("Warlock", 5)], [EB_SPELL], scores, feats=["Agonizing Blast"])
    plain = spell_caster([("Warlock", 5)], [EB_SPELL], scores)
    assert hit_avg(warlock, "Eldritch Blast") - hit_avg(plain, "Eldritch Blast") == pytest.approx(4, abs=0.2)
    evoker = spell_caster([("Wizard", 10)], [FIRE_BOLT_SPELL], scores, ability="INT", subclass={"Wizard": "Evoker"})
    wizard = spell_caster([("Wizard", 10)], [FIRE_BOLT_SPELL], scores, ability="INT")
    assert hit_avg(evoker, "Fire Bolt") - hit_avg(wizard, "Fire Bolt") == pytest.approx(4, abs=0.2)   # +INT, once
    life = spell_caster([("Cleric", 3)], [CURE_SPELL], scores, ability="WIS", subclass={"Cleric": "Life Domain"})
    assert roll(life, "spell:Cure Wounds").views[0].dist.mean() == pytest.approx(9 + 3 + 2 + 1)    # 2d8 + WIS + 2 + level
    assert roll(life, "spell:Cure Wounds", {"slot": "3"}).views[0].dist.mean() == pytest.approx(27 + 3 + 2 + 3)


def test_empowered_spell_is_better_than_nothing():
    scores = {AbilityScore.CHARISMA: 16}
    sorc = spell_caster([("Sorcerer", 5)], [FIRE_BOLT_SPELL], scores, manual={"empowered_spell"})
    base = spell_caster([("Sorcerer", 5)], [FIRE_BOLT_SPELL], scores)
    f = lambda a: float(fact(roll(a, "spell:Fire Bolt", {"target": 1}), "damage", "Average when it hits"))
    assert f(sorc) > f(base)


# ----------------------------------------------------------------------------- magic items

def item(name, attuned=True, extra="", requires=True):
    return {"name": name, "attuned": attuned, "requires_attunement": requires, "extra_properties": extra}


@pytest.fixture(scope="module")
def magic_lookup():
    from magic_item import get_magic_item_manager
    return get_magic_item_manager().get_item


def test_a_cloak_of_protection_helps_every_save_only_while_attuned(magic_lookup):
    lk = Lookups(magic_item=magic_lookup)
    on, *_ = make([("Fighter", 1)], magic_items=[item("Cloak of Protection")], lookups=lk)
    off, *_ = make([("Fighter", 1)], magic_items=[item("Cloak of Protection", attuned=False)], lookups=lk)
    gone, *_ = make([("Fighter", 1)], magic_items=[item("Cloak of Protection")], lookups=lk,
                    disabled={"Cloak of Protection"})
    assert main(roll(on, "save:WIS")).mean() == pytest.approx(11.5)
    assert main(roll(off, "save:WIS")).mean() == pytest.approx(10.5)
    assert main(roll(gone, "save:WIS")).mean() == pytest.approx(10.5)
    assert [r[:3] for r in off.item_report()] == [("Cloak of Protection", False, "not attuned")]


def test_ability_score_items_and_skill_items(magic_lookup):
    lk = Lookups(magic_item=magic_lookup)
    a, *_ = make([("Fighter", 1)], scores={AbilityScore.STRENGTH: 10},
                 magic_items=[item("Gauntlets of Ogre Power"), item("Boots of Elvenkind", requires=False)], lookups=lk)
    assert main(roll(a, "skill:ATHLETICS")).mean() == pytest.approx(10.5 + 4)             # Strength 19
    assert main(roll(a, "skill:STEALTH")).mean() == pytest.approx(13.825)                 # Advantage
    strong, *_ = make([("Fighter", 1)], scores={AbilityScore.STRENGTH: 20},
                      magic_items=[item("Gauntlets of Ogre Power")], lookups=lk)
    assert main(roll(strong, "skill:ATHLETICS")).mean() == pytest.approx(10.5 + 5)        # no effect above 19


def test_a_magic_weapon_adds_its_bonus_and_extra_dice(magic_lookup):
    lk = Lookups(magic_item=magic_lookup)
    sword = [{"name": "Sun Blade", "attack_bonus": "+5", "damage": "1d8+3 radiant"}]
    a, *_ = make([("Fighter", 1)], attacks=sword, magic_items=[item("Sun Blade")], lookups=lk)
    opt = {r.key: r for r in a.rolls()}["attack:0"]
    assert [o for o in opt.options if o.key == "magic_weapon"][0].default == "Sun Blade"      # matched by name
    plain = roll(a, "attack:0", {"magic_weapon": "None", "target": 1})
    magic = roll(a, "attack:0", {"target": 1})
    assert magic.views[0].dist.mean() == pytest.approx(plain.views[0].dist.mean() + 2)
    assert float(fact(magic, "damage", "Normal hit")) == pytest.approx(float(fact(plain, "damage", "Normal hit")) + 2)
    vs_undead = roll(a, "attack:0", {"target": 1, "xtra:Sun Blade:0": True})
    assert float(fact(vs_undead, "damage", "Normal hit")) == pytest.approx(float(fact(magic, "damage", "Normal hit")) + 4.5)
    unattuned, *_ = make([("Fighter", 1)], attacks=sword, magic_items=[item("Sun Blade", attuned=False)], lookups=lk)
    assert "magic_weapon" not in [o.key for o in {r.key: r for r in unattuned.rolls()}["attack:0"].options]


def test_spell_items_raise_attack_and_dc(magic_lookup):
    lk = Lookups(magic_item=magic_lookup, spell={"Fire Bolt": FIRE_BOLT_SPELL}.get,
                 class_def=lambda n: SimpleNamespace(spellcasting_ability="INT"))
    a, ch, _ = make([("Wizard", 5)], scores={AbilityScore.INTELLIGENCE: 18}, prof=3,
                    magic_items=[item("Wand of the War Mage, +1, +2 or +3"), item("Robe of the Archmagi")], lookups=lk)
    ch.known_spells = ["Fire Bolt"]
    spell = roll(a, "spell:Fire Bolt")
    assert spell.views[0].dist.mean() == pytest.approx(10.5 + 7 + 1 + 2)          # prof 3 + INT 4 + wand + robe
    assert any("save DC 17" in n for n in spell.notes)                           # 8 + 3 + 4 + 2


def test_every_real_magic_item_reads_without_error(magic_lookup):
    from item_effects import parse_item
    from magic_item import get_magic_item_manager
    count = 0
    for m in get_magic_item_manager().items:
        info = parse_item({"name": m.name, "attuned": True, "requires_attunement": m.requires_attunement}, m)
        count += info.does_anything
    assert count > 60


def test_every_class_and_subclass_analyses_with_everything_switched_on():
    """A smoke test across the real class data: nothing raises and every distribution is a distribution."""
    import json
    import os
    from character_context import FEATURES
    from paths import resource_path
    spell = SimpleNamespace(name="Fireball", level=3, tags=["Evocation", "Fire"],
                            description="Each creature makes a Dexterity saving throw. On a failed save, a target "
                                        "takes 8d6 Fire damage, or half as much damage on a successful one. The "
                                        "damage increases by 1d6 for each spell slot level above 3.")
    sources = []
    for name in ("classes.json", "legacy_2014.json"):
        data = json.load(open(resource_path(name), encoding="utf-8"))
        sources.append(data["classes"])
    checked = 0
    for classes in sources:
        for cname, c in classes.items():
            for sub in [s["name"] for s in c.get("subclasses", [])][:2]:
                for level in (5, 17):
                    ch = CharacterSpellList(name="T", lineage="Halfling Elf", classes=[
                        ClassLevel.from_dict({"class": cname, "level": level, "subclass": sub})])
                    ch.feats = ["Alert", "Lucky", "Great Weapon Master", "Savage Attacker", "Piercer", "Dueling"]
                    ch.known_spells = ["Fireball"]
                    sheet = CharacterSheet(character_name="T")
                    sheet.proficiency_bonus = 2 + (level - 1) // 4
                    sheet.attacks = [{"name": "Greatsword", "attack_bonus": "+7", "damage": "2d6+4 slashing"}]
                    a = CharacterAnalyzer(ch, sheet, Lookups(spell={"Fireball": spell}.get), manual_features=set(FEATURES))
                    for r in a.rolls():
                        state = {o.key: True for o in r.options if o.kind == "bool"}
                        state.update(target=12, mode="Emphasis")
                        for v in r.analyze(state).views:
                            assert v.dist.total() == pytest.approx(1, abs=1e-6), (cname, sub, level, r.key)
                    checked += 1
    assert checked > 60
