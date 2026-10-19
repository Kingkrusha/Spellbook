"""The Homebrew Studio page: editors inside the page, drafts kept as you type, Insights, reference panels, publishing."""

import os
import time
from tkinter import messagebox

import pytest

import studio_store as SS


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def pump_until(root, condition, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        root.update()
        if condition():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(scope="module")
def sm():
    from spell_manager import SpellManager
    manager = SpellManager()
    manager.load_spells()
    return manager


@pytest.fixture
def host(tk_root):
    import customtkinter as ctk
    tk_root.geometry("1500x900")
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    yield frame
    frame.destroy()
    tk_root.update()


# --------------------------------------------------------------------------- the editors as panels

def make_panel(kind, parent, sm, obj=None):
    from ui.studio_view import make_editor
    draft = SS.Draft(id="t", kind=kind, name="", parent="Fighter" if kind == "subclasses" else "")
    return make_editor(kind, parent, draft, obj, sm)


@pytest.mark.parametrize("kind", SS.KINDS)
def test_every_editor_works_as_a_panel(kind, host, tk_root, sm):
    panel = make_panel(kind, host, sm)
    panel.pack(fill="both", expand=True)
    pump(tk_root, 0.2)
    shown = []
    panel.on_finish = shown.append
    lenient = panel.build_result(strict=False)             # a blank form is still readable
    assert type(lenient).__name__ in ("Spell", "Feat", "Lineage", "Background", "Equipment", "MagicItem", "Monster",
                                      "RulePage", "CharacterClassDefinition", "SubclassDefinition")
    with pytest.raises(ValueError):
        panel.build_result(strict=True)                    # but cannot be saved blank
    panel._finish()                                        # Cancel / Close reports to the host, not to a window
    assert shown == [None]
    assert panel.winfo_exists()


def test_a_panel_form_round_trips_a_filled_in_draft(host, tk_root, sm):
    from magic_item import MagicItem, Rarity
    item = MagicItem(name="Round Trip Ring", type="Ring", rarity=Rarity.RARE, description="Grants a thing.",
                     requires_attunement=True, attunement_requirement="by a Wizard", is_official=False, is_custom=True)
    panel = make_panel("magic_items", host, sm, item)
    panel.pack(fill="both", expand=True)
    pump(tk_root, 0.2)
    back = panel.build_result(strict=True)
    assert (back.name, back.rarity, back.attunement_requirement) == ("Round Trip Ring", Rarity.RARE, "by a Wizard")
    assert SS.object_to_record("magic_items", back) == SS.object_to_record("magic_items", item)


def test_saving_inside_the_studio_does_not_touch_the_collections(host, tk_root, sm, monkeypatch):
    from lineage import get_lineage_manager
    panel = make_panel("lineages", host, sm)
    panel.pack(fill="both", expand=True)
    pump(tk_root, 0.2)
    panel.name_entry.insert(0, "Embedded Only Lineage")
    before = len(get_lineage_manager().lineages)
    got = []
    panel.on_finish = got.append
    panel._save()
    assert got and got[0].name == "Embedded Only Lineage"
    assert len(get_lineage_manager().lineages) == before
    assert get_lineage_manager().get_lineage("Embedded Only Lineage") is None


def test_the_class_editor_panel_leaves_the_class_list_alone(host, tk_root, sm):
    from character_class import get_class_manager
    panel = make_panel("classes", host, sm)
    panel.pack(fill="both", expand=True)
    pump(tk_root, 0.3)
    panel.name_entry.insert(0, "Embedded Only Class")
    got = []
    panel.on_finish = got.append
    panel._on_save_class()
    assert got and got[0].name == "Embedded Only Class"
    assert get_class_manager().get_class("Embedded Only Class") is None
    assert len(got[0].levels) == 20


def test_the_class_panel_can_be_read_before_its_other_tabs_exist(host, tk_root, sm):
    panel = make_panel("classes", host, sm)
    panel.pack(fill="both", expand=True)
    pump(tk_root, 0.3)
    assert not hasattr(panel, "is_caster_var")             # the Spellcasting tab is built on first visit
    cls = panel.build_result(strict=False)
    assert cls.is_spellcaster is False and len(cls.levels) == 20


def test_the_dialog_versions_still_save_into_the_collections(tk_root, monkeypatch):
    from magic_item import get_magic_item_manager
    from ui.magic_item_view import MagicItemEditorDialog
    dialog = MagicItemEditorDialog(tk_root, "Add Magic Item")
    dialog.name_entry.insert(0, "Dialog Test Trinket")
    dialog._save()
    assert dialog.result is not None and dialog.result.name == "Dialog Test Trinket"
    pump(tk_root, 0.2)
    assert not dialog.winfo_exists()                       # a dialog closes itself when it finishes
    monkeypatch.setattr(messagebox, "showerror", lambda *a, **k: None)
    blank = MagicItemEditorDialog(tk_root, "Add Magic Item")
    blank._save()
    assert blank.result is None and blank.winfo_exists()   # and stays open when the form is incomplete
    blank.destroy()
    assert get_magic_item_manager().get_item("Dialog Test Trinket") is None


# --------------------------------------------------------------------------- the page

@pytest.fixture(scope="module")
def shared_service(sm):
    """One service (and so one index, which takes a few seconds to build) for the whole module."""
    from studio_service import StudioService
    service = StudioService(sm, SS.StudioStore(os.path.join(os.environ["SPELLBOOK_DATA_DIR"], "studio-ui.json")))
    service.ensure_index(wait=True)
    return service


@pytest.fixture
def studio(host, tk_root, sm, tmp_path, shared_service):
    from ui.studio_view import StudioView
    service = shared_service
    service.store = SS.StudioStore(str(tmp_path / "studio.json"))
    service._dirty = False
    published = []
    view = StudioView(host, {}, spell_manager=sm, service=service, on_published=lambda: published.append(1))
    view.pack(fill="both", expand=True)
    view.published = published
    pump(tk_root, 0.4)
    yield view
    view.destroy()
    service._dirty = False


def type_into(view, root, name, text):
    view.editor.name_entry.delete(0, "end")
    view.editor.name_entry.insert(0, name)
    view.editor.desc_text.insert("1.0", text)
    view._snapshot()
    pump(root, 0.1)


def test_the_page_opens_on_a_choice_of_what_to_make(studio):
    assert studio.draft is None and studio.welcome.winfo_manager() == "pack"
    assert str(studio.publish_button.cget("state")) == "disabled"


def test_a_new_draft_opens_its_editor_and_is_kept_as_you_type(studio, tk_root):
    draft = studio.new_draft("magic_items")
    pump(tk_root, 0.3)
    assert studio.editor is not None and studio.welcome.winfo_manager() != "pack"
    type_into(studio, tk_root, "Cloak of Steady Senses", "While worn, treat a d20 roll of 9 or lower as a 10.")
    assert draft.name == "Cloak of Steady Senses"
    assert draft.record["description"].startswith("While worn")
    studio._flush_save()
    again = SS.StudioStore(studio.store.path)
    assert again.get(draft.id).name == "Cloak of Steady Senses"
    assert "Cloak of Steady Senses" in studio._chips[draft.id]["button"].cget("text")


def test_drafts_come_back_when_the_page_is_rebuilt(studio, tk_root, sm, host):
    from ui.studio_view import StudioView
    draft = studio.new_draft("feats")
    pump(tk_root, 0.3)
    type_into(studio, tk_root, "Steady Hand", "You have advantage on Dexterity checks made with thieves' tools.")
    state = studio.state
    service = studio.service
    studio.destroy()
    pump(tk_root, 0.2)
    view = StudioView(host, state, spell_manager=sm, service=service)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.5)
    try:
        assert view.draft is not None and view.draft.id == draft.id
        assert view.editor.name_entry.get() == "Steady Hand"
        assert "thieves' tools" in view.editor.desc_text.get("1.0", "end")
    finally:
        view.destroy()


