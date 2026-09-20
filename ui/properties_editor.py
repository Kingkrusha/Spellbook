"""
Reusable "named properties" editor for Spellbook content editors.

A property is a keyword with its own description (e.g. a weapon property like
Finesse or Versatile, or any homebrew keyword). Shared by the equipment and
magic item editors. The value is a list of ``{"name": str, "description": str}``
dicts and may be empty.

The add/edit dialog offers autofill suggestions drawn from every property name
already in use on that content type: type "Fin" and pick "Finesse" to fill in
its stored description; type "Vex" and "Mastery, Vex" is offered.

Mirrors the look/feel of ui/tag_editor.py: a header with a "+ Add Property"
button and a card below listing each property with Edit / remove controls.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional

from theme import get_theme_manager


def _rank_suggestions(query: str, names: List[str]) -> List[str]:
    """Order property names by how well they match `query` (case-insensitive):
    exact, then prefix, then substring. Alphabetical within each group."""
    q = query.strip().lower()
    if not q:
        return sorted(names, key=str.lower)
    exact, prefix, substr = [], [], []
    for n in names:
        low = n.lower()
        if low == q:
            exact.append(n)
        elif low.startswith(q):
            prefix.append(n)
        elif q in low:
            substr.append(n)
    return (sorted(exact, key=str.lower)
            + sorted(prefix, key=str.lower)
            + sorted(substr, key=str.lower))


class PropertyDialog(ctk.CTkToplevel):
    """Prompt for a single property's name and description, with autofill."""

    def __init__(self, parent, name: str = "", description: str = "",
                 suggestions: Optional[Dict[str, str]] = None):
        super().__init__(parent)
        self.result = None  # (name, description) tuple, or None if cancelled
        self.theme = get_theme_manager()
        self._suggestions: Dict[str, str] = dict(suggestions or {})

        self.title("Property" if not name else f"Edit Property: {name}")
        self.geometry("440x460")
        self.minsize(380, 400)
        self.transient(parent)
        self.grab_set()

        self._build(name, description)

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self, name: str, description: str):
        theme = self.theme
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(container, text="Name *",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        self._name_entry = ctk.CTkEntry(container, placeholder_text="e.g. Finesse")
        self._name_entry.pack(fill="x", pady=(0, 4))
        if name:
            self._name_entry.insert(0, name)
        self._name_entry.bind("<KeyRelease>", self._on_name_typed)

        # Autofill suggestions (hidden until the name field matches something).
        self._suggest_box = ctk.CTkScrollableFrame(
            container, height=124, fg_color=theme.get_current_color('bg_secondary'),
            label_text="Existing properties — click to autofill",
            label_font=ctk.CTkFont(size=11),
        )

        ctk.CTkLabel(container, text="Description",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(
            container,
            text="Shown when the reader hovers this keyword.",
            font=ctk.CTkFont(size=11), text_color=theme.get_text_secondary(),
        ).pack(anchor="w", pady=(0, 4))
        self._desc_text = ctk.CTkTextbox(container, height=110)
        self._desc_text.pack(fill="both", expand=True, pady=(0, 12))
        if description:
            self._desc_text.insert("1.0", description)

        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")
        ctk.CTkButton(
            btn_frame, text="Cancel", width=90, fg_color="transparent",
            border_width=1, command=self.destroy,
        ).pack(side="right", padx=(5, 0))
        ctk.CTkButton(
            btn_frame, text="Save", width=90,
            fg_color=theme.get_current_color('accent_primary'),
            command=self._on_save,
        ).pack(side="right")

        self._name_entry.focus_set()
        # Show any prefix matches straight away for a pre-filled name.
        self._on_name_typed()

    # ---- suggestions --------------------------------------------------------

    def _on_name_typed(self, _event=None):
        typed = self._name_entry.get().strip()
        matches = []
        if typed and self._suggestions:
            ordered = _rank_suggestions(typed, list(self._suggestions))
            # Don't bother offering the one thing that exactly equals the field.
            matches = [n for n in ordered if n.lower() != typed.lower()][:8]

        for w in self._suggest_box.winfo_children():
            w.destroy()

        if not matches:
            self._suggest_box.pack_forget()
            return

        theme = self.theme
        for nm in matches:
            desc = self._suggestions.get(nm, "")
            row = ctk.CTkButton(
                self._suggest_box, anchor="w",
                text=nm if not desc else f"{nm}  —  {desc[:60]}{'…' if len(desc) > 60 else ''}",
                fg_color="transparent",
                hover_color=theme.get_current_color('accent_primary'),
                text_color=theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=12),
                command=lambda n=nm: self._apply_suggestion(n),
            )
            row.pack(fill="x", pady=1)

        # Sits directly under the name field.
        self._suggest_box.pack(fill="x", after=self._name_entry, pady=(0, 4))

    def _apply_suggestion(self, nm: str):
        self._name_entry.delete(0, "end")
        self._name_entry.insert(0, nm)
        self._desc_text.delete("1.0", "end")
        self._desc_text.insert("1.0", self._suggestions.get(nm, ""))
        self._suggest_box.pack_forget()
        self._desc_text.focus_set()

    def _on_save(self):
        name = self._name_entry.get().strip()
        if not name:
            messagebox.showwarning("Warning", "A property needs a name.", parent=self)
            return
        self.result = (name, self._desc_text.get("1.0", "end-1c").strip())
        self.destroy()


class PropertiesEditor(ctk.CTkFrame):
    """Header button plus a card listing each named property."""

    def __init__(self, parent, label: str = "Properties",
                 get_suggestions: Optional[Callable[[], Dict[str, str]]] = None):
        theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.theme = theme
        self._get_suggestions = get_suggestions
        self._properties: List[dict] = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(header, text=label,
                     font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
        ctk.CTkButton(
            header, text="+ Add Property", width=120,
            fg_color=theme.get_current_color('button_success'),
            hover_color=theme.get_current_color('button_success_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._on_add,
        ).pack(side="right")

        self._display_frame = ctk.CTkFrame(
            self, fg_color=theme.get_current_color('bg_secondary'), corner_radius=8)
        self._display_frame.pack(fill="x")
        self._content_frame = ctk.CTkFrame(self._display_frame, fg_color="transparent")
        self._content_frame.pack(fill="x", padx=10, pady=10)

        self._refresh()

    # ---- public API -------------------------------------------------------

    def get_properties(self) -> List[dict]:
        return [{"name": p["name"], "description": p["description"]} for p in self._properties]

    def set_properties(self, properties):
        self._properties = []
        for entry in properties or []:
            if isinstance(entry, dict):
                name = str(entry.get("name", "")).strip()
                desc = str(entry.get("description", "")).strip()
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                name, desc = str(entry[0]).strip(), str(entry[1]).strip()
            else:
                continue
            if name:
                self._properties.append({"name": name, "description": desc})
        self._refresh()

    # ---- internals ------------------------------------------------------

    def _suggestions(self) -> Dict[str, str]:
        """Existing property names -> description, minus the ones already added."""
        pool: Dict[str, str] = {}
        if self._get_suggestions:
            try:
                pool = dict(self._get_suggestions() or {})
            except Exception:
                pool = {}
        have = {p["name"].lower() for p in self._properties}
        return {n: d for n, d in pool.items() if n.lower() not in have}

    def _on_add(self):
        dialog = PropertyDialog(self.winfo_toplevel(), suggestions=self._suggestions())
        self.wait_window(dialog)
        if dialog.result is None:
            return
        name, desc = dialog.result
        if any(p["name"].lower() == name.lower() for p in self._properties):
            messagebox.showwarning(
                "Duplicate", f"A property named '{name}' is already listed.",
                parent=self.winfo_toplevel())
            return
        self._properties.append({"name": name, "description": desc})
        self._refresh()

    def _on_edit(self, index: int):
        if not (0 <= index < len(self._properties)):
            return
        current = self._properties[index]
        # Offer suggestions for other names (not this row's own current name).
        pool = self._suggestions()
        pool.pop(current["name"], None)
        dialog = PropertyDialog(self.winfo_toplevel(),
                                current["name"], current["description"],
                                suggestions=pool)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        name, desc = dialog.result
        if any(i != index and p["name"].lower() == name.lower()
               for i, p in enumerate(self._properties)):
            messagebox.showwarning(
                "Duplicate", f"A property named '{name}' is already listed.",
                parent=self.winfo_toplevel())
            return
        self._properties[index] = {"name": name, "description": desc}
        self._refresh()

    def _remove(self, index: int):
        if 0 <= index < len(self._properties):
            del self._properties[index]
            self._refresh()

    def _refresh(self):
        for widget in self._content_frame.winfo_children():
            widget.destroy()

        theme = self.theme
        if not self._properties:
            ctk.CTkLabel(
                self._content_frame,
                text="No properties added. Click '+ Add Property' to add keyword descriptions.",
                font=ctk.CTkFont(size=12), text_color=theme.get_text_secondary(),
            ).pack(anchor="w")
            return

        for index, prop in enumerate(self._properties):
            row = ctk.CTkFrame(self._content_frame,
                               fg_color=theme.get_current_color('bg_tertiary'), corner_radius=8)
            row.pack(fill="x", pady=3)

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(6, 2))

            ctk.CTkLabel(
                top, text=prop["name"], font=ctk.CTkFont(size=13, weight="bold"),
                text_color=theme.get_current_color('accent_primary'),
            ).pack(side="left")

            ctk.CTkButton(
                top, text="×", width=24, height=24, fg_color="transparent",
                hover_color=theme.get_current_color('button_danger'),
                text_color=theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=14, weight="bold"),
                command=lambda i=index: self._remove(i),
            ).pack(side="right")
            ctk.CTkButton(
                top, text="Edit", width=48, height=24, fg_color="transparent",
                border_width=1,
                hover_color=theme.get_current_color('button_hover'),
                text_color=theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=11),
                command=lambda i=index: self._on_edit(i),
            ).pack(side="right", padx=(0, 6))

            desc = prop["description"] or "(no description)"
            ctk.CTkLabel(
                row, text=desc, font=ctk.CTkFont(size=11),
                text_color=theme.get_text_secondary(),
                wraplength=430, justify="left", anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 8))
