"""The shared manager plumbing (collection_manager.py) and how the collection managers use it."""

import json
import os

import pytest

from collection_manager import DbBackedManager
from database import SpellDatabase
from equipment import Equipment, EquipmentManager
from magic_item import MagicItem, MagicItemManager, Rarity
from feat import Feat, FeatManager
from lineage import Lineage, LineageManager
from background import Background, BackgroundManager
from monster import MonsterManager
from rules import RulesManager


@pytest.fixture(scope="module")
def database(tmp_path_factory):
    db = SpellDatabase(os.path.join(tmp_path_factory.mktemp("mgr"), "managers.db"))
    db.initialize()
    return db


def make(cls, database):
    manager = cls()
    manager._db = database
    return manager


def custom(cls, name, **fields):
    return cls(name=name, is_official=False, is_custom=True, **fields)


# ---------------------------------------------------------------- DbBackedManager itself

class Counting(DbBackedManager):
    _instance = None
    loads = 0

    def _load_all(self):
        type(self).loads += 1
        return ["a", "b"]


def test_the_cache_loads_once_and_again_after_it_is_invalidated():
    manager = Counting()
    assert manager._cached() == ["a", "b"] and manager._cached() == ["a", "b"]
    assert Counting.loads == 1
    manager._invalidate_cache()
    manager._cached()
    assert Counting.loads == 2
    assert manager.load() is True and manager._cache is None        # load() just drops the cache
    assert manager.save() is True


def test_each_manager_class_has_its_own_singleton():
    assert EquipmentManager.get_instance() is EquipmentManager.get_instance()
    assert MagicItemManager.get_instance() is MagicItemManager.get_instance()
    assert EquipmentManager.get_instance() is not MagicItemManager.get_instance()
    assert not isinstance(EquipmentManager.get_instance(), MagicItemManager)
    for cls in (EquipmentManager, MagicItemManager, FeatManager, BackgroundManager, MonsterManager, RulesManager):
        assert issubclass(cls, DbBackedManager)
        assert cls.get_instance() is cls.get_instance()


def test_the_database_is_opened_on_first_use_and_only_then(database):
    manager = EquipmentManager()
    assert manager._db is None
    manager._db = database
    assert manager.db is database


# ---------------------------------------------------------------- equipment and magic items (ItemManagerBase)

ITEM_KINDS = {
    "equipment": dict(cls=EquipmentManager, model=Equipment, extra={"crafting_materials": ["iron"]}),
    "magic_item": dict(cls=MagicItemManager, model=MagicItem, extra={"enchanting_materials": ["gem"]}),
}


@pytest.fixture(params=list(ITEM_KINDS))
def items(request, database):
    kind = ITEM_KINDS[request.param]
    manager = make(kind["cls"], database)
    yield manager, kind["model"], kind["extra"]
    for item in list(manager.items):                     # leave the shared database as it was found
        if item.is_custom:
            manager.delete_item(item.name)


def test_items_are_added_found_updated_and_deleted(items):
    manager, model, extra = items
    before = len(manager.items)
    thing = custom(model, "T-Thing", type="Tool", description="alpha [[spell:Fireball|a spark]]", tags=["Zeta", "alpha"], **extra)

    assert manager.add_item(thing) is True
    assert len(manager.items) == before + 1                           # the cache was refreshed
    found = manager.get_item("t-thing")
    assert found.name == "T-Thing" and found.tags == ["Zeta", "alpha"] and found.is_custom
    assert manager.get_item("T-Nothing") is None

    changed = custom(model, "T-Thing", type="Tool", description="beta", **extra)
    assert manager.update_item("T-Thing", changed) is True
    assert manager.get_item("T-Thing").description == "beta"
    assert manager.update_item("T-Missing", changed) is False

    assert manager.add_item(custom(model, "T-Thing", type="Tool", description="gamma", **extra)) is True   # add = upsert
    assert len(manager.items) == before + 1 and manager.get_item("T-Thing").description == "gamma"

    assert manager.delete_item("T-Thing") is True
    assert manager.delete_item("T-Thing") is False
    assert len(manager.items) == before


