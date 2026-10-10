"""Initiative tracker rules: state, commands, turn order and what each viewer may see.

No widgets and no network in here. Three pieces, all plain data in / plain data out:

* :class:`TrackerState` - the encounter: the entries in initiative order, whose turn it is, the
  round, and the DM's visibility settings.
* :func:`apply` - the reducer. ``apply(state, actor, command)`` returns the *new* state or raises
  :class:`CommandError`. Every rule lives here, including who may do what, so the DM's local UI and
  a player's remote commands go through exactly the same checks.
* :func:`project` - what one viewer is allowed to see. The host builds this per player and sends
  only that: hidden entries, hidden HP/AC and DM notes never leave the DM's machine.

Turn order. ``entries`` is kept in initiative order (highest first) and never rotates. ``active`` is
the id of the first entry of the unit whose turn it is; a *unit* is one entry, or a run of adjacent
entries sharing a group (they take their turns together). What people see is the same list rotated so
the active unit is on top and the unit that just went is at the bottom (:func:`display_order`).
The round counter goes up when the turn wraps past the last unit.

HP and AC are copies. Entries are snapshots made when a combatant is added; nothing here ever
touches the character sheet or monster they were copied from.
"""

from __future__ import annotations

import copy
import json
import math
import random
import secrets
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import conditions as C

FORMAT_VERSION = 1

KIND_PLAYER, KIND_MONSTER, KIND_CUSTOM, KIND_EVENT = "player", "monster", "custom", "event"
KINDS = (KIND_PLAYER, KIND_MONSTER, KIND_CUSTOM, KIND_EVENT)
HP_MODES = ("number", "bar", "hidden")
AC_MODES = ("shown", "hidden")

MAX_ENTRIES = 100
MAX_ADD_AT_ONCE = 50
MAX_PER_PLAYER = 4
MAX_NAME = 60
MAX_NOTES = 500
MAX_CONDITIONS = 20
HP_LIMIT = 100_000
AC_LIMIT = 100
INIT_MIN, INIT_MAX = -100, 1000


