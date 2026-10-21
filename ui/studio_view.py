"""
Homebrew Studio: write new content with the rest of the collection beside it.

The page has three columns:

* the **editor** - the same editor the collection pages open for that kind of content (spell, feat, class,
  subclass, lineage, background, equipment, magic item, monster, rules page), inside the page instead of a dialog.
  Drafts are kept automatically; nothing reaches the collections until you publish;
* **Insights** - existing content that does what the draft does (so you do not remake Reliable Talent by
  accident) and, for a monster, whether its AC, HP, damage, immunities and resistances fit its CR;
* **reference panels** - as many panes as you like, each showing any spell, feature, monster or rule, to compare
  against the draft.

The work happens elsewhere: ``studio_service`` (index, drafts, analysis), ``homebrew_index`` (similarity),
``monster_cr`` (challenge rating), ``ui/editor_host`` (editors as panels).
"""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import homebrew_index as HI
import studio_store as SS
from studio_service import DraftAnalysis, Hit, Strictness, StudioService
from theme import get_theme_manager
from typography import ui_font
from ui.studio_insights import InsightsPanel
from ui.studio_panels import ReferencePanel
from ui.studio_text import StudioText

KIND_ORDER = ["spells", "feats", "classes", "subclasses", "lineages", "backgrounds", "equipment", "magic_items",
              "monsters", "rules"]
TICK_MS = 1200                 # how often the editor is read for changes
SAVE_DELAY_MS = 700
ANALYSIS_DELAY_MS = 450
MAX_PANELS = 4


# --------------------------------------------------------------------------- editors as panels

def make_editor(kind: str, parent, draft: SS.Draft, obj, spell_manager):
    """The embedded editor for a draft (``obj`` is None for a blank one)."""
    if kind == "spells":
        from ui.spell_editor import SpellEditorPanel
        return SpellEditorPanel(parent, "Spell", spell=obj, spell_manager=spell_manager)
    if kind == "feats":
        from ui.feats_view import FeatEditorPanel
        return FeatEditorPanel(parent, "Feat", feat=obj)
    if kind == "lineages":
        from lineage import get_lineage_manager
        from ui.lineages_view import LineageEditorPanel
        return LineageEditorPanel(parent, get_lineage_manager(), lineage=obj)
    if kind == "backgrounds":
        from background import get_background_manager
        from ui.backgrounds_view import BackgroundEditorPanel
        return BackgroundEditorPanel(parent, get_background_manager(), background=obj)
    if kind == "equipment":
        from ui.equipment_view import EquipmentEditorPanel
        return EquipmentEditorPanel(parent, "Equipment", item=obj)
    if kind == "magic_items":
        from ui.magic_item_view import MagicItemEditorPanel
        return MagicItemEditorPanel(parent, "Magic item", item=obj)
    if kind == "monsters":
        from ui.monster_view import MonsterEditorPanel
        return MonsterEditorPanel(parent, "Monster", monster=obj)
    if kind == "rules":
        from ui.rules_view import RuleEditorPanel
        return RuleEditorPanel(parent, "Rules page", page=obj)
    if kind == "classes":
        from ui.class_editor import ClassEditorPanel
        return ClassEditorPanel(parent, class_def=obj)
    if kind == "subclasses":
        from character_class import get_class_manager
        from ui.class_editor import SubclassEditorPanel
        parent_class = get_class_manager().get_class(draft.parent or getattr(obj, "parent_class", ""))
        if parent_class is None:
            raise ValueError(f"The class '{draft.parent}' this subclass belongs to is not installed.")
        return SubclassEditorPanel(parent, parent_class, subclass=obj)
    raise ValueError(f"No editor for {kind}")


def _relabel_buttons(root: tk.Misc) -> None:
    """The editors say Save / Cancel; in the Studio Save keeps the draft and Cancel just closes it."""
    for child in root.winfo_children():
        if isinstance(child, ctk.CTkButton):
            try:
                text = child.cget("text")
            except Exception:
                text = ""
            if text == "Cancel":
                child.configure(text="Close draft")
            elif text.startswith("Save") and text != "Save draft":
                child.configure(text="Save draft")
        _relabel_buttons(child)


