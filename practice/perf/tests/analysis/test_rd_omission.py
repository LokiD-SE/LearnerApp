"""Checks exercises/analysis/rd_omission.py: finding what a stalled closed-loop run never sent, and correcting it.

Hand-made rows first, then the JTL rows of a real paced JMeter run captured on 21 November 2026
(support/rd_data/stall.csv: 20 requests per second, the service frozen for 1.5 s after request 80), then one
fresh run."""

import tempfile
from pathlib import Path

import pytest
from rd_fixture import ServiceConfig, load_exercise, read_rows, run_paced

pytestmark = pytest.mark.exercise

om = load_exercise("analysis/rd_omission.py")


def row(ts, elapsed, ok=True):
    return {"timeStamp": str(ts), "elapsed": str(elapsed), "success": "true" if ok else "false"}


def test_percentile_is_nearest_rank_and_rejects_nothing():
    assert [om.percentile(list(range(1, 11)), p) for p in (50, 90, 95, 100)] == [5, 9, 10, 10]
    with pytest.raises(ValueError):
        om.percentile([], 95)


def test_a_slow_value_implies_the_values_that_were_never_measured():
    assert om.fill_expected_interval([100], 30) == [100, 70, 40]
    assert om.fill_expected_interval([100], 50) == [100, 50]
    assert om.fill_expected_interval([1500], 500) == [1500, 1000, 500]


def test_values_within_the_interval_are_left_alone_and_order_is_kept():
    assert om.fill_expected_interval([10, 20, 30], 50) == [10, 20, 30]
    assert om.fill_expected_interval([5, 120, 7], 50) == [5, 120, 70, 7]
    assert om.fill_expected_interval([], 50) == []
    assert om.fill_expected_interval([100], 0) == [100]  # no known interval, nothing to infer


def test_find_gaps_reports_holes_in_the_start_times():
    rows = [row(0, 5), row(50, 5), row(100, 5), row(1_600, 5), row(1_650, 5)]
    assert om.find_gaps(rows, 50) == [{"after_s": 0.1, "gap_ms": 1500, "missing": 29}]


def test_find_gaps_ignores_small_gaps_sorts_rows_and_handles_nothing():
    rows = [row(500, 5), row(0, 5), row(240, 5), row(260, 5)]
    assert om.find_gaps(rows, 50) == []  # 240 ms is under 5 x 50
    assert om.find_gaps(rows, 50, factor=2) == [{"after_s": 0.0, "gap_ms": 240, "missing": 3},
                                                {"after_s": 0.3, "gap_ms": 240, "missing": 3}]
    assert om.find_gaps([], 50) == []
    assert om.find_gaps([row(0, 5)], 50) == []


def test_corrected_percentiles_use_successes_only_and_show_both_views():
    rows = [row(i * 50, 10) for i in range(198)] + [row(10_000, 2_000), row(10_050, 8, ok=False)]
    got = om.corrected_percentiles(rows, 50)
    assert got["measured"] == {"p50": 10, "p95": 10, "p99": 10}
    # 198 fast + 1 slow value + 39 implied values (1950, 1900 ... 50): the slow moment now reaches the tail
    assert got["corrected"]["p50"] == 10 and got["corrected"]["p95"] > 1_000 and got["corrected"]["p99"] == 1_900


def test_a_real_stalled_run_hides_its_stall_until_it_is_corrected():
    rows = read_rows("stall.csv")
    assert len(rows) == 174  # a 10 s run at 20 per second should have sent about 200
    gaps = om.find_gaps(rows, 50)
    assert len(gaps) == 1 and 1_000 < gaps[0]["gap_ms"] < 2_000 and 20 <= gaps[0]["missing"] <= 30
    got = om.corrected_percentiles(rows, 200)  # 4 threads sharing 20 per second: 200 ms per thread
    assert got["measured"]["p95"] < 100 < 1_000 < got["measured"]["p99"]
    assert got["corrected"]["p95"] > 500 and got["corrected"]["p95"] > 20 * got["measured"]["p95"]
    assert len(om.fill_expected_interval([int(r["elapsed"]) for r in rows], 200)) - len(rows) == 23


def test_a_fresh_stalled_run_gives_the_same_picture():
    config = ServiceConfig(base_ms=10, stall_at=60, stall_s=1.5)
    rows = run_paced(Path(tempfile.mkdtemp(prefix="rd-test-stall-")), config, per_minute=1200, threads=4, seconds=8)
    gaps = om.find_gaps(rows, 50)
    assert any(g["gap_ms"] > 1_000 for g in gaps)
    got = om.corrected_percentiles(rows, 200)
    assert got["measured"]["p95"] < 200 and got["corrected"]["p95"] > 5 * got["measured"]["p95"]
