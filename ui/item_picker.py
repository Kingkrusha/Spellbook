"""
Search-and-pick dialog for adding a catalog item (equipment or magic item) to
a character sheet's inventory.

Used by the inventory tab's "+ Add Equipment" / "+ Add Item" buttons: the user
searches/browses the Equipment or Magic Items collection and picks one, which
the caller then turns into a linked inventory row (see character_sheet_view.py's
_add_equipment_item / _add_magic_item).
"""

from ui.window_utils import add_cancel_save, center_on_parent
from typing import Callable, List, Optional

import customtkinter as ctk

from typography import ui_font
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
    collection). Every row has a green **Add** button, like the spell list's Add
    Spells dialog. With ``add_fn(item) -> bool`` the dialog stays open and adds
    each item as it is clicked (``self.added`` lists the names, a row shows how
    many of it were added); without it, Add picks the item and closes, and
    ``self.result`` is the picked domain object (``None`` if cancelled).
    ``hide_fn(item) -> bool`` leaves out items that cannot be picked again (feats the character already has).
    """

    def __init__(self, parent, title: str, items: List, subtitle_fn: Callable[[object], str],
                 search_fn: Callable[[str], List], add_fn: Optional[Callable[[object], bool]] = None,
                 hide_fn: Optional[Callable[[object], bool]] = None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.result = None
        self.add_fn = add_fn
        self._hide_fn = hide_fn
        self.added: List[str] = []
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

        center_on_parent(self, parent, clamp=True)

    def _create_widgets(self, title: str):
        theme = self.theme
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            container, text=title, font=ui_font("heading", 16, bold=True)
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
        if self.add_fn is not None:
            ctk.CTkButton(
                btn_frame, text="Done", width=110,
                fg_color=theme.get_current_color('accent_primary'),
                hover_color=theme.get_current_color('accent_hover'),
                text_color=theme.get_current_color('text_on_accent'),
                command=self._on_cancel
            ).pack(side="right")
        else:
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

        if self._hide_fn is not None:
            items = [i for i in items if not self._hide_fn(i)]
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
                font=ui_font("small"),
                text_color=self.theme.get_text_secondary(),
            ).pack(pady=(6, 4))

    def _create_row(self, item):
        c = self.theme.get_current_color
        row = ctk.CTkFrame(self.list_frame, fg_color=c("spell_row"), corner_radius=6)
        row.pack(fill="x", pady=2, padx=2)
        ctk.CTkButton(
            row, text="Add", width=64, height=28, fg_color=c("button_success"),
            hover_color=c("button_success_hover"), text_color=c("text_primary"),
            command=lambda i=item: self._add(i)
        ).pack(side="right", padx=8, pady=4)
        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=4)
        name_row = ctk.CTkFrame(text, fg_color="transparent")
        name_row.pack(fill="x")
        ctk.CTkLabel(name_row, text=item.name, font=ui_font("subheading", 13, bold=True), anchor="w"
                     ).pack(side="left")
        count = self.added.count(item.name)
        if count:
            ctk.CTkLabel(name_row, text=f"  added ×{count}" if count > 1 else "  added ✓", font=ui_font("small"),
                         text_color=c("button_success")).pack(side="left")
        subtitle = self._subtitle_fn(item)
        if subtitle:
            ctk.CTkLabel(text, text=subtitle, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                         anchor="w", justify="left", wraplength=330).pack(fill="x")

    def _add(self, item):
        """The green Add button: add it and stay open, or (no ``add_fn``) pick it and close."""
        if self.add_fn is None:
            self._pick(item)
            return
        if self.add_fn(item):
            self.added.append(item.name)
            self._run_search()

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
            content, text=prompt, font=ui_font("subheading", bold=True),
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
        add_cancel_save(btn_frame, self.theme, self.destroy, self._on_add, confirm_text="Add", outlined=True)

        center_on_parent(self, parent, clamp=True)

    def _on_add(self):
        self.result = self.char_var.get()
        self.destroy()


def pick_equipment(parent, add_fn: Optional[Callable[[object], bool]] = None) -> Optional[object]:
    """Open the equipment picker and return the chosen Equipment, or None. With ``add_fn`` the dialog adds each item
    as its Add button is clicked and stays open; the return value is then the list of names added."""
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
        lambda q: manager.search_items(q), add_fn=add_fn
    )
    parent.wait_window(dialog)
    return dialog.added if add_fn is not None else dialog.result


def pick_feat(parent, owned: List[str], add_fn: Callable[[object], bool]) -> List[str]:
    """Open the feat picker (same layout as the equipment and spell pickers); returns the names added. Feats named in
    ``owned`` are not offered, and one disappears from the list once added."""
    from feat import get_feat_manager
    from legacy_content import apply_legacy_filter
    from settings import get_settings_manager

    manager = get_feat_manager()
    taken = set(owned)

    def visible():
        return apply_legacy_filter(manager.feats, get_settings_manager().settings.legacy_content_filter)

    def subtitle(feat):
        parts = [feat.type] if feat.type else []
        if feat.is_spellcasting:
            parts.append("Spellcasting")
        if feat.has_prereq and feat.prereq:
            parts.append(f"Prerequisite: {feat.prereq}")
        return "  •  ".join(parts)

    def search(query):
        q = query.lower()
        return [f for f in visible() if q in f.name.lower() or q in (f.type or "").lower()
                or q in f.plain_description().lower()]

    def add(feat) -> bool:
        if feat.name in taken or not add_fn(feat):
            return False
        taken.add(feat.name)
        return True

    dialog = ItemPickerDialog(parent, "Add Feat", visible(), subtitle, search, add_fn=add,
                              hide_fn=lambda f: f.name in taken)
    parent.wait_window(dialog)
    return dialog.added


def pick_magic_item(parent, add_fn: Optional[Callable[[object], bool]] = None) -> Optional[object]:
    """Open the magic item picker and return the chosen MagicItem, or None (see ``pick_equipment`` for ``add_fn``)."""
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
        lambda q: manager.search_items(q), add_fn=add_fn
    )
    parent.wait_window(dialog)
    return dialog.added if add_fn is not None else dialog.result
