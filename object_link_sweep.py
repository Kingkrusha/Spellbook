"""
Auto-linking of object names inside the bundled (official) content text.

Turns plain mentions such as "the Misty Step spell" or "Backpack, Bedroll" in
descriptions into ``[[category:Name|display]]`` markup - the same markup the
universal object-link system (object_links.py) understands - so mentions
become clickable in every detail view.

Design goals
------------
* Precision over recall. A missed link is invisible; a wrong link is a bug.
  Multi-word names ("Dispel Magic", "Thieves' Tools") are distinctive and link
  anywhere in prose. Single-word names ("Light", "Shield", "Fly") are also
  ordinary rules vocabulary, so they only link in contexts that prove they
  are the object: "the Wish spell", "cast Jump", "Guidance is recommended",
  a spell-list table column, a background's equipment list, and so on.
* Idempotent: text that is already linked is never linked again.
* Reversible: replacing every link by its display text gives back the original
  text (legacy ``[[Spell]]`` links aside), so nothing but markup is ever added.
* Never touches emphasised headings (``*Bear.*``), existing links, HTML tags,
  or feature/item headings such as "Lightning Bolt. When you throw ...".

This module is pure (no database, no UI) so it can be used by the sweep tool,
by the schema migration, and by tests alike.
"""

import re
from typing import Dict, Iterable, List, Optional, Tuple

# Order in which categories are tried when one written name is shared by
# several objects (e.g. "Potion of Healing" is both a magic item and gear).
PRIORITY = ["spell", "magic_item", "equipment", "feat", "subclass", "class",
            "lineage", "background"]

# Single-word names that are really rules vocabulary, never linked on their own.
_SCHOOLS = {"Abjuration", "Conjuration", "Divination", "Enchantment",
            "Evocation", "Illusion", "Necromancy", "Transmutation"}
_EQUIPMENT_STOPWORDS = {"Acid", "Dice", "Ammunition", "Horn"}

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_PROTECTED_RES = [
    _LINK_RE,                                   # existing links
    re.compile(r"\*{1,3}[^*\n]+?\*{1,3}"),      # emphasis / headings
    re.compile(r"<[^>\n]+>"),                   # html tags
]
_RARITY_HEADING = r"\((?:Common|Uncommon|Rare|Very Rare|Legendary)\)"

# What may sit between two names for them to count as one list.
_LIST_SEP = re.compile(
    r"^(?:\s*\([^)\n]*\))?"
    r"(?:\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+)"
    r"(?:(?:a|an|the)\s+)?$")

_ARTICLE_BEFORE = re.compile(
    r"(?:\b(?:a|an|the|your|his|her|their|any|each|such as|of|"
    r"with|using|holding|wielding|wearing|wear|use|carry|carrying)\s+"
    r"(?:(?:nonmagical|magical|ordinary|Simple|Martial)\s+)?)$", re.I)


def _fmt(category: str, name: str, display: str) -> str:
    if display and display != name:
        return f"[[{category}:{name}|{display}]]"
    return f"[[{category}:{name}]]"


# --------------------------------------------------------------------------
# Universe: every linkable name, compiled into one fast matcher
# --------------------------------------------------------------------------

def _surface_variants(name: str) -> List[str]:
    """Ways a name is written in prose. "Bottle, Glass" also reads "Glass Bottle"."""
    variants = [name]
    if "," in name and "(" not in name:
        head, tail = [p.strip() for p in name.split(",", 1)]
        variants.append(f"{tail} {head}")
    return variants


def _trie_pattern(words: Iterable[str]) -> str:
    """Compile many literal words into one trie-shaped regex (fast alternation)."""
    trie: dict = {}
    for w in words:
        node = trie
        for ch in w:
            node = node.setdefault(ch, {})
        node[""] = True

    def build(node: dict) -> str:
        optional = "" in node
        branches = [re.escape(ch) + build(node[ch]) for ch in sorted(k for k in node if k)]
        if not branches:
            return ""
        body = branches[0] if len(branches) == 1 else "(?:" + "|".join(branches) + ")"
        if optional:
            body = "(?:" + body + ")?"
        return body

    return build(trie)


