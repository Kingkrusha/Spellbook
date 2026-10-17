"""The Dice Analyzer page: builder rows, text, character mode, and the chart, driven through the widgets."""

import time
from types import SimpleNamespace

import pytest

from character import CharacterSpellList, ClassLevel
from character_rolls import Lookups
from character_sheet import AbilityScore, CharacterSheet, Skill
from spell import CharacterClass


def settle(root, view, timeout=6.0):
    """Pump the event loop until the page has a result (or an error)."""
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if view.state["mode"] == "Character" and view._char_view() == "overview":
            if view._job is None:
                return
        elif view._job is None and view._poll_job is None and (
                view._analysis is not None or view.error_label.winfo_ismapped()):
            root.update()
            return
        time.sleep(0.01)
    raise AssertionError("the page never produced a result")


@pytest.fixture
def make_view(tk_root):
    import customtkinter as ctk
    from ui.dice_analyzer_view import DiceAnalyzerView
    made = []

    def build(state=None, characters=None, lookups=None):
        characters = characters if characters is not None else {}
        frame = ctk.CTkFrame(tk_root)
        frame.pack(fill="both", expand=True)
        tk_root.geometry("1300x860")
        view = DiceAnalyzerView(frame, state if state is not None else {},
                                character_names=lambda: list(characters),
                                load_character=lambda n: characters.get(n),
                                lookups=lookups or Lookups(class_def=lambda n: SimpleNamespace(spellcasting_ability="")))
        view.pack(fill="both", expand=True)
        tk_root.update()
        made.append(frame)
        return view

    yield build
    for f in made:
        f.destroy()


def rogue():
    ch = CharacterSpellList(name="Pip", lineage="Halfling", classes=[ClassLevel(CharacterClass.from_string("Rogue"), 7)])
    sheet = CharacterSheet(character_name="Pip")
    sheet.proficiency_bonus = 3
    sheet.ability_scores.set(AbilityScore.DEXTERITY, 18)
    sheet.skills.set(Skill.STEALTH, 2)
    sheet.attacks = [{"name": "Rapier", "attack_bonus": "+7", "damage": "1d8+4 piercing"}]
    return ch, sheet


def test_custom_roll_is_calculated_from_the_text(tk_root, make_view):
    view = make_view({"expr": "2d6+4"})
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() == pytest.approx(11)
    assert view._stat_labels["Average"].cget("text") == "11.00"
    assert "7" in view._stat_labels["Most likely"].cget("text") or "11" in view._stat_labels["Most likely"].cget("text")


def test_typing_a_roll_fills_in_the_builder_rows_and_back(tk_root, make_view):
    view = make_view({"expr": "d20"})
    settle(tk_root, view)
    view.expr.delete(0, "end")
    view.expr.insert(0, "3d8r1+1d4kh1-2")
    view._expr_typed()
    assert len(view._rows) == 2
    assert view._rows[0].count.get() == "3" and view._rows[0].sides.get() == "8" and view._rows[0].reroll.get() == "1"
    assert view.flat.get() == "-2"
    # editing a row rewrites the text
    view._rows[0].count.delete(0, "end")
    view._rows[0].count.insert(0, "5")
    view._rows_changed()
    assert view.expr.get().startswith("5d8")
    settle(tk_root, view)
    assert view._analysis is not None


def test_quick_dice_buttons_add_and_stack(tk_root, make_view):
    view = make_view({"expr": "1d4"})
    view._quick_add(4)
    view._quick_add(4)
    view._quick_add(6)
    assert [r.sides.get() for r in view._rows] == ["4", "6"] and view._rows[0].count.get() == "3"
    assert view.expr.get() == "3d4+1d6"


def test_bad_input_is_explained_not_crashed(tk_root, make_view):
    view = make_view({"expr": "2d6"})
    settle(tk_root, view)
    view.expr.delete(0, "end")
    view.expr.insert(0, "2d6++")
    view._expr_typed()
    settle(tk_root, view)
    assert view.error_label.cget("text")
    view._rows[0].count.delete(0, "end")
    view._rows[0].count.insert(0, "many")
    view._rows_changed()
    settle(tk_root, view)
    assert "whole number" in view.error_label.cget("text")


def test_big_rolls_come_back(tk_root, make_view):
    view = make_view({"expr": "1000d20+4-12"})
    settle(tk_root, view, timeout=30)
    d = view._analysis.views[0].dist
    assert d.mean() == pytest.approx(10500 - 8) and not d.approx


def test_roll_twice_option(tk_root, make_view):
    view = make_view({"expr": "2d6+3"})
    settle(tk_root, view)
    base = view._analysis.views[0].dist.mean()
    view.twice.set("Roll twice, keep higher")
    view._twice_changed("Roll twice, keep higher")
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() > base


