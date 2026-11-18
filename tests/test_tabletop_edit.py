"""Changing drawings and shapes after they're made: the sums (tabletop_shapes), the commands (who may change
what) and the mouse on the map (pick, move, resize)."""

import pytest

import tabletop as T
import tabletop_shapes as S
from tests.test_tabletop_ui import drag, fresh_fonts, page, pump, window, with_map  # noqa: F401 (fixtures)


# ---------------------------------------------------------------- the sums

def test_box_handles_resize_from_the_opposite_side():
    box = (100, 100, 200, 150)
    assert S.handle_points(box)["se"] == (200, 150) and S.handle_points(box)["n"] == (150, 100)
    assert S.resize_box(box, "se", 300, 250) == (100, 100, 300, 250)
    assert S.resize_box(box, "nw", 50, 80) == (50, 80, 200, 150)
    assert S.resize_box(box, "e", 260, 999) == (100, 100, 260, 150)          # an edge only moves its side
    assert S.resize_box(box, "w", 400, 0) == (200 - S.MIN_SIDE, 100, 200, 150)   # never pulled inside out


def test_shift_keeps_the_shape_and_ctrl_works_from_the_middle():
    box = (0, 0, 100, 50)
    x0, y0, x1, y1 = S.resize_box(box, "se", 300, 60, keep_ratio=True)
    assert (x0, y0) == (0, 0) and (x1, y1) == (300, 150)
    assert S.resize_box(box, "e", 150, 0, centred=True) == (-50, 0, 150, 50)
    x0, y0, x1, y1 = S.resize_box(box, "s", 0, 100, keep_ratio=True)
    assert (y0, y1) == (0, 100) and (x0, x1) == (-50, 150)                  # grows round its middle across


def test_refit_stretches_points_and_a_level_line_only_moves():
    assert S.refit([0, 0, 10, 20], (0, 0, 10, 20), (5, 5, 25, 45)) == [5, 5, 25, 45]
    assert S.refit([0, 10, 100, 10], (0, 10, 100, 10), (0, 30, 50, 30)) == [0, 30, 50, 30]
    assert S.move([1, 2, 3, 4], 10, -1) == [11, 1, 13, 3]
    assert S.reshape([0, 0, 50, 50], "p1", 80, 10) == [0, 0, 80, 10]
    assert S.reshape([0, 0, 5, 5, 50, 50], "se", 100, 100) == [0, 0, 10, 10, 100, 100]


def test_joined_walls_move_together_and_a_run_is_found():
    walls = [{"id": "a", "pts": [0, 0, 100, 0]}, {"id": "b", "pts": [100, 0, 100, 100]},
             {"id": "c", "pts": [100, 100, 0, 100]}, {"id": "d", "pts": [0, 100, 0, 0]},
             {"id": "x", "pts": [500, 500, 600, 500]}]
    ends = S.wall_ends_at(walls, 100, 0)
    assert sorted(ends) == [("a", 1), ("b", 0)]
    new = S.move_wall_ends(walls, ends, 140, -20)
    assert new == {"a": [0, 0, 140, -20], "b": [140, -20, 100, 100]}
    assert S.connected_walls(walls, "c") == ["a", "b", "c", "d"]
    assert S.connected_walls(walls, "x") == ["x"]
    assert S.move_wall_ends(walls, [("a", 1)], 0, 0) == {}                  # a wall can't shrink to nothing


def test_an_area_handle_sits_at_its_reach_and_dragging_it_sizes_it():
    scene = T.new_scene("M", cell=70)                                       # 70 px a square, 5 ft a square
    cone = T.clean_area({"shape": "cone", "x": 100, "y": 100, "size": 15, "dir": 0})
    hx, hy = S.area_handle(scene, cone)
    assert abs(hx - 310) < 1e-6 and abs(hy - 100) < 1e-6
    assert S.area_from_handle(scene, cone, 100, 100 + 70 * 6) == {"size": 30, "dir": 90.0}
    cube = T.clean_area({"shape": "cube", "x": 0, "y": 0, "size": 10, "dir": 180})
    assert S.area_handle(scene, cube) == (-140, 140)
    assert S.area_from_handle(scene, cube, 210, 70)["size"] == 15
    sphere = T.clean_area({"shape": "sphere", "x": 0, "y": 0, "size": 20, "dir": 0})
    assert S.area_from_handle(scene, sphere, 0, 1)["size"] == 5             # never under one step


