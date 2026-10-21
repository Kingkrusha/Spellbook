"""
Pictures for content: a spell, monster, magic item, feat... can each have one image.

No artwork ships with the app. A user adds a picture to one entry from its page, or imports an *image pack*:
a .zip (or a folder) of pictures named after the entries they belong to::

    my-pack.zip
        pack.json                  (optional: {"name": ..., "author": ..., "version": ...})
        monsters/Goblin.png
        monsters/Adult Red Dragon.jpg
        spells/Fireball.webp
        magic items/Bag of Holding.png

The folder says which collection a picture is for (see KIND_ALIASES) and the file name says which entry
(matched ignoring case, spaces and punctuation, so ``adult-red-dragon.png`` finds "Adult Red Dragon"). A pack
can also list its pictures in pack.json (``"images": [{"kind": "monsters", "name": "Goblin", "file": "g.png"}]``).

Pictures are downscaled (longest side MAX_SIDE) and copied into ``images/`` in the user data folder, which
also holds ``index.json``: collection -> entry key -> file, plus which pack each picture came from (so a pack
can be removed again). Nothing is stored in the database, so a picture never slows a query, and the app's own
download does not grow.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

MAX_SIDE = 1024
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
ACCEPTED_TYPES = [("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")]
INDEX_FILE = "index.json"
USER_PACK = ""                       # pictures the user added one at a time

# collection key -> what it is called on screen
KINDS: Dict[str, str] = {
    "spells": "Spells", "monsters": "Monsters", "magic_items": "Magic Items", "equipment": "Equipment",
    "feats": "Feats", "lineages": "Species", "backgrounds": "Backgrounds", "classes": "Classes",
}
KIND_ALIASES: Dict[str, str] = {}
for _key, _label in KINDS.items():
    for _alias in (_key, _label, _key.rstrip("s"), _label.rstrip("s")):
        KIND_ALIASES[re.sub(r"[^a-z]", "", _alias.lower())] = _key
KIND_ALIASES.update({"creatures": "monsters", "creature": "monsters", "items": "magic_items",
                     "magicitem": "magic_items", "lineage": "lineages", "races": "lineages", "race": "lineages",
                     "species": "lineages", "gear": "equipment", "weapons": "equipment", "armor": "equipment"})


def kind_for(folder: str) -> Optional[str]:
    return KIND_ALIASES.get(re.sub(r"[^a-z]", "", (folder or "").lower()))


def name_key(name: str) -> str:
    """How names are matched: case, spaces and punctuation don't count ("Adult Red Dragon" = adult-red-dragon)."""
    return re.sub(r"[^0-9a-z]+", "", (name or "").lower())


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "image").lower()).strip("-")[:40] or "image"


@dataclass
class PackInfo:
    id: str
    name: str
    author: str = ""
    version: str = ""
    count: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "author": self.author, "version": self.version}


@dataclass
class ImportReport:
    pack: Optional[PackInfo] = None
    added: int = 0
    replaced: int = 0
    kept: int = 0                    # an entry already had a picture and "replace" was off
    skipped: List[str] = field(default_factory=list)    # files that are not pictures or not in a known folder


