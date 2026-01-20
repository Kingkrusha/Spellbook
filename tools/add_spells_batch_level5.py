import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from spell_manager import SpellManager
from spell import Spell, CharacterClass


ALLOWED_TAGS = {
    "AOE",
    "Abjuration",
    "Acid",
    "Attack",
    "Bludgeoning",
    "Buff",
    "Cold",
    "Conjuration",
    "DOT",
    "Damage",
    "Debuff",
    "Defense",
    "Divination",
    "Enchantment",
    "Evocation",
    "Fire",
    "Force",
    "Healing",
    "Illusion",
    "Light",
    "Lightning",
    "Necromancy",
    "Necrotic",
    "Piercing",
    "Poison",
    "Psychic",
    "Radiant",
    "Saving Throw",
    "Slashing",
    "Thunder",
    "Transmutation",
    "Utility",
    "Temp HP",
}


def rv(text: str) -> int:
    t = text.strip().lower()
    if t == "self":
        return 0
    if t == "sight":
        return 1
    if t == "touch":
        return 3
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def classes(names):
    return [CharacterClass.from_string(n.strip()) for n in names]


def make_spell(*, name, level, casting_time, ritual, range_str, components, duration,
               concentration, class_names, description, source, tags):
    filtered_tags = [t for t in tags if t in ALLOWED_TAGS]
    return Spell(
        name=name,
        level=level,
        casting_time=casting_time,
        ritual=ritual,
        range_value=rv(range_str),
        components=components,
        duration=duration,
        concentration=concentration,
        classes=classes(class_names),
        description=description,
        source=source,
        tags=filtered_tags,
    )


