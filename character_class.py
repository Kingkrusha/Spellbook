"""
Character Class data model for D&D 5e Spellbook Application.
Defines class features, abilities, trackable resources, and subclasses.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import json
import os
import sys


def get_data_path(filename: str) -> str:
    """Get the path to a data file, handling PyInstaller bundled apps."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        base_path = sys._MEIPASS
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


@dataclass
class TrackableFeature:
    """A class feature that can be tracked (uses, resources, etc.)."""
    title: str
    description: str = ""
    tracked_value: str = ""  # What is being tracked (e.g., "Rages", "Ki Points")
    has_uses: bool = False  # Whether this feature has limited uses
    max_uses: int = 0  # Maximum uses (if has_uses is True)
    current_uses: int = 0  # Current uses remaining
    recharge: str = "long_rest"  # "short_rest", "long_rest", "dawn", "never"
    level_scaling: Dict[int, int] = field(default_factory=dict)  # Level -> max_uses
    
    def get_max_uses_at_level(self, level: int) -> int:
        """Get max uses at a specific level."""
        if not self.level_scaling:
            return self.max_uses
        # Find the highest level that's <= current level
        max_uses = self.max_uses
        for lvl, uses in sorted(self.level_scaling.items()):
            if lvl <= level:
                max_uses = uses
        return max_uses
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "tracked_value": self.tracked_value,
            "has_uses": self.has_uses,
            "max_uses": self.max_uses,
            "current_uses": self.current_uses,
            "recharge": self.recharge,
            "level_scaling": {str(k): v for k, v in self.level_scaling.items()}
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TrackableFeature":
        level_scaling = {}
        for k, v in data.get("level_scaling", {}).items():
            level_scaling[int(k)] = v
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            tracked_value=data.get("tracked_value", ""),
            has_uses=data.get("has_uses", False),
            max_uses=data.get("max_uses", 0),
            current_uses=data.get("current_uses", 0),
            recharge=data.get("recharge", "long_rest"),
            level_scaling=level_scaling
        )


@dataclass
class ClassAbility:
    """An ability or feature gained at a specific level."""
    title: str
    description: str = ""
    is_subclass_feature: bool = False  # True if this comes from a subclass
    subclass_name: str = ""  # Name of the subclass if is_subclass_feature
    # Tables for features - list of tables, each table is a dict with title, columns, rows
    # Example: [{"title": "Magic Item Plans", "columns": ["Magic Item Plan", "Attunement"], "rows": [["Bag of Holding", "No"], ...]}]
    tables: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "is_subclass_feature": self.is_subclass_feature,
            "subclass_name": self.subclass_name,
            "tables": self.tables
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClassAbility":
        return cls(
            title=data.get("title", ""),
            description=data.get("description", ""),
            is_subclass_feature=data.get("is_subclass_feature", False),
            subclass_name=data.get("subclass_name", ""),
            tables=data.get("tables", [])
        )


@dataclass
class ClassLevel:
    """Features and abilities gained at a specific class level."""
    level: int
    abilities: List[ClassAbility] = field(default_factory=list)
    proficiency_bonus: int = 2  # Standard proficiency bonus for this level
    # Spellcaster columns (for level table display)
    cantrips_known: int = 0
    spells_known: int = 0
    spell_slots: Dict[int, int] = field(default_factory=dict)  # spell_level -> slot_count
    # Class-specific columns (e.g., Rage Damage, Martial Arts die)
    class_specific: Dict[str, str] = field(default_factory=dict)  # column_name -> value
    # Weapon Mastery
    weapon_masteries: int = 0
    
    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "abilities": [a.to_dict() for a in self.abilities],
            "proficiency_bonus": self.proficiency_bonus,
            "cantrips_known": self.cantrips_known,
            "spells_known": self.spells_known,
            "spell_slots": {str(k): v for k, v in self.spell_slots.items()},
            "class_specific": self.class_specific,
            "weapon_masteries": self.weapon_masteries
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClassLevel":
        spell_slots = {}
        for k, v in data.get("spell_slots", {}).items():
            spell_slots[int(k)] = v
        return cls(
            level=data.get("level", 1),
            abilities=[ClassAbility.from_dict(a) for a in data.get("abilities", [])],
            proficiency_bonus=data.get("proficiency_bonus", 2),
            cantrips_known=data.get("cantrips_known", 0),
            spells_known=data.get("spells_known", 0),
            spell_slots=spell_slots,
            class_specific=data.get("class_specific", {}),
            weapon_masteries=data.get("weapon_masteries", 0)
        )


@dataclass
class SubclassFeature:
    """A feature gained from a subclass at a specific level."""
    level: int
    title: str
    description: str = ""
    tables: List[Dict] = field(default_factory=list)  # Tables for this feature
    
    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "title": self.title,
            "description": self.description,
            "tables": self.tables
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SubclassFeature":
        return cls(
            level=data.get("level", 1),
            title=data.get("title", ""),
            description=data.get("description", ""),
            tables=data.get("tables", [])
        )


