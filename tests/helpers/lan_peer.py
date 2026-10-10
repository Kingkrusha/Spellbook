"""One side of tests/test_two_process.py: runs as its own process with its own data folder.

    lan_peer.py host                       -> prints {"port":..., "fp":...}, waits for a player, sends a
                                              character, prints how it went
    lan_peer.py client <port> <fingerprint> -> joins, receives, adds the character, prints the result

SPELLBOOK_DATA_DIR (set by the test) keeps each process's characters, homebrew and database apart,
exactly as two players' installs are.
"""

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def say(**fields):
    print(json.dumps(fields), flush=True)


def pump_until(service, cond, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        service.pump()
        if cond():
            return True
        time.sleep(0.05)
    return False


def managers():
    from character_manager import CharacterManager
    from spell_manager import SpellManager
    from transfer import Managers
    from ui.character_sheet_view import get_sheet_manager
    sm = SpellManager()
    sm.load_spells()
    cm = CharacterManager()
    cm.load_characters()
    return Managers(cm, get_sheet_manager(), sm)


def host():
    from character import CharacterSpellList, ClassLevel
    from character_sheet import CharacterSheet
    from feat import Feat, get_feat_manager
    from lan.service import SessionService
    from spell import CharacterClass
    import transfer

    m = managers()
    feat = Feat.from_dict({"name": "Two Process Feat", "description": "Only the sender has this."})
    feat.is_custom, feat.is_official = True, False
    get_feat_manager().add_feat(feat)
    m.character_manager.add_character(CharacterSpellList(
        name="Proc Hero", classes=[ClassLevel(CharacterClass.FIGHTER, 3)], feats=["Two Process Feat"]))
    sheet = CharacterSheet(character_name="Proc Hero")
    sheet.gold = 321
    m.sheet_manager.update_sheet("Proc Hero", sheet)

    svc = SessionService()
    port = svc.start_host("The DM", require_approval=False, port=0, bind="127.0.0.1", discoverable=False)
    say(port=port, fp=svc._host.fingerprint)
    if not pump_until(svc, lambda: len(svc.peers) >= 2):
        say(error="nobody joined")
        return 2
    other = next(p["peer_id"] for p in svc.peers if p["peer_id"] != svc.my_id)
    payload = transfer.build_character_payload(["Proc Hero"], m.character_manager, m.sheet_manager,
                                               m.spell_manager)
    xfer = svc.send_transfer(other, payload, "Proc Hero")
    ok = pump_until(svc, lambda: svc.outbox[xfer]["status"] in ("imported", "declined", "failed"), 30)
    say(status=svc.outbox[xfer]["status"] if ok else "timeout")
    svc.shutdown()
    return 0


def client(port: int, fp: str):
    from lan import protocol as P
    from lan.service import CLIENT, SessionService
    import transfer

    m = managers()
    svc = SessionService()
    svc.join(P.Invite("127.0.0.1", port, fp).encode(), "Player Two")
    if not pump_until(svc, lambda: svc.role == CLIENT):
        say(error="could not join")
        return 2
    if not pump_until(svc, lambda: svc.inbox, 30):
        say(error="nothing arrived")
        return 2
    item = svc.inbox[0]
    parsed = transfer.parse_payload(item["payload"])
    plan = transfer.plan_transfer(parsed, m)
    result = transfer.apply_transfer(parsed, m)
    svc.finish_item(item["item_id"], "imported")
    from feat import get_feat_manager
    sheet = m.sheet_manager.get_sheet("Proc Hero")
    say(sender=item["name"], characters=sorted(c.name for c in m.character_manager.characters),
        gold=sheet.gold if sheet else None,
        feat_installed=get_feat_manager().get_feat("Two Process Feat") is not None,
        feat_official=bool(get_feat_manager().get_feat("Two Process Feat").is_official)
        if get_feat_manager().get_feat("Two Process Feat") else None,
        new_homebrew=len(plan.content.new) if plan.content else 0, lines=result.lines())
    time.sleep(1.0)               # let the reply reach the host before leaving
    svc.shutdown()
    return 0


if __name__ == "__main__":
    role = sys.argv[1]
    sys.exit(host() if role == "host" else client(int(sys.argv[2]), sys.argv[3]))
