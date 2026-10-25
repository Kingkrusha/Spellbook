"""
Magic Item View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of magic items with a details panel,
laid out the same way as the Spells/Feats pages.
"""

import customtkinter as ctk
from typography import ui_font
from ui.label_text import LabeledLabel
from typing import List, Optional

from magic_item import MagicItem, Rarity, DEFAULT_MAGIC_ITEM_TYPE, get_magic_item_manager
from ui.item_editor_base import ItemEditorBody
from ui.item_view_base import ItemDetailBase, ItemViewBase
from ui.virtual_list import VirtualListPanel
from ui.editor_host import DialogWindow, EmbeddedWindow
from ui.extra_fields import show_extra_fields

# Conventional rarity colors, independent of the app's colour theme so
# rarity reads consistently at a glance regardless of theme choice.
RARITY_COLORS = {
    Rarity.COMMON: "#8a8a8a",
    Rarity.UNCOMMON: "#1e8449",
    Rarity.RARE: "#2874a6",
    Rarity.VERY_RARE: "#7d3c98",
    Rarity.LEGENDARY: "#ca6f1e",
    Rarity.ARTIFACT: "#b03a2e",
    Rarity.VARIES: "#5d6d7e",
}


class MagicItemListPanel(VirtualListPanel):
    """The virtualized, selectable list of magic items (rows coloured by rarity)."""

    TITLE = "Magic Items"
    NOUN = "item"

    def row_text(self, item: MagicItem) -> str:
        name = f"* {item.name}" if item.is_custom else item.name
        return f"{name}  ({item.rarity.value})"

    def row_text_color(self, item: MagicItem):
        return RARITY_COLORS.get(item.rarity, self.theme.get_current_color('text_primary'))

    def get_selected_item(self) -> Optional[MagicItem]:
        return self.get_selected()

    def select_item(self, name: str) -> bool:
        return self.select_by_name(name)


class MagicItemDetailPanel(ItemDetailBase):
    """Panel displaying detailed information about a magic item.

    Any optional field left blank on the item (attunement, source, enchanting
    materials, tags) is simply not shown - its row's frame is never packed
    rather than being packed empty.
    """
    IMAGE_KIND = "magic_items"

    def _create_widgets(self):
        self._add_scroll_and_name()

        badge_row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.badge_row = badge_row

        self.rarity_badge = ctk.CTkLabel(
            badge_row, text="", font=ui_font("small", bold=True),
            corner_radius=5, padx=8, pady=2, text_color="#ffffff"
        )
        self.rarity_badge.pack(side="left", padx=(0, 6))

        self.type_badge = ctk.CTkLabel(
            badge_row, text="", font=ui_font("small"),
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5, padx=8, pady=2
        )
        self.type_badge.pack(side="left")

        self._add_stats_label()

        self.attunement_label = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ui_font("body", bold=True),
            text_color=self.theme.get_current_color('button_warning'),
            wraplength=400, justify="left"
        )

        self._add_source_label()

        self.crafting_frame = ctk.CTkFrame(
            self.scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8
        )
        self.crafting_label = LabeledLabel(
            self.crafting_frame, text="", font=ui_font("body"),
            wraplength=380, justify="left", anchor="w"
        )
        self.crafting_label.pack(padx=10, pady=8, anchor="w")

        self._add_tags_label()
        self._add_properties_and_description()

    def _update_colors(self):
        self.type_badge.configure(fg_color=self.theme.get_current_color('accent_primary'))
        self.attunement_label.configure(text_color=self.theme.get_current_color('button_warning'))
        self.crafting_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
        self.tags_label.configure(text_color=self.theme.get_current_color('accent_primary'))

    def show_item(self, item: Optional[MagicItem]):
        """Display an item, then the fields the user added to Magic Items (custom_collections.py)."""
        self._show_item_details(item)
        show_extra_fields(self, "magic_items", item.name if item else None)

    def _show_item_details(self, item: Optional[MagicItem]):
        self._current_item = item

        # Detach every dynamic row first, then re-pack what we need in a fixed
        # order - so a row's position never depends on the previously shown item.
        for w in (self.badge_row, self.stats_label, self.attunement_label,
                  self.crafting_frame, self.tags_label, self.properties_frame,
                  self.desc_frame, self.source_label):
            w.pack_forget()
        self._clear_description()

        if item is None:
            self.name_label.configure(text="Select an item")
            self._show_picture(None)
            self._render_properties(None)
            return

        name_text = f"* {item.name}" if item.is_custom else item.name
        self.name_label.configure(text=name_text)
        self._show_picture(item.name)

        self.rarity_badge.configure(
            text=item.rarity.value,
            fg_color=RARITY_COLORS.get(item.rarity, "#8a8a8a"),
        )
        self.type_badge.configure(text=item.type or DEFAULT_MAGIC_ITEM_TYPE)
        self.badge_row.pack(anchor="w", pady=(0, 5))

        stats_parts = []
        if item.cost:
            stats_parts.append(f"Cost: {item.cost}")
        if item.weight:
            stats_parts.append(f"Weight: {item.display_weight()}")
        if stats_parts:
            self.stats_label.configure(text="   •   ".join(stats_parts))
            self.stats_label.pack(anchor="w", pady=(0, 5))

        attunement_text = item.display_attunement()
        if attunement_text:
            self.attunement_label.configure(text=attunement_text)
            self.attunement_label.pack(anchor="w", pady=(0, 10))

        if item.enchanting_materials:
            self.crafting_label.configure(
                text=f"Enchanting Materials: {', '.join(item.enchanting_materials)}"
            )
            self.crafting_frame.pack(fill="x", pady=(0, 10))

        if item.tags:
            self.tags_label.configure(text=item.display_tags())
            self.tags_label.pack(anchor="w", pady=(0, 10))

        self._render_properties(item.properties)

        self._render_description(item.description)

        self._show_source_footer(item)


