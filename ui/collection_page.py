"""
What the collection browsing pages (equipment, magic items, feats, lineages, backgrounds) have in common.

Each page is the same shape: a filter bar over a list of entries (left) and the selected entry's
details (right), a right-click menu, and a debounced "something in the filter bar changed" handler.
They had each grown their own copy of that plumbing, so it lives here once:

* behaviour - theme refresh, the debounce, the source filter and its summary label
* widget helpers - the back button, search box, filter drop-downs, source picker, action buttons and
  paned list/detail layout, each taking only what differs from page to page

A page mixes :class:`CollectionPageMixin` in before ``ctk.CTkFrame`` and names its manager::

    class FeatsView(CollectionPageMixin, ctk.CTkFrame):
        MANAGER_ATTR = "feat_manager"      # the attribute holding the manager (needs get_all_sources)
        PLURAL = "feats"                   # "No sources found in your feats."
"""

import tkinter as tk
from tkinter import messagebox
from typing import Callable, List, Optional, Sequence

import customtkinter as ctk

from typography import ui_font
from ui.filter_widgets import SourceFilterDialog, SourceFilterMode
from ui.tooltip import HoverTooltip


class SourceFilterMixin:
    """The "Select Sources..." filter: its dialog, the summary under it and the include / exclude test.

    The page keeps ``_selected_sources`` / ``_source_filter_mode`` and a ``source_label``, and names the manager that
    knows every source (``MANAGER_ATTR``); ``PLURAL`` words the dialog's "no sources" message (blank: no message)."""

    MANAGER_ATTR = ""
    PLURAL = ""

    def _open_source_filter(self):
        """Open the source filter dialog."""
        available_sources = getattr(self, self.MANAGER_ATTR).get_all_sources()
        options = {"empty_message": f"No sources found in your {self.PLURAL}."} if self.PLURAL else {}
        dialog = SourceFilterDialog(
            self.winfo_toplevel(), available_sources,
            self._selected_sources, self._source_filter_mode, **options
        )
        self.wait_window(dialog)
        self._selected_sources = dialog.result
        self._source_filter_mode = dialog.result_mode
        self._update_source_label()
        self._on_filter_changed(immediate=True)

    def _update_source_label(self):
        """Update the source label with selected source count and mode."""
        count = len(self._selected_sources)
        if count == 0:
            self.source_label.configure(text="None selected")
        else:
            mode_str = "include" if self._source_filter_mode == SourceFilterMode.INCLUDE else "exclude"
            if count == 1:
                self.source_label.configure(text=f"1 source ({mode_str}): {self._selected_sources[0]}")
            else:
                self.source_label.configure(text=f"{count} sources ({mode_str})")

    def _passes_source_filter(self, source: str) -> bool:
        """Whether an entry from ``source`` survives the source filter."""
        if not self._selected_sources:
            return True
        source_selected = source in self._selected_sources
        if self._source_filter_mode == SourceFilterMode.INCLUDE:
            return source_selected
        return not source_selected


class CharacterPickMixin:
    """Choosing the character an entry is handed to; the page keeps its manager in ``self.character_manager``."""

    def _pick_character(self, prompt: str):
        """Ask which character (a dialog titled with ``prompt``). Returns it, or None: after a warning when there
        is no manager or no character, quietly when the dialog is cancelled."""
        if not self.character_manager:
            messagebox.showwarning("No Characters", "No character manager available.")
            return None
        characters = self.character_manager.characters
        if not characters:
            messagebox.showwarning("No Characters", "No characters available. Create a character first.")
            return None
        from ui.item_picker import PickCharacterDialog
        dialog = PickCharacterDialog(self.winfo_toplevel(), prompt, characters)
        self.wait_window(dialog)
        if not dialog.result:
            return None
        return self.character_manager.get_character(dialog.result)

    def _active_character(self):
        """The active character, or None after saying there isn't one."""
        character = self.character_manager.get_active_character()
        if not character:
            messagebox.showwarning("No Character", "No active character selected.", parent=self)
        return character


