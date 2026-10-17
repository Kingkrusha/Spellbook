"""One-on-one fight analysis: reading stat blocks, working damage out against a defender, the simulation, tide turners."""

import json
from types import SimpleNamespace

import pytest

import matchup as M
from character import CharacterSpellList, ClassLevel
from character_rolls import Lookups
from character_sheet import AbilityScore, CharacterSheet
from dice_analyzer import Dist
from monster import Monster
from paths import resource_path


@pytest.fixture(scope="module")
def monsters():
    data = json.load(open(resource_path("monsters.json"), encoding="utf-8"))["monsters"]
    return {m["name"]: Monster.from_dict(m) for m in data}


def monster_side(monsters, name):
    return M.side_from_monster(monsters[name])


# ----------------------------------------------------------------------------- reading stat blocks

def test_attack_and_damage_components_are_read():
    s = M.parse_strike("Rend", "Melee Attack Roll: +14, reach 10 ft. Hit: 13 (1d10 + 8) Slashing damage plus 5 (2d4) "
                               "Fire damage.")
    assert s.kind == "attack" and s.attack_bonus == 14 and s.reach == 10 and s.melee
    assert s.components == [(1, 10, 8, "slashing"), (2, 4, 0, "fire")]


def test_conditional_extra_damage_is_not_counted_and_old_style_text_works():
    gob = M.parse_strike("Scimitar", "Melee Attack Roll: +4, reach 5 ft. Hit: 5 (1d6 + 2) Slashing damage, plus 2 "
                                     "(1d4) Slashing damage if the attack roll had Advantage.")
    assert gob.components == [(1, 6, 2, "slashing")]
    old = M.parse_strike("Bite", "Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 7 (1d8 + 3) piercing "
                                 "damage.")
    assert old.attack_bonus == 5 and old.components == [(1, 8, 3, "piercing")]
    ranged = M.parse_strike("Longbow", "Ranged Attack Roll: +6, range 150/600 ft. Hit: 8 (1d8 + 4) Piercing damage.")
    assert not ranged.melee and ranged.range_ft == 150


def test_saving_throw_effects_recharge_and_conditions():
    breath = M.parse_strike("Fire Breath (Recharge 5–6)", "Dexterity Saving Throw: DC 21, each creature in a 60-foot "
                                                              "Cone. Failure: 59 (17d6) Fire damage. Success: Half damage.")
    assert breath.kind == "save" and breath.save_ability == "DEX" and breath.save_dc == 21
    assert breath.half_on_save and breath.uses == "recharge" and breath.recharge == 5 and breath.area
    touch = M.parse_strike("Paralyzing Touch", "Melee Attack Roll: +12, reach 5 ft. Hit: 15 (3d6 + 5) Cold damage, and "
                                              "the target has the Paralyzed condition until the start of the lich's "
                                              "next turn.")
    assert touch.conditions == ["Paralyzed"]
    assert M.parse_strike("Nimble Escape", "The goblin takes the Disengage or Hide action.") is None


def test_multiattack_forms():
    strikes = {n: M.Strike(n) for n in ("Rend", "Grave Strike", "Bite", "Eldritch Burst", "Paralyzing Touch")}
    assert M.parse_multiattack("The troll makes three Rend attacks.", strikes) == [[("Rend", 3)]]
    assert M.parse_multiattack("The vampire makes two Grave Strike attacks and uses Bite.", strikes) == [
        [("Grave Strike", 2), ("Bite", 1)]]
    plans = M.parse_multiattack("The lich makes three attacks, using Eldritch Burst or Paralyzing Touch in any "
                                "combination.", strikes)
    assert [("Eldritch Burst", 3)] in plans and [("Paralyzing Touch", 3)] in plans


def test_a_real_monster_is_read_whole(monsters):
    troll = monster_side(monsters, "Troll")
    assert troll.ac == 15 and troll.hp == 94 and troll.regeneration == 15
    assert troll.multiattack == [[("Rend", 3)]]
    dragon = monster_side(monsters, "Adult Red Dragon")
    assert dragon.legendary_resistance == 3 and "fire" in dragon.immune
    assert {s.name for s in dragon.strikes} >= {"Rend", "Fire Breath"}
    assert dragon.speeds["fly"] == 80


