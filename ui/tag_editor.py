"""
Reusable tag-editing widget for D&D Spellbook content editors.

Shared by the equipment and magic item editors (and any future content type
that needs a free-form, chip-style tag list): a "+ Add Tag" button opens a
picker with a text box for a new tag plus a scrollable list of previously-used
/ suggested tags, and selected tags are shown as removable chips.

This mirrors the tag UI in ui/spell_editor.py, minus the "protected tag"
concept (Official/Unofficial) which is specific to spells.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, List

from theme import get_theme_manager


class TagPickerDialog(ctk.CTkToplevel):
    """Dialog for selecting a tag from existing/suggested tags or adding a new one."""

    def __init__(self, parent, available_tags: List[str], selected_tags: List[str]):
        super().__init__(parent)

        self.result = None  # Tag to add
        self.theme = get_theme_manager()

        self.title("Select Tag")
        self.geometry("350x450")
        self.minsize(300, 350)
        self.resizable(True, True)

        self.transient(parent)
        self.grab_set()

        self._create_widgets(available_tags, selected_tags)

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self, available_tags: List[str], selected_tags: List[str]):
        theme = self.theme
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        text_secondary = theme.get_text_secondary()

        ctk.CTkLabel(
            container, text="Add Tag:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(fill="x", pady=(0, 5))

        new_tag_frame = ctk.CTkFrame(container, fg_color="transparent")
        new_tag_frame.pack(fill="x", pady=(0, 10))

        self._new_tag_entry = ctk.CTkEntry(
            new_tag_frame, height=35, placeholder_text="Type to search or add a new tag"
        )
        self._new_tag_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._new_tag_entry.bind("<KeyRelease>", lambda _e: self._render_list())

        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(
            new_tag_frame, text="Add", width=60,
            fg_color=theme.get_current_color('button_success'),
            hover_color=theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_add_new
        ).pack(side="right")

        ctk.CTkFrame(container, height=2, fg_color=theme.get_current_color('border')).pack(fill="x", pady=8)

        ctk.CTkLabel(
            container, text="Existing tags (click to add):",
            font=ctk.CTkFont(size=12), text_color=text_secondary
        ).pack(fill="x", pady=(0, 6))

        selected_lower = {t.lower() for t in selected_tags}
        self._available = sorted(
            {t for t in available_tags if t.lower() not in selected_lower}, key=str.lower)

        self._list_scroll = ctk.CTkScrollableFrame(container)
        self._list_scroll.pack(fill="both", expand=True, pady=(0, 15))
        self._render_list()

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(btn_frame, text="Cancel", width=80,
                      fg_color=theme.get_current_color('button_normal'),
                      hover_color=theme.get_current_color('button_hover'),
                      text_color=btn_text,
                      command=self._on_cancel).pack(side="right")

    def _render_list(self):
        """(Re)build the existing-tag list, filtered by what's typed so far."""
        theme = self.theme
        for w in self._list_scroll.winfo_children():
            w.destroy()

        q = self._new_tag_entry.get().strip().lower()
        matches = [t for t in self._available if q in t.lower()] if q else self._available
        # Prefix matches first when searching.
        if q:
            matches.sort(key=lambda t: (not t.lower().startswith(q), t.lower()))

        if not matches:
            ctk.CTkLabel(
                self._list_scroll,
                text="No match — click Add to create this tag." if q else "No additional tags available.",
                font=ctk.CTkFont(size=12), text_color=theme.get_text_secondary()
            ).pack(pady=20)
            return

        for tag in matches:
            ctk.CTkButton(
                self._list_scroll, text=tag, anchor="w",
                fg_color="transparent",
                hover_color=theme.get_current_color('accent_primary'),
                text_color=theme.get_current_color('text_primary'),
                text_color_disabled="black",
                font=ctk.CTkFont(size=13),
                command=lambda t=tag: self._on_select_existing(t)
            ).pack(fill="x", pady=2)

    def _on_add_new(self):
        tag = self._new_tag_entry.get().strip()
        if not tag:
            messagebox.showwarning("Warning", "Please enter a tag name.", parent=self)
            return
        self.result = tag
        self.destroy()

    def _on_select_existing(self, tag: str):
        self.result = tag
        self.destroy()

    def _on_cancel(self):
        self.destroy()


