"""
Shared helpers for rule-based stat-block parsing.

The design goal is tolerance for messy input:
  * fields may appear in any order,
  * labels may be missing, abbreviated, or renamed,
  * several labelled fields may share one physical line,
  * a batch of objects may be pasted with no numbering or separators.

Everything here is generic; per-type logic (spell / lineage / feat) lives in
sibling modules and builds on these primitives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class Confidence(str, Enum):
    """How much a reviewer should trust an auto-filled value."""
    HIGH = "high"        # taken from an explicit label or an unambiguous pattern
    MEDIUM = "medium"    # inferred from an unlabelled heuristic
    LOW = "low"          # a weak guess; reviewer should confirm
    MISSING = "missing"  # nothing found; reviewer must fill it in

    def worse_than(self, other: "Confidence") -> bool:
        order = [Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW, Confidence.MISSING]
        return order.index(self) > order.index(other)


@dataclass
class FieldResult:
    """One parsed field: its value, how it was found, and a human note."""
    value: object = None
    confidence: Confidence = Confidence.MISSING
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.confidence != Confidence.MISSING


@dataclass
class ParsedObject:
    """Result of parsing a single stat block."""
    kind: str                                   # "spell" | "lineage" | "feat"
    fields: Dict[str, FieldResult] = field(default_factory=dict)
    raw_text: str = ""
    unconsumed_lines: List[str] = field(default_factory=list)

    def set(self, name: str, value, confidence: Confidence, note: str = "") -> None:
        self.fields[name] = FieldResult(value, confidence, note)

    def get(self, name: str):
        fr = self.fields.get(name)
        return fr.value if fr else None

    def needs_review(self) -> List[str]:
        """Field names a reviewer should look at (missing or low confidence)."""
        return [
            n for n, fr in self.fields.items()
            if fr.confidence in (Confidence.LOW, Confidence.MISSING)
        ]

    def uncertain_fields(self) -> List[str]:
        """Every field that was not taken verbatim from a label (i.e. not HIGH)."""
        return [
            n for n, fr in self.fields.items()
            if fr.confidence != Confidence.HIGH
        ]


# --------------------------------------------------------------------------- #
# Line / label utilities
# --------------------------------------------------------------------------- #

_LABEL_SPLIT_RE = re.compile(r"\s*[:–—\-]\s+|\s*:\s*")


_FULLY_WRAPPED_RE = re.compile(r"^(\*{1,3}|_{1,3})(.+?)\1$")


def clean_lines(text: str) -> List[str]:
    """Normalise whitespace and drop obvious decoration lines.

    Markdown emphasis is only unwrapped when it wraps the WHOLE line (e.g. a
    "**Fireball**" heading line, or "***Spike Growth***"). A line like
    "*Repeatable.* You can take this feat more than once." is left untouched -
    a naive `.strip("*_")` would strip only the leading `*` (since the line
    doesn't end in one), leaving a stray asterisk stranded mid-sentence and
    corrupting the saved description. Feats in particular store this exact
    "*Sub-heading.* text..." convention as real content, not decoration.
    """
    out: List[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        m = _FULLY_WRAPPED_RE.match(line)
        if m and m.group(2).strip():
            line = m.group(2).strip()
        line = re.sub(r"^#+\s*", "", line)           # markdown headings
        if set(line) <= {"-", "=", "_", "—", "–", " "} and line:
            continue                                 # horizontal rule
        out.append(line)
    return out


def begin_block(kind: str, text: str):
    """How every block parser starts: ``(the empty ParsedObject, the block's cleaned lines without leading blanks)``.

    An empty ``lines`` means there is nothing to parse and the object is returned as it is."""
    lines = clean_lines(text)
    while lines and not lines[0]:
        lines.pop(0)
    return ParsedObject(kind=kind, raw_text=text), lines


def strip_markdown(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s.strip()


def normalise_label(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def match_label(candidate: str, aliases: Dict[str, List[str]]) -> Optional[str]:
    """Return the canonical key whose alias set contains `candidate`."""
    key = normalise_label(candidate)
    if not key:
        return None
    for canonical, names in aliases.items():
        for name in names:
            if key == normalise_label(name):
                return canonical
    return None


_LABEL_RE_CACHE: Dict[int, "re.Pattern"] = {}


def _label_regex(aliases: Dict[str, List[str]]) -> "re.Pattern":
    key = id(aliases)
    cached = _LABEL_RE_CACHE.get(key)
    if cached is None:
        spellings = sorted(
            {n for names in aliases.values() for n in names},
            key=len, reverse=True,
        )
        alt = "|".join(re.escape(s) for s in spellings)
        cached = re.compile(rf"(?<![A-Za-z])({alt})\s*:\s*", re.IGNORECASE)
        _LABEL_RE_CACHE[key] = cached
    return cached


def first_label_start(line: str, aliases: Dict[str, List[str]]) -> Optional[int]:
    """Character offset of the first ``Label:`` on the line, or None."""
    m = _label_regex(aliases).search(line)
    return m.start() if m else None


def split_labelled_fragments(line: str, aliases: Dict[str, List[str]]) -> List[tuple]:
    """
    Pull every `Label: value` pair out of one physical line.

    Handles the common compact layout where casting time, range, components and
    duration are all crammed onto a single line. Returns a list of
    (canonical_key, value) tuples; empty if the line carries no known label.
    """
    marks = list(_label_regex(aliases).finditer(line))
    if not marks:
        return []

    results = []
    for i, m in enumerate(marks):
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(line)
        value = line[start:end].strip().strip(";,. ")
        canonical = match_label(m.group(1), aliases)
        if canonical and value:
            results.append((canonical, value))
    return results


# --------------------------------------------------------------------------- #
# Domain vocab shared by the description-tag heuristics
# --------------------------------------------------------------------------- #

SCHOOLS = [
    "abjuration", "conjuration", "divination", "enchantment",
    "evocation", "illusion", "necromancy", "transmutation",
]

DAMAGE_TYPES = [
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
]

AOE_SHAPES = ["sphere", "cube", "cone", "line", "cylinder", "emanation", "wall", "radius"]

DICE_RE = re.compile(r"\b\d+d\d+\b", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# Splitting a pasted batch into one block per object
# --------------------------------------------------------------------------- #

def split_on_blank_gaps(text: str) -> List[str]:
    """The fallback when nothing anchors a block: chunks separated by blank-line gaps, else the whole text."""
    chunks = re.split(r"\n\s*\n\s*\n*", text.strip())
    return [c.strip() for c in chunks if c.strip()] or [text.strip()]


def cluster_anchors(anchors: List[int], gap: int = 3) -> List[int]:
    """Anchor lines within ``gap`` lines of the previous one belong to the same header (a feat has both a
    category line and a Prerequisite line); returns the first line of each cluster."""
    clusters: List[int] = [anchors[0]]
    for idx in anchors[1:]:
        if idx - clusters[-1] > gap:
            clusters.append(idx)
    return clusters


def blocks_from_anchors(lines: List[str], anchors: List[int],
                        skip_line: Optional[Callable[[str], bool]] = None) -> List[str]:
    """One block per anchor: an object's name is the nearest line above its anchor that is not blank (nor
    matched by ``skip_line``, e.g. a "Source:" line sitting between name and header), and its block runs to
    the line before the next object's name."""
    starts: List[int] = []
    for anchor in anchors:
        j = anchor - 1
        while j >= 0 and (not lines[j] or (skip_line is not None and skip_line(lines[j]))):
            j -= 1
        starts.append(j if j >= 0 else anchor)

    starts = sorted(set(starts))
    blocks: List[str] = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            blocks.append(chunk)
    return blocks


def join_paragraphs(lines: List[str], separator: str) -> str:
    """Description lines -> text: runs of lines are one paragraph; blank lines end it; paragraphs are joined by
    ``separator`` (spells use a backslash, everything else a blank line)."""
    paras: List[str] = []
    buf: List[str] = []
    for ln in lines:
        if ln:
            buf.append(ln)
        elif buf:
            paras.append(" ".join(buf))
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return separator.join(paras).strip()


_FALLBACK_CLASSES = ["artificer", "bard", "cleric", "druid", "paladin", "ranger", "sorcerer", "warlock", "wizard"]


def known_class_names() -> List[str]:
    """Lower-case class names (including custom ones) when run inside the app, else the standard list."""
    try:
        from spell import CharacterClass
        return [c.lower() for c in CharacterClass.all_class_names_with_custom()]
    except Exception:  # pragma: no cover - importable in isolation
        return list(_FALLBACK_CLASSES)


def guess_description_tags(description: str, school: Optional[str]) -> List[str]:
    """Best-effort semantic tags from the spell body (all MEDIUM confidence)."""
    text = description.lower()
    tags: List[str] = []

    if school:
        tags.append(school.capitalize())

    no_damage = "no damage" in text or "takes no damage" in text
    deals_damage = (
        not no_damage and (
            (bool(DICE_RE.search(text)) and "damage" in text)
            or re.search(r"takes?\s+\d[^.]*damage", text)
        )
    )
    if deals_damage:
        tags.append("Damage")
        for dt in DAMAGE_TYPES:
            if re.search(rf"\b{dt}\b\s+damage", text) or re.search(rf"\bdamage\b[^.]*\b{dt}\b", text):
                tags.append(dt.capitalize())

    if "saving throw" in text:
        tags.append("Saving Throw")
    if "spell attack" in text or "attack roll" in text:
        tags.append("Attack")
    if (re.search(r"regain(s)?\b[^.]*hit points", text)
            or re.search(r"hit points?\b[^.]*\bincrease", text)
            or re.search(r"\bheals?\b|\bhealing\b", text)):
        tags.append("Healing")
    for shape in AOE_SHAPES:
        if re.search(rf"\b\d+[- ]?foot[- ]?(?:radius[- ]?)?{shape}\b", text) or f"-foot {shape}" in text:
            tags.append("AOE")
            break

    if "advantage on" in text or "bonus to" in text or "you have resistance" in text:
        tags.append("Buff")
    if "disadvantage on" in text or "speed is reduced" in text or "has the " in text and "condition" in text:
        tags.append("Debuff")

    if "Damage" not in tags and "Healing" not in tags:
        tags.append("Utility")

    # de-dup, keep order
    seen = set()
    ordered = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered
