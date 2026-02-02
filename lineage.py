"""
Lineage data structures and manager for D&D 5e Spellbook Application.
Represents character races/species with their traits.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class LineageTrait:
    """A trait belonging to a lineage (similar to a mini-feat)."""
    name: str
    description: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'LineageTrait':
        """Create LineageTrait from dictionary."""
        return cls(
            name=data.get("name", "Unknown Trait"),
            description=data.get("description", "")
        )


@dataclass
class Lineage:
    """Represents a D&D 5e Lineage (race/species)."""
    name: str
    description: str = ""
    creature_type: str = "Humanoid"
    size: str = "Medium"  # Can be "Small", "Medium", "Small or Medium", etc.
    speed: int = 30
    traits: List[LineageTrait] = field(default_factory=list)
    source: str = ""
    is_official: bool = True
    is_custom: bool = False
    is_legacy: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "creature_type": self.creature_type,
            "size": self.size,
            "speed": self.speed,
            "traits": [t.to_dict() for t in self.traits],
            "source": self.source,
            "is_official": self.is_official,
            "is_custom": self.is_custom,
            "is_legacy": self.is_legacy
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Lineage':
        """Create Lineage from dictionary."""
        traits = []
        if "traits" in data:
            traits = [LineageTrait.from_dict(t) for t in data["traits"]]
        
        return cls(
            name=data.get("name", "Unknown"),
            description=data.get("description", ""),
            creature_type=data.get("creature_type", "Humanoid"),
            size=data.get("size", "Medium"),
            speed=data.get("speed", 30),
            traits=traits,
            source=data.get("source", ""),
            is_official=data.get("is_official", True),
            is_custom=data.get("is_custom", False),
            is_legacy=data.get("is_legacy", False)
        )
    
    def get_traits_summary(self) -> str:
        """Get a summary of trait names."""
        if not self.traits:
            return "No special traits"
        return ", ".join(t.name for t in self.traits)


class LineageManager:
    """Manages the collection of lineages."""
    
    _instance = None
    
    def __init__(self):
        self.lineages: List[Lineage] = []
        self._data_file = self._get_data_file_path()
        self.load_lineages()
    
    def _get_data_file_path(self) -> str:
        """Get the path to the lineages data file (user-writable location)."""
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, 'lineages.json')
    
    def _get_bundled_data_path(self) -> str:
        """Get the path to bundled lineages data (for PyInstaller)."""
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, 'lineages.json')
        return self._data_file
    
    def load_lineages(self):
        """Load lineages from JSON file."""
        self.lineages = []
        
        # First try user file (for modifications)
        if os.path.exists(self._data_file):
            try:
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for lineage_data in data.get("lineages", []):
                        self.lineages.append(Lineage.from_dict(lineage_data))
                # Sort by name
                self.lineages.sort(key=lambda l: l.name)
                return
            except Exception as e:
                print(f"Error loading lineages from user path: {e}")
        
        # Try bundled path (for PyInstaller)
        bundled_path = self._get_bundled_data_path()
        if bundled_path != self._data_file and os.path.exists(bundled_path):
            try:
                with open(bundled_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for lineage_data in data.get("lineages", []):
                        self.lineages.append(Lineage.from_dict(lineage_data))
                # Save to user location so modifications can be preserved
                self.save_lineages()
                return
            except Exception as e:
                print(f"Error loading lineages from bundled path: {e}")
        
        # Sort by name
        self.lineages.sort(key=lambda l: l.name)
    
    def save_lineages(self):
        """Save all lineages to JSON file."""
        data = {
            "lineages": [l.to_dict() for l in self.lineages]
        }
        
        try:
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving lineages: {e}")
            raise
    
    def add_lineage(self, lineage: Lineage) -> bool:
        """Add a new lineage or update existing one."""
        # Check for existing lineage with same name
        for i, existing in enumerate(self.lineages):
            if existing.name.lower() == lineage.name.lower():
                self.lineages[i] = lineage
                self.save_lineages()
                return True
        
        self.lineages.append(lineage)
        self.lineages.sort(key=lambda l: l.name)
        self.save_lineages()
        return True
    
    def remove_lineage(self, lineage_name: str) -> bool:
        """Remove a lineage by name. Only custom lineages can be removed."""
        for i, lineage in enumerate(self.lineages):
            if lineage.name.lower() == lineage_name.lower():
                if lineage.is_official and not lineage.is_custom:
                    return False  # Cannot remove official lineages
                del self.lineages[i]
                self.save_lineages()
                return True
        return False
    
    def get_lineage(self, name: str) -> Optional[Lineage]:
        """Get a lineage by name."""
        for lineage in self.lineages:
            if lineage.name.lower() == name.lower():
                return lineage
        return None
    
    def get_all_creature_types(self) -> List[str]:
        """Get all unique creature types from lineages."""
        types = set()
        for lineage in self.lineages:
            if lineage.creature_type:
                types.add(lineage.creature_type)
        return sorted(types)
    
    def get_all_sizes(self) -> List[str]:
        """Get all unique sizes from lineages."""
        sizes = set()
        for lineage in self.lineages:
            if lineage.size:
                sizes.add(lineage.size)
        return sorted(sizes)
    
    def get_all_sources(self) -> List[str]:
        """Get all unique sources from lineages."""
        sources = set()
        for lineage in self.lineages:
            if lineage.source:
                sources.add(lineage.source)
        return sorted(sources)
    
    def get_unofficial_lineages(self) -> List[Lineage]:
        """Get all non-official lineages."""
        return [l for l in self.lineages if not l.is_official]
    
    def get_unofficial_sources(self) -> List[str]:
        """Get sources that have unofficial content."""
        sources = set()
        for lineage in self.lineages:
            if not lineage.is_official and lineage.source:
                sources.add(lineage.source)
        return sorted(sources)
    
    def export_to_json(self, file_path: str, lineages: Optional[List[Lineage]] = None) -> int:
        """Export lineages to a JSON file."""
        if lineages is None:
            lineages = self.get_unofficial_lineages()
        
        data = {
            "lineages": [l.to_dict() for l in lineages]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return len(lineages)
    
    def import_from_json(self, file_path: str) -> int:
        """Import lineages from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        count = 0
        lineages_data = data.get("lineages", [])
        
        for lineage_data in lineages_data:
            lineage = Lineage.from_dict(lineage_data)
            # Mark as custom/non-official when importing
            lineage.is_custom = True
            lineage.is_official = False
            self.add_lineage(lineage)
            count += 1
        
        return count
    
    def get_lineage_names(self) -> List[str]:
        """Get list of all lineage names."""
        return [l.name for l in self.lineages]


# Singleton instance
_lineage_manager: Optional[LineageManager] = None


def get_lineage_manager() -> LineageManager:
    """Get the global LineageManager instance."""
    global _lineage_manager
    if _lineage_manager is None:
        _lineage_manager = LineageManager()
    return _lineage_manager
