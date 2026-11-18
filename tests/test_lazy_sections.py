"""Parts of a long page built as they come near the view (ui/lazy_sections.py), as the Classes page uses them."""

import time
import tkinter as tk

import customtkinter as ctk
import pytest

from ui.lazy_sections import LazySections, estimate_text_height


def pump(root, n=15):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


@pytest.fixture
def page(tk_root):
    hidden = tk_root.state() == "withdrawn"
    if hidden:
        tk_root.deiconify()
    frame = tk.Frame(tk_root, width=500, height=400)
    frame.pack_propagate(False)
    frame.place(x=0, y=0)
    scroll = ctk.CTkScrollableFrame(frame)
    scroll.pack(fill="both", expand=True)
    yield scroll
    frame.destroy()
    if hidden:
        tk_root.withdraw()


def fill(n, built):
    def build(holder):
        built.append(n)
        tk.Frame(holder, height=200, bg="grey").pack(fill="x")        # twice as tall as its estimate
    return build


def test_only_the_parts_near_the_view_are_built_and_scrolling_builds_more(tk_root, page):
    lazy = LazySections(page)
    built = []
    holders = [lazy.add(page, fill(n, built), height=100) for n in range(40)]
    pump(tk_root)
    assert built and len(built) < 15 and built == sorted(built)        # the top of the page, nothing further down
    assert lazy.pending == 40 - len(built)

    canvas = page._parent_canvas
    canvas.yview_moveto(0.6)
    pump(tk_root, 25)
    far = holders[int(len(holders) * 0.6)]
    assert holders.index(far) in built or any(abs(n - holders.index(far)) < 4 for n in built[-6:])
    assert lazy.pending > 0                                            # the parts in between stay empty

    lazy.build_all()
    assert lazy.pending == 0 and sorted(built) == list(range(40))


def test_a_part_built_above_the_view_does_not_move_what_is_shown(tk_root, page):
    lazy = LazySections(page)
    built = []
    holders = [lazy.add(page, fill(n, built), height=100) for n in range(40)]
    pump(tk_root)
    canvas = page._parent_canvas
    canvas.yview_moveto(0.8)
    pump(tk_root, 25)
    # a part on screen, and where it is
    top = canvas.winfo_rooty()
    shown = [h for h in holders if top <= h.winfo_rooty() < top + canvas.winfo_height()]
    assert shown
    marker = shown[-1]
    before = marker.winfo_rooty()
    pending = lazy.pending
    for _ in range(8):                        # up with the mouse wheel, a step at a time, into parts not built yet
        canvas.yview_scroll(-2, "units")
        pump(tk_root, 4)
    assert lazy.pending < pending                                      # (some were built above the old view)
    for _ in range(8):
        canvas.yview_scroll(2, "units")
        pump(tk_root, 4)
    # back where we were: the parts that grew above didn't push the marker away (but for the scroll step's rounding)
    assert abs(marker.winfo_rooty() - before) <= int(float(canvas.cget("yscrollincrement"))) // 2 + 1


def test_cleared_parts_are_not_built(tk_root, page):
    lazy = LazySections(page)
    built = []
    for n in range(30):
        lazy.add(page, fill(n, built), height=100)
    lazy.clear()                                                       # the page is being replaced
    pump(tk_root)
    page._parent_canvas.yview_moveto(0.5)
    pump(tk_root)
    assert built == [] and lazy.pending == 0


def test_the_estimate_grows_with_the_text_and_shrinks_with_the_width(tk_root):
    from tkinter import font as tkfont
    f = tkfont.Font(root=tk_root, family="TkDefaultFont", size=12)
    short = estimate_text_height("A few words.", 600, f)
    long = estimate_text_height("word " * 400, 600, f)
    narrow = estimate_text_height("word " * 400, 300, f)
    assert short < long < narrow
    assert estimate_text_height("one\n\ntwo", 600, f) > short
