"""
Theme and color management for D&D Spellbook Application.
Centralizes all color definitions for easy customization.
"""

import customtkinter as ctk
from dataclasses import dataclass, field, asdict
from typing import Tuple, Dict, Optional, List, Callable
import json
import os


# Type alias for theme-aware colors: (light_mode_color, dark_mode_color)
ThemeColor = Tuple[str, str]


@dataclass
class ThemeColors:
    """All customizable colors in the application.
    Each color is a tuple of (light_mode, dark_mode).
    """
    
    # === Text Colors ===
    text_primary: ThemeColor = ("#1a1a1a", "#ffffff")  # Main text
    text_secondary: ThemeColor = ("#4a4a4a", "#b0b0b0")  # Secondary/muted text
    text_disabled: ThemeColor = ("#808080", "#606060")  # Disabled text
    text_on_accent: ThemeColor = ("#ffffff", "#ffffff")  # Text on accent backgrounds
    
    # === Background Colors ===
    bg_primary: ThemeColor = ("#f5f5f5", "#1a1a1a")  # Main background
    bg_secondary: ThemeColor = ("#e8e8e8", "#2b2b2b")  # Cards, panels
    bg_tertiary: ThemeColor = ("#d9d9d9", "#3a3a3a")  # Nested elements
    bg_input: ThemeColor = ("#ffffff", "#343638")  # Input fields
    
    # === Accent Colors ===
    accent_primary: ThemeColor = ("#3b8ed0", "#1f538d")  # Primary accent (selected items, active tabs)
    accent_hover: ThemeColor = ("#2d7fc4", "#2a6eb0")  # Hover state for accent
    spell_link: ThemeColor = ("#67bed9", "#67bed9")  # Spell link text color
    
    # === Button Colors ===
    button_normal: ThemeColor = ("#c0c0c0", "#4a4a4a")  # Normal button background
    button_hover: ThemeColor = ("#a0a0a0", "#5a5a5a")  # Button hover state
    button_danger: ThemeColor = ("#dc3545", "#6b3030")  # Delete/danger buttons
    button_danger_hover: ThemeColor = ("#c82333", "#8b4040")
    button_success: ThemeColor = ("#28a745", "#2d5a2d")  # Success/confirm buttons
    button_success_hover: ThemeColor = ("#218838", "#3d6a3d")
    button_warning: ThemeColor = ("#d4a017", "#5a5a2d")  # Warning buttons
    button_warning_hover: ThemeColor = ("#c49516", "#6a6a3d")
    
    # === Comparison Colors ===
    compare_better: ThemeColor = ("#22c55e", "#4ade80")  # Green - better value
    compare_worse: ThemeColor = ("#ef4444", "#f87171")  # Red - worse value
    compare_neutral: ThemeColor = ("#6b7280", "#9ca3af")  # Gray - equal/neutral
    
    # === Spell Level Colors (backgrounds) ===
    level_cantrip: ThemeColor = ("#e0e7ff", "#312e81")  # Indigo tint
    level_1: ThemeColor = ("#dbeafe", "#1e3a5f")  # Blue tint
    level_2: ThemeColor = ("#d1fae5", "#064e3b")  # Emerald tint
    level_3: ThemeColor = ("#fef3c7", "#78350f")  # Amber tint
    level_4: ThemeColor = ("#fee2e2", "#7f1d1d")  # Red tint
    level_5: ThemeColor = ("#f3e8ff", "#581c87")  # Purple tint
    level_6: ThemeColor = ("#cffafe", "#164e63")  # Cyan tint
    level_7: ThemeColor = ("#fce7f3", "#831843")  # Pink tint
    level_8: ThemeColor = ("#ffedd5", "#7c2d12")  # Orange tint
    level_9: ThemeColor = ("#fef9c3", "#713f12")  # Yellow tint
    
    # === UI Element Colors ===
    tab_bar: ThemeColor = ("#e0e0e0", "#1a1a1a")  # Tab bar background
    separator: ThemeColor = ("#d0d0d0", "#404040")  # Separators/dividers
    border: ThemeColor = ("#c0c0c0", "#505050")  # Borders
    scrollbar: ThemeColor = ("#c0c0c0", "#4a4a4a")  # Scrollbar track
    scrollbar_thumb: ThemeColor = ("#909090", "#606060")  # Scrollbar thumb
    
    # === Pane/Sash Colors ===
    pane_sash: ThemeColor = ("#c0c0c0", "#4a4a4a")  # Resizable pane sash
    
    # === Special UI Colors ===
    warlock_panel: ThemeColor = ("#c5c5d5", "#2a2a3a")  # Warlock spell slots panel
    spell_row: ThemeColor = ("#e8e8e8", "#2b2b2b")  # Spell list row
    level_header: ThemeColor = ("#d5d5d5", "#2a2a2a")  # Level section header
    description_bg: ThemeColor = ("#d9d9d9", "#2b2b2b")  # Spell description background
    
    # === Context Menu (tk widget - not theme-aware, needs manual switching) ===
    menu_bg_light: str = "#f0f0f0"
    menu_fg_light: str = "#1a1a1a"
    menu_bg_dark: str = "#2b2b2b"
    menu_fg_dark: str = "#ffffff"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ThemeColors":
        """Create from dictionary."""
        # Convert lists back to tuples
        converted = {}
        for key, value in data.items():
            if isinstance(value, list) and len(value) == 2:
                converted[key] = tuple(value)
            else:
                converted[key] = value
        
        # Only use known fields
        known_fields = set(f.name for f in cls.__dataclass_fields__.values())
        filtered = {k: v for k, v in converted.items() if k in known_fields}
        return cls(**filtered)


