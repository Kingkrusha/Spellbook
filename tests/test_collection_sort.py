"""Sorting the collection pages (collection_sort.py, ui/sort_control.py): every page's choices, ascending and
descending, the person's own fields, entries without a value, and the choice remembered per collection."""

import os
import shutil
import time
from types import SimpleNamespace as NS

import pytest

import collection_sort as cs
import custom_collections as cc
from settings import get_settings_manager


def pump(root, n=12):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


def names(entries):
    return [e.name for e in entries]


@pytest.fixture(autouse=True)
def _forget_sorts():
    """Each test starts with no remembered sort (the settings are the tests' throwaway copy)."""
    s = get_settings_manager()
    s.settings.collection_sort = {}
    yield
    s.settings.collection_sort = {}
    s.save()


# ------------------------------------------------------------------ the sorting rules (no Tk)

FIELD = cs.SortField("Level", lambda e: e.level)


def test_sorts_ascending_and_descending_with_name_breaking_ties():
    items = [NS(name="b", level=2), NS(name="C", level=1), NS(name="a", level=2), NS(name="d", level=1)]
    assert names(cs.sort_entries(items, FIELD)) == ["C", "d", "a", "b"]
    # Descending flips the levels, but equal levels stay A to Z
    assert names(cs.sort_entries(items, FIELD, descending=True)) == ["a", "b", "C", "d"]


def test_by_name_ignores_case_and_can_be_reversed():
    items = [NS(name="beta"), NS(name="Alpha"), NS(name="gamma")]
    assert names(cs.sort_entries(items, None)) == ["Alpha", "beta", "gamma"]
    assert names(cs.sort_entries(items, cs.SortField(cs.NAME, lambda e: e.name), True)) == ["gamma", "beta", "Alpha"]


def test_entries_without_a_value_come_last_either_way():
    items = [NS(name="x", level=None), NS(name="y", level=3), NS(name="w", level=""), NS(name="z", level=1)]
    assert names(cs.sort_entries(items, FIELD)) == ["z", "y", "w", "x"]
    assert names(cs.sort_entries(items, FIELD, True)) == ["y", "z", "w", "x"]


def test_mixed_numbers_and_text_never_break_the_sort():
    items = [NS(name="a", level="lots"), NS(name="b", level=5), NS(name="c", level=True), NS(name="d", level=[1, 2])]
    assert names(cs.sort_entries(items, FIELD)) == ["c", "b", "d", "a"]   # numbers (True = 1) first, then text


def test_a_broken_value_sorts_as_missing():
    def boom(e):
        if e.name == "bad":
            raise ValueError
        return 1
    items = [NS(name="bad"), NS(name="good")]
    assert names(cs.sort_entries(items, cs.SortField("X", boom))) == ["good", "bad"]


def test_sizes_rank_in_size_order():
    assert [cs.size_rank(s) for s in ("Tiny", "Small or Medium", "Gargantuan", "", "Weird")] == [0, 1, 5, None, "weird"]


def test_each_builtin_page_offers_its_own_properties():
    labels = {k: [f.label for f in fn()] for k, fn in cs.BUILTIN_SORTS.items()}
    assert labels["spells"][:2] == ["Name", "Level"] and "Range" in labels["spells"]
    assert {"Rarity", "Price", "Attunement"} <= set(labels["magic_items"])
    assert {"CR", "HP", "AC", "Size"} <= set(labels["monsters"])
    assert all(ls[0] == "Name" and "Source" in ls for ls in labels.values())


def test_magic_items_sort_by_rarity_order_not_alphabetically():
    from magic_item import MagicItem, Rarity
    items = [MagicItem("Wand", rarity=Rarity.VERY_RARE), MagicItem("Cloak", rarity=Rarity.UNCOMMON),
             MagicItem("Orb", rarity=Rarity.ARTIFACT), MagicItem("Ring", rarity=Rarity.COMMON)]
    rarity = cs.find(cs.magic_item_sorts(), "Rarity")
    assert names(cs.sort_entries(items, rarity)) == ["Ring", "Cloak", "Wand", "Orb"]