class Universe:
    """All official object names, by category."""

    def __init__(self, names_by_category: Dict[str, Iterable[str]]):
        self.names: Dict[str, set] = {c: set(n) for c, n in names_by_category.items()}
        self.by_surface: Dict[str, List[Tuple[str, str]]] = {}
        for cat, names in self.names.items():
            for name in names:
                for surface in _surface_variants(name):
                    self.by_surface.setdefault(surface, []).append((cat, name))
        for cands in self.by_surface.values():
            cands.sort(key=lambda c: PRIORITY.index(c[0]))
        pattern = _trie_pattern(sorted(self.by_surface))
        self._regex = re.compile(
            r"(?<![\w'’\-])(?:" + pattern + r")(?P<suffix>es|s)?(?![\w])")

    def find(self, text: str):
        """Yield (start, end, surface, suffix) for every raw name occurrence."""
        for m in self._regex.finditer(text):
            suffix = m.group("suffix") or ""
            surface = m.group(0)[: len(m.group(0)) - len(suffix)]
            if surface not in self.by_surface and suffix:
                # e.g. "Torches": the trie may have eaten the suffix as part
                # of a longer literal; fall back to the plain surface.
                surface = m.group(0)
                suffix = ""
            if surface in self.by_surface:
                yield m.start(), m.end(), surface, suffix


# --------------------------------------------------------------------------
# Text analysis helpers
# --------------------------------------------------------------------------

def _protected_spans(text: str) -> List[Tuple[int, int]]:
    spans = []
    for rx in _PROTECTED_RES:
        spans.extend((m.start(), m.end()) for m in rx.finditer(text))
    return spans


def _overlaps(spans: List[Tuple[int, int]], start: int, end: int) -> bool:
    return any(s < end and start < e for s, e in spans)


def _table_cells(text: str) -> List[Tuple[int, int, str]]:
    """(start, end, kind) for cells of markdown tables whose header marks them
    as holding spells ("Spells", "Prepared Spells") or species."""
    cells: List[Tuple[int, int, str]] = []
    lines = text.split("\n")
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        j = i
        while j < len(lines) and lines[j].lstrip().startswith("|"):
            j += 1
        # header cells
        header = [c.strip().lower() for c in lines[i].strip().strip("|").split("|")]
        kinds = []
        for h in header:
            if "spell" in h:
                kinds.append("spell")
            elif h == "species":
                kinds.append("species")
            else:
                kinds.append("")
        for k in range(i + 1, j):
            line = lines[k]
            if re.fullmatch(r"[\s|:\-]+", line):
                continue                                  # |---|---| separator
            bars = [m.start() for m in re.finditer(r"\|", line)]
            for col in range(len(bars) - 1):
                a, b = bars[col] + 1, bars[col + 1]
                kind = kinds[col] if col < len(kinds) else ""
                cells.append((offsets[k] + a, offsets[k] + b, kind))
        i = j
    return cells


def _pack_list_spans(text: str) -> List[Tuple[int, int]]:
    """Sentences like "The pack contains the following items: A, B, C." - every
    gear name in them is genuinely gear."""
    spans = []
    for m in re.finditer(r"(?:contains|includes)\s+the\s+following\s+items?:", text):
        end = text.find(".\n", m.end())
        end2 = text.find(". ", m.end())
        candidates = [e for e in (end, end2) if e != -1]
        spans.append((m.end(), min(candidates) if candidates else len(text)))
    return spans


class _Token:
    __slots__ = ("start", "end", "surface", "suffix", "cands")

    def __init__(self, start, end, surface, suffix, cands):
        self.start, self.end, self.surface, self.suffix, self.cands = start, end, surface, suffix, cands


def _is_heading(text: str, tok: _Token) -> bool:
    """A name that opens a paragraph/line and is followed by a full stop, colon
    or rarity tag is a feature/item heading, not a mention."""
    cut = max(text.rfind("\n", 0, tok.start), text.rfind("\\", 0, tok.start))
    lead = text[cut + 1: tok.start]
    if not re.fullmatch(r"\s*(?:[-•]\s+)?", lead):
        return False
    tail = text[tok.end:tok.end + 16]
    return bool(re.match(r"\s*(?:[.:]|" + _RARITY_HEADING + r")", tail))