@dataclass
class SubclassSpell:
    """A spell granted by a subclass at a specific level."""
    spell_name: str
    level_gained: int  # Subclass level when spell is gained
    
    def to_dict(self) -> dict:
        return {
            "spell_name": self.spell_name,
            "level_gained": self.level_gained
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SubclassSpell":
        return cls(
            spell_name=data.get("spell_name", ""),
            level_gained=data.get("level_gained", 1)
        )


@dataclass
class ClassSpell:
    """A spell granted by a class feature at a specific level (always prepared)."""
    spell_name: str
    level_gained: int  # Class level when spell is gained
    always_prepared: bool = True  # Whether the spell is always prepared
    
    def to_dict(self) -> dict:
        return {
            "spell_name": self.spell_name,
            "level_gained": self.level_gained,
            "always_prepared": self.always_prepared
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ClassSpell":
        return cls(
            spell_name=data.get("spell_name", ""),
            level_gained=data.get("level_gained", 1),
            always_prepared=data.get("always_prepared", True)
        )


@dataclass
class SubclassDefinition:
    """Definition of a subclass (archetype, path, etc.)."""
    name: str
    parent_class: str  # Name of the parent class
    description: str = ""
    features: List[SubclassFeature] = field(default_factory=list)
    # Subclass spells - always prepared, don't count against limit
    subclass_spells: List[SubclassSpell] = field(default_factory=list)
    # Subclass-granted proficiencies (e.g., College of Valor)
    armor_proficiencies: List[str] = field(default_factory=list)
    weapon_proficiencies: List[str] = field(default_factory=list)
    # Subclass-specific unarmored defense (e.g., College of Dance: "10 + DEX + CHA")
    unarmored_defense: str = ""
    # Trackable features for this subclass (e.g., Psi Warrior's psionic dice)
    trackable_features: List[TrackableFeature] = field(default_factory=list)
    source: str = "Player's Handbook"
    is_custom: bool = False
    
    def get_features_at_level(self, level: int) -> List[SubclassFeature]:
        """Get subclass features gained at a specific level."""
        return [f for f in self.features if f.level == level]
    
    def get_all_features_up_to_level(self, level: int) -> List[SubclassFeature]:
        """Get all subclass features up to a level."""
        return [f for f in self.features if f.level <= level]
    
    def get_spells_at_level(self, level: int) -> List[SubclassSpell]:
        """Get subclass spells available at a specific class level."""
        return [s for s in self.subclass_spells if s.level_gained <= level]
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "parent_class": self.parent_class,
            "description": self.description,
            "features": [f.to_dict() for f in self.features],
            "subclass_spells": [s.to_dict() for s in self.subclass_spells],
            "armor_proficiencies": self.armor_proficiencies,
            "weapon_proficiencies": self.weapon_proficiencies,
            "unarmored_defense": self.unarmored_defense,
            "trackable_features": [f.to_dict() for f in self.trackable_features],
            "source": self.source,
            "is_custom": self.is_custom
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SubclassDefinition":
        return cls(
            name=data.get("name", ""),
            parent_class=data.get("parent_class", ""),
            description=data.get("description", ""),
            features=[SubclassFeature.from_dict(f) for f in data.get("features", [])],
            subclass_spells=[SubclassSpell.from_dict(s) for s in data.get("subclass_spells", [])],
            armor_proficiencies=data.get("armor_proficiencies", []),
            weapon_proficiencies=data.get("weapon_proficiencies", []),
            unarmored_defense=data.get("unarmored_defense", ""),
            trackable_features=[TrackableFeature.from_dict(f) for f in data.get("trackable_features", [])],
            source=data.get("source", "Player's Handbook"),
            is_custom=data.get("is_custom", False)
        )


@dataclass
class StartingEquipmentOption:
    """One option for starting equipment (A, B, etc.)."""
    option_letter: str  # "A", "B", etc.
    items: List[str] = field(default_factory=list)  # List of item descriptions
    
    def to_dict(self) -> dict:
        return {
            "option_letter": self.option_letter,
            "items": self.items
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "StartingEquipmentOption":
        return cls(
            option_letter=data.get("option_letter", "A"),
            items=data.get("items", [])
        )


@dataclass
class CharacterClassDefinition:
    """
    Complete definition of a D&D 5e character class.
    This stores the class template, not a character's instance of the class.
    """
    name: str
    hit_die: str = "d8"  # e.g., "d6", "d8", "d10", "d12"
    
    # Primary ability (for class requirements/features)
    primary_ability: str = ""  # e.g., "Strength", "Dexterity and Wisdom"
    
    # Proficiencies
    armor_proficiencies: List[str] = field(default_factory=list)
    weapon_proficiencies: List[str] = field(default_factory=list)
    tool_proficiencies: List[str] = field(default_factory=list)
    saving_throw_proficiencies: List[str] = field(default_factory=list)  # e.g., ["STR", "CON"]
    
    # Skill proficiencies - choose X from list
    skill_proficiency_choices: int = 2  # How many skills to choose
    skill_proficiency_options: List[str] = field(default_factory=list)  # Available skills
    
    # Starting equipment options
    starting_equipment: List[str] = field(default_factory=list)  # Legacy: simple text list
    starting_equipment_options: List[StartingEquipmentOption] = field(default_factory=list)  # New: structured options
    starting_gold_alternative: str = ""  # e.g., "75 GP" for buying equipment
    
    # Class description
    description: str = ""
    
    # Is this a spellcasting class?
    is_spellcaster: bool = False
    spellcasting_ability: str = ""  # "INT", "WIS", "CHA"
    
    # Level at which subclass is chosen
    subclass_level: int = 3
    subclass_name: str = ""  # e.g., "Primal Path", "Arcane Tradition", "Martial Archetype"
    
    # Available subclasses
    subclasses: List[SubclassDefinition] = field(default_factory=list)
    
    # Level progression - abilities gained at each level
    levels: Dict[int, ClassLevel] = field(default_factory=dict)
    
    # Trackable features (0-3) - these show up in the class features widget
    trackable_features: List[TrackableFeature] = field(default_factory=list)
    
    # Class table columns (for display)
    class_table_columns: List[str] = field(default_factory=list)  # e.g., ["Rages", "Rage Damage"]
    
    # Class feature spells - always prepared, don't count against limit (e.g., Divine Smite, Find Steed for Paladin)
    class_spells: List[ClassSpell] = field(default_factory=list)
    
    # Special AC calculation (e.g., Barbarian Unarmored Defense, Monk Unarmored Defense)
    unarmored_defense: str = ""  # e.g., "10 + DEX + CON" for Barbarian, "10 + DEX + WIS" for Monk
    
    # Is this a custom/homebrew class?
    is_custom: bool = False
    
    # Source book
    source: str = "Player's Handbook"
    
    def __post_init__(self):
        """Initialize level progression if not provided."""
        if not self.levels:
            # Create empty level entries for 1-20
            for lvl in range(1, 21):
                prof_bonus = 2 + (lvl - 1) // 4  # Standard 5e progression
                self.levels[lvl] = ClassLevel(level=lvl, proficiency_bonus=prof_bonus)
    
    def get_abilities_at_level(self, level: int) -> List[ClassAbility]:
        """Get abilities gained at a specific level."""
        if level in self.levels:
            return self.levels[level].abilities
        return []
    
    def get_all_abilities_up_to_level(self, level: int) -> List[ClassAbility]:
        """Get all abilities from level 1 up to the specified level."""
        abilities = []
        for lvl in range(1, level + 1):
            if lvl in self.levels:
                abilities.extend(self.levels[lvl].abilities)
        return abilities
    
    def add_trackable_feature(self, feature: TrackableFeature) -> bool:
        """Add a trackable feature. Returns False if already at max (3)."""
        if len(self.trackable_features) >= 3:
            return False
        self.trackable_features.append(feature)
        return True
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hit_die": self.hit_die,
            "primary_ability": self.primary_ability,
            "armor_proficiencies": self.armor_proficiencies,
            "weapon_proficiencies": self.weapon_proficiencies,
            "tool_proficiencies": self.tool_proficiencies,
            "saving_throw_proficiencies": self.saving_throw_proficiencies,
            "skill_proficiency_choices": self.skill_proficiency_choices,
            "skill_proficiency_options": self.skill_proficiency_options,
            "starting_equipment": self.starting_equipment,
            "starting_equipment_options": [o.to_dict() for o in self.starting_equipment_options],
            "starting_gold_alternative": self.starting_gold_alternative,
            "description": self.description,
            "is_spellcaster": self.is_spellcaster,
            "spellcasting_ability": self.spellcasting_ability,
            "subclass_level": self.subclass_level,
            "subclass_name": self.subclass_name,
            "subclasses": [s.to_dict() for s in self.subclasses],
            "levels": {str(k): v.to_dict() for k, v in self.levels.items()},
            "trackable_features": [f.to_dict() for f in self.trackable_features],
            "class_table_columns": self.class_table_columns,
            "class_spells": [s.to_dict() for s in self.class_spells],
            "unarmored_defense": self.unarmored_defense,
            "is_custom": self.is_custom,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CharacterClassDefinition":
        levels_data = data.get("levels", {})
        levels = {}
        for k, v in levels_data.items():
            levels[int(k)] = ClassLevel.from_dict(v)
        
        instance = cls(
            name=data.get("name", "Unknown"),
            hit_die=data.get("hit_die", "d8"),
            primary_ability=data.get("primary_ability", ""),
            armor_proficiencies=data.get("armor_proficiencies", []),
            weapon_proficiencies=data.get("weapon_proficiencies", []),
            tool_proficiencies=data.get("tool_proficiencies", []),
            saving_throw_proficiencies=data.get("saving_throw_proficiencies", []),
            skill_proficiency_choices=data.get("skill_proficiency_choices", 2),
            skill_proficiency_options=data.get("skill_proficiency_options", []),
            starting_equipment=data.get("starting_equipment", []),
            starting_equipment_options=[StartingEquipmentOption.from_dict(o) for o in data.get("starting_equipment_options", [])],
            starting_gold_alternative=data.get("starting_gold_alternative", ""),
            description=data.get("description", ""),
            is_spellcaster=data.get("is_spellcaster", False),
            spellcasting_ability=data.get("spellcasting_ability", ""),
            subclass_level=data.get("subclass_level", 3),
            subclass_name=data.get("subclass_name", ""),
            subclasses=[SubclassDefinition.from_dict(s) for s in data.get("subclasses", [])],
            levels=levels,
            trackable_features=[TrackableFeature.from_dict(f) for f in data.get("trackable_features", [])],
            class_table_columns=data.get("class_table_columns", []),
            class_spells=[ClassSpell.from_dict(s) for s in data.get("class_spells", [])],
            unarmored_defense=data.get("unarmored_defense", ""),
            is_custom=data.get("is_custom", False),
            source=data.get("source", "Player's Handbook")
        )
        return instance


class ClassManager:
    """Manages character class definitions."""
    
    DEFAULT_FILE = "classes.json"
    
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or self.DEFAULT_FILE
        self._classes: Dict[str, CharacterClassDefinition] = {}
        self._listeners = []
    
    @property
    def classes(self) -> List[CharacterClassDefinition]:
        """Get all class definitions."""
        return list(self._classes.values())
    
    def get_class(self, name: str) -> Optional[CharacterClassDefinition]:
        """Get a class definition by name."""
        return self._classes.get(name)
    
    def add_listener(self, callback):
        """Add a listener for class changes."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback):
        """Remove a listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of changes."""
        for listener in self._listeners:
            try:
                listener()
            except Exception as e:
                print(f"Error notifying class listener: {e}")
    
    def load(self) -> bool:
        """Load classes from file."""
        # First try to load from the user's file path
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._classes = {
                        name: CharacterClassDefinition.from_dict(class_data)
                        for name, class_data in data.get("classes", {}).items()
                    }
                return True
            except Exception as e:
                print(f"Error loading classes from {self.file_path}: {e}")
        
        # If user file doesn't exist, try to load from bundled data (PyInstaller)
        bundled_path = get_data_path(self.DEFAULT_FILE)
        if bundled_path != self.file_path and os.path.exists(bundled_path):
            try:
                with open(bundled_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._classes = {
                        name: CharacterClassDefinition.from_dict(class_data)
                        for name, class_data in data.get("classes", {}).items()
                    }
                # Save to user file path so future modifications are preserved
                self.save()
                return True
            except Exception as e:
                print(f"Error loading bundled classes: {e}")
        
        # Fall back to generating default classes
        self._initialize_default_classes()
        self.save()
        return True
    
    def save(self) -> bool:
        """Save classes to file."""
        try:
            data = {
                "classes": {
                    name: cls.to_dict()
                    for name, cls in self._classes.items()
                }
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving classes: {e}")
            return False
    
    def add_class(self, class_def: CharacterClassDefinition) -> bool:
        """Add or update a class definition."""
        self._classes[class_def.name] = class_def
        self.save()
        self._notify_listeners()
        return True
    
    def delete_class(self, name: str) -> bool:
        """Delete a class definition."""
        if name in self._classes:
            del self._classes[name]
            self.save()
            self._notify_listeners()
            return True
        return False
    
    def _create_barbarian_class(self) -> CharacterClassDefinition:
        """Create the detailed Barbarian class definition."""
        # Level progression with abilities
        levels = {}
        
        # Proficiency bonus progression
        prof_bonuses = {1: 2, 2: 2, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 3, 9: 4, 10: 4,
                       11: 4, 12: 4, 13: 5, 14: 5, 15: 5, 16: 5, 17: 6, 18: 6, 19: 6, 20: 6}
        
        # Rage damage bonus by level
        rage_damage = {1: "+2", 2: "+2", 3: "+2", 4: "+2", 5: "+2", 6: "+2", 7: "+2", 8: "+2",
                      9: "+3", 10: "+3", 11: "+3", 12: "+3", 13: "+3", 14: "+3", 15: "+3", 16: "+4",
                      17: "+4", 18: "+4", 19: "+4", 20: "+4"}
        
        # Weapon masteries by level
        weapon_mast = {1: 2, 2: 2, 3: 2, 4: 3, 5: 3, 6: 3, 7: 3, 8: 3, 9: 3, 10: 4,
                      11: 4, 12: 4, 13: 4, 14: 4, 15: 4, 16: 4, 17: 4, 18: 4, 19: 4, 20: 4}
        
        # Number of rages by level
        rages = {1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 6: 4, 7: 4, 8: 4, 9: 4, 10: 4,
                11: 4, 12: 5, 13: 5, 14: 5, 15: 5, 16: 5, 17: 6, 18: 6, 19: 6, 20: 6}
        
        for lvl in range(1, 21):
            abilities = []
            class_specific = {
                "Rages": str(rages[lvl]),
                "Rage Damage": rage_damage[lvl],
                "Weapon Masteries": str(weapon_mast[lvl])
            }
            
            if lvl == 1:
                abilities = [
                    ClassAbility(
                        title="Rage",
                        description="""You can enter a Rage as a Bonus Action if you aren't wearing Heavy armor. You can enter your Rage a number of times shown for your Barbarian level in the Rages column of the Barbarian Features table. You regain one expended use when you finish a Short Rest, and you regain all expended uses when you finish a Long Rest.

*Damage Resistance.* You have Resistance to Bludgeoning, Piercing, and Slashing damage.

*Rage Damage.* When you make an attack using Strength—with either a weapon or an Unarmed Strike—and deal damage to the target, you gain a bonus to the damage that increases as you gain levels as a Barbarian, as shown in the Rage Damage column of the Barbarian Features table.

*Strength Advantage.* You have Advantage on Strength checks and Strength saving throws.

*No Concentration or Spells.* You can't maintain Concentration, and you can't cast spells.

*Duration.* The Rage lasts until the end of your next turn, and it ends early if you don Heavy armor or have the Incapacitated condition. If your Rage is still active on your next turn, you can extend the Rage for another round by doing one of the following:
• Make an attack roll against an enemy.
• Force an enemy to make a saving throw.
• Take a Bonus Action to extend your Rage.

Each time the Rage is extended, it lasts until the end of your next turn. You can maintain a Rage for up to 10 minutes."""
                    ),
                    ClassAbility(
                        title="Unarmored Defense",
                        description="""While you aren't wearing any armor, your base Armor Class equals 10 plus your Dexterity and Constitution modifiers. You can use a Shield and still gain this benefit."""
                    ),
                    ClassAbility(
                        title="Weapon Mastery",
                        description="""Your training with weapons allows you to use the mastery properties of two kinds of Simple or Martial Melee weapons of your choice, such as Greataxes and Handaxes. Whenever you finish a Long Rest, you can practice weapon drills and change one of those weapon choices.

When you reach certain Barbarian levels, you gain the ability to use the mastery properties of more kinds of weapons, as shown in the Weapon Mastery column of the Barbarian Features table."""
                    ),
                ]
            elif lvl == 2:
                abilities = [
                    ClassAbility(
                        title="Danger Sense",
                        description="""You gain an uncanny sense of when things aren't as they should be, giving you an edge when you dodge perils. You have Advantage on Dexterity saving throws unless you have the Incapacitated condition."""
                    ),
                    ClassAbility(
                        title="Reckless Attack",
                        description="""You can throw aside all concern for defense to attack with increased ferocity. When you make your first attack roll on your turn using Strength, you can decide to attack recklessly. Doing so gives you Advantage on attack rolls using Strength until the start of your next turn, but attack rolls against you have Advantage during that time."""
                    ),
                ]
            elif lvl == 3:
                abilities = [
                    ClassAbility(
                        title="Barbarian Subclass",
                        description="""You gain a Barbarian subclass of your choice. A subclass is a specialization that grants you features at certain Barbarian levels. For the rest of your career, you gain each of your subclass's features that are of your Barbarian level or lower.""",
                        is_subclass_feature=True
                    ),
                    ClassAbility(
                        title="Primal Knowledge",
                        description="""You gain proficiency in another skill of your choice from the skill list available to Barbarians at level 1.

In addition, while your Rage is active, you can channel primal power when you attempt certain tasks; whenever you make an ability check using one of the following skills, you can make it as a Strength check even if it normally uses a different ability: Acrobatics, Intimidation, Perception, Stealth, or Survival. When you use this ability, your Strength represents primal power coursing through you, honing your agility, bearing, and senses."""
                    ),
                ]
            elif lvl == 4:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify. You gain this feature again at Barbarian levels 8, 12, and 16."""
                    ),
                ]
            elif lvl == 5:
                abilities = [
                    ClassAbility(
                        title="Extra Attack",
                        description="""You can attack twice instead of once whenever you take the Attack action on your turn."""
                    ),
                    ClassAbility(
                        title="Fast Movement",
                        description="""Your speed increases by 10 feet while you aren't wearing Heavy armor."""
                    ),
                ]
            elif lvl == 6:
                abilities = [
                    ClassAbility(
                        title="Subclass Feature",
                        description="""You gain a feature from your Primal Path subclass.""",
                        is_subclass_feature=True
                    ),
                ]
            elif lvl == 7:
                abilities = [
                    ClassAbility(
                        title="Feral Instinct",
                        description="""Your instincts are so honed that you have Advantage on Initiative rolls."""
                    ),
                    ClassAbility(
                        title="Instinctive Pounce",
                        description="""As part of the Bonus Action you take to enter your Rage, you can move up to half your Speed."""
                    ),
                ]
            elif lvl == 8:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify."""
                    ),
                ]
            elif lvl == 9:
                abilities = [
                    ClassAbility(
                        title="Brutal Strike",
                        description="""If you use Reckless Attack, you can forgo any Advantage on one Strength-based attack roll of your choice on your turn. The chosen attack roll mustn't have Disadvantage. If the chosen attack roll hits, the target takes an extra 1d10 damage of the same type dealt by the weapon or Unarmed Strike, and you can cause one Brutal Strike effect of your choice. You have the following effect options.

