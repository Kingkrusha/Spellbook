"""The dice analysis engine: known results, an independent simulation as a cross-check, big counts."""

import math
import random
import time

import pytest

from dice_analyzer import (DiceError, DiceTerm, Dist, Expression, chance_at_least, parse_expression,
                           summarize)


# ----------------------------------------------------------------------------- reference roller

def simulate_term(term: DiceTerm, rng: random.Random) -> int:
    """Roll one DiceTerm the long way, following the rules literally (independent of the maths)."""
    def one_die() -> int:
        def roll() -> int:
            v = rng.randint(1, term.sides)
            if term.reroll_max and v <= term.reroll_max:
                if term.reroll_once:
                    v = rng.randint(1, term.sides)
                else:
                    while v <= term.reroll_max:
                        v = rng.randint(1, term.sides)
            return max(v, term.minimum)
        if term.copies == 1:
            return roll()
        rolls = [roll() for _ in range(term.copies)]
        if term.pick == "emph":
            mid = term.sides / 2
            return max(rolls, key=lambda v: (abs(v - mid), v))          # furthest from the middle, higher on a tie
        return max(rolls) if term.pick == "high" else min(rolls)

    dice = sorted((one_die() for _ in range(term.count)), reverse=(term.keep != "low"))
    if term.keep:
        dice = dice[:term.keep_n]
    return sum(dice)


def simulate(expr: Expression, rng: random.Random) -> int:
    def once() -> int:
        return sum(t.sign * simulate_term(t, rng) for t in expr.terms) + expr.flat
    if expr.roll_twice:
        a, b = once(), once()
        return max(a, b) if expr.roll_twice == "high" else min(a, b)
    return once()


def assert_matches_simulation(expr: Expression, trials: int = 60000, seed: int = 7):
    dist = expr.distribution()
    rng = random.Random(seed)
    samples = [simulate(expr, rng) for _ in range(trials)]
    mean = sum(samples) / trials
    sd = dist.std()
    assert abs(mean - dist.mean()) < 5 * (sd / math.sqrt(trials)) + 1e-9, (expr.text(), mean, dist.mean())
    # a few points of the cumulative distribution
    for p in (0.1, 0.5, 0.9):
        v = dist.percentile(p)
        observed = sum(1 for x in samples if x <= v) / trials
        assert abs(observed - dist.at_most(v)) < 0.012, (expr.text(), v, observed, dist.at_most(v))


# ----------------------------------------------------------------------------- known results

def test_two_d6_is_the_triangle():
    d = parse_expression("2d6").distribution()
    assert d.support() == (2, 12) and d.mean() == pytest.approx(7)
    assert d.pmf(7) == pytest.approx(6 / 36) and d.pmf(2) == pytest.approx(1 / 36)
    assert d.variance() == pytest.approx(2 * 35 / 12)
    assert d.total() == pytest.approx(1)


def test_flat_modifiers_add_and_subtract():
    d = parse_expression("2d6+4-12").distribution()
    assert d.mean() == pytest.approx(7 + 4 - 12) and d.support() == (2 + 4 - 12, 12 + 4 - 12)
    assert parse_expression("-12").distribution().mean() == -12


@pytest.mark.parametrize("text,mean", [
    ("d20adv", 13.825),                 # advantage
    ("d20dis", 7.175),                  # disadvantage
    ("d20r1", 10.975),                  # Halfling Luck: reroll a 1 once
    ("d20min10", 12.75),                # Reliable Talent: 9 or less counts as 10
    ("d6r2", 25 / 6),                   # Great Weapon Fighting: reroll 1s and 2s once
    ("4d6kh3", 12.2446),                # ability scores: drop the lowest
    ("4d6kl3", 21 - 12.2446),
    ("d20elf", 20 - 190 ** 2 / 8000),      # three d20s keep the highest (Elven Accuracy): 15.4875
    ("d20dadv", 15.4875),                  # double advantage: three d20s, keep the highest
    ("d20ddis", 21 - 15.4875),             # double disadvantage: three d20s, keep the lowest
])
def test_well_known_averages(text, mean):
    assert parse_expression(text).distribution().mean() == pytest.approx(mean, abs=1e-3)


def test_rerolling_until_higher_is_a_conditional_uniform():
    d = DiceTerm(1, 6, reroll_max=2, reroll_once=False).single()
    assert d.pmf(1) == d.pmf(2) == 0 and d.pmf(3) == pytest.approx(0.25)
    assert d.mean() == pytest.approx(4.5)


