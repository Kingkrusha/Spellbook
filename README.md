# Spellbook

A desktop application for managing D&D 5th Edition (2024) spells, characters, and content.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-green.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite-orange.svg)

## Features

- **Home page & tabs**: The app opens on a Home page with **Collections**, **Characters** and **Game Tools**. Tabs work like a browser's: click **+** for a new tab (it opens on Home), close one with its **×** or a middle click, drag to reorder, right-click for New/Duplicate/Close Other Tabs. Each tab navigates on its own, so you can keep a character sheet open next to the spell list. Your open tabs are remembered and reopened next time you start the app (turn this off under Settings > Loading Options)
- **Game sessions (LAN)**: Host or join an encrypted game over your network from **Game Tools > Session**: chat with your table (with a chat overlay that follows you to every page), roll dice with `/roll`, link spells and items, and send characters and homebrew to each other. See *LAN sessions* below
- **Characters page**: Every character in one list you can search, filter (class, species, background) and sort (name, level, class, species, background). Create, import and export characters here; click one to open its sheet
- **Spell Management**: Search, filter, create, and organize spells with full-text search and advanced filtering
- **Character Sheets**: Complete D&D 5e character sheets with ability scores, skills, combat stats, class features, and inventory
- **Spell Lists**: Per-character spell tracking with slot management, multiclass support, and Warlock pact magic
- **Stat Blocks**: Attach creature stat blocks to summoning spells
- **Collections Browser**: Browse official Lineages, Feats, Classes, Subclasses, and Backgrounds with global search
- **Legacy (2014) content**: The 2014 rules are bundled too (`legacy_2014.json`: spells, feats, species, backgrounds, classes and subclasses from the published 5e books, all flagged Legacy). A 2014 entry whose name 2024 content already uses is stored as `Name (Legacy)` (for example *Fireball (Legacy)*, *Fighter (Legacy)*); browsing lists show each spell, feat, species, background and class once, and the **Source** line of its page is a drop-down that switches between its versions (the 2024 one, the 2014 one, or a 2014 book's update such as Monsters of the Multiverse). The Legacy content setting (Settings) decides which versions are offered: everything, none, only 2014, or *Show Unupdated* (2014 versions only where there is no 2024 one)
- **Import/Export**: Import and export custom content (homebrew) as JSON files
- **Lineages**: Browse and create custom lineages (races) with trait descriptions
- **Feats**: Browse and create feats with prerequisites and spellcasting grants
- **Classes & Subclasses**: Browse official content and create homebrew classes with custom features
- **Backgrounds**: 50+ backgrounds from PHB 2024, Eberron, Sword Coast, and other official sources
- **Rich Text Editing**: Tables, spell links (`[[Fireball]]`), and bold formatting in all description editors
- **Theming**: Dark/Light modes, 23 built-in colour themes (each with its own colour for field labels such as "Casting Time:" and "Multiattack."), and a Theme Studio for creating your own (Settings > Appearance)
- **Typography**: Choose fonts for titles, headings, subheadings, normal and small text across the whole app (Settings > Typography)
- **Character portraits**: upload an image in the Personality card of a character sheet (stored in a `portraits/` folder and embedded in character exports)
- **Per-sheet styling**: Every character sheet can have its own colours and fonts, and you can click any part of the sheet to restyle just that element (the **Style** button on the sheet)
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

**Windows:**
```bash
pip install pyinstaller
pyinstaller main.spec
# Output: dist/spellbook.exe
```

**macOS:**
```bash
pip install -r requirements.txt pyinstaller
./build_mac.sh
# Output: dist/Spellbook.app  and  dist/Spellbook-macos-<arch>.zip
```
The macOS build needs a Tk-enabled Python (the python.org installer, or
`brew install python-tk`). It must run on a Mac - PyInstaller cannot
cross-compile from Windows.

### Downloading a release (macOS)

Release `.app` bundles are **not notarized** (notarization requires a paid Apple
Developer account). The first time you open one, macOS Gatekeeper will refuse it
with *"Spellbook can't be opened because Apple cannot check it for malicious
software."* To get past this **once**:

1. Right-click (or Control-click) `Spellbook.app` in Finder and choose **Open**.
2. Click **Open** in the dialog that appears.

Or, from Terminal:
```bash
xattr -dr com.apple.quarantine /path/to/Spellbook.app
```
After the first launch it opens normally like any other app. This is standard
for free, open-source Mac apps and costs nothing.

## Initiative tracker

**Game Tools > Initiative Tracker** runs combat for the table. It works on its own (no session needed),
and over a **LAN session** it is shared: each connected player automatically gets their own view of it.

- **Add** monsters (from the Monsters collection, with the HP and AC copied in; optionally rolling HP from
  its dice), your own characters, custom creatures, or **events** (a name that spans the whole table).
  Add several at once, numbered and optionally **grouped** so they take their turns together.
- **Initiative:** roll it, type it, or drag a row (⠿) to where you want it. **Next turn** moves the
  creature whose turn it is to the top and the one that just went to the bottom; the round counter
  tracks the lap. **Back** and **Undo** fix mistakes.
- **HP, AC and conditions** are changed from the table (click them). Changes belong to the tracker only -
  the character sheet or monster they were copied from is never touched.
- **Hide** a creature so it doesn't appear for players (a hidden player still sees themselves); un-hide
  it any time, or add it hidden. In **Settings** choose whether players see monster HP as numbers, a
  health bar or nothing, and whether they see monster AC; each creature can also override this.
- **Players** see the table in a resizable **pop-up window that stays on top of other apps** (pin it
  off with 📌), can edit their own HP, AC and conditions, and are told when it's their turn. The DM can
  **Pop out** the same window for a second monitor and **Preview** what a given player sees.
- **Over a session:** the DM's app is the only place the real encounter lives. Each player is sent only
  what they may see - hidden creatures, hidden HP/AC and DM notes never reach their computer - and their
  edits go to the DM's app, which applies them under the same rules (a player can only change their own
  character). Players' windows open by themselves when combat starts (Settings: `tracker_auto_open`),
  the DM can add a connected player's character from the **Player** tab, and players who are away show
  as *(offline)* until they reconnect to their character.
