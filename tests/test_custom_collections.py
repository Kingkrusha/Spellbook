"""Collections people shape themselves (custom_collections.py): new collections with their own fields, fields added
to the built-in collections, and how both travel (search, files, backups, LAN transfers, PDFs) and show on the
pages (ui/custom_collection_view.py, ui/collection_type_editor.py, ui/extra_fields.py)."""

import os
import shutil
import time

import pytest

import custom_collections as cc
import content_io


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fresh_db(tmp_path_factory, name="db"):
    from database import SpellDatabase
    folder = tmp_path_factory.mktemp(name)
    path = os.path.join(str(folder), "spellbook.db")
    shutil.copy(os.path.join(ROOT, "spellbook.db"), path)
    db = SpellDatabase(path)
    db.initialize()
    return db


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return _fresh_db(tmp_path_factory)


@pytest.fixture
def mgr(db):
    """The app's collection manager, pointed at this module's database and emptied around each test."""
    m = cc.get_collection_manager()
    old = m._db
    m._db = db
    _wipe(db)
    m.reload()
    yield m
    _wipe(db)
    m._db = old
    m.reload()


def _wipe(db):
    with db.get_connection() as conn:
        conn.execute("DELETE FROM collection_types")
        conn.execute("DELETE FROM custom_entries")
        conn.execute("DELETE FROM custom_field_values")


def deities(m, *fields):
    fields = fields or (cc.FieldDef("f_domain", "Domain", "choice", ["Life", "War"]),
                        cc.FieldDef("f_rank", "Rank", "number"),
                        cc.FieldDef("f_open", "Worshipped openly", "yes_no"),
                        cc.FieldDef("f_titles", "Titles", "list"),
                        cc.FieldDef("f_symbol", "Holy symbol", "long_text"))
    return m.save_type(cc.CollectionType(key="", name="Deities", icon="⚡", fields=list(fields)))


# ------------------------------------------------------------------ definitions

def test_a_new_collection_gets_a_key_and_keeps_its_fields(mgr):
    t = deities(mgr)
    assert (t.key, t.page_key, t.builtin) == ("deities", "custom:deities", False)
    assert [f.label for f in mgr.get_type("custom:deities").fields] == [
        "Domain", "Rank", "Worshipped openly", "Titles", "Holy symbol"]
    assert t.default_properties == cc.CUSTOM_DEFAULTS
    assert mgr.type_by_name("deities").key == "deities"


@pytest.mark.parametrize("fields, message", [
    ([cc.FieldDef("a", "Name")], "own properties"),
    ([cc.FieldDef("a", "Tags")], "own properties"),
    ([cc.FieldDef("a", "Domain"), cc.FieldDef("b", "domain")], "two fields"),
    ([cc.FieldDef("a", "Domain", "choice", [])], "at least one choice"),
    ([cc.FieldDef("a", "")], "needs a name"),
])
def test_fields_that_cannot_be_saved_are_refused(mgr, fields, message):
    with pytest.raises(cc.CollectionError, match=message):
        mgr.save_type(cc.CollectionType(key="", name="Factions", fields=fields))


def test_default_properties_of_a_built_in_collection_cannot_be_reused(mgr):
    feats = mgr.builtin_type("feats")
    assert "Prerequisite" in feats.default_properties
    feats.fields = [cc.FieldDef("p", "Prerequisite")]
    with pytest.raises(cc.CollectionError, match="own properties"):
        mgr.save_type(feats)


def test_names_must_be_free(mgr):
    deities(mgr)
    with pytest.raises(cc.CollectionError, match="already a collection"):
        mgr.save_type(cc.CollectionType(key="", name="DEITIES"))
    with pytest.raises(cc.CollectionError, match="one of the app's collections"):
        mgr.save_type(cc.CollectionType(key="", name="Spells"))
    second = mgr.save_type(cc.CollectionType(key="", name="Deities of the North"))
    assert second.key == "deities_of_the_north"


def test_deleting_a_collection_takes_its_entries(mgr):
    deities(mgr)
    mgr.add_entry(cc.CustomEntry("deities", "Zeus"))
    assert mgr.delete_type("deities") == 1
    assert mgr.custom_type("deities") is None and mgr.entries("deities") == []


def test_listeners_hear_about_changes(mgr):
    heard = []
    mgr.add_listener(lambda: heard.append(1))
    try:
        deities(mgr)
        assert heard
    finally:
        mgr._listeners.pop()