def _create_default_theme() -> ThemeColors:
    """Create the default Dark theme."""
    return ThemeColors()


def _create_blue_theme() -> ThemeColors:
    """Create a blue-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#3b82f6", "#2563eb")  # Bright blue
    colors.accent_hover = ("#2563eb", "#1d4ed8")
    colors.button_normal = ("#bfdbfe", "#1e40af")  # Blue tones
    colors.button_hover = ("#93c5fd", "#1e3a8a")
    return colors


def _create_green_theme() -> ThemeColors:
    """Create a green-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#10b981", "#059669")  # Emerald green
    colors.accent_hover = ("#059669", "#047857")
    colors.button_normal = ("#d1fae5", "#064e3b")
    colors.button_hover = ("#a7f3d0", "#065f46")
    return colors


def _create_purple_theme() -> ThemeColors:
    """Create a purple-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#8b5cf6", "#7c3aed")  # Purple
    colors.accent_hover = ("#7c3aed", "#6d28d9")
    colors.button_normal = ("#e9d5ff", "#581c87")
    colors.button_hover = ("#ddd6fe", "#6b21a8")
    return colors


def _create_red_theme() -> ThemeColors:
    """Create a red-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#ef4444", "#dc2626")  # Red
    colors.accent_hover = ("#dc2626", "#b91c1c")
    colors.button_normal = ("#fecaca", "#991b1b")
    colors.button_hover = ("#fca5a5", "#7f1d1d")
    return colors


def _create_orange_theme() -> ThemeColors:
    """Create an orange-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#f97316", "#ea580c")  # Orange
    colors.accent_hover = ("#ea580c", "#c2410c")
    colors.button_normal = ("#fed7aa", "#9a3412")
    colors.button_hover = ("#fdba74", "#7c2d12")
    return colors


def _create_amber_theme() -> ThemeColors:
    """Create an amber/gold-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#f59e0b", "#d97706")  # Amber
    colors.accent_hover = ("#d97706", "#b45309")
    colors.button_normal = ("#fde68a", "#78350f")
    colors.button_hover = ("#fcd34d", "#92400e")
    return colors


# Theme presets dictionary
THEME_PRESETS: Dict[str, Callable[[], ThemeColors]] = {
    "default": _create_default_theme,  # Dark theme (default)
    "blue": _create_blue_theme,
    "green": _create_green_theme,
    "purple": _create_purple_theme,
    "red": _create_red_theme,
    "orange": _create_orange_theme,
    "amber": _create_amber_theme,
}


