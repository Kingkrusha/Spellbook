"""The Send feedback window (Settings > Help, or its shortcut, Shift+F1 by default).

The user picks Bug report or Idea, writes a message, optionally leaves an email address, and chooses
whether to include the version and system details and the end of crash.log. "Show what will be sent"
previews the exact text. Send posts it (see feedback.py) on a background thread; Copy report puts the
same text on the clipboard for when sending isn't possible.
"""

from __future__ import annotations

import threading
from typing import Optional

import customtkinter as ctk

import feedback as F
from theme import get_theme_manager
from typography import ui_font

NOTE = ("Tell me what went wrong or what you'd like to see. It goes straight to the developer. "
        "Only what you see under \"Show what will be sent\" is sent, and only when you press Send.")

_open_dialog: Optional["FeedbackDialog"] = None


def open_feedback(parent, kind: Optional[str] = None) -> "FeedbackDialog":
    """Open the window, or bring the one that is already open to the front."""
    global _open_dialog
    if _open_dialog is not None:
        try:
            if _open_dialog.winfo_exists():
                _open_dialog.deiconify()
                _open_dialog.lift()
                _open_dialog.focus_force()
                return _open_dialog
        except Exception:
            pass
    _open_dialog = FeedbackDialog(parent.winfo_toplevel(), kind=kind)
    return _open_dialog


def _button(parent, text, command, primary=False, width=120, **kw):
    theme = get_theme_manager()
    color = theme.get_current_color("accent_primary" if primary else "button_normal")
    hover = theme.get_current_color("accent_hover" if primary else "button_hover")
    return ctk.CTkButton(parent, text=text, width=width, command=command, fg_color=color, hover_color=hover,
                         text_color=theme.get_current_color("text_primary"), **kw)


