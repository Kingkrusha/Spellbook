"""
Home page: what a new tab shows. Three big entry points - Collections,
Characters and Game Tools.
"""

import customtkinter as ctk
from typing import Callable, Optional

from typography import ui_font
from theme import get_theme_manager


class HomeView(ctk.CTkFrame):
    """Landing page with one card per area of the app."""

    # (key, title, description, enabled)
    SECTIONS = [
        ("collections", "📚 Collections",
         "View, sort and search databases of spells, classes, feats, lineages, backgrounds, equipment, magic items and monsters.", True),
        ("characters", "⚔️ Characters",
         "Your characters and their sheets. Create, sort, filter, import and export them.", True),
        ("game_tools", "🎲 Game Tools",
         "Tools to help you run your games smoothly: host a LAN session, chat with your table and send characters.", True),
    ]

    def __init__(self, parent, on_open: Optional[Callable[[str], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.on_open = on_open  # called with the section key
        self._create_widgets()

    def _create_widgets(self):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(
            outer, text="Spellbook",
            font=ui_font("title", 34, bold=True)
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            outer, text="A Dungeons & Dragons 5e reference and character management app.",
            font=ui_font("subheading"),
            text_color=self.theme.get_text_secondary()
        ).pack(pady=(0, 30))

        row = ctk.CTkFrame(outer, fg_color="transparent")
        row.pack()

        for column, (key, title, description, enabled) in enumerate(self.SECTIONS):
            self._create_card(row, key, title, description, enabled, column)

    def _create_card(self, parent, key: str, title: str, description: str, enabled: bool, column: int):
        card = ctk.CTkFrame(
            parent,
            fg_color=self.theme.get_current_color('bg_secondary'),
            corner_radius=14,
            width=260, height=230
        )
        card.grid(row=0, column=column, padx=14, pady=10)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22, pady=22)

        title_color = self.theme.get_current_color('text_primary') if enabled else self.theme.get_text_secondary()
        ctk.CTkLabel(
            inner, text=title,
            font=ui_font("heading", 20, bold=True),
            text_color=title_color
        ).pack(anchor="w")

        ctk.CTkLabel(
            inner, text=description,
            font=ui_font("body"),
            text_color=self.theme.get_text_secondary(),
            wraplength=210, justify="left"
        ).pack(anchor="w", pady=(8, 0))

        if enabled:
            ctk.CTkButton(
                inner, text="Open →",
                width=120, height=34,
                fg_color=self.theme.get_current_color('accent_primary'),
                hover_color=self.theme.get_current_color('accent_secondary'),
                command=lambda k=key: self._open(k)
            ).pack(side="bottom", anchor="w")
        else:
            ctk.CTkButton(
                inner, text="Coming Soon",
                width=120, height=34,
                fg_color=self.theme.get_current_color('bg_tertiary'),
                hover_color=self.theme.get_current_color('bg_tertiary'),
                text_color=self.theme.get_text_secondary(),
                state="disabled"
            ).pack(side="bottom", anchor="w")

    def _open(self, key: str):
        if self.on_open:
            self.on_open(key)
