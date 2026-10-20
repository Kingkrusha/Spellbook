"""
Rules View for D&D 5e Spellbook Application.

A searchable, filterable list of rules pages with the page itself beside it. Searching reads the
text of the pages (not just their names) and puts the best match first: "Stunned" opens the
Conditions page at its Stunned section, with every use of the word lit up.
"""

from ui.window_utils import center_on_parent
from ui.theme_listener import ThemeListenerMixin
import tkinter as tk
from tkinter import messagebox
from typing import List, Optional

import customtkinter as ctk

from rules import RuleHit, RulePage, get_rules_manager
from settings import get_settings_manager
from theme import get_theme_manager
from typography import ui_font
from ui.filter_widgets import SourceFilterDialog, SourceFilterMode, TagFilterDialog, TagFilterMode
from ui.label_text import LabeledLabel
from ui.rule_text import RuleTextView
from ui.scrollable_combobox import ScrollableComboBox
from ui.tag_editor import TagEditor
from ui.collection_page import CollectionPageMixin
from ui.virtual_list import VirtualListPanel
from ui.editor_host import DialogWindow, EditorBody, EmbeddedWindow

ALL_CATEGORIES = "All Categories"
DEFAULT_CATEGORY_TEXT = "Homebrew"
SORT_BOOK, SORT_NAME = "Book Order", "A to Z"
JUMP_PLACEHOLDER = "Jump to section..."


class RulesListPanel(VirtualListPanel):
    """The virtualized list of rules pages (or, while searching, of the best matches)."""

    TITLE = "Rules"
    NOUN = "page"

    def row_text(self, item) -> str:
        label = item.label() if isinstance(item, RuleHit) else item.name
        return f"* {label}" if getattr(item, "is_custom", False) else label

    def get_selected_page(self) -> Optional[RulePage]:
        item = self.get_selected()
        return item.page if isinstance(item, RuleHit) else item

    def select_page(self, name: str) -> bool:
        return self.select_by_name(name)


