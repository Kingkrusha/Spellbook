"""
Background data structures and manager for D&D 5e Spellbook Application.
Represents character backgrounds with their features and proficiencies.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class BackgroundFeature:
    """A feature belonging to a background (similar to lineage traits)."""
    name: str
    description: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'BackgroundFeature':
        """Create BackgroundFeature from dictionary."""
        return cls(
            name=data.get("name", "Unknown Feature"),
            description=data.get("description", "")
        )


@dataclass
class Background:
    """Represents a D&D 5e Background."""
    # Required fields
    name: str
    source: str
    is_legacy: bool
    description: str
    
    # Optional fields
    skills: List[str] = field(default_factory=list)  # Skill proficiencies
    other_proficiencies: List[str] = field(default_factory=list)  # Tools, vehicles, gaming sets
    ability_scores: List[str] = field(default_factory=list)  # Ability score options (e.g., ["Intelligence", "Wisdom", "Charisma"])
    feats: List[str] = field(default_factory=list)  # Origin feats granted (e.g., ["Magic Initiate (Cleric)"])
    equipment: str = ""  # Equipment description
    features: List[BackgroundFeature] = field(default_factory=list)  # Background features
    
    # Metadata
    is_official: bool = True  # True for official content, False for homebrew
    is_custom: bool = False  # True if user-created
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "source": self.source,
            "is_legacy": self.is_legacy,
            "description": self.description,
            "skills": self.skills,
            "other_proficiencies": self.other_proficiencies,
            "ability_scores": self.ability_scores,
            "feats": self.feats,
            "equipment": self.equipment,
            "features": [f.to_dict() for f in self.features],
            "is_official": self.is_official,
            "is_custom": self.is_custom
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Background':
        """Create Background from dictionary."""
        features = []
        if "features" in data:
            features = [BackgroundFeature.from_dict(f) for f in data["features"]]
        
        return cls(
            name=data.get("name", "Unknown"),
            source=data.get("source", ""),
            is_legacy=data.get("is_legacy", False),
            description=data.get("description", ""),
            skills=data.get("skills", []),
            other_proficiencies=data.get("other_proficiencies", []),
            ability_scores=data.get("ability_scores", []),
            feats=data.get("feats", []),
            equipment=data.get("equipment", ""),
            features=features,
            is_official=data.get("is_official", True),
            is_custom=data.get("is_custom", False)
        )
    
    def get_skills_summary(self) -> str:
        """Get a summary of skill proficiencies."""
        if not self.skills:
            return "No skill proficiencies"
        return ", ".join(self.skills)
    
    def get_ability_scores_summary(self) -> str:
        """Get a summary of ability score options."""
        if not self.ability_scores:
            return ""
        return ", ".join(self.ability_scores)
    
    def get_feats_summary(self) -> str:
        """Get a summary of origin feats."""
        if not self.feats:
            return ""
        return " or ".join(self.feats)
    
    def get_features_summary(self) -> str:
        """Get a summary of feature names."""
        if not self.features:
            return "No special features"
        return ", ".join(f.name for f in self.features)


class BackgroundManager:
    """Manages the collection of backgrounds using SQLite database."""
    
    _instance = None
    
    def __init__(self):
        self._db = None
        self._backgrounds_cache: Optional[List[Background]] = None
    
    @property
    def db(self):
        """Get database instance, initializing if needed."""
        if self._db is None:
            from database import SpellDatabase
            self._db = SpellDatabase()
            self._db.initialize()
        return self._db
    
    @property
    def backgrounds(self) -> List[Background]:
        """Get all backgrounds, using cache if available."""
        if self._backgrounds_cache is None:
            self._reload_cache()
        return self._backgrounds_cache or []
    
    def _reload_cache(self):
        """Reload backgrounds from database into cache."""
        self._backgrounds_cache = []
        for bg_dict in self.db.get_all_backgrounds():
            self._backgrounds_cache.append(self._dict_to_background(bg_dict))
    
    def _invalidate_cache(self):
        """Invalidate the cache to force reload on next access."""
        self._backgrounds_cache = None
    
    def _dict_to_background(self, data: dict) -> Background:
        """Convert database dict to Background object."""
        features = []
        for f in data.get('features', []):
            features.append(BackgroundFeature(name=f.get('name', ''), description=f.get('description', '')))
        
        return Background(
            name=data.get('name', ''),
            source=data.get('source', ''),
            is_legacy=data.get('is_legacy', False),
            description=data.get('description', ''),
            skills=data.get('skills', []),
            other_proficiencies=data.get('other_proficiencies', []),
            ability_scores=data.get('ability_scores', []),
            feats=data.get('feats', []),
            equipment=data.get('equipment', ''),
            features=features,
            is_official=data.get('is_official', True),
            is_custom=data.get('is_custom', False)
        )
    
    def _background_to_dict(self, background: Background) -> dict:
        """Convert Background object to dict for database."""
        return {
            'name': background.name,
            'source': background.source,
            'is_legacy': background.is_legacy,
            'description': background.description,
            'skills': background.skills,
            'other_proficiencies': background.other_proficiencies,
            'ability_scores': background.ability_scores,
            'feats': background.feats,
            'equipment': background.equipment,
            'features': [{'name': f.name, 'description': f.description} for f in background.features],
            'is_official': background.is_official,
            'is_custom': background.is_custom
        }
    
    def load_backgrounds(self):
        """Reload backgrounds from database (for compatibility)."""
        self._invalidate_cache()
    
    def save_backgrounds(self):
        """No-op for database backend (saves happen immediately)."""
        pass
    
    def add_background(self, background: Background) -> bool:
        """Add a new background or update existing one."""
        existing = self.db.get_background_by_name(background.name)
        bg_dict = self._background_to_dict(background)
        
        if existing:
            self.db.update_background(existing['id'], bg_dict)
        else:
            self.db.insert_background(bg_dict)
        
        self._invalidate_cache()
        return True
    
    def remove_background(self, background_name: str) -> bool:
        """Remove a background by name. Only custom backgrounds can be removed."""
        existing = self.db.get_background_by_name(background_name)
        if not existing:
            return False
        
        if existing.get('is_official') and not existing.get('is_custom'):
            return False  # Cannot remove official backgrounds
        
        result = self.db.delete_background(existing['id'])
        self._invalidate_cache()
        return result
    
    def get_background(self, name: str) -> Optional[Background]:
        """Get a background by name."""
        data = self.db.get_background_by_name(name)
        if data:
            return self._dict_to_background(data)
        return None
    
    def get_all_sources(self) -> List[str]:
        """Get all unique sources from backgrounds."""
        sources = set()
        for background in self.backgrounds:
            if background.source:
                sources.add(background.source)
        return sorted(sources)
    
    def get_all_skills(self) -> List[str]:
        """Get all unique skills from backgrounds."""
        skills = set()
        for background in self.backgrounds:
            for skill in background.skills:
                skills.add(skill)
        return sorted(skills)
    
    def get_background_names(self) -> List[str]:
        """Get list of all background names."""
        return [b.name for b in self.backgrounds]
    
    def get_filtered_background_names(self, legacy_filter: str = "show_all") -> List[str]:
        """Get list of background names filtered by legacy settings."""
        filtered = []
        for bg in self.backgrounds:
            if legacy_filter == "no_legacy" and bg.is_legacy:
                continue
            elif legacy_filter == "legacy_only" and not bg.is_legacy:
                continue
            filtered.append(bg.name)
        return filtered
    
    def get_unofficial_backgrounds(self) -> List[Background]:
        """Get all unofficial (custom) backgrounds."""
        return [b for b in self.backgrounds if not b.is_official or b.is_custom]
    
    def get_unofficial_sources(self) -> List[str]:
        """Get all unique sources from unofficial backgrounds."""
        sources = set()
        for background in self.backgrounds:
            if (not background.is_official or background.is_custom) and background.source:
                sources.add(background.source)
        return sorted(sources)
    
    def export_to_json(self, file_path: str, backgrounds: Optional[List[Background]] = None) -> int:
        """Export backgrounds to a JSON file."""
        if backgrounds is None:
            backgrounds = [b for b in self.backgrounds if b.is_custom]
        
        data = {
            "backgrounds": [b.to_dict() for b in backgrounds]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return len(backgrounds)
    
    def import_from_json(self, file_path: str) -> int:
        """Import backgrounds from a JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        count = 0
        backgrounds_data = data.get("backgrounds", [])
        
        for bg_data in backgrounds_data:
            background = Background.from_dict(bg_data)
            # Mark as custom/non-official when importing
            background.is_custom = True
            background.is_official = False
            self.add_background(background)
            count += 1
        
        return count


# Singleton instance
_background_manager: Optional[BackgroundManager] = None


def get_background_manager() -> BackgroundManager:
    """Get the global BackgroundManager instance."""
    global _background_manager
    if _background_manager is None:
        _background_manager = BackgroundManager()
    return _background_manager
