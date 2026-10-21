"""A markdown table in a description is drawn as a table everywhere descriptions are shown - the link pop-ups
(clicking a magic item on a character sheet) and the collection pages - never as raw pipes."""

import copy
import time

import pytest

from object_links import LinkTarget
from ui.rich_text_utils import description_blocks, split_table_cells

TABLE = "| Item | Cost |\n|---|---|\n| Zorblax Dagger | 17 gp |\n| [[equipment:Club|club]] | 1 sp |"
TEXT = "Before the table.\n\n" + TABLE + "\n\nAfter the table."
# a table straight under a line of text (no blank line between them)
GLUED = "Before the table.\n" + TABLE + "\nAfter the table."


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


@pytest.fixture(autouse=True)
def fresh_fonts(tk_root):
    from typography import get_font_manager
    get_font_manager().scope.refresh()


@pytest.fixture
def host(tk_root):
    import customtkinter as ctk
    frame = ctk.CTkFrame(tk_root)
    frame.pack(fill="both", expand=True)
    tk_root.geometry("900x800")
    yield frame
    frame.destroy()


def everything_shown(widget):
    """All the text on screen under ``widget``: text widgets, labels and buttons."""
    out = []

    def walk(w):
        if w.winfo_class() == "Text":
            out.append(w.get("1.0", "end-1c"))
        for attr in ("cget",):
            try:
                text = w.cget("text")
                if isinstance(text, str) and text:
                    out.append(text)
            except Exception:
                pass
        for child in w.winfo_children():
            walk(child)
    walk(widget)
    return out


def assert_drawn_as_table(widget):
    shown = everything_shown(widget)
    joined = "\n".join(shown)
    assert "|---" not in joined and "| Item" not in joined, joined[:300]           # no raw markdown
    assert "Zorblax Dagger" in joined and "17 gp" in joined                       # the cells are there
    assert "Item" in shown and "Cost" in shown                                     # as header cells of their own
    assert "Before the table." in joined and "After the table." in joined


# --------------------------------------------------------------------------- helpers

def test_a_table_is_split_from_the_text_around_it():
    assert [k for k, _ in description_blocks(TEXT)] == ["text", "table", "text"]
    assert [k for k, _ in description_blocks(GLUED)] == ["text", "table", "text"]
    assert description_blocks("") == [] and description_blocks("\n\n \n") == []
    kinds = [k for k, _ in description_blocks("a\n\n\n\nb")]
    assert kinds == ["text", "text"]


def test_a_link_with_shown_text_does_not_split_a_cell():
    assert split_table_cells("| [[equipment:Club|club]] | 1 sp |") == ["[[equipment:Club|club]]", "1 sp"]
    assert split_table_cells("| a | b") == ["a", "b"]


def test_description_blocks_draws_a_table(host, tk_root):
    from ui.rich_text_utils import render_description_blocks
    widgets = render_description_blocks(host, GLUED)
    pump(tk_root)
    assert len(widgets) == 3
    assert_drawn_as_table(host)


# --------------------------------------------------------------------------- the link pop-ups

def popup(host, tk_root, category, obj, name="Thing"):
    from ui.object_link_widgets import LinkDetailView
    view = LinkDetailView(host, LinkTarget(category, name, "", lambda: obj), wrap=500)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.4)
    return view


def test_magic_item_popup_draws_tables(host, tk_root):
    from magic_item import MagicItem
    item = MagicItem(name="Zorblax Item", description=TEXT)
    assert_drawn_as_table(popup(host, tk_root, "magic_item", item))


def test_equipment_popup_draws_tables_in_the_description_and_in_properties(host, tk_root):
    from equipment import Equipment
    item = Equipment(name="Zorblax Gear", description=TEXT, properties=[{"name": "Odd", "description": TEXT}])
    view = popup(host, tk_root, "equipment", item)
    joined = "\n".join(everything_shown(view))
    assert "|---" not in joined
    assert joined.count("Zorblax Dagger") == 2                                      # the description and the property