- **Conditions can have a duration** (rounds); it counts down when that creature's turn ends and the
  condition drops off at zero. *Back* does not give a round back - use *Undo*.
- **Shortcuts** on the DM page: Ctrl+→ next turn, Ctrl+← back, Ctrl+Z undo, Delete removes the selection.
- The encounter is saved as you go, so closing the app mid-fight doesn't lose it.
- **Platform notes:** on macOS use two-finger tap or Control-click for the row menu. The window stays
  above other apps' ordinary windows; macOS does not let it float over another app's *full-screen*
  space, and there is no taskbar flash for "your turn" (the banner and beep still happen). Windows
  does not float it over exclusive-full-screen games either.

## LAN sessions

One player (the DM) hosts; everyone else joins. Open **Game Tools > Session**.

**Hosting.** Pick a port (default 5150), an optional password, and whether you want to approve each
player. Press *Start session* and send players the invite shown on the Session page (one per network
address; the first is usually right). Players on the same network can also find the session in their
own list without an invite (untick *Let players on this network find it automatically* to hide it).

**Joining.** Sessions on your network are listed on the Session page; press *Join*. Because a
discovered session could be forged, you are first shown a short **security code** to compare with the
one on the DM's Session page. Over a VPN (Tailscale, Hamachi, ZeroTier) or on guest Wi-Fi that blocks
discovery, paste the DM's invite instead (`address:port#code`).

**Chat.** Plain messages go to everyone; `/w Name message` (or the *Whisper* button) is private.
`/roll 2d6+3`, `/roll d20+5 adv Perception`, `/roll 4d6kh3` roll dice (the host rolls, so nobody can
fudge); `/gmroll d20` is seen only by you and the DM. The 🔗 button links a spell, item or monster that
everyone can click. The chat overlay at the bottom of every page collapses to a small *Chat* button
that shows how many messages you have missed; on Windows it is translucent (adjust under Session >
Chat overlay).

**Sending things.** *Send characters / homebrew...* sends characters (with the homebrew they use) or
homebrew objects to one player or everyone. The receiver sees what is in it and what clashes with
their own content, chooses *keep both / replace / keep mine*, and only then is anything added.
Official content never travels and is never overwritten.

**Security.** All traffic is TLS 1.3. The host makes a throwaway certificate for each session, and
the invite or security code pins it, so someone else on the network can't pose as the DM. The host
approves each player and can set a password. Nothing arrives without the receiver's say-so, and
received data is validated and size-limited. A session only exists while the host has it open.

**Firewalls.** The first time you host, Windows Defender Firewall asks whether to allow Spellbook on
private networks - say yes, otherwise players can't connect (allow TCP on the session port and UDP
5151 for discovery). On macOS you will be asked to allow incoming connections and Local Network
access. Both are one-time prompts.

**Checking a build.** `Spellbook --lan-selftest result.json` starts a session with itself over
loopback and writes whether the encrypted stack works in that build.

## Data Storage

Writable user data lives outside the app so bundles stay read-only:

