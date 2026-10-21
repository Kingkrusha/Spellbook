"""The Monster editor as a character sheet: numbers that follow from other numbers are worked out and explained."""

import time

import pytest

import monster_rules as MR


def pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


# --------------------------------------------------------------------------- the rules

def test_the_hit_die_follows_the_size():
    assert [MR.hit_die_for_size(s) for s in ("Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan")] == \
        [4, 6, 8, 10, 12, 20]


def test_hit_points_are_the_dice_average_plus_constitution_for_each_die():
    assert MR.hit_points(6, 10, 2) == 45            # 6 x 5.5 = 33, + 6 x 2
    assert MR.hit_points(19, 12, 7) == 256          # an adult red dragon
    assert MR.hit_points(4, 8, -1) == 14            # 18 - 4
    assert MR.hit_points(0, 8, 3) == 1
    assert MR.hit_dice_text(6, 10, 2) == "6d10 + 12"
    assert MR.hit_dice_text(4, 8, -1) == "4d8 - 4"
    assert MR.hit_dice_text(3, 8, 0) == "3d8"
    assert MR.parse_hit_dice("19d12 + 133") == (19, 12, 133)
    assert MR.parse_hit_dice("nonsense") is None


def test_the_official_monsters_follow_these_rules():
    """The hit dice of the Monster Manual monsters are the size's die plus Constitution for each die."""
    from character_sheet import AbilityScore
    from monster import get_monster_manager
    followed = total = 0
    for m in get_monster_manager().monsters:
        parsed = MR.parse_hit_dice(m.hit_dice)
        if not parsed or m.spell_only:
            continue
        total += 1
        con = MR.modifier(m.ability_scores.get(AbilityScore.CONSTITUTION))
        if parsed[1] == MR.hit_die_for_size(m.size) and parsed[2] == parsed[0] * con \
                and m.hp == MR.hit_points(parsed[0], parsed[1], con):
            followed += 1
    assert total > 400 and followed / total > 0.99


STATS = MR.Stats(prof=3, mods={"STR": 4, "DEX": 2, "CON": 3, "INT": 0, "WIS": 1, "CHA": -1}, cr="5")


def test_an_attack_is_a_stat_plus_proficiency_to_hit_and_the_stat_again_to_damage():
    build = {"mode": "attack", "kind": "melee", "ability": "STR", "proficient": True, "reach": "5",
             "dice": "2d6", "type": "Slashing"}
    out = MR.built(build, STATS)
    assert out.bonus == 7 and out.average == 11
    assert out.text == "Melee Attack Roll: +7, reach 5 ft. Hit: 11 (2d6 + 4) Slashing damage."
    assert out.tip_bonus == "+4 from Strength, +3 from proficiency"
    assert "+4 from Strength is added to the damage" in out.tip_damage
    # not proficient: only the stat
    assert MR.built({**build, "proficient": False}, STATS).bonus == 4
    # a negative modifier subtracts
    weak = MR.built({**build, "ability": "CHA"}, STATS)
    assert weak.text.startswith("Melee Attack Roll: +2,") and "(2d6 - 1)" in weak.text and weak.average == 6


def test_ranged_attacks_extra_damage_and_effects_are_written_out():
    build = {"mode": "attack", "kind": "both", "ability": "DEX", "proficient": True, "reach": "5", "range": "30/120",
             "dice": "1d8", "type": "Piercing", "extra_dice": "2d6", "extra_type": "Fire",
             "effect": "The target has the Prone condition."}
    text = MR.built(build, STATS).text
    assert text == ("Melee or Ranged Attack Roll: +5, reach 5 ft. or range 30/120 ft. Hit: 6 (1d8 + 2) Piercing "
                    "damage plus 7 (2d6) Fire damage. The target has the Prone condition.")


def test_a_saving_throw_effect_has_its_dc_from_a_stat():
    build = {"mode": "save", "save": "DEX", "dc_ability": "CON", "area": "each creature in a 30-foot Cone",
             "dice": "10d10", "type": "Fire", "half": True, "effect": ""}
    out = MR.built(build, STATS)
    assert out.dc == 14 and out.average == 55
    assert out.text == ("Dexterity Saving Throw: DC 14, each creature in a 30-foot Cone. Failure: 55 (10d10) Fire "
                        "damage. Success: Half damage.")
    assert "8 + 3 from Constitution + 3 from proficiency" in out.tip_dc
    with_effect = MR.built({**build, "effect": ", and the target is Frightened.", "half": False}, STATS).text
    assert with_effect.endswith("Fire damage, and the target is Frightened.")


