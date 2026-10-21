"""Pictures for content (content_images.py): adding, packs, removal, and the picture on a page."""

import json
import os
import zipfile

import pytest
from PIL import Image

import content_images as ci


@pytest.fixture()
def store(tmp_path):
    return ci.ImageStore(str(tmp_path / "images"))


def _picture(path, size=(2000, 1000), color=(200, 30, 30), mode="RGB"):
    Image.new(mode, size, color if mode == "RGB" else color + (128,)).save(path)
    return str(path)


def test_name_matching_ignores_case_and_punctuation():
    assert ci.name_key("Adult Red Dragon") == ci.name_key("adult-red_dragon")
    assert ci.kind_for("Magic Items") == "magic_items"
    assert ci.kind_for("species") == "lineages"
    assert ci.kind_for("nonsense") is None


def test_add_and_remove_a_picture(store, tmp_path):
    rel = store.set_image_file("monsters", "Goblin", _picture(tmp_path / "g.png"))
    path = store.path_for("monsters", "goblin")
    assert path and rel.endswith(".jpg")                       # no transparency: stored as JPEG
    with Image.open(path) as img:
        assert max(img.size) == ci.MAX_SIDE                       # shrunk
    assert store.path_for("spells", "Goblin") is None
    assert ci.ImageStore(store.folder).has("monsters", "GOBLIN")  # saved in the index
    assert store.remove_image("monsters", "Goblin")
    assert not os.path.exists(path)


def test_transparent_pictures_stay_png(store, tmp_path):
    rel = store.set_image_file("spells", "Fireball", _picture(tmp_path / "f.png", (50, 50), mode="RGBA"))
    assert rel.endswith(".png")


def test_legacy_versions_fall_back_to_the_main_picture(store, tmp_path):
    store.set_image_file("spells", "Fireball", _picture(tmp_path / "f.png", (50, 50)))
    assert store.path_for("spells", "Fireball (Legacy)") == store.path_for("spells", "Fireball")


def test_not_a_picture_is_refused(store, tmp_path):
    bad = tmp_path / "bad.png"
    bad.write_text("hello")
    with pytest.raises(Exception):
        store.set_image_file("spells", "Fireball", str(bad))


def _make_pack(tmp_path, name="pack.zip", manifest=None, top=""):
    path = tmp_path / name
    pic = _picture(tmp_path / "src.png", (64, 64))
    with zipfile.ZipFile(path, "w") as z:
        if manifest is not None:
            z.writestr(top + "pack.json", json.dumps(manifest))
        z.write(pic, top + "Monsters/Goblin.png")
        z.write(pic, top + "magic items/bag-of-holding.png")
        z.write(pic, top + "Unknown/Thing.png")
        z.writestr(top + "Monsters/readme.txt", "not a picture")
    return str(path)


def test_import_a_pack_by_folders(store, tmp_path):
    report = store.import_pack(_make_pack(tmp_path, manifest={"name": "Beasts", "author": "Dom"}, top="beasts/"))
    assert report.added == 2 and len(report.skipped) == 2
    assert store.has("monsters", "Goblin") and store.has("magic_items", "Bag of Holding")
    packs = store.packs()
    assert [(p.name, p.author, p.count) for p in packs] == [("Beasts", "Dom", 2)]

    # a second pack doesn't replace pictures unless asked
    other = tmp_path / "other"
    (other / "Monsters").mkdir(parents=True)
    _picture(other / "Monsters" / "Goblin.jpg", (32, 32), (0, 0, 255))
    report = store.import_pack(str(other))
    assert report.kept == 1 and report.added == 0
    report = store.import_pack(str(other), replace=True)
    assert report.replaced == 1

    assert store.remove_pack(packs[0].id) == 1          # the Goblin now belongs to the other pack
    assert not store.has("magic_items", "Bag of Holding") and store.has("monsters", "Goblin")


def test_pack_with_a_list_in_pack_json(store, tmp_path):
    path = tmp_path / "listed.zip"
    pic = _picture(tmp_path / "x.png", (20, 20))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("pack.json", json.dumps({"name": "Listed", "images": [
            {"kind": "spells", "name": "Magic Missile", "file": "a.png"},
            {"kind": "spells", "name": "Missing", "file": "nope.png"}]}))
        z.write(pic, "a.png")
    report = store.import_pack(str(path))
    assert report.added == 1 and report.skipped == ["nope.png"]
    assert store.has("spells", "magic missile")


def test_export_and_reimport(store, tmp_path):
    store.set_image_file("feats", "Alert", _picture(tmp_path / "a.png", (40, 40)))
    store.set_image_file("monsters", "Goblin", _picture(tmp_path / "g.png", (40, 40)))
    out = str(tmp_path / "mine.zip")
    assert store.export_pack(out, name="Mine") == 2
    with zipfile.ZipFile(out) as z:
        assert {"Feats/Alert.jpg", "Monsters/Goblin.jpg", "pack.json"} <= set(z.namelist())
    fresh = ci.ImageStore(str(tmp_path / "fresh"))
    assert fresh.import_pack(out).added == 2


# --------------------------------------------------------------------------- the picture on a page

@pytest.fixture()
def fresh_fonts(tk_root):
    from typography import get_font_manager
    get_font_manager().scope.refresh()


def test_picture_widget_follows_the_store(tk_root, fresh_fonts, store, tmp_path, monkeypatch):
    monkeypatch.setattr(ci, "_store", store)
    from ui.content_image import ContentImage
    widget = ContentImage(tk_root, "monsters")
    widget.pack()
    widget.show("Goblin")
    tk_root.update()
    assert widget.add_button.winfo_manager() and not widget.image_label.winfo_manager()
    store.set_image_file("monsters", "Goblin", _picture(tmp_path / "g.png", (300, 200)))
    tk_root.update()
    assert widget.image_label.winfo_manager() and not widget.add_button.winfo_manager()
    widget.show(None)
    assert not widget.image_label.winfo_manager()
    widget.destroy()
    assert widget._on_store_changed not in store._listeners
