"""The virtual tabletop: scenes (a map with a grid), tokens, drawings and fog, with no widgets.

A **scene** is one map: a picture (or a blank area), a grid laid over it (square, hex in rows, hex in columns, or
none), the tokens standing on it, what has been drawn on it and the fog that hides what the players haven't
found yet. Positions are in the map picture's own pixels, so the grid and tokens stay put however the map is
zoomed.

Everything that changes a scene is a **command**, a small dict such as ``{"op": "token_move", "scene": id,
"id": token_id, "x": 140, "y": 280}``. :meth:`Tabletop.apply` runs one, as the DM or as a player, and decides
whether that person may: the DM may do anything; a player may move the tokens they own (or any token, when the
scene allows it), draw (when the scene allows it) and erase what they drew. The same commands come from the
DM's own screen and, over a LAN session, from the players' (see ``tabletop_net.py``).

:func:`project` turns a scene into a **view**: the plain dict a screen draws. A player's view leaves out hidden
tokens, the DM's private drawings and, for tokens that aren't theirs, the hit points, so none of it ever reaches
a player's computer.

Pictures (maps and token art) are **assets**: files named by a hash of their contents in
``user_data/tabletop/assets``, shrunk when they are added so a map stays a few hundred KB to a couple of MB.
Players get them from the DM once and keep them in ``tabletop/cache``.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import os
import re
import secrets
import shutil
import threading
import zipfile
from collections import OrderedDict
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from paths import user_data_path

GRID_TYPES = ("square", "hex_rows", "hex_cols", "none")
GRID_LABELS = {"square": "Squares", "hex_rows": "Hexes (rows)", "hex_cols": "Hexes (columns)", "none": "No grid"}
TOKEN_SIZES = {"Tiny": 0.5, "Small": 1.0, "Medium": 1.0, "Large": 2.0, "Huge": 3.0, "Gargantuan": 4.0}
DRAW_KINDS = ("free", "line", "rect", "ellipse")
FOG_SHAPES = ("rect", "ellipse", "poly")

MAP_MAX_SIDE = 3072           # a bigger map is shrunk to this (memory on small machines, and sending it)
TOKEN_MAX_SIDE = 256
MAX_ASSET_BYTES = 12 * 1024 * 1024
MAX_TOKENS = 400
MAX_DRAWINGS = 2000
MAX_FOG_OPS = 600
MAX_WALLS = 3000
MAX_POINTS = 600              # points in one freehand line or fog polygon
MAX_TEXT = 60
IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")

DEFAULT_COLORS = ["#C0392B", "#2471A3", "#229954", "#D68910", "#7D3C98", "#17A589", "#CA6F1E", "#5D6D7E"]

# The colour of each condition's segment in a token's ring
CONDITION_COLORS = {
    "Blinded": "#5D6D7E", "Charmed": "#E91E63", "Deafened": "#95A5A6", "Exhaustion": "#6E2C00",
    "Frightened": "#8E44AD", "Grappled": "#D35400", "Incapacitated": "#7F8C8D", "Invisible": "#AED6F1",
    "Paralyzed": "#F1C40F", "Petrified": "#A6ACAF", "Poisoned": "#27AE60", "Prone": "#A04000",
    "Restrained": "#B9770E", "Stunned": "#F4D03F", "Unconscious": "#17202A", "Concentrating": "#3498DB",
    "Dodging": "#48C9B0", "Hasted": "#F39C12", "Blessed": "#F7DC6F", "Hexed": "#4A235A", "Marked": "#E74C3C",
    "Raging": "#922B21", "Dead": "#000000", "Bloodied": "#C0392B",
}


def condition_color(name: str) -> str:
    """A condition's ring colour (a made-up condition gets a steady colour of its own)."""
    if name in CONDITION_COLORS:
        return CONDITION_COLORS[name]
    h = int(hashlib.md5(name.lower().encode("utf-8")).hexdigest()[:6], 16)
    return "#%02X%02X%02X" % (80 + (h >> 16) % 150, 80 + (h >> 8) % 150, 80 + h % 150)


def new_id() -> str:
    return secrets.token_hex(5)


def _num(value, default: float = 0.0, lo: float = -1e7, hi: float = 1e7) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(v) or math.isinf(v):
        return default
    return max(lo, min(hi, v))


def _text(value, limit: int = MAX_TEXT) -> str:
    return " ".join(str(value or "").split())[:limit]


_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _color(value, default: str) -> str:
    return value if isinstance(value, str) and _COLOR.match(value) else default


_ASSET_ID = re.compile(r"^[0-9a-f]{20}$")


def valid_asset_id(value) -> bool:
    return isinstance(value, str) and bool(_ASSET_ID.match(value))


# --------------------------------------------------------------------------- #
# Geometry: grids, snapping and distance
# --------------------------------------------------------------------------- #

SQRT3 = math.sqrt(3.0)


