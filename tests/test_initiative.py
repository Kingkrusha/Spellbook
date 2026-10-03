"""Initiative tracker rules: ordering, turns, groups, authorization, visibility, saving."""

import json
import random

import pytest

import conditions as C
import initiative_sources as S
import initiative_state as T
from initiative_state import Actor, CommandError, DM, TrackerState, apply, project


def ids():
    """Predictable entry ids for tests: e1, e2, ..."""
    n = [0]

    def make():
        n[0] += 1
        return f"e{n[0]}"
    return make


class Table:
    """A tiny driver so tests read like a DM at the table."""

    def __init__(self, **settings):
        self.state = TrackerState()
        self.state.settings = T.Settings(**settings)
        self.mk = ids()

    def do(self, cmd, actor=DM, rng=None):
        self.state = apply(self.state, actor, cmd, rng=rng, new_id=self.mk)
        return self.state

    def add(self, name, initiative=None, kind="monster", **kw):
        self.do({"type": "add_entry", "kind": kind, "name": name, "initiative": initiative,
                 "hp": kw.pop("hp", 10), "ac": kw.pop("ac", 12), **kw})
        return self.state.last_added[0]

    def names(self):
        return [e.name for e in T.display_order(self.state)]

    def stored(self):
        return [e.name for e in self.state.entries]


class FixedRng(random.Random):
    def __init__(self, values):
        super().__init__()
        self.values = list(values)

    def randint(self, a, b):
        return self.values.pop(0)


# ---------------------------------------------------------------- adding and ordering

def test_entries_are_inserted_in_initiative_order_ties_after():
    t = Table()
    t.add("Low", 5)
    t.add("High", 20)
    t.add("Mid", 12)
    t.add("Mid2", 12)
    t.add("Unrolled")
    t.add("Last", 1)
    assert t.stored() == ["High", "Mid", "Mid2", "Low", "Last", "Unrolled"]


def test_unrolled_entries_sit_after_rolled_ones():
    t = Table()
    t.add("Unrolled")
    t.add("Rolled", 8)
    assert t.stored() == ["Rolled", "Unrolled"]


def test_duplicate_monsters_are_numbered():
    t = Table()
    t.do({"type": "add_entry", "kind": "monster", "name": "Goblin", "hp": 7, "ac": 15, "count": 3})
    assert t.stored() == ["Goblin 1", "Goblin 2", "Goblin 3"]
    t.add("Goblin")
    assert t.stored()[-1] == "Goblin 4"
    t.add("Ogre")
    t.add("Ogre")
    assert t.stored()[-2:] == ["Ogre", "Ogre 2"]


def test_add_many_can_be_grouped_and_share_initiative():
    t = Table()
    t.add("Hero", 15)
    t.do({"type": "add_entry", "kind": "monster", "name": "Goblin", "hp": 7, "ac": 15, "count": 3,
          "group": True, "initiative": 12})
    gobs = [e for e in t.state.entries if e.name.startswith("Goblin")]
    assert len({e.group for e in gobs}) == 1 and gobs[0].group
    assert [len(u) for u in T.units(t.state)] == [1, 3]


def test_add_validation():
    t = Table()
    for bad in ({"kind": "wizard", "name": "x"}, {"kind": "monster", "name": "  "},
                {"kind": "monster", "name": "x", "hp": "lots"}):
        with pytest.raises(CommandError):
            t.do({"type": "add_entry", **bad})
    t.do({"type": "add_entry", "kind": "monster", "name": "x", "hp": 5, "hp_max": 3})
    assert t.state.entries[0].hp == 3                       # hp is capped at max
    with pytest.raises(CommandError):
        t.do({"type": "add_entry", "kind": "monster", "name": "x", "count": 51})
    for i in range(T.MAX_ENTRIES - 1):
        t.add(f"m{i}")
    with pytest.raises(CommandError) as exc:
        t.do({"type": "add_entry", "kind": "monster", "name": "one more", "count": 5})
    assert exc.value.code == "too_many"


