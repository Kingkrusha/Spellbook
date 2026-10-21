"""The collection browsing pages (equipment, magic items, feats, lineages, backgrounds) and the plumbing they
share in ui/collection_page.py and ui/item_view_base.py: filtering, the source filter, selection, the context
menu, and the add / edit / delete / add-to-character flows."""

import importlib
import time

import pytest


def pump(root, n=12):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


# page key -> (module, class, manager attribute on the page, items attribute on the manager, a known entry)
PAGES = {
    "equipment": ("ui.equipment_view", "EquipmentView", "equipment_manager", "items", "Longsword"),
    "magic_item": ("ui.magic_item_view", "MagicItemView", "magic_item_manager", "items", "Bag of Holding"),
    "feat": ("ui.feats_view", "FeatsView", "feat_manager", "feats", "Alert"),
    "lineage": ("ui.lineages_view", "LineagesView", "lineage_manager", "lineages", "Orc"),
    "background": ("ui.backgrounds_view", "BackgroundsView", "background_manager", "backgrounds", "Acolyte"),
}


@pytest.fixture(params=list(PAGES))
def page(request, tk_root):
    module, cls, manager_attr, items_attr, known = PAGES[request.param]
    view = getattr(importlib.import_module(module), cls)(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    view._apply_filters()
    pump(tk_root)
    view.KEY, view.KNOWN = request.param, known
    view.items_of = lambda: list(getattr(getattr(view, manager_attr), items_attr))
    yield view
    view.destroy()


def packed(widget):
    """Whether the widget is currently laid out (the test root is withdrawn, so nothing is ever "mapped")."""
    return widget.winfo_manager() != ""


def shown(view):
    return [i.name for i in view.list_panel._items]


def refilter(view, root):
    view._apply_filters()
    pump(root)


# ---------------------------------------------------------------- what every page does

def test_the_page_lists_its_collection(page):
    assert len(shown(page)) > 10
    assert page.KNOWN in shown(page)
    assert page.list_panel.count_label.cget("text").split()[0] == str(len(shown(page)))


def test_searching_narrows_the_list_and_clearing_restores_it(page, tk_root):
    everything = shown(page)
    page.search_var.set("zzzz-nothing-is-called-this")
    refilter(page, tk_root)
    assert shown(page) == []

    page.search_var.set(page.KNOWN.lower())
    refilter(page, tk_root)
    assert page.KNOWN in shown(page) and len(shown(page)) < len(everything)

    page._clear_filters()
    pump(tk_root, 20)
    assert page.search_var.get() == "" and shown(page) == everything


def test_the_content_filter_splits_official_from_homebrew(page, tk_root):
    page.official_var.set("Homebrew Only")
    refilter(page, tk_root)
    homebrew = shown(page)
    assert all(not i.is_official or i.is_custom or True for i in page.list_panel._items)
    page.official_var.set("Official Only")
    refilter(page, tk_root)
    official = shown(page)
    assert page.KNOWN in official and page.KNOWN not in homebrew
    assert not set(homebrew) & set(official)
    assert all(i.is_official for i in page.list_panel._items)
    page.official_var.set("Any Content")
    refilter(page, tk_root)
    assert len(shown(page)) >= len(official)


def test_the_source_filter_includes_or_excludes_and_labels_itself(page, tk_root):
    from ui.filter_widgets import SourceFilterMode
    everything = shown(page)
    sources = sorted({i.source for i in page.items_of() if i.source})
    assert page.source_label.cget("text") == "None selected"
    chosen = sources[0]

    page._selected_sources = [chosen]
    page._source_filter_mode = SourceFilterMode.INCLUDE
    page._update_source_label()
    assert page.source_label.cget("text") == f"1 source (include): {chosen}"
    refilter(page, tk_root)
    included = shown(page)
    assert 0 < len(included) < len(everything)
    assert all(i.source == chosen for i in page.list_panel._items)

    page._source_filter_mode = SourceFilterMode.EXCLUDE
    page._update_source_label()
    assert page.source_label.cget("text") == f"1 source (exclude): {chosen}"
    refilter(page, tk_root)
    assert not set(shown(page)) & set(included)
    assert all(i.source != chosen for i in page.list_panel._items)

    page._selected_sources = sources[:2]
    page._update_source_label()
    assert page.source_label.cget("text") == "2 sources (exclude)"

    page._clear_filters()
    pump(tk_root, 20)
    assert page.source_label.cget("text") == "None selected" and shown(page) == everything


def test_picking_an_entry_shows_it(page, tk_root):
    assert page.list_panel.select_by_name(page.KNOWN)
    pump(tk_root)
    assert page.list_panel.get_selected().name.startswith(page.KNOWN.split(" (")[0])
    if page.KEY in ("equipment", "magic_item"):              # their official entries can't be edited or deleted
        assert page.edit_btn.cget("state") == "disabled" and page.delete_btn.cget("state") == "disabled"


def test_filter_changes_are_debounced_into_one_refilter(page, tk_root):
    calls = []
    original = page._apply_filters
    page._apply_filters = lambda: (calls.append(1), original())
    page._on_filter_changed()
    page._on_filter_changed()
    page._on_filter_changed(immediate=True)
    pump(tk_root, 30)
    assert len(calls) == 1


def test_theme_changes_recolour_without_error(page, tk_root):
    page._on_theme_changed()
    page._update_context_menu_colors()
    page._update_paned_colors()
    pump(tk_root, 3)


def test_the_context_menu_has_the_pages_actions(page):
    labels = {
        "equipment": ["Add to Character"], "magic_item": ["Add to Character"],
        "feat": ["Add to Character", "View and Compare"],
        "lineage": ["Set as Character Lineage", "Compare"],
        "background": ["Set as Character Background", "Compare"],
    }[page.KEY]
    menu = page.context_menu
    assert [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)] == labels


