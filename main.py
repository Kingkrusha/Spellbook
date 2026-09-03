"""
Spellbook Application
A desktop application for managing D&D spells with search, filter, and edit capabilities.
"""

import customtkinter as ctk

from ui.window_icon import install as install_app_icon, set_app_user_model_id


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
    main()
