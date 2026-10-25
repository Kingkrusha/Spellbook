"""The music player (music_player.py), its library (music_library.py) and the Music page."""

import array
import math
import os
import wave

import pytest

import music_library as ml
import music_player as mp


# --------------------------------------------------------------------------- #
# Helpers: fake files (constant samples, one level per track) and a sound card the test drives
# --------------------------------------------------------------------------- #

class FakeTrack:
    def __init__(self, path, title=None, volume=1.0, duration=0.0):
        self.path, self.title, self.volume, self.duration, self.url = path, title or path, volume, duration, ""
        self.id = path


def fake_opener(levels, lengths, fail=()):
    """Each "file" plays its level for its length in seconds."""
    def opener(path, rate, seek):
        if path in fail:
            raise OSError("can't open")
        total = int(lengths[path] * rate)
        level = levels[path]
        state = {"pos": seek}

        def gen():
            n = yield array.array("h")
            while state["pos"] < total:
                k = min(n or 1024, total - state["pos"])
                state["pos"] += k
                n = yield array.array("h", [level] * (2 * k))
        g = gen()
        next(g)
        return g
    return opener


class FakeDevice:
    instances = []

    def __init__(self):
        self.gen = None
        self.stopped = False
        FakeDevice.instances.append(self)

    def start(self, gen):
        self.gen = gen

    def stop(self):
        self.stopped = True

    def close(self):
        pass


def make_player(levels, lengths, **kw):
    FakeDevice.instances = []
    player = mp.MusicPlayer(device_factory=FakeDevice, opener=fake_opener(levels, lengths, kw.pop("fail", ())),
                            duration_of=lambda p: lengths[p])
    player.volume = 1.0
    player.fade_in = kw.get("fade_in", 0.0)
    player.crossfade = kw.get("crossfade", 0.0)
    player.fade_out = kw.get("fade_out", 0.0)
    player.loop = kw.get("loop", "off")
    return player


def pump(player, seconds, block=441):
    """Play ``seconds`` of sound, letting the worker look at the queue every 10 ms. Returns the left channel."""
    out = []
    for _ in range(int(seconds * mp.OUT_RATE / block)):
        device = player._device
        if device is None:
            out.extend([0] * block)
        else:
            out.extend(device.gen.send(block)[::2])
        player.wait_idle()
    return out


# --------------------------------------------------------------------------- #
# Effects
# --------------------------------------------------------------------------- #

def test_ramp_moves_to_the_target_and_stops_there():
    samples = [1000.0] * 20                  # 10 frames
    out, gain = mp.ramp(samples, 0.0, 1.0, 0.25)
    assert [round(x) for x in out[::2]] == [250, 500, 750, 1000, 1000, 1000, 1000, 1000, 1000, 1000]
    assert gain == 1.0
    out, gain = mp.ramp(samples, 1.0, 0.0, -0.05)
    assert gain == pytest.approx(0.5) and out[-1] == pytest.approx(500)
    out, gain = mp.ramp(samples, 1.0, 1.0, 0.0, scale=0.5)
    assert out == [500.0] * 20


def test_distortion_and_muffle():
    loud = [30000.0, -30000.0] * 50
    driven = mp.distort(loud, 100)
    assert all(abs(x) <= 32767 for x in driven)
    quiet = mp.distort([1000.0, -1000.0], 100)
    assert quiet[0] > 1000 * 5                 # quiet sound is driven up hard
    assert mp.distort(loud, 0) is loud
    # a fast square wave comes out much smaller through the filter; a steady level gets through
    square = [10000.0, 10000.0, -10000.0, -10000.0] * 200
    state = [0.0] * 4
    filtered = mp.lowpass(square, mp.muffle_alpha(100), state)
    assert max(abs(x) for x in filtered[200:]) < 2000
    steady = mp.lowpass([5000.0] * 4000, mp.muffle_alpha(100), [0.0] * 4)
    assert steady[-1] == pytest.approx(5000, rel=0.02)
    assert mp.muffle_alpha(0) == 1.0
    pcm = mp.to_pcm([40000.0, -40000.0, 100.4], 1.0)
    assert list(pcm) == [32767, -32768, 100]


def test_pitch_factor():
    assert mp.pitch_factor(12) == pytest.approx(2.0)
    assert mp.pitch_factor(-12) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# The player
