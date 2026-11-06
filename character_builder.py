"""
The guided character builder's rules (no UI): what each step offers, what the choices add up to, and making the
character and its sheet at the end.

A ``Draft`` holds every choice the user has made so far. The builder page (``ui/character_builder_view.py``) shows
one step at a time and only edits the draft; nothing is saved until ``create_character`` makes the character and
its sheet in one go. Everything is read from the collections (classes, subclasses, species, backgrounds, feats,
spells and equipment), so homebrew content shows up in the builder like the official content does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

ABILITIES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]
ABILITY_LABELS = {a: a.capitalize() for a in ABILITIES}
ABILITY_SHORT = {"strength": "STR", "dexterity": "DEX", "constitution": "CON",
                 "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA"}

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
POINT_BUY_BUDGET = 27
POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
SCORE_METHODS = ("standard", "point_buy", "manual")

ASI = "Ability Score Improvement"

# The steps, in order: (key, title). Some are skipped when they don't apply (see ``steps_for``).
STEPS = [
    ("start", "Name and level"),
    ("class", "Class"),
    ("subclass", "Subclass"),
    ("lineage", "Species"),
    ("background", "Background"),
    ("abilities", "Ability scores"),
    ("feats", "Feats"),
    ("skills", "Skills"),
    ("spells", "Spells"),
    ("equipment", "Equipment"),
    ("review", "Review"),
]
STEP_TITLES = dict(STEPS)


def modifier(score: int) -> int:
    return (score - 10) // 2


def signed(value: int) -> str:
    return f"+{value}" if value >= 0 else str(value)


# ----------------------------------------------------------------------------------------------- the managers

@dataclass
class Sources:
    """Where the builder reads the collections from (injected so tests can pass their own)."""
    class_manager: object = None
    lineage_manager: object = None
    background_manager: object = None
    feat_manager: object = None
    equipment_manager: object = None
    legacy_filter: str = "show_all"

    @classmethod
    def default(cls) -> "Sources":
        from background import BackgroundManager
        from character_class import get_class_manager
        from equipment import get_equipment_manager
        from feat import get_feat_manager
        from lineage import get_lineage_manager
        try:
            from settings import get_settings_manager
            legacy = get_settings_manager().settings.legacy_content_filter
        except Exception:
            legacy = "show_all"
        return cls(get_class_manager(), get_lineage_manager(), BackgroundManager.get_instance(),
                   get_feat_manager(), get_equipment_manager(), legacy)

    def _filtered(self, items) -> list:
        from legacy_content import apply_legacy_filter
        return apply_legacy_filter(items, self.legacy_filter)

    def classes(self) -> list:
        return sorted((c for c in self._filtered(self.class_manager.classes) if c.name != "Custom"),
                      key=lambda c: c.name.lower())

    def lineages(self) -> list:
        return sorted(self._filtered(self.lineage_manager.lineages), key=lambda x: x.name.lower())

    def backgrounds(self) -> list:
        return sorted(self._filtered(self.background_manager.backgrounds), key=lambda x: x.name.lower())

    def class_def(self, name: str):
        return self.class_manager.get_class(name) if name else None

    def lineage(self, name: str):
        return self.lineage_manager.get_lineage(name) if name else None

    def background(self, name: str):
        return self.background_manager.get_background(name) if name else None

    def feat(self, name: str):
        return self.feat_manager.get_feat(name) if name and self.feat_manager else None

    def subclasses(self, class_def) -> list:
        if class_def is None:
            return []
        return self._filtered(class_def.selectable_subclasses)

    def general_feats(self) -> List[str]:
        """Feats a character can take in place of an Ability Score Improvement (2024 "General" feats have no type)."""
        if self.feat_manager is None:
            return []
        feats = [f for f in self._filtered(self.feat_manager.feats)
                 if (getattr(f, "type", "") or "") in ("", "General", "Origin", "Epic Boon") and f.name != ASI]
        return sorted({f.name for f in feats}, key=str.lower)


# ----------------------------------------------------------------------------------------------- the draft

@dataclass
class FeatSlot:
    """One Ability Score Improvement (or Epic Boon) the character's level gives."""
    level: int                                   # the class level that gives it
    feat: str = ASI                              # ASI, or the name of a feat taken instead
    plus: List[str] = field(default_factory=lambda: ["", ""])   # abilities raised by 1 each (twice = +2)


