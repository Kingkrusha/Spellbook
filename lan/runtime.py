"""Running asyncio on a private thread, and handing events to the UI.

Tkinter is not thread-safe, so the network code never touches a widget or a data
manager. It runs in its own event loop on its own thread and appends plain dicts to
an :class:`EventQueue`; the UI thread empties it from a periodic ``after`` callback
(``queue.get_nowait`` is the only thing both sides share).
"""

from __future__ import annotations

import asyncio
import queue
import threading
from concurrent.futures import Future
from typing import Any, Awaitable, Dict, List, Optional


class EventQueue:
    """Thread-safe mailbox: the network thread ``put``s, the UI thread ``drain``s."""

    def __init__(self):
        self._q: "queue.Queue[Dict[str, Any]]" = queue.Queue()

    def put(self, kind: str, **fields) -> None:
        self._q.put({"type": kind, **fields})

    def drain(self, limit: int = 500) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        while len(out) < limit:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                break
        return out

    def get(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Block for one event (tests and scripts; the UI uses :meth:`drain`)."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None


def _quiet_exception_handler(loop, context):
    """Connection resets, bad TLS handshakes from port scanners and the like are normal
    on a network socket; asyncio would otherwise print a traceback for each."""
    exc = context.get("exception")
    if isinstance(exc, (ConnectionError, OSError, asyncio.CancelledError)):
        return
    import ssl
    if isinstance(exc, ssl.SSLError):
        return
    loop.default_exception_handler(context)


class LoopThread:
    """An asyncio event loop running on a daemon thread."""

    def __init__(self, name: str = "lan"):
        self._name = name
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        assert self._loop is not None, "LoopThread not started"
        return self._loop

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        def run():
            loop = asyncio.new_event_loop()
            loop.set_exception_handler(_quiet_exception_handler)
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            try:
                loop.run_forever()
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                finally:
                    loop.close()

        self._thread = threading.Thread(target=run, name=self._name, daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def submit(self, coro: Awaitable) -> "Future":
        """Run ``coro`` on the loop; returns a ``concurrent.futures.Future``."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def call(self, coro: Awaitable, timeout: Optional[float] = None):
        """Run ``coro`` on the loop and wait for its result (from another thread)."""
        return self.submit(coro).result(timeout)

    def call_soon(self, fn, *args) -> None:
        if self.running:
            self.loop.call_soon_threadsafe(fn, *args)

    def stop(self, timeout: float = 3.0) -> None:
        if not self.running:
            return

        async def cancel_all():
            current = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks() if t is not current]
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            self.call(cancel_all(), timeout)
        except Exception:
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self._thread is not None:
            self._thread.join(timeout)
