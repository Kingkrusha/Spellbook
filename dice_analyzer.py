"""
Dice analysis engine: exact probability distributions for dice expressions.

No UI and no randomness (apart from a sampling fallback): given a description of what is rolled,
``Expression.distribution()`` returns a :class:`Dist` from which the average, spread, most likely
result, percentiles and "chance of beating a target" come directly.

What can be described
---------------------
* Any number of dice of any kind in one expression, added or subtracted, plus flat modifiers.
* Per kind of die:

  - ``copies`` / ``pick``: roll each die several times and take the best or worst (advantage and
    disadvantage are two d20s, Elven Accuracy three);
  - ``reroll_max``: a die showing this or less is rerolled, once (Halfling Luck, Great Weapon
    Fighting: the new roll must be used) or until it shows more;
  - ``minimum``: a die showing less counts as this (Reliable Talent's 10, Elemental Adept's 2);
  - ``keep``: keep only the highest / lowest ``keep_n`` of the dice (``4d6`` drop lowest).

  Per-die effects apply in the order *reroll, then minimum, then best-of-copies*, which is how
  the rules read (the d20 you finally use is the one that gets the Reliable Talent floor).
* ``roll_twice`` on a whole expression: roll the entire thing twice, keep the better (Savage
  Attacker) or worse.

How large counts work
---------------------
Independent dice add by convolution. Small cases are convolved exactly. For hundreds or
thousands of dice the sum of ``n`` identical dice is computed in the frequency domain (one
forward and one inverse FFT: the spectrum of the sum is the per-die spectrum to the ``n``), which
stays exact to ~1e-15. Beyond ``MAX_EXACT_RANGE`` possible totals the answer is a (very accurate,
by the central limit theorem) normal approximation and the result is marked ``approx``.

Text syntax (``parse_expression``)
----------------------------------
``2d6+1d4+4-12``, ``d20`` (= ``1d20``), ``4d6kh3`` / ``kl`` / ``k3`` (keep highest/lowest),
``2d6r2`` (reroll 2 or less once), ``2d6rr2`` (keep rerolling until above 2), ``d20min10``,
``d20adv`` / ``d20dis`` (roll twice, keep higher / lower), ``d20elf`` (three d20s). A trailing
``adv`` / ``dis`` (like the chat's ``/roll``) applies to the first d20.
"""

from __future__ import annotations

import cmath
import math
import random
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

MAX_EXACT_RANGE = 1 << 16        # possible-total count above which a normal approximation is used
DIRECT_LIMIT = 250_000           # len(a) * len(b) up to which convolution is done directly
DIRECT_POWER_RANGE = 1500        # size of an n-fold sum computed by repeated direct squaring
DUST = 1e-15                     # FFT noise: probabilities below this are dropped
KEEP_EXACT_COST = 4e7            # work estimate above which a keep-highest/lowest group is sampled instead

MAX_COUNT = 1_000_000
MAX_SIDES = 100_000
MAX_TERMS = 50
MAX_EMPHASIS_SIDES = 2000        # emphasis compares every pair of faces


class DiceError(ValueError):
    """The roll could not be understood or is out of range (message is user-readable)."""


# ----------------------------------------------------------------------------- FFT

def _fft(a: List[complex], invert: bool) -> None:
    """In-place iterative radix-2 FFT (``len(a)`` must be a power of two)."""
    n = len(a)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    sign = 1 if invert else -1
    length = 2
    while length <= n:
        half = length >> 1
        step = sign * 2.0 * math.pi / length
        roots = [cmath.exp(1j * step * k) for k in range(half)]
        if half >= 8:
            for i in range(0, n, length):
                lo = a[i:i + half]
                t = [h * r for h, r in zip(a[i + half:i + length], roots)]
                a[i:i + half] = [x + y for x, y in zip(lo, t)]
                a[i + half:i + length] = [x - y for x, y in zip(lo, t)]
        else:
            for i in range(0, n, length):
                for k in range(half):
                    u = a[i + k]
                    v = a[i + k + half] * roots[k]
                    a[i + k] = u + v
                    a[i + k + half] = u - v
        length <<= 1
    if invert:
        inv = 1.0 / n
        for i in range(n):
            a[i] *= inv