@dataclass
class Draft:
    name: str = ""
    level: int = 1
    class_name: str = ""
    subclass: str = ""
    lineage: str = ""
    background: str = ""
    origin_feat: str = ""
    bonus_mode: str = "2/1"                      # background ability bonuses: "2/1" or "1/1/1"
    bonus_plus2: str = ""
    bonus_plus1: str = ""
    score_method: str = "standard"
    # the ability scores before any bonus; standard array starts unassigned (0)
    base_scores: Dict[str, int] = field(default_factory=lambda: {a: 0 for a in ABILITIES})
    feat_slots: List[FeatSlot] = field(default_factory=list)
    class_skills: List[str] = field(default_factory=list)
    cantrips: List[str] = field(default_factory=list)
    spells: List[str] = field(default_factory=list)
    class_equipment: str = ""                    # option letter ("A", "B"...)
    background_equipment: str = ""
    grant_options: Dict[str, str] = field(default_factory=dict)        # species variant: {"lineage:Elf": "Drow"}
    grant_choices: Dict[str, List[str]] = field(default_factory=dict)  # spells chosen for a feat / species pick

    def set_score_method(self, method: str):
        """Switch how scores are made; each method starts from its own blank state."""
        if method == self.score_method:
            return
        self.score_method = method
        start = {"standard": 0, "point_buy": 8, "manual": 10}[method]
        self.base_scores = {a: start for a in ABILITIES}


# ----------------------------------------------------------------------------------------------- which steps apply

def needs_subclass(draft: Draft, src: Sources) -> bool:
    class_def = src.class_def(draft.class_name)
    return bool(class_def and src.subclasses(class_def) and draft.level >= class_def.subclass_level)


def feat_slot_levels(class_def, level: int) -> List[int]:
    """The class levels up to ``level`` that give an Ability Score Improvement or an Epic Boon."""
    found = []
    if class_def is None:
        return found
    for lvl in range(1, level + 1):
        data = class_def.levels.get(lvl) if isinstance(class_def.levels, dict) else None
        titles = [a.title.lower() for a in getattr(data, "abilities", [])] if data else []
        if any("ability score improvement" in t or t.startswith("epic boon") for t in titles):
            found.append(lvl)
    return found


def sync_feat_slots(draft: Draft, src: Sources) -> None:
    """Keep one feat slot per Ability Score Improvement level, keeping the choices already made."""
    levels = feat_slot_levels(src.class_def(draft.class_name), draft.level)
    old = {s.level: s for s in draft.feat_slots}
    draft.feat_slots = [old.get(lvl) or FeatSlot(lvl) for lvl in levels]


def spell_counts(draft: Draft, src: Sources) -> Tuple[int, int]:
    """(cantrips, prepared spells) the class (and a third-caster subclass) gives at the draft's level."""
    class_def = src.class_def(draft.class_name)
    if class_def is None:
        return 0, 0
    cantrips = prepared = 0
    data = class_def.levels.get(draft.level) if isinstance(class_def.levels, dict) else None
    if data is not None:
        table = getattr(data, "class_specific", {}) or {}
        cantrips = _number(table.get("Cantrips")) or int(getattr(data, "cantrips_known", 0) or 0)
        prepared = _number(table.get("Prepared Spells")) or int(getattr(data, "spells_known", 0) or 0)
    if not cantrips and not prepared and draft.subclass:
        character = draft_character(draft)
        third = character.get_eldritch_knight_level()
        if third >= 3:
            from spell_slots import get_eldritch_knight_cantrips, get_eldritch_knight_prepared
            cantrips = get_eldritch_knight_cantrips(third) + character.third_caster_extra_cantrips()
            prepared = get_eldritch_knight_prepared(third)
    return cantrips, prepared