*Forceful Blow.* The target is pushed 15 feet straight away from you. You can then move up to half your Speed straight toward the target without provoking Opportunity Attacks.

*Hamstring Blow.* The target's Speed is reduced by 15 feet until the start of your next turn. A target can be affected by only one Hamstring Blow at a time—the most recent one."""
                    ),
                ]
            elif lvl == 10:
                abilities = [
                    ClassAbility(
                        title="Subclass Feature",
                        description="""You gain a feature from your Primal Path subclass.""",
                        is_subclass_feature=True
                    ),
                ]
            elif lvl == 11:
                abilities = [
                    ClassAbility(
                        title="Relentless Rage",
                        description="""Your Rage can keep you fighting despite grievous wounds. If you drop to 0 Hit Points while your Rage is active and don't die outright, you can make a DC 10 Constitution saving throw. If you succeed, your Hit Points instead change to a number equal to twice your Barbarian level.

Each time you use this feature after the first, the DC increases by 5. When you finish a Short or Long Rest, the DC resets to 10."""
                    ),
                ]
            elif lvl == 12:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify."""
                    ),
                ]
            elif lvl == 13:
                abilities = [
                    ClassAbility(
                        title="Improved Brutal Strike",
                        description="""You have honed new ways to attack furiously. The following effects are now among your Brutal Strike options.

*Staggering Blow.* The target has Disadvantage on the next saving throw it makes, and it can't make Opportunity Attacks until the start of your next turn.

*Sundering Blow.* Before the start of your next turn, the next attack roll made by another creature against the target gains a +5 bonus to the roll. An attack roll can gain only one Sundering Blow bonus."""
                    ),
                ]
            elif lvl == 14:
                abilities = [
                    ClassAbility(
                        title="Subclass Feature",
                        description="""You gain a feature from your Primal Path subclass.""",
                        is_subclass_feature=True
                    ),
                ]
            elif lvl == 15:
                abilities = [
                    ClassAbility(
                        title="Persistent Rage",
                        description="""When you roll Initiative, you can regain all expended uses of Rage. After you regain uses of Rage in this way, you can't do so again until you finish a Long Rest.

