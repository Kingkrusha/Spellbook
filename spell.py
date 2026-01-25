"""
Spell data model and enums for D&D Spellbook Application.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict


class CharacterClass(Enum):
    """D&D character classes that can cast spells."""
    ARTIFICER = "Artificer"
    BARBARIAN = "Barbarian"
    BARD = "Bard"
    CLERIC = "Cleric"
    CUSTOM = "Custom"
    DRUID = "Druid"
    FIGHTER = "Fighter"
    MONK = "Monk"
    PALADIN = "Paladin"
    RANGER = "Ranger"
    ROGUE = "Rogue"
    SORCERER = "Sorcerer"
    WARLOCK = "Warlock"
    WIZARD = "Wizard"
    
    @classmethod
    def from_string(cls, value: str) -> "CharacterClass":
        """Convert a string to CharacterClass enum."""
        value = value.strip().upper()
        for member in cls:
            if member.name == value or member.value.upper() == value:
                return member
        raise ValueError(f"Unknown character class: {value}")
    
    @classmethod
    def all_classes(cls) -> List["CharacterClass"]:
        """Return all character classes in order."""
        return list(cls)
    
    @classmethod
    def spellcasting_classes(cls) -> List["CharacterClass"]:
        """Return only classes that can cast spells."""
        non_casters = {cls.BARBARIAN, cls.FIGHTER, cls.MONK, cls.ROGUE}
        return [c for c in cls if c not in non_casters]
    
    def is_spellcaster(self) -> bool:
        """Check if this class can cast spells."""
        non_casters = {CharacterClass.BARBARIAN, CharacterClass.FIGHTER, 
                       CharacterClass.MONK, CharacterClass.ROGUE}
        return self not in non_casters


class TagFilterMode(Enum):
    """Mode for filtering by tags."""
    HAS_ALL = "has_all"       # Spell must have ALL selected tags
    HAS_ANY = "has_any"       # Spell must have at least ONE selected tag
    HAS_NONE = "has_none"     # Spell must NOT have any selected tags


class SourceFilterMode(Enum):
    """Mode for filtering by sources."""
    INCLUDE = "include"       # Show spells from selected sources
    EXCLUDE = "exclude"       # Hide spells from selected sources


@dataclass
class AdvancedFilters:
    """Container for advanced filter options."""
    ritual_filter: Optional[bool] = None  # None=any, True=only ritual, False=no ritual
    concentration_filter: Optional[bool] = None  # None=any, True=only conc, False=no conc
    min_range: int = 0  # Minimum range value (uses range encoding: 0=Self, 3=Touch, etc.)
    has_verbal: Optional[bool] = None  # None=any, True=must have V, False=must not have V
    has_somatic: Optional[bool] = None  # None=any, True=must have S, False=must not have S
    has_material: Optional[bool] = None  # None=any, True=must have M, False=must not have M
    costly_component: Optional[bool] = None  # None=any, True=has gp cost, False=no gp cost
    casting_time_filter: str = ""  # Empty=any, else must contain this string
    duration_filter: str = ""  # Empty=any, else must contain this string
    source_filter: List[str] = field(default_factory=list)  # Empty=any, else filter by sources
    source_filter_mode: SourceFilterMode = SourceFilterMode.INCLUDE  # How to apply source filter
    tags_filter: List[str] = field(default_factory=list)  # Empty=any, else filter by tags
    tags_filter_mode: TagFilterMode = TagFilterMode.HAS_ALL  # How to apply tag filter


def range_value_to_feet(range_value: int) -> int:
    """Convert a range_value to comparable feet for filtering.
    
    Range encoding:
    - 0 = Self (0 feet)
    - 1 = Sight (effectively infinite)
    - 2 = Special (treated as infinite for filtering)
    - 3 = Touch (5 feet)
    - Positive values = feet
    - Negative values = miles (multiply by 5280)
    
    Returns a comparable distance in feet.
    """
    if range_value == 0:  # Self
        return 0
    elif range_value == 3:  # Touch
        return 5
    elif range_value < 0:  # Miles
        return abs(range_value) * 5280
    elif range_value == 1 or range_value == 2:  # Sight or Special
        return 999999  # Very large - effectively unlimited
    else:  # Regular feet
        return range_value


# Protected tags that users cannot add/remove manually
PROTECTED_TAGS = frozenset({"Official", "Unofficial"})
# Lowercase versions for case-insensitive comparison
_PROTECTED_TAGS_LOWER = frozenset(t.lower() for t in PROTECTED_TAGS)


def is_protected_tag(tag: str) -> bool:
    """Check if a tag is a protected tag (case-insensitive)."""
    return tag.lower() in _PROTECTED_TAGS_LOWER


@dataclass
class Spell:
    """Represents a D&D spell with all its properties."""
    name: str
    level: int  # 0-9, 0 = cantrip
    casting_time: str
    ritual: bool
    range_value: int  # 0 = Self, 1 = Sight, else in ft (increments of 5)
    components: str  # V, S, M combinations
    duration: str
    concentration: bool
    classes: List[CharacterClass] = field(default_factory=list)
    description: str = ""
    source: str = ""
    tags: List[str] = field(default_factory=list)
    is_modified: bool = False  # True if an official spell was edited (non-tag/source fields)
    original_name: str = ""  # For official spells: the original name for restoration matching
    
    @property
    def is_official(self) -> bool:
        """Check if this spell has the Official tag."""
        return "Official" in self.tags
    
    @property
    def display_name(self) -> str:
        """Get the display name with asterisk for modified official spells."""
        if self.is_official and self.is_modified:
            return f"{self.name}*"
        return self.name
    
    # Component helper properties
    @property
    def has_verbal(self) -> bool:
        """Check if spell has verbal component."""
        return "V" in self.components.upper()
    
    @property
    def has_somatic(self) -> bool:
        """Check if spell has somatic component."""
        return "S" in self.components.upper()
    
    @property
    def has_material(self) -> bool:
        """Check if spell has material component."""
        return "M" in self.components.upper()
    
    @property
    def has_costly_component(self) -> bool:
        """Check if spell has a material component with gold/silver/copper/platinum/electrum cost."""
        # Look for patterns like "100 gp", "5+ GP", "1 sp", "worth 50+ GP", "500 pp", etc.
        components_lower = self.components.lower()
        # Pattern matches: number followed by optional +, optional whitespace, then currency
        # Covers: "5+ gp", "50+ gp", "100 gp", "1 sp", "1,000 gp", "500 pp", "10 ep"
        currency_pattern = r'\d+[,\d]*\+?\s*(?:gp|sp|cp|pp|ep|gold\s*pieces?|silver\s*pieces?|copper\s*pieces?|platinum\s*pieces?|electrum\s*pieces?)'
        # Also match "worth X" patterns like "worth at least 1 sp"
        worth_pattern = r'worth\s+(?:at\s+least\s+)?\d+[,\d]*\+?\s*(?:gp|sp|cp|pp|ep)'
        return bool(re.search(currency_pattern, components_lower) or re.search(worth_pattern, components_lower))
    
    def display_level(self) -> str:
        """Return formatted level string."""
        if self.level == 0:
            return "Cantrip"
        return f"Level {self.level} Spell"
    
    def display_casting_time(self) -> str:
        """Return formatted casting time, including Ritual if applicable."""
        if self.ritual:
            return f"{self.casting_time}, Ritual"
        return self.casting_time
    
    def display_range(self) -> str:
        """Return formatted range string.
        
        Special values:
        - 0 = Self
        - 1 = Sight
        - 2 = Special
        - 3 = Touch
        - Positive values = feet
        - Negative values = miles (absolute value)
        """
        if self.range_value == 0:
            return "Self"
        elif self.range_value == 1:
            return "Sight"
        elif self.range_value == 2:
            return "Special"
        elif self.range_value == 3:
            return "Touch"
        elif self.range_value < 0:
            # Negative values represent miles
            miles = abs(self.range_value)
            if miles == 1:
                return "1 mile"
            else:
                return f"{miles} miles"
        else:
            return f"{self.range_value} ft"
    
    @property
    def range_as_feet(self) -> int:
        """Convert range_value to comparable feet for filtering.
        
        Returns a comparable distance in feet for filtering purposes:
        - Self (0) = 0 feet
        - Touch (3) = 5 feet
        - Feet values = value
        - Miles (negative) = abs(value) * 5280 feet
        - Sight (1) = very large number (effectively infinite)
        - Special (2) = very large number (assume unlimited for filtering)
        """
        if self.range_value == 0:  # Self
            return 0
        elif self.range_value == 3:  # Touch
            return 5
        elif self.range_value < 0:  # Miles
            return abs(self.range_value) * 5280
        elif self.range_value == 1 or self.range_value == 2:  # Sight or Special
            return 999999  # Very large - effectively unlimited
        else:  # Regular feet
            return self.range_value
    
    def display_duration(self) -> str:
        """Return formatted duration, including Concentration if applicable."""
        if self.concentration:
            return f"Concentration, up to {self.duration}"
        return self.duration
    
    def display_classes(self) -> str:
        """Return comma-separated list of class names, sorted alphabetically and capitalized."""
        sorted_classes = sorted(self.classes, key=lambda c: c.value.lower())
        return ", ".join(c.value.capitalize() for c in sorted_classes)
    
    def display_description(self) -> str:
        """Return description with paragraph breaks converted to newlines."""
        return self.description.replace("\\", "\n\n")
    
    def display_tags(self) -> str:
        """Return comma-separated list of tags, sorted alphabetically and capitalized."""
        sorted_tags = sorted(self.tags, key=lambda t: t.lower())
        return ", ".join(tag.capitalize() for tag in sorted_tags)
    
    def list_display_name(self) -> str:
        """Return name with (R) and (C) indicators for list view."""
        indicators = []
        if self.ritual:
            indicators.append("R")
        if self.concentration:
            indicators.append("C")
        
        if indicators:
            return f"{self.name} ({')('.join(indicators)})"
        return self.name
    
    def to_file_line(self) -> str:
        """Serialize spell to pipe-delimited file format."""
        classes_str = ",".join(c.value for c in self.classes)
        tags_str = ",".join(self.tags)
        
        return "|".join([
            self.name,
            str(self.level),
            self.casting_time,
            str(self.ritual).lower(),
            str(self.range_value),
            self.components,
            self.duration,
            str(self.concentration).lower(),
            classes_str,
            self.description,
            self.source,
            tags_str
        ])
    
    @classmethod
    def from_file_line(cls, line: str) -> "Spell":
        """Deserialize spell from pipe-delimited file format."""
        parts = line.strip().split("|")
        
        if len(parts) < 12:
            # Pad with empty strings if fields are missing
            parts.extend([""] * (12 - len(parts)))
        
        name = parts[0]
        level = int(parts[1]) if parts[1] else 0
        casting_time = parts[2]
        ritual = parts[3].lower() == "true"
        range_value = int(parts[4]) if parts[4] else 0
        components = parts[5]
        duration = parts[6]
        concentration = parts[7].lower() == "true"
        
        # Parse classes
        classes = []
        if parts[8]:
            for class_name in parts[8].split(","):
                try:
                    classes.append(CharacterClass.from_string(class_name))
                except ValueError:
                    pass  # Skip unknown classes
        
        description = parts[9]
        source = parts[10]
        
        # Parse tags
        tags = []
        if parts[11]:
            tags = [t.strip() for t in parts[11].split(",") if t.strip()]
        
        return cls(
            name=name,
            level=level,
            casting_time=casting_time,
            ritual=ritual,
            range_value=range_value,
            components=components,
            duration=duration,
            concentration=concentration,
            classes=classes,
            description=description,
            source=source,
            tags=tags
        )
    
    def matches_filter(self, search_text: str = "", level_filter: int = -1, 
                       class_filter: Optional[CharacterClass] = None,
                       advanced: Optional[AdvancedFilters] = None) -> bool:
        """Check if spell matches the given filter criteria."""
        # Search text filter (case-insensitive)
        if search_text:
            search_lower = search_text.lower()
            if (search_lower not in self.name.lower() and 
                search_lower not in self.description.lower() and
                search_lower not in self.display_tags().lower()):
                return False
        
        # Level filter (-1 means all levels)
        if level_filter >= 0 and self.level != level_filter:
            return False
        
        # Class filter (None means all classes)
        if class_filter is not None and class_filter not in self.classes:
            return False
        
        # Advanced filters
        if advanced:
            # Ritual filter
            if advanced.ritual_filter is not None:
                if advanced.ritual_filter and not self.ritual:
                    return False
                if not advanced.ritual_filter and self.ritual:
                    return False
            
            # Concentration filter
            if advanced.concentration_filter is not None:
                if advanced.concentration_filter and not self.concentration:
                    return False
                if not advanced.concentration_filter and self.concentration:
                    return False
            
            # Minimum range filter - compare using feet equivalents
            # min_range of 0 (Self) means no filtering
            if advanced.min_range != 0:
                min_feet = range_value_to_feet(advanced.min_range)
                spell_feet = self.range_as_feet
                if spell_feet < min_feet:
                    return False
            
            # Component filters
            if advanced.has_verbal is not None:
                if advanced.has_verbal != self.has_verbal:
                    return False
            
            if advanced.has_somatic is not None:
                if advanced.has_somatic != self.has_somatic:
                    return False
            
            if advanced.has_material is not None:
                if advanced.has_material != self.has_material:
                    return False
            
            # Costly component filter
            if advanced.costly_component is not None:
                if advanced.costly_component != self.has_costly_component:
                    return False
            
            # Casting time filter (substring match)
            if advanced.casting_time_filter:
                if advanced.casting_time_filter.lower() not in self.casting_time.lower():
                    return False
            
            # Duration filter (substring match)
            if advanced.duration_filter:
                if advanced.duration_filter.lower() not in self.duration.lower():
                    return False
            
            # Source filter (multi-select with include/exclude mode)
            if advanced.source_filter:
                source_lower = self.source.lower()
                sources_lower = [s.lower() for s in advanced.source_filter]
                source_matches = any(s in source_lower for s in sources_lower)
                
                if advanced.source_filter_mode == SourceFilterMode.INCLUDE:
                    # Must match one of the selected sources
                    if not source_matches:
                        return False
                else:  # EXCLUDE mode
                    # Must NOT match any of the selected sources
                    if source_matches:
                        return False
            
            # Tags filter (must have ALL selected tags)
            if advanced.tags_filter:
                spell_tags_lower = [t.lower() for t in self.tags]
                for required_tag in advanced.tags_filter:
                    if required_tag.lower() not in spell_tags_lower:
                        return False
        
        return True


class SpellComparison:
    """Utility class for comparing two spells."""
    
    # Casting time rankings (lower is better)
    CASTING_TIME_RANKS = {
        "bonus action": 1,
        "reaction": 1,
        "action": 2,
        "1 minute": 3,
        "10 minutes": 4,
        "1 hour": 5,
        "8 hours": 6,
        "12 hours": 7,
        "24 hours": 8,
    }
    
    @staticmethod
    def get_casting_time_rank(casting_time: str) -> int:
        """Get numerical rank for casting time (lower is better)."""
        ct_lower = casting_time.lower().strip()
        for key, rank in SpellComparison.CASTING_TIME_RANKS.items():
            if key in ct_lower:
                return rank
        return 10  # Unknown casting times rank worst
    
    @staticmethod
    def compare_casting_time(spell1: "Spell", spell2: "Spell") -> int:
        """Compare casting times. Returns -1 if spell1 better, 1 if spell2 better, 0 if equal."""
        rank1 = SpellComparison.get_casting_time_rank(spell1.casting_time)
        rank2 = SpellComparison.get_casting_time_rank(spell2.casting_time)
        if rank1 < rank2:
            return -1
        elif rank1 > rank2:
            return 1
        return 0
    
    @staticmethod
    def count_components(spell: "Spell") -> int:
        """Count number of component types (V, S, M)."""
        count = 0
        if spell.has_verbal:
            count += 1
        if spell.has_somatic:
            count += 1
        if spell.has_material:
            count += 1
        return count
    
    @staticmethod
    def compare_components(spell1: "Spell", spell2: "Spell") -> int:
        """Compare component counts. Returns -1 if spell1 better (fewer), 1 if spell2 better, 0 if equal."""
        count1 = SpellComparison.count_components(spell1)
        count2 = SpellComparison.count_components(spell2)
        if count1 < count2:
            return -1
        elif count1 > count2:
            return 1
        return 0
    
    @staticmethod
    def extract_component_cost(components: str) -> float:
        """Extract GP cost from components string. Returns 0 if no cost."""
        components_lower = components.lower()
        
        # Look for patterns like "100 gp", "5+ gp", "1,000 gp"
        gp_pattern = r'(\d+[,\d]*)\+?\s*(?:gp|gold)'
        sp_pattern = r'(\d+[,\d]*)\+?\s*(?:sp|silver)'
        cp_pattern = r'(\d+[,\d]*)\+?\s*(?:cp|copper)'
        
        total_gp = 0.0
        
        # Find GP
        gp_match = re.search(gp_pattern, components_lower)
        if gp_match:
            total_gp += float(gp_match.group(1).replace(",", ""))
        
        # Find SP (convert to GP)
        sp_match = re.search(sp_pattern, components_lower)
        if sp_match:
            total_gp += float(sp_match.group(1).replace(",", "")) / 10
        
        # Find CP (convert to GP)
        cp_match = re.search(cp_pattern, components_lower)
        if cp_match:
            total_gp += float(cp_match.group(1).replace(",", "")) / 100
        
        return total_gp
    
    @staticmethod
    def compare_component_cost(spell1: "Spell", spell2: "Spell") -> int:
        """Compare component costs. Returns -1 if spell1 better (cheaper), 1 if spell2 better, 0 if equal."""
        cost1 = SpellComparison.extract_component_cost(spell1.components)
        cost2 = SpellComparison.extract_component_cost(spell2.components)
        if cost1 < cost2:
            return -1
        elif cost1 > cost2:
            return 1
        return 0
    
    @staticmethod
    def _strip_higher_level_sections(description: str) -> str:
        """
        Remove sections that describe higher-level casting, circle spells, or cantrip upgrades.
        These sections should not be included when comparing base damage.
        """
        # Split by paragraph break (the app uses \\ for paragraph breaks)
        paragraphs = description.split("\\")
        
        # Filter out paragraphs that start with upgrade-related phrases
        filtered = []
        skip_phrases = [
            "at higher levels",
            "when you cast this spell using",
            "this spell's damage increases",
            "the spell's damage increases",
            "circle spell",
            "cantrip upgrade",
            "when you reach"  # Common cantrip upgrade phrase
        ]
        
        for para in paragraphs:
            para_lower = para.strip().lower()
            should_skip = any(para_lower.startswith(phrase) for phrase in skip_phrases)
            if not should_skip:
                filtered.append(para)
        
        return "\\".join(filtered)
    
    @staticmethod
    def extract_damage_dice(description: str, ignore_higher_levels: bool = True) -> List[Tuple[int, int]]:
        """Extract all damage dice from description. Returns list of (count, sides) tuples.
        
        Args:
            description: The spell description text
            ignore_higher_levels: If True, excludes dice from "at higher levels" and similar sections
        """
        if ignore_higher_levels:
            description = SpellComparison._strip_higher_level_sections(description)
        
        dice_pattern = r'(\d+)d(\d+)'
        matches = re.findall(dice_pattern, description.lower())
        return [(int(count), int(sides)) for count, sides in matches]
    
    @staticmethod
    def calculate_max_damage(dice: List[Tuple[int, int]]) -> Tuple[int, int]:
        """Calculate max damage and total dice count from dice list."""
        if not dice:
            return (0, 0)
        total_max = sum(count * sides for count, sides in dice)
        total_dice = sum(count for count, _ in dice)
        return (total_max, total_dice)
    
    @staticmethod
    def compare_damage(spell1: "Spell", spell2: "Spell") -> int:
        """Compare damage. Returns -1 if spell1 better, 1 if spell2 better, 0 if equal.
        Only compares if both spells have the 'Damage' tag."""
        # Check if both spells have the Damage tag
        spell1_tags_lower = [t.lower() for t in spell1.tags]
        spell2_tags_lower = [t.lower() for t in spell2.tags]
        
        if "damage" not in spell1_tags_lower or "damage" not in spell2_tags_lower:
            return 0  # Don't compare damage if both don't have the Damage tag
        
        dice1 = SpellComparison.extract_damage_dice(spell1.description)
        dice2 = SpellComparison.extract_damage_dice(spell2.description)
        
        max1, count1 = SpellComparison.calculate_max_damage(dice1)
        max2, count2 = SpellComparison.calculate_max_damage(dice2)
        
        # Compare max damage first
        if max1 > max2:
            return -1
        elif max1 < max2:
            return 1
        
        # If equal max damage, compare dice count (more dice is better)
        if count1 > count2:
            return -1
        elif count1 < count2:
            return 1
        
        return 0
    
    # Duration rankings in seconds (higher is better)
    @staticmethod
    def parse_duration_seconds(duration: str) -> int:
        """Parse duration string to seconds for comparison."""
        dur_lower = duration.lower().strip()
        
        if "instantaneous" in dur_lower:
            return 0
        if "until dispelled" in dur_lower:
            return 999999999  # Very long
        
        # Extract numbers and units
        patterns = [
            (r'(\d+)\s*round', 6),  # 1 round = 6 seconds
            (r'(\d+)\s*minute', 60),
            (r'(\d+)\s*hour', 3600),
            (r'(\d+)\s*day', 86400),
        ]
        
        for pattern, multiplier in patterns:
            match = re.search(pattern, dur_lower)
            if match:
                return int(match.group(1)) * multiplier
        
        return 0
    
    @staticmethod
    def compare_duration(spell1: "Spell", spell2: "Spell") -> int:
        """Compare durations. Returns -1 if spell1 better (longer), 1 if spell2 better, 0 if equal."""
        dur1 = SpellComparison.parse_duration_seconds(spell1.duration)
        dur2 = SpellComparison.parse_duration_seconds(spell2.duration)
        
        if dur1 > dur2:
            return -1
        elif dur1 < dur2:
            return 1
        return 0
    
    @staticmethod
    def get_range_rank(range_value: int) -> int:
        """Get numerical rank for range (higher is better).
        Self (0) is worst, Touch (3) is second worst, Sight (1) is best, others by distance."""
        if range_value == 0:  # Self
            return 0
        elif range_value == 3:  # Touch
            return 1
        elif range_value == 1:  # Sight
            return 999999  # Best
        else:
            return range_value  # Numeric range in feet
    
    @staticmethod
    def compare_range(spell1: "Spell", spell2: "Spell") -> int:
        """Compare ranges. Returns -1 if spell1 better (longer), 1 if spell2 better, 0 if equal."""
        rank1 = SpellComparison.get_range_rank(spell1.range_value)
        rank2 = SpellComparison.get_range_rank(spell2.range_value)
        
        if rank1 > rank2:
            return -1  # spell1 has better range
        elif rank1 < rank2:
            return 1   # spell2 has better range
        return 0
    
    @staticmethod
    def compare_all(spell1: "Spell", spell2: "Spell") -> Dict[str, int]:
        """
        Compare all attributes between two spells.
        Returns dict with comparison results:
        - 'casting_time': -1/0/1
        - 'components': -1/0/1
        - 'component_cost': -1/0/1
        - 'damage': -1/0/1
        - 'duration': -1/0/1
        - 'range': -1/0/1
        - 'concentration': -1/0/1 (not having it is better)
        - 'ritual': -1/0/1 (having it is better)
        
        -1 means spell1 is better, 1 means spell2 is better, 0 means equal
        """
        results = {
            'casting_time': SpellComparison.compare_casting_time(spell1, spell2),
            'components': SpellComparison.compare_components(spell1, spell2),
            'component_cost': SpellComparison.compare_component_cost(spell1, spell2),
            'damage': SpellComparison.compare_damage(spell1, spell2),
            'duration': SpellComparison.compare_duration(spell1, spell2),
            'range': SpellComparison.compare_range(spell1, spell2),
        }
        
        # Concentration: not having it is better
        if spell1.concentration and not spell2.concentration:
            results['concentration'] = 1  # spell2 better
        elif not spell1.concentration and spell2.concentration:
            results['concentration'] = -1  # spell1 better
        else:
            results['concentration'] = 0  # both same
        
        # Ritual: having it is better
        if spell1.ritual and not spell2.ritual:
            results['ritual'] = -1  # spell1 better
        elif not spell1.ritual and spell2.ritual:
            results['ritual'] = 1  # spell2 better
        else:
            results['ritual'] = 0  # both same
        
        return results
    
    @staticmethod
    def _get_excluded_ranges(description: str) -> List[Tuple[int, int]]:
        """
        Get character ranges that should be excluded from damage dice highlighting.
        These are sections that describe higher-level casting, etc.
        """
        excluded = []
        
        # Find paragraph breaks (\\) and check what follows
        skip_phrases = [
            "at higher levels",
            "when you cast this spell using",
            "this spell's damage increases",
            "the spell's damage increases",
            "circle spell",
            "cantrip upgrade",
            "when you reach"
        ]
        
        # Find all paragraph positions
        parts = description.split("\\")
        pos = 0
        for i, part in enumerate(parts):
            part_lower = part.strip().lower()
            should_exclude = any(part_lower.startswith(phrase) for phrase in skip_phrases)
            
            if should_exclude:
                # Exclude this entire paragraph
                start = pos
                end = pos + len(part)
                excluded.append((start, end))
            
            pos += len(part)
            if i < len(parts) - 1:
                pos += 1  # Account for the \\ separator (stored as single \)
        
        return excluded
    
    @staticmethod
    def get_damage_dice_positions(description: str, exclude_higher_levels: bool = True) -> List[Tuple[int, int, str]]:
        """Find positions of damage dice in description for highlighting.
        Returns list of (start, end, dice_string) tuples.
        
        Args:
            description: The spell description text
            exclude_higher_levels: If True, excludes dice from "at higher levels" and similar sections
        """
        dice_pattern = r'\d+d\d+'
        positions = []
        
        if exclude_higher_levels:
            excluded_ranges = SpellComparison._get_excluded_ranges(description)
        else:
            excluded_ranges = []
        
        for match in re.finditer(dice_pattern, description, re.IGNORECASE):
            start, end = match.start(), match.end()
            
            # Check if this position is in an excluded range
            in_excluded = any(
                excl_start <= start < excl_end
                for excl_start, excl_end in excluded_ranges
            )
            
            if not in_excluded:
                positions.append((start, end, match.group()))
        
        return positions
