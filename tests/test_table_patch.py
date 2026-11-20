"""Players get only what changed on the tabletop (table_patch.py, tabletop_net.py, lan/web/patch.js)."""

import copy
import json
import os
import random
import shutil
import subprocess

import pytest

import table_patch as TP
import tabletop as T
import tabletop_net as N

NODE = shutil.which("node")
PATCH_JS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lan", "web", "patch.js")


def a_view(tokens=3, fog_steps=2):
    return {
        "rev": 1, "role": "player",
        "scene": {
            "id": "s1", "name": "Cave", "w": 800, "h": 600, "grid": {"type": "square", "cell": 50},
            "tokens": [{"id": f"t{i}", "name": f"Goblin {i}", "x": 50.0 * i, "y": 10.0, "size": 1.0,
                        "conditions": []} for i in range(tokens)],
            "drawings": [{"id": "d1", "kind": "line", "pts": [0, 0, 10, 10], "mine": False}],
            "areas": [],
            "fog": {"on": True, "ops": [{"kind": "reveal", "pts": [0, 0, 100, 100]}] * fog_steps},
            "sight": [{"x": 1, "y": 2, "r": 300, "pts": [0, 0, 5, 5]}],
            "explored": {"cell": 25, "bits": "AAAA"},
        },
    }


def round_trip(old, new):
    ops = TP.diff_view(old, new)
    assert ops is not None
    json.dumps(ops)                                  # (they go over the network)
    got = copy.deepcopy(old)
    assert TP.apply_ops(got, ops)
    assert got == new
    return ops


def test_a_moved_token_is_one_small_change():
    old = a_view(tokens=40, fog_steps=50)
    new = copy.deepcopy(old)
    new["rev"] = 2
    new["scene"]["tokens"][7]["x"] = 400.0
    ops = round_trip(old, new)
    kinds = sorted(op[0] for op in ops)
    assert kinds == ["items", "set"]                 # the token, and the view's number
    items = next(op for op in ops if op[0] == "items")
    assert [r["id"] for r in items[2]] == ["t7"] and items[3] == [] and items[4] is None
    assert TP.worth_it(ops, len(json.dumps(new)))


def test_fog_steps_are_appended_and_other_kinds_of_change_round_trip():
    old = a_view()
    new = copy.deepcopy(old)
    new["scene"]["fog"]["ops"].append({"kind": "hide", "pts": [5, 5, 6, 6]})
    new["scene"]["tokens"].pop(0)                                       # gone
    new["scene"]["tokens"].insert(0, {"id": "new", "name": "Ogre", "x": 1.0, "y": 2.0, "size": 2.0})   # new, first
    new["scene"]["tokens"].reverse()                                     # reordered
    new["scene"]["name"] = "Deep cave"
    del new["scene"]["explored"]
    new["scene"]["doors"] = [{"id": "w1", "open": False}]
    new["scene"]["sight"] = []
    ops = round_trip(old, new)
    assert ["append", ["scene", "fog", "ops"], [{"kind": "hide", "pts": [5, 5, 6, 6]}]] in ops
    assert ["del", ["scene", "explored"]] in ops


def test_another_map_or_no_map_means_the_whole_view():
    old, new = a_view(), a_view()
    new["scene"]["id"] = "s2"
    assert TP.diff_view(old, new) is None
    assert TP.diff_view(None, new) is None
    assert TP.diff_view(old, {"rev": 3, "scene": None, "role": "player"}) is None


def test_a_patch_that_does_not_fit_is_refused():
    view = a_view()
    assert not TP.apply_ops(view, [["set", ["scene", "nowhere", "x"], 1]])
    assert not TP.apply_ops(view, [["append", ["scene", "name"], [1]]])
    assert not TP.apply_ops(view, [["items", ["scene", "tokens"], [], [], ["t0"]]])     # an order missing ids
    assert not TP.apply_ops(view, [["explode", ["scene"]]])
    assert not TP.apply_ops(view, [["set", [], 1]])
    assert not TP.apply_ops(view, "nonsense")
    assert not TP.apply_ops(view, [["set", ["rev"], 1]] * (TP.MAX_OPS + 1))