# ------------------------------------------------------------------ entries

def test_entries_are_stored_in_their_fields_shape(mgr):
    deities(mgr)
    assert mgr.add_entry(cc.CustomEntry("deities", "Zeus", "King", "Mine", ["sky", "Sky"],
                                        {"f_domain": "War", "f_rank": "1", "f_open": "yes",
                                         "f_titles": "Thunderer, Cloud-gatherer", "unknown": 3}))
    zeus = mgr.get_entry("deities", "zeus")
    assert zeus.values == {"f_domain": "War", "f_rank": 1, "f_open": True,
                           "f_titles": ["Thunderer", "Cloud-gatherer"]}
    assert zeus.tags == ["sky"]
    assert not mgr.add_entry(cc.CustomEntry("deities", "ZEUS"))         # names are unique in a collection
    with pytest.raises(cc.CollectionError, match="isn't a number"):
        mgr.add_entry(cc.CustomEntry("deities", "Hera", values={"f_rank": "high"}))


def test_an_entry_can_be_renamed_but_not_onto_another(mgr):
    deities(mgr)
    mgr.add_entry(cc.CustomEntry("deities", "Zeus"))
    mgr.add_entry(cc.CustomEntry("deities", "Hera"))
    assert mgr.update_entry("Zeus", cc.CustomEntry("deities", "Jupiter", "Renamed"))
    assert mgr.get_entry("deities", "Zeus") is None and mgr.get_entry("deities", "Jupiter").description == "Renamed"
    assert not mgr.update_entry("Jupiter", cc.CustomEntry("deities", "hera"))
    assert mgr.delete_entry("deities", "Jupiter") and not mgr.delete_entry("deities", "Jupiter")


def test_filter_options_come_from_the_choices_and_the_entries(mgr):
    t = deities(mgr)
    mgr.add_entry(cc.CustomEntry("deities", "Zeus", values={"f_titles": ["Thunderer"]}))
    assert mgr.field_options("deities", t.field("f_domain")) == ["Life", "War"]
    assert mgr.field_options("deities", t.field("f_titles")) == ["Thunderer"]
    assert mgr.field_options("deities", t.field("f_open")) == ["Yes", "No"]


# ------------------------------------------------------------------ added fields on built-in entries

def test_added_values_live_on_official_entries_and_follow_a_rename(mgr, db):
    feats = mgr.builtin_type("feats")
    feats.fields = [cc.FieldDef("f_region", "Region")]
    mgr.save_type(feats)
    mgr.set_extra_values("feats", "Alert", {"f_region": "Waterdeep"})
    assert mgr.extra_lines("feats", "Alert") == [("Region", "Waterdeep")]
    with db.get_connection() as conn:
        conn.execute("UPDATE feats SET name = 'Alertness' WHERE name = 'Alert'")
    try:
        assert mgr.extra_values("feats", "Alertness") == {"f_region": "Waterdeep"}
        assert mgr.extra_values("feats", "Alert") == {}
    finally:
        with db.get_connection() as conn:
            conn.execute("UPDATE feats SET name = 'Alert' WHERE name = 'Alertness'")
    assert mgr.extra_values("feats", "Alert") == {"f_region": "Waterdeep"}


def test_a_rename_onto_leftover_values_replaces_them(mgr, db):
    lineages = mgr.builtin_type("lineages")
    lineages.fields = [cc.FieldDef("f_note", "Note")]
    mgr.save_type(lineages)
    mgr.set_extra_values("lineages", "Elf", {"f_note": "elf"})
    mgr.set_extra_values("lineages", "Gone", {"f_note": "left behind"})     # an entry that no longer exists
    with db.get_connection() as conn:
        conn.execute("UPDATE lineages SET name = 'Gone' WHERE name = 'Elf'")
        conn.execute("UPDATE lineages SET name = 'GONE' WHERE name = 'Gone'")   # a change of case only
    try:
        assert mgr.extra_values("lineages", "Gone") == {"f_note": "elf"}
    finally:
        with db.get_connection() as conn:
            conn.execute("UPDATE lineages SET name = 'Elf' WHERE name = 'GONE'")