def test_an_attack_follows_when_the_stats_change():
    build = {"mode": "attack", "kind": "melee", "ability": "STR", "proficient": True, "reach": "5", "dice": "1d6",
             "type": "Bludgeoning"}
    low = MR.built(build, STATS)
    strong = MR.built(build, MR.Stats(prof=5, mods={**STATS.mods, "STR": 6}, cr="13"))
    assert (low.bonus, strong.bonus) == (7, 11)
    assert low.average == 7 and strong.average == 9


def test_existing_text_is_linked_only_when_it_follows_from_the_stats():
    text = "Melee Attack Roll: +7, reach 10 ft. Hit: 15 (2d10 + 4) Piercing damage."
    build = MR.guess_build(text, STATS)
    assert build and build["ability"] == "STR" and build["reach"] == "10" and build["dice"] == "2d10"
    assert MR.built(build, STATS).text == text
    assert MR.guess_build("Melee Attack Roll: +9, reach 5 ft. Hit: 15 (2d10 + 4) Piercing damage.", STATS) is None
    assert MR.guess_build("The creature roars.", STATS) is None
    save = "Dexterity Saving Throw: DC 14, each creature in a 30-foot Cone. Failure: 55 (10d10) Fire damage. Success: Half damage."
    assert MR.built(MR.guess_build(save, STATS), STATS).text == save


def test_most_official_attacks_can_be_linked_without_changing_a_word():
    from character_sheet import AbilityScore
    from monster import get_monster_manager
    order = [AbilityScore.STRENGTH, AbilityScore.DEXTERITY, AbilityScore.CONSTITUTION, AbilityScore.INTELLIGENCE,
             AbilityScore.WISDOM, AbilityScore.CHARISMA]
    total = linked = 0
    for m in get_monster_manager().monsters:
        if m.spell_only:
            continue
        stats = MR.Stats(prof=m.proficiency_bonus, mods={a: m.get_modifier(e) for a, e in zip(MR.ABILITIES, order)},
                         cr=m.challenge_rating)
        for f in m.actions:
            if f.description.startswith(("Melee Attack Roll", "Ranged Attack Roll")) or "Saving Throw: DC" in f.description[:40]:
                total += 1
                build = MR.guess_build(f.description, stats)
                if build:
                    linked += 1
                    assert MR.built(build, stats).text == f.description.strip()
    assert total > 500 and linked / total > 0.8


# --------------------------------------------------------------------------- the editor

@pytest.fixture
def host(tk_root):
    import customtkinter as ctk
    tk_root.geometry("1000x1000")
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    yield frame
    frame.destroy()
    tk_root.update()


def panel(host, root, monster=None):
    from ui.monster_view import MonsterEditorPanel
    editor = MonsterEditorPanel(host, "Monster", monster=monster)
    editor.pack(fill="both", expand=True)
    pump(root, 0.3)
    return editor


def chip(editor, key):
    label, tip = editor._chips[key]
    return label.cget("text"), tip.text


def test_proficiency_comes_from_the_cr(host, tk_root):
    ed = panel(host, tk_root)
    ed.cr_var.set("5")
    ed._update_preview()
    text, tip = chip(ed, "prof")
    assert text == "Proficiency +3" and tip == "Proficiency bonus is based off of CR (CR 5 gives +3)."
    ed.cr_var.set("17")
    ed._update_preview()
    assert chip(ed, "prof")[0] == "Proficiency +6"


def test_the_hit_die_comes_from_the_size_and_hit_points_from_the_dice(host, tk_root):
    ed = panel(host, tk_root)
    ed.size_var.set("Large")
    ed.ability_entries[next(a for a in ed.ability_entries if a.name == "CONSTITUTION")].delete(0, "end")
    for a, entry in ed.ability_entries.items():
        if a.name == "CONSTITUTION":
            entry.insert(0, "14")
    ed.hit_count_entry.insert(0, "6")
    ed._update_preview()
    assert chip(ed, "hitdie")[0] == "d10"
    assert "Large" in chip(ed, "hitdie")[1]
    assert ed.hp_entry.get() == "45" and ed.hit_dice_entry.get() == "6d10 + 12"
    assert str(ed.hp_entry.cget("state")) == "disabled"          # worked out: not typed
    assert "6 hit dice" in ed._tips["hp"].text and "+2 from Constitution" in ed._tips["hp"].text
    result = ed.build_result(strict=False)
    assert (result.hp, result.hit_dice) == (45, "6d10 + 12")
    ed.size_var.set("Huge")
    ed._update_preview()
    assert ed.hp_entry.get() == "51" and ed.hit_dice_entry.get() == "6d12 + 12"


