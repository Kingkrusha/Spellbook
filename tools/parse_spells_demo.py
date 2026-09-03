"""
Demo harness for the rule-based spell text importer.

Usage
-----
    python tools/parse_spells_demo.py                     # run the built-in samples
    python tools/parse_spells_demo.py path/to/notes.txt   # parse a file
    type notes.txt | python tools/parse_spells_demo.py -   # parse stdin

For each detected spell it prints the parsed fields with a confidence flag and,
when the app package is importable, the pipe-delimited line that Spellbook's
importer already understands.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from text_import.spell_parser import parse_spell_text, split_blocks, to_spell  # noqa: E402
from text_import.base import Confidence  # noqa: E402


FLAG = {
    Confidence.HIGH: "  ",
    Confidence.MEDIUM: "? ",
    Confidence.LOW: "! ",
    Confidence.MISSING: "X ",
}

FIELD_ORDER = [
    "name", "level", "school", "casting_time", "ritual", "range",
    "components", "duration", "concentration", "classes", "source",
    "tags", "description",
]


SAMPLES = r"""
Fire Bolt
Evocation Cantrip
Casting Time: 1 Action
Range: 120 feet
Components: V, S
Duration: Instantaneous
Classes: Sorcerer, Wizard
You hurl a mote of fire at a creature or an object within range. Make a ranged
spell attack against the target. On a hit, the target takes 1d10 Fire damage.

Cantrip Upgrade. The damage increases by 1d10 when you reach levels 5, 11, and 17.


Shield
1st-level abjuration
Reaction, which you take when you are hit by an attack or targeted by magic missile
Self
V, S
Instantaneous
Wizard, Sorcerer
An invisible barrier of magical force appears and protects you. Until the start of
your next turn, you have a +5 bonus to AC, including against the triggering attack,
and you take no damage from magic missile.


Aid
Level 2 Abjuration
1 action  Range: 30 feet  V, S, M (a strip of white cloth)  Duration: 8 hours
Cleric, Paladin, Ranger
Source: Player's Handbook (2024)
Your spell bolsters your allies with toughness and resolve. Choose up to three
creatures within range. Each target's hit point maximum and current hit points
increase by 5 for the duration.


BLESS
enchantment, 1st level
Casting time: 1 action (ritual)
range 30 ft
comp: V, S, M (a sprinkling of holy water)
dur: Concentration, up to 1 minute
You bless up to three creatures of your choice within range. Whenever a target
makes an attack roll or a saving throw before the spell ends, the target rolls a
d4 and adds the number rolled to the attack roll or save.
"""


def main() -> None:
    args = sys.argv[1:]
    if not args:
        text = SAMPLES
        print("(no file given - parsing built-in samples)\n")
    elif args[0] == "-":
        text = sys.stdin.read()
    else:
        with open(args[0], "r", encoding="utf-8") as fh:
            text = fh.read()

    blocks = split_blocks(text)
    parsed = parse_spell_text(text)
    print(f"Detected {len(blocks)} spell block(s).\n" + "=" * 72)

    for idx, obj in enumerate(parsed, 1):
        print(f"\n[{idx}] {obj.get('name') or '(unnamed)'}")
        print("-" * 72)
        for name in FIELD_ORDER:
            fr = obj.fields.get(name)
            if fr is None:
                continue
            val = fr.value
            if name == "description" and isinstance(val, str):
                val = (val[:100] + "...") if len(val) > 100 else val
                val = val.replace("\\", "  ¶ ")
            note = f"   <- {fr.note}" if fr.note else ""
            print(f" {FLAG[fr.confidence]}{name:<14}: {val}{note}")

        review = obj.needs_review()
        if review:
            print(f"\n     REVIEW NEEDED: {', '.join(review)}")

        try:
            spell = to_spell(obj)
            print("\n     pipe line:")
            print("     " + spell.to_file_line())
        except Exception as exc:  # pragma: no cover
            print(f"\n     (could not build Spell object: {exc})")

    print("\n" + "=" * 72)
    print("Legend:  (blank)=high confidence   ?=heuristic guess   "
          "!=weak guess   X=missing")


if __name__ == "__main__":
    main()
