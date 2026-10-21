"""
The two dialogs behind "Auto-Detect From Text", for every collection that has one.

Adding a spell, feat, lineage, equipment item or magic item offers a choice: fill the editor in by hand, or
paste a block of text and let the rule-based parser (see ``text_import``) fill in what it can. The two dialogs
that offer that were five near-identical files; they differ only in their wording and in which parser they
call, so that is all a :class:`TextImportSpec` holds:

* :class:`AddSourceDialog` - asks "by hand, or from pasted text?"; ``result`` is ``"manual"``, ``"auto"`` or None.
* :class:`TextImportDialog` - the paste box and disclaimer; ``result`` is a list of ``ParsedObject`` (to review in
  the normal editor) or None.

``ui/feat_text_import.py`` and its siblings subclass these with their spec. No LLM or network is involved.
"""

import importlib
from dataclasses import dataclass
from tkinter import messagebox
from typing import List, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.window_utils import center_on_parent


@dataclass(frozen=True)
class TextImportSpec:
    # the "how would you like to add it" dialog
    add_title: str                 # "Add Feat"
    add_question: str              # "How would you like to add this feat?"
    add_blurb: str
    # the paste dialog
    import_title: str              # "Auto-Detect Feats From Text"
    paste_heading: str             # "Paste feat text below"
    paste_help: str
    disclaimer: str                # shown after the warning sign
    placeholder: str
    detected_unit: str             # "feat block" -> "Detected 3 feat blocks."
    empty_warning: str             # "Please paste some feat text first."
    retry_hint: str                # "Try pasting a single feat, or add it manually instead."
    nothing_found: str             # the whole "Nothing Detected" message
    # the parser (imported when first used)
    parser_module: str             # "text_import.feat_parser"
    parse_function: str            # "parse_feat_text"