def test_sort_and_roll_initiative():
    t = Table()
    a = t.add("A", init_bonus=2)
    b = t.add("B", init_bonus=5)
    c = t.add("C", 11, init_bonus=0)
    t.do({"type": "roll_initiative"}, rng=FixedRng([10, 6]))        # A: 10+2=12, B: 6+5=11
    assert (t.state.get(a).initiative, t.state.get(b).initiative) == (12, 11)
    # B (11, bonus 5) beats C (11, bonus 0) on the tiebreak
    assert t.stored() == ["A", "B", "C"]
    t.do({"type": "roll_initiative", "only_missing": False}, rng=FixedRng([1, 1, 1]))   # A, B and C all reroll
    assert t.state.get(c).initiative is not None


def test_group_rolls_once():
    t = Table()
    t.do({"type": "add_entry", "kind": "monster", "name": "Goblin", "count": 3, "group": True, "init_bonus": 2})
    t.do({"type": "roll_initiative"}, rng=FixedRng([9]))             # exactly one d20 for the group
    assert {e.initiative for e in t.state.entries} == {11}


def test_set_initiative_repositions():
    t = Table()
    t.add("A", 20)
    t.add("B", 10)
    c = t.add("C", 5)
    t.do({"type": "set_initiative", "id": c, "value": 15})
    assert t.stored() == ["A", "C", "B"]
    t.do({"type": "set_initiative", "id": c, "value": None})
    assert t.stored() == ["A", "B", "C"]


def test_move_units():
    t = Table()
    a, b, c, d = (t.add(n, 20 - i) for i, n in enumerate("ABCD"))
    t.do({"type": "move", "id": d, "before": a})
    assert t.stored() == ["D", "A", "B", "C"]
    t.do({"type": "move", "id": d, "before": None})
    assert t.stored() == ["A", "B", "C", "D"]
    t.do({"type": "move", "id": a, "before": c})
    assert t.stored() == ["B", "A", "C", "D"]
    t.do({"type": "move", "id": a, "before": c})                    # already there: no-op
    assert t.stored() == ["B", "A", "C", "D"]


# ---------------------------------------------------------------- turns

def table_with_four():
    t = Table()
    for i, n in enumerate(["A", "B", "C", "D"]):
        t.add(n, 20 - i)
    return t


def test_next_turn_rotates_the_table_and_counts_rounds():
    t = table_with_four()
    assert t.state.started is False and t.names() == ["A", "B", "C", "D"]
    t.do({"type": "start"})
    assert (t.state.round, t.names()) == (1, ["A", "B", "C", "D"])
    t.do({"type": "next_turn"})
    assert t.names() == ["B", "C", "D", "A"]                        # B on top, the one who went is at the bottom
    assert t.stored() == ["A", "B", "C", "D"]                       # stored order never rotates
    t.do({"type": "next_turn"}); t.do({"type": "next_turn"})
    assert (t.names()[0], t.state.round) == ("D", 1)
    t.do({"type": "next_turn"})
    assert (t.names()[0], t.state.round) == ("A", 2)


def test_next_turn_starts_combat_if_needed_and_prev_turn_goes_back():
    t = table_with_four()
    t.do({"type": "next_turn"})
    assert t.state.started and t.names()[0] == "A"
    t.do({"type": "next_turn"})
    t.do({"type": "prev_turn"})
    assert t.names()[0] == "A" and t.state.round == 1
    t.do({"type": "prev_turn"})                                     # wraps back to the end of the "round before"
    assert t.names()[0] == "D" and t.state.round == 1
    with pytest.raises(CommandError):
        Table().do({"type": "prev_turn"})
    with pytest.raises(CommandError):
        Table().do({"type": "start"})


def test_end_resets():
    t = table_with_four()
    t.do({"type": "start"}); t.do({"type": "next_turn"})
    t.do({"type": "end"})
    assert (t.state.started, t.state.round, t.state.active) == (False, 0, "")
    assert t.names() == ["A", "B", "C", "D"]


def test_a_group_takes_its_turn_together():
    t = Table()
    a = t.add("A", 20)
    g1 = t.add("G1", 15)
    g2 = t.add("G2", 14)
    d = t.add("D", 5)
    t.do({"type": "group", "ids": [g1, g2], "name": "Goblins"})
    assert t.stored() == ["A", "G1", "G2", "D"] and t.state.get(g2).initiative == 15
    t.do({"type": "start"}); t.do({"type": "next_turn"})
    assert t.names() == ["G1", "G2", "D", "A"]                      # both at the top together
    assert t.state.active == g1
    t.do({"type": "next_turn"})
    assert t.names()[0] == "D"
    t.do({"type": "ungroup", "id": g1})
    assert not any(e.group for e in t.state.entries)


