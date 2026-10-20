"""Small helpers for placing and filling dialog windows."""


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
