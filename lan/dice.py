"""Dice for the session chat: ``/roll 2d6+3``, ``/roll d20+5 adv Perception``.

Pure functions, no network or UI. The host rolls (so nobody can fudge a die) using the
operating system's random source and broadcasts the result.

Syntax
------
* Terms are added or subtracted: ``1d20+1d4+5``, ``2d8-1``. A bare ``d20`` means ``1d20``;
  ``d%`` is ``d100``.
* ``kh`` / ``kl`` keep the highest / lowest dice: ``4d6kh3``, ``2d20kl1`` (``k3`` = ``kh3``).
* After the expression, ``adv`` or ``dis`` (also ``advantage`` / ``disadvantage``) turns the first
  single d20 into 2d20 keeping the higher / lower.
* Anything after that is a label shown with the roll: ``/roll 1d20+5 adv Stealth check``.

Limits keep a hostile or careless message cheap: at most 100 dice per term, 1000 sides, 20 terms.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

MAX_DICE = 100
MAX_SIDES = 1000
MAX_TERMS = 20
MAX_LABEL = 80

_rng = random.SystemRandom()

_TERM_RE = re.compile(r"^(?:(?P<count>\d*)d(?P<sides>\d+|%)(?:(?P<keep>k[hl]?)(?P<keepn>\d+))?|(?P<const>\d+))$",
                      re.IGNORECASE)
_EXPR_CHARS = re.compile(r"^[0-9dDkKhHlL%+\-]+$")


class DiceError(ValueError):
    """The roll could not be understood (message is user-readable)."""


@dataclass
class Term:
    sign: int                       # +1 or -1
    count: int = 0                  # dice; 0 for a constant
    sides: int = 0
    keep: str = ""                  # "", "h" or "l"
    keep_n: int = 0
    value: int = 0                  # a constant's value
    rolls: List[int] = field(default_factory=list)
    kept: List[bool] = field(default_factory=list)

    @property
    def is_dice(self) -> bool:
        return self.count > 0

    @property
    def subtotal(self) -> int:
        if not self.is_dice:
            return self.sign * self.value
        return self.sign * sum(r for r, k in zip(self.rolls, self.kept) if k)

    def text(self) -> str:
        if not self.is_dice:
            return str(self.value)
        keep = f"k{self.keep}{self.keep_n}" if self.keep else ""
        return f"{self.count}d{self.sides}{keep}"


@dataclass
class Roll:
    terms: List[Term]
    label: str = ""
    mode: str = ""                  # "", "adv" or "dis"

    @property
    def total(self) -> int:
        return sum(t.subtotal for t in self.terms)

    @property
    def expression(self) -> str:
        out = ""
        for i, t in enumerate(self.terms):
            out += ("-" if t.sign < 0 else ("+" if i else "")) + t.text()
        return out + (f" {self.mode}" if self.mode else "")

    @property
    def crit(self) -> str:
        """``nat20`` / ``nat1`` when the first term is a single d20 that was kept (adv/dis included)."""
        first = self.terms[0] if self.terms else None
        if first is None or not first.is_dice or first.sides != 20 or first.sign < 0:
            return ""
        kept = [r for r, k in zip(first.rolls, first.kept) if k]
        if len(kept) != 1:
            return ""
        return {20: "nat20", 1: "nat1"}.get(kept[0], "")

    @property
    def detail(self) -> str:
        """The dice behind the total, e.g. ``[17, ~4] + 5`` (``~`` marks a dropped die)."""
        out = ""
        for i, t in enumerate(self.terms):
            if t.is_dice:
                dice = ", ".join(str(r) if k else f"~{r}" for r, k in zip(t.rolls, t.kept))
                piece = f"[{dice}]"
            else:
                piece = str(t.value)
            if i == 0:
                out += ("-" if t.sign < 0 else "") + piece
            else:
                out += f" {'-' if t.sign < 0 else '+'} {piece}"
        return out

    def to_body(self) -> dict:
        return {"expr": self.expression, "detail": self.detail, "total": self.total,
                "label": self.label, "crit": self.crit}


def _parse_term(text: str, sign: int) -> Term:
    m = _TERM_RE.match(text)
    if not m:
        raise DiceError(f"I don't understand '{text}'.")
    if m.group("const") is not None:
        return Term(sign=sign, value=int(m.group("const")))
    count = int(m.group("count") or 1)
    sides = 100 if m.group("sides") == "%" else int(m.group("sides"))
    if not 1 <= count <= MAX_DICE:
        raise DiceError(f"Roll between 1 and {MAX_DICE} dice at a time.")
    if not 2 <= sides <= MAX_SIDES:
        raise DiceError(f"Dice need between 2 and {MAX_SIDES} sides.")
    keep, keep_n = "", 0
    if m.group("keep"):
        keep = (m.group("keep")[1:] or "h").lower()
        keep_n = int(m.group("keepn"))
        if not 1 <= keep_n <= count:
            raise DiceError(f"You can keep between 1 and {count} of those dice.")
    return Term(sign=sign, count=count, sides=sides, keep=keep, keep_n=keep_n)


def parse_expression(expr: str) -> List[Term]:
    expr = re.sub(r"\s+", "", expr)
    if not expr or not _EXPR_CHARS.match(expr):
        raise DiceError("Try something like /roll 2d6+3 or /roll d20+5 adv.")
    pieces = re.findall(r"[+-]?[^+-]+", expr)
    if "".join(pieces) != expr:
        raise DiceError("Try something like /roll 2d6+3 or /roll d20+5 adv.")
    if len(pieces) > MAX_TERMS:
        raise DiceError(f"That has too many parts (limit {MAX_TERMS}).")
    terms = []
    for piece in pieces:
        sign = -1 if piece.startswith("-") else 1
        terms.append(_parse_term(piece.lstrip("+-"), sign))
    if not any(t.is_dice for t in terms):
        raise DiceError("There are no dice in that.")
    return terms


_MODES = {"adv": "adv", "advantage": "adv", "dis": "dis", "disadvantage": "dis"}


def parse_command(args: str) -> Roll:
    """Parse what follows ``/roll``. Raises :class:`DiceError`."""
    words = (args or "").split()
    expr_words: List[str] = []
    while words and _EXPR_CHARS.match(words[0]):
        expr_words.append(words.pop(0))
    terms = parse_expression("".join(expr_words))
    mode = ""
    if words and words[0].lower() in _MODES:
        mode = _MODES[words.pop(0).lower()]
    label = " ".join(words)[:MAX_LABEL].strip()
    if mode:
        first = next((t for t in terms if t.is_dice and t.sides == 20 and t.count == 1 and not t.keep
                      and t.sign > 0), None)
        if first is None:
            raise DiceError("Advantage and disadvantage need a single d20 to roll twice.")
        first.count, first.keep, first.keep_n = 2, ("h" if mode == "adv" else "l"), 1
    return Roll(terms=terms, label=label, mode=mode)


def roll(spec: "Roll | str", rng: Optional[random.Random] = None) -> Roll:
    """Roll the dice in ``spec`` (a parsed :class:`Roll` or the text after ``/roll``)."""
    r = parse_command(spec) if isinstance(spec, str) else spec
    rng = rng or _rng
    for t in r.terms:
        if not t.is_dice:
            continue
        t.rolls = [rng.randint(1, t.sides) for _ in range(t.count)]
        t.kept = [True] * t.count
        if t.keep:
            order = sorted(range(t.count), key=lambda i: t.rolls[i], reverse=(t.keep == "h"))
            keep_idx = set(order[:t.keep_n])
            t.kept = [i in keep_idx for i in range(t.count)]
    return r


def split_command(text: str) -> Tuple[str, str]:
    """``"/roll 2d6"`` -> ``("/roll", "2d6")``; plain text -> ``("", text)``."""
    text = (text or "").strip()
    if not text.startswith("/"):
        return "", text
    cmd, _, rest = text.partition(" ")
    return cmd.lower(), rest.strip()