def test_every_official_monster_reads_without_errors(monsters):
    """No stat block breaks the reader; most real monsters have something to fight with."""
    with_attacks = 0
    for monster in monsters.values():
        side = M.side_from_monster(monster)
        with_attacks += bool(side.strikes)
    assert with_attacks > 0.8 * len(monsters)


# ----------------------------------------------------------------------------- damage against a defender

def test_hit_chances_follow_armor_class():
    miss, hit, crit = M.attack_chances(7, 15)
    assert (miss, hit, crit) == pytest.approx((0.35, 0.6, 0.05))         # 8 or more of 2-19, plus the natural 20
    assert M.attack_chances(30, 10)[0] == pytest.approx(0.05)             # only a natural 1 misses


def test_resistance_immunity_and_vulnerability():
    strike = M.parse_strike("Rend", "Melee Attack Roll: +100, reach 5 ft. Hit: 10 (2d6 + 3) Fire damage.")
    plain = M.make_action(strike, M.Defender("t", ac=10))
    resist = M.make_action(strike, M.Defender("t", ac=10, resist={"fire"}))
    immune = M.make_action(strike, M.Defender("t", ac=10, immune={"fire"}))
    weak = M.make_action(strike, M.Defender("t", ac=10, vulnerable={"fire"}))
    assert plain.avg == pytest.approx(10 * 0.9 + 0.05 * 17, abs=0.01)      # 90% hit, 5% crit (4d6 + 3)
    assert resist.avg < plain.avg * 0.55 and resist.avg > plain.avg * 0.4
    assert immune.avg == 0
    assert weak.avg == pytest.approx(plain.avg * 2, rel=0.02)


def test_saving_throw_damage_uses_the_targets_save_and_magic_resistance():
    breath = M.parse_strike("Breath", "Dexterity Saving Throw: DC 15, each creature in a 30-foot Cone. Failure: 28 "
                                      "(8d6) Fire damage. Success: Half damage.")
    weak_save = M.make_action(breath, M.Defender("t", saves={"DEX": -2}))
    strong_save = M.make_action(breath, M.Defender("t", saves={"DEX": 8}))
    assert weak_save.p_save == pytest.approx(0.2) and strong_save.p_save == pytest.approx(0.7)
    assert weak_save.avg > strong_save.avg
    spell = M.Strike("Fireball (spell)", kind="save", save_ability="DEX", save_dc=15, half_on_save=True,
                     components=[(8, 6, 0, "fire")], is_spell=True)
    plain = M.make_action(spell, M.Defender("t", saves={"DEX": 0}))
    resistant = M.make_action(spell, M.Defender("t", saves={"DEX": 0}, magic_resistance=True))
    assert resistant.p_save > plain.p_save and resistant.avg < plain.avg


def test_plans_say_how_likely_they_are_to_land():
    strike = M.parse_strike("Rend", "Melee Attack Roll: +7, reach 5 ft. Hit: 10 (2d6 + 3) Slashing damage.")
    plan = M.Plan("Rend", [(M.make_action(strike, M.Defender("t", ac=15)), 1)])
    assert plan.chance_text() == "65% to hit"                              # 8 or more on a d20, and every 20
    breath = M.parse_strike("Breath", "Dexterity Saving Throw: DC 15, each creature in a 30-foot Cone. Failure: 28 "
                                      "(8d6) Fire damage. Success: Half damage.")
    both = M.Plan("Both", [(M.make_action(strike, M.Defender("t", ac=15, saves={"DEX": 0})), 1),
                           (M.make_action(breath, M.Defender("t", ac=15, saves={"DEX": 0})), 1)])
    assert both.chance_text() == "Rend 65% to hit; Breath 70% to fail the save"
    assert [w for _n, _c, w in both.chances()] == ["hit", "fail"]
    auto = M.Plan("Magic Missile", [(M.Action("Magic Missile", 10.0, Dist.point(10), kind="auto"), 1)])
    assert auto.chance_text() == "auto-hit"