def _number(text) -> int:
    match = re.match(r"\s*(\d+)", str(text or ""))
    return int(match.group(1)) if match else 0


def steps_for(draft: Draft, src: Sources) -> List[str]:
    """The keys of the steps this draft goes through."""
    keys = []
    for key, _title in STEPS:
        if key == "subclass" and not needs_subclass(draft, src):
            continue
        if key == "feats" and not feat_slot_levels(src.class_def(draft.class_name), draft.level):
            continue
        if key == "spells" and draft.class_name and spell_counts(draft, src) == (0, 0):
            continue
        keys.append(key)
    return keys


# ----------------------------------------------------------------------------------------------- abilities

def background_abilities(draft: Draft, src: Sources) -> List[str]:
    """The abilities (lower case) the background lets the character raise."""
    background = src.background(draft.background)
    names = [a.strip().lower() for a in getattr(background, "ability_scores", []) or []]
    return [a for a in names if a in ABILITIES]


def background_bonuses(draft: Draft, src: Sources) -> Dict[str, int]:
    allowed = background_abilities(draft, src)
    bonus = {a: 0 for a in ABILITIES}
    if not allowed:
        return bonus
    if draft.bonus_mode == "1/1/1":
        for a in allowed:
            bonus[a] += 1
    else:
        if draft.bonus_plus2 in allowed:
            bonus[draft.bonus_plus2] += 2
        if draft.bonus_plus1 in allowed and draft.bonus_plus1 != draft.bonus_plus2:
            bonus[draft.bonus_plus1] += 1
    return bonus


def feat_bonuses(draft: Draft) -> Dict[str, int]:
    bonus = {a: 0 for a in ABILITIES}
    for slot in draft.feat_slots:
        raises = slot.plus if slot.feat == ASI else slot.plus[:1]
        for a in raises:
            if a in bonus:
                bonus[a] += 1
    return bonus


def final_scores(draft: Draft, src: Sources) -> Dict[str, int]:
    """The ability scores with the background's and the feats' bonuses (a score can't go above 20)."""
    bg = background_bonuses(draft, src)
    ft = feat_bonuses(draft)
    out = {}
    for a in ABILITIES:
        base = draft.base_scores.get(a, 0) or 0
        out[a] = min(20, base + bg[a] + ft[a]) if base else 0
    return out


def points_spent(scores: Dict[str, int]) -> int:
    return sum(POINT_BUY_COST.get(scores.get(a, 8), 99) for a in ABILITIES)


def standard_array_left(scores: Dict[str, int]) -> List[int]:
    """The standard array's values not yet given to an ability."""
    left = list(STANDARD_ARRAY)
    for a in ABILITIES:
        value = scores.get(a, 0)
        if value in left:
            left.remove(value)
    return left


# ----------------------------------------------------------------------------------------------- skills

def all_skills() -> List[str]:
    from character_sheet import Skill
    return [s.display_name for s in Skill]


def background_skills(draft: Draft, src: Sources) -> List[str]:
    background = src.background(draft.background)
    known = {s.lower(): s for s in all_skills()}
    return [known[s.strip().lower()] for s in getattr(background, "skills", []) or [] if s.strip().lower() in known]


def class_skill_choice(draft: Draft, src: Sources) -> Tuple[int, List[str]]:
    """(how many, which) skills the class lets the character choose. An empty or "any" list means any skill."""
    class_def = src.class_def(draft.class_name)
    if class_def is None:
        return 0, []
    known = {s.lower(): s for s in all_skills()}
    options = [known[o.strip().lower()] for o in class_def.skill_proficiency_options or []
               if o.strip().lower() in known]
    if not options:
        options = all_skills()
    return int(class_def.skill_proficiency_choices or 0), options