class ImageStore:
    """The pictures folder and its index."""

    def __init__(self, folder: Optional[str] = None):
        if folder is None:
            from paths import user_data_path
            folder = user_data_path("images")
        self.folder = folder
        # kind -> key -> {"file": ..., "name": ..., "pack": ...}
        self._index: Dict[str, Dict[str, dict]] = {}
        self._packs: Dict[str, dict] = {}
        self._listeners: List[Callable[[], None]] = []
        self.load()

    # ---- index

    @property
    def index_path(self) -> str:
        return os.path.join(self.folder, INDEX_FILE)

    def load(self):
        self._index, self._packs = {}, {}
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        images = data.get("images", {}) if isinstance(data, dict) else {}
        for kind, entries in images.items():
            if kind in KINDS and isinstance(entries, dict):
                self._index[kind] = {k: v for k, v in entries.items() if isinstance(v, dict) and v.get("file")}
        packs = data.get("packs", {}) if isinstance(data, dict) else {}
        self._packs = {k: v for k, v in packs.items() if isinstance(v, dict)}

    def save(self):
        from atomic_io import atomic_write_json
        os.makedirs(self.folder, exist_ok=True)
        atomic_write_json(self.index_path, {"version": 1, "images": self._index, "packs": self._packs})
        for listener in list(self._listeners):
            try:
                listener()
            except Exception as e:
                print(f"Image listener failed: {e}")

    def add_listener(self, callback: Callable[[], None]):
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]):
        if callback in self._listeners:
            self._listeners.remove(callback)

    # ---- reading

    def path_for(self, kind: str, name: str) -> Optional[str]:
        """The picture of an entry, or None."""
        entry = self._index.get(kind, {}).get(name_key(name))
        if not entry:
            # a versioned entry ("Fireball (Legacy)") falls back to its main picture
            base = re.sub(r"\s*\((legacy|2014|2024)\)\s*$", "", name or "", flags=re.IGNORECASE)
            if base != name:
                entry = self._index.get(kind, {}).get(name_key(base))
        if not entry:
            return None
        path = os.path.join(self.folder, entry["file"])
        return path if os.path.isfile(path) else None

    def has(self, kind: str, name: str) -> bool:
        return self.path_for(kind, name) is not None

    def count(self, kind: Optional[str] = None) -> int:
        if kind:
            return len(self._index.get(kind, {}))
        return sum(len(v) for v in self._index.values())

    def entries(self) -> Iterable[Tuple[str, str, dict]]:
        for kind, entries in self._index.items():
            for key, entry in entries.items():
                yield kind, key, entry

    def packs(self) -> List[PackInfo]:
        counts: Dict[str, int] = {}
        for _kind, _key, entry in self.entries():
            counts[entry.get("pack", USER_PACK)] = counts.get(entry.get("pack", USER_PACK), 0) + 1
        return [PackInfo(pid, p.get("name", pid), p.get("author", ""), p.get("version", ""), counts.get(pid, 0))
                for pid, p in self._packs.items()]

    def size_on_disk(self) -> int:
        total = 0
        for _kind, _key, entry in self.entries():
            try:
                total += os.path.getsize(os.path.join(self.folder, entry["file"]))
            except OSError:
                pass
        return total

    # ---- writing

    def _write_image(self, image, kind: str, name: str) -> str:
        """Downscale and save a PIL image; returns the file name (relative to the folder)."""
        from PIL import Image
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        has_alpha = image.mode in ("RGBA", "LA", "P") and (
            image.mode != "P" or "transparency" in image.info)
        buffer = io.BytesIO()
        if has_alpha:
            image = image.convert("RGBA")
            image.save(buffer, format="PNG", optimize=True)
            ext = "png"
        else:
            image = image.convert("RGB")
            image.save(buffer, format="JPEG", quality=85, optimize=True)
            ext = "jpg"
        data = buffer.getvalue()
        rel = f"{kind}/{_slug(name)}-{hashlib.sha1(data).hexdigest()[:10]}.{ext}"
        os.makedirs(os.path.join(self.folder, kind), exist_ok=True)
        with open(os.path.join(self.folder, rel), "wb") as f:
            f.write(data)
        return rel

    def _set(self, kind: str, name: str, rel: str, pack: str):
        old = self._index.setdefault(kind, {}).get(name_key(name))
        self._index[kind][name_key(name)] = {"file": rel, "name": name, "pack": pack}
        if old and old.get("file") != rel:
            self._delete_file_if_unused(old["file"])

    def _delete_file_if_unused(self, rel: str):
        if any(e.get("file") == rel for _k, _n, e in self.entries()):
            return
        try:
            os.remove(os.path.join(self.folder, rel))
        except OSError:
            pass

    def set_image_file(self, kind: str, name: str, source_path: str) -> str:
        """Give one entry the picture in ``source_path``. Raises if it is not a picture."""
        from PIL import Image
        if kind not in KINDS:
            raise ValueError(f"Unknown collection '{kind}'")
        with Image.open(source_path) as img:
            img.load()
            rel = self._write_image(img.copy(), kind, name)
        self._set(kind, name, rel, USER_PACK)
        self.save()
        return rel

    def remove_image(self, kind: str, name: str) -> bool:
        entry = self._index.get(kind, {}).pop(name_key(name), None)
        if entry is None:
            return False
        self._delete_file_if_unused(entry["file"])
        self.save()
        return True

    # ---- packs

    def import_pack(self, source: str, replace: bool = False,
                    progress: Optional[Callable[[int, int], None]] = None) -> ImportReport:
        """Import a pack from a .zip file or a folder. Entries that already have a picture keep it unless
        ``replace``. Pictures for entries the app doesn't have (yet) are imported too: they show up once the
        entry exists (a homebrew monster added later, say)."""
        from PIL import Image
        report = ImportReport()
        files = _PackFiles(source)
        try:
            meta = files.manifest()
            base = os.path.splitext(os.path.basename(source.rstrip("/\\")))[0]
            pack_id = _slug(meta.get("id") or meta.get("name") or base)
            info = PackInfo(pack_id, str(meta.get("name") or base), str(meta.get("author", "")),
                            str(meta.get("version", "")))
            items = files.listed(meta) if meta.get("images") else files.by_folder()
            report.skipped.extend(files.skipped)
            for i, (kind, name, member) in enumerate(items):
                if progress:
                    progress(i, len(items))
                existing = self._index.get(kind, {}).get(name_key(name))
                if existing and not replace and existing.get("pack") != pack_id:
                    report.kept += 1
                    continue
                try:
                    with files.open(member) as fh, Image.open(fh) as img:
                        img.load()
                        rel = self._write_image(img.copy(), kind, name)
                except Exception:
                    report.skipped.append(member)
                    continue
                self._set(kind, name, rel, pack_id)
                if existing:
                    report.replaced += 1
                else:
                    report.added += 1
        finally:
            files.close()
        if report.added or report.replaced:
            self._packs[pack_id] = info.to_dict()
        info.count = report.added + report.replaced
        report.pack = info
        self.save()
        return report

    def remove_pack(self, pack_id: str) -> int:
        removed = 0
        for kind in list(self._index):
            for key in [k for k, e in self._index[kind].items() if e.get("pack") == pack_id]:
                entry = self._index[kind].pop(key)
                self._delete_file_if_unused(entry["file"])
                removed += 1
        self._packs.pop(pack_id, None)
        self.save()
        return removed

    def export_pack(self, zip_path: str, name: str = "My pictures", author: str = "",
                    kinds: Optional[Iterable[str]] = None) -> int:
        """Write every picture (or those of ``kinds``) into a pack another user can import."""
        wanted = set(kinds) if kinds else None
        count = 0
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("pack.json", json.dumps({"name": name, "author": author, "version": "1"}, indent=1))
            used = set()
            for kind, _key, entry in self.entries():
                if wanted is not None and kind not in wanted:
                    continue
                src = os.path.join(self.folder, entry["file"])
                if not os.path.isfile(src):
                    continue
                ext = os.path.splitext(src)[1]
                safe = re.sub(r'[\\/:*?"<>|]+', "", entry.get("name") or _key) or "image"
                arc = f"{KINDS[kind]}/{safe}{ext}"
                n = 2
                while arc.lower() in used:
                    arc = f"{KINDS[kind]}/{safe} {n}{ext}"
                    n += 1
                used.add(arc.lower())
                z.write(src, arc)        # already compressed pictures: stored, not deflated again
                count += 1
        return count