def test_character_mode_opens_on_a_bar_overview_of_saves_and_skills(tk_root, make_view):
    view = make_view({"mode": "Character"}, {"Pip": rogue()})
    settle(tk_root, view)
    assert view._char_view() == "overview" and view.overview.winfo_manager() and not view.detail.winfo_manager()
    (saves_title, saves), (skills_title, skills) = view.ov_chart.sections
    assert (saves_title, len(saves)) == ("Saving throws", 6) and (skills_title, len(skills)) == ("Skills", 18)
    stealth = next(r for r in skills if r.key == "skill:STEALTH")
    assert stealth.tag == "◆" and stealth.value == pytest.approx(12.8875 + 4 + 6)       # Reliable Talent and Halfling Luck
    arcana = next(r for r in skills if r.key == "skill:ARCANA")
    assert arcana.tag == "" and arcana.value == pytest.approx(10.975)                    # Halfling Luck only
    # the median can be shown instead
    view.metric_switch.set("Median")
    view._metric_changed("Median")
    skills = view.ov_chart.sections[1][1]
    assert next(r for r in skills if r.key == "skill:ARCANA").value == 11
    assert view.ov_chart.unit == "median"


def test_overview_buttons_for_other_rolls(tk_root, make_view):
    view = make_view({"mode": "Character"}, {"Pip": rogue()})
    settle(tk_root, view)
    shown = [k for k, b in view._ov_button_widgets.items() if b.winfo_manager()]
    assert shown == ["Attacks", "Initiative", "Checks"]          # no spells, so no Spells / Concentration
    view._open_group("Attacks")
    settle(tk_root, view)
    assert view._char_view() == "detail" and view.detail.winfo_manager() and not view.overview.winfo_manager()
    assert [v.key for v in view._analysis.views] == ["attack", "damage", "per_attack"]     # one attack per turn
    view._show_overview()
    assert view._char_view() == "overview"


def test_spellcasters_get_spell_and_concentration_buttons(tk_root, make_view):
    from character_rolls import Lookups
    ch = CharacterSpellList(name="Wiz", classes=[ClassLevel(CharacterClass.from_string("Wizard"), 5)])
    sheet = CharacterSheet(character_name="Wiz")
    sheet.proficiency_bonus = 3
    sheet.ability_scores.set(AbilityScore.INTELLIGENCE, 18)
    sheet.ability_scores.set(AbilityScore.CONSTITUTION, 14)
    sheet.saving_throws.set_proficiency(AbilityScore.CONSTITUTION, True)
    ch.known_spells = ["Fire Bolt"]
    fire_bolt = SimpleNamespace(name="Fire Bolt", level=0,
                                description="Make a ranged spell attack. On a hit, the target takes 1d10 Fire damage.")
    import customtkinter as ctk
    from ui.dice_analyzer_view import DiceAnalyzerView
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    view = DiceAnalyzerView(frame, {"mode": "Character"}, lambda: ["Wiz"], lambda n: (ch, sheet),
                            Lookups(spell={"Fire Bolt": fire_bolt}.get,
                                    class_def=lambda n: SimpleNamespace(spellcasting_ability="INT")))
    view.pack(fill="both", expand=True)
    settle(tk_root, view)
    shown = [k for k, b in view._ov_button_widgets.items() if b.winfo_manager()]
    assert shown == ["Spells", "Concentration", "Initiative", "Checks"]
    view._open_group("Concentration")
    settle(tk_root, view)
    assert view._roll.key == "save:CON:concentration"
    assert view._analysis.views[0].dist.mean() == pytest.approx(10.5 + 2 + 3)          # CON +2, proficiency +3
    frame.destroy()


def test_clicking_a_bar_opens_the_roll_with_its_options(tk_root, make_view):
    view = make_view({"mode": "Character"}, {"Pip": rogue()})
    settle(tk_root, view)
    view._open_roll("skill:STEALTH")
    settle(tk_root, view)
    assert view._roll.key == "skill:STEALTH" and view.state["category"] == "Skills"
    d = view._analysis.views[0].dist
    assert d.support()[0] == 10 + 4 + 6                          # Reliable Talent floor + DEX + expertise
    assert any("Reliable Talent" in n for n in view._analysis.notes)


