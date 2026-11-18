"""
Sorting the collection pages (Spells, Feats, Lineages, Backgrounds, Magic Items, Equipment, Monsters and the
person's own collections).

Each page offers "Name" plus the properties that make sense for it (a spell's level, an item's rarity or price,
a monster's CR ...) and every field the person added to the collection ("Your fields"). The order can be
ascending or descending, and the choice is remembered per collection in the settings (``collection_sort``).

Headless (no Tk): the page's sort control is ``ui/sort_control.py``.

Rules every sort follows:
- Entries with no value for the chosen property (an item with no price, a blank field) always come last,
  whichever way round the sort is.
- Entries with the same value stay in name order (A to Z), also when the sort is descending.
- Values of different kinds (a number field someone typed text into) never break the sort: numbers come
  before text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

NAME = "Name"
SOURCE = "Source"

# A sort key that means "this entry has no value": sorted last.
MISSING = None


@dataclass(frozen=True)
class SortField:
    """One choice in a page's Sort drop-down: its label and how to read the value from an entry."""
    label: str
    value: Callable[[Any], Any]       # entry -> number / text / bool / None (= no value)


def _name(entry) -> str:
    return (getattr(entry, "name", "") or "").lower()


def _key(value) -> Optional[Tuple[int, Any]]:
    """A comparable key for ``value``: numbers before text; None for "no value"."""
    if value is None:
        return None
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (0, float(value))
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value)
    text = str(value).strip().lower()
    return (1, text) if text else None


def sort_entries(entries: Iterable, field: Optional[SortField], descending: bool = False) -> list:
    """``entries`` sorted by ``field`` (None = by name). See the module notes for the rules."""
    by_name = sorted(entries, key=_name)
    if field is None or field.label == NAME:
        return by_name[::-1] if descending else by_name
    keyed, missing = [], []
    for entry in by_name:
        try:
            k = _key(field.value(entry))
        except Exception:          # a broken entry sorts as "no value" rather than breaking the page
            k = None
        (missing if k is None else keyed).append((k, entry))
    # Python's sort is stable, also with reverse=True, so equal values keep their A-Z order
    keyed.sort(key=lambda pair: pair[0], reverse=descending)
    return [e for _, e in keyed] + [e for _, e in missing]


def find(fields: Sequence[SortField], label: str) -> Optional[SortField]:
    for f in fields:
        if f.label == label:
            return f
    return None


# ---------------------------------------------------------------- the remembered choice

# The order a page starts in before anything is chosen (otherwise by name). Spells were always listed by level.
DEFAULTS = {"spells": "Level"}


def default_for(collection: str) -> str:
    return DEFAULTS.get(collection, NAME)


def remembered(settings, collection: str) -> Tuple[str, bool]:
    """(label, descending) last chosen for ``collection``; the page's default, ascending, if none."""
    saved = getattr(settings, "collection_sort", None)
    entry = saved.get(collection) if isinstance(saved, dict) else None
    if isinstance(entry, (list, tuple)) and len(entry) == 2 and isinstance(entry[0], str):
        return entry[0], bool(entry[1])
    return default_for(collection), False


def remember(settings_manager, collection: str, label: str, descending: bool):
    """Store the choice (saved quietly: no settings listeners run, nothing else on screen changes)."""
    settings = settings_manager.settings
    saved = dict(getattr(settings, "collection_sort", None) or {})
    if label == default_for(collection) and not descending:
        saved.pop(collection, None)
    else:
        saved[collection] = [label, bool(descending)]
    settings.collection_sort = saved
    settings_manager.save()


# ---------------------------------------------------------------- values of the person's own fields

def field_sort_value(fdef, value):
    """The sort value of a value of an added field (custom_collections.FieldDef)."""
    if fdef.is_empty(value):
        return None
    if fdef.kind == "choice" and fdef.choices:
        # In the order the choices were set up in (e.g. Minor, Major, Legendary), not alphabetically
        lowered = [c.lower() for c in fdef.choices]
        text = str(value).strip().lower()
        return lowered.index(text) if text in lowered else str(value)
    if fdef.kind == "number":
        return value
    if fdef.kind == "yes_no":
        return bool(value)
    return value


def own_field_sorts(fields: Iterable, taken: Iterable[str], values_of: Callable[[Any, str], Any]) -> List[SortField]:
    """A SortField per added field (long text excepted). ``values_of(entry, field_id)`` reads the raw value.

    A field whose label is already a choice on the page gets " (your field)" after it."""
    taken = {t.lower() for t in taken}
    out = []
    for f in fields:
        if f.kind == "long_text":
            continue
        label = f.label if f.label.lower() not in taken else f"{f.label} (your field)"
        taken.add(label.lower())
        out.append(SortField(label, lambda e, f=f: field_sort_value(f, values_of(e, f.id))))
    return out


