"""The PDF export (pdf_export.py): turning entries into a printable, two-column PDF."""

import pytest

pytest.importorskip("reportlab")
pypdfium2 = pytest.importorskip("pypdfium2")

import pdf_export as pe  # noqa: E402
from feat import Feat  # noqa: E402
from spell import Spell, CharacterClass  # noqa: E402


def pdf_text(path):
    doc = pypdfium2.PdfDocument(str(path))
    try:
        return len(doc), "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    finally:
        doc.close()


def make_spell(name="Spark Burst", description="A burst of sparks.\\Using a Higher-Level Spell Slot. More sparks."):
    return Spell(name=name, level=1, casting_time="1 action", ritual=False, range_value=60, components="V, S",
                 duration="Instantaneous", concentration=False, classes=[CharacterClass.WIZARD],
                 description=description)


def test_inline_markup():
    assert pe.inline("**bold** and *it*") == "<b>bold</b> and <i>it</i>"
    assert "Fireball" in pe.inline("see [[spell:Fireball]]") and "[[" not in pe.inline("see [[spell:Fireball]]")
    assert pe.inline("a < b & c") == "a &lt; b &amp; c"


def test_spell_block():
    block = pe.block_for(make_spell())
    assert block.title == "Spark Burst"
    assert "Level 1" in block.subtitle and "Wizard" in block.subtitle
    assert dict(block.stats)["Components"] == "V, S"
    assert "\\" not in block.body                  # the stored paragraph marks become paragraphs


def test_export_writes_every_entry(tmp_path):
    entries = [make_spell(), make_spell("Frost Ray", "Cold.\n\n| Roll | Effect |\n|---|---|\n| 1 | Chill |"),
               Feat(name="Quick Hands", type="General", description="You are quick.")]
    path = tmp_path / "out.pdf"
    count = pe.export_pdf(str(path), entries, pe.ExportOptions(title="My Handout"))
    assert count == 3
    pages, text = pdf_text(path)
    assert pages >= 1
    for word in ("My Handout", "Spark Burst", "Frost Ray", "Quick Hands", "Chill", "Casting Time"):
        assert word in text


@pytest.mark.parametrize("options", [pe.ExportOptions(columns=1, parchment=False, page_size="A4", page_numbers=False),
                                     pe.ExportOptions(title="")])
def test_export_options(tmp_path, options):
    path = tmp_path / "out.pdf"
    pe.export_pdf(str(path), [make_spell()], options)
    pages, text = pdf_text(path)
    assert pages == 1 and "Spark Burst" in text
    if options.page_size == "A4":
        width, height = pypdfium2.PdfDocument(str(path))[0].get_size()
        assert round(width) == 595 and round(height) == 842


def test_long_export_flows_over_pages(tmp_path):
    long_text = "\\".join(["Words " * 120] * 6)
    entries = [make_spell(f"Spell {i}", long_text) for i in range(8)]
    path = tmp_path / "out.pdf"
    pe.export_pdf(str(path), entries)
    pages, text = pdf_text(path)
    assert pages > 2 and "Spell 7" in text


def test_monster_stat_block(tmp_path):
    from monster import get_monster_manager
    monster = next(iter(get_monster_manager().monsters), None) if hasattr(get_monster_manager(), "monsters") else None
    if monster is None:
        pytest.skip("no monsters in the database")
    path = tmp_path / "out.pdf"
    pe.export_pdf(str(path), [monster])
    _, text = pdf_text(path)
    assert monster.name in text and "Armor Class" in text and "STR" in text
