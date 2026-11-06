"""
Stat block widgets for D&D Spellbook Application.

MonsterStatBlock draws one monster's stat block; it is shared by the Monsters
collection page, the spell page (the creatures a spell summons) and the object
link popup. CollapsibleMonsterCard wraps it in a header with a collapse toggle
and an optional Edit button, for stacking several on the spell page.
"""

import customtkinter as ctk
from typography import ui_font
from typing import Callable, Dict, List, Optional

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
        self._compare: Optional[Dict[str, int]] = None   # metric -> -1 better / 1 worse (monster_compare.py)
        self._other: Optional[Monster] = None
        if monster is not None:
            self.show_monster(monster)

    # ----- building blocks -----

    def _text(self, text: str, size: int = 13, pady=(1, 1)):
        from ui.rich_text_utils import DynamicText, render_description_blocks
        if "\n|" in "\n" + text:                        # a feature with a table: draw it as one
            holder = ctk.CTkFrame(self._body, fg_color="transparent")
            holder.pack(fill="x", anchor="w", pady=pady)
            render_description_blocks(holder, text, self.theme, bg_color=self._bg_key, font_size=size, pady=(0, 0))
            return holder
        dt = DynamicText(self._body, self.theme, font_size=size, bg_color=self._bg_key)
        dt.set_text(text)
        dt.pack(fill="x", anchor="w", pady=pady)
        return dt

    def _line(self, label: str, value: str, metric: str = ""):
        if value:
            dt = self._text(f"**{label}** {value}")
            self._mark(dt, metric)

    # ----- compare mode -----

    def _compare_colour(self, metric: str) -> Optional[str]:
        result = (self._compare or {}).get(metric, 0)
        if not result:
            return None
        return self.theme.get_current_color("compare_better" if result < 0 else "compare_worse")

    def _none_if_compared(self, metric: str) -> str:
        """ "None" for an empty line the other monster has, so the difference shows in compare mode."""
        return "None" if (self._compare or {}).get(metric) else ""

    def _mark(self, dt, metric: str, pattern: Optional[str] = None):
        """Colour a line (or the part matching ``pattern``) better / worse in compare mode."""
        colour = self._compare_colour(metric) if metric else None
        widget = getattr(dt, "text_widget", None)
        if colour is None or widget is None:
            return
        tag = f"cmp_{metric}"
        widget.tag_configure(tag, foreground=colour)
        widget.tag_raise(tag)
        content = widget.get("1.0", "end-1c")
        if pattern is None:
            widget.tag_add(tag, "1.0", "end-1c")
            return
        import re
        for m in re.finditer(pattern, content):
            widget.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def _comparison_box(self, monster: Monster):
        """The numbers that aren't lines of a stat block: damage per round, attack bonus, save DC, legendary."""
        import monster_compare as mc
        mine = mc.monster_numbers(monster)
        theirs = mc.monster_numbers(self._other)
        box = ctk.CTkFrame(self._body, corner_radius=8, fg_color=self._shade('text_primary', 0.08))
        box.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(box, text=f"Compared with {self._other.name}", font=ui_font("body", bold=True),
                     anchor="w").grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(6, 2))
        muted = self.theme.get_text_secondary()
        row = 1
        for metric in mc.METRICS:
            if not metric.extra or (not mine[metric.key] and not theirs[metric.key]):
                continue
            colour = self._compare_colour(metric.key) or self.theme.get_current_color('text_primary')
            ctk.CTkLabel(box, text=metric.label, font=ui_font("body"), anchor="w").grid(
                row=row, column=0, sticky="w", padx=(10, 12))
            ctk.CTkLabel(box, text=mc.format_number(metric.key, mine[metric.key]), text_color=colour,
                         font=ui_font("body", bold=True), anchor="w").grid(row=row, column=1, sticky="w")
            ctk.CTkLabel(box, text=f"vs {mc.format_number(metric.key, theirs[metric.key])}", text_color=muted,
                         font=ui_font("small"), anchor="w").grid(row=row, column=2, sticky="w", padx=(8, 10))
            row += 1
        ctk.CTkLabel(box, text="Damage per round: the Multiattack or the best single action, on average.",
                     font=ui_font("small"), text_color=muted, anchor="w", justify="left", wraplength=360).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=10, pady=(2, 6))

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
        """The six abilities. Each is four small boxes - name, score, modifier, save -
        shaded differently so they read as separate cells. They sit three to a row when
        there is room and reflow to two or one when the panel is narrow."""
        # name box picks up the accent colour; the number boxes step from light to darker
        shades = (self._shade('accent_primary', 0.55), self._shade('text_primary', 0.20),
                  self._shade('text_primary', 0.11), self._shade('text_primary', 0.16))
        table = ctk.CTkFrame(self._body, fg_color="transparent")
        table.pack(anchor="w", pady=(8, 8))
        muted = self.theme.get_text_secondary()
        box = dict(width=40, height=26, corner_radius=4)
        group_width = 4 * (box["width"] + 2) + 14      # four boxes plus the gap before the next group

        groups = []
        for row in ABILITY_ROWS:
            for ability in row:
                group = ctk.CTkFrame(table, fg_color="transparent")
                groups.append(group)
                proficient = monster.saving_throws.is_proficient(ability)
                for offset, text in ((2, "MOD"), (3, "SAVE")):
                    ctk.CTkLabel(group, text=text, font=ui_font("small", 9), text_color=muted, height=14
                                 ).grid(row=0, column=offset)
                cells = (
                    (AbilityScore.short_name(ability), ui_font("body", bold=True)),
                    (str(monster.ability_scores.get(ability)), ui_font("body", 13)),
                    (signed(monster.get_modifier(ability)), ui_font("body", 13)),
                    (signed(monster.get_save_bonus(ability)),
                     ui_font("body", 13, bold=proficient)),
                )
                name = ability.name.lower()
                colours = (None, self._compare_colour(f"score_{name}"), self._compare_colour(f"score_{name}"),
                           self._compare_colour(f"save_{name}"))
                for offset, ((text, font), shade, colour) in enumerate(zip(cells, shades, colours)):
                    extra = {"text_color": colour} if colour else {}
                    if colour:
                        font = ui_font("body", 13, bold=True)
                    ctk.CTkLabel(group, text=text, font=font, fg_color=shade, **box, **extra).grid(
                        row=1, column=offset, padx=1, pady=1)

        per_row = [0]

        def layout(_event=None):
            from ui.rich_text_utils import logical_width
            width = logical_width(self._body)
            if width <= 1 and per_row[0]:
                return  # not laid out yet; keep what we have
            count = 3 if width <= 1 else max(1, min(3, width // group_width))
            if count == per_row[0]:
                return
            per_row[0] = count
            for i, group in enumerate(groups):
                group.grid(row=i // count, column=i % count, sticky="w",
                           padx=(0 if i % count == 0 else 14, 0), pady=(4 if i >= count else 0, 0))
        layout()
        self._body.bind("<Configure>", layout, add="+")

    # ----- content -----

    def refresh(self):
        """Redraw (e.g. after a theme change)."""
        if self._monster is not None:
            self.show_monster(self._monster, self._other)

    def show_monster(self, monster: Monster, compare_with: Optional[Monster] = None):
        """Draw ``monster``; with ``compare_with``, its numbers are coloured better or worse than that one's."""
        self._monster = monster
        self._other = compare_with
        if compare_with is not None:
            import monster_compare as mc
            self._compare = mc.compare_monsters(monster, compare_with)
        else:
            self._compare = None
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

        if self._other is not None:
            self._comparison_box(monster)

        core = f"**AC** {monster.display_ac()}"
        if monster.show_initiative:
            core += f"      **Initiative** {monster.display_initiative()}"
        dt = self._text(core)
        self._mark(dt, "ac", r"^AC [^ ]*(?: \([^)]*\))?")
        self._mark(dt, "initiative", r"Initiative .*$")
        self._line("HP", monster.display_hp(), "hp")
        self._line("Speed", monster.display_speed(), "speed")
        self._ability_table(monster)

        self._line("Skills", monster.display_skills(), "skills")
        self._line("Vulnerabilities", monster.display_vulnerabilities() or self._none_if_compared("vulnerabilities"), "vulnerabilities")
        self._line("Resistances", monster.display_resistances() or self._none_if_compared("resistances"), "resistances")
        self._line("Immunities", monster.display_immunities() or self._none_if_compared("immunities"), "immunities")
        self._line("Senses", monster.display_senses(), "senses")
        self._line("Languages", monster.display_languages(), "languages")
        self._line("Gear", monster.display_gear())
        self._line("CR", monster.display_cr().removeprefix("CR "), "cr")

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
