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
        name="Conjure Celestial",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S",
        duration="10 minutes",
        concentration=True,
        class_names=["Cleric"],
        description=(
            "You summon an Upper Planes spirit as a 10-foot-radius, 40-foot-high pillar of light. "
            "Each turn you can bathe creatures in Healing Light (4d12 + mod HP) or Searing Light "
            "(Dex save, 6d12 Radiant, half on success). The cylinder moves up to 30 feet when you move; "
            "each creature can be affected once per turn. +1d12 healing/damage per slot above 7."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Healing", "Damage", "Radiant", "AOE", "Saving Throw"],
    ),
    make_spell(
        name="Delayed Blast Fireball",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S, M (a ball of bat guano and sulfur)",
        duration="1 minute",
        concentration=True,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You place a glowing bead that explodes when the spell ends or if disturbed. "
            "Creatures in a 20-foot-radius sphere make a Dexterity save, taking accumulated Fire damage on a fail or half on a success. "
            "Base damage 12d6, +1d6 each time your turn ends while maintained; base also +1d6 per slot level above 7."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "AOE", "Damage", "Fire", "Saving Throw"],
    ),
    make_spell(
        name="Divine Word",
        level=7,
        casting_time="Bonus Action",
        ritual=False,
        range_str="30 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "Creatures you choose in range make a Charisma save. If 50 HP or fewer, they suffer effects based on HP; "
            "Celestials, Elementals, Fey, and Fiends that fail are banished to their home plane for 24 hours."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "Debuff", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Etherealness",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="8 hours",
        concentration=False,
        class_names=["Bard", "Cleric", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "You step into the Border Ethereal for the duration, moving freely and seeing the original plane in gray. "
            "You interact only with the Ethereal; on end you return to the corresponding spot or nearest open space, taking force damage if shunted. "
            "You can include up to three more creatures per slot level above 7 within 10 feet."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Utility", "Defense"],
    ),
    make_spell(
        name="Finger of Death",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "A target makes a Constitution save, taking 7d8 + 30 Necrotic damage on a failure or half on a success. "
            "Humanoids killed rise as Zombies on your next turn under your command."
        ),
        source="Player's Handbook (2024)",
        tags=["Necromancy", "Damage", "Necrotic", "Saving Throw"],
    ),
    make_spell(
        name="Fire Storm",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="150 feet",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric", "Druid", "Sorcerer"],
        description=(
            "Up to ten contiguous 10-foot cubes of fire appear. Creatures in the area make a Dexterity save, taking 7d10 Fire damage on a failure or half on a success. "
            "Unattended flammable objects ignite."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "AOE", "Damage", "Fire", "Saving Throw"],
    ),
    make_spell(
        name="Forcecage",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="100 feet",
        components="V, S, M (ruby dust worth 1,500+ GP, which the spell consumes)",
        duration="1 hour",
        concentration=True,
        class_names=["Bard", "Warlock", "Wizard"],
        description=(
            "You create an invisible prison as a 20-foot cage or 10-foot solid box. Creatures fully inside are trapped; others are pushed out. "
            "Teleportation or planar travel to leave requires a Charisma save, failing wastes the effect. Extends into the Ethereal and cannot be dispelled."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "Force", "Utility", "Defense", "AOE"],
    ),
    make_spell(
        name="Mirage Arcane",
        level=7,
        casting_time="10 minutes",
        ritual=False,
        range_str="Sight",
        components="V, S",
        duration="10 days",
        concentration=False,
        class_names=["Bard", "Druid", "Wizard"],
        description=(
            "You reshape the look, feel, sound, and smell of terrain in up to a 1-mile square, including structures. "
            "Can create difficult terrain or alter surfaces; illusory objects vanish if removed. Truesight reveals true terrain but not other illusory elements."
        ),
        source="Player's Handbook (2024)",
        tags=["Illusion", "Utility", "AOE"],
    ),
    make_spell(
        name="Mordenkainen's Magnificent Mansion",
        level=7,
        casting_time="1 minute",
        ritual=False,
        range_str="300 feet",
        components="V, S, M (a miniature door worth 15+ GP)",
        duration="24 hours",
        concentration=False,
        class_names=["Bard", "Wizard"],
        description=(
            "You create a 5-by-10-foot doorway to a furnished extradimensional mansion of up to 50 contiguous 10-foot cubes. "
            "It includes food for 100 and 100 invisible servants obeying you. Contents vanish if removed; creatures are expelled when the spell ends."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Mordenkainen's Sword",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="90 feet",
        components="V, S, M (a miniature sword worth 250+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Bard", "Wizard"],
        description=(
            "You create a hovering spectral sword. When it appears and as a Bonus Action on later turns, you can move it 30 feet and make a melee spell attack for 4d12 + mod Force damage."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "Damage", "Force"],
    ),
    make_spell(
        name="Plane Shift",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S, M (a forked, metal rod worth 250+ GP and attuned to a plane of existence)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Cleric", "Druid", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "You and up to eight willing creatures linking hands travel to another plane, aiming for a general destination or teleportation circle you know. "
            "Appearing near the target as determined by the DM; circles too small place creatures in nearest open spaces."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Power Word Fortify",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Cleric"],
        description=(
            "You divide 120 temporary Hit Points among up to six creatures you can see within range."
        ),
        source="Player's Handbook (2024)",
        tags=["Enchantment", "Buff", "Temp HP"],
    ),
    make_spell(
        name="Prismatic Spray",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Wizard"],
        description=(
            "Eight rays shoot in a 60-foot cone; each creature makes a Dexterity save. Roll 1d8 per target for effects: 12d6 damage of various types, restraining/petrifying, blinding with planar banishment, or two rays on an 8."
        ),
        source="Player's Handbook (2024)",
        tags=["Evocation", "AOE", "Damage", "Fire", "Acid", "Lightning", "Poison", "Cold", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Project Image",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="500 miles",
        components="V, S, M (a statuette of yourself worth 5+ GP)",
        duration="1 day",
        concentration=True,
        class_names=["Bard", "Wizard"],
        description=(
            "You create an illusory duplicate at a location you have seen within range. It looks and sounds like you but is intangible. "
            "You perceive through it, move it with a Magic action up to 60 feet, and creatures can discern it with an Investigation check; physical interaction reveals the illusion."
        ),
        source="Player's Handbook (2024)",
        tags=["Illusion", "Utility"],
    ),
    make_spell(
        name="Regenerate",
        level=7,
        casting_time="1 minute",
        ritual=False,
        range_str="Touch",
        components="V, S, M (a prayer wheel)",
        duration="1 hour",
        concentration=False,
        class_names=["Bard", "Cleric", "Druid"],
        description=(
            "A creature regains 4d8 + 15 HP, then regains 1 HP at the start of each turn for the duration. Lost body parts regrow after 2 minutes."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "Healing", "Buff"],
    ),
    make_spell(
        name="Resurrection",
        level=7,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (a diamond worth 1,000+ GP, which the spell consumes)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Cleric"],
        description=(
            "You return a creature dead up to a century (not of old age or undead) to life with full Hit Points, curing poisons and restoring missing parts. "
            "The target takes a -4 penalty to d20 tests, reduced by 1 per Long Rest; casting on a body dead a year or more exhausts you until a Long Rest."
        ),
        source="Player's Handbook (2024)",
        tags=["Necromancy", "Healing", "Utility"],
    ),
    make_spell(
        name="Reverse Gravity",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="100 feet",
        components="V, S, M (a lodestone and iron filings)",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "Gravity reverses in a 50-foot-radius, 100-foot-high cylinder. Creatures and objects fall upward; a Dexterity save lets a creature grab a fixed object. "
            "Those reaching the top hover until the spell ends, then fall."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "AOE", "Damage", "Saving Throw", "Utility"],
    ),
    make_spell(
        name="Sequester",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S, M (gem dust worth 5,000+ GP, which the spell consumes)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You render an object or willing creature Invisible and warded from divination. If a creature, it is in suspended animation, Unconscious, and doesn't age or need sustenance. "
            "You can set a condition within 1 mile to end the spell; any damage also ends it."
        ),
        source="Player's Handbook (2024)",
        tags=["Transmutation", "Utility", "Defense"],
    ),
    make_spell(
        name="Simbul's Synostodweomer",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="Touch",
        components="V, S",
        duration="1 hour",
        concentration=False,
        class_names=["Sorcerer", "Wizard"],
        description=(
            "You infuse a touched creature with healing potential. Whenever it casts a spell using a slot, it can roll unexpended Hit Point Dice equal to the slot level, regaining that total + your spellcasting modifier; those dice are then spent."
        ),
        source="Forgotten Realms - Heroes of Faerun",
        tags=["Transmutation", "Healing", "Buff"],
    ),
    make_spell(
        name="Simulacrum",
        level=7,
        casting_time="12 hours",
        ritual=False,
        range_str="Touch",
        components="V, S, M (powdered ruby worth 1,500+ GP, which the spell consumes)",
        duration="Until dispelled",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You create a duplicate of a Beast or Humanoid present during casting, using snow or ice. It has half the original's HP, is a Construct, can't cast this spell, and obeys you. "
            "Repairs during a Long Rest cost 100 GP per HP. Casting again destroys previous simulacra."
        ),
        source="Player's Handbook (2024)",
        tags=["Illusion", "Utility"],
    ),
    make_spell(
        name="Symbol",
        level=7,
        casting_time="1 minute",
        ritual=False,
        range_str="Touch",
        components="V, S, M (powdered diamond worth 1,000+ GP, which the spell consumes)",
        duration="Until dispelled or triggered",
        concentration=False,
        class_names=["Bard", "Cleric", "Druid", "Wizard"],
        description=(
            "You inscribe a nearly invisible glyph on a surface or in an object. You set triggers and choose effects such as Death, Discord, Fear, Pain, Sleep, or Stunning. "
            "When triggered, the glyph glows for 10 minutes and targets creatures in a 60-foot-radius sphere; each effect calls for appropriate saving throws."
        ),
        source="Player's Handbook (2024)",
        tags=["Abjuration", "AOE", "Damage", "Debuff", "Saving Throw"],
    ),
    make_spell(
        name="Teleport",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="10 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Wizard"],
        description=(
            "You teleport yourself and up to eight willing creatures you can see within range, or one Large or smaller object not held by an unwilling creature, to a destination on the same plane. "
            "Arrival depends on familiarity per the Teleportation Outcome table."
        ),
        source="Player's Handbook (2024)",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Create Magen",
        level=7,
        casting_time="1 hour",
        ritual=False,
        range_str="Touch",
        components="V, S, M (quicksilver worth 500 GP, a life-sized doll, both consumed, and a crystal rod worth 1,500+ GP)",
        duration="Instantaneous",
        concentration=False,
        class_names=["Wizard"],
        description=(
            "You transform a prepared doll into a magen of a type you choose. Your Hit Point maximum decreases by the magen's CR (min 1) until a Wish restores it. The magen obeys your commands."
        ),
        source="Icewind Dale - Rime of the Frostmaiden",
        tags=["Transmutation", "Utility"],
    ),
    make_spell(
        name="Crown of Stars",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="Self",
        components="V, S",
        duration="1 hour",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "Seven motes of starlight orbit your head. As a Bonus Action, you can launch one at a target within 120 feet (ranged spell attack, 4d12 Radiant). "
            "Light radius depends on remaining motes; +2 motes for each slot level above 7."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "Damage", "Radiant", "Buff"],
    ),
    make_spell(
        name="Draconic Transformation",
        level=7,
        casting_time="Bonus Action",
        ritual=False,
        range_str="Self",
        components="V, S, M (a statuette of a dragon worth 500+ GP)",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Sorcerer", "Wizard"],
        description=(
            "You take on draconic features: blindsight 30 feet; spectral wings granting 60-foot fly speed; and a Breath Weapon usable on cast and as a Bonus Action, exhaling a 60-foot cone (Dex save, 6d8 Force damage, half on success)."
        ),
        source="Fizban's Treasury of Dragons",
        tags=["Transmutation", "Buff", "Damage", "Force", "AOE", "Saving Throw"],
    ),
    make_spell(
        name="Dream of the Blue Veil",
        level=7,
        casting_time="10 minutes",
        ritual=False,
        range_str="20 feet",
        components="V, S, M (a magic item or willing creature from the destination world)",
        duration="6 hours",
        concentration=False,
        class_names=["Bard", "Sorcerer", "Warlock", "Wizard"],
        description=(
            "You and up to eight willing creatures fall unconscious and experience visions of another Material world. If the spell completes, you all travel physically to that world near the linked item or native creature. The spell ends early for a creature that takes damage."
        ),
        source="Tasha's Cauldron of Everything",
        tags=["Conjuration", "Utility"],
    ),
    make_spell(
        name="Power Word: Pain",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V",
        duration="Instantaneous",
        concentration=False,
        class_names=["Sorcerer", "Warlock", "Wizard"],
        description=(
            "You speak a word afflicting one creature you can see with crippling pain if it has 100 HP or fewer (and is not immune to charm). "
            "Its speed can't exceed 10 feet, it has disadvantage on most rolls, and casting spells requires a successful Constitution save; it can end the pain with a Constitution save at each turn's end."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Enchantment", "Debuff"],
    ),
    make_spell(
        name="Temple of the Gods",
        level=7,
        casting_time="1 hour",
        ritual=False,
        range_str="120 feet",
        components="V, S, M (a holy symbol worth 5+ GP)",
        duration="24 hours",
        concentration=False,
        class_names=["Cleric"],
        description=(
            "You create a 120-foot cube temple dedicated to your deity or philosophy. You decide interior, lighting, doors, and opposed creature types barred or hindered (Charisma save to enter; d4 penalty inside). "
            "Blocks divination sensors and ethereal travel; healing in the temple gains bonus HP equal to your Wisdom modifier. Casting daily for a year makes it permanent."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Conjuration", "Defense", "Utility"],
    ),
    make_spell(
        name="Tether Essence",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="60 feet",
        components="V, S, M (a spool of platinum cord worth 250+ GP, which the spell consumes)",
        duration="1 hour",
        concentration=True,
        class_names=["Wizard"],
        description=(
            "Two creatures within range make Constitution saves (disadvantage if within 30 feet). If both fail, they are linked: damage and healing to one are applied to the other. "
            "If either drops to 0 HP or the spell ends on one, it ends on both."
        ),
        source="Explorer's Guide to Wildemount",
        tags=["Necromancy", "Debuff", "Utility", "Saving Throw"],
    ),
    make_spell(
        name="Whirlwind",
        level=7,
        casting_time="Action",
        ritual=False,
        range_str="300 feet",
        components="V, M (a piece of straw)",
        duration="1 minute",
        concentration=True,
        class_names=["Druid", "Wizard"],
        description=(
            "You summon a 10-foot-radius, 30-foot-high whirlwind. Move it up to 30 feet each turn. Creatures entering or in it make a Dexterity save for 10d6 Bludgeoning damage (half on success); Large or smaller that fail must make a Strength save or be Restrained, rising inside. "
            "Restrained creatures can use an action to escape and are flung away if they do."
        ),
        source="Xanathar's Guide to Everything",
        tags=["Evocation", "AOE", "Damage", "Bludgeoning", "Saving Throw"],
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
