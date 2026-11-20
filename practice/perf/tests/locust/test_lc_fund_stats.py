"""Checks exercises/locust/lc_fund_stats.py: reading Locust's --json-file output, Locust-compatible percentiles,
the aggregated row and a CI verdict. The expected numbers for SAMPLE_STATS were printed by Locust 2.47.0's own
locust.stats.calculate_response_time_percentile on the same data."""

import json
import urllib.request

import pytest
from lc_fund_fixture import SAMPLE_STATS, load_exercise, write_locustfile
from load_tools import run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

stats = load_exercise("locust/lc_fund_stats.py")

# key: (requests, failures, avg_ms, p50, p95, p99) - from Locust's own functions
EXPECTED = {
    "POST /auth/token": (5, 0, 39.5, 37, 70, 70),
    "GET /v1/payments": (82, 0, 40.5, 39, 70, 73),
    "GET /v1/reports/settlement": (10, 0, 418.5, 400, 560, 560),
    "POST /v1/payments": (36, 5, 79.8, 86, 140, 140),
}


@pytest.fixture
def sample_file(tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps(SAMPLE_STATS))
    return path


def test_entries_are_keyed_by_method_and_name(sample_file):
    loaded = stats.load_stats(sample_file)
    assert set(loaded) == set(EXPECTED)
    assert stats.entry_key({"method": "POST", "name": "/v1/payments"}) == "POST /v1/payments"


@pytest.mark.parametrize("key", sorted(EXPECTED))
def test_summary_matches_locusts_own_numbers(sample_file, key):
    s = stats.summarise(stats.load_stats(sample_file)[key])
    requests, failures, avg_ms, p50, p95, p99 = EXPECTED[key]
    assert (s["requests"], s["failures"], s["avg_ms"]) == (requests, failures, avg_ms)
    assert (s["p50"], s["p95"], s["p99"]) == (p50, p95, p99)
    assert s["fail_ratio"] == pytest.approx(failures / requests)


def test_percentile_walks_the_histogram_like_locust():
    # Values from locust.stats.calculate_response_time_percentile on the same input. Locust returns the first
    # bucket (walking down from the slowest) below which at most int(n * percent) requests are left, so with
    # exactly 5 of 100 requests at 300 ms its p95 is 300, not 20.
    times = {"10": 50, "20": 45, "300": 5}
    assert stats.percentile(times, 100, 0.95) == 300
    assert stats.percentile(times, 100, 0.94) == 20
    assert stats.percentile(times, 100, 0.50) == 20
    assert stats.percentile({10: 1, 20: 1}, 2, 0.5) == 20  # int keys work too
    assert stats.percentile({}, 0, 0.95) == 0
    with pytest.raises(ValueError):
        stats.percentile(times, 100, 95)


def test_aggregate_merges_histograms_and_adds_counts():
    agg = stats.aggregate(SAMPLE_STATS)
    s = stats.summarise(agg)
    assert agg["name"] == "Aggregated"
    assert (s["requests"], s["failures"], s["avg_ms"]) == (133, 5, 79.5)
    assert (s["p50"], s["p95"], s["p99"]) == (47, 390, 530)
    assert s["rps"] == pytest.approx(29.27, abs=0.01)  # 133 requests over a 4.544 s active span


def test_verdict_reports_every_broken_threshold():
    agg = stats.summarise(stats.aggregate(SAMPLE_STATS))
    reasons = stats.ci_verdict(agg)
    assert len(reasons) == 1 and "failure ratio" in reasons[0]  # 5 of 133 = 3.76 % > 1 %
    assert stats.ci_verdict(agg, max_fail_ratio=0.05) == []
    strict = stats.ci_verdict(agg, max_fail_ratio=0.05, max_avg_ms=50, max_p95_ms=300)
    assert len(strict) == 2 and "average" in strict[0] and "p95" in strict[1]
    assert stats.ci_verdict({"requests": 0, "failures": 0, "fail_ratio": 0.0, "avg_ms": 0.0, "p95": 0}) == [
        "no requests were made"]


def test_a_fresh_run_is_read_and_judged(tmp_path):
    locustfile = write_locustfile(tmp_path, "payer")
    with serve(TargetConfig(latency_ms=2, error_rate=0.3)) as base:
        prefix = run_locust(locustfile, base, users=3, spawn_rate=3, run_time="2s", out_dir=tmp_path / "out")
        with urllib.request.urlopen(f"{base}/metrics") as r:
            server = json.load(r)
    loaded = stats.load_stats(f"{prefix}.json")
    assert set(loaded) == {"POST /auth/token", "POST /v1/payments"}
    pay = stats.summarise(loaded["POST /v1/payments"])
    assert pay["requests"] >= 20
    assert 0.1 < pay["fail_ratio"] < 0.5, pay  # about 30 % injected errors
    # The server saw every request Locust counted; it can see a few more - requests in flight when Locust stopped
    # its users are answered but never recorded by Locust.
    seen = server["routes"]["POST /v1/payments"]
    assert pay["requests"] <= seen <= pay["requests"] + 3
    assert any("failure ratio" in r for r in stats.ci_verdict(stats.summarise(stats.aggregate(list(loaded.values())))))