class MagicItemEditorBody(ItemEditorBody):
    """The form for creating or editing a magic item (see ui/editor_host.py)."""

    MANAGER_GETTER = staticmethod(get_magic_item_manager)
    DEFAULT_TYPE = DEFAULT_MAGIC_ITEM_TYPE
    GEOMETRY = "600x900"
    MINSIZE = (550, 700)
    TYPE_WIDTH = 180
    COST_WIDTH = 150
    COST_PLACEHOLDER = "e.g. 500 gp"
    REVIEW_NOTE = ("Auto-detection is rule-based, not perfect - accuracy drops for "
                   "irregularly formatted text, and cost/weight are rarely stated "
                   "in magic item text. Nothing is saved until you click Save.")

    magic_item_manager = property(lambda self: self.item_manager)

    _REVIEW_FIELD_LABELS = {
        "name": "Name", "type": "Type", "rarity": "Rarity", "cost": "Cost",
        "weight": "Weight", "source": "Source", "enchanting_materials": "Enchanting Materials",
        "requires_attunement": "Requires Attunement",
        "attunement_requirement": "Attunement Restriction", "attunement_optional": "Attunement Optional",
        "description": "Description", "tags": "Tags", "properties": "Properties",
    }

    def _build_fields(self, scroll):
        row1 = ctk.CTkFrame(scroll, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))
        self._add_type_column(row1)

        rarity_col = self._field_column(row1, "Rarity", padx=0)
        self.rarity_var = ctk.StringVar(value=Rarity.COMMON.value)
        self.rarity_combo = ctk.CTkComboBox(
            rarity_col, width=150, values=Rarity.all_values(),
            variable=self.rarity_var, state="readonly"
        )
        self.rarity_combo.pack()

        row2 = ctk.CTkFrame(scroll, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 10))
        self._add_cost_and_weight(row2)

        self._field_label(scroll, "Attunement")
        self.requires_attunement_var = ctk.BooleanVar(value=False)
        self.requires_attunement_check = ctk.CTkCheckBox(
            scroll, text="Requires Attunement",
            variable=self.requires_attunement_var,
            command=self._sync_attunement_state,
        )
        self.requires_attunement_check.pack(anchor="w", pady=(2, 2))

        ctk.CTkLabel(
            scroll, text="Restriction (optional) - e.g. \"by a Wizard\", \"by a Spellcaster\". "
                         "Leave blank for a plain \"Requires Attunement\".",
            font=ui_font("small"), text_color=self.theme.get_text_secondary(),
            justify="left", wraplength=500,
        ).pack(anchor="w")
        self.attunement_entry = ctk.CTkEntry(
            scroll, width=400, placeholder_text="e.g., by a Spellcaster")
        self.attunement_entry.pack(fill="x", pady=(2, 5))

        self.attunement_optional_var = ctk.BooleanVar(value=False)
        self.attunement_optional_check = ctk.CTkCheckBox(
            scroll, text="Attunement is optional (item still works without it)",
            variable=self.attunement_optional_var
        )
        self.attunement_optional_check.pack(anchor="w", pady=(0, 10))

        self._add_source_entry(scroll)
        self.enchanting_materials_entry = self._add_text_field(
            scroll, "Enchanting Materials (comma-separated)", "e.g., Phoenix Feather, Moonstone Dust")

    def _build_extras(self, scroll):
        from ui.roll_effects_editor import RollEffectsEditor
        self.roll_editor = RollEffectsEditor(scroll, allow_item_effects=True)
        self.roll_editor.pack(fill="x", pady=(0, 10))

    def _sync_attunement_state(self):
        """The restriction entry and 'optional' checkbox only matter once
        'Requires Attunement' is checked."""
        if self.requires_attunement_var.get():
            self.attunement_entry.configure(state="normal")
            self.attunement_optional_check.configure(state="normal")
        else:
            self.attunement_entry.configure(state="disabled")
            self.attunement_optional_var.set(False)
            self.attunement_optional_check.configure(state="disabled")

    # Backwards-compatible alias (older call sites / auto-detect flow).
    _toggle_attunement_optional = _sync_attunement_state

    def _populate_empty(self):
        self._toggle_attunement_optional()

    def _populate_from_item(self, item: MagicItem):
        self._populate_common(item)
        self.rarity_var.set(item.rarity.value)
        self.requires_attunement_var.set(item.requires_attunement)
        if item.attunement_requirement:
            self.attunement_entry.insert(0, item.attunement_requirement)
        self.attunement_optional_var.set(item.attunement_optional)
        self._sync_attunement_state()
        if item.enchanting_materials:
            self.enchanting_materials_entry.insert(0, ", ".join(item.enchanting_materials))
        self.roll_editor.set(item.roll_effects)

    def _review_widgets(self) -> dict:
        return {**super()._review_widgets(),
                "rarity": self.rarity_combo,
                "enchanting_materials": self.enchanting_materials_entry,
                "attunement_requirement": self.attunement_entry}

    def build_result(self, strict: bool = True) -> MagicItem:
        """The item the form describes. Strict (Save): raises ValueError if it is incomplete. Otherwise gaps are
        filled in (a half-written draft)."""
        fields = self._common_fields(strict)
        requires_attunement = self.requires_attunement_var.get()
        return MagicItem(
            **fields,
            enchanting_materials=self._comma_list(self.enchanting_materials_entry.get()),
            rarity=Rarity.from_string(self.rarity_var.get()),
            requires_attunement=requires_attunement,
            attunement_requirement=self.attunement_entry.get().strip() if requires_attunement else "",
            attunement_optional=self.attunement_optional_var.get() if requires_attunement else False,
            roll_effects=self.roll_editor.get(),
        )

