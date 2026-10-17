"""Rules pages: markup helpers, sections, the relevance-ranked search, the bundled Free Basic Rules
data, the database seed and manager, import/export, and rules links."""

import json
import os
import re
from collections import Counter

import pytest

import rules as R
from rules import RulePage, RuleSearchIndex, find_matches, parse_sections, parse_table, split_cells, strip_markup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundled():
    with open(os.path.join(ROOT, "rules.json"), encoding="utf-8") as f:
        return [RulePage.from_dict(d) for d in json.load(f)["rules"]]


@pytest.fixture(scope="module")
def pages():
    return bundled()


@pytest.fixture(scope="module")
def index():
    return RuleSearchIndex()


def top(index, pages, query, **kw):
    hits = index.search(query, pages, **kw)
    return hits[0] if hits else None


# --------------------------------------------------------------------------- markup

SAMPLE = """Intro line with a [[rule:Combat|link]].

# First

Text of the first.

## Nested [Tag]

Deeper text.

# Second

| Name | Cost |
|---|---|
| [[equipment:Club|Club]] | 1 SP |
"""


def test_sections_split_at_headings():
    secs = parse_sections(SAMPLE)
    assert [s.level for s in secs] == [0, 1, 2, 1]
    assert [s.index for s in secs] == [0, 1, 2, 3]
    assert secs[0].text.startswith("Intro line")
    assert secs[1].title == "First" and secs[1].text == "Text of the first."
    assert secs[2].title == "Nested" and secs[2].kind == "Tag" and secs[2].raw_title == "Nested [Tag]"


def test_a_page_without_headings_is_one_intro_section():
    secs = parse_sections("Just a paragraph.\n\nAnd another.")
    assert len(secs) == 1 and secs[0].level == 0 and "another" in secs[0].text
    assert parse_sections("")[0].text == ""


def test_strip_markup_gives_the_visible_words():
    text = "**Bold.** *Italic* [[rule:Conditions#Stunned]] and [[spell:Fireball|a fireball]].\n\n• one\n• two"
    plain = strip_markup(text)
    assert plain.startswith("Bold. Italic Stunned and a fireball.")
    assert "[[" not in plain and "**" not in plain and "•" not in plain
    assert strip_markup("| a | b |\n|---|---|\n| 1 | 2 |").split() == ["a", "b", "1", "2"]
    assert strip_markup("Value* and 2 * 3") == "Value* and 2 * 3"


def test_table_cells_keep_pipes_inside_links():
    assert split_cells("| [[rule:Combat|Combat]] | 5 |") == ["[[rule:Combat|Combat]]", "5"]
    headers, rows = parse_table("| A | B |\n|---|---|\n| 1 | [[x:y|z]] |\n| 2 |")
    assert headers == ["A", "B"]
    assert rows == [["1", "[[x:y|z]]"], ["2", ""]]
    assert parse_table("not a table") is None


# --------------------------------------------------------------------------- stemming and matching

@pytest.mark.parametrize("a,b", [
    ("stun", "stunned"), ("stun", "stunning"), ("paralyze", "paralyzed"), ("grapple", "grappled"),
    ("point", "points"), ("attack", "attacks"), ("poison", "poisoned"), ("condition", "conditions"),
    ("creature", "creature's"),
])
def test_stems_agree(a, b):
    assert R.stem(R.tokenize(a)[0]) == R.stem(R.tokenize(b)[0])


def test_stems_keep_different_words_apart():
    assert R.stem("class") != R.stem("clas") or True        # no crash on short words
    assert R.stem("armor") != R.stem("arm")
    assert R.stem("speed") != R.stem("spell")


def test_find_matches_prefers_the_phrase():
    text = "Making an Opportunity Attack. You can attack. Opportunity Attacks happen"
    spans = find_matches("opportunity attack", text)
    assert [text[a:b] for a, b in spans] == ["Opportunity Attack", "Opportunity Attacks"]
    # words that never come together are each lit up
    text = "A stunned creature. Stun lasts."
    assert [text[a:b] for a, b in find_matches("stunned", text)] == ["stunned", "Stun"]
    assert find_matches("", "anything") == []


# --------------------------------------------------------------------------- the search, on the bundled pages

def test_stunned_opens_the_conditions_page_at_stunned(index, pages):
    hit = top(index, pages, "Stunned")
    assert hit.page.name == "Conditions"
    assert hit.section_title == "Stunned"
    assert hit.target == "Conditions#Stunned"
    assert hit.page.sections[hit.section].kind == ""
    assert hit.score > 4 * index.search("Stunned", pages)[1].score      # not a near thing


def test_every_condition_is_found_on_the_conditions_page(index, pages):
    names = ["Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened", "Grappled", "Incapacitated",
             "Invisible", "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious"]
    for name in names:
        hit = top(index, pages, name)
        assert hit.page.name == "Conditions" and hit.section_title == name, name