def test_grouping_validation_and_old_groups_dissolve():
    t = Table()
    a, b, c = (t.add(n, 10) for n in "ABC")
    with pytest.raises(CommandError):
        t.do({"type": "group", "ids": [a]})
    t.do({"type": "group", "ids": [a, b]})
    t.do({"type": "group", "ids": [b, c]})                          # b leaves A's group; A is left alone
    groups = [(e.name, bool(e.group)) for e in t.state.entries]
    assert groups == [("A", False), ("B", True), ("C", True)]
    assert t.state.entries[1].group == t.state.entries[2].group


def test_defeated_units_are_skipped():
    t = table_with_four()
    t.do({"type": "start"})
    b = t.state.entries[1].id
    t.do({"type": "set_stats", "id": b, "hp": 0})                   # a monster at 0 is defeated
    assert t.state.get(b).defeated
    t.do({"type": "next_turn"})
    assert t.names()[0] == "C"
    t.do({"type": "set_settings", "skip_defeated": False})
    t.do({"type": "prev_turn"})
    assert t.names()[0] == "A" or t.names()[0] == "B"


def test_adding_mid_combat_does_not_change_whose_turn_it_is():
    t = table_with_four()
    t.do({"type": "start"}); t.do({"type": "next_turn"}); t.do({"type": "next_turn"})
    assert t.names()[0] == "C"
    t.add("Newcomer", 25)                                           # lands above everyone, before the active unit
    assert t.names()[0] == "C" and t.state.round == 1
    t.add("Late", 1)
    assert t.names()[0] == "C"


def test_removing_the_active_combatant_passes_the_turn_without_a_round():
    t = table_with_four()
    t.do({"type": "start"}); t.do({"type": "next_turn"})
    b = t.state.active
    t.do({"type": "remove", "id": b})
    assert t.names()[0] == "C" and t.state.round == 1
    d = t.state.entries[-1].id
    t.do({"type": "next_turn"}); t.do({"type": "next_turn"})        # D then wrap
    assert t.state.round == 2
    t.do({"type": "remove", "ids": [e.id for e in t.state.entries]})
    assert (t.state.started, t.state.active) == (False, "")


# ---------------------------------------------------------------- hp, conditions, authorization

def test_damage_uses_temp_hp_first_and_healing_caps_at_max():
    t = Table()
    m = t.add("Ogre", 10, hp=30, hp_temp=5)
    t.do({"type": "hp_delta", "id": m, "delta": -8})
    e = t.state.get(m)
    assert (e.hp_temp, e.hp) == (0, 27)
    t.do({"type": "hp_delta", "id": m, "delta": +100})
    assert t.state.get(m).hp == 30
    t.do({"type": "hp_delta", "id": m, "delta": -500})
    e = t.state.get(m)
    assert e.hp == 0 and e.defeated
    t.do({"type": "hp_delta", "id": m, "delta": 3})
    assert not t.state.get(m).defeated


def test_players_at_zero_are_not_defeated():
    t = Table()
    p = t.add("Hero", 10, kind="player", owner="alice", hp=10)
    t.do({"type": "hp_delta", "id": p, "delta": -99}, actor=Actor("player", "alice"))
    assert t.state.get(p).hp == 0 and not t.state.get(p).defeated


def test_conditions():
    t = Table()
    m = t.add("Ogre", 10)
    t.do({"type": "add_condition", "id": m, "name": "poisoned", "rounds": 3})
    t.do({"type": "add_condition", "id": m, "name": "Exhaustion", "level": 9})
    t.do({"type": "add_condition", "id": m, "name": "Cursed by the lich"})
    t.do({"type": "add_condition", "id": m, "name": "POISONED"})    # same condition again replaces it
    conds = t.state.get(m).conditions
    assert [C.label(c) for c in conds] == ["Exhaustion 6", "Cursed by the lich", "Poisoned"]
    t.do({"type": "remove_condition", "id": m, "name": "exhaustion"})
    assert len(t.state.get(m).conditions) == 2
    t.do({"type": "set_conditions", "id": m, "conditions": ["Prone", {"name": ""}, "prone", 5]})
    assert [c["name"] for c in t.state.get(m).conditions] == ["Prone"]
    with pytest.raises(CommandError):
        t.do({"type": "add_condition", "id": m, "name": "   "})


