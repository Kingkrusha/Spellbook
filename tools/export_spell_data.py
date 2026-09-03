#!/usr/bin/env python3
"""Export the Spellbook spell database to a portable JSON file."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spell_manager import SpellManager


def build_spell_export(manager: SpellManager) -> dict[str, Any]:
    """Build a shareable spell export payload."""
    spells = manager.spells
    spells.sort(key=lambda spell: (spell.level, spell.name.lower()))

    return {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_app": "Spellbook",
        "source_database": "spellbook.db",
        "spell_count": len(spells),
        "spells": [
            {
                "name": spell.name,
                "level": spell.level,
                "casting_time": spell.casting_time,
                "ritual": bool(spell.ritual),
                "range_value": spell.range_value,
                "components": spell.components,
                "duration": spell.duration,
                "concentration": bool(spell.concentration),
                "description": spell.description,
                "source": spell.source,
                "classes": spell.get_class_names(),
                "tags": list(spell.tags),
                "is_modified": bool(spell.is_modified),
                "original_name": spell.original_name,
                "is_legacy": bool(spell.is_legacy),
                "is_official": bool(spell.is_official),
            }
            for spell in spells
        ],
    }


def main() -> None:
    db_path = ROOT / "spellbook.db"
    output_path = ROOT / "exports" / "spellbook_spells.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manager = SpellManager(str(db_path))
    if not manager.load_spells():
        raise SystemExit("Failed to load spells from the database.")

    export_data = build_spell_export(manager)
    output_path.write_text(
        json.dumps(export_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {export_data['spell_count']} spells to {output_path}")


if __name__ == "__main__":
    main()
