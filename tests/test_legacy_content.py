"""Bundled 2014 (legacy) content: the "(Legacy)" naming helpers, the data file and its seeding."""

import json
import os
import re
import shutil
from types import SimpleNamespace as NS

import pytest

from database import SpellDatabase
from legacy_content import (LEGACY_SUFFIX, apply_legacy_filter, legacy_pair_key,
                            strip_legacy_suffix)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------- helpers

def test_strip_legacy_suffix():
    assert strip_legacy_suffix("Fireball (Legacy)") == "Fireball"
    assert strip_legacy_suffix("fireball (legacy)") == "fireball"
    assert strip_legacy_suffix("Fireball") == "Fireball"
    assert strip_legacy_suffix("Orc (Legacy: MPMM)") == "Orc"
    assert strip_legacy_suffix("Legacy of the Dragon") == "Legacy of the Dragon"
    assert strip_legacy_suffix("") == ""


def test_pair_key_ignores_case_and_punctuation():
    assert legacy_pair_key("Power Word: Kill (Legacy)") == legacy_pair_key("Power Word Kill")
    assert legacy_pair_key("Fighter (Legacy)") == legacy_pair_key("fighter")
    assert legacy_pair_key("Mage Hand") != legacy_pair_key("Mage Armor")


def _item(name, legacy):
    return NS(name=name, is_legacy=legacy)


def test_show_unupdated_pairs_a_legacy_entry_with_its_2024_name():
    items = [_item("Fireball", False), _item("Fireball (Legacy)", True),
             _item("Branding Smite", True),                       # no 2024 counterpart
             _item("Power Word Kill", False), _item("Power Word: Kill (Legacy)", True),
             _item("Orc", False), _item("Orc (Legacy: MPMM)", True), _item("Orc (Legacy: VGM)", True)]
    names = lambda mode: [i.name for i in apply_legacy_filter(items, mode)]  # noqa: E731
    assert names("show_all") == [i.name for i in items]
    assert names("no_legacy") == ["Fireball", "Power Word Kill", "Orc"]
    assert names("legacy_only") == ["Fireball (Legacy)", "Branding Smite", "Power Word: Kill (Legacy)",
                                    "Orc (Legacy: MPMM)", "Orc (Legacy: VGM)"]
    assert names("show_unupdated") == ["Fireball", "Branding Smite", "Power Word Kill", "Orc"]


# --------------------------------------------------------------------------- the data file

@pytest.fixture(scope="module")
def bundle():
    with open(os.path.join(ROOT, "legacy_2014.json"), encoding="utf-8") as f:
        return json.load(f)


def _records(bundle):
    for kind in ("spells", "feats", "lineages", "backgrounds"):
        for rec in bundle[kind]:
            yield kind, rec
    for cname, cls in bundle["classes"].items():
        yield "classes", cls
        for sub in cls["subclasses"]:
            yield "subclasses", sub


def test_everything_is_flagged_legacy_and_official(bundle):
    for kind, rec in _records(bundle):
        assert rec["is_legacy"] is True, (kind, rec["name"])
        if kind != "spells":
            assert rec["is_official"] is True and rec["is_custom"] is False, (kind, rec["name"])


def test_names_are_unique_within_each_kind(bundle):
    for kind in ("spells", "feats", "lineages", "backgrounds"):
        names = [r["name"].lower() for r in bundle[kind]]
        assert len(names) == len(set(names)), kind
    subs = [s["name"].lower() for c in bundle["classes"].values() for s in c["subclasses"]]
    assert len(subs) == len(set(subs))


def test_legacy_names_never_reuse_a_2024_name(bundle):
    """A 2014 entry may only share a 2024 name when it carries the "(Legacy)" suffix, because the
    "(Legacy)"-less name is already taken (every name column is UNIQUE)."""
    db = SpellDatabase()
    db.initialize()
    with db.get_connection() as conn:
        taken = {}
        for kind, table in (("spells", "spells"), ("feats", "feats"), ("lineages", "lineages"),
                            ("backgrounds", "backgrounds"), ("classes", "classes")):
            taken[kind] = {r[0].lower() for r in conn.execute(f"SELECT name FROM {table} WHERE is_legacy = 0")}
    for kind in taken:
        for rec in (bundle["classes"].values() if kind == "classes" else bundle[kind]):
            assert rec["name"].lower() not in taken[kind], (kind, rec["name"])


