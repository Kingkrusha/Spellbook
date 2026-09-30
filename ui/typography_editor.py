"""
Typography editor: a font family plus a style for each text role
(title / heading / subheading / normal / small), each with a live sample.

The same widget edits the app-wide fonts (``GlobalTypographyModel``) or a
character sheet's local overrides (``SheetTypographyModel``); the model decides
where changes go and what "reset" means.
"""

from typing import Callable, Dict, Optional

import customtkinter as ctk

from theme import get_theme_manager
from typography import (FONT_PRESETS, MAX_SIZE, MIN_SIZE, ROLES, ROLE_LABELS, ROLE_SAMPLES,
                        ROLE_STOCK_SIZE, FontScope, get_font_manager, installed_families,
                        default_family)
from typography import ui_font
from ui.busy import run_busy
from ui.font_picker import FontPicker
from ui.restyle import flush_restyle

BASE_FONT = "(Base font)"
WEIGHT_LABELS = {"default": "Auto weight", "bold": "Bold", "normal": "Regular"}
WEIGHT_VALUES = {v: k for k, v in WEIGHT_LABELS.items()}
SLANT_LABELS = {"default": "Auto slant", "italic": "Italic", "roman": "Upright"}
SLANT_VALUES = {v: k for k, v in SLANT_LABELS.items()}


class TypographyModel:
    """Where a TypographyEditor reads and writes. Subclasses fill these in."""

    scope: FontScope
    can_preset = False
    family_hint = ""

    def get_family(self) -> str: ...
    def set_family(self, family: str): ...
    def role_values(self, role: str) -> dict:
        """Effective {family, size, weight, slant} for display."""
    def role_family_own(self, role: str) -> str:
        """The family set specifically for this role ("" = follows base)."""
    def set_role(self, role: str, **changes): ...
    def reset_role(self, role: str): ...
    def reset_all(self): ...
    def role_overridden(self, role: str) -> bool: ...


class GlobalTypographyModel(TypographyModel):
    can_preset = True
    family_hint = "Applies to the whole app."

    def __init__(self):
        self.manager = get_font_manager()
        self.scope = self.manager.scope

    def get_family(self):
        return self.manager.settings.family

    def set_family(self, family):
        self.manager.set_family(family)

    def role_values(self, role):
        style = self.manager.settings.roles[role]
        return {"family": style.family, "size": style.size, "weight": style.weight, "slant": style.slant}

    def role_family_own(self, role):
        return self.manager.settings.roles[role].family

    def set_role(self, role, **changes):
        self.manager.set_role(role, **changes)

    def reset_role(self, role):
        from typography import RoleStyle
        self.manager.set_role(role, family="", size=ROLE_STOCK_SIZE[role], weight="default", slant="default")

    def reset_all(self):
        self.manager.reset()

    def role_overridden(self, role):
        style = self.manager.settings.roles[role]
        return (style.family, style.size, style.weight, style.slant) != ("", ROLE_STOCK_SIZE[role], "default", "default")


class SheetTypographyModel(TypographyModel):
    """Sparse per-sheet overrides: only what the user changed is stored."""

    family_hint = "Only affects this character sheet. Anything left alone follows the app."

    def __init__(self, scope: FontScope, on_change: Callable[[], None]):
        self.scope = scope
        self._on_change = on_change

    @property
    def overrides(self) -> dict:
        return self.scope.overrides

    def _changed(self):
        self.scope.refresh()
        self._on_change()

    def get_family(self):
        return self.overrides.get("family", "")

    def set_family(self, family):
        if family:
            self.overrides["family"] = family
        else:
            self.overrides.pop("family", None)
        self._changed()

    def role_values(self, role):
        style = self.scope.effective_role(role)
        return {"family": style.family, "size": style.size, "weight": style.weight, "slant": style.slant}

    def role_family_own(self, role):
        return (self.overrides.get("roles", {}).get(role, {}) or {}).get("family", self.role_values(role)["family"])

    def set_role(self, role, **changes):
        roles = self.overrides.setdefault("roles", {})
        entry = roles.setdefault(role, {})
        entry.update(changes)
        self._changed()

    def reset_role(self, role):
        roles = self.overrides.get("roles", {})
        roles.pop(role, None)
        if not roles:
            self.overrides.pop("roles", None)
        self._changed()

    def reset_all(self):
        self.overrides.clear()
        self._changed()

    def role_overridden(self, role):
        return bool((self.overrides.get("roles") or {}).get(role))


