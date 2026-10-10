"""Sending characters and homebrew: what travels, what is refused, and how it is applied."""

import json

import pytest

import character_io
import content_io
import transfer as X
from transfer import Managers, TransferError


@pytest.fixture()
def world(tmp_path):
    """A sender's homebrew + a character that uses some of it. Cleaned up afterwards."""
    from character import CharacterSpellList, ClassLevel
    from character_manager import CharacterManager
    from character_sheet import CharacterSheet
    from equipment import Equipment, get_equipment_manager
    from feat import Feat, get_feat_manager
    from magic_item import MagicItem, get_magic_item_manager
    from spell import CharacterClass
    from spell_manager import SpellManager
    from ui.character_sheet_view import CharacterSheetManager

    sm = SpellManager()
    sm.load_spells()
    fm, em, mm = get_feat_manager(), get_equipment_manager(), get_magic_item_manager()

    spell = sm._dict_to_spell({"name": "Zzz Bolt", "level": 1, "school": "Evocation", "casting_time": "Action",
                               "range_value": 60, "components": "V, S", "duration": "Instantaneous",
                               "description": "A bolt of test.", "classes": ["Wizard"], "tags": ["Unofficial"]})
    assert sm.add_spell(spell)

    def feat(name, desc):
        f = Feat.from_dict({"name": name, "description": desc})
        f.is_custom, f.is_official = True, False
        assert fm.add_feat(f)

    feat("Zzz Feat", "Lets you cast [[spell:Zzz Bolt]] once per day.")
    feat("Zzz Unrelated", "Nobody uses this.")

    blade = Equipment.from_dict({"name": "Zzz Blade", "type": "Weapon", "cost": "5 gp", "weight": 3})
    blade.is_custom, blade.is_official = True, False
    assert em.add_item(blade)
    ring = MagicItem.from_dict({"name": "Zzz Ring", "type": "Ring", "rarity": "Rare", "description": "Shiny."})
    ring.is_custom, ring.is_official = True, False
    assert mm.add_item(ring)

    cm = CharacterManager(str(tmp_path / "sender_chars.json"))
    shm = CharacterSheetManager(str(tmp_path / "sender_sheets.json"))
    cm.add_character(CharacterSpellList(
        name="Thorn", classes=[ClassLevel(CharacterClass.WIZARD, 5)],
        known_spells=["Zzz Bolt", "Fireball"], feats=["Zzz Feat"]))
    sheet = CharacterSheet(character_name="Thorn")
    sheet.equipment_items = [{"name": "Zzz Blade", "quantity": 1, "weight": 3}, {"name": "Longsword", "quantity": 1}]
    sheet.notes = "Wears [[magic_item:Zzz Ring]] always."
    shm.update_sheet("Thorn", sheet)

    yield {"spells": sm, "chars": cm, "sheets": shm, "tmp": tmp_path}

    sm.delete_spell("Zzz Bolt")
    fm.delete_feat("Zzz Feat")
    fm.delete_feat("Zzz Unrelated")
    em.delete_item("Zzz Blade")
    mm.delete_item("Zzz Ring")


def wire(payload):
    """What the receiver actually gets: the payload after a JSON round trip."""
    return json.loads(json.dumps(payload))


def names(content, kind):
    return sorted(r["name"] for r in (content or {}).get(kind, []))


def test_character_payload_carries_exactly_the_homebrew_it_uses(world):
    payload = X.build_character_payload(["Thorn"], world["chars"], world["sheets"], world["spells"])
    assert payload["kind"] == "character" and payload["format"] == "spellbook-transfer"
    content = payload["content"]
    assert names(content, "spells") == ["Zzz Bolt"]                       # Fireball is official: not sent
    assert names(content, "feats") == ["Zzz Feat"]                        # the unrelated feat stays home
    assert names(content, "equipment") == ["Zzz Blade"]                   # Longsword is official
    assert names(content, "magic_items") == ["Zzz Ring"]                  # found through a [[link]] in notes
    assert "Thorn" in payload["characters"]["character_sheets"]
    assert [c["name"] for c in payload["characters"]["character_spell_lists"]] == ["Thorn"]


