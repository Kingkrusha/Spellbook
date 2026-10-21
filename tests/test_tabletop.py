"""The virtual tabletop's model (tabletop.py): grids, commands and who may run them, views, assets."""

import io
import json
import os
import zipfile

import pytest

import tabletop as T


@pytest.fixture()
def table(tmp_path):
    return T.Tabletop(str(tmp_path / "tabletop.json"))


def make_scene(table, **kw):
    data = {"name": "Crypt", "w": 700, "h": 700, "cell": 70}
    data.update(kw)
    return table.apply({"op": "scene_new", "scene_data": data})["scene"]


# ---- grids

def test_square_snapping_and_distance():
    g = T.Grid("square", 50)
    assert g.snap(60, 80) == (75, 75)                      # medium: the centre of its square
    assert g.snap(110, 110, size=2) == (100, 100)          # large: the corner where four squares meet
    assert g.snap(10, 10, size=0.5) == (12.5, 12.5)        # tiny: quarter squares
    assert g.cells_between((25, 25), (225, 125)) == 4      # diagonals count as one square (2024 rules)


@pytest.mark.parametrize("kind", ["hex_rows", "hex_cols"])
def test_hex_round_trip_and_distance(kind):
    g = T.Grid(kind, 60, 7, 11)
    for q in range(-3, 4):
        for r in range(-3, 4):
            x, y = g.hex_center(q, r)
            assert g.hex_at(x + 3, y - 2) == (q, r)
            assert g.snap(x + 5, y + 4) == pytest.approx((x, y))
    a, b = g.hex_center(0, 0), g.hex_center(3, -1)
    assert g.cells_between(a, b) == 3
    # neighbours are one cell apart in every direction
    for dq, dr in ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1)):
        assert g.cells_between(a, g.hex_center(dq, dr)) == 1
        assert abs(((g.hex_center(dq, dr)[0] - a[0]) ** 2 + (g.hex_center(dq, dr)[1] - a[1]) ** 2) ** 0.5 - 60) < 1e-6


def test_grid_lines_cover_the_box():
    assert len(T.Grid("square", 50).lines_in(0, 0, 500, 300)) == 11 + 7
    assert len(T.Grid("hex_rows", 50).lines_in(0, 0, 500, 300)) > 50
    assert T.Grid("none").lines_in(0, 0, 500, 300) == []


# ---- commands and permissions

def test_dm_builds_a_scene_and_players_get_a_filtered_view(table):
    sid = make_scene(table)
    table.apply({"op": "scene_show", "scene": sid})
    pc = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Brakka", "x": 35, "y": 35, "hp": 20,
                                                                  "hp_max": 30, "owner": "alice", "kind": "pc"}})
    orc = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Orc", "x": 105, "y": 35, "hp": 5,
                                                                   "hp_max": 15}})
    table.apply({"op": "token_add", "scene": sid, "token": {"name": "Assassin", "x": 175, "y": 35, "hidden": True}})
    table.apply({"op": "draw_add", "scene": sid, "drawing": {"kind": "line", "pts": [0, 0, 70, 70],
                                                             "private": True}})
    view = table.view_for("alice")["scene"]
    names = {t["name"]: t for t in view["tokens"]}
    assert set(names) == {"Brakka", "Orc"}                              # hidden token left out
    assert names["Brakka"]["hp"] == 20 and names["Brakka"]["mine"]      # your own numbers
    assert names["Orc"]["hp"] is None and names["Orc"]["state"] == "bloodied"   # others: only a rough state
    assert view["drawings"] == []                                       # the DM's private notes stay private
    assert pc["token"] and orc["token"]


def test_players_may_only_move_their_own_tokens(table):
    sid = make_scene(table)
    table.apply({"op": "scene_show", "scene": sid})
    mine = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Me", "owner": "alice"}})["token"]
    other = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Orc"}})["token"]
    table.apply({"op": "token_move", "scene": sid, "id": mine, "x": 140, "y": 210}, actor="alice")
    assert T.Tabletop._token_or_fail(table.scene(sid), mine)["x"] == 140
    with pytest.raises(T.CommandError):
        table.apply({"op": "token_move", "scene": sid, "id": other, "x": 1, "y": 1}, actor="alice")
    with pytest.raises(T.CommandError):
        table.apply({"op": "token_delete", "scene": sid, "id": mine}, actor="alice")
    table.apply({"op": "scene_update", "scene": sid, "fields": {"players_move_all": True}})
    table.apply({"op": "token_move", "scene": sid, "id": other, "x": 1, "y": 1}, actor="alice")


