"""
Shared filter widgets for D&D Spellbook collection views.

The spell list was the only page with a full-featured filter bar (multi-select
source/tag dialogs, debounced search, etc.). This module extracts the reusable
pieces so lineages, feats, backgrounds, classes, equipment, and magic items can
all offer the same filtering instead of re-implementing it six times.

``TagFilterMode``/``SourceFilterMode`` are re-exported from :mod:`spell` rather
than redefined here - they're generic (HAS_ALL/HAS_ANY/HAS_NONE and
INCLUDE/EXCLUDE), not spell-specific, and reusing them keeps every collection's
filter state the same type as the spell page's.
"""

import customtkinter as ctk
from typing import Dict, List

from spell import TagFilterMode, SourceFilterMode
from theme import get_theme_manager

__all__ = ["TagFilterMode", "SourceFilterMode", "TagFilterDialog", "SourceFilterDialog"]


class _BaseMultiSelectDialog(ctk.CTkToplevel):
    """Checkbox list + match-mode dropdown for filtering by a set of strings.

    Backs tag filters, source filters, crafting/enchanting-material filters -
    anything that boils down to "pick some strings and how they must match."
    """

    def __init__(self, parent, *, window_title: str, prompt: str,
                 available_values: List[str], selected_values: List[str],
                 mode_enum, current_mode, mode_values: List[str],
                 mode_descriptions: Dict[str, str], empty_message: str,
                 geometry: str = "380x500", minsize=(320, 400)):
        super().__init__(parent)

        self._mode_enum = mode_enum
        self.result: List[str] = list(selected_values)
        self.result_mode = current_mode
        self._value_vars: Dict[str, ctk.BooleanVar] = {}
        self._mode_values = mode_values
        self._mode_descriptions = mode_descriptions

        self.title(window_title)
        self.geometry(geometry)
        self.minsize(*minsize)
        self.resizable(True, True)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self._create_widgets(prompt, available_values, selected_values, current_mode, empty_message)

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self, prompt, available_values, selected_values, current_mode, empty_message):
        theme = get_theme_manager()
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container, text=prompt, font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", pady=(0, 10))

        text_secondary = theme.get_text_secondary()

        mode_frame = ctk.CTkFrame(container, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(mode_frame, text="Filter mode:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 10))

        self._mode_var = ctk.StringVar(value=current_mode.value)
        mode_combo = ctk.CTkComboBox(
            mode_frame, values=self._mode_values, variable=self._mode_var,
            width=180, state="readonly", command=self._on_mode_changed
        )
        mode_combo.pack(side="left")

        self._mode_desc_label = ctk.CTkLabel(
            container, text=self._mode_descriptions.get(current_mode.value, ""),
            font=ctk.CTkFont(size=11), text_color=text_secondary
        )
        self._mode_desc_label.pack(fill="x", pady=(0, 15))

        if not available_values:
            ctk.CTkLabel(
                container, text=empty_message, font=ctk.CTkFont(size=13), text_color=text_secondary
            ).pack(pady=30)
        else:
            scroll = ctk.CTkScrollableFrame(container)
            scroll.pack(fill="both", expand=True, pady=(0, 15))

            selected_lower = [v.lower() for v in selected_values]
            for value in sorted(available_values, key=str.lower):
                var = ctk.BooleanVar(value=value.lower() in selected_lower)
                self._value_vars[value] = var
                ctk.CTkCheckBox(
                    scroll, text=value, variable=var, font=ctk.CTkFont(size=13)
                ).pack(fill="x", pady=3)

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(
            btn_frame, text="Clear All", width=90,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text, command=self._clear_all
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Cancel", width=80,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            text_color=btn_text, command=self._on_cancel
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_frame, text="Apply", width=80,
            fg_color=theme.get_current_color('accent_primary'), hover_color=theme.get_current_color('accent_hover'),
            text_color=btn_text, command=self._on_apply
        ).pack(side="right")

    def _on_mode_changed(self, value: str):
        self._mode_desc_label.configure(text=self._mode_descriptions.get(value, ""))

    def _clear_all(self):
        for var in self._value_vars.values():
            var.set(False)

    def _on_apply(self):
        self.result = [value for value, var in self._value_vars.items() if var.get()]
        self.result_mode = self._mode_enum(self._mode_var.get())
        self.destroy()

    def _on_cancel(self):
        self.destroy()


class TagFilterDialog(_BaseMultiSelectDialog):
    """Dialog for selecting multiple string values (tags, materials, ...) to
    filter by, with a HAS_ALL / HAS_ANY / HAS_NONE match mode."""

    _MODE_VALUES = ["has_all", "has_any", "has_none"]
    _MODE_TEMPLATES = {
        "has_all": "Must have ALL selected {noun}",
        "has_any": "Must have at least ONE selected {noun}",
        "has_none": "Must NOT have any selected {noun}",
    }

    def __init__(self, parent, available_tags: List[str], selected_tags: List[str],
                 current_mode: TagFilterMode = TagFilterMode.HAS_ALL, *,
                 window_title: str = "Select Tags", prompt: str = "Select tags to filter by:",
                 noun: str = "tags", empty_message: str = "No tags found in this collection."):
        descriptions = {k: v.format(noun=noun) for k, v in self._MODE_TEMPLATES.items()}
        super().__init__(
            parent, window_title=window_title, prompt=prompt,
            available_values=available_tags, selected_values=selected_tags,
            mode_enum=TagFilterMode, current_mode=current_mode,
            mode_values=self._MODE_VALUES, mode_descriptions=descriptions,
            empty_message=empty_message,
        )


class SourceFilterDialog(_BaseMultiSelectDialog):
    """Dialog for selecting multiple sources to filter by, with an
    INCLUDE / EXCLUDE match mode."""

    _MODE_VALUES = ["include", "exclude"]
    _MODE_DESCRIPTIONS = {
        "include": "Show only items from selected sources",
        "exclude": "Hide items from selected sources",
    }

    def __init__(self, parent, available_sources: List[str], selected_sources: List[str],
                 current_mode: SourceFilterMode = SourceFilterMode.INCLUDE, *,
                 empty_message: str = "No sources found in this collection."):
        super().__init__(
            parent, window_title="Select Sources", prompt="Select sources to filter by:",
            available_values=available_sources, selected_values=selected_sources,
            mode_enum=SourceFilterMode, current_mode=current_mode,
            mode_values=self._MODE_VALUES, mode_descriptions=self._MODE_DESCRIPTIONS,
            empty_message=empty_message,
        )