def test_values_of_a_removed_field_come_back_with_it(mgr):
    spells = mgr.builtin_type("spells")
    spells.fields = [cc.FieldDef("f_seen", "Seen in play", "yes_no"), cc.FieldDef("f_note", "Note")]
    mgr.save_type(spells)
    mgr.set_extra_values("spells", "Fireball", {"f_seen": True, "f_note": "big"})
    spells = mgr.builtin_type("spells")
    spells.fields = [spells.fields[0]]
    mgr.save_type(spells)
    mgr.set_extra_values("spells", "Fireball", {"f_seen": False})
    assert mgr.extra_values("spells", "Fireball") == {"f_seen": False, "f_note": "big"}
    assert mgr.extra_lines("spells", "Fireball") == [("Seen in play", "No")]
    spells = mgr.builtin_type("spells")
    spells.fields.append(cc.FieldDef(cc.new_field_id("Note", [f.id for f in spells.fields]), "Note"))
    mgr.save_type(spells)
    assert ("Note", "big") in mgr.extra_lines("spells", "Fireball")


# ------------------------------------------------------------------ search

def test_entries_are_found_by_the_global_search_under_their_collection(mgr, db):
    deities(mgr)
    mgr.add_entry(cc.CustomEntry("deities", "Zeus", "Hurls thunderbolts", values={"f_titles": ["Cloudgatherer"]}))
    hits = db.global_search("zeus")
    assert hits[0]["name"] == "Zeus" and hits[0]["section"] == "Deities"
    assert any(h["name"] == "Zeus" for h in db.global_search("cloudgatherer"))
    mgr.delete_type("deities")
    assert not any(h["name"] == "Zeus" for h in db.global_search("zeus"))


# ------------------------------------------------------------------ export / import

def _setup_everything(mgr):
    deities(mgr)
    mgr.add_entry(cc.CustomEntry("deities", "Zeus", "King", "Mine", ["sky"], {"f_domain": "War", "f_rank": 1}))
    feats = mgr.builtin_type("feats")
    feats.fields = [cc.FieldDef("f_region", "Region")]
    mgr.save_type(feats)
    mgr.set_extra_values("feats", "Alert", {"f_region": "Waterdeep"})


def test_an_export_carries_definitions_entries_and_values(mgr):
    _setup_everything(mgr)
    data, counts = content_io.export_bundle(None)
    assert counts["collection_types"] == 2 and counts["custom_entries"] == 1 and counts["field_values"] == 1
    by_name = {t["name"]: t for t in data["collection_types"]}
    assert by_name["Feats"]["builtin"] is True and by_name["Deities"]["icon"] == "⚡"
    assert data["custom_entries"][0]["values"]["f_domain"] == "War"


def test_sending_one_entry_brings_its_collection(mgr):
    _setup_everything(mgr)
    data, counts = content_io.bundle_of({"custom_entries": [mgr.get_entry("deities", "Zeus")]})
    assert [t["name"] for t in data["collection_types"]] == ["Deities"]


def test_sending_a_feat_brings_its_added_values(mgr):
    _setup_everything(mgr)
    from feat import get_feat_manager
    alert = get_feat_manager().get_feat("Alert")
    data, _ = content_io.bundle_of({"feats": [alert]})
    assert data["field_values"] == [{"collection": "feats", "name": "Alert", "values": {"f_region": "Waterdeep"}}]
    assert [t["key"] for t in data["collection_types"]] == ["feats"]


def test_importing_into_a_fresh_install_and_again(mgr, db, tmp_path_factory):
    _setup_everything(mgr)
    data, _ = content_io.export_bundle(None)
    other = _fresh_db(tmp_path_factory, "other")
    mgr._db = other
    mgr.reload()
    try:
        preview = content_io.preview_bundle(data)
        assert ("custom_entries", "Deities › Zeus") in preview.new and not preview.replaces
        report = content_io.import_bundle(data, None, link_mentions=False)
        assert not report.failed and not report.skipped
        assert mgr.get_entry("deities", "Zeus").values == {"f_domain": "War", "f_rank": 1}
        assert mgr.extra_values("feats", "Alert") == {"f_region": "Waterdeep"}

        again = content_io.import_bundle(data, None, link_mentions=False)
        assert sum(again.added.values()) == 0 and len(mgr.custom_types()) == 1
        preview = content_io.preview_bundle(data)
        assert ("custom_entries", "Deities › Zeus") in preview.replaces
        kept = content_io.resolve_bundle(data, default=content_io.CLASH_RENAME)
        assert [e["name"] for e in kept["custom_entries"]] == ["Zeus (2)"]
    finally:
        mgr._db = db
        mgr.reload()


