"""
RuleTextView: shows a rules page (or a part of one) in a single read-only text widget.

A page is long (the glossary is 60 KB) and full of tables, so it is drawn the cheap way: one
``tk.Text`` for the whole page, however many headings, lists, links and tables it has. Tables are
laid out here: each column's width is worked out from the text in it and the room there is, cells are
wrapped to their column, and the row's lines are separated by tab stops. (A widget per table cell
would put a long table in the hundreds of Windows handles; see ui/handle_budget.py.)

The markup is the one described in rules.py. The pure helpers (``inline_segments``, ``fit_columns``,
``wrap_words``) have no Tk in them so they can be tested on their own.
"""

from __future__ import annotations

import bisect
import re
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from rules import (_HEADING_RE, _LINK_RE, _LIST_LINE_RE, find_matches, parse_table, split_blocks)
from theme import get_theme_manager
from typography import ui_font


# --------------------------------------------------------------------------- #
# Inline markup
# --------------------------------------------------------------------------- #

@dataclass
class Seg:
    """A run of text with one style: bold, italic, and/or the inside of the ``[[...]]`` it came from."""
    text: str
    bold: bool = False
    italic: bool = False
    link: Optional[str] = None


_PLACEHOLDER_BASE = 0xE000          # a private-use character stands in for each link while emphasis is parsed
_DELIM_RE = re.compile(r"\*\*|\*|(?<!_)_(?!_)")      # a run of underscores ("Name: ____") is not emphasis
_BAR_RE = re.compile(r"-{3,}")                           # a line of its own: a horizontal bar
_OPENERS_BEFORE_ITALIC = set("([{\"“‘'—–-/")


def inline_segments(text: str) -> List[Seg]:
    """Split markup into styled segments. ``**bold**``, ``*italic*`` / ``_italic_`` and ``[[links]]``
    (which may sit inside emphasis); an asterisk that does not open and close a span ("Value*")
    stays as it is."""
    links: List[str] = []

    def hide(m):
        links.append(m.group(1))
        return chr(_PLACEHOLDER_BASE + len(links) - 1)

    flat = _LINK_RE.sub(hide, text)

    delims = []     # (start, end, kind, can_open, can_close)
    for m in _DELIM_RE.finditer(flat):
        kind = m.group(0)
        prev = flat[m.start() - 1] if m.start() > 0 else " "
        nxt = flat[m.end()] if m.end() < len(flat) else " "
        if kind == "**":
            can_open, can_close = not nxt.isspace(), not prev.isspace()
        else:
            can_open = not nxt.isspace() and (prev.isspace() or prev in _OPENERS_BEFORE_ITALIC)
            can_close = not prev.isspace() and (nxt.isspace() or not nxt.isalnum())
        delims.append((m.start(), m.end(), kind, can_open, can_close))

    matched: Dict[int, str] = {}              # delimiter start -> "open" | "close"
    stack: List[Tuple[int, str]] = []
    for start, _end, kind, can_open, can_close in delims:
        if can_close:
            for depth in range(len(stack) - 1, -1, -1):
                if stack[depth][1] == kind:
                    matched[stack[depth][0]] = "open"
                    matched[start] = "close"
                    del stack[depth:]
                    break
            else:
                if can_open:
                    stack.append((start, kind))
        elif can_open:
            stack.append((start, kind))

    segs: List[Seg] = []
    bold = italic = False
    buf: List[str] = []

    def flush():
        if buf:
            segs.append(Seg("".join(buf), bold, italic))
            buf.clear()

    i = 0
    by_start = {d[0]: d for d in delims}
    while i < len(flat):
        d = by_start.get(i)
        if d is not None and i in matched:
            flush()
            if d[2] == "**":
                bold = matched[i] == "open"
            else:
                italic = matched[i] == "open"
            i = d[1]
            continue
        ch = flat[i]
        code = ord(ch)
        if _PLACEHOLDER_BASE <= code < _PLACEHOLDER_BASE + len(links):
            flush()
            segs.append(Seg("", bold, italic, links[code - _PLACEHOLDER_BASE]))
        else:
            buf.append(ch)
        i += 1
    flush()
    # a link's shown text is filled in by the caller (it needs the object-link parser)
    return segs


