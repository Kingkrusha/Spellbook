"""
Stat block widgets for D&D Spellbook Application.

MonsterStatBlock draws one monster's stat block; it is shared by the Monsters
collection page, the spell page (the creatures a spell summons) and the object
link popup. CollapsibleMonsterCard wraps it in a header with a collapse toggle
and an optional Edit button, for stacking several on the spell page.
"""

import customtkinter as ctk
from typography import ui_font
from typing import Callable, List, Optional

from character_sheet import AbilityScore
from monster import Monster
from stat_block import StatBlockFeature
from theme import get_theme_manager

ABILITY_ROWS = [
    [AbilityScore.STRENGTH, AbilityScore.DEXTERITY, AbilityScore.CONSTITUTION],
    [AbilityScore.INTELLIGENCE, AbilityScore.WISDOM, AbilityScore.CHARISMA],
]


def signed(value: int) -> str:
    return f"+{value}" if value >= 0 else f"{value}"


class MonsterStatBlock(ctk.CTkFrame):
    """A monster's stat block: header, core stats, ability table, defenses/senses,
    then Traits / Actions / ... sections, lore and source.

    The body is rebuilt for every monster, so a row that is empty (no skills, no
    immunities, no legendary actions, ...) is simply never created.

    `bg_key` is the theme colour the block sits on ('bg_primary' or
    'bg_secondary'); the text areas need it to blend in.
    """

    def __init__(self, parent, monster: Optional[Monster] = None, bg_key: str = "bg_primary",
                 show_name: bool = True):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self._bg_key = bg_key
        self._show_name = show_name
        self._monster: Optional[Monster] = None
        self._body: Optional[ctk.CTkFrame] = None
        if monster is not None:
            self.show_monster(monster)

    # ----- building blocks -----

    def _text(self, text: str, size: int = 13, pady=(1, 1)):
        from ui.rich_text_utils import DynamicText
        dt = DynamicText(self._body, self.theme, font_size=size, bg_color=self._bg_key)
        dt.set_text(text)
        dt.pack(fill="x", anchor="w", pady=pady)
        return dt

    def _line(self, label: str, value: str):
        if value:
            self._text(f"**{label}** {value}")

    def _rule(self, pady=(6, 6)):
        ctk.CTkFrame(self._body, height=2, fg_color=self.theme.get_current_color('accent_primary')
                     ).pack(fill="x", pady=pady)

    def _heading(self, title: str):
        ctk.CTkLabel(
            self._body, text=title, anchor="w",
            font=ui_font("heading", 16, bold=True),
            text_color=self.theme.get_current_color('accent_primary'),
        ).pack(fill="x", pady=(12, 0))
        self._rule(pady=(0, 4))

    def _features(self, title: str, features: List[StatBlockFeature], intro: str = ""):
        if not features and not intro:
            return
        self._heading(title)
        if intro:
            self._text(intro, pady=(2, 4))
        for feature in features:
            self._text(f"**{feature.name}.** {feature.description}".strip(), pady=(2, 2))

    def _shade(self, key: str, amount: float) -> str:
        """The block's background with `amount` (0-1) of another theme colour mixed in."""
        def rgb(color):
            return [c // 257 for c in self.winfo_rgb(color)]        # 16-bit -> 8-bit
        base, mix = rgb(self.theme.get_current_color(self._bg_key)), rgb(self.theme.get_current_color(key))
        return "#%02x%02x%02x" % tuple(round(b + (m - b) * amount) for b, m in zip(base, mix))

    def _ability_table(self, monster: Monster):
        """Two rows of three abilities. Each is four small boxes - name, score,
        modifier, save - shaded differently so they read as separate cells."""
        # name box picks up the accent colour; the number boxes step from light to darker
        shades = (self._shade('accent_primary', 0.55), self._shade('text_primary', 0.20),
                  self._shade('text_primary', 0.11), self._shade('text_primary', 0.16))
        table = ctk.CTkFrame(self._body, fg_color="transparent")
        table.pack(anchor="w", pady=(8, 8))
        muted = self.theme.get_text_secondary()
        box = dict(width=40, height=26, corner_radius=4)
        for band, row in enumerate(ABILITY_ROWS):
            top = band * 2
            for group, ability in enumerate(row):
                base = group * 5                          # 4 boxes plus a gap column
                proficient = monster.saving_throws.is_proficient(ability)
                for offset, text in ((2, "MOD"), (3, "SAVE")):
                    ctk.CTkLabel(table, text=text, font=ui_font("small", 9), text_color=muted, height=14
                                 ).grid(row=top, column=base + offset, pady=(4 if band else 0, 0))
                cells = (
                    (AbilityScore.short_name(ability), ui_font("body", bold=True)),
                    (str(monster.ability_scores.get(ability)), ui_font("body", 13)),
                    (signed(monster.get_modifier(ability)), ui_font("body", 13)),
                    (signed(monster.get_save_bonus(ability)),
                     ui_font("body", 13, bold=proficient)),
                )
                for offset, ((text, font), shade) in enumerate(zip(cells, shades)):
                    ctk.CTkLabel(table, text=text, font=font, fg_color=shade, **box).grid(
                        row=top + 1, column=base + offset, padx=1, pady=1)
            table.columnconfigure(4, minsize=14)          # gap between the ability groups
            table.columnconfigure(9, minsize=14)

    # ----- content -----

    def refresh(self):
        """Redraw (e.g. after a theme change)."""
        if self._monster is not None:
            self.show_monster(self._monster)

    def show_monster(self, monster: Monster):
        self._monster = monster
        if self._body is not None:
            self._body.destroy()
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="x")

        muted = self.theme.get_text_secondary()
        if self._show_name:
            ctk.CTkLabel(
                self._body, text=f"* {monster.name}" if monster.is_custom else monster.name,
                font=ui_font("title", bold=True), wraplength=460, justify="left", anchor="w",
            ).pack(anchor="w")
        if monster.epithet:
            # trailing space: Tk clips the last italic glyph
            ctk.CTkLabel(self._body, text=monster.epithet + " ", text_color=muted, anchor="w",
                         font=ui_font("body", 13, italic=True), wraplength=460, justify="left"
                         ).pack(anchor="w")
        ctk.CTkLabel(self._body, text=monster.get_type_line() + " ", anchor="w",
                     font=ui_font("body", 13, italic=True), wraplength=460, justify="left"
                     ).pack(anchor="w", pady=(2, 0))
        self._rule()

        core = f"**AC** {monster.display_ac()}"
        if monster.show_initiative:
            core += f"      **Initiative** {monster.display_initiative()}"
        self._text(core)
        self._line("HP", monster.display_hp())
        self._line("Speed", monster.display_speed())
        self._ability_table(monster)

        self._line("Skills", monster.display_skills())
        self._line("Vulnerabilities", monster.display_vulnerabilities())
        self._line("Resistances", monster.display_resistances())
        self._line("Immunities", monster.display_immunities())
        self._line("Senses", monster.display_senses())
        self._line("Languages", monster.display_languages())
        self._line("Gear", monster.display_gear())
        self._line("CR", monster.display_cr().removeprefix("CR "))

        self._features("Traits", monster.traits)
        self._features("Actions", monster.actions)
        self._features("Bonus Actions", monster.bonus_actions)
        self._features("Reactions", monster.reactions)
        self._features("Legendary Actions", monster.legendary_actions,
                       monster.get_legendary_intro() if monster.legendary_actions else "")
        self._features("Lair Actions", monster.lair_actions, monster.lair_actions_intro)

        if monster.habitat or monster.treasure:
            self._rule(pady=(12, 4))
            parts = []
            if monster.habitat:
                parts.append(f"**Habitat:** {monster.display_habitat()}")
            if monster.treasure:
                parts.append(f"**Treasure:** {monster.display_treasure()}")
            self._text("      ".join(parts))

        if monster.description:
            from ui.rich_text_utils import render_description_blocks
            holder = ctk.CTkFrame(self._body, fg_color="transparent")
            holder.pack(fill="x", anchor="w", pady=(12, 0))
            render_description_blocks(holder, monster.description, self.theme)

        if monster.source:
            source_text = f"Source: {monster.source}"
            if not monster.is_official:
                source_text += " (Unofficial)"
            ctk.CTkLabel(self._body, text=source_text, font=ui_font("small"),
                         text_color=muted).pack(anchor="w", pady=(14, 0))