def test_an_import_merges_fields_by_name(mgr, tmp_path_factory):
    deities(mgr, cc.FieldDef("f_x", "Domain", "choice", ["Life"]))
    incoming = {"collection_types": [{"key": "gods", "name": "Deities", "fields": [
                    {"id": "f_dom", "label": "domain", "kind": "choice", "choices": ["Sea"]},
                    {"id": "f_x", "label": "Pantheon", "kind": "text"}]}],
                "custom_entries": [{"collection": "gods", "name": "Poseidon",
                                    "values": {"f_dom": "Sea", "f_x": "Olympian"}}]}
    report = content_io.import_bundle(incoming, None, link_mentions=False)
    assert not report.failed and not report.skipped, report.problem_lines()
    t = mgr.custom_type("deities")
    assert [f.label for f in t.fields] == ["Domain", "Pantheon"]
    assert t.fields[0].choices == ["Life", "Sea"]
    pantheon = t.fields[1].id
    assert pantheon != "f_x"                                      # the id was taken by Domain here
    assert mgr.get_entry("deities", "Poseidon").values == {"f_x": "Sea", pantheon: "Olympian"}


def test_an_entry_without_its_collection_is_skipped(mgr):
    report = content_io.import_bundle({"custom_entries": [{"collection": "nowhere", "name": "X"}]}, None,
                                      link_mentions=False)
    assert report.skipped and "collection" in report.skipped[0][2]


# ------------------------------------------------------------------ PDF

def test_pdf_blocks_carry_the_fields(mgr):
    pe = pytest.importorskip("pdf_export")
    _setup_everything(mgr)
    mgr.add_entry(cc.CustomEntry("deities", "Hera", "Queen", values={"f_symbol": "A *peacock*", "f_open": True}))
    block = pe.block_for(mgr.get_entry("deities", "Hera"))
    assert block.subtitle == "Deities" and ("Worshipped openly", "Yes") in block.stats
    assert "Holy symbol" in block.body and "peacock" in block.body
    from feat import get_feat_manager
    block = pe.block_for(get_feat_manager().get_feat("Alert"))
    assert ("Region", "Waterdeep") in block.stats


# ------------------------------------------------------------------ pages

def pump(root, n=15):
    for _ in range(n):
        time.sleep(0.02)
        root.update()


def test_the_page_lists_filters_and_edits_entries(mgr, tk_root):
    from ui.custom_collection_view import CustomCollectionView
    deities(mgr)
    mgr.add_entry(cc.CustomEntry("deities", "Zeus", "Thunder", "Greek", ["sky"], {"f_domain": "War", "f_open": True}))
    mgr.add_entry(cc.CustomEntry("deities", "Hestia", "Hearth", "Greek", [], {"f_domain": "Life"}))
    view = CustomCollectionView(tk_root, "deities")
    view.pack(fill="both", expand=True)
    try:
        pump(tk_root)
        names = lambda: [e.name for e in view.list_panel._items]
        assert names() == ["Hestia", "Zeus"]
        assert "War" in view.list_panel.row_text(mgr.get_entry("deities", "Zeus"))
        domain = view._field_vars["f_domain"]
        domain.set("Life")
        view._apply_filters()
        assert names() == ["Hestia"]
        view._clear_filters()
        pump(tk_root)
        view._field_vars["f_open"].set("Yes")
        view._apply_filters()
        assert names() == ["Zeus"]
        view._clear_filters()
        pump(tk_root)
        view.search_var.set("hearth")
        view._apply_filters()
        assert names() == ["Hestia"]
        view._clear_filters()
        pump(tk_root)

        assert view.select_entry("Zeus")
        pump(tk_root)
        assert view.detail_panel.entry.name == "Zeus"

        # a new field shows up as a filter without reopening the page
        t = mgr.custom_type("deities")
        t.fields.append(cc.FieldDef("f_sea", "Sea god", "yes_no"))
        mgr.save_type(t)
        pump(tk_root)
        assert "f_sea" in view._field_vars

        # bulk source edit goes through the shared Select bar flow
        assert view._bulk_store([cc.CustomEntry("deities", "Zeus", "Thunder", "Roman", ["sky"])]) == 1
        assert mgr.get_entry("deities", "Zeus").source == "Roman"
    finally:
        view.destroy()


