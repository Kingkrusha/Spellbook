"""The Homebrew Studio's data side: drafts on disk, publishing, the service that analyses a draft."""

import json
import os

import pytest

import studio_store as SS
from studio_service import StudioService, units_for


@pytest.fixture
def store(tmp_path):
    return SS.StudioStore(str(tmp_path / "studio.json"))


@pytest.fixture(scope="module")
def service():
    from spell_manager import SpellManager
    sm = SpellManager()
    sm.load_spells()
    svc = StudioService(sm, SS.StudioStore(os.path.join(os.environ["SPELLBOOK_DATA_DIR"], "studio-test.json")))
    svc.ensure_index(wait=True)
    return svc


# --------------------------------------------------------------------------- drafts on disk

def test_drafts_survive_a_restart(store, tmp_path):
    d = store.new("magic_items", "Cloak of Tests", {"name": "Cloak of Tests", "description": "Does things."})
    assert store.save()
    again = SS.StudioStore(str(tmp_path / "studio.json"))
    assert [x.name for x in again.drafts] == ["Cloak of Tests"]
    assert again.get(d.id).record["description"] == "Does things."
    assert again.last_draft == d.id


def test_update_reports_whether_anything_changed(store):
    d = store.new("feats", "Lucky Break", {"name": "Lucky Break"})
    assert store.update(d, "Lucky Break", {"name": "Lucky Break"}) is False
    assert store.update(d, "Lucky Break", {"name": "Lucky Break", "description": "x"}) is True
    assert d.updated >= d.created


def test_delete_and_duplicate(store):
    a = store.new("spells", "Spark")
    b = store.duplicate(a)
    assert b.name == "Spark (copy)" and b.id != a.id and b.kind == "spells"
    store.delete(a.id)
    assert store.get(a.id) is None and store.get(b.id) is not None
    assert store.last_draft == b.id


def test_a_damaged_file_does_not_stop_the_studio(tmp_path):
    path = tmp_path / "studio.json"
    path.write_text("{ not json", encoding="utf-8")
    assert SS.StudioStore(str(path)).drafts == []
    path.write_text(json.dumps({"drafts": [{"id": "x", "kind": "nonsense"}, {"id": "y", "kind": "feats", "name": "Ok"}]}),
                    encoding="utf-8")
    assert [d.name for d in SS.StudioStore(str(path)).drafts] == ["Ok"]


def test_the_file_is_written_atomically(store, tmp_path):
    store.new("rules", "Page")
    store.save()
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]


def test_sorted_puts_the_most_recent_first(store):
    a = store.new("feats", "Old")
    b = store.new("feats", "New")
    a.updated, b.updated = 1.0, 2.0
    assert [d.name for d in store.sorted()] == ["New", "Old"]


def test_blank_names_do_not_repeat(store):
    store.new("monsters", "New monster")
    assert SS.blank_name("monsters", store.drafts) == "New monster 2"


# --------------------------------------------------------------------------- objects <-> records

def test_every_kind_round_trips_through_a_record():
    from character_class import get_class_manager
    from feat import get_feat_manager
    from lineage import get_lineage_manager
    from background import get_background_manager
    from equipment import get_equipment_manager
    from magic_item import get_magic_item_manager
    from monster import get_monster_manager
    from rules import get_rules_manager
    cm = get_class_manager()
    samples = {
        "feats": get_feat_manager().feats[0], "lineages": get_lineage_manager().lineages[0],
        "backgrounds": get_background_manager().backgrounds[0], "equipment": get_equipment_manager().items[0],
        "magic_items": get_magic_item_manager().items[0], "monsters": get_monster_manager().browsable[0],
        "rules": get_rules_manager().pages[0], "classes": cm.classes[0], "subclasses": cm.classes[0].subclasses[0],
    }
    for kind, obj in samples.items():
        record = SS.object_to_record(kind, obj)
        json.dumps(record)                                  # a record must be plain JSON
        back = SS.record_to_object(kind, record)
        assert SS.object_to_record(kind, back) == record, kind


def test_a_spell_round_trips_through_a_record(service):
    spell = service.spell_manager.spells[0]
    record = SS.object_to_record("spells", spell, service.spell_manager)
    back = SS.record_to_object("spells", record, service.spell_manager)
    assert back.name == spell.name and back.description == spell.description


def test_a_partial_spell_record_gets_defaults(service):
    spell = SS.record_to_object("spells", {"name": "Half Written"}, service.spell_manager)
    assert spell.name == "Half Written" and spell.casting_time and spell.duration


# --------------------------------------------------------------------------- publishing

def test_publishing_adds_to_the_collection_and_marks_the_draft(store, service):
    from magic_item import get_magic_item_manager
    mgr = get_magic_item_manager()
    record = {"name": "Studio Test Charm", "type": "Wondrous Item", "rarity": "Rare", "description": "A test charm.",
              "cost": "", "weight": 0, "source": "Studio test"}
    d = store.new("magic_items", "Studio Test Charm", record)
    try:
        assert SS.clash(d, service.spell_manager) == ("", "")
        report = SS.publish(d, service.spell_manager, link_mentions=False)
        assert report.imported == 1 and d.published_as == "Studio Test Charm"
        item = mgr.get_item("Studio Test Charm")
        assert item is not None and item.is_custom and not item.is_official
        assert SS.clash(d, service.spell_manager) == ("custom", "Studio Test Charm")
        again = SS.publish(d, service.spell_manager, link_mentions=False)
        assert again.updated["magic_items"] == 1                        # re-publishing updates, never duplicates
    finally:
        mgr.delete_item("Studio Test Charm")