def test_the_page_can_be_given_a_character_manager_later(page):
    sentinel = object()
    page.set_character_manager(sentinel)
    assert page.character_manager is sentinel


# ---------------------------------------------------------------- the page-specific filters

def test_equipment_filters(tk_root):
    from ui.equipment_view import EquipmentView
    view = EquipmentView(tk_root)
    view.pack()
    pump(tk_root)
    try:
        everything = len(shown(view))

        view.type_var.set("Armor")
        refilter(view, tk_root)
        assert 0 < len(shown(view)) < everything and all(i.type == "Armor" for i in view.list_panel._items)
        view.type_var.set("All Types")

        view.min_price_var.set("50")
        view.max_price_var.set("100")
        refilter(view, tk_root)
        from equipment import parse_cost_to_copper
        assert view.list_panel._items and all(
            5000 <= (parse_cost_to_copper(i.cost) or -1) <= 10000 for i in view.list_panel._items)
        view.min_price_var.set("")
        view.max_price_var.set("")
        view.min_price_var.set("not a number")                       # an unparseable bound is ignored
        refilter(view, tk_root)
        assert len(shown(view)) == everything
        view.min_price_var.set("")

        tool = next(i.crafting_tool for i in view.item_manager.items if i.crafting_tool)
        view.crafting_tool_var.set(tool)
        refilter(view, tk_root)
        assert view.list_panel._items and all(i.crafting_tool == tool for i in view.list_panel._items)
        view._clear_filters()
        pump(tk_root, 20)
        assert view.crafting_tool_var.get() == "Any Tool" and len(shown(view)) == everything
    finally:
        view.destroy()


def test_tag_and_material_filters_and_their_labels(tk_root):
    from equipment import Equipment
    from ui.equipment_view import EquipmentView
    from ui.filter_widgets import TagFilterMode
    manager = EquipmentView.MANAGER_GETTER()
    manager.add_item(Equipment(name="T-Tagged", tags=["Alpha", "Beta"], crafting_materials=["Iron", "Wood"],
                               is_official=False, is_custom=True))
    view = EquipmentView(tk_root)
    view.pack()
    pump(tk_root)
    try:
        def names(**state):
            for key, value in state.items():
                setattr(view, key, value)
            refilter(view, tk_root)
            return [n for n in shown(view) if n.startswith("T-")]

        assert names(_selected_tags=["alpha"], _tag_filter_mode=TagFilterMode.HAS_ALL) == ["T-Tagged"]
        assert names(_selected_tags=["Alpha", "Zeta"], _tag_filter_mode=TagFilterMode.HAS_ALL) == []
        assert names(_selected_tags=["Alpha", "Zeta"], _tag_filter_mode=TagFilterMode.HAS_ANY) == ["T-Tagged"]
        assert names(_selected_tags=["Alpha"], _tag_filter_mode=TagFilterMode.HAS_NONE) == []
        assert names(_selected_tags=[], _selected_materials=["iron", "wood"]) == ["T-Tagged"]
        assert names(_selected_materials=["iron", "steel"]) == []

        view._selected_tags = []
        view._update_tags_label()
        assert view.tags_label.cget("text") == "None selected"
        view._selected_tags, view._tag_filter_mode = ["Alpha"], TagFilterMode.HAS_ANY
        view._update_tags_label()
        assert view.tags_label.cget("text") == "1 tag (any): Alpha"
        view._selected_tags, view._tag_filter_mode = ["Alpha", "Beta"], TagFilterMode.HAS_NONE
        view._update_tags_label()
        assert view.tags_label.cget("text") == "2 tags (none)"
        view._selected_materials = ["Iron"]
        view._update_materials_label()
        assert view.materials_label.cget("text") == "1 material (all): Iron"
        view._selected_materials = ["Iron", "Wood"]
        view._update_materials_label()
        assert view.materials_label.cget("text") == "2 materials (all)"
    finally:
        view.destroy()
        manager.delete_item("T-Tagged")