def tidy_skills(draft: Draft, src: Sources) -> None:
    """Drop class skill picks that are no longer allowed (or now come from the background)."""
    count, options = class_skill_choice(draft, src)
    from_background = set(background_skills(draft, src))
    kept = [s for s in draft.class_skills if s in options and s not in from_background]
    draft.class_skills = kept[:count]


# ----------------------------------------------------------------------------------------------- spells

def draft_character(draft: Draft):
    """An unsaved CharacterSpellList for the draft (to ask which spells it may learn)."""
    from character import CharacterSpellList, ClassLevel
    from spell import CharacterClass
    character = CharacterSpellList(name=draft.name or "New Character")
    if draft.class_name:
        enum = CharacterClass.from_string(draft.class_name)
        custom = draft.class_name if enum == CharacterClass.CUSTOM else ""
        character.classes.append(ClassLevel(enum, draft.level, subclass=draft.subclass, custom_class_name=custom))
    character.lineage = draft.lineage
    feats = [draft.origin_feat] if draft.origin_feat else []
    feats += [s.feat for s in draft.feat_slots if s.feat and s.feat != ASI]
    character.feats = list(dict.fromkeys(feats))
    character.grant_options = dict(draft.grant_options)
    character.grant_choices = {k: list(v) for k, v in draft.grant_choices.items()}
    return character


def grant_report(draft: Draft):
    """What the draft's species, feats and class give in spells (spell_grants.Report): the species variant to
    pick, and the spells a feat like Magic Initiate lets the character choose."""
    from spell_grants import build_report
    try:
        return build_report(draft_character(draft))
    except Exception as e:
        print(f"Could not read the granted spells: {e}")
        return None


def species_options(draft: Draft):
    """The species variant choices (spell_grants.OptionGroup) of the draft's species."""
    report = grant_report(draft)
    return [o for o in (report.options if report else []) if o.key.startswith("lineage:")]


def tidy_grants(draft: Draft) -> None:
    """Forget variant and spell choices that belong to a species or feat the draft no longer has."""
    report = grant_report(draft)
    if report is None:
        return
    option_keys = {o.key: o.options for o in report.options}
    draft.grant_options = {k: v for k, v in draft.grant_options.items() if v in option_keys.get(k, [])}
    picks = {p.key: p.count for p in report.picks}
    draft.grant_choices = {k: v[:picks[k]] for k, v in draft.grant_choices.items() if k in picks}


def learnable_spells(draft: Draft, spells: List[object]) -> Tuple[List[object], List[object]]:
    """(cantrips, leveled spells) from ``spells`` the draft's class may learn."""
    from spell_access import learn_rules
    rules = learn_rules(draft_character(draft))
    ok = [s for s in spells if rules.allows(s)]
    ok.sort(key=lambda s: (s.level, s.name.lower()))
    return [s for s in ok if s.level == 0], [s for s in ok if s.level > 0]


def tidy_spells(draft: Draft, src: Sources, spells: Optional[List[object]] = None) -> None:
    """Drop picked spells the draft can no longer learn, and anything over the counts."""
    cantrips, prepared = spell_counts(draft, src)
    if spells is not None:
        can_c, can_s = learnable_spells(draft, spells)
        names_c = {s.name for s in can_c}
        names_s = {s.name for s in can_s}
        draft.cantrips = [n for n in draft.cantrips if n in names_c]
        draft.spells = [n for n in draft.spells if n in names_s]
    draft.cantrips = draft.cantrips[:cantrips]
    draft.spells = draft.spells[:prepared]


# ----------------------------------------------------------------------------------------------- equipment

_LINK = re.compile(r"\[\[[a-z_ ]+:([^\]|]+)(?:\|([^\]]*))?\]\]", re.I)
_OPTION = re.compile(r"\(([A-Z])\)\s*")
_COINS = re.compile(r"^(\d[\d,]*)\s*(GP|SP|CP|EP|PP)$", re.I)
_COUNT = re.compile(r"^(\d+)\s+(.+)$")
_POUCH = re.compile(r"(\d[\d,]*)\s*(gp|sp|cp|ep|pp)\s*$", re.I)       # "a pouch containing 15gp"


