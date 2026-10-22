"""
Borderless pop-up windows (tooltips, drop-down lists, suggestion lists) that
close reliably.

Why pop-ups used to stay on screen:

1. On Windows, ``CTkToplevel.__init__`` recolours the title bar: it withdraws
   the window and calls ``update()``, which runs every pending event *while the
   pop-up is still being built*. The <Leave> or click that should close it is
   handled then, before the owner has stored the new window, so the close does
   nothing and the pop-up is shown afterwards with nobody watching it. A second
   click or keystroke handled there can even open a second pop-up, leaving the
   first one orphaned. Pop-ups have no title bar, so ``PopupWindow`` skips that
   step (``_deactivate_windows_window_header_manipulation``).
2. Each CTkToplevel also adds an app-wide <Button-1> handler that is never
   removed, so every tooltip shown made every later click a little slower.
   The main window already installs the same handler, so pop-ups skip it.
3. Tooltips only closed on <Leave>, and drop-downs only on <FocusOut>. Neither
   arrives when the view changes under a still pointer (a hotkey, a scroll),
   the window is moved or minimised, or the app loses focus with Alt+Tab.
   ``watch_hover`` and ``watch_popup`` check a few times a second and close the
   pop-up when it no longer belongs on screen.
"""

import tkinter as tk

import customtkinter as ctk

_WATCH_MS = 200


class PopupWindow(ctk.CTkToplevel):
    """A borderless, always-on-top CTkToplevel for short-lived pop-ups."""

    _deactivate_windows_window_header_manipulation = True

    def __init__(self, master, *args, **kwargs):
        self._sb_building = True
        super().__init__(master, *args, **kwargs)
        self._sb_building = False
        self.withdraw()
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

    def bind_all(self, sequence=None, func=None, add=None):
        if getattr(self, "_sb_building", False) and sequence == "<Button-1>":
            return None                    # CTk's per-window focus helper: the main window has one already
        return super().bind_all(sequence, func, add)


def is_within(widget, ancestor) -> bool:
    """True when ``widget`` is ``ancestor`` or one of its descendants."""
    w = widget
    while w is not None:
        if w == ancestor:
            return True
        w = getattr(w, "master", None)
    return False


def pointer_over(widget) -> bool:
    """True while the mouse pointer is over ``widget`` (or a child of it) and
    no other window covers that spot."""
    try:
        x, y = widget.winfo_pointerxy()
        under = widget.winfo_containing(x, y)
    except (tk.TclError, KeyError):
        return False
    return under is not None and is_within(under, widget)


def _alive(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def _viewable(widget) -> bool:
    try:
        return bool(widget.winfo_exists()) and bool(widget.winfo_viewable())
    except Exception:
        return False


def _app_has_focus(widget) -> bool:
    try:
        return widget.focus_get() is not None
    except KeyError:                       # focus is on a Tk-internal widget: still ours
        return True
    except Exception:
        return False


class _Watch:
    """A repeating check that calls ``close`` once ``should_close`` says so."""

    def __init__(self, owner, should_close, close):
        self._owner = owner
        self._should_close = should_close
        self._close = close
        self._job = None
        self._tick_later()

    def _tick_later(self):
        try:
            self._job = self._owner.after(_WATCH_MS, self._tick)
        except Exception:
            self._job = None

    def _tick(self):
        self._job = None
        try:
            done = self._should_close()
        except Exception:
            done = True
        if done:
            self._close()
        else:
            self._tick_later()

    def cancel(self):
        if self._job is not None:
            try:
                self._owner.after_cancel(self._job)
            except Exception:
                pass
            self._job = None


def watch_hover(widget, popup, close) -> _Watch:
    """Close a tooltip once the pointer is no longer over ``widget``, or
    ``widget`` is hidden or gone. Returns the watch; ``cancel()`` it on close."""
    def should_close():
        return (not _alive(popup)) or (not _viewable(widget)) or (not pointer_over(widget))
    return _Watch(widget, should_close, close)


def watch_popup(anchor, popup, close) -> _Watch:
    """Close a drop-down opened from ``anchor`` when the anchor is hidden or
    moves (page scrolled, window dragged or minimised), when the app loses
    focus, or on a click elsewhere in the anchor's window.
    Returns the watch; ``cancel()`` it when the pop-up closes."""
    host = anchor.winfo_toplevel()

    def where():
        try:
            return anchor.winfo_rootx(), anchor.winfo_rooty()
        except Exception:
            return None

    start = where()
    unfocused = [0]

    def should_close():
        if not _alive(popup) or not _viewable(anchor) or where() != start:
            return True
        # Two ticks in a row, so a focus hand-over between windows doesn't count.
        unfocused[0] = 0 if _app_has_focus(anchor) else unfocused[0] + 1
        return unfocused[0] >= 2

    def on_click(event):
        target = getattr(event, "widget", None)
        if isinstance(target, str):        # a Tk-internal widget with no Python object
            return
        if target is not None and (is_within(target, anchor) or is_within(target, popup)):
            return                         # the anchor toggles the pop-up itself
        watch.cancel()
        close()

    watch = _Watch(anchor, should_close, close)
    funcid = host.bind("<ButtonPress>", on_click, add="+")
    original_cancel = watch.cancel

    def cancel():
        original_cancel()
        remove_binding(host, "<ButtonPress>", funcid)

    watch.cancel = cancel
    return watch


def remove_binding(widget, sequence: str, funcid) -> None:
    """Remove one ``add="+"`` binding and leave the widget's others in place.
    (Before Python 3.13, ``unbind(sequence, funcid)`` removed all of them.)"""
    if not funcid:
        return
    try:
        script = widget.tk.call("bind", widget._w, sequence)
        kept = "\n".join(line for line in str(script).split("\n") if funcid not in line)
        widget.tk.call("bind", widget._w, sequence, kept)
        widget.deletecommand(funcid)
    except Exception:
        pass