def test_a_sides_main_plan_is_its_best_free_one():
    a = M.side_from_custom("A", ac=14, hp=40, attack_bonus=5, damage="1d10+3", attacks=2)
    prepared = M.prepare(a, M.side_from_custom("B", ac=12, hp=40, attack_bonus=5, damage="1d8"))
    assert prepared.main_plan() is not None and prepared.main_plan().chance_text() == "70% to hit"


# ----------------------------------------------------------------------------- the fight

def test_a_hopeless_fight_is_decided(monsters):
    r = M.analyze(monster_side(monsters, "Owlbear"), monster_side(monsters, "Goblin Warrior"), 500)
    assert r.sim["a"] > 0.99 and r.sim["rounds_mean"] < 3


def test_the_simulation_is_repeatable_and_adds_up(monsters):
    a, b = monster_side(monsters, "Troll"), monster_side(monsters, "Owlbear")
    first = M.analyze(a, b, 800, seed=5)
    again = M.analyze(a, b, 800, seed=5)
    assert first.sim["a"] == again.sim["a"] and first.sim["rounds_mean"] == again.sim["rounds_mean"]
    assert first.sim["a"] + first.sim["b"] + first.sim["draw"] == pytest.approx(1)
    assert 0 <= first.sim["first_a"] <= 1


def test_symmetric_creatures_are_an_even_fight():
    a = M.side_from_custom("A", ac=14, hp=40, attack_bonus=5, damage="1d10+3", attacks=2)
    b = M.side_from_custom("B", ac=14, hp=40, attack_bonus=5, damage="1d10+3", attacks=2)
    r = M.analyze(a, b, 4000)
    assert abs(r.sim["a"] - r.sim["b"]) < 0.06 and r.sim["draw"] < 0.01


def test_more_hit_points_win_more_often():
    weak = M.side_from_custom("Weak", ac=12, hp=30, attack_bonus=5, damage="2d6+3")
    strong = M.side_from_custom("Strong", ac=12, hp=60, attack_bonus=5, damage="2d6+3")
    assert M.analyze(weak, strong, 2000).sim["b"] > 0.8


def test_immunity_decides_a_fight_that_would_otherwise_be_even():
    fire = M.side_from_custom("Fire", ac=12, hp=40, attack_bonus=6, damage="2d8+4", damage_type="fire")
    plain = M.side_from_custom("Plain", ac=12, hp=40, attack_bonus=6, damage="2d8+4", damage_type="slashing")
    even = M.analyze(fire, plain, 2000).sim["a"]
    plain.immune = {"fire"}
    immune = M.analyze(fire, plain, 2000)
    assert abs(even - 0.5) < 0.1 and immune.sim["b"] > 0.97
    assert any("immune" in t for t in immune.turners["a"])


def test_legendary_resistance_blunts_a_save_or_damage_spell():
    caster = M.Side("Caster", "custom", ac=12, hp=40)
    caster.strikes = [M.Strike("Blast", kind="save", save_ability="CON", save_dc=18, components=[(10, 8, 0, "force")],
                               half_on_save=False)]
    caster.multiattack = []
    tank = M.Side("Tank", "custom", ac=10, hp=120, saves={"CON": 0})
    tank.strikes = [M.Strike("Slam", attack_bonus=3, components=[(1, 4, 0, "bludgeoning")])]
    plain = M.simulate(M.prepare(caster, tank), M.prepare(tank, caster), 1500)
    tank.legendary_resistance = 3
    guarded = M.simulate(M.prepare(caster, tank), M.prepare(tank, caster), 1500)
    assert guarded["rounds_mean"] > plain["rounds_mean"] + 0.5


def test_regeneration_and_recharge_matter(monsters):
    troll = monster_side(monsters, "Troll")
    plain = M.side_from_custom("Plain", ac=15, hp=94, attack_bonus=7, damage="2d6+4", attacks=3)
    regen = M.analyze(plain, troll, 1500).sim["b"]
    troll.regeneration = 0
    assert M.analyze(plain, troll, 1500).sim["b"] < regen
    dragon = monster_side(monsters, "Adult Red Dragon")
    p = M.prepare(dragon, plain.__class__("X", "custom", ac=15, hp=100))
    breath = [pl for pl in p.plans if pl.resource.startswith("recharge")][0]
    assert breath.resource == "recharge:Fire Breath"


