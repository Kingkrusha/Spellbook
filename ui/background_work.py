"""
Running a calculation off the UI thread for the Dice Analyzer and the Matchup page.

Both do the same thing: a change in a control is *debounced* (so typing does not recalculate on every key), the work
runs on a worker thread, and the page polls for the answer with ``after``. A result that arrives after the user has
already changed something else is stale and dropped, which is what the token is for. A page mixes this in and
supplies what to run and what to do with the outcome::

    class MatchupView(BackgroundWorkMixin, ctk.CTkFrame):
        POLL_MS = 60
        def __init__(...):  self._init_background_work()
        def changed(self, now=False):  self._debounce(self._start, DEBOUNCE_MS, now)
        def _start(self):  ...; self._run_in_thread(lambda: M.analyze(a, b, TRIALS))
        def _on_work_done(self, result): ...
        def _on_work_failed(self, message): ...
        def _work_error_text(self, exc): ...
"""

import queue
import threading
import tkinter as tk
from typing import Any, Callable


class BackgroundWorkMixin:
    POLL_MS = 40

    def _init_background_work(self):
        self._job = None                       # the pending (debounced) start
        self._poll_job = None                  # the pending look for an answer
        self._token = 0                        # which run the page currently wants
        self._done: "queue.Queue" = queue.Queue()
        self.bind("<Destroy>", self._on_destroy, add="+")

    # ---- what a page provides

    def _on_work_done(self, result: Any):
        raise NotImplementedError

    def _on_work_failed(self, message: str):
        raise NotImplementedError

    def _work_error_text(self, exc: Exception) -> str:
        """The message for a calculation that raised ``exc`` (a bug must not leave the page waiting)."""
        return f"Something went wrong ({type(exc).__name__}: {exc})."

    # ---- running

    def _debounce(self, callback: Callable[[], None], delay_ms: int, now: bool = False):
        """Run ``callback`` shortly (at once when ``now``), restarting the wait on every call."""
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
        try:
            self._job = self.after(1 if now else delay_ms, callback)
        except tk.TclError:
            self._job = None

    def _run_in_thread(self, work: Callable[[], Any]):
        """Start ``work()`` on a worker thread; its result (or failure) reaches the page's hooks."""
        self._token += 1
        token = self._token

        def run():
            try:
                outcome = ("ok", work())
            except Exception as exc:
                outcome = ("err", self._work_error_text(exc))
            self._done.put((token, outcome))

        threading.Thread(target=run, daemon=True).start()
        self._poll()

    def _poll(self):
        if self._poll_job is not None:
            return
        self._poll_job = self.after(self.POLL_MS, self._poll_tick)

    def _poll_tick(self):
        self._poll_job = None
        latest = None
        try:
            while True:
                latest = self._done.get_nowait()
        except queue.Empty:
            pass
        if latest is not None and latest[0] == self._token:
            kind, payload = latest[1]
            if kind == "ok":
                self._on_work_done(payload)
            else:
                self._on_work_failed(payload)
            return
        if self._token and (latest is None or latest[0] != self._token):
            self._poll()

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        self._token += 1
        for job in (self._job, self._poll_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
