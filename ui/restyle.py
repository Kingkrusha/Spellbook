"""
Live re-theming of widget trees.

Colours
-------
``ThemeManager.get_current_color(role)`` returns a :class:`theme.ThemeStr` - a
string that remembers its role - and :func:`push_ctk_defaults` gives
CustomTkinter's own defaults the same treatment (role-tagged colour pairs), so
almost every colour a widget holds knows what it *means* ("card background",
"accent", ...). :class:`Restyler` walks a widget tree and re-resolves each of
those colours through a *palette*, which is how:

* a theme switch (built-in or custom) recolours the whole open window at once,
* a character sheet can use its own palette and per-widget colours while the
  rest of the app keeps the global one.

Fonts
-----
Shared role fonts (``typography.ui_font``) already update live for the global
settings. A sheet with its own typography has widgets re-pointed at that
scope's fonts by the same walk.

Per-widget styles
-----------------
A ``Restyler`` can also carry *element styles*: colour/font/shape overrides for
individual widgets, keyed by a path that is stable across rebuilds (see
:meth:`Restyler.key_of`). Removing an override restores the value the widget was
built with (kept in ``ThemeStr.original``).
"""

import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk
from customtkinter.windows.widgets.core_widget_classes import CTkBaseClass

from theme import ThemeStr, ThemeTuple, tag_color, tag_pair, get_theme_manager, ROLE_LABELS
from typography import FontScope, RoleFont


# --------------------------------------------------------------------------
# CustomTkinter defaults -> theme roles
# --------------------------------------------------------------------------

# For each CustomTkinter class: which of its default colours follows which role.
DEFAULT_ROLES: Dict[str, Dict[str, str]] = {
    "CTk": {"fg_color": "bg_primary"},
    "CTkToplevel": {"fg_color": "bg_primary"},
    "CTkFrame": {"fg_color": "bg_secondary", "top_fg_color": "bg_tertiary", "border_color": "border"},
    "CTkButton": {"fg_color": "accent_primary", "hover_color": "accent_hover", "border_color": "border",
                  "text_color": "text_on_accent", "text_color_disabled": "text_disabled"},
    "CTkLabel": {"text_color": "text_primary"},
    "CTkEntry": {"fg_color": "bg_input", "border_color": "border", "text_color": "text_primary",
                 "placeholder_text_color": "text_secondary"},
    "CTkCheckBox": {"fg_color": "accent_primary", "border_color": "border", "hover_color": "accent_hover",
                    "checkmark_color": "text_on_accent", "text_color": "text_primary",
                    "text_color_disabled": "text_disabled"},
    "CTkSwitch": {"fg_color": "bg_tertiary", "progress_color": "accent_primary", "button_color": "text_primary",
                  "button_hover_color": "text_secondary", "text_color": "text_primary",
                  "text_color_disabled": "text_disabled"},
    "CTkRadioButton": {"fg_color": "accent_primary", "border_color": "border", "hover_color": "accent_hover",
                       "text_color": "text_primary", "text_color_disabled": "text_disabled"},
    "CTkProgressBar": {"fg_color": "bg_tertiary", "progress_color": "accent_primary", "border_color": "border"},
    "CTkSlider": {"fg_color": "bg_tertiary", "progress_color": "accent_primary", "button_color": "accent_primary",
                  "button_hover_color": "accent_hover"},
    "CTkOptionMenu": {"fg_color": "accent_primary", "button_color": "accent_hover",
                      "button_hover_color": "accent_hover", "text_color": "text_on_accent",
                      "text_color_disabled": "text_disabled"},
    "CTkComboBox": {"fg_color": "bg_input", "border_color": "border", "button_color": "button_normal",
                    "button_hover_color": "button_hover", "text_color": "text_primary",
                    "text_color_disabled": "text_disabled"},
    "CTkScrollbar": {"button_color": "scrollbar_thumb", "button_hover_color": "accent_hover"},
    "CTkSegmentedButton": {"fg_color": "bg_tertiary", "selected_color": "accent_primary",
                           "selected_hover_color": "accent_hover", "unselected_color": "bg_tertiary",
                           "unselected_hover_color": "button_hover", "text_color": "text_on_accent",
                           "text_color_disabled": "text_disabled"},
    "CTkTextbox": {"fg_color": "bg_input", "border_color": "border", "text_color": "text_primary",
                   "scrollbar_button_color": "scrollbar_thumb", "scrollbar_button_hover_color": "accent_hover"},
    "CTkScrollableFrame": {"label_fg_color": "bg_tertiary"},
    "DropdownMenu": {"fg_color": "bg_secondary", "hover_color": "bg_tertiary", "text_color": "text_primary"},
}


