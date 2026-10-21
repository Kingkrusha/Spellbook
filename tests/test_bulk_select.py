"""The collection pages' "Select" mode (tick many entries, then add them to a character or edit their tags, classes
and source), the batch writes behind it, and the "Titles only" search option every collection page has."""

import importlib
import os
import time
from dataclasses import dataclass, field
from tkinter import messagebox
from types import SimpleNamespace

import pytest

TAG = "Zqx"


def pump(root, n=12):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


# ================================================================== the list panel

@dataclass
class Entry:
    name: str
    tags: list = field(default_factory=list)


@pytest.fixture()
def panel(tk_root):
    from ui.virtual_list import VirtualListPanel
    selected = []
    p = VirtualListPanel(tk_root, on_select=selected.append)
    p.pack(fill="both", expand=True)
    p._viewport_height = lambda: 600.0
    p.selected = selected
    p.received = []
    p.enable_bulk_actions([("Do A", lambda items: p.received.append(("a", [i.name for i in items]))),
                           ("Do B", lambda items: p.received.append(("b", [i.name for i in items])))])
    p.set_items([Entry(f"Entry {i:02d}") for i in range(30)])
    p._render_visible()
    yield p
    p.destroy()


def row_texts(p):
    return {r._vl_index: r.cget("text") for r in p._pool if r._vl_index != -1}


def click(p, index):
    p._on_row_click(index)
    p._render_visible()


def test_the_list_starts_out_as_a_plain_list(panel):
    assert not panel.multi_select and panel._bulk_bar.winfo_manager() == ""
    assert row_texts(panel)[0] == "Entry 00"
    click(panel, 3)
    assert panel.checked_count() == 0 and panel.get_selected().name == "Entry 03"


def test_select_mode_shows_tick_boxes_and_a_bar(panel):
    panel.set_multi_select(True)
    panel._render_visible()
    assert panel._bulk_bar.winfo_manager() == "pack"
    assert row_texts(panel)[0] == panel.UNTICKED + "Entry 00"
    assert panel._select_btn.cget("text") == "Done"
    assert panel._bulk_count.cget("text") == "0 selected"
    assert all(b.cget("state") == "disabled" for b in panel._bulk_buttons)


def test_clicking_a_row_ticks_it_and_still_shows_it(panel):
    panel.set_multi_select(True)
    click(panel, 2)
    click(panel, 5)
    assert [i.name for i in panel.checked_items()] == ["Entry 02", "Entry 05"]
    assert row_texts(panel)[2] == panel.TICKED + "Entry 02" and row_texts(panel)[3] == panel.UNTICKED + "Entry 03"
    assert panel.get_selected().name == "Entry 05" and panel.selected[-1].name == "Entry 05"
    assert panel._bulk_count.cget("text") == "2 selected"
    assert all(b.cget("state") == "normal" for b in panel._bulk_buttons)
    click(panel, 2)                                           # a second click unticks
    assert [i.name for i in panel.checked_items()] == ["Entry 05"]
    assert row_texts(panel)[2] == panel.UNTICKED + "Entry 02"


def test_all_shown_and_none(panel):
    panel.set_multi_select(True)
    panel.check_all()
    assert panel.checked_count() == 30
    panel.clear_checked()
    assert panel.checked_count() == 0 and panel._bulk_count.cget("text") == "0 selected"


def test_the_action_buttons_get_the_ticked_entries(panel):
    panel.set_multi_select(True)
    click(panel, 1)
    click(panel, 4)
    panel._bulk_buttons[1].invoke()
    panel._bulk_buttons[0].invoke()
    assert panel.received == [("b", ["Entry 01", "Entry 04"]), ("a", ["Entry 01", "Entry 04"])]


def test_leaving_select_mode_unticks_everything(panel):
    panel.set_multi_select(True)
    panel.check_all()
    panel.set_multi_select(False)
    panel._render_visible()
    assert panel.checked_count() == 0 and panel._bulk_bar.winfo_manager() == ""
    assert row_texts(panel)[0] == "Entry 00" and panel._select_btn.cget("text") == "Select"


