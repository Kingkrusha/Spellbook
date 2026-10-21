"""
Sending "add something new" to the Homebrew Studio instead of a stand-alone editor window.

The Add buttons of the collection pages call ``open_in_studio`` first; it returns True when it opened a Studio tab
(the setting *Add buttons open the Homebrew Studio* is on, and the page is inside the main window), and False when the
caller should open its own editor dialog as before.
"""

from __future__ import annotations

from typing import Optional


def studio_enabled() -> bool:
    try:
        from settings import get_settings_manager
        return bool(getattr(get_settings_manager().settings, "studio_for_new_content", True))
    except Exception:
        return True


def main_window_of(widget):
    """The MainWindow that holds ``widget`` (anything with an ``open_studio_new`` method), or None."""
    w = widget
    while w is not None:
        if callable(getattr(w, "open_studio_new", None)):
            return w
        w = getattr(w, "master", None)
    return None


def open_in_studio(widget, kind: str, *, name: str = "", record: Optional[dict] = None, parent: str = "") -> bool:
    """Open a new Studio tab on a new draft of ``kind``; False if the caller should use its own editor."""
    if not studio_enabled():
        return False
    window = main_window_of(widget)
    if window is None:
        return False
    try:
        window.open_studio_new(kind, name=name, record=record, parent=parent)
        return True
    except Exception as e:                       # never leave the Add button dead
        print(f"Could not open the Homebrew Studio: {e}")
        return False
