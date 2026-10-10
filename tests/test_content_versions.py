"""Several versions of one thing shown as one entry (content_versions.py) and the Source drop-down."""

from types import SimpleNamespace as NS

import pytest

from content_versions import (VersionCatalog, collapse_search_results, display_name, version_label,
                              visible_in)


def item(name, source, legacy, official=True):
    return NS(name=name, source=source, is_legacy=legacy, is_official=official)


@pytest.fixture()
def orcs():
    return [
        item("Orc", "Players Handbook (2024)", False),
        item("Orc (Legacy: VGM)", "Volo's Guide to Monsters", True),
        item("Orc (Legacy: MPMM)", "Mordenkainen Presents: Monsters of the Multiverse", True),
        item("Orc (Legacy: ERLW)", "Eberron - Rising from the Last War", True),
        item("Fireball", "Player's Handbook (2024)", False),
        item("Fireball (Legacy)", "Player's Handbook (2014)", True),
        item("Aarakocra (Legacy: EEPC)", "Elemental Evil Player's Companion", True),
        item("Aarakocra (Legacy: MPMM)", "Mordenkainen Presents: Monsters of the Multiverse", True),
        item("Branding Smite", "Player's Handbook (2014)", True),
    ]


def names(items):
    return [i.name for i in items]


def test_display_name_drops_the_version_tag():
    assert display_name("Fireball (Legacy)") == "Fireball"
    assert display_name("Orc (Legacy: MPMM)") == "Orc"
    assert display_name("Fireball (Legacy)*") == "Fireball*"      # modified-spell asterisk is kept
    assert display_name("Hill Dwarf") == "Hill Dwarf"
    assert display_name("Dwarf (Mark of Warding)") == "Dwarf (Mark of Warding)"


def test_version_label_is_the_source_flagged_when_legacy_or_unofficial():
    assert version_label(item("x", "Player's Handbook (2024)", False)) == "Player's Handbook (2024)"
    assert version_label(item("x", "Player's Handbook (2014)", True)) == "Player's Handbook (2014) [Legacy]"
    assert version_label(item("x", "Mine", False, official=False)) == "Mine (Unofficial)"


def test_versions_are_ordered_2024_first_then_newest_printing(orcs):
    catalog = VersionCatalog(orcs)
    assert names(catalog.versions(orcs[0])) == ["Orc", "Orc (Legacy: MPMM)", "Orc (Legacy: ERLW)", "Orc (Legacy: VGM)"]
    # a name belonging to any version finds the same group
    assert names(catalog.versions(orcs[3])) == names(catalog.versions(orcs[0]))
    assert names(catalog.versions(orcs[6])) == ["Aarakocra (Legacy: MPMM)", "Aarakocra (Legacy: EEPC)"]


@pytest.mark.parametrize("setting, expected", [
    ("show_all", ["Orc", "Orc (Legacy: MPMM)", "Orc (Legacy: ERLW)", "Orc (Legacy: VGM)"]),
    ("no_legacy", ["Orc"]),
    ("legacy_only", ["Orc (Legacy: MPMM)", "Orc (Legacy: ERLW)", "Orc (Legacy: VGM)"]),
    ("show_unupdated", ["Orc"]),
])
def test_the_legacy_setting_decides_which_versions_are_offered(orcs, setting, expected):
    shown = orcs[2] if setting == "legacy_only" else orcs[0]        # (the version on show is always offered)
    assert names(VersionCatalog(orcs).options(shown, setting)) == expected


def test_a_legacy_only_entry_keeps_its_versions_under_show_unupdated(orcs):
    catalog = VersionCatalog(orcs)
    assert names(catalog.options(orcs[6], "show_unupdated")) == ["Aarakocra (Legacy: MPMM)", "Aarakocra (Legacy: EEPC)"]
    assert names(catalog.options(orcs[8], "show_unupdated")) == ["Branding Smite"]


def test_options_always_include_the_item_being_shown(orcs):
    """A link can open a legacy version while the setting hides legacy content."""
    catalog = VersionCatalog(orcs)
    assert names(catalog.options(orcs[1], "no_legacy")) == ["Orc", "Orc (Legacy: VGM)"]


