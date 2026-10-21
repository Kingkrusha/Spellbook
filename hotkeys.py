"""
Keyboard shortcuts (hotkeys).

Every shortcut is an *action* (an id, a label, a group and a default key) that
the main window gives a function to run. The user can rebind or clear any of
them in Settings > Keyboard Shortcuts; only the changes from the defaults are
saved, in ``AppSettings.hotkeys`` (action id -> key, "" for no key).

Keys are written in a platform-neutral form such as ``"Ctrl+Shift+F"`` or
``"F5"``. "Ctrl" is the Command key on macOS, so the same defaults feel native
there. ``tk_sequences()`` turns a key into the Tk event patterns to bind.

Tk's text boxes and entries come with built-in Ctrl+letter bindings left over
from Emacs (Ctrl+F moves the cursor, Ctrl+K deletes to the end of the line,
...). Those run *before* an app-wide binding, so ``HotkeyManager`` also binds
each shortcut on the Text and Entry classes, where it replaces the built-in
binding (and puts it back when the shortcut is changed). Copy, paste, cut,
undo, redo and select-all are reserved and can't be used as shortcuts.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

IS_MAC = sys.platform == "darwin"

# Modifier names in the order they are written
MODIFIERS = ("Ctrl", "Alt", "Shift")

# Keys that keep their usual meaning in every text field
RESERVED = {"Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+Z", "Ctrl+Y", "Ctrl+A", "Ctrl+Shift+Z"}

# Readable names for Tk keysyms that aren't a single character
_KEY_NAMES = {
    "Tab": "Tab", "ISO_Left_Tab": "Tab", "Return": "Enter", "KP_Enter": "Enter",
    "Escape": "Esc", "BackSpace": "Backspace", "Delete": "Delete", "Insert": "Insert",
    "Home": "Home", "End": "End", "Prior": "PageUp", "Next": "PageDown",
    "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right", "space": "Space",
    "comma": ",", "period": ".", "slash": "/", "semicolon": ";", "minus": "-",
    "equal": "=", "bracketleft": "[", "bracketright": "]", "apostrophe": "'",
    "grave": "`", "backslash": "\\",
}
# ... and back again, for building Tk patterns
_KEYSYMS = {
    "Tab": "Tab", "Enter": "Return", "Esc": "Escape", "Backspace": "BackSpace",
    "Delete": "Delete", "Insert": "Insert", "Home": "Home", "End": "End",
    "PageUp": "Prior", "PageDown": "Next", "Up": "Up", "Down": "Down", "Left": "Left",
    "Right": "Right", "Space": "space", ",": "comma", ".": "period", "/": "slash",
    ";": "semicolon", "-": "minus", "=": "equal", "[": "bracketleft",
    "]": "bracketright", "'": "apostrophe", "`": "grave", "\\": "backslash",
}
# Shifted digits and symbols on a US keyboard: Shift+1 arrives as "exclam"
_SHIFTED = {
    "exclam": "1", "at": "2", "numbersign": "3", "dollar": "4", "percent": "5",
    "asciicircum": "6", "ampersand": "7", "asterisk": "8", "parenleft": "9",
    "parenright": "0", "less": ",", "greater": ".", "question": "/", "colon": ";",
    "underscore": "-", "plus": "=", "braceleft": "[", "braceright": "]",
    "quotedbl": "'", "asciitilde": "`", "bar": "\\",
}
_MODIFIER_KEYSYMS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
    "Super_L", "Super_R", "Caps_Lock", "Num_Lock", "ISO_Level3_Shift", "Mode_switch",
}


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    group: str
    default: str = ""


# Every action a shortcut can run. The main window supplies the functions.
ACTIONS: List[Action] = [
    # Tabs
    Action("tab.new", "New tab", "Tabs", "Ctrl+T"),
    Action("tab.close", "Close tab", "Tabs", "Ctrl+W"),
    Action("tab.next", "Next tab", "Tabs", "Ctrl+Tab"),
    Action("tab.previous", "Previous tab", "Tabs", "Ctrl+Shift+Tab"),
    Action("tab.duplicate", "Duplicate tab", "Tabs", ""),
    *[Action(f"tab.go{n}", f"Go to tab {n}", "Tabs", f"Ctrl+{n}") for n in range(1, 9)],
    Action("tab.last", "Go to last tab", "Tabs", "Ctrl+9"),
    # Pages (open in the current tab)
    Action("page.home", "Home", "Pages", "Alt+Home"),
    Action("page.collections", "Collections", "Pages", ""),
    Action("page.characters", "Characters", "Pages", ""),
    Action("page.game_tools", "Game Tools", "Pages", ""),
    Action("page.spells", "Spells", "Pages", ""),
    Action("page.feats", "Feats", "Pages", ""),
    Action("page.lineages", "Lineages", "Pages", ""),
    Action("page.backgrounds", "Backgrounds", "Pages", ""),
    Action("page.classes", "Classes", "Pages", ""),
    Action("page.equipment", "Equipment", "Pages", ""),
    Action("page.magic_items", "Magic Items", "Pages", ""),
    Action("page.monsters", "Monsters", "Pages", ""),
    Action("page.rules", "Rules", "Pages", ""),
    Action("page.session", "Session", "Pages", ""),
    Action("page.initiative", "Initiative", "Pages", ""),
    Action("page.dice_analyzer", "Dice Analyzer", "Pages", ""),
    Action("page.matchup", "Matchup", "Pages", ""),
    Action("page.random_tables", "Random Tables", "Pages", ""),
    Action("page.calendar", "Calendar", "Pages", ""),
    Action("page.pdf_library", "PDF Library", "Pages", ""),
    Action("page.settings", "Settings", "Pages", "Ctrl+,"),
    # This page
    Action("view.refresh", "Refresh page", "This page", "F5"),
    Action("view.search", "Search this page", "This page", "Ctrl+F"),
    Action("view.clear_filters", "Clear filters", "This page", "Ctrl+Shift+X"),
    Action("view.global_search", "Search all collections", "This page", "Ctrl+K"),
    # Text formatting (in description editors)
    Action("text.bold", "Bold", "Text formatting", "Ctrl+B"),
    Action("text.italic", "Italic", "Text formatting", "Ctrl+I"),
    Action("text.spell", "Insert spell link", "Text formatting", "Ctrl+Shift+L"),
    Action("text.table", "Insert table", "Text formatting", ""),
    # Settings
    Action("toggle.appearance", "Switch light / dark mode", "Settings", "Ctrl+Shift+D"),
    Action("toggle.legacy", "Cycle legacy content filter", "Settings", ""),
    Action("toggle.chat_overlay", "Show / hide chat overlay", "Settings", ""),
]

ACTIONS_BY_ID: Dict[str, Action] = {a.id: a for a in ACTIONS}
GROUPS: List[str] = list(dict.fromkeys(a.group for a in ACTIONS))


# ---------------------------------------------------------------------------
# Writing keys


def normalize(key: str) -> str:
    """A key in its canonical written form ("shift+ctrl+f" -> "Ctrl+Shift+F"), or "" if unusable."""
    if not key:
        return ""
    parts = [p.strip() for p in key.replace(" ", "").split("+")]
    # "Ctrl++" style: a trailing empty part means the plus key, which we don't support
    if any(not p for p in parts):
        return ""
    mods, main = parts[:-1], parts[-1]
    aliases = {"control": "Ctrl", "ctrl": "Ctrl", "cmd": "Ctrl", "command": "Ctrl",
               "alt": "Alt", "option": "Alt", "shift": "Shift"}
    out_mods = set()
    for m in mods:
        name = aliases.get(m.lower())
        if name is None:
            return ""
        out_mods.add(name)
    if main.lower() in aliases:
        return ""  # a modifier on its own
    if len(main) == 1:
        main = main.upper()
    else:
        main = next((k for k in _KEYSYMS if k.lower() == main.lower()), main)
        if main.upper().startswith("F") and main[1:].isdigit():
            main = "F" + main[1:]
        elif main not in _KEYSYMS:
            return ""
    return "+".join([m for m in MODIFIERS if m in out_mods] + [main])


def display(key: str) -> str:
    """How a key is shown to the user on this platform."""
    key = normalize(key)
    if not key:
        return ""
    if IS_MAC:
        return key.replace("Ctrl+", "Cmd+").replace("Alt+", "Option+")
    return key


def is_usable(key: str) -> bool:
    """A shortcut needs a modifier, unless it is a function key; some keys are reserved."""
    key = normalize(key)
    if not key or key in RESERVED:
        return False
    *mods, main = key.split("+")
    is_function_key = main.startswith("F") and main[1:].isdigit()
    if is_function_key:
        return True
    return bool(set(mods) & {"Ctrl", "Alt"})


def tk_sequences(key: str) -> List[str]:
    """The Tk event patterns that fire for ``key``.

    A letter is bound in lower and upper case, so the shortcut still works with
    Caps Lock on; Shift+Tab is "ISO_Left_Tab" on Linux.
    """
    key = normalize(key)
    if not key:
        return []
    *mods, main = key.split("+")
    tk_mods = []
    for m in mods:
        if m == "Ctrl":
            tk_mods.append("Command" if IS_MAC else "Control")
        elif m == "Alt":
            tk_mods.append("Option" if IS_MAC else "Alt")
        else:
            tk_mods.append("Shift")
    prefix = "-".join(tk_mods) + "-" if tk_mods else ""
    if len(main) == 1 and main.isalpha():
        if "Shift" in mods:
            keysyms = [main.upper()]
        else:
            keysyms = [main.lower(), main.upper()]
    elif len(main) == 1 and main.isdigit():
        keysyms = [main]
    else:
        keysyms = [_KEYSYMS.get(main, main)]
        if main == "Tab" and "Shift" in mods and sys.platform.startswith("linux"):
            keysyms.append("ISO_Left_Tab")
    return [f"<{prefix}KeyPress-{k}>" for k in keysyms]


def from_event(keysym: str, state: int) -> str:
    """The key written for a Tk KeyPress (keysym + modifier state), or "" for a bare modifier."""
    if not keysym or keysym in _MODIFIER_KEYSYMS:
        return ""
    mods = []
    if IS_MAC:
        ctrl = bool(state & 0x0008)        # Command
        alt = bool(state & 0x0010)         # Option
    elif sys.platform == "win32":
        ctrl = bool(state & 0x0004)
        alt = bool(state & 0x20000)        # (0x0008 is Num Lock on Windows)
    else:
        ctrl = bool(state & 0x0004)
        alt = bool(state & 0x0008)         # Mod1
    shift = bool(state & 0x0001) or keysym == "ISO_Left_Tab"
    if ctrl:
        mods.append("Ctrl")
    if alt:
        mods.append("Alt")
    if keysym in _SHIFTED:
        keysym = _SHIFTED[keysym]
        shift = True
    if shift:
        mods.append("Shift")
    main = _KEY_NAMES.get(keysym)
    if main is None:
        if len(keysym) == 1:
            main = keysym.upper()
        elif keysym.startswith("F") and keysym[1:].isdigit():
            main = keysym
        elif keysym.startswith("KP_") and keysym[3:].isdigit():
            main = keysym[3:]
        else:
            return ""
    return normalize("+".join(mods + [main]))


# ---------------------------------------------------------------------------
# The user's bindings


def bindings(overrides: Optional[Dict[str, str]]) -> Dict[str, str]:
    """Action id -> key for every action: the defaults with the user's changes on top."""
    overrides = overrides or {}
    out = {}
    for action in ACTIONS:
        key = overrides.get(action.id, action.default)
        out[action.id] = normalize(key) if key else ""
    return out