def test_hit_points_can_be_set_by_hand(host, tk_root):
    ed = panel(host, tk_root)
    ed.hit_count_entry.insert(0, "6")
    ed._update_preview()
    ed.hp_manual_var.set(True)
    ed._update_preview()
    assert str(ed.hp_entry.cget("state")) == "normal"
    ed.hp_entry.delete(0, "end")
    ed.hp_entry.insert(0, "200")
    ed.hit_dice_entry.delete(0, "end")
    ed.hit_dice_entry.insert(0, "a lot")
    result = ed.build_result(strict=False)
    assert (result.hp, result.hit_dice) == (200, "a lot")
    assert "Set by hand" in ed._tips["hp"].text


def test_saves_skills_and_initiative_say_where_they_come_from(host, tk_root):
    from character_sheet import AbilityScore, Skill
    ed = panel(host, tk_root)
    ed.cr_var.set("5")                                            # proficiency +3
    ed.ability_entries[AbilityScore.STRENGTH].delete(0, "end")
    ed.ability_entries[AbilityScore.STRENGTH].insert(0, "18")
    ed.save_vars[AbilityScore.STRENGTH].set(True)
    ed.skill_vars[Skill.ATHLETICS].set("Expertise")
    ed._update_preview()
    assert chip(ed, "mod_STR")[0] == "+4"
    assert chip(ed, "save_STR") == ("Save +7", "+4 from Strength, +3 from proficiency")
    assert chip(ed, "save_DEX")[1].endswith("(not proficient)")
    text, tip = chip(ed, "skill_ATHLETICS")
    assert text == "+10" and "+4 from Strength" in tip and "+6 from proficiency" in tip and "expertise" in tip
    assert chip(ed, "passive")[0] == "Passive Perception 10"


def test_an_attack_in_the_form_follows_the_scores_and_the_cr(host, tk_root):
    from character_sheet import AbilityScore
    ed = panel(host, tk_root)
    ed.name_entry.insert(0, "Brute")
    ed.cr_var.set("5")
    ed.ability_entries[AbilityScore.STRENGTH].delete(0, "end")
    ed.ability_entries[AbilityScore.STRENGTH].insert(0, "18")
    ed.actions_editor.add_feature("Slam")
    row = ed.actions_editor._rows[0]
    ed.actions_editor._set_mode(row, "Attack")
    w = row["attack"]
    w["dice"].delete(0, "end")
    w["dice"].insert(0, "2d6")
    ed.actions_editor._changed()
    ed._update_preview()
    action = ed.build_result(strict=True).actions[0]
    assert action.description == "Melee Attack Roll: +7, reach 5 ft. Hit: 11 (2d6 + 4) Slashing damage."
    assert action.build["ability"] == "STR"
    # raise Strength and the CR: the attack follows without touching it
    ed.ability_entries[AbilityScore.STRENGTH].delete(0, "end")
    ed.ability_entries[AbilityScore.STRENGTH].insert(0, "22")
    ed.cr_var.set("9")
    ed._update_preview()
    action = ed.build_result(strict=True).actions[0]
    assert action.description == "Melee Attack Roll: +10, reach 5 ft. Hit: 13 (2d6 + 6) Slashing damage."
    assert row["tips"]["bonus"].text == "+6 from Strength, +4 from proficiency"


def test_a_linked_attack_survives_saving_and_reopening(host, tk_root):
    from monster import Monster
    ed = panel(host, tk_root)
    ed.name_entry.insert(0, "Reopened")
    ed.actions_editor.add_feature("Bite")
    ed.actions_editor._set_mode(ed.actions_editor._rows[0], "Attack")
    saved = ed.build_result(strict=True)
    again = Monster.from_dict(saved.to_dict())
    assert again.actions[0].build == saved.actions[0].build and again.actions[0].build["mode"] == "attack"
    ed2 = panel(host, tk_root, again)
    row = ed2.actions_editor._rows[0]
    assert row["mode"].get() == "Attack" and row["attack"]["ability"].get() == "STR"
    assert ed2.build_result(strict=True).actions[0].description == saved.actions[0].description


