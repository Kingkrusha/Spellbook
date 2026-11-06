"""
Monster View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of monsters with a stat block panel,
laid out the same way as the Spells/Feats/Magic Items pages.
"""

from ui.window_utils import center_on_parent
import customtkinter as ctk
from typography import ui_font
import tkinter as tk
from dataclasses import replace
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

from character_sheet import AbilityScore, AbilityScores, SavingThrows, Skill, SkillProficiencies
from monster import (
    Monster, CR_OPTIONS, SPEED_TYPES, cr_to_number, get_monster_manager, normalize_cr,
    proficiency_bonus_for_cr, sense_kind,
)
from settings import get_settings_manager
from stat_block import StatBlockFeature
from theme import get_theme_manager
from ui.filter_widgets import SourceFilterDialog, SourceFilterMode, TagFilterDialog, TagFilterMode
from ui.monster_stat_block import MonsterStatBlock, signed as _signed
from ui.bulk_actions import BulkActionsMixin
from ui.collection_page import CollectionPageMixin
from ui.virtual_list import VirtualListPanel
from ui.editor_host import DialogWindow, EditorBody, EmbeddedWindow
from ui.collapsible import CollapsibleSection
from ui.menu_button import MenuButton
from ui.monster_features import StatFeatureList
from ui.tooltip import HoverTooltip
import monster_rules as MR

ALIGNMENT_OPTIONS = [
    "Unaligned", "Any Alignment", "Lawful Good", "Neutral Good", "Chaotic Good",
    "Lawful Neutral", "Neutral", "Chaotic Neutral", "Lawful Evil", "Neutral Evil", "Chaotic Evil",
]

# Movement filter choices (a monster "has" Hover when its flying speed hovers).
MOVEMENT_OPTIONS = ["Burrow", "Climb", "Fly", "Hover", "Swim"]

# Skill / initiative proficiency levels, as stored (0, 1, 2) and as shown.
PROFICIENCY_LABELS = ["None", "Proficient", "Expertise"]

SORT_OPTIONS = {
    "Name (A-Z)": (lambda m: m.name.lower(), False),
    "CR (low to high)": (lambda m: (cr_to_number(m.challenge_rating), m.name.lower()), False),
    "CR (high to low)": (lambda m: (cr_to_number(m.challenge_rating), m.name.lower()), True),
    "HP (high to low)": (lambda m: (m.hp, m.name.lower()), True),
    "AC (high to low)": (lambda m: (m.ac, m.name.lower()), True),
}

def movement_kinds(monster: Monster) -> List[str]:
    """The MOVEMENT_OPTIONS a monster has (its non-walking speeds, plus Hover)."""
    kinds = [kind.capitalize() for kind in SPEED_TYPES
             if kind != "walk" and monster.speeds.get(kind, 0) > 0]
    if monster.can_hover and monster.speeds.get("fly", 0) > 0:
        kinds.append("Hover")
    return kinds


def _csv(text: str) -> List[str]:
    """Split a comma-separated field, keeping "Primordial (Auran, Terran)" whole."""
    parts, depth, current = [], 0, ""
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth <= 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    return [part.strip() for part in parts if part.strip()]


class MonsterListPanel(VirtualListPanel):
    """The virtualized, selectable list of monsters."""

    TITLE = "Monsters"
    NOUN = "monster"

    def row_text(self, monster: Monster) -> str:
        name = f"* {monster.name}" if monster.is_custom else monster.name
        return f"{name}  (CR {monster.cr_label()})"

    def set_monsters(self, monsters: List[Monster], reset_scroll: bool = True):
        self.set_items(monsters, reset_scroll)

    def get_selected_monster(self) -> Optional[Monster]:
        return self.get_selected()

    def select_monster(self, name: str) -> bool:
        return self.select_by_name(name)


class MonsterDetailPanel(ctk.CTkFrame):
    """Panel showing the selected monster's stat block (see MonsterStatBlock)."""

    def __init__(self, parent):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)
        self._placeholder = ctk.CTkLabel(self.scroll_frame, text="Select a monster",
                                         font=ui_font("title", bold=True))
        # the monster's picture sits beside its stat block, like a page of a bestiary
        from ui.content_image import ContentImage
        self.content_image = ContentImage(self.scroll_frame, "monsters", side=220)
        self._stat_block = MonsterStatBlock(self.scroll_frame)
        self.show_monster(None)
        self.theme.add_listener(self._on_theme_changed)

    def _on_theme_changed(self):
        if not self.winfo_exists():
            return
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._stat_block.refresh()

    def show_monster(self, monster: Optional[Monster]):
        if monster is None:
            self._stat_block.pack_forget()
            self.content_image.pack_forget()
            self.content_image.show(None)
            box = getattr(self, "_extra_fields_box", None)
            if box is not None:
                box.show(None)
            self._placeholder.pack(anchor="w")
        else:
            self._placeholder.pack_forget()
            self._stat_block.pack_forget()
            self.content_image.pack_forget()
            # the fields the user added to Monsters, full width under the stat block (custom_collections.py);
            # packed before the picture and the stat block so it gets the whole bottom edge
            from ui.extra_fields import show_extra_fields
            show_extra_fields(self, "monsters", monster.name, side="bottom")
            self.content_image.show(monster.name)
            self.content_image.pack(side="right", anchor="n", padx=(10, 0))
            self._stat_block.show_monster(monster)
            self._stat_block.pack(side="left", fill="x", expand=True, anchor="n")