def test_official_items_cannot_be_deleted(items):
    manager, _model, _extra = items
    official = next(i for i in manager.items if not i.is_custom)
    assert manager.delete_item(official.name) is False
    assert manager.get_item(official.name) is not None


def test_search_looks_at_name_description_and_tags_and_ignores_link_markup(items):
    manager, model, extra = items
    manager.add_item(custom(model, "T-Searchable", type="Tool", description="a [[spell:Fireball|glowing ember]] inside",
                            tags=["Pyrotechnic"], **extra))
    names = lambda query, **kw: [i.name for i in manager.search_items(query, **kw)]
    assert "T-Searchable" in names("searchable")
    assert "T-Searchable" in names("glowing ember")                   # the visible text of the link
    assert "T-Searchable" not in names("[[spell")                     # not the markup
    assert "T-Searchable" in names("pyrotech")
    assert "T-Searchable" in names("", item_type="Tool")
    assert "T-Searchable" not in names("searchable", item_type="Ring")
    assert [i.name for i in manager.get_items_by_type("Tool")].count("T-Searchable") == 1


def test_the_lists_of_what_is_in_use(items):
    manager, model, extra = items
    manager.add_item(custom(model, "T-Lists", type="Zebra Gear", source="Table Rules", tags=["Brand New Tag"],
                            properties=[{"name": "Gleaming", "description": ""}], **extra))
    manager.add_item(custom(model, "T-Lists2", source="Table Rules",
                            properties=[{"name": "Gleaming", "description": "It shines."}]))

    assert "Zebra Gear" in manager.get_all_types() and manager.get_all_types() == sorted(manager.get_all_types())
    assert "Brand New Tag" in manager.get_all_tags() and "Finesse" in manager.get_all_tags()   # in use + suggested
    assert manager.get_all_properties()["Gleaming"] == "It shines."   # the first non-empty description wins
    assert "Table Rules" in manager.get_all_sources()
    assert manager.get_unofficial_sources() == ["Table Rules"]
    assert sorted(i.name for i in manager.get_unofficial_items()) == ["T-Lists", "T-Lists2"]


def test_equipment_and_magic_item_extras(database):
    equipment = make(EquipmentManager, database)
    equipment.add_item(custom(Equipment, "T-Tooled", crafting_tool="Zither", crafting_materials=["Rare Wood"]))
    assert "Zither" in equipment.get_all_crafting_tools()
    assert "Rare Wood" in equipment.get_all_crafting_materials()
    equipment.delete_item("T-Tooled")

    magic = make(MagicItemManager, database)
    magic.add_item(custom(MagicItem, "T-Glowy", rarity=Rarity.LEGENDARY, enchanting_materials=["Moon Dust"]))
    assert "Moon Dust" in magic.get_all_enchanting_materials()
    assert "T-Glowy" in [i.name for i in magic.get_items_by_rarity(Rarity.LEGENDARY)]
    assert "T-Glowy" not in [i.name for i in magic.get_items_by_rarity(Rarity.COMMON)]
    magic.delete_item("T-Glowy")


def test_magic_items_keep_their_attunement_and_rarity(database):
    magic = make(MagicItemManager, database)
    magic.add_item(custom(MagicItem, "T-Attuned", rarity=Rarity.VERY_RARE, requires_attunement=True,
                          attunement_requirement="by a wizard", attunement_optional=True,
                          roll_effects=[{"kind": "x"}]))
    try:
        item = magic.get_item("T-Attuned")
        assert item.rarity is Rarity.VERY_RARE and item.requires_attunement and item.attunement_optional
        assert item.display_attunement() == "Requires Attunement by a wizard (optional)"
        assert item.roll_effects == [{"kind": "x"}]
    finally:
        magic.delete_item("T-Attuned")


