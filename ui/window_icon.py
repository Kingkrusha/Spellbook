"""
Application window icon handling.

Two problems this module solves on Windows:

1. CustomTkinter force-sets its own feather icon. ``CTk`` does it unless the app
   has already called ``iconbitmap``/``wm_iconbitmap`` (which our old code never
   did - it only called ``iconphoto``). ``CTkToplevel`` is worse: every dialog
   schedules ``self.after(200, lambda: self.iconbitmap(<CustomTkinter .ico>))``
   unconditionally in ``__init__``. So every window ends up with the CTk logo.

2. Without an explicit AppUserModelID, Windows groups the taskbar button under
   the host process (``pythonw.exe`` when run from source) and shows its icon.

`install()` fixes both: it sets the AppUserModelID, applies our icon to the root
window, and monkeypatches ``CTkToplevel`` so every dialog re-applies our icon
*after* CustomTkinter's delayed override runs.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk

from paths import resource_path

APP_USER_MODEL_ID = "Spellbook.DnD.Manager"

_ICO_NAME = "Spellbook Icon.ico"
_PNG_NAME = "Spellbook Icon.png"

# Keep a reference to the PhotoImage so Tk doesn't garbage-collect it.
_icon_photo = None
_installed = False


def _ico_path() -> str | None:
    p = resource_path(_ICO_NAME)
    return p if os.path.exists(p) else None


def _png_path() -> str | None:
    p = resource_path(_PNG_NAME)
    return p if os.path.exists(p) else None


def set_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> None:
    """Tell Windows this process is its own app, so the taskbar uses our icon.

    Must run before the first window is created to be fully effective.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def apply_icon(window) -> None:
    """Best-effort: put the Spellbook icon on ``window`` (a Tk/CTk window)."""
    global _icon_photo

    ico = _ico_path()
    if ico and sys.platform == "win32":
        try:
            # On a CTk window this also sets the internal
            # `_iconbitmap_method_called` flag, suppressing CTk's own override.
            window.iconbitmap(ico)
        except Exception:
            pass

    # iconphoto works everywhere and covers the alt-tab / Linux/macOS cases.
    png = _png_path()
    if png:
        try:
            if _icon_photo is None:
                try:
                    from PIL import Image, ImageTk

                    _icon_photo = ImageTk.PhotoImage(Image.open(png))
                except Exception:
                    _icon_photo = tk.PhotoImage(file=png)
            window.iconphoto(False, _icon_photo)
        except Exception:
            pass


def _patch_ctk_toplevel() -> None:
    """Make every CTkToplevel re-assert our icon after CTk's delayed override."""
    try:
        import customtkinter as ctk
    except Exception:
        return

    if getattr(ctk.CTkToplevel, "_spellbook_icon_patched", False):
        return

    original_init = ctk.CTkToplevel.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Immediately (harmless) and again after CTk's own after(200) fires.
        apply_icon(self)
        for delay in (260, 600):
            try:
                self.after(delay, lambda w=self: apply_icon(w))
            except Exception:
                pass

    ctk.CTkToplevel.__init__ = patched_init
    ctk.CTkToplevel._spellbook_icon_patched = True


def install(root) -> None:
    """One-time setup: AppUserModelID + root icon + CTkToplevel patch."""
    global _installed
    set_app_user_model_id()
    apply_icon(root)
    # CTk's root override also runs on a delay - re-assert after it.
    for delay in (260, 600):
        try:
            root.after(delay, lambda: apply_icon(root))
        except Exception:
            pass
    if not _installed:
        _patch_ctk_toplevel()
        _installed = True
