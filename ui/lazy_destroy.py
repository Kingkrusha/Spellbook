"""
Take widget trees apart a little at a time.

Destroying CustomTkinter widgets is slow (a button costs ~10 ms), so destroying a page with
hundreds of them in one go freezes the whole window for seconds. ``destroy_later`` hides a
widget at once and destroys it in ~20 ms slices from the event loop, so the window stays
responsive while the old page goes away.
"""

import time
from collections import deque

from customtkinter.windows.widgets.core_widget_classes import CTkBaseClass
from customtkinter import CTkScrollbar

SLICE_SECONDS = 0.020
SLICE_GAP_MS = 10

_queue: deque = deque()
_job = None
_scheduler = None  # a widget to call after() on


def _teardown_order(widget):
    """The CustomTkinter widgets under ``widget``, children first, ``widget`` last.

    Only CTk widgets are yielded: their internal Tk parts (canvas, label) go when they do, and
    destroying those on their own would skip CustomTkinter's own clean-up. Scrollbars are
    internal parts of scrollable frames and text boxes, whose canvases keep talking to them
    until the whole frame is gone, so they must outlive their content."""
    for child in list(widget.winfo_children()):
        yield from _teardown_order(child)
    if isinstance(widget, CTkBaseClass) and not isinstance(widget, CTkScrollbar):
        yield widget


def destroy_later(widget) -> None:
    """Take ``widget`` off screen now and destroy it (and everything in it) in small slices."""
    global _job, _scheduler
    try:
        widget.pack_forget()
        widget.grid_forget()
        widget.place_forget()
    except Exception:
        pass
    try:
        scheduler = widget.winfo_toplevel()
    except Exception:
        return
    _queue.append(_teardown_order(widget))
    _scheduler = scheduler
    if _job is None:
        _schedule(SLICE_GAP_MS * 2)


def pending() -> bool:
    """True while pages are still being taken apart."""
    return bool(_queue)


def _schedule(delay_ms: int) -> None:
    global _job
    try:
        _job = _scheduler.after(delay_ms, _drain)
    except Exception:
        _job = None
        _queue.clear()  # the window is gone


def _drain() -> None:
    global _job
    _job = None
    deadline = time.perf_counter() + SLICE_SECONDS
    while _queue and time.perf_counter() < deadline:
        try:
            widget = next(_queue[0])
        except StopIteration:
            _queue.popleft()
            continue
        except Exception:
            _queue.popleft()
            continue
        try:
            widget.destroy()
        except Exception:
            pass
    if _queue:
        _schedule(SLICE_GAP_MS)
