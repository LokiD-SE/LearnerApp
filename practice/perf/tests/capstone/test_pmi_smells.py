"""Checks pmi_smells.py on five real runs captured against the practice target (support/pmi_data/runs.json,
regenerate with support/pmi_capture.py) and on hand-made summaries for the cases the target cannot produce."""

import pytest
from capstone.pmi_smells import next_step, smells, verdict
from pmi_fixture import load_runs

pytestmark = pytest.mark.exercise

RUNS = load_runs()


def hand_made(**changes):
    """A healthy summary with some fields changed. NOT a measured run."""
    base = {"samples": 500, "errors": 0, "duration_s": 5.0, "achieved_rps": 100.0, "planned_rps": 100.0,
            "p50_all_ms": 20.0, "p50_ok_ms": 20.0, "first_third_p95_ms": 30.0, "last_third_p95_ms": 30.0,
            "generator_cpu_pct": 10.0}
    base.update(changes)
    return base


def test_a_healthy_captured_run_has_no_smell():
    assert smells(RUNS["healthy"]) == []
    assert verdict([]) == "trust"


def test_a_run_of_half_a_second_is_too_short():
    assert smells(RUNS["too_short"]) == ["too_few_samples"]


def test_a_burning_generator_is_reported_before_the_rate_it_caused():
    # the run also delivered about half of the planned rate, but the generator explains that
    assert smells(RUNS["slow_generator"]) == ["generator_saturated", "below_plan"]


def test_a_target_that_cannot_keep_up_is_below_plan_and_nothing_else():
    assert smells(RUNS["below_plan"]) == ["below_plan"]


def test_fast_failures_flatter_the_median():
    run = RUNS["fast_failures"]
    assert run["errors"] / run["samples"] > 0.5
    assert run["p50_all_ms"] < run["p50_ok_ms"] / 2
    assert smells(run) == ["fast_failures_flatter_latency"]


def test_a_slow_first_third_is_a_warm_up():
    assert smells(hand_made(first_third_p95_ms=120.0, last_third_p95_ms=30.0)) == ["warmup_included"]


def test_boundaries_are_not_smells():
    assert smells(hand_made(samples=100)) == []
    assert smells(hand_made(generator_cpu_pct=79.9)) == []
    assert smells(hand_made(achieved_rps=90.0)) == []
    assert smells(hand_made(first_third_p95_ms=45.0, last_third_p95_ms=30.0)) == []
    assert smells(hand_made(samples=500, errors=5)) == []  # 1% is allowed, more than 1% is not


def test_boundaries_are_smells_just_past_the_line():
    assert smells(hand_made(samples=99)) == ["too_few_samples"]
    assert smells(hand_made(generator_cpu_pct=80.0)) == ["generator_saturated"]
    assert smells(hand_made(achieved_rps=89.9)) == ["below_plan"]


def test_unknown_generator_cpu_and_no_plan_are_not_smells():
    assert smells(hand_made(generator_cpu_pct=None, planned_rps=None, achieved_rps=1.0)) == []


def test_many_errors_that_are_not_faster_do_not_flatter():
    # the failures took as long as the successes: errors are a problem, but they do not flatter the latency
    assert smells(hand_made(errors=200, p50_all_ms=20.0, p50_ok_ms=20.0)) == []


def test_priority_order_when_everything_smells():
    everything = hand_made(samples=50, errors=40, generator_cpu_pct=95.0, planned_rps=200.0, achieved_rps=10.0,
                           p50_all_ms=2.0, p50_ok_ms=20.0, first_third_p95_ms=90.0, last_third_p95_ms=30.0)
    assert smells(everything) == ["too_few_samples", "generator_saturated", "fast_failures_flatter_latency",
                                  "below_plan", "warmup_included"]


def test_a_missing_key_is_named():
    bad = hand_made()
    del bad["errors"]
    with pytest.raises(ValueError, match="errors"):
        smells(bad)


def test_zero_samples_is_too_few_not_a_division_error():
    assert smells(hand_made(samples=0, errors=0, achieved_rps=0.0)) == ["too_few_samples", "below_plan"]


def test_verdict():
    assert verdict(["below_plan"]) == "rerun"
    assert verdict([]) == "trust"


def test_next_step_follows_the_first_smell_and_each_one_differs():
    advice = {s: next_step([s]) for s in ("too_few_samples", "generator_saturated", "fast_failures_flatter_latency",
                                          "below_plan", "warmup_included")}
    assert len(set(advice.values())) == 5
    assert next_step(["generator_saturated", "below_plan"]) == advice["generator_saturated"]
    assert next_step([]) not in advice.values()
    assert "generator" in advice["generator_saturated"].lower()
    assert "warm" in advice["warmup_included"].lower()
