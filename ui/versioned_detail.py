"""
The detail pane of the collections whose entries come in versions (feats, lineages, backgrounds: the 2024 text and
its 2014 "Legacy" ones).

The three panels share their frame: a scrolling body that opens on the entry's name and, under it, a Source line
that is a drop-down when the entry has other versions; rich-text descriptions that are cleared and redrawn; and the
hand-off to the list when the reader picks another version. A subclass builds the rest, and names the attribute that
holds the entry on show (``CURRENT_ATTR``) and how to show one (``show_<thing>``, through ``_show_item``).
"""

from typing import Callable, List, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.theme_listener import ThemeListenerMixin
from ui.version_bar import VersionBar


class VersionedDetailBase(ThemeListenerMixin, ctk.CTkFrame):
    CURRENT_ATTR = "_current_item"
    IMAGE_KIND: Optional[str] = None      # the collection's key in content_images (a picture beside the name)

    def __init__(self, parent):
        super().__init__(parent, corner_radius=10)
        self.theme = get_theme_manager()
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        setattr(self, self.CURRENT_ATTR, None)
        self._versions: List = []
        self.on_version_change: Optional[Callable[[object], None]] = None
        self._create_widgets()
        self.theme.add_listener(self._on_theme_changed)

    # ---- hooks

    def _create_widgets(self):
        raise NotImplementedError

    def _update_colors(self):
        raise NotImplementedError

    def _show_item(self, item, versions: Optional[List] = None):
        """Show ``item`` (``versions``: every version offered in the Source drop-down)."""
        raise NotImplementedError

    # ---- what they share

    def _on_theme_changed(self):
        """Handle theme changes."""
        self.configure(fg_color=self.theme.get_current_color('bg_primary'))
        self._update_colors()

    def _add_scroll_and_title(self, placeholder: str, wraplength: int):
        """The scrolling body and the entry's name (``placeholder`` until one is shown)."""
        # Scrollable content
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)

        from ui.content_image import title_row
        self.name_label, self.content_image = title_row(
            self.scroll_frame, self.IMAGE_KIND, text=placeholder,
            font=ui_font("title", bold=True), wraplength=wraplength, justify="left")

    def _show_picture(self, name: Optional[str]):
        if self.content_image is not None:
            self.content_image.show(name)

    def _add_version_bar(self):
        """The Source line: a drop-down when the entry has several versions."""
        self.source_label = VersionBar(
            self.scroll_frame, text="",
            font=ui_font("small"),
            text_color=self.theme.get_text_secondary(),
            on_select=self._version_selected
        )
        self.source_label.pack(anchor="w", pady=(0, 10))

    def _version_selected(self, item):
        """The user picked another version in the Source drop-down."""
        self._show_item(item, self._versions)
        if self.on_version_change:
            self.on_version_change(item)

    def _get_renderer(self):
        """Get or create the rich text renderer."""
        if not hasattr(self, '_renderer'):
            from ui.rich_text_utils import RichTextRenderer
            self._renderer = RichTextRenderer(self.theme)
        return self._renderer

    def _clear_description(self):
        """Clear all description widgets."""
        for widget in self._desc_widgets:
            widget.destroy()
        self._desc_widgets = []
