"""
What the guided tour (``ui/tutorial.py``) says, and how it gets the window to each place it talks about.

The tour runs in a tab of its own, so the user's tabs are left as they were, and that tab closes when the
tour ends. For the character sheet part it makes an example character (a Cleric 3 / Fighter 1, so there is
something to show for multiclassing and automatic spells) and deletes it again at the end. The name of that
character is kept in the settings while the tour runs, so if the app is closed half way through it is still
cleaned up at the next start (``remove_leftover_example``).

Every step's ``prepare`` puts the window in the state the step needs from scratch, and its ``leave`` undoes
what it opened, so Back works from anywhere.
"""

from typing import List, Optional

from ui.tutorial import Step, find_named, viewable

EXAMPLE_NAME = "Tour Example Cleric"

COLLECTIONS = "Collections"
SHEETS = "Character sheets"
TOOLS = "Game Tools"


def first_viewable(*widgets):
    for widget in widgets:
        if viewable(widget):
            return widget
    return None


def remove_leftover_example(main_window) -> None:
    """Delete the example character a tour left behind (the app was closed during the tour)."""
    settings_manager = main_window.settings_manager
    name = getattr(settings_manager.settings, "tutorial_example_character", "")
    if not name:
        return
    _delete_character(main_window, name)
    settings_manager.update(tutorial_example_character="")


def _delete_character(main_window, name: str) -> None:
    from ui.character_sheet_view import get_sheet_manager
    try:
        if main_window.character_manager.get_character(name) is not None:
            main_window.character_manager.delete_character(name)
        get_sheet_manager().delete_sheet(name)
    except Exception as e:
        print(f"Could not remove the tour's example character: {e}")


class TourHost:
    """Moves the main window around for the tour."""

    def __init__(self, main_window):
        self.mw = main_window
        self.tab_id: Optional[str] = None
        self.return_to: Optional[str] = main_window._current_tab_id
        self.example: Optional[str] = None

    # ---- the tour's tab

    def tab(self) -> str:
        mw = self.mw
        if self.tab_id not in mw._tab_views:
            index = None
            if mw._current_tab_id in mw._tab_views and mw._tab_views[mw._current_tab_id]['type'] != 'settings':
                index = mw.tab_bar.get_tab_index(mw._current_tab_id) + 1
            self.tab_id = mw._open_page_in_new_tab("home", index=index)
        if mw._current_tab_id != self.tab_id:
            mw.tab_bar.select_tab(self.tab_id)
        return self.tab_id

    def info(self) -> dict:
        return self.mw._tab_views.get(self.tab(), {})

    def page(self, page_type: str, character: Optional[str] = None):
        """Show a page in the tour's tab; returns its view."""
        mw = self.mw
        tid = self.tab()
        info = mw._tab_views[tid]
        if page_type == "collections" and info.get('type') == "collections":
            if info.get('current_collection'):
                mw._back_to_collections()
            return info.get('view')
        shown = getattr(info.get('view'), 'current_character', None)
        same_sheet = page_type != "character_sheet" or (
            (shown is not None and shown.name == character) or info.get('pending_character') == character)
        if info.get('type') != page_type or not same_sheet:
            mw._navigate_tab(tid, page_type, character=character)
        return mw._tab_views[tid].get('view')

    def collection(self, key: str):
        """Show a collection page (Spells, Feats, ...) in the tour's tab; returns it."""
        mw = self.mw
        self.page("collections")
        tid = self.tab()
        info = mw._tab_views[tid]
        if info.get('current_collection') != key:
            mw._navigate_to_collection_in_tab(tid, key)
        return info.get('sub_view')

    def view(self):
        return self.info().get('view')

    def sub_view(self):
        return self.info().get('sub_view')

    # ---- the example character

    def example_character(self) -> str:
        mw = self.mw
        if self.example and mw.character_manager.get_character(self.example) is not None:
            return self.example
        from character import CharacterSpellList, ClassLevel, update_subclass_spells
        from spell import CharacterClass
        from ui.character_sheet_view import get_sheet_manager

        taken = {c.name for c in mw.character_manager.characters}
        name, n = EXAMPLE_NAME, 2
        while name in taken:
            name, n = f"{EXAMPLE_NAME} {n}", n + 1
        # Remember it before it exists, so a crash half way still gets it cleaned up next time
        mw.settings_manager.update(tutorial_example_character=name)

        character = CharacterSpellList(name=name)
        character.classes.append(ClassLevel(character_class=CharacterClass.CLERIC, level=3, subclass="Life Domain"))
        character.classes.append(ClassLevel(character_class=CharacterClass.FIGHTER, level=1))
        character.lineage = "Dwarf"
        character.feats = ["Alert"]
        update_subclass_spells(character)
        mw.character_manager.add_character(character)

        sheets = get_sheet_manager()
        sheet = sheets.get_or_create_sheet(name, character)
        scores = sheet.ability_scores
        scores.strength, scores.dexterity, scores.constitution = 14, 10, 14
        scores.intelligence, scores.wisdom, scores.charisma = 8, 16, 12
        sheets.update_sheet(name, sheet)
        self.example = name
        return name

    def sheet(self, tab: str = "front"):
        """The example character's sheet, showing ``tab`` (front, inventory, spells)."""
        view = self.page("character_sheet", character=self.example_character())
        if view is not None and getattr(view, '_current_tab', 'front') != tab:
            view._show_sheet_tab(tab)
        return view

    def sheet_part(self, name: str):
        view = self.view()
        content = getattr(view, 'sheet_content', None)
        return find_named(content, name) if content is not None else None

    # ---- the end

    def finish(self, finished: bool):
        mw = self.mw
        # The character goes first, so its sheet page sees it's gone and doesn't save itself back
        if self.example:
            _delete_character(mw, self.example)
        if getattr(mw.settings_manager.settings, "tutorial_example_character", ""):
            mw.settings_manager.update(tutorial_example_character="")
        if self.tab_id in mw._tab_views:
            for tab in list(mw.tab_bar._tabs):
                if tab.tab_id == self.tab_id:
                    mw.tab_bar._on_tab_close(tab)
                    break
        if self.return_to in mw._tab_views:
            mw.tab_bar.select_tab(self.return_to)
        elif mw._current_tab_id not in mw._tab_views:
            ids = mw.tab_bar.get_tab_ids()
            if ids:
                mw.tab_bar.select_tab(ids[-1])


