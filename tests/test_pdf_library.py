"""The PDF library (pdf_library.py): reading PDFs, the page index, search, and the page."""

import os

import pytest

pytest.importorskip("pypdfium2")
pytest.importorskip("reportlab")

import pdf_library as pl  # noqa: E402


def make_pdf(path, pages, title="Test Book", bookmarks=True):
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path))
    c.setTitle(title)
    for i, lines in enumerate(pages):
        if bookmarks:
            c.bookmarkPage(f"p{i}")
            c.addOutlineEntry(f"Chapter {i + 1}", f"p{i}", level=0)
        y = 720
        for line in lines:
            c.drawString(72, y, line)
            y -= 14
        c.showPage()
    c.save()
    return str(path)


@pytest.fixture()
def library(tmp_path):
    folder = tmp_path / "pdfs"
    folder.mkdir()
    make_pdf(folder / "bestiary.pdf", [["Goblins are small and sneaky."],
                                      ["The owlbear is a fearsome forest", "creature with a terrible hug."],
                                      ["Nothing about birds here."]], title="Bestiary")
    sub = folder / "more"
    sub.mkdir()
    make_pdf(sub / "notes.pdf", [["Session notes: the party met an owlbear cub."]], title="", bookmarks=False)
    lib = pl.PdfLibrary(str(tmp_path / "index.db"))
    report = lib.scan([str(folder)])
    assert report.added == 2 and not report.failed
    return lib, folder


def test_clean_text_joins_hyphenated_words():
    assert pl.clean_text("forest-\ndwelling  owl\r\n\r\n\r\nbear") == "forestdwelling owl\n\nbear"
    assert pl.clean_text("forest￾dwelling") == "forestdwelling"


def test_scan_reads_titles_pages_and_bookmarks(library):
    lib, _folder = library
    docs = {d.title: d for d in lib.documents()}
    assert set(docs) == {"Bestiary", "notes"}                 # no title: the file name
    assert docs["Bestiary"].pages == 3
    assert [e.title for e in lib.toc(docs["Bestiary"].id)] == ["Chapter 1", "Chapter 2", "Chapter 3"]
    assert lib.section_for(docs["Bestiary"].id, 1) == "Chapter 2"
    assert "owlbear" in lib.page_text(docs["Bestiary"].id, 1)
    assert lib.stats() == (2, 4)


def test_search_needs_every_word_and_ranks_by_mentions(library):
    lib, _folder = library
    hits = lib.search("owlbear")
    assert {(h.doc.title, h.page) for h in hits} == {("Bestiary", 1), ("notes", 0)}
    hits = lib.search("owlbear hug")
    assert [(h.doc.title, h.page, h.section) for h in hits] == [("Bestiary", 1, "Chapter 2")]
    assert "terrible hug" in hits[0].snippet
    assert lib.search("owlbear dragon") == []
    bestiary = next(d for d in lib.documents() if d.title == "Bestiary")
    assert [h.doc.title for h in lib.search("owl", doc_id=bestiary.id)] == ["Bestiary"]
    assert lib.search("   ") == []


def test_rescan_picks_up_changes_and_removals(library):
    lib, folder = library
    assert lib.scan([str(folder)]).unchanged == 2
    make_pdf(folder / "bestiary.pdf", [["Now about dragons only."]], title="Bestiary")
    os.utime(folder / "bestiary.pdf", (1e9, 1e9))
    report = lib.scan([str(folder)])
    assert report.updated == 1
    assert lib.search("owlbear hug") == [] and lib.search("dragons")
    os.remove(folder / "more" / "notes.pdf")
    assert lib.scan([str(folder)]).removed == 1
    assert [d.title for d in lib.documents()] == ["Bestiary"]


def test_a_broken_pdf_is_reported_not_fatal(tmp_path):
    folder = tmp_path / "pdfs"
    folder.mkdir()
    (folder / "broken.pdf").write_bytes(b"%PDF-1.4 nonsense")
    lib = pl.PdfLibrary(str(tmp_path / "index.db"))
    report = lib.scan([str(folder)])
    assert len(report.failed) == 1 and lib.documents() == []


@pytest.fixture()
def fresh_fonts(tk_root):
    from typography import get_font_manager
    get_font_manager().scope.refresh()


def test_library_page_searches_and_shows_the_page(tk_root, fresh_fonts, library, monkeypatch):
    pytest.importorskip("PIL.ImageTk")
    lib, folder = library
    monkeypatch.setattr(pl, "library_folders", lambda: [str(folder)])
    import ui.pdf_library_view as view_mod
    monkeypatch.setattr(view_mod, "library_folders", lambda: [str(folder)])
    imported = []
    view = view_mod.PdfLibraryView(tk_root, {}, library=lib, on_import_text=lambda k, t: imported.append((k, t)))
    view.pack(fill="both", expand=True)
    view._stop_scan = True                      # the library is already read
    tk_root.update()
    hits = view.set_search("owlbear hug") or view.results._items
    assert len(hits) == 1
    view.results.select_by_name(hits[0].name)
    tk_root.update()
    assert view.viewer.page == 1 and view.viewer.page_count == 3
    assert view.page_entry.get() == "2"
    assert len(view.viewer.canvas.find_all()) >= 3          # the page and an outline round each word
    view._go(2)
    assert view.viewer.page == 2
    view._on_section("Chapter 1")
    assert view.viewer.page == 0
    view.destroy()
