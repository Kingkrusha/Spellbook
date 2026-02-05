"""
Spellbook Application
A desktop application for managing D&D spells with search, filter, and edit capabilities.
"""

import os
import customtkinter as ctk
from ui.main_window import MainWindow

# Try to import PIL for better icon support
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def run_data_migrations():
    """Run data migrations to update old data files."""
    try:
        from data_migration import run_all_migrations
        run_all_migrations()
    except Exception as e:
        print(f"Data migration warning: {e}")


def main():
    """Application entry point."""
    # Run data migrations before starting the app
    run_data_migrations()
    
    # Set appearance and color theme
    ctk.set_appearance_mode("dark")  # "dark", "light", or "system"
    ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"
    
    # Create main window
    root = ctk.CTk()
    root.title("Spellbook")
    root.geometry("1100x750")
    root.minsize(900, 600)
    
    # Set app icon
    base_path = os.path.dirname(__file__)
    icon_png_path = os.path.join(base_path, "Spellbook Icon.png")
    icon_ico_path = os.path.join(base_path, "Spellbook Icon.ico")
    
    # Try .ico first (best for Windows taskbar)
    if os.path.exists(icon_ico_path):
        try:
            root.iconbitmap(icon_ico_path)
        except Exception:
            pass
    
    # Also set iconphoto for title bar (PNG via PIL if available)
    if os.path.exists(icon_png_path):
        try:
            if HAS_PIL:
                img = Image.open(icon_png_path)  # type: ignore[possibly-unbound]
                icon = ImageTk.PhotoImage(img)  # type: ignore[possibly-unbound]
                root.iconphoto(True, icon)  # type: ignore[arg-type]
                root._icon = icon  # type: ignore[attr-defined] - Keep reference to prevent GC
            else:
                from tkinter import PhotoImage
                icon = PhotoImage(file=icon_png_path)
                root.iconphoto(True, icon)  # type: ignore[arg-type]
                root._icon = icon  # type: ignore[attr-defined]
        except Exception:
            pass
    
    # Create main application window
    app = MainWindow(root)
    app.pack(fill="both", expand=True)
    
    # Start the application
    root.mainloop()


if __name__ == "__main__":
    main()
