"""
Monster data structure for D&D 5e Spellbook Application.

A Monster is a full creature stat block (Monster Manual style), as opposed to the
lightweight summon `StatBlock` in stat_block.py. It reuses the character sheet's
ability score / save / skill classes, so modifiers, saves and skill bonuses are
computed the same way - the only difference is that the proficiency bonus comes
from the monster's Challenge Rating instead of a character level.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from character_sheet import (
    AbilityScore, AbilityScores, SavingThrows, Skill, SkillProficiencies,
)
from stat_block import StatBlockFeature


# ===== Constants =====

SIZE_OPTIONS = ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]

CREATURE_TYPE_OPTIONS = [
    "Aberration", "Beast", "Celestial", "Construct", "Dragon", "Elemental",
    "Fey", "Fiend", "Giant", "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead",
]

# Movement types in the order a stat block lists them (walking speed first).
SPEED_TYPES = ["walk", "burrow", "climb", "fly", "swim"]

# Every valid challenge rating, in ascending order.
CR_OPTIONS = ["0", "1/8", "1/4", "1/2"] + [str(n) for n in range(1, 31)]

# XP awarded per challenge rating.
CR_XP: Dict[str, int] = {
    "0": 10, "1/8": 25, "1/4": 50, "1/2": 100, "1": 200, "2": 450, "3": 700,
    "4": 1100, "5": 1800, "6": 2300, "7": 2900, "8": 3900, "9": 5000,
    "10": 5900, "11": 7200, "12": 8400, "13": 10000, "14": 11500, "15": 13000,
    "16": 15000, "17": 18000, "18": 20000, "19": 22000, "20": 25000,
    "21": 33000, "22": 41000, "23": 50000, "24": 62000, "25": 75000,
    "26": 90000, "27": 105000, "28": 120000, "29": 135000, "30": 155000,
}

_FRACTION_CRS = {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}


def normalize_cr(value) -> str:
    """Coerce a CR (1/8, "1/8", 0.125, 5, "5", "CR 5") to its canonical string.

    Anything unrecognised falls back to "0".
    """
    if isinstance(value, str):
        text = value.strip().upper().removeprefix("CR").strip()
        if text in CR_XP:
            return text
        try:
            value = float(text)
        except ValueError:
            return "0"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number in _FRACTION_CRS:
        return _FRACTION_CRS[number]
    if number == int(number) and str(int(number)) in CR_XP:
        return str(int(number))
    return "0"


def cr_to_number(cr) -> float:
    """Numeric value of a CR ("1/2" -> 0.5)."""
    text = normalize_cr(cr)
    if "/" in text:
        top, bottom = text.split("/")
        return int(top) / int(bottom)
    return float(text)


def proficiency_bonus_for_cr(cr) -> int:
    """Proficiency bonus tied to CR: 0-4 -> +2, 5-8 -> +3, ... 29-30 -> +9."""
    number = cr_to_number(cr)
    if number <= 4:
        return 2
    return min(9, 2 + int(number - 1) // 4)


def sense_kind(sense: str) -> str:
    """The sense's name without its range: 'Darkvision 120 ft.' -> 'Darkvision'."""
    return re.sub(r"\s*\d.*$", "", sense).strip() or sense.strip()


def _signed(value: int) -> str:
    return f"+{value}" if value >= 0 else f"{value}"


def _feature_list(data) -> List[StatBlockFeature]:
    return [StatBlockFeature.from_dict(f) for f in (data or [])]


# ----- Converting summon-spell stat blocks (see Monster.from_stat_block) -----

_SPEED_RE = re.compile(r"\b(burrow|climb|fly|swim)\s+(\d+)\s*ft", re.I)
_PASSIVE_RE = re.compile(r"^passive\s+perception\s+(\d+)$", re.I)
_LOWER_START_RE = re.compile(r"(^|,\s+)([a-z])")


def _capitalize_items(text: str) -> str:
    """'acid (Water only), fire' -> 'Acid (Water only), Fire'."""
    return _LOWER_START_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def _split_text(text: str, sep: str) -> List[str]:
    """Split a free-text list, dropping empty entries and bare dashes."""
    return [part.strip() for part in (text or "").split(sep) if part.strip() not in ("", "—", "-")]


def _stored(data: dict, key: str, default):
    """Read `key`, or its JSON-string twin `<key>_json` (the shape of the seed data)."""
    if data.get(key) not in (None, ""):
        return data[key]
    raw = data.get(f"{key}_json")
    if raw:
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            pass
    return default


