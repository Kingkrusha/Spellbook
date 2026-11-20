"""A data file that can't be read (or one record in it): the rest still loads, and the file as it was is kept
next to it, because the next save would otherwise write over the only copy."""

import json
import os

import atomic_io
from character import CharacterSpellList, ClassLevel
from character_manager import CharacterManager


def unreadable_copies(folder):
    return sorted(n for n in os.listdir(folder) if ".unreadable-" in n)


def test_the_copy_is_made_once_and_only_when_there_is_something_to_keep(tmp_path):
    path = tmp_path / "characters.json"
    assert atomic_io.keep_unreadable_copy(str(path)) is None                 # no file
    path.write_text("   ")
    assert atomic_io.keep_unreadable_copy(str(path)) is None                 # nothing in it
    path.write_text('{"characters": [{"name": "Mi')
    first = atomic_io.keep_unreadable_copy(str(path))
    assert first and open(first).read() == '{"characters": [{"name": "Mi'
    assert atomic_io.keep_unreadable_copy(str(path)) == first                # the same contents: the same copy
    assert unreadable_copies(tmp_path) == [os.path.basename(first)]
    assert first.endswith(".json") and "Mi" not in os.path.basename(first)


def test_one_character_that_cannot_be_read_does_not_lose_the_others(tmp_path):
    path = tmp_path / "characters.json"
    good = CharacterSpellList(name="Mira", classes=[ClassLevel.from_dict({"class": "Wizard", "level": 3})])
    path.write_text(json.dumps({"characters": [good.to_dict(), {"classes": "nonsense"}, "junk"]}))
    heard = []
    manager = CharacterManager(str(path))
    manager.add_error_listener(heard.append)
    assert manager.load_characters()
    assert [c.name for c in manager.characters] == ["Mira"]
    assert len(heard) == 1 and heard[0].startswith("Could not load 2 of the characters")
    (copy,) = unreadable_copies(tmp_path)
    assert copy in heard[0]
    manager.save_characters()                                                # the save keeps Mira ...
    assert [c["name"] for c in json.loads(path.read_text())["characters"]] == ["Mira"]
    assert "nonsense" in (tmp_path / copy).read_text()                       # ... and the copy keeps the rest


def test_a_characters_file_that_cannot_be_read_at_all_is_kept_before_anything_saves_over_it(tmp_path):
    path = tmp_path / "characters.json"
    path.write_text('{"characters": [{"name": "Mira", "classes": [')         # cut off half way
    heard = []
    manager = CharacterManager(str(path))
    manager.add_error_listener(heard.append)
    assert not manager.load_characters() and manager.characters == []
    (copy,) = unreadable_copies(tmp_path)
    manager.add_character(CharacterSpellList(name="New"))                    # writes the file anew
    assert "Mira" in (tmp_path / copy).read_text() and "Mira" not in path.read_text()
    assert heard and copy in heard[0]


def test_one_sheet_that_cannot_be_read_does_not_lose_the_others(tmp_path):
    from character_sheet import CharacterSheet
    from ui.character_sheet_view import CharacterSheetManager
    path = tmp_path / "character_sheets.json"
    sheet = CharacterSheet(character_name="Mira")
    path.write_text(json.dumps({"sheets": {"Mira": sheet.to_dict(), "Broken": ["not", "a", "sheet"]}}))
    heard = []
    manager = CharacterSheetManager(str(path))
    manager.add_error_listener(heard.append)
    assert manager.load()
    assert manager.get_sheet("Mira") is not None and manager.get_sheet("Broken") is None
    assert len(unreadable_copies(tmp_path)) == 1 and heard and "1 of the sheets" in heard[0]

    path.write_text("[1, 2, 3]")
    assert not CharacterSheetManager(str(path)).load()
    assert len(unreadable_copies(tmp_path)) == 2


def test_a_damaged_map_does_not_lose_the_other_maps(tmp_path):
    import tabletop
    path = tmp_path / "tabletop.json"
    table = tabletop.Tabletop(str(path))
    cellar = table.apply({"op": "scene_new", "scene_data": {"name": "Cellar"}})["scene"]
    attic = table.apply({"op": "scene_new", "scene_data": {"name": "Attic"}})["scene"]
    table.apply({"op": "token_add", "scene": attic, "token": {"name": "Orc", "x": 70, "y": 70}})
    table.apply({"op": "wall_add", "scene": attic, "wall": {"pts": [0, 0, 140, 0]}})
    table.save()
    data = json.loads(path.read_text())
    room = data["scenes"][1]
    room["grid"] = "square"                                                  # the Attic's grid is nonsense now,
    room["tokens"] += ["junk", None, {"id": "t2", "name": "Ghost", "x": {"not": "a number"}, "y": []}]
    room["walls"] += [{"id": "w2", "pts": "0,0,10,10"}, {"id": "w3", "pts": [0, 0, None, 5]}]   # and so are these
    data["scenes"].append(7)
    data["scenes"].append({"id": ["not", "an", "id"], "name": "Roof"})
    path.write_text(json.dumps(data))
    again = tabletop.Tabletop(str(path))
    assert list(again.scenes) == [cellar, attic]                             # mended where that is possible
    mended = again.scenes[attic]
    assert mended["grid"]["type"] == "square" and len(mended["walls"]) == 1
    assert [(t["name"], t["x"], t["y"]) for t in mended["tokens"]] == [("Orc", 70.0, 70.0), ("Ghost", 0.0, 0.0)]
    tabletop.project(mended, None), tabletop.project(mended, "a player")     # and it can be shown
    assert len(unreadable_copies(tmp_path)) == 1                             # what was left out is kept

    path.write_text('{"scenes": [{"id": "a", "na')
    assert tabletop.Tabletop(str(path)).scenes == {}
    assert len(unreadable_copies(tmp_path)) == 2


def test_calendars_drafts_and_music_survive_files_of_the_wrong_shape(tmp_path):
    import calendar_state
    import music_library
    import studio_store
    cal = tmp_path / "calendars.json"
    good = calendar_state.new_campaign("Stormreach").to_dict()
    cal.write_text(json.dumps({"campaigns": [good, "junk", {"config": {"months": [{"days": "many"}]}}]}))
    store = calendar_state.CalendarStore(str(cal))
    assert [c.name for c in store.campaigns] == ["Stormreach"]
    cal.write_text(json.dumps({"campaigns": {"a": 1}}))
    assert calendar_state.CalendarStore(str(cal)).campaigns == []

    drafts = tmp_path / "studio.json"
    drafts.write_text(json.dumps({"drafts": [{"kind": "spells", "name": "Spark", "record": {}},
                                             {"kind": "spells", "record": 5}], "panels": 3}))
    assert [d.name for d in studio_store.StudioStore(str(drafts)).drafts] == ["Spark"]

    music = tmp_path / "music.json"
    music.write_text(json.dumps({"tracks": [{"title": "Tavern", "path": "t.mp3"}, {"title": "Bad", "volume": "loud"}],
                                 "folders": 9}))
    library = music_library.MusicLibrary(str(music))
    assert [t.title for t in library.tracks] == ["Tavern"] and library.folders == []
    assert len(unreadable_copies(tmp_path)) >= 2                             # calendars (twice) and drafts