| Platform | Location |
|----------|----------|
| Windows (.exe) | next to the executable |
| macOS (.app)   | `~/Library/Application Support/Spellbook/` |
| Linux          | `$XDG_DATA_HOME/Spellbook/` (usually `~/.local/share/Spellbook/`) |
| Running from source | the project directory (unchanged) |

That directory holds the SQLite database (`spellbook.db`):
- **Spells**: All official and custom spells with tags and classes
- **Lineages**: Races with traits and source information
- **Feats**: Feats with prerequisites and spellcasting grants
- **Classes**: Class definitions with level features and subclasses
- **Backgrounds**: Backgrounds with skills, feats, and ability scores

User-specific data stored in JSON files:
- **characters.json**: Character spell lists
- **character_sheets.json**: Full character sheets
- **settings.json**: Application settings
- **custom_themes.json**: Your custom colour themes (an older `custom_theme.json` is imported automatically)
- **font_settings.json**: Typography settings
- **portraits/**: Character portrait images

On first run, official content is migrated from bundled JSON files to the database.

## Configuration

Settings are stored in `settings.json`.

### Themes and fonts

- **Settings > Appearance > Theme Studio** lists every theme with a colour strip. Click one to apply it
  instantly; **+ New theme** copies the selected theme so you can edit each colour (separately for light and
  dark mode) with a live preview. Themes can be duplicated, renamed, exported and imported as `.json` files.
- **Settings > Typography** sets a base font and, for each text role (title, heading, subheading, normal,
  small), an optional family, size, weight and italics. Changes apply immediately everywhere.
- **Character sheets**: the **Style** button opens a panel beside the sheet. *Pick an element* outlines what a
  click would select. A click selects the whole widget (its card, bar or box) and lets you restyle everything
  inside it at once (text colour, button and field colours, font, size); a double-click selects just the label or
  field under the pointer. Clicking the page background selects the whole sheet. Each element's own colours,
  font and shape can be changed too. Every
  colour also offers "All *role*" to recolour everything on the sheet that uses it. The *Colors* and *Fonts* tabs
  restyle the whole sheet (own base theme, own typography). Sheet styling is saved with the character sheet and
  overrides the app-wide settings on that sheet only.

## Project Structure

```
Spellbook/
├── main.py                 # Application entry point with splash screen
├── lan/                    # LAN sessions: TLS transport, host/client, discovery, dice, session service
├── transfer.py             # Sending characters and homebrew between players (no UI)
├── initiative_state.py     # Initiative tracker rules: turn order, groups, hiding, who may do what (no UI)
├── initiative_rows.py      # What the tracker table draws for a viewer (no UI)
├── initiative_sources.py   # Copies of HP/AC/initiative from sheets and monsters
├── tracker_hub.py          # The app's one encounter: autosave and the DM / player backends
├── conditions.py           # Condition names for the tracker
├── character_io.py         # Character export/import bundles (no UI)
├── tests/                  # pytest suite: python -m pytest tests (needs requirements-dev.txt)
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
├── monster.py              # Monster (creature stat block) data model and manager
├── stat_block.py           # Named trait/action entries used by monsters
├── spell_slots.py          # Spell slot calculations by class/level
├── validation.py           # Spell validation for characters
├── settings.py             # Application settings management
├── theme.py                # Theme management, built-in themes, custom themes
├── typography.py           # Text roles and fonts (app-wide and per-sheet)
├── data_migration.py       # Data backup and migration utilities
├── ui/                     # UI components
│   ├── main_window.py      # Main application window with tab navigation
│   ├── splash_screen.py    # Loading screen shown during startup
│   ├── tab_bar.py          # Browser-style tab bar (+ button, closable, draggable tabs)
│   ├── home_view.py        # Home page (Collections / Characters / Game Tools)
│   ├── characters_view.py  # Characters page: search, filter, sort, open, delete
│   ├── character_transfer.py # Character import/export (JSON)
│   ├── global_search.py    # Global search bar for collections
│   ├── collections_view.py # Collections browser with content import/export
│   ├── spells_view.py      # Spells page (search, filters, list, detail, compare) - one per tab
│   ├── lazy_destroy.py     # Takes old pages apart in small slices so the window never freezes
│   ├── virtual_list.py     # Virtualized list base for Feats/Lineages/Backgrounds/Equipment/Magic Items/Monsters (constant widget count, any size)
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
│   ├── monster_view.py     # Monster browser, filters and editor
│   └── monster_stat_block.py  # Stat block widget (Monsters page, spell page, link popups)
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
| `Monster` | monster.py | Creature stat block; also the creatures summoned by spells (`spell_only`) |

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
