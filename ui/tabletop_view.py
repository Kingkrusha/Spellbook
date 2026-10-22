"""Game Tools > Tabletop: the battle map page.

The DM builds maps here (a picture or a blank area, a grid of squares or hexes, tokens, drawings and fog) and
shows one to the players. In a LAN session the players' Tabletop page shows that map, with what the DM hides
left out, and lets them move their own tokens, draw, measure and ping.

The model is ``tabletop.py``; the backends (the DM's own table, or a player's view fed by the DM) are in
``tabletop_net.py``; the map canvas is ``ui/tabletop_canvas.py``.
"""

from __future__ import annotations

import os
import tkinter as tk
from collections import OrderedDict
from tkinter import colorchooser, filedialog, messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import tabletop as T
import tabletop_net as N
from conditions import COMMON_EFFECTS, CONDITIONS
from theme import get_theme_manager
from typography import ui_font
from ui.tabletop_canvas import MapCanvas
from ui.tooltip import HoverTooltip
from ui.window_utils import add_cancel_save, center_on_parent

TOOL_BUTTONS = [
    # (tool, label, tooltip, dm only)
    ("select", "✋ Move", "Select and drag tokens; drag empty space to pan. Alt-click anywhere to ping.", False),
    ("ping", "📍 Ping", "Point at a spot on the map for everyone.", False),
    ("measure", "📐 Ruler", "Drag to measure a distance.", False),
    ("free", "✏️ Draw", "Draw freehand.", False),
    ("line", "╱ Line", "Draw a straight line.", False),
    ("rect", "▭ Box", "Draw a rectangle.", False),
    ("ellipse", "◯ Circle", "Draw a circle or oval.", False),
    ("erase", "🧽 Erase", "Click or drag over drawings and areas to remove them (players can only erase their own).",
     False),
    ("area", "💥 Area", "Drag out a spell's area: start on a token to cast it from that creature (it then moves with "
                       "it). Covered squares and creatures light up. Right-click an area to tilt, raise or remove it.",
     False),
    ("fog_reveal", "☀ Reveal", "Drag a box to reveal that part of the map to the players.", True),
    ("fog_hide", "🌫 Hide", "Drag a box to cover that part of the map again.", True),
    ("fog_lasso_reveal", "☀ Lasso", "Draw around an area to reveal it.", True),
    ("fog_lasso_hide", "🌫 Lasso", "Draw around an area to cover it again.", True),
    ("wall", "🧱 Wall", "Click corner to corner to draw walls; double-click, right-click or Esc stops. Ends snap to "
                       "other walls and grid corners. With line of sight on, players can't see through them.", True),
    ("door", "🚪 Door", "Click both ends of a door. Right-click a door to open or close it.", True),
    ("elevation", "⛰ Height", "Draw around part of the map to raise or sink it (the height is set on the Map tab). "
                             "Distances and areas count the climb.", True),
]
AREA_CHOICES = [T.AREA_LABELS[k] for k in T.AREA_SHAPES]
DRAW_COLORS = ["#E74C3C", "#F1C40F", "#2ECC71", "#3498DB", "#9B59B6", "#FFFFFF", "#111111"]
SIZE_NAMES = list(T.TOKEN_SIZES)


def _size_name(size: float) -> str:
    for name, value in T.TOKEN_SIZES.items():
        if value == size and name != "Small":
            return name
    return "Medium"


class _Thumbs:
    """Small CTkImages for the token library (kept apart from the content pictures' cache)."""

    def __init__(self, limit: int = 300):
        self.limit = limit
        self._items: "OrderedDict[tuple, ctk.CTkImage]" = OrderedDict()

    def get(self, path: str, side: int) -> Optional[ctk.CTkImage]:
        key = (path, side)
        if key in self._items:
            self._items.move_to_end(key)
            return self._items[key]
        try:
            from PIL import Image
            with Image.open(path) as im:
                im = im.convert("RGBA")
                im.thumbnail((side, side), Image.LANCZOS)
        except Exception:
            return None
        image = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)
        self._items[key] = image
        while len(self._items) > self.limit:
            self._items.popitem(last=False)
        return image