def push_ctk_defaults(palette: "Palette"):
    """Point CustomTkinter's default colours at the palette's roles.

    Widgets created afterwards (that don't pass a colour of their own) start out
    in the right theme *and* carry the role, so :class:`Restyler` can recolour
    them later. Existing widgets are handled by a Restyler pass."""
    theme = ctk.ThemeManager.theme
    for cls, attrs in DEFAULT_ROLES.items():
        section = theme.get(cls)
        if not section:
            continue
        for attr, role in attrs.items():
            if attr in section:
                pair = palette.pair(role)
                if pair:
                    section[attr] = tag_pair(pair, role)


# --------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------

class Palette:
    """Resolves a colour role to a (light, dark) pair."""

    def pair(self, role: str) -> Optional[Tuple[str, str]]:
        raise NotImplementedError

    def color(self, role: str) -> Optional[str]:
        pair = self.pair(role)
        if not pair:
            return None
        return pair[0] if ctk.get_appearance_mode().lower() == "light" else pair[1]


class GlobalPalette(Palette):
    """The app-wide theme."""

    def pair(self, role: str):
        value = getattr(get_theme_manager().colors, role, None)
        return tuple(value) if isinstance(value, (tuple, list)) and len(value) == 2 else None


class OverridePalette(Palette):
    """A palette layered over a base theme: optional base theme key plus
    per-role, per-mode overrides ``{role: {"light": hex, "dark": hex}}``.

    ``overrides`` is held by reference so edits are seen immediately."""

    def __init__(self, base_key: str = "", overrides: Optional[dict] = None):
        self.base_key = base_key
        self.overrides = overrides if overrides is not None else {}

    def base_pair(self, role: str):
        tm = get_theme_manager()
        colors = tm.get_theme_colors(self.base_key) if self.base_key else tm.colors
        value = getattr(colors, role, None)
        return tuple(value) if isinstance(value, (tuple, list)) and len(value) == 2 else None

    def pair(self, role: str):
        base = self.base_pair(role)
        if base is None:
            return None
        ov = self.overrides.get(role)
        if not ov:
            return base
        return (ov.get("light") or base[0], ov.get("dark") or base[1])

    def is_overridden(self, role: str) -> bool:
        return bool(self.overrides.get(role))


# --------------------------------------------------------------------------
# Widget classification
# --------------------------------------------------------------------------

COLOR_ATTRS: Tuple[str, ...] = (
    "fg_color", "top_fg_color", "text_color", "border_color", "hover_color",
    "button_color", "button_hover_color", "progress_color", "checkmark_color",
    "selected_color", "selected_hover_color", "unselected_color", "unselected_hover_color",
    "dropdown_fg_color", "dropdown_hover_color", "dropdown_text_color",
    "placeholder_text_color", "text_color_disabled", "label_fg_color", "label_text_color",
    "scrollbar_fg_color", "scrollbar_button_color", "scrollbar_button_hover_color",
)

# widget class name -> (short key, friendly name)
_KINDS: Dict[str, Tuple[str, str]] = {
    "CTkFrame": ("Fr", "Panel"), "CTkLabel": ("Lb", "Label"), "CTkButton": ("Bt", "Button"),
    "CTkEntry": ("En", "Text field"), "CTkTextbox": ("Tx", "Text box"), "CTkCheckBox": ("Cb", "Checkbox"),
    "CTkSwitch": ("Sw", "Switch"), "CTkRadioButton": ("Rb", "Radio button"),
    "CTkOptionMenu": ("Om", "Dropdown"), "CTkComboBox": ("Cx", "Combo box"),
    "CTkSegmentedButton": ("Sg", "Segmented button"), "CTkProgressBar": ("Pb", "Progress bar"),
    "CTkSlider": ("Sl", "Slider"), "CTkScrollbar": ("Sb", "Scrollbar"),
    "CTkScrollableFrame": ("Sf", "Scrolling panel"), "CTkTabview": ("Tv", "Tabs"),
}

