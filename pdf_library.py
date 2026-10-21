"""
The PDF library: rulebooks, adventures and handouts the user keeps as PDFs, searched page by page.

The app reads every PDF in its library folder (``PDFs`` in the user data folder) and in any other folders the
user adds (``AppSettings.pdf_folders``). The text of each page goes into a full-text index of its own,
``pdf_index.db`` beside the main database, with the same trigram search as the collections (search_index.py):
any part of a word matches, every word of the query has to be on the page. A PDF is read again only when its
size or modification time changes, so a rescan of an unchanged library takes a moment.

PDF reading uses pypdfium2 (PDFium, the engine in Chrome): text extraction here and page rendering in the
viewer (ui/pdf_library_view.py). Scanned PDFs without a text layer have nothing to index; they still open in
the viewer.
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

INDEX_FILE = "pdf_index.db"
DEFAULT_FOLDER = "PDFs"
SCHEMA_VERSION = 1
SNIPPET_CHARS = 170


def available() -> bool:
    """Whether PDFs can be read (pypdfium2 is installed)."""
    try:
        import pypdfium2  # noqa: F401
        return True
    except Exception:
        return False


def default_folder() -> str:
    from paths import user_data_path
    path = user_data_path(DEFAULT_FOLDER)
    os.makedirs(path, exist_ok=True)
    return path


def library_folders() -> List[str]:
    folders = [default_folder()]
    try:
        from settings import get_settings_manager
        extra = getattr(get_settings_manager().settings, "pdf_folders", []) or []
    except Exception:
        extra = []
    for f in extra:
        if isinstance(f, str) and f and os.path.normcase(os.path.abspath(f)) not in (
                os.path.normcase(os.path.abspath(x)) for x in folders):
            folders.append(f)
    return folders


def clean_text(text: str) -> str:
    """Page text as one searchable string: words split over a line end are joined, runs of space shrink."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub("[\u00ad\ufffe\u0002]\n?", "", text)   # soft hyphens (PDFium marks one at a line end)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # hyphenated line breaks
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


@dataclass
class Document:
    id: int
    path: str
    title: str
    pages: int
    size: int = 0

    @property
    def name(self) -> str:                  # (for lists)
        return self.title


@dataclass
class TocEntry:
    level: int
    title: str
    page: int                               # 0-based


@dataclass
class Hit:
    doc: Document
    page: int                               # 0-based
    snippet: str
    score: int
    section: str = ""

    @property
    def name(self) -> str:                  # (for lists: a key that is unique per page)
        return f"{self.doc.title} p.{self.page + 1}"


@dataclass
class ScanReport:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    failed: List[Tuple[str, str]] = field(default_factory=list)       # (path, error)