class TagEditor(ctk.CTkFrame):
    """A labelled '+ Add Tag' button plus a wrapping row of removable tag chips."""

    def __init__(self, parent, get_available_tags: Callable[[], List[str]], label: str = "Tags"):
        theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.theme = theme
        self._get_available_tags = get_available_tags
        self._tags: List[str] = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(header, text=label, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(
            header, text="+ Add Tag", width=90,
            fg_color=theme.get_current_color('button_success'),
            hover_color=theme.get_current_color('button_success_hover'),
            text_color=btn_text,
            command=self._on_add_tag
        ).pack(side="right")

        self._display_frame = ctk.CTkFrame(self, fg_color=theme.get_current_color('bg_secondary'),
                                           corner_radius=8)
        self._display_frame.pack(fill="x")

        self._content_frame = ctk.CTkFrame(self._display_frame, fg_color="transparent")
        self._content_frame.pack(fill="x", padx=10, pady=10)

        self._no_tags_label = None
        self._refresh_display()

    def get_tags(self) -> List[str]:
        return self._tags.copy()

    def set_tags(self, tags: List[str]):
        self._tags = list(tags)
        self._refresh_display()

    def _on_add_tag(self):
        available = self._get_available_tags() if self._get_available_tags else []
        dialog = TagPickerDialog(self.winfo_toplevel(), available, self._tags)
        self.wait_window(dialog)
        if dialog.result and dialog.result not in self._tags:
            self._tags.append(dialog.result)
            self._refresh_display()

    def _remove_tag(self, tag: str):
        if tag in self._tags:
            self._tags.remove(tag)
            self._refresh_display()

    def _refresh_display(self):
        for widget in self._content_frame.winfo_children():
            widget.destroy()

        theme = self.theme

        if not self._tags:
            ctk.CTkLabel(
                self._content_frame,
                text="No tags added. Click '+ Add Tag' to add tags.",
                font=ctk.CTkFont(size=12), text_color=theme.get_text_secondary()
            ).pack(anchor="w")
            return

        current_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
        current_row.pack(fill="x", anchor="w")

        for tag in sorted(self._tags, key=str.lower):
            tag_frame = ctk.CTkFrame(
                current_row, fg_color=theme.get_current_color('accent_primary'), corner_radius=12
            )
            tag_frame.pack(side="left", padx=(0, 5), pady=2)

            ctk.CTkLabel(
                tag_frame, text=tag, font=ctk.CTkFont(size=12),
                text_color=theme.get_current_color('text_primary')
            ).pack(side="left", padx=(10, 5), pady=4)

            ctk.CTkButton(
                tag_frame, text="×", width=20, height=20,
                fg_color="transparent",
                hover_color=theme.get_current_color('button_danger'),
                text_color=theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=14, weight="bold"),
                command=lambda t=tag: self._remove_tag(t)
            ).pack(side="left", padx=(0, 5), pady=2)

            tag_frame.update_idletasks()
            current_row.update_idletasks()
            if current_row.winfo_reqwidth() > 450:
                tag_frame.pack_forget()
                current_row = ctk.CTkFrame(self._content_frame, fg_color="transparent")
                current_row.pack(fill="x", anchor="w")
                tag_frame = ctk.CTkFrame(
                    current_row, fg_color=theme.get_current_color('accent_primary'), corner_radius=12
                )
                tag_frame.pack(side="left", padx=(0, 5), pady=2)
                ctk.CTkLabel(
                    tag_frame, text=tag, font=ctk.CTkFont(size=12),
                    text_color=theme.get_current_color('text_primary')
                ).pack(side="left", padx=(10, 5), pady=4)
                ctk.CTkButton(
                    tag_frame, text="×", width=20, height=20,
                    fg_color="transparent",
                    hover_color=theme.get_current_color('button_danger'),
                    text_color=theme.get_current_color('text_primary'),
                    font=ctk.CTkFont(size=14, weight="bold"),
                    command=lambda t=tag: self._remove_tag(t)
                ).pack(side="left", padx=(0, 5), pady=2)