def _next_pow2(n: int) -> int:
    size = 1
    while size < n:
        size <<= 1
    return size


def _clean(values: Iterable[complex]) -> List[float]:
    """Real parts of an inverse FFT, with noise removed and the total restored to 1."""
    out = [v.real if v.real > DUST else 0.0 for v in values]
    total = math.fsum(out)
    return [v / total for v in out] if total > 0 else out


def _convolve_direct(a: Sequence[float], b: Sequence[float]) -> List[float]:
    if len(a) < len(b):
        a, b = b, a
    res = [0.0] * (len(a) + len(b) - 1)
    for j, y in enumerate(b):
        if y == 0.0:
            continue
        for i, x in enumerate(a):
            res[i + j] += x * y
    return res


def _convolve_fft(a: Sequence[float], b: Sequence[float]) -> List[float]:
    size = _next_pow2(len(a) + len(b) - 1)
    fa = [complex(v) for v in a] + [0j] * (size - len(a))
    fb = [complex(v) for v in b] + [0j] * (size - len(b))
    _fft(fa, False)
    _fft(fb, False)
    prod = [x * y for x, y in zip(fa, fb)]
    _fft(prod, True)
    return _clean(prod[:len(a) + len(b) - 1])


# ----------------------------------------------------------------------------- Dist