class MonsterEditorBody(EditorBody):
    """The monster form (see ui/editor_host.py). It works like a character sheet: the numbers that follow from other
    numbers are worked out for you and say where they come from when you hover them - proficiency bonus from the CR,
    hit die from the size, hit points from the hit dice and Constitution, saves, skills and initiative from the scores,
    and attacks and saving throw effects from a core stat plus the proficiency bonus."""

    def __init__(self, parent, title: str, monster: Optional[Monster] = None,
                 prefill: Optional[Monster] = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("720x900")
        self.minsize(640, 600)
        self.transient(parent)
        self.grab_set()

        self.theme = get_theme_manager()
        self.manager = get_monster_manager()
        self.result: Optional[Monster] = None
        self._editing = monster
        self._chips: Dict[str, tuple] = {}            # key -> (label, tooltip) for the derived numbers
        self._tips: Dict[str, HoverTooltip] = {}
        self._sections: List[CollapsibleSection] = []
        self._ready = False

        self._create_widgets()
        source = monster or prefill
        if source:
            self._populate(source)
        self._ready = True
        self._update_preview()

        center_on_parent(self, parent, clamp=True)

    # ----- layout -----

    def _section(self, title: str, open: bool = True, note: str = "") -> CollapsibleSection:
        section = CollapsibleSection(self._scroll, title, open=open, note=note)
        section.pack(fill="x")
        self._cur = section.body
        self._sections.append(section)
        return section

    def _row(self) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._cur, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        return row

    def _labeled(self, parent, text: str, make, padx=(0, 12)):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", padx=padx, anchor="n")
        ctk.CTkLabel(col, text=text, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        widget = make(col)
        widget.pack(anchor="w")
        return widget

    def _entry(self, parent, text: str, width: int, placeholder: str = ""):
        entry = self._labeled(parent, text, lambda p: ctk.CTkEntry(
            p, width=width, placeholder_text=placeholder))
        entry.bind("<KeyRelease>", lambda _e: self._update_preview())
        return entry

    def _combo(self, parent, text: str, values, width: int, default: str, readonly=False, command=None):
        var = ctk.StringVar(value=default)
        self._labeled(parent, text, lambda p: ctk.CTkComboBox(
            p, width=width, values=list(values), variable=var,
            state="readonly" if readonly else "normal",
            command=command or (lambda _v: self._update_preview())))
        return var

    def _wide_entry(self, text: str, placeholder: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(self._cur, text=text, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        entry = ctk.CTkEntry(self._cur, placeholder_text=placeholder)
        entry.pack(fill="x", pady=(0, 8))
        return entry

    def _chip(self, parent, key: str, side: str = "left", padx=(0, 0), anchor=None) -> tk.Label:
        """A small label for a worked-out number; hover it to see where the number comes from. (A plain tk.Label:
        there are dozens of these and a rounded CTkLabel costs several times as much to create.)"""
        label = tk.Label(parent, text="", font=ui_font("body", 12, bold=True), padx=8, pady=2, bd=0)
        self._paint_chip(label)
        tip = HoverTooltip(label, "")
        self._chips[key] = (label, tip)
        if anchor:
            label.pack(side=side, padx=padx, anchor=anchor)
        else:
            label.pack(side=side, padx=padx)
        return label

    def _paint_chip(self, label: tk.Label):
        c = self.theme.get_current_color
        label.configure(bg=c("bg_secondary"), fg=c("text_primary"))

    def _set_chip(self, key: str, text: str, tip: str):
        label, tooltip = self._chips[key]
        label.configure(text=text)
        self._paint_chip(label)                      # follows a theme change at the next update
        tooltip.update_text(tip)

    def _create_widgets(self):
        from ui.rich_text_utils import RichTextEditor

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(12, 0))
        self._scroll = scroll
        mgr = self.manager
        stats = self._stats

        # ---- Identity
        self._section("Identity")
        self.name_entry = self._wide_entry("Name *")
        self.epithet_entry = self._wide_entry("Epithet", "A short tagline shown under the name")
        row = self._row()
        self.size_var = self._combo(row, "Size", mgr.get_all_sizes(), 120, "Medium", readonly=True)
        self.type_var = self._combo(row, "Creature Type", mgr.get_all_types(), 160, "", command=lambda _v: None)
        self.subtype_entry = self._entry(row, "Subtype", 150, "e.g. Chromatic")
        row = self._row()
        self.alignment_var = self._combo(row, "Alignment", ALIGNMENT_OPTIONS, 170, "Unaligned",
                                         command=lambda _v: None)
        self.source_entry = self._entry(row, "Source", 250, "e.g. Homebrew")

        # ---- Combat
        self._section("Combat")
        row = self._row()
        self.ac_entry = self._entry(row, "AC", 60)
        self.cr_var = self._combo(row, "CR", CR_OPTIONS, 80, "0", readonly=True)
        self.init_var = self._combo(row, "Initiative", PROFICIENCY_LABELS, 120, PROFICIENCY_LABELS[0],
                                    readonly=True)
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", anchor="n", padx=(4, 0))
        ctk.CTkLabel(col, text="Worked out", font=ui_font("small"), text_color=self.theme.get_text_secondary()
                     ).pack(anchor="w")
        chips = ctk.CTkFrame(col, fg_color="transparent")
        chips.pack(anchor="w", pady=(2, 0))
        self._chip(chips, "prof", padx=(0, 6))
        self._chip(chips, "init")
        row = self._row()
        self.hit_count_entry = self._entry(row, "Hit dice", 64, "e.g. 6")
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", anchor="n", padx=(0, 12))
        ctk.CTkLabel(col, text="Hit die", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self._chip(col, "hitdie", anchor="w")
        self.hp_entry = self._entry(row, "HP", 70)
        self.hit_dice_entry = self._entry(row, "Hit dice formula", 150, "e.g. 18d12 + 90")
        self.hp_manual_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text="Set HP by hand", variable=self.hp_manual_var,
                        command=self._update_preview).pack(side="left", pady=(22, 0))
        self._tips["hp"] = HoverTooltip(self.hp_entry, "")
        self._tips["hp_count"] = HoverTooltip(self.hit_count_entry, "")
        ctk.CTkLabel(self._cur, anchor="w", justify="left", text_color=self.theme.get_text_secondary(),
                     font=ui_font("small"), wraplength=620,
                     text="Hit points are the number of hit dice times (half the die + a half + Constitution modifier); "
                          "the die comes from the size. Tick \"Set HP by hand\" to type hit points and a formula yourself."
                     ).pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(self._cur, text="Speed (feet; leave blank for none)",
                     font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        row = self._row()
        self.speed_entries: Dict[str, ctk.CTkEntry] = {
            kind: self._entry(row, kind.capitalize(), 64) for kind in SPEED_TYPES}
        self.hover_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row, text="Hover", variable=self.hover_var,
                        command=self._update_preview).pack(side="left", pady=(22, 0))

        # ---- Ability scores, saves
        self._section("Ability Scores and Saving Throws")
        row = self._row()
        self.ability_entries: Dict[AbilityScore, ctk.CTkEntry] = {}
        self.save_vars: Dict[AbilityScore, ctk.BooleanVar] = {}
        for ability in AbilityScore:
            short = AbilityScore.short_name(ability)
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", padx=(0, 12), anchor="n")
            ctk.CTkLabel(col, text=short, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
            entry = ctk.CTkEntry(col, width=64)
            entry.insert(0, "10")
            entry.pack(anchor="w")
            entry.bind("<KeyRelease>", lambda _e: self._update_preview())
            self._chip(col, f"mod_{short}", anchor="w")
            var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(col, text="Save", variable=var, width=60,
                            command=self._update_preview).pack(anchor="w", pady=(4, 0))
            self._chip(col, f"save_{short}", anchor="w")
            self.ability_entries[ability] = entry
            self.save_vars[ability] = var

        # ---- Skills
        self._section("Skill Proficiencies", open=False)
        grid = ctk.CTkFrame(self._cur, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 8))
        self.skill_vars: Dict[Skill, ctk.StringVar] = {}
        for index, skill in enumerate(Skill):
            r, c = divmod(index, 2)
            ctk.CTkLabel(grid, text=skill.display_name, anchor="w", width=110
                         ).grid(row=r, column=c * 3, sticky="w", padx=(0, 6), pady=2)
            var = ctk.StringVar(value=PROFICIENCY_LABELS[0])
            MenuButton(grid, PROFICIENCY_LABELS, var, width=110, height=26,
                       command=lambda _v: self._update_preview()
                       ).grid(row=r, column=c * 3 + 1, sticky="w", padx=(0, 6), pady=2)
            holder = ctk.CTkFrame(grid, fg_color="transparent")
            holder.grid(row=r, column=c * 3 + 2, sticky="w", padx=(0, 18), pady=2)
            self._chip(holder, f"skill_{skill.name}")
            self.skill_vars[skill] = var

        # ---- Defenses, senses, languages
        self._section("Defenses, Senses and Languages (comma-separated)")
        self.vulnerabilities_entry = self._wide_entry("Damage Vulnerabilities", "e.g. Fire")
        self.resistances_entry = self._wide_entry("Damage Resistances", "e.g. Cold, Necrotic")
        self.damage_immunities_entry = self._wide_entry("Damage Immunities", "e.g. Poison")
        self.condition_immunities_entry = self._wide_entry("Condition Immunities", "e.g. Poisoned")
        self.senses_entry = self._wide_entry(
            "Senses (passive Perception is added automatically)", "e.g. Darkvision 60 ft., Blindsight 30 ft.")
        row = ctk.CTkFrame(self._cur, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        self._chip(row, "passive")
        self.languages_entry = self._wide_entry("Languages", "e.g. Common, Draconic")
        self.gear_entry = self._wide_entry("Gear", "e.g. Chain Mail, Longsword")

        # ---- Traits, actions
        self._section("Traits, Actions and Reactions")
        attack_hint = ("Choose Attack or Saving throw to work an entry out from the stats: the hit bonus is a core stat "
                       "plus the proficiency bonus, the damage adds the stat's modifier, the DC is 8 + proficiency + a stat.")
        self.traits_editor = StatFeatureList(self._cur, "Traits", stats=stats, on_change=self._update_preview)
        self.actions_editor = StatFeatureList(self._cur, "Actions", attack_hint, stats=stats, builder=True,
                                              on_change=self._update_preview)
        self.bonus_editor = StatFeatureList(self._cur, "Bonus Actions", stats=stats, builder=True,
                                            on_change=self._update_preview)
        self.reactions_editor = StatFeatureList(self._cur, "Reactions", stats=stats, builder=True,
                                                on_change=self._update_preview)
        for editor in (self.traits_editor, self.actions_editor, self.bonus_editor, self.reactions_editor):
            editor.pack(fill="x", pady=(0, 10))

        self.sec_legendary = self._section("Legendary and Lair Actions", open=False)
        self.legendary_editor = StatFeatureList(self._cur, "Legendary Actions", stats=stats, builder=True,
                                                on_change=self._update_preview)
        self.legendary_editor.pack(fill="x", pady=(0, 10))
        row = self._row()
        self.legendary_uses_entry = self._entry(row, "Legendary Action Uses", 150)
        self.legendary_uses_entry.insert(0, "3")
        self.legendary_uses_lair_entry = self._entry(row, "Uses in Lair", 110, "blank = same")
        self.legendary_intro_entry = self._wide_entry(
            "Legendary Actions Intro (blank = standard text)")
        self.lair_editor = StatFeatureList(self._cur, "Lair Actions", stats=stats, on_change=self._update_preview)
        self.lair_editor.pack(fill="x", pady=(0, 10))
        self.lair_intro_entry = self._wide_entry("Lair Actions Intro (optional)")
        self.lair_xp_entry = self._wide_entry(
            "XP in Lair (blank = the next CR's XP)", "e.g. 15000")

        # ---- Text overrides
        self.sec_overrides = self._section("Text overrides", open=False)
        ctk.CTkLabel(
            self._cur, anchor="w", justify="left", text_color=self.theme.get_text_secondary(),
            text="Shown instead of the number, for values that scale (e.g. a summoned creature's \"11 + the level of "
                 "the spell\"). Leave blank normally.",
            wraplength=620).pack(fill="x", pady=(0, 4))
        row = self._row()
        self.ac_text_entry = self._entry(row, "AC text", 170, "e.g. 11 + the spell's level")
        self.hp_text_entry = self._entry(row, "HP text", 250, "e.g. 30 + 10 per spell level above 3rd")
        row = self._row()
        self.speed_text_entry = self._entry(row, "Speed text", 250)
        self.cr_text_entry = self._entry(row, "CR text", 170, "e.g. None (PB = yours)")
        self.skills_text_entry = self._entry(row, "Skills text", 200, "e.g. Stealth +4 (+6 in snake form)")
        self.show_initiative_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row, text="Show initiative", variable=self.show_initiative_var,
                        command=self._update_preview).pack(side="left", pady=(22, 0))

        # ---- Summoned creature
        self.sec_summon = self._section("Spell Summon", open=False)
        self.spell_only_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self._cur, variable=self.spell_only_var,
            text="Spell-only summon (hidden from the Monsters collection unless enabled in Settings)"
        ).pack(anchor="w", pady=(0, 8))
        self.spell_entry = self._wide_entry("Summoned by spell", "Spell name (optional)")

        # ---- Lore
        self.sec_lore = self._section("Habitat, Treasure and Description", open=False)
        self.habitat_entry = self._wide_entry("Habitat", "e.g. Forest, Swamp")
        self.treasure_entry = self._wide_entry("Treasure", "e.g. Arcana, Individual")
        ctk.CTkLabel(self._cur, text="Description", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.desc_text = ctk.CTkTextbox(self._cur, height=200)
        self._rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        self._rich_editor.create_toolbar(self._cur).pack(fill="x", pady=(5, 5))
        self.desc_text.pack(fill="x", pady=(0, 10))

        # Footer: derived values + buttons (outside the scroll area, always visible)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=12)
        self.preview_label = ctk.CTkLabel(footer, text="", font=ui_font("body"),
                                          text_color=self.theme.get_text_secondary(),
                                          anchor="w", justify="left")
        self.preview_label.pack(side="left")
        ctk.CTkButton(footer, text="Cancel", width=100, fg_color="transparent", border_width=1,
                      command=self._finish).pack(side="right", padx=(5, 0))
        ctk.CTkButton(footer, text="Save", width=100,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      command=self._save).pack(side="right")

    # ----- what follows from what -----

    def _scores(self) -> Dict[str, int]:
        scores = {}
        for ability, entry in self.ability_entries.items():
            try:
                value = int(entry.get().strip())
            except ValueError:
                value = 10
            scores[AbilityScore.short_name(ability)] = max(1, min(30, value))
        return scores

    def _stats(self) -> MR.Stats:
        """Proficiency bonus (from the CR) and the six modifiers: what an attack is worked out from."""
        cr = normalize_cr(self.cr_var.get()) if hasattr(self, "cr_var") else "0"
        mods = {a: MR.modifier(s) for a, s in self._scores().items()} if hasattr(self, "ability_entries") \
            else {a: 0 for a in MR.ABILITIES}
        return MR.Stats(prof=proficiency_bonus_for_cr(cr), mods=mods, cr=cr)

    @staticmethod
    def _set_entry(entry: ctk.CTkEntry, text: str):
        entry.configure(state="normal")
        entry.delete(0, "end")
        if text:
            entry.insert(0, text)

    def _hit_count(self) -> int:
        try:
            return max(0, int(self.hit_count_entry.get().strip() or 0))
        except ValueError:
            return 0

    def _sync_hp(self):
        """Hit points and the hit dice formula follow the hit dice, size and Constitution unless set by hand."""
        manual = self.hp_manual_var.get()
        stats = self._stats()
        die = MR.hit_die_for_size(self.size_var.get())
        if not manual:
            count = self._hit_count()
            self._set_entry(self.hp_entry, str(MR.hit_points(count, die, stats.mods["CON"])) if count else "")
            self._set_entry(self.hit_dice_entry, MR.hit_dice_text(count, die, stats.mods["CON"]))
        self.hp_entry.configure(state="normal" if manual else "disabled")
        self.hit_dice_entry.configure(state="normal" if manual else "disabled")
        self.hit_count_entry.configure(state="disabled" if manual else "normal")

    def _update_derived(self):
        stats = self._stats()
        mods, prof, cr = stats.mods, stats.prof, stats.cr
        scores = self._scores()
        size = self.size_var.get() or "Medium"
        die = MR.hit_die_for_size(size)
        sg = MR.signed
        self._set_chip("prof", f"Proficiency {sg(prof)}",
                       f"Proficiency bonus is based off of CR (CR {cr} gives {sg(prof)}).")
        level = max(0, min(2, PROFICIENCY_LABELS.index(self.init_var.get()) if self.init_var.get() in
                           PROFICIENCY_LABELS else 0))
        init = mods["DEX"] + prof * level
        self._set_chip("init", f"Initiative {sg(init)} ({10 + init})",
                       f"{sg(mods['DEX'])} from Dexterity" + (f", {sg(prof * level)} from proficiency"
                                                               + (" (expertise: twice the bonus)" if level == 2 else "")
                                                               if level else "") + f". The fixed score is 10 + {sg(init)}.")
        self._set_chip("hitdie", f"d{die}", f"Hit die is based off of size ({size} gives a d{die}).")
        con, count = mods["CON"], self._hit_count()
        manual = self.hp_manual_var.get()
        auto_hp = MR.hit_points(count, die, con) if count else 0
        if manual:
            hp_tip = (f"Set by hand. Worked out from the hit dice it would be {auto_hp}." if count
                      else "Set by hand.")
        elif count:
            hp_tip = (f"{count} hit dice (a d{die} for a {size} creature), each averaging {die / 2 + 0.5:g} "
                      f"plus {sg(con)} from Constitution = {auto_hp} hit points.")
        else:
            hp_tip = "Enter the number of hit dice: hit points follow from them, the size and Constitution."
        self._tips["hp"].update_text(hp_tip)
        self._tips["hp_count"].update_text(hp_tip)
        for ability in AbilityScore:
            short = AbilityScore.short_name(ability)
            name = MR.ABILITY_NAMES[short]
            self._set_chip(f"mod_{short}", sg(mods[short]),
                           f"Modifier is (score - 10) / 2, rounded down: ({scores[short]} - 10) / 2 = {sg(mods[short])}.")
            proficient = self.save_vars[ability].get()
            total = mods[short] + (prof if proficient else 0)
            self._set_chip(f"save_{short}", f"Save {sg(total)}",
                           f"{sg(mods[short])} from {name}" + (f", {sg(prof)} from proficiency" if proficient
                                                              else " (not proficient)"))
        for skill in Skill:
            lvl = PROFICIENCY_LABELS.index(self.skill_vars[skill].get())
            short = AbilityScore.short_name(skill.ability)
            total = mods[short] + prof * lvl
            note = ("" if not lvl else f", {sg(prof * lvl)} from proficiency" +
                    (" (expertise: twice the bonus)" if lvl == 2 else ""))
            self._set_chip(f"skill_{skill.name}", sg(total), f"{sg(mods[short])} from {MR.ABILITY_NAMES[short]}{note}")
        perception = Skill.PERCEPTION
        plvl = PROFICIENCY_LABELS.index(self.skill_vars[perception].get())
        pp = 10 + mods["WIS"] + prof * plvl
        self._set_chip("passive", f"Passive Perception {pp}",
                       f"10 {sg(mods['WIS'])} from Wisdom" + (f" {sg(prof * plvl)} from proficiency" if plvl else "")
                       + " in Perception. It is added to the senses on its own.")
        for editor in (self.traits_editor, self.actions_editor, self.bonus_editor, self.reactions_editor,
                       self.legendary_editor, self.lair_editor):
            editor.refresh()

    # ----- data in / out -----

    @staticmethod
    def _fill(entry: ctk.CTkEntry, value):
        entry.configure(state="normal")
        entry.delete(0, "end")
        if value not in (None, ""):
            entry.insert(0, str(value))

    def _populate(self, m: Monster):
        self._fill(self.name_entry, m.name)
        self._fill(self.epithet_entry, m.epithet)
        self.size_var.set(m.size)
        self.type_var.set(m.creature_type)
        self._fill(self.subtype_entry, m.creature_subtype)
        self.alignment_var.set(m.alignment)
        self._fill(self.source_entry, m.source)
        self._fill(self.ac_entry, m.ac)
        self.cr_var.set(normalize_cr(m.challenge_rating))
        self.init_var.set(PROFICIENCY_LABELS[max(0, min(2, m.initiative_proficiency))])
        for kind, entry in self.speed_entries.items():
            self._fill(entry, m.speeds.get(kind))
        self.hover_var.set(m.can_hover)
        self._fill(self.ac_text_entry, m.ac_text)
        self._fill(self.hp_text_entry, m.hp_text)
        self._fill(self.speed_text_entry, m.speed_text)
        self._fill(self.cr_text_entry, m.cr_text)
        self._fill(self.skills_text_entry, m.skills_text)
        self.show_initiative_var.set(m.show_initiative)
        self.spell_only_var.set(m.spell_only)
        self._fill(self.spell_entry, m.spell_name)
        for ability in AbilityScore:
            self._fill(self.ability_entries[ability], m.ability_scores.get(ability))
            self.save_vars[ability].set(m.saving_throws.is_proficient(ability))
        for skill in Skill:
            self.skill_vars[skill].set(PROFICIENCY_LABELS[m.skills.get(skill)])
        for entry, values in (
                (self.vulnerabilities_entry, m.damage_vulnerabilities),
                (self.resistances_entry, m.damage_resistances),
                (self.damage_immunities_entry, m.damage_immunities),
                (self.condition_immunities_entry, m.condition_immunities),
                (self.senses_entry, m.senses), (self.languages_entry, m.languages),
                (self.gear_entry, m.gear),
                (self.habitat_entry, m.habitat), (self.treasure_entry, m.treasure)):
            self._fill(entry, ", ".join(values))
        # hit points follow the hit dice when the stored ones do; otherwise they are the author's own
        con = MR.modifier(m.ability_scores.get(AbilityScore.CONSTITUTION))
        parsed = MR.parse_hit_dice(m.hit_dice)
        follows = bool(parsed and not m.hp_text and parsed[1] == MR.hit_die_for_size(m.size)
                       and parsed[2] == parsed[0] * con and m.hp == MR.hit_points(parsed[0], parsed[1], con))
        self.hp_manual_var.set(not follows)
        self._fill(self.hit_count_entry, parsed[0] if parsed else "")
        self._fill(self.hp_entry, m.hp)
        self._fill(self.hit_dice_entry, m.hit_dice)
        for editor, features in (
                (self.traits_editor, m.traits), (self.actions_editor, m.actions),
                (self.bonus_editor, m.bonus_actions), (self.reactions_editor, m.reactions),
                (self.legendary_editor, m.legendary_actions), (self.lair_editor, m.lair_actions)):
            editor.set_features(features)
        self._fill(self.legendary_uses_entry, m.legendary_action_uses)
        self._fill(self.legendary_uses_lair_entry, m.legendary_action_uses_in_lair)
        self._fill(self.legendary_intro_entry, m.legendary_actions_intro)
        self._fill(self.lair_intro_entry, m.lair_actions_intro)
        self._fill(self.lair_xp_entry, m.lair_xp)
        self.desc_text.delete("1.0", "end")
        self.desc_text.insert("1.0", m.description)
        # sections with something in them start open
        self.sec_legendary.set_open(bool(m.legendary_actions or m.lair_actions))
        self.sec_overrides.set_open(bool(m.ac_text or m.hp_text or m.speed_text or m.cr_text or m.skills_text))
        self.sec_summon.set_open(bool(m.spell_only or m.spell_name))
        self.sec_lore.set_open(bool(m.description or m.habitat or m.treasure))
        self.skill_section_open = any(m.skills.get(s) for s in Skill)
        for section in self._sections:
            if section.title == "Skill Proficiencies":
                section.set_open(self.skill_section_open)

    @staticmethod
    def _int(entry: ctk.CTkEntry, label: str, low: int, high: Optional[int] = None,
             blank: Optional[int] = None) -> Optional[int]:
        text = entry.get().strip()
        if not text:
            return blank
        try:
            value = int(text)
        except ValueError:
            raise ValueError(f"{label} must be a whole number.")
        if value < low or (high is not None and value > high):
            bound = f"at least {low}" if high is None else f"between {low} and {high}"
            raise ValueError(f"{label} must be {bound}.")
        return value

    def _collect(self, require_name: bool = True) -> Monster:
        """Build a Monster from the form; raises ValueError with a readable message."""
        name = self.name_entry.get().strip()
        if require_name and not name:
            raise ValueError("Name is required.")
        self._sync_hp()

        speeds = {}
        for kind, entry in self.speed_entries.items():
            feet = self._int(entry, f"{kind.capitalize()} speed", 0)
            if feet is not None:
                speeds[kind] = feet

        scores = AbilityScores()
        saves = SavingThrows()
        for ability in AbilityScore:
            scores.set(ability, self._int(self.ability_entries[ability],
                                          AbilityScore.short_name(ability), 1, 30, blank=10))
            saves.set_proficiency(ability, self.save_vars[ability].get())
        skills = SkillProficiencies()
        for skill in Skill:
            skills.set(skill, PROFICIENCY_LABELS.index(self.skill_vars[skill].get()))

        for label, editor in (("Traits", self.traits_editor), ("Actions", self.actions_editor),
                              ("Bonus Actions", self.bonus_editor), ("Reactions", self.reactions_editor),
                              ("Legendary Actions", self.legendary_editor),
                              ("Lair Actions", self.lair_editor)):
            if editor.has_unnamed():
                raise ValueError(f"Every entry under {label} needs a name.")

        return Monster(
            name=name,
            epithet=self.epithet_entry.get().strip(),
            size=self.size_var.get() or "Medium",
            creature_type=self.type_var.get().strip(),
            creature_subtype=self.subtype_entry.get().strip(),
            alignment=self.alignment_var.get().strip(),
            ac=self._int(self.ac_entry, "AC", 0, blank=10),
            initiative_proficiency=PROFICIENCY_LABELS.index(self.init_var.get()),
            hp=self._int(self.hp_entry, "HP", 0, blank=1),
            hit_dice=self.hit_dice_entry.get().strip(),
            speeds=speeds,
            can_hover=self.hover_var.get(),
            ac_text=self.ac_text_entry.get().strip(),
            hp_text=self.hp_text_entry.get().strip(),
            speed_text=self.speed_text_entry.get().strip(),
            cr_text=self.cr_text_entry.get().strip(),
            skills_text=self.skills_text_entry.get().strip(),
            show_initiative=self.show_initiative_var.get(),
            ability_scores=scores, saving_throws=saves, skills=skills,
            damage_vulnerabilities=_csv(self.vulnerabilities_entry.get()),
            damage_resistances=_csv(self.resistances_entry.get()),
            damage_immunities=_csv(self.damage_immunities_entry.get()),
            condition_immunities=_csv(self.condition_immunities_entry.get()),
            senses=_csv(self.senses_entry.get()),
            languages=_csv(self.languages_entry.get()),
            gear=_csv(self.gear_entry.get()),
            challenge_rating=normalize_cr(self.cr_var.get()),
            lair_xp=self._int(self.lair_xp_entry, "XP in Lair", 0),
            traits=self.traits_editor.get_features(),
            actions=self.actions_editor.get_features(),
            bonus_actions=self.bonus_editor.get_features(),
            reactions=self.reactions_editor.get_features(),
            legendary_actions=self.legendary_editor.get_features(),
            legendary_action_uses=self._int(self.legendary_uses_entry, "Legendary Action Uses", 0, blank=3),
            legendary_action_uses_in_lair=self._int(self.legendary_uses_lair_entry, "Uses in Lair", 0),
            legendary_actions_intro=self.legendary_intro_entry.get().strip(),
            lair_actions=self.lair_editor.get_features(),
            lair_actions_intro=self.lair_intro_entry.get().strip(),
            habitat=_csv(self.habitat_entry.get()),
            treasure=_csv(self.treasure_entry.get()),
            description=self.desc_text.get("1.0", "end-1c").strip(),
            source=self.source_entry.get().strip(),
            # Editing keeps the monster's official/custom status (an official
            # summon can be tweaked from its spell's page); anything new is custom.
            is_official=self._editing.is_official if self._editing else False,
            is_custom=self._editing.is_custom if self._editing else True,
            spell_only=self.spell_only_var.get(),
            spell_name=self.spell_entry.get().strip(),
        )

    def _update_preview(self):
        """Work out every derived number, and show the ones that follow from CR and the ability scores."""
        if not getattr(self, "_ready", False):
            return
        self._sync_hp()
        self._update_derived()
        try:
            m = self._collect(require_name=False)
        except ValueError:
            self.preview_label.configure(text="")
            return
        self.preview_label.configure(
            text=(f"Proficiency {_signed(m.proficiency_bonus)}  •  Initiative {m.display_initiative()}"
                  f"  •  Passive Perception {m.get_passive_perception()}  •  XP {m.xp:,}"))

    def build_result(self, strict: bool = True) -> Monster:
        """The monster the form describes (strict: ValueError if incomplete; otherwise gaps are filled in)."""
        monster = self._collect(require_name=strict)
        if strict and not self.EMBEDDED and monster.spell_name \
                and self.manager.db.get_spell_id_by_name(monster.spell_name) is None:
            raise ValueError(f"There is no spell named '{monster.spell_name}'.")
        return monster

class MonsterEditorDialog(MonsterEditorBody, DialogWindow):
    """Dialog for creating or editing a monster."""


class MonsterEditorPanel(MonsterEditorBody, EmbeddedWindow):
    """The MonsterEditorDialog form inside the Homebrew Studio."""


class _MultiFilter:
    """A 'pick some values' filter button: opens the shared multi-select dialog and
    remembers the choice. Highlights itself while a selection is active."""

    def __init__(self, view: "MonsterView", parent, title: str, get_values: Callable[[], List[str]],
                 noun: str, width: int = 110, source: bool = False):
        self.view = view
        self.title = title
        self.noun = noun
        self.source = source
        self.get_values = get_values
        self.selected: List[str] = []
        self.mode = SourceFilterMode.INCLUDE if source else TagFilterMode.HAS_ALL
        self._theme = get_theme_manager()
        self.button = ctk.CTkButton(parent, text=f"{title}...", width=width, height=35,
                                    command=self.open)
        self._style()
        self.button.pack(side="left", padx=(0, 8))

    def _style(self):
        theme = self._theme
        active = bool(self.selected)
        if self.source:
            mode = "include" if self.mode == SourceFilterMode.INCLUDE else "exclude"
        else:
            mode = {"has_all": "all", "has_any": "any", "has_none": "none"}[self.mode.value]
        self.button.configure(
            text=f"{self.title} ({len(self.selected)} {mode})" if active else f"{self.title}...",
            fg_color=theme.get_current_color('accent_primary' if active else 'button_normal'),
            hover_color=theme.get_current_color('accent_hover' if active else 'button_hover'),
            text_color=theme.get_current_color('text_primary'))

    def open(self):
        parent = self.view.winfo_toplevel()
        values = self.get_values()
        if self.source:
            dialog = SourceFilterDialog(parent, values, self.selected, self.mode,
                                        empty_message="No sources found in your monsters.")
        else:
            dialog = TagFilterDialog(
                parent, values, self.selected, self.mode,
                window_title=f"Select {self.title}", prompt=f"Select {self.noun} to filter by:",
                noun=self.noun, empty_message=f"No {self.noun} found in your monsters.")
        self.view.wait_window(dialog)
        self.selected, self.mode = dialog.result, dialog.result_mode
        self._style()
        self.view._on_filter_changed(immediate=True)

    def clear(self):
        self.selected = []
        self.mode = SourceFilterMode.INCLUDE if self.source else TagFilterMode.HAS_ALL
        self._style()

    def matches(self, values: List[str]) -> bool:
        """Whether a monster's values satisfy the selection (always True when empty)."""
        if not self.selected:
            return True
        have = {v.lower() for v in values}
        wanted = [s.lower() for s in self.selected]
        if self.source:
            hit = bool(values) and values[0].lower() in wanted
            return hit if self.mode == SourceFilterMode.INCLUDE else not hit
        if self.mode == TagFilterMode.HAS_ALL:
            return all(s in have for s in wanted)
        if self.mode == TagFilterMode.HAS_ANY:
            return any(s in have for s in wanted)
        return not any(s in have for s in wanted)


class MonsterView(BulkActionsMixin, CollectionPageMixin, ctk.CTkFrame):
    """Main view for browsing and managing monsters."""

    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))

        self.monster_manager = get_monster_manager()
        self.settings_manager = get_settings_manager()
        self.character_manager = character_manager
        self.on_back = on_back
        self._all_monsters: List[Monster] = []
        self._search_index: Dict[str, str] = {}
        self._filter_debounce_id: Optional[str] = None
        self._filter_debounce_delay = 150
        self._filters: List[_MultiFilter] = []
        self._listed_spell_only = False

        self._create_widgets()
        self._setup_bulk_actions()
        self._load_monsters()
        self.theme.add_listener(self._on_theme_changed)
        self.settings_manager.add_listener(self._on_settings_changed)

    def _on_settings_changed(self, settings):
        """Turning "Display spell only summons" on or off relists the monsters."""
        if self.winfo_exists() and bool(settings.show_spell_only_summons) != self._listed_spell_only:
            self._load_monsters()

    def _on_theme_changed(self):
        if not self.winfo_exists():
            return
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        if hasattr(self, 'paned'):
            self.paned.configure(bg=self.theme.get_current_color("pane_sash"))
        for f in self._filters:
            f._style()

    # ----- layout -----

    def _create_panes(self):
        self.list_panel = MonsterListPanel(self.paned, on_select=self._on_monster_selected)
        self.detail_panel = MonsterDetailPanel(self.paned)

        self.paned.add(self.list_panel, minsize=280, stretch="always")
        self.paned.add(self.detail_panel, minsize=400, stretch="always")

    def _bar(self, pady=(0, 5)) -> ctk.CTkFrame:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=pady)
        return bar

    def _label(self, parent, text: str):
        ctk.CTkLabel(parent, text=text).pack(side="left", padx=(0, 5))

    def _combo(self, parent, values, default: str, width: int):
        """A read-only filter dropdown; returns (variable, combobox)."""
        var = ctk.StringVar(value=default)
        combo = ctk.CTkComboBox(
            parent, width=width, height=35, values=list(values), variable=var,
            command=lambda _: self._on_filter_changed(immediate=True), state="readonly")
        combo.pack(side="left", padx=(0, 10))
        return var, combo

    def _range_entries(self, parent, label: str, width: int = 60):
        """A 'label: min - max' pair of number entries; returns (min_var, max_var)."""
        self._label(parent, label)
        min_var, max_var = ctk.StringVar(), ctk.StringVar()
        for i, var in enumerate((min_var, max_var)):
            var.trace_add("write", lambda *args: self._on_filter_changed())
            ctk.CTkEntry(parent, width=width, height=35, textvariable=var,
                         placeholder_text="Min" if i == 0 else "Max").pack(side="left", padx=(0, 5))
            if i == 0:
                ctk.CTkLabel(parent, text="-").pack(side="left", padx=(0, 5))
        ctk.CTkFrame(parent, width=10, height=1, fg_color="transparent").pack(side="left")
        return min_var, max_var

    def _multi(self, parent, title, get_values, noun, width=110, source=False) -> _MultiFilter:
        f = _MultiFilter(self, parent, title, get_values, noun, width, source)
        self._filters.append(f)
        return f

    def _create_filter_bar(self):
        theme = self.theme
        mgr = self.monster_manager

        # Row 1: search, type, size, alignment, sort, actions
        bar = self._bar(pady=(10, 5))
        if self.on_back:
            ctk.CTkButton(
                bar, text="← Collections", width=110,
                fg_color=theme.get_current_color('button_normal'),
                hover_color=theme.get_current_color('button_hover'),
                text_color=theme.get_current_color('text_primary'),
                command=self.on_back).pack(side="left", padx=(0, 15))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        ctk.CTkEntry(bar, width=200, height=35, placeholder_text="Search monsters...",
                     textvariable=self.search_var).pack(side="left", padx=(0, 10))

        self._label(bar, "Type:")
        self.type_var, self.type_combo = self._combo(bar, ["All Types"], "All Types", 140)
        self._label(bar, "Size:")
        self.size_var, self.size_combo = self._combo(bar, ["All Sizes"], "All Sizes", 120)
        self._label(bar, "Alignment:")
        self.alignment_var, self.alignment_combo = self._combo(
            bar, ["All Alignments"], "All Alignments", 150)
        self._label(bar, "Sort:")
        self.sort_var, _ = self._combo(bar, SORT_OPTIONS, "Name (A-Z)", 150)

        ctk.CTkButton(
            bar, text="+ Add Monster", width=130, height=35,
            fg_color=theme.get_current_color('accent_primary'),
            hover_color=theme.get_current_color('accent_hover'),
            command=self._on_add_monster).pack(side="right")
        self.delete_btn = ctk.CTkButton(
            bar, text="Delete", width=70, height=35,
            fg_color=theme.get_current_color('button_danger'),
            hover_color=theme.get_current_color('button_danger_hover'),
            command=self._on_delete_monster, state="disabled")
        self.delete_btn.pack(side="right", padx=(0, 5))
        self.edit_btn = ctk.CTkButton(
            bar, text="Edit", width=60, height=35,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            command=self._on_edit_monster, state="disabled")
        self.edit_btn.pack(side="right", padx=(0, 5))
        self.duplicate_btn = ctk.CTkButton(
            bar, text="Duplicate", width=80, height=35,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            command=self._on_duplicate_monster, state="disabled")
        self.duplicate_btn.pack(side="right", padx=(0, 5))

        # Row 2: challenge rating, armor class, hit points, checkboxes
        bar = self._bar()
        self._label(bar, "CR:")
        self.min_cr_var, self.min_cr_combo = self._combo(bar, ["Any"] + CR_OPTIONS, "Any", 75)
        ctk.CTkLabel(bar, text="to").pack(side="left", padx=(0, 5))
        self.max_cr_var, self.max_cr_combo = self._combo(bar, ["Any"] + CR_OPTIONS, "Any", 75)
        self.min_ac_var, self.max_ac_var = self._range_entries(bar, "AC:")
        self.min_hp_var, self.max_hp_var = self._range_entries(bar, "HP:", width=70)
        self.legendary_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bar, text="Legendary", variable=self.legendary_var, width=90,
                        command=lambda: self._on_filter_changed(immediate=True)).pack(side="left", padx=(0, 10))
        self.lair_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bar, text="Has Lair", variable=self.lair_var, width=80,
                        command=lambda: self._on_filter_changed(immediate=True)).pack(side="left", padx=(0, 10))
        self._add_titles_only(bar, (0, 0))

        # Row 3: where it comes from, where it lives, what it carries
        bar = self._bar()
        self.source_filter = self._multi(bar, "Source", mgr.get_all_sources, "sources", 120, source=True)
        self._label(bar, "Content:")
        self.official_var, self.official_combo = self._combo(
            bar, ["Any Content", "Official Only", "Homebrew Only"], "Any Content", 140)
        self.subtype_filter = self._multi(bar, "Subtype", mgr.get_all_subtypes, "subtypes")
        self.habitat_filter = self._multi(bar, "Habitat", mgr.get_all_habitats, "habitats")
        self.treasure_filter = self._multi(bar, "Treasure", mgr.get_all_treasures, "treasures")
        self.movement_filter = self._multi(bar, "Movement", lambda: MOVEMENT_OPTIONS, "movement types")

        # Row 4: senses, languages, defenses
        bar = self._bar(pady=(0, 10))
        self.senses_filter = self._multi(bar, "Senses", mgr.get_all_sense_kinds, "senses")
        self.languages_filter = self._multi(bar, "Languages", mgr.get_all_languages, "languages", 120)
        self.immunity_filter = self._multi(
            bar, "Immunities", lambda: mgr.get_all_values("damage_immunities"), "damage immunities", 120)
        self.condition_filter = self._multi(
            bar, "Condition Imm.", lambda: mgr.get_all_values("condition_immunities"),
            "condition immunities", 130)
        self.resistance_filter = self._multi(
            bar, "Resistances", lambda: mgr.get_all_values("damage_resistances"), "resistances", 120)
        self.vulnerability_filter = self._multi(
            bar, "Vulnerabilities", lambda: mgr.get_all_values("damage_vulnerabilities"),
            "vulnerabilities", 130)
        ctk.CTkButton(
            bar, text="Clear Filters", width=110, height=35,
            fg_color=theme.get_current_color('button_danger'),
            hover_color=theme.get_current_color('button_danger_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._clear_filters).pack(side="right")

    # ----- data -----

    BULK_ACTIONS = ("source",)
    BULK_NOUN, BULK_PLURAL = "monster", "monsters"

    def _bulk_fetch(self, name: str):
        return self.monster_manager.get_monster(name)

    def _bulk_store(self, entries: list) -> int:
        with self.monster_manager.batch():
            return sum(bool(self.monster_manager.update_monster(e.name, e)) for e in entries)

    def _bulk_reload(self):
        self._load_monsters()

    def _bulk_all_sources(self) -> List[str]:
        return self.monster_manager.get_all_sources()

    def _load_monsters(self):
        from object_link_sweep import strip_links
        self._listed_spell_only = bool(self.settings_manager.settings.show_spell_only_summons)
        self._all_monsters = sorted(self.monster_manager.browsable, key=lambda m: m.name.lower())

        # One lowercase blob per monster so searching also finds traits and actions.
        self._search_index = {}
        for m in self._all_monsters:
            features = [f"{f.name} {f.description}" for group in (
                m.traits, m.actions, m.bonus_actions, m.reactions, m.legendary_actions, m.lair_actions)
                for f in group]
            blob = " ".join([m.name, m.epithet, m.creature_type, m.creature_subtype, m.alignment,
                             " ".join(m.habitat), " ".join(m.treasure), " ".join(m.gear),
                             m.description, *features])
            self._search_index[m.name] = strip_links(blob).lower()

        mgr = self.monster_manager
        self.type_combo.configure(values=["All Types"] + mgr.get_all_types())
        self.size_combo.configure(values=["All Sizes"] + mgr.get_all_sizes())
        self.alignment_combo.configure(values=["All Alignments"] + mgr.get_all_alignments())
        self._on_filter_changed(immediate=True)

    def refresh(self):
        self._load_monsters()

    def select_monster(self, name: str) -> bool:
        return self.list_panel.select_monster(name)

    # ----- filtering -----

    def _clear_filters(self):
        self.search_var.set("")
        self.titles_var.set(False)
        self.type_var.set("All Types")
        self.size_var.set("All Sizes")
        self.alignment_var.set("All Alignments")
        self.sort_var.set("Name (A-Z)")
        self.min_cr_var.set("Any")
        self.max_cr_var.set("Any")
        for var in (self.min_ac_var, self.max_ac_var, self.min_hp_var, self.max_hp_var):
            var.set("")
        self.legendary_var.set(False)
        self.lair_var.set(False)
        self.official_var.set("Any Content")
        for f in self._filters:
            f.clear()
        self._on_filter_changed(immediate=True)

    @staticmethod
    def _bound(var: ctk.StringVar) -> Optional[int]:
        """An optional whole-number bound from an entry (blank or invalid = no bound)."""
        try:
            return int(var.get().strip())
        except ValueError:
            return None

    @staticmethod
    def _in_range(value: float, low: Optional[float], high: Optional[float]) -> bool:
        return (low is None or value >= low) and (high is None or value <= high)

    def _apply_filters(self):
        self._filter_debounce_id = None
        search = self.search_var.get().strip().lower()
        type_filter, size_filter = self.type_var.get(), self.size_var.get()
        alignment_filter, official_filter = self.alignment_var.get(), self.official_var.get()

        min_cr = None if self.min_cr_var.get() == "Any" else cr_to_number(self.min_cr_var.get())
        max_cr = None if self.max_cr_var.get() == "Any" else cr_to_number(self.max_cr_var.get())
        ac_low, ac_high = self._bound(self.min_ac_var), self._bound(self.max_ac_var)
        hp_low, hp_high = self._bound(self.min_hp_var), self._bound(self.max_hp_var)

        filtered = []
        for m in self._all_monsters:
            if search and search not in (m.name.lower() if self._titles_only()
                                         else self._search_index.get(m.name, "")):
                continue
            if type_filter != "All Types" and m.creature_type != type_filter:
                continue
            if size_filter != "All Sizes" and m.size != size_filter:
                continue
            if alignment_filter != "All Alignments" and m.alignment != alignment_filter:
                continue
            if not self._in_range(cr_to_number(m.challenge_rating), min_cr, max_cr):
                continue
            if not self._in_range(m.ac, ac_low, ac_high) or not self._in_range(m.hp, hp_low, hp_high):
                continue
            if self.legendary_var.get() and not m.legendary_actions:
                continue
            if self.lair_var.get() and not m.has_lair():
                continue
            if official_filter == "Official Only" and not m.is_official:
                continue
            if official_filter == "Homebrew Only" and m.is_official:
                continue

            if not (self.source_filter.matches([m.source] if m.source else [""])
                    and self.subtype_filter.matches([m.creature_subtype] if m.creature_subtype else [])
                    and self.habitat_filter.matches(m.habitat)
                    and self.treasure_filter.matches(m.treasure)
                    and self.movement_filter.matches(movement_kinds(m))
                    and self.senses_filter.matches([sense_kind(s) for s in m.senses])
                    and self.languages_filter.matches(m.languages)
                    and self.immunity_filter.matches(m.damage_immunities)
                    and self.condition_filter.matches(m.condition_immunities)
                    and self.resistance_filter.matches(m.damage_resistances)
                    and self.vulnerability_filter.matches(m.damage_vulnerabilities)):
                continue
            filtered.append(m)

        key, reverse = SORT_OPTIONS.get(self.sort_var.get(), SORT_OPTIONS["Name (A-Z)"])
        filtered.sort(key=key, reverse=reverse)
        self.list_panel.set_monsters(filtered)

    # ----- actions -----

    def _on_monster_selected(self, monster: Optional[Monster]):
        self.detail_panel.show_monster(monster)
        self.duplicate_btn.configure(state="normal" if monster else "disabled")
        editable = "normal" if monster and monster.is_custom else "disabled"
        self.edit_btn.configure(state=editable)
        self.delete_btn.configure(state=editable)

    def _open_editor(self, title: str, **kwargs) -> Optional[Monster]:
        dialog = MonsterEditorDialog(self.winfo_toplevel(), title, **kwargs)
        self.wait_window(dialog)
        return dialog.result

    def _on_add_monster(self):
        from ui.studio_launch import open_in_studio
        if open_in_studio(self, "monsters"):
            return
        result = self._open_editor("Add Monster")
        if result:
            self._save_new(result)

    def _on_duplicate_monster(self):
        monster = self.list_panel.get_selected_monster()
        if not monster:
            return
        copy = replace(monster, name=f"{monster.name} (Copy)", is_official=False, is_custom=True,
                       spell_only=False, spell_name="")
        from ui.studio_launch import open_in_studio
        if open_in_studio(self, "monsters", name=copy.name, record=copy.to_dict()):
            return
        result = self._open_editor("Duplicate Monster", prefill=copy)
        if result:
            self._save_new(result)

    def _save_new(self, monster: Monster):
        if self.monster_manager.get_monster(monster.name):
            messagebox.showerror("Error", f"A monster named '{monster.name}' already exists. "
                                          "It was not added.")
            return
        if self.monster_manager.add_monster(monster):
            self._load_monsters()
            self.list_panel.select_when_listed(monster.name)

    def _on_edit_monster(self):
        monster = self.list_panel.get_selected_monster()
        if not monster or not monster.is_custom:
            return
        result = self._open_editor("Edit Monster", monster=monster)
        if not result:
            return
        clash = self.monster_manager.get_monster(result.name)
        if clash and clash.name.lower() != monster.name.lower():
            messagebox.showerror("Error", f"A monster named '{result.name}' already exists.")
            return
        if self.monster_manager.update_monster(monster.name, result):
            self._load_monsters()
            self.list_panel.select_when_listed(result.name)
            self.detail_panel.show_monster(result)

    def _on_delete_monster(self):
        monster = self.list_panel.get_selected_monster()
        if not monster or not monster.is_custom:
            return
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{monster.name}'?"):
            if self.monster_manager.delete_monster(monster.name):
                self._load_monsters()
                self.detail_panel.show_monster(None)
                self._on_monster_selected(None)
