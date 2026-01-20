from spell_manager import SpellManager
from spell import Spell, CharacterClass


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


def make_spell(*, name, casting_time, ritual, range_str, components, duration, concentration,
			   class_names, description, source, tags):
	return Spell(
		name=name,
		level=4,
		casting_time=casting_time,
		ritual=ritual,
		range_value=rv(range_str),
		components=components,
		duration=duration,
		concentration=concentration,
		classes=classes(class_names),
		description=description,
		source=source,
		tags=tags,
	)


PHB = "Player's Handbook (2024)"
FR = "Forgotten Realms - Heroes of Faerun"

spells = [
	make_spell(
		name="Arcane Eye",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S, M (a bit of bat fur)",
		duration="1 hour",
		concentration=True,
		class_names=["Artificer", "Wizard"],
		description=(
			"You create an Invisible, invulnerable eye within range that hovers for the duration. "
			"You mentally receive visual information from the eye, which can see in every direction. It also has Darkvision with a range of 30 feet.\n\n"
			"As a Bonus Action, you can move the eye up to 30 feet in any direction. "
			"A solid barrier blocks the eye’s movement, but the eye can pass through an opening as small as 1 inch in diameter."
		),
		source=PHB,
		tags=["Divination", "Utility", "Scout", "Vision", "Concentration"],
	),
	make_spell(
		name="Aura of Life",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V",
		duration="10 minutes",
		concentration=True,
		class_names=["Cleric", "Paladin"],
		description=(
			"An aura radiates from you in a 30-foot Emanation for the duration. "
			"While in the aura, you and your allies have Resistance to Necrotic damage, and your Hit Point maximums can’t be reduced. "
			"If an ally with 0 Hit Points starts its turn in the aura, that ally regains 1 Hit Point."
		),
		source=PHB,
		tags=["Abjuration", "Buff", "Aura", "Healing", "Resistance", "Necrotic", "Concentration"],
	),
	make_spell(
		name="Aura of Purity",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V",
		duration="10 minutes",
		concentration=True,
		class_names=["Cleric", "Paladin"],
		description=(
			"An aura radiates from you in a 30-foot Emanation for the duration. "
			"While in the aura, you and your allies have Resistance to Poison damage and Advantage on saving throws to avoid or end effects that include the Blinded, Charmed, Deafened, Frightened, Paralyzed, Poisoned, or Stunned condition."
		),
		source=PHB,
		tags=["Abjuration", "Buff", "Aura", "Resistance", "Conditions", "Concentration"],
	),
	make_spell(
		name="Backlash",
		casting_time="Reaction",
		ritual=False,
		range_str="60 feet",
		components="V",
		duration="Instantaneous",
		concentration=False,
		class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"You ward yourself against destructive energy, reducing the damage taken by 4d6 plus your spellcasting ability modifier.\n\n"
			"If the triggering damage was from a creature within range, you can force the creature to make a Constitution saving throw. "
			"The creature takes 4d6 Force damage on a failed save or half as much damage on a successful one.\n\n"
			"Using a Higher-Level Spell Slot. The damage reduction and Force damage from this spell both increase by 1d6 for every spell slot level above 4."
		),
		source=FR,
		tags=["Abjuration", "Reaction", "Defense", "Damage", "Force", "Saving Throw"],
	),
	make_spell(
		name="Banishment",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S, M (a pentacle)",
		duration="1 minute",
		concentration=True,
		class_names=["Cleric", "Paladin", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"One creature that you can see within range must succeed on a Charisma saving throw or be transported to a harmless demiplane for the duration. "
			"While there, the target has the Incapacitated condition. When the spell ends, the target reappears in the space it left or in the nearest unoccupied space if that space is occupied.\n\n"
			"If the target is an Aberration, a Celestial, an Elemental, a Fey, or a Fiend, the target doesn't return if the spell lasts for 1 minute. "
			"The target is instead transported to a random location on a plane (DM’s choice) associated with its creature type.\n\n"
			"Using a Higher-Level Spell Slot. You can target one additional creature for each spell slot level above 4."
		),
		source=PHB,
		tags=["Abjuration", "Control", "Banishing", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Blight",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S",
		duration="Instantaneous",
		concentration=False,
		class_names=["Druid", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"A creature that you can see within range makes a Constitution saving throw, taking 8d8 Necrotic damage on a failed save or half as much damage on a successful one. "
			"A Plant creature automatically fails the save.\n\n"
			"Alternatively, target a nonmagical plant that isn’t a creature, such as a tree or shrub. It doesn’t make a save; it simply withers and dies.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Necromancy", "Damage", "Necrotic", "Saving Throw"],
	),
	make_spell(
		name="Charm Monster",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S",
		duration="1 hour",
		concentration=False,
		class_names=["Bard", "Druid", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"One creature you can see within range makes a Wisdom saving throw. It does so with Advantage if you or your allies are fighting it. "
			"On a failed save, the target has the Charmed condition until the spell ends or until you or your allies damage it. "
			"The Charmed creature is Friendly to you. When the spell ends, the target knows it was Charmed by you.\n\n"
			"Using a Higher-Level Spell Slot. You can target one additional creature for each spell slot level above 4."
		),
		source=PHB,
		tags=["Enchantment", "Charm", "Debuff", "Saving Throw"],
	),
	make_spell(
		name="Compulsion",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S",
		duration="1 minute",
		concentration=True,
		class_names=["Bard"],
		description=(
			"Each creature of your choice that you can see within range must succeed on a Wisdom saving throw or have the Charmed condition until the spell ends.\n\n"
			"For the duration, you can take a Bonus Action to designate a direction that is horizontal to you. "
			"Each Charmed target must use as much of its movement as possible to move in that direction on its next turn, taking the safest route. "
			"After moving in this way, a target repeats the save, ending the spell on itself on a success."
		),
		source=PHB,
		tags=["Enchantment", "Control", "Charm", "Saving Throw", "Concentration", "Movement"],
	),
	make_spell(
		name="Confusion",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (three nut shells)",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Druid", "Sorcerer", "Wizard"],
		description=(
			"Each creature in a 10-foot-radius Sphere centered on a point you choose within range must succeed on a Wisdom saving throw, "
			"or that target can’t take Bonus Actions or Reactions and must roll 1d10 at the start of each of its turns to determine its behavior for that turn, consulting the table below.\n\n"
			"1d10\tBehavior for the Turn\n"
			"1\tThe target doesn’t take an action, and it uses all its movement to move. Roll 1d4 for the direction: 1, north; 2, east; 3, south; or 4, west.\n"
			"2–6\tThe target doesn’t move or take actions.\n"
			"7–8\tThe target doesn’t move, and it takes the Attack action to make one melee attack against a random creature within reach. If none are within reach, the target takes no action.\n"
			"9–10\tThe target chooses its behavior.\n"
			"At the end of each of its turns, an affected target repeats the save, ending the spell on itself on a success.\n\n"
			"Using a Higher-Level Spell Slot. The Sphere’s radius increases by 5 feet for each spell slot level above 4."
		),
		source=PHB,
		tags=["Enchantment", "Control", "Debuff", "AOE", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Conjure Minor Elementals",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S",
		duration="10 minutes",
		concentration=True,
		class_names=["Druid", "Wizard"],
		description=(
			"You conjure spirits from the Elemental Planes that flit around you in a 15-foot Emanation for the duration. "
			"Until the spell ends, any attack you make deals an extra 2d8 damage when you hit a creature in the Emanation. "
			"This damage is Acid, Cold, Fire, or Lightning (your choice when you make the attack).\n\n"
			"In addition, the ground in the Emanation is Difficult Terrain for your enemies.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Conjuration", "Damage", "Elemental", "Aura", "AOE", "Concentration"],
	),
	make_spell(
		name="Conjure Woodland Beings",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S",
		duration="10 minutes",
		concentration=True,
		class_names=["Druid", "Ranger"],
		description=(
			"You conjure nature spirits that flit around you in a 10-foot Emanation for the duration. "
			"Whenever the Emanation enters the space of a creature you can see and whenever a creature you can see enters the Emanation or ends its turn there, "
			"you can force that creature to make a Wisdom saving throw. The creature takes 5d8 Force damage on a failed save or half as much damage on a successful one. "
			"A creature makes this save only once per turn.\n\n"
			"In addition, you can take the Disengage action as a Bonus Action for the spell’s duration.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Conjuration", "Damage", "Force", "AOE", "Control", "Concentration", "Disengage"],
	),
	make_spell(
		name="Control Water",
		casting_time="Action",
		ritual=False,
		range_str="300 feet",
		components="V, S, M (a mixture of water and dust)",
		duration="10 minutes",
		concentration=True,
		class_names=["Cleric", "Druid", "Wizard"],
		description=(
			"Until the spell ends, you control any water inside an area you choose that is a Cube up to 100 feet on a side, using one of the following effects. "
			"As a Magic action on your later turns, you can repeat the same effect or choose a different one.\n\n"
			"Flood. You cause the water level of all standing water in the area to rise by as much as 20 feet. If you choose an area in a large body of water, "
			"you instead create a 20-foot tall wave that travels from one side of the area to the other and then crashes. "
			"Any Huge or smaller vehicles in the wave’s path are carried with it to the other side. Any Huge or smaller vehicles struck by the wave have a 25 percent chance of capsizing.\n\n"
			"The water level remains elevated until the spell ends or you choose a different effect. If this effect produced a wave, the wave repeats on the start of your next turn while the flood effect lasts.\n\n"
			"Part Water. You part water in the area and create a trench. The trench extends across the spell’s area, and the separated water forms a wall to either side. "
			"The trench remains until the spell ends or you choose a different effect. The water then slowly fills in the trench over the course of the next round until the normal water level is restored.\n\n"
			"Redirect Flow. You cause flowing water in the area to move in a direction you choose, even if the water has to flow over obstacles, up walls, or in other unlikely directions. "
			"The water in the area moves as you direct it, but once it moves beyond the spell’s area, it resumes its flow based on the terrain. "
			"The water continues to move in the direction you chose until the spell ends or you choose a different effect.\n\n"
			"Whirlpool. You cause a whirlpool to form in the center of the area, which must be at least 50 feet square and 25 feet deep. "
			"The whirlpool lasts until you choose a different effect or the spell ends. The whirlpool is 5 feet wide at the base, up to 50 feet wide at the top, and 25 feet tall. "
			"Any creature in the water and within 25 feet of the whirlpool is pulled 10 feet toward it. When a creature enters the whirlpool for the first time on a turn or ends its turn there, it makes a Strength saving throw. "
			"On a failed save, the creature takes 2d8 Bludgeoning damage. On a successful save, the creature takes half as much damage. "
			"A creature can swim away from the whirlpool only if it first takes an action to pull away and succeeds on a Strength (Athletics) check against your spell save DC."
		),
		source=PHB,
		tags=["Transmutation", "Control", "Water", "Terrain", "AOE", "Concentration"],
	),
	make_spell(
		name="Death Ward",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S",
		duration="8 hours",
		concentration=False,
		class_names=["Cleric", "Paladin"],
		description=(
			"You touch a creature and grant it a measure of protection from death. "
			"The first time the target would drop to 0 Hit Points before the spell ends, the target instead drops to 1 Hit Point, and the spell ends.\n\n"
			"If the spell is still in effect when the target is subjected to an effect that would kill it instantly without dealing damage, "
			"that effect is negated against the target, and the spell ends."
		),
		source=PHB,
		tags=["Abjuration", "Defense", "Buff"],
	),
	make_spell(
		name="Dimension Door",
		casting_time="Action",
		ritual=False,
		range_str="500 feet",
		components="V",
		duration="Instantaneous",
		concentration=False,
		class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"You teleport to a location within range. You arrive at exactly the spot desired. "
			"It can be a place you can see, one you can visualize, or one you can describe by stating distance and direction, such as “200 feet straight downward” or “300 feet upward to the northwest at a 45-degree angle.”\n\n"
			"You can also teleport one willing creature. The creature must be within 5 feet of you when you teleport, and it teleports to a space within 5 feet of your destination space.\n\n"
			"If you, the other creature, or both would arrive in a space occupied by a creature or completely filled by one or more objects, "
			"you and any creature traveling with you each take 4d6 Force damage, and the teleportation fails."
		),
		source=PHB,
		tags=["Conjuration", "Teleportation", "Movement", "Utility"],
	),
	make_spell(
		name="Divination",
		casting_time="Action or Ritual",
		ritual=True,
		range_str="Self",
		components="V, S, M (incense worth 25+ GP, which the spell consumes)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Cleric", "Druid", "Wizard"],
		description=(
			"This spell puts you in contact with a god or a god’s servants. You ask one question about a specific goal, event, or activity to occur within 7 days. "
			"The DM offers a truthful reply, which might be a short phrase or cryptic rhyme. "
			"The spell doesn’t account for circumstances that might change the answer, such as the casting of other spells.\n\n"
			"If you cast the spell more than once before finishing a Long Rest, there is a cumulative 25 percent chance for each casting after the first that you get no answer."
		),
		source=PHB,
		tags=["Divination", "Utility", "Ritual", "Knowledge", "Costly"],
	),
	make_spell(
		name="Dominate Beast",
		casting_time="Action",
		ritual=False,
		range_str="60 feet",
		components="V, S",
		duration="1 minute",
		concentration=True,
		class_names=["Druid", "Ranger", "Sorcerer"],
		description=(
			"One Beast you can see within range must succeed on a Wisdom saving throw or have the Charmed condition for the duration. "
			"The target has Advantage on the save if you or your allies are fighting it. Whenever the target takes damage, it repeats the save, ending the spell on itself on a success.\n\n"
			"You have a telepathic link with the Charmed target while the two of you are on the same plane of existence. "
			"On your turn, you can use this link to issue commands to the target (no action required), such as “Attack that creature,” “Move over there,” or “Fetch that object.” "
			"The target does its best to obey on its turn. If it completes an order and doesn’t receive further direction from you, "
			"it acts and moves as it likes, focusing on protecting itself.\n\n"
			"You can command the target to take a Reaction but must take your own Reaction to do so.\n\n"
			"Using a Higher-Level Spell Slot. Your Concentration can last longer with a spell slot of level 5 (up to 10 minutes), 6 (up to 1 hour), or 7+ (up to 8 hours)."
		),
		source=PHB,
		tags=["Enchantment", "Control", "Charm", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Doomtide",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="V, S, M (soot and a dried eel)",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Cleric", "Warlock"],
		description=(
			"You create a 20-foot-radius Sphere of inky fog within range. "
			"The fog is magical Darkness and lasts for the duration or until a strong wind (such as the one created by the Gust of Wind spell) disperses it, ending the spell.\n\n"
			"Each creature in the Sphere when it appears makes a Wisdom saving throw. On a failed save, a creature takes 5d6 Psychic damage and subtracts 1d6 from its saving throws until the end of its next turn. "
			"On a successful save, a creature takes half as much damage only. A creature also makes this save when the Sphere moves into its space, when it enters the Sphere, or when it ends its turn inside the Sphere. "
			"A creature makes this save only once per turn.\n\n"
			"The Sphere moves 10 feet away from you at the start of each of your turns.\n\n"
			"Casting as a Circle Spell. Casting this as a Circle spell requires a minimum of five secondary casters. "
			"In addition to the spell’s usual components, you must provide a special component (a string of three black pearls from Pandemonium), which the spell consumes. "
			"The spell’s range increases to 1 mile, and its duration increases to until dispelled (no Concentration required). "
			"The spell ends early if any caster who participated in this casting contributes to another casting of Doomtide as a Circle spell.\n\n"
			"When the spell is cast, each secondary caster must expend a level 3+ spell slot; otherwise, the spell fails."
		),
		source=FR,
		tags=["Conjuration", "Damage", "Psychic", "AOE", "Darkness", "Control", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Evard's Black Tentacles",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (a tentacle)",
		duration="1 minute",
		concentration=True,
		class_names=["Wizard"],
		description=(
			"Squirming, ebony tentacles fill a 20-foot square on ground that you can see within range. "
			"For the duration, these tentacles turn the ground in that area into Difficult Terrain.\n\n"
			"Each creature in that area makes a Strength saving throw. On a failed save, it takes 3d6 Bludgeoning damage, and it has the Restrained condition until the spell ends. "
			"A creature also makes that save if it enters the area or ends it turn there. A creature makes that save only once per turn.\n\n"
			"A Restrained creature can take an action to make a Strength (Athletics) check against your spell save DC, ending the condition on itself on a success."
		),
		source=PHB,
		tags=["Conjuration", "Damage", "Bludgeoning", "Control", "Restrain", "AOE", "Saving Throw", "Concentration", "Terrain"],
	),
	make_spell(
		name="Fabricate",
		casting_time="10 minutes",
		ritual=False,
		range_str="120 feet",
		components="V, S",
		duration="Instantaneous",
		concentration=False,
		class_names=["Artificer", "Wizard"],
		description=(
			"You convert raw materials into products of the same material. For example, you can fabricate a wooden bridge from a clump of trees, "
			"a rope from a patch of hemp, or clothes from flax or wool.\n\n"
			"Choose raw materials that you can see within range. You can fabricate a Large or smaller object (contained within a 10-foot Cube or eight connected 5-foot Cubes) given a sufficient quantity of material. "
			"If you’re working with metal, stone, or another mineral substance, however, the fabricated object can be no larger than Medium (contained within a 5-foot Cube). "
			"The quality of any fabricated objects is based on the quality of the raw materials.\n\n"
			"Creatures and magic items can’t be created by this spell. "
			"You also can’t use it to create items that require a high degree of skill - such as weapons and armor - unless you have proficiency with the type of Artisan’s Tools used to craft such objects."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Crafting"],
	),
	make_spell(
		name="Fire Shield",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S, M (a bit of phosphorus or a firefly)",
		duration="10 minutes",
		concentration=False,
		class_names=["Druid", "Sorcerer", "Wizard"],
		description=(
			"Wispy flames wreathe your body for the duration, shedding Bright Light in a 10-foot radius and Dim Light for an additional 10 feet.\n\n"
			"The flames provide you with a warm shield or a chill shield, as you choose. "
			"The warm shield grants you Resistance to Cold damage, and the chill shield grants you Resistance to Fire damage.\n\n"
			"In addition, whenever a creature within 5 feet of you hits you with a melee attack roll, the shield erupts with flame. "
			"The attacker takes 2d8 Fire damage from a warm shield or 2d8 Cold damage from a chill shield."
		),
		source=PHB,
		tags=["Evocation", "Buff", "Defense", "Resistance", "Fire", "Cold", "Damage"],
	),
	make_spell(
		name="Fount of Moonlight",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S",
		duration="10 minutes",
		concentration=True,
		class_names=["Bard", "Druid"],
		description=(
			"A cool light wreathes your body for the duration, emitting Bright Light in a 20-foot radius and Dim Light for an additional 20 feet.\n\n"
			"Until the spell ends, you have Resistance to Radiant damage, and your melee attacks deal an extra 2d6 Radiant damage on a hit.\n\n"
			"In addition, immediately after you take damage from a creature you can see within 60 feet of yourself, "
			"you can take a Reaction to force the creature to make a Constitution saving throw. On a failed save, the creature has the Blinded condition until the end of your next turn."
		),
		source=PHB,
		tags=["Evocation", "Buff", "Radiant", "Light", "Resistance", "Damage", "Reaction", "Concentration"],
	),
	make_spell(
		name="Freedom of Movement",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (a leather strap)",
		duration="1 hour",
		concentration=False,
		class_names=["Artificer", "Bard", "Cleric", "Druid", "Ranger"],
		description=(
			"You touch a willing creature. For the duration, the target’s movement is unaffected by Difficult Terrain, "
			"and spells and other magical effects can neither reduce the target’s Speed nor cause the target to have the Paralyzed or Restrained conditions. "
			"The target also has a Swim Speed equal to its Speed.\n\n"
			"In addition, the target can spend 5 feet of movement to automatically escape from nonmagical restraints, "
			"such as manacles or a creature imposing the Grappled condition on it.\n\n"
			"Using a Higher-Level Spell Slot. You can target one additional creature for each spell slot level above 4."
		),
		source=PHB,
		tags=["Abjuration", "Buff", "Movement", "Defense"],
	),
	make_spell(
		name="Giant Insect",
		casting_time="Action",
		ritual=False,
		range_str="60 feet",
		components="V, S",
		duration="10 minutes",
		concentration=True,
		class_names=["Druid"],
		description=(
			"You summon a giant centipede, spider, or wasp (chosen when you cast the spell). "
			"It manifests in an unoccupied space you can see within range and uses the Giant Insect stat block. "
			"The form you choose determines certain details in its stat block. The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
			"The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
			"It obeys your verbal commands (no action required by you). If you don’t issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
			"Using a Higher-Level Spell Slot. Use the spell slot’s level for the spell’s level in the stat block."
		),
		source=PHB,
		tags=["Conjuration", "Summon", "Beast", "Concentration"],
	),
	make_spell(
		name="Grasping Vine",
		casting_time="Bonus Action",
		ritual=False,
		range_str="60 feet",
		components="V, S",
		duration="1 minute",
		concentration=True,
		class_names=["Druid", "Ranger"],
		description=(
			"You conjure a vine that sprouts from a surface in an unoccupied space that you can see within range. The vine lasts for the duration.\n\n"
			"Make a melee spell attack against a creature within 30 feet of the vine. On a hit, the target takes 4d8 Bludgeoning damage and is pulled up to 30 feet toward the vine; "
			"if the target is Huge or smaller, it has the Grappled condition (escape DC equal to your spell save DC). "
			"The vine can grapple only one creature at a time, and you can cause the vine to release a Grappled creature (no action required).\n\n"
			"As a Bonus Action on your later turns, you can repeat the attack against a creature within 30 feet of the vine.\n\n"
			"Using a Higher-Level Spell Slot. The number of creatures the vine can grapple increases by one for each spell slot level above 4."
		),
		source=PHB,
		tags=["Conjuration", "Control", "Grapple", "Damage", "Bludgeoning", "Concentration", "Bonus Action"],
	),
	make_spell(
		name="Greater Invisibility",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Sorcerer", "Wizard"],
		description=(
			"A creature you touch has the Invisible condition until the spell ends."
		),
		source=PHB,
		tags=["Illusion", "Buff", "Invisibility", "Concentration"],
	),
	make_spell(
		name="Guardian of Faith",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V",
		duration="8 hours",
		concentration=False,
		class_names=["Cleric"],
		description=(
			"A Large spectral guardian appears and hovers for the duration in an unoccupied space that you can see within range. "
			"The guardian occupies that space and is invulnerable, and it appears in a form appropriate for your deity or pantheon.\n\n"
			"Any enemy that moves to a space within 10 feet of the guardian for the first time on a turn or starts its turn there makes a Dexterity saving throw, "
			"taking 20 Radiant damage on a failed save or half as much damage on a successful one. The guardian vanishes when it has dealt a total of 60 damage."
		),
		source=PHB,
		tags=["Conjuration", "Damage", "Radiant", "Control", "Saving Throw"],
	),
	make_spell(
		name="Hallucinatory Terrain",
		casting_time="10 minutes",
		ritual=False,
		range_str="300 feet",
		components="V, S, M (a mushroom)",
		duration="24 hours",
		concentration=False,
		class_names=["Bard", "Druid", "Warlock", "Wizard"],
		description=(
			"You make natural terrain in a 150-foot Cube in range look, sound, and smell like another sort of natural terrain. "
			"Thus, open fields or a road can be made to resemble a swamp, hill, crevasse, or some other difficult or impassable terrain. "
			"A pond can be made to seem like a grassy meadow, a precipice like a gentle slope, or a rock-strewn gully like a wide and smooth road. "
			"Manufactured structures, equipment, and creatures within the area aren’t changed.\n\n"
			"The tactile characteristics of the terrain are unchanged, so creatures entering the area are likely to notice the illusion. "
			"If the difference isn’t obvious by touch, a creature examining the illusion can take the Study action to make an Intelligence (Investigation) check against your spell save DC to disbelieve it. "
			"If a creature discerns that the terrain is illusory, the creature sees a vague image superimposed on the real terrain."
		),
		source=PHB,
		tags=["Illusion", "Utility", "Terrain", "Control", "Exploration"],
	),
	make_spell(
		name="Ice Storm",
		casting_time="Action",
		ritual=False,
		range_str="300 feet",
		components="V, S, M (a mitten)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Druid", "Sorcerer", "Wizard"],
		description=(
			"Hail falls in a 20-foot-radius, 40-foot-high Cylinder centered on a point within range. Each creature in the Cylinder makes a Dexterity saving throw. "
			"A creature takes 2d10 Bludgeoning damage and 4d6 Cold damage on a failed save or half as much damage on a successful one.\n\n"
			"Hailstones turn ground in the Cylinder into Difficult Terrain until the end of your next turn.\n\n"
			"Using a Higher-Level Spell Slot. The Bludgeoning damage increases by 1d10 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Evocation", "Damage", "Cold", "Bludgeoning", "AOE", "Saving Throw", "Terrain"],
	),
	make_spell(
		name="Leomund's Secret Chest",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (a chest, 3 feet by 2 feet by 2 feet, constructed from rare materials worth 5,000+ GP, and a Tiny replica of the chest made from the same materials worth 50+ GP)",
		duration="Until dispelled",
		concentration=False,
		class_names=["Artificer", "Wizard"],
		description=(
			"You hide a chest and all its contents on the Ethereal Plane. You must touch the chest and the miniature replica that serve as Material components for the spell. "
			"The chest can contain up to 12 cubic feet of nonliving material (3 feet by 2 feet by 2 feet).\n\n"
			"While the chest remains on the Ethereal Plane, you can take a Magic action and touch the replica to recall the chest. "
			"It appears in an unoccupied space on the ground within 5 feet of you. You can send the chest back to the Ethereal Plane by taking a Magic action to touch the chest and the replica.\n\n"
			"After 60 days, there is a cumulative 5 percent chance at the end of each day that the spell ends. "
			"The spell also ends if you cast this spell again or if the Tiny replica chest is destroyed. "
			"If the spell ends and the larger chest is on the Ethereal Plane, the chest remains there for you or someone else to find."
		),
		source=PHB,
		tags=["Conjuration", "Utility", "Storage"],
	),
	make_spell(
		name="Locate Creature",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S, M (fur from a bloodhound)",
		duration="1 hour",
		concentration=True,
		class_names=["Bard", "Cleric", "Druid", "Paladin", "Ranger", "Wizard"],
		description=(
			"Describe or name a creature that is familiar to you. You sense the direction to the creature’s location if that creature is within 1,000 feet of you. "
			"If the creature is moving, you know the direction of its movement.\n\n"
			"The spell can locate a specific creature known to you or the nearest creature of a specific kind (such as a human or a unicorn) "
			"if you have seen such a creature up close—within 30 feet—at least once. "
			"If the creature you described or named is in a different form, such as under the effects of a Flesh to Stone or Polymorph spell, this spell doesn’t locate the creature.\n\n"
			"This spell can’t locate a creature if any thickness of lead blocks a direct path between you and the creature."
		),
		source=PHB,
		tags=["Divination", "Utility", "Tracking", "Concentration"],
	),
	make_spell(
		name="Mordenkainen's Faithful Hound",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S, M (a silver whistle)",
		duration="8 hours",
		concentration=False,
		class_names=["Wizard"],
		description=(
			"You conjure a phantom watchdog in an unoccupied space that you can see within range. "
			"The hound remains for the duration or until the two of you are more than 300 feet apart from each other.\n\n"
			"No one but you can see the hound, and it is intangible and invulnerable. "
			"When a Small or larger creature comes within 30 feet of it without first speaking the password that you specify when you cast this spell, the hound starts barking loudly. "
			"The hound has Truesight with a range of 30 feet.\n\n"
			"At the start of each of your turns, the hound attempts to bite one enemy within 5 feet of it. "
			"That enemy must succeed on a Dexterity saving throw or take 4d8 Force damage.\n\n"
			"On your later turns, you can take a Magic action to move the hound up to 30 feet."
		),
		source=PHB,
		tags=["Conjuration", "Summon", "Force", "Damage", "Detection"],
	),
	make_spell(
		name="Mordenkainen's Private Sanctum",
		casting_time="10 minutes",
		ritual=False,
		range_str="120 feet",
		components="V, S, M (a thin sheet of lead)",
		duration="24 hours",
		concentration=False,
		class_names=["Artificer", "Wizard"],
		description=(
			"You make an area within range magically secure. The area is a Cube that can be as small as 5 feet to as large as 100 feet on each side. "
			"The spell lasts for the duration.\n\n"
			"When you cast the spell, you decide what sort of security the spell provides, choosing any of the following properties:\n"
			"Sound can’t pass through the barrier at the edge of the warded area.\n"
			"The barrier of the warded area appears dark and foggy, preventing vision (including Darkvision) through it.\n"
			"Sensors created by Divination spells can’t appear inside the protected area or pass through the barrier at its perimeter.\n"
			"Creatures in the area can’t be targeted by Divination spells.\n"
			"Nothing can teleport into or out of the warded area.\n"
			"Planar travel is blocked within the warded area.\n\n"
			"Casting this spell on the same spot every day for 365 days makes the spell last until dispelled.\n\n"
			"Using a Higher-Level Spell Slot. You can increase the size of the Cube by 100 feet for each spell slot level above 4."
		),
		source=PHB,
		tags=["Abjuration", "Utility", "Protection", "Warding"],
	),
	make_spell(
		name="Otiluke's Resilient Sphere",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S, M (a glass sphere)",
		duration="1 minute",
		concentration=True,
		class_names=["Artificer", "Wizard"],
		description=(
			"A shimmering sphere encloses a Large or smaller creature or object within range. An unwilling creature must succeed on a Dexterity saving throw or be enclosed for the duration.\n\n"
			"Nothing—not physical objects, energy, or other spell effects—can pass through the barrier, in or out, though a creature in the sphere can breathe there. "
			"The sphere is immune to all damage, and a creature or object inside can’t be damaged by attacks or effects originating from outside, nor can a creature inside the sphere damage anything outside it.\n\n"
			"The sphere is weightless and just large enough to contain the creature or object inside. "
			"An enclosed creature can take an action to push against the sphere’s walls and thus roll the sphere at up to half the creature’s Speed. "
			"Similarly, the globe can be picked up and moved by other creatures.\n\n"
			"A Disintegrate spell targeting the globe destroys it without harming anything inside."
		),
		source=PHB,
		tags=["Abjuration", "Control", "Defense", "Force", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Phantasmal Killer",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="V, S",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Wizard"],
		description=(
			"You tap into the nightmares of a creature you can see within range and create an illusion of its deepest fears, visible only to that creature. "
			"The target makes a Wisdom saving throw. On a failed save, the target takes 4d10 Psychic damage and has Disadvantage on ability checks and attack rolls for the duration. "
			"On a successful save, the target takes half as much damage, and the spell ends.\n\n"
			"For the duration, the target makes a Wisdom saving throw at the end of each of its turns. "
			"On a failed save, it takes the Psychic damage again. On a successful save, the spell ends.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d10 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Illusion", "Damage", "Psychic", "Debuff", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Polymorph",
		casting_time="Action",
		ritual=False,
		range_str="60 feet",
		components="V, S, M (a caterpillar cocoon)",
		duration="1 hour",
		concentration=True,
		class_names=["Bard", "Druid", "Sorcerer", "Wizard"],
		description=(
			"You attempt to transform a creature that you can see within range into a Beast. "
			"The target must succeed on a Wisdom saving throw or shape-shift into a Beast form for the duration. "
			"That form can be any Beast you choose that has a Challenge Rating equal to or less than the target's (or the target's level if it doesn't have a Challenge Rating). "
			"The target's game statistics are replaced by the stat block of the chosen Beast, but the target retains its alignment, personality, creature type, Hit Points, and Hit Point Dice. "
			"See appendix B for a sample of Beast stat blocks.\n\n"
			"The target gains a number of Temporary Hit Points equal to the Hit Points of the Beast form. "
			"These Temporary Hit Points vanish if any remain when the spell ends. The spell ends early on the target if it has no Temporary Hit Points left.\n"
			"The target is limited in the actions it can perform by the anatomy of its new form, and it can’t speak or cast spells.\n\n"
			"The target's gear melds into the new form. The creature can't use or otherwise benefit from any of that equipment."
		),
		source=PHB,
		tags=["Transmutation", "Control", "Shapechange", "Buff", "Concentration"],
	),
	make_spell(
		name="Spellfire Storm",
		casting_time="Action",
		ritual=False,
		range_str="60 feet",
		components="V, S",
		duration="1 minute",
		concentration=True,
		class_names=["Sorcerer", "Wizard"],
		description=(
			"You conjure a pillar of spellfire in a 20-foot-radius, 20-foot-high Cylinder centered on a point within range. "
			"The area of the Cylinder is Bright Light, and each creature in it when it appears makes a Constitution saving throw, "
			"taking 4d10 Radiant damage on a failed save or half as much damage on a successful one. "
			"A creature also makes this save when it enters the spell’s area for the first time on a turn or ends its turn there. "
			"A creature makes this save only once per turn.\n\n"
			"In addition, whenever a creature in the Cylinder casts a spell, that creature makes a Constitution saving throw. "
			"On a failed save, the spell dissipates with no effect, and the action, Bonus Action, or Reaction used to cast it is wasted. "
			"If that spell was cast with a spell slot, the slot isn’t expended.\n\n"
			"When you cast this spell, you can designate creatures to be unaffected by it.\n\n"
			"Casting as a Circle Spell. In addition to the spell’s usual components, you must provide a special component (a blue star sapphire worth 25,000+ GP), which the spell consumes. "
			"The spell’s range increases to 1 mile, and it no longer requires Concentration. "
			"When the spell is cast, each secondary caster must expend a level 3+ spell slot; otherwise, the spell fails.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d10 for every spell slot level above 4.\n\n"
			"The number of secondary casters determines the spell’s area of effect and duration, as shown in the table below. "
			"The spell ends early if any caster who participated in this casting contributes to another casting of Spellfire Storm as a Circle spell.\n\n"
			"Secondary Casters\tArea of Effect\tDuration\n"
			"1-3\t40-foot-radius, 40-foot-high Cylinder\t1 hour\n"
			"4-6\t60-foot-radius, 60-foot-high Cylinder\t8 hours\n"
			"7+\t100-foot-radius, 100-foot-high Cylinder\t24 hours"
		),
		source=FR,
		tags=["Evocation", "Damage", "Radiant", "AOE", "Control", "Anti-Magic", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Staggering Smite",
		casting_time="Bonus Action",
		ritual=False,
		range_str="Self",
		components="V",
		duration="Instantaneous",
		concentration=False,
		class_names=["Paladin"],
		description=(
			"The target takes an extra 4d6 Psychic damage from the attack, and the target must succeed on a Wisdom saving throw or have the Stunned condition until the end of your next turn.\n\n"
			"Using a Higher-Level Spell Slot. The extra damage increases by 1d6 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Enchantment", "Damage", "Psychic", "Smite", "Bonus Action", "Saving Throw", "Debuff"],
	),
	make_spell(
		name="Stone Shape",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (soft clay)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Artificer", "Cleric", "Druid", "Wizard"],
		description=(
			"You touch a stone object of Medium size or smaller or a section of stone no more than 5 feet in any dimension and form it into any shape you like. "
			"For example, you could shape a large rock into a weapon, statue, or coffer, or you could make a small passage through a wall that is 5 feet thick. "
			"You could also shape a stone door or its frame to seal the door shut. The object you create can have up to two hinges and a latch, but finer mechanical detail isn’t possible."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Crafting"],
	),
	make_spell(
		name="Stoneskin",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (diamond dust worth 100+ GP, which the spell consumes)",
		duration="1 hour",
		concentration=True,
		class_names=["Artificer", "Druid", "Ranger", "Sorcerer", "Wizard"],
		description=(
			"Until the spell ends, one willing creature you touch has Resistance to Bludgeoning, Piercing, and Slashing damage."
		),
		source=PHB,
		tags=["Transmutation", "Buff", "Defense", "Resistance", "Costly", "Concentration"],
	),
	make_spell(
		name="Summon Aberration",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (a pickled tentacle and an eyeball in a platinum-inlaid vial worth 400+ GP)",
		duration="1 hour",
		concentration=True,
		class_names=["Warlock", "Wizard"],
		description=(
			"You call forth an aberrant spirit. It manifests in an unoccupied space that you can see within range and uses the Aberrant Spirit stat block. "
			"When you cast the spell, choose Beholderkin, Mind Flayer, or Slaad. The creature resembles an Aberration of that kind, which determines certain details in its stat block. "
			"The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
			"The creature is an ally to you and your allies. In combat, it shares your Initiative count, but it takes its turn immediately after yours. "
			"It obeys your verbal commands (no action required by you). If you don’t issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
			"Using a Higher-Level Spell Slot. Use the spell slot’s level for the spell’s level in the stat block."
		),
		source=PHB,
		tags=["Conjuration", "Summon", "Aberration", "Concentration"],
	),
	make_spell(
		name="Summon Construct",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (a lockbox worth 400+ GP)",
		duration="1 hour",
		concentration=True,
		class_names=["Artificer", "Wizard"],
		description=(
			"You call forth the spirit of a Construct. It manifests in an unoccupied space that you can see within range and uses the Construct Spirit stat block. "
			"When you cast the spell, choose a material: Clay, Metal, or Stone. The creature resembles an animate statue (you determine the appearance) made of the chosen material, "
			"which determines certain details in its stat block. The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
			"The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
			"It obeys your verbal commands (no action required by you). If you don’t issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
			"Using a Higher-Level Spell Slot. Use the spell slot’s level for the spell’s level in the stat block."
		),
		source=PHB,
		tags=["Conjuration", "Summon", "Construct", "Concentration"],
	),
	make_spell(
		name="Summon Elemental",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (air, a pebble, ash, and water inside a gold-inlaid vial worth 400+ GP)",
		duration="1 hour",
		concentration=True,
		class_names=["Druid", "Ranger", "Wizard"],
		description=(
			"You call forth an Elemental spirit. It manifests in an unoccupied space that you can see within range and uses the Elemental Spirit stat block. "
			"When you cast the spell, choose an element: Air, Earth, Fire, or Water. The creature resembles a bipedal form wreathed in the chosen element, "
			"which determines certain details in its stat block. The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
			"The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
			"It obeys your verbal commands (no action required by you). If you don’t issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
			"Using a Higher-Level Spell Slot. Use the spell slot’s level for the spell’s level in the stat block."
		),
		source=PHB,
		tags=["Conjuration", "Summon", "Elemental", "Concentration"],
	),
	make_spell(
		name="Vitriolic Sphere",
		casting_time="Action",
		ritual=False,
		range_str="150 feet",
		components="V, S, M (a drop of bile)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Sorcerer", "Wizard"],
		description=(
			"You point at a location within range, and a glowing, 1-foot-diameter ball of acid streaks there and explodes in a 20-foot-radius Sphere. "
			"Each creature in that area makes a Dexterity saving throw. On a failed save, a creature takes 10d4 Acid damage and another 5d4 Acid damage at the end of its next turn. "
			"On a successful save, a creature takes half the initial damage only.\n\n"
			"Using a Higher-Level Spell Slot. The initial damage increases by 2d4 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Evocation", "Damage", "Acid", "AOE", "Saving Throw"],
	),
	make_spell(
		name="Wall of Fire",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="V, S, M (a piece of charcoal)",
		duration="1 minute",
		concentration=True,
		class_names=["Druid", "Sorcerer", "Wizard"],
		description=(
			"You create a wall of fire on a solid surface within range. You can make the wall up to 60 feet long, 20 feet high, and 1 foot thick, "
			"or a ringed wall up to 20 feet in diameter, 20 feet high, and 1 foot thick. The wall is opaque and lasts for the duration.\n\n"
			"When the wall appears, each creature in its area makes a Dexterity saving throw, taking 5d8 Fire damage on a failed save or half as much damage on a successful one.\n\n"
			"One side of the wall, selected by you when you cast this spell, deals 5d8 Fire damage to each creature that ends its turn within 10 feet of that side or inside the wall. "
			"A creature takes the same damage when it enters the wall for the first time on a turn or ends its turn there. The other side of the wall deals no damage.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 4."
		),
		source=PHB,
		tags=["Evocation", "Damage", "Fire", "AOE", "Control", "Saving Throw", "Wall", "Concentration"],
	),
]


def main():
	manager = SpellManager()
	manager.load_spells()

	added = []
	updated = []
	failed = []

	for spell in spells:
		if manager._db.spell_exists(spell.name):
			success = manager.update_spell(spell.name, spell)
			(updated if success else failed).append(spell.name)
		else:
			success = manager.add_spell(spell)
			(added if success else failed).append(spell.name)

	print({"added": added, "updated": updated, "failed": failed, "total": len(spells)})


if __name__ == "__main__":
	main()