class AddSourceDialog(ctk.CTkToplevel):
    """Ask how the user wants to create a new entry."""

    SPEC: TextImportSpec = None

    def __init__(self, parent):
        super().__init__(parent)
        spec = self.SPEC

        self.result: Optional[str] = None  # "manual" | "auto" | None

        self.title(spec.add_title)
        self.geometry("440x300")
        self.minsize(400, 280)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        theme = get_theme_manager()
        btn_text = theme.get_current_color('text_primary')

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container, text=spec.add_question,
            font=ui_font("subheading", 15, bold=True),
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            container, text=spec.add_blurb,
            font=ui_font("small"), text_color=theme.get_text_secondary(),
            justify="left", wraplength=380,
        ).pack(fill="x", pady=(0, 16))

        ctk.CTkButton(
            container, text="Enter Manually", height=42,
            text_color=btn_text, command=self._choose_manual,
        ).pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            container, text="Auto-Detect From Text", height=42,
            fg_color=theme.get_current_color('button_success'),
            hover_color=theme.get_current_color('button_success_hover'),
            text_color=btn_text, command=self._choose_auto,
        ).pack(fill="x", pady=(0, 16))

        ctk.CTkButton(
            container, text="Cancel", height=32, width=100,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text, command=self._cancel,
        ).pack()

        self.bind("<Escape>", lambda _e: self._cancel())

        center_on_parent(self, parent, root_coords=False)

    def _choose_manual(self):
        self.result = "manual"
        self.destroy()

    def _choose_auto(self):
        self.result = "auto"
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class TextImportDialog(ctk.CTkToplevel):
    """Collect a block of text and parse it into one or more drafts."""

    SPEC: TextImportSpec = None
    # Text the next dialog opens with instead of the example (set by the PDF library's Import Text)
    PREFILL: Optional[str] = None

    def __init__(self, parent):
        super().__init__(parent)
        spec = self.SPEC

        self.result: Optional[List] = None  # List[ParsedObject]

        self.title(spec.import_title)
        self.geometry("640x620")
        self.minsize(560, 520)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        theme = get_theme_manager()
        btn_text = theme.get_current_color('text_primary')

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(
            container, text=spec.paste_heading,
            font=ui_font("subheading", 15, bold=True), anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            container, text=spec.paste_help,
            font=ui_font("small"), text_color=theme.get_text_secondary(),
            justify="left", wraplength=580, anchor="w",
        ).pack(fill="x", pady=(2, 8))

        # Disclaimer - deliberately prominent.
        disclaimer = ctk.CTkFrame(container, fg_color=theme.get_current_color('bg_secondary'),
                                  corner_radius=8)
        disclaimer.pack(fill="x", pady=(0, 10))
        try:
            warn = theme.get_current_color('button_warning')
        except Exception:
            warn = "#d4a017"
        ctk.CTkLabel(
            disclaimer, text="⚠  " + spec.disclaimer,
            font=ui_font("small", bold=True), text_color=warn,
            justify="left", wraplength=580, anchor="w",
        ).pack(fill="x", padx=12, pady=8)

        self._text = ctk.CTkTextbox(container, corner_radius=8,
                                    font=ui_font("body"))
        self._text.pack(fill="both", expand=True, pady=(0, 8))
        prefill, TextImportDialog.PREFILL = TextImportDialog.PREFILL, None
        if prefill:
            self._text.insert("1.0", prefill)
            self._placeholder_active = False
        else:
            self._text.insert("1.0", spec.placeholder)
            self._placeholder_active = True
        self._text.bind("<FocusIn>", self._clear_placeholder)

        self._status = ctk.CTkLabel(
            container, text="", font=ui_font("body"),
            text_color=theme.get_text_secondary(), anchor="w",
        )
        self._status.pack(fill="x", pady=(0, 8))

        buttons = ctk.CTkFrame(container, fg_color="transparent")
        buttons.pack(fill="x")

        ctk.CTkButton(
            buttons, text="Cancel", width=100,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text, command=self._cancel,
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            buttons, text="Detect & Review", width=140,
            text_color=btn_text, command=self._detect,
        ).pack(side="right")

        ctk.CTkButton(
            buttons, text="Preview Count", width=120,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text, command=self._preview,
        ).pack(side="left")

        self.bind("<Escape>", lambda _e: self._cancel())

        center_on_parent(self, parent, root_coords=False)

    # ------------------------------------------------------------------ #

    def _clear_placeholder(self, _event=None):
        if self._placeholder_active:
            self._text.delete("1.0", "end")
            self._placeholder_active = False

    def _get_text(self) -> str:
        if self._placeholder_active:
            return ""
        return self._text.get("1.0", "end").strip()

    def _parser(self):
        return importlib.import_module(self.SPEC.parser_module)

    def _preview(self):
        split_blocks = self._parser().split_blocks
        text = self._get_text()
        if not text:
            self._status.configure(text="Nothing to parse yet.")
            return
        try:
            n = len(split_blocks(text))
        except Exception:
            self._status.configure(text="Could not read that text.")
            return
        self._status.configure(
            text=f"Detected {n} {self.SPEC.detected_unit}{'s' if n != 1 else ''}."
        )

    def _detect(self):
        parse = getattr(self._parser(), self.SPEC.parse_function)
        text = self._get_text()
        if not text:
            messagebox.showwarning("No Text", self.SPEC.empty_warning, parent=self)
            return

        try:
            parsed = parse(text)
        except Exception as exc:  # never let a parser hiccup kill the dialog
            messagebox.showerror(
                "Could Not Parse",
                f"Something went wrong reading that text:\n{exc}\n\n{self.SPEC.retry_hint}",
                parent=self,
            )
            return
        parsed = [p for p in parsed if (p.get("name") or "").strip()
                  or (p.get("description") or "").strip()]
        if not parsed:
            messagebox.showwarning("Nothing Detected", self.SPEC.nothing_found, parent=self)
            return

        self.result = parsed
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
