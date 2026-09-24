"""
Search-and-pick dialog for adding a catalog item (equipment or magic item) to
a character sheet's inventory.

Used by the inventory tab's "+ Add Equipment" / "+ Add Item" buttons: the user
searches/browses the Equipment or Magic Items collection and picks one, which
the caller then turns into a linked inventory row (see character_sheet_view.py's
_add_equipment_item / _add_magic_item).
"""

from typing import Callable, List, Optional

import customtkinter as ctk

from theme import get_theme_manager

_DEBOUNCE_MS = 150
# Building a real widget (a button plus its overlay frame/labels) per row gets
# noticeably slow past a few dozen rows - the magic items collection alone is
# 400+ entries, which took several seconds to render and made the dialog look
# like it had frozen before the search box ever got a chance to paint. Cap how
# many rows get built at once; searching narrows the underlying list instead
# of paging through this cap, so it stays useful even on a big collection.
_MAX_RENDERED_ROWS = 60


class ItemPickerDialog(ctk.CTkToplevel):
    """Modal search-and-pick list over a collection manager's items.

    ``subtitle_fn(item) -> str`` builds the secondary line shown under each
    item's name (type/rarity/cost/weight, whatever's relevant for that
    collection). ``self.result`` is the picked domain object, or ``None`` if
    the dialog was cancelled.
    """

    def __init__(self, parent, title: str, items: List, subtitle_fn: Callable[[object], str],
                 search_fn: Callable[[str], List]):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.result = None
        self._all_items = items
        self._subtitle_fn = subtitle_fn
        self._search_fn = search_fn
        self._debounce_id: Optional[str] = None

        self.title(title)
        self.geometry("480x560")
        self.minsize(400, 420)
        self.resizable(True, True)

        self.transient(parent)
        self.grab_set()

        self._create_widgets(title)

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _create_widgets(self, title: str):
        theme = self.theme
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            container, text=title, font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 10))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_a: self._schedule_search())
        search_entry = ctk.CTkEntry(
            container, textvariable=self.search_var,
            placeholder_text="Search by name...", height=32
        )
        search_entry.pack(fill="x", pady=(0, 10))
        search_entry.focus_set()

        self.list_frame = ctk.CTkScrollableFrame(
            container, fg_color=theme.get_current_color('bg_secondary')
        )
        self.list_frame.pack(fill="both", expand=True, pady=(0, 10))

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        ctk.CTkButton(
            btn_frame, text="Cancel", width=90,
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._on_cancel
        ).pack(side="right")

        self._populate(self._all_items)

    def _schedule_search(self):
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(_DEBOUNCE_MS, self._run_search)

    def _run_search(self):
        self._debounce_id = None
        query = self.search_var.get().strip()
        items = self._search_fn(query) if query else self._all_items
        self._populate(items)

    def _populate(self, items: List):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        if not items:
            ctk.CTkLabel(
                self.list_frame, text="No items found.",
                text_color=self.theme.get_text_secondary()
            ).pack(pady=30)
            return

        ordered = sorted(items, key=lambda i: i.name.lower())
        shown = ordered[:_MAX_RENDERED_ROWS]
        for item in shown:
            self._create_row(item)

        if len(ordered) > len(shown):
            ctk.CTkLabel(
                self.list_frame,
                text=f"Showing {len(shown)} of {len(ordered)} - type to narrow the search.",
                font=ctk.CTkFont(size=11),
                text_color=self.theme.get_text_secondary(),
            ).pack(pady=(6, 4))

    def _create_row(self, item):
        theme = self.theme
        row = ctk.CTkButton(
            self.list_frame, text="", anchor="w", height=44,
            fg_color="transparent", hover_color=theme.get_current_color('bg_tertiary'),
            command=lambda i=item: self._pick(i)
        )
        row.pack(fill="x", pady=2, padx=2)

        # Overlay two lines of text on the button (name + subtitle) since
        # CTkButton is single-line - a small inner frame gives real layout.
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.place(relx=0, rely=0.5, anchor="w", x=12)
        ctk.CTkLabel(
            inner, text=item.name, font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.get_current_color('text_primary'), anchor="w"
        ).pack(anchor="w")
        subtitle = self._subtitle_fn(item)
        if subtitle:
            ctk.CTkLabel(
                inner, text=subtitle, font=ctk.CTkFont(size=11),
                text_color=theme.get_text_secondary(), anchor="w"
            ).pack(anchor="w")

    def _pick(self, item):
        self.result = item
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class PickCharacterDialog(ctk.CTkToplevel):
    """Small modal that just asks "which character?" - used by the Equipment
    and Magic Items collection pages' "Add to Character" right-click action.
    ``self.result`` is the chosen character's name, or ``None`` if cancelled.
    """

    def __init__(self, parent, prompt: str, characters: List):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.result: Optional[str] = None

        self.title("Add to Character")
        self.geometry("350x200")
        self.transient(parent)
        self.grab_set()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content, text=prompt, font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=300, justify="left"
        ).pack(anchor="w", pady=(0, 15))

        character_names = [c.name for c in characters]
        self.char_var = ctk.StringVar(value=character_names[0] if character_names else "")
        self.char_combo = ctk.CTkComboBox(
            content, width=280, height=35,
            values=character_names, variable=self.char_var, state="readonly"
        )
        self.char_combo.pack(fill="x", pady=(0, 20))

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1,
            command=self.destroy
        ).pack(side="right", padx=(5, 0))
        ctk.CTkButton(
            btn_frame, text="Add", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            command=self._on_add
        ).pack(side="right")

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _on_add(self):
        self.result = self.char_var.get()
        self.destroy()


def pick_equipment(parent) -> Optional[object]:
    """Open the equipment picker and return the chosen Equipment, or None."""
    from equipment import get_equipment_manager

    manager = get_equipment_manager()

    def subtitle(item):
        parts = [item.type] if item.type else []
        if item.cost:
            parts.append(item.cost)
        parts.append(item.display_weight())
        return "  •  ".join(parts)

    dialog = ItemPickerDialog(
        parent, "Add Equipment", manager.items, subtitle,
        lambda q: manager.search_items(q)
    )
    parent.wait_window(dialog)
    return dialog.result


def pick_magic_item(parent) -> Optional[object]:
    """Open the magic item picker and return the chosen MagicItem, or None."""
    from magic_item import get_magic_item_manager

    manager = get_magic_item_manager()

    def subtitle(item):
        parts = [item.rarity.value]
        attunement = item.display_attunement()
        if attunement:
            parts.append(attunement)
        parts.append(item.display_weight())
        return "  •  ".join(parts)

    dialog = ItemPickerDialog(
        parent, "Add Magic Item", manager.items, subtitle,
        lambda q: manager.search_items(q)
    )
    parent.wait_window(dialog)
    return dialog.result