def test_ticks_survive_a_refilter_and_follow_the_new_objects(panel):
    panel.set_multi_select(True)
    click(panel, 0)
    click(panel, 7)
    newer = [Entry(f"Entry {i:02d}", tags=["new"]) for i in range(30) if i != 7]      # Entry 07 is filtered out
    panel.set_items(newer)
    panel._render_visible()
    ticked = {i.name: i for i in panel.checked_items()}
    assert set(ticked) == {"Entry 00", "Entry 07"}                  # the hidden one stays ticked
    assert ticked["Entry 00"].tags == ["new"]                        # and the shown one is the fresh object
    assert row_texts(panel)[0] == panel.TICKED + "Entry 00"
    assert panel._bulk_count.cget("text") == "2 selected"


def test_all_shown_only_ticks_what_the_filter_shows(panel):
    panel.set_multi_select(True)
    click(panel, 29)
    panel.set_items([Entry(f"Entry {i:02d}") for i in range(5)])
    panel.check_all()
    assert panel.checked_count() == 6                               # the 5 shown and the earlier one


def test_a_list_without_bulk_actions_ignores_select_mode(tk_root):
    from ui.virtual_list import VirtualListPanel
    plain = VirtualListPanel(tk_root, on_select=lambda item: None)
    plain.set_multi_select(True)
    assert not plain.multi_select
    plain.check_all()
    assert plain.checked_count() == 0
    plain.destroy()


def test_versions_of_an_entry_are_one_tick(tk_root):
    from legacy_content import legacy_pair_key
    from ui.virtual_list import VirtualListPanel

    class Versioned(VirtualListPanel):
        KEY = staticmethod(legacy_pair_key)

    p = Versioned(tk_root, on_select=lambda item: None)
    p.enable_bulk_actions([("Go", lambda items: None)])
    p.set_items([Entry("Fireball"), Entry("Shield")])
    p.set_multi_select(True)
    p._on_row_click(0)
    p.set_items([Entry("Fireball (Legacy)"), Entry("Shield")])       # the list now shows the other version
    assert [i.name for i in p.checked_items()] == ["Fireball (Legacy)"]
    p.destroy()


# ================================================================== batched writes

def test_a_batch_commits_once_and_rolls_back_on_error(tmp_path):
    from database import SpellDatabase
    db = SpellDatabase(str(tmp_path / "t.db"))
    db.initialize()
    names = ["Zqx One", "Zqx Two", "Zqx Three"]
    base = dict(level=1, casting_time="Action", ritual=False, range_value=0, components="V", duration="Instant",
                concentration=False, description="d", source="s", classes=["Wizard"], tags=[],
                is_modified=False, original_name="", is_legacy=False)
    with db.batch():
        for n in names:
            db.insert_spell({"name": n, **base})
        with db.batch():                                              # nested: joins the outer one
            assert db.spell_exists("Zqx One")
    assert all(db.spell_exists(n) for n in names)

    with pytest.raises(RuntimeError):
        with db.batch():
            db.insert_spell({"name": "Zqx Four", **base})
            raise RuntimeError("boom")
    assert not db.spell_exists("Zqx Four")
    assert db._batch_connection is None
    db.insert_spell({"name": "Zqx Five", **base})                     # ordinary writes work again afterwards
    assert db.spell_exists("Zqx Five")


# ================================================================== the pages

ITEM_PAGES = {
    "equipment": ("ui.equipment_view", "EquipmentView", "equipment", "Equipment"),
    "magic_item": ("ui.magic_item_view", "MagicItemView", "magic_item", "MagicItem"),
}


def told_messages(monkeypatch):
    told = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: told.append(a))
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: told.append(a))
    return told


def fake_dialog(monkeypatch, module, name, result):
    shown = []

    def make(parent, *args, **kwargs):
        shown.append(args)
        return SimpleNamespace(result=result)
    monkeypatch.setattr(module, name, make)
    return shown