def link_segments(text: str) -> List[Seg]:
    """``inline_segments`` with each link's shown text filled in."""
    from object_links import parse_link_markup
    out = []
    for seg in inline_segments(text):
        if seg.link is not None:
            seg = Seg(parse_link_markup(seg.link)[2], seg.bold, seg.italic, seg.link)
        out.append(seg)
    return out


# --------------------------------------------------------------------------- #
# Table layout (no Tk)
# --------------------------------------------------------------------------- #

Word = Tuple[str, bool, bool, Optional[int]]      # text, bold, italic, link instance


def fit_columns(natural: List[float], minimum: List[float], available: float, pad: float) -> List[float]:
    """Column widths: the natural widths if they fit; otherwise every column keeps at least its
    longest word and the spare room is shared out in proportion to how much more each column wants."""
    n = len(natural)
    if n == 0:
        return []
    gaps = pad * (n - 1)
    if sum(natural) + gaps <= available:
        return list(natural)
    budget = available - gaps
    if sum(minimum) >= budget:
        return list(minimum)
    extra = budget - sum(minimum)
    wants = [max(0.0, nat - mini) for nat, mini in zip(natural, minimum)]
    total = sum(wants)
    if total <= 0:
        return list(minimum)
    return [mini + extra * w / total for mini, w in zip(minimum, wants)]


def wrap_words(words: List[Word], width: float, measure: Callable[[Word], float],
               space: float) -> List[List[Word]]:
    """Greedy line breaking of ``words`` to ``width`` (a word wider than that gets its own line)."""
    lines: List[List[Word]] = []
    current: List[Word] = []
    used = 0.0
    for word in words:
        w = measure(word)
        if current and used + space + w > width:
            lines.append(current)
            current, used = [word], w
        else:
            used += (space if current else 0) + w
            current.append(word)
    if current or not lines:
        lines.append(current)
    return lines


# --------------------------------------------------------------------------- #
# The widget
# --------------------------------------------------------------------------- #

