"""Coloured text has to be readable on what it is drawn on (theme.py: readable, and the *_text colours).

A theme's accent, danger, success and warning colours are chosen as backgrounds: buttons, badges, bars. Used as
the colour of text they were often too dark for the dark theme (the default accent on the default panel: 1.8 : 1,
where 4.5 : 1 is what small text needs). The *_text colours are the same hues, shifted until they can be read."""

import pytest

import theme
from theme import THEME_PRESETS, contrast, readable

TEXT_ROLES = ("accent_text", "danger_text", "success_text", "warning_text")


@pytest.mark.parametrize("name", sorted(THEME_PRESETS))
def test_every_built_in_theme_has_readable_coloured_text(name):
    colors = THEME_PRESETS[name]()
    for role in TEXT_ROLES:
        pair = getattr(colors, role)
        for mode in (0, 1):                                     # light, dark
            for back in (colors.bg_primary[mode], colors.bg_secondary[mode]):
                ratio = contrast(pair[mode], back)
                assert ratio >= 4.5, f"{name} {role} {('light', 'dark')[mode]}: {pair[mode]} on {back} = {ratio:.2f}"


def test_the_default_accent_itself_could_not_be_read_as_text():
    """(Why the text colours exist: this is what headings and links used to be drawn in.)"""
    colors = THEME_PRESETS["default"]()
    assert contrast(colors.accent_primary[1], colors.bg_secondary[1]) < 3
    assert contrast(colors.accent_text[1], colors.bg_secondary[1]) >= 4.5


def test_a_colour_that_already_reads_well_is_left_alone():
    assert readable("#ffffff", "#000000") == "#ffffff"
    assert readable("#202020", "#f4f4f4") == "#202020"


def test_a_colour_is_shifted_only_as_far_as_it_takes_and_keeps_its_hue():
    purple, panel = "#6c3483", "#1a1a1a"
    assert contrast(purple, panel) < 4.5
    fixed = readable(purple, panel)
    assert contrast(fixed, panel) >= 4.5
    hue = theme._hex_to_hls(purple)[0]
    assert abs(theme._hex_to_hls(fixed)[0] - hue) < 0.02
    assert contrast(fixed, panel) < 6                           # not all the way to white


def test_white_or_black_text_is_turned_towards_the_other_when_that_reads_better():
    assert contrast(readable("#ffffff", "#ffd60a"), "#ffd60a") >= 4.5        # white on bright yellow: goes dark
    assert contrast(readable("#000000", "#0a0a2a"), "#0a0a2a") >= 4.5        # black on navy: goes light
    assert theme.readable_if_lost("#ffffff", "#059669") == "#ffffff"         # (3.8 : 1 is not lost: left alone)
    assert theme.readable_if_lost("white", "#059669") == "white"             # not #rrggbb: left alone


def test_the_text_colours_are_not_saved_with_a_theme():
    """They follow from the theme's other colours, so a saved or shared theme doesn't carry them."""
    from dataclasses import fields
    saved = {f.name for f in fields(THEME_PRESETS["default"]())}
    assert not saved & set(TEXT_ROLES)


def test_a_selected_row_keeps_its_coloured_name_readable(tk_root):
    """Magic items are listed in their rarity's colour: green on the blue of the selected row could not be read."""
    from dataclasses import dataclass
    from ui.virtual_list import VirtualListPanel

    @dataclass
    class Entry:
        name: str
        is_custom: bool = False

    class Coloured(VirtualListPanel):
        def row_text_color(self, item):
            return "#1e8449"

    panel = Coloured(tk_root, on_select=lambda item: None)
    panel.pack(fill="both", expand=True)
    panel._viewport_height = lambda: 400.0
    try:
        panel.set_items([Entry("Bag of Holding"), Entry("Cloak of Elvenkind")])
        tk_root.update()
        assert panel.select_by_name("Bag of Holding")
        tk_root.update()
        rows = {r._vl_index: r for r in panel._pool if r._vl_index != -1}
        highlight = str(panel.row_color(True))
        assert contrast("#1e8449", highlight) < 3
        assert contrast(str(rows[0].cget("text_color")), highlight) >= 4.5
        assert str(rows[1].cget("text_color")) == "#1e8449"       # the others keep the colour as it is
    finally:
        panel.destroy()
