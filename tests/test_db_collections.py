"""The database layer for the content collections (db_collections.py): every collection's insert / update /
delete / read, what a missing field defaults to, and what comes back."""

import os
import sqlite3

import pytest

import db_collections
from database import SpellDatabase


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    database = SpellDatabase(os.path.join(tmp_path_factory.mktemp("dbc"), "collections.db"))
    database.initialize()
    return database


# (kind, plural, a minimal row, a full row, defaults a minimal row reads back with)
CASES = {
    "lineage": dict(
        plural="lineages",
        full={"name": "T-Lineage", "description": "d", "creature_type": "Fey", "size": "Small", "speed": 25,
              "traits": [{"name": "Step", "description": "Hop."}], "source": "HB",
              "is_official": False, "is_custom": True, "is_legacy": True},
        defaults={"description": "", "creature_type": "Humanoid", "size": "Medium", "speed": 30, "traits": [],
                  "source": "", "is_official": True, "is_custom": False, "is_legacy": False}),
    "feat": dict(
        plural="feats",
        full={"name": "T-Feat", "type": "General", "is_spellcasting": True, "spell_lists": ["Wizard"],
              "spells_num": {1: 2, 3: 1}, "has_prereq": True, "prereq": "Level 4", "set_spells": ["Fireball"],
              "description": "d", "source": "HB", "is_official": False, "is_custom": True, "is_legacy": True,
              "roll_effects": [{"kind": "x"}]},
        defaults={"type": "", "is_spellcasting": False, "spell_lists": [], "spells_num": {}, "has_prereq": False,
                  "prereq": "", "set_spells": [], "description": "", "source": "", "is_official": True,
                  "is_custom": False, "is_legacy": False, "roll_effects": []}),
    "equipment": dict(
        plural="equipment",
        full={"name": "T-Equipment", "type": "Weapon", "cost": "5 gp", "weight": 2.5, "source": "HB",
              "crafting_materials": ["iron"], "crafting_tool": "Smith's Tools", "description": "d",
              "tags": ["a", "b"], "properties": [{"name": "Finesse", "description": "x"}],
              "is_official": False, "is_custom": True},
        defaults={"type": "Adventuring Gear", "cost": "", "weight": 0.0, "source": "", "crafting_materials": [],
                  "crafting_tool": "", "description": "", "tags": [], "properties": [], "is_official": True,
                  "is_custom": False}),
    "magic_item": dict(
        plural="magic_items",
        full={"name": "T-MagicItem", "type": "Ring", "cost": "100 gp", "weight": 0.1, "source": "HB",
              "enchanting_materials": ["gem"], "description": "d", "tags": ["t"],
              "properties": [{"name": "P", "description": "q"}], "rarity": "Rare", "requires_attunement": True,
              "attunement_requirement": "by a wizard", "attunement_optional": True, "is_official": False,
              "is_custom": True, "roll_effects": [{"kind": "y"}]},
        defaults={"type": "Wondrous Item", "cost": "", "weight": 0.0, "source": "", "enchanting_materials": [],
                  "description": "", "tags": [], "properties": [], "rarity": "Common", "requires_attunement": False,
                  "attunement_requirement": "", "attunement_optional": False, "is_official": True,
                  "is_custom": False, "roll_effects": []}),
    "background": dict(
        plural="backgrounds",
        full={"name": "T-Background", "source": "HB", "is_legacy": True, "description": "d", "skills": ["Arcana"],
              "other_proficiencies": ["Kit"], "ability_scores": ["INT"], "feats": ["Alert"], "equipment": "stuff",
              "features": [{"name": "f", "description": "g"}], "is_official": False, "is_custom": True},
        defaults={"source": "", "is_legacy": False, "description": "", "skills": [], "other_proficiencies": [],
                  "ability_scores": [], "feats": [], "equipment": "", "features": [], "is_official": True,
                  "is_custom": False}),
    "rule": dict(
        plural="rules",
        full={"name": "T-Rule", "category": "Combat", "description": "d", "source": "HB", "tags": ["x"],
              "order": 7, "is_official": False, "is_custom": True},
        defaults={"category": "", "description": "", "source": "", "tags": [], "order": 0, "is_official": True,
                  "is_custom": False}),
}


