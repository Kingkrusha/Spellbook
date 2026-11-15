"""The chat overlay: a panel at the bottom of the app that follows you to every page while a
session is running. It can be collapsed to a small "💬 Chat" button (which counts messages
you haven't seen) and expanded again. Both can be dragged out of the way (the button anywhere on it,
the panel by its title bar); where they were left is remembered.

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
TOP_MARGIN = 44                 # (below the tab bar)
TOGGLE_HOME = (1.0, 1.0)        # the button starts bottom right, clear of the pages' centred buttons
PANEL_HOME = (0.5, 1.0)         # the panel starts bottom centre

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


def parse_spot(text) -> Optional[tuple]:
    """``"0.25,1"`` -> ``(0.25, 1.0)``, each kept between 0 and 1; None if it isn't a position."""
    try:
        fx, fy = (float(v) for v in str(text).split(","))
    except (TypeError, ValueError):
        return None
    if fx != fx or fy != fy:                    # NaN
        return None
    return min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy))


def place_in(room: tuple, size: tuple, spot: tuple) -> tuple:
    """Top-left corner for something of ``size`` at fractions ``spot`` of ``room`` = (left, top, width,
    height): (0, 0) is the top-left corner and (1, 1) the bottom-right, always fully inside."""
    left, top, width, height = room
    w, h = size
    return (round(left + spot[0] * max(0, width - w)), round(top + spot[1] * max(0, height - h)))


def spot_of(room: tuple, size: tuple, corner: tuple) -> tuple:
    """The fractions :func:`place_in` turns back into ``corner`` (clamped inside the room)."""
    left, top, width, height = room
    w, h = size
    free_w, free_h = max(1, width - w), max(1, height - h)
    return (min(1.0, max(0.0, (corner[0] - left) / free_w)), min(1.0, max(0.0, (corner[1] - top) / free_h)))


class _Drag:
    """Press and drag on any of ``handles`` to move something; a press that doesn't move is a click.

    ``where()`` gives the thing's current top-left corner, ``move(x, y)`` puts it somewhere new while
    dragging, ``done()`` is called once when a drag ends and ``click()`` (optional) when it was a click."""

    THRESHOLD = 5           # pixels the pointer moves before a press counts as a drag

    def __init__(self, handles, where, move, done, click=None):
        self.where, self.move, self.done, self.click = where, move, done, click
        self._origin = None
        self.moved = False
        for handle in handles:
            self.attach(handle)

    def attach(self, handle) -> None:
        handle.bind("<ButtonPress-1>", self._press, add="+")
        handle.bind("<B1-Motion>", self._motion, add="+")
        handle.bind("<ButtonRelease-1>", self._release, add="+")

    def _press(self, event):
        try:
            self._origin = (event.x_root, event.y_root, self.where())
        except Exception:
            self._origin = None
        self.moved = False

    def _motion(self, event):
        if self._origin is None:
            return
        x0, y0, (left, top) = self._origin
        dx, dy = event.x_root - x0, event.y_root - y0
        if not self.moved and abs(dx) + abs(dy) < self.THRESHOLD:
            return
        self.moved = True
        self.move(left + dx, top + dy)

    def _release(self, _event):
        was_press = self._origin is not None
        self._origin = None
        if self.moved:
            self.done()
        elif was_press and self.click is not None:
            self.click()


