"""The Add buttons of the collection pages open the Homebrew Studio (a setting, on by default)."""

import time

import pytest


def pump(root, seconds=0.2):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture
def setting(monkeypatch):
    """Control the setting without touching the saved settings file."""
    from settings import get_settings_manager
    manager = get_settings_manager()
    original = manager.settings.studio_for_new_content

    def set_to(value: bool):
        manager.settings.studio_for_new_content = value
    yield set_to
    manager.settings.studio_for_new_content = original


class FakeMainWindow:
    """What a collection page looks for: a parent that can open a Studio tab."""

    def __init__(self):
        self.calls = []

    def open_studio_new(self, kind, name="", record=None, parent=""):
        self.calls.append((kind, name, record, parent))


@pytest.fixture
def host(tk_root):
    import customtkinter as ctk

    class Host(ctk.CTkFrame, FakeMainWindow):
        def __init__(self, parent):
            ctk.CTkFrame.__init__(self, parent)
            FakeMainWindow.__init__(self)
    tk_root.geometry("1200x800")
    frame = Host(tk_root)
    frame.pack(fill="both", expand=True)
    yield frame
    frame.destroy()
    tk_root.update()


def test_the_setting_is_on_by_default():
    from settings import AppSettings
    assert AppSettings().studio_for_new_content is True
    assert AppSettings.from_dict({}).studio_for_new_content is True
    assert AppSettings.from_dict({"studio_for_new_content": False}).studio_for_new_content is False


def test_the_setting_is_saved_with_the_others():
    from settings import AppSettings
    data = AppSettings(studio_for_new_content=False).to_dict()
    assert data["studio_for_new_content"] is False
    assert AppSettings.from_dict(data).studio_for_new_content is False


def test_the_settings_page_has_the_switch(tk_root):
    import customtkinter as ctk
    from settings import get_settings_manager
    from ui.settings_view import SettingsView
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    try:
        view = SettingsView(frame, get_settings_manager())
        view.pack(fill="both", expand=True)
        pump(tk_root, 0.5)
        if hasattr(view, "build_all_sections_now"):
            view.build_all_sections_now()
        pump(tk_root, 0.3)
        assert view._studio_for_new_var.get() is True
        texts = []

        def walk(w):
            for c in w.winfo_children():
                try:
                    texts.append(str(c.cget("text")))
                except Exception:
                    pass
                walk(c)
        walk(view)
        assert any("Add buttons open the Homebrew Studio" in t for t in texts)
        view._studio_for_new_var.set(False)
        view._on_setting_change()
        assert get_settings_manager().settings.studio_for_new_content is False
        view._studio_for_new_var.set(True)
        view._on_setting_change()
        assert get_settings_manager().settings.studio_for_new_content is True
    finally:
        frame.destroy()


def test_open_in_studio_asks_the_window_that_holds_the_page(host, tk_root, setting):
    import customtkinter as ctk
    from ui.studio_launch import main_window_of, open_in_studio
    setting(True)
    inner = ctk.CTkFrame(host)
    leaf = ctk.CTkLabel(inner, text="x")
    assert main_window_of(leaf) is host
    assert open_in_studio(leaf, "spells") is True
    assert open_in_studio(leaf, "monsters", name="Copy", record={"name": "Copy"}) is True
    assert open_in_studio(leaf, "subclasses", parent="Fighter") is True
    assert host.calls == [("spells", "", None, ""), ("monsters", "Copy", {"name": "Copy"}, ""),
                          ("subclasses", "", None, "Fighter")]


def test_with_the_setting_off_or_no_window_the_editor_dialog_is_used(host, tk_root, setting):
    import customtkinter as ctk
    from ui.studio_launch import open_in_studio
    setting(False)
    assert open_in_studio(host, "spells") is False and host.calls == []
    setting(True)
    stray = ctk.CTkFrame(tk_root)                    # not inside any window that can open a Studio tab
    assert open_in_studio(stray, "spells") is False
    stray.destroy()


def test_a_failing_studio_never_leaves_the_add_button_dead(host, setting):
    from ui.studio_launch import open_in_studio
    setting(True)

    def boom(*a, **k):
        raise RuntimeError("no studio today")
    host.open_studio_new = boom
    assert open_in_studio(host, "feats") is False


def test_the_monsters_add_button_opens_the_studio(host, tk_root, setting, monkeypatch):
    from ui.monster_view import MonsterView
    import ui.monster_view as mv
    view = MonsterView(host)
    view.pack(fill="both", expand=True)
    opened = []
    monkeypatch.setattr(view, "_open_editor", lambda *a, **k: opened.append(a) or None)
    setting(True)
    view._on_add_monster()
    assert host.calls == [("monsters", "", None, "")] and opened == []
    setting(False)
    view._on_add_monster()
    assert len(host.calls) == 1 and len(opened) == 1          # the stand-alone editor, as before


def test_duplicating_a_monster_sends_the_copy_to_the_studio(host, tk_root, setting):
    from monster import get_monster_manager
    from ui.monster_view import MonsterView
    view = MonsterView(host)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.3)
    ogre = get_monster_manager().get_monster("Ogre")
    assert view.list_panel.select_monster("Ogre") or True
    view.list_panel.get_selected_monster = lambda: ogre
    setting(True)
    view._on_duplicate_monster()
    kind, name, record, parent = host.calls[-1]
    assert kind == "monsters" and name == "Ogre (Copy)" and record["name"] == "Ogre (Copy)"
    assert record["is_official"] is False and record["hp"] == ogre.hp


def test_the_class_pages_add_buttons_open_the_studio(host, tk_root, setting, monkeypatch):
    from character_class import get_class_manager
    from ui.classes_view import ClassesCollectionView as ClassesView
    view = ClassesView(host)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.3)
    dialogs = []
    import ui.classes_view as cv
    monkeypatch.setattr(cv, "ClassEditorDialog", lambda *a, **k: dialogs.append("class") or _Closed())
    monkeypatch.setattr(cv, "SubclassEditorDialog", lambda *a, **k: dialogs.append("subclass") or _Closed())
    monkeypatch.setattr(view, "wait_window", lambda *_: None)
    fighter = get_class_manager().get_class("Fighter")
    setting(True)
    view._open_class_editor()
    view._open_subclass_editor(fighter)
    assert host.calls == [("classes", "", None, ""), ("subclasses", "", None, "Fighter")] and dialogs == []
    view._open_class_editor(fighter)                       # editing what exists still uses the editor window
    view._open_subclass_editor(fighter, fighter.subclasses[0])
    assert dialogs == ["class", "subclass"]
    setting(False)
    view._open_class_editor()
    assert dialogs[-1] == "class" and len(host.calls) == 2


class _Closed:
    result = None
