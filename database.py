"""
SQLite database module for D&D Spellbook Application.
Handles database creation, migrations, and spell persistence.
"""

import sqlite3
import os
import json
from typing import List, Optional, Tuple
from contextlib import contextmanager

from paths import resource_path, user_data_path
from db_collections import (CollectionStoreMixin, LINEAGES, FEATS, EQUIPMENT, MAGIC_ITEMS,
                            BACKGROUNDS, RULES, CLASSES, SUBCLASSES)
import search_index


# The (historic) stat blocks table: created on a fresh database and by the version 3 migration.
_STAT_BLOCKS_TABLE_SQL = """
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
            """

class SpellDatabase(CollectionStoreMixin):
    """SQLite database handler for spell storage."""
    
    DEFAULT_DB_PATH = "spellbook.db"
    SCHEMA_VERSION = 31  # bundled rules pages
    
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
        self.db_path = db_path or user_data_path(self.DEFAULT_DB_PATH)
        self._connection: Optional[sqlite3.Connection] = None
        self._batch_connection: Optional[sqlite3.Connection] = None
        self._search_index_ready: Optional[bool] = None
        
    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key support
        # Lets searches match a description's visible text instead of its
        # [[category:Name|shown]] link markup (see search_spells).
        from object_link_sweep import strip_links
        conn.create_function("strip_links", 1, lambda t: strip_links(t) if t else t, deterministic=True)
        # The search index triggers call search_text() (see search_index.py).
        search_index.register_functions(conn)
        return conn

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        if self._batch_connection is not None:       # inside batch(): the one connection, committed at the end
            yield self._batch_connection
            return
        conn = self._open_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def batch(self):
        """Everything written inside shares one connection and is committed once, or not at all if it raises.

        A bulk edit of hundreds of rows would otherwise open a connection and commit (a disk sync) for each."""
        if self._batch_connection is not None:
            yield
            return
        conn = self._open_connection()
        self._batch_connection = conn
        try:
            yield
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._batch_connection = None
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
            cursor.execute(_STAT_BLOCKS_TABLE_SQL)
            
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

            # Full-text index over every collection (built once, then kept current by triggers)
            self._search_index_ready = search_index.ensure(conn)
    
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
            cursor.execute(_STAT_BLOCKS_TABLE_SQL)
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
        
        # Migration to version 12: reset all is_modified flags for fresh baseline
        if current_version < 12:
            cursor.execute("UPDATE spells SET is_modified = 0")
            cursor.execute("UPDATE schema_version SET version = 12")
            current_version = 12
        
        # Migration to version 15: refresh spell descriptions with the latest bundled text
        if current_version < 15:
            self._refresh_spell_descriptions_v13(cursor)
            cursor.execute("UPDATE schema_version SET version = 15")
            current_version = 15

        # Migration to version 16: backfill the bundled equipment / magic item
        # content for databases created before it shipped. Idempotent
        # (INSERT OR IGNORE), and never touches user-created rows.
        if current_version < 16:
            self._seed_equipment_and_magic_items(cursor)
            cursor.execute("UPDATE schema_version SET version = 16")
            current_version = 16

        # Migration to version 17: re-run the seed so installs that already
        # passed v16 pick up the bundled magic_items.json (first shipped now).
        if current_version < 17:
            self._seed_equipment_and_magic_items(cursor)
            cursor.execute("UPDATE schema_version SET version = 17")
            current_version = 17

        # Migration to version 18: re-run the seed so existing installs pick up
        # the tools (artisan/other tools, gaming sets, instruments) added to
        # equipment.json.
        if current_version < 18:
            self._seed_equipment_and_magic_items(cursor)
            cursor.execute("UPDATE schema_version SET version = 18")
            current_version = 18

        # Migration to version 19: fill in the Crafting Tool of bundled
        # equipment (e.g. Acid -> Alchemist's Supplies) on existing installs.
        if current_version < 19:
            self._backfill_equipment_crafting_tools(cursor)
            cursor.execute("UPDATE schema_version SET version = 19")
            current_version = 19

        # Migration to version 20: link object mentions in official content
        # ("the Misty Step spell", a background's gear list, ...). If it can't
        # run, the version stays at 19 and it is retried on the next launch.
        if current_version < 20:
            if self._link_official_content(cursor):
                cursor.execute("UPDATE schema_version SET version = 20")
                current_version = 20

        # Migration to version 21: add bundled subclasses that shipped after
        # the classes were first seeded (Artificer: Reanimator).
        if current_version < 21:
            if self._seed_missing_subclasses(cursor):
                cursor.execute("UPDATE schema_version SET version = 21")
                current_version = 21

        # Migration to version 22: add the bundled Rare magic items to
        # existing installs (INSERT OR IGNORE, so nothing already there - or
        # user-made - is touched). The new items are bundled already linked;
        # the link sweep is re-run so older text that mentions them (Bag of
        # Holding -> Portable Hole, ...) links to them too. Idempotent, and
        # retried on the next launch if the sweep can't run.
        if current_version < 22:
            self._seed_equipment_and_magic_items(cursor)
            if self._link_official_content(cursor):
                cursor.execute("UPDATE schema_version SET version = 22")
                current_version = 22

        # Migration to version 23: add the official content from the newer
        # source books (backgrounds, species, feats, spells, subclasses; the
        # summon stat blocks ride along with the spells at startup). Every
        # insert is by name and skips what already exists, so nothing already
        # there - or user-made - is touched. The link sweep is re-run so older
        # text that mentions the new spells (Hallow, Teleportation Circle, ...)
        # links to them. Idempotent, and retried on the next launch if either
        # step can't run.
        if current_version < 23:
            if self._seed_new_official_content(cursor) and self._link_official_content(cursor):
                cursor.execute("UPDATE schema_version SET version = 23")
                current_version = 23

        # Migration to version 24: add the mounts, vehicles and poisons, and the
        # Very Rare, Legendary and Artifact magic items. Harkon's Bite first
        # shipped under a mangled name ("The Horrors Within", no source), so it
        # is renamed before seeding rather than duplicated. Seeding is
        # INSERT OR IGNORE by name (nothing already there - or user-made - is
        # touched) and the link sweep is re-run so older text that names the new
        # items (Folding Boat -> Rowboat, ...) links to them. Idempotent, and
        # retried on the next launch if the sweep can't run.
        if current_version < 24:
            self._fix_mangled_harkons_bite(cursor)
            self._seed_equipment_and_magic_items(cursor)
            if self._link_official_content(cursor):
                cursor.execute("UPDATE schema_version SET version = 24")
                current_version = 24

        # Migration to version 25: backfill magic item cost onto existing
        # installs (magic_items.json shipped with every cost blank until now).
        # Only official rows whose cost is still empty are touched, so a
        # user-edited or custom item's cost is never overwritten.
        if current_version < 25:
            self._backfill_magic_item_costs(cursor)
            cursor.execute("UPDATE schema_version SET version = 25")
            current_version = 25

        # Migration to version 26: the monsters table. It is created by
        # _create_content_tables (CREATE TABLE IF NOT EXISTS, run on every
        # initialize()), so there is nothing to copy - no monster content ships
        # with the app yet, only what the user creates or imports.
        if current_version < 26:
            cursor.execute("UPDATE schema_version SET version = 26")
            current_version = 26

        # Migration to version 27: summon-spell stat blocks are now monsters
        # (flagged spell_only, linked to their spell). Every row of the legacy
        # stat_blocks table - bundled or user-made, edited or not - is converted;
        # the old table is left in place, unused. Retried on the next launch if
        # the conversion can't run.
        if current_version < 27:
            if self._convert_stat_blocks_to_monsters(cursor):
                cursor.execute("UPDATE schema_version SET version = 27")
                current_version = 27

        # Migration to version 28: add the bundled monsters (monsters.json).
        # Inserted only if the name is missing, so nothing already there - or
        # user-made - is touched; the link sweep is re-run so older text that
        # names the new monsters links to them. Idempotent, and retried on the
        # next launch if either step can't run.
        if current_version < 28:
            if self._seed_official_monsters(cursor) and self._link_official_content(cursor):
                cursor.execute("UPDATE schema_version SET version = 28")
                current_version = 28

        # Migration to version 29: Flesh Golem shipped with no speed (its source
        # page left the line blank). Only a bundled row that still has none is
        # touched, so a user's edit is never overwritten.
        if current_version < 29:
            cursor.execute(
                "UPDATE monsters SET speeds_json = ? WHERE name = 'Flesh Golem' COLLATE NOCASE "
                "AND is_custom = 0 AND spell_only = 0 AND speeds_json IN ('{}', '')",
                (json.dumps({"walk": 30}),))
            cursor.execute("UPDATE schema_version SET version = 29")
            current_version = 29

        # Migration to version 30: add the bundled legacy (2014) content from
        # legacy_2014.json - spells, feats, lineages, backgrounds, classes and
        # subclasses, all flagged is_legacy. Inserted by name and only if the
        # name is missing (a 2014 entry whose name 2024 content owns is stored
        # as "Name (Legacy)"), so nothing already there - or user-made - is
        # touched. Legacy text is linked at build time and is not swept, so no
        # link pass is needed. Idempotent, and retried on the next launch if
        # seeding can't run.
        if current_version < 30:
            if self._seed_legacy_content(cursor):
                cursor.execute("UPDATE schema_version SET version = 30")
                current_version = 30

        # Migration to version 31: add the bundled rules pages (rules.json, the
        # Free Basic Rules). Inserted by name and only if the name is missing, so
        # a user's own page - or an edit - is never touched. Idempotent, and
        # retried on the next launch if seeding can't run.
        if current_version < 31:
            if self._seed_official_rules(cursor):
                cursor.execute("UPDATE schema_version SET version = 31")
                current_version = 31

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
                roll_effects_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feats_name ON feats(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feats_type ON feats(type)")

        # Equipment table (mundane gear)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                type TEXT DEFAULT 'Adventuring Gear',
                cost TEXT DEFAULT '',
                weight REAL NOT NULL DEFAULT 0,
                source TEXT DEFAULT '',
                crafting_materials_json TEXT DEFAULT '[]',
                crafting_tool TEXT DEFAULT '',
                description TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                properties_json TEXT DEFAULT '[]',
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipment_name ON equipment(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_equipment_type ON equipment(type)")

        # Magic items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS magic_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                type TEXT DEFAULT 'Wondrous Item',
                cost TEXT DEFAULT '',
                weight REAL NOT NULL DEFAULT 0,
                source TEXT DEFAULT '',
                enchanting_materials_json TEXT DEFAULT '[]',
                description TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                properties_json TEXT DEFAULT '[]',
                rarity TEXT DEFAULT 'Common',
                requires_attunement INTEGER NOT NULL DEFAULT 0,
                attunement_requirement TEXT DEFAULT '',
                attunement_optional INTEGER NOT NULL DEFAULT 0,
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                roll_effects_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_magic_items_name ON magic_items(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_magic_items_type ON magic_items(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_magic_items_rarity ON magic_items(rarity)")

        # Rules pages (the rulebook text; one markup string per page, see rules.py)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                category TEXT DEFAULT '',
                description TEXT DEFAULT '',
                source TEXT DEFAULT '',
                tags_json TEXT DEFAULT '[]',
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_name ON rules(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_category ON rules(category)")

        # Monsters table (creature stat blocks). Plain values get their own
        # column; lists / dicts are stored as JSON (see _MONSTER_SCALARS/_JSONS).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monsters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                epithet TEXT DEFAULT '',
                size TEXT DEFAULT 'Medium',
                creature_type TEXT DEFAULT '',
                creature_subtype TEXT DEFAULT '',
                alignment TEXT DEFAULT 'Unaligned',
                ac INTEGER NOT NULL DEFAULT 10,
                initiative_proficiency INTEGER NOT NULL DEFAULT 0,
                hp INTEGER NOT NULL DEFAULT 1,
                hit_dice TEXT DEFAULT '',
                can_hover INTEGER NOT NULL DEFAULT 0,
                ac_text TEXT DEFAULT '',
                hp_text TEXT DEFAULT '',
                speed_text TEXT DEFAULT '',
                cr_text TEXT DEFAULT '',
                skills_text TEXT DEFAULT '',
                show_initiative INTEGER NOT NULL DEFAULT 1,
                challenge_rating TEXT NOT NULL DEFAULT '0',
                lair_xp INTEGER,
                legendary_action_uses INTEGER NOT NULL DEFAULT 3,
                legendary_action_uses_in_lair INTEGER,
                legendary_actions_intro TEXT DEFAULT '',
                lair_actions_intro TEXT DEFAULT '',
                description TEXT DEFAULT '',
                source TEXT DEFAULT '',
                speeds_json TEXT DEFAULT '{}',
                ability_scores_json TEXT DEFAULT '{}',
                saving_throws_json TEXT DEFAULT '{}',
                skills_json TEXT DEFAULT '{}',
                damage_vulnerabilities_json TEXT DEFAULT '[]',
                damage_resistances_json TEXT DEFAULT '[]',
                damage_immunities_json TEXT DEFAULT '[]',
                condition_immunities_json TEXT DEFAULT '[]',
                senses_json TEXT DEFAULT '[]',
                languages_json TEXT DEFAULT '[]',
                gear_json TEXT DEFAULT '[]',
                traits_json TEXT DEFAULT '[]',
                actions_json TEXT DEFAULT '[]',
                bonus_actions_json TEXT DEFAULT '[]',
                reactions_json TEXT DEFAULT '[]',
                legendary_actions_json TEXT DEFAULT '[]',
                lair_actions_json TEXT DEFAULT '[]',
                habitat_json TEXT DEFAULT '[]',
                treasure_json TEXT DEFAULT '[]',
                is_official INTEGER NOT NULL DEFAULT 1,
                is_custom INTEGER NOT NULL DEFAULT 0,
                spell_only INTEGER NOT NULL DEFAULT 0,
                spell_id INTEGER REFERENCES spells(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_name ON monsters(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_type ON monsters(creature_type)")

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

        # Self-healing: add optional columns that were introduced after the
        # equipment / magic_items tables first shipped. CREATE TABLE IF NOT
        # EXISTS never alters an existing table, so backfill them here (this
        # method runs on every initialize()).
        # monsters.epitaph was renamed epithet ("epitaph" implies the creature is dead)
        cursor.execute("PRAGMA table_info(monsters)")
        _monster_columns = {row[1] for row in cursor.fetchall()}
        if "epitaph" in _monster_columns and "epithet" not in _monster_columns:
            cursor.execute("ALTER TABLE monsters RENAME COLUMN epitaph TO epithet")

        for _table, _col, _coldef in (
            ("equipment", "properties_json", "TEXT DEFAULT '[]'"),
            ("magic_items", "properties_json", "TEXT DEFAULT '[]'"),
            ("magic_items", "requires_attunement", "INTEGER NOT NULL DEFAULT 0"),
            ("magic_items", "roll_effects_json", "TEXT DEFAULT '[]'"),
            ("feats", "roll_effects_json", "TEXT DEFAULT '[]'"),
            ("monsters", "ac_text", "TEXT DEFAULT ''"),
            ("monsters", "hp_text", "TEXT DEFAULT ''"),
            ("monsters", "speed_text", "TEXT DEFAULT ''"),
            ("monsters", "cr_text", "TEXT DEFAULT ''"),
            ("monsters", "show_initiative", "INTEGER NOT NULL DEFAULT 1"),
            ("monsters", "spell_only", "INTEGER NOT NULL DEFAULT 0"),
            ("monsters", "spell_id", "INTEGER REFERENCES spells(id) ON DELETE CASCADE"),
            ("monsters", "gear_json", "TEXT DEFAULT '[]'"),
            ("monsters", "skills_text", "TEXT DEFAULT ''"),
        ):
            cursor.execute(f"PRAGMA table_info({_table})")
            _existing = {row[1] for row in cursor.fetchall()}
            if _col not in _existing:
                cursor.execute(f"ALTER TABLE {_table} ADD COLUMN {_col} {_coldef}")
                if _col == "requires_attunement":
                    # Rows that predate the column: infer it from the
                    # restriction text that used to double as the flag.
                    cursor.execute(
                        "UPDATE magic_items SET requires_attunement = 1 "
                        "WHERE TRIM(COALESCE(attunement_requirement, '')) != ''")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_monsters_spell_id ON monsters(spell_id)")

    def _bundled_json_path(self, filename):
        """Absolute path to a bundled JSON seed file (PyInstaller-aware)."""
        return resource_path(filename)

    def _backfill_equipment_crafting_tools(self, cursor):
        """Copy crafting_tool from the bundled equipment.json onto existing rows.

        Only official rows whose crafting_tool is still empty are touched, so
        anything the user has typed in (or a custom item) is left alone.
        """
        import os

        path = self._bundled_json_path('equipment.json')
        if not os.path.exists(path):
            return
        try:
            data = self._load_json(path)
            for item in data.get('equipment', []):
                tool = (item.get('crafting_tool') or '').strip()
                if not tool:
                    continue
                cursor.execute(
                    "UPDATE equipment SET crafting_tool = ? "
                    "WHERE name = ? AND is_custom = 0 AND COALESCE(crafting_tool, '') = ''",
                    (tool, item.get('name', '')))
        except Exception as e:
            print(f"Error backfilling equipment crafting tools: {e}")

    def _backfill_magic_item_costs(self, cursor):
        """Copy cost from the bundled magic_items.json onto existing rows.

        Only official rows whose cost is still empty are touched, so anything
        the user has typed in (or a custom item) is left alone.
        """
        import os

        path = self._bundled_json_path('magic_items.json')
        if not os.path.exists(path):
            return
        try:
            data = self._load_json(path)
            for item in data.get('magic_items', []):
                cost = (item.get('cost') or '').strip()
                if not cost:
                    continue
                cursor.execute(
                    "UPDATE magic_items SET cost = ? "
                    "WHERE name = ? AND is_custom = 0 AND COALESCE(cost, '') = ''",
                    (cost, item.get('name', '')))
        except Exception as e:
            print(f"Error backfilling magic item costs: {e}")

    def _fix_mangled_harkons_bite(self, cursor):
        """Rename the bundled magic item that was imported as "The Horrors Within".

        It is Harkon's Bite: its source line ("Ravenloft - The Horrors Within")
        was read as the item's name. Only the untouched bundled row (official,
        empty source) is renamed, and only if that name is free.
        """
        cursor.execute(
            "UPDATE OR IGNORE magic_items SET name = ?, source = ? "
            "WHERE name = 'The Horrors Within' AND is_custom = 0 AND COALESCE(source, '') = ''",
            ("Harkon's Bite", "Ravenloft - The Horrors Within"))

    @staticmethod
    def _bundled_class_row(class_name: str, cls: dict) -> dict:
        """A classes.json entry in the shape ``insert_class`` takes."""
        spellcasting = None
        if cls.get('is_spellcaster', False):
            spellcasting = {
                'is_spellcaster': True,
                'ability': cls.get('spellcasting_ability', '')
            }
        return {
            'name': class_name,
            'hit_die': cls.get('hit_die', 'd8'),
            'primary_ability': cls.get('primary_ability', ''),
            'saving_throws': cls.get('saving_throw_proficiencies', []),
            'armor_proficiencies': cls.get('armor_proficiencies', []),
            'weapon_proficiencies': cls.get('weapon_proficiencies', []),
            'tool_proficiencies': cls.get('tool_proficiencies', []),
            'skill_proficiencies': cls.get('skill_proficiency_options', []),
            'num_skills': cls.get('skill_proficiency_choices', 2),
            'starting_equipment': cls.get('starting_equipment_options', []),
            'class_features': cls.get('levels', {}),
            'spellcasting': spellcasting,
            'subclass_name': cls.get('subclass_name', ''),
            'subclass_level': cls.get('subclass_level', 3),
            'class_table_columns': cls.get('class_table_columns', []),
            'trackable_features': cls.get('trackable_features', []),
            'class_spells': cls.get('class_spells', []),
            'unarmored_defense': cls.get('unarmored_defense', ''),
            'source': cls.get('source', ''),
            'is_official': cls.get('is_official', True),
            'is_custom': cls.get('is_custom', False),
            'is_legacy': cls.get('is_legacy', False),
        }

    def _insert_class_with_subclasses(self, cursor, class_name, cls) -> int:
        """INSERT OR IGNORE one bundled class and its subclasses; returns how many rows were added.

        The class name is UNIQUE and so is (subclass name, class), so rows that
        already exist - including any the user has customised - are never
        touched.
        """
        added = 0
        cursor.execute(CLASSES.insert_statement(or_ignore=True),
                       CLASSES.values(self._bundled_class_row(class_name, cls)))
        added += cursor.rowcount

        cursor.execute("SELECT id FROM classes WHERE name = ? COLLATE NOCASE", (class_name,))
        row = cursor.fetchone()
        if not row:
            return added
        for sub in cls.get('subclasses', []):
            cursor.execute(SUBCLASSES.insert_statement(or_ignore=True),
                           SUBCLASSES.values({**sub, 'name': sub.get('name', ''), 'class_id': row[0]}))
            added += cursor.rowcount
        return added

    def _seed_missing_subclasses(self, cursor, classes=None) -> bool:
        """INSERT OR IGNORE the bundled classes.json classes and subclasses.

        Rows that already exist - including any the user has customised - are
        never touched. ``classes`` is an already-loaded ``{name: class}`` (the
        legacy bundle). Returns True on success.
        """
        import os

        if classes is None:
            path = self._bundled_json_path('classes.json')
            if not os.path.exists(path):
                return True
        try:
            if classes is None:
                classes = self._load_json(path).get('classes', {})
            added = 0
            for class_name, cls in classes.items():
                added += self._insert_class_with_subclasses(cursor, class_name, cls)
            if added:
                print(f"Added {added} bundled class/subclass row(s)")
            return True
        except Exception as e:
            print(f"Error seeding subclasses (will retry next launch): {e}")
            return False

    def _link_official_content(self, cursor) -> bool:
        """Wrap mentions of other objects in official content as [[links]].

        Runs the same sweep (object_link_sweep) that was applied to the bundled
        source files, so an upgraded install matches a fresh one. Only official
        rows are touched: custom rows never are, and spells the user has edited
        (is_modified) are left alone. Legacy (2014) rows are neither swept nor
        offered as link targets: their text was linked when it was imported
        (to the legacy versions of what it names), and 2024 text must keep
        pointing at 2024 content. Idempotent. Returns True on success.
        """
        try:
            import object_link_sweep as sweep
            from tools.spell_data import get_all_spells

            official_spells = {s['name'] for s in get_all_spells() if not s.get('is_legacy')}

            def official_names(table, extra=""):
                cursor.execute(f"SELECT name FROM {table} WHERE is_custom = 0{extra}")
                return [r[0] for r in cursor.fetchall()]

            current = " AND is_legacy = 0"   # tables with a legacy flag

            uni = sweep.Universe({
                'spell': official_spells,
                'feat': official_names('feats', current),
                'lineage': official_names('lineages', current),
                'background': official_names('backgrounds', current),
                'class': official_names('classes', current),
                'subclass': official_names('subclasses', current),
                # Mount animals are left out (prose naming them means the creature; see tools/link_sweep.py)
                'equipment': official_names('equipment', " AND tags_json NOT LIKE '%\"Mount\"%'"),
                'magic_item': official_names('magic_items'),
                # Summoned creatures belong to their spell, not to the prose universe
                'monster': official_names('monsters', " AND spell_only = 0"),
            })
            changes: list = []

            def swept(fn, rec):
                before = len(changes)
                fn(rec, uni, changes)
                return len(changes) > before

            cursor.execute("SELECT id, name, description FROM spells WHERE is_modified = 0 AND is_legacy = 0")
            for row_id, name, desc in cursor.fetchall():
                rec = {'name': name, 'description': desc}
                if name in official_spells and swept(sweep.sweep_spell, rec):
                    cursor.execute("UPDATE spells SET description = ? WHERE id = ?",
                                   (rec['description'], row_id))

            for table, fn, extra in (('feats', sweep.sweep_feat, current),
                                     ('equipment', sweep.sweep_equipment, ""),
                                     ('magic_items', sweep.sweep_magic_item, "")):
                cursor.execute(f"SELECT id, name, description FROM {table} WHERE is_custom = 0{extra}")
                for row_id, name, desc in cursor.fetchall():
                    rec = {'name': name, 'description': desc}
                    if swept(fn, rec):
                        cursor.execute(f"UPDATE {table} SET description = ? WHERE id = ?",
                                       (rec['description'], row_id))

            monster_groups = ('traits', 'actions', 'bonus_actions', 'reactions',
                              'legendary_actions', 'lair_actions')
            cursor.execute("SELECT id, name, description, " + ", ".join(f"{g}_json" for g in monster_groups)
                           + " FROM monsters WHERE is_custom = 0 AND spell_only = 0")
            for row in cursor.fetchall():
                rec = {'name': row[1], 'description': row[2]}
                for group, raw in zip(monster_groups, row[3:]):
                    rec[group] = json.loads(raw or '[]')
                if swept(sweep.sweep_monster, rec):
                    cursor.execute(
                        "UPDATE monsters SET description = ?, "
                        + ", ".join(f"{g}_json = ?" for g in monster_groups) + " WHERE id = ?",
                        [rec['description']] + [json.dumps(rec[g]) for g in monster_groups] + [row[0]])

            cursor.execute("SELECT id, name, description, traits_json FROM lineages WHERE is_custom = 0 AND is_legacy = 0")
            for row_id, name, desc, traits in cursor.fetchall():
                rec = {'name': name, 'description': desc, 'traits': json.loads(traits or '[]')}
                if swept(sweep.sweep_lineage, rec):
                    cursor.execute("UPDATE lineages SET description = ?, traits_json = ? WHERE id = ?",
                                   (rec['description'], json.dumps(rec['traits']), row_id))

            cursor.execute("SELECT id, name, description, equipment FROM backgrounds WHERE is_custom = 0 AND is_legacy = 0")
            for row_id, name, desc, gear in cursor.fetchall():
                rec = {'name': name, 'description': desc, 'equipment': gear}
                if swept(sweep.sweep_background, rec):
                    cursor.execute("UPDATE backgrounds SET description = ?, equipment = ? WHERE id = ?",
                                   (rec['description'], rec['equipment'], row_id))

            cursor.execute("SELECT id, name, class_features_json FROM classes WHERE is_custom = 0 AND is_legacy = 0")
            for row_id, name, levels_json in cursor.fetchall():
                levels = json.loads(levels_json or '{}')
                before = len(changes)
                sweep.sweep_class_levels(levels, name, uni, changes)
                if len(changes) > before:
                    cursor.execute("UPDATE classes SET class_features_json = ? WHERE id = ?",
                                   (json.dumps(levels), row_id))

            cursor.execute("SELECT id, name, description, features_json FROM subclasses WHERE is_custom = 0 AND is_legacy = 0")
            for row_id, name, desc, features_json in cursor.fetchall():
                data = json.loads(features_json or '{}')
                rec = {'name': name, 'description': desc, 'features': data.get('features', [])}
                if swept(sweep.sweep_subclass, rec):
                    cursor.execute("UPDATE subclasses SET description = ?, features_json = ? WHERE id = ?",
                                   (rec['description'], json.dumps(data), row_id))

            print(f"Linked object mentions in {len(changes)} official text fields")
            return True
        except Exception as e:
            print(f"Error linking object mentions (will retry next launch): {e}")
            return False

    def _seed_collection(self, cursor, coll, filename: str, key: str, data=None,
                         success: str = "Migrated {n} rows to database",
                         failure: str = "Error migrating rows: {e}") -> bool:
        """INSERT OR IGNORE the rows of a bundled JSON file into a collection's table.

        Idempotent (the table's name column is UNIQUE), so it is safe both when first populating a fresh
        database and from an upgrade migration that backfills installs predating the content. User-created
        rows are never touched. ``data`` is an already-loaded ``{key: [...]}`` (the legacy bundle) used
        instead of the file. Returns False if loading failed."""
        import os

        if data is None:
            path = self._bundled_json_path(filename)
            if not os.path.exists(path):
                return True
        try:
            if data is None:
                data = self._load_json(path)
            rows = data.get(key, [])
            for item in rows:
                cursor.execute(coll.seed_sql, coll.seed_values(item))
            print(success.format(n=len(rows)))
        except Exception as e:
            print(failure.format(e=e))
            return False
        return True

    def _seed_equipment_and_magic_items(self, cursor):
        """INSERT OR IGNORE the bundled equipment.json / magic_items.json rows (see _seed_collection)."""
        self._seed_collection(cursor, EQUIPMENT, 'equipment.json', 'equipment',
                              success="Seeded {n} equipment items", failure="Error seeding equipment: {e}")
        self._seed_collection(cursor, MAGIC_ITEMS, 'magic_items.json', 'magic_items',
                              success="Seeded {n} magic items", failure="Error seeding magic items: {e}")

    def _seed_lineages(self, cursor, data=None) -> bool:
        """INSERT OR IGNORE the bundled lineages.json rows (name is UNIQUE).

        ``data`` is an already-loaded ``{"lineages": [...]}`` (the legacy bundle).
        """
        return self._seed_collection(cursor, LINEAGES, 'lineages.json', 'lineages', data,
                                     "Migrated {n} lineages to database", "Error migrating lineages: {e}")

    def _seed_feats(self, cursor, data=None) -> bool:
        """INSERT OR IGNORE the bundled feats.json rows (name is UNIQUE).

        ``data`` is an already-loaded ``{"feats": [...]}`` (the legacy bundle).
        """
        return self._seed_collection(cursor, FEATS, 'feats.json', 'feats', data,
                                     "Migrated {n} feats to database", "Error migrating feats: {e}")

    def _seed_backgrounds(self, cursor, data=None) -> bool:
        """INSERT OR IGNORE the bundled backgrounds.json rows (name is UNIQUE).

        ``data`` is an already-loaded ``{"backgrounds": [...]}`` (the legacy bundle).
        """
        return self._seed_collection(cursor, BACKGROUNDS, 'backgrounds.json', 'backgrounds', data,
                                     "Migrated {n} backgrounds to database", "Error migrating backgrounds: {e}")

    def _seed_missing_spells(self, cursor, spells=None) -> int:
        """Insert bundled official spells (tools/spell_data.py) whose name isn't in the table.

        Matches by name, case-insensitively, so a spell the user already has -
        official, edited or homebrew - is never touched or duplicated. Uses the
        caller's cursor (bulk_insert_spells opens its own connection, which
        would contend with the migration's open transaction). ``spells`` is the
        legacy bundle's list.
        """
        if spells is None:
            from tools.spell_data import get_all_spells
            spells = get_all_spells()

        added = 0
        for spell in spells:
            cursor.execute("SELECT 1 FROM spells WHERE name = ? COLLATE NOCASE", (spell['name'],))
            if cursor.fetchone():
                continue
            cursor.execute("""
                INSERT INTO spells (
                    name, level, casting_time, ritual, range_value,
                    components, duration, concentration, description, source, original_name, is_legacy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                spell['name'], spell['level'], spell['casting_time'],
                1 if spell.get('ritual', False) else 0, spell['range_value'],
                spell['components'], spell['duration'],
                1 if spell.get('concentration', False) else 0,
                spell.get('description', ''), spell.get('source', ''),
                spell.get('original_name', spell['name']),
                1 if spell.get('is_legacy', False) else 0
            ))
            spell_id = cursor.lastrowid
            cursor.executemany(
                "INSERT OR IGNORE INTO spell_classes (spell_id, class_name) VALUES (?, ?)",
                [(spell_id, c) for c in spell.get('classes', [])])
            cursor.executemany(
                "INSERT OR IGNORE INTO spell_tags (spell_id, tag) VALUES (?, ?)",
                [(spell_id, self.normalize_tag(t)) for t in spell.get('tags', [])])
            added += 1
        return added

    def _legacy_bundle(self) -> dict:
        """The bundled 2014 content (legacy_2014.json): spells, feats, lineages, backgrounds, classes.

        Entries whose name 2024 content already owns are stored as "Name (Legacy)"
        (see legacy_content.py); every record carries is_legacy.
        """
        import os

        path = self._bundled_json_path('legacy_2014.json')
        if not os.path.exists(path):
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _seed_legacy_content(self, cursor, include_spells: bool = True) -> bool:
        """Insert the bundled legacy (2014) content, by name, skipping what exists.

        Nothing already there - official, edited or user-made - is touched.
        ``include_spells`` is False on a fresh database, whose spells are
        populated separately (populate_initial_spells). Returns True on success.
        """
        try:
            bundle = self._legacy_bundle()
            if not bundle:
                return True
            ok = self._seed_lineages(cursor, {'lineages': bundle.get('lineages', [])})
            ok = self._seed_feats(cursor, {'feats': bundle.get('feats', [])}) and ok
            ok = self._seed_backgrounds(cursor, {'backgrounds': bundle.get('backgrounds', [])}) and ok
            ok = self._seed_missing_subclasses(cursor, bundle.get('classes', {})) and ok
            if include_spells:
                added = self._seed_missing_spells(cursor, bundle.get('spells', []))
                if added:
                    print(f"Added {added} bundled legacy spell(s)")
            return ok
        except Exception as e:
            print(f"Error seeding legacy content (will retry next launch): {e}")
            return False

    def _seed_new_official_content(self, cursor) -> bool:
        """Backfill the bundled content that shipped after the tables were first seeded.

        Everything is inserted only if its name is missing, so existing rows
        (including user edits and homebrew that reuse a name) are left alone.
        Returns True on success; on failure the schema version is not advanced
        and the whole thing is retried on the next launch.
        """
        try:
            ok = self._seed_lineages(cursor)
            ok = self._seed_feats(cursor) and ok
            ok = self._seed_backgrounds(cursor) and ok
            added = self._seed_missing_spells(cursor)
            if added:
                print(f"Added {added} bundled spell(s)")
            return self._seed_missing_subclasses(cursor) and ok
        except Exception as e:
            print(f"Error seeding new official content (will retry next launch): {e}")
            return False

    def _migrate_json_to_database(self, cursor):
        """Migrate data from JSON files to database tables."""
        import os
        
        # Migrate lineages and feats (shared with the v23 backfill migration)
        self._seed_lineages(cursor)
        self._seed_feats(cursor)

        # Migrate equipment + magic items (shared with the v16 backfill migration)
        self._seed_equipment_and_magic_items(cursor)

        # Bundled monsters (shared with the v28 backfill migration)
        self._seed_official_monsters(cursor)

        # Bundled rules pages (shared with the v31 backfill migration)
        self._seed_official_rules(cursor)

        # Migrate backgrounds (shared with the v23 backfill migration)
        self._seed_backgrounds(cursor)

        # Migrate classes
        classes_path = resource_path('classes.json')
        if os.path.exists(classes_path):
            try:
                data = self._load_json(classes_path)
                classes_data = data.get('classes', {})
                for class_name, cls in classes_data.items():
                    self._insert_class_with_subclasses(cursor, class_name, cls)
                print(f"Migrated {len(classes_data)} classes to database")
            except Exception as e:
                print(f"Error migrating classes: {e}")

        # Bundled legacy (2014) content (its spells come with populate_initial_spells)
        self._seed_legacy_content(cursor, include_spells=False)
    
    @staticmethod
    def _load_json(path: str):
        """Parse a bundled JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _update_classes_from_bundle(self, cursor, columns: tuple, summary: str, failure: str):
        """Set these columns of every class in the bundled classes.json (matched by name).

        Printed on success: ``summary`` with ``{n}`` = how many classes were updated; on a failure: ``failure``
        with ``{e}``."""
        classes_path = resource_path('classes.json')
        if os.path.exists(classes_path):
            try:
                classes_data = self._load_json(classes_path).get('classes', {})
                sql = CLASSES.update_by_name_sql(*columns)
                updated_count = 0
                for class_name, cls in classes_data.items():
                    row = self._bundled_class_row(class_name, cls)
                    cursor.execute(sql, CLASSES.column_values(row, *columns) + [class_name])
                    if cursor.rowcount > 0:
                        updated_count += 1
                print(summary.format(n=updated_count))
            except Exception as e:
                print(failure.format(e=e))

    def _remigrate_class_features(self, cursor):
        """Re-migrate class_features_json from JSON file to fix incorrect field mapping."""
        self._update_classes_from_bundle(
            cursor,
            ('class_features_json', 'saving_throws_json', 'skill_proficiencies_json', 'num_skills',
             'starting_equipment_json', 'spellcasting_json'),
            "Re-migrated class features for {n} classes", "Error re-migrating class features: {e}")

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
        self._update_classes_from_bundle(
            cursor,
            ('class_table_columns_json', 'trackable_features_json', 'class_spells_json', 'unarmored_defense'),
            "Updated {n} classes with missing column data", "Error updating class columns: {e}")
    
    def _fix_subclass_features_v11(self, cursor):
        """Fix missing subclass feature placeholders for Bard and other classes."""
        # Update class_features_json with the corrected levels data
        self._update_classes_from_bundle(
            cursor, ('class_features_json',),
            "Fixed subclass features for {n} classes", "Error fixing subclass features: {e}")

    def _refresh_spell_descriptions_v13(self, cursor):
        """Refresh spell descriptions with table formatting from spell_data.py.
        
        Only updates spells where is_modified = 0 (not user-modified).
        """
        from tools.spell_data import get_all_spells
        
        spells = get_all_spells()
        updated_count = 0
        
        for spell in spells:
            name = spell.get('name')
            description = spell.get('description', '')
            
            if not name or not description:
                continue
            
            # Only update spells that haven't been modified by the user
            cursor.execute("""
                UPDATE spells 
                SET description = ? 
                WHERE name = ? COLLATE NOCASE AND is_modified = 0
            """, (description, name))
            
            if cursor.rowcount > 0:
                updated_count += 1
        
        print(f"Refreshed descriptions for {updated_count} spells")
    
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

        # ...and the bundled legacy (2014) spells
        count += self.bulk_insert_spells(self._legacy_bundle().get('spells', []))
        
        # Also add the summon-spell creatures
        self._populate_initial_summon_monsters()
        
        return count
    
    def _seed_official_rules(self, cursor) -> bool:
        """Insert the bundled rules.json pages whose name is not in the table.

        Idempotent (existing rows - user edits or homebrew pages that reuse a
        name - are left alone), so it serves both a fresh database and the
        backfill migration. Returns True on success.
        """
        import os
        path = self._bundled_json_path('rules.json')
        if not os.path.exists(path):
            return True
        try:
            records = self._load_json(path).get('rules', [])
            added = 0
            for rec in records:
                name = (rec.get('name') or '').strip()
                if not name:
                    continue
                cursor.execute("SELECT 1 FROM rules WHERE name = ? COLLATE NOCASE", (name,))
                if cursor.fetchone():
                    continue
                cursor.execute("""
                    INSERT INTO rules (name, category, description, source, tags_json, sort_order,
                                       is_official, is_custom)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 0)
                """, (
                    name,
                    rec.get('category', ''),
                    rec.get('description', ''),
                    rec.get('source', ''),
                    json.dumps(rec.get('tags', [])),
                    int(rec.get('order', 0) or 0),
                ))
                added += 1
            if added:
                print(f"Seeded {added} rules pages")
            return True
        except Exception as e:
            print(f"Error seeding rules (will retry next launch): {e}")
            return False

    def _seed_official_monsters(self, cursor) -> bool:
        """Insert the bundled monsters.json records whose name is not in the table.

        Idempotent (existing rows - user edits, homebrew or summons that reuse a
        name - are left alone), so it serves both a fresh database and the
        backfill migration. Returns True on success.
        """
        import os
        path = self._bundled_json_path('monsters.json')
        if not os.path.exists(path):
            return True
        try:
            from monster import Monster
            records = self._load_json(path).get('monsters', [])
            added = 0
            for rec in records:
                name = rec.get('name', '')
                if not name:
                    continue
                cursor.execute("SELECT 1 FROM monsters WHERE name = ? COLLATE NOCASE", (name,))
                if cursor.fetchone():
                    continue
                monster = Monster.from_dict(rec)
                monster.is_official, monster.is_custom, monster.spell_only = True, False, False
                monster.spell_name = ''
                self._insert_monster_row(cursor, monster.to_dict())
                added += 1
            if added:
                print(f"Seeded {added} monsters")
            return True
        except Exception as e:
            print(f"Error seeding monsters (will retry next launch): {e}")
            return False

    def _populate_initial_summon_monsters(self):
        """Add the official summon-spell creatures (tools/stat_block_data) as
        spell-only monsters. Skips any the spell already has, so it is safe to
        run at every startup and picks up creatures added in a later release."""
        from monster import Monster
        from tools.stat_block_data import get_all_stat_blocks

        with self.get_connection() as conn:
            cursor = conn.cursor()

            for sb in get_all_stat_blocks():
                spell_name = sb.get('spell_name')
                if not spell_name:
                    continue

                cursor.execute("SELECT id, source FROM spells WHERE name = ? COLLATE NOCASE",
                               (spell_name,))
                spell = cursor.fetchone()
                if not spell:
                    print(f"Warning: Spell '{spell_name}' not found for summon '{sb.get('name')}'")
                    continue

                cursor.execute("SELECT spell_id FROM monsters WHERE name = ? COLLATE NOCASE",
                               (sb.get('name', ''),))
                existing = cursor.fetchone()
                if existing:
                    if existing['spell_id'] != spell['id']:
                        print(f"Warning: a monster named '{sb.get('name')}' already exists; "
                              f"not adding the summon for '{spell_name}'")
                    continue

                monster = Monster.from_stat_block(sb, source=spell['source'] or '')
                monster.spell_name = spell_name
                self._insert_monster_row(cursor, monster.to_dict())

    def _convert_stat_blocks_to_monsters(self, cursor) -> bool:
        """Convert each row of the legacy stat_blocks table into a spell-only
        monster (migration 27). Blocks that match the bundled data stay official
        (with whatever edits the user made); the rest are the user's own. A name
        already taken by another spell's creature gets "(Spell)" appended.
        Idempotent. Returns True on success."""
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'stat_blocks'")
            if cursor.fetchone() is None:
                return True

            from monster import Monster
            from tools.stat_block_data import get_all_stat_blocks
            bundled = {(sb['spell_name'].lower(), sb['name'].lower())
                       for sb in get_all_stat_blocks() if sb.get('spell_name')}

            cursor.execute("""
                SELECT sb.*, s.name AS spell_name, s.source AS spell_source
                FROM stat_blocks sb JOIN spells s ON s.id = sb.spell_id
                ORDER BY sb.id
            """)
            converted = 0
            for row in cursor.fetchall():
                data = dict(row)
                cursor.execute("SELECT spell_id FROM monsters WHERE name = ? COLLATE NOCASE",
                               (data['name'],))
                clash = cursor.fetchone()
                if clash and clash[0] == data['spell_id']:
                    continue                      # converted on an earlier attempt
                monster = Monster.from_stat_block(data, source=data.get('spell_source') or '')
                if clash:
                    monster.name = f"{data['name']} ({data['spell_name']})"
                    cursor.execute("SELECT 1 FROM monsters WHERE name = ? COLLATE NOCASE", (monster.name,))
                    if cursor.fetchone():
                        continue
                official = (data['spell_name'].lower(), data['name'].lower()) in bundled
                monster.is_official, monster.is_custom = official, not official
                self._insert_monster_row(cursor, monster.to_dict())
                converted += 1
            if converted:
                print(f"Converted {converted} summon stat block(s) to monsters")
            return True
        except Exception as e:
            print(f"Error converting stat blocks to monsters (will retry next launch): {e}")
            return False

    def get_schema_version(self) -> int:
        """Get current schema version."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()
            return row['version'] if row else 0
    
    # ---- the pieces every spell write shares

    @staticmethod
    def _spell_core_values(spell_data: dict) -> tuple:
        """The columns every spell write has in common, in table order (name ... source)."""
        return (
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
        )

    def _insert_spell_row(self, cursor, spell_data: dict, original_name: str) -> int:
        """Insert the spell's own row (not its classes or tags); returns its ID."""
        cursor.execute("""
            INSERT INTO spells (
                name, level, casting_time, ritual, range_value,
                components, duration, concentration, description, source, original_name, is_legacy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, self._spell_core_values(spell_data) + (
            original_name,
            1 if spell_data.get('is_legacy', False) else 0,
        ))
        spell_id = cursor.lastrowid
        assert spell_id is not None, "Failed to get spell ID after insert"
        return spell_id

    @staticmethod
    def _insert_spell_classes(cursor, spell_id: int, spell_data: dict):
        classes = spell_data.get('classes', [])
        if classes:
            cursor.executemany(
                "INSERT INTO spell_classes (spell_id, class_name) VALUES (?, ?)",
                [(spell_id, cls) for cls in classes]
            )

    def _insert_spell_tags(self, cursor, spell_id: int, spell_data: dict):
        """Insert the spell's tags, normalized."""
        tags = spell_data.get('tags', [])
        if tags:
            normalized_tags = [self.normalize_tag(tag) for tag in tags]
            cursor.executemany(
                "INSERT INTO spell_tags (spell_id, tag) VALUES (?, ?)",
                [(spell_id, tag) for tag in normalized_tags]
            )

    @staticmethod
    def _spell_dict(row, classes: List[str], tags: List[str]) -> dict:
        """A spell row, with its classes and tags already fetched, as a dictionary."""
        return {
            'id': row['id'],
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
            spell_id = self._insert_spell_row(cursor, spell_data, spell_data.get('original_name', ''))
            self._insert_spell_classes(cursor, spell_id, spell_data)
            self._insert_spell_tags(cursor, spell_id, spell_data)
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
            """, self._spell_core_values(spell_data) + (
                1 if spell_data.get('is_modified', False) else 0,
                1 if spell_data.get('is_legacy', False) else 0,
                spell_id,
            ))

            # Classes and tags: delete and re-insert
            cursor.execute("DELETE FROM spell_classes WHERE spell_id = ?", (spell_id,))
            self._insert_spell_classes(cursor, spell_id, spell_data)
            cursor.execute("DELETE FROM spell_tags WHERE spell_id = ?", (spell_id,))
            self._insert_spell_tags(cursor, spell_id, spell_data)

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
        
        return self._spell_dict(row, classes, tags)
    
    @staticmethod
    def _group_by_spell(rows, column: str) -> dict:
        """``spell_id -> [row[column], ...]`` for rows of a spell_classes / spell_tags query."""
        grouped = {}
        for r in rows:
            grouped.setdefault(r['spell_id'], []).append(r[column])
        return grouped

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
        
        classes_by_spell = self._group_by_spell(cursor.fetchall(), 'class_name')
        
        # Batch fetch all tags for these spells (1 query instead of N)
        cursor.execute(f"""
            SELECT spell_id, tag 
            FROM spell_tags 
            WHERE spell_id IN ({placeholders})
        """, spell_ids)
        
        tags_by_spell = self._group_by_spell(cursor.fetchall(), 'tag')
        
        # Convert rows to dictionaries using the pre-fetched data
        return [self._spell_dict(row, classes_by_spell.get(row['id'], []), tags_by_spell.get(row['id'], []))
                for row in rows]
    
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
                      has_material: Optional[bool] = None,
                      titles_only: bool = False) -> List[dict]:
        """
        Search spells with various filters using optimized SQL queries.
        
        Args:
            search_text: Text to search in name, description, and tags (with titles_only: in the name alone)
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
            if search_text and titles_only:
                conditions.append("s.name LIKE ? COLLATE NOCASE")
                params.append(f"%{search_text}%")
            elif search_text:
                # Name and description through the full-text index when it is there, plus any tag match
                search_pattern = f"%{search_text}%"
                if self._search_index_available(conn):
                    # (matching ids are joined through a temp table: there can be hundreds)
                    cursor.execute("CREATE TEMP TABLE IF NOT EXISTS _search_ids (id INTEGER PRIMARY KEY)")
                    cursor.execute("DELETE FROM _search_ids")
                    cursor.executemany("INSERT INTO _search_ids (id) VALUES (?)",
                                       [(i,) for i in search_index.item_ids(conn, search_text, 'Spells')])
                    conditions.append("""(
                        s.id IN (SELECT id FROM _search_ids) OR
                        EXISTS (SELECT 1 FROM spell_tags st WHERE st.spell_id = s.id AND st.tag LIKE ? COLLATE NOCASE)
                    )""")
                    params.append(search_pattern)
                else:
                    conditions.append("""(
                        s.name LIKE ? COLLATE NOCASE OR
                        strip_links(s.description) LIKE ? COLLATE NOCASE OR
                        EXISTS (SELECT 1 FROM spell_tags st WHERE st.spell_id = s.id AND st.tag LIKE ? COLLATE NOCASE)
                    )""")
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
                    spell_id = self._insert_spell_row(cursor, spell_data, original_name)
                    self._insert_spell_classes(cursor, spell_id, spell_data)
                    self._insert_spell_tags(cursor, spell_id, spell_data)
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
    
    def reset_all_spell_modified_flags(self) -> int:
        """
        Reset all spell is_modified flags to 0.
        
        Returns:
            Number of spells affected
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE spells SET is_modified = 0 WHERE is_modified = 1")
            return cursor.rowcount
    
    # ==================== LINEAGE METHODS ====================
    
    def get_all_lineages(self) -> List[dict]:
        """Get all lineages from the database."""
        return self._coll_get_all(LINEAGES)

    def get_lineage_by_name(self, name: str) -> Optional[dict]:
        """Get a lineage by name (case-insensitive)."""
        return self._coll_get_by_name(LINEAGES, name)

    def insert_lineage(self, lineage_data: dict) -> int:
        """Insert a new lineage."""
        return self._coll_insert(LINEAGES, lineage_data)

    def update_lineage(self, lineage_id: int, lineage_data: dict) -> bool:
        """Update an existing lineage."""
        return self._coll_update(LINEAGES, lineage_id, lineage_data)

    def delete_lineage(self, lineage_id: int) -> bool:
        """Delete a lineage by ID."""
        return self._coll_delete(LINEAGES, lineage_id)

    # ==================== FEAT METHODS ====================
    
    def get_all_feats(self) -> List[dict]:
        """Get all feats from the database."""
        return self._coll_get_all(FEATS)

    def get_feat_by_name(self, name: str) -> Optional[dict]:
        """Get a feat by name (case-insensitive)."""
        return self._coll_get_by_name(FEATS, name)

    def insert_feat(self, feat_data: dict) -> int:
        """Insert a new feat."""
        return self._coll_insert(FEATS, feat_data)

    def update_feat(self, feat_id: int, feat_data: dict) -> bool:
        """Update an existing feat."""
        return self._coll_update(FEATS, feat_id, feat_data)

    def delete_feat(self, feat_id: int) -> bool:
        """Delete a feat by ID."""
        return self._coll_delete(FEATS, feat_id)

    # ==================== EQUIPMENT METHODS ====================

    def get_all_equipment(self) -> List[dict]:
        """Get all equipment from the database."""
        return self._coll_get_all(EQUIPMENT)

    def get_equipment_by_name(self, name: str) -> Optional[dict]:
        """Get an equipment item by name (case-insensitive)."""
        return self._coll_get_by_name(EQUIPMENT, name)

    def insert_equipment(self, item_data: dict) -> int:
        """Insert a new equipment item."""
        return self._coll_insert(EQUIPMENT, item_data)

    def update_equipment(self, item_id: int, item_data: dict) -> bool:
        """Update an existing equipment item."""
        return self._coll_update(EQUIPMENT, item_id, item_data)

    def delete_equipment(self, item_id: int) -> bool:
        """Delete an equipment item by ID."""
        return self._coll_delete(EQUIPMENT, item_id)

    # ==================== RULES METHODS ====================

    def get_all_rules(self) -> List[dict]:
        """All rules pages, in book order (the user's own after them)."""
        return self._coll_get_all(RULES)

    def get_rule_by_name(self, name: str) -> Optional[dict]:
        """A rules page by name (case-insensitive)."""
        return self._coll_get_by_name(RULES, name)

    def insert_rule(self, data: dict) -> int:
        """Insert a new rules page."""
        return self._coll_insert(RULES, data)

    def update_rule(self, rule_id: int, data: dict) -> bool:
        """Update an existing rules page."""
        return self._coll_update(RULES, rule_id, data)

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a rules page by ID."""
        return self._coll_delete(RULES, rule_id)

    # ==================== MAGIC ITEM METHODS ====================

    def get_all_magic_items(self) -> List[dict]:
        """Get all magic items from the database."""
        return self._coll_get_all(MAGIC_ITEMS)

    def get_magic_item_by_name(self, name: str) -> Optional[dict]:
        """Get a magic item by name (case-insensitive)."""
        return self._coll_get_by_name(MAGIC_ITEMS, name)

    def insert_magic_item(self, item_data: dict) -> int:
        """Insert a new magic item."""
        return self._coll_insert(MAGIC_ITEMS, item_data)

    def update_magic_item(self, item_id: int, item_data: dict) -> bool:
        """Update an existing magic item."""
        return self._coll_update(MAGIC_ITEMS, item_id, item_data)

    def delete_magic_item(self, item_id: int) -> bool:
        """Delete a magic item by ID."""
        return self._coll_delete(MAGIC_ITEMS, item_id)

    # ==================== MONSTER METHODS ====================

    # (column, default) for every plain-valued monster column, and for every
    # JSON-valued one (stored as "<key>_json"). The dict keys match
    # Monster.to_dict(), so a monster dict maps straight onto a row. The spell a
    # summoned creature belongs to is stored as spell_id but travels as
    # `spell_name` (see _MONSTER_SELECT).
    _MONSTER_SCALARS = (
        ("epithet", ""), ("size", "Medium"), ("creature_type", ""), ("creature_subtype", ""),
        ("alignment", "Unaligned"), ("ac", 10), ("initiative_proficiency", 0), ("hp", 1),
        ("hit_dice", ""), ("can_hover", False),
        ("ac_text", ""), ("hp_text", ""), ("speed_text", ""), ("cr_text", ""), ("skills_text", ""),
        ("show_initiative", True), ("challenge_rating", "0"), ("lair_xp", None),
        ("legendary_action_uses", 3), ("legendary_action_uses_in_lair", None),
        ("legendary_actions_intro", ""), ("lair_actions_intro", ""), ("description", ""),
        ("source", ""), ("is_official", True), ("is_custom", False), ("spell_only", False),
    )
    _MONSTER_BOOL_COLUMNS = {"can_hover", "show_initiative", "is_official", "is_custom", "spell_only"}
    _MONSTER_JSONS = (
        ("speeds", {}), ("ability_scores", {}), ("saving_throws", {}), ("skills", {}),
        ("damage_vulnerabilities", []), ("damage_resistances", []),
        ("damage_immunities", []), ("condition_immunities", []),
        ("senses", []), ("languages", []), ("gear", []),
        ("traits", []), ("actions", []), ("bonus_actions", []), ("reactions", []),
        ("legendary_actions", []), ("lair_actions", []),
        ("habitat", []), ("treasure", []),
    )

    # Every monster read joins its spell so the dict carries `spell_name`.
    _MONSTER_SELECT = ("SELECT m.*, s.name AS spell_name FROM monsters m "
                       "LEFT JOIN spells s ON s.id = m.spell_id")

    def _monster_columns(self) -> List[str]:
        """Every writable monster column, in the order _monster_values() yields."""
        return (["name"] + [c for c, _ in self._MONSTER_SCALARS]
                + [f"{k}_json" for k, _ in self._MONSTER_JSONS] + ["spell_id"])

    def _monster_values(self, cursor, data: dict) -> list:
        values = [data['name']]
        for column, default in self._MONSTER_SCALARS:
            value = data.get(column, default)
            values.append(int(bool(value)) if column in self._MONSTER_BOOL_COLUMNS else value)
        for key, default in self._MONSTER_JSONS:
            values.append(json.dumps(data.get(key, default)))
        values.append(self._spell_id_by_name(cursor, data.get('spell_name')))
        return values

    @staticmethod
    def _spell_id_by_name(cursor, name: Optional[str]) -> Optional[int]:
        if not name:
            return None
        cursor.execute("SELECT id FROM spells WHERE name = ? COLLATE NOCASE", (name,))
        row = cursor.fetchone()
        return row[0] if row else None

    def _insert_monster_row(self, cursor, monster_data: dict) -> int:
        columns = self._monster_columns()
        cursor.execute(
            f"INSERT INTO monsters ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' * len(columns))})",
            self._monster_values(cursor, monster_data))
        return cursor.lastrowid or 0

    def get_all_monsters(self) -> List[dict]:
        """Get all monsters (including spell-only summons) from the database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"{self._MONSTER_SELECT} ORDER BY m.name")
            return [self._row_to_monster_dict(row) for row in cursor.fetchall()]

    def get_monster_by_name(self, name: str) -> Optional[dict]:
        """Get a monster by name (case-insensitive)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"{self._MONSTER_SELECT} WHERE m.name = ? COLLATE NOCASE", (name,))
            row = cursor.fetchone()
            return self._row_to_monster_dict(row) if row else None

    def get_monsters_for_spell_by_name(self, spell_name: str) -> List[dict]:
        """Get the creatures a spell summons."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"{self._MONSTER_SELECT} WHERE s.name = ? COLLATE NOCASE ORDER BY m.name",
                           (spell_name,))
            return [self._row_to_monster_dict(row) for row in cursor.fetchall()]

    def insert_monster(self, monster_data: dict) -> int:
        """Insert a new monster."""
        with self.get_connection() as conn:
            return self._insert_monster_row(conn.cursor(), monster_data)

    def update_monster(self, monster_id: int, monster_data: dict) -> bool:
        """Update an existing monster."""
        columns = self._monster_columns()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE monsters SET {', '.join(f'{c} = ?' for c in columns)}, "
                f"updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                self._monster_values(cursor, monster_data) + [monster_id])
            return cursor.rowcount > 0

    def delete_monster(self, monster_id: int) -> bool:
        """Delete a monster by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM monsters WHERE id = ?", (monster_id,))
            return cursor.rowcount > 0

    def _row_to_monster_dict(self, row) -> dict:
        """Convert a database row to a monster dictionary (Monster.to_dict() shape)."""
        result = {'id': row['id'], 'name': row['name'], 'spell_name': row['spell_name'] or ''}
        for column, default in self._MONSTER_SCALARS:
            value = row[column]
            if column in self._MONSTER_BOOL_COLUMNS:
                value = bool(value)
            elif value is None and default is not None:
                value = default
            result[column] = value
        for key, default in self._MONSTER_JSONS:
            try:
                value = json.loads(row[f"{key}_json"])
            except (ValueError, TypeError):
                value = None
            result[key] = value if isinstance(value, type(default)) else default
        return result

    # ==================== BACKGROUND METHODS ====================
    
    def get_all_backgrounds(self) -> List[dict]:
        """Get all backgrounds from the database."""
        return self._coll_get_all(BACKGROUNDS)

    def get_background_by_name(self, name: str) -> Optional[dict]:
        """Get a background by name (case-insensitive)."""
        return self._coll_get_by_name(BACKGROUNDS, name)

    def insert_background(self, bg_data: dict) -> int:
        """Insert a new background."""
        return self._coll_insert(BACKGROUNDS, bg_data)

    def update_background(self, bg_id: int, bg_data: dict) -> bool:
        """Update an existing background."""
        return self._coll_update(BACKGROUNDS, bg_id, bg_data)

    def delete_background(self, bg_id: int) -> bool:
        """Delete a background by ID."""
        return self._coll_delete(BACKGROUNDS, bg_id)

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
        return self._coll_insert(CLASSES, class_data)

    def update_class(self, class_id: int, class_data: dict) -> bool:
        """Update an existing class."""
        return self._coll_update(CLASSES, class_id, class_data)

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
        return self._coll_insert(SUBCLASSES, subclass_data)

    def update_subclass(self, subclass_id: int, subclass_data: dict) -> bool:
        """Update an existing subclass."""
        return self._coll_update(SUBCLASSES, subclass_id, subclass_data)

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
        Search every collection for items whose name or text contains each word of `query`.
        Returns list of dicts with 'name', 'section', 'id' and 'in_name' (False when only the
        item's text matched). Name matches come first.
        """
        query = (query or "").strip()
        if not query:
            return []

        with self.get_connection() as conn:
            if self._search_index_available(conn):
                hits = search_index.search(conn, query, limit=limit)
                return self._label_subclass_hits(conn, hits)
            return self._global_search_by_name(conn, query, limit)

    def _search_index_available(self, conn) -> bool:
        """Whether the full-text index can be used (checked once per database object)."""
        if self._search_index_ready is None:
            self._search_index_ready = search_index.ensure(conn)
        return self._search_index_ready

    def rebuild_search_index(self) -> bool:
        """Build the full-text index again from scratch. Returns False if SQLite can't index."""
        with self.get_connection() as conn:
            self._search_index_ready = search_index.rebuild(conn)
            return self._search_index_ready

    @staticmethod
    def _label_subclass_hits(conn, hits: List[dict]) -> List[dict]:
        """Subclass hits are shown as "Name (Class)"."""
        ids = [h['id'] for h in hits if h['section'] == 'Subclasses']
        if not ids:
            return hits
        rows = conn.execute(
            "SELECT s.id, c.name FROM subclasses s JOIN classes c ON s.class_id = c.id "
            f"WHERE s.id IN ({','.join('?' * len(ids))})", ids).fetchall()
        class_of = {r[0]: r[1] for r in rows}
        for h in hits:
            if h['section'] == 'Subclasses' and h['id'] in class_of:
                h['name'] = f"{h['name']} ({class_of[h['id']]})"
        return hits

    def _global_search_by_name(self, conn, query: str, limit: int) -> List[dict]:
        """Name-only search, for SQLite builds without the full-text index."""
        results = []
        pattern = f"%{query}%"
        cursor = conn.cursor()
        for section, (table, _cols, where) in search_index.SOURCES.items():
            if section == 'Subclasses':
                continue
            extra = f" AND {where}" if where else ""
            cursor.execute(f"SELECT id, name FROM {table} WHERE name LIKE ? COLLATE NOCASE{extra} "
                           "ORDER BY name LIMIT ?", (pattern, limit))
            for row in cursor.fetchall():
                results.append({'id': row['id'], 'name': row['name'], 'section': section,
                                'in_name': True})
        cursor.execute("""
            SELECT s.id, s.name, c.name as class_name FROM subclasses s
            JOIN classes c ON s.class_id = c.id
            WHERE s.name LIKE ? COLLATE NOCASE
            ORDER BY s.name LIMIT ?
        """, (pattern, limit))
        for row in cursor.fetchall():
            results.append({'id': row['id'], 'name': f"{row['name']} ({row['class_name']})",
                            'section': 'Subclasses', 'in_name': True})
        results.sort(key=lambda x: x['name'].lower())
        return results[:limit]