def test_closure_follows_homebrew_that_refers_to_homebrew(world):
    """The feat links to Zzz Bolt, so even a character that only has the feat brings the spell."""
    from character import CharacterSpellList
    world["chars"].add_character(CharacterSpellList(name="Feat Only", feats=["Zzz Feat"]))
    payload = X.build_character_payload(["Feat Only"], world["chars"], world["sheets"], world["spells"])
    assert names(payload["content"], "feats") == ["Zzz Feat"]
    assert names(payload["content"], "spells") == ["Zzz Bolt"]


def test_character_with_no_homebrew_sends_no_content(world):
    from character import CharacterSpellList
    world["chars"].add_character(CharacterSpellList(name="Plain", known_spells=["Fireball"]))
    payload = X.build_character_payload(["Plain"], world["chars"], world["sheets"], world["spells"])
    assert "content" not in payload


def test_content_payload_and_parse(world):
    from feat import get_feat_manager
    fm = get_feat_manager()
    payload = X.build_content_payload({"feats": [fm.get_feat("Zzz Feat")]}, world["spells"])
    parsed = X.parse_payload(wire(payload))
    assert parsed.kind == "content" and parsed.content_counts == {"feats": 1}
    assert X.describe(parsed) == ["Feats (1): Zzz Feat"]
    with pytest.raises(TransferError):
        X.build_content_payload({}, world["spells"])


def test_parse_rejects_bad_payloads():
    good_content = {"spells": [{"name": "A"}]}
    for bad in (None, [], {}, {"format": "other"},
                {"format": X.FORMAT, "version": 99, "kind": "content", "content": good_content},
                {"format": X.FORMAT, "version": 1, "kind": "wizard"},
                {"format": X.FORMAT, "version": 1, "kind": "character"},               # no characters
                {"format": X.FORMAT, "version": 1, "kind": "content"},                 # no content
                {"format": X.FORMAT, "version": 1, "kind": "content", "content": {"nothing": []}},
                {"format": X.FORMAT, "version": 1, "kind": "content", "content": {"spells": []}},
                {"format": X.FORMAT, "version": 1, "kind": "character", "characters": {"x": 1}}):
        with pytest.raises(TransferError):
            X.parse_payload(bad)
    big = {"spells": [{"name": f"S{i}"} for i in range(X.MAX_RECORDS + 1)]}
    with pytest.raises(TransferError):
        X.parse_payload({"format": X.FORMAT, "version": 1, "kind": "content", "content": big})


def delete_homebrew(world):
    from equipment import get_equipment_manager
    from feat import get_feat_manager
    from magic_item import get_magic_item_manager
    world["spells"].delete_spell("Zzz Bolt")
    get_feat_manager().delete_feat("Zzz Feat")
    get_feat_manager().delete_feat("Zzz Unrelated")
    get_equipment_manager().delete_item("Zzz Blade")
    get_magic_item_manager().delete_item("Zzz Ring")


def receiver(world, tag):
    from character_manager import CharacterManager
    from ui.character_sheet_view import CharacterSheetManager
    cm = CharacterManager(str(world["tmp"] / f"{tag}_chars.json"))
    sh = CharacterSheetManager(str(world["tmp"] / f"{tag}_sheets.json"))
    return Managers(cm, sh, world["spells"])


def test_applying_a_character_installs_it_and_its_homebrew(world):
    from equipment import get_equipment_manager
    from feat import get_feat_manager
    from magic_item import get_magic_item_manager
    payload = wire(X.build_character_payload(["Thorn"], world["chars"], world["sheets"], world["spells"]))
    delete_homebrew(world)                                   # the receiver has none of it
    assert world["spells"].get_spell("Zzz Bolt") is None

    mgrs = receiver(world, "r1")
    parsed = X.parse_payload(payload)
    plan = X.plan_transfer(parsed, mgrs)
    assert plan.character_conflicts == []
    assert len(plan.content.new) == 4 and not plan.content.replaces

    result = X.apply_transfer(parsed, mgrs)
    assert mgrs.character_manager.get_character("Thorn") is not None
    assert mgrs.sheet_manager.get_sheet("Thorn").notes == "Wears [[magic_item:Zzz Ring]] always."
    assert world["spells"].get_spell("Zzz Bolt") is not None
    assert get_feat_manager().get_feat("Zzz Feat") is not None
    assert get_feat_manager().get_feat("Zzz Unrelated") is None      # never sent
    assert get_equipment_manager().get_item("Zzz Blade") is not None
    assert get_magic_item_manager().get_item("Zzz Ring") is not None
    assert result.characters.sheets == 1 and result.characters.spell_lists == 1
    assert any("Characters" in line for line in result.lines())
    # imported homebrew is the receiver's own, marked unofficial
    assert not world["spells"].get_spell("Zzz Bolt").is_official


