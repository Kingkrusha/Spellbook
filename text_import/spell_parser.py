"""
Rule-based spell stat-block parser.

Entry points
------------
split_blocks(text)      -> List[str]   : cut a pasted batch into per-spell chunks
parse_spell_block(text) -> ParsedObject: parse one chunk
parse_spell_text(text)  -> List[ParsedObject]: do both

The parser anchors on the "level / school" header line (``Level 3 Evocation``,
``Evocation Cantrip``, ``3rd-level evocation``...). That line is the single most
reliable landmark in the format, so it drives both batch splitting (the name is
the line just above it) and per-field parsing. Everything after the header that
is not recognised as a meta field becomes the description.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from text_import.base import (
    Confidence,
    ParsedObject,
    clean_lines,
    guess_description_tags,
    split_labelled_fragments,
    strip_markdown,
)

try:  # keep the parser importable in isolation (tests, notebooks)
    from spell import CharacterClass
    _KNOWN_CLASSES = [c.lower() for c in CharacterClass.all_class_names_with_custom()]
except Exception:  # pragma: no cover
    CharacterClass = None
    _KNOWN_CLASSES = [
        "artificer", "bard", "cleric", "druid", "paladin",
        "ranger", "sorcerer", "warlock", "wizard",
    ]


# --------------------------------------------------------------------------- #
# Header detection
# --------------------------------------------------------------------------- #

_SCHOOLS = (
    "abjuration|conjuration|divination|enchantment|"
    "evocation|illusion|necromancy|transmutation"
)

_HEADER_PATTERNS = [
    # "Level 3 Evocation"  /  "Level 3 - Evocation"  /  "Level 3: Evocation"
    re.compile(rf"^level\s+(?P<lvl>[0-9])\b[\s\-–—:,]*(?P<school>{_SCHOOLS})?", re.I),
    # "3rd-level evocation"  /  "3rd level, evocation"
    re.compile(rf"^(?P<lvl>[0-9])(?:st|nd|rd|th)[\s\-]level[\s,:\-]*(?P<school>{_SCHOOLS})?", re.I),
    # "evocation, 3rd level"  /  "evocation 3rd-level"
    re.compile(rf"^(?P<school>{_SCHOOLS})[\s,]+(?P<lvl>[0-9])(?:st|nd|rd|th)[\s\-]level", re.I),
    # "Evocation Cantrip"  /  "Cantrip - Evocation"  /  "Cantrip"
    # "Evocation Cantrip"  /  "Cantrip - Evocation"  /  "Cantrip"  /
    # "Divination cantrip (Artificer, Wizard)"  - a trailing (class list) or note
    # is allowed, but the line must still END there so a description sentence
    # like "Cantrip Upgrade. ..." is not mistaken for a header.
    re.compile(
        rf"^(?:(?P<school>{_SCHOOLS})[\s,]+)?cantrip"
        rf"(?:[\s\-–—:,]+(?P<school2>{_SCHOOLS}))?"
        rf"(?:\s*\([^)]*\))?\s*$",
        re.I,
    ),
    # "Evocation" on its own line, immediately under a name (weak; last resort)
    re.compile(rf"^(?P<school>{_SCHOOLS})$", re.I),
]


def _match_header(line: str) -> Optional[Tuple[Optional[int], Optional[str], str]]:
    """Return (level, school, strength) if `line` looks like a header."""
    s = strip_markdown(line).strip().strip(".")
    for i, pat in enumerate(_HEADER_PATTERNS):
        m = pat.match(s)
        if not m:
            continue
        gd = m.groupdict()
        lvl = int(gd["lvl"]) if gd.get("lvl") else 0
        school = gd.get("school") or gd.get("school2")
        school = school.lower() if school else None
        strength = "weak" if pat is _HEADER_PATTERNS[-1] else "strong"
        return lvl, school, strength
    return None


# --------------------------------------------------------------------------- #
# Batch splitting
# --------------------------------------------------------------------------- #

def split_blocks(text: str) -> List[str]:
    """
    Cut a pasted batch into one string per spell.

    Strategy: find every strong header line; the spell's name is the nearest
    non-empty line above it, and the block runs from that name line up to the
    line before the next spell's name. Falls back to blank-line-separated
    chunks, then to the whole input, when no headers are found.
    """
    lines = clean_lines(text)
    header_idx = [i for i, ln in enumerate(lines)
                  if (h := _match_header(ln)) and h[2] == "strong"]

    if not header_idx:
        # No recognisable headers: split on blank-line gaps of 2+.
        chunks = re.split(r"\n\s*\n\s*\n*", text.strip())
        return [c.strip() for c in chunks if c.strip()] or [text.strip()]

    # Name line = nearest non-empty line above each header.
    starts: List[int] = []
    for hi in header_idx:
        j = hi - 1
        while j >= 0 and not lines[j]:
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


# --------------------------------------------------------------------------- #
# Field-level parsing
# --------------------------------------------------------------------------- #

_LABEL_ALIASES: Dict[str, List[str]] = {
    "casting_time": ["casting time", "cast time", "casting", "time", "ct"],
    "range":        ["range", "rng"],
    "components":   ["components", "component", "comp"],
    "duration":     ["duration", "dur"],
    "classes":      ["classes", "class", "spell list", "spell lists",
                     "class list", "available for", "available to", "spellcasters"],
    "source":       ["source", "source book", "sourcebook", "book"],
    "school":       ["school"],
    "level":        ["level", "lvl", "spell level"],
}

_CT_UNIT = r"(?:action|bonus action|reaction|minute|minutes|hour|hours|round|rounds|day|days)"
# leading "N unit" (short line) ...
_CASTING_TIME_NUM_RE = re.compile(rf"^\s*\d+\s+{_CT_UNIT}\b", re.I)
# ... or a bare reaction / bonus-action line, which may carry a trigger clause
_CASTING_TIME_WORD_RE = re.compile(r"^\s*(?:1\s+)?(?:reaction|bonus action)\b", re.I)
_CASTING_TIME_ANY_RE = re.compile(rf"\b\d+\s+{_CT_UNIT}\b", re.I)

_RANGE_RE = re.compile(
    r"\b(self|touch|sight|special|unlimited|"
    r"\d[\d,]*\s*(?:-|\s)?\s*(?:feet|foot|ft|mile|miles))\b",
    re.I,
)
_RANGE_SHAPE_RE = re.compile(r"\(([^)]*\b(?:cone|cube|sphere|line|radius|emanation)\b[^)]*)\)", re.I)

_DURATION_RE = re.compile(
    r"(instantaneous|until dispelled(?: or triggered)?|permanent|special|"
    r"(?:concentration[,\s]+)?up to \d+\s*\w+|"
    r"\d+\s*(?:round|minute|hour|day)s?)",
    re.I,
)

_COMPONENTS_RE = re.compile(
    r"\b(V(?:erbal)?)\b|\b(S(?:omatic)?)\b|\b(M(?:aterial)?)\b", re.I,
)
_MATERIAL_PAREN_RE = re.compile(r"\(([^)]+)\)")


_COMPACT_COMP_RE = re.compile(
    r"\b[VSM](?:erbal|omatic|aterial)?\b"
    r"(?:[,\s]+\b[VSM](?:erbal|omatic|aterial)?\b)*"
    r"(?:[\s,]*\([^)]*\))?",   # material paren may be preceded by ", " e.g. "S, M, (...)"
    re.I,
)


def _scan_meta(text: str, found: Dict[str, str], skip=(), only=None) -> None:
    """Fill still-missing casting_time / range / components / duration from a snippet.

    `skip` names fields already labelled on this physical line. `only`, when set,
    restricts mining to that set of fields - used when scanning the *value* of a
    labelled field, where casting-time / duration phrases would otherwise be
    misread out of each other ("up to 1 minute" -> casting time "1 minute").
    """
    def want(key: str) -> bool:
        return key not in found and key not in skip and (only is None or key in only)

    if want("casting_time"):
        m = _CASTING_TIME_ANY_RE.search(text)
        if m:
            ct = m.group(0)
            # keep a trailing ritual marker: "1 Action or Ritual", "1 action (Ritual)"
            if re.search(r"\britual\b", text[m.start():m.start() + 40], re.I):
                ct += " (ritual)"
            found["casting_time"] = ct
    if want("range"):
        m = _RANGE_RE.search(text)
        if m:
            found["range"] = m.group(0)
    if want("duration"):
        m = _DURATION_RE.search(text)
        if m:
            found["duration"] = m.group(0)
    if want("components"):
        m = _COMPACT_COMP_RE.search(text)
        if m and ("," in m.group(0) or "(" in m.group(0) or len(m.group(0).strip()) <= 2):
            found["components"] = m.group(0)


def _parse_level_school(obj: ParsedObject, header_line: str) -> None:
    h = _match_header(header_line)
    if not h:
        obj.set("level", 0, Confidence.LOW, "no header line found; assumed cantrip")
        return
    lvl, school, _ = h
    obj.set("level", lvl, Confidence.HIGH)
    if school:
        obj.set("school", school, Confidence.HIGH)


def _parse_casting_time(value: str) -> Tuple[str, bool, Confidence]:
    v = strip_markdown(value).strip().strip(".")
    ritual = bool(re.search(r"\britual\b", v, re.I))
    v = re.sub(r"\s*(?:,|;|\bor\b)?\s*\(?\britual\b\)?", "", v, flags=re.I).strip(" ,;")
    return v, ritual, Confidence.HIGH


def _range_to_value(text: str) -> Tuple[Optional[int], Confidence, str]:
    """Map a range phrase to Spellbook's integer encoding."""
    t = text.lower().strip().strip(".")
    if t.startswith("self"):
        return 0, Confidence.HIGH, ""
    if t.startswith("touch"):
        return 3, Confidence.HIGH, ""
    if t.startswith("sight"):
        return 1, Confidence.HIGH, ""
    if t.startswith(("special", "unlimited")):
        return 2, Confidence.HIGH, ""
    m = re.match(r"(\d[\d,]*)\s*(?:-|\s)?\s*(feet|foot|ft|mile|miles)", t)
    if m:
        n = int(m.group(1).replace(",", ""))
        if m.group(2).startswith("mile"):
            return -n, Confidence.HIGH, ""
        if n > 3 and n % 5:
            n = round(n / 5) * 5
        return n, Confidence.HIGH, ""
    return None, Confidence.MISSING, ""


