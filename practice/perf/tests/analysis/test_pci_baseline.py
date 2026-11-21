"""Checks exercises/analysis/pci_baseline.py: a history file, a baseline with a noise measure, and a comparison.

The real data is support/pci_data/history.json: run summaries of real 4-second Locust runs of the practice API,
captured on 21 November 2026 (12 runs of the baseline build, then runs of the same build, a slightly slower
build, a clearly slower one and one that fails a fifth of its payment creations)."""

import json

import pytest
from analysis.pci_baseline import baseline, compare, load_history, save_run, tolerance
from pci_fixture import history

pytestmark = pytest.mark.exercise


def test_a_missing_history_file_is_an_empty_history(tmp_path):
    assert load_history(tmp_path / "nothing.json") == []


def test_a_broken_history_file_is_an_error_not_an_empty_history(tmp_path):
    bad = tmp_path / "h.json"
    bad.write_text("{not json")
    with pytest.raises(ValueError):
        load_history(bad)
    bad.write_text('{"p95_ms": 50}')  # valid JSON, but not a list of runs
    with pytest.raises(ValueError):
        load_history(bad)


def test_save_run_appends_and_keeps_only_the_newest_runs(tmp_path):
    path = tmp_path / "h.json"
    for n in range(1, 6):
        saved = save_run(path, {"build": f"b{n}", "p95_ms": 50 + n}, keep=3)
    assert [r["build"] for r in saved] == ["b3", "b4", "b5"]
    assert json.loads(path.read_text()) == saved
    assert load_history(path) == saved


def test_save_run_leaves_no_temporary_file_and_never_overwrites_a_broken_file(tmp_path):
    path = tmp_path / "h.json"
    save_run(path, {"build": "b1", "p95_ms": 50})
    assert [p.name for p in tmp_path.iterdir()] == ["h.json"]
    path.write_text("oops")
    with pytest.raises(ValueError):
        save_run(path, {"build": "b2", "p95_ms": 51})
    assert path.read_text() == "oops"  # the damaged file is left for a person to look at


def test_baseline_is_the_median_and_mad_of_the_last_runs():
    runs = [{"p95_ms": v} for v in (10, 12, 11, 13, 10)]
    # median 11; deviations 1, 1, 0, 2, 1 -> their median is 1
    assert baseline(runs) == {"median": 11, "mad": 1, "n": 5}
    # only the newest `window` runs count: 11, 13, 10 -> median 11, deviations 0, 2, 1 -> MAD 1
    assert baseline(runs, window=3) == {"median": 11, "mad": 1, "n": 3}


def test_baseline_skips_runs_without_the_metric_and_needs_three_runs():
    runs = [{"p95_ms": 10}, {"build": "no metric"}, {"p95_ms": 12}, {"p95_ms": 11}]
    assert baseline(runs) == {"median": 11, "mad": 1, "n": 3}
    assert baseline(runs[:3]) is None  # only two runs have p95_ms
    assert baseline([]) is None
    assert baseline([{"p99_ms": 1}, {"p99_ms": 2}, {"p99_ms": 3}], metric="p99_ms")["median"] == 2


def test_tolerance_is_the_floor_until_the_baseline_is_noisier_than_the_floor():
    assert tolerance({"median": 100, "mad": 0}) == 0.05
    # scaled MAD = 5 / 0.6745 = 7.413 ms, times k = 3, over 100 ms
    assert tolerance({"median": 100, "mad": 5}) == pytest.approx(0.2224, abs=0.0001)
    assert tolerance({"median": 100, "mad": 5}, k=1) == pytest.approx(0.0741, abs=0.0001)
    assert tolerance({"median": 100, "mad": 1}, floor=0.10) == 0.10


def test_compare_names_regressions_improvements_and_noise():
    base = {"median": 100, "mad": 0}
    assert compare(base, 110) == {"change": 0.1, "tolerance": 0.05, "status": "regression"}
    assert compare(base, 90) == {"change": -0.1, "tolerance": 0.05, "status": "improvement"}
    assert compare(base, 103)["status"] == "within noise"


def test_a_change_exactly_at_the_tolerance_is_still_noise():
    base = {"median": 100, "mad": 0}
    assert compare(base, 105)["status"] == "within noise"
    assert compare(base, 95)["status"] == "within noise"
    assert compare(base, 106)["status"] == "regression"


def test_compare_refuses_a_baseline_of_zero():
    with pytest.raises(ValueError):
        compare({"median": 0, "mad": 0}, 10)


def test_the_captured_baseline_is_a_median_of_64_ms_and_the_mad_decides_the_tolerance():
    base = baseline(history()["main"])  # the last 10 of 12 runs (the first two include a slow start)
    assert base["n"] == 10
    assert base["median"] == 64 and base["mad"] == 1
    # 3 x scaled MAD = 3 x 1 / 0.6745 = 4.45 ms = 6.95 % of the median, above the 5 % floor
    assert tolerance(base) == pytest.approx(0.0695, abs=0.0001)
    assert baseline(history()["main"], window=12)["median"] == 64


def test_captured_runs_of_the_same_build_are_noise_and_a_slower_build_is_a_regression():
    runs = history()
    base = baseline(runs["main"])
    assert [compare(base, r["p95_ms"])["status"] for r in runs["same"]] == ["within noise"] * 3
    assert [compare(base, r["p95_ms"])["status"] for r in runs["slower"]] == ["regression"] * 3


def test_a_ten_percent_slower_service_is_caught_by_some_runs_and_missed_by_others():
    """The 22 ms build (a service time 10 % longer) gave p95 of 67, 69 and 70 ms against a baseline median of 64: one
    run is inside the tolerance and two are outside it. One run is not enough evidence either way."""
    runs = history()
    base = baseline(runs["main"])
    assert [r["p95_ms"] for r in runs["small"]] == [67, 69, 70]
    assert [compare(base, r["p95_ms"])["status"] for r in runs["small"]] == ["within noise", "regression", "regression"]


def test_a_failing_build_hides_in_a_p95_comparison():
    runs = history()
    base = baseline(runs["main"])
    assert all(r["errors"] > 15 for r in runs["failing"])
    assert [compare(base, r["p95_ms"])["status"] for r in runs["failing"]] == ["within noise"] * 3
