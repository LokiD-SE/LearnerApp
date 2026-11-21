"""Checks exercises/locust/lc_shape_history.py: reading a real _stats_history.csv by phase.

The rows in tests/support are real: see support/lc_shape_fixture.py."""

import pytest
from lc_shape_fixture import HISTORY_SLOW_RAMP, HISTORY_SPIKE, load_exercise

pytestmark = pytest.mark.exercise

history = load_exercise("locust/lc_shape_history.py")


def row(users, total):
    return {"Timestamp": "0", "User Count": str(users), "Total Request Count": str(total)}


def test_phases_of_the_real_spike_run():
    assert history.phases(HISTORY_SPIKE) == [
        {"users": 0, "seconds": 1, "requests": 0, "rps": 0.0},
        {"users": 2, "seconds": 3, "requests": 80, "rps": 26.7},
        {"users": 20, "seconds": 4, "requests": 770, "rps": 192.5},
        {"users": 2, "seconds": 4, "requests": 107, "rps": 26.8},
    ]


def test_phases_of_the_real_slow_ramp_run():
    got = history.phases(HISTORY_SLOW_RAMP)
    assert [(p["users"], p["seconds"]) for p in got] == [(0, 1), (1, 1), (2, 1), (3, 1), (4, 3), (2, 3)]
    assert sum(p["requests"] for p in got) == 321  # the last running total: nothing lost between phases


def test_a_user_count_that_comes_back_is_a_new_phase():
    got = history.phases([row(2, 10), row(5, 30), row(2, 40), row(2, 55)])
    assert [(p["users"], p["seconds"], p["requests"], p["rps"]) for p in got] == [
        (2, 1, 10, 10.0), (5, 1, 20, 20.0), (2, 2, 25, 12.5)]


def test_no_rows_no_phases():
    assert history.phases([]) == []
    assert history.peak_users([]) == 0
    assert history.missed_targets([], [5]) == [5]


def test_peak_users():
    assert history.peak_users(HISTORY_SPIKE) == 20
    assert history.peak_users(HISTORY_SLOW_RAMP) == 4


def test_missed_targets_finds_the_stage_that_never_got_its_users():
    assert history.missed_targets(HISTORY_SLOW_RAMP, [10, 4, 2]) == [10]
    assert history.missed_targets(HISTORY_SPIKE, [20, 2, 2]) == []
    assert history.missed_targets(HISTORY_SPIKE, [50, 20, 30, 50]) == [30, 50]
