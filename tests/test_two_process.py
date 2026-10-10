"""Two separate Spellbook processes, each with its own data folder, exchanging a character over a
real encrypted TCP connection - the nearest thing to two players' computers that one machine allows."""

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEER = os.path.join(ROOT, "tests", "helpers", "lan_peer.py")


def spawn(role_args, data_dir):
    env = dict(os.environ, SPELLBOOK_DATA_DIR=str(data_dir), PYTHONIOENCODING="utf-8")
    return subprocess.Popen([sys.executable, PEER, *role_args], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def last_json(text):
    lines = [l for l in text.splitlines() if l.startswith("{")]
    assert lines, f"no JSON output in: {text!r}"
    return json.loads(lines[-1])


def test_character_travels_between_two_installs(tmp_path):
    for name in ("host", "client"):
        (tmp_path / name).mkdir()
        shutil.copy(os.path.join(ROOT, "spellbook.db"), tmp_path / name / "spellbook.db")

    host = spawn(["host"], tmp_path / "host")
    client = None
    try:
        first = None
        for _ in range(200):                      # skip any migration chatter printed before our line
            line = host.stdout.readline()
            if line.startswith("{"):
                first = json.loads(line)
                break
            assert line or host.poll() is None, host.stderr.read()
        assert first is not None
        assert first["port"] and len(first["fp"]) == 26

        client = spawn(["client", str(first["port"]), first["fp"]], tmp_path / "client")
        c_out, c_err = client.communicate(timeout=90)
        assert client.returncode == 0, c_err
        h_out, h_err = host.communicate(timeout=60)
        assert host.returncode == 0, h_err
    finally:
        for proc in (host, client):
            if proc is not None and proc.poll() is None:
                proc.kill()

    got = last_json(c_out)
    assert got["sender"] == "The DM"
    assert got["characters"] == ["Proc Hero"]                 # the client had no characters of its own
    assert got["gold"] == 321                                # the sheet came across intact
    assert got["feat_installed"] is True and got["feat_official"] is False
    assert got["new_homebrew"] == 1                          # the feat the character depends on

    sent = last_json(h_out)
    assert sent["status"] == "imported"                      # and the sender was told

    # the character really was written into the *client's own* data folder
    client_chars = json.load(open(tmp_path / "client" / "characters.json", encoding="utf-8"))
    assert [c["name"] for c in client_chars["characters"]] == ["Proc Hero"]
