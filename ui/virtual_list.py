"""
Virtualized list panel: the base of the Spells, Feats, Lineages, Backgrounds, Equipment, Magic
Items and Monsters lists.

However many entries the collection has (the app is meant to be extended with user content, so
that can be tens of thousands), only the rows inside the viewport plus a small buffer exist as
widgets, and they are recycled: a row's slot is ``index % pool_size``, so scrolling by one entry
rebinds just the one row that came into view, and a row whose text, colour and selection state
did not change is not touched at all (every ``configure`` redraws a CustomTkinter canvas).

Scrolling is done here rather than by a scrollable frame holding a giant spacer. Windows cannot
position a child window further than ~32,767 pixels from its parent's origin, so once a list was
taller than that (about 740 entries) the rows deep in it were silently never drawn. The viewport
here is a plain frame; the rows are ``place``d at ``index * stride - offset`` (always within a
screenful), and a CTkScrollbar is driven by the virtual offset.

All positions are in CustomTkinter's *logical* units, the ones ``place()`` and widget heights are
given in: on a display scaled to 125% or 150% physical pixels differ, and mixing the two puts the
visible rows in the wrong place.

Subclasses set ``TITLE`` / ``NOUN`` and override ``row_text`` (and optionally ``row_text_color``,
``KEY``, the function that decides whether two names are the same entry, and the row look).
Items need a ``name`` attribute.

A page can switch on *bulk actions* (``enable_bulk_actions``): a "Select" button in the header turns the rows into
tick-boxes and shows a bar of buttons, each of which gets the ticked entries. The ticks are remembered by entry
name, so they survive a refilter, and an entry that a filter hides stays ticked.
"""

from ui.theme_listener import ThemeListenerMixin
import tkinter as tk
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.platform_compat import bind_right_click


