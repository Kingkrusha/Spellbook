"""
The Studio's Insights panel: what the draft resembles, and (for a monster) whether its numbers fit its CR.

Two tabs share one panel:

* **Similar** - existing content (class features, spells, magic items, monster abilities...) that does what the
  draft does, with the words they share lit up and the mechanics they have in common named. The point is to spot
  redundancy before it is published: a magic item that lets you treat a low d20 as a 10 brings up Reliable
  Talent and Silver Tongue.
* **Balance** (monsters) - the CR the numbers add up to, every figure that is higher or lower than is typical for
  the CR the monster claims, and the official monsters whose numbers are closest.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import homebrew_index as HI
from studio_service import DraftAnalysis, Hit
from theme import get_theme_manager
from typography import ui_font
from ui.studio_panels import ALL_FAMILIES, FAMILY_CHOICES, family_key
from ui.studio_text import StudioText

SAME_KIND = "Same kind of thing"
EVERYTHING_YOU_WROTE = "Everything you wrote"


class InsightsPanel(ctk.CTkFrame):
    """Similar content and balance checks for the draft being written."""

    def __init__(self, parent, *, on_open: Callable[[Hit, bool], None], on_options_changed: Callable[[], None],
                 on_apply_cr: Callable[[str], None]):
        self.theme = get_theme_manager()
        c = self.theme.get_current_color
        super().__init__(parent, fg_color=c("bg_secondary"), corner_radius=8)
        self.on_open = on_open
        self.on_options_changed = on_options_changed
        self.on_apply_cr = on_apply_cr
        self.kind = ""
        self.compare_mode = "auto"            # which CR the monster is judged against: auto | mine | suggested
        self._analysis: Optional[DraftAnalysis] = None
        self._tab = "Similar"
        self._options_job: Optional[str] = None

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkLabel(head, text="Insights", font=ui_font("subheading", 14, bold=True)).pack(side="left")
        self.status = ctk.CTkLabel(head, text="", font=ui_font("small"), text_color=c("text_secondary"))
        self.status.pack(side="right")
        self.tabs = ctk.CTkSegmentedButton(self, values=["Similar", "Balance"], command=self._switch_tab, height=26)
        self.tabs.set("Similar")

        # ---- Similar tab
        self.similar_frame = ctk.CTkFrame(self, fg_color="transparent")
        opts = ctk.CTkFrame(self.similar_frame, fg_color="transparent")
        opts.pack(fill="x", padx=8, pady=(2, 2))
        self.scope_var = ctk.StringVar(value=ALL_FAMILIES)
        self.scope_menu = ctk.CTkOptionMenu(opts, values=[ALL_FAMILIES, SAME_KIND] + FAMILY_CHOICES[1:],
                                            variable=self.scope_var, width=170, height=26, dynamic_resizing=False,
                                            command=lambda _v: self._options_changed())
        self.scope_menu.pack(side="left")
        self.part_var = ctk.StringVar(value=EVERYTHING_YOU_WROTE)
        self.part_menu = ctk.CTkOptionMenu(opts, values=[EVERYTHING_YOU_WROTE], variable=self.part_var, width=170,
                                           height=26, dynamic_resizing=False,
                                           command=lambda _v: self._render_similar())
        self.part_menu.pack(side="left", padx=(6, 0))
        opts2 = ctk.CTkFrame(self.similar_frame, fg_color="transparent")
        opts2.pack(fill="x", padx=8, pady=(0, 2))
        self.legacy_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts2, text="2014 content", variable=self.legacy_var, font=ui_font("small"),
                        checkbox_width=18, checkbox_height=18, command=self._options_changed).pack(side="left")
        try:
            from settings import get_settings_manager
            unofficial = bool(getattr(get_settings_manager().settings, "studio_include_unofficial", False))
        except Exception:
            unofficial = False
        self.unofficial_var = ctk.BooleanVar(value=unofficial)
        ctk.CTkCheckBox(opts2, text="Unofficial content", variable=self.unofficial_var, font=ui_font("small"),
                        checkbox_width=18, checkbox_height=18, command=self._unofficial_changed
                        ).pack(side="left", padx=(10, 0))
        opts3 = ctk.CTkFrame(self.similar_frame, fg_color="transparent")
        opts3.pack(fill="x", padx=8, pady=(0, 2))
        self.manual = ctk.CTkEntry(opts3, height=26, placeholder_text="or describe something to look for...")
        self.manual.pack(side="left", fill="x", expand=True)
        self.manual.bind("<KeyRelease>", self._manual_changed)
        self.similar_text = StudioText(self.similar_frame, bg_role="bg_primary")
        self.similar_text.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        # ---- Balance tab
        self.balance_frame = ctk.CTkFrame(self, fg_color="transparent")
        top = ctk.CTkFrame(self.balance_frame, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(2, 2))
        self.compare_buttons = ctk.CTkSegmentedButton(top, values=["CR in the editor", "Suggested CR"], height=26,
                                                      command=self._compare_changed)
        self.compare_buttons.pack(side="left")
        self.apply_button = ctk.CTkButton(top, text="Use suggested CR", height=26, width=130,
                                          fg_color=c("accent_primary"), hover_color=c("accent_hover"),
                                          text_color=c("text_on_accent"), command=self._apply)
        self.apply_button.pack(side="right")
        self.balance_text = StudioText(self.balance_frame, bg_role="bg_primary")
        self.balance_text.pack(fill="both", expand=True, padx=6, pady=(2, 6))

        self.similar_frame.pack(fill="both", expand=True)
        self._show_message("Open or write something to compare it with the collection.")

    # ---- options the page reads

    def families(self, own_family: str = "") -> Optional[List[str]]:
        choice = self.scope_var.get()
        if choice == ALL_FAMILIES:
            return None
        if choice == SAME_KIND:
            return [own_family] if own_family else None
        key = family_key(choice)
        return [key] if key else None

    def include_legacy(self) -> bool:
        return bool(self.legacy_var.get())

    def include_unofficial(self) -> bool:
        return bool(self.unofficial_var.get())

    def _unofficial_changed(self):
        """The checkbox is also a setting: it is remembered."""
        try:
            from settings import get_settings_manager
            get_settings_manager().update(studio_include_unofficial=bool(self.unofficial_var.get()))
        except Exception:
            pass
        self._options_changed()

    def manual_query(self) -> str:
        return self.manual.get().strip()

    def compare_to(self) -> Optional[str]:
        """The CR to judge the monster against, or None for the default (its own CR when it looks deliberate)."""
        if self.compare_mode == "suggested" and self._analysis and self._analysis.cr is not None:
            return self._analysis.cr.suggested
        if self.compare_mode == "mine" and self._analysis and self._analysis.cr is not None:
            return self._analysis.cr.declared
        return None

    def _options_changed(self):
        self.on_options_changed()

    def _manual_changed(self, _event=None):
        if self._options_job is not None:
            try:
                self.after_cancel(self._options_job)
            except (tk.TclError, ValueError):
                pass
        self._options_job = self.after(450, self.on_options_changed)

    def _compare_changed(self, value: str):
        self.compare_mode = "suggested" if value == "Suggested CR" else "mine"
        self.on_options_changed()

    def _apply(self):
        if self._analysis and self._analysis.cr is not None:
            self.on_apply_cr(self._analysis.cr.suggested)

    # ---- tabs

    def set_kind(self, kind: str):
        """The kind of draft being written decides whether the Balance tab exists."""
        if kind == self.kind:
            return
        self.kind = kind
        if kind == "monsters":
            self.tabs.pack(fill="x", padx=8, pady=(2, 4), before=self.similar_frame)
        else:
            self.tabs.pack_forget()
            self._switch_tab("Similar")
        self.compare_mode = "auto"
        self._analysis = None
        self._show_message("Open or write something to compare it with the collection.")

    def _switch_tab(self, name: str):
        self._tab = name
        self.tabs.set(name)
        if name == "Balance":
            self.similar_frame.pack_forget()
            self.balance_frame.pack(fill="both", expand=True)
            self._render_balance()
        else:
            self.balance_frame.pack_forget()
            self.similar_frame.pack(fill="both", expand=True)
            self._render_similar()

    def select_balance(self):
        if self.kind == "monsters":
            self._switch_tab("Balance")

    # ---- showing results

    def set_busy(self, text: str):
        self.status.configure(text=text)

    def _show_message(self, text: str):
        for box in (self.similar_text, self.balance_text):
            box.clear()
            box.add(text + "\n", "muted")
        self.status.configure(text="")

    def set_analysis(self, analysis: DraftAnalysis, manual: bool = False):
        self._analysis = analysis
        parts = [u.title for u in analysis.units if u.title]
        values = [EVERYTHING_YOU_WROTE] + (parts if len({u.title for u in analysis.units}) > 1 else [])
        current = self.part_var.get()
        self.part_menu.configure(values=values)
        if current not in values:
            self.part_var.set(EVERYTHING_YOU_WROTE)
        self.status.configure(text="")
        self._render_similar()
        if self.kind == "monsters":
            self._render_balance()

    def _problem_lines(self, box: StudioText):
        if not self._analysis or not self._analysis.problems:
            return
        for line in self._analysis.problems:
            box.add("⚠ ", "warn")
            box.add(line + "\n", "indent")
        box.add("\n", "gap")

    def _render_similar(self):
        box = self.similar_text
        box.clear()
        a = self._analysis
        if a is None:
            box.add("Open or write something to compare it with the collection.\n", "muted")
            return
        self._problem_lines(box)
        part = self.part_var.get()
        matches = [m for m in a.matches if part == EVERYTHING_YOU_WROTE or m.matched_unit == part]
        omitted = [(n, c) for n, c in a.omitted if part == EVERYTHING_YOU_WROTE or n == part]
        if omitted and not self.manual_query():
            for name, count in omitted:
                box.add("• ", "muted")
                box.add(f"\"{name}\" matches more than {count - 1} things, so it reads as standard wording and "
                        f"is left out.\n", "small")
            box.add("(The limit is in Settings.)\n\n", "small")
        if self.manual_query():
            box.add(f"Content that looks like \"{self.manual_query()}\"\n", "heading")
        elif not matches:
            if a.units:
                box.add("Nothing in the collection reads much like this yet.\n", "heading")
                box.add("That does not mean it is balanced - only that the wording and the effect are new. "
                        "Open a few similar pieces of content in the reference panels to compare power.\n", "muted")
            else:
                box.add("Write a description to see what it resembles.\n", "muted")
            return
        else:
            box.add(f"{len(matches)} thing{'s' if len(matches) != 1 else ''} that read{'s' if len(matches) == 1 else ''} "
                    f"like what you wrote\n", "heading")
        for m in matches:
            e = m.entry
            box.add("\n", "gap")
            box.link(e.title, lambda m=m: self._open(m, False), "bold")
            if e.owner.lower() != e.title.lower():
                box.add(f"  {e.owner}", "muted")
            box.add(f"   {m.score:.0f}%\n", "score")
            tag = " · 2014" if e.legacy else (" · homebrew" if e.custom else "")
            box.add(f"{e.detail}{tag}\n", "small")
            if m.matched_unit:
                box.add("resembles your ", "small")
                box.add(f"{m.matched_unit}\n", "label")
            if m.shared_tags:
                box.add("Same effect: ", "accent")
                box.add("; ".join(m.shared_tags) + "\n")
            elif m.shared_terms:
                box.add("Shares: ", "muted")
                box.add(", ".join(m.shared_terms[:6]) + "\n", "muted")
            if m.snippet:
                box.add_highlighted(m.snippet, m.spans, "indent")
                box.add("\n")
            box.link("Open", lambda m=m: self._open(m, False))
            box.add("   ")
            box.link("Open beside it", lambda m=m: self._open(m, True))
            box.add("\n")
        box.to_top()

    def _open(self, match: HI.Match, new_panel: bool):
        e = match.entry
        whole = e.title.lower() == e.owner.lower() or e.family == "rules"
        hit = Hit(e.title, e.detail, e.family, e.category, e.target, entry=None if whole else e, section=e.section)
        self.on_open(hit, new_panel)

    # ---- the balance tab

    def _render_balance(self):
        box = self.balance_text
        box.clear()
        a = self._analysis
        report = a.cr if a else None
        if report is None:
            box.add("Write a monster with hit points, armor class and actions to see how it compares.\n", "muted")
            self.apply_button.configure(state="disabled")
            return
        self._problem_lines(box)
        suggested, declared = report.suggested, report.declared
        self.apply_button.configure(text=f"Use CR {suggested}", state="disabled" if declared == suggested
                                    and report.declared_set else "normal")
        effective = self.compare_mode if self.compare_mode != "auto" else ("mine" if report.declared_set
                                                                           else "suggested")
        self.compare_buttons.set("Suggested CR" if effective == "suggested" else "CR in the editor")

        box.add(f"Suggested CR {suggested}", "heading")
        parts = [f"defence CR {report.defensive}"]
        if report.offensive:
            parts.append(f"offence CR {report.offensive}")
        box.add("   " + " · ".join(parts) + "\n", "muted")
        if report.declared_set:
            if declared == suggested:
                box.add(f"This matches the CR {declared} set in the editor.\n", "good")
            else:
                box.add(f"The editor says CR {declared}.\n", "warn")
        else:
            box.add("No CR is set in the editor yet.\n", "muted")
        box.add("\n", "gap")

        box.add("Read from the stat block\n", "heading")
        for label, value in report.read:
            box.add(f"{label}: ", "label")
            box.add(value + "\n", "muted" if value == "none" else "")
        box.add("\n", "gap")

        box.add(f"Compared with CR {report.compared_with}", "heading")
        if report.peer_count:
            box.add(f"   {report.peer_count} official monsters of this CR\n", "muted")
        else:
            box.add("\n")
        for s in report.stats:
            mark, tag = {"high": ("▲", "warn"), "low": ("▼", "muted"), "ok": ("✔", "good")}[s.status]
            box.add(f"{mark} ", tag)
            box.add(f"{s.label} ", "bold")
            box.add(f"{s.value}", tag if s.status != "ok" else "")
            box.add(f"   typical {s.typical}\n", "muted")
            if s.status != "ok" and s.guideline and s.guideline != s.typical:
                box.add(f"   DMG table: {s.guideline}\n", "small")
            if s.peers:
                box.add(f"   {s.peers}\n", "small")
        if report.warnings:
            box.add("\n", "gap")
            box.add("Higher than typical\n", "heading")
            for w in report.warnings:
                box.add("• ", "warn")
                box.add(w + "\n", "indent")
        notes = [n for n in report.notes if n]
        if notes:
            box.add("\n", "gap")
            box.add("Worth knowing\n", "heading")
            for n in notes:
                box.add("• ", "muted")
                box.add(n + "\n", "indent")

        if a.closest:
            box.add("\n", "gap")
            box.add("Official monsters with the nearest numbers\n", "heading")
            for m, nums in a.closest:
                box.link(m.name, lambda m=m: self.on_open(Hit(m.name, "", "monsters", "monster", m.name), False), "bold")
                dmg = f", {nums['dmg']:.0f} dmg" if nums.get("dmg") else ""
                box.add(f"   CR {m.challenge_rating} · AC {m.ac} · HP {m.hp}{dmg}\n", "small")

        box.add("\n", "gap")
        box.add("How this was worked out\n", "heading")
        for step in report.steps:
            box.add("• ", "muted")
            box.add(step + "\n", "small")
        box.add("Armor class and hit points follow the DMG's monster table, nudged towards what the monsters in "
                "your collection really have; damage counts every attack landing, as the table does.\n", "small")
        box.to_top()
