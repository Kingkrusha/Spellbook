"""In-app updates for Spellbook.

The flow, in order:

* :func:`check_for_update` asks the GitHub Releases API whether a newer release
  exists and picks the asset matching this OS / architecture,
* :func:`download_asset` streams it to the Downloads folder, optionally verifying
  it against the release's ``SHA256SUMS`` file,
* :func:`apply_update` (Phase 2) swaps the downloaded build in for the running
  one via a small detached helper script and relaunches - the caller must exit
  the app right after so the helper can replace the locked executable,
* :func:`cleanup_backup` deletes the previous version's ``.bak`` on the next
  successful start.

Everything here is standard library only (``urllib``, ``json``, ``ssl``,
``hashlib``) so it adds no packaging weight. ``certifi`` is used for the CA
bundle when it happens to be installed (it makes HTTPS reliable inside a
PyInstaller bundle on macOS), otherwise the system trust store is used.

Nothing in here should ever raise into a caller that isn't ready for it:
:func:`check_for_update` raises :class:`UpdateCheckError` on any network / parse
problem, and callers doing a silent background check are expected to swallow it.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from version import __version__

# --- Repository the app updates from -----------------------------------------

GITHUB_OWNER = "Kingkrusha"
GITHUB_REPO = "Spellbook"

_LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
_USER_AGENT = f"Spellbook-Updater/{__version__} (+https://github.com/{GITHUB_OWNER}/{GITHUB_REPO})"

# Release asset names produced by .github/workflows/release.yml.
_ASSET_WINDOWS_X64 = "Spellbook-windows-x64.exe"
_ASSET_MACOS_ARM64 = "Spellbook-macos-arm64.zip"
_ASSET_MACOS_X86_64 = "Spellbook-macos-x86_64.zip"

# Checksums manifest attached to the release (see the GitHub setup notes). Any of
# these names is accepted; lines are "<sha256>  <filename>" (sha256sum format).
_CHECKSUMS_NAMES = ("SHA256SUMS", "SHA256SUMS.txt", "sha256sums.txt", "checksums.txt")

_DEFAULT_TIMEOUT = 8.0


class UpdateCheckError(Exception):
    """Raised when the update check cannot complete (offline, API error, ...)."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str          # browser_download_url
    size: int         # bytes, 0 if unknown


@dataclass(frozen=True)
class UpdateInfo:
    version: str            # normalised, e.g. "1.6.0"
    tag: str                # raw tag_name, e.g. "v1.6.0"
    title: str              # release name (falls back to tag)
    notes: str              # release body (markdown), may be ""
    release_url: str        # html_url of the release page
    published_at: str       # ISO 8601 string, may be ""
    asset: Optional[ReleaseAsset]  # matching download for this platform, if any
    checksums_url: Optional[str] = None  # SHA256SUMS asset, if the release has one

    @property
    def has_download(self) -> bool:
        return self.asset is not None


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


# --- Platform asset selection ---------------------------------------------------

def _expected_asset_name() -> Optional[str]:
    """The release asset filename for the platform we're running on."""
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return _ASSET_WINDOWS_X64
    if sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            return _ASSET_MACOS_ARM64
        if machine in ("x86_64", "amd64"):
            return _ASSET_MACOS_X86_64
        return None
    # Linux / other: the release workflow ships no binary, so there's nothing
    # to offer. The caller still gets the "newer version exists" notification.
    return None