def test_the_list_has_one_entry_per_thing(orcs):
    catalog = VersionCatalog(orcs)
    assert names(catalog.collapse(orcs, "show_all")) == ["Orc", "Fireball", "Aarakocra (Legacy: MPMM)", "Branding Smite"]
    assert names(catalog.collapse(orcs, "no_legacy")) == ["Orc", "Fireball"]
    assert names(catalog.collapse(orcs, "legacy_only")) == [
        "Orc (Legacy: MPMM)", "Fireball (Legacy)", "Aarakocra (Legacy: MPMM)", "Branding Smite"]
    assert names(catalog.collapse(orcs, "show_unupdated")) == ["Orc", "Fireball", "Aarakocra (Legacy: MPMM)", "Branding Smite"]


def test_collapse_represents_an_entry_by_a_version_that_matched(orcs):
    """A search that only the 2014 printing satisfies still lists the entry (by that printing)."""
    catalog = VersionCatalog(orcs)
    only_vgm = [orcs[1]]
    assert names(catalog.collapse(only_vgm, "show_all")) == ["Orc (Legacy: VGM)"]
    # ...unless the setting hides that version
    assert catalog.collapse(only_vgm, "show_unupdated") == []
    assert catalog.collapse(only_vgm, "no_legacy") == []


def test_equal_copies_count_as_the_same_item(orcs):
    """The spell list is rebuilt from the database on every search; those copies must still group."""
    catalog = VersionCatalog(orcs)
    fresh = [item("Fireball (Legacy)", "Player's Handbook (2014)", True)]
    assert names(catalog.collapse(fresh, "show_all")) == ["Fireball (Legacy)"]
    assert names(catalog.options(fresh[0], "show_all")) == ["Fireball", "Fireball (Legacy)"]


def test_find_by_exact_name(orcs):
    catalog = VersionCatalog(orcs)
    assert catalog.find("orc (legacy: vgm)") is orcs[1]
    assert catalog.find("Nothing") is None


def test_visible_in_helper():
    versions = [item("A", "s", False), item("A (Legacy)", "s", True)]
    legacy = lambda i: i.is_legacy  # noqa: E731
    assert len(visible_in(versions, "show_all", legacy)) == 2
    assert [v.name for v in visible_in(versions, "show_unupdated", legacy)] == ["A"]


def test_global_search_shows_one_hit_per_thing():
    hits = [{"name": "Fireball (Legacy)", "section": "Spells", "id": 2},
            {"name": "Fireball", "section": "Spells", "id": 1},
            {"name": "Orc (Legacy: MPMM)", "section": "Lineages", "id": 3},
            {"name": "Orc (Legacy: VGM)", "section": "Lineages", "id": 4},
            {"name": "Fireball", "section": "Feats", "id": 5},
            {"name": "Champion (Fighter)", "section": "Subclasses", "id": 6},
            {"name": "Champion (Legacy) (Fighter (Legacy))", "section": "Subclasses", "id": 7}]
    out = collapse_search_results(hits)
    assert [(h["name"], h["label"]) for h in out] == [
        ("Fireball", "Fireball"),                       # the plain-named version wins
        ("Orc (Legacy: MPMM)", "Orc"),
        ("Fireball", "Fireball"),                       # same name, other section: separate hit
        ("Champion (Fighter)", "Champion (Fighter)"),
        ("Champion (Legacy) (Fighter (Legacy))", "Champion (Legacy) (Fighter (Legacy))"),
    ]


# ------------------------------------------------------------------ the drop-down in the real views

@pytest.fixture(scope="module")
def tk_root():
    import tkinter as tk
    import customtkinter as ctk
    try:
        root = ctk.CTk()
    except tk.TclError as e:
        pytest.skip(f"no display available ({e})")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture()
def legacy_setting():
    from settings import get_settings_manager
    settings = get_settings_manager().settings
    saved = settings.legacy_content_filter

    def set_to(mode):
        settings.legacy_content_filter = mode
    yield set_to
    settings.legacy_content_filter = saved


def pump(root, n=30):
    for _ in range(n):
        root.update()


def test_version_bar_plain_then_drop_down(tk_root):
    from ui.version_bar import VersionBar
    picked = []
    bar = VersionBar(tk_root, text="Source: Somewhere", on_select=picked.append)
    bar.pack()
    pump(tk_root, 5)
    assert not bar.has_versions()
    versions = [item("A", "Player's Handbook (2024)", False), item("A (Legacy)", "Player's Handbook (2014)", True)]
    bar.set_versions(versions, versions[1])
    assert bar.has_versions() and bar.current_label() == "Player's Handbook (2014) [Legacy]"
    bar._picked("Player's Handbook (2024)")
    assert picked == [versions[0]]
    bar.configure(text="Source: Elsewhere")                    # back to a plain line
    assert not bar.has_versions()
    bar.destroy()