class FeedbackDialog(ctk.CTkToplevel):
    WIDTH, HEIGHT = 580, 640

    def __init__(self, parent, kind: Optional[str] = None, form_id: Optional[str] = None, sender=None):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.form_id = form_id
        self._sender = sender or F.send
        self._sending = False
        self.title("Send feedback")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(480, 520)
        self.transient(parent)
        secondary = self.theme.get_text_secondary()

        box = self.box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=18, pady=16)
        ctk.CTkLabel(box, text="Send feedback", font=ui_font("heading", 16, bold=True)).pack(anchor="w")
        ctk.CTkLabel(box, text=NOTE, font=ui_font("small"), text_color=secondary, wraplength=530,
                     justify="left", anchor="w").pack(fill="x", pady=(4, 10))

        self.kind_var = ctk.StringVar(value=kind if kind in F.KINDS else F.KINDS[0])
        ctk.CTkSegmentedButton(box, values=list(F.KINDS), variable=self.kind_var,
                               command=lambda _v: self._changed()).pack(anchor="w")

        # buttons first, from the bottom, so a small window squeezes the text box rather than them
        buttons = ctk.CTkFrame(box, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", pady=(8, 0))
        self.send_btn = _button(buttons, "Send", self._send, primary=True, width=110, height=34)
        self.send_btn.pack(side="left")
        self.copy_btn = _button(buttons, "Copy report", self._copy, width=120, height=34)
        self.copy_btn.pack(side="left", padx=(8, 0))
        _button(buttons, "Close", self.close, width=90, height=34).pack(side="right")
        self.status = ctk.CTkLabel(box, text="", font=ui_font("small"), wraplength=530, justify="left",
                                   anchor="w", text_color=self.theme.get_current_color("text_warning"))
        self.status.pack(side="bottom", fill="x", pady=(6, 0))

        options = ctk.CTkFrame(box, fg_color="transparent")
        options.pack(side="bottom", fill="x")
        ctk.CTkLabel(options, text="Your email (optional, only if you'd like a reply)",
                     font=ui_font("small"), text_color=secondary, anchor="w").pack(fill="x", pady=(8, 2))
        self.email = ctk.CTkEntry(options, placeholder_text="name@example.com")
        self.email.pack(fill="x")
        self.system_var = ctk.BooleanVar(value=True)
        self.log_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(options, text="Include the app version and system details (Windows/macOS version)",
                        variable=self.system_var, font=ui_font("small"),
                        command=self._changed).pack(anchor="w", pady=(10, 0))
        self.log_box = ctk.CTkCheckBox(options, text="Include recent errors from crash.log "
                                                     "(your user name is removed)",
                                       variable=self.log_var, font=ui_font("small"), command=self._changed)
        self.log_box.pack(anchor="w", pady=(6, 0))
        self.preview_btn = _button(options, "Show what will be sent", self._toggle_preview, width=180, height=26)
        self.preview_btn.pack(anchor="w", pady=(10, 0))
        self.preview = ctk.CTkTextbox(options, height=150, font=ui_font("small"), wrap="word",
                                      fg_color=self.theme.get_current_color("bg_secondary"))
        self._preview_shown = False

        ctk.CTkLabel(box, text="Message", font=ui_font("body", bold=True), anchor="w").pack(fill="x",
                                                                                           pady=(12, 2))
        self.message = ctk.CTkTextbox(box, height=140, wrap="word", font=ui_font("body"))
        self.message.pack(fill="both", expand=True)
        self.message.bind("<KeyRelease>", lambda _e: self._changed(), add="+")

        if not F.is_configured(self.form_id):
            self.send_btn.configure(state="disabled")
            self._say("Sending isn't set up in this copy yet. Copy report puts the text on your clipboard "
                      "so you can paste it into an email or a GitHub issue.")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _e: self.close())
        self._center(parent)
        self.after(50, self._focus_message)

    # ---- helpers ------------------------------------------------------------------------------------

    def _center(self, parent):
        try:
            self.update_idletasks()
            top = parent.winfo_toplevel()
            x = top.winfo_rootx() + (top.winfo_width() - self.WIDTH) // 2
            y = top.winfo_rooty() + (top.winfo_height() - self.HEIGHT) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _focus_message(self):
        try:
            self.lift()
            self.message.focus_set()
        except Exception:
            pass

    def _say(self, text: str, ok: bool = False):
        color = self.theme.get_current_color("accent_primary" if ok else "text_warning")
        self.status.configure(text=text, text_color=color)

    def report(self) -> F.Report:
        return F.make_report(self.kind_var.get(), self.message.get("1.0", "end-1c"), self.email.get(),
                             include_system=self.system_var.get(), include_log=self.log_var.get())

    def _changed(self):
        if self._preview_shown:
            self._fill_preview()

    def _fill_preview(self):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", F.report_text(self.report()))
        self.preview.configure(state="disabled")

    def _toggle_preview(self):
        self._preview_shown = not self._preview_shown
        if self._preview_shown:
            self._fill_preview()
            self.preview.pack(fill="x", pady=(6, 0))
            self.preview_btn.configure(text="Hide what will be sent")
        else:
            self.preview.pack_forget()
            self.preview_btn.configure(text="Show what will be sent")

    # ---- actions -----------------------------------------------------------------------------------

    def _copy(self):
        report = self.report()
        if not report.message.strip():
            self._say("Write a few words first.")
            return
        self.clipboard_clear()
        self.clipboard_append(F.report_text(report))
        self._say("Copied. Paste it into an email or a GitHub issue.", ok=True)

    def _send(self):
        if self._sending:
            return
        report = self.report()
        problem = report.problem()
        if problem:
            self._say(problem)
            return
        self._sending = True
        self.send_btn.configure(state="disabled", text="Sending…")
        self._say("Sending…", ok=True)

        def work():
            try:
                self._sender(report, self.form_id)
                outcome = None
            except F.SendError as err:
                outcome = str(err)
            except Exception as err:          # never let a send problem become a crash
                outcome = f"Something went wrong while sending ({err}). You can use Copy report instead."
            self._outcome = [outcome]        # picked up on the UI thread by _poll (Tk isn't thread-safe)
        self._outcome = None
        threading.Thread(target=work, name="feedback-send", daemon=True).start()
        self.after(100, self._poll)

    def _poll(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if self._outcome is None:
            self.after(100, self._poll)
            return
        self._sent(self._outcome[0])

    def _sent(self, error: Optional[str]):
        self._sending = False
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.send_btn.configure(state="normal", text="Send")
        if error:
            self._say(error)
            return
        self.message.delete("1.0", "end")
        self.log_var.set(False)
        self._changed()
        self._say("Thank you! Your report was sent.", ok=True)

    def close(self):
        global _open_dialog
        if _open_dialog is self:
            _open_dialog = None
        try:
            self.destroy()
        except Exception:
            pass