def _parse_components(value: str) -> Tuple[str, Confidence]:
    v = strip_markdown(value)
    has_v = bool(re.search(r"\bV(?:erbal)?\b", v, re.I))
    has_s = bool(re.search(r"\bS(?:omatic)?\b", v, re.I))
    has_m = bool(re.search(r"\bM(?:aterial)?\b", v, re.I))
    # compact form "VSM"
    if not (has_v or has_s or has_m):
        compact = re.sub(r"[^vsm]", "", v.lower())
        has_v, has_s, has_m = "v" in compact, "s" in compact, "m" in compact
    parts = []
    if has_v:
        parts.append("V")
    if has_s:
        parts.append("S")
    if has_m:
        mat = _MATERIAL_PAREN_RE.search(v)
        parts.append(f"M ({mat.group(1).strip()})" if mat else "M")
    if not parts:
        return "", Confidence.MISSING
    return ", ".join(parts), Confidence.HIGH


def _parse_duration(value: str) -> Tuple[str, bool, Confidence]:
    # tolerate the whole value being wrapped, e.g. "(concentration up to 10 minutes)"
    v = strip_markdown(value).strip().strip(".").strip()
    if v.startswith("(") and v.endswith(")"):
        v = v[1:-1].strip()
    conc = bool(re.search(r"\bconcentrat", v, re.I))
    m = re.search(r"up to\s+(.+)", v, re.I)
    if m:
        dur = m.group(1).strip()
    else:
        dur = re.sub(r"^\s*concentration[,\s]*", "", v, flags=re.I).strip()
    dur = dur.strip(" ()")          # drop any leftover bracket from "up to 10 minutes)"
    dur = dur[:1].upper() + dur[1:] if dur else dur
    return dur, conc, Confidence.HIGH