def test_a_deleted_collection_page_says_so(mgr, tk_root):
    from ui.custom_collection_view import CustomCollectionView
    deities(mgr)
    view = CustomCollectionView(tk_root, "deities")
    view.pack()
    try:
        pump(tk_root)
        mgr.delete_type("deities")
        pump(tk_root)
        assert view.ctype is None
    finally:
        view.destroy()


def test_the_entry_editor_reads_its_fields(mgr, tk_root):
    from ui.custom_collection_view import CustomEntryEditor
    t = deities(mgr)
    editor = CustomEntryEditor(tk_root, "New", t)
    try:
        pump(tk_root, 5)
        editor.name_entry.insert(0, "Ares")
        editor.tags_entry.insert(0, "war, blood")
        inputs = {i.fdef.id: i for i in editor.inputs}
        inputs["f_domain"].var.set("War")
        inputs["f_rank"].widget.insert(0, "4")
        inputs["f_open"].var.set(True)
        inputs["f_titles"].widget.insert(0, "Bane, Stormer")
        entry = editor.build_result()
        assert entry.tags == ["war", "blood"]
        assert t.clean_values(entry.values) == {"f_domain": "War", "f_rank": 4, "f_open": True,
                                                "f_titles": ["Bane", "Stormer"]}
        inputs["f_rank"].widget.insert("end", "x")
        with pytest.raises(cc.CollectionError, match="Rank"):
            editor.build_result()
    finally:
        editor.destroy()


def test_the_type_editor_builds_and_saves(mgr, tk_root):
    from ui.collection_type_editor import CollectionTypeEditor
    editor = CollectionTypeEditor(tk_root, None)
    try:
        pump(tk_root, 5)
        editor.name_entry.insert(0, "Factions")
        editor.add_row()
        row = editor.rows[-1]
        row.label_entry.insert(0, "Leader")
        editor.add_row()
        row = editor.rows[-1]
        row.label_entry.insert(0, "Standing")
        row.kind_var.set(cc.FIELD_KINDS["choice"])
        row._kind_changed()
        row.choices_entry.insert(0, "Friendly, Hostile")
        editor.move(row, -1)
        built = editor.build()
        assert [f.label for f in built.fields] == ["Standing", "Leader"]
        assert built.fields[0].choices == ["Friendly", "Hostile"]
        editor._save()
    except Exception:
        editor.destroy()
        raise
    stored = mgr.type_by_name("Factions")
    assert stored is not None and [f.label for f in stored.fields] == ["Standing", "Leader"]


def test_the_built_in_box_takes_no_room_until_there_are_fields(mgr, tk_root):
    import customtkinter as ctk
    from ui.extra_fields import ExtraFieldsBox
    frame = ctk.CTkFrame(tk_root)
    frame.pack()
    box = ExtraFieldsBox(frame, "equipment")
    box.pack(fill="x")
    try:
        box.show("Longsword")
        pump(tk_root, 5)
        assert not box.winfo_children() or box.winfo_reqheight() <= 2
        eq = mgr.builtin_type("equipment")
        eq.fields = [cc.FieldDef("f_maker", "Maker")]
        mgr.save_type(eq)                               # the box hears about the new field
        pump(tk_root, 5)
        assert box.winfo_children()
        mgr.set_extra_values("equipment", "Longsword", {"f_maker": "Dwarves"})
        pump(tk_root, 5)
        texts = []

        def walk(w):
            for c in w.winfo_children():
                try:
                    texts.append(c.cget("text"))
                except Exception:
                    pass
                walk(c)
        walk(box)
        assert "Dwarves" in texts
    finally:
        frame.destroy()


def test_the_collections_page_shows_a_card_for_each_collection(mgr, tk_root):
    from ui.collections_view import CollectionsView
    hub = CollectionsView(tk_root)
    hub.pack()
    try:
        pump(tk_root, 5)
        before = len(hub.cards_frame.winfo_children())
        assert before == len(CollectionsView.BUILTIN_CARDS) + 1            # and "New collection"
        deities(mgr)
        pump(tk_root, 5)
        assert len(hub.cards_frame.winfo_children()) == before + 1
    finally:
        hub.destroy()
