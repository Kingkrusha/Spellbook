"""Tracker hub (saving, backends) and the row model the table draws."""

import json

import pytest

import initiative_rows as R
import initiative_sources as S
import initiative_state as T
from initiative_state import CommandError
from tracker_hub import TrackerHub


@pytest.fixture()
def hub(tmp_path):
    return TrackerHub(str(tmp_path / "state.json"))


def fill(hub):
    dm = hub.dm()
    dm.dispatch(S.custom("Ogre", hp=59, ac=11))
    dm.dispatch({"type": "add_entry", "kind": "player", "name": "Hero", "owner": "alice", "hp": 20,
                 "hp_max": 30, "ac": 16, "initiative": 18})
    dm.dispatch({"type": "add_entry", "kind": "player", "name": "Sidekick", "owner": "bob", "hp": 9,
                 "hp_max": 12, "ac": 13, "initiative": 12})
    dm.dispatch({"type": "add_entry", "kind": "custom", "name": "Lurker", "hp": 30, "ac": 15, "initiative": 14,
                 "hidden": True})
    dm.dispatch(S.event("Avalanche", 10))
    return dm


def test_state_is_saved_and_resumed(tmp_path):
    path = str(tmp_path / "state.json")
    hub = TrackerHub(path)
    assert not hub.resumed
    fill(hub)
    hub.dm().dispatch({"type": "start"})
    assert json.load(open(path, encoding="utf-8"))["started"] is True        # saved on every change

    again = TrackerHub(path)
    assert again.resumed
    assert [e.name for e in again.tracker.state.entries] == [e.name for e in hub.tracker.state.entries]
    assert again.tracker.state.started


def test_autosave_is_debounced_when_a_scheduler_is_given(tmp_path):
    jobs, cancelled = [], []
    hub = TrackerHub(str(tmp_path / "s.json"), schedule=lambda ms, fn: jobs.append(fn) or len(jobs),
                     cancel=cancelled.append)
    dm = hub.dm()
    dm.dispatch(S.custom("A"))
    dm.dispatch(S.custom("B"))
    assert len(jobs) == 1 and not (tmp_path / "s.json").exists()             # one pending save, nothing written
    jobs[0]()
    assert (tmp_path / "s.json").exists()
    dm.dispatch(S.custom("C"))
    assert hub.flush() is True and len(json.load(open(tmp_path / "s.json"))["entries"]) == 3   # flush saves now


def test_save_failure_is_reported_not_raised(tmp_path):
    hub = TrackerHub(str(tmp_path / "no-such-dir" / "deeper" / "s.json"))
    hub.path = str(tmp_path)                       # a directory: cannot be written as a file
    hub.dm().dispatch(S.custom("A"))
    assert hub.save_error and hub.flush() is False


def test_backends_enforce_who_may_do_what(hub):
    dm = fill(hub)
    alice = hub.player("alice")
    hero = next(r for r in alice.table().rows if r.name == "Hero")
    alice.dispatch({"type": "hp_delta", "id": hero.id, "delta": -5})
    assert next(r for r in dm.table().rows if r.name == "Hero").hp == 15
    side = next(r for r in alice.table().rows if r.name == "Sidekick")
    with pytest.raises(CommandError):
        alice.dispatch({"type": "hp_delta", "id": side.id, "delta": -5})
    with pytest.raises(CommandError):
        alice.dispatch({"type": "start"})
    assert alice.can_undo is False and dm.can_undo is True
    dm.undo()
    assert next(r for r in dm.table().rows if r.name == "Hero").hp == 20


def test_listeners_fire_for_every_viewer_and_can_be_removed(hub):
    dm, alice = hub.dm(), hub.player("alice")
    seen = []
    ping = lambda: seen.append(1)                  # noqa: E731
    alice.listen(ping)
    dm.dispatch(S.custom("A"))
    dm.dispatch(S.custom("B"))
    assert len(seen) == 2
    alice.unlisten(ping)
    dm.dispatch(S.custom("C"))
    assert len(seen) == 2