class TabletopView(ctk.CTkFrame):
    """The Tabletop page (see the module docstring)."""

    def __init__(self, parent, state: dict, *, service=None,
                 remote_backend: Optional[Callable[[], Optional[N.RemoteTable]]] = None,
                 on_back: Optional[Callable[[], None]] = None,
                 characters: Optional[Callable[[], List[dict]]] = None,
                 table: Optional[T.Tabletop] = None, assets: Optional[T.AssetStore] = None,
                 initiative: Optional[Callable[[], object]] = None,
                 on_open_source: Optional[Callable[[str, str], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.on_open_source = on_open_source  # (kind, name): open a monster's stat block or a character sheet
        self.initiative = initiative          # -> the tabletop_initiative.InitiativeLink (DM only)
        self.theme = get_theme_manager()
        self.state = state
        self.service = service
        self.remote_backend = remote_backend
        self.on_back = on_back
        self.characters = characters
        self.table = table or T.get_tabletop()
        self.assets = assets or T.get_assets()
        self.backend = None
        self.canvas: Optional[MapCanvas] = None
        self._local: Optional[N.LocalTable] = None
        self._tool_buttons: Dict[str, ctk.CTkButton] = {}
        self._thumbs = _Thumbs()
        self._status_job = None
        self._save_job = None
        self._opacity_job = None

        self.table.add_listener(self._table_changed)
        if service is not None:
            service.add_listener(self._on_service)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._build()

    # ------------------------------------------------------------------ set-up

    def _c(self, name: str) -> str:
        return self.theme.get_current_color(name)

    def _button(self, parent, text, command, width=90, accent=False, danger=False, **kw):
        if accent:
            colors = dict(fg_color=self._c("accent_primary"), hover_color=self._c("accent_hover"),
                          text_color=self._c("text_on_accent"))
        elif danger:
            colors = dict(fg_color=self._c("button_danger"), hover_color=self._c("button_danger_hover"),
                          text_color="white")
        else:
            colors = dict(fg_color=self._c("button_normal"), hover_color=self._c("button_hover"),
                          text_color=self._c("text_primary"))
        colors.update(kw)
        return ctk.CTkButton(parent, text=text, width=width, height=30, command=command, **colors)

    @property
    def is_player(self) -> bool:
        from lan.service import CLIENT
        return self.service is not None and self.service.role == CLIENT and self.remote_backend is not None

    def _build(self):
        for w in self.winfo_children():
            w.destroy()
        if self.backend is not None and self.backend is self._local:
            self._local.close()
            self._local = None
        if self.is_player:
            self.backend = self.remote_backend()
            self.backend.on_error(self._show_error)
        else:
            self._local = N.LocalTable(self.table, self.assets,
                                       name=(self.service.default_name() if self.service is not None else "DM"))
            wanted = self.state.get("scene")
            if wanted in self.table.scenes:
                self._local.scene_id = wanted
            self.backend = self._local
        dm = self.backend.role == "dm"

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=14, pady=10)

        # ---- top bar
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        if self.on_back:
            self._button(head, "← Game Tools", self.on_back, width=110).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(head, text="Tabletop", font=ui_font("title", 24, bold=True)).pack(side="left")
        if dm:
            self.scene_menu = ctk.CTkOptionMenu(head, values=["-"], width=200, command=self._pick_scene,
                                                dynamic_resizing=False)
            self.scene_menu.pack(side="left", padx=(16, 6))
            self._button(head, "＋ New Map", self._new_map, width=100, accent=True).pack(side="left")
            self.show_button = self._button(head, "Show to Players", self._toggle_shown, width=150)
            self.show_button.pack(side="left", padx=6)
            HoverTooltip(self.show_button, "The players' Tabletop shows this map (when you host a session).")
            self.undo_button = self._button(head, "↶ Undo", self._undo, width=70)
            self.undo_button.pack(side="left")
            if self.initiative is not None:
                turn = self._button(head, "Next Turn ▶", self._next_turn, width=100)
                turn.pack(side="left", padx=6)
                HoverTooltip(turn, "Move the initiative tracker to the next turn (starts combat if it hasn't).")
        else:
            self.scene_label = ctk.CTkLabel(head, text="", font=ui_font("subheading"),
                                            text_color=self.theme.get_text_secondary())
            self.scene_label.pack(side="left", padx=16)
        self._button(head, "Fit", lambda: self.canvas.fit(), width=44).pack(side="right")
        self._button(head, "＋", lambda: self.canvas.zoom_by(1.25), width=34).pack(side="right", padx=2)
        self._button(head, "－", lambda: self.canvas.zoom_by(0.8), width=34).pack(side="right", padx=2)
        self.status = ctk.CTkLabel(head, text="", font=ui_font("small"), text_color=self.theme.get_text_secondary())
        self.status.pack(side="right", padx=10)

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # ---- tools
        tools = ctk.CTkScrollableFrame(body, fg_color=self._c("bg_secondary"), width=96, corner_radius=8)
        tools.pack(side="left", fill="y", padx=(0, 8))
        for tool, label, tip, dm_only in TOOL_BUTTONS:
            if dm_only and not dm:
                continue
            if tool == "fog_reveal":
                ctk.CTkLabel(tools, text="Fog", font=ui_font("small", bold=True)).pack(pady=(10, 2))
            if tool == "wall":
                ctk.CTkLabel(tools, text="Walls", font=ui_font("small", bold=True)).pack(pady=(10, 2))
            if tool == "area":
                ctk.CTkLabel(tools, text="Areas", font=ui_font("small", bold=True)).pack(pady=(10, 2))
            b = ctk.CTkButton(tools, text=label, width=86, height=30, anchor="w",
                              command=lambda t=tool: self.set_tool(t))
            b.pack(pady=2)
            HoverTooltip(b, tip)
            self._tool_buttons[tool] = b
            if tool == "area":
                self.area_var = ctk.StringVar(value=T.AREA_LABELS["sphere"])
                ctk.CTkOptionMenu(tools, values=AREA_CHOICES, variable=self.area_var, width=86,
                                  dynamic_resizing=False, command=self._pick_area_shape).pack(pady=2)
                colors = ctk.CTkFrame(tools, fg_color="transparent")
                colors.pack()
                self._area_swatches = {}
                for i, color in enumerate(T.AREA_COLORS):
                    sw = ctk.CTkButton(colors, text="", width=22, height=22, corner_radius=11, fg_color=color,
                                       hover_color=color, border_width=2, border_color=self._c("bg_secondary"),
                                       command=lambda c=color: self._set_area_color(c))
                    sw.grid(row=i // 3, column=i % 3, padx=2, pady=2)
                    self._area_swatches[color] = sw
        ctk.CTkLabel(tools, text="Pen", font=ui_font("small", bold=True)).pack(pady=(10, 2))
        swatches = ctk.CTkFrame(tools, fg_color="transparent")
        swatches.pack()
        self._swatches = {}
        for i, color in enumerate(DRAW_COLORS):
            s = ctk.CTkButton(swatches, text="", width=22, height=22, corner_radius=11, fg_color=color,
                              hover_color=color, border_width=2, border_color=self._c("bg_secondary"),
                              command=lambda c=color: self._set_pen(c))
            s.grid(row=i // 3, column=i % 3, padx=2, pady=2)
            self._swatches[color] = s
        self.width_var = ctk.IntVar(value=4)
        ctk.CTkSlider(tools, from_=1, to=20, number_of_steps=19, width=80, variable=self.width_var,
                      command=lambda v: setattr(self.canvas, "draw_width", float(v))).pack(pady=(6, 2))
        if dm:
            self.private_var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(tools, text="DM only", variable=self.private_var, width=80,
                                 command=lambda: setattr(self.canvas, "draw_private", bool(self.private_var.get())))
            cb.pack(pady=4)
            HoverTooltip(cb, "New drawings only you can see (notes, traps, secret doors).")

        # ---- the side panel (DM)
        if dm:
            self.side = ctk.CTkTabview(body, width=300, corner_radius=8)
            self.side.pack(side="right", fill="y", padx=(8, 0))
            self._build_tokens_tab(self.side.add("Tokens"))
            self._build_map_tab(self.side.add("Map"))

        # ---- the map
        holder = ctk.CTkFrame(body, fg_color=self._c("bg_tertiary"), corner_radius=8)
        holder.pack(side="left", fill="both", expand=True)
        self.canvas = MapCanvas(holder, self.backend, on_select=self._on_select, on_token_menu=self._token_menu,
                                on_token_open=self._edit_token, on_wall_menu=self._wall_menu,
                                on_area_menu=self._area_menu, on_zone_menu=self._zone_menu,
                                on_status=self._set_status,
                                on_error=self._show_error, bg=_hex(self._c("bg_tertiary")))
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<Control-z>", lambda _e: self._undo())
        self.canvas.bind("<Command-z>", lambda _e: self._undo()) if os.sys.platform == "darwin" else None
        for key, factor in (("<plus>", 1.25), ("<equal>", 1.25), ("<minus>", 0.8)):
            self.canvas.bind(key, lambda _e, f=factor: self.canvas.zoom_by(f))
        self.backend.listen(self._backend_changed)
        self.set_tool("select")
        self._set_pen(DRAW_COLORS[0])
        self._set_area_color(T.AREA_COLORS[0])
        self._backend_changed()

    # ---- tokens tab
    def _build_tokens_tab(self, tab):
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))
        self._button(row, "＋ Token", self._add_blank_token, width=86).pack(side="left", padx=(0, 4))
        self._button(row, "Monster…", self._add_monster, width=86).pack(side="left", padx=(0, 4))
        self._button(row, "Character…", self._add_character, width=90).pack(side="left")
        if self.initiative is not None:
            add_all = self._button(tab, "⚔ Add map to initiative", self._add_map_to_initiative)
            add_all.pack(fill="x", pady=(2, 0))
            HoverTooltip(add_all, "Every creature token on this map that isn't in the initiative tracker yet. "
                                  "HP and conditions then stay in step, and the token whose turn it is glows.")

        self.selected_box = ctk.CTkFrame(tab, fg_color=self._c("bg_secondary"), corner_radius=8)
        self.selected_box.pack(fill="x", pady=6)
        self.selected_label = ctk.CTkLabel(self.selected_box, text="No token selected", font=ui_font("body"),
                                           anchor="w")
        self.selected_label.pack(fill="x", padx=8, pady=(6, 2))
        sel_buttons = ctk.CTkFrame(self.selected_box, fg_color="transparent")
        sel_buttons.pack(fill="x", padx=6, pady=(0, 6))
        self.sel_edit = self._button(sel_buttons, "Edit…", lambda: self._edit_token(self.canvas.selected), width=60)
        self.sel_edit.pack(side="left", padx=2)
        self.sel_hide = self._button(sel_buttons, "Hide", self._toggle_selected_hidden, width=60)
        self.sel_hide.pack(side="left", padx=2)
        self.sel_delete = self._button(sel_buttons, "Delete", lambda: self.canvas._delete_selected(), width=60,
                                       danger=True)
        self.sel_delete.pack(side="left", padx=2)

        lib_head = ctk.CTkFrame(tab, fg_color="transparent")
        lib_head.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(lib_head, text="Token library", font=ui_font("subheading", bold=True)).pack(side="left")
        self._button(lib_head, "Import…", self._import_tokens, width=70).pack(side="right")
        self._button(lib_head, "Folder", self._open_token_folder, width=56).pack(side="right", padx=4)
        self.lib_search = ctk.CTkEntry(tab, placeholder_text="Filter tokens")
        self.lib_search.pack(fill="x", pady=2)
        self.lib_search.bind("<KeyRelease>", lambda _e: self._fill_library())
        self.library = ctk.CTkScrollableFrame(tab, fg_color="transparent", height=230)
        self.library.pack(fill="both", expand=True)

        ctk.CTkLabel(tab, text="On this map", font=ui_font("subheading", bold=True), anchor="w").pack(
            fill="x", pady=(8, 2))
        self.token_list = ctk.CTkScrollableFrame(tab, fg_color="transparent", height=150)
        self.token_list.pack(fill="both", expand=True)
        self._fill_library()

    def _fill_library(self):
        for w in self.library.winfo_children():
            w.destroy()
        files = T.list_token_files()
        query = self.lib_search.get().strip().lower() if hasattr(self, "lib_search") else ""
        if query:
            files = [f for f in files if query in f[1].lower() or query in f[0].lower()]
        if not files:
            text = ("No token pictures yet. Use Import… with a folder or .zip of pictures (sub-folders become "
                    "groups), or put them in the token folder." if not query else "No tokens match.")
            ctk.CTkLabel(self.library, text=text, font=ui_font("small"), wraplength=250, justify="left",
                         text_color=self.theme.get_text_secondary()).pack(fill="x", pady=6)
            return
        shown = files[:120]
        grid = ctk.CTkFrame(self.library, fg_color="transparent")
        grid.pack(fill="x")
        for i, (group, name, path) in enumerate(shown):
            image = self._thumbs.get(path, 56)
            b = ctk.CTkButton(grid, text="", image=image, width=62, height=62, fg_color="transparent",
                              hover_color=self._c("button_hover"), command=lambda p=path, n=name: self._place_file(p, n))
            b.grid(row=i // 4, column=i % 4, padx=1, pady=1)
            HoverTooltip(b, f"{name}" + (f"  ({group})" if group else ""))
        if len(files) > len(shown):
            ctk.CTkLabel(self.library, text=f"{len(files) - len(shown)} more: filter to find them.",
                         font=ui_font("small"), text_color=self.theme.get_text_secondary()).pack(pady=4)

    def _fill_token_list(self):
        if not hasattr(self, "token_list"):
            return
        for w in self.token_list.winfo_children():
            w.destroy()
        scene = (self.backend.view() or {}).get("scene")
        if not scene or not scene["tokens"]:
            ctk.CTkLabel(self.token_list, text="No tokens yet.", font=ui_font("small"),
                         text_color=self.theme.get_text_secondary()).pack(anchor="w")
            return
        for t in scene["tokens"][:200]:
            label = t["name"] + ("  ⚔" if t.get("entry") else "") + ("  (hidden)" if t.get("hidden") else "") + (
                f"  ({t['owner_name']})" if t.get("owner_name") else "")
            b = ctk.CTkButton(self.token_list, text=label, anchor="w", height=24, fg_color="transparent",
                              text_color=self._c("text_primary"), hover_color=self._c("button_hover"),
                              command=lambda tid=t["id"], x=t["x"], y=t["y"]: (self.canvas.select(tid),
                                                                               self.canvas.center_on(x, y)))
            b.pack(fill="x")
            b.bind("<Double-Button-1>", lambda _e, tok=dict(t): self.open_source(tok))
        if self.on_open_source is not None:
            HoverTooltip(self.token_list, "Double-click a creature to open its stat block or character sheet.")

    def source_of(self, token: dict) -> Optional[tuple]:
        """``("monster" or "character", name)`` for what a token stands for, if it is in the collection."""
        kind, _, name = (token.get("source") or "").partition(":")
        if kind in ("monster", "character") and name:
            return kind, name
        try:
            from monster import get_monster_manager
            base = _base_name(token.get("name", ""))
            if get_monster_manager().get_monster(base) is not None:
                return "monster", base
        except Exception:
            pass
        return None

    def open_source(self, token: dict) -> bool:
        """Open a token's stat block (a monster) or character sheet (a character), if it has one."""
        source = self.source_of(token)
        if source is None or self.on_open_source is None:
            self._set_status(f"{token.get('name', 'That token')} has no stat block or character sheet.")
            return False
        self.on_open_source(*source)
        return True

    # ---- map tab
    def _build_map_tab(self, tab):
        self.map_tab = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.map_tab.pack(fill="both", expand=True)
        f = self.map_tab

        def label(text):
            ctk.CTkLabel(f, text=text, font=ui_font("small", bold=True), anchor="w").pack(fill="x", pady=(8, 1))

        label("Name")
        self.name_entry = ctk.CTkEntry(f)
        self.name_entry.pack(fill="x")
        self.name_entry.bind("<Return>", lambda _e: self._rename())
        self.name_entry.bind("<FocusOut>", lambda _e: self._rename())

        label("Grid")
        self.grid_var = ctk.StringVar(value=T.GRID_LABELS["square"])
        ctk.CTkOptionMenu(f, values=[T.GRID_LABELS[k] for k in T.GRID_TYPES], variable=self.grid_var,
                          command=lambda v: self._grid_update(type={b: a for a, b in T.GRID_LABELS.items()}[v])
                          ).pack(fill="x")
        self.cell_label = ctk.CTkLabel(f, text="", font=ui_font("small"), anchor="w")
        self.cell_label.pack(fill="x", pady=(6, 0))
        nudge = ctk.CTkFrame(f, fg_color="transparent")
        nudge.pack(fill="x")
        for text, delta in (("−5", -5), ("−1", -1), ("−.1", -0.1), ("+.1", 0.1), ("+1", 1), ("+5", 5)):
            self._button(nudge, text, lambda d=delta: self._nudge_grid("cell", d), width=38).pack(side="left", padx=1)
        HoverTooltip(nudge, "The size of one square or hex, in the map picture's pixels. Line it up with the grid "
                            "printed on the map.")
        self.offset_label = ctk.CTkLabel(f, text="", font=ui_font("small"), anchor="w")
        self.offset_label.pack(fill="x", pady=(6, 0))
        pad = ctk.CTkFrame(f, fg_color="transparent")
        pad.pack(fill="x")
        for text, axis, delta in (("◀", "ox", -1), ("▶", "ox", 1), ("▲", "oy", -1), ("▼", "oy", 1)):
            self._button(pad, text, lambda a=axis, d=delta: self._nudge_grid(a, d), width=40).pack(side="left",
                                                                                                padx=1)
        HoverTooltip(pad, "Slide the grid to line up with the map (hold the button to keep going).")

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row, text="Feet per cell", font=ui_font("small")).pack(side="left")
        self.feet_entry = ctk.CTkEntry(row, width=56)
        self.feet_entry.pack(side="right")
        self.feet_entry.bind("<Return>", lambda _e: self._set_feet())
        self.feet_entry.bind("<FocusOut>", lambda _e: self._set_feet())

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(row, text="Grid lines", font=ui_font("small")).pack(side="left")
        self.grid_color_btn = ctk.CTkButton(row, text="", width=28, height=22, command=self._pick_grid_color)
        self.grid_color_btn.pack(side="right")
        self.opacity_var = ctk.DoubleVar(value=0.35)
        ctk.CTkSlider(row, from_=0, to=1, width=120, variable=self.opacity_var,
                      command=self._opacity_moved).pack(
            side="right", padx=6)

        self.blank_box = ctk.CTkFrame(f, fg_color="transparent")
        self.blank_box.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(self.blank_box, text="Size in cells", font=ui_font("small")).pack(side="left")
        self.rows_entry = ctk.CTkEntry(self.blank_box, width=44)
        self.rows_entry.pack(side="right")
        ctk.CTkLabel(self.blank_box, text="×", font=ui_font("small")).pack(side="right", padx=2)
        self.cols_entry = ctk.CTkEntry(self.blank_box, width=44)
        self.cols_entry.pack(side="right")
        for e in (self.rows_entry, self.cols_entry):
            e.bind("<Return>", lambda _e: self._set_blank_size())

        label("Players")
        self.players_draw_var = ctk.BooleanVar()
        ctk.CTkCheckBox(f, text="Players can draw", variable=self.players_draw_var,
                        command=lambda: self._scene_fields(players_draw=bool(self.players_draw_var.get()))
                        ).pack(anchor="w", pady=2)
        self.players_move_var = ctk.BooleanVar()
        ctk.CTkCheckBox(f, text="Players can move every token", variable=self.players_move_var,
                        command=lambda: self._scene_fields(players_move_all=bool(self.players_move_var.get()))
                        ).pack(anchor="w", pady=2)

        label("Fog of war")
        self.fog_var = ctk.BooleanVar()
        ctk.CTkSwitch(f, text="Fog on", variable=self.fog_var,
                      command=lambda: self._scene_fields(fog_on=bool(self.fog_var.get()))).pack(anchor="w", pady=2)
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=2)
        self._button(row, "Cover all", lambda: self._dispatch({"op": "fog_reset", "mode": "hide"}), width=90
                     ).pack(side="left", padx=(0, 4))
        self._button(row, "Reveal all", lambda: self._dispatch({"op": "fog_reset", "mode": "clear"}), width=90
                     ).pack(side="left")

        label("Walls and line of sight")
        self.los_var = ctk.BooleanVar()
        los = ctk.CTkSwitch(f, text="Line of sight", variable=self.los_var,
                            command=lambda: self._scene_fields(los=bool(self.los_var.get())))
        los.pack(anchor="w", pady=2)
        HoverTooltip(los, "Players see only what their tokens can see past the walls (a player with no token "
                          "of their own sees through the party's). Creatures out of sight are left off their map.")
        self.show_walls_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(f, text="Show walls", variable=self.show_walls_var,
                        command=self._toggle_show_walls).pack(anchor="w", pady=2)
        self.preview_var = ctk.BooleanVar(value=False)
        preview = ctk.CTkCheckBox(f, text="Preview what players see", variable=self.preview_var,
                                  command=self._toggle_preview)
        preview.pack(anchor="w", pady=2)
        HoverTooltip(preview, "Dim the map as the party's tokens see it, or as the selected token sees it.")
        self.walls_label = ctk.CTkLabel(f, text="", font=ui_font("small"), anchor="w",
                                        text_color=self.theme.get_text_secondary())
        self.walls_label.pack(fill="x")
        self._button(f, "Remove all walls", self._clear_walls, width=140).pack(anchor="w", pady=2)

        label("Height")
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text="New raised area (ft)", font=ui_font("small")).pack(side="left")
        self.zone_entry = ctk.CTkEntry(row, width=56)
        self.zone_entry.insert(0, "10")
        self.zone_entry.pack(side="right")
        self.zone_entry.bind("<KeyRelease>", lambda _e: self._set_zone_height())
        HoverTooltip(row, "How high the next area you draw with the ⛰ Height tool is (negative sinks it: a pit "
                          "or a river bed). Right-click an area to change it.")
        self.show_zones_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(f, text="Show heights", variable=self.show_zones_var,
                        command=self._toggle_show_zones).pack(anchor="w", pady=2)
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=2)
        self._button(row, "Remove heights", lambda: self._confirm_clear("zones", "zone_clear"), width=120
                     ).pack(side="left", padx=(0, 4))
        self._button(row, "Remove areas", lambda: self._confirm_clear("areas", "area_clear"), width=110
                     ).pack(side="left")

        label("Map")
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=2)
        self._button(row, "Clear drawings", self._clear_drawings, width=120).pack(side="left", padx=(0, 4))
        self._button(row, "Duplicate", lambda: self._dispatch({"op": "scene_duplicate"}), width=90).pack(side="left")
        self._button(f, "Delete this map", self._delete_scene, width=140, danger=True).pack(anchor="w", pady=(6, 10))

    # ------------------------------------------------------------------ keeping the page current

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        self.table.remove_listener(self._table_changed)
        if self.service is not None:
            self.service.remove_listener(self._on_service)
        if self.backend is not None:
            try:
                self.backend.unlisten(self._backend_changed)
            except Exception:
                pass
        if self._local is not None:
            self._local.close()
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except tk.TclError:
                pass
            self.table.save()

    def _on_service(self, kind: str, **_data):
        if kind != "state":
            return
        player = self.backend is not None and self.backend.role == "player"
        if player != self.is_player:              # joined or left a session as a player: change sides
            self.after_idle(self._build)

    def _table_changed(self, _scene_id):
        if self._save_job is None:
            try:
                self._save_job = self.after(800, self._save)
            except tk.TclError:
                pass

    def _save(self):
        self._save_job = None
        self.table.save()

    def _backend_changed(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        view = self.backend.view()
        scene = view.get("scene")
        if self.backend.role == "player":
            self.scene_label.configure(text=f"Map: {scene['name']}" if scene else "No map shown")
            return
        self.state["scene"] = scene["id"] if scene else ""
        names = [s["name"] for s in self.table.scene_list()]
        self._scene_ids = [s["id"] for s in self.table.scene_list()]
        self.scene_menu.configure(values=_unique(names) or ["No maps"])
        if scene:
            self.scene_menu.set(_unique(names)[self._scene_ids.index(scene["id"])])
        else:
            self.scene_menu.set("No maps")
        shown = scene is not None and self.table.shown == scene["id"]
        self.show_button.configure(text="✓ Shown to Players" if shown else "Show to Players",
                                   fg_color=self._c("button_success") if shown else self._c("button_normal"))
        self.undo_button.configure(state="normal" if self.table.can_undo() else "disabled")
        self._sync_map_tab(scene)
        self._fill_token_list()
        self._on_select(self.canvas.selected if self.canvas else None)

    def _sync_map_tab(self, scene):
        if scene is None:
            return
        g = scene["grid"]
        if self.focus_get() is not self.name_entry._entry:
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, scene["name"])
        self.grid_var.set(T.GRID_LABELS.get(g["type"], "Squares"))
        self.cell_label.configure(text=f"Cell size: {g['cell']:.1f} px")
        self.offset_label.configure(text=f"Grid offset: {g['ox']:.0f}, {g['oy']:.0f}")
        if self.focus_get() is not self.feet_entry._entry:
            self.feet_entry.delete(0, "end")
            self.feet_entry.insert(0, f"{g['feet']:g}")
        self.opacity_var.set(g.get("opacity", 0.35))
        self.grid_color_btn.configure(fg_color=g.get("color", "#000000"), hover_color=g.get("color", "#000000"))
        self.players_draw_var.set(bool(scene.get("players_draw")))
        self.players_move_var.set(bool(scene.get("players_move_all")))
        self.fog_var.set(bool(scene["fog"].get("on")))
        self.los_var.set(bool(scene.get("los")))
        walls = scene.get("walls") or []
        doors = sum(1 for w in walls if w.get("door"))
        self.walls_label.configure(text=f"{len(walls) - doors} wall{'s' if len(walls) - doors != 1 else ''}, "
                                        f"{doors} door{'s' if doors != 1 else ''}")
        if scene.get("map"):
            self.blank_box.pack_forget()
        else:
            self.blank_box.pack(fill="x", pady=(6, 0), after=self.grid_color_btn.master)
            for entry, value in ((self.cols_entry, scene["w"] / g["cell"]), (self.rows_entry, scene["h"] / g["cell"])):
                if self.focus_get() is not entry._entry:
                    entry.delete(0, "end")
                    entry.insert(0, f"{value:.0f}")

    # ------------------------------------------------------------------ actions

    def _dispatch(self, cmd: dict) -> Optional[dict]:
        return self.canvas.dispatch(cmd) if self.canvas else None

    def _set_status(self, text: str, color: Optional[str] = None):
        try:
            self.status.configure(text=text, text_color=color or self.theme.get_text_secondary())
        except tk.TclError:
            return
        if self._status_job is not None:
            self.after_cancel(self._status_job)
            self._status_job = None
        if text and color:
            self._status_job = self.after(4500, lambda: self._set_status(""))

    def _show_error(self, text: str):
        if text:
            self._set_status(text, self._c("button_danger"))

    def set_tool(self, tool: str):
        self.canvas.set_tool(tool)
        for name, b in self._tool_buttons.items():
            active = name == self.canvas.tool
            b.configure(fg_color=self._c("accent_primary") if active else self._c("button_normal"),
                        hover_color=self._c("accent_hover") if active else self._c("button_hover"),
                        text_color=self._c("text_on_accent") if active else self._c("text_primary"))

    def _set_pen(self, color: str):
        self.canvas.draw_color = color
        for c, s in self._swatches.items():
            s.configure(border_color=self._c("accent_primary") if c == color else self._c("bg_secondary"))

    def _undo(self):
        if self.backend.role == "dm" and not self.backend.undo():
            self._set_status("Nothing to undo.")

    # scenes
    def _pick_scene(self, label: str):
        names = _unique([s["name"] for s in self.table.scene_list()])
        if label in names:
            self._local.select_scene(self._scene_ids[names.index(label)])

    def _toggle_shown(self):
        scene = self.backend.view().get("scene")
        if scene is None:
            return
        self._dispatch({"op": "scene_show", "scene": "" if self.table.shown == scene["id"] else scene["id"]})
        if self.table.shown and (self.service is None or not self.service.active):
            self._set_status("Shown. Host a session (Game Tools > Session) and players will see it.")

    def _new_map(self):
        dialog = NewMapDialog(self.winfo_toplevel())
        self.wait_window(dialog)
        if dialog.result is None:
            return
        data = dict(dialog.result)
        path = data.pop("path", None)
        if path:
            self.configure(cursor="watch")
            self.update_idletasks()
            try:
                asset, w, h = self.assets.add_image(path)
            except Exception as e:
                messagebox.showerror("New map", f"That picture couldn't be opened.\n\n{e}", parent=self)
                return
            finally:
                self.configure(cursor="")
            data.update(map=asset, w=w, h=h)
        self._dispatch({"op": "scene_new", "scene_data": data})

    def _rename(self):
        scene = self.backend.view().get("scene")
        name = self.name_entry.get().strip()
        if scene and name and name != scene["name"]:
            self._dispatch({"op": "scene_rename", "name": name})

    def _opacity_moved(self, value):
        """The slider sends every step: apply the last one once it stops (one undo step, not fifty)."""
        if self._opacity_job is not None:
            self.after_cancel(self._opacity_job)
        self._opacity_job = self.after(250, lambda: (setattr(self, "_opacity_job", None),
                                                     self._grid_update(opacity=round(float(value), 2))))

    def _grid_update(self, **grid):
        if self.backend.view().get("scene"):
            self._dispatch({"op": "scene_update", "grid": grid})

    def _nudge_grid(self, key: str, delta: float):
        scene = self.backend.view().get("scene")
        if scene:
            self._grid_update(**{key: round(scene["grid"][key] + delta, 2)})

    def _set_feet(self):
        try:
            feet = float(self.feet_entry.get())
        except ValueError:
            return
        scene = self.backend.view().get("scene")
        if scene and feet != scene["grid"]["feet"]:
            self._grid_update(feet=feet)

    def _pick_grid_color(self):
        scene = self.backend.view().get("scene")
        if not scene:
            return
        color = colorchooser.askcolor(color=scene["grid"].get("color", "#000000"), parent=self)[1]
        if color:
            self._grid_update(color=color.upper())

    def _set_blank_size(self):
        scene = self.backend.view().get("scene")
        if not scene or scene.get("map"):
            return
        try:
            cols, rows = int(self.cols_entry.get()), int(self.rows_entry.get())
        except ValueError:
            return
        cell = scene["grid"]["cell"]
        self._scene_fields(w=max(1, cols) * cell, h=max(1, rows) * cell)

    def _scene_fields(self, **fields):
        self._dispatch({"op": "scene_update", "fields": fields})

    def _clear_drawings(self):
        if messagebox.askyesno("Clear drawings", "Remove every drawing on this map?", parent=self):
            self._dispatch({"op": "draw_clear"})

    # ---- areas and heights
    def _pick_area_shape(self, label: str):
        shape = {v: k for k, v in T.AREA_LABELS.items()}.get(label, "sphere")
        self.canvas.area_shape = shape
        self.set_tool("area")

    def _set_area_color(self, color: str):
        if not hasattr(self, "_area_swatches"):
            return
        self.canvas.area_color = color
        for c, sw in self._area_swatches.items():
            sw.configure(border_color="#FFFFFF" if c == color else self._c("bg_secondary"))

    def _set_zone_height(self):
        try:
            self.canvas.zone_height = max(-T.MAX_HEIGHT, min(T.MAX_HEIGHT, float(self.zone_entry.get())))
        except ValueError:
            pass

    def _toggle_show_zones(self):
        self.canvas.show_zones = bool(self.show_zones_var.get())
        self.canvas._draw_overlay()

    def _confirm_clear(self, key: str, op: str):
        scene = self.backend.view().get("scene") or {}
        n = len(scene.get(key) or [])
        if not n:
            return
        what = {"zones": "raised and sunken areas", "areas": "spell areas"}[key]
        if messagebox.askyesno("Tabletop", f"Remove all {n} {what} from this map?", parent=self):
            self._dispatch({"op": op})

    def _area_menu(self, area_id: str, event):
        area = self.canvas.area(area_id)
        if not self.canvas.can_edit_area(area):
            return
        upd = lambda **f: self._dispatch({"op": "area_update", "id": area_id, "fields": f})  # noqa: E731
        menu = tk.Menu(self, tearoff=0)
        if area["shape"] in ("cone", "line"):
            pitch = area.get("pitch", 0.0)
            menu.add_command(label="Tilt up 15°", command=lambda: upd(pitch=min(90, pitch + 15)))
            menu.add_command(label="Tilt down 15°", command=lambda: upd(pitch=max(-90, pitch - 15)))
            if pitch:
                menu.add_command(label="Level", command=lambda: upd(pitch=0))
        if area["shape"] == "line":
            width = area.get("width", 5.0)
            menu.add_command(label="Wider (+5 ft)", command=lambda: upd(width=width + 5))
            if width > 5:
                menu.add_command(label="Narrower (−5 ft)", command=lambda: upd(width=width - 5))
        dz = area.get("dz", 0.0)
        menu.add_command(label="Raise 5 ft", command=lambda: upd(dz=dz + 5))
        menu.add_command(label="Lower 5 ft", command=lambda: upd(dz=dz - 5))
        menu.add_command(label="Bigger (+5 ft)", command=lambda: upd(size=area["size"] + 5))
        if area["size"] > 5:
            menu.add_command(label="Smaller (−5 ft)", command=lambda: upd(size=area["size"] - 5))
        menu.add_separator()
        following = self.canvas.token(area.get("token"))
        selected = self.canvas.token(self.canvas.selected)
        if following is not None:
            menu.add_command(label=f"Stop moving with {following['name']}", command=lambda: upd(token=""))
        if selected is not None and (following is None or selected["id"] != following["id"]):
            menu.add_command(label=f"Move with {selected['name']}", command=lambda: upd(token=selected["id"]))
        if following is None and selected is None:
            menu.add_command(label="Move with a token (select it first)", state="disabled")
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._dispatch({"op": "area_delete", "id": area_id}))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _zone_menu(self, zone_id: str, event):
        scene = self.backend.view().get("scene") or {}
        zone = next((z for z in scene.get("zones") or [] if z["id"] == zone_id), None)
        if zone is None or self.backend.role != "dm":
            return
        menu = tk.Menu(self, tearoff=0)
        for delta in (5, 10, -5, -10):
            menu.add_command(label=f"{'Raise' if delta > 0 else 'Lower'} {abs(delta)} ft",
                             command=lambda d=delta: self._dispatch({"op": "zone_update", "id": zone_id,
                                                                     "elev": zone["elev"] + d}))
        menu.add_command(label="Height…", command=lambda: self._ask_zone_height(zone))
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._dispatch({"op": "zone_delete", "id": zone_id}))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _ask_zone_height(self, zone: dict):
        dialog = ctk.CTkInputDialog(title="Height", text=f"Height in feet (now {zone['elev']:g}; negative is below "
                                                         f"the ground):")
        value = dialog.get_input()
        try:
            self._dispatch({"op": "zone_update", "id": zone["id"], "elev": float(value)})
        except (TypeError, ValueError):
            pass

    def _toggle_show_walls(self):
        self.canvas.show_walls = bool(self.show_walls_var.get())
        self.canvas._draw_overlay()

    def _toggle_preview(self):
        self.canvas.preview_sight = bool(self.preview_var.get())
        self.canvas.render()

    def _clear_walls(self):
        scene = self.backend.view().get("scene")
        if not scene or not scene.get("walls"):
            return
        if messagebox.askyesno("Remove walls", f"Remove all {len(scene['walls'])} walls and doors from this map?",
                               parent=self):
            self._dispatch({"op": "wall_clear"})

    def _wall_menu(self, wall_id: str, event):
        scene = self.backend.view().get("scene") or {}
        wall = next((w for w in scene.get("walls") or [] if w["id"] == wall_id), None)
        if wall is None or self.backend.role != "dm":
            return
        menu = tk.Menu(self, tearoff=0)
        if wall.get("door"):
            menu.add_command(label="Close door" if wall.get("open") else "Open door",
                             command=lambda: self._dispatch({"op": "wall_update", "id": wall_id,
                                                             "fields": {"open": not wall.get("open")}}))
            menu.add_command(label="Make it a wall", command=lambda: self._dispatch(
                {"op": "wall_update", "id": wall_id, "fields": {"door": False}}))
        else:
            menu.add_command(label="Make it a door", command=lambda: self._dispatch(
                {"op": "wall_update", "id": wall_id, "fields": {"door": True}}))
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._dispatch({"op": "wall_delete", "id": wall_id}))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _delete_scene(self):
        scene = self.backend.view().get("scene")
        if scene and messagebox.askyesno("Delete map", f"Delete '{scene['name']}' with its tokens and drawings? "
                                                       "(Undo brings it back.)", parent=self):
            self._dispatch({"op": "scene_delete"})

    # tokens
    def _on_select(self, token_id: Optional[str]):
        if not hasattr(self, "selected_label"):
            return
        t = self.canvas.token(token_id) if self.canvas else None
        try:
            if t is None:
                self.selected_label.configure(text="No token selected. Click one on the map.")
                for b in (self.sel_edit, self.sel_hide, self.sel_delete):
                    b.configure(state="disabled")
                return
            hp = f"  ·  {t['hp']}/{t['hp_max']} HP" if t.get("hp") is not None and t.get("hp_max") else ""
            init = "  ·  in initiative" if t.get("entry") else ""
            self.selected_label.configure(text=f"{t['name']}{hp}{init}")
            self.sel_hide.configure(text="Show" if t.get("hidden") else "Hide")
            for b in (self.sel_edit, self.sel_hide, self.sel_delete):
                b.configure(state="normal")
        except tk.TclError:
            pass

    def _toggle_selected_hidden(self):
        t = self.canvas.token(self.canvas.selected)
        if t:
            self._dispatch({"op": "token_update", "id": t["id"], "fields": {"hidden": not t.get("hidden")}})

    def _scene_or_warn(self) -> Optional[dict]:
        scene = self.backend.view().get("scene")
        if scene is None:
            messagebox.showinfo("Tabletop", "Make a map first (＋ New Map).", parent=self)
        return scene

    def _unique_name(self, name: str) -> str:
        scene = self.backend.view().get("scene") or {"tokens": []}
        taken = {t["name"] for t in scene["tokens"]}
        if name not in taken:
            return name
        n = 2
        while f"{name} {n}" in taken:
            n += 1
        return f"{name} {n}"

    def _add_blank_token(self):
        if self._scene_or_warn() is None:
            return
        dialog = TokenDialog(self.winfo_toplevel(), T.new_token(self._unique_name("Token"), 0, 0),
                             self._players(), title="New token")
        self.wait_window(dialog)
        if dialog.result:
            token = dict(dialog.result)
            if not token.get("image"):
                # a token named after a monster gets the monster's picture, if an image pack has one
                image = self._monster_image(_base_name(token["name"]))
                if image:
                    token["image"] = image
            self.canvas.start_placing(token)

    def _monster_image(self, name: str) -> str:
        """The token picture (an asset id) for a monster with a picture in the image packs, or ""."""
        picture = _content_picture("monsters", name)
        if not picture:
            return ""
        try:
            return self.assets.add_image(picture, token=True)[0]
        except Exception as e:
            print(f"Tabletop: the picture of {name} couldn't be used ({e})")
            return ""

    def _place_file(self, path: str, name: str):
        if self._scene_or_warn() is None:
            return
        try:
            asset, _w, _h = self.assets.add_image(path, token=True)
        except Exception as e:
            self._show_error(f"That picture couldn't be opened ({e}).")
            return
        self.canvas.start_placing({"name": self._unique_name(name.title()), "image": asset})

    def _add_monster(self):
        if self._scene_or_warn() is None:
            return
        from monster import get_monster_manager
        manager = get_monster_manager()
        dialog = PickDialog(self.winfo_toplevel(), "Add a monster", [m.name for m in manager.monsters])
        self.wait_window(dialog)
        if not dialog.result:
            return
        monster = manager.get_monster(dialog.result)
        if monster is None:
            return
        token = {"name": self._unique_name(monster.name), "size": T.TOKEN_SIZES.get(monster.size, 1.0),
                 "hp": monster.hp, "hp_max": monster.hp, "color": T.DEFAULT_COLORS[0],
                 "source": f"monster:{monster.name}"}
        image = self._monster_image(monster.name)
        if image:
            token["image"] = image
        self.canvas.start_placing(token)

    def _add_character(self):
        if self._scene_or_warn() is None:
            return
        chars = self.characters() if self.characters else []
        if not chars:
            messagebox.showinfo("Add a character", "There are no characters yet.", parent=self)
            return
        dialog = PickDialog(self.winfo_toplevel(), "Add a character", [c["name"] for c in chars])
        self.wait_window(dialog)
        if not dialog.result:
            return
        c = next(c for c in chars if c["name"] == dialog.result)
        token = {"name": c["name"], "kind": "pc", "hp": c.get("hp"), "hp_max": c.get("hp_max"),
                 "color": T.DEFAULT_COLORS[1], "source": f"character:{c['name']}"}
        # the player who plays this character, if they're connected
        for name, cid in self._players():
            if name.lower() == c["name"].lower() or name.lower() == (c.get("player") or "").lower():
                token.update(owner=cid, owner_name=name)
        if c.get("portrait"):
            try:
                token["image"] = self.assets.add_image(c["portrait"], token=True)[0]
            except Exception:
                pass
        self.canvas.start_placing(token)

    def _players(self) -> List[tuple]:
        """``[(name, install id)]`` of the players connected to the session being hosted."""
        s = self.service
        if s is None:
            return []
        return [(p["name"], s.client_ids[p["peer_id"]]) for p in s.peers
                if p["peer_id"] != s.my_id and p["peer_id"] in s.client_ids]

    def _edit_token(self, token_id: Optional[str]):
        t = self.canvas.token(token_id)
        if t is None or self.backend.role != "dm":
            return
        dialog = TokenDialog(self.winfo_toplevel(), t, self._players())
        self.wait_window(dialog)
        if dialog.result:
            self._dispatch({"op": "token_update", "id": t["id"], "fields": dialog.result})

    def _token_menu(self, token_id: str, event):
        t = self.canvas.token(token_id)
        if t is None or self.backend.role != "dm":
            return
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edit…", command=lambda: self._edit_token(token_id))
        conditions = tk.Menu(menu, tearoff=0)
        current = set(t.get("conditions") or [])
        for name in CONDITIONS + COMMON_EFFECTS:
            var = tk.BooleanVar(value=name in current)
            conditions.add_checkbutton(label=name, variable=var, command=lambda n=name: self._dispatch(
                {"op": "token_condition", "id": token_id, "name": n}))
            conditions._vars = getattr(conditions, "_vars", []) + [var]
        menu.add_cascade(label="Conditions", menu=conditions)
        hp = tk.Menu(menu, tearoff=0)
        for delta in (-10, -5, -1, 1, 5, 10):
            hp.add_command(label=f"{delta:+d}", command=lambda d=delta: self._change_hp(token_id, d))
        if t.get("hp") is not None:
            menu.add_cascade(label="Hit points", menu=hp)
        menu.add_command(label="Show to players" if t.get("hidden") else "Hide from players",
                         command=lambda: self._dispatch({"op": "token_update", "id": token_id,
                                                         "fields": {"hidden": not t.get("hidden")}}))
        menu.add_command(label="Bring to front", command=lambda: self._dispatch({"op": "token_front",
                                                                                 "id": token_id}))
        menu.add_command(label="Duplicate", command=lambda: self._duplicate_token(t))
        link = self._link()
        if link is not None and t.get("kind") != "prop":
            menu.add_separator()
            if link.entry_for(t) is None:
                menu.add_command(label="Add to initiative", command=lambda: self._add_to_initiative([token_id]))
            else:
                menu.add_command(label="Remove from initiative",
                                 command=lambda: self._remove_from_initiative(token_id))
        menu.add_separator()
        menu.add_command(label="Delete", command=lambda: self._dispatch({"op": "token_delete", "id": token_id}))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ---- initiative tracker
    def _link(self):
        if self.initiative is None or self.backend is None or self.backend.role != "dm":
            return None
        try:
            return self.initiative()
        except Exception as e:
            print(f"Tabletop: no initiative link ({e})")
            return None

    def _add_to_initiative(self, token_ids: List[str]) -> int:
        link = self._link()
        if link is None:
            return 0
        import initiative_state as I
        try:
            added = link.add(self.backend.scene_id, token_ids)
        except I.CommandError as e:
            self._show_error(e.message)
            return 0
        if added:
            self._set_status(f"Added {added} to initiative.")
        return added

    def _add_map_to_initiative(self):
        link = self._link()
        if link is None or self._scene_or_warn() is None:
            return
        tokens = link.addable(self.backend.scene_id)
        if not tokens:
            self._set_status("Every creature on this map is already in initiative.")
            return
        self._add_to_initiative([t["id"] for t in tokens])

    def _remove_from_initiative(self, token_id: str):
        link = self._link()
        if link is not None:
            link.unlink(self.backend.scene_id, token_id, remove_entry=True)

    def _next_turn(self):
        link = self._link()
        if link is None:
            return
        import initiative_state as I
        try:
            link.next_turn()
        except I.CommandError as e:
            self._show_error(e.message)

    def _change_hp(self, token_id: str, delta: int):
        t = self.canvas.token(token_id)
        if t and t.get("hp") is not None:
            top = t.get("hp_max") or 99999
            self._dispatch({"op": "token_update", "id": token_id,
                            "fields": {"hp": max(0, min(top, t["hp"] + delta))}})

    def _duplicate_token(self, t: dict):
        copy_ = {k: v for k, v in t.items() if k in T.TOKEN_FIELDS and k != "entry"}
        copy_["name"] = self._unique_name(_base_name(t["name"]))
        copy_["x"], copy_["y"] = T.Grid.of(self.backend.view()["scene"]).snap(
            t["x"] + T.Grid.of(self.backend.view()["scene"]).cell, t["y"], t.get("size", 1.0))
        self._dispatch({"op": "token_add", "token": copy_})

    def _import_tokens(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="A .zip of pictures…", command=lambda: self._do_import(zip_=True))
        menu.add_command(label="A folder of pictures…", command=lambda: self._do_import(zip_=False))
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _do_import(self, zip_: bool):
        if zip_:
            source = filedialog.askopenfilename(parent=self, title="Import tokens",
                                                filetypes=[("Token pack", "*.zip"), ("All files", "*.*")])
        else:
            source = filedialog.askdirectory(parent=self, title="Folder of token pictures")
        if not source:
            return
        try:
            count = T.import_tokens(source)
        except Exception as e:
            messagebox.showerror("Import tokens", f"Those tokens couldn't be imported.\n\n{e}", parent=self)
            return
        self._set_status(f"Imported {count} token picture{'s' if count != 1 else ''}.")
        self._fill_library()

    def _open_token_folder(self):
        folder = T.token_folder()
        os.makedirs(folder, exist_ok=True)
        from ui.pdf_library_view import open_externally
        open_externally(folder)