def test_players_act_only_on_the_shown_scene_and_draw_when_allowed(table):
    a, b = make_scene(table), make_scene(table, name="Road")
    table.apply({"op": "scene_show", "scene": a})
    line = {"kind": "free", "pts": [0, 0, 5, 5, 9, 9]}
    with pytest.raises(T.CommandError):
        table.apply({"op": "draw_add", "scene": b, "drawing": line}, actor="bob")
    drawn = table.apply({"op": "draw_add", "scene": a, "drawing": line}, actor="bob")["drawing"]
    table.apply({"op": "draw_delete", "scene": a, "id": drawn}, actor="carol")      # not hers: nothing happens
    assert len(table.scene(a)["drawings"]) == 1
    table.apply({"op": "draw_delete", "scene": a, "id": drawn}, actor="bob")
    assert table.scene(a)["drawings"] == []
    table.apply({"op": "scene_update", "scene": a, "fields": {"players_draw": False}})
    with pytest.raises(T.CommandError):
        table.apply({"op": "draw_add", "scene": a, "drawing": line}, actor="bob")


def test_bad_input_is_cleaned_or_refused(table):
    sid = make_scene(table)
    t = table.apply({"op": "token_add", "scene": sid, "token": {"name": "x" * 500, "size": 99, "color": "red",
                                                                 "image": "../../etc", "conditions": ["A"] * 50,
                                                                 "x": float("nan")}})["token"]
    token = T.Tabletop._token_or_fail(table.scene(sid), t)
    assert len(token["name"]) <= T.MAX_TEXT and token["size"] == 4.0 and token["color"].startswith("#")
    assert token["image"] == "" and token["conditions"] == ["A"] and token["x"] == 0
    for bad in ({"op": "nope"}, {"op": "__init__"}, {"op": "token_update", "scene": "missing"}, "text"):
        with pytest.raises(T.CommandError):
            table.apply(bad)
    with pytest.raises(T.CommandError):
        table.apply({"op": "fog", "scene": sid, "fog_op": {"mode": "reveal", "shape": "rect", "pts": [1]}})


def test_conditions_toggle_and_fog_ops(table):
    sid = make_scene(table)
    t = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Orc"}})["token"]
    for name in ("Prone", "Poisoned", "Prone"):
        table.apply({"op": "token_condition", "scene": sid, "id": t, "name": name})
    assert T.Tabletop._token_or_fail(table.scene(sid), t)["conditions"] == ["Poisoned"]
    table.apply({"op": "fog", "scene": sid, "fog_op": {"mode": "reveal", "shape": "rect", "pts": [0, 0, 140, 140]}})
    fog = table.scene(sid)["fog"]
    assert fog["on"] and len(fog["ops"]) == 1
    table.apply({"op": "fog_reset", "scene": sid, "mode": "hide"})
    assert table.scene(sid)["fog"]["ops"] == []


def test_undo_and_saving(table, tmp_path):
    sid = make_scene(table)
    t = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Orc"}})["token"]
    table.apply({"op": "token_delete", "scene": sid, "id": t})
    assert table.scene(sid)["tokens"] == []
    assert table.undo() and table.scene(sid)["tokens"][0]["name"] == "Orc"
    table.apply({"op": "scene_delete", "scene": sid})
    assert table.scene(sid) is None and table.undo() and table.scene(sid) is not None
    table.apply({"op": "scene_show", "scene": sid})
    assert table.save()
    again = T.Tabletop(table.path)
    assert again.shown == sid and again.scene(sid)["tokens"][0]["name"] == "Orc"
    assert table.undo() and table.undo() and table.scene(sid) is None        # back past the scene's creation


