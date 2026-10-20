"""
Cross-reference index for the Homebrew Studio.

No UI. Every collection is broken into *entries* - the smallest thing worth comparing: a spell, a feat, one
class feature, one subclass feature, one lineage trait, one background feature, a magic item, a piece of
equipment, one trait / action of a monster, one rules section. ``HomebrewIndex.similar(text)`` then finds the
entries whose wording and *mechanics* resemble what is being written, so a designer can see that the
"treat a d20 roll of 9 or lower as a 10" item they are drafting already exists as the Rogue's Reliable Talent
and the Eloquence Bard's Silver Tongue.

Two signals are combined:

* **Words.** Stemmed, stop-worded words weighted by how rare they are across the whole index (a word such as
  "d20" or "frightened" says far more than "creature"). The score is how much of the draft's weight the entry
  covers, tempered by how much of the entry the draft explains (a 300-word class feature that merely
  contains the same phrase is a weaker match than a one-line twin).
* **Mechanics.** ``mechanics()`` reads rules phrasing into small tags ("minimum d20 roll", "advantage on saving
  throws", "resistance to fire damage"). Two texts that share a tag do the same thing even when they word it
  differently, so a shared tag is both a strong score boost and the "why" shown to the user.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from rules import stem as _stem

# --------------------------------------------------------------------------- families

# key -> label, in the order shown to users
FAMILIES: Dict[str, str] = {
    "spells": "Spells",
    "feats": "Feats",
    "class_features": "Class & subclass features",
    "lineages": "Lineages & traits",
    "backgrounds": "Backgrounds",
    "magic_items": "Magic items",
    "equipment": "Equipment",
    "monsters": "Monster abilities",
    "rules": "Rules",
}

# the editor kinds (content_io keys) -> the family of the entries they produce
KIND_FAMILY = {
    "spells": "spells", "feats": "feats", "classes": "class_features", "subclasses": "class_features",
    "lineages": "lineages", "backgrounds": "backgrounds", "magic_items": "magic_items",
    "equipment": "equipment", "monsters": "monsters", "rules": "rules",
}

# family -> the object-link category used to open the whole owning object
FAMILY_LINK = {"spells": "spell", "feats": "feat", "lineages": "lineage", "backgrounds": "background",
               "magic_items": "magic_item", "equipment": "equipment", "monsters": "monster", "rules": "rule"}


# --------------------------------------------------------------------------- text

_LINK = re.compile(r"\[\[([^\]]+)\]\]")
_WORD = re.compile(r"[a-z0-9]+")
_MARKUP = re.compile(r"(\*{1,3}|_{2}|`)")

STOPWORDS = frozenset("""
a an and are as at be been being but by can cannot could did do does doing done each either else for from had has have
having he her hers him his how i if in into is it its itself just may me might more most must my no nor not of off on
once only or other our out over own per same shall she should so some such than that the their them then there these
they this those through to too under until up upon us very was we were what when whenever where whether which while who
whom whose why will with within without would you your yours yourself also any all both few many much one two three
four five six seven eight nine ten first second third another further additionally instead after before during
again already still then thus therefore however
""".split())

# words that carry the rules meaning of a sentence but are short or common enough to deserve a floor weight
_BOOST_WORDS = frozenset("""d20 d12 d10 d8 d6 d4 d100 advantage disadvantage resistance immunity vulnerability reroll
treat minimum double half proficiency expertise bonus
""".split())


def plain(text: str) -> str:
    """Text with ``[[links]]`` replaced by their visible words and markdown emphasis removed."""
    def sub(m):
        body, _, shown = m.group(1).partition("|")
        if shown.strip():
            return shown.strip()
        head, sep, rest = body.partition(":")
        if sep and head.strip().lower().replace(" ", "_") in (
                "spell", "feat", "lineage", "background", "class", "subclass", "equipment", "magic_item",
                "monster", "rule"):
            rest = rest.strip()
            return rest.rsplit("#", 1)[-1] if head.strip().lower() == "rule" else rest
        return body.strip()
    out = _LINK.sub(sub, text or "")
    out = _MARKUP.sub("", out)
    return re.sub(r"[ \t]+", " ", out).strip()


def drop_tables(text: str) -> str:
    """Text without its markdown table rows (a summoned creature's stat block, a class table): they are long lists
    of keywords - every damage type, every condition - that would make unrelated texts look alike."""
    return "\n".join(line for line in (text or "").split("\n") if not line.lstrip().startswith("|"))


_ATTACK_FORMULA = re.compile(
    r"(?:Melee or Ranged|Melee|Ranged)(?: Weapon| Spell)? Attack(?: Roll)?:\s*[+-]\d+,\s*"
    r"(?:reach[^.]*?ft\.(?: or range[^.]*?ft\.)?|range[^.]*?ft\.)\s*Hit:\s*\d+\s*\([^)]*\)\s*\w+\s+damage"
    r"(?:\s+plus\s+\d+\s*\([^)]*\)\s*\w+\s+damage)?\.?", re.I)


def strip_attack_formula(text: str) -> str:
    """A stat block's stock attack sentence ("Melee Attack Roll: +7, reach 5 ft. Hit: 13 (2d8 + 4) Slashing damage.")
    removed. Every claw and bite has one, so it would make every claw look like every other claw; what is left is
    what the attack *also* does."""
    return _ATTACK_FORMULA.sub("", text or "").strip()


# a few words that mean the same thing in rules text
_SYNONYMS = {"hp": "hitpoint", "ac": "armor", "armour": "armor", "resist": "resistance", "resistant": "resistance",
             "immune": "immunity", "vulnerable": "vulnerability", "saves": "save", "saving": "save",
             "throw": "save", "throws": "save", "checks": "check", "rolls": "roll", "lowers": "lower",
             "lesser": "lower", "less": "lower", "below": "lower", "greater": "higher", "above": "higher",
             "count": "treat", "consider": "treat", "regains": "regain", "restores": "regain", "heals": "regain",
             "heal": "regain", "seconds": "second", "minutes": "minute", "hours": "hour"}


def words(text: str) -> List[str]:
    """Lower-case content words of ``text`` (stemmed, stop words and lone letters removed)."""
    t = (text or "").lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"(?<=\w)'(?=\w)", "", t)
    out = []
    for w in _WORD.findall(t):
        if w in STOPWORDS:
            continue
        w = _SYNONYMS.get(w, w)
        if len(w) < 2 and not w.isdigit():
            continue
        out.append(_stem(w))
    return out


# --------------------------------------------------------------------------- mechanics

_DAMAGE_TYPES = ("acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic", "piercing", "poison",
                 "psychic", "radiant", "slashing", "thunder")
_CONDITIONS = ("blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated", "invisible", "paralyzed",
               "petrified", "poisoned", "prone", "restrained", "stunned", "unconscious", "exhaustion")
_SKILLS = ("acrobatics", "animal handling", "arcana", "athletics", "deception", "history", "insight", "intimidation",
           "investigation", "medicine", "nature", "perception", "performance", "persuasion", "religion",
           "sleight of hand", "stealth", "survival")
_ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
_SENSES = ("darkvision", "blindsight", "truesight", "tremorsense")

# (tag, label, words that must appear for the pattern to be worth running, regex). The prefilter is what keeps
# indexing fast: most texts contain none of a rule's trigger words, so the regex never runs.
_RULES: List[Tuple[str, str, Tuple[str, ...], "re.Pattern"]] = []


def _rule(tag: str, label: str, needs: Tuple[str, ...], pattern: str, flags=re.I | re.S):
    _RULES.append((tag, label, tuple(n.lower() for n in needs), re.compile(pattern, flags)))


# d20 manipulation
_rule("min_d20", "treats low d20 rolls as a higher number", ("d20",),
      r"(treat|count|consider|use)[^.;]{0,80}\bd20\b[^.;]{0,60}(or lower|or less|lower than|less than|below)[^.;]{0,40}\bas (a |an )?\d+"
      r"|(roll|rolls)[^.;]{0,30}\bd20\b[^.;]{0,40}(lower|less|below)[^.;]{0,24}\bas (a |an )?\d+"
      r"|\bd20\b[^.;]{0,40}(lower|less|below)[^.;]{0,30}\b(counts?|counted|is treated|treated|becomes?)( as)? (a |an )?\d+"
      r"|\bd20 (roll|result)[^.;]{0,30}(of|is) \d+ or (lower|less)[^.;]{0,30}\d+"
      r"|minimum (result|roll|total) (of|is) \d+ on (the|a|your) d20")
_rule("reroll", "lets you reroll dice", ("reroll", "re-roll"), r"\bre-?roll\b")
_rule("roll_extra_d", "adds an extra die to a roll", ("bardic inspiration", "guidance", "bless", "add"),
      r"(add|roll|gain)[^.;]{0,25}\b\d*d(4|6|8|10|12)\b[^.;]{0,50}(to the (roll|check|save|attack|total)|to your (roll|check|save|attack))"
      r"|\bbardic inspiration\b|\bgui?dance\b|\bbless\b")
_rule("crit_range", "changes critical hits", ("critical", "crit"),
      r"critical hit[^.;]{0,50}(on a roll of|on a \d+|score)|score a critical hit on a (roll|d20) of|crit(ical)? range")
_rule("crit_extra", "extra damage on a critical hit", ("critical",),
      r"(extra|additional)[^.;]{0,30}\bon a critical hit|when you score a critical hit[^.;]{0,80}(extra|additional|add)")

# advantage / disadvantage - specific targets
_ADV_TARGETS = [
    ("saves", r"saving throws?"), ("checks", r"(ability )?checks?"), ("attacks", r"attack rolls?"),
    ("initiative", r"initiative"), ("death_saves", r"death saving throws?"),
    ("concentration", r"concentration"),
]
for _t, _p in _ADV_TARGETS:
    _rule(f"adv:{_t}", f"advantage on {_t.replace('_', ' ')}", ("advantage",), rf"\badvantage on [^.;]{{0,80}}?{_p}")
    _rule(f"dis:{_t}", f"disadvantage on {_t.replace('_', ' ')}", ("disadvantage",),
          rf"\bdisadvantage on [^.;]{{0,80}}?{_p}")
_rule("adv", "grants advantage", ("advantage",),
      r"\badvantage\b(?! on)|\bhas? advantage\b|\bwith advantage\b|\bgain advantage\b")
_rule("dis", "imposes disadvantage", ("disadvantage",), r"\bdisadvantage\b(?! on)|\bimpose disadvantage\b")
for _s in _SKILLS:
    _rule(f"skill:{_s}", f"{_s} checks", (_s,),
          rf"\b{_s}\b(?=[^.;]{{0,60}}(check|proficien|expertise|bonus|advantage))"
          rf"|(check|proficien|expertise|bonus|advantage)[^.;]{{0,60}}\b{_s}\b")
_rule("expertise", "grants expertise / doubles proficiency", ("expertise", "proficiency bonus"),
      r"\bexpertise\b|double your proficiency bonus|twice your proficiency bonus"
      r"|proficiency bonus (is |are )?(doubled|twice)|doubl\w+ (your |the )?proficiency")
_rule("proficiency", "grants proficiency", ("proficien",),
      r"\bgain proficiency\b|\byou (are|become) proficient\b|proficiency (in|with)")
_rule("pb_scaling", "scales with proficiency bonus", ("proficiency bonus",),
      r"\b(add|equal to|plus|uses?) your proficiency bonus\b|\bproficiency bonus (times|per|uses)\b")
_rule("ability_set", "sets an ability score", ("score",),
      r"\byour (strength|dexterity|constitution|intelligence|wisdom|charisma) score (becomes?|is) \d+|score increases? by")
for _a in _ABILITIES:
    _rule(f"abil:{_a}", f"uses {_a}", (_a,), rf"\b{_a}\b")

# defences
for _d in _DAMAGE_TYPES:
    _rule(f"resist:{_d}", f"resistance to {_d} damage", (_d,),
          rf"resistance to (all )?[^.;]{{0,40}}\b{_d}\b|resist[^.;]{{0,10}}[^.;]{{0,40}}\b{_d}\b damage|\b{_d}\b[^.;]{{0,20}}resistance")
    _rule(f"immune:{_d}", f"immunity to {_d} damage", (_d,),
          rf"immun(e|ity) to [^.;]{{0,40}}\b{_d}\b|\b{_d}\b[^.;]{{0,20}}immun")
    _rule(f"dmg:{_d}", f"deals {_d} damage", (_d,), rf"\b\d+d\d+\b[^.;]{{0,24}}\b{_d}\b damage|\b{_d}\b damage")
_rule("resist_all", "resistance to all damage", ("resistance",), r"resistance to (all|any) damage|resistance to damage from")
_rule("ac_bonus", "bonus to Armor Class", ("ac", "armor class"),
      r"(\+\d+|bonus of \d+|increase|add)[^.;]{0,30}(\bAC\b|armor class)|(\bAC\b|armor class)[^.;]{0,30}(\+\d+|increase)|bonus to (your )?(AC|armor class)")
_rule("ac_set", "sets Armor Class", ("ac", "armor class"),
      r"(base )?(AC|armor class) (equals?|is|becomes?) \d+|armor class (equals?|is) \d+ \+")
_rule("temp_hp", "grants temporary hit points", ("temporary hit point",), r"temporary hit points?")
_rule("heal", "restores hit points", ("hit point",),
      r"(regains?|restores?|heals?|recover)[^.;]{0,40}hit points?|hit points? (back|equal)")
_rule("hp_max", "raises hit point maximum", ("hit point maximum",), r"hit point maximum")
_rule("death", "stops dying / drop to 0", ("0 hit point", "1 hit point", "unconscious"),
      r"drop(s|ped)? to 0 hit points|instead drop to 1 hit point|fall unconscious")
_rule("revive", "brings back the dead", ("life", "resurrect", "revive"),
      r"\b(return|bring)s? [^.;]{0,40}to life|\bresurrect|\brevive")
_rule("evasion", "evades area damage", ("evasion", "half damage"),
      r"\bevasion\b|take no damage if you succeed|half damage if you fail")
_rule("save_bonus", "bonus to saving throws", ("saving throw",),
      r"(\+\d+|add|bonus)[^.;]{0,30}saving throws?|saving throws?[^.;]{0,30}\+\d+")
_rule("save_auto", "succeeds on saving throws", ("succeed",),
      r"automatically succeed[^.;]{0,30}(saving throw|save)|succeed on the saving throw")
_rule("magic_res", "magic resistance", ("magic",),
      r"advantage on saving throws against (spells|magical effects)|magic resistance")

# conditions
for _c in _CONDITIONS:
    _rule(f"cond:{_c}", f"{_c} condition", (_c,), rf"\b{_c}\b")
    _rule(f"condimm:{_c}", f"immune to {_c}", (_c,), rf"(immun(e|ity)|can'?t be|cannot be)[^.;]{{0,30}}\b{_c}\b")

# offence
_rule("extra_attack", "extra attacks", ("attack",),
      r"\bextra attack\b|attack twice|make (two|three|four) attacks|additional attack")
_rule("bonus_attack", "bonus-action attack", ("bonus action",),
      r"bonus action[^.;]{0,60}(make|attack)|(make|attack)[^.;]{0,60}as a bonus action")
_rule("sneak", "extra damage once per turn", ("once", "sneak"),
      r"once (on|per) (each of )?your turn[^.;]{0,100}\b\d+d\d+|extra \d+d\d+[^.;]{0,40}once per turn|\bsneak attack\b")
_rule("weapon_bonus", "bonus to attack and damage", ("bonus to",),
      r"\+\d+ bonus to (attack|damage)|bonus to attack rolls and damage")
_rule("dmg_dice", "extra damage dice", ("damage", "extra", "additional"),
      r"(extra|additional|bonus|deals?)[^.;]{0,30}\b\d+d\d+\b")
_rule("aoe", "area of effect", ("-foot", "each creature"),
      r"\b\d+-foot[- ](radius|cone|line|cube|sphere|emanation|cylinder)\b|each creature (in|within)")
_rule("save_dc", "forces a saving throw", ("saving throw", "dc"),
      r"\b(DC \d+|spell save DC|save DC|saving throw)\b[^.;]{0,50}\b(or|must|takes?|fail)")
_rule("push", "moves creatures", ("push", "pull", "prone", "slide"),
      r"push(ed)?[^.;]{0,30}feet|pull(ed)?[^.;]{0,30}feet|knocks?[^.;]{0,20}prone|slide")
_rule("opportunity", "opportunity attacks", ("opportunity",), r"opportunity attacks?")

# movement and senses
_rule("speed_bonus", "increases speed", ("speed",),
      r"(speed|walking speed)[^.;]{0,40}(increases?|by \d+ feet|\+\d+)|\+\d+ feet[^.;]{0,20}speed")
_rule("fly", "flight", ("fly", "flight", "hover"), r"\bfly(ing)? speed\b|\bfly\b[^.;]{0,15}\d+ feet|\bflight\b|\bhover\b")
_rule("climb", "climbing", ("climb",), r"climb(ing)? speed|climb \d+")
_rule("swim", "swimming", ("swim", "breathe water"), r"swim(ming)? speed|swim \d+|breathe water")
_rule("burrow", "burrowing", ("burrow",), r"burrow(ing)? speed|burrow \d+")
_rule("teleport", "teleportation", ("teleport", "misty step", "blink", "reappear"),
      r"\bteleport|\bmisty step|\bblink\b|disappear[^.;]{0,30}reappear")
_rule("phase", "moves through creatures or objects", ("move through", "incorporeal", "pass through"),
      r"move through[^.;]{0,30}(creature|object|wall)|incorporeal|pass through")
for _s in _SENSES:
    _rule(f"sense:{_s}", _s, (_s,), rf"\b{_s}\b")
_rule("see_invisible", "sees invisible creatures", ("invisible",), r"see invisible|detect invisible")
_rule("invisible", "invisibility", ("invisib",), r"\binvisible\b|\binvisibility\b")
_rule("stealth", "hiding and stealth", ("hide", "hidden", "stealth"), r"\bhide\b|\bhidden\b|stealth")
_rule("telepathy", "telepathy", ("telepath",), r"\btelepath")
_rule("language", "languages", ("language",), r"\blanguages?\b")

# action economy and resources
_rule("bonus_action", "uses a bonus action", ("bonus action",), r"\bbonus action\b")
_rule("reaction", "uses a reaction", ("reaction",),
      r"\bas a reaction\b|\breaction\b[^.;]{0,20}(which you take|when)|\bwhich you take when\b")
_rule("free_action", "takes no action", ("action",),
      r"(no|without using an?) action|doesn'?t require an action|free action")
_rule("short_rest", "recharges on a short rest", ("short",), r"short rest|short or long rest")
_rule("long_rest", "recharges on a long rest", ("long rest", "finish a rest"), r"long rest|finish a rest")
_rule("dawn", "recharges at dawn", ("dawn", "sunrise"), r"\bat dawn\b|\bdawn\b|sunrise")
_rule("pb_uses", "proficiency-bonus uses", ("proficiency bonus",),
      r"(a number of times equal to|number of times equal to) your proficiency bonus|proficiency bonus (times|uses)")
_rule("charges", "uses charges", ("charge",), r"\bcharges?\b")
_rule("once_per", "limited uses", ("once", "times", "per day", "/day", "per long", "per short"),
      r"\bonce (per|a|each|between)\b|\b\d+ times? (per|a) (day|rest)\b|\bper (day|long rest|short rest)\b|\b\d/day\b")
_rule("recharge", "recharges", ("recharge",), r"\brecharge\b")
_rule("attunement", "requires attunement", ("attunement",), r"requires? attunement")
_rule("concentration", "requires concentration", ("concentration",), r"\bconcentration\b")
_rule("spell_cast", "casts a spell", ("cast", "spell"),
      r"\bcast(s|ing)?\b[^.;]{0,50}\bspell\b|you can cast\b|without (expending|using)[^.;]{0,20}spell slot")
_rule("spell_slots", "spell slots", ("spell slot",), r"spell slot")
_rule("cantrip", "gives a cantrip", ("cantrip",), r"\bcantrips?\b")
_rule("spell_dc", "spell attack / DC", ("spell",), r"spell (attack|save|casting)|spellcasting (ability|focus)")
_rule("exhaustion", "exhaustion levels", ("exhaustion",), r"level of exhaustion|levels of exhaustion|exhaustion level")
_rule("concentration_adv", "protects concentration", ("concentration",),
      r"concentration[^.;]{0,50}(advantage|automatically)|advantage[^.;]{0,50}concentration")
_rule("summon", "summons a creature", ("summon", "conjure", "create", "familiar", "companion"),
      r"\bsummon|\bconjure|\bcreate[s]? an? [^.;]{0,20}(servant|spirit|creature|construct)|\bfamiliar\b|\bcompanion\b")
_rule("shape", "changes shape", ("wild shape", "polymorph", "shapechange", "transform"),
      r"\bwild shape\b|\bpolymorph|\bshapechange|\btransform")
_rule("light", "sheds light", ("light", "darkness"), r"bright light|dim light|\bdarkness\b|\bsheds? light\b")
_rule("poison_cure", "ends poison or disease", ("disease", "poison"), r"disease|neutralize poison|cure[^.;]{0,20}poison")
_rule("breath", "breath weapon", ("breath", "exhale"), r"\bbreath weapon\b|exhale")
_rule("carry", "carrying capacity", ("carrying capacity", "lift"), r"carrying capacity|push, drag, or lift|lift")
_rule("crafting", "crafting and tools", ("tool", "craft"), r"\btool proficiency\b|artisan'?s tools|\bcrafting\b|\bcraft\b")
_rule("social", "social influence", ("charm", "compelled", "suggestion", "influence", "persuad", "deceiv"),
      r"charm(ed)? person|compelled|\bsuggestion\b|\binfluence\b|\bpersuad|\bdeceiv")
_rule("gold", "gold and money", ("gp", "gold"), r"\b\d+ ?(gp|gold)\b|\bgold pieces?\b")
_rule("languages_read", "reads minds or lies", ("zone of truth", "thoughts", "lying"),
      r"zone of truth|read (its|their|the) surface thoughts|know if [^.;]{0,20}lying")
_rule("flaw", "has a drawback", ("curse", "sentient", "unless you", "at the cost"),
      r"\bcurse[ds]?\b|\bsentient\b|\bunless you\b|\bat the cost\b")

# tags produced by too many unrelated texts to say "the same effect" on their own; they only count with another tag
_WEAK_TAGS = {"bonus_action", "reaction", "long_rest", "short_rest", "once_per", "charges", "attunement", "dmg_dice",
              "proficiency", "pb_scaling", "spell_cast", "spell_slots", "concentration", "aoe", "language",
              "save_dc", "adv", "dis", "recharge", "free_action", "cantrip", "spell_dc", "heal", "gold", "light",
              "flaw", "pb_uses", "dawn", "stealth"} | {f"abil:{a}" for a in _ABILITIES}


def mechanics(text: str) -> Dict[str, str]:
    """{tag: label} for every rules effect the text expresses."""
    out: Dict[str, str] = {}
    t = plain(text)
    if not t:
        return out
    low = t.lower()
    for tag, label, needs, pattern in _RULES:
        if tag in out:
            continue
        for n in needs:
            if n in low:
                break
        else:
            continue
        if pattern.search(low):
            out[tag] = label
    # a 'skill:' or 'abil:' tag on its own is only a mention; keep it, it is weak
    return out


def tag_is_weak(tag: str) -> bool:
    return tag in _WEAK_TAGS or tag.startswith("abil:")


# --------------------------------------------------------------------------- entries

@dataclass
class Entry:
    """One comparable piece of content."""
    id: int
    family: str                      # key of FAMILIES
    title: str                       # "Reliable Talent"
    owner: str                       # the object that holds it: "Rogue", or the same as ``title`` for a whole object
    category: str                    # object-link category of the owner: "class", "magic_item", ...
    text: str                        # plain text
    detail: str = ""                 # "Rogue - level 7", "Rare wondrous item", "CR 5 Dragon"
    legacy: bool = False
    custom: bool = False
    official: bool = True            # tagged official (the shipped books); homebrew and imports are not
    source: str = ""
    section: str = ""                # a rules section / feature title inside the owner, to scroll to
    terms: Counter = field(default_factory=Counter, repr=False)
    tags: Dict[str, str] = field(default_factory=dict, repr=False)

    @property
    def target(self) -> str:
        """Name to open the owning object (``Page#Section`` for rules)."""
        return f"{self.owner}#{self.section}" if self.category == "rule" and self.section else self.owner

    def label(self) -> str:
        if self.owner and self.owner.lower() != self.title.lower():
            return f"{self.title} ({self.owner})"
        return self.title


@dataclass
class Match:
    """An entry that resembles the draft, and why."""
    entry: Entry
    score: float                     # 0-100
    shared_terms: List[str] = field(default_factory=list)
    shared_tags: List[str] = field(default_factory=list)       # labels
    snippet: str = ""
    matched_unit: str = ""           # which part of the draft it resembles (a feature title)
    spans: List[Tuple[int, int]] = field(default_factory=list)  # highlight ranges in snippet


@dataclass
class Unit:
    """A part of the draft that is compared on its own: the description, or one feature."""
    title: str
    text: str


def _entry_terms(entry: Entry) -> None:
    counts = Counter(words(entry.text))
    for w in words(entry.title):
        counts[w] += 2           # the name says what it is
    entry.terms = counts
    entry.tags = mechanics(entry.text)


# --------------------------------------------------------------------------- collecting entries

def _spell_entries(spell_manager) -> Iterable[dict]:
    if spell_manager is None:
        return
    for sp in spell_manager.spells:
        level = "Cantrip" if sp.level == 0 else f"Level {sp.level} spell"
        yield dict(family="spells", title=sp.name, owner=sp.name, category="spell",
                   text=sp.description or "", legacy=getattr(sp, "is_legacy", False),
                   custom=not getattr(sp, "is_official", True), official=bool(getattr(sp, "is_official", True)),
                   source=sp.source or "",
                   detail=f"{level} · {', '.join(sp.get_class_names()) or 'no class'}")


def _feat_entries() -> Iterable[dict]:
    from feat import get_feat_manager
    for f in get_feat_manager().feats:
        detail = f.type or "Feat"
        if f.has_prereq and f.prereq:
            detail += f" · needs {f.prereq}"
        yield dict(family="feats", title=f.name, owner=f.name, category="feat", text=f.description or "",
                   legacy=f.is_legacy, custom=f.is_custom, official=bool(f.is_official) and not f.is_custom,
                   source=f.source or "", detail=detail)


def _class_entries() -> Iterable[dict]:
    from character_class import get_class_manager
    for c in get_class_manager().classes:
        legacy = bool(getattr(c, "is_legacy", False))
        custom = bool(getattr(c, "is_custom", False))
        for level in sorted(c.levels):
            for ab in c.levels[level].abilities:
                if ab.is_subclass_feature or not (ab.description or "").strip():
                    continue
                yield dict(family="class_features", title=ab.title, owner=c.name, category="class",
                           text=ab.description, legacy=legacy, custom=custom, official=not custom,
                           source=c.source or "",
                           detail=f"{c.name} · level {level}")
        for s in c.subclasses:
            for feat in s.features:
                if not (feat.description or "").strip():
                    continue
                yield dict(family="class_features", title=feat.title, owner=s.name, category="subclass",
                           text=feat.description, legacy=bool(getattr(s, "is_legacy", False)),
                           custom=bool(getattr(s, "is_custom", False)), official=not getattr(s, "is_custom", False),
                           source=s.source or "",
                           detail=f"{c.name} · {s.name} · level {feat.level}")


def _lineage_entries() -> Iterable[dict]:
    from lineage import get_lineage_manager
    for l in get_lineage_manager().lineages:
        base = dict(owner=l.name, category="lineage", legacy=l.is_legacy, custom=l.is_custom,
                    official=bool(l.is_official) and not l.is_custom, source=l.source or "")
        for t in l.traits:
            if (t.description or "").strip():
                yield dict(base, family="lineages", title=t.name, text=t.description,
                           detail=f"{l.name} trait · {l.creature_type}".strip(" ·"))
        if (l.description or "").strip():
            yield dict(base, family="lineages", title=l.name, text=l.description,
                       detail=f"Lineage · {l.size} {l.creature_type}".strip())


def _background_entries() -> Iterable[dict]:
    from background import get_background_manager
    for b in get_background_manager().backgrounds:
        base = dict(owner=b.name, category="background", legacy=b.is_legacy, custom=b.is_custom,
                    official=bool(b.is_official) and not b.is_custom, source=b.source or "")
        for ft in b.features:
            if (ft.description or "").strip():
                yield dict(base, family="backgrounds", title=ft.name, text=ft.description,
                           detail=f"{b.name} feature")
        if (b.description or "").strip():
            yield dict(base, family="backgrounds", title=b.name, text=b.description, detail="Background")


def _property_text(item) -> str:
    return "\n".join(f"{p.get('name', '')}: {p.get('description', '')}" for p in (item.properties or [])
                     if isinstance(p, dict))


def _magic_item_entries() -> Iterable[dict]:
    from magic_item import get_magic_item_manager
    for i in get_magic_item_manager().items:
        text = (i.description or "") + "\n" + _property_text(i)
        yield dict(family="magic_items", title=i.name, owner=i.name, category="magic_item", text=text,
                   custom=i.is_custom, official=bool(i.is_official) and not i.is_custom, source=i.source or "",
                   detail=f"{i.rarity.value} {i.type}".strip() + (" · attunement" if i.requires_attunement else ""))


def _equipment_entries() -> Iterable[dict]:
    from equipment import get_equipment_manager
    for i in get_equipment_manager().items:
        text = (i.description or "") + "\n" + _property_text(i)
        if text.strip():
            yield dict(family="equipment", title=i.name, owner=i.name, category="equipment", text=text,
                       custom=i.is_custom, official=bool(i.is_official) and not i.is_custom, source=i.source or "",
                       detail=i.type or "Equipment")


_MONSTER_GROUPS = (("traits", "Trait"), ("actions", "Action"), ("bonus_actions", "Bonus action"),
                   ("reactions", "Reaction"), ("legendary_actions", "Legendary action"),
                   ("lair_actions", "Lair action"))


def _monster_entries() -> Iterable[dict]:
    from monster import get_monster_manager
    for m in get_monster_manager().browsable:
        base = dict(family="monsters", owner=m.name, category="monster", custom=m.is_custom,
                    official=bool(m.is_official) and not m.is_custom, source=m.source or "")
        for attr, kind in _MONSTER_GROUPS:
            for ft in getattr(m, attr, None) or []:
                if (ft.description or "").strip():
                    yield dict(base, title=ft.name, text=strip_attack_formula(ft.description),
                               detail=f"{m.name} · {kind} · CR {m.challenge_rating}")
        if (m.description or "").strip():
            yield dict(base, title=m.name, text=m.description, detail=f"Monster · CR {m.challenge_rating} {m.creature_type}")


def _rule_entries() -> Iterable[dict]:
    from rules import get_rules_manager
    for page in get_rules_manager().pages:
        base = dict(family="rules", owner=page.name, category="rule", custom=page.is_custom,
                    official=bool(page.is_official) and not page.is_custom, source=page.source or "")
        for sec in page.sections:
            text = (sec.text or "").strip()
            if not text:
                continue
            title = sec.title or page.name
            yield dict(base, title=title, text=text, section=sec.title if sec.level else "",
                       detail=f"Rules · {page.name}" if sec.title else f"Rules · {page.category or page.name}")


class HomebrewIndex:
    """Every comparable entry of every collection, searchable by similarity."""

    def __init__(self):
        self.entries: List[Entry] = []
        self._postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)       # word -> [(entry id, count)]
        self._tag_postings: Dict[str, List[int]] = defaultdict(list)
        self._idf: Dict[str, float] = {}
        self._tag_idf: Dict[str, float] = {}
        self._weight: List[float] = []                                              # idf weight of each entry
        self._signature: tuple = ()
        self.ready = False

    # ---- building

    @staticmethod
    def signature(spell_manager=None) -> tuple:
        """Cheap fingerprint of the collections: changes when content is added, removed or edited."""
        sig = []
        try:
            from feat import get_feat_manager
            from lineage import get_lineage_manager
            from background import get_background_manager
            from character_class import get_class_manager
            from magic_item import get_magic_item_manager
            from equipment import get_equipment_manager
            from monster import get_monster_manager
            from rules import get_rules_manager

            def fp(items, text=lambda i: getattr(i, "description", "")):
                custom = [i for i in items if getattr(i, "is_custom", False)]
                return (len(items), len(custom), sum(len(text(i) or "") for i in custom))

            sig.append(fp(get_feat_manager().feats))
            sig.append(fp(get_lineage_manager().lineages,
                          lambda l: (l.description or "") + "".join(t.description for t in l.traits)))
            sig.append(fp(get_background_manager().backgrounds,
                          lambda b: (b.description or "") + "".join(f.description for f in b.features)))
            classes = get_class_manager().classes
            sig.append(fp(classes, lambda c: sum(len(a.description) for lv in c.levels.values() for a in lv.abilities)
                          + sum(len(f.description) for s in c.subclasses for f in s.features)))
            sig.append(fp(get_magic_item_manager().items))
            sig.append(fp(get_equipment_manager().items))
            sig.append(fp(get_monster_manager().monsters,
                          lambda m: sum(len(f.description) for g in (m.traits, m.actions, m.bonus_actions, m.reactions,
                                                                     m.legendary_actions) for f in g)))
            sig.append(fp(get_rules_manager().pages))
        except Exception:
            pass
        if spell_manager is not None:
            spells = spell_manager.spells
            custom = [s for s in spells if not getattr(s, "is_official", True)]
            sig.append((len(spells), len(custom), sum(len(s.description or "") for s in custom)))
        return tuple(sig)

    def is_stale(self, spell_manager=None) -> bool:
        return not self.ready or self._signature != self.signature(spell_manager)

    def build(self, spell_manager=None, progress: Optional[Callable[[str], None]] = None) -> "HomebrewIndex":
        """(Re)build from the managers. Takes about a second; safe to call from a worker thread."""
        signature = self.signature(spell_manager)
        collectors: List[Tuple[str, Callable[[], Iterable[dict]]]] = [
            ("spells", lambda: _spell_entries(spell_manager)), ("feats", _feat_entries),
            ("class features", _class_entries), ("lineages", _lineage_entries),
            ("backgrounds", _background_entries), ("magic items", _magic_item_entries),
            ("equipment", _equipment_entries), ("monsters", _monster_entries), ("rules", _rule_entries)]
        entries: List[Entry] = []
        for name, collect in collectors:
            if progress:
                progress(f"Indexing {name}...")
            try:
                for raw in collect():
                    text = plain(drop_tables(raw.pop("text", "")))
                    if len(text) < 12:
                        continue
                    entry = Entry(id=len(entries), text=text, **raw)
                    _entry_terms(entry)
                    entries.append(entry)
            except Exception as e:                                 # a broken collection must not hide the others
                print(f"Homebrew index: could not read {name}: {e}")
        self._finish(entries)
        self._signature = signature
        return self

    def _finish(self, entries: List[Entry]) -> None:
        postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        tag_postings: Dict[str, List[int]] = defaultdict(list)
        for e in entries:
            for w, c in e.terms.items():
                postings[w].append((e.id, c))
            for t in e.tags:
                tag_postings[t].append(e.id)
        n = max(1, len(entries))
        self._idf = {w: math.log(1 + n / (1 + len(p))) for w, p in postings.items()}
        self._tag_idf = {t: math.log(1 + n / (1 + len(p))) for t, p in tag_postings.items()}
        self.entries = entries
        self._postings = postings
        self._tag_postings = tag_postings
        self._weight = [sum(self._term_weight(w, c) for w, c in e.terms.items()) for e in entries]
        self.ready = True

    def _tag_weight(self, tag: str) -> float:
        """How much sharing a mechanic says: rare ones count far more than common ones, and a generic one ("uses a
        bonus action") or a mere mention of a skill counts for little."""
        base = self._tag_idf.get(tag, 1.0) ** 2
        if tag_is_weak(tag):
            return base * 0.12
        if tag.startswith("skill:"):
            return base * 0.45
        return base

    def _term_weight(self, word: str, count: int) -> float:
        idf = self._idf.get(word)
        if idf is None:
            idf = math.log(1 + len(self.entries))            # a word nobody else uses is as telling as it gets
        if word in _BOOST_WORDS or word.isdigit() is False and re.fullmatch(r"\d*d\d+", word):
            idf = max(idf, 3.0)
        if word.isdigit():
            idf *= 0.5                                      # numbers matter, but only next to other words
        return idf * (1 + math.log(count))

    # ---- searching

    def stats(self) -> Dict[str, int]:
        counts: Counter = Counter(e.family for e in self.entries)
        return dict(counts)

    def find_title(self, query: str, families: Optional[Iterable[str]] = None, limit: int = 20) -> List[Entry]:
        """Entries whose title (or owner) matches ``query``, best first - for picking something to open."""
        q = (query or "").strip().lower()
        if not q:
            return []
        wanted = set(families) if families else None
        scored = []
        for e in self.entries:
            if wanted and e.family not in wanted:
                continue
            score = _title_score(q, e.title.lower())
            if score is None and e.owner.lower() != e.title.lower():
                s2 = _title_score(q, e.owner.lower())
                score = None if s2 is None else s2 + 3
            if score is not None:
                scored.append((score, len(e.title), e.title.lower(), e))
        scored.sort(key=lambda r: r[:3])
        return [r[3] for r in scored[:limit]]

    def similar(self, text: str, *, title: str = "", families: Optional[Iterable[str]] = None,
                exclude: Optional[Callable[[Entry], bool]] = None, limit: int = 12,
                min_score: float = 14.0, include_legacy: bool = True,
                matched_unit: str = "", min_words: int = 1, hide_exact: bool = False,
                include_unofficial: bool = True) -> List[Match]:
        """The entries most like ``text`` (a draft's description, or one of its features).

        ``min_words``: an entry needs at least this many words in common with ``text`` (numbers and filler words do
        not count). ``hide_exact``: leave out an entry whose text is word for word ``text``.
        ``include_unofficial``: also compare with content that is not tagged official."""
        if not self.ready:
            return []
        body = plain(text)
        body_words = {w for w in words(body) if not w.isdigit()}
        exact_key = _exact_key(body) if hide_exact else ""
        q_terms = Counter(words(body))
        for w in words(title):
            q_terms[w] += 1
        q_tags = mechanics(body)
        if not q_terms and not q_tags:
            return []
        q_weight = {w: self._term_weight(w, c) for w, c in q_terms.items()}
        total_q = sum(q_weight.values()) or 1.0
        wanted = set(families) if families else None

        shared: Dict[int, float] = defaultdict(float)
        shared_words: Dict[int, List[Tuple[float, str]]] = defaultdict(list)
        for w, qw in q_weight.items():
            for eid, c in self._postings.get(w, ()):
                ew = self._term_weight(w, c)
                got = min(qw, ew)
                shared[eid] += got
                shared_words[eid].append((got, w))

        tag_hits: Dict[int, List[str]] = defaultdict(list)
        core_q = [t for t in q_tags if not tag_is_weak(t) and not t.startswith("skill:")]
        for t in q_tags:
            for eid in self._tag_postings.get(t, ()):
                tag_hits[eid].append(t)

        candidates = set(shared) | {eid for eid, ts in tag_hits.items() if any(not tag_is_weak(t) for t in ts)}
        q_tag_total = sum(self._tag_weight(t) for t in q_tags) or 1.0
        out: List[Match] = []
        for eid in candidates:
            e = self.entries[eid]
            if wanted and e.family not in wanted:
                continue
            if e.legacy and not include_legacy:
                continue
            if exclude is not None and exclude(e):
                continue
            if not include_unofficial and not e.official:
                continue
            if min_words > 1 and len({w for _g, w in shared_words.get(eid, ()) if w in body_words}) < min_words:
                continue
            if exact_key and _exact_key(e.text) == exact_key:
                continue
            ew = self._weight[eid] or 1.0
            sh = shared.get(eid, 0.0)
            coverage = sh / total_q                          # how much of the draft this entry says
            precision = sh / ew                              # how much of the entry the draft says
            words_score = coverage * (0.45 + 0.55 * min(1.0, precision * 2.2))
            tags = tag_hits.get(eid, [])
            tag_score = 0.0
            if tags:
                tag_score = sum(self._tag_weight(t) for t in tags) / q_tag_total
            score = 100.0 * (0.58 * words_score + 0.42 * min(1.0, tag_score) * (0.45 + 0.55 * min(1.0, coverage * 3)))
            if core_q and any(t in e.tags for t in core_q):
                score *= 1.15
            if score < min_score:
                continue
            ranked = sorted(shared_words.get(eid, ()), reverse=True)
            terms = [w for _g, w in ranked if not w.isdigit()][:8]
            labels = [q_tags[t] for t in sorted(tags, key=lambda t: (tag_is_weak(t), -self._tag_weight(t)))
                      if not tag_is_weak(t) or len(tags) > 1][:5]
            out.append(Match(entry=e, score=min(99.0, score), shared_terms=terms, shared_tags=labels,
                             matched_unit=matched_unit))
        out.sort(key=lambda m: (-m.score, len(m.entry.text)))
        out = _dedupe(out)[:limit]
        for m in out:
            m.snippet, m.spans = snippet_for(m.entry.text, set(m.shared_terms))
        return out

    def similar_to_draft(self, units: Sequence[Unit], *, families: Optional[Iterable[str]] = None,
                         exclude: Optional[Callable[[Entry], bool]] = None, limit: int = 12,
                         include_legacy: bool = True, min_score: float = 14.0, min_words: int = 1,
                         hide_exact: bool = False, include_unofficial: bool = True,
                         max_matches: int = 0) -> "DraftMatches":
        """Run every part of a draft against the index and merge: an entry keeps its best score and remembers which
        part of the draft it resembled.

        ``max_matches`` (0 = no limit): a part of the draft that matches *more* than this many entries is standard
        wording ("make a Wisdom saving throw"), not an idea someone already had, so it is left out and listed in
        ``.omitted`` as (part, how many matches it had)."""
        best: Dict[int, Match] = {}
        omitted: List[Tuple[str, int]] = []
        for unit in units:
            if len(plain(unit.text)) < 12:
                continue
            found = self.similar(unit.text, title=unit.title, families=families, exclude=exclude,
                                 limit=(max_matches + 1) if max_matches else limit * 2,
                                 include_legacy=include_legacy, min_score=min_score,
                                 matched_unit=unit.title if len(units) > 1 else "", min_words=min_words,
                                 hide_exact=hide_exact, include_unofficial=include_unofficial)
            if max_matches and len(found) > max_matches:
                omitted.append((unit.title or "the description", len(found)))
                continue
            for m in found:
                cur = best.get(m.entry.id)
                if cur is None or m.score > cur.score:
                    best[m.entry.id] = m
        merged = sorted(best.values(), key=lambda m: -m.score)
        result = DraftMatches(_dedupe(merged)[:limit])
        result.omitted = omitted
        return result


class DraftMatches(list):
    """The matches for a draft (a list of :class:`Match`), plus the parts that were left out as standard wording."""

    def __init__(self, items=()):
        super().__init__(items)
        self.omitted: List[Tuple[str, int]] = []


def _exact_key(text: str) -> str:
    """The words of a text, so two texts that differ only in case, spacing or punctuation compare equal."""
    return " ".join(re.findall(r"[a-z0-9]+", plain(text).lower()))


def _title_score(q: str, name: str) -> Optional[int]:
    if q == name:
        return 0
    if name.startswith(q):
        return 1
    if re.search(rf"\b{re.escape(q)}\b", name):
        return 2
    if q in name:
        return 3
    if len(q) > 3 and q.endswith("s"):
        return _title_score(q[:-1], name)
    toks = [t for t in re.findall(r"[a-z0-9']+", q) if t]
    if len(toks) > 1 and all(t in name for t in toks):
        return 4
    return None


def _dedupe(matches: List[Match]) -> List[Match]:
    """Drop near-copies (the same text under two names - a 2014 and a 2024 version, an SRD reprint)."""
    seen: List[Match] = []
    for m in matches:
        dup = False
        for o in seen:
            if o.entry.title.lower() == m.entry.title.lower() and o.entry.family == m.entry.family \
                    and _same_text(o.entry.text, m.entry.text):
                dup = True
                break
        if not dup:
            seen.append(m)
    return seen


def _same_text(a: str, b: str) -> bool:
    if a == b:
        return True
    wa, wb = set(words(a)), set(words(b))
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) > 0.9