spells = [
    make_spell(
        name="Alustriel's Mooncloak",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a moonstone worth 50+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Druid", "Ranger", "Wizard"],
        description=(
            "For the duration, moonlight fills a 20-foot Emanation originating from you with Dim Light. "
            "While in that area, you and your allies have Half Cover and Resistance to Cold, Lightning, and Radiant damage.\n\n"
            "While the spell lasts, you can use one of the following options, ending the spell immediately:\n\n"
            "Liberation. When you fail a saving throw to avoid or end the Frightened, Grappled, or Restrained condition, "
            "you can take a Reaction to succeed on the save instead.\n\n"
            "Respite. As a Magic action, you or an ally within the area regains Hit Points equal to 4d10 plus your spellcasting ability modifier."
        ),
        source="Forgotten Realms - Heroes of Faerun",
        tags=["Abjuration", "Buff", "Defense", "Cold", "Lightning", "Radiant", "Healing"],
    ),
    make_spell(
        name="Animate Objects",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Artificer", "Bard", "Sorcerer", "Wizard"],
        description=(
            "Objects animate at your command. Choose a number of nonmagical objects within range that aren’t being worn or carried, "
            "aren’t fixed to a surface, and aren’t Gargantuan. The maximum number of objects is equal to your spellcasting ability modifier; "
            "for this number, a Medium or smaller target counts as one object, a Large target counts as two, and a Huge target counts as three.\n\n"
            "Each target animates, sprouts legs, and becomes a Construct that uses the Animated Object stat block; this creature is under your control until the spell ends or until it is reduced to 0 Hit Points. "
            "Each creature you make with this spell is an ally to you and your allies. In combat, it shares your Initiative count and takes its turn immediately after yours.\n\n"
            "Until the spell ends, you can take a Bonus Action to mentally command any creature you made with this spell if the creature is within 500 feet of you (if you control multiple creatures, you can command any of them at the same time, issuing the same command to each one). "
            "If you issue no commands, the creature takes the Dodge action and moves only to avoid harm. When the creature drops to 0 Hit Points, it reverts to its object form, and any remaining damage carries over to that form.\n\n"
            "Using a Higher-Level Spell Slot. The creature’s Slam damage increases by 1d4 (Medium or smaller), 1d6 (Large), or 1d12 (Huge) for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Attack", "Damage"],
    ),
    make_spell(
        name="Antilife Shell",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="1 hour",
        concentration=True,
        class_names=["Druid"],
        description=(
            "An aura extends from you in a 10-foot Emanation for the duration. The aura prevents creatures other than Constructs and Undead from passing or reaching through it. "
            "An affected creature can cast spells or make attacks with Ranged or Reach weapons through the barrier.\n\n"
            "If you move so that an affected creature is forced to pass through the barrier, the spell ends."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Defense"],
    ),
    make_spell(
        name="Awaken",
        level=5,
        casting_time="8 hours",
        ritual=False,
        range_str="Touch",
        components="V, S, M (an agate worth 1,000+ GP, which the spell consumes)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Druid"],
        description=(
            "You spend the casting time tracing magical pathways within a precious gemstone, and then touch the target. "
            "The target must be either a Beast or Plant creature with an Intelligence of 3 or less or a natural plant that isn’t a creature. "
            "The target gains an Intelligence of 10 and the ability to speak one language you know. If the target is a natural plant, it becomes a Plant creature and gains the ability to move its limbs, roots, vines, creepers, and so forth, and it gains senses similar to a human’s. "
            "The DM chooses statistics appropriate for the awakened Plant, such as the statistics for the Awakened Shrub or Awakened Tree in the Monster Manual.\n\n"
            "The awakened target has the Charmed condition for 30 days or until you or your allies deal damage to it. When that condition ends, the awakened creature chooses its attitude toward you."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Utility"],
    ),
    make_spell(
        name="Banishing Smite",
        level=5,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="1 minute",
        concentration=True,
        class_names=["Paladin"],
        description=(
            "The target hit by the attack roll takes an extra 5d10 Force damage from the attack. "
            "If the attack reduces the target to 50 Hit Points or fewer, the target must succeed on a Charisma saving throw or be transported to a harmless demiplane for the duration. "
            "While there, the target has the Incapacitated condition. When the spell ends, the target reappears in the space it left or in the nearest unoccupied space if that space is occupied."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Attack", "Damage", "Force", "Saving Throw"],
    ),
    make_spell(
        name="Bigby's Hand",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (an eggshell and a glove)",
        duration="1 minute",
        concentration=True,
        class_names=["Artificer", "Sorcerer", "Wizard"],
        description=(
            "You create a Large hand of shimmering magical energy in an unoccupied space that you can see within range. "
            "The hand lasts for the duration, and it moves at your command, mimicking the movements of your own hand.\n\n"
            "The hand is an object that has AC 20 and Hit Points equal to your Hit Point maximum. If it drops to 0 Hit Points, the spell ends. The hand doesn’t occupy its space.\n\n"
            "When you cast the spell and as a Bonus Action on your later turns, you can move the hand up to 60 feet and then cause one of the following effects:\n\n"
            "Clenched Fist. The hand strikes a target within 5 feet of it. Make a melee spell attack. On a hit, the target takes 5d8 Force damage.\n\n"
            "Forceful Hand. The hand attempts to push a Huge or smaller creature within 5 feet of it. The target must succeed on a Strength saving throw, or the hand pushes the target up to 5 feet plus a number of feet equal to five times your spellcasting ability modifier. The hand moves with the target, remaining within 5 feet of it.\n\n"
            "Grasping Hand. The hand attempts to grapple a Huge or smaller creature within 5 feet of it. The target must succeed on a Dexterity saving throw, or the target has the Grappled condition, with an escape DC equal to your spell save DC. While the hand grapples the target, you can take a Bonus Action to cause the hand to crush it, dealing Bludgeoning damage to the target equal to 4d6 plus your spellcasting ability modifier.\n\n"
            "Interposing Hand. The hand grants you Half Cover against attacks and other effects that originate from its space or that pass through it. In addition, its space counts as Difficult Terrain for your enemies.\n\n"
            "Using a Higher-Level Spell Slot. The damage of the Clenched Fist increases by 2d8 and the damage of the Grasping Hand increases by 2d6 for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Evocation", "Force", "Damage", "Attack", "Utility"],
    ),
    make_spell(
        name="Circle Of Power",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="10 minutes",
        concentration=True,
        class_names=["Artificer", "Cleric", "Paladin", "Wizard"],
        description=(
            "An aura radiates from you in a 30-foot Emanation for the duration. While in the aura, you and your allies have Advantage on saving throws against spells and other magical effects. "
            "When an affected creature makes a saving throw against a spell or magical effect that allows a save to take only half damage, it takes no damage if it succeeds on the save."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Buff", "Defense"],
    ),
    make_spell(
        name="Cloudkill",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You create a 20-foot-radius Sphere of yellow-green fog centered on a point within range. The fog lasts for the duration or until strong wind disperses it, ending the spell. Its area is Heavily Obscured.\n\n"
            "Each creature in the Sphere makes a Constitution saving throw, taking 5d8 Poison damage on a failed save or half as much damage on a successful one. "
            "A creature must also make this save when the Sphere moves into its space and when it enters the Sphere or ends its turn there. A creature makes this save only once per turn.\n\n"
            "The Sphere moves 10 feet away from you at the start of each of your turns.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "AOE", "Damage", "Poison", "Saving Throw", "DOT"],
    ),
    make_spell(
        name="Commune",
        level=5,
        casting_time="1 minute",
        ritual=True,
        range_str="Self",
        components="V, S, M (incense)",
        duration="1 minute",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "You contact a deity or a divine proxy and ask up to three questions that can be answered with yes or no. "
            "You must ask your questions before the spell ends. You receive a correct answer for each question.\n\n"
            "Divine beings aren't necessarily omniscient, so you might receive 'unclear' as an answer if a question pertains to information that lies beyond the deity’s knowledge. "
            "In a case where a one-word answer could be misleading or contrary to the deity’s interests, the DM might offer a short phrase as an answer instead.\n\n"
            "If you cast the spell more than once before finishing a Long Rest, there is a cumulative 25 percent chance for each casting after the first that you get no answer."
        ),
        source="Player's Handbook",
        tags=["Divination", "Utility"],
    ),
    make_spell(
        name="Commune With Nature",
        level=5,
        casting_time="1 minute",
        ritual=True,
        range_str="Self",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Druid", "Ranger"],
        description=(
            "You commune with nature spirits and gain knowledge of the surrounding area. In the outdoors, the spell gives you knowledge of the area within 3 miles of you. "
            "In caves and other natural underground settings, the radius is limited to 300 feet. The spell doesn't function where nature has been replaced by construction.\n\n"
            "Choose three of the following facts; you learn those facts as they pertain to the spell's area:\n"
            "Locations of settlements\n"
            "Locations of portals to other planes of existence\n"
            "Location of one Challenge Rating 10+ creature (DM’s choice) that is a Celestial, an Elemental, a Fey, a Fiend, or an Undead\n"
            "The most prevalent kind of plant, mineral, or Beast (you choose which to learn)\n"
            "Locations of bodies of water\n"
            "For example, you could determine the location of a powerful monster in the area, the locations of bodies of water, and the locations of any towns."
        ),
        source="Player's Handbook",
        tags=["Divination", "Utility"],
    ),
    make_spell(
        name="Cone Of Cold",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a small crystal or glass cone)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You unleash a blast of cold air. Each creature in a 60-foot Cone originating from you makes a Constitution saving throw, "
            "taking 8d8 Cold damage on a failed save or half as much damage on a successful one. A creature killed by this spell becomes a frozen statue until it thaws.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Evocation", "AOE", "Damage", "Cold", "Saving Throw"],
    ),
    make_spell(
        name="Conjure Elemental",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid", "Wizard"],
        description=(
            "You conjure a Large, intangible spirit from the Elemental Planes that appears in an unoccupied space within range. "
            "Choose the spirit’s element, which determines its damage type: air (Lightning), earth (Thunder), fire (Fire), or water (Cold). The spirit lasts for the duration.\n\n"
            "Whenever a creature you can see enters the spirit’s space or starts its turn within 5 feet of the spirit, you can force that creature to make a Dexterity saving throw if the spirit has no creature Restrained. "
            "On failed save, the target takes 8d8 damage of the spirit’s type, and the target has the Restrained condition until the spell ends. "
            "At the start of each of its turns, the Restrained target repeats the save. On a failed save, the target takes 4d8 damage of the spirit’s type. On a successful save, the target isn’t Restrained by the spirit.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Damage", "Saving Throw", "AOE"],
    ),
    make_spell(
        name="Conjure Volley",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (a Melee or Ranged weapon worth at least 1 CP)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Ranger"],
        description=(
            "You brandish the weapon used to cast the spell and choose a point within range. Hundreds of similar spectral weapons (or ammunition appropriate to the weapon) "
            "fall in a volley and then disappear. Each creature of your choice that you can see in a 40-foot-radius, 20-foot-high Cylinder centered on that point makes a Dexterity saving throw. "
            "A creature takes 8d8 Force damage on a failed save or half as much damage on a successful one."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "AOE", "Damage", "Force", "Saving Throw"],
    ),
    make_spell(
        name="Contact Other Plane",
        level=5,
        casting_time="1 minute",
        ritual=False,
        range_str="Self",
        components="V",
        duration="1 minute",
        concentration=False,
        class_names=["Warlock", "Wizard"],
        description=(
            "You mentally contact a demigod, the spirit of a long-dead sage, or some other knowledgeable entity from another plane. Contacting this otherworldly intelligence can break your mind. "
            "When you cast this spell, make a DC 15 Intelligence saving throw. On a successful save, you can ask the entity up to five questions. "
            "You must ask your questions before the spell ends. The DM answers each question with one word. If a one-word answer would be misleading, the DM might instead offer a short phrase.\n\n"
            "On a failed save, you take 6d6 Psychic damage and have the Incapacitated condition until you finish a Long Rest. A Greater Restoration spell cast on you ends this effect."
        ),
        source="Player's Handbook",
        tags=["Divination", "Psychic", "Damage", "Debuff", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Contagion",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S",
        duration="7 days",
        concentration=False,
        class_names=["Cleric", "Druid"],
        description=(
            "Your touch inflicts a magical contagion. The target must succeed on a Constitution saving throw or take 11d8 Necrotic damage and have the Poisoned condition. "
            "Also, choose one ability when you cast the spell. While Poisoned, the target has Disadvantage on saving throws made with the chosen ability.\n\n"
            "The target must repeat the saving throw at the end of each of its turns until it gets three successes or failures. If the target succeeds on three of these saves, the spell ends on the target. "
            "If the target fails three of the saves, the spell lasts for 7 days on it.\n\n"
            "Whenever the Poisoned target receives an effect that would end the Poisoned condition, the target must succeed on a Constitution saving throw, or the Poisoned condition doesn’t end on it."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "Damage", "Necrotic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Creation",
        level=5,
        casting_time="1 minute",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (a paintbrush)",
        duration="Special",
        concentration=False,
        class_names=["Artificer", "Sorcerer", "Wizard"],
        description=(
            "You pull wisps of shadow material from the Shadowfell to create an object within range. "
            "It is either an object of vegetable matter or mineral matter. The object must be no larger than a 5-foot Cube, and the object must be of a form and material that you have seen.\n\n"
            "The spell’s duration depends on the object’s material, as shown in the Materials table. If the object is composed of multiple materials, use the shortest duration. "
            "Using any object created by this spell as another spell’s Material component causes the other spell to fail.\n\n"
            "Materials\n"
            "Vegetable matter — 24 hours\n"
            "Stone or crystal — 12 hours\n"
            "Precious metals — 1 hour\n"
            "Gems — 10 minutes\n"
            "Adamantine or mithral — 1 minute\n\n"
            "Using a Higher-Level Spell Slot. The Cube increases by 5 feet for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Illusion", "Utility"],
    ),
    make_spell(
        name="Destructive Wave",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Paladin"],
        description=(
            "Destructive energy ripples outward from you in a 30-foot Emanation. Each creature you choose in the Emanation makes a Constitution saving throw. "
            "On a failed save, a target takes 5d6 Thunder damage and 5d6 Radiant or Necrotic damage (your choice) and has the Prone condition. "
            "On a successful save, a target takes half as much damage only."
        ),
        source="Player's Handbook",
        tags=["Evocation", "AOE", "Thunder", "Radiant", "Necrotic", "Damage", "Saving Throw"],
    ),
    make_spell(
        name="Dispel Evil and Good",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (powdered silver and iron)",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Paladin"],
        description=(
            "For the duration, Celestials, Elementals, Fey, Fiends, and Undead have Disadvantage on attack rolls against you. "
            "You can end the spell early by using either of the following special functions.\n\n"
            "Break Enchantment. As a Magic action, you touch a creature that is possessed by or has the Charmed or Frightened condition from one or more creatures of the types above. "
            "The target is no longer possessed, Charmed, or Frightened by such creatures.\n\n"
            "Dismissal. As a Magic action, you target one creature you can see within 5 feet of you that has one of the creature types above. "
            "The target must succeed on a Charisma saving throw or be sent back to its home plane if it isn’t there already."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Defense", "Utility"],
    ),
    make_spell(
        name="Dominate Person",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Sorcerer", "Wizard"],
        description=(
            "One Humanoid you can see within range must succeed on a Wisdom saving throw or have the Charmed condition for the duration. "
            "Whenever the target takes damage, it repeats the save, ending the spell on itself on a success. You can issue telepathic commands to the target on your turn."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Dream",
        level=5,
        casting_time="1 minute",
        ritual=False,
        range_str="Special",
        components="V, S, M (a handful of sand)",
        duration="8 hours",
        concentration=False,
        class_names=["Bard", "Warlock", "Wizard"],
        description=(
            "You target a creature you know on the same plane of existence. You or a willing creature you touch enters a trance state to act as a dream messenger. "
            "While in the trance, the messenger is Incapacitated and has a Speed of 0.\n\n"
            "If the target is asleep, the messenger appears in the target’s dreams and can converse with the target for the spell’s duration. "
            "The messenger can also shape the dream’s environment. If the target is awake when you cast the spell, the messenger can wait for sleep.\n\n"
            "You can make the messenger terrifying to the target. If you do so, the messenger can deliver a message of no more than ten words, and then the target makes a Wisdom saving throw. "
            "On a failed save, the target gains no benefit from its rest and takes 3d6 Psychic damage when it wakes up."
        ),
        source="Player's Handbook",
        tags=["Illusion", "Utility", "Psychic", "Damage", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Flame Strike",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a pinch of sulfur)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "A vertical column of brilliant fire roars down from above. Each creature in a 10-foot-radius, 40-foot-high Cylinder centered on a point within range makes a Dexterity saving throw, "
            "taking 5d6 Fire damage and 5d6 Radiant damage on a failed save or half as much damage on a successful one.\n\n"
            "Using a Higher-Level Spell Slot. The Fire damage and the Radiant damage increase by 1d6 for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Evocation", "AOE", "Damage", "Fire", "Radiant", "Saving Throw"],
    ),
    make_spell(
        name="Geas",
        level=5,
        casting_time="1 minute",
        ritual=False,
        range_str="60 feet",
        components="V",
        duration="30 days",
        concentration=False,
        class_names=["Bard", "Cleric", "Druid", "Paladin", "Wizard"],
        description=(
            "You give a verbal command to a creature that you can see within range. The target must succeed on a Wisdom saving throw or have the Charmed condition for the duration. "
            "While Charmed, the creature takes 5d10 Psychic damage if it acts in a manner directly counter to your command (no more than once each day). "
            "You can issue any command short of certain death. A Remove Curse, Greater Restoration, or Wish spell ends this spell.\n\n"
            "Using a Higher-Level Spell Slot. If you use a level 7 or 8 spell slot, the duration is 365 days. If you use a level 9 spell slot, the spell lasts until ended by the spells above."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "Debuff", "Psychic", "Damage", "Saving Throw"],
    ),
    make_spell(
        name="Greater Restoration",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S, M (diamond dust worth 100+ GP, which the spell consumes)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Artificer", "Bard", "Cleric", "Druid", "Paladin", "Ranger"],
        description=(
            "You touch a creature and magically remove one of the following effects from it:\n\n"
            "1 Exhaustion level\n"
            "The Charmed or Petrified condition\n"
            "A curse, including the target’s Attunement to a cursed magic item\n"
            "Any reduction to one of the target’s ability scores\n"
            "Any reduction to the target’s Hit Point maximum"
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Healing", "Utility"],
    ),
    make_spell(
        name="Hold Monster",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (a straight piece of iron)",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Choose a creature that you can see within range. The target must succeed on a Wisdom saving throw or have the Paralyzed condition for the duration. "
            "At the end of each of its turns, the target repeats the save, ending the spell on itself on a success. Using a Higher-Level Spell Slot. You can target one additional creature for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Insect Plague",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="300 feet",
        components="V, S, M (a locust)",
        duration="10 minutes",
        concentration=True,
        class_names=["Cleric", "Druid", "Sorcerer"],
        description=(
            "Swarming locusts fill a 20-foot-radius Sphere centered on a point you choose within range. The Sphere remains for the duration and is Lightly Obscured and Difficult Terrain.\n\n"
            "When the swarm appears, each creature in it makes a Constitution saving throw, taking 4d10 Piercing damage on a failed save or half as much on a successful one. "
            "A creature also makes this save when it enters the spell’s area for the first time on a turn or ends its turn there (once per turn).\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d10 for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "AOE", "Damage", "Piercing", "Saving Throw", "DOT"],
    ),
    make_spell(
        name="Legend Lore",
        level=5,
        casting_time="10 minutes",
        ritual=False,
        range_str="Self",
        components="V, S, M (incense worth 250+ GP, which the spell consumes, and four ivory strips worth 50+ GP each)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Cleric", "Wizard"],
        description=(
            "Name or describe a famous person, place, or object. The spell brings to your mind a brief summary of the significant lore about that famous thing, as described by the DM. "
            "The lore might consist of important details, amusing revelations, or even secret lore. If the thing you chose isn’t actually famous, the spell fails."
        ),
        source="Player's Handbook",
        tags=["Divination", "Utility"],
    ),
    make_spell(
        name="Mass Cure Wounds",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Cleric", "Druid"],
        description=(
            "A wave of healing energy washes out from a point you can see within range. "
            "Choose up to six creatures in a 30-foot-radius Sphere centered on that point. Each target regains Hit Points equal to 5d8 plus your spellcasting ability modifier.\n\n"
            "Using a Higher-Level Spell Slot. The healing increases by 1d8 for each spell slot level above 5."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Healing", "AOE"],
    ),
    make_spell(
        name="Mislead",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="S",
        duration="1 hour",
        concentration=True,
        class_names=["Bard", "Warlock", "Wizard"],
        description=(
            "You gain the Invisible condition at the same time that an illusory double of you appears where you are standing. "
            "The double lasts for the duration, but the invisibility ends immediately after you make an attack roll, deal damage, or cast a spell.\n\n"
            "As a Magic action, you can move the illusory double up to twice your Speed and make it gesture, speak, and behave as you choose. "
            "It is intangible and invulnerable. You can see through its eyes and hear through its ears as if you were located where it is."
        ),
        source="Player's Handbook",
        tags=["Illusion", "Utility", "Defense"],
    ),
    make_spell(
        name="Modify Memory",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Wizard"],
        description=(
            "You attempt to reshape another creature’s memories. One creature that you can see within range makes a Wisdom saving throw. "
            "On a failed save, the target has the Charmed condition for the duration and is Incapacitated and unaware of its surroundings, though it can hear you. "
            "While this charm lasts, you can affect the target’s memory of an event that it experienced within the last 24 hours and that lasted no more than 10 minutes.\n\n"
            "You must speak to the target to describe how its memories are affected, and it must understand your language. "
            "If the spell ends before you finish describing the modified memories, the creature’s memory isn’t altered. Otherwise, the modified memories take hold when the spell ends. "
            "Using a Higher-Level Spell Slot. You can alter memories up to 7 days ago (slot 6), 30 days ago (slot 7), 365 days ago (slot 8), or any time in the creature’s past (slot 9)."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "Utility", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Passwall",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (a pinch of sesame seeds)",
        duration="1 hour",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "A passage appears at a point that you can see on a wooden, plaster, or stone surface within range and lasts for the duration. "
            "You choose the opening’s dimensions: up to 5 feet wide, 8 feet tall, and 20 feet deep. The passage creates no instability in a structure surrounding it. "
            "When the opening disappears, any creatures or objects still in the passage are safely ejected to an unoccupied space nearest to the surface."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Utility"],
    ),
    make_spell(
        name="Planar Binding",
        level=5,
        casting_time="1 hour",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a jewel worth 1,000+ GP, which the spell consumes)",
        duration="24 hours",
        concentration=False,
        class_names=["Bard", "Cleric", "Druid", "Warlock", "Wizard"],
        description=(
            "You attempt to bind a Celestial, an Elemental, a Fey, or a Fiend to your service. The creature must be within range for the entire casting. "
            "At the completion of the casting, the target must succeed on a Charisma saving throw or be bound to serve you for the duration. "
            "A bound creature must follow your commands to the best of its ability. If the creature is Hostile, it strives to twist your commands.\n\n"
            "Using a Higher-Level Spell Slot. The duration increases with a spell slot of level 6 (10 days), 7 (30 days), 8 (180 days), and 9 (366 days)."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Utility"],
    ),
    make_spell(
        name="Raise Dead",
        level=5,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (a diamond worth 500+ GP, which the spell consumes)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Cleric", "Paladin"],
        description=(
            "With a touch, you revive a dead creature if it has been dead no longer than 10 days and it wasn’t Undead when it died. "
            "The creature returns to life with 1 Hit Point, neutralizes poisons, and closes mortal wounds, but missing body parts are not restored. "
            "Coming back from the dead is an ordeal; the target takes a −4 penalty to D20 Tests, reduced by 1 after each Long Rest until it reaches 0."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "Healing", "Utility"],
    ),
    make_spell(
        name="Rary's Telepathic Bond",
        level=5,
        casting_time="Action",
        ritual=True,
        range_str="30 feet",
        components="V, S, M (two eggs)",
        duration="1 hour",
        concentration=False,
        class_names=["Bard", "Wizard"],
        description=(
            "You forge a telepathic link among up to eight willing creatures of your choice within range, psychically linking each creature to all the others for the duration. "
            "Creatures that can’t communicate in any languages aren’t affected. The communication is possible over any distance, though it can’t extend to other planes of existence."
        ),
        source="Player's Handbook",
        tags=["Divination", "Utility"],
    ),
    make_spell(
        name="Reincarnate",
        level=5,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (rare oils worth 1,000+ GP, which the spell consumes)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Druid"],
        description=(
            "You touch a dead Humanoid or a piece of one. If the creature has been dead no longer than 10 days, the spell forms a new body for it and calls the soul to enter that body. "
            "Roll 1d10 to determine the body’s species, or the DM chooses another playable species. The reincarnated creature retains its capabilities but gains the traits of its new species."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "Utility", "Healing"],
    ),
    make_spell(
        name="Scrying",
        level=5,
        casting_time="10 minutes",
        ritual=False,
        range_str="Self",
        components="V, S, M (a focus worth 1,000+ GP, such as a crystal ball, mirror, or water-filled font)",
        duration="10 minutes",
        concentration=True,
        class_names=["Bard", "Cleric", "Druid", "Warlock", "Wizard"],
        description=(
            "You can see and hear a creature you choose that is on the same plane of existence as you. The target makes a Wisdom saving throw, modified by how well you know the target and your physical connection to it. "
            "On a failed save, the spell creates an Invisible, intangible sensor within 10 feet of the target that moves with it for the duration."
        ),
        source="Player's Handbook",
        tags=["Divination", "Utility", "Saving Throw"],
    ),
    make_spell(
        name="Seeming",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S",
        duration="8 hours",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Wizard"],
        description=(
            "You give an illusory appearance to each creature of your choice that you can see within range. "
            "An unwilling target can make a Charisma saving throw; if it succeeds, it is unaffected. The spell can change the appearance of the targets’ bodies and equipment within the limits described."
        ),
        source="Player's Handbook",
        tags=["Illusion", "Utility", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Songal's Elemental Suffusion",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a pearl worth 100+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You imbue yourself with the elemental power of genies. Choose one damage type: Acid, Cold, Fire, Lightning, or Thunder. "
            "You have Resistance to the chosen damage type. When you cast the spell and at the start of each of your subsequent turns, you release a burst of elemental energy in a 15-foot Emanation originating from yourself. "
            "Each creature of your choice in that area makes a Dexterity saving throw, taking 2d6 damage of your chosen type and has the Prone condition on a failed save, or half as much damage only on a success. You gain a Fly Speed of 30 feet and can hover."
        ),
        source="Forgotten Realms - Heroes of Faerun",
        tags=["Transmutation", "Buff", "Defense", "Damage", "AOE", "Acid", "Cold", "Fire", "Lightning", "Thunder", "Saving Throw"],
    ),
    make_spell(
        name="Steel Wind Strike",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="S, M (a Melee weapon worth 1+ SP)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Ranger", "Wizard"],
        description=(
            "You flourish the weapon used in the casting and then vanish to strike like the wind. Choose up to five creatures you can see within range. "
            "Make a melee spell attack against each target. On a hit, a target takes 6d10 Force damage. You then teleport to an unoccupied space you can see within 5 feet of one of the targets."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Attack", "Damage", "Force"],
    ),
    make_spell(
        name="Summon Celestial",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (a reliquary worth 500+ GP)",
        duration="1 hour",
        concentration=True,
        class_names=["Cleric", "Paladin"],
        description=(
            "You call forth a Celestial spirit. It manifests in an angelic form in an unoccupied space within range and uses the Celestial Spirit stat block. "
            "When you cast the spell, choose Avenger or Defender. The creature is an ally to you and your allies and disappears when it drops to 0 Hit Points or when the spell ends. "
            "Using a Higher-Level Spell Slot. Use the spell slot’s level for the spell’s level in the stat block."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Damage", "Radiant"],
    ),
    make_spell(
        name="Summon Dragon",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (an object with the image of a dragon engraved on it worth 500+ GP)",
        duration="1 hour",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "You call forth a Dragon spirit. It manifests in an unoccupied space that you can see within range and uses the Draconic Spirit stat block. "
            "The creature is an ally to you and your allies and disappears when it drops to 0 Hit Points or when the spell ends."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Damage"],
    ),
    make_spell(
        name="Swift Quiver",
        level=5,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a Quiver worth 1+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Ranger"],
        description=(
            "When you cast the spell and as a Bonus Action until it ends, you can make two attacks with a weapon that fires Arrows or Bolts. "
            "The spell magically creates the ammunition needed for each attack. Each Arrow or Bolt created by the spell disintegrates immediately after it hits or misses."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Buff", "Attack"],
    ),
    make_spell(
        name="Synaptic Static",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "You cause psychic energy to erupt at a point within range. Each creature in a 20-foot-radius Sphere centered on that point makes an Intelligence saving throw, "
            "taking 8d6 Psychic damage on a failed save or half as much on a successful one. On a failed save, a target also has muddled thoughts for 1 minute, subtracting 1d6 from attacks and ability checks and Concentration saves."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "AOE", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Telekinesis",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You gain the ability to move or manipulate creatures or objects by thought. "
            "When you cast the spell and as a Magic action on your later turns, you can exert your will on one creature or object within range, forcing a Strength saving throw on creatures you move."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Utility", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Tree Stride",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Ranger"],
        description=(
            "You gain the ability to enter a tree and move from inside it to inside another tree of the same kind within 500 feet. "
            "Both trees must be living and at least the same size as you. You can use this transportation ability once on each of your turns and must end each turn outside a tree."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Wall of Force",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a shard of glass)",
        duration="10 minutes",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "An Invisible wall of force springs into existence at a point you choose within range. "
            "You can form it into a dome, globe, or flat panels. Nothing can physically pass through the wall, it is immune to all damage, and a Disintegrate spell destroys it instantly."
        ),
        source="Player's Handbook",
        tags=["Evocation", "Defense", "Utility"],
    ),
    make_spell(
        name="Wall of Stone",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a cube of granite)",
        duration="10 minutes",
        concentration=True,
        class_names=["Artificer", "Druid", "Sorcerer", "Wizard"],
        description=(
            "A nonmagical wall of solid stone springs into existence at a point you choose within range. "
            "The wall is 6 inches thick and composed of ten 10-foot-by-10-foot panels (or 10-foot-by-20-foot panels at 3 inches thick). "
            "If you maintain Concentration for the full duration, the wall becomes permanent and can’t be dispelled."
        ),
        source="Player's Handbook",
        tags=["Evocation", "Defense", "Utility"],
    ),
    make_spell(
        name="Yolande's Regal Presence",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a miniature tiara)",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Wizard"],
        description=(
            "You surround yourself with unearthly majesty in a 10-foot Emanation. Whenever the Emanation enters the space of a creature you can see "
            "and whenever a creature you can see enters the Emanation or ends its turn there, you can force that creature to make a Wisdom saving throw. "
            "On a failed save, the target takes 4d6 Psychic damage and has the Prone condition, and you can push it up to 10 feet away. On a successful save, the target takes half as much damage only. "
            "A creature makes this save only once per turn."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "AOE", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Control Winds",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="300 feet",
        components="V, S",
        duration="1 hour",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You take control of the air in a 100-foot cube that you can see within range. Choose Gusts, Downdraft, or Updraft; the effect lasts for the duration unless you use an action to switch, halt, or restart it."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Utility", "AOE", "Debuff"],
    ),
    make_spell(
        name="Danse Macabre",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="1 hour",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "Threads of dark power leap from your fingers to pierce up to five Small or Medium corpses you can see within range. "
            "Each corpse immediately stands up and becomes undead (zombie or skeleton) and gains a bonus to attack and damage rolls equal to your spellcasting ability modifier. "
            "You can use a bonus action to mentally command the creatures you make with this spell."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Necromancy", "Damage", "Attack"],
    ),
    make_spell(
        name="Dawn",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a sunburst pendant worth at least 100 GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Wizard"],
        description=(
            "The light of dawn shines down on a location you specify within range. Until the spell ends, a 30-foot-radius, 40-foot-high cylinder of bright light glimmers there. "
            "When the cylinder appears, each creature in it must make a Constitution saving throw, taking 4d10 radiant damage on a failed save or half as much on a successful one. "
            "A creature must also make this saving throw whenever it ends its turn in the cylinder. If you’re within 60 feet of the cylinder, you can move it up to 60 feet as a bonus action on your turn."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Damage", "Radiant", "Light", "Saving Throw"],
    ),
    make_spell(
        name="Enervation",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "A tendril of inky darkness reaches out from you, touching a creature you can see within range to drain life from it. "
            "The target must make a Dexterity saving throw. On a successful save, the target takes 2d8 necrotic damage, and the spell ends. "
            "On a failed save, the target takes 4d8 necrotic damage, and until the spell ends, you can use your action each turn to automatically deal 4d8 necrotic damage to the target."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Necromancy", "Damage", "Necrotic", "DOT", "Saving Throw"],
    ),
    make_spell(
        name="Far Step",
        level=5,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You teleport up to 60 feet to an unoccupied space you can see. On each of your turns before the spell ends, you can use a bonus action to teleport in this way again."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Holy Weapon",
        level=5,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Touch",
        components="V, S",
        duration="1 hour",
        concentration=True,
        class_names=["Cleric", "Paladin"],
        description=(
            "You imbue a weapon you touch with holy power. Until the spell ends, the weapon emits bright light in a 30-foot radius and dim light for an additional 30 feet. "
            "Weapon attacks made with it deal an extra 2d8 radiant damage on a hit. As a bonus action, you can dismiss this spell to burst radiance: each creature of your choice within 30 feet must make a Constitution saving throw, taking 4d8 radiant damage on a failed save or half as much on a success; on a failed save, the creature is blinded for 1 minute (save at end of each turn)."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "Buff", "Radiant", "Damage", "Light", "Saving Throw"],
    ),
    make_spell(
        name="Immolation",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "Flames wreathe one creature you can see within range. The target must make a Dexterity saving throw. "
            "It takes 8d6 fire damage on a failed save, or half as much on a successful one. On a failed save, the target also burns for the spell’s duration, shedding light, and repeats the save at the end of each of its turns, taking 4d6 fire damage on a failed save, ending the spell on a success."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "Fire", "Damage", "DOT", "Saving Throw"],
    ),
    make_spell(
        name="Infernal Calling",
        level=5,
        casting_time="1 minute",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (a ruby worth at least 999 GP)",
        duration="1 hour",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "Uttering a dark incantation, you summon a devil from the Nine Hells of challenge rating 6 or lower. "
            "The devil is unfriendly and acts according to its nature but can be commanded with Charisma checks. The devil disappears when it drops to 0 hit points or when the spell ends."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "Damage"],
    ),
    make_spell(
        name="Maelstrom",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (paper or leaf in the shape of a funnel)",
        duration="1 minute",
        concentration=True,
        class_names=["Druid"],
        description=(
            "A mass of 5-foot-deep water appears and swirls in a 30-foot radius centered on a point you can see within range. "
            "Until the spell ends, that area is difficult terrain, and any creature that starts its turn there must succeed on a Strength saving throw or take 6d6 bludgeoning damage and be pulled 10 feet toward the center."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Damage", "Bludgeoning", "Saving Throw"],
    ),
    make_spell(
        name="Negative Energy Flood",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, M (a broken bone and a square of black silk)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Warlock", "Wizard"],
        description=(
            "You send ribbons of negative energy at one creature you can see within range. Unless the target is undead, it must make a Constitution saving throw, taking 5d12 necrotic damage on a failed save, or half as much on a successful one. "
            "A target killed by this damage rises as a zombie at the start of your next turn. If you target an undead, it gains temporary hit points instead of making the save."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Necromancy", "Damage", "Necrotic", "Saving Throw"],
    ),
    make_spell(
        name="Skill Empowerment",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S",
        duration="1 hour",
        concentration=True,
        class_names=["Bard", "Sorcerer", "Wizard", "Artificer"],
        description=(
            "Your magic deepens a creature’s understanding of its own talent. You touch one willing creature and give it expertise in one skill of your choice; "
            "until the spell ends, the creature doubles its proficiency bonus for ability checks it makes that use the chosen skill."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Utility"],
    ),
    make_spell(
        name="Summon Draconic Spirit",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (an object with the image of a dragon engraved on it, worth at least 500 GP)",
        duration="1 hour",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You call forth a draconic spirit. It manifests in an unoccupied space that you can see within range and uses the Draconic Spirit stat block. "
            "When you cast this spell, choose a family of dragon: chromatic, gem, or metallic. The creature is an ally to you and your companions and disappears when it drops to 0 hit points or when the spell ends."
        ),
        source="Fizban's Treasury of Dragons",
        tags=["Conjuration", "Damage"],
    ),
    make_spell(
        name="Temporal Shunt",
        level=5,
        casting_time="Reaction",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="1 round",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "When a creature you see makes an attack roll or starts to cast a spell, it must succeed on a Wisdom saving throw or vanish, being thrown to another point in time and causing the attack to miss or the spell to be wasted. "
            "At the start of its next turn, the target reappears where it was or in the closest unoccupied space. The target doesn't remember you casting the spell or being affected by it."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Transmutation", "Debuff", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Transmute Rock",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (clay and water)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Druid", "Wizard", "Artificer"],
        description=(
            "You choose an area of stone or mud that you can see that fits within a 40-foot cube and choose one of the following effects.\n\n"
            "Transmute Rock to Mud. Nonmagical rock in the area becomes thick mud. Each foot costs 4 feet of movement; creatures may become restrained on a failed Strength save. "
            "If cast on a ceiling, the mud falls, dealing 4d8 bludgeoning damage on a failed Dexterity save (half on success).\n\n"
            "Transmute Mud to Rock. Nonmagical mud or quicksand in the area transforms into soft stone. Creatures in the mud make a Dexterity saving throw; on a failed save, a creature becomes restrained by the rock (DC 20 Strength check or 25 damage to break free)."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "AOE", "Utility", "Debuff", "Bludgeoning", "Damage", "Saving Throw"],
    ),
    make_spell(
        name="Wall of Light",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a hand mirror)",
        duration="10 minutes",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "A shimmering wall of bright light appears at a point you choose within range. The wall can be up to 60 feet long, 10 feet high, and 5 feet thick and blocks line of sight. "
            "When the wall appears, each creature in its area must make a Constitution saving throw, taking 4d8 radiant damage on a failed save and is blinded for 1 minute, or half as much damage and no blindness on a success. "
            "A creature that ends its turn in the wall’s area takes 4d8 radiant damage. Until the spell ends, you can use an action to launch a beam of radiance from the wall at one creature within 60 feet of it, dealing 4d8 radiant damage on a hit and reducing the wall’s length by 10 feet."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Damage", "Radiant", "Light", "Saving Throw"],
    ),
    make_spell(
        name="Wrath Of Nature",
        level=5,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Ranger"],
        description=(
            "You call out to the spirits of nature to rouse them against your enemies. Choose a point you can see within range. "
            "Trees, rocks, and grasses in a 60-foot cube centered on that point become animated until the spell ends, creating difficult terrain for enemies, dealing slashing damage from trees, restraining with roots and vines, and hurling rocks as a bonus action."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Damage", "Slashing", "Bludgeoning", "Debuff", "Saving Throw"],
    ),
]


def main():
    manager = SpellManager()
    manager.load_spells()

    added = []
    skipped = []

    for spell in spells:
        if manager.get_spell(spell.name):
            skipped.append(spell.name)
            continue
        if manager.add_spell(spell):
            added.append(spell.name)
        else:
            skipped.append(spell.name)

    print({
        "added": len(added),
        "skipped": len(skipped),
        "added_names": added,
        "skipped_names": skipped,
    })


if __name__ == "__main__":
    main()