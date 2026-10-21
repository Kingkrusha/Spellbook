"""The Studio's challenge rating check: reading a stat block's numbers and judging them against a CR."""

import statistics

import pytest

import monster_cr as C
from monster import CR_OPTIONS, Monster
from stat_block import StatBlockFeature


def feature(name, text):
    return StatBlockFeature(name=name, description=text)


def goblin_like(**kw) -> Monster:
    base = dict(name="Test Brute", ac=15, hp=60, challenge_rating="2",
                actions=[feature("Multiattack", "The brute makes two Slam attacks."),
                         feature("Slam", "Melee Attack Roll: +5, reach 5 ft. Hit: 9 (1d10 + 4) Bludgeoning damage.")])
    base.update(kw)
    return Monster(**base)


@pytest.fixture(scope="module")
def collection():
    from monster import get_monster_manager
    from spell_manager import SpellManager
    sm = SpellManager()
    sm.load_spells()
    monsters = get_monster_manager().monsters
    return monsters, C.collection_reference(monsters, sm.get_spell), sm


# --------------------------------------------------------------------------- the table

def test_the_table_has_a_row_for_every_cr():
    assert [r.cr for r in C.TABLE] == CR_OPTIONS
    for a, b in zip(C.TABLE, C.TABLE[1:]):
        assert b.hp_lo == a.hp_hi + 1                         # the hit point ranges tile the scale
        assert b.dmg_lo >= a.dmg_lo and b.ac >= a.ac


def test_the_table_values_are_the_dmg_ones():
    row = C.row_for("5")
    assert (row.prof, row.ac, row.hp_lo, row.hp_hi, row.attack, row.dc) == (3, 15, 131, 145, 6, 15)
    assert C.row_for("1/2").hp_hi == 70
    assert C.row_for("30").hp_hi == 850


def test_table_reference_places_the_middle_of_each_row_at_its_cr():
    ref = C.table_reference()
    for cr in ("1", "5", "10", "17", "25"):
        row = C.row_for(cr)
        assert CR_OPTIONS[ref.index_for("ehp", (row.hp_lo + row.hp_hi) / 2)] == cr
        assert CR_OPTIONS[ref.index_for("dmg", (row.dmg_lo + row.dmg_hi) / 2)] == cr


# --------------------------------------------------------------------------- reading a stat block

def test_damage_per_round_counts_a_multiattack_landing_in_full():
    off = C.read_offense(goblin_like())
    assert off.detected
    assert off.per_round == pytest.approx(2 * (5.5 + 4))      # two slams of 1d10 + 4
    assert off.attack_bonus == 5 and off.uses_attacks


def test_a_recharge_breath_is_averaged_over_the_first_three_rounds():
    dragon = Monster(name="Test Wyrm", ac=18, hp=200, challenge_rating="9", actions=[
        feature("Bite", "Melee Attack Roll: +9, reach 10 ft. Hit: 15 (2d10 + 4) Piercing damage."),
        feature("Fire Breath (Recharge 5-6)", "Dexterity Saving Throw: DC 17, each creature in a 30-foot Cone. "
                                              "Failure: 55 (10d10) Fire damage. Success: Half damage.")])
    off = C.read_offense(dragon)
    assert off.save_dc == 17
    assert off.per_round == pytest.approx((55 + 2 * 15) / 3)
    assert "Fire Breath" in off.limited[0]


def test_a_creature_with_no_readable_attacks_is_judged_on_defences_alone():
    blob = Monster(name="Quiet Blob", ac=10, hp=40, challenge_rating="1/2",
                   actions=[feature("Engulf", "The blob slowly absorbs the target.")])
    report = C.analyze(blob)
    assert not report.offense.detected
    assert report.offensive == ""
    assert report.suggested == report.defensive
    assert any("defences alone" in n for n in report.notes)


def test_non_magical_resistance_counts_as_extra_hit_points_by_cr():
    plain = goblin_like(hp=60)
    tough = goblin_like(hp=60, damage_resistances=["Bludgeoning, Piercing, and Slashing from Nonmagical Attacks"])
    assert C.read_defense(plain).effective_hp == 60
    assert C.read_defense(tough).effective_hp == pytest.approx(120)           # x2 at low levels
    high = goblin_like(hp=300, damage_resistances=["Bludgeoning, Piercing, and Slashing from Nonmagical Attacks"])
    assert C.read_defense(high).effective_hp > 300                             # x1.25 at CR 11-16...
    very_high = goblin_like(hp=700, challenge_rating="20",
                            damage_resistances=["Bludgeoning, Piercing, and Slashing from Nonmagical Attacks"])
    assert C.read_defense(very_high).effective_hp == 700                       # ...and nothing from CR 17