def snippet_for(text: str, terms: Set[str], size: int = 230) -> Tuple[str, List[Tuple[int, int]]]:
    """A short excerpt of ``text`` around the sentences that use most of ``terms``, and where those words are."""
    flat = re.sub(r"\s+", " ", text).strip()
    if not flat:
        return "", []
    sentences = re.split(r"(?<=[.!?])\s+", flat)
    scores = [len(set(words(s)) & terms) for s in sentences]
    first = max(range(len(sentences)), key=lambda i: (scores[i], -i))
    lo = hi = first
    length = len(sentences[first])
    while length < size * 0.7:                         # add the neighbours that mention shared words first
        options = []
        if lo > 0:
            options.append((scores[lo - 1], lo - 1))
        if hi < len(sentences) - 1:
            options.append((scores[hi + 1], hi + 1))
        if not options:
            break
        _score, pick = max(options, key=lambda o: (o[0], -abs(o[1] - first)))
        if length + len(sentences[pick]) + 1 > size * 1.25:
            break
        if pick < lo:
            lo = pick
        else:
            hi = pick
        length += len(sentences[pick]) + 1
    excerpt = " ".join(sentences[lo:hi + 1])
    if len(excerpt) > size:
        centre = 0
        for m in re.finditer(r"[A-Za-z0-9']+", excerpt):
            ws = words(m.group(0))
            if ws and ws[0] in terms:
                centre = m.start()
                break
        a = max(0, centre - size // 3)
        cut = excerpt[a:a + size].rstrip()
        excerpt = ("…" if a > 0 else "") + cut + ("…" if a + size < len(excerpt) else "")
    spans = []
    for m in re.finditer(r"[A-Za-z0-9']+", excerpt):
        ws = words(m.group(0))
        if ws and ws[0] in terms:
            spans.append((m.start(), m.end()))
    return excerpt, spans


# --------------------------------------------------------------------------- shared instance

_INDEX: Optional[HomebrewIndex] = None


def get_index() -> HomebrewIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = HomebrewIndex()
    return _INDEX


def reset_index() -> None:
    """Forget the shared index (tests; a very large import)."""
    global _INDEX
    _INDEX = None