@dataclass
class Monster:
    """Represents a D&D 5e monster stat block."""
    # Identity
    name: str
    epithet: str = ""            # Short descriptive tagline shown under the name
    size: str = "Medium"
    creature_type: str = ""      # e.g. "Dragon"
    creature_subtype: str = ""   # e.g. "Chromatic" (shown as "Dragon (Chromatic)")
    alignment: str = "Unaligned"

    # Core stats
    ac: int = 10
    # Initiative is Dexterity plus proficiency: 0 = none, 1 = proficient, 2 = expertise
    initiative_proficiency: int = 0
    hp: int = 1                  # Average hit points
    hit_dice: str = ""           # e.g. "18d12 + 90"
    speeds: Dict[str, int] = field(default_factory=lambda: {"walk": 30})  # feet, keyed by SPEED_TYPES
    can_hover: bool = False      # Flying speed only

    # Text shown instead of the number/computed value when set. For values that
    # can't be one number - a summoned creature's "11 + the level of the spell",
    # "30 + 10 for each spell level above 3rd" - the numeric fields then hold a
    # best-effort figure used for sorting and filtering.
    ac_text: str = ""
    hp_text: str = ""
    speed_text: str = ""
    cr_text: str = ""
    skills_text: str = ""         # for skill lines the formula can't give ("+4 (+6 in snake form)")
    show_initiative: bool = True  # Summoned creatures list no initiative

    # Ability scores, save proficiencies, skill proficiencies (0/1/2, as on a character sheet)
    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    saving_throws: SavingThrows = field(default_factory=SavingThrows)
    skills: SkillProficiencies = field(default_factory=SkillProficiencies)

    # Defenses
    damage_vulnerabilities: List[str] = field(default_factory=list)
    damage_resistances: List[str] = field(default_factory=list)
    damage_immunities: List[str] = field(default_factory=list)
    condition_immunities: List[str] = field(default_factory=list)

    # Senses / languages. Passive Perception is derived from Perception, so
    # `senses` holds only entries like "Darkvision 120 ft.".
    senses: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    gear: List[str] = field(default_factory=list)   # e.g. "Chain Mail", "Longsword"

    # Challenge. Stored as a canonical string ("1/8", "15") so fractions survive
    # exactly; see cr_to_number(). `lair_xp` overrides the default lair XP (the
    # XP of the next CR up), which only applies to monsters with lair actions.
    challenge_rating: str = "0"
    lair_xp: Optional[int] = None

    # Features
    traits: List[StatBlockFeature] = field(default_factory=list)
    actions: List[StatBlockFeature] = field(default_factory=list)
    bonus_actions: List[StatBlockFeature] = field(default_factory=list)
    reactions: List[StatBlockFeature] = field(default_factory=list)
    legendary_actions: List[StatBlockFeature] = field(default_factory=list)
    legendary_action_uses: int = 3
    legendary_action_uses_in_lair: Optional[int] = None  # e.g. 4 for "3 (4 in Lair)"
    legendary_actions_intro: str = ""  # Overrides the standard "Legendary Action Uses" blurb
    lair_actions: List[StatBlockFeature] = field(default_factory=list)
    lair_actions_intro: str = ""

    # Footer / lore
    habitat: List[str] = field(default_factory=list)
    treasure: List[str] = field(default_factory=list)
    description: str = ""

    # Metadata
    source: str = ""
    is_official: bool = True   # True for official content, False for homebrew
    is_custom: bool = False    # True if user-created

    # A summoned creature: shown on its spell's page, and left out of the
    # Collections list unless "Display spell only summons" is on in Settings.
    spell_only: bool = False
    spell_name: str = ""       # The spell that summons it (blank = none)

    # ----- Derived values -----

    @property
    def proficiency_bonus(self) -> int:
        """Proficiency bonus, determined by Challenge Rating."""
        return proficiency_bonus_for_cr(self.challenge_rating)

    @property
    def xp(self) -> int:
        """XP awarded for defeating the monster."""
        return CR_XP[normalize_cr(self.challenge_rating)]

    def get_lair_xp(self) -> Optional[int]:
        """XP when fought in its lair: the stated `lair_xp`, else (for a monster with
        lair actions) the next CR's XP, else None."""
        if self.lair_xp is not None:
            return self.lair_xp
        if not self.lair_actions:
            return None
        index = CR_OPTIONS.index(normalize_cr(self.challenge_rating))
        if index + 1 >= len(CR_OPTIONS):
            return None
        return CR_XP[CR_OPTIONS[index + 1]]

    def get_modifier(self, ability: AbilityScore) -> int:
        return self.ability_scores.modifier(ability)

    def get_save_bonus(self, ability: AbilityScore) -> int:
        """Saving throw bonus: modifier, plus proficiency bonus if proficient."""
        bonus = self.get_modifier(ability)
        if self.saving_throws.is_proficient(ability):
            bonus += self.proficiency_bonus
        return bonus

    def get_skill_bonus(self, skill: Skill) -> int:
        """Skill bonus: modifier, plus proficiency bonus (x2 for expertise)."""
        return self.get_modifier(skill.ability) + self.proficiency_bonus * self.skills.get(skill)

    def get_initiative(self) -> int:
        """Initiative modifier."""
        level = max(0, min(2, self.initiative_proficiency))
        return self.get_modifier(AbilityScore.DEXTERITY) + self.proficiency_bonus * level

    def get_initiative_score(self) -> int:
        """Fixed initiative score (10 + modifier), shown in parentheses."""
        return 10 + self.get_initiative()

    def get_passive_perception(self) -> int:
        return 10 + self.get_skill_bonus(Skill.PERCEPTION)

    def has_lair(self) -> bool:
        return bool(self.lair_actions)

    def plain_description(self) -> str:
        """Description with [[link]] markup replaced by its visible text (for searching)."""
        from object_link_sweep import strip_links
        return strip_links(self.description)

    # ----- Display helpers -----

    def get_type_line(self) -> str:
        """e.g. 'Huge Dragon (Chromatic), Lawful Evil'."""
        kind = self.creature_type
        if self.creature_subtype:
            kind = f"{kind} ({self.creature_subtype})" if kind else self.creature_subtype
        line = " ".join(part for part in (self.size, kind) if part)
        if self.alignment:
            line += f", {self.alignment}"
        return line

    def display_ac(self) -> str:
        return self.ac_text or str(self.ac)

    def display_hp(self) -> str:
        """e.g. '207 (18d12 + 90)'."""
        if self.hp_text:
            return self.hp_text
        return f"{self.hp} ({self.hit_dice})" if self.hit_dice else str(self.hp)

    def display_initiative(self) -> str:
        """e.g. '+11 (21)'."""
        return f"{_signed(self.get_initiative())} ({self.get_initiative_score()})"

    def display_speed(self) -> str:
        """e.g. '40 ft., Fly 80 ft., Swim 40 ft.'."""
        if self.speed_text:
            return self.speed_text
        parts = []
        for kind in SPEED_TYPES:
            feet = self.speeds.get(kind)
            if feet is None or (feet == 0 and kind != "walk"):
                continue
            text = f"{feet} ft."
            if kind != "walk":
                text = f"{kind.capitalize()} {text}"
                if kind == "fly" and self.can_hover:
                    text += " (hover)"
            parts.append(text)
        return ", ".join(parts)

    def display_skills(self) -> str:
        """Proficient skills only, e.g. 'Deception +9, Perception +12'."""
        if self.skills_text:
            return self.skills_text
        parts = [
            f"{skill.display_name} {_signed(self.get_skill_bonus(skill))}"
            for skill in Skill if self.skills.get(skill)
        ]
        return ", ".join(parts)

    def display_senses(self) -> str:
        """Senses with the derived passive Perception appended."""
        return ", ".join(self.senses + [f"Passive Perception {self.get_passive_perception()}"])

    def display_languages(self) -> str:
        return ", ".join(self.languages) if self.languages else "None"

    def display_gear(self) -> str:
        return ", ".join(self.gear)

    def display_vulnerabilities(self) -> str:
        return ", ".join(self.damage_vulnerabilities)

    def display_resistances(self) -> str:
        return ", ".join(self.damage_resistances)

    def display_immunities(self) -> str:
        """Damage immunities then condition immunities, e.g. 'Poison; Poisoned'."""
        return "; ".join(part for part in (
            ", ".join(self.damage_immunities),
            ", ".join(self.condition_immunities),
        ) if part)

    def display_cr(self) -> str:
        """e.g. 'CR 15 (XP 13,000, or 15,000 in Lair; PB +5)'."""
        if self.cr_text:
            return f"CR {self.cr_text}"
        xp = f"XP {self.xp:,}"
        lair = self.get_lair_xp()
        if lair is not None:
            xp += f", or {lair:,} in Lair"
        return f"CR {normalize_cr(self.challenge_rating)} ({xp}; PB {_signed(self.proficiency_bonus)})"

    def display_legendary_uses(self) -> str:
        """e.g. '3 (4 in Lair)'."""
        uses = str(self.legendary_action_uses)
        if self.legendary_action_uses_in_lair is not None:
            uses += f" ({self.legendary_action_uses_in_lair} in Lair)"
        return uses

    def cr_label(self) -> str:
        """Short CR for lists: '1/4', '15', ... or, for a monster with CR override
        text, its first words ("None (XP 0; PB equals ...)" -> "None")."""
        if self.cr_text:
            return self.cr_text.split(" (")[0].strip()
        return normalize_cr(self.challenge_rating)

    def get_legendary_intro(self) -> str:
        """Text shown above the legendary actions (the standard blurb unless overridden)."""
        if self.legendary_actions_intro:
            return self.legendary_actions_intro
        who = f"the {self.creature_type.lower()}" if self.creature_type else "the creature"
        return (f"Legendary Action Uses: {self.display_legendary_uses()}. Immediately after "
                f"another creature's turn, {who} can expend a use to take one of the following "
                f"actions. {who.capitalize()} regains all expended uses at the start of each "
                f"of its turns.")

    def display_habitat(self) -> str:
        return ", ".join(self.habitat)

    def display_treasure(self) -> str:
        return ", ".join(self.treasure)

    # ----- Serialization -----

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "epithet": self.epithet,
            "size": self.size,
            "creature_type": self.creature_type,
            "creature_subtype": self.creature_subtype,
            "alignment": self.alignment,
            "ac": self.ac,
            "initiative_proficiency": self.initiative_proficiency,
            "hp": self.hp,
            "hit_dice": self.hit_dice,
            "speeds": dict(self.speeds),
            "can_hover": self.can_hover,
            "ac_text": self.ac_text,
            "hp_text": self.hp_text,
            "speed_text": self.speed_text,
            "cr_text": self.cr_text,
            "skills_text": self.skills_text,
            "show_initiative": self.show_initiative,
            "ability_scores": self.ability_scores.to_dict(),
            "saving_throws": self.saving_throws.to_dict(),
            "skills": self.skills.to_dict(),
            "damage_vulnerabilities": self.damage_vulnerabilities,
            "damage_resistances": self.damage_resistances,
            "damage_immunities": self.damage_immunities,
            "condition_immunities": self.condition_immunities,
            "senses": self.senses,
            "languages": self.languages,
            "gear": self.gear,
            "challenge_rating": normalize_cr(self.challenge_rating),
            "lair_xp": self.lair_xp,
            "traits": [f.to_dict() for f in self.traits],
            "actions": [f.to_dict() for f in self.actions],
            "bonus_actions": [f.to_dict() for f in self.bonus_actions],
            "reactions": [f.to_dict() for f in self.reactions],
            "legendary_actions": [f.to_dict() for f in self.legendary_actions],
            "legendary_action_uses": self.legendary_action_uses,
            "legendary_action_uses_in_lair": self.legendary_action_uses_in_lair,
            "legendary_actions_intro": self.legendary_actions_intro,
            "lair_actions": [f.to_dict() for f in self.lair_actions],
            "lair_actions_intro": self.lair_actions_intro,
            "habitat": self.habitat,
            "treasure": self.treasure,
            "description": self.description,
            "source": self.source,
            "is_official": self.is_official,
            "is_custom": self.is_custom,
            "spell_only": self.spell_only,
            "spell_name": self.spell_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Monster":
        """Create Monster from dictionary."""
        return cls(
            name=data.get("name", "Unknown"),
            epithet=data.get("epithet", data.get("epitaph", "")),   # "epitaph" in early exports
            size=data.get("size", "Medium") or "Medium",
            creature_type=data.get("creature_type", ""),
            creature_subtype=data.get("creature_subtype", ""),
            alignment=data.get("alignment", "Unaligned"),
            ac=int(data.get("ac", 10) or 10),
            initiative_proficiency=int(data.get("initiative_proficiency", 0) or 0),
            hp=int(data.get("hp", 1) or 1),
            hit_dice=data.get("hit_dice", ""),
            speeds={k: int(v) for k, v in (data["speeds"] if "speeds" in data else {"walk": 30}).items()},
            can_hover=data.get("can_hover", False),
            ac_text=data.get("ac_text", ""),
            hp_text=data.get("hp_text", ""),
            speed_text=data.get("speed_text", ""),
            cr_text=data.get("cr_text", ""),
            skills_text=data.get("skills_text", ""),
            show_initiative=data.get("show_initiative", True),
            ability_scores=AbilityScores.from_dict(data.get("ability_scores") or {}),
            saving_throws=SavingThrows.from_dict(data.get("saving_throws") or {}),
            skills=SkillProficiencies.from_dict(data.get("skills") or {}),
            damage_vulnerabilities=data.get("damage_vulnerabilities", []),
            damage_resistances=data.get("damage_resistances", []),
            damage_immunities=data.get("damage_immunities", []),
            condition_immunities=data.get("condition_immunities", []),
            senses=data.get("senses", []),
            languages=data.get("languages", []),
            gear=data.get("gear", []),
            challenge_rating=normalize_cr(data.get("challenge_rating", "0")),
            lair_xp=data.get("lair_xp"),
            traits=_feature_list(data.get("traits")),
            actions=_feature_list(data.get("actions")),
            bonus_actions=_feature_list(data.get("bonus_actions")),
            reactions=_feature_list(data.get("reactions")),
            legendary_actions=_feature_list(data.get("legendary_actions")),
            legendary_action_uses=int(data.get("legendary_action_uses", 3)),
            legendary_action_uses_in_lair=data.get("legendary_action_uses_in_lair"),
            legendary_actions_intro=data.get("legendary_actions_intro", ""),
            lair_actions=_feature_list(data.get("lair_actions")),
            lair_actions_intro=data.get("lair_actions_intro", ""),
            habitat=data.get("habitat", []),
            treasure=data.get("treasure", []),
            description=data.get("description", ""),
            source=data.get("source", ""),
            is_official=data.get("is_official", True),
            is_custom=data.get("is_custom", False),
            spell_only=data.get("spell_only", False),
            spell_name=data.get("spell_name", "") or "",
        )

    @classmethod
    def from_stat_block(cls, data: dict, source: str = "") -> "Monster":
        """Convert a summon-spell stat block (the old ``StatBlock`` dict shape, or a
        row of ``tools/stat_block_data``) into a spell-only Monster.

        Formulas ("11 + the level of the spell") are kept as display text and the
        numeric fields get the leading number. Passive Perception is dropped from
        the senses when it is what the ability scores already give.
        """
        abilities = _stored(data, "abilities", {})
        scores = AbilityScores(**{
            name: int((abilities.get(name) or {}).get("score", 10))
            for name in ("strength", "dexterity", "constitution",
                         "intelligence", "wisdom", "charisma")})

        senses = []
        for token in _split_text(data.get("senses", ""), ","):
            match = _PASSIVE_RE.match(token)
            if match and int(match.group(1)) == 10 + scores.modifier(AbilityScore.WISDOM):
                continue
            senses.append(_capitalize_items(token))

        speed = data.get("speed", "") or ""
        speeds = {}
        walk = re.match(r"\s*(\d+)\s*ft", speed)
        if walk:
            speeds["walk"] = int(walk.group(1))
        for kind, feet in _SPEED_RE.findall(speed):
            speeds.setdefault(kind.lower(), int(feet))

        def first_int(text: str, default: int) -> int:
            match = re.search(r"\d+", text or "")
            return int(match.group()) if match else default

        def item_list(key: str) -> List[str]:
            """Damage/condition names. A group with a qualifier - "Acid, Cold (matching
            dragon type)" - is one entry; a plain "Necrotic, Poison" is split up."""
            items = []
            for segment in _split_text(data.get(key, ""), ";"):
                items += [segment] if "(" in segment else _split_text(segment, ",")
            return [_capitalize_items(item) for item in items]

        return cls(
            name=data.get("name", "Unknown"),
            size=data.get("size", "Medium") or "Medium",
            creature_type=data.get("creature_type", ""),
            creature_subtype=data.get("creature_subtype", "") or "",
            alignment=data.get("alignment", "") or "Unaligned",
            ac=first_int(data.get("armor_class", ""), 10),
            hp=first_int(data.get("hit_points", ""), 1),
            speeds=speeds,
            can_hover=bool(re.search(r"\bfly\s+\d+\s*ft\.?\s*\(?hover\b", speed, re.I)),
            ac_text=data.get("armor_class", "") or "",
            hp_text=data.get("hit_points", "") or "",
            speed_text=speed,
            cr_text=(data.get("challenge_rating") or "").strip(),
            show_initiative=False,
            ability_scores=scores,
            damage_resistances=item_list("damage_resistances"),
            damage_immunities=item_list("damage_immunities"),
            condition_immunities=item_list("condition_immunities"),
            senses=senses,
            languages=_split_text(data.get("languages", ""), ","),
            traits=_feature_list(_stored(data, "traits", [])),
            actions=_feature_list(_stored(data, "actions", [])),
            bonus_actions=_feature_list(_stored(data, "bonus_actions", [])),
            reactions=_feature_list(_stored(data, "reactions", [])),
            legendary_actions=_feature_list(_stored(data, "legendary_actions", [])),
            source=source,
            spell_only=True,
            spell_name=data.get("spell_name", "") or "",
        )


