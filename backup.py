"""A full backup: everything the user made or changed, in one file another Spellbook can import.

Settings > Backup writes it and reads it back (ui/backup_dialogs.py); this module is the part with no
widgets. The file is an ordinary .zip with a ``manifest.json`` saying what is inside::

    manifest.json              {"format": "spellbook-backup", "version": 1, "app_version", "created",
                                "categories": {"content": {"count": 12, "bytes": 3456}, ...}}
    settings/settings.json     settings and keyboard shortcuts (machine-specific values left out)
    settings/font_settings.json, settings/custom_themes.json
    content.json               homebrew and edited content of every collection (a content_io bundle)
    random_tables.json         the user's tables, and official tables they changed
    characters.json            spell lists + sheets + portraits (a character_io bundle)
    studio.json                Homebrew Studio drafts
    calendars.json             game calendars and their trackers
    images/...                 content pictures: the pictures folder as it is, with its index.json
    tabletop/tabletop.json     tabletop scenes, and tabletop/assets/... their maps and token art
    tokens/...                 the token library
    pdfs/...                   the PDF library (the library folder, then one folder per extra folder)

Each category can be left out when exporting and when importing. Importing adds to what is already
installed: something with the same name (or id) is either replaced by the backup's or kept, as the person
chooses. Official content is never written: the other install has it already, and content_io refuses to
overwrite it anyway.
"""

from __future__ import annotations

import json
import os
import posixpath
import shutil
import tempfile
import zipfile
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple

FORMAT = "spellbook-backup"
VERSION = 1
MANIFEST = "manifest.json"
FILE_TYPES = [("Spellbook backup", "*.zip"), ("All files", "*.*")]

ProgressFn = Callable[[str, float], None]

# key -> (label, what it holds). The order is the order shown and the order of import (content before
# characters, so the homebrew a character uses is there when the character arrives).
CATEGORIES: "OrderedDict[str, Tuple[str, str]]" = OrderedDict([
    ("settings", ("Settings and shortcuts", "Preferences, keyboard shortcuts, fonts and your colour themes")),
    ("content", ("Homebrew and edited content", "Everything you added or changed in the collections: "
                                                 "spells, feats, classes, species, items, monsters, rules pages...")),
    ("random_tables", ("Random tables", "Your tables, and official tables you changed")),
    ("characters", ("Characters", "Spell lists, character sheets and portraits")),
    ("studio", ("Homebrew Studio drafts", "Drafts you have not published yet")),
    ("calendars", ("Calendars", "Game calendars, dates and progress trackers")),
    ("images", ("Pictures", "Content pictures and imported image packs")),
    ("tabletop", ("Tabletop maps", "Tabletop scenes with their maps, tokens, walls and fog")),
    ("tokens", ("Token library", "The pictures in your token library")),
    ("pdfs", ("PDF library", "The PDFs in your library folders (can be large)")),
])

# settings.json keys that belong to this computer, not to the person: never exported or imported
LOCAL_SETTINGS = {"lan_client_id", "lan_last_invite", "pdf_folders", "tracker_window_state",
                  "skipped_update_version", "initial_official_tag_applied"}
SETTINGS_FILES = ("settings.json", "font_settings.json", "custom_themes.json")

MAX_JSON_BYTES = 256 * 1024 * 1024          # one JSON member of a backup


class BackupError(ValueError):
    """The file can't be used (the message is meant for the person reading it)."""


def label(key: str) -> str:
    return CATEGORIES.get(key, (key, ""))[0]


def format_size(n: int) -> str:
    size = float(n)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} bytes"


# --------------------------------------------------------------------------- #
# Where everything is
# --------------------------------------------------------------------------- #