class Dist:
    """The distribution of an integer: ``probs[i]`` is P(X = lo + i)."""

    __slots__ = ("lo", "probs", "approx", "_mean", "_var")

    def __init__(self, lo: int, probs: Sequence[float], approx: bool = False,
                 mean: Optional[float] = None, var: Optional[float] = None):
        self.lo = int(lo)
        self.probs = list(probs)
        self.approx = approx
        self._mean = mean
        self._var = var

    # ---- construction
    @classmethod
    def point(cls, value: int) -> "Dist":
        return cls(value, [1.0], mean=float(value), var=0.0)

    @classmethod
    def uniform(cls, sides: int) -> "Dist":
        return cls(1, [1.0 / sides] * sides)

    @classmethod
    def normal(cls, mean: float, var: float) -> "Dist":
        """A discretised normal (used past MAX_EXACT_RANGE, flagged ``approx``)."""
        if var <= 1e-12:
            return cls(int(round(mean)), [1.0], approx=True, mean=mean, var=0.0)
        sd = math.sqrt(var)
        lo = int(math.floor(mean - 8.5 * sd))
        hi = int(math.ceil(mean + 8.5 * sd))

        def phi(x: float) -> float:
            return 0.5 * (1.0 + math.erf((x - mean) / (sd * math.sqrt(2.0))))
        probs = [max(0.0, phi(v + 0.5) - phi(v - 0.5)) for v in range(lo, hi + 1)]
        total = math.fsum(probs)
        return cls(lo, [p / total for p in probs], approx=True, mean=mean, var=var)

    @classmethod
    def mixture(cls, parts: Sequence[Tuple[float, "Dist"]]) -> "Dist":
        """Pick ``dist`` with probability ``weight`` (weights need not be normalised)."""
        parts = [(w, d) for w, d in parts if w > 0]
        if not parts:
            return cls.point(0)
        total = math.fsum(w for w, _ in parts)
        lo = min(d.lo for _, d in parts)
        hi = max(d.hi for _, d in parts)
        probs = [0.0] * (hi - lo + 1)
        for w, d in parts:
            share = w / total
            off = d.lo - lo
            for i, p in enumerate(d.probs):
                probs[off + i] += share * p
        return cls(lo, probs, approx=any(d.approx for _, d in parts)).trimmed()

    # ---- basics
    @property
    def hi(self) -> int:
        return self.lo + len(self.probs) - 1

    def trimmed(self) -> "Dist":
        probs = self.probs
        start, end = 0, len(probs)
        while start < end - 1 and probs[start] <= 0.0:
            start += 1
        while end - 1 > start and probs[end - 1] <= 0.0:
            end -= 1
        if start == 0 and end == len(probs):
            return self
        return Dist(self.lo + start, probs[start:end], self.approx, self._mean, self._var)

    def mean(self) -> float:
        if self._mean is not None:
            return self._mean
        return math.fsum((self.lo + i) * p for i, p in enumerate(self.probs))

    def variance(self) -> float:
        if self._var is not None:
            return self._var
        mu = self.mean()
        return max(0.0, math.fsum(((self.lo + i) - mu) ** 2 * p for i, p in enumerate(self.probs)))

    def std(self) -> float:
        return math.sqrt(self.variance())

    def pmf(self, value: int) -> float:
        i = value - self.lo
        return self.probs[i] if 0 <= i < len(self.probs) else 0.0

    def at_most(self, value: int) -> float:
        """P(X <= value)."""
        i = value - self.lo
        if i < 0:
            return 0.0
        if i >= len(self.probs) - 1:
            return 1.0
        return min(1.0, math.fsum(self.probs[:i + 1]))

    def at_least(self, value: int) -> float:
        """P(X >= value)."""
        i = value - self.lo
        if i <= 0:
            return 1.0
        if i >= len(self.probs):
            return 0.0
        return min(1.0, math.fsum(self.probs[i:]))

    def percentile(self, fraction: float) -> int:
        """The smallest value v with P(X <= v) >= fraction."""
        running = 0.0
        for i, p in enumerate(self.probs):
            running += p
            if running >= fraction - 1e-12:
                return self.lo + i
        return self.hi

    def median(self) -> int:
        return self.percentile(0.5)

    def modes(self) -> List[int]:
        best = max(self.probs)
        return [self.lo + i for i, p in enumerate(self.probs) if p >= best - 1e-12]

    def support(self) -> Tuple[int, int]:
        t = self.trimmed()
        return t.lo, t.hi

    def total(self) -> float:
        return math.fsum(self.probs)

    # ---- transforms
    def shift(self, k: int) -> "Dist":
        return Dist(self.lo + k, self.probs, self.approx,
                    None if self._mean is None else self._mean + k, self._var)

    def negate(self) -> "Dist":
        return Dist(-self.hi, self.probs[::-1], self.approx,
                    None if self._mean is None else -self._mean, self._var)

    def clamp_min(self, minimum: int) -> "Dist":
        """Values below ``minimum`` count as ``minimum``."""
        if self.lo >= minimum:
            return self
        if self.hi <= minimum:
            return Dist.point(minimum)
        below = math.fsum(self.probs[:minimum - self.lo + 1])
        probs = [below] + self.probs[minimum - self.lo + 1:]
        return Dist(minimum, probs, self.approx)

    def halved(self) -> "Dist":
        """Each value halved, rounded down (the damage of a successful save)."""
        out: Dict[int, float] = {}
        for i, p in enumerate(self.probs):
            v = (self.lo + i) // 2
            out[v] = out.get(v, 0.0) + p
        lo, hi = min(out), max(out)
        return Dist(lo, [out.get(v, 0.0) for v in range(lo, hi + 1)], self.approx)

    def __add__(self, other: "Dist") -> "Dist":
        if len(self.probs) == 1:
            return other.shift(self.lo)
        if len(other.probs) == 1:
            return self.shift(other.lo)
        if len(self.probs) * len(other.probs) <= DIRECT_LIMIT:
            probs = _convolve_direct(self.probs, other.probs)
        elif len(self.probs) + len(other.probs) > MAX_EXACT_RANGE:
            return Dist.normal(self.mean() + other.mean(), self.variance() + other.variance())
        else:
            probs = _convolve_fft(self.probs, other.probs)
        mean = var = None
        if self._mean is not None and other._mean is not None:
            mean, var = self._mean + other._mean, self.variance() + other.variance()
        return Dist(self.lo + other.lo, probs, self.approx or other.approx, mean, var).trimmed()

    def max_with(self, other: "Dist") -> "Dist":
        """The distribution of max(X, Y) for independent X (this) and Y (other)."""
        return _extreme(self, other, True)

    def min_with(self, other: "Dist") -> "Dist":
        return _extreme(self, other, False)

    def power(self, n: int) -> "Dist":
        """The sum of ``n`` independent copies of this distribution."""
        if n < 0:
            raise DiceError("A negative number of dice makes no sense.")
        if n == 0:
            return Dist.point(0)
        if n == 1 or len(self.probs) == 1:
            return self if n == 1 else self.shift(self.lo * (n - 1)) if len(self.probs) == 1 else self
        width = len(self.probs)
        size = n * (width - 1) + 1
        mean, var = n * self.mean(), n * self.variance()
        if size > MAX_EXACT_RANGE:
            return Dist.normal(mean, var)
        if size <= DIRECT_POWER_RANGE:
            result: Optional[List[float]] = None
            base = list(self.probs)
            k = n
            while k:
                if k & 1:
                    result = base if result is None else _convolve_direct(result, base)
                k >>= 1
                if k:
                    base = _convolve_direct(base, base)
            return Dist(self.lo * n, result or [1.0], self.approx, mean, var).trimmed()
        # n-fold convolution in the frequency domain: spectrum ** n, one inverse transform
        fsize = _next_pow2(size)
        spectrum = [complex(v) for v in self.probs] + [0j] * (fsize - width)
        _fft(spectrum, False)
        powered = []
        for value in spectrum:
            r, theta = cmath.polar(value)
            powered.append(cmath.rect(r ** n, theta * n) if r > 0 else 0j)
        _fft(powered, True)
        return Dist(self.lo * n, _clean(powered[:size]), self.approx, mean, var).trimmed()

    def sample(self, rng: random.Random) -> int:
        x = rng.random()
        running = 0.0
        for i, p in enumerate(self.probs):
            running += p
            if x < running:
                return self.lo + i
        return self.hi

    # ---- for charts
    def binned(self, max_bins: int = 120) -> List[Tuple[int, int, float]]:
        """(first value, last value, probability) bars; one per value unless there are too many."""
        n = len(self.probs)
        if n <= max_bins:
            return [(self.lo + i, self.lo + i, p) for i, p in enumerate(self.probs)]
        width = math.ceil(n / max_bins)
        bars = []
        for start in range(0, n, width):
            chunk = self.probs[start:start + width]
            bars.append((self.lo + start, self.lo + start + len(chunk) - 1, math.fsum(chunk)))
        return bars