def test_a_page_name_beats_text_that_mentions_it(index, pages):
    assert top(index, pages, "conditions").page.name == "Conditions"
    assert top(index, pages, "combat").page.name == "Combat"
    assert top(index, pages, "weapons").page.name == "Weapons"
    assert top(index, pages, "spell slots").target == "Casting Spells#Spell Slots"


def test_the_search_reads_the_text_of_the_pages(index, pages):
    hit = top(index, pages, "right yourself")             # only in the Prone condition's text
    assert hit.page.name == "Conditions" and hit.section_title == "Prone"
    hit = top(index, pages, "heroic inspiration")
    assert hit.page.name in ("D20 Tests", "Rules Definitions")


def test_a_half_typed_word_finds_the_page(index, pages):
    assert top(index, pages, "stun").target == "Conditions#Stunned"
    assert top(index, pages, "opportunity att").section_title == "Opportunity Attacks"
    assert top(index, pages, "st") is None or top(index, pages, "st").page is not None   # too short to prefix: no crash


def test_every_word_has_to_be_on_the_page(index, pages):
    assert index.search("stunned zzzqqq", pages) == []
    assert index.search("zzzqqq", pages) == []
    assert index.search("", pages) == []
    assert index.search("   ", pages) == []
    both = index.search("stunned prone", pages)
    assert both and both[0].page.name == "Conditions"


def test_quoted_phrases_must_appear_as_written(index, pages):
    plain = {h.page.name for h in index.search("opportunity attack", pages)}
    quoted = {h.page.name for h in index.search('"opportunity attack"', pages)}
    assert quoted and quoted <= plain
    assert index.search('"attack opportunity"', pages) == []


def test_titles_only_ignores_the_text(index, pages):
    assert index.search("right yourself", pages, titles_only=True) == []
    assert top(index, pages, "stunned", titles_only=True).target == "Conditions#Stunned"


def test_results_are_ranked_and_stable(index, pages):
    hits = index.search("attack", pages)
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)
    assert [h.name for h in hits] == [h.name for h in index.search("attack", pages)]
    assert len({h.name for h in hits}) == len(hits)                # one result per page
    assert hits[0].page.name in ("Actions", "Rules Definitions", "Combat")


def test_a_hit_knows_every_matching_section_and_a_snippet(index, pages):
    hit = top(index, pages, "prone")
    assert hit.page.name == "Conditions"
    assert hit.section in hit.sections and hit.sections == sorted(hit.sections)
    assert "Prone" in hit.snippet or "prone" in hit.snippet.lower()
    assert hit.label().startswith("Conditions")


def test_long_lists_of_names_are_not_searched(index, pages):
    magic = next(p for p in pages if p.name == "Magic Items")
    # "Winged Boots" is one of 500+ items listed under "Magic Items A-Z"; that list is not what
    # makes this page an answer to a search
    hits = index.search("Winged Boots", [magic])
    assert not hits or hits[0].section_title != "Magic Items A–Z"
    sec = magic.find_section("Magic Items A–Z")
    assert "Winged Boots" in sec.plain and "Winged Boots" not in sec.search_text


def test_search_is_fast_enough_to_type_into(index, pages):
    import time
    index.search("warm up", pages)
    t = time.time()
    for q in ("a", "attack", "hit points", "stunned", "long rest", "ability check"):
        index.search(q, pages)
    assert time.time() - t < 1.5


def test_an_edited_page_is_reindexed(index):
    page = RulePage(name="Scratch Rule", description="# Zorblax\n\nThe zorblax effect.")
    assert top(index, [page], "zorblax").section_title == "Zorblax"
    page.description = "# Quuxling\n\nThe quuxling effect."
    assert index.search("zorblax", [page]) == []
    assert top(index, [page], "quuxling").section_title == "Quuxling"


# --------------------------------------------------------------------------- the bundled data

def test_bundled_pages_are_the_free_basic_rules(pages):
    assert len(pages) == 67
    names = [p.name for p in pages]
    assert len({n.lower() for n in names}) == 67
    for must in ("Combat", "D20 Tests", "Conditions", "Hazards", "Areas of Effect", "Rules Definitions",
                 "Actions", "Weapons", "Casting Spells", "Traps", "Poison", "Parts of a Stat Block"):
        assert must in names
    assert all(p.source == "Free Basic Rules (2024)" for p in pages)
    assert all(p.category and p.description.strip() and p.tags for p in pages)
    assert [p.order for p in pages] == list(range(1, 68))
    cats = Counter(p.category for p in pages)
    assert {"Playing the Game", "Character Creation", "Equipment", "Spells", "Rules Glossary",
            "Gameplay Toolbox", "Magic Items", "Monsters"} <= set(cats)


