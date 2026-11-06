"""
Equipment View for D&D 5e Spellbook Application.
Displays a searchable/filterable list of equipment with a details panel,
laid out the same way as the Spells/Feats pages.
"""

import re
import customtkinter as ctk
from typography import ui_font
from typing import List, Optional

from equipment import Equipment, DEFAULT_EQUIPMENT_TYPE, get_equipment_manager
from ui.item_editor_base import ItemEditorBody
from ui.item_view_base import ItemDetailBase, ItemViewBase
from ui.virtual_list import VirtualListPanel
from ui.editor_host import DialogWindow, EmbeddedWindow
from ui.extra_fields import show_extra_fields


class EquipmentListPanel(VirtualListPanel):
    """The virtualized, selectable list of equipment."""

    TITLE = "Equipment"
    NOUN = "item"

    def row_text(self, item: Equipment) -> str:
        name = f"* {item.name}" if item.is_custom else item.name
        return f"{name}  ({item.type})" if item.type else name

    def get_selected_item(self) -> Optional[Equipment]:
        return self.get_selected()

    def select_item(self, name: str) -> bool:
        return self.select_by_name(name)


class EquipmentDetailPanel(ItemDetailBase):
    """Panel displaying detailed information about an equipment item.

    Any optional field left blank on the item (source, crafting materials,
    crafting tool, tags) is simply not shown - its row's frame is never
    packed rather than being packed empty.
    """
    IMAGE_KIND = "equipment"

    def _create_widgets(self):
        self._add_scroll_and_name()

        self.type_badge = ctk.CTkLabel(
            self.scroll_frame, text="",
            font=ui_font("small"),
            fg_color=self.theme.get_current_color('accent_primary'),
            corner_radius=5, padx=8, pady=2
        )

        self._add_stats_label()
        self._add_source_label()

        self.crafting_frame = ctk.CTkFrame(
            self.scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8
        )
        # A link-aware text box (not a plain label) so crafting tool names can
        # be clicked to open that tool.
        from ui.rich_text_utils import DynamicText
        self.crafting_text = DynamicText(self.crafting_frame, self.theme, bg_color='bg_secondary')
        self.crafting_text.pack(fill="x", padx=10, pady=8)

        self._add_tags_label()
        self._add_properties_and_description()

    def _update_colors(self):
        self.type_badge.configure(fg_color=self.theme.get_current_color('accent_primary'))
        self.crafting_frame.configure(fg_color=self.theme.get_current_color('bg_secondary'))
        self.tags_label.configure(text_color=self.theme.get_current_color('accent_primary'))

    @staticmethod
    def _crafting_tool_markup(text: str) -> str:
        """Turn a crafting-tool string into text with [[equipment:...]] links.

        The field is free text ("Smith's Tools", "Carpenter's Tools or
        Woodcarver's Tools"), so each name is only linked when it matches an
        equipment item; anything else (homebrew wording) is left as plain text.
        """
        manager = get_equipment_manager()

        def link(name: str) -> str:
            name = name.strip()
            item = manager.get_item(name) if name else None
            return f"[[equipment:{item.name}|{name}]]" if item else name

        whole = manager.get_item(text.strip())
        if whole:
            return link(text)
        parts = [p for p in re.split(r"\s+or\s+|,\s*(?:or\s+)?", text) if p.strip()]
        if len(parts) <= 1:
            return link(text)
        # Preserve the author's separators: re-join with " or ".
        return " or ".join(link(p) for p in parts)

    def show_item(self, item: Optional[Equipment]):
        """Display an item, then the fields the user added to Equipment (custom_collections.py)."""
        self._show_item_details(item)
        show_extra_fields(self, "equipment", item.name if item else None)

    def _show_item_details(self, item: Optional[Equipment]):
        self._current_item = item

        # Detach every dynamic row first, then re-pack the ones we need in a
        # fixed order - so a row's position never depends on which item was
        # shown before this one.
        for w in (self.type_badge, self.stats_label, self.crafting_frame,
                  self.tags_label, self.properties_frame, self.desc_frame,
                  self.source_label):
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

        self.type_badge.configure(text=item.type or DEFAULT_EQUIPMENT_TYPE)
        self.type_badge.pack(anchor="w", pady=(0, 5))

        stats_parts = []
        if item.cost:
            stats_parts.append(f"Cost: {item.cost}")
        stats_parts.append(f"Weight: {item.display_weight()}")
        self.stats_label.configure(text="   •   ".join(stats_parts))
        self.stats_label.pack(anchor="w", pady=(0, 10))

        crafting_lines = []
        if item.crafting_materials:
            crafting_lines.append(f"Crafting Materials: {', '.join(item.crafting_materials)}")
        if item.crafting_tool:
            crafting_lines.append(f"Crafting Tool: {self._crafting_tool_markup(item.crafting_tool)}")
        if crafting_lines:
            self.crafting_text.set_text("\n".join(crafting_lines))
            self.crafting_frame.pack(fill="x", pady=(0, 10))

        if item.tags:
            self.tags_label.configure(text=item.display_tags())
            self.tags_label.pack(anchor="w", pady=(0, 10))

        self._render_properties(item.properties)

        self._render_description(item.description)

        self._show_source_footer(item)


