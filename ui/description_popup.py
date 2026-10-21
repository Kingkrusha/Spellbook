"""
The read-only popup that shows one thing's description: a class feature, a feat, a lineage trait.

They were three copies of the same window - a header with the name and a grey note after it, a close button, a
scrolling body, the rich-text description (or "No description available."), and an OK button. A subclass says what
is different: the strings in the header, the window size, and anything to show above or below the description.
"""

import customtkinter as ctk

from theme import get_theme_manager
from typography import ui_font
from ui.window_utils import center_on_parent


class DescriptionPopup(ctk.CTkToplevel):
    GEOMETRY = "550x450"
    MINSIZE = (450, 350)
    # The marker for bold/italic in the description. Class features and feats still use the older single
    # asterisk; None keeps the renderer's default.
    BOLD_PATTERN = r'\*([^*]+)\*'

    def __init__(self, parent, name: str, note: str, description: str):
        """``name`` is the title, ``note`` the grey text after it (e.g. "(Feat)")."""
        super().__init__(parent)

        from ui.rich_text_utils import RichTextRenderer

        self.theme = get_theme_manager()
        self._renderer = RichTextRenderer(self.theme)
        self._name, self._note, self._description = name, note, description

        self.title(f"{name}")
        self.geometry(self.GEOMETRY)
        self.resizable(True, True)
        self.minsize(*self.MINSIZE)

        # Make modal
        self.transient(parent)
        self.grab_set()

        self._create_widgets()

        # Center on parent
        center_on_parent(self, parent)

    # ---- what a subclass can add

    def _add_above_description(self, scroll_frame):
        """Anything to show before the description (a prerequisite warning, say)."""

    def _add_below_description(self, scroll_frame):
        """Anything to show after the description (tables, say)."""

    # ---- the window

    def _render_formatted_text(self, parent, text: str):
        """Render text with rich formatting using global utilities."""
        options = {} if self.BOLD_PATTERN is None else {"bold_pattern": self.BOLD_PATTERN}
        self._renderer.render_formatted_text(
            parent, text,
            on_spell_click=lambda s: self._renderer.show_spell_popup(self, s),
            **options
        )

    def _create_widgets(self):
        container = ctk.CTkFrame(self, fg_color=self.theme.get_current_color('bg_primary'))
        container.pack(fill="both", expand=True)

        # Header
        header = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'),
                              corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(
            header, text=self._name,
            font=ui_font("heading", bold=True)
        ).pack(side="left", padx=15, pady=10)

        ctk.CTkLabel(
            header, text=self._note,
            font=ui_font("body"),
            text_color=self.theme.get_current_color('text_secondary')
        ).pack(side="left", padx=5, pady=10)

        # Close button
        ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('button_hover'),
            command=self.destroy
        ).pack(side="right", padx=5, pady=5)

        # Scrollable content
        scroll_frame = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True, padx=15, pady=15)

        self._add_above_description(scroll_frame)

        # Description with formatted text
        desc_frame = ctk.CTkFrame(scroll_frame, fg_color=self.theme.get_current_color('bg_secondary'),
                                  corner_radius=8)
        desc_frame.pack(fill="x")

        inner_frame = ctk.CTkFrame(desc_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=10, pady=10)

        if self._description:
            self._render_formatted_text(inner_frame, self._description)
        else:
            ctk.CTkLabel(
                inner_frame, text="No description available.",
                font=ui_font("body"),
                text_color=self.theme.get_current_color('text_secondary')
            ).pack(anchor="w")

        self._add_below_description(scroll_frame)

        # OK button at bottom
        ctk.CTkButton(
            container, text="OK", width=100,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_hover'),
            command=self.destroy
        ).pack(pady=15)
