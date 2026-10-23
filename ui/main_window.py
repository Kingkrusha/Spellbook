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
from ui import handle_budget, lazy_destroy
import tkinter as tk
from ui.lazy_view import LazyView

# Collections a tab can be showing (also what a restored tab may reopen on)
COLLECTION_KEYS = ("spells", "classes", "feats", "lineages", "backgrounds",
                   "equipment", "magic_items", "monsters", "rules")

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
        self._use_clock = 0   # "last used" stamps for the handle budget (see _touch)
        
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

        # Keep the process under Windows' handle limit (see ui/handle_budget.py)
        handle_budget.set_reclaimer(self._make_headroom)
        self.after(2500, self._budget_tick)

        # Rule links in popups ("Open in Rules") open a Rules tab
        from ui.object_link_widgets import set_rule_opener
        set_rule_opener(self.open_rule)

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
        if getattr(settings, 'preload_rules', True):
            steps.append(("rules", lambda: self._preload_sub_view("rules")))
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
        if key in self._spare_sub_views or handle_budget.over(handle_budget.BACKGROUND_LIMIT):
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
            if self._tracker_link is not None:
                self._tracker_link.close()
            for window in list(self._tracker_windows.values()):
                window.close()
            self.tracker_hub.flush()            # a fight in progress must survive closing the app
        except Exception:
            pass

        try:
            import tabletop
            if self._table_link is not None:
                self._table_link.close()
            if tabletop._tabletop is not None:      # players' moves made while the page was closed
                tabletop._tabletop.save()
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

    # Initiative tracker: one encounter for the whole app, shown on a page and/or in pop-up windows.

    @property
    def tracker_hub(self):
        if self._tracker_hub is None:
            from tracker_hub import TrackerHub
            self._tracker_hub = TrackerHub(schedule=lambda ms, fn: self.after(ms, fn), cancel=self.after_cancel)
        return self._tracker_hub

    def _sync_tracker_links(self):
        """The tracker follows the session: hosting means every player is sent their view of it;
        being a player means the tracker window is fed by the host."""
        from lan.service import CLIENT, HOSTING
        role = self.session.role
        if role == HOSTING and self._tracker_link is None:
            from tracker_net import TrackerHostLink
            self._tracker_link = TrackerHostLink(self.tracker_hub, self.session,
                                                 schedule=lambda ms, fn: self.after(ms, fn))
        elif role != HOSTING and self._tracker_link is not None:
            self._tracker_link.close()
            self._tracker_link = None
        if role == CLIENT and self._remote_tracker is None:
            from tracker_net import RemoteBackend
            self._remote_tracker = RemoteBackend(self.session)
            self._remote_was_started = False
        # the tabletop follows the session the same way
        if role == HOSTING and self._table_link is None:
            from tabletop_net import TableHostLink
            self._table_link = TableHostLink(self.session, schedule=lambda ms, fn: self.after(ms, fn))
        elif role != HOSTING and self._table_link is not None:
            self._table_link.close()
            self._table_link = None
        if role == CLIENT and self._remote_table is None:
            from tabletop_net import RemoteTable
            self._remote_table = RemoteTable(self.session)
        elif role != CLIENT and self._remote_table is not None:
            self._remote_table.close()
            self._remote_table = None
        if role != CLIENT and self._remote_tracker is not None:
            window = self._tracker_windows.get("remote")
            if window is not None and window.winfo_exists():
                window.close()
            self._remote_tracker.close()
            self._remote_tracker = None

    def _maybe_open_tracker_for_player(self, view: dict):
        """A player's tracker window opens by itself when the DM starts combat (turn it off in
        Settings; closing the window keeps it closed until the next encounter)."""
        started = bool(view.get("started"))
        was, self._remote_was_started = self._remote_was_started, started
        if started and not was and getattr(self.settings_manager.settings, "tracker_auto_open", True):
            self.open_tracker_window("remote")

    def open_initiative(self):
        """The DM gets the tracker page; a player gets the window fed by the host."""
        from lan.service import CLIENT
        if self.session.role == CLIENT:
            self.open_tracker_window("remote")
        else:
            self._open_page_in_new_tab("initiative")

    def _tracker_players(self):
        """``[(display name, install id)]`` of the players connected to the session being hosted."""
        s = self.session
        return [(p["name"], s.client_ids[p["peer_id"]]) for p in s.peers
                if p["peer_id"] != s.my_id and p["peer_id"] in s.client_ids]

    def open_tracker_window(self, which: str = "dm"):
        """Open (or raise) a tracker pop-up. ``which``: "dm", or "player:<owner id>" to preview what
        that player sees ("player:" alone is an observer with no character)."""
        existing = self._tracker_windows.get(which)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            return existing
        from ui.initiative_window import InitiativeWindow
        hub = self.tracker_hub
        if which == "remote":
            if self._remote_tracker is None:
                return None
            backend, kind, title = self._remote_tracker, "player", "Initiative"
        elif which == "dm":
            backend, kind, title = hub.dm(), "dm", "Initiative (DM)"
        else:
            owner = which.partition(":")[2]
            backend, kind = hub.player(owner), "player"
            title = "Initiative (preview as player)" if which != "player:" or owner else "Initiative"
        window = InitiativeWindow(self.winfo_toplevel(), backend, self.settings_manager, kind=kind, title=title,
                                  get_managers=self._transfer_managers)
        self._tracker_windows[which] = window
        window.bind("<Destroy>", lambda e, w=which: self._tracker_windows.pop(w, None) if e.widget is window else None,
                    add="+")
        return window

    def _init_session(self):
        self._tracker_hub = None
        self._tracker_windows = {}
        self._tracker_link = None           # while hosting: sends each player their view
        self._remote_tracker = None         # while a player: the host's view, as a backend
        self._table_link = None             # while hosting: sends each player their view of the shown map
        self._remote_table = None           # while a player: the map the DM shows
        self._initiative_link = None        # tabletop tokens <-> initiative tracker entries (the DM's)
        self._remote_was_started = False
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
        if kind == 'state':
            self._sync_tracker_links()
        elif kind == 'tracker_state':
            self._maybe_open_tracker_for_player(data.get('view') or {})
        elif kind == 'table_state':
            scene = (data.get('view') or {}).get('scene') or {}
            shown = scene.get('id')
            if shown and shown != getattr(self, '_table_last_note', None):
                self._table_last_note = shown
                self.session.note(f"The DM is showing the map '{str(scene.get('name', ''))[:60]}'. "
                                  "Open it in Game Tools > Tabletop.")
        elif kind == 'approval_request':
            from ui.session_widgets import ApprovalDialog
            request_id = data['request_id']
            self._approval_dialogs[request_id] = ApprovalDialog(
                self.winfo_toplevel(), data['name'], data['address'],
                lambda accept, rid=request_id: self.session.resolve_approval(rid, accept), web=bool(data.get('web')))
        elif kind == 'approval_done':
            dialog = self._approval_dialogs.pop(data['request_id'], None)
            if dialog is not None:
                dialog.dismiss()
        elif kind == 'ended':
            for dialog in list(self._approval_dialogs.values()):
                dialog.dismiss()
            self._approval_dialogs.clear()
            window = self._tracker_windows.get("remote")
            if window is not None and window.winfo_exists():
                window.close()

    def _update_session_bar(self):
        """Show the status bar under the tabs while a session is running."""
        if self.session.active and self._session_bar is None:
            from ui.session_widgets import SessionStatusBar
            self._session_bar = SessionStatusBar(self, self.session, on_open=self._open_session_page,
                                                 on_initiative=self.open_initiative)
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

        self._install_hotkeys()

    def _install_hotkeys(self):
        """Bind the keyboard shortcuts (Settings > Keyboard Shortcuts changes them)."""
        import hotkeys
        from ui.hotkey_actions import build_handlers
        overrides = dict(getattr(self.settings_manager.settings, 'hotkeys', {}) or {})
        try:
            manager = hotkeys.install(self.winfo_toplevel(), build_handlers(self), overrides)
        except Exception as e:
            print(f"Keyboard shortcuts are off: {e}")
            return
        last = {'value': overrides}

        def on_settings(settings):
            # Reset to defaults (or an edit elsewhere) changed the shortcuts: bind them again
            current = dict(getattr(settings, 'hotkeys', {}) or {})
            if current != last['value']:
                last['value'] = current
                manager.apply(current)
        self.settings_manager.add_listener(on_settings)

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
            "initiative": "Initiative",
            "dice_analyzer": "Dice Analyzer",
            "matchup": "Matchup",
            "random_tables": "Random Tables",
            "calendar": "Calendar",
            "pdf_library": "PDF Library",
            "tabletop": "Tabletop",
            "studio": "Homebrew Studio",
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
        if page == "studio":
            page = "game_tools"       # the Studio is heavy to build: a restored tab opens on the tool list instead
        if page not in ("home", "collections", "characters", "character_sheet", "game_tools", "session",
                    "initiative", "dice_analyzer", "matchup", "random_tables", "calendar", "pdf_library",
                    "tabletop"):
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
                character = (shown.name if shown else info.get('pending_character')
                             or (info.get('suspended') or {}).get('character'))
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
            view = info.get('view')
            if view is not None:
                character = view.current_character.name if view.current_character else None
            else:
                character = (info.get('suspended') or {}).get('character')
            self._open_page_in_new_tab(page_type, index=index, character=character)
        elif page_type == 'collections' and info.get('current_collection'):
            new_id = self._open_page_in_new_tab(page_type, index=index)
            self._navigate_to_collection_in_tab(new_id, info['current_collection'])
        else:
            self._open_page_in_new_tab(page_type, index=index)

    def _build_page(self, tab_id: str, page_type: str, character: Optional[str] = None):
        """Create the widget for a page (not packed yet)."""
        self._make_headroom()
        return self._guarded_build(lambda: self._build_page_now(tab_id, page_type, character))

    def _build_page_now(self, tab_id: str, page_type: str, character: Optional[str] = None):
        if page_type == "home":
            from ui.home_view import HomeView
            return HomeView(self, on_open=lambda key, tid=tab_id: self._open_from_home(tid, key))
        if page_type == "collections":
            from ui.collections_view import CollectionsView
            return CollectionsView(
                self,
                spell_manager=self.spell_manager,
                on_navigate=lambda key, name=None, tid=tab_id: self._navigate_to_collection_in_tab(tid, key, name),
                on_home=lambda tid=tab_id: self._navigate_tab(tid, "home"),
                on_open_studio=lambda tid=tab_id: self._navigate_tab(tid, "studio")
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
                               overlay=self.chat_overlay, get_managers=self._transfer_managers,
                               on_initiative=self.open_initiative, get_characters=self._session_character_names,
                               character_info=self._session_character_info)
        if page_type == "initiative":
            from ui.initiative_view import InitiativeView
            return InitiativeView(
                self, self.tracker_hub, get_managers=self._transfer_managers,
                on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"),
                open_window=self.open_tracker_window, get_players=self._tracker_players)
        if page_type == "dice_analyzer":
            return self._build_dice_analyzer(tab_id)
        if page_type == "matchup":
            return self._build_matchup(tab_id)
        if page_type == "random_tables":
            from ui.random_tables_view import RandomTablesView
            state = self._tab_views[tab_id].setdefault('random_tables_state', {}) \
                if tab_id in self._tab_views else {}
            return RandomTablesView(self, state, service=self.session,
                                    on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"))
        if page_type == "calendar":
            from ui.calendar_view import CalendarView
            state = self._tab_views[tab_id].setdefault('calendar_state', {}) if tab_id in self._tab_views else {}
            return CalendarView(self, state, on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"))
        if page_type == "pdf_library":
            from ui.pdf_library_view import PdfLibraryView
            state = self._tab_views[tab_id].setdefault('pdf_state', {}) if tab_id in self._tab_views else {}
            return PdfLibraryView(self, state, on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"),
                                  on_import_text=self.import_text_into)
        if page_type == "tabletop":
            from ui.tabletop_view import TabletopView
            state = self._tab_views[tab_id].setdefault('tabletop_state', {}) if tab_id in self._tab_views else {}
            from lan.service import CLIENT
            if self.session.role != CLIENT:
                self._tabletop_initiative()         # catch the tokens up with the tracker
            return TabletopView(self, state, service=self.session, remote_backend=lambda: self._remote_table,
                                on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"),
                                characters=self._tabletop_characters, initiative=self._tabletop_initiative,
                                on_open_source=lambda kind, name, tid=tab_id: self._open_token_source(tid, kind, name))
        if page_type == "studio":
            return self._build_studio(tab_id)
        raise ValueError(f"Unknown page type: {page_type}")

    def _open_token_source(self, tab_id: str, kind: str, name: str):
        """A tabletop token's stat block (a monster) or character sheet, in a new tab beside the map."""
        if kind == "character":
            self._open_character(tab_id, name, new_tab=True)
            return
        index = self.tab_bar.get_tab_index(tab_id) + 1
        new_id = self._open_page_in_new_tab("collections", index=index)
        self._navigate_to_collection_in_tab(new_id, "monsters", name)

    def _tabletop_initiative(self):
        """The link between tabletop tokens and the initiative tracker, made the first time it's needed."""
        if self._initiative_link is None:
            import tabletop
            from tabletop_initiative import InitiativeLink
            self._initiative_link = InitiativeLink(tabletop.get_tabletop(), self.tracker_hub.tracker,
                                                   lookup=self._initiative_entry_for_token)
        return self._initiative_link

    def _initiative_entry_for_token(self, token: dict):
        """The tracker entry (AC, initiative bonus...) for a token made from a monster or a character."""
        import initiative_sources as S
        kind, _, name = (token.get("source") or "").partition(":")
        if kind == "monster":
            from monster import get_monster_manager
            monster = get_monster_manager().get_monster(name)
            return S.from_monster(monster) if monster is not None else None
        if kind == "character":
            from ui.character_sheet_view import get_sheet_manager
            sheet = get_sheet_manager().get_sheet(name)
            return S.from_sheet(sheet, owner=token.get("owner", "")) if sheet is not None else None
        if kind == "player":                            # a character a connected player is playing
            import initiative_state as T
            c = next((c for c in self.session.player_characters.values()
                      if c.get("client_id") == token.get("owner") and c.get("name") == name), None)
            if c is None:
                return None
            return {"type": "add_entry", "kind": T.KIND_PLAYER, "name": c["name"], "hp": c.get("hp") or 0,
                    "hp_max": c.get("hp_max") or c.get("hp") or 0, "ac": c.get("ac") if c.get("ac") is not None else 10,
                    "owner": token.get("owner", "")}
        return None

    def _session_character_names(self) -> list:
        """This user's characters, for "Playing as" when joining a session."""
        return [c.name for c in self.character_manager.characters]

    def _session_character_info(self, name: str) -> dict:
        """What the DM is told about the character this player plays: numbers, a short line and a small portrait."""
        import base64
        import io
        import portraits
        from ui.character_sheet_view import get_sheet_manager
        info = {"name": name}
        character = self.character_manager.get_character(name)
        if character is not None:
            bits = [f"Level {character.total_level}" if character.total_level else "",
                    character.lineage or "", character.display_classes() if character.classes else ""]
            info["summary"] = " ".join(b for b in bits if b)
        sheet = get_sheet_manager().get_sheet(name)
        if sheet is not None:
            info.update(hp=sheet.hit_points.current, hp_max=sheet.hit_points.maximum, ac=sheet.armor_class)
            path = portraits.portrait_path(getattr(sheet, "portrait", "") or "")
            if path:
                try:
                    from PIL import Image, ImageOps
                    with Image.open(path) as image:
                        image = ImageOps.exif_transpose(image).convert("RGB")
                        image.thumbnail((160, 160))
                        data = io.BytesIO()
                        image.save(data, "JPEG", quality=82)
                    info["portrait"] = base64.b64encode(data.getvalue()).decode("ascii")
                except Exception as e:                  # the portrait is a nicety; the rest still goes
                    print(f"Session: couldn't shrink the portrait of {name}: {e}")
        return info

    def _tabletop_characters(self):
        """``[{name, portrait, hp, hp_max}]`` for the Tabletop's "Character…" button."""
        import portraits
        from ui.character_sheet_view import get_sheet_manager
        out = []
        for c in self.character_manager.characters:
            sheet = get_sheet_manager().get_sheet(c.name)
            entry = {"name": c.name, "portrait": None, "hp": None, "hp_max": None,
                     "player": getattr(c, "player_name", "") or ""}
            if sheet is not None:
                entry["hp"], entry["hp_max"] = sheet.hit_points.current, sheet.hit_points.maximum
                if getattr(sheet, "portrait", None):
                    entry["portrait"] = portraits.portrait_path(sheet.portrait)
            out.append(entry)
        return out

    def _analysis_tools(self):
        """What the Dice Analyzer and Matchup pages need: a character loader and the lookups for the things a sheet
        only knows by name (spells, equipment, classes, magic items, homebrew feats and species)."""
        from character_rolls import Lookups
        from equipment import get_equipment_manager
        from character_class import get_class_manager
        from ui.character_sheet_view import get_sheet_manager
        from magic_item import get_magic_item_manager
        from feat import get_feat_manager
        from lineage import get_lineage_manager

        def load_character(name):
            character = self.character_manager.get_character(name)
            if character is None:
                return None
            sheet = get_sheet_manager().get_sheet(name)
            if sheet is None:
                # no sheet yet: analyse a blank one (without saving it) at the character's level
                from character_sheet import CharacterSheet, calculate_proficiency_bonus
                sheet = CharacterSheet(character_name=name)
                sheet.proficiency_bonus = calculate_proficiency_bonus(sum(c.level for c in character.classes) or 1)
                sheet._unsaved = True
            return character, sheet

        lookups = Lookups(spell=self.spell_manager.get_spell,
                          equipment=lambda n: get_equipment_manager().get_item(n),
                          class_def=lambda n: get_class_manager().get_class(n),
                          magic_item=lambda n: get_magic_item_manager().get_item(n),
                          feat=lambda n: get_feat_manager().get_feat(n),
                          lineage=lambda n: get_lineage_manager().get_lineage(n))
        return load_character, lookups

    def _build_dice_analyzer(self, tab_id: str):
        """The Dice Analyzer page. What it remembers (the roll typed in, the character and roll picked)
        is kept per tab here, so leaving the page and coming back finds it as it was."""
        from ui.dice_analyzer_view import DiceAnalyzerView
        load_character, lookups = self._analysis_tools()
        state = self._tab_views[tab_id].setdefault('dice_state', {}) if tab_id in self._tab_views else {}
        return DiceAnalyzerView(
            self, state,
            character_names=lambda: [c.name for c in self.character_manager.characters],
            load_character=load_character, lookups=lookups,
            on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"))

    def _build_matchup(self, tab_id: str):
        """The Matchup page (a one-on-one fight between two creatures or characters)."""
        from monster import get_monster_manager
        from ui.matchup_view import MatchupView
        load_character, lookups = self._analysis_tools()
        state = self._tab_views[tab_id].setdefault('matchup_state', {}) if tab_id in self._tab_views else {}
        monsters = get_monster_manager()
        return MatchupView(
            self, state,
            character_names=lambda: [c.name for c in self.character_manager.characters],
            load_character=load_character, lookups=lookups,
            monster_names=lambda: sorted(m.name for m in monsters.browsable),
            get_monster=lambda n: monsters.get_monster(n),
            on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"))

    def _build_studio(self, tab_id: str):
        """The Homebrew Studio: write content with the rest of the collection beside it. Which drafts and
        reference panels are open is kept per tab here (the drafts themselves are in studio.json)."""
        from ui.studio_view import StudioView
        state = self._tab_views[tab_id].setdefault('studio_state', {}) if tab_id in self._tab_views else {}
        if not hasattr(self, '_studio_service'):
            from studio_service import StudioService
            self._studio_service = StudioService(self.spell_manager)
        return StudioView(
            self, state, spell_manager=self.spell_manager, service=self._studio_service,
            on_back=lambda tid=tab_id: self._navigate_tab(tid, "game_tools"),
            on_published=self._after_studio_publish)

    def open_studio_new(self, kind: str, name: str = "", record: Optional[dict] = None, parent: str = ""):
        """Open a new Homebrew Studio tab with a new draft of ``kind`` (the Add buttons of the collection pages)."""
        tab_id = self._open_page_in_new_tab("studio")
        view = self._tab_views[tab_id].get('view')
        if view is not None:
            view.new_draft(kind, name=name, record=record, parent=parent)
        return view

    def _after_studio_publish(self):
        """Something was published from the Studio: the open collection lists should show it."""
        try:
            self.refresh_all_collection_views()
        except Exception as e:
            print(f"Could not refresh the collections: {e}")

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

        entry = {'view': view, 'sub_views': info.pop('sub_views', None) or OrderedDict(),
                 'used': self._touch()}
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

    def _dispose_tab(self, info: dict, immediately: bool = False):
        """Get rid of everything a closed (or suspended) tab was holding."""
        entries = list((info.pop('cache', None) or {}).values())
        if info.get('view') is not None:
            entries.append({'view': info['view'], 'sub_views': info.pop('sub_views', None) or {}})
            info['view'] = None
        else:
            info.pop('sub_views', None)
        for entry in entries:
            self._dispose_entry(entry, immediately)
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
        elif key == "initiative":
            from lan.service import CLIENT
            if self.session.role == CLIENT:
                self.open_tracker_window("remote")        # players watch it in the pop-up window
            else:
                self._navigate_tab(tab_id, "initiative")
        elif key == "dice_analyzer":
            self._navigate_tab(tab_id, "dice_analyzer")
        elif key in ("matchup", "random_tables", "calendar", "pdf_library", "tabletop"):
            self._navigate_tab(tab_id, key)
        elif key == "studio":
            self._navigate_tab(tab_id, "studio")

    def _open_character(self, tab_id: str, name: str, new_tab: bool = False):
        """Open a character's sheet in this tab (or a new one)."""
        if new_tab:
            index = self.tab_bar.get_tab_index(tab_id) + 1
            self._open_page_in_new_tab("character_sheet", index=index, character=name)
            return
        # Already open in another tab? Go there instead of opening a second copy
        for other_id, info in self._tab_views.items():
            suspended = info.get('suspended') or {}
            if other_id == tab_id or info['type'] != 'character_sheet' \
                    or (info.get('view') is None and not suspended):
                continue
            shown = info['view'].current_character if info.get('view') is not None else None
            pending = info.get('pending_character') or suspended.get('character')
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
        info['used'] = self._touch()
        if info['type'] != 'settings':
            self._last_regular_tab_id = tab_id
        if info.get('suspended'):
            # Its page was released to save window handles: build it again, as it was
            self._resume_tab(tab_id)
            self._schedule_tab_save()
            return
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

    # ---- window-handle budget -------------------------------------------------------------
    # Windows allows a process 10,000 USER objects and each CustomTkinter widget is several of
    # them, so a handful of tabs of heavy pages could hit the limit (after which Tk cannot create
    # anything: "No more menus can be allocated"). Everything that is not on screen is therefore
    # disposable, in this order: prebuilt spare pages, pages a tab left behind, collection pages
    # a tab is not showing, and finally the page of a background tab (suspended: it is rebuilt,
    # at the same place, when its tab is selected again). Nothing the user is looking at is touched.

    def _touch(self) -> int:
        """A monotonic "last used" stamp for least-recently-used decisions."""
        self._use_clock += 1
        return self._use_clock

    def _eviction_candidates(self) -> list:
        """(priority, last used, kind, tab id, key) for everything that can be given up, cheapest
        to lose first."""
        current = self._current_tab_id
        found = [(0, 0, 'spare', None, key) for key in self._spare_sub_views]
        for tab_id, info in self._tab_views.items():
            if info.get('type') in (None, 'settings'):
                continue
            for key, entry in (info.get('cache') or {}).items():
                found.append((1, entry.get('used', 0), 'cache', tab_id, key))
            shown = info.get('sub_view')
            for key, view in (info.get('sub_views') or {}).items():
                if view is not shown:
                    found.append((2, (info.get('sub_used') or {}).get(key, 0), 'sub', tab_id, key))
            if tab_id != current and info.get('view') is not None \
                    and info['type'] in self.CACHEABLE_PAGES:
                found.append((3, info.get('used', 0), 'tab', tab_id, None))
        found.sort(key=lambda c: (c[0], c[1]))
        return found

    def _dispose_view(self, view, immediately: bool):
        if view is None:
            return
        self._detach_orphaned_sheet(view)
        if immediately:
            try:
                view.pack_forget()
                view.destroy()
            except Exception:
                pass
        else:
            self._destroy_later(view)

    def _evict(self, candidate, immediately: bool):
        _, _, kind, tab_id, key = candidate
        info = self._tab_views.get(tab_id) if tab_id else None
        if kind == 'spare':
            self._dispose_view(self._spare_sub_views.pop(key, None), immediately)
        elif kind == 'cache' and info is not None:
            entry = (info.get('cache') or {}).pop(key, None)
            if entry is not None:
                self._dispose_entry(entry, immediately)
        elif kind == 'sub' and info is not None:
            self._dispose_view((info.get('sub_views') or {}).pop(key, None), immediately)
        elif kind == 'tab' and info is not None:
            self._suspend_tab(tab_id, immediately)

    def _reclaim_handles(self, target_fraction: float, immediately: bool) -> int:
        """Free pages until the handle count is under ``target_fraction`` of the quota (all that
        can be freed if it cannot get there). Not immediately: one page per call, torn down in
        slices. Returns how many things were released."""
        count = handle_budget.user_handles()
        if count is None:
            return 0
        target = handle_budget.quota() * target_fraction
        if immediately:
            lazy_destroy.drain_all()    # what is already being taken apart still holds handles
            count = handle_budget.user_handles() or count
        released = 0
        while count > target:
            candidates = self._eviction_candidates()
            if not candidates:
                break
            self._evict(candidates[0], immediately)
            released += 1
            if not immediately:
                break
            count = handle_budget.user_handles() or 0
        return released

    def _make_headroom(self):
        """Called before building a page: if the process is close to the limit, free pages first."""
        if handle_budget.over(handle_budget.BUILD_LIMIT):
            self._reclaim_handles(handle_budget.TARGET, immediately=True)

    def _budget_tick(self):
        """Every couple of seconds: above the background limit, release one unneeded page."""
        try:
            if not self.winfo_exists():
                return
            level = handle_budget.level()
            delay = 2500
            if level is not None and level > handle_budget.BACKGROUND_LIMIT:
                if not lazy_destroy.pending():
                    self._reclaim_handles(handle_budget.TARGET, immediately=False)
                delay = 700 if level > handle_budget.BUILD_LIMIT else 1200
            self.after(delay, self._budget_tick)
        except Exception:
            try:
                self.after(5000, self._budget_tick)
            except Exception:
                pass

    def _guarded_build(self, build):
        """Run a page build; if Windows refuses to create more windows, free everything that can
        be freed and try once more."""
        try:
            return build()
        except tk.TclError as exc:
            if not handle_budget.is_out_of_handles_error(exc):
                raise
        self._reclaim_handles(0.0, immediately=True)
        try:
            return build()
        except tk.TclError as exc:
            if handle_budget.is_out_of_handles_error(exc):
                messagebox.showerror(
                    "Too many windows open",
                    "Spellbook has run out of room for more windows.\n\n"
                    "Close a few tabs (or go back to the Collections page in them) and try again.")
            raise

    def _selected_item_name(self, view, key: str) -> Optional[str]:
        """Name of the entry selected in a collection page (so a suspended tab can reselect it)."""
        try:
            if key == "spells":
                item = view.spell_list.get_selected()
            elif key == "classes":
                item = getattr(view, "current_class", None)
            else:
                item = view.list_panel.get_selected()
            return item.name if item is not None else None
        except Exception:
            return None

    def _suspend_tab(self, tab_id: str, immediately: bool = False):
        """Release a background tab's pages, remembering where it was."""
        info = self._tab_views.get(tab_id)
        if info is None or info.get('view') is None or tab_id == self._current_tab_id:
            return
        state = {'type': info['type'], 'character': None,
                 'collection': info.get('current_collection'), 'item': None}
        view = info['view']
        if info['type'] == 'character_sheet':
            shown = getattr(view, 'current_character', None)
            state['character'] = shown.name if shown else info.get('pending_character')
        if state['collection'] and info.get('sub_view') is not None:
            state['item'] = self._selected_item_name(info['sub_view'], info.get('sub_view_key'))
        self._dispose_tab(info, immediately)
        info['suspended'] = state
        info.pop('fresh', None)

    def _resume_tab(self, tab_id: str):
        """Rebuild a suspended tab's page where it was (called as the tab is selected)."""
        info = self._tab_views[tab_id]
        state = info.pop('suspended', None)
        if not state:
            return
        self._navigate_tab(tab_id, state['type'], character=state.get('character'))
        if state.get('collection'):
            self._navigate_to_collection_in_tab(tab_id, state['collection'], state.get('item'))

    # Collection pages (spells, classes, ...). Every collections tab has its own instance of
    # the page it is showing (info['sub_view'], kept while the tab stays on that collection),
    # so tabs never share a selection, filters or scroll position.

    @staticmethod
    def _sub_view_class(key: str):
        """The page class for a collection. These are plain imports, not importlib.import_module
        on a string: PyInstaller only bundles modules it can see imported, so a string-built
        import left every page but Spells/Feats/Monsters out of the packaged app."""
        if key == "classes":
            from ui.classes_view import ClassesCollectionView as view_class
        elif key == "feats":
            from ui.feats_view import FeatsView as view_class
        elif key == "lineages":
            from ui.lineages_view import LineagesView as view_class
        elif key == "backgrounds":
            from ui.backgrounds_view import BackgroundsView as view_class
        elif key == "equipment":
            from ui.equipment_view import EquipmentView as view_class
        elif key == "magic_items":
            from ui.magic_item_view import MagicItemView as view_class
        elif key == "monsters":
            from ui.monster_view import MonsterView as view_class
        elif key == "rules":
            from ui.rules_view import RulesView as view_class
        else:
            raise KeyError(key)
        return view_class

    # Method each page has for selecting an item by name
    SUB_VIEW_SELECTORS = {
        "spells": "select_spell", "classes": "select_class", "feats": "select_feat",
        "lineages": "select_lineage", "backgrounds": "select_background",
        "equipment": "select_item", "magic_items": "select_item", "monsters": "select_monster",
        "rules": "select_rule",
    }
    # How long each page needs to finish rendering before an item can be selected in it
    SUB_VIEW_SELECT_DELAY_MS = {"spells": 100, "classes": 300}

    def _new_sub_view(self, key: str):
        """Build a collection page (not packed yet)."""
        self._make_headroom()
        return self._guarded_build(lambda: self._new_sub_view_now(key))

    def _new_sub_view_now(self, key: str):
        if key == "spells":
            from ui.spells_view import SpellsView
            return SpellsView(self, self.spell_manager, self.character_manager,
                              self.settings_manager, on_back=self._back_to_collections)
        view_class = self._sub_view_class(key)
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
        info.setdefault('sub_used', {})[collection_key] = self._touch()

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

    def refresh_pages_after_import(self, changed):
        """A backup import changed ``changed`` (backup.py category keys): redraw the open pages that
        show them (the Characters list, Random Tables, Calendar), shown or kept in a tab's cache."""
        from ui.calendar_view import CalendarView
        from ui.characters_view import CharactersView
        from ui.random_tables_view import RandomTablesView
        wanted = tuple(cls for key, cls in (("characters", CharactersView), ("random_tables", RandomTablesView),
                                            ("calendars", CalendarView)) if key in changed)
        if not wanted:
            return
        views = []
        for info in self._tab_views.values():
            views.append(info.get('view'))
            views.extend(entry.get('view') for entry in (info.get('cache') or {}).values())
        for view in views:
            if isinstance(view, wanted):
                try:
                    if view.winfo_exists():
                        view.refresh()
                except Exception as e:
                    print(f"Could not refresh {type(view).__name__}: {e}")

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
        if collection_key == "random_tables":
            self._open_random_table(tab_id, item_name)
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

    # collection -> the page method that runs its "add from pasted text" flow
    _TEXT_IMPORTERS = {"spells": "_on_new_spell_from_text", "feats": "_on_add_feat_from_text",
                       "lineages": "_on_add_lineage_from_text", "equipment": "_on_add_item_from_text",
                       "magic_items": "_on_add_item_from_text"}

    def import_text_into(self, collection_key: str, text: str):
        """Open a collection in a new tab and run its text importer on ``text`` (the PDF library's Import)."""
        method = self._TEXT_IMPORTERS.get(collection_key)
        if method is None:
            return
        tab_id = self._open_page_in_new_tab("collections")
        self._navigate_to_collection_in_tab(tab_id, collection_key)
        page = (self._tab_views.get(tab_id) or {}).get('sub_view')
        run = getattr(page, method, None)
        if run is None:
            return
        from ui.text_import_dialogs import TextImportDialog

        def go():
            TextImportDialog.PREFILL = text
            try:
                run()
            finally:
                TextImportDialog.PREFILL = None
        self.after(100, go)

    def _open_random_table(self, tab_id: str, name: Optional[str] = None):
        """Show the Random Tables page in this tab (a random table picked in the global search)."""
        info = self._tab_views.get(tab_id) or {}
        if info.get('type') == 'collections' and hasattr(info.get('view'), 'search_bar'):
            info['view'].search_bar.cleanup()
        if name:
            state = info.setdefault('random_tables_state', {})
            state['selected'], state['query'] = name, ""
        self._navigate_tab(tab_id, "random_tables")
        view = (self._tab_views.get(tab_id) or {}).get('view')
        if name and hasattr(view, 'select_table'):
            view.select_table(name)

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
            'monsters': 'Monsters',
            'rules': 'Rules'
        }

        if item_name and collection_key == 'classes':
            # For specific class, use the class name
            tab_name = item_name
        else:
            tab_name = name_map.get(collection_key, 'Collections')

        self.tab_bar.update_tab_text(tab_id, tab_name)

    def open_rule(self, name: str):
        """Open a rules page (``Page`` or ``Page#Section``) in a new tab, next to the current one."""
        index = self.tab_bar.get_tab_index(self._current_tab_id) + 1 if self._current_tab_id else None
        tab_id = self._open_page_in_new_tab("collections", index=index)
        self._navigate_to_collection_in_tab(tab_id, "rules", name)

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

        # Update theme-dependent widgets that use tk (not ctk) on the spell pages and the rules text
        for key, view in self._all_sub_views():
            if key in ("spells", "rules"):
                view.apply_theme()

    def _on_theme_changed(self):
        """Handle ThemeManager changes (colors updated or custom theme saved)."""
        theme = get_theme_manager()
        # Recolour every widget on screen from its theme role (also picks up
        # widgets that never passed an explicit colour)
        restyle_app()

        # Update widgets that rely on TK colors or CTkFrame backgrounds (spell pages, rules text)
        for key, view in self._all_sub_views():
            if key in ("spells", "rules"):
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
    
