"""
Rules pages: the data model, how a page splits into sections, the relevance-ranked search over
their text, and the manager.

A rules page is a named chunk of the rulebook ("Combat", "Conditions", "Rules Definitions").
Its text is stored as one markup string:

    # Heading            level 1 .. 4 section headings, a line of their own
    **bold**  *italic*   emphasis
    [[category:Name]]    object links; ``[[rule:Page#Section|shown]]`` points into another rules page
    • item / 1. item     list lines (leading spaces nest them)
    | a | b |            tables (a header row, a ``|---|---|`` row, then the rows)

Text before the first heading is the page's intro. Headings of glossary entries may end with a
bracketed tag ("Friendly [Attitude]"); the tag is the section's *kind*, the rest its title.
"""

from __future__ import annotations

import bisect
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_CATEGORY = "Homebrew"

_HEADING_RE = re.compile(r"^(#{1,4})[ \t]+(.+?)[ \t]*$")
_TAGGED_TITLE_RE = re.compile(r"^(.*?)\s*\[([^\]]+)\]\s*$")
_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_LIST_LINE_RE = re.compile(r"^(\s*)(?:•|[-*]|\d+\.)\s+")


# --------------------------------------------------------------------------- #
# Markup helpers
# --------------------------------------------------------------------------- #

def link_display(inner: str) -> str:
    """The visible text of the inside of a ``[[...]]`` token."""
    from object_links import parse_link_markup
    return parse_link_markup(inner)[2]


def strip_markup(text: str) -> str:
    """Plain text of a markup string: links become their shown text; emphasis, heading marks,
    table pipes and bullets disappear. Line structure is kept."""
    if not text:
        return ""
    text = _LINK_RE.sub(lambda m: link_display(m.group(1)), text)
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|"):
            if set(stripped) <= set("|-: "):
                continue                              # the |---|---| row
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            line = "  ".join(c for c in cells if c)
        elif re.fullmatch(r"-{3,}", stripped):
            continue                                  # a horizontal bar
        else:
            m = _HEADING_RE.match(stripped)
            if m:
                line = m.group(2)
            else:
                line = _LIST_LINE_RE.sub(r"\1", line)
        out.append(line)
    text = "\n".join(out)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)
    text = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"\1", text, flags=re.S)
    text = re.sub(r"(?<![\w_])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w_])", r"\1", text, flags=re.S)
    return text