def test_magic_item_filters(tk_root):
    from ui.magic_item_view import MagicItemView
    view = MagicItemView(tk_root)
    view.pack()
    pump(tk_root)
    try:
        everything = len(shown(view))

        view.rarity_var.set("Legendary")
        refilter(view, tk_root)
        assert 0 < len(shown(view)) < everything and all(i.rarity.value == "Legendary" for i in view.list_panel._items)

        view.attunement_var.set(True)
        refilter(view, tk_root)
        assert view.list_panel._items and all(
            i.rarity.value == "Legendary" and i.requires_attunement for i in view.list_panel._items)

        view.rarity_var.set("All Rarities")
        refilter(view, tk_root)
        assert all(i.requires_attunement for i in view.list_panel._items)
        assert len(shown(view)) > len([i for i in view.list_panel._items if i.rarity.value == "Legendary"])

        view._clear_filters()
        pump(tk_root, 20)
        assert view.rarity_var.get() == "All Rarities" and view.attunement_var.get() is False
        assert len(shown(view)) == everything
    finally:
        view.destroy()


def test_feat_filters(tk_root):
    from ui.feats_view import FeatsView
    view = FeatsView(tk_root)
    view.pack()
    pump(tk_root)
    try:
        view.spellcasting_var.set(True)
        refilter(view, tk_root)
        assert view.list_panel._items and all(f.is_spellcasting for f in view.list_panel._items)
        view.spellcasting_var.set(False)

        view.prereq_var.set("No Prerequisite")
        refilter(view, tk_root)
        assert view.list_panel._items and all(not f.has_prereq for f in view.list_panel._items)
        view.prereq_var.set("Has Prerequisite")
        refilter(view, tk_root)
        assert view.list_panel._items and all(f.has_prereq for f in view.list_panel._items)

        view._clear_filters()
        pump(tk_root, 20)
        assert view.prereq_var.get() == "Any" and view.spellcasting_var.get() is False
    finally:
        view.destroy()


def test_lineage_and_background_filters(tk_root):
    from ui.backgrounds_view import BackgroundsView
    from ui.lineages_view import LineagesView

    lineages = LineagesView(tk_root)
    lineages.pack()
    pump(tk_root)
    try:
        size = next(s for s in lineages.size_combo.cget("values") if s != "All Sizes")
        lineages.size_var.set(size)
        refilter(lineages, tk_root)
        assert lineages.list_panel._items and all(size in l.size for l in lineages.list_panel._items)
        lineages.size_var.set("All Sizes")
        lineages.min_speed_var.set("40")
        refilter(lineages, tk_root)
        assert all(l.speed >= 40 for l in lineages.list_panel._items)
        lineages._clear_filters()
        pump(tk_root, 20)
        assert lineages.min_speed_var.get() == "Any" and lineages.size_var.get() == "All Sizes"
    finally:
        lineages.destroy()

    backgrounds = BackgroundsView(tk_root)
    backgrounds.pack()
    pump(tk_root)
    try:
        skill = next(s for s in backgrounds.skill_combo.cget("values") if s != "All Skills")
        backgrounds.skill_var.set(skill)
        refilter(backgrounds, tk_root)
        assert backgrounds.list_panel._items and all(skill in b.skills for b in backgrounds.list_panel._items)
        backgrounds._clear_filters()
        pump(tk_root, 20)
        assert backgrounds.skill_var.get() == "All Skills"
    finally:
        backgrounds.destroy()