def _select_asset(assets: List[ReleaseAsset]) -> Optional[ReleaseAsset]:
    """Best guess at the download for this platform, or ``None`` to fall back
    to the release page.

    Release asset naming has varied over time (older releases ship a bare
    ``spellbook.exe``; the current workflow produces
    ``Spellbook-windows-x64.exe`` / ``Spellbook-macos-<arch>.zip``), so this
    tries progressively looser matches - but never guesses at macOS architecture,
    where picking the wrong one is worse than offering no download.
    """
    expected = _expected_asset_name()
    if not expected:
        return None

    # 1. Exact match on the current workflow's naming.
    for asset in assets:
        if asset.name == expected:
            return asset

    # 2. Platform token anywhere in the name (tolerates a version suffix, etc.).
    token = {
        _ASSET_WINDOWS_X64: "windows",
        _ASSET_MACOS_ARM64: "macos-arm64",
        _ASSET_MACOS_X86_64: "macos-x86_64",
    }[expected]
    for asset in assets:
        if token in asset.name.lower():
            return asset

    # 3. Windows only: there is exactly one Windows binary per release, so any
    #    lone .exe is safe to offer even when it's the un-suffixed name.
    if sys.platform == "win32":
        exes = [a for a in assets if a.name.lower().endswith(".exe")]
        if len(exes) == 1:
            return exes[0]

    # 4. macOS: only accept a single arch-agnostic archive when nothing in the
    #    release hints at multiple architectures.
    if sys.platform == "darwin":
        archives = [
            a for a in assets
            if a.name.lower().endswith((".zip", ".dmg"))
        ]
        arch_hinted = any(
            t in a.name.lower()
            for a in assets
            for t in ("arm64", "aarch64", "x86_64", "x64", "intel", "amd64")
        )
        if len(archives) == 1 and not arch_hinted:
            return archives[0]

    return None


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

    assets: List[ReleaseAsset] = []
    checksums_url: Optional[str] = None
    for raw in payload.get("assets") or []:
        url = raw.get("browser_download_url")
        name = raw.get("name")
        if not url or not name:
            continue
        if name in _CHECKSUMS_NAMES:
            checksums_url = url
            continue
        assets.append(
            ReleaseAsset(name=name, url=url, size=int(raw.get("size") or 0))
        )

    return UpdateInfo(
        version=_normalise_version(tag),
        tag=tag,
        title=str(payload.get("name") or tag).strip(),
        notes=str(payload.get("body") or "").strip(),
        release_url=str(payload.get("html_url") or ""),
        published_at=str(payload.get("published_at") or ""),
        asset=_select_asset(assets),
        checksums_url=checksums_url,
    )


def downloads_dir() -> str:
    """The folder downloaded installers are saved into."""
    candidate = os.path.join(os.path.expanduser("~"), "Downloads")
    return candidate if os.path.isdir(candidate) else os.path.expanduser("~")


def download_asset(
    info: UpdateInfo,
    dest_dir: Optional[str] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    timeout: float = 30.0,
    expected_sha256: Optional[str] = None,
) -> str:
    """Download ``info.asset`` and return the path to the finished file.

    ``progress_cb(downloaded_bytes, total_bytes)`` is called as data arrives
    (``total_bytes`` is 0 when the server sends no Content-Length). The file is
    written to ``<name>.part`` and renamed into place only on success.

    When ``expected_sha256`` is given the finished file's digest must match it,
    otherwise the file is deleted and :class:`UpdateCheckError` is raised.
    """
    if info.asset is None:
        raise UpdateCheckError("No downloadable asset for this platform")

    target_dir = dest_dir or downloads_dir()
    os.makedirs(target_dir, exist_ok=True)
    final_path = os.path.join(target_dir, info.asset.name)
    part_path = final_path + ".part"

    try:
        with _open(info.asset.url, timeout) as response:
            total = info.asset.size or int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            if progress_cb:
                progress_cb(0, total)
            with open(part_path, "wb") as out:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as exc:
        _quiet_remove(part_path)
        raise UpdateCheckError(f"Download failed: {exc}") from exc
    except BaseException:
        _quiet_remove(part_path)
        raise

    if expected_sha256:
        actual = _sha256_file(part_path)
        if actual.lower() != expected_sha256.strip().lower():
            _quiet_remove(part_path)
            raise UpdateCheckError(
                "Checksum mismatch - the download is corrupted or has been "
                "tampered with. Nothing was installed."
            )

    os.replace(part_path, final_path)
    return final_path


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_expected_hash(info: UpdateInfo, timeout: float = 15.0) -> Optional[str]:
    """Return the expected SHA-256 for ``info.asset`` from the release's
    ``SHA256SUMS`` manifest, or ``None`` when the release publishes no manifest
    (or it has no line for this asset). Raises nothing - callers treat ``None``
    as "unverified".
    """
    if not info.checksums_url or info.asset is None:
        return None
    try:
        with _open(info.checksums_url, timeout) as response:
            text = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError):
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        digest = parts[0]
        # sha256sum prints "<hash> *<name>" for binary mode; strip the marker
        # and any directory component.
        name = os.path.basename(parts[-1].lstrip("*"))
        if name == info.asset.name and re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            return digest
    return None


