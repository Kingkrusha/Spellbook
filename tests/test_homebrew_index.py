"""The Homebrew Studio's similarity index: finding content that already does what a draft does."""

import pytest

import homebrew_index as H
from homebrew_index import Unit


@pytest.fixture(scope="module")
def index():
    from spell_manager import SpellManager
    sm = SpellManager()
    sm.load_spells()
    return H.HomebrewIndex().build(sm), sm


# --------------------------------------------------------------------------- reading rules text

def test_plain_removes_link_markup_and_emphasis():
    assert H.plain("Cast [[spell:Fireball]] or [[spell:Shield|a shield]] with **great** care.") == \
        "Cast Fireball or a shield with great care."
    assert H.plain("See [[rule:Conditions#Stunned]].") == "See Stunned."


def test_words_drops_filler_and_stems():
    ws = H.words("When you are stunned, you can't take actions.")
    assert "stun" in ws and "action" in ws
    assert "you" not in ws and "the" not in ws


@pytest.mark.parametrize("text, tag", [
    ("You can treat a d20 roll of 9 or lower as a 10.", "min_d20"),
    ("Treat any roll on a d20 lower than a 10 as a 10.", "min_d20"),
    ("You have resistance to fire damage.", "resist:fire"),
    ("You are immune to poison damage and the poisoned condition.", "immune:poison"),
    ("You have advantage on saving throws against being frightened.", "adv:saves"),
    ("You have disadvantage on attack rolls while in sunlight.", "dis:attacks"),
    ("You have darkvision out to 60 feet.", "sense:darkvision"),
    ("As a bonus action, you become invisible.", "invisible"),
    ("You gain a fly speed equal to your walking speed.", "fly"),
    ("When you drop to 0 hit points, you instead drop to 1 hit point.", "death"),
    ("You regain hit points equal to your level.", "heal"),
])
def test_mechanics_reads_the_effect(text, tag):
    assert tag in H.mechanics(text)


def test_mechanics_does_not_invent_effects():
    tags = H.mechanics("The tavern smells of old ale and woodsmoke.")
    assert not [t for t in tags if not H.tag_is_weak(t)]


def test_unrelated_wording_of_the_same_effect_shares_a_tag():
    a = H.mechanics("Whenever you make an ability check, you can treat a d20 roll of 9 or lower as a 10.")
    b = H.mechanics("Any d20 roll lower than 10 counts as a 10 for Perception checks.")
    assert "min_d20" in a and "min_d20" in b


# --------------------------------------------------------------------------- the index

def test_every_collection_is_indexed(index):
    idx, _sm = index
    stats = idx.stats()
    for family in H.FAMILIES:
        assert stats.get(family, 0) > 20, family


def test_the_example_from_the_design_brief(index):
    """A magic item that treats a d20 below 10 as a 10 for Perception must bring up Reliable Talent and Silver Tongue."""
    idx, _sm = index
    found = idx.similar("treat any roll on a d20 lower than a 10 as a 10 for perception checks")
    titles = [m.entry.title for m in found[:6]]
    assert "Reliable Talent" in titles
    assert "Silver Tongue" in titles
    top = found[0]
    assert any("d20" in label for label in top.shared_tags)
    assert top.snippet and top.spans


def test_the_match_names_what_it_has_in_common(index):
    idx, _sm = index
    m = idx.similar("You have resistance to fire damage.")[0]
    assert "resistance to fire damage" in m.shared_tags
    assert "fire" in m.shared_terms


def test_nonsense_finds_nothing(index):
    idx, _sm = index
    assert idx.similar("xyzzy plugh quux frobnicate") == []


def test_families_filter_the_results(index):
    idx, _sm = index
    found = idx.similar("You gain darkvision out to 60 feet.", families=["spells"])
    assert found and all(m.entry.family == "spells" for m in found)


def test_legacy_content_can_be_left_out(index):
    idx, _sm = index
    with_legacy = idx.similar("treat a d20 roll of 9 or lower as a 10", include_legacy=True, limit=20)
    without = idx.similar("treat a d20 roll of 9 or lower as a 10", include_legacy=False, limit=20)
    assert any(m.entry.legacy for m in with_legacy)
    assert not any(m.entry.legacy for m in without)


def test_a_draft_is_not_matched_with_its_own_published_copy(index):
    idx, _sm = index
    custom = [e for e in idx.entries if e.custom][:1]
    # nothing in the shipped data is custom; exercise the exclusion function directly
    entry = idx.entries[0]
    exclude = lambda e: e.owner == entry.owner
    found = idx.similar(entry.text, exclude=exclude, limit=20)
    assert all(m.entry.owner != entry.owner for m in found)
    assert custom == []


def test_each_part_of_a_draft_is_compared_on_its_own(index):
    idx, _sm = index
    units = [Unit("Steady Hands", "You can treat a d20 roll of 9 or lower as a 10 on Dexterity checks."),
             Unit("Stone Skin", "You have resistance to bludgeoning, piercing and slashing damage from nonmagical attacks.")]
    found = idx.similar_to_draft(units, limit=30)
    by_unit = {m.matched_unit for m in found}
    assert by_unit == {"Steady Hands", "Stone Skin"}
    assert any(m.entry.title == "Reliable Talent" and m.matched_unit == "Steady Hands" for m in found)


