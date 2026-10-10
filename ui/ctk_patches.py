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

Also: tkinter deletes a destroyed widget's ``after()`` callbacks but leaves their
timers scheduled. Python can then reuse the freed object id for a *new* callback
with the same name, and the stale timer calls that unrelated function with the
wrong arguments (an intermittent "missing 1 required positional argument: 'e'" on
a list row, for example). Pending timers are cancelled when their widget is
destroyed.

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
    _cancel_timers_on_destroy()


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


def _cancel_timers_on_destroy():
    """Cancel a widget's pending after()/after_idle() timers when the widget is destroyed."""
    import tkinter
    misc = tkinter.Misc
    original_after = misc.after
    original_after_idle = misc.after_idle
    original_after_cancel = misc.after_cancel
    original_destroy = misc.destroy

    def track(widget, schedule, func, args):
        jobs = widget.__dict__.setdefault("_sb_after_jobs", set())
        cell = []

        def wrapped(*call_args):
            jobs.discard(cell[0])
            return func(*call_args)

        wrapped.__name__ = getattr(func, "__name__", "wrapped")
        job = schedule(wrapped, *args)
        cell.append(job)
        jobs.add(job)
        return job

    def after(self, ms, func=None, *args):
        if func is None:                      # after(ms): a plain sleep, nothing to track
            return original_after(self, ms)
        return track(self, lambda f, *a: original_after(self, ms, f, *a), func, args)

    def after_idle(self, func, *args):
        return track(self, lambda f, *a: original_after_idle(self, f, *a), func, args)

    def after_cancel(self, id):
        jobs = self.__dict__.get("_sb_after_jobs")
        if jobs is not None:
            jobs.discard(id)
        return original_after_cancel(self, id)

    def destroy(self):
        jobs = self.__dict__.get("_sb_after_jobs")
        if jobs:
            for job in list(jobs):
                try:
                    original_after_cancel(self, job)
                except Exception:
                    pass
            jobs.clear()
        return original_destroy(self)

    misc.after = after
    misc.after_idle = after_idle
    misc.after_cancel = after_cancel
    misc.destroy = destroy