def test_prices_sort_as_coins_and_unknown_prices_come_last():
    from equipment import Equipment
    items = [Equipment("Gem", cost="1 pp"), Equipment("Rope", cost="1 gp"), Equipment("Odd", cost="Varies"),
             Equipment("Nail", cost="5 cp")]
    price = cs.find(cs.equipment_sorts(), "Price")
    assert names(cs.sort_entries(items, price)) == ["Nail", "Rope", "Gem", "Odd"]
    assert names(cs.sort_entries(items, price, True)) == ["Gem", "Rope", "Nail", "Odd"]


def test_remembered_per_collection_and_defaults_are_not_stored():
    s = get_settings_manager()
    assert cs.remembered(s.settings, "feats") == ("Name", False)
    assert cs.remembered(s.settings, "spells") == ("Level", False)        # spells were always listed by level
    cs.remember(s, "feats", "Type", True)
    cs.remember(s, "spells", "Level", False)
    assert cs.remembered(s.settings, "feats") == ("Type", True)
    assert "spells" not in s.settings.collection_sort
    cs.remember(s, "feats", "Name", False)
    assert s.settings.collection_sort == {}


def test_settings_keep_the_sorts_and_drop_a_broken_value():
    from settings import AppSettings
    assert AppSettings.from_dict({"collection_sort": {"feats": ["Type", True]}}).collection_sort == {
        "feats": ["Type", True]}
    assert AppSettings.from_dict({"collection_sort": "nonsense"}).collection_sort == {}
    # and a broken entry in it reads as "not chosen"
    assert cs.remembered(NS(collection_sort={"feats": "Type"}), "feats") == ("Name", False)


# ------------------------------------------------------------------ the person's own fields

def _fresh_db(tmp_path_factory):
    from database import SpellDatabase
    folder = tmp_path_factory.mktemp("sortdb")
    path = os.path.join(str(folder), "spellbook.db")
    shutil.copy(os.environ["SPELLBOOK_TEST_SEED_DB"], path)
    db = SpellDatabase(path)
    db.initialize()
    return db


def _wipe(db):
    with db.get_connection() as conn:
        conn.execute("DELETE FROM collection_types")
        conn.execute("DELETE FROM custom_entries")
        conn.execute("DELETE FROM custom_field_values")


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return _fresh_db(tmp_path_factory)


@pytest.fixture
def mgr(db):
    m = cc.get_collection_manager()
    old = m._db
    m._db = db
    _wipe(db)
    m.reload()
    yield m
    _wipe(db)
    m._db = old
    m.reload()


def test_added_fields_on_a_builtin_collection_are_sort_choices(mgr):
    feats = mgr.builtin_type("feats")
    feats.fields = [cc.FieldDef("f_tier", "Tier", "choice", ["Low", "Mid", "High"]),
                    cc.FieldDef("f_notes", "Notes", "long_text")]      # long text isn't offered
    mgr.save_type(feats)
    mgr.set_extra_values("feats", "Alert", {"f_tier": "High"})
    mgr.set_extra_values("feats", "Lucky", {"f_tier": "Low"})
    mgr.set_extra_values("feats", "Tough", {"f_tier": "Mid"})
    sorts = cs.sorts_for("feats", mgr)
    labels = [f.label for f in sorts]
    assert "Tier" in labels and "Notes" not in labels
    # (a field can't be called after a property the collection has; one that matches a sort choice anyway
    # gets a note after its name)
    clash = cs.own_field_sorts([cc.FieldDef("f_cr", "CR")], ["Name", "CR"], lambda e, fid: None)
    assert [f.label for f in clash] == ["CR (your field)"]
    entries = [NS(name=n) for n in ("Tough", "Grappler", "Alert", "Lucky")]
    # choices sort in the order they were set up in (Low, Mid, High), not alphabetically; no value last
    assert names(cs.sort_entries(entries, cs.find(sorts, "Tier"))) == ["Lucky", "Tough", "Alert", "Grappler"]


