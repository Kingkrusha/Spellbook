"""Feedback and bug reports, sent from the app to the developer.

A report is a short form (bug or idea, a message, an optional email address to reply to) plus, unless the
user unticks them, the app version and system details and the end of the app's logs (``crash.log`` and
``spellbook.log``), and any pictures the user attached. It is posted to a Formspree form, which forwards it
to the developer by email. Nothing is sent without the user pressing Send (crash reports, see
crash_report.py, can be turned off), and the user can read everything that would be sent first
(:func:`report_text`).

Pictures go as file uploads, which Formspree accepts only on its paid plans: if the form refuses them, the
report is sent again without them and the sender is told (:func:`send` returns that note).

The Formspree form id is not a secret: it only lets people *submit* to the form, which is what it is
for, so it is fine in source code. Formspree's own spam filtering and the ``_gotcha`` honeypot keep
junk out.

Standard library only (``urllib``, ``json``, ``platform``) so it adds no packaging weight.
"""

from __future__ import annotations

import io
import json
import os
import platform
import re
import secrets
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from version import __version__

# The Formspree form reports go to (the code at the end of https://formspree.io/f/<id>).
# Empty means "not set up": the window still opens and Copy report works, but Send is off.
FORMSPREE_FORM_ID = "xrppebgl"

KINDS = ("Bug report", "Idea or feedback")
MAX_MESSAGE = 10_000      # characters the user can write
LOG_TAIL = 8_000          # characters of crash.log that are attached at most
APP_LOG_TAIL = 6_000      # ... and of spellbook.log
TIMEOUT = 15              # seconds (pictures get longer, see send())
MAX_PICTURES = 3
PICTURE_SIDE = 1600       # pictures are shrunk to fit this many pixels on their longer side
MAX_PICTURE_BYTES = 2 * 1024 * 1024


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


def app_log_tail(limit: int = APP_LOG_TAIL) -> str:
    """The end of spellbook.log (what the app printed), with the user's name taken out."""
    try:
        import app_log
        return redact(app_log.tail(limit))
    except Exception:
        return ""


# --- pictures -------------------------------------------------------------------------------------