def _create_midnight_blue_theme() -> ThemeColors:
    """Deep midnight blue theme suited for late-night use."""
    colors = ThemeColors()
    colors.bg_primary = ("#071124", "#071124")
    colors.bg_secondary = ("#071a2a", "#071a2a")
    colors.accent_primary = ("#60a5fa", "#1e40af")
    colors.accent_hover = ("#3b82f6", "#2563eb")
    colors.text_primary = ("#dbeafe", "#e6f2ff")
    colors.button_normal = ("#0b3a66", "#0b3a66")
    colors.button_hover = ("#134e8a", "#134e8a")
    return colors


def _create_sepia_theme() -> ThemeColors:
    """Warm sepia-toned theme."""
    colors = ThemeColors()
    colors.bg_primary = ("#f4efe6", "#2b1f13")
    colors.bg_secondary = ("#efe6d6", "#382a1b")
    colors.accent_primary = ("#b07b3f", "#7a4f2a")
    colors.accent_hover = ("#8f5f2a", "#6b4020")
    colors.text_primary = ("#2b1f13", "#f4efe6")
    colors.button_normal = ("#d6b48a", "#6b4020")
    colors.button_hover = ("#c49f6f", "#7a4f2a")
    return colors


def _create_greyscale_theme() -> ThemeColors:
    """Minimal greyscale theme."""
    colors = ThemeColors()
    colors.bg_primary = ("#ffffff", "#0f0f0f")
    colors.bg_secondary = ("#f0f0f0", "#1a1a1a")
    colors.accent_primary = ("#6b7280", "#9ca3af")
    colors.accent_hover = ("#9ca3af", "#d1d5db")
    colors.text_primary = ("#0b0b0b", "#ffffff")
    colors.button_normal = ("#d1d5db", "#2b2b2b")
    colors.button_hover = ("#9ca3af", "#3a3a3a")
    return colors


# Add the new presets to the presets map
THEME_PRESETS.update({
    "midnight": _create_midnight_blue_theme,
    "sepia": _create_sepia_theme,
    "greyscale": _create_greyscale_theme,
})


def _create_solarized_theme() -> ThemeColors:
    """Solarized-like theme (soft contrast)."""
    colors = ThemeColors()
    colors.bg_primary = ("#fdf6e3", "#002b36")
    colors.bg_secondary = ("#eee8d5", "#073642")
    colors.accent_primary = ("#268bd2", "#268bd2")
    colors.accent_hover = ("#2aa198", "#2aa198")
    colors.text_primary = ("#073642", "#839496")
    colors.button_normal = ("#eee8d5", "#073642")
    colors.button_hover = ("#e6dec4", "#0b3946")
    return colors


def _create_forest_theme() -> ThemeColors:
    """Green forest theme."""
    colors = ThemeColors()
    colors.bg_primary = ("#f3fbf3", "#071806")
    colors.bg_secondary = ("#e6f7e6", "#0b2a0b")
    colors.accent_primary = ("#15803d", "#10b981")
    colors.accent_hover = ("#16a34a", "#059669")
    colors.text_primary = ("#072b19", "#dfffe6")
    colors.button_normal = ("#c7f0d0", "#054d2b")
    colors.button_hover = ("#9fe1ac", "#06663a")
    return colors


def _create_monokai_theme() -> ThemeColors:
    """Monokai-inspired dark theme."""
    colors = ThemeColors()
    colors.bg_primary = ("#272822", "#272822")
    colors.bg_secondary = ("#3e3d32", "#3e3d32")
    colors.accent_primary = ("#f92672", "#fd971f")
    colors.accent_hover = ("#fd971f", "#66d9ef")
    colors.text_primary = ("#f8f8f2", "#f8f8f2")
    colors.button_normal = ("#5a5a50", "#5a5a50")
    colors.button_hover = ("#75715e", "#75715e")
    return colors


