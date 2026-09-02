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
from typing import Any


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
