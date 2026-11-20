"""Drop-downs grow with the text size (ui/dropdown_width.py), so long choices aren't cut off with larger text."""

import customtkinter as ctk
import pytest

import typography
from typography import get_font_manager, ui_font
from ui import dropdown_width
from ui.restyle import install_creation_hook

install_creation_hook()


@pytest.fixture
def text_size():
    """Set the body text size (points over the normal 13) for a test, and put it back after."""
    manager = get_font_manager()
    role = manager.settings.roles["body"]
    before = role.size

    def set_delta(delta):
        role.size = typography.ROLE_STOCK_SIZE["body"] + delta
        manager.apply(save=False)

    set_delta(0)
    yield set_delta
    role.size = before
    manager.apply(save=False)


@pytest.mark.parametrize("kind", [ctk.CTkComboBox, ctk.CTkOptionMenu])
def test_the_normal_text_size_keeps_the_width_it_was_made_with(kind, tk_root, text_size):
    box = kind(tk_root, width=150, values=["All Alignments"])
    assert box._desired_width == 150
    plain = kind(tk_root, values=["A"])                       # (CustomTkinter's own default)
    assert plain._desired_width == 140
    box.destroy()
    plain.destroy()


@pytest.mark.parametrize("kind", [ctk.CTkComboBox, ctk.CTkOptionMenu])
def test_larger_text_widens_it_and_back_again(kind, tk_root, text_size):
    box = kind(tk_root, width=150, values=["All Alignments"], font=ui_font("body"))
    text_size(6)
    box.configure(font=ui_font("body"))                       # (what the restyle pass does after a change)
    wide = box._desired_width
    assert 150 * 1.3 < wide <= 150 * dropdown_width.MAX_GROWTH
    box.configure(width=100)                                  # a new width is grown the same way
    assert box._desired_width == round(100 * wide / 150) or abs(box._desired_width - 100 * wide / 150) <= 1
    text_size(0)
    box.configure(font=ui_font("body"))
    assert box._desired_width == 100
    made_large = kind(tk_root, width=120, values=["x"])
    assert made_large._desired_width == 120
    box.destroy()
    made_large.destroy()


def test_it_still_measures_after_an_earlier_window_was_closed(tk_root, text_size):
    """(The test windows come and go; so does a Tk in the app's own tests and tools.)"""
    other = ctk.CTk()
    box = ctk.CTkComboBox(other, width=150, values=["x"], font=ui_font("body"))
    text_size(6)
    box.configure(font=ui_font("body"))
    other.destroy()
    text_size(4)
    again = ctk.CTkComboBox(tk_root, width=150, values=["x"], font=ui_font("body"))
    assert again._desired_width > 150 * 1.2
    again.destroy()
