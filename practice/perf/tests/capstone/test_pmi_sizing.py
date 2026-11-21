"""Checks pmi_sizing.py: the whiteboard arithmetic of a performance-testing interview."""

import pytest
from capstone.pmi_sizing import (arrival_rate, pacing_interval, throughput_for_users, users_for_throughput,
                                 workers_needed)

pytestmark = pytest.mark.exercise


def test_arrival_rate_at_the_average_and_at_a_peak():
    assert arrival_rate(864_000) == pytest.approx(10.0)
    assert arrival_rate(864_000, peak_factor=3) == pytest.approx(30.0)


def test_arrival_rate_rejects_a_peak_below_the_average_and_negative_volume():
    with pytest.raises(ValueError):
        arrival_rate(1000, peak_factor=0.5)
    with pytest.raises(ValueError):
        arrival_rate(-1)


def test_users_follow_littles_law_and_round_up():
    # 100 requests/s, 0.2 s to answer, 0.8 s of thinking: 100 * 1.0 = 100 users
    assert users_for_throughput(100, 0.2, 0.8) == 100
    # 12.2 users is 13 users
    assert users_for_throughput(10, 0.22, 1.0) == 13


def test_users_with_no_think_time_is_just_concurrency():
    assert users_for_throughput(50, 0.1, 0) == 5


def test_throughput_is_users_over_cycle_time():
    assert throughput_for_users(8, 0.02, 0.05) == pytest.approx(8 / 0.07)
    assert throughput_for_users(100, 0.2, 0.8) == pytest.approx(100.0)


def test_the_two_formulas_are_inverses_up_to_rounding():
    users = users_for_throughput(37.5, 0.12, 0.4)
    assert throughput_for_users(users, 0.12, 0.4) >= 37.5


def test_throughput_needs_some_waiting_time():
    with pytest.raises(ValueError):
        throughput_for_users(5, 0, 0)
    with pytest.raises(ValueError):
        throughput_for_users(-1, 0.1, 0.1)


def test_workers_keep_utilisation_at_the_target():
    # 100 req/s * 0.05 s = 5 busy workers on average; at 70% that is 7.14 -> 8
    assert workers_needed(100, 0.05) == 8
    assert workers_needed(100, 0.05, max_utilisation=1.0) == 5


def test_workers_reject_nonsense():
    for args in [(-1, 0.1), (10, -0.1)]:
        with pytest.raises(ValueError):
            workers_needed(*args)
    for u in (0, -0.1, 1.5):
        with pytest.raises(ValueError):
            workers_needed(10, 0.1, max_utilisation=u)


def test_pacing_interval_spreads_the_rate_over_users():
    assert pacing_interval(10, 5) == pytest.approx(2.0)
    assert pacing_interval(1, 4) == pytest.approx(0.25)


def test_pacing_rejects_zero():
    with pytest.raises(ValueError):
        pacing_interval(0, 5)
    with pytest.raises(ValueError):
        pacing_interval(5, 0)