# ---------------------------------------------------------------------------------------------- the steps

def build_steps(host: TourHost) -> List[Step]:
    h = host

    def spells():
        return h.collection("spells")

    def pick(view, *names):
        """The first of ``names`` that is in the collection (else any spell)."""
        manager = view.spell_manager
        for name in names:
            spell = manager.get_spell(name)
            if spell is not None:
                return spell
        return manager.spells[0] if manager.spells else None

    def show_spell(*names):
        view = spells()
        spell = pick(view, *names)
        if spell is not None:
            view.select_spell(spell.name)
        return view

    def open_filters():
        view = spells()
        if not view._advanced_expanded:
            view._toggle_advanced_filters()

    def close_filters():
        view = h.sub_view()
        if getattr(view, '_advanced_expanded', False):
            view._toggle_advanced_filters()

    def select_mode():
        view = spells()
        panel = view.spell_list
        panel.set_multi_select(True)
        if not panel.checked_count():
            for name in ("Bless", "Cure Wounds", "Shield of Faith"):
                spell = view.spell_manager.get_spell(name)
                if spell is not None:
                    panel._toggle_checked(spell)

    def end_select_mode():
        view = h.sub_view()
        if hasattr(view, 'spell_list'):
            view.spell_list.set_multi_select(False)

    def compare():
        view = show_spell("Fireball")
        other = pick(view, "Lightning Bolt", "Ice Storm")
        if other is not None and view.spell_detail._current_spell is not None:
            view._show_compare_panel(other)

    def end_compare():
        view = h.sub_view()
        if getattr(view, '_compare_mode', False):
            view._close_compare_panel()

    def characters_page():
        view = h.page("characters")
        if getattr(view, 'builder', None) is not None:
            view.close_builder()
        return view

    def open_builder():
        view = h.page("characters")
        return view.open_builder() if hasattr(view, 'open_builder') else None

    def close_builder():
        view = h.view()
        if getattr(view, 'builder', None) is not None:
            view.close_builder()

    def builder_part():
        builder = getattr(h.view(), 'builder', None)
        return getattr(builder, 'steps_panel', None)

    def tool_card(key):
        return lambda: (h.view().cards_by_key.get(key) if hasattr(h.view(), 'cards_by_key') else None)

    def tool_step(key, title, text):
        return Step(TOOLS, title, text, prepare=lambda: h.page("game_tools"), target=tool_card(key))

    return [
        # ------------------------------------------------------------------ welcome
        Step("Welcome", "Welcome to Spellbook!",
             "This short tour shows what Spellbook can do for you, in three parts: the collections of "
             "spells, monsters, items and rules; character sheets that do the maths for you; and the "
             "Game Tools for running a session.\n\n"
             "The tour opens its own tab and closes it when it's done. Press Skip tour (or Esc) to stop "
             "at any time, and start it again from Settings > Help. The arrow keys move back and forward.",
             prepare=lambda: h.tab()),

        # ------------------------------------------------------------------ collections
        Step(COLLECTIONS, "Everything in one place",
             "Each card opens a collection: Spells, Feats, Lineages, Magic Items, Classes, Backgrounds, "
             "Equipment, Monsters and the Rules. They all work the same way, so what you learn on the "
             "Spells page works everywhere.",
             prepare=lambda: h.page("collections"),
             target=lambda: getattr(h.view(), 'cards_frame', None)),
        Step(COLLECTIONS, "Search all of it at once",
             "Type here to search every collection together, by name or by the words in a description. "
             "Pick a result to jump straight to it.",
             prepare=lambda: h.page("collections"),
             target=lambda: getattr(h.view(), 'search_bar', None)),
        Step(COLLECTIONS, "Filters",
             "Narrow the list down by name, level and class. Every collection page has filters like "
             "these that fit what it holds: a monster's CR and type, an item's rarity, and so on.",
             prepare=spells, target=lambda: getattr(h.sub_view(), 'filter_bar', None)),
        Step(COLLECTIONS, "More filters and tags",
             "The Filters button opens the rest: ritual, concentration, components, casting time, range, "
             "duration, source book, and your own tags.\n\nTags are labels you give entries yourself "
             "(\"Fire\", \"Healing\", \"My campaign\"). Add them when you edit an entry, or to many at "
             "once with Select, then filter by them here.",
             prepare=open_filters, leave=close_filters,
             target=lambda: getattr(h.sub_view(), 'advanced_frame', None)),
        Step(COLLECTIONS, "Select many at once",
             "Select turns the list into tick boxes. Tick what you want (or All shown) and act on them "
             "all together: add them to a character, edit their tags, classes or source, or export them "
             "as a printable PDF. Done goes back to the normal list.",
             prepare=select_mode, leave=end_select_mode,
             target=lambda: getattr(h.sub_view(), 'spell_list', None)),
        Step(COLLECTIONS, "Right-click for more",
             "Right-click any entry in a list for its shortcuts. On spells that's Add to Spell List, "
             "which puts the spell on one of your characters (with a warning if it isn't on their class "
             "list or is too high level), and View and Compare.",
             prepare=lambda: show_spell("Fireball"),
             target=lambda: getattr(h.sub_view(), 'spell_list', None)),
        Step(COLLECTIONS, "View and compare",
             "View and Compare puts two entries side by side. With comparison highlights on (Settings), "
             "the better values show in green and the worse in red, so you can see at a glance which "
             "spell, item or monster comes out ahead.",
             prepare=compare, leave=end_compare, wait_ms=150,
             target=lambda: getattr(h.sub_view(), 'main_paned', None)),

        # ------------------------------------------------------------------ character sheets
        Step(SHEETS, "Your characters",
             "The Characters page (on Home) lists all your characters, with search, filters and sorting. "
             "Click one to open its sheet.\n\n"
             "New to making characters? The Character Builder walks you through it step by step. "
             "+ New Character makes a blank one to fill in yourself.",
             prepare=characters_page, target=lambda: getattr(h.view(), 'builder_btn', None)),
        Step(SHEETS, "The Character Builder",
             "One choice at a time: your class, a subclass if your level is high enough, species, "
             "background, ability scores (standard array, point buy or your own rolls), skills, spells "
             "and starting equipment. Each step explains the choice and shows the details from your "
             "collections, homebrew included.\n\n"
             "Nothing is saved until you press Create Character, and then the new character's sheet "
             "opens with everything filled in.",
             prepare=open_builder, leave=close_builder, wait_ms=150, target=builder_part),
        Step(SHEETS, "A character to look at",
             f"For this part the tour has made an example character, \"{EXAMPLE_NAME}\": a dwarf Life "
             "Domain Cleric 3 / Fighter 1. It's deleted again when the tour ends.",
             prepare=lambda: h.sheet("front"), wait_ms=200,
             target=lambda: h.sheet_part("basic_info")),
        Step(SHEETS, "Multiclassing",
             "Each class has its own level box, and the subclass choice appears once a class is high "
             "enough. The + button adds another class; setting a second class to level 0 removes it.\n\n"
             "Change a level and everything that follows from it updates: hit points, proficiency bonus, "
             "spell slots (shared the multiclass way), features and spells.",
             prepare=lambda: h.sheet("front"),
             target=lambda: getattr(h.view(), 'class_frame', None)),
        Step(SHEETS, "The sheet does the maths",
             "Type in an ability score and its modifier, saving throws and skills follow. Proficiency "
             "comes from the classes, and skills you tick add your proficiency bonus for you.",
             prepare=lambda: h.sheet("front"),
             target=lambda: h.sheet_part("ability_scores")),
        Step(SHEETS, "Combat numbers too",
             "Armor class is worked out from the armor and shield you pick (and Unarmored Defense), "
             "maximum HP from your class levels and Constitution, and initiative and speed from your "
             "abilities, lineage and feats. The Alert feat on this character is already counted in its "
             "initiative.",
             prepare=lambda: h.sheet("front"),
             target=lambda: h.sheet_part("combat")),
        Step(SHEETS, "Features and feats",
             "Everything your classes, subclass and lineage give you is listed here. Click any feature "
             "to read it in full.\n\n+ Add Feat picks feats from the collection; a feat's own effects "
             "and spells are applied, and right-clicking a feat removes it.",
             prepare=lambda: h.sheet("front"),
             target=lambda: h.sheet_part("features")),
        Step(SHEETS, "Long rest",
             "One click for the end of the day: hit points back to full, spell slots and feature uses "
             "restored, and hit dice back (all, half or none: you choose in Settings).",
             prepare=lambda: h.sheet("front"),
             target=lambda: getattr(h.view(), 'long_rest_btn', None)),
        Step(SHEETS, "Inventory",
             "The Inventory tab holds your coins, equipment and magic items. Items linked to the "
             "collections open their full entry, and the carry weight bar adds up what you're carrying "
             "against your Strength.",
             prepare=lambda: h.sheet("inventory"), leave=lambda: _sheet_front(h),
             target=lambda: first_viewable(getattr(h.view(), 'inventory_content', None),
                                           getattr(h.view(), 'inventory_tab_btn', None))),
        Step(SHEETS, "Spells, added for you",
             "The Spells tab is the character's spell book: slots to tick off, prepared spells and the "
             "spells known.\n\nSpells that come with a class, subclass, lineage or feat are added "
             "automatically. This cleric's Life Domain spells are already here, marked ★ (always "
             "prepared). + Add Spells picks more from the collection.",
             prepare=lambda: h.sheet("spells"), leave=lambda: _sheet_front(h), wait_ms=150,
             target=lambda: first_viewable(getattr(h.view(), 'spells_content', None),
                                           getattr(h.view(), 'spells_tab_btn', None))),

        # ------------------------------------------------------------------ game tools
        Step(TOOLS, "Game Tools",
             "Everything for running a game at the table. A quick look at each, then a closer look at "
             "the Homebrew Studio, Session and Tabletop.",
             prepare=lambda: h.page("game_tools"),
             target=lambda: getattr(h.view(), '_row', None)),
        tool_step("initiative", "Initiative Tracker",
                  "Turn order, HP, AC and conditions for everyone in a fight. Players can keep it in a "
                  "small window on top of their other apps."),
        tool_step("dice_analyzer", "Dice Analyzer",
                  "The odds of any roll, with advantage, rerolls and modifiers, or of a roll straight from "
                  "a character sheet."),
        tool_step("matchup", "Matchup",
                  "Two creatures or characters in a one-on-one fight: who's likely to win, and how fast."),
        tool_step("random_tables", "Random Tables",
                  "Keep d100 (or any) tables and roll on them. Dice and other tables a result names are "
                  "rolled too."),
        tool_step("calendar", "Calendar",
                  "Your campaign's calendar and clock with your own months and holidays, and progress bars "
                  "for things that take days."),
        tool_step("pdf_library", "PDF Library",
                  "Search the text of all your PDFs at once, and copy an entry's text from a page into a "
                  "collection."),
        Step(TOOLS, "Homebrew Studio",
             "Write your own spells, items, feats, monsters, classes and more. Pick what you're making, "
             "and the draft is saved as you type. Nothing goes into your collections until you press "
             "Publish, and the ⋯ menu exports the draft as a PDF.",
             prepare=lambda: h.page("studio"), wait_ms=300,
             target=lambda: getattr(h.view(), 'editor_pane', None)),
        Step(TOOLS, "Insights",
             "While you write, Insights lists existing content that does the same thing, so you can "
             "check you're not making something that's already there. For a monster it also checks "
             "its numbers against its challenge rating.",
             prepare=lambda: h.page("studio"),
             target=lambda: getattr(h.view(), 'insights', None)),
        Step(TOOLS, "Reference panels",
             "Keep official content open beside your draft for comparison: + Panel adds another one.",
             prepare=lambda: h.page("studio"),
             target=lambda: getattr(h.view(), 'refs_pane', None)),
        Step(TOOLS, "Session: host a game",
             "Session connects the computers at your table, over your home network or a VPN. As the DM, "
             "start a session and send the players the invite. It's encrypted, and you approve each "
             "player. Players without Spellbook can join from a web browser, even on a phone.",
             prepare=lambda: h.page("session"),
             target=lambda: first_viewable(getattr(h.view(), 'host_card', None), getattr(h.view(), 'body', None))),
        Step(TOOLS, "Session: join a game",
             "Players see sessions on the same network here, or paste the invite. Once in, there's chat "
             "(with whispers and dice rolls), and you can send each other characters and homebrew. The "
             "initiative tracker and tabletop are shared with everyone.",
             prepare=lambda: h.page("session"),
             target=lambda: first_viewable(getattr(h.view(), 'join_card', None), getattr(h.view(), 'body', None))),
        Step(TOOLS, "Tabletop: maps",
             "Battle maps with a square or hex grid, or none. Make a map with + New Map, and press Show "
             "to Players to put it on their screens when you host a session.",
             prepare=lambda: h.page("tabletop"), wait_ms=200,
             target=lambda: getattr(h.view(), 'head', None)),
        Step(TOOLS, "Tabletop: tools",
             "Move tokens, ping, measure, draw, and drop spell areas that light up who they hit. As the "
             "DM you also get fog of war, walls and doors that block the players' line of sight, and "
             "raised ground. Hover over a tool to see what it does.",
             prepare=lambda: h.page("tabletop"),
             target=lambda: getattr(h.view(), 'tools_panel', None)),
        Step(TOOLS, "Tabletop: tokens",
             "Add tokens from your monsters and characters, or from your own pictures. Give them HP and "
             "condition rings, hide them from players, or hand one to a player to move. Tokens are "
             "linked to the initiative tracker, so HP and conditions stay the same in both.",
             prepare=lambda: h.page("tabletop"),
             target=lambda: first_viewable(getattr(h.view(), 'side', None), getattr(h.view(), 'map_holder', None))),

        # ------------------------------------------------------------------ the end
        Step("Done", "That's the tour!",
             "Finish closes the tour's tab and the example character, and takes you back to where you "
             "were.\n\nWant to see it again? It's in Settings > Help, or press F1. Settings is also where "
             "you choose the theme, fonts and keyboard shortcuts, and back up everything."),
    ]


def _sheet_front(h: TourHost):
    view = h.view()
    if hasattr(view, '_show_sheet_tab') and getattr(view, '_current_tab', 'front') != 'front':
        view._show_sheet_tab('front')
