"""
Feat data structures and manager for D&D 5e Spellbook Application.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Feat type constants
FEAT_TYPE_GENERAL = ""  # Normal level-up feats
FEAT_TYPE_ORIGIN = "Origin"
FEAT_TYPE_FIGHTING_STYLE = "Fighting Style"
FEAT_TYPE_ELDRITCH_INVOCATION = "Eldritch Invocation"
FEAT_TYPE_DRAGONMARK = "Dragonmark"
FEAT_TYPE_EPIC_BOON = "Epic Boon"

# Default feat types - users can add more
DEFAULT_FEAT_TYPES = [
    FEAT_TYPE_GENERAL,
    FEAT_TYPE_ORIGIN,
    FEAT_TYPE_FIGHTING_STYLE,
    FEAT_TYPE_ELDRITCH_INVOCATION,
    FEAT_TYPE_DRAGONMARK,
    FEAT_TYPE_EPIC_BOON,
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
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
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


def get_data_path(filename: str) -> str:
    """Get the path to a data file, handling PyInstaller bundling."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


class FeatManager:
    """Manages the feat database using SQLite."""
    
    _instance: Optional['FeatManager'] = None
    
    def __init__(self):
        self._db = None
        self._feats_cache: Optional[List[Feat]] = None
    
    @classmethod
    def get_instance(cls) -> 'FeatManager':
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
    def feats(self) -> List[Feat]:
        """Get all feats, using cache if available."""
        if self._feats_cache is None:
            self._reload_cache()
        return self._feats_cache or []
    
    def _reload_cache(self):
        """Reload feats from database into cache."""
        self._feats_cache = []
        for feat_dict in self.db.get_all_feats():
            self._feats_cache.append(self._dict_to_feat(feat_dict))
    
    def _invalidate_cache(self):
        """Invalidate the cache to force reload on next access."""
        self._feats_cache = None
    
    def _dict_to_feat(self, data: dict) -> Feat:
        """Convert database dict to Feat object."""
        return Feat(
            name=data.get('name', ''),
            type=data.get('type', ''),
            is_spellcasting=data.get('is_spellcasting', False),
            spell_lists=data.get('spell_lists', []),
            spells_num=data.get('spells_num', {}),
            has_prereq=data.get('has_prereq', False),
            prereq=data.get('prereq', ''),
            set_spells=data.get('set_spells', []),
            description=data.get('description', ''),
            source=data.get('source', ''),
            is_official=data.get('is_official', True),
            is_custom=data.get('is_custom', False),
            is_legacy=data.get('is_legacy', False)
        )
    
    def _feat_to_dict(self, feat: Feat) -> dict:
        """Convert Feat object to dict for database."""
        return {
            'name': feat.name,
            'type': feat.type,
            'is_spellcasting': feat.is_spellcasting,
            'spell_lists': feat.spell_lists,
            'spells_num': {str(k): v for k, v in feat.spells_num.items()},
            'has_prereq': feat.has_prereq,
            'prereq': feat.prereq,
            'set_spells': feat.set_spells,
            'description': feat.description,
            'source': feat.source,
            'is_official': feat.is_official,
            'is_custom': feat.is_custom,
            'is_legacy': feat.is_legacy
        }
    
    def load(self) -> bool:
        """Reload feats from database (for compatibility)."""
        self._invalidate_cache()
        return True
    
    def save(self) -> bool:
        """No-op for database backend (saves happen immediately)."""
        return True
    
    def get_feat(self, name: str) -> Optional[Feat]:
        """Get a feat by name."""
        data = self.db.get_feat_by_name(name)
        if data:
            return self._dict_to_feat(data)
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
        feat_dict = self._feat_to_dict(feat)
        
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
        
        feat_dict = self._feat_to_dict(updated_feat)
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
            if query_lower in feat.name.lower() or query_lower in feat.description.lower():
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
            data = {
                "feats": [f.to_dict() for f in feats]
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return len(feats)
        except Exception as e:
            print(f"Error exporting feats to JSON: {e}")
            return 0
    
    def import_from_json(self, file_path: str) -> int:
        """Import feats from a JSON file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            feats_data = data.get("feats", [])
            imported_count = 0
            
            for feat_dict in feats_data:
                try:
                    feat = Feat.from_dict(feat_dict)
                    # Imported feats are always custom and unofficial
                    feat.is_custom = True
                    feat.is_official = False
                    self.add_feat(feat)
                    imported_count += 1
                except Exception as e:
                    print(f"Error importing feat: {e}")
                    continue
            
            return imported_count
        except Exception as e:
            print(f"Error importing from JSON: {e}")
            return 0


def get_feat_manager() -> FeatManager:
    """Get the singleton FeatManager instance."""
    return FeatManager.get_instance()