class _Content:
    """The chat widgets: a header with the collapse button, the log, and the input row."""

    def __init__(self, parent, service, bg: str, on_collapse: Callable[[], None], popup_parent,
                 header_bg: Optional[str] = None):
        theme = get_theme_manager()
        top = header_bg or bg               # (the see-through panel needs a solid bar to grab)
        self.header = header = ctk.CTkFrame(parent, fg_color=top, corner_radius=6 if header_bg else 0)
        header.pack(fill="x", padx=10, pady=(8, 0))
        self.title = ctk.CTkLabel(header, text="💬 Session chat", font=ui_font("body", bold=True),
                                  fg_color=top, text_color=theme.get_current_color('text_primary'))
        self.title.pack(side="left", padx=(6 if header_bg else 0, 0))
        self.hint = ctk.CTkLabel(header, text="drag to move", font=ui_font("small"), fg_color=top,
                                 text_color=theme.get_text_secondary())
        self.hint.pack(side="left", padx=10)
        self.handles = (header, self.title, self.hint)
        for widget in self.handles:
            try:
                tk.Frame.configure(widget, cursor="fleur")      # (CTk's own configure has no cursor)
            except Exception:
                pass
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
        self.drag = _Drag(self.content.handles, where=lambda: self.corner, move=self.put,
                          done=overlay.save_panel_spot)
        self.corner = (0, 0)
        self.reposition()

    @property
    def log(self) -> ChatLog:
        return self.content.log

    @property
    def size(self) -> tuple:
        return self.overlay.panel_size()

    def reposition(self) -> None:
        o = self.overlay
        self.put(*place_in(o.room(), self.size, o.panel_spot()))

    def put(self, x: int, y: int) -> None:
        """Top-left corner at (x, y) in the app's own coordinates (kept inside it)."""
        o = self.overlay
        room, size = o.room(), self.size
        x, y = place_in(room, size, spot_of(room, size, (x, y)))
        self.corner = (x, y)
        # Tk's own place, in screen pixels: CTk's would scale x and y again on a high-DPI screen, and it
        # refuses a size
        tk.Place.place_configure(self.frame, x=x, y=y, anchor="nw", width=size[0], height=size[1])
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

        self.content = _Content(self.front, overlay.service, self.key, overlay.collapse, lambda: overlay.root,
                                header_bg=theme.get_current_color('bg_tertiary'))
        for win in (self.back, self.front):
            win.bind("<MouseWheel>", self.content.scroll)
        self.content.text.bind("<MouseWheel>", self.content.scroll)
        self.drag = _Drag(self.content.handles, where=lambda: self.corner, move=self.put,
                          done=overlay.save_panel_spot)
        self.corner = (0, 0)
        self.reposition()
        self.back.deiconify()
        self.front.deiconify()
        self.front.lift()

    @property
    def log(self) -> ChatLog:
        return self.content.log

    def set_opacity(self, value: float) -> None:
        self.back.attributes("-alpha", value)

    @property
    def size(self) -> tuple:
        return self.overlay.panel_size()

    def reposition(self) -> None:
        o = self.overlay
        o.main.update_idletasks()
        self.put(*place_in(o.room(), self.size, o.panel_spot()))

    def put(self, x: int, y: int) -> None:
        """Top-left corner at (x, y) in the app's own coordinates (kept inside it)."""
        o = self.overlay
        m = o.main
        room, size = o.room(), self.size
        x, y = place_in(room, size, spot_of(room, size, (x, y)))
        self.corner = (x, y)
        geometry = f"{size[0]}x{size[1]}+{m.winfo_rootx() + x}+{m.winfo_rooty() + y}"
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
        self._toggle_corner = (0, 0)
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

    # ---------------------------------------------------------------- where

    def scaling(self) -> float:
        """CTk's widget scaling (more than 1 on a high-DPI screen)."""
        try:
            return float(ctk.ScalingTracker.get_widget_scaling(self.main)) or 1.0
        except Exception:
            return 1.0

    def room(self) -> tuple:
        """(left, top, width, height), in screen pixels, that the button and the panel move in: the app
        below its tabs and above the session bar."""
        m = self.main
        scale = self.scaling()
        width, height = max(1, m.winfo_width()), max(1, m.winfo_height())
        side, top = round(SIDE_MARGIN * scale), min(round(TOP_MARGIN * scale), max(0, height // 4))
        return side, top, max(1, width - 2 * side), max(1, height - top - self.bottom_offset())

    def panel_size(self) -> tuple:
        scale = self.scaling()
        room = self.room()
        return (max(min(room[2], round(320 * scale)), min(round(PANEL_MAX_WIDTH * scale), room[2])),
                min(round(PANEL_HEIGHT * scale), max(120, room[3])))

    def toggle_spot(self) -> tuple:
        return parse_spot(self._setting("lan_overlay_toggle_pos", "")) or TOGGLE_HOME

    def panel_spot(self) -> tuple:
        return parse_spot(self._setting("lan_overlay_panel_pos", "")) or PANEL_HOME

    def save_panel_spot(self) -> None:
        panel = self._panel
        if panel is not None:
            fx, fy = spot_of(self.room(), panel.size, panel.corner)
            self._save(lan_overlay_panel_pos=f"{fx:.4f},{fy:.4f}")

    def reset_positions(self) -> None:
        """Put the button and the panel back where they start."""
        self._save(lan_overlay_toggle_pos="", lan_overlay_panel_pos="")
        self._reposition()

    def _toggle_size(self) -> tuple:
        t = self._toggle
        return max(1, t.winfo_reqwidth()), max(1, t.winfo_reqheight())

    def _put_toggle(self, x: int, y: int) -> None:
        if self._toggle is None:
            return
        room, size = self.room(), self._toggle_size()
        x, y = place_in(room, size, spot_of(room, size, (x, y)))
        self._toggle_corner = (x, y)
        tk.Place.place_configure(self._toggle, x=x, y=y, anchor="nw")     # (screen pixels; see _InlinePanel.put)
        self._toggle.lift()

    def _place_toggle(self) -> None:
        if self._toggle is not None:
            self._put_toggle(*place_in(self.room(), self._toggle_size(), self.toggle_spot()))

    def _save_toggle_spot(self) -> None:
        if self._toggle is not None:
            fx, fy = spot_of(self.room(), self._toggle_size(), self._toggle_corner)
            self._save(lan_overlay_toggle_pos=f"{fx:.4f},{fy:.4f}")

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
            # (no command: a click is told apart from a drag by _Drag, which then calls expand)
            self._toggle = ctk.CTkButton(
                self.main, text="", width=120, height=26, corner_radius=13, font=ui_font("small", bold=True),
                fg_color=theme.get_current_color('bg_tertiary'),
                hover_color=theme.get_current_color('button_hover'),
                text_color=theme.get_current_color('text_primary'),
                border_width=1, border_color=theme.get_current_color('border'))
            self._toggle_drag = _Drag([self._toggle], where=lambda: self._toggle_corner, move=self._put_toggle,
                                      done=self._save_toggle_spot, click=self.expand)
            try:
                from ui.tooltip import HoverTooltip
                HoverTooltip(self._toggle, "Open the session chat. Drag to move this button.")
            except Exception:
                pass
            self._toggle.update_idletasks()
        self._toggle.configure(text="💬 Chat" + (f"  ({self._unread})" if self._unread else ""))
        self._place_toggle()

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
            self._place_toggle()
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
