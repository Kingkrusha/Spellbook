"""
Small performance patches for CustomTkinter.

CTkScrollbar._draw() finishes with ``self._canvas.update_idletasks()``, and Tk
calls the scrollbar's set() every time a scroll region or view changes. Each of
those calls flushes *all* pending layout and redraw work in the whole
application, re-entrantly - so a window with several scrollable frames (this
app has one per collection, plus settings, spells and character sheets)
spends seconds redrawing the same widgets over and over during its first paint.
Drawing a scrollbar does not need that flush, so it is disabled on each
scrollbar's own (private) canvas.

Call install() once, before any window is created.
"""

_installed = False


def install():
    global _installed
    if _installed:
        return
    _installed = True
    try:
        from customtkinter.windows.widgets.ctk_scrollbar import CTkScrollbar
    except Exception:
        return                      # a different CustomTkinter layout: leave it alone

    original_init = CTkScrollbar.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._canvas.update_idletasks = lambda: None   # shadows the method on this canvas only

    CTkScrollbar.__init__ = patched_init

    _guard_toplevel_titlebar_revert()


def _guard_toplevel_titlebar_revert():
    """A CTkToplevel that is closed within ~10 ms of opening (a quick Cancel on a
    small dialog) makes CustomTkinter's delayed "revert withdraw" call
    ``deiconify()`` on a window that no longer exists. Harmless, but Tk prints a
    traceback for it; swallow that one error."""
    try:
        from customtkinter.windows.ctk_toplevel import CTkToplevel
        import tkinter
    except Exception:
        return
    original = getattr(CTkToplevel, "_revert_withdraw_after_windows_set_titlebar_color", None)
    if original is None:
        return

    def guarded(self, *args, **kwargs):
        try:
            return original(self, *args, **kwargs)
        except tkinter.TclError:
            return None

    CTkToplevel._revert_withdraw_after_windows_set_titlebar_color = guarded
