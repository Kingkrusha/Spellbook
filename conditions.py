"""Conditions for the initiative tracker.

The 2024 rules' conditions, plus free-text ones (``Concentrating``, ``Hexed``, a homebrew
status...). The character sheet has no condition model; in the tracker a condition is just
``{"name": str, "level": int (Exhaustion only), "rounds": int (optional countdown)}``.
"""

from __future__ import annotations

from typing import List, Optional

CONDITIONS: List[str] = [
    "Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened", "Grappled", "Incapacitated",
    "Invisible", "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious",
]

# Not conditions in the rules but tracked at the table all the time
COMMON_EFFECTS: List[str] = ["Concentrating", "Dodging", "Hasted", "Blessed", "Hexed", "Marked", "Raging"]

EXHAUSTION = "Exhaustion"
MAX_EXHAUSTION = 6
MAX_NAME = 40
MAX_ROUNDS = 1000

# Short badge text for narrow windows
ABBREVIATIONS = {
    "Blinded": "Blind", "Charmed": "Charm", "Deafened": "Deaf", "Exhaustion": "Exh",
    "Frightened": "Fright", "Grappled": "Grap", "Incapacitated": "Incap", "Invisible": "Invis",
    "Paralyzed": "Paral", "Petrified": "Petri", "Poisoned": "Pois", "Prone": "Prone",
    "Restrained": "Restr", "Stunned": "Stun", "Unconscious": "Uncon",
}


def canonical_name(name: str) -> str:
    """The standard spelling for a known condition (case-insensitive), else the cleaned text."""
    cleaned = " ".join((name or "").split())[:MAX_NAME]
    lowered = cleaned.lower()
    for known in CONDITIONS + COMMON_EFFECTS:
        if known.lower() == lowered:
            return known
    return cleaned


def make_condition(name: str, level: Optional[int] = None, rounds: Optional[int] = None) -> dict:
    """A validated condition dict. Raises ValueError for an empty name."""
    name = canonical_name(name)
    if not name:
        raise ValueError("A condition needs a name.")
    cond: dict = {"name": name}
    if name == EXHAUSTION:
        cond["level"] = max(1, min(MAX_EXHAUSTION, int(level or 1)))
    if rounds is not None:
        cond["rounds"] = max(1, min(MAX_ROUNDS, int(rounds)))
    return cond


def label(cond: dict) -> str:
    """Display text, e.g. ``Exhaustion 2`` or ``Poisoned (3 rds)``."""
    text = cond.get("name", "")
    if cond.get("level"):
        text += f" {cond['level']}"
    if cond.get("rounds"):
        text += f" ({cond['rounds']} rd{'s' if cond['rounds'] != 1 else ''})"
    return text