def test_all_object_links_resolve(bundle):
    """Every [[category:Name]] link in the legacy text points at something that exists."""
    db = SpellDatabase()
    db.initialize()
    names = {k: set() for k in ("spell", "feat", "lineage", "background", "class", "subclass")}
    with db.get_connection() as conn:
        for kind, table in (("spell", "spells"), ("feat", "feats"), ("lineage", "lineages"),
                            ("background", "backgrounds"), ("class", "classes"), ("subclass", "subclasses")):
            names[kind] |= {r[0].lower() for r in conn.execute(f"SELECT name FROM {table}")}
    for kind, rec in _records(bundle):
        singular = {"spells": "spell", "feats": "feat", "lineages": "lineage", "backgrounds": "background",
                    "classes": "class", "subclasses": "subclass"}[kind]
        names[singular].add(rec["name"].lower())
    link = re.compile(r"\[\[([a-z_]+):([^\]|]+)(?:\|[^\]]*)?\]\]")
    dangling = []

    def walk(obj, where):
        if isinstance(obj, str):
            for m in link.finditer(obj):
                if m.group(2).strip().lower() not in names.get(m.group(1), set()):
                    dangling.append((where, m.group(0)))
        elif isinstance(obj, list):
            for x in obj:
                walk(x, where)
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v, where)

    for kind, rec in _records(bundle):
        walk(rec, rec["name"])
    assert not dangling, dangling[:10]


# --------------------------------------------------------------------------- seeding

def _counts(path):
    db = SpellDatabase(path)
    with db.get_connection() as conn:
        out = {}
        for t in ("spells", "feats", "lineages", "backgrounds", "classes", "subclasses"):
            out[t] = tuple(conn.execute(f"SELECT COUNT(*), COALESCE(SUM(is_legacy), 0) FROM {t}").fetchone())
        return out


def test_upgrade_and_fresh_install_get_the_same_legacy_content(tmp_path, bundle):
    # upgrade: the committed database predates the legacy content (schema < 30)
    upgraded = str(tmp_path / "upgraded.db")
    shutil.copy(os.path.join(ROOT, "spellbook.db"), upgraded)
    before = _counts(upgraded)
    SpellDatabase(upgraded).initialize()
    SpellDatabase(upgraded).initialize()            # a second launch changes nothing

    fresh = str(tmp_path / "fresh.db")
    fdb = SpellDatabase(fresh)
    fdb.initialize()
    fdb.populate_initial_spells()

    after_upgrade, after_fresh = _counts(upgraded), _counts(fresh)
    assert after_upgrade == after_fresh
    assert after_upgrade["spells"][1] == len(bundle["spells"])
    assert after_upgrade["feats"][1] == len(bundle["feats"])
    assert after_upgrade["lineages"][1] == len(bundle["lineages"])
    assert after_upgrade["backgrounds"][1] == len(bundle["backgrounds"])
    assert after_upgrade["classes"][1] == len(bundle["classes"])
    assert after_upgrade["subclasses"][1] == sum(len(c["subclasses"]) for c in bundle["classes"].values())
    # the 2024 rows are exactly what they were
    for table in ("spells", "feats", "lineages", "backgrounds", "classes", "subclasses"):
        legacy = after_upgrade[table][1]
        assert after_upgrade[table][0] - legacy == before[table][0] - before[table][1]


def test_seeding_never_overwrites_an_existing_row(tmp_path):
    path = str(tmp_path / "keep.db")
    shutil.copy(os.path.join(ROOT, "spellbook.db"), path)
    db = SpellDatabase(path)
    db.initialize()
    with db.get_connection() as conn:
        conn.execute("UPDATE spells SET description = 'my notes' WHERE name = 'Fireball (Legacy)'")
        conn.execute("UPDATE feats SET description = 'my notes' WHERE name = 'Alert (Legacy)'")
    with db.get_connection() as conn:
        assert db._seed_legacy_content(conn.cursor())
        assert conn.execute("SELECT description FROM spells WHERE name = 'Fireball (Legacy)'").fetchone()[0] == "my notes"
        assert conn.execute("SELECT description FROM feats WHERE name = 'Alert (Legacy)'").fetchone()[0] == "my notes"