In addition, your Rage is so fierce that it now lasts for 10 minutes without you needing to do anything to extend it from round to round. The Rage ends early if you have the Unconscious condition (not just Incapacitated) or don Heavy armor."""
                    ),
                ]
            elif lvl == 16:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify."""
                    ),
                ]
            elif lvl == 17:
                abilities = [
                    ClassAbility(
                        title="Improved Brutal Strike",
                        description="""The extra damage of your Brutal Strike increases to 2d10. In addition, you can use two different Brutal Strike effects whenever you use your Brutal Strike feature."""
                    ),
                ]
            elif lvl == 18:
                abilities = [
                    ClassAbility(
                        title="Indomitable Might",
                        description="""If your total for a Strength check or Strength saving throw is less than your Strength score, you can use that score in place of the total."""
                    ),
                ]
            elif lvl == 19:
                abilities = [
                    ClassAbility(
                        title="Epic Boon",
                        description="""You gain an Epic Boon feat or another feat of your choice for which you qualify. Boon of Irresistible Offense is recommended."""
                    ),
                ]
            elif lvl == 20:
                abilities = [
                    ClassAbility(
                        title="Primal Champion",
                        description="""You embody primal power. Your Strength and Constitution scores increase by 4, and their maximum is now 25."""
                    ),
                ]
            
            levels[lvl] = ClassLevel(
                level=lvl,
                abilities=abilities,
                proficiency_bonus=prof_bonuses[lvl],
                class_specific=class_specific,
                weapon_masteries=weapon_mast[lvl]
            )
        
        # Create trackable feature for Rage
        rage_feature = TrackableFeature(
            title="Rage",
            description="Number of times you can enter a Rage.",
            tracked_value="Rages",
            has_uses=True,
            max_uses=2,
            current_uses=2,
            recharge="long_rest",
            level_scaling={1: 2, 3: 3, 6: 4, 12: 5, 17: 6}  # Max 6 rages at level 17+
        )
        
        # Create Path of the Berserker subclass
        berserker = SubclassDefinition(
            name="Path of the Berserker",
            parent_class="Barbarian",
            description="""Barbarians who walk the Path of the Berserker direct their Rage primarily toward violence. Their path is one of untrammeled fury, and they thrill in the chaos of battle as they allow their Rage to seize and empower them.""",
            features=[
                SubclassFeature(
                    level=3,
                    title="Frenzy",
                    description="""If you use Reckless Attack while your Rage is active, you deal extra damage to the first target you hit on your turn with a Strength-based attack. To determine the extra damage, roll a number of d6s equal to your Rage Damage bonus, and add them together. The damage has the same type as the weapon or Unarmed Strike used for the attack."""
                ),
                SubclassFeature(
                    level=6,
                    title="Mindless Rage",
                    description="""You have Immunity to the Charmed and Frightened conditions while your Rage is active. If you're Charmed or Frightened when you enter your Rage, the condition ends on you."""
                ),
                SubclassFeature(
                    level=10,
                    title="Retaliation",
                    description="""When you take damage from a creature that is within 5 feet of you, you can take a Reaction to make one melee attack against that creature, using a weapon or an Unarmed Strike."""
                ),
                SubclassFeature(
                    level=14,
                    title="Intimidating Presence",
                    description="""As a Bonus Action, you can strike terror into others with your menacing presence and primal power. When you do so, each creature of your choice in a 30-foot Emanation originating from you must make a Wisdom saving throw (DC 8 plus your Strength modifier and Proficiency Bonus). On a failed save, a creature has the Frightened condition for 1 minute. At the end of each of the Frightened creature's turns, the creature repeats the save, ending the effect on itself on a success.

Once you use this feature, you can't use it again until you finish a Long Rest unless you expend a use of your Rage (no action required) to restore your use of it."""
                ),
            ],
            source="Player's Handbook (2024)"
        )
        
        # Create Path of the Wild Heart subclass
        wild_heart = SubclassDefinition(
            name="Path of the Wild Heart",
            parent_class="Barbarian",
            description="""Barbarians who follow the Path of the Wild Heart view themselves as kin to animals. These Barbarians learn magical means to communicate with animals, and their Rage heightens their connection to animals as it fills them with supernatural might.""",
            features=[
                SubclassFeature(
                    level=3,
                    title="Animal Speaker",
                    description="""You can cast the Beast Sense and Speak with Animals spells but only as Rituals. Wisdom is your spellcasting ability for them."""
                ),
                SubclassFeature(
                    level=3,
                    title="Rage of the Wilds",
                    description="""Your Rage taps into the primal power of animals. Whenever you activate your Rage, you gain one of the following options of your choice.

*Bear.* While your Rage is active, you have Resistance to every damage type except Force, Necrotic, Psychic, and Radiant.

*Eagle.* When you activate your Rage, you can take the Disengage and Dash actions as part of that Bonus Action. While your Rage is active, you can take a Bonus Action to take both of those actions.

*Wolf.* While your Rage is active, your allies have Advantage on attack rolls against any enemy of yours within 5 feet of you."""
                ),
                SubclassFeature(
                    level=6,
                    title="Aspect of the Wilds",
                    description="""You gain one of the following options of your choice. Whenever you finish a Long Rest, you can change your choice.

*Owl.* You have Darkvision with a range of 60 feet. If you already have Darkvision, its range increases by 60 feet.

*Panther.* You have a Climb Speed equal to your Speed.

*Salmon.* You have a Swim Speed equal to your Speed."""
                ),
                SubclassFeature(
                    level=10,
                    title="Nature Speaker",
                    description="""You can cast the Commune with Nature spell but only as a Ritual. Wisdom is your spellcasting ability for it."""
                ),
                SubclassFeature(
                    level=14,
                    title="Power of the Wilds",
                    description="""Whenever you activate your Rage, you gain one of the following options of your choice.

*Falcon.* While your Rage is active, you have a Fly Speed equal to your Speed if you aren't wearing any armor.

*Lion.* While your Rage is active, any of your enemies within 5 feet of you have Disadvantage on attack rolls against targets other than you or another Barbarian who has this option active.

*Ram.* While your Rage is active, you can cause a Large or smaller creature to have the Prone condition when you hit it with a melee attack."""
                ),
            ],
            source="Player's Handbook (2024)"
        )
        
        # Create Path of the World Tree subclass
        world_tree = SubclassDefinition(
            name="Path of the World Tree",
            parent_class="Barbarian",
            description="""Barbarians who follow the Path of the World Tree connect with the cosmic tree Yggdrasil through their Rage. This tree grows among the Outer Planes, connecting them to each other and the Material Plane. These Barbarians draw on the tree's magic for vitality and as a means of dimensional travel.""",
            features=[
                SubclassFeature(
                    level=3,
                    title="Vitality of the Tree",
                    description="""Your Rage taps into the life force of the World Tree. You gain the following benefits.

*Vitality Surge.* When you activate your Rage, you gain a number of Temporary Hit Points equal to your Barbarian level.

*Life-Giving Force.* At the start of each of your turns while your Rage is active, you can choose another creature within 10 feet of yourself to gain Temporary Hit Points. To determine the number of Temporary Hit Points, roll a number of d6s equal to your Rage Damage bonus, and add them together. If any of these Temporary Hit Points remain when your Rage ends, they vanish."""
                ),
                SubclassFeature(
                    level=6,
                    title="Branches of the Tree",
                    description="""Whenever a creature you can see starts its turn within 30 feet of you while your Rage is active, you can take a Reaction to summon spectral branches of the World Tree around it. The target must succeed on a Strength saving throw (DC 8 plus your Strength modifier and Proficiency Bonus) or be teleported to an unoccupied space you can see within 5 feet of yourself or in the nearest unoccupied space you can see. After the target teleports, you can reduce its Speed to 0 until the end of the current turn."""
                ),
                SubclassFeature(
                    level=10,
                    title="Battering Roots",
                    description="""During your turn, your reach is 10 feet greater with any Melee weapon that has the Heavy or Versatile property, as tendrils of the World Tree extend from you. When you hit with such a weapon on your turn, you can activate the Push or Topple mastery property in addition to a different mastery property you're using with that weapon."""
                ),
                SubclassFeature(
                    level=14,
                    title="Travel Along the Tree",
                    description="""When you activate your Rage and as a Bonus Action while your Rage is active, you can teleport up to 60 feet to an unoccupied space you can see.

In addition, once per Rage, you can increase the range of that teleport to 150 feet. When you do so, you can also bring up to six willing creatures who are within 10 feet of you. Each creature teleports to an unoccupied space of your choice within 10 feet of your destination space."""
                ),
            ],
            source="Player's Handbook (2024)"
        )
        
        # Create Path of the Zealot subclass
        zealot = SubclassDefinition(
            name="Path of the Zealot",
            parent_class="Barbarian",
            description="""Barbarians who walk the Path of the Zealot receive boons from a god or pantheon. These Barbarians experience their Rage as an ecstatic episode of divine union that infuses them with power. They are often allies to the priests and other followers of their god or pantheon.""",
            features=[
                SubclassFeature(
                    level=3,
                    title="Divine Fury",
                    description="""You can channel divine power into your strikes. On each of your turns while your Rage is active, the first creature you hit with a weapon or an Unarmed Strike takes extra damage equal to 1d6 plus half your Barbarian level (round down). The extra damage is Necrotic or Radiant; you choose the type each time you deal the damage."""
                ),
                SubclassFeature(
                    level=3,
                    title="Warrior of the Gods",
                    description="""A divine entity helps ensure you can continue the fight. You have a pool of four d12s that you can spend to heal yourself. As a Bonus Action, you can expend dice from the pool, roll them, and regain a number of Hit Points equal to the roll's total.

Your pool regains all expended dice when you finish a Long Rest.

The pool's maximum number of dice increases by one when you reach Barbarian levels 6 (5 dice), 12 (6 dice), and 17 (7 dice)."""
                ),
                SubclassFeature(
                    level=6,
                    title="Fanatical Focus",
                    description="""Once per active Rage, if you fail a saving throw, you can reroll it with a bonus equal to your Rage Damage bonus, and you must use the new roll."""
                ),
                SubclassFeature(
                    level=10,
                    title="Zealous Presence",
                    description="""As a Bonus Action, you unleash a battle cry infused with divine energy. Up to ten other creatures of your choice within 60 feet of you gain Advantage on attack rolls and saving throws until the start of your next turn.

Once you use this feature, you can't use it again until you finish a Long Rest unless you expend a use of your Rage (no action required) to restore your use of it."""
                ),
                SubclassFeature(
                    level=14,
                    title="Rage of the Gods",
                    description="""When you activate your Rage, you can assume the form of a divine warrior. This form lasts for 1 minute or until you drop to 0 Hit Points. Once you use this feature, you can't do so again until you finish a Long Rest.

While in this form, you gain the benefits below.

*Flight.* You have a Fly Speed equal to your Speed and can hover.

*Resistance.* You have Resistance to Necrotic, Psychic, and Radiant damage.

*Revivification.* When a creature within 30 feet of you would drop to 0 Hit Points, you can take a Reaction to expend a use of your Rage to instead change the target's Hit Points to a number equal to your Barbarian level."""
                ),
            ],
            source="Player's Handbook (2024)"
        )
        
        return CharacterClassDefinition(
            name="Barbarian",
            hit_die="d12",
            primary_ability="Strength",
            armor_proficiencies=["Light Armor", "Medium Armor", "Shields"],
            weapon_proficiencies=["Simple Weapons", "Martial Weapons"],
            saving_throw_proficiencies=["STR", "CON"],
            skill_proficiency_choices=2,
            skill_proficiency_options=["Animal Handling", "Athletics", "Intimidation", "Nature", "Perception", "Survival"],
            starting_equipment_options=[
                StartingEquipmentOption(
                    option_letter="A",
                    items=["Greataxe", "4 Handaxes", "Explorer's Pack", "15 GP"]
                ),
                StartingEquipmentOption(
                    option_letter="B",
                    items=["75 GP"]
                ),
            ],
            starting_gold_alternative="75 GP",
            description="""Barbarians are mighty warriors who are powered by primal forces of the multiverse that manifest as a Rage. More than a mere emotion—and not limited to anger—this Rage is an incarnation of a predator's ferocity, a storm's fury, and a sea's turmoil.

Some Barbarians personify their Rage as a fierce spirit or revered forebear. Others see it as a connection to the pain and anguish of the world, as an impersonal force, or as an expression of their own deepest self. For every Barbarian, their Rage is a power that fuels not just battle frenzy but also uncanny reflexes and feats of strength.""",
            is_spellcaster=False,
            subclass_level=3,
            subclass_name="Primal Path",
            subclasses=[berserker, wild_heart, world_tree, zealot],
            levels=levels,
            trackable_features=[rage_feature],
            class_table_columns=["Rages", "Rage Damage", "Weapon Masteries"],
            unarmored_defense="10 + DEX + CON",
            is_custom=False,
            source="Player's Handbook (2024)"
        )

    def _create_artificer_class(self) -> CharacterClassDefinition:
        """Create the complete Artificer class definition."""
        levels = {}
        
        # Proficiency bonuses by level
        prof_bonuses = {lvl: 2 + (lvl - 1) // 4 for lvl in range(1, 21)}
        
        # Artificer class-specific columns by level
        # Plans Known, Magic Items, Cantrips, Prepared Spells, Spell Slots 1st-5th
        artificer_data = {
            1:  {"Plans Known": "-", "Magic Items": "-", "Cantrips": "2", "Prepared Spells": "2", "1st": "2", "2nd": "-", "3rd": "-", "4th": "-", "5th": "-"},
            2:  {"Plans Known": "4", "Magic Items": "2", "Cantrips": "2", "Prepared Spells": "3", "1st": "2", "2nd": "-", "3rd": "-", "4th": "-", "5th": "-"},
            3:  {"Plans Known": "4", "Magic Items": "2", "Cantrips": "2", "Prepared Spells": "4", "1st": "3", "2nd": "-", "3rd": "-", "4th": "-", "5th": "-"},
            4:  {"Plans Known": "4", "Magic Items": "2", "Cantrips": "2", "Prepared Spells": "5", "1st": "3", "2nd": "-", "3rd": "-", "4th": "-", "5th": "-"},
            5:  {"Plans Known": "4", "Magic Items": "2", "Cantrips": "2", "Prepared Spells": "6", "1st": "4", "2nd": "2", "3rd": "-", "4th": "-", "5th": "-"},
            6:  {"Plans Known": "5", "Magic Items": "3", "Cantrips": "2", "Prepared Spells": "6", "1st": "4", "2nd": "2", "3rd": "-", "4th": "-", "5th": "-"},
            7:  {"Plans Known": "5", "Magic Items": "3", "Cantrips": "2", "Prepared Spells": "7", "1st": "4", "2nd": "3", "3rd": "-", "4th": "-", "5th": "-"},
            8:  {"Plans Known": "5", "Magic Items": "3", "Cantrips": "2", "Prepared Spells": "7", "1st": "4", "2nd": "3", "3rd": "-", "4th": "-", "5th": "-"},
            9:  {"Plans Known": "5", "Magic Items": "3", "Cantrips": "2", "Prepared Spells": "9", "1st": "4", "2nd": "3", "3rd": "2", "4th": "-", "5th": "-"},
            10: {"Plans Known": "6", "Magic Items": "4", "Cantrips": "3", "Prepared Spells": "9", "1st": "4", "2nd": "3", "3rd": "2", "4th": "-", "5th": "-"},
            11: {"Plans Known": "6", "Magic Items": "4", "Cantrips": "3", "Prepared Spells": "10", "1st": "4", "2nd": "3", "3rd": "3", "4th": "-", "5th": "-"},
            12: {"Plans Known": "6", "Magic Items": "4", "Cantrips": "3", "Prepared Spells": "10", "1st": "4", "2nd": "3", "3rd": "3", "4th": "-", "5th": "-"},
            13: {"Plans Known": "6", "Magic Items": "4", "Cantrips": "3", "Prepared Spells": "11", "1st": "4", "2nd": "3", "3rd": "3", "4th": "1", "5th": "-"},
            14: {"Plans Known": "7", "Magic Items": "5", "Cantrips": "4", "Prepared Spells": "11", "1st": "4", "2nd": "3", "3rd": "3", "4th": "1", "5th": "-"},
            15: {"Plans Known": "7", "Magic Items": "5", "Cantrips": "4", "Prepared Spells": "12", "1st": "4", "2nd": "3", "3rd": "3", "4th": "2", "5th": "-"},
            16: {"Plans Known": "7", "Magic Items": "5", "Cantrips": "4", "Prepared Spells": "12", "1st": "4", "2nd": "3", "3rd": "3", "4th": "2", "5th": "-"},
            17: {"Plans Known": "7", "Magic Items": "5", "Cantrips": "4", "Prepared Spells": "14", "1st": "4", "2nd": "3", "3rd": "3", "4th": "3", "5th": "1"},
            18: {"Plans Known": "8", "Magic Items": "6", "Cantrips": "4", "Prepared Spells": "14", "1st": "4", "2nd": "3", "3rd": "3", "4th": "3", "5th": "1"},
            19: {"Plans Known": "8", "Magic Items": "6", "Cantrips": "4", "Prepared Spells": "15", "1st": "4", "2nd": "3", "3rd": "3", "4th": "3", "5th": "2"},
            20: {"Plans Known": "8", "Magic Items": "6", "Cantrips": "4", "Prepared Spells": "15", "1st": "4", "2nd": "3", "3rd": "3", "4th": "3", "5th": "2"},
        }
        
        for lvl in range(1, 21):
            abilities = []
            class_specific = artificer_data[lvl]
            
            if lvl == 1:
                abilities = [
                    ClassAbility(
                        title="Spellcasting",
                        description="""You have learned how to channel magical energy through objects. See the Player's Handbook for the rules on spellcasting. The information below details how you use those rules with Artificer spells, which appear in the Artificer Spell List.

*Tools Required.* You produce your Artificer spells through tools. You can use Thieves' Tools, Tinker's Tools, or another kind of Artisan's Tools with which you have proficiency as a Spellcasting Focus, and you must have one of those focuses in hand when you cast an Artificer spell (meaning the spell has an M component when you cast it).

*Cantrips.* You know two Artificer cantrips of your choice. Acid Splash and Prestidigitation are recommended. Whenever you finish a Long Rest, you can replace one of your cantrips from this feature with another Artificer cantrip of your choice. When you reach Artificer levels 10 and 14, you learn another Artificer cantrip of your choice, as shown in the Cantrips column of the Artificer Features table.

*Spell Slots.* The Artificer Features table shows how many spell slots you have to cast your level 1+ spells. You regain all expended slots when you finish a Long Rest.

*Prepared Spells of Level 1+.* You prepare the list of level 1+ spells that are available for you to cast with this feature. To start, choose two level 1 Artificer spells. Cure Wounds and Grease are recommended.

The number of spells on your list increases as you gain Artificer levels, as shown in the Prepared Spells column of the Artificer Features table. Whenever that number increases, choose additional Artificer spells until the number of spells on your list matches the number on the table. The chosen spells must be of a level for which you have spell slots.

If another Artificer feature gives you spells that you always have prepared, those don't count against the number of spells you can prepare with this feature, but those spells otherwise count as Artificer spells for you.

*Changing Your Prepared Spells.* Whenever you finish a Long Rest, you can change your list of prepared spells, replacing any of the spells there with other Artificer spells for which you have spell slots.

*Spellcasting Ability.* Intelligence is your spellcasting ability for your Artificer spells."""
                    ),
                    ClassAbility(
                        title="Tinker's Magic",
                        description="""You know the Mending cantrip.

As a Magic action while holding Tinker's Tools, you can create one item in an unoccupied space within 5 feet of yourself, choosing the item from the following list:

The item lasts until you finish a Long Rest, at which point it vanishes.

You can use this feature a number of times equal to your Intelligence modifier (minimum of once), and you regain all expended uses when you finish a Long Rest.""",
                        tables=[{
                            "title": "",
                            "columns": ["", "", ""],
                            "rows": [
                                ["Ball Bearings", "Flask", "Pouch"],
                                ["Basket", "Grappling Hook", "Rope"],
                                ["Bedroll", "Hunting Trap", "Sack"],
                                ["Bell", "Jug", "Shovel"],
                                ["Blanket", "Lamp", "Spikes, Iron"],
                                ["Block and Tackle", "Manacles", "String"],
                                ["Bottle, Glass", "Net", "Tinderbox"],
                                ["Bucket", "Oil", "Torch"],
                                ["Caltrops", "Paper", "Vial"],
                                ["Candle", "Parchment", ""],
                                ["Crowbar", "Pole", ""],
                            ]
                        }]
                    ),
                ]
            elif lvl == 2:
                # Magic Item Plans tables
                plans_level_2 = {
                    "title": "Magic Item Plans (Artificer Level 2+)",
                    "columns": ["Magic Item Plan", "Attunement"],
                    "rows": [
                        ["Alchemy Jug", "No"],
                        ["Bag of Holding", "No"],
                        ["Cap of Water Breathing", "No"],
                        ["Common magic item that isn't a Potion, a Scroll, or cursed (you can learn this option multiple times and must select a different item each time; each item selected counts as a different plan)", "Varies"],
                        ["Goggles of Night", "No"],
                        ["Manifold Tool", "Yes"],
                        ["Repeating Shot", "Yes"],
                        ["Returning Weapon", "No"],
                        ["Rope of Climbing", "No"],
                        ["Sending Stones", "No"],
                        ["Shield +1", "No"],
                        ["Wand of Magic Detection", "No"],
                        ["Wand of Secrets", "No"],
                        ["Wand of the War Mage +1", "Yes"],
                        ["Weapon +1", "No"],
                        ["Wraps of Unarmed Power +1", "No"],
                    ]
                }
                plans_level_6 = {
                    "title": "Magic Item Plans (Artificer Level 6+)",
                    "columns": ["Magic Item Plan", "Attunement"],
                    "rows": [
                        ["Armor +1", "No"],
                        ["Boots of Elvenkind", "No"],
                        ["Boots of the Winding Path", "Yes"],
                        ["Cloak of Elvenkind", "Yes"],
                        ["Cloak of the Manta Ray", "No"],
                        ["Dazzling Weapon", "Yes"],
                        ["Eyes of Charming", "Yes"],
                        ["Eyes of Minute Seeing", "No"],
                        ["Gloves of Thievery", "No"],
                        ["Helm of Awareness", "No"],
                        ["Lantern of Revealing", "No"],
                        ["Mind Sharpener", "Yes"],
                        ["Necklace of Adaption", "Yes"],
                        ["Pipes of Haunting", "No"],
                        ["Repulsion Shield", "No"],
                        ["Ring of Swimming", "No"],
                        ["Ring of Water Walking", "No"],
                        ["Sentinel Shield", "No"],
                        ["Spell-Refueling Ring", "Yes"],
                        ["Wand of Magic Missiles", "No"],
                        ["Wand of Web", "No"],
                        ["Weapon of Warning", "Yes"],
                    ]
                }
                plans_level_10 = {
                    "title": "Magic Item Plans (Artificer Level 10+)",
                    "columns": ["Magic Item Plan", "Attunement"],
                    "rows": [
                        ["Armor of Resistance", "Yes"],
                        ["Dagger of Venom", "No"],
                        ["Elven Chain", "No"],
                        ["Ring of Feather Falling", "Yes"],
                        ["Ring of Jumping", "Yes"],
                        ["Ring of Mind Shielding", "Yes"],
                        ["Shield +2", "No"],
                        ["Uncommon Wondrous Item that isn't cursed (you can learn this option multiple times and must select a different item each time; each item selected counts as a different plan)", "Varies"],
                        ["Wand of the War Mage +2", "Yes"],
                        ["Weapon +2", "No"],
                        ["Wraps of Unarmed Power +2", "No"],
                    ]
                }
                plans_level_14 = {
                    "title": "Magic Item Plans (Artificer Level 14+)",
                    "columns": ["Magic Item Plan", "Attunement"],
                    "rows": [
                        ["Armor +2", "No"],
                        ["Arrow-Catching Shield", "Yes"],
                        ["Flame Tongue", "Yes"],
                        ["Rare Wondrous Item that isn't cursed (you can learn this option multiple times and must select a different item each time; each item selected counts as a different plan)", "Varies"],
                        ["Ring of Free Action", "Yes"],
                        ["Ring of Protection", "Yes"],
                        ["Ring of the Ram", "Yes"],
                    ]
                }
                abilities = [
                    ClassAbility(
                        title="Replicate Magic Item",
                        description="""You have learned arcane plans that you use to make magic items.

*Plans Known.* When you gain this feature, choose four plans to learn from the Magic Item Plans (Artificer Level 2+) table. Bag of Holding, Cap of Water Breathing, Sending Stones, and Wand of the War Mage are recommended. Whenever you gain an Artificer level, you can replace one of the plans you know with a new plan for which you qualify.

You learn another plan of your choice when you reach certain Artificer levels, as shown in the Plans Known column of the Artificer Features table. When you choose a plan to learn, you choose it from any Magic Item Plans table for which you qualify.

*Creating an Item.* When you finish a Long Rest, you can create one or two different magic items if you have Tinker's Tools in hand. Each item is based on one of the plans you know for this feature.

If a created item requires Attunement, you can attune yourself to it the instant you create it. If you decide to attune to the item later, you must do so using the normal process for Attunement.

When you reach certain Artificer levels specified in the Magic Items column of the Artificer Features table, the number of magic items you can create at the end of a Long Rest increases. Each item you create must be based on a different plan you know.

You can't have more magic items from this feature than the number shown in the Magic Items column of the Artificer Features table for your level. If you try to exceed your maximum number of magic items for this feature, the oldest item vanishes, and then the new item appears.

*Duration.* A magic item created by this feature functions as the normal magic item, except its magic isn't permanent; when you die, the magic item vanishes after 1d4 days. If you replace a plan you know with a new plan, any magic item created with the replaced plan immediately vanishes.

*Spellcasting Focus.* You can use any Wand or Weapon created by this feature as a Spellcasting Focus in lieu of using a set of Artisan's Tools.""",
                        tables=[plans_level_2, plans_level_6, plans_level_10, plans_level_14]
                    ),
                ]
            elif lvl == 3:
                abilities = [
                    ClassAbility(
                        title="Artificer Subclass",
                        description="""You gain an Artificer subclass of your choice. A subclass is a specialization that grants you features at certain Artificer levels. For the rest of your career, you gain each of your subclass's features that are of your Artificer level or lower.""",
                        is_subclass_feature=True
                    ),
                ]
            elif lvl == 4:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify. You gain this feature again at Artificer levels 8, 12, and 16."""
                    ),
                ]
            elif lvl == 5:
                abilities = [
                    ClassAbility(
                        title="Subclass Feature",
                        description="""You gain a feature from your Artificer subclass.""",
                        is_subclass_feature=True
                    ),
                ]
            elif lvl == 6:
                abilities = [
                    ClassAbility(
                        title="Magic Item Tinker",
                        description="""Your Replicate Magic Item feature gains the following options.

*Charge Magic Item.* As a Bonus Action, you can touch a magic item within 5 feet of yourself that you created with Replicate Magic Item and that uses charges. You expend a level 1+ spell slot and recharge the item. The number of charges the item regains is equal to the level of spell slot expended.

*Drain Magic Item.* As a Bonus Action, you can touch a magic item within 5 feet of yourself that you created with Replicate Magic Item and cause the item to vanish, converting its magical energy into a spell slot. The slot is level 1 if the item is Common or level 2 if the item is Uncommon or Rare. Once you use this feature, you can't do so again until you finish a Long Rest. Any spell slot you create with this feature vanishes when you finish a Long Rest.

*Transmute Magic Item.* As a Magic action, you can touch one magic item within 5 feet of yourself that you created with Replicate Magic Item and transform it into a different magic item. The resulting item must be based on a magic item plan you know. Once you use this feature, you can't do so again until you finish a Long Rest."""
                    ),
                ]
            elif lvl == 7:
                abilities = [
                    ClassAbility(
                        title="Flash of Genius",
                        description="""When you or a creature you can see within 30 feet of you fails an ability check or a saving throw, you can take a Reaction to add a bonus to the roll, potentially causing it to succeed. The bonus equals your Intelligence modifier (minimum of +1).

You can take this Reaction a number of times equal to your Intelligence modifier (minimum of once). You regain all expended uses when you finish a Long Rest."""
                    ),
                ]
            elif lvl == 8:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify. You gain this feature again at Artificer levels 8, 12, and 16."""
                    ),
                ]
            elif lvl == 9:
                abilities = [
                    ClassAbility(
                        title="Subclass Feature",
                        description="""You gain a feature from your Artificer subclass.""",
                        is_subclass_feature=True
                    ),
                ]
            elif lvl == 10:
                abilities = [
                    ClassAbility(
                        title="Magic Item Adept",
                        description="""You can now attune to up to four magic items at once."""
                    ),
                ]
            elif lvl == 11:
                abilities = [
                    ClassAbility(
                        title="Spell-Storing Item",
                        description="""Whenever you finish a Long Rest, you can touch one Simple or Martial weapon or one item that you can use as a Spellcasting Focus, and you store a spell in it, choosing a level 1, 2, or 3 Artificer spell that has a casting time of an action and doesn't require a Material component that is consumed by the spell (you needn't have the spell prepared).

