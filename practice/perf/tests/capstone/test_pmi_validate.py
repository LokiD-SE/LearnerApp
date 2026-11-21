"""Checks pmi_validate.py, then runs a real closed-model load (a few seconds, loopback only) and checks the
verdicts: Little's law holds when you plug in what the run measured, and breaks when you plug in the plan."""

import pytest
from capstone.pmi_sizing import throughput_for_users
from capstone.pmi_validate import compare, explain
from pmi_fixture import run_closed, serve_separately

pytestmark = pytest.mark.exercise


def test_compare_within_tolerance():
    assert compare(100, 100) == "as_predicted"
    assert compare(100, 90) == "as_predicted"
    assert compare(100, 110) == "as_predicted"


def test_compare_outside_tolerance():
    assert compare(100, 89) == "below_prediction"
    assert compare(100, 111) == "above_prediction"
    assert compare(100, 50, tolerance=0.6) == "as_predicted"


def test_compare_rejects_nonsense():
    with pytest.raises(ValueError):
        compare(0, 10)
    with pytest.raises(ValueError):
        compare(10, -1)
    with pytest.raises(ValueError):
        compare(10, 10, tolerance=1.0)


def test_each_verdict_has_its_own_explanation():
    texts = {v: explain(v) for v in ("as_predicted", "below_prediction", "above_prediction")}
    assert len(set(texts.values())) == 3
    assert "satur" in texts["below_prediction"].lower()
    with pytest.raises(ValueError):
        explain("nope")


@pytest.fixture(scope="module")
def runs():
    """Two short runs: a healthy target, and one that has a single worker for the same eight users."""
    with serve_separately(latency_ms=20, capacity=16) as base:
        healthy = run_closed(base, 8, 2.5, think_s=0.05)
    with serve_separately(latency_ms=20, capacity=1) as base:
        starved = run_closed(base, 8, 2.5, think_s=0.05)
    return healthy, starved


def test_littles_law_holds_with_the_measured_response_time(runs):
    healthy, _ = runs
    predicted = throughput_for_users(8, healthy["mean_ms"] / 1000, 0.05)
    assert compare(predicted, healthy["achieved_rps"], tolerance=0.15) == "as_predicted"


def test_the_plan_is_met_when_the_target_has_room(runs):
    healthy, _ = runs
    planned = throughput_for_users(8, 0.02, 0.05)
    assert compare(planned, healthy["achieved_rps"], tolerance=0.2) == "as_predicted"


def test_the_plan_is_missed_when_the_target_queues(runs):
    _, starved = runs
    planned = throughput_for_users(8, 0.02, 0.05)
    assert compare(planned, starved["achieved_rps"], tolerance=0.2) == "below_prediction"
    # ... and Little's law still holds if you plug in what actually happened
    predicted = throughput_for_users(8, starved["mean_ms"] / 1000, 0.05)
    assert compare(predicted, starved["achieved_rps"], tolerance=0.15) == "as_predicted"