def _looks_like_class_line(line: str) -> Optional[List[str]]:
    """Detect an unlabelled bare class list, e.g. 'Sorcerer, Wizard'."""
    s = strip_markdown(line).strip().strip(".")
    if len(s) > 80 or ":" in s:
        return None
    tokens = [t.strip() for t in re.split(r",|/|&|\band\b", s) if t.strip()]
    if not tokens:
        return None
    matched = [t for t in tokens if t.lower() in _KNOWN_CLASSES]
    if matched and len(matched) >= max(1, len(tokens) - 1):
        return matched
    return None


def _parse_classes(value: str, labelled: bool) -> Tuple[List[str], Confidence]:
    s = strip_markdown(value).strip().strip(".")
    tokens = [t.strip() for t in re.split(r",|/|&|\band\b", s) if t.strip()]
    if not tokens:
        return [], Confidence.MISSING
    known = [t.title() for t in tokens if t.lower() in _KNOWN_CLASSES]
    unknown = [t for t in tokens if t.lower() not in _KNOWN_CLASSES]
    if labelled:
        # trust the label, but flag if some names are unrecognised
        out = known + [u.title() for u in unknown]
        conf = Confidence.HIGH if not unknown else Confidence.MEDIUM
        return out, conf
    if known and len(known) >= max(1, len(tokens) - 1):
        return known, Confidence.MEDIUM
    return [], Confidence.MISSING