While holding the object, a creature can take a Magic action to produce the spell's effect from it, using your spellcasting ability modifier. If the spell requires Concentration, the creature must concentrate. Once a creature has used the object to produce the spell's effect, the object can't be used this way again until the start of the creature's next turn.

The spell stays in the object until it's been used a number of times equal to twice your Intelligence modifier (minimum of twice) or until you use this feature again to store a spell in an object."""
                    ),
                ]
            elif lvl == 12:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify. You gain this feature again at Artificer levels 8, 12, and 16."""
                    ),
                ]
            elif lvl == 13:
                abilities = []  # No new feature at level 13
            elif lvl == 14:
                abilities = [
                    ClassAbility(
                        title="Advanced Artifice",
                        description="""You gain the following benefits.

*Magic Item Savant.* You can now attune to up to five magic items at once.

*Refreshed Genius.* When you finish a Short Rest, you regain one expended use of your Flash of Genius feature."""
                    ),
                ]
            elif lvl == 15:
                abilities = [
                    ClassAbility(
                        title="Subclass Feature",
                        description="""You gain a feature from your Artificer subclass.""",
                        is_subclass_feature=True
                    ),
                ]
            elif lvl == 16:
                abilities = [
                    ClassAbility(
                        title="Ability Score Improvement",
                        description="""You gain the Ability Score Improvement feat or another feat of your choice for which you qualify. You gain this feature again at Artificer levels 8, 12, and 16."""
                    ),
                ]
            elif lvl == 17:
                abilities = []  # No new feature at level 17
            elif lvl == 18:
                abilities = [
                    ClassAbility(
                        title="Magic Item Master",
                        description="""You can now attune to up to six magic items at once."""
                    ),
                ]
            elif lvl == 19:
                abilities = [
                    ClassAbility(
                        title="Epic Boon",
                        description="""You gain an Epic Boon feat or another feat of your choice for which you qualify. Boon of Energy Resistance is recommended."""
                    ),
                ]
            elif lvl == 20:
                abilities = [
                    ClassAbility(
                        title="Soul of Artifice",
                        description="""You have developed a mystical connection to your magic items, which you can draw on for aid. You gain the following benefits.

*Cheat Death.* If you're reduced to 0 Hit Points but not killed outright, you can disintegrate any number of Uncommon or Rare magic items created by your Replicate Magic Item feature. If you do so, your Hit Points instead change to a number equal to 20 times the number of magic items disintegrated.

