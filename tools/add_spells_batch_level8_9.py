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
    if t == "sight" or t == "unlimited":
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
    # Level 8
    make_spell(
        name="Animal Shapes",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S",
        duration="24 hours",
        concentration=False,
        class_names=["Druid"],
        description=(
            "Choose any number of willing creatures in range; each becomes a Large or smaller Beast of CR 4 or lower (forms can differ). "
            "On later turns you can use a Magic action to change their forms again. Stats are replaced but they keep type, HP, HD, alignment, communication, and mental scores. "
            "Equipment melds. Each gains temp HP equal to the HP of the first form. Targets can end the effect as a Bonus Action."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "Buff", "Utility", "Temp HP"],
    ),
    make_spell(
        name="Antimagic Field",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (iron filings)",
        duration="1 hour",
        concentration=True,
        class_names=["Cleric", "Wizard"],
        description=(
            "A 10-foot emanation of antimagic surrounds you. Spells and magic effects are suppressed inside; magic items fail; AOE can't enter; teleport and planar travel fail. "
            "Ongoing spells are suppressed unless from artifacts or deities. Dispel Magic doesn't affect the field; overlapping fields don't cancel."
        ),
        source="Player's Handbook (2024)",
        tags=["Abjuration", "Defense", "Utility"],
    ),
    make_spell(
        name="Antipathy/Sympathy",
        level=8,
        casting_time="1 hour",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a mix of vinegar and honey)",
        duration="10 days",
        concentration=False,
        class_names=["Bard", "Druid", "Wizard"],
        description=(
            "Enchant a Huge or smaller creature or object with antipathy or sympathy toward a specified creature type within 120 feet. "
            "Failing Wisdom save: Antipathy frightens and drives away; Sympathy charms and draws near. Ending save occurs when 120+ feet away; success grants 1-minute immunity."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Debuff", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Befuddlement",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (a key ring with no keys)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Druid", "Warlock", "Wizard"],
        description=(
            "Target creature makes an Intelligence save; on a fail takes 10d12 Psychic damage and cannot cast spells or take Magic actions. "
            "The target repeats the save every 30 days; Greater Restoration, Heal, or Wish also ends the effect. Success halves damage only."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Clone",
        level=8,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (a diamond worth 1,000+ GP, consumed; a sealable vessel worth 2,000+ GP)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You create an inert duplicate in a vessel that finishes in 120 days. If the original dies later and the soul is willing, it transfers to the clone, which is identical but equipmentless. "
            "Original remains become inert and can't be revived."
        ),
        source="Player's Handbook (2024)",
        tags=["Necromancy", "Utility"],
    ),
    make_spell(
        name="Control Weather",
        level=8,
        casting_time="10 minutes",
        ritual=False,
        range_str="Self",
        components="V, S, M (burning incense)",
        duration="8 hours",
        concentration=True,
        class_names=["Cleric", "Druid", "Wizard"],
        description=(
            "Outdoors, change weather within 5 miles. Adjust precipitation, temperature, wind by one stage (tables) taking 1d4×10 minutes; can change again. "
            "Ends early if you go indoors; weather returns gradually."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "Utility", "AOE"],
    ),
    make_spell(
        name="Demiplane",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="S",
        duration="1 hour",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "Create a shadowy Medium door to an empty 30-foot cube demiplane of wood or stone. Items remain when it closes; creatures can choose to be shunted out prone. "
            "Each casting can make a new demiplane or link to one you know (including others' if you know it)."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Dominate Monster",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="1 hour",
        concentration=True,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "One creature makes a Wisdom save (advantage if fighting). On a fail, charmed with telepathic link; commands require no action. "
            "Damage triggers repeat saves. Can command reactions by using yours. Slot 9 extends duration up to 8 hours."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Debuff", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Earthquake",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="500 feet",
        components="V, S, M (a fractured rock)",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Druid", "Sorcerer"],
        description=(
            "Tremors in a 100-foot-radius area create difficult terrain. Each turn creatures on ground save Dex or fall prone and lose Concentration. "
            "You can create fissures (Dex save or fall) and damage structures (50 bludgeoning each turn; collapse deals 12d6 and buries on failed Dex)."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "AOE", "Damage", "Bludgeoning", "Saving Throw"],
    ),
    make_spell(
        name="Glibness",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="1 hour",
        concentration=False,
        class_names=["Bard", "Warlock"],
        description=(
            "For the duration you can treat any Charisma check roll as 15, and magic detecting lies reads you as truthful."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Buff", "Utility"],
    ),
    make_spell(
        name="Holy Aura",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a reliquary worth 1,000+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric"],
        description=(
            "A 30-foot emanation grants chosen creatures advantage on all saves; attackers have disadvantage on attacks against them. "
            "Fiends or Undead hitting a protected creature must Con save or be blinded until end of next turn."
        ),
        source="Player's Handbook (2024)",
        tags=["Abjuration", "Buff", "Defense", "Saving Throw", "Radiant"],
    ),
    make_spell(
        name="Holy Star of Mystra",
        level=8,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Wizard"],
        description=(
            "A glowing mote hovers above you shedding light. On cast and as a Bonus Action, make a ranged spell attack within 120 feet for 4d10 + mod Force or Radiant. "
            "You have Three-Quarters Cover; if you succeed a save vs a level 7 or lower single-target spell, you can react to deflect it back at the caster."
        ),
        source="Forgotten Realms - Heroes of Faerun",
        tags=["Evocation", "Damage", "Force", "Radiant", "Defense", "Buff", "Attack"],
    ),
    make_spell(
        name="Incendiary Cloud",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "A 20-foot-radius heavily obscuring cloud deals 10d8 Fire when it appears (Dex save half) and when creatures enter/start turn; once per turn. "
            "Moves 10 feet away from you each turn. Strong wind disperses."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "AOE", "Damage", "Fire", "Saving Throw"],
    ),
    make_spell(
        name="Maze",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "Banish a creature to a labyrinth demiplane. It can use Study action to make DC 20 Int (Investigation) to escape; on success returns and spell ends. "
            "Otherwise returns when the spell ends."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Debuff", "Utility", "Saving Throw"],
    ),
    make_spell(
        name="Mind Blank",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S",
        duration="24 hours",
        concentration=False,
        class_names=["Bard", "Wizard"],
        description=(
            "One willing creature gains immunity to Psychic damage and the Charmed condition, and is immune to mind reading, alignment/emotion sensing, location detection, and remote observation; even Wish can't gather info about it."
        ),
        source="Player's Handbook (2024)",
        tags=["Abjuration", "Defense", "Buff"],
    ),
    make_spell(
        name="Power Word Stun",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "If target has 150 HP or fewer, it is Stunned; otherwise its speed is 0 until your next turn. Stunned targets make Con saves at end of turns to end."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Sunburst",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (a piece of sunstone)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric", "Druid", "Sorcerer", "Wizard"],
        description=(
            "A 60-foot-radius sphere of sunlight forces Con saves; fail: 12d6 Radiant and Blinded for 1 minute, success: half damage. Blinded can save each turn to end. Dispels Darkness in the area."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "AOE", "Damage", "Radiant", "Saving Throw", "Light"],
    ),
    make_spell(
        name="Telepathy",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="Unlimited",
        components="V, S, M (a pair of linked silver rings)",
        duration="24 hours",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You and a familiar willing creature on the same plane share an instant two-way telepathic link for the duration, exchanging words, images, sounds, and sensory messages."
        ),
        source="Player's Handbook (2024)",
        tags=["Divination", "Utility"],
    ),
    make_spell(
        name="Tsunami",
        level=8,
        casting_time="1 minute",
        ritual=False,
        range_str="1 mile",
        components="V, S",
        duration="6 rounds",
        concentration=True,
        class_names=["Druid"],
        description=(
            "Create a wall of water up to 300×300×50 feet. On appearance creatures save Str for 6d10 Bludgeoning (half on success). Each turn wall moves 50 feet away; creatures save or take 5d10 (once per round) as height and damage drop by 1d10 each turn until dissipated. Movement inside requires Str (Athletics) vs your DC to move."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "AOE", "Damage", "Bludgeoning", "Saving Throw"],
    ),
    make_spell(
        name="Abi-Dalzim's Horrid Wilting",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (a bit of sponge)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "Drain moisture in a 30-foot cube. Creatures Con save for 12d8 Necrotic (half on success); Plants and Water Elementals save at disadvantage; Constructs/Undead unaffected. Nonmagical plants wither."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Necromancy", "AOE", "Damage", "Necrotic", "Saving Throw"],
    ),
    make_spell(
        name="Dark Star",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (a shard of onyx and a drop of blood, consumed)",
        duration="1 minute",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "Create up to a 40-foot-radius sphere of magical darkness and crushing gravity. Area is difficult terrain, silent, blocks light; creatures inside are deafened and immune to Thunder. "
            "Entering or starting turn triggers Con save for 8d10 Force (half on success); kills disintegrate nonmagical items."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Evocation", "AOE", "Damage", "Force", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Feeblemind",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (clay, crystal, glass, or mineral spheres)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Druid", "Warlock", "Wizard"],
        description=(
            "Target takes 4d6 Psychic and makes an Intelligence save. On a fail, Int and Cha become 1; cannot cast spells, use magic items, understand language, or communicate meaningfully but knows friends. "
            "Save repeats every 30 days; Greater Restoration, Heal, or Wish ends the effect. Success halves damage only."
        ),
        source="Player's Handbook (2014)",
        tags=["Enchantment", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Illusory Dragon",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="S",
        duration="1 minute",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "Create a Huge shadow dragon. Enemies that see it Wis save or be frightened for 1 minute; can retry when out of sight. Bonus Action move 60 feet and exhale 60-foot cone choosing Acid, Cold, Fire, Lightning, Necrotic, or Poison (Int save, 7d6 damage, half on success). "
            "Illusion is immune to attacks; Investigation reveals it."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Illusion", "AOE", "Damage", "Debuff", "Saving Throw", "Acid", "Cold", "Fire", "Lightning", "Necrotic", "Poison"],
    ),
    make_spell(
        name="Maddening Darkness",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, M (pitch mixed with mercury)",
        duration="10 minutes",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "A 60-foot-radius sphere of magical darkness with unsettling sounds. Creatures starting turn inside make Wisdom save, taking 8d8 Psychic on a fail, half on success. Light of level 8 or lower can't illuminate."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Damage", "Psychic", "Saving Throw", "Debuff"],
    ),
    make_spell(
        name="Mighty Fortress",
        level=8,
        casting_time="1 minute",
        ritual=False,
        range_str="1 mile",
        components="V, S, M (a diamond worth 500+ GP, consumed)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "Raise a stone fortress (120-foot square walls with four turrets, keep inside, furnished, unseen servants). Lasts 7 days (crumbles after) unless cast weekly for a year to become permanent. Walls have AC 15 and 30 HP per inch."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "Utility", "Defense"],
    ),
    make_spell(
        name="Reality Break",
        level=8,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a crystal prism)",
        duration="1 minute",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "Target makes Wisdom save or can't take reactions and rolls d10 each turn for chaotic effects: psychic damage/stun, force damage Dex save, teleport + force + prone, or cold damage + blinded. "
            "Repeat Wis save each turn to end."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Conjuration", "Damage", "Psychic", "Force", "Cold", "Debuff", "Saving Throw"],
    ),
    # Level 9
    make_spell(
        name="Astral Projection",
        level=9,
        casting_time="1 hour",
        ritual=False,
        range_str="10 feet",
        components="V, S, M (for each target a jacinth worth 1,000+ GP and a silver bar worth 100+ GP, consumed)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Cleric", "Warlock", "Wizard"],
        description=(
            "You and up to eight willing creatures project astral bodies into the Astral Plane; bodies remain unconscious and unharmed. Astral forms keep stats and gear plus a silver cord; cutting it kills both. "
            "Damage to astral form doesn't affect body. Spell ends on 0 HP for body or form or when you dismiss; survivors return to bodies."
        ),
        source="Player's Handbook (2024)",
        tags=["Necromancy", "Utility"],
    ),
    make_spell(
        name="Blade Of Disaster",
        level=9,
        casting_time="Bonus Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "Create a planar rift blade; immediately and as Bonus Actions you can move it 60 feet and make up to two melee spell attacks (crit on 18-20) for 10d6 Force each. "
            "Passes through barriers including Wall of Force."
        ),
        source="Forgotten Realms - Heroes of Faerun",
        tags=["Conjuration", "Attack", "Damage", "Force", "Saving Throw"],
    ),
    make_spell(
        name="Foresight",
        level=9,
        casting_time="1 minute",
        ritual=False,
        range_str="Touch",
        components="V, S, M (a hummingbird feather)",
        duration="8 hours",
        concentration=False,
        class_names=["Bard", "Druid", "Warlock", "Wizard"],
        description=(
            "Touch grants advantage on all d20 Tests; attackers have disadvantage on attacks against the target. Ends early if cast again."
        ),
        source="Player's Handbook (2024)",
        tags=["Divination", "Buff", "Defense"],
    ),
    make_spell(
        name="Gate",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a diamond worth 5,000+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Cleric", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Create a planar portal 5-20 feet wide linking to a precise location on another plane; travel through the front transports instantly. "
            "Can name a specific creature to open next to it and bring it through. Planar rulers can block portals in their domains."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Imprisonment",
        level=9,
        casting_time="1 minute",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (a statuette of the target worth 5,000+ GP)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Warlock", "Wizard"],
        description=(
            "Target makes Wisdom save or is imprisoned without aging or needs; divinations can't find it. Choose mode: Burial (sphere under earth), Chaining (Restrained), Hedged Prison (demiplane), Minimus Containment (gem), or Slumber (Unconscious). "
            "Specify a trigger to end. Dispel Magic works only with a level 9 slot on prison or component."
        ),
        source="Player's Handbook (2024)",
        tags=["Abjuration", "Debuff", "Saving Throw", "Utility", "Defense"],
    ),
    make_spell(
        name="Mass Heal",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "Distribute up to 700 HP among creatures you can see in range; also end Blinded, Deafened, and Poisoned on them."
        ),
        source="Player's Handbook (2024)",
        tags=["Abjuration", "Healing", "Buff"],
    ),
    make_spell(
        name="Meteor Swarm",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="1 mile",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "Four points each explode in a 40-foot-radius sphere. Creatures Dex save for 20d6 Fire + 20d6 Bludgeoning (half on success). A creature in multiple spheres is affected once. Flammable objects ignite."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "AOE", "Damage", "Fire", "Bludgeoning", "Saving Throw"],
    ),
    make_spell(
        name="Power Word Heal",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Cleric"],
        description=(
            "One creature regains all Hit Points; ends Charmed, Frightened, Paralyzed, Poisoned, Stunned; if Prone can use Reaction to stand."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Healing", "Buff"],
    ),
    make_spell(
        name="Power Word Kill",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Target with 100 HP or fewer dies. Otherwise it takes 12d12 Psychic damage."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Damage", "Psychic"],
    ),
    make_spell(
        name="Prismatic Wall",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="10 minutes",
        concentration=False,
        class_names=["Bard", "Wizard"],
        description=(
            "Create a multicolored wall or globe; blinds on approach (Con save). Passing through layers forces Dex saves vs damage/effects per color. Layers can be destroyed in order by specific means; Antimagic Field and most Dispels don't affect it (only violet layer by Dispel Magic)."
        ),
        source="Player's Handbook (2024)",
        tags=["Abjuration", "AOE", "Damage", "Debuff", "Saving Throw", "Defense", "Light"],
    ),
    make_spell(
        name="Shapechange",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a jade circlet worth 1,500+ GP)",
        duration="1 hour",
        concentration=True,
        class_names=["Druid", "Wizard"],
        description=(
            "You assume forms of creatures you've seen with CR up to your level; not Constructs/Undead. Can use Magic action to change forms. Gain temp HP equal to first form's HP. "
            "Stats replaced by form but keep type, alignment, personality, mental scores, HP/HD, proficiencies, communication, and Spellcasting feature. Gear may drop or resize."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "Buff", "Utility", "Temp HP"],
    ),
    make_spell(
        name="Storm of Vengeance",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="1 mile",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Druid"],
        description=(
            "300-foot-radius storm. On cast, Con save or 2d6 Thunder and Deafened for duration. Turn 2 acidic rain 4d6 Acid; Turn 3 six lightning bolts Dex save 10d6 Lightning; Turn 4 hail 2d6 Bludgeoning; Turns 5-10 deal 1d6 Cold each round and create difficult terrain, heavy obscurement, no ranged weapon attacks, strong wind."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "AOE", "Damage", "Thunder", "Acid", "Lightning", "Bludgeoning", "Cold", "Saving Throw"],
    ),
    make_spell(
        name="Time Stop",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You take 1d4+1 turns while others are frozen. Ends if your actions or effects affect others or objects they carry, or if you move more than 1,000 feet from the casting point."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "Utility"],
    ),
    make_spell(
        name="True Polymorph",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="30 feet",
        components="V, S, M (mercury, gum arabic, and smoke)",
        duration="1 hour",
        concentration=True,
        class_names=["Bard", "Warlock", "Wizard"],
        description=(
            "Transform creature or nonmagical object. Creature→creature up to target's CR/level; object→creature CR 9 or less; creature→object of similar size. "
            "Maintain Concentration full duration for permanence until dispelled. Unwilling creatures Wis save to resist. Temp HP equals new form HP."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "Debuff", "Buff", "Utility", "Saving Throw", "Temp HP"],
    ),
    make_spell(
        name="True Resurrection",
        level=9,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (diamonds worth 25,000+ GP, consumed)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric", "Druid"],
        description=(
            "Return a creature dead up to 200 years (not of old age) to life with all HP, curing ailments and restoring body or creating a new one if none remains. Restores non-Undead to life if they were undead."
        ),
        source="Player's Handbook (2024)",
        tags=["Necromancy", "Healing", "Utility"],
    ),
    make_spell(
        name="Weird",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S",
        duration="1 minute",
        concentration=True,
        class_names=["Warlock", "Wizard"],
        description=(
            "Creatures of your choice in a 30-foot-radius sphere make Wisdom saves; fail: 10d10 Psychic and Frightened for duration, success: half damage only. Frightened targets save each turn, failing takes 5d10 Psychic; success ends for that target."
        ),
        source="Player's Handbook (2024)",
        tags=["Illusion", "AOE", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Wish",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "Duplicate any spell level 8 or lower without requirements, or produce powerful effects (object creation, instant health, resistance, spell immunity, feat swap, reroll, or other reality shaping per DM). "
            "Non-duplication uses cause casting stress: future spellcasting before a Long Rest deals necrotic damage per level, Str becomes 3 for 2d4 days, and 33% risk of never casting Wish again."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Utility", "Healing", "Buff", "Defense"],
    ),
    make_spell(
        name="Invulnerability",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (adamantine worth 500+ GP, consumed)",
        duration="10 minutes",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "You are immune to all damage for the duration."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Abjuration", "Defense", "Buff"],
    ),
    make_spell(
        name="Mass Polymorph",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a caterpillar cocoon)",
        duration="1 hour",
        concentration=True,
        class_names=["Bard", "Sorcerer", "Wizard"],
        description=(
            "Transform up to ten creatures into beasts you've seen; unwilling Wis save (shapechangers auto-succeed). Form CR ≤ target's CR or half level. Targets keep HP, alignment, personality; gain temp HP equal to beast HP and revert at 0 temp HP or end. Gear melds; can't speak or cast."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Transmutation", "Buff", "Debuff", "Utility", "Saving Throw", "Temp HP"],
    ),
    make_spell(
        name="Psychic Scream",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "Up to ten creatures with Int 3+ make Intelligence saves; fail: 14d6 Psychic and Stunned, success: half and not stunned. Stunned can repeat save each turn. Killed targets' heads explode."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Enchantment", "AOE", "Damage", "Psychic", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Ravenous Void",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="1000 feet",
        components="V, S, M (a small iron nine-pointed star)",
        duration="1 minute",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "Create a 20-foot-radius gravitational sphere; area within 100 feet is difficult terrain and pulls unsecured objects. Creatures starting within 100 feet Str save or be pulled toward center. "
            "Entering/starting inside sphere deals 5d10 Force and restrains; Str check to escape. Creatures reduced to 0 are annihilated with nonmagical items."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Evocation", "AOE", "Damage", "Force", "Saving Throw", "Debuff"],
    ),
    make_spell(
        name="Time Ravage",
        level=9,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (an hourglass with diamond dust worth 5,000+ GP, consumed)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "Target Con save; fail: 10d12 Necrotic and ages to 30 days from death, with disadvantage on attacks/checks/saves and halved speed. Success: half damage. Only Wish or Greater Restoration with a 9th-level slot ends the aging."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Necromancy", "Damage", "Necrotic", "Debuff", "Saving Throw"],
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