class Grid:
    """A scene's grid. ``cell`` is the distance between neighbouring cell centres, in map pixels."""

    def __init__(self, kind: str = "square", cell: float = 70.0, ox: float = 0.0, oy: float = 0.0):
        self.kind = kind if kind in GRID_TYPES else "square"
        self.cell = max(8.0, float(cell))
        self.ox, self.oy = float(ox), float(oy)

    @classmethod
    def of(cls, scene: dict) -> "Grid":
        g = scene.get("grid") or {}
        return cls(g.get("type", "square"), g.get("cell", 70), g.get("ox", 0), g.get("oy", 0))

    # pointy-top hexes in rows; hexes in columns are the same with x and y swapped
    def _swap(self, x: float, y: float) -> Tuple[float, float]:
        return (y, x) if self.kind == "hex_cols" else (x, y)

    def hex_center(self, q: int, r: int) -> Tuple[float, float]:
        s = self.cell
        ox, oy = self._swap(self.ox, self.oy)
        x, y = ox + s * (q + r / 2.0), oy + r * s * SQRT3 / 2.0
        return self._swap(x, y)

    def hex_at(self, x: float, y: float) -> Tuple[int, int]:
        """The axial (q, r) of the hex that contains the point."""
        x, y = self._swap(x, y)
        ox, oy = self._swap(self.ox, self.oy)
        s = self.cell
        r = (y - oy) / (s * SQRT3 / 2.0)
        q = (x - ox) / s - r / 2.0
        # cube rounding
        cx, cz = q, r
        cy = -cx - cz
        rx, ry, rz = round(cx), round(cy), round(cz)
        dx, dy, dz = abs(rx - cx), abs(ry - cy), abs(rz - cz)
        if dx > dy and dx > dz:
            rx = -ry - rz
        elif dy > dz:
            ry = -rx - rz
        else:
            rz = -rx - ry
        return int(rx), int(rz)

    def hex_corners(self, q: int, r: int) -> List[Tuple[float, float]]:
        cx, cy = self._swap(*self.hex_center(q, r))
        radius = self.cell / SQRT3
        pts = []
        for i in range(6):
            a = math.radians(60 * i - 30)
            pts.append(self._swap(cx + radius * math.cos(a), cy + radius * math.sin(a)))
        return pts

    def snap(self, x: float, y: float, size: float = 1.0) -> Tuple[float, float]:
        """Where a token of ``size`` cells whose centre is dropped at (x, y) settles (its new centre)."""
        if self.kind == "none":
            return x, y
        if self.kind == "square":
            s = self.cell
            if size < 1:                      # tiny: quarter-cell steps
                step = s / 2.0
                return (self.ox + (math.floor((x - self.ox) / step) + 0.5) * step,
                        self.oy + (math.floor((y - self.oy) / step) + 0.5) * step)
            span = max(1, int(round(size)))
            # top-left cell of the footprint, then the footprint's centre
            left = round((x - self.ox) / s - span / 2.0)
            top = round((y - self.oy) / s - span / 2.0)
            return self.ox + (left + span / 2.0) * s, self.oy + (top + span / 2.0) * s
        return self.hex_center(*self.hex_at(x, y))

    def cells_between(self, a: Tuple[float, float], b: Tuple[float, float]) -> float:
        """How many cells apart two points are (the 2024 rules: a diagonal square counts as one)."""
        if self.kind == "square":
            dx = abs(b[0] - a[0]) / self.cell
            dy = abs(b[1] - a[1]) / self.cell
            return max(round(dx), round(dy))
        if self.kind in ("hex_rows", "hex_cols"):
            q1, r1 = self.hex_at(*a)
            q2, r2 = self.hex_at(*b)
            dq, dr = q2 - q1, r2 - r1
            return (abs(dq) + abs(dr) + abs(dq + dr)) / 2
        return math.hypot(b[0] - a[0], b[1] - a[1]) / self.cell

    def lines_in(self, x0: float, y0: float, x1: float, y1: float, limit: int = 4000) -> List[List[float]]:
        """The grid's lines (or hex outlines) that cross a box, as flat point lists in map pixels."""
        out: List[List[float]] = []
        if self.kind == "square":
            s = self.cell
            i = math.floor((x0 - self.ox) / s)
            while True:
                x = self.ox + i * s
                if x > x1 or len(out) > limit:
                    break
                out.append([x, y0, x, y1])
                i += 1
            j = math.floor((y0 - self.oy) / s)
            while True:
                y = self.oy + j * s
                if y > y1 or len(out) > limit:
                    break
                out.append([x0, y, x1, y])
                j += 1
            return out
        if self.kind in ("hex_rows", "hex_cols"):
            # every hex whose centre is within one cell of the box
            pad = self.cell
            qa, ra = self.hex_at(x0 - pad, y0 - pad)
            qb, rb = self.hex_at(x1 + pad, y1 + pad)
            qc, rc = self.hex_at(x0 - pad, y1 + pad)
            qd, rd = self.hex_at(x1 + pad, y0 - pad)
            rs = [ra, rb, rc, rd]
            qs = [qa, qb, qc, qd]
            r_lo, r_hi = min(rs) - 1, max(rs) + 1
            q_lo, q_hi = min(qs) - (r_hi - r_lo) - 1, max(qs) + (r_hi - r_lo) + 1
            for r in range(r_lo, r_hi + 1):
                for q in range(q_lo, q_hi + 1):
                    cx, cy = self.hex_center(q, r)
                    if x0 - pad <= cx <= x1 + pad and y0 - pad <= cy <= y1 + pad:
                        pts = self.hex_corners(q, r)
                        # three edges per hex draw every edge once (neighbours draw the rest)
                        out.append([pts[3][0], pts[3][1], pts[4][0], pts[4][1], pts[5][0], pts[5][1],
                                    pts[0][0], pts[0][1]])
                        if len(out) > limit:
                            return out
            return out
        return out


# --------------------------------------------------------------------------- #
# Scenes and tokens
# --------------------------------------------------------------------------- #

def new_scene(name: str, map_asset: str = "", width: int = 0, height: int = 0, cell: float = 70.0,
              grid: str = "square") -> dict:
    """A fresh scene. With no map, the area is ``width`` x ``height`` pixels (default 30 x 20 cells)."""
    if not width or not height:
        width, height = int(cell * 30), int(cell * 20)
    return {
        "id": new_id(), "name": _text(name) or "Scene", "map": map_asset if valid_asset_id(map_asset) else "",
        "w": int(width), "h": int(height), "bg": "#2B2B2B",
        "grid": {"type": grid if grid in GRID_TYPES else "square", "cell": float(cell), "ox": 0.0, "oy": 0.0,
                 "color": "#000000", "opacity": 0.35, "feet": 5},
        "fog": {"on": False, "ops": []},
        "tokens": [], "drawings": [], "walls": [], "los": False,
        "players_move_all": False, "players_draw": True,
    }