def test_feat_popup_draws_tables(host, tk_root):
    from feat import get_feat_manager
    feat = copy.deepcopy(get_feat_manager().get_feat("Alert"))
    feat.description = TEXT
    assert_drawn_as_table(popup(host, tk_root, "feat", feat))


def test_lineage_popup_draws_tables_in_the_text_and_in_a_trait(host, tk_root):
    from lineage import get_lineage_manager
    lineage = copy.deepcopy(get_lineage_manager().get_lineage("Elf"))
    lineage.description = TEXT
    lineage.traits[0].description = TEXT
    view = popup(host, tk_root, "lineage", lineage)
    joined = "\n".join(everything_shown(view))
    assert "|---" not in joined and joined.count("Zorblax Dagger") == 2


def test_background_popup_draws_tables_in_the_text_and_in_a_feature(host, tk_root):
    from background import get_background_manager
    background = copy.deepcopy(get_background_manager().get_background("Acolyte"))
    background.description = TEXT
    if background.features:
        background.features[0].description = TEXT
    view = popup(host, tk_root, "background", background)
    joined = "\n".join(everything_shown(view))
    assert "|---" not in joined and "Zorblax Dagger" in joined


def test_class_and_subclass_popups_draw_tables(host, tk_root):
    from character_class import get_class_manager
    cls = copy.deepcopy(get_class_manager().get_class("Wizard"))
    cls.description = TEXT
    assert_drawn_as_table(popup(host, tk_root, "class", cls))
    sub = copy.deepcopy(cls.subclasses[0])
    sub.description = TEXT
    assert_drawn_as_table(popup(host, tk_root, "subclass", sub))


def test_spell_popup_draws_tables(host, tk_root):
    from ui.rich_text_utils import RichTextRenderer
    spell = RichTextRenderer().get_spell("Fireball")
    spell = copy.deepcopy(spell)
    spell.description = TEXT
    assert_drawn_as_table(popup(host, tk_root, "spell", spell, "Fireball"))


def test_a_link_inside_a_popup_table_opens_a_popup(host, tk_root, monkeypatch):
    from ui import object_link_widgets as widgets
    from magic_item import MagicItem
    opened = []
    monkeypatch.setattr(widgets, "open_link_popup", lambda parent, category, name: opened.append((category, name)))
    view = popup(host, tk_root, "magic_item", MagicItem(name="Zorblax Item", description=TEXT))
    view._open_inner_link("equipment:Club|club")
    assert opened == [("equipment", "Club")]


# --------------------------------------------------------------------------- the collection pages

def test_collection_pages_draw_tables(host, tk_root):
    from lineage import get_lineage_manager
    from background import get_background_manager
    from ui.backgrounds_view import BackgroundDetailPanel
    from ui.lineages_view import LineageDetailPanel
    lineage = copy.deepcopy(get_lineage_manager().get_lineage("Elf"))
    lineage.description = TEXT
    lineage.traits[0].description = TEXT
    panel = LineageDetailPanel(host)
    panel.pack(fill="both", expand=True)
    panel.show_lineage(lineage)
    pump(tk_root, 0.5)
    joined = "\n".join(everything_shown(panel))
    assert "|---" not in joined and joined.count("Zorblax Dagger") == 2
    panel.destroy()

    background = copy.deepcopy(get_background_manager().get_background("Acolyte"))
    background.description = TEXT
    panel = BackgroundDetailPanel(host)
    panel.pack(fill="both", expand=True)
    panel.show_background(background)
    pump(tk_root, 0.5)
    assert_drawn_as_table(panel)
    panel.destroy()


def test_monster_features_draw_tables(host, tk_root):
    from monster import get_monster_manager
    from ui.monster_stat_block import MonsterStatBlock
    monster = copy.deepcopy(get_monster_manager().get_monster("Goblin Warrior") or get_monster_manager().browsable[0])
    monster.description = TEXT
    block = MonsterStatBlock(host, monster)
    block.pack(fill="both", expand=True)
    pump(tk_root, 0.5)
    assert_drawn_as_table(block)
