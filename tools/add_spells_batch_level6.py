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
        name="Arcane Gate",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="500 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You create linked teleportation portals. Choose two Large, unoccupied spaces on the ground that you can see, one within range and the other within 10 feet of you. "
            "A circular portal opens in each space for the duration. The portals are open on only one side (your choice), and anything entering one exits the other as if adjacent. "
            "As a Bonus Action, you can change the facing of the open sides."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Blade Barrier",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Cleric"],
        description=(
            "You create a wall of whirling blades made of magical energy. The wall can be a straight line up to 100 feet long, 20 feet high, and 5 feet thick, or a ring up to 60 feet in diameter, 20 feet high, and 5 feet thick. "
            "The wall provides Three-Quarters Cover and is Difficult Terrain. Creatures in the wall’s space make a Dexterity saving throw, taking 6d10 Force damage on a failed save or half on a success. "
            "A creature also makes the save if it enters the wall’s space or ends its turn there (once per turn)."
        ),
        source="Player's Handbook",
        tags=["Evocation", "AOE", "Damage", "Force", "Saving Throw", "Defense"],
    ),
    make_spell(
        name="Chain Lightning",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (three silver pins)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You launch a lightning bolt toward a target you can see within range. Three bolts then leap from that target to as many as three other targets within 30 feet of the first. "
            "Each target makes a Dexterity saving throw, taking 10d8 Lightning damage on a failed save or half as much on a successful one. "
            "Using a Higher-Level Spell Slot. One additional bolt leaps for each slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Evocation", "Damage", "Lightning", "Saving Throw"],
    ),
    make_spell(
        name="Circle Of Death",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (the powder of a crushed black pearl worth 500+ GP)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "Negative energy ripples out in a 60-foot-radius Sphere from a point you choose within range. Each creature in that area makes a Constitution saving throw, "
            "taking 8d8 Necrotic damage on a failed save or half as much on a successful one. Using a Higher-Level Spell Slot. Damage increases by 2d8 per slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "AOE", "Damage", "Necrotic", "Saving Throw"],
    ),
    make_spell(
        name="Conjure Fey",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid"],
        description=(
            "You conjure a Medium spirit from the Feywild in an unoccupied space you can see within range. When it appears, you can make one melee spell attack against a creature within 5 feet of it; "
            "on a hit, the target takes 3d12 + your spellcasting ability modifier Psychic damage and has the Frightened condition until the start of your next turn. "
            "As a Bonus Action on later turns, you can teleport the spirit up to 30 feet and repeat the attack. Using a Higher-Level Spell Slot. Damage increases by 1d12 per slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Attack", "Damage", "Psychic", "Debuff"],
    ),
    make_spell(
        name="Contingency",
        level=6,
        casting_time="10 minutes",
        ritual=False,
        range_str="Self",
        components="V, S, M (a gem-encrusted statuette of yourself worth 1,500+ GP)",
        duration="10 days",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "Choose a spell of level 5 or lower that you can cast, has a casting time of an action, and can target you. You cast that spell as part of casting Contingency, expending slots for both, "
            "but the contingent spell takes effect when a described trigger occurs. The contingent spell only affects you. You can have only one Contingency at a time; casting it again ends a previous one."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Utility", "Buff"],
    ),
    make_spell(
        name="Create Undead",
        level=6,
        casting_time="1 minute",
        ritual=False,
        range_str="10 feet",
        components="V, S, M (one 150+ GP black onyx stone for each corpse)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric", "Warlock", "Wizard"],
        description=(
            "You can cast this spell only at night. Choose up to three corpses of Medium or Small Humanoids within range. Each one becomes a Ghoul under your control for 24 hours. "
            "You can command them as a Bonus Action while within 120 feet. Recasting before control ends reasserts control instead of animating new ones, with higher slots allowing more or stronger undead."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "Utility"],
    ),
    make_spell(
        name="Dirge",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Cleric"],
        description=(
            "Deathly power fills a 60-foot Emanation originating from you. Designate creatures to be unaffected. Other creatures can’t regain Hit Points while in the area. "
            "Whenever the area enters a creature’s space or a creature enters or ends its turn there, it makes a Constitution saving throw, taking 3d10 Necrotic damage and has the Prone condition on a failed save, or half damage and its Speed is halved on a success. "
            "A creature that fails also gains 1 Exhaustion level. Casting as a Circle Spell extends duration to 10 minutes with secondary casters expending level 4+ slots."
        ),
        source="Forgotten Realms - Heroes of Faerun",
        tags=["Enchantment", "AOE", "Damage", "Necrotic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Disintegrate",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a lodestone and dust)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You launch a green ray at a target you can see within range. The target makes a Dexterity saving throw, taking 10d6 + 40 Force damage on a failed save or half on a success. "
            "If reduced to 0 Hit Points by this damage, the target and nonmagical items it wears or carries are disintegrated into dust. Nonmagical objects Large or smaller are automatically disintegrated; larger objects lose a 10-foot cube. "
            "Using a Higher-Level Spell Slot. Damage increases by 3d6 per slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Damage", "Force", "Saving Throw"],
    ),
    make_spell(
        name="Drawmij's Instant Summons",
        level=6,
        casting_time="1 minute",
        ritual=True,
        range_str="Touch",
        components="V, S, M (a sapphire worth 1,000+ GP)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You touch a sapphire and an object weighing 10 pounds or less whose longest dimension is 6 feet or less, marking the object and inscribing its name on the sapphire. "
            "As a Magic action, you can speak the name and crush the sapphire: the object appears in your hand regardless of distance, or if carried by another, you learn who and where."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Elminster's Effulgent Spheres",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (an opal worth 1,000+ GP)",
        duration="1 hour",
        concentration=False,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "Six chromatic spheres orbit you. You can expend spheres for Absorb Energy (Reaction to gain Resistance to Acid, Cold, Fire, Lightning, or Thunder until your next turn) or Energy Blast (Bonus Action, ranged spell attack at a target within 120 feet for 3d6 damage of a chosen type). "
            "The spell ends early if no spheres remain. Using a Higher-Level Spell Slot. Spheres increase by 1 for each slot level above 6."
        ),
        source="Forgotten Realms - Heroes of Faerun",
        tags=["Evocation", "Damage", "Buff", "Defense", "Acid", "Cold", "Fire", "Lightning", "Thunder"],
    ),
    make_spell(
        name="Eyebite",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "For the duration, one creature within 60 feet that you can see must succeed on a Wisdom saving throw or suffer an effect you choose: Asleep (Unconscious), Panicked (Frightened and must Dash away), or Sickened (Poisoned). "
            "On each of your turns, you can target another creature, but not one that succeeded on a save against this casting."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Find the Path",
        level=6,
        casting_time="1 minute",
        ritual=False,
        range_str="Self",
        components="V, S, M (divination tools worth 100+ GP)",
        duration="1 day",
        concentration=True,
        class_names=["Bard", "Cleric", "Druid"],
        description=(
            "You sense the most direct physical route to a familiar location on the same plane, knowing distance and direction. At each choice, you know the most direct path. The spell fails for moving or unspecific destinations or those on other planes."
        ),
        source="Player's Handbook",
        tags=["Divination", "Utility"],
    ),
    make_spell(
        name="Flesh to Stone",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a cockatrice feather)",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You attempt to turn one creature you can see within range to stone. The target makes a Constitution saving throw. On a failed save, it is Restrained for the duration; on a success, its Speed is 0 until the start of your next turn. Constructs automatically succeed. "
            "A Restrained target repeats the save at the end of each turn; three successes end the spell, three failures Petrify the target. Maintaining Concentration for the full duration leaves the target Petrified until freed by magic such as Greater Restoration."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Forbiddance",
        level=6,
        casting_time="10 minutes",
        ritual=True,
        range_str="Touch",
        components="V, S, M (ruby dust worth 1,000+ GP)",
        duration="1 day",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "You ward up to 40,000 square feet of floor space to a height of 30 feet. Creatures can’t teleport into the area or use planar travel to enter. "
            "Choose creature types (Aberrations, Celestials, Elementals, Fey, Fiends, Undead); such creatures entering or ending their turn in the area take 5d10 Radiant or Necrotic damage (your choice). "
            "You can set a password to avoid the damage. Casting daily for 30 days makes the effect permanent."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Defense", "Utility", "Damage", "Radiant", "Necrotic", "AOE"],
    ),
    make_spell(
        name="Globe of Invulnerability",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a glass bead)",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "An immobile, shimmering barrier appears in a 10-foot Emanation around you. Any spell of level 5 or lower cast from outside cannot affect anything within. "
            "Using a Higher-Level Spell Slot. The barrier blocks spells of one level higher for each slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Defense"],
    ),
    make_spell(
        name="Guards and Wards",
        level=6,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (a silver rod worth 10+ GP)",
        duration="24 hours",
        concentration=False,
        class_names=["Bard", "Wizard"],
        description=(
            "You ward up to 2,500 square feet of floor space (up to 20 feet tall) with multiple effects: fog in corridors, illusory doors, Arcane Lock on doors, webs on stairs, and one additional effect (Dancing Lights, Magic Mouth, Stinking Cloud, Gust of Wind, or Suggestion). "
            "You can set friendly creatures and a password to ignore effects. Dispel Magic removes individual effects; all must be dispelled to end the spell. Casting daily for 365 days makes it last until dispelled."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Defense", "Utility"],
    ),
    make_spell(
        name="Harm",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "You unleash virulent magic on a creature you can see. The target makes a Constitution saving throw, taking 14d6 Necrotic damage on a failed save or half as much on a success, and its Hit Point maximum is reduced by the Necrotic damage taken (can’t drop below 1)."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "Damage", "Necrotic", "Saving Throw"],
    ),
    make_spell(
        name="Heal",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric", "Druid"],
        description=(
            "Choose a creature you can see within range. The target regains 70 Hit Points and ends the Blinded, Deafened, and Poisoned conditions. Using a Higher-Level Spell Slot. Healing increases by 10 for each slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Abjuration", "Healing", "Buff"],
    ),
    make_spell(
        name="Heroes' Feast",
        level=6,
        casting_time="10 minutes",
        ritual=False,
        range_str="Self",
        components="V, S, M (a gem-encrusted bowl worth 1,000+ GP, which the spell consumes)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Cleric", "Druid"],
        description=(
            "You conjure a feast for up to twelve creatures, taking 1 hour to consume. Benefits last 24 hours: Resistance to Poison damage; Immunity to Frightened and Poisoned; Hit Point maximum increases by 2d10 and the creature gains that many Hit Points."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Buff", "Healing", "Poison"],
    ),
    make_spell(
        name="Magic Jar",
        level=6,
        casting_time="1 minute",
        ritual=False,
        range_str="Self",
        components="V, S, M (a gem, crystal, or reliquary worth 500+ GP)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "Your soul leaves your body for the container used as the material component. From the container, you can attempt to possess a Humanoid within 100 feet (Charisma saving throw). "
            "On a failed save, your soul enters the target’s body and its soul is trapped in the container; on a success, the target resists and you can’t try again for 24 hours. "
            "You can return to your body with a Magic action while within 100 feet. If the host dies while possessed, you make a Charisma save to return to the container. Destroying the container ends the spell and frees souls as described."
        ),
        source="Player's Handbook",
        tags=["Necromancy", "Utility", "Debuff"],
    ),
    make_spell(
        name="Mass Suggestion",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, M (a snake’s tongue)",
        duration="24 hours",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Wizard"],
        description=(
            "You suggest a course of activity (25 words or fewer) to up to twelve creatures you can see within range that can hear and understand you. "
            "Each target makes a Wisdom saving throw or has the Charmed condition for the duration (or until harmed), pursuing the suggestion. Using a Higher-Level Spell Slot. Duration increases to 10 days (slot 7), 30 days (slot 8), or 366 days (slot 9)."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "Debuff", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Move Earth",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a miniature shovel)",
        duration="2 hours",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "Choose an area of dirt, sand, or clay no larger than 40 feet on a side within range. You reshape it over 10 minutes, raising, lowering, trenching, or forming pillars within half the area’s largest dimension. "
            "Every 10 minutes of Concentration, you can choose a new area. The spell doesn’t affect stone or plant growth, and terrain shifts accommodate structures (which might collapse if destabilized)."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Utility"],
    ),
    make_spell(
        name="Otiluke's Freezing Sphere",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="300 feet",
        components="V, S, M (a miniature crystal sphere)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "A frigid globe explodes in a 60-foot-radius Sphere at a point within range. Each creature there makes a Constitution saving throw, taking 10d6 Cold damage on a failed save or half on a success. "
            "If the globe strikes water, it freezes a 30-foot square 6 inches thick for 1 minute, potentially restraining swimmers (Strength check to break free). You can hold the unfired globe; it can be thrown 40 feet or slung, shattering with the spell’s effect; unused, it explodes after 1 minute. "
            "Using a Higher-Level Spell Slot. Damage increases by 1d6 per slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Evocation", "AOE", "Damage", "Cold", "Saving Throw"],
    ),
    make_spell(
        name="Otto's Irresistible Dance",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Wizard"],
        description=(
            "One creature you can see within range makes a Wisdom saving throw. On a success, it dances until the end of its next turn, spending all movement. "
            "On a failed save, the target is Charmed, must use all movement to dance, has Disadvantage on Dexterity saves and attack rolls, and others have Advantage on attacks against it. On each turn it can use an action to repeat the save, ending the spell on a success."
        ),
        source="Player's Handbook",
        tags=["Enchantment", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Planar Ally",
        level=6,
        casting_time="10 minutes",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "You beseech a known otherworldly entity for aid; it sends a Celestial, Elemental, or Fiend loyal to it to appear within range. The creature is not compelled—services are bargained for with payment appropriate to the task’s danger and duration. "
            "Tasks measured in minutes/hours/days typically cost 100 GP per minute, 1,000 GP per hour, or 10,000 GP per day (up to 10 days), adjusted by the DM. When service ends, the creature departs."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Programmed Illusion",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (jade dust worth 25+ GP)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Bard", "Wizard"],
        description=(
            "You create an illusion (object, creature, or visible phenomenon) within range that activates on a specified visual or audible trigger within 30 feet. The illusion (up to a 30-foot Cube) behaves and sounds as you script for up to 5 minutes, then disappears and resets after 10 minutes, ready to trigger again. "
            "Physical interaction reveals it; Study can discern it with an Intelligence (Investigation) check against your save DC."
        ),
        source="Player's Handbook",
        tags=["Illusion", "Utility"],
    ),
    make_spell(
        name="Summon Fiend",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (a bloody vial worth 600+ GP)",
        duration="1 hour",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "You call forth a fiendish spirit (Demon, Devil, or Yugoloth) using the Fiendish Spirit stat block. It appears in an unoccupied space within range, acts immediately after you on your Initiative, and obeys your verbal commands. "
            "If you issue none, it takes the Dodge action. The creature disappears at 0 Hit Points or when the spell ends. Using a Higher-Level Spell Slot. Use the slot’s level for the spell level in the stat block."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Damage", "Utility"],
    ),
    make_spell(
        name="Sunbeam",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a magnifying glass)",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Druid", "Sorcerer", "Wizard"],
        description=(
            "You launch a sunbeam in a 5-foot-wide, 60-foot-long Line. Each creature in the Line makes a Constitution saving throw, taking 6d8 Radiant damage and is Blinded until the start of your next turn on a failed save, or half damage only on a success. "
            "Until the spell ends, you can take a Magic action each turn to create a new line. A mote above you sheds Bright Light 30 feet and Dim Light 30 feet (sunlight)."
        ),
        source="Player's Handbook",
        tags=["Evocation", "AOE", "Damage", "Radiant", "Light", "Saving Throw"],
    ),
    make_spell(
        name="Tasha's Bubbling Cauldron",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="5 feet",
        components="V, S, M (a gilded ladle worth 500+ GP)",
        duration="10 minutes",
        concentration=False,
        class_names=["Warlock", "Wizard"],
        description=(
            "You conjure a claw-footed cauldron filled with bubbling liquid in an unoccupied space within 5 feet. It can’t be moved and vanishes with the spell. "
            "The liquid duplicates a Common or Uncommon potion you choose. As a Bonus Action, you or an ally can withdraw one potion (in a vial that disappears after use). The cauldron produces a number of potions equal to your spellcasting ability modifier (minimum 1); after the last, it disappears. Unused potions disappear when you cast this spell again."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Utility", "Healing"],
    ),
    make_spell(
        name="Transport via Plants",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="10 feet",
        components="V, S",
        duration="1 minute",
        concentration=False,
        class_names=["Druid"],
        description=(
            "You create a link between a Large or larger inanimate plant within range and another plant of the same kind on the same plane that you have seen or touched. "
            "For the duration, any creature can step into the target plant and exit the destination plant using 5 feet of movement."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="True Seeing",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S, M (mushroom powder worth 25+ GP, which the spell consumes)",
        duration="1 hour",
        concentration=False,
        class_names=["Bard", "Cleric", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "A willing creature you touch gains Truesight to 120 feet for the duration."
        ),
        source="Player's Handbook",
        tags=["Divination", "Utility"],
    ),
    make_spell(
        name="Wall of Ice",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a piece of quartz)",
        duration="10 minutes",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "You create a wall of ice: either a dome/globe of radius up to 10 feet or a flat surface of ten contiguous 10-foot squares, 1 foot thick. "
            "If the wall appears in a creature’s space, it is pushed to a side and makes a Dexterity saving throw, taking 10d6 Cold damage on a failed save or half on a success. The wall has AC 12 and 30 HP per 10-foot section (Immunity to Cold, Poison, Psychic; Vulnerable to Fire). "
            "Destroying a section leaves a sheet of frigid air; moving through it for the first time on a turn deals 5d6 Cold damage (Constitution save for half). Using a Higher-Level Spell Slot. Initial and frigid-air damage increase by 2d6 and 1d6 per slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Evocation", "AOE", "Damage", "Cold", "Saving Throw", "Defense"],
    ),
    make_spell(
        name="Wall of Thorns",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a handful of thorns)",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid"],
        description=(
            "You create a wall of tangled brush bristling with thorns up to 60 feet long, 10 feet high, 5 feet thick, or a 20-foot-diameter circle up to 20 feet high and 5 feet thick. The wall blocks sight. "
            "When it appears, each creature in its area makes a Dexterity saving throw, taking 7d8 Piercing damage on a failed save or half on a success. The wall is Difficult Terrain; moving through costs 4 feet per foot, and the first time a creature enters or ends its turn there each turn, it makes a Dexterity save, taking 7d8 Slashing damage on a failed save or half on success. Using a Higher-Level Spell Slot. Both damages increase by 1d8 per slot level above 6."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "AOE", "Damage", "Piercing", "Slashing", "Saving Throw", "DOT"],
    ),
    make_spell(
        name="Wind Walk",
        level=6,
        casting_time="1 minute",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (a candle)",
        duration="8 hours",
        concentration=False,
        class_names=["Druid"],
        description=(
            "You and up to ten willing creatures within range assume gaseous forms. In cloud form, a target has a Fly Speed of 300 feet, can hover, is immune to Prone, and has Resistance to Bludgeoning, Piercing, and Slashing damage. "
            "Actions are limited to Dash or a Magic action to begin reverting (takes 1 minute, target is Stunned during). Targets can revert to cloud form with another Magic action and 1-minute transformation. If flying when the spell ends, the target descends safely 60 feet per round for 1 minute before falling."
        ),
        source="Player's Handbook",
        tags=["Transmutation", "Utility", "Buff", "Defense"],
    ),
    make_spell(
        name="Word of Recall",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="5 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "You and up to five willing creatures within 5 feet instantly teleport to a previously designated sanctuary. Casting without a prepared sanctuary has no effect. You must designate the sanctuary by casting this spell there."
        ),
        source="Player's Handbook",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Bones of the Earth",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Druid"],
        description=(
            "You cause up to six stone pillars (5-foot diameter, up to 30 feet high) to burst from the ground within range. You can target ground under a Medium or smaller creature; it must make a Dexterity saving throw or be lifted by the pillar. "
            "If blocked by a ceiling, the creature on the pillar takes 6d6 bludgeoning damage and is Restrained between pillar and obstacle (Str/Dex check vs your save DC to end). Pillars have AC 5 and 30 HP; when destroyed, they crumble to rubble creating 10-foot-radius Difficult Terrain. Using a Higher-Level Spell Slot. Create two additional pillars per slot level above 6."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Damage", "Bludgeoning", "Debuff", "Saving Throw", "AOE"],
    ),
    make_spell(
        name="Create Homunculus",
        level=6,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (clay, ash, mandrake root consumed; jewel-encrusted dagger worth 1,000+ GP)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You cut yourself with a jewel-encrusted dagger, taking 2d4 piercing damage that can’t be reduced, then transform the components into a homunculus companion (see Monster Manual). "
            "You can have only one; casting while one lives fails. After each long rest with it on the same plane, you may spend up to half your Hit Dice, reducing your hit point maximum by the total plus Con modifiers and increasing the homunculus’s maximum and current hit points by the same (reduction ends next long rest or on homunculus’s death)."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Utility"],
    ),
    make_spell(
        name="Druid Grove",
        level=6,
        casting_time="10 minutes",
        ritual=False,
        range_str="Touch",
        components="V, S, M (mistletoe harvested with a golden sickle under a full moon, consumed)",
        duration="24 hours",
        concentration=False,
        class_names=["Druid"],
        description=(
            "You protect an outdoor or underground area (30- to 90-foot cube, excluding structures). Casting daily for a year makes it last until dispelled. You can name friends and a password to ignore effects. "
            "Effects include Solid Fog (heavily obscured, difficult terrain), Grasping Undergrowth (entangle-like), Grove Guardians (up to four animated trees acting as awakened trees without speech), and one additional effect (gust of wind, spike growth, wind wall). Dispel Magic can remove individual effects; all must be removed to end the spell."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Abjuration", "Defense", "Utility"],
    ),
    make_spell(
        name="Fizban's Platinum Shield",
        level=6,
        casting_time="Bonus Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a platinum-plated dragon scale worth 500+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You create a silvery field around a creature within range. It sheds Dim Light 5 feet and grants half cover, Resistance to acid, cold, fire, lightning, and poison damage, and Evasion against Dexterity saves for half damage (take none on success, half on failure). "
            "As a Bonus Action, you can move the field to another creature within 60 feet."
        ),
        source="Fizban's Treasury of Dragons",
        tags=["Abjuration", "Defense", "Buff", "Acid", "Cold", "Fire", "Lightning", "Poison"],
    ),
    make_spell(
        name="Gravity Fissure",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a fistful of iron filings)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You manifest a ravine of gravitational energy in a 100-foot-long, 5-foot-wide line from you. Each creature in the line makes a Constitution saving throw, taking 8d8 Force damage on a failed save or half on a success. "
            "Each creature within 10 feet of the line but not in it must also make a Constitution save or take 8d8 Force damage and be pulled into the line. Using a Higher-Level Spell Slot. Damage increases by 1d8 per slot level above 6."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Evocation", "AOE", "Damage", "Force", "Saving Throw"],
    ),
    make_spell(
        name="Investiture of Flame",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Flames wreathe you, shedding bright light 30 feet and dim light 30 more. You are immune to fire damage and have resistance to cold damage. "
            "Creatures that move within 5 feet of you for the first time on a turn or end there take 1d10 fire damage. As an action, you can create a 15-foot line of fire; creatures in it make a Dexterity saving throw, taking 4d8 fire damage on a failed save or half on success."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Defense", "Damage", "Fire", "Cold", "Saving Throw"],
    ),
    make_spell(
        name="Investiture of Ice",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Ice rimes your body. You are immune to cold damage and have resistance to fire damage. You ignore difficult terrain from ice or snow. Ground in a 10-foot radius around you is icy difficult terrain for others (moves with you). "
            "As an action, you create a 15-foot cone of freezing wind; creatures make a Constitution saving throw, taking 4d6 cold damage on a failed save or half on success; on a failed save, a creature’s speed is halved until the start of your next turn."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Defense", "Damage", "Cold", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Investiture of Stone",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Bits of rock cover you. You have resistance to bludgeoning, piercing, and slashing damage from nonmagical weapons. "
            "As an action, you create a small earthquake in a 15-foot radius centered on you; other creatures there must succeed on a Dexterity saving throw or be knocked prone. You can move through earth or stone as if it were air (without destabilizing it) but can’t end movement inside; otherwise you are ejected, the spell ends, and you are stunned until end of your next turn."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Defense", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Investiture of Wind",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Wind whirls around you. Ranged weapon attacks against you have Disadvantage. You gain a flying speed of 60 feet (you fall when the spell ends if still airborne). "
            "As an action, you create a 15-foot cube of swirling wind within 60 feet; creatures in it make a Constitution saving throw, taking 2d10 bludgeoning damage on a failed save or half on success; Large or smaller creatures that fail are pushed up to 10 feet from the cube’s center."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Defense", "Damage", "Bludgeoning", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Mental Prison",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="S",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You bind a creature you can see within range in an illusory cell. The target makes an Intelligence saving throw (auto success if immune to charmed). On a success, it takes 5d10 psychic damage and the spell ends. "
            "On a failed save, it takes 5d10 psychic damage and is Restrained, perceiving only the illusion. If it is moved out of the illusion, makes a melee attack through it, or reaches through it, it takes 10d10 psychic damage and the spell ends."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Illusion", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Primordial Ward",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Druid"],
        description=(
            "You have resistance to acid, cold, fire, lightning, and thunder damage for the duration. When you take one of those damage types, you can use your reaction to gain immunity to it (including the triggering damage), ending the resistances and granting immunity until the end of your next turn, after which the spell ends."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Abjuration", "Defense", "Buff"],
    ),
    make_spell(
        name="Scatter",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "Up to five creatures you can see within range are teleported to unoccupied spaces you can see within 120 feet (on the ground). Unwilling creatures must succeed on a Wisdom saving throw to resist."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "Utility", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Soul Cage",
        level=6,
        casting_time="Reaction",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a tiny silver cage worth 100 GP)",
        duration="8 hours",
        concentration=False,
        class_names=["Warlock", "Wizard"],
        description=(
            "When a Humanoid dies within 60 feet, you snatch its soul into a tiny cage. The soul remains trapped until the spell ends or the cage is destroyed. While you have a soul, you can exploit it up to six times: Steal Life (Bonus Action, regain 2d8 HP), Query Soul (ask a question, brief truthful answer), Borrow Experience (Bonus Action, gain Advantage on next roll before your next turn), Eyes of the Dead (Action, create a sensor at a place the humanoid saw, as Concentration up to 10 minutes). After six uses, the soul is released."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Necromancy", "Utility", "Healing"],
    ),
    make_spell(
        name="Tasha's Otherworldly Guise",
        level=6,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (an object engraved with a symbol of the Outer Planes worth 500+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You draw on Lower or Upper Planes. Benefits: immunity to fire and poison damage and the poisoned condition (Lower) or immunity to radiant and necrotic damage and the charmed condition (Upper); spectral wings for 40-foot fly speed; +2 AC; weapon attacks are magical and can use your spellcasting ability for attack/damage; you can Attack twice when you take the Attack action."
        ),
        source="Tasha's Cauldron of Everything",
        tags=["Transmutation", "Buff", "Defense", "Fire", "Poison", "Radiant", "Necrotic", "Attack"],
    ),
    make_spell(
        name="Tenser's Transformation",
        level=6,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a few hairs from a bull)",
        duration="10 minutes",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "You endow yourself with martial prowess and cannot cast spells. You gain 50 temporary Hit Points; Advantage on attack rolls with simple and martial weapons; weapon hits deal +2d12 force damage; proficiency with all armor, shields, simple and martial weapons; proficiency in Strength and Constitution saves; and you can Attack twice when you take the Attack action (ignore if you already can). "
            "When the spell ends, you must succeed on a DC 15 Constitution saving throw or suffer one level of exhaustion."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Attack", "Damage", "Force", "Temp HP", "Saving Throw"],
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