# ---------------------------------------------------------------- the commands

@pytest.fixture
def table(tmp_path):
    t = T.Tabletop(str(tmp_path / "t.json"))
    sid = t.apply({"op": "scene_new", "scene_data": {"name": "Hall"}})["scene"]
    t.apply({"op": "scene_show", "scene": sid})
    t.apply({"op": "scene_update", "scene": sid, "fields": {"players_draw": True}})
    t.sid = sid
    return t


def test_a_player_moves_their_own_drawing_but_not_others(table):
    sid = table.sid
    mine = table.apply({"op": "draw_add", "scene": sid, "drawing": {"kind": "rect", "pts": [0, 0, 50, 50]}},
                       "cid-a")["drawing"]
    dms = table.apply({"op": "draw_add", "scene": sid, "drawing": {"kind": "line", "pts": [0, 0, 9, 9]}})["drawing"]
    table.apply({"op": "draw_update", "scene": sid, "id": mine, "fields": {"pts": [10, 10, 90, 70], "author": "x",
                                                                            "kind": "free"}}, "cid-a")
    d = next(d for d in table.scene(sid)["drawings"] if d["id"] == mine)
    assert d["pts"] == [10, 10, 90, 70] and d["author"] == "cid-a" and d["kind"] == "rect"
    with pytest.raises(T.CommandError, match="isn't yours"):
        table.apply({"op": "draw_update", "scene": sid, "id": dms, "fields": {"pts": [1, 1, 2, 2]}}, "cid-a")
    with pytest.raises(T.CommandError, match="couldn't be read"):
        table.apply({"op": "draw_update", "scene": sid, "id": mine, "fields": {"pts": [1]}}, "cid-a")
    table.apply({"op": "scene_update", "scene": sid, "fields": {"players_draw": False}})
    with pytest.raises(T.CommandError, match="turned drawing off"):
        table.apply({"op": "draw_update", "scene": sid, "id": mine, "fields": {"pts": [0, 0, 5, 5]}}, "cid-a")
    table.apply({"op": "draw_update", "scene": sid, "id": mine, "fields": {"pts": [0, 0, 5, 5]}})   # the DM may
    assert table.undo()
    assert next(d for d in table.scene(sid)["drawings"] if d["id"] == mine)["pts"] == [10, 10, 90, 70]


def test_walls_and_raised_ground_can_be_reshaped_by_the_dm_only(table):
    sid = table.sid
    ids = table.apply({"op": "wall_add", "scene": sid, "walls": [{"pts": [0, 0, 100, 0]},
                                                                  {"pts": [100, 0, 100, 100]}]})["walls"]
    table.apply({"op": "wall_reshape", "scene": sid, "walls": [{"id": ids[0], "pts": [0, 0, 120, 10]},
                                                                {"id": ids[1], "pts": [120, 10, 100, 100]}]})
    assert [w["pts"] for w in table.scene(sid)["walls"]] == [[0, 0, 120, 10], [120, 10, 100, 100]]
    with pytest.raises(T.CommandError, match="that short"):                  # all or nothing
        table.apply({"op": "wall_reshape", "scene": sid, "walls": [{"id": ids[0], "pts": [5, 5, 50, 5]},
                                                                    {"id": ids[1], "pts": [7, 7, 7, 7]}]})
    assert table.scene(sid)["walls"][0]["pts"] == [0, 0, 120, 10]
    with pytest.raises(T.CommandError, match="Only the DM"):
        table.apply({"op": "wall_reshape", "scene": sid, "walls": [{"id": ids[0], "pts": [0, 0, 9, 9]}]}, "cid-a")
    zone = table.apply({"op": "zone_add", "scene": sid, "zone": {"pts": [0, 0, 70, 0, 70, 70, 0, 70],
                                                                  "elev": 10}})["zone"]
    table.apply({"op": "zone_update", "scene": sid, "id": zone, "pts": [140, 0, 280, 0, 280, 140, 140, 140]})
    scene = table.scene(sid)
    assert scene["zones"][0]["elev"] == 10 and T.ground_at(scene, 200, 70) == 10 and T.ground_at(scene, 35, 35) == 0