def _next_word_is_title(after: str) -> bool:
    """True when the name runs on into a longer Title Case phrase ("Shield Bash",
    "Book of Shadows", "Commune with Nature")."""
    return bool(re.match(r"\s+[A-Z][a-z]", after)) or \
        bool(re.match(r"\s+(?:of|with)\s+[A-Z]", after))


def _is_whole_piece(before: str, after: str) -> bool:
    """The name is a complete comma-separated item of its table cell."""
    return bool(re.search(r"(?:\||,|\band|\bor)\s*$", before)) and \
        bool(re.match(r"\s*(?:\||,|\band\b|\bor\b|$|\n)", after))


_FUNCTION_WORDS = {"A", "An", "The", "Your", "You", "This", "That", "Each", "Any", "If", "When"}


def _prev_word_is_title(before: str) -> bool:
    """True when the word just before is capitalised mid-sentence ("Dim Light")."""
    m = re.search(r"([A-Z][A-Za-z']+)\s+$", before)
    if not m or m.group(1) in _FUNCTION_WORDS:
        return False
    lead = before[:m.start()]
    if not lead.strip() or re.search(r"(?:[.!?:]|\n|\\)\s*$", lead):
        return False            # capitalised only because it opens a sentence
    return True


# --------------------------------------------------------------------------
# The linker
# --------------------------------------------------------------------------

def link_text(text: str, uni: Universe, owner: Optional[Tuple[str, str]] = None,
              list_context: bool = False,
              report: Optional[list] = None) -> str:
    """Return ``text`` with recognised object mentions wrapped as links.

    owner        -- (category, name) of the object the text belongs to; its own
                    name is never linked.
    list_context -- the whole text is a gear list (e.g. a background's
                    equipment), so any gear name in it is gear.
    report       -- optional list that receives one dict per link added.
    """
    if not text:
        return text
    text = _convert_legacy_links(text, uni)

    protected = _protected_spans(text)
    cells = _table_cells(text)
    packs = _pack_list_spans(text)

    tokens: List[_Token] = []
    for start, end, surface, suffix in uni.find(text):
        if _overlaps(protected, start, end):
            continue
        cands = uni.by_surface[surface]
        if owner and any((c, n) == owner for c, n in cands):
            cands = [(c, n) for c, n in cands if (c, n) != owner]
            if not cands:
                continue
        tok = _Token(start, end, surface, suffix, cands)
        if _is_heading(text, tok):
            continue
        tokens.append(tok)

    # Group neighbouring names into lists ("Guidance, Sacred Flame, and Thaumaturgy").
    runs: List[List[_Token]] = []
    for tok in tokens:
        if runs and _LIST_SEP.match(text[runs[-1][-1].end:tok.start]):
            runs[-1].append(tok)
        else:
            runs.append([tok])

    edits: List[Tuple[int, int, str]] = []
    for run in runs:
        before = text[: run[0].start]
        after = text[run[-1].end:]
        anchors = _run_anchors(before, after)
        equipment_like = sum(
            1 for t in run if any(c in ("equipment", "magic_item") for c, _ in t.cands))
        for tok in run:
            choice = _decide(text, tok, anchors, equipment_like, cells, packs, list_context, owner)
            if not choice:
                continue
            cat, name, rule = choice
            shown = tok.surface + (tok.suffix if cat in ("equipment", "magic_item") else "")
            if tok.suffix and cat not in ("equipment", "magic_item"):
                continue
            edits.append((tok.start, tok.end, _fmt(cat, name, shown)))
            if report is not None:
                report.append({"category": cat, "name": name, "shown": shown, "rule": rule,
                               "context": text[max(0, tok.start - 40):tok.end + 40].replace("\n", " ")})

    for start, end, repl in sorted(edits, reverse=True):
        text = text[:start] + repl + text[end:]
    return text


