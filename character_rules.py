"""
The tables of what class, feat and species features do to a character's dice.

``D20_RULES`` are the effects on d20 rolls (checks, saves, initiative, attack and spell attack rolls): advantage,
flat and dice bonuses, treating low rolls as higher ones, and "if the roll fails" options. ``DAMAGE_RULES`` are the
extra damage (and healing) dice features add to weapon attacks and spells. A rule applies when the character has
its feature (see ``character_context``) and the roll looks like the one it is written for; a rule with a
``toggle`` is a choice for that roll ("Vow of Enmity: against your sworn enemy").

Both 2024 and 2014 ("Legacy") versions are covered where they differ; the character's class and feat entries say
which one applies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, Union

from character_context import DRAGONMARKS, Ctx
from roll_rules import (ADV, DIS, Eff, RESCUE_SET20, RESCUE_SUCCEED, DmgCtx, DmgRule, Rule, die, flat, fs,
                        minimum, reroll)

D20_RULES: List[Rule] = []


def R(rid: str, label: str, feature: str, kinds, effects, *, skills=None, abilities=None, conc=None, proficient=None,
      ranged=None, vs: str = "", toggle=None, default: bool = False, when=None, spell_class: str = "") -> None:
    D20_RULES.append(Rule(
        id=rid, label=label, feature=feature, kinds=tuple(kinds), skills=skills, abilities=abilities, conc=conc,
        proficient=proficient, ranged=ranged, vs=vs, effects=tuple(effects), toggle=bool(toggle),
        toggle_label=toggle if isinstance(toggle, str) else label, default=default, when=when,
        spell_class=spell_class))


def rescue_fn(fn: Callable[[Ctx], Tuple[int, int, int]]) -> Eff:
    return Eff("rescue_add", fn)


def reroll_plus(fn: Callable[[Ctx], int]) -> Eff:
    return Eff("rescue_reroll", fn)


def lineage(*fragments: str) -> Callable[[Ctx], bool]:
    return lambda c: c.lineage_has(*fragments)


CHECK = ("check",)
SAVE = ("save",)
ATTACK = ("attack",)
D20TEST = ("check", "save", "attack")
CHA_SKILLS = fs("Deception", "Intimidation", "Performance", "Persuasion")

# ============================================================================= ability checks and skills
R("actor", "Actor: Advantage while impersonating someone", "actor", CHECK, [ADV], skills=fs("Deception", "Performance"),
  toggle="Actor: impersonating someone (Advantage)")
R("skulker", "Skulker: Advantage on Stealth to hide in combat", "skulker", CHECK, [ADV], skills=fs("Stealth"),
  toggle="Skulker: hiding during combat (Advantage)")
R("familiar_friend", "Familiar Friend: Advantage on a proficient skill", "familiar_friend", CHECK, [ADV],
  proficient=True, toggle="Familiar Friend: your familiar is within 5 feet (Advantage)")
R("sharp_eye", "Sharp Eye: Advantage on a Search or Study check", "sharp_eye", CHECK, [ADV],
  toggle="Sharp Eye: the Search or Study action (Advantage)")
R("dungeon_delver", "Dungeon Delver: Advantage on checks for secret doors", "dungeon_delver", CHECK, [ADV],
  skills=fs("Perception", "Investigation"), toggle="Dungeon Delver: detecting secret doors (Advantage)")
R("dungeon_delver_traps", "Dungeon Delver: Advantage on saves against traps", "dungeon_delver", SAVE, [ADV],
  toggle="Dungeon Delver: saving against a trap (Advantage)")
R("kenku_recall", "Kenku Recall: Advantage on a proficient skill check", "", CHECK, [ADV], proficient=True,
  when=lineage("kenku"), toggle="Kenku Recall: spend a use (Advantage on a proficient skill)")
R("draconblood", "Forceful Presence: Advantage on Intimidation or Persuasion", "", CHECK, [ADV],
  skills=fs("Intimidation", "Persuasion"), when=lineage("draconblood"),
  toggle="Forceful Presence: once per long rest (Advantage)")
R("changeling", "Shape-Shifter: Advantage on Charisma checks while shape-shifted", "", CHECK, [ADV],
  abilities=fs("CHA"), when=lineage("changeling"), toggle="Shape-Shifter: while shape-shifted (Advantage on Charisma checks)")
R("goliath_form", "Large Form: Advantage on Strength checks", "", CHECK, [ADV], abilities=fs("STR"),
  when=lineage("goliath"), toggle="Large Form: while enlarged (Advantage on Strength checks)")
R("shifter", "Wildhunt: Advantage on Wisdom checks while shifted", "", CHECK, [ADV], abilities=fs("WIS"),
  when=lineage("shifter"), toggle="Shifting: while shifted (Advantage on Wisdom checks)")
R("duskling_ardor", "Ardor: Advantage on Charisma checks", "", CHECK, [ADV], abilities=fs("CHA"),
  when=lineage("duskling"), toggle="Inner Magic (Ardor): Advantage on Charisma checks")
R("duskling_vigor", "Vigor: Advantage on Athletics and Acrobatics", "", CHECK, [ADV],
  skills=fs("Athletics", "Acrobatics"), when=lineage("duskling"), toggle="Inner Magic (Vigor): Advantage on Athletics and Acrobatics")
R("firbolg", "Speech of Beast and Leaf: Advantage on Charisma checks to influence beasts and plants", "", CHECK, [ADV],
  abilities=fs("CHA"), when=lineage("firbolg"), toggle="Speech of Beast and Leaf: influencing beasts and plants (Advantage)")
R("hippo_build", "Hippo Build: Advantage on Strength checks and saves", "", ("check", "save"), [ADV],
  abilities=fs("STR"), when=lineage("giff"))
R("pallid_elf", "Incisive Sense: Advantage on Investigation and Insight", "", CHECK, [ADV],
  skills=fs("Investigation", "Insight"), when=lineage("pallid"))
R("deep_gnome", "Svirfneblin Camouflage: Advantage on Stealth", "", CHECK, [ADV], skills=fs("Stealth"),
  when=lineage("deep gnome"))
R("peerless_athlete", "Peerless Athlete: Advantage on Athletics and Acrobatics", "peerless_athlete", CHECK, [ADV],
  skills=fs("Athletics", "Acrobatics"), toggle="Peerless Athlete: active (Advantage on Athletics and Acrobatics)")
R("living_legend_cha", "Living Legend: Advantage on Charisma checks", "living_legend", CHECK, [ADV],
  abilities=fs("CHA"), toggle="Living Legend: active (Advantage on Charisma checks)")
R("dazzling_footwork", "Dazzling Footwork: Advantage on Performance while dancing", "dazzling_footwork", CHECK, [ADV],
  skills=fs("Performance"), toggle="Dazzling Footwork: dancing (Advantage on Performance)")
R("dampening_field", "Dampening Field: Advantage on Stealth", "dampening_field", CHECK, [ADV], skills=fs("Stealth"))
R("wondrous_alteration", "Wondrous Alteration: Advantage on Deception", "wondrous_alteration", CHECK, [ADV],
  skills=fs("Deception"), toggle="Wondrous Alteration: changed appearance (Advantage on Deception)")
R("fey_glamour", "Otherworldly Glamour: + Wisdom modifier (min +1) to Charisma checks", "fey_wanderer", CHECK,
  [flat(lambda c: max(1, c.mod("WIS")))], abilities=fs("CHA"))
R("thaumaturge", "Divine Order (Thaumaturge): + Wisdom modifier (min +1) to Arcana and Religion", "thaumaturge", CHECK,
  [flat(lambda c: max(1, c.mod("WIS")))], skills=fs("Arcana", "Religion"))
R("magician", "Primal Order (Magician): + Wisdom modifier (min +1) to Arcana and Nature", "magician", CHECK,
  [flat(lambda c: max(1, c.mod("WIS")))], skills=fs("Arcana", "Nature"))
R("starry_form", "Starry Form: a d20 of 9 or less counts as 10 on Intelligence and Wisdom checks", "starry_form", CHECK,
  [minimum(10)], abilities=fs("INT", "WIS"), toggle="Starry Form: active (9 or less counts as 10 on Int and Wis checks)")
R("starry_form_conc", "Starry Form: a d20 of 9 or less counts as 10 on concentration saves", "starry_form", SAVE,
  [minimum(10)], conc=True, toggle="Starry Form: active (9 or less counts as 10 on concentration saves)")
R("trance_of_order", "Trance of Order: a d20 of 9 or less counts as 10", "trance_of_order", D20TEST, [minimum(10)],
  toggle="Trance of Order: active (9 or less on a d20 counts as 10)")
R("divine_foreknowledge", "Divine Foreknowledge: Advantage on D20 Tests", "divine_foreknowledge", D20TEST, [ADV],
  toggle="Divine Foreknowledge: active (Advantage on D20 Tests)")
R("indomitable_might", "Indomitable Might: a Strength check or save counts as at least your Strength score",
  "indomitable_might", ("check", "save"), [Eff("floor_total", lambda c: c.score("STR"))], abilities=fs("STR"))
R("boon_of_skill_proficiency", "Boon of Skill Proficiency: a proficient skill total below 20 counts as 20",
  "boon_of_skill_proficiency", ("skill",), [Eff("floor_total", 20)], proficient=True,
  toggle="Boon of Skill Proficiency: treat the total as 20 (chosen skill)")
R("adept_red_robes", "Magical Balance: a d20 of 9 or less counts as 10", "adept_red_robes", ("check", "attack"),
  [minimum(10)], toggle="Adept of the Red Robes: balance fate (9 or less counts as 10)")
R("arcane_eloquence", "Arcane Eloquence: +1d4 to Deception, Intimidation and Persuasion", "arcane_eloquence", CHECK,
  [die(1, 4)], skills=fs("Deception", "Intimidation", "Persuasion"))
R("arcane_undertaker", "Arcane Undertaker: +1d4 to History and Medicine", "arcane_undertaker", CHECK, [die(1, 4)],
  skills=fs("History", "Medicine"))
for _mark, (_skills, _) in DRAGONMARKS.items():
    R(f"mark_{_mark}", f"Mark of {_mark.title()}: +1d4 to {', '.join(_skills)}", f"mark_{_mark}", ("skill",),
      [die(1, 4)], skills=fs(*_skills), when=(lambda m: lambda c: not c.has(f"greater_mark_{m}"))(_mark))
    R(f"greater_mark_{_mark}", f"Greater Mark of {_mark.title()}: +1d6 to {', '.join(_skills)}",
      f"greater_mark_{_mark}", ("skill",), [die(1, 6)], skills=fs(*_skills))

# ============================================================================= initiative
R("alert_init", "Alert: + proficiency bonus to initiative (+5 in the 2014 version)", "alert", ("initiative",),
  [flat(lambda c: 5 if c.feat_legacy("alert") else c.prof)])
R("feral_instinct", "Feral Instinct: Advantage on initiative", "feral_instinct", ("initiative",), [ADV])
R("remarkable_athlete_2024", "Remarkable Athlete: Advantage on initiative", "remarkable_athlete", ("initiative",),
  [ADV], when=lambda c: not c.is_legacy("Fighter"))
R("remarkable_athlete_athletics", "Remarkable Athlete: Advantage on Athletics", "remarkable_athlete", ("skill",),
  [ADV], skills=fs("Athletics"), when=lambda c: not c.is_legacy("Fighter"))
R("assassinate_init", "Assassinate: Advantage on initiative", "assassinate_initiative", ("initiative",), [ADV])
R("dread_ambusher_init", "Dread Ambusher: + Wisdom modifier to initiative", "dread_ambusher", ("initiative",),
  [flat(lambda c: c.mod("WIS"))])
R("hare_trigger", "Hare-Trigger: + proficiency bonus to initiative", "", ("initiative",), [flat(lambda c: c.prof)],
  when=lineage("harengon"))
R("tactical_wit", "Tactical Wit: + Intelligence modifier to initiative", "tactical_wit", ("initiative",),
  [flat(lambda c: c.mod("INT"))])
R("survivor_init", "Survivor: reroll initiative if it is 9 or lower", "survivor_feat", ("initiative",), [reroll(9)])

# ============================================================================= luck: rerolls and extra d20s
R("halfling_luck", "Halfling Luck: a 1 on the d20 is rerolled", "halfling_luck", D20TEST, [reroll(1)])
R("harper_agent", "Favor the Bold: a 1 on a saving throw is rerolled", "harper_agent", SAVE, [reroll(1)])
R("lucky_2024", "Lucky: a Luck Point gives Advantage", "lucky", D20TEST, [ADV],
  when=lambda c: not c.feat_legacy("lucky"), toggle="Lucky: spend a Luck Point (Advantage)")
R("lucky_2014", "Lucky: a Luck Point rolls an extra d20", "lucky", D20TEST, [Eff("copies", 1)],
  when=lambda c: c.feat_legacy("lucky"), toggle="Lucky: spend a Luck Point (roll an extra d20, use either)")
R("boon_of_fortunes_favor", "Boon of Fortune's Favor: a Luck Point rolls an extra d20", "boon_of_fortunes_favor",
  D20TEST, [Eff("copies", 1)], toggle="Boon of Fortune's Favor: spend a Luck Point (extra d20)")
R("elven_accuracy", "Elven Accuracy: a third d20 with Advantage", "elven_accuracy", ATTACK,
  [Eff("copies_if_adv", 1)], toggle="Elven Accuracy: a Dex/Int/Wis/Cha attack",
  default=True)

# ============================================================================= "if the roll fails" options
R("indomitable", "Indomitable: reroll a failed save with a bonus", "indomitable", SAVE,
  [reroll_plus(lambda c: 0 if c.is_legacy("Fighter") else c.lvl("Fighter"))],
  toggle="Indomitable: reroll a failed save (+ Fighter level)")
R("disciplined_survivor", "Disciplined Survivor: reroll a failed save", "disciplined_survivor", SAVE,
  [reroll_plus(lambda c: 0)], toggle="Disciplined Survivor: spend a Focus Point to reroll a failed save")
R("fanatical_focus", "Fanatical Focus: reroll a failed save with your Rage Damage bonus", "fanatical_focus", SAVE,
  [reroll_plus(lambda c: c.rage_damage())], toggle="Fanatical Focus: reroll a failed save (+ Rage Damage)")
R("living_legend_save", "Living Legend: reroll a failed save", "living_legend", SAVE, [reroll_plus(lambda c: 0)],
  toggle="Living Legend: reroll a failed save")
R("fey_pact", "Fey Pact: reroll a failed Deception or Persuasion check", "fey_pact", CHECK, [reroll_plus(lambda c: 0)],
  skills=fs("Deception", "Persuasion"), toggle="Fey Pact: reroll a failed Deception or Persuasion check")
R("noble_scion", "Noble Scion: a failed D20 Test succeeds", "noble_scion", D20TEST, [RESCUE_SUCCEED],
  toggle="Noble Scion: turn a failed d20 test into a success")
R("mage_slayer", "Guarded Mind: a failed Int, Wis or Cha save succeeds", "mage_slayer", SAVE, [RESCUE_SUCCEED],
  abilities=fs("INT", "WIS", "CHA"), toggle="Mage Slayer (Guarded Mind): turn a failed Int/Wis/Cha save into a success")
R("stroke_of_luck", "Stroke of Luck: a failed d20 test becomes a 20", "stroke_of_luck", D20TEST, [RESCUE_SET20],
  toggle="Stroke of Luck: turn a failed d20 test into a 20")
R("boon_of_combat_prowess", "Peerless Aim: a missed attack hits", "boon_of_combat_prowess", ATTACK, [RESCUE_SUCCEED],
  toggle="Boon of Combat Prowess: turn a miss into a hit")
R("tactical_mind", "Tactical Mind: +1d10 on a failed check", "tactical_mind", CHECK, [Eff("rescue_add", (1, 10, 0))],
  toggle="Tactical Mind: spend Second Wind (+1d10 on a failed check)")
R("peerless_skill", "Peerless Skill: + Bardic Inspiration die on a failed check or attack", "peerless_skill",
  ("check", "attack"), [rescue_fn(lambda c: (1, c.bardic_die(), 0))],
  toggle="Peerless Skill: spend Bardic Inspiration (+ the die on a failure)")
R("psi_bolstered_knack", "Psi-Bolstered Knack: + Psionic Energy Die on a failed proficient skill check",
  "psi_bolstered_knack", ("skill",), [rescue_fn(lambda c: (1, c.psionic_die("Rogue"), 0))], proficient=True,
  toggle="Psi-Bolstered Knack: spend a Psionic Energy Die (+ the die on a failure)")
R("homing_strikes", "Homing Strikes: + Psionic Energy Die on a missed Psychic Blade attack", "homing_strikes", ATTACK,
  [rescue_fn(lambda c: (1, c.psionic_die("Rogue"), 0))], toggle="Homing Strikes: spend a Psionic Energy Die on a miss")
R("guided_strike", "Guided Strike: +10 on a missed attack", "guided_strike", ATTACK, [Eff("rescue_add", (0, 6, 10))],
  toggle="Guided Strike: spend Channel Divinity (+10 on a miss)")
R("flash_of_genius_2024", "Flash of Genius: + Intelligence modifier on a failed check or save", "flash_of_genius",
  ("check", "save"), [rescue_fn(lambda c: (0, 6, max(1, c.mod("INT"))))], when=lambda c: not c.is_legacy("Artificer"),
  toggle="Flash of Genius: + Intelligence modifier on a failure")
R("flash_of_genius_2014", "Flash of Genius: + Intelligence modifier to the roll", "flash_of_genius", ("check", "save"),
  [flat(lambda c: c.mod("INT"))], when=lambda c: c.is_legacy("Artificer"), toggle="Flash of Genius: + Intelligence modifier")
R("dark_ones_own_luck", "Dark One's Own Luck: +1d10 on a failed check or save", "dark_ones_own_luck",
  ("check", "save"), [Eff("rescue_add", (1, 10, 0))], toggle="Dark One's Own Luck: +1d10 on a failure")
R("reborn", "Knowledge from a Past Life: +1d6 on a failed check", "", CHECK, [Eff("rescue_add", (1, 6, 0))],
  when=lineage("reborn"), toggle="Knowledge from a Past Life: +1d6 on a failed check")
R("built_for_success", "Built for Success: +1d4 on a failed d20 test", "", D20TEST, [Eff("rescue_add", (1, 4, 0))],
  when=lineage("autognome"), toggle="Built for Success: +1d4 on a failure (once per rest)")
R("honed_instincts", "Honed Instincts: +1d6 on a failed check", "tactical_combatant", CHECK,
  [Eff("rescue_add", (1, 6, 0))], toggle="Honed Instincts: +1d6 on a failed check")
R("aberrant_fortitude", "Aberrant Fortitude: +1d4 (1d6 with the greater mark) on a failed Constitution save",
  "aberrant_dragonmark", SAVE, [rescue_fn(lambda c: (1, 6 if c.feat("greater aberrant mark") else 4, 0))],
  abilities=fs("CON"), toggle="Aberrant Fortitude: + a die on a failed Constitution save")
R("lucky_footwork", "Lucky Footwork: +1d4 on a failed Dexterity save", "", SAVE, [Eff("rescue_add", (1, 4, 0))],
  abilities=fs("DEX"), when=lineage("harengon"), toggle="Lucky Footwork: +1d4 on a failed Dexterity save")
R("spell_resistant", "Spell Resistant: +1d6 on a failed save against a spell", "spell_resistant", SAVE,
  [Eff("rescue_add", (1, 6, 0))], vs="magic", toggle="Spell Resistant: +1d6 on a failed save against a spell")
R("arcane_omens", "Arcane Omens: +1d4 on a failed save", "arcane_omens", SAVE, [Eff("rescue_add", (1, 4, 0))],
  toggle="Arcane Omens: +1d4 on a failed save")
R("boon_of_fate", "Boon of Fate: +2d4 on a failed d20 test", "boon_of_fate", D20TEST, [Eff("rescue_add", (2, 4, 0))],
  toggle="Boon of Fate: +2d4 on a failed d20 test")
R("hobgoblin_fortune", "Fortune from the Many: + allies nearby (up to +3) on a failed roll", "", D20TEST,
  [Eff("rescue_add", (0, 6, 3))], when=lineage("hobgoblin"), toggle="Fortune from the Many: +3 on a failure (3 allies in sight)")

# ============================================================================= saving throws
R("aura_of_protection", "Aura of Protection: + Charisma modifier (min +1) to saves", "aura_of_protection", SAVE,
  [flat(lambda c: max(1, c.mod("CHA")))])
R("danger_sense", "Danger Sense: Advantage on Dexterity saves", "danger_sense", SAVE, [ADV], abilities=fs("DEX"))
R("moon_toughness", "Increased Toughness: + Wisdom modifier to Constitution saves", "moon_toughness", SAVE,
  [flat(lambda c: c.mod("WIS"))], abilities=fs("CON"))
R("hungering_might", "Hungering Might: + Wisdom modifier (min +1) to Constitution saves", "hungering_might", SAVE,
  [flat(lambda c: max(1, c.mod("WIS")))], abilities=fs("CON"))
R("soul_of_artifice", "Soul of Artifice: +1 to saves per attuned magic item", "soul_of_artifice", SAVE,
  [flat(lambda c: sum(1 for i in c.active_items if i.needs_attunement))])
R("war_caster", "War Caster: Advantage on concentration saves", "war_caster", SAVE, [ADV], conc=True)
R("wondrous_alteration_conc", "Wondrous Alteration: Advantage on concentration saves", "wondrous_alteration", SAVE,
  [ADV], conc=True, toggle="Wondrous Alteration: Advantage on concentration saves")
R("gnome_cunning", "Gnomish Cunning: Advantage on Int, Wis and Cha saves", "", SAVE, [ADV],
  abilities=fs("INT", "WIS", "CHA"),
  when=lambda c: c.lineage_has("gnome") and not c.lineage_has("rock", "forest", "deep", "mark of scribing", "legacy"))
R("gnome_cunning_legacy", "Gnome Cunning: Advantage on Int, Wis and Cha saves against magic", "", SAVE, [ADV],
  abilities=fs("INT", "WIS", "CHA"), vs="magic",
  when=lambda c: c.lineage_has("gnome") and c.lineage_has("rock", "forest", "deep", "mark of scribing", "legacy"))
R("kalashtar", "Dual Mind: Advantage on Wisdom and Charisma saves", "", SAVE, [ADV], abilities=fs("WIS", "CHA"),
  when=lambda c: c.lineage_has("kalashtar") and "legacy" not in c.lineage)
R("kalashtar_legacy", "Dual Mind: Advantage on Wisdom saves", "", SAVE, [ADV], abilities=fs("WIS"),
  when=lambda c: c.lineage_has("kalashtar") and "legacy" in c.lineage)
R("verdan", "Telepathic Insight: Advantage on Wisdom and Charisma saves", "", SAVE, [ADV], abilities=fs("WIS", "CHA"),
  when=lineage("verdan"))
# saves against a condition or kind of effect (chosen with "Save against")
R("fey_ancestry", "Fey Ancestry: Advantage on saves against being Charmed", "", SAVE, [ADV], vs="charmed",
  when=lineage("elf", "eladrin", "khoravar", "boggart", "goblin", "hobgoblin", "bugbear", "shadar-kai", "githzerai",
               "loxodon", "locathah"))
R("brave", "Brave: Advantage on saves against being Frightened", "", SAVE, [ADV], vs="frightened",
  when=lineage("halfling", "kor", "kobold", "duskling", "githzerai", "loxodon", "locathah", "kender"))
R("dwarven_resilience", "Resilience: Advantage on saves against being Poisoned", "", SAVE, [ADV], vs="poisoned",
  when=lineage("dwarf", "duergar", "warforged", "stout", "yuan-ti", "autognome", "plasmoid", "locathah"))
R("magic_resistance_species", "Magic Resistance: Advantage on saves against spells and magic", "", SAVE, [ADV],
  vs="magic", when=lineage("satyr", "yuan-ti", "vedalken"))
R("beguiling_twist", "Beguiling Twist: Advantage on saves against Charmed and Frightened", "fey_wanderer", SAVE, [ADV],
  vs="charmed", when=lambda c: c.lvl("Ranger") >= 7)
R("beguiling_twist_f", "Beguiling Twist: Advantage on saves against Frightened", "fey_wanderer", SAVE, [ADV],
  vs="frightened", when=lambda c: c.lvl("Ranger") >= 7)
R("psychic_defenses", "Psychic Defenses: Advantage on saves against Charmed", "", SAVE, [ADV], vs="charmed",
  when=lambda c: c.lvl("Sorcerer") >= 6 and (c.sub_has("Sorcerer", "aberrant")))
R("psychic_defenses_f", "Psychic Defenses: Advantage on saves against Frightened", "", SAVE, [ADV], vs="frightened",
  when=lambda c: c.lvl("Sorcerer") >= 6 and (c.sub_has("Sorcerer", "aberrant")))
R("spell_resistance", "Spell Resistance: Advantage on saves against spells", "", SAVE, [ADV], vs="magic",
  when=lambda c: c.lvl("Wizard") >= 14 and c.sub_has("Wizard", "abjur"))

# ============================================================================= attack rolls
R("steady_aim", "Steady Aim: Advantage on your next attack", "steady_aim", ATTACK, [ADV],
  toggle="Steady Aim: used this turn (Advantage)")
R("vow_of_enmity", "Vow of Enmity: Advantage against your sworn enemy", "vow_of_enmity", ATTACK, [ADV],
  toggle="Vow of Enmity: attacking the marked creature (Advantage)")
R("precise_hunter", "Precise Hunter: Advantage against your Hunter's Mark target", "precise_hunter", ATTACK, [ADV],
  toggle="Precise Hunter: attacking your Hunter's Mark target (Advantage)")
R("studied_attacks", "Studied Attacks: Advantage after a miss", "studied_attacks", ATTACK, [ADV],
  toggle="Studied Attacks: you missed this creature last turn (Advantage)")
R("sacred_weapon", "Sacred Weapon: + Charisma modifier (min +1) to attack rolls", "sacred_weapon", ATTACK,
  [flat(lambda c: max(1, c.mod("CHA")))], toggle="Sacred Weapon: active (+ Charisma to attack rolls)")
R("hexblades_curse", "Hexblade's Curse: critical hits on 19 or 20", "hexblades_curse", ATTACK, [Eff("crit", 19)],
  toggle="Hexblade's Curse: attacking the cursed creature (crit on 19-20)")
R("archery", "Archery: +2 to ranged weapon attack rolls", "archery", ATTACK, [flat(2)], ranged=True)
R("grappler", "Grappler: Advantage against a creature you have grappled", "grappler", ATTACK, [ADV],
  toggle="Grappler: the target is grappled by you (Advantage)")
R("mounted_combatant", "Mounted Combatant: Advantage against a smaller unmounted creature", "mounted_combatant",
  ATTACK, [ADV], toggle="Mounted Combatant: mounted (Advantage against a smaller creature)")
R("purple_dragon_commandant", "Last Stand: Advantage while Bloodied", "purple_dragon_commandant", ATTACK, [ADV],
  toggle="Last Stand: you are Bloodied (Advantage)")
R("treacherous_allure", "Inevitable Betrayal: Advantage against Charmed creatures", "treacherous_allure", ATTACK, [ADV],
  toggle="Treacherous Allure: the target is Charmed (Advantage)")
R("boon_of_terror", "Feed on Fear: Advantage against Frightened creatures", "boon_of_terror", ATTACK, [ADV],
  toggle="Feed on Fear: the target is Frightened (Advantage)")
R("pack_tactics", "Pack Tactics: Advantage with an ally next to the target", "", ATTACK, [ADV],
  when=lineage("kobold"), toggle="Pack Tactics: an ally is within 5 feet of the target (Advantage)")
R("squire_of_solamnia", "Precise Strike: Advantage on one attack", "squire_of_solamnia", ATTACK, [ADV],
  toggle="Squire of Solamnia: Precise Strike (Advantage)")
R("sunlight_sensitivity", "Sunlight Sensitivity: Disadvantage in direct sunlight", "", ATTACK, [DIS],
  when=lineage("dark elf", "drow", "duergar", "kobold", "mul daya"),
  toggle="Sunlight Sensitivity: you or the target is in direct sunlight (Disadvantage)")
R("sunlight_sensitivity_perception", "Sunlight Sensitivity: Disadvantage on sight-based Perception", "", CHECK, [DIS],
  skills=fs("Perception"), when=lineage("dark elf", "drow", "duergar", "kobold", "mul daya"),
  toggle="Sunlight Sensitivity: in direct sunlight (Disadvantage on sight-based Perception)")
R("innate_sorcery", "Innate Sorcery: Advantage on Sorcerer spell attack rolls, +1 spell save DC", "innate_sorcery",
  ("spell",), [ADV, Eff("dc", 1)], toggle="Innate Sorcery: active (Advantage on spell attacks, +1 save DC)",
  spell_class="Sorcerer")
R("tides_of_chaos", "Tides of Chaos: Advantage on one d20 test", "tides_of_chaos", D20TEST + ("spell",), [ADV],
  toggle="Tides of Chaos: spend it (Advantage)")
R("divination_adept_self", "Prescient Intervention: Advantage on a D20 Test", "divination_adept", D20TEST, [ADV],
  toggle="Divination Adept: Prescient Intervention (Advantage)")
R("infernal_dragoon", "Infernal Dragoon: +2 to a D20 Test", "infernal_dragoon", D20TEST, [flat(2)],
  toggle="Infernal Dragoon: transformed (+2 to d20 tests)")


# ============================================================================= damage and healing
DAMAGE_RULES: List[DmgRule] = []


def D(rid: str, label: str, feature: str = "", *, kind: str, dice=None, flat_=0, once: bool = False, default: bool = True,
      toggle: bool = True, when=None, applies=None, crit_doubles: bool = True, minimum_: int = 1,
      per_projectile: bool = False) -> None:
    def ok(c: Ctx, d: DmgCtx) -> bool:
        if d.kind != kind:
            return False
        return applies(c, d) if applies else True
    DAMAGE_RULES.append(DmgRule(rid, label, feature, when, ok, dice, flat_, once, toggle, default, label, crit_doubles,
                                minimum_, per_projectile))


def melee(c: Ctx, d: DmgCtx) -> bool:
    return not d.ranged


def martial_die(c: Ctx) -> int:
    lvl = c.lvl("Monk")
    return 12 if lvl >= 17 else 10 if lvl >= 11 else 8 if lvl >= 5 else 6


# ---- weapons
D("radiant_strikes", "Radiant Strikes: +1d8 Radiant on melee hits", "radiant_strikes", kind="weapon",
  dice=lambda c: (1, 8), applies=melee)
D("blessed_strikes", "Divine Strike: +1d8 (2d8 from level 14) Necrotic or Radiant, once per turn", "blessed_strikes",
  kind="weapon", dice=lambda c: (2 if c.lvl("Cleric") >= 14 else 1, 8), once=True)
D("primal_strike", "Primal Strike: +1d8 (2d8 from level 15), once per turn", "primal_strike", kind="weapon",
  dice=lambda c: (2 if c.lvl("Druid") >= 15 else 1, 8), once=True)
D("hunters_mark", "Hunter's Mark: +1d6", "hunters_mark", kind="weapon", dice=lambda c: (1, 6), default=False)
D("hex", "Hex: +1d6 Necrotic", "hex", kind="weapon", dice=lambda c: (1, 6), default=False)
D("hunters_prey", "Hunter's Prey: +1d8 against a creature that is hurt, once per turn", "hunters_prey", kind="weapon",
  dice=lambda c: (1, 8), once=True, default=False)
D("dreadful_strikes", "Dreadful Strikes: +1d4 (1d6 from level 11) Psychic, once per turn", "dreadful_strikes",
  kind="weapon", dice=lambda c: (1, 6 if c.lvl("Ranger") >= 11 else 4), once=True)
D("polar_strikes", "Polar Strikes: +1d4 (1d6 from level 11) Cold, once per turn", "polar_strikes", kind="weapon",
  dice=lambda c: (1, 6 if c.lvl("Ranger") >= 11 else 4), once=True)
D("dread_ambusher", "Dreadful Strike: +2d6 Psychic, once per turn", "dread_ambusher", kind="weapon",
  dice=lambda c: (2, 6), once=True, default=False)
D("frenzy", "Frenzy: extra d6s equal to your Rage Damage (Reckless Attack while raging), first hit each turn",
  "frenzy", kind="weapon", dice=lambda c: (max(1, c.rage_damage()), 6), once=True, default=False)
D("divine_fury", "Divine Fury: 1d6 + half your Barbarian level while raging, first hit each turn", "divine_fury",
  kind="weapon", dice=lambda c: (1, 6), flat_=lambda c, d: c.lvl("Barbarian") // 2, once=True, default=False)
D("hand_of_harm", "Hand of Harm: a Martial Arts die + Wisdom modifier Necrotic (a Focus Point), once per turn",
  "hand_of_harm", kind="weapon", dice=lambda c: (1, martial_die(c)), flat_=lambda c, d: c.mod("WIS"), once=True,
  default=False, applies=lambda c, d: d.unarmed or True)
D("arcane_jolt", "Arcane Jolt: +2d6 Force (4d6 from level 15), once per turn", "arcane_jolt", kind="weapon",
  dice=lambda c: (4 if c.lvl("Artificer") >= 15 else 2, 6), once=True, default=False)
D("lightning_launcher", "Lightning Launcher: +1d6 Lightning, once per turn", "lightning_launcher", kind="weapon",
  dice=lambda c: (1, 6), once=True, default=False)
D("charger", "Charge Attack: +1d8 after moving 10 feet", "charger", kind="weapon", dice=lambda c: (1, 8), default=False)
D("boon_of_bloodshed", "Savage Strikes: + proficiency bonus", "boon_of_bloodshed", kind="weapon",
  flat_=lambda c, d: c.prof)
D("boon_of_furious_storm", "Thunderous Blows: +1d10 + proficiency bonus Lightning or Thunder, once per turn",
  "boon_of_furious_storm", kind="weapon", dice=lambda c: (1, 10), flat_=lambda c, d: c.prof, once=True, default=False,
  applies=melee)
D("boon_of_poison_mastery", "Venomous Strikes: +2d6 Poison, once per turn", "boon_of_poison_mastery", kind="weapon",
  dice=lambda c: (2, 6), once=True, default=False)
D("zhentarim_ruffian", "Cutthroat Strike: +1d6 against a creature that has not acted, once per turn", "zhentarim_ruffian",
  kind="weapon", dice=lambda c: (1, 6), once=True, default=False)
D("squire_of_solamnia_dmg", "Precise Strike: +1d8", "squire_of_solamnia", kind="weapon", dice=lambda c: (1, 8),
  default=False, once=True)
D("lifedrinker", "Lifedrinker: +1d6 Necrotic, Psychic or Radiant with your pact weapon, once per turn", "lifedrinker",
  kind="weapon", dice=lambda c: (1, 6), once=True, default=False)
D("thrown_weapon_fighting", "Thrown Weapon Fighting: +2 damage with a thrown weapon", "thrown_weapon_fighting",
  kind="weapon", flat_=2, applies=lambda c, d: d.ranged or d.thrown, default=False)
D("celestial_revelation", "Celestial Revelation: + proficiency bonus, once per turn", "", kind="weapon",
  flat_=lambda c, d: c.prof, once=True, default=False, when=lineage("aasimar"))
D("fury_of_the_small", "Fury of the Small: + proficiency bonus against a larger creature", "", kind="weapon",
  flat_=lambda c, d: c.prof, once=True, default=False, when=lineage("goblin", "boggart"))
D("surprise_attack", "Surprise Attack: +2d6 against a creature that has not acted", "", kind="weapon",
  dice=lambda c: (2, 6), once=True, default=False, when=lineage("bugbear"))
D("astral_spark", "Astral Spark: + proficiency bonus Force", "", kind="weapon", flat_=lambda c, d: c.prof, once=True,
  default=False, when=lineage("giff"))
D("giant_fire", "Fire's Burn: +1d10 Fire", "giant_ancestry_fire", kind="weapon", dice=lambda c: (1, 10), default=False)
D("giant_frost", "Frost's Chill: +1d6 Cold", "giant_ancestry_frost", kind="weapon", dice=lambda c: (1, 6), default=False)
D("pack_fighting", "Pack Fighting: +1 with an ally next to the target", "pack_fighting", kind="weapon", flat_=1,
  default=False)

# ---- spells
D("potent_cleric", "Potent Spellcasting: + Wisdom modifier to a cantrip's damage", "potent_spellcasting_cleric",
  kind="spell", flat_=lambda c, d: c.mod("WIS"), applies=lambda c, d: d.cantrip and not d.healing, per_projectile=True)
D("potent_druid", "Potent Spellcasting: + Wisdom modifier to a cantrip's damage", "potent_spellcasting_druid",
  kind="spell", flat_=lambda c, d: c.mod("WIS"), applies=lambda c, d: d.cantrip and not d.healing, per_projectile=True,
  default=False)
D("empowered_evocation", "Empowered Evocation: + Intelligence modifier to one damage roll of an Evocation spell",
  "empowered_evocation", kind="spell", flat_=lambda c, d: c.mod("INT"), once=True,
  applies=lambda c, d: d.school == "evocation" and not d.healing)
D("radiant_soul", "Radiant Soul: + Charisma modifier to Radiant or Fire spell damage, once per turn", "radiant_soul",
  kind="spell", flat_=lambda c, d: c.mod("CHA"), once=True,
  applies=lambda c, d: d.damage_type in ("radiant", "fire"))
D("elemental_affinity", "Elemental Affinity: + Charisma modifier to one damage roll of your ancestry's damage type",
  "elemental_affinity", kind="spell", flat_=lambda c, d: c.mod("CHA"), once=True, default=False,
  applies=lambda c, d: not d.healing)
D("power_from_beyond", "Power from Beyond: +1d6 to one damage roll or the healing, once per turn", "power_from_beyond",
  kind="spell", dice=lambda c: (1, 6), once=True, default=False, applies=lambda c, d: not d.cantrip)
D("arcane_firearm", "Arcane Firearm: +1d8 to one damage roll", "arcane_firearm", kind="spell",
  dice=lambda c: (1, 8), once=True, default=False, applies=lambda c, d: not d.healing)
D("alchemical_savant", "Alchemical Savant: + Intelligence modifier (min +1) to Acid, Fire or Poison damage or healing",
  "alchemical_savant", kind="spell", flat_=lambda c, d: max(1, c.mod("INT")), once=True, default=False,
  applies=lambda c, d: d.healing or d.damage_type in ("acid", "fire", "poison"))
D("agonizing_blast", "Agonizing Blast: + Charisma modifier to each Eldritch Blast beam", "agonizing_blast",
  kind="spell", flat_=lambda c, d: c.mod("CHA"), per_projectile=True,
  applies=lambda c, d: d.spell_name.lower() == "eldritch blast")
D("disciple_of_life", "Disciple of Life: healing spells restore 2 + the spell's level more", "disciple_of_life",
  kind="spell", flat_=lambda c, d: 2 + d.level, once=True, applies=lambda c, d: d.healing and d.level >= 1)

R("reliable_talent", "Reliable Talent: a d20 of 9 or less counts as 10", "reliable_talent", ("skill",), [minimum(10)],
  proficient=True)
D("dueling", "Dueling: +2 damage with a one-handed melee weapon", "dueling", kind="weapon", flat_=2, applies=melee)