def random_change(rng, view):
    scene = view["scene"]
    choice = rng.randrange(8)
    tokens = scene["tokens"]
    if choice == 0 and tokens:
        rng.choice(tokens)["x"] = float(rng.randrange(800))
    elif choice == 1:
        tokens.append({"id": f"n{rng.randrange(10 ** 6)}", "name": "New", "x": 1.0, "y": 1.0, "size": 1.0})
    elif choice == 2 and tokens:
        tokens.pop(rng.randrange(len(tokens)))
    elif choice == 3:
        rng.shuffle(tokens)
    elif choice == 4:
        scene["fog"]["ops"].append({"kind": "reveal", "pts": [rng.random()]})
    elif choice == 5:
        scene["fog"]["ops"] = scene["fog"]["ops"][:1]
    elif choice == 6:
        scene["drawings"] = [{"id": f"d{i}", "kind": "free", "pts": [i]} for i in range(rng.randrange(4))]
    else:
        scene["grid"]["cell"] = rng.choice([40, 50, 70])
        scene.pop("sight", None) if rng.random() < 0.5 else scene.__setitem__("sight", [{"r": rng.random()}])
    view["rev"] += 1


def test_random_changes_always_round_trip():
    rng = random.Random(7)
    view = a_view()
    for _ in range(300):
        new = copy.deepcopy(view)
        for _ in range(rng.randrange(1, 4)):
            random_change(rng, new)
        round_trip(view, new)
        view = new


# ---- the host and a player's app

class Service:
    """A session that only notes what the host link sends, and a player that asks for patches."""
    my_id = "host"

    def __init__(self):
        self.peers = [{"peer_id": "host"}, {"peer_id": "p1"}]
        self.client_ids = {"p1": "install-p1"}
        self.sent = []
        self.listeners = []

    def add_listener(self, fn):
        self.listeners.append(fn)

    def remove_listener(self, fn):
        self.listeners.remove(fn)

    def send_table_state(self, peer_id, view, seq=None):
        self.sent.append(("state", peer_id, json.loads(json.dumps(view)), seq))

    def send_table_patch(self, peer_id, ops, base, seq):
        self.sent.append(("patch", peer_id, json.loads(json.dumps(ops)), base, seq))

    def send_table_error(self, *args):
        pass

    def event(self, kind, **data):
        for fn in list(self.listeners):
            fn(kind, **data)


class PlayerService:
    def __init__(self):
        self.listeners = []
        self.syncs = 0

    def add_listener(self, fn):
        self.listeners.append(fn)

    def remove_listener(self, fn):
        self.listeners.remove(fn)

    def request_table_sync(self):
        self.syncs += 1
        return True

    def request_table_assets(self, ids):
        return True

    def client_id(self):
        return "install-p1"

    def deliver(self, message):
        """One message from the host, as lan/service.py hands it on."""
        for fn in list(self.listeners):
            if message[0] == "state":
                fn("table_state", view=message[2], seq=message[3])
            else:
                fn("table_patch", ops=message[2], base=message[3], seq=message[4])


def a_table(tmp_path):
    table = T.Tabletop(str(tmp_path / "tabletop.json"))
    scene = table.apply({"op": "scene_new", "scene_data": {"name": "Cave", "w": 2000, "h": 2000}})["scene"]
    table.apply({"op": "scene_show", "scene": scene})
    for i in range(30):
        table.apply({"op": "token_add", "scene": scene, "token": {"name": f"Goblin {i}", "x": 25 + 50 * i, "y": 25}})
    return table, scene


