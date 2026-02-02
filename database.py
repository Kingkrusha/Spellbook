"""
SQLite database module for D&D Spellbook Application.
Handles database creation, migrations, and spell persistence.
"""

import sqlite3
import os
import json
from typing import List, Optional, Tuple
from contextlib import contextmanager


class SpellDatabase:
    """SQLite database handler for spell storage."""
    
    DEFAULT_DB_PATH = "spellbook.db"
    SCHEMA_VERSION = 7  # Bumped for is_legacy column
    
    # Protected tags that users cannot add/remove (case-insensitive)
    PROTECTED_TAGS = {"Official", "Unofficial"}
    _PROTECTED_TAGS_LOWER = {t.lower() for t in PROTECTED_TAGS}
    
    # Tag normalization map for consistent capitalization
    TAG_NORMALIZATION = {
        # Spellcasting tags
        'light': 'Light',
        'aoe': 'AOE',
        'buff': 'Buff',
        'debuff': 'Debuff',
        'healing': 'Healing',
        'damage': 'Damage',
        'utility': 'Utility',
        'attack': 'Attack',
        'saving throw': 'Saving Throw',
        # Damage types
        'fire': 'Fire',
        'cold': 'Cold',
        'lightning': 'Lightning',
        'thunder': 'Thunder',
        'acid': 'Acid',
        'poison': 'Poison',
        'radiant': 'Radiant',
        'necrotic': 'Necrotic',
        'force': 'Force',
        'psychic': 'Psychic',
        # Schools
        'abjuration': 'Abjuration',
        'conjuration': 'Conjuration',
        'divination': 'Divination',
        'enchantment': 'Enchantment',
        'evocation': 'Evocation',
        'illusion': 'Illusion',
        'necromancy': 'Necromancy',
        'transmutation': 'Transmutation',
        # Official tags
        'official': 'Official',
        'unofficial': 'Unofficial',
    }
    
    @classmethod
    def normalize_tag(cls, tag: str) -> str:
        """Normalize a tag to its canonical capitalization."""
        return cls.TAG_NORMALIZATION.get(tag.lower(), tag)
    
    @classmethod
    def is_protected_tag(cls, tag: str) -> bool:
        """Check if a tag is a protected tag (case-insensitive)."""
        return tag.lower() in cls._PROTECTED_TAGS_LOWER
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database connection."""
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self._connection: Optional[sqlite3.Connection] = None
        
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def initialize(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Schema version table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                )
            """)
            
            # Main spells table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spells (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    level INTEGER NOT NULL CHECK(level >= 0 AND level <= 9),
                    casting_time TEXT NOT NULL,
                    ritual INTEGER NOT NULL DEFAULT 0,
                    range_value INTEGER NOT NULL,
                    components TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    concentration INTEGER NOT NULL DEFAULT 0,
                    description TEXT,
                    source TEXT,
                    is_modified INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Spell classes junction table (many-to-many)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spell_classes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spell_id INTEGER NOT NULL,
                    class_name TEXT NOT NULL,
                    FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE,
                    UNIQUE(spell_id, class_name)
                )
            """)
            
            # Spell tags junction table (many-to-many)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS spell_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spell_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE,
                    UNIQUE(spell_id, tag)
                )
            """)
            
            # Stat blocks table (for summoning spells)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stat_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spell_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    size TEXT NOT NULL DEFAULT 'Medium',
                    creature_type TEXT NOT NULL DEFAULT '',
                    creature_subtype TEXT DEFAULT '',
                    alignment TEXT DEFAULT 'Neutral',
                    armor_class TEXT NOT NULL DEFAULT '',
                    hit_points TEXT NOT NULL DEFAULT '',
                    speed TEXT NOT NULL DEFAULT '',
                    abilities_json TEXT,
                    damage_resistances TEXT DEFAULT '',
                    damage_immunities TEXT DEFAULT '',
                    condition_immunities TEXT DEFAULT '',
                    senses TEXT DEFAULT '',
                    languages TEXT DEFAULT '',
                    challenge_rating TEXT DEFAULT '',
                    traits_json TEXT DEFAULT '[]',
                    actions_json TEXT DEFAULT '[]',
                    bonus_actions_json TEXT DEFAULT '[]',
                    reactions_json TEXT DEFAULT '[]',
                    legendary_actions_json TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spells_level ON spells(level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spells_name ON spells(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spell_classes_spell_id ON spell_classes(spell_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spell_classes_class ON spell_classes(class_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spell_tags_spell_id ON spell_tags(spell_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_spell_tags_tag ON spell_tags(tag)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stat_blocks_spell_id ON stat_blocks(spell_id)")
            
            # Set schema version if not exists
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (self.SCHEMA_VERSION,))
            
            # Create trigger for updated_at
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_spell_timestamp 
                AFTER UPDATE ON spells
                BEGIN
                    UPDATE spells SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """)
            
            # Run migrations
            self._run_migrations(conn)
    
    def _run_migrations(self, conn):
        """Run schema migrations if needed."""
        cursor = conn.cursor()
        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        current_version = row['version'] if row else 0
        
        # Migration to version 2: add is_modified column
        if current_version < 2:
            # Check if column already exists
            cursor.execute("PRAGMA table_info(spells)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_modified' not in columns:
                cursor.execute("ALTER TABLE spells ADD COLUMN is_modified INTEGER NOT NULL DEFAULT 0")
            cursor.execute("UPDATE schema_version SET version = 2")
            current_version = 2
        
        # Migration to version 3: add stat_blocks table
        if current_version < 3:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stat_blocks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    spell_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    size TEXT NOT NULL DEFAULT 'Medium',
                    creature_type TEXT NOT NULL DEFAULT '',
                    creature_subtype TEXT DEFAULT '',
                    alignment TEXT DEFAULT 'Neutral',
                    armor_class TEXT NOT NULL DEFAULT '',
                    hit_points TEXT NOT NULL DEFAULT '',
                    speed TEXT NOT NULL DEFAULT '',
                    abilities_json TEXT,
                    damage_resistances TEXT DEFAULT '',
                    damage_immunities TEXT DEFAULT '',
                    condition_immunities TEXT DEFAULT '',
                    senses TEXT DEFAULT '',
                    languages TEXT DEFAULT '',
                    challenge_rating TEXT DEFAULT '',
                    traits_json TEXT DEFAULT '[]',
                    actions_json TEXT DEFAULT '[]',
                    bonus_actions_json TEXT DEFAULT '[]',
                    reactions_json TEXT DEFAULT '[]',
                    legendary_actions_json TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (spell_id) REFERENCES spells(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_stat_blocks_spell_id ON stat_blocks(spell_id)")
            cursor.execute("UPDATE schema_version SET version = 3")
            current_version = 3
        
        # Migration to version 4: update spell descriptions to exact PHB 2024 text
        if current_version < 4:
            self._apply_spell_description_updates(cursor)
            cursor.execute("UPDATE schema_version SET version = 4")
            current_version = 4
        
        # Migration to version 5: add original_name column for restoration matching
        if current_version < 5:
            # Check if column already exists
            cursor.execute("PRAGMA table_info(spells)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'original_name' not in columns:
                cursor.execute("ALTER TABLE spells ADD COLUMN original_name TEXT DEFAULT ''")
                # For existing official spells, set original_name to current name
                cursor.execute("""
                    UPDATE spells SET original_name = name 
                    WHERE id IN (SELECT spell_id FROM spell_tags WHERE tag = 'Official')
                """)
            cursor.execute("UPDATE schema_version SET version = 5")
            current_version = 5
        
        # Migration to version 6: normalize tag capitalization
        if current_version < 6:
            self._normalize_tags(cursor)
            cursor.execute("UPDATE schema_version SET version = 6")
            current_version = 6
        
        # Migration to version 7: add is_legacy column for 2014 content filtering
        if current_version < 7:
            # Check if column already exists
            cursor.execute("PRAGMA table_info(spells)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'is_legacy' not in columns:
                cursor.execute("ALTER TABLE spells ADD COLUMN is_legacy INTEGER NOT NULL DEFAULT 0")
                # Mark spells as legacy if their source is NOT one of the 2024 sources
                # 2024 sources: "Player's Handbook (2024)", "Forgotten Realms - Heroes of Faerun", "Eberron - Forge of the Artificer"
                cursor.execute("""
                    UPDATE spells SET is_legacy = 1 
                    WHERE source NOT IN (
                        'Player''s Handbook (2024)', 
                        'Forgotten Realms - Heroes of Faerun', 
                        'Eberron - Forge of the Artificer'
                    ) AND source != ''
                """)
            cursor.execute("UPDATE schema_version SET version = 7")
            current_version = 7
    
    def _normalize_tags(self, cursor):
        """Normalize tag capitalization using class-level normalization map."""
        # Get all unique tags
        cursor.execute("SELECT DISTINCT tag FROM spell_tags")
        tags = [row[0] for row in cursor.fetchall()]
        
        for tag in tags:
            normalized = self.TAG_NORMALIZATION.get(tag.lower())
            if normalized and normalized != tag:
                # Update the tag
                cursor.execute(
                    "UPDATE spell_tags SET tag = ? WHERE tag = ?",
                    (normalized, tag)
                )
    
    def _apply_spell_description_updates(self, cursor):
        """Apply updated spell descriptions from PHB 2024 and other sources."""
        from tools.update_spell_descriptions import get_spell_updates
        
        updates = get_spell_updates()
        for spell_name, fields in updates.items():
            # Build SET clause dynamically based on provided fields
            set_parts = []
            values = []
            for field, value in fields.items():
                set_parts.append(f"{field} = ?")
                values.append(value)
            
            if set_parts:
                values.append(spell_name)  # For WHERE clause
                sql = f"UPDATE spells SET {', '.join(set_parts)} WHERE name = ? COLLATE NOCASE"
                cursor.execute(sql, values)
    
    def populate_initial_spells(self) -> int:
        """
        Populate the database with all official spells from spell_data.
        Called when the database is empty on first run.
        
        Returns:
            Number of spells inserted
        """
        from tools.spell_data import get_all_spells
        
        spells = get_all_spells()
        count = self.bulk_insert_spells(spells)
        
        # Also populate stat blocks
        self._populate_initial_stat_blocks()
        
        return count
    
    def _populate_initial_stat_blocks(self):
        """Populate stat blocks for summoning spells."""
        from tools.stat_block_data import get_all_stat_blocks
        
        stat_blocks = get_all_stat_blocks()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for sb in stat_blocks:
                # Get the spell_id from the spell_name
                spell_name = sb.get('spell_name')
                if not spell_name:
                    continue
                    
                cursor.execute(
                    "SELECT id FROM spells WHERE name = ? COLLATE NOCASE",
                    (spell_name,)
                )
                row = cursor.fetchone()
                if not row:
                    print(f"Warning: Spell '{spell_name}' not found for stat block '{sb.get('name')}'")
                    continue
                
                spell_id = row['id']
                
                # Check if stat block already exists
                cursor.execute(
                    "SELECT id FROM stat_blocks WHERE spell_id = ? AND name = ?",
                    (spell_id, sb.get('name'))
                )
                if cursor.fetchone():
                    continue  # Skip duplicates
                
                # Insert stat block
                cursor.execute("""
                    INSERT INTO stat_blocks (
                        spell_id, name, size, creature_type, creature_subtype, alignment,
                        armor_class, hit_points, speed, abilities_json,
                        damage_resistances, damage_immunities, condition_immunities,
                        senses, languages, challenge_rating,
                        traits_json, actions_json, bonus_actions_json,
                        reactions_json, legendary_actions_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    spell_id,
                    sb.get('name', ''),
                    sb.get('size', 'Medium'),
                    sb.get('creature_type', ''),
                    sb.get('creature_subtype', ''),
                    sb.get('alignment', 'Neutral'),
                    sb.get('armor_class', ''),
                    sb.get('hit_points', ''),
                    sb.get('speed', ''),
                    sb.get('abilities_json', '{}'),
                    sb.get('damage_resistances', ''),
                    sb.get('damage_immunities', ''),
                    sb.get('condition_immunities', ''),
                    sb.get('senses', ''),
                    sb.get('languages', ''),
                    sb.get('challenge_rating', ''),
                    sb.get('traits_json', '[]'),
                    sb.get('actions_json', '[]'),
                    sb.get('bonus_actions_json', '[]'),
                    sb.get('reactions_json', '[]'),
                    sb.get('legendary_actions_json', '[]')
                ))
    
    def get_schema_version(self) -> int:
        """Get current schema version."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            return row['version'] if row else 0
    
    def insert_spell(self, spell_data: dict) -> int:
        """
        Insert a new spell into the database.
        
        Args:
            spell_data: Dictionary with keys:
                - name, level, casting_time, ritual, range_value, components,
                - duration, concentration, description, source, classes, tags
        
        Returns:
            The new spell's ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert main spell data
            cursor.execute("""
                INSERT INTO spells (
                    name, level, casting_time, ritual, range_value, 
                    components, duration, concentration, description, source, original_name, is_legacy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                spell_data['name'],
                spell_data['level'],
                spell_data['casting_time'],
                1 if spell_data.get('ritual', False) else 0,
                spell_data['range_value'],
                spell_data['components'],
                spell_data['duration'],
                1 if spell_data.get('concentration', False) else 0,
                spell_data.get('description', ''),
                spell_data.get('source', ''),
                spell_data.get('original_name', ''),
                1 if spell_data.get('is_legacy', False) else 0
            ))
            
            spell_id = cursor.lastrowid
            assert spell_id is not None, "Failed to get spell ID after insert"
            
            # Insert classes
            classes = spell_data.get('classes', [])
            if classes:
                cursor.executemany(
                    "INSERT INTO spell_classes (spell_id, class_name) VALUES (?, ?)",
                    [(spell_id, cls) for cls in classes]
                )
            
            # Insert tags (normalized)
            tags = spell_data.get('tags', [])
            if tags:
                normalized_tags = [self.normalize_tag(tag) for tag in tags]
                cursor.executemany(
                    "INSERT INTO spell_tags (spell_id, tag) VALUES (?, ?)",
                    [(spell_id, tag) for tag in normalized_tags]
                )
            
            return spell_id
    
    def update_spell(self, spell_id: int, spell_data: dict) -> bool:
        """
        Update an existing spell.
        
        Args:
            spell_id: The spell's database ID
            spell_data: Dictionary with spell data (same as insert_spell)
        
        Returns:
            True if successful
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Update main spell data (including is_modified and is_legacy)
            cursor.execute("""
                UPDATE spells SET
                    name = ?, level = ?, casting_time = ?, ritual = ?,
                    range_value = ?, components = ?, duration = ?,
                    concentration = ?, description = ?, source = ?,
                    is_modified = ?, is_legacy = ?
                WHERE id = ?
            """, (
                spell_data['name'],
                spell_data['level'],
                spell_data['casting_time'],
                1 if spell_data.get('ritual', False) else 0,
                spell_data['range_value'],
                spell_data['components'],
                spell_data['duration'],
                1 if spell_data.get('concentration', False) else 0,
                spell_data.get('description', ''),
                spell_data.get('source', ''),
                1 if spell_data.get('is_modified', False) else 0,
                1 if spell_data.get('is_legacy', False) else 0,
                spell_id
            ))
            
            # Update classes - delete and re-insert
            cursor.execute("DELETE FROM spell_classes WHERE spell_id = ?", (spell_id,))
            classes = spell_data.get('classes', [])
            if classes:
                cursor.executemany(
                    "INSERT INTO spell_classes (spell_id, class_name) VALUES (?, ?)",
                    [(spell_id, cls) for cls in classes]
                )
            
            # Update tags - delete and re-insert (normalized)
            cursor.execute("DELETE FROM spell_tags WHERE spell_id = ?", (spell_id,))
            tags = spell_data.get('tags', [])
            if tags:
                normalized_tags = [self.normalize_tag(tag) for tag in tags]
                cursor.executemany(
                    "INSERT INTO spell_tags (spell_id, tag) VALUES (?, ?)",
                    [(spell_id, tag) for tag in normalized_tags]
                )
            
            return cursor.rowcount > 0
    
    def delete_spell(self, spell_id: int) -> bool:
        """Delete a spell by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM spells WHERE id = ?", (spell_id,))
            return cursor.rowcount > 0
    
    def delete_spell_by_name(self, name: str) -> bool:
        """Delete a spell by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM spells WHERE name = ? COLLATE NOCASE", (name,))
            return cursor.rowcount > 0
    
    def get_spell_by_id(self, spell_id: int) -> Optional[dict]:
        """Get a spell by its ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM spells WHERE id = ?", (spell_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_spell_dict(conn, row)
            return None
    
    def get_spell_by_name(self, name: str) -> Optional[dict]:
        """Get a spell by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM spells WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_spell_dict(conn, row)
            return None
    
    def get_spell_id_by_name(self, name: str) -> Optional[int]:
        """Get a spell's ID by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM spells WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            return row['id'] if row else None
    
    def get_all_spells(self) -> List[dict]:
        """Get all spells from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM spells ORDER BY level, name")
            rows = cursor.fetchall()
            
            # Use batch query optimization to avoid N+1 queries
            return self._rows_to_spell_dicts_batch(conn, rows)
    
    def spell_exists(self, name: str) -> bool:
        """Check if a spell with the given name exists."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM spells WHERE name = ? COLLATE NOCASE LIMIT 1", (name,))
            return cursor.fetchone() is not None
    
    def get_spell_count(self) -> int:
        """Get total number of spells."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM spells")
            return cursor.fetchone()['count']
    
    def get_all_sources(self) -> List[str]:
        """Get all unique sources."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT source FROM spells 
                WHERE source IS NOT NULL AND source != '' 
                ORDER BY source
            """)
            return [row['source'] for row in cursor.fetchall()]
    
    def get_all_casting_times(self) -> List[str]:
        """Get all unique casting times."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT casting_time FROM spells 
                WHERE casting_time IS NOT NULL AND casting_time != '' 
                ORDER BY casting_time
            """)
            return [row['casting_time'] for row in cursor.fetchall()]
    
    def get_all_durations(self) -> List[str]:
        """Get all unique durations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT duration FROM spells 
                WHERE duration IS NOT NULL AND duration != '' 
                ORDER BY duration
            """)
            return [row['duration'] for row in cursor.fetchall()]
    
    def get_all_range_values(self) -> List[int]:
        """Get all unique range_value integers, sorted for display."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT range_value FROM spells ORDER BY range_value")
            return [row['range_value'] for row in cursor.fetchall()]
    
    def get_all_ranges_for_display(self) -> List[tuple]:
        """Get all unique range values with display labels, ordered appropriately.
        Returns list of (value, display_label) tuples.
        Order: Self (0), Touch (3), numeric feet ascending, Special (2), Sight (1), miles (negative, ascending by abs)
        """
        raw_values = self.get_all_range_values()
        
        results = []
        feet_values = []
        mile_values = []
        
        for val in raw_values:
            if val == 0:  # Self
                results.insert(0, (0, "Self"))
            elif val == 1:  # Sight - added later
                pass
            elif val == 2:  # Special - added later
                pass
            elif val == 3:  # Touch
                results.append((3, "Touch"))
            elif val < 0:  # Miles
                mile_values.append(val)
            else:  # Regular feet
                feet_values.append(val)
        
        # Add feet values sorted ascending
        feet_values.sort()
        for val in feet_values:
            results.append((val, f"{val} ft"))
        
        # Add Special and Sight at end
        if 2 in raw_values:
            results.append((2, "Special"))
        if 1 in raw_values:
            results.append((1, "Sight"))
        
        # Add mile values (negative) sorted by absolute value
        mile_values.sort(key=lambda x: abs(x))
        for val in mile_values:
            miles = abs(val)
            label = "1 mile" if miles == 1 else f"{miles} miles"
            results.append((val, label))
        
        return results
    
    def get_all_tags(self) -> List[str]:
        """Get all unique tags."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT tag FROM spell_tags ORDER BY tag")
            return [row['tag'] for row in cursor.fetchall()]
    
    def get_all_classes(self) -> List[str]:
        """Get all unique class names used in spells."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT class_name FROM spell_classes ORDER BY class_name")
            return [row['class_name'] for row in cursor.fetchall()]
    
    def _row_to_spell_dict(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
        """Convert a database row to a spell dictionary.
        Note: For batch operations, use _rows_to_spell_dicts_batch() instead to avoid N+1 queries.
        """
        cursor = conn.cursor()
        spell_id = row['id']
        
        # Get classes
        cursor.execute("SELECT class_name FROM spell_classes WHERE spell_id = ?", (spell_id,))
        classes = [r['class_name'] for r in cursor.fetchall()]
        
        # Get tags
        cursor.execute("SELECT tag FROM spell_tags WHERE spell_id = ?", (spell_id,))
        tags = [r['tag'] for r in cursor.fetchall()]
        
        return {
            'id': spell_id,
            'name': row['name'],
            'level': row['level'],
            'casting_time': row['casting_time'],
            'ritual': bool(row['ritual']),
            'range_value': row['range_value'],
            'components': row['components'],
            'duration': row['duration'],
            'concentration': bool(row['concentration']),
            'description': row['description'] or '',
            'source': row['source'] or '',
            'classes': classes,
            'tags': tags,
            'is_modified': bool(row['is_modified']) if 'is_modified' in row.keys() else False,
            'original_name': row['original_name'] if 'original_name' in row.keys() else '',
            'is_legacy': bool(row['is_legacy']) if 'is_legacy' in row.keys() else False,
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
    
    def _rows_to_spell_dicts_batch(self, conn: sqlite3.Connection, rows: List[sqlite3.Row]) -> List[dict]:
        """Convert multiple database rows to spell dictionaries using batch queries.
        This avoids the N+1 query problem by fetching all classes and tags in just 2 queries.
        """
        if not rows:
            return []
        
        cursor = conn.cursor()
        
        # Get all spell IDs
        spell_ids = [row['id'] for row in rows]
        
        # Batch fetch all classes for these spells (1 query instead of N)
        placeholders = ','.join('?' * len(spell_ids))
        cursor.execute(f"""
            SELECT spell_id, class_name 
            FROM spell_classes 
            WHERE spell_id IN ({placeholders})
        """, spell_ids)
        
        # Build a dictionary mapping spell_id -> list of classes
        classes_by_spell = {}
        for r in cursor.fetchall():
            spell_id = r['spell_id']
            if spell_id not in classes_by_spell:
                classes_by_spell[spell_id] = []
            classes_by_spell[spell_id].append(r['class_name'])
        
        # Batch fetch all tags for these spells (1 query instead of N)
        cursor.execute(f"""
            SELECT spell_id, tag 
            FROM spell_tags 
            WHERE spell_id IN ({placeholders})
        """, spell_ids)
        
        # Build a dictionary mapping spell_id -> list of tags
        tags_by_spell = {}
        for r in cursor.fetchall():
            spell_id = r['spell_id']
            if spell_id not in tags_by_spell:
                tags_by_spell[spell_id] = []
            tags_by_spell[spell_id].append(r['tag'])
        
        # Convert rows to dictionaries using the pre-fetched data
        result = []
        for row in rows:
            spell_id = row['id']
            result.append({
                'id': spell_id,
                'name': row['name'],
                'level': row['level'],
                'casting_time': row['casting_time'],
                'ritual': bool(row['ritual']),
                'range_value': row['range_value'],
                'components': row['components'],
                'duration': row['duration'],
                'concentration': bool(row['concentration']),
                'description': row['description'] or '',
                'source': row['source'] or '',
                'classes': classes_by_spell.get(spell_id, []),
                'tags': tags_by_spell.get(spell_id, []),
                'is_modified': bool(row['is_modified']) if 'is_modified' in row.keys() else False,
                'original_name': row['original_name'] if 'original_name' in row.keys() else '',
                'is_legacy': bool(row['is_legacy']) if 'is_legacy' in row.keys() else False,
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        
        return result
    
    def search_spells(self, 
                      search_text: str = "",
                      level: int = -1,
                      class_name: Optional[str] = None,
                      ritual: Optional[bool] = None,
                      concentration: Optional[bool] = None,
                      min_range: int = 0,
                      source: Optional[str] = None,
                      tags: Optional[List[str]] = None,
                      tags_mode: str = "has_all",
                      casting_time: Optional[str] = None,
                      duration: Optional[str] = None,
                      has_verbal: Optional[bool] = None,
                      has_somatic: Optional[bool] = None,
                      has_material: Optional[bool] = None) -> List[dict]:
        """
        Search spells with various filters using optimized SQL queries.
        
        Args:
            search_text: Text to search in name, description, and tags
            level: Spell level (-1 for all)
            class_name: Filter by class
            ritual: Filter by ritual (None for any)
            concentration: Filter by concentration (None for any)
            min_range: Minimum range (0 for no filter, sight/touch always pass)
            source: Filter by source (exact match)
            tags: List of tags to filter by
            tags_mode: "has_all" (must have ALL), "has_any" (must have at least one), "has_none" (must have none)
            casting_time: Filter by casting time (exact match)
            duration: Filter by duration (exact match)
            has_verbal: Filter by verbal component
            has_somatic: Filter by somatic component
            has_material: Filter by material component
        
        Returns:
            List of matching spell dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT DISTINCT s.* FROM spells s"
            conditions = []
            params = []
            
            # Join for class filtering
            if class_name:
                query += " INNER JOIN spell_classes sc ON s.id = sc.spell_id"
                conditions.append("sc.class_name = ? COLLATE NOCASE")
                params.append(class_name)
            
            # Tag filtering based on mode
            if tags:
                if tags_mode == "has_all":
                    # Must have ALL specified tags (use JOINs)
                    for i, tag in enumerate(tags):
                        alias = f"st{i}"
                        query += f" INNER JOIN spell_tags {alias} ON s.id = {alias}.spell_id"
                        conditions.append(f"{alias}.tag = ? COLLATE NOCASE")
                        params.append(tag)
                elif tags_mode == "has_any":
                    # Must have at least ONE specified tag (use EXISTS with OR)
                    tag_conditions = " OR ".join(["st.tag = ? COLLATE NOCASE" for _ in tags])
                    conditions.append(f"EXISTS (SELECT 1 FROM spell_tags st WHERE st.spell_id = s.id AND ({tag_conditions}))")
                    params.extend(tags)
                elif tags_mode == "has_none":
                    # Must NOT have any of the specified tags
                    tag_conditions = " OR ".join(["st.tag = ? COLLATE NOCASE" for _ in tags])
                    conditions.append(f"NOT EXISTS (SELECT 1 FROM spell_tags st WHERE st.spell_id = s.id AND ({tag_conditions}))")
                    params.extend(tags)
            
            # Add WHERE clause conditions
            if search_text:
                # Search in name, description, and check if any tag matches
                conditions.append("""(
                    s.name LIKE ? COLLATE NOCASE OR 
                    s.description LIKE ? COLLATE NOCASE OR
                    EXISTS (SELECT 1 FROM spell_tags st WHERE st.spell_id = s.id AND st.tag LIKE ? COLLATE NOCASE)
                )""")
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern, search_pattern])
            
            if level >= 0:
                conditions.append("s.level = ?")
                params.append(level)
            
            if ritual is not None:
                conditions.append("s.ritual = ?")
                params.append(1 if ritual else 0)
            
            if concentration is not None:
                conditions.append("s.concentration = ?")
                params.append(1 if concentration else 0)
            
            if min_range > 0:
                # range_value=1 (Sight) and range_value=3 (Touch) always pass
                conditions.append("(s.range_value = 1 OR s.range_value = 3 OR s.range_value >= ?)")
                params.append(min_range)
            
            if source:
                conditions.append("s.source = ? COLLATE NOCASE")
                params.append(source)
            
            if casting_time:
                conditions.append("s.casting_time = ? COLLATE NOCASE")
                params.append(casting_time)
            
            if duration:
                conditions.append("s.duration = ? COLLATE NOCASE")
                params.append(duration)
            
            # Component filters using LIKE on the components string
            if has_verbal is not None:
                if has_verbal:
                    conditions.append("UPPER(s.components) LIKE '%V%'")
                else:
                    conditions.append("UPPER(s.components) NOT LIKE '%V%'")
            
            if has_somatic is not None:
                if has_somatic:
                    conditions.append("UPPER(s.components) LIKE '%S%'")
                else:
                    conditions.append("UPPER(s.components) NOT LIKE '%S%'")
            
            if has_material is not None:
                if has_material:
                    conditions.append("UPPER(s.components) LIKE '%M%'")
                else:
                    conditions.append("UPPER(s.components) NOT LIKE '%M%'")
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY s.level, s.name COLLATE NOCASE"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Use batch query optimization to avoid N+1 queries
            return self._rows_to_spell_dicts_batch(conn, rows)
    
    def get_filtered_spell_ids(self,
                               search_text: str = "",
                               level: int = -1,
                               class_name: Optional[str] = None,
                               ritual: Optional[bool] = None,
                               concentration: Optional[bool] = None,
                               min_range: int = 0,
                               source: Optional[str] = None,
                               tags: Optional[List[str]] = None,
                               casting_time: Optional[str] = None,
                               duration: Optional[str] = None,
                               has_verbal: Optional[bool] = None,
                               has_somatic: Optional[bool] = None,
                               has_material: Optional[bool] = None) -> List[int]:
        """
        Get IDs of spells matching filters (faster than full search for large result sets).
        Uses same parameters as search_spells.
        
        Returns:
            List of spell IDs matching the criteria
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT DISTINCT s.id FROM spells s"
            conditions = []
            params = []
            
            # Join for class filtering
            if class_name:
                query += " INNER JOIN spell_classes sc ON s.id = sc.spell_id"
                conditions.append("sc.class_name = ? COLLATE NOCASE")
                params.append(class_name)
            
            # Join for tag filtering
            if tags:
                for i, tag in enumerate(tags):
                    alias = f"st{i}"
                    query += f" INNER JOIN spell_tags {alias} ON s.id = {alias}.spell_id"
                    conditions.append(f"{alias}.tag = ? COLLATE NOCASE")
                    params.append(tag)
            
            # Build WHERE conditions (same as search_spells)
            if search_text:
                conditions.append("""(
                    s.name LIKE ? COLLATE NOCASE OR 
                    s.description LIKE ? COLLATE NOCASE OR
                    EXISTS (SELECT 1 FROM spell_tags st WHERE st.spell_id = s.id AND st.tag LIKE ? COLLATE NOCASE)
                )""")
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern, search_pattern])
            
            if level >= 0:
                conditions.append("s.level = ?")
                params.append(level)
            
            if ritual is not None:
                conditions.append("s.ritual = ?")
                params.append(1 if ritual else 0)
            
            if concentration is not None:
                conditions.append("s.concentration = ?")
                params.append(1 if concentration else 0)
            
            if min_range > 0:
                conditions.append("(s.range_value = 1 OR s.range_value = 3 OR s.range_value >= ?)")
                params.append(min_range)
            
            if source:
                conditions.append("s.source = ? COLLATE NOCASE")
                params.append(source)
            
            if casting_time:
                conditions.append("s.casting_time = ? COLLATE NOCASE")
                params.append(casting_time)
            
            if duration:
                conditions.append("s.duration = ? COLLATE NOCASE")
                params.append(duration)
            
            if has_verbal is not None:
                if has_verbal:
                    conditions.append("UPPER(s.components) LIKE '%V%'")
                else:
                    conditions.append("UPPER(s.components) NOT LIKE '%V%'")
            
            if has_somatic is not None:
                if has_somatic:
                    conditions.append("UPPER(s.components) LIKE '%S%'")
                else:
                    conditions.append("UPPER(s.components) NOT LIKE '%S%'")
            
            if has_material is not None:
                if has_material:
                    conditions.append("UPPER(s.components) LIKE '%M%'")
                else:
                    conditions.append("UPPER(s.components) NOT LIKE '%M%'")
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            cursor.execute(query, params)
            return [row[0] for row in cursor.fetchall()]
    
    def bulk_insert_spells(self, spells: List[dict]) -> int:
        """
        Insert multiple spells at once (more efficient for imports).
        
        Args:
            spells: List of spell dictionaries
        
        Returns:
            Number of spells inserted
        """
        inserted = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for spell_data in spells:
                try:
                    # Check if spell exists
                    cursor.execute(
                        "SELECT id FROM spells WHERE name = ? COLLATE NOCASE", 
                        (spell_data['name'],)
                    )
                    if cursor.fetchone():
                        continue  # Skip duplicates
                    
                    # Insert spell (for official spells, original_name = name)
                    original_name = spell_data.get('original_name', spell_data['name'])
                    cursor.execute("""
                        INSERT INTO spells (
                            name, level, casting_time, ritual, range_value,
                            components, duration, concentration, description, source, original_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        spell_data['name'],
                        spell_data['level'],
                        spell_data['casting_time'],
                        1 if spell_data.get('ritual', False) else 0,
                        spell_data['range_value'],
                        spell_data['components'],
                        spell_data['duration'],
                        1 if spell_data.get('concentration', False) else 0,
                        spell_data.get('description', ''),
                        spell_data.get('source', ''),
                        original_name
                    ))
                    
                    spell_id = cursor.lastrowid
                    
                    # Insert classes
                    classes = spell_data.get('classes', [])
                    if classes:
                        cursor.executemany(
                            "INSERT INTO spell_classes (spell_id, class_name) VALUES (?, ?)",
                            [(spell_id, cls) for cls in classes]
                        )
                    
                    # Insert tags (normalized)
                    tags = spell_data.get('tags', [])
                    if tags:
                        normalized_tags = [self.normalize_tag(tag) for tag in tags]
                        cursor.executemany(
                            "INSERT INTO spell_tags (spell_id, tag) VALUES (?, ?)",
                            [(spell_id, tag) for tag in normalized_tags]
                        )
                    
                    inserted += 1
                    
                except sqlite3.IntegrityError:
                    continue  # Skip duplicates
            
            conn.commit()
        
        return inserted
    
    def clear_all_spells(self):
        """Remove all spells from the database. Use with caution!"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM spell_tags")
            cursor.execute("DELETE FROM spell_classes")
            cursor.execute("DELETE FROM spells")
    
    # ==================== Stat Block Methods ====================
    
    def insert_stat_block(self, stat_block_data: dict) -> int:
        """
        Insert a new stat block into the database.
        
        Args:
            stat_block_data: Dictionary with stat block fields
        
        Returns:
            The new stat block's ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO stat_blocks (
                    spell_id, name, size, creature_type, creature_subtype, alignment,
                    armor_class, hit_points, speed, abilities_json,
                    damage_resistances, damage_immunities, condition_immunities,
                    senses, languages, challenge_rating,
                    traits_json, actions_json, bonus_actions_json, 
                    reactions_json, legendary_actions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stat_block_data['spell_id'],
                stat_block_data['name'],
                stat_block_data.get('size', 'Medium'),
                stat_block_data.get('creature_type', ''),
                stat_block_data.get('creature_subtype', ''),
                stat_block_data.get('alignment', 'Neutral'),
                stat_block_data.get('armor_class', ''),
                stat_block_data.get('hit_points', ''),
                stat_block_data.get('speed', ''),
                json.dumps(stat_block_data.get('abilities')) if stat_block_data.get('abilities') else None,
                stat_block_data.get('damage_resistances', ''),
                stat_block_data.get('damage_immunities', ''),
                stat_block_data.get('condition_immunities', ''),
                stat_block_data.get('senses', ''),
                stat_block_data.get('languages', ''),
                stat_block_data.get('challenge_rating', ''),
                json.dumps(stat_block_data.get('traits', [])),
                json.dumps(stat_block_data.get('actions', [])),
                json.dumps(stat_block_data.get('bonus_actions', [])),
                json.dumps(stat_block_data.get('reactions', [])),
                json.dumps(stat_block_data.get('legendary_actions', []))
            ))
            
            stat_block_id = cursor.lastrowid
            assert stat_block_id is not None, "Failed to get stat block ID after insert"
            return stat_block_id
    
    def update_stat_block(self, stat_block_id: int, stat_block_data: dict) -> bool:
        """Update an existing stat block."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE stat_blocks SET
                    name = ?, size = ?, creature_type = ?, creature_subtype = ?,
                    alignment = ?, armor_class = ?, hit_points = ?, speed = ?,
                    abilities_json = ?, damage_resistances = ?, damage_immunities = ?,
                    condition_immunities = ?, senses = ?, languages = ?,
                    challenge_rating = ?, traits_json = ?, actions_json = ?,
                    bonus_actions_json = ?, reactions_json = ?, legendary_actions_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                stat_block_data['name'],
                stat_block_data.get('size', 'Medium'),
                stat_block_data.get('creature_type', ''),
                stat_block_data.get('creature_subtype', ''),
                stat_block_data.get('alignment', 'Neutral'),
                stat_block_data.get('armor_class', ''),
                stat_block_data.get('hit_points', ''),
                stat_block_data.get('speed', ''),
                json.dumps(stat_block_data.get('abilities')) if stat_block_data.get('abilities') else None,
                stat_block_data.get('damage_resistances', ''),
                stat_block_data.get('damage_immunities', ''),
                stat_block_data.get('condition_immunities', ''),
                stat_block_data.get('senses', ''),
                stat_block_data.get('languages', ''),
                stat_block_data.get('challenge_rating', ''),
                json.dumps(stat_block_data.get('traits', [])),
                json.dumps(stat_block_data.get('actions', [])),
                json.dumps(stat_block_data.get('bonus_actions', [])),
                json.dumps(stat_block_data.get('reactions', [])),
                json.dumps(stat_block_data.get('legendary_actions', [])),
                stat_block_id
            ))
            
            return cursor.rowcount > 0
    
    def delete_stat_block(self, stat_block_id: int) -> bool:
        """Delete a stat block by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stat_blocks WHERE id = ?", (stat_block_id,))
            return cursor.rowcount > 0
    
    def get_stat_blocks_for_spell(self, spell_id: int) -> List[dict]:
        """Get all stat blocks linked to a spell."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stat_blocks WHERE spell_id = ? ORDER BY name", (spell_id,))
            rows = cursor.fetchall()
            
            return [self._row_to_stat_block_dict(row) for row in rows]
    
    def get_stat_blocks_for_spell_by_name(self, spell_name: str) -> List[dict]:
        """Get all stat blocks linked to a spell by spell name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Join with spells table to get by name
            cursor.execute("""
                SELECT sb.* FROM stat_blocks sb
                JOIN spells s ON sb.spell_id = s.id
                WHERE s.name = ? COLLATE NOCASE
                ORDER BY sb.name
            """, (spell_name,))
            rows = cursor.fetchall()
            
            return [self._row_to_stat_block_dict(row) for row in rows]
    
    def get_stat_block_by_id(self, stat_block_id: int) -> Optional[dict]:
        """Get a single stat block by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stat_blocks WHERE id = ?", (stat_block_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_stat_block_dict(row)
            return None
    
    def _row_to_stat_block_dict(self, row) -> dict:
        """Convert a database row to a stat block dictionary."""
        return {
            'id': row['id'],
            'spell_id': row['spell_id'],
            'name': row['name'],
            'size': row['size'],
            'creature_type': row['creature_type'],
            'creature_subtype': row['creature_subtype'] or '',
            'alignment': row['alignment'] or 'Neutral',
            'armor_class': row['armor_class'],
            'hit_points': row['hit_points'],
            'speed': row['speed'],
            'abilities': json.loads(row['abilities_json']) if row['abilities_json'] else None,
            'damage_resistances': row['damage_resistances'] or '',
            'damage_immunities': row['damage_immunities'] or '',
            'condition_immunities': row['condition_immunities'] or '',
            'senses': row['senses'] or '',
            'languages': row['languages'] or '',
            'challenge_rating': row['challenge_rating'] or '',
            'traits': json.loads(row['traits_json']) if row['traits_json'] else [],
            'actions': json.loads(row['actions_json']) if row['actions_json'] else [],
            'bonus_actions': json.loads(row['bonus_actions_json']) if row['bonus_actions_json'] else [],
            'reactions': json.loads(row['reactions_json']) if row['reactions_json'] else [],
            'legendary_actions': json.loads(row['legendary_actions_json']) if row['legendary_actions_json'] else []
        }
    
    def get_spells_with_stat_blocks(self) -> List[int]:
        """Get list of spell IDs that have stat blocks."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT spell_id FROM stat_blocks")
            return [row['spell_id'] for row in cursor.fetchall()]

