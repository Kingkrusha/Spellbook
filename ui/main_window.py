"""
Main application window for D&D Spellbook (CustomTkinter version).
"""

from collections import OrderedDict

import customtkinter as ctk
from tkinter import messagebox
from typing import Optional, Dict
from spell_manager import SpellManager
from character_manager import CharacterManager
from settings import get_settings_manager
from theme import get_theme_manager
import tab_session
from ui.restyle import install_global as install_global_restyler, restyle_app
from ui.tab_bar import DraggableTabBar
from ui.lazy_destroy import destroy_later
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
        self._current_tab_id: Optional[str] = None  # Current active tab_id
        self._current_tab_type = "home"  # Kind of page the active tab shows
        self._current_collection = None  # Current sub-collection being viewed (for collections tabs)
        # tab_id -> {type: page kind, view: the page's widget, current_collection: key or None}
        self._tab_views: Dict[str, Dict] = {}
        self._last_regular_tab_id: Optional[str] = None  # last active tab that was not Settings
        self._restoring_tabs = False  # True while reopening the saved tabs at startup
        self._tab_save_after = None  # pending debounced save of the open tabs
        # Collection pages built ahead of time (see _preload_sub_view): the next collections
        # tab to open that collection takes it instead of building its own
        self._spare_sub_views: Dict[str, ctk.CTkFrame] = {}
        
        # Build UI. Settings and a first spell browser are set up front (so the first visit
        # to Spells is instant); every other page is built when a tab navigates to it.
        # The tab bar packs itself at the top since no view is packed yet.
        self._update_progress("Building spells view...", 0.65)
        self._spare_sub_views["spells"] = self._new_sub_view("spells")

        self._update_progress("Building settings...", 0.85)
        self._create_settings_view()

        self._update_progress("Finalizing UI...", 0.90)
        self._create_tab_bar()  # Also opens the first (Home) tab

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
        it. (The lists inside are virtualized - see ui/virtual_list.py - so a
        view costs the same however many entries it holds.)
        """
        settings = self.settings_manager.settings
        steps = []
        if settings.preload_classes:
            steps.append(("classes", self._preload_classes))
        if settings.preload_feats:
            steps.append(("feats", lambda: self._preload_sub_view("feats")))
        if settings.preload_lineages:
            steps.append(("lineages", lambda: self._preload_sub_view("lineages")))
        if settings.preload_backgrounds:
            steps.append(("backgrounds", lambda: self._preload_sub_view("backgrounds")))
        if getattr(settings, 'preload_equipment', True):
            steps.append(("equipment", lambda: self._preload_sub_view("equipment")))
        if getattr(settings, 'preload_magic_items', True):
            steps.append(("magic items", lambda: self._preload_sub_view("magic_items")))
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

    def _preload_sub_view(self, key: str):
        """Build a collection page ahead of time (unpacked) for the next tab that needs it."""
        if key in self._spare_sub_views:
            return
        self._spare_sub_views[key] = self._new_sub_view(key)

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
            views = [view_info.get('view')]
            views += [entry['view'] for entry in (view_info.get('cache') or {}).values()]
            for view in views:
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

    def _transfer_managers(self):
        """What the Send / Inbox dialogs need to read and write characters and homebrew."""
        from transfer import Managers
        from ui.character_sheet_view import get_sheet_manager
        return Managers(self.character_manager, get_sheet_manager(), self.spell_manager)

    def _on_session_event(self, kind: str, **data):
        if kind in ('state', 'inbox'):
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
                               overlay=self.chat_overlay, get_managers=self._transfer_managers)
        raise ValueError(f"Unknown page type: {page_type}")

    # Pages a tab has left are kept (hidden) for a while, so going back to Home, the Characters
    # list, a character sheet or a collection is instant. Building and - especially - destroying
    # CustomTkinter widgets is slow (a button costs ~10 ms to destroy), so throwing a page away
    # on every navigation is what made switching feel sluggish.
    CACHEABLE_PAGES = ("home", "collections", "characters", "character_sheet")
    PAGE_CACHE_SIZE = 3        # left pages kept per tab
    SUB_VIEW_CACHE_SIZE = 3    # collection pages kept per tab

    def _page_key(self, page_type: str, character: Optional[str] = None) -> tuple:
        return (page_type, character) if page_type == "character_sheet" else (page_type,)

    def _navigate_tab(self, tab_id: str, page_type: str, **kwargs):
        """Make a tab show a different page (like following a link in a browser tab)."""
        info = self._tab_views.get(tab_id)
        if info is None:
            return
        character = kwargs.get('character')
        key = self._page_key(page_type, character)
        self._stash_page(tab_id)

        entry = self._take_cached_page(info, key)
        info['type'] = page_type
        info['page_key'] = key
        info['current_collection'] = None
        if entry is not None:
            info['view'] = entry['view']
            if entry['sub_views']:
                info['sub_views'] = entry['sub_views']
            info.pop('fresh', None)  # a reused page catches up with changes when it is shown
        else:
            info['view'] = self._build_page(tab_id, page_type, character=character)
            info['fresh'] = True  # just built: nothing to catch up on when it is first shown
            if page_type == 'character_sheet':
                info['pending_character'] = character  # selected once it is on screen
        self.tab_bar.update_tab_text(tab_id, self._page_title(page_type, character))

        if tab_id == self._current_tab_id:
            self._show_tab_content(tab_id)
            if entry is not None and page_type == 'characters':
                info['view'].refresh()
        self._schedule_tab_save()

    def _stash_page(self, tab_id: str):
        """Take the page a tab is showing off screen, keeping it for when the tab comes back."""
        info = self._tab_views.get(tab_id)
        if info is None or info.get('view') is None:
            return
        view = info['view']
        page_type = info['type']
        key = info.get('page_key')
        self._hide_tab_content(tab_id)

        entry = {'view': view, 'sub_views': info.pop('sub_views', None) or OrderedDict()}
        info['view'] = None
        info.pop('sub_view', None)
        info.pop('sub_view_key', None)
        loaded = info.pop('pending_character', None) is None  # a sheet that never showed has nothing to keep

        if page_type in self.CACHEABLE_PAGES and key and loaded:
            if page_type == 'character_sheet' and not self._sheet_still_valid(view):
                self._dispose_entry(entry)
                return
            cache = info.setdefault('cache', OrderedDict())
            stale = cache.pop(key, None)
            if stale is not None:
                self._dispose_entry(stale)
            cache[key] = entry
            while len(cache) > self.PAGE_CACHE_SIZE:
                self._dispose_entry(cache.popitem(last=False)[1])
        else:
            self._dispose_entry(entry, immediately=page_type not in self.CACHEABLE_PAGES)

    def _take_cached_page(self, info: dict, key: tuple):
        """The cached page for ``key`` (removed from the cache), or None."""
        cache = info.get('cache')
        entry = cache.pop(key, None) if cache else None
        if entry is None:
            return None
        if key[0] == 'character_sheet' and not self._sheet_still_valid(entry['view']):
            self._dispose_entry(entry)
            return None
        return entry

    def _sheet_still_valid(self, view) -> bool:
        """A kept sheet can be reused only while its character and sheet are still the live ones
        (the character may have been deleted, or its sheet replaced by an import)."""
        character = getattr(view, 'current_character', None)
        if character is None or self.character_manager.get_character(character.name) is None:
            return False
        from ui.character_sheet_view import get_sheet_manager
        return get_sheet_manager().get_sheet(character.name) is getattr(view, 'current_sheet', None)

    def _dispose_tab(self, info: dict):
        """Get rid of everything a closed tab was holding."""
        entries = list((info.pop('cache', None) or {}).values())
        if info.get('view') is not None:
            entries.append({'view': info['view'], 'sub_views': info.pop('sub_views', None) or {}})
            info['view'] = None
        for entry in entries:
            self._dispose_entry(entry)
        info.pop('sub_view', None)
        info.pop('sub_view_key', None)
        info.pop('pending_character', None)

    def _dispose_entry(self, entry: dict, immediately: bool = False):
        """Destroy a page and its collection pages. Heavy pages are taken apart in small slices
        so the window does not freeze; pages with their own teardown logic go at once."""
        widgets = list(entry.get('sub_views', {}).values()) + [entry['view']]
        for widget in widgets:
            if widget is None:
                continue
            self._detach_orphaned_sheet(widget)  # a sheet whose character is gone must not re-save
            if immediately:
                try:
                    widget.pack_forget()
                    widget.destroy()  # a sheet saves its pending edits on the way out
                except Exception:
                    pass
            else:
                self._destroy_later(widget)

    def _destroy_later(self, widget):
        """Destroy a widget tree a little at a time instead of in one freeze (ui/lazy_destroy.py)."""
        destroy_later(widget)

    def _detach_orphaned_sheet(self, view):
        """If a sheet is no longer the live one for its character - the character was deleted
        (e.g. from another tab), or its sheet was replaced (deleted and recreated, or imported)
        - stop it from saving itself back over the real data when it is torn down."""
        character = getattr(view, 'current_character', None)
        if character is not None and not self._sheet_still_valid(view):
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
            self._dispose_tab(self._tab_views[tab_id])
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
        # ... and the collection page this tab was showing, if any
        self._hide_sub_view(info)
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
            self._show_collection_sub_view(tab_id, info['current_collection'])
            return

        view.pack(fill="both", expand=True)
        if info['type'] == 'settings':
            view.refresh_from_settings()
        elif info['type'] == 'character_sheet':
            pending = info.pop('pending_character', None)
            if pending:
                view.select_character(pending)

    # Collection pages (spells, classes, ...). Every collections tab has its own instance of
    # the page it is showing (info['sub_view'], kept while the tab stays on that collection),
    # so tabs never share a selection, filters or scroll position.

    SUB_VIEW_CLASSES = {
        "classes": ("ui.classes_view", "ClassesCollectionView"),
        "feats": ("ui.feats_view", "FeatsView"),
        "lineages": ("ui.lineages_view", "LineagesView"),
        "backgrounds": ("ui.backgrounds_view", "BackgroundsView"),
        "equipment": ("ui.equipment_view", "EquipmentView"),
        "magic_items": ("ui.magic_item_view", "MagicItemView"),
        "monsters": ("ui.monster_view", "MonsterView"),
    }
    # Method each page has for selecting an item by name
    SUB_VIEW_SELECTORS = {
        "spells": "select_spell", "classes": "select_class", "feats": "select_feat",
        "lineages": "select_lineage", "backgrounds": "select_background",
        "equipment": "select_item", "magic_items": "select_item", "monsters": "select_monster",
    }
    # How long each page needs to finish rendering before an item can be selected in it
    SUB_VIEW_SELECT_DELAY_MS = {"spells": 100, "classes": 300}

    def _new_sub_view(self, key: str):
        """Build a collection page (not packed yet)."""
        if key == "spells":
            from ui.spells_view import SpellsView
            return SpellsView(self, self.spell_manager, self.character_manager,
                              self.settings_manager, on_back=self._back_to_collections)
        import importlib
        module, class_name = self.SUB_VIEW_CLASSES[key]
        view_class = getattr(importlib.import_module(module), class_name)
        if key == "classes":
            return view_class(self, on_back=self._back_to_collections)
        return view_class(self, character_manager=self.character_manager,
                          on_back=self._back_to_collections)

    def _show_collection_sub_view(self, tab_id: str, collection_key: str, item_name: Optional[str] = None):
        """Show a tab's collection page (building it if the tab has none for it yet).

        The tab keeps the last few collections it showed, so hopping between Spells, Feats, ...
        and back does not rebuild anything."""
        info = self._tab_views.get(tab_id)
        if info is None:
            return
        pages = info.setdefault('sub_views', OrderedDict())
        view = pages.pop(collection_key, None)  # re-inserted below as the most recent
        if view is None:
            view = self._spare_sub_views.pop(collection_key, None) or self._new_sub_view(collection_key)
        pages[collection_key] = view

        shown = info.get('sub_view')
        if shown is not None and shown is not view:
            try:
                shown.pack_forget()
            except Exception:
                pass
        info['sub_view'] = view
        info['sub_view_key'] = collection_key
        view.pack(fill="both", expand=True)

        while len(pages) > self.SUB_VIEW_CACHE_SIZE:
            oldest = next(k for k in pages if k != collection_key)
            self._destroy_later(pages.pop(oldest))

        if item_name:
            delay = self.SUB_VIEW_SELECT_DELAY_MS.get(collection_key, 150)
            self.after(delay, lambda: self._select_collection_item(view, collection_key, item_name))

    def _select_collection_item(self, view, collection_key: str, name: str):
        """Select an item by name in a collection page (if it is still there)."""
        try:
            if view.winfo_exists():
                getattr(view, self.SUB_VIEW_SELECTORS[collection_key])(name)
        except Exception:
            pass

    def _hide_sub_view(self, info: dict):
        """Take a tab's collection page off screen (it stays alive)."""
        view = info.get('sub_view')
        if view is not None:
            try:
                view.pack_forget()
            except Exception:
                pass

    def _all_sub_views(self):
        """(collection key, page) for every collection page that exists: shown, kept, or spare."""
        seen = set()
        for info in self._tab_views.values():
            groups = [info.get('sub_views') or {}]
            groups += [entry['sub_views'] for entry in (info.get('cache') or {}).values()]
            for pages in groups:
                for key, view in pages.items():
                    if id(view) not in seen:
                        seen.add(id(view))
                        yield key, view
        yield from self._spare_sub_views.items()

    def refresh_class_filter(self):
        """Refresh every spell page's class filter (includes newly imported custom classes)."""
        for key, view in self._all_sub_views():
            if key == "spells":
                view.refresh_class_filter()

    def refresh_all_collection_views(self):
        """Reload every already-open collection list so freshly imported content shows up
        without restarting the app. Pages are built on demand, so only the ones that exist are
        refreshed; managers themselves are reloaded separately."""
        for key, view in self._all_sub_views():
            if key == "spells":
                view.reload()
            elif key == "classes":
                view._populate_class_list()
            else:
                view.refresh()

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
        self._show_collection_sub_view(tab_id, collection_key, item_name)
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

    def _navigate_to_spell(self, spell_name: str):
        """Open a spell in a new Spells tab (so the sheet it was clicked from stays put)."""
        index = self.tab_bar.get_tab_index(self._current_tab_id) + 1 if self._current_tab_id else None
        tab_id = self._open_page_in_new_tab("collections", index=index)
        self._navigate_to_collection_in_tab(tab_id, "spells", spell_name)

    def _back_to_collections(self):
        """Go back to the main collections view within the current tab."""
        # Get the current tab
        if not self._current_tab_id or self._current_tab_id not in self._tab_views:
            return

        view_info = self._tab_views[self._current_tab_id]

        # Only process collections tabs
        if view_info['type'] != 'collections':
            return

        # Hide the collection page (kept, in case the tab goes straight back to it)
        self._hide_sub_view(view_info)

        # Reset the current collection state
        view_info['current_collection'] = None
        self._current_collection = None

        # Reset tab name to "Collections"
        self.tab_bar.update_tab_text(self._current_tab_id, "Collections")
        self._schedule_tab_save()

        # Show the collections hub view for this tab
        view_info['view'].pack(fill="both", expand=True)

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
    
    def _on_appearance_changed(self, mode: str):
        """Handle appearance mode change from settings."""
        # Light/dark switched: re-resolve every role-tagged colour on screen
        restyle_app()

        # Update theme-dependent widgets that use tk (not ctk) on the spell pages
        for key, view in self._all_sub_views():
            if key == "spells":
                view.apply_theme()

    def _on_theme_changed(self):
        """Handle ThemeManager changes (colors updated or custom theme saved)."""
        theme = get_theme_manager()
        # Recolour every widget on screen from its theme role (also picks up
        # widgets that never passed an explicit colour)
        restyle_app()

        # Update widgets that rely on TK colors or CTkFrame backgrounds (spell pages)
        for key, view in self._all_sub_views():
            if key == "spells":
                view.apply_theme()

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

        # Update the search bar on every open collections hub
        try:
            for view_info in self._tab_views.values():
                view = view_info.get('view')
                if view_info['type'] == 'collections' and hasattr(view, 'search_bar'):
                    view.search_bar.update_colors()
        except Exception:
            pass
    