class RuleDetailPanel(ThemeListenerMixin, ctk.CTkFrame):
    """One rules page: its name and details above the text, with a jump list of its sections."""

    def __init__(self, parent, on_link=None, on_back=None):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._on_link = on_link
        self._on_back = on_back
        self._page: Optional[RulePage] = None
        self._section_choices = {}
        self._query = ""
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)

    def _on_theme_changed(self):
        try:
            self.configure(fg_color=self.theme.get_current_color('bg_primary'))
            self.category_badge.configure(fg_color=self.theme.get_current_color('accent_primary'))
        except tk.TclError:
            pass

    def _create_widgets(self):
        theme = self.theme
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=15, pady=(15, 0))

        self.name_label = ctk.CTkLabel(head, text="Select a rules page", font=ui_font("title", bold=True),
                                       wraplength=520, justify="left", anchor="w")
        self.name_label.pack(anchor="w", pady=(0, 5))

        self.badge_row = ctk.CTkFrame(head, fg_color="transparent")
        self.category_badge = ctk.CTkLabel(
            self.badge_row, text="", font=ui_font("small"),
            fg_color=theme.get_current_color('accent_primary'), corner_radius=5, padx=8, pady=2)
        self.category_badge.pack(side="left", padx=(0, 8))
        self.tags_label = ctk.CTkLabel(self.badge_row, text="", font=ui_font("body"),
                                       text_color=theme.get_current_color('accent_primary'))
        self.tags_label.pack(side="left")

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=15, pady=(8, 4))
        self.back_btn = ctk.CTkButton(
            bar, text="◀ Back", width=70, height=30,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=lambda: self._on_back() if self._on_back else None)
        self.back_btn.pack(side="left", padx=(0, 8))
        self.jump_var = ctk.StringVar(value=JUMP_PLACEHOLDER)
        self.jump_combo = ScrollableComboBox(
            bar, width=250, height=30, values=[JUMP_PLACEHOLDER], variable=self.jump_var,
            command=self._on_jump, state="readonly")
        self.jump_combo.pack(side="left")

        self.match_bar = ctk.CTkFrame(bar, fg_color="transparent")
        self.next_btn = ctk.CTkButton(self.match_bar, text="▼", width=30, height=30,
                                      fg_color=theme.get_current_color('button_normal'),
                                      hover_color=theme.get_current_color('button_hover'),
                                      text_color=theme.get_current_color('text_primary'),
                                      command=lambda: self._step(1))
        self.prev_btn = ctk.CTkButton(self.match_bar, text="▲", width=30, height=30,
                                      fg_color=theme.get_current_color('button_normal'),
                                      hover_color=theme.get_current_color('button_hover'),
                                      text_color=theme.get_current_color('text_primary'),
                                      command=lambda: self._step(-1))
        self.next_btn.pack(side="right")
        self.prev_btn.pack(side="right", padx=(0, 4))
        self.match_label = ctk.CTkLabel(self.match_bar, text="", font=ui_font("small"),
                                        text_color=theme.get_text_secondary())
        self.match_label.pack(side="right", padx=(0, 8))

        self.text_view = RuleTextView(self, on_link=self._on_link)
        self.text_view.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        self.foot = LabeledLabel(self, text="", font=ui_font("small"),
                                 text_color=theme.get_text_secondary(), anchor="w", justify="left")
        self.foot.pack(fill="x", padx=15, pady=(0, 10))

    # ------------------------------------------------------------------ showing a page

    def set_back_enabled(self, enabled: bool):
        self.back_btn.configure(state="normal" if enabled else "disabled")

    def show_page(self, page: Optional[RulePage], hit: Optional[RuleHit] = None, query: str = "",
                  section: Optional[int] = None):
        """Show ``page``. With a search ``query`` its words are lit up and the view opens at the
        best match; ``section`` (an index into the page's sections) opens it there instead."""
        self._page = page
        self._query = query or ""
        if page is None:
            self.name_label.configure(text="Select a rules page")
            self.badge_row.pack_forget()
            self.match_bar.pack_forget()
            self.jump_combo.configure(values=[JUMP_PLACEHOLDER])
            self.jump_var.set(JUMP_PLACEHOLDER)
            self.text_view.clear()
            self.foot.configure(text="")
            return

        self.name_label.configure(text=f"* {page.name}" if page.is_custom else page.name)
        self.category_badge.configure(text=page.category or "Rules")
        self.tags_label.configure(text=page.display_tags())
        self.badge_row.pack(anchor="w", pady=(0, 2))

        self._section_choices = {}
        choices = [JUMP_PLACEHOLDER]
        for sec in page.sections:
            if sec.level:
                label = " " * (sec.level - 1) + (sec.title or "(untitled)")
                if label in self._section_choices:
                    label += f" ({sec.index})"
                self._section_choices[label] = sec.index
                choices.append(label)
        self.jump_combo.configure(values=choices)
        self.jump_var.set(JUMP_PLACEHOLDER)

        source = page.source + (" (Unofficial)" if not page.is_official and page.source else "")
        self.foot.configure(text=f"Source: {source}" if source else "")

        self.text_view.set_markup(page.description, self._query)
        target = section if section is not None else (hit.section if hit is not None else None)
        total = self.text_view.hit_count
        if self._query.strip():
            self.match_bar.pack(side="right")
            if total:
                pos = self.text_view.hit_near_section(target or 0)
                self._show_hit(pos, scroll=not target)
                if target:
                    self._scroll_later(target)       # the section's heading at the top, the match inside it
                else:
                    for delay in (60, 260):          # again once the text has settled (a long page lays out lazily)
                        self.after(delay, lambda p=pos: self._reshow_hit(p))
            else:
                self.match_label.configure(text="No matches in the text")
                self._scroll_later(target)
        else:
            self.match_bar.pack_forget()
            self._scroll_later(target)

    def _scroll_later(self, section: Optional[int]):
        """Scroll once the text has been laid out (a hidden or just-built widget has no height yet)."""
        if not section:
            self.text_view.scroll_to_top()
            return
        for delay in (30, 220):
            self.after(delay, lambda s=section: self._scroll_now(s))

    def _scroll_now(self, section: int):
        try:
            if self.winfo_exists():
                self.text_view.scroll_to_section(section)
        except tk.TclError:
            pass

    def _reshow_hit(self, position: int):
        try:
            if self.winfo_exists() and self.text_view.hit_count:
                self.text_view.goto_hit(position)
        except tk.TclError:
            pass

    def _show_hit(self, position: int, scroll: bool = True):
        pos, total = self.text_view.goto_hit(position, scroll=scroll)
        if total:
            self.match_label.configure(text=f"{pos + 1} of {total} matches")

    def _step(self, direction: int):
        pos, total = self.text_view.next_hit(direction)
        if total:
            self.match_label.configure(text=f"{pos + 1} of {total} matches")

    def goto_section(self, index: int):
        self.text_view.scroll_to_section(index)

    def _on_jump(self, value: str):
        index = self._section_choices.get(value)
        self.jump_var.set(JUMP_PLACEHOLDER)
        if index is not None:
            self.text_view.scroll_to_section(index)


