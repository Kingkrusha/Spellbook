"""Text styles in descriptions: headings, horizontal bars and italics - how they are drawn (rules pages,
DynamicText, the line renderer) and what the editors' toolbar writes."""

import time

import pytest

from ui.rich_text_utils import (BAR_LINE_RE, DEFAULT_BOLD_PATTERN, HEADING_LINE_RE, RichTextEditor, RichTextRenderer,
                                DynamicText, render_description_blocks, split_italics)


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture(autouse=True)
def fresh_fonts(tk_root):
    from typography import get_font_manager
    get_font_manager().scope.refresh()


@pytest.fixture
def host(tk_root):
    import customtkinter as ctk
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="x", anchor="n")
    tk_root.geometry("900x700")
    yield frame
    frame.destroy()


# --------------------------------------------------------------------------- the markup

def test_line_patterns():
    assert HEADING_LINE_RE.match("## Subheading").group(1) == "##"
    assert HEADING_LINE_RE.match("#### Small").group(2) == "Small"
    assert not HEADING_LINE_RE.match("#NoSpace") and not HEADING_LINE_RE.match("##### Too deep")
    assert BAR_LINE_RE.match("---") and BAR_LINE_RE.match("-----  ")
    assert not BAR_LINE_RE.match("--") and not BAR_LINE_RE.match("--- x")


def test_italics_underscore_everywhere_and_star_only_when_free():
    assert split_italics("a _b_ c", False) == [("a ", False), ("b", True), (" c", False)]
    assert split_italics("a *b* c", True)[1] == ("b", True)
    assert split_italics("a *b* c", False) == [("a *b* c", False)]      # a lone * is the older bold there
    plain = "snake_case, Name: ____, 2 * 3 and Value*"
    assert split_italics(plain, True) == [(plain, False)]


# --------------------------------------------------------------------------- DynamicText

def tags_at(widget, needle):
    index = widget.search(needle, "1.0")
    return widget.tag_names(index)


def test_dynamic_text_draws_headings_bars_and_italics(host, tk_root):
    dt = DynamicText(host, bg_color="bg_primary")
    dt.pack(fill="x")
    dt.set_text("# Title\n\nSome _slanted_ and **bold** text.\n---\n## Sub\nTail")
    pump(tk_root)
    w = dt.text_widget
    assert "h1" in tags_at(w, "Title") and "h2" in tags_at(w, "Sub")
    assert "italic" in tags_at(w, "slanted") and "italic" not in tags_at(w, "Some")
    assert "bold" in tags_at(w, "bold")
    assert "#" not in w.get("1.0", "end") and "---" not in w.get("1.0", "end")
    bars = [i for i in range(1, int(w.index("end").split(".")[0])) if "bar3" in w.tag_names(f"{i}.0")]
    assert len(bars) == 1                                              # the "---" line
    assert w.tag_ranges("bar1")                                        # the line under the heading
    assert dt._pixel_height                                            # headings make the height pixel-exact


def test_dynamic_text_without_styles_is_unchanged(host, tk_root):
    dt = DynamicText(host, bg_color="bg_primary")
    dt.pack(fill="x")
    dt.set_text("Just **text** with a_b and 2 * 3.\nSecond line.")
    pump(tk_root)
    assert dt.text_widget.get("1.0", "end-1c") == "Just text with a_b and 2 * 3.\nSecond line."
    assert not dt._pixel_height and not dt._line_tags_ready
    assert dt.text_widget.cget("height") == 2


def test_legacy_single_asterisk_bold_keeps_its_meaning(host, tk_root):
    dt = DynamicText(host, bg_color="bg_primary")
    dt.pack(fill="x")
    dt.set_text("*Run-in.* then _italic_ and *more*", bold_pattern=r"\*([^*]+)\*")
    pump(tk_root)
    w = dt.text_widget
    assert "bold" in tags_at(w, "Run-in.") and "bold" in tags_at(w, "more")
    assert "italic" in tags_at(w, "italic")


