"""
Rule-based text import for Spellbook custom content.

Parses free-form stat-block text (spells, lineages, feats, equipment, magic
items) into structured field values with a confidence rating per field, so a
review UI can pre-fill an editor and highlight anything that needs a human
check. No LLM / network use.
"""

from text_import.base import Confidence, FieldResult, ParsedObject
from text_import.spell_parser import parse_spell_text, split_blocks, to_spell
from text_import.feat_parser import parse_feat_text, to_feat
from text_import.lineage_parser import parse_lineage_text, to_lineage
from text_import.equipment_parser import parse_equipment_text, to_equipment
from text_import.magic_item_parser import parse_magic_item_text, to_magic_item

__all__ = [
    "Confidence",
    "FieldResult",
    "ParsedObject",
    "parse_spell_text",
    "split_blocks",
    "to_spell",
    "parse_feat_text",
    "to_feat",
    "parse_lineage_text",
    "to_lineage",
    "parse_equipment_text",
    "to_equipment",
    "parse_magic_item_text",
    "to_magic_item",
]
