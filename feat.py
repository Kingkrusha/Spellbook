"""
Feat data structures and manager for D&D 5e Spellbook Application.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from collection_manager import DbBackedManager


# Feat type constants
FEAT_TYPE_GENERAL = ""  # Normal level-up feats
FEAT_TYPE_ORIGIN = "Origin"
FEAT_TYPE_FIGHTING_STYLE = "Fighting Style"
FEAT_TYPE_ELDRITCH_INVOCATION = "Eldritch Invocation"
FEAT_TYPE_DRAGONMARK = "Dragonmark"
FEAT_TYPE_EPIC_BOON = "Epic Boon"
FEAT_TYPE_DARK_GIFT = "Dark Gift"
FEAT_TYPE_PLANAR_PACT = "Planar Pact"

# Default feat types - users can add more
DEFAULT_FEAT_TYPES = [
    FEAT_TYPE_GENERAL,
    FEAT_TYPE_ORIGIN,
    FEAT_TYPE_FIGHTING_STYLE,
    FEAT_TYPE_ELDRITCH_INVOCATION,
    FEAT_TYPE_DRAGONMARK,
    FEAT_TYPE_EPIC_BOON,
    FEAT_TYPE_DARK_GIFT,
    FEAT_TYPE_PLANAR_PACT,
]


@dataclass
class Feat:
    """Represents a D&D 5e Feat."""
    name: str
    type: str = ""  # Blank for normal feats, or Origin/Fighting Style/etc.
    is_spellcasting: bool = False
    spell_lists: List[str] = field(default_factory=list)  # Class names for spell selection
    spells_num: Dict[int, int] = field(default_factory=dict)  # {spell_level: count}
    has_prereq: bool = False
    prereq: str = ""
    set_spells: List[str] = field(default_factory=list)  # Specific spells granted
    description: str = ""
    source: str = ""  # Source book
    is_official: bool = True  # True for official content, False for homebrew
    is_custom: bool = False  # True if user-created
    is_legacy: bool = False  # True for 2014 (legacy) content
    roll_effects: List[dict] = field(default_factory=list)  # homebrew: what it does to the Dice Analyzer's rolls

    def plain_description(self) -> str:
        """Description with [[link]] markup replaced by its visible text (for searching)."""
        from object_link_sweep import strip_links
        return strip_links(self.description)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "name": self.name,
            "type": self.type,
            "is_spellcasting": self.is_spellcasting,
            "spell_lists": self.spell_lists,
            "spells_num": {str(k): v for k, v in self.spells_num.items()},  # JSON keys must be strings
            "has_prereq": self.has_prereq,
            "prereq": self.prereq,
            "set_spells": self.set_spells,
            "description": self.description,
            "source": self.source,
            "is_official": self.is_official,
            "is_custom": self.is_custom,
            "is_legacy": self.is_legacy,
        }
        if self.roll_effects:
            data["roll_effects"] = self.roll_effects
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Feat':
        """Create Feat from dictionary."""
        # Convert spells_num keys back to integers
        spells_num = {}
        if "spells_num" in data and data["spells_num"]:
            spells_num = {int(k): v for k, v in data["spells_num"].items()}
        
        return cls(
            name=data.get("name", "Unknown"),
            type=data.get("type", ""),
            is_spellcasting=data.get("is_spellcasting", False),
            spell_lists=data.get("spell_lists", []),
            spells_num=spells_num,
            has_prereq=data.get("has_prereq", False),
            prereq=data.get("prereq", ""),
            set_spells=data.get("set_spells", []),
            description=data.get("description", ""),
            source=data.get("source", ""),
            is_official=data.get("is_official", True),
            is_custom=data.get("is_custom", False),
            is_legacy=data.get("is_legacy", False),
            roll_effects=data.get("roll_effects", []) or [],
        )
    
    def get_type_display(self) -> str:
        """Get display string for feat type."""
        return self.type if self.type else "General"
    
    def get_spells_summary(self) -> str:
        """Get a summary of spells granted by this feat."""
        if not self.is_spellcasting:
            return ""
        
        if self.set_spells:
            return f"Grants: {', '.join(self.set_spells)}"
        
        if self.spells_num:
            parts = []
            for level, count in sorted(self.spells_num.items()):
                if level == 0:
                    parts.append(f"{count} cantrip{'s' if count > 1 else ''}")
                else:
                    ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(level, f"{level}th")
                    parts.append(f"{count} {ordinal}-level spell{'s' if count > 1 else ''}")
            
            lists = ", ".join(self.spell_lists) if self.spell_lists else "any"
            return f"Learn {', '.join(parts)} from {lists} list"
        
        return ""


class FeatManager(DbBackedManager):
    """Manages the feat database using SQLite."""
    
    _instance: Optional['FeatManager'] = None
    
    def _load_all(self) -> List[Feat]:
        return [Feat.from_dict(d) for d in self.db.get_all_feats()]
    
    @property
    def feats(self) -> List[Feat]:
        """Get all feats, using cache if available."""
        return self._cached()
    
    def get_feat(self, name: str) -> Optional[Feat]:
        """Get a feat by name."""
        data = self.db.get_feat_by_name(name)
        if data:
            return Feat.from_dict(data)
        return None
    
    def get_feats_by_type(self, feat_type: str) -> List[Feat]:
        """Get all feats of a specific type."""
        return [f for f in self.feats if f.type == feat_type]
    
    def get_spellcasting_feats(self) -> List[Feat]:
        """Get all feats that grant spellcasting."""
        return [f for f in self.feats if f.is_spellcasting]
    
    def add_feat(self, feat: Feat) -> bool:
        """Add a new feat or update existing."""
        existing = self.db.get_feat_by_name(feat.name)
        feat_dict = feat.to_dict()
        
        if existing:
            self.db.update_feat(existing['id'], feat_dict)
        else:
            self.db.insert_feat(feat_dict)
        
        self._invalidate_cache()
        return True
    
    def update_feat(self, name: str, updated_feat: Feat) -> bool:
        """Update an existing feat."""
        existing = self.db.get_feat_by_name(name)
        if not existing:
            return False
        
        feat_dict = updated_feat.to_dict()
        result = self.db.update_feat(existing['id'], feat_dict)
        self._invalidate_cache()
        return result
    
    def delete_feat(self, name: str) -> bool:
        """Delete a feat by name."""
        existing = self.db.get_feat_by_name(name)
        if not existing:
            return False
        
        if not existing.get('is_custom'):
            return False  # Can't delete official feats
        
        result = self.db.delete_feat(existing['id'])
        self._invalidate_cache()
        return result
    
    def search_feats(self, query: str, feat_type: Optional[str] = None) -> List[Feat]:
        """Search feats by name or description."""
        query_lower = query.lower()
        results = []
        
        for feat in self.feats:
            # Filter by type if specified
            if feat_type is not None and feat.type != feat_type:
                continue
            
            # Search in name and description
            if query_lower in feat.name.lower() or query_lower in feat.plain_description().lower():
                results.append(feat)
        
        return results
    
    def get_all_types(self) -> List[str]:
        """Get all unique feat types including custom ones."""
        types = set(DEFAULT_FEAT_TYPES)
        for feat in self.feats:
            if feat.type:
                types.add(feat.type)
        # Return sorted list with empty string (General) first
        sorted_types = sorted([t for t in types if t])
        return [""] + sorted_types
    
    def get_all_sources(self) -> List[str]:
        """Get all unique sources from feats."""
        sources = set()
        for feat in self.feats:
            if feat.source:
                sources.add(feat.source)
        return sorted(sources)
    
    def get_unofficial_sources(self) -> List[str]:
        """Get list of sources that have unofficial (non-official) feats."""
        sources = set()
        for feat in self.feats:
            if (not feat.is_official or feat.is_custom) and feat.source:
                sources.add(feat.source)
        return sorted(sources)
    
    def get_unofficial_feats(self) -> List[Feat]:
        """Get all feats that are not official."""
        return [f for f in self.feats if not f.is_official or f.is_custom]
    
    def export_to_json(self, file_path: str, feats: Optional[List[Feat]] = None) -> int:
        """Export feats to a JSON file."""
        if feats is None:
            feats = self.get_unofficial_feats()
        
        try:
            from atomic_io import atomic_write_json
            data = {
                "feats": [f.to_dict() for f in feats]
            }
            atomic_write_json(file_path, data)
            return len(feats)
        except Exception as e:
            print(f"Error exporting feats to JSON: {e}")
            return 0
    
    def import_from_json(self, file_path: str) -> int:
        """Import feats from a JSON file; returns how many were added or updated.

        Goes through content_io, so an entry whose name belongs to official content
        is skipped instead of overwritten.
        """
        import content_io

        try:
            report = content_io.import_file(file_path, kinds=["feats"], link_mentions=False)
        except Exception as e:
            print(f"Error importing feats from JSON: {e}")
            return 0
        return report.added["feats"] + report.updated["feats"]



def get_feat_manager() -> FeatManager:
    """Get the singleton FeatManager instance."""
    return FeatManager.get_instance()
