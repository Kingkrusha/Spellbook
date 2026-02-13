"""
Data Migration System for D&D Spellbook Application.
Handles updating old data files to be compatible with new versions
while preserving user modifications.
"""

import json
import os
import sys
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable


# Current data format versions
DATA_VERSIONS = {
    "lineages": 2,
    "feats": 2,
    "classes": 2,
    "settings": 2,
    "backgrounds": 1,
}


def get_data_path(filename: str) -> str:
    """Get the path to a data file, handling PyInstaller bundling."""
    if getattr(sys, 'frozen', False):
        return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def get_user_data_path(filename: str) -> str:
    """Get the path to user data file (writable location)."""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def backup_file(filepath: str) -> Optional[str]:
    """Create a backup of a file before migration."""
    if not os.path.exists(filepath):
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(filepath), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    filename = os.path.basename(filepath)
    backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")
    
    try:
        shutil.copy2(filepath, backup_path)
        print(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"Failed to create backup: {e}")
        return None


def load_json_file(filepath: str) -> Optional[Dict]:
    """Load a JSON file safely."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None


def save_json_file(filepath: str, data: Dict) -> bool:
    """Save data to a JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving {filepath}: {e}")
        return False


class DataMigrator:
    """Handles data file migrations between versions."""
    
    def __init__(self):
        self.migrations: Dict[str, Dict[int, Callable]] = {
            "lineages": {},
            "feats": {},
            "classes": {},
            "settings": {},
            "backgrounds": {},
        }
        self._register_migrations()
    
    def _register_migrations(self):
        """Register all migration functions."""
        # Lineages migrations
        self.migrations["lineages"][1] = self._migrate_lineages_v1_to_v2
        
        # Feats migrations
        self.migrations["feats"][1] = self._migrate_feats_v1_to_v2
        
        # Classes migrations
        self.migrations["classes"][1] = self._migrate_classes_v1_to_v2
        
        # Settings migrations
        self.migrations["settings"][1] = self._migrate_settings_v1_to_v2
    
    def get_data_version(self, data: Dict, data_type: str) -> int:
        """Get the version of a data file."""
        return data.get("_version", 1)
    
    def migrate_file(self, filepath: str, data_type: str) -> bool:
        """Migrate a data file to the latest version."""
        if not os.path.exists(filepath):
            return True  # Nothing to migrate
        
        data = load_json_file(filepath)
        if data is None:
            return False
        
        current_version = self.get_data_version(data, data_type)
        target_version = DATA_VERSIONS.get(data_type, 1)
        
        if current_version >= target_version:
            return True  # Already up to date
        
        print(f"Migrating {data_type} from v{current_version} to v{target_version}")
        
        # Create backup before migration
        backup_file(filepath)
        
        # Apply migrations sequentially
        while current_version < target_version:
            migration_func = self.migrations.get(data_type, {}).get(current_version)
            if migration_func:
                try:
                    data = migration_func(data)
                    current_version += 1
                    data["_version"] = current_version
                except Exception as e:
                    print(f"Migration error at v{current_version}: {e}")
                    return False
            else:
                current_version += 1
                data["_version"] = current_version
        
        return save_json_file(filepath, data)
    
    def merge_with_bundled(self, user_filepath: str, data_type: str) -> bool:
        """
        Merge user data with bundled data, preserving user modifications.
        - Adds new official entries from bundled data
        - Updates official entries that haven't been modified by user
        - Preserves all user-created (custom) entries
        - Preserves user modifications to official entries
        """
        bundled_filepath = get_data_path(os.path.basename(user_filepath))
        
        if not os.path.exists(bundled_filepath):
            return True  # No bundled data to merge
        
        if bundled_filepath == user_filepath:
            return True  # Same file, no merge needed
        
        bundled_data = load_json_file(bundled_filepath)
        if bundled_data is None:
            return True  # Can't load bundled, skip merge
        
        if not os.path.exists(user_filepath):
            # No user file, just copy bundled
            return save_json_file(user_filepath, bundled_data)
        
        user_data = load_json_file(user_filepath)
        if user_data is None:
            return False
        
        # Backup before merge
        backup_file(user_filepath)
        
        # Perform type-specific merge
        if data_type == "lineages":
            merged = self._merge_lineages(user_data, bundled_data)
        elif data_type == "feats":
            merged = self._merge_feats(user_data, bundled_data)
        elif data_type == "classes":
            merged = self._merge_classes(user_data, bundled_data)
        elif data_type == "backgrounds":
            merged = self._merge_backgrounds(user_data, bundled_data)
        else:
            return True  # No merge logic for this type
        
        return save_json_file(user_filepath, merged)
    
    def _merge_lineages(self, user_data: Dict, bundled_data: Dict) -> Dict:
        """Merge lineages, preserving user customizations."""
        user_lineages = {l["name"]: l for l in user_data.get("lineages", [])}
        bundled_lineages = {l["name"]: l for l in bundled_data.get("lineages", [])}
        
        merged = []
        
        # First, add all user entries
        for name, lineage in user_lineages.items():
            if lineage.get("is_custom", False):
                # User-created lineage, always keep
                merged.append(lineage)
            elif name in bundled_lineages:
                # Official lineage - check if user modified it
                bundled = bundled_lineages[name]
                if self._lineage_modified(lineage, bundled):
                    # User modified it, keep user version
                    merged.append(lineage)
                else:
                    # Not modified, use updated bundled version
                    merged.append(bundled)
            else:
                # Official lineage removed from bundled, keep if user modified
                merged.append(lineage)
        
        # Add new bundled lineages not in user data
        for name, lineage in bundled_lineages.items():
            if name not in user_lineages:
                merged.append(lineage)
        
        result = user_data.copy()
        result["lineages"] = sorted(merged, key=lambda l: l.get("name", ""))
        result["_version"] = DATA_VERSIONS["lineages"]
        return result
    
    def _lineage_modified(self, user: Dict, bundled: Dict) -> bool:
        """Check if user modified a lineage from the bundled version."""
        # Compare key fields that indicate modification
        fields_to_check = ["description", "traits", "speed", "size", "creature_type"]
        for field in fields_to_check:
            if user.get(field) != bundled.get(field):
                return True
        return False
    
    def _merge_feats(self, user_data: Dict, bundled_data: Dict) -> Dict:
        """Merge feats, preserving user customizations."""
        user_feats = {f["name"]: f for f in user_data.get("feats", [])}
        bundled_feats = {f["name"]: f for f in bundled_data.get("feats", [])}
        
        merged = []
        
        for name, feat in user_feats.items():
            if feat.get("is_custom", False):
                merged.append(feat)
            elif name in bundled_feats:
                bundled = bundled_feats[name]
                if self._feat_modified(feat, bundled):
                    merged.append(feat)
                else:
                    merged.append(bundled)
            else:
                merged.append(feat)
        
        for name, feat in bundled_feats.items():
            if name not in user_feats:
                merged.append(feat)
        
        result = user_data.copy()
        result["feats"] = sorted(merged, key=lambda f: f.get("name", ""))
        result["_version"] = DATA_VERSIONS["feats"]
        return result
    
    def _feat_modified(self, user: Dict, bundled: Dict) -> bool:
        """Check if user modified a feat."""
        fields_to_check = ["description", "prereq", "type", "is_spellcasting"]
        for field in fields_to_check:
            if user.get(field) != bundled.get(field):
                return True
        return False
    
    def _merge_classes(self, user_data: Dict, bundled_data: Dict) -> Dict:
        """Merge classes, preserving user customizations."""
        user_classes = user_data.get("classes", {})
        bundled_classes = bundled_data.get("classes", {})
        
        merged = {}
        
        for name, cls in user_classes.items():
            if cls.get("is_custom", False):
                merged[name] = cls
            elif name in bundled_classes:
                bundled = bundled_classes[name]
                if cls.get("is_custom", False):
                    merged[name] = cls
                else:
                    # Use bundled version for official classes
                    merged[name] = bundled
                    # But preserve any custom subclasses
                    if "subclasses" in cls:
                        custom_subclasses = [
                            s for s in cls["subclasses"]
                            if s.get("is_custom", False)
                        ]
                        if custom_subclasses:
                            merged[name]["subclasses"] = (
                                bundled.get("subclasses", []) + custom_subclasses
                            )
            else:
                merged[name] = cls
        
        for name, cls in bundled_classes.items():
            if name not in user_classes:
                merged[name] = cls
        
        result = user_data.copy()
        result["classes"] = merged
        result["_version"] = DATA_VERSIONS["classes"]
        return result
    
    def _merge_backgrounds(self, user_data: Dict, bundled_data: Dict) -> Dict:
        """Merge backgrounds, preserving user customizations."""
        user_backgrounds = {b["name"]: b for b in user_data.get("backgrounds", [])}
        bundled_backgrounds = {b["name"]: b for b in bundled_data.get("backgrounds", [])}
        
        merged = []
        
        # First, add all user entries
        for name, background in user_backgrounds.items():
            if background.get("is_custom", False):
                # User-created background, always keep
                merged.append(background)
            elif name in bundled_backgrounds:
                # Official background - check if user modified it
                bundled = bundled_backgrounds[name]
                if self._background_modified(background, bundled):
                    # User modified it, keep user version
                    merged.append(background)
                else:
                    # Not modified, use updated bundled version
                    merged.append(bundled)
            else:
                # Official background removed from bundled, keep if user modified
                merged.append(background)
        
        # Add new bundled backgrounds not in user data
        for name, background in bundled_backgrounds.items():
            if name not in user_backgrounds:
                merged.append(background)
        
        result = user_data.copy()
        result["backgrounds"] = sorted(merged, key=lambda b: b.get("name", ""))
        result["_version"] = DATA_VERSIONS["backgrounds"]
        return result
    
    def _background_modified(self, user: Dict, bundled: Dict) -> bool:
        """Check if user modified a background from the bundled version."""
        # Compare key fields that indicate modification
        fields_to_check = ["description", "skills", "feats", "equipment", "features"]
        for field in fields_to_check:
            if user.get(field) != bundled.get(field):
                return True
        return False
    
    # Migration functions
    def _migrate_lineages_v1_to_v2(self, data: Dict) -> Dict:
        """Migrate lineages from v1 to v2 format."""
        lineages = data.get("lineages", [])
        for lineage in lineages:
            # Add any new required fields with defaults
            if "is_legacy" not in lineage:
                lineage["is_legacy"] = False
            if "creature_type" not in lineage:
                lineage["creature_type"] = "Humanoid"
        return data
    
    def _migrate_feats_v1_to_v2(self, data: Dict) -> Dict:
        """Migrate feats from v1 to v2 format."""
        feats = data.get("feats", [])
        for feat in feats:
            if "is_custom" not in feat:
                feat["is_custom"] = False
            if "source" not in feat:
                feat["source"] = ""
        return data
    
    def _migrate_classes_v1_to_v2(self, data: Dict) -> Dict:
        """Migrate classes from v1 to v2 format."""
        classes = data.get("classes", {})
        for name, cls in classes.items():
            if "is_legacy" not in cls:
                cls["is_legacy"] = False
            # Ensure subclasses have required fields
            for subclass in cls.get("subclasses", []):
                if "is_custom" not in subclass:
                    subclass["is_custom"] = False
        return data
    
    def _migrate_settings_v1_to_v2(self, data: Dict) -> Dict:
        """Migrate settings from v1 to v2 format."""
        # Add any new settings with defaults
        defaults = {
            "show_legacy_content": True,
            "auto_backup": True,
        }
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
        return data


def run_all_migrations():
    """Run all data migrations on startup.
    
    Note: Lineages, feats, classes, and backgrounds are now stored in SQLite database.
    The database migration (_migrate_json_to_database) handles importing from bundled
    JSON files on first run. This function only handles settings.json now.
    """
    migrator = DataMigrator()
    
    # Only settings still uses JSON - other content is in SQLite
    settings_path = get_user_data_path("settings.json")
    migrator.migrate_file(settings_path, "settings")
    
    print("Data migration complete.")


if __name__ == "__main__":
    run_all_migrations()
