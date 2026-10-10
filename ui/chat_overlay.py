"""The chat overlay: a panel at the bottom of the app that follows you to every page while a
session is running. It can be collapsed to a small "💬 Chat" button (which counts messages
you haven't seen) and expanded again.

Translucency
------------
Tk cannot blend one widget with what is behind it; the only alpha it has is per *window*.
So on Windows the expanded panel is two frameless windows stacked over the app:

* a backdrop window, solid colour at partial alpha (``lan_overlay_opacity``), and
* a front window on top of it whose background is a "key" colour that Windows treats as fully
  transparent (``-transparentcolor``) - only the text and the input controls are actually drawn,
  at full opacity, over the translucent backdrop.

Everywhere else (macOS, Linux) - or if the user turns translucency off - the panel is an ordinary
opaque frame placed over the app inside its window, which needs no OS support. (A macOS
implementation using ``-transparent`` / ``systemTransparent`` is possible but has not been
tried, so it is not enabled.)
"""

from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.chat_input import ChatInput
from ui.chat_render import ChatLog

PANEL_MAX_WIDTH = 760
PANEL_HEIGHT = 250
SIDE_MARGIN = 20

IS_WINDOWS = sys.platform == "win32"


def _hex(widget, color) -> str:
    """Any Tk colour as ``#rrggbb``."""
    r, g, b = widget.winfo_rgb(color)
    return f"#{r >> 8:02x}{g >> 8:02x}{b >> 8:02x}"


def _nudge(color: str) -> str:
    """A colour one step away from ``color``, used as the transparency key so that it can never be
    exactly equal to a colour a visible widget uses."""
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    b = b + 1 if b < 255 else b - 1
    return f"#{r:02x}{g:02x}{b:02x}"


def _no_activate(window) -> None:
    """Windows: clicks on this window must not activate it, or it would be raised over the
    front window and wash out the text."""
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        window.update_idletasks()
        user32 = ctypes.windll.user32
        hwnd = user32.GetAncestor(window.winfo_id(), 2)       # GA_ROOT
        GWL_EXSTYLE, WS_EX_NOACTIVATE = -20, 0x08000000
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
    except Exception:
        pass


class _Content:
    """The chat widgets: a header with the collapse button, the log, and the input row."""

    def __init__(self, parent, service, bg: str, on_collapse: Callable[[], None], popup_parent):
        theme = get_theme_manager()
        header = ctk.CTkFrame(parent, fg_color=bg)
        header.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(header, text="💬 Session chat", font=ui_font("body", bold=True),
                     fg_color=bg, text_color=theme.get_current_color('text_primary')).pack(side="left")
        ctk.CTkButton(header, text="▼", width=30, height=22, font=ui_font("small"),
                      fg_color=theme.get_current_color('button_normal'),
                      hover_color=theme.get_current_color('button_hover'),
                      command=on_collapse).pack(side="right")

        # The input row is packed first (at the bottom) so the log can never squeeze it out
        self.input = ChatInput(parent, service, bg=bg)
        self.input.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        body = ctk.CTkFrame(parent, fg_color=bg)
        body.pack(fill="both", expand=True, padx=4, pady=4)
        self.text = tk.Text(
            body, wrap="word", height=6, state="disabled", relief="flat", bd=0, highlightthickness=0,
            padx=8, pady=4, bg=bg, fg=theme.get_current_color('text_primary'), font=ui_font("body"),
            insertbackground=theme.get_current_color('text_primary'), cursor="arrow",
            selectbackground=theme.get_current_color('accent_primary'))
        scroll = ctk.CTkScrollbar(body, command=self.text.yview, fg_color=bg, width=12)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.log = ChatLog(self.text, service, popup_parent=popup_parent)   # popups outlive the panel

    def scroll(self, event) -> None:
        delta = getattr(event, "delta", 0)
        if delta:
            self.text.yview_scroll(-3 if delta > 0 else 3, "units")