def test_halfling_luck_then_reliable_talent_then_advantage_order():
    """Reroll, then the minimum, then pick the best copy: the d20 you finally use gets the floor."""
    term = DiceTerm(1, 20, copies=2, reroll_max=1, minimum=10)
    d = term.distribution()
    assert d.support() == (10, 20)
    # every value of one die is >= 10, so the chance of a 10 with advantage is the chance both are 10
    single = DiceTerm(1, 20, reroll_max=1, minimum=10).single()
    assert d.pmf(10) == pytest.approx(single.pmf(10) ** 2)


def test_roll_twice_keeps_the_better_whole_roll():
    e = Expression([DiceTerm(2, 6)], flat=3, roll_twice="high")
    d = e.distribution()
    base = Expression([DiceTerm(2, 6)], flat=3).distribution()
    assert d.mean() > base.mean() and d.support() == base.support()
    assert d.total() == pytest.approx(1)
    low = Expression([DiceTerm(2, 6)], flat=3, roll_twice="low").distribution()
    assert low.mean() + d.mean() == pytest.approx(2 * base.mean())      # symmetric around the mean


def test_subtracted_dice():
    d = parse_expression("1d8-1d4").distribution()
    assert d.mean() == pytest.approx(4.5 - 2.5) and d.support() == (1 - 4, 8 - 1)


# ----------------------------------------------------------------------------- against a simulation

@pytest.mark.parametrize("text", [
    "d20adv+5",
    "d20dis-2",
    "3d8rr2+1d6r1-2",
    "2d6r2+4",
    "d20r1min10adv+7",
    "5d6kh3+2d4",
    "6d10kl2r2",
    "d20elf+3",
    "4d6r1min2kh3",
    "d20emph+4",
    "3d6emph",
    "d20dadv-1",
    "d20ddis",
    "2d8r1emph+2",
])
def test_exact_distribution_agrees_with_an_independent_simulation(text):
    assert_matches_simulation(parse_expression(text))


def test_roll_twice_agrees_with_simulation():
    assert_matches_simulation(Expression([DiceTerm(2, 6, reroll_max=2)], flat=4, roll_twice="high"))


# ----------------------------------------------------------------------------- big counts

def test_a_thousand_dice_are_exact_and_fast():
    t = time.time()
    d = parse_expression("1000d20").distribution()
    assert time.time() - t < 6
    assert not d.approx
    assert d.mean() == pytest.approx(10500) and d.variance() == pytest.approx(1000 * 33.25)
    assert d.total() == pytest.approx(1, abs=1e-9)
    assert d.support()[0] > 1000 and d.support()[1] < 20000
    assert d.percentile(0.5) in (10499, 10500, 10501)


def test_fft_and_direct_convolution_agree():
    from dice_analyzer import _convolve_direct, _convolve_fft
    rng = random.Random(3)
    a = [rng.random() for _ in range(300)]
    b = [rng.random() for _ in range(200)]
    direct = _convolve_direct(a, b)
    fast = _convolve_fft(a, b)
    scale = sum(direct)
    assert all(abs(x / scale - y) < 1e-12 for x, y in zip(direct, fast))


def test_many_dice_of_several_kinds_in_one_request():
    d = parse_expression("200d6+150d10+80d20+3000d4-77").distribution()
    assert d.mean() == pytest.approx(200 * 3.5 + 150 * 5.5 + 80 * 10.5 + 3000 * 2.5 - 77)
    assert d.total() == pytest.approx(1, abs=1e-9)


def test_absurd_sizes_fall_back_to_a_marked_normal_approximation():
    d = parse_expression("200000d20").distribution()
    assert d.approx
    assert d.mean() == pytest.approx(200000 * 10.5, rel=1e-9)
    assert d.std() == pytest.approx(math.sqrt(200000 * 33.25), rel=1e-6)
    assert d.total() == pytest.approx(1)


def test_fft_results_do_not_have_negative_probabilities():
    d = parse_expression("2500d12").distribution()
    assert min(d.probs) >= 0.0 and d.total() == pytest.approx(1, abs=1e-9)


def test_big_keep_groups_are_solved_exactly_or_flagged():
    exact = parse_expression("10d6kh3").distribution()
    assert not exact.approx and exact.total() == pytest.approx(1)
    assert_matches_simulation(parse_expression("10d6kh3"), trials=30000)
    sampled = parse_expression("200d20kh100").distribution()
    assert sampled.approx and sampled.total() == pytest.approx(1)


