"""Helpers for 2014 (legacy) content that shares its name with 2024 content.

Every content table keeps names unique, so a 2014 entry whose name is already taken by a
2024 entry is stored as "Name (Legacy)" (Fireball -> "Fireball (Legacy)", Fighter ->
"Fighter (Legacy)"). Several 2014 versions of one species share a name, so those carry the
book too: "Orc (Legacy: MPMM)", "Orc (Legacy: VGM)". The Legacy content setting ("Show
Unupdated" in particular) pairs an entry with its 2024 counterpart by *name*, so the pairing
has to look past that suffix.
"""

import re
from typing import Callable, Iterable, List, TypeVar

LEGACY_SUFFIX = " (Legacy)"
_SUFFIX_RE = re.compile(r"\s*\(Legacy(?::[^)]*)?\)\s*$", re.I)

T = TypeVar("T")


def strip_legacy_suffix(name: str) -> str:
    """The name without a trailing " (Legacy)" / " (Legacy: MPMM)" ("Fighter (Legacy)" -> "Fighter")."""
    return _SUFFIX_RE.sub("", (name or "").strip())


def legacy_pair_key(name: str) -> str:
    """Key shared by an entry and its "(Legacy)" twin.

    Case and punctuation are ignored, because the two editions don't always
    punctuate a name alike ("Power Word: Kill" vs "Power Word Kill").
    """
    return re.sub(r"[^a-z0-9]", "", strip_legacy_suffix(name).lower())


def apply_legacy_filter(items: Iterable[T], legacy_filter: str,
                        name: Callable[[T], str] = lambda i: i.name,
                        is_legacy: Callable[[T], bool] = lambda i: i.is_legacy) -> List[T]:
    """Filter ``items`` by the Legacy content setting.

    show_all        every item
    no_legacy       only non-legacy items
    legacy_only     only legacy items
    show_unupdated  non-legacy items, plus legacy items that have no non-legacy
                    counterpart (same name, ignoring a "(Legacy)" suffix)
    """
    items = list(items)
    if legacy_filter == "no_legacy":
        return [i for i in items if not is_legacy(i)]
    if legacy_filter == "legacy_only":
        return [i for i in items if is_legacy(i)]
    if legacy_filter == "show_unupdated":
        current = {legacy_pair_key(name(i)) for i in items if not is_legacy(i)}
        return [i for i in items if not is_legacy(i) or legacy_pair_key(name(i)) not in current]
    return items