# --------------------------------------------------------------------------- #

def test_plays_a_queue_and_stops_at_the_end():
    p = make_player({"a": 1000, "b": 2000}, {"a": 0.5, "b": 0.5})
    p.play([FakeTrack("a"), FakeTrack("b")], 0)
    p.wait_idle()
    assert p.status()["state"] == "playing" and p.status()["track"].path == "a"
    assert p.status()["next"].path == "b"
    sound = pump(p, 1.3)
    assert sound[100] == 1000 and sound[int(0.75 * mp.OUT_RATE)] == 2000      # no gap between the tracks
    assert p.status()["state"] == "stopped"
    assert p._device is None and FakeDevice.instances[0].stopped
    p.close()


def test_fade_in_and_crossfade():
    p = make_player({"a": 1000, "b": 3000}, {"a": 2.0, "b": 2.0}, fade_in=0.5, crossfade=0.5, loop="off")
    p.play([FakeTrack("a"), FakeTrack("b")], 0)
    p.wait_idle()
    sound = pump(p, 3.0)
    at = lambda s: sound[int(s * mp.OUT_RATE)]
    assert at(0.0) < 100 and 300 < at(0.25) < 700 and at(1.0) == 1000          # fades in
    assert 1000 < at(1.8) < 3000                                               # both play while crossfading
    assert at(2.2) == 3000
    p.close()


def test_loop_one_track_repeats_it():
    p = make_player({"a": 1000, "b": 2000}, {"a": 0.3, "b": 0.3}, loop="one")
    p.play([FakeTrack("a"), FakeTrack("b")], 0)
    p.wait_idle()
    sound = pump(p, 1.0)
    assert set(sound[100:]) == {1000}
    assert p.status()["track"].path == "a" and p.status()["state"] == "playing"
    p.close()


def test_pause_keeps_the_place_and_resume_carries_on():
    p = make_player({"a": 1000}, {"a": 5.0})
    p.play([FakeTrack("a")], 0)
    p.wait_idle()
    pump(p, 1.0)
    p.toggle_pause()
    pump(p, 0.5)
    st = p.status()
    assert st["state"] == "paused" and p._device is None
    where = st["position"]
    assert 1.0 <= where < 1.4
    p.toggle_pause()
    p.wait_idle()
    assert p.status()["state"] == "playing"
    sound = pump(p, 0.5)
    assert sound[-1] == 1000
    assert p.status()["position"] == pytest.approx(where + 0.5, abs=0.05)
    p.close()


def test_stop_fades_out_then_closes_the_device():
    p = make_player({"a": 1000}, {"a": 5.0}, fade_out=0.5)
    p.play([FakeTrack("a")], 0)
    p.wait_idle()
    pump(p, 0.2)
    p.stop()
    p.wait_idle()
    assert p.status()["state"] == "stopping"
    sound = pump(p, 0.8)
    assert 300 < sound[int(0.25 * mp.OUT_RATE)] < 700
    assert p.status()["state"] == "stopped" and p._device is None
    p.close()


def test_next_previous_and_seek():
    p = make_player({"a": 1000, "b": 2000, "c": 3000}, {"a": 5.0, "b": 5.0, "c": 5.0}, loop="all")
    tracks = [FakeTrack("a"), FakeTrack("b"), FakeTrack("c")]
    p.play(tracks, 1)
    p.wait_idle()
    p.next()
    p.wait_idle()
    assert p.status()["track"].path == "c"
    p.next()
    p.wait_idle()
    assert p.status()["track"].path == "a"                  # loops round
    p.previous()
    p.wait_idle()
    assert p.status()["track"].path == "c"
    p.seek(4.0)
    p.wait_idle()
    assert p.status()["position"] == pytest.approx(4.0, abs=0.01)
    p.previous()                                            # far in: back to the start of this track
    p.wait_idle()
    assert p.status()["track"].path == "c" and p.status()["position"] < 0.1
    p.close()


def test_pitch_plays_faster_and_effects_apply():
    p = make_player({"a": 10000}, {"a": 10.0})
    p.play([FakeTrack("a")], 0)
    p.wait_idle()
    p.set_pitch(12)
    p.wait_idle()
    pump(p, 0.5)
    assert p.status()["position"] == pytest.approx(1.0, abs=0.05)    # an octave up: twice as fast
    p.set_volume(0.5)
    p.set_effects(distortion=0, muffle=0)
    assert pump(p, 0.1)[-1] == 5000
    p.set_effects(distortion=60)
    assert pump(p, 0.1)[-1] > 10000                         # driven louder, but still in range
    p.close()


