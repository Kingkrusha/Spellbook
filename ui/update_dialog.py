"""Dialog shown when a newer Spellbook release is available.

Purely a notification: it shows the release notes and a button that opens the
GitHub releases page in the user's browser. The app itself never downloads,
writes, or runs an executable as part of updating - the user gets the file
through their browser like any other download, and installs it themselves.
"""

from __future__ import annotations

from typing import Callable, Optional

import customtkinter as ctk

from theme import get_theme_manager
from updater import UpdateInfo, open_release_page
from version import __version__


class UpdateDialog(ctk.CTkToplevel):
    """'Update available' notification window.

    ``on_skip`` (if given) is called with ``info.version`` when the user chooses
    "Skip This Version", so the caller can persist that and stop nagging.
    """

    def __init__(
        self,
        parent,
        info: UpdateInfo,
        on_skip: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)

        self._info = info
        self._on_skip = on_skip
        self._theme = get_theme_manager()

        self.title("Update Available")
        self.geometry("480x420")
        self.minsize(420, 360)
        self.transient(parent)

        try:
            self.configure(fg_color=self._theme.get_current_color("bg_primary"))
        except Exception:
            pass

        self._build()

        # Centre on the parent window.
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except Exception:
            pass

        self.lift()
        self.after(100, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except Exception:
            pass

    # --- UI ----------------------------------------------------------------

    def _build(self):
        theme = self._theme
        text_secondary = theme.get_text_secondary()
        btn_text = theme.get_current_color("text_primary")
        btn_normal = theme.get_current_color("button_normal")
        btn_hover = theme.get_current_color("button_hover")

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container,
            text=f"Spellbook {self._info.version} is available",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            container,
            text=f"You have version {__version__}.",
            font=ctk.CTkFont(size=12),
            text_color=text_secondary,
        ).pack(anchor="w", pady=(2, 12))

        notes_header = "What's new" if self._info.notes else "Release"
        ctk.CTkLabel(
            container,
            text=notes_header,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w")

        notes_box = ctk.CTkTextbox(
            container,
            wrap="word",
            font=ctk.CTkFont(size=12),
            fg_color=theme.get_current_color("bg_secondary"),
            text_color=theme.get_current_color("text_primary"),
        )
        notes_box.pack(fill="both", expand=True, pady=(4, 12))
        notes_box.insert(
            "1.0",
            self._info.notes or "No release notes were provided.",
        )
        notes_box.configure(state="disabled")

        ctk.CTkLabel(
            container,
            text="Download it from GitHub and run it to update - Spellbook doesn't install updates automatically.",
            font=ctk.CTkFont(size=11),
            text_color=text_secondary,
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Buttons.
        buttons = ctk.CTkFrame(container, fg_color="transparent")
        buttons.pack(fill="x")

        later_btn = ctk.CTkButton(
            buttons, text="Later", width=80,
            fg_color=btn_normal, hover_color=btn_hover, text_color=btn_text,
            command=self.destroy,
        )
        later_btn.pack(side="right")

        skip_btn = ctk.CTkButton(
            buttons, text="Skip This Version", width=140,
            fg_color=btn_normal, hover_color=btn_hover, text_color=btn_text,
            command=self._on_skip_clicked,
        )
        skip_btn.pack(side="right", padx=(0, 10))

        view_btn = ctk.CTkButton(
            buttons, text="View on GitHub", width=140,
            text_color=btn_text,
            command=self._on_view,
        )
        view_btn.pack(side="left")

    # --- actions ---------------------------------------------------------

    def _on_view(self):
        open_release_page(self._info)

    def _on_skip_clicked(self):
        if self._on_skip:
            try:
                self._on_skip(self._info.version)
            except Exception:
                pass
        self.destroy()