def _plain_text(text: str) -> str:
    return _LINK.sub(lambda m: m.group(2) or m.group(1), text or "").strip()


def split_items(text: str) -> List[str]:
    """'2 Daggers, Robe, and 5 GP' -> ['2 Daggers', 'Robe', '5 GP'] (commas inside brackets are kept)."""
    parts, depth, current = [], 0, ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    parts.append(current)
    items = []
    for part in parts:
        part = re.sub(r"^\s*(and|or)\s+", "", part.strip())
        part = re.sub(r"\s+and\s+(?=\d+\s*(GP|SP|CP)\b)", ", ", part)   # "Pack and 8 GP"
        for piece in part.split(", "):
            piece = piece.strip(" .;")
            if piece:
                items.append(piece)
    return items


def equipment_options(text: str) -> List[Tuple[str, List[str]]]:
    """'Choose A or B: (A) Robe, 5 GP; or (B) 55 GP' -> [('A', ['Robe', '5 GP']), ('B', ['55 GP'])].
    Text without lettered options is one option, 'A'."""
    text = _plain_text(text)
    if not text:
        return []
    pieces = _OPTION.split(text)
    if len(pieces) < 3:
        return [("A", split_items(text))]
    options = []
    for i in range(1, len(pieces) - 1, 2):
        body = re.sub(r"[;,]?\s*(or)?\s*$", "", pieces[i + 1].strip()).strip()
        options.append((pieces[i], split_items(body)))
    return options


def class_equipment_options(class_def) -> List[Tuple[str, List[str]]]:
    if class_def is None:
        return []
    structured = getattr(class_def, "starting_equipment_options", None) or []
    if structured:
        return [(o.option_letter, [_plain_text(i) for i in o.items]) for o in structured]
    text = " ".join(class_def.starting_equipment or []) or _bundled_equipment_text(class_def.name)
    return equipment_options(text)


_bundled: Optional[Dict[str, dict]] = None


def _bundled_class(class_name: str) -> dict:
    """A class as the bundled classes.json has it (empty for homebrew classes)."""
    global _bundled
    if _bundled is None:
        _bundled = {}
        try:
            import json
            from paths import resource_path
            with open(resource_path("classes.json"), encoding="utf-8") as f:
                data = json.load(f).get("classes", {})
            if isinstance(data, dict):
                _bundled = {name: entry for name, entry in data.items() if isinstance(entry, dict)}
        except Exception as e:
            print(f"Could not read the bundled classes: {e}")
    return _bundled.get(class_name, {})


def _bundled_equipment_text(class_name: str) -> str:
    """The starting equipment text of a bundled class. The database keeps only lettered options, so the
    classes whose equipment is written as one sentence (Rogue, Wizard...) lost it on the way in."""
    return " ".join(_bundled_class(class_name).get("starting_equipment") or [])


def class_description(class_def) -> str:
    """A class's description (the bundled one when the database has none)."""
    if class_def is None:
        return ""
    return class_def.description or _bundled_class(class_def.name).get("description", "")


@dataclass
class Item:
    text: str                      # as written: "2 Daggers"
    name: str = ""                 # the matching equipment entry, if there is one
    quantity: int = 1
    weight: float = 0.0
    coins: Tuple[str, int] = ("", 0)
    note: str = ""                 # what the linked row can't say: "(prayers)", "20" arrows in the bundle


