"""Percentiles four ways: fixed data with hand-checked answers, then JMeter's dashboard and Locust's final
statistics from real runs against the local quotes service (support/metrics_fixture.py)."""

import statistics
from collections import Counter

import pytest
from fundamentals.metrics_percentiles import (
    aggregate_report_percentile,
    dashboard_percentile,
    locust_bucket,
    locust_percentile,
    nearest_rank,
)
from load_tools import jmeter_home
from metrics_fixture import jmeter_quotes_run, locust_quotes_run

pytestmark = pytest.mark.exercise

TIMES = [12, 15, 20, 22, 25, 30, 95, 140, 480, 510]  # ms, one slow tail
needs_jmeter = pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")


@pytest.mark.parametrize("fn", [nearest_rank, dashboard_percentile, aggregate_report_percentile, locust_percentile])
def test_rejects_empty_and_out_of_range(fn):
    with pytest.raises(ValueError):
        fn([], 90)
    for bad in (0, -5, 100.5):
        with pytest.raises(ValueError):
            fn(TIMES, bad)


def test_nearest_rank_is_always_an_observed_value():
    assert [nearest_rank(TIMES, p) for p in (10, 50, 90, 95, 100)] == [12, 25, 480, 510, 510]
    assert nearest_rank([7], 99) == 7
    assert nearest_rank(reversed(TIMES), 50) == 25  # input order does not matter


def test_dashboard_percentile_interpolates_at_n_plus_1():
    assert dashboard_percentile(TIMES, 50) == pytest.approx(27.5)
    assert dashboard_percentile(TIMES, 90) == pytest.approx(507.0)
    q = statistics.quantiles(TIMES, n=100, method="exclusive")  # the same definition inside the range
    assert dashboard_percentile(TIMES, 50) == pytest.approx(q[49])
    assert dashboard_percentile(TIMES, 90) == pytest.approx(q[89])


def test_dashboard_percentile_clamps_where_python_extrapolates():
    # position (10 + 1) * 0.95 = 10.45 > n: Commons Math LEGACY clamps to the max, statistics.quantiles goes past it
    assert dashboard_percentile(TIMES, 95) == 510
    assert statistics.quantiles(TIMES, n=100, method="exclusive")[94] > 510
    assert dashboard_percentile(TIMES, 5) == 12  # position 0.55 < 1: the min


def test_aggregate_report_rounds_the_count_like_java():
    assert aggregate_report_percentile(TIMES, 50) == 25  # round(5.0) = 5th value
    assert aggregate_report_percentile(TIMES, 94) == 480  # round(9.4) = 9th
    assert aggregate_report_percentile(TIMES, 95) == 510  # round(9.5) = 10th - Java rounds half up
    assert aggregate_report_percentile(TIMES, 100) == 510
    assert aggregate_report_percentile([5, 5, 5, 9], 70) == 5  # duplicates count individually


def test_locust_bucket_keeps_about_two_significant_digits():
    raw = [12.4, 99.6, 101.0, 147.0, 145.0, 155.0, 3432.0, 999.9, 10499.0, 58760.0]
    assert [locust_bucket(x) for x in raw] == [12, 100, 100, 150, 140, 160, 3400, 1000, 10000, 59000]


def test_locust_percentile_walks_buckets_from_the_top():
    assert locust_percentile(TIMES, 50) == 30  # not 25 or 27.5: int(10 * 0.5) = 5 requests may be faster
    assert locust_percentile(TIMES, 90) == 510
    assert locust_percentile([147.0, 151.0, 149.0], 100) == 150  # every value lands in the 150 bucket


@needs_jmeter
def test_dashboard_definition_matches_jmeter_statistics_json():
    run = jmeter_quotes_run()
    stats = run["statistics"]
    for label, entry in stats.items():
        rows = run["rows"] if label == "Total" else [r for r in run["rows"] if r["label"] == label]
        elapsed = [int(r["elapsed"]) for r in rows]
        assert dashboard_percentile(elapsed, 50) == pytest.approx(entry["medianResTime"]), label
        for key, pct in (("pct1ResTime", 90), ("pct2ResTime", 95), ("pct3ResTime", 99)):
            assert dashboard_percentile(elapsed, pct) == pytest.approx(entry[key]), (label, pct)


def test_locust_definition_matches_locust_final_statistics():
    run = locust_quotes_run()
    final = run["final"][0]
    times = [t for _, t in run["raw"]]
    assert len(times) == final["num_requests"]
    assert Counter(locust_bucket(t) for t in times) == {int(k): v for k, v in final["response_times"].items()}
    for pct, expected in run["percentiles"].items():  # computed by Locust's own calculate_response_time_percentile
        assert locust_percentile(times, pct) == expected, pct
