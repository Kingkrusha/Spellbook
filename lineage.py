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
    """Manages the collection of lineages using SQLite database."""
    
    _instance = None
    
    def __init__(self):
        self._db = None
        self._lineages_cache: Optional[List[Lineage]] = None
    
    @property
    def db(self):
        """Get database instance, initializing if needed."""
        if self._db is None:
            from database import SpellDatabase
            self._db = SpellDatabase()
            self._db.initialize()
        return self._db
    
    @property
    def lineages(self) -> List[Lineage]:
        """Get all lineages, using cache if available."""
        if self._lineages_cache is None:
            self._reload_cache()
        return self._lineages_cache or []
    
    def _reload_cache(self):
        """Reload lineages from database into cache."""
        self._lineages_cache = []
        for lin_dict in self.db.get_all_lineages():
            self._lineages_cache.append(self._dict_to_lineage(lin_dict))
    
    def _invalidate_cache(self):
        """Invalidate the cache to force reload on next access."""
        self._lineages_cache = None
    
    def _dict_to_lineage(self, data: dict) -> Lineage:
        """Convert database dict to Lineage object."""
        traits = []
        for t in data.get('traits', []):
            traits.append(LineageTrait(name=t.get('name', ''), description=t.get('description', '')))
        
        return Lineage(
            name=data.get('name', ''),
            description=data.get('description', ''),
            creature_type=data.get('creature_type', 'Humanoid'),
            size=data.get('size', 'Medium'),
            speed=data.get('speed', 30),
            traits=traits,
            source=data.get('source', ''),
            is_official=data.get('is_official', True),
            is_custom=data.get('is_custom', False),
            is_legacy=data.get('is_legacy', False)
        )
    
    def _lineage_to_dict(self, lineage: Lineage) -> dict:
        """Convert Lineage object to dict for database."""
        return {
            'name': lineage.name,
            'description': lineage.description,
            'creature_type': lineage.creature_type,
            'size': lineage.size,
            'speed': lineage.speed,
            'traits': [{'name': t.name, 'description': t.description} for t in lineage.traits],
            'source': lineage.source,
            'is_official': lineage.is_official,
            'is_custom': lineage.is_custom,
            'is_legacy': lineage.is_legacy
        }
    
    def load_lineages(self):
        """Reload lineages from database (for compatibility)."""
        self._invalidate_cache()
    
    def save_lineages(self):
        """No-op for database backend (saves happen immediately)."""
        pass
    
    def add_lineage(self, lineage: Lineage) -> bool:
        """Add a new lineage or update existing one."""
        existing = self.db.get_lineage_by_name(lineage.name)
        lineage_dict = self._lineage_to_dict(lineage)
        
        if existing:
            self.db.update_lineage(existing['id'], lineage_dict)
        else:
            self.db.insert_lineage(lineage_dict)
        
        self._invalidate_cache()
        return True
    
    def remove_lineage(self, lineage_name: str) -> bool:
        """Remove a lineage by name. Only custom lineages can be removed."""
        existing = self.db.get_lineage_by_name(lineage_name)
        if not existing:
            return False
        
        if existing.get('is_official') and not existing.get('is_custom'):
            return False  # Cannot remove official lineages
        
        result = self.db.delete_lineage(existing['id'])
        self._invalidate_cache()
        return result
    
    def get_lineage(self, name: str) -> Optional[Lineage]:
        """Get a lineage by name."""
        data = self.db.get_lineage_by_name(name)
        if data:
            return self._dict_to_lineage(data)
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
        return [l for l in self.lineages if not l.is_official or l.is_custom]
    
    def get_unofficial_sources(self) -> List[str]:
        """Get sources that have unofficial content."""
        sources = set()
        for lineage in self.lineages:
            if (not lineage.is_official or lineage.is_custom) and lineage.source:
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
