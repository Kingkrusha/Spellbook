"""
Spellbook Application
A desktop application for managing D&D spells with search, filter, and edit capabilities.
"""

import sys


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
                   "ui.transfer_dialogs", "ui.game_tools_view"]
        for name in modules:
            importlib.import_module(name)
        import cryptography
        from lan.client import LanClient
        from lan.host import LanHost

        host = LanHost("Self-test", require_approval=False)
        host.start(port=0, bind="127.0.0.1")
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
    
    # Track if we're currently closing
    closing = [False]
    app_ref: list = [None]  # Will hold reference to MainWindow
    
    def on_closing():
        """Handle window close with splash screen."""
        if closing[0]:
            return  # Already closing
        closing[0] = True
        
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
            
            # Close splash and show main window
            splash.destroy()
            root.deiconify()
            root.lift()
            root.focus_force()
            
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


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--lan-selftest":
        raise SystemExit(_lan_selftest(sys.argv[2]))
    main()