@pytest.fixture(params=list(ITEM_PAGES))
def item_page(request, tk_root, monkeypatch):
    module, cls, model_module, model_cls = ITEM_PAGES[request.param]
    view = getattr(importlib.import_module(module), cls)(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    model = getattr(importlib.import_module(model_module), model_cls)
    for n in ("A", "B", "C"):
        view.item_manager.add_item(model(name=f"{TAG} {n}", type=view.item_manager.get_all_types()[0], source="Old",
                                         tags=["keep"], is_official=False, is_custom=True))
    view._load_items()
    pump(tk_root)
    view.wait_window = lambda w: None
    view.model = model
    yield view
    for item in list(view.item_manager.items):
        if item.name.startswith(TAG):
            view.item_manager.delete_item(item.name)
    view.destroy()


def tick(view, *names):
    panel = view.list_panel
    panel.set_multi_select(True)
    for name in names:
        index = panel._find(name)
        assert index is not None, name
        panel._toggle_checked(panel._items[index])


def test_the_item_pages_offer_add_tags_and_source(item_page):
    assert [b.cget("text") for b in item_page.list_panel._bulk_buttons] == ["Add to Character", "Edit Tags", "Set Source",
                                                                         "Export PDF"]


def test_setting_the_source_of_several_items(item_page, monkeypatch, tk_root):
    told = told_messages(monkeypatch)
    sources = fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkSourceDialog", "New Book")
    official = next(i for i in item_page.item_manager.items if i.is_official and not i.is_custom)
    tick(item_page, f"{TAG} A", f"{TAG} B", official.name)
    before = item_page.item_manager.get_item(official.name).source

    item_page.list_panel._bulk_buttons[2].invoke()

    assert item_page.item_manager.get_item(f"{TAG} A").source == "New Book"
    assert item_page.item_manager.get_item(f"{TAG} B").source == "New Book"
    assert item_page.item_manager.get_item(f"{TAG} C").source == "Old"                  # not ticked
    assert item_page.item_manager.get_item(official.name).source == before             # official: left alone
    assert "Updated 2 items" in told[-1][1] and "1 official left alone" in told[-1][1]
    assert len(sources) == 1 and "2 items" in sources[0][0]                            # the dialog counts the editable ones


def test_adding_and_removing_tags_on_several_items(item_page, monkeypatch, tk_root):
    told = told_messages(monkeypatch)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkTagsDialog", (["fresh", "KEEP"], ["keep"]))
    item_page.item_manager.update_item(f"{TAG} B", item_page.model(
        name=f"{TAG} B", type=item_page.item_manager.get_all_types()[0], source="Old", tags=["fresh"],
        is_official=False, is_custom=True))
    tick(item_page, f"{TAG} A", f"{TAG} B")

    item_page.list_panel._bulk_buttons[1].invoke()

    a = item_page.item_manager.get_item(f"{TAG} A")
    b = item_page.item_manager.get_item(f"{TAG} B")
    assert a.tags == ["fresh", "KEEP"]                    # "keep" removed (whatever its case), the new ones added
    assert b.tags == ["fresh", "KEEP"]                    # "fresh" was there already, so it isn't doubled
    assert "Updated" in told[-1][1]


def test_tags_that_already_match_are_not_rewritten(item_page, monkeypatch):
    told = told_messages(monkeypatch)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkTagsDialog", (["keep"], []))
    tick(item_page, f"{TAG} A")
    stored = []
    original = item_page.item_manager.update_item
    item_page.item_manager.update_item = lambda *a: stored.append(a) or original(*a)
    item_page.list_panel._bulk_buttons[1].invoke()
    assert stored == [] and "Updated 0 of 1" in told[-1][1]


def test_export_pdf_writes_the_ticked_items(item_page, monkeypatch, tmp_path):
    pytest.importorskip("reportlab")
    import pdf_export
    from tkinter import filedialog
    bulk = importlib.import_module("ui.bulk_actions")
    dialogs = fake_dialog(monkeypatch, bulk, "ExportPdfDialog", pdf_export.ExportOptions(title="Loot"))
    target = tmp_path / "loot.pdf"
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **k: str(target))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    written = []
    monkeypatch.setattr(pdf_export, "export_pdf", lambda path, entries, options: written.append(
        (path, [e.name for e in entries], options.title)))
    tick(item_page, f"{TAG} B", f"{TAG} A")
    item_page.list_panel._bulk_buttons[-1].invoke()
    assert len(dialogs) == 1 and "2 items" in dialogs[0][0]
    assert written == [(str(target), [f"{TAG} A", f"{TAG} B"], "Loot")]          # official or not, sorted by name


def test_only_official_items_ticked_says_so_and_changes_nothing(item_page, monkeypatch):
    told = told_messages(monkeypatch)
    dialogs = fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkSourceDialog", "X")
    official = [i for i in item_page.item_manager.items if i.is_official and not i.is_custom][:2]
    tick(item_page, *[o.name for o in official])
    item_page.list_panel._bulk_buttons[2].invoke()
    assert dialogs == [] and "official" in told[-1][1]