class _PackFiles:
    """The files of a pack, from a zip or a folder."""

    def __init__(self, source: str):
        self.source = source
        self.skipped: List[str] = []
        if os.path.isdir(source):
            self._zip = None
            self._names = []
            for root, _dirs, names in os.walk(source):
                for n in names:
                    self._names.append(os.path.relpath(os.path.join(root, n), source).replace(os.sep, "/"))
        else:
            self._zip = zipfile.ZipFile(source)
            self._names = [n for n in self._zip.namelist() if not n.endswith("/")]
        self._names = [n for n in self._names if "__MACOSX" not in n and not os.path.basename(n).startswith(".")]
        # a zip of a folder ("pack/monsters/x.png"): drop the shared top folder
        tops = {n.split("/", 1)[0] for n in self._names if "/" in n}
        self._prefix = ""
        if len(tops) == 1 and all("/" in n for n in self._names) and kind_for(next(iter(tops))) is None:
            self._prefix = next(iter(tops)) + "/"

    def close(self):
        if self._zip is not None:
            self._zip.close()

    def open(self, member: str):
        if self._zip is not None:
            return io.BytesIO(self._zip.read(member))
        return open(os.path.join(self.source, member), "rb")

    def manifest(self) -> dict:
        name = self._prefix + "pack.json"
        if name not in self._names:
            return {}
        try:
            with self.open(name) as f:
                data = json.loads(f.read().decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, OSError, UnicodeDecodeError):
            return {}

    def by_folder(self) -> List[Tuple[str, str, str]]:
        items = []
        for member in self._names:
            rel = member[len(self._prefix):]
            if rel == "pack.json":
                continue
            if os.path.splitext(rel)[1].lower() not in IMAGE_EXTS:
                self.skipped.append(member)
                continue
            parts = rel.split("/")
            kind = kind_for(parts[0]) if len(parts) >= 2 else None
            if kind is None:
                self.skipped.append(member)
                continue
            items.append((kind, os.path.splitext(parts[-1])[0], member))
        return items

    def listed(self, meta: dict) -> List[Tuple[str, str, str]]:
        items = []
        for rec in meta.get("images", []):
            if not isinstance(rec, dict):
                continue
            kind = kind_for(str(rec.get("kind", "")))
            member = self._prefix + str(rec.get("file", ""))
            if kind is None or member not in self._names or not rec.get("name"):
                self.skipped.append(str(rec.get("file", "")))
                continue
            items.append((kind, str(rec["name"]), member))
        return items


_store: Optional[ImageStore] = None


def get_image_store() -> ImageStore:
    global _store
    if _store is None:
        _store = ImageStore()
    return _store


def format_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} bytes"