def test_a_file_that_wont_open_is_skipped():
    p = make_player({"a": 1000, "b": 2000}, {"a": 1.0, "b": 1.0}, fail={"a"})
    p.play([FakeTrack("a"), FakeTrack("b")], 0)
    p.wait_idle()
    assert p.status()["track"].path == "b"
    p.close()


def test_shuffle_keeps_the_current_track_first():
    lengths = {str(i): 5.0 for i in range(20)}
    p = make_player({k: 1000 for k in lengths}, lengths)
    p.shuffle = True
    tracks = [FakeTrack(k) for k in lengths]
    p.play(tracks, 7)
    p.wait_idle()
    assert p.queue[0].path == "7" and sorted(t.path for t in p.queue) == sorted(lengths)
    p.set_shuffle(False)
    p.wait_idle()
    assert [t.path for t in p.queue] == list(lengths) and p.status()["index"] == 7
    p.close()


def write_wav(path, seconds=0.5, freq=440):
    rate = 22050
    frames = int(rate * seconds)
    data = array.array("h", [int(8000 * math.sin(2 * math.pi * freq * i / rate)) for i in range(frames)])
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return str(path)


@pytest.mark.skipif(not mp.available(), reason="miniaudio isn't installed")
def test_real_file_decodes_resampled_to_stereo(tmp_path):
    path = write_wav(tmp_path / "tone.wav", 0.5)
    assert mp.file_duration(path) == pytest.approx(0.5, abs=0.01)
    stream = mp.open_stream(path, mp.OUT_RATE, 0)
    chunk = stream.send(1000)
    assert len(chunk) == 2000 and chunk[0] == chunk[1]          # mono comes out on both channels
    stream.close()


# --------------------------------------------------------------------------- #
# The library
# --------------------------------------------------------------------------- #

def test_library_scans_folders_with_sub_folder_tags_and_saves(tmp_path):
    music = tmp_path / "Music"
    (music / "Tavern").mkdir(parents=True)
    (music / "Combat" / "Undead").mkdir(parents=True)
    write_wav(music / "Combat" / "Undead" / "zombie_horde.wav")
    write_wav(music / "Tavern" / "jolly_jig.wav")
    write_wav(music / "theme.wav")
    (music / "notes.txt").write_text("not music")
    lib = ml.MusicLibrary(str(tmp_path / "music.json"))
    assert lib.add_folder(str(music)) and not lib.add_folder(str(music))
    report = lib.scan()
    assert report.added == 3 and lib.scan().added == 0
    horde = next(t for t in lib.tracks if t.title == "zombie horde")
    assert horde.tags == ["Combat", "Undead"]                # every sub-folder is a tag
    assert lib.find(tags=["combat", "undead"]) == [horde] and lib.find(tags=["Undead", "Tavern"]) == []
    jig = next(t for t in lib.tracks if t.title == "jolly jig")
    assert jig.tags == ["Tavern"]
    lib.remove([horde.id])
    assert lib.read_durations(lambda p: 0.5) == 2 and lib.read_durations(lambda p: 0.5) == 0
    link = lib.add_link("youtu.be/abc", "", ["Tavern", "tavern", " Calm "])
    assert link.url == "https://youtu.be/abc" and link.kind == "YouTube" and link.tags == ["Tavern", "Calm"]
    assert link.title == "YouTube link"
    assert [t.title for t in lib.find(tag="tavern")] == ["jolly jig", "YouTube link"]
    assert [t.title for t in lib.find("jig")] == ["jolly jig"]
    assert lib.all_tags() == ["Calm", "Tavern"]
    lib.settings["volume"] = 0.4
    lib.settings["loop"] = "one"
    jig.volume = 0.7
    lib.save()

    again = ml.MusicLibrary(str(tmp_path / "music.json"))
    assert len(again.tracks) == 3 and again.folders == [str(music)]
    assert again.settings["volume"] == 0.4 and again.settings["loop"] == "one"
    assert again.get(jig.id).volume == 0.7 and again.get(jig.id).duration == 0.5
    again.rename_tag("Tavern", "Inn")
    assert again.all_tags() == ["Calm", "Inn"]
    again.remove_folder(str(music))
    assert [t.title for t in again.tracks] == ["YouTube link"]