class RuleTextView(ctk.CTkFrame):
    """A read-only, scrollable view of rules markup."""

    TABLE_INDENT = 6
    CELL_PAD = 18
    BULLET_INDENT = 16

    def __init__(self, parent, on_link: Optional[Callable[[str, str], None]] = None,
                 font_size: int = 13, bg_role: str = "bg_primary"):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.on_link = on_link               # (category, name); default opens the link popup
        self.font_size = font_size
        self.bg_role = bg_role
        self._markup = ""
        self._query = ""
        self._links: Dict[str, Tuple[str, str]] = {}
        self._hits: List[Tuple[str, str]] = []
        self._hit_pos = -1
        self._has_tables = False
        self._laid_out_width = 0
        self._resize_job = None
        self._pending_scroll: Optional[int] = None

        self.text = tk.Text(
            self, wrap="word", relief="flat", borderwidth=0, highlightthickness=0,
            padx=14, pady=10, cursor="arrow", state="disabled", takefocus=0,
            spacing1=0, spacing2=2, spacing3=0, undo=False)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.bind("<Button-1>", lambda _e: self.text.focus_set(), add="+")
        self.text.bind("<Configure>", self._on_configure, add="+")
        self._apply_colors()
        self._bind_links()
        self.theme.add_listener(self._on_theme_changed)

    # ------------------------------------------------------------------ public API

    def set_markup(self, markup: str, query: str = ""):
        """Show ``markup``; words matching ``query`` are lit up."""
        self._markup = markup or ""
        self._query = query or ""
        self.render()

    def set_query(self, query: str):
        """Change what is lit up without redrawing the text."""
        self._query = query or ""
        self._mark_hits()

    def clear(self):
        self.set_markup("")

    def plain_text(self) -> str:
        return self.text.get("1.0", "end-1c")

    @property
    def hit_count(self) -> int:
        return len(self._hits)

    def has_section(self, index: int) -> bool:
        return f"sec{index}" in self.text.mark_names()

    def scroll_to_section(self, index: int):
        """Scroll so the heading of section ``index`` is at the top."""
        if index <= 0:
            self.text.yview_moveto(0.0)
            return
        if self.has_section(index):
            self.text.yview(f"sec{index}")

    def scroll_to_top(self):
        self.text.yview_moveto(0.0)

    def goto_hit(self, position: int, scroll: bool = True) -> Tuple[int, int]:
        """Select hit ``position`` (wrapping round) and scroll to it. Returns (position, total)."""
        total = len(self._hits)
        if not total:
            self._hit_pos = -1
            return -1, 0
        position %= total
        self.text.tag_remove("hit_current", "1.0", "end")
        start, end = self._hits[position]
        self.text.tag_add("hit_current", start, end)
        if scroll:
            self.text.see(start)
        self._hit_pos = position
        return position, total

    def next_hit(self, step: int = 1) -> Tuple[int, int]:
        return self.goto_hit((self._hit_pos if self._hit_pos >= 0 else (-1 if step > 0 else 0)) + step)

    def hit_near_section(self, index: int) -> int:
        """The position of the first hit at or after section ``index`` (0 if there is none)."""
        if not self._hits:
            return -1
        if index > 0 and self.has_section(index):
            for i, (start, _end) in enumerate(self._hits):
                if self.text.compare(start, ">=", f"sec{index}"):
                    return i
        return 0

    # ------------------------------------------------------------------ colours and fonts

    def _color(self, role: str) -> str:
        value = self.theme.get_current_color(role)
        return value[1] if isinstance(value, tuple) else str(value)

    def _apply_colors(self):
        bg, fg = self._color(self.bg_role), self._color("text_primary")
        t = self.text
        t.configure(bg=bg, fg=fg, insertbackground=fg, selectbackground=self._color("accent_primary"),
                    selectforeground=self._color("text_on_accent"), inactiveselectbackground=self._color("accent_primary"))
        t.tag_configure("b", foreground=self._color("text_label"))
        t.tag_configure("link", foreground=self._color("spell_link"), underline=True)
        t.tag_configure("kind", foreground=self._color("text_secondary"))
        for tag in ("bar1", "bar2", "hr"):
            t.tag_configure(tag, background=self._color("scrollbar_thumb"))
        t.tag_configure("hit", background=self._color("level_9"), foreground=self._color("text_primary"))
        t.tag_configure("hit_current", background=self._color("accent_primary"),
                        foreground=self._color("text_on_accent"))
        t.tag_configure("t_head", background=self._color("bg_tertiary"))
        t.tag_configure("t_odd", background=self._color("bg_secondary"))
        t.tag_configure("t_even", background=bg)
        t.tag_raise("hit")
        t.tag_raise("hit_current")
        t.tag_raise("sel")

    def _on_theme_changed(self):
        self.apply_theme()

    def apply_theme(self):
        """Recolour the text and its tags (a tk.Text is not reached by the app-wide restyle)."""
        try:
            self._apply_colors()
            self._configure_tags()
        except tk.TclError:
            pass

    def _configure_tags(self):
        """Fonts and spacing for the tags (looked up fresh each render: a text-size change replaces the fonts)."""
        size = self.font_size
        self._f_body = ui_font("body", size)
        self._f_bold = ui_font("body", size, bold=True)
        self._f_italic = ui_font("body", size, italic=True)
        self._f_bolditalic = ui_font("body", size, bold=True, italic=True)
        self._f_table = ui_font("body", max(9, size - 1))
        self._f_table_bold = ui_font("body", max(9, size - 1), bold=True)
        t = self.text
        t.configure(font=self._f_body)
        t.tag_configure("i", font=self._f_italic)
        t.tag_configure("bi", font=self._f_bolditalic)
        t.tag_configure("bold", font=self._f_bold)
        heads = {1: ("heading", size + 5, 16), 2: ("subheading", size + 2, 12),
                 3: ("subheading", size, 10), 4: ("body", size, 8)}
        for level, (role, pt, above) in heads.items():
            t.tag_configure(f"h{level}", font=ui_font(role, pt, bold=True), spacing1=above, spacing3=4)
        t.tag_configure("p", spacing3=7)
        t.tag_configure("li", spacing3=3)
        t.tag_configure("kind", font=ui_font("small", max(9, size - 1), italic=True))
        t.tag_configure("gap", font=ui_font("body", 4), spacing1=0, spacing3=0)
        # bars: the line is as tall as its font, so the font is tiny; the spacing is the air around it
        # (fonts sized in pixels, so a line is a couple of pixels tall whatever the text-size setting)
        # (spacing around a line is painted with the line's background, so the air is separate lines)
        self._bar_fonts = [tkfont.Font(root=self.text, size=-px) for px in (3, 2, 3, 5, 9)]
        t.tag_configure("bar1", font=self._bar_fonts[0], spacing1=0, spacing3=0)
        t.tag_configure("bar2", font=self._bar_fonts[1], spacing1=0, spacing3=0)
        t.tag_configure("hr", font=self._bar_fonts[2], spacing1=0, spacing3=0)
        t.tag_configure("air", font=self._bar_fonts[3], spacing1=0, spacing3=0)
        t.tag_configure("air_big", font=self._bar_fonts[4], spacing1=0, spacing3=0)
        for tag in ("t_head", "t_odd", "t_even"):
            t.tag_configure(tag, wrap="none", spacing1=2, spacing3=2, lmargin1=self.TABLE_INDENT,
                            lmargin2=self.TABLE_INDENT, font=self._f_table)
        t.tag_configure("t_head", font=self._f_table_bold)
        t.tag_configure("t_bold", font=self._f_table_bold)
        t.tag_configure("t_italic", font=ui_font("body", max(9, size - 1), italic=True))
        t.tag_configure("t_bolditalic", font=ui_font("body", max(9, size - 1), bold=True, italic=True))

    # ------------------------------------------------------------------ rendering

    def _available_width(self) -> int:
        try:
            width = self.text.winfo_width()
        except tk.TclError:
            width = 0
        if width < 100:
            width = 620
        return max(200, width - 28 - 2 * self.TABLE_INDENT - 8)

    def render(self, keep_scroll: bool = False):
        t = self.text
        top = None
        if keep_scroll:
            try:
                top = t.index("@0,0")
            except tk.TclError:
                top = None
        t.configure(state="normal")
        t.delete("1.0", "end")
        for name in list(t.mark_names()):
            if name.startswith("sec"):
                t.mark_unset(name)
        for tag in list(t.tag_names()):
            if tag.startswith(("lk", "tab")):
                t.tag_delete(tag)
        self._links.clear()
        self._link_counter = 0
        self._has_tables = False
        self._configure_tags()
        self._laid_out_width = self._available_width()

        section = 0
        for block in split_blocks(self._markup):
            single = "\n" not in block
            m = _HEADING_RE.match(block.strip()) if single else None
            if m:
                section += 1
                self._insert_heading(len(m.group(1)), m.group(2), section)
            elif single and _BAR_RE.fullmatch(block.strip()):
                self._insert_bar("hr")
            elif block.lstrip().startswith("|") and parse_table(block):
                headers, rows = parse_table(block)
                self._insert_table(headers, rows)
            elif _LIST_LINE_RE.match(block.split("\n", 1)[0]):
                self._insert_list(block)
            else:
                self._insert_paragraph(block)
        t.configure(state="disabled")
        self._mark_hits()
        if top is not None:
            try:
                t.yview(top)
            except tk.TclError:
                pass
        else:
            t.yview_moveto(0.0)

    def _style_tags(self, seg: Seg, in_table: bool = False) -> Tuple[str, ...]:
        tags: List[str] = []
        if seg.bold and seg.italic:
            tags.append("t_bolditalic" if in_table else "bi")
        elif seg.bold:
            tags.append("t_bold" if in_table else "bold")
        elif seg.italic:
            tags.append("t_italic" if in_table else "i")
        if seg.bold:
            tags.append("b")
        return tuple(tags)

    def _link_tags(self, link_inner: str) -> Tuple[str, ...]:
        from object_links import parse_link_markup
        self._link_counter += 1
        tag = f"lk{self._link_counter}"
        category, name, display = parse_link_markup(link_inner)
        self._links[tag] = (category, name)
        return ("link", tag)

    def _insert_segments(self, segs: List[Seg], base: Tuple[str, ...]):
        t = self.text
        from object_links import parse_link_markup
        for seg in segs:
            tags = base + self._style_tags(seg)
            text = seg.text
            if seg.link is not None:
                text = parse_link_markup(seg.link)[2]
                tags = tags + self._link_tags(seg.link)
            if text:
                t.insert("end", text, tags)

    def _insert_heading(self, level: int, title: str, ordinal: int):
        t = self.text
        t.mark_set(f"sec{ordinal}", "end-1c")
        t.mark_gravity(f"sec{ordinal}", "left")
        from rules import split_title
        shown, kind = split_title(title)
        t.insert("end", shown, (f"h{min(level, 4)}",))
        if kind:
            t.insert("end", f"   {kind}", (f"h{min(level, 4)}", "kind"))
        t.insert("end", "\n", (f"h{min(level, 4)}",))
        self._insert_bar("bar1" if level <= 2 else "bar2")        # the line under a heading

    def _insert_bar(self, tag: str):
        """A horizontal bar across the page: a line of tiny text with a coloured background."""
        if tag == "hr":
            self.text.insert("end", "\n", ("air_big",))
        self.text.insert("end", "\n", (tag,))
        self.text.insert("end", "\n", ("air_big" if tag == "hr" else "air",))

    def _insert_paragraph(self, block: str):
        self._insert_segments(link_segments(block), ("p",))
        self.text.insert("end", "\n", ("p",))

    def _insert_list(self, block: str):
        t = self.text
        lines = block.split("\n")
        items: List[Tuple[int, str, str]] = []           # depth, marker, text
        for line in lines:
            m = _LIST_LINE_RE.match(line)
            if m:
                depth = len(m.group(1)) // 2
                rest = line[m.end():]
                marker = line[len(m.group(1)):m.end()].strip()
                items.append((depth, "•" if marker in ("-", "*") else marker, rest))
            elif items:
                depth, marker, text = items[-1]
                items[-1] = (depth, marker, text + " " + line.strip())
            else:
                items.append((0, "", line.strip()))
        for depth, marker, text in items:
            indent = self.BULLET_INDENT * (depth + 1)
            hang = self._f_body.measure(f"{marker}  ") if marker else 0
            tag = f"tab_li_{depth}_{hang}"
            t.tag_configure(tag, lmargin1=indent, lmargin2=indent + hang)
            if marker:
                t.insert("end", f"{marker}  ", ("li", tag))
            self._insert_segments(link_segments(text), ("li", tag))
            t.insert("end", "\n", ("li", tag))
        t.insert("end", "\n", ("gap",))          # a little air after the list

    # ---- tables -------------------------------------------------------------

    def _insert_table(self, headers: List[str], rows: List[List[str]]):
        t = self.text
        self._has_tables = True
        grid = [headers] + rows
        ncols = len(headers)
        font_r, font_b = self._f_table, self._f_table_bold
        space = font_r.measure(" ")
        cell_words: List[List[List[Word]]] = []
        link_inner: Dict[int, str] = {}
        for ri, row in enumerate(grid):
            wrow = []
            for ci in range(ncols):
                cell = row[ci] if ci < len(row) else ""
                words = []
                for seg in link_segments(cell):
                    link_id = None
                    if seg.link is not None:
                        self._link_counter += 1
                        link_id = self._link_counter
                        link_inner[link_id] = seg.link
                    for w in seg.text.split():
                        words.append((w, seg.bold or ri == 0, seg.italic, link_id))
                wrow.append(words)
            cell_words.append(wrow)

        def measure(word: Word) -> float:
            return (font_b if word[1] else font_r).measure(word[0])

        natural, minimum = [0.0] * ncols, [0.0] * ncols
        for wrow in cell_words:
            for ci, words in enumerate(wrow):
                if not words:
                    continue
                natural[ci] = max(natural[ci], sum(measure(w) for w in words) + space * (len(words) - 1))
                minimum[ci] = max(minimum[ci], max(measure(w) for w in words))
        widths = fit_columns(natural, minimum, self._available_width(), self.CELL_PAD)
        stops, x = [], float(self.TABLE_INDENT)
        for w in widths[:-1]:
            x += w + self.CELL_PAD
            stops.append(int(x))
        tab_tag = f"tab_t{len(stops)}_{'_'.join(map(str, stops))}"
        if stops:
            t.tag_configure(tab_tag, tabs=tuple(v for stop in stops for v in (stop, "left")))
        else:
            t.tag_configure(tab_tag)

        for ri, wrow in enumerate(cell_words):
            wrapped = [wrap_words(words, widths[ci], measure, space) for ci, words in enumerate(wrow)]
            height = max(len(w) for w in wrapped)
            row_tag = "t_head" if ri == 0 else ("t_odd" if ri % 2 else "t_even")
            for li in range(height):
                for ci in range(ncols):
                    line = wrapped[ci][li] if li < len(wrapped[ci]) else []
                    for wi, (text, bold, italic, link_id) in enumerate(line):
                        seg = Seg(text, bold, italic)
                        tags = (row_tag, tab_tag) + self._style_tags(seg, in_table=True)
                        if link_id is not None:
                            tags += self._table_link_tags(link_id, link_inner[link_id])
                        t.insert("end", text, tags)
                        if wi < len(line) - 1:
                            joined = link_id is not None and line[wi + 1][3] == link_id
                            t.insert("end", " ", (row_tag, tab_tag) + (tags[-2:] if joined else ()))
                    t.insert("end", "\t" if ci < ncols - 1 else "\n", (row_tag, tab_tag))
        t.insert("end", "\n", ("gap",))

    def _table_link_tags(self, link_id: int, inner: str) -> Tuple[str, ...]:
        from object_links import parse_link_markup
        tag = f"lk{link_id}"
        if tag not in self._links:
            category, name, _display = parse_link_markup(inner)
            self._links[tag] = (category, name)
        return ("link", tag)

    # ------------------------------------------------------------------ links

    def _bind_links(self):
        t = self.text
        t.tag_bind("link", "<Button-1>", self._on_link_click)
        t.tag_bind("link", "<Enter>", lambda _e: t.configure(cursor="hand2"))
        t.tag_bind("link", "<Leave>", lambda _e: t.configure(cursor="arrow"))

    def _on_link_click(self, event):
        try:
            index = self.text.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return
        for tag in self.text.tag_names(index):
            target = self._links.get(tag)
            if target:
                self._open_link(*target)
                return

    def _open_link(self, category: str, name: str):
        if self.on_link is not None:
            self.on_link(category, name)
            return
        from ui.object_link_widgets import open_link_popup
        open_link_popup(self, category, name)

    # ------------------------------------------------------------------ search highlighting

    def _mark_hits(self):
        t = self.text
        t.tag_remove("hit", "1.0", "end")
        t.tag_remove("hit_current", "1.0", "end")
        self._hits = []
        self._hit_pos = -1
        if not self._query.strip():
            return
        content = t.get("1.0", "end-1c")
        if not content:
            return
        line_starts = [0]
        for m in re.finditer("\n", content):
            line_starts.append(m.end())

        def index_of(offset: int) -> str:
            line = bisect.bisect_right(line_starts, offset) - 1
            return f"{line + 1}.{offset - line_starts[line]}"

        for start, end in find_matches(self._query, content):
            a, b = index_of(start), index_of(end)
            t.tag_add("hit", a, b)
            self._hits.append((a, b))

    # ------------------------------------------------------------------ resizing and teardown

    def _on_configure(self, _event=None):
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(120, self._relayout)

    def _relayout(self):
        self._resize_job = None
        try:
            if not self.winfo_exists():
                return
            if self._has_tables and abs(self._available_width() - self._laid_out_width) > 6:
                current = self._hit_pos
                self.render(keep_scroll=True)
                if current >= 0 and self._hits:
                    self._hit_pos = min(current, len(self._hits) - 1)
                    start, end = self._hits[self._hit_pos]
                    self.text.tag_add("hit_current", start, end)
        except tk.TclError:
            pass

    def destroy(self):
        try:
            self.theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()
