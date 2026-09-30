"""
A stand-in for a heavy view that is only built the first time it is shown.

The Settings view has hundreds of widgets; even hidden, drawing them made up
about two thirds of the window's first paint. Its tab holds a LazyView instead,
and the real view is created when the tab is first opened.
"""

from typing import Any, Callable, Optional


class LazyView:
    def __init__(self, factory: Callable[[], Any]):
        self._factory = factory
        self._view: Optional[Any] = None

    @property
    def created(self) -> bool:
        return self._view is not None

    def ensure(self):
        """The real view, building it if this is the first use."""
        if self._view is None:
            self._view = self._factory()
        return self._view

    # What the tab code does with a view; showing it is what builds it.
    def pack(self, *args, **kwargs):
        self.ensure().pack(*args, **kwargs)

    def pack_forget(self):
        if self._view is not None:
            self._view.pack_forget()

    def destroy(self):
        if self._view is not None:
            self._view.destroy()

    def __getattr__(self, name: str):
        # Only reached for names not defined above. Until the view exists it has
        # nothing to offer (so e.g. a shutdown check for commit_pending_edits
        # does not build it just to be told there is nothing to save).
        if self._view is None:
            raise AttributeError(name)
        return getattr(self._view, name)

    def refresh_from_settings(self):
        self.ensure().refresh_from_settings()