def test_a_bar_is_a_few_pixels_tall(host, tk_root):
    widgets = render_description_blocks(host, "Before\n\n---\n\nAfter")
    pump(tk_root, 0.5)
    assert len(widgets) == 3
    assert widgets[1].winfo_reqheight() < 40                    # a bar plus a little air, not a line of text


def test_the_heading_is_cut_to_its_pixels(host, tk_root):
    widgets = render_description_blocks(host, "# Heading\n\nText")
    pump(tk_root, 0.5)
    heading, text = widgets
    assert heading.winfo_reqheight() < 60 and text.winfo_reqheight() < 30


# --------------------------------------------------------------------------- the line renderer (spell pages)

def test_formatted_text_renderer_handles_headings_bars_and_italics(host, tk_root):
    import customtkinter as ctk
    RichTextRenderer().render_formatted_text(host, "# Heading\nA _slanted_ word\n---\nPlain line")
    pump(tk_root, 0.4)
    kinds = [type(w).__name__ for w in host.winfo_children()]
    labels = [w.cget("text") for w in host.winfo_children() if isinstance(w, ctk.CTkLabel)]
    assert "Heading" in labels and "Plain line" in labels
    bars = [w for w in host.winfo_children() if isinstance(w, ctk.CTkFrame)]
    assert len(bars) == 2                                       # under the heading, and the "---"
    assert kinds.count("Text") == 1                             # the italic line is a text widget
    texts = [w for w in host.winfo_children() if w.winfo_class() == "Text"]
    assert "italic" in texts[0].tag_names(texts[0].search("slanted", "1.0"))


# --------------------------------------------------------------------------- the editor toolbar

@pytest.fixture
def editor(host, tk_root):
    import customtkinter as ctk
    box = ctk.CTkTextbox(host, height=120)
    box.pack(fill="x")
    ed = RichTextEditor(tk_root, box)
    toolbar = ed.create_toolbar(host)
    toolbar.pack(fill="x")
    pump(tk_root, 0.1)
    yield ed, box
    pump(tk_root, 0.1)                       # the link scanner runs when idle: let it before the box goes


def text_of(box):
    return box.get("1.0", "end-1c")


def test_toolbar_has_the_text_style_buttons(editor):
    ed, _box = editor
    labels = [w.cget("text") for w in ed.style_button.master.winfo_children()]
    assert labels == ["📊 Table", "✨ Spell", "B", "I", "Aa ▾", "― Bar"]


def test_heading_and_list_styles_change_the_line_prefix(editor):
    ed, box = editor
    box.insert("1.0", "First\nSecond\n\nFourth")
    box.mark_set("insert", "1.2")
    ed.apply_line_style("# ")
    assert text_of(box).split("\n")[0] == "# First"
    ed.apply_line_style("## ")                                  # replaces, never stacks
    assert text_of(box).split("\n")[0] == "## First"
    ed.apply_line_style("")
    assert text_of(box).split("\n")[0] == "First"
    box.tag_add("sel", "1.0", "4.2")                            # a selection over four lines
    ed.apply_line_style("• ")
    assert text_of(box) == "• First\n• Second\n\n• Fourth"      # the blank line is left alone
    ed.apply_line_style("1. ")
    assert text_of(box) == "1. First\n2. Second\n\n3. Fourth"
    ed.apply_line_style("")
    assert text_of(box) == "First\nSecond\n\nFourth"


def test_bar_and_italic_insertions(editor):
    ed, box = editor
    box.insert("1.0", "Above")
    box.mark_set("insert", "end-1c")
    ed.insert_bar()
    assert text_of(box) == "Above\n---\n"
    box.delete("1.0", "end")
    box.insert("1.0", "ab")
    box.mark_set("insert", "1.1")
    ed.insert_bar()                                             # in the middle of a line: it splits the line
    assert text_of(box) == "a\n---\nb"
    box.delete("1.0", "end")
    ed.insert_italic()
    assert text_of(box) == "_text_"
    box.delete("1.0", "end")
    box.insert("1.0", "slant me")
    box.tag_add("sel", "1.0", "1.5")
    ed.insert_italic()
    assert text_of(box) == "_slant_ me"
    ed.apply_line_style("### ")
    assert text_of(box).startswith("### ")
