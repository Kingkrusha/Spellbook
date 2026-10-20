"""
The editor form shared by equipment and magic items: the same name, type, cost, weight, source, tags,
properties and description, with a few fields of its own on each side. A subclass lays out its fields
(``_build_fields``), says what else to read and fill in, and supplies the model and manager.
"""

from typing import Dict, List, Optional

import customtkinter as ctk

from theme import get_theme_manager
from ui.editor_host import EditorBody
from ui.properties_editor import PropertiesEditor
from ui.review_banner import add_review_banner, outline_fields
from ui.tag_editor import TagEditor
from ui.window_utils import center_on_parent


class ItemEditorBody(EditorBody):
    # Subclass configuration -------------------------------------------------
    MANAGER_GETTER = None                # callable returning the manager
    DEFAULT_TYPE = ""
    GEOMETRY = "600x820"
    MINSIZE = (550, 650)
    TYPE_WIDTH = 200
    COST_WIDTH = 100
    COST_PLACEHOLDER = "e.g. 5 gp"
    REVIEW_NOTE = ""
    _REVIEW_FIELD_LABELS: Dict[str, str] = {}

    def __init__(self, parent, title: str, item=None, prefill_item=None,
                 review_fields: Optional[List[str]] = None, batch_progress: str = ""):
        super().__init__(parent)
        self.title(title)
        self.geometry(self.GEOMETRY)
        self.minsize(*self.MINSIZE)
        self.transient(parent)
        self.grab_set()

        self.theme = get_theme_manager()
        self.item_manager = self.MANAGER_GETTER()
        self.result = None
        self._editing_item = item
        # Auto-detect pre-fill: populate the form from parsed text but keep
        # this a brand-new item, and mark fields for the reviewer to check.
        self._review_fields = set(review_fields or [])
        self._batch_progress = batch_progress

        self._create_widgets()
        if item:
            self._populate_from_item(item)
        elif prefill_item:
            self._populate_from_item(prefill_item)
            self._apply_review_highlights()
        else:
            self._populate_empty()

        center_on_parent(self, parent)

    # ---- hooks -----------------------------------------------------------------

    def _build_fields(self, scroll):
        """Lay out the fields between the name and the tags (type, cost, weight, source ...)."""
        raise NotImplementedError

    def _build_extras(self, scroll):
        """Anything after the description (the roll effects of a magic item)."""

    def _populate_from_item(self, item):
        raise NotImplementedError

    def _populate_empty(self):
        """A brand-new, empty form."""

    def _review_widgets(self) -> dict:
        """Field name -> widget, for the outline of an uncertain field."""
        return {
            "name": self.name_entry,
            "type": self.type_combo,
            "cost": self.cost_entry,
            "weight": self.weight_entry,
            "source": self.source_entry,
        }

    # ---- the form -----------------------------------------------------------------

    def _create_widgets(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        self._scroll = scroll

        self._field_label(scroll, "Name *")
        self.name_entry = ctk.CTkEntry(scroll, width=400)
        self.name_entry.pack(fill="x", pady=(0, 10))

        self._build_fields(scroll)

        self.tag_editor = TagEditor(scroll, get_available_tags=self.item_manager.get_all_tags)
        self.tag_editor.pack(fill="x", pady=(0, 10))

        self.properties_editor = PropertiesEditor(
            scroll, get_suggestions=self.item_manager.get_all_properties)
        self.properties_editor.pack(fill="x", pady=(0, 10))

        self._add_description_editor(scroll)
        self._build_extras(scroll)
        self._add_save_buttons(scroll)

    def _field_column(self, row, text: str, padx=(0, 15)):
        """A column of a row of fields: a frame with its heading; the field goes in it."""
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", padx=padx)
        self._field_label(col, text)
        return col

    def _add_type_column(self, row):
        col = self._field_column(row, "Type")
        type_options = sorted(set(self.item_manager.TYPE_OPTIONS) | set(self.item_manager.get_all_types()))
        self.type_var = ctk.StringVar(value=self.DEFAULT_TYPE)
        self.type_combo = ctk.CTkComboBox(col, width=self.TYPE_WIDTH, values=type_options, variable=self.type_var)
        self.type_combo.pack()

    def _add_cost_and_weight(self, row):
        col = self._field_column(row, "Cost")
        self.cost_entry = ctk.CTkEntry(col, width=self.COST_WIDTH, placeholder_text=self.COST_PLACEHOLDER)
        self.cost_entry.pack()

        col = self._field_column(row, "Weight (lb)", padx=0)
        self.weight_entry = ctk.CTkEntry(col, width=80, placeholder_text="0")
        self.weight_entry.pack()

    def _add_source_entry(self, scroll):
        self._field_label(scroll, "Source")
        self.source_entry = ctk.CTkEntry(scroll, width=400, placeholder_text="e.g., Homebrew, Custom Campaign")
        self.source_entry.pack(fill="x", pady=(0, 10))

    def _add_text_field(self, scroll, label: str, placeholder: str) -> ctk.CTkEntry:
        """A full-width one-line field under its heading."""
        self._field_label(scroll, label)
        entry = ctk.CTkEntry(scroll, width=400, placeholder_text=placeholder)
        entry.pack(fill="x", pady=(0, 10))
        return entry

    # ---- filling it in --------------------------------------------------------------

    def _populate_common(self, item):
        self.name_entry.insert(0, item.name)
        self.type_var.set(item.type or self.DEFAULT_TYPE)
        if item.cost:
            self.cost_entry.insert(0, item.cost)
        self.weight_entry.insert(0, str(item.weight) if item.weight else "0")
        if item.source:
            self.source_entry.insert(0, item.source)
        self.tag_editor.set_tags(item.tags)
        self.properties_editor.set_properties(item.properties)
        self.desc_text.insert("1.0", item.description)

    def _apply_review_highlights(self):
        """Add the auto-detect disclaimer banner and outline uncertain fields."""
        banner, warn = add_review_banner(
            self, self._scroll, self._review_fields, self._REVIEW_FIELD_LABELS, self._batch_progress,
            self.REVIEW_NOTE, padx=20, wraplength=520)
        outline_fields(self._review_widgets(), self._review_fields, warn)

    # ---- reading it back --------------------------------------------------------------

    def _common_fields(self, strict: bool) -> dict:
        """The fields every item has, as keyword arguments for the model (strict: ValueError if incomplete)."""
        name = self.name_entry.get().strip()
        if not name and strict:
            raise ValueError("Name is required.")

        weight_text = self.weight_entry.get().strip() or "0"
        try:
            weight = float(weight_text)
            if weight < 0:
                raise ValueError
        except ValueError:
            if strict:
                raise ValueError("Weight must be a non-negative number.")
            weight = 0.0

        return dict(
            name=name,
            type=self.type_var.get().strip() or self.DEFAULT_TYPE,
            cost=self.cost_entry.get().strip(),
            weight=weight,
            source=self.source_entry.get().strip(),
            description=self.desc_text.get("1.0", "end-1c").strip(),
            tags=self.tag_editor.get_tags(),
            properties=self.properties_editor.get_properties(),
            is_official=False,
            is_custom=True,
        )

    @staticmethod
    def _comma_list(text: str) -> List[str]:
        return [part.strip() for part in text.split(",") if part.strip()]
