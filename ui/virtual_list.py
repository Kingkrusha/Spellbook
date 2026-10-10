"""
Virtualized list panel: the base of the Feats, Lineages, Backgrounds, Equipment, Magic Items
and Monsters lists.

However many entries the collection has (the app is meant to be extended with user content, so
that can be thousands), only the rows inside the viewport plus a small buffer exist as widgets.
The rest of the list is a single spacer frame whose height gives the scrollbar its range. Rows
are recycled: a row's slot is ``index % pool_size``, so scrolling by one entry rebinds just the
one row that came into view instead of every row (and a row whose text, colour and selection
state did not change is not touched at all - every ``configure`` redraws a CustomTkinter canvas).

Subclasses set ``TITLE`` / ``NOUN`` and override ``row_text`` (and optionally ``row_text_color``
and ``KEY``, the function that decides whether two names are the same entry). Items need a
``name`` attribute.
"""

import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.platform_compat import bind_right_click


class VirtualListPanel(ctk.CTkFrame):
    """A scrollable, selectable list that stays fast with any number of entries."""

    TITLE = "Items"
    NOUN = "item"            # "1 item", "2 items"
    ROW_HEIGHT = 40
    ROW_GAP = 4              # space between rows (half above, half below each)
    BUFFER_ROWS = 6          # rows kept ready above and below the viewport
    ROW_RADIUS = 8

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
        self._pool: List[ctk.CTkButton] = []
        self._render_job: Optional[str] = None
        self._font = ui_font("body", 13)

        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._create_widgets()
        self._install_scroll_hooks()
        self.theme.add_listener(self._on_theme_changed)

    # ------------------------------------------------------------------ hooks

    def row_text(self, item) -> str:
        """The text of an item's row."""
        return ("* " if getattr(item, "is_custom", False) else "") + item.name

    def row_text_color(self, item):
        """The text colour of an item's row (a theme colour unless overridden)."""
        return self.theme.get_current_color('text_primary')

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

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Stands in for the whole list so the scrollbar has the right range
        self._spacer = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", height=1)
        self._spacer.pack(fill="x")
        try:
            self._spacer.pack_propagate(False)
        except Exception:
            pass

    def _install_scroll_hooks(self):
        """Re-render the visible window whenever the canvas scrolls or is resized."""
        try:
            canvas = self.scroll_frame._parent_canvas
            scrollbar = self.scroll_frame._scrollbar
        except AttributeError:
            return

        def on_yscroll(first, last):
            try:
                scrollbar.set(first, last)
            except Exception:
                pass
            self._request_render()

        canvas.configure(yscrollcommand=on_yscroll)
        canvas.bind("<Configure>", lambda _e: self._request_render(), add="+")

    def _count_text(self, n: int) -> str:
        return f"{n} {self.NOUN}{'' if n == 1 else 's'}"

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
        try:
            canvas = self.scroll_frame._parent_canvas
            top = canvas.canvasy(0)
            viewport = canvas.winfo_height()
        except (AttributeError, tk.TclError):
            return 0, min(n, self.BUFFER_ROWS * 2 + 8)
        if viewport <= 1:   # not laid out yet; a <Configure> follows with the real size
            return 0, min(n, self.BUFFER_ROWS * 2 + 8)
        first = max(0, int(top // self._stride) - self.BUFFER_ROWS)
        last = int((top + viewport) // self._stride) + 1 + self.BUFFER_ROWS
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
        first, last = self._visible_range()
        count = last - first
        self._ensure_pool(count)
        size = max(1, len(self._pool))

        in_use = set()
        for index in range(first, last):
            slot = index % size          # stable: scrolling only rebinds rows that changed index
            row = self._pool[slot]
            in_use.add(slot)
            self._bind_row(row, index)
            y = index * self._stride + self.ROW_GAP // 2
            if row._y != y:
                row.place(x=0, y=y, relwidth=1.0)
                row._y = y
        for slot, row in enumerate(self._pool):
            if slot not in in_use and row._index != -1:
                row.place_forget()
                row._index = -1
                row._y = None
                row._state = None

    def _ensure_pool(self, count: int):
        while len(self._pool) < count:
            row = ctk.CTkButton(
                self.scroll_frame, text="", anchor="w",
                height=self.ROW_HEIGHT, corner_radius=self.ROW_RADIUS,
                fg_color="transparent",
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                font=self._font,
            )
            row._index = -1      # which item this pooled row currently shows
            row._y = None        # where it is placed
            row._state = None    # (text, colour, selected) it was last configured with
            row.configure(command=lambda r=row: self._on_row_click(r._index))
            bind_right_click(row, self._on_row_right_click)
            for child in row.winfo_children():
                try:
                    bind_right_click(child, self._on_row_right_click)
                except Exception:
                    pass
            self._pool.append(row)
            # The pool grew, so the slot of every index changed: everything rebinds on this render
            for other in self._pool[:-1]:
                other._state = None

    def _bind_row(self, row, index: int):
        """Point a pooled row at item ``index`` (touching the widget only if something changed)."""
        item = self._items[index]
        selected = index == self._selected_index
        state = (self.row_text(item), self.row_text_color(item), selected)
        row._index = index
        if row._state == state:
            return
        row._state = state
        row.configure(
            text=state[0], text_color=state[1],
            fg_color=(self.theme.get_current_color('accent_primary') if selected else "transparent"),
        )

    # ------------------------------------------------------------ interaction

    def _on_row_click(self, index: int):
        if 0 <= index < len(self._items):
            self._select(index, scroll=False)

    def _on_row_right_click(self, event):
        if not event or not self.on_right_click:
            return
        widget = event.widget   # the row or one of its internal canvas / label children
        while widget is not None and not hasattr(widget, "_index"):
            widget = getattr(widget, "master", None)
        if widget is not None and 0 <= widget._index < len(self._items):
            self.on_right_click(self._items[widget._index], event.x_root, event.y_root)

    def _select(self, index: int, scroll: bool = True):
        self._selected_index = index
        if scroll:
            self._ensure_visible(index)
        self._render_visible()   # cheap: only the old and new selected rows actually change
        self.on_select(self._items[index])

    def _ensure_visible(self, index: int):
        """Scroll so the row for ``index`` is inside the viewport."""
        try:
            canvas = self.scroll_frame._parent_canvas
            canvas.update_idletasks()   # the spacer's new height must reach the scroll region
            top = canvas.canvasy(0)
            viewport = canvas.winfo_height()
        except (AttributeError, tk.TclError):
            return
        row_top = index * self._stride
        row_bottom = row_top + self._stride
        if row_top < top:
            new_top = row_top
        elif row_bottom > top + viewport:
            new_top = row_bottom - viewport
        else:
            return
        total = len(self._items) * self._stride
        if total > 0:
            try:
                canvas.yview_moveto(max(0.0, min(1.0, new_top / total)))
            except tk.TclError:
                pass

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
        try:
            self._spacer.configure(height=max(1, len(items) * self._stride))
        except Exception:
            pass
        for row in self._pool:       # every row may now show a different item
            row._state = None
        if reset_scroll:
            try:
                self.scroll_frame._parent_canvas.yview_moveto(0)
            except Exception:
                pass
        self._request_render()
        if notify and self._selected_index is not None:
            self._select(self._selected_index)

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

    def get_selected(self) -> Optional[object]:
        if self._selected_index is not None and self._selected_index < len(self._items):
            return self._items[self._selected_index]
        return None

    def replace_selected(self, item):
        """The detail panel switched the selected entry to another version of it."""
        if self._selected_index is not None and self._selected_index < len(self._items):
            self._items[self._selected_index] = item
            self._request_render()

    def clear_selection(self):
        self._selected_index = None
        self._request_render()

    def scroll_to_top(self):
        try:
            self.scroll_frame._parent_canvas.yview_moveto(0)
        except (AttributeError, tk.TclError):
            pass
        self._request_render()

    # ------------------------------------------------------------------ theme

    def _on_theme_changed(self):
        try:
            self.configure(fg_color=self.theme.get_current_color('bg_primary'))
            self.count_label.configure(text_color=self.theme.get_text_secondary())
            for row in self._pool:
                row._state = None
                row.configure(hover_color=self.theme.get_current_color('button_hover'))
            self._request_render()
        except Exception:
            pass

    def destroy(self):
        try:
            self.theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()
