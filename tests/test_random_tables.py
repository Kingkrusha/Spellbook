"""Random tables (random_tables.py): reading pasted tables, rolling, storage and search, and the page."""

import os
import random
import shutil

import pytest

import random_tables as rt
from database import SpellDatabase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def manager(tmp_path):
    path = tmp_path / "spellbook.db"
    shutil.copy(os.path.join(ROOT, "spellbook.db"), path)
    db = SpellDatabase(str(path))
    db.initialize()
    m = rt.RandomTablesManager()
    m._db = db
    return m


def test_dice_range():
    assert rt.dice_range("d100") == (1, 100)
    assert rt.dice_range("2d6") == (2, 12)
    assert rt.dice_range("d%") == (1, 100)
    assert rt.dice_range("1d6+2") == (3, 8)
    assert rt.dice_range("4d6kh3") == (3, 18)
    assert not rt.valid_dice("banana")


def test_parse_numbered_d100_lines():
    text = "01-05 A merchant\n06–50: Nothing\n51 to 95 | Wolves\n96-00. A dragon\n   who is asleep"
    entries, dice = rt.parse_entries(text)
    assert dice == "d100"
    assert [(e.low, e.high) for e in entries] == [(1, 5), (6, 50), (51, 95), (96, 100)]
    assert entries[3].text == "A dragon who is asleep"
    table = rt.RandomTable("T", dice, entries)
    assert table.problems() == []
    assert table.entry_for(100).text.startswith("A dragon")


def test_parse_markdown_table():
    text = "| d8 | Result |\n|---|---|\n| 1-4 | Rain |\n| 5-7 | Sun |\n| 8 | Snow |"
    entries, dice = rt.parse_entries(text)
    assert dice == "d8"
    assert [(e.low, e.high, e.text) for e in entries] == [(1, 4, "Rain"), (5, 7, "Sun"), (8, 8, "Snow")]


def test_parse_unnumbered_lines_are_numbered():
    entries, dice = rt.parse_entries("Goblin\nOrc\n- Troll\n")
    assert dice == "d3"
    assert [(e.low, e.text) for e in entries] == [(1, "Goblin"), (2, "Orc"), (3, "Troll")]


def test_plus_means_up_to_the_top_of_the_die():
    entries, _ = rt.parse_entries("1-9 Small\n10+ Big", dice="d20")
    assert (entries[1].low, entries[1].high) == (10, 20)


def test_problems_list_gaps_overlaps_and_unreachable_entries():
    entries = [rt.TableEntry(1, 10, "a"), rt.TableEntry(8, 15, "b"), rt.TableEntry(30, 40, "c")]
    problems = rt.coverage_problems(entries, 1, 20)
    assert any("No entry for 16" in p for p in problems)
    assert any("More than one entry for 8" in p for p in problems)
    assert any("can't roll" in p for p in problems)


def test_entries_text_round_trips():
    table = rt.RandomTable("T", "d100", [rt.TableEntry(1, 50, "Low"), rt.TableEntry(51, 100, "High")])
    assert table.entries_text().splitlines()[1].startswith("51–00")
    entries, dice = rt.parse_entries(table.entries_text(), "d100")
    assert [(e.low, e.high) for e in entries] == [(1, 50), (51, 100)]


def test_roll_rolls_inline_dice_and_other_tables():
    rng = random.Random(4)
    inner = rt.RandomTable("Colour", "d2", [rt.TableEntry(1, 2, "red")])
    outer = rt.RandomTable("Thing", "d4", [rt.TableEntry(1, 4, "{1d2+10} {table: colour} hats")])
    lookup = {"colour": inner}.get
    result = rt.roll_table(outer, lambda n: lookup(n.lower()), rng)
    assert result.text in ("11 red hats", "12 red hats")
    assert result.nested and result.nested[0].table is inner
    assert "Thing:" in result.summary()


def test_nesting_stops_at_a_loop():
    loop = rt.RandomTable("Loop", "d2", [rt.TableEntry(1, 2, "again {table: Loop}")])
    result = rt.roll_table(loop, lambda n: loop)
    assert result.text.count("again") == rt.MAX_NESTING + 1


def test_a_roll_no_entry_covers():
    table = rt.RandomTable("Gap", "d4", [rt.TableEntry(1, 1, "one")])
    result = rt.roll_table(table, rng=random.Random(1))
    if result.total != 1:
        assert result.entry is None and "no entry" in result.summary()


def test_bundled_tables_are_seeded_and_valid(manager):
    names = {t.name for t in manager.tables}
    assert {"Weather", "Road Encounters", "Tavern Name"} <= names
    for t in manager.tables:
        assert t.problems() == [], t.name
    # every {table: ...} they name exists
    import re
    for t in manager.tables:
        for e in t.entries:
            for ref in re.findall(r"\{table:\s*([^}]+)\}", e.text):
                assert manager.get_table(ref.strip()), ref


def test_add_edit_delete_and_search(manager):
    table = rt.RandomTable("Haunted Noises", "d6", [rt.TableEntry(1, 3, "A creak upstairs"),
                                                    rt.TableEntry(4, 6, "Chains rattling")],
                           category="Spooky")
    manager.add_table(table)
    assert manager.get_table("haunted noises").category == "Spooky"
    assert [t.name for t in manager.search("rattling")] == ["Haunted Noises"]
    assert "Spooky" in manager.categories()
    table.entries.append(rt.TableEntry(7, 7, "x"))
    table.name = "Haunted Sounds"
    assert manager.update_table("Haunted Noises", table)
    assert manager.get_table("Haunted Noises") is None
    assert len(manager.get_table("Haunted Sounds").entries) == 3
    assert manager.delete_table("Haunted Sounds")
    assert manager.search("rattling") == []


def test_global_search_finds_tables_by_their_entries(manager):
    hits = manager.db.global_search("loaded")
    assert any(h["section"] == "Random Tables" and h["name"] == "Pocket Contents" for h in hits)


def test_export_and_import(manager, tmp_path):
    table = rt.RandomTable("Exported", "d2", [rt.TableEntry(1, 2, "yes")])
    path = str(tmp_path / "tables.json")
    assert manager.export_to_json(path, [table]) == 1
    assert manager.import_from_json(path) == 1
    got = manager.get_table("Exported")
    assert got.is_custom and got.entries[0].text == "yes"


# --------------------------------------------------------------------------- the page


@pytest.fixture()
def fresh_fonts(tk_root):
    """The shared fonts belong to the Tk that first made them (an earlier test module's): make them again."""
    from typography import get_font_manager
    get_font_manager().scope.refresh()

def test_page_search_select_and_roll(tk_root, fresh_fonts, manager, monkeypatch):
    monkeypatch.setattr(rt.RandomTablesManager, "_instance", manager)
    from ui.random_tables_view import RandomTablesView

    class Service:
        in_session = True
        sent = []

        def send_chat(self, text):
            self.sent.append(text)

    service = Service()
    state = {}
    view = RandomTablesView(tk_root, state, service=service)
    view.pack(fill="both", expand=True)
    tk_root.update()
    view.set_search("bandits")
    names = [t.name for t in view.list_panel._items]
    assert "Road Encounters" in names
    assert view.select_table("Weather")
    assert view._table.name == "Weather"
    view.share_var.set(True)
    view.count_var.set("×3")
    rolls = view.roll()
    assert len(rolls) == 3 and all(r.entry is not None for r in rolls)
    assert len(state["history"]) == 3 and len(service.sent) == 3
    hits = view.table_view.text.tag_ranges("hit")
    assert hits
    view.destroy()