def reveal_in_file_manager(path: str) -> None:
    """Open the platform file manager with ``path`` selected (best effort)."""
    try:
        if sys.platform == "win32":
            # explorer.exe exits non-zero even on success; don't check the code.
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path) or "."])
    except Exception:
        pass


def open_release_page(info: UpdateInfo) -> None:
    """Open the GitHub release page in the default browser (best effort)."""
    url = info.release_url or f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
    try:
        webbrowser.open(url)
    except Exception:
        pass


# --- Phase 2: apply the update in place --------------------------------------

def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _running_exe() -> str:
    """Absolute path to the running Spellbook executable."""
    return os.path.abspath(sys.executable)


def _macos_app_bundle() -> Optional[str]:
    """Path to the running ``Spellbook.app`` bundle, or ``None`` if not in one."""
    exe = _running_exe()
    marker = ".app/Contents/MacOS/"
    idx = exe.find(marker)
    if idx == -1:
        return None
    return exe[: idx + len(".app")]


def can_self_update() -> Tuple[bool, str]:
    """Whether :func:`apply_update` can run here.

    Returns ``(True, "")`` when an in-place update is possible, otherwise
    ``(False, reason)`` with a message suitable for showing the user.
    """
    if not _is_frozen():
        return False, "Running from source - use 'git pull' to update."

    if sys.platform == "win32":
        exe = _running_exe()
        if not os.access(os.path.dirname(exe), os.W_OK):
            return False, (
                "Spellbook's folder is read-only. Move Spellbook.exe somewhere "
                "you can write to (e.g. your user folder) and try again."
            )
        return True, ""

    if sys.platform == "darwin":
        app = _macos_app_bundle()
        if not app or not os.path.isdir(app):
            return False, "Could not locate the Spellbook.app bundle."
        if "/AppTranslocation/" in app:
            return False, (
                "macOS is running Spellbook from a quarantine sandbox. Move it "
                "to your Applications folder and reopen it, then try again."
            )
        if not os.access(app, os.W_OK) or not os.access(os.path.dirname(app), os.W_OK):
            return False, (
                "Spellbook.app is in a read-only location. Move it to your "
                "Applications folder and try again."
            )
        return True, ""

    return False, "In-app updates aren't supported on this platform yet."


def apply_update(downloaded_path: str) -> None:
    """Replace the running build with ``downloaded_path`` and relaunch.

    Spawns a small **detached** helper that waits for this process to exit, swaps
    the new build in (keeping the old one as ``.bak`` for rollback), and starts
    the app again. This function returns immediately; the caller MUST quit the
    app right away so the helper can proceed.

    Raises :class:`UpdateCheckError` if the update can't be applied.
    """
    ok, reason = can_self_update()
    if not ok:
        raise UpdateCheckError(reason)
    if not os.path.isfile(downloaded_path):
        raise UpdateCheckError("The downloaded file is missing.")

    if sys.platform == "win32":
        _apply_update_windows(downloaded_path)
    elif sys.platform == "darwin":
        _apply_update_macos(downloaded_path)
    else:  # pragma: no cover - guarded by can_self_update()
        raise UpdateCheckError("In-app updates aren't supported on this platform yet.")


