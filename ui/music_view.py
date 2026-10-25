"""
Music page (Game Tools): the music library and the player.

Left: the tracks, searchable and filtered by tag (a tag is also a playlist: "Play All" plays what the list
shows). Right: what's playing with the transport buttons, the selected track (title, tags, its own volume),
and the sound: volume, pitch, distortion, muffle, and the fade times.

The player itself (music_player.py) lives as long as the app, so music keeps playing on other pages and the
page just shows it again when it opens.
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

import music_player
from music_library import (AUDIO_EXTENSIONS, MusicLibrary, Track, format_time, get_music_library, link_kind,
                           parse_tags)
from theme import get_theme_manager
from typography import ui_font
from ui.virtual_list import VirtualListPanel
from ui.window_utils import add_cancel_save, center_on_parent

ALL_TRACKS = "All tracks"
FADE_CHOICES = ["0 s", "0.5 s", "1 s", "2 s", "3 s", "5 s", "8 s", "12 s"]
LOOP_LABELS = {"off": "Loop: off", "all": "Loop: all", "one": "Loop: this track"}
POLL_MS = 250


def _seconds(choice: str) -> float:
    try:
        return float(choice.split()[0])
    except (ValueError, IndexError):
        return 0.0


def _choice(seconds: float) -> str:
    best = min(FADE_CHOICES, key=lambda c: abs(_seconds(c) - seconds))
    return best


def open_externally(path: str):
    from ui.pdf_library_view import open_externally as _open
    _open(path)


class TrackList(VirtualListPanel):
    TITLE = "Tracks"
    NOUN = "track"
    ROW_HEIGHT = 50

    def __init__(self, parent, on_select, on_activate: Callable[[Track], None], playing: Callable[[], str]):
        self.on_activate = on_activate
        self._playing = playing
        super().__init__(parent, on_select=on_select)

    KEY = staticmethod(lambda name: name)

    def row_text(self, item) -> str:
        mark = "♪ " if item.id == self._playing() else ("🔗 " if item.is_link else "")
        bits = []
        if item.is_link:
            bits.append(item.kind)
        if item.tags:
            bits.append(", ".join(item.tags))
        if item.duration:
            bits.append(format_time(item.duration))
        if item.path and not os.path.isfile(item.path):
            bits.insert(0, "file missing")
        sub = "  ·  ".join(bits)
        title = item.title if len(item.title) <= 44 else item.title[:43] + "…"
        sub = sub if len(sub) <= 52 else sub[:51] + "…"
        return f"{mark}{title}\n{sub}"

    def _ensure_pool(self, count: int):
        before = len(self._pool)
        super()._ensure_pool(count)
        for row in self._pool[before:]:
            label = getattr(row, "_text_label", None)
            if label is not None:
                label.configure(justify="left")
            for widget in [row] + list(row.winfo_children()):
                widget.bind("<Double-Button-1>", lambda _e, r=row: self._activate(r._vl_index), add="+")

    def _activate(self, index: int):
        if 0 <= index < len(self._items):
            self.on_activate(self._items[index])

    def redraw(self):
        for row in self._pool:
            row._vl_state = None
        self._request_render()


class LinkDialog(ctk.CTkToplevel):
    """Add a link (a YouTube video, a Spotify playlist...): it opens in the browser."""

    def __init__(self, parent, tags: str = ""):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.title("Add Link")
        self.geometry("520x330")
        self.resizable(True, False)
        self.transient(parent)
        self.result = None
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)
        ctk.CTkLabel(frame, text="Spotify and YouTube can't play inside Spellbook without an account and keys for "
                                 "their services, so a link opens in your browser (or the Spotify app). Put it "
                                 "beside your own files with the same tags.",
                     font=ui_font("small"), text_color=self.theme.get_text_secondary(), justify="left",
                     wraplength=470).pack(anchor="w", pady=(0, 8))
        self.fields = {}
        for key, label, hint, value in (("url", "Link *", "https://www.youtube.com/watch?v=...", ""),
                                        ("title", "Title", "e.g., Tavern ambience", ""),
                                        ("tags", "Tags", "comma separated: Tavern, Calm", tags)):
            ctk.CTkLabel(frame, text=label, font=ui_font("subheading", 13, bold=True)).pack(anchor="w")
            entry = ctk.CTkEntry(frame, placeholder_text=hint)
            if value:
                entry.insert(0, value)
            entry.pack(fill="x", pady=(0, 6))
            self.fields[key] = entry
        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.pack(fill="x", side="bottom")
        add_cancel_save(buttons, self.theme, self.destroy, self._ok, confirm_text="Add", accent=True)
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        center_on_parent(self, parent)
        self.after(50, lambda: self.fields["url"].focus_set())

    def _ok(self):
        url = self.fields["url"].get().strip()
        if not url:
            self.fields["url"].focus_set()
            return
        self.result = (url, self.fields["title"].get().strip(), parse_tags(self.fields["tags"].get()))
        self.destroy()


class FoldersDialog(ctk.CTkToplevel):
    """The folders the library reads music from."""

    def __init__(self, parent, library: MusicLibrary, on_change: Callable[[], None]):
        super().__init__(parent)
        self.theme = get_theme_manager()
        self.library = library
        self.on_change = on_change
        self.title("Music Folders")
        self.geometry("560x380")
        self.transient(parent)
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=16)
        ctk.CTkLabel(frame, text="Music stays where it is: Spellbook only lists it. Files in a sub-folder get "
                                 "the sub-folder's name as a tag.", font=ui_font("small"),
                     text_color=self.theme.get_text_secondary(), wraplength=510, justify="left"
                     ).pack(anchor="w", pady=(0, 8))
        self.listbox = tk.Listbox(frame, height=8, activestyle="none", exportselection=False,
                                  font=ui_font("body"))
        self.listbox.pack(fill="both", expand=True)
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(row, text="Add Folder…", width=110, command=self._add).pack(side="left")
        ctk.CTkButton(row, text="Remove", width=90, command=self._remove,
                      fg_color=self.theme.get_current_color('button_normal'),
                      hover_color=self.theme.get_current_color('button_hover')).pack(side="left", padx=8)
        ctk.CTkButton(row, text="Close", width=90, command=self.destroy).pack(side="right")
        self._fill()
        center_on_parent(self, parent)

    def _fill(self):
        self.listbox.delete(0, "end")
        for f in self.library.folders:
            self.listbox.insert("end", f)

    def _add(self):
        folder = filedialog.askdirectory(parent=self, title="Add a music folder")
        if folder and self.library.add_folder(folder):
            self._fill()
            self.on_change()

    def _remove(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        folder = self.library.folders[sel[0]]
        if not messagebox.askyesno("Remove folder", f"Stop listing the music in\n{folder}?\n\n"
                                   "The files themselves aren't touched.", parent=self):
            return
        self.library.remove_folder(folder)
        self._fill()
        self.on_change()


class MusicView(ctk.CTkFrame):
    """The Music page."""

    def __init__(self, parent, state: Optional[dict] = None, on_back=None, library: Optional[MusicLibrary] = None,
                 player: Optional[music_player.MusicPlayer] = None):
        self.theme = get_theme_manager()
        super().__init__(parent, fg_color="transparent")
        self.state = state if state is not None else {}
        self.on_back = on_back
        self.library = library or get_music_library()
        self._player = player
        self._selected: Optional[Track] = None
        self._poll_job = None
        self._save_job = None
        self._pitch_job = None
        self._seeking = False
        self._last_track_id = ""
        self._scan_thread: Optional[threading.Thread] = None
        self._stop = False
        self._create_widgets()
        self._load_settings()
        self.refresh_list()
        if not music_player.available():
            self.status.configure(text="Sound isn't available: the miniaudio package is missing "
                                       "(pip install miniaudio).")
        self.rescan()
        self._poll()

    @property
    def player(self) -> music_player.MusicPlayer:
        if self._player is None:
            self._player = music_player.get_player()
            self._player.apply_settings(self.library.settings)
        return self._player

    def _live_player(self) -> Optional[music_player.MusicPlayer]:
        return self._player or music_player.peek_player()

    def destroy(self):
        self._stop = True
        for job in (self._poll_job, self._pitch_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        if self._save_job is not None:
            try:
                self.after_cancel(self._save_job)
            except Exception:
                pass
            self.library.save()
        super().destroy()

    # ------------------------------------------------------------------ layout

    def _button(self, parent, text, command, width=90, kind="normal"):
        colors = {"normal": ("button_normal", "button_hover"), "accent": ("accent_primary", "accent_hover")}[kind]
        return ctk.CTkButton(parent, text=text, width=width, height=32, command=command,
                             fg_color=self.theme.get_current_color(colors[0]),
                             hover_color=self.theme.get_current_color(colors[1]),
                             text_color=self.theme.get_current_color(
                                 'text_primary' if kind == "normal" else 'text_on_accent'),
                             text_color_disabled=self.theme.get_text_secondary())

    def _card(self, parent, title: str):
        card = ctk.CTkFrame(parent, fg_color=self.theme.get_current_color('bg_secondary'), corner_radius=10)
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(card, text=title, font=ui_font("heading", 16, bold=True), anchor="w"
                     ).pack(fill="x", padx=14, pady=(10, 2))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=(0, 12))
        return inner

    def _slider_row(self, parent, label: str, from_: float, to: float, steps: int, command, width=110):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=width, anchor="w", font=ui_font("body")).pack(side="left")
        value = ctk.CTkLabel(row, text="", width=70, anchor="e", font=ui_font("small"))
        value.pack(side="right")
        slider = ctk.CTkSlider(row, from_=from_, to=to, number_of_steps=steps, command=command)
        slider.pack(side="left", fill="x", expand=True, padx=(0, 8))
        return slider, value

    def _create_widgets(self):
        th = self.theme
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 6))
        if self.on_back:
            self._button(header, "← Game Tools", self.on_back, width=120).pack(side="left", padx=(0, 15))
        ctk.CTkLabel(header, text="Music", font=ui_font("title", 28, bold=True)).pack(side="left")
        self._button(header, "Rescan", self.rescan, width=80).pack(side="right")
        self._button(header, "Folders…", self._on_folders, width=90).pack(side="right", padx=(0, 8))
        self._button(header, "Add Link…", self._on_add_link, width=100).pack(side="right", padx=(0, 8))
        self._button(header, "Add Files…", self._on_add_files, width=100).pack(side="right", padx=(0, 8))
        self.status = ctk.CTkLabel(self, text="", font=ui_font("small"), anchor="w", text_color=th.get_text_secondary())
        self.status.pack(fill="x", padx=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(6, 20))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ---- left: the tracks
        left = ctk.CTkFrame(body, fg_color="transparent", width=380)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_propagate(False)
        left.pack_propagate(False)
        self.search_entry = ctk.CTkEntry(left, height=34, placeholder_text="Search titles and tags...")
        if self.state.get("query"):
            self.search_entry.insert(0, self.state["query"])
        self.search_entry.pack(fill="x", pady=(0, 6))
        self.search_entry.bind("<KeyRelease>", lambda _e: self.refresh_list(), add="+")
        tag_row = ctk.CTkFrame(left, fg_color="transparent")
        tag_row.pack(fill="x", pady=(0, 6))
        self.tag_var = ctk.StringVar(value=self.state.get("tag") or ALL_TRACKS)
        self.tag_menu = ctk.CTkOptionMenu(tag_row, variable=self.tag_var, values=[ALL_TRACKS], height=32,
                                          command=lambda _v: self.refresh_list())
        self.tag_menu.pack(side="left", fill="x", expand=True)
        self.play_all_btn = self._button(tag_row, "▶ Play All", self._play_all, width=100, kind="accent")
        self.play_all_btn.pack(side="left", padx=(6, 0))
        self.tracks = TrackList(left, on_select=self._on_select, on_activate=self._play_track,
                                playing=lambda: self._last_track_id)
        self.tracks.pack(fill="both", expand=True)
        ctk.CTkLabel(left, text="Double-click a track to play it. A tag is a playlist: pick it, then Play All.",
                     font=ui_font("small"), text_color=th.get_text_secondary(), wraplength=360, justify="left"
                     ).pack(anchor="w", pady=(6, 0))

        # ---- right: player, track, sound
        right = ctk.CTkScrollableFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        self.right = right

        now = self._card(right, "Now Playing")
        self.now_title = ctk.CTkLabel(now, text="Nothing playing", font=ui_font("heading", 18, bold=True),
                                      anchor="w", justify="left", wraplength=520)
        self.now_title.pack(fill="x")
        self.next_label = ctk.CTkLabel(now, text="", font=ui_font("small"), anchor="w",
                                       text_color=th.get_text_secondary())
        self.next_label.pack(fill="x")
        seek = ctk.CTkFrame(now, fg_color="transparent")
        seek.pack(fill="x", pady=(6, 2))
        self.pos_label = ctk.CTkLabel(seek, text="0:00", width=50, font=ui_font("small"))
        self.pos_label.pack(side="left")
        self.len_label = ctk.CTkLabel(seek, text="0:00", width=50, font=ui_font("small"))
        self.len_label.pack(side="right")
        self.seek_slider = ctk.CTkSlider(seek, from_=0, to=1, command=self._on_seek_drag)
        self.seek_slider.set(0)
        self.seek_slider.pack(side="left", fill="x", expand=True, padx=6)
        self.seek_slider.bind("<ButtonRelease-1>", self._on_seek_release, add="+")
        transport = ctk.CTkFrame(now, fg_color="transparent")
        transport.pack(fill="x", pady=(6, 0))
        self._button(transport, "◀◀", lambda: self._live_call("previous"), width=44).pack(side="left")
        self.play_btn = self._button(transport, "▶", self._on_play_pause, width=60, kind="accent")
        self.play_btn.pack(side="left", padx=6)
        self._button(transport, "▶▶", lambda: self._live_call("next"), width=44).pack(side="left")
        self._button(transport, "■ Fade Out", lambda: self._live_call("stop"), width=110).pack(side="left", padx=(12, 0))
        self.shuffle_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(transport, text="Shuffle", variable=self.shuffle_var, width=80,
                        command=self._on_shuffle).pack(side="right")
        self.loop_var = ctk.StringVar(value=LOOP_LABELS["all"])
        ctk.CTkOptionMenu(transport, variable=self.loop_var, values=list(LOOP_LABELS.values()), width=150,
                          height=32, command=self._on_loop).pack(side="right", padx=(0, 10))

        track = self._card(right, "Track")
        self.track_hint = ctk.CTkLabel(track, text="Pick a track on the left.", font=ui_font("small"), anchor="w",
                                       text_color=th.get_text_secondary())
        self.track_hint.pack(fill="x")
        self.track_box = ctk.CTkFrame(track, fg_color="transparent")
        grid = ctk.CTkFrame(self.track_box, fg_color="transparent")
        grid.pack(fill="x")
        grid.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(grid, text="Title", font=ui_font("body", bold=True)).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.title_entry = ctk.CTkEntry(grid)
        self.title_entry.grid(row=0, column=1, sticky="ew", pady=2)
        ctk.CTkLabel(grid, text="Tags", font=ui_font("body", bold=True)).grid(row=1, column=0, sticky="w", padx=(0, 10))
        self.tags_entry = ctk.CTkEntry(grid, placeholder_text="comma separated: Combat, Boss")
        self.tags_entry.grid(row=1, column=1, sticky="ew", pady=2)
        for entry in (self.title_entry, self.tags_entry):
            entry.bind("<Return>", lambda _e: self._save_track(), add="+")
            entry.bind("<FocusOut>", lambda _e: self._save_track(), add="+")
        self.where_label = ctk.CTkLabel(self.track_box, text="", font=ui_font("small"), anchor="w", justify="left",
                                        text_color=th.get_text_secondary(), wraplength=520)
        self.where_label.pack(fill="x", pady=(4, 2))
        self.track_volume, self.track_volume_label = self._slider_row(self.track_box, "Track volume", 0, 150, 30,
                                                                      self._on_track_volume)
        buttons = ctk.CTkFrame(self.track_box, fg_color="transparent")
        buttons.pack(fill="x", pady=(6, 0))
        self.track_play_btn = self._button(buttons, "▶ Play", lambda: self._play_track(self._selected),
                                           width=90, kind="accent")
        self.track_play_btn.pack(side="left")
        self.show_btn = self._button(buttons, "Show File", self._show_file, width=100)
        self.show_btn.pack(side="left", padx=6)
        self._button(buttons, "Remove", self._remove_track, width=90).pack(side="right")

        sound = self._card(right, "Sound")
        self.volume_slider, self.volume_label = self._slider_row(sound, "Volume", 0, 100, 100, self._on_volume)
        self.pitch_slider, self.pitch_label = self._slider_row(sound, "Pitch", -12, 12, 48, self._on_pitch)
        self.distortion_slider, self.distortion_label = self._slider_row(sound, "Distortion", 0, 100, 100,
                                                                         self._on_distortion)
        self.muffle_slider, self.muffle_label = self._slider_row(sound, "Muffle", 0, 100, 100, self._on_muffle)
        ctk.CTkLabel(sound, text="Pitch plays the music faster and higher, or slower and lower, like a tape. "
                                 "Muffle sounds like music through a wall.", font=ui_font("small"),
                     text_color=th.get_text_secondary(), anchor="w", justify="left", wraplength=520
                     ).pack(fill="x", pady=(2, 6))
        fades = ctk.CTkFrame(sound, fg_color="transparent")
        fades.pack(fill="x")
        self.fade_vars = {}
        for key, label in (("fade_in", "Fade in"), ("crossfade", "Crossfade"), ("fade_out", "Fade out")):
            ctk.CTkLabel(fades, text=label, font=ui_font("body")).pack(side="left", padx=(0, 4))
            var = ctk.StringVar(value="2 s")
            ctk.CTkOptionMenu(fades, variable=var, values=FADE_CHOICES, width=78, height=30,
                              command=lambda v, k=key: self._on_fade(k, v)).pack(side="left", padx=(0, 12))
            self.fade_vars[key] = var
        self._button(sound, "Reset Effects", self._reset_effects, width=120).pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------ settings

    def _load_settings(self):
        s = self.library.settings
        self.volume_slider.set(float(s["volume"]) * 100)
        self.pitch_slider.set(float(s["pitch"]))
        self.distortion_slider.set(float(s["distortion"]))
        self.muffle_slider.set(float(s["muffle"]))
        for key, var in self.fade_vars.items():
            var.set(_choice(float(s[key])))
        self.loop_var.set(LOOP_LABELS.get(str(s["loop"]), LOOP_LABELS["all"]))
        self.shuffle_var.set(bool(s["shuffle"]))
        self._update_sound_labels()
        live = self._live_player()
        if live is not None:
            live.apply_settings(s)

    def _update_sound_labels(self):
        s = self.library.settings
        self.volume_label.configure(text=f"{round(float(s['volume']) * 100)}%")
        p = float(s["pitch"])
        self.pitch_label.configure(text="normal" if p == 0 else f"{p:+g} st")
        self.distortion_label.configure(text="off" if not s["distortion"] else f"{round(float(s['distortion']))}")
        self.muffle_label.configure(text="off" if not s["muffle"] else f"{round(float(s['muffle']))}")

    def _changed(self, key: str, value):
        self.library.settings[key] = value
        self._update_sound_labels()
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_job = self.after(800, self._save_now)

    def _save_now(self):
        self._save_job = None
        self.library.save()

    def _on_volume(self, value):
        self._changed("volume", round(float(value) / 100.0, 3))
        live = self._live_player()
        if live is not None:
            live.set_volume(self.library.settings["volume"])

    def _on_pitch(self, value):
        self._changed("pitch", round(float(value) * 2) / 2)
        if self._pitch_job is not None:
            self.after_cancel(self._pitch_job)
        # reopening the track at a new speed takes a moment: wait until the slider rests
        self._pitch_job = self.after(150, self._apply_pitch)

    def _apply_pitch(self):
        self._pitch_job = None
        live = self._live_player()
        if live is not None:
            live.set_pitch(float(self.library.settings["pitch"]))

    def _on_distortion(self, value):
        self._changed("distortion", round(float(value)))
        live = self._live_player()
        if live is not None:
            live.set_effects(distortion=self.library.settings["distortion"])

    def _on_muffle(self, value):
        self._changed("muffle", round(float(value)))
        live = self._live_player()
        if live is not None:
            live.set_effects(muffle=self.library.settings["muffle"])

    def _on_fade(self, key: str, choice: str):
        self._changed(key, _seconds(choice))
        live = self._live_player()
        if live is not None:
            live.set_fades(**{key: _seconds(choice)})

    def _on_loop(self, label: str):
        mode = next((k for k, v in LOOP_LABELS.items() if v == label), "all")
        self._changed("loop", mode)
        live = self._live_player()
        if live is not None:
            live.set_loop(mode)

    def _on_shuffle(self):
        self._changed("shuffle", bool(self.shuffle_var.get()))
        live = self._live_player()
        if live is not None:
            live.set_shuffle(self.library.settings["shuffle"])

    def _reset_effects(self):
        for key, slider, value in (("pitch", self.pitch_slider, 0), ("distortion", self.distortion_slider, 0),
                                   ("muffle", self.muffle_slider, 0)):
            slider.set(value)
            self.library.settings[key] = value
        self._changed("pitch", 0)
        live = self._live_player()
        if live is not None:
            live.set_effects(distortion=0, muffle=0)
            live.set_pitch(0)

    # ------------------------------------------------------------------ the list

    def visible_tracks(self) -> List[Track]:
        tag = self.tag_var.get()
        return self.library.find(self.search_entry.get().strip(), "" if tag == ALL_TRACKS else tag)

    def refresh_list(self):
        tags = self.library.all_tags()
        values = [ALL_TRACKS] + tags
        self.tag_menu.configure(values=values)
        if self.tag_var.get() not in values:
            self.tag_var.set(ALL_TRACKS)
        self.state["query"] = self.search_entry.get().strip()
        self.state["tag"] = "" if self.tag_var.get() == ALL_TRACKS else self.tag_var.get()
        items = self.visible_tracks()
        self.tracks.set_items(items, reset_scroll=False, keep=self._selected.id if self._selected else None)
        if self._selected is not None and self.library.get(self._selected.id) is None:
            self._on_select(None)
        playable = [t for t in items if not t.is_link]
        self.play_all_btn.configure(state="normal" if playable else "disabled")
        if not self.library.tracks:
            self.status.configure(text="No music yet. Add a folder of music (Folders…) or some files: MP3, FLAC, "
                                       "WAV or OGG. Links to YouTube or Spotify open in the browser.")

    def _on_select(self, track: Optional[Track]):
        self._save_track()
        self._selected = track
        if track is None:
            self.track_box.pack_forget()
            self.track_hint.pack(fill="x")
            return
        self.track_hint.pack_forget()
        self.track_box.pack(fill="x")
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, track.title)
        self.tags_entry.delete(0, "end")
        if track.tags:
            self.tags_entry.insert(0, ", ".join(track.tags))
        if track.is_link:
            where = f"{link_kind(track.url)} link: {track.url}"
        elif not os.path.isfile(track.path):
            where = f"The file is missing: {track.path}"
        else:
            where = track.path + (f"  ·  {format_time(track.duration)}" if track.duration else "")
        self.where_label.configure(text=where)
        self.track_volume.set(track.volume * 100)
        self.track_volume_label.configure(text=f"{round(track.volume * 100)}%")
        self.track_play_btn.configure(text="🔗 Open" if track.is_link else "▶ Play")
        self.show_btn.configure(state="disabled" if track.is_link else "normal")

    def _save_track(self):
        t = self._selected
        if t is None or self.library.get(t.id) is None:
            return
        title = self.title_entry.get().strip() or t.title
        tags = parse_tags(self.tags_entry.get())
        if title == t.title and tags == t.tags:
            return
        t.title, t.tags = title, tags
        self.library.save()
        self.refresh_list()

    def _on_track_volume(self, value):
        t = self._selected
        if t is None:
            return
        t.volume = round(float(value) / 100.0, 2)
        self.track_volume_label.configure(text=f"{round(t.volume * 100)}%")
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_job = self.after(800, self._save_now)

    def _show_file(self):
        t = self._selected
        if t is not None and t.path:
            folder = os.path.dirname(t.path)
            if os.path.isdir(folder):
                open_externally(folder)

    def _remove_track(self):
        t = self._selected
        if t is None:
            return
        if not messagebox.askyesno("Remove track", f"Take \"{t.title}\" out of the music library?\n\n"
                                   "The file itself isn't deleted.", parent=self.winfo_toplevel()):
            return
        self.library.remove([t.id])
        self.library.save()
        self._selected = None
        self._on_select(None)
        self.refresh_list()

    # ------------------------------------------------------------------ adding

    def _on_add_files(self):
        patterns = " ".join("*" + e for e in AUDIO_EXTENSIONS)
        paths = filedialog.askopenfilenames(parent=self.winfo_toplevel(), title="Add music",
                                            filetypes=[("Music", patterns), ("All files", "*.*")])
        added = [t for t in (self.library.add_file(p, self._current_tag()) for p in paths or ()) if t]
        if added:
            self.library.save()
            self.refresh_list()
            self.status.configure(text=f"Added {len(added)} track{'s' if len(added) != 1 else ''}.")
            self._read_durations()

    def _current_tag(self) -> List[str]:
        tag = self.tag_var.get()
        return [] if tag == ALL_TRACKS else [tag]

    def _on_add_link(self):
        dialog = LinkDialog(self.winfo_toplevel(), ", ".join(self._current_tag()))
        self.wait_window(dialog)
        if dialog.result:
            url, title, tags = dialog.result
            track = self.library.add_link(url, title, tags)
            self.library.save()
            self.refresh_list()
            self.tracks.select_by_name(track.id)

    def _on_folders(self):
        FoldersDialog(self.winfo_toplevel(), self.library, on_change=self.rescan)

    def rescan(self):
        if self._scan_thread is not None and self._scan_thread.is_alive():
            return
        if not self.library.folders and not self.library.tracks_needing_duration():
            return
        self.status.configure(text="Looking for music…")
        result = {}

        def work():
            try:
                result["report"] = self.library.scan(should_stop=lambda: self._stop)
                if music_player.available():
                    result["durations"] = self.library.read_durations(music_player.file_duration,
                                                                      should_stop=lambda: self._stop)
            except Exception as e:
                result["error"] = str(e)

        self._scan_thread = threading.Thread(target=work, daemon=True, name="music-scan")
        self._scan_thread.start()
        self.after(200, lambda: self._after_scan(result))

    def _read_durations(self):
        if self._scan_thread is not None and self._scan_thread.is_alive():
            return
        self.rescan()

    def _after_scan(self, result: dict):
        if self._stop:
            return
        if self._scan_thread is not None and self._scan_thread.is_alive():
            self.after(200, lambda: self._after_scan(result))
            return
        try:
            if "error" in result:
                self.status.configure(text=f"The music folders couldn't be read: {result['error']}")
                return
            report = result.get("report")
            self.library.save()
            n = len([t for t in self.library.tracks if not t.is_link])
            text = f"{n} track{'s' if n != 1 else ''}."
            if report and report.added:
                text += f" {report.added} new."
            if report and report.missing:
                text += f" {report.missing} missing (moved or deleted)."
            self.status.configure(text=text)
            self.refresh_list()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ playing

    def _play_track(self, track: Optional[Track]):
        if track is None:
            return
        if track.is_link:
            webbrowser.open(track.url)
            return
        if not music_player.available():
            messagebox.showinfo("Music", "Sound needs the miniaudio package (pip install miniaudio).",
                                parent=self.winfo_toplevel())
            return
        if not os.path.isfile(track.path):
            self.status.configure(text=f"The file is missing: {track.path}")
            return
        queue = [t for t in self.visible_tracks() if not t.is_link and os.path.isfile(t.path)]
        if track not in queue:
            queue = [track]
        self.player.play(queue, queue.index(track))

    def _play_all(self):
        queue = [t for t in self.visible_tracks() if not t.is_link and os.path.isfile(t.path)]
        if not queue or not music_player.available():
            return
        start = 0
        if self.library.settings.get("shuffle"):
            import random
            start = random.randrange(len(queue))
        self.player.play(queue, start)

    def _on_play_pause(self):
        live = self._live_player()
        if live is not None and live.status()["track"] is not None:
            live.toggle_pause()
        elif self._selected is not None and not self._selected.is_link:
            self._play_track(self._selected)
        else:
            self._play_all()

    def _live_call(self, name: str):
        live = self._live_player()
        if live is not None:
            getattr(live, name)()

    def _on_seek_drag(self, _value):
        self._seeking = True

    def _on_seek_release(self, _event=None):
        live = self._live_player()
        if live is not None and self._seeking:
            st = live.status()
            if st["duration"]:
                live.seek(self.seek_slider.get() * st["duration"])
        self._seeking = False

    def _poll(self):
        self._poll_job = None
        if self._stop:
            return
        try:
            self._show_status()
        except tk.TclError:
            return
        self._poll_job = self.after(POLL_MS, self._poll)

    def _show_status(self):
        live = self._live_player()
        st = live.status() if live is not None else None
        track = st["track"] if st else None
        track_id = track.id if track is not None and hasattr(track, "id") else ""
        if track_id != self._last_track_id:
            self._last_track_id = track_id
            self.tracks.redraw()
        if not st or track is None:
            self.now_title.configure(text="Nothing playing")
            self.next_label.configure(text=(st or {}).get("error") or "")
            self.play_btn.configure(text="▶")
            self.pos_label.configure(text="0:00")
            self.len_label.configure(text="0:00")
            if not self._seeking:
                self.seek_slider.set(0)
            return
        state = st["state"]
        self.now_title.configure(text=track.title + ("  (paused)" if state == "paused" else ""))
        nxt = st["next"]
        if st["error"]:
            self.next_label.configure(text=st["error"])
        elif nxt is not None:
            self.next_label.configure(text=f"Up next: {nxt.title}" + (f"   ({st['index'] + 1} of {st['count']})"
                                                                      if st["count"] > 1 else ""))
        else:
            self.next_label.configure(text="Last track" if st["count"] > 1 else "")
        self.play_btn.configure(text="❚❚" if state == "playing" else "▶")
        pos, dur = st["position"], st["duration"]
        self.pos_label.configure(text=format_time(pos))
        self.len_label.configure(text=format_time(dur) if dur else "?")
        if not self._seeking and dur:
            self.seek_slider.set(min(1.0, pos / dur))
