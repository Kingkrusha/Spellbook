"""
Windows limits a process to 10,000 USER objects (windows, menus) by default, and every
CustomTkinter widget is several native windows. A few tabs of heavy pages (a class's detail
alone is ~800 widgets) can reach the limit, and then Windows refuses to create anything more:
"No more menus can be allocated", and the app is unusable.

This module just *measures* the process's handle count and lets the window ask for room.
The policy (what to give up, in which order) lives in ``MainWindow``; it registers itself here
with ``set_reclaimer`` so views that are about to do something heavy can call
``ensure_headroom()`` without knowing about tabs.

On other platforms there is no such limit and every function here is a no-op.
"""

import sys
from typing import Callable, Optional

DEFAULT_QUOTA = 10000

# Fractions of the quota
BACKGROUND_LIMIT = 0.45   # above this, unneeded pages are released gradually, in the background
BUILD_LIMIT = 0.62        # above this, room is made *before* building another page
TARGET = 0.40             # what reclaiming frees down to

_quota: Optional[int] = None
_user32 = None
_process = None
_reclaimer: Optional[Callable[[], None]] = None


def _init():
    global _user32, _process, _quota
    if _user32 is not None or sys.platform != "win32":
        return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        user32.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetGuiResources.restype = ctypes.c_uint
        _process = kernel32.GetCurrentProcess()
        _user32 = user32
    except Exception:
        _user32 = None
        return
    try:   # the quota can be changed by the user in the registry
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows") as key:
            value, _ = winreg.QueryValueEx(key, "USERProcessHandleQuota")
            _quota = int(value) if int(value) > 1000 else DEFAULT_QUOTA
    except Exception:
        _quota = DEFAULT_QUOTA


def quota() -> int:
    _init()
    return _quota or DEFAULT_QUOTA


def user_handles() -> Optional[int]:
    """The process's USER object count, or None where that is not measurable."""
    _init()
    if _user32 is None:
        return None
    try:
        count = int(_user32.GetGuiResources(_process, 1))   # 1 = GR_USEROBJECTS
        return count if count > 0 else None
    except Exception:
        return None


def level() -> Optional[float]:
    """Handle use as a fraction of the quota (None if unknown)."""
    count = user_handles()
    return None if count is None else count / quota()


def over(limit_fraction: float) -> bool:
    current = level()
    return current is not None and current > limit_fraction


def set_reclaimer(callback: Optional[Callable[[], None]]) -> None:
    """The window registers the function that frees handles."""
    global _reclaimer
    _reclaimer = callback


def ensure_headroom() -> None:
    """Call before building something big: frees pages if the process is close to the limit."""
    if _reclaimer is not None and over(BUILD_LIMIT):
        try:
            _reclaimer()
        except Exception as e:
            print(f"Handle budget: could not free handles: {e}")


def is_out_of_handles_error(exc: BaseException) -> bool:
    """True for the error Tk raises when Windows refuses to create another window or menu."""
    text = str(exc).lower()
    return ("no more menus" in text or "can't create" in text or "cannot create" in text
            or "not enough" in text or "out of memory" in text or "quota" in text)