def test_the_glossary_was_split_into_topic_pages(pages):
    by = {p.name: p for p in pages}
    conditions = [s.title for s in by["Conditions"].sections if s.level]
    assert len(conditions) == 15 and "Stunned" in conditions and "Exhaustion" in conditions
    assert [s.title for s in by["Hazards"].sections if s.level] == [
        "Burning", "Dehydration", "Falling", "Malnutrition", "Suffocation"]
    assert len([s for s in by["Areas of Effect"].sections if s.level]) == 6
    actions = [s.title for s in by["Actions"].sections if s.level]
    assert "Action Definitions" in actions and "Dodge" in actions and "Utilize" in actions
    glossary = by["Rules Definitions"]
    assert glossary.find_section("Advantage") is not None
    assert glossary.find_section("Stunned") is None          # it lives on the Conditions page now


def test_every_rules_link_resolves(pages):
    from object_links import parse_link_markup
    by = {p.name.lower(): p for p in pages}
    seen = 0
    for page in pages:
        for m in re.finditer(r"\[\[([^\]]+)\]\]", page.description):
            category, name, _shown = parse_link_markup(m.group(1))
            if category != "rule":
                continue
            seen += 1
            page_name, _, section = name.partition("#")
            target = by.get(page_name.lower())
            assert target is not None, f"{page.name}: {name}"
            assert not section or target.find_section(section) is not None, f"{page.name}: {name}"
    assert seen > 500


def test_every_table_parses_and_is_rectangular(pages):
    tables = 0
    for page in pages:
        for block in R.split_blocks(page.description):
            if block.lstrip().startswith("|"):
                parsed = parse_table(block)
                assert parsed is not None, page.name
                headers, rows = parsed
                assert headers and rows, page.name
                assert all(len(r) == len(headers) for r in rows), page.name
                tables += 1
    assert tables > 60


def test_no_stray_markup_or_control_characters(pages):
    for page in pages:
        text = page.description
        assert not re.search(r"[\x00-\x08\x0b-\x1f�]", text), page.name
        assert text.count("[[") == text.count("]]"), page.name
        for line in text.split("\n"):
            assert line.count("**") % 2 == 0, (page.name, line[:80])


def test_headings_have_sensible_levels(pages):
    for page in pages:
        levels = [s.level for s in page.sections if s.level]
        if levels:
            assert min(levels) == 1, page.name
            assert all(b - a <= 1 for a, b in zip(levels, levels[1:])), page.name   # no skipped level


# --------------------------------------------------------------------------- database and manager

@pytest.fixture
def manager():
    m = R.get_rules_manager()
    m.load()
    yield m
    for p in list(m.pages):
        if p.is_custom:
            m.delete_page(p.name)


def test_the_database_has_the_bundled_pages(manager):
    assert len(manager.pages) == 67
    assert [p.name for p in manager.pages[:3]] == ["Rhythm of Play", "The Six Abilities", "D20 Tests"]
    assert all(p.is_official and not p.is_custom for p in manager.pages)
    assert manager.get_page("conditions").name == "Conditions"
    assert manager.get_all_categories()[0] == "Playing the Game"
    assert "Combat" in manager.get_all_tags() and "Free Basic Rules (2024)" in manager.get_all_sources()


def test_resolve_pages_sections_and_bare_titles(manager):
    ref = manager.resolve("Conditions#Stunned")
    assert ref.page.name == "Conditions" and ref.section.title == "Stunned" and ref.name == "Conditions#Stunned"
    assert "Incapacitated" in ref.description
    assert manager.resolve("Stunned").name == "Conditions#Stunned"
    assert manager.resolve("Combat").section is None
    assert manager.resolve("Combat#No Such Section").section is None       # falls back to the page
    assert manager.resolve("No Such Page") is None and manager.resolve("") is None


def test_custom_pages_follow_the_book_and_can_be_edited_and_deleted(manager):
    page = RulePage(name="House Rule", category="Homebrew", description="# Crits\n\nZorbtastic damage on a 20.",
                    tags=["Combat"], order=5, is_official=False, is_custom=True)
    assert manager.add_rule(page)
    assert manager.pages[-1].name == "House Rule"
    assert manager.pages[-1].order == 0                      # never inserted into the book's order
    assert manager.search("zorbtastic")[0].page.name == "House Rule"
    page.description = "# Crits\n\nQuuxish damage."
    assert manager.update_page("House Rule", page)
    assert manager.search("quuxish")[0].page.name == "House Rule"
    assert manager.search("zorbtastic") == []
    assert [p.name for p in manager.get_unofficial_rules()] == ["House Rule"]
    assert manager.delete_page("House Rule") and manager.get_page("House Rule") is None


