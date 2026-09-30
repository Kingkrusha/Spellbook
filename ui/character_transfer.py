"""
Character import / export (JSON files holding character sheets + spell lists).

Used by the Characters page. Both directions work on the app's shared
CharacterManager, so the character list on screen is current straight away.
"""

import customtkinter as ctk
from typography import ui_font
import json
from tkinter import filedialog, messagebox

from theme import get_theme_manager


def import_characters(parent, character_manager, spell_manager=None) -> bool:
    """Ask for a character export file and import it.

    Returns True if at least one sheet or spell list was imported, so the
    caller knows to refresh its list.
    """
    file_path = filedialog.askopenfilename(
        title="Import Character Sheets",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        parent=parent
    )

    if not file_path:
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if "character_sheets" not in data and "sheets" not in data:
            messagebox.showerror(
                "Invalid File",
                "This file does not contain character sheet data.",
                parent=parent
            )
            return False

        # Get sheets data (support both formats)
        sheets_data = data.get("character_sheets", data.get("sheets", {}))

        if not sheets_data:
            messagebox.showinfo("No Data", "No character sheets found in file.", parent=parent)
            return False

        # Import character sheets with missing content validation
        from ui.character_sheet_view import get_sheet_manager

        sheet_manager = get_sheet_manager()

        imported = 0
        warnings = []

        spell_lists_data = data.get("character_spell_lists", [])
        names_with_list_in_file = {c.get("name") for c in spell_lists_data if isinstance(c, dict)}

        # Importing replaces a character that already has the same name - say so first
        already_here = sorted(
            {n for n in sheets_data if sheet_manager.get_sheet(n) is not None}
            | {n for n in names_with_list_in_file if n and character_manager.get_character(n) is not None}
        )
        if already_here:
            shown = ", ".join(already_here[:8]) + (f" and {len(already_here) - 8} more" if len(already_here) > 8 else "")
            if not messagebox.askyesno(
                "Replace existing characters?",
                f"{len(already_here)} character(s) in this file already exist and will be replaced:\n\n"
                f"{shown}\n\nContinue?",
                parent=parent
            ):
                return False

        # Object links in a sheet ([[spell:Fireball]], ...) only open if that content is installed
        import content_io
        try:
            from object_links import get_link_targets
            known_links = {(t.category, t.name.lower()) for t in get_link_targets(enabled_only=False)}
        except Exception:
            known_links = None

        for name, sheet_data in sheets_data.items():
            try:
                from character_sheet import CharacterSheet
                sheet = CharacterSheet.from_dict(sheet_data)
                import portraits
                if isinstance(sheet_data, dict) and sheet_data.get("portrait_data"):
                    sheet.portrait = portraits.decode_portrait(sheet_data["portrait_data"], name)
                elif sheet.portrait and not portraits.portrait_path(sheet.portrait):
                    sheet.portrait = ""          # the file did not come along

                # Check if character spell list exists (here already, or coming from this same file)
                char_exists = (character_manager.get_character(name) is not None
                               or name in names_with_list_in_file)
                if not char_exists:
                    warnings.append(f"'{name}': No matching character spell list found")

                if known_links is not None:
                    missing = content_io.dangling_links(sheet_data, known_links)
                    if missing:
                        warnings.append(f"'{name}': links to content that isn't installed: "
                                        f"{content_io.format_dangling(missing)}")

                # Import the sheet
                sheet_manager.update_sheet(name, sheet)
                imported += 1
            except Exception as e:
                warnings.append(f"'{name}': Import error - {e}")

        # Import character spell lists if present
        spell_list_imported = 0

        for char_data in spell_lists_data:
            try:
                from character import CharacterSpellList
                char = CharacterSpellList.from_dict(char_data)

                # Validate class references
                from character_class import get_class_manager
                class_manager = get_class_manager()

                for cl in char.classes:
                    class_name = cl.get_class_name() if hasattr(cl, 'get_class_name') else (cl.character_class.value if hasattr(cl.character_class, 'value') else str(cl.character_class))
                    if not class_manager.get_class(class_name):
                        warnings.append(f"'{char.name}': Class '{class_name}' not found in system")

                # Validate spell references
                if spell_manager:
                    for spell_name in char.known_spells + char.prepared_spells:
                        if not spell_manager._db.get_spell_by_name(spell_name):
                            warnings.append(f"'{char.name}': Spell '{spell_name}' not found")

                # Add or update character
                if character_manager.get_character(char.name):
                    character_manager.update_character(char.name, char)
                else:
                    character_manager.add_character(char)
                spell_list_imported += 1
            except Exception as e:
                warnings.append(f"Character spell list error: {e}")

        # Show results
        msg = f"Successfully imported {imported} character sheet(s)"
        if spell_list_imported > 0:
            msg += f" and {spell_list_imported} character spell list(s)"
        msg += "."

        if warnings:
            msg += f"\n\nWarnings ({len(warnings)}):\n"
            msg += "\n".join(warnings[:10])  # Show first 10 warnings
            if len(warnings) > 10:
                msg += f"\n... and {len(warnings) - 10} more"
            messagebox.showwarning("Import Complete with Warnings", msg, parent=parent)
        else:
            messagebox.showinfo("Import Complete", msg, parent=parent)

        return imported > 0 or spell_list_imported > 0

    except json.JSONDecodeError as e:
        messagebox.showerror("Invalid JSON", f"Failed to parse file:\n{e}", parent=parent)
    except Exception as e:
        messagebox.showerror("Import Error", f"Failed to import:\n{e}", parent=parent)
    return False