def split_cells(line: str) -> List[str]:
    """The cells of one table line. A ``|`` inside ``[[...]]`` (a link's shown text) is not a divider."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, depth, current = [], 0, []
    i = 0
    while i < len(line):
        two = line[i:i + 2]
        if two == "[[":
            depth += 1
            current.append(two)
            i += 2
            continue
        if two == "]]" and depth:
            depth -= 1
            current.append(two)
            i += 2
            continue
        if line[i] == "|" and depth == 0:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(line[i])
        i += 1
    cells.append("".join(current).strip())
    return cells


def parse_table(block: str) -> Optional[Tuple[List[str], List[List[str]]]]:
    """(header cells, rows) of a markdown table block, or None if it is not one."""
    lines = [l for l in block.split("\n") if l.strip()]
    if len(lines) < 2 or not lines[0].lstrip().startswith("|"):
        return None
    header = split_cells(lines[0])
    start = 1
    if set(lines[1].strip()) <= set("|-: "):
        start = 2
    rows = [split_cells(l) for l in lines[start:] if l.lstrip().startswith("|")]
    width = len(header)
    rows = [r + [""] * (width - len(r)) if len(r) < width else r for r in rows]
    return header, rows


def split_blocks(text: str) -> List[str]:
    """The blank-line separated blocks of a markup string."""
    return [b.strip("\n") for b in re.split(r"\n\s*\n", text or "") if b.strip()]


def split_title(raw: str) -> Tuple[str, str]:
    """``"Stunned [Condition]"`` -> ("Stunned", "Condition"); a plain title has no kind."""
    m = _TAGGED_TITLE_RE.match(raw.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else (raw.strip(), "")


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #

@dataclass
class RuleSection:
    index: int
    level: int            # 0 = the intro before the first heading, else 1..4
    raw_title: str        # as written ("Stunned [Condition]")
    title: str            # shown ("Stunned")
    kind: str             # the bracketed tag, if any
    text: str             # markup of the body, without the heading line
    _plain: Optional[str] = field(default=None, repr=False, compare=False)
    _searchable: Optional[str] = field(default=None, repr=False, compare=False)

    @property
    def plain(self) -> str:
        if self._plain is None:
            self._plain = strip_markup(self.text)
        return self._plain

    @property
    def search_text(self) -> str:
        """What the search reads: the text without the long runs of bare names (the A-Z of magic
        items, the list of every monster), which would make every page that has one match them."""
        if self._searchable is None:
            self._searchable = strip_markup(_without_name_lists(self.text))
        return self._searchable


MIN_NAME_LIST = 60      # this many short list lines in one section make it a list of names (the A-Z of magic items)
MAX_NAME_LENGTH = 40


def _without_name_lists(text: str) -> str:
    """``text`` minus its short list lines, when there are enough of them to be a list of names."""
    lines = text.split("\n")
    names = [i for i, line in enumerate(lines)
             if _LIST_LINE_RE.match(line) and len(strip_markup(line).strip()) <= MAX_NAME_LENGTH]
    if len(names) < MIN_NAME_LIST:
        return text
    drop = set(names)
    return "\n".join(line for i, line in enumerate(lines) if i not in drop)


def parse_sections(description: str) -> List[RuleSection]:
    """Split a page's markup into sections at its heading lines. The first section is always the
    intro (level 0, possibly empty)."""
    sections: List[RuleSection] = []
    cur_title, cur_level, cur_lines = "", 0, []

    def close():
        text = "\n".join(cur_lines).strip("\n")
        title, kind = split_title(cur_title) if cur_title else ("", "")
        sections.append(RuleSection(len(sections), cur_level, cur_title, title, kind, text))

    for block in re.split(r"\n\s*\n", description or ""):
        stripped = block.strip()
        m = _HEADING_RE.match(stripped) if stripped and "\n" not in stripped else None
        if m:
            close()
            cur_level, cur_title, cur_lines = len(m.group(1)), m.group(2).strip(), []
        elif stripped:
            cur_lines.append(block.strip("\n"))
            cur_lines.append("")
    close()                                    # (the intro stays even when empty: index 0 is always it)
    return sections


# --------------------------------------------------------------------------- #
# The page
# --------------------------------------------------------------------------- #

@dataclass
class RulePage:
    """One page of the rules."""
    name: str
    category: str = ""               # the chapter it belongs to
    description: str = ""            # markup, see the module docstring
    source: str = ""
    tags: List[str] = field(default_factory=list)
    order: int = 0                   # position in the book (0 = not in the book: the user's own)
    is_official: bool = True
    is_custom: bool = False
    _sections: Optional[List[RuleSection]] = field(default=None, repr=False, compare=False)
    _sections_of: str = field(default="", repr=False, compare=False)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "source": self.source,
            "tags": list(self.tags),
            "order": self.order,
            "description": self.description,
            "is_official": self.is_official,
            "is_custom": self.is_custom,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RulePage":
        tags = data.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        return cls(
            name=str(data.get("name", "Unknown")).strip() or "Unknown",
            category=str(data.get("category", "") or ""),
            description=str(data.get("description", "") or ""),
            source=str(data.get("source", "") or ""),
            tags=[str(t) for t in tags],
            order=int(data.get("order", 0) or 0),
            is_official=bool(data.get("is_official", True)),
            is_custom=bool(data.get("is_custom", False)),
        )

    @property
    def sections(self) -> List[RuleSection]:
        if self._sections is None or self._sections_of != self.description:
            self._sections = parse_sections(self.description)
            self._sections_of = self.description
        return self._sections

    def find_section(self, title: str) -> Optional[RuleSection]:
        """A section by its shown or raw title (case-insensitive)."""
        wanted = title.strip().lower()
        if not wanted:
            return None
        for sec in self.sections:
            if sec.level and (sec.title.lower() == wanted or sec.raw_title.lower() == wanted):
                return sec
        return None

    def plain_description(self) -> str:
        return strip_markup(self.description)

    def display_tags(self) -> str:
        return ", ".join(sorted(self.tags, key=lambda t: t.lower()))


@dataclass
class RuleRef:
    """A page, or one section of it: what a ``[[rule:...]]`` link points at."""
    page: RulePage
    section: Optional[RuleSection] = None

    @property
    def name(self) -> str:
        return self.page.name if self.section is None else f"{self.page.name}#{self.section.title}"

    @property
    def title(self) -> str:
        return self.page.name if self.section is None else self.section.title

    @property
    def description(self) -> str:
        if self.section is None:
            return self.page.description
        return self.section.text


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #

_WORD_RE = re.compile(r"[a-z0-9]+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z]+)?")


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"(?<=\w)'(?=\w)", "", text)          # can't -> cant, creature's -> creatures


def tokenize(text: str) -> List[str]:
    """Lower-case words of ``text`` ("Creature's" -> "creatures")."""
    return _WORD_RE.findall(_normalise(text))


def stem(word: str) -> str:
    """A crude stem, enough to make stun/stuns/stunned/stunning and paralyze/paralyzed equal."""
    w = word
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith("sses"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiouls":
        w = w[:-1]                                     # stunn -> stun, run(n)ing
    if len(w) > 4 and w.endswith("e"):
        w = w[:-1]
    return w


def stems(text: str) -> List[str]:
    return [stem(w) for w in tokenize(text)]


# Weights. Only their order matters: a name beats a heading beats a tag beats body text.
MIN_PREFIX = 3        # a half-typed last word matches as a prefix from this many letters
W_NAME_EXACT, W_NAME_PREFIX = 60, 35
W_NAME_ALL, W_NAME_EQUAL, W_NAME_STARTS, W_NAME_CONTAINS = 80, 400, 150, 80
W_TAG, W_CATEGORY = 25, 15
W_TITLE_EXACT, W_TITLE_PREFIX = 60, 35
W_TITLE_ALL, W_TITLE_EQUAL, W_TITLE_STARTS, W_TITLE_CONTAINS = 60, 260, 70, 50
W_BODY_BASE, W_BODY_PER_USE, BODY_USE_CAP = 8, 3, 6
W_TOGETHER, W_PHRASE_TITLE, W_PHRASE_BODY = 40, 120, 50
OTHER_SECTIONS_SHARE = 0.15
STEM_ONLY = 0.6       # a word that matched only after stemming (poison for poisoned) counts for less than the exact word
PREFIX_ONLY = 0.58    # ... and so does the start of the word being typed


@dataclass
class _SecIndex:
    title_stems: set
    title_raw: set
    title_norm: str
    body: Counter
    body_norm: str


@dataclass
class _PageIndex:
    signature: tuple
    name_stems: set
    name_raw: set
    name_norm: str
    tag_stems: set
    category_stems: set
    sections: List[_SecIndex]
    body_total: Counter
    body_keys: List[str]         # sorted, for prefix lookups


@dataclass
class RuleHit:
    """One search result: a page, how well it matched, and where in it the best match is."""
    page: RulePage
    score: float = 0.0
    section: Optional[int] = None          # the best-matching section (None: the page itself)
    sections: List[int] = field(default_factory=list)   # every section that matched, in page order
    snippet: str = ""
    query: str = ""

    @property
    def name(self) -> str:
        return self.page.name

    @property
    def is_custom(self) -> bool:
        return self.page.is_custom

    @property
    def section_title(self) -> str:
        if self.section is None:
            return ""
        sec = self.page.sections[self.section]
        return sec.title if sec.level else ""

    @property
    def target(self) -> str:
        """``Page`` or ``Page#Section``: what to open for this result."""
        title = self.section_title
        return f"{self.page.name}#{title}" if title else self.page.name

    def label(self) -> str:
        title = self.section_title
        if title and title.lower() != self.page.name.lower():
            return f"{self.page.name}  ›  {title}"
        return self.page.name


