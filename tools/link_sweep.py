"""
Link every mentioned object in the bundled content, in place.

Usage (from the project root):

    python tools/link_sweep.py            # dry run: print a summary only
    python tools/link_sweep.py --report   # ...plus every change, for review
    python tools/link_sweep.py --apply    # rewrite the bundled source files

The linking rules live in object_link_sweep.py. This script feeds them the
bundled sources (tools/spell_data.py and the *.json content files) and writes
the result back by replacing only the exact string literals that changed, so
file formatting, key order and encoding are never disturbed. Running it twice
is a no-op.

Existing installs get the same result from the schema migration in
database.py, which runs the identical sweep over the user's database.
"""

import collections
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import object_link_sweep as sweep  # noqa: E402
from tools.spell_data import get_all_spells  # noqa: E402


def _load_json(name, key):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return json.load(f)[key]


def load_sources():
    return {
        "spells": get_all_spells(),
        "feats": _load_json("feats.json", "feats"),
        "lineages": _load_json("lineages.json", "lineages"),
        "backgrounds": _load_json("backgrounds.json", "backgrounds"),
        "classes": _load_json("classes.json", "classes"),
        "equipment": _load_json("equipment.json", "equipment"),
        "magic_items": _load_json("magic_items.json", "magic_items"),
    }


def build_universe(src):
    return sweep.Universe({
        "spell": [s["name"] for s in src["spells"]],
        "feat": [f["name"] for f in src["feats"]],
        "lineage": [l["name"] for l in src["lineages"]],
        "background": [b["name"] for b in src["backgrounds"]],
        "class": list(src["classes"]),
        "subclass": [sc["name"] for c in src["classes"].values() for sc in c["subclasses"]],
        "equipment": [e["name"] for e in src["equipment"]],
        "magic_item": [m["name"] for m in src["magic_items"]],
    })


def run_sweep(src, uni):
    """Sweep every record in place; return the list of changes."""
    changes: list = []
    for s in src["spells"]:
        sweep.sweep_spell(s, uni, changes)
    for f in src["feats"]:
        sweep.sweep_feat(f, uni, changes)
    for l in src["lineages"]:
        sweep.sweep_lineage(l, uni, changes)
    for b in src["backgrounds"]:
        sweep.sweep_background(b, uni, changes)
    for name, c in src["classes"].items():
        sweep.sweep_class_levels(c.get("levels", {}), name, uni, changes)
        for sc in c.get("subclasses", []):
            sweep.sweep_subclass(sc, uni, changes)
    for e in src["equipment"]:
        sweep.sweep_equipment(e, uni, changes)
    for m in src["magic_items"]:
        sweep.sweep_magic_item(m, uni, changes)
    return changes


# --------------------------------------------------------------------------
# Writing the results back
# --------------------------------------------------------------------------

def _patch(path, replacements, encoders):
    """Replace each old string literal with its new one, exactly once per
    occurrence found by the sweep. `replacements` is {old: (new, expected_count)}."""
    with open(path, encoding="utf-8", newline="") as f:
        raw = f.read()
    for old, (new, expected) in replacements.items():
        for enc in encoders:
            lit_old = enc(old)
            found = raw.count(lit_old)
            if found:
                break
        else:
            raise SystemExit(f"{os.path.basename(path)}: could not find a changed string:\n  {old[:80]!r}")
        if found != expected:
            raise SystemExit(
                f"{os.path.basename(path)}: {found} occurrences of a string the sweep changed "
                f"{expected} time(s) - refusing to guess:\n  {old[:80]!r}")
        raw = raw.replace(lit_old, enc(new))
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(raw)


def _plan(changes, owners):
    """{old: (new, count)} for changes whose owner category is in `owners`."""
    plan: dict = {}
    for c in changes:
        if c["owner"][0] not in owners:
            continue
        old, new = c["old"], c["new"]
        if old in plan and plan[old][0] != new:
            raise SystemExit(f"Same text linked two different ways:\n  {old[:80]!r}")
        plan[old] = (new, plan.get(old, (new, 0))[1] + 1)
    return plan


def write_back(changes):
    json_encoders = (lambda s: json.dumps(s, ensure_ascii=False), lambda s: json.dumps(s, ensure_ascii=True))
    targets = {
        "tools/spell_data.py": ({"spell"}, [repr]),
        "feats.json": ({"feat"}, json_encoders),
        "lineages.json": ({"lineage"}, json_encoders),
        "backgrounds.json": ({"background"}, json_encoders),
        "classes.json": ({"class", "subclass"}, json_encoders),
        "equipment.json": ({"equipment"}, json_encoders),
        "magic_items.json": ({"magic_item"}, json_encoders),
    }
    for rel, (owners, encoders) in targets.items():
        plan = _plan(changes, owners)
        if plan:
            _patch(os.path.join(ROOT, rel), plan, encoders)
            print(f"  {rel}: {sum(n for _, n in plan.values())} fields updated")


def main(argv):
    src = load_sources()
    original = copy.deepcopy(src)
    uni = build_universe(src)
    changes = run_sweep(src, uni)

    # Proof of reversibility: stripping the markup returns the original text.
    for c in changes:
        assert sweep.strip_links(c["new"]) == sweep.strip_links(c["old"]), c["owner"]

    counts = collections.Counter((l["category"], l["rule"]) for c in changes for l in c["links"])
    print(f"{len(changes)} fields changed, {sum(counts.values())} links added")
    for (cat, rule), n in sorted(counts.items()):
        print(f"  {cat:11} {rule:24} {n}")

    if "--report" in argv:
        print()
        for c in changes:
            for l in c["links"]:
                print(f"[{c['owner'][0]}:{c['owner'][1]}] {l['rule']:22} {l['shown']!r} -> "
                      f"{l['category']}:{l['name']}   ...{l['context']}...")

    if "--apply" in argv:
        write_back(changes)
        print("Done. Existing databases pick this up via the schema migration.")
    else:
        print("\n(dry run - pass --apply to write the bundled files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
