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
		level=3,
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
		name="Daylight",
		casting_time="Action",
		ritual=False,
		range_str="60 feet",
		components="V, S",
		duration="1 hour",
		concentration=False,
		class_names=["Cleric", "Druid", "Paladin", "Ranger", "Sorcerer"],
		description=(
			"For the duration, sunlight spreads from a point within range and fills a 60-foot-radius Sphere. "
			"The sunlight’s area is Bright Light and sheds Dim Light for an additional 60 feet.\n\n"
			"Alternatively, you cast the spell on an object that isn’t being worn or carried, causing the sunlight "
			"to fill a 60-foot Emanation originating from that object. Covering that object with something opaque, "
			"such as a bowl or helm, blocks the sunlight.\n\n"
			"If any of this spell’s area overlaps with an area of Darkness created by a spell of level 3 or lower, "
			"that other spell is dispelled."
		),
		source=PHB,
		tags=["Evocation", "Light", "Utility", "AOE"],
	),
	make_spell(
		name="Dispel Magic",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="V, S",
		duration="Instantaneous",
		concentration=False,
		class_names=["Artificer", "Bard", "Cleric", "Druid", "Paladin", "Ranger", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"Choose one creature, object, or magical effect within range. Any ongoing spell of level 3 or lower on the target ends. "
			"For each ongoing spell of level 4 or higher on the target, make an ability check using your spellcasting ability (DC 10 plus that spell’s level). "
			"On a successful check, the spell ends.\n\n"
			"Using a Higher-Level Spell Slot. You automatically end a spell on the target if the spell’s level is equal to or less than the level of the spell slot you use."
		),
		source=PHB,
		tags=["Abjuration", "Utility", "Dispel"],
	),
	make_spell(
		name="Elemental Weapon",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S",
		duration="1 hour",
		concentration=True,
		class_names=["Artificer", "Druid", "Paladin", "Ranger"],
		description=(
			"A nonmagical weapon you touch becomes a magic weapon. Choose one of the following damage types: Acid, Cold, Fire, Lightning, or Thunder. "
			"For the duration, the weapon has a +1 bonus to attack rolls and deals an extra 1d4 damage of the chosen type when it hits.\n\n"
			"Using a Higher-Level Spell Slot. If you use a level 5–6 spell slot, the bonus to attack rolls increases to +2, and the extra damage increases to 2d4. "
			"If you use a level 7+ spell slot, the bonus increases to +3, and the extra damage increases to 3d4."
		),
		source=PHB,
		tags=["Transmutation", "Buff", "Damage", "Weapon", "Concentration"],
	),
	make_spell(
		name="Fear",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S, M (a white feather)",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"Each creature in a 30-foot Cone must succeed on a Wisdom saving throw or drop whatever it is holding and have the Frightened condition for the duration.\n\n"
			"A Frightened creature takes the Dash action and moves away from you by the safest route on each of its turns unless there is nowhere to move. "
			"If the creature ends its turn in a space where it doesn’t have line of sight to you, the creature makes a Wisdom saving throw. "
			"On a successful save, the spell ends on that creature."
		),
		source=PHB,
		tags=["Illusion", "Debuff", "Frightened", "AOE", "Saving Throw", "Control", "Concentration"],
	),
	make_spell(
		name="Feign Death",
		casting_time="Action or Ritual",
		ritual=True,
		range_str="Touch",
		components="V, S, M (a pinch of graveyard dirt)",
		duration="1 hour",
		concentration=False,
		class_names=["Bard", "Cleric", "Druid", "Wizard"],
		description=(
			"You touch a willing creature and put it into a cataleptic state that is indistinguishable from death.\n\n"
			"For the duration, the target appears dead to outward inspection and to spells used to determine the target’s status. "
			"The target has the Blinded and Incapacitated conditions, and its Speed is 0.\n\n"
			"The target also has Resistance to all damage except Psychic damage, and it has Immunity to the Poisoned condition."
		),
		source=PHB,
		tags=["Necromancy", "Utility", "Ritual", "Defense"],
	),
	make_spell(
		name="Fireball",
		casting_time="Action",
		ritual=False,
		range_str="150 feet",
		components="V, S, M (a ball of bat guano and sulfur)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Sorcerer", "Wizard"],
		description=(
			"A bright streak flashes from you to a point you choose within range and then blossoms with a low roar into a fiery explosion. "
			"Each creature in a 20-foot-radius Sphere centered on that point makes a Dexterity saving throw, taking 8d6 Fire damage on a failed save or half as much damage on a successful one.\n\n"
			"Flammable objects in the area that aren’t being worn or carried start burning.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d6 for each spell slot level above 3"
		),
		source=PHB,
		tags=["Evocation", "Damage", "Fire", "AOE", "Saving Throw"],
	),
	make_spell(
		name="Fly",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (a feather)",
		duration="10 minutes",
		concentration=True,
		class_names=["Artificer", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"You touch a willing creature. For the duration, the target gains a Fly Speed of 60 feet and can hover. "
			"When the spell ends, the target falls if it is still aloft unless it can stop the fall.\n\n"
			"Using a Higher-Level Spell Slot. You can target one additional creature for each spell slot level above 3."
		),
		source=PHB,
		tags=["Transmutation", "Buff", "Movement", "Concentration"],
	),
	make_spell(
		name="Gaseous Form",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (a bit of gauze)",
		duration="1 hour",
		concentration=True,
		class_names=["Sorcerer", "Warlock", "Wizard"],
		description=(
			"A willing creature you touch shape-shifts, along with everything it’s wearing and carrying, into a misty cloud for the duration. "
			"The spell ends on the target if it drops to 0 Hit Points or if it takes a Magic action to end the spell on itself.\n\n"
			"While in this form, the target’s only method of movement is a Fly Speed of 10 feet, and it can hover. "
			"The target can enter and occupy the space of another creature. The target has Resistance to Bludgeoning, Piercing, and Slashing damage; "
			"it has Immunity to the Prone condition; and it has Advantage on Strength, Dexterity, and Constitution saving throws. "
			"The target can pass through narrow openings, but it treats liquids as though they were solid surfaces.\n\n"
			"The target can’t talk or manipulate objects, and any objects it was carrying or holding can’t be dropped, used, or otherwise interacted with. "
			"Finally, the target can’t attack or cast spells.\n\n"
			"Using a Higher-Level Spell Slot. You can target one additional creature for each spell slot level above 3."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Movement", "Defense", "Concentration"],
	),
	make_spell(
		name="Glyph of Warding",
		casting_time="1 hour",
		ritual=False,
		range_str="Touch",
		components="V, S, M (powdered diamond worth 200+ GP, which the spell consumes)",
		duration="Until dispelled or triggered",
		concentration=False,
		class_names=["Artificer", "Bard", "Cleric", "Wizard"],
		description=(
			"You inscribe a glyph that later unleashes a magical effect. You inscribe it either on a surface (such as a table or a section of floor) "
			"or within an object that can be closed (such as a book or chest) to conceal the glyph. The glyph can cover an area no larger than 10 feet in diameter. "
			"If the surface or object is moved more than 10 feet from where you cast this spell, the glyph is broken, and the spell ends without being triggered.\n\n"
			"The glyph is nearly imperceptible and requires a successful Wisdom (Perception) check against your spell save DC to notice.\n\n"
			"When you inscribe the glyph, you set its trigger and choose whether it’s an explosive rune or a spell glyph, as explained below.\n\n"
			"Set the Trigger. You decide what triggers the glyph when you cast the spell. For glyphs inscribed on a surface, common triggers include touching or stepping on the glyph, removing another object covering it, or approaching within a certain distance of it. "
			"For glyphs inscribed within an object, common triggers include opening that object or seeing the glyph. Once a glyph is triggered, this spell ends.\n\n"
			"You can refine the trigger so that only creatures of certain types activate it (for example, the glyph could be set to affect Aberrations). "
			"You can also set conditions for creatures that don’t trigger the glyph, such as those who say a certain password.\n\n"
			"Explosive Rune. When triggered, the glyph erupts with magical energy in a 20-foot-radius Sphere centered on the glyph. Each creature in the area makes a Dexterity saving throw. "
			"A creature takes 5d8 Acid, Cold, Fire, Lightning, or Thunder damage (your choice when you create the glyph) on a failed save or half as much damage on a successful one.\n\n"
			"Spell Glyph. You can store a prepared spell of level 3 or lower in the glyph by casting it as part of creating the glyph. The spell must target a single creature or an area. The spell being stored has no immediate effect when cast in this way.\n\n"
			"When the glyph is triggered, the stored spell takes effect. If the spell has a target, it targets the creature that triggered the glyph. If the spell affects an area, the area is centered on that creature. "
			"If the spell summons Hostile creatures or creates harmful objects or traps, they appear as close as possible to the intruder and attack it. "
			"If the spell requires Concentration, it lasts until the end of its full duration.\n\n"
			"Using a Higher-Level Spell Slot. The damage of an explosive rune increases by 1d8 for each spell slot level above 3. "
			"If you create a spell glyph, you can store any spell of up to the same level as the spell slot you use for the Glyph of Warding."
		),
		source=PHB,
		tags=["Abjuration", "Utility", "Trap", "Damage", "Costly"],
	),
	make_spell(
		name="Haste",
		casting_time="Action",
		ritual=False,
		range_str="30 feet",
		components="V, S, M (a shaving of licorice root)",
		duration="1 minute",
		concentration=True,
		class_names=["Artificer", "Sorcerer", "Wizard"],
		description=(
			"Choose a willing creature that you can see within range. Until the spell ends, the target’s Speed is doubled, it gains a +2 bonus to Armor Class, "
			"it has Advantage on Dexterity saving throws, and it gains an additional action on each of its turns. "
			"That action can be used to take only the Attack (one attack only), Dash, Disengage, Hide, or Utilize action.\n\n"
			"When the spell ends, the target is Incapacitated and has a Speed of 0 until the end of its next turn, as a wave of lethargy washes over it."
		),
		source=PHB,
		tags=["Transmutation", "Buff", "Haste", "Concentration"],
	),
	make_spell(
		name="Hunger of Hadar",
		casting_time="Action",
		ritual=False,
		range_str="150 feet",
		components="V, S, M (a pickled tentacle)",
		duration="1 minute",
		concentration=True,
		class_names=["Warlock"],
		description=(
			"You open a gateway to the Far Realm, a region infested with unspeakable horrors. A 20-foot-radius Sphere of Darkness appears, centered on a point with range and lasting for the duration. "
			"The Sphere is Difficult Terrain, and it is filled with strange whispers and slurping noises, which can be heard up to 30 feet away. "
			"No light, magical or otherwise, can illuminate the area, and creatures fully within it have the Blinded condition.\n\n"
			"Any creature that starts its turn in the area takes 2d6 Cold damage. Any creature that ends its turn there must succeed on a Dexterity saving throw or take 2d6 Acid damage from otherworldly tentacles.\n\n"
			"Using a Higher-Level Spell Slot. The Cold or Acid damage (your choice) increases by 1d6 for each spell slot level above 3."
		),
		source=PHB,
		tags=["Conjuration", "Damage", "Cold", "Acid", "AOE", "Control", "Darkness", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Hypnotic Pattern",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="S, M (a pinch of confetti)",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"You create a twisting pattern of colors in a 30-foot Cube within range. The pattern appears for a moment and vanishes. "
			"Each creature in the area who can see the pattern must succeed on a Wisdom saving throw or have the Charmed condition for the duration. "
			"While Charmed, the creature has the Incapacitated condition and a Speed of 0.\n\n"
			"The spell ends for an affected creature if it takes any damage or if someone else uses an action to shake the creature out of its stupor."
		),
		source=PHB,
		tags=["Illusion", "Debuff", "Charm", "AOE", "Saving Throw", "Control", "Concentration"],
	),
	make_spell(
		name="Laeral's Silver Lance",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S, M (a silver pin worth 250+ GP)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Cleric", "Sorcerer", "Wizard"],
		description=(
			"Silver energy bursts out from you in a 120-foot-long, 5-foot-wide Line. Each creature of your choice in the Line makes a Strength saving throw. "
			"On a failed save, a creature takes 3d10 Force damage and has the Prone condition. On a successful save, a creature takes half as much damage only.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d10 for every spell slot level above 3."
		),
		source=FR,
		tags=["Evocation", "Damage", "Force", "AOE", "Line", "Saving Throw", "Prone"],
	),
	make_spell(
		name="Leomund's Tiny Hut",
		casting_time="1 minute or Ritual",
		ritual=True,
		range_str="Self",
		components="V, S, M (a crystal bead)",
		duration="8 hours",
		concentration=False,
		class_names=["Bard", "Wizard"],
		description=(
			"A 10-foot Emanation springs into existence around you and remains stationary for the duration. "
			"The spell fails when you cast it if the Emanation isn’t big enough to fully encapsulate all creatures in its area.\n\n"
			"Creatures and objects within the Emanation when you cast the spell can move through it freely. All other creatures and objects are barred from passing through it. "
			"Spells of level 3 or lower can’t be cast through it, and the effects of such spells can’t extend into it.\n\n"
			"The atmosphere inside the Emanation is comfortable and dry, regardless of the weather outside. "
			"Until the spell ends, you can command the interior to have Dim Light or Darkness (no action required). "
			"The Emanation is opaque from the outside and of any color you choose, but it’s transparent from the inside.\n\n"
			"The spell ends early if you leave the Emanation or if you cast it again."
		),
		source=PHB,
		tags=["Evocation", "Utility", "Defense", "Ritual"],
	),
	make_spell(
		name="Lightning Arrow",
		casting_time="Bonus Action",
		ritual=False,
		range_str="Self",
		components="V, S",
		duration="Instantaneous",
		concentration=False,
		class_names=["Ranger"],
		description=(
			"As your attack hits or misses the target, the weapon or ammunition you’re using transforms into a lightning bolt. "
			"Instead of taking any damage or other effects from the attack, the target takes 4d8 Lightning damage on a hit or half as much damage on a miss. "
			"Each creature within 10 feet of the target then makes a Dexterity saving throw, taking 2d8 Lightning damage on a failed save or half as much damage on a successful one.\n\n"
			"The weapon or ammunition then returns to its normal form.\n\n"
			"Using a Higher-Level Spell Slot. The damage for both effects of the spell increases by 1d8 for each spell slot level above 3."
		),
		source=PHB,
		tags=["Transmutation", "Damage", "Lightning", "AOE", "Attack", "Saving Throw"],
	),
	make_spell(
		name="Lightning Bolt",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S, M (a bit of fur and a crystal rod)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Sorcerer", "Wizard"],
		description=(
			"A stroke of lightning forming a 100-foot-long, 5-foot-wide Line blasts out from you in a direction you choose. "
			"Each creature in the Line makes a Dexterity saving throw, taking 8d6 Lightning damage on a failed save or half as much damage on a successful one.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d6 for each spell slot level above 3."
		),
		source=PHB,
		tags=["Evocation", "Damage", "Lightning", "AOE", "Saving Throw", "Line"],
	),
	make_spell(
		name="Magic Circle",
		casting_time="1 minute",
		ritual=False,
		range_str="10 feet",
		components="V, S, M (salt and powdered silver worth 100+ GP, which the spell consumes)",
		duration="1 hour",
		concentration=False,
		class_names=["Cleric", "Paladin", "Warlock", "Wizard"],
		description=(
			"You create a 10-foot-radius, 20-foot-tall Cylinder of magical energy centered on a point on the ground that you can see within range. "
			"Glowing runes appear wherever the Cylinder intersects with the floor or other surface.\n\n"
			"Choose one or more of the following types of creatures: Celestials, Elementals, Fey, Fiends, or Undead. "
			"The circle affects a creature of the chosen type in the following ways:\n\n"
			"The creature can’t willingly enter the Cylinder by nonmagical means. If the creature tries to use teleportation or interplanar travel to do so, it must first succeed on a Charisma saving throw.\n"
			"The creature has Disadvantage on attack rolls against targets within the Cylinder.\n"
			"Targets within the Cylinder can’t be possessed by or gain the Charmed or Frightened condition from the creature.\n\n"
			"Each time you cast this spell, you can cause its magic to operate in the reverse direction, preventing a creature of the specified type from leaving the Cylinder and protecting targets outside it.\n\n"
			"Using a Higher-Level Spell Slot. The duration increases by 1 hour for each spell slot level above 3."
		),
		source=PHB,
		tags=["Abjuration", "Utility", "Protection", "Costly"],
	),
	make_spell(
		name="Major Image",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="V, S, M (a bit of fleece)",
		duration="10 minutes",
		concentration=True,
		class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"You create the image of an object, a creature, or some other visible phenomenon that is no larger than a 20-foot Cube. "
			"The image appears at a spot that you can see within range and lasts for the duration. "
			"It seems real, including sounds, smells, and temperature appropriate to the thing depicted, but it can’t deal damage or cause conditions.\n\n"
			"If you are within range of the illusion, you can take a Magic action to cause the image to move to any other spot within range. "
			"As the image changes location, you can alter its appearance so that its movements appear natural for the image. "
			"For example, if you create an image of a creature and move it, you can alter the image so that it appears to be walking. "
			"Similarly, you can cause the illusion to make different sounds at different times, even making it carry on a conversation, for example.\n\n"
			"Physical interaction with the image reveals it to be an illusion, for things can pass through it. "
			"A creature that takes a Study action to examine the image can determine that it is an illusion with a successful Intelligence (Investigation) check against your spell save DC. "
			"If a creature discerns the illusion for what it is, the creature can see through the image, and its other sensory qualities become faint to the creature.\n\n"
			"Using a Higher-Level Spell Slot. The spell lasts until dispelled, without requiring Concentration, if cast with a level 4+ spell slot."
		),
		source=PHB,
		tags=["Illusion", "Utility", "Control", "Concentration"],
	),
	make_spell(
		name="Mass Healing Word",
		casting_time="Bonus Action",
		ritual=False,
		range_str="60 feet",
		components="V",
		duration="Instantaneous",
		concentration=False,
		class_names=["Bard", "Cleric"],
		description=(
			"Up to six creatures of your choice that you can see within range regain Hit Points equal to 2d4 plus your spellcasting ability modifier.\n\n"
			"Using a Higher-Level Spell Slot. The healing increases by 1d4 for each spell slot level above 3."
		),
		source=PHB,
		tags=["Abjuration", "Healing", "Buff"],
	),
	make_spell(
		name="Meld into Stone",
		casting_time="Action or Ritual",
		ritual=True,
		range_str="Touch",
		components="V, S",
		duration="8 hours",
		concentration=False,
		class_names=["Cleric", "Druid", "Ranger"],
		description=(
			"You step into a stone object or surface large enough to fully contain your body, merging yourself and your equipment with the stone for the duration. "
			"You must touch the stone to do so. Nothing of your presence remains visible or otherwise detectable by nonmagical senses.\n\n"
			"While merged with the stone, you can’t see what occurs outside it, and any Wisdom (Perception) checks you make to hear sounds outside it are made with Disadvantage. "
			"You remain aware of the passage of time and can cast spells on yourself while merged in the stone. "
			"You can use 5 feet of movement to leave the stone where you entered it, which ends the spell. You otherwise can’t move.\n\n"
			"Minor physical damage to the stone doesn’t harm you, but its partial destruction or a change in its shape (to the extent that you no longer fit within it) expels you and deals 6d6 Force damage to you. "
			"The stone’s complete destruction (or transmutation into a different substance) expels you and deals 50 Force damage to you. "
			"If expelled, you move into an unoccupied space closest to where you first entered and have the Prone condition."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Ritual", "Defense"],
	),
	make_spell(
		name="Nondetection",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (a pinch of diamond dust worth 25+ GP, which the spell consumes)",
		duration="8 hours",
		concentration=False,
		class_names=["Bard", "Ranger", "Wizard"],
		description=(
			"For the duration, you hide a target that you touch from Divination spells. "
			"The target can be a willing creature, or it can be a place or an object no larger than 10 feet in any dimension. "
			"The target can’t be targeted by any Divination spell or perceived through magical scrying sensors."
		),
		source=PHB,
		tags=["Abjuration", "Utility", "Costly"],
	),
	make_spell(
		name="Phantom Steed",
		casting_time="1 minute or Ritual",
		ritual=True,
		range_str="30 feet",
		components="V, S",
		duration="1 hour",
		concentration=False,
		class_names=["Wizard"],
		description=(
			"A Large, quasi-real, horselike creature appears on the ground in an unoccupied space of your choice within range. "
			"You decide the creature’s appearance, and it is equipped with a saddle, bit, and bridle. "
			"Any of the equipment created by the spell vanishes in a puff of smoke if it is carried more than 10 feet away from the steed.\n\n"
			"For the duration, you or a creature you choose can ride the steed. The steed uses the Riding Horse stat block, except it has a Speed of 100 feet and can travel 13 miles in an hour. "
			"When the spell ends, the steed gradually fades, giving the rider 1 minute to dismount. The spell ends early if the steed takes any damage."
		),
		source=PHB,
		tags=["Illusion", "Utility", "Movement", "Ritual"],
	),
	make_spell(
		name="Plant Growth",
		casting_time="Action (Overgrowth) or 8 hours (Enrichment)",
		ritual=False,
		range_str="150 feet",
		components="V, S",
		duration="Instantaneous",
		concentration=False,
		class_names=["Bard", "Druid", "Ranger"],
		description=(
			"This spell channels vitality into plants. The casting time you use determines whether the spell has the Overgrowth or the Enrichment effect below.\n\n"
			"Overgrowth. Choose a point within range. All normal plants in a 100-foot-radius Sphere centered on that point become thick and overgrown. "
			"A creature moving through that area must spend 4 feet of movement for every 1 foot it moves. "
			"You can exclude one or more areas of any size within the spell’s area from being affected.\n\n"
			"Enrichment. All plants in a half-mile radius centered on a point within range become enriched for 365 days. "
			"The plants yield twice the normal amount of food when harvested. They can benefit from only one Plant Growth per year."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Control", "Terrain"],
	),
	make_spell(
		name="Protection from Energy",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S",
		duration="1 hour",
		concentration=True,
		class_names=["Artificer", "Cleric", "Druid", "Ranger", "Sorcerer", "Wizard"],
		description=(
			"For the duration, the willing creature you touch has Resistance to one damage type of your choice: Acid, Cold, Fire, Lightning, or Thunder."
		),
		source=PHB,
		tags=["Abjuration", "Buff", "Resistance", "Concentration"],
	),
	make_spell(
		name="Remove Curse",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S",
		duration="Instantaneous",
		concentration=False,
		class_names=["Cleric", "Paladin", "Warlock", "Wizard"],
		description=(
			"At your touch, all curses affecting one creature or object end. If the object is a cursed magic item, its curse remains, "
			"but the spell breaks its owner’s Attunement to the object so it can be removed or discarded."
		),
		source=PHB,
		tags=["Abjuration", "Utility"],
	),
	make_spell(
		name="Revivify",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, S, M (a diamond worth 300+ GP, which the spell consumes)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Artificer", "Cleric", "Druid", "Paladin", "Ranger"],
		description=(
			"You touch a creature that has died within the last minute. That creature revives with 1 Hit Point. "
			"This spell can’t revive a creature that has died of old age, nor does it restore any missing body parts."
		),
		source=PHB,
		tags=["Necromancy", "Healing", "Costly"],
	),
	make_spell(
		name="Sending",
		casting_time="Action",
		ritual=False,
		range_str="Unlimited",
		components="V, S, M (a copper wire)",
		duration="Instantaneous",
		concentration=False,
		class_names=["Bard", "Cleric", "Wizard"],
		description=(
			"You send a short message of 25 words or fewer to a creature you have met or a creature described to you by someone who has met it. "
			"The target hears the message in its mind, recognizes you as the sender if it knows you, and can answer in a like manner immediately. "
			"The spell enables targets to understand the meaning of your message.\n\n"
			"You can send the message across any distance and even to other planes of existence, but if the target is on a different plane than you, there is a 5 percent chance that the message doesn’t arrive. "
			"You know if the delivery fails.\n\n"
			"Upon receiving your message, a creature can block your ability to reach it again with this spell for 8 hours. "
			"If you try to send another message during that time, you learn that you are blocked, and the spell fails."
		),
		source=PHB,
		tags=["Divination", "Utility", "Communication"],
	),
	make_spell(
		name="Sleet Storm",
		casting_time="Action",
		ritual=False,
		range_str="150 feet",
		components="V, S, M (a miniature umbrella)",
		duration="1 minute",
		concentration=True,
		class_names=["Druid", "Sorcerer", "Wizard"],
		description=(
			"Until the spell ends, sleet falls in a 40-foot-tall, 20-foot-radius Cylinder centered on a point you choose within range. "
			"The area is Heavily Obscured, and exposed flames in the area are doused.\n\n"
			"Ground in the Cylinder is Difficult Terrain. When a creature enters the Cylinder for the first time on a turn or starts its turn there, "
			"it must succeed on a Dexterity saving throw or have the Prone condition and lose Concentration."
		),
		source=PHB,
		tags=["Conjuration", "Control", "AOE", "Saving Throw", "Concentration", "Terrain"],
	),
	make_spell(
		name="Slow",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="V, S, M (a drop of molasses)",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Sorcerer", "Wizard"],
		description=(
			"You alter time around up to six creatures of your choice in a 40-foot Cube within range. Each target must succeed on a Wisdom saving throw or be affected by this spell for the duration.\n\n"
			"An affected target’s Speed is halved, it takes a −2 penalty to AC and Dexterity saving throws, and it can’t take Reactions. "
			"On its turns, it can take either an action or a Bonus Action, not both, and it can make only one attack if it takes the Attack action. "
			"If it casts a spell with a Somatic component, there is a 25 percent chance the spell fails as a result of the target making the spell’s gestures too slowly.\n\n"
			"An affected target repeats the save at the end of each of its turns, ending the spell on itself on a success."
		),
		source=PHB,
		tags=["Transmutation", "Debuff", "Control", "AOE", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Speak with Dead",
		casting_time="Action",
		ritual=False,
		range_str="10 feet",
		components="V, S, M (burning incense)",
		duration="10 minutes",
		concentration=False,
		class_names=["Bard", "Cleric", "Wizard"],
		description=(
			"You grant the semblance of life to a corpse of your choice within range, allowing it to answer questions you pose. "
			"The corpse must have a mouth, and this spell fails if the deceased creature was Undead when it died. "
			"The spell also fails if the corpse was the target of this spell within the past 10 days.\n\n"
			"Until the spell ends, you can ask the corpse up to five questions. The corpse knows only what it knew in life, including the languages it knew. "
			"Answers are usually brief, cryptic, or repetitive, and the corpse is under no compulsion to offer a truthful answer if you are antagonistic toward it or it recognizes you as an enemy. "
			"This spell doesn’t return the creature’s soul to its body, only its animating spirit. Thus, the corpse can’t learn new information, doesn’t comprehend anything that has happened since it died, and can’t speculate about future events."
		),
		source=PHB,
		tags=["Necromancy", "Utility", "Communication"],
	),
	make_spell(
		name="Speak with Plants",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S",
		duration="10 minutes",
		concentration=False,
		class_names=["Bard", "Druid", "Ranger"],
		description=(
			"You imbue plants in an immobile 30-foot Emanation with limited sentience and animation, giving them the ability to communicate with you and follow your simple commands. "
			"You can question plants about events in the spell’s area within the past day, gaining information about creatures that have passed, weather, and other circumstances.\n\n"
			"You can also turn Difficult Terrain caused by plant growth (such as thickets and undergrowth) into ordinary terrain that lasts for the duration. "
			"Or you can turn ordinary terrain where plants are present into Difficult Terrain that lasts for the duration.\n\n"
			"The spell doesn’t enable plants to uproot themselves and move about, but they can move their branches, tendrils, and stalks for you.\n\n"
			"If a Plant creature is in the area, you can communicate with it as if you shared a common language."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Communication", "Control"],
	),
	make_spell(
		name="Spirit Guardians",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S, M (a prayer scroll)",
		duration="10 minutes",
		concentration=True,
		class_names=["Cleric"],
		description=(
			"Protective spirits flit around you in a 15-foot Emanation for the duration. "
			"If you are good or neutral, their spectral form appears angelic or fey (your choice). If you are evil, they appear fiendish.\n\n"
			"When you cast this spell, you can designate creatures to be unaffected by it. "
			"Any other creature’s Speed is halved in the Emanation, and whenever the Emanation enters a creature’s space and whenever a creature enters the Emanation or ends its turn there, the creature must make a Wisdom saving throw. "
			"On a failed save, the creature takes 3d8 Radiant damage (if you are good or neutral) or 3d8 Necrotic damage (if you are evil). "
			"On a successful save, the creature takes half as much damage. A creature makes this save only once per turn.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d8 for each spell slot level above 3."
		),
		source=PHB,
		tags=["Conjuration", "Damage", "Radiant", "Necrotic", "AOE", "Saving Throw", "Concentration"],
	),
	make_spell(
		name="Stinking Cloud",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (a rotten egg)",
		duration="1 minute",
		concentration=True,
		class_names=["Bard", "Sorcerer", "Wizard"],
		description=(
			"You create a 20-foot-radius Sphere of yellow, nauseating gas centered on a point within range. The cloud is Heavily Obscured. "
			"The cloud lingers in the air for the duration or until a strong wind (such as the one created by Gust of Wind) disperses it.\n\n"
			"Each creature that starts its turn in the Sphere must succeed on a Constitution saving throw or have the Poisoned condition until the end of the current turn. "
			"While Poisoned in this way, the creature can’t take an action or a Bonus Action."
		),
		source=PHB,
		tags=["Conjuration", "Control", "AOE", "Saving Throw", "Poison", "Debuff", "Concentration"],
	),
	make_spell(
		name="Summon Fey",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (a gilded flower worth 300+ GP)",
		duration="1 hour",
		concentration=True,
		class_names=["Druid", "Ranger", "Warlock", "Wizard"],
		description=(
			"You call forth a Fey spirit. It manifests in an unoccupied space that you can see within range and uses the Fey Spirit stat block. "
			"When you cast the spell, choose a mood: Fuming, Mirthful, or Tricksy. The creature resembles a Fey creature of your choice marked by the chosen mood, which determines certain details in its stat block. "
			"The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
			"The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
			"It obeys your verbal commands (no action required by you). If you don’t issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
			"Using a Higher-Level Spell Slot. Use the spell slot’s level for the spell’s level in the stat block."
		),
		source=PHB,
		tags=["Conjuration", "Summon", "Fey", "Concentration"],
	),
	make_spell(
		name="Summon Undead",
		casting_time="Action",
		ritual=False,
		range_str="90 feet",
		components="V, S, M (a gilded skull worth 300+ GP)",
		duration="1 hour",
		concentration=True,
		class_names=["Warlock", "Wizard"],
		description=(
			"You call forth an Undead spirit. It manifests in an unoccupied space that you can see within range and uses the Undead Spirit stat block. "
			"When you cast the spell, choose the creature’s form: Ghostly, Putrid, or Skeletal. "
			"The spirit resembles an Undead creature with the chosen form, which determines certain details in its stat block. "
			"The creature disappears when it drops to 0 Hit Points or when the spell ends.\n\n"
			"The creature is an ally to you and your allies. In combat, the creature shares your Initiative count, but it takes its turn immediately after yours. "
			"It obeys your verbal commands (no action required by you). If you don’t issue any, it takes the Dodge action and uses its movement to avoid danger.\n\n"
			"Using a Higher-Level Spell Slot. Use the spell slot’s level for the spell’s level in the stat block."
		),
		source=PHB,
		tags=["Necromancy", "Summon", "Undead", "Concentration"],
	),
	make_spell(
		name="Sylune's Viper",
		casting_time="Bonus Action",
		ritual=False,
		range_str="Self",
		components="V, S, M (a snake fang)",
		duration="1 hour",
		concentration=False,
		class_names=["Druid", "Wizard"],
		description=(
			"A shimmering, spectral snake encircles your body for the duration. You gain 15 Temporary Hit Points; the spell ends early if you have no Temporary Hit Points left.\n\n"
			"While the spell is active, you gain the following benefits:\n\n"
			"Climbing. You gain a Climb Speed equal to your Speed.\n\n"
			"Venomous Bite. As a Magic action, you can make a ranged spell attack using the snake against one creature within 50 feet. "
			"On a hit, the target takes 1d6 Force damage and has the Poisoned condition until the start of your next turn. "
			"While Poisoned, the target has the Incapacitated condition.\n\n"
			"Using a Higher-Level Spell Slot. For each spell slot level above 3, the number of Temporary Hit Points you gain from this spell increases by 5, and the damage of Venomous Bite increases by 1d6."
		),
		source=FR,
		tags=["Conjuration", "Buff", "Defense", "Force", "Poisoned", "Temp HP"],
	),
	make_spell(
		name="Tongues",
		casting_time="Action",
		ritual=False,
		range_str="Touch",
		components="V, M (a miniature ziggurat)",
		duration="1 hour",
		concentration=False,
		class_names=["Bard", "Cleric", "Sorcerer", "Warlock", "Wizard"],
		description=(
			"This spell grants the creature you touch the ability to understand any spoken or signed language that it hears or sees. "
			"Moreover, when the target communicates by speaking or signing, any creature that knows at least one language can understand it if that creature can hear the speech or see the signing."
		),
		source=PHB,
		tags=["Divination", "Utility", "Communication"],
	),
	make_spell(
		name="Vampiric Touch",
		casting_time="Action",
		ritual=False,
		range_str="Self",
		components="V, S",
		duration="1 minute",
		concentration=True,
		class_names=["Sorcerer", "Warlock", "Wizard"],
		description=(
			"The touch of your shadow-wreathed hand can siphon life force from others to heal your wounds. Make a melee spell attack against one creature within reach. "
			"On a hit, the target takes 3d6 Necrotic damage, and you regain Hit Points equal to half the amount of Necrotic damage dealt.\n\n"
			"Until the spell ends, you can make the attack again on each of your turns as a Magic action, targeting the same creature or a different one.\n\n"
			"Using a Higher-Level Spell Slot. The damage increases by 1d6 for each spell slot level above 3."
		),
		source=PHB,
		tags=["Necromancy", "Damage", "Healing", "Attack", "Concentration"],
	),
	make_spell(
		name="Water Breathing",
		casting_time="Action or Ritual",
		ritual=True,
		range_str="30 feet",
		components="V, S, M (a short reed)",
		duration="24 hours",
		concentration=False,
		class_names=["Artificer", "Druid", "Ranger", "Sorcerer", "Wizard"],
		description=(
			"This spell grants up to ten willing creatures of your choice within range the ability to breathe underwater until the spell ends. "
			"Affected creatures also retain their normal mode of respiration."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Ritual"],
	),
	make_spell(
		name="Water Walk",
		casting_time="Action or Ritual",
		ritual=True,
		range_str="30 feet",
		components="V, S, M (a piece of cork)",
		duration="1 hour",
		concentration=False,
		class_names=["Artificer", "Cleric", "Druid", "Ranger", "Sorcerer"],
		description=(
			"This spell grants the ability to move across any liquid surface - such as water, acid, mud, snow, quicksand, or lava - as if it were harmless solid ground (creatures crossing molten lava can still take damage from the heat). "
			"Up to ten willing creatures of your choice within range gain this ability for the duration.\n\n"
			"An affected target must take a Bonus Action to pass from the liquid’s surface into the liquid itself and vice versa, but if the target falls into the liquid, the target passes through the surface into the liquid below."
		),
		source=PHB,
		tags=["Transmutation", "Utility", "Ritual", "Movement"],
	),
	make_spell(
		name="Wind Wall",
		casting_time="Action",
		ritual=False,
		range_str="120 feet",
		components="V, S, M (a fan and a feather)",
		duration="1 minute",
		concentration=True,
		class_names=["Druid", "Ranger"],
		description=(
			"A wall of strong wind rises from the ground at a point you choose within range. You can make the wall up to 50 feet long, 15 feet high, and 1 foot thick. "
			"You can shape the wall in any way you choose so long as it makes one continuous path along the ground. The wall lasts for the duration.\n\n"
			"When the wall appears, each creature in its area makes a Strength saving throw, taking 4d8 Bludgeoning damage on a failed save or half as much damage on a successful one.\n\n"
			"The strong wind keeps fog, smoke, and other gases at bay. Small or smaller flying creatures or objects can’t pass through the wall. "
			"Loose, lightweight materials brought into the wall fly upward. Arrows, bolts, and other ordinary projectiles launched at targets behind the wall are deflected upward and miss automatically. "
			"Boulders hurled by Giants or siege engines, and similar projectiles, are unaffected. Creatures in gaseous form can’t pass through it."
		),
		source=PHB,
		tags=["Evocation", "Damage", "Control", "AOE", "Saving Throw", "Bludgeoning", "Concentration"],
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