def _apply_update_windows(new_exe: str) -> None:
    target = _running_exe()
    backup = target + ".bak"
    pid = os.getpid()
    tmp = tempfile.gettempdir()
    log = os.path.join(tmp, "spellbook_update.log")
    bat = os.path.join(tmp, f"spellbook_update_{pid}.bat")

    # `ping -n 2 127.0.0.1` is the reliable ~1s sleep for a detached .bat
    # (`timeout` fails when stdin is redirected). tasklist|find sets errorlevel 1
    # when the PID is gone.
    script = f"""@echo off
setlocal enableextensions
echo Spellbook update %DATE% %TIME% > "{log}"
:waitloop
tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL
if not errorlevel 1 (
    ping -n 2 127.0.0.1 >NUL
    goto waitloop
)
if exist "{backup}" del /f /q "{backup}" >> "{log}" 2>&1
move /y "{target}" "{backup}" >> "{log}" 2>&1
move /y "{new_exe}" "{target}" >> "{log}" 2>&1
if errorlevel 1 (
    echo swap failed - restoring backup >> "{log}"
    move /y "{backup}" "{target}" >> "{log}" 2>&1
)
start "" "{target}"
del /f /q "%~f0"
"""
    with open(bat, "w", encoding="ascii", errors="replace", newline="\r\n") as f:
        f.write(script)

    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000
    try:
        subprocess.Popen(
            ["cmd", "/c", bat],
            cwd=tmp,
            close_fds=True,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
        )
    except OSError as exc:
        _quiet_remove(bat)
        raise UpdateCheckError(f"Could not start the update helper: {exc}") from exc


def _apply_update_macos(zip_path: str) -> None:
    app = _macos_app_bundle()
    if not app:
        raise UpdateCheckError("Could not locate the Spellbook.app bundle.")
    backup = app + ".bak"
    pid = os.getpid()
    tmp = tempfile.gettempdir()
    extract_dir = tempfile.mkdtemp(prefix="spellbook_update_")
    log = os.path.join(tmp, "spellbook_update.log")
    sh = os.path.join(tmp, f"spellbook_update_{pid}.sh")

    script = f"""#!/bin/sh
exec >> "{log}" 2>&1
echo "Spellbook update $(date)"
while kill -0 {pid} 2>/dev/null; do sleep 0.5; done
set -e
/usr/bin/ditto -x -k "{zip_path}" "{extract_dir}"
NEW_APP=$(/usr/bin/find "{extract_dir}" -maxdepth 3 -name 'Spellbook.app' -type d | head -n 1)
if [ -z "$NEW_APP" ]; then echo "no Spellbook.app inside archive"; exit 1; fi
rm -rf "{backup}"
mv "{app}" "{backup}"
if /usr/bin/ditto "$NEW_APP" "{app}"; then
    /usr/bin/xattr -dr com.apple.quarantine "{app}" 2>/dev/null || true
else
    echo "swap failed - restoring backup"
    rm -rf "{app}"; mv "{backup}" "{app}"
fi
rm -rf "{extract_dir}"
/usr/bin/open "{app}"
rm -f "$0"
"""
    with open(sh, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(sh, 0o755)

    try:
        subprocess.Popen(
            ["/bin/sh", sh],
            cwd=tmp,
            close_fds=True,
            start_new_session=True,
        )
    except OSError as exc:
        _quiet_remove(sh)
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise UpdateCheckError(f"Could not start the update helper: {exc}") from exc


def cleanup_backup() -> None:
    """Delete the previous version's ``.bak`` left by a past update.

    Safe to call unconditionally at startup; does nothing when running from
    source or when no backup is present.
    """
    if not _is_frozen():
        return
    try:
        if sys.platform == "win32":
            backup = _running_exe() + ".bak"
            if os.path.isfile(backup):
                os.remove(backup)
        elif sys.platform == "darwin":
            app = _macos_app_bundle()
            if app and os.path.isdir(app + ".bak"):
                shutil.rmtree(app + ".bak", ignore_errors=True)
    except OSError:
        pass


def _quiet_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
