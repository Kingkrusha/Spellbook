"""
What each keyboard shortcut does (see hotkeys.py for the list and the binding).

``build_handlers(main_window)`` returns action id -> function for the
HotkeyManager. A function returns False when the shortcut does not apply
where the user is (Ctrl+B outside a description editor), so the key keeps its
normal meaning there.
"""

from __future__ import annotations

import weakref
from typing import Callable, Dict, Optional

import customtkinter as ctk

from typography import ui_font

# Rich text editors, by the Tk path of their text box (filled in by RichTextEditor)
_RICH_EDITORS: "weakref.WeakValueDictionary[str, object]" = weakref.WeakValueDictionary()

COLLECTION_PAGES = ("spells", "feats", "lineages", "backgrounds", "classes",
                    "equipment", "magic_items", "monsters", "rules")
TOOL_PAGES = ("session", "initiative", "dice_analyzer", "matchup", "random_tables", "calendar", "pdf_library", "music", "tabletop")
LEGACY_CYCLE = [
    ("show_all", "Show All Content"),
    ("show_unupdated", "Show Unupdated"),
    ("no_legacy", "No Legacy Content"),
    ("legacy_only", "Legacy Only"),
]


def register_rich_editor(text_widget, editor):
    """Let the formatting shortcuts find ``editor`` when its text box has focus."""
    inner = getattr(text_widget, "_textbox", text_widget)
    try:
        _RICH_EDITORS[str(inner)] = editor
    except TypeError:
        pass


def focused_rich_editor(root):
    try:
        widget = root.focus_get()
    except Exception:
        return None
    return _RICH_EDITORS.get(str(widget)) if widget is not None else None


# ---------------------------------------------------------------------------


def _regular_tab(mw) -> str:
    """The tab a page shortcut should change: the current one, unless that is Settings."""
    tab_id = mw._current_tab_id
    info = mw._tab_views.get(tab_id) if tab_id else None
    if info is not None and info.get('type') != 'settings':
        return tab_id
    last = mw._last_regular_tab_id
    if last in mw._tab_views:
        mw.tab_bar.select_tab(last)
        return last
    return mw._open_page_in_new_tab("home")


def visible_page(mw):
    """The page on screen in the current tab (a collection page if one is open)."""
    info = mw._tab_views.get(mw._current_tab_id) or {}
    if info.get('type') == 'collections' and info.get('current_collection'):
        return info.get('sub_view'), info.get('current_collection')
    # (a lazily built page such as Settings is a LazyView, which passes attributes through)
    return info.get('view'), info.get('type')


def _find_search_entry(view):
    """The search box of a page: its ``search_entry``, or the entry tied to its ``search_var``."""
    entry = getattr(view, 'search_entry', None)
    if entry is not None:
        return entry
    bar = getattr(view, 'search_bar', None)
    if bar is not None and getattr(bar, 'search_entry', None) is not None:
        return bar.search_entry
    var = getattr(view, 'search_var', None)
    if var is None:
        return None
    stack = [view]
    while stack:
        widget = stack.pop()
        if isinstance(widget, ctk.CTkEntry) and getattr(widget, '_textvariable', None) is var:
            return widget
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
    return None


def _focus_entry(entry) -> bool:
    if entry is None:
        return False
    try:
        entry.focus_set()
        inner = getattr(entry, '_entry', None)
        if inner is not None:
            inner.select_range(0, 'end')
            inner.icursor('end')
        return True
    except Exception:
        return False


def toast(mw, text: str, ms: int = 1600):
    """A short message at the bottom of the window."""
    old = getattr(mw, '_hotkey_toast', None)
    if old is not None:
        try:
            old.destroy()
        except Exception:
            pass
    from theme import get_theme_manager
    theme = get_theme_manager()
    label = ctk.CTkLabel(mw, text=text, font=ui_font("body"), corner_radius=8,
                         fg_color=theme.get_current_color('bg_secondary'),
                         text_color=theme.get_current_color('text_primary'))
    label.place(relx=0.5, rely=1.0, anchor="s", y=-24)
    label.lift()
    mw._hotkey_toast = label

    def remove():
        try:
            label.destroy()
        except Exception:
            pass
    mw.after(ms, remove)


# ---------------------------------------------------------------------------


