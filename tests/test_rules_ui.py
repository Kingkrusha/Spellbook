"""The Rules collection page and the text viewer it shows pages in, driven through the widgets."""

import time

import pytest

import rules as R
from ui.rule_text import Seg, fit_columns, inline_segments, link_segments, wrap_words

PAGE = """Intro with a [[rule:Combat|link]] and **bold** and *italic*.

# First Heading

Some text about stunned creatures.

• one
• two [[rule:Conditions#Stunned]]
  • nested

| Name | Cost | Notes |
|---|---|---|
| [[equipment:Club|Club]] | 1 SP | A long note that will have to wrap inside its column when there is not enough room |
| Dagger | 2 GP | Short |

## Sub Heading

More text.

# Second Heading

The end.
"""


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture(autouse=True)
def fresh_fonts(tk_root):
    """The shared role fonts belong to the Tk interpreter that first made them; an earlier test module's
    root is gone by now, and the viewer measures text with them, so they are made again for this one."""
    from typography import get_font_manager
    get_font_manager().scope.refresh()


@pytest.fixture
def host(tk_root):
    import customtkinter as ctk
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    tk_root.geometry("1300x860")
    yield frame
    frame.destroy()


# --------------------------------------------------------------------------- pure helpers

def test_inline_segments_nest_links_in_emphasis():
    segs = inline_segments("*[[spell:Fireball]]* and **[[feat:Alert|alert]]** plus Value* and 2 * 3")
    assert [(s.link, s.bold, s.italic) for s in segs if s.link] == [("spell:Fireball", False, True),
                                                                    ("feat:Alert|alert", True, False)]
    assert "".join(s.text for s in segs).endswith("plus Value* and 2 * 3")
    assert [s.text for s in link_segments("[[rule:Conditions#Stunned]] x") if s.link] == ["Stunned"]
    assert inline_segments("unclosed *italic and **bold") == [Seg("unclosed *italic and **bold")]


def test_columns_use_the_room_there_is():
    assert fit_columns([100, 300], [40, 60], 500, 10) == [100, 300]
    narrow = fit_columns([100, 300], [40, 60], 250, 10)
    assert sum(narrow) + 10 == pytest.approx(250)
    assert narrow[0] >= 40 and narrow[1] >= 60 and narrow[0] <= 100 and narrow[1] <= 300
    assert fit_columns([100, 300], [90, 200], 100, 10) == [90, 200]       # cannot go below the longest word
    assert fit_columns([], [], 100, 10) == []


def test_words_wrap_to_the_column():
    width = lambda w: len(w[0]) * 7
    words = [(t, False, False, None) for t in ("hello", "big", "wide", "world")]
    lines = wrap_words(words, 90, width, 7)
    assert [[w[0] for w in line] for line in lines] == [["hello", "big"], ["wide", "world"]]
    assert wrap_words([], 90, width, 7) == [[]]
    assert [[w[0] for w in line] for line in wrap_words(words[:1], 10, width, 7)] == [["hello"]]


# --------------------------------------------------------------------------- the text viewer

def test_the_viewer_draws_headings_lists_tables_and_links(host, tk_root):
    from ui.rule_text import RuleTextView
    clicked = []
    view = RuleTextView(host, on_link=lambda cat, name: clicked.append((cat, name)))
    view.pack(fill="both", expand=True)
    view.set_markup(PAGE)
    pump(tk_root)
    text = view.plain_text()
    for needle in ("Intro with a link and bold and italic.", "First Heading", "Sub Heading", "Second Heading",
                   "two Stunned", "nested", "Dagger", "Short"):
        assert needle in text, needle
    assert "**" not in text and "[[" not in text
    assert [view.has_section(i) for i in (1, 2, 3, 4)] == [True, True, True, False]
    # the table is laid out in columns separated by tabs, the long note wrapped over several lines
    table_lines = [l for l in text.split("\n") if "\t" in l]
    assert len(table_lines) >= 4 and all(l.count("\t") == 2 for l in table_lines)
    assert sum(1 for l in table_lines if "Club" in l or "Dagger" in l) == 2
    # clicking a link tells the page
    link_tags = [t for t in view.text.tag_names() if t.startswith("lk")]
    assert len(link_tags) >= 3
    from types import SimpleNamespace
    seen = set()
    for tag in link_tags:
        start = view.text.tag_ranges(tag)[0]
        view.text.see(start)
        tk_root.update()
        bbox = view.text.bbox(start)
        if bbox:
            view._on_link_click(SimpleNamespace(x=bbox[0] + 2, y=bbox[1] + 2))
            seen.add(clicked[-1])
    view._on_link_click(SimpleNamespace(x=1, y=1))            # a click that hits no link does nothing
    assert ("rule", "Combat") in seen and ("rule", "Conditions#Stunned") in seen
    assert ("equipment", "Club") in seen
    view.destroy()


