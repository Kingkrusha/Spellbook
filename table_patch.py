"""
Sending a player only what changed on the tabletop.

The host used to send every player their whole view of the map after each change: every token, drawing, fog
step and sight polygon, though a move changes one token and its sight. ``diff_view(old, new)`` lists the changes
from the view a player has to the new one, and ``apply_ops(view, ops)`` makes them on the player's side (the
browser page has the same in lan/web/tabletop.js). The host sends the list instead of the view when it is
clearly smaller; each message carries a number, and a player whose view isn't the one the list starts from asks
for the whole view again ("table_sync").

An operation is a list:

* ``["set", path, value]`` - the value at ``path`` (a list of keys from the top of the view) is now ``value``
* ``["del", path]`` - that key is gone
* ``["append", path, items]`` - ``items`` were added at the end of the list at ``path`` (fog steps)
* ``["items", path, put, gone, order]`` - in the list of records with an ``"id"`` at ``path`` (tokens,
  drawings, areas, doors): ``put`` are new or changed records, ``gone`` the ids taken away, and ``order``
  the ids in their new order when that changed (otherwise ``None``)

Pure logic, no Tk and no network.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

MAX_DEPTH = 3        # how far into nested dicts changes are looked for (the view -> scene -> fog)
MAX_OPS = 2000


def _id_list(value) -> bool:
    """A list of records each with a distinct string id."""
    if not isinstance(value, list) or not value:
        return False
    ids = [v.get("id") if isinstance(v, dict) else None for v in value]
    return all(isinstance(i, str) for i in ids) and len(set(ids)) == len(ids)


def _items_op(path, old: list, new: list):
    before = {r["id"]: r for r in old}
    put = [r for r in new if before.get(r["id"]) != r]
    new_ids = [r["id"] for r in new]
    kept = set(new_ids)
    gone = [r["id"] for r in old if r["id"] not in kept]
    # the order a player ends up with by keeping what stays where it was and adding new records at the end
    added = [r["id"] for r in put if r["id"] not in before]
    natural = [i for i in (r["id"] for r in old) if i in kept] + added
    order = None if natural == new_ids else new_ids
    if not put and not gone and order is None:
        return None
    return ["items", path, put, gone, order]


def _diff(old, new, path: list, ops: list, depth: int) -> None:
    for key, value in new.items():
        here = path + [key]
        if key not in old:
            ops.append(["set", here, value])
            continue
        before = old[key]
        if before == value:
            continue
        if isinstance(before, dict) and isinstance(value, dict) and depth < MAX_DEPTH:
            _diff(before, value, here, ops, depth + 1)
        elif isinstance(before, list) and isinstance(value, list):
            if _id_list(before) and _id_list(value):
                op = _items_op(here, before, value)
                if op is not None:
                    ops.append(op)
            elif len(value) > len(before) and value[:len(before)] == before:
                ops.append(["append", here, value[len(before):]])
            else:
                ops.append(["set", here, value])
        else:
            ops.append(["set", here, value])
    for key in old:
        if key not in new:
            ops.append(["del", path + [key]])


def diff_view(old: Optional[dict], new: dict) -> Optional[List[list]]:
    """The operations that turn ``old`` into ``new`` (both plain JSON-like dicts), or None when there's no use
    in a list: no old view, or a different map (then the whole view goes)."""
    if not isinstance(old, dict) or not isinstance(new, dict):
        return None
    old_scene, new_scene = old.get("scene"), new.get("scene")
    if not isinstance(old_scene, dict) or not isinstance(new_scene, dict) or old_scene.get("id") != new_scene.get("id"):
        return None
    ops: List[list] = []
    _diff(old, new, [], ops, 0)
    return ops


def _parent(view: dict, path) -> Optional[dict]:
    node: Any = view
    for key in path[:-1]:
        if not isinstance(node, dict) or not isinstance(node.get(key), dict):
            return None
        node = node[key]
    return node if isinstance(node, dict) else None


def apply_ops(view: dict, ops) -> bool:
    """Make the changes in ``view`` (in place). False when they don't fit it (then ask for the whole view)."""
    if not isinstance(view, dict) or not isinstance(ops, list) or len(ops) > MAX_OPS:
        return False
    for op in ops:
        if not isinstance(op, list) or len(op) < 2 or not isinstance(op[1], list) or not op[1]:
            return False
        kind, path = op[0], op[1]
        if not all(isinstance(k, str) for k in path):
            return False
        parent = _parent(view, path)
        if parent is None:
            return False
        key = path[-1]
        if kind == "set" and len(op) == 3:
            parent[key] = op[2]
        elif kind == "del":
            parent.pop(key, None)
        elif kind == "append" and len(op) == 3 and isinstance(op[2], list) and isinstance(parent.get(key), list):
            parent[key].extend(op[2])
        elif kind == "items" and len(op) == 5 and isinstance(parent.get(key), list):
            put, gone, order = op[2], op[3], op[4]
            if not isinstance(put, list) or not isinstance(gone, list) or not (order is None or isinstance(order, list)):
                return False
            if not all(isinstance(r, dict) and isinstance(r.get("id"), str) for r in put):
                return False
            records = [r for r in parent[key] if isinstance(r, dict)]
            gone_ids = set(gone)
            index = {r.get("id"): i for i, r in enumerate(records)}
            for r in put:
                if r["id"] in index:
                    records[index[r["id"]]] = r
                else:
                    index[r["id"]] = len(records)
                    records.append(r)
            records = [r for r in records if r.get("id") not in gone_ids]
            if order is not None:
                by_id = {r.get("id"): r for r in records}
                if set(order) != set(by_id) or len(order) != len(by_id):
                    return False
                records = [by_id[i] for i in order]
            parent[key] = records
        else:
            return False
    return True


def worth_it(ops: List[list], whole_size: int) -> bool:
    """Whether sending the list beats sending the whole view (a list that is most of the view isn't)."""
    return len(json.dumps(ops, separators=(",", ":"))) < whole_size * 0.6
