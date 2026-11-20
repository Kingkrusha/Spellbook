"""Things that have to fit the window's width (ui/flow_bar.py, ui/placeholder_entry.py): toolbars that wrap
instead of losing their buttons, the class table that keeps its spell slot columns, and search boxes whose hint
shows although they are tied to a variable."""

import importlib
import time
import tkinter as tk

import customtkinter as ctk
import pytest

from ui.flow_bar import FlowBar, SidewaysBox
from ui.placeholder_entry import PlaceholderEntry


def pump(root, n=12):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


@pytest.fixture
def stage(tk_root):
    """A frame of a set width to build in (the test window itself is no particular size).

    The window is put on screen for these tests: Tk tells a widget that its size changed (<Configure>) only once
    the widget really exists, and that is when its window is first shown. Laying out again on that event is the
    very thing under test."""
    from typography import get_font_manager
    get_font_manager().scope.refresh()          # (fonts made for an earlier test module's window are gone with it)
    frames = []
    hidden = tk_root.state() == "withdrawn"
    if hidden:
        tk_root.deiconify()
        tk_root.update()

    def make(width, height=500):
        frame = tk.Frame(tk_root, width=width, height=height)
        frame.pack_propagate(False)
        frame.place(x=0, y=0)
        frames.append(frame)
        return frame

    yield make
    for frame in frames:
        frame.destroy()
    if hidden:
        tk_root.withdraw()


def left_edge(widget, inside):
    return widget.winfo_rootx() - inside.winfo_rootx()


def fits(widget, inside) -> bool:
    """Whether the whole of the widget is inside ``inside``, at its full width."""
    x = left_edge(widget, inside)
    return (widget.winfo_manager() != "" and widget.winfo_width() >= widget.winfo_reqwidth()
            and x >= 0 and x + widget.winfo_width() <= inside.winfo_width())


def a_bar(parent, controls=6):
    bar = ctk.CTkFrame(parent, fg_color="transparent")
    bar.pack(fill="x")
    left = []
    for n in range(controls):
        ctk.CTkLabel(bar, text=f"Filter {n}:").pack(side="left", padx=(0, 5))
        box = ctk.CTkComboBox(bar, width=120, values=["All"])
        box.pack(side="left", padx=(0, 10))
        left.append(box)
    add = ctk.CTkButton(bar, text="+ Add", width=90)
    add.pack(side="right")
    delete = ctk.CTkButton(bar, text="Delete", width=70)
    delete.pack(side="right", padx=(0, 5))
    return bar, left, [add, delete]


# ---------------------------------------------------------------- the wrapping bar

def test_a_bar_too_wide_for_the_window_wraps_and_keeps_its_buttons(tk_root, stage):
    frame = stage(520)
    bar, left, right = a_bar(frame)
    pump(tk_root)
    assert not all(fits(w, frame) for w in left + right)         # packed in one row: something is squeezed out

    FlowBar(bar)
    pump(tk_root)
    assert all(fits(w, frame) for w in left + right)
    assert len({w.winfo_y() for w in left}) > 1                  # ... because the filters went onto more rows
    assert left_edge(right[0], frame) + right[0].winfo_width() == frame.winfo_width()    # Add: far right, row one
    assert right[0].winfo_y() == min(w.winfo_y() for w in left + right)
    assert left_edge(right[1], frame) < left_edge(right[0], frame)
    assert bar.winfo_height() >= max(w.winfo_y() + w.winfo_height() for w in left)       # the bar grew with its rows