def test_a_moved_drawing_reaches_the_players(table):
    sid = table.sid
    did = table.apply({"op": "draw_add", "scene": sid, "drawing": {"kind": "line", "pts": [0, 0, 50, 0]}},
                      "cid-a")["drawing"]
    table.apply({"op": "draw_update", "scene": sid, "id": did, "fields": {"pts": [0, 0, 80, 40]}}, "cid-a")
    seen = T.project(table.scene(sid), "cid-b")["scene"]["drawings"][0]
    assert seen["pts"] == [0, 0, 80, 40] and not seen["mine"]
    assert T.project(table.scene(sid), "cid-a")["scene"]["drawings"][0]["mine"]


# ---------------------------------------------------------------- the mouse

def click(c, x, y):
    c.event_generate("<ButtonPress-1>", x=int(x), y=int(y))
    c.event_generate("<ButtonRelease-1>", x=int(x), y=int(y))


def test_pick_move_and_resize_a_box_drawing(page, tk_root):
    sid = with_map(page, tk_root)
    c = page.canvas
    page._dispatch({"op": "draw_add", "drawing": {"kind": "rect", "pts": [100, 100, 200, 160]}})
    pump(tk_root)
    page.set_tool("select")
    drag(c, [c.to_screen(100, 130), c.to_screen(140, 150), c.to_screen(170, 170)])   # by its edge
    d = page.table_.scene(sid)["drawings"][0]
    assert c.picked == {"kind": "d", "ids": [d["id"]]}
    assert abs(d["pts"][0] - 170) < 2 and abs(d["pts"][1] - 140) < 2 and abs(d["pts"][2] - 270) < 2
    pump(tk_root)
    hx, hy = c.to_screen(*S.handle_points(S.bounds(d["pts"]))["se"])
    assert c._pick_handle_at(hx, hy) == "se"
    drag(c, [(hx, hy), (hx + 20, hy + 20), c.to_screen(370, 300)])
    d = page.table_.scene(sid)["drawings"][0]
    assert abs(d["pts"][0] - 170) < 2 and abs(d["pts"][2] - 370) < 2 and abs(d["pts"][3] - 300) < 2
    c.focus_force()
    c.event_generate("<Delete>")
    pump(tk_root)
    assert not page.table_.scene(sid)["drawings"] and c.picked is None


def test_a_line_end_moves_alone_and_clicking_empty_map_lets_go(page, tk_root):
    sid = with_map(page, tk_root)
    c = page.canvas
    page._dispatch({"op": "draw_add", "drawing": {"kind": "line", "pts": [100, 100, 300, 300]}})
    pump(tk_root)
    click(c, *c.to_screen(200, 200))
    pump(tk_root)
    assert c.picked and set(c._pick_handles()) == {"p0", "p1"}
    drag(c, [c.to_screen(300, 300), c.to_screen(350, 320), c.to_screen(400, 250)])
    pts = page.table_.scene(sid)["drawings"][0]["pts"]
    assert pts[:2] == [100, 100] and abs(pts[2] - 400) < 1 and abs(pts[3] - 250) < 1
    pump(tk_root)
    click(c, *c.to_screen(600, 60))
    assert c.picked is None


