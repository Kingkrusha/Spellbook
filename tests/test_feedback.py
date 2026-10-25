"""Send feedback (feedback.py, ui/feedback_dialog.py): what a report holds, that the user's name is taken
out of crash.log, how sending answers, and the window from typing to Sent."""

import io
import json
import os
import time
import urllib.error

import pytest

import feedback as F


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def _opener(answer=b'{"ok": true}', seen=None):
    def open_(request, timeout):
        if seen is not None:
            seen.append(request)
        return _Response(answer)
    return open_


def test_form_ids_are_checked():
    assert not F.is_configured("")
    assert not F.is_configured("../evil")
    assert F.is_configured("xyzabcde")
    assert F.endpoint("xyzabcde") == "https://formspree.io/f/xyzabcde"


def test_the_home_folder_and_user_name_are_taken_out(monkeypatch):
    monkeypatch.setattr(os.path, "expanduser", lambda p: r"C:\Users\Dominic" if p == "~" else p)
    text = (r'File "C:\Users\Dominic\Documents\Spellbook\main.py", line 3' "\n"
            "c:/users/dominic/AppData/x.json\nhello Dominic\nDominica stays")
    out = F.redact(text)
    assert "Dominic\\" not in out and "dominic/" not in out
    assert r'"~\Documents\Spellbook\main.py"' in out
    assert "~/AppData/x.json" in out
    assert "hello <user>" in out
    assert "Dominica stays" in out


def test_crash_log_tail_keeps_the_newest_part_on_whole_lines(tmp_path):
    log = tmp_path / "crash.log"
    log.write_text("".join(f"line {i}\n" for i in range(5000)), encoding="utf-8")
    tail = F.crash_log_tail(str(log), limit=200)
    assert tail.endswith("line 4999")
    assert tail.startswith("line ")
    assert len(tail) <= 200
    assert F.crash_log_tail(str(tmp_path / "missing.log")) == ""


def test_a_report_only_holds_what_was_ticked(tmp_path):
    log = tmp_path / "crash.log"
    log.write_text("Traceback: boom\n", encoding="utf-8")
    bare = F.make_report("Bug report", " It broke ", include_system=False, include_log=False,
                         log_path=str(log))
    fields = bare.fields()
    assert fields["message"] == "It broke"
    assert "crash_log" not in fields and not any(k.startswith("system_") for k in fields)
    assert "email" not in fields

    full = F.make_report("Bug report", "It broke", email="a@b.co", include_system=True, include_log=True,
                         log_path=str(log))
    fields = full.fields()
    assert fields["system_app_version"] == F.__version__
    assert "boom" in fields["crash_log"]
    assert fields["email"] == "a@b.co"
    assert F.__version__ in fields["_subject"]
    text = F.report_text(full)
    assert "It broke" in text and "boom" in text and "Reply to: a@b.co" in text


def test_reports_that_cannot_be_sent_say_why():
    assert F.Report("Bug report", "   ").problem()
    assert F.Report("Bug report", "x" * (F.MAX_MESSAGE + 1)).problem()
    assert F.Report("Bug report", "ok", email="not an email").problem()
    assert F.Report("Bug report", "ok", email="").problem() == ""


def test_send_posts_json_to_the_form():
    seen = []
    F.send(F.Report("Idea or feedback", "More dragons"), form_id="abcd1234", opener=_opener(seen=seen))
    request = seen[0]
    assert request.full_url == "https://formspree.io/f/abcd1234"
    assert request.get_method() == "POST"
    assert json.loads(request.data)["message"] == "More dragons"


def test_send_explains_failures():
    with pytest.raises(F.SendError, match="isn't set up"):
        F.send(F.Report("Bug report", "x"), form_id="")
    with pytest.raises(F.SendError, match="Write a few words"):
        F.send(F.Report("Bug report", ""), form_id="abcd1234", opener=_opener())

    def offline(request, timeout):
        raise urllib.error.URLError("no network")
    with pytest.raises(F.SendError, match="internet"):
        F.send(F.Report("Bug report", "x"), form_id="abcd1234", opener=offline)

    def busy(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 429, "busy", {}, io.BytesIO(b"{}"))
    with pytest.raises(F.SendError, match="try again later"):
        F.send(F.Report("Bug report", "x"), form_id="abcd1234", opener=busy)

    with pytest.raises(F.SendError, match="bad field"):
        F.send(F.Report("Bug report", "x"), form_id="abcd1234",
               opener=_opener(b'{"errors": [{"message": "bad field"}]}'))


def test_the_shortcut_is_shift_f1_and_can_be_bound():
    import hotkeys
    action = hotkeys.ACTIONS_BY_ID["help.feedback"]
    assert action.default == "Shift+F1"
    assert hotkeys.normalize(action.default) == "Shift+F1"
    assert hotkeys.tk_sequences(action.default)


# ---------------------------------------------------------------------------------------------- window

def _pump(root, seconds=0.0):
    end = time.monotonic() + seconds
    while True:
        root.update()
        if time.monotonic() >= end:
            return
        time.sleep(0.02)


def test_the_window_sends_and_clears_the_message(tk_root):
    from ui.feedback_dialog import FeedbackDialog
    sent = []
    dialog = FeedbackDialog(tk_root, form_id="abcd1234", sender=lambda report, form_id: sent.append(report))
    try:
        _pump(tk_root)
        dialog._send()
        assert "Write a few words" in dialog.status.cget("text")
        dialog.message.insert("1.0", "The map won't load")
        dialog.log_var.set(True)
        dialog._toggle_preview()
        assert "The map won't load" in dialog.preview.get("1.0", "end")
        dialog._send()
        for _ in range(50):
            _pump(tk_root, 0.05)
            if not dialog._sending:
                break
        assert sent and sent[0].message == "The map won't load" and sent[0].include_log
        assert "Thank you" in dialog.status.cget("text")
        assert dialog.message.get("1.0", "end-1c") == ""
        assert dialog.log_var.get() is False
    finally:
        dialog.close()
        _pump(tk_root)


def test_without_a_form_send_is_off_and_copy_still_works(tk_root):
    from ui.feedback_dialog import FeedbackDialog
    dialog = FeedbackDialog(tk_root, form_id="")
    try:
        _pump(tk_root)
        assert dialog.send_btn.cget("state") == "disabled"
        dialog.message.insert("1.0", "Idea: owlbears")
        dialog._copy()
        assert "Idea: owlbears" in tk_root.clipboard_get()
    finally:
        dialog.close()
        _pump(tk_root)


def test_a_failed_send_keeps_the_message(tk_root):
    from ui.feedback_dialog import FeedbackDialog

    def fail(report, form_id):
        raise F.SendError("Couldn't reach the feedback service.")
    dialog = FeedbackDialog(tk_root, form_id="abcd1234", sender=fail)
    try:
        dialog.message.insert("1.0", "Keep me")
        dialog._send()
        for _ in range(50):
            _pump(tk_root, 0.05)
            if not dialog._sending:
                break
        assert "Couldn't reach" in dialog.status.cget("text")
        assert dialog.message.get("1.0", "end-1c") == "Keep me"
        assert dialog.send_btn.cget("state") == "normal"
    finally:
        dialog.close()
        _pump(tk_root)
