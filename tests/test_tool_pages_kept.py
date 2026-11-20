"""Game Tools pages a tab leaves are kept (the last few), so going back to one is instant (ui/main_window.py)."""

from collections import OrderedDict

from ui.main_window import MainWindow


class Page:
    def __init__(self, name):
        self.name = name
        self.destroyed = False

    def pack_forget(self):
        pass

    def destroy(self):
        self.destroyed = True


class FakeWindow:
    """Just the page-keeping part of the main window."""
    CACHEABLE_PAGES = MainWindow.CACHEABLE_PAGES
    KEPT_TOOL_PAGES = MainWindow.KEPT_TOOL_PAGES
    PAGE_CACHE_SIZE = MainWindow.PAGE_CACHE_SIZE
    TOOL_CACHE_SIZE = MainWindow.TOOL_CACHE_SIZE
    _stash_page = MainWindow._stash_page
    _take_cached_page = MainWindow._take_cached_page
    _is_tool_key = MainWindow._is_tool_key
    _dispose_entry = MainWindow._dispose_entry
    _page_key = MainWindow._page_key

    def __init__(self):
        self._clock = 0
        self.later = []
        self._tab_views = {"t": {"type": None, "view": None}}

    def _touch(self):
        self._clock += 1
        return self._clock

    def _hide_tab_content(self, tab_id):
        pass

    def _detach_orphaned_sheet(self, view):
        pass

    def _destroy_later(self, widget):
        self.later.append(widget)

    def show(self, page_type):
        """What _navigate_tab does with the cache: leave the page shown, then reuse or build the next."""
        info = self._tab_views["t"]
        self._stash_page("t")
        key = self._page_key(page_type)
        entry = self._take_cached_page(info, key)
        info["type"], info["page_key"] = page_type, key
        info["view"] = entry["view"] if entry else Page(page_type)
        return info["view"], entry is not None


def test_going_back_to_a_tool_reuses_its_page():
    w = FakeWindow()
    tabletop, _ = w.show("tabletop")
    w.show("game_tools")
    initiative, _ = w.show("initiative")
    again, reused = w.show("tabletop")
    assert reused and again is tabletop and not tabletop.destroyed
    back, reused = w.show("initiative")
    assert reused and back is initiative


def test_only_the_last_few_tools_are_kept_and_the_rest_are_closed_at_once():
    w = FakeWindow()
    pages = [w.show(kind)[0] for kind in ("tabletop", "initiative", "dice_analyzer", "music", "calendar", "home")]
    cache = w._tab_views["t"]["cache"]
    tools = [k[0] for k in cache if k[0] in MainWindow.KEPT_TOOL_PAGES]
    assert tools == ["dice_analyzer", "music", "calendar"]           # the three left most recently
    assert pages[0].destroyed and pages[1].destroyed                   # tabletop, initiative: torn down at once
    assert pages[0] not in w.later                                     # (not taken apart in slices)


def test_kept_tools_do_not_push_out_the_kept_collection_pages():
    w = FakeWindow()
    for kind in ("collections", "characters", "home", "tabletop", "initiative", "music", "calendar"):
        w.show(kind)
    cache = w._tab_views["t"]["cache"]
    assert {("collections",), ("characters",), ("home",)} <= set(cache)
