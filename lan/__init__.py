"""LAN sessions: an encrypted host-relay (star) network for a game table.

One player (the DM) hosts; everyone else joins. Nothing here touches widgets or the
app's data managers - the network runs on its own thread and hands the UI plain
event dicts through a queue (see :mod:`lan.runtime`). The design is in
``docs/lan-and-tracker-plan.md``.
"""

from lan.protocol import (  # noqa: F401  (public surface)
    DEFAULT_PORT, PROTOCOL_VERSION, Invite, LanError, ProtocolError,
)
