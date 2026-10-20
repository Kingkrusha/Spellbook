"""
Auto-detect (rule-based) feat import UI for the D&D Spellbook.

``AddFeatSourceDialog`` and ``FeatTextImportDialog`` are the shared dialogs of ``ui/text_import_dialogs.py``
with this collection's wording and parser.
"""

from ui.text_import_dialogs import AddSourceDialog, TextImportDialog, TextImportSpec

_PLACEHOLDER = """Paste one or more feats here, for example:

Alert
Origin Feat
Prerequisite: None
You gain the following benefits:
Initiative Proficiency. You can add your proficiency bonus to your
initiative rolls...
"""

SPEC = TextImportSpec(
    add_title="Add Feat",
    add_question="How would you like to add this feat?",
    add_blurb=("You can fill in every field yourself, or paste a block of feat text and let "
        "Spellbook fill in what it can for you to review."),
    import_title="Auto-Detect Feats From Text",
    paste_heading="Paste feat text below",
    paste_help=("Multiple feats can be pasted at once - no numbering or separators needed. Spellbook "
        "looks for a name followed by a category line (\"Origin Feat\", \"Epic Boon\", ...) or a "
        "\"Prerequisite:\" line to tell them apart."),
    disclaimer=("Auto-detection is rule-based and may not be fully accurate, especially for "
        "irregularly formatted text - feats vary a lot more than spells do, and spellcasting "
        "fields in particular are a best guess. Every detected feat opens in the editor for "
        "you to review and correct before it is saved."),
    placeholder=_PLACEHOLDER,
    detected_unit="feat block",
    empty_warning="Please paste some feat text first.",
    retry_hint="Try pasting a single feat, or add it manually instead.",
    nothing_found=("Could not find a feat in that text.\n\nMake sure each feat has a name line, ideally "
        "followed by a category line (e.g. \"Origin Feat\") or a \"Prerequisite:\" line."),
    parser_module="text_import.feat_parser",
    parse_function="parse_feat_text",
)


class AddFeatSourceDialog(AddSourceDialog):
    """Ask how the user wants to create a new feat."""

    SPEC = SPEC


class FeatTextImportDialog(TextImportDialog):
    """Collect a block of text and parse it into one or more feat drafts."""

    SPEC = SPEC
