"""
Typography for the Spellbook application.

Every piece of text in the UI belongs to one of five *roles*:

    title        big page titles / numbers
    heading      section and dialog headings
    subheading   card titles, field-group labels
    body         normal text
    small        captions, hints, secondary text

The user can pick a font family for the whole app and, per role, a family, a
size, a weight and italics (Settings > Appearance > Typography). Widgets get
their font from :func:`ui_font`, which returns a *shared* CTkFont: changing a
role's style reconfigures those shared fonts in place, so every label and
button using them updates live - no restart, no per-widget listeners.

A call site keeps its own size (``ui_font("body", 13)``). What the role setting
changes is the *base size* of the role: the difference between the call-site
size and the role's stock size is preserved, so a 13pt caption stays one point
above a 12pt one whatever the user picks for "body".

Character sheets can carry their own overrides (a :class:`FontScope` built from
a sparse dict). Widgets inside a styled sheet are re-pointed at that scope's
fonts by ``ui/restyle.py``.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from atomic_io import atomic_write_json
from paths import user_data_path


ROLES: Tuple[str, ...] = ("title", "heading", "subheading", "body", "small")

ROLE_LABELS: Dict[str, str] = {
    "title": "Title",
    "heading": "Heading",
    "subheading": "Subheading",
    "body": "Normal text",
    "small": "Small text",
}

ROLE_SAMPLES: Dict[str, str] = {
    "title": "Spellbook of the Archmage",
    "heading": "Evocation Spells",
    "subheading": "Casting Time & Range",
    "body": "You hurl a mote of fire at a creature or object within range.",
    "small": "Source: Player's Handbook, page 242",
}

# The point size each role is designed around. Call sites pass their own
# (historic) size; the offset from these is what is preserved.
ROLE_STOCK_SIZE: Dict[str, int] = {
    "title": 24,
    "heading": 18,
    "subheading": 14,
    "body": 12,
    "small": 11,
}

MIN_SIZE = 6
MAX_SIZE = 72

# Weight / slant choices for a role. "default" leaves it to the call site.
WEIGHT_CHOICES = ("default", "bold", "normal")
SLANT_CHOICES = ("default", "italic", "roman")


@dataclass
class RoleStyle:
    """One role's style. ``family == ""`` means "use the global family"."""
    family: str = ""
    size: int = 12
    weight: str = "default"   # "default" | "bold" | "normal"
    slant: str = "default"    # "default" | "italic" | "roman"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict, fallback: "RoleStyle") -> "RoleStyle":
        try:
            size = int(data.get("size", fallback.size))
        except (TypeError, ValueError):
            size = fallback.size
        weight = data.get("weight", fallback.weight)
        slant = data.get("slant", fallback.slant)
        return cls(
            family=str(data.get("family", fallback.family) or ""),
            size=max(MIN_SIZE, min(MAX_SIZE, size)),
            weight=weight if weight in WEIGHT_CHOICES else "default",
            slant=slant if slant in SLANT_CHOICES else "default",
        )


def default_role_styles() -> Dict[str, RoleStyle]:
    return {role: RoleStyle(size=ROLE_STOCK_SIZE[role]) for role in ROLES}


