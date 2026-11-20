"""Getting into a session: what one address may do before the DM has let it in (lan/host.py's ``_Door``),
and names that can't pass for someone else's."""

import socket
import time

import pytest

from lan import host as H
from lan import protocol as P
from lan import web as W
from lan.client import LanClient
from lan.host import LanHost
from lan.protocol import LanError
from tests.test_lan_web import Browser, http_get, no_event, wait_for

ADDRESS = "192.168.1.50"


# --------------------------------------------------------------------------- the door on its own

def test_one_address_can_hold_only_a_few_of_the_waiting_places():
    door = H._Door()
    assert all(door.enter(ADDRESS) for _ in range(H.MAX_PENDING_PER_ADDRESS))
    assert not door.enter(ADDRESS)
    assert door.enter("192.168.1.51")               # someone else still gets in
    door.leave(ADDRESS)
    assert door.enter(ADDRESS)


def test_the_dms_own_computer_is_not_counted():
    door = H._Door()
    for address in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "?"):
        assert all(door.enter(address) for _ in range(20))
        for _ in range(20):
            door.wrong_password(address)
        assert not door.locked_out(address)
        door.refused(address)
        assert door.wait_left(address) == 0


def test_wrong_passwords_lock_an_address_out_for_a_while(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(H.time, "monotonic", lambda: now[0])
    door = H._Door()
    for _ in range(H.WRONG_PASSWORDS - 1):
        door.wrong_password(ADDRESS)
    assert not door.locked_out(ADDRESS)
    door.wrong_password(ADDRESS)
    assert door.locked_out(ADDRESS)
    assert not door.locked_out("192.168.1.51")
    now[0] += H.WRONG_PASSWORD_WINDOW + 1
    assert not door.locked_out(ADDRESS)


def test_each_no_from_the_dm_makes_the_address_wait_longer(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(H.time, "monotonic", lambda: now[0])
    door = H._Door()
    assert door.wait_left(ADDRESS) == 0
    door.refused(ADDRESS)
    assert door.wait_left(ADDRESS) == H.DENY_COOLDOWN
    now[0] += H.DENY_COOLDOWN + 1
    assert door.wait_left(ADDRESS) == 0
    door.refused(ADDRESS)
    assert door.wait_left(ADDRESS) == H.DENY_COOLDOWN * 2
    for _ in range(20):
        door.refused(ADDRESS)
    assert door.wait_left(ADDRESS) == H.DENY_COOLDOWN_MAX
    assert "minutes" in H._wait_words(door.wait_left(ADDRESS))
    door.let_in(ADDRESS)                             # the DM said yes after all
    assert door.wait_left(ADDRESS) == 0


def test_the_door_forgets_old_addresses_rather_than_growing():
    door = H._Door()
    for i in range(door.KEPT + 50):
        door.wrong_password(f"10.0.{i // 250}.{i % 250 + 1}")
        door.refused(f"10.0.{i // 250}.{i % 250 + 1}")
    assert len(door._wrong) == door.KEPT and len(door._refused) == door.KEPT


# --------------------------------------------------------------------------- through a real session

@pytest.fixture()
def strict_host():
    h = LanHost("DM", password="owlbear", require_approval=True)
    h._door.count_loopback = True                   # (the tests only have 127.0.0.1 to come from)
    h.start(port=0, bind="127.0.0.1")
    h.start_web(port=0, bind="127.0.0.1")
    yield h
    h.stop()


def test_guessing_the_password_gets_an_address_locked_out(strict_host):
    h = strict_host
    for _ in range(H.WRONG_PASSWORDS):
        with pytest.raises(LanError) as e:
            LanClient("Mallory", password="nope").connect("127.0.0.1", h.port, h.fingerprint, timeout=20)
        assert e.value.message == "Wrong session password."
    started = time.time()
    with pytest.raises(LanError) as e:              # even the right password has to wait now
        LanClient("Mallory", password="owlbear").connect("127.0.0.1", h.port, h.fingerprint, timeout=20)
    assert e.value.code == "password" and "Too many" in e.value.message
    assert time.time() - started < 5
    no_event(h.events, "approval_request", 0.3)


def test_a_no_from_the_dm_also_holds_for_a_new_name_and_id_from_that_address(strict_host):
    h = strict_host
    b = Browser(h.web_port)
    b.hello(name="Mallory", client_id="aaa111", password="owlbear")
    h.resolve_approval(wait_for(h.events, "approval_request")["request_id"], False, "No.")
    assert b.recv("error")["body"]["message"] == "No."
    b.close()
    again = Browser(h.web_port)
    again.hello(name="Totally Someone Else", client_id="bbb222", password="owlbear")
    err = again.recv("error")["body"]
    assert err["code"] == "declined" and "Wait" in err["message"]
    no_event(h.events, "approval_request", 0.3)
    again.close()


def test_one_address_cannot_fill_the_dms_screen_with_requests(strict_host):
    h = strict_host
    waiting = []
    for i in range(H.MAX_PENDING_PER_ADDRESS):
        b = Browser(h.web_port)
        b.hello(name=f"Player {i}", client_id=f"id{i}", password="owlbear")
        waiting.append(b)
        wait_for(h.events, "approval_request")
    extra = Browser(h.web_port)
    extra.hello(name="One more", client_id="extra", password="owlbear")
    no_event(h.events, "approval_request", 0.5)
    extra.sock.settimeout(5)
    with pytest.raises((ConnectionError, OSError, AssertionError)):
        extra.recv("welcome")                       # that connection was simply closed
    for b in waiting + [extra]:
        b.close()


def test_the_page_server_keeps_places_for_other_addresses(monkeypatch):
    h = LanHost("DM", require_approval=False)
    h.start(port=0, bind="127.0.0.1")
    monkeypatch.setattr(W, "MAX_WAITING_PER_ADDRESS", 3)
    try:
        port = h.start_web(port=0, bind="127.0.0.1")
        silent = [socket.create_connection(("127.0.0.1", port), timeout=5) for _ in range(3)]
        time.sleep(0.3)                             # three connections that never send their request
        with pytest.raises((ConnectionError, OSError, IndexError, ValueError)):
            http_get(port, "/info")                 # a fourth from the same address is closed straight away
        for s in silent:
            s.close()
        deadline = time.time() + 5
        while True:
            try:
                status, _headers, _body = http_get(port, "/info")
                break
            except (ConnectionError, OSError, IndexError, ValueError):
                assert time.time() < deadline
                time.sleep(0.1)
        assert status == 200                        # and the places come back when they go
    finally:
        h.stop()


# --------------------------------------------------------------------------- names and messages

def test_a_name_has_nothing_in_it_that_cannot_be_seen():
    assert P.clean_name("Dun​geon Mas‍ter") == "Dungeon Master"       # zero-width
    assert P.clean_name("‮retsaM noegnuD") == "retsaM noegnuD"             # written backwards
    assert P.clean_name("Rob­in﻿") == "Robin"                         # soft hyphen, byte order mark
    assert P.clean_name("​‎") == "Player"
    assert P.clean_name("Zoë  O'Brien\n") == "Zoë O'Brien"                      # ordinary names are untouched
    assert P.clean_name("דנה") == "דנה"


def test_a_message_cannot_turn_its_text_around():
    assert P.clean_text("the DM says ‮on‬", 100) == "the DM says on"
    assert P.clean_text("a⁦b⁩c", 100) == "abc"
    assert P.clean_text("line one\n\ttwo \x85\x00end", 100) == "line one\n\ttwo end"
    assert P.clean_text("👩‍💻 שלום‏", 100) == "👩‍💻 שלום‏"   # joined emoji and marks stay


def test_a_player_cannot_hide_characters_in_their_tracker_name():
    import initiative_state as T
    state = T.TrackerState()
    state = T.apply(state, T.Actor("player", "p1"), {"type": "add_me", "name": "Gob​lin‮ 1", "hp": 5})
    assert state.entries[0].name == "Goblin 1"