def builtin_field_sorts(collection: str, taken: Iterable[str], manager=None) -> List[SortField]:
    """Sort choices for the fields added to a built-in collection ("spells", "feats", ...)."""
    if manager is None:
        import custom_collections as cc
        manager = cc.get_collection_manager()
    fields = manager.builtin_fields(collection)
    if not fields:
        return []
    cache: Dict[str, dict] = {}

    def values_of(entry, field_id):
        if "v" not in cache:
            cache["v"] = manager.extra_values_by_name(collection)
        return cache["v"].get(_name(entry), {}).get(field_id)

    return own_field_sorts(fields, taken, values_of)


# ---------------------------------------------------------------- each built-in page's own choices

SIZE_ORDER = ["tiny", "small", "medium", "large", "huge", "gargantuan"]


def size_rank(size: str):
    """"Small or Medium" ranks as Small; unknown sizes sort as text after the known ones."""
    text = (size or "").strip().lower()
    if not text:
        return None
    for i, s in enumerate(SIZE_ORDER):
        if text.startswith(s):
            return i
    return text


def _source(e):
    return getattr(e, "source", "") or None


def spell_sorts() -> List[SortField]:
    from spell import range_value_to_feet
    return [
        SortField(NAME, _name),
        SortField("Level", lambda s: s.level),
        SortField("Casting Time", lambda s: s.casting_time),
        SortField("Range", lambda s: range_value_to_feet(s.range_value)),
        SortField("Duration", lambda s: s.duration),
        SortField("Concentration", lambda s: bool(s.concentration)),
        SortField("Ritual", lambda s: bool(s.ritual)),
        SortField(SOURCE, _source),
    ]


def feat_sorts() -> List[SortField]:
    return [
        SortField(NAME, _name),
        SortField("Type", lambda f: f.type or "General"),
        SortField("Prerequisite", lambda f: bool(f.has_prereq)),
        SortField("Spellcasting", lambda f: bool(f.is_spellcasting)),
        SortField(SOURCE, _source),
    ]


def lineage_sorts() -> List[SortField]:
    return [
        SortField(NAME, _name),
        SortField("Size", lambda l: size_rank(l.size)),
        SortField("Creature Type", lambda l: l.creature_type),
        SortField("Speed", lambda l: l.speed),
        SortField(SOURCE, _source),
    ]


def background_sorts() -> List[SortField]:
    return [SortField(NAME, _name), SortField(SOURCE, _source)]


def _price(item):
    from equipment import parse_cost_to_copper
    return parse_cost_to_copper(item.cost)


def _weight(item):
    return item.weight if item.weight else None


def magic_item_sorts() -> List[SortField]:
    from magic_item import Rarity
    order = [r for r in Rarity]       # Common ... Artifact, then Varies
    return [
        SortField(NAME, _name),
        SortField("Rarity", lambda i: order.index(i.rarity) if i.rarity in order else None),
        SortField("Type", lambda i: i.type),
        SortField("Attunement", lambda i: bool(i.requires_attunement)),
        SortField("Price", _price),
        SortField("Weight", _weight),
        SortField(SOURCE, _source),
    ]


def equipment_sorts() -> List[SortField]:
    return [
        SortField(NAME, _name),
        SortField("Type", lambda i: i.type),
        SortField("Price", _price),
        SortField("Weight", _weight),
        SortField(SOURCE, _source),
    ]


def monster_sorts() -> List[SortField]:
    from monster import cr_to_number
    return [
        SortField(NAME, _name),
        SortField("CR", lambda m: cr_to_number(m.challenge_rating)),
        SortField("HP", lambda m: m.hp),
        SortField("AC", lambda m: m.ac),
        SortField("Size", lambda m: size_rank(m.size)),
        SortField("Type", lambda m: m.creature_type),
        SortField("Alignment", lambda m: m.alignment),
        SortField(SOURCE, _source),
    ]


BUILTIN_SORTS = {
    "spells": spell_sorts,
    "feats": feat_sorts,
    "lineages": lineage_sorts,
    "backgrounds": background_sorts,
    "magic_items": magic_item_sorts,
    "equipment": equipment_sorts,
    "monsters": monster_sorts,
}


def sorts_for(collection: str, manager=None) -> List[SortField]:
    """Every sort choice of a built-in collection page: its own, then the person's added fields."""
    own = BUILTIN_SORTS[collection]()
    return own + builtin_field_sorts(collection, [f.label for f in own], manager)


def custom_collection_sorts(ctype) -> List[SortField]:
    """Sort choices for one of the person's own collections (custom_collections.CollectionType)."""
    own = [SortField(NAME, _name), SortField(SOURCE, _source)]
    return own + own_field_sorts(ctype.fields, [f.label for f in own],
                                 lambda e, fid: (getattr(e, "values", None) or {}).get(fid))