class CommandError(Exception):
    """A command was refused. ``code`` is machine-readable, ``message`` is for people."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Actor:
    role: str                       # "dm" or "player"
    id: str = ""                    # a player's stable client id (what ``Entry.owner`` holds)

    @property
    def is_dm(self) -> bool:
        return self.role == "dm"


DM = Actor("dm")


def new_id() -> str:
    """Random entry id. Not a counter: a player must not be able to count hidden entries."""
    return secrets.token_hex(3)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class Entry:
    id: str
    kind: str
    name: str
    initiative: Optional[int] = None
    init_bonus: int = 0
    hp: int = 0
    hp_max: int = 0
    hp_temp: int = 0
    ac: int = 10
    conditions: List[dict] = field(default_factory=list)
    hidden: bool = False
    group: str = ""
    owner: str = ""                 # the player (client id) who may edit it; "" = DM only
    source: Dict[str, str] = field(default_factory=dict)    # {"type": "character"|"monster", "name": ...}
    notes: str = ""                 # DM-private
    defeated: bool = False
    hp_mode: Optional[str] = None   # per-entry override of the DM's HP visibility setting
    ac_mode: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: copy.deepcopy(v) for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "Entry":
        e = cls(id=str(data.get("id") or new_id()), kind=data.get("kind") if data.get("kind") in KINDS else KIND_CUSTOM,
                name=_text(data.get("name"), MAX_NAME) or "?")
        e.initiative = _opt_int(data.get("initiative"), INIT_MIN, INIT_MAX)
        e.init_bonus = _int(data.get("init_bonus", 0), -50, 50, "init_bonus")
        e.hp_max = _int(data.get("hp_max", data.get("hp", 0)), 0, HP_LIMIT, "hp_max")
        e.hp = min(_int(data.get("hp", e.hp_max), 0, HP_LIMIT, "hp"), e.hp_max)
        e.hp_temp = _int(data.get("hp_temp", 0), 0, HP_LIMIT, "hp_temp")
        e.ac = _int(data.get("ac", 10), 0, AC_LIMIT, "ac")
        e.conditions = _clean_conditions(data.get("conditions"))
        e.hidden = bool(data.get("hidden"))
        e.group = _text(data.get("group"), 20)
        e.owner = _text(data.get("owner"), 64)
        src = data.get("source")
        e.source = {str(k)[:20]: _text(v, MAX_NAME) for k, v in src.items()} if isinstance(src, dict) else {}
        e.notes = _text(data.get("notes"), MAX_NOTES)
        e.defeated = bool(data.get("defeated"))
        e.hp_mode = data.get("hp_mode") if data.get("hp_mode") in HP_MODES else None
        e.ac_mode = data.get("ac_mode") if data.get("ac_mode") in AC_MODES else None
        return e


@dataclass
class Settings:
    monster_hp: str = "number"      # how players see monsters' HP: number / bar / hidden
    monster_ac: str = "shown"       # ... and AC: shown / hidden  (monsters, custom creatures, NPCs)
    player_hp: str = "number"       # how players see each other's HP
    players_can_add: bool = True
    skip_defeated: bool = True      # next turn skips units whose every member is defeated

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: Any) -> "Settings":
        s = cls()
        if isinstance(data, dict):
            s.monster_hp = data.get("monster_hp") if data.get("monster_hp") in HP_MODES else s.monster_hp
            s.monster_ac = data.get("monster_ac") if data.get("monster_ac") in AC_MODES else s.monster_ac
            s.player_hp = data.get("player_hp") if data.get("player_hp") in HP_MODES else s.player_hp
            s.players_can_add = bool(data.get("players_can_add", s.players_can_add))
            s.skip_defeated = bool(data.get("skip_defeated", s.skip_defeated))
        return s


@dataclass
class TrackerState:
    entries: List[Entry] = field(default_factory=list)
    active: str = ""
    round: int = 0
    started: bool = False
    settings: Settings = field(default_factory=Settings)
    group_names: Dict[str, str] = field(default_factory=dict)
    group_seq: int = 0
    rev: int = 0
    last_added: List[str] = field(default_factory=list)      # ids created by the last command (not saved)

    def get(self, entry_id: str) -> Optional[Entry]:
        for e in self.entries:
            if e.id == entry_id:
                return e
        return None

    def to_dict(self) -> dict:
        return {"format": "spellbook-initiative", "version": FORMAT_VERSION, "rev": self.rev,
                "started": self.started, "round": self.round, "active": self.active,
                "settings": self.settings.to_dict(), "group_names": dict(self.group_names),
                "group_seq": self.group_seq, "entries": [e.to_dict() for e in self.entries]}

    @classmethod
    def from_dict(cls, data: Any) -> "TrackerState":
        """Load (and sanitise) saved state. Raises ValueError if it isn't a tracker file."""
        if not isinstance(data, dict) or data.get("format") != "spellbook-initiative":
            raise ValueError("Not an initiative tracker file.")
        if isinstance(data.get("version"), int) and data["version"] > FORMAT_VERSION:
            raise ValueError("This encounter was saved by a newer version of Spellbook.")
        s = cls()
        seen = set()
        for raw in (data.get("entries") or [])[:MAX_ENTRIES]:
            if isinstance(raw, dict):
                try:
                    e = Entry.from_dict(raw)
                except CommandError:
                    continue                       # one bad record must not lose the whole encounter
                if e.id in seen:
                    e.id = new_id()
                seen.add(e.id)
                s.entries.append(e)
        s.settings = Settings.from_dict(data.get("settings"))
        s.started = bool(data.get("started")) and bool(s.entries)
        s.round = _int(data.get("round", 0), 0, 100000, "round") if s.started else 0
        s.active = str(data.get("active") or "") if s.started else ""
        names = data.get("group_names")
        s.group_names = {str(k)[:20]: _text(v, MAX_NAME) for k, v in names.items()} if isinstance(names, dict) else {}
        s.group_seq = _int(data.get("group_seq", 0), 0, 10**6, "group_seq")
        s.rev = _int(data.get("rev", 0), 0, 10**9, "rev")
        _normalize(s)
        return s


# ---------------------------------------------------------------------------
# Small validators
# ---------------------------------------------------------------------------

def _text(value: Any, max_len: int) -> str:
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value if ch >= " " and ch != "\x7f").strip()[:max_len]


