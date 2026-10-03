"""
Main application window for D&D Spellbook (CustomTkinter version).
"""

import customtkinter as ctk
from typography import ui_font
import tkinter as tk
from tkinter import messagebox, filedialog
from typing import List, Optional, Dict
from spell_manager import SpellManager
from character_manager import CharacterManager
from spell import Spell, CharacterClass, AdvancedFilters, TagFilterMode, SourceFilterMode
from settings import SettingsManager, get_settings_manager
from validation import validate_spell_for_character
from theme import get_theme_manager
import tab_session
from ui.restyle import install_global as install_global_restyler, restyle_app
from ui.tab_bar import DraggableTabBar
from ui.filter_widgets import TagFilterDialog, SourceFilterDialog
from ui.lazy_view import LazyView

# Collections a tab can be showing (also what a restored tab may reopen on)
COLLECTION_KEYS = ("spells", "classes", "feats", "lineages", "backgrounds",
                   "equipment", "magic_items", "monsters")

# Pause between startup preload steps, so the window stays responsive
PRELOAD_STEP_GAP_MS = 350


class MainWindow(ctk.CTkFrame):
    """Main application window: a browser-style tab bar over the page the active tab shows."""
    
    def __init__(self, parent, progress_callback=None):
        super().__init__(parent, fg_color="transparent")
        
        self._progress_callback = progress_callback
        
        # Initialize managers
        self._update_progress("Loading spell database...", 0.35)
        self.spell_manager = SpellManager()
        self.spell_manager.load_spells()
        
        self._update_progress("Loading characters...", 0.45)
        self.character_manager = CharacterManager()
        self.character_manager.add_error_listener(self._on_data_save_error)
        self.character_manager.load_characters()

        from ui.character_sheet_view import get_sheet_manager
        get_sheet_manager().add_error_listener(self._on_data_save_error)
        
        self.settings_manager = get_settings_manager()
        self._init_session()
        
        # On first run, mark all existing spells as "Official". (The summon-spell
        # creatures are added by the spell manager's load, not here.)
        if not self.settings_manager.settings.initial_official_tag_applied:
            if len(self.spell_manager.spells) > 0:
                count = self.spell_manager.mark_all_spells_official()
                print(f"First run: marked {count} spells as Official.")

            self.settings_manager.settings.initial_official_tag_applied = True
            self.settings_manager.save()
        
        # Apply appearance mode from settings
        ctk.set_appearance_mode(self.settings_manager.settings.appearance_mode)
        # Apply the saved colour theme before any view is built, so everything
        # renders with the right palette from the start.
        theme = get_theme_manager()
        try:
            theme.set_theme(getattr(self.settings_manager.settings, 'theme_name', 'default') or 'default')
        except Exception:
            pass
        # Give CustomTkinter's own default colours the theme's roles and set up
        # the app-wide restyler (recolours everything on screen when the theme
        # or light/dark mode changes).
        install_global_restyler(parent)
        # Register for theme change notifications
        theme.add_listener(self._on_theme_changed)
        # keep a reference for cleanup on destroy
        self._theme = theme
        # Apply base background to root and this frame so transparent children show themed bg
        try:
            parent.configure(fg_color=theme.get_current_color('bg_primary'))
        except Exception:
            pass
        try:
            self.configure(fg_color=theme.get_current_color('bg_primary'))
        except Exception:
            pass

        # State
        self._advanced_expanded = False
        self._current_tab_id: Optional[str] = None  # Current active tab_id
        self._current_tab_type = "home"  # Kind of page the active tab shows
        self._current_collection = None  # Current sub-collection being viewed (for collections tabs)
        # tab_id -> {type: page kind, view: the page's widget, current_collection: key or None}
        self._tab_views: Dict[str, Dict] = {}
        self._last_regular_tab_id: Optional[str] = None  # last active tab that was not Settings
        self._restoring_tabs = False  # True while reopening the saved tabs at startup
        self._tab_save_after = None  # pending debounced save of the open tabs
        self._selected_tags: List[str] = []
        self._tag_filter_mode: TagFilterMode = TagFilterMode.HAS_ALL
        self._selected_sources: List[str] = []
        self._source_filter_mode: SourceFilterMode = SourceFilterMode.INCLUDE
        self._compare_mode = False  # Whether compare panel is shown
        self._compare_spell: Optional[Spell] = None  # Spell in compare panel
        self._filter_debounce_id: Optional[str] = None  # For debouncing filter changes
        self._filter_debounce_delay = 200  # Milliseconds to wait before applying filters
        
        # Build UI. The spell browser and settings are set up front (the spell browser is
        # shared by every tab that opens Spells); every other page is built when a tab
        # navigates to it. The tab bar packs itself at the top since no view is packed yet.
        self._update_progress("Building spells view...", 0.65)
        self._create_spells_view()

        # Feats view is lazy-loaded for faster startup
        self._feats_view_created = False

        self._update_progress("Building settings...", 0.85)
        self._create_settings_view()

        self._update_progress("Finalizing UI...", 0.90)
        self._create_tab_bar()  # Also opens the first (Home) tab
        self._create_context_menu()

        # Bind spell manager updates
        self.spell_manager.add_listener(self._on_spells_changed)
        
        # Initial refresh
        self._update_progress("Loading spell list...", 0.95)
        self._refresh_spell_list()

        # Schedule background preloading after UI is visible
        self.after(800, self._background_preload)

        # Check GitHub for a newer release (silent, background, best-effort;
        # only opens a browser link - never downloads or installs anything).
        self.after(4000, self._maybe_check_for_updates)
    
    def _update_progress(self, message: str, value: float):
        """Update startup progress if callback is available."""
        if self._progress_callback:
            self._progress_callback(message, value)
            self.update_idletasks()

    def _on_data_save_error(self, message: str):
        """Warn the user when a character/character-sheet save fails.

        Previously these failures were only ever ``print()``-ed, which is
        invisible in the packaged (windowed, no console) build - the user had
        no way to know their edits hadn't reached disk. Only the first one
        pops a dialog per session; once it's shown we know the user is aware
        something is wrong, and repeated identical popups (e.g. from a
        permanently read-only data folder) would just be noise.
        """
        if getattr(self, "_shown_save_error", False):
            return
        self._shown_save_error = True
        try:
            messagebox.showerror(
                "Save Failed",
                f"{message}\n\nYour changes may not be saved. Check that the "
                "Spellbook data folder is writable and has free disk space."
            )
        except Exception:
            pass
    
    def _background_preload(self):
        """Preload collection views in the background, per the user's settings.

        Building all of them in one go froze the window for many seconds right
        after startup, so each view gets its own idle tick with a pause after
        it; the list inside each view also fills in gradually while it is not
        on screen (see ui/list_batching.py).
        """
        settings = self.settings_manager.settings
        steps = []
        if settings.preload_classes:
            steps.append(("classes", self._preload_classes))
        if settings.preload_feats:
            steps.append(("feats", self._ensure_feats_view_created))
        if settings.preload_lineages:
            steps.append(("lineages", lambda: self._preload_view("lineages_view", "ui.lineages_view", "LineagesView")))
        if settings.preload_backgrounds:
            steps.append(("backgrounds", lambda: self._preload_view("backgrounds_view", "ui.backgrounds_view", "BackgroundsView")))
        if getattr(settings, 'preload_equipment', True):
            steps.append(("equipment", lambda: self._preload_view("equipment_view", "ui.equipment_view", "EquipmentView")))
        if getattr(settings, 'preload_magic_items', True):
            steps.append(("magic items", lambda: self._preload_view("magic_items_view", "ui.magic_item_view", "MagicItemView")))
        if settings.preload_character_sheets:
            steps.append(("character sheets", self._preload_character_sheets))
        self._run_preload_steps(steps)

    def _run_preload_steps(self, steps):
        """Run the next preload step, then schedule the one after it."""
        if not steps or not self.winfo_exists():
            return
        name, step = steps.pop(0)
        try:
            step()
        except Exception as e:
            print(f"Background preload ({name}): {e}")
        self.after(PRELOAD_STEP_GAP_MS, lambda: self._run_preload_steps(steps))

    def _preload_classes(self):
        from character_class import ClassManager
        _ = ClassManager().classes  # Trigger cache population

    def _preload_view(self, attr: str, module: str, class_name: str):
        """Create a collection view (unpacked) unless it already exists."""
        if hasattr(self, attr):
            return
        import importlib
        view_class = getattr(importlib.import_module(module), class_name)
        setattr(self, attr, view_class(
            self,
            character_manager=self.character_manager,
            on_back=self._back_to_collections
        ))

    def _preload_character_sheets(self):
        from ui.character_sheet_view import get_sheet_manager
        sheet_manager = get_sheet_manager()
        for char in self.character_manager.characters:
            _ = sheet_manager.get_sheet(char.name)

    def _maybe_check_for_updates(self):
        """Silently check GitHub for a newer release on startup.

        Only runs for a packaged build (running from source you use git) and
        only when the user hasn't turned the auto-check off. Any failure -
        offline, GitHub down, rate limited - is swallowed; this must never
        interrupt startup.
        """
        try:
            from paths import is_frozen
            if not is_frozen():
                return
            if not getattr(self.settings_manager.settings, 'auto_check_updates', True):
                return
        except Exception:
            return

        def worker():
            try:
                from updater import check_for_update
                info = check_for_update()
            except Exception:
                return  # stay quiet on any failure
            if info is None:
                return
            try:
                self.after(0, lambda: self._show_update_dialog(info))
            except Exception:
                pass

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _show_update_dialog(self, info):
        """Show the update dialog unless the user has skipped this version."""
        try:
            skipped = getattr(self.settings_manager.settings, 'skipped_update_version', "")
            if skipped and skipped == info.version:
                return
            from ui.update_dialog import UpdateDialog
            UpdateDialog(
                self.winfo_toplevel(),
                info,
                on_skip=lambda v: self.settings_manager.update(skipped_update_version=v),
            )
        except Exception as e:
            print(f"Update dialog error: {e}")

    def commit_pending_edits(self):
        """Flush edits still sitting in focused widgets across all open tabs.

        Called on shutdown (from main.py) before the window is destroyed so an
        in-progress field edit isn't lost.
        """
        for view_info in list(self._tab_views.values()):
            view = view_info.get('view')
            commit = getattr(view, 'commit_pending_edits', None)
            if callable(commit):
                try:
                    commit()
                except Exception:
                    pass

    def destroy(self):
        """Clean up listeners to avoid leaks when the main window is destroyed."""
        self.commit_pending_edits()
        self._flush_tab_save()

        try:
            if self._session_pump_after is not None:
                self.after_cancel(self._session_pump_after)
            self.chat_overlay.shutdown()
            self.session.shutdown()
        except Exception:
            pass

        try:
            if hasattr(self, '_theme'):
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass

        try:
            self.spell_manager.remove_listener(self._on_spells_changed)
        except Exception:
            pass

        super().destroy()
    
    # LAN session. The connection, peer list and chat live in one SessionService owned by
    # this window (not by any page), so closing a tab never ends the game.

    def _init_session(self):
        from lan.service import SessionService
        from version import __version__
        self.session = SessionService(self.settings_manager, app_version=__version__)
        self.session.set_wake(self._ensure_session_pump)
        self.session.add_listener(self._on_session_event)
        self._session_pump_after = None
        self._session_bar = None
        from ui.chat_overlay import ChatOverlay
        self.chat_overlay = ChatOverlay(
            self, self.session, self.settings_manager,
            bottom_offset=lambda: (self._session_bar.winfo_height() if self._session_bar else 0) + 8)
        self._approval_dialogs: Dict[str, object] = {}

    def _ensure_session_pump(self):
        """Poll the network event queues (every 100 ms) while a session exists."""
        if self._session_pump_after is None:
            self._session_pump_after = self.after(100, self._session_tick)

    def _session_tick(self):
        self._session_pump_after = None
        try:
            self.session.pump()
        except Exception as e:
            print(f"Session error: {e}")
        if self.session.needs_pump:
            self._ensure_session_pump()

    def _on_session_event(self, kind: str, **data):
        if kind == 'state':
            self._update_session_bar()
        elif kind == 'approval_request':
            from ui.session_widgets import ApprovalDialog
            request_id = data['request_id']
            self._approval_dialogs[request_id] = ApprovalDialog(
                self.winfo_toplevel(), data['name'], data['address'],
                lambda accept, rid=request_id: self.session.resolve_approval(rid, accept))
        elif kind == 'approval_done':
            dialog = self._approval_dialogs.pop(data['request_id'], None)
            if dialog is not None:
                dialog.dismiss()
        elif kind == 'ended':
            for dialog in list(self._approval_dialogs.values()):
                dialog.dismiss()
            self._approval_dialogs.clear()

    def _update_session_bar(self):
        """Show the status bar under the tabs while a session is running."""
        if self.session.active and self._session_bar is None:
            from ui.session_widgets import SessionStatusBar
            self._session_bar = SessionStatusBar(self, self.session, on_open=self._open_session_page)
            self._session_bar.pack(side="bottom", fill="x", before=self.tab_bar)
        elif not self.session.active and self._session_bar is not None:
            self._session_bar.destroy()
            self._session_bar = None
        if self._session_bar is not None:
            self._session_bar.refresh()
        self._sync_chat_overlay()

    def _open_session_page(self):
        """Go to the Session page: an open tab that shows it, or a new one."""
        for tab_id, info in self._tab_views.items():
            if info['type'] == 'session' and info.get('view') is not None:
                self.tab_bar.select_tab(tab_id)
                return
        self._open_page_in_new_tab("session")

    # Tabs. Each tab shows one "page" at a time and navigates between pages like a browser
    # tab does: Home -> Collections / Characters -> (a collection | a character sheet).
    # Page kinds: home, collections, characters, character_sheet, game_tools, session, settings.

    def _create_tab_bar(self):
        """Create the tab bar and open the first tab (Home)."""
        self.tab_bar = DraggableTabBar(
            self,
            on_tab_selected=self._on_tab_selected,
            on_tab_closed=self._on_tab_closed,
            on_tabs_changed=self._on_tabs_changed,
            on_new_tab=self._on_new_tab_requested,
            on_duplicate_tab=self._duplicate_tab
        )
        self.tab_bar.pack(fill="x")

        # Settings tab: pinned on the right, uses the (lazy) self.settings_view
        settings_tab_id = self.tab_bar.add_tab(
            tab_type="settings",
            display_text="⚙ Settings",
            is_closable=False,
            is_settings=True,
            select=False
        )
        self._tab_views[settings_tab_id] = {
            'type': 'settings',
            'view': self.settings_view,
            'current_collection': None
        }

        # Reopen the tabs from last time (if wanted); otherwise the app opens on a Home tab
        self._restore_tabs()

    def _on_new_tab_requested(self, index: Optional[int] = None):
        """The tab bar's "+" (or its context menu) asked for a new tab: it opens on Home."""
        self._open_page_in_new_tab("home", index=index)

    def _page_title(self, page_type: str, character: Optional[str] = None) -> str:
        """Text for a tab showing the given page."""
        if page_type == "character_sheet":
            return f"{character}'s Sheet" if character else "Character Sheet"
        return {
            "home": "Home",
            "collections": "Collections",
            "characters": "Characters",
            "game_tools": "Game Tools",
            "session": "Session",
        }.get(page_type, "Spellbook")

    def _open_page_in_new_tab(self, page_type: str, index: Optional[int] = None,
                              select: bool = True, **kwargs) -> str:
        """Add a tab showing ``page_type`` and (by default) switch to it. Returns the new tab's id."""
        tab_id = self.tab_bar.add_tab(
            tab_type=page_type,
            display_text=self._page_title(page_type, kwargs.get('character')),
            is_closable=True,
            select=False,
            index=index
        )
        self._tab_views[tab_id] = {'type': None, 'view': None, 'current_collection': None}
        self._navigate_tab(tab_id, page_type, **kwargs)
        if select:
            self.tab_bar.select_tab(tab_id)
        self._schedule_tab_save()
        return tab_id

    # ---- remembering the open tabs between sessions

    def _restore_tabs(self):
        """Reopen the tabs saved by the last session, or a single Home tab."""
        saved, active = [], 0
        if getattr(self.settings_manager.settings, 'restore_tabs', True):
            saved, active = tab_session.load_tabs()

        opened = {}  # index in the saved list -> tab id
        self._restoring_tabs = True
        try:
            for i, entry in enumerate(saved):
                try:
                    tab_id = self._restore_tab(entry)
                except Exception as e:
                    print(f"Could not restore a tab: {e}")
                    tab_id = None
                if tab_id:
                    opened[i] = tab_id
        finally:
            self._restoring_tabs = False

        if not opened:
            self._open_page_in_new_tab("home")
        else:
            self.tab_bar.select_tab(opened.get(active) or next(iter(opened.values())))
        self._schedule_tab_save()

    def _restore_tab(self, entry: dict) -> Optional[str]:
        """Open one saved tab (not selected). Returns its id, or None if it cannot be reopened."""
        page = entry.get('page')
        character = entry.get('character')
        if page not in ("home", "collections", "characters", "character_sheet", "game_tools", "session"):
            return None
        if page == "character_sheet" and (
                not character or self.character_manager.get_character(character) is None):
            page, character = "characters", None  # that character is gone: show the list instead

        tab_id = self._open_page_in_new_tab(page, select=False, character=character)
        collection = entry.get('collection')
        if page == "collections" and collection in COLLECTION_KEYS:
            # Just remember which collection it was on; it is built when the tab is first shown
            self._tab_views[tab_id]['current_collection'] = collection
            self._update_tab_name_for_collection(tab_id, collection)
        return tab_id

    def _capture_tabs(self):
        """The open tabs, in order, as saved entries, plus the active tab's index."""
        tabs, active = [], 0
        shown_id = self._current_tab_id
        if shown_id not in self._tab_views or self._tab_views[shown_id]['type'] == 'settings':
            shown_id = self._last_regular_tab_id  # Settings is not saved: reopen on the last page
        for tab_id in self.tab_bar.get_tab_ids():
            info = self._tab_views.get(tab_id)
            if not info or not info.get('type'):
                continue
            character = None
            if info['type'] == 'character_sheet':
                view = info.get('view')
                shown = view.current_character if view is not None else None
                character = shown.name if shown else info.get('pending_character')
            if tab_id == shown_id:
                active = len(tabs)
            tabs.append({'page': info['type'], 'collection': info.get('current_collection'),
                         'character': character})
        return tabs, active

    def _schedule_tab_save(self):
        """Save the open tabs shortly after the last change (changes come in bursts)."""
        if self._restoring_tabs:
            return
        try:
            if self._tab_save_after is not None:
                self.after_cancel(self._tab_save_after)
            self._tab_save_after = self.after(400, self._flush_tab_save)
        except Exception:
            self._tab_save_after = None

    def _flush_tab_save(self):
        """Save the open tabs now (or forget them if the feature is turned off)."""
        if self._tab_save_after is not None:
            try:
                self.after_cancel(self._tab_save_after)
            except Exception:
                pass
            self._tab_save_after = None
        if self._restoring_tabs or not hasattr(self, 'tab_bar'):
            return
        if not getattr(self.settings_manager.settings, 'restore_tabs', True):
            tab_session.clear_tabs()
            return
        tabs, active = self._capture_tabs()
        if tabs:
            tab_session.save_tabs(tabs, active)

    def _duplicate_tab(self, tab_id: str):
        """Open a copy of a tab (same page) right after it."""
        info = self._tab_views.get(tab_id)
        if not info or info['type'] == 'settings':
            return
        index = self.tab_bar.get_tab_index(tab_id) + 1
        page_type = info['type']
        if page_type == 'character_sheet':
            view = info['view']
            character = view.current_character.name if view.current_character else None
            self._open_page_in_new_tab(page_type, index=index, character=character)
        elif page_type == 'collections' and info.get('current_collection'):
            new_id = self._open_page_in_new_tab(page_type, index=index)
            self._navigate_to_collection_in_tab(new_id, info['current_collection'])
        else:
            self._open_page_in_new_tab(page_type, index=index)

    def _build_page(self, tab_id: str, page_type: str, character: Optional[str] = None):
        """Create the widget for a page (not packed yet)."""
        if page_type == "home":
            from ui.home_view import HomeView
            return HomeView(self, on_open=lambda key, tid=tab_id: self._open_from_home(tid, key))
        if page_type == "collections":
            from ui.collections_view import CollectionsView
            return CollectionsView(
                self,
                spell_manager=self.spell_manager,
                on_navigate=lambda key, name=None, tid=tab_id: self._navigate_to_collection_in_tab(tid, key, name),
                on_home=lambda tid=tab_id: self._navigate_tab(tid, "home")
            )
        if page_type == "characters":
            from ui.characters_view import CharactersView
            return CharactersView(
                self, self.character_manager,
                spell_manager=self.spell_manager,
                on_open=lambda name, new_tab=False, tid=tab_id: self._open_character(tid, name, new_tab),
                on_home=lambda tid=tab_id: self._navigate_tab(tid, "home")
            )
        if page_type == "character_sheet":
            from ui.character_sheet_view import CharacterSheetView
            return CharacterSheetView(
                self, self.character_manager,
                spell_manager=self.spell_manager,
                on_navigate_to_spell=self._navigate_to_spell,
                on_character_changed=lambda name, tid=tab_id: self._on_character_changed_in_tab(tid, name),
                on_back=lambda tid=tab_id: self._navigate_tab(tid, "characters")
            )
        if page_type == "game_tools":
            from ui.game_tools_view import GameToolsView
            return GameToolsView(
                self, service=self.session,
                on_open=lambda key, tid=tab_id: self._open_game_tool(tid, key),
                on_home=lambda tid=tab_id: self._navigate_tab(tid, "home")
            )
        if page_type == "session":
            from ui.session_view import SessionView
            return SessionView(self, self.session, on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"),
                               overlay=self.chat_overlay)
        raise ValueError(f"Unknown page type: {page_type}")

    def _navigate_tab(self, tab_id: str, page_type: str, **kwargs):
        """Make a tab show a different page (like following a link in a browser tab)."""
        info = self._tab_views.get(tab_id)
        if info is None:
            return
        self._discard_page(tab_id)

        info['type'] = page_type
        info['current_collection'] = None
        info['view'] = self._build_page(tab_id, page_type, character=kwargs.get('character'))
        info['fresh'] = True  # just built: nothing to catch up on when it is first shown
        if page_type == 'character_sheet':
            info['pending_character'] = kwargs.get('character')  # selected once it is on screen
        self.tab_bar.update_tab_text(tab_id, self._page_title(page_type, kwargs.get('character')))

        if tab_id == self._current_tab_id:
            self._show_tab_content(tab_id)
        self._schedule_tab_save()

    def _discard_page(self, tab_id: str):
        """Tear down the page a tab is showing (before it shows another, or closes)."""
        info = self._tab_views.get(tab_id)
        if info is None or info.get('view') is None:
            return
        view = info['view']

        # The collection sub-views are shared by all tabs: only take one off screen when
        # it is this tab that is showing it
        if tab_id == self._current_tab_id and info.get('current_collection'):
            self._hide_collection_sub_view(info['current_collection'])

        if info['type'] == 'character_sheet':
            self._detach_orphaned_sheet(view)
        elif info['type'] == 'collections' and hasattr(view, 'search_bar'):
            view.search_bar.cleanup()

        try:
            view.pack_forget()
            view.destroy()  # a sheet saves its pending edits on the way out
        except Exception:
            pass
        info['view'] = None
        info.pop('pending_character', None)

    def _detach_orphaned_sheet(self, view):
        """If a sheet's character was deleted (e.g. from another tab), stop the sheet
        from saving itself back into existence when it is closed."""
        character = getattr(view, 'current_character', None)
        if character is not None and self.character_manager.get_character(character.name) is None:
            view.current_character = None
            view.current_sheet = None

    def _open_from_home(self, tab_id: str, key: str):
        """A card on a Home page was clicked."""
        if key in ("collections", "characters", "game_tools"):
            self._navigate_tab(tab_id, key)

    def _open_game_tool(self, tab_id: str, key: str):
        """A card on the Game Tools page was clicked."""
        if key == "session":
            self._navigate_tab(tab_id, "session")

    def _open_character(self, tab_id: str, name: str, new_tab: bool = False):
        """Open a character's sheet in this tab (or a new one)."""
        if new_tab:
            index = self.tab_bar.get_tab_index(tab_id) + 1
            self._open_page_in_new_tab("character_sheet", index=index, character=name)
            return
        # Already open in another tab? Go there instead of opening a second copy
        for other_id, info in self._tab_views.items():
            if other_id == tab_id or info['type'] != 'character_sheet' or info.get('view') is None:
                continue
            shown = info['view'].current_character
            pending = info.get('pending_character')
            if (shown and shown.name == name) or (pending == name):
                self.tab_bar.select_tab(other_id)
                return
        self._navigate_tab(tab_id, "character_sheet", character=name)

    def _on_character_changed_in_tab(self, tab_id: str, character_name: str):
        """Handle character selection in a character sheet tab."""
        self.tab_bar.update_tab_text(tab_id, self._page_title("character_sheet", character_name or None))
        self._schedule_tab_save()

    def _on_tab_closed(self, tab_id: str):
        """Handle tab closure - destroy its page."""
        if tab_id in self._tab_views:
            self._discard_page(tab_id)
            del self._tab_views[tab_id]
        if tab_id == self._current_tab_id:
            self._current_tab_id = None
        if tab_id == self._last_regular_tab_id:
            self._last_regular_tab_id = None
        self._schedule_tab_save()

    def _on_tab_selected(self, tab_id: str, tab_type: str):
        """Handle tab selection from the tab bar."""
        self._show_tab_by_id(tab_id)

    def _on_tabs_changed(self):
        """Handle tabs being added, removed, or reordered."""
        self._schedule_tab_save()  # tabs were closed or reordered

    def _show_tab_by_id(self, tab_id: str):
        """Switch to the specified tab by its ID."""
        if tab_id not in self._tab_views:
            return

        # Skip if already on this tab
        if tab_id == self._current_tab_id:
            return

        # Take the previously visible tab off screen (its page stays alive)
        if self._current_tab_id and self._current_tab_id in self._tab_views:
            self._hide_tab_content(self._current_tab_id)

        info = self._tab_views[tab_id]
        fresh = info.get('fresh')  # page was just built: nothing to catch up on
        self._current_tab_id = tab_id
        if info['type'] != 'settings':
            self._last_regular_tab_id = tab_id
        self._show_tab_content(tab_id)
        self._schedule_tab_save()
        if fresh:
            return

        # Pages that show shared data catch up with changes made in other tabs
        if info['type'] == 'characters':
            info['view'].refresh()
        elif info['type'] == 'character_sheet':
            view = info['view']
            if view is not None and view.current_character is not None \
                    and self.character_manager.get_character(view.current_character.name) is None:
                # Its character was deleted while this tab was in the background
                self._navigate_tab(tab_id, "characters")

    def _hide_tab_content(self, tab_id: str):
        """Take a tab's page off screen without destroying it."""
        info = self._tab_views[tab_id]
        view = info.get('view')
        if view is None:
            return
        try:
            view.pack_forget()
        except Exception:
            pass
        # Hide any collection sub-view that was visible for this tab
        if info.get('current_collection'):
            self._hide_collection_sub_view(info['current_collection'])
        # Clean up search bar if switching away from a collections hub
        if info['type'] == 'collections' and hasattr(view, 'search_bar'):
            view.search_bar.cleanup()

    def _show_tab_content(self, tab_id: str):
        """Put a tab's page on screen."""
        self._put_page_on_screen(tab_id)
        self._sync_chat_overlay()

    def _sync_chat_overlay(self):
        """The chat overlay hides itself on the Session page (which shows the chat anyway) and
        is lifted above whatever page was just shown."""
        info = self._tab_views.get(self._current_tab_id) or {}
        self.chat_overlay.suppressed = info.get('type') == 'session'
        self.chat_overlay.refresh()

    def _put_page_on_screen(self, tab_id: str):
        info = self._tab_views[tab_id]
        view = info.get('view')
        self._current_tab_type = info['type']
        self._current_collection = info.get('current_collection')
        info.pop('fresh', None)
        if view is None:
            return

        if info['type'] == 'collections' and info.get('current_collection'):
            self._show_collection_sub_view(info['current_collection'])
            return

        view.pack(fill="both", expand=True)
        if info['type'] == 'settings':
            view.refresh_from_settings()
        elif info['type'] == 'character_sheet':
            pending = info.pop('pending_character', None)
            if pending:
                view.select_character(pending)

    def _hide_collection_sub_view(self, collection_key: str):
        """Hide a collection sub-view."""
        if collection_key == "spells" and hasattr(self, 'spells_view'):
            self.spells_view.pack_forget()
        elif collection_key == "classes" and hasattr(self, 'classes_view'):
            self.classes_view.pack_forget()
        elif collection_key == "feats" and hasattr(self, 'feats_view'):
            self.feats_view.pack_forget()
        elif collection_key == "lineages" and hasattr(self, 'lineages_view'):
            self.lineages_view.pack_forget()
        elif collection_key == "backgrounds" and hasattr(self, 'backgrounds_view'):
            self.backgrounds_view.pack_forget()
        elif collection_key == "equipment" and hasattr(self, 'equipment_view'):
            self.equipment_view.pack_forget()
        elif collection_key == "magic_items" and hasattr(self, 'magic_items_view'):
            self.magic_items_view.pack_forget()
        elif collection_key == "monsters" and hasattr(self, 'monsters_view'):
            self.monsters_view.pack_forget()

    def _navigate_to_collection_in_tab(self, tab_id: str, collection_key: str, item_name: Optional[str] = None):
        """Navigate to a collection within a specific tab."""
        if tab_id not in self._tab_views:
            return
        
        view_info = self._tab_views[tab_id]
        view_info['current_collection'] = collection_key
        
        # Clean up search bar before navigating
        if hasattr(view_info['view'], 'search_bar'):
            view_info['view'].search_bar.cleanup()
        
        # Hide the collections hub view
        view_info['view'].pack_forget()
        
        # Update tab name to reflect content
        self._update_tab_name_for_collection(tab_id, collection_key, item_name)
        
        # Show the appropriate sub-view
        self._show_collection_sub_view(collection_key, item_name)
        self._schedule_tab_save()
    
    def _update_tab_name_for_collection(self, tab_id: str, collection_key: str, item_name: Optional[str] = None):
        """Update the tab name based on the collection being viewed."""
        name_map = {
            'spells': 'Spells',
            'feats': 'Feats',
            'lineages': 'Lineages',
            'backgrounds': 'Backgrounds',
            'classes': 'Classes',
            'equipment': 'Equipment',
            'magic_items': 'Magic Items',
            'monsters': 'Monsters'
        }
        
        if item_name and collection_key == 'classes':
            # For specific class, use the class name
            tab_name = item_name
        else:
            tab_name = name_map.get(collection_key, 'Collections')
        
        self.tab_bar.update_tab_text(tab_id, tab_name)
    
    def _show_collection_sub_view(self, collection_key: str, item_name: Optional[str] = None):
        """Show a collection sub-view (spells, classes, etc.)."""
        if collection_key == "spells":
            self.spells_view.pack(fill="both", expand=True)
            if item_name:
                self.after(100, lambda: self.spell_list.select_spell(item_name))
        elif collection_key == "classes":
            self._show_classes_view_internal()
            if item_name:
                # Longer delay for classes/subclasses - view needs time to fully render
                self.after(300, lambda: self._select_class_item(item_name))
        elif collection_key == "feats":
            self._ensure_feats_view_created()
            self.feats_view.pack(fill="both", expand=True)
            if item_name:
                self.after(150, lambda: self._select_feat_item(item_name))
        elif collection_key == "lineages":
            self._show_lineages_view_internal()
            if item_name:
                self.after(150, lambda: self._select_lineage_item(item_name))
        elif collection_key == "backgrounds":
            self._show_backgrounds_view_internal()
            if item_name:
                self.after(150, lambda: self._select_background_item(item_name))
        elif collection_key == "equipment":
            self._show_equipment_view_internal()
            if item_name:
                self.after(150, lambda: self._select_equipment_item(item_name))
        elif collection_key == "magic_items":
            self._show_magic_items_view_internal()
            if item_name:
                self.after(150, lambda: self._select_magic_item_item(item_name))
        elif collection_key == "monsters":
            self._show_monsters_view_internal()
            if item_name:
                self.after(150, lambda: self._select_monster_item(item_name))

    def _ensure_feats_view_created(self):
        """Create feats view if not already created (lazy loading)."""
        if not self._feats_view_created:
            self._create_feats_view()
            self._feats_view_created = True
    
    def _navigate_to_spell(self, spell_name: str):
        """Open a spell in a new Spells tab (so the sheet it was clicked from stays put)."""
        # Clear filters to ensure spell is visible
        self.search_var.set("")
        self.level_var.set("All")
        self.class_var.set("All")
        self._clear_advanced_filters()
        self._refresh_spell_list()

        index = self.tab_bar.get_tab_index(self._current_tab_id) + 1 if self._current_tab_id else None
        tab_id = self._open_page_in_new_tab("collections", index=index)
        self._navigate_to_collection_in_tab(tab_id, "spells")
        self.spell_list.select_spell(spell_name)

    def _select_class_item(self, name: str):
        """Select a class or subclass in the classes view."""
        if hasattr(self, 'classes_view') and hasattr(self.classes_view, 'select_class'):
            self.classes_view.select_class(name)
    
    def _select_feat_item(self, name: str):
        """Select a feat in the feats view."""
        if hasattr(self, 'feats_view') and hasattr(self.feats_view, 'select_feat'):
            self.feats_view.select_feat(name)
    
    def _select_lineage_item(self, name: str):
        """Select a lineage in the lineages view."""
        if hasattr(self, 'lineages_view') and hasattr(self.lineages_view, 'select_lineage'):
            self.lineages_view.select_lineage(name)
    
    def _select_background_item(self, name: str):
        """Select a background in the backgrounds view."""
        if hasattr(self, 'backgrounds_view') and hasattr(self.backgrounds_view, 'select_background'):
            self.backgrounds_view.select_background(name)

    def _select_equipment_item(self, name: str):
        """Select an item in the equipment view."""
        if hasattr(self, 'equipment_view') and hasattr(self.equipment_view, 'select_item'):
            self.equipment_view.select_item(name)

    def _select_magic_item_item(self, name: str):
        """Select an item in the magic items view."""
        if hasattr(self, 'magic_items_view') and hasattr(self.magic_items_view, 'select_item'):
            self.magic_items_view.select_item(name)

    def _select_monster_item(self, name: str):
        """Select a monster in the monsters view."""
        if hasattr(self, 'monsters_view') and hasattr(self.monsters_view, 'select_monster'):
            self.monsters_view.select_monster(name)

    def _show_classes_view_internal(self):
        """Internal method to show classes view without modifying tab state."""
        from ui.classes_view import ClassesCollectionView
        
        # Create classes view if needed
        if not hasattr(self, 'classes_view'):
            self.classes_view = ClassesCollectionView(
                self,
                on_back=self._back_to_collections
            )
        
        self.classes_view.pack(fill="both", expand=True)
    
    def _show_lineages_view_internal(self):
        """Internal method to show lineages view without modifying tab state."""
        from ui.lineages_view import LineagesView
        
        # Create lineages view if needed
        if not hasattr(self, 'lineages_view'):
            self.lineages_view = LineagesView(
                self,
                character_manager=self.character_manager,
                on_back=self._back_to_collections
            )
        
        self.lineages_view.pack(fill="both", expand=True)
    
    def _show_backgrounds_view_internal(self):
        """Internal method to show backgrounds view without modifying tab state."""
        from ui.backgrounds_view import BackgroundsView
        
        # Create backgrounds view if needed
        if not hasattr(self, 'backgrounds_view'):
            self.backgrounds_view = BackgroundsView(
                self,
                character_manager=self.character_manager,
                on_back=self._back_to_collections
            )
        
        self.backgrounds_view.pack(fill="both", expand=True)

    def _show_equipment_view_internal(self):
        """Internal method to show the equipment view without modifying tab state."""
        from ui.equipment_view import EquipmentView

        if not hasattr(self, 'equipment_view'):
            self.equipment_view = EquipmentView(
                self,
                character_manager=self.character_manager,
                on_back=self._back_to_collections
            )

        self.equipment_view.pack(fill="both", expand=True)

    def _show_magic_items_view_internal(self):
        """Internal method to show the magic items view without modifying tab state."""
        from ui.magic_item_view import MagicItemView

        if not hasattr(self, 'magic_items_view'):
            self.magic_items_view = MagicItemView(
                self,
                character_manager=self.character_manager,
                on_back=self._back_to_collections
            )

        self.magic_items_view.pack(fill="both", expand=True)

    def _show_monsters_view_internal(self):
        """Internal method to show the monsters view without modifying tab state."""
        from ui.monster_view import MonsterView

        if not hasattr(self, 'monsters_view'):
            self.monsters_view = MonsterView(
                self,
                character_manager=self.character_manager,
                on_back=self._back_to_collections
            )

        self.monsters_view.pack(fill="both", expand=True)

    def _back_to_collections(self):
        """Go back to the main collections view within the current tab."""
        # Get the current tab
        if not self._current_tab_id or self._current_tab_id not in self._tab_views:
            return
        
        view_info = self._tab_views[self._current_tab_id]
        
        # Only process collections tabs
        if view_info['type'] != 'collections':
            return
        
        # Hide any current sub-views
        current_col = view_info.get('current_collection')
        if current_col:
            self._hide_collection_sub_view(current_col)
        
        # Reset the current collection state
        view_info['current_collection'] = None
        self._current_collection = None
        
        # Reset tab name to "Collections"
        self.tab_bar.update_tab_text(self._current_tab_id, "Collections")
        self._schedule_tab_save()
        
        # Show the collections hub view for this tab
        view_info['view'].pack(fill="both", expand=True)
    
    def _create_spells_view(self):
        """Create the spells view (main spell browser)."""
        self.spells_view = ctk.CTkFrame(self, fg_color="transparent")
        
        self._create_toolbar()
        self._create_advanced_filters()
        self._create_main_content()
    
    def _create_settings_view(self):
        """Set up the settings view. It is large, so it is only built when the
        Settings tab is first opened (see ui/lazy_view.py)."""
        def build():
            from ui.settings_view import SettingsView
            return SettingsView(
                self, self.settings_manager,
                on_appearance_changed=self._on_appearance_changed,
                spell_manager=self.spell_manager
            )
        self.settings_view = LazyView(build)
    
    def _create_feats_view(self):
        """Create the feats view."""
        from ui.feats_view import FeatsView
        self.feats_view = FeatsView(
            self, 
            character_manager=self.character_manager,
            on_back=self._back_to_collections
        )
    
    def _on_appearance_changed(self, mode: str):
        """Handle appearance mode change from settings."""
        # Update theme-dependent widgets that use tk (not ctk)
        self._update_context_menu_colors()
        self._update_paned_colors()
        
        # Light/dark switched: re-resolve every role-tagged colour on screen
        restyle_app()

        # Update spell detail description colors
        if hasattr(self, 'spell_detail'):
            self.spell_detail._update_description_colors()
        if hasattr(self, 'compare_detail'):
            self.compare_detail._update_description_colors()

    def _on_theme_changed(self):
        """Handle ThemeManager changes (colors updated or custom theme saved)."""
        theme = get_theme_manager()
        # Recolour every widget on screen from its theme role (also picks up
        # widgets that never passed an explicit colour)
        restyle_app()

        # Update widgets that rely on TK colors or CTkFrame backgrounds
        self._update_context_menu_colors()
        self._update_paned_colors()

        # Update root and main frame backgrounds so transparent widgets reflect the theme
        try:
            self.configure(fg_color=theme.get_current_color('bg_primary'))
        except Exception:
            pass

        # Reconfigure tab bar colors
        try:
            if hasattr(self, 'tab_bar'):
                self.tab_bar.update_colors()
        except Exception:
            pass

        try:
            self.advanced_btn.configure(fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'))
        except Exception:
            pass

        # These "card" panels are created with an explicit fg_color (not
        # "transparent"), so they need to be repainted explicitly too.
        card_bg = theme.get_current_color('bg_secondary')
        for attr in ('advanced_frame', 'compare_container'):
            try:
                getattr(self, attr).configure(fg_color=card_bg)
            except Exception:
                pass

        # Update input widgets (entries / combos) to pick up input/background colors
        try:
            input_bg = theme.get_current_color('bg_input')
            input_text = theme.get_current_color('text_primary')
            border_col = theme.get_current_color('border')

            if hasattr(self, 'search_entry'):
                try:
                    self.search_entry.configure(fg_color=input_bg, text_color=input_text, border_color=border_col)
                except Exception:
                    pass
            if hasattr(self, 'min_range_combo'):
                try:
                    self.min_range_combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                except Exception:
                    pass
            if hasattr(self, 'level_combo'):
                try:
                    self.level_combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                except Exception:
                    pass
            if hasattr(self, 'class_combo'):
                try:
                    self.class_combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                except Exception:
                    pass
            # Advanced filter combos
            for combo_name in ('ritual_combo','conc_combo','verbal_combo','somatic_combo','material_combo','costly_combo',
                               'cast_time_combo','duration_combo','source_combo'):
                if hasattr(self, combo_name):
                    try:
                        combo = getattr(self, combo_name)
                        combo.configure(fg_color=input_bg, text_color=input_text, button_color=input_bg)
                    except Exception:
                        pass
        except Exception:
            pass

        # Notify subviews
        try:
            if hasattr(self, 'spell_detail'):
                # SpellDetailPanel provides its own description color updater
                self.spell_detail._update_description_colors()
        except Exception:
            pass
        
        # Update the search bar on every open collections hub
        try:
            for view_info in self._tab_views.values():
                view = view_info.get('view')
                if view_info['type'] == 'collections' and hasattr(view, 'search_bar'):
                    view.search_bar.update_colors()
        except Exception:
            pass
    
    def _update_context_menu_colors(self):
        """Update context menu colors based on current theme."""
        # Guard: context_menu may not be created yet when listener is registered
        if not hasattr(self, 'context_menu'):
            return
        theme = get_theme_manager()
        bg, fg, active_bg, active_fg = theme.get_menu_colors()
        self.context_menu.configure(
            bg=bg, fg=fg,
            activebackground=active_bg, activeforeground=active_fg,
            relief="flat", borderwidth=1
        )
    
    def _update_paned_colors(self):
        """Update PanedWindow sash colors based on current theme."""
        theme = get_theme_manager()
        self.main_paned.configure(bg=theme.get_current_color('pane_sash'))
    
    def _create_toolbar(self):
        """Create the toolbar with search, filters, and action buttons."""
        toolbar = ctk.CTkFrame(self.spells_view, fg_color="transparent")
        toolbar.pack(fill="x", padx=15, pady=(15, 10))

        # Left side - Back button, Search and filters
        left_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_frame.pack(side="left", fill="x", expand=True)
        
        # Back to Collections button
        theme = get_theme_manager()
        ctk.CTkButton(
            left_frame, text="← Collections", width=110,
            fg_color=theme.get_current_color('button_normal'), 
            hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._back_to_collections
        ).pack(side="left", padx=(0, 15))

        # Search entry
        search_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        search_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(search_frame, text="Search:", font=ui_font("body", 13)).pack(
            side="left", padx=(0, 8))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_filter_changed())
        self.search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var,
                                         width=160, placeholder_text="Search spells...")
        self.search_entry.pack(side="left")

        # Level filter
        level_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        level_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(level_frame, text="Level:", font=ui_font("body", 13)).pack(
            side="left", padx=(0, 8))
        self.level_var = ctk.StringVar(value="All")
        level_options = ["All", "Cantrip"] + [str(i) for i in range(1, 10)]
        self.level_combo = ctk.CTkComboBox(level_frame, variable=self.level_var,
                                           values=level_options, width=90,
                                           command=lambda x: self._on_filter_changed(immediate=True))
        self.level_combo.pack(side="left")

        # Class filter
        class_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        class_frame.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(class_frame, text="Class:", font=ui_font("body", 13)).pack(
            side="left", padx=(0, 8))
        self.class_var = ctk.StringVar(value="All")
        class_options = ["All"] + CharacterClass.spellcasting_class_names()
        self.class_combo = ctk.CTkComboBox(class_frame, variable=self.class_var,
                                           values=class_options, width=110,
                                           command=lambda x: self._on_filter_changed(immediate=True))
        self.class_combo.pack(side="left")

        # Advanced filters toggle button
        self.advanced_btn = ctk.CTkButton(
            left_frame, text="▼ Filters", width=90,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            text_color=theme.get_current_color('text_primary'),
            command=self._toggle_advanced_filters
        )
        self.advanced_btn.pack(side="left")

        # Right side - New Spell button only
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(btn_frame, text="+ New Spell", width=100,
                      text_color=theme.get_current_color('text_primary'),
                      command=self._on_new_spell).pack(side="left")
    
    def _create_advanced_filters(self):
        """Create the collapsible advanced filters panel."""
        # Container frame (hidden by default)
        theme = get_theme_manager()
        self.advanced_frame = ctk.CTkFrame(self.spells_view, corner_radius=10,
                                            fg_color=theme.get_current_color('bg_secondary'))
        # Don't pack yet - will be shown/hidden by toggle
        
        # Inner content with padding
        content = ctk.CTkFrame(self.advanced_frame, fg_color="transparent")
        content.pack(fill="x", padx=15, pady=15)
        
        # Row 1: Ritual, Concentration, Min Range
        row1 = ctk.CTkFrame(content, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 12))
        
        # Ritual filter
        ritual_frame = ctk.CTkFrame(row1, fg_color="transparent")
        ritual_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(ritual_frame, text="Ritual:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.ritual_var = ctk.StringVar(value="Any")
        self.ritual_combo = ctk.CTkComboBox(ritual_frame, variable=self.ritual_var,
                                            values=["Any", "Ritual Only", "Non-Ritual"],
                                            width=110, command=lambda x: self._on_filter_changed(immediate=True))
        self.ritual_combo.pack(side="left")
        
        # Concentration filter
        conc_frame = ctk.CTkFrame(row1, fg_color="transparent")
        conc_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(conc_frame, text="Concentration:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.conc_var = ctk.StringVar(value="Any")
        self.conc_combo = ctk.CTkComboBox(conc_frame, variable=self.conc_var,
                                          values=["Any", "Concentration", "Non-Concentration"],
                                          width=140, command=lambda x: self._on_filter_changed(immediate=True))
        self.conc_combo.pack(side="left")
        
        # Minimum Range
        range_frame = ctk.CTkFrame(row1, fg_color="transparent")
        range_frame.pack(side="left", padx=(0, 30))
        ctk.CTkLabel(range_frame, text="Min Range:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.min_range_var = ctk.StringVar(value="Self")
        self._range_display_to_value = {"Self": 0}  # Will be populated by _update_filter_dropdowns
        self.min_range_combo = ctk.CTkComboBox(range_frame, variable=self.min_range_var,
                                               values=["Self"],
                                               width=100, command=lambda x: self._on_filter_changed(immediate=True))
        self.min_range_combo.pack(side="left")
        
        # Get text_secondary color for later use
        text_secondary = theme.get_text_secondary()
        
        # Row 2: Component filters
        row2 = ctk.CTkFrame(content, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(row2, text="Components:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 15))
        
        # Verbal filter
        self.verbal_var = ctk.StringVar(value="Any")
        self.verbal_combo = ctk.CTkComboBox(row2, variable=self.verbal_var,
                                            values=["Any", "Has V", "No V"],
                                            width=80, command=lambda x: self._on_filter_changed(immediate=True))
        self.verbal_combo.pack(side="left", padx=(0, 10))
        
        # Somatic filter
        self.somatic_var = ctk.StringVar(value="Any")
        self.somatic_combo = ctk.CTkComboBox(row2, variable=self.somatic_var,
                                             values=["Any", "Has S", "No S"],
                                             width=80, command=lambda x: self._on_filter_changed(immediate=True))
        self.somatic_combo.pack(side="left", padx=(0, 10))
        
        # Material filter
        self.material_var = ctk.StringVar(value="Any")
        self.material_combo = ctk.CTkComboBox(row2, variable=self.material_var,
                                              values=["Any", "Has M", "No M"],
                                              width=80, command=lambda x: self._on_filter_changed(immediate=True))
        self.material_combo.pack(side="left", padx=(0, 20))
        
        # Costly component filter
        self.costly_var = ctk.StringVar(value="Any")
        ctk.CTkLabel(row2, text="GP Cost:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.costly_combo = ctk.CTkComboBox(row2, variable=self.costly_var,
                                            values=["Any", "Has GP Cost", "No GP Cost"],
                                            width=120, command=lambda x: self._on_filter_changed(immediate=True))
        self.costly_combo.pack(side="left")
        
        # Row 3: Casting Time, Duration, Source
        row3 = ctk.CTkFrame(content, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 12))
        
        # Casting Time filter
        cast_frame = ctk.CTkFrame(row3, fg_color="transparent")
        cast_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(cast_frame, text="Casting Time:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.cast_time_var = ctk.StringVar(value="Any")
        self.cast_time_combo = ctk.CTkComboBox(cast_frame, variable=self.cast_time_var,
                                                values=["Any"], width=120,
                                                command=lambda x: self._on_filter_changed(immediate=True))
        self.cast_time_combo.pack(side="left")
        
        # Duration filter
        dur_frame = ctk.CTkFrame(row3, fg_color="transparent")
        dur_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(dur_frame, text="Duration:", font=ui_font("body")).pack(side="left", padx=(0, 8))
        self.duration_var = ctk.StringVar(value="Any")
        self.duration_combo = ctk.CTkComboBox(dur_frame, variable=self.duration_var,
                                               values=["Any"], width=130,
                                               command=lambda x: self._on_filter_changed(immediate=True))
        self.duration_combo.pack(side="left")
        
        # Source filter (button opens multi-select dialog)
        source_frame = ctk.CTkFrame(row3, fg_color="transparent")
        source_frame.pack(side="left", padx=(0, 25))
        ctk.CTkLabel(source_frame, text="Source:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 8))
        
        self.source_btn = ctk.CTkButton(
            source_frame, text="Select Sources...", width=130,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            command=self._open_source_filter
        )
        self.source_btn.pack(side="left", padx=(0, 10))
        
        self.source_label = ctk.CTkLabel(
            source_frame, text="None selected",
            font=ui_font("small"),
            text_color=text_secondary
        )
        self.source_label.pack(side="left")
        
        # Row 4: Tags filter and Clear button
        row4 = ctk.CTkFrame(content, fg_color="transparent")
        row4.pack(fill="x")
        
        # Tags filter
        tags_frame = ctk.CTkFrame(row4, fg_color="transparent")
        tags_frame.pack(side="left")
        ctk.CTkLabel(tags_frame, text="Tags:", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 8))
        
        self.tags_btn = ctk.CTkButton(
            tags_frame, text="Select Tags...", width=120,
            fg_color=theme.get_current_color('button_normal'), hover_color=theme.get_current_color('button_hover'),
            command=self._open_tag_filter
        )
        self.tags_btn.pack(side="left", padx=(0, 10))
        
        self.tags_label = ctk.CTkLabel(
            tags_frame, text="None selected",
            font=ui_font("small"),
            text_color=text_secondary
        )
        self.tags_label.pack(side="left")
        
        # Clear filters button (use themed danger color)
        theme = get_theme_manager()
        danger = theme.get_current_color('button_danger')
        danger_hover = theme.get_current_color('button_danger_hover')
        btn_text = theme.get_current_color('text_primary')
        ctk.CTkButton(row4, text="Clear All Filters", width=120,
                      fg_color=danger, hover_color=danger_hover,
                      text_color=btn_text,
                      command=self._clear_advanced_filters).pack(side="right")

        # Update dropdown values
        self._update_filter_dropdowns()
    
    def _open_tag_filter(self):
        """Open the tag filter dialog."""
        available_tags = self.spell_manager.get_all_tags()
        dialog = TagFilterDialog(
            self.winfo_toplevel(),
            available_tags,
            self._selected_tags,
            self._tag_filter_mode
        )
        self.wait_window(dialog)
        
        self._selected_tags = dialog.result
        self._tag_filter_mode = dialog.result_mode
        self._update_tags_label()
        self._on_filter_changed(immediate=True)
    
    def _open_source_filter(self):
        """Open the source filter dialog."""
        available_sources = self.spell_manager.get_all_sources()
        dialog = SourceFilterDialog(
            self.winfo_toplevel(),
            available_sources,
            self._selected_sources,
            self._source_filter_mode
        )
        self.wait_window(dialog)
        
        self._selected_sources = dialog.result
        self._source_filter_mode = dialog.result_mode
        self._update_source_label()
        self._on_filter_changed(immediate=True)
    
    def _update_source_label(self):
        """Update the source label with selected source count and mode."""
        count = len(self._selected_sources)
        mode_labels = {
            SourceFilterMode.INCLUDE: "include",
            SourceFilterMode.EXCLUDE: "exclude"
        }
        mode_str = mode_labels.get(self._source_filter_mode, "")
        
        if count == 0:
            self.source_label.configure(text="None selected")
        elif count == 1:
            self.source_label.configure(text=f"1 source ({mode_str}): {self._selected_sources[0]}")
        else:
            self.source_label.configure(text=f"{count} sources ({mode_str})")
    
    def _update_tags_label(self):
        """Update the tags label with selected tag count and mode."""
        count = len(self._selected_tags)
        mode_labels = {
            TagFilterMode.HAS_ALL: "all",
            TagFilterMode.HAS_ANY: "any",
            TagFilterMode.HAS_NONE: "none"
        }
        mode_str = mode_labels.get(self._tag_filter_mode, "")
        
        if count == 0:
            self.tags_label.configure(text="None selected")
        elif count == 1:
            self.tags_label.configure(text=f"1 tag ({mode_str}): {self._selected_tags[0]}")
        else:
            self.tags_label.configure(text=f"{count} tags ({mode_str})")
    
    def _toggle_advanced_filters(self):
        """Toggle the advanced filters panel visibility."""
        self._advanced_expanded = not self._advanced_expanded
        
        if self._advanced_expanded:
            self.advanced_btn.configure(text="▲ Filters")
            self.advanced_frame.pack(fill="x", padx=15, pady=(0, 10), before=self._main_content)
            self._update_filter_dropdowns()
        else:
            self.advanced_btn.configure(text="▼ Filters")
            self.advanced_frame.pack_forget()
    
    def _update_filter_dropdowns(self):
        """Update the casting time, duration, and source dropdowns with current values."""
        # Preserve current selections
        current_cast_time = self.cast_time_var.get()
        current_duration = self.duration_var.get()
        current_min_range = self.min_range_var.get()
        
        # Casting times
        cast_times = ["Any"] + self.spell_manager.get_all_casting_times()
        self.cast_time_combo.configure(values=cast_times)
        # Restore selection if still valid, otherwise reset to "Any"
        if current_cast_time in cast_times:
            self.cast_time_var.set(current_cast_time)
        else:
            self.cast_time_var.set("Any")
        
        # Durations
        durations = ["Any"] + self.spell_manager.get_all_durations()
        self.duration_combo.configure(values=durations)
        if current_duration in durations:
            self.duration_var.set(current_duration)
        else:
            self.duration_var.set("Any")
        
        # Range values
        ranges = self.spell_manager.get_all_ranges_for_display()
        self._range_display_to_value = {label: value for value, label in ranges}
        range_labels = [label for _, label in ranges]
        self.min_range_combo.configure(values=range_labels)
        if current_min_range in range_labels:
            self.min_range_var.set(current_min_range)
        else:
            self.min_range_var.set("Self")
    
    def _clear_advanced_filters(self):
        """Reset all advanced filters to their default values."""
        self.ritual_var.set("Any")
        self.conc_var.set("Any")
        self.min_range_var.set("Self")
        self.verbal_var.set("Any")
        self.somatic_var.set("Any")
        self.material_var.set("Any")
        self.costly_var.set("Any")
        self.cast_time_var.set("Any")
        self.duration_var.set("Any")
        self._selected_sources = []
        self._source_filter_mode = SourceFilterMode.INCLUDE
        self._update_source_label()
        self._selected_tags = []
        self._tag_filter_mode = TagFilterMode.HAS_ALL
        self._update_tags_label()
        self._on_filter_changed(immediate=True)
    
    def _create_main_content(self):
        """Create the main content area with resizable two-panel layout."""
        # Main content frame
        self._main_content = ctk.CTkFrame(self.spells_view, fg_color="transparent")
        self._main_content.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        # Create a PanedWindow for resizable panels
        # opaqueresize=False for smooth dragging (shows ghost line, resizes on release)
        self.main_paned = tk.PanedWindow(
            self._main_content,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            handlesize=0,
            opaqueresize=False,
            sashcursor="sb_h_double_arrow"
        )
        # Set initial color based on current theme
        self._update_paned_colors()
        self.main_paned.pack(fill="both", expand=True)
        
        # Left panel container (for spell list or compare panel)
        self.left_container = ctk.CTkFrame(self.main_paned, fg_color="transparent")
        
        # Left panel - Spell list
        from ui.spell_list import SpellListPanel
        self.spell_list = SpellListPanel(
            self.left_container, 
            self._on_spell_selected,
            on_right_click=self._on_spell_right_click
        )
        self.spell_list.pack(fill="both", expand=True)
        
        # Right panel - Spell detail
        from ui.spell_detail import SpellDetailPanel
        self.spell_detail = SpellDetailPanel(
            self.main_paned, 
            on_edit=self._on_edit_spell,
            on_delete=self._on_delete_spell,
            on_export=self._on_export_spell,
            on_add_to_list=self._on_add_to_list,
            character_manager=self.character_manager,
            spell_manager=self.spell_manager,
            on_restore=self._on_restore_spell
        )
        
        # Add panes with minimum sizes
        self.main_paned.add(self.left_container, minsize=280, stretch="always")
        self.main_paned.add(self.spell_detail, minsize=400, stretch="always")
        
        # Set initial sash position (roughly 1:2 ratio)
        self.after(100, lambda: self.main_paned.sash_place(0, 320, 0))
        
        # Compare panel (created but not shown initially)
        self._create_compare_panel()
    
    def _create_compare_panel(self):
        """Create the compare spell panel (hidden initially)."""
        from ui.spell_detail import SpellDetailPanel
        theme = get_theme_manager()

        # Container frame that will replace the spell list when comparing
        self.compare_container = ctk.CTkFrame(self.left_container, corner_radius=10,
                                               fg_color=theme.get_current_color('bg_secondary'))
        
        # Header with close button
        header = ctk.CTkFrame(self.compare_container, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text="Compare Spell",
            font=ui_font("subheading", bold=True)
        ).pack(side="left")
        
        theme = get_theme_manager()
        close_btn = ctk.CTkButton(
            header, text="✕", width=30, height=30,
            fg_color=theme.get_current_color('button_danger'), hover_color=theme.get_current_color('button_danger_hover'),
            command=self._close_compare_panel
        )
        close_btn.pack(side="right")
        
        # The detail panel for comparing
        self.compare_detail = SpellDetailPanel(
            self.compare_container,
            on_edit=self._on_edit_spell,
            on_delete=self._on_delete_spell,
            on_export=self._on_export_spell,
            on_add_to_list=self._on_add_to_list,
            character_manager=self.character_manager,
            spell_manager=self.spell_manager
        )
        self.compare_detail.pack(fill="both", expand=True)
    
    def _create_context_menu(self):
        """Create the right-click context menu for spells."""
        self.context_menu = tk.Menu(self, tearoff=0)
        self._update_context_menu_colors()
        self.context_menu.add_command(
            label="Add to Spell List",
            command=self._context_add_to_list
        )
        self.context_menu.add_command(
            label="View and Compare",
            command=self._context_view_compare
        )
        
        # Store reference to the spell being acted on
        self._context_spell: Optional[Spell] = None
    
    def _on_spell_right_click(self, spell: Spell, x: int, y: int):
        """Handle right-click on a spell in the list."""
        self._context_spell = spell
        try:
            self.context_menu.tk_popup(x, y)
        finally:
            self.context_menu.grab_release()
    
    def _context_add_to_list(self):
        """Context menu: Add spell to a character's list."""
        if self._context_spell and self.character_manager:
            from ui.spell_detail import AddToListDialog, SpellWarningDialog
            from spell_slots import get_max_cantrips, get_max_spell_level, get_character_classes
            
            characters = self.character_manager.characters
            dialog = AddToListDialog(
                self.winfo_toplevel(),
                self._context_spell.name,
                characters
            )
            self.wait_window(dialog)
            
            if dialog.result:
                # Get the selected character
                character = self.character_manager.get_character(dialog.result)
                if character:
                    # Check for warnings
                    warnings = self._validate_spell_for_character(
                        self._context_spell, character
                    )
                    
                    if warnings:
                        # Show warning dialog
                        warning_dialog = SpellWarningDialog(
                            self.winfo_toplevel(),
                            self._context_spell.name,
                            warnings
                        )
                        self.wait_window(warning_dialog)
                        
                        if not warning_dialog.result:
                            return  # User cancelled
                    
                    # Add the spell
                    self._on_add_to_list(self._context_spell, dialog.result)
    
    def _validate_spell_for_character(self, spell: Spell, character) -> List[str]:
        """Validate if a spell is appropriate for a character.
        Respects settings for which warnings to show.
        """
        # Use shared validation utility with settings filtering
        return validate_spell_for_character(
            spell, character,
            spell_manager=self.spell_manager,
            settings=self.settings_manager.settings
        )
    
    def _context_view_compare(self):
        """Context menu: View and compare spell."""
        if self._context_spell:
            # Check if the primary detail panel has a spell
            primary_spell = self.spell_detail._current_spell
            
            if primary_spell is None:
                # No spell in primary panel - open there instead
                self.spell_list.select_spell(self._context_spell.name)
            else:
                # Show compare panel
                self._show_compare_panel(self._context_spell)
    
    def _show_compare_panel(self, spell: Spell):
        """Show the compare panel with the given spell."""
        self._compare_mode = True
        self._compare_spell = spell
        
        # Hide spell list, show compare panel
        self.spell_list.pack_forget()
        self.compare_container.pack(fill="both", expand=True)
        
        # Set the spell in compare panel
        self.compare_detail.set_spell(spell)
        
        # Apply comparison coloring to both panels (if enabled in settings)
        if self.settings_manager.settings.show_comparison_highlights:
            primary_spell = self.spell_detail._current_spell
            if primary_spell:
                # Primary panel compares against compare spell
                self.spell_detail.apply_comparison(spell, is_primary=True)
                # Compare panel compares against primary spell
                self.compare_detail.apply_comparison(primary_spell, is_primary=False)
    
    def _close_compare_panel(self):
        """Close the compare panel and return to spell list."""
        self._compare_mode = False
        self._compare_spell = None
        
        # Clear comparison coloring from primary panel
        self.spell_detail.clear_comparison()
        
        # Clear comparison from compare panel
        self.compare_detail.clear_comparison()
        
        # Hide compare panel, show spell list
        self.compare_container.pack_forget()
        self.spell_list.pack(fill="both", expand=True)
    
    def _get_current_filters(self):
        """Get current filter values including advanced filters."""
        search_text = self.search_var.get()
        
        # Level filter
        level_str = self.level_var.get()
        if level_str == "All":
            level_filter = -1
        elif level_str == "Cantrip":
            level_filter = 0
        else:
            level_filter = int(level_str)
        
        # Class filter - use class name string directly (for custom class support)
        class_str = self.class_var.get()
        class_name_filter = "" if class_str == "All" else class_str
        
        # Build advanced filters
        advanced = AdvancedFilters()
        
        # Ritual filter
        ritual_val = self.ritual_var.get()
        if ritual_val == "Ritual Only":
            advanced.ritual_filter = True
        elif ritual_val == "Non-Ritual":
            advanced.ritual_filter = False
        
        # Concentration filter
        conc_val = self.conc_var.get()
        if conc_val == "Concentration":
            advanced.concentration_filter = True
        elif conc_val == "Non-Concentration":
            advanced.concentration_filter = False
        
        # Minimum range - look up the selected display label to get the actual value
        range_label = self.min_range_var.get()
        if range_label in self._range_display_to_value:
            advanced.min_range = self._range_display_to_value[range_label]
        else:
            advanced.min_range = 0  # Default to Self
        
        # Component filters
        verbal_val = self.verbal_var.get()
        if verbal_val == "Has V":
            advanced.has_verbal = True
        elif verbal_val == "No V":
            advanced.has_verbal = False
        
        somatic_val = self.somatic_var.get()
        if somatic_val == "Has S":
            advanced.has_somatic = True
        elif somatic_val == "No S":
            advanced.has_somatic = False
        
        material_val = self.material_var.get()
        if material_val == "Has M":
            advanced.has_material = True
        elif material_val == "No M":
            advanced.has_material = False
        
        # Costly component filter
        costly_val = self.costly_var.get()
        if costly_val == "Has GP Cost":
            advanced.costly_component = True
        elif costly_val == "No GP Cost":
            advanced.costly_component = False
        
        # Casting time filter
        cast_time_val = self.cast_time_var.get()
        if cast_time_val != "Any":
            advanced.casting_time_filter = cast_time_val
        
        # Duration filter
        duration_val = self.duration_var.get()
        if duration_val != "Any":
            advanced.duration_filter = duration_val
        
        # Source filter (multi-select)
        advanced.source_filter = self._selected_sources.copy()
        advanced.source_filter_mode = self._source_filter_mode
        
        # Tags filter
        advanced.tags_filter = self._selected_tags.copy()
        advanced.tags_filter_mode = self._tag_filter_mode
        
        return search_text, level_filter, class_name_filter, advanced
    
    def _refresh_spell_list(self, reset_scroll: bool = True):
        """Refresh the spell list with current filters.
        
        Args:
            reset_scroll: If True, scroll position resets to top (default True)
        """
        search_text, level_filter, class_name_filter, advanced = self._get_current_filters()
        legacy_filter = self.settings_manager.settings.legacy_content_filter
        filtered_spells = self.spell_manager.get_filtered_spells(
            search_text, level_filter, class_name_filter, advanced, legacy_filter
        )
        self.spell_list.set_spells(filtered_spells, reset_scroll=reset_scroll)
    
    def _on_filter_changed(self, immediate: bool = False):
        """Called when any filter value changes.
        Uses debouncing to avoid excessive database queries during typing.
        
        Args:
            immediate: If True, apply filters with minimal delay (for dropdowns)
        """
        # Cancel any pending debounced call
        if self._filter_debounce_id is not None:
            self.after_cancel(self._filter_debounce_id)
            self._filter_debounce_id = None
        
        if immediate:
            # Apply with minimal delay to allow UI to update first
            self._filter_debounce_id = self.after(10, self._apply_debounced_filter)
        else:
            # Debounce text input to avoid excessive queries
            self._filter_debounce_id = self.after(
                self._filter_debounce_delay,
                self._apply_debounced_filter
            )
    
    def _apply_debounced_filter(self):
        """Apply the filter after debounce delay."""
        self._filter_debounce_id = None
        self._refresh_spell_list()
    
    def refresh_class_filter(self):
        """Refresh the class filter dropdown to include newly imported custom classes."""
        if hasattr(self, 'class_combo'):
            current_value = self.class_var.get()
            class_options = ["All"] + CharacterClass.spellcasting_class_names()
            self.class_combo.configure(values=class_options)
            # Preserve current selection if still valid
            if current_value not in class_options:
                self.class_var.set("All")

    def refresh_all_collection_views(self):
        """Reload every already-open collection list so freshly imported content shows up
        without restarting the app. Each sub-view is lazily created on first visit, so only
        refresh the ones that actually exist; managers themselves are reloaded separately."""
        self.refresh_class_filter()
        self._refresh_spell_list()
        if hasattr(self, 'classes_view'):
            self.classes_view._populate_class_list()
        for attr in ('feats_view', 'lineages_view', 'backgrounds_view', 'equipment_view',
                     'magic_items_view', 'monsters_view'):
            view = getattr(self, attr, None)
            if view is not None:
                view.refresh()

    def _on_spells_changed(self):
        """Called when the spell collection changes."""
        self._update_filter_dropdowns()
        self._refresh_spell_list()
    
    def _on_spell_selected(self, spell):
        """Called when a spell is selected in the list."""
        self.spell_detail.set_spell(spell)
        
        # If in compare mode, update comparison (if enabled in settings)
        if self._compare_mode and self._compare_spell and spell:
            if self.settings_manager.settings.show_comparison_highlights:
                self.spell_detail.apply_comparison(self._compare_spell, is_primary=True)
                self.compare_detail.apply_comparison(spell, is_primary=False)
    
    def _on_new_spell(self):
        """Open dialog to create a new spell (manual entry or auto-detect from text)."""
        from ui.spell_editor import SpellEditorDialog
        from ui.spell_text_import import AddSpellSourceDialog

        source_dialog = AddSpellSourceDialog(self.winfo_toplevel())
        self.wait_window(source_dialog)
        if source_dialog.result is None:
            return
        if source_dialog.result == "auto":
            self._on_new_spell_from_text()
            return

        dialog = SpellEditorDialog(self.winfo_toplevel(), "New Spell", spell_manager=self.spell_manager)
        self.wait_window(dialog)

        if dialog.result:
            if self.spell_manager.add_spell(dialog.result):
                self.spell_list.select_spell(dialog.result.name)
            else:
                messagebox.showerror("Error",
                    f"A spell named '{dialog.result.name}' already exists.")

    def _on_new_spell_from_text(self):
        """Paste a block of text, auto-detect spell fields, and review each draft."""
        from ui.spell_editor import SpellEditorDialog
        from ui.spell_text_import import SpellTextImportDialog

        import_dialog = SpellTextImportDialog(self.winfo_toplevel())
        self.wait_window(import_dialog)
        parsed_list = import_dialog.result
        if not parsed_list:
            return

        try:
            from text_import.spell_parser import to_spell
        except Exception as exc:
            messagebox.showerror("Auto-Detect Unavailable",
                                 f"Could not load the text importer:\n{exc}")
            return

        added = []
        total = len(parsed_list)
        for idx, parsed in enumerate(parsed_list, 1):
            try:
                draft = to_spell(parsed)
            except Exception as exc:
                messagebox.showerror("Parse Error",
                                     f"Could not build spell {idx} of {total}:\n{exc}")
                continue

            review = sorted(set(parsed.needs_review()) | set(parsed.uncertain_fields()))
            progress = f"{idx} of {total}" if total > 1 else ""

            editor = SpellEditorDialog(
                self.winfo_toplevel(),
                f"Review Spell: {draft.name or 'Untitled'}",
                spell_manager=self.spell_manager,
                prefill_spell=draft, review_fields=review, batch_progress=progress,
            )
            self.wait_window(editor)

            if editor.result:
                if self.spell_manager.add_spell(editor.result):
                    added.append(editor.result.name)
                else:
                    messagebox.showerror(
                        "Error",
                        f"A spell named '{editor.result.name}' already exists. "
                        "It was not added.")
            elif idx < total:
                if not messagebox.askyesno(
                        "Continue?",
                        "Skip this spell and continue reviewing the remaining "
                        f"{total - idx} spell(s)?"):
                    break

        if added:
            self.spell_list.select_spell(added[-1])
            if len(added) > 1:
                messagebox.showinfo("Spells Added",
                                    f"Added {len(added)} spells:\n" + "\n".join(added))


    def _on_edit_spell(self, spell):
        """Open dialog to edit an existing spell."""
        from ui.spell_editor import SpellEditorDialog
        dialog = SpellEditorDialog(self.winfo_toplevel(), "Edit Spell", spell, spell_manager=self.spell_manager)
        self.wait_window(dialog)
        
        if dialog.result:
            if self.spell_manager.update_spell(spell.name, dialog.result):
                self.spell_list.select_spell(dialog.result.name)
            else:
                messagebox.showerror("Error", 
                    f"A spell named '{dialog.result.name}' already exists.")
    
    def _on_restore_spell(self, spell):
        """Restore a modified official spell to its default values."""
        if self.spell_manager.restore_spell_to_default(spell.name):
            # Refresh the spell list and detail view
            self._refresh_spell_list(reset_scroll=False)
            # Re-select the restored spell to show updated details
            self.spell_list.select_spell(spell.name)
            messagebox.showinfo("Success", 
                f"'{spell.name}' has been restored to its original version.")
        else:
            messagebox.showerror("Error", 
                f"Failed to restore '{spell.name}'.")
    
    def _on_delete_spell(self, spell):
        """Delete the selected spell."""
        # Check if deletion of official spells is allowed
        if spell.is_official and not self.settings_manager.settings.allow_delete_official_spells:
            messagebox.showwarning(
                "Cannot Delete Official Spell",
                f"'{spell.name}' is an official spell and cannot be deleted.\n\n"
                "You can enable deletion of official spells in Settings if needed."
            )
            return
        
        if messagebox.askyesno("Confirm Delete", 
                               f"Are you sure you want to delete '{spell.name}'?"):
            self.spell_manager.delete_spell(spell.name)
            self.spell_detail.set_spell(None)
    
    def _on_export_spell(self, spell):
        """Export a single spell to an importable JSON file (Collections > Import reads it back)."""
        import content_io

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{spell.name.replace(' ', '_')}.json"
        )
        
        if not file_path:
            return
        try:
            content_io.export_objects(file_path, {"spells": [spell]}, self.spell_manager)
            messagebox.showinfo("Success", f"Spell exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export spell:\n{e}")
    
    def _on_add_to_list(self, spell, character_name: str):
        """Add a spell to a character's known spells."""
        if self.character_manager.add_spell_to_character(character_name, spell.name):
            if self.settings_manager.settings.show_spell_added_notification:
                messagebox.showinfo("Success", 
                    f"'{spell.name}' added to {character_name}'s spell list.")
        else:
            # Always show if already exists (this is a different type of feedback)
            messagebox.showinfo("Info", 
                f"'{spell.name}' is already in {character_name}'s spell list.")
    