*Magical Guidance.* When you finish a Short Rest, you regain all expended uses of your Flash of Genius if you have Attunement to at least one magic item."""
                    ),
                ]
            
            levels[lvl] = ClassLevel(
                level=lvl,
                abilities=abilities,
                proficiency_bonus=prof_bonuses[lvl],
                class_specific=class_specific
            )
        
        # Create trackable feature for Flash of Genius
        flash_of_genius = TrackableFeature(
            title="Flash of Genius",
            description="Add INT modifier to failed ability checks or saving throws.",
            tracked_value="Uses",
            has_uses=True,
            max_uses=3,  # Default INT modifier of 3
            current_uses=3,
            recharge="long_rest",
            level_scaling={7: 3}  # Available from level 7
        )
        
        # Create trackable feature for Tinker's Magic
        tinkers_magic = TrackableFeature(
            title="Tinker's Magic",
            description="Create mundane items with Tinker's Tools.",
            tracked_value="Uses",
            has_uses=True,
            max_uses=3,  # Default INT modifier of 3
            current_uses=3,
            recharge="long_rest",
            level_scaling={1: 3}
        )
        
        # Create Artificer subclasses
        alchemist = SubclassDefinition(
            name="Alchemist",
            parent_class="Artificer",
            description="An Alchemist is an expert at combining reagents to produce magical effects. Alchemists use their creations to give life and to leech it away.",
            source="Eberron - Forge of the Artificer",
            subclass_spells=[
                SubclassSpell("Healing Word", 3),
                SubclassSpell("Ray of Sickness", 3),
                SubclassSpell("Flaming Sphere", 5),
                SubclassSpell("Melf's Acid Arrow", 5),
                SubclassSpell("Gaseous Form", 9),
                SubclassSpell("Mass Healing Word", 9),
                SubclassSpell("Death Ward", 13),
                SubclassSpell("Vitriolic Sphere", 13),
                SubclassSpell("Cloudkill", 17),
                SubclassSpell("Raise Dead", 17),
            ],
            features=[
                SubclassFeature(
                    level=3,
                    title="Tools of the Trade",
                    description="""*Tool Proficiency.* You gain proficiency with Alchemist's Supplies and the Herbalism Kit. If you already have one of these proficiencies, you gain proficiency with one other type of Artisan's Tools of your choice (or with two other types if you have both).

