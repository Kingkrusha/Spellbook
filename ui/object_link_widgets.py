"""
UI layer for universal object linking: the small floating suggestion popup,
the generic (and class/subclass-specialized) detail popup, and the
`LinkAwareText` behavior that turns any CTkTextbox into a linkable text field.

Attach it via `attach_object_linking(text_widget, theme)`, or get it for free
on every RichTextEditor-managed textbox (spells, feats, lineages, backgrounds,
equipment, magic items, classes/subclasses all go through RichTextEditor).
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from theme import get_theme_manager
from ui.platform_compat import bind_right_click
from object_links import (
    LINK_CATEGORIES,
    LINK_MARKUP_RE,
    LinkTarget,
    find_target,
    format_link_markup,
    get_link_targets,
    parse_link_markup,
    search_links,
)

_MIN_QUERY_LEN = 3
_SUGGEST_DEBOUNCE_MS = 250
# Trailing run of "word" characters immediately before the cursor. Deliberately
# not Tk's own wordstart/wordend: those misjudge the boundary exactly when the
# cursor sits right after the last character just typed, with no character
# after it yet - precisely the moment a live-typing suggestion needs to fire.
_TRAILING_WORD_RE = re.compile(r"[A-Za-z']+$")
_IGNORED_KEYSYMS = {
    "Up", "Down", "Left", "Right", "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Caps_Lock", "Tab", "Escape",
}


def open_link_popup(parent, category: str, name: str):
    """Open the right popup for an existing (category, name) link, or warn if
    the target can no longer be found (renamed/deleted since the link was made)."""
    if category == "spell":
        from ui.rich_text_utils import RichTextRenderer
        RichTextRenderer().show_spell_popup(parent, name)
        return
    target = find_target(category, name)
    if target is None:
        messagebox.showwarning(
            "Link Not Found",
            f"Couldn't find \"{name}\" ({LINK_CATEGORIES.get(category, category)}). "
            "It may have been renamed or removed.",
            parent=parent.winfo_toplevel(),
        )
        return
    LinkPopup(parent.winfo_toplevel(), target).focus()


# --------------------------------------------------------------------------- #
# Detail popup
# --------------------------------------------------------------------------- #

class LinkPopup(ctk.CTkToplevel):
    """Read-only detail popup for any non-spell link target.

    Classes and subclasses get a taller window and a features list, since
    dumping their full text at the same size as a one-line item description
    reads badly.
    """

    def __init__(self, parent, target: LinkTarget):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.target = target
        self.obj = target.get_object()

        big = target.category in ("class", "subclass")
        self.title(target.name)
        self.geometry("560x680" if big else "480x520")
        self.minsize(420, 380)
        self.resizable(True, True)
        self.transient(parent)

        self._build()

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.lift()

    def _build(self):
        theme = self.theme
        scroll = ctk.CTkScrollableFrame(self, fg_color=theme.get_current_color('bg_primary'))
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            scroll, text=self.target.name, font=ctk.CTkFont(size=22, weight="bold"),
            wraplength=460, justify="left", anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        badge_row = ctk.CTkFrame(scroll, fg_color="transparent")
        badge_row.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            badge_row, text=self.target.category_label, font=ctk.CTkFont(size=11),
            fg_color=theme.get_current_color('accent_primary'), corner_radius=5, padx=8, pady=2,
        ).pack(side="left", padx=(0, 6))
        if self.target.subtitle:
            ctk.CTkLabel(
                badge_row, text=self.target.subtitle, font=ctk.CTkFont(size=11),
                text_color=theme.get_text_secondary(),
            ).pack(side="left")

        if self.obj is None:
            ctk.CTkLabel(
                scroll, text="Couldn't load details for this item.",
                text_color=theme.get_text_secondary(),
            ).pack(anchor="w", pady=20)
            return

        renderer = {
            "feat": self._render_feat,
            "lineage": self._render_lineage,
            "background": self._render_background,
            "equipment": self._render_equipment_like,
            "magic_item": self._render_equipment_like,
            "class": self._render_class,
            "subclass": self._render_subclass,
        }.get(self.target.category)
        if renderer:
            renderer(scroll)
        else:
            self._render_description(scroll, getattr(self.obj, "description", ""))

    # ---- shared pieces ---------------------------------------------------

    def _stat_line(self, parent, parts: List[str]):
        if not parts:
            return
        ctk.CTkLabel(
            parent, text="   •   ".join(parts), font=ctk.CTkFont(size=13),
            text_color=self.theme.get_text_secondary(), anchor="w", justify="left",
        ).pack(anchor="w", pady=(0, 8))

    def _section_title(self, parent, text: str):
        ctk.CTkLabel(
            parent, text=text, font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(12, 4))

    def _render_description(self, parent, text: str):
        from ui.rich_text_utils import DynamicText

        if not text:
            return
        for paragraph in text.split("\n\n"):
            if not paragraph.strip():
                continue
            dt = DynamicText(
                parent, self.theme, bg_color='bg_primary',
                on_spell_click=lambda inner: open_link_popup(self, *parse_link_markup(inner)[:2]),
            )
            dt.set_text(paragraph.strip())
            dt.pack(fill="x", expand=True, pady=(2, 2))

    def _named_entries(self, parent, entries: List[Tuple[str, str]], empty_ok: bool = True):
        """Render a list of (name, description) pairs - traits, features, etc."""
        for name, desc in entries:
            row = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(
                row, text=name, font=ctk.CTkFont(size=13, weight="bold"),
                text_color=self.theme.get_current_color('accent_primary'), anchor="w",
            ).pack(anchor="w", padx=10, pady=(6, 0))
            if desc:
                ctk.CTkLabel(
                    row, text=desc, font=ctk.CTkFont(size=11), wraplength=460,
                    justify="left", anchor="w",
                ).pack(anchor="w", padx=10, pady=(0, 8))
            else:
                ctk.CTkFrame(row, height=4, fg_color="transparent").pack()

    # ---- per-category renderers -------------------------------------------

    def _render_feat(self, parent):
        f = self.obj
        parts = []
        if f.type:
            parts.append(f.type)
        if f.has_prereq and f.prereq:
            parts.append(f"Prerequisite: {f.prereq}")
        self._stat_line(parent, parts)
        self._render_description(parent, f.description)

    def _render_lineage(self, parent):
        l = self.obj
        self._stat_line(parent, [l.creature_type, l.size, f"Speed {l.speed} ft."])
        self._render_description(parent, l.description)
        if l.traits:
            self._section_title(parent, "Traits")
            self._named_entries(parent, [(t.name, t.description) for t in l.traits])

    def _render_background(self, parent):
        b = self.obj
        parts = []
        if b.skills:
            parts.append("Skills: " + ", ".join(b.skills))
        if b.ability_scores:
            parts.append("Abilities: " + ", ".join(b.ability_scores))
        self._stat_line(parent, parts)
        self._render_description(parent, b.description)
        if b.features:
            self._section_title(parent, "Features")
            self._named_entries(parent, [(ft.name, ft.description) for ft in b.features])

    def _render_equipment_like(self, parent):
        item = self.obj
        parts = []
        if getattr(item, "cost", ""):
            parts.append(f"Cost: {item.cost}")
        if getattr(item, "weight", 0):
            parts.append(f"Weight: {item.display_weight()}")
        rarity = getattr(item, "rarity", None)
        if rarity is not None:
            parts.append(rarity.value)
        attunement = getattr(item, "display_attunement", None)
        if callable(attunement) and attunement():
            parts.append(attunement())
        self._stat_line(parent, parts)

        tags = getattr(item, "tags", None)
        if tags:
            ctk.CTkLabel(
                parent, text=item.display_tags(), font=ctk.CTkFont(size=12),
                text_color=self.theme.get_current_color('accent_primary'),
                wraplength=460, justify="left", anchor="w",
            ).pack(anchor="w", pady=(0, 8))

        properties = getattr(item, "properties", None)
        if properties:
            self._section_title(parent, "Properties")
            self._named_entries(parent, [(p.get("name", ""), p.get("description", "")) for p in properties])

        self._render_description(parent, item.description)

    def _render_class(self, parent):
        c = self.obj
        self._stat_line(parent, [f"Hit Die: {c.hit_die}", c.primary_ability or ""])
        if c.saving_throw_proficiencies:
            ctk.CTkLabel(
                parent, text="Saving Throws: " + ", ".join(c.saving_throw_proficiencies),
                font=ctk.CTkFont(size=12), text_color=self.theme.get_text_secondary(), anchor="w",
            ).pack(anchor="w", pady=(0, 8))
        self._render_description(parent, c.description)

        levels = getattr(c, "levels", {}) or {}
        if levels:
            self._section_title(parent, "Features")
            list_frame = ctk.CTkFrame(parent, fg_color="transparent")
            list_frame.pack(fill="x")
            for level in sorted(levels):
                for ability in levels[level].abilities:
                    if ability.is_subclass_feature:
                        continue
                    ctk.CTkLabel(
                        list_frame, text=f"Level {level} — {ability.title}",
                        font=ctk.CTkFont(size=12), anchor="w", justify="left", wraplength=460,
                    ).pack(anchor="w", pady=1)

    def _render_subclass(self, parent):
        s = self.obj
        self._stat_line(parent, [f"{s.parent_class} Subclass"])
        self._render_description(parent, s.description)
        if s.features:
            self._section_title(parent, "Features")
            list_frame = ctk.CTkFrame(parent, fg_color="transparent")
            list_frame.pack(fill="x")
            for feature in sorted(s.features, key=lambda x: x.level):
                ctk.CTkLabel(
                    list_frame, text=f"Level {feature.level} — {feature.title}",
                    font=ctk.CTkFont(size=12), anchor="w", justify="left", wraplength=460,
                ).pack(anchor="w", pady=1)


# --------------------------------------------------------------------------- #
# Floating suggestion popup
# --------------------------------------------------------------------------- #

class LinkSuggestionPopup(ctk.CTkToplevel):
    """The small "link this word?" popup - up to 2 rows for as-you-type
    suggestions, or every match (scrollable) for "Find link suggestions"."""

    def __init__(self, parent, matches: List[LinkTarget], on_pick: Callable[[LinkTarget], None],
                 on_close: Callable[[], None], theme=None, scrollable: bool = False):
        super().__init__(parent)
        self.theme = theme or get_theme_manager()
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        border = self.theme.get_current_color('border')
        bg = self.theme.get_current_color('bg_secondary')

        outer = ctk.CTkFrame(self, fg_color=bg, border_color=border, border_width=1, corner_radius=8)
        outer.pack()

        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            header, text=f"{len(matches)} link suggestion{'s' if len(matches) != 1 else ''}",
            font=ctk.CTkFont(size=11), text_color=self.theme.get_text_secondary(),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="×", width=20, height=20, fg_color="transparent",
            hover_color=self.theme.get_current_color('button_danger'),
            text_color=self.theme.get_current_color('text_primary'),
            font=ctk.CTkFont(size=13, weight="bold"), command=self._on_close,
        ).pack(side="right")

        if scrollable and len(matches) > 6:
            body = ctk.CTkScrollableFrame(outer, fg_color="transparent", width=300, height=220)
        else:
            body = ctk.CTkFrame(outer, fg_color="transparent", width=300)
        body.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        for target in matches:
            row = ctk.CTkButton(
                body, anchor="w",
                text=f"{target.name}   ({target.category_label}"
                     f"{' · ' + target.subtitle if target.subtitle else ''})",
                fg_color="transparent",
                hover_color=self.theme.get_current_color('accent_primary'),
                text_color=self.theme.get_current_color('text_primary'),
                font=ctk.CTkFont(size=12),
                command=lambda t=target: on_pick(t),
            )
            row.pack(fill="x", pady=1)

        self._on_close_cb = on_close
        self.bind("<Escape>", lambda _e: self._on_close())

    def _on_close(self):
        try:
            self._on_close_cb()
        finally:
            try:
                self.destroy()
            except Exception:
                pass

    def position_above(self, root_x: int, root_y: int):
        self.update_idletasks()
        h = self.winfo_height()
        y = root_y - h - 6
        if y < 0:
            y = root_y + 20  # not enough room above - drop it below instead
        self.geometry(f"+{max(root_x - 10, 0)}+{max(y, 0)}")


# --------------------------------------------------------------------------- #
# The text-widget behavior
# --------------------------------------------------------------------------- #

class LinkAwareText:
    """Attach to any CTkTextbox/tk.Text to get:

    - as-you-type suggestions (top 2 matches) while the word under the cursor
      matches a linkable object,
    - click a suggestion to turn the typed word into a link,
    - click an existing link to open its popup,
    - right-click a selection for "Find Link Suggestions" (every match),
    - right-click an existing link for "Unlink".

    Stored/round-tripped text uses `[[category:Name]]` / `[[category:Name|display]]`
    markup (see object_links.py); this class keeps that markup and the live,
    colored, clickable rendering in sync transparently by wrapping the
    widget's own `insert`/`get`/`delete`.
    """

    def __init__(self, text_widget, theme=None, get_popup_parent: Optional[Callable[[], object]] = None):
        self.text_widget = text_widget
        self.theme = theme or get_theme_manager()
        self._get_popup_parent = get_popup_parent or (lambda: self.text_widget.winfo_toplevel())
        self._links: Dict[str, Tuple[str, str, str]] = {}
        self._next_id = 0
        self._suggestion_popup: Optional[LinkSuggestionPopup] = None
        self._suggest_after_id = None
        self._materializing = False

        self._configure_tag()
        self.theme.add_listener(self._on_theme_changed)

        # Wrap the raw Text methods so every insertion path (typing, the rich
        # toolbar, or an editor populating itself from a saved item) stays in
        # sync without each call site needing to know about links at all.
        self._raw = getattr(text_widget, "_textbox", text_widget)
        self._orig_insert = text_widget.insert
        self._orig_get = text_widget.get
        self._orig_delete = text_widget.delete
        text_widget.insert = self._wrapped_insert
        text_widget.get = self._wrapped_get

        text_widget.bind("<KeyRelease>", self._on_key_release, add="+")
        text_widget.bind("<Button-1>", self._on_left_click, add="+")
        bind_right_click(text_widget, self._on_right_click, add=True)
        self._host_click_binding: Optional[str] = None

    # ---- theme -------------------------------------------------------------

    def _configure_tag(self):
        color = self.theme.get_current_color('spell_link')
        self.text_widget.tag_config("obj_link", foreground=color, underline=True)

    def _on_theme_changed(self):
        try:
            self._configure_tag()
        except Exception:
            pass

    # ---- wrapped Text methods ----------------------------------------------

    def _wrapped_insert(self, index, text, *args, **kwargs):
        result = self._orig_insert(index, text, *args, **kwargs)
        if not self._materializing:
            self.text_widget.after_idle(self._rescan_raw_markup)
        return result

    def _wrapped_get(self, index1, index2=None):
        if not self._materializing and index1 in ("1.0", 1.0) and index2 in ("end-1c", "end", None):
            return self.get_markup_text()
        return self._orig_get(index1, index2)

    # ---- content <-> markup -------------------------------------------------

    def set_content(self, markup_text: str):
        """Replace the whole widget content, materializing any `[[...]]` markup
        into live links. Used to populate an editor from a saved description."""
        self._materializing = True
        try:
            self._orig_delete("1.0", "end")
            self._links.clear()
            pos = 0
            for m in LINK_MARKUP_RE.finditer(markup_text):
                if m.start() > pos:
                    self._orig_insert("end", markup_text[pos:m.start()])
                category, name, display = parse_link_markup(m.group(1))
                self._create_link("end", category, name, display)
                pos = m.end()
            if pos < len(markup_text):
                self._orig_insert("end", markup_text[pos:])
        finally:
            self._materializing = False

    def get_markup_text(self) -> str:
        """Reconstruct the storable markup string from the live widget content."""
        try:
            dump = self._raw.dump("1.0", "end-1c", tag=True, text=True)
        except Exception:
            return self._orig_get("1.0", "end-1c")

        parts: List[str] = []
        active: Optional[str] = None
        active_text = ""
        for key, value, _index in dump:
            if key == "tagon" and value.startswith("objlink_"):
                active = value
                active_text = ""
            elif key == "tagoff" and value == active:
                entry = self._links.get(active)
                if entry:
                    category, name, _stale_display = entry
                    # Use the text actually on screen, not the stored display -
                    # the user may have edited inside the link (fixed a typo)
                    # since it was created.
                    parts.append(format_link_markup(category, name, active_text or name))
                active = None
            elif key == "text" and active is None:
                parts.append(value)
            elif key == "text":
                active_text += value
        if active is not None:
            # A link's tagged range reached the very end of the dumped
            # content, so Tk never emitted its closing "tagoff" - dump() only
            # reports transitions strictly inside [index1, index2).
            entry = self._links.get(active)
            if entry:
                category, name, _stale_display = entry
                parts.append(format_link_markup(category, name, active_text or name))
        return "".join(parts)

    def _rescan_raw_markup(self):
        """Convert one literal `[[...]]` span (typed or pasted) into a live
        link in place. Re-runs itself if more than one is present."""
        if self._materializing:
            return
        content = self._orig_get("1.0", "end-1c")
        m = LINK_MARKUP_RE.search(content)
        if not m:
            return
        self._materializing = True
        try:
            start = self.text_widget.index(f"1.0 + {m.start()} chars")
            end = self.text_widget.index(f"1.0 + {m.end()} chars")
            category, name, display = parse_link_markup(m.group(1))
            self._orig_delete(start, end)
            self._create_link(start, category, name, display)
        finally:
            self._materializing = False
        self.text_widget.after_idle(self._rescan_raw_markup)

    def _create_link(self, at: str, category: str, name: str, display: str):
        tag_id = f"objlink_{self._next_id}"
        self._next_id += 1
        start = self.text_widget.index(at)
        self._orig_insert(at, display)
        end = self.text_widget.index(f"{start} + {len(display)} chars")
        self.text_widget.tag_add("obj_link", start, end)
        self.text_widget.tag_add(tag_id, start, end)
        self._links[tag_id] = (category, name, display)
        self.text_widget.mark_set("insert", end)
        return tag_id

    def _unlink(self, tag_id: str):
        ranges = self.text_widget.tag_ranges(tag_id)
        if len(ranges) >= 2:
            self.text_widget.tag_remove("obj_link", ranges[0], ranges[1])
            self.text_widget.tag_remove(tag_id, ranges[0], ranges[1])
        self._links.pop(tag_id, None)

    def _link_tag_at(self, index: str) -> Optional[str]:
        for t in self.text_widget.tag_names(index):
            if t.startswith("objlink_"):
                return t
        return None

    # ---- click handling ------------------------------------------------

    def _on_left_click(self, event):
        try:
            index = self.text_widget.index(f"@{event.x},{event.y}")
        except Exception:
            return
        tag_id = self._link_tag_at(index)
        if tag_id:
            entry = self._links.get(tag_id)
            if entry:
                open_link_popup(self._get_popup_parent(), entry[0], entry[1])

    def _on_right_click(self, event):
        try:
            index = self.text_widget.index(f"@{event.x},{event.y}")
        except Exception:
            index = None

        tag_id = self._link_tag_at(index) if index else None
        has_selection = bool(self.text_widget.tag_ranges("sel"))

        theme = self.theme
        menu = tk.Menu(self.text_widget, tearoff=0)
        menu.configure(
            bg=theme.get_current_color('bg_secondary'), fg=theme.get_current_color('text_primary'),
            activebackground=theme.get_current_color('accent_primary'),
            activeforeground=theme.get_current_color('text_primary'),
        )

        if tag_id:
            entry = self._links.get(tag_id)
            menu.add_command(label="Open Link",
                             command=lambda: entry and open_link_popup(self._get_popup_parent(), entry[0], entry[1]))
            menu.add_command(label="Unlink", command=lambda: self._unlink(tag_id))
            menu.add_separator()
        if has_selection:
            menu.add_command(label="Find Link Suggestions",
                             command=lambda: self._find_all_suggestions(event))
            menu.add_separator()
        menu.add_command(label="Cut", command=lambda: self.text_widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: self.text_widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: self.text_widget.event_generate("<<Paste>>"))

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    # ---- as-you-type suggestions ------------------------------------------

    def _on_key_release(self, event):
        self._hide_suggestions()
        if event.keysym in _IGNORED_KEYSYMS:
            return
        if self._suggest_after_id:
            try:
                self.text_widget.after_cancel(self._suggest_after_id)
            except Exception:
                pass
        self._suggest_after_id = self.text_widget.after(_SUGGEST_DEBOUNCE_MS, self._maybe_suggest)

    def _current_word_range(self) -> Optional[Tuple[str, str, str]]:
        """The run of letters immediately before the cursor, as (start, end, word)."""
        try:
            line_start = self.text_widget.index("insert linestart")
            end = self.text_widget.index("insert")
            prefix = self.text_widget.get(line_start, end)
        except Exception:
            return None
        m = _TRAILING_WORD_RE.search(prefix)
        if not m:
            return None
        word = m.group(0)
        start = self.text_widget.index(f"{end} - {len(word)} chars")
        return start, end, word

    def _maybe_suggest(self):
        self._suggest_after_id = None
        found = self._current_word_range()
        if not found:
            return
        word_start, word_end, word = found
        if self._link_tag_at(word_start) or self._link_tag_at("insert - 1 chars"):
            return  # already linked - don't suggest re-linking it
        if len(word) < _MIN_QUERY_LEN:
            return
        targets = get_link_targets(enabled_only=True)
        matches = search_links(word, targets, limit=2)
        if not matches:
            return
        self._show_suggestions(matches, word_start, word_end, scrollable=False)

    def _find_all_suggestions(self, _event):
        try:
            sel_start = self.text_widget.index("sel.first")
            sel_end = self.text_widget.index("sel.last")
            query = self.text_widget.get(sel_start, sel_end).strip()
        except tk.TclError:
            return
        if not query:
            return
        targets = get_link_targets(enabled_only=True)
        matches = search_links(query, targets)
        if not matches:
            messagebox.showinfo(
                "No Matches", f'No linkable objects found matching "{query}".',
                parent=self.text_widget.winfo_toplevel(),
            )
            return
        self._show_suggestions(matches, sel_start, sel_end, scrollable=True)

    def _show_suggestions(self, matches: List[LinkTarget], start: str, end: str, scrollable: bool):
        self._hide_suggestions()
        try:
            # Use the raw inner Text widget for *both* the bbox and the root
            # position it's measured against - mixing the CTkTextbox wrapper's
            # winfo_rootx/y (the outer frame's origin) with bbox() (returned
            # relative to the inner widget) is off by the wrapper's border/
            # padding, which is what made the popup land in the wrong spot.
            bbox = self._raw.bbox(start)
        except Exception:
            bbox = None
        if not bbox:
            return
        x, y, _w, _h = bbox
        root_x = self._raw.winfo_rootx() + x
        root_y = self._raw.winfo_rooty() + y

        def on_pick(target: LinkTarget):
            self._apply_link(start, end, target)
            self._hide_suggestions()

        popup = LinkSuggestionPopup(
            self.text_widget.winfo_toplevel(), matches, on_pick=on_pick,
            on_close=self._hide_suggestions, theme=self.theme, scrollable=scrollable,
        )
        popup.position_above(root_x, root_y)
        self._suggestion_popup = popup

        # Dismiss if the user clicks elsewhere in the *same* window. A click
        # landing on the popup itself is delivered to its own toplevel and
        # never reaches this handler, so there's no race with picking a
        # suggestion (unlike binding <FocusOut> on the text widget, which
        # fired - and destroyed the popup's buttons - before their own click
        # finished, silently swallowing every pick).
        host = self.text_widget.winfo_toplevel()
        self._host_click_binding = host.bind("<Button-1>", lambda _e: self._hide_suggestions(), add="+")
        self._host_for_click_binding = host

    def _hide_suggestions(self):
        if self._host_click_binding is not None:
            try:
                self._host_for_click_binding.unbind("<Button-1>", self._host_click_binding)
            except Exception:
                pass
            self._host_click_binding = None
        if self._suggestion_popup is not None:
            popup, self._suggestion_popup = self._suggestion_popup, None
            try:
                popup.destroy()
            except Exception:
                pass

    def _apply_link(self, start: str, end: str, target: LinkTarget):
        typed = self._orig_get(start, end)
        display = typed
        try:
            from settings import get_settings_manager
            autocomplete = getattr(get_settings_manager().settings, 'link_autocomplete_names', True)
        except Exception:
            autocomplete = True
        if autocomplete:
            # Correct what was typed to the object's real name, e.g. "fire"
            # -> "Fire Bolt" (case-preserving substring is not attempted -
            # the point is to end up with the canonical name on screen).
            display = target.name
        self._materializing = True
        try:
            self._orig_delete(start, end)
            self._create_link(start, target.category, target.name, display)
        finally:
            self._materializing = False
        self.text_widget.focus_set()


def attach_object_linking(text_widget, theme=None,
                          get_popup_parent: Optional[Callable[[], object]] = None) -> LinkAwareText:
    """Turn `text_widget` (a CTkTextbox or tk.Text) into a linkable field."""
    return LinkAwareText(text_widget, theme=theme, get_popup_parent=get_popup_parent)