def test_owners_for_previewing_as_a_player(hub):
    dm = fill(hub)
    assert dict(dm.owners()) == {"alice": "Hero", "bob": "Sidekick"}


# ---------------------------------------------------------------- the row model

def test_dm_rows_show_everything(hub):
    dm = fill(hub)
    tv = dm.table()
    assert tv.role == "dm" and not tv.started
    names = [r.name for r in tv.rows]
    assert names == ["Hero", "Lurker", "Sidekick", "Avalanche", "Ogre"]       # stored order == display order
    lurker = next(r for r in tv.rows if r.name == "Lurker")
    assert lurker.hidden and lurker.hp == 30 and lurker.ac == 15 and lurker.can_edit
    event = next(r for r in tv.rows if r.is_event)
    assert event.ac is None and not event.can_edit


def test_player_rows_hide_what_they_should(hub):
    dm = fill(hub)
    dm.dispatch({"type": "set_settings", "monster_hp": "bar", "monster_ac": "hidden"})
    tv = hub.player("alice").table()
    assert [r.name for r in tv.rows] == ["Hero", "Sidekick", "Avalanche", "Ogre"]       # Lurker is hidden
    ogre = next(r for r in tv.rows if r.name == "Ogre")
    assert ogre.hp_mode == "bar" and ogre.hp_frac == 1.0 and ogre.ac is None and not ogre.can_edit
    hero = next(r for r in tv.rows if r.name == "Hero")
    assert (hero.mine, hero.can_edit, hero.hp, hero.hp_max, hero.ac) == (True, True, 20, 30, 16)
    assert tv.my_count == 1 and tv.can_add is True
    side = next(r for r in tv.rows if r.name == "Sidekick")
    assert not side.mine and not side.can_edit and side.hp == 9


def test_rotation_and_active_marker(hub):
    dm = fill(hub)
    dm.dispatch({"type": "start"})
    dm.dispatch({"type": "next_turn"})
    dm.dispatch({"type": "next_turn"})
    tv = dm.table()
    assert [r.name for r in tv.rows][0] == "Sidekick" and tv.rows[0].active
    assert tv.round == 1 and tv.started and tv.rotated
    assert tv.stored_order[0] != tv.active_id                                  # display is rotated from stored
    # dropping at the very end of the displayed list means "just before the active unit"
    assert R.move_before(tv, len(tv.rows)) == tv.active_id
    assert R.move_before(tv, 1) == tv.rows[1].id
    dm.dispatch({"type": "end"})
    assert R.move_before(dm.table(), 99) is None                                # not rotated: plain end


def test_group_brackets_and_labels(hub):
    dm = hub.dm()
    dm.dispatch(S.several(S.custom("Goblin", hp=7, ac=15), 3, group=True, group_name="Goblins"))
    dm.dispatch(S.custom("Ogre"))
    rows = dm.table().rows
    gob = [r for r in rows if r.name.startswith("Goblin")]
    assert [r.first_in_group for r in gob] == [True, False, False]
    assert [r.last_in_group for r in gob] == [False, False, True]
    assert {r.group_name for r in gob} == {"Goblins"} and {r.group_index for r in gob} == {0}
    assert rows[-1].group == "" and not rows[-1].first_in_group


def test_a_dragged_move_lands_where_it_was_dropped(hub):
    dm = fill(hub)
    dm.dispatch({"type": "start"})
    dm.dispatch({"type": "next_turn"})                                          # active is now Lurker
    tv = dm.table()
    names = [r.name for r in tv.rows]
    ogre = next(r for r in tv.rows if r.name == "Ogre")
    # dropping onto the active row puts it *before* that creature in turn order - which, in a table
    # rotated so the active creature is on top, is the very bottom (it acts last this round)
    dm.dispatch({"type": "move", "id": ogre.id, "before": R.move_before(tv, 0)})
    tv = dm.table()
    after = [r.name for r in tv.rows]
    assert after[0] == "Lurker" and after[-1] == "Ogre"
    # nothing was lost or duplicated, and the active creature is unchanged
    assert sorted(after) == sorted(names)
    assert next(r for r in tv.rows if r.active).name == "Lurker"
