"""Small pieces of the session UI that live outside the Session page: the status bar
shown under every tab while a session is running, and the "may this player join?"
prompt the host sees (it can appear on any tab, so it is not part of the page)."""

from typing import Callable, Optional

import customtkinter as ctk

from lan.service import CLIENT, HOSTING, JOINING
from theme import get_theme_manager
from typography import ui_font


class SessionStatusBar(ctk.CTkFrame):
    """One-line bar: who we are connected to, with shortcuts to the Session page and Leave."""

    def __init__(self, parent, service, on_open: Callable[[], None]):
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
        self.label.configure(text=text)


class ApprovalDialog(ctk.CTkToplevel):
    """Non-blocking prompt: ``on_answer(True/False)`` is called once, when the DM chooses.

    Closing the window counts as "Deny"."""

    def __init__(self, parent, name: str, address: str, on_answer: Callable[[bool], None]):
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
        ctk.CTkLabel(box, text=f"From {address}. Only let in people you invited.",
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