def test_insights_name_what_a_draft_resembles(studio, tk_root):
    studio.new_draft("magic_items")
    pump(tk_root, 0.3)
    type_into(studio, tk_root, "Cloak of Steady Senses",
              "While you wear this cloak, treat any roll on a d20 lower than a 10 as a 10 for perception checks.")
    studio._start_analysis()
    assert pump_until(tk_root, lambda: "Reliable Talent" in studio.insights.similar_text.plain())
    text = studio.insights.similar_text.plain()
    assert "Silver Tongue" in text
    assert "Same effect: treats low d20 rolls as a higher number" in text


def test_a_name_that_is_already_taken_is_flagged(studio, tk_root):
    studio.new_draft("magic_items")
    pump(tk_root, 0.3)
    type_into(studio, tk_root, "Bag of Holding", "A bag that holds more than it should.")
    studio._start_analysis()
    assert pump_until(tk_root, lambda: "official content" in studio.insights.similar_text.plain())


def test_the_balance_tab_judges_a_monster_against_its_cr(studio, tk_root):
    studio.new_draft("monsters")
    pump(tk_root, 0.5)
    ed = studio.editor
    ed.name_entry.insert(0, "Brute of Ash")
    ed.ac_entry.insert(0, "17")
    ed.hp_manual_var.set(True)                              # a typed number: hit points are not worked out
    ed._update_preview()
    ed.hp_entry.insert(0, "310")
    ed.cr_var.set("5")
    studio._snapshot()
    studio._start_analysis()
    assert pump_until(tk_root, lambda: studio.insights._analysis is not None and studio.insights._analysis.cr)
    assert studio.insights.tabs.winfo_manager() == "pack"
    studio.insights.select_balance()
    pump(tk_root, 0.2)
    text = studio.insights.balance_text.plain()
    assert "Hit Points 310 are higher than is typical for CR 5" in text
    assert "Suggested CR" in text
    # take the suggestion
    suggested = studio.insights._analysis.cr.suggested
    studio.insights._apply()
    pump(tk_root, 0.2)
    assert ed.cr_var.get() == suggested