def new_token(name: str, x: float, y: float, *, size: float = 1.0, color: str = "", image: str = "",
              hp: Optional[int] = None, hp_max: Optional[int] = None, owner: str = "", owner_name: str = "",
              hidden: bool = False, kind: str = "npc") -> dict:
    return {
        "id": new_id(), "name": _text(name) or "Token", "x": float(x), "y": float(y),
        "size": size if size in TOKEN_SIZES.values() else 1.0,
        "color": _color(color, DEFAULT_COLORS[0]), "image": image if valid_asset_id(image) else "",
        "hp": hp, "hp_max": hp_max, "conditions": [], "owner": owner, "owner_name": _text(owner_name, 32),
        "hidden": bool(hidden), "kind": kind if kind in ("npc", "pc", "prop") else "npc", "show_name": True,
        "vision": 0.0,
    }


TOKEN_FIELDS = {"name", "size", "color", "image", "hp", "hp_max", "conditions", "owner", "owner_name", "hidden",
                "kind", "show_name", "x", "y", "entry", "source", "vision"}
PRIVATE_TOKEN_FIELDS = ("entry", "source")    # the DM's bookkeeping, never sent to players
SCENE_FIELDS = {"name", "bg", "players_move_all", "players_draw", "w", "h", "los"}
GRID_FIELDS = {"type", "cell", "ox", "oy", "color", "opacity", "feet"}


def _clean_token_fields(fields: dict) -> dict:
    out = {}
    for k, v in fields.items():
        if k not in TOKEN_FIELDS:
            continue
        if k == "name":
            out[k] = _text(v) or "Token"
        elif k == "owner_name":
            out[k] = _text(v, 32)
        elif k == "owner":
            out[k] = _text(v, 64)
        elif k in ("entry", "source"):
            out[k] = _text(v, 80)
        elif k == "size":
            out[k] = _num(v, 1.0, 0.5, 4.0)
        elif k == "color":
            out[k] = _color(v, DEFAULT_COLORS[0])
        elif k == "image":
            out[k] = v if valid_asset_id(v) else ""
        elif k in ("hp", "hp_max"):
            out[k] = None if v is None or v == "" else int(_num(v, 0, -9999, 99999))
        elif k == "conditions":
            names = []
            for c in (v if isinstance(v, list) else []):
                c = _text(c, 40)
                if c and c not in names:
                    names.append(c)
            out[k] = names[:20]
        elif k in ("hidden", "show_name"):
            out[k] = bool(v)
        elif k == "kind":
            out[k] = v if v in ("npc", "pc", "prop") else "npc"
        elif k in ("x", "y"):
            out[k] = _num(v)
        elif k == "vision":
            out[k] = 0.0 if v in (None, "") else _num(v, 0.0, 0.0, 5280.0)
    return out


