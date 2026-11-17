"""Small helpers for placing and filling dialog windows, and for the main window's remembered size and place."""

import re
import tkinter as tk


def center_on_parent(window, parent, *, root_coords: bool = True, clamp: bool = False):
    """Move ``window`` to the middle of ``parent``.

    ``root_coords`` places it from the parent's position on the screen (``winfo_rootx``); without it the parent's
    position within its own toplevel is used. ``clamp`` keeps the window from starting off the top or left edge.
    """
    window.update_idletasks()
    if root_coords:
        left, top = parent.winfo_rootx(), parent.winfo_rooty()
    else:
        left, top = parent.winfo_x(), parent.winfo_y()
    x = left + (parent.winfo_width() - window.winfo_width()) // 2
    y = top + (parent.winfo_height() - window.winfo_height()) // 2
    if clamp:
        x, y = max(x, 0), max(y, 0)
    window.geometry(f"+{x}+{y}")


def add_cancel_save(parent, theme, on_cancel, on_confirm, *, confirm_text: str = "Save", confirm_width: int = 100,
                    cancel_width: int = 100, outlined: bool = False, accent: bool = False):
    """The Cancel / Save pair at the bottom right of a dialog; returns ``(cancel_button, confirm_button)``.

    The default look is the themed one (grey Cancel, green Save). ``outlined`` is the editors' look: an outlined
    Cancel and an accent-coloured Save; ``accent`` is a grey Cancel with an accent-coloured confirm button.
    The caller packs ``parent`` itself, so this only fills it."""
    import customtkinter as ctk

    if accent:
        cancel = ctk.CTkButton(parent, text="Cancel", width=cancel_width,
                               fg_color=theme.get_current_color('button_normal'),
                               hover_color=theme.get_current_color('button_hover'), command=on_cancel)
        cancel.pack(side="right", padx=(10, 0))
        confirm = ctk.CTkButton(parent, text=confirm_text, width=confirm_width,
                                fg_color=theme.get_current_color('accent_primary'),
                                hover_color=theme.get_current_color('accent_hover'), command=on_confirm)
        confirm.pack(side="right")
        return cancel, confirm

    if outlined:
        cancel = ctk.CTkButton(parent, text="Cancel", width=cancel_width, fg_color="transparent", border_width=1,
                               command=on_cancel)
        cancel.pack(side="right", padx=(5, 0))
        confirm = ctk.CTkButton(parent, text=confirm_text, width=confirm_width,
                                fg_color=theme.get_current_color('accent_primary'), command=on_confirm)
        confirm.pack(side="right")
        return cancel, confirm

    text_color = theme.get_current_color('text_primary')
    cancel = ctk.CTkButton(parent, text="Cancel", width=cancel_width,
                           fg_color=theme.get_current_color('button_normal'),
                           hover_color=theme.get_current_color('button_hover'),
                           text_color=text_color, command=on_cancel)
    cancel.pack(side="right", padx=(10, 0))
    confirm = ctk.CTkButton(parent, text=confirm_text, width=confirm_width,
                            fg_color=theme.get_current_color('button_success'),
                            hover_color=theme.get_current_color('button_success_hover'),
                            text_color=text_color, command=on_confirm)
    confirm.pack(side="right")
    return cancel, confirm


def add_export_cancel(parent, theme, export_text: str, on_export, on_cancel):
    """The tall export dialogs' button row: an accent Export on the left and a flat Cancel on the right."""
    import customtkinter as ctk

    ctk.CTkButton(
        parent, text=export_text, width=150, height=40,
        fg_color=theme.get_current_color('accent_primary'),
        hover_color=theme.get_current_color('accent_secondary'),
        command=on_export
    ).pack(side="left")
    ctk.CTkButton(
        parent, text="Cancel", width=100, height=40,
        fg_color="transparent",
        hover_color=theme.get_current_color('bg_tertiary'),
        command=on_cancel
    ).pack(side="right")


# ---- the main window's size and place, kept from one run to the next

_GEOMETRY = re.compile(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)")


def _is_zoomed(root) -> bool:
    try:
        if root.state() == "zoomed":                 # Windows, macOS
            return True
    except tk.TclError:
        pass
    try:
        return bool(root.attributes("-zoomed"))      # X11
    except tk.TclError:
        return False


def zoom_window(root):
    """Maximise the window."""
    try:
        root.state("zoomed")
    except tk.TclError:
        try:
            root.attributes("-zoomed", True)
        except tk.TclError:
            pass


def window_memory(root, previous: str = "") -> str:
    """What to remember of the main window as it closes: "<width>x<height>+<x>+<y>", with " zoomed" after it when
    it is maximised (the size before that is then the one already remembered, since Tk only knows the full one)."""
    if _is_zoomed(root):
        old = _GEOMETRY.match(str(previous or ""))
        return ((old.group(0) + " ") if old else "") + "zoomed"
    return root.geometry()


def fit_window_memory(text: str, least: tuple, screen: tuple, origin: tuple = (0, 0), scaling: float = 1.0):
    """``(geometry, zoomed)`` to open the main window with, from what ``window_memory`` kept, or None for the default.

    ``least`` is the window's minimum (width, height), ``screen`` the desktop's size in pixels and ``origin`` its
    top-left corner (the monitors together), ``scaling`` the display scaling the width and height are multiplied by.
    The size is kept inside the desktop and the place is dropped when the window would open where it can't be
    reached: the monitor it was on is gone, or it was closed from the taskbar while minimised."""
    text = str(text or "").strip()
    zoomed = text.endswith("zoomed")
    match = _GEOMETRY.match(text)
    if not match:
        return ("", True) if zoomed else None
    width, height, x, y = (int(g) for g in match.groups())
    scaling = scaling if scaling and scaling > 0 else 1.0
    width = max(least[0], min(width, int(screen[0] / scaling)))
    height = max(least[1], min(height, int(screen[1] / scaling)))
    reach = 120                                      # this much of the title bar has to be on the desktop
    on_screen = (origin[0] - width * scaling + reach <= x <= origin[0] + screen[0] - reach
                 and origin[1] <= y <= origin[1] + screen[1] - reach)
    return f"{width}x{height}" + (f"+{x}+{y}" if on_screen else ""), zoomed


def restore_window(root, text: str, least: tuple = (900, 600)) -> bool:
    """Size and place the main window as it was left. Returns whether it should be maximised once it is shown."""
    try:
        scaling = float(getattr(root, "_get_window_scaling", lambda: 1.0)())
        fit = fit_window_memory(text, least, (root.winfo_vrootwidth(), root.winfo_vrootheight()),
                                (root.winfo_vrootx(), root.winfo_vrooty()), scaling)
        if fit is None:
            return False
        if fit[0]:
            root.geometry(fit[0])
        return fit[1]
    except (tk.TclError, ValueError, TypeError):
        return False
