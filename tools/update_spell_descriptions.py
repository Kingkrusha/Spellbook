"""
Script to update spell descriptions to exact word-for-word text.
This script updates existing spells in the database with the correct descriptions.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from database import SpellDatabase


def get_spell_updates():
    """Return a dictionary of spell name -> updated fields."""
    
    updates = {}
    
    # ============================================
    # LEVEL 5 SPELLS
    # ============================================
    
    updates["Alustriel's Mooncloak"] = {
        "source": "Forgotten Realms - Heroes of Faerun",
        "description": (
            "For the duration, moonlight fills a 20-foot Emanation originating from you with Dim Light. "
            "While in that area, you and your allies have Half Cover and Resistance to Cold, Lightning, and Radiant damage.\n\n"
            "While the spell lasts, you can use one of the following options, ending the spell immediately:\n\n"
            "Liberation. When you fail a saving throw to avoid or end the Frightened, Grappled, or Restrained condition, "
            "you can take a Reaction to succeed on the save instead.\n\n"
            "Respite. As a Magic action, you or an ally within the area regains Hit Points equal to 4d10 plus your spellcasting ability modifier."
        ),
    }
    
    updates["Animate Objects"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Objects animate at your command. Choose a number of nonmagical objects within range that aren't being worn or carried, "
            "aren't fixed to a surface, and aren't Gargantuan. The maximum number of objects is equal to your spellcasting ability modifier; "
            "for this number, a Medium or smaller target counts as one object, a Large target counts as two, and a Huge target counts as three.\n\n"
            "Each target animates, sprouts legs, and becomes a Construct that uses the Animated Object stat block; "
            "this creature is under your control until the spell ends or until it is reduced to 0 Hit Points. "
            "Each creature you make with this spell is an ally to you and your allies. In combat, it shares your Initiative count and takes its turn immediately after yours.\n\n"
            "Until the spell ends, you can take a Bonus Action to mentally command any creature you made with this spell if the creature is within 500 feet of you "
            "(if you control multiple creatures, you can command any of them at the same time, issuing the same command to each one). "
            "If you issue no commands, the creature takes the Dodge action and moves only to avoid harm. "
            "When the creature drops to 0 Hit Points, it reverts to its object form, and any remaining damage carries over to that form.\n\n"
            "Using a Higher-Level Spell Slot. The creature's Slam damage increases by 1d4 (Medium or smaller), 1d6 (Large), or 1d12 (Huge) for each spell slot level above 5."
        ),
    }
    
    updates["Antilife Shell"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "An aura extends from you in a 10-foot Emanation for the duration. "
            "The aura prevents creatures other than Constructs and Undead from passing or reaching through it. "
            "An affected creature can cast spells or make attacks with Ranged or Reach weapons through the barrier.\n\n"
            "If you move so that an affected creature is forced to pass through the barrier, the spell ends."
        ),
    }
    
    updates["Awaken"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You spend the casting time tracing magical pathways within a precious gemstone, and then touch the target. "
            "The target must be either a Beast or Plant creature with an Intelligence of 3 or less or a natural plant that isn't a creature. "
            "The target gains an Intelligence of 10 and the ability to speak one language you know. "
            "If the target is a natural plant, it becomes a Plant creature and gains the ability to move its limbs, roots, vines, creepers, and so forth, "
            "and it gains senses similar to a human's. The DM chooses statistics appropriate for the awakened Plant, "
            "such as the statistics for the Awakened Shrub or Awakened Tree in the Monster Manual.\n\n"
            "The awakened target has the Charmed condition for 30 days or until you or your allies deal damage to it. "
            "When that condition ends, the awakened creature chooses its attitude toward you."
        ),
    }
    
    updates["Banishing Smite"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "The target hit by the attack roll takes an extra 5d10 Force damage from the attack. "
            "If the attack reduces the target to 50 Hit Points or fewer, the target must succeed on a Charisma saving throw "
            "or be transported to a harmless demiplane for the duration. While there, the target has the Incapacitated condition. "
            "When the spell ends, the target reappears in the space it left or in the nearest unoccupied space if that space is occupied."
        ),
    }
    
    updates["Bigby's Hand"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a Large hand of shimmering magical energy in an unoccupied space that you can see within range. "
            "The hand lasts for the duration, and it moves at your command, mimicking the movements of your own hand.\n\n"
            "The hand is an object that has AC 20 and Hit Points equal to your Hit Point maximum. "
            "If it drops to 0 Hit Points, the spell ends. The hand doesn't occupy its space.\n\n"
            "When you cast the spell and as a Bonus Action on your later turns, you can move the hand up to 60 feet "
            "and then cause one of the following effects:\n\n"
            "Clenched Fist. The hand strikes a target within 5 feet of it. Make a melee spell attack. On a hit, the target takes 5d8 Force damage.\n\n"
            "Forceful Hand. The hand attempts to push a Huge or smaller creature within 5 feet of it. "
            "The target must succeed on a Strength saving throw, or the hand pushes the target up to 5 feet plus a number of feet equal to five times your spellcasting ability modifier. "
            "The hand moves with the target, remaining within 5 feet of it.\n\n"
            "Grasping Hand. The hand attempts to grapple a Huge or smaller creature within 5 feet of it. "
            "The target must succeed on a Dexterity saving throw, or the target has the Grappled condition, with an escape DC equal to your spell save DC. "
            "While the hand grapples the target, you can take a Bonus Action to cause the hand to crush it, "
            "dealing Bludgeoning damage to the target equal to 4d6 plus your spellcasting ability modifier.\n\n"
            "Interposing Hand. The hand grants you Half Cover against attacks and other effects that originate from its space or that pass through it. "
            "In addition, its space counts as Difficult Terrain for your enemies.\n\n"
            "Using a Higher-Level Spell Slot. The damage of the Clenched Fist increases by 2d8 and the damage of the Grasping Hand increases by 2d6 for each spell slot level above 5."
        ),
    }
    
    updates["Circle of Power"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "An aura radiates from you in a 30-foot Emanation for the duration. "
            "While in the aura, you and your allies have Advantage on saving throws against spells and other magical effects. "
            "When an affected creature makes a saving throw against a spell or magical effect that allows a save to take only half damage, "
            "it takes no damage if it succeeds on the save."
        ),
    }
    
    updates["Cloudkill"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a 20-foot-radius Sphere of yellow-green fog centered on a point within range. "
            "The fog lasts for the duration or until strong wind (such as the one created by Gust of Wind) disperses it, ending the spell. "
            "Its area is Heavily Obscured.\n\n"
            "Each creature in the Sphere makes a Constitution saving throw, taking 5d8 Poison damage on a failed save or half as much damage on a successful one. "
            "A creature must also make this save when the Sphere moves into its space and when it enters the Sphere or ends its turn there. "
            "A creature makes this save only once per turn.\n\n"
            "The Sphere moves 10 feet away from you at the start of each of your turns.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 5."
        ),
    }
    
    updates["Commune"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You contact a deity or a divine proxy and ask up to three questions that can be answered with yes or no. "
            "You must ask your questions before the spell ends. You receive a correct answer for each question.\n\n"
            "Divine beings aren't necessarily omniscient, so you might receive \"unclear\" as an answer if a question pertains to information that lies beyond the deity's knowledge. "
            "In a case where a one-word answer could be misleading or contrary to the deity's interests, the DM might offer a short phrase as an answer instead.\n\n"
            "If you cast the spell more than once before finishing a Long Rest, there is a cumulative 25 percent chance for each casting after the first that you get no answer."
        ),
    }
    
    updates["Commune with Nature"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You commune with nature spirits and gain knowledge of the surrounding area. "
            "In the outdoors, the spell gives you knowledge of the area within 3 miles of you. "
            "In caves and other natural underground settings, the radius is limited to 300 feet. "
            "The spell doesn't function where nature has been replaced by construction, such as in castles and settlements.\n\n"
            "Choose three of the following facts; you learn those facts as they pertain to the spell's area:\n\n"
            "Locations of settlements\n"
            "Locations of portals to other planes of existence\n"
            "Location of one Challenge Rating 10+ creature (DM's choice) that is a Celestial, an Elemental, a Fey, a Fiend, or an Undead\n"
            "The most prevalent kind of plant, mineral, or Beast (you choose which to learn)\n"
            "Locations of bodies of water\n\n"
            "For example, you could determine the location of a powerful monster in the area, the locations of bodies of water, and the locations of any towns."
        ),
    }
    
    updates["Cone of Cold"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You unleash a blast of cold air. Each creature in a 60-foot Cone originating from you makes a Constitution saving throw, "
            "taking 8d8 Cold damage on a failed save or half as much damage on a successful one. "
            "A creature killed by this spell becomes a frozen statue until it thaws.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 5."
        ),
    }
    
    updates["Conjure Elemental"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You conjure a Large, intangible spirit from the Elemental Planes that appears in an unoccupied space within range. "
            "Choose the spirit's element, which determines its damage type: air (Lightning), earth (Thunder), fire (Fire), or water (Cold). "
            "The spirit lasts for the duration.\n\n"
            "Whenever a creature you can see enters the spirit's space or starts its turn within 5 feet of the spirit, "
            "you can force that creature to make a Dexterity saving throw if the spirit has no creature Restrained. "
            "On failed save, the target takes 8d8 damage of the spirit's type, and the target has the Restrained condition until the spell ends. "
            "At the start of each of its turns, the Restrained target repeats the save. "
            "On a failed save, the target takes 4d8 damage of the spirit's type. On a successful save, the target isn't Restrained by the spirit.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 5."
        ),
    }
    
    updates["Conjure Volley"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You brandish the weapon used to cast the spell and choose a point within range. "
            "Hundreds of similar spectral weapons (or ammunition appropriate to the weapon) fall in a volley and then disappear. "
            "Each creature of your choice that you can see in a 40-foot-radius, 20-foot-high Cylinder centered on that point makes a Dexterity saving throw. "
            "A creature takes 8d8 Force damage on a failed save or half as much damage on a successful one."
        ),
    }
    
    updates["Contact Other Plane"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You mentally contact a demigod, the spirit of a long-dead sage, or some other knowledgeable entity from another plane. "
            "Contacting this otherworldly intelligence can break your mind. When you cast this spell, make a DC 15 Intelligence saving throw. "
            "On a successful save, you can ask the entity up to five questions. You must ask your questions before the spell ends. "
            "The DM answers each question with one word, such as \"yes,\" \"no,\" \"maybe,\" \"never,\" \"irrelevant,\" or \"unclear\" (if the entity doesn't know the answer to the question). "
            "If a one-word answer would be misleading, the DM might instead offer a short phrase as an answer.\n\n"
            "On a failed save, you take 6d6 Psychic damage and have the Incapacitated condition until you finish a Long Rest. "
            "A Greater Restoration spell cast on you ends this effect."
        ),
    }
    
    updates["Contagion"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Your touch inflicts a magical contagion. The target must succeed on a Constitution saving throw or take 11d8 Necrotic damage and have the Poisoned condition. "
            "Also, choose one ability when you cast the spell. While Poisoned, the target has Disadvantage on saving throws made with the chosen ability.\n\n"
            "The target must repeat the saving throw at the end of each of its turns until it gets three successes or failures. "
            "If the target succeeds on three of these saves, the spell ends on the target. If the target fails three of the saves, the spell lasts for 7 days on it.\n\n"
            "Whenever the Poisoned target receives an effect that would end the Poisoned condition, the target must succeed on a Constitution saving throw, "
            "or the Poisoned condition doesn't end on it."
        ),
    }
    
    updates["Creation"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You pull wisps of shadow material from the Shadowfell to create an object within range. "
            "It is either an object of vegetable matter (soft goods, rope, wood, and the like) or mineral matter (stone, crystal, metal, and the like). "
            "The object must be no larger than a 5-foot Cube, and the object must be of a form and material that you have seen.\n\n"
            "The spell's duration depends on the object's material, as shown in the Materials table. "
            "If the object is composed of multiple materials, use the shortest duration. "
            "Using any object created by this spell as another spell's Material component causes the other spell to fail.\n\n"
            "Materials\n"
            "Material - Duration\n"
            "Vegetable matter - 24 hours\n"
            "Stone or crystal - 12 hours\n"
            "Precious metals - 1 hour\n"
            "Gems - 10 minutes\n"
            "Adamantine or mithral - 1 minute\n\n"
            "Using a Higher-Level Spell Slot. The Cube increases by 5 feet for each spell slot level above 5."
        ),
    }
    
    updates["Destructive Wave"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Destructive energy ripples outward from you in a 30-foot Emanation. "
            "Each creature you choose in the Emanation makes a Constitution saving throw. "
            "On a failed save, a target takes 5d6 Thunder damage and 5d6 Radiant or Necrotic damage (your choice) and has the Prone condition. "
            "On a successful save, a target takes half as much damage only."
        ),
    }
    
    updates["Dispel Evil and Good"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "For the duration, Celestials, Elementals, Fey, Fiends, and Undead have Disadvantage on attack rolls against you. "
            "You can end the spell early by using either of the following special functions.\n\n"
            "Break Enchantment. As a Magic action, you touch a creature that is possessed by or has the Charmed or Frightened condition from one or more creatures of the types above. "
            "The target is no longer possessed, Charmed, or Frightened by such creatures.\n\n"
            "Dismissal. As a Magic action, you target one creature you can see within 5 feet of you that has one of the creature types above. "
            "The target must succeed on a Charisma saving throw or be sent back to its home plane if it isn't there already. "
            "If they aren't on their home plane, Undead are sent to the Shadowfell, and Fey are sent to the Feywild."
        ),
    }
    
    updates["Dominate Person"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "One Humanoid you can see within range must succeed on a Wisdom saving throw or have the Charmed condition for the duration. "
            "The target has Advantage on the save if you or your allies are fighting it. Whenever the target takes damage, it repeats the save, ending the spell on itself on a success.\n\n"
            "You have a telepathic link with the Charmed target while the two of you are on the same plane of existence. "
            "On your turn, you can use this link to issue commands to the target (no action required), such as \"Attack that creature,\" \"Move over there,\" or \"Fetch that object.\" "
            "The target does its best to obey on its turn. If it completes an order and doesn't receive further direction from you, it acts and moves as it likes, focusing on protecting itself.\n\n"
            "You can command the target to take a Reaction but must take your own Reaction to do so.\n\n"
            "Using a Higher-Level Spell Slot. Your Concentration can last longer with a spell slot of level 6 (up to 10 minutes), 7 (up to 1 hour), or 8+ (up to 8 hours)."
        ),
    }
    
    updates["Dream"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You target a creature you know on the same plane of existence. You or a willing creature you touch enters a trance state to act as a dream messenger. "
            "While in the trance, the messenger is Incapacitated and has a Speed of 0.\n\n"
            "If the target is asleep, the messenger appears in the target's dreams and can converse with the target as long as it remains asleep, through the spell's duration. "
            "The messenger can also shape the dream's environment, creating landscapes, objects, and other images. "
            "The messenger can emerge from the trance at any time, ending the spell. The target recalls the dream perfectly upon waking.\n\n"
            "If the target is awake when you cast the spell, the messenger knows it and can either end the trance (and the spell) or wait for the target to sleep, "
            "at which point the messenger enters its dreams.\n\n"
            "You can make the messenger terrifying to the target. If you do so, the messenger can deliver a message of no more than ten words, "
            "and then the target makes a Wisdom saving throw. On a failed save, the target gains no benefit from its rest, and it takes 3d6 Psychic damage when it wakes up."
        ),
    }
    
    updates["Flame Strike"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A vertical column of brilliant fire roars down from above. "
            "Each creature in a 10-foot-radius, 40-foot-high Cylinder centered on a point within range makes a Dexterity saving throw, "
            "taking 5d6 Fire damage and 5d6 Radiant damage on a failed save or half as much damage on a successful one.\n\n"
            "Using a Higher-Level Spell Slot. The Fire damage and the Radiant damage increase by 1d6 for each spell slot level above 5."
        ),
    }
    
    updates["Geas"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You give a verbal command to a creature that you can see within range, ordering it to carry out some service or refrain from an action or a course of activity as you decide. "
            "The target must succeed on a Wisdom saving throw or have the Charmed condition for the duration. The target automatically succeeds if it can't understand your command.\n\n"
            "While Charmed, the creature takes 5d10 Psychic damage if it acts in a manner directly counter to your command. It takes this damage no more than once each day.\n\n"
            "You can issue any command you choose, short of an activity that would result in certain death. Should you issue a suicidal command, the spell ends.\n\n"
            "A Remove Curse, Greater Restoration, or Wish spell ends this spell.\n\n"
            "Using a Higher-Level Spell Slot. If you use a level 7 or 8 spell slot, the duration is 365 days. If you use a level 9 spell slot, the spell lasts until it is ended by one of the spells mentioned above."
        ),
    }
    
    updates["Greater Restoration"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You touch a creature and magically remove one of the following effects from it:\n\n"
            "1 Exhaustion level\n"
            "The Charmed or Petrified condition\n"
            "A curse, including the target's Attunement to a cursed magic item\n"
            "Any reduction to one of the target's ability scores\n"
            "Any reduction to the target's Hit Point maximum"
        ),
    }
    
    updates["Hold Monster"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Choose a creature that you can see within range. The target must succeed on a Wisdom saving throw or have the Paralyzed condition for the duration. "
            "At the end of each of its turns, the target repeats the save, ending the spell on itself on a success.\n\n"
            "Using a Higher-Level Spell Slot. You can target one additional creature for each spell slot level above 5."
        ),
    }
    
    updates["Insect Plague"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Swarming locusts fill a 20-foot-radius Sphere centered on a point you choose within range. "
            "The Sphere remains for the duration, and its area is Lightly Obscured and Difficult Terrain.\n\n"
            "When the swarm appears, each creature in it makes a Constitution saving throw, taking 4d10 Piercing damage on a failed save or half as much damage on a successful one. "
            "A creature also makes this save when it enters the spell's area for the first time on a turn or ends its turn there. A creature makes this save only once per turn.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d10 for each spell slot level above 5."
        ),
    }
    
    updates["Legend Lore"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Name or describe a famous person, place, or object. The spell brings to your mind a brief summary of the significant lore about that famous thing, as described by the DM.\n\n"
            "The lore might consist of important details, amusing revelations, or even secret lore that has never been widely known. "
            "The more information you already know about the thing, the more precise and detailed the information you receive is. "
            "That information is accurate but might be couched in figurative language or poetry, as determined by the DM.\n\n"
            "If the famous thing you chose isn't actually famous, you hear sad musical notes played on a trombone, and the spell fails."
        ),
    }
    
    updates["Mass Cure Wounds"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A wave of healing energy washes out from a point you can see within range. "
            "Choose up to six creatures in a 30-foot-radius Sphere centered on that point. "
            "Each target regains Hit Points equal to 5d8 plus your spellcasting ability modifier.\n\n"
            "Using a Higher-Level Spell Slot. The healing increases by 1d8 for each spell slot level above 5."
        ),
    }
    
    updates["Mislead"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You gain the Invisible condition at the same time that an illusory double of you appears where you are standing. "
            "The double lasts for the duration, but the invisibility ends immediately after you make an attack roll, deal damage, or cast a spell.\n\n"
            "As a Magic action, you can move the illusory double up to twice your Speed and make it gesture, speak, and behave in whatever way you choose. "
            "It is intangible and invulnerable.\n\n"
            "You can see through its eyes and hear through its ears as if you were located where it is."
        ),
    }
    
    updates["Modify Memory"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You attempt to reshape another creature's memories. One creature that you can see within range makes a Wisdom saving throw. "
            "If you are fighting the creature, it has Advantage on the save. On a failed save, the target has the Charmed condition for the duration. "
            "While Charmed in this way, the target also has the Incapacitated condition and is unaware of its surroundings, though it can hear you. "
            "If it takes any damage or is targeted by another spell, this spell ends, and no memories are modified.\n\n"
            "While this charm lasts, you can affect the target's memory of an event that it experienced within the last 24 hours and that lasted no more than 10 minutes. "
            "You can permanently eliminate all memory of the event, allow the target to recall the event with perfect clarity, change its memory of the event's details, "
            "or create a memory of some other event.\n\n"
            "You must speak to the target to describe how its memories are affected, and it must be able to understand your language for the modified memories to take root. "
            "Its mind fills in any gaps in the details of your description. If the spell ends before you finish describing the modified memories, the creature's memory isn't altered. "
            "Otherwise, the modified memories take hold when the spell ends.\n\n"
            "A modified memory doesn't necessarily affect how a creature behaves, particularly if the memory contradicts the creature's natural inclinations, alignment, or beliefs. "
            "An illogical modified memory, such as a false memory of how much the creature enjoyed swimming in acid, is dismissed as a bad dream. "
            "The DM might deem a modified memory too nonsensical to affect a creature.\n\n"
            "A Remove Curse or Greater Restoration spell cast on the target restores the creature's true memory.\n\n"
            "Using a Higher-Level Spell Slot. You can alter the target's memories of an event that took place up to 7 days ago (level 6 spell slot), "
            "30 days ago (level 7 spell slot), 365 days ago (level 8 spell slot), or any time in the creature's past (level 9 spell slot)."
        ),
    }
    
    updates["Passwall"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A passage appears at a point that you can see on a wooden, plaster, or stone surface (such as a wall, ceiling, or floor) within range and lasts for the duration. "
            "You choose the opening's dimensions: up to 5 feet wide, 8 feet tall, and 20 feet deep. The passage creates no instability in a structure surrounding it.\n\n"
            "When the opening disappears, any creatures or objects still in the passage created by the spell are safely ejected to an unoccupied space nearest to the surface on which you cast the spell."
        ),
    }
    
    updates["Planar Binding"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You attempt to bind a Celestial, an Elemental, a Fey, or a Fiend to your service. "
            "The creature must be within range for the entire casting of the spell. "
            "(Typically, the creature is first summoned into the center of the inverted version of the Magic Circle spell to trap it while this spell is cast.) "
            "At the completion of the casting, the target must succeed on a Charisma saving throw or be bound to serve you for the duration. "
            "If the creature was summoned or created by another spell, that spell's duration is extended to match the duration of this spell.\n\n"
            "A bound creature must follow your commands to the best of its ability. You might command the creature to accompany you on an adventure, to guard a location, or to deliver a message. "
            "If the creature is Hostile, it strives to twist your commands to achieve its own objectives. "
            "If the creature carries out your commands completely before the spell ends, it travels to you to report this fact if you are on the same plane of existence. "
            "If you are on a different plane, it returns to the place where you bound it and remains there until the spell ends.\n\n"
            "Using a Higher-Level Spell Slot. The duration increases with a spell slot of level 6 (10 days), 7 (30 days), 8 (180 days), and 9 (366 days)."
        ),
    }
    
    updates["Raise Dead"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "With a touch, you revive a dead creature if it has been dead no longer than 10 days and it wasn't Undead when it died.\n\n"
            "The creature returns to life with 1 Hit Point. This spell also neutralizes any poisons that affected the creature at the time of death.\n\n"
            "This spell closes all mortal wounds, but it doesn't restore missing body parts. "
            "If the creature is lacking body parts or organs integral for its survival - its head, for instance - the spell automatically fails.\n\n"
            "Coming back from the dead is an ordeal. The target takes a −4 penalty to D20 Tests. "
            "Every time the target finishes a Long Rest, the penalty is reduced by 1 until it becomes 0."
        ),
    }
    
    updates["Rary's Telepathic Bond"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You forge a telepathic link among up to eight willing creatures of your choice within range, psychically linking each creature to all the others for the duration. "
            "Creatures that can't communicate in any languages aren't affected by this spell.\n\n"
            "Until the spell ends, the targets can communicate telepathically through the bond whether or not they share a language. "
            "The communication is possible over any distance, though it can't extend to other planes of existence."
        ),
    }
    
    updates["Reincarnate"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You touch a dead Humanoid or a piece of one. If the creature has been dead no longer than 10 days, "
            "the spell forms a new body for it and calls the soul to enter that body. Roll 1d10 and consult the table below to determine the body's species, "
            "or the DM chooses another playable species.\n\n"
            "1d10 - Species\n"
            "1 - Aasimar\n"
            "2 - Dragonborn\n"
            "3 - Dwarf\n"
            "4 - Elf\n"
            "5 - Gnome\n"
            "6 - Goliath\n"
            "7 - Halfling\n"
            "8 - Human\n"
            "9 - Orc\n"
            "10 - Tiefling\n\n"
            "The reincarnated creature makes any choices that a species' description offers, and the creature recalls its former life. "
            "It retains the capabilities it had in its original form, except it loses the traits of its previous species and gains the traits of its new one."
        ),
    }
    
    updates["Scrying"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You can see and hear a creature you choose that is on the same plane of existence as you. "
            "The target makes a Wisdom saving throw, which is modified (see the tables below) by how well you know the target and the sort of physical connection you have to it. "
            "The target doesn't know what it is making the save against, only that it feels uneasy.\n\n"
            "Your Knowledge of the Target Is... - Save Modifier\n"
            "Secondhand (heard of the target) - +5\n"
            "Firsthand (met the target) - +0\n"
            "Extensive (know the target well) - -5\n\n"
            "You Have the Target's... - Save Modifier\n"
            "Picture or other likeness - -2\n"
            "Garment or other possession - -4\n"
            "Body part, lock of hair, or bit of nail - -10\n\n"
            "On a successful save, the target isn't affected, and you can't use this spell on it again for 24 hours.\n\n"
            "On a failed save, the spell creates an Invisible, intangible sensor within 10 feet of the target. "
            "You can see and hear through the sensor as if you were there. The sensor moves with the target, remaining within 10 feet of it for the duration. "
            "If something can see the sensor, it appears as a luminous orb about the size of your fist.\n\n"
            "Instead of targeting a creature, you can target a location you have seen. When you do so, the sensor appears at that location and doesn't move."
        ),
    }
    
    updates["Seeming"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You give an illusory appearance to each creature of your choice that you can see within range. "
            "An unwilling target can make a Charisma saving throw, and if it succeeds, it is unaffected by this spell.\n\n"
            "You can give the same appearance or different ones to the targets. The spell can change the appearance of the targets' bodies and equipment. "
            "You can make each creature seem 1 foot shorter or taller and appear heavier or lighter. "
            "A target's new appearance must have the same basic arrangement of limbs as the target, but the extent of the illusion is otherwise up to you. "
            "The spell lasts for the duration.\n\n"
            "The changes wrought by this spell fail to hold up to physical inspection. "
            "For example, if you use this spell to add a hat to a creature's outfit, objects pass through the hat.\n\n"
            "A creature that takes the Study action to examine a target can make an Intelligence (Investigation) check against your spell save DC. "
            "If it succeeds, it becomes aware that the target is disguised."
        ),
    }
    
    updates["Songal's Elemental Suffusion"] = {
        "source": "Forgotten Realms - Heroes of Faerun",
        "description": (
            "You imbue yourself with the elemental power of genies. You gain the following benefits until the spell ends:\n\n"
            "Elemental Immunity. When you cast this spell, choose one of the following damage types: Acid, Cold, Fire, Lightning, or Thunder. "
            "You have Resistance to the chosen damage type.\n\n"
            "Elemental Pulse. When you cast this spell and at the start of each of your subsequent turns, you release a burst of elemental energy in a 15-foot Emanation originating from yourself. "
            "Each creature of your choice in that area makes a Dexterity saving throw. On a failed save, a creature takes 2d6 Acid, Cold, Fire, Lightning, or Thunder damage (your choice) and has the Prone condition. "
            "On a successful save, a creature takes half as much damage only.\n\n"
            "Flight. You gain a Fly Speed of 30 feet and can hover.\n\n"
            "Casting as a Circle Spell. If the spell is cast as a Circle spell, its casting time increases to 1 minute, and its duration increases to Concentration, up to 10 minutes. "
            "For each secondary caster who participates in the casting, you can choose one additional creature, to a maximum of nine additional creatures. "
            "The chosen creatures also gain the benefits of the spell for its duration.\n\n"
            "When the spell is cast, each secondary caster must expend a level 2+ spell slot; otherwise, the spell fails."
        ),
    }
    
    updates["Steel Wind Strike"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You flourish the weapon used in the casting and then vanish to strike like the wind. "
            "Choose up to five creatures you can see within range. Make a melee spell attack against each target. "
            "On a hit, a target takes 6d10 Force damage.\n\n"
            "You then teleport to an unoccupied space you can see within 5 feet of one of the targets."
        ),
    }
    
    updates["Summon Celestial"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You call forth a Celestial spirit. It manifests in an angelic form in an unoccupied space that you can see within range and uses the Celestial Spirit stat block. "
            "When you cast the spell, choose Avenger or Defender. Your choice determines certain details in its stat block. "
            "The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
            "The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
            "It obeys your verbal commands (no action required by you). If you don't issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
            "Using a Higher-Level Spell Slot. Use the spell slot's level for the spell's level in the stat block."
        ),
    }
    
    updates["Summon Dragon"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You call forth a Dragon spirit. It manifests in an unoccupied space that you can see within range and uses the Draconic Spirit stat block. "
            "The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
            "The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
            "It obeys your verbal commands (no action required by you). If you don't issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
            "Using a Higher-Level Spell Slot. Use the spell slot's level for the spell's level in the stat block."
        ),
    }
    
    updates["Swift Quiver"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "When you cast the spell and as a Bonus Action until it ends, you can make two attacks with a weapon that fires Arrows or Bolts, such as a Longbow or a Light Crossbow. "
            "The spell magically creates the ammunition needed for each attack. "
            "Each Arrow or Bolt created by the spell deals damage like a nonmagical piece of ammunition of its kind and disintegrates immediately after it hits or misses."
        ),
    }
    
    updates["Synaptic Static"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You cause psychic energy to erupt at a point within range. Each creature in a 20-foot-radius Sphere centered on that point makes an Intelligence saving throw, "
            "taking 8d6 Psychic damage on a failed save or half as much damage on a successful one.\n\n"
            "On a failed save, a target also has muddled thoughts for 1 minute. During that time, it subtracts 1d6 from all its attack rolls and ability checks, "
            "as well as any Constitution saving throws to maintain Concentration. The target makes an Intelligence saving throw at the end of each of its turns, ending the effect on itself on a success."
        ),
    }
    
    updates["Telekinesis"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You gain the ability to move or manipulate creatures or objects by thought. "
            "When you cast the spell and as a Magic action on your later turns before the spell ends, you can exert your will on one creature or object that you can see within range, "
            "causing the appropriate effect below. You can affect the same target round after round or choose a new one at any time. "
            "If you switch targets, the prior target is no longer affected by the spell.\n\n"
            "Creature. You can try to move a Huge or smaller creature. The target must succeed on a Strength saving throw, or you move it up to 30 feet in any direction within the spell's range. "
            "Until the end of your next turn, the creature has the Restrained condition, and if you lift it into the air, it is suspended there. "
            "It falls at the end of your next turn unless you use this option on it again and it fails the save.\n\n"
            "Object. You can try to move a Huge or smaller object. If the object isn't being worn or carried, you automatically move it up to 30 feet in any direction within the spell's range.\n\n"
            "If the object is worn or carried by a creature, that creature must succeed on a Strength saving throw, or you pull the object away and move it up to 30 feet in any direction within the spell's range.\n\n"
            "You can exert fine control on objects with your telekinetic grip, such as manipulating a simple tool, opening a door or a container, stowing or retrieving an item from an open container, or pouring the contents from a vial."
        ),
    }
    
    updates["Tree Stride"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You gain the ability to enter a tree and move from inside it to inside another tree of the same kind within 500 feet. "
            "Both trees must be living and at least the same size as you. You must use 5 feet of movement to enter a tree. "
            "You instantly know the location of all other trees of the same kind within 500 feet and, as part of the move used to enter the tree, "
            "can either pass into one of those trees or step out of the tree you're in. You appear in a spot of your choice within 5 feet of the destination tree, using another 5 feet of movement. "
            "If you have no movement left, you appear within 5 feet of the tree you entered.\n\n"
            "You can use this transportation ability only once on each of your turns. You must end each turn outside a tree."
        ),
    }
    
    updates["Wall of Force"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "An Invisible wall of force springs into existence at a point you choose within range. "
            "The wall appears in any orientation you choose, as a horizontal or vertical barrier or at an angle. It can be free floating or resting on a solid surface. "
            "You can form it into a hemispherical dome or a globe with a radius of up to 10 feet, or you can shape a flat surface made up of ten 10-foot-by-10-foot panels. "
            "Each panel must be contiguous with another panel. In any form, the wall is 1/4 inch thick and lasts for the duration. "
            "If the wall cuts through a creature's space when it appears, the creature is pushed to one side of the wall (you choose which side).\n\n"
            "Nothing can physically pass through the wall. It is immune to all damage and can't be dispelled by Dispel Magic. "
            "A Disintegrate spell destroys the wall instantly, however. The wall also extends into the Ethereal Plane and blocks ethereal travel through the wall."
        ),
    }
    
    updates["Wall of Stone"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A nonmagical wall of solid stone springs into existence at a point you choose within range. "
            "The wall is 6 inches thick and is composed of ten 10-foot-by-10-foot panels. Each panel must be contiguous with another panel. "
            "Alternatively, you can create 10-foot-by-20-foot panels that are only 3 inches thick.\n\n"
            "If the wall cuts through a creature's space when it appears, the creature is pushed to one side of the wall (you choose which side). "
            "If a creature would be surrounded on all sides by the wall (or the wall and another solid surface), that creature can make a Dexterity saving throw. "
            "On a success, it can use its Reaction to move up to its Speed so that it is no longer enclosed by the wall.\n\n"
            "The wall can have any shape you desire, though it can't occupy the same space as a creature or object. "
            "The wall doesn't need to be vertical or rest on a firm foundation. It must, however, merge with and be solidly supported by existing stone. "
            "Thus, you can use this spell to bridge a chasm or create a ramp.\n\n"
            "If you create a span greater than 20 feet in length, you must halve the size of each panel to create supports. You can crudely shape the wall to create battlements and the like.\n\n"
            "The wall is an object made of stone that can be damaged and thus breached. Each panel has AC 15 and 30 Hit Points per inch of thickness, "
            "and it has Immunity to Poison and Psychic damage. Reducing a panel to 0 Hit Points destroys it and might cause connected panels to collapse at the DM's discretion.\n\n"
            "If you maintain your Concentration on this spell for its full duration, the wall becomes permanent and can't be dispelled. Otherwise, the wall disappears when the spell ends."
        ),
    }
    
    updates["Yolande's Regal Presence"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You surround yourself with unearthly majesty in a 10-foot Emanation. "
            "Whenever the Emanation enters the space of a creature you can see and whenever a creature you can see enters the Emanation or ends its turn there, "
            "you can force that creature to make a Wisdom saving throw. On a failed save, the target takes 4d6 Psychic damage and has the Prone condition, and you can push it up to 10 feet away. "
            "On a successful save, the target takes half as much damage only. A creature makes this save only once per turn."
        ),
    }
    
    # XGtE and other Level 5 spells
    updates["Control Winds"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You take control of the air in a 100-foot cube that you can see within range. Choose one of the following effects when you cast the spell. "
            "The effect lasts for the spell's duration, unless you use your action on a later turn to switch to a different effect. "
            "You can also use your action to temporarily halt the effect or to restart one you've halted.\n\n"
            "Gusts. A wind picks up within the cube, continually blowing in a horizontal direction that you choose. You choose the intensity of the wind: calm, moderate, or strong. "
            "If the wind is moderate or strong, ranged weapon attacks that pass through it or that are made against targets within the cube have disadvantage on their attack rolls. "
            "If the wind is strong, any creature moving against the wind must spend 1 extra foot of movement for each foot moved.\n\n"
            "Downdraft. You cause a sustained blast of strong wind to blow downward from the top of the cube. "
            "Ranged weapon attacks that pass through the cube or that are made against targets within it have disadvantage on their attack rolls. "
            "A creature must make a Strength saving throw if it flies into the cube for the first time on a turn or starts its turn there flying. "
            "On a failed save, the creature is knocked prone.\n\n"
            "Updraft. You cause a sustained updraft within the cube, rising upward from the cube's bottom edge. "
            "Creatures that end a fall within the cube take only half damage from the fall. "
            "When a creature in the cube makes a vertical jump, the creature can jump up to 10 feet higher than normal."
        ),
    }
    
    updates["Danse Macabre"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "Threads of dark power leap from your fingers to pierce up to five Small or Medium corpses you can see within range. "
            "Each corpse immediately stands up and becomes undead. You decide whether it is a zombie or a skeleton (the statistics for zombies and skeletons are in the Monster Manual), "
            "and it gains a bonus to its attack and damage rolls equal to your spellcasting ability modifier. "
            "You can use a bonus action to mentally command the creatures you make with this spell, issuing the same command to all of them. "
            "To receive the command, a creature must be within 60 feet of you. "
            "You decide what action the creatures will take and where they will move during their next turn, "
            "or you can issue a general command, such as to guard a chamber or passageway against your foes. "
            "If you issue no commands, the creatures do nothing except defend themselves against hostile creatures. "
            "Once given an order, the creatures continue to follow it until their task is complete.\n\n"
            "The creatures are under your control until the spell ends, after which they become inanimate once more.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th level or higher, you animate up to two additional corpses for each slot level above 5th."
        ),
    }
    
    updates["Dawn"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "The light of dawn shines down on a location you specify within range. Until the spell ends, a 30-foot-radius, 40-foot-high cylinder of bright light glimmers there. "
            "This light is sunlight. When the cylinder appears, each creature in it must make a Constitution saving throw, taking 4d10 radiant damage on a failed save, "
            "or half as much damage on a successful one. A creature must also make this saving throw whenever it ends its turn in the cylinder. "
            "If you're within 60 feet of the cylinder, you can move it up to 60 feet as a bonus action on your turn."
        ),
    }
    
    updates["Enervation"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "A tendril of inky darkness reaches out from you, touching a creature you can see within range to drain life from it. "
            "The target must make a Dexterity saving throw. On a successful save, the target takes 2d8 necrotic damage, and the spell ends. "
            "On a failed save, the target takes 4d8 necrotic damage, and until the spell ends, you can use your action on each of your turns to automatically deal 4d8 necrotic damage to the target. "
            "The spell ends if you use your action to do anything else, if the target is ever outside the spell's range, or if the target has total cover from you. "
            "Whenever the spell deals damage to a target, you regain hit points equal to half the amount of necrotic damage the target takes.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th level or higher, the damage increases by 1d8 for each slot level above 5th."
        ),
    }
    
    updates["Far Step"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You teleport up to 60 feet to an unoccupied space you can see. On each of your turns before the spell ends, you can use a bonus action to teleport in this way again."
        ),
    }
    
    updates["Holy Weapon"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You imbue a weapon you touch with holy power. Until the spell ends, the weapon emits bright light in a 30-foot radius and dim light for an additional 30 feet. "
            "In addition, weapon attacks made with it deal an extra 2d8 radiant damage on a hit. If the weapon isn't already a magic weapon, it becomes one for the duration. "
            "As a bonus action on your turn, you can dismiss this spell and cause the weapon to emit a burst of radiance. "
            "Each creature of your choice that you can see within 30 feet of the weapon must make a Constitution saving throw. "
            "On a failed save, a creature takes 4d8 radiant damage, and it is blinded for 1 minute. On a successful save, a creature takes half as much damage and isn't blinded. "
            "At the end of each of its turns, a blinded creature can make a Constitution saving throw, ending the effect on itself on a success."
        ),
    }
    
    updates["Immolation"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "Flames wreathe one creature you can see within range. The target must make a Dexterity saving throw. "
            "It takes 8d6 fire damage on a failed save, or half as much damage on a successful one. On a failed save, the target also burns for the spell's duration. "
            "The burning target sheds bright light in a 30-foot radius and dim light for an additional 30 feet. "
            "At the end of each of its turns, the target repeats the saving throw. It takes 4d6 fire damage on a failed save, and the spell ends on a successful one. "
            "These magical flames can't be extinguished by nonmagical means.\n\n"
            "If damage from this spell kills a target, the target is turned to ash."
        ),
    }
    
    updates["Infernal Calling"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "Uttering a dark incantation, you summon a devil from the Nine Hells. You choose the devil's type, which must be one of challenge rating 6 or lower, "
            "such as a barbed devil or a bearded devil. The devil appears in an unoccupied space that you can see within range. "
            "The devil disappears when it drops to 0 hit points or when the spell ends.\n\n"
            "The devil is unfriendly toward you and your companions. Roll initiative for the devil, which has its own turns. "
            "It is under the Dungeon Master's control and acts according to its nature on each of its turns, "
            "which might result in its attacking you if it thinks it can prevail, or trying to tempt you to undertake an evil act in exchange for limited service. "
            "The DM has the creature's statistics.\n\n"
            "On each of your turns, you can try to issue a verbal command to the devil (no action required by you). "
            "It obeys the command if the likely outcome is in accordance with its desires, especially if the result would draw you toward evil. "
            "Otherwise, you must make a Charisma (Deception, Intimidation, or Persuasion) check contested by its Wisdom (Insight) check. "
            "You make the check with advantage if you say the devil's true name. If your check fails, the devil becomes immune to your verbal commands for the duration of the spell, "
            "though it can still carry out your commands if it chooses. If your check succeeds, the devil carries out your command—such as \"attack my enemies,\" \"explore the room ahead,\" "
            "or \"bear this message to the queen\"—until it completes the activity, at which point it returns to you to report having done so.\n\n"
            "If your concentration ends before the spell reaches its full duration, the devil doesn't disappear if it has become immune to your verbal commands. "
            "Instead, it acts in whatever manner it chooses for 3d6 minutes, and then it disappears.\n\n"
            "If you possess an individual devil's talisman, you can summon that devil if it is of the appropriate challenge rating plus 1, "
            "and it obeys all your commands, with no Charisma checks required.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th level or higher, the challenge rating increases by 1 for each slot level above 5th."
        ),
    }
    
    updates["Maelstrom"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "A mass of 5-foot-deep water appears and swirls in a 30-foot radius centered on a point you can see within range. "
            "The point must be on ground or in a body of water. Until the spell ends, that area is difficult terrain, "
            "and any creature that starts its turn there must succeed on a Strength saving throw or take 6d6 bludgeoning damage and be pulled 10 feet toward the center."
        ),
    }
    
    updates["Negative Energy Flood"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You send ribbons of negative energy at one creature you can see within range. Unless the target is undead, "
            "it must make a Constitution saving throw, taking 5d12 necrotic damage on a failed save, or half as much damage on a successful one. "
            "A target killed by this damage rises up as a zombie at the start of your next turn. The zombie pursues whatever creature it can see that is closest to it. "
            "Statistics for the zombie are in the Monster Manual. If you target an undead with this spell, the target doesn't make a saving throw. "
            "Instead, roll 5d12. The target gains half the total as temporary hit points."
        ),
    }
    
    updates["Skill Empowerment"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "Your magic deepens a creature's understanding of its own talent. You touch one willing creature and give it expertise in one skill of your choice; "
            "until the spell ends, the creature doubles its proficiency bonus for ability checks it makes that use the chosen skill.\n\n"
            "You must choose a skill in which the target is proficient and that isn't already benefiting from an effect, such as Expertise, that doubles its proficiency bonus."
        ),
    }
    
    updates["Summon Draconic Spirit"] = {
        "source": "Fizban's Treasury of Dragons",
        "description": (
            "You call forth a draconic spirit. It manifests in an unoccupied space that you can see within range. "
            "This corporeal form uses the Draconic Spirit stat block. When you cast this spell, choose a family of dragon: chromatic, gem, or metallic. "
            "The creature resembles a dragon of the chosen family, which determines certain traits in its stat block. "
            "The creature disappears when it drops to 0 hit points or when the spell ends.\n\n"
            "The creature is an ally to you and your companions. In combat, the creature shares your initiative count, but it takes its turn immediately after yours. "
            "It obeys your verbal commands (no action required by you). If you don't issue any, it takes the Dodge action and uses its move to avoid danger.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th level or higher, use the higher level wherever the spell's level appears in the stat block."
        ),
    }
    
    updates["Temporal Shunt"] = {
        "source": "Explorer's Guide to Wildemount",
        "description": (
            "You target the triggering creature, which must succeed on a Wisdom saving throw or vanish, being thrown to another point in time and causing the attack to miss or the spell to be wasted. "
            "At the start of its next turn, the target reappears where it was or in the closest unoccupied space. "
            "The target doesn't remember you casting the spell or being affected by it.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th level or higher, you can target one additional creature for each slot level above 5th. "
            "All targets must be within 30 feet of each other."
        ),
    }
    
    updates["Transmute Rock"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You choose an area of stone or mud that you can see that fits within a 40-foot cube and that is within range, and choose one of the following effects.\n\n"
            "Transmute Rock to Mud. Nonmagical rock of any sort in the area becomes an equal volume of thick and flowing mud that remains for the spell's duration.\n"
            "If you cast the spell on an area of ground, it becomes muddy enough that creatures can sink into it. "
            "Each foot that a creature moves through the mud costs 4 feet of movement, and any creature on the ground when you cast the spell must make a Strength saving throw. "
            "A creature must also make this save the first time it enters the area on a turn or ends its turn there. "
            "On a failed save, a creature sinks into the mud and is restrained, though it can use an action to end the restrained condition on itself by pulling itself free of the mud.\n"
            "If you cast the spell on a ceiling, the mud falls. Any creature under the mud when it falls must make a Dexterity saving throw. "
            "A creature takes 4d8 bludgeoning damage on a failed save, or half as much damage on a successful one.\n\n"
            "Transmute Mud to Rock. Nonmagical mud or quicksand in the area no more than 10 feet deep transforms into soft stone for the spell's duration. "
            "Any creature in the mud when it transforms must make a Dexterity saving throw. On a failed save, a creature becomes restrained by the rock. "
            "The restrained creature can use an action to try to break free by succeeding on a Strength check (DC 20) or by dealing 25 damage to the rock around it. "
            "On a successful save, a creature is shunted safely to the surface to an unoccupied space."
        ),
    }
    
    updates["Wall of Light"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "A shimmering wall of bright light appears at a point you choose within range. "
            "The wall appears in any orientation you choose: horizontally, vertically, or diagonally. It can be free floating, or it can rest on a solid surface. "
            "The wall can be up to 60 feet long, 10 feet high, and 5 feet thick. The wall blocks line of sight, but creatures and objects can pass through it. "
            "It emits bright light out to 120 feet and dim light for an additional 120 feet.\n\n"
            "When the wall appears, each creature in its area must make a Constitution saving throw. On a failed save, a creature takes 4d8 radiant damage, and it is blinded for 1 minute. "
            "On a successful save, it takes half as much damage and isn't blinded. A blinded creature can make a Constitution saving throw at the end of each of its turns, ending the effect on itself on a success.\n\n"
            "A creature that ends its turn in the wall's area takes 4d8 radiant damage.\n\n"
            "Until the spell ends, you can use an action to launch a beam of radiance from the wall at one creature you can see within 60 feet of it. "
            "Make a ranged spell attack. On a hit, the target takes 4d8 radiant damage. Whether you hit or miss, reduce the length of the wall by 10 feet. "
            "If the wall's length drops to 0 feet, the spell ends.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th level or higher, the damage increases by 1d8 for each slot level above 5th."
        ),
    }
    
    updates["Wrath of Nature"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You call out to the spirits of nature to rouse them against your enemies. Choose a point you can see within range. "
            "The spirits cause trees, rocks, and grasses in a 60-foot cube centered on that point to become animated until the spell ends.\n\n"
            "Grasses and Undergrowth. Any area of ground in the cube that is covered by grass or undergrowth is difficult terrain for your enemies.\n\n"
            "Trees. At the start of each of your turns, each of your enemies within 10 feet of any tree in the cube must succeed on a Dexterity saving throw "
            "or take 4d6 slashing damage from whipping branches.\n\n"
            "Roots and Vines. At the end of each of your turns, one creature of your choice that is on the ground in the cube must succeed on a Strength saving throw "
            "or become restrained until the spell ends. A restrained creature can use an action to make a Strength (Athletics) check against your spell save DC, ending the effect on itself on a success.\n\n"
            "Rocks. As a bonus action on your turn, you can cause a loose rock in the cube to launch at a creature you can see in the cube. "
            "Make a ranged spell attack against the target. On a hit, the target takes 3d8 nonmagical bludgeoning damage, and it must succeed on a Strength saving throw or fall prone."
        ),
    }
    
    # ============================================
    # LEVEL 6 SPELLS
    # ============================================
    
    updates["Arcane Gate"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create linked teleportation portals. Choose two Large, unoccupied spaces on surfaces that you can see, "
            "one space within 10 feet of yourself and one space within 500 feet of yourself. A circular portal opens in each of those spaces and remains for the duration.\n\n"
            "The portals are two-dimensional glowing rings filled with mist that blocks sight. They hover inches from the ground and are perpendicular to it.\n\n"
            "A portal is open on only one side (you choose which). Anything entering the open side of a portal exits from the open side of the other portal as if the two were adjacent to each other. "
            "As a Bonus Action, you can change the facing of the open sides."
        ),
    }
    
    updates["Blade Barrier"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a wall of whirling blades made of magical energy. The wall appears within range and lasts for the duration. "
            "You make a straight wall up to 100 feet long, 20 feet high, and 5 feet thick, or a ringed wall up to 60 feet in diameter, 20 feet high, and 5 feet thick. "
            "The wall provides Three-Quarters Cover, and its space is Difficult Terrain.\n\n"
            "Any creature in the wall's space makes a Dexterity saving throw, taking 6d10 Force damage on a failed save or half as much damage on a successful one. "
            "A creature also makes that save if it enters the wall's space or ends it turn there. A creature makes that save only once per turn."
        ),
    }
    
    updates["Chain Lightning"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You launch a lightning bolt toward a target you can see within range. Three bolts then leap from that target to as many as three other targets of your choice, "
            "each of which must be within 30 feet of the first target. A target can be a creature or an object and can be targeted by only one of the bolts.\n\n"
            "Each target makes a Dexterity saving throw, taking 10d8 Lightning damage on a failed save or half as much damage on a successful one.\n\n"
            "Using a Higher-Level Spell Slot. One additional bolt leaps from the first target to another target for each spell slot level above 6."
        ),
    }
    
    updates["Circle of Death"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Negative energy ripples out in a 60-foot-radius Sphere from a point you choose within range. "
            "Each creature in that area makes a Constitution saving throw, taking 8d8 Necrotic damage on a failed save or half as much damage on a successful one.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 2d8 for each spell slot level above 6."
        ),
    }
    
    updates["Conjure Fey"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You conjure a Medium spirit from the Feywild in an unoccupied space you can see within range. The spirit lasts for the duration, "
            "and it looks like a Fey creature of your choice. When the spirit appears, you can make one melee spell attack against a creature within 5 feet of it. "
            "On a hit, the target takes Psychic damage equal to 3d12 plus your spellcasting ability modifier.\n\n"
            "As a Bonus Action on your later turns, you can teleport the spirit to an unoccupied space you can see within 30 feet of the space it left "
            "and make the attack against a creature within 5 feet of it.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 2d12 for each spell slot level above 6."
        ),
    }
    
    updates["Contingency"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Choose a spell of level 5 or lower that you can cast, that has a casting time of an action, and that can target you. "
            "You cast that spell—called the contingent spell—as part of casting Contingency, expending spell slots for both, but the contingent spell doesn't come into effect. "
            "Instead, it takes effect when a certain trigger occurs. You describe that trigger when you cast the two spells. "
            "For example, a Contingency cast with Water Breathing might stipulate that Water Breathing comes into effect when you are engulfed in water or a similar liquid.\n\n"
            "The contingent spell takes effect immediately after the trigger occurs for the first time, whether or not you want it to, and then Contingency ends.\n\n"
            "The contingent spell takes effect only on you, even if it can normally target others. You can use only one Contingency spell at a time. "
            "If you cast this spell again, the effect of another Contingency spell on you ends. Also, Contingency ends on you if its material component is ever not on your person."
        ),
    }
    
    updates["Create Undead"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You can cast this spell only at night. Choose up to three corpses of Medium or Small Humanoids within range. "
            "Each one becomes a Ghoul under your control (see the Monster Manual for its stat block).\n\n"
            "As a Bonus Action on each of your turns, you can mentally command any creature you animated with this spell if the creature is within 120 feet of you "
            "(if you control multiple creatures, you can command any or all of them at the same time, issuing the same command to each one). "
            "You decide what action the creature will take and where it will move on its next turn, "
            "or you can issue a general command, such as to guard a particular place. If you issue no commands, the creature takes the Dodge action and moves only to avoid harm. "
            "Once given an order, the creature continues to follow the order until its task is complete.\n\n"
            "The creature is under your control for 24 hours, after which it stops obeying any command you've given it. "
            "To maintain control of the creature for another 24 hours, you must cast this spell on the creature before the current 24-hour period ends. "
            "This use of the spell reasserts your control over up to three creatures you have animated with this spell rather than animating new ones.\n\n"
            "Using a Higher-Level Spell Slot. If you use a level 7 spell slot, you can animate or reassert control over four Ghouls. "
            "If you use a level 8 spell slot, you can animate or reassert control over five Ghouls or two Ghasts or Wights. "
            "If you use a level 9 spell slot, you can animate or reassert control over six Ghouls, three Ghasts or Wights, or two Mummies. "
            "See the Monster Manual for these stat blocks."
        ),
    }
    
    updates["Disintegrate"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You launch a green ray at a target you can see within range. The target can be a creature, a nonmagical object, or a creation of magical force, such as the wall created by Wall of Force.\n\n"
            "A creature targeted by this spell makes a Dexterity saving throw. On a failed save, the target takes 10d6 + 40 Force damage. "
            "If this damage reduces it to 0 Hit Points, it and everything nonmagical it is wearing and carrying are disintegrated into gray dust. "
            "The target can be revived only by a True Resurrection or Wish spell.\n\n"
            "This spell automatically disintegrates a Large or smaller nonmagical object or a creation of magical force. "
            "If such a target is Huge or larger, this spell disintegrates a 10-foot-Cube portion of it.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 3d6 for each spell slot level above 6."
        ),
    }
    
    updates["Drawmij's Instant Summons"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You touch the object you inscribed during the casting and a creature of your choice within 30 feet of you. "
            "At any time afterward, that creature can take a Magic action to speak the item's name, causing the item to appear in the creature's hand from the unknown location, "
            "whereupon the spell ends.\n\n"
            "If another creature is holding or carrying the item, speaking the item's name doesn't transport it, but instead you learn who the creature possessing the item is "
            "and where that creature is currently located."
        ),
    }
    
    updates["Eyebite"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "For the duration, your eyes become an inky void. One creature of your choice within 60 feet of you that you can see must succeed on a Wisdom saving throw "
            "or be affected by one of the following effects of your choice for the duration. On each of your turns until the spell ends, "
            "you can take a Magic action to target another creature but can't target a creature again if it has succeeded on a save against this casting of the spell.\n\n"
            "Asleep. The target has the Unconscious condition. It wakes up if it takes any damage or if another creature takes an action to shake it awake.\n\n"
            "Panicked. The target has the Frightened condition. On each of its turns, the Frightened target must take the Dash action and move away from you by the safest route available. "
            "If the target moves to a space at least 60 feet away from you where it can't see you, this effect ends.\n\n"
            "Sickened. The target has the Poisoned condition."
        ),
    }
    
    updates["Find the Path"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You magically sense the most direct physical route to a location you name. You must be familiar with the location, "
            "and the spell fails if you name a destination on another plane of existence, a destination that moves (such as a mobile fortress), "
            "or an unspecific destination (such as a green dragon's lair).\n\n"
            "For the duration, as long as you are on the same plane of existence as the destination, you know how far it is and in what direction it lies. "
            "Whenever you face a choice of paths along the way there, you know which path is the most direct."
        ),
    }
    
    updates["Flesh to Stone"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You attempt to turn one creature that you can see within range into stone. The target makes a Constitution saving throw. "
            "On a failed save, the target has the Restrained condition for the duration. On a successful save, the target's Speed is 0 until the start of your next turn.\n\n"
            "If the target is Restrained for the full duration, it is turned to stone and has the Petrified condition for the duration. "
            "Petrification can be ended by any effect that ends the Petrified condition.\n\n"
            "At the end of each of its turns, a Restrained target repeats the save. If it has three successes, the spell ends on the target. "
            "If it has three failures, it immediately becomes Petrified. The successes and failures don't need to be consecutive; keep track of both until the target reaches three of a kind."
        ),
    }
    
    updates["Forbiddance"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a ward against magical travel that protects up to 40,000 square feet of floor space to a height of 30 feet above the floor. "
            "For the duration, creatures can't teleport into the area or use portals, such as those created by the Gate spell, to enter the area. "
            "The spell proofs the area against planar travel, and therefore prevents creatures from accessing the area by way of the Astral Plane, the Ethereal Plane, the Feywild, the Shadowfell, or the Plane Shift spell.\n\n"
            "In addition, the spell damages types of creatures that you choose when you cast it. Choose one or more of the following: Aberrations, Celestials, Elementals, Fey, Fiends, and Undead. "
            "When a creature of a chosen type enters the spell's area for the first time on a turn or ends its turn there, the creature takes 5d10 Radiant or Necrotic damage (your choice when you cast this spell).\n\n"
            "You can designate a password when you cast the spell. A creature that speaks the password as it enters the area takes no damage from the spell.\n\n"
            "If you cast this spell every day for 30 days in the same location, the spell lasts until it is dispelled, and the material components are consumed on the last casting."
        ),
    }
    
    updates["Globe of Invulnerability"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "An immobile, shimmering barrier appears in a 10-foot Emanation around you and remains for the duration.\n\n"
            "Any spell of level 5 or lower cast from outside the barrier can't affect anything within it. "
            "Such a spell can target creatures and objects within the barrier, but the spell has no effect on them. "
            "Similarly, the area within the barrier is excluded from areas of effect created by such spells.\n\n"
            "Using a Higher-Level Spell Slot. The barrier blocks spells of the spell slot's level or lower."
        ),
    }
    
    updates["Guards and Wards"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a ward that protects up to 2,500 square feet of floor space (an area 50 feet square, or one hundred 5-foot squares or twenty-five 10-foot squares). "
            "The warded area can be up to 20 feet tall, and you shape it as you desire. You can ward several stories of a stronghold by dividing the area among them, "
            "as long as you can walk into each contiguous area while you're casting the spell.\n\n"
            "When you cast this spell, you can specify individuals who aren't affected by the spell's effects. "
            "You can also specify a password that, when spoken aloud within 5 feet of the warded area, makes the speaker immune to its effects.\n\n"
            "The spell creates the effects below within the warded area. Dispel Magic has no effect on Guards and Wards itself, "
            "but each of the following effects can be dispelled. If all four effects are dispelled, Guards and Wards ends. If you cast the spell every day for 365 days on an area, the spell thereafter lasts until all its effects are dispelled.\n\n"
            "Corridors. Fog fills all the warded corridors, making them Heavily Obscured. In addition, at each intersection or branching passage offering a choice of direction, there is a 50 percent chance that a creature other than you believes it is going in the opposite direction from the one it chooses.\n\n"
            "Doors. All doors in the warded area are magically locked, as if sealed by the Arcane Lock spell. In addition, you can cover up to ten doors with an illusion to make them appear as plain sections of wall.\n\n"
            "Stairs. Webs fill all stairs in the warded area from top to bottom, as in the Web spell. These strands regrow in 10 minutes if they are destroyed while Guards and Wards lasts.\n\n"
            "Other Spell Effect. Place one of the following magical effects within the warded area:\n"
            "- Dancing Lights in four corridors, with a simple program that the lights repeat as long as Guards and Wards lasts\n"
            "- Magic Mouth in two locations\n"
            "- Stinking Cloud in two locations; the vapors appear in the places you designate, and they return within 10 minutes if dispersed while Guards and Wards lasts\n"
            "- Gust of Wind in one corridor or room\n"
            "- Suggestion in one location; any creature that enters that 5-foot-square area receives the Suggestion mentally"
        ),
    }
    
    updates["Harm"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You unleash virulent magic on a creature you can see within range. The target makes a Constitution saving throw. "
            "On a failed save, it takes 14d6 Necrotic damage, and its Hit Point maximum is reduced by an amount equal to the Necrotic damage it took. "
            "On a successful save, it takes half as much damage only. This spell can't reduce a target's Hit Point maximum below 1."
        ),
    }
    
    updates["Heal"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Choose a creature that you can see within range. Positive energy washes through the target, restoring 70 Hit Points. "
            "This spell also ends the Blinded, Deafened, and Poisoned conditions on the target.\n\n"
            "Using a Higher-Level Spell Slot. The healing increases by 10 for each spell slot level above 6."
        ),
    }
    
    updates["Heroes' Feast"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You conjure a magnificent feast that takes 1 hour to consume and disappears at the end of that time. The feast's effects don't set in until this hour is over. "
            "Up to twelve creatures can partake of the feast, and any creature that partakes gains several benefits, which last for 24 hours.\n\n"
            "A creature that partakes is cured of all Poisons and has Immunity to Poison. "
            "It also makes Wisdom saving throws with Advantage, has Resistance to one damage type of your choice when you cast this spell, and increases its Hit Point maximum by 2d10 and gains the same number of Hit Points."
        ),
    }
    
    updates["Mass Suggestion"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You suggest a course of activity—described in no more than 25 words—to twelve or fewer creatures you can see within range that can hear and understand you. "
            "The suggestion must sound achievable and not involve anything that would obviously deal damage to any of the targets or their allies. "
            "For example, you could say, \"Walk to the village down that road, and help the villagers there harvest crops until sunset.\" Or you could say, "
            "\"Now is not the time for violence. Drop your weapons, and dance! Stop in an hour.\"\n\n"
            "Each target must succeed on a Wisdom saving throw or have the Charmed condition for the duration or until you or your allies deal damage to the target. "
            "Each Charmed target pursues the suggestion to the best of its ability. The suggested activity can continue for the entire duration, but if the suggested activity can be completed in a shorter time, the spell ends for a target upon completing it."
        ),
    }
    
    updates["Move Earth"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Choose an area of terrain no larger than 40 feet on a side within range. You can reshape dirt, sand, or clay in the area in any manner you choose for the duration. "
            "You can raise or lower the area's elevation, create or fill in a trench, erect or flatten a wall, or form a pillar. The extent of any such changes can't exceed half the area's largest dimension. "
            "For example, if you affect a 40-foot square, you can create a pillar up to 20 feet high, raise or lower the square's elevation by up to 20 feet, dig a trench up to 20 feet deep, and so on. "
            "It takes 10 minutes for these changes to complete. Because the terrain's transformation occurs slowly, creatures in the area can't usually be trapped or injured by the ground's movement.\n\n"
            "At the end of every 10 minutes you spend Concentrating on the spell, you can choose a new area of terrain to affect within range.\n\n"
            "This spell can't manipulate natural stone or stone construction. Rocks and structures shift to accommodate the new terrain. "
            "If the way you shape the terrain would make a structure unstable, it might collapse.\n\n"
            "Similarly, this spell doesn't directly affect plant growth. The moved earth carries any plants along with it."
        ),
    }
    
    updates["Otiluke's Freezing Sphere"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A frigid globe streaks from you to a point of your choice within range, where it explodes in a 60-foot-radius Sphere. "
            "Each creature in that area makes a Constitution saving throw, taking 10d6 Cold damage on a failed save or half as much damage on a successful one.\n\n"
            "If the globe strikes a body of water, it freezes the water to a depth of 6 inches over an area 30 feet square. This ice lasts for 1 minute. "
            "Creatures that were swimming on the surface of frozen water are trapped in the ice and have the Restrained condition. "
            "A trapped creature can take an action to make a Strength (Athletics) check against your spell save DC to break free.\n\n"
            "You can refrain from firing the globe after completing the spell's casting. If you do so, a globe about the size of a sling bullet, cool to the touch, appears in your hand. "
            "At any time, you or a creature you give the globe to can throw the globe (to a range of 40 feet) or hurl it with a sling (to the sling's normal range). "
            "It shatters on impact, with the same effect as if you had cast the spell. You can also set the globe down without shattering it. "
            "After 1 minute, if the globe hasn't already shattered, it explodes.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d6 for each spell slot level above 6."
        ),
    }
    
    updates["Otto's Irresistible Dance"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "One creature that you can see within range must make a Wisdom saving throw. On a successful save, the target dances comically until the end of its next turn, "
            "during which it must spend all its movement to dance in place and has Disadvantage on Dexterity saving throws and attack rolls, and other creatures have Advantage on attack rolls against it.\n\n"
            "On a failed save, the target has the Charmed condition for the duration. While Charmed, the target dances comically, must use all its movement to dance in place, "
            "and has Disadvantage on Dexterity saving throws and attack rolls, and other creatures have Advantage on attack rolls against it. "
            "The dancing target can take actions and Reactions normally, but it must repeat the save at the end of each of its turns, ending the spell on itself on a success."
        ),
    }
    
    updates["Planar Ally"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You beseech an otherworldly entity for aid. The being must be known to you: a god, a demon prince, or some other being of cosmic power. "
            "That entity sends a Celestial, an Elemental, or a Fiend loyal to it to aid you, making the creature appear in an unoccupied space within range. "
            "If you know a specific creature's name, you can speak that name when you cast this spell to request that creature, though you might get a different creature anyway (DM's choice).\n\n"
            "When the creature appears, it is under no compulsion to behave in any particular way. "
            "You can ask it to perform a service in exchange for payment, but it isn't obliged to do so. "
            "The requested task could range from simple (fly us across the chasm, or help us fight a battle) to complex (spy on our enemies, or protect us during our foray into the dungeon). "
            "You must be able to communicate with the creature to bargain for its services.\n\n"
            "Payment can take a variety of forms. A Celestial might require a sizable donation of gold or magic items to an allied temple, "
            "while a Fiend might demand a living sacrifice or a gift of treasure. Some creatures might exchange their service for a quest undertaken by you.\n\n"
            "A task that can be measured in minutes requires a payment worth 100 GP per minute. A task measured in hours requires 1,000 GP per hour. "
            "And a task measured in days (up to 10 days) requires 10,000 GP per day. "
            "The DM can adjust these payments based on the circumstances under which you cast the spell. If the task is aligned with the creature's ethos, payment might be halved or waived. "
            "Nonhazardous tasks typically require only half the suggested payment, while especially dangerous tasks might require a greater gift. Creatures rarely accept tasks that seem suicidal.\n\n"
            "After the creature completes the task, or when the agreed-upon duration of service expires, the creature returns to its home plane after reporting back to you if possible. "
            "If you're unable to agree on a price for the creature's service, the creature immediately returns to its home plane.\n\n"
            "A creature enlisted to join your group counts as a member of it, receiving a full share of experience points awarded."
        ),
    }
    
    updates["Primordial Ward"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You have resistance to acid, cold, fire, lightning, and thunder damage for the spell's duration.\n\n"
            "When you take damage of one of those types, you can use your reaction to gain immunity to that type of damage, including against the triggering damage. "
            "If you do so, the resistances end, and you have the immunity until the end of your next turn, at which time the spell ends."
        ),
    }
    
    updates["Programmed Illusion"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create an illusion of an object, a creature, or some other visible phenomenon within range that activates when a specific trigger occurs. "
            "The illusion is imperceptible until then. It must be no larger than a 30-foot Cube, and you decide when you cast the spell how the illusion behaves and what sounds it makes. "
            "This scripted performance can last up to 5 minutes.\n\n"
            "When the trigger you specify occurs, the illusion springs into existence and performs in the manner you described. "
            "Once the illusion finishes performing, it disappears and remains dormant for 10 minutes. After this time, the illusion can be activated again.\n\n"
            "The trigger can be as general or as detailed as you like, though it must be based on visual or audible conditions that occur within 30 feet of the area. "
            "For example, you could create an illusion of yourself to appear and warn off others who attempt to open a trapped door.\n\n"
            "Physical interaction with the image reveals it to be an illusion, since things can pass through it. "
            "A creature that takes a Study action to examine the image can determine that it is an illusion with a successful Intelligence (Investigation) check against your spell save DC. "
            "If a creature discerns the illusion for what it is, the creature can see through the image, and any noise it makes sounds hollow to the creature."
        ),
    }
    
    updates["Sunbeam"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You launch a sunbeam in a 5-foot-wide, 60-foot-long Line. Each creature in the Line makes a Constitution saving throw. "
            "On a failed save, a creature takes 6d8 Radiant damage and has the Blinded condition until the start of your next turn. On a successful save, it takes half as much damage only.\n\n"
            "Until the spell ends, you can take a Magic action to create a new Line of radiance.\n\n"
            "For the duration, a mote of brilliant radiance shines above you. It sheds Bright Light in a 30-foot radius and Dim Light for an additional 30 feet. This light is sunlight."
        ),
    }
    
    updates["Tasha's Otherworldly Guise"] = {
        "source": "Tasha's Cauldron of Everything",
        "description": (
            "Uttering an incantation, you draw on the magic of the Lower Planes or Upper Planes (your choice) to transform yourself. You gain the following benefits until the spell ends:\n\n"
            "• You are immune to fire and poison damage (Lower Planes) or radiant and necrotic damage (Upper Planes).\n"
            "• You are immune to the poisoned condition (Lower Planes) or the charmed condition (Upper Planes).\n"
            "• Spectral wings appear on your back, giving you a flying speed of 40 feet.\n"
            "• You have a +2 bonus to AC.\n"
            "• All your weapon attacks are magical, and when you make a weapon attack, you can use your spellcasting ability modifier, instead of Strength or Dexterity, for the attack and damage rolls.\n"
            "• You can attack twice, instead of once, when you take the Attack action on your turn. You ignore this benefit if you already have a feature, like Extra Attack, that lets you attack more than once when you take the Attack action on your turn."
        ),
    }
    
    updates["Transport via Plants"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "This spell creates a magical link between a Large or larger inanimate plant within range and another plant, at any distance, on the same plane of existence. "
            "You must have seen or touched the destination plant at least once before. For the duration, any creature can step into the target plant and exit from the destination plant by using 5 feet of movement."
        ),
    }
    
    updates["True Seeing"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "For the duration, the willing creature you touch has Truesight with a range of 120 feet."
        ),
    }
    
    updates["Word of Recall"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You and up to five willing creatures within 5 feet of you instantly teleport to a previously designated sanctuary. "
            "You and any creatures that teleport with you appear in the nearest unoccupied space to the spot you designated when you prepared your sanctuary (see below). "
            "If you cast this spell without first preparing a sanctuary, the spell has no effect.\n\n"
            "You must designate a location, such as a temple or your home, as a sanctuary by casting this spell there."
        ),
    }
    
    # Additional Level 6 Spells from XGtE
    updates["Bones of the Earth"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You cause up to six pillars of stone to burst from places on the ground that you can see within range. "
            "Each pillar is a cylinder that has a diameter of 5 feet and a height of up to 30 feet. The ground where a pillar appears must be wide enough for its diameter, "
            "and you can target the ground under a creature if that creature is Medium or smaller. "
            "Each pillar has AC 5 and 30 hit points. When reduced to 0 hit points, a pillar crumbles into rubble, which creates an area of difficult terrain with a 10-foot radius that lasts until the rubble is cleared. "
            "Each 5-foot-diameter portion of the area requires at least 1 minute to clear by hand.\n\n"
            "If a pillar is created under a creature, that creature must succeed on a Dexterity saving throw or be lifted by the pillar. "
            "A creature can choose to fail the save. If a pillar is prevented from reaching its full height because of a ceiling or other obstacle, "
            "a creature on the pillar takes 6d6 bludgeoning damage and is restrained, pinched between the pillar and the obstacle. "
            "The restrained creature can use an action to make a Strength or Dexterity check (the creature's choice) against the spell's save DC. "
            "On a success, the creature is no longer restrained and must either move off the pillar or fall off it.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 7th level or higher, you can create two additional pillars for each slot level above 6th."
        ),
    }
    
    updates["Create Homunculus"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "While speaking an intricate incantation, you cut yourself with a jewel-encrusted dagger, taking 2d4 piercing damage that can't be reduced in any way. "
            "You then drip your blood on the spell's other components and touch them, transforming them into a homunculus.\n\n"
            "The homunculus is friendly to you and your companions, and it obeys your commands. See this creature's game statistics in the homunculus entry in the Monster Manual. "
            "If you already have a homunculus from this spell, the first one immediately dies.\n\n"
            "You can have only one homunculus at a time. While your homunculus is within 100 feet of you, you can communicate with it telepathically. "
            "Additionally, as an action, you can see through the homunculus's eyes and hear what it hears until the start of your next turn, gaining the benefits of any special senses that the homunculus has. "
            "During this time, you are deaf and blind with regard to your own senses.\n\n"
            "You can dismiss your homunculus, causing it to die, as a bonus action."
        ),
    }
    
    updates["Mental Prison"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You attempt to bind a creature within an illusory cell that only it perceives. One creature you can see within range must make an Intelligence saving throw. "
            "The target succeeds automatically if it is immune to being charmed. On a successful save, the target takes 5d10 psychic damage, and the spell ends. "
            "On a failed save, the target takes 5d10 psychic damage, and you make the area immediately around the target's space appear dangerous to it in some way. "
            "You might cause the target to perceive itself as being surrounded by fire, floating razors, or hideous maws filled with dripping teeth. "
            "Whatever form the illusion takes, the target can't see or hear anything beyond it and is restrained for the spell's duration. "
            "If the target is moved out of the illusion, makes a melee attack through it, or reaches any part of its body through it, "
            "the target takes 10d10 psychic damage, and the spell ends."
        ),
    }
    
    updates["Scatter"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "The air quivers around up to five creatures of your choice that you can see within range. "
            "An unwilling creature must succeed on a Wisdom saving throw to resist this spell. "
            "You teleport each affected target to an unoccupied space that you can see within 120 feet of you. "
            "That space must be on the ground or on a floor."
        ),
    }
    
    updates["Soul Cage"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "This spell snatches the soul of a humanoid as it dies and traps it inside the tiny cage you use for the material component. "
            "A stolen soul remains inside the cage until the spell ends or until you destroy the cage, which ends the spell. "
            "While you have a soul inside the cage, you can exploit it in any of the ways described below. "
            "You can use a trapped soul up to six times. Once you exploit a soul for the sixth time, it is released, and the spell ends. "
            "While a soul is trapped, the dead humanoid it came from can't be revived.\n\n"
            "Steal Life. You can use a bonus action to drain vigor from the soul and regain 2d8 hit points.\n\n"
            "Query Soul. You ask the soul a question (no action required) and receive a brief telepathic answer, which you can understand regardless of the language used. "
            "The soul knows only what it knew in life, but it must answer you truthfully and to the best of its ability. "
            "The answer is no more than a sentence or two and might be cryptic.\n\n"
            "Borrow Experience. You can use a bonus action to bolster yourself with the soul's life experience, making your next attack roll, ability check, or saving throw with advantage. "
            "If you don't use this benefit before the start of your next turn, it is lost.\n\n"
            "Eyes of the Dead. You can use an action to name a place the humanoid saw in life, which creates an invisible sensor somewhere in that place if it is on the plane of existence you're currently on. "
            "The sensor remains for as long as you concentrate, up to 10 minutes (as if you were concentrating on a spell). You receive visual and auditory information from the sensor as if you were in its space using your senses.\n\n"
            "A creature that can see the sensor (such as one using see invisibility or truesight) sees a translucent image of the tormented humanoid whose soul you caged."
        ),
    }
    
    updates["Summon Fiend"] = {
        "source": "Tasha's Cauldron of Everything",
        "description": (
            "You call forth a fiendish spirit. It manifests in an unoccupied space that you can see within range. "
            "This corporeal form uses the Fiendish Spirit stat block. When you cast the spell, choose Demon, Devil, or Yugoloth. "
            "The creature resembles a fiend of the chosen type, which determines certain traits in its stat block. "
            "The creature disappears when it drops to 0 hit points or when the spell ends.\n\n"
            "The creature is an ally to you and your companions. In combat, the creature shares your initiative count, but it takes its turn immediately after yours. "
            "It obeys your verbal commands (no action required by you). If you don't issue any, it takes the Dodge action and uses its move to avoid danger.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 7th level or higher, use the higher level wherever the spell's level appears in the stat block."
        ),
    }
    
    updates["Tenser's Transformation"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You endow yourself with endurance and martial prowess fueled by magic. Until the spell ends, you can't cast spells, and you gain the following benefits:\n\n"
            "• You gain 50 temporary hit points. If any of these remain when the spell ends, they are lost.\n"
            "• You have advantage on attack rolls that you make with simple and martial weapons.\n"
            "• When you hit a target with a weapon attack, that target takes an extra 2d12 force damage.\n"
            "• You have proficiency with all armor, shields, simple weapons, and martial weapons.\n"
            "• You have proficiency in Strength and Constitution saving throws.\n"
            "• You can attack twice, instead of once, when you take the Attack action on your turn. You ignore this benefit if you already have a feature, like Extra Attack, that gives you extra attacks.\n\n"
            "Immediately after the spell ends, you must succeed on a DC 15 Constitution saving throw or suffer one level of exhaustion."
        ),
    }
    
    # ============================================
    # LEVEL 7 SPELLS
    # ============================================
    
    updates["Conjure Celestial"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You conjure a spirit from the Upper Planes. It manifests in an angelic form in an unoccupied space that you can see within range "
            "and uses the Celestial Spirit stat block. When you cast the spell, choose a benefit: Healer, Warrior, or Avenger. Your choice determines certain details in its stat block. "
            "The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
            "The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
            "It obeys your verbal commands (no action required by you). If you don't issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
            "Using a Higher-Level Spell Slot. Use the spell slot's level for the spell's level in the stat block."
        ),
    }
    
    updates["Crown of Stars"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "Seven star-like motes of light appear and orbit your head until the spell ends. You can use a bonus action to send one of the motes streaking toward one creature or object within 120 feet of you. "
            "When you do so, make a ranged spell attack. On a hit, the target takes 4d12 radiant damage. Whether you hit or miss, the mote is expended. The spell ends early if you expend the last mote.\n\n"
            "If you have four or more motes remaining, they shed bright light in a 30-foot radius and dim light for an additional 30 feet. "
            "With one to three motes remaining, they shed dim light in a 30-foot radius.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 8th level or higher, the number of motes created increases by two for each slot level above 7th."
        ),
    }
    
    updates["Delayed Blast Fireball"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A beam of yellow light flashes from you, then condenses at a chosen point within range as a glowing bead for the duration. "
            "When the spell ends, the bead explodes, and each creature in a 20-foot-radius Sphere centered on that point makes a Dexterity saving throw. "
            "A creature takes 12d6 Fire damage on a failed save or half as much damage on a successful one.\n\n"
            "If the glowing bead is touched before the duration ends, the creature touching it makes a Dexterity saving throw. "
            "On a failed save, the spell ends, causing the bead to explode. On a successful save, the creature can throw the bead up to 40 feet. "
            "If the thrown bead enters a creature's space or collides with a solid object, the spell ends, and the bead explodes.\n\n"
            "When the bead explodes, flammable objects in the explosion that aren't being worn or carried start burning.\n\n"
            "Using a Higher-Level Spell Slot. The damage increases by 1d6 for each spell slot level above 7."
        ),
    }
    
    updates["Divine Word"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You utter a word imbued with power from the Upper Planes. Each creature of your choice in range makes a Charisma saving throw. "
            "On a failed save, a target that has 50 Hit Points or fewer suffers an effect based on its current Hit Points, as shown in the Divine Word Effects table. "
            "Regardless of its Hit Points, a Celestial, an Elemental, a Fey, or a Fiend target that fails its save is forced back to its plane of origin (if it isn't there already) "
            "and can't return to the current plane for 24 hours by any means short of a Wish spell.\n\n"
            "Divine Word Effects\n"
            "Hit Points - Effect\n"
            "0-20 - The target dies.\n"
            "21-30 - The target has the Blinded, Deafened, and Stunned conditions for 1 hour.\n"
            "31-40 - The target has the Blinded and Deafened conditions for 10 minutes.\n"
            "41-50 - The target has the Deafened condition for 1 minute."
        ),
    }
    
    updates["Etherealness"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You step into the border regions of the Ethereal Plane, where it overlaps with your current plane. You remain in the Border Ethereal for the duration. "
            "During this time, you can move in any direction. If you move up or down, every foot of movement costs an extra foot. "
            "You can perceive the plane you left, which looks gray, and you can't see anything there more than 60 feet away.\n\n"
            "While on the Ethereal Plane, you can affect and be affected only by creatures, objects, and effects on that plane. "
            "Creatures that aren't on the Ethereal Plane can't perceive or interact with you unless a feature gives them the ability to do so.\n\n"
            "You return to the plane you left when the spell ends. You return to the spot you currently occupy. "
            "If you occupy the same spot as a solid object or creature when this happens, you're shunted to the nearest unoccupied space and take 1d10 Force damage for every 5 feet you're moved.\n\n"
            "When the spell ends, you immediately return to the plane you left unless the spell is dispelled. "
            "If you have moved more than 500 feet from where you left, you appear in a random location on the plane.\n\n"
            "Using a Higher-Level Spell Slot. You can target up to three willing creatures (including yourself) for each spell slot level above 7. "
            "The creatures must be within 10 feet of you when you cast the spell."
        ),
    }
    
    updates["Finger of Death"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You unleash negative energy toward a creature you can see within range. The target makes a Constitution saving throw, "
            "taking 7d8 + 30 Necrotic damage on a failed save or half as much damage on a successful one.\n\n"
            "A Humanoid killed by this spell rises at the start of your next turn as a Zombie that follows your commands."
        ),
    }
    
    updates["Fire Storm"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A storm of fire appears within range. The area of the storm consists of up to ten 10-foot Cubes, which you arrange as you like. "
            "Each Cube must be contiguous with at least one other Cube. Each creature in the area makes a Dexterity saving throw, "
            "taking 7d10 Fire damage on a failed save or half as much damage on a successful one.\n\n"
            "Flammable objects in the area that aren't being worn or carried start burning."
        ),
    }
    
    updates["Forcecage"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "An immobile, Invisible, Cube-shaped prison composed of magical force springs into existence around an area you choose within range. "
            "The prison can be a cage or a solid box, as you choose.\n\n"
            "A prison in the shape of a cage can be up to 20 feet on a side and is made from 1/2-inch diameter bars spaced 1/2 inch apart. "
            "A prison in the shape of a box can be up to 10 feet on a side, creating a solid barrier that prevents any matter from passing through it "
            "and blocking any spells cast into or out from the area.\n\n"
            "When you cast the spell, any creature that is completely inside the cage's area is trapped. "
            "Creatures only partially within the area, or those too large to fit inside it, are pushed away from the center of the area until they are completely outside it.\n\n"
            "A creature inside the cage can't leave it by nonmagical means. If the creature tries to use teleportation or interplanar travel to leave, "
            "it must first make a Charisma saving throw. On a successful save, the creature can use that magic to exit the cage. "
            "On a failed save, the creature doesn't exit the cage and wastes the spell or effect. The cage also extends into the Ethereal Plane, blocking ethereal travel.\n\n"
            "This spell can't be dispelled by Dispel Magic."
        ),
    }
    
    updates["Mirage Arcane"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You make terrain in an area up to 1 mile square look, sound, smell, and even feel like some other sort of terrain. "
            "Open fields or a road could be made to resemble a swamp, hill, crevasse, or some other rough or impassable terrain. "
            "A pond can be made to seem like a grassy meadow, a precipice like a gentle slope, or a rock-strewn gully like a wide and smooth road.\n\n"
            "Similarly, you can alter the appearance of structures or add them where none are present. The spell doesn't disguise, conceal, or add creatures.\n\n"
            "The illusion includes audible, visual, tactile, and olfactory elements, so it can turn clear ground into Difficult Terrain (or vice versa) "
            "or otherwise impede movement through the area. Any piece of the illusory terrain (such as a rock or stick) that is removed from the spell's area disappears immediately.\n\n"
            "Creatures with Truesight can see through the illusion to the terrain's true form; however, all other elements of the illusion remain, "
            "so while the creature is aware of the illusion's presence, the creature can still physically interact with the illusion."
        ),
    }
    
    updates["Mordenkainen's Magnificent Mansion"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You conjure a shimmering door in range that lasts for the duration. The door leads to an extradimensional dwelling and can be opened or closed at will while it exists. "
            "While the door is closed, it is Invisible.\n\n"
            "Beyond the door is a magnificent foyer with numerous chambers beyond. The dwelling's atmosphere is clean, fresh, and warm.\n\n"
            "You can create any floor plan you like for the dwelling, but it can't exceed 50 contiguous 10-foot Cubes. "
            "The place is furnished and decorated as you choose, and it contains sufficient food to serve a nine-course banquet for up to 100 people. "
            "Furnishings and other objects created by this spell dissipate into smoke if removed from it.\n\n"
            "A staff of 100 near-transparent servants attends all who enter. You determine the appearance of these servants and their attire. "
            "They are completely obedient to your orders. Each servant can perform tasks that a human could perform, but they can't attack or take any action that would directly harm another creature. "
            "Thus the servants can fetch things, clean, mend, fold clothes, light fires, serve food, pour wine, and so on. "
            "The servants can't leave the dwelling.\n\n"
            "Any creature that enters the extradimensional dwelling and remains there for at least 10 consecutive minutes gains the benefit of a Short Rest, "
            "and a creature can't gain this benefit again until it finishes a Long Rest outside the extradimensional dwelling. "
            "When the spell ends, any creatures or objects left inside the extradimensional space are deposited in the nearest unoccupied spaces to the door."
        ),
    }
    
    updates["Mordenkainen's Sword"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a spectral sword that hovers within range. It lasts for the duration.\n\n"
            "When the sword appears, you make a melee spell attack against a target within 5 feet of the sword. "
            "On a hit, the target takes Force damage equal to 4d12 plus your spellcasting ability modifier.\n\n"
            "On your later turns, you can take a Bonus Action to move the sword up to 30 feet to a spot you can see and repeat the attack against the same target or a different one."
        ),
    }
    
    updates["Plane Shift"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You and up to eight willing creatures who link hands in a circle are transported to a different plane of existence. "
            "You can specify a target destination in general terms, such as the City of Brass on the Elemental Plane of Fire or the palace of Dispater on the second level of the Nine Hells, "
            "and you appear in or near that destination, as determined by the DM.\n\n"
            "Alternatively, if you know the sigil sequence of a teleportation circle on another plane of existence, this spell can take you to that circle. "
            "If the teleportation circle is too small to hold all the creatures you transported, they appear in the closest unoccupied spaces next to the circle.\n\n"
            "Banishment. You can use this spell to banish an unwilling creature to another plane. Choose a creature within 10 feet of you and make a melee spell attack against it. "
            "On a hit, the creature must make a Charisma saving throw. If the creature fails the save, it is transported to a random location on the plane of existence you specify. "
            "A creature so transported must find its own way back to your current plane of existence."
        ),
    }
    
    updates["Power Word Fortify"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You fortify up to six creatures you can see within range. The spell bestows 120 Temporary Hit Points, which you divide among the spell's recipients as you choose."
        ),
    }
    
    updates["Prismatic Spray"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Eight rays of light flash from you in a 60-foot Cone. Each creature in the Cone makes a Dexterity saving throw. "
            "For each target, roll 1d8 to determine which color ray affects it, consulting the Prismatic Rays table.\n\n"
            "Prismatic Rays\n"
            "1d8 - Ray\n"
            "1 - Red. Failed Save: 12d6 Fire damage. Successful Save: Half as much damage.\n"
            "2 - Orange. Failed Save: 12d6 Acid damage. Successful Save: Half as much damage.\n"
            "3 - Yellow. Failed Save: 12d6 Lightning damage. Successful Save: Half as much damage.\n"
            "4 - Green. Failed Save: 12d6 Poison damage. Successful Save: Half as much damage.\n"
            "5 - Blue. Failed Save: 12d6 Cold damage. Successful Save: Half as much damage.\n"
            "6 - Indigo. Failed Save: The target has the Restrained condition and makes a Constitution saving throw at the end of each of its turns. "
            "If it successfully saves three times, the condition ends. If it fails three times, it has the Petrified condition until it is freed by an effect like the Greater Restoration spell. "
            "The successes and failures don't need to be consecutive; keep track of both until the target collects three of a kind.\n"
            "7 - Violet. Failed Save: The target has the Blinded condition and makes a Wisdom saving throw at the start of your next turn. "
            "On a successful save, the condition ends. On a failed save, the creature is transported to another plane of existence (DM's choice) and the Blinded condition ends.\n"
            "8 - Special. The target is struck by two rays. Roll twice, rerolling any 8."
        ),
    }
    
    updates["Project Image"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create an illusory copy of yourself that lasts for the duration. The copy can appear at any location within range that you have seen before, regardless of intervening obstacles. "
            "The illusion looks and sounds like you, but it is intangible. If the illusion takes any damage, it disappears, and the spell ends.\n\n"
            "You can see through the illusion's eyes and hear through its ears as if you were in its space. "
            "As a Magic action, you can move the illusion up to twice your Speed and make it gesture, speak, and behave in whatever way you choose. It mimics your mannerisms perfectly.\n\n"
            "A creature that takes a Study action to examine the illusion can determine that it is an illusion with a successful Intelligence (Investigation) check against your spell save DC. "
            "If a creature discerns the illusion for what it is, the creature can see through the image, and any noise it makes sounds hollow to the creature."
        ),
    }
    
    updates["Regenerate"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A creature you touch regains 4d8 + 15 Hit Points. For the duration, the target regains 1 Hit Point at the start of each of its turns (10 Hit Points each minute).\n\n"
            "The target's severed body members (fingers, legs, tails, and so on), if any, are restored after 2 minutes. If you have the severed part and hold it to the stump, the spell instantaneously causes the limb to knit to the stump."
        ),
    }
    
    updates["Resurrection"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "With a touch, you revive a dead creature that has been dead for no more than a century, didn't die of old age, and wasn't Undead when it died.\n\n"
            "The creature returns to life with all its Hit Points. This spell also neutralizes any poisons and cures nonmagical diseases that affected the creature at the time of death. "
            "This spell doesn't remove magical diseases, curses, or similar effects; if such effects aren't removed prior to casting the spell, they return when the creature returns to life.\n\n"
            "This spell closes all mortal wounds and restores any missing body parts.\n\n"
            "Coming back from the dead is an ordeal. The target takes a −4 penalty to D20 Tests. "
            "Every time the target finishes a Long Rest, the penalty is reduced by 1 until it becomes 0.\n\n"
            "Casting this spell to revive a creature that has been dead for 365 days or longer taxes you. "
            "Until you finish a Long Rest, you can't cast spells again, and you have Disadvantage on D20 Tests."
        ),
    }
    
    updates["Reverse Gravity"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "This spell reverses gravity in a 50-foot-radius, 100-foot high Cylinder centered on a point within range. "
            "All creatures and objects in that area that aren't anchored to the ground fall upward and reach the top of the Cylinder. "
            "A creature can make a Dexterity saving throw to grab onto a fixed object it can reach, thus avoiding the fall upward.\n\n"
            "If a ceiling or an anchored object is encountered in this fall, creatures and objects strike it just as they would during a downward fall. "
            "If an affected creature or object reaches the Cylinder's top without striking anything, it hovers there for the duration.\n\n"
            "When the spell ends, affected objects and creatures fall back down."
        ),
    }
    
    updates["Sequester"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "With a touch, you magically sequester a willing creature or an object. "
            "For the duration, the target has the Invisible condition and can't be targeted by Divination spells, perceived through scrying sensors created by Divination spells, or detected by abilities that sense creatures or objects.\n\n"
            "If the target is a creature, it enters a state of suspended animation; it has the Unconscious condition, doesn't age, and doesn't need food, water, or air.\n\n"
            "You can set a trigger that ends the spell early. The trigger can be anything you choose, such as someone speaking a certain word or entering the target's space. "
            "Dispel Magic can end the spell only if it is cast with a level 9 spell slot, targeting either the trigger or the sequestered target."
        ),
    }
    
    updates["Simulacrum"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a simulacrum of one Beast or Humanoid that is within 10 feet of you for the entire casting of the spell. "
            "You finish the casting by touching both the creature and a pile of ice or snow that is the same size as that creature, "
            "and the pile turns into the simulacrum, which is a creature. It uses the game statistics of the original creature at the time of casting, "
            "except it is a Construct, its Hit Point maximum is half as much, and it can't cast this spell.\n\n"
            "The simulacrum is Friendly to you and creatures you designate. It obeys your commands and acts on your turn in combat. "
            "The simulacrum can't gain levels, and it can't take Short or Long Rests.\n\n"
            "If the simulacrum takes damage, the only way to restore its Hit Points is to repair it as you take a Long Rest, during which you expend components worth 100 GP per Hit Point restored. "
            "The simulacrum must stay within 5 feet of you for the repair.\n\n"
            "The simulacrum lasts until it drops to 0 Hit Points, at which point it reverts to snow and melts away. "
            "If you cast this spell again, any simulacrum you created with this spell is instantly destroyed."
        ),
    }
    
    updates["Symbol"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You inscribe a harmful glyph either on a surface (such as a section of floor or wall) or within an object that can be closed (such as a book or chest). "
            "The glyph can cover an area no larger than 10 feet in diameter. If you choose an object, it must remain in place; if it is moved more than 10 feet from where you cast this spell, the glyph breaks, and the spell ends without being triggered.\n\n"
            "The glyph is nearly imperceptible and requires a successful Wisdom (Perception) check against your spell save DC to find.\n\n"
            "You decide what triggers the glyph when you cast the spell. For glyphs inscribed on a surface, common triggers include touching or stepping on the glyph, removing another object covering it, "
            "approaching within a certain distance of it, or manipulating the object that holds it. For glyphs inscribed within an object, common triggers include opening that object, approaching within a certain distance of it, "
            "or seeing or reading the glyph.\n\n"
            "You can refine the trigger so that only creatures of certain types activate it (for example, the glyph could be set to affect Aberrations). "
            "You can also set conditions for creatures that don't trigger the glyph, such as those who say a certain password.\n\n"
            "When you inscribe the glyph, choose one of the options below for its effect. Once triggered, the glyph glows, filling a 60-foot-radius Sphere with Dim Light for 10 minutes, after which time the spell ends. "
            "Each creature in the Sphere when the glyph activates is targeted by its effect, as is a creature that enters the Sphere for the first time on a turn or ends its turn there. A creature is targeted only once per turn.\n\n"
            "Death. Each target makes a Constitution saving throw, taking 10d10 Necrotic damage on a failed save or half as much damage on a successful save.\n\n"
            "Discord. Each target makes a Constitution saving throw. On a failed save, a target argues with other creatures for 1 minute. During this time, it is incapable of meaningful communication and has Disadvantage on attack rolls and ability checks.\n\n"
            "Fear. Each target must succeed on a Wisdom saving throw or have the Frightened condition for 1 minute. While Frightened, the target must move at least 30 feet away from the glyph on each of its turns, if able.\n\n"
            "Hopelessness. Each target must succeed on a Charisma saving throw or have the Incapacitated condition for 1 minute. During this time, the target can't attack or target any creature with harmful abilities, spells, or other magical effects.\n\n"
            "Insanity. Each target must succeed on an Intelligence saving throw or has the Charmed condition for 1 minute. While Charmed, the target has the Incapacitated condition and ignores all other creatures, babbling and laughing uncontrollably.\n\n"
            "Pain. Each target must succeed on a Constitution saving throw or have the Incapacitated condition for 1 minute.\n\n"
            "Sleep. Each target must succeed on a Wisdom saving throw or have the Unconscious condition for 10 minutes. A creature awakens if it takes damage or if someone takes an action to shake it awake.\n\n"
            "Stunning. Each target must succeed on a Wisdom saving throw or have the Stunned condition for 1 minute."
        ),
    }
    
    updates["Teleport"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "This spell instantly transports you and up to eight willing creatures that you can see within range, or a single object that you can see within range, "
            "to a destination you select. If you target an object, it must be able to fit entirely inside a 10-foot Cube, and it can't be held or carried by an unwilling creature.\n\n"
            "The destination you choose must be known to you, and it must be on the same plane of existence as you. "
            "Your familiarity with the destination determines whether you arrive there successfully. The DM rolls 1d100 and consults the Teleportation Outcome table.\n\n"
            "Teleportation Outcome\n"
            "Familiarity - Mishap - Similar Area - Off Target - On Target\n"
            "Permanent circle - — - — - — - 01-100\n"
            "Linked object - — - — - — - 01-100\n"
            "Very familiar - 01-05 - 06-13 - 14-24 - 25-100\n"
            "Seen casually - 01-33 - 34-43 - 44-53 - 54-100\n"
            "Viewed once or described - 01-43 - 44-53 - 54-73 - 74-100\n"
            "False destination - 01-50 - 51-100 - — - —\n\n"
            "Familiarity. \"Permanent circle\" means a permanent teleportation circle whose sigil sequence you know. \"Linked object\" means you possess an object taken from the destination within the last six months, such as a book from a wizard's library. "
            "\"Very familiar\" is a place you have visited often, a place you have carefully studied, or a place you can see when you cast the spell. \"Seen casually\" is a place you have seen more than once but with which you aren't very familiar. "
            "\"Viewed once or described\" is a place you have seen once, possibly using magic, or a place you have heard described, perhaps from a map. \"False destination\" is a place that doesn't exist, such as if you tried to teleport to a familiar location that no longer exists.\n\n"
            "On Target. You and your group appear where you want to.\n\n"
            "Off Target. You and your group appear a random distance away from the destination in a random direction. "
            "The farther you travel, the farther off target you are likely to be. Distance off target is 1d10 × 1d10 percent of the distance traveled. "
            "For example, if you tried to teleport 120 miles and rolled a 5 and 3 on the two d10s, then you would be off target by 15 percent, or 18 miles. The DM determines the direction off target by rolling 1d8, with 1 being north, 2 being northeast, and so on. "
            "If you were teleporting to a coastal city and wound up 18 miles out at sea, you might be in trouble.\n\n"
            "Similar Area. You and your group wind up in a different area that's visually or thematically similar to the target area. For example, if you were teleporting to your home laboratory, you might wind up in another laboratory or in an alchemy supply shop. "
            "Generally, you appear in the closest similar place, but that's up to the DM.\n\n"
            "Mishap. The spell's magic is disrupted, resulting in a mishap. Each teleporting creature (or the target object) takes 3d10 Force damage, and the DM rerolls on the table to see where you wind up (multiple mishaps can occur, dealing damage each time)."
        ),
    }
    
    updates["Whirlwind"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "A whirlwind howls down to a point on the ground you specify. The whirlwind is a 10-foot-radius, 30-foot-high cylinder centered on that point. "
            "Until the spell ends, you can use your action to move the whirlwind up to 30 feet in any direction along the ground. "
            "The whirlwind sucks up any Medium or smaller objects that aren't secured to anything and that aren't worn or carried by anyone.\n\n"
            "A creature must make a Dexterity saving throw the first time on a turn that it enters the whirlwind or that the whirlwind enters its space, including when the whirlwind first appears. "
            "A creature takes 10d6 bludgeoning damage on a failed save, or half as much damage on a successful one. "
            "In addition, a Large or smaller creature that fails the save must succeed on a Strength saving throw or become restrained in the whirlwind until the spell ends. "
            "When a creature starts its turn restrained by the whirlwind, the creature is pulled 5 feet higher inside it, unless the creature is at the top. "
            "A restrained creature moves with the whirlwind and falls when the spell ends, unless the creature has some means to stay aloft.\n\n"
            "A restrained creature can use an action to make a Strength or Dexterity check against your spell save DC. If successful, the creature is no longer restrained by the whirlwind and is hurled 3d6 × 10 feet away from it in a random direction."
        ),
    }
    
    # ============================================
    # LEVEL 8 SPELLS
    # ============================================
    
    updates["Abi-Dalzim's Horrid Wilting"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You draw the moisture from every creature in a 30-foot cube centered on a point you choose within range. "
            "Each creature in that area must make a Constitution saving throw. "
            "Constructs and undead aren't affected, and plants and water elementals make this saving throw with disadvantage. "
            "A creature takes 12d8 necrotic damage on a failed save, or half as much damage on a successful one.\n\n"
            "Nonmagical plants in the area that aren't creatures, such as trees and shrubs, wither and die instantly."
        ),
    }
    
    updates["Animal Shapes"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Choose any number of willing creatures that you can see within range. Each target shape-shifts into a Large or smaller Beast of your choice that has a Challenge Rating of 4 or lower. "
            "You can choose a different form for each target. On later turns, you can take a Magic action to transform the targets again.\n\n"
            "A target's game statistics are replaced by the chosen Beast's statistics, but the target retains its creature type; Hit Points; Hit Point Dice; alignment; ability to communicate; "
            "and Intelligence, Wisdom, and Charisma scores. The target's actions are limited by the Beast form's anatomy, and it can't cast spells. The target's equipment melds into the new form, "
            "and the target can't use any of that equipment while in that form.\n\n"
            "The target gains a number of Temporary Hit Points equal to the Beast form's Hit Points. "
            "The transformation lasts for the duration for each target, or until the target drops to 0 Hit Points or dies."
        ),
    }
    
    updates["Antimagic Field"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "An aura of antimagic surrounds you in 10-foot Emanation. No one can cast spells, take Magic actions, or create other magical effects inside the aura, "
            "and those things can't target or otherwise affect anything inside it. Magical properties of magic items don't work inside the aura or on anything inside it.\n\n"
            "Areas of effect created by spells and other magic can't extend into the aura, and no one can teleport into or out of it or use planar travel there. "
            "Portals close temporarily while in the aura.\n\n"
            "Ongoing spells, except those cast by an Artifact or a deity, are suppressed in the area. While an effect is suppressed, it doesn't function, but the time it spends suppressed counts against its duration.\n\n"
            "Dispel Magic has no effect on the aura, and the auras created by different Antimagic Field spells don't nullify each other."
        ),
    }
    
    updates["Antipathy/Sympathy"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "As you cast the spell, choose whether it creates antipathy or sympathy, and target one creature or object that is Huge or smaller. "
            "Then specify a kind of creature, such as red dragons, goblins, or vampires. A creature of the chosen kind makes a Wisdom saving throw when it comes within 120 feet of the target. "
            "Your choice of antipathy or sympathy determines what happens to a creature when it fails that save:\n\n"
            "Antipathy. The creature has the Frightened condition. The Frightened creature must use its movement on its turns to get as far away as possible from the target, "
            "moving by the safest route.\n\n"
            "Sympathy. The creature has the Charmed condition. The Charmed creature must use its movement on its turns to get as close as possible to the target, moving by the safest route. "
            "If the creature is within 5 feet of the target, the creature can't willingly move away. "
            "If the target damages the Charmed creature, that creature can make a Wisdom saving throw to end the effect, as described below.\n\n"
            "Ending the Effect. If the Frightened or Charmed creature ends its turn more than 120 feet away from the target, the creature makes a Wisdom saving throw. "
            "On a successful save, the creature is no longer affected by the target. "
            "On a failed save, the creature doesn't make this save again until it ends another turn more than 120 feet away from the target."
        ),
    }
    
    updates["Befuddlement"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You blast the mind of a creature that you can see within range. The target makes an Intelligence saving throw.\n\n"
            "On a failed save, the target takes 10d12 Psychic damage and can't cast spells or take the Magic action. "
            "At the end of every 30 days, the target repeats the save, ending the effect on a success. The effect can also be ended by the Greater Restoration, Heal, or Wish spell.\n\n"
            "On a successful save, the target takes half as much damage only."
        ),
    }
    
    updates["Clone"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You touch a creature or at least 1 cubic inch of its flesh. An inert duplicate of that creature forms inside the vessel used in the spell's casting "
            "and finishes growing after 120 days; you choose whether the finished clone is the same age as the creature or younger. "
            "The clone remains inert and endures indefinitely while its vessel remains undisturbed.\n\n"
            "If the original creature dies after the clone finishes forming, the creature's soul transfers to the clone if the soul is free and willing to return. "
            "The clone is physically identical to the original and has the same personality, memories, and abilities, but none of the original's equipment. "
            "The creature's original remains, if any, become inert and can't be revived, since the creature's soul is elsewhere."
        ),
    }
    
    updates["Control Weather"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You take control of the weather within 5 miles of you for the duration. You must be outdoors to cast this spell, and it ends early if you go indoors.\n\n"
            "When you cast the spell, you change the current weather conditions, which are determined by the DM. "
            "You can change precipitation, temperature, and wind. It takes 1d4 × 10 minutes for the new conditions to take effect. "
            "Once they do so, you can change the conditions again. When the spell ends, the weather gradually returns to normal.\n\n"
            "When you change the weather conditions, find the current conditions on the tables included in this spell's full description and change them by one stage, up or down. "
            "When changing the wind, you can change its direction.\n\n"
            "Precipitation\n"
            "Stage - Condition\n"
            "1 - Clear\n"
            "2 - Light clouds\n"
            "3 - Overcast or ground fog\n"
            "4 - Rain, hail, or snow\n"
            "5 - Torrential rain, driving hail, or blizzard\n\n"
            "Temperature\n"
            "Stage - Condition\n"
            "1 - Heat wave\n"
            "2 - Hot\n"
            "3 - Warm\n"
            "4 - Cool\n"
            "5 - Cold\n"
            "6 - Freezing\n\n"
            "Wind\n"
            "Stage - Condition\n"
            "1 - Calm\n"
            "2 - Moderate wind\n"
            "3 - Strong wind\n"
            "4 - Gale\n"
            "5 - Storm"
        ),
    }
    
    updates["Demiplane"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a shadowy door on a flat solid surface that you can see within range. "
            "This door is large enough to allow Medium creatures to pass through unhindered. "
            "When opened, the door leads to a demiplane that is an empty room 30 feet in each dimension, made of wood or stone (your choice). "
            "When the spell ends, the door vanishes, and any objects inside the demiplane remain there. "
            "Any creatures inside also remain unless they opt to be shunted through the door as it vanishes, ending up in the nearest unoccupied spaces to the door's former space.\n\n"
            "Each time you cast this spell, you can create a new demiplane or connect the shadowy door to a demiplane you created with a previous casting of this spell. "
            "Additionally, if you know the nature and contents of a demiplane created by a casting of this spell by another creature, you can connect the shadowy door to that demiplane instead."
        ),
    }
    
    updates["Dominate Monster"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "One creature you can see within range must succeed on a Wisdom saving throw or have the Charmed condition for the duration. "
            "The target has Advantage on the save if you or your allies are fighting it. Whenever the target takes damage, it repeats the save, ending the spell on itself on a success.\n\n"
            "You have a telepathic link with the Charmed target while the two of you are on the same plane of existence. "
            "On your turn, you can use this link to issue commands to the target (no action required), such as \"Attack that creature,\" \"Move over there,\" or \"Fetch that object.\" "
            "The target does its best to obey on its turn. If it completes an order and doesn't receive further direction from you, it acts and moves as it likes, focusing on protecting itself.\n\n"
            "You can command the target to take a Reaction but must take your own Reaction to do so.\n\n"
            "Using a Higher-Level Spell Slot. Your Concentration can last longer with a level 9 spell slot (up to 8 hours)."
        ),
    }
    
    updates["Earthquake"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Choose a point on the ground that you can see within range. For the duration, an intense tremor rips through the ground in a 100-foot-radius circle centered on that point. "
            "The ground there is Difficult Terrain.\n\n"
            "When you cast this spell and at the end of each of your turns for the duration, each creature on the ground in the area makes a Dexterity saving throw. "
            "On a failed save, a creature has the Prone condition, and its Concentration is broken.\n\n"
            "You can also cause the effects below.\n\n"
            "Fissures. A total of 1d6 fissures open in the spell's area at the end of the turn you cast it. "
            "You choose the fissures' locations, which can't be under structures. Each fissure is 1d10 × 10 feet deep and 10 feet wide, and it extends from one edge of the spell's area to another edge. "
            "A creature in a fissure's space when the fissure opens must succeed on a Dexterity saving throw or fall in. A creature that saves moves with the fissure's edge. "
            "A creature that falls into a fissure makes a Dexterity saving throw, taking 4d6 Bludgeoning damage on a failed save or half as much damage on a successful one. "
            "A fissure that opens beneath a structure causes it to automatically collapse (see below).\n\n"
            "Structures. The tremor deals 50 Bludgeoning damage to any structure in contact with the ground in the area when you cast the spell and at the end of each of your turns until the spell ends. "
            "If a structure drops to 0 Hit Points, it collapses.\n\n"
            "A creature within a distance from a collapsing structure equal to half the structure's height must succeed on a Dexterity saving throw "
            "or take 12d6 Bludgeoning damage, have the Prone condition, and be buried in the rubble, which requires a DC 20 Strength (Athletics) check as an action to escape. "
            "If the save succeeds, the creature takes half as much damage only."
        ),
    }
    
    updates["Feeblemind"] = {
        "source": "Player's Handbook (2014)",
        "description": (
            "You blast the mind of a creature that you can see within range, attempting to shatter its intellect and personality. The target takes 4d6 psychic damage and must make an Intelligence saving throw.\n\n"
            "On a failed save, the creature's Intelligence and Charisma scores become 1. The creature can't cast spells, activate magic items, understand language, "
            "or communicate in any intelligible way. The creature can, however, identify its friends, follow them, and even protect them.\n\n"
            "At the end of every 30 days, the creature can repeat its saving throw against this spell. If it succeeds on its saving throw, the spell ends. "
            "The spell can also be ended by greater restoration, heal, or wish."
        ),
    }
    
    updates["Glibness"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Until the spell ends, when you make a Charisma check, you can replace the number you roll with a 15. "
            "Additionally, no matter what you say, magic that would determine if you are telling the truth indicates that you are being truthful."
        ),
    }
    
    updates["Holy Aura"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "For the duration, you emit an aura in a 30-foot Emanation. While in the aura, creatures of your choice have Advantage on all saving throws, "
            "and other creatures have Disadvantage on attack rolls against them. In addition, when a Fiend or an Undead hits an affected creature with a melee attack roll, "
            "the attacker must succeed on a Constitution saving throw or have the Blinded condition until the end of its next turn."
        ),
    }
    
    updates["Incendiary Cloud"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A swirling cloud of embers and smoke fills a 20-foot-radius Sphere centered on a point within range. The cloud's area is Heavily Obscured. "
            "It lasts for the duration or until a strong wind (like that created by Gust of Wind) disperses it.\n\n"
            "When the cloud appears, each creature in it makes a Dexterity saving throw, taking 10d8 Fire damage on a failed save or half as much damage on a successful one. "
            "A creature must also make this save when the Sphere moves into its space and when it enters the Sphere or ends its turn there. A creature makes this save only once per turn.\n\n"
            "The cloud moves 10 feet away from you in a direction you choose at the start of each of your turns."
        ),
    }
    
    updates["Maddening Darkness"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "Magical darkness spreads from a point you choose within range to fill a 60-foot-radius sphere until the spell ends. "
            "The darkness spreads around corners. A creature with darkvision can't see through this darkness. "
            "Non-magical light, as well as light created by spells of 8th level or lower, can't illuminate the area.\n\n"
            "Shrieks, gibbering, and mad laughter can be heard within the sphere. Whenever a creature starts its turn in the sphere, "
            "it must make a Wisdom saving throw, taking 8d8 psychic damage on a failed save, or half as much damage on a successful one."
        ),
    }
    
    updates["Maze"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You banish a creature that you can see within range into a labyrinthine demiplane. The target remains there for the duration or until it escapes the maze.\n\n"
            "The target can take a Study action to try to escape. When it does so, it makes a DC 20 Intelligence (Investigation) check. "
            "If it succeeds, it escapes, and the spell ends.\n\n"
            "When the spell ends, the target reappears in the space it left or, if that space is occupied, in the nearest unoccupied space."
        ),
    }
    
    updates["Mighty Fortress"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "A fortress of stone erupts from a square area of ground of your choice that you can see within range. The area is 120 feet on each side, "
            "and it must not have any buildings or other structures on it. Any creatures in the area are harmlessly lifted up as the fortress rises.\n\n"
            "The fortress has four turrets with square bases, each one 20 feet on a side and 30 feet tall, with one turret on each corner. "
            "The turrets are connected to each other by stone walls that are each 80 feet long, creating an enclosed area. "
            "Each wall is 1 foot thick and is composed of panels that are 10 feet wide and 20 feet tall. Each panel is contiguous with two other panels or one other panel and a turret. "
            "You can place up to four stone doors in the fortress's outer wall.\n\n"
            "A small keep stands inside, in the middle of the enclosed area. The keep has a square base that is 50 feet on each side, and it has three floors with 10-foot-high ceilings. "
            "Each of the floors can be divided into as many rooms as you like, provided each room is at least 5 feet on each side. "
            "The floors of the keep are connected by stone staircases, its walls are 6 inches thick, and interior rooms can have stone doors or open archways as you choose. "
            "The keep is furnished and decorated however you like, and it contains sufficient food to serve a nine-course banquet for up to 100 people each day. "
            "Furnishings, food, and other objects created by this spell crumble to dust if removed from the fortress.\n\n"
            "A staff of one hundred invisible servants obeys any command given to them by creatures you designate when you cast the spell. "
            "Each servant functions as if created by the unseen servant spell.\n\n"
            "The walls, turrets, and keep are all made of stone that can be damaged. Each 10-foot-by-10-foot section of stone has AC 15 and 30 hit points per inch of thickness. "
            "Reducing a section of stone to 0 hit points destroys it and might cause connected sections to buckle and collapse at the DM's discretion.\n\n"
            "After 7 days or when you cast this spell somewhere else, the fortress harmlessly crumbles and sinks back into the ground, leaving any creatures that were inside it safely on the ground.\n\n"
            "Casting this spell on the same spot once every 7 days for a year makes the fortress permanent."
        ),
    }
    
    updates["Mind Blank"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Until the spell ends, one willing creature you touch has Immunity to Psychic damage and the Charmed condition. "
            "The target is also unaffected by anything that would sense its emotions or read its thoughts, Divination spells, "
            "and the Charmed condition."
        ),
    }
    
    updates["Power Word Stun"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You overwhelm the mind of one creature you can see within range. If the target has 150 Hit Points or fewer, it has the Stunned condition. "
            "Otherwise, its Speed is 0 until the start of your next turn.\n\n"
            "The Stunned target makes a Constitution saving throw at the end of each of its turns, ending the condition on itself on a success."
        ),
    }
    
    updates["Sunburst"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Brilliant sunlight flashes in a 60-foot-radius Sphere centered on a point you choose within range. "
            "Each creature in the Sphere makes a Constitution saving throw. On a failed save, a creature takes 12d6 Radiant damage and has the Blinded condition for 1 minute. "
            "On a successful save, it takes half as much damage only.\n\n"
            "A creature Blinded by this spell makes another Constitution saving throw at the end of each of its turns, ending the condition on itself on a success.\n\n"
            "This spell dispels Darkness in its area that was created by any spell."
        ),
    }
    
    updates["Telepathy"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a telepathic link between yourself and a willing creature with which you are familiar. "
            "The creature can be anywhere on the same plane of existence as you. The spell ends if you or the target are no longer on the same plane.\n\n"
            "Until the spell ends, you and the target can instantly share words, images, sounds, and other sensory messages with each other through the link, "
            "and the target recognizes you as the creature it is communicating with. The spell enables a creature with an Intelligence of at least 1 to understand the meaning of your words "
            "and any sensory messages you send to it."
        ),
    }
    
    updates["Tsunami"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A wall of water springs into existence at a point you choose within range. You can make the wall up to 300 feet long, 300 feet high, and 50 feet thick. "
            "The wall lasts for the duration.\n\n"
            "When the wall appears, each creature in its area makes a Strength saving throw, taking 6d10 Bludgeoning damage on a failed save or half as much damage on a successful one.\n\n"
            "At the start of each of your turns after the wall appears, the wall, along with any creatures in it, moves 50 feet away from you. "
            "Any Huge or smaller creature inside the wall or whose space the wall enters when it moves must succeed on a Strength saving throw or take 5d10 Bludgeoning damage. "
            "A creature can take this damage only once per turn. At the end of the turn, the wall's height is reduced by 50 feet, and the damage the wall deals on later turns is reduced by 1d10. "
            "When the wall reaches 0 feet in height, the spell ends."
        ),
    }
    
    # ============================================
    # LEVEL 9 SPELLS
    # ============================================
    
    updates["Astral Projection"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You and up to eight willing creatures within range project your astral bodies into the Astral Plane (the spell ends instantly if you are already on that plane). "
            "Each target's body is left behind in a state of suspended animation; it has the Unconscious condition, doesn't need food or air, and doesn't age.\n\n"
            "A target's astral form resembles its body in almost every way, replicating its game statistics and possessions. "
            "The principal difference is the addition of a silvery cord that trails from between the shoulder blades of the astral form. "
            "The cord fades from view after 1 foot. If the cord is cut—Loss something that happens only when an effect specifically states that it does—the target's body and astral form both die.\n\n"
            "A target's astral form can travel through the Astral Plane. The moment an astral form leaves that plane, the target's body and possessions travel along the silver cord, "
            "causing the target to re-enter its body on the new plane.\n\n"
            "Any damage or other effects that apply to an astral form have no effect on the target's body and vice versa. If a target's body or astral form drops to 0 Hit Points, the spell ends for that target. "
            "The spell ends for all the targets if you take a Magic action to dismiss it."
        ),
    }
    
    updates["Foresight"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You touch a willing creature and bestow a limited ability to see into the immediate future. For the duration, the target has Advantage on D20 Tests, "
            "and other creatures have Disadvantage on attack rolls against it. The spell ends early if you cast it again."
        ),
    }
    
    updates["Gate"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You conjure a portal linking an unoccupied space you can see within range to a precise location on a different plane of existence. "
            "The portal is a circular opening, which you can make 5 to 20 feet in diameter. You can orient the portal in any direction you choose. "
            "The portal lasts for the duration, and the portal's destination is visible through it.\n\n"
            "The portal has a front and a back on each plane where it appears. Travel through the portal is possible only by moving through its front. "
            "Anything that does so is instantly transported to the other plane, appearing in the unoccupied space nearest to the portal.\n\n"
            "Deities and other planar rulers can prevent portals created by this spell from opening in their presence or anywhere within their domains.\n\n"
            "When you cast this spell, you can speak the name of a specific creature (a pseudonym, title, or nickname doesn't work). "
            "If that creature is on a plane other than the one you are on, the portal opens next to the named creature and draws it through to the nearest unoccupied space on your side of the portal. "
            "You gain no special power over the creature, and it is free to act as the DM deems appropriate. It might leave, attack you, or help you."
        ),
    }
    
    updates["Imprisonment"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You create a magical restraint to hold a creature that you can see within range. The target must make a Wisdom saving throw. "
            "On a successful save, the target is unaffected, and it is immune to this spell for 24 hours. On a failed save, the target is affected by one of the following effects of your choice:\n\n"
            "Burial. The target is entombed far beneath the earth in a Sphere of magical force that is just large enough to contain the target. "
            "Nothing can pass into or out of the Sphere.\n\n"
            "Chaining. Chains made of magical force hold the target in place. The target has the Restrained condition and can't be moved by any means.\n\n"
            "Hedged Prison. The target is confined to a small area of your choice that is warded against teleportation and planar travel. "
            "The area can be as small as 10 feet on a side or as large as 100 feet on a side.\n\n"
            "Minimus Containment. The target becomes 1 inch tall and is imprisoned inside a gemstone or a similar object. "
            "Light can pass through the gemstone (allowing the target to see out and other creatures to see in), but nothing else can pass through by any means.\n\n"
            "Slumber. The target has the Unconscious condition and can't be awoken.\n\n"
            "Ending the Spell. The spell lasts until dispelled. Dispel Magic can end the spell only if it is cast with a level 9 spell slot. "
            "The conditions for ending the spell are specified in the component you choose. "
            "A condition can be as elaborate or as simple as you choose (such as after 1,000 years or if the tarrasque awakens). "
            "A Wish spell can end the spell."
        ),
    }
    
    updates["Invulnerability"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You are immune to all damage until the spell ends."
        ),
    }
    
    updates["Mass Heal"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A flood of healing energy flows from you into creatures around you. You restore up to 700 Hit Points, divided as you choose among any number of creatures that you can see within range. "
            "Creatures healed by this spell also have the Blinded, Deafened, and Poisoned conditions removed from them."
        ),
    }
    
    updates["Mass Polymorph"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You transform up to ten creatures of your choice that you can see within range. An unwilling target must succeed on a Wisdom saving throw to resist the transformation. "
            "An unwilling shapechanger automatically succeeds on the save.\n\n"
            "Each target assumes a beast form of your choice, and you can choose the same form or different ones for each target. "
            "The new form can be any beast you have seen whose challenge rating is equal to or less than the target's (or half the target's level, if the target doesn't have a challenge rating). "
            "The target's game statistics, including mental ability scores, are replaced by the statistics of the chosen beast, but the target retains its alignment and personality.\n\n"
            "Each target gains a number of temporary hit points equal to the hit points of its new form. "
            "These temporary hit points can't be replaced by temporary hit points from another source. A target reverts to its normal form when it has no more temporary hit points or it dies. "
            "If the spell ends before then, the creature loses all its temporary hit points and reverts to its normal form.\n\n"
            "The creature is limited in the actions it can perform by the nature of its new form. It can't speak, cast spells, or do anything else that requires hands or speech.\n\n"
            "The target's gear melds into the new form. The target can't activate, use, wield, or otherwise benefit from any of its equipment."
        ),
    }
    
    updates["Meteor Swarm"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Blazing orbs of fire plummet to the ground at four different points you can see within range. "
            "Each creature in a 40-foot-radius Sphere centered on each of those points makes a Dexterity saving throw. "
            "A creature takes 20d6 Fire damage and 20d6 Bludgeoning damage on a failed save or half as much damage on a successful one. "
            "A creature in the area of more than one fiery Sphere is affected only once.\n\n"
            "Flammable objects that aren't being worn or carried start burning if they're in the spell's area."
        ),
    }
    
    updates["Power Word Heal"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A wave of healing energy washes over a creature you can see within range. The target regains all its Hit Points. "
            "If the creature has the Charmed, Frightened, Paralyzed, Poisoned, or Stunned condition, the condition ends. "
            "If the creature has the Prone condition, it can use its Reaction to stand up."
        ),
    }
    
    updates["Power Word Kill"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You compel one creature you can see within range to die. If the target has 100 Hit Points or fewer, it dies. Otherwise, it takes 12d12 Psychic damage."
        ),
    }
    
    updates["Prismatic Wall"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "A shimmering, multicolored plane of light forms a vertical wall—up to 90 feet long, 30 feet high, and 1 inch thick—centered on a point within range. "
            "Alternatively, you can shape the wall into a globe up to 30 feet in diameter centered on a point within range. The wall lasts for the duration. "
            "If you position the wall so that it passes through a space occupied by a creature, the spell ends instantly without effect.\n\n"
            "The wall sheds Bright Light within 100 feet and Dim Light for an additional 100 feet. You and creatures you designate when you cast the spell can pass through and be near the wall without harm. "
            "If another creature that can see the wall moves within 20 feet of it or starts its turn there, the creature must succeed on a Constitution saving throw or have the Blinded condition for 1 minute.\n\n"
            "The wall consists of seven layers, each with a different color. When a creature reaches into or passes through the wall, it does so one layer at a time through all the layers. "
            "On entry into each layer, the creature must make a Dexterity saving throw or be affected by that layer's properties as described in the Prismatic Layers table.\n\n"
            "The wall can be destroyed, one layer at a time, in order from red to violet, by means specific to each layer. Once a layer is destroyed, it is gone for the duration. "
            "An Antimagic Field has no effect on the wall, and Dispel Magic can affect only the violet layer.\n\n"
            "Prismatic Layers\n"
            "Order - Color - Effect on Failed Save - Negated By\n"
            "1 - Red - 12d6 Fire damage - Cone of Cold\n"
            "2 - Orange - 12d6 Acid damage - Gust of Wind\n"
            "3 - Yellow - 12d6 Lightning damage - Disintegrate\n"
            "4 - Green - 12d6 Poison damage - Passwall\n"
            "5 - Blue - 12d6 Cold damage - Magic Missile\n"
            "6 - Indigo - On a failed save, the target has the Restrained condition and makes a Constitution saving throw at the end of each of its turns. "
            "If it saves successfully three times, the condition ends. If it fails three times, it has the Petrified condition until freed by an effect like Greater Restoration. "
            "The successes and failures needn't be consecutive; keep track of both until the target collects three of a kind. - Daylight\n"
            "7 - Violet - On a failed save, the target has the Blinded condition and makes a Wisdom saving throw at the start of your next turn. "
            "On a successful save, the condition ends. On a failed save, the condition ends, and the creature is transported to another plane of existence (DM's choice). - Dispel Magic"
        ),
    }
    
    updates["Psychic Scream"] = {
        "source": "Xanathar's Guide to Everything",
        "description": (
            "You unleash the power of your mind to blast the intellect of up to ten creatures of your choice that you can see within range. "
            "Creatures that have an Intelligence score of 2 or lower are unaffected.\n\n"
            "Each target must make an Intelligence saving throw. On a failed save, a target takes 14d6 psychic damage and is stunned. "
            "On a successful save, a target takes half as much damage and isn't stunned. If a target is killed by this damage, its head explodes, assuming it has one.\n\n"
            "A stunned target can make an Intelligence saving throw at the end of each of its turns. On a successful save, the stunning effect ends."
        ),
    }
    
    updates["Shapechange"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You shape-shift into another creature for the duration or until you take a Magic action to shape-shift into a different eligible form. "
            "The new form must be of a creature that has a Challenge Rating no higher than your level or Challenge Rating. "
            "You must have seen the sort of creature before, and it can't be a Construct or an Undead.\n\n"
            "When you shape-shift, you gain a number of Temporary Hit Points equal to the Hit Points of the form. "
            "The transformation also ends if you drop to 0 Hit Points or die. Your equipment can merge into the new form or be worn by it (your choice).\n\n"
            "Your game statistics are replaced by the stat block of the chosen form, but you retain your creature type; alignment; personality; "
            "Intelligence, Wisdom, and Charisma scores; Hit Points; Hit Point Dice; proficiencies; and ability to communicate. "
            "If the form has any legendary actions or lair actions, you can't use them.\n\n"
            "You retain the benefit of any features from your class, species, or other source and can use them if the new form is physically capable of doing so. "
            "You can't use any special senses unless the new form also has them. "
            "You can cast spells only if the new form can take the Speak action and can make any motions required to cast the spell."
        ),
    }
    
    updates["Time Stop"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You briefly stop the flow of time for everyone but yourself. No time passes for other creatures, while you take 1d4 + 1 turns in a row, "
            "during which you can use actions and move as normal.\n\n"
            "This spell ends if one of the actions you use during this period, or any effects that you create during it, affects a creature other than you "
            "or an object being worn or carried by someone other than you. In addition, the spell ends if you move to a place more than 1,000 feet from the location where you cast it."
        ),
    }
    
    updates["True Polymorph"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Choose one creature or nonmagical object that you can see within range. The creature shape-shifts into a different creature "
            "or a nonmagical object, or the object shape-shifts into a creature (the object must be neither combating you or your companions). "
            "The transformation lasts for the duration or until the target is reduced to 0 Hit Points or dies. "
            "If you concentrate on this spell for the full duration, the spell lasts until dispelled.\n\n"
            "An unwilling creature can make a Wisdom saving throw, and if it succeeds, it isn't affected by this spell.\n\n"
            "Creature into Creature. If you turn a creature into another kind of creature, the new form can be any kind you choose that has a Challenge Rating equal to or less than the target's Challenge Rating or level. "
            "The target's game statistics are replaced by the stat block of the new form, but it retains its alignment, personality, creature type, Hit Points, and Hit Point Dice. "
            "The target gains a number of Temporary Hit Points equal to the Hit Points of the new form. The target can't have legendary actions or lair actions.\n\n"
            "The target's equipment can merge into the new form or be worn by it (your choice). The target is limited in the actions it can perform by the nature of its new form, "
            "and it can't cast spells or communicate.\n\n"
            "Object into Creature. You can turn an object into any kind of creature if the creature's size is no larger than the object's size and the creature has a Challenge Rating of 9 or lower. "
            "The creature is Friendly to you and your allies. In combat, it takes its turn immediately after yours, and it obeys your commands. "
            "If you issue it no commands, the creature defends itself but takes no other actions. If the spell becomes permanent, you no longer control the creature.\n\n"
            "Creature into Object. If you turn a creature into an object, the target's equipment can merge into the new form or drop to the ground in its space (your choice). "
            "The creature's statistics become those of the object, and the creature has no memory of time spent in this form after the spell ends and it returns to its normal form."
        ),
    }
    
    updates["True Resurrection"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You touch a creature that has been dead for no longer than 200 years and that died for any reason except old age. "
            "The creature is revived with all its Hit Points.\n\n"
            "This spell closes all wounds, neutralizes any poison, cures all magical and nonmagical diseases, and lifts any curses affecting the creature when it died. "
            "The spell replaces damaged or missing organs and limbs. If the creature was Undead, it is restored to its non-Undead form.\n\n"
            "The spell can provide a new body if the original no longer exists, in which case you must speak the creature's name. The creature then appears in an unoccupied space you choose within 10 feet of you."
        ),
    }
    
    updates["Weird"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "You try to create illusory terrors in others' minds. Each creature of your choice in a 30-foot-radius Sphere centered on a point within range makes a Wisdom saving throw. "
            "On a failed save, a target takes 10d10 Psychic damage and has the Frightened condition for the duration. On a successful save, a target takes half as much damage only.\n\n"
            "A Frightened target makes a Wisdom saving throw at the end of each of its turns. On a failed save, it takes 5d10 Psychic damage. On a successful save, the spell ends on that target."
        ),
    }
    
    updates["Wish"] = {
        "source": "Player's Handbook (2024)",
        "description": (
            "Wish is the mightiest spell a mortal can cast. By simply speaking aloud, you can alter reality itself.\n\n"
            "The basic use of this spell is to duplicate any other spell of level 8 or lower. "
            "If you use it this way, you don't need to meet any requirements of that spell, including costly components. The spell simply takes effect.\n\n"
            "Alternatively, you can create one of the following effects of your choice:\n\n"
            "Object Creation. You create one object of up to 25,000 GP in value that isn't a magic item. "
            "The object can be no more than 300 feet in any dimension, and it appears in an unoccupied space that you can see on the ground.\n\n"
            "Instant Health. You allow yourself and up to twenty creatures that you can see to regain all Hit Points, and you end all effects on them listed in the Greater Restoration spell.\n\n"
            "Resistance. You grant up to ten creatures that you can see Resistance to one damage type that you choose. This Resistance is permanent.\n\n"
            "Spell Immunity. You grant up to ten creatures you can see immunity to a single spell or other magical effect for 8 hours.\n\n"
            "Sudden Learning. You replace one of your feats with another feat for which you are eligible. "
            "You lose all the benefits of the old feat and gain the benefits of the new one. You can't replace a feat that is a prerequisite for any of your other feats or features.\n\n"
            "Roll Redo. You undo a single recent event by forcing a reroll of any die roll made within the last round (including your last turn). "
            "Reality reshapes itself to accommodate the new result. For example, a Wish spell could undo an ally's failed saving throw or a foe's Critical Hit. "
            "You can force the reroll to be made with Advantage or Disadvantage (your choice), and you choose whether to use the reroll or the original roll.\n\n"
            "Reshape Reality. You may wish for something not included in any of the other effects. To do so, state your wish to the DM as precisely as possible. "
            "Be careful, for your DM has great latitude in ruling what occurs in such an instance; the greater the wish, the greater the likelihood that something goes wrong. "
            "This spell might simply fail, the effect you desire might be achieved only in part, or you might suffer an unforeseen consequence as a result of how you worded the wish. "
            "For example, wishing that a villain were dead might propel you forward in time to a period when that villain is no longer alive, "
            "effectively removing you from the game. Similarly, wishing for a legendary magic item or an Artifact might instantly transport you to the presence of the item's current owner. "
            "If your wish is granted and its effects have consequences for a whole community, region, or world, you are likely to attract the attention of powerful beings who are affected by your wish.\n\n"
            "The stress of casting Wish to produce any effect other than duplicating another spell weakens you. "
            "After enduring that stress, each time you cast a spell until you finish a Long Rest, you take 1d10 Necrotic damage per level of that spell. "
            "This damage can't be reduced or prevented in any way. In addition, your Strength becomes 3 for 2d4 days. For each of those days that you spend resting and doing nothing more than light activity, "
            "your remaining recovery time decreases by 2 days. Finally, there is a 33 percent chance you are unable to cast Wish ever again if you suffer this stress."
        ),
    }
    
    return updates


def update_spells_in_database():
    """Update all spells in the database with the correct descriptions."""
    db = SpellDatabase()
    updates = get_spell_updates()
    
    updated_count = 0
    not_found = []
    
    for spell_name, fields in updates.items():
        spell_id = db.get_spell_id_by_name(spell_name)
        
        if spell_id is None:
            not_found.append(spell_name)
            continue
        
        # Get current spell data
        spell_data = db.get_spell_by_id(spell_id)
        if spell_data is None:
            not_found.append(spell_name)
            continue
        
        # Update the fields - classes and tags are already in spell_data from get_spell_by_id
        updated_data = dict(spell_data)
        for field, value in fields.items():
            updated_data[field] = value
        
        # Update in database
        success = db.update_spell(spell_id, updated_data)
        if success:
            updated_count += 1
            print(f"Updated: {spell_name}")
        else:
            print(f"Failed to update: {spell_name}")
    
    print(f"\n=== Summary ===")
    print(f"Updated: {updated_count} spells")
    print(f"Not found: {len(not_found)} spells")
    if not_found:
        print("Spells not found in database:")
        for name in not_found:
            print(f"  - {name}")


if __name__ == "__main__":
    update_spells_in_database()
