# Spellbook

A desktop application for managing D&D 5th Edition (2024) spells, characters, and content.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-green.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite-orange.svg)

## Features

- **Spell Management**: Search, filter, create, and organize spells with full-text search and advanced filtering
- **Character Sheets**: Complete D&D 5e character sheets with ability scores, skills, combat stats, class features, and inventory
- **Spell Lists**: Per-character spell tracking with slot management, multiclass support, and Warlock pact magic
- **Stat Blocks**: Attach creature stat blocks to summoning spells
- **Collections Browser**: Browse official Lineages, Feats, Classes, Subclasses, and Backgrounds with global search
- **Import/Export**: Import and export custom content (homebrew) as JSON files
- **Lineages**: Browse and create custom lineages (races) with trait descriptions
- **Feats**: Browse and create feats with prerequisites and spellcasting grants
- **Classes & Subclasses**: Browse official content and create homebrew classes with custom features
- **Backgrounds**: 50+ backgrounds from PHB 2024, Eberron, Sword Coast, and other official sources
- **Rich Text Editing**: Tables, spell links (`[[Fireball]]`), and bold formatting in all description editors
- **Theming**: Dark/Light modes with customizable themes
- **SQLite Database**: All content stored in a fast, portable SQLite database with automatic migrations
- **Splash Screen**: Loading screen with progress indicator during startup

## Installation

### Quick Start
```bash
git clone https://github.com/yourusername/spellbook.git
cd spellbook
pip install -r requirements.txt
python main.py
```

### Build Executable
```bash
pip install pyinstaller
pyinstaller main.spec
# Output: dist/spellbook.exe
```

## Data Storage

All application data is stored in SQLite database (`spellbook.db`):
- **Spells**: All official and custom spells with tags and classes
- **Lineages**: Races with traits and source information
- **Feats**: Feats with prerequisites and spellcasting grants
- **Classes**: Class definitions with level features and subclasses
- **Backgrounds**: Backgrounds with skills, feats, and ability scores

User-specific data stored in JSON files:
- **characters.json**: Character spell lists
- **character_sheets.json**: Full character sheets
- **settings.json**: Application settings
- **custom_theme.json**: Custom theme configuration

On first run, official content is migrated from bundled JSON files to the database.

## Configuration

Settings are stored in `settings.json`. Custom themes can be defined in `custom_theme.json`:

```json
{
  "dark": {
    "bg_primary": "#1a1a2e",
    "accent": "#e94560"
  }
}
```

## Project Structure

```
Spellbook/
├── main.py                 # Application entry point with splash screen
├── database.py             # SQLite database with schema migrations
├── spell.py                # Spell data model and filtering
├── spell_manager.py        # Spell CRUD and filtering operations
├── character.py            # Character spell list data model
├── character_manager.py    # Character spell list persistence (JSON)
├── character_sheet.py      # Full character sheet data model
├── character_class.py      # Class/subclass definitions and manager
├── lineage.py              # Lineage (race) data model and manager
├── feat.py                 # Feat data model and manager
├── background.py           # Background data model and manager
├── stat_block.py           # Creature stat block data model
├── spell_slots.py          # Spell slot calculations by class/level
├── validation.py           # Spell validation for characters
├── settings.py             # Application settings management
├── theme.py                # Theme management and color schemes
├── data_migration.py       # Data backup and migration utilities
├── ui/                     # UI components
│   ├── main_window.py      # Main application window with tab navigation
│   ├── splash_screen.py    # Loading screen shown during startup
│   ├── tab_bar.py          # Custom tab bar component
│   ├── global_search.py    # Global search bar for collections
│   ├── collections_view.py # Collections browser with import/export
│   ├── spell_list.py       # Paginated spell list panel
│   ├── spell_detail.py     # Spell detail view with popup
│   ├── spell_editor.py     # Spell create/edit dialog
│   ├── spell_lists_view.py # Character spell lists management
│   ├── character_editor.py # Character create/edit dialog
│   ├── character_sheet_view.py # Full character sheet UI
│   ├── classes_view.py     # Class browser with feature tables
│   ├── class_editor.py     # Class/subclass editor dialogs
│   ├── lineages_view.py    # Lineage browser and editor
│   ├── feats_view.py       # Feat browser and editor
│   ├── backgrounds_view.py # Background browser and editor
│   ├── settings_view.py    # Settings panel with preload options
│   ├── rich_text_utils.py  # Rich text rendering/editing
│   ├── stat_block_display.py  # Stat block display widget
│   └── stat_block_editor.py   # Stat block editor dialog
├── tools/                  # Data generation and updates
│   ├── spell_data.py       # Official spell definitions
│   ├── stat_block_data.py  # Official stat block definitions
│   └── update_spell_descriptions.py  # Spell text updates
├── *.json                  # Bundled official data (migrated to DB on first run)
└── spellbook.db            # SQLite database (created on first run)
```

## Data Classes

### Core Models

| Class | File | Description |
|-------|------|-------------|
| `Spell` | spell.py | Spell with level, school, components, description, classes |
| `CharacterSpellList` | character.py | Character's known/prepared spells, slots, feats, lineage |
| `CharacterSheet` | character_sheet.py | Full sheet: abilities, skills, HP, inventory, attacks |
| `StatBlock` | stat_block.py | Creature stats, abilities, traits, actions for summons |

### Content Models

| Class | File | Description |
|-------|------|-------------|
| `CharacterClassDefinition` | character_class.py | Class with levels, features, spellcasting, subclasses |
| `SubclassDefinition` | character_class.py | Subclass with features and spell lists |
| `Lineage` | lineage.py | Race with traits, size, speed, creature type |
| `Feat` | feat.py | Feat with type, prerequisites, spellcasting grants |
| `Background` | background.py | Background with skills, tools, ability scores, feats |

### Managers

Each content type has a corresponding manager class that handles:
- Database operations (CRUD via SQLite)
- Caching for performance
- Listener pattern for UI updates
- Import/export to JSON

| Manager | Manages | Storage |
|---------|---------|---------|
| `SpellManager` | Spells, tags, classes | SQLite |
| `FeatManager` | Feats | SQLite |
| `ClassManager` | Classes and subclasses | SQLite |
| `LineageManager` | Lineages | SQLite |
| `BackgroundManager` | Backgrounds | SQLite |
| `CharacterManager` | Character spell lists | JSON |
| `CharacterSheetManager` | Full character sheets | JSON |

## License

This project is for personal, non-commercial use. D&D content is property of Wizards of the Coast.

## Acknowledgments

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for the modern UI framework
- Wizards of the Coast for D&D 5th Edition