def api(db, kind):
    plural = CASES[kind]["plural"]
    return (getattr(db, f"get_all_{plural}"), getattr(db, f"get_{kind}_by_name"), getattr(db, f"insert_{kind}"),
            getattr(db, f"update_{kind}"), getattr(db, f"delete_{kind}"))


def without_id(row):
    return {k: v for k, v in row.items() if k != "id"}


@pytest.mark.parametrize("kind", CASES)
def test_a_full_row_reads_back_as_it_was_written(db, kind):
    get_all, get_by_name, insert, update, delete = api(db, kind)
    full = CASES[kind]["full"]
    row_id = insert(full)
    try:
        assert row_id > 0
        assert without_id(get_by_name(full["name"])) == full
        assert get_by_name(full["name"].upper())["id"] == row_id          # names are looked up case-insensitively
    finally:
        delete(row_id)


@pytest.mark.parametrize("kind", CASES)
def test_a_name_alone_gets_the_defaults(db, kind):
    get_all, get_by_name, insert, update, delete = api(db, kind)
    row_id = insert({"name": "T-Minimal"})
    try:
        assert without_id(get_by_name("T-Minimal")) == {"name": "T-Minimal", **CASES[kind]["defaults"]}
    finally:
        delete(row_id)


@pytest.mark.parametrize("kind", CASES)
def test_update_replaces_every_field_and_reports_whether_the_row_existed(db, kind):
    get_all, get_by_name, insert, update, delete = api(db, kind)
    row_id = insert({"name": "T-Update"})
    try:
        assert update(row_id, dict(CASES[kind]["full"], name="T-Update")) is True
        assert without_id(get_by_name("T-Update")) == dict(CASES[kind]["full"], name="T-Update")
        assert update(row_id, {"name": "T-Update"}) is True                 # a bare update resets to the defaults
        assert without_id(get_by_name("T-Update")) == {"name": "T-Update", **CASES[kind]["defaults"]}
        assert update(10 ** 9, {"name": "nobody"}) is False
    finally:
        delete(row_id)


@pytest.mark.parametrize("kind", CASES)
def test_delete_removes_the_row_and_reports_whether_it_existed(db, kind):
    get_all, get_by_name, insert, update, delete = api(db, kind)
    row_id = insert({"name": "T-Delete"})
    assert delete(row_id) is True
    assert get_by_name("T-Delete") is None
    assert delete(row_id) is False
    assert "T-Delete" not in [r["name"] for r in get_all()]


@pytest.mark.parametrize("kind", CASES)
def test_the_official_content_is_there_and_every_row_has_the_same_keys(db, kind):
    get_all, get_by_name, *_ = api(db, kind)
    rows = get_all()
    assert len(rows) > 10
    keys = set(rows[0])
    assert {"id", "name"} <= keys
    assert all(set(r) == keys for r in rows)
    assert get_by_name("definitely not a thing") is None


def test_lists_are_alphabetical_except_rules_which_follow_the_book(db):
    for kind in ("lineage", "feat", "equipment", "magic_item", "background"):
        names = [r["name"] for r in api(db, kind)[0]()]
        assert names == sorted(names, key=str.lower), kind

    ids = [db.insert_rule({"name": n, "order": o}) for n, o in (("T-Zed", 0), ("T-Alpha", 0), ("T-Second", 2))]
    try:
        rules = db.get_all_rules()
        ordered = [r for r in rules if r["order"]]
        assert [r["order"] for r in ordered] == sorted(r["order"] for r in ordered)       # the book's pages first
        tail = [r["name"] for r in rules if not r["order"]]
        assert tail == sorted(tail, key=str.lower)                                         # the user's own after, A-Z
        assert rules.index(next(r for r in rules if r["name"] == "T-Second")) < rules.index(
            next(r for r in rules if r["name"] == "T-Alpha"))
    finally:
        for i in ids:
            db.delete_rule(i)


