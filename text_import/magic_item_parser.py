"""
Rule-based magic item stat-block parser.

Unlike mundane equipment, magic items in every official D&D 5e source (DMG,
SRD, D&D Beyond, 5etools...) share one very consistent header line right under
the name:

    <Type>, <rarity>[ (requires attunement[ by a <class/condition>][, optional])]

e.g. "Wondrous item, uncommon", "Ring, rare (requires attunement)",
"Weapon (longsword), rare (requires attunement by a paladin)". That line is
this parser's anchor for both batch-splitting and rarity/type/attunement
extraction - much like a spell's "Level 3 Evocation" line. Cost/weight/source
are rare in copied item text (real stat blocks don't usually list them) and
fall back to the same labelled-line handling used elsewhere, ending up
flagged for review when absent.
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
from text_import.equipment_parser import _WEIGHT_RE, _guess_tags, _scan_cost_weight

try:
    from magic_item import Rarity
except Exception:  # pragma: no cover - importable in isolation
    Rarity = None

_RARITY_WORD = "common|uncommon|rare|very rare|legendary|artifact"
_RARITY_WORDS = f"{_RARITY_WORD}|varies"

_MI_HEADER_RE = re.compile(
    rf"^(?P<type>[A-Za-z][A-Za-z '\-]*?(?:\s*\([^)]*\))?)\s*,\s*"
    rf"(?:rarity\s+)?(?P<rarity>{_RARITY_WORDS})"
    rf"(?:\s*\((?P<paren>[^)]*)\))?\.?\s*$",
    re.IGNORECASE,
)

# A "family" header lists several rarities side by side, one per bonus/variant,
# e.g. "Uncommon (+1), Rare (+2), or Very Rare (+3)" or "Uncommon (Silver) or
# Rare (Golden)". There's no single rarity to extract, so this is treated the
# same as an explicit "Rarity Varies" header - the tiers stay in the prose.
_MI_MULTI_RARITY_RE = re.compile(
    rf"^(?P<type>[A-Za-z][A-Za-z '\-]*?(?:\s*\([^)]*\))?)\s*,\s*"
    rf"(?:{_RARITY_WORD})\s*\([^)]*\)"
    rf"(?:\s*,?\s*(?:or\s+)?(?:{_RARITY_WORD})\s*\([^)]*\)){{1,}}"
    rf"\s*(?:\((?P<paren>[^)]*attun[^)]*)\))?\.?\s*$",
    re.IGNORECASE,
)

_LABEL_ALIASES: Dict[str, List[str]] = {
    "type": ["type", "category", "item type"],
    "cost": ["cost", "price", "value"],
    "weight": ["weight"],
    "source": ["source", "source book", "sourcebook", "book"],
    "enchanting_materials": ["enchanting materials", "materials"],
    "rarity": ["rarity"],
    "attunement": ["attunement", "attunement requirement"],
}


def _match_header(line: str) -> Optional[Dict[str, Optional[str]]]:
    """Match a "<Type>, <rarity>[ (attunement...)]" header line, including the
    multi-rarity "family" form. Returns {"type", "rarity", "paren"} or None."""
    text = strip_markdown(line).strip()
    m = _MI_HEADER_RE.match(text)
    if m:
        return {"type": m.group("type"), "rarity": m.group("rarity"), "paren": m.group("paren")}
    m = _MI_MULTI_RARITY_RE.match(text)
    if m:
        return {"type": m.group("type"), "rarity": "varies", "paren": m.group("paren")}
    return None


def split_blocks(text: str) -> List[str]:
    """Cut a pasted batch into one string per magic item.

    Anchors on the "<Type>, <rarity>[ (attunement...)]" header line; the name
    is the nearest non-empty line above it. Falls back to a labelled
    "Rarity:"/"Attunement:" line, then blank-line gaps, then the whole input,
    when no item in the paste uses the standard header.
    """
    lines = clean_lines(text)
    header_idx = {i for i, ln in enumerate(lines) if ln and _match_header(ln)}
    label_idx = {
        i for i, ln in enumerate(lines)
        if ln and i not in header_idx
        and split_labelled_fragments(ln, {"rarity": _LABEL_ALIASES["rarity"],
                                          "attunement": _LABEL_ALIASES["attunement"]})
    }
    # A standard header line is itself a complete, unambiguous anchor. A
    # "Rarity:"/"Attunement:" line (the homebrew fallback style) only anchors
    # when it isn't immediately following a header anchor for the same item
    # and it isn't close enough to another such line to be part of one it
    # already joined - cluster all anchors together so a batch that mixes
    # both styles (or splits Rarity:/Attunement: across two lines) still
    # produces one block per item.
    all_anchors = sorted(header_idx | label_idx)

    if not all_anchors:
        chunks = re.split(r"\n\s*\n\s*\n*", text.strip())
        return [c.strip() for c in chunks if c.strip()] or [text.strip()]

    # A header line is a complete anchor on its own and always starts a new
    # item. A label anchor ("Rarity:"/"Attunement:") only merges into the
    # *previous* cluster when that cluster is itself a nearby label anchor
    # (the homebrew style splits rarity/attunement across two short lines) -
    # never into a preceding header, which already fully describes its own
    # item and would otherwise wrongly swallow the next item's labelled
    # header when the two sit close together with no blank line between them.
    clusters: List[int] = [all_anchors[0]]
    cluster_is_label = [all_anchors[0] in label_idx]
    for idx in all_anchors[1:]:
        if idx in label_idx and cluster_is_label[-1] and idx - clusters[-1] <= 3:
            pass  # joins the current label-style cluster
        else:
            clusters.append(idx)
            cluster_is_label.append(idx in label_idx)

    starts: List[int] = []
    for hi in clusters:
        # Walk up past blank lines AND labelled lines (e.g. a "Source:" line
        # that sits between the item name and its "<Type>, <rarity>" header) so
        # the block starts at the real name, not the label.
        j = hi - 1
        while j >= 0 and (not lines[j]
                          or split_labelled_fragments(lines[j], _LABEL_ALIASES)):
            j -= 1
        starts.append(j if j >= 0 else hi)

    starts = sorted(set(starts))
    blocks: List[str] = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            blocks.append(chunk)
    return blocks


def _parse_attunement(paren: Optional[str]) -> Tuple[bool, str, bool]:
    """Return (requires_attunement, restriction_text, optional) from a header's
    parenthetical, e.g. "requires attunement by a Paladin, optional".

    A bare "(requires attunement)" yields ("", requires=True): attunement is
    needed but with no class/kind restriction.
    """
    if not paren:
        return False, "", False
    text = paren.strip()
    if not re.search(r"\battun", text, re.I):
        return False, "", False
    optional = bool(re.search(r"\boptional\b", text, re.I))
    text = re.sub(r"\s*,?\s*\boptional\b", "", text, flags=re.I).strip()
    m = re.search(r"requires?\s+attunement\s*(.*)", text, re.I)
    detail = (m.group(1) if m else text).strip(" ,.")
    return True, detail, optional


def parse_magic_item_block(text: str) -> ParsedObject:
    obj = ParsedObject(kind="magic_item", raw_text=text)
    lines = clean_lines(text)
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return obj

    header_line_idx = None
    for i, ln in enumerate(lines[:4]):
        if _match_header(ln):
            header_line_idx = i
            break

    found: Dict[str, str] = {}
    header_attunement: Tuple[bool, str, bool] = (False, "", False)

    if header_line_idx is None:
        obj.set("name", strip_markdown(lines[0]) or "", Confidence.LOW,
                "no '<Type>, <rarity>' header line found near the top")
        body_start = 1
    else:
        # The name is the nearest line above the header that isn't blank and
        # isn't a labelled line ("Source: ..." commonly sits in between).
        name = ""
        j = header_line_idx - 1
        while j >= 0 and (not lines[j]
                          or split_labelled_fragments(lines[j], _LABEL_ALIASES)):
            j -= 1
        if j >= 0:
            name = strip_markdown(lines[j])
        obj.set("name", name.rstrip(" .*"), Confidence.HIGH if name else Confidence.MISSING)

        m = _match_header(lines[header_line_idx])
        found["type"] = m["type"].strip()
        found["rarity"] = m["rarity"].strip()
        header_attunement = _parse_attunement(m["paren"])
        body_start = header_line_idx + 1

    # Scan every line except the header itself for labelled fields - a
    # "Source:" line often appears *above* the header, not only below it.
    for li, ln in enumerate(lines):
        if not ln or li == header_line_idx:
            continue
        pairs = split_labelled_fragments(ln, _LABEL_ALIASES)
        if pairs:
            for key, val in pairs:
                found.setdefault(key, val)
            continue
        m = re.match(
            r"^(type|category|cost|price|weight|source|enchanting materials|"
            r"materials|rarity|attunement)\b[\s:.\-–]+(.+)$", ln, re.I)
        if m:
            key = match_label(m.group(1), _LABEL_ALIASES)
            if key and key not in found:
                found[key] = m.group(2).strip()

    # Body lines (minus any consumed labelled/header lines) become the
    # description - anything not recognised as a field just stays prose.
    desc_lines: List[str] = []
    for ln in lines[body_start:]:
        if not ln:
            desc_lines.append("")
            continue
        if split_labelled_fragments(ln, _LABEL_ALIASES):
            continue
        if re.match(r"^(type|category|cost|price|weight|source|enchanting materials|"
                    r"materials|rarity|attunement)\b[\s:.\-–]+", ln, re.I):
            continue
        desc_lines.append(ln)

    _scan_cost_weight("\n".join(desc_lines), found)

    # Preserve the source's own capitalisation when it already has some (e.g.
    # "Armor (Any Light, Medium, or Heavy)"); only Title-Case an all-lowercase
    # type like "wondrous item".
    raw_type = found.get("type", "").strip()
    type_val = raw_type if any(c.isupper() for c in raw_type) else raw_type.title()
    obj.set("type", type_val, Confidence.HIGH if raw_type else Confidence.MISSING)

    if "rarity" in found and Rarity is not None:
        rarity = Rarity.from_string(found["rarity"])
        conf = Confidence.HIGH if rarity.value.lower() == found["rarity"].strip().lower() else Confidence.MEDIUM
        obj.set("rarity", rarity, conf)
    else:
        obj.set("rarity", Rarity.COMMON if Rarity is not None else None, Confidence.MISSING)

    if "attunement" in found:
        # An explicit labelled line overrides/supplements the header parse.
        val = found["attunement"].strip()
        if val.lower() in ("none", "no", "n/a", "-", ""):
            obj.set("requires_attunement", False, Confidence.HIGH)
            obj.set("attunement_requirement", "", Confidence.HIGH)
            obj.set("attunement_optional", False, Confidence.HIGH)
        else:
            optional = bool(re.search(r"\boptional\b", val, re.I))
            restriction = re.sub(r"^\s*(?:yes|required|requires?\s+attunement)\b[\s,]*", "",
                                 re.sub(r"\s*,?\s*\boptional\b", "", val, flags=re.I),
                                 flags=re.I).strip(" ,.")
            obj.set("requires_attunement", True, Confidence.HIGH)
            obj.set("attunement_requirement", restriction, Confidence.HIGH)
            obj.set("attunement_optional", optional, Confidence.HIGH)
    else:
        requires, restriction, optional = header_attunement
        obj.set("requires_attunement", requires,
                Confidence.HIGH if header_line_idx is not None else Confidence.MISSING)
        obj.set("attunement_requirement", restriction,
                Confidence.HIGH if header_line_idx is not None else Confidence.MISSING)
        obj.set("attunement_optional", optional,
                Confidence.HIGH if requires else Confidence.MEDIUM)

    obj.set("cost", found.get("cost", ""), Confidence.HIGH if "cost" in found else Confidence.MISSING)

    if "weight" in found:
        m = _WEIGHT_RE.search(found["weight"]) or re.search(r"\d+(?:\.\d+)?", found["weight"])
        weight = float(m.group(1) if (m and m.lastindex) else (m.group(0) if m else 0.0))
        obj.set("weight", weight, Confidence.HIGH if m else Confidence.LOW)
    else:
        obj.set("weight", 0.0, Confidence.MISSING)

    obj.set("source", found.get("source", ""),
            Confidence.HIGH if "source" in found else Confidence.MISSING)

    enchanting_materials = []
    if "enchanting_materials" in found:
        enchanting_materials = [m.strip() for m in found["enchanting_materials"].split(",") if m.strip()]
    obj.set("enchanting_materials", enchanting_materials,
            Confidence.HIGH if enchanting_materials else Confidence.MISSING)

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
            Confidence.HIGH if len(description) > 10 else Confidence.LOW)

    tags = _guess_tags(description)
    obj.set("tags", tags, Confidence.MEDIUM if tags else Confidence.MISSING)

    return obj


def parse_magic_item_text(text: str) -> List[ParsedObject]:
    return [parse_magic_item_block(b) for b in split_blocks(text)]


def to_magic_item(obj: ParsedObject):
    from magic_item import MagicItem, DEFAULT_MAGIC_ITEM_TYPE, Rarity as RarityCls
    rarity = obj.get("rarity")
    if not isinstance(rarity, RarityCls):
        rarity = RarityCls.from_string(str(rarity) if rarity else "Common")
    return MagicItem(
        name=obj.get("name") or "",
        type=obj.get("type") or DEFAULT_MAGIC_ITEM_TYPE,
        cost=obj.get("cost") or "",
        weight=float(obj.get("weight") or 0.0),
        source=obj.get("source") or "",
        enchanting_materials=list(obj.get("enchanting_materials") or []),
        description=obj.get("description") or "",
        tags=list(obj.get("tags") or []),
        properties=list(obj.get("properties") or []),
        rarity=rarity,
        requires_attunement=bool(obj.get("requires_attunement")),
        attunement_requirement=obj.get("attunement_requirement") or "",
        attunement_optional=bool(obj.get("attunement_optional")) if obj.get("requires_attunement") else False,
        is_official=False,
        is_custom=True,
    )