def test_a_player_whose_app_asks_gets_changes_and_ends_up_with_the_same_view(tmp_path):
    table, scene = a_table(tmp_path)
    host = Service()
    link = N.TableHostLink(host, table, T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c")))
    player = PlayerService()
    remote = N.RemoteTable(player, T.AssetStore(str(tmp_path / "pa"), str(tmp_path / "pc")))
    assert player.syncs == 1
    assert [m[0] for m in host.sent] == ["state"]           # before the player asked: the whole view
    host.sent.clear()
    host.event("table_sync", peer_id="p1")                   # (what the player's request turns into)
    assert [m[0] for m in host.sent] == ["state"]
    for message in host.sent:
        player.deliver(message)
    host.sent.clear()

    token = table.scenes[scene]["tokens"][3]["id"]
    table.apply({"op": "token_move", "scene": scene, "id": token, "x": 525, "y": 525})
    table.apply({"op": "draw_add", "scene": scene, "drawing": {"kind": "line", "pts": [0, 0, 50, 50]}})
    assert [m[0] for m in host.sent] == ["patch", "patch"]
    assert len(json.dumps(host.sent[0][2])) < 400            # one token, not thirty
    for message in host.sent:
        player.deliver(message)
    assert remote.view() == json.loads(json.dumps(table.view_for("install-p1")))
    link.close()
    remote.close()


def test_a_player_who_missed_a_change_asks_for_the_whole_view_once(tmp_path):
    table, scene = a_table(tmp_path)
    host = Service()
    link = N.TableHostLink(host, table, T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c")))
    host.event("table_sync", peer_id="p1")
    player = PlayerService()
    remote = N.RemoteTable(player, T.AssetStore(str(tmp_path / "pa"), str(tmp_path / "pc")))
    player.deliver(host.sent[-1])
    host.sent.clear()
    tokens = table.scenes[scene]["tokens"]
    for i, x in enumerate((125, 175, 225)):
        table.apply({"op": "token_move", "scene": scene, "id": tokens[i]["id"], "x": x, "y": 125})
    first, second, third = host.sent
    before = remote.view()
    player.deliver(second)                                   # (the first one got lost)
    player.deliver(third)
    assert player.syncs == 2 and remote.view() is before    # asked once, and the map didn't change
    host.sent.clear()
    host.event("table_sync", peer_id="p1")
    player.deliver(host.sent[-1])
    assert remote.view()["scene"]["tokens"][2]["x"] == 225
    link.close()
    remote.close()


def test_a_player_that_never_asked_keeps_getting_whole_views(tmp_path):
    table, scene = a_table(tmp_path)
    host = Service()
    link = N.TableHostLink(host, table, T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c")))
    host.sent.clear()
    token = table.scenes[scene]["tokens"][0]["id"]
    table.apply({"op": "token_move", "scene": scene, "id": token, "x": 525, "y": 525})
    assert [m[0] for m in host.sent] == ["state"]           # (an app from before patches)
    host.event("table_sync", peer_id="p1")
    host.event("peer_left", peer={"peer_id": "p1"})
    host.sent.clear()
    table.apply({"op": "token_move", "scene": scene, "id": token, "x": 25, "y": 25})
    assert [m[0] for m in host.sent] == ["state"]           # leaving forgets it
    link.close()


# ---- the browser page

RUNNER = r"""
const P = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(cases.map((c) => { const v = c.view; return [P.applyOps(v, c.ops), v]; })))
"""


@pytest.mark.skipif(NODE is None, reason="Node.js is needed to run the page's JavaScript")
def test_the_page_makes_the_same_changes_as_the_app():
    rng = random.Random(11)
    cases, expected = [], []
    view = a_view()
    for _ in range(150):
        new = copy.deepcopy(view)
        for _ in range(rng.randrange(1, 4)):
            random_change(rng, new)
        ops = TP.diff_view(view, new)
        cases.append({"view": view, "ops": ops})
        expected.append([True, new])
        view = new
    bad = [[["set", ["scene", "nowhere", "x"], 1]], [["items", ["scene", "tokens"], [], [], ["x"]]],
           [["set", ["__proto__"], 1]], [["append", ["scene", "name"], [1]]]]
    for ops in bad:
        cases.append({"view": a_view(), "ops": ops})
        expected.append([False, None])
    proc = subprocess.run([NODE, "-e", RUNNER, PATCH_JS], input=json.dumps(cases), capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    for (ok, view), (want_ok, want) in zip(got, expected):
        assert ok == want_ok
        if want_ok:
            assert view == want
