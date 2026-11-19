"""Checks exercises/fundamentals/workload_log_model.py against one synthetic day of SandPay access log."""

from datetime import datetime, timezone

import pytest
from fundamentals.workload_log_model import (
    client_share,
    endpoint,
    parse_line,
    peak_factor,
    peak_window,
    project_peak,
    task_weights,
    transaction_mix,
)
from workload_fixture import generate_access_log

pytestmark = pytest.mark.exercise

SAMPLE = '203.0.113.24 - merchant-7 [17/Nov/2026:12:03:41 +0000] "GET /v1/payments?limit=20 HTTP/1.1" 200 812 0.034'


@pytest.fixture(scope="module")
def records():
    return [parse_line(line) for line in generate_access_log()]


def test_parse_line_reads_every_field():
    r = parse_line(SAMPLE)
    assert r == {
        "ip": "203.0.113.24",
        "client": "merchant-7",
        "ts": datetime(2026, 11, 17, 12, 3, 41, tzinfo=timezone.utc),
        "method": "GET",
        "target": "/v1/payments?limit=20",
        "status": 200,
        "bytes": 812,
        "duration": 0.034,
    }


def test_parse_line_anonymous_client_is_none():
    r = parse_line('10.0.0.5 - - [17/Nov/2026:00:00:10 +0000] "GET /health HTTP/1.1" 200 15 0.001')
    assert r["client"] is None and r["target"] == "/health"


@pytest.mark.parametrize("bad", ["", "203.0.113.10 - merchant-2 [17/Nov/2026:11:00:0",
                                 '203.0.113.9 - - [17/Nov/2026:03:14:07 +0000] "\\x16\\x03\\x01" 400 0 0.000'])
def test_parse_line_malformed_is_none(bad):
    assert parse_line(bad) is None


def test_the_day_has_three_malformed_lines(records):
    assert sum(r is None for r in records) == 3


@pytest.mark.parametrize("method,target,expected", [
    ("GET", "/v1/payments?limit=20", "GET /v1/payments"),
    ("GET", "/v1/payments/pay_100123", "GET /v1/payments/{id}"),
    ("GET", "/v1/payments/pay_100123?expand=refunds", "GET /v1/payments/{id}"),
    ("POST", "/v1/payments", "POST /v1/payments"),
    ("GET", "/health", "GET /health"),
])
def test_endpoint_names_transactions(method, target, expected):
    assert endpoint(method, target) == expected


def test_transaction_mix_excludes_monitoring_and_sums_to_one(records):
    mix = transaction_mix(records)
    assert "GET /health" not in mix
    assert sum(mix.values()) == pytest.approx(1.0)
    assert list(mix) == ["GET /v1/payments", "GET /v1/payments/{id}", "POST /auth/token", "POST /v1/payments",
                         "GET /v1/reports/settlement"]
    assert mix["GET /v1/payments"] == pytest.approx(0.443, abs=0.001)
    assert mix["POST /v1/payments"] == pytest.approx(0.118, abs=0.001)


def test_transaction_mix_can_keep_everything(records):
    mix = transaction_mix(records, exclude=frozenset())
    assert mix["GET /health"] == pytest.approx(0.205, abs=0.001)


def test_peak_hour_is_lunchtime(records):
    start, count, rate = peak_window(records)
    assert start == datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    assert count == 2775
    assert rate == pytest.approx(2775 / 3600)


def test_peak_minute_is_the_nightly_batch(records):
    start, count, rate = peak_window(records, window_s=60)
    assert start == datetime(2026, 11, 17, 2, 1, tzinfo=timezone.utc)
    assert count == 209
    assert rate == pytest.approx(209 / 60)


def test_peak_factor_depends_on_the_window(records):
    assert peak_factor(records) == pytest.approx(1.98, abs=0.01)
    assert peak_factor(records, window_s=60) == pytest.approx(8.95, abs=0.01)


def test_peak_factor_counts_quiet_windows():
    def rec(h):
        return parse_line(f'203.0.113.1 - merchant-1 [17/Nov/2026:{h:02d}:00:00 +0000] "GET /v1/payments HTTP/1.1" 200 1 0.010')
    # 3 requests at 00:00, none at 01:00, 1 at 02:00: mean over 3 hours is 4/3 per hour, peak 3 per hour.
    assert peak_factor([rec(0), rec(0), rec(0), rec(2)]) == pytest.approx(3 / (4 / 3))


def test_client_share_shows_skew(records):
    assert client_share(records) == pytest.approx(0.618, abs=0.001)
    assert client_share(records, top_fraction=1.0) == pytest.approx(1.0)


def test_task_weights_keep_proportions(records):
    assert task_weights(transaction_mix(records)) == {
        "GET /v1/payments": 44, "GET /v1/payments/{id}": 22, "POST /auth/token": 18, "POST /v1/payments": 12,
        "GET /v1/reports/settlement": 4,
    }


def test_task_weights_largest_remainder_and_minimum_one():
    assert task_weights({"a": 1, "b": 1, "c": 1}) == {"a": 34, "b": 33, "c": 33}
    w = task_weights({"common": 0.998, "rare": 0.002}, total=100)
    assert w == {"common": 99, "rare": 1}
    assert sum(task_weights({"x": 0.5, "y": 0.3, "z": 0.2}, total=10).values()) == 10


def test_project_peak_compounds_growth_and_adds_headroom():
    assert project_peak(10.0, 0.4, 12) == pytest.approx(14.0)
    assert project_peak(10.0, 0.4, 6) == pytest.approx(10 * 1.4 ** 0.5)
    assert project_peak(10.0, 0.4, 18, headroom=0.3) == pytest.approx(10 * 1.4 ** 1.5 * 1.3)
    assert project_peak(10.0, 0.0, 24) == pytest.approx(10.0)


@pytest.mark.parametrize("args", [(-1.0, 0.1, 12), (10.0, -1.0, 12), (10.0, 0.1, -1), (10.0, 0.1, 12, -0.1)])
def test_project_peak_rejects_nonsense(args):
    with pytest.raises(ValueError):
        project_peak(*args)
