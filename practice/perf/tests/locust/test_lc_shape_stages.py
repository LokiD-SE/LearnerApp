"""Checks exercises/locust/lc_shape_stages.py: the stage plan functions behind a Locust load shape.

The topic folder is called ``locust``, like the Locust package, so the module is loaded from its file."""

import pytest
from lc_shape_fixture import load_exercise

pytestmark = pytest.mark.exercise

stages = load_exercise("locust/lc_shape_stages.py")

SPIKE = [
    {"duration": 3, "users": 2, "spawn_rate": 10},
    {"duration": 7, "users": 20, "spawn_rate": 20},
    {"duration": 11, "users": 2, "spawn_rate": 20},
]
SLOW_RAMP = [
    {"duration": 3, "users": 10, "spawn_rate": 1},
    {"duration": 6, "users": 4, "spawn_rate": 10},
    {"duration": 9, "users": 2, "spawn_rate": 10},
]


@pytest.mark.parametrize("run_time, expected", [
    (0, (2, 10)), (2.99, (2, 10)), (3, (20, 20)), (6.5, (20, 20)), (7, (2, 20)), (10.99, (2, 20)),
    (11, None), (500, None),
])
def test_tick_picks_the_stage_running_now(run_time, expected):
    assert stages.tick(SPIKE, run_time) == expected


def test_tick_with_no_stages_stops_at_once():
    assert stages.tick([], 0) is None


def test_step_plan_has_cumulative_end_times():
    plan = stages.from_steps(first_users=10, step_users=10, steps=3, step_seconds=60, spawn_rate=5)
    assert plan == [
        {"duration": 60, "users": 10, "spawn_rate": 5},
        {"duration": 120, "users": 20, "spawn_rate": 5},
        {"duration": 180, "users": 30, "spawn_rate": 5},
    ]


def test_step_plan_of_one_step_and_none():
    assert stages.from_steps(4, 2, 1, 30.5, 1) == [{"duration": 30.5, "users": 4, "spawn_rate": 1}]
    assert stages.from_steps(4, 2, 0, 30, 1) == []


def test_a_step_plan_drives_tick_through_every_step_then_stops():
    plan = stages.from_steps(5, 5, 4, 10, 5)
    users = [stages.tick(plan, t)[0] for t in (0, 9.9, 10, 19.9, 20, 29.9, 30, 39.9)]
    assert users == [5, 5, 10, 10, 15, 15, 20, 20]
    assert stages.tick(plan, 40) is None


@pytest.mark.parametrize("a, b, rate, seconds", [(0, 10, 1, 10), (10, 4, 10, 0.6), (2, 20, 6, 3), (5, 5, 2, 0)])
def test_ramp_seconds_goes_both_ways(a, b, rate, seconds):
    assert stages.ramp_seconds(a, b, rate) == pytest.approx(seconds)


@pytest.mark.parametrize("rate", [0, -1])
def test_ramp_needs_a_positive_spawn_rate(rate):
    with pytest.raises(ValueError):
        stages.ramp_seconds(0, 10, rate)


def test_a_sound_plan_has_no_problems():
    assert stages.stage_problems(SPIKE) == []
    assert stages.stage_problems(stages.from_steps(10, 10, 5, 60, 5)) == []


def test_a_ramp_as_long_as_the_stage_is_fine():
    assert stages.stage_problems([{"duration": 10, "users": 10, "spawn_rate": 1}]) == []


def test_a_ramp_longer_than_its_stage_is_reported():
    assert stages.stage_problems(SLOW_RAMP) == [(0, "ramp-too-slow")]


def test_stage_lengths_written_instead_of_end_times_are_reported():
    lengths = [
        {"duration": 60, "users": 10, "spawn_rate": 10},
        {"duration": 60, "users": 20, "spawn_rate": 10},
        {"duration": 60, "users": 30, "spawn_rate": 10},
    ]
    assert stages.stage_problems(lengths) == [(1, "not-increasing"), (2, "not-increasing")]


def test_a_dead_stage_is_skipped_when_judging_the_next_ones():
    plan = [
        {"duration": 10, "users": 10, "spawn_rate": 10},
        {"duration": 5, "users": 50, "spawn_rate": 1},  # never reached, ignored below
        {"duration": 20, "users": 12, "spawn_rate": 1},  # 10 -> 12 at 1/s takes 2 s of its 10 s
    ]
    assert stages.stage_problems(plan) == [(1, "not-increasing")]


def test_problems_come_in_stage_order():
    plan = [
        {"duration": 2, "users": 10, "spawn_rate": 1},
        {"duration": 2, "users": 10, "spawn_rate": 1},
        {"duration": 4, "users": 0, "spawn_rate": 1},
    ]
    assert stages.stage_problems(plan) == [(0, "ramp-too-slow"), (1, "not-increasing"), (2, "ramp-too-slow")]