def _extreme(a: Dist, b: Dist, high: bool) -> Dist:
    lo = min(a.lo, b.lo)
    hi = max(a.hi, b.hi)

    def cdf_table(d: Dist) -> List[float]:
        """P(X <= v) for v from lo to hi."""
        table, running = [], 0.0
        for v in range(lo, hi + 1):
            i = v - d.lo
            if 0 <= i < len(d.probs):
                running += d.probs[i]
            table.append(min(1.0, running))
        return table

    ca, cb = cdf_table(a), cdf_table(b)
    if high:      # P(max <= v) = F_a(v) * F_b(v)
        joint = [x * y for x, y in zip(ca, cb)]
        probs = [joint[0]] + [joint[i] - joint[i - 1] for i in range(1, len(joint))]
    else:         # P(min >= v) = (1 - F_a(v-1)) * (1 - F_b(v-1))
        sf = [(1.0 - (ca[i - 1] if i else 0.0)) * (1.0 - (cb[i - 1] if i else 0.0)) for i in range(len(ca))]
        probs = [sf[i] - (sf[i + 1] if i + 1 < len(sf) else 0.0) for i in range(len(sf))]
    return Dist(lo, [max(0.0, p) for p in probs], a.approx or b.approx).trimmed()


# ----------------------------------------------------------------------------- one die

