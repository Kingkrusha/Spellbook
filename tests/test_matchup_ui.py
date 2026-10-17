"""The Matchup page: picking two sides, the odds appearing, swapping, and errors being explained."""

import time
from types import SimpleNamespace

import pytest

from character import CharacterSpellList, ClassLevel
from character_rolls import Lookups
from character_sheet import AbilityScore, CharacterSheet
from monster import get_monster_manager


def settle(root, view, timeout=40.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if view._job is None and view._poll_job is None and (view.result is not None or "Pick" in view.status.cget("text")
                                                             or "must be" in view.status.cget("text")):
            root.update()
            return
        time.sleep(0.01)
    raise AssertionError("the page never produced a result")


def fighter():
    ch = CharacterSpellList(name="Fred", classes=[ClassLevel.from_dict({"class": "Fighter", "level": 5})])
    sheet = CharacterSheet(character_name="Fred")
    sheet.proficiency_bonus = 3
    sheet.armor_class = 18
    sheet.hit_points.maximum = sheet.hit_points.current = 49
    sheet.ability_scores.set(AbilityScore.STRENGTH, 18)
    sheet.attacks = [{"name": "Greatsword", "attack_bonus": "+7", "damage": "2d6+4 slashing"}]
    return ch, sheet


@pytest.fixture
def make_view(tk_root, monkeypatch):
    import customtkinter as ctk
    import ui.matchup_view as mv
    from ui.matchup_view import MatchupView
    monkeypatch.setattr(mv, "TRIALS", 400)               # plenty for the checks, and quick on a busy machine
    made = []

    def build(state=None):
        frame = ctk.CTkFrame(tk_root)
        frame.pack(fill="both", expand=True)
        tk_root.geometry("1300x900")
        monsters = get_monster_manager()
        view = MatchupView(frame, state if state is not None else {},
                           character_names=lambda: ["Fred"], load_character=lambda n: fighter() if n == "Fred" else None,
                           lookups=Lookups(class_def=lambda n: SimpleNamespace(spellcasting_ability="")),
                           monster_names=lambda: sorted(m.name for m in monsters.browsable),
                           get_monster=monsters.get_monster)
        view.pack(fill="both", expand=True)
        tk_root.update()
        made.append(frame)
        return view

    yield build
    for f in made:
        f.destroy()


def test_a_character_against_a_monster(tk_root, make_view):
    view = make_view({"a": {"kind": "Character", "character": "Fred"},
                      "b": {"kind": "Monster", "monster": "Owlbear"}})
    settle(tk_root, view)
    r = view.result
    assert r.a.side.name == "Fred" and r.b.side.name == "Owlbear"
    assert 0.1 < r.sim["a"] < 0.9 and r.sim["a"] + r.sim["b"] + r.sim["draw"] == pytest.approx(1)
    assert view.results.winfo_children()            # the odds, tables and tide turners were drawn


def test_custom_creatures_and_swapping(tk_root, make_view):
    view = make_view({"a": {"kind": "Custom", "c_name": "Brute", "c_ac": "13", "c_hp": "60", "c_bonus": "6",
                            "c_damage": "2d8+4", "c_attacks": "2", "c_type": "slashing"},
                      "b": {"kind": "Custom", "c_name": "Pixie", "c_ac": "16", "c_hp": "10", "c_bonus": "3",
                            "c_damage": "1d4", "c_attacks": "1", "c_range": "30"}})
    settle(tk_root, view)
    assert view.result.a.side.name == "Brute" and view.result.sim["a"] > 0.9
    view.result = None
    view._swap()
    settle(tk_root, view)
    assert view.result.a.side.name == "Pixie" and view.result.sim["b"] > 0.9


def test_searching_monsters_and_defences(tk_root, make_view):
    view = make_view({"a": {"kind": "Monster"}, "b": {"kind": "Custom"}})
    card = view.card_a
    card._widgets["monster_search"].insert(0, "troll")
    card._monster_search()
    names = card._widgets["monster_menu"].cget("values")
    assert names and all("troll" in n.lower() for n in names)
    settle(tk_root, view)
    assert view.result.a.side.regeneration == 15 or "Troll" in view.result.a.side.name
    view.result = None
    view.state["a"]["immune"] = "slashing"
    view.state["b"]["c_damage"] = "1d8+3"
    view.changed(now=True)
    settle(tk_root, view)
    assert "slashing" in view.result.a.side.immune


def test_characters_can_be_searched_and_hit_chances_are_shown(tk_root, make_view):
    view = make_view({"a": {"kind": "Character", "character": "Fred"}, "b": {"kind": "Monster", "monster": "Owlbear"}})
    card = view.card_a
    assert card._widgets["character_menu"].cget("values") == ["Fred"]
    card._widgets["character_search"].insert(0, "zzz")
    card._character_search()
    assert card._widgets["character_menu"].cget("values") == ["(no match)"]
    assert view.state["a"]["character"] == ""
    card._widgets["character_search"].delete(0, "end")
    card._widgets["character_search"].insert(0, "fre")
    card._character_search()
    assert card._widgets["character_menu"].cget("values") == ["Fred"] and view.state["a"]["character"] == "Fred"
    settle(tk_root, view)

    def texts(widget):
        out = []
        for child in widget.winfo_children():
            try:
                out.append(child.cget("text"))
            except Exception:
                pass
            out.extend(texts(child))
        return out

    shown = texts(view.results)
    assert any(t.startswith("Chance to hit Owlbear (AC 13): ") and t.endswith("%") for t in shown)
    assert any(t.startswith("Chance to hit Fred (AC 18): ") for t in shown)
    assert any(t.endswith("% to hit") and not t.startswith("Chance") for t in shown)        # a per-plan chance


def test_missing_input_is_explained(tk_root, make_view):
    view = make_view({"a": {"kind": "Monster", "monster_query": "zzzzzz"}, "b": {"kind": "Custom", "c_ac": "lots"}})
    tk_root.update()
    view._start()
    assert "Pick a monster" in view.status.cget("text")
    view.state["a"] = {"kind": "Custom"}
    view.card_a.state = view.state["a"]
    view._start()
    assert "Armor Class must be" in view.status.cget("text")