def test_listeners_hear_each_change(table):
    heard = []
    table.add_listener(heard.append)
    sid = make_scene(table)
    table.apply({"op": "scene_rename", "scene": sid, "name": "Vault"})
    assert heard == [sid, sid]


# ---- assets and the token library

def png_bytes(size=(40, 30), color=(200, 10, 10, 255)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_assets_are_named_by_content_and_checked_when_received(tmp_path):
    from PIL import Image
    store = T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c"))
    big = Image.new("RGB", (5000, 2500), (10, 120, 30))
    asset, w, h = store.add_image(big)
    assert (w, h) == (T.MAP_MAX_SIDE, T.MAP_MAX_SIDE // 2) and store.path(asset).endswith(".jpg")
    assert store.add_image(big)[0] == asset                              # same picture, same name
    token, tw, th = store.add_image(png_bytes((600, 600)), token=True)
    assert max(tw, th) == T.TOKEN_MAX_SIDE and store.path(token).endswith(".png")

    other = T.AssetStore(str(tmp_path / "x"), str(tmp_path / "y"))
    data = store.read(token)
    assert not other.add_received(asset, data)                           # wrong name for those bytes
    assert not other.add_received(T.AssetStore._encode.__name__, data)   # not an id at all
    assert other.add_received(token, data) and other.has(token)
    junk = b"not a picture"
    import hashlib
    assert not other.add_received(hashlib.sha1(junk).hexdigest()[:20], junk)


def test_token_library_imports_folders_and_zips(tmp_path):
    src = tmp_path / "Goblins"
    (src / "Archers").mkdir(parents=True)
    (src / "boss.png").write_bytes(png_bytes())
    (src / "Archers" / "goblin_archer.png").write_bytes(png_bytes())
    (src / "notes.txt").write_text("hi")
    lib = tmp_path / "lib"
    assert T.import_tokens(str(src), str(lib)) == 2
    zpath = tmp_path / "Undead.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Undead/zombie.png", png_bytes())
        z.writestr("../evil.png", png_bytes())
    assert T.import_tokens(str(zpath), str(lib)) == 2
    assert not (tmp_path / "evil.png").exists()
    found = T.list_token_files(str(lib))
    assert ("Goblins / Archers", "goblin archer") in [(g, n) for g, n, _ in found]
    assert any(n == "zombie" for _, n, _ in found)


# ---- walls and line of sight

def _wall_scene(table, **kw):
    sid = make_scene(table, **kw)
    table.apply({"op": "scene_update", "scene": sid, "fields": {"los": True}})
    # a wall straight down the middle, with a door in it at the bottom
    table.apply({"op": "wall_add", "scene": sid, "walls": [{"pts": [350, 0, 350, 560]}]})
    door = table.apply({"op": "wall_add", "scene": sid, "wall": {"pts": [350, 560, 350, 700], "door": True}})
    me = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Me", "x": 105, "y": 105,
                                                                  "owner": "me", "kind": "pc"}})["token"]
    orc = table.apply({"op": "token_add", "scene": sid, "token": {"name": "Orc", "x": 595, "y": 105}})["token"]
    table.apply({"op": "scene_show", "scene": sid})
    return sid, door["walls"][0], me, orc


def test_walls_hide_what_a_players_tokens_cant_see(table):
    sid, door, me, orc = _wall_scene(table)
    view = table.view_for("me")["scene"]
    assert {t["name"] for t in view["tokens"]} == {"Me"}           # the orc is behind the wall
    assert "walls" not in view and len(view["sight"]) == 1          # the walls themselves stay with the DM
    assert T.in_sight(view["sight"], 200, 300) and not T.in_sight(view["sight"], 500, 300)

    # opening the door lets the eye through the gap
    table.apply({"op": "wall_update", "scene": sid, "id": door, "fields": {"open": True}})
    table.apply({"op": "token_move", "scene": sid, "id": me, "x": 105, "y": 630}, actor="me")
    table.apply({"op": "token_move", "scene": sid, "id": orc, "x": 595, "y": 630})
    assert {t["name"] for t in table.view_for("me")["scene"]["tokens"]} == {"Me", "Orc"}

    # line of sight off: everything (that isn't hidden) again, and no darkness
    table.apply({"op": "scene_update", "scene": sid, "fields": {"los": False}})
    table.apply({"op": "token_move", "scene": sid, "id": orc, "x": 595, "y": 105})
    view = table.view_for("me")["scene"]
    assert "sight" not in view and {t["name"] for t in view["tokens"]} == {"Me", "Orc"}


