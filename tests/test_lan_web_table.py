"""The browser tabletop's geometry (lan/web/geometry.js) agrees with the app's (tabletop.py).

The same random scenes, areas and points go through both, and every answer is compared. Needs Node.js to run
the JavaScript (GitHub's runners have it); without it these tests are skipped.
"""

import json
import math
import os
import random
import shutil
import subprocess

import pytest

import tabletop as T
from ui import tabletop_canvas as C

NODE = shutil.which("node")
GEOMETRY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lan", "web", "geometry.js")

pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is needed to run the page's JavaScript")

RUNNER = r"""
const G = require(process.argv[1]);
const cases = JSON.parse(require("fs").readFileSync(0, "utf8"));
const out = cases.map((c) => {
  const s = c.scene;
  const grid = G.Grid.of(s);
  switch (c.kind) {
    case "snap": return grid.snap(c.x, c.y, c.size);
    case "hex_at": return grid.hexAt(c.x, c.y);
    case "cells_between": return grid.cellsBetween(c.a, c.b);
    case "lines": return grid.linesIn(c.box[0], c.box[1], c.box[2], c.box[3]);
    case "distance": return G.distanceFt(s, c.a, c.b);
    case "ground": return G.groundAt(s, c.x, c.y);
    case "contains": return G.areaContains(s, c.area, c.x, c.y, c.z);
    case "footprint": return G.areaFootprint(s, c.area);
    case "cells": return G.areaCells(s, c.area);
    case "tokens": return G.areaTokens(s, c.area);
    case "clean": return G.cleanArea(c.area);
    case "axis": return G.axisSnap(...c.pts);
    case "box": return G.shapeBox(...c.pts, c.square, c.centred);
    case "text": return [G.areaText(c.area, s), G.heightText(c.feet)];
    case "letter": return G.tokenLetter(c.name);
    case "color": return G.conditionColor(c.name);
  }
  return null;
});
process.stdout.write(JSON.stringify(out));
"""


def run_js(cases):
    proc = subprocess.run([NODE, "-e", RUNNER, GEOMETRY], input=json.dumps(cases), capture_output=True,
                          text=True, encoding="utf-8", timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def close(a, b, tol=1e-6):
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(close(a[k], b[k], tol) for k in a)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=tol)
    return a == b


def random_scene(rng, grid):
    scene = T.new_scene("Test", width=1400, height=1000, cell=rng.choice([50.0, 70.0, 64.0]), grid=grid)
    scene["grid"]["ox"], scene["grid"]["oy"] = rng.uniform(-20, 20), rng.uniform(-20, 20)
    scene["grid"]["feet"] = rng.choice([5, 5, 5, 10])
    for _ in range(3):
        x, y, w, h = rng.uniform(0, 1100), rng.uniform(0, 700), rng.uniform(80, 300), rng.uniform(80, 300)
        scene["zones"].append(T.clean_zone({"pts": [x, y, x + w, y, x + w, y + h, x, y + h],
                                            "elev": rng.choice([5, 10, -10, 20])}))
    for i in range(8):
        t = T.new_token(f"T{i}", rng.uniform(0, 1400), rng.uniform(0, 1000),
                        size=rng.choice([0.5, 1.0, 2.0, 3.0]))
        t["z"] = rng.choice([0, 0, 10, -5, 30])
        scene["tokens"].append(t)
    return scene


def random_area(rng, scene):
    token = rng.choice(scene["tokens"] + [None, None])
    area = T.clean_area({"shape": rng.choice(T.AREA_SHAPES), "x": rng.uniform(100, 1300), "y": rng.uniform(100, 900),
                         "size": rng.choice([5, 10, 15, 20, 30, 60]), "width": rng.choice([5, 10]),
                         "dir": rng.uniform(-180, 360), "pitch": rng.choice([0, 0, 15, -30, 45]),
                         "dz": rng.choice([0, 0, 5, -5]), "token": token["id"] if token else ""})
    if token is not None:
        area["x"], area["y"] = token["x"], token["y"]
        area["base"] = T.token_elevation(scene, token)
    return area


