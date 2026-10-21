"""
Bulk actions on the entries ticked in a collection page's list ("Select" mode, see ``ui/virtual_list.py``):
add them all to a character, edit their tags, edit their classes (spells), set their source, and export them as a
printable PDF (every page offers that one).

:class:`BulkActionsMixin` is the flow, written once; a page names which actions it offers and says how to read,
store and hand out its entries::

    class FeatsView(BulkActionsMixin, CollectionPageMixin, ctk.CTkFrame):
        BULK_ACTIONS = ("add", "source")
        BULK_NOUN, BULK_PLURAL = "feat", "feats"
        def _bulk_fetch(self, name): ...         # the entry as it is stored now
        def _bulk_store(self, entries): ...      # save the edited entries; how many were saved
        def _bulk_reload(self): ...              # show the saved changes
        def _bulk_give(self, character, entries): ...   # "add to character"; returns the message to show

The dialogs only collect the choice; nothing is changed until they are accepted. Entries are re-read from the
manager before they are edited, so an edit never writes back a stale copy.
"""

import copy
from tkinter import filedialog, messagebox
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.collection_page import CharacterPickMixin
from ui.tag_editor import TagEditor
from ui.window_utils import add_cancel_save, center_on_parent


def count_text(n: int, noun: str, plural: str) -> str:
    return f"{n} {noun if n == 1 else plural}"


# ---------------------------------------------------------------------------------------------- dialogs

