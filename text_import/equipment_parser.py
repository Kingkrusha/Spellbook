"""
Rule-based equipment stat-block parser.

Equipment text is the least standardized of the content types this app
auto-detects: mundane gear ranges from a one-line table row ("Longsword, 15
gp, 1d8 slashing, 3 lb., Versatile") to a full prose description with labelled
fields. Rather than anchoring on one exact layout, this parser:

* anchors batch-splitting on whichever of a Cost token (``15 gp``), a Weight
  token (``3 lb.``), or a labelled Type/Cost/Weight line appears first for
  each item,
* pulls Cost/Weight/Type/Source/Crafting Materials/Crafting Tool from labelled
  lines when present (tolerant to renamed/missing labels, several labels per
  line - same primitives as the spell/feat/lineage parsers),
* falls back to scanning the whole block for a cost/weight token when no
  label carried it (common in copy-pasted table rows),
* guesses tags from the description: damage dice, damage type, weapon/armor
  category, and common weapon properties.
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
    from equipment import DAMAGE_TYPES, EQUIPMENT_TYPE_OPTIONS
except Exception:  # pragma: no cover - importable in isolation
    DAMAGE_TYPES = [
        "Bludgeoning", "Piercing", "Slashing", "Acid", "Cold", "Fire", "Force",
        "Lightning", "Necrotic", "Poison", "Psychic", "Radiant", "Thunder",
    ]
    EQUIPMENT_TYPE_OPTIONS = [
        "Adventuring Gear", "Ammunition", "Armor", "Clothing", "Container",
        "Food and Drink", "Melee Weapon", "Mount and Vehicle", "Potion",
        "Ranged Weapon", "Shield", "Tool", "Trade Good",
    ]

_LABEL_ALIASES: Dict[str, List[str]] = {
    "type": ["type", "category", "item type"],
    "cost": ["cost", "price", "value"],
    "weight": ["weight"],
    "source": ["source", "source book", "sourcebook", "book"],
    "crafting_materials": ["crafting materials", "materials"],
    "crafting_tool": ["crafting tool", "tool", "tools required"],
}

_COST_RE = re.compile(r"\b\d[\d,]*\+?\s*(?:cp|sp|ep|gp|pp)\b", re.IGNORECASE)
_WEIGHT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:lbs?\.?|pounds?)\b", re.IGNORECASE)
_DICE_RE = re.compile(r"\b(\d+d\d+)\b", re.IGNORECASE)

_WEAPON_PROPERTIES = [
    "finesse", "versatile", "two-handed", "reach", "thrown", "light", "heavy",
    "loading", "special", "ammunition",
]


def _is_anchor_line(line: str) -> bool:
    if split_labelled_fragments(line, _LABEL_ALIASES):
        return True
    if _COST_RE.search(line) or _WEIGHT_RE.search(line):
        return True
    return False


def split_blocks(text: str) -> List[str]:
    """Cut a pasted batch into one string per item.

    A copy-pasted reference table (one item per line, tab- or
    whitespace-delimited) is detected first and split one row per line - the
    prose-block anchor logic below would otherwise merge dozens of one-line
    rows into a handful of oversized blocks, since each row anchors and
    consecutive rows sit only one line apart.

    Otherwise, anchors on a line that carries a cost token, a weight token, or
    a labelled Type/Cost/Weight field; nearby anchors (within 3 lines) cluster
    into one item's header block, and each cluster's start - minus the
    nearest name line above it - is a split point. Falls back to blank-line
    gaps, then the whole input, when nothing anchors.
    """
    table = _detect_table_rows(text)
    if table is not None:
        data_rows, _roles = table
        # Drop repeated header rows (a paste that concatenates several sub-tables
        # carries a "Name  Damage  ..." line before each) so the preview count
        # matches what parse_equipment_text actually yields.
        return ["\t".join(r) for r in data_rows
                if r and r[0].strip().lower() not in _TABLE_HEADER_LABELS]

    lines = clean_lines(text)
    anchors = [i for i, ln in enumerate(lines) if ln and _is_anchor_line(ln)]

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


def _match_type(value: str) -> Optional[str]:
    low = value.strip().lower()
    for option in EQUIPMENT_TYPE_OPTIONS:
        if option.lower() == low:
            return option
    return None


# Phrases that mean a nearby damage-type/armor-class word describes something
# the item resists, is immune to, or that a *different* thing is not, rather
# than something the item deals or is - e.g. "Immunity to ... Psychic damage"
# (of the net itself, not what it deals), "saving throws against extreme
# cold" (weather, not cold damage), "not wearing ... Heavy armor".
_NEGATED_CONTEXT_RE = re.compile(
    r"\b(?:immunit(?:y|ies)\s+to|immune\s+to|resistance\s+to|resistant\s+to|"
    r"against(?:\s+\w+){0,4}\s+extreme|not\s+wearing|without\s+wearing)\b",
    re.IGNORECASE,
)


def _has_unnegated_match(pattern: str, text: str, window: int = 60) -> bool:
    """True if `pattern` matches somewhere not immediately preceded by a
    resistance/immunity/negation phrase within `window` characters."""
    for m in re.finditer(pattern, text, re.IGNORECASE):
        preceding = text[max(0, m.start() - window):m.start()]
        if not _NEGATED_CONTEXT_RE.search(preceding):
            return True
    return False


def _guess_tags(description: str) -> List[str]:
    text = description.lower()
    tags: List[str] = []

    for m in _DICE_RE.finditer(text):
        die = "d" + m.group(1).split("d")[1]
        if die not in tags:
            tags.append(die)

    for dt in DAMAGE_TYPES:
        # "extreme cold"/"extreme heat" is always the environmental-exposure
        # rule (surviving a blizzard), never a damage type an item deals -
        # this phrasing recurs often enough (and far enough from any
        # "against"/"immune to" trigger, e.g. a boilerplate "see the DMG for
        # rules on extreme cold" aside) to special-case directly.
        pattern = rf"\b{dt.lower()}\b"
        matches = [m for m in re.finditer(pattern, text)
                   if not re.search(r"extreme\s+$", text[max(0, m.start() - 10):m.start()])]
        if matches and any(not _NEGATED_CONTEXT_RE.search(text[max(0, m.start() - 60):m.start()])
                            for m in matches):
            tags.append(dt)

    if re.search(r"\bsimple\b.{0,10}\bweapon", text) or re.search(r"\bsimple\s+(melee|ranged)\b", text):
        tags.append("Simple Weapon")
    if re.search(r"\bmartial\b.{0,10}\bweapon", text) or re.search(r"\bmartial\s+(melee|ranged)\b", text):
        tags.append("Martial Weapon")

    for weight_class in ("Light", "Medium", "Heavy"):
        if _has_unnegated_match(rf"\b{weight_class.lower()}\s+armor\b", text):
            tags.append(f"{weight_class} Armor")

    for prop in _WEAPON_PROPERTIES:
        if prop in ("light", "heavy", "reach", "special", "loading"):
            # These double as ordinary English outside a weapon-property list
            # ("bright light", "a heavy blow", "within its reach") - only
            # treat them as the property when they sit in a comma-separated
            # list, e.g. "Finesse, light, thrown".
            pattern = rf"(?:^|,\s*){prop}\b\s*(?:,|\(|$)"
            matched = bool(re.search(pattern, text, re.MULTILINE))
        else:
            matched = bool(re.search(rf"\b{re.escape(prop)}\b", text))
        if matched:
            tags.append(prop.title() if prop != "two-handed" else "Two-Handed")

    seen = set()
    ordered = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


def _scan_cost_weight(text: str, found: Dict[str, str]) -> None:
    """Fallback: pull cost/weight tokens from anywhere in the block."""
    if "cost" not in found:
        m = _COST_RE.search(text)
        if m:
            found["cost"] = m.group(0)
    if "weight" not in found:
        m = _WEIGHT_RE.search(text)
        if m:
            found["weight"] = m.group(0)


# --------------------------------------------------------------------------- #
# Table mode: one item per line (a copy-pasted TSV/whitespace-aligned table,
# e.g. an "Item / Weight / Cost / Function" reference table). This is a
# different shape from a prose stat block, and the classic "cluster nearby
# anchors" splitter above massively under-splits it (every row anchors, and
# consecutive rows sit only one line apart) - so it's detected and handled
# separately, ahead of the anchor-based path.
# --------------------------------------------------------------------------- #

_COLUMN_ROLE_KEYWORDS: Dict[str, List[str]] = {
    "name": ["item", "name"],
    "weight": ["weight", "wt"],
    "cost": ["cost", "price", "value"],
    "damage": ["damage", "dmg"],
    "mastery": ["mastery"],
    "properties": ["properties", "property", "traits"],
    "description": ["function", "description", "effect", "notes"],
}

# A lone dash in a cell means "nothing here" (the Properties column of a
# weapon with no properties, etc.) - never literal text to keep.
_EMPTY_CELL_TOKENS = {"", "-", "—", "–", "--", "n/a", "none"}

_FRACTION_CHARS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}

_TABLE_HEADER_LABELS = {
    w for words in _COLUMN_ROLE_KEYWORDS.values() for w in words
}


def _split_table_row(line: str) -> Optional[List[str]]:
    """Split one line into table cells (tab-delimited, or 2+-space-aligned)."""
    line = line.strip()
    if not line:
        return None
    if "\t" in line:
        fields = [f.strip() for f in line.split("\t")]
    else:
        fields = [f.strip() for f in re.split(r"\s{2,}", line)]
    fields = [f for f in fields if f != ""]
    return fields if len(fields) >= 2 else None


def _detect_table_rows(text: str) -> Optional[Tuple[List[List[str]], Dict[int, str]]]:
    """Return (data_rows, column_roles) if `text` looks like a gear table.

    `column_roles` maps a column index to "name"/"weight"/"cost"/"description"
    when a header row (e.g. "Item  Weight  Cost  Function") was found;
    otherwise it's empty and each row is classified by content instead.
    """
    raw_lines = [ln for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    all_rows: List[List[str]] = []
    for ln in raw_lines:
        row = _split_table_row(ln)
        if row:
            all_rows.append(row)

    multi_field = [r for r in all_rows if len(r) >= 3]
    if len(multi_field) < 3 or len(multi_field) < 0.5 * max(len(all_rows), 1):
        return None  # not enough consistent rows to call this a table

    column_roles: Dict[int, str] = {}
    header_row: Optional[List[str]] = None
    for row in all_rows[:3]:
        roles: Dict[int, str] = {}
        for ci, cell in enumerate(row):
            norm = re.sub(r"[^a-z]", "", cell.lower())
            for role, keywords in _COLUMN_ROLE_KEYWORDS.items():
                if norm in keywords:
                    roles[ci] = role
                    break
        if len(roles) >= 2 and "name" in roles.values():
            column_roles = roles
            header_row = row
            break

    data_rows = [r for r in all_rows if r is not header_row and len(r) >= 2]
    return data_rows, column_roles


def _parse_weight_field(raw: str) -> Tuple[float, Confidence]:
    text = raw.strip()
    low = text.lower()
    if low in ("-", "—", "", "n/a", "none"):
        return 0.0, Confidence.MISSING
    if low == "varies":
        return 0.0, Confidence.LOW

    for frac_char, frac_val in _FRACTION_CHARS.items():
        if frac_char in text:
            m = re.search(rf"(\d+)?\s*{frac_char}", text)
            whole = int(m.group(1)) if m and m.group(1) else 0
            return whole + frac_val, Confidence.HIGH

    m = re.match(r"(\d+)\s*/\s*(\d+)", text)
    if m:
        return int(m.group(1)) / int(m.group(2)), Confidence.HIGH

    m = _WEIGHT_RE.search(text)
    if m:
        return float(m.group(1)), Confidence.HIGH

    m = re.search(r"\d+(?:\.\d+)?", text)
    if m:
        return float(m.group(0)), Confidence.MEDIUM

    return 0.0, Confidence.LOW


def _row_to_parsed_object(fields: List[str], column_roles: Dict[int, str]) -> Optional[ParsedObject]:
    name: Optional[str] = None
    weight_field: Optional[str] = None
    cost_field: Optional[str] = None
    damage_field: Optional[str] = None
    mastery_field: Optional[str] = None
    properties_field: Optional[str] = None
    desc_parts: List[str] = []

    if column_roles:
        for ci, cell in enumerate(fields):
            role = column_roles.get(ci)
            if role == "name" and name is None:
                name = cell
            elif role == "weight" and weight_field is None:
                weight_field = cell
            elif role == "cost" and cost_field is None:
                cost_field = cell
            elif role == "damage" and damage_field is None:
                damage_field = cell
            elif role == "mastery" and mastery_field is None:
                mastery_field = cell
            elif role == "properties" and properties_field is None:
                properties_field = cell
            else:
                desc_parts.append(cell)
    else:
        if not fields:
            return None
        name = fields[0]
        for cell in fields[1:]:
            if cost_field is None and (_COST_RE.search(cell) or cell.strip().lower() == "varies"):
                cost_field = cell
            elif weight_field is None and (
                    _WEIGHT_RE.search(cell) or re.match(r"^\d+(?:\.\d+)?$", cell.strip())
                    or any(c in cell for c in _FRACTION_CHARS) or "/" in cell
                    or cell.strip() in ("-", "—") or cell.strip().lower() == "varies"):
                weight_field = cell
            else:
                desc_parts.append(cell)

    if not name or not re.match(r"^[A-Za-z0-9]", name) or name.lower() in _TABLE_HEADER_LABELS:
        return None

    obj = ParsedObject(kind="equipment")
    obj.set("name", strip_markdown(name), Confidence.HIGH)

    if cost_field is not None:
        obj.set("cost", cost_field.strip(), Confidence.HIGH)
    else:
        obj.set("cost", "", Confidence.MISSING)

    if weight_field is not None:
        weight, conf = _parse_weight_field(weight_field)
        obj.set("weight", weight, conf)
    else:
        obj.set("weight", 0.0, Confidence.MISSING)

    obj.set("type", "", Confidence.MISSING, "not found; defaults to Adventuring Gear")
    obj.set("source", "", Confidence.MISSING)
    obj.set("crafting_materials", [], Confidence.MISSING)
    obj.set("crafting_tool", "", Confidence.MISSING)

    def _clean(cell: Optional[str]) -> str:
        cell = (cell or "").strip()
        return "" if cell.lower() in _EMPTY_CELL_TOKENS else cell

    # A weapon-style table gives Damage / Properties / Mastery their own
    # columns. Route Properties + Mastery into the structured `properties`
    # list (descriptions left blank - a plain table has no glossary), and keep
    # the free-text description to just the damage line, so an auto-detected
    # weapon lands the same shape as curated content.
    damage_field = _clean(damage_field)
    mastery_field = _clean(mastery_field)
    properties_field = _clean(properties_field)
    leftover = " ".join(p for p in (_clean(p) for p in desc_parts) if p).strip()

    properties: List[dict] = []
    if properties_field:
        for entry in re.split(r",\s*(?![^(]*\))", properties_field):
            entry = entry.strip()
            if entry:
                properties.append({"name": entry, "description": ""})
    if mastery_field:
        properties.append({"name": f"Mastery, {mastery_field}", "description": ""})
    obj.set("properties", properties,
            Confidence.MEDIUM if properties else Confidence.MISSING)

    if damage_field or mastery_field or properties_field:
        desc_lines = []
        if damage_field:
            desc_lines.append(f"**Damage:** {damage_field}")
        if leftover:
            desc_lines.append(leftover)
        description = "\n\n".join(desc_lines)
    else:
        description = leftover

    obj.set("description", description,
            Confidence.HIGH if len(description) > 5 else Confidence.LOW)

    tag_source = " ".join(x for x in (damage_field, properties_field, leftover) if x) or description
    tags = _guess_tags(tag_source)
    obj.set("tags", tags, Confidence.MEDIUM if tags else Confidence.MISSING)

    return obj


def parse_equipment_block(text: str) -> ParsedObject:
    obj = ParsedObject(kind="equipment", raw_text=text)
    lines = clean_lines(text)
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return obj

    name = strip_markdown(lines[0])
    obj.set("name", name, Confidence.HIGH if name else Confidence.MISSING)

    found: Dict[str, str] = {}
    desc_lines: List[str] = []

    for ln in lines[1:]:
        if not ln:
            desc_lines.append("")
            continue

        pairs = split_labelled_fragments(ln, _LABEL_ALIASES)
        if pairs:
            labels_here = {k for k, _ in pairs}
            for key, val in pairs:
                found.setdefault(key, val)
                labels_here.add(key)
            residual = ln
            for _key, val in pairs:
                residual = residual.replace(val, " ", 1)
            _scan_cost_weight(residual, found)
            continue

        m = re.match(
            r"^(type|category|cost|price|weight|source|crafting materials|"
            r"materials|crafting tool|tools?)\b[\s:.\-–]+(.+)$", ln, re.I)
        if m:
            key = match_label(m.group(1), _LABEL_ALIASES)
            if key and key not in found:
                found[key] = m.group(2).strip()
                continue

        desc_lines.append(ln)

    # A cost/weight token can also be sitting inline in an otherwise-prose
    # first description line (common in a pasted table row) - scan the whole
    # remaining body once as a last resort.
    _scan_cost_weight("\n".join(desc_lines), found)

    if "type" in found:
        matched_type = _match_type(found["type"])
        obj.set("type", matched_type or found["type"].strip().title(),
                Confidence.HIGH if matched_type else Confidence.MEDIUM)
    else:
        obj.set("type", "", Confidence.MISSING, "not found; defaults to Adventuring Gear")

    if "cost" in found:
        obj.set("cost", found["cost"].strip(), Confidence.HIGH)
    else:
        obj.set("cost", "", Confidence.MISSING)

    if "weight" in found:
        m = _WEIGHT_RE.search(found["weight"]) or re.search(r"\d+(?:\.\d+)?", found["weight"])
        weight = float(m.group(1) if m.lastindex else m.group(0)) if m else 0.0
        obj.set("weight", weight, Confidence.HIGH if m else Confidence.LOW)
    else:
        obj.set("weight", 0.0, Confidence.MISSING)

    obj.set("source", found.get("source", ""),
            Confidence.HIGH if "source" in found else Confidence.MISSING)

    crafting_materials = []
    if "crafting_materials" in found:
        crafting_materials = [m.strip() for m in found["crafting_materials"].split(",") if m.strip()]
    obj.set("crafting_materials", crafting_materials,
            Confidence.HIGH if crafting_materials else Confidence.MISSING)

    obj.set("crafting_tool", found.get("crafting_tool", ""),
            Confidence.HIGH if "crafting_tool" in found else Confidence.MISSING)

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


def parse_equipment_text(text: str) -> List[ParsedObject]:
    table = _detect_table_rows(text)
    if table is not None:
        data_rows, column_roles = table
        objs = [_row_to_parsed_object(r, column_roles) for r in data_rows]
        return [o for o in objs if o is not None]

    return [parse_equipment_block(b) for b in split_blocks(text)]


def to_equipment(obj: ParsedObject):
    from equipment import Equipment, DEFAULT_EQUIPMENT_TYPE
    return Equipment(
        name=obj.get("name") or "",
        type=obj.get("type") or DEFAULT_EQUIPMENT_TYPE,
        cost=obj.get("cost") or "",
        weight=float(obj.get("weight") or 0.0),
        source=obj.get("source") or "",
        crafting_materials=list(obj.get("crafting_materials") or []),
        crafting_tool=obj.get("crafting_tool") or "",
        description=obj.get("description") or "",
        tags=list(obj.get("tags") or []),
        properties=list(obj.get("properties") or []),
        is_official=False,
        is_custom=True,
    )
