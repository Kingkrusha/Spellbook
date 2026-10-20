# Spellbook

A desktop app for running D&D 5th Edition (2024) games: browse the rules and every kind of content, build and play your characters, write your own homebrew, and run the table. Everything is in one place and works offline.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-green.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite-orange.svg)

The app opens on a Home page with three areas: **Collections**, **Characters** and **Game Tools**. Tabs work like a browser's, so you can keep a character sheet open next to the spell list. Your open tabs come back the next time you start the app.

## Collections

Look things up, search them, and add your own.

- **Spells**: Search and filter by level, class, casting time, duration, components, source, tags and more. Spells that appear in more than one edition show once, with a drop-down to switch between the 2024 and 2014 versions
- **Classes and subclasses**: Every class with its level-by-level features, plus the subclasses
- **Lineages (species), backgrounds and feats**: Traits, prerequisites and what each one gives you
- **Equipment and magic items**: Filter by type, price, tags and materials
- **Monsters**: The 2024 Monster Manual with full stat blocks, filters for type, size, CR, defenses and more
- **Rules**: The Free Basic Rules (2024) as searchable pages. The search reads the text of the rules, not just the titles, and puts the best match first (try searching *Stunned*)
- **2014 (Legacy) content** is included too and can be shown, hidden or limited to what 2024 didn't update (Settings)
- **Search everywhere**: Every collection has a search box with a **Titles only** option. A global search covers all of them at once, and descriptions link to each other (click a spell name inside a feat to open it)
- **Select several at once**: Press **Select** above a list to tick many entries, then add them all to a character, or change their tags, classes (spells) or source in one go
- **Your own content**: Add spells, feats, items, monsters, classes and more by hand, or paste text from a book and let the app fill in the form. Homebrew is marked with a `*`
- **Import and export**: Share homebrew as a file. Importing never overwrites official content, and mentions of other content are linked automatically, even across several files imported together

## Characters

- **Characters page**: All your characters in one list you can search, filter (class, species, background) and sort. Create, import and export them here
- **Character sheets**: Ability scores, skills, saves, combat stats, class features, species traits, feats, inventory with carrying weight, notes and a portrait
- **Works out the numbers for you**: Armor class, hit points, initiative, spell attack and save DC are calculated from the class, items, features and feats. Hover one to see how it was worked out, or type over it to set your own
- **Spells**: Track known and prepared spells, spell slots (including multiclass and Warlock pact magic), and see your spell attack and save DC. **+ Add Spells** searches only what your character can learn. Spells that your species, feats and features grant are added automatically
- **Roll effects**: Give your homebrew roll effects (a bonus to attacks, extra damage dice and so on) and the Dice Analyzer counts them in your odds
- **Your own look**: Every sheet can have its own colours and fonts

## Game Tools

- **Homebrew Studio**: Write homebrew with reference panels beside you. As you write, it points out existing content that already does the same thing, and checks a monster's numbers against its challenge rating
- **Dice Analyzer**: The odds of any roll, from `2d6+4` to advantage, disadvantage, rerolls and keeping the best dice: average, spread, the chance of reaching a number, and a chart of every result. It can use your character's own features
- **Matchup**: Pit two characters or monsters against each other and see who wins most often, how long the fight lasts and what turns it
- **Initiative Tracker**: Run combat with monsters, characters and events, groups that take turns together, conditions, and a round counter
- **Game sessions**: Host or join a game over your network. Chat, roll with `/roll`, link spells and items in messages, and send characters and homebrew to each other. Sessions are encrypted

## Make it yours

- **Themes**: Dark and light modes, 23 colour themes, and a Theme Studio to make your own
- **Fonts**: Pick the font for titles, headings and text across the whole app
- **Settings**: Choose what loads at start-up, which warnings to see, how legacy content is shown and more

## Getting started

**Windows and macOS**: download the latest build from the [Releases page](https://github.com/Kingkrusha/Spellbook/releases) and run it. Your characters, homebrew and settings are saved next to the app (on macOS, in `~/Library/Application Support/Spellbook/`), so back that folder up if you want to keep them safe.

On macOS the app isn't notarized (that needs a paid Apple account), so the first time, right-click `Spellbook.app`, choose **Open**, then **Open** again. After that it opens normally.

**From source** (Python 3.10 or newer):

```bash
git clone https://github.com/Kingkrusha/Spellbook.git
cd Spellbook
pip install -r requirements.txt
python main.py
```

## Still growing

Spellbook is still being built and more is on the way. Feedback, ideas and bug reports are very welcome and make a real difference: please open an [issue](https://github.com/Kingkrusha/Spellbook/issues) on GitHub.

## Disclaimer

Spellbook is a fan-made tool. I do not own any Dungeons & Dragons content: it is the property of Wizards of the Coast, and Spellbook is not affiliated with or endorsed by them.

Spellbook is for non-commercial use only. It will not be monetized. It is meant to be a convenient way to run your own games, not a way to copy or republish other people's work. Please do not use Spellbook to distribute material you do not own.

## Acknowledgments

- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) for the modern UI framework
- Wizards of the Coast for D&D 5th Edition
