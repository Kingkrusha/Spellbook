"""
Characters page: every character in one list that can be searched, filtered and
sorted, with character import / export. Clicking a character opens its sheet.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from typography import ui_font
from theme import get_theme_manager
from ui.lazy_destroy import destroy_later
from ui.platform_compat import bind_right_click
from ui.scrollable_combobox import ScrollableComboBox

ALL = "All"
SORT_OPTIONS = ["Name", "Level", "Class", "Species", "Background"]
THUMB_SIZE = 56

# Portrait thumbnails, by stored file name (names are content-hashed, so they never go stale)
_thumbnails: Dict[str, Optional[object]] = {}


def _thumbnail(filename: str):
    """A small CTkImage of a stored portrait, or None."""
    if not filename:
        return None
    if filename not in _thumbnails:
        image = None
        try:
            import portraits
            pil = portraits.load_image(filename)
            if pil is not None:
                pil.thumbnail((THUMB_SIZE * 2, THUMB_SIZE * 2))
                scale = min(THUMB_SIZE / pil.width, THUMB_SIZE / pil.height)
                size = (max(1, int(pil.width * scale)), max(1, int(pil.height * scale)))
                image = ctk.CTkImage(light_image=pil, dark_image=pil, size=size)
        except Exception:
            image = None
        _thumbnails[filename] = image
    return _thumbnails[filename]


class CharactersView(ctk.CTkFrame):
    """List of all characters with search, filters, sorting, import and export."""

    # Sort / filter choices survive leaving the page (e.g. to open a sheet) and coming back
    _remembered = {"search": "", "class": ALL, "species": ALL, "background": ALL,
                   "sort": "Name", "descending": False}

    def __init__(self, parent, character_manager, spell_manager=None,
                 on_open: Optional[Callable[[str, bool], None]] = None,
                 on_home: Optional[Callable[[], None]] = None):
        """``on_open(name, new_tab)`` opens a character's sheet."""
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.character_manager = character_manager
        self.spell_manager = spell_manager
        self.on_open = on_open
        self.on_home = on_home

        mem = CharactersView._remembered
        self._initial_search = mem["search"]
        self.class_var = ctk.StringVar(value=mem["class"])
        self.species_var = ctk.StringVar(value=mem["species"])
        self.background_var = ctk.StringVar(value=mem["background"])
        self.sort_var = ctk.StringVar(value=mem["sort"])
        self._descending = mem["descending"]
        self._search_after = None
        # Each character's card, built once: filtering and sorting only re-order them, and a
        # card is rebuilt only when that character's data changed (building one costs ~20 ms)
        self._cards: dict = {}   # name -> (signature, card)
        self._message = None     # the "no characters" / "no matches" notice, if shown

        self._create_widgets()
        self._update_filter_choices()
        self._rebuild_list()

    # ------------------------------------------------------------------ layout

    def _create_widgets(self):
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        # Header: back button, title, actions
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))

        if self.on_home:
            ctk.CTkButton(
                header, text="← Home", width=90, height=32,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                command=self.on_home
            ).pack(side="left", padx=(0, 15))

        ctk.CTkLabel(
            header, text="Characters", font=ui_font("title", 28, bold=True)
        ).pack(side="left")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        ctk.CTkButton(
            actions, text="+ New Character", width=130, height=34,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self._on_new_character
        ).pack(side="left", padx=5)
        for text, command in (("📥 Import", self._on_import), ("📤 Export", self._on_export)):
            ctk.CTkButton(
                actions, text=text, width=100, height=34,
                fg_color=self.theme.get_current_color('button_normal'),
                hover_color=self.theme.get_current_color('button_hover'),
                command=command
            ).pack(side="left", padx=5)

        # Search + filters + sorting
        bar = ctk.CTkFrame(outer, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=10)
        bar.pack(fill="x", pady=(0, 12))

        row1 = ctk.CTkFrame(bar, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(10, 4))

        # (no textvariable: CTkEntry hides its placeholder text when it has one)
        self.search_entry = ctk.CTkEntry(
            row1, height=32,
            placeholder_text="Search name, class, species, background…"
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        if self._initial_search:
            self.search_entry.insert(0, self._initial_search)
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search_typed())

        ctk.CTkLabel(row1, text="Sort by:", font=ui_font("body")).pack(side="left", padx=(0, 6))
        ScrollableComboBox(
            row1, width=120, height=32, variable=self.sort_var, values=SORT_OPTIONS,
            command=lambda _v: self._on_filters_changed(), state="readonly"
        ).pack(side="left")
        self.direction_btn = ctk.CTkButton(
            row1, text=self._direction_text(), width=36, height=32,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._toggle_direction
        )
        self.direction_btn.pack(side="left", padx=(6, 0))

        row2 = ctk.CTkFrame(bar, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 10))

        self.class_combo = self._filter_combo(row2, "Class", self.class_var)
        self.species_combo = self._filter_combo(row2, "Species", self.species_var)
        self.background_combo = self._filter_combo(row2, "Background", self.background_var)

        ctk.CTkButton(
            row2, text="Clear", width=70, height=30,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._clear_filters
        ).pack(side="left", padx=(4, 0))

        self.count_label = ctk.CTkLabel(
            row2, text="", font=ui_font("body"), text_color=self.theme.get_text_secondary()
        )
        self.count_label.pack(side="right")

        # The character cards
        self.list_frame = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True)

        self._create_context_menu()

    def _filter_combo(self, parent, label: str, variable: ctk.StringVar) -> ScrollableComboBox:
        ctk.CTkLabel(parent, text=f"{label}:", font=ui_font("body")).pack(side="left", padx=(0, 6))
        combo = ScrollableComboBox(
            parent, width=150, height=30, variable=variable, values=[ALL],
            command=lambda _v: self._on_filters_changed(), state="readonly"
        )
        combo.pack(side="left", padx=(0, 14))
        return combo

    def _create_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        bg, fg, active_bg, active_fg = self.theme.get_menu_colors()
        self.context_menu.configure(bg=bg, fg=fg, activebackground=active_bg,
                                    activeforeground=active_fg, relief="flat", borderwidth=1)

    # -------------------------------------------------------------------- data

    def _entries(self) -> List[dict]:
        """One record per character, with everything the list shows / sorts / filters on."""
        from ui.character_sheet_view import get_sheet_manager
        sheets = get_sheet_manager()
        entries = []
        for char in self.character_manager.characters:
            sheet = sheets.get_sheet(char.name)
            class_names = [cl.get_class_name() for cl in char.classes]
            entries.append({
                "name": char.name,
                "level": char.total_level,
                "class_names": class_names,
                "class_text": " / ".join(f"{cl.get_class_name()} {cl.level}" for cl in char.classes),
                "species": (char.lineage or (sheet.race if sheet else "") or "").strip(),
                "background": ((sheet.background if sheet else "") or "").strip(),
                "portrait": sheet.portrait if sheet else "",
            })
        return entries

    @staticmethod
    def _sort_key(sort: str):
        def text(value):
            return (value or "").lower()
        if sort == "Level":
            return lambda e: (e["level"], text(e["name"]))
        if sort == "Class":
            return lambda e: (text(e["class_names"][0] if e["class_names"] else ""), text(e["name"]))
        if sort == "Species":
            return lambda e: (text(e["species"]), text(e["name"]))
        if sort == "Background":
            return lambda e: (text(e["background"]), text(e["name"]))
        return lambda e: text(e["name"])

    def _matches(self, entry: dict) -> bool:
        if self.class_var.get() != ALL and self.class_var.get() not in entry["class_names"]:
            return False
        if self.species_var.get() != ALL and entry["species"] != self.species_var.get():
            return False
        if self.background_var.get() != ALL and entry["background"] != self.background_var.get():
            return False
        query = self.search_entry.get().strip().lower()
        if query:
            haystack = " ".join([entry["name"], entry["class_text"], entry["species"],
                                 entry["background"]]).lower()
            if not all(word in haystack for word in query.split()):
                return False
        return True

    def _update_filter_choices(self):
        """Fill the filter dropdowns from what the characters actually use."""
        entries = self._entries()
        pools = (
            (self.class_combo, self.class_var, {c for e in entries for c in e["class_names"]}),
            (self.species_combo, self.species_var, {e["species"] for e in entries if e["species"]}),
            (self.background_combo, self.background_var, {e["background"] for e in entries if e["background"]}),
        )
        for combo, var, values in pools:
            choices = [ALL] + sorted(values, key=str.lower)
            combo.configure(values=choices)
            if var.get() not in choices:
                var.set(ALL)

    # ---------------------------------------------------------------- rendering

    @staticmethod
    def _signature(entry: dict) -> tuple:
        """Everything a card shows; if it is unchanged the card can be reused."""
        return (entry["name"], entry["level"], entry["class_text"], entry["species"],
                entry["background"], entry["portrait"])

    def _rebuild_list(self):
        entries = self._entries()
        shown = [e for e in entries if self._matches(e)]
        shown.sort(key=self._sort_key(self.sort_var.get()), reverse=self._descending)

        self.count_label.configure(
            text=f"{len(shown)} of {len(entries)} character{'s' if len(entries) != 1 else ''}")

        # Cards of characters that are gone or changed are thrown away (a little at a time)
        current = {e["name"]: self._signature(e) for e in entries}
        for name, (signature, card) in list(self._cards.items()):
            if current.get(name) != signature:
                destroy_later(card)
                del self._cards[name]

        if self._message is not None:
            self._message.destroy()
            self._message = None
        for _signature, card in self._cards.values():
            card.pack_forget()

        if not entries:
            self._show_message("No characters yet.",
                               "Click “+ New Character” to create one, or import characters from a file.")
        elif not shown:
            self._show_message("No characters match your search or filters.", None, clear_button=True)
        else:
            for entry in shown:
                name = entry["name"]
                if name not in self._cards:
                    self._cards[name] = (self._signature(entry), self._build_card(entry))
                self._cards[name][1].pack(fill="x", pady=4, padx=2)

        self._remember()

    def _show_message(self, title: str, hint: Optional[str], clear_button: bool = False):
        box = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        box.pack(pady=60)
        self._message = box
        ctk.CTkLabel(box, text=title, font=ui_font("heading", 16),
                     text_color=self.theme.get_text_secondary()).pack()
        if hint:
            ctk.CTkLabel(box, text=hint, font=ui_font("body"),
                         text_color=self.theme.get_text_secondary()).pack(pady=(6, 0))
        if clear_button:
            ctk.CTkButton(box, text="Clear filters", width=110, command=self._clear_filters).pack(pady=(12, 0))

    def _build_card(self, entry: dict):
        """Build (not pack) one character's card."""
        card = ctk.CTkFrame(self.list_frame, fg_color=self.theme.get_current_color('bg_secondary'),
                            corner_radius=10, cursor="hand2")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)

        thumb = _thumbnail(entry["portrait"])
        if thumb is not None:
            portrait = ctk.CTkLabel(inner, text="", image=thumb, width=THUMB_SIZE, height=THUMB_SIZE)
        else:
            portrait = ctk.CTkLabel(
                inner, text=(entry["name"][:1] or "?").upper(), width=THUMB_SIZE, height=THUMB_SIZE,
                fg_color=self.theme.get_current_color('bg_tertiary'), corner_radius=8,
                font=ui_font("heading", 22, bold=True), text_color=self.theme.get_text_secondary())
        portrait.pack(side="left", padx=(0, 14))

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text_col, text=entry["name"], font=ui_font("heading", 17, bold=True),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(text_col, text=entry["class_text"] or "No class",
                     font=ui_font("body"), anchor="w",
                     text_color=self.theme.get_text_secondary()).pack(fill="x")
        # Always present (blank if empty) so every card is the same height
        details = " · ".join(x for x in (entry["species"], entry["background"]) if x)
        ctk.CTkLabel(text_col, text=details or " ", font=ui_font("small"), anchor="w",
                     text_color=self.theme.get_text_secondary()).pack(fill="x")

        ctk.CTkLabel(inner, text=f"Level {entry['level']}", font=ui_font("subheading", bold=True)
                     ).pack(side="right", padx=(10, 4))

        name = entry["name"]
        self._bind_card(card, name)
        return card

    def _bind_card(self, card: ctk.CTkFrame, name: str):
        def inside(event):
            widget = card.winfo_containing(event.x_root, event.y_root)
            while widget is not None:
                if widget is card:
                    return True
                widget = getattr(widget, "master", None)
            return False

        # (colours are looked up when the mouse moves, not captured now: cards live across theme changes)
        card.bind("<Enter>", lambda e: card.configure(fg_color=self.theme.get_current_color('bg_tertiary')))
        card.bind("<Leave>", lambda e: None if inside(e)
                  else card.configure(fg_color=self.theme.get_current_color('bg_secondary')))

        def bind_all(widget):
            widget.bind("<Button-1>", lambda e, n=name: self._open(n, False))
            widget.bind("<Control-Button-1>", lambda e, n=name: self._open(n, True))
            bind_right_click(widget, lambda e, n=name: self._show_menu(e, n))
            for child in widget.winfo_children():
                bind_all(child)
        bind_all(card)

    # ------------------------------------------------------------------ actions

    def _open(self, name: str, new_tab: bool):
        if self.on_open:
            self.on_open(name, new_tab)

    def _show_menu(self, event, name: str):
        menu = self.context_menu
        menu.delete(0, "end")
        menu.add_command(label="Open", command=lambda: self._open(name, False))
        menu.add_command(label="Open in New Tab", command=lambda: self._open(name, True))
        menu.add_separator()
        menu.add_command(label="Export…", command=lambda: self._on_export([name]))
        menu.add_command(label="Delete…", command=lambda: self._delete(name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _delete(self, name: str):
        if not messagebox.askyesno(
            "Delete Character",
            f"Are you sure you want to delete '{name}'?\n\n"
            "This will permanently remove the character and their sheet.\n"
            "This action cannot be undone.",
            icon='warning', parent=self
        ):
            return
        from ui.character_sheet_view import get_sheet_manager
        self.character_manager.delete_character(name)
        get_sheet_manager().delete_sheet(name)
        self.refresh()

    def _on_new_character(self):
        from ui.character_sheet_view import NewCharacterDialog
        dialog = NewCharacterDialog(self.winfo_toplevel(), self.character_manager)
        self.wait_window(dialog)
        if dialog.result:
            self._open(dialog.result.name, False)

    def _on_import(self):
        from ui.character_transfer import import_characters
        if import_characters(self.winfo_toplevel(), self.character_manager, self.spell_manager):
            self.refresh()

    def _on_export(self, preselected: Optional[List[str]] = None):
        from ui.character_transfer import CharacterSheetExportDialog
        dialog = CharacterSheetExportDialog(self.winfo_toplevel(), self.character_manager,
                                            preselected=preselected)
        dialog.grab_set()

    # ------------------------------------------------------- filter / sort state

    def _direction_text(self) -> str:
        return "↓" if self._descending else "↑"

    def _toggle_direction(self):
        self._descending = not self._descending
        self.direction_btn.configure(text=self._direction_text())
        self._rebuild_list()

    def _on_search_typed(self):
        # Wait for a pause in typing before rebuilding the list
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = self.after(150, self._apply_search)

    def _apply_search(self):
        self._search_after = None
        self._rebuild_list()

    def _on_filters_changed(self):
        self._rebuild_list()

    def _clear_filters(self):
        self.search_entry.delete(0, "end")
        for var in (self.class_var, self.species_var, self.background_var):
            var.set(ALL)
        self._rebuild_list()

    def _remember(self):
        CharactersView._remembered = {
            "search": self.search_entry.get(), "class": self.class_var.get(),
            "species": self.species_var.get(), "background": self.background_var.get(),
            "sort": self.sort_var.get(), "descending": self._descending,
        }

    def refresh(self):
        """Pick up characters added / changed / deleted elsewhere."""
        self._update_filter_choices()
        self._rebuild_list()

    def destroy(self):
        if self._search_after is not None:
            try:
                self.after_cancel(self._search_after)
            except Exception:
                pass
            self._search_after = None
        super().destroy()