class SearchTitlesMixin:
    """The search box's "Titles only" option, for any page that filters a list by a search box."""

    def _add_titles_only(self, bar, padx=(0, 15)):
        """A "Titles only" tick-box: the search then looks at names alone, not at descriptions and the like."""
        self.titles_var = ctk.BooleanVar(value=False)
        box = ctk.CTkCheckBox(bar, text="Titles only", variable=self.titles_var, width=24,
                              command=lambda: self._on_filter_changed(immediate=True))
        box.pack(side="left", padx=padx)
        HoverTooltip(box, "Search the names only, not the descriptions or tags.")
        return box

    def _titles_only(self) -> bool:
        var = getattr(self, "titles_var", None)
        return bool(var and var.get())

    def _passes_search(self, search: str, name: str, texts=()) -> bool:
        """Whether an entry matches the (lower-cased) search box.

        It matches by name or, unless "Titles only" is ticked, by any of ``texts`` (the other searchable
        text of the entry: a list of strings, or a function that makes one, for text that is costly to build)."""
        if not search or search in name.lower():
            return True
        if self._titles_only():
            return False
        return any(search in text.lower() for text in (texts() if callable(texts) else texts))


class CollectionPageMixin(CharacterPickMixin, SearchTitlesMixin, SourceFilterMixin):
    """The plumbing of a collection page (see the module docstring)."""

    PANE_SASH = 320          # initial width of the list pane

    # ------------------------------------------------------------------ behaviour

    def set_character_manager(self, character_manager):
        """Set the character manager used by the "Add to Character" style context menu actions."""
        self.character_manager = character_manager

    def _on_theme_changed(self):
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._update_context_menu_colors()
        if hasattr(self, 'paned'):
            self._update_paned_colors()
        if hasattr(self, 'compare_container'):
            self.compare_container.configure(fg_color=self.theme.get_current_color('bg_secondary'))

    def _update_context_menu_colors(self):
        if not hasattr(self, 'context_menu'):
            return
        bg_color = self.theme.get_current_color('bg_secondary')
        fg_color = self.theme.get_current_color('text_primary')
        self.context_menu.configure(
            bg=bg_color,
            fg=fg_color,
            activebackground=self.theme.get_current_color('accent_primary'),
            activeforeground=fg_color
        )

    def _update_paned_colors(self):
        """Update PanedWindow sash colors based on current theme."""
        self.paned.configure(bg=self.theme.get_current_color("pane_sash"))

    def _on_filter_changed(self, immediate: bool = False):
        """Called when any filter value changes, debounced so typing doesn't refilter every key."""
        if self._filter_debounce_id is not None:
            self.after_cancel(self._filter_debounce_id)
            self._filter_debounce_id = None

        delay = 10 if immediate else self._filter_debounce_delay
        self._filter_debounce_id = self.after(delay, self._apply_filters)

    @staticmethod
    def _passes_official_filter(is_official: bool, choice: str) -> bool:
        """Whether an entry survives the "Any Content / Official Only / Homebrew Only" choice."""
        if choice == "Official Only" and not is_official:
            return False
        if choice == "Homebrew Only" and is_official:
            return False
        return True

    # ------------------------------------------------------------------ widget helpers

    def _add_back_button(self, bar):
        """The "← Collections" button, when the page was opened from the Collections hub."""
        if self.on_back:
            ctk.CTkButton(
                bar, text="← Collections", width=110,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                text_color=self.theme.get_current_color('text_primary'),
                command=self.on_back
            ).pack(side="left", padx=(0, 15))

    def _add_search_entry(self, bar, placeholder: str, width: int, padx=(0, 15)):
        """The search box and, beside it, the "Titles only" tick-box."""
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        ctk.CTkEntry(
            bar, width=width, height=35,
            placeholder_text=placeholder, textvariable=self.search_var
        ).pack(side="left", padx=(0, 8))
        self._add_titles_only(bar, padx)

    def _add_filter_combo(self, bar, name: str, label: str, default: str, values: Sequence[str],
                          width: int, padx=(0, 15)):
        """A labelled read-only drop-down; creates ``self.<name>_var`` and ``self.<name>_combo``."""
        ctk.CTkLabel(bar, text=label).pack(side="left", padx=(0, 5))
        var = ctk.StringVar(value=default)
        combo = ctk.CTkComboBox(
            bar, width=width, height=35, values=list(values),
            variable=var, command=lambda _: self._on_filter_changed(immediate=True),
            state="readonly"
        )
        combo.pack(side="left", padx=padx)
        setattr(self, f"{name}_var", var)
        setattr(self, f"{name}_combo", combo)

    def _add_source_filter(self, bar, end_padx=(0, 20)):
        """"Source:" label, the Select Sources button and its summary label."""
        ctk.CTkLabel(bar, text="Source:").pack(side="left", padx=(0, 5))
        self.source_btn = ctk.CTkButton(
            bar, text="Select Sources...", width=130, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._open_source_filter
        )
        self.source_btn.pack(side="left", padx=(0, 8))
        self.source_label = ctk.CTkLabel(
            bar, text="None selected",
            font=ui_font("small"), text_color=self.theme.get_text_secondary()
        )
        self.source_label.pack(side="left", padx=end_padx)

    def _add_content_filter(self, bar, padx=(0, 20)):
        self._add_filter_combo(bar, "official", "Content:", "Any Content",
                               ["Any Content", "Official Only", "Homebrew Only"], 140, padx)

    def _add_clear_button(self, bar):
        ctk.CTkButton(
            bar, text="Clear Filters", width=110, height=35,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            text_color=self.theme.get_current_color('text_primary'),
            command=self._clear_filters
        ).pack(side="right")

    def _add_action_buttons(self, bar, add_text: str, add_width: int, on_add: Callable,
                            on_edit: Callable, on_delete: Callable, start_disabled: bool = False):
        """The right-hand "+ Add", Delete and Edit buttons (``self.delete_btn`` / ``self.edit_btn``)."""
        ctk.CTkButton(
            bar, text=add_text, width=add_width, height=35,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=on_add
        ).pack(side="right")

        self.delete_btn = ctk.CTkButton(
            bar, text="Delete", width=80, height=35,
            fg_color=self.theme.get_current_color('button_danger'),
            hover_color=self.theme.get_current_color('button_danger_hover'),
            command=on_delete
        )
        self.delete_btn.pack(side="right", padx=(0, 5))

        self.edit_btn = ctk.CTkButton(
            bar, text="Edit", width=80, height=35,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=on_edit
        )
        self.edit_btn.pack(side="right", padx=(0, 5))

        if start_disabled:
            self.edit_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")

    def _filter_row(self, pady=(0, 10)):
        """A further row of filters under the first."""
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=pady)
        return row

    def _build_context_menu(self, entries: List[tuple]):
        """The right-click menu: ``entries`` is ``[(label, command), ...]``."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self._update_context_menu_colors()
        for label, command in entries:
            self.context_menu.add_command(label=label, command=command)

    def _create_paned_layout(self):
        """The filter bar, then a resizable list | detail split (``self.paned``).

        The page supplies the two panes in ``_create_panes`` and adds them to ``self.paned``."""
        self._create_filter_bar()

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.paned = tk.PanedWindow(
            self.content, orient=tk.HORIZONTAL, sashwidth=8, sashrelief=tk.RAISED,
            handlesize=0, opaqueresize=False, sashcursor="sb_h_double_arrow"
        )
        self.paned.pack(fill="both", expand=True)
        self._update_paned_colors()

        self._create_panes()

        # Initial sash position (roughly 1:2 ratio)
        self.after(100, self._place_sash)

    def _create_panes_with_container(self, list_cls, detail_cls, on_select, on_right_click):
        """Panes for the versioned pages: the list sits in ``self.left_container`` so a compare panel can
        take its place, and picking a version in the detail pane's Source drop-down updates the list."""
        self.left_container = ctk.CTkFrame(self.paned, fg_color="transparent")

        self.list_panel = list_cls(
            self.left_container, on_select=on_select, on_right_click=on_right_click
        )
        self.list_panel.pack(fill="both", expand=True)

        self.detail_panel = detail_cls(self.paned)
        self.detail_panel.on_version_change = self.list_panel.replace_selected

        self.paned.add(self.left_container, minsize=280, stretch="always")
        self.paned.add(self.detail_panel, minsize=400, stretch="always")

    def _place_sash(self):
        try:
            self.paned.sash_place(0, self.PANE_SASH, 0)
        except tk.TclError:
            pass

    def _create_widgets(self):
        self._create_paned_layout()

    def _create_panes(self):
        raise NotImplementedError

    def _build_compare_panel(self, title: str, detail_cls: Callable, close_command: Callable,
                             padded: bool = True):
        """The (initially hidden) panel that replaces the list while comparing two entries."""
        self.compare_container = ctk.CTkFrame(
            self.left_container, corner_radius=10,
            fg_color=self.theme.get_current_color('bg_secondary'))

        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            header, text=title,
            font=ui_font("subheading", bold=True)
        ).pack(side="left")

        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=close_command
        ).pack(side="right")

        self.compare_detail = detail_cls(self.compare_container)
        if padded:
            self.compare_detail.pack(fill="both", expand=True, padx=5, pady=5)
        else:
            self.compare_detail.pack(fill="both", expand=True)