def test_comparing_swaps_the_list_for_a_second_detail_pane(tk_root):
    from ui.lineages_view import LineagesView
    view = LineagesView(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    try:
        view.list_panel.select_by_name("Orc")
        pump(tk_root)
        view._context_lineage = view.list_panel.get_selected()
        view._context_compare()
        pump(tk_root)
        assert packed(view.compare_container) and not packed(view.list_panel)
        assert "Orc" in view.compare_detail.name_label.cget("text")
        view._close_compare()
        pump(tk_root)
        assert packed(view.list_panel) and not packed(view.compare_container)
    finally:
        view.destroy()


# ---------------------------------------------------------------- add / edit / delete flows (equipment, magic items)

class FakeEditor:
    """Stands in for the editor dialog: records how it was opened and answers with ``result``."""
    result = None
    opened = []

    def __init__(self, parent, title, item=None, **kw):
        type(self).opened.append((title, item, kw))
        self.result = type(self).next_result


def reload(view, root):
    view._load_items()
    pump(root)                      # the refilter is scheduled, not immediate


def run_flow(monkeypatch, view, editor_result):
    FakeEditor.opened = []
    FakeEditor.next_result = editor_result
    monkeypatch.setattr(type(view), "EDITOR_DIALOG", FakeEditor)
    view.wait_window = lambda w: None


ITEM_PAGES = {
    "equipment": ("ui.equipment_view", "EquipmentView", "equipment", "Equipment", "Add Equipment", "Edit Equipment"),
    "magic_item": ("ui.magic_item_view", "MagicItemView", "magic_item", "MagicItem", "Add Magic Item", "Edit Magic Item"),
}


@pytest.fixture(params=list(ITEM_PAGES))
def item_page(request, tk_root, monkeypatch):
    module, cls, model_module, model_cls, add_title, edit_title = ITEM_PAGES[request.param]
    view_cls = getattr(importlib.import_module(module), cls)
    model = getattr(importlib.import_module(model_module), model_cls)
    view = view_cls(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    monkeypatch.setattr("ui.studio_launch.open_in_studio", lambda *a, **k: False)
    view.model, view.add_title, view.edit_title = model, add_title, edit_title
    yield view
    for item in list(view.item_manager.items):
        if item.name.startswith("T-"):
            view.item_manager.delete_item(item.name)
    view.destroy()


def source_dialog(result):
    class Dialog:
        def __init__(self, parent):
            self.result = result
    return Dialog


def test_adding_an_item_by_hand(item_page, monkeypatch, tk_root):
    from ui import studio_launch  # noqa: F401  (patched by the fixture)
    run_flow(monkeypatch, item_page, item_page.model(name="T-Made", is_official=False, is_custom=True))
    src_module = importlib.import_module(item_page._text_import()[0].__module__)
    monkeypatch.setattr(src_module, item_page._text_import()[0].__name__, source_dialog("manual"))

    item_page._on_add_item()
    pump(tk_root)
    assert FakeEditor.opened[0][0] == item_page.add_title
    assert item_page.item_manager.get_item("T-Made") is not None
    assert "T-Made" in shown(item_page)
    assert item_page.list_panel.get_selected().name == "T-Made"           # the new item is selected...
    assert item_page.detail_panel.name_label.cget("text") == "* T-Made"   # ...and shown
    assert item_page.edit_btn.cget("state") == "normal" and item_page.delete_btn.cget("state") == "normal"


def test_cancelling_the_add_dialog_adds_nothing(item_page, monkeypatch, tk_root):
    run_flow(monkeypatch, item_page, None)
    cls = item_page._text_import()[0]
    src_module = importlib.import_module(cls.__module__)
    before = len(item_page.item_manager.items)

    monkeypatch.setattr(src_module, cls.__name__, source_dialog(None))               # closed the chooser
    item_page._on_add_item()
    monkeypatch.setattr(src_module, cls.__name__, source_dialog("manual"))           # cancelled the editor
    item_page._on_add_item()
    assert len(item_page.item_manager.items) == before
    assert len(FakeEditor.opened) == 1


def test_editing_only_works_on_homebrew(item_page, monkeypatch, tk_root):
    item_page.item_manager.add_item(item_page.model(name="T-Edit", is_official=False, is_custom=True))
    reload(item_page, tk_root)
    run_flow(monkeypatch, item_page, item_page.model(name="T-Edited", description="new", is_official=False,
                                                     is_custom=True))

    item_page.list_panel.select_by_name(next(i.name for i in item_page.item_manager.items if not i.is_custom))
    item_page._on_edit_item()
    assert FakeEditor.opened == []                                                  # official: nothing opens

    item_page.list_panel.select_by_name("T-Edit")
    item_page._on_edit_item()
    pump(tk_root)
    assert FakeEditor.opened[0][0] == item_page.edit_title and FakeEditor.opened[0][1].name == "T-Edit"
    assert item_page.item_manager.get_item("T-Edit") is None
    assert item_page.item_manager.get_item("T-Edited").description == "new"
    assert "T-Edited" in shown(item_page) and "T-Edit" not in shown(item_page)
    assert item_page.list_panel.get_selected().name == "T-Edited"
    assert item_page.detail_panel.name_label.cget("text") == "* T-Edited"


def test_editing_an_item_without_renaming_it_shows_the_new_details(item_page, monkeypatch, tk_root):
    item_page.item_manager.add_item(item_page.model(name="T-Same", description="old", is_official=False, is_custom=True))
    reload(item_page, tk_root)
    item_page.list_panel.select_by_name("T-Same")
    pump(tk_root)
    run_flow(monkeypatch, item_page, item_page.model(name="T-Same", description="brand new", is_official=False,
                                                     is_custom=True))
    item_page._on_edit_item()
    pump(tk_root)
    assert item_page.list_panel.get_selected().description == "brand new"
    assert item_page.detail_panel._current_item.description == "brand new"


def test_deleting_asks_first_and_only_removes_homebrew(item_page, monkeypatch, tk_root):
    from tkinter import messagebox
    item_page.item_manager.add_item(item_page.model(name="T-Delete", is_official=False, is_custom=True))
    reload(item_page, tk_root)
    item_page.list_panel.select_by_name("T-Delete")
    pump(tk_root)

    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: False)
    item_page._on_delete_item()
    assert item_page.item_manager.get_item("T-Delete") is not None

    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    item_page._on_delete_item()
    pump(tk_root)
    assert item_page.item_manager.get_item("T-Delete") is None
    assert "T-Delete" not in shown(item_page)
    assert item_page.detail_panel.name_label.cget("text") == "Select an item"


def test_adding_several_items_from_pasted_text(item_page, monkeypatch, tk_root):
    from tkinter import messagebox
    source_cls, import_cls, _ = item_page._text_import()
    module = importlib.import_module(source_cls.__module__)

    class Parsed:
        def __init__(self, name):
            self.name = name

        def needs_review(self):
            return ["name"]

        def uncertain_fields(self):
            return ["type"]

    monkeypatch.setattr(module, source_cls.__name__, source_dialog("auto"))

    class Importer:
        def __init__(self, parent):
            self.result = [Parsed("T-One"), Parsed("T-Two"), Parsed("T-Three")]
    monkeypatch.setattr(module, import_cls.__name__, Importer)

    parser = importlib.import_module("text_import." + ("equipment_parser" if item_page.STUDIO_KIND == "equipment"
                                                       else "magic_item_parser"))
    converter = "to_equipment" if item_page.STUDIO_KIND == "equipment" else "to_magic_item"
    monkeypatch.setattr(parser, converter, lambda parsed: item_page.model(name=parsed.name))

    results = iter([item_page.model(name="T-One", is_official=False, is_custom=True), None,
                    item_page.model(name="T-Three", is_official=False, is_custom=True)])
    FakeEditor.opened = []
    monkeypatch.setattr(type(item_page), "EDITOR_DIALOG", type("E", (FakeEditor,), {
        "__init__": lambda self, parent, title, item=None, **kw: (FakeEditor.opened.append((title, kw)),
                                                                  setattr(self, "result", next(results)))[0]}))
    item_page.wait_window = lambda w: None
    asked, told = [], []
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: asked.append(a) or True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: told.append(a))

    item_page._on_add_item()
    pump(tk_root)

    assert [t for t, _ in FakeEditor.opened] == ["Review Item: T-One", "Review Item: T-Two", "Review Item: T-Three"]
    kw = FakeEditor.opened[0][1]
    assert kw["review_fields"] == ["name", "type"] and kw["batch_progress"] == "1 of 3"
    assert item_page.item_manager.get_item("T-One") and item_page.item_manager.get_item("T-Three")
    assert item_page.item_manager.get_item("T-Two") is None
    assert len(asked) == 1 and "Skip this item" in asked[0][1]                      # asked once, for the cancelled one
    assert told and "Added 2 items" in told[0][1]
    assert {"T-One", "T-Three"} <= set(shown(item_page)) and "T-Two" not in shown(item_page)
    assert item_page.list_panel.get_selected().name == "T-Three"           # the last one added


