"""View and Compare for monsters: the numbers compared and the colours on the Monsters page."""

import time

import monster_compare as mc
from monster import Monster
from stat_block import StatBlockFeature


def brute(**kw):
    m = Monster(name=kw.pop("name", "Brute"), ac=kw.pop("ac", 13), hp=kw.pop("hp", 50), **kw)
    return m


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def test_damage_per_round_takes_the_multiattack_or_the_best_single_action():
    m = brute(actions=[
        StatBlockFeature("Multiattack", "The brute makes two Claw attacks and one Bite attack."),
        StatBlockFeature("Claw", "Melee Attack Roll: +6, reach 5 ft. Hit: 8 (1d8 + 4) Slashing damage."),
        StatBlockFeature("Bite", "Melee Attack Roll: +6, reach 5 ft. Hit: 11 (2d6 + 4) Piercing damage plus "
                                 "3 (1d6) Fire damage."),
        StatBlockFeature("Breath (Recharge 5-6)", "Dexterity Saving Throw: DC 15. Failure: 27 (6d8) Fire "
                                                  "damage. Success: Half damage."),
    ])
    assert mc.action_damage(m.actions[2].description) == 14
    assert mc.damage_per_round(m) == 30           # 2 x 8 + 14, beats the 27 breath
    assert mc.best_attack_bonus(m) == 6
    assert mc.best_save_dc(m) == 15


def test_a_multiattack_that_names_no_attack_uses_the_best_one():
    m = brute(actions=[
        StatBlockFeature("Multiattack", "The giant makes two attacks, using Tree Club or Trash Lob in any combination."),
        StatBlockFeature("Tree Club", "Melee Attack Roll: +8. Hit: 18 (3d8 + 5) Bludgeoning damage."),
        StatBlockFeature("Trash Lob", "Ranged Attack Roll: +8. Hit: 16 (2d10 + 5) Bludgeoning damage."),
    ])
    assert mc.damage_per_round(m) == 36


def test_compare_monsters_says_which_is_better_for_each_number():
    a = brute(name="A", ac=15, hp=40, speeds={"walk": 30, "fly": 60}, damage_resistances=["Fire"],
              damage_vulnerabilities=["Cold"], senses=["Darkvision 60 ft."], languages=["Common"],
              traits=[StatBlockFeature("Legendary Resistance (3/Day)", "It succeeds instead.")])
    b = brute(name="B", ac=15, hp=60, speeds={"walk": 40}, damage_immunities=["Poison"],
              condition_immunities=["Poisoned"], languages=["None"])
    r = mc.compare_monsters(a, b)
    assert r["ac"] == 0
    assert r["hp"] == 1                     # B has more
    assert r["speed"] == -1                 # A's fly 60 is the fastest
    assert r["resistances"] == -1
    assert r["immunities"] == 1
    assert r["vulnerabilities"] == 1        # fewer is better
    assert r["senses"] == -1
    assert r["languages"] == -1             # "None" isn't a language
    assert r["legendary_resistance"] == -1
    assert set(r) == {m.key for m in mc.METRICS}


def test_the_monsters_page_compares_two_stat_blocks(tk_root):
    import customtkinter as ctk
    from ui.monster_view import MonsterView

    view = MonsterView(tk_root)
    view.pack(fill="both", expand=True)
    try:
        pump(tk_root)
        assert view.select_monster("Owlbear")
        view._context_monster = view.monster_manager.get_monster("Hill Giant")
        view._context_compare()
        pump(tk_root)
        assert view._compare_mode and view.compare_container.winfo_manager()
        block = view.detail_panel._stat_block
        assert block._other.name == "Hill Giant" and block._compare["hp"] == 1
        assert view.compare_detail._stat_block._compare["hp"] == -1

        def labels(w):
            out = []
            for c in w.winfo_children():
                if isinstance(c, ctk.CTkLabel):
                    out.append(c.cget("text"))
                out += labels(c)
            return out
        assert "Compared with Hill Giant" in labels(block)

        view._close_compare()
        pump(tk_root)
        assert not view._compare_mode and view.detail_panel._stat_block._other is None
        assert view.list_panel.winfo_manager()
    finally:
        view.destroy()
