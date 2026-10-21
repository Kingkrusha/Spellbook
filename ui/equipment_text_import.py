"""
Auto-detect (rule-based) equipment import UI for the D&D Spellbook.

``AddEquipmentSourceDialog`` and ``EquipmentTextImportDialog`` are the shared dialogs of ``ui/text_import_dialogs.py``
with this collection's wording and parser.
"""

from ui.text_import_dialogs import AddSourceDialog, TextImportDialog, TextImportSpec

_PLACEHOLDER = """Paste one or more items here, for example:

Longsword
Type: Melee Weapon
Cost: 15 gp
Weight: 3 lb
Damage: 1d8 slashing (1d10 versatile)
A versatile blade favored by knights and mercenaries.
"""

SPEC = TextImportSpec(
    add_title="Add Equipment",
    add_question="How would you like to add this item?",
    add_blurb=("You can fill in every field yourself, or paste a block of equipment text and let "
        "Spellbook fill in what it can for you to review."),
    import_title="Auto-Detect Equipment From Text",
    paste_heading="Paste equipment text below",
    paste_help=("Multiple items can be pasted at once - no numbering or separators needed. Spellbook "
        "looks for a cost (\"15 gp\"), a weight (\"3 lb\"), or a labelled Type/Cost/Weight line "
        "to tell items apart."),
    disclaimer=("Auto-detection is rule-based and may not be fully accurate, especially for "
        "irregularly formatted text - equipment varies more in layout than spells do. Every "
        "detected item opens in the editor for you to review and correct before it is saved."),
    placeholder=_PLACEHOLDER,
    detected_unit="item",
    empty_warning="Please paste some equipment text first.",
    retry_hint="Try pasting a single item, or add it manually instead.",
    nothing_found=("Could not find an item in that text.\n\nMake sure each item has a name line, "
        "ideally followed by a cost or weight."),
    parser_module="text_import.equipment_parser",
    parse_function="parse_equipment_text",
)


class AddEquipmentSourceDialog(AddSourceDialog):
    """Ask how the user wants to create a new equipment item."""

    SPEC = SPEC


class EquipmentTextImportDialog(TextImportDialog):
    """Collect a block of text and parse it into one or more equipment drafts."""

    SPEC = SPEC