def test_players_can_only_touch_their_own_stats():
    t = Table()
    mine = t.add("Hero", 10, kind="player", owner="alice", hp=20, ac=15)
    other = t.add("Ally", 9, kind="player", owner="bob", hp=20)
    ogre = t.add("Ogre", 8)
    alice = Actor("player", "alice")
    t.do({"type": "set_stats", "id": mine, "hp": 5, "ac": 17, "hp_temp": 3}, actor=alice)
    assert (t.state.get(mine).hp, t.state.get(mine).ac, t.state.get(mine).hp_temp) == (5, 17, 3)
    t.do({"type": "add_condition", "id": mine, "name": "Prone"}, actor=alice)
    for target in (other, ogre):
        for cmd in ({"type": "set_stats", "id": target, "hp": 1}, {"type": "hp_delta", "id": target, "delta": -1},
                    {"type": "add_condition", "id": target, "name": "Prone"}):
            with pytest.raises(CommandError) as exc:
                t.do(cmd, actor=alice)
            assert exc.value.code == "forbidden"
    assert t.state.get(other).hp == 20 and t.state.get(ogre).hp == 10


@pytest.mark.parametrize("cmd", [
    {"type": "add_entry", "kind": "monster", "name": "x"}, {"type": "remove", "id": "e1"},
    {"type": "clear"}, {"type": "sort"}, {"type": "start"}, {"type": "next_turn"}, {"type": "end"},
    {"type": "move", "id": "e1", "before": None}, {"type": "group", "ids": ["e1", "e2"]},
    {"type": "set_hidden", "id": "e1", "hidden": True}, {"type": "set_initiative", "id": "e1", "value": 30},
    {"type": "set_field", "id": "e1", "field": "owner", "value": "alice"},
    {"type": "set_settings", "monster_hp": "hidden"}, {"type": "roll_initiative"},
])
def test_players_cannot_use_dm_commands(cmd):
    t = Table()
    t.add("Hero", 10, kind="player", owner="alice")
    t.add("Ogre", 9)
    before = json.dumps(t.state.to_dict())
    with pytest.raises(CommandError) as exc:
        apply(t.state, Actor("player", "alice"), cmd)
    assert exc.value.code == "forbidden"
    assert json.dumps(t.state.to_dict()) == before


def test_unknown_and_malformed_commands():
    t = Table()
    for bad in ({"type": "explode"}, {}, {"type": 5}, "start", None):
        with pytest.raises(CommandError):
            t.do(bad)


def test_add_me():
    t = Table()
    alice = Actor("player", "alice")
    me = {"type": "add_me", "name": "Thorn", "hp": 20, "hp_max": 25, "hp_temp": 2, "ac": 16, "init_bonus": 3,
          "owner": "someone-else", "hidden": True, "initiative": 99}
    t.do(me, actor=alice)
    e = t.state.entries[0]
    assert (e.name, e.hp, e.hp_max, e.ac, e.owner, e.kind) == ("Thorn", 20, 25, 16, "alice", "player")
    assert not e.hidden and e.initiative is None                     # a player can't hide themselves or pick a slot
    with pytest.raises(CommandError) as exc:
        t.do(me, actor=alice)
    assert exc.value.code == "duplicate"
    for i in range(T.MAX_PER_PLAYER - 1):
        t.do({**me, "name": f"Pet {i}"}, actor=alice)
    with pytest.raises(CommandError) as exc:
        t.do({**me, "name": "One too many"}, actor=alice)
    assert exc.value.code == "too_many"
    t.do({**me, "name": "Thorn"}, actor=Actor("player", "bob"))      # another player may share a name
    assert [x.name for x in t.state.entries].count("Thorn (2)") == 1
    t.do({"type": "set_settings", "players_can_add": False})
    with pytest.raises(CommandError) as exc:
        t.do({**me, "name": "Late"}, actor=Actor("player", "carol"))
    assert exc.value.code == "forbidden"
    with pytest.raises(CommandError):
        t.do(me, actor=DM)


