"""Sending characters and homebrew to other players, and reviewing what arrives.

* :class:`SendDialog` - pick who to send to and what; builds the payloads (``transfer.py``) and
  hands them to the session.
* :class:`InboxReviewDialog` - look at one received item, decide what to do about anything it clashes
  with, then add it or decline. Nothing is written until the person presses the button.
"""

from __future__ import annotations

import json
from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

import character_io
import content_io
import transfer as X
from lan import protocol as P
from theme import get_theme_manager
from typography import ui_font

EVERYONE = "Everyone else"
MAX_PAYLOAD_BYTES = P.MAX_FRAME - 64 * 1024        # leave room for the envelope


class SendDialog(ctk.CTkToplevel):
    def __init__(self, parent, service, managers: X.Managers, peer_id: Optional[str] = None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.service = service
        self.managers = managers
        self.title("Send characters or homebrew")
        self.geometry("520x640")
        self.minsize(460, 480)
        self.transient(parent.winfo_toplevel())

        self._char_vars: Dict[str, ctk.BooleanVar] = {}
        self._item_vars: List[Tuple[str, object, ctk.BooleanVar]] = []     # (kind, object, var)
        self._peers = {p["name"]: p["peer_id"] for p in service.peers if p["peer_id"] != service.my_id}

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=18, pady=16)

        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text="Send to", font=ui_font("body", bold=True)).pack(side="left", padx=(0, 10))
        names = sorted(self._peers) + ([EVERYONE] if len(self._peers) > 1 else [])
        self._to_var = ctk.StringVar(value=service.peer_name(peer_id) if peer_id else (names[0] if names else ""))
        ctk.CTkOptionMenu(row, values=names or ["(nobody else is here)"], variable=self._to_var,
                          width=200).pack(side="left")

        ctk.CTkLabel(box, text="They look at what you send and choose whether to add it. Homebrew your "
                               "characters use (spells, feats, items...) is included automatically.",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary(),
                     wraplength=470, justify="left").pack(anchor="w", pady=(8, 8))

        self.scroll = ctk.CTkScrollableFrame(box, fg_color=self.theme.get_current_color('bg_secondary'))
        self.scroll.pack(fill="both", expand=True)
        self._fill()

        self.status = ctk.CTkLabel(box, text="", font=ui_font("small"), wraplength=470, justify="left",
                                   text_color=self.theme.get_current_color('text_warning'))
        self.status.pack(anchor="w", pady=(8, 0))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(row, text="📤 Send", width=110, height=34,
                      fg_color=self.theme.get_current_color('accent_primary'),
                      hover_color=self.theme.get_current_color('accent_hover'),
                      command=self._send).pack(side="left")
        ctk.CTkButton(row, text="Cancel", width=90, height=34,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover'),
                      command=self.destroy).pack(side="right")

    # ------------------------------------------------------------------ content

    def _header(self, text: str):
        ctk.CTkLabel(self.scroll, text=text, font=ui_font("body", bold=True)).pack(anchor="w", padx=6, pady=(10, 2))

    def _fill(self):
        cm = self.managers.character_manager
        characters = cm.characters
        self._header("Characters")
        if not characters:
            ctk.CTkLabel(self.scroll, text="You have no characters yet.", font=ui_font("small"),
                         text_color=self.theme.get_text_secondary()).pack(anchor="w", padx=14)
        for char in characters:
            var = ctk.BooleanVar(value=False)
            self._char_vars[char.name] = var
            classes = ", ".join(f"{c.get_class_name()} {c.level}" for c in char.classes)
            ctk.CTkCheckBox(self.scroll, text=f"{char.name}" + (f"  ({classes})" if classes else ""),
                            variable=var).pack(anchor="w", padx=14, pady=2)

        any_homebrew = False
        for kind in content_io.DISPLAY_ORDER:
            try:
                objs = content_io.unofficial_objects(kind, self.managers.spell_manager)
            except Exception:
                objs = []
            objs = [o for o in objs if not getattr(o, "spell_only", False)]
            if not objs:
                continue
            if not any_homebrew:
                self._header("Your homebrew")
                any_homebrew = True
            ctk.CTkLabel(self.scroll, text=content_io.label(kind), font=ui_font("small", bold=True),
                         text_color=self.theme.get_text_secondary()).pack(anchor="w", padx=10, pady=(6, 0))
            for obj in sorted(objs, key=lambda o: o.name.lower()):
                var = ctk.BooleanVar(value=False)
                self._item_vars.append((kind, obj, var))
                ctk.CTkCheckBox(self.scroll, text=obj.name, variable=var).pack(anchor="w", padx=18, pady=1)
        if not any_homebrew:
            self._header("Your homebrew")
            ctk.CTkLabel(self.scroll, text="You have no homebrew content yet.", font=ui_font("small"),
                         text_color=self.theme.get_text_secondary()).pack(anchor="w", padx=14)

    # --------------------------------------------------------------------- send

    def _recipients(self) -> List[str]:
        target = self._to_var.get()
        if target == EVERYONE:
            return list(self._peers.values())
        return [self._peers[target]] if target in self._peers else []

    def _send(self):
        recipients = self._recipients()
        if not recipients:
            self.status.configure(text="There is nobody to send to.")
            return
        chosen_chars = [n for n, v in self._char_vars.items() if v.get()]
        chosen_items: Dict[str, list] = {}
        for kind, obj, var in self._item_vars:
            if var.get():
                chosen_items.setdefault(kind, []).append(obj)
        if not chosen_chars and not chosen_items:
            self.status.configure(text="Tick at least one character or homebrew item.")
            return

        payloads: List[Tuple[dict, str]] = []
        try:
            if chosen_chars:
                title = chosen_chars[0] if len(chosen_chars) == 1 else f"{len(chosen_chars)} characters"
                payloads.append((X.build_character_payload(
                    chosen_chars, self.managers.character_manager, self.managers.sheet_manager,
                    self.managers.spell_manager), title))
            if chosen_items:
                total = sum(len(v) for v in chosen_items.values())
                only = next(iter(chosen_items.values()))[0].name if total == 1 else f"{total} homebrew items"
                payloads.append((X.build_content_payload(chosen_items, self.managers.spell_manager), only))
        except X.TransferError as e:
            self.status.configure(text=str(e))
            return
        for payload, _title in payloads:
            if len(json.dumps(payload, separators=(",", ":"))) > MAX_PAYLOAD_BYTES:
                self.status.configure(text="That is too much to send in one go. Send fewer items at a time.")
                return

        sent = 0
        for payload, title in payloads:
            for peer_id in recipients:
                if self.service.send_transfer(peer_id, payload, title):
                    sent += 1
        if not sent:
            self.status.configure(text="Could not send - are you still connected?")
            return
        self.destroy()


