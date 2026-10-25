"""
The music player behind Game Tools > Music. No UI: the page and the hotkeys drive it.

Sound comes from miniaudio (a small library that decodes MP3, FLAC, WAV and Ogg Vorbis and talks to the
sound card itself; nothing else to install). The player keeps playing while the person uses other pages.

Effects are worked out here, a block of samples at a time, in plain Python (no numpy):

* fades: fade in when music starts from silence, crossfade from one track to the next, fade out on stop;
* pitch: tape style, the track plays faster and higher or slower and lower (miniaudio resamples it);
* distortion: soft clipping, from warm to broken speaker;
* muffle: a low-pass filter, like music through a wall.

Threads: the sound card asks for samples on miniaudio's own thread (:meth:`MusicPlayer._render`). Opening
files, seeking and moving through the queue happen on the player's worker thread, so neither the window nor
the sound ever waits for a file. The worker sleeps when nothing is playing.
"""

from __future__ import annotations

import array
import math
import queue
import random
import threading
import time
from typing import Callable, Iterator, List, Optional

OUT_RATE = 44100
CHANNELS = 2
PAUSE_FADE = 0.25          # seconds: pause and resume fade quickly instead of clicking
RESTART_AFTER = 3.0        # Previous restarts the track when it is further in than this
TICK = 0.1                 # the worker looks at the queue this often while music plays

Opener = Callable[[str, int, int], Iterator]     # (path, sample rate, first frame) -> a sample stream


def available() -> bool:
    try:
        import miniaudio  # noqa: F401
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Effects (lists of interleaved stereo samples, scaled like 16-bit)
# --------------------------------------------------------------------------- #

def pitch_factor(semitones: float) -> float:
    return 2.0 ** (float(semitones) / 12.0)


def ramp(samples, gain: float, target: float, step: float, scale: float = 1.0):
    """Multiply by a gain that moves by ``step`` each frame until it reaches ``target``.
    Returns (samples, gain at the end)."""
    n = len(samples) // CHANNELS
    if step == 0.0 or gain == target:
        g = target * scale
        if g == 1.0:
            return list(samples), target
        return [s * g for s in samples], target
    k = min(n, int(math.ceil(abs(target - gain) / abs(step))))
    gains = [gain + step * (j + 1) for j in range(k)]
    if gains and (gains[-1] - target) * step >= 0:
        gains[-1] = target                      # don't overshoot
    end = gains[-1] if gains else gain
    head = [samples[i] * gains[i >> 1] * scale for i in range(CHANNELS * k)]
    if k < n:
        g = target * scale
        head.extend(s * g for s in samples[CHANNELS * k:])
        end = target
    return head, end


def muffle_alpha(amount: float, rate: int = OUT_RATE) -> float:
    """The low-pass filter's coefficient: 0 = off, 100 = cut-off near 300 Hz."""
    if amount <= 0:
        return 1.0
    cutoff = 20000.0 * (300.0 / 20000.0) ** (min(100.0, amount) / 100.0)
    return 1.0 - math.exp(-2.0 * math.pi * cutoff / rate)


def lowpass(samples, alpha: float, state: List[float]):
    """Two one-pole low-pass filters in a row, per channel. ``state`` (4 numbers) carries on between blocks."""
    l1, r1, l2, r2 = state
    out = [0.0] * len(samples)
    for i in range(0, len(samples) - 1, 2):
        l1 += alpha * (samples[i] - l1)
        r1 += alpha * (samples[i + 1] - r1)
        l2 += alpha * (l1 - l2)
        r2 += alpha * (r1 - r2)
        out[i] = l2
        out[i + 1] = r2
    state[:] = [l1, r1, l2, r2]
    return out


def distort(samples, amount: float):
    """Soft clipping: 0 = clean, 100 = very driven (the level stays about the same)."""
    if amount <= 0:
        return samples
    drive = 1.0 + min(100.0, amount) * 0.24
    k = drive / 32768.0
    c = 32767.0 / math.tanh(drive)
    tanh = math.tanh
    return [tanh(s * k) * c for s in samples]


