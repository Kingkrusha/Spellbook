"""
Auto-detect (rule-based) spell import UI for the D&D Spellbook.

``AddSpellSourceDialog`` and ``SpellTextImportDialog`` are the shared dialogs of ``ui/text_import_dialogs.py``
with this collection's wording and parser.
"""

from ui.text_import_dialogs import AddSourceDialog, TextImportDialog, TextImportSpec

_PLACEHOLDER = """Paste one or more spells here, for example:

Fire Bolt
Evocation Cantrip
Casting Time: 1 Action
Range: 120 feet
Components: V, S
Duration: Instantaneous
Classes: Sorcerer, Wizard
You hurl a mote of fire at a creature or an object within range...
"""

SPEC = TextImportSpec(
    add_title="Add Spell",
    add_question="How would you like to add this spell?",
    add_blurb=("You can fill in every field yourself, or paste a block of spell text and let "
        "Spellbook fill in what it can for you to review."),
    import_title="Auto-Detect Spells From Text",
    paste_heading="Paste spell text below",
    paste_help=("Multiple spells can be pasted at once - no numbering or separators needed. "
        "Spellbook looks for a name followed by a line like \"Level 3 Evocation\" or "
        "\"Evocation Cantrip\" to tell them apart."),
    disclaimer=("Auto-detection is rule-based and may not be fully accurate, especially for "
        "irregularly formatted text. Every detected spell opens in the editor for you to "
        "review and correct before it is saved."),
    placeholder=_PLACEHOLDER,
    detected_unit="spell block",
    empty_warning="Please paste some spell text first.",
    retry_hint="Try pasting a single spell, or add it manually instead.",
    nothing_found=("Could not find a spell in that text.\n\nMake sure each spell has a name line "
        "followed by a line such as \"Level 2 Evocation\" or \"Evocation Cantrip\"."),
    parser_module="text_import.spell_parser",
    parse_function="parse_spell_text",
)


class AddSpellSourceDialog(AddSourceDialog):
    """Ask how the user wants to create a new spell."""

    SPEC = SPEC


class SpellTextImportDialog(TextImportDialog):
    """Collect a block of text and parse it into one or more spell drafts."""

    SPEC = SPEC
