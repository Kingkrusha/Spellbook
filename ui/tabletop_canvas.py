"""The map itself: a canvas that draws a tabletop view and turns the mouse into tabletop commands.

Drawing is split in two so it stays light on small machines:

* the **base picture** - the visible part of the map, scaled, with the grid and the fog painted on - is made
  with Pillow as one image the size of the canvas, and only remade when the view moves, zooms or the scene
  changes (never while you drag a token);
* **tokens, drawings, pings and the ruler** are canvas items on top, so dragging and drawing are instant.

The canvas knows nothing about who may do what; it sends commands through the backend
(``tabletop_net.LocalTable`` or ``RemoteTable``) and the backend decides.
"""

from __future__ import annotations

import math
import sys
import time
import tkinter as tk
from collections import OrderedDict
from typing import Callable, List, Optional, Tuple

import tabletop as T
from ui.platform_compat import bind_right_click

ZOOM_MIN, ZOOM_MAX = 0.1, 6.0
TOOLS = ("select", "free", "line", "rect", "ellipse", "erase", "measure", "ping", "fog_reveal", "fog_hide",
         "fog_lasso_reveal", "fog_lasso_hide", "wall", "door")
DRAW_TOOLS = {"free", "line", "rect", "ellipse"}
DM_TOOLS = {"fog_reveal", "fog_hide", "fog_lasso_reveal", "fog_lasso_hide", "wall", "door"}
WALL_TOOLS = {"wall", "door"}
WALL_SNAP_PX = 12             # a wall end clicked this close (on screen) to another wall's end joins it
WALL_COLOR, DOOR_COLOR, OPEN_DOOR_COLOR = "#FF9800", "#3498DB", "#2ECC71"
FOG_SCALE_MAX = 1024          # the fog mask is kept at most this many pixels across


class _ImageCache:
    """A few decoded pictures (maps are big, so only a handful are kept)."""

    def __init__(self, size: int = 4):
        self.size = size
        self._items: "OrderedDict[str, object]" = OrderedDict()

    def get(self, key, make):
        if key in self._items:
            self._items.move_to_end(key)
            return self._items[key]
        value = make()
        self._items[key] = value
        while len(self._items) > self.size:
            self._items.popitem(last=False)
        return value

    def clear(self):
        self._items.clear()