class _PickDialog(ctk.CTkToplevel):
    """Choose one of a list (used to pick the class a new subclass belongs to)."""

    def __init__(self, parent, title: str, prompt: str, values: List[str]):
        super().__init__(parent)
        self.result: Optional[str] = None
        self.title(title)
        self.geometry("380x170")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        theme = get_theme_manager()
        ctk.CTkLabel(self, text=prompt, font=ui_font("body"), wraplength=340, justify="left").pack(
            anchor="w", padx=20, pady=(20, 8))
        self.var = ctk.StringVar(value=values[0] if values else "")
        ctk.CTkOptionMenu(self, values=values or [""], variable=self.var, width=340).pack(padx=20)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(row, text="OK", width=90, fg_color=theme.get_current_color("accent_primary"),
                      command=self._ok).pack(side="right")
        ctk.CTkButton(row, text="Cancel", width=90, fg_color="transparent", border_width=1,
                      text_color=theme.get_current_color("text_primary"), command=self.destroy).pack(side="right",
                                                                                                      padx=8)
        self.after(60, self._grab)

    def _grab(self):
        try:
            self.grab_set()
            self.focus()
        except tk.TclError:
            pass

    def _ok(self):
        self.result = self.var.get() or None
        self.destroy()


class _ExistingDialog(ctk.CTkToplevel):
    """Pick an existing piece of content to start a draft from."""

    def __init__(self, parent, service: StudioService):
        super().__init__(parent)
        self.service = service
        self.result: Optional[Hit] = None
        self.title("Start from existing content")
        self.geometry("520x520")
        self.transient(parent.winfo_toplevel())
        theme = get_theme_manager()
        ctk.CTkLabel(self, text="Start a draft from a copy of something that already exists.",
                     font=ui_font("body"), wraplength=480, justify="left").pack(anchor="w", padx=18, pady=(18, 6))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=18)
        self.kind_var = ctk.StringVar(value="Spells")
        labels = list(self._CATEGORY)
        ctk.CTkOptionMenu(row, values=labels, variable=self.kind_var, width=150, command=lambda _v: self._search()
                          ).pack(side="left", padx=(0, 6))
        self.entry = ctk.CTkEntry(row, placeholder_text="Type a name...")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", lambda _e: self._search())
        self.results = StudioText(self, bg_role="bg_secondary")
        self.results.pack(fill="both", expand=True, padx=18, pady=12)
        ctk.CTkButton(self, text="Cancel", width=90, fg_color="transparent", border_width=1,
                      text_color=theme.get_current_color("text_primary"), command=self.destroy).pack(
            anchor="e", padx=18, pady=(0, 14))
        self.after(60, self._grab)
        self.entry.focus_set()

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    _CATEGORY = {"Spells": "spell", "Feats": "feat", "Classes": "class", "Subclasses": "subclass",
                 "Lineages": "lineage", "Backgrounds": "background", "Equipment": "equipment",
                 "Magic items": "magic_item", "Monsters": "monster", "Rules pages": "rule"}

    def _search(self):
        query = self.entry.get().strip()
        self.results.clear()
        if not query:
            return
        category = self._CATEGORY.get(self.kind_var.get(), "")
        targets = [t for t in self.service._targets if t.category == category]
        from object_links import search_links
        found = search_links(query, targets, limit=14)
        if not found:
            self.results.add("Nothing found.", "muted")
        for t in found:
            self.results.link(t.label, lambda t=t: self._choose(t), "bold")
            self.results.add(f"   {t.subtitle}\n", "small")

    def _choose(self, target):
        self.result = Hit(target.label, target.subtitle, "", target.category, target.name)
        self.destroy()


# --------------------------------------------------------------------------- the page

