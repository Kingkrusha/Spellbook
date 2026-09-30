"""
Theme and color management for D&D Spellbook Application.
Centralizes all color definitions for easy customization.
"""

import customtkinter as ctk
from dataclasses import dataclass, field, asdict
from typing import Tuple, Dict, Optional, List, Callable
import copy
import json
import os
import uuid

from atomic_io import atomic_write_json
from paths import user_data_path


# Type alias for theme-aware colors: (light_mode_color, dark_mode_color)
ThemeColor = Tuple[str, str]


class ThemeStr(str):
    """A colour string that remembers which theme role it came from.

    ``ThemeManager.get_current_color("bg_secondary")`` returns one of these.
    CustomTkinter stores colour strings untouched, so ``widget.cget("fg_color")``
    still carries the role - which is what lets ``ui/restyle.py`` recolour a
    whole window (or one character sheet) when the theme changes, without every
    view having to keep its own list of widgets to repaint.

    ``original`` is set on colours the user applied by hand to one widget: it
    holds whatever the widget had before, so removing the override restores it.
    """
    role: Optional[str] = None
    original = None


def tag_color(value, role: Optional[str], original=None) -> "ThemeStr":
    s = ThemeStr(value)
    s.role = role
    s.original = original
    return s


class ThemeTuple(tuple):
    """A (light, dark) colour pair that remembers its theme role.

    Used for CustomTkinter's own defaults (see ``ui/restyle.py``): CTk resolves
    the pair for the current appearance mode by itself, so widgets holding one
    follow light/dark switches without any help.
    """
    role: Optional[str] = None
    original = None


def tag_pair(pair, role: Optional[str], original=None) -> "ThemeTuple":
    t = ThemeTuple(pair)
    t.role = role
    t.original = original
    return t


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
    text_warning: ThemeColor = ("#b45309", "#fb923c")  # Encumbered/reduced-speed warning text
    text_label: ThemeColor = ("#8a5a12", "#e3b666")  # Field labels on objects ("Casting Time:", "Multiattack.") - distinct from body text and links
    
    # === Background Colors ===
    bg_primary: ThemeColor = ("#f5f5f5", "#1a1a1a")  # Main background
    bg_secondary: ThemeColor = ("#e8e8e8", "#2b2b2b")  # Cards, panels
    bg_tertiary: ThemeColor = ("#d9d9d9", "#3a3a3a")  # Nested elements
    bg_input: ThemeColor = ("#ffffff", "#343638")  # Input fields
    
    # === Accent Colors ===
    accent_primary: ThemeColor = ("#3b8ed0", "#1f538d")  # Primary accent (selected items, active tabs)
    accent_hover: ThemeColor = ("#2d7fc4", "#2a6eb0")  # Hover state for accent
    spell_link: ThemeColor = ("#67bed9", "#67bed9")  # Hyperlink text color (spells, feats, equipment, and other object links)
    
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
        theme = cls(**filtered)
        if "text_label" not in filtered and "accent_primary" in filtered:
            # A theme saved before field labels had their own colour: pick one that
            # contrasts with its accent and link colours instead of a fixed default.
            theme.text_label = derive_label_color(theme)
        return theme


def _hex_to_hls(value: str):
    import colorsys
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(r, g, b)