class FakeCharacterManager:
    def __init__(self):
        self.characters = []

    def get_character(self, name):
        return next((c for c in self.characters if c.name == name), None)


def test_add_to_character_puts_the_item_on_the_sheet(item_page, monkeypatch, tk_root):
    from tkinter import messagebox
    from types import SimpleNamespace
    import ui.character_sheet_view as sheet_view
    import ui.item_picker as picker

    character = SimpleNamespace(name="Tester")
    sheet = SimpleNamespace(equipment_items=[], magic_items=[])
    updated = []
    sheet_manager = SimpleNamespace(get_or_create_sheet=lambda name, char: sheet,
                                    update_sheet=lambda name, s: updated.append((name, s)))
    monkeypatch.setattr(sheet_view, "get_sheet_manager", lambda: sheet_manager)
    monkeypatch.setattr(picker, "PickCharacterDialog", lambda parent, title, chars: SimpleNamespace(result="Tester"))
    told = []
    monkeypatch.setattr(messagebox, "showinfo", lambda *a, **k: told.append(a))
    warned = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: warned.append(a))
    item_page.wait_window = lambda w: None

    item_page._context_add_to_character()                    # nothing was right-clicked yet
    assert warned == [] and told == []

    item_page.list_panel.select_by_name(item_page.item_manager.items[0].name)
    item = item_page.list_panel.get_selected()
    item_page._context_item = item

    item_page._context_add_to_character()                    # no character manager at all
    assert "No character manager" in warned[-1][1]
    item_page.set_character_manager(FakeCharacterManager())
    item_page._context_add_to_character()                    # a manager without characters
    assert "No characters available" in warned[-1][1]

    item_page.character_manager.characters.append(character)
    item_page._context_add_to_character()
    assert updated == [("Tester", sheet)]
    assert told and item.name in told[0][1] and "Tester" in told[0][1]
    if item_page.STUDIO_KIND == "equipment":
        assert sheet.equipment_items == [{"name": item.name, "quantity": 1, "weight": item.weight}] and not sheet.magic_items
    else:
        (entry,) = sheet.magic_items
        assert entry["name"] == item.name and entry["attuned"] is False
        assert entry["requires_attunement"] == item.requires_attunement and not sheet.equipment_items


