"""Settings > Pictures: show or hide content pictures, and import, export or remove image packs."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from content_images import KINDS, format_size, get_image_store
from theme import get_theme_manager
from typography import ui_font

HELP = ("Give any spell, monster, item, feat, species, background or class a picture: use \"Add picture\" on its "
        "page, or import an image pack. A pack is a .zip or a folder with a folder per collection (Spells, "
        "Monsters, Magic Items, Equipment, Feats, Species, Backgrounds, Classes) holding pictures named after "
        "the entries, e.g. Monsters/Goblin.png. Pictures are shrunk to at most 1024 pixels and kept in the app's "
        "data folder, so the app itself doesn't grow.")


class ImagePacksPanel(ctk.CTkFrame):
    def __init__(self, parent, settings_manager):
        super().__init__(parent, fg_color="transparent")
        self.theme = get_theme_manager()
        self.settings_manager = settings_manager
        self.store = get_image_store()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="Show pictures on content pages", font=ui_font("subheading")).pack(side="left")
        self.show_var = ctk.BooleanVar(value=getattr(settings_manager.settings, "show_content_images", True))
        ctk.CTkSwitch(row, text="", variable=self.show_var, width=46, command=self._on_toggle).pack(side="right")

        ctk.CTkLabel(self, text=HELP, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     justify="left", anchor="w", wraplength=640).pack(fill="x", pady=(8, 8))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x")
        for text, command in (("Import Pack (.zip)…", self._import_zip), ("Import Folder…", self._import_folder),
                              ("Export My Pictures…", self._export)):
            ctk.CTkButton(buttons, text=text, width=150, command=command,
                          fg_color=self.theme.get_current_color('button_normal'),
                          hover_color=self.theme.get_current_color('button_hover'),
                          text_color=self.theme.get_current_color('text_primary')).pack(side="left", padx=(0, 8))
        self.replace_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="When importing, replace pictures entries already have",
                        variable=self.replace_var).pack(anchor="w", pady=(8, 4))

        self.summary = ctk.CTkLabel(self, text="", font=ui_font("body"), anchor="w", justify="left")
        self.summary.pack(fill="x", pady=(6, 2))
        self.packs_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.packs_frame.pack(fill="x")
        self.store.add_listener(self.refresh)
        self.refresh()

    def destroy(self):
        self.store.remove_listener(self.refresh)
        super().destroy()

    def refresh(self):
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        total = self.store.count()
        per_kind = ", ".join(f"{label} {self.store.count(k)}" for k, label in KINDS.items() if self.store.count(k))
        text = f"{total} picture{'s' if total != 1 else ''} ({format_size(self.store.size_on_disk())})"
        self.summary.configure(text=text + (f": {per_kind}" if per_kind else ""))
        for w in self.packs_frame.winfo_children():
            w.destroy()
        for pack in self.store.packs():
            line = ctk.CTkFrame(self.packs_frame, fg_color="transparent")
            line.pack(fill="x", pady=1)
            label = pack.name + (f" {pack.version}" if pack.version else "") + (f" by {pack.author}" if pack.author
                                                                              else "")
            ctk.CTkLabel(line, text=f"📦 {label}  ({pack.count} pictures)", font=ui_font("body"),
                         anchor="w").pack(side="left")
            ctk.CTkButton(line, text="Remove", width=70, height=24,
                          fg_color=self.theme.get_current_color('button_danger'),
                          hover_color=self.theme.get_current_color('button_danger_hover'),
                          command=lambda p=pack: self._remove(p)).pack(side="right")

    def _on_toggle(self):
        self.settings_manager.update(show_content_images=bool(self.show_var.get()))
        self.store.save()                    # tells the pages to show or hide their pictures

    def _import(self, source: str):
        try:
            report = self.store.import_pack(source, replace=bool(self.replace_var.get()))
        except Exception as e:
            messagebox.showerror("Import pictures", f"That pack couldn't be read.\n\n{e}", parent=self)
            return
        lines = [f"Added {report.added} picture{'s' if report.added != 1 else ''}."]
        if report.replaced:
            lines.append(f"Replaced {report.replaced}.")
        if report.kept:
            lines.append(f"Kept {report.kept} existing picture{'s' if report.kept != 1 else ''} "
                         "(tick \"replace\" to swap them).")
        if report.skipped:
            sample = ", ".join(report.skipped[:5]) + (" ..." if len(report.skipped) > 5 else "")
            lines.append(f"Skipped {len(report.skipped)} file(s) that aren't pictures in a known folder: {sample}")
        messagebox.showinfo("Import pictures", "\n".join(lines), parent=self)

    def _import_zip(self):
        path = filedialog.askopenfilename(parent=self, title="Import image pack",
                                          filetypes=[("Image pack", "*.zip"), ("All files", "*.*")])
        if path:
            self._import(path)

    def _import_folder(self):
        path = filedialog.askdirectory(parent=self, title="Folder of pictures (a folder per collection inside)")
        if path:
            self._import(path)

    def _export(self):
        if not self.store.count():
            messagebox.showinfo("Export pictures", "There are no pictures to export yet.", parent=self)
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export pictures as a pack", defaultextension=".zip",
                                            initialfile="spellbook-pictures.zip", filetypes=[("Image pack", "*.zip")])
        if not path:
            return
        try:
            count = self.store.export_pack(path)
        except OSError as e:
            messagebox.showerror("Export pictures", str(e), parent=self)
            return
        messagebox.showinfo("Export pictures", f"Exported {count} pictures.", parent=self)

    def _remove(self, pack):
        if messagebox.askyesno("Remove pack", f"Remove the {pack.count} pictures that came with '{pack.name}'?",
                               parent=self):
            self.store.remove_pack(pack.id)