def read_item(text: str, find: Callable[[str], object]) -> Item:
    """Read one item of a starting-equipment list; ``find(name)`` looks an entry up in the equipment collection."""
    item = Item(text=text)
    match = _COINS.match(text.strip())
    if match:
        item.coins = (match.group(2).lower(), int(match.group(1).replace(",", "")))
        return item
    name = text.strip()
    match = _COUNT.match(name)
    if match:
        item.quantity = int(match.group(1))
        name = match.group(2)
    base = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()
    candidates = [name, base]
    for word in (base,):
        if word.endswith("ies"):
            candidates.append(word[:-3] + "y")
        if word.endswith("es"):
            candidates.append(word[:-2])
        if word.endswith("s"):
            candidates.append(word[:-1])
        candidates += [word + " Armor", word.replace(" Armor", "")]
    for candidate in candidates:
        entry = find(candidate) if candidate else None
        if entry is not None:
            item.name = entry.name
            try:
                item.weight = float(getattr(entry, "weight", 0) or 0)
            except (TypeError, ValueError):
                item.weight = 0.0
            details = re.findall(r"\((.*?)\)", name)
            if (getattr(entry, "type", "") or "").lower() == "ammunition" and item.quantity > 1:
                details.insert(0, str(item.quantity))
                item.quantity = 1          # sold (and weighed) as a bundle: "20 Arrows" is one row of Arrows
            if details:
                item.note = f"{entry.name}: {', '.join(details)}"
            break
    else:
        match = _POUCH.search(text)
        if match:
            item.coins = (match.group(2).lower(), int(match.group(1).replace(",", "")))
    return item


# ----------------------------------------------------------------------------------------------- checking a step

def problems(draft: Draft, step: str, src: Sources, existing_names=()) -> List[str]:
    """What still has to be done on ``step`` before Next (empty when it's complete)."""
    out = []
    if step == "start":
        name = draft.name.strip()
        if not name:
            out.append("Give your character a name.")
        elif name in set(existing_names):
            out.append("A character with that name already exists.")
        if not 1 <= draft.level <= 20:
            out.append("The level must be between 1 and 20.")
    elif step == "class":
        if not src.class_def(draft.class_name):
            out.append("Pick a class.")
    elif step == "subclass":
        if needs_subclass(draft, src) and not draft.subclass:
            out.append("Pick a subclass.")
    elif step == "lineage":
        if not draft.lineage:
            out.append("Pick a species.")
    elif step == "background":
        if not draft.background:
            out.append("Pick a background.")
        allowed = background_abilities(draft, src)
        if allowed and draft.bonus_mode == "2/1":
            if draft.bonus_plus2 not in allowed or draft.bonus_plus1 not in allowed:
                out.append("Choose which abilities get +2 and +1.")
            elif draft.bonus_plus2 == draft.bonus_plus1:
                out.append("The +2 and the +1 must go to different abilities.")
    elif step == "abilities":
        scores = draft.base_scores
        if draft.score_method == "standard" and any(not scores.get(a) for a in ABILITIES):
            out.append("Give every ability a score from the standard array.")
        elif draft.score_method == "point_buy" and points_spent(scores) > POINT_BUY_BUDGET:
            out.append(f"That's more than {POINT_BUY_BUDGET} points.")
        elif draft.score_method == "manual" and any(not 3 <= scores.get(a, 0) <= 20 for a in ABILITIES):
            out.append("Every score must be between 3 and 20.")
    elif step == "feats":
        for slot in draft.feat_slots:
            if slot.feat == ASI and not all(slot.plus):
                out.append(f"Level {slot.level}: choose the abilities your improvement raises.")
    elif step == "skills":
        count, _options = class_skill_choice(draft, src)
        if len(draft.class_skills) < count:
            out.append(f"Choose {count - len(draft.class_skills)} more skill"
                       f"{'s' if count - len(draft.class_skills) != 1 else ''}.")
    elif step == "equipment":
        if class_equipment_options(src.class_def(draft.class_name)) and not draft.class_equipment:
            out.append("Choose your class's starting equipment.")
        background = src.background(draft.background)
        if equipment_options(getattr(background, "equipment", "")) and not draft.background_equipment:
            out.append("Choose your background's starting equipment.")
    return out