@dataclass
class Picture:
    name: str            # a file name for the developer's end ("screenshot-1.png")
    data: bytes
    mime: str            # image/png or image/jpeg

    @property
    def size_text(self) -> str:
        n = len(self.data)
        return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{max(1, n // 1024)} KB"


def make_picture(image, name: str) -> Picture:
    """A picture ready to send from a PIL image: shrunk to :data:`PICTURE_SIDE` and kept under
    :data:`MAX_PICTURE_BYTES` (PNG when that is small enough, so text in a screenshot stays sharp)."""
    from PIL import Image
    image = image.copy()
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
    image.thumbnail((PICTURE_SIDE, PICTURE_SIDE), Image.LANCZOS)
    stem = os.path.splitext(os.path.basename(name))[0][:40] or "picture"
    stem = re.sub(r"[^A-Za-z0-9 ._-]+", "_", stem).strip() or "picture"
    data = io.BytesIO()
    image.save(data, "PNG", optimize=True)
    if data.tell() <= MAX_PICTURE_BYTES:
        return Picture(stem + ".png", data.getvalue(), "image/png")
    flat = image.convert("RGB")
    for quality in (85, 70, 55):
        data = io.BytesIO()
        flat.save(data, "JPEG", quality=quality, optimize=True)
        if data.tell() <= MAX_PICTURE_BYTES:
            break
    return Picture(stem + ".jpg", data.getvalue(), "image/jpeg")


def picture_from_file(path: str) -> Picture:
    """Raises ValueError with a readable reason if the file isn't a picture."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        with Image.open(path) as image:
            image.load()
            image = ImageOps.exif_transpose(image)
            return make_picture(image, os.path.basename(path))
    except (UnidentifiedImageError, OSError, ValueError) as err:
        raise ValueError(f"That file isn't a picture Spellbook can read ({err}).") from None


# --- the report -----------------------------------------------------------------------------------

@dataclass
class Report:
    kind: str
    message: str
    email: str = ""
    include_system: bool = True
    include_log: bool = False
    system: Dict[str, str] = field(default_factory=dict)
    log: str = ""              # the end of crash.log
    app_log: str = ""          # the end of spellbook.log
    pictures: List[Picture] = field(default_factory=list)

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
            data["app_log"] = self.app_log or "(spellbook.log is empty)"
        if self.pictures:
            data["pictures"] = ", ".join(f"{p.name} ({p.size_text})" for p in self.pictures)
        return data


def make_report(kind: str, message: str, email: str = "", include_system: bool = True,
                include_log: bool = False, log_path: Optional[str] = None,
                pictures: Optional[List[Picture]] = None) -> Report:
    return Report(kind=kind, message=message, email=email, include_system=include_system,
                  include_log=include_log, system=system_info() if include_system else {},
                  log=crash_log_tail(log_path) if include_log else "",
                  app_log=app_log_tail() if include_log else "",
                  pictures=list(pictures or [])[:MAX_PICTURES])


def report_text(report: Report) -> str:
    """The report as plain text: shown as a preview and used by Copy report."""
    lines = [f"Spellbook {__version__}: {report.kind}", "", report.message.strip()]
    if report.email.strip():
        lines += ["", f"Reply to: {report.email.strip()}"]
    if report.pictures:
        lines += ["", "Pictures: " + ", ".join(f"{p.name} ({p.size_text})" for p in report.pictures)]
    if report.include_system and report.system:
        lines += ["", "System:"] + [f"  {k}: {v}" for k, v in report.system.items()]
    if report.include_log:
        lines += ["", "End of crash.log:", report.log or "(crash.log is empty)",
                  "", "End of spellbook.log:", report.app_log or "(spellbook.log is empty)"]
    return "\n".join(lines)


# --- sending --------------------------------------------------------------------------------------

class SendError(Exception):
    """A report could not be sent; the message is fit to show the user. ``reason`` is "offline" (the
    service couldn't be reached), "busy" (too many reports just now) or "refused" (the form said no)."""

    def __init__(self, message: str, reason: str = "refused"):
        super().__init__(message)
        self.reason = reason


def _ssl_context():
    from updater import _ssl_context as context      # same CA handling as the update check
    return context()


def multipart(fields: Dict[str, str], pictures: List[Picture]) -> Tuple[bytes, str]:
    """``(body, content type)`` of a multipart/form-data post with the fields and the pictures."""
    boundary = "SpellbookReport" + secrets.token_hex(12)

    def quoted(text: str) -> str:
        return re.sub(r'[\r\n"\\]', "_", text)
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{quoted(name)}"\r\n\r\n'
                  .encode("utf-8"))
        out.write(str(value).encode("utf-8") + b"\r\n")
    for picture in pictures:
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="attachment"; '
                  f'filename="{quoted(picture.name)}"\r\nContent-Type: {picture.mime}\r\n\r\n'.encode("utf-8"))
        out.write(picture.data + b"\r\n")
    out.write(f"--{boundary}--\r\n".encode("ascii"))
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def _post(url: str, body: bytes, content_type: str, timeout: float, opener=None) -> bytes:
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": content_type,
        "Accept": "application/json",
        "User-Agent": f"Spellbook/{__version__}",
    })
    try:
        if opener is not None:
            response = opener(request, timeout)
        else:
            response = urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())
        with response:
            answer = response.read()
    except urllib.error.HTTPError as err:
        raise SendError(_error_text(err.code, err.read() if hasattr(err, "read") else b""),
                        "busy" if err.code == 429 else "refused") from None
    except (urllib.error.URLError, OSError) as err:
        raise SendError("Couldn't reach the feedback service. Check your internet connection, "
                        "or use Copy report.", "offline") from err
    try:
        result = json.loads(answer or b"{}")
    except ValueError:
        result = {}
    if isinstance(result, dict) and result.get("errors"):
        raise SendError(_error_text(400, answer))
    return answer


def send(report: Report, form_id: Optional[str] = None, opener=None) -> Optional[str]:
    """Post the report. Raises :class:`SendError` with a readable reason when it doesn't arrive.

    Returns None, or a note for the sender when the report went but its pictures didn't (the form doesn't
    take files, which on Formspree needs a paid plan)."""
    if not is_configured(form_id):
        raise SendError("Sending isn't set up in this copy of Spellbook. Use Copy report instead.")
    problem = report.problem()
    if problem:
        raise SendError(problem)
    fields = report.fields()
    if report.pictures:
        body, kind = multipart(fields, report.pictures)
        try:
            _post(endpoint(form_id), body, kind, TIMEOUT + 30, opener)
            return None
        except SendError as err:
            if err.reason != "refused":
                raise
            reason = str(err)
        fields = dict(fields, pictures=fields.get("pictures", "") + " (not attached: the form refused them)")
        _post(endpoint(form_id), json.dumps(fields).encode("utf-8"), "application/json", TIMEOUT, opener)
        return f"Sent, but without the pictures ({reason.rstrip('.')})."
    _post(endpoint(form_id), json.dumps(fields).encode("utf-8"), "application/json", TIMEOUT, opener)
    return None


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