def test_an_edit_shows_in_the_detail_pane_and_the_list_afterwards(item_page, monkeypatch, tk_root):
    told_messages(monkeypatch)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkSourceDialog", "Brand New Book")
    item_page.list_panel.select_by_name(f"{TAG} A")
    pump(tk_root)
    tick(item_page, f"{TAG} A")
    item_page.list_panel._bulk_buttons[2].invoke()
    pump(tk_root, 20)
    assert item_page.list_panel.get_selected().source == "Brand New Book"
    assert item_page.list_panel.is_checked(item_page.list_panel.get_selected())          # still ticked


def test_add_to_character_puts_every_ticked_item_on_the_sheet(item_page, monkeypatch, tk_root):
    import ui.character_sheet_view as sheet_view
    import ui.item_picker as picker
    told = told_messages(monkeypatch)
    sheet = SimpleNamespace(equipment_items=[], magic_items=[])
    updated = []
    sheet_manager = SimpleNamespace(get_or_create_sheet=lambda name, char: sheet,
                                    update_sheet=lambda name, s: updated.append(name))
    monkeypatch.setattr(sheet_view, "get_sheet_manager", lambda: sheet_manager)
    character = SimpleNamespace(name="Tester")
    monkeypatch.setattr(picker, "PickCharacterDialog", lambda parent, title, chars: SimpleNamespace(result="Tester"))
    item_page.set_character_manager(SimpleNamespace(characters=[character], get_character=lambda n: character))
    tick(item_page, f"{TAG} A", f"{TAG} C")

    item_page.list_panel._bulk_buttons[0].invoke()

    assert len(sheet.equipment_items) + len(sheet.magic_items) == 2 and updated == ["Tester"]   # saved once
    assert "Added 2 items to Tester's inventory" in told[-1][1]


def test_add_to_character_without_characters_warns(item_page, monkeypatch):
    told = told_messages(monkeypatch)
    tick(item_page, f"{TAG} A")
    item_page.set_character_manager(None)
    item_page.list_panel._bulk_buttons[0].invoke()
    assert "No character manager" in told[-1][1]
    item_page.set_character_manager(SimpleNamespace(characters=[]))
    item_page.list_panel._bulk_buttons[0].invoke()
    assert "No characters available" in told[-1][1]


def test_cancelling_a_dialog_changes_nothing(item_page, monkeypatch):
    told = told_messages(monkeypatch)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkSourceDialog", None)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkTagsDialog", None)
    tick(item_page, f"{TAG} A")
    item_page.list_panel._bulk_buttons[2].invoke()
    item_page.list_panel._bulk_buttons[1].invoke()
    assert told == [] and item_page.item_manager.get_item(f"{TAG} A").source == "Old"


# ---------------------------------------------------------------- feats

@pytest.fixture()
def feats_page(tk_root, monkeypatch):
    from feat import Feat
    from ui.feats_view import FeatsView
    view = FeatsView(tk_root)
    view.pack(fill="both", expand=True)
    for n in ("A", "B"):
        view.feat_manager.add_feat(Feat(name=f"{TAG} {n}", description="d", type="General", source="Old",
                                        is_official=False, is_custom=True))
    view._load_feats()
    pump(tk_root)
    view.wait_window = lambda w: None
    yield view
    for feat in list(view.feat_manager.feats):
        if feat.name.startswith(TAG):
            view.feat_manager.delete_feat(feat.name)
    view.destroy()


def test_the_feats_page_offers_add_and_source(feats_page):
    assert [b.cget("text") for b in feats_page.list_panel._bulk_buttons] == ["Add to Character", "Set Source", "Export PDF"]


def test_feats_go_on_the_character_once(feats_page, monkeypatch):
    import ui.item_picker as picker
    told = told_messages(monkeypatch)
    saved = []
    character = SimpleNamespace(name="Tester", feats=[f"{TAG} A"])
    manager = SimpleNamespace(characters=[character], get_character=lambda n: character,
                              save_characters=lambda: saved.append(1))
    monkeypatch.setattr(picker, "PickCharacterDialog", lambda parent, title, chars: SimpleNamespace(result="Tester"))
    feats_page.set_character_manager(manager)
    tick(feats_page, f"{TAG} A", f"{TAG} B")
    feats_page.list_panel._bulk_buttons[0].invoke()
    assert character.feats == [f"{TAG} A", f"{TAG} B"] and saved == [1]
    assert "Added 1 feat" in told[-1][1] and "1 was already there" in told[-1][1]


