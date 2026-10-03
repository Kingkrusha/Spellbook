import random

import pytest

from lan import dice
from lan.dice import DiceError


class FixedRng(random.Random):
    """Returns the given values in order for randint."""

    def __init__(self, values):
        super().__init__()
        self.values = list(values)

    def randint(self, a, b):
        v = self.values.pop(0)
        assert a <= v <= b
        return v


def test_basic_expressions():
    r = dice.roll("2d6+3", FixedRng([4, 5]))
    assert r.total == 12 and r.detail == "[4, 5] + 3" and r.expression == "2d6+3"
    r = dice.roll("d20-1", FixedRng([10]))
    assert r.total == 9 and r.expression == "1d20-1"
    r = dice.roll("1d8 + 1d4 + 2", FixedRng([3, 2]))
    assert r.total == 7
    r = dice.roll("d%", FixedRng([77]))
    assert r.total == 77 and r.terms[0].sides == 100


def test_keep_highest_and_lowest():
    r = dice.roll("4d6kh3", FixedRng([2, 6, 3, 5]))
    assert r.total == 14 and r.detail == "[~2, 6, 3, 5]"
    r = dice.roll("4d6kl1", FixedRng([2, 6, 3, 5]))
    assert r.total == 2
    r = dice.roll("3d6k2", FixedRng([1, 6, 3]))        # k2 == kh2
    assert r.total == 9


def test_advantage_disadvantage_and_label():
    r = dice.roll("d20+5 adv Perception check", FixedRng([4, 17]))
    assert r.total == 22 and r.mode == "adv" and r.label == "Perception check"
    assert r.detail == "[~4, 17] + 5" and r.expression == "2d20kh1+5 adv"
    r = dice.roll("d20+5 dis", FixedRng([4, 17]))
    assert r.total == 9
    with pytest.raises(DiceError):
        dice.parse_command("2d6 adv")


def test_crit_detection():
    assert dice.roll("d20", FixedRng([20])).crit == "nat20"
    assert dice.roll("d20+7", FixedRng([1])).crit == "nat1"
    assert dice.roll("d20 adv", FixedRng([1, 20])).crit == "nat20"
    assert dice.roll("d20 adv", FixedRng([1, 3])).crit == ""
    assert dice.roll("2d20", FixedRng([20, 20])).crit == ""
    assert dice.roll("d12", FixedRng([12])).crit == ""


@pytest.mark.parametrize("bad", ["", "hello", "5", "d1", "0d6", "101d6", "d1001", "2d6kh3", "2d6+",
                                 "+", "d20++3", "1d4" + "+1d4" * 20])
def test_bad_input(bad):
    with pytest.raises(DiceError):
        dice.parse_command(bad)


def test_real_rng_stays_in_range():
    for _ in range(200):
        r = dice.roll("3d6+2")
        assert 5 <= r.total <= 20


def test_split_command():
    assert dice.split_command("/roll 2d6") == ("/roll", "2d6")
    assert dice.split_command("  /R d20 ") == ("/r", "d20")
    assert dice.split_command("hi there") == ("", "hi there")
