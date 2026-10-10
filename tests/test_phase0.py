import os

import pytest

import character_io
import content_io
import paths


def test_data_dir_override_is_used():
    assert paths.user_data_dir() == os.path.abspath(os.environ["SPELLBOOK_DATA_DIR"])
    assert paths.user_data_path("x.json").startswith(paths.user_data_dir())


@pytest.fixture()
def managers(tmp_path):
    from character_manager import CharacterManager
    from ui.character_sheet_view import CharacterSheetManager
    cm = CharacterManager(str(tmp_path / "characters.json"))
    sm = CharacterSheetManager(str(tmp_path / "sheets.json"))
    return cm, sm


def _make_character(cm, sm, name, gold=5):
    from character import CharacterSpellList
    from character_sheet import CharacterSheet
    cm.add_character(CharacterSpellList(name=name))
    sheet = CharacterSheet(character_name=name)
    sheet.gold = gold
    sm.update_sheet(name, sheet)


def test_export_import_roundtrip_and_conflicts(managers, tmp_path):
    cm, sm = managers
    _make_character(cm, sm, "Thorn", gold=7)
    data, lists, sheets = character_io.build_export(["Thorn"], cm, sm)
    assert (lists, sheets) == (1, 1)

    from character_manager import CharacterManager
    from ui.character_sheet_view import CharacterSheetManager
    cm2 = CharacterManager(str(tmp_path / "c2.json"))
    sm2 = CharacterSheetManager(str(tmp_path / "s2.json"))
    bundle = character_io.parse_bundle(data)
    assert character_io.plan_import(bundle, cm2, sm2).conflicts == []
    report = character_io.apply_import(bundle, cm2, sm2)
    assert report.sheets == 1 and report.spell_lists == 1
    assert sm2.get_sheet("Thorn").gold == 7

    plan = character_io.plan_import(bundle, cm2, sm2)
    assert plan.conflicts == ["Thorn"]


def test_conflict_policies(managers):
    cm, sm = managers
    _make_character(cm, sm, "Thorn", gold=1)
    data, _, _ = character_io.build_export(["Thorn"], cm, sm)
    data["character_sheets"]["Thorn"]["gold"] = 99
    bundle = character_io.parse_bundle(data)

    r = character_io.apply_import(bundle, cm, sm, policies={"Thorn": character_io.SKIP})
    assert r.skipped == ["Thorn"] and sm.get_sheet("Thorn").gold == 1

    r = character_io.apply_import(bundle, cm, sm, policies={"Thorn": character_io.RENAME})
    assert r.renamed == {"Thorn": "Thorn (2)"}
    assert sm.get_sheet("Thorn").gold == 1
    assert sm.get_sheet("Thorn (2)").gold == 99
    assert cm.get_character("Thorn (2)") is not None

    r = character_io.apply_import(bundle, cm, sm, policies={"Thorn": character_io.REPLACE})
    assert sm.get_sheet("Thorn").gold == 99


def test_parse_bundle_rejects_junk():
    for bad in (None, [], {}, {"character_sheets": []}, {"character_spell_lists": {}, "sheets": {}}):
        with pytest.raises(character_io.CharacterBundleError):
            character_io.parse_bundle(bad)


def test_preview_and_resolve_bundle():
    from feat import get_feat_manager, Feat
    fm = get_feat_manager()
    official = next(f for f in fm.feats if getattr(f, "is_official", False) and not getattr(f, "is_custom", False))
    mine = Feat.from_dict({"name": "Zzz Test Feat", "description": "mine"})
    mine.is_custom, mine.is_official = True, False
    fm.add_feat(mine)
    try:
        data = {"feats": [
            {"name": "Zzz Test Feat", "description": "theirs"},
            {"name": official.name, "description": "x"},
            {"name": "Zzz Brand New", "description": "y"},
        ]}
        pv = content_io.preview_bundle(data)
        assert ("feats", "Zzz Test Feat") in pv.replaces
        assert ("feats", official.name) in pv.official
        assert ("feats", "Zzz Brand New") in pv.new

        skipped = content_io.resolve_bundle(data, {("feats", "zzz test feat"): content_io.CLASH_SKIP})
        assert [r["name"] for r in skipped["feats"]] == [official.name, "Zzz Brand New"]

        renamed = content_io.resolve_bundle(data, default=content_io.CLASH_RENAME)
        assert "Zzz Test Feat (2)" in [r["name"] for r in renamed["feats"]]
        assert data["feats"][0]["name"] == "Zzz Test Feat"       # input untouched
    finally:
        fm.delete_feat("Zzz Test Feat")
