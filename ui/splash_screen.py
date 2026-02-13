"""
Splash Screen for D&D Spellbook Application.
Shows a loading screen while the application initializes.
"""

import customtkinter as ctk
from typing import Callable, Optional
import os
import sys


class SplashScreen(ctk.CTkToplevel):
    """Splash screen shown during application startup."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # Configure window
        self.title("Loading Spellbook...")
        self.geometry("400x250")
        self.resizable(False, False)
        
        # Remove window decorations for a cleaner look
        self.overrideredirect(True)
        
        # Center on screen
        self.update_idletasks()
        width = 400
        height = 250
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Keep on top
        self.attributes("-topmost", True)
        
        # Create UI
        self._create_widgets()
        
        # Force the window to display
        self.lift()
        self.update()
    
    def _create_widgets(self):
        """Create splash screen widgets."""
        # Main container with themed background
        self.container = ctk.CTkFrame(self, fg_color=("#1a1a2e", "#1a1a2e"), corner_radius=0)
        self.container.pack(fill="both", expand=True)
        
        # Try to load icon
        self._load_icon()
        
        # App title
        self.title_label = ctk.CTkLabel(
            self.container,
            text="Spellbook",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="#ffffff"
        )
        self.title_label.pack(pady=(5, 3))
        
        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.container,
            text="A D&D resource manager",
            font=ctk.CTkFont(size=14),
            text_color="#b0b0b0"
        )
        self.subtitle_label.pack(pady=(0, 20))
        
        # Status message
        self.status_label = ctk.CTkLabel(
            self.container,
            text="Initializing...",
            font=ctk.CTkFont(size=12),
            text_color="#808080"
        )
        self.status_label.pack(pady=(0, 8))
        
        # Progress bar
        self.progress = ctk.CTkProgressBar(
            self.container,
            width=300,
            height=8,
            progress_color="#3b8ed0",
            fg_color="#2b2b3e"
        )
        self.progress.pack(pady=(0, 15))
        self.progress.set(0)
    
    def _load_icon(self):
        """Try to load and display the app icon."""
        try:
            if getattr(sys, 'frozen', False):
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            icon_path = os.path.join(base_path, "Spellbook Icon.png")
            if os.path.exists(icon_path):
                from PIL import Image
                img = Image.open(icon_path)
                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                self._icon_image = ctk.CTkImage(light_image=img, dark_image=img, size=(64, 64))
                
                icon_label = ctk.CTkLabel(
                    self.container,
                    image=self._icon_image,
                    text=""
                )
                icon_label.pack(pady=(15, 0))
        except Exception:
            pass  # Icon is optional
    
    def set_status(self, message: str):
        """Update the status message."""
        self.status_label.configure(text=message)
        self.update()
    
    def set_progress(self, value: float):
        """Set progress bar value (0.0 to 1.0)."""
        self.progress.set(value)
        self.update()
    
    def update_progress(self, message: str, value: float):
        """Update both status and progress."""
        self.set_status(message)
        self.set_progress(value)
