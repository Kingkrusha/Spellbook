"""Keep Tk's clean-up calls on Tk's own thread.

Python frees an object on whichever thread drops the last reference to it, or happens to run the
cycle collector. For a tkinter variable, image or font, freeing it means a Tcl call ("unset this
variable", "delete this image"). Tk only works on the thread that created it: from any other thread
the call has to be handed over and waited for. That stalls the other thread (the session's network
thread, a music or PDF worker) for as long as the window is busy, and at worst, when the last
reference to the Tcl interpreter itself goes away elsewhere, Tcl aborts the whole program ("Tcl_AsyncDelete:
async handler deleted by the wrong thread").

:func:`install` wraps those classes' finalizers: on Tk's thread they run as before; on any other
thread the object is put aside and finished off on Tk's thread a moment later (:func:`drain`).
"""

from __future__ import annotations

import threading
from typing import List, Tuple

_MAIN = threading.main_thread()
_lock = threading.Lock()
_pending: List[Tuple[object, object]] = []      # (original finalizer, object) to finish on Tk's thread
_installed = False
_job = None

DRAIN_MS = 500


def _wrap(cls) -> None:
    original = cls.__dict__.get("__del__")
    if original is None or getattr(original, "_sb_on_tk_thread", False):
        return

    def __del__(self, _original=original):
        try:
            elsewhere = threading.current_thread() is not _MAIN
        except Exception:                       # (the interpreter is shutting down)
            elsewhere = False
        if not elsewhere:
            _original(self)
            return
        with _lock:
            _pending.append((_original, self))  # keeps it alive until drain() runs on Tk's thread

    __del__._sb_on_tk_thread = True
    cls.__del__ = __del__


def wrap_classes() -> None:
    """Wrap the finalizers (safe to call more than once)."""
    import tkinter
    import tkinter.font
    for cls in (tkinter.Variable, tkinter.Image, tkinter.font.Font):
        _wrap(cls)
    try:
        from PIL import ImageTk
        for cls in (ImageTk.PhotoImage, ImageTk.BitmapImage):
            _wrap(cls)
    except Exception:
        pass


def drain() -> int:
    """Finish off what other threads let go of (on Tk's thread). Returns how many there were."""
    with _lock:
        items = list(_pending)
        _pending.clear()
    for finalize, obj in items:
        try:
            finalize(obj)
        except Exception:
            pass
    count = len(items)
    del items                                   # (the objects are freed here, on this thread)
    return count


def pending() -> int:
    with _lock:
        return len(_pending)


def install(root) -> None:
    """Wrap the finalizers and keep draining them from ``root``'s event loop."""
    global _installed
    wrap_classes()
    if _installed:
        return
    _installed = True

    def tick():
        global _job
        _job = None
        try:
            drain()
        finally:
            try:
                _job = root.after(DRAIN_MS, tick)
            except Exception:                   # the window is gone
                pass

    try:
        global _job
        _job = root.after(DRAIN_MS, tick)
    except Exception:
        pass