def test_feat_sources_change_in_one_go(feats_page, monkeypatch):
    told_messages(monkeypatch)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkSourceDialog", "Shared Book")
    tick(feats_page, f"{TAG} A", f"{TAG} B")
    feats_page.list_panel._bulk_buttons[1].invoke()
    assert {feats_page.feat_manager.get_feat(f"{TAG} {n}").source for n in "AB"} == {"Shared Book"}


# ---------------------------------------------------------------- lineages, backgrounds, monsters: source only

def test_lineages_backgrounds_and_monsters_offer_the_source(tk_root):
    for module, cls in (("ui.lineages_view", "LineagesView"), ("ui.backgrounds_view", "BackgroundsView"),
                        ("ui.monster_view", "MonsterView")):
        view = getattr(importlib.import_module(module), cls)(tk_root)
        try:
            assert [b.cget("text") for b in view.list_panel._bulk_buttons] == ["Set Source", "Export PDF"], cls
        finally:
            view.destroy()


def test_a_lineage_source_can_be_set_in_bulk(tk_root, monkeypatch):
    from lineage import Lineage
    from ui.lineages_view import LineagesView
    told_messages(monkeypatch)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkSourceDialog", "Lineage Book")
    view = LineagesView(tk_root)
    view.pack(fill="both", expand=True)
    view.wait_window = lambda w: None
    try:
        source = next(l for l in view.lineage_manager.lineages if l.is_official).source
        view.lineage_manager.add_lineage(Lineage(name=f"{TAG} Folk", description="d", size="Medium", speed=30,
                                                 creature_type="Humanoid", traits=[], source=source,
                                                 is_official=False, is_custom=True))
        view._load_lineages()
        pump(tk_root)
        tick(view, f"{TAG} Folk")
        view.list_panel._bulk_buttons[0].invoke()
        assert view.lineage_manager.get_lineage(f"{TAG} Folk").source == "Lineage Book"
    finally:
        view.lineage_manager.remove_lineage(f"{TAG} Folk")
        view.destroy()


# ---------------------------------------------------------------- spells