def test_values_are_clamped_and_validated():
    t = Table()
    m = t.add("Ogre", 10, hp=10)
    t.do({"type": "set_stats", "id": m, "ac": 9999, "hp_max": 10**9, "hp": 10**9})
    e = t.state.get(m)
    assert e.ac == T.AC_LIMIT and e.hp_max == T.HP_LIMIT and e.hp == T.HP_LIMIT
    for bad in ({"hp": "abc"}, {"hp": None}, {"ac": True}):
        with pytest.raises(CommandError):
            t.do({"type": "set_stats", "id": m, **bad})
    with pytest.raises(CommandError):
        t.do({"type": "hp_delta", "id": m, "delta": "x"})
    with pytest.raises(CommandError):
        t.do({"type": "set_stats", "id": "nope", "hp": 1})
    t.do({"type": "set_field", "id": m, "field": "name", "value": "  " + "x" * 200})
    assert len(t.state.get(m).name) == T.MAX_NAME
    with pytest.raises(CommandError):
        t.do({"type": "set_field", "id": m, "field": "hp", "value": 1})   # not a settable field


def test_events():
    t = Table()
    t.add("Hero", 15, kind="player")
    t.do({"type": "add_entry", "kind": "event", "name": "Lair action", "initiative": 20, "hp": 50, "ac": 50})
    ev = t.state.entries[0]
    assert (ev.kind, ev.name, ev.hp_max, ev.conditions) == ("event", "Lair action", 0, [])
    with pytest.raises(CommandError):
        t.do({"type": "hp_delta", "id": ev.id, "delta": -1})
    t.do({"type": "roll_initiative", "only_missing": False}, rng=FixedRng([5]))   # events keep their slot
    assert t.state.get(ev.id).initiative == 20


# ---------------------------------------------------------------- visibility

def mixed_table():
    t = Table(monster_hp="number", monster_ac="shown")
    t.add("Hero", 18, kind="player", owner="alice", hp=20, hp_max=30, ac=16)
    t.add("Sidekick", 16, kind="player", owner="bob", hp=9, hp_max=12, ac=13)
    t.add("Ogre", 14, hp=59, ac=11)
    t.add("SECRET-AMBUSHER", 12, hp=33, ac=18, hidden=True, notes="SECRET-NOTE")
    t.add("Spy", 10, kind="player", owner="carol", hp=8, hp_max=8, ac=12, hidden=True)
    t.do({"type": "add_entry", "kind": "event", "name": "SECRET-TRAP", "initiative": 8, "hidden": True})
    t.do({"type": "add_entry", "kind": "event", "name": "Avalanche", "initiative": 6})
    return t


def names_in(view):
    return [e["name"] for e in view["entries"]]


def test_hidden_entries_are_not_sent_to_players():
    t = mixed_table()
    alice = project(t.state, Actor("player", "alice"))
    assert names_in(alice) == ["Hero", "Sidekick", "Ogre", "Avalanche"]
    carol = project(t.state, Actor("player", "carol"))
    assert "Spy" in names_in(carol) and "Spy" not in names_in(alice)          # a hidden player still sees themself
    spy = next(e for e in carol["entries"] if e["name"] == "Spy")
    assert spy["hidden"] is True and spy["mine"] is True
    assert "SECRET-AMBUSHER" not in names_in(carol)
    dm = project(t.state, DM)
    assert len(dm["entries"]) == 7 and dm["role"] == "dm"


def test_nothing_secret_appears_anywhere_in_a_players_view():
    """Search the whole serialized projection - ids, names, notes, numbers - for hidden data."""
    t = mixed_table()
    secret = next(e for e in t.state.entries if e.name == "SECRET-AMBUSHER")
    trap = next(e for e in t.state.entries if e.name == "SECRET-TRAP")
    for viewer in (Actor("player", "alice"), Actor("player", "bob"), Actor("player", ""), Actor("player", "zed")):
        blob = json.dumps(project(t.state, viewer))
        for needle in ("SECRET", secret.id, trap.id, "alice-never-sees-this"):
            if viewer.id != "alice" or needle != "alice-never-sees-this":
                assert needle not in blob, (viewer, needle)
        assert '"notes"' not in blob and '"owner"' not in blob and '"source"' not in blob
        assert '"init_bonus"' not in blob


