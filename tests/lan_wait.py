"""What a LAN test prints when a wait runs out: where each session got to, and what every thread was
doing. A join on a busy CI runner very occasionally never finishes; this is how we find out why."""

import faulthandler
import sys


def stall_report(services) -> str:
    lines = []
    for i, s in enumerate(services):
        client = getattr(s, "_client", None)
        lines.append(f"session {i}: role={s.role!r} last_end_reason={s.last_end_reason!r} "
                     f"peers={len(s.peers)} client_connected={getattr(client, '_connected', None)}")
    sys.stderr.write("\n".join(["LAN wait ran out:"] + lines) + "\n")
    sys.stderr.flush()
    try:
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
    except Exception:
        pass
    return "\n".join(lines)
