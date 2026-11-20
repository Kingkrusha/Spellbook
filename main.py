"""
Spellbook Application
A desktop application for managing D&D spells with search, filter, and edit capabilities.
"""

import sys
import time

# When this run started: it names the run in crash.log and spellbook.log, so a crash report can find it
STARTED = time.strftime("%Y-%m-%d %H:%M:%S")


def _ensure_std_streams():
    """Give ``print()`` somewhere safe to write.

    PyInstaller builds with ``console=False`` (all three .spec files here) run
    with ``sys.stdout``/``sys.stderr`` set to ``None`` on Windows and macOS -
    there's no console to attach to. The app has many ``print()`` calls in
    error-handling paths (character/character-sheet save failures among them);
    against a ``None`` stream those raise ``AttributeError`` instead of
    logging, and that new exception escapes the ``except`` block uncaught,
    silently abandoning whatever save or migration was in progress. Redirect
    to a log file up front so those diagnostics land somewhere instead of
    crashing the operation that was trying to report them.
    """
    if not (len(sys.argv) >= 2 and sys.argv[1] == "--lan-selftest"):
        try:      # everything printed is also kept in spellbook.log (see app_log.py)
            import app_log
            app_log.install(started=STARTED)
        except Exception:
            pass
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        from paths import user_data_path
        log_file = open(user_data_path("spellbook.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        import io
        log_file = io.StringIO()
    if sys.stdout is None:
        sys.stdout = log_file
    if sys.stderr is None:
        sys.stderr = log_file


_ensure_std_streams()


def _lan_selftest(out_path: str) -> int:
    """``Spellbook --lan-selftest <file>``: prove the LAN stack works in *this* build.

    A windowed (console-less) PyInstaller exe can't print, so the result is written to ``out_path``
    as JSON. It imports every LAN module, makes the per-session TLS certificate, starts a host, joins
    it as a client over loopback, and sends a chat message and a dice roll through it. No window is
    shown and no user data is read or written.
    """
    import json
    import traceback

    result = {"ok": False}
    try:
        import importlib
        import ssl

        modules = ["lan.protocol", "lan.security", "lan.runtime", "lan.host", "lan.client", "lan.service",
                   "lan.discovery", "lan.dice", "transfer", "character_io", "ui.session_view",
                   "ui.session_widgets", "ui.chat_overlay", "ui.chat_input", "ui.chat_render",
                   "ui.transfer_dialogs", "ui.game_tools_view", "initiative_state", "initiative_rows",
                   "initiative_sources", "conditions", "tracker_hub", "tracker_net", "ui.initiative_table",
                   "ui.initiative_dialogs", "ui.initiative_view", "ui.initiative_window"]
        for name in modules:
            importlib.import_module(name)
        import cryptography
        from lan.client import LanClient
        from lan.host import LanHost

        host = LanHost("Self-test", require_approval=False)
        host.start(port=0, bind="127.0.0.1")
        # the initiative tracker's rules run too: a tiny encounter, projected for a player
        import initiative_state as T
        tracker = T.Tracker()
        tracker.dispatch(T.DM, {"type": "add_entry", "kind": "custom", "name": "Probe Ogre", "hp": 5,
                                "hidden": True})
        if T.project(tracker.state, T.Actor("player", "x"))["entries"]:
            raise RuntimeError("tracker leaked a hidden entry")
        client = LanClient("Probe")
        try:
            client.connect("127.0.0.1", host.port, host.fingerprint, timeout=15)
            client.send_chat("/roll 2d6+1")
            roll = None
            for _ in range(50):
                ev = client.events.get(timeout=0.2)
                if ev and ev["type"] == "roll":
                    roll = ev
                    break
            if roll is None or not 3 <= roll["total"] <= 13:
                raise RuntimeError(f"no sensible dice roll came back: {roll}")
        finally:
            client.close()
            host.stop()
        result = {"ok": True, "modules": len(modules), "cryptography": cryptography.__version__,
                  "openssl": ssl.OPENSSL_VERSION, "tls": "1.3", "roll": roll["total"]}
    except Exception:
        result["error"] = traceback.format_exc()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return 0 if result["ok"] else 1

import customtkinter as ctk

from ui.window_icon import install as install_app_icon, set_app_user_model_id
from ui.ctk_patches import install as install_ctk_patches


def run_data_migrations():
    """Run data migrations to update old data files."""
    try:
        from data_migration import run_all_migrations
        run_all_migrations()
    except Exception as e:
        print(f"Data migration warning: {e}")


_crash_log = None             # crash.log, open for the whole run (faulthandler writes to it)
FREEZE_SECONDS = 30           # the window not answering for this long counts as frozen (see _watch_for_freezes)
MAX_CRASH_REPORTS_A_DAY = 3


def _install_crash_logging(root):
    """Leave evidence when something goes wrong, so a report has more than "it crashed".

    * Unhandled errors in Tk callbacks (button clicks, timers, ...) are recorded in
      ``crash.log`` in the data folder, then reported as usual. The window keeps running after
      them, so without this they are invisible in a windowed build.
    * ``faulthandler`` writes the Python stack of every thread there if the process dies for a
      reason Python cannot catch (a native crash), which is otherwise completely silent.
    """
    global _crash_log
    import os
    import time
    import traceback
    try:
        from paths import user_data_path
        handle = open(user_data_path("crash.log"), "a", encoding="utf-8", buffering=1)
    except Exception:
        return
    _crash_log = handle
    try:
        import app_log
        handle.write("\n" + app_log.start_line(STARTED, os.getpid()) + "\n")
        import faulthandler
        faulthandler.enable(file=handle, all_threads=True)
    except Exception:
        pass

    def log(kind, exc, value, tb):
        try:
            handle.write(f"\n--- {kind} {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            handle.write("".join(traceback.format_exception(exc, value, tb)))
        except Exception:
            pass

    original_hook = sys.excepthook

    def excepthook(exc, value, tb):
        log("unhandled error", exc, value, tb)
        original_hook(exc, value, tb)
    sys.excepthook = excepthook

    original_report = root.report_callback_exception

    def report_callback_exception(exc, value, tb):
        log("error in a UI callback", exc, value, tb)
        original_report(exc, value, tb)
    root.report_callback_exception = report_callback_exception

    try:       # errors in background threads (the LAN host/client, update check)
        import threading
        previous = threading.excepthook

        def thread_hook(args):
            log(f"error in thread {getattr(args.thread, 'name', '?')}", args.exc_type, args.exc_value,
                args.exc_traceback)
            previous(args)
        threading.excepthook = thread_hook
    except Exception:
        pass


def _watch_for_freezes(root):
    """If the window stops answering for FREEZE_SECONDS, write what every thread is doing to crash.log.

    faulthandler's own watchdog thread does the writing (Python code can't run on a stuck thread); the
    window only keeps pushing its deadline back while it is still answering. A freeze that ends with the
    app being closed by force is then reported like a crash (crash_report.py)."""
    import faulthandler
    if _crash_log is None:
        return

    def push_back():
        try:
            faulthandler.dump_traceback_later(FREEZE_SECONDS, repeat=False, file=_crash_log, exit=False)
            root.after(5000, push_back)
        except Exception:
            pass
    push_back()


def _report_earlier_crashes(app, crashed):
    """After a run that didn't close normally: send the developer its logs (Settings > Help can turn
    this off), at most a few a day, and say so at the bottom of the window."""
    import threading
    import crash_report
    import feedback
    settings_manager = app.settings_manager
    settings = settings_manager.settings
    done = str(getattr(settings, "crash_report_done", "") or "")
    pick = None
    for run in crashed:                                  # newest first
        report = None
        if pick is None and run.key != done:
            try:
                report = crash_report.report_for(run)
            except Exception as e:
                print(f"Crash report: couldn't read the logs: {e}")
        if report is not None:
            pick = (run, report)
        else:
            crash_report.forget(run)                     # nothing to tell, already told, or older
    if pick is None:
        return
    run, report = pick
    from ui.hotkey_actions import toast
    if not getattr(settings, "send_crash_reports", True):
        crash_report.forget(run)
        toast(app, "Spellbook closed unexpectedly last time. You can tell the developer with "
                   "Send feedback (Shift+F1).", ms=8000)
        return
    now = time.time()
    recent = [t for t in (getattr(settings, "crash_reports_sent", None) or [])
              if isinstance(t, (int, float)) and now - t < 86400]
    if len(recent) >= MAX_CRASH_REPORTS_A_DAY:
        crash_report.forget(run)
        return
    outcome = []

    def work():
        try:
            feedback.send(report)
            outcome.append(None)
        except Exception as e:
            outcome.append(str(e))
    threading.Thread(target=work, name="crash-report", daemon=True).start()

    def check():
        if not outcome:
            app.after(250, check)
            return
        if outcome[0] is None:
            crash_report.forget(run)
            settings_manager.update(crash_report_done=run.key, crash_reports_sent=(recent + [now])[-10:])
            toast(app, "Spellbook closed unexpectedly last time, so a crash report was sent to the developer. "
                       "(You can turn this off in Settings > Help.)", ms=8000)
        else:
            print(f"Crash report: not sent ({outcome[0]}); trying again next time.")
    app.after(250, check)


def main():
    """Application entry point."""
    # Must run before any window is created so Windows groups the taskbar
    # button under Spellbook (not pythonw.exe) and uses our icon.
    set_app_user_model_id()

    # Removes a CustomTkinter redraw that made the first paint several times slower
    install_ctk_patches()

    # Set appearance and color theme first
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # Create main window (hidden initially)
    root = ctk.CTk()
    root.title("Spellbook")
    root.geometry("1100x750")
    root.minsize(900, 600)
    root.withdraw()  # Hide until fully loaded
    _install_crash_logging(root)
    # Tk objects freed on the network (or any other) thread are finished off on Tk's thread
    from ui import tk_threads
    tk_threads.install(root)
    # Runs that didn't close normally (this run is noted too, and the note removed when it closes)
    crashed = []
    try:
        import crash_report
        from version import __version__
        crashed = crash_report.begin_run(STARTED, __version__)
    except Exception as e:
        print(f"Crash report: couldn't note this run: {e}")
    
    # Track if we're currently closing
    closing = [False]
    app_ref: list = [None]  # Will hold reference to MainWindow
    
    def on_closing():
        """Handle window close with splash screen."""
        if closing[0]:
            return  # Already closing
        closing[0] = True

        # Remember where the window was and how big, for next time
        try:
            from settings import get_settings_manager
            from ui.window_utils import window_memory
            manager = get_settings_manager()
            kept = window_memory(root, manager.settings.window_geometry)
            if kept != manager.settings.window_geometry:
                manager.update(window_geometry=kept)
        except Exception as e:
            print(f"Window size not remembered: {e}")

        # Show closing splash
        from ui.splash_screen import ClosingSplash
        splash = ClosingSplash(root)
        
        def do_cleanup():
            """Perform actual cleanup."""
            try:
                splash.set_status("Saving data...")
                root.update()

                # Flush any edit still sitting in a focused widget before we
                # tear the window down (otherwise the last unfocused change is
                # lost).
                if app_ref[0]:
                    try:
                        app_ref[0].commit_pending_edits()
                    except Exception:
                        pass

                # Destroy the main app window first
                if app_ref[0]:
                    try:
                        app_ref[0].destroy()
                    except Exception:
                        pass
                
                splash.set_status("Closing...")
                root.update()
                
            except Exception:
                pass
            finally:
                # Stop progress animation and destroy
                try:
                    splash.progress.stop()
                    splash.destroy()
                except Exception:
                    pass
                root.quit()
                root.destroy()
        
        # Schedule cleanup after splash is shown
        root.after(50, do_cleanup)
    
    # Override window close protocol
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # Set the app icon on the root window and every future CTkToplevel (this
    # also monkeypatches CTkToplevel to defeat CustomTkinter's own icon).
    install_app_icon(root)

    # Show splash screen
    from ui.splash_screen import SplashScreen
    splash = SplashScreen(root)
    
    def load_app():
        """Load the application in stages with progress updates."""
        try:
            # Stage 1: Data migrations
            splash.update_progress("Running data migrations...", 0.1)
            root.update()
            run_data_migrations()
            
            # Stage 2: Import main window (triggers module loading)
            splash.update_progress("Loading modules...", 0.2)
            root.update()
            from ui.main_window import MainWindow
            
            # Stage 3: Create main window with progress callback
            splash.update_progress("Initializing database...", 0.3)
            root.update()
            
            app = MainWindow(root, progress_callback=splash.update_progress)
            app.pack(fill="both", expand=True)
            app_ref[0] = app  # Store reference for cleanup
            
            # Stage 4: Final setup
            splash.update_progress("Finalizing...", 1.0)
            root.update()
            
            # Close splash and show main window, the size and in the place it was left
            from settings import get_settings_manager
            from ui.window_utils import restore_window, zoom_window
            zoomed = restore_window(root, get_settings_manager().settings.window_geometry)
            splash.destroy()
            root.deiconify()
            if zoomed:
                zoom_window(root)
            root.lift()
            root.focus_force()
            _watch_for_freezes(root)
            if crashed:
                app.after(3000, lambda: _report_earlier_crashes(app, crashed))
            
        except Exception as e:
            print(f"Error during startup: {e}")
            import traceback
            traceback.print_exc()
            splash.destroy()
            root.deiconify()
    
    # Schedule loading after splash is displayed
    root.after(100, load_app)
    
    # Start the application
    root.mainloop()
    # Closed normally: no freeze watch, and no crash report about this run next time
    try:
        import faulthandler
        faulthandler.cancel_dump_traceback_later()
    except Exception:
        pass
    try:
        import crash_report
        crash_report.end_run()
    except Exception:
        pass


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--lan-selftest":
        raise SystemExit(_lan_selftest(sys.argv[2]))
    main()
