"""
Universal object linking.

A cross-content-type search index (spells, feats, lineages, backgrounds,
classes, subclasses, equipment, magic items) plus the markup helpers used to
embed and resolve links inside any description/notes text field.

Markup format stored in text: ``[[category:Name]]``, or ``[[category:Name|display]]``
when the visible word differs from the target's real name (e.g. the user typed
"axe" and linked it to "Battleaxe"). The pre-existing spell-only markup
``[[SpellName]]`` (no category) still parses - it's treated as ``spell``.

This module has no UI dependencies of its own; ``ui/object_link_widgets.py``
builds the popups/tooltips/text-widget behavior on top of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

# Category key -> human-readable label (used in tooltips, popups, Settings).
LINK_CATEGORIES: Dict[str, str] = {
    "spell": "Spells",
    "feat": "Feats",
    "lineage": "Lineages",
    "background": "Backgrounds",
    "class": "Classes",
    "subclass": "Subclasses",
    "equipment": "Equipment",
    "magic_item": "Magic Items",
}

# The AppSettings boolean that gates *suggesting* a category. Subclasses ride
# along with Classes rather than getting their own toggle.
_SETTING_ATTR: Dict[str, str] = {
    "spell": "link_suggest_spells",
    "feat": "link_suggest_feats",
    "lineage": "link_suggest_lineages",
    "background": "link_suggest_backgrounds",
    "class": "link_suggest_classes",
    "subclass": "link_suggest_classes",
    "equipment": "link_suggest_equipment",
    "magic_item": "link_suggest_magic_items",
}


@dataclass
class LinkTarget:
    """One linkable object. `fetch()` lazily returns the full domain object
    (Spell, Feat, Equipment, ...) for popup rendering."""
    category: str
    name: str
    subtitle: str = ""
    fetch: Optional[Callable[[], object]] = None

    @property
    def category_label(self) -> str:
        return LINK_CATEGORIES.get(self.category, self.category.replace("_", " ").title())

    def get_object(self):
        if self.fetch is None:
            return None
        try:
            return self.fetch()
        except Exception:
            return None


# --------------------------------------------------------------------------- #
# Per-category target collectors
# --------------------------------------------------------------------------- #

def _get_full_spell(name: str):
    from ui.rich_text_utils import RichTextRenderer
    return RichTextRenderer().get_spell(name)


def _spell_targets() -> List[LinkTarget]:
    from database import SpellDatabase
    db = SpellDatabase()
    db.initialize()
    targets = []
    for d in db.get_all_spells():
        name = d.get("name", "")
        if not name:
            continue
        level = d.get("level", 0)
        subtitle = "Cantrip" if level == 0 else f"Level {level} Spell"
        targets.append(LinkTarget("spell", name, subtitle, lambda n=name: _get_full_spell(n)))
    return targets


def _feat_targets() -> List[LinkTarget]:
    from feat import get_feat_manager
    return [LinkTarget("feat", f.name, f.type or "Feat", (lambda obj=f: obj))
            for f in get_feat_manager().feats]


def _lineage_targets() -> List[LinkTarget]:
    from lineage import get_lineage_manager
    return [LinkTarget("lineage", l.name, l.creature_type or "Lineage", (lambda obj=l: obj))
            for l in get_lineage_manager().lineages]


def _background_targets() -> List[LinkTarget]:
    from background import get_background_manager
    return [LinkTarget("background", b.name, "Background", (lambda obj=b: obj))
            for b in get_background_manager().backgrounds]


def _class_targets() -> List[LinkTarget]:
    from character_class import get_class_manager
    targets = []
    for c in get_class_manager().classes:
        targets.append(LinkTarget("class", c.name, f"Class ({c.hit_die} Hit Die)", (lambda obj=c: obj)))
        for s in c.subclasses:
            targets.append(LinkTarget("subclass", s.name, f"{c.name} Subclass", (lambda obj=s: obj)))
    return targets


def _equipment_targets() -> List[LinkTarget]:
    from equipment import get_equipment_manager
    return [LinkTarget("equipment", i.name, i.type or "Equipment", (lambda obj=i: obj))
            for i in get_equipment_manager().items]


def _magic_item_targets() -> List[LinkTarget]:
    from magic_item import get_magic_item_manager
    return [LinkTarget("magic_item", i.name, i.rarity.value, (lambda obj=i: obj))
            for i in get_magic_item_manager().items]


# Keyed by the Settings toggle's category (not every LINK_CATEGORIES key has
# its own collector - "subclass" rides along inside "class").
_COLLECTORS: Dict[str, Callable[[], List[LinkTarget]]] = {
    "spell": _spell_targets,
    "feat": _feat_targets,
    "lineage": _lineage_targets,
    "background": _background_targets,
    "class": _class_targets,
    "equipment": _equipment_targets,
    "magic_item": _magic_item_targets,
}


def get_link_targets(enabled_only: bool = True) -> List[LinkTarget]:
    """All linkable objects across every content type.

    With `enabled_only=True` (the default - used for as-you-type and
    right-click *suggestions*), a category disabled in Settings is skipped
    entirely. Pass False to resolve an existing link regardless of the
    current suggestion settings: a link someone already made should always
    still open, and "Unlink" needs to find it too.
    """
    settings = None
    if enabled_only:
        try:
            from settings import get_settings_manager
            settings = get_settings_manager().settings
        except Exception:
            settings = None

    targets: List[LinkTarget] = []
    for category, collector in _COLLECTORS.items():
        if settings is not None and not getattr(settings, _SETTING_ATTR[category], True):
            continue
        try:
            targets.extend(collector())
        except Exception:
            continue
    return targets


def find_target(category: str, name: str) -> Optional[LinkTarget]:
    """Resolve one specific (category, name) pair, e.g. to open or unlink an
    existing link. Always searches every category, ignoring Settings."""
    name_l = name.strip().lower()
    for t in get_link_targets(enabled_only=False):
        if t.category == category and t.name.lower() == name_l:
            return t
    return None


# --------------------------------------------------------------------------- #
# Matching / ranking
# --------------------------------------------------------------------------- #

def _score(query: str, name: str) -> Optional[int]:
    """Lower is better; None means "no match". Bands, best to worst:
    exact -> prefix -> whole word inside the name -> plain substring."""
    q = query.strip().lower()
    n = name.lower()
    if not q:
        return None
    if q == n:
        return 0
    if n.startswith(q):
        return 1
    if re.search(rf"\b{re.escape(q)}\b", n):
        return 2
    if q in n:
        return 3
    # Tolerate a simple trailing plural ("axes" -> matches "axe").
    if len(q) > 3 and q.endswith("s"):
        return _score(q[:-1], n)
    return None


def search_links(query: str, targets: List[LinkTarget], limit: Optional[int] = None) -> List[LinkTarget]:
    """Rank `targets` by how well their name matches `query`. Ties break by
    shorter name first, then alphabetically, so tighter matches surface first."""
    scored = []
    for t in targets:
        s = _score(query, t.name)
        if s is not None:
            scored.append((s, len(t.name), t.name.lower(), t))
    scored.sort(key=lambda row: row[:3])
    results = [row[3] for row in scored]
    return results[:limit] if limit else results


# --------------------------------------------------------------------------- #
# Markup
# --------------------------------------------------------------------------- #

LINK_MARKUP_RE = re.compile(r"\[\[([^\]]+)\]\]")


def parse_link_markup(inner: str):
    """Parse the inside of a ``[[...]]`` token into (category, name, display).

    Legacy spell links carry no category: ``[[Fireball]]`` -> ("spell",
    "Fireball", "Fireball"). Any link can carry a display override after a
    pipe: ``[[equipment:Battleaxe|axe]]`` -> ("equipment", "Battleaxe", "axe").
    """
    body = inner
    display = None
    if "|" in body:
        body, display = body.split("|", 1)
    category, name = "spell", body
    if ":" in body:
        maybe_cat, rest = body.split(":", 1)
        key = maybe_cat.strip().lower().replace(" ", "_")
        if key in LINK_CATEGORIES and rest.strip():
            category, name = key, rest
    name = name.strip()
    display = (display.strip() if display else "") or name
    return category, name, display


def format_link_markup(category: str, name: str, display: str) -> str:
    """Build the stored markup for a link, omitting the display override when
    it's identical to the target's real name."""
    name = name.strip()
    display = display.strip()
    body = f"{category}:{name}"
    if display and display.lower() != name.lower():
        return f"[[{body}|{display}]]"
    return f"[[{body}]]"
