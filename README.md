# Spellbook

A desktop application for managing D&D 5th Edition spells, character sheets, and stat blocks with comprehensive search, filtering, and character management features.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-green.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite-orange.svg)

## Features

### Spell Management
- **Comprehensive Spell Database**: Pre-populated with D&D 5e spells from the SRD and other sources
- **Advanced Filtering**: Filter by level, class, casting time, duration, range, components, concentration, ritual, source, and tags
- **Full-Text Search**: Search spells by name, description, or tags
- **CRUD Operations**: Create, read, update, and delete spells
- **Import/Export**: Import spells from text files and export spell collections
- **Official/Unofficial Tagging**: Distinguish between official and homebrew spells

### Character Spell Lists
- **Multiple Characters**: Create and manage spell lists for multiple characters
- **Class Support**: All D&D 5e classes including non-spellcasters (Fighter, Rogue, Monk, Barbarian)
- **Multiclass Support**: Characters can have multiple classes with different levels
- **Spell Slot Tracking**: Track spell slot usage with automatic calculations based on class/level
- **Warlock Pact Magic**: Separate tracking for Warlock pact magic slots
- **Mystic Arcanum**: Track Warlock mystic arcanum usage (levels 6-9)
- **Cantrip Management**: Automatic cantrip limit tracking per class
- **Validation Warnings**: Optional warnings for class compatibility, spell level limits, and cantrip limits
- **Custom Class**: Configure custom spell slot limits for homebrew classes

### Character Sheets
- **Full D&D 5e Character Sheet**: Complete character sheet with all standard sections
- **Ability Scores**: Track all six ability scores with automatic modifier calculation
- **Saving Throws**: Proficiency tracking for all saves
- **Skills**: Full skill list with proficiency and expertise support
- **Combat Stats**: AC, Initiative, Speed, Hit Points with current/max/temp tracking
- **Hit Dice**: Independent tracking per die type (d6, d8, d10, d12) for multiclass characters
- **Death Saves**: Track successes and failures
- **Attacks**: Track up to 5 attacks with name, bonus, and damage
- **Class Features**: Automatic tracking of class-specific resources:
  - Barbarian: Rage uses and damage bonus
  - Bard: Bardic Inspiration uses and die type
  - Cleric/Paladin: Channel Divinity uses
  - Druid: Wild Shape uses and max CR
  - Fighter: Second Wind, Action Surge, Indomitable
  - Monk: Focus Points (Ki) and Martial Arts die
  - Paladin: Lay on Hands pool
  - Ranger: Favored Enemy uses
  - Rogue: Sneak Attack dice
  - Sorcerer: Sorcery Points
  - Warlock: Invocations known
  - Wizard: Arcane Recovery spell levels
  - Artificer: Infusions known and items
- **Long Rest**: One-click restoration of HP, hit dice, spell slots, and class features
- **Inventory Tab**: Equipment, currency (CP/SP/EP/GP/PP), and magic items with attunement tracking
- **Character Details**: Name, race, background, alignment, XP, age, height, weight
- **Notes & Personality**: Features/traits, proficiencies, notes, and personality sections

### Stat Blocks
- **Summoning Spell Support**: Attach creature stat blocks to summoning spells
- **Full Stat Block Display**: View creature stats, abilities, traits, actions, and more
- **Editable Stat Blocks**: Create and edit stat blocks with a dedicated editor
- **Pre-seeded Data**: Official stat blocks for common summoning spells

### User Interface
- **Modern Dark Theme**: Clean, modern UI with customizable themes
- **Responsive Layout**: Resizable panels with smooth animations
- **Keyboard Shortcuts**: Quick navigation with Escape to close dialogs
- **Debounced Search**: Smooth filtering without lag during typing

### Settings
- **Appearance Mode**: Dark, Light, or System theme
- **Notification Preferences**: Toggle spell added and rest notifications
- **Spell Warnings**: Configure warnings for cantrips, class compatibility, and spell levels
- **Character Sheet Options**:
  - Auto-calculate HP maximum
  - Auto-fill proficiencies for new sheets
  - Multiclass removal warning toggle
  - Long rest hit dice restoration (All/Half/None)

## Installation

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/spellbook.git
cd spellbook
```

2. Create a virtual environment (recommended):
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python main.py
```

### Optional: PIL Support
For better icon support, install Pillow:
```bash
pip install Pillow
```

## Project Structure

```
Spellbook/
├── main.py                 # Application entry point
├── database.py             # SQLite database handler with migrations
├── spell.py                # Spell data model and filtering logic
├── spell_manager.py        # Spell collection management
├── character.py            # Character spell list data model
├── character_manager.py    # Character persistence (JSON)
├── character_sheet.py      # Character sheet data model (abilities, skills, HP, etc.)
├── spell_slots.py          # Spell slot calculations by class/level
├── validation.py           # Spell validation for characters
├── settings.py             # Application settings management
├── theme.py                # Theme management and color schemes
├── stat_block.py           # Stat block data model
├── seed_stat_blocks.py     # Pre-seed official stat blocks
├── init_official_spells.py # Initialize official spell data
├── ui/
│   ├── __init__.py
│   ├── main_window.py      # Main application window
│   ├── spell_list.py       # Spell list panel with pagination
│   ├── spell_detail.py     # Spell detail view and compare
│   ├── spell_editor.py     # Spell create/edit dialog
│   ├── spell_lists_view.py # Character spell lists view
│   ├── character_editor.py # Character create/edit dialog
│   ├── character_sheet_view.py # Full character sheet interface
│   ├── settings_view.py    # Settings panel
│   ├── stat_block_display.py  # Stat block display widget
│   └── stat_block_editor.py   # Stat block editor dialog
├── tools/                  # Batch spell import scripts
├── requirements.txt        # Python dependencies
├── spellbook.db           # SQLite database (created on first run)
├── characters.json        # Character data (created on first run)
├── character_sheets.json  # Character sheet data (created on first run)
├── settings.json          # User settings (created on first run)
└── custom_theme.json      # Custom theme colors (optional)
```

