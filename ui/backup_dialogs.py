"""Settings > Backup: export everything to one file, and import such a file (see backup.py).

* :class:`BackupPanel` - the section on the Settings page: two buttons and a line of help.
* :class:`ExportBackupDialog` - tick what to include (with how much of each there is), then save.
* :class:`ImportBackupDialog` - shows what a backup holds; tick what to bring in and whether things that
  are already here are replaced or kept.
"""

from __future__ import annotations

import os
import time
from tkinter import filedialog, messagebox
from typing import Dict, Optional

import customtkinter as ctk

import backup as B
from theme import get_theme_manager
from typography import ui_font

HELP = ("Make one file with your settings and everything you added or changed: homebrew in the collections, "
        "characters, random tables, calendars, Studio drafts, pictures, tabletop maps, tokens and PDFs. "
        "Import it on another computer (or after reinstalling) to bring it all across.")

# a PDF library bigger than this starts unticked (it would make a very large file); the rest starts ticked
LARGE_PDFS = 500 * 1024 * 1024


def _main_window(widget):
    return widget.winfo_toplevel()


def backup_sources(widget) -> B.Sources:
    """The live stores of the running app (so what an import changes is seen at once)."""
    mw = _main_window(widget)
    from ui.character_sheet_view import get_sheet_manager
    service = getattr(mw, "_studio_service", None)
    return B.Sources(spell_manager=getattr(mw, "spell_manager", None),
                     character_manager=getattr(mw, "character_manager", None),
                     sheet_manager=get_sheet_manager(),
                     studio_store=service.store if service is not None else None)


def _button(parent, text, command, primary=False, width=150, **kw):
    theme = get_theme_manager()
    color = theme.get_current_color("accent_primary" if primary else "button_normal")
    hover = theme.get_current_color("accent_hover" if primary else "button_hover")
    return ctk.CTkButton(parent, text=text, width=width, command=command, fg_color=color, hover_color=hover,
                         text_color=theme.get_current_color("text_primary"), **kw)


