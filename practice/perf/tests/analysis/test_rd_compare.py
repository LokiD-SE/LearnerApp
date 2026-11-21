"""Checks exercises/analysis/rd_compare.py: how much repeated runs differ, and whether a change is bigger.

The real data is support/rd_data/noise.json: the p95 (ms) of five 4-second Locust runs of the practice API at 20 ms
service time (twice) and at 26 ms, captured on 21 November 2026."""

import json

import pytest
from rd_fixture import DATA, load_exercise

pytestmark = pytest.mark.exercise

cmp = load_exercise("analysis/rd_compare.py")


def p95s(name):
    return [r["p95_ms"] for r in json.loads((DATA / "noise.json").read_text())[name]]


def test_spread_is_the_range_over_the_median():
    assert cmp.spread([100, 110, 90]) == pytest.approx(0.2)
    assert cmp.spread([50, 50, 50]) == 0
    assert cmp.spread([10]) == 0
    with pytest.raises(ValueError):
        cmp.spread([])


def test_a_clear_slowdown_is_a_regression_and_a_clear_speed_up_an_improvement():
    base = [100, 104, 98, 101, 99]
    assert cmp.verdict(base, [130, 128, 135, 131, 129]) == "regression"
    assert cmp.verdict(base, [70, 72, 69, 71, 73]) == "improvement"


def test_a_small_change_is_no_difference_either_way():
    base = [100, 104, 98, 101, 99]
    assert cmp.verdict(base, [104, 103, 106, 102, 105]) == "no difference"
    assert cmp.verdict(base, [96, 97, 95, 98, 97]) == "no difference"
    assert cmp.verdict(base, [110, 111, 112, 113, 114], margin=0.2) == "no difference"


def test_a_big_median_shift_with_overlapping_runs_is_inconclusive():
    assert cmp.verdict([100, 140, 100, 100, 100], [130, 90, 135, 132, 131]) == "inconclusive"
    assert cmp.verdict([100, 100, 100, 160, 100], [90, 60, 65, 105, 61]) == "inconclusive"


def test_too_few_runs_are_never_a_verdict():
    assert cmp.verdict([100, 101], [200, 201, 202]) == "inconclusive"
    assert cmp.verdict([100, 101, 102], [200, 201]) == "inconclusive"
    assert cmp.verdict([], []) == "inconclusive"


def test_the_margin_decides_what_counts_as_big():
    base, cand = [100, 100, 101, 100, 99], [112, 113, 112, 111, 112]
    assert cmp.verdict(base, cand, margin=0.10) == "regression"
    assert cmp.verdict(base, cand, margin=0.15) == "no difference"


def test_generator_overload_is_any_sample_above_the_threshold():
    assert cmp.generator_overloaded([40, 55, 91]) is True
    assert cmp.generator_overloaded([40, 55, 90]) is False  # 90 is not above 90
    assert cmp.generator_overloaded([40, 99], threshold=99) is False
    assert cmp.generator_overloaded([]) is False


def test_real_repeated_runs_vary_a_little_but_not_as_much_as_a_real_slowdown():
    base, again, slower = p95s("baseline"), p95s("same_again"), p95s("candidate")
    assert 0 < cmp.spread(base) < 0.2  # identical runs still differ
    assert cmp.verdict(base, again) == "no difference"  # the same build twice
    assert cmp.verdict(base, slower) == "regression"  # a 30 % slower service stands out
    assert cmp.verdict(slower, base) == "improvement"