@pytest.fixture()
def spells_page(tk_root, monkeypatch):
    from spell import CharacterClass, Spell
    view = make_spells_view(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    for n, classes in (("A", [CharacterClass.WIZARD]), ("B", [CharacterClass.WIZARD, CharacterClass.BARD]),
                       ("C", [CharacterClass.CLERIC])):
        view.spell_manager.add_spell(Spell(name=f"{TAG} Spell {n}", level=1, casting_time="Action", ritual=False,
                                           range_value=0, components="V", duration="Instantaneous",
                                           concentration=False, classes=classes, description="d", source="Old",
                                           tags=["keep", "Unofficial"]))
    view._refresh_spell_list()
    pump(tk_root)
    view.wait_window = lambda w: None
    told_messages(monkeypatch)
    yield view
    for spell in list(view.spell_manager.spells):
        if spell.name.startswith(TAG):
            view.spell_manager.delete_spell(spell.name)
    view.destroy()


def make_spells_view(root):
    import tempfile
    from character_manager import CharacterManager
    from settings import get_settings_manager
    from spell_manager import SpellManager
    from ui.spells_view import SpellsView
    manager = SpellManager()
    assert manager.load_spells()
    characters = CharacterManager(os.path.join(tempfile.mkdtemp(), "characters.json"))
    return SpellsView(root, manager, characters, get_settings_manager())


def tick_spells(view, *letters):
    tick_names = [f"{TAG} Spell {n}" for n in letters]
    view.spell_list.set_multi_select(True)
    for name in tick_names:
        index = view.spell_list._find(name)
        assert index is not None, name
        view.spell_list._toggle_checked(view.spell_list._items[index])


def stored_spell(view, letter):
    return view.spell_manager.get_spell(f"{TAG} Spell {letter}")


def test_the_spells_page_offers_all_its_actions(spells_page):
    assert [b.cget("text") for b in spells_page.spell_list._bulk_buttons] == [
        "Add to Character", "Edit Tags", "Edit Classes", "Set Source", "Export PDF"]


def test_spell_tags_in_bulk_keep_the_protected_ones(spells_page, monkeypatch):
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkTagsDialog", (["new tag"], ["keep"]))
    tick_spells(spells_page, "A", "B")
    spells_page.spell_list._bulk_buttons[1].invoke()
    for letter in "AB":
        assert sorted(stored_spell(spells_page, letter).tags) == ["Unofficial", "new tag"]
    assert stored_spell(spells_page, "C").tags == ["keep", "Unofficial"]


def test_spell_sources_in_bulk(spells_page, monkeypatch):
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkSourceDialog", "Spell Book")
    tick_spells(spells_page, "A", "C")
    spells_page.spell_list._bulk_buttons[3].invoke()
    assert [stored_spell(spells_page, n).source for n in "ABC"] == ["Spell Book", "Old", "Spell Book"]


def test_spell_classes_in_bulk(spells_page, monkeypatch):
    from spell import CharacterClass
    told = told_messages(monkeypatch)
    # add Druid to everything, take Wizard away: A would be left with Druid only, C (a Cleric) gains Druid
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkClassesDialog", (["Druid"], ["Wizard"]))
    tick_spells(spells_page, "A", "B", "C")
    spells_page.spell_list._bulk_buttons[2].invoke()
    assert sorted(stored_spell(spells_page, "A").get_class_names()) == ["Druid"]
    assert sorted(stored_spell(spells_page, "B").get_class_names()) == ["Bard", "Druid"]
    assert sorted(stored_spell(spells_page, "C").get_class_names()) == ["Cleric", "Druid"]
    assert CharacterClass.DRUID in stored_spell(spells_page, "A").classes
    assert "Updated 3 spells" in told[-1][1]


def test_a_spell_is_never_left_without_a_class(spells_page, monkeypatch):
    told = told_messages(monkeypatch)
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkClassesDialog", ([], ["Cleric"]))
    tick_spells(spells_page, "C", "A")
    spells_page.spell_list._bulk_buttons[2].invoke()
    assert stored_spell(spells_page, "C").get_class_names() == ["Cleric"]
    assert "kept their classes" in told[-1][1]


def test_editing_official_spells_marks_class_changes_as_modified(spells_page, monkeypatch):
    from spell import CharacterClass
    fake_dialog(monkeypatch, importlib.import_module("ui.bulk_actions"), "BulkClassesDialog", (["Warlock"], []))
    official = next(s for s in spells_page.spell_manager.spells if s.is_official and not s.is_modified
                    and "Warlock" not in s.get_class_names())
    spells_page.spell_list.set_multi_select(True)
    spells_page.spell_list.select_by_name(official.name)
    spells_page.spell_list._toggle_checked(spells_page.spell_list.get_selected())
    try:
        spells_page.spell_list._bulk_buttons[2].invoke()
        changed = spells_page.spell_manager.get_spell(official.name)
        assert "Warlock" in changed.get_class_names() and changed.is_modified
    finally:
        spells_page.spell_manager.restore_spell_to_default(official.name)


def test_one_notification_for_a_whole_bulk_update(spells_page):
    calls = []
    spells_page.spell_manager.add_listener(lambda: calls.append(1))
    spells = [spells_page.spell_manager.get_spell(f"{TAG} Spell {n}") for n in "ABC"]
    for s in spells:
        s.source = "Together"
    assert spells_page.spell_manager.update_spells([(s.name, s) for s in spells]) == 3
    assert len(calls) == 1
    assert spells_page.spell_manager.update_spells([("Zqx Not A Spell", spells[0])]) == 0


def test_add_spells_to_a_character_saves_once(tmp_path):
    from character import CharacterSpellList
    from character_manager import CharacterManager
    cm = CharacterManager(str(tmp_path / "characters.json"))
    cm.add_character(CharacterSpellList(name="Tester"))
    saves, notes = [], []
    original = cm.save_characters
    cm.save_characters = lambda: saves.append(1) or original()
    cm.add_listener(lambda: notes.append(1)) if hasattr(cm, "add_listener") else None
    assert cm.add_spells_to_character("Tester", ["Fireball", "Shield", "Fireball"]) == (2, 1)
    assert cm.add_spells_to_character("Tester", ["Shield"]) == (0, 1)
    assert cm.add_spells_to_character("Nobody", ["Shield"]) == (0, 0)
    assert len(saves) == 1                                         # nothing new, nothing saved


def test_add_spells_to_a_character_from_the_page(spells_page, monkeypatch):
    import ui.item_picker as picker
    from character import CharacterSpellList
    told = told_messages(monkeypatch)
    added = []
    character = CharacterSpellList(name="Tester")
    manager = SimpleNamespace(
        characters=[character], get_character=lambda n: character,
        add_spells_to_character=lambda name, names: (added.extend(names) or (len(names), 0)))
    monkeypatch.setattr(picker, "PickCharacterDialog", lambda parent, title, chars: SimpleNamespace(result="Tester"))
    spells_page.character_manager = manager
    spells_page._validate_spell_for_character = lambda spell, ch: []
    tick_spells(spells_page, "A", "B")
    spells_page.spell_list._bulk_buttons[0].invoke()
    assert sorted(added) == [f"{TAG} Spell A", f"{TAG} Spell B"]
    assert "Added 2 spells to Tester's spell list" in told[-1][1]


@pytest.mark.parametrize("choice, expected, message", [
    ("all", ["A", "B", "C"], "Added 3 spells"),
    ("clean", ["A", "C"], "1 with warnings left out"),
    (None, [], None),
])
def test_spells_with_warnings_ask_before_being_added(spells_page, monkeypatch, choice, expected, message):
    import ui.item_picker as picker
    from character import CharacterSpellList
    told = told_messages(monkeypatch)
    added = []
    character = CharacterSpellList(name="Tester")
    manager = SimpleNamespace(
        characters=[character], get_character=lambda n: character,
        add_spells_to_character=lambda name, names: (added.extend(names) or (len(names), 0)))
    monkeypatch.setattr(picker, "PickCharacterDialog", lambda parent, title, chars: SimpleNamespace(result="Tester"))
    spells_page.character_manager = manager
    spells_page._validate_spell_for_character = lambda spell, ch: ["too high a level"] if spell.name.endswith("B") else []
    asked = fake_dialog(monkeypatch, importlib.import_module("ui.spells_view"), "BulkWarningsDialog", choice)
    tick_spells(spells_page, "A", "B", "C")
    spells_page.spell_list._bulk_buttons[0].invoke()
    assert len(asked) == 1 and asked[0][1] == [(f"{TAG} Spell B", ["too high a level"])]
    assert sorted(added) == [f"{TAG} Spell {n}" for n in expected]
    if message:
        assert message in told[-1][1]
    else:
        assert told == []


# ================================================================== the dialogs

@pytest.fixture()
def parent(tk_root):
    return tk_root


def test_the_tags_dialog_collects_and_checks(parent, monkeypatch):
    from ui.bulk_actions import BulkTagsDialog
    warned = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: warned.append(a))
    dialog = BulkTagsDialog(parent, "Edit", ["a", "b"], ["b"])
    dialog._accept()
    assert dialog.result is None and "at least one" in warned[-1][1]
    dialog.add_editor.set_tags(["x"])
    dialog.remove_editor.set_tags(["X"])
    dialog._accept()
    assert dialog.result is None and "both lists" in warned[-1][1]
    dialog.remove_editor.set_tags(["y"])
    dialog._accept()
    assert dialog.result == (["x"], ["y"])


