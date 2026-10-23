"""Full backup: what goes into the file, and importing it into another install (replace or keep)."""

import json
import os
import zipfile

import pytest

import backup as B


def _png(path, color=(200, 30, 30)):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new("RGB", (40, 30), color).save(path)
    return path


def _sources(tmp_path, name, spell_manager=None):
    from character_manager import CharacterManager
    from settings import SettingsManager
    from ui.character_sheet_view import CharacterSheetManager
    root = tmp_path / name
    root.mkdir()
    sm = SettingsManager(str(root / "settings.json"))
    sm.load()
    cm = CharacterManager(str(root / "characters.json"))
    shm = CharacterSheetManager(str(root / "character_sheets.json"))
    return B.Sources(spell_manager=spell_manager, character_manager=cm, sheet_manager=shm,
                     data_dir=str(root), settings_manager=sm)


@pytest.fixture()
def spells():
    from spell_manager import SpellManager
    sm = SpellManager()
    sm.load_spells()
    return sm


@pytest.fixture()
def home(tmp_path, spells):
    """An install with something in every category."""
    from calendar_state import new_campaign
    from character import CharacterSpellList, ClassLevel
    from character_sheet import CharacterSheet
    from random_tables import RandomTable, TableEntry
    from spell import CharacterClass

    src = _sources(tmp_path, "home", spells)
    src.settings_manager.update(appearance_mode="light", hotkeys={"page.settings": "Ctrl+Alt+S"},
                                lan_client_id="home-install-id")
    with open(src.path("font_settings.json"), "w") as f:
        json.dump({"family": "Georgia"}, f)
    with open(src.path("custom_themes.json"), "w") as f:
        json.dump({"version": 2, "themes": [{"id": "abc", "name": "Mine", "colors": {}}]}, f)

    spell = spells._dict_to_spell({"name": "Bkp Bolt", "level": 1, "school": "Evocation",
                                   "casting_time": "Action", "range_value": 60, "components": "V",
                                   "duration": "Instantaneous", "description": "Original text.",
                                   "classes": ["Wizard"], "tags": ["Unofficial"]})
    assert spells.add_spell(spell)

    src.random_tables.add_table(RandomTable("Bkp Table", "d4", [TableEntry(1, 4, "Anything")]))

    src.character_manager.add_character(CharacterSpellList(
        name="Bkp Hero", classes=[ClassLevel(CharacterClass.WIZARD, 3)], known_spells=["Bkp Bolt"]))
    src.sheet_manager.update_sheet("Bkp Hero", CharacterSheet(character_name="Bkp Hero"))

    src.studio_store.new("feats", "Bkp Draft", {"name": "Bkp Draft", "description": "WIP"})
    src.studio_store.save()
    store = src.calendar_store
    store.campaigns.append(new_campaign("Bkp Campaign"))
    store.save()

    src.image_store.set_image_file("monsters", "Goblin", _png(str(tmp_path / "goblin.png")))

    asset_id, w, h = src.assets.add_image(_png(str(tmp_path / "map.png"), (10, 90, 10)))
    from tabletop import new_scene
    scene = new_scene("Bkp Cave", asset_id, w, h)
    src.tabletop.scenes[scene["id"]] = scene
    src.tabletop.order.append(scene["id"])
    src.tabletop.save()

    _png(os.path.join(src.token_folder, "Orcs", "Orc Chief.png"))
    pdfs = src.path("PDFs")
    os.makedirs(pdfs)
    with open(os.path.join(pdfs, "Handout.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 test handout")

    yield src
    spells.delete_spell("Bkp Bolt") if spells.get_spell("Bkp Bolt") else None
    src.random_tables.delete_table("Bkp Table")


def test_summary_counts_every_category(home):
    info = B.summarize(home)
    assert list(info) == list(B.CATEGORIES)
    assert info["content"].count >= 1
    assert info["random_tables"].count == 1          # the bundled official tables are not "yours"
    assert info["characters"].count == 1
    assert info["studio"].count == 1
    assert info["calendars"].count == 1
    assert info["images"].count == 1
    assert info["tabletop"].count == 1
    assert info["tokens"].count == 1
    assert info["pdfs"].count == 1
    assert not any(i.error for i in info.values())


def test_export_writes_a_zip_with_manifest_and_only_chosen_parts(home, tmp_path):
    path = str(tmp_path / "out.zip")
    result = B.export_backup(path, home, ["settings", "characters", "images"])
    assert set(result.counts) == {"settings", "characters", "images"}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        manifest = json.loads(z.read("manifest.json"))
        settings = json.loads(z.read("settings/settings.json"))
    assert manifest["format"] == B.FORMAT and set(manifest["categories"]) == set(result.counts)
    assert "characters.json" in names and "images/index.json" in names
    assert "content.json" not in names and not any(n.startswith("pdfs/") for n in names)
    assert settings["appearance_mode"] == "light"
    assert "lan_client_id" not in settings              # this computer's identity stays here
    assert not [n for n in os.listdir(tmp_path) if n.endswith(".tmp")]


def test_round_trip_into_a_fresh_install(home, tmp_path, spells):
    path = str(tmp_path / "full.zip")
    B.export_backup(path, home, B.CATEGORIES)
    manifest = B.read_manifest(path)
    assert set(manifest.categories) == set(B.CATEGORIES)

    # the content lives in the shared test database: remove it so the import has to bring it back
    spells.delete_spell("Bkp Bolt")
    home.random_tables.delete_table("Bkp Table")

    away = _sources(tmp_path, "away", spells)
    away.settings_manager.update(lan_client_id="away-install-id")
    result = B.import_backup(path, away, B.CATEGORIES)
    assert not result.warnings, result.warnings

    s = away.settings_manager.settings
    assert s.appearance_mode == "light" and s.hotkeys == {"page.settings": "Ctrl+Alt+S"}
    assert s.lan_client_id == "away-install-id"
    assert json.load(open(away.path("font_settings.json")))["family"] == "Georgia"
    assert result.restart_needed
    assert spells.get_spell("Bkp Bolt") is not None
    assert away.random_tables.get_table("Bkp Table") is not None
    assert away.character_manager.get_character("Bkp Hero") is not None
    assert away.sheet_manager.get_sheet("Bkp Hero") is not None
    assert [d.name for d in away.studio_store.drafts] == ["Bkp Draft"]
    assert [c.name for c in away.calendar_store.campaigns] == ["Bkp Campaign"]
    assert away.calendar_store.active_id == away.calendar_store.campaigns[0].id
    assert away.image_store.path_for("monsters", "Goblin")
    scene = next(iter(away.tabletop.scenes.values()))
    assert scene["name"] == "Bkp Cave" and away.assets.path(scene["map"])
    assert os.path.isfile(os.path.join(away.token_folder, "Orcs", "Orc Chief.png"))
    assert os.path.isfile(os.path.join(away.pdf_target, "Handout.pdf"))

    # importing the same backup again changes nothing and duplicates nothing
    again = B.import_backup(path, away, B.CATEGORIES)
    assert len(away.studio_store.drafts) == 1 and len(away.calendar_store.campaigns) == 1
    assert len(away.tabletop.scenes) == 1
    assert "added" not in again.lines["tokens"]


def test_keep_mine_leaves_existing_things_alone(home, tmp_path, spells):
    path = str(tmp_path / "full.zip")
    B.export_backup(path, home, ["content", "characters", "studio"])
    spell = spells.get_spell("Bkp Bolt")
    spell.description = "Changed here."
    spells.update_spell("Bkp Bolt", spell)
    home.studio_store.drafts[0].name = "Renamed here"
    home.studio_store.save()

    result = B.import_backup(path, home, ["content", "characters", "studio"], replace=False)
    assert spells.get_spell("Bkp Bolt").description == "Changed here."
    assert home.studio_store.drafts[0].name == "Renamed here"
    assert "kept" in result.lines["content"] and "kept" in result.lines["characters"]

    B.import_backup(path, home, ["content", "studio"], replace=True)
    assert spells.get_spell("Bkp Bolt").description == "Original text."
    assert home.studio_store.drafts[0].name == "Bkp Draft"


def test_only_chosen_categories_are_imported(home, tmp_path, spells):
    path = str(tmp_path / "full.zip")
    B.export_backup(path, home, B.CATEGORIES)
    away = _sources(tmp_path, "away", spells)
    result = B.import_backup(path, away, ["calendars"])
    assert list(result.lines) == ["calendars"]
    assert away.character_manager.get_character("Bkp Hero") is None
    assert not os.path.exists(away.token_folder)


def test_rejects_files_that_are_not_backups(tmp_path):
    bad = tmp_path / "x.zip"
    bad.write_text("not a zip")
    with pytest.raises(B.BackupError):
        B.read_manifest(str(bad))
    pack = tmp_path / "pack.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("Monsters/Goblin.png", b"..")
    with pytest.raises(B.BackupError, match="not a Spellbook backup"):
        B.read_manifest(str(pack))
    newer = tmp_path / "newer.zip"
    with zipfile.ZipFile(newer, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": B.FORMAT, "version": B.VERSION + 1}))
    with pytest.raises(B.BackupError, match="newer version"):
        B.read_manifest(str(newer))


def test_paths_that_escape_the_folder_are_ignored(tmp_path, spells):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("manifest.json", json.dumps({"format": B.FORMAT, "version": 1,
                                                "categories": {"tokens": {"count": 3}, "pdfs": {"count": 1}}}))
        z.writestr("tokens/../../escaped.png", b"x")
        z.writestr("tokens//abs.png", b"x")
        z.writestr("tokens/C:/win.png", b"x")
        z.writestr("pdfs/../outside.pdf", b"x")
    away = _sources(tmp_path, "away", spells)
    B.import_backup(str(evil), away, B.CATEGORIES)
    assert not (tmp_path / "escaped.png").exists()
    assert not (tmp_path / "away" / "outside.pdf").exists()
    assert B.safe_member("tokens/a/b.png", "tokens/") == "a/b.png"
    for bad in ("tokens/../x", "tokens//x", "tokens/a/../../x", "tokens/C:/x", "tokens/a\\..\\x", "tokens/"):
        assert B.safe_member(bad, "tokens/") is None


def test_dialogs_list_the_categories_and_import(home, tmp_path, spells, tk_root, monkeypatch):
    from tkinter import messagebox
    from ui import backup_dialogs as D

    shown = []
    monkeypatch.setattr(messagebox, "showinfo", lambda title, text, **kw: shown.append(text))
    monkeypatch.setattr(messagebox, "showwarning", lambda title, text, **kw: shown.append(text))

    export = D.ExportBackupDialog(tk_root, home)
    assert set(export.vars) == set(B.CATEGORIES)
    assert export.vars["characters"].get() and export.vars["pdfs"].get()
    export.vars["pdfs"].set(False)
    path = str(tmp_path / "ui.zip")
    monkeypatch.setattr(D.filedialog, "asksaveasfilename", lambda **kw: path)
    export._go()
    assert os.path.isfile(path) and shown and "Saved" in shown[-1]
    assert "pdfs" not in B.read_manifest(path).categories

    away = _sources(tmp_path, "away", spells)
    dialog = D.ImportBackupDialog(tk_root, path, B.read_manifest(path), away)
    assert "pdfs" not in dialog.vars and dialog.vars["calendars"].get()
    for key, var in dialog.vars.items():
        var.set(key in ("calendars", "tokens"))
    dialog._go()
    assert [c.name for c in away.calendar_store.campaigns] == ["Bkp Campaign"]
    assert os.path.isfile(os.path.join(away.token_folder, "Orcs", "Orc Chief.png"))
    assert away.character_manager.get_character("Bkp Hero") is None
    assert "Calendars: 1 added" in shown[-1]
