"""Checks exercises/analysis/tc_summary.py: JMeter's and Locust's results in one summary.

Hand-made rows and histograms with the arithmetic worked out in comments; then one real JMeter result file and one
real Locust result file of the same checkout scenario (support/tc_data, captured 21 November 2026); and one fresh
real JMeter run of the shipped plan."""

import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pytest
import tc_fixture as fx
from analysis.tc_summary import (bucket, locust_percentile, mix, percentile, same_scenario, summarise_jtl,
                                 summarise_locust)

pytestmark = pytest.mark.exercise

BUSINESS = ("GET /v1/payments", "POST /v1/payments", "GET /v1/payments/{id}")


def row(ts, elapsed, label, ok=True):
    return {"timeStamp": str(ts), "elapsed": str(elapsed), "label": label, "success": "true" if ok else "false"}


def test_percentile_is_nearest_rank_on_exact_values():
    values = [50, 10, 40, 20, 30]
    assert percentile(values, 0.5) == 30  # ceil(0.5 x 5) = 3rd smallest
    assert percentile(values, 0.95) == 50  # ceil(4.75) = 5th
    assert percentile(values, 0.2) == 10  # ceil(1.0) = 1st
    assert percentile(values, 0) == 10  # never rank 0
    assert percentile(list(range(1, 11)), 0.9) == 9  # ceil(9.0) = 9th, not the 10th
    assert percentile([], 0.5) is None
    assert values == [50, 10, 40, 20, 30]  # the input is not reordered


def test_bucket_is_locusts_rounding():
    assert [bucket(v) for v in (7, 99.6, 100, 147, 150, 999, 1000, 3432, 58760)] == [7, 100, 100, 150, 150, 1000, 1000, 3400, 59000]
    assert all(isinstance(bucket(v), int) for v in (7.4, 147.2, 3432.9, 58760.1))


def test_locust_percentile_follows_locusts_rule_not_nearest_rank():
    hist = {10: 5, 20: 3, 150: 2}  # ten requests
    # allowed = int(10 x 0.5) = 5; from the top: 150 -> seen 2 (10 - 2 = 8 > 5), 20 -> seen 5 (10 - 5 = 5 <= 5): 20
    assert locust_percentile(hist, 10, 0.5) == 20
    assert percentile([10] * 5 + [20] * 3 + [150] * 2, 0.5) == 10  # the two rules differ here, by one rank
    assert locust_percentile(hist, 10, 0.95) == 150  # allowed 9: 150 -> 10 - 2 = 8 <= 9
    assert locust_percentile(hist, 10, 0.1) == 10  # allowed 1: reaches 10 only after all the others
    assert locust_percentile({"10": 5, "20": 3, "150": 2}, 10, 0.5) == 20  # string keys, as in the JSON file
    assert locust_percentile({}, 0, 0.5) == 0


def test_summarise_jtl_counts_failures_and_percentiles_per_label():
    rows = [row(1000, 10, "A"), row(1500, 20, "A"), row(2000, 30, "A", ok=False),
            row(2500, 100, "B"), row(3000, 200, "B"), row(3000, 300, "B")]
    s = summarise_jtl(rows)
    assert s["requests"] == 6 and s["failures"] == 1
    assert list(s["labels"]) == ["A", "B"]
    assert s["labels"]["A"] == {"requests": 3, "failures": 1, "p50": 20, "p95": 30}  # the failed row is counted in the times
    assert s["labels"]["B"] == {"requests": 3, "failures": 0, "p50": 200, "p95": 300}
    assert s["rps"] == 2.5  # (6 - 1) requests over (3000 - 1000) ms
    assert summarise_jtl([row(5, 1, "A")])["rps"] == 0.0  # no span, no rate