def test_a_new_collection_sorts_by_its_own_fields(mgr):
    t = mgr.save_type(cc.CollectionType(key="", name="Deities", fields=[
        cc.FieldDef("f_rank", "Rank", "number"), cc.FieldDef("f_open", "Worshipped openly", "yes_no")]))
    entries = [cc.CustomEntry("deities", "Zeus", values={"f_rank": 1, "f_open": True}),
               cc.CustomEntry("deities", "Hades", values={"f_rank": 3, "f_open": False}),
               cc.CustomEntry("deities", "Pan")]
    sorts = cs.custom_collection_sorts(t)
    assert [f.label for f in sorts] == ["Name", "Source", "Rank", "Worshipped openly"]
    assert names(cs.sort_entries(entries, cs.find(sorts, "Rank"), True)) == ["Hades", "Zeus", "Pan"]
    assert names(cs.sort_entries(entries, cs.find(sorts, "Worshipped openly"), True)) == ["Zeus", "Hades", "Pan"]


# ------------------------------------------------------------------ on the pages

def shown(view):
    return [i.name for i in view.list_panel._items]


def _page(tk_root, module, cls):
    import importlib
    view = getattr(importlib.import_module(module), cls)(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    view._apply_filters()
    pump(tk_root)
    return view


def test_feats_page_sorts_by_type_and_remembers_it(tk_root):
    view = _page(tk_root, "ui.feats_view", "FeatsView")
    try:
        assert shown(view) == sorted(shown(view), key=str.lower)
        view.sorter.set("Type", descending=True)
        pump(tk_root, 20)
        types = [(f.type or "General").lower() for f in view.list_panel._items]
        assert types == sorted(types, reverse=True)
        assert view.sorter.direction_btn.cget("text") == "↓"
    finally:
        view.destroy()
    # A new Feats page starts sorted the same way
    again = _page(tk_root, "ui.feats_view", "FeatsView")
    try:
        assert (again.sorter.var.get(), again.sorter.descending) == ("Type", True)
        again._clear_filters()                       # Clear Filters keeps the sort
        pump(tk_root, 20)
        assert again.sorter.var.get() == "Type"
    finally:
        again.destroy()


def test_items_page_sorts_by_price(tk_root):
    from equipment import parse_cost_to_copper
    view = _page(tk_root, "ui.equipment_view", "EquipmentView")
    try:
        view.sorter.set("Price")
        pump(tk_root, 20)
        prices = [parse_cost_to_copper(i.cost) for i in view.list_panel._items]
        known = [p for p in prices if p is not None]
        assert known == sorted(known) and prices[:len(known)] == known     # unknown prices at the end
    finally:
        view.destroy()


def test_monsters_page_sorts_by_cr_both_ways(tk_root):
    from monster import cr_to_number
    view = _page(tk_root, "ui.monster_view", "MonsterView")
    try:
        view.sorter.set("CR", descending=True)
        pump(tk_root, 20)
        crs = [cr_to_number(m.challenge_rating) for m in view.list_panel._items]
        assert len(crs) > 10 and crs == sorted(crs, reverse=True)
        view.sorter.toggle_direction()
        pump(tk_root, 20)
        crs = [cr_to_number(m.challenge_rating) for m in view.list_panel._items]
        assert crs == sorted(crs)
    finally:
        view.destroy()


def test_spells_page_starts_by_level_and_sorts_by_name(tk_root):
    import tempfile
    from character_manager import CharacterManager
    from spell_manager import SpellManager
    from ui.spells_view import SpellsView
    manager = SpellManager()
    assert manager.load_spells()
    characters = CharacterManager(os.path.join(tempfile.mkdtemp(), "characters.json"))
    view = SpellsView(tk_root, manager, characters, get_settings_manager())
    view.pack(fill="both", expand=True)
    pump(tk_root)
    view._refresh_spell_list()
    pump(tk_root)
    try:
        levels = [s.level for s in view.spell_list._items]
        assert view.sorter.var.get() == "Level" and levels == sorted(levels)
        view.sorter.set("Name", descending=True)
        pump(tk_root, 20)
        shown_names = [s.name.lower() for s in view.spell_list._items]
        assert shown_names == sorted(shown_names, reverse=True)
    finally:
        view.destroy()