class MonsterManager:
    """Manages the monster database using SQLite."""

    _instance: Optional["MonsterManager"] = None

    def __init__(self):
        self._db = None
        self._monsters_cache: Optional[List[Monster]] = None

    @classmethod
    def get_instance(cls) -> "MonsterManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def db(self):
        """Get database instance, initializing if needed."""
        if self._db is None:
            from database import SpellDatabase
            self._db = SpellDatabase()
            self._db.initialize()
        return self._db

    @property
    def monsters(self) -> List[Monster]:
        """Get all monsters, using cache if available."""
        if self._monsters_cache is None:
            self._reload_cache()
        return self._monsters_cache or []

    @property
    def browsable(self) -> List[Monster]:
        """What the Collections page lists: every monster except spell-only summons,
        unless "Display spell only summons" is on in Settings."""
        from settings import get_settings_manager
        show = getattr(get_settings_manager().settings, "show_spell_only_summons", False)
        return [m for m in self.monsters if show or not m.spell_only]

    def _reload_cache(self):
        """Reload monsters from database into cache."""
        self._monsters_cache = [Monster.from_dict(d) for d in self.db.get_all_monsters()]

    def _invalidate_cache(self):
        """Invalidate the cache to force reload on next access."""
        self._monsters_cache = None

    def load(self) -> bool:
        """Reload monsters from database (for compatibility)."""
        self._invalidate_cache()
        return True

    def save(self) -> bool:
        """No-op for database backend (saves happen immediately)."""
        return True

    def get_monster(self, name: str) -> Optional[Monster]:
        """Get a monster by name."""
        data = self.db.get_monster_by_name(name)
        return Monster.from_dict(data) if data else None

    def add_monster(self, monster: Monster) -> bool:
        """Add a new monster or update an existing one (by name)."""
        existing = self.db.get_monster_by_name(monster.name)
        if existing:
            self.db.update_monster(existing["id"], monster.to_dict())
        else:
            self.db.insert_monster(monster.to_dict())
        self._invalidate_cache()
        return True

    def update_monster(self, name: str, updated: Monster) -> bool:
        """Update an existing monster."""
        existing = self.db.get_monster_by_name(name)
        if not existing:
            return False
        result = self.db.update_monster(existing["id"], updated.to_dict())
        self._invalidate_cache()
        return result

    def delete_monster(self, name: str) -> bool:
        """Delete a monster by name. Only custom monsters can be removed."""
        existing = self.db.get_monster_by_name(name)
        if not existing:
            return False
        if not existing.get("is_custom"):
            return False  # Can't delete official monsters
        result = self.db.delete_monster(existing["id"])
        self._invalidate_cache()
        return result

    def get_monsters_for_spell(self, spell_name: str) -> List[Monster]:
        """The creatures a spell summons (read fresh from the database)."""
        return [Monster.from_dict(d) for d in self.db.get_monsters_for_spell_by_name(spell_name)]

    def replace_spell_monsters(self, spell_name: str, monsters: List[Monster]) -> int:
        """Give a spell exactly these summoned creatures (used by imports): its own
        custom creatures are replaced, official ones are kept. A creature whose name
        another monster already uses is renamed "Name (Spell)". Returns how many
        were saved."""
        for existing in self.db.get_monsters_for_spell_by_name(spell_name):
            if existing.get("is_custom"):
                self.db.delete_monster(existing["id"])
        saved = 0
        for monster in monsters:
            monster.spell_only, monster.spell_name = True, spell_name
            monster.is_official, monster.is_custom = False, True
            clash = self.db.get_monster_by_name(monster.name)
            if clash and clash["spell_name"].lower() != spell_name.lower():
                monster.name = f"{monster.name} ({spell_name})"
                clash = self.db.get_monster_by_name(monster.name)
            if clash:
                continue          # the spell already has an official creature of this name
            self.db.insert_monster(monster.to_dict())
            saved += 1
        self._invalidate_cache()
        return saved

    def search_monsters(self, query: str, creature_type: Optional[str] = None) -> List[Monster]:
        """Search monsters by name, type, description or feature text."""
        query_lower = query.lower()
        results = []
        for monster in self.browsable:
            if creature_type is not None and monster.creature_type != creature_type:
                continue
            if (query_lower in monster.name.lower()
                    or query_lower in monster.creature_type.lower()
                    or query_lower in monster.plain_description().lower()):
                results.append(monster)
        return results

    def get_monsters_by_type(self, creature_type: str) -> List[Monster]:
        return [m for m in self.browsable if m.creature_type == creature_type]

    # ----- Values available to filters and editors -----

    def get_all_values(self, attr: str) -> List[str]:
        """Sorted unique values of a list-of-strings field (e.g. 'habitat', 'languages')."""
        values = set()
        for monster in self.browsable:
            values.update(v for v in getattr(monster, attr) if v)
        return sorted(values, key=str.lower)

    def get_all_types(self) -> List[str]:
        """All creature types, the standard ones plus any custom ones in use."""
        types = set(CREATURE_TYPE_OPTIONS)
        types.update(m.creature_type for m in self.browsable if m.creature_type)
        return sorted(types)

    def get_all_subtypes(self) -> List[str]:
        return sorted({m.creature_subtype for m in self.browsable if m.creature_subtype}, key=str.lower)

    def get_all_sizes(self) -> List[str]:
        """All sizes, smallest first (custom sizes go last)."""
        extra = sorted({m.size for m in self.browsable if m.size and m.size not in SIZE_OPTIONS})
        return SIZE_OPTIONS + extra

    def get_all_alignments(self) -> List[str]:
        return sorted({m.alignment for m in self.browsable if m.alignment}, key=str.lower)

    def get_all_habitats(self) -> List[str]:
        return self.get_all_values("habitat")

    def get_all_treasures(self) -> List[str]:
        return self.get_all_values("treasure")

    def get_all_languages(self) -> List[str]:
        return self.get_all_values("languages")

    def get_all_sense_kinds(self) -> List[str]:
        """Sense names without ranges ('Darkvision', 'Blindsight', ...)."""
        return sorted({sense_kind(s) for m in self.browsable for s in m.senses if s}, key=str.lower)

    def get_all_sources(self) -> List[str]:
        return sorted({m.source for m in self.browsable if m.source})

    def get_unofficial_sources(self) -> List[str]:
        """Get sources that have unofficial (non-official/custom) monsters."""
        return sorted({m.source for m in self.get_unofficial_monsters() if m.source})

    def get_unofficial_monsters(self) -> List[Monster]:
        """The user's own monsters, for export. Spell-only summons are left out:
        they travel inside their spell's record instead."""
        return [m for m in self.monsters
                if (not m.is_official or m.is_custom) and not m.spell_only]

    def export_to_json(self, file_path: str, monsters: Optional[List[Monster]] = None) -> int:
        """Export monsters to a JSON file."""
        if monsters is None:
            monsters = self.get_unofficial_monsters()
        try:
            from atomic_io import atomic_write_json
            atomic_write_json(file_path, {"monsters": [m.to_dict() for m in monsters]})
            return len(monsters)
        except Exception as e:
            print(f"Error exporting monsters to JSON: {e}")
            return 0

    def import_from_json(self, file_path: str) -> int:
        """Import monsters from a JSON file; returns how many were added or updated.

        Goes through content_io, so an entry whose name belongs to official content
        is skipped instead of overwritten.
        """
        import content_io

        try:
            report = content_io.import_file(file_path, kinds=["monsters"], link_mentions=False)
        except Exception as e:
            print(f"Error importing monsters from JSON: {e}")
            return 0
        return report.added["monsters"] + report.updated["monsters"]


def get_monster_manager() -> MonsterManager:
    """Get the singleton MonsterManager instance."""
    return MonsterManager.get_instance()