THEME_PRESETS.update({
    "solarized": _create_solarized_theme,
    "forest": _create_forest_theme,
    "monokai": _create_monokai_theme,
})

# Simplify presets: only keep the default preset. All other preset UI has been removed.
THEME_PRESETS = {"default": _create_default_theme}


class ThemeManager:
    """Manages application themes and provides color access."""
    
    CUSTOM_THEME_FILE = "custom_theme.json"
    
    def __init__(self):
        self._preset_colors: Dict[str, ThemeColors] = {}
        self._custom_colors: Optional[ThemeColors] = None
        self._current_theme_name = "default"
        self._listeners = []
        # Load custom theme if it exists
        self.load_custom_theme()

    def initialize_custom_with_dark_defaults(self):
        """Initialize the custom theme so that both light and dark values default to the dark palette.

        This makes the "Custom" option start from the current dark values so users editing
        a custom theme see the dark-mode colors prefilled.
        """
        # Use the default preset as the base if available
        base = self._get_preset_colors("default")
        init_values = {}
        for field_name in ThemeColors.__dataclass_fields__.keys():
            val = getattr(base, field_name)
            # If it's a tuple (light,dark) use dark for both entries
            if isinstance(val, tuple) and len(val) == 2:
                init_values[field_name] = (val[1], val[1])
            else:
                init_values[field_name] = val

        self._custom_colors = ThemeColors.from_dict(init_values)
        self.save_custom_theme()
    
    def _get_preset_colors(self, theme_name: str) -> ThemeColors:
        """Get or create preset theme colors."""
        if theme_name not in self._preset_colors:
            if theme_name in THEME_PRESETS:
                self._preset_colors[theme_name] = THEME_PRESETS[theme_name]()
            else:
                # Fallback to default
                self._preset_colors[theme_name] = THEME_PRESETS["default"]()
        return self._preset_colors[theme_name]
    
    @property
    def colors(self) -> ThemeColors:
        """Get current theme colors."""
        if self._current_theme_name == "custom":
            # Use custom theme - default to dark colors if not initialized
            if self._custom_colors is None:
                # Initialize with dark theme colors
                self._custom_colors = ThemeColors()
            return self._custom_colors
        else:
            return self._get_preset_colors(self._current_theme_name)
    
    @property
    def current_theme_name(self) -> str:
        """Get the current theme name."""
        return self._current_theme_name
    
    def set_theme(self, theme_name: str):
        """Set the active theme by name."""
        if theme_name not in THEME_PRESETS and theme_name != "custom":
            theme_name = "default"  # Fallback
        self._current_theme_name = theme_name
        self._notify_listeners()
    
    def get_available_presets(self) -> List[str]:
        """Get list of available theme preset names."""
        return list(THEME_PRESETS.keys())
    
    def add_listener(self, callback):
        """Add a listener to be notified when theme changes."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback):
        """Remove a listener to prevent memory leaks when views are destroyed."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    def _notify_listeners(self):
        """Notify all listeners of theme change."""
        for listener in self._listeners:
            try:
                listener()
            except Exception as e:
                print(f"Error notifying theme listener: {e}")
    
    def get_color(self, color_name: str) -> ThemeColor:
        """Get a specific color by name."""
        return getattr(self.colors, color_name, ("#000000", "#ffffff"))
    
    def get_current_color(self, color_name: str) -> str:
        """Get the current color value based on appearance mode."""
        color = self.get_color(color_name)
        mode = ctk.get_appearance_mode().lower()
        if mode == "light":
            return color[0]
        else:
            return color[1]
    
    def get_text_secondary(self) -> str:
        """Get secondary text color (theme-aware)."""
        return self.get_current_color("text_secondary")
    
    def get_text_disabled(self) -> str:
        """Get disabled text color (theme-aware)."""
        return self.get_current_color("text_disabled")
    
    def load_custom_theme(self) -> bool:
        """Load custom theme from file. Returns True if loaded."""
        if not os.path.exists(self.CUSTOM_THEME_FILE):
            return False
        
        try:
            with open(self.CUSTOM_THEME_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._custom_colors = ThemeColors.from_dict(data)
            return True
        except Exception as e:
            print(f"Error loading custom theme: {e}")
            return False
    
    def save_custom_theme(self, colors: Optional[ThemeColors] = None) -> bool:
        """Save custom theme to file."""
        if colors:
            self._custom_colors = colors
        
        if not self._custom_colors:
            return False
        
        try:
            with open(self.CUSTOM_THEME_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._custom_colors.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving custom theme: {e}")
            return False
    
    def enable_custom_theme(self, enabled: bool = True):
        """Enable or disable custom theme. (Legacy method for compatibility)"""
        if enabled:
            self.set_theme("custom")
            if self._custom_colors is None:
                # Initialize custom colors with dark theme defaults (copy dark values into both slots)
                self.initialize_custom_with_dark_defaults()
        else:
            self.set_theme("default")
    
    def reset_custom_theme(self):
        """Reset custom theme to dark theme defaults."""
        self._custom_colors = ThemeColors()  # Dark theme defaults
        self.save_custom_theme()
        if self._current_theme_name == "custom":
            self._notify_listeners()
    
    def update_custom_color(self, color_name: str, light_value: str, dark_value: str):
        """Update a specific color in the custom theme."""
        if self._custom_colors is None:
            # Initialize with dark theme defaults
            self._custom_colors = ThemeColors()
        
        if hasattr(self._custom_colors, color_name):
            setattr(self._custom_colors, color_name, (light_value, dark_value))
            self.save_custom_theme()
            if self._current_theme_name == "custom":
                self._notify_listeners()
    
    def get_level_color(self, level: int) -> ThemeColor:
        """Get the color for a spell level."""
        level_colors = {
            0: self.colors.level_cantrip,
            1: self.colors.level_1,
            2: self.colors.level_2,
            3: self.colors.level_3,
            4: self.colors.level_4,
            5: self.colors.level_5,
            6: self.colors.level_6,
            7: self.colors.level_7,
            8: self.colors.level_8,
            9: self.colors.level_9,
        }
        return level_colors.get(level, self.colors.bg_secondary)
    
    def get_menu_colors(self) -> Tuple[str, str, str, str]:
        """Get context menu colors: (bg, fg, active_bg, active_fg)."""
        mode = ctk.get_appearance_mode().lower()
        if mode == "light":
            return (self.colors.menu_bg_light, self.colors.menu_fg_light, 
                    self.colors.accent_primary[0], "#ffffff")
        else:
            return (self.colors.menu_bg_dark, self.colors.menu_fg_dark,
                    self.colors.accent_primary[1], "#ffffff")


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
        _theme_manager.load_custom_theme()
    return _theme_manager


def get_colors() -> ThemeColors:
    """Convenience function to get current theme colors."""
    return get_theme_manager().colors


# Color name groups for the theme editor UI
COLOR_GROUPS = {
    "Text": [
        ("text_primary", "Primary Text"),
        ("text_secondary", "Secondary Text"),
        ("text_disabled", "Disabled Text"),
    ],
    "Backgrounds": [
        ("bg_primary", "Primary Background"),
        ("bg_secondary", "Secondary Background"),
        ("bg_input", "Input Fields"),
    ],
    "Accents": [
        ("accent_primary", "Primary Accent"),
        ("accent_hover", "Accent Hover"),
    ],
    "Buttons": [
        ("button_normal", "Normal Button"),
        ("button_hover", "Button Hover"),
        ("button_danger", "Danger Button"),
        ("button_success", "Success Button"),
    ],
    "Spell Levels": [
        ("level_cantrip", "Cantrip"),
        ("level_1", "Level 1"),
        ("level_2", "Level 2"),
        ("level_3", "Level 3"),
        ("level_4", "Level 4"),
        ("level_5", "Level 5"),
        ("level_6", "Level 6"),
        ("level_7", "Level 7"),
        ("level_8", "Level 8"),
        ("level_9", "Level 9"),
    ],
}

