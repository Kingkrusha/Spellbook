"""
Character Sheet data model for D&D 5e Spellbook Application.
Contains full character sheet information beyond just spell lists.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum


# ===== Armor Types for AC Calculation =====

class ArmorType(Enum):
    """Armor types for AC calculation."""
    NONE = ("None", 10, None, True)  # (name, base_ac, max_dex, add_dex)
    PADDED = ("Padded", 11, None, True)
    LEATHER = ("Leather", 11, None, True)
    STUDDED_LEATHER = ("Studded Leather", 12, None, True)
    HIDE = ("Hide", 12, 2, True)
    CHAIN_SHIRT = ("Chain Shirt", 13, 2, True)
    SCALE_MAIL = ("Scale Mail", 14, 2, True)
    BREASTPLATE = ("Breastplate", 14, 2, True)
    HALF_PLATE = ("Half Plate", 15, 2, True)
    RING_MAIL = ("Ring Mail", 14, 0, False)
    CHAIN_MAIL = ("Chain Mail", 16, 0, False)
    SPLINT = ("Splint", 17, 0, False)
    PLATE = ("Plate", 18, 0, False)
    
    @property
    def display_name(self) -> str:
        return self.value[0]
    
    @property
    def base_ac(self) -> int:
        return self.value[1]
    
    @property
    def max_dex_bonus(self) -> Optional[int]:
        """Maximum DEX bonus allowed, or None for no limit."""
        return self.value[2]
    
    @property
    def adds_dex(self) -> bool:
        """Whether this armor adds DEX modifier to AC."""
        return self.value[3]
    
    def is_heavy(self) -> bool:
        """Check if this is heavy armor."""
        return self in [ArmorType.RING_MAIL, ArmorType.CHAIN_MAIL, ArmorType.SPLINT, ArmorType.PLATE]
    
    def is_medium(self) -> bool:
        """Check if this is medium armor."""
        return self in [ArmorType.HIDE, ArmorType.CHAIN_SHIRT, ArmorType.SCALE_MAIL, ArmorType.BREASTPLATE, ArmorType.HALF_PLATE]
    
    def is_light(self) -> bool:
        """Check if this is light armor."""
        return self in [ArmorType.PADDED, ArmorType.LEATHER, ArmorType.STUDDED_LEATHER]
    
    @classmethod
    def from_name(cls, name: str) -> "ArmorType":
        """Get armor type from display name."""
        for armor in cls:
            if armor.display_name.lower() == name.lower():
                return armor
        return cls.NONE


# Simple list for common armor selections in dropdown
COMMON_ARMOR_OPTIONS = [
    ("None", ArmorType.NONE),
    ("Leather (11 + DEX)", ArmorType.LEATHER),
    ("Studded Leather (12 + DEX)", ArmorType.STUDDED_LEATHER),
    ("Chain Shirt (13 + DEX max 2)", ArmorType.CHAIN_SHIRT),
    ("Breastplate (14 + DEX max 2)", ArmorType.BREASTPLATE),
    ("Half Plate (15 + DEX max 2)", ArmorType.HALF_PLATE),
    ("Chain Mail (16)", ArmorType.CHAIN_MAIL),
    ("Splint (17)", ArmorType.SPLINT),
    ("Plate (18)", ArmorType.PLATE),
]

# Shield options - can be expanded for magic shields
SHIELD_OPTIONS = [
    ("None", 0),
    ("Shield (+2)", 2),
]


def calculate_ac(armor_type: ArmorType, dex_modifier: int, has_shield: bool = False,
                 unarmored_defense: str = "", con_modifier: int = 0, wis_modifier: int = 0,
                 cha_modifier: int = 0, shield_bonus: int = 0) -> int:
    """
    Calculate Armor Class based on armor, shield, and special abilities.
    
    Args:
        armor_type: The type of armor worn
        dex_modifier: Character's DEX modifier
        has_shield: Whether character is using a shield (legacy, use shield_bonus instead)
        unarmored_defense: Special unarmored AC formula (e.g., "10 + DEX + CON" for Barbarian)
        con_modifier: Character's CON modifier (for Barbarian unarmored defense)
        wis_modifier: Character's WIS modifier (for Monk unarmored defense)
        cha_modifier: Character's CHA modifier (for College of Dance unarmored defense)
        shield_bonus: AC bonus from shield (0 = no shield, 2 = normal shield, etc.)
    
    Returns:
        Calculated AC value
    """
    ac = 10
    
    # Check for unarmored defense (only applies when not wearing armor)
    if armor_type == ArmorType.NONE and unarmored_defense:
        if "DEX + CON" in unarmored_defense:
            # Barbarian: 10 + DEX + CON
            ac = 10 + dex_modifier + con_modifier
        elif "DEX + WIS" in unarmored_defense:
            # Monk: 10 + DEX + WIS
            ac = 10 + dex_modifier + wis_modifier
        elif "DEX + CHA" in unarmored_defense:
            # College of Dance Bard: 10 + DEX + CHA
            ac = 10 + dex_modifier + cha_modifier
        else:
            # Standard unarmored: 10 + DEX
            ac = 10 + dex_modifier
    elif armor_type == ArmorType.NONE:
        # Standard unarmored: 10 + DEX
        ac = 10 + dex_modifier
    else:
        # Armored: base AC + DEX (with possible cap)
        ac = armor_type.base_ac
        if armor_type.adds_dex:
            dex_bonus = dex_modifier
            if armor_type.max_dex_bonus is not None:
                dex_bonus = min(dex_modifier, armor_type.max_dex_bonus)
            ac += dex_bonus
    
    # Add shield bonus (use shield_bonus if provided, otherwise legacy has_shield)
    if shield_bonus > 0:
        ac += shield_bonus
    elif has_shield:
        ac += 2  # Legacy support
    
    return ac


# ===== Class Data for Hit Dice and Proficiencies =====

# Hit die type for each class
CLASS_HIT_DICE: Dict[str, str] = {
    "Artificer": "d8",
    "Barbarian": "d12",
    "Bard": "d8",
    "Cleric": "d8",
    "Druid": "d8",
    "Fighter": "d10",
    "Monk": "d8",
    "Paladin": "d10",
    "Ranger": "d10",
    "Rogue": "d8",
    "Sorcerer": "d6",
    "Warlock": "d8",
    "Wizard": "d6",
    "Custom": "d8",  # Default for custom class
}

# Average roll for each die type (rounded down)
HIT_DIE_AVERAGE: Dict[str, int] = {
    "d6": 4,  # 3.5 rounded up
    "d8": 5,  # 4.5 rounded up
    "d10": 6,  # 5.5 rounded up
    "d12": 7,  # 6.5 rounded up
}

# Maximum roll for each die type
HIT_DIE_MAX: Dict[str, int] = {
    "d6": 6,
    "d8": 8,
    "d10": 10,
    "d12": 12,
}

# Default proficiencies for each class (armor, weapons, tools, saving throws)
CLASS_PROFICIENCIES: Dict[str, Dict[str, List[str]]] = {
    "Artificer": {
        "armor": ["Light armor", "Medium armor", "Shields"],
        "weapons": ["Simple weapons"],
        "tools": ["Thieves' tools", "Tinker's tools", "One artisan's tools"],
        "saving_throws": ["Constitution", "Intelligence"],
    },
    "Barbarian": {
        "armor": ["Light armor", "Medium armor", "Shields"],
        "weapons": ["Simple weapons", "Martial weapons"],
        "tools": [],
        "saving_throws": ["Strength", "Constitution"],
    },
    "Bard": {
        "armor": ["Light armor"],
        "weapons": ["Simple weapons", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
        "tools": ["Three musical instruments"],
        "saving_throws": ["Dexterity", "Charisma"],
    },
    "Cleric": {
        "armor": ["Light armor", "Medium armor", "Shields"],
        "weapons": ["Simple weapons"],
        "tools": [],
        "saving_throws": ["Wisdom", "Charisma"],
    },
    "Druid": {
        "armor": ["Light armor", "Medium armor", "Shields (nonmetal)"],
        "weapons": ["Clubs", "Daggers", "Darts", "Javelins", "Maces", "Quarterstaffs", "Scimitars", "Sickles", "Slings", "Spears"],
        "tools": ["Herbalism kit"],
        "saving_throws": ["Intelligence", "Wisdom"],
    },
    "Fighter": {
        "armor": ["All armor", "Shields"],
        "weapons": ["Simple weapons", "Martial weapons"],
        "tools": [],
        "saving_throws": ["Strength", "Constitution"],
    },
    "Monk": {
        "armor": [],
        "weapons": ["Simple weapons", "Shortswords"],
        "tools": ["One artisan's tools or musical instrument"],
        "saving_throws": ["Strength", "Dexterity"],
    },
    "Paladin": {
        "armor": ["All armor", "Shields"],
        "weapons": ["Simple weapons", "Martial weapons"],
        "tools": [],
        "saving_throws": ["Wisdom", "Charisma"],
    },
    "Ranger": {
        "armor": ["Light armor", "Medium armor", "Shields"],
        "weapons": ["Simple weapons", "Martial weapons"],
        "tools": [],
        "saving_throws": ["Strength", "Dexterity"],
    },
    "Rogue": {
        "armor": ["Light armor"],
        "weapons": ["Simple weapons", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
        "tools": ["Thieves' tools"],
        "saving_throws": ["Dexterity", "Intelligence"],
    },
    "Sorcerer": {
        "armor": [],
        "weapons": ["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
        "tools": [],
        "saving_throws": ["Constitution", "Charisma"],
    },
    "Warlock": {
        "armor": ["Light armor"],
        "weapons": ["Simple weapons"],
        "tools": [],
        "saving_throws": ["Wisdom", "Charisma"],
    },
    "Wizard": {
        "armor": [],
        "weapons": ["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
        "tools": [],
        "saving_throws": ["Intelligence", "Wisdom"],
    },
    "Custom": {
        "armor": [],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
    },
}


def get_hit_dice_for_classes(class_levels: List[Tuple[str, int]]) -> Dict[str, int]:
    """
    Get hit dice breakdown for a character based on their class levels.
    Returns dict of hit_die_type -> count.
    """
    hit_dice = {}
    for class_name, level in class_levels:
        die_type = CLASS_HIT_DICE.get(class_name, "d8")
        hit_dice[die_type] = hit_dice.get(die_type, 0) + level
    return hit_dice


def calculate_hp_maximum(class_levels: List[Tuple[str, int]], con_modifier: int) -> int:
    """
    Calculate HP maximum based on class levels and constitution modifier.
    First level of primary class gets max roll, subsequent levels get average.
    """
    if not class_levels:
        return 10 + con_modifier
    
    total_hp = 0
    is_first_level = True
    
    for class_name, level in class_levels:
        die_type = CLASS_HIT_DICE.get(class_name, "d8")
        
        for lvl in range(level):
            if is_first_level:
                # First level gets max roll
                total_hp += HIT_DIE_MAX.get(die_type, 8) + con_modifier
                is_first_level = False
            else:
                # Subsequent levels get average
                total_hp += HIT_DIE_AVERAGE.get(die_type, 5) + con_modifier
    
    return max(1, total_hp)


def calculate_proficiency_bonus(total_level: int) -> int:
    """
    Calculate proficiency bonus based on total character level.
    Levels 1-4: +2, 5-8: +3, 9-12: +4, 13-16: +5, 17-20: +6
    """
    if total_level <= 0:
        return 2
    return 2 + (total_level - 1) // 4


def get_default_proficiencies(class_levels: List[Tuple[str, int]]) -> str:
    """
    Get default proficiencies text based on character classes.
    """
    if not class_levels:
        return ""
    
    all_armor = set()
    all_weapons = set()
    all_tools = set()
    all_saves = set()
    
    for class_name, _ in class_levels:
        profs = CLASS_PROFICIENCIES.get(class_name, {})
        all_armor.update(profs.get("armor", []))
        all_weapons.update(profs.get("weapons", []))
        all_tools.update(profs.get("tools", []))
        all_saves.update(profs.get("saving_throws", []))
    
    lines = []
    if all_armor:
        lines.append(f"Armor: {', '.join(sorted(all_armor))}")
    if all_weapons:
        lines.append(f"Weapons: {', '.join(sorted(all_weapons))}")
    if all_tools:
        lines.append(f"Tools: {', '.join(sorted(all_tools))}")
    if all_saves:
        lines.append(f"Saving Throws: {', '.join(sorted(all_saves))}")
    
    return "\n".join(lines)


class AbilityScore(Enum):
    """D&D 5e ability scores."""
    STRENGTH = "Strength"
    DEXTERITY = "Dexterity"
    CONSTITUTION = "Constitution"
    INTELLIGENCE = "Intelligence"
    WISDOM = "Wisdom"
    CHARISMA = "Charisma"
    
    @classmethod
    def short_name(cls, ability: "AbilityScore") -> str:
        """Return abbreviated ability name."""
        return {
            cls.STRENGTH: "STR",
            cls.DEXTERITY: "DEX",
            cls.CONSTITUTION: "CON",
            cls.INTELLIGENCE: "INT",
            cls.WISDOM: "WIS",
            cls.CHARISMA: "CHA"
        }.get(ability, "")


class Skill(Enum):
    """D&D 5e skills with their associated ability."""
    ACROBATICS = ("Acrobatics", AbilityScore.DEXTERITY)
    ANIMAL_HANDLING = ("Animal Handling", AbilityScore.WISDOM)
    ARCANA = ("Arcana", AbilityScore.INTELLIGENCE)
    ATHLETICS = ("Athletics", AbilityScore.STRENGTH)
    DECEPTION = ("Deception", AbilityScore.CHARISMA)
    HISTORY = ("History", AbilityScore.INTELLIGENCE)
    INSIGHT = ("Insight", AbilityScore.WISDOM)
    INTIMIDATION = ("Intimidation", AbilityScore.CHARISMA)
    INVESTIGATION = ("Investigation", AbilityScore.INTELLIGENCE)
    MEDICINE = ("Medicine", AbilityScore.WISDOM)
    NATURE = ("Nature", AbilityScore.INTELLIGENCE)
    PERCEPTION = ("Perception", AbilityScore.WISDOM)
    PERFORMANCE = ("Performance", AbilityScore.CHARISMA)
    PERSUASION = ("Persuasion", AbilityScore.CHARISMA)
    RELIGION = ("Religion", AbilityScore.INTELLIGENCE)
    SLEIGHT_OF_HAND = ("Sleight of Hand", AbilityScore.DEXTERITY)
    STEALTH = ("Stealth", AbilityScore.DEXTERITY)
    SURVIVAL = ("Survival", AbilityScore.WISDOM)
    
    @property
    def display_name(self) -> str:
        return self.value[0]
    
    @property
    def ability(self) -> AbilityScore:
        return self.value[1]


@dataclass
class AbilityScores:
    """Container for all six ability scores."""
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    
    def get(self, ability: AbilityScore) -> int:
        """Get score for an ability."""
        return {
            AbilityScore.STRENGTH: self.strength,
            AbilityScore.DEXTERITY: self.dexterity,
            AbilityScore.CONSTITUTION: self.constitution,
            AbilityScore.INTELLIGENCE: self.intelligence,
            AbilityScore.WISDOM: self.wisdom,
            AbilityScore.CHARISMA: self.charisma
        }.get(ability, 10)
    
    def set(self, ability: AbilityScore, value: int):
        """Set score for an ability."""
        value = max(1, min(30, value))  # D&D scores range 1-30
        if ability == AbilityScore.STRENGTH:
            self.strength = value
        elif ability == AbilityScore.DEXTERITY:
            self.dexterity = value
        elif ability == AbilityScore.CONSTITUTION:
            self.constitution = value
        elif ability == AbilityScore.INTELLIGENCE:
            self.intelligence = value
        elif ability == AbilityScore.WISDOM:
            self.wisdom = value
        elif ability == AbilityScore.CHARISMA:
            self.charisma = value
    
    def modifier(self, ability: AbilityScore) -> int:
        """Calculate ability modifier."""
        return (self.get(ability) - 10) // 2
    
    def to_dict(self) -> dict:
        return {
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AbilityScores":
        return cls(
            strength=data.get("strength", 10),
            dexterity=data.get("dexterity", 10),
            constitution=data.get("constitution", 10),
            intelligence=data.get("intelligence", 10),
            wisdom=data.get("wisdom", 10),
            charisma=data.get("charisma", 10)
        )


@dataclass
class SavingThrows:
    """Saving throw proficiencies."""
    strength: bool = False
    dexterity: bool = False
    constitution: bool = False
    intelligence: bool = False
    wisdom: bool = False
    charisma: bool = False
    
    def is_proficient(self, ability: AbilityScore) -> bool:
        """Check if proficient in a saving throw."""
        return {
            AbilityScore.STRENGTH: self.strength,
            AbilityScore.DEXTERITY: self.dexterity,
            AbilityScore.CONSTITUTION: self.constitution,
            AbilityScore.INTELLIGENCE: self.intelligence,
            AbilityScore.WISDOM: self.wisdom,
            AbilityScore.CHARISMA: self.charisma
        }.get(ability, False)
    
    def set_proficiency(self, ability: AbilityScore, proficient: bool):
        """Set saving throw proficiency."""
        if ability == AbilityScore.STRENGTH:
            self.strength = proficient
        elif ability == AbilityScore.DEXTERITY:
            self.dexterity = proficient
        elif ability == AbilityScore.CONSTITUTION:
            self.constitution = proficient
        elif ability == AbilityScore.INTELLIGENCE:
            self.intelligence = proficient
        elif ability == AbilityScore.WISDOM:
            self.wisdom = proficient
        elif ability == AbilityScore.CHARISMA:
            self.charisma = proficient
    
    def to_dict(self) -> dict:
        return {
            "strength": self.strength,
            "dexterity": self.dexterity,
            "constitution": self.constitution,
            "intelligence": self.intelligence,
            "wisdom": self.wisdom,
            "charisma": self.charisma
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SavingThrows":
        return cls(
            strength=data.get("strength", False),
            dexterity=data.get("dexterity", False),
            constitution=data.get("constitution", False),
            intelligence=data.get("intelligence", False),
            wisdom=data.get("wisdom", False),
            charisma=data.get("charisma", False)
        )


@dataclass
class SkillProficiencies:
    """Skill proficiencies (proficient, expertise, or neither)."""
    # 0 = not proficient, 1 = proficient, 2 = expertise
    acrobatics: int = 0
    animal_handling: int = 0
    arcana: int = 0
    athletics: int = 0
    deception: int = 0
    history: int = 0
    insight: int = 0
    intimidation: int = 0
    investigation: int = 0
    medicine: int = 0
    nature: int = 0
    perception: int = 0
    performance: int = 0
    persuasion: int = 0
    religion: int = 0
    sleight_of_hand: int = 0
    stealth: int = 0
    survival: int = 0
    
    def get(self, skill: Skill) -> int:
        """Get proficiency level for a skill (0=none, 1=proficient, 2=expertise)."""
        attr_name = skill.name.lower()
        return getattr(self, attr_name, 0)
    
    def set(self, skill: Skill, level: int):
        """Set proficiency level (0=none, 1=proficient, 2=expertise)."""
        level = max(0, min(2, level))
        attr_name = skill.name.lower()
        setattr(self, attr_name, level)
    
    def to_dict(self) -> dict:
        return {
            "acrobatics": self.acrobatics,
            "animal_handling": self.animal_handling,
            "arcana": self.arcana,
            "athletics": self.athletics,
            "deception": self.deception,
            "history": self.history,
            "insight": self.insight,
            "intimidation": self.intimidation,
            "investigation": self.investigation,
            "medicine": self.medicine,
            "nature": self.nature,
            "perception": self.perception,
            "performance": self.performance,
            "persuasion": self.persuasion,
            "religion": self.religion,
            "sleight_of_hand": self.sleight_of_hand,
            "stealth": self.stealth,
            "survival": self.survival
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SkillProficiencies":
        return cls(
            acrobatics=data.get("acrobatics", 0),
            animal_handling=data.get("animal_handling", 0),
            arcana=data.get("arcana", 0),
            athletics=data.get("athletics", 0),
            deception=data.get("deception", 0),
            history=data.get("history", 0),
            insight=data.get("insight", 0),
            intimidation=data.get("intimidation", 0),
            investigation=data.get("investigation", 0),
            medicine=data.get("medicine", 0),
            nature=data.get("nature", 0),
            perception=data.get("perception", 0),
            performance=data.get("performance", 0),
            persuasion=data.get("persuasion", 0),
            religion=data.get("religion", 0),
            sleight_of_hand=data.get("sleight_of_hand", 0),
            stealth=data.get("stealth", 0),
            survival=data.get("survival", 0)
        )


@dataclass
class DeathSaves:
    """Death saving throw tracking."""
    successes: int = 0
    failures: int = 0
    
    def add_success(self):
        self.successes = min(3, self.successes + 1)
    
    def add_failure(self):
        self.failures = min(3, self.failures + 1)
    
    def reset(self):
        self.successes = 0
        self.failures = 0
    
    def to_dict(self) -> dict:
        return {"successes": self.successes, "failures": self.failures}
    
    @classmethod
    def from_dict(cls, data: dict) -> "DeathSaves":
        return cls(
            successes=data.get("successes", 0),
            failures=data.get("failures", 0)
        )


@dataclass
class HitPoints:
    """Hit point tracking."""
    maximum: int = 10
    current: int = 10
    temporary: int = 0
    hit_dice_total: int = 1
    hit_dice_remaining: int = 1
    hit_die_type: str = "d8"  # e.g., "d8", "d10", "d12" (primary class die)
    # Track remaining dice per die type: {"d8": 3, "d10": 2}
    hit_dice_by_type: Dict[str, int] = field(default_factory=dict)
    
    def heal(self, amount: int):
        """Heal hit points."""
        self.current = min(self.maximum, self.current + amount)
    
    def damage(self, amount: int):
        """Take damage (temp HP first)."""
        remaining = amount
        if self.temporary > 0:
            temp_absorbed = min(self.temporary, remaining)
            self.temporary -= temp_absorbed
            remaining -= temp_absorbed
        self.current = max(0, self.current - remaining)
    
    def to_dict(self) -> dict:
        return {
            "maximum": self.maximum,
            "current": self.current,
            "temporary": self.temporary,
            "hit_dice_total": self.hit_dice_total,
            "hit_dice_remaining": self.hit_dice_remaining,
            "hit_die_type": self.hit_die_type,
            "hit_dice_by_type": self.hit_dice_by_type
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "HitPoints":
        return cls(
            maximum=data.get("maximum", 10),
            current=data.get("current", 10),
            temporary=data.get("temporary", 0),
            hit_dice_total=data.get("hit_dice_total", 1),
            hit_dice_remaining=data.get("hit_dice_remaining", 1),
            hit_die_type=data.get("hit_die_type", "d8"),
            hit_dice_by_type=data.get("hit_dice_by_type", {})
        )


@dataclass
class CharacterSheet:
    """
    Full D&D 5e character sheet data.
    Linked to a CharacterSpellList by name.
    """
    # Basic Info
    character_name: str = ""
    player_name: str = ""
    race: str = ""
    background: str = ""
    alignment: str = ""
    experience_points: int = 0
    age: str = ""
    height: str = ""
    weight: str = ""
    
    # Core Stats
    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    saving_throws: SavingThrows = field(default_factory=SavingThrows)
    skills: SkillProficiencies = field(default_factory=SkillProficiencies)
    
    # Combat
    armor_class: int = 10
    armor_type: str = "None"  # ArmorType display name for storage
    has_shield: bool = False  # Legacy - kept for backwards compatibility
    shield_bonus: int = 0  # Shield AC bonus (0 = no shield, 2 = normal shield, etc.)
    unarmored_defense: str = ""  # Formula like "10 + DEX + CON" for Barbarian
    initiative_bonus: int = 0  # Additional bonus beyond DEX
    speed: int = 30
    base_speed: int = 30  # Base speed before bonuses (race-based)
    hit_points: HitPoints = field(default_factory=HitPoints)
    death_saves: DeathSaves = field(default_factory=DeathSaves)
    inspiration: bool = False
    
    # Attacks (list of dicts with name, attack_bonus, damage)
    attacks: List[Dict[str, str]] = field(default_factory=list)
    
    # Proficiency
    proficiency_bonus: int = 2
    
    # Equipment & Features
    equipment: str = ""
    features_and_traits: str = ""
    other_proficiencies: str = ""  # Languages, tools, weapons, armor
    
    # Magic Items (list of dicts with name, description, attuned)
    magic_items: List[Dict[str, Any]] = field(default_factory=list)
    
    # Class Feature Uses (tracks current uses for class features like rage, bardic inspiration, etc.)
    # Format: {"class_name:feature_name": current_value}
    class_feature_uses: Dict[str, int] = field(default_factory=dict)
    
    # Ability score bonuses from class features (e.g., Primal Champion)
    # Format: {"feature_name": {"ability": bonus}} e.g., {"Primal Champion": {"strength": 4, "constitution": 4}}
    ability_bonuses: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Personality
    personality_traits: str = ""
    ideals: str = ""
    bonds: str = ""
    flaws: str = ""
    
    # Currency
    copper: int = 0
    silver: int = 0
    electrum: int = 0
    gold: int = 0
    platinum: int = 0
    
    # Additional notes
    notes: str = ""
    appearance: str = ""
    backstory: str = ""
    allies_and_organizations: str = ""
    
    def get_proficiency_bonus(self) -> int:
        """Return proficiency bonus based on level (stored separately or calculated)."""
        return self.proficiency_bonus
    
    def get_initiative(self) -> int:
        """Calculate initiative bonus."""
        return self.ability_scores.modifier(AbilityScore.DEXTERITY) + self.initiative_bonus
    
    def get_passive_perception(self) -> int:
        """Calculate passive perception."""
        perception_bonus = self.get_skill_bonus(Skill.PERCEPTION)
        return 10 + perception_bonus
    
    def get_saving_throw_bonus(self, ability: AbilityScore) -> int:
        """Calculate saving throw bonus for an ability."""
        base = self.get_effective_ability_modifier(ability)
        if self.saving_throws.is_proficient(ability):
            base += self.proficiency_bonus
        return base
    
    def get_skill_bonus(self, skill: Skill, jack_of_all_trades_bonus: int = 0) -> int:
        """Calculate skill bonus.
        
        Args:
            skill: The skill to calculate bonus for
            jack_of_all_trades_bonus: Half proficiency bonus (rounded down) to add
                                      if the character is not proficient in the skill
                                      (from Bard's Jack of All Trades feature)
        """
        ability_mod = self.get_effective_ability_modifier(skill.ability)
        prof_level = self.skills.get(skill)
        if prof_level == 1:
            return ability_mod + self.proficiency_bonus
        elif prof_level == 2:
            return ability_mod + (self.proficiency_bonus * 2)  # Expertise
        # Not proficient - add Jack of All Trades bonus if applicable
        return ability_mod + jack_of_all_trades_bonus
    
    def get_ability_bonus(self, ability: AbilityScore) -> int:
        """Get total ability bonus from features like Primal Champion."""
        ability_name = ability.name.lower()
        total_bonus = 0
        for feature_name, bonuses in self.ability_bonuses.items():
            total_bonus += bonuses.get(ability_name, 0)
        return total_bonus
    
    def get_effective_ability_score(self, ability: AbilityScore, max_score: int = 30) -> int:
        """Get ability score including bonuses from features."""
        base = self.ability_scores.get(ability)
        bonus = self.get_ability_bonus(ability)
        return min(base + bonus, max_score)
    
    def get_effective_ability_modifier(self, ability: AbilityScore, max_score: int = 30) -> int:
        """Get ability modifier using effective score with bonuses."""
        return (self.get_effective_ability_score(ability, max_score) - 10) // 2
    
    def apply_primal_champion(self):
        """Apply Primal Champion bonus (+4 STR/CON, max 25)."""
        # Get current base scores
        base_str = self.ability_scores.get(AbilityScore.STRENGTH)
        base_con = self.ability_scores.get(AbilityScore.CONSTITUTION)
        
        # Calculate bonus (up to 4, but don't exceed 25)
        str_bonus = min(4, 25 - base_str) if base_str < 25 else 0
        con_bonus = min(4, 25 - base_con) if base_con < 25 else 0
        
        # Apply as ability_bonuses (so we can track and revert)
        self.ability_bonuses["Primal Champion"] = {
            "strength": str_bonus,
            "constitution": con_bonus
        }
    
    def remove_primal_champion(self):
        """Remove Primal Champion bonus."""
        if "Primal Champion" in self.ability_bonuses:
            del self.ability_bonuses["Primal Champion"]
    
    def has_primal_champion(self) -> bool:
        """Check if character has Primal Champion bonus applied."""
        return "Primal Champion" in self.ability_bonuses
    
    def apply_body_and_mind(self):
        """Apply Body and Mind bonus (+4 DEX/WIS, max 25) for Monk level 20."""
        # Get current base scores
        base_dex = self.ability_scores.get(AbilityScore.DEXTERITY)
        base_wis = self.ability_scores.get(AbilityScore.WISDOM)
        
        # Calculate bonus (up to 4, but don't exceed 25)
        dex_bonus = min(4, 25 - base_dex) if base_dex < 25 else 0
        wis_bonus = min(4, 25 - base_wis) if base_wis < 25 else 0
        
        # Apply as ability_bonuses (so we can track and revert)
        self.ability_bonuses["Body and Mind"] = {
            "dexterity": dex_bonus,
            "wisdom": wis_bonus
        }
    
    def remove_body_and_mind(self):
        """Remove Body and Mind bonus."""
        if "Body and Mind" in self.ability_bonuses:
            del self.ability_bonuses["Body and Mind"]
    
    def has_body_and_mind(self) -> bool:
        """Check if character has Body and Mind bonus applied."""
        return "Body and Mind" in self.ability_bonuses
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "character_name": self.character_name,
            "player_name": self.player_name,
            "race": self.race,
            "background": self.background,
            "alignment": self.alignment,
            "experience_points": self.experience_points,
            "age": self.age,
            "height": self.height,
            "weight": self.weight,
            "ability_scores": self.ability_scores.to_dict(),
            "saving_throws": self.saving_throws.to_dict(),
            "skills": self.skills.to_dict(),
            "armor_class": self.armor_class,
            "armor_type": self.armor_type,
            "has_shield": self.has_shield,
            "shield_bonus": self.shield_bonus,
            "unarmored_defense": self.unarmored_defense,
            "initiative_bonus": self.initiative_bonus,
            "speed": self.speed,
            "base_speed": self.base_speed,
            "hit_points": self.hit_points.to_dict(),
            "death_saves": self.death_saves.to_dict(),
            "inspiration": self.inspiration,
            "attacks": self.attacks,
            "proficiency_bonus": self.proficiency_bonus,
            "equipment": self.equipment,
            "features_and_traits": self.features_and_traits,
            "other_proficiencies": self.other_proficiencies,
            "magic_items": self.magic_items,
            "class_feature_uses": self.class_feature_uses,
            "ability_bonuses": self.ability_bonuses,
            "personality_traits": self.personality_traits,
            "ideals": self.ideals,
            "bonds": self.bonds,
            "flaws": self.flaws,
            "copper": self.copper,
            "silver": self.silver,
            "electrum": self.electrum,
            "gold": self.gold,
            "platinum": self.platinum,
            "notes": self.notes,
            "appearance": self.appearance,
            "backstory": self.backstory,
            "allies_and_organizations": self.allies_and_organizations
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CharacterSheet":
        """Create from dictionary."""
        return cls(
            character_name=data.get("character_name", ""),
            player_name=data.get("player_name", ""),
            race=data.get("race", ""),
            background=data.get("background", ""),
            alignment=data.get("alignment", ""),
            experience_points=data.get("experience_points", 0),
            age=data.get("age", ""),
            height=data.get("height", ""),
            weight=data.get("weight", ""),
            ability_scores=AbilityScores.from_dict(data.get("ability_scores", {})),
            saving_throws=SavingThrows.from_dict(data.get("saving_throws", {})),
            skills=SkillProficiencies.from_dict(data.get("skills", {})),
            armor_class=data.get("armor_class", 10),
            armor_type=data.get("armor_type", "None"),
            has_shield=data.get("has_shield", False),
            shield_bonus=data.get("shield_bonus", 2 if data.get("has_shield", False) else 0),  # Migrate legacy
            unarmored_defense=data.get("unarmored_defense", ""),
            initiative_bonus=data.get("initiative_bonus", 0),
            speed=data.get("speed", 30),
            base_speed=data.get("base_speed", data.get("speed", 30)),  # Default to speed for migration
            hit_points=HitPoints.from_dict(data.get("hit_points", {})),
            death_saves=DeathSaves.from_dict(data.get("death_saves", {})),
            inspiration=data.get("inspiration", False),
            attacks=data.get("attacks", []),
            proficiency_bonus=data.get("proficiency_bonus", 2),
            equipment=data.get("equipment", ""),
            features_and_traits=data.get("features_and_traits", ""),
            other_proficiencies=data.get("other_proficiencies", ""),
            magic_items=data.get("magic_items", []),
            class_feature_uses=data.get("class_feature_uses", {}),
            ability_bonuses=data.get("ability_bonuses", {}),
            personality_traits=data.get("personality_traits", ""),
            ideals=data.get("ideals", ""),
            bonds=data.get("bonds", ""),
            flaws=data.get("flaws", ""),
            copper=data.get("copper", 0),
            silver=data.get("silver", 0),
            electrum=data.get("electrum", 0),
            gold=data.get("gold", 0),
            platinum=data.get("platinum", 0),
            notes=data.get("notes", ""),
            appearance=data.get("appearance", ""),
            backstory=data.get("backstory", ""),
            allies_and_organizations=data.get("allies_and_organizations", "")
        )