def to_pcm(samples, volume: float) -> array.array:
    """Scale by the master volume and clip into 16-bit samples."""
    return array.array("h", [int(v) if -32768.0 < v < 32767.0 else (32767 if v > 0 else -32768)
                             for v in (s * volume for s in samples)])


# --------------------------------------------------------------------------- #
# One playing track
# --------------------------------------------------------------------------- #

def open_stream(path: str, rate: int, seek_frame: int) -> Iterator:
    import miniaudio
    return miniaudio.stream_file(path, output_format=miniaudio.SampleFormat.SIGNED16, nchannels=CHANNELS,
                                 sample_rate=rate, seek_frame=max(0, seek_frame))


def file_duration(path: str) -> float:
    import miniaudio
    info = miniaudio.get_file_info(path)
    return float(info.duration)


class Voice:
    """A track being played: its sample stream, where it is, and its fade."""

    def __init__(self, track, opener: Opener, pitch: float, start: float = 0.0, gain: float = 1.0,
                 queue_index: int = -1, duration: float = 0.0):
        self.track = track
        self.queue_index = queue_index
        self.duration = duration or float(getattr(track, "duration", 0.0) or 0.0)
        self.gain = gain
        self.target = gain
        self.step = 0.0
        self.stop_at_silence = False
        self.done = False
        self._opener = opener
        self.stream, self.rate, self.frame = self.open(pitch, start)

    def open(self, pitch: float, start: float):
        """A new stream at ``start`` seconds for this pitch (the caller swaps it in)."""
        rate = max(4000, int(round(OUT_RATE / pitch_factor(pitch))))
        frame = int(max(0.0, start) * rate)
        return self._opener(self.track.path, rate, frame), rate, frame

    def swap(self, opened):
        old = self.stream
        self.stream, self.rate, self.frame = opened
        _close(old)

    def close(self):
        _close(self.stream)

    @property
    def position(self) -> float:
        return self.frame / self.rate if self.rate else 0.0

    def remaining(self) -> Optional[float]:
        """Seconds of real time left (None if the length isn't known)."""
        if not self.duration:
            return None
        return max(0.0, (self.duration - self.position) * self.rate / OUT_RATE)

    def fade_to(self, target: float, seconds: float, stop: bool = False):
        self.target = target
        self.stop_at_silence = stop
        frames = seconds * OUT_RATE
        if frames < 1:
            self.gain, self.step = target, 0.0
        else:
            self.step = (target - self.gain) / frames

    def read(self, frames: int) -> list:
        """Up to ``frames`` frames with the fade and the track's volume applied (fewer at the end)."""
        if self.done:
            return []
        if self.gain <= 0.0 and self.target <= 0.0 and not self.stop_at_silence:
            return [0.0] * (frames * CHANNELS)     # paused: hold the place
        try:
            chunk = self.stream.send(frames)
        except StopIteration:
            chunk = []
        except Exception:
            chunk = []
        if len(chunk) < frames * CHANNELS:
            self.done = True
        self.frame += len(chunk) // CHANNELS
        samples, self.gain = ramp(chunk, self.gain, self.target, self.step,
                                  float(getattr(self.track, "volume", 1.0)))
        if self.gain == self.target:
            self.step = 0.0
            if self.stop_at_silence and self.target <= 0.0:
                self.done = True
        return samples


def _close(stream):
    try:
        stream.close()
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# The player
# --------------------------------------------------------------------------- #