# --------------------------------------------------------------------------- dialogs

class _Dialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, size: str):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.result = None
        self.title(title)
        self.geometry(size)
        self.transient(parent)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=18, pady=14)
        self.after(50, self._grab)
        center_on_parent(self, parent, clamp=True)

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def _buttons(self, confirm: str = "OK"):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        first = self.body.pack_slaves()
        # packed ahead of the rest, so a short window squeezes the fields, never the buttons
        row.pack(side="bottom", fill="x", pady=(10, 0), **({"before": first[0]} if first else {}))
        add_cancel_save(row, self.theme, self.destroy, self._accept, confirm_text=confirm, outlined=True)

    def _accept(self):
        raise NotImplementedError


class NewMapDialog(_Dialog):
    """A new map: a picture (a battle map) or a blank area of so many cells."""

    def __init__(self, parent):
        self.path: Optional[str] = None
        super().__init__(parent, "New map", "440x380")
        b = self.body
        ctk.CTkLabel(b, text="Name", font=ui_font("small", bold=True), anchor="w").pack(fill="x")
        self.name = ctk.CTkEntry(b)
        self.name.insert(0, "New Map")
        self.name.pack(fill="x", pady=(0, 8))
        self.kind = ctk.StringVar(value="Picture")
        ctk.CTkSegmentedButton(b, values=["Picture", "Blank"], variable=self.kind,
                               command=lambda _v: self._kind_changed()).pack(anchor="w")
        self.picture_row = ctk.CTkFrame(b, fg_color="transparent")
        ctk.CTkButton(self.picture_row, text="Choose picture…", width=140, command=self._choose).pack(side="left")
        self.picture_label = ctk.CTkLabel(self.picture_row, text="No picture chosen", font=ui_font("small"))
        self.picture_label.pack(side="left", padx=8)
        self.blank_row = ctk.CTkFrame(b, fg_color="transparent")
        ctk.CTkLabel(self.blank_row, text="Cells", font=ui_font("small")).pack(side="left")
        self.cols = ctk.CTkEntry(self.blank_row, width=50)
        self.cols.insert(0, "30")
        self.cols.pack(side="left", padx=4)
        ctk.CTkLabel(self.blank_row, text="×", font=ui_font("small")).pack(side="left")
        self.rows = ctk.CTkEntry(self.blank_row, width=50)
        self.rows.insert(0, "20")
        self.rows.pack(side="left", padx=4)
        ctk.CTkLabel(b, text="Grid", font=ui_font("small", bold=True), anchor="w").pack(fill="x", pady=(14, 0))
        self.grid = ctk.StringVar(value=T.GRID_LABELS["square"])
        ctk.CTkOptionMenu(b, values=[T.GRID_LABELS[k] for k in T.GRID_TYPES], variable=self.grid).pack(anchor="w")
        row = ctk.CTkFrame(b, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row, text="Cell size in pixels", font=ui_font("small")).pack(side="left")
        self.cell = ctk.CTkEntry(row, width=60)
        self.cell.insert(0, "70")
        self.cell.pack(side="left", padx=6)
        ctk.CTkLabel(b, text="For a battle map, use its grid's square size; you can fine-tune it on the Map tab.",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary(), wraplength=380,
                     justify="left").pack(fill="x", pady=4)
        self._buttons("Create")
        self._kind_changed()

    def _kind_changed(self):
        self.picture_row.pack_forget()
        self.blank_row.pack_forget()
        row = self.picture_row if self.kind.get() == "Picture" else self.blank_row
        row.pack(fill="x", pady=8, after=self.body.winfo_children()[2])

    def _choose(self):
        path = filedialog.askopenfilename(parent=self, title="Battle map picture", filetypes=[
            ("Pictures", " ".join(f"*{e}" for e in T.IMAGE_TYPES)), ("All files", "*.*")])
        if path:
            self.path = path
            self.picture_label.configure(text=os.path.basename(path)[:40])
            if self.name.get() == "New Map":
                self.name.delete(0, "end")
                self.name.insert(0, os.path.splitext(os.path.basename(path))[0].replace("_", " ")[:40])

    def _accept(self):
        try:
            cell = max(8.0, float(self.cell.get()))
        except ValueError:
            cell = 70.0
        grid = {b: a for a, b in T.GRID_LABELS.items()}[self.grid.get()]
        data = {"name": self.name.get().strip() or "Map", "cell": cell, "grid": grid}
        if self.kind.get() == "Picture":
            if not self.path:
                messagebox.showwarning("New map", "Choose a picture, or pick Blank.", parent=self)
                return
            data["path"] = self.path
        else:
            try:
                cols, rows = max(1, int(self.cols.get())), max(1, int(self.rows.get()))
            except ValueError:
                cols, rows = 30, 20
            data.update(w=int(cols * cell), h=int(rows * cell))
        self.result = data
        self.destroy()