class CollapsibleMonsterCard(ctk.CTkFrame):
    """A stat block under a header (toggle, name, Edit) that can be collapsed -
    the form used for the creatures on a spell's page."""

    def __init__(self, parent, monster: Monster,
                 on_edit: Optional[Callable[[Monster], None]] = None, collapsed: bool = False):
        super().__init__(parent, corner_radius=8)
        theme = get_theme_manager()
        self._monster = monster
        self._collapsed = collapsed

        container = ctk.CTkFrame(self, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
        container.pack(fill="both", expand=True, padx=2, pady=2)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))
        self.toggle_btn = ctk.CTkButton(
            header, text="▶" if collapsed else "▼", width=24, height=24,
            fg_color="transparent", hover_color=("gray70", "gray30"), command=self.toggle)
        self.toggle_btn.pack(side="left", padx=(0, 5))
        ctk.CTkLabel(header, text=monster.name, font=ui_font("heading", bold=True),
                     anchor="w").pack(side="left", fill="x", expand=True)
        if on_edit:
            ctk.CTkButton(header, text="Edit", width=50, height=24, font=ui_font("small"),
                          command=lambda: on_edit(self._monster)).pack(side="right", padx=2)

        self.content = MonsterStatBlock(container, monster, bg_key="bg_secondary", show_name=False)
        if not collapsed:
            self.content.pack(fill="x", padx=10, pady=(0, 10))

    def toggle(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self.content.pack_forget()
        else:
            self.content.pack(fill="x", padx=10, pady=(0, 10))
        self.toggle_btn.configure(text="▶" if self._collapsed else "▼")