class _Query:
    """A parsed search string: stemmed words, the last of which also matches as a prefix (so a
    half-typed word works), and "quoted phrases" that must appear as written."""

    def __init__(self, text: str):
        self.raw = text
        phrases = re.findall(r'"([^"]+)"', text)
        rest = re.sub(r'"[^"]*"', " ", text)
        self.phrases = [" ".join(tokenize(p)) for p in phrases if tokenize(p)]
        self.raw_words = tokenize(rest)
        self.words = [stem(w) for w in self.raw_words]
        # a word in a phrase also has to be found on the page
        self.all_words: List[str] = list(self.words)
        for p in self.phrases:
            self.all_words += [stem(w) for w in p.split()]
        self.last = self.words[-1] if self.words and not text.rstrip().endswith('"') else None
        self.norm = " ".join(tokenize(rest))
        self.empty = not self.all_words

    def find_matches(self, text: str) -> List[Tuple[int, int]]:
        """(start, end) of what to light up in ``text``: where the words of the query come one right
        after another, if they do anywhere, else every word of the query on its own. Words are
        matched the way the search matches them (same stemming)."""
        wanted = {w for w in self.all_words if len(w) >= 2}
        if not wanted:
            return []
        prefix = self.last if self.last and len(self.last) >= MIN_PREFIX else None
        tokens = []          # (start, end, stem)
        for m in _TOKEN_RE.finditer(text):
            tokens.append((m.start(), m.end(), stem(m.group(0).lower().replace("'", "").replace("’", ""))))

        def word_matches(tok_stem: str, query_word: str, last: bool) -> bool:
            return tok_stem == query_word or (last and prefix is not None and query_word == prefix
                                              and tok_stem.startswith(prefix))

        runs = []
        if len(self.words) > 1:
            n = len(self.words)
            i = 0
            while i + n <= len(tokens):
                if all(word_matches(tokens[i + k][2], self.words[k], k == n - 1) for k in range(n)):
                    runs.append((tokens[i][0], tokens[i + n - 1][1]))
                    i += n
                else:
                    i += 1
        if runs:
            return runs
        out = []
        for start, end, tok_stem in tokens:
            if tok_stem in wanted or (prefix and tok_stem.startswith(prefix)):
                out.append((start, end))
        return out


