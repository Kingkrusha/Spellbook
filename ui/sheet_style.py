"""
Per-character-sheet styling.

A character sheet can carry its own look: a palette (a base theme plus colour
overrides), its own typography, and colour/font/shape overrides for individual
widgets. Everything is stored in ``CharacterSheet.style`` and applied by a
:class:`ui.restyle.Restyler` rooted at the sheet view, so the rest of the app
keeps using the global theme.

Styling is done *on* the sheet: turn on "Pick an element", hover to see what a
click would select, click it, and the inspector next to the sheet shows that
widget's colours, font and shape.
"""

import tkinter as tk
from typing import Callable, List, Optional

import customtkinter as ctk

from theme import COLOR_GROUPS, ROLE_LABELS, get_theme_manager, ThemeStr
from typography import (FontScope, get_font_manager, installed_families, ui_font, MIN_SIZE, MAX_SIZE)
from ui import restyle
from ui.color_picker import ColorSwatch, ask_color, normalize_hex
from ui.restyle import (ATTR_LABELS, GlobalPalette, OverridePalette, Restyler, ROOT_KEY, base_color,
                        is_container, role_label, widget_kind, safe_children)
from ui.font_picker import FontPicker
from ui.typography_editor import SheetTypographyModel, TypographyEditor

PANEL_WIDTH = 350
HOVER_COLOR = "#38bdf8"
SELECT_COLOR = "#f59e0b"


# --------------------------------------------------------------------------
# Outline overlay
# --------------------------------------------------------------------------

class Outline:
    """A rectangular outline drawn over a widget (four thin frames)."""

    def __init__(self, view, color: str, thickness: int):
        self.view = view
        self.thickness = thickness
        self.frames = []
        for _ in range(4):
            f = tk.Frame(view, bg=color, bd=0, highlightthickness=0)
            f._sb_skip = True
            self.frames.append(f)
        self.current = None

    def show(self, widget, clip=None):
        try:
            if not widget.winfo_exists() or not widget.winfo_ismapped():
                self.hide()
                return
            vx, vy = self.view.winfo_rootx(), self.view.winfo_rooty()
            x0, y0 = widget.winfo_rootx() - vx, widget.winfo_rooty() - vy
            x1, y1 = x0 + widget.winfo_width(), y0 + widget.winfo_height()
            if clip is not None and clip.winfo_ismapped():
                cx0, cy0 = clip.winfo_rootx() - vx, clip.winfo_rooty() - vy
                cx1, cy1 = cx0 + clip.winfo_width(), cy0 + clip.winfo_height()
                if x1 < cx0 or x0 > cx1 or y1 < cy0 or y0 > cy1:
                    self.hide()
                    return
                x0, y0, x1, y1 = max(x0, cx0), max(y0, cy0), min(x1, cx1), min(y1, cy1)
        except Exception:
            self.hide()
            return
        t = self.thickness
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        top, bottom, left, right = self.frames
        top.place(x=x0 - t, y=y0 - t, width=w + 2 * t, height=t)
        bottom.place(x=x0 - t, y=y1, width=w + 2 * t, height=t)
        left.place(x=x0 - t, y=y0, width=t, height=h)
        right.place(x=x1, y=y0, width=t, height=h)
        for f in self.frames:
            f.lift()
        self.current = widget

    def hide(self):
        self.current = None
        for f in self.frames:
            f.place_forget()

    def destroy(self):
        for f in self.frames:
            try:
                f.destroy()
            except Exception:
                pass


# --------------------------------------------------------------------------
# The styler
# --------------------------------------------------------------------------