@dataclass
class DiceTerm:
    """``count`` dice of ``sides`` sides, and how each one is rolled."""
    count: int
    sides: int
    sign: int = 1
    copies: int = 1           # roll each die this many times and keep one (2 = advantage/disadvantage)
    pick: str = "high"        # which one: "high", "low", or "emph" (emphasis: the one furthest from the middle)
    reroll_max: int = 0       # a die showing this or less is rerolled (0 = never)
    reroll_once: bool = True  # once (the new roll stands) or until it shows more
    minimum: int = 1          # a die showing less counts as this
    keep: str = ""            # "", "high" or "low": keep only the best/worst keep_n of the dice
    keep_n: int = 0

    def validate(self) -> None:
        if not 1 <= self.count <= MAX_COUNT:
            raise DiceError(f"Use between 1 and {MAX_COUNT:,} dice per kind.")
        if not 2 <= self.sides <= MAX_SIDES:
            raise DiceError(f"Dice need between 2 and {MAX_SIDES:,} sides.")
        if self.copies < 1 or self.copies > 20:
            raise DiceError("A die can be rolled between 1 and 20 times (advantage rolls it twice).")
        if self.pick not in ("high", "low", "emph"):
            raise DiceError("A die is kept as the highest, the lowest or by emphasis.")
        if self.pick == "emph" and self.copies > 1:
            if self.copies != 2:
                raise DiceError("Emphasis rolls a die twice.")
            if self.sides > MAX_EMPHASIS_SIDES:
                raise DiceError(f"Emphasis works on dice of up to {MAX_EMPHASIS_SIDES:,} sides.")
        if self.reroll_max < 0 or self.reroll_max > self.sides:
            raise DiceError("Reroll values must be between 0 and the number of sides.")
        if self.reroll_max >= self.sides and not self.reroll_once:
            raise DiceError("Rerolling every value until one is higher never ends: lower the reroll limit.")
        if self.minimum < 1 or self.minimum > self.sides:
            raise DiceError("The minimum must be between 1 and the number of sides.")
        if self.keep:
            if self.keep not in ("high", "low"):
                raise DiceError("Keep must be highest or lowest.")
            if not 1 <= self.keep_n <= self.count:
                raise DiceError(f"You can keep between 1 and {self.count} of those dice.")

    # ---- the distribution of one die
    def die_probabilities(self) -> List[float]:
        """P(a single die's final value = v) for v in 1..sides, after rerolls, minimum and copies."""
        s = self.sides
        p = [1.0 / s] * s
        r = self.reroll_max
        if r:
            if self.reroll_once:
                # a die that shows <= r is rolled again and that roll stands
                again = r / s
                p = [(1.0 / s) * (0.0 if v <= r else 1.0) + again * (1.0 / s) for v in range(1, s + 1)]
            else:
                p = [0.0 if v <= r else 1.0 / (s - r) for v in range(1, s + 1)]
        m = self.minimum
        if m > 1:
            floored = [0.0] * s
            for v in range(1, s + 1):
                floored[max(v, m) - 1] += p[v - 1]
            p = floored
        if self.copies > 1:
            c = self.copies
            cdf = []
            running = 0.0
            for v in range(s):
                running += p[v]
                cdf.append(min(1.0, running))
            if self.pick == "emph":
                p = _emphasis(p)
            elif self.pick == "high":
                p = [cdf[v] ** c - (cdf[v - 1] ** c if v else 0.0) for v in range(s)]
            else:
                sf_next = [1.0 - cdf[v - 1] if v else 1.0 for v in range(s)]    # P(X >= v+1)
                p = [sf_next[v] ** c - (sf_next[v + 1] ** c if v + 1 < s else 0.0) for v in range(s)]
        return [max(0.0, v) for v in p]

    def single(self) -> Dist:
        return Dist(1, self.die_probabilities())

    def distribution(self) -> Dist:
        """The distribution of this term's total (before ``sign`` is applied)."""
        self.validate()
        single = self.single()
        if not self.keep or self.keep_n >= self.count:
            return single.power(self.count)
        return _keep_distribution(single, self.count, self.keep_n, self.keep == "high")

    def text(self) -> str:
        out = f"{self.count}d{self.sides}"
        if self.keep:
            out += ("kh" if self.keep == "high" else "kl") + str(self.keep_n)
        if self.reroll_max:
            out += ("r" if self.reroll_once else "rr") + str(self.reroll_max)
        if self.minimum > 1:
            out += f"min{self.minimum}"
        if self.copies == 2 and self.pick == "emph":
            out += "emph"
        elif self.copies == 2:
            out += "adv" if self.pick == "high" else "dis"
        elif self.copies == 3 and self.pick in ("high", "low"):
            out += "dadv" if self.pick == "high" else "ddis"
        elif self.copies > 1:
            out += f"x{self.copies}{'h' if self.pick == 'high' else 'l'}"
        return out