def test_other_kinds_have_no_balance_tab(studio, tk_root):
    studio.new_draft("monsters")
    pump(tk_root, 0.4)
    assert studio.insights.tabs.winfo_manager() == "pack"
    studio.new_draft("feats")
    pump(tk_root, 0.4)
    assert studio.insights.tabs.winfo_manager() != "pack"


def test_reference_panels_show_content_side_by_side(studio, tk_root):
    from studio_service import Hit
    assert len(studio.panels) == 1
    studio._open_hit(Hit("Fireball", "", "spells", "spell", "Fireball"))
    studio._open_hit(Hit("Rogue", "", "class_features", "class", "Rogue"), new_panel=True)
    pump(tk_root, 0.8)
    assert len(studio.panels) == 2
    assert studio.panels[0].title_label.cget("text") == "Fireball"
    assert studio.panels[1].title_label.cget("text") == "Rogue"
    studio._remove_panel(studio.panels[0])
    assert len(studio.panels) == 1
    assert [p["name"] for p in studio.state["panels"]] == ["Rogue"]


def test_a_class_feature_opens_as_just_that_feature(studio, tk_root):
    hit = studio.service.search("reliable talent")[0]
    studio._open_hit(hit)
    pump(tk_root, 0.5)
    panel = studio.active_panel
    assert panel.title_label.cget("text") == "Reliable Talent"
    assert panel.state["feature"] == "Reliable Talent" and panel.state["name"] == "Rogue"
    panel.show_target("class", "Rogue")                     # "Show the whole Rogue"
    pump(tk_root, 0.8)
    assert panel.title_label.cget("text") == "Rogue"


def test_a_panel_search_box_finds_things_by_name(studio, tk_root):
    panel = studio.panels[0]
    panel.entry.insert(0, "reliable")
    panel._search_now()
    pump(tk_root, 0.2)
    assert "Reliable Talent" in panel.results.plain()
    panel.kind_var.set("Spells")
    panel.entry.delete(0, "end")
    panel.entry.insert(0, "fireb")
    panel._search_now()
    assert "Fireball" in panel.results.plain() and "Reliable" not in panel.results.plain()


def test_panels_come_back_with_the_page(studio, tk_root, sm, host):
    from studio_service import Hit
    from ui.studio_view import StudioView
    studio._open_hit(Hit("Fireball", "", "spells", "spell", "Fireball"))
    pump(tk_root, 0.6)
    state, service = studio.state, studio.service
    studio.destroy()
    pump(tk_root, 0.2)
    view = StudioView(host, state, spell_manager=sm, service=service)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.8)
    try:
        assert view.panels and view.panels[0].title_label.cget("text") == "Fireball"
    finally:
        view.destroy()


def test_publishing_adds_the_draft_to_the_collection(studio, tk_root, monkeypatch):
    from magic_item import get_magic_item_manager
    shown = []
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: shown.append(a))
    import ui.collections_view as cv
    monkeypatch.setattr(cv, "ImportReportDialog", lambda *a, **k: shown.append("report"))
    studio.new_draft("magic_items")
    pump(tk_root, 0.3)
    studio.publish()                                        # nothing written yet: refused, with a reason
    assert shown and "Name is required" in str(shown[0])
    shown.clear()
    studio.editor.name_entry.insert(0, "Studio Published Trinket")
    studio.editor.desc_text.insert("1.0", "A trinket that exists to be published by a test.")
    studio.publish()
    try:
        item = get_magic_item_manager().get_item("Studio Published Trinket")
        assert item is not None and item.is_custom
        assert shown == ["report"] and studio.published == [1]
        assert studio.draft.published_as == "Studio Published Trinket"
        assert studio.service.is_stale()                    # the index will pick the new item up
    finally:
        get_magic_item_manager().delete_item("Studio Published Trinket")


def test_closing_and_deleting_drafts(studio, tk_root, monkeypatch):
    a = studio.new_draft("feats")
    pump(tk_root, 0.3)
    b = studio.new_draft("spells")
    pump(tk_root, 0.4)
    assert studio.draft is b and len(studio._chips) == 2
    studio.close_draft(b.id)
    assert studio.draft is a and len(studio._chips) == 1
    assert studio.store.get(b.id) is not None               # closing keeps the draft
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    studio.delete_draft()
    assert studio.draft is None and studio.welcome.winfo_manager() == "pack"
    assert studio.store.get(a.id) is None


def test_the_editors_buttons_say_what_they_do_here(studio, tk_root):
    import customtkinter as ctk
    studio.new_draft("feats")
    pump(tk_root, 0.3)
    texts = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, ctk.CTkButton):
                texts.append(c.cget("text"))
            walk(c)
    walk(studio.editor)
    assert "Save draft" in texts and "Close draft" in texts and "Cancel" not in texts


def test_the_cancel_button_closes_the_draft_tab_but_keeps_the_draft(studio, tk_root):
    draft = studio.new_draft("feats")
    pump(tk_root, 0.3)
    type_into(studio, tk_root, "Kept Feat", "Remains in the drafts list.")
    studio.editor._finish()
    assert studio.draft is None
    assert studio.store.get(draft.id).name == "Kept Feat"
