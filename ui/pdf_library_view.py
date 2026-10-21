"""
PDF Library page (Game Tools): search every PDF in the library folders and read the page a match is on.

The left side searches page text (every word must be on the page) and lists the matching pages, best first,
with the bookmark each falls under and a piece of the text. The right side shows a page, drawn by PDFium, with
the searched words outlined. "Import Text" sends the page's text (trimmed by the user) to a collection's
"add from text" importer, which fills in an entry for review.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional

import customtkinter as ctk

from pdf_library import Document, Hit, available, default_folder, get_pdf_library, library_folders
from theme import get_theme_manager
from typography import ui_font
from ui.virtual_list import VirtualListPanel

ALL_DOCS = "All documents"
ZOOMS = [0.5, 0.67, 0.8, 1.0, 1.25, 1.5, 2.0, 3.0]
IMPORT_KINDS = {"Spell": "spells", "Feat": "feats", "Species": "lineages", "Equipment": "equipment",
                "Magic Item": "magic_items"}


def _color(theme, role: str) -> str:
    value = theme.get_current_color(role)
    return value[1] if isinstance(value, tuple) else str(value)


def open_externally(path: str):
    """Open a file or folder with the system's own app."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("Open", f"Couldn't open {path}:\n{e}")


class ResultList(VirtualListPanel):
    TITLE = "Library"
    NOUN = "result"
    ROW_HEIGHT = 56

    def row_text(self, item) -> str:
        if isinstance(item, Hit):
            where = f"{item.doc.title}  ·  p. {item.page + 1}" + (f"  ·  {item.section}" if item.section else "")
            snippet = item.snippet if len(item.snippet) <= 54 else item.snippet[:53] + "…"
            return f"{where}\n{snippet}"
        return f"📄 {item.title}\n{item.pages} pages"

    def _ensure_pool(self, count: int):
        super()._ensure_pool(count)
        for row in self._pool:                 # two-line rows: both lines start at the left
            label = getattr(row, "_text_label", None)
            if label is not None:
                label.configure(justify="left")


class PageCanvas(tk.Frame):
    """One PDF page, rendered to fit the width (times the zoom), with words outlined."""

    def __init__(self, parent):
        self.theme = get_theme_manager()
        super().__init__(parent, highlightthickness=0, borderwidth=0, bg=_color(self.theme, "bg_tertiary"))
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, bg=_color(self.theme, "bg_tertiary"),
                                takefocus=1)
        self.vbar = ctk.CTkScrollbar(self, command=self.canvas.yview)
        self.hbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.vbar.pack(side="right", fill="y")
        self.hbar.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind(seq, self._on_wheel, add="+")
        self.canvas.bind("<Configure>", lambda _e: self._schedule_render(), add="+")
        self._pdf = None
        self._path: Optional[str] = None
        self.page = 0
        self.zoom = 1.0
        self.terms: List[str] = []
        self._photo = None
        self._job = None
        self._last_key = None

    # ---- document

    def open(self, path: Optional[str]):
        if path == self._path:
            return
        self.close()
        self._path = path
        if path:
            import pypdfium2 as pdfium
            self._pdf = pdfium.PdfDocument(path)
        self.page = 0
        self._last_key = None

    def close(self):
        if self._pdf is not None:
            try:
                self._pdf.close()
            except Exception:
                pass
        self._pdf = None
        self._path = None

    def destroy(self):
        self.close()
        super().destroy()

    @property
    def page_count(self) -> int:
        return len(self._pdf) if self._pdf is not None else 0

    def show_page(self, page: int, terms: Optional[List[str]] = None):
        if self._pdf is None:
            self.canvas.delete("all")
            return
        self.page = max(0, min(page, self.page_count - 1))
        if terms is not None:
            self.terms = terms
        self.render()
        self.canvas.yview_moveto(0)

    # ---- drawing

    def _schedule_render(self):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(120, self.render)

    def render(self):
        self._job = None
        if self._pdf is None:
            return
        width = max(200, self.canvas.winfo_width() - 20)
        page = self._pdf[self.page]
        try:
            page_w, page_h = page.get_size()
            scale = width / page_w * self.zoom
            key = (self._path, self.page, round(scale, 3), tuple(self.terms))
            if key == self._last_key:
                return
            self._last_key = key
            from PIL import ImageTk
            image = page.render(scale=scale).to_pil()
            self._photo = ImageTk.PhotoImage(image)
            c = self.canvas
            c.delete("all")
            x0 = max(10, (self.canvas.winfo_width() - image.width) // 2)
            c.create_image(x0, 10, image=self._photo, anchor="nw")
            first_y = None
            if self.terms:
                textpage = page.get_textpage()
                try:
                    for term in self.terms:
                        searcher = textpage.search(term, match_case=False)
                        try:
                            while True:
                                found = searcher.get_next()
                                if not found:
                                    break
                                index, count = found
                                for r in range(textpage.count_rects(index, count)):
                                    left, bottom, right, top = textpage.get_rect(r)
                                    y = 10 + (page_h - top) * scale
                                    c.create_rectangle(x0 + left * scale - 2, y - 2, x0 + right * scale + 2,
                                                       10 + (page_h - bottom) * scale + 2,
                                                       outline=_color(self.theme, "accent_primary"), width=2)
                                    first_y = y if first_y is None else min(first_y, y)
                        finally:
                            searcher.close()
                finally:
                    textpage.close()
            total_h = image.height + 20
            c.configure(scrollregion=(0, 0, max(image.width + 20, self.canvas.winfo_width()), total_h))
            if first_y is not None and total_h > 0:
                self.canvas.yview_moveto(max(0.0, (first_y - 80) / total_h))
        finally:
            page.close()

    def _on_wheel(self, event):
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-3, "units")
        else:
            self.canvas.yview_scroll(3, "units")
        return "break"


