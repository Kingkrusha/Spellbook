"""
The "add from pasted text" flow every collection page runs the same way.

The page asks for a block of text (``ui/text_import_dialogs.py``), the rule-based parser splits it into drafts, and
each draft opens in the collection's own editor, pre-filled and with the uncertain fields outlined, for the user to
review. Saving adds it; cancelling skips it, after offering to stop when more are waiting.

The pages differ only in the dialog, parser, editor and what "add" does, which they pass in; they keep what happens
afterwards (reloading the list, selecting the last one added).
"""

from tkinter import messagebox
from typing import Any, Callable, List, Optional


def import_from_pasted_text(owner, *, import_cls, load_converter: Callable[[], Callable], noun: str,
                            noun_phrase: str, make_editor: Callable[[Any, List[str], str], Any],
                            add: Callable[[Any], bool], prepare: Optional[Callable[[Any], None]] = None,
                            dialog_parent=None) -> List[str]:
    """Run the flow and return the names that were added.

    ``noun`` ("feat") and ``noun_phrase`` ("a feat") word the messages. ``load_converter()`` imports and returns
    the parser's draft builder (it may raise); ``make_editor(draft, review_fields, progress)`` opens the editor on a
    draft; ``add(result)`` stores what was saved and says whether it was new; ``prepare(result)`` touches a saved
    result before that. ``dialog_parent`` is the window the dialogs belong to (default: the page's toplevel)."""
    parent = dialog_parent if dialog_parent is not None else owner.winfo_toplevel()

    import_dialog = import_cls(parent)
    owner.wait_window(import_dialog)
    parsed_list = import_dialog.result
    if not parsed_list:
        return []

    try:
        to_draft = load_converter()
    except Exception as exc:
        messagebox.showerror("Auto-Detect Unavailable",
                             f"Could not load the text importer:\n{exc}")
        return []

    added: List[str] = []
    total = len(parsed_list)
    for idx, parsed in enumerate(parsed_list, 1):
        try:
            draft = to_draft(parsed)
        except Exception as exc:
            messagebox.showerror("Parse Error",
                                 f"Could not build {noun} {idx} of {total}:\n{exc}")
            continue

        review = sorted(set(parsed.needs_review()) | set(parsed.uncertain_fields()))
        progress = f"{idx} of {total}" if total > 1 else ""

        editor = make_editor(draft, review, progress)
        owner.wait_window(editor)

        if editor.result:
            if prepare is not None:
                prepare(editor.result)
            if add(editor.result):
                added.append(editor.result.name)
            else:
                messagebox.showerror(
                    "Error",
                    f"{noun_phrase.capitalize()} named '{editor.result.name}' already exists. "
                    "It was not added.")
        elif idx < total:
            if not messagebox.askyesno(
                    "Continue?",
                    f"Skip this {noun} and continue reviewing the remaining "
                    f"{total - idx} {noun}(s)?"):
                break
    return added


def announce_added(added: List[str], plural: str):
    """After several were added at once: say which (a single one needs no announcement)."""
    if len(added) > 1:
        messagebox.showinfo(f"{plural.title()} Added", f"Added {len(added)} {plural}:\n" + "\n".join(added))
