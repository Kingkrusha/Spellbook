"""
Auto-detect (rule-based) magic item import UI for the D&D Spellbook.

``AddMagicItemSourceDialog`` and ``MagicItemTextImportDialog`` are the shared dialogs of ``ui/text_import_dialogs.py``
with this collection's wording and parser.
"""

from ui.text_import_dialogs import AddSourceDialog, TextImportDialog, TextImportSpec

_PLACEHOLDER = """Paste one or more magic items here, for example:

Bag of Holding
Wondrous item, uncommon
This bag has an interior space considerably larger than its outside
dimensions...

Ring of Protection
Ring, rare (requires attunement)
You gain a +1 bonus to AC and saving throws while wearing this ring.
"""

SPEC = TextImportSpec(
    add_title="Add Magic Item",
    add_question="How would you like to add this magic item?",
    add_blurb=("You can fill in every field yourself, or paste a block of magic item text and let "
        "Spellbook fill in what it can for you to review."),
    import_title="Auto-Detect Magic Items From Text",
    paste_heading="Paste magic item text below",
    paste_help=("Multiple items can be pasted at once - no numbering or separators needed. Spellbook "
        "looks for the standard \"<Type>, <rarity>\" header line (e.g. \"Ring, rare (requires "
        "attunement)\") to tell items apart, and falls back to labelled "
        "\"Rarity:\"/\"Attunement:\" lines."),
    disclaimer=("Auto-detection is rule-based and may not be fully accurate, especially for "
        "irregularly formatted text. Cost and weight are rarely stated in magic item text "
        "and will usually need filling in by hand. Every detected item opens in the editor "
        "for you to review and correct before it is saved."),
    placeholder=_PLACEHOLDER,
    detected_unit="item",
    empty_warning="Please paste some magic item text first.",
    retry_hint="Try pasting a single item, or add it manually instead.",
    nothing_found=("Could not find a magic item in that text.\n\nMake sure each item has a name line "
        "followed by a line like \"Wondrous item, rare (requires attunement)\"."),
    parser_module="text_import.magic_item_parser",
    parse_function="parse_magic_item_text",
)


class AddMagicItemSourceDialog(AddSourceDialog):
    """Ask how the user wants to create a new magic item."""

    SPEC = SPEC


class MagicItemTextImportDialog(TextImportDialog):
    """Collect a block of text and parse it into one or more magic item drafts."""

    SPEC = SPEC
