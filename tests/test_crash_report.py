"""Crash reports (crash_report.py): finding runs that didn't close, and what is sent about them."""

import json
import os
import subprocess
import sys
import textwrap

import app_log
import crash_report as C


def _note(folder, pid, started="2026-11-15 05:00:00", version="1.10.0"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{pid}.json"), "w", encoding="utf-8") as f:
        json.dump({"pid": pid, "started": started, "version": version}, f)


def _dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


def test_a_run_that_did_not_close_is_found_and_this_run_is_noted(tmp_path):
    folder = str(tmp_path / "runs")
    dead = _dead_pid()
    _note(folder, dead)
    _note(folder, os.getppid())                 # (still running: another copy of the app, say)
    crashed = C.begin_run("2026-11-15 06:00:00", "1.10.0", folder=folder)
    assert [r.pid for r in crashed] == [dead]
    assert os.path.exists(os.path.join(folder, f"{os.getpid()}.json"))
    C.forget(crashed[0])
    C.end_run(folder=folder)
    assert sorted(os.listdir(folder)) == [f"{os.getppid()}.json"]


def test_broken_or_very_old_notes_are_thrown_away(tmp_path):
    folder = str(tmp_path / "runs")
    os.makedirs(folder)
    (tmp_path / "runs" / "junk.json").write_text("{not json")
    dead = _dead_pid()
    _note(folder, dead)
    old = os.path.join(folder, f"{dead}.json")
    os.utime(old, (0, 0))
    assert C.begin_run("2026-11-15 06:00:00", folder=folder) == []
    assert os.listdir(folder) == [f"{os.getpid()}.json"]


def _logs(tmp_path, crash_body, run):
    crash = tmp_path / "crash.log"
    crash.write_text("\n" + app_log.start_line("2026-11-14 20:00:00", 11) + "\nolder run\n"
                     + "\n" + app_log.start_line(run.started, run.pid) + "\n" + crash_body
                     + "\n" + app_log.start_line("2026-11-15 06:00:00", 99) + "\nthe run after\n", encoding="utf-8")
    app = tmp_path / "spellbook.log"
    app.write_text("\n" + app_log.start_line(run.started, run.pid) + "\nSession error: boom\n", encoding="utf-8")
    return str(crash), str(app)


def test_only_a_crash_or_a_freeze_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(os.path, "expanduser", lambda p: "/home/aria" if p == "~" else p)
    run = C.Run(1234, "2026-11-15 05:00:00", "1.10.0")
    crash, app = _logs(tmp_path, "Fatal Python error: Segmentation fault\n\nThread 0x01 (most recent call first):\n"
                                 '  File "/home/aria/Spellbook/ui/tabletop_view.py", line 9 in draw\n', run)
    report = C.report_for(run, crash, app)
    assert report is not None and report.kind == "Crash report" and report.include_log
    assert "closed unexpectedly" in report.message and "Segmentation fault" in report.message
    assert "tabletop_view.py" in report.log and "older run" not in report.log and "the run after" not in report.log
    assert "/home/aria" not in report.log and "~/Spellbook" in report.log
    assert "Session error: boom" in report.app_log
    fields = report.fields()
    assert fields["crash_log"] == report.log and fields["app_log"] == report.app_log

    crash, app = _logs(tmp_path, "Timeout (0:00:30)!\nThread 0x01 (most recent call first):\n  File x\n", run)
    assert "stopped responding" in C.report_for(run, crash, app).message

    crash, app = _logs(tmp_path, "--- error in a UI callback 2026-11-15 05:10:00 ---\nKeyError: 'x'\n", run)
    assert C.report_for(run, crash, app) is None            # (the app kept going after that; e.g. a power cut)
    assert C.report_for(C.Run(77, "2026-01-01 00:00:00"), crash, app) is None     # (no part of the log)


def test_a_long_log_keeps_its_start_and_its_end():
    text = "first line\n" + "x" * 50_000 + "\nlast line"
    clipped = C._clip(text, 2000)
    assert clipped.startswith("first line") and clipped.endswith("last line") and len(clipped) < 2200


def test_a_real_crash_leaves_what_the_report_needs(tmp_path):
    """A child process sets up logging the way main.py does and then dies natively."""
    script = textwrap.dedent(f"""
        import faulthandler, os, sys
        sys.path.insert(0, {os.getcwd()!r})
        import app_log
        handle = open({str(tmp_path / 'crash.log')!r}, "a", encoding="utf-8", buffering=1)
        handle.write("\\n" + app_log.start_line("2026-11-15 05:00:00", os.getpid()) + "\\n")
        faulthandler.enable(file=handle, all_threads=True)
        print(os.getpid(), flush=True)
        faulthandler._sigsegv()
    """)
    p = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert p.returncode != 0
    pid = int(p.stdout.split()[0])
    run = C.Run(pid, "2026-11-15 05:00:00", "1.10.0")
    report = C.report_for(run, str(tmp_path / "crash.log"), str(tmp_path / "none.log"))
    assert report is not None and "Fatal Python error" in report.log
