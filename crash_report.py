"""Crash reports: when Spellbook closed unexpectedly, the next start tells the developer.

Each run leaves a note in the data folder (``runs/<pid>.json``) when it starts and removes it when it
closes normally. A note left behind by a run that is no longer running means that run ended without
closing: it crashed, froze and was ended, or the computer went off. :func:`begin_run` finds those.

What happened is in ``crash.log``: Python writes every thread's stack there when the process dies
(``faulthandler``), the app's freeze watchdog writes it there when the window stops responding for a while,
and errors that reached the top are recorded there. :func:`report_for` picks out the crashed run's part of
crash.log and spellbook.log (each run starts with the line from :func:`app_log.start_line`) and makes a
:class:`feedback.Report` of it, but only when crash.log shows a crash or a freeze, so a power cut or a
forced shutdown doesn't send anything. Sending is on by default and can be turned off in Settings > Help;
the user's home folder and name are taken out of everything, as for any feedback.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

import app_log
import feedback as F

RUNS_FOLDER = "runs"
MAX_AGE_DAYS = 30               # notes older than this are thrown away without a report
CRASH_LOG_LIMIT = 20_000        # characters of the crashed run's crash.log section that go in a report
APP_LOG_LIMIT = 6_000

# What crash.log says when a run really went wrong (rather than the computer simply being switched off)
_FATAL = ("Fatal Python error", "Windows fatal exception", "Segmentation fault", "--- unhandled error")
_FREEZE = re.compile(r"^Timeout \(\d+:\d\d:\d\d(\.\d+)?\)!", re.MULTILINE)


@dataclass
class Run:
    """A run that didn't close normally."""
    pid: int
    started: str
    version: str = ""
    path: str = ""

    @property
    def key(self) -> str:
        return f"{self.started} (pid {self.pid})"


def runs_folder() -> str:
    from paths import user_data_path
    return user_data_path(RUNS_FOLDER)


def _alive(pid: int) -> bool:
    """Whether a process with this id is running (never signals it: os.kill(pid, 0) ends it on Windows)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
            kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            handle = kernel32.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def begin_run(started: str, version: str = "", folder: Optional[str] = None) -> List[Run]:
    """Note that this run has started. Returns the earlier runs that didn't close normally, newest first
    (their notes stay until :func:`forget` is called for them)."""
    folder = folder or runs_folder()
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        return []
    crashed: List[Run] = []
    now = time.time()
    try:
        names = os.listdir(folder)
    except OSError:
        names = []
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            run = Run(int(data["pid"]), str(data["started"]), str(data.get("version", "")), path)
        except (OSError, ValueError, KeyError, TypeError):
            _remove(path)
            continue
        if run.pid == os.getpid():
            continue
        if _alive(run.pid):
            continue                                    # another copy of Spellbook, still open
        try:
            old = now - os.path.getmtime(path) > MAX_AGE_DAYS * 86400
        except OSError:
            old = True
        if old:
            _remove(path)
            continue
        crashed.append(run)
    crashed.sort(key=lambda r: r.started, reverse=True)
    try:
        with open(os.path.join(folder, f"{os.getpid()}.json"), "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "started": started, "version": version}, f)
    except OSError:
        pass
    return crashed


def end_run(folder: Optional[str] = None) -> None:
    """This run is closing normally."""
    _remove(os.path.join(folder or runs_folder(), f"{os.getpid()}.json"))


def forget(run: Run) -> None:
    """A crashed run has been dealt with (reported, or nothing to report)."""
    if run.path:
        _remove(run.path)


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


# ------------------------------------------------------------------------------------------- the logs

def section(text: str, run: Run) -> str:
    """The part of a log written by ``run``: from its start line to the next run's."""
    marker = app_log.start_line(run.started, run.pid)
    at = text.rfind(marker)
    if at < 0:
        return ""
    body = text[at:]
    after = re.search(r"^===== Spellbook started ", body[len(marker):], re.MULTILINE)
    return body[:len(marker) + after.start()] if after else body


def _read(path: str, limit: int = 4 * 1024 * 1024) -> str:
    """The end of a file (at most ``limit`` bytes), "" if it can't be read."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def what_happened(crash_log: str) -> str:
    """"crash", "freeze" or "" (nothing that explains the run ending) for a run's part of crash.log."""
    if any(mark in crash_log for mark in _FATAL):
        return "crash"
    if _FREEZE.search(crash_log):
        return "freeze"
    return ""


def _clip(text: str, limit: int) -> str:
    """The start and the end of a long text (the first error and the very last moments both matter)."""
    if len(text) <= limit:
        return text
    head = text[:limit // 3]
    tail = text[-(limit - len(head) - 40):]
    return f"{head}\n\n[... {len(text) - len(head) - len(tail):,} characters left out ...]\n\n{tail}"


def report_for(run: Run, crash_log_path: Optional[str] = None,
               app_log_path: Optional[str] = None) -> Optional[F.Report]:
    """The report to send about a run that didn't close, or None if its logs show no crash or freeze."""
    crash = section(_read(crash_log_path or F.crash_log_path()), run)
    kind = what_happened(crash)
    if not kind:
        return None
    app = section(_read(app_log_path or app_log.log_path()), run)
    if not app and app_log_path is None:                   # (it may have moved to spellbook.log.1)
        app = section(_read(app_log.log_path() + ".1"), run)
    first = next((line.strip() for line in crash.splitlines()
                  if any(m in line for m in _FATAL) or _FREEZE.match(line)), "")
    words = "stopped responding and was closed" if kind == "freeze" else "closed unexpectedly"
    message = (f"Automatic crash report: Spellbook {run.version or '?'} {words}.\n"
               f"The run started {run.started}.\n" + (f"First sign: {first}\n" if first else ""))
    report = F.Report(kind="Crash report", message=message, include_system=True, include_log=True,
                      system=F.system_info(),
                      log=F.redact(_clip(crash.strip(), CRASH_LOG_LIMIT)),
                      app_log=F.redact(_clip(app.strip(), APP_LOG_LIMIT)))
    return report