def _emphasis(p: List[float]) -> List[float]:
    """Roll twice and keep the result furthest from the middle of the die (sides / 2: 10 on a d20). If both are
    equally far (such as 5 and 15 on a d20) the higher one is kept."""
    s = len(p)
    mid = s / 2.0
    dist_of = [abs(v - mid) for v in range(1, s + 1)]
    order = sorted(range(s), key=lambda i: (dist_of[i], i))          # closest to the middle first, then lower first
    # rank groups of equal distance; within a group the higher face wins, so rank by (distance, face)
    out = [0.0] * s
    below = 0.0                                                      # P(a roll is ranked strictly below this one)
    for i in order:
        # this face wins if the other roll is ranked below it, or is the same face (tie keeps the same value)
        out[i] = p[i] * (2.0 * below + p[i])
        below += p[i]
    return out


def reroll_lowest_distribution(single: Dist, n: int, k: int) -> Dist:
    """The sum of ``n`` dice where you may reroll up to ``k`` of them once and must keep the new rolls (Empowered
    Spell, Piercer ...). You reroll the lowest dice, and only those showing less than the average of a fresh die,
    which is the best way to play it. Exact."""
    if k <= 0 or n <= 0:
        return single.power(max(n, 0))
    mean = single.mean()
    probs = single.probs
    low_p = [p if (single.lo + i) < mean else 0.0 for i, p in enumerate(probs)]
    q = math.fsum(low_p)
    if q <= 1e-15:
        return single.power(n)
    low = Dist(single.lo, [p / q for p in low_p]).trimmed()
    high_p = [0.0 if (single.lo + i) < mean else p for i, p in enumerate(probs)]
    h = math.fsum(high_p)
    high = Dist(single.lo, [p / h for p in high_p]).trimmed() if h > 1e-15 else None
    parts = []
    for c in range(n + 1):
        w = math.comb(n, c) * (q ** c) * ((1.0 - q) ** (n - c))
        if w <= 1e-18:
            continue
        r = min(k, c)
        total = Dist.point(0)
        if c - r > 0:
            total = total + _keep_distribution(low, c, c - r, True)       # the low dice you leave alone
        if r > 0:
            total = total + single.power(r)                                  # the rerolled dice
        if n - c > 0 and high is not None:
            total = total + high.power(n - c)
        parts.append((w, total))
    return Dist.mixture(parts)


