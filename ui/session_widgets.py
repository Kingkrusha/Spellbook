"""Small pieces of the session UI that live outside the Session page: the status bar
shown under every tab while a session is running, and the "may this player join?"
prompt the host sees (it can appear on any tab, so it is not part of the page)."""

from typing import Callable, List, Optional

import customtkinter as ctk

from lan.service import CLIENT, HOSTING, JOINING
from theme import get_theme_manager
from typography import ui_font
from ui.tooltip import HoverTooltip


class SessionStatusBar(ctk.CTkFrame):
    """One-line bar: who we are connected to, with shortcuts to the Session page and Leave."""

    def __init__(self, parent, service, on_open: Callable[[], None],
                 on_initiative: Optional[Callable[[], None]] = None):
        theme = get_theme_manager()
        super().__init__(parent, fg_color=theme.get_current_color('bg_tertiary'), corner_radius=0, height=30)
        self.service = service
        self._on_open = on_open

        self.dot = ctk.CTkLabel(self, text="●", width=18, font=ui_font("body"),
                                text_color="#3fb950")      # status green: readable on every theme
        self.dot.pack(side="left", padx=(12, 2))
        self.label = ctk.CTkLabel(self, text="", font=ui_font("body"), anchor="w")
        self.label.pack(side="left", padx=(0, 10))

        self.leave_btn = ctk.CTkButton(
            self, text="Leave", width=60, height=22, font=ui_font("small"),
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            command=lambda: service.leave())
        self.leave_btn.pack(side="right", padx=(4, 12), pady=4)
        ctk.CTkButton(
            self, text="Open Session", width=100, height=22, font=ui_font("small"),
            fg_color=theme.get_current_color('button_normal'),
            hover_color=theme.get_current_color('button_hover'),
            command=on_open).pack(side="right", padx=4, pady=4)
        if on_initiative is not None:
            ctk.CTkButton(
                self, text="⚔ Initiative", width=96, height=22, font=ui_font("small"),
                fg_color=theme.get_current_color('button_normal'),
                hover_color=theme.get_current_color('button_hover'),
                command=on_initiative).pack(side="right", padx=4, pady=4)
        self.refresh()

    def refresh(self) -> None:
        s = self.service
        if s.role == HOSTING:
            n = max(0, len(s.peers) - 1)
            text = f"Hosting a session - {n} player{'s' if n != 1 else ''} connected"
            self.leave_btn.configure(text="End")
        elif s.role == CLIENT:
            text = f"Connected to {s.host_name}'s session - {len(s.peers)} in the room"
            self.leave_btn.configure(text="Leave")
        elif s.role == JOINING:
            text = "Joining a session..."
            self.leave_btn.configure(text="Cancel")
        else:
            text = ""
        waiting = len(getattr(s, "inbox", []))
        if text and waiting:
            text += f"  -  {waiting} item{'s' if waiting != 1 else ''} in your inbox"
        self.label.configure(text=text)


class NameDialog(ctk.CTkToplevel):
    """Asks what name the table should see, every time the player hosts or joins.

    The box starts with whatever they typed last time (empty on the very first use); nothing is read
    from the computer to guess one. ``on_done(name)`` is called once with the trimmed name; closing or
    cancelling calls nothing."""

    NOBODY = "No one yet"

    def __init__(self, parent, initial: str, on_done: Callable[[str], None], hosting: bool = False,
                 characters: Optional[List[str]] = None, character: str = ""):
        super().__init__(parent)
        theme = get_theme_manager()
        self._on_done = on_done
        self.character = ""                       # what was picked under "Playing as" ("" = nobody)
        self.title("Your name")
        self.geometry("400x270" if characters else "400x210")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=22, pady=18)
        ctk.CTkLabel(box, text="What should the table call you?", font=ui_font("heading", 17, bold=True),
                     wraplength=350, justify="left").pack(anchor="w")
        who = "your players" if hosting else "everyone in the session"
        ctk.CTkLabel(box, text=f"This is the name {who} will see in chat and on the initiative tracker. "
                               "It can be a character name.",
                     font=ui_font("body"), text_color=theme.get_text_secondary(), wraplength=350,
                     justify="left").pack(anchor="w", pady=(4, 8))
        self.entry = ctk.CTkEntry(box, height=34, placeholder_text="Your name")
        self.entry.pack(fill="x")
        if initial:
            self.entry.insert(0, initial)
            self.entry.select_range(0, "end")
        self.playing = None
        if characters:
            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(line, text="Playing as", font=ui_font("body")).pack(side="left")
            values = [self.NOBODY] + list(characters)
            self.playing = ctk.StringVar(value=character if character in characters else self.NOBODY)
            ctk.CTkOptionMenu(line, values=values, variable=self.playing, width=220,
                              dynamic_resizing=False).pack(side="left", padx=8)
            HoverTooltip(line, "The DM sees this character's name, hit points, AC and portrait, "
                               "and can give you its token on the tabletop.")
        self.error = ctk.CTkLabel(box, text="", font=ui_font("small"),
                                  text_color=theme.get_current_color('text_warning'))
        self.error.pack(anchor="w", pady=(4, 0))

        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", side="bottom")
        self.ok_btn = ctk.CTkButton(row, text="Start hosting" if hosting else "Join", width=120,
                                    fg_color=theme.get_current_color('accent_primary'),
                                    hover_color=theme.get_current_color('accent_hover'),
                                    command=self._submit)
        self.ok_btn.pack(side="left")
        ctk.CTkButton(row, text="Cancel", width=90, fg_color=theme.get_current_color('button_normal'),
                      hover_color=theme.get_current_color('button_hover'),
                      command=self.destroy).pack(side="right")
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(150, self._focus)               # CTk finishes its own window setup first

    def _focus(self) -> None:
        try:
            self.lift()
            self.entry.focus_set()
        except Exception:
            pass

    def _submit(self) -> None:
        name = " ".join(self.entry.get().split())
        if not name:
            self.error.configure(text="Enter a name to continue.")
            return
        if self.playing is not None and self.playing.get() != self.NOBODY:
            self.character = self.playing.get()
        callback, self._on_done = self._on_done, None
        self.destroy()
        if callback is not None:
            callback(name)


