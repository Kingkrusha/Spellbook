"""Changing what is already on the tabletop: moving and resizing drawings, walls, raised ground and spell areas.

Only the sums live here (no widgets), so the app's map (ui/tabletop_canvas.py) and the browser's
(lan/web/geometry.js, which has the same functions) agree, and they can be tested on their own.

A shape that has a box (a freehand line, a box, a circle, a raised area, a run of walls) gets eight handles round
that box: the corners change both sides, the edges one. A straight line or a single wall gets a handle at each end
instead. A spell area keeps its starting point and gets one more handle where it reaches to.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

import tabletop as T

HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
MIN_SIDE = 4.0                 # map pixels: a shape is never squashed flatter than this
JOIN_EPS = 0.75                # wall ends this close together are joined (they move together)

Box = Tuple[float, float, float, float]


def bounds(pts: List[float]) -> Box:
    """The smallest box round a flat point list (x0, y0, x1, y1 with x0 <= x1, y0 <= y1)."""
    xs, ys = pts[0::2], pts[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def handle_points(box: Box) -> Dict[str, Tuple[float, float]]:
    """Where each of the eight handles of a box goes."""
    x0, y0, x1, y1 = box
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    return {"nw": (x0, y0), "n": (mx, y0), "ne": (x1, y0), "e": (x1, my),
            "se": (x1, y1), "s": (mx, y1), "sw": (x0, y1), "w": (x0, my)}


def resize_box(box: Box, handle: str, x: float, y: float, *, keep_ratio: bool = False, centred: bool = False,
               min_side: float = MIN_SIDE) -> Box:
    """The box after its ``handle`` is dragged to (x, y). The opposite side stays put (or, ``centred``, the middle
    does); ``keep_ratio`` keeps its shape (a circle stays a circle). A side can't be pulled past the other one."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    moves_x = "e" in handle or "w" in handle
    moves_y = "n" in handle or "s" in handle
    sign_x = 1 if "e" in handle else -1
    sign_y = 1 if "s" in handle else -1
    # the new width and height, measured from the side that stays (or from the middle)
    if centred:
        nw = 2 * max(min_side / 2, (x - cx) * sign_x) if moves_x else w
        nh = 2 * max(min_side / 2, (y - cy) * sign_y) if moves_y else h
    else:
        nw = max(min_side, (x - (x0 if sign_x > 0 else x1)) * sign_x) if moves_x else w
        nh = max(min_side, (y - (y0 if sign_y > 0 else y1)) * sign_y) if moves_y else h
    if keep_ratio and w > 1e-9 and h > 1e-9:
        if moves_x and moves_y:
            k = max(nw / w, nh / h)
        elif moves_x:
            k = nw / w
        else:
            k = nh / h
        k = max(k, min_side / min(w, h))
        nw, nh = w * k, h * k
    # put the box back round what stays
    if centred:
        return cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2
    if moves_x:
        nx0, nx1 = (x0, x0 + nw) if sign_x > 0 else (x1 - nw, x1)
    else:                       # an edge handle with the shape kept: the other way grows round the middle
        nx0, nx1 = cx - nw / 2, cx + nw / 2
    if moves_y:
        ny0, ny1 = (y0, y0 + nh) if sign_y > 0 else (y1 - nh, y1)
    else:
        ny0, ny1 = cy - nh / 2, cy + nh / 2
    return nx0, ny0, nx1, ny1


def refit(pts: List[float], old: Box, new: Box) -> List[float]:
    """Stretch a shape's points from one box to another. A side with no width (a level line) is only moved."""
    ox0, oy0, ox1, oy1 = old
    nx0, ny0, nx1, ny1 = new
    kx = (nx1 - nx0) / (ox1 - ox0) if ox1 - ox0 > 1e-9 else 1.0
    ky = (ny1 - ny0) / (oy1 - oy0) if oy1 - oy0 > 1e-9 else 1.0
    out = []
    for i in range(0, len(pts) - 1, 2):
        out += [round(nx0 + (pts[i] - ox0) * kx, 1), round(ny0 + (pts[i + 1] - oy0) * ky, 1)]
    return out


def move(pts: List[float], dx: float, dy: float) -> List[float]:
    return [round(p + (dx if i % 2 == 0 else dy), 1) for i, p in enumerate(pts)]


def grid_step(scene: dict, dx: float, dy: float) -> Tuple[float, float]:
    """A move rounded to whole squares (on a square grid), so a room drawn on the grid stays on it."""
    grid = T.Grid.of(scene)
    if grid.kind != "square":
        return dx, dy
    return round(dx / grid.cell) * grid.cell, round(dy / grid.cell) * grid.cell


# ---- walls: a wall joined to others drags them with it

def _key(x: float, y: float) -> Tuple[int, int]:
    return round(x / JOIN_EPS), round(y / JOIN_EPS)