def _run_anchors(before: str, after: str) -> Dict[str, str]:
    """Which contexts a list of names sits in (see module docstring)."""
    anchors: Dict[str, str] = {}
    trail = re.match(r"(?:\s*\([^)\n]*\))?", after).end()
    rest = after[trail:]
    if re.match(r"\s+(?:spells?|cantrips?)\b(?!\s+lists?)", rest):
        anchors["spell"] = "spell/cantrip"
    if re.search(r"\bcast(?:s|ing)?\s+(?:either\s+|any\s+of\s+|one\s+of\s+|the\s+)?$", before):
        anchors["spell"] = "cast"
    if re.search(r"\bhave\s+(?:the\s+)?$", before) and re.match(r"\s+(?:spells?\s+)?prepared\b", rest):
        anchors["spell"] = "prepared"
    if re.match(r"\s+(?:is|are)\s+recommended\b", rest):
        anchors["spell"] = anchors["feat"] = anchors["magic_item"] = "recommended"
    if re.search(_RARITY_HEADING + r"\s+-\s+$", before):
        anchors["spell"] = "instrument-list"
    if re.search(r"\s-\s+$", before) and re.match(r"\s+in\s", rest):
        anchors["spell"] = "bullet"
    if re.match(r"\s+(?:is|was|are|were|be|been)\s+cast\b", rest):
        anchors["spell"] = "is-cast"
    if re.match(r"\s+feats?\b", rest):
        anchors["feat"] = "feat"
    if re.match(r"\s+(?:subclass(?:es)?)\b", rest):
        anchors["subclass"] = "subclass"
    if re.match(r"\s+spell\s+lists?\b", rest):
        anchors["class"] = "spell-list"
    if re.match(r"\s+background\b", rest):
        anchors["background"] = "background"
    return anchors


def _decide(text: str, tok: _Token, anchors: Dict[str, str], equipment_like: int,
            cells, packs, list_context: bool, owner=None) -> Optional[Tuple[str, str, str]]:
    before = text[: tok.start]
    after = text[tok.end:]
    multi = " " in tok.surface
    possessive = bool(re.match(r"['’]s\b", after))

    in_cell = None
    exact_cell = False        # the cell holds nothing but this name
    for a, b, kind in cells:
        if a <= tok.start and tok.end <= b:
            in_cell = kind
            exact_cell = text[a:b].strip() == text[tok.start:tok.end]
            break
    in_pack = any(a <= tok.start < b for a, b in packs)

    for cat, name in tok.cands:
        if cat == "lineage":
            if in_cell == "species" and not tok.suffix and _is_whole_piece(before, after):
                return cat, name, "species-cell"
            continue

        if exact_cell and cat not in ("class", "background") and not (
                cat == "equipment" and name in _EQUIPMENT_STOPWORDS):
            if not (cat in ("equipment", "magic_item") or " " in tok.surface) or not tok.suffix:
                return cat, name, "exact-cell"

        if multi and not (cat == "background" or cat == "class"):
            if possessive and "'" not in tok.surface:
                continue
            if tok.suffix and cat not in ("equipment", "magic_item"):
                continue
            return cat, name, "multi-word"

        # ---- single-word names: need proof --------------------------------
        if possessive:
            continue
        adjacent = _next_word_is_title(after) or _prev_word_is_title(before)

        if cat == "spell":
            if tok.suffix:
                continue
            if in_cell == "spell" and _is_whole_piece(before, after):
                return cat, name, "spell-cell"
            if name in _SCHOOLS and anchors.get("spell") != "cast":
                continue
            if anchors.get("spell") and not adjacent:
                return cat, name, f"anchor:{anchors['spell']}"
        elif cat in ("feat", "subclass", "class", "background"):
            if tok.suffix:
                continue
            key = cat
            if cat == "feat" and anchors.get("feat") in ("recommended", "feat") and not adjacent:
                return cat, name, f"anchor:{anchors['feat']}"
            if cat != "feat" and anchors.get(key) and not adjacent:
                return cat, name, f"anchor:{anchors[key]}"
        elif cat in ("equipment", "magic_item"):
            if name in _EQUIPMENT_STOPWORDS and not (list_context or in_pack):
                continue
            if owner and owner[0] == "magic_item" and re.search(
                    r"\b" + re.escape(tok.surface) + r"\b", owner[1]):
                continue        # "this Shield" inside Sentinel Shield is the item itself
            if cat == "equipment" and (list_context or in_pack):
                return cat, name, "gear-list"
            if adjacent:
                continue
            if equipment_like >= 2:
                return cat, name, "gear-run"
            if _ARTICLE_BEFORE.search(before):
                return cat, name, "article"
    return None


