"""
Rule-based feat stat-block parser.

Feats are far less standardized than spells - there is no near-universal
anchor line like a spell's "Level 3 Evocation". This parser leans on the two
lines that *are* common across both official (2024 PHB) and homebrew feat
text: a "Prerequisite:" line (2024 feats always print one, even "None") and a
feat-category line ("Origin Feat", "Fighting Style", "Epic Boon", ...).
Either is enough to anchor a block; when a paste has neither, the whole input
is treated as a single feat.

Entry points mirror spell_parser.py: split_blocks / parse_feat_block /
parse_feat_text / to_feat.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from text_import.base import (
    Confidence,
    ParsedObject,
    clean_lines,
    match_label,
    split_labelled_fragments,
    strip_markdown,
)

try:
    from spell import CharacterClass
    _KNOWN_CLASSES = [c.lower() for c in CharacterClass.all_class_names_with_custom()]
except Exception:  # pragma: no cover - importable in isolation
    _KNOWN_CLASSES = [
        "artificer", "bard", "cleric", "druid", "paladin",
        "ranger", "sorcerer", "warlock", "wizard",
    ]

try:
    from feat import DEFAULT_FEAT_TYPES  # noqa: F401  (kept for reference)
except Exception:  # pragma: no cover
    pass


# --------------------------------------------------------------------------- #
# Feat "type" line
# --------------------------------------------------------------------------- #

# Canonical type string -> the bare category phrase that means it. Every
# phrase optionally carries a trailing "Feat"/"Feats" ("Origin Feat",
# "Eldritch Invocation Feat", ...) which is stripped before comparing, so it
# doesn't need to be spelled out here for each type.
_TYPE_PHRASES: List[Tuple[str, str]] = [
    ("Eldritch Invocation", "eldritch invocation"),
    ("Fighting Style", "fighting style"),
    ("Epic Boon", "epic boon"),
    ("Dragonmark", "dragonmark"),
    ("Origin", "origin"),
    ("", "general"),
]


def _match_type_line(line: str) -> Optional[str]:
    """Return the canonical feat type if `line` is a bare category line."""
    s = strip_markdown(line).strip().strip(".")
    low = re.sub(r"\s+feats?$", "", s.lower()).strip()
    for canonical, phrase in _TYPE_PHRASES:
        if low == phrase:
            return canonical
    return None


_PREREQ_ALIASES = ["prerequisite", "prerequisites", "prereq", "pre-requisite"]
_NO_PREREQ_VALUES = {"none", "no prerequisite", "no prerequisites", "n/a", "-", "—", ""}


def _is_prereq_line(line: str) -> bool:
    s = strip_markdown(line).strip()
    low = re.sub(r"[^a-z]", "", s.split(":", 1)[0].lower()) if ":" in s else ""
    return any(low == re.sub(r"[^a-z]", "", a) for a in _PREREQ_ALIASES)


_LABEL_ALIASES: Dict[str, List[str]] = {
    "type": ["type", "feat type", "category"],
    "prereq": _PREREQ_ALIASES,
    "source": ["source", "source book", "sourcebook", "book"],
}


# --------------------------------------------------------------------------- #
# Batch splitting
# --------------------------------------------------------------------------- #

def _anchor_lines(lines: List[str]) -> List[int]:
    """Indices of lines that anchor a feat block (type line or Prerequisite:)."""
    anchors = []
    for i, ln in enumerate(lines):
        if not ln:
            continue
        if _match_type_line(ln) is not None or _is_prereq_line(ln):
            anchors.append(i)
    return anchors


def split_blocks(text: str) -> List[str]:
    """Cut a pasted batch into one string per feat.

    Anchor lines (a bare category line, or a "Prerequisite:" line) close
    together belong to the same feat's header, so they're clustered first;
    each cluster's start, minus the nearest name line above it, marks a split
    point. Falls back to blank-line gaps, then the whole input, when no
    anchors are found at all.
    """
    lines = clean_lines(text)
    anchors = _anchor_lines(lines)

    if not anchors:
        chunks = re.split(r"\n\s*\n\s*\n*", text.strip())
        return [c.strip() for c in chunks if c.strip()] or [text.strip()]

    # Cluster anchors that are within 3 lines of each other (one feat's header
    # commonly has both a type line AND a Prerequisite line).
    clusters: List[int] = [anchors[0]]
    for idx in anchors[1:]:
        if idx - clusters[-1] > 3:
            clusters.append(idx)
        # else: same cluster as the previous anchor: keep the earliest index

    starts: List[int] = []
    for cluster_start in clusters:
        j = cluster_start - 1
        while j >= 0 and not lines[j]:
            j -= 1
        starts.append(j if j >= 0 else cluster_start)

    starts = sorted(set(starts))
    blocks: List[str] = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            blocks.append(chunk)
    return blocks


# --------------------------------------------------------------------------- #
# Spellcasting heuristics (best-effort; never HIGH confidence)
# --------------------------------------------------------------------------- #

_NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
}
_LEVEL_WORDS = {
    "1st": 1, "first": 1, "2nd": 2, "second": 2, "3rd": 3, "third": 3,
    "4th": 4, "fourth": 4, "5th": 5, "fifth": 5,
}


def _guess_spellcasting(description: str) -> Tuple[bool, List[str], Dict[int, int], List[str]]:
    """Best-effort (is_spellcasting, spell_lists, spells_num, set_spells)."""
    text = description.lower()

    is_spellcasting = bool(
        re.search(r"\bcantrips?\b", text) or re.search(r"\bspell slot", text)
        or re.search(r"\b(learn|know|prepare)\b[^.]{0,40}\bspells?\b", text)
    )

    spell_lists: List[str] = []
    m = re.search(r"from the ([a-z, ]+?) spell list", text)
    if m:
        for token in re.split(r",|\band\b", m.group(1)):
            token = token.strip()
            if token in _KNOWN_CLASSES:
                spell_lists.append(token.title())

    spells_num: Dict[int, int] = {}
    for m in re.finditer(r"\b(a|an|one|two|three|four|five|\d+)\s+cantrips?\b", text):
        n = _NUM_WORDS.get(m.group(1), None)
        if n is None:
            try:
                n = int(m.group(1))
            except ValueError:
                continue
        spells_num[0] = spells_num.get(0, 0) + n
        break  # only count once - repeated phrasing shouldn't double up
    for m in re.finditer(
            r"\b(a|an|one|two|three|four|five|\d+)\s+(1st|first|2nd|second|3rd|third|"
            r"4th|fourth|5th|fifth)[- ]level spells?\b", text):
        n = _NUM_WORDS.get(m.group(1))
        if n is None:
            try:
                n = int(m.group(1))
            except ValueError:
                continue
        lvl = _LEVEL_WORDS.get(m.group(2))
        if lvl:
            spells_num[lvl] = spells_num.get(lvl, 0) + n

    set_spells: List[str] = []
    for m in re.finditer(r"\bthe ([A-Z][A-Za-z' -]{2,30}?) spell\b", description):
        name = m.group(1).strip()
        if name.lower() not in ("same", "chosen", "above", "following") and name not in set_spells:
            set_spells.append(name)

    return is_spellcasting, spell_lists, spells_num, set_spells


# --------------------------------------------------------------------------- #
# Block parser
# --------------------------------------------------------------------------- #

def parse_feat_block(text: str) -> ParsedObject:
    obj = ParsedObject(kind="feat", raw_text=text)
    lines = clean_lines(text)
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return obj

    # ---- name: the first non-empty line, unless it's itself an anchor ---- #
    name_idx = 0
    name = strip_markdown(lines[0])
    # Trailing "(Origin Feat)" style parenthetical on the name line.
    paren_type: Optional[str] = None
    pm = re.search(r"\(([^)]+)\)\s*$", name)
    if pm:
        candidate = _match_type_line(pm.group(1))
        if candidate is not None:
            paren_type = candidate
            name = name[:pm.start()].strip()
    obj.set("name", name, Confidence.HIGH if name else Confidence.MISSING)

    found: Dict[str, str] = {}
    if paren_type is not None:
        found["type"] = paren_type

    desc_lines: List[str] = []

    for ln in lines[name_idx + 1:]:
        if not ln:
            desc_lines.append("")
            continue

        pairs = split_labelled_fragments(ln, _LABEL_ALIASES)
        if pairs:
            for key, val in pairs:
                found.setdefault(key, val)
            continue

        m = re.match(r"^(type|feat type|category|prerequisites?|prereq|source)\b"
                     r"[\s:.\-–]+(.+)$", ln, re.I)
        if m:
            key = match_label(m.group(1), _LABEL_ALIASES)
            if key and key not in found:
                found[key] = m.group(2).strip()
                continue

        type_here = _match_type_line(ln)
        if type_here is not None and "type" not in found:
            found["type"] = type_here
            continue

        if _is_prereq_line(ln) and "prereq" not in found:
            # a bare "Prerequisite" line with the value on the next line
            found["prereq"] = ""
            continue

        desc_lines.append(ln)

    # ---- fold ------------------------------------------------------------ #
    if "type" in found:
        obj.set("type", found["type"], Confidence.HIGH)
    else:
        obj.set("type", "", Confidence.MISSING, "assumed General - check the source text")

    if "prereq" in found:
        val = found["prereq"].strip()
        has_prereq = bool(val) and val.lower() not in _NO_PREREQ_VALUES
        obj.set("has_prereq", has_prereq, Confidence.HIGH)
        obj.set("prereq", val if has_prereq else "", Confidence.HIGH)
    else:
        obj.set("has_prereq", False, Confidence.MEDIUM, "no Prerequisite line found")
        obj.set("prereq", "", Confidence.MEDIUM)

    obj.set("source", found.get("source", ""),
            Confidence.HIGH if "source" in found else Confidence.MISSING)

    # description: collapse blank runs into paragraphs joined by a blank line
    # (feats store real "\n\n" between paragraphs, unlike spells' "\" marker).
    paras: List[str] = []
    buf: List[str] = []
    for ln in desc_lines:
        if ln:
            buf.append(ln)
        elif buf:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    description = "\n\n".join(paras).strip()
    obj.set("description", description,
            Confidence.HIGH if len(description) > 15 else Confidence.LOW)

    is_spellcasting, spell_lists, spells_num, set_spells = _guess_spellcasting(description)
    obj.set("is_spellcasting", is_spellcasting,
            Confidence.MEDIUM if is_spellcasting else Confidence.HIGH)
    if is_spellcasting:
        obj.set("spell_lists", spell_lists,
                Confidence.MEDIUM if spell_lists else Confidence.MISSING)
        obj.set("spells_num", spells_num,
                Confidence.MEDIUM if spells_num else Confidence.MISSING)
        obj.set("set_spells", set_spells,
                Confidence.LOW if set_spells else Confidence.MISSING)

    return obj


def parse_feat_text(text: str) -> List[ParsedObject]:
    return [parse_feat_block(b) for b in split_blocks(text)]


def to_feat(obj: ParsedObject):
    from feat import Feat
    return Feat(
        name=obj.get("name") or "",
        type=obj.get("type") or "",
        is_spellcasting=bool(obj.get("is_spellcasting")),
        spell_lists=list(obj.get("spell_lists") or []),
        spells_num=dict(obj.get("spells_num") or {}),
        has_prereq=bool(obj.get("has_prereq")),
        prereq=obj.get("prereq") or "",
        set_spells=list(obj.get("set_spells") or []),
        description=obj.get("description") or "",
        source=obj.get("source") or "",
        is_official=False,
        is_custom=True,
        is_legacy=False,
    )