def test_a_bar_with_room_stays_on_one_row(tk_root, stage):
    frame = stage(1400)
    bar, left, right = a_bar(frame)
    FlowBar(bar)
    pump(tk_root)
    assert all(fits(w, frame) for w in left + right)
    assert len({w.winfo_y() + w.winfo_height() // 2 for w in left + right}) == 1


def test_a_label_stays_on_the_row_of_the_control_it_names(tk_root, stage):
    frame = stage(430)
    bar, left, _right = a_bar(frame, controls=5)
    FlowBar(bar)
    pump(tk_root)
    labels = [w for w in bar.winfo_children() if isinstance(w, ctk.CTkLabel)]
    assert len(labels) == len(left)
    for label, box in zip(labels, left):
        assert abs((label.winfo_y() + label.winfo_height() / 2) - (box.winfo_y() + box.winfo_height() / 2)) <= 2
        assert left_edge(label, frame) < left_edge(box, frame)


def test_a_control_shown_later_takes_its_place_in_the_rows(tk_root, stage):
    """The "Your fields" button: made with the bar, packed only once there is a field to filter on."""
    frame = stage(900)
    bar = ctk.CTkFrame(frame, fg_color="transparent")
    bar.pack(fill="x")
    first = ctk.CTkButton(bar, text="Sources...", width=110)
    first.pack(side="left", padx=(0, 10))
    extra = ctk.CTkButton(bar, text="Your fields", width=110)           # made here, but not packed
    last = ctk.CTkButton(bar, text="Tags...", width=110)
    last.pack(side="left", padx=(0, 10))
    ctk.CTkButton(bar, text="Clear Filters", width=110).pack(side="right")
    flow = FlowBar(bar)
    pump(tk_root)
    assert extra.winfo_manager() == "" and left_edge(last, frame) == first.winfo_width() + 10

    extra.pack(side="left", padx=(0, 20))
    pump(tk_root)
    assert fits(extra, frame)
    assert left_edge(first, frame) < left_edge(extra, frame) < left_edge(last, frame)     # where it was made
    assert left_edge(last, frame) == left_edge(extra, frame) + extra.winfo_width() + 20

    extra.pack_forget()
    pump(tk_root)
    assert extra.winfo_manager() == "" and left_edge(last, frame) == first.winfo_width() + 10
    assert [i.shown for i in flow.items if i.widget is extra] == [False]


# ---------------------------------------------------------------- the pages that use it

PAGES = {
    "monsters": ("ui.monster_view", "MonsterView"),
    "magic items": ("ui.magic_item_view", "MagicItemView"),
    "equipment": ("ui.equipment_view", "EquipmentView"),
    "feats": ("ui.feats_view", "FeatsView"),
    "spells": ("ui.spells_view", "SpellsView"),
}


def buttons(widget, found=None):
    found = [] if found is None else found
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton):
            found.append(child)
        elif isinstance(child, ctk.CTkFrame):
            buttons(child, found)
    return found


@pytest.mark.parametrize("key", list(PAGES))
def test_the_add_edit_and_delete_buttons_fit_the_smallest_window(key, tk_root, stage):
    """At 900 pixels (the window's minimum) the pages used to lose them: on Monsters already at the default size."""
    module, cls = PAGES[key]
    frame = stage(900, 600)
    kwargs = {}
    if key == "spells":
        from character_manager import CharacterManager
        from spell_manager import SpellManager
        from settings import get_settings_manager
        kwargs = {"spell_manager": SpellManager(), "character_manager": CharacterManager(),
                  "settings_manager": get_settings_manager()}
    try:
        view = getattr(importlib.import_module(module), cls)(frame, **kwargs)
    except TypeError:
        pytest.skip("this page is built differently here")
    view.pack(fill="both", expand=True)
    pump(tk_root, 25)
    try:
        wanted = [b for b in buttons(view) if str(b.cget("text")).startswith(("+ ", "Edit", "Delete", "Duplicate",
                                                                               "Clear Filters"))
                  and b.winfo_viewable() and b.winfo_y() < 300]
        assert any(str(b.cget("text")).startswith("+ ") for b in wanted)
        assert [str(b.cget("text")) for b in wanted if not fits(b, frame)] == []
    finally:
        view.destroy()


def test_a_full_casters_class_table_shows_every_spell_slot_column(tk_root, stage):
    """The Wizard's table has eleven columns after "Class Features". At the default window size the page has about
    815 pixels for it, and showed the slots up to 2nd level only."""
    from ui.classes_view import ClassesCollectionView
    frame = stage(1100, 700)                             # the window's default width
    view = ClassesCollectionView(frame)
    view.pack(fill="both", expand=True)
    pump(tk_root, 10)
    try:
        assert view.select_class("Wizard")
        deadline = time.time() + 20
        box = None
        while time.time() < deadline:
            pump(tk_root, 5)
            # (the first class shown, Artificer, may still be on its way out: only the table on screen counts)
            boxes = [w for w in view.content.winfo_children() if isinstance(w, SidewaysBox) and w.winfo_manager()]
            tables = boxes[-1].inner.winfo_children() if boxes else []
            if tables and tables[0]._rows >= 21:
                box = boxes[-1]
                break
        assert box is not None, "the feature table was not built"
        pump(tk_root, 10)
        table = box.inner.winfo_children()[0]
        headings = table.header_labels()
        titles = [str(w.cget("text")).replace("\n", " ") for w in headings]
        shown = view.current_class               # (whichever Wizard the content settings pick)
        assert {"Level", "Proficiency Bonus", "Class Features"} <= set(titles)
        assert set(shown.class_table_columns) <= set(titles) and "1st" in titles and len(titles) >= 10
        assert not box._bar_shown                                        # nothing to scroll: it all fits
        for label in headings:
            assert fits(label, box), label.cget("text")
        assert len(table.winfo_children()) == 21 * len(table.columns)    # one plain label a cell, nothing more
    finally:
        view.destroy()


def test_a_table_wider_than_its_room_scrolls_sideways(tk_root, stage):
    frame = stage(300, 300)
    box = SidewaysBox(frame, least_width=700)
    box.pack(fill="x")
    ctk.CTkLabel(box.inner, text="a row").pack(fill="x")
    pump(tk_root)
    assert box._bar_shown and box.inner.winfo_width() >= 700

    frame.configure(width=900)
    pump(tk_root)
    assert not box._bar_shown and box.inner.winfo_width() == box._view.winfo_width()


# ---------------------------------------------------------------- the hint in a box that has a variable

def test_a_search_box_with_a_variable_shows_its_hint_and_keeps_it_out_of_the_variable(tk_root, stage):
    frame = stage(400)
    var = ctk.StringVar()
    seen = []
    var.trace_add("write", lambda *_: seen.append(var.get()))
    box = PlaceholderEntry(frame, textvariable=var, placeholder_text="Search monsters...")
    box.pack()
    pump(tk_root, 3)
    assert box._entry.get() == "Search monsters..." and var.get() == "" and box.get() == "" and seen == []

    box._entry_focus_in()                      # the person clicks in the box and types
    box._entry.insert(0, "dra")
    assert var.get() == "dra" and seen == ["dra"] and box.get() == "dra"

    var.set("")                                # Clear Filters, while the box still has the keyboard
    assert box._entry.get() == ""
    box._entry_focus_out()
    assert box._entry.get() == "Search monsters..." and var.get() == ""

    var.set("gob")                             # set by the page while the hint is showing
    assert box._entry.get() == "gob" and box.get() == "gob"
    var.set("")
    assert box._entry.get() == "Search monsters..." and var.get() == "" and seen[-1] == ""

    box.destroy()
    var.set("still fine")                      # (the box no longer listens)


def test_a_box_that_starts_with_a_value_shows_the_value(tk_root, stage):
    frame = stage(400)
    var = ctk.StringVar(value="12")
    box = PlaceholderEntry(frame, textvariable=var, placeholder_text="Min")
    box.pack()
    pump(tk_root, 3)
    assert box._entry.get() == "12" and var.get() == "12"


def test_the_pages_search_boxes_show_their_hints(tk_root, stage):
    from ui.monster_view import MonsterView
    frame = stage(1000, 600)
    view = MonsterView(frame)
    view.pack(fill="both", expand=True)
    pump(tk_root, 10)
    try:
        bars = list(view._top_bar.winfo_children()) + [
            e for row in view.folding.rows for e in row.winfo_children()]      # (most filters fold away)
        hints = sorted(e._entry.get() for e in bars if isinstance(e, PlaceholderEntry))
        assert hints == ["Max", "Max", "Min", "Min", "Search monsters..."]
        assert view.search_var.get() == "" and view.min_ac_var.get() == ""
        before = len(view.list_panel._items)
        view.search_var.set("aboleth")
        pump(tk_root, 30)
        assert 0 < len(view.list_panel._items) < before
    finally:
        view.destroy()
