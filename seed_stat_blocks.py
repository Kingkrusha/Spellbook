"""
Seed script for official D&D 5e summoning spell stat blocks.
This script populates the database with the official stat blocks for summoning spells.
Run once or call seed_stat_blocks() from main.py during first run.
"""

from typing import Optional
from database import SpellDatabase
from stat_block import StatBlock, StatBlockFeature, AbilityScores


def get_official_stat_blocks():
    """Return a list of (spell_name, stat_block) tuples for official summoning spells."""
    
    stat_blocks = []
    
    # 2. Bestial Spirit (Summon Beast)
    stat_blocks.append(("Summon Beast", StatBlock(
        name="Bestial Spirit",
        size="Small",
        creature_type="Beast",
        creature_subtype="",
        alignment="Unaligned",
        armor_class="11 + the level of the spell (natural armor)",
        hit_points="20 (Air only) or 30 (Land and Water only) + 5 for each spell level above 2nd",
        speed="30 ft.; climb 30 ft. (Land only); fly 60 ft. (Air only); swim 30 ft. (Water only)",
        abilities=AbilityScores.from_scores(18, 11, 16, 4, 14, 5),
        senses="darkvision 60 ft., passive Perception 12",
        languages="understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Flyby (Air Only)", description="The beast doesn't provoke opportunity attacks when it flies out of an enemy's reach."),
            StatBlockFeature(name="Pack Tactics (Land and Water Only)", description="The beast has advantage on an attack roll against a creature if at least one of the beast's allies is within 5 feet of the creature and the ally isn't incapacitated."),
            StatBlockFeature(name="Water Breathing (Water Only)", description="The beast can breathe only underwater.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The beast makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Maul", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d8 + 4 + the spell's level piercing damage.")
        ]
    )))
    
    # 3. Find Greater Steed (Otherworldly Steed)
    stat_blocks.append(("Find Greater Steed", StatBlock(
        name="Otherworldly Steed",
        size="Large",
        creature_type="Celestial, Fey, or Fiend",
        creature_subtype="your choice",
        alignment="Neutral",
        armor_class="10 + 1 + the level of the spell (natural armor)",
        hit_points="5 + 10 for each spell level above 2nd (the steed has a number of Hit Dice [d10s] equal to the spell's level)",
        speed="60 ft.; fly 60 ft. (requires spell level 4+)",
        abilities=AbilityScores.from_scores(18, 12, 14, 6, 12, 8),
        senses="passive Perception 11",
        languages="understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Life Bond", description="When you regain hit points from a spell of 1st level or higher, the steed regains the same number of hit points if you're within 5 feet of it.")
        ],
        actions=[
            StatBlockFeature(name="Maul", description="Melee Weapon Attack: your spell attack modifier to hit (with advantage), reach 5 ft., one target. Hit: 1d8 + 4 + the spell's level bludgeoning, piercing, or slashing damage (your choice)."),
            StatBlockFeature(name="Otherworldly Slam (Requires Spell Level 4+)", description="Melee Spell Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 2d12 + the spell's level radiant, psychic, or necrotic damage (your choice based on creature type).")
        ]
    )))
    
    # 4. Fey Spirit (Summon Fey)
    stat_blocks.append(("Summon Fey", StatBlock(
        name="Fey Spirit",
        size="Small",
        creature_type="Fey",
        alignment="Unaligned",
        armor_class="12 + the level of the spell (natural armor)",
        hit_points="30 + 10 for each spell level above 3rd",
        speed="40 ft.",
        abilities=AbilityScores.from_scores(13, 16, 14, 14, 11, 16),
        condition_immunities="charmed",
        senses="darkvision 60 ft., passive Perception 10",
        languages="Sylvan, understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Fey Step", description="As a bonus action, the fey can magically teleport up to 30 feet to an unoccupied space it can see.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The fey makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Shortsword", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d6 + 3 + the spell's level piercing damage + 1d6 force damage.")
        ],
        bonus_actions=[
            StatBlockFeature(name="Fey Step", description="The fey magically teleports up to 30 feet to an unoccupied space it can see.")
        ]
    )))
    
    # 5. Undead Spirit (Summon Undead)
    stat_blocks.append(("Summon Undead", StatBlock(
        name="Undead Spirit",
        size="Medium",
        creature_type="Undead",
        alignment="Unaligned",
        armor_class="11 + the level of the spell (natural armor)",
        hit_points="30 + 10 for each spell level above 3rd",
        speed="30 ft.; fly 40 ft. (hover, Ghostly only)",
        abilities=AbilityScores.from_scores(12, 16, 15, 4, 10, 9),
        damage_immunities="necrotic, poison",
        condition_immunities="exhaustion, frightened, paralyzed, poisoned",
        senses="darkvision 60 ft., passive Perception 10",
        languages="understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Festering Aura (Putrid Only)", description="Any creature, other than you, that starts its turn within 5 feet of the spirit must succeed on a Constitution saving throw against your spell save DC or be poisoned until the start of its next turn."),
            StatBlockFeature(name="Incorporeal Passage (Ghostly Only)", description="The spirit can move through other creatures and objects as if they were difficult terrain. If it ends its turn inside an object, it is shunted to the nearest unoccupied space and takes 1d10 force damage for every 5 feet traveled.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The spirit makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Deathly Touch (Ghostly Only)", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d8 + 3 + the spell's level necrotic damage, and the creature must succeed on a Wisdom saving throw against your spell save DC or be frightened of the undead until the end of the target's next turn."),
            StatBlockFeature(name="Grave Bolt (Skeletal Only)", description="Ranged Spell Attack: your spell attack modifier to hit, range 150 ft., one target. Hit: 2d4 + 3 + the spell's level necrotic damage."),
            StatBlockFeature(name="Rotting Claw (Putrid Only)", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d6 + 3 + the spell's level slashing damage. If the target is poisoned, it must succeed on a Constitution saving throw against your spell save DC or be paralyzed until the end of its next turn.")
        ]
    )))
    
    # 6. Shadow Spirit (Summon Shadowspawn)
    stat_blocks.append(("Summon Shadowspawn", StatBlock(
        name="Shadow Spirit",
        size="Medium",
        creature_type="Monstrosity",
        alignment="Unaligned",
        armor_class="11 + the level of the spell (natural armor)",
        hit_points="35 + 15 for each spell level above 3rd",
        speed="40 ft.",
        abilities=AbilityScores.from_scores(13, 16, 15, 4, 10, 16),
        damage_resistances="necrotic",
        condition_immunities="frightened",
        senses="darkvision 120 ft., passive Perception 10",
        languages="understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Terror Frenzy (Fury Only)", description="The spirit has advantage on attack rolls against frightened creatures."),
            StatBlockFeature(name="Weight of Sorrow (Despair Only)", description="Any creature, other than you, that starts its turn within 5 feet of the spirit has its speed reduced by 20 feet until the start of that creature's next turn.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The spirit makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Chilling Rend", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d12 + 3 + the spell's level cold damage."),
            StatBlockFeature(name="Dreadful Scream (1/Day)", description="The spirit screams. Each creature within 30 feet of it must succeed on a Wisdom saving throw against your spell save DC or be frightened for 1 minute. The frightened creature can repeat the saving throw at the end of each of its turns, ending the effect on itself on a success.")
        ],
        bonus_actions=[
            StatBlockFeature(name="Shadow Stealth (Fear Only)", description="While in dim light or darkness, the spirit takes the Hide action.")
        ]
    )))
    
    # 7. Giant Insect (Giant Insect spell)
    stat_blocks.append(("Giant Insect", StatBlock(
        name="Giant Insect",
        size="Large",
        creature_type="Beast",
        alignment="Unaligned",
        armor_class="11 + the level of the spell (natural armor)",
        hit_points="30 + 10 for each spell level above 4th",
        speed="40 ft.; climb 40 ft.; fly 60 ft. (Wasp only)",
        abilities=AbilityScores.from_scores(17, 13, 15, 4, 14, 3),
        senses="darkvision 60 ft., passive Perception 12",
        languages="understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Spider Climb (Centipede and Spider Only)", description="The insect can climb difficult surfaces, including upside down on ceilings, without needing to make an ability check.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The insect makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Poison Jab", description="Melee Weapon Attack: your spell attack modifier to hit, reach 10 ft., one target. Hit: 1d6 + 3 + the spell's level piercing damage plus 1d4 poison damage.")
        ]
    )))
    
    # 8. Aberrant Spirit (Summon Aberration)
    stat_blocks.append(("Summon Aberration", StatBlock(
        name="Aberrant Spirit",
        size="Medium",
        creature_type="Aberration",
        alignment="Unaligned",
        armor_class="11 + the level of the spell (natural armor)",
        hit_points="40 + 10 for each spell level above 4th",
        speed="30 ft.; fly 30 ft. (hover, Star Spawn only)",
        abilities=AbilityScores.from_scores(16, 10, 17, 17, 10, 6),
        damage_immunities="psychic",
        senses="darkvision 60 ft., passive Perception 10",
        languages="Deep Speech, understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Regeneration (Slaad Only)", description="The aberration regains 5 hit points at the start of its turn if it has at least 1 hit point."),
            StatBlockFeature(name="Whispering Aura (Star Spawn Only)", description="At the start of each of the aberration's turns, each creature within 5 feet of the aberration must succeed on a Wisdom saving throw against your spell save DC or take 2d6 psychic damage, provided that the aberration isn't incapacitated.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The aberration makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Claws (Beholderkin Only)", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d8 + 3 + the spell's level slashing damage. If the target is a creature, it can't take reactions until the start of its next turn."),
            StatBlockFeature(name="Slam", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d8 + 3 + the spell's level bludgeoning damage."),
            StatBlockFeature(name="Eye Ray (Beholderkin Only)", description="Ranged Spell Attack: your spell attack modifier to hit, range 150 ft., one target. Hit: 1d8 + 3 + the spell's level psychic damage.")
        ]
    )))
    
    # 9. Construct Spirit (Summon Construct)
    stat_blocks.append(("Summon Construct", StatBlock(
        name="Construct Spirit",
        size="Medium",
        creature_type="Construct",
        alignment="Unaligned",
        armor_class="13 + the level of the spell (natural armor)",
        hit_points="40 + 15 for each spell level above 4th",
        speed="30 ft.",
        abilities=AbilityScores.from_scores(18, 10, 18, 14, 11, 5),
        damage_resistances="poison",
        condition_immunities="charmed, exhaustion, frightened, incapacitated, paralyzed, petrified, poisoned",
        senses="darkvision 60 ft., passive Perception 10",
        languages="understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Heated Body (Metal Only)", description="A creature that touches the construct or hits it with a melee attack while within 5 feet of it takes 1d10 fire damage."),
            StatBlockFeature(name="Stony Lethargy (Stone Only)", description="When a creature the construct can see starts its turn within 10 feet of the construct, the construct can force it to make a Wisdom saving throw against your spell save DC. On a failed save, the target can't use reactions and its speed is halved until the start of its next turn.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The construct makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Slam", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d8 + 4 + the spell's level bludgeoning damage.")
        ],
        reactions=[
            StatBlockFeature(name="Berserk Lashing (Clay Only)", description="When the construct takes damage, it makes a slam attack against a random creature within 5 feet of it. If no creature is within reach, the construct moves up to half its speed toward an enemy it can see, without provoking opportunity attacks.")
        ]
    )))
    
    # 10. Elemental Spirit (Summon Elemental)
    stat_blocks.append(("Summon Elemental", StatBlock(
        name="Elemental Spirit",
        size="Medium",
        creature_type="Elemental",
        alignment="Unaligned",
        armor_class="11 + the level of the spell (natural armor)",
        hit_points="50 + 10 for each spell level above 4th",
        speed="40 ft.; burrow 40 ft. (Earth only); fly 40 ft. (hover, Air only); swim 40 ft. (Water only)",
        abilities=AbilityScores.from_scores(18, 15, 17, 4, 10, 16),
        damage_resistances="acid (Water only); lightning and thunder (Air only); piercing and slashing (Earth only)",
        damage_immunities="poison; fire (Fire only)",
        condition_immunities="exhaustion, paralyzed, petrified, poisoned, unconscious",
        senses="darkvision 60 ft., passive Perception 10",
        languages="Primordial, understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Amorphous Form (Air, Fire, and Water Only)", description="The elemental can move through a space as narrow as 1 inch wide without squeezing.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The elemental makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Slam", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d10 + 4 + the spell's level bludgeoning damage (Air, Earth, and Water only) or fire damage (Fire only).")
        ]
    )))
    
    # 11. Reaper Spirit (Spirit of Death)
    stat_blocks.append(("Spirit of Death", StatBlock(
        name="Reaper Spirit",
        size="Medium",
        creature_type="Undead",
        alignment="Neutral",
        armor_class="11 + the level of the spell (natural armor)",
        hit_points="40 + 10 for each spell level above 4th",
        speed="30 ft.; fly 30 ft. (hover)",
        abilities=AbilityScores.from_scores(16, 16, 16, 16, 16, 16),
        damage_immunities="necrotic, poison",
        condition_immunities="charmed, exhaustion, frightened, grappled, paralyzed, petrified, poisoned, prone, restrained, unconscious",
        senses="darkvision 60 ft., passive Perception 13",
        languages="understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Incorporeal Movement", description="The reaper can move through other creatures and objects as if they were difficult terrain. It takes 5 (1d10) force damage if it ends its turn inside an object."),
            StatBlockFeature(name="Harvester of Death", description="The reaper appears to target one creature you can see within 60 feet of you when you cast the spell. The target must succeed on a Wisdom saving throw against your spell save DC or be frightened of the reaper until the spell ends. At the start of each of its turns, the frightened target can repeat the saving throw, ending the effect on a success. If the target's saving throw is successful, the target is immune to this reaper's Harvester of Death for 24 hours.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The reaper makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Reaping Scythe", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d10 + 3 + the spell's level necrotic damage. If the target is frightened of the reaper, it takes an extra 1d12 necrotic damage and the reaper regains hit points equal to half the extra damage dealt.")
        ]
    )))
    
    # 12. Celestial Spirit (Summon Celestial)
    stat_blocks.append(("Summon Celestial", StatBlock(
        name="Celestial Spirit",
        size="Large",
        creature_type="Celestial",
        alignment="Unaligned",
        armor_class="11 + the level of the spell (natural armor, Defender only) or 13 + the level of the spell (natural armor, Avenger only)",
        hit_points="40 + 10 for each spell level above 5th",
        speed="30 ft.; fly 40 ft.",
        abilities=AbilityScores.from_scores(16, 14, 16, 10, 14, 16),
        damage_resistances="radiant",
        condition_immunities="charmed, frightened",
        senses="darkvision 60 ft., passive Perception 12",
        languages="Celestial, understands the languages you speak",
        challenge_rating="—",
        actions=[
            StatBlockFeature(name="Multiattack", description="The celestial makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Radiant Bow (Avenger Only)", description="Ranged Weapon Attack: your spell attack modifier to hit, range 150/600 ft., one target. Hit: 2d6 + 2 + the spell's level radiant damage."),
            StatBlockFeature(name="Radiant Mace (Defender Only)", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d10 + 3 + the spell's level radiant damage, and the celestial can choose itself or another creature it can see within 10 feet of the target. The chosen creature gains 1d10 temporary hit points."),
            StatBlockFeature(name="Healing Touch (1/Day)", description="The celestial touches another creature. The target magically regains hit points equal to 2d8 + the spell's level.")
        ]
    )))
    
    # 13. Draconic Spirit (Summon Dragon)
    stat_blocks.append(("Summon Dragon", StatBlock(
        name="Draconic Spirit",
        size="Large",
        creature_type="Dragon",
        alignment="Neutral",
        armor_class="14 + the level of the spell (natural armor)",
        hit_points="50 + 10 for each spell level above 5th",
        speed="30 ft.; fly 60 ft.; swim 30 ft.",
        abilities=AbilityScores.from_scores(19, 14, 17, 10, 14, 14),
        damage_resistances="acid, cold, fire, lightning, poison (matching dragon type)",
        senses="blindsight 30 ft., darkvision 60 ft., passive Perception 12",
        languages="Draconic, understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Shared Resistances", description="When you summon the dragon, choose one of its damage resistances. You have resistance to the chosen damage type until the spell ends.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The dragon makes a number of Rend attacks equal to half the spell's level (rounded down), and it uses Breath Weapon."),
            StatBlockFeature(name="Rend", description="Melee Weapon Attack: your spell attack modifier to hit, reach 10 ft., one target. Hit: 1d6 + 4 + the spell's level piercing damage."),
            StatBlockFeature(name="Breath Weapon", description="The dragon exhales destructive energy in a 30-foot cone (Chromatic only) or 60-foot line that is 5 feet wide (Gem or Metallic only). Each creature in that area must make a Dexterity saving throw (Chromatic or Metallic) or Intelligence saving throw (Gem) against your spell save DC. On a failed save, a creature takes 2d6 damage of a type this dragon has resistance to. On a successful save, it takes half as much damage.")
        ]
    )))
    
    # 14. Fiendish Spirit (Summon Fiend)
    stat_blocks.append(("Summon Fiend", StatBlock(
        name="Fiendish Spirit",
        size="Large",
        creature_type="Fiend",
        alignment="Unaligned",
        armor_class="12 + the level of the spell (natural armor)",
        hit_points="50 + 15 for each spell level above 6th",
        speed="40 ft.; climb 40 ft. (Demon only); fly 60 ft. (Devil only)",
        abilities=AbilityScores.from_scores(13, 16, 15, 10, 10, 16),
        damage_resistances="fire",
        damage_immunities="poison",
        condition_immunities="poisoned",
        senses="darkvision 60 ft., passive Perception 10",
        languages="Abyssal, Infernal, understands the languages you speak",
        challenge_rating="—",
        traits=[
            StatBlockFeature(name="Death Throes (Demon Only)", description="When the fiend drops to 0 hit points or the spell ends, the fiend explodes, and each creature within 10 feet of it must make a Dexterity saving throw against your spell save DC. A creature takes 2d10 + this spell's level fire damage on a failed save, or half as much damage on a successful one."),
            StatBlockFeature(name="Devil's Sight (Devil Only)", description="Magical darkness doesn't impede the fiend's darkvision."),
            StatBlockFeature(name="Magic Resistance", description="The fiend has advantage on saving throws against spells and other magical effects.")
        ],
        actions=[
            StatBlockFeature(name="Multiattack", description="The fiend makes a number of attacks equal to half this spell's level (rounded down)."),
            StatBlockFeature(name="Bite (Demon Only)", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d12 + 3 + the spell's level necrotic damage."),
            StatBlockFeature(name="Claws (Yugoloth Only)", description="Melee Weapon Attack: your spell attack modifier to hit, reach 5 ft., one target. Hit: 1d8 + 3 + the spell's level slashing damage. Immediately after the attack hits or misses, the fiend can magically teleport up to 30 feet to an unoccupied space it can see."),
            StatBlockFeature(name="Hurl Flame (Devil Only)", description="Ranged Spell Attack: your spell attack modifier to hit, range 150 ft., one target. Hit: 2d6 + 3 + the spell's level fire damage. If the target is a flammable object that isn't being worn or carried, it also catches fire.")
        ]
    )))
    
    return stat_blocks


def seed_stat_blocks(db: Optional[SpellDatabase] = None):
    """Seed the database with official stat blocks. Returns number of stat blocks added."""
    if db is None:
        db = SpellDatabase()
    
    stat_blocks = get_official_stat_blocks()
    added_count = 0
    
    for spell_name, stat_block in stat_blocks:
        # Get the spell ID
        spell_id = db.get_spell_id_by_name(spell_name)
        
        if spell_id is None:
            print(f"Warning: Spell '{spell_name}' not found in database, skipping stat block '{stat_block.name}'")
            continue
        
        # Check if this stat block already exists for this spell
        existing = db.get_stat_blocks_for_spell(spell_id)
        if any(sb['name'] == stat_block.name for sb in existing):
            print(f"Stat block '{stat_block.name}' already exists for '{spell_name}', skipping")
            continue
        
        # Insert the stat block
        stat_block_dict = stat_block.to_dict()
        stat_block_dict['spell_id'] = spell_id
        
        try:
            db.insert_stat_block(stat_block_dict)
            added_count += 1
            print(f"Added stat block '{stat_block.name}' for spell '{spell_name}'")
        except Exception as e:
            print(f"Error adding stat block '{stat_block.name}' for '{spell_name}': {e}")
    
    return added_count


if __name__ == "__main__":
    print("Seeding official stat blocks...")
    count = seed_stat_blocks()
    print(f"\nDone! Added {count} stat blocks.")
