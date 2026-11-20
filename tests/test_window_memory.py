"""The main window opens the size and in the place it was closed (ui/window_utils.py)."""

import pytest

from ui.window_utils import fit_window_memory, restore_window, window_memory

LEAST = (900, 600)
SCREEN = (1920, 1080)


def test_nothing_remembered_means_the_default_size():
    assert fit_window_memory("", LEAST, SCREEN) is None
    assert fit_window_memory("not a window", LEAST, SCREEN) is None
    assert fit_window_memory(None, LEAST, SCREEN) is None
    assert fit_window_memory(42, LEAST, SCREEN) is None


def test_the_size_and_place_come_back():
    assert fit_window_memory("1400x900+200+80", LEAST, SCREEN) == ("1400x900+200+80", False)
    assert fit_window_memory("1400x900+200+80 zoomed", LEAST, SCREEN) == ("1400x900+200+80", True)
    assert fit_window_memory("zoomed", LEAST, SCREEN) == ("", True)


def test_a_window_bigger_than_the_screen_is_cut_down_to_it():
    """Remembered on a large monitor, opened on a laptop."""
    assert fit_window_memory("2400x1300+0+0", LEAST, (1366, 768)) == ("1366x768+0+0", False)
    # ... and with the display scaled to 150%, the same pixels hold a smaller window
    assert fit_window_memory("1800x1000+0+0", LEAST, SCREEN, scaling=1.5) == ("1280x720+0+0", False)
    # never under the window's minimum
    assert fit_window_memory("300x200+10+10", LEAST, SCREEN) == ("900x600+10+10", False)


@pytest.mark.parametrize("place", ["+-32000+-32000",          # closed from the taskbar while minimised (Windows)
                                   "+2500+100",               # on a second monitor that is no longer there
                                   "+100+1060",               # title bar under the bottom of the screen
                                   "+-1300+100"])             # all but a sliver off the left edge
def test_a_place_that_cannot_be_reached_is_forgotten_but_the_size_is_kept(place):
    assert fit_window_memory("1400x900" + place, LEAST, SCREEN) == ("1400x900", False)


def test_a_second_monitor_to_the_left_counts_as_on_screen():
    assert fit_window_memory("1400x900+-1800+50", LEAST, (3840, 1080), origin=(-1920, 0)) == \
        ("1400x900+-1800+50", False)


def test_a_real_window_is_remembered_and_put_back(tk_root):
    # (a plain Tk window: on Windows a CustomTkinter pop-up hides itself for a moment after it is made, to colour
    # its title bar, and a hidden window reports its old size)
    import tkinter as tk
    window = tk.Toplevel(tk_root)
    try:
        window.geometry("940x620+60+40")
        window.update()
        kept = window_memory(window)
        assert kept.startswith("940x620+")

        window.geometry("1000x700+10+10")
        window.update()
        assert restore_window(window, kept) is False
        window.update()
        assert window.geometry().startswith("940x620")

        assert restore_window(window, "garbage") is False          # nothing to restore: left as it is
        window.update()
        assert window.geometry().startswith("940x620")
    finally:
        window.destroy()


def test_the_remembered_window_stays_on_this_computer():
    """It is about this computer's screens: a backup doesn't carry it to another one."""
    import backup
    from settings import AppSettings
    assert "window_geometry" in backup.LOCAL_SETTINGS
    assert AppSettings.from_dict({"window_geometry": "1400x900+200+80"}).window_geometry == "1400x900+200+80"
