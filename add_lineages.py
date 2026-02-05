"""Script to add new lineages to lineages.json"""
import json

# Load existing lineages
with open('lineages.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# New lineages to add
new_lineages = [
    {
        "name": "Changeling",
        "description": "With ever-changing appearances, changelings reside in many societies undetected. Each changeling can supernaturally adopt any face they like. For some changelings, a new face may reveal an aspect of their soul.\n\nThe first changelings in the multiverse appeared in the Feywild, and the wondrous, mutable essence of that plane lingers in changelings today - even in those who have never set foot in the fey realm.\n\nIn their true form, changelings appear faded, their features almost devoid of detail. It is rare to see one in that form, for a typical changeling alters their shape the way others might change clothes. However, many changelings develop identities with more depth, crafting a persona complete with history and beliefs to go with each shape. A changeling adventurer might have personas for many situations, including negotiation, investigation, and combat.\n\nMultiple changelings can share a persona. Personas can even pass down through a family, allowing a younger changeling to take advantage of contacts established by the persona's previous users.",
        "creature_type": "Fey",
        "size": "Medium or Small",
        "speed": 30,
        "traits": [
            {
                "name": "Changeling Instincts",
                "description": "Thanks to your connection to the fey realm, you gain proficiency in two of the following skills of your choice: Deception, Insight, Intimidation, Performance, or Persuasion."
            },
            {
                "name": "Shape-Shifter",
                "description": "As an action, you can shape-shift to change your appearance and your voice. You determine the specifics of the changes, including your coloration, hair length, and sex. You can also adjust your height and weight and can change your size between Medium and Small. You can make yourself appear as a member of another playable species, though none of your game statistics change. You can't duplicate the appearance of an individual you've never seen, and you must adopt a form that has the same basic arrangement of limbs that you have. This trait doesn't change your clothing and equipment.\n\nWhile shape-shifted with this trait, you have Advantage on Charisma checks.\n\nYou stay in the new form until you take an action to revert to your true form."
            }
        ],
        "source": "Eberron - Forge of the Artificer",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Kalashtar",
        "description": "Kalashtar (pronounced kal-ASH-tar) are created from the union of humanity and renegade spirits called quori from the plane of dreams. Kalashtar appear human, but their spiritual connection affects them in a variety of ways. They have symmetrical, slightly angular features, and their eyes often glow when they are concentrating or expressing strong emotions.\n\nKalashtar can't communicate directly with their quori spirits. Rather, kalashtar might experience them as a source of instinct and inspiration, drawing on the spirits' memories when the kalashtar sleep. This connection grants kalashtar minor psionic abilities, as well as protection from psionic attacks.",
        "creature_type": "Aberration",
        "size": "Medium",
        "speed": 30,
        "traits": [
            {"name": "Dual Mind", "description": "You have Advantage on Wisdom and Charisma saving throws."},
            {"name": "Mental Discipline", "description": "You have Resistance to Psychic damage."},
            {"name": "Mind Link", "description": "You have telepathy with a range in feet equal to 10 times your level. When you're using this trait to speak telepathically to a creature, you can take a Magic action to give that creature the ability to speak telepathically with you for 1 hour or until you take another Magic action to end this effect."},
            {"name": "Severed from Dreams", "description": "You can't be the target of the Dream spell. In addition, when you finish a Long Rest, you gain proficiency in one skill of your choice. This proficiency lasts until you finish another Long Rest."}
        ],
        "source": "Eberron - Forge of the Artificer",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Khoravar",
        "description": "Over the course of centuries, those descended from both humans and elves have developed their own communities and traditions in Khorvaire. The rise of House Lyrandar and House Medani has strengthened this identity. Members of these communities call themselves Khoravar, an Elvish term meaning \"children of Khorvaire,\" as they dislike the term \"half-elf.\"\n\nMany Khoravar espouse the idea of being \"the bridge between,\" believing they are called to facilitate communication and cooperation between members of different cultures or species. Khoravar who follow this philosophy often become bards, diplomats, mediators, or translators. Others, fascinated by their distant connection to the Fey, seek to build bridges between the Material Plane and the Feywild of Thelanis. These Khoravar often become druids or warlocks with archfey patrons.",
        "creature_type": "Humanoid",
        "size": "Medium or Small",
        "speed": 30,
        "traits": [
            {"name": "Darkvision", "description": "You have Darkvision with a range of 60 feet."},
            {"name": "Fey Ancestry", "description": "You have Advantage on saving throws you make to avoid or end the Charmed condition."},
            {"name": "Fey Gift", "description": "You know the Friends cantrip. Whenever you finish a Long Rest, you can replace that cantrip with a different cantrip from the Cleric, Druid, or Wizard spell list. Intelligence, Wisdom, or Charisma is your spellcasting ability for the spell you cast with this trait (chosen when you select this species)."},
            {"name": "Lethargy Resilience", "description": "When you fail a saving throw to avoid or end the Unconscious condition, you can succeed instead. Once you use this trait, you can't do so again until you finish 1d4 Long Rests."},
            {"name": "Skill Versatility", "description": "You gain proficiency in one skill or with one tool of your choice. Whenever you finish a Long Rest, you can replace it with another skill or tool proficiency."}
        ],
        "source": "Eberron - Forge of the Artificer",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Shifter",
        "description": "Shifters - sometimes called \"weretouched\" - descend from people who contracted full or partial lycanthropy. Humanoids with a bestial aspect, shifters can't change shape fully, but they can enhance their animalistic features temporarily in a process they call \"shifting.\"\n\nShifters resemble humans in height and build but are typically more lithe and flexible. Their facial features have a bestial cast, often with large eyes and pointed ears; most shifters also possess prominent canine teeth. They grow fur-like hair on nearly every part of their bodies. While a shifter's appearance might remind an onlooker of an animal, the shifter remains clearly identifiable as a Humanoid even when at their most feral.",
        "creature_type": "Humanoid",
        "size": "Medium or Small",
        "speed": 30,
        "traits": [
            {"name": "Bestial Instincts", "description": "Channeling the beast within, you gain proficiency in one of the following skills of your choice: Acrobatics, Athletics, Intimidation, or Survival."},
            {"name": "Darkvision", "description": "You have Darkvision with a range of 60 feet."},
            {"name": "Shifting", "description": "As a Bonus Action, you can shape-shift to assume a more bestial appearance. This transformation lasts for 1 minute or until you revert to your normal appearance as a Bonus Action. When you shift, you gain Temporary Hit Points equal to 2 times your Proficiency Bonus. You can shift a number of times equal to your Proficiency Bonus, and you regain all expended uses when you finish a Long Rest.\n\nWhenever you shift, you gain the benefit of one of the following options (choose when you select this species):\n\n**Beasthide.** You gain 1d6 additional Temporary Hit Points. While shifted, you have a +1 bonus to your Armor Class.\n\n**Longtooth.** When you shift and as a Bonus Action on your other turns while shifted, you can use your elongated fangs to make an Unarmed Strike. If you hit with this Unarmed Strike and deal damage, you can deal Piercing damage equal to 1d6 plus your Strength modifier, instead of the normal damage of an Unarmed Strike.\n\n**Swiftstride.** While you are shifted, your Speed increases by 10 feet. Additionally, you can move up to 10 feet as a Reaction when a creature ends its turn within 5 feet of you. This reactive movement doesn't provoke Opportunity Attack action.\n\n**Wildhunt.** While shifted, you have Advantage on Wisdom checks. Additionally, no creature within 30 feet of you can have Advantage on an attack roll against you unless you have the Incapacitated condition."}
        ],
        "source": "Eberron - Forge of the Artificer",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Warforged",
        "description": "Warforged are mechanical beings built as weapons to fight in the Last War. An unexpected breakthrough produced sentient beings made from wood and metal that nevertheless can feel pain and emotion.\n\nWarforged comprise a blend of organic and inorganic materials. Rootlike cords infused with alchemical fluids serve as their muscles, wrapped around a framework of steel, darkwood, or stone. Armored plates form a protective outer shell and reinforce joints. The more a warforged cultivates their individuality, the more likely they are to modify their body, seeking out an artificer to customize the look of their face, limbs, and plating.",
        "creature_type": "Construct",
        "size": "Medium or Small",
        "speed": 30,
        "traits": [
            {"name": "Construct Resilience", "description": "You have Resistance to Poison damage. You also have Advantage on saving throws to avoid or end the Poisoned condition."},
            {"name": "Integrated Protection", "description": "You gain a +1 bonus to your Armor Class. In addition, armor you have donned can't be removed against your will while you're alive."},
            {"name": "Sentry's Rest", "description": "You don't need to sleep, and magic can't put you to sleep. You can finish a Long Rest in 6 hours if you spend those hours in an inactive, motionless state. During this time, you appear inert but remain conscious."},
            {"name": "Specialized Design", "description": "You gain one skill proficiency and one tool proficiency of your choice."},
            {"name": "Tireless", "description": "You don't gain Exhaustion levels from dehydration, malnutrition, or suffocation."}
        ],
        "source": "Eberron - Forge of the Artificer",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Boggart",
        "description": "Boggarts are Small, squat goblinoids found in the realm of Lorwyn-Shadowmoor. They possess bestial physical features, including horns and animal-like snouts. Beyond these commonalities, boggart appearances vary widely. One boggart may look like a hedgehog, with spiky fur and beady eyes, while another might sport the snout and fleshy ears of a swine. Boggarts tend to love crafting potions and commonly gravitate to specific areas of expertise.\n\n**In Lorwyn**\nBoggarts in Lorwyn are born into communal warrens where laws and hierarchies are considered suggestions. The oldest and most powerful boggarts, known as \"aunties,\" serve as respected leaders who keep the peace. Lorwyn boggarts value sharing knowledge and past experiences with their communities. Many are willing to brave great dangers in pursuit of new experiences, and adventurers are common.\n\nLorwyn boggarts also have a knack for magic. Boggarts who feel drawn to learning and using these natural affinities often become Druids. A Lorwyn boggart might alternatively find a calling as a Ranger, especially the Fey Wanderer subclass, or as a Wizard, especially the Diviner subclass, as boggarts have proven fond of ascertaining information through divination magic.\n\n**In Shadowmoor**\nBoggarts in Shadowmoor generally have sharper physical features than Lorwyn boggarts, including additional sets of horns. They are also known for body modifications, such as riveting armored plates to their flesh. Shadowmoor boggart society is chaotic and decentralized; their communities are few and likely to be found in isolated or dangerous environments. Aunties in Shadowmoor wander the lands, greeting those they meet with arbitrary tests, boons, or even curses.\n\nLike their Lorwyn counterparts, Shadowmoor boggarts are drawn to magic. These boggarts might become Warlocks, particularly leaning toward the Archfey Patron subclass; some might believe their patron is Isilu. Others prove to be Sorcerers and are especially likely to manifest their power in the form of the Wild Magic Sorcery subclass.",
        "creature_type": "Humanoid",
        "size": "Small",
        "speed": 30,
        "traits": [
            {"name": "Darkvision", "description": "You can see in dim light within 60 feet of you as if it were bright light and in darkness as if it were dim light. You discern colors in that darkness only as shades of gray."},
            {"name": "Fey Ancestry", "description": "You have advantage on saving throws you make to avoid or end the charmed condition on yourself."},
            {"name": "Fury of the Small", "description": "When you damage a creature with an attack or a spell and the creature's size is larger than yours, you can cause the attack or spell to deal extra damage to the creature. The extra damage equals your proficiency bonus.\n\nYou can use this trait a number of times equal to your proficiency bonus, regaining all expended uses when you finish a long rest, and you can use it no more than once per turn."},
            {"name": "Nimble Escape", "description": "You can take the Disengage or Hide action as a bonus action on each of your turns."}
        ],
        "source": "Lorwyn - First Light",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Faerie",
        "description": "Known for their mischief, faeries resemble insects with humanoid features. Their size and shape may vary, but all have antennae, black eyes, chitinous skin, and insectoid legs and wings. Every faerie is born from a flower and possesses innate magic, which many use to play pranks.\n\nSome Lorwyn faeries serve Queen Oura, who has proclaimed herself the faeries' ruler. Not all faeries recognize Oura's authority, however. In Shadowmoor, faeries might instead worship Queen Maralen, the elf who overthrew the previous faerie queen and, some say, ushered in the clashing of Lorwyn and Shadowmoor.",
        "creature_type": "Fey",
        "size": "Small",
        "speed": 30,
        "traits": [
            {"name": "Fairy Magic", "description": "You know the Druidcraft cantrip.\n\nStarting at 3rd level, you can cast the Faerie Fire spell with this trait. Starting at 5th level, you can also cast the Enlarge/Reduce spell with this trait. Once you cast Faerie Fire or Enlarge/Reduce with this trait, you can't cast that spell with it again until you finish a long rest. You can also cast either of those spells using any spell slots you have of the appropriate level.\n\nIntelligence, Wisdom, or Charisma is your spellcasting ability for these spells when you cast them with this trait (choose when you select this race)."},
            {"name": "Flight", "description": "Because of your wings, you have a flying speed equal to your walking speed. You can't use this flying speed if you're wearing medium or heavy armor.\n\nIn addition, Shadowmoor faeries have Darkvision with a range of 120 feet."}
        ],
        "source": "Lorwyn - First Light",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Flamekin",
        "description": "Flamekin are people made from two key elements of creation: fire and stone. As a result, many flamekin feel a strong connection to the natural world. Flamekin's bodies radiate harmless magical flames, though they possess innate magic that allows them to create burning flames in a multitude of forms.\n\nFlamekin view self-discovery and self-expression the noblest of aspirations and believe that self-realization is the most important thing an individual can do with their life. Flamekin call this lifelong pursuit the Path of Flame.\n\nFlamekin dwell in either Lorwyn or Shadowmoor. Physically and culturally, they are similar in both lands.",
        "creature_type": "Humanoid",
        "size": "Medium or Small",
        "speed": 30,
        "traits": [
            {"name": "Darkvision", "description": "You can see in dim light within 60 feet of you as if it were bright light and in darkness as if it were dim light. You discern colors in that darkness only as shades of gray."},
            {"name": "Fire Resistance", "description": "You have resistance to fire damage."},
            {"name": "Reach to the Blaze", "description": "You know the Produce Flame cantrip. Starting at 3rd level, you can cast the Burning Hands spell with this trait. Starting at 5th level, you can also cast the Flame Blade spell with this trait, without requiring a material component. Once you cast Burning Hands or Flame Blade with this trait, you can't cast that spell with it again until you finish a long rest. You can also cast either of those spells using any spell slots you have of the appropriate level.\n\nIntelligence, Wisdom, or Charisma is your spellcasting ability for these spells when you cast them with this trait (choose when you select this race)."}
        ],
        "source": "Lorwyn - First Light",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Lorwyn Changeling",
        "description": "The changelings of Lorwyn are charismatic shapeshifters able to crudely mimic the forms of creatures and plants. Unlike most shapeshifters, however, their innate powers don't allow them to truly disguise themselves; rather, their transformations are purely surface level.\n\nNo matter their form, Lorwyn changelings keep their key traits: blue-green skin, tufts of tentacle-like fur, and bulbous yellow eyes with slitted pupils. The true changeling identity of a bug-eyed tree, teal elk, or furry boulder is always easy to spot. These counterfeits are so plain that many Lorwyn denizens find the effect inexplicably charming.\n\nChangelings from Lorwyn live in a vast, mystical cave called Velis Vel Grotto. Once per year, many changelings make a pilgrimage to the grotto to contemplate their past deeds.",
        "creature_type": "Fey",
        "size": "Medium or Small",
        "speed": 30,
        "traits": [
            {"name": "Shape Self", "description": "As an action, you can reshape your body to a two-legged Humanoid shape or to a four-legged Beast shape. While you have a Humanoid shape, you can wear clothing and armor made for a Humanoid of your size."},
            {"name": "Darkvision", "description": "You have Darkvision with a range of 120 feet."},
            {"name": "Delightful Imitator", "description": "You have proficiency in the Performance skill."},
            {"name": "Unpredictable Movement", "description": "When you roll Initiative and don't have Disadvantage on that roll, you can take the Dash action as a Reaction."}
        ],
        "source": "Lorwyn - First Light",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Rimekin",
        "description": "Rimekin hail from both Lorwyn and Shadowmoor, though the first rimekin arose from flamekin during the Phyrexian invasion. These flamekin approached their problems with cold logic and rejected reactionary responses. As a result, the magical flames that engulfed their bodies took on a frigid air, and they became rimekin.\n\nLike flamekin, rimekin possess innate magic, but the flames they conjure burn icy blue rather than red hot. Further, these \"flames\" emanate a chilling cold rather than blazing heat. This effect extends, superficially, to the items rimekin touch. Any armor worn or weapons wielded by rimekin become coated in layers of spiky yet harmless hoarfrost.",
        "creature_type": "Humanoid",
        "size": "Medium or Small",
        "speed": 30,
        "traits": [
            {"name": "Cold Fire Magic", "description": "You know the Ray of Frost cantrip. When you reach character levels 3 and 5, you learn the Ice Knife spell and the Flame Blade spell, respectively. You always have those spells prepared. You can cast each once without a spell slot, and you regain the ability to cast these spells in this way when you finish a Long Rest. You can also cast the spells using any spell slots you have of the appropriate level. When you cast Flame Blade using this trait, the spell deals Cold damage instead of Fire damage.\n\nIntelligence, Wisdom, or Charisma is your spellcasting ability for these spells (choose the ability when you select this species)."},
            {"name": "Cold Resistance", "description": "You have Resistance to Cold damage."},
            {"name": "Darkvision", "description": "You have Darkvision with a range of 60 feet."}
        ],
        "source": "Lorwyn - First Light",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    },
    {
        "name": "Dhampir",
        "description": "Dhampirs are living people who possess vampiric prowess but are cursed with macabre hunger. Most dhampirs thirst for blood, but some gain sustenance from dreams, life energy, or other vital sources. Dhampirs must choose whether to fight to control their hunger or give in to predatory urges.\n\nDhampirs often arise from encounters with vampires; some are the descendants of a powerful vampire, while others are partially transformed by a vampire's bite. All manner of macabre bargains and necromantic influences might also give rise to a dhampir. Regardless of their origins, dhampirs exhibit their vampiric nature in various ways, including increased speed and a life-draining bite.",
        "creature_type": "Humanoid",
        "size": "Medium or Small",
        "speed": 35,
        "traits": [
            {"name": "Darkvision", "description": "You have Darkvision with a range of 60 feet."},
            {"name": "Spider Climb", "description": "You have a Climb Speed equal to your Speed. When you reach character level 3, you can move up, down, and across vertical surfaces and along ceilings while leaving your hands free."},
            {"name": "Trace of Undeath", "description": "You have Resistance to Necrotic damage."},
            {"name": "Vampiric Bite", "description": "When you use your Unarmed Strike and deal damage, you can choose to bite with your fangs. You deal Piercing damage equal to 1d4 plus your Constitution modifier instead of the normal damage of an Unarmed Strike.\n\nIn addition, when you deal this damage to a creature that isn't a Construct or an Undead, you can empower yourself in one of the following ways:\n\n**Drain.** You regain Hit Points equal to the Piercing damage dealt.\n\n**Strengthen.** You gain a bonus to the next ability check or attack roll you make within the next minute; the bonus is equal to the Piercing damage dealt.\n\nYou can empower yourself with this trait a number of times equal to your Proficiency Bonus, and you regain all expended uses when you finish a Long Rest."}
        ],
        "source": "Astarion's Book of Hungers",
        "is_official": True,
        "is_custom": False,
        "is_legacy": False
    }
]

# Add new lineages
added_count = 0
for lineage in new_lineages:
    existing_names = [l['name'] for l in data['lineages']]
    if lineage['name'] not in existing_names:
        data['lineages'].append(lineage)
        print(f"Added: {lineage['name']}")
        added_count += 1
    else:
        print(f"Already exists: {lineage['name']}")

# Add version marker
data['_version'] = 2

# Sort by name
data['lineages'].sort(key=lambda l: l['name'])

# Save
with open('lineages.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"\nAdded {added_count} new lineages")
print(f"Total lineages: {len(data['lineages'])}")