# ----------------------------------------------------------------------------- characters

def make_character(name, cls, level, scores, attacks, spells=(), ac=16, hp=40, subclass="", lookups=None):
    ch = CharacterSpellList(name=name, classes=[ClassLevel.from_dict({"class": cls, "level": level,
                                                                      "subclass": subclass})])
    ch.known_spells = list(spells)
    sheet = CharacterSheet(character_name=name)
    sheet.proficiency_bonus = 2 + (level - 1) // 4
    sheet.armor_class, sheet.speed = ac, 30
    sheet.hit_points.maximum = sheet.hit_points.current = hp
    for ab, v in scores.items():
        sheet.ability_scores.set(ab, v)
    sheet.attacks = attacks
    return M.side_from_character(ch, sheet, lookups or Lookups(class_def=lambda n: SimpleNamespace(
        spellcasting_ability="INT")))


SPELLS = {
    "Fire Bolt": SimpleNamespace(name="Fire Bolt", level=0, tags=["Evocation", "Fire"],
                                 description="Make a ranged spell attack. On a hit, the target takes 1d10 Fire damage."
                                             "\\Cantrip Upgrade. The damage increases by 1d10 when you reach levels 5 "
                                             "(2d10), 11 (3d10), and 17 (4d10)."),
    "Burning Hands": SimpleNamespace(name="Burning Hands", level=1, tags=["Evocation", "Fire"],
                                     description="Each creature in a 15-foot Cone makes a Dexterity saving throw. On "
                                                 "a failed save, a target takes 3d6 Fire damage, or half as much "
                                                 "damage on a successful one.\\Using a Higher-Level Spell Slot. The "
                                                 "damage increases by 1d6 for each spell slot level above 1."),
    "Fireball": SimpleNamespace(name="Fireball", level=3, tags=["Evocation", "Fire"],
                                description="Each creature in a 20-foot-radius Sphere makes a Dexterity saving throw. "
                                            "On a failed save, a target takes 8d6 Fire damage, or half as much damage "
                                            "on a successful one.\\Using a Higher-Level Spell Slot. The damage "
                                            "increases by 1d6 for each spell slot level above 3."),
    "Hold Person": SimpleNamespace(name="Hold Person", level=2, tags=["Enchantment"],
                                   description="Choose a Humanoid. The target must succeed on a Wisdom saving throw "
                                               "or have the Paralyzed condition for the duration."),
}


def wizard(level=5):
    lookups = Lookups(spell=SPELLS.get, class_def=lambda n: SimpleNamespace(spellcasting_ability="INT"))
    return make_character("Wanda", "Wizard", level, {AbilityScore.INTELLIGENCE: 18},
                          [{"name": "Dagger", "attack_bonus": "+4", "damage": "1d4+2 piercing"}],
                          spells=list(SPELLS), ac=12, hp=28, lookups=lookups)


def test_a_character_is_built_from_its_sheet():
    fighter = make_character("Fred", "Fighter", 5, {AbilityScore.STRENGTH: 18, AbilityScore.CONSTITUTION: 14},
                             [{"name": "Greatsword", "attack_bonus": "+7", "damage": "2d6+4 slashing"}], ac=18, hp=49)
    assert fighter.ac == 18 and fighter.hp == 49 and fighter.saves["CON"] == 2        # +2 modifier, no proficiency
    dummy = M.side_from_custom("Dummy", ac=13, hp=59, attack_bonus=0, damage="1d4")
    plan = M.prepare(fighter, dummy).plans[0]
    assert plan.name == "Greatsword x2"                                               # Extra Attack at level 5
    # +7 against AC 13: 70% to hit for 2d6+4 (7+4), 5% crit for 4d6+4, twice
    assert plan.avg == pytest.approx(2 * (0.7 * 11 + 0.05 * 18), abs=0.01)