def test_sight_range_and_the_partys_eyes(table):
    sid, _door, me, orc = _wall_scene(table)
    table.apply({"op": "wall_clear", "scene": sid})
    table.apply({"op": "token_update", "scene": sid, "id": me, "fields": {"vision": 30}})   # 6 squares of 5 ft
    sight = table.view_for("me")["scene"]["sight"]
    assert sight[0]["r"] == pytest.approx(420)
    assert not T.in_sight(sight, 595, 105)                          # the orc is 7 squares away
    table.apply({"op": "token_update", "scene": sid, "id": me, "fields": {"vision": None}})
    assert "Orc" in {t["name"] for t in table.view_for("me")["scene"]["tokens"]}
    # someone with no token of their own sees what the party sees
    assert len(table.view_for("someone-else")["scene"]["sight"]) == 1


def test_wall_commands_are_dm_only_clean_and_undoable(table):
    sid = make_scene(table)
    table.apply({"op": "scene_show", "scene": sid})
    with pytest.raises(T.CommandError):
        table.apply({"op": "wall_add", "scene": sid, "wall": {"pts": [0, 0, 70, 0]}}, actor="player")
    with pytest.raises(T.CommandError):
        table.apply({"op": "wall_add", "scene": sid, "wall": {"pts": [5, 5, 5, 5]}})        # no length
    ids = table.apply({"op": "wall_add", "scene": sid, "wall": {"pts": [0, 0, 70, 0], "open": True}})["walls"]
    wall = table.scene(sid)["walls"][0]
    assert wall["id"] == ids[0] and wall["door"] is False and wall["open"] is False
    table.apply({"op": "wall_update", "scene": sid, "id": ids[0], "fields": {"door": True, "open": True}})
    assert table.scene(sid)["walls"][0]["open"] is True
    assert table.undo() and table.scene(sid)["walls"][0]["door"] is False
    table.apply({"op": "wall_delete", "scene": sid, "ids": ids})
    assert table.scene(sid)["walls"] == []
    assert table.save() and T.Tabletop(table.path).scene(sid)["los"] is False


def test_the_visibility_polygon_matches_a_brute_force_check():
    import random
    rng = random.Random(7)
    scene = T.new_scene("x", width=1400, height=1000)
    scene["walls"] = [T.clean_wall({"pts": [rng.uniform(0, 1400), rng.uniform(0, 1000),
                                            rng.uniform(0, 1400), rng.uniform(0, 1000)]}) for _ in range(30)]
    eye = {"x": 700.5, "y": 500.5}
    sight = T.sight_for(scene, [eye])

    def crosses(a, b, c, d):
        def side(p, q, r):
            return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0]) > 0
        return side(a, c, d) != side(b, c, d) and side(a, b, c) != side(a, b, d)

    for _ in range(800):
        p = (rng.uniform(0, 1400), rng.uniform(0, 1000))
        blocked = any(crosses((eye["x"], eye["y"]), p, w[:2], w[2:]) for w in T.blocking_walls(scene))
        assert T.in_sight(sight, *p) == (not blocked)


def test_token_pictures_are_cut_square_keeping_a_portraits_top(tmp_path):
    from PIL import Image
    store = T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c"))
    tall = Image.new("RGB", (200, 600), (0, 0, 255))
    tall.paste((255, 0, 0), (0, 0, 200, 200))                     # a red "head" at the top
    asset, w, h = store.add_image(tall, token=True)
    assert (w, h) == (200, 200)
    with Image.open(store.path(asset)) as im:
        r, g, b = im.convert("RGB").getpixel((100, 60))
        assert r > 200 and b < 60
