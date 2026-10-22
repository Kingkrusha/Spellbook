"""The tabletop over a real encrypted session (loopback): each player's view, their commands, pictures and pings."""

import time

import pytest

from tests.lan_wait import stall_report

import tabletop as T
import tabletop_net as N
from lan import protocol as P
from lan.service import CLIENT, SessionService


def pump_until(cond, *services, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for s in services:
            s.pump()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached\n" + stall_report(services))


def png(color):
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (900, 600), color).save(buf, "PNG")
    return buf.getvalue()


class Game:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.table = T.Tabletop(str(tmp_path / "tabletop.json"))
        self.assets = T.AssetStore(str(tmp_path / "dm_assets"), str(tmp_path / "dm_cache"))
        self.host = SessionService()
        port = self.host.start_host("DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
        self.invite = P.Invite("127.0.0.1", port, self.host._host.fingerprint).encode()
        self.link = N.TableHostLink(self.host, self.table, self.assets)
        self.dm = N.LocalTable(self.table, self.assets)
        self.players = {}

    def join(self, name, client_id):
        svc = SessionService()
        svc._client_id_cache = client_id
        svc.join(self.invite, name)
        pump_until(lambda: svc.role == CLIENT, self.host, svc)
        remote = N.RemoteTable(svc, T.AssetStore(str(self.tmp / f"{name}_a"), str(self.tmp / f"{name}_c")))
        self.players[name] = (svc, remote)
        self.settle()
        return remote

    def svcs(self):
        return [s for s, _ in self.players.values()]

    def settle(self, cond=None, timeout=20.0):
        pump_until(cond or (lambda: True), self.host, *self.svcs(), timeout=timeout)
        for _ in range(12):
            for s in [self.host] + self.svcs():
                s.pump()
            time.sleep(0.02)

    def close(self):
        self.link.close()
        self.dm.close()
        for s in self.svcs():
            s.shutdown()
        self.host.shutdown()


@pytest.fixture()
def game(tmp_path):
    g = Game(tmp_path)
    yield g
    g.close()


def names(remote):
    scene = remote.view()["scene"]
    return {t["name"]: t for t in scene["tokens"]} if scene else {}


def test_players_see_the_shown_scene_without_hidden_things_and_get_the_map(game):
    map_id, w, h = game.assets.add_image(png((30, 90, 40)))
    sid = game.dm.dispatch({"op": "scene_new", "scene_data": {"name": "Woods", "map": map_id, "w": w, "h": h}})["scene"]
    game.dm.dispatch({"op": "token_add", "token": {"name": "Brakka", "x": 35, "y": 35, "owner": "cid-alice",
                                                   "hp": 12, "hp_max": 20}})
    game.dm.dispatch({"op": "token_add", "token": {"name": "Lurker", "x": 135, "y": 35, "hidden": True}})
    alice = game.join("Alice", "cid-alice")
    assert alice.view()["scene"] is None                       # nothing shown yet
    game.dm.dispatch({"op": "scene_show", "scene": sid})
    game.settle(lambda: alice.view()["scene"] is not None and alice.asset_path(map_id) is not None)
    assert set(names(alice)) == {"Brakka"} and names(alice)["Brakka"]["hp"] == 12
    with open(alice.asset_path(map_id), "rb") as f:
        assert f.read() == game.assets.read(map_id)           # the same picture, checked by its hash


def test_a_player_moves_their_own_token_but_not_others(game):
    sid = game.dm.dispatch({"op": "scene_new", "scene_data": {"name": "Hall"}})["scene"]
    mine = game.dm.dispatch({"op": "token_add", "token": {"name": "Me", "x": 35, "y": 35, "owner": "cid-bob"}})["token"]
    orc = game.dm.dispatch({"op": "token_add", "token": {"name": "Orc", "x": 105, "y": 35}})["token"]
    game.dm.dispatch({"op": "scene_show", "scene": sid})
    bob = game.join("Bob", "cid-bob")
    errors = []
    bob.on_error(errors.append)
    bob.dispatch({"op": "token_move", "id": mine, "x": 245, "y": 175})
    assert names(bob)["Me"]["x"] == 245                         # moves at once on the player's screen
    game.settle(lambda: T.Tabletop._token_or_fail(game.table.scene(sid), mine)["x"] == 245)
    bob.dispatch({"op": "token_move", "id": orc, "x": 500, "y": 500})
    game.settle(lambda: bool(errors))
    assert "isn't yours" in errors[0]
    assert T.Tabletop._token_or_fail(game.table.scene(sid), orc)["x"] == 105
    game.settle(lambda: names(bob)["Orc"]["x"] == 105)          # put back where the DM has it


def test_drawings_and_pings_reach_everyone(game):
    sid = game.dm.dispatch({"op": "scene_new", "scene_data": {"name": "Map"}})["scene"]
    game.dm.dispatch({"op": "scene_show", "scene": sid})
    alice, bob = game.join("Alice", "cid-a"), game.join("Bob", "cid-b")
    pings = {"dm": [], "bob": []}
    game.dm.on_ping(pings["dm"].append)
    bob.on_ping(pings["bob"].append)
    alice.dispatch({"op": "draw_add", "drawing": {"kind": "line", "pts": [0, 0, 100, 100], "color": "#00FF00"}})
    game.settle(lambda: len(bob.view()["scene"]["drawings"]) == 1)
    alice.ping(300, 200)
    game.settle(lambda: pings["dm"] and pings["bob"])
    assert pings["bob"][0]["name"] == "Alice" and pings["bob"][0]["x"] == 300
    game.dm.ping(10, 10)
    game.settle(lambda: len(pings["bob"]) == 2)


def test_a_player_only_gets_pictures_they_can_see(game):
    secret, _, _ = game.assets.add_image(png((200, 0, 0)), token=True)
    sid = game.dm.dispatch({"op": "scene_new", "scene_data": {"name": "Map"}})["scene"]
    game.dm.dispatch({"op": "token_add", "token": {"name": "Hidden", "image": secret, "hidden": True}})
    game.dm.dispatch({"op": "scene_show", "scene": sid})
    alice = game.join("Alice", "cid-a")
    svc = game.players["Alice"][0]
    alice._requested.add(secret)
    svc.request_table_assets([secret])
    game.settle()
    assert alice.asset_path(secret) is None


def test_bad_views_are_refused():
    assert N.valid_view({"scene": None})
    assert not N.valid_view({"scene": {"id": "x", "tokens": "no", "drawings": []}})
    assert not N.valid_view({"scene": {"id": "x", "tokens": [{"id": "a", "name": "b", "x": "1", "y": 0, "size": 1}],
                                       "drawings": [], "grid": {}, "fog": {"ops": []}}})


def test_views_with_damaged_areas_or_heights_are_refused():
    base = {"id": "x", "tokens": [], "drawings": [], "grid": {}, "fog": {"ops": []}}
    good = T.clean_area({"shape": "cone", "x": 1, "y": 2, "size": 15})
    assert N.valid_view({"scene": dict(base, areas=[good], zones=[{"pts": [0, 0, 1, 0, 0, 1], "elev": 5}])})
    assert not N.valid_view({"scene": dict(base, areas=[dict(good, shape="blob")])})
    assert not N.valid_view({"scene": dict(base, areas=[dict(good, size="big")])})
    assert not N.valid_view({"scene": dict(base, zones=[{"pts": [], "elev": "up"}])})
