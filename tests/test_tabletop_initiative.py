"""Tabletop tokens linked to the initiative tracker (tabletop_initiative.py)."""

import pytest

import initiative_state as I
import tabletop as T
from tabletop_initiative import InitiativeLink, active_entries


@pytest.fixture()
def world(tmp_path):
    table = T.Tabletop(str(tmp_path / "tabletop.json"))
    tracker = I.Tracker()
    scene = table.apply({"op": "scene_new", "scene_data": {"name": "Crypt", "w": 700, "h": 700}})["scene"]
    table.apply({"op": "scene_show", "scene": scene})
    link = InitiativeLink(table, tracker)
    return table, tracker, scene, link


def add_token(table, scene, **fields):
    data = {"name": "Goblin", "x": 35, "y": 35, "hp": 7, "hp_max": 7}
    data.update(fields)
    return table.apply({"op": "token_add", "scene": scene, "token": data})["token"]


def token(table, scene, tid):
    return next(t for t in table.scene(scene)["tokens"] if t["id"] == tid)


def test_adding_tokens_creates_linked_entries(world):
    table, tracker, scene, link = world
    gob = add_token(table, scene, conditions=["Prone"], hidden=True)
    hero = add_token(table, scene, name="Aria", kind="pc", owner="p1", hp=20, hp_max=24)
    add_token(table, scene, name="Barrel", kind="prop", hp=None, hp_max=None)
    assert [t["name"] for t in link.addable(scene)] == ["Goblin", "Aria"]

    assert link.add(scene, [t["id"] for t in table.scene(scene)["tokens"]]) == 2
    entries = {e.name: e for e in tracker.state.entries}
    assert entries["Goblin"].kind == I.KIND_MONSTER and entries["Goblin"].hidden
    assert [c["name"] for c in entries["Goblin"].conditions] == ["Prone"]
    assert entries["Aria"].kind == I.KIND_PLAYER and entries["Aria"].owner == "p1"
    assert (entries["Aria"].hp, entries["Aria"].hp_max) == (20, 24)
    assert token(table, scene, gob)["entry"] == entries["Goblin"].id
    assert token(table, scene, hero)["entry"] == entries["Aria"].id
    assert link.addable(scene) == []
    assert link.add(scene, [gob]) == 0                   # already in


def test_hp_and_conditions_follow_both_ways(world):
    table, tracker, scene, link = world
    gob = add_token(table, scene)
    link.add(scene, [gob])
    eid = token(table, scene, gob)["entry"]

    tracker.dispatch(I.DM, {"type": "hp_delta", "id": eid, "delta": -3})
    tracker.dispatch(I.DM, {"type": "add_condition", "id": eid, "name": "poisoned", "rounds": 3})
    t = token(table, scene, gob)
    assert t["hp"] == 4 and t["conditions"] == ["Poisoned"]

    table.apply({"op": "token_update", "scene": scene, "id": gob, "fields": {"hp": 1}})
    table.apply({"op": "token_condition", "scene": scene, "id": gob, "name": "Prone"})
    e = tracker.state.get(eid)
    assert e.hp == 1
    assert {c["name"]: c.get("rounds") for c in e.conditions} == {"Poisoned": 3, "Prone": None}  # rounds kept

    table.apply({"op": "token_update", "scene": scene, "id": gob, "fields": {"hp": 99}})
    assert tracker.state.get(eid).hp == 7 and token(table, scene, gob)["hp"] == 7   # clamped, both sides


def test_turn_ring_follows_the_active_unit(world):
    table, tracker, scene, link = world
    a = add_token(table, scene, name="Goblin")
    b = add_token(table, scene, name="Orc")
    link.add(scene, [a, b])
    for e, init in zip(tracker.state.entries, (15, 10)):
        tracker.dispatch(I.DM, {"type": "set_initiative", "id": e.id, "initiative": init})
    assert table.turn == ()
    link.next_turn()                                      # starts combat
    assert table.turn == tuple(active_entries(tracker.state))
    view = T.project(table.scene(scene), T.DM, turn=table.turn)
    assert {t["name"]: t["turn"] for t in view["scene"]["tokens"]} == {"Goblin": True, "Orc": False}
    link.next_turn()
    player = table.view_for("p1")["scene"]["tokens"]
    assert {t["name"]: t["turn"] for t in player} == {"Goblin": False, "Orc": True}
    assert all("entry" not in t and "source" not in t for t in player)    # bookkeeping stays with the DM


def test_removing_the_entry_unlinks_the_token(world):
    table, tracker, scene, link = world
    gob = add_token(table, scene)
    link.add(scene, [gob])
    tracker.dispatch(I.DM, {"type": "remove", "id": token(table, scene, gob)["entry"]})
    assert token(table, scene, gob)["entry"] == ""
    assert token(table, scene, gob)["hp"] == 7            # the token stays as it was

    link.add(scene, [gob])
    link.unlink(scene, gob, remove_entry=True)
    assert tracker.state.entries == [] and token(table, scene, gob)["entry"] == ""


def test_linking_is_not_undone_with_map_edits_and_copies_start_unlinked(world):
    table, tracker, scene, link = world
    gob = add_token(table, scene)
    link.add(scene, [gob])
    table.apply({"op": "token_move", "scene": scene, "id": gob, "x": 105, "y": 35})
    table.undo()                                          # undoes the move, not the link
    assert token(table, scene, gob)["entry"]
    copy_id = table.apply({"op": "scene_duplicate", "scene": scene})["scene"]
    assert all(not t["entry"] for t in table.scene(copy_id)["tokens"])


def test_catches_up_on_changes_made_while_unlinked(tmp_path, world):
    table, tracker, scene, link = world
    gob = add_token(table, scene)
    link.add(scene, [gob])
    link.close()
    tracker.dispatch(I.DM, {"type": "hp_delta", "id": token(table, scene, gob)["entry"], "delta": -5})
    assert token(table, scene, gob)["hp"] == 7
    InitiativeLink(table, tracker)
    assert token(table, scene, gob)["hp"] == 2


def test_lookup_supplies_real_stats(world):
    table, tracker, scene, _ = world
    _.close()
    link = InitiativeLink(table, tracker, lookup=lambda t: {"type": "add_entry", "kind": I.KIND_MONSTER,
                                                            "name": "Goblin", "ac": 15, "init_bonus": 2,
                                                            "source": {"type": "monster", "name": "Goblin"}})
    gob = add_token(table, scene, name="Goblin 2", hp=5, hp_max=7)
    link.add(scene, [gob])
    e = tracker.state.entries[0]
    assert (e.name, e.ac, e.init_bonus, e.hp, e.hp_max) == ("Goblin 2", 15, 2, 5, 7)
    assert e.source == {"type": "monster", "name": "Goblin"}
