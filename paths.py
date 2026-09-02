"""
Cross-platform path resolution for the Spellbook application.

There are two kinds of path the app cares about:

* **Resource paths** - read-only files bundled with the app (official-content
  JSON, the icon, the ``tools`` package). In a PyInstaller build these are
  unpacked into the temporary ``sys._MEIPASS`` directory; running from source
  they sit next to the code. Use :func:`resource_path`.

* **User-data paths** - writable files the app creates and rewrites
  (``spellbook.db``, ``settings.json``, ``characters.json``,
  ``character_sheets.json``, ``custom_theme.json`` and the ``backups`` folder).
  Where these live depends on how the app is running:

  =====================  =================================================
  Running from source    the project directory (unchanged dev behaviour)
  Frozen on Windows      the folder containing the .exe (portable, unchanged)
  Frozen on macOS        ~/Library/Application Support/Spellbook
  Frozen on Linux        $XDG_DATA_HOME/Spellbook  (or ~/.local/share/...)
  =====================  =================================================

  A macOS ``.app`` bundle is read-only (writing inside it also breaks the code
  signature), so the historical "write next to the executable" approach is not
  portable. Everything writable goes through :func:`user_data_dir`.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

APP_NAME = "Spellbook"


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_path(name: str = "") -> str:
    """Absolute path to a bundled, read-only resource.

    ``name`` is a path relative to the app root, e.g. ``"classes.json"`` or
    ``os.path.join("tools", "spell_data.py")``. Called with no argument it
    returns the resource root directory.
    """
    if is_frozen():
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name) if name else base


def _frozen_user_data_dir() -> str:
    """Writable data directory for a frozen build, per platform."""
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~/Library/Application Support"), APP_NAME
        )
    if sys.platform == "win32":
        # Preserve the historical "portable" behaviour: data lives next to the
        # .exe. This is also more robust than the old bare relative paths, which
        # depended on the process working directory.
        return os.path.dirname(sys.executable)
    # Linux / other POSIX - follow the XDG base-directory spec.
    xdg = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(xdg, APP_NAME)


_cached_dir: Optional[str] = None


def user_data_dir() -> str:
    """Absolute path to this user's writable Spellbook data directory.

    The directory is created on first call. When running from source this is
    the project directory, so the repo-local ``spellbook.db`` / ``settings.json``
    that developers already have keep working unchanged.
    """
    global _cached_dir
    if _cached_dir is not None:
        return _cached_dir

    if is_frozen():
        path = _frozen_user_data_dir()
    else:
        path = os.path.dirname(os.path.abspath(__file__))

    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        # If we genuinely can't create it, fall back to the cwd so the app can
        # still limp along rather than crash on import.
        path = os.path.abspath(".")
    _cached_dir = path
    return path


def user_data_path(name: str) -> str:
    """Absolute path to a writable user-data file inside :func:`user_data_dir`."""
    return os.path.join(user_data_dir(), name)
