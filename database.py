"""
SQLite database module for D&D Spellbook Application.
Handles database creation, migrations, and spell persistence.
"""

import sqlite3
import os
import sys
import json
from typing import List, Optional, Tuple
from contextlib import contextmanager


class SpellDatabase:
    """SQLite database handler for spell storage."""
    
    DEFAULT_DB_PATH = "spellbook.db"
    SCHEMA_VERSION = 11  # Fix missing subclass feature placeholders for Bard and other classes
    
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
            
            # Main spells table (includes all columns from migrations)
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
                    original_name TEXT DEFAULT '',
                    is_legacy INTEGER NOT NULL DEFAULT 0,
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
            
            # Create content tables (lineages, feats, backgrounds, classes)
            self._create_content_tables(cursor)
            
            # Track if this is a fresh database (for initial data population)
            is_fresh_db = False
            
            # Set schema version if not exists
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (self.SCHEMA_VERSION,))
                is_fresh_db = True
            
            # Create trigger for updated_at
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_spell_timestamp 
                AFTER UPDATE ON spells
                BEGIN
                    UPDATE spells SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
            """)
            
            # Run migrations (for upgrading existing databases)
            self._run_migrations(conn)
            
            # If this is a fresh database, populate content tables from JSON
            if is_fresh_db:
                print("Populating content tables from bundled JSON files...")
                self._migrate_json_to_database(cursor)
    
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
        
        # Migration to version 8: add content tables (lineages, feats, backgrounds, classes)
        if current_version < 8:
            self._create_content_tables(cursor)
            self._migrate_json_to_database(cursor)
            cursor.execute("UPDATE schema_version SET version = 8")
            current_version = 8
        
        # Migration to version 9: fix class_features_json (was using wrong field name)
        if current_version < 9:
            self._remigrate_class_features(cursor)
            cursor.execute("UPDATE schema_version SET version = 9")
            current_version = 9
        
        # Migration to version 10: add missing class columns
        if current_version < 10:
            self._add_class_columns_v10(cursor)
            cursor.execute("UPDATE schema_version SET version = 10")
            current_version = 10
        
        # Migration to version 11: fix missing subclass feature placeholders
        if current_version < 11:
            self._fix_subclass_features_v11(cursor)
            cursor.execute("UPDATE schema_version SET version = 11")
            current_version = 11
    
    def _create_content_tables(self, cursor):
        """Create tables for lineages, feats, backgrounds, and classes."""
        # Lineages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lineages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                description TEXT DEFAULT '',
                creature_type TEXT DEFAULT 'Humanoid',
                size TEXT DEFAULT 'Medium',
                speed INTEGER DEFAULT 30,
                traits_json TEXT DEFAULT '[]',
                source TEXT DEFAULT '',
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                is_legacy INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lineages_name ON lineages(name)")
        
        # Feats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                type TEXT DEFAULT '',
                is_spellcasting INTEGER NOT NULL DEFAULT 0,
                spell_lists_json TEXT DEFAULT '[]',
                spells_num_json TEXT DEFAULT '{}',
                has_prereq INTEGER NOT NULL DEFAULT 0,
                prereq TEXT DEFAULT '',
                set_spells_json TEXT DEFAULT '[]',
                description TEXT DEFAULT '',
                source TEXT DEFAULT '',
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                is_legacy INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feats_name ON feats(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feats_type ON feats(type)")
        
        # Backgrounds table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backgrounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                source TEXT DEFAULT '',
                is_legacy INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                skills_json TEXT DEFAULT '[]',
                other_proficiencies_json TEXT DEFAULT '[]',
                ability_scores_json TEXT DEFAULT '[]',
                feats_json TEXT DEFAULT '[]',
                equipment TEXT DEFAULT '',
                features_json TEXT DEFAULT '[]',
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_backgrounds_name ON backgrounds(name)")
        
        # Classes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                hit_die INTEGER NOT NULL DEFAULT 8,
                primary_ability TEXT DEFAULT '',
                saving_throws_json TEXT DEFAULT '[]',
                armor_proficiencies_json TEXT DEFAULT '[]',
                weapon_proficiencies_json TEXT DEFAULT '[]',
                tool_proficiencies_json TEXT DEFAULT '[]',
                skill_proficiencies_json TEXT DEFAULT '[]',
                num_skills INTEGER DEFAULT 2,
                starting_equipment_json TEXT DEFAULT '[]',
                class_features_json TEXT DEFAULT '[]',
                spellcasting_json TEXT DEFAULT 'null',
                subclass_name TEXT DEFAULT '',
                subclass_level INTEGER DEFAULT 3,
                class_table_columns_json TEXT DEFAULT '[]',
                trackable_features_json TEXT DEFAULT '[]',
                class_spells_json TEXT DEFAULT '[]',
                unarmored_defense TEXT DEFAULT '',
                source TEXT DEFAULT '',
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                is_legacy INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_classes_name ON classes(name)")
        
        # Subclasses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subclasses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE,
                class_id INTEGER NOT NULL,
                description TEXT DEFAULT '',
                features_json TEXT DEFAULT '[]',
                source TEXT DEFAULT '',
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                is_legacy INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
                UNIQUE(name, class_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subclasses_name ON subclasses(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_subclasses_class_id ON subclasses(class_id)")
    
    def _migrate_json_to_database(self, cursor):
        """Migrate data from JSON files to database tables."""
        import os
        import sys
        
        def get_json_path(filename):
            # For bundled PyInstaller app, look in _MEIPASS for bundled JSON files
            if getattr(sys, 'frozen', False):
                base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base, filename)
        
        # Migrate lineages
        lineages_path = get_json_path('lineages.json')
        if os.path.exists(lineages_path):
            try:
                with open(lineages_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for lin in data.get('lineages', []):
                    cursor.execute("""
                        INSERT OR IGNORE INTO lineages 
                        (name, description, creature_type, size, speed, traits_json, source, is_official, is_custom, is_legacy)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lin.get('name', ''),
                        lin.get('description', ''),
                        lin.get('creature_type', 'Humanoid'),
                        lin.get('size', 'Medium'),
                        lin.get('speed', 30),
                        json.dumps(lin.get('traits', [])),
                        lin.get('source', ''),
                        1 if lin.get('is_official', True) else 0,
                        1 if lin.get('is_custom', False) else 0,
                        1 if lin.get('is_legacy', False) else 0
                    ))
                print(f"Migrated {len(data.get('lineages', []))} lineages to database")
            except Exception as e:
                print(f"Error migrating lineages: {e}")
        
        # Migrate feats
        feats_path = get_json_path('feats.json')
        if os.path.exists(feats_path):
            try:
                with open(feats_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for feat in data.get('feats', []):
                    cursor.execute("""
                        INSERT OR IGNORE INTO feats 
                        (name, type, is_spellcasting, spell_lists_json, spells_num_json, has_prereq, prereq, 
                         set_spells_json, description, source, is_official, is_custom, is_legacy)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        feat.get('name', ''),
                        feat.get('type', ''),
                        1 if feat.get('is_spellcasting', False) else 0,
                        json.dumps(feat.get('spell_lists', [])),
                        json.dumps(feat.get('spells_num', {})),
                        1 if feat.get('has_prereq', False) else 0,
                        feat.get('prereq', ''),
                        json.dumps(feat.get('set_spells', [])),
                        feat.get('description', ''),
                        feat.get('source', ''),
                        1 if feat.get('is_official', True) else 0,
                        1 if feat.get('is_custom', False) else 0,
                        1 if feat.get('is_legacy', False) else 0
                    ))
                print(f"Migrated {len(data.get('feats', []))} feats to database")
            except Exception as e:
                print(f"Error migrating feats: {e}")
        
        # Migrate backgrounds
        backgrounds_path = get_json_path('backgrounds.json')
        if os.path.exists(backgrounds_path):
            try:
                with open(backgrounds_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for bg in data.get('backgrounds', []):
                    cursor.execute("""
                        INSERT OR IGNORE INTO backgrounds 
                        (name, source, is_legacy, description, skills_json, other_proficiencies_json,
                         ability_scores_json, feats_json, equipment, features_json, is_official, is_custom)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        bg.get('name', ''),
                        bg.get('source', ''),
                        1 if bg.get('is_legacy', False) else 0,
                        bg.get('description', ''),
                        json.dumps(bg.get('skills', [])),
                        json.dumps(bg.get('other_proficiencies', [])),
                        json.dumps(bg.get('ability_scores', [])),
                        json.dumps(bg.get('feats', [])),
                        bg.get('equipment', ''),
                        json.dumps(bg.get('features', [])),
                        1 if bg.get('is_official', True) else 0,
                        1 if bg.get('is_custom', False) else 0
                    ))
                print(f"Migrated {len(data.get('backgrounds', []))} backgrounds to database")
            except Exception as e:
                print(f"Error migrating backgrounds: {e}")
        
        # Migrate classes
        classes_path = get_json_path('classes.json')
        if os.path.exists(classes_path):
            try:
                with open(classes_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                classes_data = data.get('classes', {})
                for class_name, cls in classes_data.items():
                    # Build spellcasting info from JSON fields
                    spellcasting_info = None
                    if cls.get('is_spellcaster', False):
                        spellcasting_info = {
                            'is_spellcaster': True,
                            'ability': cls.get('spellcasting_ability', '')
                        }
                    cursor.execute("""
                        INSERT OR IGNORE INTO classes 
                        (name, hit_die, primary_ability, saving_throws_json, armor_proficiencies_json,
                         weapon_proficiencies_json, tool_proficiencies_json, skill_proficiencies_json,
                         num_skills, starting_equipment_json, class_features_json, spellcasting_json,
                         subclass_name, subclass_level, class_table_columns_json, trackable_features_json,
                         class_spells_json, unarmored_defense, source, is_official, is_custom, is_legacy)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        class_name,
                        cls.get('hit_die', 'd8'),
                        cls.get('primary_ability', ''),
                        json.dumps(cls.get('saving_throw_proficiencies', [])),
                        json.dumps(cls.get('armor_proficiencies', [])),
                        json.dumps(cls.get('weapon_proficiencies', [])),
                        json.dumps(cls.get('tool_proficiencies', [])),
                        json.dumps(cls.get('skill_proficiency_options', [])),
                        cls.get('skill_proficiency_choices', 2),
                        json.dumps(cls.get('starting_equipment_options', [])),
                        json.dumps(cls.get('levels', {})),
                        json.dumps(spellcasting_info) if spellcasting_info else 'null',
                        cls.get('subclass_name', ''),
                        cls.get('subclass_level', 3),
                        json.dumps(cls.get('class_table_columns', [])),
                        json.dumps(cls.get('trackable_features', [])),
                        json.dumps(cls.get('class_spells', [])),
                        cls.get('unarmored_defense', ''),
                        cls.get('source', ''),
                        1 if cls.get('is_official', True) else 0,
                        1 if cls.get('is_custom', False) else 0,
                        1 if cls.get('is_legacy', False) else 0
                    ))
                    
                    # Get the class ID for subclasses
                    cursor.execute("SELECT id FROM classes WHERE name = ? COLLATE NOCASE", (class_name,))
                    row = cursor.fetchone()
                    if row:
                        class_id = row[0]
                        # Migrate subclasses
                        for subclass in cls.get('subclasses', []):
                            # Store all subclass data in features_json
                            features_data = {
                                'features': subclass.get('features', []),
                                'subclass_spells': subclass.get('subclass_spells', []),
                                'armor_proficiencies': subclass.get('armor_proficiencies', []),
                                'weapon_proficiencies': subclass.get('weapon_proficiencies', []),
                                'unarmored_defense': subclass.get('unarmored_defense', ''),
                                'trackable_features': subclass.get('trackable_features', [])
                            }
                            cursor.execute("""
                                INSERT OR IGNORE INTO subclasses 
                                (name, class_id, description, features_json, source, is_official, is_custom, is_legacy)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                subclass.get('name', ''),
                                class_id,
                                subclass.get('description', ''),
                                json.dumps(features_data),
                                subclass.get('source', ''),
                                1 if subclass.get('is_official', True) else 0,
                                1 if subclass.get('is_custom', False) else 0,
                                1 if subclass.get('is_legacy', False) else 0
                            ))
                print(f"Migrated {len(classes_data)} classes to database")
            except Exception as e:
                print(f"Error migrating classes: {e}")
    
    def _remigrate_class_features(self, cursor):
        """Re-migrate class_features_json from JSON file to fix incorrect field mapping."""
        def get_json_path(filename):
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_path, filename)
        
        classes_path = get_json_path('classes.json')
        if os.path.exists(classes_path):
            try:
                with open(classes_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                classes_data = data.get('classes', {})
                updated_count = 0
                for class_name, cls in classes_data.items():
                    # Build spellcasting info from JSON fields
                    spellcasting_info = None
                    if cls.get('is_spellcaster', False):
                        spellcasting_info = {
                            'is_spellcaster': True,
                            'ability': cls.get('spellcasting_ability', '')
                        }
                    # Update the class with correct levels data
                    cursor.execute("""
                        UPDATE classes SET 
                            class_features_json = ?,
                            saving_throws_json = ?,
                            skill_proficiencies_json = ?,
                            num_skills = ?,
                            starting_equipment_json = ?,
                            spellcasting_json = ?
                        WHERE name = ? COLLATE NOCASE
                    """, (
                        json.dumps(cls.get('levels', {})),
                        json.dumps(cls.get('saving_throw_proficiencies', [])),
                        json.dumps(cls.get('skill_proficiency_options', [])),
                        cls.get('skill_proficiency_choices', 2),
                        json.dumps(cls.get('starting_equipment_options', [])),
                        json.dumps(spellcasting_info) if spellcasting_info else 'null',
                        class_name
                    ))
                    if cursor.rowcount > 0:
                        updated_count += 1
                print(f"Re-migrated class features for {updated_count} classes")
            except Exception as e:
                print(f"Error re-migrating class features: {e}")
    
    def _add_class_columns_v10(self, cursor):
        """Add missing class columns (class_table_columns, trackable_features, class_spells, unarmored_defense)."""
        # Add the missing columns if they don't exist
        cursor.execute("PRAGMA table_info(classes)")
        existing_columns = {col[1] for col in cursor.fetchall()}
        
        columns_to_add = [
            ("class_table_columns_json", "TEXT DEFAULT '[]'"),
            ("trackable_features_json", "TEXT DEFAULT '[]'"),
            ("class_spells_json", "TEXT DEFAULT '[]'"),
            ("unarmored_defense", "TEXT DEFAULT ''"),
        ]
        
        for col_name, col_def in columns_to_add:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE classes ADD COLUMN {col_name} {col_def}")
        
        # Now populate the new columns from JSON file
        def get_json_path(filename):
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_path, filename)
        
        classes_path = get_json_path('classes.json')
        if os.path.exists(classes_path):
            try:
                with open(classes_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                classes_data = data.get('classes', {})
                updated_count = 0
                for class_name, cls in classes_data.items():
                    cursor.execute("""
                        UPDATE classes SET 
                            class_table_columns_json = ?,
                            trackable_features_json = ?,
                            class_spells_json = ?,
                            unarmored_defense = ?
                        WHERE name = ? COLLATE NOCASE
                    """, (
                        json.dumps(cls.get('class_table_columns', [])),
                        json.dumps(cls.get('trackable_features', [])),
                        json.dumps(cls.get('class_spells', [])),
                        cls.get('unarmored_defense', ''),
                        class_name
                    ))
                    if cursor.rowcount > 0:
                        updated_count += 1
                print(f"Updated {updated_count} classes with missing column data")
            except Exception as e:
                print(f"Error updating class columns: {e}")
    
    def _fix_subclass_features_v11(self, cursor):
        """Fix missing subclass feature placeholders for Bard and other classes."""
        def get_json_path(filename):
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_path, filename)
        
        classes_path = get_json_path('classes.json')
        if os.path.exists(classes_path):
            try:
                with open(classes_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                classes_data = data.get('classes', {})
                updated_count = 0
                for class_name, cls in classes_data.items():
                    # Update class_features_json with the corrected levels data
                    cursor.execute("""
                        UPDATE classes SET 
                            class_features_json = ?
                        WHERE name = ? COLLATE NOCASE
                    """, (
                        json.dumps(cls.get('levels', {})),
                        class_name
                    ))
                    if cursor.rowcount > 0:
                        updated_count += 1
                print(f"Fixed subclass features for {updated_count} classes")
            except Exception as e:
                print(f"Error fixing subclass features: {e}")
    
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
    
    def add_class_to_spells(self, class_name: str, spell_names: List[str]) -> int:
        """
        Add a class to the allowed classes list of specified spells.
        This does NOT mark the spells as modified (for custom class imports).
        
        Args:
            class_name: The class name to add (e.g., "Witch")
            spell_names: List of spell names to add the class to
        
        Returns:
            Number of spells updated
        """
        if not spell_names:
            return 0
        
        updated_count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            for spell_name in spell_names:
                # Get spell ID
                cursor.execute("SELECT id FROM spells WHERE name = ? COLLATE NOCASE", (spell_name,))
                row = cursor.fetchone()
                
                if row:
                    spell_id = row['id']
                    # Check if class already exists for this spell
                    cursor.execute(
                        "SELECT 1 FROM spell_classes WHERE spell_id = ? AND class_name = ?",
                        (spell_id, class_name)
                    )
                    if not cursor.fetchone():
                        # Add the class to the spell
                        cursor.execute(
                            "INSERT INTO spell_classes (spell_id, class_name) VALUES (?, ?)",
                            (spell_id, class_name)
                        )
                        updated_count += 1
        
        return updated_count
    
    def remove_class_from_all_spells(self, class_name: str) -> int:
        """
        Remove a class from all spells' allowed classes list.
        Used when deleting a custom class.
        
        Args:
            class_name: The class name to remove
        
        Returns:
            Number of spells updated
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM spell_classes WHERE class_name = ?", (class_name,))
            return cursor.rowcount
    
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
    
    # ==================== LINEAGE METHODS ====================
    
    def get_all_lineages(self) -> List[dict]:
        """Get all lineages from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lineages ORDER BY name")
            return [self._row_to_lineage_dict(row) for row in cursor.fetchall()]
    
    def get_lineage_by_name(self, name: str) -> Optional[dict]:
        """Get a lineage by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lineages WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            return self._row_to_lineage_dict(row) if row else None
    
    def insert_lineage(self, lineage_data: dict) -> int:
        """Insert a new lineage."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO lineages (name, description, creature_type, size, speed, traits_json, 
                                      source, is_official, is_custom, is_legacy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lineage_data['name'],
                lineage_data.get('description', ''),
                lineage_data.get('creature_type', 'Humanoid'),
                lineage_data.get('size', 'Medium'),
                lineage_data.get('speed', 30),
                json.dumps(lineage_data.get('traits', [])),
                lineage_data.get('source', ''),
                1 if lineage_data.get('is_official', True) else 0,
                1 if lineage_data.get('is_custom', False) else 0,
                1 if lineage_data.get('is_legacy', False) else 0
            ))
            return cursor.lastrowid or 0
    
    def update_lineage(self, lineage_id: int, lineage_data: dict) -> bool:
        """Update an existing lineage."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE lineages SET name = ?, description = ?, creature_type = ?, size = ?, 
                speed = ?, traits_json = ?, source = ?, is_official = ?, is_custom = ?, is_legacy = ?,
                updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                lineage_data['name'],
                lineage_data.get('description', ''),
                lineage_data.get('creature_type', 'Humanoid'),
                lineage_data.get('size', 'Medium'),
                lineage_data.get('speed', 30),
                json.dumps(lineage_data.get('traits', [])),
                lineage_data.get('source', ''),
                1 if lineage_data.get('is_official', True) else 0,
                1 if lineage_data.get('is_custom', False) else 0,
                1 if lineage_data.get('is_legacy', False) else 0,
                lineage_id
            ))
            return cursor.rowcount > 0
    
    def delete_lineage(self, lineage_id: int) -> bool:
        """Delete a lineage by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM lineages WHERE id = ?", (lineage_id,))
            return cursor.rowcount > 0
    
    def _row_to_lineage_dict(self, row) -> dict:
        """Convert a database row to a lineage dictionary."""
        return {
            'id': row['id'],
            'name': row['name'],
            'description': row['description'] or '',
            'creature_type': row['creature_type'] or 'Humanoid',
            'size': row['size'] or 'Medium',
            'speed': row['speed'] or 30,
            'traits': json.loads(row['traits_json']) if row['traits_json'] else [],
            'source': row['source'] or '',
            'is_official': bool(row['is_official']),
            'is_custom': bool(row['is_custom']),
            'is_legacy': bool(row['is_legacy'])
        }
    
    # ==================== FEAT METHODS ====================
    
    def get_all_feats(self) -> List[dict]:
        """Get all feats from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM feats ORDER BY name")
            return [self._row_to_feat_dict(row) for row in cursor.fetchall()]
    
    def get_feat_by_name(self, name: str) -> Optional[dict]:
        """Get a feat by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM feats WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            return self._row_to_feat_dict(row) if row else None
    
    def insert_feat(self, feat_data: dict) -> int:
        """Insert a new feat."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feats (name, type, is_spellcasting, spell_lists_json, spells_num_json,
                                   has_prereq, prereq, set_spells_json, description, source,
                                   is_official, is_custom, is_legacy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feat_data['name'],
                feat_data.get('type', ''),
                1 if feat_data.get('is_spellcasting', False) else 0,
                json.dumps(feat_data.get('spell_lists', [])),
                json.dumps(feat_data.get('spells_num', {})),
                1 if feat_data.get('has_prereq', False) else 0,
                feat_data.get('prereq', ''),
                json.dumps(feat_data.get('set_spells', [])),
                feat_data.get('description', ''),
                feat_data.get('source', ''),
                1 if feat_data.get('is_official', True) else 0,
                1 if feat_data.get('is_custom', False) else 0,
                1 if feat_data.get('is_legacy', False) else 0
            ))
            return cursor.lastrowid or 0
    
    def update_feat(self, feat_id: int, feat_data: dict) -> bool:
        """Update an existing feat."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE feats SET name = ?, type = ?, is_spellcasting = ?, spell_lists_json = ?,
                spells_num_json = ?, has_prereq = ?, prereq = ?, set_spells_json = ?, description = ?,
                source = ?, is_official = ?, is_custom = ?, is_legacy = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                feat_data['name'],
                feat_data.get('type', ''),
                1 if feat_data.get('is_spellcasting', False) else 0,
                json.dumps(feat_data.get('spell_lists', [])),
                json.dumps(feat_data.get('spells_num', {})),
                1 if feat_data.get('has_prereq', False) else 0,
                feat_data.get('prereq', ''),
                json.dumps(feat_data.get('set_spells', [])),
                feat_data.get('description', ''),
                feat_data.get('source', ''),
                1 if feat_data.get('is_official', True) else 0,
                1 if feat_data.get('is_custom', False) else 0,
                1 if feat_data.get('is_legacy', False) else 0,
                feat_id
            ))
            return cursor.rowcount > 0
    
    def delete_feat(self, feat_id: int) -> bool:
        """Delete a feat by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feats WHERE id = ?", (feat_id,))
            return cursor.rowcount > 0
    
    def _row_to_feat_dict(self, row) -> dict:
        """Convert a database row to a feat dictionary."""
        spells_num_raw = json.loads(row['spells_num_json']) if row['spells_num_json'] else {}
        spells_num = {int(k): v for k, v in spells_num_raw.items()} if spells_num_raw else {}
        return {
            'id': row['id'],
            'name': row['name'],
            'type': row['type'] or '',
            'is_spellcasting': bool(row['is_spellcasting']),
            'spell_lists': json.loads(row['spell_lists_json']) if row['spell_lists_json'] else [],
            'spells_num': spells_num,
            'has_prereq': bool(row['has_prereq']),
            'prereq': row['prereq'] or '',
            'set_spells': json.loads(row['set_spells_json']) if row['set_spells_json'] else [],
            'description': row['description'] or '',
            'source': row['source'] or '',
            'is_official': bool(row['is_official']),
            'is_custom': bool(row['is_custom']),
            'is_legacy': bool(row['is_legacy'])
        }
    
    # ==================== BACKGROUND METHODS ====================
    
    def get_all_backgrounds(self) -> List[dict]:
        """Get all backgrounds from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backgrounds ORDER BY name")
            return [self._row_to_background_dict(row) for row in cursor.fetchall()]
    
    def get_background_by_name(self, name: str) -> Optional[dict]:
        """Get a background by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM backgrounds WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            return self._row_to_background_dict(row) if row else None
    
    def insert_background(self, bg_data: dict) -> int:
        """Insert a new background."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO backgrounds (name, source, is_legacy, description, skills_json,
                                         other_proficiencies_json, ability_scores_json, feats_json,
                                         equipment, features_json, is_official, is_custom)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bg_data['name'],
                bg_data.get('source', ''),
                1 if bg_data.get('is_legacy', False) else 0,
                bg_data.get('description', ''),
                json.dumps(bg_data.get('skills', [])),
                json.dumps(bg_data.get('other_proficiencies', [])),
                json.dumps(bg_data.get('ability_scores', [])),
                json.dumps(bg_data.get('feats', [])),
                bg_data.get('equipment', ''),
                json.dumps(bg_data.get('features', [])),
                1 if bg_data.get('is_official', True) else 0,
                1 if bg_data.get('is_custom', False) else 0
            ))
            return cursor.lastrowid or 0
    
    def update_background(self, bg_id: int, bg_data: dict) -> bool:
        """Update an existing background."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE backgrounds SET name = ?, source = ?, is_legacy = ?, description = ?,
                skills_json = ?, other_proficiencies_json = ?, ability_scores_json = ?, feats_json = ?,
                equipment = ?, features_json = ?, is_official = ?, is_custom = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                bg_data['name'],
                bg_data.get('source', ''),
                1 if bg_data.get('is_legacy', False) else 0,
                bg_data.get('description', ''),
                json.dumps(bg_data.get('skills', [])),
                json.dumps(bg_data.get('other_proficiencies', [])),
                json.dumps(bg_data.get('ability_scores', [])),
                json.dumps(bg_data.get('feats', [])),
                bg_data.get('equipment', ''),
                json.dumps(bg_data.get('features', [])),
                1 if bg_data.get('is_official', True) else 0,
                1 if bg_data.get('is_custom', False) else 0,
                bg_id
            ))
            return cursor.rowcount > 0
    
    def delete_background(self, bg_id: int) -> bool:
        """Delete a background by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM backgrounds WHERE id = ?", (bg_id,))
            return cursor.rowcount > 0
    
    def _row_to_background_dict(self, row) -> dict:
        """Convert a database row to a background dictionary."""
        return {
            'id': row['id'],
            'name': row['name'],
            'source': row['source'] or '',
            'is_legacy': bool(row['is_legacy']),
            'description': row['description'] or '',
            'skills': json.loads(row['skills_json']) if row['skills_json'] else [],
            'other_proficiencies': json.loads(row['other_proficiencies_json']) if row['other_proficiencies_json'] else [],
            'ability_scores': json.loads(row['ability_scores_json']) if row['ability_scores_json'] else [],
            'feats': json.loads(row['feats_json']) if row['feats_json'] else [],
            'equipment': row['equipment'] or '',
            'features': json.loads(row['features_json']) if row['features_json'] else [],
            'is_official': bool(row['is_official']),
            'is_custom': bool(row['is_custom'])
        }
    
    # ==================== CLASS METHODS ====================
    
    def get_all_character_classes(self) -> List[dict]:
        """Get all character classes from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM classes ORDER BY name")
            classes = []
            for row in cursor.fetchall():
                cls_dict = self._row_to_class_dict(row)
                # Get subclasses for this class
                cursor.execute("SELECT * FROM subclasses WHERE class_id = ? ORDER BY name", (row['id'],))
                cls_dict['subclasses'] = [self._row_to_subclass_dict(sub_row) for sub_row in cursor.fetchall()]
                classes.append(cls_dict)
            return classes
    
    def get_class_by_name(self, name: str) -> Optional[dict]:
        """Get a class by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM classes WHERE name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            if row:
                cls_dict = self._row_to_class_dict(row)
                cursor.execute("SELECT * FROM subclasses WHERE class_id = ? ORDER BY name", (row['id'],))
                cls_dict['subclasses'] = [self._row_to_subclass_dict(sub_row) for sub_row in cursor.fetchall()]
                return cls_dict
            return None
    
    def insert_class(self, class_data: dict) -> int:
        """Insert a new class."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO classes (name, hit_die, primary_ability, saving_throws_json,
                                     armor_proficiencies_json, weapon_proficiencies_json,
                                     tool_proficiencies_json, skill_proficiencies_json,
                                     num_skills, starting_equipment_json, class_features_json,
                                     spellcasting_json, subclass_name, subclass_level,
                                     class_table_columns_json, trackable_features_json,
                                     class_spells_json, unarmored_defense,
                                     source, is_official, is_custom, is_legacy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                class_data['name'],
                class_data.get('hit_die', 8),
                class_data.get('primary_ability', ''),
                json.dumps(class_data.get('saving_throws', [])),
                json.dumps(class_data.get('armor_proficiencies', [])),
                json.dumps(class_data.get('weapon_proficiencies', [])),
                json.dumps(class_data.get('tool_proficiencies', [])),
                json.dumps(class_data.get('skill_proficiencies', [])),
                class_data.get('num_skills', 2),
                json.dumps(class_data.get('starting_equipment', [])),
                json.dumps(class_data.get('class_features', [])),
                json.dumps(class_data.get('spellcasting')) if class_data.get('spellcasting') else 'null',
                class_data.get('subclass_name', ''),
                class_data.get('subclass_level', 3),
                json.dumps(class_data.get('class_table_columns', [])),
                json.dumps(class_data.get('trackable_features', [])),
                json.dumps(class_data.get('class_spells', [])),
                class_data.get('unarmored_defense', ''),
                class_data.get('source', ''),
                1 if class_data.get('is_official', True) else 0,
                1 if class_data.get('is_custom', False) else 0,
                1 if class_data.get('is_legacy', False) else 0
            ))
            return cursor.lastrowid or 0
    
    def update_class(self, class_id: int, class_data: dict) -> bool:
        """Update an existing class."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE classes SET name = ?, hit_die = ?, primary_ability = ?, saving_throws_json = ?,
                armor_proficiencies_json = ?, weapon_proficiencies_json = ?, tool_proficiencies_json = ?,
                skill_proficiencies_json = ?, num_skills = ?, starting_equipment_json = ?,
                class_features_json = ?, spellcasting_json = ?, subclass_name = ?, subclass_level = ?,
                class_table_columns_json = ?, trackable_features_json = ?, class_spells_json = ?,
                unarmored_defense = ?, source = ?, is_official = ?, is_custom = ?, is_legacy = ?,
                updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                class_data['name'],
                class_data.get('hit_die', 8),
                class_data.get('primary_ability', ''),
                json.dumps(class_data.get('saving_throws', [])),
                json.dumps(class_data.get('armor_proficiencies', [])),
                json.dumps(class_data.get('weapon_proficiencies', [])),
                json.dumps(class_data.get('tool_proficiencies', [])),
                json.dumps(class_data.get('skill_proficiencies', [])),
                class_data.get('num_skills', 2),
                json.dumps(class_data.get('starting_equipment', [])),
                json.dumps(class_data.get('class_features', [])),
                json.dumps(class_data.get('spellcasting')) if class_data.get('spellcasting') else 'null',
                class_data.get('subclass_name', ''),
                class_data.get('subclass_level', 3),
                json.dumps(class_data.get('class_table_columns', [])),
                json.dumps(class_data.get('trackable_features', [])),
                json.dumps(class_data.get('class_spells', [])),
                class_data.get('unarmored_defense', ''),
                class_data.get('source', ''),
                1 if class_data.get('is_official', True) else 0,
                1 if class_data.get('is_custom', False) else 0,
                1 if class_data.get('is_legacy', False) else 0,
                class_id
            ))
            return cursor.rowcount > 0
    
    def delete_class(self, class_id: int) -> bool:
        """Delete a class by ID (cascades to subclasses)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM classes WHERE id = ?", (class_id,))
            return cursor.rowcount > 0
    
    def _row_to_class_dict(self, row) -> dict:
        """Convert a database row to a class dictionary."""
        spellcasting = None
        if row['spellcasting_json'] and row['spellcasting_json'] != 'null':
            spellcasting = json.loads(row['spellcasting_json'])
        
        # Handle new columns that might not exist in older databases
        class_table_columns = []
        trackable_features = []
        class_spells = []
        unarmored_defense = ''
        
        # Try to access new columns, fall back to defaults if they don't exist
        try:
            if row['class_table_columns_json']:
                class_table_columns = json.loads(row['class_table_columns_json'])
        except (KeyError, IndexError):
            pass
        
        try:
            if row['trackable_features_json']:
                trackable_features = json.loads(row['trackable_features_json'])
        except (KeyError, IndexError):
            pass
        
        try:
            if row['class_spells_json']:
                class_spells = json.loads(row['class_spells_json'])
        except (KeyError, IndexError):
            pass
        
        try:
            unarmored_defense = row['unarmored_defense'] or ''
        except (KeyError, IndexError):
            pass
        
        return {
            'id': row['id'],
            'name': row['name'],
            'hit_die': row['hit_die'] or 8,
            'primary_ability': row['primary_ability'] or '',
            'saving_throws': json.loads(row['saving_throws_json']) if row['saving_throws_json'] else [],
            'armor_proficiencies': json.loads(row['armor_proficiencies_json']) if row['armor_proficiencies_json'] else [],
            'weapon_proficiencies': json.loads(row['weapon_proficiencies_json']) if row['weapon_proficiencies_json'] else [],
            'tool_proficiencies': json.loads(row['tool_proficiencies_json']) if row['tool_proficiencies_json'] else [],
            'skill_proficiencies': json.loads(row['skill_proficiencies_json']) if row['skill_proficiencies_json'] else [],
            'num_skills': row['num_skills'] or 2,
            'starting_equipment': json.loads(row['starting_equipment_json']) if row['starting_equipment_json'] else [],
            'class_features': json.loads(row['class_features_json']) if row['class_features_json'] else [],
            'spellcasting': spellcasting,
            'subclass_name': row['subclass_name'] or '',
            'subclass_level': row['subclass_level'] or 3,
            'class_table_columns': class_table_columns,
            'trackable_features': trackable_features,
            'class_spells': class_spells,
            'unarmored_defense': unarmored_defense,
            'source': row['source'] or '',
            'is_official': bool(row['is_official']),
            'is_custom': bool(row['is_custom']),
            'is_legacy': bool(row['is_legacy']),
            'subclasses': []  # Filled by get_all_classes or get_class_by_name
        }
    
    def _row_to_subclass_dict(self, row) -> dict:
        """Convert a database row to a subclass dictionary."""
        # features_json contains all subclass data
        features_data = json.loads(row['features_json']) if row['features_json'] else {}
        
        # Handle both old format (list of features) and new format (dict with multiple fields)
        if isinstance(features_data, list):
            features = features_data
            subclass_spells = []
            armor_proficiencies = []
            weapon_proficiencies = []
            unarmored_defense = ''
            trackable_features = []
        else:
            features = features_data.get('features', [])
            subclass_spells = features_data.get('subclass_spells', [])
            armor_proficiencies = features_data.get('armor_proficiencies', [])
            weapon_proficiencies = features_data.get('weapon_proficiencies', [])
            unarmored_defense = features_data.get('unarmored_defense', '')
            trackable_features = features_data.get('trackable_features', [])
        
        return {
            'id': row['id'],
            'name': row['name'],
            'class_id': row['class_id'],
            'description': row['description'] or '',
            'features': features,
            'subclass_spells': subclass_spells,
            'armor_proficiencies': armor_proficiencies,
            'weapon_proficiencies': weapon_proficiencies,
            'unarmored_defense': unarmored_defense,
            'trackable_features': trackable_features,
            'source': row['source'] or '',
            'is_official': bool(row['is_official']),
            'is_custom': bool(row['is_custom']),
            'is_legacy': bool(row['is_legacy'])
        }
    
    # ==================== SUBCLASS METHODS ====================
    
    def get_subclasses_for_class(self, class_id: int) -> List[dict]:
        """Get all subclasses for a class."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subclasses WHERE class_id = ? ORDER BY name", (class_id,))
            return [self._row_to_subclass_dict(row) for row in cursor.fetchall()]
    
    def insert_subclass(self, subclass_data: dict) -> int:
        """Insert a new subclass. class_id must be in subclass_data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Store all subclass data in features_json
            features_data = {
                'features': subclass_data.get('features', []),
                'subclass_spells': subclass_data.get('subclass_spells', []),
                'armor_proficiencies': subclass_data.get('armor_proficiencies', []),
                'weapon_proficiencies': subclass_data.get('weapon_proficiencies', []),
                'unarmored_defense': subclass_data.get('unarmored_defense', ''),
                'trackable_features': subclass_data.get('trackable_features', [])
            }
            cursor.execute("""
                INSERT INTO subclasses (name, class_id, description, features_json, source,
                                        is_official, is_custom, is_legacy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                subclass_data['name'],
                subclass_data['class_id'],
                subclass_data.get('description', ''),
                json.dumps(features_data),
                subclass_data.get('source', ''),
                1 if subclass_data.get('is_official', True) else 0,
                1 if subclass_data.get('is_custom', False) else 0,
                1 if subclass_data.get('is_legacy', False) else 0
            ))
            return cursor.lastrowid or 0
    
    def update_subclass(self, subclass_id: int, subclass_data: dict) -> bool:
        """Update an existing subclass."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Store all subclass data in features_json
            features_data = {
                'features': subclass_data.get('features', []),
                'subclass_spells': subclass_data.get('subclass_spells', []),
                'armor_proficiencies': subclass_data.get('armor_proficiencies', []),
                'weapon_proficiencies': subclass_data.get('weapon_proficiencies', []),
                'unarmored_defense': subclass_data.get('unarmored_defense', ''),
                'trackable_features': subclass_data.get('trackable_features', [])
            }
            cursor.execute("""
                UPDATE subclasses SET name = ?, description = ?, features_json = ?, source = ?,
                is_official = ?, is_custom = ?, is_legacy = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                subclass_data['name'],
                subclass_data.get('description', ''),
                json.dumps(features_data),
                subclass_data.get('source', ''),
                1 if subclass_data.get('is_official', True) else 0,
                1 if subclass_data.get('is_custom', False) else 0,
                1 if subclass_data.get('is_legacy', False) else 0,
                subclass_id
            ))
            return cursor.rowcount > 0
    
    def delete_subclass(self, subclass_id: int) -> bool:
        """Delete a subclass by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subclasses WHERE id = ?", (subclass_id,))
            return cursor.rowcount > 0
    
    def get_all_subclasses(self) -> List[dict]:
        """Get all subclasses with their parent class name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, c.name as parent_class 
                FROM subclasses s 
                JOIN classes c ON s.class_id = c.id 
                ORDER BY s.name
            """)
            results = []
            for row in cursor.fetchall():
                sub_dict = self._row_to_subclass_dict(row)
                sub_dict['parent_class'] = row['parent_class']
                results.append(sub_dict)
            return results
    
    def get_subclass_by_name(self, name: str, parent_class_name: str) -> Optional[dict]:
        """Get a subclass by name and parent class name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, c.name as parent_class 
                FROM subclasses s 
                JOIN classes c ON s.class_id = c.id 
                WHERE s.name = ? AND c.name = ?
            """, (name, parent_class_name))
            row = cursor.fetchone()
            if row:
                sub_dict = self._row_to_subclass_dict(row)
                sub_dict['parent_class'] = row['parent_class']
                return sub_dict
            return None
    
    def get_subclasses_by_class(self, class_name: str) -> List[dict]:
        """Get all subclasses for a class by class name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, c.name as parent_class 
                FROM subclasses s 
                JOIN classes c ON s.class_id = c.id 
                WHERE c.name = ?
                ORDER BY s.name
            """, (class_name,))
            results = []
            for row in cursor.fetchall():
                sub_dict = self._row_to_subclass_dict(row)
                sub_dict['parent_class'] = row['parent_class']
                results.append(sub_dict)
            return results
    
    # ==================== GLOBAL SEARCH ====================
    
    def global_search(self, query: str, limit: int = 50) -> List[dict]:
        """
        Search across all content types by name.
        Returns list of dicts with 'name', 'section', and 'id'.
        """
        if not query or len(query) < 1:
            return []
        
        results = []
        search_pattern = f"%{query}%"
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Search spells
            cursor.execute("""
                SELECT id, name FROM spells 
                WHERE name LIKE ? COLLATE NOCASE 
                ORDER BY name LIMIT ?
            """, (search_pattern, limit))
            for row in cursor.fetchall():
                results.append({'id': row['id'], 'name': row['name'], 'section': 'Spells'})
            
            # Search lineages
            cursor.execute("""
                SELECT id, name FROM lineages 
                WHERE name LIKE ? COLLATE NOCASE 
                ORDER BY name LIMIT ?
            """, (search_pattern, limit))
            for row in cursor.fetchall():
                results.append({'id': row['id'], 'name': row['name'], 'section': 'Lineages'})
            
            # Search feats
            cursor.execute("""
                SELECT id, name FROM feats 
                WHERE name LIKE ? COLLATE NOCASE 
                ORDER BY name LIMIT ?
            """, (search_pattern, limit))
            for row in cursor.fetchall():
                results.append({'id': row['id'], 'name': row['name'], 'section': 'Feats'})
            
            # Search backgrounds
            cursor.execute("""
                SELECT id, name FROM backgrounds 
                WHERE name LIKE ? COLLATE NOCASE 
                ORDER BY name LIMIT ?
            """, (search_pattern, limit))
            for row in cursor.fetchall():
                results.append({'id': row['id'], 'name': row['name'], 'section': 'Backgrounds'})
            
            # Search classes
            cursor.execute("""
                SELECT id, name FROM classes 
                WHERE name LIKE ? COLLATE NOCASE 
                ORDER BY name LIMIT ?
            """, (search_pattern, limit))
            for row in cursor.fetchall():
                results.append({'id': row['id'], 'name': row['name'], 'section': 'Classes'})
            
            # Search subclasses
            cursor.execute("""
                SELECT s.id, s.name, c.name as class_name FROM subclasses s
                JOIN classes c ON s.class_id = c.id
                WHERE s.name LIKE ? COLLATE NOCASE 
                ORDER BY s.name LIMIT ?
            """, (search_pattern, limit))
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'], 
                    'name': f"{row['name']} ({row['class_name']})", 
                    'section': 'Subclasses'
                })
        
        # Sort by name and limit total results
        results.sort(key=lambda x: x['name'].lower())
        return results[:limit]