def test_spell_row_and_detail_use_one_entry_with_a_version_drop_down(tk_root, legacy_setting):
    from character_manager import CharacterManager
    from settings import get_settings_manager
    from spell_manager import SpellManager
    from ui.spells_view import SpellsView
    import tempfile, os

    manager = SpellManager()
    assert manager.load_spells()
    characters = CharacterManager(os.path.join(tempfile.mkdtemp(), "characters.json"))
    legacy_setting("show_all")
    view = SpellsView(tk_root, manager, characters, get_settings_manager())
    view.pack(fill="both", expand=True)
    pump(tk_root)
    view._refresh_spell_list()
    listed = [s.name for s in view.spell_list._spells]
    assert "Fireball" in listed and "Fireball (Legacy)" not in listed
    assert "Branding Smite" in listed                            # 2014-only spells are still listed

    assert view.spell_list.select_spell("Fireball (Legacy)", manager.version_catalog.find("Fireball (Legacy)"))
    pump(tk_root)
    bar = view.spell_detail.source_label
    assert view.spell_detail.name_label.cget("text") == "FIREBALL"
    assert bar.has_versions() and bar.current_label() == "Player's Handbook (2014) [Legacy]"
    assert view.spell_detail._current_spell.name == "Fireball (Legacy)"

    bar._picked("Player's Handbook (2024)")
    pump(tk_root)
    assert view.spell_detail._current_spell.name == "Fireball"
    assert view.spell_list.get_selected_spell().name == "Fireball"    # actions use the version on show

    legacy_setting("no_legacy")
    view._refresh_spell_list()
    assert "Branding Smite" not in [s.name for s in view.spell_list._spells]
    view.destroy()


def test_lineage_feat_and_background_views(tk_root, legacy_setting):
    from ui.backgrounds_view import BackgroundsView
    from ui.feats_view import FeatsView
    from ui.lineages_view import LineagesView

    legacy_setting("show_all")
    for view_class, select, picked, name, exact, versions in (
            (LineagesView, "select_lineage", "get_selected_lineage", "Orc", "Orc (Legacy: VGM)", 3),
            (FeatsView, "select_feat", "get_selected_feat", "Alert", "Alert (Legacy)", 2),
            (BackgroundsView, "select_background", "get_selected_background", "Acolyte", "Acolyte (Legacy)", 2)):
        view = view_class(tk_root)
        view.pack(fill="both", expand=True)
        pump(tk_root)
        view._apply_filters()
        pump(tk_root)
        shown = [x.name for x in (getattr(view, "_filtered_" + {"LineagesView": "lineages", "FeatsView": "feats",
                                                               "BackgroundsView": "backgrounds"}[view_class.__name__]))]
        assert name in shown and exact not in shown, view_class.__name__
        assert getattr(view, select)(exact)
        pump(tk_root)
        bar = view.detail_panel.source_label
        assert bar.has_versions() and len(bar._labels) >= versions, view_class.__name__
        assert getattr(view.list_panel, picked)().name == exact
        bar._picked(bar._labels[0])                                 # the 2024 version
        pump(tk_root)
        assert getattr(view.list_panel, picked)().name == name
        view.destroy()


def test_class_page_has_a_version_drop_down(tk_root, legacy_setting):
    from ui.classes_view import ClassesCollectionView
    from ui.version_bar import VersionBar

    legacy_setting("show_all")
    view = ClassesCollectionView(tk_root)
    view.pack(fill="both", expand=True)
    pump(tk_root)
    listed = [c.name for c in view._get_filtered_classes()]
    assert "Fighter" in listed and "Fighter (Legacy)" not in listed
    view._select_class("Fighter")
    pump(tk_root, 60)
    bars = []

    def walk(widget):
        if isinstance(widget, VersionBar):
            bars.append(widget)
        for child in widget.winfo_children():
            walk(child)
    walk(view.content)
    assert bars and bars[0].has_versions()
    bars[0]._picked(bars[0]._labels[1])
    pump(tk_root, 60)
    assert view.current_class.name == "Fighter (Legacy)"
    view.destroy()
