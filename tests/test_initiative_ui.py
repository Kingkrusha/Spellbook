"""The tracker's screens, against a real (hidden) Tk root and a hub in a temp folder."""

import json
import time
import types

import pytest

import initiative_sources as S
import initiative_state as T
from tracker_hub import TrackerHub


def pump(root, seconds=0.1):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture()
def hub(tmp_path):
    return TrackerHub(str(tmp_path / "state.json"))


def fill(hub):
    dm = hub.dm()
    dm.dispatch({"type": "add_entry", "kind": "player", "name": "Hero", "owner": "alice", "hp": 20, "hp_max": 30,
                 "ac": 16, "initiative": 18})
    dm.dispatch(S.custom("Ogre", hp=59, ac=11))
    dm.dispatch({"type": "add_entry", "kind": "custom", "name": "Lurker", "hp": 9, "ac": 12, "initiative": 5,
                 "hidden": True})
    dm.dispatch(S.event("Avalanche", 10))
    return dm


class Settings:
    """Just enough of SettingsManager for the pop-up."""

    def __init__(self):
        self.settings = types.SimpleNamespace(tracker_window_state="", tracker_turn_beep=False)
        self.saved = []

    def update(self, **kw):
        for k, v in kw.items():
            setattr(self.settings, k, v)
        self.saved.append(kw)
        return True


def fake_event(state=0):
    return types.SimpleNamespace(state=state, x_root=10, y_root=10)


def test_table_updates_rows_in_place(tk_root, hub):
    from ui.initiative_table import InitiativeTable
    dm = fill(hub)
    table = InitiativeTable(tk_root, dm.hub.dm())
    try:
        # by initiative: Hero 18, Avalanche 10, Lurker 5 (hidden, but the DM sees it), Ogre unrolled last
        assert [r.name for r in table.view.rows] == ["Hero", "Avalanche", "Lurker", "Ogre"]
        ids = {r.name: r.id for r in table.view.rows}
        before = table.widget_of(ids["Hero"])
        dm.dispatch({"type": "hp_delta", "id": ids["Hero"], "delta": -5})
        pump(tk_root, 0.1)
        assert table.widget_of(ids["Hero"]) is before                      # same widget, new numbers
        assert "15 / 30" in before.hp_text.cget("text")
        dm.dispatch({"type": "remove", "id": ids["Ogre"]})
        pump(tk_root, 0.1)
        assert table.widget_of(ids["Ogre"]) is None
        assert len(table.view.rows) == 3
        assert table.widget_of(ids["Avalanche"]).is_event
    finally:
        table.destroy()


def test_dm_clicks_open_the_right_things(tk_root, hub):
    from ui.initiative_table import InitiativeTable, TableCallbacks
    dm = fill(hub)
    got = []
    cb = TableCallbacks(on_stats=lambda *a: got.append(("stats", a[0])),
                        on_conditions=lambda *a: got.append(("cond", a[0])),
                        on_initiative=lambda *a: got.append(("init", a[0])),
                        on_select=lambda ids: got.append(("select", set(ids))),
                        on_context=lambda *a: got.append(("menu", a[0])))
    table = InitiativeTable(tk_root, dm, cb)
    try:
        ogre = next(r for r in table.view.rows if r.name == "Ogre")
        w = table.widget_of(ogre.id)
        table._clicked(ogre.id, w.hp_text, fake_event())
        table._clicked(ogre.id, w.ac, fake_event())
        table._clicked(ogre.id, w.cond, fake_event())
        table._clicked(ogre.id, w.init, fake_event())
        assert got == [("stats", ogre.id), ("stats", ogre.id), ("cond", ogre.id), ("init", ogre.id)]

        got.clear()
        table._clicked(ogre.id, w.name, fake_event())                       # the name selects
        hero = next(r for r in table.view.rows if r.name == "Hero")
        table._clicked(hero.id, table.widget_of(hero.id).name, fake_event(state=0x0004))   # Ctrl adds
        assert got[-1] == ("select", {ogre.id, hero.id})
        table._right_clicked(ogre.id, fake_event())
        assert got[-1] == ("menu", ogre.id)

        # an event has no HP/AC/conditions to open - and its row is one spanning label
        ev = next(r for r in table.view.rows if r.is_event)
        assert table.widget_of(ev.id).hp_text is None
    finally:
        table.destroy()


def test_a_player_can_only_open_their_own_rows(tk_root, hub):
    from ui.initiative_table import InitiativeTable, TableCallbacks
    fill(hub)
    got = []
    table = InitiativeTable(tk_root, hub.player("alice"),
                            TableCallbacks(on_stats=lambda *a: got.append(("stats", a[0])),
                                           on_conditions=lambda *a: got.append(("cond", a[0])),
                                           on_initiative=lambda *a: got.append(("init", a[0]))))
    try:
        names = [r.name for r in table.view.rows]
        assert "Lurker" not in names                                        # hidden from players
        hero = next(r for r in table.view.rows if r.name == "Hero")
        ogre = next(r for r in table.view.rows if r.name == "Ogre")
        table._clicked(hero.id, table.widget_of(hero.id).hp_text, fake_event())
        table._clicked(hero.id, table.widget_of(hero.id).cond, fake_event())
        table._clicked(ogre.id, table.widget_of(ogre.id).hp_text, fake_event())      # not theirs: nothing
        table._clicked(hero.id, table.widget_of(hero.id).init, fake_event())         # only the DM sets initiative
        assert got == [("stats", hero.id), ("cond", hero.id)]
        assert table.widget_of(hero.id).tools is None                                # no DM tools on a player's row
    finally:
        table.destroy()