class MapCanvas(tk.Canvas):
    """The map, its tokens and drawings, and the tools that work on them."""

    def __init__(self, parent, backend, *, on_select: Optional[Callable[[Optional[str]], None]] = None,
                 on_token_menu: Optional[Callable[[str, tk.Event], None]] = None,
                 on_token_open: Optional[Callable[[str], None]] = None,
                 on_wall_menu: Optional[Callable[[str, tk.Event], None]] = None,
                 on_status: Optional[Callable[[str], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None, bg: str = "#1E1E1E"):
        super().__init__(parent, highlightthickness=0, borderwidth=0, bg=bg, takefocus=1)
        self.backend = backend
        self.on_select = on_select
        self.on_token_menu = on_token_menu
        self.on_token_open = on_token_open
        self.on_wall_menu = on_wall_menu
        self.on_status = on_status or (lambda _t: None)
        self.on_error = on_error or (lambda _t: None)
        self.empty_bg = bg

        self.zoom = 1.0
        self.vx = self.vy = 0.0            # the map point at the canvas's top-left corner
        self.tool = "select"
        self.draw_color = "#E74C3C"
        self.draw_width = 4.0
        self.draw_private = False
        self.place: Optional[dict] = None  # a token waiting to be put down (from the library)
        self.selected: Optional[str] = None
        self.show_grid = True
        self.show_walls = True             # the DM sees the walls they drew
        self.preview_sight = False         # the DM sees the map dimmed as the players' tokens see it
        self._chain: Optional[Tuple[float, float]] = None   # the last corner of the wall being drawn

        self._scene: Optional[dict] = None
        self._scene_id = ""
        self._photo = None
        self._render_job = None
        self._maps = _ImageCache(3)
        self._token_art = _ImageCache(200)
        self._fog_cache: Tuple[object, object] = (None, None)    # (key, (mask, scale))
        self._drag: Optional[dict] = None
        self._pings: List[dict] = []
        self._ping_job = None
        self._measure: Optional[Tuple[float, float, float, float]] = None
        self._fitted_for = ""

        self.bind("<Configure>", self._on_configure, add="+")
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._motion)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<Double-Button-1>", self._double)
        self.bind("<Motion>", self._hover)
        if sys.platform != "darwin":       # middle-drag pans (on a Mac Button-2 is the right click)
            self.bind("<ButtonPress-2>", self._pan_start)
            self.bind("<B2-Motion>", self._pan_move)
            self.bind("<ButtonRelease-2>", self._pan_end)
        bind_right_click(self, self._right_click)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(seq, self._wheel, add="+")
        self.bind("<Delete>", lambda _e: self._delete_selected())
        self.bind("<BackSpace>", lambda _e: self._delete_selected())
        self.bind("<Escape>", lambda _e: self._escape())

        backend.listen(self._backend_changed)
        backend.on_ping(self._add_ping)
        self._backend_changed()

    def destroy(self):
        try:
            self.backend.unlisten(self._backend_changed)
        except Exception:
            pass
        for job in (self._render_job, self._ping_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        super().destroy()

    # ------------------------------------------------------------------ coordinates

    def to_screen(self, x: float, y: float) -> Tuple[float, float]:
        return (x - self.vx) * self.zoom, (y - self.vy) * self.zoom

    def to_map(self, sx: float, sy: float) -> Tuple[float, float]:
        return sx / self.zoom + self.vx, sy / self.zoom + self.vy

    @property
    def grid(self) -> T.Grid:
        return T.Grid.of(self._scene) if self._scene else T.Grid()

    def _on_configure(self, _e=None):
        if not self._fit_when_sized():
            self.schedule_render()

    def _fit_when_sized(self) -> bool:
        """A new map is fitted to the canvas once the canvas has its real size."""
        if self._scene and self._fitted_for != self._scene["id"] and self.winfo_width() > 60 \
                and self.winfo_height() > 60:
            self._fitted_for = self._scene["id"]
            self.fit()
            return True
        if not self._scene:
            self.schedule_render()
        return False

    def fit(self):
        """Zoom so the whole map fits, centred."""
        scene = self._scene
        w, h = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        if not scene:
            return
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, min(w / max(scene["w"], 1), h / max(scene["h"], 1)) * 0.96))
        self.vx = scene["w"] / 2 - w / 2 / self.zoom
        self.vy = scene["h"] / 2 - h / 2 / self.zoom
        self.render()

    def zoom_by(self, factor: float, sx: Optional[float] = None, sy: Optional[float] = None):
        if sx is None:
            sx, sy = self.winfo_width() / 2, self.winfo_height() / 2
        mx, my = self.to_map(sx, sy)
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * factor))
        self.vx, self.vy = mx - sx / self.zoom, my - sy / self.zoom
        self.schedule_render(10)

    def center_on(self, x: float, y: float):
        self.vx = x - self.winfo_width() / 2 / self.zoom
        self.vy = y - self.winfo_height() / 2 / self.zoom
        self.render()

    # ------------------------------------------------------------------ the backend

    def _backend_changed(self):
        view = self.backend.view()
        scene = view.get("scene")
        self._scene = scene
        new_scene = (scene or {}).get("id", "")
        if new_scene != self._scene_id:
            self._scene_id = new_scene
            self.selected = None
            self._drag = None
            if self.on_select:
                self.on_select(None)
            self._fitted_for = ""
            self._fit_when_sized()
            return
        if self.selected and not self.token(self.selected):
            self.selected = None
            if self.on_select:
                self.on_select(None)
        self.schedule_render(5)

    def token(self, token_id: Optional[str]) -> Optional[dict]:
        if not self._scene or not token_id:
            return None
        for t in self._scene["tokens"]:
            if t["id"] == token_id:
                return t
        return None

    def dispatch(self, cmd: dict) -> Optional[dict]:
        try:
            return self.backend.dispatch(cmd)
        except T.CommandError as e:
            self.on_error(str(e))
        except Exception as e:                       # never let one bad command break the page
            self.on_error(f"That couldn't be done ({e}).")
        return None

    @property
    def is_dm(self) -> bool:
        return self.backend.role == "dm"

    def can_move(self, token: dict) -> bool:
        if self.is_dm:
            return True
        return bool(token.get("mine") or (self._scene or {}).get("players_move_all"))

    # ------------------------------------------------------------------ drawing the base picture

    def schedule_render(self, delay: int = 30):
        if self._render_job is None:
            self._render_job = self.after(delay, self.render)

    def render(self):
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except tk.TclError:
                pass
            self._render_job = None
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self.delete("all")
        scene = self._scene
        W, H = self.winfo_width(), self.winfo_height()
        if scene is None or W < 4 or H < 4:
            self._draw_empty(W, H)
            return
        try:
            base = self._base_image(scene, W, H)
        except Exception as e:
            print(f"Tabletop: the map couldn't be drawn: {e}")
            base = None
        if base is not None:
            from PIL import ImageTk
            self._photo = ImageTk.PhotoImage(base)
            self.create_image(0, 0, image=self._photo, anchor="nw", tags=("base",))
        self._draw_overlay()

    def _draw_empty(self, W, H):
        text = ("No map yet. Make one with ＋ New Map." if self.is_dm
                else "The DM isn't showing a map right now.")
        self.create_text(W / 2, H / 2, text=text, fill="#A0A0A0", font=("TkDefaultFont", 13))

    def _map_image(self, asset_id: str):
        def load():
            from PIL import Image
            path = self.backend.asset_path(asset_id)
            if not path:
                return None
            with Image.open(path) as im:
                return im.convert("RGB")
        if not asset_id:
            return None
        image = self._maps.get(asset_id, load)
        if image is None:
            self._maps._items.pop(asset_id, None)      # not here yet (a player waiting for it): try again later
        return image

    def _base_image(self, scene: dict, W: int, H: int):
        from PIL import Image, ImageDraw
        z = self.zoom
        bg = scene.get("bg") or "#2B2B2B"
        out = Image.new("RGB", (W, H), self.empty_bg)
        # the scene's area
        x0, y0 = self.to_screen(0, 0)
        x1, y1 = self.to_screen(scene["w"], scene["h"])
        ImageDraw.Draw(out).rectangle([x0, y0, x1, y1], fill=bg)
        source = self._map_image(scene.get("map", ""))
        if source is not None:
            sw, sh = source.size
            # the part of the map the canvas shows, in map pixels (scaled if the stored picture is smaller)
            fx, fy = sw / max(scene["w"], 1), sh / max(scene["h"], 1)
            mx0, my0 = max(0.0, self.vx), max(0.0, self.vy)
            mx1, my1 = min(float(scene["w"]), self.vx + W / z), min(float(scene["h"]), self.vy + H / z)
            if mx1 > mx0 and my1 > my0:
                box = (int(mx0 * fx), int(my0 * fy), int(math.ceil(mx1 * fx)), int(math.ceil(my1 * fy)))
                crop = source.crop(box)
                # where that box lands on the canvas
                dx0, dy0 = self.to_screen(box[0] / fx, box[1] / fy)
                dx1, dy1 = self.to_screen(box[2] / fx, box[3] / fy)
                size = (max(1, int(round(dx1 - dx0))), max(1, int(round(dy1 - dy0))))
                resample = Image.BILINEAR if z * min(1 / fx, 1 / fy) >= 0.5 else Image.BOX
                out.paste(crop.resize(size, resample), (int(round(dx0)), int(round(dy0))))
        elif scene.get("map"):
            ImageDraw.Draw(out).text((x0 + 10, y0 + 10), "Loading the map…", fill="#DDDDDD")
        # the grid
        g = scene["grid"]
        if self.show_grid and g.get("type") != "none" and g.get("opacity", 0) > 0 and g["cell"] * z >= 6:
            out = self._paint_grid(out, scene, W, H)
        # the fog, and what the tokens can't see
        sight = self._sight(scene)
        if scene["fog"].get("on") or sight is not None:
            out = self._paint_fog(out, scene, W, H, sight)
        return out

    def _sight(self, scene: dict) -> Optional[List[dict]]:
        """What the darkness leaves visible: a player's view comes with it (when the DM has line of sight
        on); the DM gets it only as a preview, through the selected token or else the party."""
        if not self.is_dm:
            return scene.get("sight")
        if not self.preview_sight:
            return None
        eyes = [t for t in scene["tokens"] if t["id"] == self.selected and t.get("kind") != "prop"]
        return T.sight_for(scene, eyes or T.eyes_for(scene, ""))

    def _paint_grid(self, out, scene, W, H):
        from PIL import Image, ImageDraw
        g = scene["grid"]
        grid = T.Grid.of(scene)
        mx0, my0 = self.to_map(0, 0)
        mx1, my1 = self.to_map(W, H)
        mx0, my0 = max(mx0, 0), max(my0, 0)
        mx1, my1 = min(mx1, scene["w"]), min(my1, scene["h"])
        if mx1 <= mx0 or my1 <= my0:
            return out
        color = g.get("color", "#000000").lstrip("#")
        rgb = tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
        alpha = int(255 * max(0.0, min(1.0, g.get("opacity", 0.35))))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        width = 2 if self.zoom >= 1.5 else 1
        clip = (mx0, my0, mx1, my1)
        for line in grid.lines_in(*clip):
            pts = []
            for i in range(0, len(line), 2):
                x = min(max(line[i], clip[0]), clip[2]) if grid.kind == "square" else line[i]
                y = min(max(line[i + 1], clip[1]), clip[3]) if grid.kind == "square" else line[i + 1]
                pts.append(self.to_screen(x, y))
            draw.line(pts, fill=rgb + (alpha,), width=width)
        if grid.kind != "square":
            # hexes are drawn whole: trim what spills past the map's edge
            sx0, sy0 = self.to_screen(0, 0)
            sx1, sy1 = self.to_screen(scene["w"], scene["h"])
            mask = Image.new("L", (W, H), 0)
            ImageDraw.Draw(mask).rectangle([sx0, sy0, sx1, sy1], fill=255)
            layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (W, H), 0), mask))
        base = out.convert("RGBA")
        base.alpha_composite(layer)
        return base.convert("RGB")

    def _fog_mask(self, scene, sight: Optional[List[dict]] = None):
        """The fog (and the darkness outside the tokens' sight) over the whole map at a reduced size:
        255 = hidden, 0 = revealed."""
        from PIL import Image, ImageChops, ImageDraw
        ops = scene["fog"]["ops"]
        fog_on = bool(scene["fog"].get("on"))
        sight_key = None if sight is None else tuple(
            (s["x"], s["y"], s["r"], len(s["pts"]), hash(tuple(s["pts"]))) for s in sight)
        key = (scene["id"], scene["w"], scene["h"], fog_on, len(ops), repr(ops[-1]) if ops else "", sight_key)
        if self._fog_cache[0] == key:
            return self._fog_cache[1]
        scale = min(1.0, FOG_SCALE_MAX / max(scene["w"], scene["h"], 1))
        size = (max(1, int(scene["w"] * scale)), max(1, int(scene["h"] * scale)))
        mask = Image.new("L", size, 255 if fog_on else 0)
        draw = ImageDraw.Draw(mask)
        for op in (ops if fog_on else []):
            fill = 0 if op["mode"] == "reveal" else 255
            pts = [p * scale for p in op["pts"]]
            if op["shape"] == "rect":
                draw.rectangle(_box(pts), fill=fill)
            elif op["shape"] == "ellipse":
                draw.ellipse(_box(pts), fill=fill)
            else:
                draw.polygon(pts, fill=fill)
        if sight is not None:
            dark = Image.new("L", size, 255)
            for s in sight:
                seen = Image.new("L", size, 0)
                if len(s["pts"]) >= 6:
                    ImageDraw.Draw(seen).polygon([p * scale for p in s["pts"]], fill=255)
                if s.get("r"):
                    reach = Image.new("L", size, 0)
                    x, y, r = s["x"] * scale, s["y"] * scale, s["r"] * scale
                    ImageDraw.Draw(reach).ellipse((x - r, y - r, x + r, y + r), fill=255)
                    seen = ImageChops.darker(seen, reach)
                dark = ImageChops.darker(dark, ImageChops.invert(seen))
            mask = ImageChops.lighter(mask, dark)
        result = (mask, scale)
        self._fog_cache = (key, result)
        return result

    def _paint_fog(self, out, scene, W, H, sight: Optional[List[dict]] = None):
        from PIL import Image
        mask, scale = self._fog_mask(scene, sight)
        z = self.zoom
        # the fog mask's part under the canvas, grown by a pixel so the edges line up
        fx0, fy0 = self.vx * scale, self.vy * scale
        fx1, fy1 = (self.vx + W / z) * scale, (self.vy + H / z) * scale
        full = Image.new("L", (W, H), 255)
        mw, mh = mask.size
        cx0, cy0 = max(0, math.floor(fx0)), max(0, math.floor(fy0))
        cx1, cy1 = min(mw, math.ceil(fx1)), min(mh, math.ceil(fy1))
        if cx1 > cx0 and cy1 > cy0:
            part = mask.crop((cx0, cy0, cx1, cy1))
            dx0, dy0 = (cx0 / scale - self.vx) * z, (cy0 / scale - self.vy) * z
            dx1, dy1 = (cx1 / scale - self.vx) * z, (cy1 / scale - self.vy) * z
            size = (max(1, int(round(dx1 - dx0))), max(1, int(round(dy1 - dy0))))
            full.paste(part.resize(size, Image.BILINEAR), (int(round(dx0)), int(round(dy0))))
        # outside the map counts as hidden for players; the DM sees through the fog dimly
        if self.is_dm:
            full = full.point(lambda v: v * 150 // 255)
        fog = Image.new("RGB", (W, H), (12, 12, 16))
        return Image.composite(fog, out, full)

    # ------------------------------------------------------------------ tokens, drawings and the rest

    def _draw_overlay(self):
        self.delete("overlay")
        scene = self._scene
        if scene is None:
            return
        for d in scene["drawings"]:
            self._draw_drawing(d)
        if self.is_dm and (self.show_walls or self.tool in WALL_TOOLS):
            self._draw_walls(scene)
        for t in scene["tokens"]:
            self._draw_token(t)
        self._draw_pings()
        if self._measure:
            self._draw_measure(*self._measure)

    def _draw_drawing(self, d: dict, tags: Tuple[str, ...] = ()):
        pts = []
        for i in range(0, len(d["pts"]) - 1, 2):
            pts.extend(self.to_screen(d["pts"][i], d["pts"][i + 1]))
        width = max(1.0, d.get("width", 4) * self.zoom)
        color = d.get("color", "#E74C3C")
        tags = ("overlay", "drawing", f"d:{d.get('id', '')}") + tags
        dash = (6, 4) if d.get("private") else None
        if d["kind"] in ("free", "line"):
            if len(pts) >= 4:
                self.create_line(*pts, fill=color, width=width, capstyle="round", joinstyle="round",
                                 smooth=d["kind"] == "free", tags=tags, dash=dash)
        elif d["kind"] == "rect":
            self.create_rectangle(*_box(pts[:4]), outline=color, width=width, tags=tags, dash=dash)
        elif d["kind"] == "ellipse":
            self.create_oval(*_box(pts[:4]), outline=color, width=width, tags=tags, dash=dash)

    def _draw_walls(self, scene: dict):
        width = max(2.0, min(5.0, 3 * self.zoom))
        for w in scene.get("walls") or []:
            a, b = self.to_screen(*w["pts"][:2]), self.to_screen(*w["pts"][2:4])
            tags = ("overlay", "wall", f"w:{w['id']}")
            if w.get("door"):
                is_open = bool(w.get("open"))
                self.create_line(*a, *b, fill=OPEN_DOOR_COLOR if is_open else DOOR_COLOR, width=width * 2,
                                 dash=(6, 4) if is_open else None, capstyle="butt", tags=tags)
            else:
                self.create_line(*a, *b, fill=WALL_COLOR, width=width, capstyle="round", tags=tags)

    def wall_at(self, sx: float, sy: float) -> Optional[str]:
        """The id of the wall drawn under a canvas point, if any."""
        for item in reversed(self.find_overlapping(sx - 5, sy - 5, sx + 5, sy + 5)):
            for tag in self.gettags(item):
                if tag.startswith("w:"):
                    return tag[2:]
        return None

    def _wall_snap(self, sx: float, sy: float) -> Tuple[float, float]:
        """Where a wall corner clicked here goes: onto a nearby wall end, else a nearby grid corner."""
        mx, my = self.to_map(sx, sy)
        reach = WALL_SNAP_PX / self.zoom
        best, best_d = None, reach
        for w in (self._scene or {}).get("walls") or []:
            for px, py in ((w["pts"][0], w["pts"][1]), (w["pts"][2], w["pts"][3])):
                d = math.hypot(px - mx, py - my)
                if d <= best_d:
                    best, best_d = (px, py), d
        if self._chain is not None and math.hypot(self._chain[0] - mx, self._chain[1] - my) <= best_d:
            best = None
        if best is not None:
            return best
        grid = self.grid
        if grid.kind == "square":
            gx = grid.ox + round((mx - grid.ox) / grid.cell) * grid.cell
            gy = grid.oy + round((my - grid.oy) / grid.cell) * grid.cell
            if math.hypot(gx - mx, gy - my) <= reach:
                return gx, gy
        return round(mx, 1), round(my, 1)

    def _wall_click(self, e):
        p = self._wall_snap(e.x, e.y)
        if self._chain is None:
            self._chain = p
            self.on_status("Click to put down the next corner. Double-click, right-click or Esc to stop.")
        elif math.hypot(p[0] - self._chain[0], p[1] - self._chain[1]) > 1:
            door = self.tool == "door"
            self.dispatch({"op": "wall_add", "wall": {"pts": [*self._chain, *p], "door": door}})
            self._chain = None if door else p
            if door:
                self.on_status("")
        self._draw_wall_preview(e.x, e.y)

    def _draw_wall_preview(self, sx: float, sy: float):
        self.delete("preview")
        if self._chain is None:
            return
        a = self.to_screen(*self._chain)
        b = self.to_screen(*self._wall_snap(sx, sy))
        color = DOOR_COLOR if self.tool == "door" else WALL_COLOR
        self.create_line(*a, *b, fill=color, width=3, dash=(6, 4), tags=("overlay", "preview"))
        self.create_oval(a[0] - 4, a[1] - 4, a[0] + 4, a[1] + 4, fill=color, outline="", tags=("overlay", "preview"))

    def end_wall(self):
        """Stop drawing the current run of walls."""
        if self._chain is not None:
            self._chain = None
            self.delete("preview")
            self.on_status("")

    def _token_photo(self, asset_id: str, diameter: int):
        """A token's picture cut to a circle, at the size it's drawn."""
        def make():
            from PIL import Image, ImageDraw, ImageTk
            path = self.backend.asset_path(asset_id)
            if not path:
                return None
            with Image.open(path) as im:
                im = im.convert("RGBA")
            side = min(im.size)
            left, top = (im.width - side) // 2, (im.height - side) // 2
            im = im.crop((left, top, left + side, top + side)).resize((diameter, diameter), Image.LANCZOS)
            mask = Image.new("L", (diameter * 3, diameter * 3), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, diameter * 3 - 1, diameter * 3 - 1), fill=255)
            mask = mask.resize((diameter, diameter), Image.LANCZOS)
            alpha = Image.composite(im.getchannel("A"), Image.new("L", im.size, 0), mask)
            im.putalpha(alpha)
            return ImageTk.PhotoImage(im)
        if not asset_id or diameter < 4:
            return None
        photo = self._token_art.get((asset_id, diameter), make)
        if photo is None:
            self._token_art._items.pop((asset_id, diameter), None)
        return photo

    def _draw_token(self, t: dict, tags_extra: Tuple[str, ...] = ()):
        grid = self.grid
        cx, cy, r = T.token_box(t, grid)
        sx, sy = self.to_screen(cx, cy)
        sr = max(5.0, r * self.zoom * 0.92)
        tags = ("overlay", "token", f"t:{t['id']}") + tags_extra
        hidden = t.get("hidden")
        photo = self._token_photo(t.get("image", ""), int(sr * 2)) if t.get("image") else None
        # whose turn it is in the initiative tracker: a bright halo outside the condition ring
        if t.get("turn"):
            halo = sr + max(10.0, sr * 0.45)
            self.create_oval(sx - halo, sy - halo, sx + halo, sy + halo, outline="#FFD54F",
                             width=max(3.0, sr * 0.12), tags=tags + ("turn",))
        # body
        if photo is not None:
            # (a picture with see-through parts shows the token's colour behind it)
            self.create_oval(sx - sr, sy - sr, sx + sr, sy + sr, fill=t.get("color", "#111111"), outline="",
                             tags=tags)
            self.create_image(sx, sy, image=photo, tags=tags)
        else:
            self.create_oval(sx - sr, sy - sr, sx + sr, sy + sr, fill=t.get("color", "#C0392B"),
                             outline="#111111", width=1, tags=tags, stipple="gray50" if hidden else "")
            if sr >= 6:
                letter = token_letter(t.get("name", ""))
                font = ("TkDefaultFont", -max(8, int(sr * 1.1)), "bold")    # negative: pixels, not points
                self.create_text(sx + 1, sy + 1, text=letter, fill="#000000", font=font, tags=tags)
                self.create_text(sx, sy, text=letter, fill="white", font=font, tags=tags)
        # the outline: the token's colour, gold when selected
        selected = t["id"] == self.selected
        self.create_oval(sx - sr, sy - sr, sx + sr, sy + sr, outline="#F1C40F" if selected else t.get("color"),
                         width=3 if selected else 2, dash=(4, 3) if hidden else None, tags=tags)
        # the condition ring
        conditions = list(t.get("conditions") or [])
        state = t.get("state")
        if state == "bloodied" and "Bloodied" not in conditions:
            conditions.append("Bloodied")
        hp, hp_max = t.get("hp"), t.get("hp_max")
        if hp is not None and hp_max and hp * 2 <= hp_max and hp > 0 and "Bloodied" not in conditions:
            conditions.append("Bloodied")
        if conditions:
            ring = sr + max(3.0, sr * 0.14)
            width = max(3.0, sr * 0.16)
            span = 360.0 / len(conditions)
            for i, name in enumerate(conditions):
                self.create_arc(sx - ring, sy - ring, sx + ring, sy + ring, start=90 - (i + 1) * span + 2,
                                extent=max(1.0, span - 4) if len(conditions) > 1 else 359.9, style="arc",
                                outline=T.condition_color(name), width=width, tags=tags)
        if state == "down" or (hp is not None and hp_max and hp <= 0):
            k = sr * 0.6
            self.create_line(sx - k, sy - k, sx + k, sy + k, fill="#E74C3C", width=max(2, sr * 0.15), tags=tags)
            self.create_line(sx - k, sy + k, sx + k, sy - k, fill="#E74C3C", width=max(2, sr * 0.15), tags=tags)
        # hit points (the DM, and a player for their own tokens)
        if hp is not None and hp_max and sr >= 10:
            frac = max(0.0, min(1.0, hp / hp_max))
            bw, bh = sr * 1.6, max(3, sr * 0.14)
            bx, by = sx - bw / 2, sy + sr + (max(3.0, sr * 0.14) * 2 if conditions else 3)
            self.create_rectangle(bx, by, bx + bw, by + bh, fill="#222222", outline="", tags=tags)
            color = "#27AE60" if frac > 0.5 else ("#F39C12" if frac > 0.25 else "#E74C3C")
            self.create_rectangle(bx, by, bx + bw * frac, by + bh, fill=color, outline="", tags=tags)
        if t.get("show_name", True) and sr >= 8:
            ny = sy + sr + (14 if hp is not None and hp_max else 8) + (max(3.0, sr * 0.14) if conditions else 0)
            label = t["name"] + ("  (hidden)" if hidden else "")
            self.create_text(sx + 1, ny + 1, text=label, fill="#000000", font=("TkDefaultFont", 9, "bold"),
                             tags=tags + ("label",))
            self.create_text(sx, ny, text=label, fill="#FFFFFF", font=("TkDefaultFont", 9, "bold"),
                             tags=tags + ("label",))

    def _token_at(self, sx: float, sy: float) -> Optional[dict]:
        """The top-most token under a canvas point."""
        if not self._scene:
            return None
        mx, my = self.to_map(sx, sy)
        grid = self.grid
        for t in reversed(self._scene["tokens"]):
            cx, cy, r = T.token_box(t, grid)
            if (mx - cx) ** 2 + (my - cy) ** 2 <= r * r:
                return t
        return None

    # ------------------------------------------------------------------ pings and the ruler

    def _add_ping(self, ping: dict):
        if not self._scene or ping.get("scene") != self._scene["id"]:
            return
        ping = dict(ping)
        ping["t0"] = time.time()
        self._pings.append(ping)
        if self._ping_job is None:
            self._animate_pings()

    def _animate_pings(self):
        self._ping_job = None
        now = time.time()
        self._pings = [p for p in self._pings if now - p["t0"] < 2.2]
        self._draw_pings()
        if self._pings:
            self._ping_job = self.after(40, self._animate_pings)

    def _draw_pings(self):
        self.delete("ping")
        now = time.time()
        for p in self._pings:
            age = now - p["t0"]
            sx, sy = self.to_screen(p["x"], p["y"])
            for k in range(2):
                phase = (age * 1.4 + k * 0.5) % 1.0
                r = 8 + phase * 46
                self.create_oval(sx - r, sy - r, sx + r, sy + r, outline=p.get("color", "#F1C40F"),
                                 width=max(1, int(4 * (1 - phase))) + 1, tags=("overlay", "ping"))
            self.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, fill=p.get("color", "#F1C40F"), outline="white",
                             tags=("overlay", "ping"))
            if p.get("name"):
                self.create_text(sx, sy - 22, text=p["name"], fill="white", font=("TkDefaultFont", 10, "bold"),
                                 tags=("overlay", "ping"))

    def _draw_measure(self, x0, y0, x1, y1):
        self.delete("measure")
        grid = self.grid
        g = (self._scene or {}).get("grid", {})
        cells = grid.cells_between((x0, y0), (x1, y1))
        feet = cells * float(g.get("feet", 5))
        a, b = self.to_screen(x0, y0), self.to_screen(x1, y1)
        self.create_line(*a, *b, fill="#F1C40F", width=3, arrow="last", tags=("overlay", "measure"))
        text = (f"{feet:g} ft" if grid.kind != "none" else f"{feet:.0f} ft") + \
               (f"  ({cells:g} squares)" if grid.kind == "square" else (f"  ({cells:g} hexes)"
                                                                         if grid.kind != "none" else ""))
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 16
        self.create_rectangle(mx - 70, my - 11, mx + 70, my + 11, fill="#1C1C1C", outline="#F1C40F",
                              tags=("overlay", "measure"))
        self.create_text(mx, my, text=text, fill="white", font=("TkDefaultFont", 10, "bold"),
                         tags=("overlay", "measure"))

    # ------------------------------------------------------------------ mouse

    def set_tool(self, tool: str):
        self.end_wall()
        was_walls = self.tool in WALL_TOOLS
        self.tool = tool if tool in TOOLS else "select"
        self.place = None
        if self._scene is not None and was_walls != (self.tool in WALL_TOOLS) and not self.show_walls:
            self._draw_overlay()
        self.configure(cursor={"select": "", "measure": "crosshair", "ping": "hand2", "erase": "X_cursor"}.get(
            self.tool, "pencil" if self.tool in DRAW_TOOLS else "crosshair"))

    def start_placing(self, token: dict):
        """The next click puts this token down (a library picture or a monster)."""
        self.place = token
        self.configure(cursor="plus")
        self.on_status(f"Click the map to place {token.get('name', 'the token')}. Esc cancels.")

    def _escape(self):
        self.end_wall()
        self.place = None
        self._drag = None
        self._measure = None
        self.set_tool(self.tool)
        self.delete("preview")
        self.delete("measure")
        self.on_status("")

    def _press(self, e):
        self.focus_set()
        if not self._scene:
            return
        mx, my = self.to_map(e.x, e.y)
        if _alt_held(e.state):                           # Alt-click pings, whatever the tool
            self.backend.ping(mx, my)
            return
        if self.place is not None:
            token = dict(self.place)
            size = token.get("size", 1.0)
            token["x"], token["y"] = self.grid.snap(mx, my, size)
            result = self.dispatch({"op": "token_add", "token": token})
            if result and not (e.state & 0x0001):       # Shift keeps placing copies
                self.place = None
                self.set_tool(self.tool)
                self.on_status("")
                self.select(result.get("token"))
            return
        tool = self.tool
        if tool == "ping":
            self.backend.ping(mx, my)
            return
        if tool == "select":
            t = self._token_at(e.x, e.y)
            if t is not None:
                self.select(t["id"])
                if self.can_move(t):
                    self._drag = {"kind": "token", "id": t["id"], "sx": e.x, "sy": e.y, "moved": False,
                                  "ox": t["x"], "oy": t["y"]}
                    self.tag_raise(f"t:{t['id']}")
                return
            self.select(None)
            self._pan_start(e)
            return
        if tool == "measure":
            self._drag = {"kind": "measure", "x0": mx, "y0": my}
            return
        if tool == "erase":
            self._erase_at(e.x, e.y)
            self._drag = {"kind": "erase"}
            return
        if tool in DRAW_TOOLS:
            self._drag = {"kind": "draw", "pts": [mx, my], "last": (e.x, e.y)}
            return
        if tool in WALL_TOOLS and self.is_dm:
            self._wall_click(e)
            return
        if tool in DM_TOOLS and self.is_dm:
            self._drag = {"kind": "fog", "pts": [mx, my], "last": (e.x, e.y)}

    def _motion(self, e):
        d = self._drag
        if d is None:
            return
        kind = d["kind"]
        if kind == "pan":
            self._pan_move(e)
            return
        mx, my = self.to_map(e.x, e.y)
        if kind == "token":
            dx, dy = e.x - d["sx"], e.y - d["sy"]
            if abs(dx) + abs(dy) > 2:
                d["moved"] = True
            self.move(f"t:{d['id']}", dx, dy)
            d["sx"], d["sy"] = e.x, e.y
            t = self.token(d["id"])
            if t is not None:
                cells = self.grid.cells_between((d["ox"], d["oy"]), (mx, my))
                feet = cells * float(self._scene["grid"].get("feet", 5))
                self.on_status(f"Moving {t['name']}: {feet:g} ft")
        elif kind == "measure":
            self._measure = (d["x0"], d["y0"], mx, my)
            self._draw_measure(*self._measure)
        elif kind == "erase":
            self._erase_at(e.x, e.y)
        elif kind in ("draw", "fog"):
            lx, ly = d["last"]
            freehand = self.tool in ("free", "fog_lasso_reveal", "fog_lasso_hide")
            if freehand:
                if (e.x - lx) ** 2 + (e.y - ly) ** 2 < 9 or len(d["pts"]) >= T.MAX_POINTS * 2:
                    return
                d["pts"].extend([mx, my])
                d["last"] = (e.x, e.y)
            else:
                d["pts"] = d["pts"][:2] + [mx, my]
            self._draw_preview(d)

    def _release(self, e):
        d, self._drag = self._drag, None
        if d is None:
            return
        kind = d["kind"]
        if kind == "pan":
            self._pan_end(e)
        elif kind == "token":
            t = self.token(d["id"])
            if t is None:
                return
            if not d["moved"]:
                self.on_status("")
                self._draw_overlay()
                return
            nx, ny = self._dragged_centre(d)
            nx, ny = self.grid.snap(nx, ny, t.get("size", 1.0))
            self.on_status("")
            self.dispatch({"op": "token_move", "id": t["id"], "x": nx, "y": ny})
            self._draw_overlay()
        elif kind == "measure":
            self._measure = None
            self.delete("measure")
        elif kind == "draw":
            self.delete("preview")
            pts = d["pts"]
            if len(pts) >= 4 and (abs(pts[-2] - pts[0]) + abs(pts[-1] - pts[1]) > 1 or len(pts) > 4):
                self.dispatch({"op": "draw_add", "drawing": {
                    "id": T.new_id(), "kind": self.tool, "pts": [round(p, 1) for p in pts],
                    "color": self.draw_color, "width": self.draw_width,
                    "private": bool(self.draw_private and self.is_dm)}})
        elif kind == "fog":
            self.delete("preview")
            pts = d["pts"]
            mode = "reveal" if self.tool in ("fog_reveal", "fog_lasso_reveal") else "hide"
            shape = "poly" if self.tool.startswith("fog_lasso") else "rect"
            if (shape == "rect" and len(pts) == 4 and abs(pts[2] - pts[0]) > 2 and abs(pts[3] - pts[1]) > 2) or \
                    (shape == "poly" and len(pts) >= 6):
                self.dispatch({"op": "fog", "fog_op": {"mode": mode, "shape": shape,
                                                       "pts": [round(p, 1) for p in pts]}})

    def _dragged_centre(self, d: dict) -> Tuple[float, float]:
        """Where the dragged token's centre is now: the first item's moved position, back in map pixels."""
        t = self.token(d["id"])
        items = self.find_withtag(f"t:{d['id']}")
        if t is None or not items:
            return d["ox"], d["oy"]
        x0, y0, x1, y1 = self.coords(items[0])[:4]
        return self.to_map((x0 + x1) / 2, (y0 + y1) / 2)

    def _draw_preview(self, d: dict):
        self.delete("preview")
        pts = d["pts"]
        if len(pts) < 4:
            return
        if d["kind"] == "fog":
            color = "#5DADE2" if self.tool in ("fog_reveal", "fog_lasso_reveal") else "#E74C3C"
            screen = []
            for i in range(0, len(pts) - 1, 2):
                screen.extend(self.to_screen(pts[i], pts[i + 1]))
            if self.tool.startswith("fog_lasso"):
                if len(screen) >= 6:
                    self.create_polygon(*screen, outline=color, fill="", width=2, dash=(6, 4),
                                        tags=("overlay", "preview"))
            else:
                self.create_rectangle(*_box(screen[:4]), outline=color, width=2, dash=(6, 4),
                                      tags=("overlay", "preview"))
            return
        self._draw_drawing({"kind": self.tool, "pts": pts, "color": self.draw_color, "width": self.draw_width,
                            "private": self.draw_private and self.is_dm}, tags=("preview",))

    def _erase_at(self, sx, sy):
        for item in reversed(self.find_overlapping(sx - 6, sy - 6, sx + 6, sy + 6)):
            for tag in self.gettags(item):
                if tag.startswith("d:"):
                    drawing_id = tag[2:]
                    self.delete(f"d:{drawing_id}")
                    self.dispatch({"op": "draw_delete", "id": drawing_id})
                    return
                if tag.startswith("w:") and self.is_dm:
                    self.delete(tag)
                    self.dispatch({"op": "wall_delete", "id": tag[2:]})
                    return

    def _double(self, e):
        if self.tool in WALL_TOOLS:
            self.end_wall()
            return
        if self.tool != "select" or not self._scene:
            return
        t = self._token_at(e.x, e.y)
        if t is not None and self.on_token_open and self.is_dm:
            self.on_token_open(t["id"])

    def _right_click(self, e):
        if not self._scene:
            return
        if self._chain is not None:
            self.end_wall()
            return
        t = self._token_at(e.x, e.y)
        if t is not None:
            self.select(t["id"])
            if self.on_token_menu:
                self.on_token_menu(t["id"], e)
            return
        wall = self.wall_at(e.x, e.y) if self.is_dm else None
        if wall is not None and self.on_wall_menu:
            self.on_wall_menu(wall, e)

    def _hover(self, e):
        if self._drag is not None or not self._scene:
            return
        if self._chain is not None:
            self._draw_wall_preview(e.x, e.y)
            return
        t = self._token_at(e.x, e.y)
        if self.tool == "select" and self.place is None:
            self.configure(cursor="fleur" if t is not None and self.can_move(t) else "")

    def _wheel(self, e):
        if getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0:
            self.zoom_by(1.15, e.x, e.y)
        else:
            self.zoom_by(1 / 1.15, e.x, e.y)

    # panning: the items slide at once; the base picture is remade when the drag pauses or ends
    def _pan_start(self, e):
        self._drag = {"kind": "pan", "sx": e.x, "sy": e.y}

    def _pan_move(self, e):
        d = self._drag
        if not d or d.get("kind") != "pan":
            return
        dx, dy = e.x - d["sx"], e.y - d["sy"]
        d["sx"], d["sy"] = e.x, e.y
        self.vx -= dx / self.zoom
        self.vy -= dy / self.zoom
        self.move("all", dx, dy)
        self.schedule_render(120)

    def _pan_end(self, _e):
        self._drag = None
        self.schedule_render(5)

    # ------------------------------------------------------------------ selection

    def select(self, token_id: Optional[str]):
        if token_id == self.selected:
            return
        self.selected = token_id
        self._draw_overlay()
        if self.preview_sight:
            self.schedule_render(5)               # the preview looks through the selected token
        if self.on_select:
            self.on_select(token_id)

    def _delete_selected(self):
        if self.is_dm and self.selected:
            self.dispatch({"op": "token_delete", "id": self.selected})


def token_letter(name: str) -> str:
    """The letter on a token without a picture: the first letter (or digit) of its name."""
    for ch in name or "":
        if ch.isalnum():
            return ch.upper()
    return "?"


def _alt_held(state: int) -> bool:
    """Whether Alt (Option on a Mac) is held in a mouse event's state. The bit differs by system: on Windows
    0x0008 means Num Lock is on, so reading it as Alt turned every click into a ping there."""
    if sys.platform == "win32":
        return bool(state & 0x20000)
    if sys.platform == "darwin":
        return bool(state & 0x0010)
    return bool(state & 0x0008)


def _box(pts) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = pts[:4]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