def _int(value: Any, lo: int, hi: int, name: str) -> int:
    if isinstance(value, bool):
        raise CommandError("bad_value", f"{name} must be a number.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise CommandError("bad_value", f"{name} must be a number.")
    return max(lo, min(hi, number))


def _opt_int(value: Any, lo: int, hi: int) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return None


def _clean_conditions(raw: Any) -> List[dict]:
    out: List[dict] = []
    for item in (raw if isinstance(raw, list) else [])[:MAX_CONDITIONS]:
        try:
            if isinstance(item, str):
                item = {"name": item}
            cond = C.make_condition(item.get("name", ""), item.get("level"), item.get("rounds"))
        except (ValueError, TypeError, AttributeError):
            continue
        if not any(c["name"].lower() == cond["name"].lower() for c in out):
            out.append(cond)
    return out


# ---------------------------------------------------------------------------
# Turn structure
# ---------------------------------------------------------------------------

def units(state: TrackerState) -> List[List[Entry]]:
    """The turn units, in stored order: one entry each, or a run of adjacent entries in one group."""
    out: List[List[Entry]] = []
    for e in state.entries:
        if out and e.group and out[-1][0].group == e.group:
            out[-1].append(e)
        else:
            out.append([e])
    return out


def _unit_index(unit_list: List[List[Entry]], entry_id: str) -> int:
    for i, unit in enumerate(unit_list):
        if any(e.id == entry_id for e in unit):
            return i
    return -1


def display_order(state: TrackerState) -> List[Entry]:
    """The entries as the table shows them: the active unit first, the unit that just went last."""
    ul = units(state)
    i = _unit_index(ul, state.active) if state.started else -1
    if i <= 0:
        return [e for unit in ul for e in unit]
    return [e for unit in ul[i:] + ul[:i] for e in unit]


def _normalize(s: TrackerState) -> None:
    """Repair invariants after any change: contiguous groups, a valid active pointer."""
    # a group's members must be adjacent; anything stranded is ungrouped
    seen_runs = set()
    prev = ""
    for e in s.entries:
        if e.group and e.group != prev:
            if e.group in seen_runs:
                e.group = ""                       # a second, separate run of the same group id
            else:
                seen_runs.add(e.group)
        prev = e.group
    counts: Dict[str, int] = {}
    for e in s.entries:
        if e.group:
            counts[e.group] = counts.get(e.group, 0) + 1
    for e in s.entries:
        if e.group and counts[e.group] < 2:
            e.group = ""                           # a "group" of one is just an entry
    s.group_names = {g: n for g, n in s.group_names.items() if counts.get(g, 0) >= 2}

    if not s.entries:
        s.active, s.started, s.round = "", False, 0
        return
    if s.started:
        ul = units(s)
        i = _unit_index(ul, s.active)
        s.active = ul[max(i, 0)][0].id             # the first entry of the active unit (or of unit 0)
    else:
        s.active, s.round = "", 0


def _insert_position(s: TrackerState, initiative: Optional[int], skip: Iterable[str] = ()) -> int:
    """Index (in ``s.entries``) of the unit boundary where a unit with this initiative belongs:
    after every unit that is at least as high, before anything lower or unrolled."""
    skip = set(skip)
    pos = 0
    for unit in units(s):
        if all(e.id in skip for e in unit):
            pos += len(unit)
            continue
        first = unit[0].initiative
        if initiative is None:
            pos = pos + len(unit)
            continue
        if first is not None and first >= initiative:
            pos += len(unit)
        else:
            break
    return pos


def _move_unit_to_sorted_slot(s: TrackerState, member_ids: List[str]) -> None:
    ids = set(member_ids)
    moving = [e for e in s.entries if e.id in ids]
    initiative = moving[0].initiative
    rest = TrackerState(entries=[e for e in s.entries if e.id not in ids])
    pos = _insert_position(rest, initiative)
    s.entries = rest.entries[:pos] + moving + rest.entries[pos:]


def _advance(s: TrackerState, step: int) -> None:
    """Move the active pointer one unit forward (+1) or back (-1), skipping defeated units,
    counting the round when it wraps."""
    ul = units(s)
    n = len(ul)
    i = _unit_index(ul, s.active)
    rnd = s.round
    for _ in range(n):
        i += step
        if i >= n:
            i, rnd = 0, rnd + 1
        elif i < 0:
            i, rnd = n - 1, max(1, rnd - 1)
        if not (s.settings.skip_defeated and all(e.defeated for e in ul[i])):
            break
    s.active, s.round = ul[i][0].id, rnd


# ---------------------------------------------------------------------------
# Reducer
# ---------------------------------------------------------------------------

Handler = Callable[..., None]
_HANDLERS: Dict[str, Tuple[Handler, bool]] = {}      # command type -> (handler, dm_only)


def command(name: str, dm_only: bool = True):
    def register(fn: Handler) -> Handler:
        _HANDLERS[name] = (fn, dm_only)
        return fn
    return register


def apply(state: TrackerState, actor: Actor, cmd: dict, *, rng: Optional[random.Random] = None,
          new_id: Callable[[], str] = new_id) -> TrackerState:
    """Return the state after ``cmd`` (the input is untouched). Raises :class:`CommandError`."""
    if not isinstance(cmd, dict) or not isinstance(cmd.get("type"), str):
        raise CommandError("bad_command", "That isn't a command.")
    entry = _HANDLERS.get(cmd["type"])
    if entry is None:
        raise CommandError("unknown_command", f"Unknown command '{cmd['type'][:30]}'.")
    handler, dm_only = entry
    if dm_only and not actor.is_dm:
        raise CommandError("forbidden", "Only the DM can do that.")
    s = copy.deepcopy(state)
    s.last_added = []
    handler(s, actor, cmd, rng or random.SystemRandom(), new_id)
    _normalize(s)
    s.rev = state.rev + 1
    return s


def _find(s: TrackerState, entry_id: Any) -> Entry:
    e = s.get(entry_id) if isinstance(entry_id, str) else None
    if e is None:
        raise CommandError("not_found", "That combatant isn't in the tracker.")
    return e


def _editable(s: TrackerState, actor: Actor, entry_id: Any) -> Entry:
    """An entry the actor may change the stats of: anything for the DM, only their own for a player."""
    e = _find(s, entry_id)
    if not actor.is_dm and (not actor.id or e.owner != actor.id):
        raise CommandError("forbidden", "You can only change your own character.")
    return e


def _set_hp(e: Entry, hp: int) -> None:
    e.hp = max(0, min(e.hp_max, hp))
    if e.hp > 0:
        e.defeated = False
    elif e.kind != KIND_PLAYER and e.kind != KIND_EVENT:
        e.defeated = True               # monsters at 0 are out; a player at 0 is making death saves


def _unique_name(s: TrackerState, base: str, force_number: bool) -> Tuple[str, int]:
    """(name, next number): numbering only when asked for several or the name is already taken."""
    taken = [e.name for e in s.entries]
    exists = base in taken or any(n.startswith(base + " ") and n[len(base) + 1:].isdigit() for n in taken)
    if not exists and not force_number:
        return base, 0
    highest = 1 if base in taken else 0
    for n in taken:
        if n.startswith(base + " ") and n[len(base) + 1:].isdigit():
            highest = max(highest, int(n[len(base) + 1:]))
    return base, highest


@command("add_entry")
def _add_entry(s, actor, cmd, rng, mk_id):
    kind = cmd.get("kind")
    if kind not in KINDS:
        raise CommandError("bad_value", "Unknown kind of combatant.")
    count = _int(cmd.get("count", 1), 1, 10**6, "count")
    if count > MAX_ADD_AT_ONCE:
        raise CommandError("too_many", f"Add at most {MAX_ADD_AT_ONCE} at once.")
    if len(s.entries) + count > MAX_ENTRIES:
        raise CommandError("too_many", f"The tracker is full ({MAX_ENTRIES} entries).")
    name = _text(cmd.get("name"), MAX_NAME)
    if not name:
        raise CommandError("bad_value", "A combatant needs a name.")

    initiative = _opt_int(cmd.get("initiative"), INIT_MIN, INIT_MAX)
    base, highest = (name, 0) if kind in (KIND_PLAYER, KIND_EVENT) else _unique_name(s, name, count > 1)
    new: List[Entry] = []
    for i in range(count):
        e = Entry.from_dict({**cmd, "id": mk_id(), "kind": kind, "name": name, "initiative": initiative,
                             "group": "", "conditions": cmd.get("conditions"), "notes": cmd.get("notes", "")})
        if kind != KIND_PLAYER and (count > 1 or highest):
            e.name = f"{base} {highest + 1 + i}" if highest else f"{base} {i + 1}"
        if kind == KIND_EVENT:
            e.hp = e.hp_max = e.hp_temp = 0
            e.conditions = []
        new.append(e)
    if count > 1 and cmd.get("group"):
        s.group_seq += 1
        gid = f"g{s.group_seq}"
        for e in new:
            e.group = gid
        s.group_names[gid] = _text(cmd.get("group_name"), MAX_NAME) or base
    pos = _insert_position(s, initiative) if initiative is not None else len(s.entries)
    s.entries[pos:pos] = new
    s.last_added = [e.id for e in new]


@command("add_me", dm_only=False)
def _add_me(s, actor, cmd, rng, mk_id):
    if actor.is_dm:
        raise CommandError("bad_command", "The DM adds combatants with add_entry.")
    if not s.settings.players_can_add:
        raise CommandError("forbidden", "The DM has turned off adding yourself.")
    if not actor.id:
        raise CommandError("forbidden", "Unknown player.")
    mine = [e for e in s.entries if e.owner == actor.id]
    if len(mine) >= MAX_PER_PLAYER:
        raise CommandError("too_many", f"You can have up to {MAX_PER_PLAYER} characters in the tracker.")
    if len(s.entries) >= MAX_ENTRIES:
        raise CommandError("too_many", f"The tracker is full ({MAX_ENTRIES} entries).")
    name = _text(cmd.get("name"), MAX_NAME)
    if not name:
        raise CommandError("bad_value", "Your character needs a name.")
    if any(e.owner == actor.id and e.name.lower() == name.lower() for e in s.entries):
        raise CommandError("duplicate", f"{name} is already in the tracker.")
    taken = {e.name.lower() for e in s.entries}
    unique = name
    n = 2
    while unique.lower() in taken:
        unique, n = f"{name} ({n})", n + 1
    e = Entry.from_dict({"id": mk_id(), "kind": KIND_PLAYER, "name": unique, "owner": actor.id,
                         "hp": cmd.get("hp", 0), "hp_max": cmd.get("hp_max", cmd.get("hp", 0)),
                         "hp_temp": cmd.get("hp_temp", 0), "ac": cmd.get("ac", 10),
                         "init_bonus": cmd.get("init_bonus", 0), "source": cmd.get("source"),
                         "initiative": None})
    s.entries.append(e)
    s.last_added = [e.id]


@command("remove")
def _remove(s, actor, cmd, rng, mk_id):
    ids = cmd.get("ids") if isinstance(cmd.get("ids"), list) else [cmd.get("id")]
    for entry_id in ids:
        _find(s, entry_id)
    ul = units(s)
    ui = _unit_index(ul, s.active) if s.started else 0
    gone = set(ids)
    s.entries = [e for e in s.entries if e.id not in gone]
    if s.started and s.entries and s.get(s.active) is None:
        ul = units(s)
        s.active = ul[ui % len(ul)][0].id          # the next unit takes over; no round is counted


@command("clear")
def _clear(s, actor, cmd, rng, mk_id):
    s.entries = []
    s.group_names = {}


@command("set_initiative")
def _set_initiative(s, actor, cmd, rng, mk_id):
    e = _find(s, cmd.get("id"))
    value = _opt_int(cmd.get("value"), INIT_MIN, INIT_MAX)
    members = [m for unit in units(s) for m in unit if any(x.id == e.id for x in unit)] or [e]
    for m in members:
        m.initiative = value
    _move_unit_to_sorted_slot(s, [m.id for m in members])


@command("roll_initiative")
def _roll_initiative(s, actor, cmd, rng, mk_id):
    only_missing = cmd.get("only_missing", True)
    wanted = set(cmd["ids"]) if isinstance(cmd.get("ids"), list) else None
    for unit in units(s):
        if wanted is not None and not any(e.id in wanted for e in unit):
            continue
        if unit[0].kind == KIND_EVENT:
            continue
        if only_missing and unit[0].initiative is not None:
            continue
        value = rng.randint(1, 20) + unit[0].init_bonus       # one roll for a whole group
        for e in unit:
            e.initiative = value
    _sort(s)


def _sort(s: TrackerState) -> None:
    order = {e.id: i for i, e in enumerate(s.entries)}
    ul = units(s)
    ul.sort(key=lambda u: (u[0].initiative is None, -(u[0].initiative or 0), -u[0].init_bonus, order[u[0].id]))
    s.entries = [e for unit in ul for e in unit]


@command("sort")
def _sort_cmd(s, actor, cmd, rng, mk_id):
    _sort(s)


@command("move")
def _move(s, actor, cmd, rng, mk_id):
    """Move the unit holding ``id`` to just before the unit holding ``before`` (None = the end)."""
    _find(s, cmd.get("id"))
    ul = units(s)
    src = _unit_index(ul, cmd["id"])
    before = cmd.get("before")
    if before is None:
        dst = len(ul)
    else:
        _find(s, before)
        dst = _unit_index(ul, before)
    if dst == src or dst == src + 1:
        return
    moving = ul.pop(src)
    if dst > src:
        dst -= 1
    ul.insert(dst, moving)
    s.entries = [e for unit in ul for e in unit]


@command("group")
def _group(s, actor, cmd, rng, mk_id):
    ids = cmd.get("ids")
    if not isinstance(ids, list) or len(set(ids)) < 2:
        raise CommandError("bad_value", "Pick at least two combatants to group.")
    chosen = [_find(s, i) for i in dict.fromkeys(ids)]
    chosen_ids = {e.id for e in chosen}
    touched = {e.group for e in chosen if e.group}
    for e in s.entries:
        if e.group in touched and e.id not in chosen_ids:
            e.group = ""                           # leaving members of an old group behind: dissolve it
    first_index = min(i for i, e in enumerate(s.entries) if e.id in chosen_ids)
    members = [e for e in s.entries if e.id in chosen_ids]
    rest = [e for e in s.entries if e.id not in chosen_ids]
    insert_at = len([e for e in s.entries[:first_index] if e.id not in chosen_ids])
    s.group_seq += 1
    gid = f"g{s.group_seq}"
    initiative = members[0].initiative
    for e in members:
        e.group, e.initiative = gid, initiative
    s.entries = rest[:insert_at] + members + rest[insert_at:]
    s.group_names[gid] = _text(cmd.get("name"), MAX_NAME)


@command("ungroup")
def _ungroup(s, actor, cmd, rng, mk_id):
    e = _find(s, cmd.get("id"))
    if e.group:
        for m in s.entries:
            if m.group == e.group:
                m.group = ""


@command("set_hidden")
def _set_hidden(s, actor, cmd, rng, mk_id):
    ids = cmd.get("ids") if isinstance(cmd.get("ids"), list) else [cmd.get("id")]
    hide = bool(cmd.get("hidden"))
    for entry_id in ids:
        _find(s, entry_id).hidden = hide


_DM_FIELDS = {"name", "init_bonus", "notes", "defeated", "hp_mode", "ac_mode", "owner"}


@command("set_field")
def _set_field(s, actor, cmd, rng, mk_id):
    e = _find(s, cmd.get("id"))
    name, value = cmd.get("field"), cmd.get("value")
    if name not in _DM_FIELDS:
        raise CommandError("bad_value", "That field can't be changed that way.")
    if name == "name":
        text = _text(value, MAX_NAME)
        if not text:
            raise CommandError("bad_value", "A combatant needs a name.")
        e.name = text
    elif name == "init_bonus":
        e.init_bonus = _int(value, -50, 50, "init_bonus")
    elif name == "notes":
        e.notes = _text(value, MAX_NOTES)
    elif name == "defeated":
        e.defeated = bool(value)
    elif name == "hp_mode":
        e.hp_mode = value if value in HP_MODES else None
    elif name == "ac_mode":
        e.ac_mode = value if value in AC_MODES else None
    elif name == "owner":
        e.owner = _text(value, 64)


@command("set_stats", dm_only=False)
def _set_stats(s, actor, cmd, rng, mk_id):
    """HP / max HP / temp HP / AC of one combatant: the DM's, or the player's own."""
    e = _editable(s, actor, cmd.get("id"))
    if e.kind == KIND_EVENT:
        raise CommandError("bad_value", "An event has no stats.")
    if "hp_max" in cmd:
        e.hp_max = _int(cmd["hp_max"], 0, HP_LIMIT, "Max HP")
        e.hp = min(e.hp, e.hp_max)
    if "hp" in cmd:
        _set_hp(e, _int(cmd["hp"], 0, HP_LIMIT, "HP"))
    if "hp_temp" in cmd:
        e.hp_temp = _int(cmd["hp_temp"], 0, HP_LIMIT, "Temp HP")
    if "ac" in cmd:
        e.ac = _int(cmd["ac"], 0, AC_LIMIT, "AC")


@command("hp_delta", dm_only=False)
def _hp_delta(s, actor, cmd, rng, mk_id):
    """Damage (negative) or healing (positive). Damage uses temporary HP first."""
    e = _editable(s, actor, cmd.get("id"))
    if e.kind == KIND_EVENT:
        raise CommandError("bad_value", "An event has no hit points.")
    delta = _int(cmd.get("delta"), -HP_LIMIT, HP_LIMIT, "Amount")
    if delta < 0:
        damage = -delta
        absorbed = min(e.hp_temp, damage)
        e.hp_temp -= absorbed
        _set_hp(e, e.hp - (damage - absorbed))
    else:
        _set_hp(e, e.hp + delta)


@command("add_condition", dm_only=False)
def _add_condition(s, actor, cmd, rng, mk_id):
    e = _editable(s, actor, cmd.get("id"))
    try:
        cond = C.make_condition(cmd.get("name", ""), cmd.get("level"), cmd.get("rounds"))
    except (ValueError, TypeError):
        raise CommandError("bad_value", "A condition needs a name.")
    e.conditions = [c for c in e.conditions if c["name"].lower() != cond["name"].lower()]
    if len(e.conditions) >= MAX_CONDITIONS:
        raise CommandError("too_many", f"That's too many conditions (limit {MAX_CONDITIONS}).")
    e.conditions.append(cond)


@command("remove_condition", dm_only=False)
def _remove_condition(s, actor, cmd, rng, mk_id):
    e = _editable(s, actor, cmd.get("id"))
    name = C.canonical_name(str(cmd.get("name", ""))).lower()
    e.conditions = [c for c in e.conditions if c["name"].lower() != name]


@command("set_conditions", dm_only=False)
def _set_conditions(s, actor, cmd, rng, mk_id):
    _editable(s, actor, cmd.get("id")).conditions = _clean_conditions(cmd.get("conditions"))


@command("set_settings")
def _set_settings(s, actor, cmd, rng, mk_id):
    new = Settings.from_dict({**s.settings.to_dict(), **{k: v for k, v in cmd.items() if k != "type"}})
    s.settings = new


@command("start")
def _start(s, actor, cmd, rng, mk_id):
    if not s.entries:
        raise CommandError("empty", "Add some combatants first.")
    ul = units(s)
    s.started, s.round = True, 1
    first = next((u for u in ul if not (s.settings.skip_defeated and all(e.defeated for e in u))), ul[0])
    s.active = first[0].id


@command("end")
def _end(s, actor, cmd, rng, mk_id):
    s.started, s.round, s.active = False, 0, ""


@command("next_turn")
def _next_turn(s, actor, cmd, rng, mk_id):
    if not s.entries:
        raise CommandError("empty", "Add some combatants first.")
    if not s.started:
        _start(s, actor, cmd, rng, mk_id)
        return
    _advance(s, +1)


@command("prev_turn")
def _prev_turn(s, actor, cmd, rng, mk_id):
    if not s.started:
        raise CommandError("not_started", "Combat hasn't started.")
    _advance(s, -1)


# ---------------------------------------------------------------------------
# What each viewer sees
# ---------------------------------------------------------------------------

def quantize_fraction(hp: int, hp_max: int) -> float:
    """HP as a fraction rounded to tenths for a health bar - never showing 0 for a living
    creature, nor 1.0 for a wounded one, so the bar can't hide or exaggerate an injury."""
    if hp_max <= 0 or hp <= 0:
        return 0.0
    frac = round(hp / hp_max * 10) / 10
    if hp < hp_max:
        frac = min(frac, 0.9)
    return max(frac, 0.1)


def _visible_to(e: Entry, viewer: Actor) -> bool:
    return (not e.hidden) or (e.kind == KIND_PLAYER and bool(viewer.id) and e.owner == viewer.id)


def _player_view(e: Entry, s: TrackerState, viewer: Actor, group_labels: Dict[str, str]) -> dict:
    mine = bool(viewer.id) and e.owner == viewer.id
    out: dict = {"id": e.id, "kind": e.kind, "name": e.name, "initiative": e.initiative,
                 "conditions": copy.deepcopy(e.conditions), "defeated": e.defeated, "mine": mine,
                 "group": group_labels.get(e.group, ""), "hidden": e.hidden and mine}
    if e.kind == KIND_EVENT:
        return out
    hp_mode = e.hp_mode or (s.settings.player_hp if e.kind == KIND_PLAYER else s.settings.monster_hp)
    ac_mode = e.ac_mode or ("shown" if e.kind == KIND_PLAYER else s.settings.monster_ac)
    if mine:
        hp_mode, ac_mode = "number", "shown"
    out["hp_mode"] = hp_mode
    if hp_mode == "number":
        out.update(hp=e.hp, hp_max=e.hp_max, hp_temp=e.hp_temp)
    elif hp_mode == "bar":
        out["hp_frac"] = quantize_fraction(e.hp, e.hp_max)
    if ac_mode == "shown":
        out["ac"] = e.ac
    return out


def project(state: TrackerState, viewer: Actor) -> dict:
    """What ``viewer`` may see, as plain JSON-able data.

    The DM gets everything, in display order. A player gets only visible entries - a hidden player's
    own entry is still visible to *them* - with HP/AC filtered by the DM's settings; DM notes, source
    links, owners and the ids of hidden entries are never included.
    """
    shown = display_order(state)
    if viewer.is_dm:
        return {"role": "dm", "rev": state.rev, "started": state.started, "round": state.round,
                "active": state.active, "settings": state.settings.to_dict(),
                "group_names": dict(state.group_names), "entries": [e.to_dict() for e in shown],
                "order": [e.id for e in state.entries]}          # stored order, for drag-to-reorder

    visible = [e for e in shown if _visible_to(e, viewer)]
    # When the active unit is entirely hidden, the top of the list is the next visible unit, with no
    # "now acting" highlight (so a hidden creature's turn doesn't announce itself).
    active = ""
    if state.started:
        active_unit = next((u for u in units(state) if any(e.id == state.active for e in u)), [])
        active_visible = [e for e in active_unit if _visible_to(e, viewer)]
        if active_visible:
            active = active_visible[0].id
    labels: Dict[str, str] = {}
    for e in visible:
        if e.group and e.group not in labels:
            labels[e.group] = f"g{len(labels) + 1}"
    group_names = {labels[g]: n for g, n in state.group_names.items() if g in labels and n}
    return {"role": "player", "rev": state.rev, "started": state.started, "round": state.round,
            "active": active, "can_add": state.settings.players_can_add,
            "group_names": group_names,
            "entries": [_player_view(e, state, viewer, labels) for e in visible]}


# ---------------------------------------------------------------------------
# History (undo) and saving
# ---------------------------------------------------------------------------

class Tracker:
    """A :class:`TrackerState` plus an undo history and change listeners; the object the app holds."""

    HISTORY = 30

    def __init__(self, state: Optional[TrackerState] = None):
        self.state = state or TrackerState()
        self._history: List[TrackerState] = []
        self._listeners: List[Callable[[TrackerState], None]] = []

    def add_listener(self, fn: Callable[[TrackerState], None]) -> None:
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[TrackerState], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    def dispatch(self, actor: Actor, cmd: dict, **kw) -> TrackerState:
        """Apply a command (or ``{"type": "undo"}``, DM only). Raises :class:`CommandError`."""
        if isinstance(cmd, dict) and cmd.get("type") == "undo":
            if not actor.is_dm:
                raise CommandError("forbidden", "Only the DM can do that.")
            if not self._history:
                raise CommandError("nothing_to_undo", "Nothing to undo.")
            previous = self._history.pop()
            new = copy.deepcopy(previous)
            new.rev = self.state.rev + 1               # revisions only ever go up, so clients accept it
            new.last_added = []
        else:
            new = apply(self.state, actor, cmd, **kw)
            self._history.append(self.state)
            del self._history[:-self.HISTORY]
        self.state = new
        for fn in list(self._listeners):
            fn(new)
        return new


def save_state(state: TrackerState, path: str) -> None:
    from atomic_io import atomic_write_json
    atomic_write_json(path, state.to_dict(), ensure_ascii=False)


def load_state(path: str) -> Optional[TrackerState]:
    """The saved encounter, or None if there is none or it can't be read."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return TrackerState.from_dict(json.load(f))
    except (OSError, ValueError, CommandError):
        return None