def test_the_viewer_lights_up_matches_and_steps_through_them(host, tk_root):
    from ui.rule_text import RuleTextView
    view = RuleTextView(host)
    view.pack(fill="both", expand=True)
    view.set_markup(PAGE, query="text")
    pump(tk_root)
    assert view.hit_count == 2                       # "text" in two paragraphs
    pos, total = view.goto_hit(0)
    assert (pos, total) == (0, 2)
    assert view.next_hit(1) == (1, 2)
    assert view.next_hit(1) == (0, 2)                # wraps round
    assert view.next_hit(-1) == (1, 2)
    first_in_second = view.hit_near_section(3)
    assert first_in_second in (0, 1)
    view.set_query("")
    assert view.hit_count == 0
    view.set_query("stunned")
    assert view.hit_count >= 1
    view.destroy()


def test_the_viewer_scrolls_to_a_section(host, tk_root):
    from ui.rule_text import RuleTextView
    view = RuleTextView(host)
    view.pack(fill="both", expand=True)
    lots = "\n\n".join(f"# Section {i}\n\n" + "Filler text for the section. " * 40 for i in range(1, 30))
    view.set_markup(lots)
    pump(tk_root, 0.5)
    view.scroll_to_section(20)
    pump(tk_root, 0.3)
    top = view.text.index("@0,0")
    assert view.text.compare(top, ">=", "sec19") or view.text.compare(top, "<=", "sec20")
    assert view.text.yview()[0] > 0.3
    view.scroll_to_section(0)
    pump(tk_root)
    assert view.text.yview()[0] == 0.0
    view.destroy()


def test_tables_reflow_when_the_room_changes(host, tk_root):
    from ui.rule_text import RuleTextView
    view = RuleTextView(host)
    view.pack(fill="both", expand=True)
    room = {"width": 1200}
    view._available_width = lambda: room["width"]             # (a withdrawn test window cannot be resized)
    view.set_markup(PAGE)
    pump(tk_root, 0.4)
    wide = view.plain_text().count("\n")
    room["width"] = 260
    view._relayout()                                          # what a resize ends up calling
    narrow = view.plain_text().count("\n")
    assert narrow > wide                                      # the long note needs more lines in less room
    assert view._laid_out_width == 260
    room["width"] = 1200
    view._relayout()
    assert view.plain_text().count("\n") == wide
    view.destroy()


# --------------------------------------------------------------------------- the page

@pytest.fixture
def view(host, tk_root):
    from ui.rules_view import RulesView
    v = RulesView(host, on_back=lambda: None)
    v.pack(fill="both", expand=True)
    pump(tk_root, 0.4)
    yield v
    v.destroy()


def search(view, tk_root, text):
    view.search_var.set(text)
    pump(tk_root, 0.5)


def test_the_page_lists_the_whole_book(view):
    assert len(view.list_panel._items) == 67
    assert view.list_panel.get_selected() is None
    assert view.edit_btn.cget("state") == "disabled" and view.delete_btn.cget("state") == "disabled"


def test_searching_stunned_opens_the_conditions_page_at_stunned(view, tk_root):
    search(view, tk_root, "stunned")
    items = view.list_panel._items
    assert items[0].page.name == "Conditions" and items[0].section_title == "Stunned"
    selected = view.list_panel.get_selected()
    assert selected is items[0]
    assert view.detail_panel.name_label.cget("text") == "Conditions"
    assert view.detail_panel.text_view.hit_count >= 2           # the heading and "have the Stunned condition"
    assert "of" in view.detail_panel.match_label.cget("text")
    pump(tk_root, 0.6)
    tv = view.detail_panel.text_view
    heading_line = tv.text.index(f"sec{items[0].section}").split(".")[0]
    assert tv.text.index("@0,0").split(".")[0] == heading_line      # the page opens with Stunned at the top


def test_clearing_the_search_keeps_the_page_open_without_highlights(view, tk_root):
    search(view, tk_root, "stunned")
    search(view, tk_root, "")
    assert len(view.list_panel._items) == 67
    assert view.list_panel.get_selected().name == "Conditions"
    assert view.detail_panel.text_view.hit_count == 0


def test_search_results_are_ranked_by_relevance(view, tk_root):
    search(view, tk_root, "hit points")
    names = [i.page.name for i in view.list_panel._items]
    assert names[0] in ("Damage and Healing", "Rules Definitions")
    scores = [i.score for i in view.list_panel._items]
    assert scores == sorted(scores, reverse=True)
    search(view, tk_root, "zzzqqq")
    assert view.list_panel._items == []
    assert view.detail_panel.name_label.cget("text") == "Select a rules page"


