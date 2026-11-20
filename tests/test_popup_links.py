"""Links inside description pop-ups open what they point to.

A class feature's pop-up (Tinker's Magic: "You know the [[spell:Mending]] cantrip ... holding
[[equipment:Tinker's Tools]]") passed the raw link markup to the spell lookup, so every link said
"Spell Not Found". Click handlers get the inside of the ``[[...]]`` token; it must be parsed first.
"""

import tkinter as tk

import pytest

from character_class import ClassAbility


@pytest.fixture
def opened(monkeypatch):
    """Record what a link click opens instead of opening windows."""
    import ui.object_link_widgets as olw
    import ui.rich_text_utils as rtu
    import ui.spell_detail as sd

    log = []

    class FakeSpellPopup:
        def __init__(self, parent, spell):
            log.append(("spell", spell.name))

        def focus(self):
            pass

    class FakeLinkPopup:
        def __init__(self, parent, target):
            log.append((target.category, target.name))

        def focus(self):
            pass

    monkeypatch.setattr(sd, "SpellPopupDialog", FakeSpellPopup)
    monkeypatch.setattr(olw, "LinkPopup", FakeLinkPopup)
    monkeypatch.setattr(rtu.messagebox, "showwarning", lambda *a, **k: log.append(("warning", a[0])))
    monkeypatch.setattr(olw.messagebox, "showwarning", lambda *a, **k: log.append(("warning", a[0])))
    return log


@pytest.mark.parametrize("inner, expected", [
    ("spell:Mending", ("spell", "Mending")),
    ("Mending", ("spell", "Mending")),                       # legacy link without a category
    ("spell:Mending|the mending cantrip", ("spell", "Mending")),
    ("equipment:Tinker's Tools", ("equipment", "Tinker's Tools")),
    ("equipment:Tinker's Tools|tools", ("equipment", "Tinker's Tools")),
])
def test_spell_popup_handler_understands_link_markup(tk_root, opened, inner, expected):
    from ui.rich_text_utils import RichTextRenderer
    renderer = RichTextRenderer()
    renderer.show_spell_popup(tk_root, inner)
    renderer.show_link_popup(tk_root, inner)
    assert opened == [expected, expected]


def test_missing_link_still_warns(tk_root, opened):
    from ui.rich_text_utils import RichTextRenderer
    RichTextRenderer().show_link_popup(tk_root, "equipment:No Such Thing")
    RichTextRenderer().show_link_popup(tk_root, "spell:No Such Spell")
    assert [kind for kind, _ in opened] == ["warning", "warning"]


def test_feature_popup_links_open_their_targets(tk_root, opened, monkeypatch):
    from ui.character_sheet_view import FeaturePopupDialog

    # keep the click handler of every link drawn, to run it as a click would
    clicks = []
    real_tag_bind = tk.Text.tag_bind

    def tag_bind(self, tagName, sequence, func=None, add=None):
        if sequence == "<Button-1>" and func is not None:
            clicks.append(func)
        return real_tag_bind(self, tagName, sequence, func, add)

    monkeypatch.setattr(tk.Text, "tag_bind", tag_bind)

    ability = ClassAbility(
        title="Tinker's Magic",
        description="You know the [[spell:Mending]] cantrip.\n\n"
                    "As a Magic action while holding *[[equipment:Tinker's Tools]]*, you can create one item.",
        tables=[{"title": "", "columns": ["Item", "Note"],
                 "rows": [["[[equipment:Rope]]", "*Bold [[spell:Light]]* text"]]}],
    )
    popup = FeaturePopupDialog(tk_root, ability, "Artificer")
    try:
        popup.update()
        for click in clicks:
            click(None)
        assert sorted(set(opened)) == [("equipment", "Rope"), ("equipment", "Tinker's Tools"),
                                       ("spell", "Light"), ("spell", "Mending")]
    finally:
        popup.grab_release()
        popup.destroy()
