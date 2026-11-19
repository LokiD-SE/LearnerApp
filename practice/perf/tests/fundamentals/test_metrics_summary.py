"""Summarise a real JTL and compare with JMeter's own dashboard (statistics.json) for the same file."""

import pytest
from fundamentals.metrics_summary import share_slower_than_mean, summarise
from load_tools import jmeter_home
from metrics_fixture import jmeter_quotes_run

pytestmark = [
    pytest.mark.exercise,
    pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)"),
]

KEYS = {"samples": "sampleCount", "errors": "errorCount", "error_pct": "errorPct", "mean_ms": "meanResTime",
        "min_ms": "minResTime", "max_ms": "maxResTime", "median_ms": "medianResTime", "p90_ms": "pct1ResTime",
        "p95_ms": "pct2ResTime", "p99_ms": "pct3ResTime", "throughput_per_s": "throughput"}


def row(ts, elapsed, label="GET quote", ok=True):
    return {"timeStamp": str(ts), "elapsed": str(elapsed), "label": label, "responseCode": "200" if ok else "500",
            "success": "true" if ok else "false"}


def test_small_file_by_hand():
    rows = [row(1000, 20), row(1010, 40), row(1050, 450, ok=False), row(1100, 30, label="GET health")]
    s = summarise(rows)
    assert set(s) == {"GET quote", "GET health", "Total"}
    q = s["GET quote"]
    assert (q["samples"], q["errors"], q["min_ms"], q["max_ms"]) == (3, 1, 20, 450)
    assert q["error_pct"] == pytest.approx(100 / 3)
    assert q["mean_ms"] == pytest.approx(170)
    # first start 1000, last end 1050 + 450 = 1500: 3 samples in 0.5 s
    assert q["throughput_per_s"] == pytest.approx(6.0)
    assert s["Total"]["samples"] == 4
    assert s["Total"]["throughput_per_s"] == pytest.approx(4 / 0.5)


def test_custom_percentiles_name_their_keys():
    s = summarise([row(1000 + i, i) for i in range(1, 101)], percentiles=(75, 99.9))
    assert {"p75_ms", "p99.9_ms"} <= set(s["Total"])


def test_empty_file_is_an_error():
    with pytest.raises(ValueError):
        summarise([])


def test_matches_jmeter_dashboard_for_a_real_run():
    run = jmeter_quotes_run()
    mine = summarise(run["rows"])
    assert set(mine) == set(run["statistics"])
    for label, theirs in run["statistics"].items():
        for my_key, their_key in KEYS.items():
            assert mine[label][my_key] == pytest.approx(theirs[their_key], rel=1e-6), (label, my_key)


def test_most_requests_are_faster_than_the_mean_in_a_long_tail():
    run = jmeter_quotes_run()
    ok = [int(r["elapsed"]) for r in run["rows"] if r["label"] == "GET quote"]
    assert share_slower_than_mean(ok) < 0.5  # the slow tail drags the mean above the typical request
    assert share_slower_than_mean([10, 10, 10, 10]) == 0
    with pytest.raises(ValueError):
        share_slower_than_mean([])