def test_dragging_a_wall_corner_keeps_the_room_closed_and_a_double_click_takes_the_whole_room(page, tk_root):
    sid = with_map(page, tk_root)
    c = page.canvas
    corners = [70, 70, 210, 70, 210, 210, 70, 210, 70, 70]
    page._dispatch({"op": "wall_add", "walls": [{"pts": corners[i:i + 4]} for i in range(0, 8, 2)]})
    pump(tk_root)
    walls = page.table_.scene(sid)["walls"]
    top = next(w for w in walls if w["pts"][1] == 70 and w["pts"][3] == 70)
    mid = c.to_screen(140, 70)
    click(c, *mid)
    pump(tk_root)
    assert c.picked == {"kind": "w", "ids": [top["id"]]}
    drag(c, [c.to_screen(210, 70), c.to_screen(250, 60), c.to_screen(279, 71)])   # onto a grid corner
    walls = page.table_.scene(sid)["walls"]
    assert sum(1 for w in walls for e in (0, 1) if w["pts"][2 * e:2 * e + 2] == [280, 70]) == 2
    assert not any(w["pts"][2 * e:2 * e + 2] == [210, 70] for w in walls for e in (0, 1))
    pump(tk_root)
    c._double(type("E", (), {"x": int(mid[0]), "y": int(mid[1])})())       # (Tk can't fake a double-click)
    pump(tk_root)
    assert sorted(c.picked["ids"]) == sorted(w["id"] for w in walls)
    drag(c, [c.to_screen(140, 140), c.to_screen(170, 150), c.to_screen(215, 135)])   # whole squares on a grid
    xs = sorted({p for w in page.table_.scene(sid)["walls"] for p in w["pts"][0::2]})
    assert xs == [140, 280, 350]                                               # (one corner was pulled out)
    assert page.table_.undo()
    assert sorted({p for w in page.table_.scene(sid)["walls"] for p in w["pts"][0::2]}) == [70, 210, 280]


def test_a_spell_area_grows_by_its_handle(page, tk_root):
    sid = with_map(page, tk_root)
    c = page.canvas
    page._dispatch({"op": "area_add", "area": {"shape": "cone", "x": 105, "y": 105, "size": 15, "dir": 0}})
    pump(tk_root)
    click(c, *c.to_screen(105, 105))
    pump(tk_root)
    area = page.table_.scene(sid)["areas"][0]
    assert c.picked == {"kind": "a", "ids": [area["id"]]}
    tip = c.to_screen(*S.area_handle(page.table_.scene(sid), area))
    assert c._pick_handle_at(*tip) == "reach"
    drag(c, [tip, c.to_screen(200, 200), c.to_screen(105, 105 + 70 * 6)])
    area = page.table_.scene(sid)["areas"][0]
    assert area["size"] == 30 and abs(area["dir"] - 90) < 0.5 and area["x"] == 105


def test_a_raised_area_is_moved_and_stretched(page, tk_root):
    sid = with_map(page, tk_root)
    c = page.canvas
    page._dispatch({"op": "zone_add", "zone": {"pts": [70, 70, 210, 70, 210, 210, 70, 210], "elev": 10}})
    pump(tk_root)
    drag(c, [c.to_screen(140, 70), c.to_screen(160, 80), c.to_screen(215, 75)])
    zone = page.table_.scene(sid)["zones"][0]
    assert zone["pts"][:2] == [140, 70] and zone["elev"] == 10
    pump(tk_root)
    hx, hy = c.to_screen(280, 210)
    assert c._pick_handle_at(hx, hy) == "se"
    drag(c, [(hx, hy), c.to_screen(330, 330), c.to_screen(350, 352)])
    assert S.bounds(page.table_.scene(sid)["zones"][0]["pts"]) == (140, 70, 350, 350)