def _keep_distribution(single: Dist, n: int, k: int, highest: bool) -> Dist:
    """The sum of the best ``k`` of ``n`` independent dice with per-die distribution ``single``.

    Dice are "placed" value by value, best value first. State: ``j`` dice placed so far (only
    while ``j < k``) and the sum of the kept ones. At each value, ``t`` of the ``n - j`` dice not
    yet placed show it (``C(n-j, t) * p**t``). As soon as ``k`` dice are placed the rest only have
    to be strictly worse than the current value, which adds nothing to the sum, so that case is
    closed off with a single factor ``P(worse) ** (dice left)``.
    """
    s = len(single.probs)
    if highest:
        values = list(range(single.lo + s - 1, single.lo - 1, -1))      # best (highest) first
        pmf = list(reversed(single.probs))
    else:
        values = list(range(single.lo, single.lo + s))                   # best (lowest) first
        pmf = list(single.probs)

    if s * k * (k * s) * n > KEEP_EXACT_COST:
        return _keep_sampled(single, n, k, highest)

    worse = []                                   # P(a die is strictly worse than values[i])
    running = 0.0
    for p in pmf:
        running += p
        worse.append(max(0.0, 1.0 - running))
    comb = [[0.0] * (n + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        comb[i][0] = 1.0
        for j in range(1, i + 1):
            comb[i][j] = comb[i - 1][j - 1] + (comb[i - 1][j] if j <= i - 1 else 0.0)

    states: Dict[int, Dict[int, float]] = {0: {0: 1.0}}
    result: Dict[int, float] = {}
    for i, value in enumerate(values):
        p = pmf[i]
        if p <= 0.0:
            continue
        powers = [p ** t for t in range(n + 1)]
        nxt: Dict[int, Dict[int, float]] = {}
        for j, sums in states.items():
            remaining = n - j
            for t in range(remaining + 1):
                weight = comb[remaining][t] * powers[t]
                if j + t >= k:
                    w = weight * (worse[i] ** (remaining - t))
                    if w <= 0.0:
                        continue
                    take = (k - j) * value
                    for sm, w0 in sums.items():
                        result[sm + take] = result.get(sm + take, 0.0) + w0 * w
                else:
                    bucket = nxt.setdefault(j + t, {})
                    add = t * value
                    for sm, w0 in sums.items():
                        bucket[sm + add] = bucket.get(sm + add, 0.0) + w0 * weight
        states = nxt
    if not result:
        return Dist.point(0)
    if not highest:
        pass                                      # values already ran lowest-first: sums are the real sums
    lo, hi = min(result), max(result)
    probs = [result.get(v, 0.0) for v in range(lo, hi + 1)]
    total = math.fsum(probs)
    return Dist(lo, [p / total for p in probs]).trimmed()


def _keep_sampled(single: Dist, n: int, k: int, highest: bool) -> Dist:
    """Sampling fallback for keep-highest/lowest groups too big to solve exactly (marked approximate)."""
    rng = random.Random(0xD1CE)
    population = [single.lo + i for i in range(len(single.probs))]
    trials = max(8000, min(60000, 3_000_000 // max(1, n)))
    counts: Dict[int, int] = {}
    for _ in range(trials):
        rolls = rng.choices(population, weights=single.probs, k=n)
        rolls.sort(reverse=highest)
        total = sum(rolls[:k])
        counts[total] = counts.get(total, 0) + 1
    lo, hi = min(counts), max(counts)
    return Dist(lo, [counts.get(v, 0) / trials for v in range(lo, hi + 1)], approx=True)


# ----------------------------------------------------------------------------- expressions

@dataclass
class Expression:
    """Kinds of dice (each added or subtracted), a flat modifier, and an optional whole-roll rule."""
    terms: List[DiceTerm] = field(default_factory=list)
    flat: int = 0
    roll_twice: str = ""          # "" | "high" | "low": roll the whole expression twice, keep the better/worse

    def distribution(self) -> Dist:
        if len(self.terms) > MAX_TERMS:
            raise DiceError(f"That has too many kinds of dice (limit {MAX_TERMS}).")
        total = Dist.point(0)
        for term in self.terms:
            part = term.distribution()
            total = total + (part if term.sign > 0 else part.negate())
        total = total.shift(self.flat)
        if self.roll_twice == "high":
            total = total.max_with(total)
        elif self.roll_twice == "low":
            total = total.min_with(total)
        return total.trimmed()

    def text(self) -> str:
        out = ""
        for i, t in enumerate(self.terms):
            out += ("-" if t.sign < 0 else ("+" if i else "")) + t.text()
        if self.flat or not self.terms:
            if out:
                out += f"{'+' if self.flat >= 0 else '-'}{abs(self.flat)}"
            else:
                out = str(self.flat)
        return out

    def copy(self) -> "Expression":
        return Expression([DiceTerm(**t.__dict__) for t in self.terms], self.flat, self.roll_twice)


_TERM = re.compile(r"^(?P<count>\d*)d(?P<sides>\d+|%)(?P<opts>(?:kh\d+|kl\d+|k\d+|rr\d+|r\d+|min\d+|dadv|ddis|emph|adv|dis|elf)*)$",
                   re.IGNORECASE)
_OPT = re.compile(r"kh(\d+)|kl(\d+)|k(\d+)|rr(\d+)|r(\d+)|min(\d+)|(dadv|elf)|(ddis)|(emph)|(adv)|(dis)", re.IGNORECASE)
_MODE_WORD = re.compile(r"\s+(advantage|adv|disadvantage|dis)\s*$", re.IGNORECASE)
_EXPR_OK = re.compile(r"^[0-9dDkKhHlLrRmMiInNaAvVsSeElLfFpP%+\-]+$")


def parse_expression(text: str) -> Expression:
    """Parse ``2d6+1d4+4-12``, ``4d6kh3``, ``d20adv+5`` ... (see the module docstring)."""
    raw = (text or "").strip()
    mode = ""
    m = _MODE_WORD.search(raw)
    if m:
        mode = "adv" if m.group(1).lower().startswith("adv") else "dis"
        raw = raw[:m.start()]
    expr = re.sub(r"\s+", "", raw)
    if not expr:
        raise DiceError("Type a roll such as 2d6+3, 4d6kh3 or d20+5.")
    if not _EXPR_OK.match(expr):
        raise DiceError("I can only read dice, numbers, + and - (and kh, kl, r, rr, min, adv, dis, dadv, ddis, emph).")
    pieces = re.findall(r"[+-]?[^+-]+", expr)
    if "".join(pieces) != expr:
        raise DiceError("That roll is not written correctly: check the + and - signs.")
    if len(pieces) > MAX_TERMS:
        raise DiceError(f"That has too many parts (limit {MAX_TERMS}).")
    out = Expression()
    for piece in pieces:
        sign = -1 if piece.startswith("-") else 1
        body = piece.lstrip("+-")
        if body.isdigit():
            out.flat += sign * int(body)
            continue
        t = _TERM.match(body)
        if not t:
            raise DiceError(f"I don't understand '{body}'.")
        term = DiceTerm(count=int(t.group("count") or 1),
                        sides=100 if t.group("sides") == "%" else int(t.group("sides")), sign=sign)
        for kh, kl, k, rr, r, mn, dadv, ddis, emph, adv, dis in _OPT.findall(t.group("opts")):
            if kh or k:
                term.keep, term.keep_n = "high", int(kh or k)
            elif kl:
                term.keep, term.keep_n = "low", int(kl)
            elif rr:
                term.reroll_max, term.reroll_once = int(rr), False
            elif r:
                term.reroll_max, term.reroll_once = int(r), True
            elif mn:
                term.minimum = int(mn)
            elif adv:
                term.copies, term.pick = 2, "high"
            elif dis:
                term.copies, term.pick = 2, "low"
            elif dadv:
                term.copies, term.pick = 3, "high"
            elif ddis:
                term.copies, term.pick = 3, "low"
            elif emph:
                term.copies, term.pick = 2, "emph"
        term.validate()
        out.terms.append(term)
    if mode:
        first = next((t for t in out.terms if t.sides == 20 and t.copies == 1 and t.sign > 0), None)
        if first is None:
            raise DiceError("Advantage and disadvantage need a d20 to roll twice.")
        first.copies, first.pick = 2, ("high" if mode == "adv" else "low")
    return out


# ----------------------------------------------------------------------------- summaries

@dataclass
class Stats:
    mean: float
    std: float
    low: int
    high: int
    median: int
    modes: List[int]
    percentiles: Dict[int, int]       # 10, 25, 75, 90
    approx: bool


def summarize(dist: Dist) -> Stats:
    low, high = dist.support()
    return Stats(mean=dist.mean(), std=dist.std(), low=low, high=high, median=dist.median(),
                 modes=dist.modes()[:5], percentiles={p: dist.percentile(p / 100) for p in (10, 25, 75, 90)},
                 approx=dist.approx)


def chance_at_least(dist: Dist, target: int) -> float:
    return dist.at_least(target)
