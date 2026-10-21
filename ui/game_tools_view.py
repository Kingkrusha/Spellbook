"""Game Tools page: the tools for running a game at the table (Session chat and, later,
the initiative tracker)."""

from typing import Callable, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font


class GameToolsView(ctk.CTkFrame):
    # (key, title, description, enabled)
    TOOLS = [
        ("session", "🌐 Session",
         "Host or join an encrypted game on your network or VPN: chat with your table and send "
         "characters and homebrew to each other.", True),
        ("initiative", "⚔️ Initiative Tracker",
         "Run combat: turn order, HP, AC and conditions for everyone at the table, with a pop-up "
         "window players can keep on top of their other apps.", True),
        ("dice_analyzer", "🎲 Dice Analyzer",
         "The odds of any roll: mixed dice, modifiers, advantage, rerolls and minimums, or a roll from a "
         "character sheet with the character's features counted.", True),
        ("matchup", "🥊 Matchup",
         "Put two creatures or characters in a one-on-one fight: the odds, how long it takes, each side's damage "
         "against the other and what could swing it.", True),
        ("random_tables", "📜 Random Tables",
         "Store d100 tables (or d20, 2d6...), search them, and roll: the result comes up straight away, with "
         "any dice or other tables it names rolled too.", True),
        ("calendar", "📅 Calendar",
         "Each campaign's calendar and clock: your own months, weeks and holidays, and progress bars for "
         "crafting, travel or training that fill as the days pass.", True),
        ("studio", "🛠️ Homebrew Studio",
         "Write your own spells, items, monsters, classes and more with the rest of the collection beside you: "
         "it points out content that already does the same thing and checks a monster against its CR.", True),
    ]

    def __init__(self, parent, service=None, on_open: Optional[Callable[[str], None]] = None,
                 on_home: Optional[Callable[[], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.service = service
        self.on_open = on_open
        self.on_home = on_home

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        if on_home:
            ctk.CTkButton(
                header, text="← Home", width=90, height=32,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                command=on_home).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(header, text="Game Tools", font=ui_font("title", 28, bold=True)).pack(side="left")

        # the cards wrap onto more rows when the window is narrow
        self._row = ctk.CTkFrame(outer, fg_color="transparent")
        self._row.pack(anchor="n")
        self._cards = []
        for tool in self.TOOLS:
            self._cards.append(self._card(self._row, 0, *tool))
        self._columns = 0
        outer.bind("<Configure>", self._on_resize)
        self._layout(3)

    CARD_SPAN = 330

    def _on_resize(self, event):
        self._layout(max(1, (event.width - 40) // self.CARD_SPAN))

    def _layout(self, columns: int):
        columns = max(1, min(columns, len(self._cards)))
        if columns == self._columns:
            return
        self._columns = columns
        for i, card in enumerate(self._cards):
            card.grid(row=i // columns, column=i % columns, padx=14, pady=10, sticky="n")

    def _card(self, parent, column: int, key: str, title: str, description: str, enabled: bool):
        card = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_secondary'),
                            corner_radius=14, width=300, height=220)
        card.pack_propagate(False)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22, pady=22)

        ctk.CTkLabel(
            inner, text=title, font=ui_font("heading", 20, bold=True),
            text_color=self.theme.get_current_color('text_primary') if enabled
            else self.theme.get_text_secondary()).pack(anchor="w")
        ctk.CTkLabel(inner, text=description, font=ui_font("body"),
                     text_color=self.theme.get_text_secondary(),
                     wraplength=250, justify="left").pack(anchor="w", pady=(8, 0))

        if key == "session" and self.service is not None and self.service.in_session:
            ctk.CTkLabel(inner, text="● A session is running", font=ui_font("small", bold=True),
                         text_color=self.theme.get_current_color('button_success')
                         ).pack(side="bottom", anchor="w", pady=(0, 6))

        if enabled:
            ctk.CTkButton(
                inner, text="Open →", width=120, height=34,
                fg_color=self.theme.get_current_color('accent_primary'),
                hover_color=self.theme.get_current_color('accent_hover'),
                command=lambda k=key: self.on_open and self.on_open(k)
            ).pack(side="bottom", anchor="w")
        else:
            ctk.CTkButton(
                inner, text="Coming Soon", width=120, height=34,
                fg_color=self.theme.get_current_color('bg_tertiary'),
                hover_color=self.theme.get_current_color('bg_tertiary'),
                text_color=self.theme.get_text_secondary(), state="disabled"
            ).pack(side="bottom", anchor="w")
        return card