class VirtualListPanel(ThemeListenerMixin, ctk.CTkFrame):
    """A scrollable, selectable list that stays fast and correct with any number of entries."""

    TITLE = "Items"
    NOUN = "item"            # "1 item", "2 items"
    ROW_HEIGHT = 40
    ROW_GAP = 4              # space between rows (half above, half below each)
    BUFFER_ROWS = 6          # rows kept ready above and below the viewport
    ROW_RADIUS = 8
    WHEEL_STEP = 90          # logical pixels per mouse-wheel notch
    SCROLL_UNIT = 30         # logical pixels per scrollbar "unit"
    REBASE_ROWS = 8          # the rows' frame is re-based every this many rows of scrolling
    TICKED = "\u2611  "       # a row's tick-box in "Select" mode
    UNTICKED = "\u2610  "

    # Decides whether a name from outside refers to the same entry as an item. Versioned
    # collections (2024 / Legacy) match with legacy_pair_key so one row stands for all versions.
    KEY = staticmethod(lambda name: name.lower())

    def __init__(self, parent, on_select: Callable[[Optional[object]], None],
                 on_right_click: Optional[Callable[[object, int, int], None]] = None):
        super().__init__(parent, corner_radius=10)
        self.on_select = on_select
        self.on_right_click = on_right_click  # (item, x_root, y_root)

        self.theme = get_theme_manager()
        self._items: List[object] = []
        self._selected_index: Optional[int] = None
        self._select_when_listed: Optional[tuple] = None   # (name, version) for the next set_items
        self._multi = False                                 # "Select" mode: rows are tick-boxes
        self._checked: Dict[str, object] = {}               # KEY(name) -> the ticked entry
        self._bulk_actions: List[Tuple[str, Callable[[list], None]]] = []
        self._select_btn: Optional[ctk.CTkButton] = None
        self._bulk_bar: Optional[ctk.CTkFrame] = None
        self._bulk_buttons: List[ctk.CTkButton] = []
        self._bulk_count: Optional[ctk.CTkLabel] = None
        self._pool: List[ctk.CTkButton] = []
        self._render_job: Optional[str] = None
        self._offset: float = 0.0     # logical pixels scrolled
        self._base: int = 0           # index of the item at the top of the rows' frame
        self._content_geometry = None  # y the rows' frame was last placed at

        self.configure(fg_color=self.panel_color())
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)

    # ------------------------------------------------------------------ hooks

    def row_text(self, item) -> str:
        """The text of an item's row."""
        return ("* " if getattr(item, "is_custom", False) else "") + item.name

    def row_text_color(self, item):
        """The text colour of an item's row (a theme colour unless overridden)."""
        return self.theme.get_current_color('text_primary')

    def panel_color(self):
        return self.theme.get_current_color('bg_primary')

    def list_color(self):
        """Background of the area the rows sit in."""
        return "transparent"

    def row_color(self, selected: bool):
        """A row's background."""
        return self.theme.get_current_color('accent_primary') if selected else "transparent"

    # ------------------------------------------------------------------ setup

    @property
    def _stride(self) -> int:
        return self.ROW_HEIGHT + self.ROW_GAP

    def _create_widgets(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(15, 10))
        ctk.CTkLabel(header, text=self.TITLE, font=ui_font("heading", bold=True)).pack(side="left")
        self.count_label = ctk.CTkLabel(header, text=self._count_text(0), font=ui_font("body"),
                                        text_color=self.theme.get_text_secondary())
        self.count_label.pack(side="right")
        self._header = header

        body = self._body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.scrollbar = ctk.CTkScrollbar(body, orientation="vertical", command=self._on_scrollbar)
        self.scrollbar.pack(side="right", fill="y", padx=(4, 0))

        # The rows are placed inside this plain frame
        self.viewport = ctk.CTkFrame(body, fg_color=self.list_color(), corner_radius=0)
        self.viewport.pack(side="left", fill="both", expand=True)
        self.viewport.bind("<Configure>", lambda _e: self._on_viewport_resized(), add="+")

        # The rows live in this frame. Scrolling moves the one frame (a single window move);
        # the rows themselves only move when the frame is re-based, every few rows. Its own
        # coordinates therefore stay within a few thousand pixels however long the list is.
        self._content = ctk.CTkFrame(self.viewport, fg_color="transparent", corner_radius=0,
                                     border_width=0, height=1)
        self._content.place(x=0, y=0, relwidth=1.0)
        self._frame_height = 1

        for widget in (self.viewport, self._content, self.scrollbar):
            self._bind_wheel(widget)

    def _bind_wheel(self, widget):
        widget.bind("<MouseWheel>", self._on_wheel, add="+")
        widget.bind("<Button-4>", self._on_wheel, add="+")   # X11
        widget.bind("<Button-5>", self._on_wheel, add="+")

    def _count_text(self, n: int) -> str:
        return f"{n} {self.NOUN}{'' if n == 1 else 's'}"

    # ------------------------------------------------------------- geometry

    def _scale(self) -> float:
        try:
            return self.viewport._get_widget_scaling() or 1.0
        except Exception:
            return 1.0

    def _viewport_height(self) -> float:
        """Viewport height in logical units (winfo_height is physical pixels)."""
        try:
            return self.viewport.winfo_height() / self._scale()
        except tk.TclError:
            return 0.0

    def _content_height(self) -> float:
        return len(self._items) * self._stride

    def _max_offset(self) -> float:
        return max(0.0, self._content_height() - self._viewport_height())

    def _clamp_offset(self):
        self._offset = max(0.0, min(self._offset, self._max_offset()))

    def _update_scrollbar(self):
        total = self._content_height()
        height = self._viewport_height()
        try:
            if total <= 0 or height <= 1 or total <= height:
                self.scrollbar.set(0.0, 1.0)
            else:
                self.scrollbar.set(self._offset / total, min(1.0, (self._offset + height) / total))
        except Exception:
            pass

    # -------------------------------------------------------------- scrolling

    def _on_viewport_resized(self):
        self._clamp_offset()
        self._request_render()

    def _on_scrollbar(self, *args):
        """CTkScrollbar commands: ('moveto', fraction) or ('scroll', n, 'units'|'pages')."""
        total = self._content_height()
        if not args or total <= 0:
            return
        if args[0] == "moveto":
            self._offset = float(args[1]) * total
        elif args[0] == "scroll":
            amount = float(args[1])
            step = self._viewport_height() * 0.9 if len(args) > 2 and args[2] == "pages" else self.SCROLL_UNIT
            self._offset += amount * step
        self._clamp_offset()
        self._request_render()

    def _on_wheel(self, event):
        if getattr(event, "num", 0) == 4:
            notches = 1.0
        elif getattr(event, "num", 0) == 5:
            notches = -1.0
        else:
            delta = float(getattr(event, "delta", 0) or 0)
            notches = delta / 120.0 if abs(delta) >= 120 else (1.0 if delta > 0 else -1.0 if delta < 0 else 0.0)
        if notches:
            self._offset -= notches * self.WHEEL_STEP
            self._clamp_offset()
            self._request_render()
        return "break"

    # -------------------------------------------------------------- rendering

    def _request_render(self):
        """Render once, on the next idle (collapses the bursts scrolling and resizing produce)."""
        if self._render_job is not None:
            return
        self._render_job = self.after_idle(self._render)

    def _visible_range(self):
        """(first, last) item indices that should have a row right now."""
        n = len(self._items)
        if n == 0:
            return 0, 0
        height = self._viewport_height()
        if height <= 1:   # not laid out yet; a <Configure> follows with the real size
            return 0, min(n, self.BUFFER_ROWS * 2 + 8)
        first = max(0, int(self._offset // self._stride) - self.BUFFER_ROWS)
        last = int((self._offset + height) // self._stride) + 1 + self.BUFFER_ROWS
        return first, min(n, last)

    def _render(self):
        self._render_job = None
        try:
            if not self.winfo_exists():
                return
            self._render_visible()
        except tk.TclError:
            pass

    def _render_visible(self):
        self._clamp_offset()
        first, last = self._visible_range()
        stride = self._stride

        # Re-base the rows' frame when the scroll has moved a few rows away from it
        base = (first // self.REBASE_ROWS) * self.REBASE_ROWS
        if base != self._base:
            self._base = base
            for row in self._pool:
                row._vl_y = None            # their position inside the frame changes
        # (rows needed from the frame's top down to the last one shown)
        count = max(0, last - first)
        self._ensure_pool(count)
        size = max(1, len(self._pool))

        content_y = int(round(self._base * stride - self._offset))
        needed = (last - self._base) * stride + stride
        if needed > self._frame_height or self._frame_height > needed * 2 + 600:
            # Grown in steps (and rarely shrunk): setting the height redraws the frame
            self._frame_height = max(1, ((needed + 255) // 256) * 256)
            self._content.configure(height=self._frame_height)
        if self._content_geometry != content_y:
            self._content.place(x=0, y=content_y, relwidth=1.0)
            self._content_geometry = content_y

        in_use = set()
        for index in range(first, last):
            slot = index % size          # stable: scrolling only rebinds rows that changed index
            row = self._pool[slot]
            in_use.add(slot)
            self._bind_row(row, index)
            y = (index - self._base) * stride + self.ROW_GAP // 2
            if row._vl_y != y:
                row.place(x=0, y=y, relwidth=1.0)
                row._vl_y = y
        for slot, row in enumerate(self._pool):
            if slot not in in_use and row._vl_index != -1:
                row.place_forget()
                row._vl_index = -1
                row._vl_y = None
                row._vl_state = None
        self._update_scrollbar()

    def _ensure_pool(self, count: int):
        while len(self._pool) < count:
            row = ctk.CTkButton(
                self._content, text="", anchor="w",
                height=self.ROW_HEIGHT, corner_radius=self.ROW_RADIUS, border_width=0,
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                # looked up now, not cached: a text-size change in Settings replaces the font
                # objects, and a row created later must not come out in the old size
                font=ui_font("body", 13),
            )
            row._vl_index = -1      # which item this pooled row currently shows
            row._vl_y = None        # where it is placed
            row._vl_state = None    # (text, colour, selected) it was last configured with
            row.configure(command=lambda r=row: self._on_row_click(r._vl_index))
            bind_right_click(row, self._on_row_right_click)
            self._bind_wheel(row)
            for child in row.winfo_children():
                try:
                    bind_right_click(child, self._on_row_right_click)
                    self._bind_wheel(child)
                except Exception:
                    pass
            self._pool.append(row)
            # The pool grew, so the slot of every index changed: everything rebinds on this render
            for other in self._pool[:-1]:
                other._vl_state = None

    def _bind_row(self, row, index: int):
        """Point a pooled row at item ``index`` (touching the widget only if something changed)."""
        item = self._items[index]
        selected = index == self._selected_index
        ticked = self._multi and self.KEY(item.name) in self._checked
        state = (self.row_text(item), self.row_text_color(item), selected, ticked if self._multi else None)
        row._vl_index = index
        if row._vl_state == state:
            return
        row._vl_state = state
        text = state[0] if not self._multi else (self.TICKED if ticked else self.UNTICKED) + state[0]
        row.configure(text=text, text_color=state[1], fg_color=self.row_color(selected))

    # ------------------------------------------------------------ interaction

    def _on_row_click(self, index: int):
        if 0 <= index < len(self._items):
            if self._multi:
                self._toggle_checked(self._items[index])
            self._select(index, scroll=False)

    def _on_row_right_click(self, event):
        if not event or not self.on_right_click:
            return
        widget = event.widget   # the row or one of its internal canvas / label children
        while widget is not None and not hasattr(widget, "_vl_index"):
            widget = getattr(widget, "master", None)
        if widget is not None and 0 <= widget._vl_index < len(self._items):
            self.on_right_click(self._items[widget._vl_index], event.x_root, event.y_root)

    def _select(self, index: int, scroll: bool = True):
        self._selected_index = index
        if scroll:
            self._ensure_visible(index)
        self._render_visible()   # cheap: only the old and new selected rows actually change
        self.on_select(self._items[index])

    def _ensure_visible(self, index: int):
        """Scroll so the row for ``index`` is inside the viewport."""
        height = self._viewport_height()
        row_top = index * self._stride
        row_bottom = row_top + self._stride
        if height <= 1:       # not laid out yet: put the row at the top once it is
            self._offset = row_top
        elif row_top < self._offset:
            self._offset = row_top
        elif row_bottom > self._offset + height:
            self._offset = row_bottom - height
        self._clamp_offset()

    # ------------------------------------------------------------- bulk actions

    def enable_bulk_actions(self, actions: Sequence[Tuple[str, Callable[[list], None]]]):
        """Add the "Select" button and the action bar. ``actions`` is ``[(button text, callback(entries)), ...]``;
        a callback gets the ticked entries (and is only enabled while something is ticked)."""
        self._bulk_actions = list(actions)
        self._select_btn = ctk.CTkButton(
            self._header, text="Select", width=64, height=26, font=ui_font("small"),
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            command=lambda: self.set_multi_select(not self._multi))
        self._select_btn.pack(side="right", padx=(0, 10))

        bar = self._bulk_bar = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_secondary'),
                                            corner_radius=8)
        top = ctk.CTkFrame(bar, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 4))
        self._bulk_count = ctk.CTkLabel(top, text="", font=ui_font("small", bold=True))
        self._bulk_count.pack(side="left")
        for text, command in (("None", self.clear_checked), ("All shown", self.check_all)):
            ctk.CTkButton(
                top, text=text, width=64, height=24, font=ui_font("small"),
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                command=command).pack(side="right", padx=(4, 0))

        grid = ctk.CTkFrame(bar, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=(0, 8))
        self._bulk_buttons = []
        for i, (text, callback) in enumerate(self._bulk_actions):
            button = ctk.CTkButton(
                grid, text=text, height=28, font=ui_font("small"),
                fg_color=self.theme.get_current_color('accent_primary'),
                hover_color=self.theme.get_current_color('accent_hover'),
                command=lambda cb=callback: cb(self.checked_items()))
            button.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
            grid.grid_columnconfigure(i % 2, weight=1, uniform="bulk")
            self._bulk_buttons.append(button)
        self._update_bulk_bar()

    @property
    def multi_select(self) -> bool:
        return self._multi

    def set_multi_select(self, on: bool):
        """Turn "Select" mode on or off (turning it off un-ticks everything)."""
        if self._bulk_bar is None or on == self._multi:
            return
        self._multi = on
        if on:
            self._bulk_bar.pack(side="bottom", fill="x", padx=10, pady=(0, 10), before=self._body)
        else:
            self._bulk_bar.pack_forget()
            self._checked.clear()
        self._select_btn.configure(
            text="Done" if on else "Select",
            fg_color=self.theme.get_current_color('accent_primary' if on else 'button_normal'))
        self._rebind_rows()
        self._update_bulk_bar()

    def checked_items(self) -> list:
        """The ticked entries (including ones a filter is hiding right now)."""
        return list(self._checked.values())

    def checked_count(self) -> int:
        return len(self._checked)

    def is_checked(self, item) -> bool:
        return self.KEY(item.name) in self._checked

    def check_all(self):
        """Tick every entry in the list as it is filtered now (the ones ticked earlier stay ticked)."""
        if not self._multi:
            return
        for item in self._items:
            self._checked[self.KEY(item.name)] = item
        self._rebind_rows()
        self._update_bulk_bar()

    def clear_checked(self):
        self._checked.clear()
        self._rebind_rows()
        self._update_bulk_bar()

    def _toggle_checked(self, item):
        key = self.KEY(item.name)
        if key in self._checked:
            del self._checked[key]
        else:
            self._checked[key] = item
        self._rebind_rows()
        self._update_bulk_bar()

    def _rebind_rows(self):
        for row in self._pool:
            row._vl_state = None
        self._request_render()

    def _update_bulk_bar(self):
        if self._bulk_bar is None:
            return
        n = len(self._checked)
        self._bulk_count.configure(text=f"{n} selected")
        for button in self._bulk_buttons:
            button.configure(state="normal" if n else "disabled")

    # -------------------------------------------------------------- public API

    def _find(self, name: Optional[str]) -> Optional[int]:
        if not name:
            return None
        key = self.KEY(name)
        for i, item in enumerate(self._items):
            if self.KEY(item.name) == key:
                return i
        return None

    def set_items(self, items: List[object], reset_scroll: bool = True,
                  keep: Optional[str] = None, keep_current: bool = True, notify: bool = False):
        """Show ``items``.

        The selection follows the entry named ``keep`` (default: whichever is selected now, unless
        ``keep_current`` is False). With ``notify`` the selection callback fires for it, which is
        how a list that was reloaded re-shows its entry in the detail panel."""
        name = keep
        if name is None and keep_current and self._selected_index is not None \
                and self._selected_index < len(self._items):
            name = self._items[self._selected_index].name

        self._items = items
        self._selected_index = self._find(name)
        self.count_label.configure(text=self._count_text(len(items)))
        if self._checked:                       # the ticked entries are the new objects where the list has them
            for item in items:
                key = self.KEY(item.name)
                if key in self._checked:
                    self._checked[key] = item
            self._update_bulk_bar()
        for row in self._pool:       # every row may now show a different item
            row._vl_state = None
        if reset_scroll:
            self._offset = 0.0
        self._clamp_offset()
        self._request_render()
        if notify and self._selected_index is not None:
            self._select(self._selected_index)
        if self._select_when_listed is not None:
            wanted, self._select_when_listed = self._select_when_listed, None
            self.select_by_name(*wanted)

    def select_by_name(self, name: str, version: Optional[object] = None) -> bool:
        """Select an entry by name and scroll it into view. Returns True if it exists.

        ``version`` is the exact version to show in that entry (versioned collections)."""
        index = self._find(name)
        if index is None:
            return False
        if version is not None and version is not self._items[index]:
            self._items[index] = version
        self._select(index)
        return True

    def select_when_listed(self, name: str, version: Optional[object] = None):
        """Select an entry once the list next changes (a no-op if it is not in the new list).

        For a page that has just added or edited an entry: it reloads its list, but the refilter that puts
        the new or changed object in it runs a moment later (filter changes are debounced). Selecting at
        once would find nothing (a new entry) or select, and show, the old object (an edited one)."""
        self._select_when_listed = (name, version)

    def get_selected(self) -> Optional[object]:
        if self._selected_index is not None and self._selected_index < len(self._items):
            return self._items[self._selected_index]
        return None

    def replace_selected(self, item):
        """The detail panel switched the selected entry to another version of it."""
        if self._selected_index is not None and self._selected_index < len(self._items):
            self._items[self._selected_index] = item
            for row in self._pool:
                row._vl_state = None
            self._request_render()

    def clear_selection(self):
        self._selected_index = None
        self._request_render()

    def scroll_to_top(self):
        self._offset = 0.0
        self._request_render()

    # ------------------------------------------------------------------ theme

    def _on_theme_changed(self):
        try:
            self.configure(fg_color=self.panel_color())
            self.viewport.configure(fg_color=self.list_color())
            self.count_label.configure(text_color=self.theme.get_text_secondary())
            for row in self._pool:
                row._vl_state = None
                row.configure(hover_color=self.theme.get_current_color('button_hover'))
            if self._bulk_bar is not None:
                self._bulk_bar.configure(fg_color=self.theme.get_current_color('bg_secondary'))
                self._select_btn.configure(
                    fg_color=self.theme.get_current_color('accent_primary' if self._multi else 'button_normal'),
                    hover_color=self.theme.get_current_color('button_hover'),
                    text_color=self.theme.get_current_color('text_primary'))
                for button in self._bulk_buttons:
                    button.configure(fg_color=self.theme.get_current_color('accent_primary'),
                                     hover_color=self.theme.get_current_color('accent_hover'))
            self._request_render()
        except Exception:
            pass