def _clean_points(points, limit: int = MAX_POINTS) -> List[float]:
    if not isinstance(points, list):
        return []
    pts = [_num(p) for p in points[: limit * 2]]
    return pts[: len(pts) // 2 * 2]


def clean_drawing(d: dict, author: str = "") -> Optional[dict]:
    if not isinstance(d, dict) or d.get("kind") not in DRAW_KINDS:
        return None
    pts = _clean_points(d.get("pts"))
    if len(pts) < 4:
        return None
    return {"id": _text(d.get("id"), 16) or new_id(), "kind": d["kind"], "pts": pts,
            "color": _color(d.get("color"), "#E74C3C"), "width": _num(d.get("width"), 4, 1, 40),
            "author": author, "private": bool(d.get("private"))}


def clean_fog_op(op: dict) -> Optional[dict]:
    if not isinstance(op, dict) or op.get("shape") not in FOG_SHAPES or op.get("mode") not in ("reveal", "hide"):
        return None
    pts = _clean_points(op.get("pts"))
    if len(pts) < 4 or (op["shape"] == "poly" and len(pts) < 6):
        return None
    return {"mode": op["mode"], "shape": op["shape"], "pts": pts}


def clean_wall(w: dict) -> Optional[dict]:
    """A wall (or door) is one straight segment: ``pts`` = [x0, y0, x1, y1]."""
    if not isinstance(w, dict):
        return None
    pts = _clean_points(w.get("pts"), 2)
    if len(pts) != 4 or (abs(pts[2] - pts[0]) < 0.5 and abs(pts[3] - pts[1]) < 0.5):
        return None
    return {"id": _text(w.get("id"), 16) or new_id(), "pts": [round(p, 1) for p in pts],
            "door": bool(w.get("door")), "open": bool(w.get("door")) and bool(w.get("open"))}


def token_box(token: dict, grid: Grid) -> Tuple[float, float, float]:
    """``(centre x, centre y, radius)`` of a token in map pixels."""
    return token["x"], token["y"], max(4.0, token.get("size", 1.0) * grid.cell / 2.0)


# --------------------------------------------------------------------------- #
# Walls and line of sight
# --------------------------------------------------------------------------- #
#
# With line of sight on, a player sees only what their tokens can see: each token's eye is its centre, and its
# view is the visibility polygon around it (the area no wall stands in front of), cut to the token's sight range
# when it has one. Tokens outside every polygon are left out of the player's view, like hidden ones.
#
# The polygon comes from casting a ray just either side of every wall end. To stay quick in plain Python, each
# ray tries the walls nearest the eye first and stops once no further wall could be closer than its hit, and
# polygons are kept in a small cache keyed on the eye and the walls.

_SIGHT_CACHE: "OrderedDict[tuple, List[float]]" = OrderedDict()
_SIGHT_CACHE_SIZE = 256
_EPS = 1e-4


def blocking_walls(scene: dict) -> List[Tuple[float, float, float, float]]:
    """The segments that block sight: every wall, and every door that is closed."""
    return [tuple(w["pts"]) for w in scene.get("walls") or [] if not (w.get("door") and w.get("open"))]


def _seg_distance(ex: float, ey: float, s: Tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = s
    dx, dy = x1 - x0, y1 - y0
    length = dx * dx + dy * dy
    u = 0.0 if length == 0 else max(0.0, min(1.0, ((ex - x0) * dx + (ey - y0) * dy) / length))
    return math.hypot(x0 + u * dx - ex, y0 + u * dy - ey)


def visibility_polygon(ex: float, ey: float, walls: List[Tuple[float, float, float, float]],
                       box: Tuple[float, float, float, float]) -> List[float]:
    """The area visible from (ex, ey), as a flat point list, inside ``box`` (x0, y0, x1, y1)."""
    bx0, by0, bx1, by1 = min(box[0], ex - 1), min(box[1], ey - 1), max(box[2], ex + 1), max(box[3], ey + 1)
    segs = list(walls)
    segs += [(bx0, by0, bx1, by0), (bx1, by0, bx1, by1), (bx1, by1, bx0, by1), (bx0, by1, bx0, by0)]
    order = sorted(((_seg_distance(ex, ey, s), s) for s in segs), key=lambda p: p[0])
    angles = set()
    for _d, (x0, y0, x1, y1) in order:
        for px, py in ((x0, y0), (x1, y1)):
            if bx0 <= px <= bx1 and by0 <= py <= by1:
                a = math.atan2(py - ey, px - ex)
                angles.add(round(a, 6))
    rays = sorted({a + d for a in angles for d in (-_EPS, _EPS)})
    far = math.hypot(bx1 - bx0, by1 - by0) * 2
    out: List[float] = []
    for a in rays:
        dx, dy = math.cos(a), math.sin(a)
        best = far
        for dist, (x0, y0, x1, y1) in order:
            if dist >= best:
                break
            sx, sy = x1 - x0, y1 - y0
            denom = dx * sy - dy * sx
            if -1e-12 < denom < 1e-12:
                continue
            ox, oy = x0 - ex, y0 - ey
            t = (ox * sy - oy * sx) / denom
            if t <= 1e-6 or t >= best:
                continue
            u = (ox * dy - oy * dx) / denom
            if -1e-9 <= u <= 1 + 1e-9:
                best = t
        out.extend((round(ex + dx * best, 1), round(ey + dy * best, 1)))
    return out


def point_in_polygon(x: float, y: float, pts: List[float]) -> bool:
    inside = False
    n = len(pts) // 2
    j = n - 1
    for i in range(n):
        xi, yi, xj, yj = pts[2 * i], pts[2 * i + 1], pts[2 * j], pts[2 * j + 1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def sight_range(token: dict, scene: dict) -> float:
    """How far a token sees, in map pixels (0 = no limit)."""
    feet = token.get("vision") or 0
    g = scene.get("grid") or {}
    if feet <= 0 or not g.get("feet"):
        return 0.0
    return feet / float(g["feet"]) * float(g.get("cell", 70))


def eye_sight(scene: dict, token: dict, walls=None) -> dict:
    """One token's view: ``{"x", "y", "r", "pts"}`` (``r`` 0 = no limit)."""
    walls = blocking_walls(scene) if walls is None else walls
    r = sight_range(token, scene)
    ex, ey = float(token["x"]), float(token["y"])
    cell = float((scene.get("grid") or {}).get("cell", 70))
    if r > 0:
        box = (ex - r - cell, ey - r - cell, ex + r + cell, ey + r + cell)
        walls = [w for w in walls if _seg_distance(ex, ey, w) <= r]
    else:
        box = (-cell, -cell, scene["w"] + cell, scene["h"] + cell)
    key = (round(ex, 1), round(ey, 1), box, hash(tuple(walls)), len(walls))
    pts = _SIGHT_CACHE.get(key)
    if pts is None:
        pts = visibility_polygon(ex, ey, walls, box)
        _SIGHT_CACHE[key] = pts
        while len(_SIGHT_CACHE) > _SIGHT_CACHE_SIZE:
            _SIGHT_CACHE.popitem(last=False)
    else:
        _SIGHT_CACHE.move_to_end(key)
    return {"x": ex, "y": ey, "r": round(r, 1), "pts": pts}


def sight_for(scene: dict, eyes: Iterable[dict]) -> List[dict]:
    walls = blocking_walls(scene)
    return [eye_sight(scene, t, walls) for t in eyes]


def eyes_for(scene: dict, viewer: str) -> List[dict]:
    """Whose eyes a player sees through: their own tokens, or (if they have none) the party's."""
    shown = [t for t in scene["tokens"] if not t.get("hidden")]
    mine = [t for t in shown if viewer and t.get("owner") == viewer]
    return mine or [t for t in shown if t.get("kind") == "pc"]


def in_sight(sight: List[dict], x: float, y: float) -> bool:
    for s in sight:
        if s["r"] and math.hypot(x - s["x"], y - s["y"]) > s["r"]:
            continue
        if point_in_polygon(x, y, s["pts"]):
            return True
    return False


def token_in_sight(sight: List[dict], token: dict, grid: Grid) -> bool:
    """Whether any part of a token is seen (its centre, or a point near its edge)."""
    cx, cy, r = token_box(token, grid)
    if in_sight(sight, cx, cy):
        return True
    k = r * 0.85
    for i in range(8):
        a = i * math.pi / 4
        if in_sight(sight, cx + k * math.cos(a), cy + k * math.sin(a)):
            return True
    return False


# --------------------------------------------------------------------------- #
# Views: what one person may see of a scene
# --------------------------------------------------------------------------- #

DM = "dm"


def project(scene: Optional[dict], viewer: str = DM, *, rev: int = 0, turn=()) -> dict:
    """The scene as ``viewer`` (``DM``, or a player's install id) may see it. ``turn`` holds the
    initiative entries whose turn it is: their tokens get ``"turn": True``."""
    if scene is None:
        return {"rev": rev, "scene": None, "role": "dm" if viewer == DM else "player"}
    if viewer == DM:
        view = copy.deepcopy(scene)
        for t in view["tokens"]:
            t["turn"] = bool(t.get("entry")) and t["entry"] in turn
        return {"rev": rev, "scene": view, "role": "dm"}
    s = {k: copy.deepcopy(v) for k, v in scene.items() if k not in ("tokens", "drawings", "fog", "walls")}
    s["tokens"] = []
    sight = None
    if scene.get("los"):
        # the walls themselves stay with the DM (a secret door is a wall too); the player gets what they see
        sight = sight_for(scene, eyes_for(scene, viewer))
        s["sight"] = sight
    grid = Grid.of(scene)
    for t in scene["tokens"]:
        if t.get("hidden"):
            continue
        if sight is not None and t.get("owner") != viewer and not token_in_sight(sight, t, grid):
            continue
        t = dict(t)
        t["turn"] = bool(t.get("entry")) and t["entry"] in turn
        for k in PRIVATE_TOKEN_FIELDS:
            t.pop(k, None)
        t["conditions"] = list(t.get("conditions") or [])
        if t.get("owner") != viewer:
            # other creatures' numbers stay with the DM; a player sees a rough state instead
            hp, hp_max = t.get("hp"), t.get("hp_max")
            if hp is not None and hp_max:
                if hp <= 0:
                    t["state"] = "down"
                elif hp * 2 <= hp_max:
                    t["state"] = "bloodied"
            t["hp"] = t["hp_max"] = None
            t["mine"] = False
        else:
            t["mine"] = True
        s["tokens"].append(t)
    s["drawings"] = [dict(d) for d in scene["drawings"] if not d.get("private")]
    s["fog"] = {"on": scene["fog"]["on"], "ops": copy.deepcopy(scene["fog"]["ops"])}
    return {"rev": rev, "scene": s, "role": "player"}


# --------------------------------------------------------------------------- #
# The tabletop: every scene, the one the players are shown, and the commands
# --------------------------------------------------------------------------- #

class CommandError(Exception):
    """A command that may not or cannot be run (the message says why, for the person who sent it)."""


class Tabletop:
    """All scenes, saved in ``tabletop.json``. Listeners hear ``(scene_id or None)`` after every change."""

    UNDO_DEPTH = 40

    def __init__(self, path: Optional[str] = None):
        self.path = path or user_data_path(os.path.join("tabletop", "tabletop.json"))
        self.scenes: Dict[str, dict] = {}
        self.order: List[str] = []
        self.shown: str = ""              # the scene the players see ("" = none)
        self.rev = 0
        self.turn: Tuple[str, ...] = ()   # initiative entries whose turn it is (not saved)
        self._listeners: List[Callable[[Optional[str]], None]] = []
        self._undo: List[Tuple[str, Optional[dict], List[str], str]] = []
        self._lock = threading.RLock()
        self.load()

    # ---- storage

    def load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        for s in data.get("scenes", []):
            if isinstance(s, dict) and s.get("id"):
                self.scenes[s["id"]] = self._repair(s)
                self.order.append(s["id"])
        self.shown = data.get("shown", "") if data.get("shown") in self.scenes else ""

    @staticmethod
    def _repair(scene: dict) -> dict:
        base = new_scene(scene.get("name", "Scene"))
        for k, v in base.items():
            if k not in scene:
                scene[k] = v
        for k, v in base["grid"].items():
            scene["grid"].setdefault(k, v)
        scene["fog"].setdefault("on", False)
        scene["fog"].setdefault("ops", [])
        return scene

    def save(self) -> bool:
        from atomic_io import atomic_write_json
        with self._lock:
            data = {"version": 1, "shown": self.shown, "scenes": [self.scenes[i] for i in self.order]}
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                atomic_write_json(self.path, data)
                return True
            except OSError as e:
                print(f"Tabletop: could not save: {e}")
                return False

    # ---- listeners

    def add_listener(self, fn: Callable[[Optional[str]], None]) -> None:
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[Optional[str]], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    def _changed(self, scene_id: Optional[str]) -> None:
        self.rev += 1
        for fn in list(self._listeners):
            try:
                fn(scene_id)
            except Exception as e:
                print(f"Tabletop listener failed: {e}")

    # ---- reading

    def scene(self, scene_id: str) -> Optional[dict]:
        return self.scenes.get(scene_id)

    def scene_list(self) -> List[dict]:
        return [self.scenes[i] for i in self.order]

    def shown_scene(self) -> Optional[dict]:
        return self.scenes.get(self.shown)

    def view_for(self, viewer: str) -> dict:
        """A player's view of the scene they're shown."""
        return project(self.shown_scene(), viewer, rev=self.rev, turn=self.turn)

    # ---- the initiative tracker's side (see tabletop_initiative): no undo, these follow the tracker

    def link_tokens(self, scene_id: str, changes: Dict[str, dict]) -> None:
        """Set fields on several tokens of one map at once, outside the undo history."""
        with self._lock:
            scene = self.scenes.get(scene_id)
            if scene is None:
                return
            changed = False
            for t in scene["tokens"]:
                fields = _clean_token_fields(changes.get(t["id"]) or {})
                if any(t.get(k) != v for k, v in fields.items()):
                    t.update(fields)
                    changed = True
        if changed:
            self._changed(scene_id)

    def set_turn(self, entry_ids) -> None:
        turn = tuple(entry_ids)
        if turn != self.turn:
            self.turn = turn
            self._changed(None)

    # ---- undo (the DM's own changes)

    def _remember(self, scene_id: str, label: str) -> None:
        before = copy.deepcopy(self.scenes.get(scene_id))
        self._undo.append((scene_id, before, list(self.order), self.shown))
        del self._undo[:-self.UNDO_DEPTH]

    def can_undo(self) -> bool:
        return bool(self._undo)

    def undo(self) -> bool:
        if not self._undo:
            return False
        scene_id, before, order, shown = self._undo.pop()
        if before is None:
            self.scenes.pop(scene_id, None)
        else:
            self.scenes[scene_id] = before
        self.order = [i for i in order if i in self.scenes]
        self.shown = shown if shown in self.scenes else ""
        self._changed(scene_id)
        return True

    # ---- commands

    def apply(self, cmd: dict, actor: str = DM, actor_name: str = "") -> dict:
        """Run one command as ``actor`` (``DM`` or a player's install id). Returns a small result dict
        (e.g. the new token's id). Raises :class:`CommandError` if it may not be run."""
        if not isinstance(cmd, dict):
            raise CommandError("That was not a tabletop command.")
        op = cmd.get("op")
        handler = getattr(self, f"_op_{op}", None) if isinstance(op, str) and op.isidentifier() else None
        if handler is None:
            raise CommandError("Unknown tabletop command.")
        with self._lock:
            scene_id = cmd.get("scene") or ""
            is_dm = actor == DM
            if op in self.PLAYER_OPS:
                if not is_dm and scene_id != self.shown:
                    raise CommandError("That map isn't being shown any more.")
            elif not is_dm:
                raise CommandError("Only the DM can do that.")
            if is_dm and op not in self.NO_UNDO:
                self._remember(scene_id, op)
            result = handler(cmd, actor, actor_name) or {}
        self._changed(result.get("scene", scene_id) or None)
        return result

    PLAYER_OPS = {"token_move", "draw_add", "draw_delete"}
    NO_UNDO = {"scene_show"}

    def _scene_or_fail(self, cmd: dict) -> dict:
        scene = self.scenes.get(cmd.get("scene") or "")
        if scene is None:
            raise CommandError("That map no longer exists.")
        return scene

    @staticmethod
    def _token_or_fail(scene: dict, token_id) -> dict:
        for t in scene["tokens"]:
            if t["id"] == token_id:
                return t
        raise CommandError("That token is gone.")

    # scenes
    def _op_scene_new(self, cmd, actor, actor_name):
        s = cmd.get("scene_data") or {}
        scene = new_scene(s.get("name", "Scene"), s.get("map", ""), int(_num(s.get("w"), 0, 0, 20000)),
                          int(_num(s.get("h"), 0, 0, 20000)), _num(s.get("cell"), 70, 8, 1000),
                          s.get("grid", "square"))
        self.scenes[scene["id"]] = scene
        self.order.append(scene["id"])
        self._undo[-1] = (scene["id"], None, [i for i in self.order if i != scene["id"]], self.shown)
        return {"scene": scene["id"]}

    def _op_scene_update(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        fields = cmd.get("fields") or {}
        for k, v in fields.items():
            if k == "name":
                scene["name"] = _text(v) or scene["name"]
            elif k == "bg":
                scene["bg"] = _color(v, scene["bg"])
            elif k in ("players_move_all", "players_draw"):
                scene[k] = bool(v)
            elif k in ("w", "h") and not scene["map"]:
                scene[k] = int(_num(v, scene[k], 100, 20000))
            elif k == "fog_on":
                scene["fog"]["on"] = bool(v)
            elif k == "los":
                scene["los"] = bool(v)
        grid = cmd.get("grid") or {}
        g = scene["grid"]
        for k, v in grid.items():
            if k == "type" and v in GRID_TYPES:
                g["type"] = v
            elif k == "cell":
                g["cell"] = _num(v, g["cell"], 8, 1000)
            elif k in ("ox", "oy"):
                g[k] = _num(v, g[k], -5000, 5000)
            elif k == "color":
                g["color"] = _color(v, g["color"])
            elif k == "opacity":
                g["opacity"] = _num(v, g["opacity"], 0, 1)
            elif k == "feet":
                g["feet"] = _num(v, g["feet"], 0.5, 5280)

    def _op_scene_delete(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        del self.scenes[scene["id"]]
        self.order.remove(scene["id"])
        if self.shown == scene["id"]:
            self.shown = ""

    def _op_scene_rename(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        scene["name"] = _text(cmd.get("name")) or scene["name"]

    def _op_scene_show(self, cmd, actor, actor_name):
        scene_id = cmd.get("scene") or ""
        self.shown = scene_id if scene_id in self.scenes else ""

    def _op_scene_duplicate(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        copy_ = copy.deepcopy(scene)
        copy_["id"] = new_id()
        copy_["name"] = _text(f"{scene['name']} (copy)")
        for t in copy_["tokens"]:
            t["id"] = new_id()
            t["entry"] = ""             # one token per initiative entry: the copy starts unlinked
        self.scenes[copy_["id"]] = copy_
        self.order.insert(self.order.index(scene["id"]) + 1, copy_["id"])
        return {"scene": copy_["id"]}

    # tokens
    def _op_token_add(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        if len(scene["tokens"]) >= MAX_TOKENS:
            raise CommandError(f"A map holds at most {MAX_TOKENS} tokens.")
        data = cmd.get("token") or {}
        token = new_token(data.get("name", "Token"), _num(data.get("x")), _num(data.get("y")))
        token.update(_clean_token_fields(data))
        scene["tokens"].append(token)
        return {"token": token["id"]}

    def _op_token_update(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        token = self._token_or_fail(scene, cmd.get("id"))
        token.update(_clean_token_fields(cmd.get("fields") or {}))

    def _op_token_delete(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        token = self._token_or_fail(scene, cmd.get("id"))
        scene["tokens"].remove(token)

    def _op_token_front(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        token = self._token_or_fail(scene, cmd.get("id"))
        scene["tokens"].remove(token)
        scene["tokens"].append(token)

    def _op_token_condition(self, cmd, actor, actor_name):
        """Turn one condition on or off on a token."""
        scene = self._scene_or_fail(cmd)
        token = self._token_or_fail(scene, cmd.get("id"))
        name = _text(cmd.get("name"), 40)
        if not name:
            return
        conditions = list(token.get("conditions") or [])
        if name in conditions:
            conditions.remove(name)
        elif len(conditions) < 20:
            conditions.append(name)
        token["conditions"] = conditions

    def _op_token_move(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        token = self._token_or_fail(scene, cmd.get("id"))
        if actor != DM:
            if token.get("hidden"):
                raise CommandError("That token is gone.")
            if token.get("owner") != actor and not scene.get("players_move_all"):
                raise CommandError("That token isn't yours to move.")
        token["x"] = _num(cmd.get("x"), token["x"], -2000, scene["w"] + 2000)
        token["y"] = _num(cmd.get("y"), token["y"], -2000, scene["h"] + 2000)

    # drawings
    def _op_draw_add(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        if actor != DM and not scene.get("players_draw"):
            raise CommandError("The DM has turned drawing off on this map.")
        drawing = clean_drawing(cmd.get("drawing") or {}, author=actor)
        if drawing is None:
            raise CommandError("That drawing couldn't be read.")
        if actor != DM:
            drawing["private"] = False
        if len(scene["drawings"]) >= MAX_DRAWINGS:
            scene["drawings"].pop(0)
        if any(d["id"] == drawing["id"] for d in scene["drawings"]):
            drawing["id"] = new_id()
        scene["drawings"].append(drawing)
        return {"drawing": drawing["id"]}

    def _op_draw_delete(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        ids = cmd.get("ids") if isinstance(cmd.get("ids"), list) else [cmd.get("id")]
        keep = []
        for d in scene["drawings"]:
            if d["id"] in ids and (actor == DM or d.get("author") == actor):
                continue
            keep.append(d)
        scene["drawings"] = keep

    def _op_draw_clear(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        scene["drawings"] = []

    # walls and doors
    def _op_wall_add(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        raw = cmd.get("walls") if isinstance(cmd.get("walls"), list) else [cmd.get("wall")]
        walls = [w for w in (clean_wall(w) for w in raw[:MAX_WALLS]) if w is not None]
        if not walls:
            raise CommandError("That wall couldn't be read.")
        if len(scene["walls"]) + len(walls) > MAX_WALLS:
            raise CommandError(f"A map holds at most {MAX_WALLS} walls.")
        taken = {w["id"] for w in scene["walls"]}
        for w in walls:
            if w["id"] in taken:
                w["id"] = new_id()
            taken.add(w["id"])
        scene["walls"].extend(walls)
        return {"walls": [w["id"] for w in walls]}

    def _op_wall_update(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        wall = next((w for w in scene["walls"] if w["id"] == cmd.get("id")), None)
        if wall is None:
            raise CommandError("That wall is gone.")
        fields = cmd.get("fields") or {}
        if "door" in fields:
            wall["door"] = bool(fields["door"])
        if "open" in fields:
            wall["open"] = bool(fields["open"])
        if not wall["door"]:
            wall["open"] = False

    def _op_wall_delete(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        ids = cmd.get("ids") if isinstance(cmd.get("ids"), list) else [cmd.get("id")]
        scene["walls"] = [w for w in scene["walls"] if w["id"] not in ids]

    def _op_wall_clear(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        scene["walls"] = []

    # fog
    def _op_fog(self, cmd, actor, actor_name):
        scene = self._scene_or_fail(cmd)
        op = clean_fog_op(cmd.get("fog_op") or {})
        if op is None:
            raise CommandError("That fog change couldn't be read.")
        ops = scene["fog"]["ops"]
        ops.append(op)
        if len(ops) > MAX_FOG_OPS:
            del ops[: len(ops) - MAX_FOG_OPS]
        scene["fog"]["on"] = True

    def _op_fog_reset(self, cmd, actor, actor_name):
        """``hide``: cover the whole map again; ``clear``: reveal it all (fog stays on)."""
        scene = self._scene_or_fail(cmd)
        if cmd.get("mode") == "clear":
            scene["fog"]["ops"] = [{"mode": "reveal", "shape": "rect", "pts": [-4000, -4000, scene["w"] + 4000,
                                                                                scene["h"] + 4000]}]
        else:
            scene["fog"]["ops"] = []


_tabletop: Optional[Tabletop] = None


def get_tabletop() -> Tabletop:
    global _tabletop
    if _tabletop is None:
        _tabletop = Tabletop()
    return _tabletop


# --------------------------------------------------------------------------- #
# Assets: maps and token pictures, named by their contents
# --------------------------------------------------------------------------- #

class AssetStore:
    """Pictures the tabletop uses. ``folder`` holds the DM's own; ``cache`` the ones a player was sent."""

    def __init__(self, folder: Optional[str] = None, cache: Optional[str] = None):
        self.folder = folder or user_data_path(os.path.join("tabletop", "assets"))
        self.cache = cache or user_data_path(os.path.join("tabletop", "cache"))

    def path(self, asset_id: str) -> Optional[str]:
        if not valid_asset_id(asset_id):
            return None
        for folder in (self.folder, self.cache):
            for ext in (".jpg", ".png"):
                p = os.path.join(folder, asset_id + ext)
                if os.path.exists(p):
                    return p
        return None

    def has(self, asset_id: str) -> bool:
        return self.path(asset_id) is not None

    def read(self, asset_id: str) -> Optional[bytes]:
        p = self.path(asset_id)
        if p is None:
            return None
        with open(p, "rb") as f:
            return f.read()

    @staticmethod
    def _encode(image, max_side: int) -> Tuple[bytes, str]:
        """Shrink and save a picture: PNG when it has see-through parts (token art), else JPEG."""
        from PIL import Image
        image.thumbnail((max_side, max_side), Image.LANCZOS)
        alpha = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
        buf = io.BytesIO()
        if alpha:
            image.convert("RGBA").save(buf, "PNG", optimize=True)
            return buf.getvalue(), ".png"
        image.convert("RGB").save(buf, "JPEG", quality=84, optimize=True)
        return buf.getvalue(), ".jpg"

    def _store(self, data: bytes, ext: str, folder: Optional[str] = None) -> str:
        asset_id = hashlib.sha1(data).hexdigest()[:20]
        folder = folder or self.folder
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, asset_id + ext)
        if not os.path.exists(path):
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        return asset_id

    def add_image(self, source, *, token: bool = False) -> Tuple[str, int, int]:
        """Add a picture (a path, bytes or a PIL image). Returns ``(asset id, width, height)`` after shrinking."""
        from PIL import Image, ImageOps
        if isinstance(source, Image.Image):
            image = source.copy()
        elif isinstance(source, (bytes, bytearray)):
            image = Image.open(io.BytesIO(source))
        else:
            image = Image.open(source)
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "transparency" in image.info or image.mode in ("LA", "P")
                                  else "RGB")
        if token:
            image = square_crop(image)
        data, ext = self._encode(image, TOKEN_MAX_SIDE if token else MAP_MAX_SIDE)
        w, h = image.size
        return self._store(data, ext), w, h

    def add_received(self, asset_id: str, data: bytes) -> bool:
        """Keep a picture the DM sent, if it is what it says it is (its hash) and really a picture."""
        if not valid_asset_id(asset_id) or len(data) > MAX_ASSET_BYTES:
            return False
        if hashlib.sha1(data).hexdigest()[:20] != asset_id:
            return False
        from PIL import Image
        try:
            with Image.open(io.BytesIO(data)) as im:
                fmt = im.format
                if im.size[0] * im.size[1] > MAP_MAX_SIDE * MAP_MAX_SIDE * 2:
                    return False
                im.verify()
        except Exception:
            return False
        ext = ".png" if fmt == "PNG" else ".jpg"
        self._store(data, ext, self.cache)
        return True

    def size(self, asset_id: str) -> Tuple[int, int]:
        from PIL import Image
        p = self.path(asset_id)
        if not p:
            return 0, 0
        with Image.open(p) as im:
            return im.size


def square_crop(image):
    """Cut a picture to a square for a round token. A tall picture (a creature's portrait) keeps its top
    part, where the head usually is; a wide one keeps its middle."""
    w, h = image.size
    if w == h or not w or not h:
        return image
    side = min(w, h)
    if h > w:
        top = int((h - side) * 0.2)
        return image.crop((0, top, side, top + side))
    left = (w - side) // 2
    return image.crop((left, 0, left + side, side))


_assets: Optional[AssetStore] = None


def get_assets() -> AssetStore:
    global _assets
    if _assets is None:
        _assets = AssetStore()
    return _assets


# --------------------------------------------------------------------------- #
# The token library: the user's own token pictures, in folders
# --------------------------------------------------------------------------- #

def token_folder() -> str:
    return user_data_path(os.path.join("tabletop", "tokens"))


def list_token_files(folder: Optional[str] = None) -> List[Tuple[str, str, str]]:
    """``[(group, name, path)]`` for every picture in the token folder (a sub-folder is a group)."""
    folder = folder or token_folder()
    out = []
    if not os.path.isdir(folder):
        return out
    for root, dirs, files in os.walk(folder):
        dirs.sort(key=str.lower)
        group = os.path.relpath(root, folder)
        group = "" if group == "." else group.replace(os.sep, " / ")
        for f in sorted(files, key=str.lower):
            if os.path.splitext(f)[1].lower() in IMAGE_TYPES:
                out.append((group, os.path.splitext(f)[0].replace("_", " "), os.path.join(root, f)))
    return out


def import_tokens(source: str, folder: Optional[str] = None) -> int:
    """Copy the pictures in a folder or .zip into the token library (sub-folders kept). Returns how many."""
    folder = folder or token_folder()
    os.makedirs(folder, exist_ok=True)
    count = 0
    if os.path.isdir(source):
        base = os.path.basename(os.path.normpath(source))
        for root, _dirs, files in os.walk(source):
            for f in files:
                if os.path.splitext(f)[1].lower() not in IMAGE_TYPES:
                    continue
                rel = os.path.relpath(os.path.join(root, f), source)
                target = os.path.join(folder, base, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(os.path.join(root, f), target)
                count += 1
        return count
    base = os.path.splitext(os.path.basename(source))[0]
    with zipfile.ZipFile(source) as z:
        for info in z.infolist():
            name = info.filename
            if info.is_dir() or os.path.splitext(name)[1].lower() not in IMAGE_TYPES:
                continue
            parts = [p for p in re.split(r"[\\/]+", name) if p not in ("", ".", "..")]
            if not parts or info.file_size > MAX_ASSET_BYTES:
                continue
            target = os.path.join(folder, base, *parts)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def asset_ids_in(scene: Optional[dict]) -> List[str]:
    """Every picture a view of this scene needs (map first)."""
    if not scene:
        return []
    ids = [scene["map"]] if scene.get("map") else []
    for t in scene.get("tokens", []):
        if t.get("image") and t["image"] not in ids:
            ids.append(t["image"])
    return ids


def chunks(data: bytes, size: int = 900 * 1024) -> Iterable[bytes]:
    for i in range(0, len(data), size):
        yield data[i:i + size]