def leftovers(draft: Draft, src: Sources) -> List[str]:
    """Things the builder doesn't choose, to finish on the sheet (shown on the Review step)."""
    notes = []
    cantrips, prepared = spell_counts(draft, src)
    if len(draft.cantrips) < cantrips or len(draft.spells) < prepared:
        notes.append("Some spells are still to choose: add them on the sheet's Spells tab.")
    class_def = src.class_def(draft.class_name)
    if class_def is not None:
        for lvl in range(1, draft.level + 1):
            data = class_def.levels.get(lvl) if isinstance(class_def.levels, dict) else None
            for ability in getattr(data, "abilities", []) or []:
                title = ability.title.lower()
                if any(word in title for word in ("fighting style", "eldritch invocation", "expertise",
                                                  "weapon mastery", "metamagic")):
                    notes.append(f"{class_def.name} {lvl}: choose your {ability.title} on the sheet.")
    report = grant_report(draft)
    if report is not None and report.unresolved():
        notes.append("Your species or a feat still has a choice to make: finish it on the sheet's Spells tab.")
    return list(dict.fromkeys(notes))


# ----------------------------------------------------------------------------------------------- making it

def create_character(draft: Draft, src: Sources, character_manager, sheet_manager):
    """Make and save the character and its sheet from a finished draft; returns the character."""
    from character import update_subclass_spells
    from character_sheet import (AbilityScore, ArmorType, Skill, calculate_proficiency_bonus,
                                 get_default_proficiencies, get_hit_dice_for_classes)
    import sheet_stats
    from character_rolls import Lookups

    character = draft_character(draft)
    character.name = draft.name.strip()
    class_def = src.class_def(draft.class_name)
    character.known_spells = list(dict.fromkeys(draft.cantrips + draft.spells))
    character.prepared_spells = list(dict.fromkeys(draft.spells))
    try:
        update_subclass_spells(character)
    except Exception as e:                                # a spell lookup problem never stops the character
        print(f"Could not add granted spells: {e}")

    sheets = sheet_manager
    with _held(character_manager), _held(sheets):
        character_manager.add_character(character)
        sheet = sheets.get_or_create_sheet(character.name, character)
        sheet.background = draft.background
        lineage = src.lineage(draft.lineage)
        sheet.race = draft.lineage
        if lineage is not None and lineage.speed:
            sheet.base_speed = sheet.speed = int(lineage.speed)

        for ability, score in final_scores(draft, src).items():
            setattr(sheet.ability_scores, ability, score or 10)

        # Saving throws and Unarmored Defense from the class
        if class_def is not None:
            for save in class_def.saving_throw_proficiencies:
                enum = AbilityScore.from_short_name(save)
                if enum is not None:
                    sheet.saving_throws.set_proficiency(enum, True)
            if class_def.unarmored_defense:
                sheet.unarmored_defense = class_def.unarmored_defense
            sub = class_def.find_subclass(draft.subclass) if draft.subclass else None
            if sub is not None and sub.unarmored_defense and not sheet.unarmored_defense:
                sheet.unarmored_defense = sub.unarmored_defense

        chosen = set(background_skills(draft, src)) | set(draft.class_skills)
        for skill in Skill:
            if skill.display_name in chosen:
                sheet.skills.set(skill, 1)

        class_levels = [(draft.class_name, draft.level)] if draft.class_name else []
        sheet.proficiency_bonus = calculate_proficiency_bonus(draft.level)
        dice = get_hit_dice_for_classes(class_levels)
        sheet.hit_points.hit_dice_total = sum(dice.values())
        sheet.hit_points.hit_dice_by_type = dict(dice)
        sheet.hit_points.hit_dice_remaining = sum(dice.values())
        if class_def is not None:
            sheet.hit_points.hit_die_type = class_def.hit_die

        # Proficiencies and languages
        lines = []
        defaults = get_default_proficiencies(class_levels)
        if defaults:
            lines.append(defaults)
        background = src.background(draft.background)
        tools = [_plain_text(t) for t in getattr(background, "other_proficiencies", []) or []]
        if tools:
            lines.append("Background: " + ", ".join(tools))
        lines.append("Languages: Common")
        sheet.other_proficiencies = "\n\n".join(lines)

        _give_equipment(draft, src, sheet)

        lookups = Lookups(class_def=src.class_def, feat=src.feat, lineage=src.lineage,
                          equipment=lambda n: _find_equipment(src, n))
        try:
            from magic_item import get_magic_item_manager
            lookups.magic_item = lambda n: get_magic_item_manager().get_item(n)
        except Exception:
            pass
        try:
            bonuses = sheet_stats.find_bonuses(character, sheet, lookups)
            sheet.armor_class = sheet_stats.auto_ac(character, sheet, lookups, bonuses).value
            hp = sheet_stats.auto_hp_max(character, sheet, lookups, bonuses).value
            sheet.hit_points.maximum = sheet.hit_points.current = hp
        except Exception as e:
            print(f"Could not work out AC / HP for the new character: {e}")
        if ArmorType.from_name(sheet.armor_type) == ArmorType.NONE and sheet.armor_type != "None":
            sheet.armor_type = "None"
        sheets.update_sheet(character.name, sheet)
        character_manager.save_characters()
    return character