class SheetStyler:
    """Owns one sheet view's local style, restyler, outlines and panel."""

    def __init__(self, view, on_save: Callable[[], None]):
        self.view = view
        self._on_save = on_save
        self.style: dict = {}
        self.font_manager = get_font_manager()
        self.font_scope = FontScope(self.font_manager, {})
        self.palette = OverridePalette("", {})
        self.restyler = Restyler(view, self.palette, self.font_scope, {}, include_toplevels=False)
        self.restyler.after_apply = self._after_apply
        view._sb_restyler = self.restyler

        self.panel: Optional["StylePanel"] = None
        self.picking = False
        self.selected = None
        self.selected_key: Optional[str] = None
        self.hover = Outline(view, HOVER_COLOR, 2)
        self.selection = Outline(view, SELECT_COLOR, 3)
        self._hover_widget = None
        self._bound = False
        self._escape_bound = False
        self._poll_job = None
        # bindtag that captures clicks while picking; one per sheet view (class
        # bindings are global, and several sheet tabs can be open)
        self.capture_tag = f"SbStyleCapture{id(view)}"
        self._font_listener = self._on_global_fonts
        self.font_manager.add_listener(self._font_listener)

    # -- data ---------------------------------------------------------------------

    def load(self, style: Optional[dict]):
        """Adopt a sheet's style dict (edited in place) and restyle."""
        self.style = style if style is not None else {}
        pal = self.style.setdefault("palette", {})
        pal.setdefault("base", "")
        colors = pal.setdefault("colors", {})
        fonts = self.style.setdefault("fonts", {})
        elements = self.style.setdefault("elements", {})
        self.palette.base_key = pal["base"]
        self.palette.overrides = colors
        self.font_scope.overrides = fonts
        self.font_scope.refresh()
        self.restyler.elements = elements
        self.clear_selection()
        if self.panel is not None:
            self.panel.reload()

    def has_style(self) -> bool:
        from character_sheet import prune_style
        return bool(prune_style(self.style))

    def commit(self):
        """Persist the sheet (its style dict is part of it)."""
        try:
            self._on_save()
        except Exception as e:
            print(f"Error saving sheet style: {e}")

    def set_base_theme(self, key: str):
        self.style.setdefault("palette", {})["base"] = key
        self.palette.base_key = key
        self.apply()
        self.commit()

    def apply(self):
        self.restyler.apply()
        self._after_apply()

    def schedule(self):
        self.restyler.schedule()

    def _after_apply(self):
        if self.panel is not None:
            self.panel.restyle_self()
        if self.picking:
            self.refresh_capture()
            self._reselect()

    def _on_global_fonts(self):
        """App-wide fonts changed: sheet scopes derive from them."""
        try:
            self.font_scope.refresh()
        except Exception:
            pass

    def destroy(self):
        self.font_manager.remove_listener(self._font_listener)
        self.stop_picking()
        self.hover.destroy()
        self.selection.destroy()

    # -- element styles -------------------------------------------------------------

    def element(self, key: str, create: bool = False) -> Optional[dict]:
        elements = self.restyler.elements
        if key in elements:
            return elements[key]
        if create:
            elements[key] = {}
            return elements[key]
        return None

    def prune_element(self, key: str):
        if key in self.restyler.elements and not self.restyler.elements[key]:
            del self.restyler.elements[key]

    def restyle_widget(self, widget, key: str = ""):
        """Restyle one widget (and everything in it, for a panel)."""
        self.restyler.restyle_widget(widget)

    def clean_element(self, key: str):
        """Drop empty scaffolding from an element style."""
        entry = self.restyler.elements.get(key)
        if entry is None:
            return
        if not entry.get("group"):
            entry.pop("group", None)
        self.prune_element(key)

    # -- picking -------------------------------------------------------------------

    def start_picking(self):
        if self.picking:
            return
        self.picking = True
        try:
            self.view.focus_set()       # commits any half-typed field first
        except Exception:
            pass
        if not self._bound:
            self._bound = True
            v = self.view
            v.bind_class(self.capture_tag, "<Motion>", self._on_motion)
            v.bind_class(self.capture_tag, "<ButtonPress-1>", self._on_click)
            v.bind_class(self.capture_tag, "<Double-Button-1>", self._on_double_click)
            for seq in ("<ButtonRelease-1>", "<B1-Motion>", "<Triple-Button-1>",
                        "<ButtonPress-2>", "<ButtonPress-3>", "<ButtonRelease-3>", "<Key>"):
                v.bind_class(self.capture_tag, seq, lambda e: "break")
        self.refresh_capture()
        self._ensure_polling()
        if not self._escape_bound:
            self._escape_bound = True
            try:
                self.view.winfo_toplevel().bind("<Escape>", self._on_escape, add="+")
            except Exception:
                pass
        if self.panel is not None:
            self.panel.picking_changed()

    def stop_picking(self):
        if not self.picking:
            return
        self.picking = False
        for w in self._iter_tk(self.view):
            try:
                tags = w.bindtags()
                if self.capture_tag in tags:
                    w.bindtags(tuple(t for t in tags if t != self.capture_tag))
            except Exception:
                pass
        self.hover.hide()
        self._hover_widget = None
        if self.panel is not None:
            self.panel.picking_changed()

    def _on_escape(self, event=None):
        if self.picking:
            self.stop_picking()

    def _iter_tk(self, parent):
        for child in safe_children(parent):
            if getattr(child, "_sb_skip", False) or isinstance(child, (tk.Toplevel, ctk.CTkToplevel)):
                continue
            yield child
            yield from self._iter_tk(child)

    def refresh_capture(self):
        """Put the capture bindtag first on every widget (including new ones)."""
        for w in self._iter_tk(self.view):
            try:
                tags = w.bindtags()
                if self.capture_tag not in tags:
                    w.bindtags((self.capture_tag,) + tuple(tags))
            except Exception:
                pass

    def _clip_for(self, widget):
        try:
            content = self.view.content_frame
            w = widget
            while w is not None:
                if w is content:
                    return content
                w = getattr(w, "master", None)
        except Exception:
            pass
        return None

    # what a click lands on: the whole widget, not just the label under the pointer
    _LEAVES_WITH_BACKGROUND = ("Bt", "En", "Tx", "Cb", "Sw", "Rb", "Om", "Cx", "Sg", "Pb", "Sl")

    def _is_unit(self, widget) -> bool:
        """True for something that is visibly a thing of its own: a button, a field,
        a card with a background... (not a bare label or a transparent layout frame)."""
        kind = widget_kind(widget)
        if kind is None:
            return False
        if kind[0] in self._LEAVES_WITH_BACKGROUND:
            return True
        try:
            return str(widget.cget("fg_color")) != "transparent"
        except Exception:
            return False

    def group_target(self, widget):
        """The whole widget a plain click selects: the nearest visible thing at or above ``widget``."""
        w = widget
        while w is not None and w is not self.view:
            if self._is_unit(w):
                return w
            w = getattr(w, "master", None)
        return self.view                      # the page itself

    def _hover_target(self, event, deep: bool = False):
        owner = self.restyler.owner_of(event.widget)
        if owner is None:
            return None
        return owner if deep else self.group_target(owner)

    def _on_motion(self, event):
        target = self._hover_target(event)
        if target is self.view:
            target = None
        if target is self._hover_widget:
            return "break"
        self._hover_widget = target
        if target is None or target is self.selected:
            self.hover.hide()
        else:
            self.hover.show(target, self._clip_for(target))
        return "break"

    def _on_click(self, event):
        target = self._hover_target(event)
        if target is not None:
            self.select(target)
        return "break"

    def _on_double_click(self, event):
        """Double-click: just the element under the pointer (a label, not its whole card)."""
        target = self._hover_target(event, deep=True)
        if target is not None:
            self.select(target)
        return "break"

    # -- selection -------------------------------------------------------------------

    def select(self, widget):
        self.selected = widget
        self.selected_key = self.restyler.key_of(widget)
        self.hover.hide()
        self._hover_widget = None
        self.selection.show(widget, self._clip_for(widget))
        self._ensure_polling()
        if self.panel is not None:
            self.panel.show_element(widget)

    def clear_selection(self):
        self.selected = None
        self.selected_key = None
        self.selection.hide()
        self.hover.hide()
        self._hover_widget = None
        if self.panel is not None:
            self.panel.show_element(None)

    def _reselect(self):
        """After a rebuild: find the widget selected before, by its key."""
        if self.selected_key is None:
            return
        try:
            alive = self.selected is not None and self.selected.winfo_exists()
        except Exception:
            alive = False
        if alive:
            self.selection.show(self.selected, self._clip_for(self.selected))
            return
        widget = self.restyler.find(self.selected_key)
        if widget is not None:
            self.selected = widget
            self.selection.show(widget, self._clip_for(widget))
            if self.panel is not None:
                self.panel.show_element(widget)
        else:
            self.selection.hide()

    def refresh_outlines(self):
        if self.selected is not None:
            self.selection.show(self.selected, self._clip_for(self.selected))

    def _poll(self):
        """Keep the outlines glued to their widgets while the sheet scrolls."""
        self._poll_job = None
        try:
            if not self.view.winfo_exists():
                return
        except Exception:
            return
        if self.selected is not None or self.picking:
            self.refresh_outlines()
            if self._hover_widget is not None and self.hover.current is not None:
                self.hover.show(self._hover_widget, self._clip_for(self._hover_widget))
            self._poll_job = self.view.after(150, self._poll)

    def _ensure_polling(self):
        if getattr(self, "_poll_job", None) is None:
            self._poll_job = self.view.after(150, self._poll)