def conflicts(table: Dict[str, str]) -> Dict[str, List[str]]:
    """Keys bound to more than one action (key -> action ids)."""
    by_key: Dict[str, List[str]] = {}
    for action_id, key in table.items():
        if key:
            by_key.setdefault(key, []).append(action_id)
    return {k: v for k, v in by_key.items() if len(v) > 1}


def set_binding(overrides: Optional[Dict[str, str]], action_id: str, key: str) -> Dict[str, str]:
    """New overrides with ``action_id`` bound to ``key`` ("" clears it).

    Any other action that had the same key loses it, so one key never runs two
    things. Overrides equal to the default are dropped.
    """
    overrides = dict(overrides or {})
    key = normalize(key)
    if key:
        for other, other_key in bindings(overrides).items():
            if other != action_id and other_key == key:
                overrides[other] = ""
    overrides[action_id] = key
    return {a: k for a, k in overrides.items()
            if a in ACTIONS_BY_ID and normalize(k) != normalize(ACTIONS_BY_ID[a].default)}


def reset_binding(overrides: Optional[Dict[str, str]], action_id: str) -> Dict[str, str]:
    """New overrides with ``action_id`` back on its default key (taken from whoever has it now)."""
    default = ACTIONS_BY_ID[action_id].default
    out = {a: k for a, k in (overrides or {}).items() if a != action_id}
    if default:
        out = set_binding(out, action_id, default)
    return out


