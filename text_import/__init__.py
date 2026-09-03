"""
Rule-based text import for Spellbook custom content.

Parses free-form stat-block text (spells, lineages, feats) into structured
field values with a confidence rating per field, so a review UI can pre-fill an
editor and highlight anything that needs a human check. No LLM / network use.
"""

from text_import.base import Confidence, FieldResult, ParsedObject
from text_import.spell_parser import parse_spell_text, split_blocks, to_spell

__all__ = [
    "Confidence",
    "FieldResult",
    "ParsedObject",
    "parse_spell_text",
    "split_blocks",
    "to_spell",
]