class Sources:
    """The stores a backup reads from and writes to. Anything not given is the app's own (the live
    singletons, so an import is seen at once and a later save doesn't write the old state back)."""

    def __init__(self, spell_manager=None, character_manager=None, sheet_manager=None,
                 data_dir: Optional[str] = None, studio_store=None, calendar_store=None,
                 image_store=None, tabletop=None, assets=None, token_folder: Optional[str] = None,
                 pdf_folders: Optional[List[str]] = None, pdf_target: Optional[str] = None,
                 settings_manager=None, random_tables=None):
        self.spell_manager = spell_manager
        self.character_manager = character_manager
        self.sheet_manager = sheet_manager
        self._data_dir = data_dir
        self._studio = studio_store
        self._calendars = calendar_store
        self._images = image_store
        self._tabletop = tabletop
        self._assets = assets
        self._tokens = token_folder
        self._pdf_folders = pdf_folders
        self._pdf_target = pdf_target
        self._settings = settings_manager
        self._random_tables = random_tables

    def path(self, name: str) -> str:
        if self._data_dir:
            return os.path.join(self._data_dir, name)
        from paths import user_data_path
        return user_data_path(name)

    @property
    def settings_manager(self):
        if self._settings is None:
            from settings import get_settings_manager
            self._settings = get_settings_manager()
        return self._settings

    @property
    def random_tables(self):
        if self._random_tables is None:
            from random_tables import get_random_tables_manager
            self._random_tables = get_random_tables_manager()
        return self._random_tables

    @property
    def studio_store(self):
        if self._studio is None:
            from studio_store import StudioStore
            self._studio = StudioStore(self.path("studio.json") if self._data_dir else None)
        return self._studio

    @property
    def calendar_store(self):
        if self._calendars is None:
            if self._data_dir:
                from calendar_state import CalendarStore
                self._calendars = CalendarStore(self.path("calendars.json"))
            else:
                from calendar_state import get_calendar_store
                self._calendars = get_calendar_store()
        return self._calendars

    @property
    def image_store(self):
        if self._images is None:
            if self._data_dir:
                from content_images import ImageStore
                self._images = ImageStore(self.path("images"))
            else:
                from content_images import get_image_store
                self._images = get_image_store()
        return self._images

    @property
    def tabletop(self):
        if self._tabletop is None:
            if self._data_dir:
                from tabletop import Tabletop
                self._tabletop = Tabletop(self.path(os.path.join("tabletop", "tabletop.json")))
            else:
                from tabletop import get_tabletop
                self._tabletop = get_tabletop()
        return self._tabletop

    @property
    def assets(self):
        if self._assets is None:
            if self._data_dir:
                from tabletop import AssetStore
                self._assets = AssetStore(self.path(os.path.join("tabletop", "assets")),
                                          self.path(os.path.join("tabletop", "cache")))
            else:
                from tabletop import get_assets
                self._assets = get_assets()
        return self._assets

    @property
    def token_folder(self) -> str:
        if self._tokens is None:
            if self._data_dir:
                self._tokens = self.path(os.path.join("tabletop", "tokens"))
            else:
                from tabletop import token_folder
                self._tokens = token_folder()
        return self._tokens

    @property
    def pdf_folders(self) -> List[str]:
        if self._pdf_folders is None:
            if self._data_dir:
                self._pdf_folders = [self.path("PDFs")]
            else:
                from pdf_library import library_folders
                self._pdf_folders = library_folders()
        return self._pdf_folders

    @property
    def pdf_target(self) -> str:
        """Where imported PDFs go: the library folder."""
        if self._pdf_target is None:
            self._pdf_target = self.pdf_folders[0] if self.pdf_folders else self.path("PDFs")
        return self._pdf_target


# --------------------------------------------------------------------------- #
# What each category holds (shared by the export and the counts the dialog shows)
# --------------------------------------------------------------------------- #