class PdfLibrary:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from paths import user_data_path
            db_path = user_data_path(INDEX_FILE)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._fts: Optional[bool] = None
        with closing(self._connect()) as conn:
            self._create(conn)

    # ---- database

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _create(self, conn: sqlite3.Connection):
        import search_index
        with conn:
            conn.execute("CREATE TABLE IF NOT EXISTS meta (version INTEGER)")
            conn.execute("""CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL UNIQUE, size INTEGER, mtime REAL,
                title TEXT, pages INTEGER)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS toc (
                doc_id INTEGER NOT NULL REFERENCES docs(id) ON DELETE CASCADE, seq INTEGER, level INTEGER,
                title TEXT, page INTEGER)""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_toc_doc ON toc(doc_id, page)")
            self._fts = search_index.is_supported(conn)
            if self._fts:
                conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(
                    doc_id UNINDEXED, page UNINDEXED, text, tokenize = 'trigram', detail = 'none')""")
            else:
                conn.execute("CREATE TABLE IF NOT EXISTS pages (doc_id INTEGER, page INTEGER, text TEXT)")
            if conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0] == 0:
                conn.execute("INSERT INTO meta (version) VALUES (?)", (SCHEMA_VERSION,))

    # ---- documents

    def documents(self) -> List[Document]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT id, path, title, pages, size FROM docs ORDER BY title COLLATE NOCASE")
            return [Document(*r) for r in rows]

    def document(self, doc_id: int) -> Optional[Document]:
        with closing(self._connect()) as conn:
            r = conn.execute("SELECT id, path, title, pages, size FROM docs WHERE id = ?", (doc_id,)).fetchone()
            return Document(*r) if r else None

    def toc(self, doc_id: int) -> List[TocEntry]:
        with closing(self._connect()) as conn:
            return [TocEntry(*r) for r in conn.execute(
                "SELECT level, title, page FROM toc WHERE doc_id = ? ORDER BY seq", (doc_id,))]

    def section_for(self, doc_id: int, page: int) -> str:
        """The bookmark a page falls under (the deepest one starting at or before it)."""
        with closing(self._connect()) as conn:
            return self._section_for(conn, doc_id, page)

    @staticmethod
    def _section_for(conn, doc_id: int, page: int) -> str:
        row = conn.execute("SELECT title FROM toc WHERE doc_id = ? AND page <= ? ORDER BY page DESC, level DESC, "
                           "seq DESC LIMIT 1", (doc_id, page)).fetchone()
        return row[0] if row else ""

    def page_text(self, doc_id: int, page: int) -> str:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT text FROM pages WHERE doc_id = ? AND page = ?", (doc_id, page)).fetchone()
            return row[0] if row else ""

    # ---- scanning

    @staticmethod
    def find_pdfs(folders: List[str]) -> List[str]:
        found = []
        for folder in folders:
            if not os.path.isdir(folder):
                continue
            for root, _dirs, names in os.walk(folder):
                for n in names:
                    if n.lower().endswith(".pdf") and not n.startswith("."):
                        found.append(os.path.abspath(os.path.join(root, n)))
        return sorted(set(found))

    def scan(self, folders: Optional[List[str]] = None,
             progress: Optional[Callable[[int, int, str], None]] = None,
             should_stop: Optional[Callable[[], bool]] = None) -> ScanReport:
        """Bring the index up to date with the PDFs in ``folders`` (default: the library's folders)."""
        report = ScanReport()
        paths = self.find_pdfs(library_folders() if folders is None else folders)
        with self._lock, closing(self._connect()) as conn:
            known: Dict[str, Tuple[int, int, float]] = {
                r[1]: (r[0], r[2], r[3]) for r in conn.execute("SELECT id, path, size, mtime FROM docs")}
            for i, path in enumerate(paths):
                if should_stop and should_stop():
                    break
                if progress:
                    progress(i, len(paths), os.path.basename(path))
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                old = known.pop(path, None)
                if old and old[1] == st.st_size and abs((old[2] or 0) - st.st_mtime) < 1e-6:
                    report.unchanged += 1
                    continue
                try:
                    title, pages, toc = read_pdf(path)
                except Exception as e:
                    report.failed.append((path, str(e)))
                    continue
                with conn:
                    if old:
                        self._delete(conn, old[0])
                    cur = conn.execute("INSERT INTO docs (path, size, mtime, title, pages) VALUES (?, ?, ?, ?, ?)",
                                       (path, st.st_size, st.st_mtime, title, len(pages)))
                    doc_id = cur.lastrowid
                    conn.executemany("INSERT INTO pages (doc_id, page, text) VALUES (?, ?, ?)",
                                     [(doc_id, n, text) for n, text in enumerate(pages)])
                    conn.executemany("INSERT INTO toc (doc_id, seq, level, title, page) VALUES (?, ?, ?, ?, ?)",
                                     [(doc_id, s, e.level, e.title, e.page) for s, e in enumerate(toc)])
                if old:
                    report.updated += 1
                else:
                    report.added += 1
            if not (should_stop and should_stop()):
                for _path, (doc_id, _s, _m) in known.items():          # gone from the folders
                    with conn:
                        self._delete(conn, doc_id)
                    report.removed += 1
        if progress:
            progress(len(paths), len(paths), "")
        return report

    @staticmethod
    def _delete(conn, doc_id: int):
        conn.execute("DELETE FROM pages WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM toc WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))

    # ---- searching

    def search(self, query: str, doc_id: Optional[int] = None, limit: int = 300) -> List[Hit]:
        """Pages that hold every word of ``query``; the best (most mentions, the words together) first."""
        terms = [t for t in (query or "").lower().split() if t]
        if not terms:
            return []
        with closing(self._connect()) as conn:
            where_doc = " AND doc_id = ?" if doc_id is not None else ""
            extra = [doc_id] if doc_id is not None else []
            found: Optional[set] = None
            for term in sorted(terms, key=len, reverse=True):
                ids = {r[0] for r in conn.execute(
                    f"SELECT rowid FROM pages WHERE text LIKE ?{where_doc}", [f"%{term}%"] + extra)}
                found = ids if found is None else found & ids
                if not found:
                    return []
            docs = {d.id: d for d in self.documents()}
            phrase = " ".join(terms)
            hits: List[Hit] = []
            ids = sorted(found)
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                for d_id, page, text in conn.execute(
                        f"SELECT doc_id, page, text FROM pages WHERE rowid IN ({','.join('?' * len(chunk))})", chunk):
                    doc = docs.get(int(d_id))
                    if doc is None:
                        continue
                    flat = " ".join(text.split())
                    lower = flat.lower()
                    score = sum(lower.count(t) for t in terms) + (10 * lower.count(phrase) if len(terms) > 1 else 0)
                    hits.append(Hit(doc, int(page), _snippet(flat, lower, terms, phrase), score))
            hits.sort(key=lambda h: (-h.score, h.doc.title.lower(), h.page))
            hits = hits[:limit]
            for h in hits:
                h.section = self._section_for(conn, h.doc.id, h.page)
            return hits

    def stats(self) -> Tuple[int, int]:
        """(documents, pages) in the index."""
        with closing(self._connect()) as conn:
            docs = conn.execute("SELECT COUNT(*), COALESCE(SUM(pages), 0) FROM docs").fetchone()
            return int(docs[0]), int(docs[1])


def _snippet(flat: str, lower: str, terms: List[str], phrase: str) -> str:
    pos = lower.find(phrase)
    if pos < 0:
        pos = min((lower.find(t) for t in terms if lower.find(t) >= 0), default=0)
    start = max(0, pos - SNIPPET_CHARS // 3)
    if start:
        space = flat.find(" ", start)
        start = space + 1 if 0 <= space < pos else start
    piece = flat[start:start + SNIPPET_CHARS]
    return ("…" if start else "") + piece.strip() + ("…" if start + SNIPPET_CHARS < len(flat) else "")


def read_pdf(path: str) -> Tuple[str, List[str], List[TocEntry]]:
    """(title, the text of each page, bookmarks) of a PDF."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    try:
        title = ""
        try:
            title = (pdf.get_metadata_dict().get("Title") or "").strip()
        except Exception:
            pass
        if not title or title.lower() in ("untitled", "microsoft word"):
            title = os.path.splitext(os.path.basename(path))[0]
        pages = []
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                textpage = page.get_textpage()
                try:
                    pages.append(clean_text(textpage.get_text_range()))
                finally:
                    textpage.close()
            finally:
                page.close()
        toc = []
        try:
            for item in pdf.get_toc(max_depth=4):
                dest = item.get_dest()
                page_index = dest.get_index() if dest is not None else None
                title_text = (item.get_title() or "").strip()
                if page_index is not None and page_index >= 0 and title_text:
                    toc.append(TocEntry(int(item.level), title_text, int(page_index)))
        except Exception:
            pass
        return title, pages, toc
    finally:
        pdf.close()


_library: Optional[PdfLibrary] = None


def get_pdf_library() -> PdfLibrary:
    global _library
    if _library is None:
        _library = PdfLibrary()
    return _library