class CharacterSheetExportDialog(ctk.CTkToplevel):
    """Dialog for exporting character sheets with selection."""

    def __init__(self, parent, character_manager, preselected=None):
        """``preselected``: names to tick initially (default: everyone)."""
        super().__init__(parent)

        self.theme = get_theme_manager()
        self.character_manager = character_manager
        self._preselected = None if preselected is None else set(preselected)

        self.title("Export Character Sheets")
        self.geometry("500x550")
        self.resizable(False, False)

        # Center on parent
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 500) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 550) // 2
        self.geometry(f"+{x}+{y}")

        self._selected_chars = {}  # character_name -> BooleanVar
        self._create_widgets()

    def _create_widgets(self):
        """Create export dialog UI."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            container, text="Export Character Sheets",
            font=ui_font("heading", 20, bold=True)
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(
            container,
            text="Select characters to export. Both character sheet and spell list data will be included.",
            font=ui_font("body"),
            text_color=self.theme.get_text_secondary(),
            wraplength=460
        ).pack(anchor="w", pady=(0, 15))

        # Select All / Deselect All buttons
        select_frame = ctk.CTkFrame(container, fg_color="transparent")
        select_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            select_frame, text="Select All", width=100, height=30,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._select_all
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            select_frame, text="Deselect All", width=100, height=30,
            fg_color=self.theme.get_current_color('button_normal'),
            hover_color=self.theme.get_current_color('button_hover'),
            command=self._deselect_all
        ).pack(side="left")

        # Character selection list
        list_frame = ctk.CTkFrame(container, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
        list_frame.pack(fill="both", expand=True, pady=(0, 15))

        # Scrollable area
        self.scroll_frame = ctk.CTkScrollableFrame(
            list_frame, fg_color="transparent",
            height=250
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

        from ui.character_sheet_view import get_sheet_manager
        sheet_manager = get_sheet_manager()

        characters = self.character_manager.characters

        if not characters:
            ctk.CTkLabel(
                self.scroll_frame, text="No characters found.",
                text_color=self.theme.get_text_secondary()
            ).pack(pady=20)
        else:
            for char in characters:
                initial = self._preselected is None or char.name in self._preselected
                var = ctk.BooleanVar(value=initial)
                self._selected_chars[char.name] = var

                # Check if sheet exists
                sheet_exists = sheet_manager.get_sheet(char.name) is not None

                char_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
                char_frame.pack(fill="x", pady=2)

                cb = ctk.CTkCheckBox(
                    char_frame, text=char.name,
                    variable=var,
                    command=self._update_count
                )
                cb.pack(side="left", padx=5)

                # Class info
                if char.classes:
                    class_info = ", ".join([f"{cl.get_class_name()} {cl.level}" for cl in char.classes])
                    ctk.CTkLabel(
                        char_frame, text=f"({class_info})",
                        text_color=self.theme.get_text_secondary(),
                        font=ui_font("small")
                    ).pack(side="left", padx=5)

                # Sheet status
                status_text = "✓ Sheet" if sheet_exists else "○ No sheet"
                status_color = self.theme.get_current_color('success') if sheet_exists else self.theme.get_text_secondary()
                ctk.CTkLabel(
                    char_frame, text=status_text,
                    text_color=status_color,
                    font=ui_font("small", 10)
                ).pack(side="right", padx=10)

        # Count label
        self.count_label = ctk.CTkLabel(
            container, text="",
            font=ui_font("body")
        )
        self.count_label.pack(anchor="w", pady=(0, 15))
        self._update_count()

        # Buttons
        btn_frame = ctk.CTkFrame(container, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, text="📤 Export Selected",
            width=150, height=40,
            fg_color=self.theme.get_current_color('accent_primary'),
            hover_color=self.theme.get_current_color('accent_secondary'),
            command=self._export
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Cancel",
            width=100, height=40,
            fg_color="transparent",
            hover_color=self.theme.get_current_color('bg_tertiary'),
            command=self.destroy
        ).pack(side="right")

    def _select_all(self):
        """Select all characters."""
        for var in self._selected_chars.values():
            var.set(True)
        self._update_count()

    def _deselect_all(self):
        """Deselect all characters."""
        for var in self._selected_chars.values():
            var.set(False)
        self._update_count()

    def _update_count(self):
        """Update the selection count label."""
        selected = sum(1 for var in self._selected_chars.values() if var.get())
        total = len(self._selected_chars)
        self.count_label.configure(text=f"Selected: {selected} of {total} character(s)")

    def _export(self):
        """Export selected characters."""
        selected_names = [name for name, var in self._selected_chars.items() if var.get()]

        if not selected_names:
            messagebox.showwarning("No Selection", "Please select at least one character to export.", parent=self)
            return

        file_path = filedialog.asksaveasfilename(
            title="Export Character Sheets",
            defaultextension=".json",
            initialfile="character_sheets_export.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=self
        )

        if not file_path:
            return

        try:
            from atomic_io import atomic_write_json
            from ui.character_sheet_view import get_sheet_manager

            sheet_manager = get_sheet_manager()

            export_data = {
                "character_sheets": {},
                "character_spell_lists": []
            }

            sheets_exported = 0
            spell_lists_exported = 0

            for name in selected_names:
                # Export character spell list
                char = self.character_manager.get_character(name)
                if char:
                    export_data["character_spell_lists"].append(char.to_dict())
                    spell_lists_exported += 1

                # Export character sheet
                sheet = sheet_manager.get_sheet(name)
                if sheet:
                    sheet_dict = sheet.to_dict()
                    if sheet.portrait:
                        # embed the portrait so it travels with the sheet
                        import portraits
                        embedded = portraits.encode_portrait(sheet.portrait)
                        if embedded:
                            sheet_dict["portrait_data"] = embedded
                    export_data["character_sheets"][name] = sheet_dict
                    sheets_exported += 1

            atomic_write_json(file_path, export_data, ensure_ascii=False)

            messagebox.showinfo(
                "Export Complete",
                f"Successfully exported:\n• {spell_lists_exported} character spell list(s)\n• {sheets_exported} character sheet(s)",
                parent=self
            )
            self.destroy()

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{e}", parent=self)