def test_library_ignores_a_broken_file_and_bad_settings(tmp_path):
    path = tmp_path / "music.json"
    path.write_text("{not json")
    assert ml.MusicLibrary(str(path)).tracks == []
    path.write_text('{"settings": {"volume": "loud", "loop": "sideways", "shuffle": 1}, "tracks": [{"title": "x"}]}')
    lib = ml.MusicLibrary(str(path))
    assert lib.settings["volume"] == ml.DEFAULT_SETTINGS["volume"]
    assert lib.settings["loop"] == "all" and lib.settings["shuffle"] is False
    assert lib.tracks[0].title == "x" and lib.tracks[0].id


def test_format_time_and_titles():
    assert ml.format_time(5) == "0:05" and ml.format_time(3725) == "1:02:05"
    assert ml.title_from_path("/x/01_The_Inn.mp3") == "01 The Inn"
    assert ml.link_kind("https://open.spotify.com/playlist/1") == "Spotify"


# --------------------------------------------------------------------------- #
# The page
# --------------------------------------------------------------------------- #

@pytest.fixture()
def fresh_fonts(tk_root):
    from typography import get_font_manager
    get_font_manager().scope.refresh()


def test_music_page_lists_filters_and_plays(tk_root, fresh_fonts, tmp_path, monkeypatch):
    music = tmp_path / "Music"
    (music / "Combat").mkdir(parents=True)
    a = write_wav(music / "Combat" / "battle.wav")
    b = write_wav(music / "Combat" / "boss.wav")
    write_wav(music / "calm.wav")
    lib = ml.MusicLibrary(str(tmp_path / "music.json"))
    lib.add_folder(str(music))
    lib.scan()
    for t in lib.tracks:
        t.duration = 0.5
    lib.add_link("https://open.spotify.com/playlist/1", "Tavern playlist", ["Combat"])
    player = make_player({a: 1000, b: 2000}, {a: 5.0, b: 5.0, str(music / "calm.wav"): 5.0})
    monkeypatch.setattr(mp, "available", lambda: True)
    opened = []
    import ui.music_view as view_mod
    monkeypatch.setattr(view_mod.webbrowser, "open", lambda url: opened.append(url))

    view = view_mod.MusicView(tk_root, {}, library=lib, player=player)
    view.pack(fill="both", expand=True)
    tk_root.update()
    assert len(view.tracks._items) == 4
    view.set_tags(["Combat"])
    assert [t.title for t in view.tracks._items] == ["battle", "boss", "Tavern playlist"]

    link = view.tracks._items[2]
    view._play_track(link)
    assert opened == ["https://open.spotify.com/playlist/1"]

    view._play_all()
    player.wait_idle()
    assert player.status()["track"].title == "battle" and len(player.queue) == 2   # the link isn't queued
    view._show_status()
    assert view.now_title.cget("text") == "battle" and "boss" in view.next_label.cget("text")
    assert view.tracks.row_text(view.tracks._items[0]).startswith("♪ ")

    # editing a track's tags moves it between playlists
    view.tracks.select_by_name(view.tracks._items[1].id)
    tk_root.update()
    view.tags_entry.delete(0, "end")
    view.tags_entry.insert(0, "Boss, Combat")
    view._save_track()
    assert "Boss" in lib.all_tags()
    view.set_tags(["combat", "Boss"])                       # tracks with both tags
    assert [t.title for t in view.tracks._items] == ["boss"] and view.tag_btn.cget("text").startswith("Combat + Boss")
    view.set_tags(["Combat"])
    assert ml.MusicLibrary(str(tmp_path / "music.json")).find(tag="boss")[0].title == "boss"

    view._on_volume(50)
    assert player.volume == 0.5 and lib.settings["volume"] == 0.5
    view._on_loop(view_mod.LOOP_LABELS["one"])
    assert player.loop == "one"
    view._on_play_pause()
    player.wait_idle()
    pump(player, 0.4)
    assert player.status()["state"] == "paused"
    view.destroy()
    player.close()