def test_hidden_data_never_leaks_for_random_tables():
    rng = random.Random(1234)
    for trial in range(40):
        t = Table(monster_hp=rng.choice(T.HP_MODES), monster_ac=rng.choice(T.AC_MODES),
                  player_hp=rng.choice(T.HP_MODES))
        hidden_marks = []
        for i in range(rng.randint(2, 12)):
            kind = rng.choice(["monster", "custom", "player", "event"])
            hidden = rng.random() < 0.4
            name = f"X{trial}Q{i}Z" if hidden else f"vis{trial}n{i}"
            owner = rng.choice(["alice", "bob", ""]) if kind == "player" else ""
            eid = t.add(name, rng.choice([None, rng.randint(1, 25)]), kind=kind, owner=owner, hidden=hidden,
                        hp=rng.randint(1, 80), ac=rng.randint(8, 20), notes=f"NOTE{trial}-{i}")
            if hidden and not (kind == "player" and owner == "alice"):
                hidden_marks.append((name, eid))
        if rng.random() < 0.5 and len(t.state.entries) > 2:
            ids_ = [e.id for e in t.state.entries[:3]]
            t.do({"type": "group", "ids": ids_})
        if rng.random() < 0.6:
            t.do({"type": "start"})
            for _ in range(rng.randint(0, 6)):
                t.do({"type": "next_turn"})
        view = project(t.state, Actor("player", "alice"))
        blob = json.dumps(view)
        for name, eid in hidden_marks:
            assert name not in blob and f'"{eid}"' not in blob, (trial, name)
        assert "NOTE" not in blob
        for e in view["entries"]:
            if not e["mine"] and e["kind"] != "event":
                mode = e["hp_mode"]
                assert ("hp" in e) == (mode == "number") and ("hp_frac" in e) == (mode == "bar")


def test_hp_and_ac_visibility_settings():
    t = mixed_table()
    t.do({"type": "set_settings", "monster_hp": "bar", "monster_ac": "hidden"})
    view = project(t.state, Actor("player", "alice"))
    ogre = next(e for e in view["entries"] if e["name"] == "Ogre")
    assert "hp" not in ogre and ogre["hp_frac"] == 1.0 and "ac" not in ogre
    hero = next(e for e in view["entries"] if e["name"] == "Hero")
    assert (hero["hp"], hero["hp_max"], hero["ac"]) == (20, 30, 16)         # your own are always exact
    side = next(e for e in view["entries"] if e["name"] == "Sidekick")
    assert side["hp"] == 9 and side["ac"] == 13                              # other players: number + AC shown

    t.do({"type": "set_settings", "monster_hp": "hidden", "player_hp": "bar"})
    view = project(t.state, Actor("player", "alice"))
    ogre = next(e for e in view["entries"] if e["name"] == "Ogre")
    assert "hp" not in ogre and "hp_frac" not in ogre
    side = next(e for e in view["entries"] if e["name"] == "Sidekick")
    assert "hp" not in side and side["hp_frac"] == 0.8

    ogre_id = ogre["id"]
    t.do({"type": "set_field", "id": ogre_id, "field": "hp_mode", "value": "number"})      # per-entry reveal
    t.do({"type": "set_field", "id": ogre_id, "field": "ac_mode", "value": "shown"})
    ogre = next(e for e in project(t.state, Actor("player", "alice"))["entries"] if e["name"] == "Ogre")
    assert ogre["hp"] == 59 and ogre["ac"] == 11


def test_quantized_health_bar_never_lies_about_the_extremes():
    q = T.quantize_fraction
    assert q(0, 10) == 0.0 and q(10, 10) == 1.0 and q(0, 0) == 0.0
    assert q(1, 100) == 0.1                      # alive: never shows empty
    assert q(99, 100) == 0.9                     # hurt: never shows full
    assert q(5, 10) == 0.5 and q(7, 10) == 0.7