def test_official_content_is_never_replaced(store, service):
    d = store.new("magic_items", "Bag of Holding", {"name": "Bag of Holding", "description": "Mine now."})
    assert SS.clash(d, service.spell_manager)[0] == "official"
    report = SS.publish(d, service.spell_manager, link_mentions=False)
    assert report.imported == 0 and report.skipped and d.published_as == ""
    from magic_item import get_magic_item_manager
    assert "Mine now." not in get_magic_item_manager().get_item("Bag of Holding").description


def test_a_published_monster_and_spell_arrive(store, service):
    from monster import get_monster_manager
    d = store.new("monsters", "Studio Test Beast", {"name": "Studio Test Beast", "ac": 12, "hp": 20,
                                                    "challenge_rating": "1/2"})
    spell = store.new("spells", "Studio Test Spark", {"name": "Studio Test Spark", "level": 1, "casting_time": "Action",
                                                      "range_value": 30, "components": "V, S", "duration": "Instantaneous",
                                                      "description": "A spark.", "classes": ["Wizard"]})
    try:
        assert SS.publish(d, service.spell_manager, link_mentions=False).imported == 1
        assert get_monster_manager().get_monster("Studio Test Beast") is not None
        assert SS.publish(spell, service.spell_manager, link_mentions=False).imported == 1
        assert service.spell_manager.get_spell("Studio Test Spark") is not None
    finally:
        get_monster_manager().delete_monster("Studio Test Beast")
        service.spell_manager.delete_spell("Studio Test Spark")


# --------------------------------------------------------------------------- the service

def test_units_split_a_draft_into_the_parts_worth_comparing():
    from character_class import ClassAbility, ClassLevel, CharacterClassDefinition
    from lineage import Lineage, LineageTrait
    cls = CharacterClassDefinition(name="Tester", levels={
        1: ClassLevel(level=1, abilities=[ClassAbility(title="Quick Study", description="You learn a language of your choice.")]),
        2: ClassLevel(level=2, abilities=[ClassAbility(title="Second Wind", description="You regain hit points as a bonus action.")])})
    assert [u.title for u in units_for("classes", cls)] == ["Quick Study", "Second Wind"]
    lin = Lineage(name="Tester", description="A short blurb.", traits=[LineageTrait(name="Keen Eyes", description="You have darkvision out to 60 feet.")])
    assert [u.title for u in units_for("lineages", lin)] == ["Keen Eyes"]


def test_analysis_finds_similar_content_and_checks_the_name(service):
    from magic_item import MagicItem, Rarity
    item = MagicItem(name="Bag of Holding", type="Wondrous Item", rarity=Rarity.RARE,
                     description="You can treat a d20 roll of 9 or lower as a 10 on Perception checks.",
                     is_official=False, is_custom=True)
    record = SS.object_to_record("magic_items", item)
    result = service.analyze("magic_items", item, record)
    assert any(m.entry.title == "Reliable Talent" for m in result.matches)
    assert any("official content" in p for p in result.problems)
    assert result.cr is None


def test_analysis_reports_missing_links(service):
    from feat import Feat
    feat = Feat(name="Link Test", description="You can cast [[spell:Definitely Not A Spell]] once per day.",
                is_official=False, is_custom=True)
    result = service.analyze("feats", feat, SS.object_to_record("feats", feat))
    assert any("not installed" in p and "Definitely Not A Spell" in p for p in result.problems)


def test_a_monster_analysis_includes_the_cr_report(service):
    from monster import Monster
    from stat_block import StatBlockFeature
    m = Monster(name="Ash Brute", ac=17, hp=310, challenge_rating="5", actions=[
        StatBlockFeature("Slam", "Melee Attack Roll: +7, reach 5 ft. Hit: 13 (2d8 + 4) Bludgeoning damage.")])
    result = service.analyze("monsters", m, SS.object_to_record("monsters", m))
    assert result.cr is not None and result.cr.warnings
    assert result.closest and all(c.is_official for c, _n in result.closest)
    other = service.analyze("monsters", m, SS.object_to_record("monsters", m), compare_to="17")
    assert other.cr.compared_with == "17"


def test_search_finds_objects_and_features(service):
    hits = service.search("reliable talent")
    assert hits and hits[0].title == "Reliable Talent" and hits[0].entry is not None
    hits = service.search("fireball", families=["spells"])
    assert hits and hits[0].category == "spell" and hits[0].entry is None
    assert service.search("") == []
    assert all(h.family == "monsters" for h in service.search("dragon", families=["monsters"]))


def test_a_target_can_be_opened_by_name(service):
    assert service.target("class", "Rogue") is not None
    assert service.target("spell", "fireball") is not None
    assert service.target("magic_item", "No Such Item Anywhere") is None


def test_the_index_notices_when_content_changes(service):
    assert not service.is_stale()
    service.invalidate()
    assert service.is_stale()
    service.ensure_index(wait=True)
    assert not service.is_stale()
