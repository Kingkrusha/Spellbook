"""
Atomic file-write helpers for D&D Spellbook Application.

Writing user data with a plain ``open(path, "w")`` truncates the existing file
before the new contents are written. If the process is interrupted mid-write
(crash, power loss, the OS killing the app during shutdown) the file is left
truncated or partially written and the previous good copy is gone.

These helpers write to a temporary file in the same directory, flush it to disk,
then ``os.replace()`` it over the target. ``os.replace`` is atomic on both
Windows and POSIX, so a reader either sees the complete old file or the complete
new one - never a half-written file.
"""

import json
import os
import tempfile
from contextlib import contextmanager
from typing import Any, Callable, List


def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> None:
    """Atomically write ``text`` to ``path``.

    Raises on failure (caller is responsible for logging / returning a status).
    """
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)

    # Create the temp file in the same directory so os.replace stays on one
    # filesystem (a cross-device rename would not be atomic and would fail).
    fd, tmp_path = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up the temp file on any failure; never leave litter behind.
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(
    path: str,
    data: Any,
    *,
    indent: int = 2,
    ensure_ascii: bool = True,
) -> None:
    """Atomically serialize ``data`` to JSON at ``path``.

    Raises on failure (caller is responsible for logging / returning a status).
    """
    text = json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)
    atomic_write_text(path, text)


class SaveErrorListeners:
    """For a manager that saves user data: lets the UI hear about a failed load or save.

    Without it a failure was only ever ``print()``-ed - invisible in a windowed build with no console - so edits
    could silently vanish without the user ever finding out. The manager sets ``self._error_listeners = []`` and
    calls ``self._notify_error(message)`` where it used to print."""

    _error_listeners: List[Callable[[str], None]]

    def add_error_listener(self, callback: Callable[[str], None]):
        """Add a listener to be notified when a load/save fails."""
        self._error_listeners.append(callback)

    def _notify_error(self, message: str):
        for listener in self._error_listeners:
            try:
                listener(message)
            except Exception:
                pass


class HeldSaves:
    """For a manager that writes its whole file on every save: lets a burst of changes be written once.

    Inside ``with manager.saves_held():`` a save only notes that there is something to write; when the
    outermost ``with`` ends, the file is written a single time. The manager names its save method in
    ``_HELD_SAVE`` and starts its save method with ``if self._hold_save(): return True``."""

    _HELD_SAVE = "save"
    _save_hold = 0
    _save_pending = False

    def _hold_save(self) -> bool:
        """True while saves are held (the save is remembered for later)."""
        if self._save_hold:
            self._save_pending = True
            return True
        return False

    @contextmanager
    def saves_held(self):
        self._save_hold += 1
        try:
            yield self
        finally:
            self._save_hold -= 1
            if not self._save_hold and self._save_pending:
                self._save_pending = False
                getattr(self, self._HELD_SAVE)()