# ----------------------------------------------------------------------------- queries

def test_chance_queries():
    d = parse_expression("d20").distribution()
    assert chance_at_least(d, 15) == pytest.approx(0.3)
    assert d.at_least(21) == 0 and d.at_least(0) == 1 and d.at_most(0) == 0 and d.at_most(20) == 1
    assert d.percentile(0.5) == 10 and d.median() == 10


def test_summary():
    s = summarize(parse_expression("d20adv").distribution())
    assert s.low == 1 and s.high == 20 and s.mean == pytest.approx(13.825)
    assert s.modes == [20] and s.percentiles[90] >= s.percentiles[10]


def test_binning_keeps_all_the_probability():
    d = parse_expression("300d6").distribution()
    bars = d.binned(80)
    assert len(bars) <= 80 and sum(p for _, _, p in bars) == pytest.approx(1)


def test_halved_and_clamped():
    d = parse_expression("2d8").distribution()
    half = d.halved()
    assert half.support() == (1, 8) and half.total() == pytest.approx(1)
    assert d.clamp_min(10).support() == (10, 16) and d.clamp_min(10).total() == pytest.approx(1)


def test_mixture():
    miss = Dist.point(0)
    hit = parse_expression("1d6").distribution()
    m = Dist.mixture([(0.25, miss), (0.75, hit)])
    assert m.mean() == pytest.approx(0.75 * 3.5) and m.pmf(0) == pytest.approx(0.25)


# ----------------------------------------------------------------------------- bad input

@pytest.mark.parametrize("text", ["", "2d", "dd6", "3x6", "abc", "d20adv adv", "5d6kh9", "d6 dis", "1d1", "d20min21",
                                  "0d6", "2d6rr6", "+", "2d6++3"])
def test_unreadable_or_impossible_rolls_give_clear_errors(text):
    with pytest.raises(DiceError):
        parse_expression(text).distribution()


def test_the_text_form_round_trips():
    for text in ("2d6+1d4+4", "4d6kh3", "d20adv+5", "3d8rr2+1d6r1-2", "d20min10", "1d20elf+7"):
        once = parse_expression(text).text()
        assert parse_expression(once).text() == once


def test_emphasis_keeps_the_roll_furthest_from_the_middle():
    d = parse_expression("d20emph").distribution()
    assert d.pmf(20) == pytest.approx(0.0975) and d.pmf(1) == pytest.approx(0.0875)     # 1 and 19 tie: the higher is kept
    assert d.pmf(10) == pytest.approx(1 / 400)                                          # only a double 10
    assert d.total() == pytest.approx(1)
    assert d.mean() > 10.5                                                                # the tie-break favours high
    # a d6's middle is 3: 1 and 6 are both far, 3 is closest
    d6 = parse_expression("d6emph").distribution()
    assert d6.pmf(3) == pytest.approx(1 / 36) and d6.pmf(6) > d6.pmf(1)


def test_double_advantage_and_disadvantage_text_round_trips():
    for text in ("d20dadv+5", "d20ddis", "d20emph-2", "2d6emph"):
        once = parse_expression(text).text()
        assert parse_expression(once).text() == once
    with pytest.raises(DiceError):
        DiceTerm(1, 5000, copies=2, pick="emph").validate()


def test_reroll_the_lowest_dice_is_exact():
    from dice_analyzer import reroll_lowest_distribution
    rng = random.Random(11)
    n, k, sides = 6, 2, 6
    single = DiceTerm(1, sides).single()
    exact = reroll_lowest_distribution(single, n, k)
    samples = []
    for _ in range(60000):
        dice = sorted(rng.randint(1, sides) for _ in range(n))
        for i in range(k):
            if dice[i] < 3.5:
                dice[i] = rng.randint(1, sides)
        samples.append(sum(dice))
    assert abs(sum(samples) / len(samples) - exact.mean()) < 0.05
    assert exact.total() == pytest.approx(1)
    # with no limit it is the same as rerolling every die below the average once
    free = reroll_lowest_distribution(single, 3, 3)
    per_die = DiceTerm(3, 6, reroll_max=3).distribution()
    assert free.mean() == pytest.approx(per_die.mean())
    assert reroll_lowest_distribution(single, 3, 0).mean() == pytest.approx(10.5)