def test_a_saving_throw_effect_in_the_form(host, tk_root):
    from character_sheet import AbilityScore
    ed = panel(host, tk_root)
    ed.name_entry.insert(0, "Breather")
    ed.cr_var.set("9")                                            # proficiency +4
    ed.ability_entries[AbilityScore.CONSTITUTION].delete(0, "end")
    ed.ability_entries[AbilityScore.CONSTITUTION].insert(0, "16")
    ed.actions_editor.add_feature("Fire Breath (Recharge 5-6)")
    row = ed.actions_editor._rows[0]
    ed.actions_editor._set_mode(row, "Saving throw")
    ed._update_preview()
    action = ed.build_result(strict=True).actions[0]
    assert action.description.startswith("Dexterity Saving Throw: DC 15,")        # 8 + 4 + 3
    assert row["tips"]["dc"].text.startswith("8 + 3 from Constitution + 4 from proficiency")


def test_plain_text_can_be_linked_to_the_stats(host, tk_root, monkeypatch):
    from tkinter import messagebox
    from character_sheet import AbilityScore
    ed = panel(host, tk_root)
    ed.name_entry.insert(0, "Old Style")
    ed.cr_var.set("5")
    ed.ability_entries[AbilityScore.STRENGTH].delete(0, "end")
    ed.ability_entries[AbilityScore.STRENGTH].insert(0, "18")
    ed.actions_editor.add_feature("Claw", "Melee Attack Roll: +7, reach 5 ft. Hit: 11 (2d6 + 4) Slashing damage.")
    row = ed.actions_editor._rows[0]
    ed.actions_editor._link(row)
    assert row["mode"].get() == "Attack" and row["attack"]["dice"].get() == "2d6"
    ed.actions_editor.add_feature("Odd", "Melee Attack Roll: +99, reach 5 ft. Hit: 1 (1d1) Slashing damage.")
    shown = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: shown.append(a))
    ed.actions_editor._link(ed.actions_editor._rows[1])
    assert shown and ed.actions_editor._rows[1]["mode"].get() == "Text"


def test_an_official_monster_opens_with_its_numbers_worked_out(host, tk_root):
    from monster import get_monster_manager
    dragon = get_monster_manager().get_monster("Adult Red Dragon")
    ed = panel(host, tk_root, dragon)
    assert not ed.hp_manual_var.get()                           # its 19d12 + 133 is exactly what the rules give
    assert ed.hit_count_entry.get() == "19" and ed.hp_entry.get() == "256"
    out = ed.build_result(strict=True)
    assert out.to_dict()["actions"] == dragon.to_dict()["actions"]          # nothing rewritten
    assert (out.hp, out.hit_dice) == (dragon.hp, dragon.hit_dice)


def test_hit_points_that_do_not_follow_the_rules_stay_as_written(host, tk_root):
    from monster import Monster
    odd = Monster(name="Odd Hit Points", size="Medium", hp=100, hit_dice="4d8 + 4")
    ed = panel(host, tk_root, odd)
    assert ed.hp_manual_var.get()
    out = ed.build_result(strict=True)
    assert (out.hp, out.hit_dice) == (100, "4d8 + 4")


def test_sections_fold_away_and_keep_their_contents(host, tk_root):
    ed = panel(host, tk_root)
    skills = next(s for s in ed._sections if s.title == "Skill Proficiencies")
    assert not skills.is_open                                    # rarely used: folded by default
    assert skills.body.winfo_manager() == ""
    skills.toggle()
    assert skills.is_open and skills.body.winfo_manager() == "pack"
    skills.toggle()
    from character_sheet import Skill
    ed.skill_vars[Skill.STEALTH].set("Proficient")               # still readable while folded
    assert ed.build_result(strict=False).skills.get(Skill.STEALTH) == 1
    combat = next(s for s in ed._sections if s.title == "Combat")
    assert combat.is_open
    assert "▾" in combat.header.cget("text")
    combat.toggle()
    assert "▸" in combat.header.cget("text")


def test_sections_with_content_start_open(host, tk_root):
    from monster import Monster
    from stat_block import StatBlockFeature
    m = Monster(name="Lord", legendary_actions=[StatBlockFeature("Tail", "It swipes.")], description="Lore.")
    ed = panel(host, tk_root, m)
    assert ed.sec_legendary.is_open and ed.sec_lore.is_open
    assert not ed.sec_summon.is_open and not ed.sec_overrides.is_open