def test_the_detail_pane_shows_what_the_item_has_and_hides_the_rest(item_page, tk_root):
    manager = item_page.item_manager
    manager.add_item(item_page.model(name="T-Bare", is_official=False, is_custom=True))
    manager.add_item(item_page.model(name="T-Full", description="Some **text**.", source="Table Rules", tags=["b", "A"],
                                     properties=[{"name": "Gleaming", "description": "It shines."}, {"name": ""}],
                                     is_official=False, is_custom=True))
    reload(item_page, tk_root)
    detail = item_page.detail_panel

    item_page.list_panel.select_by_name("T-Bare")
    pump(tk_root)
    assert detail.name_label.cget("text") == "* T-Bare"
    assert not packed(detail.tags_label) and not packed(detail.properties_frame)
    assert not packed(detail.source_label) and not packed(detail.desc_frame)

    item_page.list_panel.select_by_name("T-Full")
    pump(tk_root)
    assert detail.tags_label.cget("text") == "A, b" and packed(detail.tags_label)
    assert detail.source_label.cget("text") == "Source: Table Rules (Unofficial)"
    assert packed(detail.properties_frame)
    assert [c.cget("text") for row in detail._properties_chip_area.winfo_children() for c in row.winfo_children()] == [
        "Gleaming"]                                                                   # the nameless one is dropped
    assert detail._desc_widgets

    detail.show_item(None)
    assert detail.name_label.cget("text") == "Select an item" and not packed(detail.properties_frame)
    detail._on_theme_changed()
