"""
The picture on a content page (a spell's, a monster's ...): a thumbnail beside the entry's details, or a small
"Add picture" button when it has none. Clicking the thumbnail shows the picture full size; right-clicking it
offers Change and Remove. See content_images.py for where the pictures live.
"""

from __future__ import annotations

import tkinter as tk
from collections import OrderedDict
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from content_images import ACCEPTED_TYPES, get_image_store
from theme import get_theme_manager
from typography import ui_font
from ui.platform_compat import bind_right_click

_THUMBS: "OrderedDict[tuple, ctk.CTkImage]" = OrderedDict()
_THUMB_LIMIT = 48


def thumbnail(path: str, side: int) -> Optional[ctk.CTkImage]:
    """A CTkImage of the picture scaled to fit ``side`` (cached by file and size)."""
    import os
    try:
        key = (path, side, os.path.getmtime(path))
    except OSError:
        return None
    image = _THUMBS.get(key)
    if image is not None:
        _THUMBS.move_to_end(key)
        return image
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.load()
            pil = img.copy()
    except Exception as e:
        print(f"Could not open the picture {path}: {e}")
        return None
    pil.thumbnail((side, side), Image.LANCZOS)
    image = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
    _THUMBS[key] = image
    while len(_THUMBS) > _THUMB_LIMIT:
        _THUMBS.popitem(last=False)
    return image


def pictures_enabled() -> bool:
    try:
        from settings import get_settings_manager
        return bool(getattr(get_settings_manager().settings, "show_content_images", True))
    except Exception:
        return True


class ContentImage(ctk.CTkFrame):
    """The picture of one entry. Call ``show(name)`` whenever the page shows another entry."""

    def __init__(self, parent, kind: str, side: int = 140, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.theme = get_theme_manager()
        self.store = get_image_store()
        self.kind = kind
        self.side = side
        self.name: Optional[str] = None
        self.image_label = ctk.CTkLabel(self, text="", cursor="hand2")
        self.image_label.bind("<Button-1>", lambda _e: self.open_viewer())
        bind_right_click(self.image_label, self._on_right_click)
        self.add_button = ctk.CTkButton(
            self, text="🖼 Add picture", width=110, height=24, font=ui_font("small"), fg_color="transparent",
            border_width=1, text_color=self.theme.get_text_secondary(),
            hover_color=self.theme.get_current_color('button_hover'), command=self.choose_file)
        self._blank = None
        self.store.add_listener(self._on_store_changed)

    def destroy(self):
        self.store.remove_listener(self._on_store_changed)
        super().destroy()

    def _on_store_changed(self):
        try:
            if self.winfo_exists():
                self.show(self.name)
        except tk.TclError:
            pass

    @property
    def path(self) -> Optional[str]:
        return self.store.path_for(self.kind, self.name) if self.name else None

    def show(self, name: Optional[str]):
        """Show the picture of the entry called ``name`` (None: nothing is shown)."""
        self.name = name
        self.image_label.pack_forget()
        self.add_button.pack_forget()
        if not name or not pictures_enabled():
            self._clear_image()
            return
        path = self.path
        image = thumbnail(path, self.side) if path else None
        if image is not None:
            self.image_label.configure(image=image)
            self.image_label.pack(anchor="ne")
        else:
            self._clear_image()
            self.add_button.pack(anchor="ne")

    def _clear_image(self):
        # a CTkLabel cannot go back to image=None once it has shown a CTkImage
        if self._blank is None:
            from PIL import Image
            self._blank = ctk.CTkImage(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))
        try:
            self.image_label.configure(image=self._blank)
        except tk.TclError:
            pass

    # ---- actions

    def choose_file(self):
        if not self.name:
            return
        path = filedialog.askopenfilename(parent=self, title=f"Picture for {self.name}", filetypes=ACCEPTED_TYPES)
        if not path:
            return
        try:
            self.store.set_image_file(self.kind, self.name, path)
        except Exception as e:
            messagebox.showerror("Picture", f"That file couldn't be opened as a picture.\n\n{e}", parent=self)

    def remove(self):
        if self.name and messagebox.askyesno("Remove picture", f"Remove the picture of {self.name}?", parent=self):
            self.store.remove_image(self.kind, self.name)

    def _on_right_click(self, event):
        from ui.base_widgets import create_context_menu, show_context_menu
        menu = create_context_menu(self, [("View", self.open_viewer), ("Change picture…", self.choose_file),
                                          ("Remove picture", self.remove)], self.theme)
        show_context_menu(menu, event)

    def open_viewer(self):
        path = self.path
        if path:
            ImageViewer(self.winfo_toplevel(), path, self.name or "")


class ImageViewer(ctk.CTkToplevel):
    """A picture at full size (up to most of the screen)."""

    def __init__(self, parent, path: str, title: str):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        side = int(min(self.winfo_screenwidth(), self.winfo_screenheight()) * 0.8)
        self._image = thumbnail(path, side)
        label = ctk.CTkLabel(self, text="" if self._image else "The picture couldn't be opened.",
                             image=self._image)
        label.pack(padx=10, pady=10)
        label.bind("<Button-1>", lambda _e: self.destroy())
        self.bind("<Escape>", lambda _e: self.destroy())
        from ui.window_utils import center_on_parent
        center_on_parent(self, parent, clamp=True)
        self.after(50, self.focus_set)


def title_row(parent, kind: Optional[str], **label_kwargs):
    """The entry's name with its picture at the right: returns ``(name_label, content_image)`` (the picture is
    None when ``kind`` is None). The row is packed into ``parent`` like the plain name label was."""
    if kind is None:
        label = ctk.CTkLabel(parent, **label_kwargs)
        label.pack(anchor="w", pady=(0, 5))
        return label, None
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=(0, 5))
    picture = ContentImage(row, kind)
    picture.pack(side="right", anchor="n", padx=(10, 0))
    label = ctk.CTkLabel(row, **label_kwargs)
    label.pack(side="left", anchor="nw")
    return label, picture
