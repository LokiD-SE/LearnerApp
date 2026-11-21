"""Checks exercises/analysis/rd_timeline.py: windows, warm-up and the steady state of a load test run.

The tests use hand-made rows, the JTL rows of a real JMeter run captured on 21 November 2026
(support/rd_data/warmup.csv) and one fresh JMeter run against the cold-start service."""

import tempfile
from pathlib import Path

import pytest
from rd_fixture import ServiceConfig, load_exercise, read_rows, run_closed

pytestmark = pytest.mark.exercise

tl = load_exercise("analysis/rd_timeline.py")


def row(ts, elapsed, ok=True):
    return {"timeStamp": str(ts), "elapsed": str(elapsed), "success": "true" if ok else "false"}


def test_percentile_is_nearest_rank():
    assert tl.percentile([5, 1, 4, 2, 3], 50) == 3
    assert tl.percentile([10, 20, 30, 40], 25) == 10
    assert tl.percentile([10, 20, 30, 40], 26) == 20
    assert tl.percentile(list(range(1, 101)), 95) == 95
    assert tl.percentile([7], 99) == 7


def test_percentile_of_nothing_raises():
    with pytest.raises(ValueError):
        tl.percentile([], 50)


def test_windows_group_by_start_time_from_the_first_sample():
    rows = [row(10_000, 10), row(10_400, 30), row(10_999, 20), row(11_000, 100), row(11_500, 300)]
    w = tl.windows(rows)
    assert [(x["start"], x["samples"], x["p50"], x["p95"], x["rps"]) for x in w] == [
        (0.0, 3, 20, 30, 3.0), (1.0, 2, 100, 300, 2.0)]


def test_windows_keep_empty_windows_and_count_errors_separately():
    rows = [row(0, 10), row(100, 5000, ok=False), row(3_200, 40)]
    w = tl.windows(rows)
    assert [x["samples"] for x in w] == [2, 0, 0, 1]
    assert w[0]["errors"] == 1 and w[0]["p50"] == 10 and w[0]["p95"] == 10  # the failure is not a response time
    assert w[1] == {"start": 1.0, "samples": 0, "errors": 0, "p50": None, "p95": None, "rps": 0.0}


def test_windows_of_two_seconds_and_of_nothing():
    rows = [row(0, 1), row(1_900, 2), row(2_000, 3)]
    w = tl.windows(rows, seconds=2)
    assert [(x["start"], x["samples"], x["rps"]) for x in w] == [(0.0, 2, 1.0), (2.0, 1, 0.5)]
    assert tl.windows([]) == []


def test_windows_do_not_need_sorted_rows():
    w = tl.windows([row(5_000, 9), row(0, 1)])
    assert [x["samples"] for x in w] == [1, 0, 0, 0, 0, 1]


def wins(p50s):
    return [{"start": float(i), "samples": 10, "errors": 0, "p50": p, "p95": p, "rps": 10.0} for i, p in enumerate(p50s)]


def test_steady_start_finds_the_end_of_the_warm_up():
    assert tl.steady_start(wins([300, 200, 60, 31, 30, 32, 30, 31])) == 3.0


def test_steady_start_needs_a_run_of_windows_and_a_reference():
    assert tl.steady_start(wins([30, 100, 30, 100, 30, 100])) is None  # never three in a row near the reference
    assert tl.steady_start(wins([30, 30])) is None  # not enough windows for a run of three
    assert tl.steady_start(wins([None, None, None, None])) is None
    assert tl.steady_start([]) is None


def test_steady_start_respects_tolerance_and_run_length():
    p50s = [40, 40, 40, 32, 32, 32, 32, 32]
    assert tl.steady_start(wins(p50s), tolerance=0.25) == 0.0  # 40 is exactly 25 % above 32
    assert tl.steady_start(wins(p50s), tolerance=0.10) == 3.0
    assert tl.steady_start(wins([300, 30, 31, 30, 30, 31, 30, 30]), run=5) == 1.0


def test_steady_summary_keeps_only_samples_after_the_warm_up():
    rows = [row(0, 900), row(500, 800), row(1_000, 10), row(1_500, 20), row(2_000, 30, ok=False), row(2_500, 40)]
    assert tl.steady_summary(rows, 1) == {"samples": 4, "errors": 1, "p50": 20, "p95": 40, "p99": 40}
    whole = tl.steady_summary(rows, 0)
    assert whole["samples"] == 6 and whole["p95"] == 900
    assert tl.steady_summary(rows, 100) == {"samples": 0, "errors": 0, "p50": None, "p95": None, "p99": None}


def test_a_real_cold_start_run_shows_a_warm_up_then_a_steady_state():
    rows = read_rows("warmup.csv")
    w = tl.windows(rows)
    assert w[0]["p50"] > 5 * w[-2]["p50"]  # the first second is far slower than the last full second
    start = tl.steady_start(w)
    assert start is not None and 2.0 <= start <= 4.0
    steady, whole = tl.steady_summary(rows, start), tl.steady_summary(rows, 0)
    assert steady["p95"] < whole["p95"] / 3 and steady["p99"] < whole["p99"] / 3
    assert steady["samples"] > 0.8 * whole["samples"]


def test_a_fresh_run_against_the_cold_start_service_shows_the_same_shape():
    config = ServiceConfig(base_ms=20, warmup_requests=60, warmup_extra_ms=300)
    rows = run_closed(Path(tempfile.mkdtemp(prefix="rd-test-warm-")), config, threads=4, seconds=6)
    w = tl.windows(rows)
    assert w[0]["p50"] > 3 * w[-2]["p50"]
    start = tl.steady_start(w)
    assert start is not None and start <= 4.0
    assert tl.steady_summary(rows, start)["p95"] < 120
