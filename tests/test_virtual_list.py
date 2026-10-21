"""Regression tests for the virtualized lists, the tab bar width, and the window-handle budget.

These guard problems that only show up with a lot of content or a lot of tabs:

* rows deep in a long list were never drawn (Windows cannot position a child window further than
  ~32,767 px from its parent, and the list used to be one giant scroll region);
* rows created after a text-size change came out in the old size;
* a tab's width attribute collided with CustomTkinter's (a float), breaking the label truncation
  as soon as the bar had been resized;
* enough heavy tabs exhausted Windows' 10,000 window handles ("No more menus can be allocated").
"""

from dataclasses import dataclass
from types import SimpleNamespace

import pytest


@dataclass
class Entry:
    name: str
    is_custom: bool = False


@pytest.fixture()
def panel(tk_root):
    from ui.virtual_list import VirtualListPanel
    p = VirtualListPanel(tk_root, on_select=lambda item: None)
    p.pack(fill="both", expand=True)
    # A withdrawn root has no real geometry: give the list a fixed, known viewport
    p._viewport_height = lambda: 600.0
    yield p
    p.destroy()


def placed_rows(p):
    return sorted((r._vl_index, r._vl_y) for r in p._pool if r._vl_index != -1)


def test_rows_are_positioned_near_the_viewport_however_deep_the_list(panel):
    """The limit that broke long lists: coordinates must never grow with the list length."""
    n = 30000                       # ~1.3 million px of virtual height
    panel.set_items([Entry(f"Entry {i:05d}") for i in range(n)])
    for fraction in (0.0, 0.31, 0.5, 0.97, 1.0):
        panel._offset = fraction * panel._max_offset()
        panel._render_visible()
        rows = placed_rows(panel)
        assert 0 < len(rows) < 60                                # constant, not O(n)
        indexes = [i for i, _ in rows]
        assert indexes == list(range(indexes[0], indexes[0] + len(indexes)))   # contiguous
        first_visible = int(panel._offset // panel._stride)
        assert indexes[0] <= first_visible <= indexes[-1]        # the first visible entry has a row
        assert all(0 <= y < 5000 for _, y in rows)               # inside the small rows frame
        assert abs(panel._content_geometry) < 5000               # and the frame itself stays near 0


def test_every_visible_entry_has_a_row(panel):
    panel.set_items([Entry(f"Entry {i:05d}") for i in range(5000)])
    panel._offset = 0.6 * panel._max_offset()
    panel._render_visible()
    shown = {i for i, _ in placed_rows(panel)}
    first = int(panel._offset // panel._stride)
    last = int((panel._offset + 600) // panel._stride)
    assert set(range(first, last + 1)) <= shown


def test_scrollbar_commands_move_and_clamp(panel):
    panel.set_items([Entry(f"E{i}") for i in range(1000)])
    panel._on_scrollbar("moveto", "0.5")
    assert abs(panel._offset / panel._content_height() - 0.5) < 0.01
    panel._on_scrollbar("scroll", "3", "units")
    assert panel._offset > 0.5 * panel._content_height() - 1
    panel._on_scrollbar("moveto", "2.0")                         # past the end
    assert panel._offset == panel._max_offset()
    panel._on_scrollbar("moveto", "-1")                          # before the start
    assert panel._offset == 0


def test_selecting_a_far_entry_scrolls_it_into_view(panel):
    selected = []
    panel.on_select = selected.append
    panel.set_items([Entry(f"Entry {i:05d}") for i in range(8000)])
    assert panel.select_by_name("entry 07500")
    assert selected and selected[-1].name == "Entry 07500"
    first = int(panel._offset // panel._stride)
    assert first <= 7500 <= first + 600 // panel._stride + 1


def test_select_when_listed_waits_for_the_entry_to_arrive(tk_root):
    """A page that adds an entry reloads its list a moment later; the new entry is selected when it shows up."""
    from ui.virtual_list import VirtualListPanel
    picked = []
    p = VirtualListPanel(tk_root, on_select=picked.append)
    p.pack(fill="both", expand=True)
    p._viewport_height = lambda: 600.0
    try:
        old = [Entry("A"), Entry("B")]
        p.set_items(old)
        assert p.select_by_name("C") is False and p.get_selected() is None      # not there yet: nothing happens

        p.select_when_listed("C")
        assert p.get_selected() is None and picked == []                        # still waiting
        fresh = [Entry("A"), Entry("B"), Entry("C")]
        p.set_items(fresh)
        assert p.get_selected() is fresh[2] and picked == [fresh[2]]            # selected, and the owner told

        # an entry that is already listed is re-selected from the NEW list, so an edited entry is shown as edited
        edited = [Entry("A"), Entry("B"), Entry("C", is_custom=True)]
        p.select_when_listed("C")
        p.set_items(edited)
        assert p.get_selected() is edited[2] and picked[-1] is edited[2]

        # the wait lasts for one change only, and a name that never arrives is dropped
        p.select_when_listed("Z")
        p.set_items(edited)
        p.set_items(edited + [Entry("Z")])
        assert p.get_selected() is edited[2]
    finally:
        p.destroy()


def test_rows_created_after_a_text_size_change_use_the_new_size(tk_root, panel):
    """Rows are created lazily as the window grows; they must not come out in the old size."""
    from typography import get_font_manager, ui_font
    manager = get_font_manager()
    original = manager.settings.roles["body"].size
    try:
        panel.set_items([Entry(f"E{i}") for i in range(500)])
        panel._render_visible()
        small_pool = len(panel._pool)
        manager.set_role("body", size=original + 8)
        panel._viewport_height = lambda: 1800.0          # a much taller window: the pool must grow
        panel._render_visible()
        assert len(panel._pool) > small_pool
        expected = ui_font("body", 13).cget("size")
        new_rows = panel._pool[small_pool:]
        assert new_rows and all(r.cget("font").cget("size") == expected for r in new_rows)
    finally:
        manager.set_role("body", size=original)


def test_tab_label_truncation_survives_customtkinter_resizing(tk_root):
    """TabWidget used to keep its width in an attribute CustomTkinter overwrites with a float."""
    from ui.tab_bar import TabWidget
    tab = TabWidget(tk_root, tab_id="t", tab_type="collections", display_text="A rather long title",
                    is_closable=True)
    tab._current_width = 117.0          # what CTk's own resize handling leaves behind
    tab.set_text("Another quite long tab title")      # used to raise TypeError (float slice index)
    tab.set_width(64.0)
    assert isinstance(tab.display_text, str) and tab.display_text
    tab.destroy()


def fake_window(tabs, current="cur", spare=()):
    from ui.main_window import MainWindow
    ns = SimpleNamespace(_current_tab_id=current, _tab_views=tabs,
                         _spare_sub_views={k: object() for k in spare},
                         CACHEABLE_PAGES=MainWindow.CACHEABLE_PAGES)
    return MainWindow._eviction_candidates(ns)


def test_handle_budget_gives_up_cheap_things_first_and_never_the_current_page():
    page = object()
    tabs = {
        "cur": {"type": "collections", "view": page, "sub_view": "s", "sub_views": {"spells": "s", "feats": "f"},
                "sub_used": {"feats": 5}, "cache": {("home",): {"used": 9}}, "used": 100},
        "old": {"type": "character_sheet", "view": page, "used": 10},
        "new": {"type": "collections", "view": page, "used": 90},
        "settings": {"type": "settings", "view": page},
    }
    order = fake_window(tabs, spare=("monsters",))
    kinds = [(kind, tab, key) for _p, _u, kind, tab, key in order]
    assert kinds[0] == ("spare", None, "monsters")                 # prebuilt, unused pages go first
    assert kinds[1] == ("cache", "cur", ("home",))                 # then pages a tab left behind
    assert kinds[2] == ("sub", "cur", "feats")                     # then collection pages not shown
    assert [k for k in kinds if k[0] == "tab"] == [("tab", "old", None), ("tab", "new", None)]   # oldest first
    assert ("tab", "cur", None) not in kinds                       # what you are looking at is never offered
    assert ("sub", "cur", "spells") not in kinds                   # nor the collection page that is shown
    assert not any(tab == "settings" for _k, tab, _key in kinds)   # settings is not a page to give up


def test_handle_budget_is_inert_where_handles_cannot_be_measured(monkeypatch):
    from ui import handle_budget
    monkeypatch.setattr(handle_budget, "user_handles", lambda: None)
    called = []
    handle_budget.set_reclaimer(lambda: called.append(1))
    try:
        handle_budget.ensure_headroom()
        assert not called and handle_budget.level() is None
    finally:
        handle_budget.set_reclaimer(None)


def test_out_of_handles_errors_are_recognised():
    from ui.handle_budget import is_out_of_handles_error
    assert is_out_of_handles_error(Exception("No more menus can be allocated."))
    assert not is_out_of_handles_error(Exception('invalid command name ".!frame"'))
