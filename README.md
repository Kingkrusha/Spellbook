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
- **Lineages**: Browse and create custom lineages (races) with trait descriptions
- **Feats**: Browse and create feats with prerequisites and spellcasting grants
- **Classes & Subclasses**: Browse official content and create homebrew classes with custom features
- **Backgrounds**: 50+ backgrounds from PHB 2024, Eberron, Sword Coast, and other official sources
- **Rich Text Editing**: Tables, spell links (`[[Fireball]]`), and bold formatting in all description editors
- **Theming**: Dark/Light modes

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
# Output: dist/Spellbook.exe
```

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
├── main.py                 # Application entry point
├── database.py             # SQLite database with migrations
├── spell.py                # Spell data model and filtering
├── spell_manager.py        # Spell CRUD and filtering operations
├── character.py            # Character spell list data model
├── character_manager.py    # Character persistence (JSON)
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
│   ├── main_window.py      # Main application window with tabs
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
│   ├── rich_text_utils.py  # Rich text rendering/editing
│   ├── stat_block_display.py  # Stat block display widget
│   └── stat_block_editor.py   # Stat block editor dialog
├── *.json                  # Data files (created on first run)
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
- Loading/saving data from JSON files
- CRUD operations
- Listener pattern for UI updates

| Manager | Manages |
|---------|---------|
| `SpellManager` | Spells (SQLite) |
| `CharacterManager` | Character spell lists |
| `CharacterSheetManager` | Full character sheets |
| `ClassManager` | Classes and subclasses |
| `LineageManager` | Lineages |
| `FeatManager` | Feats |
| `BackgroundManager` | Backgrounds |

## License

This project is for personal, non-commercial use. D&D content is property of Wizards of the Coast.

## Acknowledgments

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for the modern UI framework
- Wizards of the Coast for D&D 5th Edition
