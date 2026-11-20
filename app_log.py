"""spellbook.log: everything the app prints, kept in a small file in the data folder.

The app reports most problems with ``print()``. Run from a console they scroll past and are gone when it
closes, and a windowed build has no console at all, so :func:`install` copies whatever is written to
``sys.stdout`` and ``sys.stderr`` into ``spellbook.log`` as well (still printing it where it went before,
if anywhere). Each start writes a line naming the run, so a crash report can pick out the run that
crashed. The file is kept small: past :data:`MAX_BYTES` it is renamed to ``spellbook.log.1`` (replacing
the one before) and a new one is started.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional, TextIO

FILE = "spellbook.log"
MAX_BYTES = 1024 * 1024

_handle: Optional[TextIO] = None
_lock = threading.Lock()
_path = ""
_size = 0


def log_path() -> str:
    from paths import user_data_path
    return user_data_path(FILE)


def start_line(started: str, pid: int) -> str:
    """The line that opens one run's part of the log (crash.log uses the same one)."""
    return f"===== Spellbook started {started} (pid {pid}) ====="


class _Tee:
    """A text stream that writes to the original stream (if there is one) and to the log file."""

    def __init__(self, original):
        self._original = original

    def write(self, text):
        if self._original is not None:
            try:
                self._original.write(text)
            except Exception:
                pass
        _write(text)
        return len(text) if isinstance(text, str) else 0

    def flush(self):
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass

    def isatty(self):
        try:
            return bool(self._original is not None and self._original.isatty())
        except Exception:
            return False

    @property
    def encoding(self):
        return getattr(self._original, "encoding", None) or "utf-8"

    def fileno(self):
        if self._original is None:
            raise OSError("no file descriptor")
        return self._original.fileno()

    def __getattr__(self, name):              # anything else a stream has (errors, buffer...)
        if self._original is None:
            raise AttributeError(name)
        return getattr(self._original, name)


def _open() -> Optional[TextIO]:
    global _size
    try:
        handle = open(_path, "a", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        return None
    try:
        _size = os.path.getsize(_path)
    except OSError:
        _size = 0
    return handle


def _write(text) -> None:
    global _size
    if not isinstance(text, str) or not text:
        return
    with _lock:
        if _handle is None:
            return
        try:
            _handle.write(text)
            _size += len(text)
            if _size > MAX_BYTES:
                _rotate()
        except Exception:
            pass


def _rotate() -> None:
    """(with the lock held) Start a new file, keeping the last one as spellbook.log.1."""
    global _handle
    try:
        _handle.close()
    except Exception:
        pass
    try:
        os.replace(_path, _path + ".1")
    except OSError:
        pass
    _handle = _open()


def install(started: Optional[str] = None, pid: Optional[int] = None) -> None:
    """Start copying stdout and stderr into the log (safe to call more than once)."""
    global _handle, _path
    if _handle is not None:
        return
    try:
        _path = log_path()
    except Exception:
        return
    _handle = _open()
    if _handle is None:
        return
    started = started or time.strftime("%Y-%m-%d %H:%M:%S")
    _write("\n" + start_line(started, os.getpid() if pid is None else pid) + "\n")
    if not isinstance(sys.stdout, _Tee):
        sys.stdout = _Tee(sys.stdout)
    if not isinstance(sys.stderr, _Tee):
        sys.stderr = _Tee(sys.stderr)


def tail(limit: int = 6000, path: Optional[str] = None) -> str:
    """The end of the log (newest last), starting on a whole line; "" if there is none."""
    path = path or _path or log_path()
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit * 2))
            data = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    text = data[-limit:]
    if len(data) > limit and "\n" in text:
        text = text.split("\n", 1)[1]
    return text.strip()