def test_exporting_writes_only_the_homebrew_unless_told_otherwise(items, tmp_path):
    manager, model, extra = items
    manager.add_item(custom(model, "T-Exported", description="d", **extra))
    path = str(tmp_path / "out.json")
    assert manager.export_to_json(path) == 1
    written = json.loads(open(path, encoding="utf-8").read())
    (key,) = written
    assert key == manager.JSON_KEY and [e["name"] for e in written[key]] == ["T-Exported"]

    everything = manager.items[:3]
    assert manager.export_to_json(path, everything) == 3
    assert manager.export_to_json(str(tmp_path)) == 0                                  # a directory: the write fails, 0 reported


def test_importing_a_missing_file_adds_nothing(items, tmp_path):
    manager, _model, _extra = items
    assert manager.import_from_json(str(tmp_path / "nope.json")) == 0


# ---------------------------------------------------------------- the display helpers both models share

@pytest.mark.parametrize("model", [Equipment, MagicItem])
def test_item_display_helpers(model):
    assert model(name="a", weight=1).display_weight() == "1 lb"
    assert model(name="a", weight=2).display_weight() == "2 lbs"
    assert model(name="a", weight=2.5).display_weight() == "2.5 lbs"
    assert model(name="a", weight=0).display_weight() == "0 lbs"
    assert model(name="a", tags=["beta", "Alpha", "gamma"]).display_tags() == "Alpha, beta, gamma"
    assert model(name="a", description="see [[spell:Fireball|the flames]] here").plain_description() == "see the flames here"


# ---------------------------------------------------------------- the other collection managers

def test_feats_lineages_and_backgrounds_round_trip_through_their_managers(database):
    feats = make(FeatManager, database)
    assert feats.add_feat(custom(Feat, "T-Feat", type="General", spells_num={1: 2}, is_spellcasting=True)) is True
    try:
        feat = feats.get_feat("T-Feat")
        assert feat.spells_num == {1: 2} and feat.is_spellcasting
        assert "T-Feat" in [f.name for f in feats.feats] and feat in feats.get_spellcasting_feats()
        assert feats.update_feat("T-Feat", custom(Feat, "T-Feat", description="changed")) is True
        assert feats.get_feat("T-Feat").description == "changed"
    finally:
        assert feats.delete_feat("T-Feat") is True
    assert feats.get_feat("T-Feat") is None

    lineages = make(LineageManager, database)
    assert lineages.add_lineage(custom(Lineage, "T-Lineage", size="Small", speed=20)) is True
    try:
        assert lineages.get_lineage("T-Lineage").speed == 20
        assert "T-Lineage" in [l.name for l in lineages.lineages]
    finally:
        assert lineages.remove_lineage("T-Lineage") is True
    assert lineages.get_lineage("T-Lineage") is None

    backgrounds = make(BackgroundManager, database)
    assert backgrounds.add_background(custom(Background, "T-Background", source="", is_legacy=False, description="", skills=["Arcana"])) is True
    try:
        assert backgrounds.get_background("T-Background").skills == ["Arcana"]
        assert "T-Background" in [b.name for b in backgrounds.backgrounds]
    finally:
        assert backgrounds.remove_background("T-Background") is True
    assert backgrounds.get_background("T-Background") is None


def test_monsters_and_rules_load_through_the_shared_cache(database):
    monsters = make(MonsterManager, database)
    assert len(monsters.monsters) > 100 and monsters.monsters is monsters.monsters      # cached, not re-read
    first = monsters.monsters[0]
    assert monsters.get_monster(first.name).name == first.name
    assert monsters.load() is True and monsters._cache is None

    rules = make(RulesManager, database)
    assert len(rules.pages) > 10 and rules.get_page("combat") is not None
    assert rules.pages is rules.pages
    assert rules.load() is True and rules._cache is None
    assert rules.get_page("combat") is not None                                         # and it reloads on demand
