"""
Spell List Panel for D&D Spellbook (CustomTkinter version).

Displays a scrollable list of spells with selection support.

Rendering is **virtualized**: no matter how many spells match the current
filter, only the rows visible in the viewport (plus a small buffer) are realized
as widgets. The rest of the list is represented by a single spacer frame that
gives the scrollbar the correct extent. This keeps resizing and re-filtering
fast even with the full ~500-spell list - the previous approach kept one
``CTkButton`` per matching spell and had to redraw hundreds of rounded-corner
canvases on every ``<Configure>`` event during a window/pane resize.

Extra speedups folded in here:
  * row buttons use ``corner_radius=0`` and a solid ``fg_color`` (CTk's rounded
    + transparent draw path is the expensive one);
  * ``<Configure>`` storms from a resize drag are coalesced into a single
    re-render.
"""

import customtkinter as ctk
import tkinter as tk
from typing import List, Callable, Optional
from spell import Spell
from theme import get_theme_manager
from ui.platform_compat import bind_right_click


class SpellListPanel(ctk.CTkFrame):
    """A virtualized scrollable list panel for displaying and selecting spells."""

    ROW_HEIGHT = 38          # height of a single row widget (px)
    ROW_STRIDE = 42          # distance between successive row origins (row + gap)
    BUFFER_ROWS = 8          # rows rendered above/below the viewport as slack

    def __init__(self, parent, on_select: Callable[[Optional[Spell]], None],
                 on_right_click: Optional[Callable[[Spell, int, int], None]] = None):
        super().__init__(parent, corner_radius=10)

        self.on_select = on_select
        self.on_right_click = on_right_click  # (spell, x_root, y_root)

        self._spells: List[Spell] = []
        self._selected_index: Optional[int] = None
        self._total_height: int = 1

        self._row_pool: List[ctk.CTkButton] = []
        self._render_pending = False
        self._configure_after_id: Optional[str] = None

        self._font = ctk.CTkFont(size=13)

        self._refresh_colors()
        self.configure(fg_color=self._panel_bg)
        self._create_widgets()
        self._install_scroll_hooks()

        # Register theme listener so this panel updates live when theme changes
        try:
            self._theme = get_theme_manager()
            self._theme.add_listener(self._on_theme_changed)
        except Exception:
            self._theme = None

    # ------------------------------------------------------------------ setup

    def _refresh_colors(self):
        theme = get_theme_manager()
        self._panel_bg = theme.get_current_color('bg_primary')
        self._row_bg = theme.get_current_color('spell_row')
        self._accent = theme.get_current_color('accent_primary')
        self._hover = theme.get_current_color('button_hover')
        self._text = theme.get_current_color('text_primary')
        self._secondary_text = theme.get_text_secondary()

    def _create_widgets(self):
        """Create the header and the virtualized scroll area."""
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkLabel(header_frame, text="Spells",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")

        self.count_label = ctk.CTkLabel(header_frame, text="0 spells",
                                        font=ctk.CTkFont(size=12),
                                        text_color=self._secondary_text)
        self.count_label.pack(side="right")

        # Solid fg_color (not "transparent") - a solid fill is cheaper to redraw.
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=self._row_bg)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # One spacer whose height stands in for the whole (virtual) list, so the
        # scrollbar has the right range even though only ~20 rows really exist.
        self._spacer = ctk.CTkFrame(self.scroll_frame, fg_color="transparent",
                                    height=self._total_height)
        self._spacer.pack(fill="x")
        try:
            self._spacer.pack_propagate(False)
        except Exception:
            pass

    def _install_scroll_hooks(self):
        """Re-render the visible window whenever the canvas scrolls or resizes."""
        try:
            canvas = self.scroll_frame._parent_canvas
            scrollbar = self.scroll_frame._scrollbar
        except AttributeError:
            return

        def _on_yscroll(first, last):
            # Keep CTk's own scrollbar in sync, then refresh the visible rows.
            try:
                scrollbar.set(first, last)
            except Exception:
                pass
            self._request_render()

        canvas.configure(yscrollcommand=_on_yscroll)
        canvas.bind("<Configure>", self._on_canvas_configure, add="+")

    # -------------------------------------------------------------- rendering

    def _on_canvas_configure(self, _event=None):
        """Coalesce the <Configure> storm a window/pane drag produces."""
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
        self._configure_after_id = self.after(40, self._do_render)

    def _request_render(self):
        """Schedule one render on the next idle (collapses rapid triggers)."""
        if self._render_pending:
            return
        self._render_pending = True
        self.after_idle(self._do_render)

    def _do_render(self):
        self._render_pending = False
        self._configure_after_id = None
        if not self.winfo_exists():
            return
        try:
            self._render_visible()
        except tk.TclError:
            pass

    def _visible_range(self):
        """Return (first, last) spell indices that should currently have widgets."""
        n = len(self._spells)
        if n == 0:
            return 0, 0
        try:
            canvas = self.scroll_frame._parent_canvas
            top = canvas.canvasy(0)
            viewport = canvas.winfo_height()
        except (AttributeError, tk.TclError):
            return 0, min(n, self.BUFFER_ROWS * 2)

        if viewport <= 1:
            # Canvas not laid out yet - render a first screenful; a <Configure>
            # will follow once it has a real size.
            return 0, min(n, self.BUFFER_ROWS * 2)

        first = max(0, int(top // self.ROW_STRIDE) - self.BUFFER_ROWS)
        last = int((top + viewport) // self.ROW_STRIDE) + 1 + self.BUFFER_ROWS
        return first, min(n, last)

    def _render_visible(self):
        first, last = self._visible_range()
        count = max(0, last - first)
        self._ensure_pool(count)

        for k in range(count):
            spell_index = first + k
            btn = self._row_pool[k]
            self._bind_row(btn, spell_index)
            # CTk forbids width/height in place(); the row height comes from the
            # CTkButton constructor. relwidth=1 keeps rows spanning the panel.
            btn.place(x=0, y=spell_index * self.ROW_STRIDE, relwidth=1.0)

        # Park any leftover pooled rows off-layout (kept for reuse, not destroyed).
        for k in range(count, len(self._row_pool)):
            self._row_pool[k].place_forget()

    def _ensure_pool(self, count: int):
        """Grow the recycled-row pool to at least ``count`` widgets."""
        while len(self._row_pool) < count:
            btn = ctk.CTkButton(
                self.scroll_frame, text="", anchor="w",
                height=self.ROW_HEIGHT, corner_radius=0, border_width=0,
                fg_color=self._row_bg, hover_color=self._hover,
                text_color=self._text, font=self._font,
            )
            btn._spell_index = -1  # which spell this pooled row currently shows
            btn.configure(command=lambda b=btn: self._on_row_click(b._spell_index))
            bind_right_click(btn, self._on_row_right_click)
            for child in btn.winfo_children():
                try:
                    bind_right_click(child, self._on_row_right_click)
                except Exception:
                    pass
            self._row_pool.append(btn)

    @staticmethod
    def _row_text(spell: Spell) -> str:
        indicators = []
        if spell.ritual:
            indicators.append("R")
        if spell.concentration:
            indicators.append("C")
        suffix = f"  ({', '.join(indicators)})" if indicators else ""
        # display_name adds a trailing * for modified official spells.
        return f"{spell.display_name}{suffix}"

    def _bind_row(self, btn: "ctk.CTkButton", spell_index: int):
        """Point a pooled row widget at ``spell_index``."""
        spell = self._spells[spell_index]
        btn._spell_index = spell_index
        selected = spell_index == self._selected_index
        btn.configure(
            text=self._row_text(spell),
            fg_color=(self._accent if selected else self._row_bg),
        )

    # ------------------------------------------------------------ interaction

    def _on_row_click(self, spell_index: int):
        if not (0 <= spell_index < len(self._spells)):
            return
        self._selected_index = spell_index
        self._render_visible()  # cheap: just recolours the ~20 live rows
        self.on_select(self._spells[spell_index])

    def _on_row_right_click(self, event):
        if not event or not self.on_right_click:
            return
        # event.widget may be the button or one of its internal canvas/label
        # children - walk up to the pooled CTkButton that carries _spell_index.
        widget = event.widget
        while widget is not None and not hasattr(widget, "_spell_index"):
            widget = getattr(widget, "master", None)
        if widget is None:
            return
        idx = widget._spell_index
        if 0 <= idx < len(self._spells):
            self.on_right_click(self._spells[idx], event.x_root, event.y_root)

    # -------------------------------------------------------------- public API

    def set_spells(self, spells: List[Spell], reset_scroll: bool = True):
        """Replace the displayed spells, preserving the current selection by name."""
        current_name = None
        if self._selected_index is not None and self._selected_index < len(self._spells):
            current_name = self._spells[self._selected_index].name

        self._spells = spells

        # Re-locate the previously selected spell in the new list.
        self._selected_index = None
        if current_name:
            lowered = current_name.lower()
            for i, spell in enumerate(spells):
                if spell.name.lower() == lowered:
                    self._selected_index = i
                    break

        count = len(spells)
        self.count_label.configure(
            text=f"{count} spell{'s' if count != 1 else ''}",
            text_color=get_theme_manager().get_text_secondary(),
        )

        self._total_height = max(1, count * self.ROW_STRIDE)
        try:
            self._spacer.configure(height=self._total_height)
        except Exception:
            pass

        if reset_scroll:
            self.scroll_to_top()

        # Spacer height -> canvas scrollregion settles on the next idle tick.
        self._request_render()

    def select_spell(self, name: str) -> bool:
        """Select a spell by name, scrolling it into view. Returns True if found."""
        lowered = name.lower()
        target = None
        for i, spell in enumerate(self._spells):
            if spell.name.lower() == lowered:
                target = i
                break
        if target is None:
            return False

        self._selected_index = target
        self._ensure_visible(target)
        self._do_render()
        self.on_select(self._spells[target])
        return True

    def get_selected_spell(self) -> Optional[Spell]:
        """Return the currently selected spell, or None."""
        if self._selected_index is not None and self._selected_index < len(self._spells):
            return self._spells[self._selected_index]
        return None

    def clear_selection(self):
        """Clear the current selection."""
        self._selected_index = None
        self._do_render()
        self.on_select(None)

    def scroll_to_top(self):
        """Scroll the spell list to the top."""
        try:
            self.scroll_frame._parent_canvas.yview_moveto(0)
        except (AttributeError, tk.TclError):
            pass
        self._request_render()

    # ------------------------------------------------------------------ helpers

    def _ensure_visible(self, spell_index: int):
        """Scroll so ``spell_index``'s row sits inside the viewport."""
        try:
            canvas = self.scroll_frame._parent_canvas
            canvas.update_idletasks()
            top = canvas.canvasy(0)
            viewport = canvas.winfo_height()
        except (AttributeError, tk.TclError):
            return

        row_top = spell_index * self.ROW_STRIDE
        row_bottom = row_top + self.ROW_HEIGHT

        if row_top < top:
            new_top = row_top
        elif row_bottom > top + viewport:
            new_top = row_bottom - viewport
        else:
            return  # already visible

        if self._total_height > 0:
            frac = max(0.0, min(1.0, new_top / self._total_height))
            try:
                canvas.yview_moveto(frac)
            except tk.TclError:
                pass

    def _on_theme_changed(self):
        """Reconfigure colours when the theme changes."""
        try:
            self._refresh_colors()
            try:
                self.configure(fg_color=self._panel_bg)
                self.count_label.configure(text_color=self._secondary_text)
                self.scroll_frame.configure(fg_color=self._row_bg)
            except Exception:
                pass
            for btn in self._row_pool:
                try:
                    btn.configure(hover_color=self._hover, text_color=self._text,
                                  fg_color=self._row_bg)
                except Exception:
                    pass
            self._do_render()  # re-applies the accent to the selected row
        except Exception:
            pass

    def destroy(self):
        """Clean up the theme listener and any pending redraw."""
        if self._configure_after_id is not None:
            try:
                self.after_cancel(self._configure_after_id)
            except Exception:
                pass
        try:
            if getattr(self, "_theme", None):
                self._theme.remove_listener(self._on_theme_changed)
        except Exception:
            pass
        super().destroy()
