"""
The music library (Game Tools > Music). Pure logic, no UI and no sound.

The library lists music files that stay where they are (in the folders the person added, or picked one by
one), and links to music elsewhere (a YouTube video, a Spotify playlist), which open in the browser. Each
track has a title, tags and its own volume. Tags double as playlists: "play everything tagged Combat".

Tracks found in sub-folders start with those folders' names as tags (Music/Combat/Undead/x.mp3 -> "Combat",
"Undead"). A track can have any number of tags, and the list can be narrowed to tracks having several at once.

Everything is saved in ``music.json`` in the user data folder, with the player's settings (volume, effects,
fades, loop and shuffle).
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple

FILE_NAME = "music.json"
FORMAT_VERSION = 1

# What miniaudio can decode (OGG means Ogg Vorbis; Opus and AAC/M4A aren't supported).
AUDIO_EXTENSIONS = (".mp3", ".wav", ".flac", ".ogg", ".oga")

LOOP_MODES = ("off", "all", "one")

DEFAULT_SETTINGS = {
    "volume": 0.8,          # 0..1
    "pitch": 0,             # semitones, -12..12 (tape style: faster and higher, or slower and lower)
    "distortion": 0,        # 0..100
    "muffle": 0,            # 0..100 (a low-pass filter: music from the next room)
    "fade_in": 2.0,         # seconds
    "crossfade": 3.0,
    "fade_out": 3.0,
    "loop": "all",
    "shuffle": False,
}


def link_kind(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "YouTube"
    if "spotify.com" in u or u.startswith("spotify:"):
        return "Spotify"
    return "Link"


def title_from_path(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"[_]+", " ", stem).strip()
    return stem or os.path.basename(path)


def clean_tags(tags: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for t in tags:
        t = re.sub(r"\s+", " ", str(t)).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def parse_tags(text: str) -> List[str]:
    return clean_tags(text.split(","))


@dataclass
class Track:
    id: str
    title: str
    path: str = ""                 # a music file, or
    url: str = ""                  # a link that opens in the browser
    tags: List[str] = field(default_factory=list)
    volume: float = 1.0            # 0..1.5, on top of the master volume
    duration: float = 0.0          # seconds, 0 = not known yet
    stamp: Tuple[int, int] = (0, 0)   # (size, mtime) the duration was read at

    @property
    def name(self) -> str:         # the key the list widgets select by
        return self.id

    @property
    def is_link(self) -> bool:
        return bool(self.url)

    @property
    def kind(self) -> str:
        return link_kind(self.url) if self.url else "File"

    def has_tag(self, tag: str) -> bool:
        t = tag.lower()
        return any(x.lower() == t for x in self.tags)

    def matches(self, query: str) -> bool:
        words = query.lower().split()
        hay = " ".join([self.title, " ".join(self.tags), os.path.basename(self.path), self.url]).lower()
        return all(w in hay for w in words)

    def to_dict(self) -> dict:
        d = {"id": self.id, "title": self.title}
        if self.path:
            d["path"] = self.path
        if self.url:
            d["url"] = self.url
        if self.tags:
            d["tags"] = list(self.tags)
        if self.volume != 1.0:
            d["volume"] = round(self.volume, 3)
        if self.duration:
            d["duration"] = round(self.duration, 3)
            d["stamp"] = list(self.stamp)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Track":
        stamp = d.get("stamp") or (0, 0)
        try:
            stamp = (int(stamp[0]), int(stamp[1]))
        except (TypeError, ValueError, IndexError):
            stamp = (0, 0)
        return cls(id=str(d.get("id") or uuid.uuid4().hex), title=str(d.get("title", "")),
                   path=str(d.get("path", "")), url=str(d.get("url", "")),
                   tags=clean_tags(d.get("tags") or []),
                   volume=max(0.0, min(1.5, float(d.get("volume", 1.0) or 0))),
                   duration=max(0.0, float(d.get("duration", 0) or 0)), stamp=stamp)


def _stamp(path: str) -> Tuple[int, int]:
    try:
        st = os.stat(path)
        return int(st.st_size), int(st.st_mtime)
    except OSError:
        return 0, 0


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


@dataclass
class ScanReport:
    added: int = 0
    missing: int = 0


class MusicLibrary:
    """The tracks, folders and player settings in ``music.json``."""

    def __init__(self, path: str):
        self.path = path
        self.tracks: List[Track] = []
        self.folders: List[str] = []
        self.settings: Dict[str, object] = dict(DEFAULT_SETTINGS)
        self._lock = threading.RLock()
        self.load()

    # ---- file

    def load(self):
        with self._lock:
            self.tracks, self.folders, self.settings = [], [], dict(DEFAULT_SETTINGS)
            try:
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                return
            if not isinstance(data, dict):
                return
            self.tracks = [Track.from_dict(t) for t in data.get("tracks") or [] if isinstance(t, dict)]
            self.folders = [str(f) for f in data.get("folders") or [] if f]
            settings = data.get("settings") or {}
            if isinstance(settings, dict):
                for key, default in DEFAULT_SETTINGS.items():
                    value = settings.get(key)
                    if isinstance(default, bool):
                        ok = isinstance(value, bool)
                    elif isinstance(default, (int, float)):
                        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
                    else:
                        ok = isinstance(value, type(default))
                    if ok:
                        self.settings[key] = value
            if self.settings["loop"] not in LOOP_MODES:
                self.settings["loop"] = "all"

    def save(self):
        with self._lock:
            data = {"version": FORMAT_VERSION, "folders": list(self.folders),
                    "settings": dict(self.settings), "tracks": [t.to_dict() for t in self.tracks]}
        from atomic_io import atomic_write_json
        atomic_write_json(self.path, data)

    # ---- tracks

    def get(self, track_id: str) -> Optional[Track]:
        return next((t for t in self.tracks if t.id == track_id), None)

    def all_tags(self) -> List[str]:
        tags: Dict[str, str] = {}
        for t in self.tracks:
            for tag in t.tags:
                tags.setdefault(tag.lower(), tag)
        return sorted(tags.values(), key=str.lower)

    def find(self, query: str = "", tag: str = "", tags: Iterable[str] = ()) -> List[Track]:
        """Tracks matching the search that have every one of the tags ("Combat" + "Undead")."""
        wanted = [x for x in ([tag] if tag else []) + list(tags) if x]
        found = [t for t in self.tracks if all(t.has_tag(x) for x in wanted) and (not query or t.matches(query))]
        return sorted(found, key=lambda t: t.title.lower())

    def add_file(self, path: str, tags: Iterable[str] = ()) -> Optional[Track]:
        """Add one music file (None if it's already in the library or isn't a music file)."""
        if not path.lower().endswith(AUDIO_EXTENSIONS):
            return None
        key = _norm(path)
        with self._lock:
            if any(t.path and _norm(t.path) == key for t in self.tracks):
                return None
            track = Track(uuid.uuid4().hex, title_from_path(path), path=os.path.abspath(path),
                          tags=clean_tags(tags))
            self.tracks.append(track)
        return track

    def add_link(self, url: str, title: str = "", tags: Iterable[str] = ()) -> Track:
        url = url.strip()
        if not re.match(r"^(https?://|spotify:)", url, re.I):
            url = "https://" + url
        track = Track(uuid.uuid4().hex, title.strip() or f"{link_kind(url)} link", url=url, tags=clean_tags(tags))
        with self._lock:
            self.tracks.append(track)
        return track

    def remove(self, track_ids: Iterable[str]):
        ids = set(track_ids)
        with self._lock:
            self.tracks = [t for t in self.tracks if t.id not in ids]

    def rename_tag(self, old: str, new: str):
        new = re.sub(r"\s+", " ", new).strip()
        with self._lock:
            for t in self.tracks:
                if t.has_tag(old):
                    t.tags = clean_tags([new if x.lower() == old.lower() else x for x in t.tags] if new
                                        else [x for x in t.tags if x.lower() != old.lower()])

    def missing(self) -> List[Track]:
        return [t for t in self.tracks if t.path and not os.path.isfile(t.path)]

    # ---- folders

    def add_folder(self, folder: str) -> bool:
        folder = os.path.abspath(folder)
        with self._lock:
            if any(_norm(f) == _norm(folder) for f in self.folders):
                return False
            self.folders.append(folder)
        return True

    def remove_folder(self, folder: str, remove_tracks: bool = True):
        key = _norm(folder)
        with self._lock:
            self.folders = [f for f in self.folders if _norm(f) != key]
            if remove_tracks:
                prefix = key.rstrip(os.sep) + os.sep
                self.tracks = [t for t in self.tracks if not (t.path and _norm(t.path).startswith(prefix))]

    def scan(self, should_stop: Callable[[], bool] = lambda: False) -> ScanReport:
        """Add the music files in the library folders that aren't listed yet."""
        report = ScanReport()
        for folder in list(self.folders):
            if not os.path.isdir(folder):
                continue
            for root, dirs, files in os.walk(folder):
                if should_stop():
                    return report
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                rel = os.path.relpath(root, folder)
                # every sub-folder on the way is a tag: Music/Combat/Undead/x.mp3 -> Combat, Undead
                tags = [] if rel in (".", "") else [p for p in rel.split(os.sep) if p and p != "."]
                for name in sorted(files):
                    if self.add_file(os.path.join(root, name), tags):
                        report.added += 1
        report.missing = len(self.missing())
        return report

    def tracks_needing_duration(self) -> List[Track]:
        return [t for t in self.tracks if t.path and os.path.isfile(t.path) and
                (not t.duration or t.stamp != _stamp(t.path))]

    def read_durations(self, info: Callable[[str], float], should_stop: Callable[[], bool] = lambda: False) -> int:
        """Fill in the length of tracks that don't have one (or whose file changed). Returns how many."""
        count = 0
        for t in self.tracks_needing_duration():
            if should_stop():
                break
            try:
                t.duration = max(0.0, float(info(t.path)))
            except Exception:
                t.duration = 0.0
            t.stamp = _stamp(t.path)
            count += 1
        return count


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds + 0.5))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


_library: Optional[MusicLibrary] = None


def get_music_library() -> MusicLibrary:
    global _library
    if _library is None:
        from paths import user_data_path
        _library = MusicLibrary(user_data_path(FILE_NAME))
    return _library