def test_titles_only_and_filters(view, tk_root):
    search(view, tk_root, "right yourself")
    assert view.list_panel._items and view.list_panel._items[0].page.name == "Conditions"
    view.titles_var.set(True)
    view._apply_filters_now()
    assert view.list_panel._items == []
    view.titles_var.set(False)
    search(view, tk_root, "")
    view.category_var.set("Equipment")
    view._apply_filters_now()
    assert {i.category for i in view.list_panel._items} == {"Equipment"}
    view.category_var.set("All Categories")
    view._selected_tags = ["Traps"]
    view._apply_filters_now()
    assert {i.name for i in view.list_panel._items} >= {"Hidden Pit", "Spiked Pit", "Traps"}
    assert all("Traps" in i.tags for i in view.list_panel._items)
    view._clear_filters()
    pump(tk_root, 0.3)
    assert len(view.list_panel._items) == 67
    view.official_var.set("Homebrew Only")
    view._apply_filters_now()
    assert view.list_panel._items == []
    view._clear_filters()
    pump(tk_root, 0.3)
    view.sort_var.set("A to Z")
    view._apply_filters_now()
    names = [i.name for i in view.list_panel._items]
    assert names == sorted(names, key=str.lower)


def test_select_rule_opens_a_section_and_links_move_within_the_page(view, tk_root):
    assert view.select_rule("Conditions#Stunned")
    pump(tk_root, 0.6)
    assert view.detail_panel.name_label.cget("text") == "Conditions"
    assert view.list_panel.get_selected().name == "Conditions"
    assert view.select_rule("Stunned")                      # a bare title finds it too
    assert view.select_rule("Nonexistent Page") is False
    # following a link: the new page opens, Back returns
    view._on_rule_link("rule", "Combat")
    pump(tk_root, 0.4)
    assert view.detail_panel.name_label.cget("text") == "Combat"
    assert view.detail_panel.back_btn.cget("state") == "normal"
    view._go_back()
    pump(tk_root, 0.4)
    assert view.detail_panel.name_label.cget("text") == "Conditions"
    assert view.detail_panel.back_btn.cget("state") == "disabled"
    # a link to a section of the page that is open just scrolls
    view._on_rule_link("rule", "Conditions#Prone")
    assert view.detail_panel.name_label.cget("text") == "Conditions"


def test_following_a_link_while_searching_clears_the_search(view, tk_root):
    search(view, tk_root, "stunned")
    view._on_rule_link("rule", "Combat")
    pump(tk_root, 0.5)
    assert view.search_var.get() == ""
    assert view.list_panel.get_selected().name == "Combat"
    assert view.detail_panel.text_view.hit_count == 0


def test_jump_list_names_the_sections_of_the_page(view, tk_root):
    view.select_rule("Conditions")
    pump(tk_root, 0.5)
    choices = view.detail_panel.jump_combo.cget("values")
    assert choices[0] == "Jump to section..."
    assert "Stunned" in choices and "Blinded" in choices
    view.detail_panel._on_jump("Stunned")
    pump(tk_root, 0.3)
    assert view.detail_panel.text_view.text.yview()[0] > 0.2


def test_adding_editing_and_deleting_your_own_page(view, tk_root, monkeypatch):
    from tkinter import messagebox
    from ui import rules_view as rv

    class FakeDialog:
        def __init__(self, parent, title, page=None):
            self.result = R.RulePage(
                name="Table Rule", category="House Rules", description="# Snacks\n\nBring snacks.",
                tags=["Social"], is_official=False, is_custom=True) if page is None else R.RulePage(
                name="Table Rule", category="House Rules", description="# Snacks\n\nBring good snacks.",
                tags=["Social"], is_official=False, is_custom=True)

    monkeypatch.setattr(rv, "RuleEditorDialog", FakeDialog)
    monkeypatch.setattr(view, "wait_window", lambda w: None)
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    try:
        view._on_add()
        pump(tk_root, 0.5)
        assert view.list_panel.get_selected().name == "Table Rule"
        assert view.edit_btn.cget("state") == "normal" and view.delete_btn.cget("state") == "normal"
        assert "* Table Rule" == view.list_panel.row_text(view.list_panel.get_selected())
        search(view, tk_root, "snacks")
        assert view.list_panel._items[0].page.name == "Table Rule"
        search(view, tk_root, "")
        view.select_rule("Table Rule")
        view._on_edit()
        pump(tk_root, 0.5)
        assert "good snacks" in view.detail_panel.text_view.plain_text()
        view._on_delete()
        pump(tk_root, 0.5)
        assert R.get_rules_manager().get_page("Table Rule") is None
        assert len(view.list_panel._items) == 67
    finally:
        R.get_rules_manager().delete_page("Table Rule")