def test_overview_situation_carries_into_the_opened_roll(tk_root, make_view):
    ch = CharacterSpellList(name="Bear", classes=[ClassLevel(CharacterClass.from_string("Barbarian"), 3)])
    sheet = CharacterSheet(character_name="Bear")
    sheet.ability_scores.set(AbilityScore.STRENGTH, 18)
    view = make_view({"mode": "Character"}, {"Bear": (ch, sheet)})
    settle(tk_root, view)
    calm = next(r for r in view.ov_chart.sections[1][1] if r.key == "skill:STEALTH").value
    view._ov_vars["rage"].set(True)
    view._overview_option("rage", True)
    raging = next(r for r in view.ov_chart.sections[1][1] if r.key == "skill:STEALTH").value
    assert calm == pytest.approx(10.5) and raging == pytest.approx(13.825 + 4)          # Strength with advantage
    view._open_roll("skill:STEALTH")
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() == pytest.approx(13.825 + 4)
    assert view._opt_vars["rage"].get() is True


def test_skill_ability_can_be_changed_and_bonus_dice_added(tk_root, make_view):
    ch, sheet = rogue()
    sheet.ability_scores.set(AbilityScore.STRENGTH, 20)
    view = make_view({"mode": "Character"}, {"Pip": (ch, sheet)})
    settle(tk_root, view)
    view._open_roll("skill:INTIMIDATION")
    settle(tk_root, view)
    base = view._analysis.views[0].dist.mean()
    assert "Based on" in [o.label for o in view._roll.options]
    # switch the ability menu to Strength through the widget
    menu_getters = view._option_widgets
    assert menu_getters["ability"]() == "CHA"
    view.options_frame.update()
    ability_menu = next(w for w in _all_widgets(view.options_frame)
                        if w.__class__.__name__ == "CTkOptionMenu" and w.get() == "CHA")
    ability_menu.set("STR")
    view._option_changed(None)
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() == pytest.approx(base + 5)              # STR +5 instead of CHA +0
    # bonus dice: add Bardic Inspiration then Mind Sliver (subtracts)
    dice = view._bonus_lists["bonus_dice"]
    dice._add_preset("Bardic Inspiration (d8)")
    dice._add_preset("Mind Sliver (-d4)")
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() == pytest.approx(base + 5 + 4.5 - 2.5)
    assert [r["sign"] for r in dice.value()] == [1, -1]
    dice._remove(dice.rows[0])
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() == pytest.approx(base + 5 - 2.5)


def _all_widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from _all_widgets(child)


def test_switching_between_views_and_options(tk_root, make_view):
    view = make_view({"mode": "Character"}, {"Pip": rogue()})
    settle(tk_root, view)
    view._open_roll("attack:0")
    settle(tk_root, view)
    view._pick_view("Damage per attack")
    assert view._view_key == "per_attack"
    before = view._analysis.views[2].dist.mean()
    view._opt_vars["sneak"].set(True)
    view._option_changed(None)
    settle(tk_root, view)
    assert view._analysis.views[2].dist.mean() > before + 10


def test_manual_feature_toggles_rebuild_the_rolls(tk_root, make_view):
    ch, sheet = rogue()
    view = make_view({"mode": "Character"}, {"Pip": (ch, sheet)})
    settle(tk_root, view)
    view._toggle_features()
    assert "alert" in view._feature_vars
    view._feature_vars["alert"].set(True)
    view._features_changed()
    assert view.state["manual"]["Pip"] == ["alert"]
    view._open_group("Initiative")
    settle(tk_root, view)
    assert any("Alert" in n for n in view._analysis.notes)


def test_no_characters_is_handled(tk_root, make_view):
    view = make_view({"mode": "Character"}, {})
    tk_root.update()
    view._compute()
    tk_root.update()
    assert "No character" in view.ov_title.cget("text")


def test_switching_to_character_mode_goes_to_the_overview(tk_root, make_view):
    view = make_view({"mode": "Character", "char_view": "detail"}, {"Pip": rogue()})
    view._open_roll("attack:0")
    view._set_mode("Custom")
    view._set_mode("Character")
    assert view._char_view() == "overview"


def test_state_survives_rebuilding_the_page(tk_root, make_view):
    state = {}
    first = make_view(state)
    first.expr.delete(0, "end")
    first.expr.insert(0, "4d6kh3")
    first._expr_typed()
    second = make_view(state)
    assert second.expr.get() == "4d6kh3" and len(second._rows) == 1 and second._rows[0].keep.get() == "Highest"


def test_chart_draws_every_mode_without_errors(tk_root, make_view):
    from dice_analyzer import parse_expression
    from ui.distribution_chart import DistributionChart
    import customtkinter as ctk
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    chart = DistributionChart(frame, height=300, width=700)
    chart.pack()
    tk_root.update()
    chart.winfo_width, chart.winfo_height = (lambda: 700), (lambda: 300)      # a withdrawn root reports 1x1
    for text in ("d20", "2d6+4", "300d6", "d20adv-3", "d4"):
        d = parse_expression(text).distribution()
        for cumulative in (False, True):
            chart.set_dist(d, cumulative=cumulative, target=10)
            tk_root.update()
            chart._draw()
            assert chart.find_all()
    chart._hover = 2
    chart._draw()
    chart.set_dist(None)
    chart._draw()
    frame.destroy()