def _hls_to_hex(h: float, l: float, s: float) -> str:
    import colorsys
    r, g, b = colorsys.hls_to_rgb(h % 1.0, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def derive_label_color(colors: "ThemeColors") -> ThemeColor:
    """A label colour for a palette that has none: the hue opposite the accent (so it
    stands apart from both body text and the accent), light enough for dark
    backgrounds and dark enough for light ones."""
    out = []
    for i, lightness in ((0, 0.26), (1, 0.74)):
        try:
            hue, _l, _s = _hex_to_hls(colors.accent_primary[i])
            out.append(_hls_to_hex(hue + 0.5, lightness, 0.55))
        except Exception:
            out.append(("#8a5a12", "#e3b666")[i])
    return (out[0], out[1])


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
    colors.spell_link = ("#0891b2", "#22d3ee")  # Teal-cyan - distinct from the blue accent
    colors.text_label = ("#7f4a05", "#f0b45a")  # Field labels ("Casting Time:")
    return colors


def _create_green_theme() -> ThemeColors:
    """Create a green-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#10b981", "#059669")  # Emerald green
    colors.accent_hover = ("#059669", "#047857")
    colors.button_normal = ("#d1fae5", "#064e3b")
    colors.button_hover = ("#a7f3d0", "#065f46")
    colors.spell_link = ("#0284c7", "#38bdf8")  # Sky blue - pops against the green accent
    colors.text_label = ("#8a4a1c", "#f0a878")  # Field labels ("Casting Time:")
    return colors


def _create_purple_theme() -> ThemeColors:
    """Create a purple-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#8b5cf6", "#7c3aed")  # Purple
    colors.accent_hover = ("#7c3aed", "#6d28d9")
    colors.button_normal = ("#e9d5ff", "#581c87")
    colors.button_hover = ("#ddd6fe", "#6b21a8")
    colors.spell_link = ("#0369a1", "#7dd3fc")  # Sky blue - distinct from the purple accent
    colors.text_label = ("#8a5a12", "#f2c266")  # Field labels ("Casting Time:")
    return colors


def _create_red_theme() -> ThemeColors:
    """Create a red-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#ef4444", "#dc2626")  # Red
    colors.accent_hover = ("#dc2626", "#b91c1c")
    colors.button_normal = ("#fecaca", "#991b1b")
    colors.button_hover = ("#fca5a5", "#7f1d1d")
    colors.spell_link = ("#1d4ed8", "#60a5fa")  # Blue - distinct from the red accent
    colors.text_label = ("#7a5a0a", "#e8c25a")  # Field labels ("Casting Time:")
    return colors


def _create_orange_theme() -> ThemeColors:
    """Create an orange-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#f97316", "#ea580c")  # Orange
    colors.accent_hover = ("#ea580c", "#c2410c")
    colors.button_normal = ("#fed7aa", "#9a3412")
    colors.button_hover = ("#fdba74", "#7c2d12")
    colors.spell_link = ("#1d4ed8", "#7dd3fc")  # Blue - distinct from the orange accent
    colors.text_label = ("#7c3a9a", "#d8a0f0")  # Field labels ("Casting Time:")
    return colors


def _create_amber_theme() -> ThemeColors:
    """Create an amber/gold-tinted theme."""
    colors = ThemeColors()
    colors.accent_primary = ("#f59e0b", "#d97706")  # Amber
    colors.accent_hover = ("#d97706", "#b45309")
    colors.button_normal = ("#fde68a", "#78350f")
    colors.button_hover = ("#fcd34d", "#92400e")
    colors.spell_link = ("#1e40af", "#93c5fd")  # Blue - distinct from the amber accent
    colors.text_label = ("#8a2a5a", "#f0a0c8")  # Field labels ("Casting Time:")
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
    colors.spell_link = ("#fbbf24", "#fbbf24")  # Amber - warm contrast against the all-blue palette
    colors.text_label = ("#c9a0f5", "#c9a0f5")  # Field labels ("Casting Time:")
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
    colors.spell_link = ("#2563eb", "#7dd3fc")  # Cool blue - stands out against the warm sepia tones
    colors.text_label = ("#8a2a1a", "#e89a70")  # Field labels ("Casting Time:")
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
    colors.spell_link = ("#2563eb", "#60a5fa")  # The one spot of color in an otherwise monochrome theme
    colors.text_label = ("#8a5a12", "#e0b060")  # Field labels ("Casting Time:")
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
    colors.spell_link = ("#6c71c4", "#6c71c4")  # Solarized violet - distinct from the cyan-blue accent
    colors.text_label = ("#7a5c00", "#b58900")  # Field labels ("Casting Time:")
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
    colors.spell_link = ("#b45309", "#fbbf24")  # Amber - pops against the all-green palette
    colors.text_label = ("#8a3a5a", "#e89ab8")  # Field labels ("Casting Time:")
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
    colors.spell_link = ("#66d9ef", "#66d9ef")  # Monokai's signature cyan
    colors.text_label = ("#a6e22e", "#a6e22e")  # Field labels ("Casting Time:")
    return colors


THEME_PRESETS.update({
    "solarized": _create_solarized_theme,
    "forest": _create_forest_theme,
    "monokai": _create_monokai_theme,
})


def _palette(light: Dict[str, str], dark: Dict[str, str], **extra: ThemeColor) -> ThemeColors:
    """Build a full ThemeColors from a compact description of each appearance mode.

    Each dict supplies: bg, card, tert, input, text, muted, accent, accent_hover,
    button, button_hover, border, link. Everything else in the palette (tab bar,
    scrollbars, list rows, ...) is derived from those, and any field can be
    forced through ``extra``.
    """
    def pair(key: str) -> ThemeColor:
        return (light[key], dark[key])

    colors = ThemeColors()
    colors.text_primary = pair("text")
    colors.text_secondary = pair("muted")
    colors.text_disabled = (light.get("disabled", light["muted"]), dark.get("disabled", dark["muted"]))
    colors.text_on_accent = (light.get("on_accent", "#ffffff"), dark.get("on_accent", "#ffffff"))
    colors.bg_primary = pair("bg")
    colors.bg_secondary = pair("card")
    colors.bg_tertiary = pair("tert")
    colors.bg_input = pair("input")
    colors.accent_primary = pair("accent")
    colors.accent_hover = pair("accent_hover")
    colors.spell_link = pair("link")
    colors.text_label = pair("label") if "label" in light and "label" in dark else derive_label_color(colors)
    colors.button_normal = pair("button")
    colors.button_hover = pair("button_hover")
    colors.tab_bar = pair("bg")
    colors.separator = pair("border")
    colors.border = pair("border")
    colors.scrollbar = pair("button")
    colors.scrollbar_thumb = pair("button_hover")
    colors.pane_sash = pair("button")
    colors.warlock_panel = pair("tert")
    colors.spell_row = pair("card")
    colors.level_header = pair("tert")
    colors.description_bg = pair("tert")
    for name, value in extra.items():
        setattr(colors, name, value)
    return colors


def _create_nord_theme() -> ThemeColors:
    """Arctic, north-bluish palette."""
    return _palette(
        light=dict(bg="#eceff4", card="#e5e9f0", tert="#d8dee9", input="#ffffff", text="#2e3440",
                   muted="#4c566a", accent="#5e81ac", accent_hover="#81a1c1", button="#d8dee9",
                   button_hover="#c5cddb", border="#c2cad8", link="#5e81ac", label="#86561a"),
        dark=dict(bg="#2e3440", card="#3b4252", tert="#434c5e", input="#3b4252", text="#eceff4",
                  muted="#b6bfd0", accent="#5e81ac", accent_hover="#81a1c1", button="#4c566a",
                  button_hover="#5c6a82", border="#4c566a", link="#88c0d0", label="#ebcb8b"),
    )


def _create_dracula_theme() -> ThemeColors:
    """Purple-and-pink dark palette."""
    return _palette(
        light=dict(bg="#f8f8f2", card="#eeeef4", tert="#e0e0ea", input="#ffffff", text="#282a36",
                   muted="#5b5f7a", accent="#8b5fd6", accent_hover="#7546c4", button="#dcdcea",
                   button_hover="#c9c9dc", border="#c9c9dc", link="#0e8aa8", label="#a05a10"),
        dark=dict(bg="#282a36", card="#343746", tert="#44475a", input="#343746", text="#f8f8f2",
                  muted="#b7b9d0", accent="#bd93f9", accent_hover="#a77bf0", button="#44475a",
                  button_hover="#565a72", border="#44475a", link="#8be9fd", label="#ffb86c", on_accent="#282a36"),
    )


def _create_rose_theme() -> ThemeColors:
    """Soft rose and blush."""
    return _palette(
        light=dict(bg="#fff5f7", card="#fde8ee", tert="#f8d7e0", input="#ffffff", text="#4a1f2e",
                   muted="#8a4d63", accent="#e11d68", accent_hover="#be1857", button="#f8d7e0",
                   button_hover="#f2c0cf", border="#f0c4d2", link="#7c3aed", label="#8a5a10"),
        dark=dict(bg="#25121a", card="#341a25", tert="#45222f", input="#341a25", text="#ffe9ef",
                  muted="#d3a3b4", accent="#f43f7e", accent_hover="#e11d68", button="#5a2c3d",
                  button_hover="#733a4f", border="#5a2c3d", link="#c4b5fd", label="#f5c26b"),
    )


def _create_ocean_theme() -> ThemeColors:
    """Deep-sea teal."""
    return _palette(
        light=dict(bg="#f0fafb", card="#dff3f5", tert="#c9e8ec", input="#ffffff", text="#0b3038",
                   muted="#3d6a74", accent="#0e8a9a", accent_hover="#0a6f7d", button="#c9e8ec",
                   button_hover="#b0dce2", border="#b0dce2", link="#c2410c", label="#6f5a0a"),
        dark=dict(bg="#061c22", card="#0b2b33", tert="#11404b", input="#0b2b33", text="#e0f7fa",
                  muted="#93c5cd", accent="#14a3b5", accent_hover="#22bfd2", button="#154956",
                  button_hover="#1c6072", border="#154956", link="#fdba74", label="#e8d070"),
    )


def _create_crimson_theme() -> ThemeColors:
    """Blood Moon: near-black with deep reds."""
    return _palette(
        light=dict(bg="#faf3f2", card="#f3e3e1", tert="#e8d0cd", input="#ffffff", text="#2a0f0e",
                   muted="#6e3b38", accent="#b91c1c", accent_hover="#991b1b", button="#e8d0cd",
                   button_hover="#dbb9b5", border="#dfc3bf", link="#1d4ed8", label="#705408"),
        dark=dict(bg="#140708", card="#220c0d", tert="#331214", input="#220c0d", text="#f8e4e2",
                  muted="#c99a97", accent="#b91c1c", accent_hover="#dc2626", button="#4a1a1c",
                  button_hover="#672427", border="#4a1a1c", link="#fca5a5", label="#e8c46a"),
    )


def _create_arcane_theme() -> ThemeColors:
    """Wizard's study: deep violet with gold."""
    return _palette(
        light=dict(bg="#f7f4fc", card="#ece5f7", tert="#ddd1f0", input="#ffffff", text="#241542",
                   muted="#5e4a86", accent="#6d28d9", accent_hover="#5b21b6", button="#ddd1f0",
                   button_hover="#cbbae6", border="#d0c2ea", link="#b45309", label="#8a3a7a"),
        dark=dict(bg="#120a24", card="#1c1236", tert="#2a1c4d", input="#1c1236", text="#f1e9ff",
                  muted="#b7a5dc", accent="#7c3aed", accent_hover="#9155f5", button="#3a2766",
                  button_hover="#4e3585", border="#3a2766", link="#fbbf24", label="#f0a8e0"),
    )


def _create_ember_theme() -> ThemeColors:
    """Charcoal with glowing orange."""
    return _palette(
        light=dict(bg="#faf6f1", card="#f1e8de", tert="#e5d7c8", input="#ffffff", text="#26190f",
                   muted="#6b5443", accent="#d9480f", accent_hover="#b83c0a", button="#e5d7c8",
                   button_hover="#d6c3ae", border="#dccbb8", link="#0369a1", label="#6f5405"),
        dark=dict(bg="#151210", card="#221d19", tert="#332b25", input="#221d19", text="#f5ece4",
                  muted="#bfab9a", accent="#e8590c", accent_hover="#fb7a2c", button="#40342b",
                  button_hover="#5a4a3d", border="#40342b", link="#7dd3fc", label="#f0c850"),
    )


def _create_high_contrast_theme() -> ThemeColors:
    """Maximum legibility: pure black/white with a bold yellow accent."""
    return _palette(
        light=dict(bg="#ffffff", card="#f2f2f2", tert="#e0e0e0", input="#ffffff", text="#000000",
                   muted="#1f1f1f", disabled="#4a4a4a", accent="#0033cc", accent_hover="#002299",
                   button="#d6d6d6", button_hover="#bdbdbd", border="#000000", link="#0033cc", label="#7a3d00"),
        dark=dict(bg="#000000", card="#0d0d0d", tert="#1a1a1a", input="#000000", text="#ffffff",
                  muted="#e6e6e6", disabled="#a0a0a0", accent="#ffd60a", accent_hover="#ffe066",
                  button="#2b2b2b", button_hover="#404040", border="#ffffff", link="#66d9ff", label="#ffd166",
                  on_accent="#000000"),
    )


def _create_lavender_theme() -> ThemeColors:
    """Gentle lavender and cream."""
    return _palette(
        light=dict(bg="#faf8ff", card="#f0ebfa", tert="#e3dbf5", input="#ffffff", text="#2b2340",
                   muted="#6b6088", accent="#8b7fd4", accent_hover="#7568c4", button="#e3dbf5",
                   button_hover="#d3c8ee", border="#d8cff0", link="#0e7490", label="#9a5a2a"),
        dark=dict(bg="#1d1a2b", card="#282440", tert="#36305a", input="#282440", text="#eeeafc",
                  muted="#b5aed6", accent="#8b7fd4", accent_hover="#a094e6", button="#3f3868",
                  button_hover="#524a83", border="#3f3868", link="#7dd3fc", label="#f0b98a"),
    )


def _create_mint_theme() -> ThemeColors:
    """Fresh mint and slate."""
    return _palette(
        light=dict(bg="#f3fbf8", card="#e2f5ee", tert="#cdeadf", input="#ffffff", text="#12372a",
                   muted="#466b5c", accent="#0d9488", accent_hover="#0b7a70", button="#cdeadf",
                   button_hover="#b5ddce", border="#bfe0d2", link="#7c3aed", label="#834a1a"),
        dark=dict(bg="#0f1f1b", card="#162b26", tert="#1f3d36", input="#162b26", text="#e6fbf3",
                  muted="#9cc7b9", accent="#14b8a6", accent_hover="#2dd4bf", button="#24473f",
                  button_hover="#31615a", border="#24473f", link="#c4b5fd", label="#f0b87a", on_accent="#04211c"),
    )


THEME_PRESETS.update({
    "nord": _create_nord_theme,
    "dracula": _create_dracula_theme,
    "rose": _create_rose_theme,
    "ocean": _create_ocean_theme,
    "crimson": _create_crimson_theme,
    "arcane": _create_arcane_theme,
    "ember": _create_ember_theme,
    "lavender": _create_lavender_theme,
    "mint": _create_mint_theme,
    "high_contrast": _create_high_contrast_theme,
})

# Human-readable names for the theme selector in Settings. Order here is the
# order shown in the dropdown; keys must exist in THEME_PRESETS.
PRESET_DISPLAY_NAMES: Dict[str, str] = {
    "default": "Default",
    "blue": "Blue",
    "green": "Green",
    "purple": "Purple",
    "red": "Red",
    "orange": "Orange",
    "amber": "Amber",
    "midnight": "Midnight Blue",
    "sepia": "Sepia",
    "greyscale": "Greyscale",
    "solarized": "Solarized",
    "forest": "Forest",
    "monokai": "Monokai",
    "nord": "Nord",
    "dracula": "Dracula",
    "rose": "Rosé",
    "ocean": "Ocean",
    "crimson": "Blood Moon",
    "arcane": "Arcane Study",
    "ember": "Ember",
    "lavender": "Lavender",
    "mint": "Mint",
    "high_contrast": "High Contrast",
}

# Custom themes are stored under keys of the form "custom:<id>".
CUSTOM_PREFIX = "custom:"


def is_custom_key(key: str) -> bool:
    return key.startswith(CUSTOM_PREFIX)


class ThemeManager:
    """Manages application themes and provides color access.

    A theme is either a built-in preset (key like ``"nord"``) or one of the
    user's custom themes (key ``"custom:<id>"``). Custom themes are stored in
    ``custom_themes.json``; the single ``custom_theme.json`` of older versions
    is imported as "My Custom Theme".
    """

    CUSTOM_THEMES_FILE = "custom_themes.json"
    LEGACY_CUSTOM_FILE = "custom_theme.json"

    def __init__(self):
        # Resolve the custom-theme files to the writable user-data dir so it works
        # from a read-only macOS .app bundle as well as a portable Windows build.
        self.custom_themes_path = user_data_path(self.CUSTOM_THEMES_FILE)
        self.legacy_custom_path = user_data_path(self.LEGACY_CUSTOM_FILE)
        self._preset_colors: Dict[str, ThemeColors] = {}
        self._custom: Dict[str, dict] = {}       # id -> {"name": str, "colors": ThemeColors}
        self._custom_order: List[str] = []
        self._current_theme_name = "default"
        self._listeners = []
        self.load_custom_themes()

    # -- theme catalogue ----------------------------------------------------

    def list_themes(self) -> List[Tuple[str, str, bool]]:
        """(key, display name, is_custom) for every selectable theme."""
        themes = [(key, PRESET_DISPLAY_NAMES.get(key, key.title()), False) for key in THEME_PRESETS]
        for cid in self._custom_order:
            themes.append((CUSTOM_PREFIX + cid, self._custom[cid]["name"], True))
        return themes

    def display_name(self, key: str) -> str:
        if is_custom_key(key):
            entry = self._custom.get(key[len(CUSTOM_PREFIX):])
            return entry["name"] if entry else "Default"
        return PRESET_DISPLAY_NAMES.get(key, "Default")

    def normalize_key(self, key: Optional[str]) -> str:
        """Map any stored theme name to one that exists (legacy "custom" included)."""
        key = key or "default"
        if key == "custom":
            return CUSTOM_PREFIX + self._custom_order[0] if self._custom_order else "default"
        if is_custom_key(key):
            return key if key[len(CUSTOM_PREFIX):] in self._custom else "default"
        return key if key in THEME_PRESETS else "default"

    def _get_preset_colors(self, theme_name: str) -> ThemeColors:
        """Get or create preset theme colors."""
        if theme_name not in self._preset_colors:
            factory = THEME_PRESETS.get(theme_name, THEME_PRESETS["default"])
            self._preset_colors[theme_name] = factory()
        return self._preset_colors[theme_name]

    def get_theme_colors(self, key: str) -> ThemeColors:
        """The ThemeColors of any theme key (falls back to the default theme)."""
        key = self.normalize_key(key)
        if is_custom_key(key):
            return self._custom[key[len(CUSTOM_PREFIX):]]["colors"]
        return self._get_preset_colors(key)

    @property
    def colors(self) -> ThemeColors:
        """Get current theme colors."""
        return self.get_theme_colors(self._current_theme_name)

    @property
    def current_theme_name(self) -> str:
        """Get the current theme key."""
        return self._current_theme_name

    def is_current_custom(self) -> bool:
        return is_custom_key(self._current_theme_name)

    def set_theme(self, theme_name: str, notify: bool = True):
        """Set the active theme by key."""
        self._current_theme_name = self.normalize_key(theme_name)
        if notify:
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

    def notify(self):
        """Tell every listener that colours changed (used by the theme editor)."""
        self._notify_listeners()

    def _notify_listeners(self):
        """Notify all listeners of theme change.

        A listener that is a method of a widget which is not on screen (a view in
        another tab, a closed dialog) is held back until that widget is next
        shown: recolouring what nobody sees costs redraws, and the widget
        recolours itself the moment it appears."""
        for listener in list(self._listeners):
            owner = getattr(listener, "__self__", None)
            if owner is not None and hasattr(owner, "winfo_ismapped"):
                try:
                    if not owner.winfo_ismapped():
                        self._defer_listener(owner, listener)
                        continue
                except Exception:
                    pass
            try:
                listener()
            except Exception as e:
                print(f"Error notifying theme listener: {e}")

    def _defer_listener(self, owner, listener):
        pending = owner.__dict__.setdefault("_theme_pending", [])
        if listener not in pending:
            pending.append(listener)
        if owner.__dict__.get("_theme_map_bound"):
            return
        owner.__dict__["_theme_map_bound"] = True
        try:
            import tkinter
            tkinter.Misc.bind(owner, "<Map>", lambda e, o=owner: self._flush_listeners(o, e), add="+")
        except Exception:
            owner.__dict__["_theme_map_bound"] = False

    def _flush_listeners(self, owner, event=None):
        if event is not None and event.widget is not owner:
            return
        pending = owner.__dict__.get("_theme_pending") or []
        owner.__dict__["_theme_pending"] = []
        for listener in pending:
            if listener in self._listeners:
                try:
                    listener()
                except Exception as e:
                    print(f"Error notifying theme listener: {e}")

    # -- colour access ------------------------------------------------------

    def get_color(self, color_name: str) -> ThemeColor:
        """Get a specific color by name, as a (light, dark) pair."""
        return tag_pair(getattr(self.colors, color_name, ("#000000", "#ffffff")), color_name)

    def get_current_color(self, color_name: str) -> str:
        """Get the current color value based on appearance mode.

        The result is a :class:`ThemeStr` - a plain string that also remembers
        the role it was resolved from."""
        color = self.get_color(color_name)
        mode = ctk.get_appearance_mode().lower()
        return tag_color(color[0] if mode == "light" else color[1], color_name)

    def color_in(self, colors: ThemeColors, color_name: str, mode: Optional[str] = None) -> str:
        """A role's colour from an arbitrary palette, for the given (or current) mode."""
        color = getattr(colors, color_name, ("#000000", "#ffffff"))
        mode = (mode or ctk.get_appearance_mode()).lower()
        return color[0] if mode == "light" else color[1]

    def get_text_secondary(self) -> str:
        """Get secondary text color (theme-aware)."""
        return self.get_current_color("text_secondary")

    def get_text_disabled(self) -> str:
        """Get disabled text color (theme-aware)."""
        return self.get_current_color("text_disabled")

    def get_text_warning(self) -> str:
        """Get warning text color (theme-aware) - used for a moderate speed reduction."""
        return self.get_current_color("text_warning")

    # -- custom themes ------------------------------------------------------

    def load_custom_themes(self) -> bool:
        """Load the user's custom themes (importing the legacy single file once)."""
        self._custom.clear()
        self._custom_order.clear()
        if os.path.exists(self.custom_themes_path):
            try:
                with open(self.custom_themes_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry in data.get("themes", []):
                    cid = str(entry.get("id") or "").strip()
                    if not cid or cid in self._custom:
                        continue
                    self._custom[cid] = {
                        "name": str(entry.get("name") or "Custom Theme"),
                        "colors": ThemeColors.from_dict(entry.get("colors", {})),
                    }
                    self._custom_order.append(cid)
                return True
            except Exception as e:
                print(f"Error loading custom themes: {e}")
                return False
        return self._import_legacy_custom_theme()

    def _import_legacy_custom_theme(self) -> bool:
        """Bring in custom_theme.json from older versions, if it holds real edits."""
        if not os.path.exists(self.legacy_custom_path):
            return False
        try:
            with open(self.legacy_custom_path, "r", encoding="utf-8") as f:
                colors = ThemeColors.from_dict(json.load(f))
        except Exception as e:
            print(f"Error importing legacy custom theme: {e}")
            return False
        if colors.to_dict() == ThemeColors().to_dict():
            return False        # never customised: nothing worth keeping
        self._custom["legacy"] = {"name": "My Custom Theme", "colors": colors}
        self._custom_order.append("legacy")
        self.save_custom_themes()
        return True

    def save_custom_themes(self) -> bool:
        try:
            atomic_write_json(self.custom_themes_path, {
                "version": 2,
                "themes": [
                    {"id": cid, "name": self._custom[cid]["name"],
                     "colors": self._custom[cid]["colors"].to_dict()}
                    for cid in self._custom_order
                ],
            })
            return True
        except Exception as e:
            print(f"Error saving custom themes: {e}")
            return False

    def _unique_name(self, name: str, ignore_id: Optional[str] = None) -> str:
        taken = {e["name"].lower() for cid, e in self._custom.items() if cid != ignore_id}
        taken |= {n.lower() for n in PRESET_DISPLAY_NAMES.values()}
        name = (name or "Custom Theme").strip() or "Custom Theme"
        candidate, n = name, 2
        while candidate.lower() in taken:
            candidate = f"{name} {n}"
            n += 1
        return candidate

    def create_custom_theme(self, name: str, base_key: str = "default") -> str:
        """Create a custom theme as a copy of ``base_key``; returns its key."""
        cid = uuid.uuid4().hex[:8]
        base = self.get_theme_colors(base_key)
        self._custom[cid] = {
            "name": self._unique_name(name),
            "colors": ThemeColors.from_dict(copy.deepcopy(base.to_dict())),
        }
        self._custom_order.append(cid)
        self.save_custom_themes()
        return CUSTOM_PREFIX + cid

    def rename_custom_theme(self, key: str, name: str):
        cid = key[len(CUSTOM_PREFIX):] if is_custom_key(key) else key
        if cid in self._custom:
            self._custom[cid]["name"] = self._unique_name(name, ignore_id=cid)
            self.save_custom_themes()

    def delete_custom_theme(self, key: str):
        cid = key[len(CUSTOM_PREFIX):] if is_custom_key(key) else key
        if cid not in self._custom:
            return
        was_current = self._current_theme_name == CUSTOM_PREFIX + cid
        del self._custom[cid]
        self._custom_order.remove(cid)
        self.save_custom_themes()
        if was_current:
            self.set_theme("default")

    def set_custom_color(self, key: str, color_name: str, light: Optional[str] = None,
                         dark: Optional[str] = None, notify: bool = True, save: bool = True):
        """Change one colour role of a custom theme (only the modes given)."""
        cid = key[len(CUSTOM_PREFIX):] if is_custom_key(key) else key
        entry = self._custom.get(cid)
        if entry is None or color_name not in ThemeColors.__dataclass_fields__:
            return
        current = getattr(entry["colors"], color_name)
        if not isinstance(current, tuple):
            return
        setattr(entry["colors"], color_name,
                (light if light is not None else current[0], dark if dark is not None else current[1]))
        if save:
            self.save_custom_themes()
        if notify and self._current_theme_name == CUSTOM_PREFIX + cid:
            self._notify_listeners()

    def reset_custom_theme_colors(self, key: str, base_key: str = "default"):
        """Overwrite a custom theme's colours with those of another theme."""
        cid = key[len(CUSTOM_PREFIX):] if is_custom_key(key) else key
        if cid in self._custom:
            self._custom[cid]["colors"] = ThemeColors.from_dict(
                copy.deepcopy(self.get_theme_colors(base_key).to_dict()))
            self.save_custom_themes()
            if self._current_theme_name == CUSTOM_PREFIX + cid:
                self._notify_listeners()

    def export_theme(self, key: str) -> dict:
        return {"name": self.display_name(key),
                "colors": self.get_theme_colors(key).to_dict()}

    def import_theme(self, data: dict) -> Optional[str]:
        """Add a custom theme from an exported dict; returns its key."""
        if not isinstance(data, dict) or not isinstance(data.get("colors"), dict):
            return None
        cid = uuid.uuid4().hex[:8]
        self._custom[cid] = {"name": self._unique_name(str(data.get("name") or "Imported Theme")),
                             "colors": ThemeColors.from_dict(data["colors"])}
        self._custom_order.append(cid)
        self.save_custom_themes()
        return CUSTOM_PREFIX + cid

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
        # Derived from the palette so menus follow every theme (built-in or custom).
        idx = 0 if ctk.get_appearance_mode().lower() == "light" else 1
        c = self.colors
        return (c.bg_secondary[idx], c.text_primary[idx], c.accent_primary[idx], c.text_on_accent[idx])


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


def get_colors() -> ThemeColors:
    """Convenience function to get current theme colors."""
    return get_theme_manager().colors


# Colour roles shown in the theme editors, grouped and labelled. Every field of
# ThemeColors that holds a (light, dark) pair is listed exactly once.
COLOR_GROUPS: Dict[str, List[Tuple[str, str]]] = {
    "Backgrounds": [
        ("bg_primary", "Window background"),
        ("bg_secondary", "Cards & panels"),
        ("bg_tertiary", "Nested panels"),
        ("bg_input", "Input fields"),
        ("tab_bar", "Tab bar"),
        ("description_bg", "Description box"),
        ("spell_row", "List rows"),
        ("level_header", "List section headers"),
        ("warlock_panel", "Warlock slots panel"),
    ],
    "Text": [
        ("text_primary", "Normal text"),
        ("text_secondary", "Muted text"),
        ("text_disabled", "Disabled text"),
        ("text_on_accent", "Text on accent"),
        ("text_warning", "Warning text"),
        ("text_label", "Field labels"),
        ("spell_link", "Links"),
    ],
    "Accents": [
        ("accent_primary", "Accent"),
        ("accent_hover", "Accent (hover)"),
    ],
    "Buttons": [
        ("button_normal", "Button"),
        ("button_hover", "Button (hover)"),
        ("button_danger", "Danger button"),
        ("button_danger_hover", "Danger (hover)"),
        ("button_success", "Success button"),
        ("button_success_hover", "Success (hover)"),
        ("button_warning", "Warning button"),
        ("button_warning_hover", "Warning (hover)"),
    ],
    "Lines & scrollbars": [
        ("border", "Borders"),
        ("separator", "Separators"),
        ("scrollbar", "Scrollbar track"),
        ("scrollbar_thumb", "Scrollbar thumb"),
        ("pane_sash", "Pane divider"),
    ],
    "Comparison": [
        ("compare_better", "Better value"),
        ("compare_worse", "Worse value"),
        ("compare_neutral", "Equal value"),
    ],
    "Spell levels": [
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

# Friendly label for every role (used to name a colour in the sheet style panel).
ROLE_LABELS: Dict[str, str] = {name: label for group in COLOR_GROUPS.values() for name, label in group}
