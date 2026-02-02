"""
Settings management for D&D Spellbook Application.
Handles user preferences and persistent storage.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class AppSettings:
    """Application settings and user preferences."""
    
    # Appearance
    appearance_mode: str = "dark"  # "dark", "light", or "system"
    theme_name: str = "default"  # Theme preset name or "custom" for custom theme
    use_custom_theme: bool = False  # Deprecated: use theme_name="custom" instead (kept for backwards compatibility)
    
    # Notifications
    show_spell_added_notification: bool = True
    show_rest_notification: bool = True
    
    # Spell list warnings
    warn_too_many_cantrips: bool = True
    warn_wrong_class: bool = True
    warn_spell_too_high_level: bool = True
    warn_too_many_prepared: bool = True  # Show warning when preparing more spells than allowed
    
    # Comparison mode
    show_comparison_highlights: bool = True
    
    # Character sheet
    auto_calculate_hp: bool = True  # Automatically calculate HP maximum based on class and level
    auto_calculate_ac: bool = True  # Automatically calculate AC based on armor and DEX
    auto_fill_proficiencies: bool = True  # Automatically fill proficiencies when creating new sheet
    auto_apply_saving_throws: bool = True  # Automatically apply saving throw proficiencies from starting class
    warn_multiclass_removal: bool = True  # Show warning when removing a multiclass by setting level to 0
    long_rest_hit_dice: str = "all"  # "all", "half", or "none" - how many hit dice to restore on long rest
    
    # Official spell protection
    allow_delete_official_spells: bool = False  # If False, cannot delete spells tagged as Official
    
    # Legacy content filter
    # Options: "show_all", "show_unupdated", "no_legacy", "legacy_only"
    legacy_content_filter: str = "show_all"
    
    # Internal flags (not user-configurable)
    initial_official_tag_applied: bool = False  # True after first run marks spells as Official
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        """Create settings from dictionary."""
        # Handle backwards compatibility: convert use_custom_theme to theme_name
        if 'theme_name' not in data and 'use_custom_theme' in data:
            data['theme_name'] = 'custom' if data.get('use_custom_theme') else 'default'
        
        # Only use known fields to handle version differences
        known_fields = {
            'appearance_mode', 'theme_name', 'use_custom_theme', 'show_spell_added_notification', 
            'show_rest_notification', 'warn_too_many_cantrips',
            'warn_wrong_class', 'warn_spell_too_high_level', 'warn_too_many_prepared',
            'show_comparison_highlights', 'initial_official_tag_applied',
            'allow_delete_official_spells', 'auto_calculate_hp', 'auto_calculate_ac',
            'auto_fill_proficiencies', 'auto_apply_saving_throws',
            'warn_multiclass_removal', 'long_rest_hit_dice', 'legacy_content_filter'
        }
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)


class SettingsManager:
    """Manages loading and saving application settings."""
    
    DEFAULT_FILE = "settings.json"
    
    def __init__(self, file_path: Optional[str] = None):
        """Initialize the settings manager."""
        self.file_path = file_path or self.DEFAULT_FILE
        self._settings: AppSettings = AppSettings()
        self._listeners = []
    
    @property
    def settings(self) -> AppSettings:
        """Get current settings."""
        return self._settings
    
    def add_listener(self, callback):
        """Add a listener to be notified when settings change."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback):
        """Remove a listener to prevent memory leaks when views are destroyed."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of settings change."""
        for listener in self._listeners:
            try:
                listener(self._settings)
            except Exception as e:
                print(f"Error notifying settings listener: {e}")
    
    def load(self) -> bool:
        """Load settings from file. Returns True if successful."""
        if not os.path.exists(self.file_path):
            # Create default settings file
            self._settings = AppSettings()
            self.save()
            return True
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._settings = AppSettings.from_dict(data)
            return True
        except Exception as e:
            print(f"Error loading settings: {e}")
            self._settings = AppSettings()
            return False
    
    def save(self) -> bool:
        """Save settings to file. Returns True if successful."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def update(self, **kwargs) -> bool:
        """Update specific settings and save."""
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        
        success = self.save()
        if success:
            self._notify_listeners()
        return success
    
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self._settings = AppSettings()
        self.save()
        self._notify_listeners()


# Global settings instance (singleton pattern)
_settings_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
        _settings_manager.load()
    return _settings_manager

