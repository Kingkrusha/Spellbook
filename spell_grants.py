"""
The spells a character's species, feats, classes and subclasses give them.

Class and subclass spells have always been added to a character automatically: always prepared, known, and not
counted against the spells the character can prepare. This module does the same for everything else that grants
spells:

* a species' innate spells (Fairy Magic, a Tiefling's legacy, the Marks of Eberron ...), at the character levels
  they arrive; species that make you choose a variant (the Elf's lineage, a Tiefling's legacy, the Gnome's
  lineage) use the variant chosen in ``CharacterSpellList.grant_options``;
* a feat's set spells (Fey Touched's Misty Step, an Eldritch Invocation's at-will spell ...);
* spells a feat or species lets the character pick (Magic Initiate's cantrips), chosen in
  ``CharacterSpellList.grant_choices`` and added like the others;
* class and subclass features that give a spell a class table does not list (a Wizard school's Polymorph, the
  Wild Heart's rituals ...).

``build_report`` works out what applies to a character; ``add_granted_spells`` writes it to the character and is
called by ``character.update_subclass_spells``. Pure logic: the managers it reads are passed in or found lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, NamedTuple, Optional

import spell_grant_data as data
from legacy_content import strip_legacy_suffix


class SpellRef(NamedTuple):
    name: str
    level: int


@dataclass
class Grant:
    spell: str
    source: str                         # "Feat: Fey Touched", "Species: Tiefling", "Subclass: Path of the Wild Heart"
    level: int = 1


@dataclass
class Pick:
    """Spells the character chooses (Magic Initiate's two cantrips ...)."""
    key: str
    source: str
    label: str
    count: int
    spell_level: Optional[int] = None   # None: any level
    lists: List[str] = field(default_factory=list)      # class spell lists or schools the spell may come from
    names: List[str] = field(default_factory=list)      # or an explicit short list
    chosen: List[str] = field(default_factory=list)

    def allows(self, spell) -> bool:
        """Whether ``spell`` (a Spell) may be chosen for this pick."""
        if self.spell_level is not None and spell.level != self.spell_level:
            return False
        if self.names:
            return spell.name.lower() in {n.lower() for n in self.names}
        if not self.lists:
            return True
        wanted = {strip_legacy_suffix(x).strip().lower() for x in self.lists}
        classes = {strip_legacy_suffix(c).strip().lower() for c in spell.get_class_names()}
        tags = {t.lower() for t in getattr(spell, "tags", [])}
        return bool(wanted & classes) or bool(wanted & tags)


@dataclass
class OptionGroup:
    """A choice between variants of a species trait that decides which spells it gives."""
    key: str
    source: str
    label: str
    options: List[str]
    selected: str = ""


@dataclass
class Report:
    fixed: List[Grant] = field(default_factory=list)
    picks: List[Pick] = field(default_factory=list)
    options: List[OptionGroup] = field(default_factory=list)

    @property
    def has_choices(self) -> bool:
        return bool(self.picks or self.options)

    def unresolved(self) -> int:
        """How many choices are still to be made."""
        return (sum(1 for o in self.options if not o.selected)
                + sum(max(0, p.count - len(p.chosen)) for p in self.picks))


# ----------------------------------------------------------------------------- finding spells

_database = None


def default_lookup() -> Callable[[str], Optional[SpellRef]]:
    """Name -> SpellRef straight from the spell database (no need for a loaded SpellManager)."""
    global _database
    from database import SpellDatabase
    if _database is None:
        _database = SpellDatabase()
        _database.initialize()
    db = _database

    def lookup(name: str) -> Optional[SpellRef]:
        with db.get_connection() as conn:
            row = conn.execute("SELECT name, level FROM spells WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        return SpellRef(row["name"], row["level"]) if row else None

    return lookup


def resolve_spell(lookup: Callable[[str], object], name: str, legacy: bool = False):
    """The spell called ``name`` in the collection. A legacy source prefers the 2014 version of the spell, any
    other the current one; either falls back to the other so a spell is found when only one exists."""
    plain = strip_legacy_suffix(name).strip()
    order = [f"{plain} (Legacy)", plain] if legacy else [plain, f"{plain} (Legacy)"]
    if plain != name.strip():                                     # the name already says which version
        order.insert(0, name.strip())
    for candidate in order:
        spell = lookup(candidate)
        if spell is not None:
            return spell
    return None


def _managers(class_manager=None, feat_manager=None, lineage_manager=None):
    if class_manager is None:
        from character_class import get_class_manager
        class_manager = get_class_manager()
    if feat_manager is None:
        from feat import get_feat_manager
        feat_manager = get_feat_manager()
    if lineage_manager is None:
        from lineage import get_lineage_manager
        lineage_manager = get_lineage_manager()
    return class_manager, feat_manager, lineage_manager


def _total_level(character) -> int:
    return max(1, sum(cl.level for cl in character.classes))


def _is_legacy_class(class_name: str, class_def) -> bool:
    return class_name.strip().lower().endswith("(legacy)") or bool(getattr(class_def, "is_legacy", False))


# ----------------------------------------------------------------------------- reading the sources

def _lineage_report(character, report: Report, lineage_manager, lookup):
    name = (getattr(character, "lineage", "") or "").strip()
    if not name:
        return
    lineage = lineage_manager.get_lineage(name) if lineage_manager is not None else None
    legacy = bool(getattr(lineage, "is_legacy", False))
    source = f"Species: {name}"
    level = _total_level(character)
    table = {k.lower(): v for k, v in data.LINEAGE_GRANTS.items()}.get(name.lower())

    fixed, options, picks = [], {}, []
    if table is not None:
        fixed = list(table["fixed"])
        options = {k: list(v) for k, v in table["options"].items()}
        picks = list(table["picks"])
    if lineage is not None and getattr(lineage, "is_custom", False):      # what a custom species' traits say
        for trait in getattr(lineage, "traits", []) or []:
            for entry in getattr(trait, "spells", []) or []:
                spell = entry.get("spell") if isinstance(entry, dict) else None
                if not spell:
                    continue
                at = int(entry.get("level", 1) or 1)
                option = (entry.get("option") or "").strip()
                if option:
                    options.setdefault(option, []).append((spell, at))
                else:
                    fixed.append((spell, at))
    for spell, at in fixed:
        if at <= level:
            _add_fixed(report, lookup, spell, source, at, legacy)
    if options:
        key = f"lineage:{name}"
        label = data.OPTION_LABEL.get(name, "Species option")
        selected = (getattr(character, "grant_options", {}) or {}).get(key, "")
        if selected not in options:
            selected = ""
        report.options.append(OptionGroup(key, source, label, list(options), selected))
        for spell, at in options.get(selected, []):
            if at <= level:
                _add_fixed(report, lookup, spell, source, at, legacy)
    for i, pick in enumerate(picks):
        _add_pick(report, character, f"lineage:{name}:{i}", source, pick["label"], pick["count"], pick.get("level"),
                  pick.get("lists", []), pick.get("names", []))


def _feat_report(character, report: Report, feat_manager, lookup):
    for feat_name in getattr(character, "feats", []) or []:
        feat = feat_manager.get_feat(feat_name) if feat_manager is not None else None
        name = feat.name if feat is not None else feat_name
        legacy = bool(getattr(feat, "is_legacy", False))
        source = f"Feat: {name}"
        fixed = list(getattr(feat, "set_spells", []) or []) or list(data.FEAT_GRANTS.get(name, []))
        fixed_levels: Dict[int, int] = {}
        for spell_name in fixed:
            spell = _add_fixed(report, lookup, spell_name, source, 1, legacy)
            if spell is not None:
                fixed_levels[spell.level] = fixed_levels.get(spell.level, 0) + 1
        if feat is not None and getattr(feat, "is_spellcasting", False):
            lists = list(getattr(feat, "spell_lists", []) or [])
            for spell_level, count in sorted((getattr(feat, "spells_num", {}) or {}).items()):
                left = int(count) - fixed_levels.get(int(spell_level), 0)
                if left > 0:
                    what = "cantrip" if int(spell_level) == 0 else f"level {spell_level} spell"
                    _add_pick(report, character, f"feat:{name}:{spell_level}", source,
                              f"{left} {what}{'s' if left != 1 else ''}", left, int(spell_level), lists, [])
        for i, extra in enumerate(data.FEAT_PICKS.get(name, [])):
            _add_pick(report, character, f"feat:{name}:extra{i}", source, extra["label"], extra["count"],
                      extra.get("level"), extra.get("lists", []), extra.get("names", []))


def _class_report(character, report: Report, class_manager, lookup):
    for cl in character.classes:
        class_name = cl.get_class_name()
        class_def = class_manager.get_class(class_name) if class_manager is not None else None
        legacy = _is_legacy_class(class_name, class_def)
        base = strip_legacy_suffix(class_name).strip().lower()
        class_table = data.LEGACY_CLASS_GRANTS if legacy else data.CLASS_GRANTS
        for spell, at in class_table.get(base, []):
            if cl.level >= at:
                _add_fixed(report, lookup, spell, f"Class: {strip_legacy_suffix(class_name)}", at, legacy)
        sub = (getattr(cl, "subclass", "") or "").strip()
        if not sub:
            continue
        sub_def = class_def.find_subclass(sub) if class_def is not None else None
        sub_legacy = legacy or sub.lower().endswith("(legacy)") or bool(getattr(sub_def, "is_legacy", False))
        table = data.LEGACY_SUBCLASS_GRANTS if sub_legacy else data.SUBCLASS_GRANTS
        grants = table.get((base, strip_legacy_suffix(sub).strip().lower()), [])
        sub_level = getattr(class_def, "subclass_level", 1) or 1
        for spell, at in grants:
            if cl.level >= max(at, sub_level):                # nothing a subclass grants arrives before it is chosen
                _add_fixed(report, lookup, spell, f"Subclass: {sub}", at, sub_legacy)


def _add_fixed(report: Report, lookup, name: str, source: str, level: int, legacy: bool):
    spell = resolve_spell(lookup, name, legacy)
    if spell is None:
        return None
    for g in report.fixed:
        if g.spell.lower() == spell.name.lower():
            if source not in g.source:
                g.source += f", {source}"
            return spell
    report.fixed.append(Grant(spell.name, source, level))
    return spell


def _add_pick(report: Report, character, key: str, source: str, label: str, count: int, level,
              lists: List[str], names: List[str]):
    chosen = list((getattr(character, "grant_choices", {}) or {}).get(key, []))[:count]
    report.picks.append(Pick(key, source, label, count, level, list(lists), list(names), chosen))


def build_report(character, class_manager=None, feat_manager=None, lineage_manager=None,
                 spell_lookup: Optional[Callable[[str], object]] = None) -> Report:
    """Everything the character's species, feats, classes and subclasses give in spells."""
    class_manager, feat_manager, lineage_manager = _managers(class_manager, feat_manager, lineage_manager)
    lookup = spell_lookup or default_lookup()
    report = Report()
    _lineage_report(character, report, lineage_manager, lookup)
    _feat_report(character, report, feat_manager, lookup)
    _class_report(character, report, class_manager, lookup)
    return report


# ----------------------------------------------------------------------------- homebrew species traits

def parse_trait_spells(text: str, lookup: Optional[Callable[[str], object]] = None):
    """The spells a custom species trait gives, typed one per line as ``Spell``, ``Spell, 3`` (arrives at
    character level 3) or ``Spell, 3, Variant`` (only for that variant of the trait). Returns (entries, errors);
    with a ``lookup`` every name must be a spell in the collection."""
    entries, errors = [], []
    for number, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        spell = parts[0]
        level = 1
        if len(parts) > 1 and parts[1]:
            try:
                level = int(parts[1])
            except ValueError:
                errors.append(f"Line {number}: '{parts[1]}' is not a character level.")
                continue
            if not 1 <= level <= 20:
                errors.append(f"Line {number}: the character level must be between 1 and 20.")
                continue
        if lookup is not None:
            found = resolve_spell(lookup, spell)
            if found is None:
                errors.append(f"Line {number}: there is no spell called '{spell}'.")
                continue
            spell = found.name
        entry = {"spell": spell, "level": level}
        if len(parts) > 2 and parts[2]:
            entry["option"] = ", ".join(parts[2:])
        entries.append(entry)
    return entries, errors


def format_trait_spells(entries) -> str:
    """The text ``parse_trait_spells`` reads, for showing a trait's spells in an editor."""
    lines = []
    for e in entries or []:
        line = f"{e.get('spell', '')}, {e.get('level', 1)}"
        if e.get("option"):
            line += f", {e['option']}"
        lines.append(line)
    return "\n".join(lines)


# ----------------------------------------------------------------------------- writing it to the character

def _grant(character, spell_name: str, source: str):
    """Always prepared, known, and outside the counts of prepared spells and cantrips."""
    low = spell_name.lower()
    if low not in [s.lower() for s in character.subclass_spells]:
        character.subclass_spells.append(spell_name)
    if low not in [s.lower() for s in character.class_feature_spells]:
        character.class_feature_spells.append(spell_name)
    if not character.has_spell(spell_name):
        character.known_spells.append(spell_name)
    if low not in [s.lower() for s in character.prepared_spells]:
        character.prepared_spells.append(spell_name)
    sources = character.spell_sources
    if spell_name in sources and source not in sources[spell_name]:
        sources[spell_name] += f", {source}"
    else:
        sources.setdefault(spell_name, source)


def add_granted_spells(character, class_manager=None, report: Optional[Report] = None,
                       spell_lookup: Optional[Callable[[str], object]] = None) -> Report:
    """Add the spells the character's species, feats, classes and subclasses give."""
    character.spell_sources = {}
    lookup = spell_lookup or default_lookup()
    report = report or build_report(character, class_manager, spell_lookup=lookup)
    for g in report.fixed:
        _grant(character, g.spell, g.source)
    for pick in report.picks:
        for name in pick.chosen:
            spell = resolve_spell(lookup, name)
            if spell is not None:
                _grant(character, spell.name, pick.source)
    return report
