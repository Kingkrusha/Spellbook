"""
Spell Manager for D&D Spellbook Application.
Handles spell collection management with SQLite database persistence.
"""

import os
import sys
from typing import List, Optional, Callable, Set
from spell import Spell, CharacterClass, AdvancedFilters, PROTECTED_TAGS
from database import SpellDatabase


def get_resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for dev and for PyInstaller.
    When running as a bundled .exe, resources are in a temp folder.
    """
    if hasattr(sys, '_MEIPASS'):
        # Running as bundled executable (PyInstaller)
        return os.path.join(sys._MEIPASS, relative_path)  # type: ignore[attr-defined]
    else:
        # Running in development
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# Spells to exclude from automatic migration (outdated/duplicate versions)
EXCLUDED_SPELLS: Set[str] = {
    "summon draconic spirit",  # Outdated version of "Summon Dragon"
}


import shutil


class SpellManager:
    """Manages a collection of spells with SQLite database persistence."""
    
    DEFAULT_DB_PATH = "spellbook.db"
    LEGACY_FILE_NAME = "spells.txt"  # For migration and import/export
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the spell manager with an optional database path."""
        self.db_path = db_path or self.DEFAULT_DB_PATH
        
        # If database doesn't exist, try to copy from bundled location
        if not os.path.exists(self.db_path):
            bundled_db = get_resource_path(self.DEFAULT_DB_PATH)
            if bundled_db != self.db_path and os.path.exists(bundled_db):
                try:
                    shutil.copy2(bundled_db, self.db_path)
                    print(f"Copied bundled database to {self.db_path}")
                except Exception as e:
                    print(f"Could not copy bundled database: {e}")
        
        self._db = SpellDatabase(self.db_path)
        self._spells: List[Spell] = []
        self._listeners: List[Callable[[], None]] = []
    
    @property
    def LEGACY_FILE(self) -> str:
        """Get the path to the legacy spells.txt file, handling packaged executables."""
        return get_resource_path(self.LEGACY_FILE_NAME)
        
    @property
    def spells(self) -> List[Spell]:
        """Return a copy of the spell list."""
        return self._spells.copy()
    
    def add_listener(self, callback: Callable[[], None]):
        """Add a listener to be notified when spells change."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[], None]):
        """Remove a listener to prevent memory leaks when views are destroyed."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of a change."""
        for listener in self._listeners:
            listener()
    
    def _spell_to_dict(self, spell: Spell) -> dict:
        """Convert a Spell object to a dictionary for database storage."""
        # Use class_names if available, otherwise fall back to enum values
        class_names = spell.class_names if spell.class_names else [c.value for c in spell.classes]
        return {
            'name': spell.name,
            'level': spell.level,
            'casting_time': spell.casting_time,
            'ritual': spell.ritual,
            'range_value': spell.range_value,
            'components': spell.components,
            'duration': spell.duration,
            'concentration': spell.concentration,
            'description': spell.description,
            'source': spell.source,
            'classes': class_names,
            'tags': spell.tags,
            'is_modified': spell.is_modified,
            'original_name': spell.original_name,
            'is_legacy': spell.is_legacy
        }
    
    def _dict_to_spell(self, data: dict) -> Spell:
        """Convert a database dictionary to a Spell object."""
        # Keep the original class name strings
        class_names = data.get('classes', [])
        
        # Convert to enum values for backward compatibility
        classes = []
        for class_name in class_names:
            try:
                classes.append(CharacterClass.from_string(class_name))
            except ValueError:
                pass  # Skip unknown classes
        
        return Spell(
            name=data['name'],
            level=data['level'],
            casting_time=data['casting_time'],
            ritual=data.get('ritual', False),
            range_value=data['range_value'],
            components=data['components'],
            duration=data['duration'],
            concentration=data.get('concentration', False),
            classes=classes,
            class_names=class_names,  # Store original class name strings
            description=data.get('description', ''),
            source=data.get('source', ''),
            tags=data.get('tags', []),
            is_modified=data.get('is_modified', False),
            original_name=data.get('original_name', ''),
            is_legacy=data.get('is_legacy', False)
        )
    
    def load_spells(self) -> bool:
        """Load spells from the database. Returns True if successful."""
        try:
            # Initialize database (creates tables if needed)
            self._db.initialize()
            
            # Check if we need to populate with initial spell data
            if self._db.get_spell_count() == 0:
                print("Populating database with initial spell data...")
                count = self._db.populate_initial_spells()
                print(f"Populated {count} spells into the database.")
            
            # Load all spells from database
            spell_dicts = self._db.get_all_spells()
            self._spells = [self._dict_to_spell(d) for d in spell_dicts]
            self._spells.sort(key=lambda s: (s.level, s.name.lower()))
            
            self._notify_listeners()
            return True
            
        except Exception as e:
            print(f"Error loading spells: {e}")
            return False
    
    def _migrate_from_text_file(self):
        """Migrate spells from legacy text file to database."""
        try:
            with open(self.LEGACY_FILE, "r", encoding="utf-8") as f:
                spells_to_import = []
                skipped_count = 0
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            spell = Spell.from_file_line(line)
                            # Skip excluded spells (outdated/duplicate versions)
                            if spell.name.lower() in EXCLUDED_SPELLS:
                                skipped_count += 1
                                continue
                            spells_to_import.append(self._spell_to_dict(spell))
                        except Exception as e:
                            print(f"Error parsing spell line during migration: {e}")
                            continue
                
                if spells_to_import:
                    count = self._db.bulk_insert_spells(spells_to_import)
                    print(f"Migrated {count} spells to SQLite database.")
                    if skipped_count > 0:
                        print(f"Skipped {skipped_count} excluded spells.")
                    
                    # Rename the old file as backup
                    try:
                        backup_path = self.LEGACY_FILE + ".backup"
                        if os.path.exists(backup_path):
                            os.remove(backup_path)  # Remove old backup if exists
                        os.rename(self.LEGACY_FILE, backup_path)
                        print(f"Legacy file backed up to {backup_path}")
                    except Exception as backup_error:
                        print(f"Could not backup legacy file: {backup_error}")
                    
        except Exception as e:
            print(f"Error during migration: {e}")
    
    def save_spells(self) -> bool:
        """
        Save is now handled automatically by the database.
        This method exists for compatibility but individual operations
        already persist immediately.
        """
        return True
    
    def add_spell(self, spell: Spell) -> bool:
        """Add a new spell to the collection. New spells get 'Unofficial' tag unless already marked."""
        try:
            # Check for duplicate name
            if self._db.spell_exists(spell.name):
                return False
            
            # Auto-tag new spells as "Unofficial" if they don't have Official or Unofficial
            if "Official" not in spell.tags and "Unofficial" not in spell.tags:
                spell.tags = spell.tags + ["Unofficial"]
            
            # Insert into database
            self._db.insert_spell(self._spell_to_dict(spell))
            
            # Update in-memory list
            self._spells.append(spell)
            self._spells.sort(key=lambda s: (s.level, s.name.lower()))
            
            self._notify_listeners()
            return True
            
        except Exception as e:
            print(f"Error adding spell: {e}")
            return False
    
    def bulk_add_spells(self, spells: List[Spell], progress_callback=None) -> int:
        """
        Add multiple spells efficiently using batch database operations.
        
        Args:
            spells: List of Spell objects to add
            progress_callback: Optional callback(current, total) for progress updates
        
        Returns:
            Number of spells successfully added
        """
        if not spells:
            return 0
        
        try:
            # Pre-process spells: enforce unofficial status and convert to dicts
            spell_dicts = []
            total = len(spells)
            for i, spell in enumerate(spells):
                # Enforce unofficial status
                tags = [t for t in spell.tags if t != "Official"]
                if "Unofficial" not in tags:
                    tags.append("Unofficial")
                spell.tags = tags
                
                spell_dicts.append(self._spell_to_dict(spell))
                
                # Call progress callback periodically (every 20 spells)
                if progress_callback and (i + 1) % 20 == 0:
                    progress_callback(i + 1, total)
            
            # Bulk insert to database (single transaction)
            inserted = self._db.bulk_insert_spells(spell_dicts)
            
            # Reload in-memory list once (already sorted by database query)
            self.load_spells()
            
            # Final progress update
            if progress_callback:
                progress_callback(total, total)
            
            return inserted
            
        except Exception as e:
            print(f"Error in bulk_add_spells: {e}")
            return 0
    
    def update_spell(self, old_name: str, updated_spell: Spell) -> bool:
        """Update an existing spell. Returns True if successful."""
        try:
            # Get the spell ID
            spell_id = self._db.get_spell_id_by_name(old_name)
            if spell_id is None:
                return False
            
            # Check for name conflict if name changed
            if old_name.lower() != updated_spell.name.lower():
                if self._db.spell_exists(updated_spell.name):
                    return False
            
            # Find the original spell to check for modifications
            original_spell = None
            for spell in self._spells:
                if spell.name.lower() == old_name.lower():
                    original_spell = spell
                    break
            
            # Check if this is an official spell being modified
            if original_spell and original_spell.is_official:
                # Check if any gameplay-relevant fields changed (not tags or source)
                if self._has_gameplay_changes(original_spell, updated_spell):
                    updated_spell.is_modified = True
            
            # Update in database
            self._db.update_spell(spell_id, self._spell_to_dict(updated_spell))
            
            # Update in-memory list
            for i, spell in enumerate(self._spells):
                if spell.name.lower() == old_name.lower():
                    self._spells[i] = updated_spell
                    break
            
            self._spells.sort(key=lambda s: (s.level, s.name.lower()))
            self._notify_listeners()
            return True
            
        except Exception as e:
            print(f"Error updating spell: {e}")
            return False
    
    def restore_spell_to_default(self, spell_name: str) -> bool:
        """
        Restore a modified official spell to its original default values.
        Uses original_name if the spell was renamed, falls back to current name.
        Returns True if successful, False otherwise.
        """
        try:
            from tools.spell_data import get_all_spells
            
            # First find the spell by current name to get its original_name
            spell_to_restore = None
            for spell in self._spells:
                if spell.name.lower() == spell_name.lower():
                    spell_to_restore = spell
                    break
            
            if not spell_to_restore:
                print(f"Spell not found in collection: {spell_name}")
                return False
            
            # Use original_name if available, otherwise use current name
            lookup_name = spell_to_restore.original_name if spell_to_restore.original_name else spell_name
            
            # Find the original spell data
            original_data = None
            for spell_data in get_all_spells():
                if spell_data['name'].lower() == lookup_name.lower():
                    original_data = spell_data
                    break
            
            if not original_data:
                print(f"Original spell data not found for: {lookup_name}")
                return False
            
            # Get the current spell ID
            spell_id = self._db.get_spell_id_by_name(spell_name)
            if spell_id is None:
                return False
            
            # Restore with is_modified=False (keep original_name for future restoration)
            restore_data = {
                'name': original_data['name'],
                'level': original_data['level'],
                'casting_time': original_data['casting_time'],
                'ritual': original_data['ritual'],
                'range_value': original_data['range_value'],
                'components': original_data['components'],
                'duration': original_data['duration'],
                'concentration': original_data['concentration'],
                'description': original_data['description'],
                'source': original_data['source'],
                'classes': original_data['classes'],
                'tags': original_data['tags'],
                'is_modified': False
            }
            
            # Update in database
            self._db.update_spell(spell_id, restore_data)
            
            # Update in-memory list
            restore_data['original_name'] = original_data['name']  # Ensure original_name is set
            restored_spell = self._dict_to_spell(restore_data)
            for i, spell in enumerate(self._spells):
                if spell.name.lower() == spell_name.lower():
                    self._spells[i] = restored_spell
                    break
            
            self._notify_listeners()
            return True
            
        except Exception as e:
            print(f"Error restoring spell: {e}")
            return False
    
    def restore_all_official_spells(self) -> int:
        """
        Restore all modified official spells to their default values.
        Uses original_name to find the original spell data even if renamed.
        Returns the number of spells restored.
        """
        try:
            from tools.spell_data import get_all_spells
            
            # Build a lookup of original spell data
            original_spells = {spell_data['name'].lower(): spell_data for spell_data in get_all_spells()}
            
            count = 0
            for spell in self._spells:
                if spell.is_official and spell.is_modified:
                    # Use original_name if available, otherwise use current name
                    lookup_name = spell.original_name if spell.original_name else spell.name
                    original_data = original_spells.get(lookup_name.lower())
                    if original_data:
                        spell_id = self._db.get_spell_id_by_name(spell.name)
                        if spell_id:
                            restore_data = {
                                'name': original_data['name'],
                                'level': original_data['level'],
                                'casting_time': original_data['casting_time'],
                                'ritual': original_data['ritual'],
                                'range_value': original_data['range_value'],
                                'components': original_data['components'],
                                'duration': original_data['duration'],
                                'concentration': original_data['concentration'],
                                'description': original_data['description'],
                                'source': original_data['source'],
                                'classes': original_data['classes'],
                                'tags': original_data['tags'],
                                'is_modified': False
                            }
                            self._db.update_spell(spell_id, restore_data)
                            count += 1
            
            # Reload spells if any were restored
            if count > 0:
                self.load_spells()
                self._notify_listeners()
            
            return count
            
        except Exception as e:
            print(f"Error restoring all official spells: {e}")
            return 0
    
    def _has_gameplay_changes(self, original: Spell, updated: Spell) -> bool:
        """
        Check if an official spell has gameplay-relevant changes.
        Tags and source are excluded from this check.
        """
        # Compare name (case-insensitive)
        if original.name.lower() != updated.name.lower():
            return True
        # Compare level
        if original.level != updated.level:
            return True
        # Compare casting_time
        if original.casting_time != updated.casting_time:
            return True
        # Compare ritual
        if original.ritual != updated.ritual:
            return True
        # Compare range_value
        if original.range_value != updated.range_value:
            return True
        # Compare components
        if original.components != updated.components:
            return True
        # Compare duration
        if original.duration != updated.duration:
            return True
        # Compare concentration
        if original.concentration != updated.concentration:
            return True
        # Compare classes
        if set(original.classes) != set(updated.classes):
            return True
        # Compare description
        if original.description != updated.description:
            return True
        return False
    
    def mark_all_spells_official(self) -> int:
        """
        Mark all existing spells as 'Official' by adding the tag.
        Removes 'Unofficial' tag if present.
        Returns the number of spells modified.
        """
        count = 0
        for spell in self._spells:
            modified = False
            # Remove Unofficial if present
            if "Unofficial" in spell.tags:
                spell.tags = [t for t in spell.tags if t != "Unofficial"]
                modified = True
            # Add Official if not present
            if "Official" not in spell.tags:
                spell.tags = spell.tags + ["Official"]
                modified = True
            
            if modified:
                spell_id = self._db.get_spell_id_by_name(spell.name)
                if spell_id:
                    self._db.update_spell(spell_id, self._spell_to_dict(spell))
                    count += 1
        
        if count > 0:
            self._notify_listeners()
        return count
    
    def delete_spell(self, name: str) -> bool:
        """Delete a spell by name. Returns True if successful."""
        try:
            if not self._db.delete_spell_by_name(name):
                return False
            
            # Update in-memory list
            self._spells = [s for s in self._spells if s.name.lower() != name.lower()]
            
            self._notify_listeners()
            return True
            
        except Exception as e:
            print(f"Error deleting spell: {e}")
            return False
    
    def get_spell(self, name: str) -> Optional[Spell]:
        """Get a spell by name."""
        for spell in self._spells:
            if spell.name.lower() == name.lower():
                return spell
        return None
    
    def get_filtered_spells(self, search_text: str = "", level_filter: int = -1,
                            class_name_filter: str = "",
                            advanced: Optional[AdvancedFilters] = None,
                            legacy_filter: str = "show_all") -> List[Spell]:
        """Return spells matching the given filter criteria.
        
        Uses SQL for most filtering (much faster for large spell collections),
        with Python post-filtering for complex criteria like costly_component and min_range.
        
        Args:
            class_name_filter: Class name string (e.g., "Wizard", "Witch") for filtering
        
        legacy_filter options:
            - "show_all": No legacy filtering
            - "show_unupdated": Show non-legacy + legacy without a non-legacy version
            - "no_legacy": Only show non-legacy spells
            - "legacy_only": Only show legacy spells
        """
        # Build SQL filter parameters from advanced filters
        ritual = None
        concentration = None
        source = None
        tags = None
        tags_mode = "has_all"
        casting_time = None
        duration = None
        has_verbal = None
        has_somatic = None
        has_material = None
        costly_component = None  # Can't filter in SQL, handled in Python
        min_range = 0  # Complex with new range encoding, handled in Python
        
        if advanced:
            ritual = advanced.ritual_filter
            concentration = advanced.concentration_filter
            min_range = advanced.min_range  # Will be used for Python filtering
            has_verbal = advanced.has_verbal
            has_somatic = advanced.has_somatic
            has_material = advanced.has_material
            costly_component = advanced.costly_component
            
            # Source filter now handled in Python for multi-select support
            # Keep source_filter and source_filter_mode for post-processing
            
            # Tags filter
            if advanced.tags_filter:
                tags = advanced.tags_filter
                tags_mode = advanced.tags_filter_mode.value
            
            # Casting time filter (use exact match for SQL)
            if advanced.casting_time_filter:
                casting_time = advanced.casting_time_filter
            
            # Duration filter (use exact match for SQL)
            if advanced.duration_filter:
                duration = advanced.duration_filter
        
        # Get filtered results from database
        # Note: min_range and source not passed to SQL - handled in Python due to complex filtering
        # Normalize None -> empty values for database call to satisfy typed signatures
        spell_dicts = self._db.search_spells(
            search_text=search_text,
            level=level_filter,
            class_name=class_name_filter,
            ritual=ritual,
            concentration=concentration,
            min_range=0,  # Don't filter by range in SQL
            source="",  # Don't filter by source in SQL - handled in Python
            tags=(tags or []),
            tags_mode=tags_mode,
            casting_time=(casting_time or ""),
            duration=(duration or ""),
            has_verbal=has_verbal,
            has_somatic=has_somatic,
            has_material=has_material
        )
        
        # Convert to Spell objects
        results = [self._dict_to_spell(d) for d in spell_dicts]
        
        # Apply Python post-filters for criteria that can't be done in SQL
        if costly_component is not None:
            results = [s for s in results if s.has_costly_component == costly_component]
        
        # Filter by minimum range using the new encoding system
        if min_range != 0:
            from spell import range_value_to_feet
            min_feet = range_value_to_feet(min_range)
            results = [s for s in results if s.range_as_feet >= min_feet]
        
        # Filter by source using include/exclude mode
        if advanced and advanced.source_filter:
            from spell import SourceFilterMode
            sources_lower = [s.lower() for s in advanced.source_filter]
            if advanced.source_filter_mode == SourceFilterMode.INCLUDE:
                # Keep spells from selected sources
                results = [s for s in results if any(src in s.source.lower() for src in sources_lower)]
            else:  # EXCLUDE mode
                # Remove spells from selected sources
                results = [s for s in results if not any(src in s.source.lower() for src in sources_lower)]
        
        # Apply legacy content filter
        if legacy_filter == "no_legacy":
            # Only show non-legacy spells
            results = [s for s in results if not s.is_legacy]
        elif legacy_filter == "legacy_only":
            # Only show legacy spells
            results = [s for s in results if s.is_legacy]
        elif legacy_filter == "show_unupdated":
            # Show non-legacy spells + legacy spells that don't have a non-legacy version
            # Build set of non-legacy spell names for quick lookup
            non_legacy_names = {s.name.lower() for s in results if not s.is_legacy}
            results = [s for s in results if not s.is_legacy or s.name.lower() not in non_legacy_names]
        # "show_all" - no filtering needed
        
        # Hide spells whose ALL classes are missing from the system
        # This allows unofficial spells with classes like "Witch" to remain hidden
        # until that class is imported, while still remembering the class association
        valid_classes = set(c.lower() for c in CharacterClass.all_class_names_with_custom())
        results = [s for s in results if any(
            cn.lower() in valid_classes for cn in s.class_names
        )]
        
        return results
    
    def get_all_sources(self) -> List[str]:
        """Return a sorted list of all unique sources across all spells."""
        return self._db.get_all_sources()
    
    def get_all_casting_times(self) -> List[str]:
        """Return a sorted list of all unique casting times across all spells."""
        return self._db.get_all_casting_times()
    
    def get_all_durations(self) -> List[str]:
        """Return a sorted list of all unique durations across all spells."""
        return self._db.get_all_durations()
    
    def get_all_range_values(self) -> List[int]:
        """Return all unique range_value integers across all spells."""
        return self._db.get_all_range_values()
    
    def get_all_ranges_for_display(self) -> List[tuple]:
        """Return all unique range values with display labels, ordered appropriately.
        Returns list of (value, display_label) tuples.
        """
        return self._db.get_all_ranges_for_display()
    
    def get_all_tags(self) -> List[str]:
        """Return a sorted list of all unique tags across all spells."""
        return self._db.get_all_tags()
    
    def import_spells(self, file_path: str, replace: bool = False) -> int:
        """
        Import spells from a pipe-delimited text file.
        
        Args:
            file_path: Path to the file to import from
            replace: If True, replace existing spells. If False, merge (skip duplicates).
        
        Returns:
            Number of spells imported
        """
        imported_count = 0
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                new_spells = []
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            spell = Spell.from_file_line(line)
                            new_spells.append(self._spell_to_dict(spell))
                        except Exception:
                            continue
                
                if replace:
                    # Clear existing and insert all new
                    self._db.clear_all_spells()
                    imported_count = self._db.bulk_insert_spells(new_spells)
                else:
                    # Merge - bulk_insert_spells already skips duplicates
                    imported_count = self._db.bulk_insert_spells(new_spells)
                
                # Reload in-memory list
                spell_dicts = self._db.get_all_spells()
                self._spells = [self._dict_to_spell(d) for d in spell_dicts]
                self._spells.sort(key=lambda s: (s.level, s.name.lower()))
                
                self._notify_listeners()
                
        except Exception as e:
            print(f"Error importing spells: {e}")
        
        return imported_count
    
    def export_spells(self, file_path: str, spells: Optional[List[Spell]] = None, 
                      unofficial_only: bool = True) -> bool:
        """
        Export spells to a pipe-delimited text file.
        
        Args:
            file_path: Path to export to
            spells: List of spells to export (None = export based on unofficial_only)
            unofficial_only: If True and spells is None, only export unofficial spells
        
        Returns:
            True if successful
        """
        if spells is None:
            if unofficial_only:
                # Only export spells that don't have the Official tag
                spells = [s for s in self._spells if not s.is_official]
            else:
                spells = self._spells
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for spell in spells:
                    f.write(spell.to_file_line() + "\n")
            return True
        except Exception as e:
            print(f"Error exporting spells: {e}")
            return False
    
    def get_unofficial_spell_count(self) -> int:
        """Get the count of unofficial spells (for export info)."""
        return len([s for s in self._spells if not s.is_official])
    
    def get_unofficial_sources(self) -> List[str]:
        """Get list of sources that have unofficial (non-official) spells."""
        sources = set()
        for spell in self._spells:
            if not spell.is_official and spell.source:
                sources.add(spell.source)
        return sorted(sources)
    
    def export_to_text_file(self, file_path: Optional[str] = None) -> bool:
        """
        Export all spells to a text file (useful for backup).
        
        Args:
            file_path: Path to export to (defaults to spells.txt)
        
        Returns:
            True if successful
        """
        return self.export_spells(file_path or self.LEGACY_FILE)
    
    def export_to_json(self, file_path: str, spells: Optional[List[Spell]] = None) -> int:
        """
        Export spells to a JSON file.
        
        Args:
            file_path: Path to export to
            spells: List of spells to export (None = export all unofficial)
        
        Returns:
            Number of spells exported
        """
        import json
        
        if spells is None:
            # Default to unofficial spells only
            spells = [s for s in self._spells if not s.is_official]
        
        try:
            data = {
                "spells": [self._spell_to_dict(s) for s in spells]
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return len(spells)
        except Exception as e:
            print(f"Error exporting spells to JSON: {e}")
            return 0
    
    def import_from_json(self, file_path: str) -> int:
        """
        Import spells from a JSON file.
        
        Args:
            file_path: Path to the JSON file
        
        Returns:
            Number of spells imported
        """
        import json
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            spells_data = data.get("spells", [])
            imported_count = 0
            
            for spell_dict in spells_data:
                try:
                    spell = self._dict_to_spell(spell_dict)
                    # Enforce unofficial status: remove Official, add Unofficial
                    tags = [t for t in spell.tags if t != "Official"]
                    if "Unofficial" not in tags:
                        tags.append("Unofficial")
                    spell.tags = tags
                    # Add or update the spell
                    existing = self.get_spell(spell.name)
                    if existing:
                        self.update_spell(spell.name, spell)
                    else:
                        self.add_spell(spell)
                    imported_count += 1
                except Exception as e:
                    print(f"Error importing spell: {e}")
                    continue
            
            return imported_count
        except Exception as e:
            print(f"Error importing from JSON: {e}")
            return 0
    
    def import_from_text_file(self, file_path: str) -> int:
        """
        Import spells from a pipe-delimited text file.
        
        Args:
            file_path: Path to the text file
        
        Returns:
            Number of spells imported
        """
        return self.import_spells(file_path, replace=False)
    
    def get_spell_count(self) -> int:
        """Get total number of spells."""
        return len(self._spells)
    
    def reload_from_database(self):
        """Force reload all spells from the database."""
        spell_dicts = self._db.get_all_spells()
        self._spells = [self._dict_to_spell(d) for d in spell_dicts]
        self._spells.sort(key=lambda s: (s.level, s.name.lower()))
        self._notify_listeners()
