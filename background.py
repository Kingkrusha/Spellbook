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
    """Manages the collection of backgrounds."""
    
    _instance = None
    
    def __init__(self):
        self.backgrounds: List[Background] = []
        self._data_file = self._get_data_file_path()
        self.load_backgrounds()
    
    def _get_data_file_path(self) -> str:
        """Get the path to the backgrounds data file (user-writable location)."""
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, 'backgrounds.json')
    
    def _get_bundled_data_path(self) -> str:
        """Get the path to bundled backgrounds data (for PyInstaller)."""
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, 'backgrounds.json')
        return self._data_file
    
    def load_backgrounds(self):
        """Load backgrounds from JSON file."""
        self.backgrounds = []
        
        # First try user file (for modifications)
        if os.path.exists(self._data_file):
            try:
                with open(self._data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for bg_data in data.get("backgrounds", []):
                        self.backgrounds.append(Background.from_dict(bg_data))
                # Sort by name
                self.backgrounds.sort(key=lambda b: b.name)
                return
            except Exception as e:
                print(f"Error loading backgrounds from user path: {e}")
        
        # Try bundled path (for PyInstaller)
        bundled_path = self._get_bundled_data_path()
        if bundled_path != self._data_file and os.path.exists(bundled_path):
            try:
                with open(bundled_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for bg_data in data.get("backgrounds", []):
                        self.backgrounds.append(Background.from_dict(bg_data))
                # Save to user location so modifications can be preserved
                self.save_backgrounds()
                return
            except Exception as e:
                print(f"Error loading backgrounds from bundled path: {e}")
        
        # Sort by name
        self.backgrounds.sort(key=lambda b: b.name)
    
    def save_backgrounds(self):
        """Save all backgrounds to JSON file."""
        data = {
            "backgrounds": [b.to_dict() for b in self.backgrounds]
        }
        
        try:
            with open(self._data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving backgrounds: {e}")
            raise
    
    def add_background(self, background: Background) -> bool:
        """Add a new background or update existing one."""
        # Check for existing background with same name
        for i, existing in enumerate(self.backgrounds):
            if existing.name.lower() == background.name.lower():
                self.backgrounds[i] = background
                self.save_backgrounds()
                return True
        
        self.backgrounds.append(background)
        self.backgrounds.sort(key=lambda b: b.name)
        self.save_backgrounds()
        return True
    
    def remove_background(self, background_name: str) -> bool:
        """Remove a background by name. Only custom backgrounds can be removed."""
        for i, background in enumerate(self.backgrounds):
            if background.name.lower() == background_name.lower():
                if background.is_official and not background.is_custom:
                    return False  # Cannot remove official backgrounds
                del self.backgrounds[i]
                self.save_backgrounds()
                return True
        return False
    
    def get_background(self, name: str) -> Optional[Background]:
        """Get a background by name."""
        for background in self.backgrounds:
            if background.name.lower() == name.lower():
                return background
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
        """Get list of background names filtered by legacy settings.
        
        Args:
            legacy_filter: One of "show_all", "show_unupdated", "no_legacy", "legacy_only"
        """
        filtered = []
        for bg in self.backgrounds:
            if legacy_filter == "no_legacy" and bg.is_legacy:
                continue
            elif legacy_filter == "legacy_only" and not bg.is_legacy:
                continue
            # "show_all" and "show_unupdated" show everything (unupdated doesn't apply to backgrounds)
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