class _InlinePanel:
    """Opaque panel placed over the app inside its own window (works everywhere)."""

    def __init__(self, overlay: "ChatOverlay"):
        self.overlay = overlay
        theme = get_theme_manager()
        bg = theme.get_current_color('bg_secondary')
        self.frame = ctk.CTkFrame(overlay.main, fg_color=bg, border_width=1, corner_radius=10,
                                  border_color=theme.get_current_color('border'))
        self.content = _Content(self.frame, overlay.service, bg, overlay.collapse, lambda: overlay.root)
        self.reposition()

    @property
    def log(self) -> ChatLog:
        return self.content.log

    def reposition(self) -> None:
        o = self.overlay
        width = max(320, min(PANEL_MAX_WIDTH, o.main.winfo_width() - 2 * SIDE_MARGIN))
        self.frame.place(relx=0.5, rely=1.0, y=-o.bottom_offset(), anchor="s", width=width, height=PANEL_HEIGHT)
        self.frame.lift()

    def lift(self) -> None:
        self.frame.lift()

    def destroy(self) -> None:
        try:
            self.frame.destroy()
        except Exception:
            pass


class _FloatingPanel:
    """Windows: translucent backdrop window + front window with a see-through background."""

    def __init__(self, overlay: "ChatOverlay"):
        self.overlay = overlay
        root = overlay.root
        theme = get_theme_manager()
        base = _hex(root, theme.get_current_color('bg_secondary'))
        self.key = _nudge(base)

        self.back = tk.Toplevel(root)
        self.front = tk.Toplevel(root)
        for win in (self.back, self.front):
            win.withdraw()
            win.overrideredirect(True)
            win.configure(bg=self.key)
            win.transient(root)
        self.back.attributes("-alpha", overlay.opacity)
        self.front.attributes("-transparentcolor", self.key)
        _no_activate(self.back)

        self.content = _Content(self.front, overlay.service, self.key, overlay.collapse, lambda: overlay.root)
        for win in (self.back, self.front):
            win.bind("<MouseWheel>", self.content.scroll)
        self.content.text.bind("<MouseWheel>", self.content.scroll)
        self.reposition()
        self.back.deiconify()
        self.front.deiconify()
        self.front.lift()

    @property
    def log(self) -> ChatLog:
        return self.content.log

    def set_opacity(self, value: float) -> None:
        self.back.attributes("-alpha", value)

    def reposition(self) -> None:
        o = self.overlay
        m = o.main
        m.update_idletasks()
        width = max(320, min(PANEL_MAX_WIDTH, m.winfo_width() - 2 * SIDE_MARGIN))
        x = m.winfo_rootx() + (m.winfo_width() - width) // 2
        y = m.winfo_rooty() + m.winfo_height() - o.bottom_offset() - PANEL_HEIGHT
        geometry = f"{width}x{PANEL_HEIGHT}+{x}+{y}"
        self.back.geometry(geometry)
        self.front.geometry(geometry)

    def lift(self) -> None:
        self.back.lift()
        self.front.lift()

    def destroy(self) -> None:
        for win in (self.front, self.back):
            try:
                win.destroy()
            except Exception:
                pass