class _held:
    """``with saves_held()`` when the manager has it (one file write for the whole character)."""

    def __init__(self, manager):
        self._cm = manager.saves_held() if hasattr(manager, "saves_held") else None

    def __enter__(self):
        if self._cm is not None:
            self._cm.__enter__()

    def __exit__(self, *exc):
        if self._cm is not None:
            return self._cm.__exit__(*exc)
        return False


def _find_equipment(src: Sources, name: str):
    manager = src.equipment_manager
    if manager is None or not name:
        return None
    try:
        return manager.get_item(name)
    except Exception:
        return None


def chosen_items(draft: Draft, src: Sources) -> List[Item]:
    """Every item of the starting equipment options the draft picked."""
    texts: List[str] = []
    for options, letter in ((class_equipment_options(src.class_def(draft.class_name)), draft.class_equipment),
                            (equipment_options(getattr(src.background(draft.background), "equipment", "")),
                             draft.background_equipment)):
        for opt_letter, items in options:
            if opt_letter == letter:
                texts += items
    find = lambda n: _find_equipment(src, n)
    return [read_item(t, find) for t in texts]


def _give_equipment(draft: Draft, src: Sources, sheet) -> None:
    from character_sheet import ArmorType
    rows: Dict[str, dict] = {}
    notes: List[str] = []
    best_armor = None
    for item in chosen_items(draft, src):
        kind, amount = item.coins
        if kind:
            attr = {"gp": "gold", "sp": "silver", "cp": "copper", "ep": "electrum", "pp": "platinum"}[kind]
            setattr(sheet, attr, getattr(sheet, attr, 0) + amount)
            continue
        if not item.name:
            notes.append(item.text)
            continue
        if item.note:              # "Arcane Focus: Quarterstaff", "Arrows: 20"
            notes.append(item.note)
        row = rows.get(item.name)
        if row is None:
            rows[item.name] = {"name": item.name, "quantity": item.quantity, "weight": item.weight}
        else:
            row["quantity"] += item.quantity
        armor = ArmorType.from_name(item.name.replace(" Armor", ""))
        if armor != ArmorType.NONE and (best_armor is None or armor.base_ac > best_armor.base_ac):
            best_armor = armor
        if item.name.lower() == "shield":
            sheet.shield_bonus = 2
    sheet.equipment_items = list(sheet.equipment_items) + list(rows.values())
    if best_armor is not None:
        sheet.armor_type = best_armor.display_name
    if notes:
        sheet.equipment = "\n".join(([sheet.equipment] if sheet.equipment else []) + notes)
