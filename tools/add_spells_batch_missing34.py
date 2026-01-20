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
    num = "".join(ch for ch in text if ch.isdigit())
    return int(num) if num else 0


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
        name="Antagonize",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (a playing card depicting a rogue)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "You whisper magical words that antagonize one creature of your choice within range. "
            "The target must make a Wisdom saving throw. On a failed save, the target takes 4d4 psychic damage and must immediately use its reaction to make a melee attack against another creature of your choice that you can see. "
            "If the target can’t make this attack (for example, because there is no one within its reach or because its reaction is unavailable), the target instead has disadvantage on the next attack roll it makes before the start of your next turn. "
            "On a successful save, the target takes half as much damage only.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d4 for each slot level above 3rd."
        ),
        source="The Book of Many Things",
        tags=["Enchantment", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Catnap",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="S, M (a pinch of sand)",
        duration="10 minutes",
        concentration=False,
        class_names=["Artificer", "Bard", "Sorcerer", "Wizard"],
        description=(
            "You make a calming gesture, and up to three willing creatures of your choice that you can see within range fall unconscious for the spell’s duration. "
            "The spell ends on a target early if it takes damage or someone uses an action to shake or slap it awake. "
            "If a target remains unconscious for the full duration, that target gains the benefit of a short rest, and it can’t be affected by this spell again until it finishes a long rest."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Enchantment", "Utility"],
    ),
    make_spell(
        name="Erupting Earth",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a piece of obsidian)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "Choose a point you can see on the ground within range. A fountain of churned earth and stone erupts in a 20-foot cube centered on that point. "
            "Each creature in that area must make a Dexterity saving throw. A creature takes 3d12 bludgeoning damage on a failed save, or half as much damage on a successful one. "
            "Additionally, the ground in that area becomes difficult terrain until cleared away. Each 5-foot-square portion of the area requires at least 1 minute to clear by hand.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d12 for each slot level above 3rd."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "AOE", "Bludgeoning", "Damage", "Saving Throw"],
    ),
    make_spell(
        name="Galder's Tower",
        level=3,
        casting_time="10 minutes",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (a fragment of stone, wood, or other building material)",
        duration="24 hours",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You conjure a two-story tower made of stone, wood, or similar suitably sturdy materials. The tower can be round or square in shape. "
            "Each level of the tower is 10 feet tall and has an area of up to 100 square feet. Access between levels consists of a simple ladder and hatch. "
            "Each level takes one of the following forms, chosen by you when you cast the spell:\n\n"
            "A bedroom with a bed, chairs, chest, and magical fireplace\n"
            "A study with desks, books, bookshelves, parchments, ink, and ink pens\n"
            "A dining space with a table, chairs, magical fireplace, containers, and cooking utensils\n"
            "A lounge with couches, armchairs, side tables and footstools\n"
            "A washroom with toilets, washtubs, a magical brazier, and sauna benches\n"
            "An observatory with a telescope and maps of the night sky\n"
            "An unfurnished, empty room\n\n"
            "The interior of the tower is warm and dry, regardless of conditions outside. Any equipment or furnishings conjured with the tower dissipate into smoke if removed from it. "
            "At the end of the spell’s duration, all creatures and objects within the tower that were not created by the spell appear safely outside on the ground, and all traces of the tower and its furnishings disappear.\n\n"
            "You can cast this spell again while it is active to maintain the tower’s existence for another 24 hours. "
            "You can create a permanent tower by casting this spell in the same location and with the same configuration every day for one year.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, the tower can have one additional story for each slot level beyond 3rd."
        ),
        source="Lost Laboratory of Kwalish",
        tags=["Conjuration", "Utility", "Defense"],
    ),
    make_spell(
        name="Incite Greed",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (a gem worth at least 50 gp)",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "When you cast this spell, you present the gem used as the material component and choose any number of creatures within range that can see you. "
            "Each target must succeed on a Wisdom saving throw or be charmed by you until the spell ends, or until you or your companions do anything harmful to it. "
            "While charmed in this way, a creature can do nothing but use its movement to approach you in a safe manner. While an affected creature is within 5 feet of you, it cannot move, but simply stares greedily at the gem you present.\n\n"
            "At the end of each of its turns, an affected target can make a Wisdom saving throw. If it succeeds, this effect ends for that target."
        ),
        source="Acquisitions Inc.",
        tags=["Enchantment", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Intellect Fortress",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V",
        duration="1 hour",
        concentration=True,
        class_names=["Artificer", "Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "For the duration, you or one willing creature you can see within range has resistance to psychic damage, as well as advantage on Intelligence, Wisdom, and Charisma saving throws.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, you can target one additional creature for each slot level above 3rd. "
            "The creatures must be within 30 feet of each other when you target them."
        ),
        source="Tasha's Cauldron of Everything",
        tags=["Abjuration", "Buff", "Defense", "Psychic"],
    ),
    make_spell(
        name="Life Transference",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric", "Wizard"],
        description=(
            "You sacrifice some of your health to mend another creature’s injuries. "
            "You take 4d8 necrotic damage, which can’t be reduced in any way, and one creature of your choice that you can see within range regains a number of hit points equal to twice the necrotic damage you take.\n\n"
            "At Higher Levels: When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d8 for each slot level above 3rd."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Necromancy", "Healing", "Necrotic"],
    ),
    make_spell(
        name="Melf's Minute Meteors",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (niter, sulfur, and pine tar formed into a bead)",
        duration="10 minutes",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You create six tiny meteors in your space. They float in the air and orbit you for the spell’s duration. "
            "When you cast the spell — and as a bonus action on each of your turns thereafter — you can expend one or two of the meteors, sending them streaking toward a point or points you choose within 120 feet of you. "
            "Once a meteor reaches its destination or impacts against a solid surface, the meteor explodes. "
            "Each creature within 5 feet of the point where the meteor explodes must make a Dexterity saving throw. "
            "A creature takes 2d6 fire damage on a failed save, or half as much damage on a successful one.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, the number of meteors created increases by two for each slot level above 3rd."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "Damage", "Fire", "AOE", "Saving Throw"],
    ),
    make_spell(
        name="Motivational Speech",
        level=3,
        casting_time="1 minute",
        ritual=False,
        range_str="60 feet",
        components="V",
        duration="1 hour",
        concentration=False,
        class_names=["Bard", "Cleric"],
        description=(
            "Choose up to five creatures within range that can hear you. For the duration, each affected creature gains 5 temporary hit points and has advantage on Wisdom saving throws. "
            "If an affected creature is hit by an attack, it has advantage on the next attack roll it makes. "
            "Once an affected creature loses the temporary hit points granted by this spell, the spell ends for that creature.\n\n"
            "At Higher Levels: When you cast this spell using a spell slot of 4th level or higher, the temporary hit points increase by 5 for each slot level above 3rd."
        ),
        source="Acquisitions Inc.",
        tags=["Enchantment", "Buff", "Temp HP"],
    ),
    make_spell(
        name="Pulse Wave",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You create intense pressure, unleash it in a 30-foot cone, and decide whether the pressure pulls or pushes creatures and objects. "
            "Each creature in that cone must make a Constitution saving throw. "
            "A creature takes 6d6 force damage on a failed save, or half as much damage on a successful one. "
            "And every creature that fails the save is either pulled 15 feet toward you or pushed 15 feet away from you, depending on the choice you made for the spell.\n\n"
            "In addition, unsecured objects that are completely within the cone are likewise pulled or pushed 15 feet.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d6 and the distance pulled or pushed increases by 5 feet for each slot level above 3rd."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Evocation", "Damage", "Force", "AOE", "Saving Throw"],
    ),
    make_spell(
        name="Spirit Shroud",
        level=3,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Paladin", "Warlock", "Wizard"],
        description=(
            "You call forth spirits of the dead, which flit around you for the spell’s duration. The spirits are intangible and invulnerable.\n\n"
            "Until the spell ends, any attack you make deals 1d8 extra damage when you hit a creature within 10 feet of you. "
            "This damage is radiant, necrotic, or cold (your choice when you cast the spell). "
            "Any creature that takes this damage can’t regain hit points until the start of your next turn.\n\n"
            "In addition, any creature of your choice that you can see that starts its turn within 10 feet of you has its speed reduced by 10 feet until the start of your next turn.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d8 for every two slot levels above 3rd."
        ),
        source="Tasha's Cauldron of Everything",
        tags=["Necromancy", "Damage", "Radiant", "Necrotic", "Cold", "Debuff"],
    ),
    make_spell(
        name="Summon Lesser Demons",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a vial of blood from a humanoid killed within the past 24 hours)",
        duration="1 hour",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "You utter foul words, summoning demons from the chaos of the Abyss. "
            "Roll on the following table to determine what appears.\n\n"
            "d6\tDemons Summoned\n"
            "1-2\tTwo demons of challenge rating 1 or lower\n"
            "3-4\tFour demons of challenge rating 1/2 or lower\n"
            "5-6\tEight demons of challenge rating 1/4 or lower\n\n"
            "The DM chooses the demons, such as manes or dretches, and you choose the unoccupied spaces you can see within range where they appear. "
            "A summoned demon disappears when it drops to 0 hit points or when the spell ends.\n\n"
            "The demons are hostile to all creatures, including you. Roll initiative for the summoned demons as a group, which has its own turns. "
            "The demons pursue and attack the nearest non-demons to the best of their ability.\n\n"
            "As part of casting the spell, you can form a circle on the ground with the blood used as a material component. "
            "The circle is large enough to encompass your space. While the spell lasts, the summoned demons can't cross the circle or harm it, and they can't target anyone within it. "
            "Using the material component in this manner consumes it when the spell ends.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th or 7th level, you summon twice as many demons. "
            "If you cast it using a spell slot of 8th or 9th level, you summon three times as many demons."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration"],
    ),
    make_spell(
        name="Summon Shadowspawn",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (tears inside a crystal vial worth at least 300 gp)",
        duration="1 hour",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "You call forth a shadowy spirit. It manifests in an unoccupied space that you can see within range. This corporeal form uses the Shadow Spirit stat block. "
            "When you cast the spell, choose an emotion: Fury, Despair, or Fear. "
            "The creature resembles a misshapen biped marked by the chosen emotion, which determines certain traits in its stat block. "
            "The creature disappears when it drop to 0 hit points or when the spell ends.\n\n"
            "The creature is an ally to you and your companions. In combat, the creature shares your initiative count, but it takes its turn immediately after your. "
            "It obeys your verbal commands (no action required by you). If you don’t issue any, it takes the Dodge action and it uses its move to avoid danger.\n\n"
            "At Higher Levels. When you cast the spell using a spell slot of 4th level or higher, use the higher level wherever the spell’s level appears on the stat block."
        ),
        source="Tasha's Cauldron of Everything",
        tags=["Conjuration"],
    ),
    make_spell(
        name="Thunder Step",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You teleport yourself to an unoccupied space you can see within range. Immediately after you disappear, a thunderous boom sounds, "
            "and each creature within 10 feet of the space you left must make a Constitution saving throw, taking 3d10 thunder damage on a failed save, or half as much damage on a successful one. "
            "The thunder can be heard from up to 300 feet away.\n\n"
            "You can bring along objects as long as their weight doesn’t exceed what you can carry. "
            "You can also teleport one willing creature of your size or smaller who is carrying gear up to its carrying capacity. "
            "The creature must be within 5 feet of you when you cast this spell, and there must be an unoccupied space within 5 feet of your destination space for the creature to appear in; otherwise, the creature is left behind.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, the damage increases by 1d10 for each slot level above 3rd."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "AOE", "Thunder", "Damage", "Saving Throw"],
    ),
    make_spell(
        name="Tiny Servant",
        level=3,
        casting_time="1 minute",
        ritual=False,
        range_str="Touch",
        components="V, S",
        duration="8 hours",
        concentration=False,
        class_names=["Wizard", "Artificer"],
        description=(
            "You touch one Tiny, nonmagical object that isn’t attached to another object or a surface and isn’t being carried by another creature. "
            "The target animates and sprouts little arms and legs, becoming a creature under your control until the spell ends or the creature drops to 0 hit points. "
            "See the stat block for its statistics.\n\n"
            "As a bonus action, you can mentally command the creature if it is within 120 feet of you. (If you control multiple creatures with this spell, you can command any or all of them at the same time, issuing the same command to each one.) "
            "You decide what action the creature will take and where it will move during its next turn, or you can issue a simple, general command, such as to fetch a key, stand watch, or stack some books. "
            "If you issue no commands, the servant does nothing other than defend itself against hostile creatures. Once given an order, the servant continues to follow that order until its task is complete.\n\n"
            "When the creature drops to 0 hit points, it reverts to its original form, and any remaining damage carries over to that form.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 4th level or higher, you can animate two additional objects for each slot level above 3rd."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Utility"],
    ),
    make_spell(
        name="Tidal Wave",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a drop of water)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You conjure up a wave of water that crashes down on an area within range. "
            "The area can be up to 30 feet long, up to 10 feet wide, and up to 10 feet tall. "
            "Each creature in that area must make a Dexterity saving throw. On a failure, a creature takes 4d8 bludgeoning damage and is knocked prone. "
            "On a success, a creature takes half as much damage and isn’t knocked prone. "
            "The water then spreads out across the ground in all directions, extinguishing unprotected flames in its area and within 30 feet of it."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "AOE", "Bludgeoning", "Damage", "Saving Throw"],
    ),
    make_spell(
        name="Wall of Sand",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (a handful of sand)",
        duration="10 minutes",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "You conjure up a wall of swirling sand on the ground at a point you can see within range. "
            "You can make the wall up to 30 feet long, 10 feet high, and 10 feet thick, and it vanishes when the spell ends. "
            "It blocks line of sight but not movement. A creature is blinded while in the wall’s space and must spend 3 feet of movement for every 1 foot it moves there."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Debuff"],
    ),
    make_spell(
        name="Wall of Water",
        level=3,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a drop of water)",
        duration="10 minutes",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You conjure up a wall of water on the ground at a point you can see within range. "
            "You can make the wall up to 30 feet long, 10 feet high, and 1 foot thick, or you can make a ringed wall up to 20 feet in diameter, 20 feet high, and 1 foot thick. "
            "The wall vanishes when the spell ends. The wall’s space is difficult terrain.\n\n"
            "Any ranged weapon attack that enters the wall’s space has disadvantage on the attack roll, and fire damage is halved if the fire effect passes through the wall to reach its target. "
            "Spells that deal cold damage that pass through the wall cause the area of the wall they pass through to freeze solid (at least a 5-foot square section is frozen). "
            "Each 5-foot-square frozen section has AC 5 and 15 hit points. Reducing a frozen section to 0 hit points destroys it. "
            "When a section is destroyed, the wall’s water doesn’t fill it."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Utility"],
    ),
    # 4th level
    make_spell(
        name="Elemental Bane",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Warlock", "Wizard", "Artificer"],
        description=(
            "Choose one creature you can see within range, and choose one of the following damage types: acid, cold, fire, lightning, or thunder. "
            "The target must succeed on a Constitution saving throw or be affected by the spell for its duration. "
            "The first time each turn the affected target takes damage of the chosen type, the target takes an extra 2d6 damage of that type. "
            "Moreover, the target loses any resistance to that damage type until the spell ends.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 5th level or higher, you can target one additional creature for each slot level above 4th. "
            "The creatures must be within 30 feet of each other when you target them."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Debuff", "Damage", "Saving Throw"],
    ),
    make_spell(
        name="Find Greater Steed",
        level=4,
        casting_time="10 minutes",
        ritual=False,
        range_str="30 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Paladin"],
        description=(
            "You summon a spirit that assumes the form of a loyal, majestic mount. Appearing in an unoccupied space within range, the spirit takes on a form you choose: a griffon, a pegasus, a peryton, a dire wolf, a rhinoceros, or a saber-toothed tiger. "
            "The creature has the statistics provided in the Monster Manual for the chosen form, though it is a celestial, a fey, or a fiend (your choice) instead of its normal creature type. "
            "Additionally, if it has an Intelligence score of 5 or lower, its Intelligence becomes 6, and it gains the ability to understand one language of your choice that you speak. "
            "You control the mount in combat. While the mount is within 1 mile of you, you can communicate with it telepathically. "
            "While mounted on it, you can make any spell you cast that targets only you also target the mount. "
            "The mount disappears temporarily when it drops to 0 hit points or when you dismiss it as an action. "
            "Casting this spell again re-summons the bonded mount, with all its hit points restored and any conditions removed. "
            "You can’t have more than one mount bonded by this spell or find steed at the same time. "
            "As an action, you can release a mount from its bond, causing it to disappear permanently. "
            "Whenever the mount disappears, it leaves behind any objects it was wearing or carrying."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Galder's Speedy Courier",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="10 feet",
        components="V, S, M (25 gold pieces, or mineral goods of equivalent value, which the spell consumes)",
        duration="10 minutes",
        concentration=False,
        class_names=["Warlock", "Wizard"],
        description=(
            "You summon a Small air elemental to a spot within range. "
            "The air elemental is formless, nearly transparent, immune to all damage, and cannot interact with other creatures or objects. "
            "It carries an open, empty chest whose interior dimensions are 3 feet on each side. "
            "While the spell lasts, you can deposit as many items inside the chest as will fit. "
            "You can then name a living creature you have met and seen at least once before, or any creature for which you possess a body part, lock of hair, clipping from a nail, or similar portion of the creature’s body.\n\n"
            "As soon as the lid of the chest is closed, the elemental and the chest disappear, then reappear adjacent to the target creature. "
            "If the target creature is on another plane, or if it is proofed against magical detection or location, the contents of the chest reappear on the ground at your feet.\n\n"
            "The target creature is made aware of the chest’s contents before it chooses whether or not to open it, and knows how much of the spell’s duration remains in which it can retrieve them. "
            "No other creature can open the chest and retrieve its contents. "
            "When the spell expires or when all the contents of the chest have been removed, the elemental and the chest disappear. "
            "The elemental also disappears if the target creature orders it to return the items to you. "
            "When the elemental disappears, any items not taken from the chest reappear on the ground at your feet.\n\n"
            "At Higher Levels. When you cast this spell using an 8th-level spell slot, you can send the chest to a creature on a different plane of existence from you."
        ),
        source="Lost Laboratory of Kwalish",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Gate Seal",
        level=4,
        casting_time="1 minute",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a broken portal key, which the spell consumes)",
        duration="24 hours",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You fortify the fabric of the planes within a 30-foot cube you can see within range. Within that area, portals close and can't be opened for the duration. "
            "Spells and other effects that allow planar travel or open portals such as gate or plane shift, fail if used to enter or leave the area. "
            "The cube is stationary.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 6th level or higher, the spell lasts until dispelled."
        ),
        source="Planescape - Adventures in the Multiverse",
        tags=["Abjuration", "Utility", "Defense"],
    ),
    make_spell(
        name="Gravity Sinkhole",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a black marble)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "A 20-foot-radius sphere of crushing force forms at a point you can see within range and tugs at the creatures there. "
            "Each creature in the sphere must make a Constitution saving throw. "
            "On a failed save, the creature takes 5d10 force damage, and is pulled in a straight line toward the center of the sphere, ending in an unoccupied space as close to the center as possible (even if that space is in the air). "
            "On a successful save, the creature takes half as much damage and isn't pulled.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 5th level or higher, the damage increases by 1d10 for each slot level above 4th."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Evocation", "Damage", "Force", "AOE", "Saving Throw"],
    ),
    make_spell(
        name="Guardian of Nature",
        level=4,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Ranger"],
        description=(
            "A nature spirit answers your call and transforms you into a powerful guardian. The transformation lasts until the spell ends. "
            "You choose one of the following forms to assume: Primal Beast or Great Tree.\n\n"
            "Primal Beast. Bestial fur covers your body, your facial features become feral, and you gain the following benefits:\n"
            "Your walking speed increases by 10 feet.\n"
            "You gain darkvision with a range of 120 feet.\n"
            "You make Strength-based attack rolls with advantage.\n"
            "Your melee weapon attacks deal an extra 1d6 force damage on a hit.\n\n"
            "Great Tree. Your skin appears barky, leaves sprout from your hair, and you gain the following benefits:\n"
            "You gain 10 temporary hit points.\n"
            "You make Constitution saving throws with advantage.\n"
            "You make Dexterity and Wisdom-based attack rolls with advantage.\n"
            "While you are on the ground, the ground within 15 feet of you is difficult terrain for your enemies."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Damage", "Force", "Temp HP"],
    ),
    make_spell(
        name="Raulothim's Psychic Lance",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "You unleash a shimmering lance of psychic power from your forehead at a creature that you can see within range. "
            "Alternatively, you can utter a creature’s name. If the named target is within range, it becomes the spell’s target even if you can’t see it. "
            "If the named target isn’t within range, the lance dissipates without effect.\n\n"
            "The target must make an Intelligence saving throw. On a failed save, the target takes 7d6 psychic damage and is incapacitated until the start of your next turn. "
            "On a successful save, the creature takes half as much damage and isn’t incapacitated.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 5th level or higher, the damage increases by 1d6 for each slot level above 4th."
        ),
        source="Fizban's Treasury of Dragons",
        tags=["Enchantment", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Shadow Of Moil",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (an undead eyeball encased in a gem worth at least 150 gp)",
        duration="1 minute",
        concentration=True,
        class_names=["Warlock"],
        description=(
            "Flame-like shadows wreathe your body until the spell ends, causing you to become heavily obscured to others. "
            "The shadows turn dim light within 10 feet of you into darkness, and bright light in the same area to dim light.\n\n"
            "Until the spell ends, you have resistance to radiant damage. In addition, whenever a creature within 10 feet of you hits you with an attack, the shadows lash out at that creature, dealing it 2d8 necrotic damage."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Necromancy", "Buff", "Defense", "Damage", "Necrotic"],
    ),
    make_spell(
        name="Sickening Radiance",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "Dim, greenish light spreads within a 30-foot-radius sphere centered on a point you choose within range. "
            "The light spreads around corners, and it lasts until the spell ends.\n\n"
            "When a creature moves into the spell’s area for the first time on a turn or starts its turn there, that creature must succeed on a Constitution saving throw or take 4d10 radiant damage, and it suffers one level of exhaustion and emits a dim, greenish light in a 5-foot radius. "
            "This light makes it impossible for the creature to benefit from being invisible. "
            "The light and any levels of exhaustion caused by this spell go away when the spell ends."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Damage", "Radiant", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Spirit Of Death",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a gilded playing card worth at least 400 gp and depicting an avatar of death)",
        duration="1 hour",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You call forth a spirit that embodies death. The spirit manifests in an unoccupied space you can see within range and uses the reaper spirit stat block. "
            "The spirit disappears when it is reduced to 0 hit points or when the spell ends.\n\n"
            "The spirit is an ally to you and your companions. In combat, the spirit shares your initiative count and takes its turn immediately after yours. "
            "It obeys your verbal commands (no action required by you). If you don’t issue the spirit any commands, it takes the Dodge action and uses its movement to avoid danger.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 5th level or higher, use the higher level wherever the spell’s level appears in the reaper spirit stat block."
        ),
        source="The Book of Many Things",
        tags=["Conjuration"],
    ),
    make_spell(
        name="Summon Greater Demon",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a vial of blood from a humanoid killed within the past 24 hours)",
        duration="1 hour",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "You utter foul words, summoning one demon from the chaos of the Abyss. "
            "You choose the demon’s type, which must be one of challenge rating 5 or lower, such as a shadow demon or a barlgura. "
            "The demon appears in an unoccupied space you can see within range, and the demon disappears when it drops to 0 hit points or when the spell ends.\n\n"
            "Roll initiative for the demon, which has its own turns. When you summon it and on each of your turns thereafter, you can issue a verbal command to it (requiring no action on your part), telling it what it must do on its next turn. "
            "If you issue no command, it spends its turn attacking any creature within reach that has attacked it.\n\n"
            "At the end of each of the demon’s turns, it makes a Charisma saving throw. The demon has disadvantage on this saving throw if you say its true name. "
            "On a failed save, the demon continues to obey you. On a successful save, your control of the demon ends for the rest of the duration, and the demon spends its turns pursuing and attacking the nearest non-demons to the best of its ability. "
            "If you stop concentrating on the spell before it reaches its full duration, an uncontrolled demon doesn’t disappear for 1d6 rounds if it still has hit points.\n\n"
            "As part of casting the spell, you can form a circle on the ground with the blood used as a material component. "
            "The circle is large enough to encompass your space. While the spell lasts, the summoned demon can’t cross the circle or harm it, and it can’t target anyone within it. "
            "Using the material component in this manner consumes it when the spell ends.\n\n"
            "At Higher Levels. When you cast this spell using a spell slot of 5th level or higher, the challenge rating increases by 1 for each slot level above 4th."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration"],
    ),
    make_spell(
        name="Watery Sphere",
        level=4,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (a droplet of water)",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You conjure up a sphere of water with a 5-foot radius on a point you can see within range. "
            "The sphere can hover in the air, but no more than 10 feet off the ground. The sphere remains for the spell’s duration.\n\n"
            "Any creature in the sphere’s space must make a Strength saving throw. "
            "On a successful save, a creature is ejected from that space to the nearest unoccupied space outside it. "
            "A Huge or larger creature succeeds on the saving throw automatically. "
            "On a failed save, a creature is restrained by the sphere and is engulfed by the water. "
            "At the end of each of its turns, a restrained target can repeat the saving throw.\n\n"
            "The sphere can restrain a maximum of four Medium or smaller creatures or one Large creature. "
            "If the sphere restrains a creature in excess of these numbers, a random creature that was already restrained by the sphere falls out of it and lands prone in a space within 5 feet of it.\n\n"
            "As an action, you can move the sphere up to 30 feet in a straight line. "
            "If it moves over a pit, cliff, or other drop, it safely descends until it is hovering 10 feet over ground. "
            "Any creature restrained by the sphere moves with it. "
            "You can ram the sphere into creatures, forcing them to make the saving throw, but no more than once per turn.\n\n"
            "When the spell ends, the sphere falls to the ground and extinguishes all normal flames within 30 feet of it. "
            "Any creature restrained by the sphere is knocked prone in the space where it falls."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "AOE", "Saving Throw"],
    ),
]


def main():
    manager = SpellManager()
    manager.load_spells()

    added = []
    skipped = []
    failed = []

    for spell in spells:
        if manager._db.spell_exists(spell.name):
            skipped.append(spell.name)
            continue

        success = manager.add_spell(spell)
        (added if success else failed).append(spell.name)

    print({"added": added, "skipped": skipped, "failed": failed, "total": len(spells)})


if __name__ == "__main__":
    main()