def test_a_single_part_draft_does_not_label_its_matches(index):
    idx, _sm = index
    found = idx.similar_to_draft([Unit("Lucky Charm", "You can reroll one attack roll or saving throw.")])
    assert found and all(m.matched_unit == "" for m in found)


def test_title_search_finds_features_inside_classes(index):
    idx, _sm = index
    found = idx.find_title("reliable talent")
    assert found and found[0].title == "Reliable Talent"
    assert found[0].owner == "Rogue" and found[0].family == "class_features"
    assert idx.find_title("") == []


def test_snippet_lights_up_the_shared_words():
    text = "First sentence is long and says nothing. You can treat a d20 roll of 9 or lower as a 10. Another one."
    snippet, spans = H.snippet_for(text, {"treat", "d20", "lower"})
    assert "d20" in snippet
    assert {snippet[a:b] for a, b in spans} >= {"treat", "d20", "lower"}


def test_the_signature_notices_new_content(index):
    idx, sm = index
    assert not idx.is_stale(sm)
    from magic_item import MagicItem, Rarity, get_magic_item_manager
    mgr = get_magic_item_manager()
    item = MagicItem(name="Index Test Charm", type="Wondrous Item", description="A charm used by a test.",
                     rarity=Rarity.COMMON, is_official=False, is_custom=True)
    mgr.add_item(item)
    try:
        assert idx.is_stale(sm)
    finally:
        mgr.delete_item("Index Test Charm")
    assert not idx.is_stale(sm)


# --------------------------------------------------------------------------- strictness

def test_a_match_needs_enough_words_in_common(index):
    idx, _sm = index
    text = "You gain darkvision out to 60 feet."
    assert idx.similar(text)                                    # two words in common: fine for the engine's default
    assert idx.similar(text, min_words=4) == []
    found = idx.similar("treat any roll on a d20 lower than a 10 as a 10 for perception checks", min_words=4)
    assert found and all(len(m.shared_terms) >= 4 for m in found)
    assert "Reliable Talent" in [m.entry.title for m in found]


def test_content_with_exactly_the_same_text_can_be_hidden(index):
    idx, _sm = index
    reliable = next(e for e in idx.entries if e.title == "Reliable Talent" and e.owner == "Rogue")
    assert reliable.title in [m.entry.title for m in idx.similar(reliable.text)]
    shown = idx.similar(reliable.text, hide_exact=True)
    assert all(m.entry.id != reliable.id for m in shown)
    # case, spacing and punctuation do not make it different
    assert all(m.entry.id != reliable.id for m in idx.similar("  " + reliable.text.upper() + "  ", hide_exact=True))
    assert shown                                               # similar content is still found


def test_unofficial_content_is_only_compared_on_request(index):
    idx, _sm = index
    from copy import copy
    original = next(e for e in idx.entries if e.title == "Reliable Talent" and e.owner == "Rogue")
    homebrew = copy(original)
    homebrew.id = len(idx.entries)
    homebrew.title, homebrew.owner, homebrew.official, homebrew.custom = "Steady Talent", "Homebrew Rogue", False, True
    idx.entries.append(homebrew)
    for word, entries in idx._postings.items():
        if word in homebrew.terms:
            entries.append((homebrew.id, homebrew.terms[word]))
    idx._weight.append(idx._weight[original.id])
    for tag in homebrew.tags:
        idx._tag_postings[tag].append(homebrew.id)
    try:
        text = "You can treat a d20 roll of 9 or lower as a 10 on ability checks."
        assert "Steady Talent" in [m.entry.title for m in idx.similar(text, include_unofficial=True)]
        assert "Steady Talent" not in [m.entry.title for m in idx.similar(text, include_unofficial=False)]
        assert "Reliable Talent" in [m.entry.title for m in idx.similar(text, include_unofficial=False)]
    finally:
        idx.entries.pop()
        idx._weight.pop()
        for word, entries in idx._postings.items():
            if entries and entries[-1][0] == homebrew.id:
                entries.pop()
        for tag in homebrew.tags:
            if idx._tag_postings[tag] and idx._tag_postings[tag][-1] == homebrew.id:
                idx._tag_postings[tag].pop()


def test_every_shipped_entry_is_tagged_official(index):
    idx, _sm = index
    assert all(e.official for e in idx.entries if not e.custom)
    assert sum(1 for e in idx.entries if e.official) > 8000


def test_standard_wording_is_left_out_when_it_matches_too_much(index):
    idx, _sm = index
    wording = [Unit("Warding", "The target must make a Wisdom saving throw or be frightened until the end of its next turn."),
               Unit("Steady Hands", "You can treat a d20 roll of 9 or lower as a 10 on Dexterity checks.")]
    unlimited = idx.similar_to_draft(wording, limit=30, min_words=4, min_score=30)
    assert {m.matched_unit for m in unlimited} == {"Warding", "Steady Hands"}
    strict = idx.similar_to_draft(wording, limit=30, min_words=4, min_score=30, max_matches=10)
    assert [name for name, _n in strict.omitted] == ["Warding"]                 # too many things say this
    assert {m.matched_unit for m in strict} == {"Steady Hands"}                 # the rare idea still shows
    assert all(count > 10 for _n, count in strict.omitted)
    assert idx.similar_to_draft(wording, limit=30, min_words=4, min_score=30, max_matches=0).omitted == []