def test_hidden_active_creature_does_not_announce_itself():
    t = Table()
    t.add("Hero", 20, kind="player", owner="alice")
    t.add("Lurker", 15, hidden=True)
    t.add("Ogre", 10)
    t.do({"type": "start"}); t.do({"type": "next_turn"})
    assert T.display_order(t.state)[0].name == "Lurker"
    view = project(t.state, Actor("player", "alice"))
    assert names_in(view) == ["Ogre", "Hero"] and view["active"] == ""       # next visible on top, nobody highlighted
    t.do({"type": "next_turn"})
    view = project(t.state, Actor("player", "alice"))
    assert names_in(view)[0] == "Ogre" and view["active"] == view["entries"][0]["id"]
    t.do({"type": "set_hidden", "id": t.state.entries[1].id, "hidden": False})    # un-hide at any time
    assert "Lurker" in names_in(project(t.state, Actor("player", "alice")))


def test_group_labels_do_not_reveal_hidden_members():
    t = Table()
    ids_ = [t.add(f"G{i}", 10, hidden=(i == 2)) for i in range(3)]
    t.do({"type": "group", "ids": ids_, "name": "Goblins"})
    view = project(t.state, Actor("player", "alice"))
    assert len(view["entries"]) == 2
    assert {e["group"] for e in view["entries"]} == {"g1"} and view["group_names"] == {"g1": "Goblins"}
    assert "G2" not in json.dumps(view)


def test_player_view_reports_what_the_player_may_do():
    t = mixed_table()
    assert project(t.state, Actor("player", "alice"))["can_add"] is True
    t.do({"type": "set_settings", "players_can_add": False})
    assert project(t.state, Actor("player", "alice"))["can_add"] is False


# ---------------------------------------------------------------- history, saving

def test_undo_and_monotonic_revisions():
    tr = T.Tracker()
    seen = []
    tr.add_listener(lambda s: seen.append(s.rev))
    tr.dispatch(DM, {"type": "add_entry", "kind": "monster", "name": "Ogre", "hp": 10})
    tr.dispatch(DM, {"type": "hp_delta", "id": tr.state.entries[0].id, "delta": -4})
    assert tr.state.entries[0].hp == 6
    tr.dispatch(DM, {"type": "undo"})
    assert tr.state.entries[0].hp == 10
    tr.dispatch(DM, {"type": "undo"})
    assert tr.state.entries == [] and not tr.can_undo
    assert seen == sorted(seen) and len(set(seen)) == len(seen)
    with pytest.raises(CommandError):
        tr.dispatch(DM, {"type": "undo"})
    with pytest.raises(CommandError):
        tr.dispatch(Actor("player", "a"), {"type": "undo"})
    before = tr.state.rev
    with pytest.raises(CommandError):
        tr.dispatch(DM, {"type": "remove", "id": "nope"})
    assert tr.state.rev == before                                            # a failed command changes nothing


def test_apply_never_mutates_its_input():
    t = mixed_table()
    snapshot = json.dumps(t.state.to_dict())
    apply(t.state, DM, {"type": "start"})
    apply(t.state, DM, {"type": "sort"})
    apply(t.state, DM, {"type": "remove", "id": t.state.entries[0].id})
    assert json.dumps(t.state.to_dict()) == snapshot


def test_save_and_load_round_trip(tmp_path):
    t = mixed_table()
    t.do({"type": "start"}); t.do({"type": "next_turn"})
    t.do({"type": "add_condition", "id": t.state.entries[2].id, "name": "Prone"})
    path = str(tmp_path / "initiative_state.json")
    T.save_state(t.state, path)
    loaded = T.load_state(path)
    assert loaded.to_dict() == t.state.to_dict()
    assert [e.name for e in T.display_order(loaded)] == t.names()