class TypographyEditor(ctk.CTkFrame):
    """Family picker + one row of controls per text role."""

    def __init__(self, parent, model: TypographyModel, on_changed: Optional[Callable[[], None]] = None,
                 compact: bool = False):
        super().__init__(parent, fg_color="transparent")
        self.model = model
        self._on_changed = on_changed
        self._compact = compact
        self._loading = False
        self._rows: Dict[str, dict] = {}
        self._build()
        self.refresh()

    # -- construction -----------------------------------------------------------

    def _build(self):
        theme = get_theme_manager()
        muted = theme.get_current_color("text_secondary")
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))

        if self.model.can_preset:
            row = ctk.CTkFrame(head, fg_color="transparent")
            row.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(row, text="Font style:", font=ui_font("subheading")).pack(side="left")
            self.preset_menu = ctk.CTkOptionMenu(row, values=list(FONT_PRESETS.keys()), width=200,
                                                 command=self._on_preset)
            self.preset_menu.set("Choose a preset\u2026")
            self.preset_menu.pack(side="right")

        row = ctk.CTkFrame(head, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="Base font:", font=ui_font("subheading")).pack(side="left")
        self.family_box = FontPicker(
            row, special=BASE_FONT if self.model.family_hint.startswith("Only") else "(Default)",
            width=200 if self._compact else 230, command=self._on_family)
        self.family_box.pack(side="right")
        ctk.CTkLabel(head, text=self.model.family_hint, font=ui_font("small"), text_color=muted,
                     anchor="w", justify="left",
                     wraplength=250 if self._compact else 560).pack(fill="x", pady=(2, 0))

        for role in ROLES:
            self._build_role(role)

        ctk.CTkButton(self, text="Reset all fonts", width=130, height=28,
                      fg_color=theme.get_current_color("button_normal"),
                      hover_color=theme.get_current_color("button_hover"),
                      text_color=theme.get_current_color("text_primary"),
                      command=self._reset_all).pack(anchor="e", pady=(10, 0))

    def _build_role(self, role: str):
        theme = get_theme_manager()
        box = ctk.CTkFrame(self, corner_radius=8, fg_color=theme.get_current_color("bg_tertiary"))
        box.pack(fill="x", pady=4)
        top = ctk.CTkFrame(box, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(top, text=ROLE_LABELS[role].upper(), font=ui_font("small", bold=True),
                     text_color=theme.get_current_color("text_secondary")).pack(side="left")
        reset = ctk.CTkButton(top, text="\u21ba", width=26, height=22, fg_color="transparent",
                              hover_color=theme.get_current_color("button_hover"),
                              text_color=theme.get_current_color("text_secondary"),
                              command=lambda r=role: self._reset_role(r))
        reset.pack(side="right")

        sample = ctk.CTkLabel(box, text=ROLE_SAMPLES[role], anchor="w", justify="left",
                              font=self.model.scope.font(role, bold=role in ("title", "heading", "subheading")),
                              wraplength=230 if self._compact else 440)
        sample._sb_font_scope = self.model.scope     # keep showing this scope's font when restyled
        sample.pack(fill="x", padx=12, pady=(0, 6))

        controls = ctk.CTkFrame(box, fg_color="transparent")
        controls.pack(fill="x", padx=12, pady=(0, 10))
        compact = self._compact
        first = ctk.CTkFrame(controls, fg_color="transparent") if compact else controls
        if compact:
            first.pack(fill="x")

        fam = FontPicker(first, special=BASE_FONT, width=210 if compact else 180, height=26,
                         command=lambda v, r=role: self._on_role_family(r, v))
        fam.pack(side="left")

        second = ctk.CTkFrame(controls, fg_color="transparent") if compact else controls
        if compact:
            second.pack(fill="x", pady=(6, 0))
        size_frame = ctk.CTkFrame(second, fg_color="transparent")
        size_frame.pack(side="left", padx=(0 if compact else 10, 0))
        minus = ctk.CTkButton(size_frame, text="\u2212", width=24, height=26,
                              command=lambda r=role: self._nudge(r, -1))
        minus.pack(side="left")
        size_label = ctk.CTkLabel(size_frame, text="12", width=32, font=ui_font("body", bold=True))
        size_label.pack(side="left")
        plus = ctk.CTkButton(size_frame, text="+", width=24, height=26,
                             command=lambda r=role: self._nudge(r, 1))
        plus.pack(side="left")

        menu_w = 84 if compact else 92
        weight = ctk.CTkOptionMenu(second, values=list(WEIGHT_LABELS.values()), width=menu_w, height=26,
                                   command=lambda v, r=role: self._on_weight(r, v))
        weight.pack(side="left", padx=(8 if compact else 10, 0))
        slant = ctk.CTkOptionMenu(second, values=list(SLANT_LABELS.values()), width=menu_w, height=26,
                                  command=lambda v, r=role: self._on_slant(r, v))
        slant.pack(side="left", padx=(6, 0))

        self._rows[role] = {"sample": sample, "family": fam, "size": size_label,
                            "weight": weight, "slant": slant, "reset": reset}

    # -- syncing ----------------------------------------------------------------

    def refresh(self):
        """Show the model's current values in every control."""
        self._loading = True
        try:
            family = self.model.get_family()
            default_label = BASE_FONT if self.model.family_hint.startswith("Only") else "(Default)"
            self.family_box.set(family or default_label)
            for role, row in self._rows.items():
                vals = self.model.role_values(role)
                row["family"].set(vals["family"] or BASE_FONT)
                row["size"].configure(text=str(vals["size"]))
                row["weight"].set(WEIGHT_LABELS.get(vals["weight"], "Auto weight"))
                row["slant"].set(SLANT_LABELS.get(vals["slant"], "Auto slant"))
                dim = theme_dim(self.model.role_overridden(role))
                row["reset"].configure(text_color=dim)
        finally:
            self._loading = False

    def _apply(self, change: Callable[[], None]):
        """Run a model change (which restyles what is on screen) behind the busy card."""
        def work():
            change()
            flush_restyle()
        run_busy("font", "Applying fonts…", work)
        self.refresh()
        if self._on_changed:
            self._on_changed()

    # -- handlers ---------------------------------------------------------------

    def _on_preset(self, name: str):
        self._apply(lambda: get_font_manager().apply_preset(name))

    def _on_family(self, value: str):
        if self._loading:
            return
        family = "" if value in (BASE_FONT, "(Default)") else value
        self._apply(lambda: self.model.set_family(family))

    def _on_role_family(self, role: str, value: str):
        if self._loading:
            return
        family = "" if value == BASE_FONT else value
        self._apply(lambda: self.model.set_role(role, family=family))

    def _nudge(self, role: str, delta: int):
        size = max(MIN_SIZE, min(MAX_SIZE, self.model.role_values(role)["size"] + delta))
        self._apply(lambda: self.model.set_role(role, size=size))

    def _on_weight(self, role: str, label: str):
        if not self._loading:
            weight = WEIGHT_VALUES.get(label, "default")
            self._apply(lambda: self.model.set_role(role, weight=weight))

    def _on_slant(self, role: str, label: str):
        if not self._loading:
            slant = SLANT_VALUES.get(label, "default")
            self._apply(lambda: self.model.set_role(role, slant=slant))

    def _reset_role(self, role: str):
        self._apply(lambda: self.model.reset_role(role))

    def _reset_all(self):
        self._apply(self.model.reset_all)


def theme_dim(active: bool) -> str:
    """Reset-arrow colour: bright when the role has been changed."""
    theme = get_theme_manager()
    return theme.get_current_color("accent_primary" if active else "text_disabled")