# --------------------------------------------------------------------------
# The docked panel
# --------------------------------------------------------------------------

class StylePanel(ctk.CTkFrame):
    """Inspector docked beside the sheet: Element / Colors / Fonts."""

    def __init__(self, view, styler: SheetStyler):
        super().__init__(view, width=PANEL_WIDTH, corner_radius=0)
        self._sb_skip = True                      # the sheet's own restyler leaves the panel alone
        self.view = view
        self.styler = styler
        self.tm = get_theme_manager()
        self.grid_propagate(False)
        self.pack_propagate(False)
        self._panel_restyler = Restyler(self, GlobalPalette(), get_font_manager().scope)
        self._tab = "Element"
        self._build()

    def restyle_self(self):
        try:
            self._panel_restyler.apply()
        except Exception:
            pass

    # -- frame -------------------------------------------------------------------

    def _build(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(head, text="\U0001f3a8  Sheet style", font=ui_font("heading", bold=True)).pack(side="left")
        ctk.CTkButton(head, text="✕", width=28, height=28, fg_color="transparent",
                      hover_color=self.tm.get_current_color("button_hover"),
                      text_color=self.tm.get_current_color("text_primary"),
                      command=self.view.hide_style_panel).pack(side="right")

        self.pick_button = ctk.CTkButton(self, text="◎  Pick an element on the sheet", height=34,
                                         command=self._toggle_pick)
        self.pick_button.pack(fill="x", padx=12, pady=(4, 2))
        self.hint = ctk.CTkLabel(self, text="", font=ui_font("small"), anchor="w", justify="left",
                                 wraplength=PANEL_WIDTH - 30,
                                 text_color=self.tm.get_current_color("text_secondary"))
        self.hint.pack(fill="x", padx=14)

        self.tabs = ctk.CTkSegmentedButton(self, values=["Element", "Colors", "Fonts"], command=self._on_tab)
        self.tabs.set("Element")
        self.tabs.pack(fill="x", padx=12, pady=(8, 6))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=4)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=12, pady=10)
        ctk.CTkButton(foot, text="Reset all styling on this sheet", height=30,
                      fg_color=self.tm.get_current_color("button_danger"),
                      hover_color=self.tm.get_current_color("button_danger_hover"),
                      text_color="#ffffff", command=self._reset_everything).pack(fill="x")
        self.picking_changed()
        self._render()

    def picking_changed(self):
        picking = self.styler.picking
        if picking:
            self.pick_button.configure(text="■  Stop picking (Esc)")
            self.hint.configure(text="Click selects the whole widget (its panel or bar). Double-click selects "
                                     "just the label or field under the pointer. Buttons won't trigger while picking.")
        else:
            self.pick_button.configure(text="◎  Pick an element on the sheet")
            self.hint.configure(text="Turn on picking, then click any part of the sheet to restyle it.")

    def reload(self):
        self._render()

    def _toggle_pick(self):
        if self.styler.picking:
            self.styler.stop_picking()
        else:
            self._tab = "Element"
            self.tabs.set("Element")
            self.styler.start_picking()
            self._render()

    def _on_tab(self, value: str):
        self._tab = value
        self._render()

    def _clear_body(self):
        for child in self.body.winfo_children():
            child.destroy()

    def _render(self):
        self._clear_body()
        if self._tab == "Element":
            self._render_element(self.styler.selected)
        elif self._tab == "Colors":
            self._render_colors()
        else:
            self._render_fonts()
        self.restyle_self()

    def show_element(self, widget):
        if self._tab != "Element":
            self._tab = "Element"
            self.tabs.set("Element")
        self._render()

    def _reset_everything(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Reset styling", "Remove all custom colours, fonts and per-element "
                                   "styling from this character sheet?", parent=self.winfo_toplevel()):
            return
        for section in ("palette", "fonts", "elements"):
            self.styler.style.pop(section, None)
        self.styler.load(self.styler.style)
        self.styler.apply()
        self.styler.commit()

    # -- element tab -------------------------------------------------------------

    def _section(self, title: str):
        ctk.CTkLabel(self.body, text=title.upper(), anchor="w", font=ui_font("small", bold=True),
                     text_color=self.tm.get_current_color("text_secondary")).pack(fill="x", padx=10, pady=(14, 3))

    def _render_element(self, widget):
        styler = self.styler
        rs = styler.restyler
        try:
            alive = widget is not None and widget.winfo_exists()
        except Exception:
            alive = False
        if not alive:
            box = ctk.CTkFrame(self.body, corner_radius=10, fg_color=self.tm.get_current_color("bg_tertiary"))
            box.pack(fill="x", padx=8, pady=10)
            ctk.CTkLabel(box, justify="left", anchor="w", wraplength=PANEL_WIDTH - 90,
                         font=ui_font("body"),
                         text="Nothing selected.\n\nTurn on “Pick an element” and click a label, a "
                              "button, a card – anything on the sheet – to change its colours, font "
                              "and shape.\n\nUse the Colors and Fonts tabs to restyle the whole sheet at once."
                         ).pack(fill="x", padx=14, pady=14)
            return
        key = rs.key_of(widget)
        self._selected_widget = widget

        # breadcrumb: ancestors, nearest last
        chain = []
        w = widget
        while w is not None and w is not styler.view:
            if widget_kind(w) is not None:
                chain.append(w)
            w = getattr(w, "master", None)
        chain = list(reversed(chain))[-4:]
        crumbs = ctk.CTkFrame(self.body, fg_color="transparent")
        crumbs.pack(fill="x", padx=8, pady=(4, 0))
        if widget is not styler.view:
            top = ctk.CTkButton(crumbs, text="\u2191 Whole sheet", height=22, anchor="w", font=ui_font("small"),
                                fg_color="transparent", hover_color=self.tm.get_current_color("button_hover"),
                                text_color=self.tm.get_current_color("spell_link"),
                                command=lambda: styler.select(styler.view))
            top.pack(fill="x", pady=(0, 2))
        for i, w in enumerate(chain):
            last = w is widget
            label = rs.describe(w)
            if len(label) > 26:
                label = label[:25] + "…"
            btn = ctk.CTkButton(crumbs, text=label, height=24, corner_radius=6, anchor="w",
                                font=ui_font("small", bold=last),
                                fg_color=self.tm.get_current_color("accent_primary") if last else "transparent",
                                hover_color=self.tm.get_current_color("button_hover"),
                                text_color=self.tm.get_current_color("text_on_accent" if last else "text_secondary"),
                                command=lambda w=w: styler.select(w))
            btn.pack(fill="x", padx=(i * 10, 0), pady=1)

        if key is None:
            return
        override = {k: v for k, v in (styler.element(key) or {}).items() if k != "group"}
        if widget is styler.view:
            ctk.CTkLabel(self.body, text="Whole sheet", anchor="w", font=ui_font("subheading", bold=True)).pack(
                fill="x", padx=12, pady=(6, 0))

        # ---- colours
        rows = rs.color_rows(widget)
        if rows:
            self._section("This element" if is_container(widget) else "Colours")
        for attr, color, role, label, overridden in rows:
            self._color_row(widget, key, attr, color, role, label, overridden)

        # ---- everything inside (panels only)
        if is_container(widget):
            self._group_section(widget, key)

        # ---- font
        if restyle.has_font(widget):
            self._section("Text")
            self._font_controls(widget, key)

        # ---- shape
        shape_attrs = []
        for attr in ("corner_radius", "border_width"):
            try:
                shape_attrs.append((attr, int(widget.cget(attr))))
            except Exception:
                pass
        if shape_attrs:
            self._section("Shape")
            for attr, value in shape_attrs:
                self._shape_row(widget, key, attr, value)

        if override:
            ctk.CTkButton(self.body, text="Reset this element", height=28,
                          fg_color=self.tm.get_current_color("button_normal"),
                          hover_color=self.tm.get_current_color("button_hover"),
                          text_color=self.tm.get_current_color("text_primary"),
                          command=lambda: self._reset_element(widget, key)).pack(fill="x", padx=10, pady=(14, 4))

    def _color_row(self, widget, key, attr, color, role, label, overridden):
        styler = self.styler
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=2)
        swatch = ColorSwatch(row, color, width=44, height=28,
                             command=lambda: self._pick_element_color(widget, key, attr))
        swatch.pack(side="left")
        col = ctk.CTkFrame(row, fg_color="transparent")
        col.pack(side="left", fill="x", expand=True, padx=8)
        name = ctk.CTkLabel(col, text=label, anchor="w", font=ui_font("body", bold=overridden))
        name.pack(fill="x")
        if role:
            link = ctk.CTkButton(col, text=f"All “{role_label(role)}” →", height=18, anchor="w",
                                 font=ui_font("small"), fg_color="transparent", border_width=0,
                                 hover_color=self.tm.get_current_color("button_hover"),
                                 text_color=self.tm.get_current_color("spell_link"),
                                 command=lambda: self._pick_role_color(role))
            link.pack(fill="x")
        if overridden:
            ctk.CTkButton(row, text="↺", width=26, height=26, fg_color="transparent",
                          hover_color=self.tm.get_current_color("button_hover"),
                          text_color=self.tm.get_current_color("accent_primary"),
                          command=lambda: self._reset_element_attr(widget, key, attr)).pack(side="right")

    def _palette_swatches(self):
        pal = self.styler.palette
        out = []
        for role in ("bg_primary", "bg_secondary", "bg_tertiary", "accent_primary", "text_primary",
                     "text_secondary", "button_normal", "spell_link"):
            pair = pal.pair(role)
            if pair:
                idx = 0 if ctk.get_appearance_mode().lower() == "light" else 1
                out.append((role, pair[idx]))
        return out

    def _pick_element_color(self, widget, key, attr):
        styler = self.styler
        rs = styler.restyler
        elements = rs.elements
        had = key in elements and attr in elements[key]
        previous = elements.get(key, {}).get(attr)
        current = normalize_hex(restyle._resolve_display(widget.cget(attr))) or "#808080"
        if str(widget.cget(attr)) == "transparent":
            current = "#808080"

        def live(color):
            styler.element(key, create=True)[attr] = color
            styler.restyle_widget(widget, key)
            styler.refresh_outlines()

        # a leaf widget repaints instantly; a panel restyles everything inside it, so wait for the colour to settle
        heavy = is_container(widget)
        status, value = ask_color(self, current, title=f"{ATTR_LABELS.get(attr, attr)} – this element only",
                                  on_change=None if heavy else live, on_settle=live if heavy else None,
                                  swatches=self._palette_swatches(),
                                  allow_clear=had, clear_text="Reset")
        if status == "ok":
            styler.commit()
        else:
            if status == "clear" or not had:
                if key in elements:
                    elements[key].pop(attr, None)
                    styler.prune_element(key)
            else:
                elements[key][attr] = previous
            styler.restyle_widget(widget, key)
            if status == "clear":
                styler.commit()
        self._render()

    def _pick_role_color(self, role: str):
        """Change a palette role for the whole sheet."""
        styler = self.styler
        overrides = styler.palette.overrides
        mode = "light" if ctk.get_appearance_mode().lower() == "light" else "dark"
        pair = styler.palette.pair(role)
        current = pair[0 if mode == "light" else 1]
        before = dict(overrides.get(role) or {})

        def live(color):
            overrides.setdefault(role, {})[mode] = color
            styler.apply()

        status, _ = ask_color(self, current,
                              title=f"{role_label(role)} – everything using it on this sheet",
                              on_settle=live, swatches=self._palette_swatches(),
                              allow_clear=bool(before.get(mode)), clear_text="Reset")
        if status == "ok":
            styler.commit()
        else:
            if before:
                overrides[role] = before
            else:
                overrides.pop(role, None)
            if status == "clear":
                cleared = dict(before)
                cleared.pop(mode, None)
                if cleared:
                    overrides[role] = cleared
                else:
                    overrides.pop(role, None)
                styler.commit()
            styler.apply()
        self._render()

    def _reset_element_attr(self, widget, key, attr):
        self.styler.restyler.elements.get(key, {}).pop(attr, None)
        self.styler.clean_element(key)
        self.styler.restyle_widget(widget, key)
        self.styler.commit()
        self._render()

    def _reset_element(self, widget, key):
        """Remove this element's own overrides (what it imposes on everything inside is kept)."""
        entry = self.styler.restyler.elements.get(key)
        if entry is not None:
            for k in [k for k in entry if k != "group"]:
                del entry[k]
        self.styler.clean_element(key)
        self.styler.restyle_widget(widget, key)
        self.styler.refresh_outlines()
        self.styler.commit()
        self._render()

    # -- group styles: everything inside a panel -----------------------------------

    GROUP_COLORS = (
        ("text_color", "All text", "text_primary"),
        ("button_color", "All buttons", "accent_primary"),
        ("field_color", "All input fields", "bg_input"),
    )

    def _count_inside(self, widget) -> int:
        total = 0
        for c in safe_children(widget):
            if getattr(c, "_sb_skip", False):
                continue
            if widget_kind(c) is not None:
                total += 1
            total += self._count_inside(c)
        return total

    def _group_section(self, widget, key):
        styler = self.styler
        group = (styler.element(key) or {}).get("group", {})
        self._section("Everything inside")
        ctk.CTkLabel(self.body, anchor="w", justify="left", wraplength=PANEL_WIDTH - 90, font=ui_font("small"),
                     text_color=self.tm.get_current_color("text_secondary"),
                     text=f"Changes here apply to all {self._count_inside(widget)} elements in this "
                          f"{'sheet' if widget is styler.view else 'widget'}. Double-click a label to "
                          f"style just that label instead.").pack(fill="x", padx=12, pady=(0, 4))

        for prop, label, role in self.GROUP_COLORS:
            row = ctk.CTkFrame(self.body, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            current = group.get(prop) or styler.palette.color(role) or "#808080"
            ColorSwatch(row, current, width=44, height=28,
                        command=lambda p=prop, l=label: self._pick_group_color(widget, key, p, l)).pack(side="left")
            ctk.CTkLabel(row, text=label, anchor="w", font=ui_font("body", bold=prop in group)).pack(
                side="left", padx=8)
            if prop in group:
                ctk.CTkButton(row, text="\u21ba", width=26, height=26, fg_color="transparent",
                              hover_color=self.tm.get_current_color("button_hover"),
                              text_color=self.tm.get_current_color("accent_primary"),
                              command=lambda p=prop: self._set_group(widget, key, p, None)).pack(side="right")

        font = group.get("font", {})

        def update_font(**changes):
            entry = dict(font)
            for k, v in changes.items():
                if v in (None, "", 0):
                    entry.pop(k, None)
                else:
                    entry[k] = v
            self._set_group(widget, key, "font", entry or None)

        ctk.CTkLabel(self.body, text="Font", anchor="w", font=ui_font("body", bold=bool(font))).pack(
            fill="x", padx=12, pady=(8, 2))
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=2)
        fam = FontPicker(row, value=font.get("family") or "(Keep fonts)", special="(Keep fonts)", width=190,
                         height=28, command=lambda v: update_font(family="" if v == "(Keep fonts)" else v))
        fam.pack(side="left")
        row2 = ctk.CTkFrame(self.body, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=2)
        delta = int(font.get("size_delta", 0))
        ctk.CTkLabel(row2, text="Size", width=40, anchor="w", font=ui_font("body")).pack(side="left", padx=(4, 0))
        ctk.CTkButton(row2, text="\u2212", width=26, height=28,
                      command=lambda: update_font(size_delta=delta - 1)).pack(side="left")
        ctk.CTkLabel(row2, text=f"{delta:+d} pt", width=54, font=ui_font("body", bold=True)).pack(side="left")
        ctk.CTkButton(row2, text="+", width=26, height=28,
                      command=lambda: update_font(size_delta=delta + 1)).pack(side="left")
        row3 = ctk.CTkFrame(self.body, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=(4, 2))
        weight = ctk.CTkOptionMenu(row3, values=["Keep weight", "Bold", "Regular"], width=100, height=26,
                                   command=lambda v: update_font(weight={"Bold": "bold", "Regular": "normal"}.get(v, "")))
        weight.set({"bold": "Bold", "normal": "Regular"}.get(font.get("weight"), "Keep weight"))
        weight.pack(side="left")
        slant = ctk.CTkOptionMenu(row3, values=["Keep slant", "Italic", "Upright"], width=100, height=26,
                                  command=lambda v: update_font(slant={"Italic": "italic", "Upright": "roman"}.get(v, "")))
        slant.set({"italic": "Italic", "roman": "Upright"}.get(font.get("slant"), "Keep slant"))
        slant.pack(side="left", padx=(6, 0))

        if group:
            ctk.CTkButton(self.body, text="Clear styling for everything inside", height=28,
                          fg_color=self.tm.get_current_color("button_normal"),
                          hover_color=self.tm.get_current_color("button_hover"),
                          text_color=self.tm.get_current_color("text_primary"),
                          command=lambda: self._clear_group(widget, key)).pack(fill="x", padx=10, pady=(10, 2))

    def _set_group(self, widget, key, prop, value):
        """Set (or, with None, remove) one group property, then restyle the panel."""
        styler = self.styler
        entry = styler.element(key, create=True)
        group = entry.setdefault("group", {})
        if value is None:
            group.pop(prop, None)
        else:
            group[prop] = value
        styler.clean_element(key)
        styler.restyle_widget(widget)
        styler.refresh_outlines()
        styler.commit()
        self._render()

    def _clear_group(self, widget, key):
        entry = self.styler.element(key)
        if entry is not None:
            entry.pop("group", None)
        self.styler.clean_element(key)
        self.styler.restyle_widget(widget)
        self.styler.commit()
        self._render()

    def _pick_group_color(self, widget, key, prop, label):
        styler = self.styler
        group = (styler.element(key) or {}).get("group", {})
        had = prop in group
        previous = group.get(prop)
        role = {p: r for p, _l, r in self.GROUP_COLORS}[prop]
        current = normalize_hex(previous or styler.palette.color(role) or "#808080") or "#808080"

        def live(color):
            entry = styler.element(key, create=True)
            entry.setdefault("group", {})[prop] = color
            styler.restyle_widget(widget)
            styler.refresh_outlines()

        status, _ = ask_color(self, current, title=f"{label} \u2013 everything inside",
                              on_settle=live, swatches=self._palette_swatches(),
                              allow_clear=had, clear_text="Reset")
        entry = styler.element(key, create=True)
        grp = entry.setdefault("group", {})
        if status == "ok":
            styler.commit()
        else:
            if status == "clear" or not had:
                grp.pop(prop, None)
            else:
                grp[prop] = previous
            styler.clean_element(key)
            styler.restyle_widget(widget)
            if status == "clear":
                styler.commit()
        styler.clean_element(key)
        self._render()

    # -- element font & shape ---------------------------------------------------

    def _font_controls(self, widget, key):
        styler = self.styler
        try:
            font = widget.cget("font")
            role = getattr(font, "spec", ("body",))[0]
            family, size = font.cget("family"), int(font.cget("size"))
            bold, italic = font.cget("weight") == "bold", font.cget("slant") == "italic"
        except Exception:
            return
        from typography import ROLE_LABELS as FONT_ROLE_LABELS
        note = ctk.CTkFrame(self.body, fg_color="transparent")
        note.pack(fill="x", padx=8)
        ctk.CTkLabel(note, text=f"Text style: {FONT_ROLE_LABELS.get(role, role)}", anchor="w",
                     font=ui_font("body")).pack(side="left", padx=2)
        ctk.CTkButton(note, text="Edit all →", width=70, height=20, font=ui_font("small"),
                      fg_color="transparent", hover_color=self.tm.get_current_color("button_hover"),
                      text_color=self.tm.get_current_color("spell_link"),
                      command=lambda: self._jump("Fonts")).pack(side="right")

        override = (styler.element(key) or {}).get("font", {})

        def update(**changes):
            entry = styler.element(key, create=True).setdefault("font", {})
            entry.update(changes)
            styler.restyle_widget(widget, key)
            styler.refresh_outlines()
            styler.commit()
            self._render()

        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(4, 2))
        fam = FontPicker(row, value=family, width=190, height=28, command=lambda v: update(family=v))
        fam.pack(side="left")
        minus = ctk.CTkButton(row, text="−", width=26, height=28,
                              command=lambda: update(size=max(MIN_SIZE, size - 1)))
        minus.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(row, text=str(size), width=30, font=ui_font("body", bold=True)).pack(side="left")
        ctk.CTkButton(row, text="+", width=26, height=28,
                      command=lambda: update(size=min(MAX_SIZE, size + 1))).pack(side="left")

        row2 = ctk.CTkFrame(self.body, fg_color="transparent")
        row2.pack(fill="x", padx=8, pady=2)
        b_var = ctk.BooleanVar(value=bold)
        i_var = ctk.BooleanVar(value=italic)
        ctk.CTkCheckBox(row2, text="Bold", variable=b_var, width=70, checkbox_width=18, checkbox_height=18,
                        command=lambda: update(weight="bold" if b_var.get() else "normal")).pack(side="left")
        ctk.CTkCheckBox(row2, text="Italic", variable=i_var, width=70, checkbox_width=18, checkbox_height=18,
                        command=lambda: update(slant="italic" if i_var.get() else "roman")).pack(side="left", padx=10)
        if override:
            ctk.CTkButton(row2, text="↺", width=26, height=26, fg_color="transparent",
                          hover_color=self.tm.get_current_color("button_hover"),
                          text_color=self.tm.get_current_color("accent_primary"),
                          command=lambda: self._reset_element_font(widget, key)).pack(side="right")

    def _reset_element_font(self, widget, key):
        entry = self.styler.element(key)
        if entry:
            entry.pop("font", None)
            self.styler.prune_element(key)
        self.styler.restyle_widget(widget, key)
        self.styler.refresh_outlines()
        self.styler.commit()
        self._render()

    def _shape_row(self, widget, key, attr, value):
        styler = self.styler
        label = "Corner radius" if attr == "corner_radius" else "Border width"
        maximum = 30 if attr == "corner_radius" else 8
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text=label, width=96, anchor="w", font=ui_font("body")).pack(side="left")
        readout = ctk.CTkLabel(row, text=str(value), width=28, font=ui_font("body", bold=True))
        slider = ctk.CTkSlider(row, from_=0, to=maximum, number_of_steps=maximum, width=140)
        slider.set(min(value, maximum))
        slider.pack(side="left", padx=4)
        readout.pack(side="left")

        def moved(v):
            n = int(round(v))
            readout.configure(text=str(n))
            styler.element(key, create=True)[attr] = n
            styler.restyle_widget(widget, key)
            styler.refresh_outlines()

        slider.configure(command=moved)
        slider.bind("<ButtonRelease-1>", lambda e: styler.commit(), add="+")

    def _jump(self, tab: str):
        self._tab = tab
        self.tabs.set(tab)
        self._render()

    # -- colours tab -----------------------------------------------------------------

    def _render_colors(self):
        styler = self.styler
        tm = self.tm
        muted = tm.get_current_color("text_secondary")
        mode = "light" if ctk.get_appearance_mode().lower() == "light" else "dark"

        self._section("Base theme for this sheet")
        names = ["Same as the app"] + [name for _k, name, _c in tm.list_themes()]
        keys = [""] + [k for k, _n, _c in tm.list_themes()]
        current_key = styler.palette.base_key
        current_name = names[keys.index(current_key)] if current_key in keys else names[0]

        def on_base(name):
            styler.set_base_theme(keys[names.index(name)])
            self._render()

        menu = ctk.CTkOptionMenu(self.body, values=names, command=on_base)
        menu.set(current_name)
        menu.pack(fill="x", padx=10)
        ctk.CTkLabel(self.body, anchor="w", justify="left", wraplength=PANEL_WIDTH - 90, font=ui_font("small"),
                     text_color=muted,
                     text=f"Then adjust individual colours below. You are editing the {mode} mode "
                          f"colours (switch appearance mode in Settings to edit the other)."
                     ).pack(fill="x", padx=12, pady=(4, 0))

        idx = 0 if mode == "light" else 1
        for group in ("Backgrounds", "Text", "Accents", "Buttons", "Lines & scrollbars"):
            self._section(group)
            for role, label in COLOR_GROUPS[group]:
                pair = styler.palette.pair(role)
                if not pair:
                    continue
                overridden = bool((styler.palette.overrides.get(role) or {}).get(mode))
                row = ctk.CTkFrame(self.body, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=1)
                ColorSwatch(row, pair[idx], width=40, height=24,
                            command=lambda r=role: self._pick_role_color(r)).pack(side="left")
                ctk.CTkLabel(row, text=label, anchor="w", font=ui_font("body", bold=overridden)).pack(
                    side="left", padx=8)
                if overridden:
                    ctk.CTkButton(row, text="↺", width=24, height=24, fg_color="transparent",
                                  hover_color=tm.get_current_color("button_hover"),
                                  text_color=tm.get_current_color("accent_primary"),
                                  command=lambda r=role: self._reset_role(r)).pack(side="right")

        if styler.palette.overrides or styler.palette.base_key:
            ctk.CTkButton(self.body, text="Reset sheet colours", height=28,
                          fg_color=tm.get_current_color("button_normal"),
                          hover_color=tm.get_current_color("button_hover"),
                          text_color=tm.get_current_color("text_primary"),
                          command=self._reset_palette).pack(fill="x", padx=10, pady=(14, 4))

    def _reset_role(self, role: str):
        mode = "light" if ctk.get_appearance_mode().lower() == "light" else "dark"
        entry = self.styler.palette.overrides.get(role) or {}
        entry.pop(mode, None)
        if not entry:
            self.styler.palette.overrides.pop(role, None)
        self.styler.apply()
        self.styler.commit()
        self._render()

    def _reset_palette(self):
        self.styler.palette.overrides.clear()
        self.styler.palette.base_key = ""
        self.styler.style.setdefault("palette", {})["base"] = ""
        self.styler.apply()
        self.styler.commit()
        self._render()

    # -- fonts tab -------------------------------------------------------------------

    def _render_fonts(self):
        model = SheetTypographyModel(self.styler.font_scope, on_change=self._fonts_changed)
        editor = TypographyEditor(self.body, model, compact=True)
        editor.pack(fill="x", padx=6, pady=4)

    def _fonts_changed(self):
        self.styler.apply()
        self.styler.commit()
