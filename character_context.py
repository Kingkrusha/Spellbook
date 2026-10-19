"""
The facts about a character that features depend on, and how each feature is recognised.

:class:`Ctx` reads a character and its sheet (classes and levels, subclasses, feats, lineage, linked magic items)
and answers questions such as "how many Rogue levels?" or "does this character have Lucky?". ``FEATURES`` lists
every feature the analyzer understands with the test that finds it on a character; anything the sheet cannot
show (a fighting style taken as a class feature, a Sorcerer's metamagic) is offered as a tick-box instead
(``manual=True``). The effects of each feature are in ``character_rules``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set, Tuple

from character_sheet import AbilityScore, Skill
from item_effects import ItemInfo

ABILITIES = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
ABILITY_NAMES = {"STR": "Strength", "DEX": "Dexterity", "CON": "Constitution",
                 "INT": "Intelligence", "WIS": "Wisdom", "CHA": "Charisma"}
ENUM = {"STR": AbilityScore.STRENGTH, "DEX": AbilityScore.DEXTERITY, "CON": AbilityScore.CONSTITUTION,
        "INT": AbilityScore.INTELLIGENCE, "WIS": AbilityScore.WISDOM, "CHA": AbilityScore.CHARISMA}
ABBR = {v: k for k, v in ENUM.items()}

_LEGACY = re.compile(r"\s*\((?:legacy[^)]*)\)", re.IGNORECASE)


def base_name(name: str) -> Tuple[str, bool]:
    """("Barbarian (Legacy)") -> ("Barbarian", True)."""
    text = (name or "").strip()
    legacy = bool(_LEGACY.search(text))
    return _LEGACY.sub("", text).strip(), legacy


class Ctx:
    """A character as the rules see it."""

    def __init__(self, character, sheet, manual: Optional[Set[str]] = None, items: Optional[List[ItemInfo]] = None,
                 disabled_items: Optional[Set[str]] = None):
        self.character = character
        self.sheet = sheet
        self.manual = set(manual or ())
        self.levels: Dict[str, int] = {}
        self.legacy_classes: Set[str] = set()
        self.subclasses: Dict[str, str] = {}
        self.class_entries: List[Tuple[str, str, int, str]] = []       # (class as written, base name, level, subclass)
        self.extra_rules: List = []                                      # homebrew d20 rules (see roll_effects)
        self.extra_damage_rules: List = []
        for cl in getattr(character, "classes", []):
            name, legacy = base_name(cl.get_class_name())
            self.class_entries.append((cl.get_class_name(), name, cl.level,
                                       base_name(getattr(cl, "subclass", "") or "")[0].lower()))
            self.levels[name] = self.levels.get(name, 0) + cl.level
            if legacy:
                self.legacy_classes.add(name)
            sub = getattr(cl, "subclass", "") or ""
            if sub:
                self.subclasses[name] = base_name(sub)[0].lower()
        self.total_level = sum(self.levels.values()) or 1
        self.prof = sheet.proficiency_bonus
        self.feats: Dict[str, bool] = {}
        for f in getattr(character, "feats", []) or []:
            name, legacy = base_name(f)
            key = name.lower()
            self.feats[key] = self.feats.get(key, False) or legacy
        self.lineage = " ".join(x for x in (getattr(character, "lineage", ""), getattr(sheet, "race", "")) if x).lower()
        self.items: List[ItemInfo] = list(items or [])
        self.disabled_items = set(disabled_items or ())

    # ---- classes
    def lvl(self, class_name: str) -> int:
        return self.levels.get(class_name, 0)

    def is_legacy(self, class_name: str) -> bool:
        return class_name in self.legacy_classes

    def sub_has(self, class_name: str, fragment: str) -> bool:
        return fragment in self.subclasses.get(class_name, "")

    # ---- feats and lineage
    def feat(self, name: str) -> bool:
        return name.lower() in self.feats

    def feat_legacy(self, name: str) -> bool:
        return self.feats.get(name.lower(), False)

    def lineage_has(self, *fragments: str) -> bool:
        return any(f in self.lineage for f in fragments)

    # ---- features
    def detected(self, feature: str) -> bool:
        f = FEATURES.get(feature)
        return bool(f and f.detect(self))

    def has(self, feature: str) -> bool:
        return feature in self.manual or self.detected(feature)

    def source(self, feature: str) -> str:
        return "sheet" if self.detected(feature) else ("manual" if feature in self.manual else "")

    # ---- magic items
    @property
    def active_items(self) -> List[ItemInfo]:
        return [i for i in self.items if i.usable and i.name not in self.disabled_items]

    def item_ability_set(self, ability: str) -> int:
        return max([i.ability_sets.get(ability, 0) for i in self.active_items] or [0])

    # ---- numbers
    def score(self, ability: str) -> int:
        base = self.sheet.get_effective_ability_score(ENUM[ability])
        return max(base, self.item_ability_set(ability))

    def mod(self, ability: str) -> int:
        return (self.score(ability) - 10) // 2

    def save_proficient(self, ability: str) -> bool:
        if self.sheet.saving_throws.is_proficient(ENUM[ability]):
            return True
        if self.lvl("Monk") >= 14 and not self.is_legacy("Monk"):
            return True                                         # Disciplined Survivor (2024) / Diamond Soul
        if self.lvl("Monk") >= 14 and self.is_legacy("Monk"):
            return True
        if self.lvl("Rogue") >= 15 and ability in ("WIS", "CHA"):
            return True                                         # Slippery Mind
        if self.lvl("Cleric") >= 6 and self.sub_has("Cleric", "knowledge") and ability == "INT" \
                and not self.is_legacy("Cleric"):
            return True                                         # Unfettered Mind
        if self.lvl("Ranger") >= 7 and self.sub_has("Ranger", "gloom") and ability == "WIS":
            return True                                         # Iron Mind
        return False

    def skill_level(self, skill: Skill) -> int:
        return self.sheet.skills.get(skill)

    def spell_attack_bonus(self, ability: str, spell_class: str = "", raw: bool = False) -> int:
        """The spell attack modifier: the number typed on the sheet if there is one, else worked out
        (``raw=True`` ignores what was typed)."""
        typed = getattr(self.sheet, "stat_overrides", {}).get(f"spell_attack:{ability}")
        if typed is not None and not raw:
            return int(typed)
        extra = 0
        for item in self.active_items:
            if item.spell_attack and (not item.spell_class or not spell_class
                                      or item.spell_class.lower() == spell_class.lower()):
                extra += item.spell_attack
        return self.prof + self.mod(ability) + extra

    def spell_dc(self, ability: str, spell_class: str = "", raw: bool = False) -> int:
        typed = getattr(self.sheet, "stat_overrides", {}).get(f"spell_dc:{ability}")
        if typed is not None and not raw:
            return int(typed)
        extra = 0
        for item in self.active_items:
            if item.spell_dc and (not item.spell_class or not spell_class
                                  or item.spell_class.lower() == spell_class.lower()):
                extra += item.spell_dc
        return 8 + self.prof + self.mod(ability) + extra

    # ---- class numbers
    def rage_damage(self) -> int:
        lvl = self.lvl("Barbarian")
        return 0 if lvl < 1 else (2 if lvl < 9 else 3 if lvl < 16 else 4)

    def sneak_dice(self) -> int:
        return (self.lvl("Rogue") + 1) // 2

    def attacks_per_turn(self) -> int:
        fighter = self.lvl("Fighter")
        n = 1 + (fighter >= 5) + (fighter >= 11) + (fighter >= 20) if fighter else 1
        if any(self.lvl(c) >= 5 for c in ("Barbarian", "Paladin", "Ranger", "Monk")):
            n = max(n, 2)
        return n

    def bardic_die(self) -> int:
        lvl = self.lvl("Bard")
        return 12 if lvl >= 15 else 10 if lvl >= 10 else 8 if lvl >= 5 else 6

    def psionic_die(self, class_name: str) -> int:
        lvl = self.lvl(class_name)
        return 12 if lvl >= 17 else 10 if lvl >= 11 else 8 if lvl >= 5 else 6

    def crit_min(self) -> int:
        if self.has("superior_critical"):
            return 18
        if self.has("improved_critical"):
            return 19
        return 20


# ----------------------------------------------------------------------------- the registry

@dataclass
class Feature:
    id: str
    label: str
    detect: Callable[[Ctx], bool]
    manual: bool = False            # offered as a tick-box when the sheet does not show it


FEATURES: Dict[str, Feature] = {}


def F(fid: str, label: str, detect: Callable[[Ctx], bool], manual: bool = False) -> None:
    FEATURES[fid] = Feature(fid, label, detect, manual)


def L(cls: str, level: int) -> Callable[[Ctx], bool]:
    return lambda c: c.lvl(cls) >= level


def S(cls: str, fragment: str, level: int = 1) -> Callable[[Ctx], bool]:
    return lambda c: c.lvl(cls) >= level and c.sub_has(cls, fragment)


def FT(*names: str) -> Callable[[Ctx], bool]:
    return lambda c: any(c.feat(n) for n in names)


def LN(*fragments: str) -> Callable[[Ctx], bool]:
    return lambda c: c.lineage_has(*fragments)


def not_legacy(cls: str, inner: Callable[[Ctx], bool]) -> Callable[[Ctx], bool]:
    return lambda c: inner(c) and not c.is_legacy(cls)


# ---- Barbarian
F("rage", "Rage", L("Barbarian", 1))
F("danger_sense", "Danger Sense", L("Barbarian", 2))
F("primal_knowledge", "Primal Knowledge", not_legacy("Barbarian", L("Barbarian", 3)))
F("feral_instinct", "Feral Instinct", L("Barbarian", 7))
F("brutal_strike", "Brutal Strike", not_legacy("Barbarian", L("Barbarian", 9)))
F("brutal_critical", "Brutal Critical", lambda c: c.is_legacy("Barbarian") and c.lvl("Barbarian") >= 9)
F("indomitable_might", "Indomitable Might", not_legacy("Barbarian", L("Barbarian", 18)))
F("frenzy", "Frenzy (Berserker)", not_legacy("Barbarian", S("Barbarian", "berserker", 3)))
F("divine_fury", "Divine Fury (Zealot)", S("Barbarian", "zealot", 3))
F("fanatical_focus", "Fanatical Focus (Zealot)", S("Barbarian", "zealot", 6))
# ---- Bard
F("jack_of_all_trades", "Jack of All Trades", L("Bard", 2))
F("peerless_skill", "Peerless Skill (College of Lore)", S("Bard", "lore", 14))
F("dazzling_footwork", "Dazzling Footwork (College of Dance)", S("Bard", "dance", 3))
F("power_from_beyond", "Empowered Channeling (College of Spirits)", S("Bard", "spirits", 6))
# ---- Cleric
F("disciple_of_life", "Disciple of Life", lambda c: c.lvl("Cleric") >= 1 and c.sub_has("Cleric", "life"))
F("supreme_healing", "Supreme Healing", lambda c: c.lvl("Cleric") >= 17 and c.sub_has("Cleric", "life"))
F("divine_foreknowledge", "Divine Foreknowledge", lambda c: c.lvl("Cleric") >= 17 and c.sub_has("Cleric", "knowledge")
  and not c.is_legacy("Cleric"))
F("guided_strike", "Guided Strike (War Domain)", S("Cleric", "war", 2))
F("blessed_strikes", "Blessed Strikes / Divine Strike", lambda c: (
    c.lvl("Cleric") >= 7 if not c.is_legacy("Cleric")
    else c.lvl("Cleric") >= 8 and not any(d in c.subclasses.get("Cleric", "") for d in (
        "arcana", "grave", "knowledge", "light", "peace", "ambition"))))
F("potent_spellcasting_cleric", "Potent Spellcasting (Cleric)", lambda c: (
    c.lvl("Cleric") >= 7 if not c.is_legacy("Cleric")
    else c.lvl("Cleric") >= 8 and any(d in c.subclasses.get("Cleric", "") for d in (
        "arcana", "grave", "knowledge", "light", "peace", "ambition"))))
F("thaumaturge", "Divine Order: Thaumaturge", lambda c: False, manual=True)
# ---- Druid
F("potent_spellcasting_druid", "Potent Spellcasting (Druid)", not_legacy("Druid", L("Druid", 7)))
F("primal_strike", "Primal Strike", not_legacy("Druid", L("Druid", 7)))
F("starry_form", "Starry Form (Circle of Stars)", lambda c: c.lvl("Druid") >= 2 and c.sub_has("Druid", "star"))
F("moon_toughness", "Increased Toughness (Circle of the Moon)", lambda c: c.lvl("Druid") >= 6 and c.sub_has("Druid", "moon")
  and not c.is_legacy("Druid"))
F("magician", "Primal Order: Magician", lambda c: False, manual=True)
# ---- Fighter
F("tactical_mind", "Tactical Mind", not_legacy("Fighter", L("Fighter", 2)))
F("indomitable", "Indomitable", L("Fighter", 9))
F("studied_attacks", "Studied Attacks", not_legacy("Fighter", L("Fighter", 13)))
F("improved_critical", "Improved Critical", lambda c: c.lvl("Fighter") >= 3 and c.sub_has("Fighter", "champion"))
F("superior_critical", "Superior Critical", lambda c: c.lvl("Fighter") >= 15 and c.sub_has("Fighter", "champion"))
F("remarkable_athlete", "Remarkable Athlete", lambda c: c.sub_has("Fighter", "champion") and (
    c.lvl("Fighter") >= 7 if c.is_legacy("Fighter") else c.lvl("Fighter") >= 3))
# ---- Monk
F("disciplined_survivor", "Disciplined Survivor", not_legacy("Monk", L("Monk", 14)))
F("hand_of_harm", "Hand of Harm (Warrior of Mercy)", lambda c: c.lvl("Monk") >= 3 and (
    c.sub_has("Monk", "mercy")))
# ---- Paladin
F("aura_of_protection", "Aura of Protection", L("Paladin", 6))
F("divine_smite", "Divine Smite", L("Paladin", 2))
F("radiant_strikes", "Radiant Strikes", L("Paladin", 11))
F("sacred_weapon", "Sacred Weapon (Devotion)", S("Paladin", "devotion", 3))
F("vow_of_enmity", "Vow of Enmity (Vengeance)", S("Paladin", "vengeance", 3))
F("peerless_athlete", "Peerless Athlete (Glory)", S("Paladin", "glory", 3))
F("living_legend", "Living Legend (Glory)", S("Paladin", "glory", 20))
F("noble_scion", "Noble Scion (Noble Genie)", S("Paladin", "genie", 20))
# ---- Ranger
F("hunters_mark", "Hunter's Mark", L("Ranger", 1))
F("precise_hunter", "Precise Hunter", not_legacy("Ranger", L("Ranger", 17)))
F("fey_wanderer", "Fey Wanderer", S("Ranger", "fey wanderer", 3))
F("dreadful_strikes", "Dreadful Strikes (Fey Wanderer)", S("Ranger", "fey wanderer", 3))
F("polar_strikes", "Polar Strikes (Winter Walker)", S("Ranger", "winter", 3))
F("hunters_prey", "Hunter's Prey", S("Ranger", "hunter", 3))
F("dread_ambusher", "Dread Ambusher (Gloom Stalker)", S("Ranger", "gloom", 3))
F("hungering_might", "Hungering Might (Hollow Warden)", S("Ranger", "hollow", 7))
# ---- Rogue
F("sneak_attack", "Sneak Attack", L("Rogue", 1))
F("steady_aim", "Steady Aim", L("Rogue", 3))
F("reliable_talent", "Reliable Talent", lambda c: c.lvl("Rogue") >= (11 if c.is_legacy("Rogue") else 7))
F("stroke_of_luck", "Stroke of Luck", L("Rogue", 20))
F("dread_incarnate", "Dread Incarnate (Scion of the Three)", S("Rogue", "scion", 17))
F("psi_bolstered_knack", "Psi-Bolstered Knack (Soulknife)", S("Rogue", "soulknife", 3))
F("homing_strikes", "Homing Strikes (Soulknife)", S("Rogue", "soulknife", 9))
F("assassinate_initiative", "Assassinate (initiative)", lambda c: c.lvl("Rogue") >= 3 and c.sub_has("Rogue", "assassin")
  and not c.is_legacy("Rogue"))
# ---- Sorcerer
F("innate_sorcery", "Innate Sorcery", not_legacy("Sorcerer", L("Sorcerer", 1)))
F("tides_of_chaos", "Tides of Chaos (Wild Magic)", lambda c: c.lvl("Sorcerer") >= 1 and c.sub_has("Sorcerer", "wild"))
F("trance_of_order", "Trance of Order (Clockwork)", lambda c: c.lvl("Sorcerer") >= 14 and c.sub_has("Sorcerer", "clockwork"))
F("elemental_affinity", "Elemental Affinity (Draconic)", lambda c: c.lvl("Sorcerer") >= 6 and c.sub_has("Sorcerer", "draconic"))
F("empowered_spell", "Metamagic: Empowered Spell", lambda c: False, manual=True)
# ---- Warlock
F("hex", "Hex", L("Warlock", 1))
F("dark_ones_own_luck", "Dark One's Own Luck (Fiend)", lambda c: c.lvl("Warlock") >= 6 and c.sub_has("Warlock", "fiend"))
F("radiant_soul", "Radiant Soul (Celestial)", lambda c: c.lvl("Warlock") >= 6 and c.sub_has("Warlock", "celestial"))
F("hexblades_curse", "Hexblade's Curse", lambda c: c.lvl("Warlock") >= 1 and c.sub_has("Warlock", "hexblade"))
F("agonizing_blast", "Agonizing Blast", FT("agonizing blast"), manual=True)
# ---- Wizard
F("bladesong", "Bladesong", lambda c: c.lvl("Wizard") >= (2 if c.is_legacy("Wizard") else 3) and c.sub_has("Wizard", "bladesing"))
F("empowered_evocation", "Empowered Evocation", lambda c: c.lvl("Wizard") >= 10 and (c.sub_has("Wizard", "evok") or c.sub_has("Wizard", "evocat")))
F("wondrous_alteration", "Wondrous Alteration (Transmuter)", lambda c: c.lvl("Wizard") >= 3 and c.sub_has("Wizard", "transmut")
  and not c.is_legacy("Wizard"))
F("tactical_wit", "Tactical Wit (War Magic)", lambda c: c.lvl("Wizard") >= 2 and c.sub_has("Wizard", "war magic"))
# ---- Artificer
F("flash_of_genius", "Flash of Genius", L("Artificer", 7))
F("arcane_firearm", "Arcane Firearm (Artillerist)", S("Artificer", "artillerist", 5))
F("arcane_jolt", "Arcane Jolt (Battle Smith)", S("Artificer", "battle smith", 9))
F("lightning_launcher", "Lightning Launcher (Armorer)", S("Artificer", "armorer", 3))
F("dampening_field", "Dampening Field (Armorer)", S("Artificer", "armorer", 3))
F("alchemical_savant", "Alchemical Savant (Alchemist)", S("Artificer", "alchemist", 5))
F("soul_of_artifice", "Soul of Artifice", lambda c: c.is_legacy("Artificer") and c.lvl("Artificer") >= 20)
# ---- feats (the sheet's feat list)
F("great_weapon_master", "Great Weapon Master", FT("great weapon master"), manual=True)
F("great_weapon_fighting", "Great Weapon Fighting", FT("great weapon fighting"), manual=True)
F("archery", "Archery", FT("archery"), manual=True)
F("dueling", "Dueling", FT("dueling"), manual=True)
F("thrown_weapon_fighting", "Thrown Weapon Fighting", FT("thrown weapon fighting"), manual=True)
F("savage_attacker", "Savage Attacker", FT("savage attacker"), manual=True)
F("lucky", "Lucky", FT("lucky"), manual=True)
F("alert", "Alert", FT("alert"), manual=True)
F("war_caster", "War Caster", FT("war caster", "eldritch mind"), manual=True)
F("elemental_adept", "Elemental Adept", FT("elemental adept"), manual=True)
F("sharpshooter", "Sharpshooter", FT("sharpshooter"))
F("elven_accuracy", "Elven Accuracy", FT("elven accuracy"), manual=True)
F("piercer", "Piercer", FT("piercer"), manual=True)
F("charger", "Charger", FT("charger"))
F("eldritch_smite", "Eldritch Smite", FT("eldritch smite"))
F("lifedrinker", "Lifedrinker", FT("lifedrinker"))
F("healer", "Healer", FT("healer"))
F("tavern_brawler", "Tavern Brawler", FT("tavern brawler"))
F("mage_slayer", "Mage Slayer", FT("mage slayer"))
F("actor", "Actor", FT("actor"))
F("skulker", "Skulker", FT("skulker"))
F("familiar_friend", "Familiar Friend", FT("familiar friend"))
F("sharp_eye", "Sharp Eye", FT("sharp eye"))
F("dungeon_delver", "Dungeon Delver", FT("dungeon delver"))
F("harper_agent", "Harper Agent", FT("harper agent"))
F("survivor_feat", "Survivor", FT("survivor"))
F("tactical_combatant", "Tactical Combatant", FT("tactical combatant"))
F("fey_pact", "Fey Pact", FT("fey pact"))
F("infernal_dragoon", "Infernal Dragoon", FT("infernal dragoon"))
F("spell_resistant", "Spell Resistant", FT("spell resistant"))
F("arcane_omens", "Arcane Omens", FT("arcane omens"))
F("symbiotic_being", "Symbiotic Being", FT("symbiotic being"))
F("aberrant_dragonmark", "Aberrant Dragonmark", FT("aberrant dragonmark"))
F("boon_of_fate", "Boon of Fate", FT("boon of fate"))
F("boon_of_combat_prowess", "Boon of Combat Prowess", FT("boon of combat prowess"))
F("boon_of_fortunes_favor", "Boon of Fortune's Favor", FT("boon of fortune's favor"))
F("boon_of_skill_proficiency", "Boon of Skill Proficiency", FT("boon of skill proficiency"))
F("boon_of_bloodshed", "Boon of Bloodshed", FT("boon of bloodshed"))
F("boon_of_furious_storm", "Boon of the Furious Storm", FT("boon of the furious storm"))
F("boon_of_poison_mastery", "Boon of Poison Mastery", FT("boon of poison mastery"))
F("zhentarim_ruffian", "Zhentarim Ruffian", FT("zhentarim ruffian"))
F("adept_red_robes", "Adept of the Red Robes", FT("adept of the red robes"))
F("squire_of_solamnia", "Squire of Solamnia", FT("squire of solamnia"))
F("orcish_fury", "Orcish Fury", FT("orcish fury"))
F("flames_of_phlegethos", "Flames of Phlegethos", FT("flames of phlegethos"))
F("grappler", "Grappler", FT("grappler"))
F("mounted_combatant", "Mounted Combatant", FT("mounted combatant"))
F("purple_dragon_commandant", "Purple Dragon Commandant", FT("purple dragon commandant"))
F("treacherous_allure", "Treacherous Allure", FT("treacherous allure"))
F("boon_of_terror", "Boon of Terror", FT("boon of terror"))
F("boon_of_revelry", "Boon of Revelry", FT("boon of revelry"))
F("arcane_eloquence", "Arcane Eloquence", FT("arcane eloquence"))
F("arcane_undertaker", "Arcane Undertaker", FT("arcane undertaker"))
F("divination_adept", "Divination Adept", FT("divination adept"))
F("pack_fighting", "Pack Fighting", FT("pack fighting"))
F("mythal_touched", "Mythal Touched", FT("mythal touched"))
# ---- species
F("halfling_luck", "Halfling Luck", LN("halfling", "kor"), manual=True)
F("gnome_cunning", "Gnomish Cunning", LN("gnome"))
F("kalashtar", "Kalashtar Dual Mind", LN("kalashtar"))
F("hare_trigger", "Hare-Trigger", LN("harengon"))
F("lucky_footwork", "Lucky Footwork", LN("harengon"))
F("savage_attacks", "Savage Attacks", LN("half-orc", "orc ", "minotaur"))
F("fury_of_the_small", "Fury of the Small", LN("goblin", "boggart"))
F("surprise_attack", "Surprise Attack (Bugbear)", LN("bugbear"))
F("celestial_revelation", "Celestial Revelation", LN("aasimar"))
F("giant_ancestry_fire", "Giant Ancestry: Fire's Burn", lambda c: False, manual=True)
F("giant_ancestry_frost", "Giant Ancestry: Frost's Chill", lambda c: False, manual=True)
F("astral_spark", "Astral Spark", LN("giff"))
F("reborn", "Knowledge from a Past Life", LN("reborn"))
F("built_for_success", "Built for Success", LN("autognome"))
F("hobgoblin_fortune", "Fortune from the Many", LN("hobgoblin"))
F("kefnets_blessing", "Kefnet's Blessing", LN("ibis-headed"))
F("pallid_elf", "Incisive Sense", LN("pallid"))
F("deep_gnome", "Svirfneblin Camouflage", LN("deep gnome"))
F("hippo_build", "Hippo Build", LN("giff"))
F("sunlight_sensitivity", "Sunlight Sensitivity", LN("dark elf", "drow", "duergar", "kobold", "mul daya"))
F("pack_tactics", "Pack Tactics", LN("kobold"))
F("goliath", "Goliath", LN("goliath"))
F("shifter", "Shifter", LN("shifter"))
F("duskling", "Duskling", LN("duskling"))
F("changeling", "Changeling", LN("changeling"))
F("kenku", "Kenku Recall", LN("kenku"))
F("draconblood", "Forceful Presence", LN("draconblood"))
F("firbolg", "Speech of Beast and Leaf", LN("firbolg"))
F("dwarf_poison", "Dwarven Resilience", LN("dwarf", "duergar", "warforged", "stout", "yuan-ti", "autognome", "plasmoid"))

DRAGONMARKS = {
    "detection": (("Investigation", "Insight"), "INT"),
    "finding": (("Perception", "Survival"), ""),
    "handling": (("Nature", "Animal Handling"), ""),
    "healing": (("Medicine",), ""),
    "hospitality": (("Persuasion",), ""),
    "making": (("Arcana",), ""),
    "passage": (("Athletics", "Acrobatics"), ""),
    "scribing": (("History",), ""),
    "sentinel": (("Insight", "Perception"), ""),
    "shadow": (("Stealth", "Performance"), ""),
    "storm": (("Acrobatics",), ""),
    "warding": (("Investigation",), ""),
}
for _mark in DRAGONMARKS:
    F(f"mark_{_mark}", f"Mark of {_mark.title()}",
      (lambda m: lambda c: c.feat(f"mark of {m}") or c.lineage_has(f"mark of {m}"))(_mark))
    F(f"greater_mark_{_mark}", f"Greater Mark of {_mark.title()}",
      (lambda m: lambda c: c.feat(f"greater mark of {m}"))(_mark))


def feature_label(fid: str) -> str:
    f = FEATURES.get(fid)
    return f.label if f else fid


def manual_features() -> List[Feature]:
    """The features offered as tick-boxes (things a sheet cannot always show)."""
    return [f for f in FEATURES.values() if f.manual]