class _Progress(ctk.CTkToplevel):
    """A small window with a progress bar, redrawn as the work goes (the work runs on the UI thread, since
    it writes through the app's own managers)."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        theme = get_theme_manager()
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=24, pady=20)
        ctk.CTkLabel(box, text=title, font=ui_font("heading", bold=True)).pack(anchor="w")
        self.status = ctk.CTkLabel(box, text="Starting…", font=ui_font("body"), anchor="w",
                                   text_color=theme.get_text_secondary())
        self.status.pack(fill="x", pady=(8, 6))
        self.bar = ctk.CTkProgressBar(box, width=320, progress_color=theme.get_current_color("accent_primary"))
        self.bar.pack(fill="x")
        self.bar.set(0)
        self._last = 0.0
        try:
            self.update_idletasks()
            x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
            self.grab_set()
        except Exception:
            pass
        self.update()

    def __call__(self, text: str, fraction: float):
        now = time.monotonic()
        if now - self._last < 0.05 and fraction < 1.0:
            return
        self._last = now
        try:
            self.status.configure(text=text)
            self.bar.set(max(0.0, min(1.0, fraction)))
            self.update()
        except Exception:
            pass

    def close(self):
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass


class _ChoiceDialog(ctk.CTkToplevel):
    """The shared frame: a heading, a note, a scrolling list of category checkboxes and two buttons."""

    def __init__(self, parent, title: str, note: str, action: str):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.title(title)
        self.geometry("560x640")
        self.minsize(460, 480)
        self.transient(parent)
        self.vars: Dict[str, ctk.BooleanVar] = {}

        self.box = ctk.CTkFrame(self, fg_color="transparent")
        self.box.pack(fill="both", expand=True, padx=18, pady=16)
        ctk.CTkLabel(self.box, text=title, font=ui_font("heading", 16, bold=True)).pack(anchor="w")
        ctk.CTkLabel(self.box, text=note, font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     wraplength=510, justify="left", anchor="w").pack(fill="x", pady=(4, 8))

        row = ctk.CTkFrame(self.box, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))
        _button(row, "All", lambda: self._set_all(True), width=60, height=24).pack(side="left")
        _button(row, "None", lambda: self._set_all(False), width=60, height=24).pack(side="left", padx=(6, 0))

        # the buttons are packed first, from the bottom, so a small window squeezes the list, not them
        buttons = ctk.CTkFrame(self.box, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", pady=(8, 0))
        self.action_btn = _button(buttons, action, self._go, primary=True, width=140, height=34)
        self.action_btn.pack(side="left")
        _button(buttons, "Cancel", self.destroy, width=90, height=34).pack(side="right")
        self.status = ctk.CTkLabel(self.box, text="", font=ui_font("small"), wraplength=510, justify="left",
                                   text_color=self.theme.get_current_color("text_warning"))
        self.status.pack(side="bottom", anchor="w", pady=(6, 0))
        self.extra = ctk.CTkFrame(self.box, fg_color="transparent", height=1)
        self.extra.pack(side="bottom", fill="x")

        self.list = ctk.CTkScrollableFrame(self.box, height=200,
                                           fg_color=self.theme.get_current_color("bg_secondary"))
        self.list.pack(fill="both", expand=True)
        self._center(parent)

    def _center(self, parent):
        try:
            self.update_idletasks()
            top = parent.winfo_toplevel()
            x = top.winfo_rootx() + (top.winfo_width() - 560) // 2
            y = top.winfo_rooty() + (top.winfo_height() - 640) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def add_row(self, key: str, detail: str, on: bool, enabled: bool = True):
        name, description = B.CATEGORIES[key]
        var = ctk.BooleanVar(value=on and enabled)
        self.vars[key] = var
        row = ctk.CTkFrame(self.list, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(8, 0))
        box = ctk.CTkCheckBox(row, text=name, variable=var, font=ui_font("body", bold=True))
        box.pack(side="left")
        if not enabled:
            box.configure(state="disabled")
        ctk.CTkLabel(row, text=detail, font=ui_font("small"),
                     text_color=self.theme.get_text_secondary()).pack(side="right")
        ctk.CTkLabel(self.list, text=description, font=ui_font("small"), anchor="w", justify="left",
                     wraplength=420, text_color=self.theme.get_text_secondary()).pack(fill="x", padx=(38, 12))

    def chosen(self):
        return [k for k, v in self.vars.items() if v.get()]

    def _set_all(self, value: bool):
        for var in self.vars.values():
            var.set(value)

    def _go(self):
        raise NotImplementedError


class ExportBackupDialog(_ChoiceDialog):
    def __init__(self, parent, sources: Optional[B.Sources] = None):
        super().__init__(parent, "Export a backup",
                         "Tick what to put in the backup. Official content isn't included: every Spellbook "
                         "has it already.", "💾 Export…")
        self.sources = sources or backup_sources(parent)
        self.info = B.summarize(self.sources)
        for key, info in self.info.items():
            empty = not info.count and not info.error
            self.add_row(key, "nothing yet" if empty else info.describe(key),
                         on=not (key == "pdfs" and info.bytes > LARGE_PDFS), enabled=not empty)

    def _go(self):
        keys = self.chosen()
        if not keys:
            self.status.configure(text="Tick at least one thing to include.")
            return
        name = f"Spellbook backup {time.strftime('%Y-%m-%d')}.zip"
        path = filedialog.asksaveasfilename(parent=self, title="Save backup", defaultextension=".zip",
                                            initialfile=name, filetypes=B.FILE_TYPES)
        if not path:
            return
        progress = _Progress(self, "Exporting backup")
        try:
            result = B.export_backup(path, self.sources, keys, progress)
        except Exception as e:
            progress.close()
            messagebox.showerror("Export failed", f"The backup could not be written:\n{e}", parent=self)
            return
        progress.close()
        lines = [f"{B.label(k)}: {self.info[k].describe(k) if k in self.info else n}"
                 for k, n in result.counts.items()]
        text = f"Saved {os.path.basename(path)} ({B.format_size(result.bytes)}).\n\n" + "\n".join(lines)
        if result.warnings:
            text += "\n\nNotes:\n" + "\n".join(result.warnings[:8])
        (messagebox.showwarning if result.warnings else messagebox.showinfo)("Backup saved", text, parent=self)
        self.destroy()


class ImportBackupDialog(_ChoiceDialog):
    REPLACE, KEEP = "Replace them with the backup's", "Keep mine"

    def __init__(self, parent, path: str, manifest: B.Manifest, sources: Optional[B.Sources] = None):
        made = manifest.created[:10] if manifest.created else "an unknown date"
        version = f" by Spellbook {manifest.app_version}" if manifest.app_version else ""
        super().__init__(parent, "Import a backup",
                         f"{os.path.basename(path)}, made {made}{version}. Tick what to bring in. It is added "
                         f"to what you have; nothing is deleted.", "📥 Import")
        self.path = path
        self.sources = sources or backup_sources(parent)
        for key, info in manifest.categories.items():
            self.add_row(key, info.describe(key), on=True)
        if not manifest.categories:
            ctk.CTkLabel(self.list, text="This backup is empty.", font=ui_font("body")).pack(pady=20)
            self.action_btn.configure(state="disabled")

        ctk.CTkLabel(self.extra, text="When something with the same name is already here:",
                     font=ui_font("body", bold=True)).pack(anchor="w", pady=(10, 2))
        self.mode = ctk.StringVar(value=self.REPLACE)
        for value in (self.REPLACE, self.KEEP):
            ctk.CTkRadioButton(self.extra, text=value, variable=self.mode, value=value).pack(anchor="w", padx=10,
                                                                                               pady=1)
        ctk.CTkLabel(self.extra, text="Chosen settings always replace yours. Official content is never changed.",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary()).pack(anchor="w", pady=(4, 0))

    def _go(self):
        keys = self.chosen()
        if not keys:
            self.status.configure(text="Tick at least one thing to import.")
            return
        parent = self.master
        progress = _Progress(self, "Importing backup")
        try:
            result = B.import_backup(self.path, self.sources, keys, replace=self.mode.get() == self.REPLACE,
                                     progress=progress)
        except Exception as e:
            progress.close()
            messagebox.showerror("Import failed", f"The backup could not be imported:\n{e}", parent=self)
            return
        progress("Refreshing…", 1.0)
        refresh_after_import(parent, result.changed, self.sources)
        progress.close()
        text = result.summary() or "Nothing was imported."
        if result.restart_needed:
            text += ("\n\nRestart Spellbook to see the imported appearance, fonts and keyboard shortcuts "
                     "everywhere.")
        if result.warnings:
            text += "\n\nNotes:\n" + "\n".join(result.warnings[:10])
        self.destroy()
        (messagebox.showwarning if result.warnings else messagebox.showinfo)("Backup imported", text,
                                                                             parent=parent)


def refresh_after_import(widget, changed, sources: B.Sources):
    """Show what an import brought in without a restart: reload the content managers and redraw the open
    pages that show it."""
    if not changed:
        return
    mw = _main_window(widget)
    if "content" in changed:
        _reload_content_managers(sources.spell_manager)
        for name in ("refresh_class_filter", "refresh_all_collection_views"):
            fn = getattr(mw, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception as e:
                    print(f"Backup import: {name} failed: {e}")
    if "random_tables" in changed:
        try:
            sources.random_tables._invalidate_cache()
        except Exception:
            pass
    fn = getattr(mw, "refresh_pages_after_import", None)
    if callable(fn):
        try:
            fn(changed)
        except Exception as e:
            print(f"Backup import: refreshing pages failed: {e}")


def _reload_content_managers(spell_manager):
    from background import get_background_manager
    from character_class import get_class_manager
    from equipment import get_equipment_manager
    from feat import get_feat_manager
    from lineage import get_lineage_manager
    from magic_item import get_magic_item_manager
    from monster import get_monster_manager
    from rules import get_rules_manager
    steps = [get_class_manager().load, get_feat_manager().load, get_lineage_manager().load_lineages,
             get_background_manager().load_backgrounds, get_equipment_manager().load,
             get_magic_item_manager().load, get_monster_manager().load, get_rules_manager().load]
    if spell_manager is not None:
        steps.append(spell_manager.load_spells)
    for step in steps:
        try:
            step()
        except Exception as e:
            print(f"Backup import: reloading content failed: {e}")


class BackupPanel(ctk.CTkFrame):
    """The Backup section of the Settings page."""

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        theme = get_theme_manager()
        ctk.CTkLabel(self, text=HELP, font=ui_font("small"), text_color=theme.get_text_secondary(),
                     justify="left", anchor="w", wraplength=640).pack(fill="x", pady=(0, 10))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        _button(row, "Export Backup…", self._export, width=150).pack(side="left", padx=(0, 8))
        _button(row, "Import Backup…", self._import, width=150).pack(side="left")

    def _export(self):
        try:
            dialog = ExportBackupDialog(self.winfo_toplevel())
        except Exception as e:
            messagebox.showerror("Export", f"Could not open the export window:\n{e}", parent=self)
            return
        dialog.grab_set()

    def _import(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a Spellbook backup", filetypes=B.FILE_TYPES)
        if not path:
            return
        try:
            manifest = B.read_manifest(path)
        except B.BackupError as e:
            messagebox.showerror("Not a backup", str(e), parent=self)
            return
        dialog = ImportBackupDialog(self.winfo_toplevel(), path, manifest)
        dialog.grab_set()