def wall_ends_at(walls: Iterable[dict], x: float, y: float) -> List[Tuple[str, int]]:
    """Every wall end at (x, y): (wall id, 0 for its start or 1 for its end)."""
    out = []
    for w in walls:
        p = w["pts"]
        for end in (0, 1):
            if abs(p[2 * end] - x) <= JOIN_EPS and abs(p[2 * end + 1] - y) <= JOIN_EPS:
                out.append((w["id"], end))
    return out


def connected_walls(walls: List[dict], wall_id: str) -> List[str]:
    """The wall and every wall joined to it end to end (a box or circle drawn as walls is one run)."""
    by_end: Dict[Tuple[int, int], List[str]] = {}
    pts = {}
    for w in walls:
        pts[w["id"]] = w["pts"]
        for end in (0, 1):
            by_end.setdefault(_key(w["pts"][2 * end], w["pts"][2 * end + 1]), []).append(w["id"])
    if wall_id not in pts:
        return []
    seen, todo = {wall_id}, [wall_id]
    while todo:
        p = pts[todo.pop()]
        for end in (0, 1):
            for other in by_end.get(_key(p[2 * end], p[2 * end + 1]), ()):
                if other not in seen:
                    seen.add(other)
                    todo.append(other)
    return [w["id"] for w in walls if w["id"] in seen]


def move_wall_ends(walls: List[dict], ends: List[Tuple[str, int]], x: float, y: float) -> Dict[str, List[float]]:
    """New points for the walls whose ends (from :func:`wall_ends_at`) are dragged to (x, y). A wall that would
    shrink to nothing is left out."""
    by_id = {w["id"]: w for w in walls}
    out: Dict[str, List[float]] = {}
    for wall_id, end in ends:
        w = by_id.get(wall_id)
        if w is None:
            continue
        p = list(out.get(wall_id) or w["pts"])
        p[2 * end], p[2 * end + 1] = round(x, 1), round(y, 1)
        out[wall_id] = p
    return {k: p for k, p in out.items() if abs(p[2] - p[0]) >= 0.5 or abs(p[3] - p[1]) >= 0.5}


# ---- spell areas: one handle where the area reaches to

def _pitch_scale(area: dict) -> float:
    c = math.cos(math.radians(area.get("pitch") or 0.0))
    return c if c > 0.2 else 1.0


def area_handle(scene: dict, area: dict) -> Tuple[float, float]:
    """Where an area's size handle goes: the tip of a cone or line, the edge of a sphere in the way it was cast,
    the far corner of a cube."""
    ox, oy, _oz = T.area_origin(scene, area)
    ppf = 1.0 / T.feet_per_px(scene)
    shape, size = area["shape"], float(area["size"]) * ppf
    d = math.radians(area.get("dir", 0.0))
    if shape in ("cube", "square"):
        return ox + (size if math.cos(d) >= 0 else -size), oy + (size if math.sin(d) >= 0 else -size)
    if shape in ("circle", "sphere", "emanation"):
        r = size + T._token_reach_ft(scene, area) * ppf
        return ox + r * math.cos(d), oy + r * math.sin(d)
    length = size * _pitch_scale(area)
    return ox + length * math.cos(d), oy + length * math.sin(d)


def area_from_handle(scene: dict, area: dict, x: float, y: float) -> dict:
    """The size (in whole steps of the grid's feet) and direction of an area whose size handle is dragged to
    (x, y)."""
    ox, oy, _oz = T.area_origin(scene, area)
    fpp = T.feet_per_px(scene)
    feet = float(scene["grid"].get("feet", 5) or 5)
    dx, dy = x - ox, y - oy
    shape = area["shape"]
    if shape in ("cube", "square"):
        reach = max(abs(dx), abs(dy)) * fpp
    elif shape in ("circle", "sphere", "emanation"):
        reach = math.hypot(dx, dy) * fpp - T._token_reach_ft(scene, area)
    else:
        reach = math.hypot(dx, dy) * fpp / _pitch_scale(area)
    out = {"size": max(feet, round(reach / feet) * feet)}
    if dx or dy:
        out["dir"] = round(math.degrees(math.atan2(dy, dx)) % 360.0, 2)
    return out


def reshape(pts: List[float], handle: str, x: float, y: float, *, start: Optional[Box] = None,
            keep_ratio: bool = False, centred: bool = False) -> List[float]:
    """A shape's points after one of its handles is dragged to (x, y): "p0"/"p1" move a line's ends, a box
    handle stretches the whole shape."""
    if handle in ("p0", "p1"):
        out = list(pts)
        i = 0 if handle == "p0" else len(out) - 2
        out[i], out[i + 1] = round(x, 1), round(y, 1)
        return out
    old = start or bounds(pts)
    return refit(pts, old, resize_box(old, handle, x, y, keep_ratio=keep_ratio, centred=centred))