class StudioView(ctk.CTkFrame):
    """The Homebrew Studio page."""

    def __init__(self, parent, state: dict, *, spell_manager=None, service: Optional[StudioService] = None,
                 on_back: Optional[Callable[[], None]] = None, on_published: Optional[Callable[[], None]] = None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.state = state
        self.service = service or StudioService(spell_manager)
        self.on_back = on_back
        self.on_published = on_published
        self.panels: List[ReferencePanel] = []
        self.active_panel: Optional[ReferencePanel] = None
        self.draft: Optional[SS.Draft] = None
        self.editor = None
        self._editor_error: Optional[ctk.CTkLabel] = None
        self._last_record: Optional[dict] = None
        self._last_obj = None
        self._chips: Dict[str, dict] = {}
        self._alive = True
        self._jobs: Dict[str, Optional[str]] = {"tick": None, "save": None, "analysis": None, "poll": None,
                                                "index": None}
        self._token = 0
        self._done: "queue.Queue" = queue.Queue()
        self._indexing_notice = False
        c = self.theme.get_current_color

        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=16, pady=12)

        # ---- header
        head = ctk.CTkFrame(outer, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        if on_back:
            ctk.CTkButton(head, text="← Game Tools", width=110, height=32, fg_color=c("button_normal"),
                          hover_color=c("button_hover"), text_color=c("text_primary"), command=on_back
                          ).pack(side="left", padx=(0, 14))
        ctk.CTkLabel(head, text="Homebrew Studio", font=ui_font("title", 26, bold=True)).pack(side="left")
        self.status = ctk.CTkLabel(head, text="", font=ui_font("small"), text_color=c("text_secondary"))
        self.status.pack(side="left", padx=16)
        self.new_button = ctk.CTkButton(head, text="＋ New", width=90, height=32, fg_color=c("accent_primary"),
                                        hover_color=c("accent_hover"), text_color=c("text_on_accent"),
                                        command=self._show_new_menu)
        self.new_button.pack(side="right")
        self.drafts_button = ctk.CTkButton(head, text="Drafts ▾", width=90, height=32, fg_color=c("button_normal"),
                                           hover_color=c("button_hover"), text_color=c("text_primary"),
                                           command=self._show_drafts_menu)
        self.drafts_button.pack(side="right", padx=8)
        ctk.CTkButton(head, text="＋ Panel", width=84, height=32, fg_color=c("button_normal"),
                      hover_color=c("button_hover"), text_color=c("text_primary"),
                      command=lambda: self._add_panel(focus=True)).pack(side="right")

        self.chip_row = ctk.CTkFrame(outer, fg_color="transparent", height=30)
        self.chip_row.pack(fill="x", pady=(0, 6))

        # ---- the three columns
        self.paned = tk.PanedWindow(outer, orient=tk.HORIZONTAL, sashwidth=8, sashrelief=tk.RAISED, handlesize=0,
                                    opaqueresize=False, sashcursor="sb_h_double_arrow")
        self.paned.pack(fill="both", expand=True)
        self._paint_panes()

        self.editor_pane = ctk.CTkFrame(self.paned, fg_color=c("bg_primary"), corner_radius=8)
        bar = ctk.CTkFrame(self.editor_pane, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(8, 0))
        self.kind_label = ctk.CTkLabel(bar, text="", font=ui_font("subheading", 14, bold=True), anchor="w")
        self.kind_label.pack(side="left")
        self.menu_button = ctk.CTkButton(bar, text="⋯", width=34, height=28, fg_color=c("button_normal"),
                                         hover_color=c("button_hover"), text_color=c("text_primary"),
                                         command=self._show_draft_menu)
        self.publish_button = ctk.CTkButton(bar, text="Publish to collection", height=28, fg_color=c("button_success"),
                                            hover_color=c("button_success_hover"), text_color=c("text_primary"),
                                            command=self.publish)
        self.menu_button.pack(side="right")
        self.publish_button.pack(side="right", padx=(0, 6))
        self.editor_host = ctk.CTkFrame(self.editor_pane, fg_color="transparent")
        self.editor_host.pack(fill="both", expand=True, padx=2, pady=(4, 2))

        self.insights = InsightsPanel(self.paned, on_open=self._open_hit, on_options_changed=self._schedule_analysis,
                                      on_apply_cr=self._apply_cr)

        self.refs_pane = ctk.CTkFrame(self.paned, fg_color="transparent")
        self.refs = tk.PanedWindow(self.refs_pane, orient=tk.HORIZONTAL, sashwidth=8, sashrelief=tk.RAISED,
                                   handlesize=0, opaqueresize=False, sashcursor="sb_h_double_arrow")
        self.refs.pack(fill="both", expand=True)
        self.refs_hint = ctk.CTkLabel(self.refs_pane, text="", font=ui_font("body"),
                                      text_color=c("text_secondary"), wraplength=300, justify="left")
        self._paint_panes()

        self.paned.add(self.editor_pane, minsize=430, width=620, stretch="always")
        self.paned.add(self.insights, minsize=300, width=400, stretch="never")
        self.paned.add(self.refs_pane, minsize=280, width=460, stretch="always")

        self.welcome = ctk.CTkFrame(self.editor_host, fg_color="transparent")
        self._build_welcome()

        self.theme.add_listener(self._paint_panes)
        self.bind("<Destroy>", self._on_destroy, add="+")

        # ---- start up
        self.service.ensure_index()
        self._restore_panels()
        self._restore_drafts()
        self._jobs["tick"] = self.after(TICK_MS, self._tick)
        self._jobs["index"] = self.after(250, self._poll_index)

    # ------------------------------------------------------------------ small helpers

    def _paint_panes(self):
        try:
            sash = self.theme.get_current_color("pane_sash")
            self.paned.configure(bg=sash)
            self.refs.configure(bg=sash)
        except (tk.TclError, AttributeError):
            pass

    def _say(self, text: str):
        try:
            self.status.configure(text=text)
        except tk.TclError:
            pass

    def _cancel(self, name: str):
        job = self._jobs.get(name)
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._jobs[name] = None

    def _on_destroy(self, event):
        if event.widget is not self:
            return
        self._alive = False
        for name in list(self._jobs):
            self._cancel(name)
        try:
            self.theme.remove_listener(self._paint_panes)
        except Exception:
            pass

    def destroy(self):
        self.commit_pending_edits()
        self._alive = False
        super().destroy()

    # ------------------------------------------------------------------ welcome screen

    def _build_welcome(self):
        c = self.theme.get_current_color
        box = self.welcome
        ctk.CTkLabel(box, text="What are you making?", font=ui_font("title", 22, bold=True)).pack(
            anchor="w", padx=24, pady=(40, 4))
        ctk.CTkLabel(box, text="Write it here with the rest of the collection beside you. Insights points out "
                               "existing content that already does the same thing, and checks a monster's numbers "
                               "against its CR. Nothing is added to your collections until you publish.",
                     font=ui_font("body"), text_color=c("text_secondary"), wraplength=520, justify="left").pack(
            anchor="w", padx=24, pady=(0, 16))
        grid = ctk.CTkFrame(box, fg_color="transparent")
        grid.pack(anchor="w", padx=20)
        for i, kind in enumerate(KIND_ORDER):
            ctk.CTkButton(grid, text=f"{SS.KIND_ICONS[kind]}  {SS.KINDS[kind]}", width=160, height=36,
                          fg_color=c("button_normal"), hover_color=c("button_hover"), text_color=c("text_primary"),
                          anchor="w", command=lambda k=kind: self.new_draft(k)).grid(row=i // 2, column=i % 2,
                                                                                    padx=4, pady=4)
        ctk.CTkButton(box, text="Start from existing content...", height=34, fg_color="transparent", border_width=1,
                      text_color=c("text_primary"), command=self.new_from_existing).pack(
            anchor="w", padx=24, pady=(14, 0))

    # ------------------------------------------------------------------ drafts and tabs

    @property
    def store(self) -> SS.StudioStore:
        return self.service.store

    def _restore_drafts(self):
        ids = [i for i in self.state.get("open", []) if self.store.get(i)]
        self.state["open"] = ids
        if not ids:
            self._show_welcome()
            self._refresh_chips()
            return
        active = self.state.get("active")
        self._refresh_chips()
        self.open_draft(active if active in ids else ids[-1], force=True)

    def _show_welcome(self):
        self.draft = None
        self.editor = None
        self._last_record = self._last_obj = None
        self.kind_label.configure(text="")
        self.publish_button.configure(state="disabled")
        self.menu_button.configure(state="disabled")
        self.welcome.pack(fill="both", expand=True)
        self.insights.set_kind("")

    def _clear_editor(self):
        if self.editor is not None:
            try:
                self.editor.pack_forget()
                self.editor.destroy()
            except tk.TclError:
                pass
        self.editor = None
        if self._editor_error is not None:
            self._editor_error.destroy()
            self._editor_error = None
        self.welcome.pack_forget()

    def new_draft(self, kind: str, name: str = "", record: Optional[dict] = None, parent: str = "") -> Optional[SS.Draft]:
        if kind == "subclasses" and not parent:
            from character_class import get_class_manager
            names = sorted(c.name for c in get_class_manager().classes)
            dialog = _PickDialog(self, "New subclass", "Which class does the subclass belong to?", names)
            self.wait_window(dialog)
            if not dialog.result:
                return None
            parent = dialog.result
        draft = self.store.new(kind, name, record, parent)
        self.state.setdefault("open", []).append(draft.id)
        self.store.save()
        self.open_draft(draft.id)
        return draft

    def new_from_existing(self):
        dialog = _ExistingDialog(self, self.service)
        self.wait_window(dialog)
        hit = dialog.result
        if hit is None:
            return
        target = self.service.target(hit.category, hit.name)
        obj = target.get_object() if target is not None else None
        if obj is None:
            messagebox.showwarning("Not found", f"Could not load '{hit.name}'.", parent=self.winfo_toplevel())
            return
        kind = {"spell": "spells", "feat": "feats", "lineage": "lineages", "background": "backgrounds",
                "magic_item": "magic_items", "equipment": "equipment", "monster": "monsters", "rule": "rules",
                "class": "classes", "subclass": "subclasses"}.get(hit.category)
        if hit.category == "rule":
            obj = getattr(obj, "page", obj)
        if kind is None:
            return
        try:
            record = SS.object_to_record(kind, obj, self.service.spell_manager)
        except Exception as e:
            messagebox.showwarning("Not copied", f"Could not copy '{hit.name}' ({e}).", parent=self.winfo_toplevel())
            return
        import copy
        record = copy.deepcopy(record)
        name = f"{record.get('name', hit.title)} (variant)"
        record["name"] = name
        record["is_official"] = False
        record["is_custom"] = True
        if kind == "monsters":
            record["spell_only"], record["spell_name"] = False, ""
        record.pop("original_name", None)
        parent = record.get("parent_class", "") if kind == "subclasses" else ""
        self.new_draft(kind, name, record, parent)

    def open_draft(self, draft_id: str, force: bool = False):
        draft = self.store.get(draft_id)
        if draft is None:
            return
        if self.draft is draft and not force:
            return
        self._snapshot()
        self._flush_save()
        open_ids: List[str] = self.state.setdefault("open", [])
        if draft_id not in open_ids:
            open_ids.append(draft_id)
        self.state["active"] = draft_id
        self.store.last_draft = draft_id
        self._clear_editor()
        self.draft = draft
        self.kind_label.configure(text=f"{SS.KIND_ICONS[draft.kind]}  {SS.KINDS[draft.kind]}")
        self.publish_button.configure(state="normal")
        self.menu_button.configure(state="normal")
        self.insights.set_kind(draft.kind)
        self._build_editor(draft)
        self._refresh_chips()
        self._schedule_analysis()

    def _build_editor(self, draft: SS.Draft):
        try:
            from ui import handle_budget
            handle_budget.ensure_headroom()
        except Exception:
            pass
        obj = None
        if draft.record:
            try:
                obj = SS.record_to_object(draft.kind, draft.record, self.service.spell_manager)
            except Exception as e:
                print(f"Studio: could not read the draft '{draft.name}': {e}")
                obj = None
        try:
            editor = make_editor(draft.kind, self.editor_host, draft, obj, self.service.spell_manager)
        except Exception as e:
            self._editor_error = ctk.CTkLabel(self.editor_host, text=f"This draft cannot be opened: {e}",
                                              font=ui_font("body"), wraplength=480, justify="left",
                                              text_color=self.theme.get_current_color("button_danger"))
            self._editor_error.pack(anchor="w", padx=20, pady=30)
            self.editor = None
            return
        editor.on_finish = self._editor_finished
        editor.pack(fill="both", expand=True)
        self.editor = editor
        try:
            _relabel_buttons(editor)
        except Exception:
            pass
        self._last_record = None
        self._snapshot(baseline=True)

    def _editor_finished(self, result):
        """Save (the editor accepted the form) or Close draft (cancelled)."""
        if result is None:
            self.close_draft(self.draft.id if self.draft else "")
            return
        self._snapshot()
        self._flush_save()
        self._say(f"Draft saved {time.strftime('%H:%M')}")

    def close_draft(self, draft_id: str):
        if not draft_id:
            return
        if self.draft is not None and self.draft.id == draft_id:
            self._snapshot()
            self._flush_save()
        ids: List[str] = self.state.setdefault("open", [])
        if draft_id in ids:
            index = ids.index(draft_id)
            ids.remove(draft_id)
        else:
            index = 0
        if self.draft is not None and self.draft.id == draft_id:
            self._clear_editor()
            self.draft = None
            if ids:
                self.open_draft(ids[min(index, len(ids) - 1)], force=True)
            else:
                self.state["active"] = ""
                self._show_welcome()
        self._refresh_chips()

    def delete_draft(self):
        draft = self.draft
        if draft is None:
            return
        if not messagebox.askyesno("Delete draft", f"Delete the draft '{draft.title()}'? This cannot be undone.",
                                   parent=self.winfo_toplevel()):
            return
        draft_id = draft.id
        ids: List[str] = self.state.setdefault("open", [])
        if draft_id in ids:
            ids.remove(draft_id)
        self._clear_editor()
        self.draft = None
        self.store.delete(draft_id)
        self.store.save()
        if ids:
            self.open_draft(ids[-1], force=True)
        else:
            self._show_welcome()
        self._refresh_chips()

    def duplicate_draft(self):
        if self.draft is None:
            return
        self._snapshot()
        copy_ = self.store.duplicate(self.draft)
        self.state.setdefault("open", []).append(copy_.id)
        self.store.save()
        self.open_draft(copy_.id)

    # ---- the tab strip

    def _chip_text(self, draft: SS.Draft) -> str:
        title = draft.title()
        if len(title) > 22:
            title = title[:21] + "…"
        mark = " ✓" if draft.published_as and draft.published_as == draft.name else ""
        return f"{SS.KIND_ICONS[draft.kind]} {title}{mark}"

    def _refresh_chips(self):
        c = self.theme.get_current_color
        wanted = [self.store.get(i) for i in self.state.get("open", [])]
        wanted = [d for d in wanted if d is not None]
        ids = {d.id for d in wanted}
        for draft_id in list(self._chips):
            if draft_id not in ids:
                self._chips.pop(draft_id)["frame"].destroy()
        for draft in wanted:
            chip = self._chips.get(draft.id)
            if chip is None:
                frame = ctk.CTkFrame(self.chip_row, fg_color="transparent")
                button = ctk.CTkButton(frame, text="", height=26, corner_radius=6, anchor="w",
                                       command=lambda i=draft.id: self.open_draft(i))
                close = ctk.CTkButton(frame, text="✕", width=22, height=26, corner_radius=6, fg_color="transparent",
                                      hover_color=c("button_hover"), text_color=c("text_secondary"),
                                      command=lambda i=draft.id: self.close_draft(i))
                button.pack(side="left")
                close.pack(side="left", padx=(0, 4))
                chip = self._chips[draft.id] = {"frame": frame, "button": button, "close": close}
            chip["button"].configure(text=self._chip_text(draft))
        for draft in wanted:           # keep the order of the open list
            self._chips[draft.id]["frame"].pack_forget()
        for draft in wanted:
            self._chips[draft.id]["frame"].pack(side="left")
        for draft in wanted:
            active = self.draft is not None and draft.id == self.draft.id
            self._chips[draft.id]["button"].configure(
                fg_color=c("accent_primary") if active else c("button_normal"),
                hover_color=c("accent_hover") if active else c("button_hover"),
                text_color=c("text_on_accent") if active else c("text_primary"))

    # ---- menus

    def _popup(self, menu: tk.Menu, widget: tk.Misc):
        try:
            menu.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())
        finally:
            menu.grab_release()

    def _show_new_menu(self):
        menu = tk.Menu(self, tearoff=0)
        for kind in KIND_ORDER:
            menu.add_command(label=f"{SS.KIND_ICONS[kind]}  {SS.KINDS[kind]}", command=lambda k=kind: self.new_draft(k))
        menu.add_separator()
        menu.add_command(label="From existing content...", command=self.new_from_existing)
        self._popup(menu, self.new_button)

    def _show_drafts_menu(self):
        menu = tk.Menu(self, tearoff=0)
        drafts = self.store.sorted()
        if not drafts:
            menu.add_command(label="No drafts yet", state="disabled")
        for d in drafts[:30]:
            published = "  ✓ published" if d.published_as and d.published_as == d.name else ""
            menu.add_command(label=f"{SS.KIND_ICONS[d.kind]}  {d.title()}  ·  {SS.KINDS[d.kind]}{published}",
                             command=lambda i=d.id: self.open_draft(i))
        self._popup(menu, self.drafts_button)

    def _show_draft_menu(self):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Duplicate draft", command=self.duplicate_draft)
        menu.add_command(label="Export draft as JSON...", command=self.export_draft)
        menu.add_separator()
        menu.add_command(label="Close draft", command=lambda: self.close_draft(self.draft.id if self.draft else ""))
        menu.add_command(label="Delete draft...", command=self.delete_draft)
        self._popup(menu, self.menu_button)

    # ------------------------------------------------------------------ reading the editor

    def _snapshot(self, baseline: bool = False) -> bool:
        """Read the form. Stores the draft if it changed (never for the first read of an editor: ``baseline``)."""
        editor, draft = self.editor, self.draft
        if editor is None or draft is None:
            return False
        try:
            obj = editor.build_result(strict=False)
            record = SS.object_to_record(draft.kind, obj, self.service.spell_manager)
        except Exception:
            return False                       # half-typed numbers and the like: keep the last good copy
        self._last_obj = obj
        if baseline:
            self._last_record = record
            return True
        if record != self._last_record:
            self._last_record = record
            name = (getattr(obj, "name", "") or "").strip()
            if draft.kind == "subclasses":
                record["parent_class"] = draft.parent or record.get("parent_class", "")
            if self.store.update(draft, name, record):
                self._schedule_save()
                self._refresh_chips()
            self._schedule_analysis()
        return True

    def _tick(self):
        self._jobs["tick"] = None
        if not self._alive:
            return
        try:
            if self.editor is not None and self.winfo_ismapped():
                self._snapshot()
        except Exception as e:
            print(f"Studio: could not read the editor: {e}")
        if self._alive:
            self._jobs["tick"] = self.after(TICK_MS, self._tick)

    def _schedule_save(self):
        self._cancel("save")
        self._jobs["save"] = self.after(SAVE_DELAY_MS, self._flush_save)

    def _flush_save(self):
        self._cancel("save")
        if self.store.save():
            self._say(f"Draft saved {time.strftime('%H:%M')}")

    def commit_pending_edits(self):
        """Keep what is in the editor (called when the app closes or the page is left)."""
        try:
            if self.editor is not None:
                self._snapshot()
            self.store.panels = [dict(p.state) for p in self.panels if p.state]
            self.store.save()
        except Exception as e:
            print(f"Studio: could not keep the draft: {e}")

    # ------------------------------------------------------------------ insights

    def _schedule_analysis(self, delay: int = ANALYSIS_DELAY_MS):
        self._cancel("analysis")
        if self._alive:
            self._jobs["analysis"] = self.after(delay, self._start_analysis)

    def _start_analysis(self):
        self._jobs["analysis"] = None
        draft, obj = self.draft, self._last_obj
        if draft is None or obj is None or self._last_record is None:
            return
        if not self.service.ready:
            self.insights.set_busy("Indexing the collections...")
            self._indexing_notice = True
            return
        self._token += 1
        token = self._token
        record = dict(self._last_record)
        family = HI.KIND_FAMILY.get(draft.kind, "")
        families = self.insights.families(family)
        legacy = self.insights.include_legacy()
        strict = Strictness.from_settings(include_unofficial=self.insights.include_unofficial())
        manual = self.insights.manual_query()
        compare_to = self.insights.compare_to()
        kind, service = draft.kind, self.service
        self.insights.set_busy("Comparing...")

        def work():
            try:
                analysis = service.analyze(kind, obj, record, families=families, include_legacy=legacy, token=token,
                                           compare_to=compare_to, strict=strict)
                if manual:
                    analysis.matches = service.index.similar(
                        manual, families=families, include_legacy=legacy, limit=14, min_words=strict.min_words,
                        include_unofficial=strict.include_unofficial, min_score=strict.min_score)
                    analysis.omitted = []
                self._done.put((token, analysis))
            except Exception as e:             # never leave the panel on "Comparing..."
                print(f"Studio: comparison failed: {e}")
                self._done.put((token, e))

        threading.Thread(target=work, daemon=True, name="studio-analysis").start()
        if self._jobs["poll"] is None:
            self._jobs["poll"] = self.after(70, self._poll_analysis)

    def _poll_analysis(self):
        self._jobs["poll"] = None
        if not self._alive:
            return
        latest = None
        try:
            while True:
                latest = self._done.get_nowait()
        except queue.Empty:
            pass
        if latest is not None and latest[0] == self._token:
            if isinstance(latest[1], DraftAnalysis):
                self.insights.set_analysis(latest[1], manual=bool(self.insights.manual_query()))
            else:
                self.insights.set_busy("Could not compare this draft.")
            return
        if self._token:
            self._jobs["poll"] = self.after(70, self._poll_analysis)

    def _poll_index(self):
        self._jobs["index"] = None
        if not self._alive:
            return
        if self.service.ready:
            if self._indexing_notice:
                self._indexing_notice = False
                self._schedule_analysis(50)
            if self.service.is_stale() and not self.service.building:
                self.service.ensure_index()       # content changed while the page was open
            self._jobs["index"] = self.after(4000, self._poll_index)
        else:
            if self.service.error:
                self.insights.set_busy("The collections could not be indexed.")
            self._jobs["index"] = self.after(300, self._poll_index)

    def _apply_cr(self, cr: str):
        editor = self.editor
        if editor is None or not hasattr(editor, "cr_var"):
            return
        editor.cr_var.set(cr)
        try:
            editor._update_preview()
        except Exception:
            pass
        self._snapshot()
        self._schedule_analysis(50)

    # ------------------------------------------------------------------ reference panels

    def _restore_panels(self):
        saved = self.state.get("panels")
        if saved is None:
            saved = self.store.panels or [{}]
        for st in saved[:MAX_PANELS]:
            panel = self._add_panel(save=False)
            if st:
                self.after(60, lambda p=panel, s=dict(st): p.winfo_exists() and p.restore(s))
        self._relayout_panels()
        self._set_active(self.panels[0] if self.panels else None)

    def _add_panel(self, focus: bool = False, save: bool = True) -> ReferencePanel:
        if len(self.panels) >= MAX_PANELS:
            panel = self.panels[-1]
            self._set_active(panel)
            return panel
        panel = ReferencePanel(self.refs, self.service, on_close=self._remove_panel, on_activate=self._set_active)
        self.refs.add(panel, minsize=260, width=420, stretch="always")
        self.panels.append(panel)
        self._relayout_panels()
        self._set_active(panel)
        if focus:
            panel.entry.focus_set()
        if save:
            self._save_panels()
        return panel

    def _remove_panel(self, panel: ReferencePanel):
        if panel not in self.panels:
            return
        self.panels.remove(panel)
        try:
            self.refs.forget(panel)
        except tk.TclError:
            pass
        panel.destroy()
        if self.active_panel is panel:
            self.active_panel = None
            self._set_active(self.panels[-1] if self.panels else None)
        self._relayout_panels()
        self._save_panels()

    def _set_active(self, panel: Optional[ReferencePanel]):
        self.active_panel = panel
        for p in self.panels:
            try:
                p.set_active(p is panel and len(self.panels) > 1)
            except tk.TclError:
                pass

    def _relayout_panels(self):
        if self.panels:
            self.refs_hint.pack_forget()
            self.refs.pack(fill="both", expand=True)
        else:
            self.refs.pack_forget()
            self.refs_hint.configure(text="Reference panels open here. Press ＋ Panel, or open a result from "
                                          "Insights, to look at other content beside your draft.")
            self.refs_hint.pack(anchor="nw", padx=16, pady=20)

    def _save_panels(self):
        states = [dict(p.state) for p in self.panels]
        self.state["panels"] = states
        self.store.panels = states
        self.store.save()

    def _open_hit(self, hit: Hit, new_panel: bool = False):
        """Show a search result / similar match in the active panel, or in a new one."""
        if new_panel or not self.panels:
            if new_panel and len(self.panels) >= MAX_PANELS:
                panel = self.panels[-1]
            else:
                panel = self._add_panel(save=False)
        else:
            panel = self.active_panel or self.panels[0]
        panel.show_hit(hit)
        self._set_active(panel)
        self._save_panels()

    # ------------------------------------------------------------------ publishing and export

    def publish(self):
        draft, editor = self.draft, self.editor
        if draft is None or editor is None:
            return
        parent = self.winfo_toplevel()
        try:
            obj = editor.build_result(strict=True)
        except ValueError as e:
            messagebox.showwarning("Not ready to publish", str(e), parent=parent)
            return
        except Exception as e:
            messagebox.showwarning("Not ready to publish", f"The form could not be read ({e}).", parent=parent)
            return
        record = SS.object_to_record(draft.kind, obj, self.service.spell_manager)
        if draft.kind == "subclasses":
            record["parent_class"] = draft.parent or record.get("parent_class", "")
        self.store.update(draft, obj.name, record)
        self._last_record = record
        status, name = SS.clash(draft, self.service.spell_manager)
        label = SS.KINDS[draft.kind].lower()
        if status == "official":
            messagebox.showwarning("Name already used", f"'{name}' is the name of official content, which is never "
                                   f"replaced. Choose another name.", parent=parent)
            return
        if status == "custom":
            question = f"You already have a {label} called '{name}'. Replace it with this draft?"
        else:
            question = f"Add '{name}' to your {label} collection?"
        if not messagebox.askyesno("Publish", question, parent=parent):
            return
        report = SS.publish(draft, self.service.spell_manager, link_mentions=True)
        self.store.save()
        self.service.invalidate()
        self._refresh_chips()
        if report.imported:
            self._say(f"Published '{name}'.")
            if self.on_published:
                try:
                    self.on_published()
                except Exception as e:
                    print(f"Studio: collections not refreshed: {e}")
        from ui.collections_view import ImportReportDialog
        ImportReportDialog(parent, report, [], [])
        self._schedule_analysis(200)

    def export_draft(self):
        draft = self.draft
        if draft is None or self.editor is None:
            return
        self._snapshot()
        import content_io
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(), title="Export draft", defaultextension=".json",
            initialfile=f"{(draft.name or 'draft').replace(' ', '_')}.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            record = dict(draft.record)
            record["name"] = draft.name
            content_io.write_bundle(path, {"format": content_io.FORMAT_NAME, "version": content_io.FORMAT_VERSION,
                                           draft.kind: [record]})
            self._say("Draft exported.")
        except Exception as e:
            messagebox.showerror("Export failed", str(e), parent=self.winfo_toplevel())