# --------------------------------------------------------------------------- #
# Block parser
# --------------------------------------------------------------------------- #

def parse_spell_block(text: str) -> ParsedObject:
    obj = ParsedObject(kind="spell", raw_text=text)
    lines = [ln for ln in clean_lines(text)]
    # drop leading blanks
    while lines and not lines[0]:
        lines.pop(0)
    if not lines:
        return obj

    # ---- locate header + name -------------------------------------------- #
    header_line_idx = None
    for i, ln in enumerate(lines[:6]):
        if _match_header(ln):
            header_line_idx = i
            break

    if header_line_idx is None:
        obj.set("name", strip_markdown(lines[0]) or "", Confidence.LOW,
                "no level/school line found near the top")
        body_start = 1
    else:
        # name = nearest non-empty line above the header (or the header's own
        # prefix if 'Name - Level 3 Evocation' is on one line)
        name = ""
        j = header_line_idx - 1
        while j >= 0 and not lines[j]:
            j -= 1
        if j >= 0:
            name = strip_markdown(lines[j])
        if not name:
            # maybe "Fireball - Level 3 Evocation"
            pre = re.split(r"[-–—]\s*(?=level\b|cantrip\b|\d)", lines[header_line_idx], 1, re.I)
            if len(pre) == 2 and _match_header(pre[1]):
                name = strip_markdown(pre[0])
        obj.set("name", name.rstrip(" .*"),
                Confidence.HIGH if name else Confidence.MISSING)
        _parse_level_school(obj, lines[header_line_idx])
        body_start = header_line_idx + 1

    # ---- classify every remaining line --------------------------------- #
    found: Dict[str, str] = {}          # canonical -> raw value
    labelled_keys: set = set()
    desc_lines: List[str] = []
    unconsumed: List[str] = []
    header_ritual = False

    # header line extras: "(ritual)" marker and a parenthetical class list
    # e.g. "Level 1 Abjuration (Bard, Cleric, Druid)"  /  "2nd-level ... (ritual)"
    if header_line_idx is not None:
        hdr = lines[header_line_idx]
        if re.search(r"\britual\b", hdr, re.I):
            header_ritual = True
        for par in re.findall(r"\(([^)]+)\)", hdr):
            if re.fullmatch(r"\s*ritual\s*", par, re.I):
                continue
            if _looks_like_class_line(par) is not None:
                found["classes"] = par
                labelled_keys.add("classes")

    for ln in lines[body_start:]:
        if not ln:
            desc_lines.append("")
            continue

        # (a) one or more "Label: value" pairs on this line
        pairs = split_labelled_fragments(ln, _LABEL_ALIASES)
        if pairs:
            labels_here = {k for k, _ in pairs}
            for key, val in pairs:
                found.setdefault(key, val)
                labelled_keys.add(key)
                # a label's value can over-capture a trailing unlabelled field,
                # e.g. Range value "120 feet  V, S" on a compact line
                _scan_meta(val, found, skip=labels_here, only={"components", "range"})
            # text before the first label (a bare "1 action" prefix, say)
            from text_import.base import first_label_start
            fps = first_label_start(ln, _LABEL_ALIASES)
            if fps:
                _scan_meta(ln[:fps], found, skip=labels_here)
            continue

        # (a') a single label with no colon: "range 30 ft", "Duration Instantaneous"
        m = re.match(
            r"^(range|rng|duration|dur|components?|comp|classes?|class list|"
            r"spell lists?|casting time|cast time|source|source ?book|school)"
            r"\b[\s:.\-–]+(.+)$",
            ln, re.I,
        )
        if m:
            from text_import.base import match_label
            key = match_label(m.group(1), _LABEL_ALIASES)
            if key and key not in found:
                found[key] = m.group(2).strip()
                labelled_keys.add(key)
                continue

        # (b) unlabelled but recognisable meta line
        low = ln.lower()
        consumed = False

        if "casting_time" not in found and (
                _CASTING_TIME_WORD_RE.match(ln)
                or (_CASTING_TIME_NUM_RE.match(ln) and len(ln) < 60)):
            found["casting_time"] = ln
            consumed = True
        elif "duration" not in found and _DURATION_RE.fullmatch(ln.strip(".")):
            found["duration"] = ln
            consumed = True
        elif "range" not in found and _RANGE_RE.fullmatch(ln.strip(".")):
            found["range"] = ln
            consumed = True
        elif "components" not in found and re.fullmatch(
                r"(?:V(?:erbal)?|S(?:omatic)?|M(?:aterial)?)(?:[,\s]+(?:V(?:erbal)?|"
                r"S(?:omatic)?|M(?:aterial)?))*(?:[\s,]*\([^)]*\))?", ln, re.I):
            found["components"] = ln
            consumed = True
        elif "classes" not in found and _looks_like_class_line(ln) is not None:
            found["classes"] = ln
            consumed = True
        elif re.fullmatch(r"(?:ritual|\(ritual\))", low):
            found.setdefault("casting_time", "")
            found["casting_time"] = (found["casting_time"] + " ritual").strip()
            consumed = True
        elif "," in ln and len(ln) < 90 and not re.search(r"[.!?]\s", ln) and (
                _CASTING_TIME_ANY_RE.search(ln) or _RANGE_RE.search(ln)
                or _DURATION_RE.search(ln)):
            # (c) compact unlabelled mash: "1 action, V, S, 150 feet, Instantaneous"
            before = dict(found)
            _scan_meta(ln, found)
            consumed = found != before

        if not consumed:
            desc_lines.append(ln)

    # ---- fold parsed values into the object ---------------------------- #
    if "casting_time" in found:
        ct, ritual, conf = _parse_casting_time(found["casting_time"])
        ritual = ritual or header_ritual
        obj.set("casting_time", ct, conf if ct else Confidence.LOW)
        obj.set("ritual", ritual, Confidence.HIGH if ritual else Confidence.MEDIUM)
    else:
        obj.set("casting_time", "1 action", Confidence.MISSING, "not found; default shown")
        obj.set("ritual", header_ritual, Confidence.HIGH if header_ritual else Confidence.MEDIUM)

    if "range" in found:
        val, conf, _ = _range_to_value(found["range"])
        shape = _RANGE_SHAPE_RE.search(found["range"])
        note = f"area: {shape.group(1)}" if shape else ""
        obj.set("range", val if val is not None else 0,
                conf if val is not None else Confidence.LOW, note)
    else:
        obj.set("range", 0, Confidence.MISSING, "not found")

    if "components" in found:
        comp, conf = _parse_components(found["components"])
        obj.set("components", comp, conf)
    else:
        obj.set("components", "", Confidence.MISSING, "not found")

    if "duration" in found:
        dur, conc, conf = _parse_duration(found["duration"])
        obj.set("duration", dur, conf)
        obj.set("concentration", conc, Confidence.HIGH)
    else:
        obj.set("duration", "Instantaneous", Confidence.MISSING, "not found; default shown")
        obj.set("concentration", False, Confidence.MEDIUM)

    if "classes" in found:
        cls, conf = _parse_classes(found["classes"], "classes" in labelled_keys)
        obj.set("classes", cls, conf)
    else:
        obj.set("classes", [], Confidence.MISSING, "not found")

    if "source" in found:
        obj.set("source", strip_markdown(found["source"]), Confidence.HIGH)
    else:
        obj.set("source", "", Confidence.MISSING)

    # description: trim, collapse blank runs, join paragraphs with the app's "\"
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
    description = "\\".join(paras).strip()
    obj.set("description", description,
            Confidence.HIGH if len(description) > 20 else Confidence.LOW)

    # tags: school + description heuristics
    school = obj.get("school")
    tags = guess_description_tags(description, school)
    obj.set("tags", tags, Confidence.MEDIUM if tags else Confidence.MISSING)

    obj.unconsumed_lines = unconsumed
    return obj


def parse_spell_text(text: str) -> List[ParsedObject]:
    """Split a batch and parse every block."""
    return [parse_spell_block(b) for b in split_blocks(text)]


# --------------------------------------------------------------------------- #
# Convenience: build a real Spell (skips cleanly if run outside the app)
# --------------------------------------------------------------------------- #

def to_spell(obj: ParsedObject):
    """Turn a ParsedObject into a Spell dataclass instance (best effort)."""
    if CharacterClass is None:
        raise RuntimeError("spell module not importable in this context")
    from spell import Spell

    class_names = obj.get("classes") or []
    classes = [CharacterClass.from_string(c) for c in class_names]
    return Spell(
        name=obj.get("name") or "",
        level=int(obj.get("level") or 0),
        casting_time=obj.get("casting_time") or "1 action",
        ritual=bool(obj.get("ritual")),
        range_value=int(obj.get("range") or 0),
        components=obj.get("components") or "",
        duration=obj.get("duration") or "Instantaneous",
        concentration=bool(obj.get("concentration")),
        classes=classes,
        class_names=class_names,
        description=obj.get("description") or "",
        source=obj.get("source") or "",
        tags=list(obj.get("tags") or []),
    )
