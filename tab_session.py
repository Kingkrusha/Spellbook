"""
Remembers which tabs were open, so the app can reopen them on the next start.

Kept in its own small file (open_tabs.json in the user data folder) rather than in
settings.json: it is session state that changes on every navigation, not a preference.

File format::

    {"tabs": [{"page": "collections", "collection": "spells", "character": null}, ...],
     "active": 0}
"""

import json
import os
from typing import List, Tuple

from atomic_io import atomic_write_json
from paths import user_data_path

FILE_NAME = "open_tabs.json"


def _path() -> str:
    return user_data_path(FILE_NAME)


def save_tabs(tabs: List[dict], active: int) -> bool:
    """Write the open tabs (in order) and the index of the active one."""
    try:
        atomic_write_json(_path(), {"tabs": tabs, "active": active})
        return True
    except Exception as e:
        print(f"Could not save open tabs: {e}")
        return False


def load_tabs() -> Tuple[List[dict], int]:
    """The saved tabs and active index; ([], 0) if there is nothing usable."""
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        tabs = [t for t in data.get("tabs", []) if isinstance(t, dict) and isinstance(t.get("page"), str)]
        active = data.get("active", 0)
        return tabs, active if isinstance(active, int) else 0
    except Exception:
        return [], 0


def clear_tabs() -> None:
    """Forget the saved tabs (e.g. when the user turns the feature off)."""
    try:
        os.remove(_path())
    except OSError:
        pass