def build_handlers(mw) -> Dict[str, Callable[[], Optional[bool]]]:
    tab_bar = mw.tab_bar
    handlers: Dict[str, Callable[[], Optional[bool]]] = {}

    regular_tabs = tab_bar.get_tab_ids  # (the pinned Settings tab is not among them)

    # -- tabs
    handlers["tab.new"] = lambda: mw._on_new_tab_requested()

    def close_tab():
        tab = tab_bar.get_active_tab()
        if tab is None or not tab.is_closable:
            return False
        tab_bar._on_tab_close(tab)
    handlers["tab.close"] = close_tab

    def step(delta):
        def go():
            ids = tab_bar.get_tab_ids()
            if not ids:
                return False
            current = mw._current_tab_id
            i = ids.index(current) if current in ids else 0
            tab_bar.select_tab(ids[(i + delta) % len(ids)])
        return go
    handlers["tab.next"] = step(1)
    handlers["tab.previous"] = step(-1)

    def duplicate():
        if mw._current_tab_id is None:
            return False
        mw._duplicate_tab(mw._current_tab_id)
    handlers["tab.duplicate"] = duplicate

    def go_to(n):
        def go():
            ids = regular_tabs()
            if not ids:
                return False
            tab_bar.select_tab(ids[-1] if n is None else ids[min(n, len(ids)) - 1])
        return go
    for n in range(1, 9):
        handlers[f"tab.go{n}"] = go_to(n)
    handlers["tab.last"] = go_to(None)

    # -- pages
    def page(page_type):
        def go():
            mw._navigate_tab(_regular_tab(mw), page_type)
        return go
    for page_type in ("home", "collections", "characters", "game_tools") + TOOL_PAGES:
        handlers[f"page.{page_type}"] = page(page_type)

    def collection(key):
        def go():
            tab_id = _regular_tab(mw)
            info = mw._tab_views.get(tab_id) or {}
            if info.get('type') != 'collections':
                mw._navigate_tab(tab_id, "collections")
            mw._navigate_to_collection_in_tab(tab_id, key)
        return go
    for key in COLLECTION_PAGES:
        handlers[f"page.{key}"] = collection(key)

    def settings():
        tab = next((t for t in tab_bar._tabs if t.tab_type == "settings"), None)
        if tab is None:
            return False
        tab_bar.select_tab(tab.tab_id)
    handlers["page.settings"] = settings

    # -- music (works from any page while something plays)
    def music(name):
        def go():
            import music_player
            player = music_player.peek_player()
            if player is None or player.status()["track"] is None:
                return False
            getattr(player, name)()
        return go
    for name in ("toggle_pause", "next", "previous", "stop"):
        handlers[f"music.{name}"] = music(name)

    # -- help
    handlers["help.tour"] = lambda: mw.start_tutorial()
    handlers["help.feedback"] = lambda: mw.open_feedback()

    # -- this page
    def refresh():
        view, kind = visible_page(mw)
        if view is None:
            return False
        if kind == "spells" and hasattr(view, "reload"):
            view.reload()
        elif kind == "classes" and hasattr(view, "_populate_class_list"):
            view._populate_class_list()
        elif kind == "settings" and hasattr(view, "refresh_from_settings"):
            view.refresh_from_settings()
        elif hasattr(view, "refresh"):
            view.refresh()
        else:
            return False
        toast(mw, "Page refreshed")
    handlers["view.refresh"] = refresh

    def search_page():
        view, _kind = visible_page(mw)
        return _focus_entry(_find_search_entry(view)) if view is not None else False
    handlers["view.search"] = search_page

    def clear_filters():
        view, _kind = visible_page(mw)
        clear = getattr(view, "_clear_filters", None)
        if clear is None:
            return False
        clear()
        toast(mw, "Filters cleared")
    handlers["view.clear_filters"] = clear_filters

    def global_search():
        tab_id = _regular_tab(mw)
        info = mw._tab_views.get(tab_id) or {}
        if info.get('type') != 'collections' or info.get('current_collection'):
            if info.get('type') == 'collections':
                mw._back_to_collections()
            else:
                mw._navigate_tab(tab_id, "collections")
        hub = (mw._tab_views.get(tab_id) or {}).get('view')
        bar = getattr(hub, 'search_bar', None)
        if bar is None:
            return False
        mw.after(50, lambda: _focus_entry(bar.search_entry))
    handlers["view.global_search"] = global_search

    # -- text formatting
    root = mw.winfo_toplevel()

    def formatting(method):
        def go():
            editor = focused_rich_editor(root)
            if editor is None:
                return False
            getattr(editor, method)()
        return go
    handlers["text.bold"] = formatting("insert_bold")
    handlers["text.italic"] = formatting("insert_italic")
    handlers["text.spell"] = formatting("insert_spell")
    handlers["text.table"] = formatting("insert_table")

    # -- settings
    sm = mw.settings_manager

    def appearance():
        current = ctk.get_appearance_mode().lower()
        mode = "light" if current == "dark" else "dark"
        sm.update(appearance_mode=mode)
        ctk.set_appearance_mode(mode)
        mw._on_appearance_changed(mode)
        toast(mw, f"{mode.title()} mode")
    handlers["toggle.appearance"] = appearance

    def legacy():
        values = [v for v, _ in LEGACY_CYCLE]
        current = getattr(sm.settings, "legacy_content_filter", "show_all")
        i = values.index(current) if current in values else -1
        value, label = LEGACY_CYCLE[(i + 1) % len(LEGACY_CYCLE)]
        sm.update(legacy_content_filter=value)
        mw.refresh_all_collection_views()
        toast(mw, f"Legacy content: {label}")
    handlers["toggle.legacy"] = legacy

    def chat_overlay():
        overlay = getattr(mw, "chat_overlay", None)
        if overlay is None:
            return False
        overlay.set_enabled(not overlay.enabled)
        toast(mw, "Chat overlay on" if overlay.enabled else "Chat overlay off")
    handlers["toggle.chat_overlay"] = chat_overlay

    return handlers