class TokenDialog(_Dialog):
    """Everything about one token. ``result`` is the changed fields."""

    def __init__(self, parent, token: dict, players: List[tuple], title: str = "Token"):
        self.token = token
        self.players = players
        super().__init__(parent, title, "520x640")
        b = self.body
        top = ctk.CTkFrame(b, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text="Name", font=ui_font("small", bold=True)).grid(row=0, column=0, sticky="w")
        self.name = ctk.CTkEntry(top, width=230)
        self.name.insert(0, token.get("name", ""))
        self.name.grid(row=1, column=0, sticky="w", padx=(0, 10))
        ctk.CTkLabel(top, text="Size", font=ui_font("small", bold=True)).grid(row=0, column=1, sticky="w")
        self.size = ctk.StringVar(value=_size_name(token.get("size", 1.0)))
        ctk.CTkOptionMenu(top, values=[n for n in SIZE_NAMES if n != "Small"] , variable=self.size, width=130
                          ).grid(row=1, column=1, sticky="w")

        hp = ctk.CTkFrame(b, fg_color="transparent")
        hp.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(hp, text="Hit points", font=ui_font("small", bold=True)).pack(side="left")
        self.hp = ctk.CTkEntry(hp, width=60)
        self.hp.pack(side="left", padx=6)
        ctk.CTkLabel(hp, text="of", font=ui_font("small")).pack(side="left")
        self.hp_max = ctk.CTkEntry(hp, width=60)
        self.hp_max.pack(side="left", padx=6)
        for entry, value in ((self.hp, token.get("hp")), (self.hp_max, token.get("hp_max"))):
            if value is not None:
                entry.insert(0, str(value))
        ctk.CTkLabel(hp, text="Sight (ft)", font=ui_font("small", bold=True)).pack(side="left", padx=(14, 0))
        self.vision = ctk.CTkEntry(hp, width=56, placeholder_text="any")
        self.vision.pack(side="left", padx=6)
        if token.get("vision"):
            self.vision.insert(0, f"{token['vision']:g}")
        row = ctk.CTkFrame(b, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(row, text="Height above the ground (ft)", font=ui_font("small", bold=True)).pack(side="left")
        self.height = ctk.CTkEntry(row, width=60, placeholder_text="0")
        self.height.pack(side="left", padx=6)
        if token.get("z"):
            self.height.insert(0, f"{token['z']:g}")
        HoverTooltip(self.height, "Flying or burrowing: negative is below the ground. On the map, Shift-drag a "
                                  "token up or down to change it.")
        HoverTooltip(self.vision, "How far this token sees with line of sight on (e.g. 60 for darkvision in a dark "
                                  "dungeon). Leave it empty to see as far as the walls allow.")

        ctk.CTkLabel(b, text="Colour", font=ui_font("small", bold=True), anchor="w").pack(fill="x", pady=(10, 0))
        colors = ctk.CTkFrame(b, fg_color="transparent")
        colors.pack(fill="x")
        self.color = token.get("color", T.DEFAULT_COLORS[0])
        self._color_buttons = {}
        for c in T.DEFAULT_COLORS:
            btn = ctk.CTkButton(colors, text="", width=26, height=26, corner_radius=13, fg_color=c, hover_color=c,
                                border_width=3, command=lambda c=c: self._pick_color(c))
            btn.pack(side="left", padx=2)
            self._color_buttons[c] = btn
        self._pick_color(self.color)

        who = ctk.CTkFrame(b, fg_color="transparent")
        who.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(who, text="Belongs to", font=ui_font("small", bold=True)).pack(side="left")
        self._owner_names = ["Nobody (DM)"] + [n for n, _ in players]
        current = token.get("owner_name") or ""
        if token.get("owner") and current and current not in self._owner_names:
            self._owner_names.append(current)                    # a player who isn't connected right now
        self.owner = ctk.StringVar(value=current if token.get("owner") else "Nobody (DM)")
        ctk.CTkOptionMenu(who, values=self._owner_names, variable=self.owner, width=170).pack(side="left", padx=8)
        HoverTooltip(who, "That player can move this token and see its hit points.")

        flags = ctk.CTkFrame(b, fg_color="transparent")
        flags.pack(fill="x", pady=(8, 0))
        self.hidden = ctk.BooleanVar(value=bool(token.get("hidden")))
        ctk.CTkCheckBox(flags, text="Hidden from players", variable=self.hidden).pack(side="left")
        self.show_name = ctk.BooleanVar(value=bool(token.get("show_name", True)))
        ctk.CTkCheckBox(flags, text="Show name", variable=self.show_name).pack(side="left", padx=12)

        ctk.CTkLabel(b, text="Conditions", font=ui_font("small", bold=True), anchor="w").pack(fill="x", pady=(10, 0))
        grid = ctk.CTkFrame(b, fg_color="transparent")
        grid.pack(fill="x")
        self.cond_vars: Dict[str, ctk.BooleanVar] = {}
        current = list(token.get("conditions") or [])
        names = CONDITIONS + COMMON_EFFECTS + [c for c in current if c not in CONDITIONS + COMMON_EFFECTS]
        for i, name in enumerate(names):
            var = ctk.BooleanVar(value=name in current)
            self.cond_vars[name] = var
            ctk.CTkCheckBox(grid, text=name, variable=var, width=120, checkbox_width=18, checkbox_height=18,
                            fg_color=T.condition_color(name), font=ui_font("small")).grid(
                row=i // 4, column=i % 4, sticky="w", pady=1)
        other = ctk.CTkFrame(b, fg_color="transparent")
        other.pack(fill="x", pady=(6, 0))
        ctk.CTkLabel(other, text="Other", font=ui_font("small")).pack(side="left")
        self.other = ctk.CTkEntry(other, placeholder_text="e.g. Hunter's Mark", width=200)
        self.other.pack(side="left", padx=6)
        self._buttons("Save")

    def _pick_color(self, color: str):
        self.color = color
        for c, btn in self._color_buttons.items():
            btn.configure(border_color="#FFFFFF" if c == color else c)

    def _accept(self):
        def number(entry):
            text = entry.get().strip()
            if not text:
                return None
            try:
                return int(float(text))
            except ValueError:
                return None
        conditions = [n for n, v in self.cond_vars.items() if v.get()]
        extra = self.other.get().strip()
        if extra and extra not in conditions:
            conditions.append(extra)
        owner_name = self.owner.get()
        owner, shown_name = "", ""
        for name, cid in self.players:
            if name == owner_name:
                owner, shown_name = cid, name
        if not owner and owner_name not in ("Nobody (DM)", "") and owner_name == self.token.get("owner_name"):
            owner, shown_name = self.token.get("owner", ""), owner_name
        self.result = {
            "name": self.name.get().strip() or "Token", "size": T.TOKEN_SIZES[self.size.get()],
            "hp": number(self.hp), "hp_max": number(self.hp_max), "color": self.color, "owner": owner,
            "owner_name": shown_name, "hidden": bool(self.hidden.get()), "show_name": bool(self.show_name.get()),
            "conditions": conditions, "vision": max(0, number(self.vision) or 0), "z": number(self.height) or 0,
        }
        if self.token.get("image"):
            self.result["image"] = self.token["image"]
        if owner:
            self.result["kind"] = "pc"
        self.destroy()


class PickDialog(_Dialog):
    """Pick one name from a long list, with a filter."""

    def __init__(self, parent, title: str, names: List[str]):
        self.names = sorted(set(names), key=str.lower)
        super().__init__(parent, title, "380x480")
        self.search = ctk.CTkEntry(self.body, placeholder_text="Type to filter")
        self.search.pack(fill="x")
        self.search.bind("<KeyRelease>", lambda _e: self._fill())
        self.search.bind("<Return>", lambda _e: self._accept())
        self.listbox = tk.Listbox(self.body, activestyle="none", borderwidth=0, highlightthickness=0,
                                  font=("TkDefaultFont", 11))
        self.listbox.pack(fill="both", expand=True, pady=8)
        self.listbox.bind("<Double-Button-1>", lambda _e: self._accept())
        self._buttons("Add")
        self._fill()
        self.after(80, self.search.focus_set)

    def _fill(self):
        q = self.search.get().strip().lower()
        self.listbox.delete(0, "end")
        for n in self.names:
            if not q or q in n.lower():
                self.listbox.insert("end", n)
        if self.listbox.size():
            self.listbox.selection_set(0)

    def _accept(self):
        sel = self.listbox.curselection()
        if sel:
            self.result = self.listbox.get(sel[0])
            self.destroy()


# --------------------------------------------------------------------------- helpers

def _unique(names: List[str]) -> List[str]:
    """Menu labels must differ: number repeated names."""
    seen: Dict[str, int] = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n} ({seen[n]})")
    return out


def _base_name(name: str) -> str:
    parts = name.rsplit(" ", 1)
    return parts[0] if len(parts) == 2 and parts[1].isdigit() else name


def _hex(color: str) -> str:
    return color if isinstance(color, str) and color.startswith("#") else "#1E1E1E"


def _content_picture(kind: str, name: str) -> Optional[str]:
    try:
        from content_images import get_image_store
        return get_image_store().path_for(kind, name)
    except Exception:
        return None