class RuleEditorBody(EditorBody):
    """Dialog for adding or editing the user's own rules page. (the form; see ui/editor_host.py)"""

    def __init__(self, parent, title: str, page: Optional[RulePage] = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("640x760")
        self.minsize(560, 600)
        self.transient(parent)
        self.grab_set()

        self.theme = get_theme_manager()
        self.manager = get_rules_manager()
        self.result: Optional[RulePage] = None
        self._editing = page

        self._create_widgets()
        if page:
            self._populate(page)

        center_on_parent(self, parent, clamp=True)

    def _create_widgets(self):
        from ui.rich_text_utils import RichTextEditor

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(scroll, text="Name *", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.name_entry = ctk.CTkEntry(scroll, width=400)
        self.name_entry.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(scroll, fg_color="transparent")
        row.pack(fill="x", pady=(0, 10))
        cat_col = ctk.CTkFrame(row, fg_color="transparent")
        cat_col.pack(side="left", padx=(0, 15))
        ctk.CTkLabel(cat_col, text="Category", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        categories = self.manager.get_all_categories()
        self.category_var = ctk.StringVar(value=DEFAULT_CATEGORY_TEXT)
        self.category_combo = ctk.CTkComboBox(cat_col, width=240, values=categories or [DEFAULT_CATEGORY_TEXT],
                                              variable=self.category_var)
        self.category_combo.pack()
        src_col = ctk.CTkFrame(row, fg_color="transparent")
        src_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(src_col, text="Source", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        self.source_entry = ctk.CTkEntry(src_col, placeholder_text="e.g., Homebrew, My Campaign")
        self.source_entry.pack(fill="x")

        self.tag_editor = TagEditor(scroll, get_available_tags=self.manager.get_all_tags)
        self.tag_editor.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Text", font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
        ctk.CTkLabel(
            scroll,
            text="Use the Aa menu for headings (each section gets a bar under its heading) and lists, B and I "
                 "for bold and italic, ― Bar for a horizontal bar (a line of ---) and Table for tables. "
                 "Link other content or rules (e.g. [[rule:Conditions#Stunned]]) with the link suggestions.",
            font=ui_font("small"), text_color=self.theme.get_text_secondary(),
            justify="left", wraplength=540).pack(anchor="w", pady=(0, 4))
        self.desc_text = ctk.CTkTextbox(scroll, height=380)
        self._rich_editor = RichTextEditor(self, self.desc_text, self.theme)
        toolbar = self._rich_editor.create_toolbar(scroll)
        toolbar.pack(fill="x", pady=(5, 5))
        self.desc_text.pack(fill="x", pady=(0, 10))

        btns = ctk.CTkFrame(scroll, fg_color="transparent")
        btns.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btns, text="Cancel", width=100, fg_color="transparent", border_width=1,
                      command=self._finish).pack(side="right", padx=(5, 0))
        ctk.CTkButton(btns, text="Save", width=100,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      command=self._save).pack(side="right")

    def _populate(self, page: RulePage):
        self.name_entry.insert(0, page.name)
        self.category_var.set(page.category or DEFAULT_CATEGORY_TEXT)
        if page.source:
            self.source_entry.insert(0, page.source)
        self.tag_editor.set_tags(page.tags)
        self.desc_text.insert("1.0", page.description)

    def build_result(self, strict: bool = True) -> RulePage:
        """The page the form describes (strict: ValueError if incomplete; otherwise gaps are filled in)."""
        name = self.name_entry.get().strip()
        text = self.desc_text.get("1.0", "end-1c").strip()
        if strict:
            if not name:
                raise ValueError("Name is required.")
            if "#" in name or "|" in name or "[" in name or "]" in name:
                raise ValueError("The name cannot contain # | [ or ].")
            clash = self.manager.get_page(name)
            if clash is not None and not self.EMBEDDED and (
                    self._editing is None or clash.name.lower() != self._editing.name.lower()):
                raise ValueError(f"A rules page called '{clash.name}' already exists. Choose another name.")
            if not text:
                raise ValueError("The page needs some text.")
        return RulePage(
            name=name,
            category=self.category_var.get().strip() or DEFAULT_CATEGORY_TEXT,
            description=text,
            source=self.source_entry.get().strip(),
            tags=self.tag_editor.get_tags(),
            order=0, is_official=False, is_custom=True)

class RuleEditorDialog(RuleEditorBody, DialogWindow):
    """Dialog for adding or editing the user's own rules page."""


class RuleEditorPanel(RuleEditorBody, EmbeddedWindow):
    """The RuleEditorDialog form inside the Homebrew Studio."""


class RulesView(CollectionPageMixin, ctk.CTkFrame):
    """Main view for browsing, searching and managing rules pages."""

    def __init__(self, parent, character_manager=None, on_back=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color=self.theme.get_current_color('bg_primary'))

        self.manager = get_rules_manager()
        self.settings_manager = get_settings_manager()
        self.character_manager = character_manager
        self.on_back = on_back
        self._all_pages: List[RulePage] = []
        self._filter_debounce_id: Optional[str] = None
        self._filter_debounce_delay = 150
        self._history: List[str] = []
        self._shown_name: Optional[str] = None
        self._last_query = ""

        self._selected_sources: List[str] = []
        self._source_filter_mode: SourceFilterMode = SourceFilterMode.INCLUDE
        self._selected_tags: List[str] = []
        self._tag_filter_mode: TagFilterMode = TagFilterMode.HAS_ALL

        self._create_widgets()
        self._load_pages()
        self.theme.add_listener(self._on_theme_changed)

    def destroy(self):
        if self._filter_debounce_id is not None:
            try:
                self.after_cancel(self._filter_debounce_id)
            except Exception:
                pass
            self._filter_debounce_id = None
        try:
            self.theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()

    def _on_theme_changed(self):
        try:
            self.configure(fg_color=self.theme.get_current_color('bg_primary'))
            if hasattr(self, 'paned'):
                self.paned.configure(bg=self.theme.get_current_color("pane_sash"))
        except tk.TclError:
            pass

    def apply_theme(self):
        """Light/dark was switched: the text and the divider are tk widgets, which recolour here."""
        self._on_theme_changed()
        try:
            self.detail_panel.text_view.apply_theme()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ layout

    def _create_panes(self):
        self.list_panel = RulesListPanel(self.paned, on_select=self._on_item_selected)
        self.detail_panel = RuleDetailPanel(self.paned, on_link=self._on_rule_link, on_back=self._go_back)
        self.detail_panel.set_back_enabled(False)

        self.paned.add(self.list_panel, minsize=260, stretch="always")
        self.paned.add(self.detail_panel, minsize=420, stretch="always")

    def _button(self, parent, text, command, width=110, danger=False):
        theme = self.theme
        return ctk.CTkButton(
            parent, text=text, width=width, height=35,
            fg_color=theme.get_current_color('button_danger' if danger else 'button_normal'),
            hover_color=theme.get_current_color('button_danger_hover' if danger else 'button_hover'),
            text_color=theme.get_current_color('text_primary'), command=command)

    def _create_filter_bar(self):
        theme = self.theme
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=10)

        if self.on_back:
            self._button(bar, "← Collections", self.on_back).pack(side="left", padx=(0, 15))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        self.search_entry = ctk.CTkEntry(
            bar, width=280, height=35,
            placeholder_text="Search rules (titles and text)...", textvariable=self.search_var)
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_entry.bind("<Escape>", lambda _e: self.search_var.set(""))
        self.search_entry.bind("<Return>", lambda _e: self._open_top_hit())

        ctk.CTkLabel(bar, text="Category:").pack(side="left", padx=(0, 5))
        self.category_var = ctk.StringVar(value=ALL_CATEGORIES)
        self.category_combo = ctk.CTkComboBox(
            bar, width=180, height=35, values=[ALL_CATEGORIES], variable=self.category_var,
            command=lambda _: self._on_filter_changed(immediate=True), state="readonly")
        self.category_combo.pack(side="left", padx=(0, 10))

        self._button(bar, "+ Add Page", self._on_add, width=110).pack(side="right")
        self.delete_btn = self._button(bar, "Delete", self._on_delete, width=80, danger=True)
        self.delete_btn.pack(side="right", padx=(0, 5))
        self.edit_btn = self._button(bar, "Edit", self._on_edit, width=80)
        self.edit_btn.pack(side="right", padx=(0, 5))
        self.edit_btn.configure(state="disabled")
        self.delete_btn.configure(state="disabled")

        bar2 = ctk.CTkFrame(self, fg_color="transparent")
        bar2.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(bar2, text="Source:").pack(side="left", padx=(0, 5))
        self.source_btn = self._button(bar2, "Select Sources...", self._open_source_filter, width=130)
        self.source_btn.pack(side="left", padx=(0, 8))
        self.source_label = ctk.CTkLabel(bar2, text="None selected", font=ui_font("small"),
                                         text_color=theme.get_text_secondary())
        self.source_label.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(bar2, text="Content:").pack(side="left", padx=(0, 5))
        self.official_var = ctk.StringVar(value="Any Content")
        self.official_combo = ctk.CTkComboBox(
            bar2, width=140, height=35, values=["Any Content", "Official Only", "Homebrew Only"],
            variable=self.official_var, command=lambda _: self._on_filter_changed(immediate=True),
            state="readonly")
        self.official_combo.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(bar2, text="Tags:").pack(side="left", padx=(0, 5))
        self.tags_btn = self._button(bar2, "Select Tags...", self._open_tag_filter, width=120)
        self.tags_btn.pack(side="left", padx=(0, 8))
        self.tags_label = ctk.CTkLabel(bar2, text="None selected", font=ui_font("small"),
                                       text_color=theme.get_text_secondary())
        self.tags_label.pack(side="left")

        self._button(bar2, "Clear Filters", self._clear_filters, width=110, danger=True).pack(side="right")

        bar3 = ctk.CTkFrame(self, fg_color="transparent")
        bar3.pack(fill="x", padx=10, pady=(0, 10))
        self.titles_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(bar3, text="Titles only (don't search the text)", variable=self.titles_var,
                        command=lambda: self._on_filter_changed(immediate=True)).pack(side="left", padx=(0, 20))
        ctk.CTkLabel(bar3, text="Sort:").pack(side="left", padx=(0, 5))
        self.sort_var = ctk.StringVar(value=SORT_BOOK)
        self.sort_combo = ctk.CTkComboBox(
            bar3, width=130, height=35, values=[SORT_BOOK, SORT_NAME], variable=self.sort_var,
            command=lambda _: self._on_filter_changed(immediate=True), state="readonly")
        self.sort_combo.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(bar3, text="(a search is always sorted by how well each page matches)",
                     font=ui_font("small"), text_color=theme.get_text_secondary()).pack(side="left")

    # ------------------------------------------------------------------ filters

    def _load_pages(self):
        self._all_pages = list(self.manager.pages)
        categories = self.manager.get_all_categories()
        self.category_combo.configure(values=[ALL_CATEGORIES] + categories)
        if self.category_var.get() not in [ALL_CATEGORIES] + categories:
            self.category_var.set(ALL_CATEGORIES)
        self._on_filter_changed(immediate=True)

    def _open_source_filter(self):
        dialog = SourceFilterDialog(
            self.winfo_toplevel(), self.manager.get_all_sources(),
            self._selected_sources, self._source_filter_mode,
            empty_message="No sources found in your rules pages.")
        self.wait_window(dialog)
        self._selected_sources = dialog.result
        self._source_filter_mode = dialog.result_mode
        self._update_source_label()
        self._on_filter_changed(immediate=True)

    def _update_source_label(self):
        count = len(self._selected_sources)
        if count == 0:
            self.source_label.configure(text="None selected")
        else:
            mode = "include" if self._source_filter_mode == SourceFilterMode.INCLUDE else "exclude"
            self.source_label.configure(
                text=f"1 source ({mode}): {self._selected_sources[0]}" if count == 1 else f"{count} sources ({mode})")

    def _open_tag_filter(self):
        dialog = TagFilterDialog(
            self.winfo_toplevel(), self.manager.get_all_tags(), self._selected_tags, self._tag_filter_mode,
            noun="tags", empty_message="No tags found in your rules pages.")
        self.wait_window(dialog)
        self._selected_tags = dialog.result
        self._tag_filter_mode = dialog.result_mode
        self._update_tags_label()
        self._on_filter_changed(immediate=True)

    def _update_tags_label(self):
        count = len(self._selected_tags)
        if count == 0:
            self.tags_label.configure(text="None selected")
        else:
            mode = {"has_all": "all", "has_any": "any", "has_none": "none"}[self._tag_filter_mode.value]
            self.tags_label.configure(
                text=f"1 tag ({mode}): {self._selected_tags[0]}" if count == 1 else f"{count} tags ({mode})")

    def _clear_filters(self):
        self.search_var.set("")
        self.category_var.set(ALL_CATEGORIES)
        self.titles_var.set(False)
        self.official_var.set("Any Content")
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._selected_tags = []
        self._tag_filter_mode = TagFilterMode.HAS_ALL
        self._update_source_label()
        self._update_tags_label()
        self._on_filter_changed(immediate=True)

    @staticmethod
    def _matches_tags(values: List[str], selected: List[str], mode: TagFilterMode) -> bool:
        if not selected:
            return True
        have = [v.lower() for v in values]
        wanted = [s.lower() for s in selected]
        if mode == TagFilterMode.HAS_ALL:
            return all(s in have for s in wanted)
        if mode == TagFilterMode.HAS_ANY:
            return any(s in have for s in wanted)
        return not any(s in have for s in wanted)

    def _filtered_pages(self) -> List[RulePage]:
        category = self.category_var.get()
        official = self.official_var.get()
        pages = []
        for page in self._all_pages:
            if category != ALL_CATEGORIES and page.category != category:
                continue
            if not self._matches_tags(page.tags, self._selected_tags, self._tag_filter_mode):
                continue
            if self._selected_sources:
                chosen = page.source in self._selected_sources
                if self._source_filter_mode == SourceFilterMode.INCLUDE and not chosen:
                    continue
                if self._source_filter_mode == SourceFilterMode.EXCLUDE and chosen:
                    continue
            if official == "Official Only" and not page.is_official:
                continue
            if official == "Homebrew Only" and page.is_official:
                continue
            pages.append(page)
        return pages

    def _apply_filters(self):
        self._filter_debounce_id = None
        pages = self._filtered_pages()
        query = self.search_var.get().strip()
        if query:
            items = self.manager.search(query, pages, titles_only=self.titles_var.get())
            self.list_panel.set_items(items, reset_scroll=True, keep_current=False)
            self._last_query = query
            if items:
                self.list_panel.select_by_name(items[0].name)
            else:
                self.list_panel.clear_selection()
                self.detail_panel.show_page(None)
                self._update_buttons(None)
            return
        if self.sort_var.get() == SORT_NAME:
            pages = sorted(pages, key=lambda p: p.name.lower())
        had_query, self._last_query = bool(self._last_query), ""
        self.list_panel.set_items(pages, reset_scroll=not had_query)
        if had_query and self._shown_name:
            # the search is over: keep the page that was open, without the highlights
            self.list_panel.select_by_name(self._shown_name)

    def _open_top_hit(self):
        item = self.list_panel.get_selected()
        if item is not None:
            self.detail_panel.text_view.focus_set()

    # ------------------------------------------------------------------ selection

    def _on_item_selected(self, item):
        if item is None:
            self.detail_panel.show_page(None)
            self._update_buttons(None)
            return
        page = item.page if isinstance(item, RuleHit) else item
        hit = item if isinstance(item, RuleHit) else None
        self._shown_name = page.name
        self.detail_panel.show_page(page, hit, query=self.search_var.get().strip() if hit else "")
        self._update_buttons(page)

    def _update_buttons(self, page: Optional[RulePage]):
        editable = page is not None and page.is_custom
        self.edit_btn.configure(state="normal" if editable else "disabled")
        self.delete_btn.configure(state="normal" if editable else "disabled")

    def _on_rule_link(self, category: str, name: str):
        """A link clicked inside a page: rules links move within this view, others open their popup."""
        if category != "rule":
            from ui.object_link_widgets import open_link_popup
            open_link_popup(self, category, name)
            return
        if self._shown_name:
            self._history.append(self._shown_name)
            self._history = self._history[-30:]
        if not self.select_rule(name, from_history=False):
            from ui.object_link_widgets import open_link_popup
            open_link_popup(self, category, name)
        self.detail_panel.set_back_enabled(bool(self._history))

    def _go_back(self):
        while self._history:
            target = self._history.pop()
            if self.select_rule(target, from_history=True):
                break
        self.detail_panel.set_back_enabled(bool(self._history))

    def select_rule(self, name: str, from_history: bool = False) -> bool:
        """Open a page (``"Combat"``) or a section of one (``"Conditions#Stunned"``, or just
        ``"Stunned"``). Clears a search or filter that would hide it."""
        ref = self.manager.resolve(name)
        if ref is None:
            return False
        page = ref.page
        if self._shown_name == page.name and not self.search_var.get().strip():
            if ref.section is not None:
                self.detail_panel.goto_section(ref.section.index)
            else:
                self.detail_panel.text_view.scroll_to_top()
            return True
        if not any(p.name == page.name for p in self._all_pages):
            self._load_pages()
        if self.search_var.get().strip() or page.name not in {p.name for p in self._filtered_pages()}:
            self._clear_filters()
        if self._filter_debounce_id is not None:
            self._apply_filters_now()              # the list is about to change: let it, so the page is in it
        if not self.list_panel.select_by_name(page.name):
            return False
        if ref.section is not None:
            self.detail_panel.show_page(page, section=ref.section.index)
        return True

    select_page = select_rule

    def _apply_filters_now(self):
        if self._filter_debounce_id is not None:
            self.after_cancel(self._filter_debounce_id)
        self._apply_filters()

    # ------------------------------------------------------------------ editing

    def _on_add(self):
        from ui.studio_launch import open_in_studio
        if open_in_studio(self, "rules"):
            return
        dialog = RuleEditorDialog(self.winfo_toplevel(), "Add Rules Page")
        self.wait_window(dialog)
        if dialog.result and self.manager.add_rule(dialog.result):
            self._load_pages()
            self.select_rule(dialog.result.name)

    def _on_edit(self):
        page = self.list_panel.get_selected_page()
        if not page or not page.is_custom:
            return
        dialog = RuleEditorDialog(self.winfo_toplevel(), "Edit Rules Page", page)
        self.wait_window(dialog)
        if dialog.result and self.manager.update_page(page.name, dialog.result):
            self._load_pages()
            self._shown_name = None
            self.select_rule(dialog.result.name)

    def _on_delete(self):
        page = self.list_panel.get_selected_page()
        if not page or not page.is_custom:
            return
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{page.name}'?"):
            if self.manager.delete_page(page.name):
                self._shown_name = None
                self._load_pages()
                self.detail_panel.show_page(None)
                self._update_buttons(None)

    def refresh(self):
        self._load_pages()