def test_resistances_of_a_character_come_from_species_and_options():
    sheet_side = make_character("Dave", "Fighter", 1, {AbilityScore.STRENGTH: 16},
                                [{"name": "Axe", "attack_bonus": "+5", "damage": "1d8+3 slashing"}])
    assert sheet_side.resist == set()
    ch = CharacterSpellList(name="Thorin", lineage="Hill Dwarf", classes=[ClassLevel.from_dict(
        {"class": "Fighter", "level": 1})])
    sheet = CharacterSheet(character_name="Thorin")
    dwarf = M.side_from_character(ch, sheet, Lookups(), {"resist": "fire", "immune": "psychic",
                                                         "cond_immune": "Charmed, Frightened"})
    assert dwarf.resist == {"poison", "fire"} and dwarf.immune == {"psychic"}
    assert dwarf.condition_immunities == {"Charmed", "Frightened"}


def test_spell_damage_per_level_and_per_slot_level():
    side = wizard()
    owl = M.side_from_custom("Dummy", ac=13, hp=59, attack_bonus=0, damage="1d4")
    owl.saves = {"DEX": 1}
    prepared = M.prepare(side, owl)
    levels = prepared.spell_levels
    assert set(levels) == {0, 1, 3}                                          # cantrips are in the per-level list
    assert levels[0]["name"] == "Fire Bolt" and levels[0]["per_slot"] is None    # but not in damage per slot level
    assert levels[3]["name"] == "Fireball" and levels[3]["per_slot"] == pytest.approx(levels[3]["avg"] / 3)
    assert levels[1]["per_slot"] == pytest.approx(levels[1]["avg"])
    cantrip = next(r for r in prepared.spells_table if r["level"] == 0)
    assert cantrip["avg"] == pytest.approx(2 * 5.5 * 0.8, abs=0.3)           # 2d10 at level 5, hits AC 13 on 6+... about
    upcast = next(r for r in prepared.spells_table if r["name"] == "Burning Hands")["upcast"]
    assert upcast[0] == 3 and upcast[1] > next(r for r in prepared.spells_table if r["name"] == "Burning Hands")["avg"]


def test_spell_slots_limit_how_often_a_caster_nukes():
    side = wizard()
    assert side.spell_slots == {1: 4, 2: 3, 3: 2}
    owl = M.side_from_custom("Wall", ac=10, hp=400, attack_bonus=-5, damage="1d4")
    owl.saves = {"DEX": 0}
    result = M.analyze(side, owl, 200)
    # 400 hit points cannot be dealt by 2 fireballs: the wizard has to fall back on cantrips for a long fight
    assert result.sim["rounds_mean"] > 10 or result.sim["draw"] > 0.5


def test_debuff_spells_and_features_are_listed_as_tide_turners(monsters):
    wiz = wizard()
    lich = monster_side(monsters, "Lich")
    result = M.analyze(wiz, lich, 100)
    notes = " ".join(result.turners["a"])
    assert "Hold Person" in notes and "Paralyzed" in notes and "Wisdom save" in notes
    lich_notes = " ".join(result.turners["b"])
    assert "Legendary Resistance" in lich_notes and "Paralyzing Touch can inflict Paralyzed" in lich_notes


def test_condition_immunity_is_flagged_against_a_debuff():
    wiz = wizard()
    golem = M.side_from_custom("Golem", ac=17, hp=100, attack_bonus=8, damage="3d8+4")
    golem.condition_immunities = {"Paralyzed"}
    result = M.analyze(wiz, golem, 50)
    assert any("Hold Person" in t and "immune to Paralyzed" in t for t in result.turners["a"])


def test_speed_flight_and_range_differences_are_noted(monsters):
    dragon = monster_side(monsters, "Adult Red Dragon")
    brute = M.side_from_custom("Brute", ac=15, hp=80, attack_bonus=6, damage="2d6+4")
    result = M.analyze(dragon, brute, 50)
    assert any("Flies" in t for t in result.turners["a"])
    archer = M.side_from_custom("Archer", ac=14, hp=40, attack_bonus=5, damage="1d8+3", range_ft=150)
    result = M.analyze(archer, brute, 50)
    assert any("ranged attack" in t for t in result.turners["a"])
    fast = M.side_from_custom("Runner", ac=14, hp=40, attack_bonus=5, damage="1d8+3", speed=60)
    result = M.analyze(fast, brute, 50)
    assert any("faster" in t for t in result.turners["a"])