def test_the_source_dialog_wants_a_source(parent, monkeypatch):
    from ui.bulk_actions import BulkSourceDialog
    warned = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: warned.append(a))
    dialog = BulkSourceDialog(parent, "Set", ["Book A"])
    dialog._accept()
    assert dialog.result is None and warned
    dialog.source_var.set("  New Book ")
    dialog._accept()
    assert dialog.result == "New Book"


def test_the_classes_dialog_collects_and_checks(parent, monkeypatch):
    from ui.bulk_actions import BulkClassesDialog
    warned = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: warned.append(a))
    dialog = BulkClassesDialog(parent, "Edit", ["Bard", "Cleric", "Druid"])
    dialog._accept()
    assert dialog.result is None and "at least one" in warned[-1][1]
    dialog.add_vars["Bard"].set(True)
    dialog.remove_vars["Bard"].set(True)
    dialog._accept()
    assert dialog.result is None and "both columns" in warned[-1][1]
    dialog.remove_vars["Bard"].set(False)
    dialog.remove_vars["Druid"].set(True)
    dialog._accept()
    assert dialog.result == (["Bard"], ["Druid"])


def test_the_warnings_dialog_answers(parent):
    from ui.bulk_actions import BulkWarningsDialog
    dialog = BulkWarningsDialog(parent, "Some have warnings", [("Fireball", ["too high"])], 2)
    dialog._finish("clean")
    assert dialog.result == "clean"


# ================================================================== "Titles only"

