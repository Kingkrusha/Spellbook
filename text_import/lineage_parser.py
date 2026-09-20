"""
Rule-based lineage (species/race) stat-block parser.

A lineage stat block has two parts: a short header (creature type / size /
speed) and a body of prose that is the lineage description followed by its
traits. Traits almost universally appear as a run-in heading - "Trait Name.
Description..." (sometimes bolded, sometimes "Trait Name: Description") -
which is what this parser looks for once the header fields are stripped out.

Entry points mirror spell_parser.py: split_blocks / parse_lineage_block /
parse_lineage_text / to_lineage.
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

_SIZE_WORDS = r"tiny|small|medium|large|huge|gargantuan"

_LABEL_ALIASES: Dict[str, List[str]] = {
    "creature_type": ["creature type", "type", "species type"],
    "size": ["size"],
    "speed": ["speed", "walking speed", "base speed"],
    "source": ["source", "source book", "sourcebook", "book"],
}

# Unlabelled "Medium Humanoid" / "Small or Medium Fey" header line.
_SIZE_TYPE_LINE_RE = re.compile(
    rf"^(?P<size>(?:{_SIZE_WORDS})(?:\s+or\s+(?:{_SIZE_WORDS}))?)\s+"
    rf"(?P<type>[A-Za-z]+)\.?$",
    re.IGNORECASE,
)

# Unlabelled "Speed 30 feet." / "Speed: 30 ft" (also matches the labelled
# form, so it doubles as a batch-split anchor and a value extractor).
_SPEED_RE = re.compile(r"\bspeed\b\D{0,10}?(\d+)\s*(?:ft\.?|feet)?", re.IGNORECASE)


def _is_stat_line(line: str) -> bool:
    """True when `line` carries a creature-type / size / speed signal."""
    if split_labelled_fragments(line, _LABEL_ALIASES):
        return True
    if _SIZE_TYPE_LINE_RE.match(line):
        return True
    if _SPEED_RE.search(line):
        return True
    return False


# --------------------------------------------------------------------------- #
# Batch splitting
# --------------------------------------------------------------------------- #

def split_blocks(text: str) -> List[str]:
    """Cut a pasted batch into one string per lineage.

    Anchors on lines that carry a creature-type / size / speed signal
    (labelled, or the compact "Medium Humanoid" / "Speed 30 feet" forms).
    Nearby anchors (within 3 lines) cluster into one lineage's header; each
    cluster's start, minus the nearest name line above it, is a split point.
    Falls back to blank-line gaps, then the whole input, when nothing anchors.
    """
    lines = clean_lines(text)
    anchors = [i for i, ln in enumerate(lines) if ln and _is_stat_line(ln)]

    if not anchors:
        chunks = re.split(r"\n\s*\n\s*\n*", text.strip())
        return [c.strip() for c in chunks if c.strip()] or [text.strip()]

    clusters: List[int] = [anchors[0]]
    for idx in anchors[1:]:
        if idx - clusters[-1] > 3:
            clusters.append(idx)

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
# Trait splitting
# --------------------------------------------------------------------------- #

# A short run-in heading followed by its description on the same paragraph:
# "Darkvision. You have Darkvision..." / "Fey Gift: You know the Friends..."
_TRAIT_RUNIN_RE = re.compile(r"^\*{0,2}([A-Z][A-Za-z0-9'/,\- ]{1,45}?)\*{0,2}[:.]\s+(\S.*)$")

# A trait name alone on its own short paragraph, with the description as the
# next paragraph (seen in content copied from wiki-style headers).
_TRAIT_NAME_ONLY_RE = re.compile(r"^\*{0,2}([A-Z][A-Za-z0-9'/,\- ]{1,40})\*{0,2}:?$")

# Function words ignored when judging whether a candidate heading is really a
# short Title Case trait name ("Reach to the Blaze") rather than the first
# sentence of an ordinary paragraph ("Multiple changelings can share a
# persona" / "Flamekin dwell in either Lorwyn or Shadowmoor" - grammatically
# identical in shape to a real header, but lowercase throughout except the
# first word).
_TRAIT_STOPWORDS = {
    "a", "an", "the", "of", "to", "in", "on", "at", "for", "and", "or",
    "with", "from", "by", "as",
}


def _looks_like_trait_name(phrase: str) -> bool:
    """True when `phrase` reads as a short Title Case trait name."""
    words = [w for w in re.split(r"[\s-]+", phrase) if w]
    significant = [w for w in words if w.lower() not in _TRAIT_STOPWORDS]
    if not significant:
        return False
    capitalized = sum(1 for w in significant if w[:1].isupper())
    return (capitalized / len(significant)) >= 0.75


def _split_traits(paragraphs: List[str]) -> Tuple[str, List[Tuple[str, str]]]:
    """Split body paragraphs into (base_description, [(trait_name, trait_desc)])."""
    description_paras: List[str] = []
    traits: List[Tuple[str, str]] = []

    i = 0
    n = len(paragraphs)
    while i < n:
        para = paragraphs[i]
        m = _TRAIT_RUNIN_RE.match(para)
        if m and _looks_like_trait_name(m.group(1)):
            traits.append((m.group(1).strip(), m.group(2).strip()))
            i += 1
            continue

        m2 = _TRAIT_NAME_ONLY_RE.match(para)
        if m2 and len(para) <= 40 and i + 1 < n and _looks_like_trait_name(m2.group(1)):
            traits.append((m2.group(1).strip(), paragraphs[i + 1].strip()))
            i += 2
            continue

        if traits:
            # Continuation of the previous trait's description (a trait that
            # spans more than one paragraph). Lineages store real "\n\n"
            # between paragraphs, unlike spells' "\" marker.
            name, desc = traits[-1]
            traits[-1] = (name, f"{desc}\n\n{para}")
        else:
            description_paras.append(para)
        i += 1

    return "\n\n".join(description_paras).strip(), traits


# --------------------------------------------------------------------------- #
# Block parser
# --------------------------------------------------------------------------- #

def parse_lineage_block(text: str) -> ParsedObject:
    obj = ParsedObject(kind="lineage", raw_text=text)
    lines = clean_lines(text)
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return obj

    name = strip_markdown(lines[0])
    obj.set("name", name, Confidence.HIGH if name else Confidence.MISSING)

    found: Dict[str, str] = {}
    body_lines: List[str] = []

    for ln in lines[1:]:
        if not ln:
            body_lines.append("")
            continue

        pairs = split_labelled_fragments(ln, _LABEL_ALIASES)
        if pairs:
            for key, val in pairs:
                found.setdefault(key, val)
            continue

        m = re.match(
            r"^(creature\s*type|type|size|speed|walking\s*speed|base\s*speed|source)\b"
            r"[\s:.\-–]+(.+)$", ln, re.I)
        if m:
            key = match_label(m.group(1), _LABEL_ALIASES)
            if key and key not in found:
                found[key] = m.group(2).strip()
                continue

        st = _SIZE_TYPE_LINE_RE.match(ln)
        if st and "size" not in found and "creature_type" not in found:
            found["size"] = st.group("size")
            found["creature_type"] = st.group("type")
            continue

        sm = _SPEED_RE.search(ln)
        if sm and "speed" not in found and len(ln) < 40:
            found["speed"] = sm.group(1)
            continue

        body_lines.append(ln)

    if "creature_type" in found:
        obj.set("creature_type", found["creature_type"].strip().title(), Confidence.HIGH)
    else:
        obj.set("creature_type", "Humanoid", Confidence.MISSING, "not found; defaulted")

    if "size" in found:
        size = " ".join(w if w.lower() == "or" else w.title() for w in found["size"].split())
        obj.set("size", size, Confidence.HIGH)
    else:
        obj.set("size", "Medium", Confidence.MISSING, "not found; defaulted")

    if "speed" in found:
        m = re.search(r"\d+", found["speed"])
        obj.set("speed", int(m.group()) if m else 30, Confidence.HIGH if m else Confidence.LOW)
    else:
        obj.set("speed", 30, Confidence.MISSING, "not found; defaulted")

    obj.set("source", found.get("source", ""),
            Confidence.HIGH if "source" in found else Confidence.MISSING)

    # Group remaining lines into blank-line-separated paragraphs.
    paragraphs: List[str] = []
    buf: List[str] = []
    for ln in body_lines:
        if ln:
            buf.append(ln)
        elif buf:
            paragraphs.append(" ".join(buf))
            buf = []
    if buf:
        paragraphs.append(" ".join(buf))

    description, traits = _split_traits(paragraphs)
    obj.set("description", description,
            Confidence.HIGH if len(description) > 15 else Confidence.LOW)
    obj.set("traits", traits,
            Confidence.MEDIUM if traits else Confidence.MISSING,
            "" if traits else "no traits detected - check the paste's formatting")

    return obj


def parse_lineage_text(text: str) -> List[ParsedObject]:
    return [parse_lineage_block(b) for b in split_blocks(text)]


def to_lineage(obj: ParsedObject):
    from lineage import Lineage, LineageTrait
    traits = [
        LineageTrait(name=n, description=d)
        for n, d in (obj.get("traits") or [])
    ]
    return Lineage(
        name=obj.get("name") or "",
        description=obj.get("description") or "",
        creature_type=obj.get("creature_type") or "Humanoid",
        size=obj.get("size") or "Medium",
        speed=int(obj.get("speed") or 30),
        traits=traits,
        source=obj.get("source") or "",
        is_official=False,
        is_custom=True,
        is_legacy=False,
    )
