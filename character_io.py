"""
Headless character import / export.

A character is two records joined by name: the spell list (``characters.json``,
:class:`character.CharacterSpellList`) and the sheet (``character_sheets.json``,
:class:`character_sheet.CharacterSheet`). This module builds and applies the
JSON bundle that carries both, with no dialogs, so the file Import/Export on
the Characters page and the LAN "send a character" feature share one code path
(the same split ``content_io`` made for homebrew content).

Bundle format (what "Char Export" has always written)::

    {"character_sheets": {"Name": {...sheet...}},
     "character_spell_lists": [{...spell list...}]}

A sheet may carry ``portrait_data`` (base64 image) so the portrait travels too.
Older files use a top-level ``sheets`` key instead of ``character_sheets``.

Importing never prompts. :func:`plan_import` tells the caller which names would
replace an existing character; the caller decides per name with a
:data:`ConflictPolicy` and passes the answers to :func:`apply_import`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

# What to do when an incoming character has the same name as one already here.
REPLACE = "replace"     # overwrite the existing character
RENAME = "rename"       # keep both: the incoming one is saved as "Name (2)"
SKIP = "skip"           # leave the existing character alone, drop the incoming one

POLICIES = (REPLACE, RENAME, SKIP)


class CharacterBundleError(ValueError):
    """The data is not a usable character bundle (message is user-readable)."""


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def build_export(names: Iterable[str], character_manager, sheet_manager) -> Tuple[dict, int, int]:
    """Bundle the named characters. Returns ``(data, spell_lists, sheets)``."""
    data: Dict[str, Any] = {"character_sheets": {}, "character_spell_lists": []}
    spell_lists = sheets = 0
    for name in names:
        char = character_manager.get_character(name)
        if char:
            data["character_spell_lists"].append(char.to_dict())
            spell_lists += 1
        sheet = sheet_manager.get_sheet(name)
        if sheet:
            sheet_dict = sheet.to_dict()
            if sheet.portrait:
                import portraits
                embedded = portraits.encode_portrait(sheet.portrait)
                if embedded:
                    sheet_dict["portrait_data"] = embedded   # the portrait travels with the sheet
            data["character_sheets"][name] = sheet_dict
            sheets += 1
    return data, spell_lists, sheets


# ---------------------------------------------------------------------------
# Reading a bundle
# ---------------------------------------------------------------------------

@dataclass
class CharacterBundle:
    sheets: Dict[str, dict] = field(default_factory=dict)       # name -> sheet dict
    spell_lists: List[dict] = field(default_factory=list)       # CharacterSpellList dicts

    @property
    def names(self) -> List[str]:
        """Every character name in the bundle (sheets first), without duplicates."""
        seen, out = set(), []
        for n in list(self.sheets) + [c.get("name") for c in self.spell_lists if isinstance(c, dict)]:
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out


def parse_bundle(data: Any) -> CharacterBundle:
    """Validate raw JSON data. Raises :class:`CharacterBundleError`."""
    if not isinstance(data, dict):
        raise CharacterBundleError("This file does not contain character sheet data.")
    if "character_sheets" not in data and "sheets" not in data:
        raise CharacterBundleError("This file does not contain character sheet data.")
    sheets = data.get("character_sheets", data.get("sheets", {}))
    if not isinstance(sheets, dict):
        raise CharacterBundleError("The character sheets in this file are not in a recognised format.")
    lists = data.get("character_spell_lists", [])
    if not isinstance(lists, list):
        raise CharacterBundleError("The character spell lists in this file are not in a recognised format.")
    sheets = {str(n): s for n, s in sheets.items() if isinstance(s, dict)}
    lists = [c for c in lists if isinstance(c, dict) and c.get("name")]
    return CharacterBundle(sheets=sheets, spell_lists=lists)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@dataclass
class ImportPlan:
    """What an import would run into, worked out without changing anything."""
    names: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)          # names already present here


@dataclass
class CharacterImportReport:
    sheets: int = 0
    spell_lists: int = 0
    warnings: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    renamed: Dict[str, str] = field(default_factory=dict)       # incoming name -> name it was saved as

    @property
    def imported(self) -> int:
        return self.sheets + self.spell_lists


def _exists(name: str, character_manager, sheet_manager) -> bool:
    return character_manager.get_character(name) is not None or sheet_manager.get_sheet(name) is not None


def plan_import(bundle: CharacterBundle, character_manager, sheet_manager) -> ImportPlan:
    names = bundle.names
    return ImportPlan(names=names,
                      conflicts=sorted(n for n in names if _exists(n, character_manager, sheet_manager)))


def unique_name(name: str, character_manager, sheet_manager) -> str:
    """``name`` if free, else ``"name (2)"``, ``"name (3)"`` ... (case-insensitive)."""
    if not _exists(name, character_manager, sheet_manager):
        return name
    n = 2
    while _exists(f"{name} ({n})", character_manager, sheet_manager):
        n += 1
    return f"{name} ({n})"


def apply_import(bundle: CharacterBundle, character_manager, sheet_manager, spell_manager=None,
                 policies: Optional[Dict[str, str]] = None,
                 default_policy: str = REPLACE) -> CharacterImportReport:
    """Write the bundle's characters. Never raises for a bad record: it is reported.

    ``policies`` maps an incoming name to :data:`REPLACE`, :data:`RENAME` or
    :data:`SKIP`; names without an entry use ``default_policy``. The policy only
    matters when the name already exists here.
    """
    from character import CharacterSpellList
    from character_sheet import CharacterSheet
    import content_io

    policies = policies or {}
    report = CharacterImportReport()

    # Decide each name's fate once, so a sheet and its spell list always agree.
    target: Dict[str, Optional[str]] = {}          # incoming name -> saved-as name (None = skip)
    for name in bundle.names:
        if not _exists(name, character_manager, sheet_manager):
            target[name] = name
            continue
        policy = policies.get(name, default_policy)
        if policy == SKIP:
            target[name] = None
            report.skipped.append(name)
        elif policy == RENAME:
            new = unique_name(name, character_manager, sheet_manager)
            target[name] = new
            report.renamed[name] = new
        else:
            target[name] = name

    # Object links in a sheet ([[spell:Fireball]], ...) only open if that content is installed
    try:
        from object_links import get_link_targets
        known_links = {(t.category, t.name.lower()) for t in get_link_targets(enabled_only=False)}
    except Exception:
        known_links = None

    names_with_list = {c.get("name") for c in bundle.spell_lists}

    for name, sheet_data in bundle.sheets.items():
        saved_as = target.get(name)
        if saved_as is None:
            continue
        try:
            sheet = CharacterSheet.from_dict(sheet_data)
            sheet.character_name = saved_as
            import portraits
            if sheet_data.get("portrait_data"):
                sheet.portrait = portraits.decode_portrait(sheet_data["portrait_data"], saved_as)
            elif sheet.portrait and not portraits.portrait_path(sheet.portrait):
                sheet.portrait = ""                    # the file did not come along

            if not (character_manager.get_character(saved_as) is not None or name in names_with_list):
                report.warnings.append(f"'{name}': No matching character spell list found")
            if known_links is not None:
                missing = content_io.dangling_links(sheet_data, known_links)
                if missing:
                    report.warnings.append(f"'{name}': links to content that isn't installed: "
                                           f"{content_io.format_dangling(missing)}")
            sheet_manager.update_sheet(saved_as, sheet)
            report.sheets += 1
        except Exception as e:
            report.warnings.append(f"'{name}': Import error - {e}")

    for char_data in bundle.spell_lists:
        name = char_data.get("name")
        saved_as = target.get(name)
        if saved_as is None:
            continue
        try:
            char = CharacterSpellList.from_dict(char_data)
            char.name = saved_as

            from character_class import get_class_manager
            class_manager = get_class_manager()
            for cl in char.classes:
                class_name = (cl.get_class_name() if hasattr(cl, "get_class_name")
                              else (cl.character_class.value if hasattr(cl.character_class, "value")
                                    else str(cl.character_class)))
                if not class_manager.get_class(class_name):
                    report.warnings.append(f"'{char.name}': Class '{class_name}' not found in system")

            if spell_manager:
                for spell_name in char.known_spells + char.prepared_spells:
                    if not spell_manager._db.get_spell_by_name(spell_name):
                        report.warnings.append(f"'{char.name}': Spell '{spell_name}' not found")

            if character_manager.get_character(saved_as):
                character_manager.update_character(saved_as, char)
            else:
                character_manager.add_character(char)
            report.spell_lists += 1
        except Exception as e:
            report.warnings.append(f"Character spell list error: {e}")

    return report
