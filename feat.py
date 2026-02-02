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
        base_path = sys._MEIPASS
    else:
        # Running as script
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, filename)


class FeatManager:
    """Manages the feat database."""
    
    DEFAULT_FILE = "feats.json"
    _instance: Optional['FeatManager'] = None
    
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or self.DEFAULT_FILE
        self._feats: List[Feat] = []
        self._loaded = False
    
    @classmethod
    def get_instance(cls) -> 'FeatManager':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @property
    def feats(self) -> List[Feat]:
        """Get all feats, loading if necessary."""
        if not self._loaded:
            self.load()
        return self._feats
    
    def load(self) -> bool:
        """Load feats from file."""
        # First try user file path (for modifications)
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._feats = [Feat.from_dict(fd) for fd in data.get("feats", [])]
                    self._loaded = True
                    return True
            except Exception as e:
                print(f"Error loading feats from user path: {e}")
        
        # Try bundled path (for PyInstaller)
        bundled_path = get_data_path(self.DEFAULT_FILE)
        if bundled_path != self.file_path and os.path.exists(bundled_path):
            try:
                with open(bundled_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._feats = [Feat.from_dict(fd) for fd in data.get("feats", [])]
                    self._loaded = True
                    # Save to user path so modifications are preserved
                    self.save()
                    return True
            except Exception as e:
                print(f"Error loading feats from bundled path: {e}")
        
        # Initialize with defaults if no file exists
        self._initialize_default_feats()
        self._loaded = True
        self.save()
        return True
    
    def _initialize_default_feats(self):
        """Initialize with a basic set of default feats."""
        self._feats = [
            # This will be populated from feats.json
            # Adding a few examples as fallback
            Feat(
                name="Alert",
                type="",
                description="You gain a +5 bonus to initiative. You can't be surprised while you are conscious. Other creatures don't gain advantage on attack rolls against you as a result of being unseen by you.",
            ),
            Feat(
                name="Magic Initiate",
                type="",
                is_spellcasting=True,
                spell_lists=["Bard", "Cleric", "Druid", "Sorcerer", "Warlock", "Wizard"],
                spells_num={0: 2, 1: 1},
                description="Choose a class: bard, cleric, druid, sorcerer, warlock, or wizard. You learn two cantrips of your choice from that class's spell list. In addition, choose one 1st-level spell to learn from that same list. You can cast this spell at its lowest level once per long rest without expending a spell slot.",
            ),
        ]
    
    def save(self) -> bool:
        """Save feats to file."""
        try:
            data = {
                "feats": [feat.to_dict() for feat in self._feats]
            }
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving feats: {e}")
            return False
    
    def get_feat(self, name: str) -> Optional[Feat]:
        """Get a feat by name."""
        for feat in self.feats:
            if feat.name.lower() == name.lower():
                return feat
        return None
    
    def get_feats_by_type(self, feat_type: str) -> List[Feat]:
        """Get all feats of a specific type."""
        return [f for f in self.feats if f.type == feat_type]
    
    def get_spellcasting_feats(self) -> List[Feat]:
        """Get all feats that grant spellcasting."""
        return [f for f in self.feats if f.is_spellcasting]
    
    def add_feat(self, feat: Feat) -> bool:
        """Add a new feat."""
        if self.get_feat(feat.name):
            return False  # Already exists
        self._feats.append(feat)
        self.save()
        return True
    
    def update_feat(self, name: str, updated_feat: Feat) -> bool:
        """Update an existing feat."""
        for i, feat in enumerate(self._feats):
            if feat.name.lower() == name.lower():
                self._feats[i] = updated_feat
                self.save()
                return True
        return False
    
    def delete_feat(self, name: str) -> bool:
        """Delete a feat by name."""
        for i, feat in enumerate(self._feats):
            if feat.name.lower() == name.lower():
                if not feat.is_custom:
                    return False  # Can't delete official feats
                del self._feats[i]
                self.save()
                return True
        return False
    
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
            if not feat.is_official and feat.source:
                sources.add(feat.source)
        return sorted(sources)
    
    def get_unofficial_feats(self) -> List[Feat]:
        """Get all feats that are not official."""
        return [f for f in self.feats if not f.is_official]
    
    def export_to_json(self, file_path: str, feats: Optional[List[Feat]] = None) -> int:
        """
        Export feats to a JSON file.
        
        Args:
            file_path: Path to export to
            feats: List of feats to export (None = export all unofficial)
        
        Returns:
            Number of feats exported
        """
        if feats is None:
            # Default to unofficial feats only
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
        """
        Import feats from a JSON file.
        
        Args:
            file_path: Path to the JSON file
        
        Returns:
            Number of feats imported
        """
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
                    
                    # Add or update the feat
                    existing = self.get_feat(feat.name)
                    if existing:
                        self.update_feat(feat.name, feat)
                    else:
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