# Widgets whose children are user widgets (everything else is a leaf to us).
_CONTAINERS = (ctk.CTkFrame, ctk.CTkScrollableFrame, ctk.CTkTabview)

_class_info_cache: Dict[type, Optional[Tuple[str, str, str]]] = {}
_class_attr_cache: Dict[type, Tuple[str, ...]] = {}
_class_font_cache: Dict[type, bool] = {}


def widget_kind(widget) -> Optional[Tuple[str, str, str]]:
    """(short key, friendly name, CTk class name) for a styleable widget, else None."""
    cls = type(widget)
    if cls in _class_info_cache:
        return _class_info_cache[cls]
    info = None
    if isinstance(widget, (CTkBaseClass, ctk.CTkScrollableFrame)):
        for base in cls.__mro__:
            if base.__module__.startswith("customtkinter") and base.__name__ in _KINDS:
                short, friendly = _KINDS[base.__name__]
                info = (short, friendly, base.__name__)
                break
        if info is None and isinstance(widget, CTkBaseClass):
            info = ("Wd", "Widget", "CTkBaseClass")
    _class_info_cache[cls] = info
    return info


def color_attrs(widget) -> Tuple[str, ...]:
    """Colour options this widget class supports (probed once per class)."""
    cls = type(widget)
    cached = _class_attr_cache.get(cls)
    if cached is not None:
        return cached
    found = []
    for attr in COLOR_ATTRS:
        try:
            if widget.cget(attr) is not None:
                found.append(attr)
        except Exception:
            pass
    _class_attr_cache[cls] = tuple(found)
    return _class_attr_cache[cls]


def has_font(widget) -> bool:
    cls = type(widget)
    cached = _class_font_cache.get(cls)
    if cached is None:
        try:
            cached = widget.cget("font") is not None
        except Exception:
            cached = False
        _class_font_cache[cls] = cached
    return cached


def is_container(widget) -> bool:
    return isinstance(widget, _CONTAINERS)


def style_name(widget, name: str):
    """Give a widget a stable name: element styles under it are keyed from
    this name instead of the (more fragile) position in the widget tree."""
    widget._sb_name = name
    return widget


def base_color(value):
    """What the app originally set, ignoring any per-widget override."""
    original = getattr(value, "original", None)
    return original if original is not None else value


def role_of(value) -> Optional[str]:
    return getattr(base_color(value), "role", None)