class _BulkDialog(ctk.CTkToplevel):
    """A modal dialog over a page, with a heading and a body to fill in; ``result`` stays None unless accepted."""

    CONFIRM = "Apply"

    def __init__(self, parent, title: str, heading: str, size: str):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.result = None
        self.title(title)
        self.geometry(size)
        self.minsize(380, 300)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(self.container, text=heading, font=ui_font("subheading", bold=True),
                     wraplength=420, justify="left").pack(anchor="w", pady=(0, 12))
        self._build(self.container)

        buttons = ctk.CTkFrame(self.container, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", pady=(12, 0))
        add_cancel_save(buttons, self.theme, self.destroy, self._accept, confirm_text=self.CONFIRM, outlined=True)
        center_on_parent(self, parent, clamp=True)

    def _build(self, container):
        raise NotImplementedError

    def _accept(self):
        raise NotImplementedError

    def _warn(self, text: str):
        messagebox.showwarning("Bulk edit", text, parent=self)


class ExportPdfDialog(_BulkDialog):
    """How the PDF should look. ``result`` is a ``pdf_export.ExportOptions``."""

    CONFIRM = "Export…"

    def __init__(self, parent, heading: str, default_title: str):
        self._default_title = default_title
        super().__init__(parent, "Export PDF", heading, "440x380")

    def _build(self, container):
        ctk.CTkLabel(container, text="Title", font=ui_font("body"), anchor="w").pack(fill="x")
        self.title_var = ctk.StringVar(value=self._default_title)
        ctk.CTkEntry(container, textvariable=self.title_var).pack(fill="x", pady=(2, 10))
        self.columns_var = ctk.StringVar(value="Two columns")
        ctk.CTkSegmentedButton(container, values=["Two columns", "One column"],
                               variable=self.columns_var).pack(anchor="w", pady=(0, 8))
        self.size_var = ctk.StringVar(value="Letter")
        ctk.CTkSegmentedButton(container, values=["Letter", "A4"], variable=self.size_var).pack(anchor="w",
                                                                                              pady=(0, 8))
        self.parchment_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(container, text="Parchment background (turn off to save ink)",
                        variable=self.parchment_var).pack(anchor="w", pady=4)
        self.numbers_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(container, text="Page numbers", variable=self.numbers_var).pack(anchor="w", pady=4)

    def _accept(self):
        from pdf_export import ExportOptions
        self.result = ExportOptions(title=self.title_var.get().strip(),
                                    columns=2 if self.columns_var.get().startswith("Two") else 1,
                                    parchment=bool(self.parchment_var.get()), page_size=self.size_var.get(),
                                    page_numbers=bool(self.numbers_var.get()))
        self.destroy()


class BulkTagsDialog(_BulkDialog):
    """Tags to add to, and tags to remove from, every ticked entry. ``result`` is ``(add, remove)``."""

    def __init__(self, parent, heading: str, available_tags: Sequence[str], present_tags: Sequence[str],
                 is_protected: Optional[Callable[[str], bool]] = None):
        self._available, self._present, self._is_protected = list(available_tags), list(present_tags), is_protected
        super().__init__(parent, "Edit Tags", heading, "520x620")

    def _build(self, container):
        self.add_editor = TagEditor(container, lambda: self._available, label="Add these tags",
                                    is_protected=self._is_protected)
        self.add_editor.pack(fill="x", pady=(0, 12))
        self.remove_editor = TagEditor(container, lambda: self._present, label="Remove these tags",
                                       is_protected=self._is_protected)
        self.remove_editor.pack(fill="x")
        ctk.CTkLabel(container, text="The remove list offers the tags the ticked entries have.",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary()).pack(anchor="w", pady=(6, 0))

    def _accept(self):
        add, remove = self.add_editor.get_tags(), self.remove_editor.get_tags()
        if not add and not remove:
            return self._warn("Pick at least one tag to add or to remove.")
        both = {t.lower() for t in add} & {t.lower() for t in remove}
        if both:
            return self._warn(f"'{sorted(both)[0]}' is in both lists.")
        self.result = (add, remove)
        self.destroy()


class BulkSourceDialog(_BulkDialog):
    """The source to give every ticked entry (one already in use, or a new name). ``result`` is the name."""

    def __init__(self, parent, heading: str, sources: Sequence[str]):
        self._sources = list(sources)
        super().__init__(parent, "Set Source", heading, "480x300")

    def _build(self, container):
        self.source_var = ctk.StringVar()
        self.combo = ctk.CTkComboBox(container, values=self._sources, variable=self.source_var, height=35)
        self.combo.pack(fill="x")
        self.combo.set("")
        ctk.CTkLabel(container, text="Pick a source from the list or type a new one.", font=ui_font("small"),
                     text_color=self.theme.get_text_secondary()).pack(anchor="w", pady=(6, 0))

    def _accept(self):
        source = self.source_var.get().strip()
        if not source:
            return self._warn("Enter a source.")
        self.result = source
        self.destroy()


class BulkClassesDialog(_BulkDialog):
    """Classes to add to, and classes to remove from, every ticked spell. ``result`` is ``(add, remove)``."""

    def __init__(self, parent, heading: str, class_names: Sequence[str]):
        self._class_names = list(class_names)
        super().__init__(parent, "Edit Classes", heading, "560x560")

    def _build(self, container):
        columns = ctk.CTkFrame(container, fg_color="transparent")
        columns.pack(fill="both", expand=True)
        self.add_vars: Dict[str, ctk.BooleanVar] = {}
        self.remove_vars: Dict[str, ctk.BooleanVar] = {}
        for column, (title, store) in enumerate((("Add to these classes", self.add_vars),
                                                 ("Remove from these classes", self.remove_vars))):
            frame = ctk.CTkFrame(columns, fg_color="transparent")
            frame.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
            columns.grid_columnconfigure(column, weight=1, uniform="cols")
            ctk.CTkLabel(frame, text=title, font=ui_font("body", bold=True)).pack(anchor="w", pady=(0, 4))
            scroll = ctk.CTkScrollableFrame(frame, height=330)
            scroll.pack(fill="both", expand=True)
            for name in self._class_names:
                var = ctk.BooleanVar(value=False)
                store[name] = var
                ctk.CTkCheckBox(scroll, text=name, variable=var).pack(anchor="w", pady=2)
        columns.grid_rowconfigure(0, weight=1)

    def _accept(self):
        add = [n for n, v in self.add_vars.items() if v.get()]
        remove = [n for n, v in self.remove_vars.items() if v.get()]
        if not add and not remove:
            return self._warn("Tick at least one class to add or to remove.")
        both = set(add) & set(remove)
        if both:
            return self._warn(f"'{sorted(both)[0]}' is ticked in both columns.")
        self.result = (add, remove)
        self.destroy()


class BulkWarningsDialog(ctk.CTkToplevel):
    """Several entries have warnings about being added to a character. ``result`` is "all" (add them anyway),
    "clean" (add only the ones without a warning) or None (cancel)."""

    def __init__(self, parent, heading: str, rows: Sequence[Tuple[str, Sequence[str]]], clean_count: int):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.result: Optional[str] = None
        self.title("Warnings")
        self.geometry("560x520")
        self.minsize(420, 320)
        self.transient(parent)
        self.grab_set()

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        ctk.CTkLabel(container, text=heading, font=ui_font("subheading", bold=True),
                     wraplength=500, justify="left").pack(anchor="w", pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(container)
        scroll.pack(fill="both", expand=True, pady=(0, 12))
        for name, warnings in rows:
            ctk.CTkLabel(scroll, text=name, font=ui_font("body", bold=True), anchor="w").pack(fill="x", pady=(6, 0))
            for warning in warnings:
                ctk.CTkLabel(scroll, text=f"• {warning}", font=ui_font("small"), anchor="w", justify="left",
                             wraplength=470, text_color=self.theme.get_text_secondary()).pack(fill="x", padx=(10, 0))

        buttons = ctk.CTkFrame(container, fg_color="transparent")
        buttons.pack(fill="x")
        ctk.CTkButton(buttons, text="Cancel", width=90, fg_color="transparent", border_width=1,
                      command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Add all anyway", width=130,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      command=lambda: self._finish("all")).pack(side="right", padx=(8, 0))
        skip = ctk.CTkButton(buttons, text=f"Add the other {clean_count}", width=130,
                             fg_color=self.theme.get_current_color('button_normal'),
                             hover_color=self.theme.get_current_color('button_hover'),
                             text_color=self.theme.get_current_color('text_primary'),
                             command=lambda: self._finish("clean"),
                             state="normal" if clean_count else "disabled")
        skip.pack(side="right")
        center_on_parent(self, parent, clamp=True)

    def _finish(self, choice: str):
        self.result = choice
        self.destroy()


# ---------------------------------------------------------------------------------------------- the flow

class BulkActionsMixin(CharacterPickMixin):
    """The "Select" actions of a collection page (see the module docstring)."""

    BULK_ACTIONS: Tuple[str, ...] = ()       # any of "add", "tags", "classes", "source", in the order shown
    BULK_NOUN = "entry"
    BULK_PLURAL = "entries"
    BULK_EDIT_OFFICIAL = False               # may bundled (official) entries be edited? (spells: yes)
    BULK_PANEL_ATTR = "list_panel"           # the page's list panel

    # ---- what a page supplies --------------------------------------------------------------------

    def _bulk_fetch(self, name: str):
        """The entry as stored now, or None."""
        raise NotImplementedError

    def _bulk_store(self, entries: list) -> int:
        """Save the edited entries (one transaction where it can); returns how many were saved."""
        raise NotImplementedError

    def _bulk_reload(self):
        """Show the saved changes in the page."""
        raise NotImplementedError

    def _bulk_give(self, character, entries: list) -> Optional[str]:
        """Add the entries to ``character``; returns the message to show (None: nothing to say, e.g. cancelled)."""
        raise NotImplementedError

    def _bulk_all_tags(self) -> List[str]:
        return []

    def _bulk_all_sources(self) -> List[str]:
        return []

    def _bulk_class_names(self) -> List[str]:
        return []

    def _bulk_is_protected_tag(self) -> Optional[Callable[[str], bool]]:
        return None

    # ---- set-up ----------------------------------------------------------------------------------

    @property
    def _bulk_panel(self):
        return getattr(self, self.BULK_PANEL_ATTR)

    def _setup_bulk_actions(self):
        actions = {
            "add": ("Add to Character", self._bulk_add_to_character),
            "tags": ("Edit Tags", self._bulk_edit_tags),
            "classes": ("Edit Classes", self._bulk_edit_classes),
            "source": ("Set Source", self._bulk_set_source),
        }
        chosen = [actions[key] for key in self.BULK_ACTIONS]
        chosen.append(("Export PDF", self._bulk_export_pdf))
        self._bulk_panel.enable_bulk_actions(chosen)

    # ---- helpers ---------------------------------------------------------------------------------

    def _bulk_count_text(self, n: int) -> str:
        return count_text(n, self.BULK_NOUN, self.BULK_PLURAL)

    def _bulk_split(self, entries: list) -> Tuple[list, int]:
        """``(the entries that may be edited, how many are official and so left alone)``."""
        if self.BULK_EDIT_OFFICIAL:
            return list(entries), 0
        editable = [e for e in entries if getattr(e, "is_custom", False)]
        return editable, len(entries) - len(editable)

    def _bulk_fresh(self, entries: list) -> list:
        """Private copies of the entries as stored now (an entry that has gone is left out)."""
        fresh = []
        for entry in entries:
            current = self._bulk_fetch(entry.name)
            if current is not None:
                fresh.append(copy.deepcopy(current))
        return fresh

    def _bulk_finish(self, saved: int, total: int, details: Sequence[str] = ()):
        current = self._bulk_panel.get_selected()
        if current is not None:                    # the detail pane shows the edited entry, not the old one
            self._bulk_panel.select_when_listed(current.name)
        self._bulk_reload()
        lines = [f"Updated {saved} of {self._bulk_count_text(total)}." if saved != total
                 else f"Updated {self._bulk_count_text(saved)}."]
        lines += [d for d in details if d]
        messagebox.showinfo("Bulk edit", "\n".join(lines), parent=self)

    def _bulk_nothing_editable(self, official: int):
        messagebox.showinfo(
            "Bulk edit",
            f"The {official} ticked {self.BULK_PLURAL if official != 1 else self.BULK_NOUN} "
            f"{'are' if official != 1 else 'is'} official, and official content can't be edited. "
            f"Your own {self.BULK_PLURAL} can.", parent=self)

    @staticmethod
    def _official_note(official: int) -> str:
        return f"{official} official left alone." if official else ""

    # ---- add to character ------------------------------------------------------------------------

    def _bulk_add_to_character(self, entries: list):
        if not entries:
            return
        character = self._pick_character(f"Add {self._bulk_count_text(len(entries))} to:")
        if not character:
            return
        message = self._bulk_give(character, self._bulk_fresh(entries))
        if message:
            messagebox.showinfo("Added", message, parent=self)

    # ---- export PDF ------------------------------------------------------------------------------

    def _bulk_export_pdf(self, entries: list):
        if not entries:
            return
        import pdf_export
        if not pdf_export.available():
            messagebox.showerror("Export PDF", "Exporting needs the 'reportlab' package, which isn't installed.",
                                 parent=self)
            return
        fresh = sorted(self._bulk_fresh(entries), key=lambda e: e.name.lower())
        dialog = ExportPdfDialog(self.winfo_toplevel(), f"Export {self._bulk_count_text(len(fresh))} as a PDF",
                                 self.BULK_PLURAL.title())
        self.wait_window(dialog)
        if dialog.result is None:
            return
        options = dialog.result
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in options.title).strip() or "export"
        path = filedialog.asksaveasfilename(parent=self, title="Save PDF", defaultextension=".pdf",
                                            initialfile=f"{safe}.pdf", filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            pdf_export.export_pdf(path, fresh, options)
        except Exception as e:                 # a locked file, a full disk, or text reportlab can't lay out
            messagebox.showerror("Export PDF", f"The PDF couldn't be written.\n\n{e}", parent=self)
            return
        if messagebox.askyesno("Export PDF", f"Saved {self._bulk_count_text(len(fresh))} to\n{path}\n\n"
                               "Open it now?", parent=self):
            from ui.pdf_library_view import open_externally
            open_externally(path)

    # ---- tags ------------------------------------------------------------------------------------

    def _bulk_edit_tags(self, entries: list):
        editable, official = self._bulk_split(entries)
        if not editable:
            return self._bulk_nothing_editable(official)
        present = sorted({t for e in editable for t in e.tags}, key=str.lower)
        dialog = BulkTagsDialog(self.winfo_toplevel(), f"Edit the tags of {self._bulk_count_text(len(editable))}",
                                self._bulk_all_tags(), present, self._bulk_is_protected_tag())
        self.wait_window(dialog)
        if not dialog.result:
            return
        add, remove = dialog.result
        remove_lower = {t.lower() for t in remove}
        changed = []
        for entry in self._bulk_fresh(editable):
            tags = [t for t in entry.tags if t.lower() not in remove_lower]
            have = {t.lower() for t in tags}
            tags += [t for t in add if t.lower() not in have]
            if tags != entry.tags:
                entry.tags = tags
                changed.append(entry)
        saved = self._bulk_store(changed) if changed else 0
        self._bulk_finish(saved, len(editable), [
            f"{len(editable) - len(changed)} already matched." if len(editable) != len(changed) else "",
            self._official_note(official)])

    # ---- source ----------------------------------------------------------------------------------

    def _bulk_set_source(self, entries: list):
        editable, official = self._bulk_split(entries)
        if not editable:
            return self._bulk_nothing_editable(official)
        dialog = BulkSourceDialog(
            self.winfo_toplevel(), f"Set the source of {self._bulk_count_text(len(editable))} to:",
            self._bulk_all_sources())
        self.wait_window(dialog)
        if not dialog.result:
            return
        changed = []
        for entry in self._bulk_fresh(editable):
            if entry.source != dialog.result:
                entry.source = dialog.result
                changed.append(entry)
        saved = self._bulk_store(changed) if changed else 0
        self._bulk_finish(saved, len(editable), [
            f"{len(editable) - len(changed)} already had that source." if len(editable) != len(changed) else "",
            self._official_note(official)])

    # ---- classes (spells) ------------------------------------------------------------------------

    def _bulk_edit_classes(self, entries: list):
        editable, official = self._bulk_split(entries)
        if not editable:
            return self._bulk_nothing_editable(official)
        dialog = BulkClassesDialog(
            self.winfo_toplevel(), f"Edit the classes of {self._bulk_count_text(len(editable))}",
            self._bulk_class_names())
        self.wait_window(dialog)
        if not dialog.result:
            return
        add, remove = dialog.result
        remove_lower = {c.lower() for c in remove}
        changed, emptied = [], 0
        for entry in self._bulk_fresh(editable):
            names = [c for c in entry.get_class_names() if c.lower() not in remove_lower]
            have = {c.lower() for c in names}
            names += [c for c in add if c.lower() not in have]
            if names == entry.get_class_names():
                continue
            if not names:                          # a spell on no class list would vanish from every list
                emptied += 1
                continue
            self._bulk_set_classes(entry, names)
            changed.append(entry)
        saved = self._bulk_store(changed) if changed else 0
        self._bulk_finish(saved, len(editable), [
            f"{emptied} kept their classes (they would have been left with none)." if emptied else "",
            self._official_note(official)])

    def _bulk_set_classes(self, entry, names: List[str]):
        raise NotImplementedError