class MagicItemEditorDialog(MagicItemEditorBody, DialogWindow):
    """Dialog for creating or editing a magic item."""


class MagicItemEditorPanel(MagicItemEditorBody, EmbeddedWindow):
    """The magic item form inside the Homebrew Studio."""


class MagicItemView(ItemViewBase):
    """Main view for browsing and managing magic items."""

    MANAGER_GETTER = staticmethod(get_magic_item_manager)
    LIST_PANEL = MagicItemListPanel
    DETAIL_PANEL = MagicItemDetailPanel
    EDITOR_DIALOG = MagicItemEditorDialog
    ADD_TITLE = "Add Magic Item"
    EDIT_TITLE = "Edit Magic Item"
    STUDIO_KIND = "magic_items"
    MATERIAL_NOUN = "enchanting"
    PLURAL = "magic items"

    magic_item_manager = property(lambda self: self.item_manager)

    def _item_materials(self, item) -> List[str]:
        return item.enchanting_materials

    def _all_materials(self) -> List[str]:
        return self.item_manager.get_all_enchanting_materials()

    def _add_to_sheet(self, sheet, item):
        sheet.magic_items.append({
            "name": item.name,
            "description": item.description,
            "attuned": False,
            "requires_attunement": item.requires_attunement,
            "extra_properties": "",
        })

    def _text_import(self):
        from ui.magic_item_text_import import AddMagicItemSourceDialog, MagicItemTextImportDialog

        def to_draft():
            from text_import.magic_item_parser import to_magic_item
            return to_magic_item
        return AddMagicItemSourceDialog, MagicItemTextImportDialog, to_draft

    def _create_filter_bar(self):
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)

        self._add_back_button(filter_bar)
        self._add_search_and_type(filter_bar, "Search magic items...", 150, (0, 10), 150, (0, 10))
        self._add_filter_combo(filter_bar, "rarity", "Rarity:", "All Rarities",
                               ["All Rarities"] + Rarity.all_values(), 130, (0, 10))

        self.attunement_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            filter_bar, text="Requires Attunement",
            variable=self.attunement_var,
            command=lambda: self._on_filter_changed(immediate=True)
        ).pack(side="left")

        self._add_action_buttons(filter_bar, "+ Add Magic Item", 140, self._on_add_item,
                                 self._on_edit_item, self._on_delete_item, start_disabled=True)

        # Second row: source, official content, tags
        filter_bar2 = self._filter_row(pady=(0, 5))
        self._add_source_filter(filter_bar2)
        self._add_content_filter(filter_bar2)
        self._add_tags_filter(filter_bar2, end_padx=0)

        # Third row: enchanting materials, price range, clear
        filter_bar3 = self._filter_row()
        self._add_price_filter(filter_bar3)

    def _clear_extra_filters(self):
        self.rarity_var.set("All Rarities")
        self.attunement_var.set(False)

    def _extra_filter(self):
        rarity = self.rarity_var.get()
        attunement_only = self.attunement_var.get()
        if rarity == "All Rarities" and not attunement_only:
            return None
        return lambda item: ((rarity == "All Rarities" or item.rarity.value == rarity)
                             and (not attunement_only or item.requires_attunement))
