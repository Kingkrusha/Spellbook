"""The session chat overlay: where its button and panel go, and dragging them out of the way."""

import time
import types

import customtkinter as ctk
import pytest

from ui import chat_overlay as O


def pump(root, seconds=0.15):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def test_spots_are_fractions_of_the_room_and_stay_inside_it():
    room = (20, 44, 800, 500)
    assert O.place_in(room, (120, 26), (1.0, 1.0)) == (20 + 680, 44 + 474)
    assert O.place_in(room, (120, 26), (0.0, 0.0)) == (20, 44)
    corner = O.place_in(room, (120, 26), (0.25, 0.5))
    assert O.spot_of(room, (120, 26), corner) == pytest.approx((0.25, 0.5), abs=0.01)
    assert O.spot_of(room, (120, 26), (-500, 9999)) == (0.0, 1.0)        # dragged off the edge: kept inside
    assert O.parse_spot("0.3,0.9") == (0.3, 0.9)
    assert O.parse_spot("2,-1") == (1.0, 0.0)
    assert O.parse_spot("") is None and O.parse_spot("nan,1") is None and O.parse_spot("a,b") is None


class Service:
    in_session = True
    chat: list = []
    my_id = "me"

    def add_listener(self, fn):
        self.listener = fn

    def peer_name(self, pid):
        return ""


class Settings:
    def __init__(self, **values):
        base = dict(lan_overlay_enabled=True, lan_overlay_collapsed=True, lan_overlay_opacity=0.7,
                    lan_overlay_translucent=False, lan_overlay_toggle_pos="", lan_overlay_panel_pos="")
        self.settings = types.SimpleNamespace(**{**base, **values})

    def update(self, **kw):
        for k, v in kw.items():
            setattr(self.settings, k, v)
        return True


class Event:
    def __init__(self, x, y):
        self.x_root, self.y_root = x, y


@pytest.fixture()
def window(tk_root):
    win = ctk.CTkToplevel(tk_root)
    win.geometry("900x600+0+0")
    main = ctk.CTkFrame(win)
    main.pack(fill="both", expand=True)
    pump(tk_root, 0.3)
    yield win, main
    win.destroy()


def test_the_button_starts_bottom_right_and_can_be_dragged(tk_root, window):
    win, main = window
    settings = Settings()
    overlay = O.ChatOverlay(main, Service(), settings, bottom_offset=lambda: 8)
    overlay.refresh()
    pump(tk_root)
    toggle = overlay._toggle
    w, h = toggle.winfo_reqwidth(), toggle.winfo_reqheight()
    x, y = overlay._toggle_corner
    assert x + w == main.winfo_width() - overlay.room()[0]      # bottom right, clear of the centred buttons
    assert y + h == main.winfo_height() - 8
    drag = overlay._toggle_drag
    drag._press(Event(500, 500))
    drag._motion(Event(300, 200))
    drag._release(Event(300, 200))
    assert overlay._toggle_corner == (x - 200, y - 300)
    assert O.parse_spot(settings.settings.lan_overlay_toggle_pos) == pytest.approx(
        O.spot_of(overlay.room(), (w, h), (x - 200, y - 300)), abs=0.01)
    assert overlay.collapsed                                     # a drag isn't a click
    # it comes back where it was left, even after a resize
    overlay._hide_toggle()
    overlay.refresh()
    pump(tk_root)
    assert overlay._toggle_corner == (x - 200, y - 300)
    # a press without moving opens the chat
    drag = overlay._toggle_drag
    drag._press(Event(10, 10))
    drag._release(Event(11, 10))
    pump(tk_root)
    assert not overlay.collapsed and overlay._panel is not None
    overlay.reset_positions()
    assert settings.settings.lan_overlay_toggle_pos == "" and settings.settings.lan_overlay_panel_pos == ""
    overlay.shutdown()


def test_the_panel_moves_by_its_title_bar(tk_root, window):
    win, main = window
    settings = Settings(lan_overlay_collapsed=False)
    overlay = O.ChatOverlay(main, Service(), settings, bottom_offset=lambda: 8)
    overlay.refresh()
    pump(tk_root)
    panel = overlay._panel
    x, y = panel.corner
    assert y + panel.size[1] == main.winfo_height() - 8          # starts at the bottom, in the middle
    panel.drag._press(Event(400, 400))
    panel.drag._motion(Event(400, 200))
    panel.drag._release(Event(400, 200))
    assert panel.corner == (x, y - 200)
    panel.drag._press(Event(400, 400))
    panel.drag._motion(Event(400, -900))                         # (not past the tabs)
    panel.drag._release(Event(400, -900))
    assert panel.corner == (x, overlay.room()[1])
    panel.drag._press(Event(400, 400))
    panel.drag._motion(Event(400, 542))
    panel.drag._release(Event(400, 542))
    assert settings.settings.lan_overlay_panel_pos
    overlay.collapse()
    overlay.expand()
    pump(tk_root)
    assert overlay._panel.corner == (x, overlay.room()[1] + 142)
    overlay.shutdown()
