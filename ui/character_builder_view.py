"""
The guided character builder: a step-by-step page on the Characters page for making a character.

Class, subclass (when the level is high enough), species, background, ability scores, feats (for the
Ability Score Improvements the level gives), skills, spells and starting equipment, then a review. Every
choice goes into a ``character_builder.Draft``; nothing is saved until Create Character at the end, which makes
the character and its sheet with everything filled in (``character_builder.create_character``).

Long lists (classes, species, backgrounds, spells) are plain Tk listboxes, which are cheap to fill, so moving
between steps stays quick on slow machines.
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

import character_builder as cb
from theme import get_theme_manager
from typography import ui_font
from ui.scrollable_combobox import ScrollableComboBox

NONE = "—"


def clean(text: str) -> str:
    """Description text without link markup and markdown emphasis."""
    text = cb._plain_text(text or "")
    return re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text).strip()


class CharacterBuilderView(ctk.CTkFrame):
    """``on_close(name)`` is called with the new character's name, or None when the builder is left."""

    def __init__(self, parent, character_manager, spell_manager=None,
                 on_close: Optional[Callable[[Optional[str]], None]] = None, sources: Optional[cb.Sources] = None):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.character_manager = character_manager
        self.spell_manager = spell_manager
        self.on_close = on_close
        self.src = sources or cb.Sources.default()
        self.draft = cb.Draft()
        self.step = "start"
        self.visited = {"start"}
        self._all_spells: Optional[list] = None
        self._spell_tab = ""
        self._build()
        self.show_step("start")

    # ------------------------------------------------------------------ layout

    def _color(self, key: str) -> str:
        return self.theme.get_current_color(key)

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkButton(header, text="← Characters", width=110, height=32,
                      fg_color=self._color('button_normal'), hover_color=self._color('button_hover'),
                      command=self.cancel).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(header, text="Character Builder", font=ui_font("title", 28, bold=True)).pack(side="left")
        self.step_label = ctk.CTkLabel(header, text="", font=ui_font("body"),
                                       text_color=self.theme.get_text_secondary())
        self.step_label.pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        self.steps_panel = ctk.CTkFrame(body, width=190, fg_color=self._color('bg_secondary'), corner_radius=10)
        self.steps_panel.pack(side="left", fill="y", padx=(0, 12))
        self.steps_panel.pack_propagate(False)

        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        footer = ctk.CTkFrame(right, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        self.next_btn = ctk.CTkButton(footer, text="Next →", width=150, height=36,
                                      fg_color=self._color('accent_primary'), hover_color=self._color('accent_hover'),
                                      text_color=self._color('text_on_accent'), command=self.next)
        self.next_btn.pack(side="right")
        self.back_btn = ctk.CTkButton(footer, text="← Back", width=100, height=36,
                                      fg_color=self._color('button_normal'), hover_color=self._color('button_hover'),
                                      command=self.back)
        self.back_btn.pack(side="right", padx=(0, 8))
        self.problem_label = ctk.CTkLabel(footer, text="", font=ui_font("body"), anchor="w", justify="left",
                                          text_color=self._color('button_danger'))
        self.problem_label.pack(side="left", fill="x", expand=True)

        self.content = ctk.CTkFrame(right, fg_color=self._color('bg_secondary'), corner_radius=10)
        self.content.pack(side="top", fill="both", expand=True)

    def _fill_steps_panel(self, keys: List[str]):
        for child in self.steps_panel.winfo_children():
            child.destroy()
        ctk.CTkLabel(self.steps_panel, text="Steps", font=ui_font("subheading", bold=True),
                     anchor="w").pack(fill="x", padx=14, pady=(12, 6))
        for i, key in enumerate(keys, 1):
            current = key == self.step
            done = key in self.visited and not current
            mark = "▶" if current else ("✓" if done else "○")
            label = ctk.CTkLabel(
                self.steps_panel, text=f"{mark}  {i}. {cb.STEP_TITLES[key]}", anchor="w",
                font=ui_font("body", bold=current), corner_radius=6,
                fg_color=self._color('bg_tertiary') if current else "transparent",
                text_color=self._color('text_primary') if (current or done) else self.theme.get_text_secondary())
            label.pack(fill="x", padx=8, pady=1, ipady=3)
            if key in self.visited and not current:
                label.configure(cursor="hand2")
                label.bind("<Button-1>", lambda _e, k=key: self.show_step(k))

    # ------------------------------------------------------------------ moving between steps

    def steps(self) -> List[str]:
        return cb.steps_for(self.draft, self.src)

    def _existing_names(self):
        return [c.name for c in self.character_manager.characters]

    def show_step(self, key: str):
        self._tidy()
        keys = self.steps()
        if key not in keys:
            key = keys[0]
        self.step = key
        self.visited.add(key)
        self.problem_label.configure(text="")
        for child in self.content.winfo_children():
            child.destroy()
        getattr(self, f"_step_{key}")(self.content)
        self._fill_steps_panel(keys)
        index = keys.index(key)
        self.step_label.configure(text=f"Step {index + 1} of {len(keys)}: {cb.STEP_TITLES[key]}")
        self.back_btn.configure(state="normal" if index > 0 else "disabled")
        self.next_btn.configure(text="Create Character" if key == "review" else "Next →")

    def next(self):
        issues = cb.problems(self.draft, self.step, self.src, self._existing_names())
        if issues:
            self.problem_label.configure(text=issues[0])
            return
        if self.step == "review":
            # a step can have come undone when an earlier one changed (a new class needs new skills)
            for key in self.steps():
                issues = cb.problems(self.draft, key, self.src, self._existing_names())
                if issues:
                    self.show_step(key)
                    self.problem_label.configure(text=issues[0])
                    return
            self.create()
            return
        self._tidy()
        keys = self.steps()
        index = keys.index(self.step) if self.step in keys else 0
        self.show_step(keys[min(index + 1, len(keys) - 1)])

    def back(self):
        keys = self.steps()
        index = keys.index(self.step) if self.step in keys else 0
        if index > 0:
            self.show_step(keys[index - 1])

    def _tidy(self):
        """Keep later choices consistent with earlier ones (a new class drops the old subclass, and so on)."""
        d, src = self.draft, self.src
        if d.subclass and (not cb.needs_subclass(d, src) or
                           d.subclass not in [s.name for s in src.subclasses(src.class_def(d.class_name))]):
            d.subclass = ""
        cb.sync_feat_slots(d, src)
        background = src.background(d.background)
        feats = self._origin_feats(background)
        if d.origin_feat not in feats:
            d.origin_feat = feats[0] if feats else ""
        cb.tidy_skills(d, src)
        cb.tidy_grants(d)
        cb.tidy_spells(d, src, self._spells())
        letters = [o[0] for o in cb.class_equipment_options(src.class_def(d.class_name))]
        if d.class_equipment not in letters:
            d.class_equipment = letters[0] if letters else ""
        letters = [o[0] for o in cb.equipment_options(getattr(background, "equipment", ""))]
        if d.background_equipment not in letters:
            d.background_equipment = letters[0] if letters else ""

    def _origin_feats(self, background) -> List[str]:
        return [f for f in getattr(background, "feats", []) or [] if self.src.feat(f) is not None]

    def cancel(self):
        d = self.draft
        if (d.name.strip() or d.class_name) and not messagebox.askyesno(
                "Leave the Character Builder", "Leave the builder? The choices you made here will be lost.",
                parent=self):
            return
        self._close(None)

    def create(self):
        from ui.character_sheet_view import get_sheet_manager
        try:
            character = cb.create_character(self.draft, self.src, self.character_manager, get_sheet_manager())
        except Exception as e:
            messagebox.showerror("Character Builder", f"Could not create the character:\n{e}", parent=self)
            return
        self._close(character.name)

    def _close(self, name: Optional[str]):
        if self.on_close:
            self.on_close(name)

    # ------------------------------------------------------------------ small building blocks

    def _intro(self, parent, title: str, text: str):
        ctk.CTkLabel(parent, text=title, font=ui_font("heading", 20, bold=True), anchor="w").pack(
            fill="x", padx=18, pady=(14, 2))
        if text:
            ctk.CTkLabel(parent, text=text, font=ui_font("body"), anchor="w", justify="left", wraplength=760,
                         text_color=self.theme.get_text_secondary()).pack(fill="x", padx=18, pady=(0, 8))

    def _listbox(self, parent, height: int = 12) -> tk.Listbox:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True)
        lb = tk.Listbox(frame, activestyle="none", exportselection=False, relief="flat", highlightthickness=0,
                        height=height, bg=self._color('bg_input'), fg=self._color('text_primary'),
                        selectbackground=self._color('accent_primary'),
                        selectforeground=self._color('text_on_accent'), font=("TkDefaultFont", 11))
        bar = ctk.CTkScrollbar(frame, command=lb.yview)
        lb.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)
        return lb

    def _detail_box(self, parent) -> ctk.CTkTextbox:
        box = ctk.CTkTextbox(parent, wrap="word", font=ui_font("body"), fg_color=self._color('bg_input'))
        box.pack(fill="both", expand=True)
        box.configure(state="disabled")
        return box

    @staticmethod
    def _set_text(box: ctk.CTkTextbox, text: str):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _chooser(self, parent, names: List[str], selected: str, on_pick: Callable[[str], None],
                 describe: Callable[[str], str], search: bool = True):
        """A searchable list on the left and the picked entry's description on the right."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        left = ctk.CTkFrame(row, fg_color="transparent", width=260)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        entry = None
        if search:
            entry = ctk.CTkEntry(left, height=30, placeholder_text="Search…")
            entry.pack(fill="x", pady=(0, 6))
        lb = self._listbox(left)
        box = self._detail_box(right)
        shown: List[str] = []

        def fill():
            query = entry.get().strip().lower() if entry is not None else ""
            shown[:] = [n for n in names if not query or query in n.lower()]
            lb.delete(0, "end")
            for n in shown:
                lb.insert("end", n)
            if selected_name[0] in shown:
                i = shown.index(selected_name[0])
                lb.selection_set(i)
                lb.see(i)

        def picked(_e=None):
            sel = lb.curselection()
            if not sel:
                return
            name = shown[sel[0]]
            selected_name[0] = name
            self._set_text(box, describe(name))
            self.problem_label.configure(text="")
            on_pick(name)

        selected_name = [selected]
        lb.bind("<<ListboxSelect>>", picked)
        lb.bind("<Double-Button-1>", lambda _e: self.next())
        if entry is not None:
            entry.bind("<KeyRelease>", lambda _e: fill())
        fill()
        self._set_text(box, describe(selected) if selected else "Pick one from the list to read about it.")
        return lb

    def _combo(self, parent, values: List[str], value: str, command, width: int = 160) -> ScrollableComboBox:
        var = ctk.StringVar(value=value)
        combo = ScrollableComboBox(parent, width=width, height=30, variable=var, values=values, state="readonly",
                                   command=command)
        return combo

    # ------------------------------------------------------------------ 1. name and level

    def _step_start(self, parent):
        self._intro(parent, "Let's make a character",
                    "This builder walks you through making a character one step at a time: class, subclass, "
                    "species, background, ability scores, skills, spells and equipment. Nothing is saved until "
                    "you press Create Character at the end, and you can go back to any step you've seen.")
        form = ctk.CTkFrame(parent, fg_color="transparent")
        form.pack(fill="x", padx=18, pady=8)
        ctk.CTkLabel(form, text="Character name", font=ui_font("body", bold=True), anchor="w").pack(fill="x")
        name = ctk.CTkEntry(form, height=34, width=360, placeholder_text="e.g. Tess Brightwater")
        name.pack(anchor="w", pady=(2, 14))
        if self.draft.name:
            name.insert(0, self.draft.name)
        name.bind("<KeyRelease>", lambda _e: setattr(self.draft, "name", name.get()))
        name.bind("<Return>", lambda _e: self.next())
        self.name_entry = name
        self.after(50, lambda: name.focus_set() if name.winfo_exists() else None)

        ctk.CTkLabel(form, text="Starting level", font=ui_font("body", bold=True), anchor="w").pack(fill="x")
        line = ctk.CTkFrame(form, fg_color="transparent")
        line.pack(anchor="w", pady=(2, 0))
        level_label = ctk.CTkLabel(line, text=str(self.draft.level), width=40, font=ui_font("heading", 18, bold=True))

        def change(delta):
            self.draft.level = max(1, min(20, self.draft.level + delta))
            level_label.configure(text=str(self.draft.level))
        for text, delta in (("−", -1),):
            ctk.CTkButton(line, text=text, width=34, height=32, fg_color=self._color('button_normal'),
                          hover_color=self._color('button_hover'), command=lambda d=delta: change(d)).pack(side="left")
        level_label.pack(side="left", padx=6)
        ctk.CTkButton(line, text="+", width=34, height=32, fg_color=self._color('button_normal'),
                      hover_color=self._color('button_hover'), command=lambda: change(1)).pack(side="left")
        ctk.CTkLabel(form, text="Most new characters start at level 1. A higher level adds a subclass choice, "
                                "feats and more spells along the way.",
                     font=ui_font("small"), anchor="w", text_color=self.theme.get_text_secondary()).pack(
            fill="x", pady=(6, 0))

    # ------------------------------------------------------------------ 2. class

    def _describe_class(self, name: str) -> str:
        c = self.src.class_def(name)
        if c is None:
            return ""
        count, options = cb.class_skill_choice(cb.Draft(class_name=name), self.src)
        lines = [f"Hit die: {c.hit_die}"]
        if c.primary_ability:
            lines.append(f"Primary ability: {c.primary_ability}")
        if c.saving_throw_proficiencies:
            lines.append("Saving throws: " + ", ".join(c.saving_throw_proficiencies))
        if c.armor_proficiencies:
            lines.append("Armor: " + ", ".join(c.armor_proficiencies))
        if c.weapon_proficiencies:
            lines.append("Weapons: " + ", ".join(c.weapon_proficiencies))
        if c.tool_proficiencies:
            lines.append("Tools: " + ", ".join(clean(t) for t in c.tool_proficiencies))
        if count:
            lines.append(f"Skills: choose {count} from " + ", ".join(options))
        if c.is_spellcaster:
            lines.append(f"Spellcasting ability: {c.spellcasting_ability}")
        if c.selectable_subclasses:
            lines.append(f"Subclass at level {c.subclass_level}")
        if c.source:
            lines.append(f"Source: {c.source}")
        return "\n".join(lines) + "\n\n" + clean(cb.class_description(c))

    def _step_class(self, parent):
        self._intro(parent, "Choose a class",
                    "Your class is what your character does best: fight, cast spells, sneak, heal... It decides "
                    "your hit points, what you're proficient in and the features you get as you level up.")

        def pick(name):
            self.draft.class_name = name
        self._chooser(parent, [c.name for c in self.src.classes()], self.draft.class_name, pick,
                      self._describe_class)

    # ------------------------------------------------------------------ 3. subclass

    def _describe_subclass(self, name: str) -> str:
        class_def = self.src.class_def(self.draft.class_name)
        sub = class_def.find_subclass(name) if class_def else None
        if sub is None:
            return ""
        lines = [clean(sub.description)]
        features = class_def.get_subclass_features_up_to_level(sub, self.draft.level)
        if features:
            lines.append("\nFeatures up to your level:")
            lines += [f"• Level {f.level}: {f.title}" for f in features]
        if sub.source:
            lines.append(f"\nSource: {sub.source}")
        return "\n".join(lines)

    def _step_subclass(self, parent):
        class_def = self.src.class_def(self.draft.class_name)
        label = class_def.subclass_name or "subclass"
        self._intro(parent, f"Choose your {label.lower()}",
                    f"At level {class_def.subclass_level} a {class_def.name} specialises. Your subclass adds "
                    f"its own features (and for some, spells) on top of the class's.")

        def pick(name):
            self.draft.subclass = name
        self._chooser(parent, [s.name for s in self.src.subclasses(class_def)], self.draft.subclass, pick,
                      self._describe_subclass)

    # ------------------------------------------------------------------ 4. species

    def _describe_lineage(self, name: str) -> str:
        lin = self.src.lineage(name)
        if lin is None:
            return ""
        lines = [f"{lin.creature_type} · Size: {lin.size} · Speed: {lin.speed} ft."]
        if lin.source:
            lines.append(f"Source: {lin.source}")
        lines.append("\n" + clean(lin.description))
        for trait in lin.traits:
            lines.append(f"\n{trait.name}. {clean(trait.description)}")
        return "\n".join(lines)

    def _step_lineage(self, parent):
        self._intro(parent, "Choose a species",
                    "Your species (lineage) gives you traits like darkvision, a special speed or resistance, and "
                    "sometimes a spell or two.")
        extra = ctk.CTkFrame(parent, fg_color="transparent")

        def pick(name):
            self.draft.lineage = name
            cb.tidy_grants(self.draft)
            self._species_extras(extra)
        self._chooser(parent, [x.name for x in self.src.lineages()], self.draft.lineage, pick,
                      self._describe_lineage)
        extra.pack(fill="x", padx=18, pady=(0, 12))
        self._species_extras(extra)

    def _species_extras(self, frame):
        for child in frame.winfo_children():
            child.destroy()
        for group in cb.species_options(self.draft):
            line = ctk.CTkFrame(frame, fg_color="transparent")
            line.pack(fill="x")
            ctk.CTkLabel(line, text=f"{group.label}:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 8))

            def chose(value, key=group.key):
                if value == NONE:
                    self.draft.grant_options.pop(key, None)
                else:
                    self.draft.grant_options[key] = value
            self._combo(line, [NONE] + group.options, self.draft.grant_options.get(group.key, NONE), chose,
                        width=200).pack(side="left")
            ctk.CTkLabel(line, text="(decides which spells the species gives)", font=ui_font("small"),
                         text_color=self.theme.get_text_secondary()).pack(side="left", padx=8)

    # ------------------------------------------------------------------ 5. background

    def _describe_background(self, name: str) -> str:
        bg = self.src.background(name)
        if bg is None:
            return ""
        lines = []
        if bg.skills:
            lines.append("Skills: " + ", ".join(bg.skills))
        if bg.other_proficiencies:
            lines.append("Tools: " + ", ".join(clean(t) for t in bg.other_proficiencies))
        if bg.ability_scores:
            lines.append("Ability scores: " + ", ".join(bg.ability_scores))
        if bg.feats:
            lines.append("Origin feat: " + " or ".join(bg.feats))
        if bg.equipment:
            lines.append("Equipment: " + clean(bg.equipment))
        if bg.source:
            lines.append(f"Source: {bg.source}")
        lines.append("\n" + clean(bg.description))
        for feature in bg.features:
            lines.append(f"\n{feature.name}. {clean(feature.description)}")
        return "\n".join(lines)

    def _step_background(self, parent):
        self._intro(parent, "Choose a background",
                    "Your background is what you did before adventuring. It gives two skills, a tool, an origin "
                    "feat, and raises some ability scores.")
        extra = ctk.CTkFrame(parent, fg_color="transparent")

        def pick(name):
            self.draft.background = name
            feats = self._origin_feats(self.src.background(name))
            if self.draft.origin_feat not in feats:
                self.draft.origin_feat = feats[0] if feats else ""
            allowed = cb.background_abilities(self.draft, self.src)
            if self.draft.bonus_plus2 not in allowed:
                self.draft.bonus_plus2 = ""
            if self.draft.bonus_plus1 not in allowed:
                self.draft.bonus_plus1 = ""
            self._background_extras(extra)
        self._chooser(parent, [b.name for b in self.src.backgrounds()], self.draft.background, pick,
                      self._describe_background)
        extra.pack(fill="x", padx=18, pady=(0, 12))
        self._background_extras(extra)

    def _background_extras(self, frame):
        for child in frame.winfo_children():
            child.destroy()
        d = self.draft
        feats = self._origin_feats(self.src.background(d.background))
        if len(feats) > 1:
            line = ctk.CTkFrame(frame, fg_color="transparent")
            line.pack(fill="x", pady=(0, 6))
            ctk.CTkLabel(line, text="Origin feat:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 8))
            self._combo(line, feats, d.origin_feat, lambda v: setattr(d, "origin_feat", v), width=240).pack(side="left")
        elif feats:
            ctk.CTkLabel(frame, text=f"Origin feat: {feats[0]}", font=ui_font("body", bold=True),
                         anchor="w").pack(fill="x", pady=(0, 6))

        allowed = cb.background_abilities(d, self.src)
        if not allowed:
            return
        line = ctk.CTkFrame(frame, fg_color="transparent")
        line.pack(fill="x")
        ctk.CTkLabel(line, text="Ability scores:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 8))
        choices = ctk.CTkFrame(frame, fg_color="transparent")

        def set_mode(value):
            d.bonus_mode = "1/1/1" if value.startswith("+1 / +1") else "2/1"
            self._bonus_choices(choices, allowed)
        mode = ctk.CTkSegmentedButton(line, values=["+2 and +1", "+1 / +1 / +1"], command=set_mode)
        mode.set("+1 / +1 / +1" if d.bonus_mode == "1/1/1" else "+2 and +1")
        mode.pack(side="left")
        choices.pack(fill="x", pady=(6, 0))
        self._bonus_choices(choices, allowed)

    def _bonus_choices(self, frame, allowed: List[str]):
        for child in frame.winfo_children():
            child.destroy()
        d = self.draft
        labels = [cb.ABILITY_LABELS[a] for a in allowed]
        if d.bonus_mode == "1/1/1":
            ctk.CTkLabel(frame, text="+1 to " + ", ".join(labels), font=ui_font("body"), anchor="w").pack(fill="x")
            return
        by_label = {cb.ABILITY_LABELS[a]: a for a in allowed}
        for text, attr in (("+2 to", "bonus_plus2"), ("+1 to", "bonus_plus1")):
            ctk.CTkLabel(frame, text=text, font=ui_font("body")).pack(side="left", padx=(0, 6))
            current = cb.ABILITY_LABELS.get(getattr(d, attr), NONE)
            self._combo(frame, [NONE] + labels, current,
                        lambda v, a=attr: setattr(d, a, by_label.get(v, "")), width=140).pack(side="left", padx=(0, 14))

    # ------------------------------------------------------------------ 6. ability scores

    def _step_abilities(self, parent):
        class_def = self.src.class_def(self.draft.class_name)
        hint = ""
        if class_def is not None and class_def.primary_ability:
            hint = f" A {class_def.name} relies most on {class_def.primary_ability}."
        self._intro(parent, "Set your ability scores",
                    "Strength, Dexterity, Constitution, Intelligence, Wisdom and Charisma. Use the standard array, "
                    "point buy, or type in scores you rolled. Your background's bonuses are added on top." + hint)
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(0, 8))
        labels = {"standard": "Standard array", "point_buy": "Point buy", "manual": "Enter scores"}
        by_label = {v: k for k, v in labels.items()}
        grid = ctk.CTkFrame(parent, fg_color="transparent")

        def set_method(value):
            self.draft.set_score_method(by_label[value])
            self._ability_grid(grid)
        method = ctk.CTkSegmentedButton(top, values=list(labels.values()), command=set_method)
        method.set(labels[self.draft.score_method])
        method.pack(side="left")
        ctk.CTkButton(top, text="Suggest for my class", width=160, height=30, fg_color=self._color('button_normal'),
                      hover_color=self._color('button_hover'),
                      command=lambda: (self._suggest_scores(), method.set(labels["standard"]),
                                       self._ability_grid(grid))).pack(side="left", padx=12)
        grid.pack(fill="x", padx=18)
        self._ability_grid(grid)

    def _suggest_scores(self):
        """The standard array, highest first into the class's main abilities, then Constitution and Dexterity."""
        class_def = self.src.class_def(self.draft.class_name)
        text = (getattr(class_def, "primary_ability", "") or "").lower()
        order = [a for a in cb.ABILITIES if a in text]
        caster = (getattr(class_def, "spellcasting_ability", "") or "").upper()
        for a, short in cb.ABILITY_SHORT.items():
            if short == caster and a not in order:
                order.append(a)
        for a in ("constitution", "dexterity", "wisdom", "strength", "charisma", "intelligence"):
            if a not in order:
                order.append(a)
        self.draft.set_score_method("standard")
        self.draft.base_scores = {a: v for a, v in zip(order, cb.STANDARD_ARRAY)}

    def _ability_grid(self, grid):
        for child in grid.winfo_children():
            child.destroy()
        d = self.draft
        heads = ["Ability", "Score", "Bonus", "Total", "Modifier"]
        for col, text in enumerate(heads):
            ctk.CTkLabel(grid, text=text, font=ui_font("small", bold=True),
                         text_color=self.theme.get_text_secondary()).grid(row=0, column=col, padx=8, pady=(0, 4),
                                                                          sticky="w")
        self._ability_cells = {}
        for row, ability in enumerate(cb.ABILITIES, 1):
            ctk.CTkLabel(grid, text=cb.ABILITY_LABELS[ability], font=ui_font("body", bold=True), anchor="w",
                         width=110).grid(row=row, column=0, padx=8, pady=3, sticky="w")
            holder = ctk.CTkFrame(grid, fg_color="transparent")
            holder.grid(row=row, column=1, padx=8, pady=3, sticky="w")
            self._score_control(holder, ability)
            bonus = ctk.CTkLabel(grid, text="", width=60)
            bonus.grid(row=row, column=2, padx=8)
            total = ctk.CTkLabel(grid, text="", width=60, font=ui_font("body", bold=True))
            total.grid(row=row, column=3, padx=8)
            mod = ctk.CTkLabel(grid, text="", width=60)
            mod.grid(row=row, column=4, padx=8)
            self._ability_cells[ability] = (bonus, total, mod)
        self._ability_status = ctk.CTkLabel(grid, text="", font=ui_font("body"), anchor="w",
                                            text_color=self.theme.get_text_secondary())
        self._ability_status.grid(row=len(cb.ABILITIES) + 1, column=0, columnspan=5, sticky="w", padx=8, pady=(8, 0))
        self._update_ability_totals()

    def _score_control(self, holder, ability: str):
        d = self.draft
        if d.score_method == "standard":
            values = [NONE] + [str(v) for v in cb.STANDARD_ARRAY]
            current = str(d.base_scores.get(ability) or NONE)

            def chose(value, a=ability):
                new = int(value) if value != NONE else 0
                old = d.base_scores.get(a, 0)
                for other in cb.ABILITIES:          # a value already used elsewhere swaps places
                    if other != a and new and d.base_scores.get(other) == new:
                        d.base_scores[other] = old
                d.base_scores[a] = new
                self._ability_grid(holder.master)
            self._combo(holder, values, current, chose, width=90).pack(side="left")
        elif d.score_method == "point_buy":
            value = ctk.CTkLabel(holder, text=str(d.base_scores.get(ability, 8)), width=36,
                                 font=ui_font("body", bold=True))

            def step(delta, a=ability, label=value):
                score = d.base_scores.get(a, 8) + delta
                if not 8 <= score <= 15:
                    return
                trial = dict(d.base_scores, **{a: score})
                if cb.points_spent(trial) > cb.POINT_BUY_BUDGET:
                    return
                d.base_scores[a] = score
                label.configure(text=str(score))
                self._update_ability_totals()
            ctk.CTkButton(holder, text="−", width=30, height=28, fg_color=self._color('button_normal'),
                          hover_color=self._color('button_hover'), command=lambda: step(-1)).pack(side="left")
            value.pack(side="left", padx=4)
            ctk.CTkButton(holder, text="+", width=30, height=28, fg_color=self._color('button_normal'),
                          hover_color=self._color('button_hover'), command=lambda: step(1)).pack(side="left")
        else:
            entry = ctk.CTkEntry(holder, width=60, height=30, justify="center")
            entry.insert(0, str(d.base_scores.get(ability, 10)))

            def typed(_e=None, a=ability, box=entry):
                try:
                    d.base_scores[a] = int(box.get())
                except ValueError:
                    d.base_scores[a] = 0
                self._update_ability_totals()
            entry.bind("<KeyRelease>", typed)
            entry.pack(side="left")

    def _update_ability_totals(self):
        d, src = self.draft, self.src
        bg = cb.background_bonuses(d, src)
        ft = cb.feat_bonuses(d)
        totals = cb.final_scores(d, src)
        for ability, (bonus, total, mod) in self._ability_cells.items():
            extra = bg[ability] + ft[ability]
            bonus.configure(text=f"+{extra}" if extra else "")
            if totals[ability]:
                total.configure(text=str(totals[ability]))
                mod.configure(text=cb.signed(cb.modifier(totals[ability])))
            else:
                total.configure(text=NONE)
                mod.configure(text="")
        if d.score_method == "standard":
            left = cb.standard_array_left(d.base_scores)
            text = ("Still to place: " + ", ".join(map(str, left))) if left else "Every value is placed."
        elif d.score_method == "point_buy":
            spent = cb.points_spent(d.base_scores)
            text = f"Points spent: {spent} of {cb.POINT_BUY_BUDGET}  (scores 8 to 15 before bonuses)"
        else:
            text = "Type the scores you rolled (3 to 20)."
        self._ability_status.configure(text=text)

    # ------------------------------------------------------------------ 7. feats

    def _step_feats(self, parent):
        self._intro(parent, "Ability Score Improvements and feats",
                    "Your level gives you these improvements. Each one raises two ability scores by 1 (or one by "
                    "2: pick it twice), or you can take a feat instead. If a feat raises an ability, pick which.")
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        feats = [cb.ASI] + self.src.general_feats()
        labels = [NONE] + [cb.ABILITY_LABELS[a] for a in cb.ABILITIES]
        by_label = {cb.ABILITY_LABELS[a]: a for a in cb.ABILITIES}
        for slot in self.draft.feat_slots:
            line = ctk.CTkFrame(scroll, fg_color="transparent")
            line.pack(fill="x", pady=4)
            ctk.CTkLabel(line, text=f"Level {slot.level}", width=70, anchor="w",
                         font=ui_font("body", bold=True)).pack(side="left")

            def chose_feat(value, s=slot):
                s.feat = value
                s.plus = ["", ""] if value == cb.ASI else s.plus[:1] + [""]
                self.show_step("feats")
            self._combo(line, feats, slot.feat, chose_feat, width=240).pack(side="left", padx=(0, 12))
            count = 2 if slot.feat == cb.ASI else 1
            ctk.CTkLabel(line, text="+1 to" if count == 2 else "Its +1 (if any):",
                         font=ui_font("body")).pack(side="left", padx=(0, 6))
            for i in range(count):
                def chose_ability(value, s=slot, i=i):
                    s.plus[i] = by_label.get(value, "")
                current = cb.ABILITY_LABELS.get(slot.plus[i], NONE)
                self._combo(line, labels, current, chose_ability, width=130).pack(side="left", padx=(0, 6))

    # ------------------------------------------------------------------ 8. skills

    def _step_skills(self, parent):
        d = self.draft
        count, options = cb.class_skill_choice(d, self.src)
        from_bg = cb.background_skills(d, self.src)
        self._intro(parent, "Choose your skills",
                    f"Your class lets you choose {count} skill{'s' if count != 1 else ''}. "
                    + (f"Your background already gives you {', '.join(from_bg)}." if from_bg else ""))
        self._skill_count = ctk.CTkLabel(parent, text="", font=ui_font("body", bold=True), anchor="w")
        self._skill_count.pack(fill="x", padx=18)
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=8)
        self._skill_boxes = {}
        names = list(dict.fromkeys(from_bg + options))
        for i, skill in enumerate(names):
            var = tk.BooleanVar(value=skill in from_bg or skill in d.class_skills)
            box = ctk.CTkCheckBox(grid, text=skill + ("  (background)" if skill in from_bg else ""), variable=var,
                                  command=lambda s=skill, v=var: self._toggle_skill(s, v, count))
            box.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 24), pady=4)
            if skill in from_bg:
                box.configure(state="disabled")
            self._skill_boxes[skill] = (box, var)
        self._update_skill_count(count)

    def _toggle_skill(self, skill: str, var, count: int):
        d = self.draft
        if var.get():
            if len(d.class_skills) >= count:
                var.set(False)
                self.problem_label.configure(text=f"You can choose {count}. Untick one first.")
                return
            d.class_skills.append(skill)
        elif skill in d.class_skills:
            d.class_skills.remove(skill)
        self.problem_label.configure(text="")
        self._update_skill_count(count)

    def _update_skill_count(self, count: int):
        self._skill_count.configure(text=f"Chosen: {len(self.draft.class_skills)} of {count}")

    # ------------------------------------------------------------------ 9. spells

    def _spells(self) -> Optional[list]:
        if self._all_spells is None and self.spell_manager is not None:
            legacy = self.src.legacy_filter
            if legacy == "show_all":
                legacy = "show_unupdated"         # a 2024 character isn't offered every spell twice
            try:
                self._all_spells = list(self.spell_manager.get_filtered_spells(legacy_filter=legacy))
            except Exception as e:
                print(f"Could not read the spells: {e}")
                self._all_spells = []
        return self._all_spells

    def _spell_lists(self):
        """[(key, title, allowed spells, how many, chosen list)] for the class and every feat/species pick."""
        d = self.draft
        spells = self._spells() or []
        cantrips, prepared = cb.spell_counts(d, self.src)
        can_c, can_s = cb.learnable_spells(d, spells)
        lists = []
        if cantrips:
            lists.append(("class:cantrips", "Cantrips", can_c, cantrips, d.cantrips))
        if prepared:
            lists.append(("class:spells", "Prepared spells", can_s, prepared, d.spells))
        report = cb.grant_report(d)
        for pick in (report.picks if report else []):
            chosen = d.grant_choices.setdefault(pick.key, [])
            allowed = sorted((s for s in spells if pick.allows(s)), key=lambda s: (s.level, s.name.lower()))
            title = f"{pick.source.split(': ', 1)[-1]}: {pick.label}"
            lists.append((pick.key, title, allowed, pick.count, chosen))
        return lists

    def _step_spells(self, parent):
        d = self.draft
        if self.spell_manager is None:
            self._intro(parent, "Spells", "The spell collection isn't available here: add spells on the sheet.")
            return
        class_def = self.src.class_def(d.class_name)
        self._intro(parent, "Choose your spells",
                    f"Pick the spells your {class_def.name if class_def else 'character'} starts with. Only spells "
                    "on your spell list and of a level you can cast are shown. Spells your subclass or species "
                    "always give are added for you. Double-click a spell to add or remove it.")
        lists = self._spell_lists()
        if not lists:
            ctk.CTkLabel(parent, text="No spells to choose at this level.", font=ui_font("body")).pack(padx=18)
            return
        keys = [k for k, *_r in lists]
        if self._spell_tab not in keys:
            self._spell_tab = keys[0]
        titles = {k: t for k, t, *_r in lists}
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(0, 6))
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        def label_for(key, title, count, chosen):
            return f"{title} ({len(chosen)}/{count})"
        tab_labels = {k: label_for(k, t, c, ch) for k, t, _a, c, ch in lists}
        by_label = {v: k for k, v in tab_labels.items()}

        def switch(value):
            self._spell_tab = by_label.get(value, keys[0])
            self.show_step("spells")
        tabs = ctk.CTkSegmentedButton(bar, values=list(tab_labels.values()), command=switch)
        tabs.set(tab_labels[self._spell_tab])
        tabs.pack(side="left")
        entry = next(x for x in lists if x[0] == self._spell_tab)
        self._spell_picker(body, entry, tabs, tab_labels, label_for)

    def _spell_picker(self, body, entry, tabs, tab_labels, label_for):
        key, title, allowed, count, chosen = entry
        left = ctk.CTkFrame(body, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)
        middle = ctk.CTkFrame(body, fg_color="transparent", width=110)
        middle.pack(side="left", fill="y", padx=10)
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        search_line = ctk.CTkFrame(left, fg_color="transparent")
        search_line.pack(fill="x", pady=(0, 6))
        search = ctk.CTkEntry(search_line, height=30, placeholder_text="Search spells…")
        search.pack(side="left", fill="x", expand=True)
        levels = sorted({s.level for s in allowed})
        level_labels = ["All levels"] + [("Cantrips" if lv == 0 else f"Level {lv}") for lv in levels]
        level_var = ctk.StringVar(value="All levels")
        if len(levels) > 1:
            ctk.CTkOptionMenu(search_line, values=level_labels, variable=level_var, width=110, height=30,
                              command=lambda _v: fill()).pack(side="left", padx=(6, 0))
        available = self._listbox(left, height=14)
        ctk.CTkLabel(right, text="Chosen", font=ui_font("body", bold=True), anchor="w").pack(fill="x", pady=(0, 6))
        picked = self._listbox(right, height=14)
        info = ctk.CTkLabel(body.master, text="", font=ui_font("small"), anchor="w",
                            text_color=self.theme.get_text_secondary())
        info.pack(fill="x", padx=18, pady=(0, 6))
        by_name = {s.name: s for s in allowed}
        shown: List[str] = []

        def describe(name):
            s = by_name.get(name)
            if s is None:
                return ""
            level = "Cantrip" if s.level == 0 else f"Level {s.level}"
            parts = [name, level, s.display_casting_time() if hasattr(s, "display_casting_time") else s.casting_time]
            try:
                parts.append(s.display_range())
            except Exception:
                pass
            parts.append(s.duration)
            return " · ".join(p for p in parts if p)

        def fill():
            query = search.get().strip().lower()
            want = level_var.get()
            shown[:] = []
            for s in allowed:
                if s.name in chosen:
                    continue
                if query and query not in s.name.lower():
                    continue
                if want != "All levels" and (("Cantrips" if s.level == 0 else f"Level {s.level}") != want):
                    continue
                shown.append(s.name)
            available.delete(0, "end")
            for n in shown:
                s = by_name[n]
                available.insert("end", n if s.level == 0 else f"{n}   ({s.level})")
            picked.delete(0, "end")
            for n in chosen:
                picked.insert("end", n)
            tab_labels[key] = label_for(key, title, count, chosen)
            try:
                tabs.configure(values=list(tab_labels.values()))
                tabs.set(tab_labels[key])
            except Exception:
                pass

        def add(_e=None):
            sel = available.curselection()
            if not sel:
                return
            if len(chosen) >= count:
                self.problem_label.configure(text=f"That's all {count} for {title}. Remove one to swap it.")
                return
            chosen.append(shown[sel[0]])
            self.problem_label.configure(text="")
            fill()

        def remove(_e=None):
            sel = picked.curselection()
            if sel:
                del chosen[sel[0]]
                self.problem_label.configure(text="")
                fill()

        available.bind("<Double-Button-1>", add)
        available.bind("<<ListboxSelect>>", lambda _e: info.configure(
            text=describe(shown[available.curselection()[0]]) if available.curselection() else ""))
        picked.bind("<Double-Button-1>", remove)
        picked.bind("<<ListboxSelect>>", lambda _e: info.configure(
            text=describe(chosen[picked.curselection()[0]]) if picked.curselection() else ""))
        search.bind("<KeyRelease>", lambda _e: fill())
        ctk.CTkButton(middle, text="Add →", width=100, command=add).pack(pady=(60, 6))
        ctk.CTkButton(middle, text="← Remove", width=100, fg_color=self._color('button_normal'),
                      hover_color=self._color('button_hover'), command=remove).pack()
        self.spell_available, self.spell_chosen = available, picked
        self.spell_add, self.spell_remove = add, remove
        fill()

    # ------------------------------------------------------------------ 10. equipment

    def _step_equipment(self, parent):
        d, src = self.draft, self.src
        self._intro(parent, "Choose your starting equipment",
                    "Take the gear your class and background come with, or the gold to buy your own. Items that are "
                    "in the Equipment collection go into the inventory linked to their entries; anything else is "
                    "kept in the equipment notes.")
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        class_def = src.class_def(d.class_name)
        background = src.background(d.background)
        sections = [(f"From your class ({d.class_name})", cb.class_equipment_options(class_def), "class_equipment"),
                    (f"From your background ({d.background})",
                     cb.equipment_options(getattr(background, "equipment", "")), "background_equipment")]
        for title, options, attr in sections:
            ctk.CTkLabel(scroll, text=title, font=ui_font("subheading", bold=True), anchor="w").pack(
                fill="x", pady=(8, 4))
            if not options:
                ctk.CTkLabel(scroll, text="Nothing listed.", font=ui_font("body"), anchor="w",
                             text_color=self.theme.get_text_secondary()).pack(fill="x")
                continue
            var = tk.StringVar(value=getattr(d, attr))
            for letter, items in options:
                ctk.CTkRadioButton(scroll, text=f"{letter}:  " + ", ".join(items), variable=var, value=letter,
                                   command=lambda a=attr, v=var: setattr(d, a, v.get())).pack(anchor="w", pady=3)

    # ------------------------------------------------------------------ 11. review

    def _step_review(self, parent):
        d, src = self.draft, self.src
        self._intro(parent, f"Ready to create {d.name.strip() or 'your character'}?",
                    "Check your choices. Click a step on the left to change something, or press Create Character. "
                    "The new character's sheet opens with everything filled in.")
        box = self._detail_box(parent)
        box.pack_configure(padx=18, pady=(0, 12))
        self.review_box = box
        self._set_text(box, self.summary())

    def summary(self) -> str:
        d, src = self.draft, self.src
        lines = [f"Name: {d.name.strip()}", f"Class: {d.class_name} {d.level}"
                 + (f" ({d.subclass})" if d.subclass else "")]
        species = d.lineage
        for key, value in d.grant_options.items():
            if key == f"lineage:{d.lineage}":
                species += f" ({value})"
        lines.append(f"Species: {species}")
        lines.append(f"Background: {d.background}")
        feats = [d.origin_feat] if d.origin_feat else []
        feats += [f"{s.feat} (level {s.level})" for s in d.feat_slots if s.feat != cb.ASI]
        if feats:
            lines.append("Feats: " + ", ".join(feats))
        scores = cb.final_scores(d, src)
        lines.append("Ability scores: " + ", ".join(
            f"{cb.ABILITY_SHORT[a]} {scores[a]} ({cb.signed(cb.modifier(scores[a]))})" for a in cb.ABILITIES))
        skills = sorted(set(cb.background_skills(d, src)) | set(d.class_skills))
        lines.append("Skills: " + (", ".join(skills) or "none"))
        class_def = src.class_def(d.class_name)
        if class_def is not None:
            from character_sheet import calculate_hp_maximum
            hp = calculate_hp_maximum([(d.class_name, d.level)], cb.modifier(scores["constitution"] or 10),
                                      feats=[d.origin_feat] + [s.feat for s in d.feat_slots])
            lines.append(f"Hit points: {hp}  ·  Proficiency bonus: +{2 + (d.level - 1) // 4}")
        if d.cantrips:
            lines.append("Cantrips: " + ", ".join(d.cantrips))
        if d.spells:
            lines.append("Spells: " + ", ".join(d.spells))
        for key, chosen in d.grant_choices.items():
            if chosen:
                lines.append(f"{key.split(':')[1]}: " + ", ".join(chosen))
        gear = []
        coins = 0
        for item in cb.chosen_items(d, src):
            if item.coins[0] == "gp":
                coins += item.coins[1]
            elif not item.coins[0]:
                gear.append(item.text)
        if gear or coins:
            lines.append("Equipment: " + ", ".join(gear + ([f"{coins} GP"] if coins else [])))
        notes = cb.leftovers(d, src)
        if notes:
            lines.append("\nLeft to do on the sheet:")
            lines += [f"• {n}" for n in notes]
        return "\n".join(lines)