def test_a_legacy_spell_keeps_its_data(tmp_path):
    path = str(tmp_path / "spell.db")
    shutil.copy(os.path.join(ROOT, "spellbook.db"), path)
    db = SpellDatabase(path)
    db.initialize()
    spell = db.get_spell_by_name("Fireball (Legacy)")
    assert spell["is_legacy"] and spell["level"] == 3 and spell["range_value"] == 150
    assert spell["source"] == "Player's Handbook (2014)"
    assert set(spell["classes"]) == {"Sorcerer", "Wizard"}
    assert "Official" in spell["tags"] and "Evocation" in spell["tags"]
    assert db.get_spell_by_name("Fireball")["is_legacy"] == 0      # the 2024 one is untouched


def test_legacy_class_is_complete(tmp_path):
    path = str(tmp_path / "class.db")
    shutil.copy(os.path.join(ROOT, "spellbook.db"), path)
    db = SpellDatabase(path)
    db.initialize()
    cls = db.get_class_by_name("Wizard (Legacy)")
    assert cls["is_legacy"] and cls["hit_die"] == "d6"
    assert len(cls["class_features"]) == 20
    assert cls["class_features"]["5"]["spell_slots"] == {"1": 4, "2": 3, "3": 2}
    subs = db.get_subclasses_by_class("Wizard (Legacy)")
    assert len(subs) >= 12 and all(s["is_legacy"] for s in subs)
    assert LEGACY_SUFFIX.strip() in "Wizard (Legacy)"


# --------------------------------------------------------------------------- legacy subclasses on 2024 classes

@pytest.fixture(scope="module")
def classes():
    from character_class import ClassManager
    manager = ClassManager()
    manager.load()
    return manager


def test_official_legacy_subclasses_are_selectable_on_the_2024_class(classes):
    """Every official legacy subclass of "X (Legacy)" can be picked by a character of the 2024 class X."""
    checked = 0
    for legacy in classes.classes:
        if not legacy.is_legacy:
            continue
        current = classes.get_class(strip_legacy_suffix(legacy.name))
        if current is None or current.is_legacy:
            continue
        selectable = {s.name for s in current.selectable_subclasses}
        for sub in legacy.subclasses:
            if sub.is_legacy and not sub.is_custom:
                assert sub.name in selectable, (current.name, sub.name)
                assert current.find_subclass(sub.name) is sub
                checked += 1
    assert checked > 100


def test_compatible_subclasses_are_not_saved_with_the_2024_class(classes):
    fighter = classes.get_class("Fighter")
    assert all(not s.is_legacy for s in fighter.subclasses)
    assert fighter.compat_subclasses and all(s.is_legacy for s in fighter.compat_subclasses)
    assert "compat_subclasses" not in fighter.to_dict()
    # ...and the legacy class doesn't pick up 2024 subclasses
    assert all(s.is_legacy for s in classes.get_class("Fighter (Legacy)").selectable_subclasses)


def test_homebrew_legacy_subclasses_stay_with_their_own_class(classes):
    from character_class import SubclassDefinition
    legacy = classes.get_class("Fighter (Legacy)")
    legacy.subclasses.append(SubclassDefinition(name="Homebrew Test", parent_class=legacy.name,
                                                is_legacy=True, is_custom=True))
    try:
        classes._attach_compatible_subclasses()
        assert classes.get_class("Fighter").find_subclass("Homebrew Test") is None
    finally:
        legacy.subclasses.pop()


def test_subclass_features_wait_for_the_class_to_choose_a_subclass(classes):
    """A 2014 Warlock patron grants its first feature at level 1; the 2024 Warlock picks a subclass at 3."""
    legacy_warlock, warlock = classes.get_class("Warlock (Legacy)"), classes.get_class("Warlock")
    assert legacy_warlock.subclass_level == 1 and warlock.subclass_level == 3
    patron = legacy_warlock.find_subclass("The Archfey")
    assert min(f.level for f in patron.features) == 1

    assert [f.level for f in legacy_warlock.get_subclass_features_up_to_level(patron, 1)] == [1, 1]
    assert warlock.get_subclass_features_up_to_level(patron, 1) == []
    assert warlock.get_subclass_features_up_to_level(patron, 2) == []
    at_3 = warlock.get_subclass_features_up_to_level(patron, 3)
    assert [f.title for f in at_3] == ["Expanded Spell List", "Fey Presence"]
    assert all(f.level == 3 for f in at_3)
    assert len(warlock.get_subclass_features_up_to_level(patron, 6)) == 3        # + Misty Escape at 6
    # the stored definition is not rewritten
    assert min(f.level for f in patron.features) == 1


