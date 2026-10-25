"""Feedback and bug reports, sent from the app to the developer.

A report is a short form (bug or idea, a message, an optional email address to reply to) plus, only if
the user ticks them, the app version and system details and the end of ``crash.log``. It is posted to a
Formspree form, which forwards it to the developer by email. Nothing is sent without the user pressing
Send, and the user can read everything that would be sent first (:func:`report_text`).

The Formspree form id is not a secret: it only lets people *submit* to the form, which is what it is
for, so it is fine in source code. Formspree's own spam filtering and the ``_gotcha`` honeypot keep
junk out.

Standard library only (``urllib``, ``json``, ``platform``) so it adds no packaging weight.
"""

from __future__ import annotations

import json
import os
import platform
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, Optional

from version import __version__

# The Formspree form reports go to (the code at the end of https://formspree.io/f/<id>).
# Empty means "not set up": the window still opens and Copy report works, but Send is off.
FORMSPREE_FORM_ID = "xrppebgl"

KINDS = ("Bug report", "Idea or feedback")
MAX_MESSAGE = 10_000      # characters the user can write
LOG_TAIL = 8_000          # characters of crash.log that are attached at most
TIMEOUT = 15              # seconds


def is_configured(form_id: Optional[str] = None) -> bool:
    form_id = FORMSPREE_FORM_ID if form_id is None else form_id
    return bool(re.fullmatch(r"[A-Za-z0-9]{4,32}", form_id or ""))


def endpoint(form_id: Optional[str] = None) -> str:
    return f"https://formspree.io/f/{FORMSPREE_FORM_ID if form_id is None else form_id}"


# --- what can be attached ------------------------------------------------------------------------

def system_info() -> Dict[str, str]:
    """App version and the basics of the machine; nothing that names the user."""
    info = {
        "app_version": __version__,
        "os": f"{platform.system()} {platform.release()}".strip(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "packaged": "yes" if getattr(sys, "frozen", False) else "no (running from source)",
    }
    try:
        import tkinter
        info["tk"] = str(tkinter.TkVersion)
    except Exception:
        pass
    return info


def redact(text: str) -> str:
    """Replace the user's home folder and user name with neutral words, so paths don't name them."""
    home = os.path.expanduser("~")
    user = re.split(r"[\\/]", home.rstrip("\\/"))[-1]
    if home and home not in ("~", "/", "\\"):
        for variant in {home, home.replace("\\", "/"), home.replace("/", "\\")}:
            text = re.sub(re.escape(variant), "~", text, flags=re.IGNORECASE)
    if user and len(user) >= 3 and user.lower() not in ("root", "user", "home", "users"):
        text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])", "<user>", text,
                      flags=re.IGNORECASE)
    return text


def crash_log_path() -> str:
    from paths import user_data_path
    return user_data_path("crash.log")


def crash_log_tail(path: Optional[str] = None, limit: int = LOG_TAIL) -> str:
    """The end of crash.log (most recent errors), with the user's name taken out; "" if there is none."""
    path = path or crash_log_path()
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit * 2))
            data = handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    text = redact(data)[-limit:].strip()
    if not text:
        return ""
    # start on a whole line rather than halfway through one
    if len(data) >= limit and "\n" in text:
        text = text.split("\n", 1)[1]
    return text


# --- the report -----------------------------------------------------------------------------------

@dataclass
class Report:
    kind: str
    message: str
    email: str = ""
    include_system: bool = True
    include_log: bool = False
    system: Dict[str, str] = field(default_factory=dict)
    log: str = ""

    def problem(self) -> str:
        """Why this report can't be sent yet, or "" if it can."""
        if not self.message.strip():
            return "Write a few words first."
        if len(self.message) > MAX_MESSAGE:
            return f"That is a bit long: please keep it under {MAX_MESSAGE:,} characters."
        if self.email.strip() and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.email.strip()):
            return "That email address doesn't look right (or leave it empty)."
        return ""

    def fields(self) -> Dict[str, str]:
        """What is posted to the form."""
        data = {
            "_subject": f"Spellbook {__version__}: {self.kind}",
            "kind": self.kind,
            "message": self.message.strip(),
        }
        if self.email.strip():
            data["email"] = self.email.strip()      # Formspree uses this as the reply-to address
        if self.include_system and self.system:
            data.update({f"system_{k}": v for k, v in self.system.items()})
        if self.include_log:
            data["crash_log"] = self.log or "(crash.log is empty)"
        return data


def make_report(kind: str, message: str, email: str = "", include_system: bool = True,
                include_log: bool = False, log_path: Optional[str] = None) -> Report:
    return Report(kind=kind, message=message, email=email, include_system=include_system,
                  include_log=include_log, system=system_info() if include_system else {},
                  log=crash_log_tail(log_path) if include_log else "")


def report_text(report: Report) -> str:
    """The report as plain text: shown as a preview and used by Copy report."""
    lines = [f"Spellbook {__version__}: {report.kind}", "", report.message.strip()]
    if report.email.strip():
        lines += ["", f"Reply to: {report.email.strip()}"]
    if report.include_system and report.system:
        lines += ["", "System:"] + [f"  {k}: {v}" for k, v in report.system.items()]
    if report.include_log:
        lines += ["", "End of crash.log:", report.log or "(crash.log is empty)"]
    return "\n".join(lines)


# --- sending --------------------------------------------------------------------------------------

class SendError(Exception):
    """A report could not be sent; the message is fit to show the user."""


def _ssl_context():
    from updater import _ssl_context as context      # same CA handling as the update check
    return context()


def send(report: Report, form_id: Optional[str] = None, opener=None) -> None:
    """Post the report. Raises :class:`SendError` with a readable reason when it doesn't arrive."""
    if not is_configured(form_id):
        raise SendError("Sending isn't set up in this copy of Spellbook. Use Copy report instead.")
    problem = report.problem()
    if problem:
        raise SendError(problem)
    body = json.dumps(report.fields()).encode("utf-8")
    request = urllib.request.Request(endpoint(form_id), data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"Spellbook/{__version__}",
    })
    try:
        if opener is not None:
            response = opener(request, TIMEOUT)
        else:
            response = urllib.request.urlopen(request, timeout=TIMEOUT, context=_ssl_context())
        with response:
            answer = response.read()
    except urllib.error.HTTPError as err:
        raise SendError(_error_text(err.code, err.read() if hasattr(err, "read") else b"")) from None
    except (urllib.error.URLError, OSError) as err:
        raise SendError("Couldn't reach the feedback service. Check your internet connection, "
                        "or use Copy report.") from err
    try:
        result = json.loads(answer or b"{}")
    except ValueError:
        result = {}
    if isinstance(result, dict) and result.get("errors"):
        raise SendError(_error_text(400, answer))


def _error_text(code: int, raw: bytes) -> str:
    detail = ""
    try:
        errors = json.loads(raw or b"{}").get("errors") or []
        detail = "; ".join(str(e.get("message", "")) for e in errors if isinstance(e, dict)).strip("; ")
    except Exception:
        pass
    if code == 429:
        return "Too many reports were sent just now. Please try again later, or use Copy report."
    if code in (403, 404):
        return "The feedback form isn't accepting reports right now. Please use Copy report instead."
    return f"The report wasn't accepted ({detail or f'error {code}'}). You can use Copy report instead."