@dataclass
class FontSettings:
    """The global typography settings."""
    family: str = ""                               # "" = CustomTkinter's default (Roboto)
    roles: Dict[str, RoleStyle] = field(default_factory=default_role_styles)

    def to_dict(self) -> dict:
        return {"family": self.family,
                "roles": {r: s.to_dict() for r, s in self.roles.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> "FontSettings":
        defaults = default_role_styles()
        roles = {}
        raw_roles = data.get("roles", {}) if isinstance(data, dict) else {}
        for role in ROLES:
            raw = raw_roles.get(role)
            roles[role] = RoleStyle.from_dict(raw, defaults[role]) if isinstance(raw, dict) else defaults[role]
        return cls(family=str((data or {}).get("family", "") or ""), roles=roles)

    def is_default(self) -> bool:
        return self.to_dict() == FontSettings().to_dict()


# Quick "look" presets offered in Settings. Sizes stay at the stock values; a
# preset only changes families / weights.
FONT_PRESETS: Dict[str, Dict] = {
    "Default (Roboto)": {"family": "", "roles": {}},
    "Modern (Segoe UI)": {"family": "Segoe UI", "roles": {}},
    "Classic Serif (Georgia)": {"family": "Georgia", "roles": {}},
    "Tome (Palatino headings)": {
        "family": "",
        "roles": {r: {"family": "Palatino Linotype"} for r in ("title", "heading", "subheading")},
    },
    "Scribe (Garamond text)": {
        "family": "Garamond",
        "roles": {"title": {"family": "Palatino Linotype"}, "heading": {"family": "Palatino Linotype"}},
    },
    "Typewriter (Consolas)": {"family": "Consolas", "roles": {}},
}

# Families worth suggesting when installed; the picker also lists everything else.
SUGGESTED_FAMILIES: Tuple[str, ...] = (
    "Roboto", "Segoe UI", "Calibri", "Arial", "Verdana", "Tahoma", "Trebuchet MS",
    "Georgia", "Cambria", "Palatino Linotype", "Book Antiqua", "Bookman Old Style",
    "Garamond", "Times New Roman", "Constantia", "Consolas", "Courier New",
    "Helvetica Neue", "Avenir", "Optima", "Palatino", "Baskerville", "Menlo",
)


def default_family() -> str:
    """CustomTkinter's default font family."""
    try:
        return ctk.ThemeManager.theme["CTkFont"]["family"]
    except Exception:
        return "Roboto"


# Symbol/icon families are useless for text and unreadable when their own name is shown in them.
_SYMBOL_FONT_PARTS = ("wingdings", "webdings", "symbol", "marlett", "mdl2", "fluent icons", "emoji",
                      "holomdl", "dingbats", "ornament", "outlook")
_families_cache: Optional[List[str]] = None


def installed_families() -> List[str]:
    """All usable font families Tk can see, suggested ones first (cached)."""
    global _families_cache
    if _families_cache is not None:
        return _families_cache
    try:
        import tkinter.font as tkfont
        families = {f for f in tkfont.families()
                    if f and not f.startswith("@") and not any(p in f.lower() for p in _SYMBOL_FONT_PARTS)}
    except Exception:
        families = set()
    families.add(default_family())
    suggested = [f for f in SUGGESTED_FAMILIES if f in families]
    rest = sorted(families - set(suggested), key=str.lower)
    _families_cache = suggested + rest
    return _families_cache


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------

FontSpec = Tuple[str, int, bool, bool, bool]   # role, call-site size, bold, italic, underline


class RoleFont(ctk.CTkFont):
    """A CTkFont that remembers which role/spec it was built for.

    ``spec`` lets the restyle pass re-resolve the same font inside another scope
    (a character sheet with its own typography).
    """

    def __init__(self, scope: "FontScope", spec: FontSpec, family, size, weight, slant, underline):
        self.scope = scope
        self.spec = spec
        self.element_override = None   # set on fonts made for a per-widget override
        super().__init__(family=family, size=size, weight=weight, slant=slant, underline=underline)


class FontScope:
    """A set of shared role fonts, resolved from the global settings plus an
    optional sparse override dict (``{"family": str, "roles": {role: {...}}}``).

    The global scope has no overrides. A character sheet's scope has whatever
    the user customised for that sheet; everything else falls through to the
    global settings.
    """

    def __init__(self, manager: "FontManager", overrides: Optional[dict] = None):
        self.manager = manager
        self.overrides: dict = overrides or {}
        self._fonts: Dict[FontSpec, RoleFont] = {}
        self._element_fonts: Dict[tuple, RoleFont] = {}

    # -- resolution ---------------------------------------------------------

    def effective_role(self, role: str) -> RoleStyle:
        """Role style after applying this scope's overrides to the global one."""
        base = self.manager.settings.roles.get(role) or RoleStyle(size=ROLE_STOCK_SIZE.get(role, 12))
        ov = (self.overrides.get("roles") or {}).get(role) or {}
        style = RoleStyle(family=base.family, size=base.size, weight=base.weight, slant=base.slant)
        if "family" in ov:
            style.family = ov["family"] or ""
        if "size" in ov:
            try:
                style.size = max(MIN_SIZE, min(MAX_SIZE, int(ov["size"])))
            except (TypeError, ValueError):
                pass
        if ov.get("weight") in WEIGHT_CHOICES:
            style.weight = ov["weight"]
        if ov.get("slant") in SLANT_CHOICES:
            style.slant = ov["slant"]
        return style

    def effective_family(self, role: str) -> str:
        """The concrete family a role renders in (never empty)."""
        style = self.effective_role(role)
        if style.family:
            return style.family
        if "family" in self.overrides and self.overrides["family"]:
            return self.overrides["family"]
        if self.manager.settings.family:
            return self.manager.settings.family
        return default_family()

    def _resolve(self, spec: FontSpec) -> Tuple[str, int, str, str, bool]:
        role, base_size, bold, italic, underline = spec
        style = self.effective_role(role)
        size = max(MIN_SIZE, base_size + (style.size - ROLE_STOCK_SIZE.get(role, style.size)))
        if style.weight == "bold":
            weight = "bold"
        elif style.weight == "normal":
            weight = "normal"
        else:
            weight = "bold" if bold else "normal"
        if style.slant == "italic":
            slant = "italic"
        elif style.slant == "roman":
            slant = "roman"
        else:
            slant = "italic" if italic else "roman"
        return self.effective_family(role), size, weight, slant, underline

    # -- font objects -------------------------------------------------------

    def font(self, role: str = "body", size: Optional[int] = None, bold: bool = False,
             italic: bool = False, underline: bool = False) -> RoleFont:
        if role not in ROLE_STOCK_SIZE:
            role = "body"
        spec: FontSpec = (role, ROLE_STOCK_SIZE[role] if size is None else int(size),
                          bool(bold), bool(italic), bool(underline))
        return self.font_for_spec(spec)

    def font_for_spec(self, spec: FontSpec) -> RoleFont:
        font = self._fonts.get(spec)
        if font is None:
            family, size, weight, slant, underline = self._resolve(spec)
            font = RoleFont(self, spec, family, size, weight, slant, underline)
            self._fonts[spec] = font
        return font

    def element_font(self, spec: FontSpec, override: dict) -> RoleFont:
        """Font for a single widget the user restyled by hand.

        ``override`` may hold ``family``, ``size`` (absolute points),
        ``weight`` ("bold"/"normal") and ``slant`` ("italic"/"roman")."""
        key = (spec, tuple(sorted((k, str(v)) for k, v in override.items())))
        font = self._element_fonts.get(key)
        if font is None:
            family, size, weight, slant, underline = self._resolve(spec)
            font = RoleFont(self, spec, *self._apply_element(override, family, size, weight, slant, underline))
            font.element_override = dict(override)
            self._element_fonts[key] = font
        return font

    @staticmethod
    def _apply_element(override, family, size, weight, slant, underline):
        if override.get("family"):
            family = override["family"]
        if override.get("size"):
            try:
                size = max(MIN_SIZE, min(MAX_SIZE, int(override["size"])))
            except (TypeError, ValueError):
                pass
        elif override.get("size_delta"):
            try:
                size = max(MIN_SIZE, min(MAX_SIZE, size + int(override["size_delta"])))
            except (TypeError, ValueError):
                pass
        if override.get("weight") in ("bold", "normal"):
            weight = override["weight"]
        if override.get("slant") in ("italic", "roman"):
            slant = override["slant"]
        if "underline" in override:
            underline = bool(override["underline"])
        return family, size, weight, slant, underline

    def refresh(self):
        """Forget the cached fonts so they are rebuilt from the current settings.

        Existing widgets keep their old font object until the restyler
        (``ui/restyle.py``) re-points them - which it does only for widgets that
        are on screen, and for the rest the moment they are shown. That is much
        cheaper than reconfiguring shared fonts in place, which makes every widget
        that uses them (visible or not) re-measure and redraw itself at once."""
        self._fonts.clear()
        self._element_fonts.clear()

    def set_overrides(self, overrides: Optional[dict]):
        self.overrides = overrides or {}
        self.refresh()


class FontManager:
    """Owns the global font settings and the global scope."""

    SETTINGS_FILE = "font_settings.json"

    def __init__(self):
        self.path = user_data_path(self.SETTINGS_FILE)
        self.settings = FontSettings()
        self.scope = FontScope(self)          # the global scope
        self._listeners: List[Callable[[], None]] = []
        self.load()

    # -- persistence --------------------------------------------------------

    def load(self) -> bool:
        if not os.path.exists(self.path):
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.settings = FontSettings.from_dict(json.load(f))
            return True
        except Exception as e:
            print(f"Error loading font settings: {e}")
            return False

    def save(self) -> bool:
        try:
            atomic_write_json(self.path, self.settings.to_dict())
            return True
        except Exception as e:
            print(f"Error saving font settings: {e}")
            return False

    # -- changes ------------------------------------------------------------

    def add_listener(self, callback: Callable[[], None]):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def apply(self, save: bool = True):
        """Push the current settings into every live font, then tell listeners."""
        self.scope.refresh()
        if save:
            self.save()
        for listener in list(self._listeners):
            try:
                listener()
            except Exception as e:
                print(f"Error notifying font listener: {e}")
        try:
            from ui.restyle import restyle_app
            restyle_app()
        except Exception as e:
            print(f"Error restyling after a font change: {e}")

    def set_family(self, family: str):
        self.settings.family = family or ""
        self.apply()

    def set_role(self, role: str, **changes):
        style = self.settings.roles.get(role)
        if style is None:
            return
        for key, value in changes.items():
            if hasattr(style, key):
                setattr(style, key, value)
        style.size = max(MIN_SIZE, min(MAX_SIZE, int(style.size)))
        self.apply()

    def reset(self):
        self.settings = FontSettings()
        self.apply()

    def apply_preset(self, name: str):
        preset = FONT_PRESETS.get(name)
        if preset is None:
            return
        settings = FontSettings()
        settings.family = preset.get("family", "")
        for role, changes in (preset.get("roles") or {}).items():
            for key, value in changes.items():
                setattr(settings.roles[role], key, value)
        self.settings = settings
        self.apply()


_manager: Optional[FontManager] = None


def get_font_manager() -> FontManager:
    global _manager
    if _manager is None:
        _manager = FontManager()
    return _manager


def ui_font(role: str = "body", size: Optional[int] = None, bold: bool = False,
            italic: bool = False, underline: bool = False) -> RoleFont:
    """The shared font for a text role.

    ``size`` is the call site's own size in points; the role's setting shifts
    it. ``bold``/``italic`` are the call site's defaults (the user's per-role
    weight setting wins when it is not "default").
    """
    return get_font_manager().scope.font(role, size, bold, italic, underline)


def role_for(size: int, bold: bool = False) -> str:
    """Which role a legacy (size, bold) pair belongs to - used when retrofitting."""
    if size >= 22:
        return "title"
    if size >= 16:
        return "heading"
    if size >= 14 or (size == 13 and bold):
        return "subheading"
    if size >= 12:
        return "body"
    return "small"
