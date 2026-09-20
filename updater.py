"""Update notification for Spellbook.

This module only asks the GitHub Releases API whether a newer release exists.
It never downloads, writes, moves, or deletes an executable, and it never
launches a helper script - the app previously did that to install updates in
place, but that self-replace behaviour (a process renaming/deleting/relaunching
its own executable via a spawned script) is exactly the pattern heuristic
antivirus flags as malware, and several users' AV did flag it. Updating is now
entirely manual: the app tells the user a newer version exists and opens the
GitHub Releases page in their normal browser, where the download carries the
usual browser provenance (Mark-of-the-Web / quarantine) that Windows/macOS
expect from a legitimate installer.

Standard library only (``urllib``, ``json``, ``ssl``) so it adds no packaging
weight. ``certifi`` is used for the CA bundle when it happens to be installed
(it makes HTTPS reliable inside a PyInstaller bundle on macOS), otherwise the
system trust store is used.

:func:`check_for_update` raises :class:`UpdateCheckError` on any network /
parse problem; callers doing a silent background check are expected to
swallow it.
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import Optional

from version import __version__

# --- Repository the app updates from -----------------------------------------

GITHUB_OWNER = "Kingkrusha"
GITHUB_REPO = "Spellbook"

RELEASES_PAGE_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"

_LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
_USER_AGENT = f"Spellbook-Updater/{__version__} (+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})"

_DEFAULT_TIMEOUT = 8.0


class UpdateCheckError(Exception):
    """Raised when the update check cannot complete (offline, API error, ...)."""


@dataclass(frozen=True)
class UpdateInfo:
    version: str            # normalised, e.g. "1.6.0"
    tag: str                # raw tag_name, e.g. "v1.6.0"
    title: str              # release name (falls back to tag)
    notes: str              # release body (markdown), may be ""
    release_url: str        # html_url of the release page
    published_at: str       # ISO 8601 string, may be ""


# --- Version comparison ------------------------------------------------------

_VERSION_RE = re.compile(r"(\d+(?:\.\d+)*)")


def _parse_version(text: str) -> tuple:
    """Extract a numeric version tuple from a tag like ``v1.5.3`` or ``V1.4.1``.

    Returns an empty tuple when no digits are present (e.g. a ``Beta`` tag),
    which compares as older than any real version.
    """
    if not text:
        return ()
    match = _VERSION_RE.search(text)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _normalise_version(text: str) -> str:
    parts = _parse_version(text)
    return ".".join(str(p) for p in parts) if parts else text.strip()


def is_newer(candidate: str, current: str = __version__) -> bool:
    """True when ``candidate`` represents a strictly newer version than ``current``."""
    a = _parse_version(candidate)
    b = _parse_version(current)
    if not a:
        return False
    length = max(len(a), len(b))
    a += (0,) * (length - len(a))
    b += (0,) * (length - len(b))
    return a > b


# --- HTTPS plumbing -----------------------------------------------------------

def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open(url: str, timeout: float):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    return urllib.request.urlopen(request, timeout=timeout, context=_ssl_context())


# --- Public API -------------------------------------------------------------

def check_for_update(
    timeout: float = _DEFAULT_TIMEOUT,
    current_version: str = __version__,
) -> Optional[UpdateInfo]:
    """Return an :class:`UpdateInfo` when a newer release exists, else ``None``.

    This makes a single read-only GET request to the GitHub API. It does not
    download, write, or execute anything.

    Raises :class:`UpdateCheckError` if the check can't be completed.
    """
    try:
        with _open(_LATEST_RELEASE_URL, timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # No published (non-prerelease) release yet - not an error state.
            return None
        raise UpdateCheckError(f"GitHub API returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError(f"Could not reach GitHub: {exc}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise UpdateCheckError("Unexpected response from GitHub") from exc

    tag = str(payload.get("tag_name") or "").strip()
    if not tag:
        raise UpdateCheckError("Release has no tag")

    if not is_newer(tag, current_version):
        return None

    return UpdateInfo(
        version=_normalise_version(tag),
        tag=tag,
        title=str(payload.get("name") or tag).strip(),
        notes=str(payload.get("body") or "").strip(),
        release_url=str(payload.get("html_url") or RELEASES_PAGE_URL),
        published_at=str(payload.get("published_at") or ""),
    )


def open_release_page(info: Optional[UpdateInfo] = None) -> None:
    """Open the GitHub release page in the user's default browser (best effort).

    This is the only "download" action the app takes - it hands off to the
    browser, which downloads and tags the file the normal way (the app itself
    never touches an executable).
    """
    url = (info.release_url if info else None) or RELEASES_PAGE_URL
    try:
        webbrowser.open(url)
    except Exception:
        pass
