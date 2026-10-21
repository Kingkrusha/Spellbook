"""
Auto-detect (rule-based) lineage import UI for the D&D Spellbook.

``AddLineageSourceDialog`` and ``LineageTextImportDialog`` are the shared dialogs of ``ui/text_import_dialogs.py``
with this collection's wording and parser.
"""

from ui.text_import_dialogs import AddSourceDialog, TextImportDialog, TextImportSpec

_PLACEHOLDER = """Paste one or more lineages here, for example:

Changeling
Creature Type: Fey
Size: Medium or Small
Speed: 30 feet
With ever-changing appearances, changelings reside in many societies
undetected...

Changeling Instincts. Thanks to your connection to the fey realm, you gain
proficiency in two of the following skills of your choice: Deception,
Insight, Intimidation, Performance, or Persuasion.

Shape-Shifter. As an action, you can shape-shift to change your appearance...
"""

SPEC = TextImportSpec(
    add_title="Add Lineage",
    add_question="How would you like to add this lineage?",
    add_blurb=("You can fill in every field yourself, or paste a block of lineage text and let "
        "Spellbook fill in what it can for you to review."),
    import_title="Auto-Detect Lineages From Text",
    paste_heading="Paste lineage text below",
    paste_help=("Multiple lineages can be pasted at once - no numbering or separators needed. "
        "Spellbook looks for a name followed by creature type / size / speed to tell them "
        "apart, and splits traits from run-in headings like \"Darkvision. You have...\"."),
    disclaimer=("Auto-detection is rule-based and may not be fully accurate, especially for "
        "irregularly formatted text. Splitting traits from the base description is a best "
        "guess. Every detected lineage opens in the editor for you to review and correct "
        "before it is saved."),
    placeholder=_PLACEHOLDER,
    detected_unit="lineage block",
    empty_warning="Please paste some lineage text first.",
    retry_hint="Try pasting a single lineage, or add it manually instead.",
    nothing_found=("Could not find a lineage in that text.\n\nMake sure each lineage has a name line, "
        "ideally followed by its creature type, size, and speed."),
    parser_module="text_import.lineage_parser",
    parse_function="parse_lineage_text",
)


class AddLineageSourceDialog(AddSourceDialog):
    """Ask how the user wants to create a new lineage."""

    SPEC = SPEC


class LineageTextImportDialog(TextImportDialog):
    """Collect a block of text and parse it into one or more lineage drafts."""

    SPEC = SPEC
