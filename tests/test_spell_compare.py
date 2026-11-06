"""Spell compare mode: the damage a spell's dice add up to, and the colouring in the detail panel."""

import pytest

from spell import SpellComparison as S

FIREBALL = ("Each creature in a 20-foot-radius Sphere makes a Dexterity saving throw, taking 8d6 Fire damage on a "
            "failed save or half as much damage on a successful one.\n\nFlammable objects start burning.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d6 for each spell slot level above 3")
ICE_STORM = ("A creature takes 2d10 Bludgeoning damage and 4d6 Cold damage on a failed save or half as much damage "
             "on a successful one.\\Using a Higher-Level Spell Slot. The Bludgeoning damage increases by 1d10.")
TOLL = ("The target must succeed on a Wisdom saving throw or take 1d8 Necrotic damage. If the target is missing any "
        "of its Hit Points, it instead takes 1d12 Necrotic damage.\\Cantrip Upgrade. The damage increases by one "
        "die when you reach levels 5 (2d8 or 2d12), 11 (3d8 or 3d12), and 17 (4d8 or 4d12).")
GUARDIANS = ("On a failed save, the creature takes 3d8 Radiant damage (if you are good or neutral) or 3d8 Necrotic "
             "damage (if you are evil).")
MIND_SLIVER = ("The target must succeed on an Intelligence saving throw or take 1d6 Psychic damage and subtract 1d4 "
               "from the next saving throw it makes before the end of your next turn.")
ICE_KNIFE = ("On a hit, the target takes 1d10 Piercing damage. Hit or miss, the shard then explodes. Each creature "
             "within 5 feet of it must succeed on a Dexterity saving throw or take 2d6 Cold damage.")
FIRE_SHIELD = "The attacker takes 2d8 Fire damage from a warm shield or 2d8 Cold damage from a chill shield."
BLADES = "Each creature takes 1d6 Slashing damage or 2d4 Piercing damage, your choice, and 1d4 Force damage."


@pytest.mark.parametrize("text, terms", [
    (FIREBALL, [[(8, 6)]]),                       # the upcast paragraph after a line break doesn't count
    (ICE_STORM, [[(2, 10)], [(4, 6)]]),           # "and": both apply
    (TOLL, [[(1, 8), (1, 12)]]),                  # "instead": one or the other
    (GUARDIANS, [[(3, 8)]]),                      # "or" between the same dice
    (MIND_SLIVER, [[(1, 6)]]),                    # the 1d4 isn't damage
    (ICE_KNIFE, [[(1, 10)], [(2, 6)]]),           # "Hit or miss" isn't a choice between dice
    (FIRE_SHIELD, [[(2, 8)]]),
    (BLADES, [[(1, 6), (2, 4)], [(1, 4)]]),
])
def test_damage_terms_add_up_and_or_is_a_choice(text, terms):
    assert S.damage_terms(text) == terms


def test_the_summary_totals_the_dice_and_takes_the_bigger_choice():
    assert S.damage_summary(ICE_STORM) == "2d10 + 4d6 (6 dice, average 25, up to 44)"
    assert S.damage_summary(TOLL) == "1d8 or 1d12 (average 6.5, up to 12)"
    assert S.damage_summary(BLADES) == "(1d6 or 2d4) + 1d4 (average 7.5, up to 12)"
    assert S.damage_summary("No dice here.") == ""
    assert S.extract_damage_dice(TOLL) == [(1, 12)]


class _Spell:
    def __init__(self, description, tags=("Damage",)):
        self.description = description
        self.tags = list(tags)


def test_compare_damage_uses_every_die_and_ignores_upcasting():
    assert S.compare_damage(_Spell(ICE_STORM), _Spell(FIREBALL)) == 1     # 2d10+4d6 (44) < 8d6 (48)
    assert S.compare_damage(_Spell(FIREBALL), _Spell(FIREBALL)) == 0
    assert S.compare_damage(_Spell(TOLL), _Spell(ICE_KNIFE)) == 1        # 12 < 22
    assert S.compare_damage(_Spell(TOLL), _Spell(ICE_KNIFE, tags=())) == 0


def test_the_detail_panel_shows_the_damage_and_colours_the_dice(tk_root):
    import tkinter as tk
    import customtkinter as ctk
    from spell import Spell
    from ui.spell_detail import SpellDetailPanel

    def spell(name, description):
        return Spell(name=name, level=3, casting_time="Action", ritual=False, range_value=150,
                     components="V, S", duration="Instantaneous", concentration=False,
                     classes=[], description=description, tags=["Damage"])

    panel = SpellDetailPanel(tk_root, on_edit=lambda s: None, on_delete=lambda s: None, on_export=lambda s: None)
    panel.pack()
    try:
        storm, fireball = spell("Ice Storm", ICE_STORM), spell("Fireball", FIREBALL)
        panel.set_spell(storm)
        panel.apply_comparison(fireball)
        tk_root.update()

        def walk(w):
            yield w
            for c in w.winfo_children():
                yield from walk(c)

        widgets = list(walk(panel._description_content))
        labels = [w.cget("text") for w in widgets if isinstance(w, ctk.CTkLabel)]
        assert "Damage: 2d10 + 4d6 (6 dice, average 25, up to 44)" in labels
        texts = [w for w in widgets if isinstance(w, tk.Text)]
        marked = [w.get(*r) for w in texts for r in zip(*[iter(w.tag_ranges("highlight"))] * 2)]
        assert marked == ["2d10", "4d6"]           # the upcast paragraph's 1d10 isn't coloured

        panel.clear_comparison()
        tk_root.update()
        labels = [w.cget("text") for w in walk(panel._description_content) if isinstance(w, ctk.CTkLabel)]
        assert not any(str(t).startswith("Damage:") for t in labels)
    finally:
        panel.destroy()