## Architecture

### Data Layer

#### Database (`database.py`)
- SQLite database with schema versioning and migrations
- Tables: `spells`, `spell_classes`, `spell_tags`, `stat_blocks`, `schema_version`
- Indexes for fast querying on common filter fields
- Foreign key support with cascade deletes
- Batch query optimization to avoid N+1 queries

#### Data Models
- **`Spell`** (`spell.py`): Dataclass representing a spell with all properties
- **`CharacterSpellList`** (`character.py`): Character with class levels and known spells
- **`CharacterSheet`** (`character_sheet.py`): Full character sheet with abilities, skills, HP, equipment, etc.
- **`StatBlock`** (`stat_block.py`): Creature stat block with abilities and features
- **`AppSettings`** (`settings.py`): User preferences and warning toggles

### Manager Layer

#### SpellManager (`spell_manager.py`)
- CRUD operations for spells
- Filtering with SQL optimization and Python post-filters
- Import/export functionality
- Listener pattern for UI updates
- Legacy text file migration support

#### CharacterManager (`character_manager.py`)
- JSON persistence for character data
- CRUD operations for characters
- Listener pattern for UI updates

#### SettingsManager (`settings.py`)
- JSON persistence for settings
- Default values with user overrides
- Listener pattern for settings changes

### UI Layer

Built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for modern styling.

#### Main Components
- **`MainWindow`**: Tab-based layout with Spells, Spell Lists, and Settings views
- **`SpellListPanel`**: Paginated spell list with selection support
- **`SpellDetailPanel`**: Detailed spell view with stat block integration
- **`SpellListsView`**: Character management and spell list editing
- **`CharacterSheetView`**: Full D&D 5e character sheet with tabs for Stats, Spells, and Inventory

#### Dialog Components
- **`SpellEditorDialog`**: Create/edit spells with validation
- **`CharacterEditorDialog`**: Create/edit characters with multiclass support
- **`StatBlockEditorDialog`**: Full-featured stat block editor
- **`NewCharacterDialog`**: Quick character creation wizard

### Theme System (`theme.py`)

- Dark/Light mode support
- Customizable color schemes via `custom_theme.json`
- Listener pattern for live theme updates
- Semantic color naming (e.g., `button_danger`, `text_secondary`)

## Key Design Patterns

### Observer Pattern
Managers use listeners to notify UI of data changes:
```python
spell_manager.add_listener(self._on_spells_changed)
# ... later, when destroyed:
spell_manager.remove_listener(self._on_spells_changed)
```

### Context Manager for Database
All database operations use a context manager for automatic commit/rollback:
```python
with self.get_connection() as conn:
    cursor = conn.cursor()
    # ... operations ...
# Auto-commits on success, rollbacks on exception
```

### Debouncing for Search
Text input filtering uses debouncing to avoid excessive queries:
```python
self._filter_debounce_id = self.after(200, self._apply_debounced_filter)
```

## Configuration

### Settings (`settings.json`)
```json
{
  "appearance_mode": "dark",
  "theme_name": "default",
  "show_spell_added_notification": true,
  "show_rest_notification": true,
  "warn_too_many_cantrips": true,
  "warn_wrong_class": true,
  "warn_spell_too_high_level": true,
  "show_comparison_highlights": true,
  "auto_calculate_hp": true,
  "auto_fill_proficiencies": true,
  "warn_multiclass_removal": true,
  "long_rest_hit_dice": "all",
  "allow_delete_official_spells": false
}
```

### Custom Theme (`custom_theme.json`)
```json
{
  "dark": {
    "bg_primary": "#1a1a2e",
    "bg_secondary": "#16213e",
    "accent": "#e94560",
    "text_primary": "#ffffff"
  }
}
```

## Range Encoding

Spell ranges use a compact integer encoding:
| Value | Meaning |
|-------|---------|
| 0 | Self |
| 1 | Sight |
| 2 | Special |
| 3 | Touch |
| > 3 | Distance in feet |
| < 0 | Distance in miles (absolute value) |

## Building for Distribution

### Windows Executable
```bash
pip install pyinstaller
pyinstaller main.spec
```

The executable will be in `dist/Spellbook.exe`.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the application to verify
5. Submit a pull request

## License

This project is for personal, non-commercial use. D&D content is property of Wizards of the Coast.

## Acknowledgments

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for the modern UI framework
- Wizards of the Coast for D&D 5th Edition