def test_summarise_locust_uses_the_histogram_and_skips_aggregated():
    entry = {"num_requests": 10, "num_failures": 1, "response_times": {"10": 5, "20": 3, "150": 2},
             "start_time": 0.0, "last_request_timestamp": 5.0}
    other = {"num_requests": 5, "num_failures": 0, "response_times": {"30": 5}, "start_time": 0.5,
             "last_request_timestamp": 4.0}
    s = summarise_locust({"A": entry, "B": other, "Aggregated": {**entry, "num_requests": 15}})
    assert s["requests"] == 15 and s["failures"] == 1
    assert s["labels"]["A"] == {"requests": 10, "failures": 1, "p50": 20, "p95": 150}
    assert s["labels"]["B"] == {"requests": 5, "failures": 0, "p50": 30, "p95": 30}
    assert s["rps"] == 2.8  # (15 - 1) requests over 5.0 - 0.0 seconds


def test_mix_and_same_scenario_compare_shares_not_totals():
    a = {"requests": 100, "labels": {"x": {"requests": 90}, "y": {"requests": 10}}}
    b = {"requests": 1000, "labels": {"x": {"requests": 905}, "y": {"requests": 95}}}  # ten times the traffic, same mix
    assert mix(a) == {"x": 0.9, "y": 0.1}
    assert same_scenario(a, b) == []
    c = {"requests": 100, "labels": {"x": {"requests": 70}, "y": {"requests": 30}}}
    assert same_scenario(a, c) == ["x: 90.0% of the first run, 70.0% of the second",
                                   "y: 10.0% of the first run, 30.0% of the second"]
    assert same_scenario(a, c, tolerance=0.25) == []
    d = {"requests": 100, "labels": {"x": {"requests": 90}, "z": {"requests": 10}}}
    assert same_scenario(a, d) == ["y: only in the first run", "z: only in the second run"]
    assert mix({"requests": 0, "labels": {}}) == {}


def test_the_two_captured_results_describe_the_same_scenario():
    j, l = summarise_jtl(fx.jtl_rows()), summarise_locust(fx.locust_entries())
    assert set(j["labels"]) == set(l["labels"]) == {"POST /auth/token", *BUSINESS}
    assert j["labels"]["POST /auth/token"]["requests"] == l["labels"]["POST /auth/token"]["requests"] == 10  # once per user
    for s in (j, l):
        assert s["failures"] == 0
        counts = [s["labels"][name]["requests"] for name in BUSINESS]
        assert max(counts) - min(counts) <= 10  # ten users: each may be mid-iteration when the run ends
        assert all(s["labels"][n]["p50"] <= s["labels"][n]["p95"] for n in s["labels"])
    assert same_scenario(j, l) == []
    assert (j["requests"], j["rps"]) == (1180, 120.3)
    assert (l["requests"], l["rps"]) == (1123, 118.0)
    assert j["labels"]["POST /auth/token"]["p50"] > 3 * l["labels"]["POST /auth/token"]["p50"]  # JMeter's first call: 125 ms


def test_a_run_without_the_sign_in_is_not_the_same_scenario():
    entries = {k: v for k, v in fx.locust_entries().items() if k != "POST /auth/token"}
    problems = same_scenario(summarise_jtl(fx.jtl_rows()), summarise_locust(entries))
    assert problems == ["POST /auth/token: only in the first run"]  # the other shares still agree


def test_a_fresh_jmeter_run_of_the_shipped_plan_has_the_scenarios_shape():
    with tempfile.TemporaryDirectory() as tmp, fx.with_target() as base:
        _, jtl = fx.run_jmeter_scenario(Path(tmp), urlparse(base).port, threads=3, seconds=3, wait_ms=200)
        s = summarise_jtl(fx.read_jtl(jtl))
    assert set(s["labels"]) == {"POST /auth/token", *BUSINESS}
    assert s["labels"]["POST /auth/token"]["requests"] == 3  # the Once Only Controller: one sign-in per thread
    counts = [s["labels"][name]["requests"] for name in BUSINESS]
    assert min(counts) >= 6 and max(counts) - min(counts) <= 3
    assert s["failures"] == 0