class ChatOverlay:
    """Owns the overlay's state (shown / collapsed / unread) and whichever panel is up."""

    def __init__(self, main, service, settings_manager, bottom_offset: Callable[[], int]):
        self.main = main
        self.root = main.winfo_toplevel()
        self.service = service
        self.settings_manager = settings_manager
        self.bottom_offset = bottom_offset

        self.suppressed = False            # the page itself shows the chat (the Session page)
        self._panel = None
        self._toggle: Optional[ctk.CTkButton] = None
        self._unread = 0
        self._reposition_after = None
        self._rebuild_after = None

        service.add_listener(self._on_event)
        get_theme_manager().add_listener(self._on_theme)
        for widget in (main, self.root):
            widget.bind("<Configure>", self._on_configure, add="+")

    # ---------------------------------------------------------------- settings

    def _setting(self, key: str, default):
        return getattr(self.settings_manager.settings, key, default)

    def _save(self, **values) -> None:
        try:
            self.settings_manager.update(**values)
        except Exception:
            pass

    @property
    def enabled(self) -> bool:
        return bool(self._setting("lan_overlay_enabled", True))

    @property
    def collapsed(self) -> bool:
        return bool(self._setting("lan_overlay_collapsed", False))

    @property
    def opacity(self) -> float:
        return max(0.2, min(0.95, float(self._setting("lan_overlay_opacity", 0.6))))

    @property
    def supports_translucency(self) -> bool:
        return IS_WINDOWS

    @property
    def translucent(self) -> bool:
        return self.supports_translucency and bool(self._setting("lan_overlay_translucent", True))

    def set_enabled(self, value: bool) -> None:
        self._save(lan_overlay_enabled=bool(value))
        self.refresh()

    def set_opacity(self, value: float) -> None:
        self._save(lan_overlay_opacity=round(float(value), 2))
        if isinstance(self._panel, _FloatingPanel):
            self._panel.set_opacity(self.opacity)

    # ------------------------------------------------------------------ showing

    def collapse(self) -> None:
        self._save(lan_overlay_collapsed=True)
        self.refresh()

    def expand(self) -> None:
        self._save(lan_overlay_collapsed=False)
        self._unread = 0
        self.refresh()

    def refresh(self) -> None:
        """Show whatever should be showing right now (nothing, the button, or the panel)."""
        want = self.service.in_session and self.enabled and not self.suppressed
        if not want:
            self._hide_panel()
            self._hide_toggle()
        elif self.collapsed:
            self._hide_panel()
            self._show_toggle()
        else:
            self._hide_toggle()
            self._show_panel()

    def _show_toggle(self) -> None:
        theme = get_theme_manager()
        if self._toggle is None:
            self._toggle = ctk.CTkButton(
                self.main, text="", width=120, height=26, corner_radius=13, font=ui_font("small", bold=True),
                fg_color=theme.get_current_color('bg_tertiary'),
                hover_color=theme.get_current_color('button_hover'),
                text_color=theme.get_current_color('text_primary'),
                border_width=1, border_color=theme.get_current_color('border'),
                command=self.expand)
        self._toggle.configure(text="💬 Chat" + (f"  ({self._unread})" if self._unread else ""))
        self._toggle.place(relx=0.5, rely=1.0, y=-self.bottom_offset(), anchor="s")
        self._toggle.lift()

    def _hide_toggle(self) -> None:
        if self._toggle is not None:
            self._toggle.destroy()
            self._toggle = None

    def _show_panel(self) -> None:
        if self._panel is None:
            panel = None
            if self.translucent:
                try:
                    panel = _FloatingPanel(self)
                except Exception as e:
                    print(f"Translucent chat overlay unavailable, using a solid panel: {e}")
            if panel is None:
                panel = _InlinePanel(self)
            self._panel = panel
            panel.log.set_lines(self.service.chat[-200:])
        else:
            self._panel.reposition()
        self._panel.lift()

    def _hide_panel(self) -> None:
        if self._panel is not None:
            self._panel.destroy()
            self._panel = None

    # ------------------------------------------------------------------- events

    def _on_event(self, kind: str, **data) -> None:
        if kind == "line":
            line = data["line"]
            if self._panel is not None:
                self._panel.log.append(line)
            elif (self._toggle is not None and not line.get("mine")
                  and (line["kind"] in ("chat", "dm", "roll") or line.get("alert"))):
                self._unread += 1
                self._show_toggle()
        elif kind in ("state", "ended"):
            if not self.service.in_session:
                self._unread = 0
            self.refresh()

    def _on_configure(self, event) -> None:
        if event.widget not in (self.main, self.root):
            return
        if self._reposition_after is None:
            self._reposition_after = self.root.after(30, self._reposition)

    def _reposition(self) -> None:
        self._reposition_after = None
        try:
            if self._panel is not None:
                self._panel.reposition()
            if self._toggle is not None:
                self._toggle.place(relx=0.5, rely=1.0, y=-self.bottom_offset(), anchor="s")
        except Exception:
            pass

    def _on_theme(self) -> None:
        """Colours (and the see-through key colour) are baked in when the panel is built."""
        if self._panel is not None and self._rebuild_after is None:
            self._rebuild_after = self.root.after(80, self._rebuild)

    def _rebuild(self) -> None:
        self._rebuild_after = None
        if self._panel is not None:
            self._hide_panel()
            self._hide_toggle()
            self.refresh()

    def shutdown(self) -> None:
        try:
            get_theme_manager().remove_listener(self._on_theme)
        except Exception:
            pass
        self._hide_panel()
        self._hide_toggle()