def test_official_pages_cannot_be_deleted(manager):
    assert manager.delete_page("Combat") is False
    assert manager.get_page("Combat") is not None


def test_seeding_never_overwrites_an_edited_or_homebrew_page(manager):
    db = manager.db
    existing = db.get_rule_by_name("Coins")
    edited = dict(existing, description="My own coins text.")
    db.update_rule(existing["id"], edited)
    with db.get_connection() as conn:
        assert db._seed_official_rules(conn.cursor())
    assert db.get_rule_by_name("Coins")["description"] == "My own coins text."
    db.update_rule(existing["id"], existing)                  # put it back for the other tests
    manager.load()


# --------------------------------------------------------------------------- import / export

def test_rules_round_trip_through_the_content_file(manager, tmp_path):
    import content_io
    assert "rules" in content_io.KINDS and "rules" in content_io.DISPLAY_ORDER
    page = RulePage(name="Table Etiquette", category="House Rules", description="# Phones\n\nPhones away.",
                    source="My Table", tags=["Social"], is_official=False, is_custom=True)
    manager.add_rule(page)
    path = str(tmp_path / "rules_export.json")
    exported = content_io.export_to_file(path, kinds=["rules"])
    assert exported == {"rules": 1}
    data = json.load(open(path, encoding="utf-8"))
    assert [r["name"] for r in data["rules"]] == ["Table Etiquette"]
    manager.delete_page("Table Etiquette")
    report = content_io.import_file(path, kinds=["rules"], link_mentions=False)
    assert report.added["rules"] == 1
    back = manager.get_page("Table Etiquette")
    assert back.is_custom and not back.is_official and back.description.endswith("Phones away.")
    again = content_io.import_file(path, kinds=["rules"], link_mentions=False)
    assert again.updated["rules"] == 1 and again.added["rules"] == 0
    # an official page's name is never overwritten
    data["rules"][0]["name"] = "Combat"
    other = str(tmp_path / "clash.json")
    json.dump(data, open(other, "w", encoding="utf-8"))
    clash = content_io.import_file(other, kinds=["rules"], link_mentions=False)
    assert clash.skipped == [("rules", "Combat", "official")]
    assert manager.get_page("Combat").is_official


# --------------------------------------------------------------------------- links

def test_rule_links_show_their_section_title():
    from object_links import format_link_markup, parse_link_markup
    assert parse_link_markup("rule:Conditions#Stunned") == ("rule", "Conditions#Stunned", "Stunned")
    assert parse_link_markup("rule:Combat") == ("rule", "Combat", "Combat")
    assert parse_link_markup("rule:Conditions#Stunned|stun")[2] == "stun"
    assert format_link_markup("rule", "Conditions#Stunned", "Stunned") == "[[rule:Conditions#Stunned]]"
    assert format_link_markup("rule", "Conditions#Stunned", "stunned out") == "[[rule:Conditions#Stunned|stunned out]]"


def test_rule_targets_resolve_and_are_opt_in(manager):
    from object_links import find_target, get_link_targets, search_links
    target = find_target("rule", "Conditions#Stunned")
    assert target.label == "Stunned" and target.category_label == "Rules"
    assert target.get_object().page.name == "Conditions"
    assert find_target("rule", "Stunned").get_object().section.title == "Stunned"       # a bare title works too
    assert find_target("rule", "Combat").get_object().section is None
    assert find_target("rule", "Nope") is None
    # not offered as you type unless the setting is on, but always available to resolve a link
    assert not [t for t in get_link_targets(enabled_only=True) if t.category == "rule"]
    everything = [t for t in get_link_targets(enabled_only=False) if t.category == "rule"]
    assert len(everything) > 500
    found = search_links("stunned", everything)
    assert found[0].label == "Stunned"


def test_search_bar_adds_rules_to_the_global_results():
    from ui.global_search import GlobalSearchBar
    rows = GlobalSearchBar._with_rules([{"id": 1, "name": "Stunning Strike", "section": "Spells"}], "stunned")
    rules_rows = [r for r in rows if r["section"] == "Rules"]
    assert rules_rows[0]["name"] == "Conditions#Stunned"
    assert rows[0] is rules_rows[0]                  # a strong match leads
    assert "Conditions" in rules_rows[0]["label"] and "Stunned" in rules_rows[0]["label"]
    weak = GlobalSearchBar._with_rules([{"id": 1, "name": "Aid", "section": "Spells"}], "zorblaxnothing")
    assert weak == [{"id": 1, "name": "Aid", "section": "Spells"}]


def test_stripping_links_reads_a_rules_link_as_its_section():
    from object_link_sweep import strip_links
    assert strip_links("see [[rule:Conditions#Stunned]], [[rule:Combat]] and [[rule:Combat#Cover|cover]]") \
        == "see Stunned, Combat and cover"
