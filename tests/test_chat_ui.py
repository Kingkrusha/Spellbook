"""Chat rendering (links, dice lines) and outgoing link handling, with a hidden Tk root."""

import time
import tkinter as tk

import pytest

from ui.chat_input import qualify_links


@pytest.fixture()
def text(tk_root):
    widget = tk.Text(tk_root, font=("TkDefaultFont", 10))
    widget.pack()
    yield widget
    widget.destroy()


class FakeService:
    my_id = "me"

    def peer_name(self, pid):
        return {"p2": "Bob"}.get(pid, "")


def line(kind, text="", **kw):
    base = {"kind": kind, "text": text, "name": "Alice", "from": "p1", "to": "", "ts": time.time(), "mine": False}
    base.update(kw)
    return base


def test_links_are_rendered_and_tagged(text):
    from ui.chat_render import ChatLog
    log = ChatLog(text, FakeService())
    log.append(line("chat", "I cast [[spell:Fireball]] and [[equipment:Longsword|my sword]]!"))
    body = text.get("1.0", "end")
    assert "Fireball and my sword!" in body and "[[" not in body       # markup is replaced by its display text
    links = [t for t in text.tag_names() if t.startswith("chatlink")]
    assert len(links) == 2
    assert all("obj_link" in text.tag_names(text.tag_ranges(t)[0]) for t in links)


def test_roll_lines(text):
    from ui.chat_render import ChatLog
    log = ChatLog(text, FakeService())
    roll = {"expr": "1d20+5", "detail": "[20] + 5", "total": 25, "label": "Stealth", "crit": "nat20",
            "private": False}
    log.append(line("roll", roll=roll))
    log.append(line("roll", roll=dict(roll, private=True, crit=""), mine=True, **{"from": "me"}))
    body = text.get("1.0", "end")
    assert "Alice rolled 1d20+5 (Stealth): [20] + 5 = 25  natural 20!" in body
    assert "(private) You rolled" in body
    assert text.tag_ranges("nat20")


def test_whisper_lines(text):
    from ui.chat_render import ChatLog
    log = ChatLog(text, FakeService())
    log.append(line("dm", "psst", to="me"))
    log.append(line("dm", "yes?", to="p2", mine=True, **{"from": "me"}))
    body = text.get("1.0", "end")
    assert "(whisper) Alice → you: psst" in body and "(whisper) You → Bob: yes?" in body


def test_set_lines_redraws(text):
    from ui.chat_render import ChatLog
    log = ChatLog(text, FakeService())
    log.append(line("chat", "one"))
    log.set_lines([line("chat", "two"), line("system", "three")])
    body = text.get("1.0", "end")
    assert "one" not in body and "two" in body and "three" in body


def test_qualify_links():
    assert qualify_links("cast [[Fireball]] now") == "cast [[Fireball]] now"        # a spell: unchanged
    assert qualify_links("[[spell:Fireball]]") == "[[spell:Fireball]]"              # already qualified
    assert qualify_links("[[Definitely Not Real]]") == "[[Definitely Not Real]]"    # unknown: left alone
    fixed = qualify_links("[[Longsword]]")
    assert fixed.startswith("[[") and ":" in fixed and "Longsword" in fixed         # found elsewhere: qualified
