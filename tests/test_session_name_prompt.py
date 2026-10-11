"""The Session page asks for a name every time you host or join - it never guesses one."""

import socket
import time

import pytest

from lan.service import HOSTING, JOINING, NONE, SessionService
from ui.session_widgets import NameDialog


def pump(root, seconds=0.1):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeSettings:
    """Just enough of SettingsManager for the session service."""

    class settings:
        lan_player_name = ""
        lan_port = 5150
        lan_require_approval = True
        lan_discovery = False
        lan_client_id = ""
        lan_last_invite = ""

    def update(self, **kw):
        for k, v in kw.items():
            setattr(self.settings, k, v)
        return True


@pytest.fixture()
def page(tk_root):
    from ui.session_view import SessionView
    FakeSettings.settings.lan_player_name = ""        # the settings object is shared class state
    svc = SessionService(FakeSettings())
    svc.scan = lambda *a, **k: None                  # no network scan in a unit test
    view = SessionView(tk_root, svc)
    view.pack(fill="both", expand=True)
    pump(tk_root, 0.1)
    yield tk_root, svc, view
    try:
        view.destroy()
    except Exception:
        pass
    svc.shutdown()


def dialogs(root):
    return [w for w in root.winfo_children() if isinstance(w, NameDialog)]


def test_the_page_has_no_name_box_filled_from_the_computer(page):
    root, svc, view = page
    assert not hasattr(view, "_name_entry")
    assert svc.default_name() == ""


def test_hosting_asks_for_a_name_first(page):
    root, svc, view = page
    view._port_entry.delete(0, "end")
    view._port_entry.insert(0, str(free_port()))
    view._discover_var.set(False)
    view._on_start_host()
    pump(root, 0.2)
    assert svc.role == NONE                                   # nothing starts until a name is given
    (dlg,) = dialogs(root)
    assert dlg.entry.get() == ""                              # first time: nothing is pre-filled

    dlg._submit()                                             # blank: stays open with a message
    assert dialogs(root) and "name" in dlg.error.cget("text").lower()
    assert svc.role == NONE

    dlg.entry.insert(0, "  Thorin   Oakenshield ")
    dlg._submit()
    pump(root, 0.2)
    assert svc.role == HOSTING and svc.my_name == "Thorin Oakenshield"
    assert FakeSettings.settings.lan_player_name == "Thorin Oakenshield"
    assert not dialogs(root)


def test_cancelling_the_prompt_does_nothing(page):
    root, svc, view = page
    view._invite_entry.insert(0, "127.0.0.1:1#" + "A" * 26)
    view._on_join()
    pump(root, 0.2)
    (dlg,) = dialogs(root)
    dlg.destroy()
    pump(root, 0.1)
    assert svc.role == NONE


def test_joining_asks_for_a_name_and_remembers_it_for_next_time(page):
    root, svc, view = page
    view._invite_entry.delete(0, "end")
    view._invite_entry.insert(0, "127.0.0.1:1#" + "A" * 26)
    view._on_join()
    pump(root, 0.2)
    (dlg,) = dialogs(root)
    dlg.entry.insert(0, "Mira")
    dlg._submit()
    pump(root, 0.2)
    assert svc.my_name == "Mira" and svc.role in (JOINING, NONE)   # the unreachable host may fail at once
    assert FakeSettings.settings.lan_player_name == "Mira"
    svc.cancel_join()

    # the next prompt starts from what was typed, so a returning player just presses Enter
    view._on_join()
    pump(root, 0.2)
    (dlg2,) = dialogs(root)
    assert dlg2.entry.get() == "Mira"
    dlg2.destroy()