def test_the_custom_builder_has_double_advantage_and_emphasis(tk_root, make_view):
    view = make_view({"expr": "d20emph+3"})
    settle(tk_root, view)
    assert view._rows[0].kind.get() == "Emphasis"
    assert view._analysis.views[0].dist.mean() == pytest.approx(14.2)
    view._rows[0].kind.set("Double advantage")
    view._rows_changed()
    assert view.expr.get() == "1d20dadv+3"
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() == pytest.approx(18.4875)
    view._rows[0].kind.set("Double disadvantage")
    view._rows_changed()
    assert view.expr.get() == "1d20ddis+3"


def test_overview_modes_include_double_advantage_and_emphasis(tk_root, make_view):
    view = make_view({"mode": "Character"}, {"Pip": rogue()})
    settle(tk_root, view)
    view._overview_option("mode", "Double advantage")
    arcana = next(r for r in view.ov_chart.sections[1][1] if r.key == "skill:ARCANA").value
    assert arcana > 13.8
    view._overview_option("mode", "Emphasis")
    assert next(r for r in view.ov_chart.sections[1][1] if r.key == "skill:ARCANA").value > 10.9


def test_linked_magic_items_are_listed_and_can_be_switched_off(tk_root, make_view):
    from magic_item import get_magic_item_manager
    ch, sheet = rogue()
    sheet.magic_items = [{"name": "Cloak of Protection", "attuned": True, "requires_attunement": True},
                         {"name": "Ring of Protection", "attuned": False, "requires_attunement": True}]
    lookups = Lookups(class_def=lambda n: SimpleNamespace(spellcasting_ability=""),
                      magic_item=lambda n: get_magic_item_manager().get_item(n))
    view = make_view({"mode": "Character"}, {"Pip": (ch, sheet)}, lookups)
    settle(tk_root, view)
    wis = lambda: next(r for r in view.ov_chart.sections[0][1] if r.key == "save:WIS").value
    base = wis()
    assert base == pytest.approx(10.975 + 1)                  # Halfling Luck, +1 from the attuned cloak only
    view._toggle_features()
    assert set(view._item_vars) == {"Cloak of Protection", "Ring of Protection"}
    assert view._item_vars["Cloak of Protection"].get() is True and view._item_vars["Ring of Protection"].get() is False
    view._item_vars["Cloak of Protection"].set(False)
    view._items_changed()
    settle(tk_root, view)
    assert wis() == pytest.approx(10.975)
    assert view.state["items_off"]["Pip"] == ["Cloak of Protection"]


def test_save_against_choice_appears_for_characters_with_conditional_advantage(tk_root, make_view):
    ch = CharacterSpellList(name="Eli", lineage="Elf", classes=[ClassLevel.from_dict({"class": "Fighter", "level": 1})])
    sheet = CharacterSheet(character_name="Eli")
    view = make_view({"mode": "Character"}, {"Eli": (ch, sheet)})
    settle(tk_root, view)
    view._open_roll("save:WIS")
    settle(tk_root, view)
    assert "Save against" in [o.label for o in view._roll.options]
    base = view._analysis.views[0].dist.mean()
    ctk_menu = next(w for w in _all_widgets(view.options_frame)
                    if w.__class__.__name__ == "CTkOptionMenu" and w.get() == "Anything else")
    ctk_menu.set("Charmed")
    view._option_changed(None)
    settle(tk_root, view)
    assert view._analysis.views[0].dist.mean() > base + 3


def test_the_features_list_can_be_searched(tk_root, make_view):
    view = make_view({"mode": "Character"}, {"Pip": rogue()})
    settle(tk_root, view)
    view._toggle_features()
    assert "alert" in view._feature_vars and "danger_sense" not in view._feature_vars     # the short list
    view.feature_search.insert(0, "danger")
    view._feature_search_typed()
    view._render_features_body()
    assert list(view._feature_vars) == ["danger_sense"]                                    # any feature can be found
    view._feature_vars["danger_sense"].set(True)
    view._features_changed()
    assert view.state["manual"]["Pip"] == ["danger_sense"]
    view.feature_search.delete(0, "end")
    view.feature_search.insert(0, "zzzz")
    view._feature_search_typed()
    view._render_features_body()
    assert not view._feature_vars and not view._item_vars
    # ticked features survive being filtered out
    view.feature_search.delete(0, "end")
    view._feature_search_typed()
    view._render_features_body()
    assert "alert" in view._feature_vars
    assert view.state["manual"]["Pip"] == ["danger_sense"]