class VerifyDialog(ctk.CTkToplevel):
    """Before joining a session found on the network: compare its security code with the DM's.

    A discovery reply is unauthenticated, so anyone could advertise a fake "Dungeon Master". The
    code is derived from the session's certificate; a fake advertises its own, which won't match
    the one on the real DM's screen. Nothing (not even the password) is sent until you confirm."""

    def __init__(self, parent, found, on_confirm: Callable[[], None]):
        super().__init__(parent)
        theme = get_theme_manager()
        self.title("Check the security code")
        self.geometry("420x250")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=22, pady=18)
        ctk.CTkLabel(box, text=f"Join {found.name}'s session?", font=ui_font("heading", 17, bold=True),
                     wraplength=370, justify="left").pack(anchor="w")
        ctk.CTkLabel(box, text=f"at {found.address}. Ask your DM to read out the security code on their "
                               "Session page. It should match this one:",
                     font=ui_font("body"), text_color=theme.get_text_secondary(), wraplength=370,
                     justify="left").pack(anchor="w", pady=(4, 8))
        ctk.CTkLabel(box, text=found.security_code, font=ui_font("title", 24, bold=True),
                     text_color=theme.get_current_color('text_label')).pack(pady=(0, 6))
        ctk.CTkLabel(box, text="If it doesn't match, don't join - someone else may be pretending to be the DM.",
                     font=ui_font("small"), text_color=theme.get_current_color('text_warning'),
                     wraplength=370, justify="left").pack(anchor="w")
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", side="bottom")
        ctk.CTkButton(row, text="It matches - join", width=140,
                      fg_color=theme.get_current_color('accent_primary'),
                      hover_color=theme.get_current_color('accent_hover'),
                      command=lambda: (self.destroy(), on_confirm())).pack(side="left")
        ctk.CTkButton(row, text="Cancel", width=90, fg_color=theme.get_current_color('button_normal'),
                      hover_color=theme.get_current_color('button_hover'),
                      command=self.destroy).pack(side="right")


class ApprovalDialog(ctk.CTkToplevel):
    """Non-blocking prompt: ``on_answer(True/False)`` is called once, when the DM chooses.

    Closing the window counts as "Deny"."""

    def __init__(self, parent, name: str, address: str, on_answer: Callable[[bool], None], web: bool = False):
        super().__init__(parent)
        theme = get_theme_manager()
        self._on_answer = on_answer
        self._answered = False

        self.title("Player wants to join")
        self.geometry("380x170")
        self.resizable(False, False)
        try:
            self.attributes("-topmost", True)
        except Exception:
            pass

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=20, pady=18)
        ctk.CTkLabel(box, text=f"{name} wants to join your session",
                     font=ui_font("heading", 16, bold=True), wraplength=340, justify="left"
                     ).pack(anchor="w")
        where = f"From a web browser at {address}." if web else f"From {address}."
        ctk.CTkLabel(box, text=f"{where} Only let in people you invited.",
                     font=ui_font("body"), text_color=theme.get_text_secondary(),
                     wraplength=340, justify="left").pack(anchor="w", pady=(4, 14))

        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(fill="x", side="bottom")
        ctk.CTkButton(row, text="Let them in", width=120,
                      fg_color=theme.get_current_color('button_success'),
                      hover_color=theme.get_current_color('button_success_hover'),
                      command=lambda: self._answer(True)).pack(side="left")
        ctk.CTkButton(row, text="Deny", width=90,
                      fg_color=theme.get_current_color('button_danger'),
                      hover_color=theme.get_current_color('button_danger_hover'),
                      command=lambda: self._answer(False)).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", lambda: self._answer(False))

    def _answer(self, accept: bool) -> None:
        if not self._answered:
            self._answered = True
            try:
                self._on_answer(accept)
            finally:
                try:
                    self.destroy()
                except Exception:
                    pass

    def dismiss(self) -> None:
        """Close without answering (it was answered elsewhere, or the session ended)."""
        self._answered = True
        try:
            self.destroy()
        except Exception:
            pass