# --------------------------------------------------------------------------- the link popup

def test_a_rules_link_opens_a_popup_with_the_text(host, tk_root):
    from object_links import find_target
    from ui.object_link_widgets import LinkPopup
    popup = LinkPopup(tk_root, find_target("rule", "Conditions#Stunned"))
    pump(tk_root, 0.5)
    try:
        assert popup.title() == "Stunned"
        texts = []

        def collect(widget):
            if widget.winfo_class() == "Text":
                texts.append(widget.get("1.0", "end-1c"))
            for child in widget.winfo_children():
                collect(child)
        collect(popup)
        assert any("Incapacitated" in t and "Saving Throws Affected" in t for t in texts)
    finally:
        popup.destroy()


# --------------------------------------------------------------------------- the editor

def test_the_editor_checks_what_you_type(tk_root, monkeypatch):
    from tkinter import messagebox
    from ui.rules_view import RuleEditorDialog
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda title, message, **k: errors.append(message))
    dialog = RuleEditorDialog(tk_root, "Add Rules Page")
    try:
        dialog._save()
        assert dialog.result is None and "Name is required" in errors[-1]
        dialog.name_entry.insert(0, "Combat")
        dialog.desc_text.insert("1.0", "# Mine\n\nText.")
        dialog._save()
        assert dialog.result is None and "already exists" in errors[-1]       # an official page's name
        dialog.name_entry.delete(0, "end")
        dialog.name_entry.insert(0, "Bad # Name")
        dialog._save()
        assert dialog.result is None and "cannot contain" in errors[-1]
        dialog.name_entry.delete(0, "end")
        dialog.name_entry.insert(0, "Flanking")
        dialog.source_entry.insert(0, "My Table")
        dialog.tag_editor.set_tags(["Combat"])
        dialog._save()
    finally:
        try:
            dialog.destroy()
        except Exception:
            pass
    page = dialog.result
    assert page.name == "Flanking" and page.source == "My Table" and page.tags == ["Combat"]
    assert page.is_custom and not page.is_official and page.order == 0
    assert page.category == "Homebrew" and "Mine" in page.sections[1].title


def test_the_editor_fills_in_an_existing_page(tk_root):
    from ui.rules_view import RuleEditorDialog
    page = R.RulePage(name="Flanking", category="House Rules", description="# Gang up\n\nBonus.",
                      source="My Table", tags=["Combat"], is_official=False, is_custom=True)
    dialog = RuleEditorDialog(tk_root, "Edit Rules Page", page)
    try:
        assert dialog.name_entry.get() == "Flanking" and dialog.category_var.get() == "House Rules"
        assert dialog.source_entry.get() == "My Table" and dialog.tag_editor.get_tags() == ["Combat"]
        assert dialog.desc_text.get("1.0", "end-1c") == "# Gang up\n\nBonus."
        dialog.name_entry.delete(0, "end")
        dialog.name_entry.insert(0, "Flanking Rules")            # renaming your own page is fine
        dialog._save()
        assert dialog.result.name == "Flanking Rules"
    finally:
        try:
            dialog.destroy()
        except Exception:
            pass


# --------------------------------------------------------------------------- bars and italics

def test_headings_get_a_bar_and_a_bar_line_draws_one(host, tk_root):
    from ui.rule_text import RuleTextView
    view = RuleTextView(host)
    view.pack(fill="both", expand=True)
    view.set_markup("Intro _slanted_ and *also*.\n\n# One\n\nText.\n\n## Two\n\nText.\n\n---\n\n### Three\n\nEnd.")
    pump(tk_root, 0.3)
    t = view.text
    bar_lines = {tag: [i for i in range(1, int(t.index("end").split(".")[0])) if tag in t.tag_names(f"{i}.0")]
                 for tag in ("bar1", "bar2", "hr")}
    assert len(bar_lines["bar1"]) == 2 and len(bar_lines["bar2"]) == 1     # one under each heading
    assert len(bar_lines["hr"]) == 1                                       # the "---"
    assert "---" not in view.plain_text()
    assert [view.has_section(i) for i in (1, 2, 3, 4)] == [True, True, True, False]
    assert "i" in t.tag_names(t.search("slanted", "1.0")) and "i" in t.tag_names(t.search("also", "1.0"))
    view.destroy()


def test_underscore_runs_and_words_are_not_italic():
    from ui.rule_text import inline_segments
    assert [s.italic for s in inline_segments("snake_case and Name: ____ here")] == [False]
    assert [(s.text, s.italic) for s in inline_segments("a _b_ c")][1] == ("b", True)