def test_the_page_measures_and_lays_out_areas_like_the_app():
    rng = random.Random(7)
    cases, expected = [], []

    def add(case, value):
        cases.append(case)
        expected.append(value)

    for grid_kind in T.GRID_TYPES:
        for _ in range(6):
            scene = random_scene(rng, grid_kind)
            grid = T.Grid.of(scene)
            for _ in range(15):
                x, y = rng.uniform(-50, 1450), rng.uniform(-50, 1050)
                size = rng.choice([0.5, 1.0, 2.0, 3.0])
                add({"kind": "snap", "scene": scene, "x": x, "y": y, "size": size}, list(grid.snap(x, y, size)))
                if grid.kind.startswith("hex"):
                    add({"kind": "hex_at", "scene": scene, "x": x, "y": y}, list(grid.hex_at(x, y)))
                a = (x, y, rng.choice([0, 10, 25]))
                b = (rng.uniform(0, 1400), rng.uniform(0, 1000), rng.choice([0, 5, 40]))
                add({"kind": "cells_between", "scene": scene, "a": a[:2], "b": b[:2]}, grid.cells_between(a[:2], b[:2]))
                add({"kind": "distance", "scene": scene, "a": a, "b": b}, T.distance_ft(scene, a, b))
                add({"kind": "ground", "scene": scene, "x": x, "y": y}, T.ground_at(scene, x, y))
            box = [rng.uniform(0, 300), rng.uniform(0, 300), rng.uniform(600, 900), rng.uniform(500, 800)]
            add({"kind": "lines", "scene": scene, "box": box}, [list(map(float, ln)) for ln in grid.lines_in(*box)])
            for _ in range(10):
                area = random_area(rng, scene)
                add({"kind": "footprint", "scene": scene, "area": area}, T.area_footprint(scene, area))
                add({"kind": "cells", "scene": scene, "area": area}, [list(c) for c in T.area_cells(scene, area)])
                add({"kind": "tokens", "scene": scene, "area": area}, T.area_tokens(scene, area))
                add({"kind": "text", "scene": scene, "area": area, "feet": area["dz"]},
                    [C.area_text(area, scene), C.height_text(area["dz"])])
                for _ in range(10):
                    x, y, z = rng.uniform(0, 1400), rng.uniform(0, 1000), rng.uniform(-10, 40)
                    add({"kind": "contains", "scene": scene, "area": area, "x": x, "y": y, "z": z},
                        T.area_contains(scene, area, x, y, z))
    for _ in range(40):
        raw = {"shape": rng.choice(T.AREA_SHAPES), "x": rng.uniform(-100, 2000), "y": rng.uniform(-100, 2000),
               "size": rng.uniform(-10, 6000), "width": rng.uniform(0, 600), "dir": rng.uniform(-800, 800),
               "pitch": rng.uniform(-120, 120), "dz": rng.uniform(-20000, 20000), "color": rng.choice(["#E74C3C", "red"])}
        expected_area = T.clean_area(raw)
        add({"kind": "clean", "scene": {}, "area": raw}, dict(expected_area, id=""))
    for _ in range(40):
        pts = [rng.uniform(0, 500) for _ in range(2)]
        pts += [pts[0] + rng.choice([rng.uniform(-300, 300), rng.uniform(-3, 3)]),
                pts[1] + rng.choice([rng.uniform(-300, 300), rng.uniform(-3, 3)])]
        add({"kind": "axis", "scene": {}, "pts": pts}, list(C.axis_snap(*pts)))
        for square in (False, True):
            for centred in (False, True):
                add({"kind": "box", "scene": {}, "pts": pts, "square": square, "centred": centred},
                    C.shape_box(*pts, square=square, centred=centred))
    for name in ("Goblin", "  ogre", "3rd guard", "Ælfric", "", "!!", "élan"):
        add({"kind": "letter", "scene": {}, "name": name}, C.token_letter(name))
    for name in ("Prone", "Hexed", "Burning", "Glowing ember", "Ünicode", "x" * 70):
        add({"kind": "color", "scene": {}, "name": name}, T.condition_color(name))

    got = run_js(cases)
    wrong = [(c["kind"], e, g) for c, e, g in zip(cases, expected, got) if not close(e, g)]
    assert not wrong, f"{len(wrong)} of {len(cases)} differ, e.g. {wrong[:3]}"