*Potion Crafting.* When you brew a potion using the crafting rules in the Dungeon Master's Guide, the amount of time required to craft it is halved."""
                ),
                SubclassFeature(
                    level=3,
                    title="Alchemist Spells",
                    description="When you reach an Artificer level specified in the Alchemist Spells table, you thereafter always have the listed spells prepared.",
                    tables=[{
                        "title": "Alchemist Spells",
                        "columns": ["Artificer Level", "Spells"],
                        "rows": [
                            ["3", "Healing Word, Ray of Sickness"],
                            ["5", "Flaming Sphere, Melf's Acid Arrow"],
                            ["9", "Gaseous Form, Mass Healing Word"],
                            ["13", "Death Ward, Vitriolic Sphere"],
                            ["17", "Cloudkill, Raise Dead"],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=3,
                    title="Experimental Elixir",
                    description="""Whenever you finish a Long Rest while holding Alchemist's Supplies, you can use that tool to magically produce two elixirs. For each elixir, roll on the Experimental Elixir table for the elixir's effect, which is triggered when someone drinks the elixir. The elixir appears in a vial, and the vial vanishes when the elixir is drunk or poured out. If any elixir remains when you finish a Long Rest, the elixir and its vial vanish.

*Drinking an Elixir.* As a Bonus Action, a creature can drink the elixir or administer it to another creature within 5 feet of itself.

*Creating Additional Elixirs.* As a Magic action while holding Alchemist's Supplies, you can expend one spell slot to create another elixir. When you do so, you choose its effect from the Experimental Elixir table rather than rolling.

When you reach certain Artificer levels, you can make an additional elixir at the end of each Long Rest: a total of three at level 5, four at level 9, and five at level 15.""",
                    tables=[{
                        "title": "Experimental Elixir",
                        "columns": ["D6", "Effect"],
                        "rows": [
                            ["1", "Healing. The drinker regains a number of Hit Points equal to 2d8 plus your Intelligence modifier. The number of Hit Points restored increases by 1d8 when you reach Artificer levels 9 (3d8) and 15 (4d8)."],
                            ["2", "Swiftness. The drinker's Speed increases by 10 feet for 1 hour. This bonus increases when you reach Artificer levels 9 (15 feet) and 15 (20 feet)."],
                            ["3", "Resilience. The drinker gains a +1 bonus to AC for 10 minutes. The duration increases when you reach Artificer levels 9 (1 hour) and 15 (8 hours)."],
                            ["4", "Boldness. The drinker can roll 1d4 and add the number rolled to every attack roll and saving throw it makes for the next minute. The duration increases when you reach Artificer levels 9 (10 minutes) and 15 (1 hour)."],
                            ["5", "Flight. The drinker gains a Fly Speed of 10 feet for 10 minutes. The Fly Speed increases when you reach Artificer levels 9 (20 feet) and 15 (30 feet)."],
                            ["6", "You determine the elixir's effect by choosing one of the other rows in this table."],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=5,
                    title="Alchemical Savant",
                    description="Whenever you cast a spell using your Alchemist's Supplies as the Spellcasting Focus, you gain a bonus to one roll of the spell. That roll must restore Hit Points or be a damage roll that deals Acid, Fire, or Poison damage. The bonus equals your Intelligence modifier (minimum bonus of +1)."
                ),
                SubclassFeature(
                    level=9,
                    title="Restorative Reagents",
                    description="You can cast Lesser Restoration without expending a spell slot and without preparing the spell, provided you use Alchemist's Supplies as the Spellcasting Focus. You can do so a number of times equal to your Intelligence modifier (minimum of once), and you regain all expended uses when you finish a Long Rest."
                ),
                SubclassFeature(
                    level=15,
                    title="Chemical Mastery",
                    description="""*Alchemical Eruption.* When you cast an Artificer spell that deals Acid, Fire, or Poison damage to a target, you can also deal 2d8 Force damage to that target. You can use this benefit only once on each of your turns.

*Chemical Resistance.* You gain Resistance to Acid damage and Poison damage. You also gain Immunity to the Poisoned condition.

*Conjured Cauldron.* You can cast Tasha's Bubbling Cauldron without expending a spell slot, without preparing the spell, and without Material components, provided you use Alchemist's Supplies as the Spellcasting Focus. Once you use this feature, you can't use it again until you finish a Long Rest."""
                ),
            ]
        )
        
        armorer = SubclassDefinition(
            name="Armorer",
            parent_class="Artificer",
            description="An Armorer modifies armor to function almost like a second skin. The armor is enhanced to hone the Armorer's magic, unleash potent attacks, and generate a formidable defense.",
            source="Eberron - Forge of the Artificer",
            subclass_spells=[
                SubclassSpell("Magic Missile", 3),
                SubclassSpell("Thunderwave", 3),
                SubclassSpell("Mirror Image", 5),
                SubclassSpell("Shatter", 5),
                SubclassSpell("Hypnotic Pattern", 9),
                SubclassSpell("Lightning Bolt", 9),
                SubclassSpell("Fire Shield", 13),
                SubclassSpell("Greater Invisibility", 13),
                SubclassSpell("Passwall", 17),
                SubclassSpell("Wall of Force", 17),
            ],
            features=[
                SubclassFeature(
                    level=3,
                    title="Tools of the Trade",
                    description="""*Armor Training.* You gain training with Heavy armor.

*Tool Proficiency.* You gain proficiency with Smith's Tools. If you already have this tool proficiency, you gain proficiency with one other type of Artisan's Tools of your choice.

*Armor Crafting.* When you craft nonmagical or magic armor, the amount of time required to craft it is halved."""
                ),
                SubclassFeature(
                    level=3,
                    title="Armorer Spells",
                    description="When you reach an Artificer level specified in the Armorer Spells table, you thereafter always have the listed spells prepared.",
                    tables=[{
                        "title": "Armorer Spells",
                        "columns": ["Artificer Level", "Spells"],
                        "rows": [
                            ["3", "Magic Missile, Thunderwave"],
                            ["5", "Mirror Image, Shatter"],
                            ["9", "Hypnotic Pattern, Lightning Bolt"],
                            ["13", "Fire Shield, Greater Invisibility"],
                            ["17", "Passwall, Wall of Force"],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=3,
                    title="Arcane Armor",
                    description="""As a Magic action while you have Smith's Tools in hand, you can turn a suit of armor you are wearing into Arcane Armor. The armor continues to be Arcane Armor until you don another suit of armor or you die.

You gain the following benefits while wearing your Arcane Armor.

*No Strength Requirement.* If the armor normally has a Strength requirement, the Arcane Armor lacks this requirement for you.

*Quick Don and Doff.* You can don or doff the armor as a Utilize action. The armor can't be removed against your will.

*Spellcasting Focus.* You can use the Arcane Armor as a Spellcasting Focus for your Artificer spells."""
                ),
                SubclassFeature(
                    level=3,
                    title="Armor Model",
                    description="""You can customize your Arcane Armor. When you do so, choose one of the following armor models: Dreadnaught, Guardian, or Infiltrator. The model you choose gives you special benefits while you wear it.

Each model includes a special weapon. When you attack with that weapon, you can add your Intelligence modifier, instead of your Strength or Dexterity modifier, to the attack and damage rolls.

You can change the armor's model whenever you finish a Short or Long Rest if you have Smith's Tools in hand.

*Dreadnaught.* You design your armor to become a towering juggernaut in battle. It has the following features:

*Force Demolisher.* An arcane wrecking ball or sledgehammer projects from your armor. The demolisher counts as a Simple Melee weapon with the Reach property, and it deals 1d10 Force damage on a hit. If you hit a creature that is at least one size smaller than you with the demolisher, you can push the creature up to 10 feet straight away from yourself or pull the creature up to 10 feet toward yourself.

*Giant Stature.* As a Bonus Action, you transform and enlarge your armor for 1 minute. For the duration, your reach increases by 5 feet, and if you are smaller than Large, you become Large, along with anything you are wearing. If there isn't enough room for you to increase your size, your size doesn't change. You can use this Bonus Action a number of times equal to your Intelligence modifier (minimum of once). You regain all expended uses when you finish a Long Rest.

*Guardian.* You design your armor to be in the front line of conflict. It has the following features:

*Thunder Pulse.* You can discharge concussive blasts with strikes from your armor. The pulse counts as a Simple Melee weapon and deals 1d8 Thunder damage on a hit. A creature hit by the pulse has Disadvantage on attack rolls against targets other than you until the start of your next turn.

*Defensive Field.* While Bloodied, you can take a Bonus Action to gain Temporary Hit Points equal to your Artificer level. You lose these Temporary Hit Points if you doff the armor.

*Infiltrator.* You customize your armor for subtler undertakings. It has the following features:

*Lightning Launcher.* A gemlike node appears on your armor, from which you can shoot bolts of lightning. The launcher counts as a Simple Ranged weapon with a normal range of 90 feet and a long range of 300 feet, and it deals 1d6 Lightning damage on a hit. Once on each of your turns when you hit a creature with the launcher, you can deal an extra 1d6 Lightning damage to that target.

*Powered Steps.* Your Speed increases by 5 feet.

*Dampening Field.* You have Advantage on Dexterity (Stealth) checks. If the armor imposes Disadvantage on such checks, the Advantage and Disadvantage cancel each other, as normal."""
                ),
                SubclassFeature(
                    level=5,
                    title="Extra Attack",
                    description="You can attack twice instead of once whenever you take the Attack action on your turn."
                ),
                SubclassFeature(
                    level=9,
                    title="Improved Armorer",
                    description="""*Armor Replication.* You learn an additional plan for your Replicate Magic Item feature, and it must be in the Armor category. If you replace that plan, you must replace it with another Armor plan. In addition, you can create an additional item with that feature, and the item must also be in the Armor category.

*Improved Arsenal.* You gain a +1 bonus to attack and damage rolls made with the special weapon of your Arcane Armor model."""
                ),
                SubclassFeature(
                    level=15,
                    title="Perfected Armor",
                    description="""Your Arcane Armor gains additional benefits based on its model, as detailed below.

*Dreadnaught.* The damage die of your Force Demolisher increases to 2d6 Force damage. In addition, when you use your Giant Stature, your reach increases by 10 feet, your size can increase to Large or Huge (your choice), and you have Advantage on Strength checks and Strength saving throws for the duration.

*Guardian.* The damage die of your Thunder Pulse increases to 1d10 Thunder damage. In addition, when a Huge or smaller creature you can see ends its turn within 30 feet of you, you can take a Reaction to magically force that creature to make a Strength saving throw against your spell save DC. On a failed save, you pull the creature up to 25 feet directly toward you to an unoccupied space. If you pull the target to a space within 5 feet of yourself, you can make a melee weapon attack against it as part of this Reaction. You can take this Reaction a number of times equal to your Intelligence modifier (minimum of once), and you regain all expended uses when you finish a Long Rest.

*Infiltrator.* The damage die of your Lightning Launcher increases to 2d6 Lightning damage. Any creature that takes Lightning damage from your Lightning Launcher glimmers with magical light until the start of your next turn. The glimmering creature sheds Dim Light in a 5-foot radius, and it has Disadvantage on attack rolls against you, as the light jolts it if it attacks you. Additionally, as a Bonus Action, you can gain a Fly Speed equal to twice your Speed until the end of the current turn. You can take this Bonus Action a number of times equal to your Intelligence modifier (minimum of once), and you regain all expended uses when you finish a Long Rest."""
                ),
            ]
        )
        
        artillerist = SubclassDefinition(
            name="Artillerist",
            parent_class="Artificer",
            description="An Artillerist specializes in using magic to hurl energy, projectiles, and explosions on a battlefield.",
            source="Eberron - Forge of the Artificer",
            subclass_spells=[
                SubclassSpell("Shield", 3),
                SubclassSpell("Thunderwave", 3),
                SubclassSpell("Scorching Ray", 5),
                SubclassSpell("Shatter", 5),
                SubclassSpell("Fireball", 9),
                SubclassSpell("Wind Wall", 9),
                SubclassSpell("Ice Storm", 13),
                SubclassSpell("Wall of Fire", 13),
                SubclassSpell("Cone of Cold", 17),
                SubclassSpell("Wall of Force", 17),
            ],
            features=[
                SubclassFeature(
                    level=3,
                    title="Tools of the Trade",
                    description="""*Ranged Weaponry.* You gain proficiency with Martial Ranged weapons.

*Tool Proficiency.* You gain proficiency with Woodcarver's Tools. If you already have this proficiency, you gain proficiency with one other type of Artisan's Tools of your choice.

*Wand Crafting.* When you craft a magic Wand, the amount of time required to craft it is halved."""
                ),
                SubclassFeature(
                    level=3,
                    title="Artillerist Spells",
                    description="When you reach an Artificer level specified in the Artillerist Spells table, you thereafter always have the listed spells prepared.",
                    tables=[{
                        "title": "Artillerist Spells",
                        "columns": ["Artificer Level", "Spells"],
                        "rows": [
                            ["3", "Shield, Thunderwave"],
                            ["5", "Scorching Ray, Shatter"],
                            ["9", "Fireball, Wind Wall"],
                            ["13", "Ice Storm, Wall of Fire"],
                            ["17", "Cone of Cold, Wall of Force"],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=3,
                    title="Eldritch Cannon",
                    description="""Using Smith's Tools or Woodcarver's Tools, you can take a Magic action to create a Small or Tiny Eldritch Cannon in an unoccupied space on a horizontal surface within 5 feet of yourself. The cannon's game statistics appear below. You determine its appearance, including whether you carry it or not (and your choice of legs or wheels, for the latter). It disappears if it is reduced to 0 Hit Points or after 1 hour. You can dismiss it early as a Magic action.

Once you create a cannon, you can't do so again until you finish a Long Rest or expend a spell slot to create one. You can have only one cannon at a time and can't create one while you already have one.""",
                    tables=[{
                        "title": "Eldritch Cannon",
                        "columns": ["Statistic", "Value"],
                        "rows": [
                            ["Size", "Small or Tiny Object"],
                            ["Armor Class", "18"],
                            ["Hit Points", "5 × your Artificer level"],
                            ["Immunities", "Poison, Psychic"],
                            ["Flamethrower", "15-ft Cone, DEX save, 2d8 Fire damage"],
                            ["Force Ballista", "Ranged attack, 120 ft, 2d8 Force, push 5 ft"],
                            ["Protector", "10 ft radius, 1d8 + INT mod Temp HP"],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=5,
                    title="Arcane Firearm",
                    description="When you finish a Long Rest, you can use Woodcarver's Tools to carve special sigils into a Rod, Staff, Wand, or Martial Ranged weapon and thereby turn it into your Arcane Firearm. The sigils disappear from the object if you later carve them on a different item. The sigils otherwise last indefinitely. You can use your Arcane Firearm as a Spellcasting Focus for your Artificer spells. When you cast an Artificer spell through the firearm, roll 1d8, and you gain a bonus to one of the spell's damage rolls equal to the number rolled."
                ),
                SubclassFeature(
                    level=9,
                    title="Explosive Cannon",
                    description="""Every Eldritch Cannon you create is now more destructive.

*Detonate.* When your cannon takes damage, you can take a Reaction to command the cannon to detonate if you are within 60 feet of it. Doing so destroys the cannon and forces each creature within 20 feet of it to make a Dexterity saving throw against your spell save DC, taking 3d10 Force damage on a failed save or half as much damage on a successful one.

*Firepower.* The cannon's damage rolls and the number of Temporary Hit Points granted by Protector increase by 1d8."""
                ),
                SubclassFeature(
                    level=15,
                    title="Fortified Position",
                    description="""You're a master at forming well-defended emplacements using your Eldritch Cannon.

*Double Firepower.* You can now have two cannons at the same time, and you can create two with the same Magic action. (If you expend a spell slot to create the first cannon, you must expend another spell slot to create the second.) You can activate both of them with the same Bonus Action, ordering them to use the same activation option or different ones. You can't create a third cannon while you have two.

*Shimmering Field Projection.* You and your allies have Half Cover while within 10 feet of your Eldritch Cannon."""
                ),
            ]
        )
        
        battle_smith = SubclassDefinition(
            name="Battle Smith",
            parent_class="Artificer",
            description="A Battle Smith is a combination of protector and medic, an expert at defending others and repairing both materiel and personnel. To aid in their work, Battle Smiths are accompanied by a Steel Defender, a protective companion of their own creation.",
            source="Eberron - Forge of the Artificer",
            subclass_spells=[
                SubclassSpell("Heroism", 3),
                SubclassSpell("Shield", 3),
                SubclassSpell("Shining Smite", 5),
                SubclassSpell("Warding Bond", 5),
                SubclassSpell("Aura of Vitality", 9),
                SubclassSpell("Conjure Barrage", 9),
                SubclassSpell("Aura of Purity", 13),
                SubclassSpell("Fire Shield", 13),
                SubclassSpell("Banishing Smite", 17),
                SubclassSpell("Mass Cure Wounds", 17),
            ],
            features=[
                SubclassFeature(
                    level=3,
                    title="Tools of the Trade",
                    description="""*Tool Proficiency.* You gain proficiency with Smith's Tools. If you already have this proficiency, you gain proficiency with one other type of Artisan's Tools of your choice.

*Weapon Crafting.* When you craft a nonmagical or magic weapon, the amount of time required to craft it is halved."""
                ),
                SubclassFeature(
                    level=3,
                    title="Battle Smith Spells",
                    description="When you reach an Artificer level specified in the Battle Smith Spells table, you thereafter always have the listed spells prepared.",
                    tables=[{
                        "title": "Battle Smith Spells",
                        "columns": ["Artificer Level", "Spells"],
                        "rows": [
                            ["3", "Heroism, Shield"],
                            ["5", "Shining Smite, Warding Bond"],
                            ["9", "Aura of Vitality, Conjure Barrage"],
                            ["13", "Aura of Purity, Fire Shield"],
                            ["17", "Banishing Smite, Mass Cure Wounds"],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=3,
                    title="Battle Ready",
                    description="""Your combat training and your experiments with magic have paid off in two ways.

*Arcane Empowerment.* When you attack with a magic weapon, you can use your Intelligence modifier, instead of your Strength or Dexterity modifier, for the attack and damage rolls.

*Weapon Knowledge.* You gain proficiency with Martial weapons. You can use a weapon with which you have proficiency as a Spellcasting Focus for your Artificer spells."""
                ),
                SubclassFeature(
                    level=3,
                    title="Steel Defender",
                    description="""Your tinkering has borne you a companion, a Steel Defender. You determine the defender's appearance and whether it has two legs or four; your choices don't affect the defender's game statistics.

The defender is Friendly to you and your allies and obeys you. It vanishes if you die.

*The Defender in Combat.* In combat, the defender acts during your turn. It can move and take its Reaction on its own, but the only action it takes is the Dodge action unless you take a Bonus Action to command it to take an action. If you have the Incapacitated condition, the defender acts on its own and isn't limited to the Dodge action.

*Restoring or Replacing the Defender.* If the defender has died within the last hour, you can take a Magic action to touch it and expend a spell slot. The defender returns to life after 1 minute with all its Hit Points restored. Whenever you finish a Long Rest, you can create a new defender if you have Smith's Tools in hand. If you already have a defender from this feature, the first one vanishes.""",
                    tables=[{
                        "title": "Steel Defender",
                        "columns": ["Statistic", "Value"],
                        "rows": [
                            ["Size/Type", "Medium Construct"],
                            ["Armor Class", "12 + your Intelligence modifier"],
                            ["Hit Points", "5 + five times your Artificer level"],
                            ["Speed", "40 ft."],
                            ["STR/DEX/CON", "14 (+2) / 12 (+1) / 14 (+2)"],
                            ["INT/WIS/CHA", "4 (-3) / 10 (+0) / 6 (-2)"],
                            ["Immunities", "Poison; Charmed, Exhaustion, Poisoned"],
                            ["Force-Empowered Rend", "Melee, 1d8 + 2 + INT mod Force"],
                            ["Repair (3/Day)", "2d8 + INT mod HP to Construct"],
                            ["Deflect Attack", "Reaction: attacker has Disadvantage"],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=5,
                    title="Extra Attack",
                    description="You can attack twice instead of once whenever you take the Attack action on your turn. You can forgo one of your attacks when you take the Attack action to command your Steel Defender to take the Force-Empowered Rend action."
                ),
                SubclassFeature(
                    level=9,
                    title="Arcane Jolt",
                    description="""When either you hit a target with an attack roll using a magic weapon or your Steel Defender hits a target, you can channel magical energy through the strike to create one of the following effects:

*Destructive Energy.* The target takes an extra 2d6 Force damage.

*Restorative Energy.* Choose one creature or object you can see within 30 feet of the target. Healing energy flows into the chosen recipient, restoring 2d6 Hit Points to it.

You can use this energy a number of times equal to your Intelligence modifier (minimum of once), but you can do so no more than once per turn. You regain all expended uses when you finish a Long Rest."""
                ),
                SubclassFeature(
                    level=15,
                    title="Improved Defender",
                    description="""Your Arcane Jolt and Steel Defender have become more powerful.

*Improved Jolt.* The extra damage and healing of your Arcane Jolt both increase to 4d6.

*Improved Deflection.* Whenever your Steel Defender uses its Deflect Attack, the attacker takes Force damage equal to 1d4 plus your Intelligence modifier."""
                ),
            ]
        )
        
        cartographer = SubclassDefinition(
            name="Cartographer",
            parent_class="Artificer",
            description="Cartographers are the premier navigators and reconnaissance agents. Using their creations, Cartographers can highlight threats, safeguard allies, and carve portals to distant locations.",
            source="Eberron - Forge of the Artificer",
            subclass_spells=[
                SubclassSpell("Faerie Fire", 3),
                SubclassSpell("Guiding Bolt", 3),
                SubclassSpell("Healing Word", 3),
                SubclassSpell("Locate Object", 5),
                SubclassSpell("Mind Spike", 5),
                SubclassSpell("Call Lightning", 9),
                SubclassSpell("Clairvoyance", 9),
                SubclassSpell("Banishment", 13),
                SubclassSpell("Locate Creature", 13),
                SubclassSpell("Scrying", 17),
                SubclassSpell("Teleportation Circle", 17),
            ],
            features=[
                SubclassFeature(
                    level=3,
                    title="Tools of the Trade",
                    description="""*Tool Proficiency.* You gain proficiency with Calligrapher's Supplies and Cartographer's Tools. If you already have one of these proficiencies, you gain proficiency with one other type of Artisan's Tools of your choice (or with two other types if you have both).

*Scroll Crafting.* When you scribe a Spell Scroll using the crafting rules in the Player's Handbook, the amount of time required to craft it is halved."""
                ),
                SubclassFeature(
                    level=3,
                    title="Cartographer Spells",
                    description="When you reach an Artificer level specified in the Cartographer Spells table, you thereafter always have the listed spells prepared.",
                    tables=[{
                        "title": "Cartographer Spells",
                        "columns": ["Artificer Level", "Spells"],
                        "rows": [
                            ["3", "Faerie Fire, Guiding Bolt, Healing Word"],
                            ["5", "Locate Object, Mind Spike"],
                            ["9", "Call Lightning, Clairvoyance"],
                            ["13", "Banishment, Locate Creature"],
                            ["17", "Scrying, Teleportation Circle"],
                        ]
                    }]
                ),
                SubclassFeature(
                    level=3,
                    title="Adventurer's Atlas",
                    description="""Whenever you finish a Long Rest while holding Cartographer's Tools, you can use that tool to create a set of magical maps by touching at least two creatures (one of whom can be yourself), up to a maximum number of creatures equal to 1 plus your Intelligence modifier (minimum of two creatures). Each target receives a magical map, which constantly updates to show the relative position of all the map holders but is illegible to all others. The maps last until you die or until you use this feature again, at which point any existing maps created by this feature immediately vanish.

While carrying the map, a target gains the following benefits.

*Awareness.* The target adds 1d4 to its Initiative rolls.

*Positioning.* The target knows the location of all other map holders that are on the same plane of existence as itself. When casting a spell or creating another effect that requires being able to see the effect's target, a map holder can target another map holder regardless of sight or cover, so long as the other map holder is still within the effect's range."""
                ),
                SubclassFeature(
                    level=3,
                    title="Mapping Magic",
                    description="""*Illuminated Cartography.* You can cast Faerie Fire without expending a spell slot, outlining the affected creatures as if in ink. You can do so a number of times equal to your Intelligence modifier (minimum of once), and you regain all expended uses when you finish a Long Rest.

*Portal Jump.* On your turn, you can spend an amount of movement equal to half your Speed (round down) to teleport to an unoccupied space you can see within 10 feet of yourself or within 5 feet of a creature that is within 30 feet of you and holding one of your Adventurer's Atlas maps. You can't use this benefit if your Speed is 0."""
                ),
                SubclassFeature(
                    level=5,
                    title="Guided Precision",
                    description="Once per turn, whenever you cast a spell from your Cartographer Spells list or hit a creature affected by your Faerie Fire with an attack roll, you can add your Intelligence modifier to one damage roll of the spell or attack. In addition, taking damage can't cause you to lose Concentration on Faerie Fire."
                ),
                SubclassFeature(
                    level=9,
                    title="Ingenious Movement",
                    description="When you use your Flash of Genius, you or a willing creature of your choice that you can see within 30 feet of yourself can teleport up to 30 feet to an unoccupied space you can see as part of that same Reaction."
                ),
                SubclassFeature(
                    level=15,
                    title="Superior Atlas",
                    description="""Your Adventurer's Atlas improves, gaining the following benefits.

*Safe Haven.* When a map holder would be reduced to 0 Hit Points but not killed outright, that creature can destroy its map. The creature's Hit Points instead change to a number equal to twice your Artificer level, and the creature is teleported to an unoccupied space within 5 feet of you or another map holder of its choice.

*Unerring Path.* If you are one of the map holders for your Adventurer's Atlas, you can cast Find the Path without expending a spell slot, without preparing the spell, and without needing spell components. Once you use this benefit, you can't use it again until you finish a Long Rest."""
                ),
            ]
        )
        
        return CharacterClassDefinition(
            name="Artificer",
            hit_die="d8",
            primary_ability="Intelligence",
            armor_proficiencies=["Light Armor", "Medium Armor", "Shields"],
            weapon_proficiencies=["Simple Weapons"],
            tool_proficiencies=["Thieves' Tools", "Tinker's Tools", "One type of Artisan's Tools of your choice"],
            saving_throw_proficiencies=["CON", "INT"],
            skill_proficiency_choices=2,
            skill_proficiency_options=["Arcana", "History", "Investigation", "Medicine", "Nature", "Perception", "Sleight of Hand"],
            starting_equipment_options=[
                StartingEquipmentOption(
                    option_letter="A",
                    items=["Studded Leather Armor", "Dagger", "Thieves' Tools", "Tinker's Tools", "Dungeoneer's Pack", "16 GP"]
                ),
                StartingEquipmentOption(
                    option_letter="B",
                    items=["150 GP"]
                ),
            ],
            starting_gold_alternative="150 GP",
            description="""Masters of invention, Artificers use ingenuity and magic to unlock extraordinary capabilities in objects. They see magic as a complex system waiting to be decoded and then harnessed in their spells and inventions.""",
            is_spellcaster=True,
            spellcasting_ability="INT",
            subclass_level=3,
            subclass_name="Artificer Specialist",
            subclasses=[alchemist, armorer, artillerist, battle_smith, cartographer],
            levels=levels,
            trackable_features=[tinkers_magic, flash_of_genius],
            class_table_columns=["Plans Known", "Magic Items", "Cantrips", "Prepared Spells", "1st", "2nd", "3rd", "4th", "5th"],
            is_custom=False,
            source="Eberron - Forge of the Artificer"
        )

    def _initialize_default_classes(self):
        """Initialize with basic D&D 5e class stubs."""
        default_classes = [
            self._create_barbarian_class(),
            CharacterClassDefinition(
                name="Bard",
                hit_die="d8",
                armor_proficiencies=["Light armor"],
                weapon_proficiencies=["Simple weapons", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
                tool_proficiencies=["Three musical instruments of your choice"],
                saving_throw_proficiencies=["DEX", "CHA"],
                skill_proficiency_choices=3,
                skill_proficiency_options=["Acrobatics", "Animal Handling", "Arcana", "Athletics", "Deception", "History", "Insight", "Intimidation", "Investigation", "Medicine", "Nature", "Perception", "Performance", "Persuasion", "Religion", "Sleight of Hand", "Stealth", "Survival"],
                is_spellcaster=True,
                spellcasting_ability="CHA",
                subclass_level=3,
                subclass_name="Bard College",
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Cleric",
                hit_die="d8",
                armor_proficiencies=["Light armor", "Medium armor", "Shields"],
                weapon_proficiencies=["Simple weapons"],
                saving_throw_proficiencies=["WIS", "CHA"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["History", "Insight", "Medicine", "Persuasion", "Religion"],
                is_spellcaster=True,
                spellcasting_ability="WIS",
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Druid",
                hit_die="d8",
                armor_proficiencies=["Light armor", "Medium armor", "Shields (druids will not wear armor or use shields made of metal)"],
                weapon_proficiencies=["Clubs", "Daggers", "Darts", "Javelins", "Maces", "Quarterstaffs", "Scimitars", "Sickles", "Slings", "Spears"],
                tool_proficiencies=["Herbalism kit"],
                saving_throw_proficiencies=["INT", "WIS"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["Arcana", "Animal Handling", "Insight", "Medicine", "Nature", "Perception", "Religion", "Survival"],
                is_spellcaster=True,
                spellcasting_ability="WIS",
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Fighter",
                hit_die="d10",
                armor_proficiencies=["All armor", "Shields"],
                weapon_proficiencies=["Simple weapons", "Martial weapons"],
                saving_throw_proficiencies=["STR", "CON"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["Acrobatics", "Animal Handling", "Athletics", "History", "Insight", "Intimidation", "Perception", "Survival"],
                is_spellcaster=False,
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Monk",
                hit_die="d8",
                armor_proficiencies=[],
                weapon_proficiencies=["Simple weapons", "Shortswords"],
                saving_throw_proficiencies=["STR", "DEX"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["Acrobatics", "Athletics", "History", "Insight", "Religion", "Stealth"],
                is_spellcaster=False,
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Paladin",
                hit_die="d10",
                armor_proficiencies=["All armor", "Shields"],
                weapon_proficiencies=["Simple weapons", "Martial weapons"],
                saving_throw_proficiencies=["WIS", "CHA"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["Athletics", "Insight", "Intimidation", "Medicine", "Persuasion", "Religion"],
                is_spellcaster=True,
                spellcasting_ability="CHA",
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Ranger",
                hit_die="d10",
                armor_proficiencies=["Light armor", "Medium armor", "Shields"],
                weapon_proficiencies=["Simple weapons", "Martial weapons"],
                saving_throw_proficiencies=["STR", "DEX"],
                skill_proficiency_choices=3,
                skill_proficiency_options=["Animal Handling", "Athletics", "Insight", "Investigation", "Nature", "Perception", "Stealth", "Survival"],
                is_spellcaster=True,
                spellcasting_ability="WIS",
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Rogue",
                hit_die="d8",
                armor_proficiencies=["Light armor"],
                weapon_proficiencies=["Simple weapons", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
                tool_proficiencies=["Thieves' tools"],
                saving_throw_proficiencies=["DEX", "INT"],
                skill_proficiency_choices=4,
                skill_proficiency_options=["Acrobatics", "Athletics", "Deception", "Insight", "Intimidation", "Investigation", "Perception", "Performance", "Persuasion", "Sleight of Hand", "Stealth"],
                is_spellcaster=False,
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Sorcerer",
                hit_die="d6",
                armor_proficiencies=[],
                weapon_proficiencies=["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
                saving_throw_proficiencies=["CON", "CHA"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["Arcana", "Deception", "Insight", "Intimidation", "Persuasion", "Religion"],
                is_spellcaster=True,
                spellcasting_ability="CHA",
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Warlock",
                hit_die="d8",
                armor_proficiencies=["Light armor"],
                weapon_proficiencies=["Simple weapons"],
                saving_throw_proficiencies=["WIS", "CHA"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["Arcana", "Deception", "History", "Intimidation", "Investigation", "Nature", "Religion"],
                is_spellcaster=True,
                spellcasting_ability="CHA",
                source="Player's Handbook"
            ),
            CharacterClassDefinition(
                name="Wizard",
                hit_die="d6",
                armor_proficiencies=[],
                weapon_proficiencies=["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
                saving_throw_proficiencies=["INT", "WIS"],
                skill_proficiency_choices=2,
                skill_proficiency_options=["Arcana", "History", "Insight", "Investigation", "Medicine", "Religion"],
                is_spellcaster=True,
                spellcasting_ability="INT",
                source="Player's Handbook"
            ),
            self._create_artificer_class(),  # Full Artificer class
        ]
        
        for cls in default_classes:
            self._classes[cls.name] = cls


# Singleton instance
_class_manager: Optional[ClassManager] = None

def get_class_manager() -> ClassManager:
    """Get the singleton ClassManager instance."""
    global _class_manager
    if _class_manager is None:
        _class_manager = ClassManager()
        _class_manager.load()
    return _class_manager