def test_a_player_can_only_pick_their_own_drawings(window, tk_root, tmp_path):
    import tabletop_net as N
    from lan.service import CLIENT
    from ui.tabletop_view import TabletopView
    table = T.Tabletop(str(tmp_path / "t.json"))
    sid = table.apply({"op": "scene_new", "scene_data": {"name": "Cave", "w": 700, "h": 490, "cell": 70}})["scene"]
    table.apply({"op": "scene_show", "scene": sid})
    table.apply({"op": "scene_update", "scene": sid, "fields": {"players_draw": True}})
    table.apply({"op": "draw_add", "scene": sid, "drawing": {"kind": "line", "pts": [100, 100, 300, 100]}})
    table.apply({"op": "draw_add", "scene": sid, "drawing": {"kind": "line", "pts": [100, 300, 300, 300]}}, "me")

    class Service:
        role = CLIENT
        active = True

        def add_listener(self, fn):
            pass

        def remove_listener(self, fn):
            pass

    class Remote(N.LocalTable):
        role = "player"

        def view(self):
            return T.project(self.table.scene(self.scene_id), "me", rev=1)

        def dispatch(self, cmd):
            return self.table.apply(dict(cmd, scene=self.scene_id), "me", "Me")

        def on_error(self, fn):
            pass

    remote = Remote(table, T.AssetStore(str(tmp_path / "a"), str(tmp_path / "c")))
    view = TabletopView(window, {}, table=table, service=Service(), remote_backend=lambda: remote)
    view.pack(fill="both", expand=True)
    pump(tk_root, 10)
    c = view.canvas
    c.fit()
    pump(tk_root)
    assert c._shape_at(*c.to_screen(200, 100)) is None
    drag(c, [c.to_screen(200, 300), c.to_screen(220, 330), c.to_screen(200, 370)])
    theirs, mine = [d["pts"] for d in table.scene(sid)["drawings"]]
    assert theirs == [100, 100, 300, 100] and abs(mine[1] - 370) < 1 and abs(mine[3] - 370) < 1
    view.destroy()


# ---------------------------------------------------------------- the browser's copy of the sums

def test_the_browser_resizes_shapes_and_areas_like_the_app():
    import json
    import os
    import random
    import shutil
    import subprocess
    from tests.test_lan_web_table import close, random_area, random_scene
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is needed to run the page's JavaScript")
    geometry = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lan", "web", "geometry.js")
    runner = r"""
const G = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(cases.map((c) => {
  if (c.kind === "box") return G.resizeBox(c.box, c.handle, c.x, c.y, c.ratio, c.centred);
  if (c.kind === "reshape") return G.reshape(c.pts, c.handle, c.x, c.y, null, c.ratio, c.centred);
  if (c.kind === "move") return G.movePts(c.pts, c.x, c.y);
  if (c.kind === "handle") return G.areaHandle(c.scene, c.area);
  return G.areaFromHandle(c.scene, c.area, c.x, c.y);
})));
"""
    rng = random.Random(11)
    cases, expected = [], []
    for _ in range(150):
        pts = [round(rng.uniform(-200, 900), 1) for _ in range(rng.choice([4, 4, 10, 30]))]
        box = S.bounds(pts)
        handle = rng.choice(S.HANDLES + ("p0", "p1"))
        x, y, ratio, centred = rng.uniform(-300, 1200), rng.uniform(-300, 1200), rng.random() < 0.4, rng.random() < 0.3
        if handle in S.HANDLES:
            cases.append({"kind": "box", "box": box, "handle": handle, "x": x, "y": y, "ratio": ratio,
                          "centred": centred})
            expected.append(list(S.resize_box(box, handle, x, y, keep_ratio=ratio, centred=centred)))
        cases.append({"kind": "reshape", "pts": pts, "handle": handle, "x": x, "y": y, "ratio": ratio,
                      "centred": centred})
        expected.append(S.reshape(pts, handle, x, y, keep_ratio=ratio, centred=centred))
        cases.append({"kind": "move", "pts": pts, "x": x, "y": y})
        expected.append(S.move(pts, x, y))
    for grid in T.GRID_TYPES:
        scene = random_scene(rng, grid)
        for _ in range(30):
            area = random_area(rng, scene)
            cases.append({"kind": "handle", "scene": scene, "area": area})
            expected.append(list(S.area_handle(scene, area)))
            x, y = rng.uniform(0, 1400), rng.uniform(0, 1000)
            cases.append({"kind": "from", "scene": scene, "area": area, "x": x, "y": y})
            expected.append(S.area_from_handle(scene, area, x, y))
    proc = subprocess.run([node, "-e", runner, geometry], input=json.dumps(cases), capture_output=True, text=True,
                          encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    bad = [(c, e, g) for c, e, g in zip(cases, expected, got) if not close(e, g, 0.11)]
    assert not bad, bad[:3]