def _convert_legacy_links(text: str, uni: Universe) -> str:
    """[[Fireball]] -> [[spell:Fireball]] (only when it names a real spell)."""
    def sub(m):
        inner = m.group(1)
        body, _, display = inner.partition("|")
        head, sep, rest = body.partition(":")
        if sep and head.strip().lower().replace(" ", "_") in uni.names:
            return m.group(0)                      # already categorised
        name = body.strip()
        if name in uni.names.get("spell", ()):
            return _fmt("spell", name, display.strip() or name)
        return m.group(0)
    return _LINK_RE.sub(sub, text)


def strip_links(text: str) -> str:
    """Replace every [[...]] by its visible text (used to prove reversibility)."""
    def sub(m):
        body, _, display = m.group(1).partition("|")
        if display.strip():
            return display.strip()
        head, sep, rest = body.partition(":")
        if sep and head.strip().lower().replace(" ", "_") in (
                "spell", "feat", "lineage", "background", "class", "subclass",
                "equipment", "magic_item"):
            return rest.strip()
        return body.strip()
    return _LINK_RE.sub(sub, text)


# --------------------------------------------------------------------------
# Which fields of which object are prose (and therefore linkable)
#
# Records use the shape of the bundled JSON sources. Structured fields are
# deliberately left alone: class `tables` (the class view already turns their
# "Spells" columns into links), starting-equipment lists, proficiency lists,
# property tooltips and stat blocks are not rendered by link-aware widgets.
# --------------------------------------------------------------------------

def _apply(rec: dict, key: str, uni: Universe, owner, changes: list, label: str,
           list_context: bool = False):
    old = rec.get(key)
    if not isinstance(old, str) or not old:
        return
    links: list = []
    new = link_text(old, uni, owner, list_context, links)
    if new != old:
        rec[key] = new
        changes.append({"owner": owner, "field": label, "old": old, "new": new, "links": links})


def sweep_spell(rec, uni, changes):
    _apply(rec, "description", uni, ("spell", rec["name"]), changes, "description")


def sweep_feat(rec, uni, changes):
    _apply(rec, "description", uni, ("feat", rec["name"]), changes, "description")


def sweep_lineage(rec, uni, changes):
    owner = ("lineage", rec["name"])
    _apply(rec, "description", uni, owner, changes, "description")
    for t in rec.get("traits", []) or []:
        _apply(t, "description", uni, owner, changes, f"trait:{t.get('name', '')}")


def sweep_background(rec, uni, changes):
    owner = ("background", rec["name"])
    _apply(rec, "description", uni, owner, changes, "description")
    _apply(rec, "equipment", uni, owner, changes, "equipment", list_context=True)


def sweep_class_levels(levels: dict, class_name: str, uni, changes):
    owner = ("class", class_name)
    for lvl, data in (levels or {}).items():
        for ab in data.get("abilities", []) or []:
            _apply(ab, "description", uni, owner, changes, f"level {lvl}:{ab.get('title', '')}")


def sweep_subclass(sc: dict, uni, changes):
    owner = ("subclass", sc["name"])
    _apply(sc, "description", uni, owner, changes, "description")
    for f in sc.get("features", []) or []:
        _apply(f, "description", uni, owner, changes, f"level {f.get('level', '?')}:{f.get('title', '')}")


def sweep_equipment(rec, uni, changes):
    _apply(rec, "description", uni, ("equipment", rec["name"]), changes, "description")


def sweep_magic_item(rec, uni, changes):
    _apply(rec, "description", uni, ("magic_item", rec["name"]), changes, "description")
