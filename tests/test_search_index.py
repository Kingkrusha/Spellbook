"""The full-text search index (search_index.py) and the searches that use it."""

import os
import shutil
import sqlite3

import pytest

import search_index
from database import SpellDatabase

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "spellbook.db"
    shutil.copy(os.path.join(ROOT, "spellbook.db"), path)
    database = SpellDatabase(str(path))
    database.initialize()
    return database


needs_trigram = pytest.mark.skipif(
    not search_index.is_supported(sqlite3.connect(":memory:")),
    reason="this SQLite build has no FTS5 trigram tokenizer")


def test_search_text_reads_json_values_and_link_text():
    text = search_index.search_text(
        "Casts [[spell:Fireball|a fireball]].",
        '[{"name": "Darkvision", "description": "See in the dark."}]',
        None)
    assert "a fireball" in text and "[[" not in text
    assert "Darkvision" in text and "See in the dark." in text
    assert "description" not in text  # JSON keys are not indexed


@needs_trigram
def test_index_covers_every_collection(db):
    with db.get_connection() as conn:
        sections = {r[0] for r in conn.execute("SELECT DISTINCT section FROM search_index")}
    # the entries of collections people make ("Custom") are empty until someone makes one
    # (tests/test_custom_collections.py searches them)
    assert sections == set(search_index.SOURCES) - {"Custom"}


@needs_trigram
def test_global_search_matches_text_and_ranks_names_first(db):
    hits = db.global_search("fireball")
    assert hits[0]["in_name"]
    names = [h["name"] for h in hits]
    assert "Fireball" in names
    # Items that only mention it in their text come after every name match
    flags = [h["in_name"] for h in hits]
    assert flags == sorted(flags, reverse=True)
    assert not all(flags)


@needs_trigram
def test_words_match_in_any_order_and_inside_words(db):
    names = {h["name"] for h in db.global_search("ball fire", limit=200)}
    assert "Fireball" in names
    spells = {s["name"] for s in db.search_spells(search_text="fire ball")}
    assert "Fireball" in spells


@needs_trigram
def test_new_collections_are_searchable(db):
    sections = {h["section"] for h in db.global_search("dragon", limit=500)}
    assert {"Monsters", "Magic Items"} <= sections


@needs_trigram
def test_subclass_hits_name_their_class(db):
    hits = [h for h in db.global_search("hunter", limit=200) if h["section"] == "Subclasses"]
    assert any(h["name"] == "Hunter (Ranger)" for h in hits)


@needs_trigram
def test_triggers_keep_the_index_current(db):
    with db.get_connection() as conn:
        conn.execute("INSERT INTO feats (name, description) VALUES ('Zzyx Test Feat', 'Grants qwertyuiop.')")
    assert [h["name"] for h in db.global_search("qwertyuiop")] == ["Zzyx Test Feat"]

    with db.get_connection() as conn:
        conn.execute("UPDATE feats SET description = 'Grants asdfghjkl.' WHERE name = 'Zzyx Test Feat'")
    assert db.global_search("qwertyuiop") == []
    assert [h["name"] for h in db.global_search("asdfghjkl")] == ["Zzyx Test Feat"]

    with db.get_connection() as conn:
        conn.execute("DELETE FROM feats WHERE name = 'Zzyx Test Feat'")
    assert db.global_search("asdfghjkl") == []


@needs_trigram
def test_summoned_creatures_stay_out_of_search(db):
    with db.get_connection() as conn:
        hidden = conn.execute("SELECT id FROM monsters WHERE spell_only = 1").fetchall()
        indexed = conn.execute(
            "SELECT COUNT(*) FROM search_index WHERE section = 'Monsters' AND item_id IN (%s)"
            % ",".join(str(r[0]) for r in hidden) if hidden else "SELECT 0").fetchone()[0]
    assert indexed == 0


@needs_trigram
def test_index_is_built_once(db):
    with db.get_connection() as conn:
        before = conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0]
    SpellDatabase(db.db_path).initialize()
    with db.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM search_index").fetchone()[0] == before


@needs_trigram
def test_rebuild(db):
    with db.get_connection() as conn:
        conn.execute("DELETE FROM search_index")
    assert db.global_search("fireball") == []
    assert db.rebuild_search_index()
    assert db.global_search("fireball")


def test_falls_back_to_name_search_without_the_index(db, monkeypatch):
    monkeypatch.setattr(search_index, "is_supported", lambda conn: False)
    fallback = SpellDatabase(db.db_path)
    fallback.initialize()
    names = {h["name"] for h in fallback.global_search("fireball")}
    assert "Fireball" in names
    assert all(h["in_name"] for h in fallback.global_search("fireball"))
    assert {s["name"] for s in fallback.search_spells(search_text="fireball")} >= {"Fireball"}
    # The triggers are gone, so edits still work on a SQLite that can't run them
    with fallback.get_connection() as conn:
        assert not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'search_index%'").fetchone()
        conn.execute("INSERT INTO feats (name, description) VALUES ('Fallback Feat', 'x')")


@needs_trigram
def test_a_lost_trigger_rebuilds_the_index(db):
    with db.get_connection() as conn:
        conn.execute("DROP TRIGGER search_index_feats_ai")
    SpellDatabase(db.db_path).initialize()
    with db.get_connection() as conn:
        conn.execute("INSERT INTO feats (name, description) VALUES ('Trigger Feat', 'zxcvbnm')")
    assert [h["name"] for h in db.global_search("zxcvbnm")] == ["Trigger Feat"]