# ---------------------------------------------------------------------------
# Binding them in Tk


class HotkeyManager:
    """Binds every shortcut on a Tk app and runs the matching action.

    ``handlers`` maps action ids to functions taking no arguments; an action
    without a handler is simply not bound. A handler that returns False lets
    the key do what it would normally do (for example Ctrl+B outside a text
    editor).
    """

    WIDGET_CLASSES = ("Text", "Entry")

    def __init__(self, root, handlers: Dict[str, Callable[[], Optional[bool]]],
                 overrides: Optional[Dict[str, str]] = None):
        self.root = root
        self.handlers = dict(handlers)
        self._bound: List[Tuple[str, str]] = []           # (tag, sequence) we bound
        self._saved_class: Dict[Tuple[str, str], str] = {}  # original class scripts we replaced
        self.enabled = True
        self.apply(overrides)

    def apply(self, overrides: Optional[Dict[str, str]]):
        """(Re)bind everything from the user's overrides."""
        self._unbind_all()
        self.table = bindings(overrides)
        for action_id, key in self.table.items():
            if not key or action_id not in self.handlers or not is_usable(key):
                continue
            for seq in tk_sequences(key):
                self._bind("all", seq, action_id)
                for cls in self.WIDGET_CLASSES:
                    self._bind(cls, seq, action_id)

    def run(self, action_id: str) -> bool:
        """Run an action now. True when it did something."""
        handler = self.handlers.get(action_id)
        if handler is None or not self.enabled:
            return False
        try:
            return handler() is not False
        except Exception as e:
            print(f"Shortcut {action_id} failed: {e}")
            return True

    # -- internals

    def _from_main_window(self, event) -> bool:
        try:
            return event.widget.winfo_toplevel() == self.root.winfo_toplevel()
        except Exception:
            return True  # widget already gone, or a plain string path: don't block the key

    def _bind(self, tag: str, seq: str, action_id: str):
        def fire(event, action_id=action_id):
            if not self._from_main_window(event):
                return None  # a dialog is in front: leave its keys alone
            return "break" if self.run(action_id) else None

        try:
            if tag in self.WIDGET_CLASSES and (tag, seq) not in self._saved_class:
                self._saved_class[(tag, seq)] = self.root.bind_class(tag, seq)
            self.root.bind_class(tag, seq, fire)
            self._bound.append((tag, seq))
        except Exception as e:  # an odd key this Tk doesn't know
            print(f"Could not bind {seq}: {e}")

    def _unbind_all(self):
        for tag, seq in self._bound:
            try:
                original = self._saved_class.pop((tag, seq), None)
                if original:
                    self.root.bind_class(tag, seq, original)
                else:
                    self.root.unbind_class(tag, seq)
            except Exception:
                pass
        self._bound = []


_manager: Optional[HotkeyManager] = None


def install(root, handlers, overrides=None) -> HotkeyManager:
    """Create the app's hotkey manager (one per app)."""
    global _manager
    _manager = HotkeyManager(root, handlers, overrides)
    return _manager


def get_manager() -> Optional[HotkeyManager]:
    return _manager


def actions_in(group: str) -> Iterable[Action]:
    return (a for a in ACTIONS if a.group == group)