class EquipmentEditorBody(ItemEditorBody):
    """Dialog for creating or editing an equipment item. (the form; see ui/editor_host.py)"""

    MANAGER_GETTER = staticmethod(get_equipment_manager)
    DEFAULT_TYPE = DEFAULT_EQUIPMENT_TYPE
    GEOMETRY = "600x820"
    MINSIZE = (550, 650)
    REVIEW_NOTE = ("Auto-detection is rule-based, not perfect - accuracy drops for "
                   "irregularly formatted text. Nothing is saved until you click Save.")

    equipment_manager = property(lambda self: self.item_manager)

    _REVIEW_FIELD_LABELS = {
        "name": "Name", "type": "Type", "cost": "Cost", "weight": "Weight",
        "source": "Source", "crafting_materials": "Crafting Materials",
        "crafting_tool": "Crafting Tool", "description": "Description", "tags": "Tags",
        "properties": "Properties",
    }

    def _build_fields(self, scroll):
        row1 = ctk.CTkFrame(scroll, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 10))
        self._add_type_column(row1)
        self._add_cost_and_weight(row1)

        self._add_source_entry(scroll)
        self.crafting_materials_entry = self._add_text_field(
            scroll, "Crafting Materials (comma-separated)", "e.g., Iron, Leather Strips")
        self.crafting_tool_entry = self._add_text_field(scroll, "Crafting Tool", "e.g., Smith's Tools")

    def _populate_from_item(self, item: Equipment):
        self._populate_common(item)
        if item.crafting_materials:
            self.crafting_materials_entry.insert(0, ", ".join(item.crafting_materials))
        if item.crafting_tool:
            self.crafting_tool_entry.insert(0, item.crafting_tool)

    def _review_widgets(self) -> dict:
        return {**super()._review_widgets(),
                "crafting_materials": self.crafting_materials_entry,
                "crafting_tool": self.crafting_tool_entry}

    def build_result(self, strict: bool = True) -> Equipment:
        """The item the form describes (strict: ValueError if incomplete; otherwise gaps are filled in)."""
        fields = self._common_fields(strict)
        return Equipment(
            **fields,
            crafting_materials=self._comma_list(self.crafting_materials_entry.get()),
            crafting_tool=self.crafting_tool_entry.get().strip(),
        )

class EquipmentEditorDialog(EquipmentEditorBody, DialogWindow):
    """Dialog for creating or editing an equipment item."""


class EquipmentEditorPanel(EquipmentEditorBody, EmbeddedWindow):
    """The EquipmentEditorDialog form inside the Homebrew Studio."""


class EquipmentView(ItemViewBase):
    """Main view for browsing and managing equipment."""

    MANAGER_GETTER = staticmethod(get_equipment_manager)
    LIST_PANEL = EquipmentListPanel
    DETAIL_PANEL = EquipmentDetailPanel
    EDITOR_DIALOG = EquipmentEditorDialog
    ADD_TITLE = "Add Equipment"
    EDIT_TITLE = "Edit Equipment"
    STUDIO_KIND = "equipment"
    MATERIAL_NOUN = "crafting"
    PLURAL = "equipment"

    equipment_manager = property(lambda self: self.item_manager)

    def _item_materials(self, item) -> List[str]:
        return item.crafting_materials

    def _all_materials(self) -> List[str]:
        return self.item_manager.get_all_crafting_materials()

    def _add_to_sheet(self, sheet, item):
        sheet.equipment_items.append({
            "name": item.name,
            "quantity": 1,
            "weight": item.weight,
        })

    def _text_import(self):
        from ui.equipment_text_import import AddEquipmentSourceDialog, EquipmentTextImportDialog

        def to_draft():
            from text_import.equipment_parser import to_equipment
            return to_equipment
        return AddEquipmentSourceDialog, EquipmentTextImportDialog, to_draft

    def _create_filter_bar(self):
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=10, pady=10)

        self._add_back_button(filter_bar)
        self._add_search_and_type(filter_bar, "Search equipment...", 170, (0, 15), 170, (0, 15))
        self._add_action_buttons(filter_bar, "+ Add Equipment", 130, self._on_add_item,
                                 self._on_edit_item, self._on_delete_item, start_disabled=True)

        # Second row: source, official content, crafting tool
        filter_bar2 = self._filter_row(pady=(0, 5))
        self._add_source_filter(filter_bar2)
        self._add_content_filter(filter_bar2)
        self._add_filter_combo(filter_bar2, "crafting_tool", "Crafting Tool:", "Any Tool", ["Any Tool"],
                               160, padx=0)

        # Third row: tags, crafting materials, price range, clear
        filter_bar3 = self._filter_row()
        self._add_tags_filter(filter_bar3, end_padx=(0, 20))
        self._add_price_filter(filter_bar3)

    def _load_extra_options(self):
        tool_options = ["Any Tool"] + self.item_manager.get_all_crafting_tools()
        self.crafting_tool_combo.configure(values=tool_options)
        if self.crafting_tool_var.get() not in tool_options:
            self.crafting_tool_var.set("Any Tool")

    def _clear_extra_filters(self):
        self.crafting_tool_var.set("Any Tool")

    def _extra_filter(self):
        tool = self.crafting_tool_var.get()
        if tool == "Any Tool":
            return None
        return lambda item: item.crafting_tool == tool