def test_immunities_to_common_damage_types_add_hit_points():
    base = C.read_defense(goblin_like(hp=100)).effective_hp
    assert C.read_defense(goblin_like(hp=100, damage_immunities=["Fire"])).effective_hp > base
    assert C.read_defense(goblin_like(hp=100, damage_immunities=["Fire", "Cold", "Lightning", "Poison"])
                          ).effective_hp > C.read_defense(goblin_like(hp=100, damage_immunities=["Fire"])).effective_hp


def test_regeneration_and_saving_throw_proficiencies_count():
    from character_sheet import AbilityScore
    regen = goblin_like(hp=100, traits=[feature("Regeneration", "The troll regains 10 hit points at the start of "
                                                                 "its turn.")])
    assert C.read_defense(regen).effective_hp == pytest.approx(130)
    m = goblin_like()
    for a in (AbilityScore.STRENGTH, AbilityScore.DEXTERITY, AbilityScore.CONSTITUTION):
        m.saving_throws.set_proficiency(a, True)
    assert C.read_defense(m).effective_ac == m.ac + 2


# --------------------------------------------------------------------------- suggesting a CR

def monster_for(cr: str) -> Monster:
    """A monster built to the middle of the DMG table for ``cr``."""
    row = C.row_for(cr)
    hp = (row.hp_lo + row.hp_hi) // 2
    dmg = (row.dmg_lo + row.dmg_hi) / 2
    hit = max(1, int(round(dmg / 2 - row.prof - 3)))          # two attacks of about dmg / 2 each
    return Monster(name=f"Table CR {cr}", ac=row.ac, hp=hp, challenge_rating=cr, actions=[
        feature("Multiattack", "The creature makes two Strike attacks."),
        feature("Strike", f"Melee Attack Roll: +{row.attack}, reach 5 ft. Hit: {int(dmg / 2)} (1d4 + {int(dmg / 2) - 2}) "
                          f"Slashing damage.")])


@pytest.mark.parametrize("cr", ["1", "3", "5", "8", "12", "16", "20"])
def test_a_creature_built_to_the_table_is_suggested_its_own_cr(cr):
    report = C.analyze(monster_for(cr))               # the DMG table alone
    assert abs(CR_OPTIONS.index(report.suggested) - CR_OPTIONS.index(cr)) <= 1, (cr, report.suggested)
    assert report.defensive == cr


def test_too_many_hit_points_is_called_out():
    report = C.analyze(goblin_like(hp=300, challenge_rating="2"))
    hp = next(s for s in report.stats if s.key == "hp")
    assert hp.status == "high"
    assert any("Hit Points" in w and "higher than is typical for CR 2" in w for w in report.warnings)
    assert CR_OPTIONS.index(report.suggested) > CR_OPTIONS.index("2")


def test_too_much_damage_and_too_high_a_bonus_are_called_out():
    glass = Monster(name="Glass Cannon", ac=12, hp=40, challenge_rating="1", actions=[
        feature("Multiattack", "The cannon makes three Blast attacks."),
        feature("Blast", "Ranged Attack Roll: +9, range 120 ft. Hit: 20 (4d8 + 2) Fire damage.")])
    report = C.analyze(glass)
    by = {s.key: s for s in report.stats}
    assert by["damage"].status == "high"
    assert by["attack"].status == "high"
    assert by["hp"].status in ("low", "ok")
    assert any("Damage per round" in w for w in report.warnings)


def test_weak_numbers_are_a_note_not_a_warning():
    soft = goblin_like(hp=10, ac=8, challenge_rating="5", actions=[
        feature("Poke", "Melee Attack Roll: +2, reach 5 ft. Hit: 3 (1d4 + 1) Piercing damage.")])
    report = C.analyze(soft)
    assert not any("higher" in w for w in report.warnings if "Hit Points" in w)
    assert any("lower than is typical" in n for n in report.notes)