def test_loading_garbage_is_safe(tmp_path):
    assert T.load_state(str(tmp_path / "missing.json")) is None
    p = tmp_path / "bad.json"
    for text in ("not json", "[]", '{"format": "other"}', '{"format": "spellbook-initiative", "version": 99}'):
        p.write_text(text)
        assert T.load_state(str(p)) is None
    p.write_text(json.dumps({"format": "spellbook-initiative", "version": 1, "started": True, "active": "ghost",
                             "entries": [{"id": "a", "kind": "monster", "name": "Ok", "hp": 5},
                                         {"id": "a", "kind": "monster", "name": "Dup id", "hp": "x"},
                                         {"id": "b", "kind": "wizard", "name": "Odd kind", "hp": 3},
                                         "junk", 5]}))
    loaded = T.load_state(str(p))
    assert [e.name for e in loaded.entries] == ["Ok", "Odd kind"]
    assert loaded.active == loaded.entries[0].id                             # a stale pointer is repaired


# ---------------------------------------------------------------- sources (T1): copies, never links

def test_tracker_changes_never_touch_the_sheet_or_monster():
    from character_sheet import CharacterSheet
    from monster import Monster

    sheet = CharacterSheet(character_name="Thorn")
    sheet.hit_points.maximum, sheet.hit_points.current, sheet.hit_points.temporary = 30, 22, 4
    sheet.armor_class = 17
    sheet_before = json.dumps(sheet.to_dict(), sort_keys=True)
    monster = Monster.from_dict({"name": "Test Ogre", "hp": 59, "ac": 11, "hit_dice": "7d10 + 21"})
    monster_before = json.dumps(monster.to_dict(), sort_keys=True)

    t = Table()
    t.do(S.from_sheet(sheet, owner="alice"))
    t.do(S.from_monster(monster))
    thorn, ogre = t.state.entries
    assert (thorn.hp, thorn.hp_max, thorn.hp_temp, thorn.ac) == (22, 30, 4, 17)
    assert (ogre.hp, ogre.hp_max, ogre.ac) == (59, 59, 11)
    assert thorn.source == {"type": "character", "name": "Thorn"} and ogre.source["type"] == "monster"

    t.do({"type": "hp_delta", "id": thorn.id, "delta": -20})
    t.do({"type": "set_stats", "id": ogre.id, "hp": 0, "ac": 5})
    t.do({"type": "add_condition", "id": ogre.id, "name": "Prone"})
    assert json.dumps(sheet.to_dict(), sort_keys=True) == sheet_before
    assert json.dumps(monster.to_dict(), sort_keys=True) == monster_before


def test_monster_hp_can_be_rolled_from_hit_dice():
    from monster import Monster
    m = Monster.from_dict({"name": "Test Ogre", "hp": 59, "ac": 11, "hit_dice": "7d10 + 21"})
    cmd = S.from_monster(m, roll_hp=True, rng=FixedRng([10, 1, 1, 1, 1, 1, 1]))
    assert cmd["hp"] == 10 + 6 + 21 and cmd["hp_max"] == cmd["hp"]
    assert S.from_monster(m)["hp"] == 59                                      # default: the average
    odd = Monster.from_dict({"name": "Summoned Thing", "hp": 12, "ac": 14, "hit_dice": "see spell"})
    assert S.from_monster(odd, roll_hp=True)["hp"] == 12                      # unparseable dice fall back
    assert S.roll_hit_dice("nonsense") is None


def test_sources_build_valid_commands():
    t = Table()
    t.do(S.several(S.custom("Bandit", hp=11, ac=12, init_bonus=1), 3, group=True))
    t.do(S.event("Bridge collapses", 10))
    from character_sheet import CharacterSheet
    me = S.as_me(S.from_sheet(CharacterSheet(character_name="Zed")))
    assert me["type"] == "add_me" and me["name"] == "Zed" and "owner" not in me
    t.do(me, actor=Actor("player", "zed"))
    assert [e.name for e in t.state.entries] == ["Bridge collapses", "Bandit 1", "Bandit 2", "Bandit 3", "Zed"]
    assert sorted({e.kind for e in t.state.entries}) == ["custom", "event", "player"]


def test_condition_helpers():
    assert C.canonical_name("  PRONE ") == "Prone" and C.canonical_name("hexed") == "Hexed"
    assert C.make_condition("exhaustion", level=0)["level"] == 1
    assert C.label({"name": "Poisoned", "rounds": 1}) == "Poisoned (1 rd)"
    with pytest.raises(ValueError):
        C.make_condition("  ")