class MusicPlayer:
    """A queue of tracks played with fades and effects. Every method is safe to call from the UI thread."""

    def __init__(self, device_factory: Optional[Callable[[], object]] = None, opener: Opener = open_stream,
                 duration_of: Callable[[str], float] = file_duration):
        self._device_factory = device_factory or self._default_device
        self._opener = opener
        self._duration_of = duration_of
        self._lock = threading.RLock()
        self._cmds: "queue.Queue" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._closed = False
        self._device = None
        self._lp_state = [0.0, 0.0, 0.0, 0.0]

        self.queue: list = []                  # tracks in play order
        self._original: list = []              # the same tracks in the order they were given (for shuffle off)
        self.voices: List[Voice] = []          # sounding now (more than one while crossfading)
        self.current: Optional[Voice] = None
        self.pending: Optional[Voice] = None   # opened ahead: starts the moment current ends
        self.state = "stopped"                 # stopped | playing | paused
        self._pausing = False
        self._last_index = -1
        self.error = ""

        self.volume = 0.8
        self.pitch = 0.0
        self.distortion = 0.0
        self.muffle = 0.0
        self.fade_in = 2.0
        self.crossfade = 3.0
        self.fade_out = 3.0
        self.loop = "all"                      # off | all | one
        self.shuffle = False

    # ------------------------------------------------------------------ settings

    def apply_settings(self, settings: dict):
        with self._lock:
            self.volume = max(0.0, min(1.0, float(settings.get("volume", self.volume))))
            self.distortion = max(0.0, min(100.0, float(settings.get("distortion", self.distortion))))
            self.muffle = max(0.0, min(100.0, float(settings.get("muffle", self.muffle))))
            self.fade_in = max(0.0, float(settings.get("fade_in", self.fade_in)))
            self.crossfade = max(0.0, float(settings.get("crossfade", self.crossfade)))
            self.fade_out = max(0.0, float(settings.get("fade_out", self.fade_out)))
            loop = settings.get("loop", self.loop)
            self.loop = loop if loop in ("off", "all", "one") else "all"
        self.set_shuffle(bool(settings.get("shuffle", self.shuffle)))
        self.set_pitch(float(settings.get("pitch", self.pitch)))

    def set_volume(self, volume: float):
        self.volume = max(0.0, min(1.0, float(volume)))

    def set_effects(self, distortion: Optional[float] = None, muffle: Optional[float] = None):
        if distortion is not None:
            self.distortion = max(0.0, min(100.0, float(distortion)))
        if muffle is not None:
            self.muffle = max(0.0, min(100.0, float(muffle)))

    def set_pitch(self, semitones: float):
        semitones = max(-12.0, min(12.0, float(semitones)))
        if semitones == self.pitch:
            return
        self.pitch = semitones
        self._post(self._repitch)

    def set_fades(self, fade_in: Optional[float] = None, crossfade: Optional[float] = None,
                  fade_out: Optional[float] = None):
        if fade_in is not None:
            self.fade_in = max(0.0, float(fade_in))
        if crossfade is not None:
            self.crossfade = max(0.0, float(crossfade))
            self._post(self._drop_pending)
        if fade_out is not None:
            self.fade_out = max(0.0, float(fade_out))

    def set_loop(self, mode: str):
        if mode in ("off", "all", "one"):
            self.loop = mode
            self._post(self._drop_pending)

    def set_shuffle(self, on: bool):
        on = bool(on)
        if on == self.shuffle:
            return
        self.shuffle = on
        self._post(self._reorder)

    # ------------------------------------------------------------------ transport

    def play(self, tracks: list, index: int = 0):
        """Play these tracks from ``index`` (crossfading from whatever plays now)."""
        tracks = [t for t in tracks if getattr(t, "path", "") and not getattr(t, "url", "")]
        if not tracks:
            return
        index = max(0, min(index, len(tracks) - 1))
        self._post(lambda: self._start_queue(tracks, index))

    def toggle_pause(self):
        self._post(self._toggle_pause)

    def pause(self):
        self._post(lambda: self._toggle_pause() if self.state == "playing" and not self._pausing else None)

    def resume(self):
        self._post(lambda: self._toggle_pause() if self.state == "paused" or self._pausing else None)

    def next(self):
        self._post(lambda: self._skip(+1))

    def previous(self):
        self._post(lambda: self._skip(-1))

    def stop(self, fade: bool = True):
        self._post(lambda: self._stop(fade))

    def seek(self, seconds: float):
        self._post(lambda: self._seek(seconds))

    def close(self):
        """Stop at once and end the worker (when the app closes)."""
        self._closed = True
        self._cmds.put(None)
        worker = self._worker
        if worker is not None and worker.is_alive() and worker is not threading.current_thread():
            worker.join(timeout=2)
        self._close_device()
        with self._lock:
            for v in self.voices + ([self.pending] if self.pending else []):
                v.close()
            self.voices, self.current, self.pending = [], None, None
            self.state = "stopped"

    def status(self) -> dict:
        with self._lock:
            cur = self.current
            state = "paused" if self._pausing else self.state
            if state == "playing" and cur is None:
                state = "stopping"              # fading out
            return {
                "state": state,
                "track": cur.track if cur else None,
                "position": cur.position if cur else 0.0,
                "duration": cur.duration if cur else 0.0,
                "index": cur.queue_index if cur else -1,
                "count": len(self.queue),
                "next": self._peek_next_track(),
                "error": self.error,
            }

    def wait_idle(self, timeout: float = 2.0) -> bool:
        """Wait until the worker has done everything asked of it so far (for tests)."""
        done = threading.Event()
        self._post(done.set)
        return done.wait(timeout)

    # ------------------------------------------------------------------ worker

    def _post(self, fn: Callable[[], None]):
        if self._closed:
            return
        self._cmds.put(fn)
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work, name="music-player", daemon=True)
            self._worker.start()

    def _work(self):
        while not self._closed:
            active = self.state == "playing" or self._pausing
            try:
                fn = self._cmds.get(timeout=TICK) if active else self._cmds.get()
            except queue.Empty:
                fn = None
            if self._closed:
                break
            if fn is not None:
                try:
                    fn()
                except Exception as e:          # a bad file must not end the worker
                    self.error = str(e)
            try:
                self._tick()
            except Exception as e:
                self.error = str(e)

    def _open_voice(self, index: int, start: float = 0.0, gain: float = 1.0) -> Optional[Voice]:
        """Open queue[index], skipping tracks that can't be played. None if none can."""
        tried = 0
        while self.queue and tried < len(self.queue):
            index %= len(self.queue)
            track = self.queue[index]
            try:
                duration = float(getattr(track, "duration", 0.0) or 0.0)
                if not duration:
                    try:
                        duration = float(self._duration_of(track.path))
                        track.duration = duration
                    except Exception:
                        duration = 0.0
                voice = Voice(track, self._opener, self.pitch, start, gain, index, duration)
                self.error = ""
                return voice
            except Exception as e:
                self.error = f"Couldn't play {getattr(track, 'title', track.path)}: {e}"
                tried += 1
                if self.loop == "off" and index + 1 >= len(self.queue):
                    return None
                index += 1
                start = 0.0
        return None

    def _start_queue(self, tracks: list, index: int):
        first = tracks[index]
        self._original = list(tracks)
        if self.shuffle:
            rest = tracks[:index] + tracks[index + 1:]
            random.shuffle(rest)
            self.queue, index = [first] + rest, 0
        else:
            self.queue = list(tracks)
        self._switch_to(index)

    def _switch_to(self, index: int, start: float = 0.0):
        """Start queue[index]: crossfade from what plays now, or fade in from silence."""
        sounding = self.state == "playing" and not self._pausing and any(v.gain > 0 for v in self.voices)
        voice = self._open_voice(index, start, gain=0.0)
        if voice is None:
            return
        fade = self.crossfade if sounding else self.fade_in
        voice.fade_to(1.0, fade)
        with self._lock:
            for v in self.voices:
                v.fade_to(0.0, max(0.05, self.crossfade if sounding else 0.0), stop=True)
            if self.pending is not None:
                self.pending.close()
                self.pending = None
            self.voices.append(voice)
            self.current = voice
            self._pausing = False
            self.state = "playing"
        self._open_device()

    def _toggle_pause(self):
        with self._lock:
            if self.current is None:
                return
            if self.state == "playing" and not self._pausing:
                self._pausing = True
                for v in self.voices:
                    if v is self.current:
                        v.fade_to(0.0, PAUSE_FADE)
                    else:
                        v.fade_to(0.0, PAUSE_FADE, stop=True)
                return
            self._pausing = False
            self.state = "playing"
            self.current.fade_to(1.0, PAUSE_FADE)
        self._open_device()

    def _stop(self, fade: bool):
        with self._lock:
            seconds = self.fade_out if fade and self.state == "playing" and not self._pausing else 0.0
            if self.pending is not None:
                self.pending.close()
                self.pending = None
            self.current = None                 # nothing comes after the fade
            self._pausing = False
            if seconds > 0.0 and self.voices:
                for v in self.voices:
                    v.fade_to(0.0, seconds, stop=True)
                return
            for v in self.voices:
                v.close()
            self.voices = []
            self.state = "stopped"
        self._close_device()

    def _skip(self, direction: int):
        cur = self.current
        if cur is None or not self.queue:
            return
        if direction < 0 and cur.position > RESTART_AFTER:
            self._seek(0.0)
            return
        index = cur.queue_index + direction
        if index < 0:
            index = len(self.queue) - 1 if self.loop == "all" else 0
        elif index >= len(self.queue):
            if self.loop == "off":
                self._stop(True)
                return
            index = 0
        self._switch_to(index)

    def _seek(self, seconds: float):
        cur = self.current
        if cur is None:
            return
        if cur.duration:
            seconds = min(seconds, max(0.0, cur.duration - 0.05))
        try:
            opened = cur.open(self.pitch, seconds)
        except Exception as e:
            self.error = str(e)
            return
        with self._lock:
            if cur is self.current:
                cur.swap(opened)
                cur.done = False
            else:
                _close(opened[0])
        self._drop_pending()

    def _repitch(self):
        with self._lock:
            voices = list(self.voices)
        for v in voices:
            try:
                opened = v.open(self.pitch, v.position)
            except Exception:
                continue
            with self._lock:
                if v in self.voices:
                    v.swap(opened)
                else:
                    _close(opened[0])
        self._drop_pending()

    def _drop_pending(self):
        with self._lock:
            if self.pending is not None:
                self.pending.close()
                self.pending = None

    def _reorder(self):
        with self._lock:
            cur = self.current
            if not self.queue:
                return
            current_track = cur.track if cur else None
            if self.shuffle:
                rest = [t for t in self.queue if t is not current_track]
                random.shuffle(rest)
                self.queue = ([current_track] if current_track is not None else []) + rest
            else:
                self.queue = list(self._original) or self.queue
            if cur is not None and current_track in self.queue:
                cur.queue_index = self.queue.index(current_track)
        self._drop_pending()

    def _next_index(self, after: int) -> Optional[int]:
        if not self.queue:
            return None
        if self.loop == "one":
            return after
        if after + 1 < len(self.queue):
            return after + 1
        return 0 if self.loop == "all" else None

    def _peek_next_track(self):
        cur = self.current
        if cur is None:
            return None
        i = self._next_index(cur.queue_index)
        return self.queue[i] if i is not None and i < len(self.queue) else None

    def _tick(self):
        """Move through the queue: crossfade or line up the next track, and close the device when silent."""
        with self._lock:
            cur = self.current
            ended = cur is not None and cur.done and self.pending is None
            for v in [v for v in self.voices if v.done]:
                v.close()
                self.voices.remove(v)
            if self.current is not None and self.current not in self.voices:
                self.current = None
            if self._pausing and self.current is not None and self.current.gain <= 0.0 and len(self.voices) <= 1:
                self._pausing = False
                self.state = "paused"
            cur = self.current
        if ended and cur is None:
            # the track ran out before the next one was lined up (its length wasn't known, or was wrong)
            nxt = self._next_index(self._last_index)
            if nxt is not None:
                voice = self._open_voice(nxt)
                if voice is not None:
                    with self._lock:
                        self.voices.append(voice)
                        self.current = cur = voice
        with self._lock:
            if not self.voices and self.state == "playing":
                self.state = "stopped"
            state = self.state
        if state != "playing":
            self._close_device()
            return
        if cur is None or self._pausing:
            return
        self._last_index = cur.queue_index
        remaining = cur.remaining()
        if remaining is None or self.pending is not None or cur.target <= 0:
            return
        nxt = self._next_index(cur.queue_index)
        if nxt is None:
            return
        cross = min(self.crossfade, (cur.duration * cur.rate / OUT_RATE) / 3.0)
        if cross > 0.05 and remaining <= cross:
            voice = self._open_voice(nxt, gain=0.0)
            if voice is not None:
                voice.fade_to(1.0, remaining)
                with self._lock:
                    cur.fade_to(0.0, max(0.05, remaining), stop=True)
                    self.voices.append(voice)
                    self.current = voice
        elif cross <= 0.05 and remaining <= 1.0:
            voice = self._open_voice(nxt, gain=1.0)
            if voice is not None:
                with self._lock:
                    self.pending = voice

    # ------------------------------------------------------------------ sound card

    @staticmethod
    def _default_device():
        import miniaudio
        return miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16, nchannels=CHANNELS,
                                        sample_rate=OUT_RATE, buffersize_msec=150, app_name="Spellbook")

    def _open_device(self):
        if self._device is not None:
            return
        try:
            device = self._device_factory()
            gen = self._generator()
            next(gen)
            device.start(gen)
            self._device = device
        except Exception as e:
            self.error = f"No sound: {e}"
            with self._lock:
                for v in self.voices:
                    v.close()
                self.voices, self.current = [], None
                self.state = "stopped"

    def _close_device(self):
        device, self._device = self._device, None
        if device is None:
            return
        for name in ("stop", "close"):
            try:
                getattr(device, name)()
            except Exception:
                pass

    def _generator(self):
        frames = yield b""
        while True:
            frames = yield self._render(frames)

    def _render(self, frames: int) -> array.array:
        """``frames`` frames of the mix, with the effects and the volume (the sound card's thread)."""
        try:
            with self._lock:
                mixed = None
                for v in list(self.voices):
                    s = v.read(frames)
                    if v.done and v is self.current and self.pending is not None:
                        nxt, self.pending = self.pending, None
                        self.voices.append(nxt)
                        self.current = nxt
                        got = len(s) // CHANNELS
                        if got < frames:
                            s = s + nxt.read(frames - got)
                    if len(s) < frames * CHANNELS:
                        s = s + [0.0] * (frames * CHANNELS - len(s))
                    mixed = s if mixed is None else [a + b for a, b in zip(mixed, s)]
                volume, muffle, drive = self.volume, self.muffle, self.distortion
            if mixed is None:
                return array.array("h", bytes(frames * CHANNELS * 2))
            if muffle > 0:
                mixed = lowpass(mixed, muffle_alpha(muffle), self._lp_state)
            if drive > 0:
                mixed = distort(mixed, drive)
            return to_pcm(mixed, volume)
        except Exception as e:
            self.error = str(e)
            return array.array("h", bytes(frames * CHANNELS * 2))


_player: Optional[MusicPlayer] = None


def get_player() -> MusicPlayer:
    global _player
    if _player is None:
        _player = MusicPlayer()
    return _player


def peek_player() -> Optional[MusicPlayer]:
    """The player if music was ever played this run (closing the app stops it)."""
    return _player