def test_the_blank_form_is_not_judged_as_cr_zero():
    report = C.analyze(Monster(name="New", ac=16, hp=120, challenge_rating="0", actions=[
        feature("Claw", "Melee Attack Roll: +6, reach 5 ft. Hit: 12 (2d8 + 3) Slashing damage.")]))
    assert not report.declared_set
    assert report.compared_with == report.suggested
    assert not report.warnings


def test_a_deliberate_cr_is_the_one_compared():
    report = C.analyze(goblin_like(hp=300, challenge_rating="2"))
    assert report.declared_set and report.compared_with == "2"
    report = C.analyze(goblin_like(hp=300, challenge_rating="2"), compare_to="9")
    assert report.compared_with == "9"


def test_notes_mention_what_the_table_cannot_count():
    m = goblin_like(challenge_rating="3", traits=[feature("Legendary Resistance (3/Day)", "If it fails a save, it succeeds."),
                                                  feature("Magic Resistance", "Advantage on saves against spells.")],
                    speeds={"walk": 30, "fly": 60})
    notes = " ".join(C.analyze(m).notes)
    assert "Legendary Resistance" in notes and "Magic Resistance" in notes and "Flying" in notes


# --------------------------------------------------------------------------- against the real monsters

def test_the_suggestion_tracks_the_official_challenge_ratings(collection):
    monsters, ref, sm = collection
    official = [m for m in monsters if m.is_official and not m.spell_only]
    assert len(official) > 300
    errors = []
    for m in official:
        report = C.analyze(m, reference=ref, spell_lookup=sm.get_spell)
        errors.append(CR_OPTIONS.index(report.suggested) - CR_OPTIONS.index(report.declared))
    within_one = sum(1 for e in errors if abs(e) <= 1) / len(errors)
    assert within_one > 0.80, within_one
    assert statistics.mean(abs(e) for e in errors) < 1.0
    assert abs(statistics.mean(errors)) < 0.5                  # no strong lean either way


def test_the_reference_has_real_ranges_where_the_collection_has_monsters(collection):
    _monsters, ref, _sm = collection
    band = ref.band("1", "ehp")
    assert band.n > 20
    assert band.hi < C.row_for("1").hp_hi             # real CR 1 monsters keep well under the DMG's 71-85 hit points
    assert ref.band("30", "ehp").hi >= 700            # little data up there, so the table carries it


def test_closest_monsters_are_official_and_near(collection):
    monsters, ref, sm = collection
    ogre = next(m for m in monsters if m.name == "Ogre")
    near = C.closest(ogre, ref, sm.get_spell, exclude="Ogre")
    assert len(near) == 5 and all(m.name != "Ogre" for m, _n in near)
    assert all(abs(n["hp"] - ogre.hp) < 120 for _m, n in near)


def test_multiattack_with_other_attacks_is_read_in_full(collection):
    """The Tarrasque's 'one Bite and three other attacks, using Claw or Tail' used to be read as one attack."""
    import matchup as M
    monsters, _ref, sm = collection
    t = next(m for m in monsters if m.name == "Tarrasque")
    side = M.side_from_monster(t, sm.get_spell)
    assert side.multiattack and all(sum(c for _n, c in combo) == 4 for combo in side.multiattack)
    assert C.read_offense(t, sm.get_spell).per_round > 110     # it was read as 78 before


def test_the_report_lists_what_was_read_from_the_stat_block():
    m = goblin_like(hp=100, damage_resistances=["Fire"], damage_immunities=["Poison"],
                    condition_immunities=["Poisoned", "Charmed"], actions=[
        feature("Multiattack", "The brute makes two Slam attacks."),
        feature("Slam", "Melee Attack Roll: +5, reach 5 ft. Hit: 9 (1d10 + 4) Bludgeoning damage, and the target "
                        "has the Grappled condition (escape DC 13).")])
    lines = dict(C.analyze(m).read)
    assert lines["Armor Class"] == "15"
    assert lines["Hit Points"].startswith("100") and "counts as" in lines["Hit Points"]
    assert lines["Damage per round"].startswith("19") and "Multiattack (Slam x2)" in lines["Damage per round"]
    assert lines["Attack bonus"] == "+5"
    assert (lines["Resistances"], lines["Immunities"]) == ("Fire", "Poison")
    assert lines["Condition immunities"] == "Poisoned, Charmed"
    assert lines["Vulnerabilities"] == "none"
    assert lines["Can inflict"] == "Grappled"