class PdfLibraryView(ctk.CTkFrame):
    """The PDF Library page."""

    def __init__(self, parent, state: Optional[dict] = None, on_back=None, on_import_text=None, library=None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.state = state if state is not None else {}
        self.on_back = on_back
        self.on_import_text = on_import_text
        self.library = library or get_pdf_library()
        self._doc: Optional[Document] = None
        self._search_job = None
        self._scan_thread: Optional[threading.Thread] = None
        self._scan_queue: "queue.Queue" = queue.Queue()
        self._stop_scan = False
        self._toc = []
        self._create_widgets()
        if not available():
            self.status.configure(text="PDF support isn't installed (the pypdfium2 package is missing).")
            return
        self._show_documents()
        self.rescan()

    def destroy(self):
        self._stop_scan = True
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except Exception:
                pass
        super().destroy()

    # ------------------------------------------------------------------ layout

    def _button(self, parent, text, command, width=90, kind="normal"):
        colors = {"normal": ("button_normal", "button_hover"), "accent": ("accent_primary", "accent_hover")}[kind]
        return ctk.CTkButton(parent, text=text, width=width, height=32, command=command,
                             fg_color=self.theme.get_current_color(colors[0]),
                             hover_color=self.theme.get_current_color(colors[1]),
                             text_color=self.theme.get_current_color(
                                 'text_primary' if kind == "normal" else 'text_on_accent'),
                             text_color_disabled=self.theme.get_text_secondary())

    def _create_widgets(self):
        th = self.theme
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        if self.on_back:
            self._button(header, "← Game Tools", self.on_back, width=120).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(header, text="PDF Library", font=ui_font("title", 28, bold=True)).pack(side="left")
        self._button(header, "Rescan", self.rescan, width=80).pack(side="right")
        self._button(header, "Folders…", self._on_folders, width=90).pack(side="right", padx=(0, 8))
        self._button(header, "Open Library Folder", lambda: open_externally(default_folder()),
                     width=150).pack(side="right", padx=(0, 8))
        self.status = ctk.CTkLabel(self, text="", font=ui_font("small"), anchor="w",
                                   text_color=th.get_text_secondary())
        self.status.pack(fill="x", padx=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(6, 20))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent", width=360)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_propagate(False)
        left.pack_propagate(False)
        self.search_entry = ctk.CTkEntry(left, height=34, placeholder_text="Search the text of every PDF...")
        if self.state.get("query"):
            self.search_entry.insert(0, self.state["query"])
        self.search_entry.pack(fill="x", pady=(0, 6))
        self.search_entry.bind("<KeyRelease>", self._on_key, add="+")
        self.doc_var = ctk.StringVar(value=ALL_DOCS)
        self.doc_menu = ctk.CTkOptionMenu(left, variable=self.doc_var, values=[ALL_DOCS], height=32,
                                          command=lambda _v: self.search())
        self.doc_menu.pack(fill="x", pady=(0, 6))
        self.results = ResultList(left, on_select=self._on_select)
        self.results.pack(fill="both", expand=True)

        right = ctk.CTkFrame(body, fg_color=th.get_current_color('bg_primary'), corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew")
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(10, 4))
        self.title_label = ctk.CTkLabel(bar, text="Pick a document or search", font=ui_font("heading", bold=True),
                                        anchor="w")
        self.title_label.pack(side="left")
        self.open_btn = self._button(bar, "Open in PDF App", self._open_external, width=130)
        self.open_btn.pack(side="right")
        self.import_btn = self._button(bar, "Import Text…", self._on_import_text, width=110)
        self.import_btn.pack(side="right", padx=(0, 6))

        nav = ctk.CTkFrame(right, fg_color="transparent")
        nav.pack(fill="x", padx=10, pady=(0, 6))
        self.prev_btn = self._button(nav, "◀", lambda: self._go(self.viewer.page - 1), width=34)
        self.prev_btn.pack(side="left")
        self.page_entry = ctk.CTkEntry(nav, width=56, height=32, justify="center")
        self.page_entry.pack(side="left", padx=4)
        self.page_entry.bind("<Return>", lambda _e: self._go_typed())
        self.count_label = ctk.CTkLabel(nav, text="", font=ui_font("body"))
        self.count_label.pack(side="left")
        self.next_btn = self._button(nav, "▶", lambda: self._go(self.viewer.page + 1), width=34)
        self.next_btn.pack(side="left", padx=(4, 12))
        self._button(nav, "−", lambda: self._zoom(-1), width=34).pack(side="left")
        self.zoom_label = ctk.CTkLabel(nav, text="100%", width=50, font=ui_font("small"))
        self.zoom_label.pack(side="left")
        self._button(nav, "+", lambda: self._zoom(1), width=34).pack(side="left")
        self.section_var = ctk.StringVar(value="Sections")
        self.section_menu = ctk.CTkOptionMenu(nav, variable=self.section_var, values=["Sections"], width=240,
                                              height=32, command=self._on_section)
        self.section_menu.pack(side="right")

        self.viewer = PageCanvas(right)
        self.viewer.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        for widget in (self.viewer.canvas,):
            widget.bind("<Prior>", lambda _e: self._go(self.viewer.page - 1))
            widget.bind("<Next>", lambda _e: self._go(self.viewer.page + 1))
            widget.bind("<Button-1>", lambda _e: self.viewer.canvas.focus_set(), add="+")
        self._update_nav()

    # ------------------------------------------------------------------ scanning

    def rescan(self):
        if not available() or (self._scan_thread is not None and self._scan_thread.is_alive()):
            return
        self.status.configure(text="Reading the library…")
        self._stop_scan = False
        folders = library_folders()

        def work():
            try:
                report = self.library.scan(folders, progress=lambda i, n, name: self._scan_queue.put(
                    ("progress", i, n, name)), should_stop=lambda: self._stop_scan)
                self._scan_queue.put(("done", report))
            except Exception as e:
                self._scan_queue.put(("error", str(e)))

        self._scan_thread = threading.Thread(target=work, daemon=True, name="pdf-scan")
        self._scan_thread.start()
        self.after(150, self._poll_scan)

    def _poll_scan(self):
        if self._stop_scan:
            return
        last = None
        try:
            while True:
                last = self._scan_queue.get_nowait()
                if last[0] != "progress":
                    break
        except queue.Empty:
            pass
        try:
            if last and last[0] == "progress":
                _k, i, n, name = last
                if name:
                    self.status.configure(text=f"Reading PDFs: {i + 1} of {n} ({name})")
            elif last and last[0] == "done":
                self._after_scan(last[1])
                return
            elif last and last[0] == "error":
                self.status.configure(text=f"The library couldn't be read: {last[1]}")
                return
            self.after(150, self._poll_scan)
        except tk.TclError:
            pass

    def _after_scan(self, report):
        docs, pages = self.library.stats()
        text = f"{docs} PDF{'s' if docs != 1 else ''}, {pages} pages."
        changes = [f"{n} {what}" for n, what in ((report.added, "new"), (report.updated, "updated"),
                                                (report.removed, "removed")) if n]
        if changes:
            text += " " + ", ".join(changes) + "."
        if report.failed:
            text += f" {len(report.failed)} couldn't be read: " + ", ".join(
                os.path.basename(p) for p, _e in report.failed[:3])
        if not docs:
            text = "No PDFs yet. Put some in the library folder (Open Library Folder) or add a folder, then Rescan."
        self.status.configure(text=text)
        self._show_documents()

    # ------------------------------------------------------------------ searching

    def _documents(self) -> List[Document]:
        return self.library.documents()

    def _show_documents(self):
        docs = self._documents()
        titles = [ALL_DOCS] + [d.title for d in docs]
        self.doc_menu.configure(values=titles)
        if self.doc_var.get() not in titles:
            self.doc_var.set(ALL_DOCS)
        self.search()

    def _on_key(self, event):
        if event.keysym == "Return":
            self.search()
            hit = self.results.get_selected()
            if hit is None and self.results._items:
                self.results.select_by_name(self.results._items[0].name)
            return
        if self._search_job is not None:
            self.after_cancel(self._search_job)
        self._search_job = self.after(300, self.search)

    def search_text(self) -> str:
        return self.search_entry.get()

    def set_search(self, text: str):
        self.search_entry.delete(0, "end")
        if text:
            self.search_entry.insert(0, text)
        self.search()

    def search(self) -> list:
        self._search_job = None
        query = self.search_text().strip()
        self.state["query"] = query
        docs = self._documents()
        doc_id = next((d.id for d in docs if d.title == self.doc_var.get()), None)
        if not query:
            items = [d for d in docs if doc_id is None or d.id == doc_id]
        else:
            items = self.library.search(query, doc_id)
        self.results.set_items(items, keep_current=False)
        return items

    def _terms(self) -> List[str]:
        return [t for t in self.search_text().lower().split() if t]

    def _on_select(self, item):
        if item is None:
            return
        if isinstance(item, Hit):
            self.open_document(item.doc, item.page)
        else:
            self.open_document(item, 0)

    # ------------------------------------------------------------------ viewing

    def open_document(self, doc: Document, page: int = 0):
        if not os.path.isfile(doc.path):
            messagebox.showwarning("PDF Library", f"{doc.path} isn't there any more. Rescan to tidy the list.",
                                   parent=self)
            return
        changed = self._doc is None or self._doc.id != doc.id
        self._doc = doc
        try:
            self.viewer.open(doc.path)
        except Exception as e:
            messagebox.showerror("PDF Library", f"Couldn't open {doc.title}:\n{e}", parent=self)
            return
        if changed:
            self._toc = self.library.toc(doc.id)
            labels = ["Sections"] + [("   " * min(e.level, 3)) + e.title[:60] for e in self._toc]
            self.section_menu.configure(values=labels if self._toc else ["No bookmarks"])
            self.section_var.set("Sections" if self._toc else "No bookmarks")
        self.title_label.configure(text=doc.title)
        self.viewer.show_page(page, self._terms())
        self._update_nav()

    def _update_nav(self):
        has = self._doc is not None
        n = self.viewer.page_count
        self.page_entry.delete(0, "end")
        if has:
            self.page_entry.insert(0, str(self.viewer.page + 1))
        self.count_label.configure(text=f"/ {n}" if has else "")
        for btn in (self.open_btn, self.import_btn, self.prev_btn, self.next_btn):
            btn.configure(state="normal" if has else "disabled")
        self.zoom_label.configure(text=f"{int(self.viewer.zoom * 100)}%")

    def _go(self, page: int):
        if self._doc is None:
            return
        self.viewer.show_page(page, self._terms())
        self._update_nav()

    def _go_typed(self):
        try:
            self._go(int(self.page_entry.get()) - 1)
        except ValueError:
            self._update_nav()

    def _zoom(self, step: int):
        zooms = ZOOMS
        i = min(range(len(zooms)), key=lambda k: abs(zooms[k] - self.viewer.zoom))
        self.viewer.zoom = zooms[max(0, min(len(zooms) - 1, i + step))]
        self.viewer.render()
        self._update_nav()

    def _on_section(self, label: str):
        labels = self.section_menu.cget("values")
        if label in labels and labels.index(label) > 0 and self._toc:
            entry = self._toc[labels.index(label) - 1]
            self._go(entry.page)

    def _open_external(self):
        if self._doc is not None:
            open_externally(self._doc.path)

    # ------------------------------------------------------------------ folders and import

    def _on_folders(self):
        FoldersDialog(self.winfo_toplevel(), on_change=self.rescan)

    def _on_import_text(self):
        if self._doc is None:
            return
        text = self.library.page_text(self._doc.id, self.viewer.page)
        if not text.strip():
            messagebox.showinfo("Import Text", "This page has no text to import (it may be a scanned picture).",
                                parent=self)
            return
        dialog = ImportTextDialog(self.winfo_toplevel(), text, f"{self._doc.title}, page {self.viewer.page + 1}")
        self.wait_window(dialog)
        if dialog.result and self.on_import_text:
            kind, chosen = dialog.result
            self.on_import_text(IMPORT_KINDS[kind], chosen)


class ImportTextDialog(ctk.CTkToplevel):
    """Trim a page's text down to one entry and pick which collection it is for."""

    def __init__(self, parent, text: str, where: str):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.title("Import Text")
        self.geometry("620x640")
        self.transient(parent)
        self.result = None
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(frame, text=f"Text from {where}", font=ui_font("subheading", bold=True),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(frame, text="Delete everything but the entries you want (the importer splits several of the "
                                 "same kind). Each one opens in its editor, filled in, for you to check before "
                                 "it's added.", font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     wraplength=570, justify="left", anchor="w").pack(fill="x", pady=(2, 8))
        self.text = ctk.CTkTextbox(frame, wrap="word", font=ui_font("body"))
        self.text.insert("1.0", text)
        self.text.pack(fill="both", expand=True)
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(row, text="Import as", font=ui_font("body")).pack(side="left")
        self.kind_var = ctk.StringVar(value=list(IMPORT_KINDS)[0])
        ctk.CTkOptionMenu(row, variable=self.kind_var, values=list(IMPORT_KINDS), width=140).pack(
            side="left", padx=8)
        from ui.window_utils import add_cancel_save, center_on_parent
        add_cancel_save(row, self.theme, self.destroy, self._ok, confirm_text="Import…", accent=True)
        center_on_parent(self, parent, clamp=True)
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _ok(self):
        text = self.text.get("1.0", "end").strip()
        if text:
            self.result = (self.kind_var.get(), text)
        self.destroy()


class FoldersDialog(ctk.CTkToplevel):
    """The folders the library reads: its own folder (always) and any the user added."""

    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        from settings import get_settings_manager
        self.theme = get_theme_manager()
        self.settings_manager = get_settings_manager()
        self.on_change = on_change
        self.title("Library Folders")
        self.geometry("560x380")
        self.transient(parent)
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        ctk.CTkLabel(frame, text="PDFs in these folders (and the folders inside them) are in the library.",
                     font=ui_font("body"), anchor="w").pack(fill="x", pady=(0, 8))
        self.list_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True)
        bottom = ctk.CTkFrame(frame, fg_color="transparent")
        bottom.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(bottom, text="Add Folder…", width=120, command=self._add).pack(side="left")
        ctk.CTkButton(bottom, text="Done", width=90, command=self.destroy).pack(side="right")
        self._show()
        from ui.window_utils import center_on_parent
        center_on_parent(self, parent, clamp=True)

    def _folders(self) -> List[str]:
        return list(getattr(self.settings_manager.settings, "pdf_folders", []) or [])

    def _show(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=f"{default_folder()}  (the library's own folder)", font=ui_font("small"),
                     anchor="w").pack(side="left")
        for folder in self._folders():
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=folder, font=ui_font("small"), anchor="w").pack(side="left")
            ctk.CTkButton(row, text="Remove", width=70, height=24,
                          fg_color=self.theme.get_current_color('button_danger'),
                          hover_color=self.theme.get_current_color('button_danger_hover'),
                          command=lambda f=folder: self._remove(f)).pack(side="right")

    def _add(self):
        folder = filedialog.askdirectory(parent=self, title="Add a folder of PDFs")
        if folder and folder not in self._folders():
            self.settings_manager.update(pdf_folders=self._folders() + [folder])
            self._show()
            if self.on_change:
                self.on_change()

    def _remove(self, folder: str):
        self.settings_manager.update(pdf_folders=[f for f in self._folders() if f != folder])
        self._show()
        if self.on_change:
            self.on_change()