def find_matches(query: str, text: str) -> List[Tuple[int, int]]:
    """Character ranges of ``text`` that match the words of a search ``query``."""
    return _Query(query or "").find_matches(text)


class RuleSearchIndex:
    """Relevance-ranked search over rules pages: the name beats a heading, which beats a tag, which
    beats the words in a section; a page needs every word of the query somewhere. The index of a
    page is rebuilt only when its text changes."""

    def __init__(self):
        self._pages: Dict[str, _PageIndex] = {}

    # ---- indexing -------------------------------------------------------

    @staticmethod
    def _signature(page: RulePage) -> tuple:
        return (page.description, page.name, page.category, tuple(page.tags))

    def _index(self, page: RulePage) -> _PageIndex:
        sig = self._signature(page)
        got = self._pages.get(page.name)
        if got is not None and got.signature == sig:
            return got
        sections, total = [], Counter()
        for sec in page.sections:
            body = Counter(stems(sec.search_text))
            title_norm = " ".join(tokenize(sec.title))
            sections.append(_SecIndex(
                title_stems={stem(w) for w in title_norm.split()},
                title_raw=set(title_norm.split()),
                title_norm=title_norm,
                body=body,
                body_norm=" ".join(tokenize(sec.search_text))))
            total.update(body)
        idx = _PageIndex(
            signature=sig,
            name_stems=set(stems(page.name)),
            name_raw=set(tokenize(page.name)),
            name_norm=" ".join(tokenize(page.name)),
            tag_stems={s for t in page.tags for s in stems(t)},
            category_stems=set(stems(page.category)),
            sections=sections, body_total=total, body_keys=sorted(total))
        self._pages[page.name] = idx
        return idx

    def forget(self, name: Optional[str] = None):
        if name is None:
            self._pages.clear()
        else:
            self._pages.pop(name, None)

    # ---- matching -------------------------------------------------------

    @staticmethod
    def _prefix_count(idx: _PageIndex, prefix: str) -> int:
        lo = bisect.bisect_left(idx.body_keys, prefix)
        n = 0
        while lo < len(idx.body_keys) and idx.body_keys[lo].startswith(prefix):
            n += idx.body_total[idx.body_keys[lo]]
            lo += 1
        return n

    def _page_has(self, q: _Query, idx: _PageIndex, word: str, titles_only: bool) -> bool:
        prefix = word == q.last and len(word) >= MIN_PREFIX
        if word in idx.name_stems or word in idx.tag_stems or word in idx.category_stems:
            return True
        if prefix and any(s.startswith(word) for s in idx.name_stems | idx.tag_stems | idx.category_stems):
            return True
        for sec in idx.sections:
            if word in sec.title_stems or (prefix and any(s.startswith(word) for s in sec.title_stems)):
                return True
        if titles_only:
            return False
        if idx.body_total.get(word):
            return True
        return bool(prefix and self._prefix_count(idx, word))

    @staticmethod
    def _weight(raw: str, word: str, prefix: bool, raws: set, stems_: set) -> float:
        """How well one query word is matched by a title: 1 for the word itself, less for its stem
        or the start of it, 0 for no match."""
        if raw in raws:
            return 1.0
        if word in stems_:
            return STEM_ONLY
        if prefix and any(s.startswith(word) for s in stems_):
            return PREFIX_ONLY
        return 0.0

    def _section_score(self, q: _Query, sec: _SecIndex, titles_only: bool) -> Tuple[float, bool]:
        score, present = 0.0, 0
        weights = []
        for k, word in enumerate(q.words):
            prefix = k == len(q.words) - 1 and q.last is not None and len(word) >= MIN_PREFIX
            hit = False
            w = self._weight(q.raw_words[k], word, prefix, sec.title_raw, sec.title_stems)
            weights.append(w)
            if w:
                score += W_TITLE_EXACT * w
                hit = True
            if not titles_only:
                uses = sec.body.get(word, 0)
                if uses == 0 and prefix:
                    uses = sum(c for s_, c in sec.body.items() if s_.startswith(word)) * 0.7
                if uses:
                    score += W_BODY_BASE + W_BODY_PER_USE * min(uses, BODY_USE_CAP)
                    hit = True
            present += hit
        all_present = bool(q.words) and present == len(q.words)
        if sec.title_stems and weights and all(weights):
            score += W_TITLE_ALL * min(weights)
            if q.norm and sec.title_norm == q.norm:
                score += W_TITLE_EQUAL
            elif q.norm and sec.title_norm.startswith(q.norm):
                score += W_TITLE_STARTS
        elif q.norm and len(q.words) > 1 and q.norm in sec.title_norm:
            score += W_TITLE_CONTAINS
        if all_present:
            score += W_TOGETHER
        for phrase in q.phrases:
            if phrase in sec.title_norm:
                score += W_PHRASE_TITLE
            elif not titles_only and phrase in sec.body_norm:
                score += W_PHRASE_BODY
        if len(q.words) > 1 and q.norm and not titles_only and q.norm in sec.body_norm:
            score += W_PHRASE_BODY
        return score, all_present

    def _page_score(self, q: _Query, idx: _PageIndex) -> float:
        score = 0.0
        weights = []
        for k, word in enumerate(q.words):
            prefix = k == len(q.words) - 1 and q.last is not None and len(word) >= MIN_PREFIX
            w = self._weight(q.raw_words[k], word, prefix, idx.name_raw, idx.name_stems)
            weights.append(w)
            score += W_NAME_EXACT * w
            if word in idx.tag_stems:
                score += W_TAG
            if word in idx.category_stems:
                score += W_CATEGORY
        if weights and all(weights):
            score += W_NAME_ALL * min(weights)
            if q.norm == idx.name_norm:
                score += W_NAME_EQUAL
            elif idx.name_norm.startswith(q.norm):
                score += W_NAME_STARTS
        elif q.norm and len(q.words) > 1 and q.norm in idx.name_norm:
            score += W_NAME_CONTAINS
        return score

    def search(self, query: str, pages: Iterable[RulePage], titles_only: bool = False,
               limit: Optional[int] = None) -> List[RuleHit]:
        """Pages matching ``query``, best first. An empty query matches nothing."""
        q = _Query(query or "")
        if q.empty:
            return []
        hits: List[RuleHit] = []
        for page in pages:
            idx = self._index(page)
            if not all(self._page_has(q, idx, w, titles_only) for w in q.all_words):
                continue
            if q.phrases and not titles_only:
                joined = " ".join(s.body_norm for s in idx.sections)
                if not all(p in joined or p in idx.name_norm
                           or any(p in s.title_norm for s in idx.sections) for p in q.phrases):
                    continue
            scored = []
            for sec_idx, sec in enumerate(idx.sections):
                s, _together = self._section_score(q, sec, titles_only)
                if s > 0:
                    scored.append((s, sec_idx))
            name_part = self._page_score(q, idx)
            best_score, best = 0.0, None
            if scored:
                best_score, best = max(scored, key=lambda t: (t[0], -t[1]))
            others = sorted((s for s, i in scored if i != best), reverse=True)[:4]
            total = name_part + best_score + OTHER_SECTIONS_SHARE * sum(others)
            if total <= 0:
                continue
            # a page whose own name carries the match, and has no section that matches better, is
            # shown as a whole
            section = best
            if section is not None and (name_part >= best_score or page.sections[section].level == 0):
                section = None
            hit = RuleHit(page=page, score=total, section=section,
                          sections=sorted(i for _s, i in scored), query=query)
            hit.snippet = self._snippet(q, page, section)
            hits.append(hit)
        hits.sort(key=lambda h: (-h.score, len(h.page.name), h.page.name.lower()))
        return hits[:limit] if limit else hits

    @staticmethod
    def _snippet(q: _Query, page: RulePage, section: Optional[int]) -> str:
        if section is None:
            return ""
        text = " ".join(page.sections[section].plain.split())
        if not text:
            return ""
        found = q.find_matches(text)
        start = max(0, (found[0][0] if found else 0) - 50)
        piece = text[start:start + 150].strip()
        return ("…" if start else "") + piece + ("…" if start + 150 < len(text) else "")


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #

class RulesManager:
    """Manages the rules pages stored in the database."""

    _instance: Optional["RulesManager"] = None

    def __init__(self):
        self._db = None
        self._cache: Optional[List[RulePage]] = None
        self._by_name: Dict[str, RulePage] = {}
        self._index = RuleSearchIndex()

    @classmethod
    def get_instance(cls) -> "RulesManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def db(self):
        if self._db is None:
            from database import SpellDatabase
            self._db = SpellDatabase()
            self._db.initialize()
        return self._db

    # ---- loading ----------------------------------------------------------

    @staticmethod
    def book_order(page: RulePage):
        """The book's own order, then the user's pages (A-Z)."""
        return (0 if page.order else 1, page.order, page.name.lower())

    @property
    def pages(self) -> List[RulePage]:
        if self._cache is None:
            self._reload_cache()
        return self._cache or []

    def _reload_cache(self):
        pages = [RulePage.from_dict(d) for d in self.db.get_all_rules()]
        pages.sort(key=self.book_order)
        self._cache = pages
        self._by_name = {p.name.lower(): p for p in pages}

    def _invalidate(self):
        self._cache = None

    def load(self) -> bool:
        self._invalidate()
        self._index.forget()
        return True

    def save(self) -> bool:
        return True

    # ---- lookup -------------------------------------------------------------

    def get_page(self, name: str) -> Optional[RulePage]:
        _ = self.pages
        return self._by_name.get((name or "").strip().lower())

    get_rule = get_page            # the name content_io's generic importer uses

    def resolve(self, name: str) -> Optional[RuleRef]:
        """A page (``"Combat"``), a section of one (``"Conditions#Stunned"``), or a bare section
        title (``"Stunned"``: the first page, in book order, that has one) -> what it points at."""
        name = (name or "").strip()
        if not name:
            return None
        if "#" in name:
            page_name, _, section_name = name.partition("#")
            page = self.get_page(page_name)
            if page is None:
                return None
            sec = page.find_section(section_name)
            return RuleRef(page, sec) if sec is not None else RuleRef(page)
        page = self.get_page(name)
        if page is not None:
            return RuleRef(page)
        for page in self.pages:
            sec = page.find_section(name)
            if sec is not None:
                return RuleRef(page, sec)
        return None

    # ---- editing -------------------------------------------------------------

    def add_rule(self, page: RulePage) -> bool:
        """Add a page, or update the one with the same name."""
        existing = self.db.get_rule_by_name(page.name)
        data = page.to_dict()
        if page.is_custom or not page.is_official:
            data["order"] = 0                    # the user's own pages follow the book
        if existing:
            self.db.update_rule(existing["id"], data)
        else:
            self.db.insert_rule(data)
        self._index.forget(page.name)
        self._invalidate()
        return True

    add_page = add_rule

    def update_page(self, name: str, updated: RulePage) -> bool:
        existing = self.db.get_rule_by_name(name)
        if not existing:
            return False
        data = updated.to_dict()
        if updated.is_custom or not updated.is_official:
            data["order"] = 0
        ok = self.db.update_rule(existing["id"], data)
        self._index.forget(name)
        self._index.forget(updated.name)
        self._invalidate()
        return ok

    def delete_page(self, name: str) -> bool:
        """Delete a page by name. Only the user's own pages can be removed."""
        existing = self.db.get_rule_by_name(name)
        if not existing or not existing.get("is_custom"):
            return False
        ok = self.db.delete_rule(existing["id"])
        self._index.forget(name)
        self._invalidate()
        return ok

    # ---- aggregates ------------------------------------------------------------

    def get_all_categories(self) -> List[str]:
        """Chapters in book order, then the user's own categories."""
        seen: List[str] = []
        for p in self.pages:
            if p.category and p.category not in seen:
                seen.append(p.category)
        return seen

    def get_all_tags(self) -> List[str]:
        return sorted({t for p in self.pages for t in p.tags}, key=str.lower)

    def get_all_sources(self) -> List[str]:
        return sorted({p.source for p in self.pages if p.source})

    def get_unofficial_sources(self) -> List[str]:
        return sorted({p.source for p in self.pages if (not p.is_official or p.is_custom) and p.source})

    def get_unofficial_rules(self) -> List[RulePage]:
        return [p for p in self.pages if not p.is_official or p.is_custom]

    get_unofficial_pages = get_unofficial_rules

    # ---- search -----------------------------------------------------------------

    def search(self, query: str, pages: Optional[Iterable[RulePage]] = None, titles_only: bool = False,
               limit: Optional[int] = None) -> List[RuleHit]:
        return self._index.search(query, self.pages if pages is None else pages, titles_only, limit)

    # ---- files -------------------------------------------------------------------

    def export_to_json(self, file_path: str, pages: Optional[List[RulePage]] = None) -> int:
        if pages is None:
            pages = self.get_unofficial_rules()
        try:
            from atomic_io import atomic_write_json
            atomic_write_json(file_path, {"rules": [p.to_dict() for p in pages]})
            return len(pages)
        except Exception as e:
            print(f"Error exporting rules to JSON: {e}")
            return 0

    def import_from_json(self, file_path: str) -> int:
        """Import rules pages from a JSON file; returns how many were added or updated (an
        official page's name is never overwritten)."""
        import content_io
        try:
            report = content_io.import_file(file_path, kinds=["rules"], link_mentions=False)
        except Exception as e:
            print(f"Error importing rules from JSON: {e}")
            return 0
        return report.added["rules"] + report.updated["rules"]


def get_rules_manager() -> RulesManager:
    return RulesManager.get_instance()