class InboxReviewDialog(ctk.CTkToplevel):
    """Decide what to do with one received transfer."""

    KEEP_BOTH, REPLACE, SKIP = "Keep both", "Replace mine", "Keep mine (skip)"

    def __init__(self, parent, service, item: dict, managers: X.Managers,
                 on_done: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.service, self.item, self.managers, self.on_done = service, item, managers, on_done
        self.title(f"From {item['name']}")
        self.geometry("560x600")
        self.minsize(480, 420)
        self.transient(parent.winfo_toplevel())

        self._char_vars: Dict[str, ctk.StringVar] = {}
        self._content_vars: Dict[Tuple[str, str], ctk.StringVar] = {}
        self.parsed: Optional[X.Parsed] = None
        self.plan: Optional[X.TransferPlan] = None
        self._error = ""
        try:
            self.parsed = X.parse_payload(item["payload"])
            self.plan = X.plan_transfer(self.parsed, managers)
        except X.TransferError as e:
            self._error = str(e)
        except Exception as e:                                   # a surprise must not kill the app
            self._error = f"Could not read this transfer: {e}"
        self._build()

    # ------------------------------------------------------------------- layout

    def _build(self):
        t = self.theme
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=18, pady=16)
        ctk.CTkLabel(box, text=f"{self.item['name']} sent you \"{self.item['title']}\"",
                     font=ui_font("heading", 17, bold=True), wraplength=510, justify="left").pack(anchor="w")

        if self.parsed is None:
            ctk.CTkLabel(box, text=self._error, font=ui_font("body"), wraplength=510, justify="left",
                         text_color=t.get_current_color('text_warning')).pack(anchor="w", pady=(10, 0))
            self._buttons(box, can_accept=False)
            return

        body = ctk.CTkScrollableFrame(box, fg_color=t.get_current_color('bg_secondary'))
        body.pack(fill="both", expand=True, pady=(10, 0))

        try:
            from version import __version__ as mine
        except Exception:
            mine = ""
        if self.parsed.app_version and mine and self.parsed.app_version != mine:
            ctk.CTkLabel(body, text=f"⚠ Sent from Spellbook {self.parsed.app_version}; you have {mine}. "
                                    "Official content may differ between versions.",
                         font=ui_font("small"), wraplength=470, justify="left",
                         text_color=t.get_current_color('text_warning')).pack(anchor="w", padx=8, pady=(6, 0))

        ctk.CTkLabel(body, text="What's in it", font=ui_font("body", bold=True)).pack(anchor="w", padx=8, pady=(8, 2))
        for line in X.describe(self.parsed):
            ctk.CTkLabel(body, text="• " + line, font=ui_font("small"), wraplength=470, justify="left",
                         text_color=t.get_text_secondary()).pack(anchor="w", padx=14)

        # characters you already have
        if self.plan.character_conflicts:
            ctk.CTkLabel(body, text="Characters you already have", font=ui_font("body", bold=True)
                         ).pack(anchor="w", padx=8, pady=(12, 2))
            for name in self.plan.character_conflicts:
                self._choice_row(body, name, self._char_vars, name, default=self.KEEP_BOTH)

        # homebrew you already have
        preview = self.plan.content
        if preview is not None and preview.replaces:
            ctk.CTkLabel(body, text="Homebrew with the same name as yours", font=ui_font("body", bold=True)
                         ).pack(anchor="w", padx=8, pady=(12, 2))
            default = self.SKIP if self.parsed.kind == X.KIND_CHARACTER else self.KEEP_BOTH
            if self.parsed.kind == X.KIND_CHARACTER:
                ctk.CTkLabel(body, text="The character will use your version unless you replace it.",
                             font=ui_font("small"), text_color=t.get_text_secondary(), wraplength=470,
                             justify="left").pack(anchor="w", padx=14)
            for kind, name in preview.replaces:
                self._choice_row(body, f"{name}  ({content_io.singular(kind)})", self._content_vars,
                                 (kind, name.lower()), default=default)
        if preview is not None and preview.official:
            names = ", ".join(n for _k, n in preview.official[:8])
            more = f" and {len(preview.official) - 8} more" if len(preview.official) > 8 else ""
            ctk.CTkLabel(body, text=f"Skipped, because official content already uses the name: {names}{more}",
                         font=ui_font("small"), wraplength=470, justify="left",
                         text_color=t.get_text_secondary()).pack(anchor="w", padx=8, pady=(10, 0))

        self._buttons(box, can_accept=True)

    def _choice_row(self, parent, label: str, store: dict, key, default: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text=label, font=ui_font("small"), anchor="w").pack(side="left", padx=(6, 8))
        var = ctk.StringVar(value=default)
        store[key] = var
        ctk.CTkOptionMenu(row, values=[self.KEEP_BOTH, self.REPLACE, self.SKIP], variable=var,
                          width=150, height=26).pack(side="right")

    def _buttons(self, box, can_accept: bool):
        t = self.theme
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", pady=(10, 0))
        if can_accept:
            ctk.CTkButton(row, text="Add to my collection", width=170, height=36,
                          fg_color=t.get_current_color('button_success'),
                          hover_color=t.get_current_color('button_success_hover'),
                          command=self._accept).pack(side="left")
        ctk.CTkButton(row, text="Decline", width=100, height=36,
                      fg_color=t.get_current_color('button_danger'),
                      hover_color=t.get_current_color('button_danger_hover'),
                      command=self._decline).pack(side="right")
        ctk.CTkButton(row, text="Decide later", width=110, height=36,
                      fg_color=t.get_current_color('button_normal'),
                      hover_color=t.get_current_color('button_hover'),
                      command=self.destroy).pack(side="right", padx=8)

    # ------------------------------------------------------------------ actions

    def _decline(self):
        self.service.decline_item(self.item["item_id"])
        self._finish()

    def _accept(self):
        words = {self.KEEP_BOTH: (content_io.CLASH_RENAME, character_io.RENAME),
                 self.REPLACE: (content_io.CLASH_REPLACE, character_io.REPLACE),
                 self.SKIP: (content_io.CLASH_SKIP, character_io.SKIP)}
        content_decisions = {key: words[var.get()][0] for key, var in self._content_vars.items()}
        char_policies = {name: words[var.get()][1] for name, var in self._char_vars.items()}
        try:
            result = X.apply_transfer(self.parsed, self.managers, content_decisions, char_policies)
        except Exception as e:
            messagebox.showerror("Could not add it", f"Something went wrong, and nothing was changed:\n{e}",
                                 parent=self)
            self.service.finish_item(self.item["item_id"], "failed", "It could not be added.")
            self._finish()
            return
        self.service.finish_item(self.item["item_id"], "imported")
        lines = result.lines() or ["Nothing new was added."]
        problems = result.problems()
        text = "\n".join(lines)
        if problems:
            text += "\n\nNotes:\n" + "\n".join(problems[:8])
        (messagebox.showwarning if problems else messagebox.showinfo)("Added", text, parent=self)
        self._finish()

    def _finish(self):
        try:
            self.destroy()
        finally:
            if self.on_done:
                self.on_done()
