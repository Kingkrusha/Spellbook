"""
Spell List Panel for D&D Spellbook (CustomTkinter version).

A scrollable, selectable list of spells. All the rendering and scrolling is the shared
virtualized list in ``ui/virtual_list.py`` (only the visible rows exist as widgets, so it stays
fast and correct with any number of spells, including a large imported collection); this class
just says how a spell's row looks and keeps the spell-specific API.

The rows use ``corner_radius=0`` and a solid fill: CustomTkinter's rounded + transparent draw
path is the expensive one.
"""

from typing import List, Callable, Optional

from spell import Spell
from content_versions import display_name
from legacy_content import legacy_pair_key
from ui.virtual_list import VirtualListPanel


class SpellListPanel(VirtualListPanel):
    """A virtualized scrollable list panel for displaying and selecting spells."""

    TITLE = "Spells"
    NOUN = "spell"
    ROW_HEIGHT = 38
    ROW_GAP = 4              # stride 42, as before
    ROW_RADIUS = 0
    # One row stands for all the versions of a spell (2024, 2014)
    KEY = staticmethod(legacy_pair_key)

    def __init__(self, parent, on_select: Callable[[Optional[Spell]], None],
                 on_right_click: Optional[Callable[[Spell, int, int], None]] = None):
        super().__init__(parent, on_select, on_right_click)

    # ------------------------------------------------------------------ look

    def list_color(self):
        return self.theme.get_current_color('spell_row')

    def row_color(self, selected: bool):
        if selected:
            return self.theme.get_current_color('accent_primary')
        return self.theme.get_current_color('spell_row')

    def row_text(self, spell: Spell) -> str:
        indicators = []
        if spell.ritual:
            indicators.append("R")
        if spell.concentration:
            indicators.append("C")
        suffix = f"  ({', '.join(indicators)})" if indicators else ""
        # display_name adds a trailing * for modified official spells. One row stands for all the
        # versions of a spell (2024, 2014), so no "(Legacy)" tag: the detail panel switches them.
        return f"{display_name(spell.display_name)}{suffix}"

    # ------------------------------------------------------------ public API

    def set_spells(self, spells: List[Spell], reset_scroll: bool = True):
        """Replace the displayed spells, keeping the selection (by name, any version)."""
        self.set_items(spells, reset_scroll)

    def select_spell(self, name: str, version: Optional[Spell] = None) -> bool:
        """Select a spell by name, scrolling it into view. Returns True if found.

        "Fireball (Legacy)" selects the Fireball row; ``version`` is the exact version to show."""
        return self.select_by_name(name, version)

    def get_selected_spell(self) -> Optional[Spell]:
        return self.get_selected()

    def clear_selection(self):
        """Clear the selection and tell the owner nothing is selected."""
        super().clear_selection()
        self.on_select(None)