def _same(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return str(a) == str(b) and getattr(a, "role", None) == getattr(b, "role", None) \
            and getattr(a, "original", None) is getattr(b, "original", None)
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return tuple(a) == tuple(b) and getattr(a, "role", None) == getattr(b, "role", None) \
            and getattr(a, "original", None) is getattr(b, "original", None)
    return False


# --------------------------------------------------------------------------
# The restyler
# --------------------------------------------------------------------------

def _is_mapped(widget) -> bool:
    try:
        return bool(widget.winfo_ismapped())
    except Exception:
        return False


def _run_deferred(node, event=None):
    """<Map> handler: restyle a subtree that was skipped while hidden."""
    pending = getattr(node, "_sb_deferred", None)
    if not pending:
        return
    node._sb_deferred = None
    restyler, path, inherited = pending
    restyler._apply_node(node, path, inherited)


class Restyler:
    """Re-resolves colours and fonts of a widget tree.

    ``elements`` maps element keys to override dicts::

        {"fg_color": "#hex", "text_color": "#hex", ..., "corner_radius": 8,
         "border_width": 2, "font": {"family": ..., "size": ..., "weight": ..., "slant": ...}}
    """

    def __init__(self, root, palette: Palette, fonts: Optional[FontScope] = None,
                 elements: Optional[Dict[str, dict]] = None,
                 include_toplevels: bool = True):
        self.root = root
        self.palette = palette
        self.fonts = fonts
        self.elements: Dict[str, dict] = elements if elements is not None else {}
        self.include_toplevels = include_toplevels
        self.after_apply: Optional[Callable[[], None]] = None   # runs after each scheduled pass
        self._job = None

    def schedule(self, delay_ms: int = 40):
        """Restyle soon (coalescing bursts) - used when new widgets appear."""
        if self._job is not None:
            return
        try:
            self._job = self.root.after(delay_ms, self._run_scheduled)
        except Exception:
            self._job = None

    def _run_scheduled(self):
        self._job = None
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        self.apply()
        if self.after_apply:
            try:
                self.after_apply()
            except Exception:
                pass

    def find(self, key: str):
        """The widget currently carrying element key ``key`` (or None)."""
        if key == ROOT_KEY:
            return self.root
        found = []

        def visit(parent, path):
            counts: Dict[str, int] = {}
            for child in _safe_children(parent):
                if getattr(child, "_sb_skip", False) or isinstance(child, (tk.Toplevel, ctk.CTkToplevel)):
                    continue
                kind = widget_kind(child)
                if kind is None:
                    visit(child, path)
                    continue
                n = counts.get(kind[0], 0)
                counts[kind[0]] = n + 1
                name = getattr(child, "_sb_name", None)
                child_path = name if name else f"{path}/{kind[0]}{n}"
                if child_path == key:
                    found.append(child)
                    return
                if is_container(child):
                    visit(child, child_path)
                if found:
                    return

        visit(self.root, "")
        return found[0] if found else None

    # -- tree walking --------------------------------------------------------

    def apply(self, subtree=None):
        """Restyle the whole tree (or one subtree)."""
        root = subtree or self.root
        try:
            if not root.winfo_exists():
                return
        except Exception:
            return
        path = ""
        if subtree is not None and subtree is not self.root:
            path = self.key_of(subtree) or ""
            inherited = self.inherited_for(subtree, include_self=True)
        else:
            kind = widget_kind(root)
            inherited = None
            if kind is not None or isinstance(root, (ctk.CTk, ctk.CTkToplevel)):
                self._style(root, ROOT_KEY if kind is not None else "", styled=kind is not None)
                inherited = merge_group(None, (self.elements.get(ROOT_KEY) or {}).get("group"))
        self._walk(root, path, inherited)

    def _walk(self, parent, path: str, inherited: Optional[dict] = None):
        counts: Dict[str, int] = {}
        try:
            children = parent.winfo_children()
        except Exception:
            return
        for child in children:
            if getattr(child, "_sb_skip", False):
                continue
            is_top = isinstance(child, (tk.Toplevel, ctk.CTkToplevel))
            if is_top and not self.include_toplevels:
                continue
            own = getattr(child, "_sb_restyler", None)
            if own is not None and own is not self:
                if _is_mapped(child):
                    own.apply()
                else:
                    own._defer(child, "", None)
                continue
            kind = None if is_top else widget_kind(child)
            if kind is None:
                child_path = path                # internal tk widget / window: look through it
            else:
                n = counts.get(kind[0], 0)
                counts[kind[0]] = n + 1
                name = getattr(child, "_sb_name", None)
                child_path = name if name else f"{path}/{kind[0]}{n}"
            if not _is_mapped(child):
                # Off screen (another tab, a closed dialog...): restyling it would cost
                # redraws nobody sees. It is restyled the moment it is shown.
                self._defer(child, child_path, inherited)
                continue
            self._style(child, child_path if kind is not None else "", styled=kind is not None,
                        inherited=inherited)
            if kind is None or is_container(child):
                inner = inherited
                if kind is not None:
                    inner = merge_group(inherited, (self.elements.get(child_path) or {}).get("group"))
                self._walk(child, child_path, inner)

    def _defer(self, node, path: str, inherited: Optional[dict] = None):
        """Restyle ``node`` (and everything under it) when it is next mapped."""
        node._sb_deferred = (self, path, inherited)
        if getattr(node, "_sb_map_bound", False):
            return
        node._sb_map_bound = True
        try:
            tk.Misc.bind(node, "<Map>", lambda e, n=node: _run_deferred(n, e), add="+")
        except Exception:
            node._sb_map_bound = False

    def _apply_node(self, node, path: str, inherited: Optional[dict] = None):
        try:
            if not node.winfo_exists():
                return
        except Exception:
            return
        kind = None if isinstance(node, (tk.Toplevel, ctk.CTkToplevel)) else widget_kind(node)
        self._style(node, path if kind is not None else "", styled=kind is not None, inherited=inherited)
        if kind is None or is_container(node):
            inner = inherited
            if kind is not None:
                inner = merge_group(inherited, (self.elements.get(path) or {}).get("group"))
            self._walk(node, path, inner)

    # -- group styles (an element styling everything inside it) --------------------

    def inherited_for(self, widget, include_self: bool = False) -> Optional[dict]:
        """The merged group styles of ``widget``'s ancestors (and itself, if asked)."""
        chain = []
        w = widget if include_self else getattr(widget, "master", None)
        while w is not None:
            if widget_kind(w) is not None:
                chain.append(w)
            if w is self.root:
                break
            w = getattr(w, "master", None)
        merged = None
        for w in reversed(chain):
            key = self.key_of(w)
            group = (self.elements.get(key) or {}).get("group") if key else None
            merged = merge_group(merged, group)
        return merged

    def restyle_widget(self, widget):
        """Restyle one widget (and, for a panel, everything in it) from its element style."""
        key = self.key_of(widget)
        if key is None:
            return
        self._style(widget, key, styled=True, inherited=self.inherited_for(widget))
        if is_container(widget):
            self.apply(subtree=widget)

    def _effective_override(self, w, key: str, inherited: Optional[dict]) -> Optional[dict]:
        """The element's own overrides plus what enclosing groups impose on it."""
        own = self.elements.get(key) if (key and self.elements) else None
        if not inherited:
            return own
        kind = widget_kind(w)
        short = kind[0] if kind else ""
        ov: dict = {}
        if inherited.get("text_color") and "text_color" in color_attrs(w):
            ov["text_color"] = inherited["text_color"]
        if inherited.get("button_color") and short == "Bt":
            ov["fg_color"] = inherited["button_color"]
        if inherited.get("field_color") and short in ("En", "Tx", "Cx", "Om"):
            ov["fg_color"] = inherited["field_color"]
        if inherited.get("font") and has_font(w):
            ov["font"] = dict(inherited["font"])
        if own:
            for k, v in own.items():
                if k == "group":
                    continue
                if k == "font" and "font" in ov:
                    merged = dict(ov["font"])
                    merged.update(v)
                    if "size" in v:
                        merged.pop("size_delta", None)
                    ov["font"] = merged
                else:
                    ov[k] = v
        return ov or None

    # -- keys ----------------------------------------------------------------

    def key_of(self, widget) -> Optional[str]:
        """Stable identifier of a widget inside this restyler's tree."""
        if widget is self.root:
            return ROOT_KEY
        segments: List[str] = []
        w = widget
        while w is not None and w is not self.root:
            kind = widget_kind(w)
            if kind is not None:
                name = getattr(w, "_sb_name", None)
                if name:
                    segments.append(name)
                    return "/".join(reversed(segments))
                parent = w.master
                same = [c for c in _safe_children(parent) if widget_kind(c) is not None
                        and widget_kind(c)[0] == kind[0] and not getattr(c, "_sb_skip", False)]
                try:
                    idx = same.index(w)
                except ValueError:
                    return None
                segments.append(f"{kind[0]}{idx}")
            w = getattr(w, "master", None)
        if w is None:
            return None
        return "/" + "/".join(reversed(segments)) if segments else ""

    def owner_of(self, tk_widget):
        """The styleable (CTk) widget a raw tk widget belongs to, if inside the root."""
        w = tk_widget
        while w is not None:
            if widget_kind(w) is not None:
                return w
            if w is self.root:
                return None
            w = getattr(w, "master", None)
        return None

    # -- styling one widget ----------------------------------------------------

    def _style(self, w, key: str, styled: bool = True, inherited: Optional[dict] = None):
        override = self._effective_override(w, key, inherited)
        try:
            attrs = color_attrs(w)
        except Exception:
            attrs = ()
        changes = {}
        dark = ctk.get_appearance_mode().lower() != "light"
        for attr in attrs:
            try:
                cur = w.cget(attr)
            except Exception:
                continue
            if cur is None:
                continue
            base = base_color(cur)
            role = getattr(base, "role", None)
            if role == "text_on_accent" and attr in ("text_color", "checkmark_color") and                     self._sits_on_neutral(w):
                role = "text_primary"       # default button text is white: unreadable on light neutrals
            ov = override.get(attr) if override else None
            if ov:
                desired = tag_color(ov, role, original=base)
            elif role:
                pair = self.palette.pair(role)
                if pair is None:
                    continue
                if isinstance(base, (tuple, list)):
                    desired = tag_pair(pair, role)
                else:
                    desired = tag_color(pair[1] if dark else pair[0], role)
            else:
                desired = base
            if not _same(cur, desired):
                changes[attr] = desired

        if styled and isinstance(w, CTkBaseClass) and not isinstance(w, (ctk.CTk, ctk.CTkToplevel)):
            # CTk paints rounded corners in ``bg_color`` (the parent's colour).
            # A parent's own change is propagated by CTk itself only to direct
            # children, so keep it in step here.
            try:
                wanted = w._detect_color_of_master()
                if wanted is not None and str(w._bg_color) != str(wanted):
                    changes["bg_color"] = wanted
            except Exception:
                pass

        if changes:
            # One configure per widget: every call redraws it.
            try:
                w.configure(**changes)
            except Exception:
                for attr, value in changes.items():
                    try:
                        w.configure(**{attr: value})
                    except Exception:
                        pass

        if isinstance(w, ctk.CTkScrollableFrame):
            self._sync_scrollable(w)

        if styled and not isinstance(w, (ctk.CTk, ctk.CTkToplevel)):
            self._style_shape(w, override)
            self._style_font(w, override)

    @staticmethod
    def _sits_on_neutral(w) -> bool:
        """True for a button/menu whose own background is a plain neutral colour."""
        if not isinstance(w, (ctk.CTkButton, ctk.CTkOptionMenu, ctk.CTkSegmentedButton)):
            return False
        try:
            fg = w.cget("fg_color")
        except Exception:
            return False
        return role_of(fg) in NEUTRAL_ROLES

    @staticmethod
    def _sync_scrollable(w):
        """A scrolling panel paints its canvas from its frame's colour (or the
        parent's, when transparent) - and only re-reads that on its own events."""
        try:
            frame = w._parent_frame
            fg = frame.cget("fg_color")
            source = frame.cget("bg_color") if fg == "transparent" else fg
            if isinstance(source, (tuple, list)):
                source = source[0] if ctk.get_appearance_mode().lower() == "light" else source[1]
            if str(w._parent_canvas.cget("bg")).lower() != str(source).lower():
                tk.Frame.configure(w, bg=source)
                w._parent_canvas.configure(bg=source)
        except Exception:
            pass

    @staticmethod
    def _style_shape(w, override):
        """Corner radius / border width overrides (the built-in value is remembered
        so removing the override puts it back)."""
        remembered = getattr(w, "_sb_shape", None)
        if not override and not remembered:
            return
        for attr in ("corner_radius", "border_width"):
            try:
                cur = w.cget(attr)
            except Exception:
                continue
            if override and attr in override:
                if remembered is None:
                    remembered = w._sb_shape = {}
                remembered.setdefault(attr, cur)
                if cur != override[attr]:
                    try:
                        w.configure(**{attr: override[attr]})
                    except Exception:
                        pass
            elif remembered and attr in remembered:
                original = remembered.pop(attr)
                if cur != original:
                    try:
                        w.configure(**{attr: original})
                    except Exception:
                        pass

    def _style_font(self, w, override):
        scope = getattr(w, "_sb_font_scope", None) or self.fonts    # e.g. a sample label showing a sheet's fonts
        if scope is None or not has_font(w):
            return
        try:
            cur = w.cget("font")
        except Exception:
            return
        font_ov = override.get("font") if override else None
        if isinstance(cur, RoleFont):
            spec = cur.spec
        elif isinstance(cur, ctk.CTkFont) and font_ov:
            spec = ("body", int(cur.cget("size")), cur.cget("weight") == "bold",
                    cur.cget("slant") == "italic", bool(cur.cget("underline")))
        else:
            return
        if font_ov:
            desired = scope.element_font(spec, font_ov)
        else:
            desired = scope.font_for_spec(spec)
        if desired is not cur:
            try:
                w.configure(font=desired)
            except Exception:
                pass

    # -- inspector helpers -----------------------------------------------------

    def describe(self, widget) -> str:
        kind = widget_kind(widget)
        name = getattr(widget, "_sb_name", None)
        if widget is self.root:
            return "Whole sheet"
        if kind is None:
            return type(widget).__name__
        friendly = kind[1]
        cls_name = type(widget).__name__
        if cls_name != kind[2] and not cls_name.startswith("CTk"):
            friendly = _humanize(cls_name)
        text = ""
        try:
            text = str(widget.cget("text") or "")
        except Exception:
            pass
        text = " ".join(text.split())
        if text:
            clipped = text[:22] + ("…" if len(text) > 22 else "")
            friendly += " “" + clipped + "”"
        if name:
            friendly = f"{_humanize(name)}: {friendly}"
        return friendly

    def color_rows(self, widget) -> List[Tuple[str, str, Optional[str], str, bool]]:
        """(attr, current colour, role, label, overridden) for each colour of a widget."""
        key = self.key_of(widget)
        ov = self.elements.get(key, {}) if key is not None else {}
        rows = []
        for attr in color_attrs(widget):
            try:
                cur = widget.cget(attr)
            except Exception:
                continue
            if cur is None:
                continue
            resolved = _resolve_display(cur)
            if resolved == "transparent":
                # Show what actually shows through
                resolved = _resolve_display(_bg_of(widget)) or "#000000"
            rows.append((attr, resolved, role_of(cur), ATTR_LABELS.get(attr, attr), attr in ov))
        return rows


ATTR_LABELS: Dict[str, str] = {
    "fg_color": "Background",
    "top_fg_color": "Nested background",
    "text_color": "Text",
    "border_color": "Border",
    "hover_color": "Hover",
    "button_color": "Button",
    "button_hover_color": "Button hover",
    "progress_color": "Progress",
    "checkmark_color": "Checkmark",
    "selected_color": "Selected",
    "selected_hover_color": "Selected hover",
    "unselected_color": "Unselected",
    "unselected_hover_color": "Unselected hover",
    "dropdown_fg_color": "Dropdown background",
    "dropdown_hover_color": "Dropdown hover",
    "dropdown_text_color": "Dropdown text",
    "placeholder_text_color": "Placeholder text",
    "text_color_disabled": "Disabled text",
    "label_fg_color": "Label background",
    "label_text_color": "Label text",
    "scrollbar_fg_color": "Scrollbar track",
    "scrollbar_button_color": "Scrollbar thumb",
    "scrollbar_button_hover_color": "Scrollbar hover",
}

ROOT_KEY = "@root"      # element key of the restyler's root widget


def merge_group(outer: Optional[dict], inner: Optional[dict]) -> Optional[dict]:
    """Combine an enclosing group style with a nested one (the nested one wins;
    font size adjustments add up)."""
    if not inner:
        return outer
    if not outer:
        return dict(inner)
    merged = dict(outer)
    for k, v in inner.items():
        if k == "font" and "font" in merged:
            font = dict(merged["font"])
            delta = font.get("size_delta", 0) + v.get("size_delta", 0)
            font.update(v)
            if delta:
                font["size_delta"] = delta
            merged["font"] = font
        else:
            merged[k] = v
    return merged


# Backgrounds that are neutral (text on them is normal text, not "text on accent").
NEUTRAL_ROLES = frozenset({"button_normal", "button_hover", "bg_primary", "bg_secondary", "bg_tertiary",
                           "bg_input", "tab_bar", "scrollbar", "scrollbar_thumb", "pane_sash",
                           "spell_row", "level_header", "description_bg", "warlock_panel"})

# Colours worth showing first for each kind of widget (others follow).
PRIMARY_ATTRS: Tuple[str, ...] = ("fg_color", "text_color", "border_color", "hover_color")


def _humanize(name: str) -> str:
    out = []
    for i, ch in enumerate(name.replace("_", " ")):
        if ch.isupper() and i and not name[i - 1].isupper() and name[i - 1] != " ":
            out.append(" ")
        out.append(ch)
    return "".join(out).strip().title() if name.islower() else "".join(out).strip()


def _resolve_display(value) -> str:
    """A concrete colour string for a stored colour (picks the current mode of a pair)."""
    if isinstance(value, (tuple, list)):
        return value[0] if ctk.get_appearance_mode().lower() == "light" else value[1]
    return str(value)


def _bg_of(widget):
    try:
        return widget._detect_color_of_master()
    except Exception:
        return None


def safe_children(widget):
    return _safe_children(widget)


def _safe_children(widget):
    try:
        return widget.winfo_children()
    except Exception:
        return []


def role_label(role: Optional[str]) -> str:
    return ROLE_LABELS.get(role or "", role or "")


# --------------------------------------------------------------------------
# App-wide restyling
# --------------------------------------------------------------------------

_global_restyler: Optional[Restyler] = None


_creation_hook_installed = False


def _note_created(widget):
    """A widget was just built: if it lives inside a scoped restyler (a
    character sheet), ask that restyler to style it once the build settles."""
    m = getattr(widget, "master", None)
    for _ in range(60):
        if m is None:
            return
        restyler = getattr(m, "_sb_restyler", None)
        if restyler is not None:
            restyler.schedule()
            return
        m = getattr(m, "master", None)


def install_creation_hook():
    """Wrap the CTk widget constructors so scoped restylers hear about new widgets."""
    global _creation_hook_installed
    if _creation_hook_installed:
        return
    _creation_hook_installed = True
    import functools
    names = ("CTkFrame", "CTkLabel", "CTkButton", "CTkEntry", "CTkTextbox", "CTkCheckBox", "CTkSwitch",
             "CTkRadioButton", "CTkOptionMenu", "CTkComboBox", "CTkSegmentedButton", "CTkProgressBar",
             "CTkSlider", "CTkScrollableFrame")
    for name in names:
        cls = getattr(ctk, name, None)
        if cls is None:
            continue
        original = cls.__init__

        def make(orig):
            @functools.wraps(orig)
            def init(self, *args, **kwargs):
                orig(self, *args, **kwargs)
                _note_created(self)
            return init

        cls.__init__ = make(original)


def install_global(root) -> Restyler:
    """Create the app-wide restyler for ``root`` and point CTk's defaults at the theme."""
    global _global_restyler
    install_creation_hook()
    palette = GlobalPalette()
    push_ctk_defaults(palette)
    from typography import get_font_manager
    _global_restyler = Restyler(root, palette, get_font_manager().scope)
    return _global_restyler


_restyle_job = None


def restyle_app(delay_ms: int = 15):
    """Recolour everything already on screen after a theme or appearance change.

    Calls arriving within ``delay_ms`` of each other (dragging a colour picker,
    say) are coalesced into a single pass."""
    global _restyle_job
    restyler = _global_restyler
    if restyler is None:
        return
    push_ctk_defaults(restyler.palette)
    if _restyle_job is not None:
        return

    def run():
        global _restyle_job
        _restyle_job = None
        restyler.apply()

    try:
        _restyle_job = restyler.root.after(delay_ms, run)
    except Exception:
        _restyle_job = None
        restyler.apply()


def flush_restyle():
    """Run a pending (debounced) app restyle right now."""
    global _restyle_job
    restyler = _global_restyler
    if restyler is None or _restyle_job is None:
        return
    try:
        restyler.root.after_cancel(_restyle_job)
    except Exception:
        pass
    _restyle_job = None
    restyler.apply()


def best_text_color(bg_hex: str) -> str:
    """Black or white, whichever reads better on ``bg_hex``."""
    try:
        h = bg_hex.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return "#ffffff"
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#111111" if luminance > 150 else "#ffffff"
