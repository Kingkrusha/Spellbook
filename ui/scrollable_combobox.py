"""
A CTkComboBox whose dropdown is a real scrollable list instead of a native
OS menu.

CTkComboBox's dropdown is a plain ``tkinter.Menu`` (see customtkinter's
``DropdownMenu``). Long lists (armor types, subclasses, saving-throw
proficiency options, and anything backed by a growing collection) either get
clipped or fall back to tiny, easy-to-miss native scroll arrows with no
visible scrollbar and no mouse-wheel support - not a usable "scrollable"
control. ``ScrollableComboBox`` swaps the popup for a borderless
``CTkToplevel`` holding a ``CTkScrollableFrame`` of buttons (mouse wheel and
a real scrollbar work), with a type-to-filter box for long lists.

It's a drop-in replacement: same constructor, same ``.get()``/``.set()``/
``command=`` behavior, since only the popup mechanism (``_open_dropdown_menu``)
is overridden - everything else is inherited from ``CTkComboBox`` unchanged.
"""

import tkinter as tk

import customtkinter as ctk

from theme import get_theme_manager

# Below this many values, the popup skips the search box - typing a filter
# isn't worth the extra row when everything already fits on screen at once.
_SEARCH_BOX_THRESHOLD = 10
_MAX_VISIBLE_ROWS = 8
_ROW_HEIGHT = 28


class ScrollableComboBox(ctk.CTkComboBox):
    """CTkComboBox with a scrollable (and, for long lists, filterable) dropdown."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scrollable_popup = None
        self._popup_scroll_frame = None
        self._popup_search_var = None
        self._popup_rows = None

    def _open_dropdown_menu(self):
        if self._state == tk.DISABLED or not self._values:
            return
        if self._scrollable_popup is not None:
            self._close_scrollable_dropdown()
            return

        theme = get_theme_manager()
        popup = ctk.CTkToplevel(self)
        popup.overrideredirect(True)
        try:
            popup.attributes("-topmost", True)
        except Exception:
            pass

        show_search = len(self._values) >= _SEARCH_BOX_THRESHOLD
        visible_rows = min(len(self._values), _MAX_VISIBLE_ROWS)
        width = max(self.winfo_width(), 160)
        list_height = visible_rows * _ROW_HEIGHT + 8
        height = list_height + (36 if show_search else 0)
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 2
        popup.geometry(f"{width}x{height}+{x}+{y}")

        outer = ctk.CTkFrame(
            popup, fg_color=theme.get_current_color('bg_secondary'),
            border_width=1, border_color=theme.get_current_color('border'),
        )
        outer.pack(fill="both", expand=True)

        search_var = None
        if show_search:
            search_var = ctk.StringVar()
            search_entry = ctk.CTkEntry(
                outer, textvariable=search_var, placeholder_text="Type to filter...",
                height=26,
            )
            search_entry.pack(fill="x", padx=4, pady=(4, 2))
            search_entry.focus_set()

        scroll = ctk.CTkScrollableFrame(
            outer, fg_color="transparent", width=width - 8, height=list_height - 4,
        )
        scroll.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        # Exposed for tests/introspection - more reliable than walking the Tk
        # widget tree, since CTkScrollableFrame nests a canvas + inner frame
        # internally (see ui/classes_view.py's _toggle_filters for the exact
        # pack(before=<scrollable frame>) pitfall that comes from that nesting).
        self._popup_search_var = search_var
        self._popup_scroll_frame = scroll

        rows: list = []

        def build_rows(filter_text: str = ""):
            for child in scroll.winfo_children():
                child.destroy()
            rows.clear()
            needle = filter_text.strip().lower()
            matches = [v for v in self._values if needle in v.lower()] if needle else list(self._values)
            for value in matches:
                btn = ctk.CTkButton(
                    scroll, text=value, anchor="w", height=_ROW_HEIGHT - 4,
                    fg_color="transparent",
                    hover_color=theme.get_current_color('accent_primary'),
                    text_color=theme.get_current_color('text_primary'),
                    command=lambda v=value: self._pick_scrollable_value(v),
                )
                btn.pack(fill="x", pady=1)
                rows.append(btn)

        build_rows()
        self._popup_rows = rows
        if search_var is not None:
            search_var.trace_add("write", lambda *_a: build_rows(search_var.get()))

        popup.bind("<Escape>", lambda _e: self._close_scrollable_dropdown())
        popup.bind("<FocusOut>", self._on_popup_focus_out)
        self._scrollable_popup = popup
        popup.after(10, popup.focus_force)

    def _on_popup_focus_out(self, event=None):
        # A click on one of the row buttons (or the search entry) fires
        # FocusOut on the popup toplevel before the button's own command runs;
        # closing immediately would destroy the button out from under that
        # click. Defer the close one tick so the command fires first.
        self.after(150, self._close_if_unfocused)

    def _close_if_unfocused(self):
        if self._scrollable_popup is None:
            return
        try:
            focused = self.focus_get()
        except Exception:
            focused = None
        if focused is None or not self._is_within_popup(focused):
            self._close_scrollable_dropdown()

    def _is_within_popup(self, widget) -> bool:
        popup = self._scrollable_popup
        if popup is None:
            return False
        w = widget
        while w is not None:
            if w == popup:
                return True
            w = w.master
        return False

    def _pick_scrollable_value(self, value: str):
        self._close_scrollable_dropdown()
        self._dropdown_callback(value)

    def _close_scrollable_dropdown(self):
        popup = self._scrollable_popup
        self._scrollable_popup = None
        self._popup_scroll_frame = None
        self._popup_search_var = None
        self._popup_rows = None
        if popup is not None:
            try:
                popup.destroy()
            except Exception:
                pass

    def _clicked(self, event=None):
        if self._scrollable_popup is not None:
            self._close_scrollable_dropdown()
        elif self._state is not tk.DISABLED and len(self._values) > 0:
            self._open_dropdown_menu()

    def destroy(self):
        self._close_scrollable_dropdown()
        super().destroy()