def test_compact_mode_hides_ac_and_shortens_conditions(tk_root, hub):
    from ui.initiative_table import InitiativeTable
    dm = fill(hub)
    ogre = next(r for r in dm.table().rows if r.name == "Ogre")
    dm.dispatch({"type": "add_condition", "id": ogre.id, "name": "Incapacitated"})
    table = InitiativeTable(tk_root, dm)
    try:
        w = table.widget_of(ogre.id)
        assert w.cond.cget("text") == "Incapacitated"
        table.set_compact(True)
        assert w.cond.cget("text") == "Incap"
        assert not w.ac.winfo_ismapped() or w.ac.grid_info() == {}
        table.set_compact(False)
        assert w.cond.cget("text") == "Incapacitated"
    finally:
        table.destroy()


def test_player_window_pins_and_announces_your_turn(tk_root, hub):
    from ui.initiative_window import InitiativeWindow
    dm = fill(hub)
    settings = Settings()
    win = InitiativeWindow(tk_root, hub.player("alice"), settings, kind="player")
    try:
        pump(tk_root, 1.1)                                                  # CTk's own setup, then our pin
        assert bool(win.attributes("-topmost")) is True
        assert win.banner.cget("text") == "Waiting to start"

        dm.dispatch({"type": "start"})
        pump(tk_root, 0.2)
        assert win.banner.cget("text") == "▶  YOUR TURN"                    # Hero (18) goes first
        assert "YOUR TURN" in win.title()
        dm.dispatch({"type": "next_turn"})
        pump(tk_root, 0.2)
        assert "YOUR TURN" not in win.banner.cget("text")
        assert "turn" in win.banner.cget("text")

        win._toggle_pin()
        assert bool(win.attributes("-topmost")) is False
        win._toggle_pin()
        assert bool(win.attributes("-topmost")) is True
    finally:
        win.close()
    saved = json.loads(settings.settings.tracker_window_state)["player"]
    assert saved["pinned"] is True and "x" in saved["geo"]


def test_player_window_offers_to_add_a_character_until_they_have_one(tk_root, hub):
    from ui.initiative_window import InitiativeWindow
    dm = hub.dm()
    dm.dispatch(S.custom("Ogre"))
    win = InitiativeWindow(tk_root, hub.player("bob"), Settings(), kind="player")
    try:
        pump(tk_root, 0.2)
        assert win.add_btn.winfo_manager() == "pack"
        hub.player("bob").dispatch({"type": "add_me", "name": "Bobby", "hp": 10, "hp_max": 10, "ac": 12,
                                    "init_bonus": 1})
        pump(tk_root, 0.2)
        assert win.add_btn.winfo_manager() == ""                            # already in: no button
        dm.dispatch({"type": "set_settings", "players_can_add": False})
        win2 = InitiativeWindow(tk_root, hub.player("carol"), Settings(), kind="player2")
        pump(tk_root, 0.2)
        assert win2.add_btn.winfo_manager() == ""
        win2.close()
    finally:
        win.close()


def test_dm_window_has_next_turn(tk_root, hub):
    from ui.initiative_window import InitiativeWindow
    fill(hub)
    win = InitiativeWindow(tk_root, hub.dm(), Settings(), kind="dm")
    try:
        pump(tk_root, 0.2)
        assert win.next_btn.winfo_manager() == "pack" and "Start" in win.next_btn.cget("text")
        win.next_btn.invoke()
        pump(tk_root, 0.2)
        assert hub.tracker.state.started and "Next turn" in win.next_btn.cget("text")
    finally:
        win.close()


def test_saved_window_position_is_kept_on_screen(tk_root, hub):
    from ui.initiative_window import InitiativeWindow
    settings = Settings()
    settings.settings.tracker_window_state = json.dumps({"player": {"geo": "500x400+9000+7000", "compact": True,
                                                                    "alpha": 0.8, "pinned": False}})
    win = InitiativeWindow(tk_root, hub.player(""), settings, kind="player")
    try:
        pump(tk_root, 0.2)
        x, y = win.winfo_x(), win.winfo_y()
        assert x < win.winfo_screenwidth() and y < win.winfo_screenheight()
        assert win.compact is True and win.pinned is False and abs(win.alpha - 0.8) < 0.01
    finally:
        win.close()


def test_dialog_parsing_helpers():
    from ui.initiative_dialogs import _to_int
    assert _to_int(" 12 ") == 12 and _to_int("-3") == -3
    assert _to_int("") is None and _to_int("x") is None and _to_int("1.5") is None
