"""
Reference panels for the Homebrew Studio: look at any other content next to the draft you are writing.

Each panel has its own search box (spells, feats, class features, monsters, rules... anything in the
collections, down to a single feature of a class), and shows what you open the way the collection page does.
Several panels can sit side by side so two or three existing pieces of content can be compared with the draft.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

import homebrew_index as HI
from studio_service import Hit, StudioService
from theme import get_theme_manager
from typography import ui_font
from ui.studio_text import StudioText

ALL_FAMILIES = "Everything"
FAMILY_CHOICES = [ALL_FAMILIES] + list(HI.FAMILIES.values())
_FAMILY_BY_LABEL = {label: key for key, label in HI.FAMILIES.items()}

SEARCH_DEBOUNCE_MS = 180


def family_key(label: str) -> Optional[str]:
    """The index family for a menu label (None = everything)."""
    return _FAMILY_BY_LABEL.get(label)


class ReferencePanel(ctk.CTkFrame):
    """One pane that shows existing content."""

    def __init__(self, parent, service: StudioService, *, on_close: Optional[Callable[["ReferencePanel"], None]] = None,
                 on_activate: Optional[Callable[["ReferencePanel"], None]] = None):
        self.theme = get_theme_manager()
        c = self.theme.get_current_color
        super().__init__(parent, fg_color=c("bg_secondary"), corner_radius=8, border_width=2,
                         border_color=c("border"))
        self.service = service
        self.on_close = on_close
        self.on_activate = on_activate
        self.state: Dict[str, str] = {}              # what is shown: category, name, section
        self._hits: List[Hit] = []
        self._search_job: Optional[str] = None
        self._resize_job: Optional[str] = None
        self._built_width = 0
        self._detail: Optional[tk.Widget] = None
        self._active = False

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(8, 2))
        self.title_label = ctk.CTkLabel(head, text="Reference", font=ui_font("subheading", 14, bold=True), anchor="w")
        self.title_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(head, text="✕", width=26, height=24, fg_color="transparent", hover_color=c("button_hover"),
                      text_color=c("text_secondary"), command=self._close).pack(side="right")
        self.copy_button = ctk.CTkButton(head, text="Copy link", width=70, height=24, fg_color="transparent",
                                         hover_color=c("button_hover"), text_color=c("text_secondary"),
                                         font=ui_font("small"), command=self._copy_link)
        self.copy_button.pack(side="right", padx=(0, 2))

        search = ctk.CTkFrame(self, fg_color="transparent")
        search.pack(fill="x", padx=8, pady=(2, 4))
        self.kind_var = ctk.StringVar(value=ALL_FAMILIES)
        self.kind_menu = ctk.CTkOptionMenu(search, values=FAMILY_CHOICES, variable=self.kind_var, width=118,
                                           height=28, dynamic_resizing=False, command=lambda _v: self._search_now())
        self.kind_menu.pack(side="left", padx=(0, 6))
        self.entry = ctk.CTkEntry(search, height=28, placeholder_text="Find something to look at...")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<Escape>", lambda _e: self._hide_results())
        self.entry.bind("<FocusIn>", lambda _e: self._activate(), add="+")

        self.results = StudioText(self, bg_role="bg_tertiary", font_size=12)
        self.results.text.configure(height=7)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=4, pady=(0, 6))
        self._placeholder("Search above, or choose a result in Similar, to look at it here.")
        self.bind("<Button-1>", lambda _e: self._activate(), add="+")
        self.body.bind("<Configure>", self._on_resize, add="+")

    # ---- activation

    def _activate(self):
        if self.on_activate:
            self.on_activate(self)

    def set_active(self, active: bool):
        self._active = active
        c = self.theme.get_current_color
        self.configure(border_color=c("accent_primary") if active else c("border"))

    def _close(self):
        if self.on_close:
            self.on_close(self)

    # ---- searching

    def _on_key(self, _event=None):
        self._activate()
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except (tk.TclError, ValueError):
                pass
        self._search_job = self.after(SEARCH_DEBOUNCE_MS, self._search_now)

    def _search_now(self):
        self._search_job = None
        query = self.entry.get().strip()
        if not query:
            self._hide_results()
            return
        family = family_key(self.kind_var.get())
        self._hits = self.service.search(query, [family] if family else None, limit=12)
        self.results.clear()
        if not self._hits:
            if self.service.building and not self.service.ready:
                self.results.add("Still indexing the collections...", "muted")
            else:
                self.results.add("Nothing found.", "muted")
        for hit in self._hits:
            self.results.link(hit.title, lambda h=hit: self._pick(h), "bold")
            self.results.add(f"   {hit.detail}\n", "small")
        if not self.results.winfo_ismapped():
            self.results.pack(fill="x", padx=8, pady=(0, 4), before=self.body)
        self.results.to_top()

    def _hide_results(self):
        if self.results.winfo_ismapped():
            self.results.pack_forget()

    def _pick(self, hit: Hit):
        self._hide_results()
        self.entry.delete(0, "end")
        self.show_hit(hit)

    # ---- showing things

    def _clear_body(self):
        for child in self.body.winfo_children():
            try:
                child.destroy()
            except tk.TclError:
                pass
        self._detail = None

    def _placeholder(self, text: str):
        self._clear_body()
        ctk.CTkLabel(self.body, text=text, font=ui_font("body"), text_color=self.theme.get_text_secondary(),
                     wraplength=260, justify="left").pack(anchor="w", padx=10, pady=14)
        self.title_label.configure(text="Reference")
        self.state = {}

    def _wrap(self) -> int:
        width = self.body.winfo_width()
        scaling = 1.0
        try:
            scaling = self.body._get_widget_scaling()
        except Exception:
            pass
        width = int(width / scaling) if width > 1 else 380
        return max(240, width - 56)

    def _on_resize(self, _event=None):
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except (tk.TclError, ValueError):
                pass
        self._resize_job = self.after(350, self._rebuild_if_resized)

    def _rebuild_if_resized(self):
        self._resize_job = None
        if self.state and abs(self._wrap() - self._built_width) > 60:
            self.restore(dict(self.state))

    def show_hit(self, hit: Hit):
        """Show a search result or a Similar match."""
        entry = hit.entry
        if entry is not None and hit.category != "rule" and entry.title.lower() != entry.owner.lower():
            self.show_feature(entry)
        else:
            self.show_target(hit.category, hit.name)

    def show_entry(self, entry: HI.Entry):
        if entry.title.lower() != entry.owner.lower() or entry.family == "rules" and entry.section:
            if entry.family == "rules":
                self.show_target("rule", entry.target)
            else:
                self.show_feature(entry)
        else:
            self.show_target(entry.category, entry.owner)

    def show_feature(self, entry: HI.Entry):
        """One feature of a class / monster / lineage / background: its text, with a way to open its owner."""
        self._clear_body()
        self._built_width = self._wrap()
        self.state = {"category": entry.category, "name": entry.owner, "feature": entry.title,
                      "detail": entry.detail, "text": entry.text}
        self.title_label.configure(text=entry.title)
        c = self.theme.get_current_color
        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        self._detail = scroll
        ctk.CTkLabel(scroll, text=entry.title, font=ui_font("title", 20, bold=True), anchor="w", justify="left",
                     wraplength=self._built_width).pack(anchor="w", pady=(2, 2))
        ctk.CTkLabel(scroll, text=entry.detail, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     anchor="w", justify="left", wraplength=self._built_width).pack(anchor="w", pady=(0, 8))
        from ui.rich_text_utils import render_description_blocks
        holder = ctk.CTkFrame(scroll, fg_color="transparent")
        holder.pack(fill="x", pady=(0, 8))
        render_description_blocks(holder, entry.text, self.theme, bg_color="bg_secondary", pady=(0, 2))
        ctk.CTkButton(scroll, text=f"Show the whole {entry.owner}", height=28, fg_color=c("button_normal"),
                      hover_color=c("button_hover"), text_color=c("text_primary"),
                      command=lambda: self.show_target(entry.category, entry.owner)).pack(anchor="w", pady=(4, 0))

    def show_target(self, category: str, name: str):
        """Show a whole object (spell, feat, class, monster, rules page...)."""
        target = self.service.target(category, name)
        self._clear_body()
        self._built_width = self._wrap()
        if target is None:
            self._placeholder(f"'{name}' could not be found. It may have been renamed or removed.")
            return
        self.state = {"category": category, "name": target.name}
        self.title_label.configure(text=target.label)
        from ui.object_link_widgets import LinkDetailView
        try:
            view = LinkDetailView(self.body, target, wrap=self._built_width)
        except Exception as e:                      # a broken record must not take the Studio down
            self._placeholder(f"Could not show '{name}' ({type(e).__name__}: {e}).")
            return
        view.pack(fill="both", expand=True)
        self._detail = view

    def restore(self, state: Dict[str, str]):
        """Show what ``state`` (from a saved layout) describes."""
        if not state:
            return
        if state.get("feature"):
            e = HI.Entry(id=-1, family="", title=state["feature"], owner=state.get("name", ""),
                         category=state.get("category", ""), text=state.get("text", ""),
                         detail=state.get("detail", ""))
            self.show_feature(e)
        elif state.get("name"):
            self.show_target(state.get("category", ""), state["name"])

    # ---- link markup

    def _copy_link(self):
        category, name = self.state.get("category"), self.state.get("name")
        if not category or not name:
            return
        from object_links import format_link_markup
        markup = format_link_markup(category, name, name.rsplit("#", 1)[-1])
        try:
            self.clipboard_clear()
            self.clipboard_append(markup)
            self.copy_button.configure(text="Copied")
            self.after(1400, lambda: self.copy_button.winfo_exists() and self.copy_button.configure(text="Copy link"))
        except tk.TclError:
            pass

    def destroy(self):
        for job in (self._search_job, self._resize_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
        super().destroy()