def _read_json(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _settings_payload(src: Sources) -> Dict[str, dict]:
    """settings file name -> its JSON (only files that exist; settings.json without the local keys)."""
    out: Dict[str, dict] = {}
    data = src.settings_manager.settings.to_dict()
    out["settings.json"] = {k: v for k, v in data.items() if k not in LOCAL_SETTINGS}
    for name in ("font_settings.json", "custom_themes.json"):
        value = _read_json(src.path(name))
        if isinstance(value, dict):
            out[name] = value
    return out


def _bundled_tables() -> Dict[str, dict]:
    from paths import resource_path
    from random_tables import RandomTable
    data = _read_json(resource_path("random_tables.json")) or {}
    out = {}
    for rec in data.get("random_tables", []) if isinstance(data, dict) else []:
        if isinstance(rec, dict) and rec.get("name"):
            out[str(rec["name"]).strip().lower()] = _table_key(RandomTable.from_dict(rec))
    return out


def _table_key(table) -> dict:
    d = table.to_dict()
    for k in ("is_official", "is_custom", "source"):
        d.pop(k, None)
    return d


def tables_to_export(src: Sources) -> list:
    """The user's own tables, and official tables whose entries (or name, die...) they changed."""
    bundled = None
    out = []
    for table in src.random_tables.tables:
        if not table.is_official or table.is_custom:
            out.append(table)
            continue
        if bundled is None:
            bundled = _bundled_tables()
        if bundled.get(table.name.lower()) != _table_key(table):
            out.append(table)
    return out


def _character_names(src: Sources) -> List[str]:
    names: List[str] = []
    if src.character_manager is not None:
        names.extend(c.name for c in src.character_manager.characters)
    if src.sheet_manager is not None:
        names.extend(getattr(src.sheet_manager, "_sheets", {}).keys())
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _walk_files(folder: str, exts: Optional[Tuple[str, ...]] = None) -> List[Tuple[str, str]]:
    """``[(path, relative posix path)]`` of the files under ``folder`` (sorted)."""
    out = []
    if not folder or not os.path.isdir(folder):
        return out
    for root, dirs, files in os.walk(folder):
        dirs.sort(key=str.lower)
        for f in sorted(files, key=str.lower):
            if f.endswith(".tmp") or (exts and os.path.splitext(f)[1].lower() not in exts):
                continue
            p = os.path.join(root, f)
            out.append((p, os.path.relpath(p, folder).replace(os.sep, "/")))
    return out


def _image_files(src: Sources) -> List[Tuple[str, str]]:
    store = src.image_store
    files, seen = [], set()
    for _kind, _key, entry in store.entries():
        rel = str(entry.get("file") or "")
        p = os.path.join(store.folder, rel)
        if rel and rel not in seen and os.path.isfile(p):
            seen.add(rel)
            files.append((p, rel.replace(os.sep, "/")))
    return files


def _asset_files(src: Sources) -> List[Tuple[str, str]]:
    """The map and token pictures the scenes use (from the DM's folder or the player cache)."""
    from tabletop import asset_ids_in
    used = set()
    for scene in list(src.tabletop.scenes.values()):
        used.update(asset_ids_in(scene))
    out = []
    for asset_id in sorted(used):
        p = src.assets.path(asset_id)
        if p:
            out.append((p, os.path.basename(p)))
    return out


def _pdf_files(src: Sources) -> List[Tuple[str, str]]:
    """``[(path, name in the backup)]``: the library folder's PDFs at the top, each extra folder's in a
    folder named after it."""
    out, used = [], set()
    for i, folder in enumerate(src.pdf_folders):
        prefix = ""
        if i:
            base = os.path.basename(os.path.normpath(folder)) or f"Folder {i}"
            prefix, n = base, 2
            while prefix.lower() in used:
                prefix, n = f"{base} {n}", n + 1
            used.add(prefix.lower())
            prefix += "/"
        for p, rel in _walk_files(folder, (".pdf",)):
            out.append((p, prefix + rel))
    return out


def _sizes(files: Iterable[Tuple[str, str]]) -> int:
    total = 0
    for p, _ in files:
        try:
            total += os.path.getsize(p)
        except OSError:
            pass
    return total


@dataclass
class CategoryInfo:
    count: int = 0
    bytes: int = 0
    error: str = ""

    def describe(self, key: str) -> str:
        if self.error:
            return f"could not be read ({self.error})"
        unit = {"settings": "file", "content": "entry", "random_tables": "table", "characters": "character",
                "studio": "draft", "calendars": "calendar", "images": "picture", "tabletop": "scene",
                "tokens": "token", "pdfs": "PDF"}.get(key, "item")
        plural = {"entry": "entries"}.get(unit, unit + "s")
        text = f"{self.count} {unit if self.count == 1 else plural}"
        if self.bytes >= 1024 * 1024:
            text += f", {format_size(self.bytes)}"
        return text


def summarize(src: Sources, keys: Optional[Iterable[str]] = None) -> "OrderedDict[str, CategoryInfo]":
    """How much each category would put in a backup (for the export dialog)."""
    out: "OrderedDict[str, CategoryInfo]" = OrderedDict()
    for key in (keys or CATEGORIES):
        info = CategoryInfo()
        try:
            if key == "settings":
                info.count = len(_settings_payload(src))
            elif key == "content":
                import content_io
                info.count = sum(len(v) for v in content_io.collect_export(src.spell_manager).values())
            elif key == "random_tables":
                info.count = len(tables_to_export(src))
            elif key == "characters":
                info.count = len(_character_names(src))
            elif key == "studio":
                info.count = len(src.studio_store.drafts)
            elif key == "calendars":
                info.count = len(src.calendar_store.campaigns)
            elif key == "images":
                files = _image_files(src)
                info.count, info.bytes = src.image_store.count(), _sizes(files)
            elif key == "tabletop":
                info.count = len(src.tabletop.scenes)
                info.bytes = _sizes(_asset_files(src))
            elif key == "tokens":
                files = _walk_files(src.token_folder)
                info.count, info.bytes = len(files), _sizes(files)
            elif key == "pdfs":
                files = _pdf_files(src)
                info.count, info.bytes = len(files), _sizes(files)
        except Exception as e:                    # one broken store must not hide the others
            info.error = str(e) or type(e).__name__
        out[key] = info
    return out


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #

def _app_version() -> str:
    try:
        from version import __version__
        return __version__
    except Exception:
        return ""


@dataclass
class ExportResult:
    path: str = ""
    counts: "OrderedDict[str, int]" = field(default_factory=OrderedDict)
    bytes: int = 0
    warnings: List[str] = field(default_factory=list)


def export_backup(path: str, src: Sources, keys: Iterable[str],
                  progress: Optional[ProgressFn] = None) -> ExportResult:
    """Write a backup of the chosen categories to ``path`` (written to a temporary file first, so a failed
    export never leaves half a file behind)."""
    keys = [k for k in CATEGORIES if k in set(keys)]
    if not keys:
        raise BackupError("Choose at least one thing to include.")
    result = ExportResult(path=path)
    manifest = {"format": FORMAT, "version": VERSION, "app_version": _app_version(),
                "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "categories": {}}
    folder = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".spellbook-backup-", suffix=".tmp", dir=folder)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
            def put_json(name: str, data) -> int:
                text = json.dumps(data, ensure_ascii=False, indent=1)
                z.writestr(name, text)
                return len(text.encode("utf-8"))

            def put_files(prefix: str, files: List[Tuple[str, str]]) -> int:
                total = 0
                for p, rel in files:
                    try:
                        # pictures and PDFs are compressed already: storing them is as small and much faster
                        z.write(p, prefix + rel, compress_type=zipfile.ZIP_STORED)
                        total += os.path.getsize(p)
                    except OSError as e:
                        result.warnings.append(f"Left out {rel}: {e}")
                return total

            for i, key in enumerate(keys):
                if progress:
                    progress(f"Adding {label(key).lower()}…", i / len(keys))
                count = size = 0
                try:
                    count, size = _export_category(key, src, put_json, put_files, result)
                except Exception as e:
                    result.warnings.append(f"{label(key)} could not be exported: {e}")
                    continue
                manifest["categories"][key] = {"count": count, "bytes": size}
                result.counts[key] = count
            z.writestr(MANIFEST, json.dumps(manifest, indent=1))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    result.bytes = os.path.getsize(path)
    if progress:
        progress("Done", 1.0)
    return result


def _export_category(key, src: Sources, put_json, put_files, result: ExportResult) -> Tuple[int, int]:
    if key == "settings":
        payload = _settings_payload(src)
        size = sum(put_json(f"settings/{name}", data) for name, data in payload.items())
        return len(payload), size
    if key == "content":
        import content_io
        data, counts = content_io.export_bundle(src.spell_manager)
        return sum(counts.values()), put_json("content.json", data)
    if key == "random_tables":
        tables = tables_to_export(src)
        return len(tables), put_json("random_tables.json", {"random_tables": [t.to_dict() for t in tables]})
    if key == "characters":
        import character_io
        names = _character_names(src)
        if src.character_manager is None or src.sheet_manager is None:
            return 0, 0
        data, _lists, _sheets = character_io.build_export(names, src.character_manager, src.sheet_manager)
        return len(names), put_json("characters.json", data)
    if key == "studio":
        store = src.studio_store
        data = {"version": 1, "drafts": [d.to_dict() for d in store.drafts]}
        return len(store.drafts), put_json("studio.json", data)
    if key == "calendars":
        store = src.calendar_store
        data = {"version": 1, "active": store.active_id, "campaigns": [c.to_dict() for c in store.campaigns]}
        return len(store.campaigns), put_json("calendars.json", data)
    if key == "images":
        store = src.image_store
        index = {"version": 1, "images": {k: dict(v) for k, v in store._index.items()},
                 "packs": dict(store._packs)}
        size = put_json("images/index.json", index)
        return store.count(), size + put_files("images/", _image_files(src))
    if key == "tabletop":
        tt = src.tabletop
        with tt._lock:
            data = {"version": 1, "scenes": [tt.scenes[i] for i in tt.order if i in tt.scenes]}
            size = put_json("tabletop/tabletop.json", data)
        return len(data["scenes"]), size + put_files("tabletop/assets/", _asset_files(src))
    if key == "tokens":
        files = _walk_files(src.token_folder)
        return len(files), put_files("tokens/", files)
    if key == "pdfs":
        files = _pdf_files(src)
        return len(files), put_files("pdfs/", files)
    return 0, 0


# --------------------------------------------------------------------------- #
# Reading a backup
# --------------------------------------------------------------------------- #

@dataclass
class Manifest:
    app_version: str = ""
    created: str = ""
    categories: "OrderedDict[str, CategoryInfo]" = field(default_factory=OrderedDict)


def safe_member(name: str, prefix: str) -> Optional[str]:
    """The part of ``name`` after ``prefix`` when it is a plain relative path (no drive, no ``..``), else
    None: a backup must never write outside the folder it is unpacked into."""
    if not name.startswith(prefix) or name.endswith("/"):
        return None
    rel = name[len(prefix):]
    if not rel or "\\" in rel or ":" in rel or rel.startswith("/"):
        return None
    norm = posixpath.normpath(rel)
    if norm.startswith("..") or norm.startswith("/") or norm == ".":
        return None
    if any(part in ("", ".", "..") for part in norm.split("/")):
        return None
    return norm


def _open_zip(path: str) -> zipfile.ZipFile:
    try:
        z = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as e:
        raise BackupError(f"This is not a Spellbook backup (it can't be opened as a .zip: {e}).")
    return z


def read_manifest(path: str) -> Manifest:
    """What a backup holds. Raises :class:`BackupError` for anything that is not a usable backup."""
    with _open_zip(path) as z:
        return _manifest(z)


def _manifest(z: zipfile.ZipFile) -> Manifest:
    try:
        data = json.loads(z.read(MANIFEST).decode("utf-8"))
    except KeyError:
        raise BackupError("This .zip is not a Spellbook backup (it has no manifest.json). "
                          "Image packs are imported under Pictures, token packs on the Tabletop.")
    except (ValueError, UnicodeDecodeError) as e:
        raise BackupError(f"The backup's manifest can't be read ({e}).")
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise BackupError("This .zip is not a Spellbook backup.")
    ver = data.get("version")
    if isinstance(ver, int) and ver > VERSION:
        raise BackupError("This backup was made by a newer version of Spellbook. Please update the app.")
    m = Manifest(app_version=str(data.get("app_version", "")), created=str(data.get("created", "")))
    cats = data.get("categories") if isinstance(data.get("categories"), dict) else {}
    for key in CATEGORIES:
        if key in cats:
            c = cats[key] if isinstance(cats[key], dict) else {}
            m.categories[key] = CategoryInfo(count=_int(c.get("count")), bytes=_int(c.get("bytes")))
    return m


def _int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _load_json(z: zipfile.ZipFile, name: str):
    try:
        info = z.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_JSON_BYTES:
        raise BackupError(f"{name} in the backup is too large.")
    try:
        return json.loads(z.read(info).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise BackupError(f"{name} in the backup can't be read ({e}).")


def _extract(z: zipfile.ZipFile, info: zipfile.ZipInfo, dest: str) -> None:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    tmp = dest + ".tmp"
    with z.open(info) as fin, open(tmp, "wb") as fout:
        shutil.copyfileobj(fin, fout, 1024 * 1024)
    os.replace(tmp, dest)


def _members(z: zipfile.ZipFile, prefix: str) -> List[Tuple[zipfile.ZipInfo, str]]:
    out = []
    for info in z.infolist():
        rel = safe_member(info.filename, prefix)
        if rel is not None:
            out.append((info, rel))
    return out


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #

@dataclass
class ImportResult:
    lines: "OrderedDict[str, str]" = field(default_factory=OrderedDict)    # category -> what happened
    warnings: List[str] = field(default_factory=list)
    changed: set = field(default_factory=set)                              # categories that changed something
    restart_needed: bool = False                                            # appearance / shortcuts

    def summary(self) -> str:
        return "\n".join(f"{label(k)}: {v}" for k, v in self.lines.items())


def _counted(added: int, replaced: int, kept: int, noun: str = "") -> str:
    parts = []
    if added:
        parts.append(f"{added} added")
    if replaced:
        parts.append(f"{replaced} replaced")
    if kept:
        parts.append(f"{kept} kept as they were")
    return ", ".join(parts) or "nothing new"


def import_backup(path: str, src: Sources, keys: Iterable[str], replace: bool = True,
                  progress: Optional[ProgressFn] = None) -> ImportResult:
    """Add the chosen categories of a backup to this install.

    ``replace``: something already here with the same name (or id) is replaced by the backup's; otherwise
    it is kept and the backup's copy is skipped. Settings are always taken from the backup when chosen.
    """
    result = ImportResult()
    with _open_zip(path) as z:
        manifest = _manifest(z)
        wanted = [k for k in CATEGORIES if k in set(keys) and k in manifest.categories]
        for i, key in enumerate(wanted):
            if progress:
                progress(f"Importing {label(key).lower()}…", i / max(1, len(wanted)))
            try:
                line = _IMPORTERS[key](z, src, replace, result)
            except BackupError as e:
                result.warnings.append(f"{label(key)}: {e}")
                continue
            except Exception as e:                       # a bug in one part must not lose the others
                result.warnings.append(f"{label(key)} could not be imported: {e}")
                continue
            result.lines[key] = line
    if progress:
        progress("Done", 1.0)
    return result


def _import_settings(z, src: Sources, replace: bool, result: ImportResult) -> str:
    from settings import AppSettings
    done = []
    incoming = _load_json(z, "settings/settings.json")
    if isinstance(incoming, dict):
        sm = src.settings_manager
        current = sm.settings.to_dict()
        merged = dict(current)
        merged.update({k: v for k, v in incoming.items() if k not in LOCAL_SETTINGS and k in current})
        sm._settings = AppSettings.from_dict(merged)
        sm.save()
        try:
            sm._notify_listeners()
        except Exception:
            pass
        done.append("preferences and shortcuts")

    fonts = _load_json(z, "settings/font_settings.json")
    if isinstance(fonts, dict):
        from atomic_io import atomic_write_json
        atomic_write_json(src.path("font_settings.json"), fonts)
        if not src._data_dir:
            try:
                from typography import get_font_manager
                get_font_manager().load()
            except Exception:
                pass
        done.append("fonts")

    themes = _load_json(z, "settings/custom_themes.json")
    if isinstance(themes, dict) and isinstance(themes.get("themes"), list):
        mine = _read_json(src.path("custom_themes.json"))
        mine_list = mine.get("themes", []) if isinstance(mine, dict) else []
        by_id = OrderedDict((str(t.get("id")), t) for t in mine_list if isinstance(t, dict) and t.get("id"))
        added = 0
        for t in themes["themes"]:
            if not isinstance(t, dict) or not t.get("id"):
                continue
            tid = str(t["id"])
            if tid not in by_id or replace:
                added += tid not in by_id
                by_id[tid] = t
        from atomic_io import atomic_write_json
        atomic_write_json(src.path("custom_themes.json"), {"version": 2, "themes": list(by_id.values())})
        if not src._data_dir:
            try:
                from theme import get_theme_manager
                get_theme_manager().load_custom_themes()
            except Exception:
                pass
        done.append("colour themes")
    if done:
        result.changed.add("settings")
        result.restart_needed = True
    return ", ".join(done).capitalize() + " imported" if done else "nothing to import"


def _import_content(z, src: Sources, replace: bool, result: ImportResult) -> str:
    import content_io
    data = _load_json(z, "content.json")
    if not isinstance(data, dict):
        return "nothing to import"
    try:
        content_io.check_bundle(data)
    except ValueError as e:
        if "No recognised content" in str(e):
            return "nothing to import"
        raise BackupError(str(e))
    kept = 0
    if not replace:
        preview = content_io.preview_bundle(data, src.spell_manager)
        kept = len(preview.replaces)
        data = content_io.resolve_bundle(data, default=content_io.CLASH_SKIP, spell_manager=src.spell_manager)
    report = content_io.import_bundle(data, src.spell_manager, link_mentions=False)
    for line in report.problem_lines(limit=10):
        result.warnings.append(f"Content: {line}")
    if report.imported:
        result.changed.add("content")
    added, updated = sum(report.added.values()), sum(report.updated.values())
    text = _counted(added, updated, kept)
    if report.skipped:
        text += f"; {len(report.skipped)} skipped (official content has that name)"
    return text


def _import_random_tables(z, src: Sources, replace: bool, result: ImportResult) -> str:
    from random_tables import RandomTable
    data = _load_json(z, "random_tables.json")
    recs = data.get("random_tables", []) if isinstance(data, dict) else []
    mgr = src.random_tables
    added = replaced = kept = 0
    for rec in recs if isinstance(recs, list) else []:
        if not isinstance(rec, dict):
            continue
        table = RandomTable.from_dict(rec)
        if not table.name:
            continue
        exists = mgr.get_table(table.name) is not None
        if exists and not replace:
            kept += 1
            continue
        table.id = None
        mgr.add_table(table)
        replaced += exists
        added += not exists
    if added or replaced:
        result.changed.add("random_tables")
    return _counted(added, replaced, kept)


def _import_characters(z, src: Sources, replace: bool, result: ImportResult) -> str:
    import character_io
    if src.character_manager is None or src.sheet_manager is None:
        raise BackupError("characters can't be imported here")
    data = _load_json(z, "characters.json")
    if data is None:
        return "nothing to import"
    try:
        bundle = character_io.parse_bundle(data)
    except character_io.CharacterBundleError as e:
        raise BackupError(str(e))
    plan = character_io.plan_import(bundle, src.character_manager, src.sheet_manager)
    policy = character_io.REPLACE if replace else character_io.SKIP
    report = character_io.apply_import(bundle, src.character_manager, src.sheet_manager, src.spell_manager,
                                       default_policy=policy)
    result.warnings.extend(f"Characters: {w}" for w in report.warnings[:10])
    replaced = len(plan.conflicts) - len(report.skipped)
    added = len(plan.names) - len(plan.conflicts)
    if added or replaced:
        result.changed.add("characters")
    return _counted(added, replaced, len(report.skipped))


def _import_studio(z, src: Sources, replace: bool, result: ImportResult) -> str:
    from studio_store import KINDS, Draft
    data = _load_json(z, "studio.json")
    raws = data.get("drafts", []) if isinstance(data, dict) else []
    store = src.studio_store
    added = replaced = kept = 0
    for raw in raws if isinstance(raws, list) else []:
        if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
            continue
        draft = Draft.from_dict(raw)
        existing = store.get(draft.id)
        if existing is not None:
            if not replace:
                kept += 1
                continue
            store.drafts[store.drafts.index(existing)] = draft
            replaced += 1
        else:
            store.drafts.append(draft)
            added += 1
    if added or replaced:
        store.save()
        result.changed.add("studio")
    return _counted(added, replaced, kept)


def _import_calendars(z, src: Sources, replace: bool, result: ImportResult) -> str:
    from calendar_state import Campaign
    data = _load_json(z, "calendars.json")
    raws = data.get("campaigns", []) if isinstance(data, dict) else []
    store = src.calendar_store
    added = replaced = kept = 0
    for raw in raws if isinstance(raws, list) else []:
        if not isinstance(raw, dict):
            continue
        try:
            campaign = Campaign.from_dict(raw)
        except (TypeError, ValueError) as e:
            result.warnings.append(f"Calendars: one could not be read ({e})")
            continue
        index = next((i for i, c in enumerate(store.campaigns) if c.id == campaign.id), None)
        if index is not None:
            if not replace:
                kept += 1
                continue
            store.campaigns[index] = campaign
            replaced += 1
        else:
            store.campaigns.append(campaign)
            added += 1
    if added or replaced:
        if not store.active_id or store.active_id not in {c.id for c in store.campaigns}:
            active = data.get("active") if isinstance(data, dict) else None
            store.active_id = active if active in {c.id for c in store.campaigns} else store.campaigns[0].id
        store.save()
        result.changed.add("calendars")
    return _counted(added, replaced, kept)


def _import_images(z, src: Sources, replace: bool, result: ImportResult) -> str:
    from content_images import KINDS, name_key
    index = _load_json(z, "images/index.json")
    if not isinstance(index, dict):
        return "nothing to import"
    store = src.image_store
    members = {rel: info for info, rel in _members(z, "images/")}
    added = replaced = kept = 0
    for kind, entries in (index.get("images") or {}).items():
        if kind not in KINDS or not isinstance(entries, dict):
            continue
        for key, entry in entries.items():
            if not isinstance(entry, dict):
                continue
            rel = safe_member("images/" + str(entry.get("file") or ""), "images/")
            info = members.get(rel) if rel else None
            if info is None:
                continue
            existing = store._index.get(kind, {}).get(name_key(str(entry.get("name") or key)))
            if existing and not replace:
                kept += 1
                continue
            dest = os.path.join(store.folder, *rel.split("/"))
            if not os.path.exists(dest):
                _extract(z, info, dest)
            store._set(kind, str(entry.get("name") or key), rel, str(entry.get("pack") or ""))
            replaced += bool(existing)
            added += not existing
    packs = index.get("packs")
    if isinstance(packs, dict):
        for pid, meta in packs.items():
            if isinstance(meta, dict) and (pid not in store._packs or replace):
                store._packs[pid] = meta
    if added or replaced:
        store.save()
        result.changed.add("images")
    return _counted(added, replaced, kept)


def _import_tabletop(z, src: Sources, replace: bool, result: ImportResult) -> str:
    from tabletop import valid_asset_id
    data = _load_json(z, "tabletop/tabletop.json")
    scenes = data.get("scenes", []) if isinstance(data, dict) else []
    assets = src.assets
    for info, rel in _members(z, "tabletop/assets/"):
        name, ext = os.path.splitext(rel)
        if "/" in rel or ext.lower() not in (".png", ".jpg") or not valid_asset_id(name):
            continue
        dest = os.path.join(assets.folder, rel)
        if not os.path.exists(dest):
            _extract(z, info, dest)
    tt = src.tabletop
    added = replaced = kept = 0
    with tt._lock:
        for scene in scenes if isinstance(scenes, list) else []:
            if not isinstance(scene, dict) or not scene.get("id"):
                continue
            sid = str(scene["id"])
            if sid in tt.scenes:
                if not replace:
                    kept += 1
                    continue
                replaced += 1
            else:
                tt.order.append(sid)
                added += 1
            tt.scenes[sid] = tt._repair(scene)
    if added or replaced:
        tt.save()
        tt._changed(None)
        result.changed.add("tabletop")
    return _counted(added, replaced, kept)


def _copy_folder(z, prefix: str, dest_folder: str, replace: bool,
                 exts: Optional[Tuple[str, ...]] = None) -> Tuple[int, int, int]:
    added = replaced = kept = 0
    for info, rel in _members(z, prefix):
        if exts and os.path.splitext(rel)[1].lower() not in exts:
            continue
        dest = os.path.join(dest_folder, *rel.split("/"))
        if os.path.exists(dest):
            try:
                same = os.path.getsize(dest) == info.file_size
            except OSError:
                same = False
            if same or not replace:
                kept += 1
                continue
            _extract(z, info, dest)
            replaced += 1
        else:
            _extract(z, info, dest)
            added += 1
    return added, replaced, kept


def _import_tokens(z, src: Sources, replace: bool, result: ImportResult) -> str:
    from tabletop import IMAGE_TYPES
    added, replaced, kept = _copy_folder(z, "tokens/", src.token_folder, replace, tuple(IMAGE_TYPES))
    if added or replaced:
        result.changed.add("tokens")
    return _counted(added, replaced, kept)


def _import_pdfs(z, src: Sources, replace: bool, result: ImportResult) -> str:
    added, replaced, kept = _copy_folder(z, "pdfs/", src.pdf_target, replace, (".pdf",))
    if added or replaced:
        result.changed.add("pdfs")
    return _counted(added, replaced, kept)


_IMPORTERS = {
    "settings": _import_settings, "content": _import_content, "random_tables": _import_random_tables,
    "characters": _import_characters, "studio": _import_studio, "calendars": _import_calendars,
    "images": _import_images, "tabletop": _import_tabletop, "tokens": _import_tokens, "pdfs": _import_pdfs,
}