def test_features_already_past_the_subclass_level_do_not_move(classes):
    fighter = classes.get_class("Fighter")
    champion = fighter.find_subclass("Champion (Legacy)")
    assert fighter.subclass_level == 3
    for feature in fighter.get_subclass_features_up_to_level(champion, 20):
        original = next(f for f in champion.features if f.title == feature.title)
        assert feature.level == max(original.level, 3)
    assert [f.level for f in fighter.get_subclass_features_up_to_level(champion, 7)] == [3, 7]


def test_subclass_spells_are_given_at_the_class_level_too(classes):
    cleric = classes.get_class("Cleric")
    assert cleric.subclass_level == 3
    life = cleric.find_subclass("Life Domain (Legacy)")
    assert min(s.level_gained for s in life.subclass_spells) == 1
    assert cleric.get_subclass_spells_up_to_level(life, 2) == []
    at_3 = cleric.get_subclass_spells_up_to_level(life, 3)
    assert {s.spell_name for s in at_3} >= {"Bless (Legacy)", "Cure Wounds (Legacy)"}
    assert all(s.level_gained == 3 for s in at_3)


def test_a_2024_character_with_a_legacy_subclass_gets_its_spells_at_the_subclass_level(classes):
    from character import CharacterSpellList, ClassLevel, update_subclass_spells
    from spell import CharacterClass

    def spells_at(level):
        character = CharacterSpellList(name="t", classes=[
            ClassLevel(character_class=CharacterClass.CLERIC, level=level, subclass="Life Domain (Legacy)")])
        update_subclass_spells(character, classes)
        return character.subclass_spells

    assert spells_at(2) == []
    assert "Bless (Legacy)" in spells_at(3) and "Cure Wounds (Legacy)" in spells_at(3)
    assert "Revivify (Legacy)" not in spells_at(4) and "Revivify (Legacy)" in spells_at(5)


def test_any_subclass_with_too_early_features_is_clamped(classes):
    """The rule is general: features defined below the class's subclass level arrive at that level."""
    from character_class import SubclassDefinition, SubclassFeature
    fighter = classes.get_class("Fighter")
    sub = SubclassDefinition(name="Early", parent_class="Fighter",
                             features=[SubclassFeature(level=1, title="A"), SubclassFeature(level=2, title="B"),
                                       SubclassFeature(level=10, title="C")])
    assert fighter.get_subclass_features_up_to_level(sub, 2) == []
    assert [(f.title, f.level) for f in fighter.get_subclass_features_up_to_level(sub, 3)] == [("A", 3), ("B", 3)]
    assert [f.title for f in fighter.get_subclass_features_up_to_level(sub, 10)] == ["A", "B", "C"]


def test_everything_the_database_is_seeded_with_is_official(tmp_path):
    """Upgraded and fresh installs alike: the bundled legacy rows are official content, never homebrew."""
    upgraded = str(tmp_path / "up.db")
    shutil.copy(os.path.join(ROOT, "spellbook.db"), upgraded)
    SpellDatabase(upgraded).initialize()
    fresh = str(tmp_path / "fresh.db")
    fdb = SpellDatabase(fresh)
    fdb.initialize()
    fdb.populate_initial_spells()
    for path in (upgraded, fresh):
        with SpellDatabase(path).get_connection() as conn:
            for table in ("feats", "lineages", "backgrounds", "classes", "subclasses"):
                rows = conn.execute(f"SELECT is_official, is_custom FROM {table} WHERE is_legacy = 1").fetchall()
                assert rows, table
                assert all(r[0] == 1 and r[1] == 0 for r in rows), (path, table)
            unofficial = conn.execute(
                "SELECT s.name FROM spells s WHERE s.is_legacy = 1 AND NOT EXISTS "
                "(SELECT 1 FROM spell_tags t WHERE t.spell_id = s.id AND t.tag = 'Official')").fetchall()
            assert not unofficial, unofficial[:5]
            assert conn.execute("SELECT COUNT(*) FROM spells WHERE is_legacy = 1 AND is_modified = 1").fetchone()[0] == 0