def test_clashes_are_shown_and_each_choice_is_honoured(world):
    from feat import get_feat_manager
    payload = wire(X.build_character_payload(["Thorn"], world["chars"], world["sheets"], world["spells"]))
    # receiver already has a *different* "Zzz Feat" and its own "Thorn"
    fm = get_feat_manager()
    own = fm.get_feat("Zzz Feat")
    own.description = "THE RECEIVER'S OWN VERSION"
    assert fm.update_feat("Zzz Feat", own)
    assert "RECEIVER" in fm.get_feat("Zzz Feat").description
    mgrs = receiver(world, "r2")
    from character import CharacterSpellList
    mgrs.character_manager.add_character(CharacterSpellList(name="Thorn", known_spells=["Mine"]))

    parsed = X.parse_payload(payload)
    plan = X.plan_transfer(parsed, mgrs)
    assert plan.character_conflicts == ["Thorn"]
    assert ("feats", "Zzz Feat") in plan.content.replaces

    # default for a character transfer: keep the receiver's own homebrew and character (nothing lost)
    result = X.apply_transfer(parsed, mgrs, character_default=character_io.SKIP)
    assert result.characters.skipped == ["Thorn"]
    assert mgrs.character_manager.get_character("Thorn").known_spells == ["Mine"]
    assert "RECEIVER" in fm.get_feat("Zzz Feat").description          # their homebrew was not touched

    # the receiver chooses to keep both copies of the character
    result = X.apply_transfer(parsed, mgrs, character_policies={"Thorn": character_io.RENAME})
    assert result.characters.renamed == {"Thorn": "Thorn (2)"}
    assert mgrs.character_manager.get_character("Thorn (2)").known_spells == ["Zzz Bolt", "Fireball"]
    assert mgrs.character_manager.get_character("Thorn").known_spells == ["Mine"]

    # ... and explicitly choosing "replace" for that one feat swaps in the sender's version
    X.apply_transfer(parsed, mgrs, content_decisions={("feats", "zzz feat"): content_io.CLASH_REPLACE},
                     character_default=character_io.SKIP)
    assert "Lets you cast" in fm.get_feat("Zzz Feat").description


def test_standalone_homebrew_defaults_to_keeping_both(world):
    from feat import get_feat_manager
    fm = get_feat_manager()
    payload = wire(X.build_content_payload({"feats": [fm.get_feat("Zzz Feat")]}, world["spells"]))
    mgrs = receiver(world, "r3")
    result = X.apply_transfer(X.parse_payload(payload), mgrs)         # "Zzz Feat" is already there
    assert fm.get_feat("Zzz Feat (2)") is not None
    assert result.content.added.get("feats") == 1
    fm.delete_feat("Zzz Feat (2)")


def test_official_names_are_never_overwritten(world):
    payload = {"format": X.FORMAT, "version": 1, "kind": "content",
               "content": {"spells": [{"name": "Fireball", "level": 3, "description": "HACKED",
                                       "casting_time": "Action", "range_value": 150, "components": "V",
                                       "duration": "Instantaneous"}]}}
    mgrs = receiver(world, "r4")
    parsed = X.parse_payload(payload)
    assert X.plan_transfer(parsed, mgrs).content.official == [("spells", "Fireball")]
    X.apply_transfer(parsed, mgrs)
    assert "HACKED" not in world["spells"].get_spell("Fireball").description


def test_a_payload_with_a_hostile_character_is_contained(world):
    """Garbage inside an otherwise well-formed payload fails that character, not the app."""
    payload = {"format": X.FORMAT, "version": 1, "kind": "character",
               "characters": {"character_sheets": {"Evil": {"ability_scores": "nope", "hit_points": 5}},
                              "character_spell_lists": [{"name": "Evil", "classes": [{"class": "Wizard"}]}]}}
    mgrs = receiver(world, "r5")
    result = X.apply_transfer(X.parse_payload(payload), mgrs)
    assert result.characters.warnings                                  # reported, not raised
    assert result.characters.sheets == 0
