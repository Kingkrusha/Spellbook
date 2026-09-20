"""
Auto-detect (rule-based) feat import UI for the D&D Spellbook.

Two small dialogs, mirroring ui/spell_text_import.py:

* ``AddFeatSourceDialog`` - asks whether to add a feat manually or by pasting
  a block of text for auto-detection.
* ``FeatTextImportDialog`` - the paste box + disclaimer; parses the text into
  one or more ``ParsedObject`` results for review in the normal feat editor.

No LLM / network use - parsing is entirely rule-based (see ``text_import``).
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import List, Optional

from theme import get_theme_manager


class AddFeatSourceDialog(ctk.CTkToplevel):
    """Ask how the user wants to create a new feat."""

    def __init__(self, parent):
        super().__init__(parent)

        self.result: Optional[str] = None  # "manual" | "auto" | None

        self.title("Add Feat")
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
            container, text="How would you like to add this feat?",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            container,
            text="You can fill in every field yourself, or paste a block of feat "
                 "text and let Spellbook fill in what it can for you to review.",
            font=ctk.CTkFont(size=11), text_color=theme.get_text_secondary(),
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

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _choose_manual(self):
        self.result = "manual"
        self.destroy()

    def _choose_auto(self):
        self.result = "auto"
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


_PLACEHOLDER = """Paste one or more feats here, for example:

Alert
Origin Feat
Prerequisite: None
You gain the following benefits:
Initiative Proficiency. You can add your proficiency bonus to your
initiative rolls...
"""


class FeatTextImportDialog(ctk.CTkToplevel):
    """Collect a block of text and parse it into one or more feat drafts."""

    def __init__(self, parent):
        super().__init__(parent)

        self.result: Optional[List] = None  # List[ParsedObject]

        self.title("Auto-Detect Feats From Text")
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
            container, text="Paste feat text below",
            font=ctk.CTkFont(size=15, weight="bold"), anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            container,
            text="Multiple feats can be pasted at once - no numbering or separators "
                 "needed. Spellbook looks for a name followed by a category line "
                 "(\"Origin Feat\", \"Epic Boon\", ...) or a \"Prerequisite:\" line "
                 "to tell them apart.",
            font=ctk.CTkFont(size=11), text_color=theme.get_text_secondary(),
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
            disclaimer,
            text="⚠  Auto-detection is rule-based and may not be fully accurate, "
                 "especially for irregularly formatted text - feats vary a lot more "
                 "than spells do, and spellcasting fields in particular are a best "
                 "guess. Every detected feat opens in the editor for you to review "
                 "and correct before it is saved.",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=warn,
            justify="left", wraplength=580, anchor="w",
        ).pack(fill="x", padx=12, pady=8)

        self._text = ctk.CTkTextbox(container, corner_radius=8,
                                    font=ctk.CTkFont(size=12))
        self._text.pack(fill="both", expand=True, pady=(0, 8))
        self._text.insert("1.0", _PLACEHOLDER)
        self._placeholder_active = True
        self._text.bind("<FocusIn>", self._clear_placeholder)

        self._status = ctk.CTkLabel(
            container, text="", font=ctk.CTkFont(size=12),
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

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------ #

    def _clear_placeholder(self, _event=None):
        if self._placeholder_active:
            self._text.delete("1.0", "end")
            self._placeholder_active = False

    def _get_text(self) -> str:
        if self._placeholder_active:
            return ""
        return self._text.get("1.0", "end").strip()

    def _preview(self):
        from text_import.feat_parser import split_blocks
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
            text=f"Detected {n} feat block{'s' if n != 1 else ''}."
        )

    def _detect(self):
        from text_import.feat_parser import parse_feat_text
        text = self._get_text()
        if not text:
            messagebox.showwarning("No Text", "Please paste some feat text first.",
                                   parent=self)
            return

        try:
            parsed = parse_feat_text(text)
        except Exception as exc:  # never let a parser hiccup kill the dialog
            messagebox.showerror(
                "Could Not Parse",
                f"Something went wrong reading that text:\n{exc}\n\n"
                "Try pasting a single feat, or add it manually instead.",
                parent=self,
            )
            return
        parsed = [p for p in parsed if (p.get("name") or "").strip()
                  or (p.get("description") or "").strip()]
        if not parsed:
            messagebox.showwarning(
                "Nothing Detected",
                "Could not find a feat in that text.\n\n"
                "Make sure each feat has a name line, ideally followed by a "
                "category line (e.g. \"Origin Feat\") or a \"Prerequisite:\" line.",
                parent=self,
            )
            return

        self.result = parsed
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