def test_feat_spell_counts_come_back_with_integer_keys(db):
    row_id = db.insert_feat({"name": "T-Counts", "spells_num": {"1": 2, "5": 1}})
    try:
        assert db.get_feat_by_name("T-Counts")["spells_num"] == {1: 2, 5: 1}
    finally:
        db.delete_feat(row_id)


def test_roll_effects_that_are_none_are_stored_as_an_empty_list(db):
    feat = db.insert_feat({"name": "T-NoEffects", "roll_effects": None})
    item = db.insert_magic_item({"name": "T-NoEffects", "roll_effects": None})
    try:
        assert db.get_feat_by_name("T-NoEffects")["roll_effects"] == []
        assert db.get_magic_item_by_name("T-NoEffects")["roll_effects"] == []
    finally:
        db.delete_feat(feat)
        db.delete_magic_item(item)


def test_a_magic_item_with_an_attunement_requirement_needs_attunement_unless_told_otherwise(db):
    ids = [db.insert_magic_item({"name": "T-Att1", "attunement_requirement": "by a cleric"}),
           db.insert_magic_item({"name": "T-Att2", "attunement_requirement": "by a cleric",
                                 "requires_attunement": False}),
           db.insert_magic_item({"name": "T-Att3"})]
    try:
        assert db.get_magic_item_by_name("T-Att1")["requires_attunement"] is True
        assert db.get_magic_item_by_name("T-Att2")["requires_attunement"] is False
        assert db.get_magic_item_by_name("T-Att3")["requires_attunement"] is False
    finally:
        for i in ids:
            db.delete_magic_item(i)


def test_a_zero_weight_is_kept(db):
    row_id = db.insert_equipment({"name": "T-Weightless", "weight": 0})
    try:
        assert db.get_equipment_by_name("T-Weightless")["weight"] == 0
    finally:
        db.delete_equipment(row_id)


def test_a_name_is_required():
    with pytest.raises(KeyError):
        db_collections.LINEAGES.values({"description": "no name"})


def test_the_generated_sql_names_every_column_once():
    for coll in (db_collections.LINEAGES, db_collections.FEATS, db_collections.EQUIPMENT,
                 db_collections.MAGIC_ITEMS, db_collections.BACKGROUNDS, db_collections.RULES):
        columns = [c.column for c in coll.columns]
        assert len(columns) == len(set(columns)) and columns[0] == "name"
        assert coll.insert_sql.count("?") == len(columns)
        assert coll.update_sql.count("?") == len(columns) + 1


class FakeRow(dict):
    """A sqlite3.Row stand-in: indexing a missing column raises IndexError like the real one does."""
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            raise IndexError(key)


def test_json_list_columns_tolerate_absent_or_damaged_data():
    read = db_collections.safe_json_list
    assert read(FakeRow(), "tags_json") == []                               # an older schema without the column
    assert read(FakeRow(tags_json=None), "tags_json") == []
    assert read(FakeRow(tags_json=""), "tags_json") == []
    assert read(FakeRow(tags_json="{not json"), "tags_json") == []
    assert read(FakeRow(tags_json='{"a": 1}'), "tags_json") == []           # valid JSON, but not a list
    assert read(FakeRow(tags_json='["a", "b"]'), "tags_json") == ["a", "b"]


def test_flag_columns_fall_back_when_absent():
    flag = db_collections.row_flag
    assert flag(FakeRow(), "requires_attunement", True) is True
    assert flag(FakeRow(requires_attunement=None), "requires_attunement", True) is True
    assert flag(FakeRow(requires_attunement=0), "requires_attunement", True) is False
    assert flag(FakeRow(requires_attunement=1), "requires_attunement") is True


def test_the_committed_tables_have_the_columns_the_collections_expect(db):
    """A column added to a collection but not migrated into the table would only fail at runtime."""
    with sqlite3.connect(db.db_path) as conn:
        for coll in (db_collections.LINEAGES, db_collections.FEATS, db_collections.EQUIPMENT,
                     db_collections.MAGIC_ITEMS, db_collections.BACKGROUNDS, db_collections.RULES):
            table_columns = {r[1] for r in conn.execute(f"PRAGMA table_info({coll.table})")}
            assert {c.column for c in coll.columns} <= table_columns, coll.table