TITLE_PAGES = {
    "feat": ("ui.feats_view", "FeatsView", lambda f: [f.plain_description()]),
    "equipment": ("ui.equipment_view", "EquipmentView", lambda i: [i.plain_description(), *i.tags]),
    "magic_item": ("ui.magic_item_view", "MagicItemView", lambda i: [i.plain_description(), *i.tags]),
    "lineage": ("ui.lineages_view", "LineagesView", lambda l: [t.name for t in l.traits]),
    "background": ("ui.backgrounds_view", "BackgroundsView", lambda b: [*b.skills, *b.feats]),
}


@pytest.fixture(params=list(TITLE_PAGES))
def title_page(request, tk_root):
    module, cls, texts = TITLE_PAGES[request.param]
    view = getattr(importlib.import_module(module), cls)(tk_root)
    view.pack(fill="both", expand=True)
    view._apply_filters()
    pump(tk_root)
    view.texts = texts
    yield view
    view.destroy()


def search(view, root, text, titles_only):
    view.titles_var.set(titles_only)
    view.search_var.set(text)
    view._apply_filters()
    pump(root)
    return [i.name for i in view.list_panel._items]


def a_word_only_in_the_text(view):
    """A word that some entry's searchable text has and no entry's name has, with the entry that has it."""
    names = " ".join(i.name.lower() for i in view.list_panel._items)
    for item in view.list_panel._items:
        for text in view.texts(item):
            for word in text.lower().replace(".", " ").replace(",", " ").split():
                if len(word) > 5 and word.isalpha() and word not in names:
                    return word, item.name
    raise AssertionError("no such word")


def test_titles_only_stops_the_search_looking_at_the_text(title_page, tk_root):
    word, owner = a_word_only_in_the_text(title_page)
    assert owner in search(title_page, tk_root, word, titles_only=False)
    assert search(title_page, tk_root, word, titles_only=True) == []


def test_titles_only_still_finds_names(title_page, tk_root):
    name = title_page.list_panel._items[3].name
    assert name in search(title_page, tk_root, name.lower(), titles_only=True)


def test_clearing_the_filters_unticks_titles_only(title_page, tk_root):
    title_page.titles_var.set(True)
    title_page._clear_filters()
    pump(tk_root, 20)
    assert title_page.titles_var.get() is False


def test_ticking_titles_only_refilters_at_once(title_page, tk_root):
    word, owner = a_word_only_in_the_text(title_page)
    title_page.search_var.set(word)
    pump(tk_root, 20)
    assert owner in [i.name for i in title_page.list_panel._items]
    title_page.titles_var.set(True)
    title_page._titles_check.invoke() if hasattr(title_page, "_titles_check") else None
    title_page._on_filter_changed(immediate=True)
    pump(tk_root, 20)
    assert [i.name for i in title_page.list_panel._items] == []


def test_titles_only_on_the_monster_page(tk_root):
    from ui.monster_view import MonsterView
    view = MonsterView(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    try:
        names = " ".join(m.name.lower() for m in view._all_monsters)
        word = next(w for blob in view._search_index.values() for w in blob.split()
                    if len(w) > 6 and w.isalpha() and w not in names)
        view.search_var.set(word)
        view.titles_var.set(False)
        view._apply_filters()
        assert view.list_panel._items
        view.titles_var.set(True)
        view._apply_filters()
        assert view.list_panel._items == []
        view._clear_filters()
        assert view.titles_var.get() is False
    finally:
        view.destroy()


def test_titles_only_on_the_spells_page(tk_root):
    view = make_spells_view(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    try:
        spells = view.spell_manager.spells
        names = " ".join(s.name.lower() for s in spells)
        word = next(w for s in spells for w in s.description.lower().split()
                    if len(w) > 6 and w.isalpha() and w not in names)
        view.search_var.set(word)
        view.titles_var.set(False)
        view._refresh_spell_list()
        assert view.spell_list._items
        view.titles_var.set(True)
        view._refresh_spell_list()
        assert view.spell_list._items == []
        view.search_var.set("fireb")
        view._refresh_spell_list()
        assert any(s.name.startswith("Fireball") for s in view.spell_list._items)
    finally:
        view.destroy()


def test_the_database_search_honours_titles_only():
    from database import SpellDatabase
    db = SpellDatabase()
    db.initialize()
    word = "hurl"
    anywhere = db.search_spells(search_text=word)
    in_names = db.search_spells(search_text=word, titles_only=True)
    assert len(anywhere) > len(in_names) and all(word in s["name"].lower() for s in in_names)
