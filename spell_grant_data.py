"""The spells that bundled species, feats, classes and subclasses give a character.

Used by ``spell_grants`` to add what a character's features give (always prepared, not counted against the
spells they can prepare) the way class and subclass spells already are. Official content is described here
rather than in the content files so that upgraded installs get it without a data migration; custom feats and
species say the same things in their own fields (a feat's set spells, a species trait's ``spells``).

Spell names are the names in the spell collection. A "(Legacy)" spell name is the 2014 version; the class and
subclass tables give plain names and a legacy class picks the legacy version of each (``resolve_spell``).
Levels: species grants are character levels, class and subclass grants are class levels.
"""

# species: {name: {fixed: [(spell, level)], options: {option: [(spell, level)]}, picks: [...]}}
OPTION_LABEL = {
    'Elf': 'Elven Lineage',
    'Gnome': 'Gnomish Lineage',
    'Tiefling': 'Fiendish Legacy',
    'Variant Tiefling': 'Variant feature',
}

LINEAGE_GRANTS = {
    'Aasimar': {
        'fixed': [('Light', 1)],
        'options': {},
        'picks': [],
    },
    'Elf': {
        'fixed': [],
        'options': {
            'Drow': [('Dancing Lights', 1), ('Faerie Fire', 3), ('Darkness', 5)],
            'High Elf': [('Prestidigitation', 1), ('Detect Magic', 3), ('Misty Step', 5)],
            'Wood Elf': [('Druidcraft', 1), ('Longstrider', 3), ('Pass without Trace', 5)],
            'Lorwyn Elf': [('Thorn Whip', 1), ('Command', 3), ('Silence', 5)],
            'Shadowmoor Elf': [('Starry Wisp', 1), ('Heroism', 3), ('Gentle Repose', 5)],
        },
        'picks': [],
    },
    'Faerie': {
        'fixed': [('Druidcraft', 1), ('Faerie Fire', 3), ('Enlarge/Reduce', 5)],
        'options': {},
        'picks': [],
    },
    'Flamekin': {
        'fixed': [('Produce Flame', 1), ('Burning Hands', 3), ('Flame Blade', 5)],
        'options': {},
        'picks': [],
    },
    'Gnome': {
        'fixed': [],
        'options': {
            'Forest Gnome': [('Minor Illusion', 1), ('Speak with Animals', 1)],
            'Rock Gnome': [('Mending', 1), ('Prestidigitation', 1)],
        },
        'picks': [],
    },
    'Khoravar': {
        'fixed': [('Friends', 1)],
        'options': {},
        'picks': [],
    },
    'Rimekin': {
        'fixed': [('Ray of Frost', 1), ('Ice Knife', 3), ('Flame Blade', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling': {
        'fixed': [('Thaumaturgy', 1)],
        'options': {
            'Abyssal': [('Poison Spray', 1), ('Ray of Sickness', 3), ('Hold Person', 5)],
            'Chthonic': [('Chill Touch', 1), ('False Life', 3), ('Ray of Enfeeblement', 5)],
            'Infernal': [('Fire Bolt', 1), ('Hellish Rebuke', 3), ('Darkness', 5)],
        },
        'picks': [],
    },
    'Hexblood': {
        'fixed': [('Disguise Self', 1), ('Hex', 1)],
        'options': {},
        'picks': [],
    },
    'Dwarf (Mark of Warding)': {
        'fixed': [('Alarm (Legacy)', 1), ('Mage Armor (Legacy)', 1), ('Arcane Lock (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Dark Elf': {
        'fixed': [('Dancing Lights (Legacy)', 1), ('Faerie Fire (Legacy)', 3), ('Darkness (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'High Elf': {
        'fixed': [],
        'options': {},
        'picks': [
            {
                'label': 'Cantrip',
                'count': 1,
                'level': 0,
                'lists': ['Wizard'],
            },
        ],
    },
    'Pallid Elf': {
        'fixed': [('Light (Legacy)', 1), ('Sleep (Legacy)', 3), ('Invisibility (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Elf (Mark of Shadow)': {
        'fixed': [('Minor Illusion (Legacy)', 1), ('Invisibility (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Astral Elf': {
        'fixed': [('Dancing Lights (Legacy)', 1), ('Light (Legacy)', 1), ('Sacred Flame (Legacy)', 1)],
        'options': {},
        'picks': [
            {
                'label': 'Astral Fire',
                'count': 1,
                'level': 0,
                'names': ['Dancing Lights (Legacy)', 'Light (Legacy)', 'Sacred Flame (Legacy)'],
            },
        ],
    },
    'Vahadar Elf': {
        'fixed': [],
        'options': {},
        'picks': [
            {
                'label': 'Cantrip',
                'count': 1,
                'level': 0,
                'lists': ['Druid'],
            },
        ],
    },
    'Mul Daya Elf': {
        'fixed': [('Chill Touch (Legacy)', 1), ('Hex (Legacy)', 3), ('Darkness (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Forest Gnome': {
        'fixed': [('Minor Illusion (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Gnome (Mark of Scribing)': {
        'fixed': [('Message (Legacy)', 1), ('Comprehend Languages (Legacy)', 1), ('Magic Mouth (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Half-Elf (Mark of Detection)': {
        'fixed': [
            ('Detect Magic (Legacy)', 1),
            ('Detect Poison and Disease (Legacy)', 1),
            ('See Invisibility (Legacy)', 3),
        ],
        'options': {},
        'picks': [],
    },
    'Half-Elf (Mark of Storm)': {
        'fixed': [('Gust', 1), ('Gust of Wind (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Half-Orc (Mark of Finding)': {
        'fixed': [("Hunter's Mark (Legacy)", 1), ('Locate Object (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Lotusden Halfling': {
        'fixed': [('Druidcraft (Legacy)', 1), ('Entangle (Legacy)', 3), ('Spike Growth (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Halfling (Mark of Hospitality)': {
        'fixed': [
            ('Prestidigitation (Legacy)', 1),
            ('Purify Food and Drink (Legacy)', 1),
            ('Unseen Servant (Legacy)', 1),
        ],
        'options': {},
        'picks': [],
    },
    'Halfling (Mark of Healing)': {
        'fixed': [('Cure Wounds (Legacy)', 1), ('Lesser Restoration (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Human (Mark of Finding)': {
        'fixed': [("Hunter's Mark (Legacy)", 1), ('Locate Object (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Human (Mark of Handling)': {
        'fixed': [('Animal Friendship (Legacy)', 1), ('Speak with Animals (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Human (Mark of Making)': {
        'fixed': [('Mending (Legacy)', 1), ('Magic Weapon (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Human (Mark of Passage)': {
        'fixed': [('Misty Step (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Human (Mark of Sentinel)': {
        'fixed': [('Shield (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Legacy)': {
        'fixed': [('Thaumaturgy (Legacy)', 1), ('Hellish Rebuke (Legacy)', 3), ('Darkness (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Baalzebul)': {
        'fixed': [('Thaumaturgy (Legacy)', 1), ('Ray of Sickness (Legacy)', 3), ('Crown of Madness (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Dispater)': {
        'fixed': [('Thaumaturgy (Legacy)', 1), ('Disguise Self (Legacy)', 3), ('Detect Thoughts (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Fierna)': {
        'fixed': [('Friends (Legacy)', 1), ('Charm Person (Legacy)', 3), ('Suggestion (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Glasya)': {
        'fixed': [('Minor Illusion (Legacy)', 1), ('Disguise Self (Legacy)', 3), ('Invisibility (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Levistus)': {
        'fixed': [('Ray of Frost (Legacy)', 1), ('Armor of Agathys (Legacy)', 3), ('Darkness (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Mammon)': {
        'fixed': [('Mage Hand (Legacy)', 1), ("Tenser's Floating Disk (Legacy)", 3), ('Arcane Lock (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Mephistopheles)': {
        'fixed': [('Mage Hand (Legacy)', 1), ('Burning Hands (Legacy)', 3), ('Flame Blade (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Tiefling (Bloodline of Zariel)': {
        'fixed': [('Thaumaturgy (Legacy)', 1), ('Searing Smite (Legacy)', 3), ('Branding Smite', 5)],
        'options': {},
        'picks': [],
    },
    'Variant Tiefling': {
        'fixed': [],
        'options': {
            "Devil's Tongue": [('Vicious Mockery (Legacy)', 1), ('Charm Person (Legacy)', 3), ('Enthrall (Legacy)', 5)],
            'Hellfire': [('Burning Hands (Legacy)', 3)],
        },
        'picks': [],
    },
    'Aarakocra (Legacy: MPMM)': {
        'fixed': [('Gust of Wind (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Aasimar (Legacy)': {
        'fixed': [('Light (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Protector Aasimar': {
        'fixed': [('Light (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Scourge Aasimar': {
        'fixed': [('Light (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Fallen Aasimar': {
        'fixed': [('Light (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Deep Gnome (Legacy: MPMM)': {
        'fixed': [('Disguise Self (Legacy)', 3), ('Nondetection (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Duergar (Legacy: MPMM)': {
        'fixed': [('Enlarge/Reduce (Legacy)', 3), ('Invisibility (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Duergar (Legacy: SCAG)': {
        'fixed': [('Enlarge/Reduce (Legacy)', 3), ('Invisibility (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Fairy (Legacy: MPMM)': {
        'fixed': [('Druidcraft (Legacy)', 1), ('Faerie Fire (Legacy)', 3), ('Enlarge/Reduce (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Fairy (Legacy: WBW)': {
        'fixed': [('Druidcraft (Legacy)', 1), ('Faerie Fire (Legacy)', 3), ('Enlarge/Reduce (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Firbolg (Legacy: MPMM)': {
        'fixed': [('Detect Magic (Legacy)', 1), ('Disguise Self (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Firbolg (Legacy: VGM)': {
        'fixed': [('Detect Magic (Legacy)', 1), ('Disguise Self (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Air Genasi (Legacy: MPMM)': {
        'fixed': [('Shocking Grasp (Legacy)', 1), ('Feather Fall (Legacy)', 3), ('Levitate (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Air Genasi (Legacy: EEPC)': {
        'fixed': [('Levitate (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Earth Genasi (Legacy: MPMM)': {
        'fixed': [('Blade Ward (Legacy)', 1), ('Pass Without Trace (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Earth Genasi (Legacy: EEPC)': {
        'fixed': [('Pass Without Trace (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Fire Genasi (Legacy: MPMM)': {
        'fixed': [('Produce Flame (Legacy)', 1), ('Burning Hands (Legacy)', 3), ('Flame Blade (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Fire Genasi (Legacy: EEPC)': {
        'fixed': [('Produce Flame (Legacy)', 1), ('Burning Hands (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Water Genasi (Legacy: MPMM)': {
        'fixed': [('Acid Splash (Legacy)', 1), ('Create or Destroy Water (Legacy)', 3), ('Water Walk (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Water Genasi (Legacy: EEPC)': {
        'fixed': [('Shape Water', 1), ('Create or Destroy Water (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Githyanki (Legacy: MPMM)': {
        'fixed': [('Mage Hand (Legacy)', 1), ('Jump (Legacy)', 3), ('Misty Step (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Githyanki (Legacy: MToF)': {
        'fixed': [('Mage Hand (Legacy)', 1), ('Jump (Legacy)', 3), ('Misty Step (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Githzerai (Legacy: MPMM)': {
        'fixed': [('Mage Hand (Legacy)', 1), ('Shield (Legacy)', 3), ('Detect Thoughts (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Githzerai (Legacy: MToF)': {
        'fixed': [('Mage Hand (Legacy)', 1), ('Shield (Legacy)', 3), ('Detect Thoughts (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Triton (Legacy: MPMM)': {
        'fixed': [('Fog Cloud (Legacy)', 1), ('Gust of Wind (Legacy)', 3), ('Water Walk (Legacy)', 5)],
        'options': {},
        'picks': [],
    },
    'Triton (Legacy: VGM)': {
        'fixed': [('Fog Cloud (Legacy)', 1), ('Gust of Wind (Legacy)', 3), ('Wall of Water', 5)],
        'options': {},
        'picks': [],
    },
    'Yuan-Ti (Legacy: MPMM)': {
        'fixed': [('Poison Spray (Legacy)', 1), ('Animal Friendship (Legacy)', 1), ('Suggestion (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Yuan-Ti (Legacy: VGM)': {
        'fixed': [('Poison Spray (Legacy)', 1), ('Animal Friendship (Legacy)', 1), ('Suggestion (Legacy)', 3)],
        'options': {},
        'picks': [],
    },
    'Siren': {
        'fixed': [('Friends (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
    'Hexblood (Legacy)': {
        'fixed': [('Disguise Self (Legacy)', 1), ('Hex (Legacy)', 1)],
        'options': {},
        'picks': [],
    },
}

# feats whose record has no set spells: {feat name: [spell, ...]}
FEAT_GRANTS = {
    'Boon of Blazing Dawn': ['Light'],
    'Cartomancer': ['Prestidigitation (Legacy)'],
    'Rune Shaper': ['Comprehend Languages (Legacy)'],
    'Outlands Envoy': ['Misty Step (Legacy)', 'Tongues (Legacy)'],
    'Servo Crafting': ['Find Familiar (Legacy)'],
    'Wood Elf Magic': ['Longstrider (Legacy)', 'Pass Without Trace (Legacy)'],
    'Drow High Magic': ['Detect Magic (Legacy)', 'Levitate (Legacy)', 'Dispel Magic (Legacy)'],
    'Divinely Favored': ['Augury (Legacy)'],
    'Fey Teleportation': ['Misty Step (Legacy)'],
    'Strixhaven Mascot': ['Find Familiar (Legacy)'],
    'Gift of the Metallic Dragon': ['Cure Wounds (Legacy)'],
    'Armor of Shadows (Legacy)': ['Mage Armor (Legacy)'],
    'Ascendant Step (Legacy)': ['Levitate (Legacy)'],
    'Beast Speech': ['Speak with Animals (Legacy)'],
    'Bewitching Whispers': ['Compulsion (Legacy)'],
    'Chains of Carceri': ['Hold Monster (Legacy)'],
    'Dreadful Word': ['Confusion (Legacy)'],
    'Eldritch Sight': ['Detect Magic (Legacy)'],
    'Far Scribe': ['Sending (Legacy)'],
    'Fiendish Vigor (Legacy)': ['False Life (Legacy)'],
    'Gift of the Depths (Legacy)': ['Water Breathing (Legacy)'],
    'Mask of Many Faces (Legacy)': ['Disguise Self (Legacy)'],
    'Master of Myriad Forms (Legacy)': ['Alter Self (Legacy)'],
    'Minions of Chaos': ['Conjure Elemental (Legacy)'],
    'Mire the Mind': ['Slow (Legacy)'],
    'Misty Visions (Legacy)': ['Silent Image (Legacy)'],
    'Otherworldly Leap (Legacy)': ['Jump (Legacy)'],
    'Sculptor of Flesh': ['Polymorph (Legacy)'],
    'Shroud of Shadow': ['Invisibility (Legacy)'],
    'Sign of Ill Omen': ['Bestow Curse (Legacy)'],
    'Thief of Five Fates': ['Bane (Legacy)'],
    "Trickster's Escape": ['Freedom of Movement (Legacy)'],
    'Undying Servitude': ['Animate Dead (Legacy)'],
    'Visions of Distant Realms (Legacy)': ['Arcane Eye (Legacy)'],
    'Whispers of the Grave (Legacy)': ['Speak with Dead (Legacy)'],
}

# spells to pick on top: {feat name: [{label, count, level}]}
FEAT_PICKS = {
    'Divinely Favored': [
        {
            'label': '1st-level spell',
            'count': 1,
            'level': 1,
        },
    ],
}

# (class, subclass) in lower case: [(spell, class level)]
SUBCLASS_GRANTS = {
    ('barbarian', 'path of the wild heart'): [('Beast Sense', 3), ('Speak with Animals', 3)],
    ('bard', 'college of spirits'): [('Guidance', 3), ('Spirit Guardians', 6)],
    ('druid', 'circle of the stars'): [('Guidance', 3), ('Guiding Bolt', 3)],
    ('fighter', 'psi warrior'): [('Telekinesis', 18)],
    ('fighter', 'banneret'): [('Comprehend Languages', 3)],
    ('monk', 'warrior of shadow'): [('Darkness', 3)],
    ('rogue', 'phantom'): [('Augury', 9), ('Speak with Dead', 9)],
    ('sorcerer', 'shadow sorcery'): [('Summon Beast', 6)],
    ('wizard', 'diviner'): [('See Invisibility', 10)],
    ('wizard', 'illusionist'): [('Minor Illusion', 3)],
    ('wizard', 'necromancer'): [('Animate Dead', 6)],
    ('wizard', 'transmuter'): [('Alter Self', 3), ('Polymorph', 10), ('Raise Dead', 14)],
    ('artificer', 'alchemist'): [('Lesser Restoration', 9), ("Tasha's Bubbling Cauldron", 15)],
    ('artificer', 'cartographer'): [('Find the Path', 15)],
}

# the same for 2014 subclasses
LEGACY_SUBCLASS_GRANTS = {
    ('barbarian', 'path of the totem warrior'): [('Beast Sense', 3), ('Speak with Animals', 3), ('Commune with Nature', 10)],
    ('barbarian', 'path of the ancestral guardian'): [('Augury', 10), ('Clairvoyance', 10)],
    ('bard', 'college of spirits'): [('Guidance', 3)],
    ('bard', 'college of glamour'): [('Command', 6)],
    ('cleric', 'grave domain'): [('Spare the Dying', 1)],
    ('cleric', 'light domain'): [('Light', 1)],
    ('druid', 'circle of stars'): [('Guidance', 2), ('Guiding Bolt', 2)],
    ('druid', 'circle of dreams'): [('Dream', 14), ('Scrying', 14), ('Teleportation Circle', 14)],
    ('druid', 'circle of the moon'): [('Alter Self', 14)],
    ('fighter', 'psi warrior'): [('Telekinesis', 18)],
    ('monk', 'way of shadow'): [('Darkness', 3), ('Darkvision', 3), ('Pass Without Trace', 3), ('Silence', 3), ('Minor Illusion', 3)],
    ('monk', 'way of the sun soul'): [('Burning Hands', 6)],
    ('ranger', 'fey wanderer'): [('Summon Fey', 11)],
    ('ranger', 'horizon walker conclave'): [('Etherealness', 7)],
    ('ranger', 'drakewarden'): [('Thaumaturgy', 3)],
    ('sorcerer', 'lunar sorcery'): [('Sacred Flame', 1)],
    ('sorcerer', 'shadow magic'): [('Darkness', 3)],
    ('warlock', 'the celestial'): [('Light', 1), ('Sacred Flame', 1)],
    ('warlock', 'the fathomless'): [("Evard's Black Tentacles", 10)],
    ('warlock', 'the undying'): [('Spare the Dying', 1)],
    ('wizard', 'school of illusion'): [('Minor Illusion', 2)],
    ('wizard', 'school of transmutation'): [('Polymorph', 10), ('Raise Dead', 14)],
    ('artificer', 'alchemist'): [('Lesser Restoration', 9), ('Greater Restoration', 15), ('Heal', 15)],
}

# class: [(spell, class level)] given by a class feature (the class files list Divine Smite, Find Steed,
# Hunter's Mark; these are the others)
CLASS_GRANTS = {
    'druid': [('Speak with Animals', 1), ('Find Familiar', 2)],
    'warlock': [('Contact Other Plane', 9)],
}

# the same for the 2014 version of a class
LEGACY_CLASS_GRANTS = {
    'monk': [('Astral Projection', 18)],
}
