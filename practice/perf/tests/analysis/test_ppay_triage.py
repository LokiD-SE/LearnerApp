"""Checks exercises/analysis/ppay_triage.py: reading status codes before reading latency.

Hand-made rows first, then three short live probes of the practice API (a fixed key, fresh keys, a per-client rate
limit); no Locust is needed."""

import pytest
from ppay_fixture import call, load_exercise, probe_rows, token
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

tr = load_exercise("analysis/ppay_triage.py")


@pytest.mark.parametrize("status, headers, expected", [
    (201, {}, "ok"), (200, None, "ok"), (201, {"Idempotent-Replayed": "true"}, "replay"),
    (201, {"idempotent-replayed": "TRUE"}, "replay"), (201, {"Idempotent-Replayed": "false"}, "ok"),
    (429, {"Retry-After": "1"}, "rate-limited"), (503, {"Retry-After": "1"}, "overloaded"),
    (500, {}, "server-error"), (502, {}, "server-error"), (504, {}, "server-error"),
    (401, {}, "auth"), (403, {}, "auth"), (400, {}, "bad-request"), (404, {}, "bad-request"),
    (422, {}, "bad-request"), (None, {}, "no-response"), (302, {}, "other"),
])
def test_classify(status, headers, expected):
    assert tr.classify(status, headers) == expected


def test_summarise_always_has_every_class():
    assert set(tr.summarise([])) == set(tr.CLASSES) and sum(tr.summarise([]).values()) == 0
    rows = [{"status": 201, "headers": {}}, {"status": 201, "headers": {"Idempotent-Replayed": "true"}},
            {"status": None}, {"status": 503, "headers": {}}]
    got = tr.summarise(rows)
    assert got["ok"] == 1 and got["replay"] == 1 and got["no-response"] == 1 and got["overloaded"] == 1
    assert got["auth"] == 0


def summary(**counts):
    base = {c: 0 for c in tr.CLASSES}
    base.update({k.replace("_", "-"): v for k, v in counts.items()})
    return base


def test_an_empty_run_is_not_a_measurement():
    assert tr.verdict(summary()) == {"valid": False, "findings": ["empty: no requests"]}


def test_a_clean_run_is_valid_without_findings():
    assert tr.verdict(summary(ok=500)) == {"valid": True, "findings": []}


def test_a_script_that_is_rejected_is_invalid_above_one_percent():
    assert tr.verdict(summary(ok=99, bad_request=1))["valid"] is True  # exactly 1 %: not above
    got = tr.verdict(summary(ok=98, bad_request=1, auth=1))
    assert got["valid"] is False and got["findings"][0].startswith("script-error")
    assert tr.verdict(summary(ok=98, bad_request=3), script_error_share=0.05)["valid"] is True


def test_a_run_of_replays_is_invalid_above_the_share():
    assert tr.verdict(summary(ok=80, replay=20))["valid"] is True  # exactly 20 %
    got = tr.verdict(summary(ok=79, replay=21))
    assert got["valid"] is False and got["findings"][0].startswith("replays")
    assert tr.verdict(summary(ok=1, replay=99), replay_share=0.995)["valid"] is True


def test_429_invalidates_the_run_unless_a_limit_was_expected():
    got = tr.verdict(summary(ok=90, rate_limited=10))
    assert got["valid"] is False and got["findings"][0].startswith("rate-limited")
    assert tr.verdict(summary(ok=90, rate_limited=10), expect_limit=True) == {"valid": True, "findings": []}


def test_503_and_5xx_are_results_not_script_mistakes():
    got = tr.verdict(summary(ok=90, overloaded=10))
    assert got["valid"] is True and [f.split(":")[0] for f in got["findings"]] == ["overloaded"]
    got = tr.verdict(summary(ok=97, server_error=2, no_response=1))
    assert got["valid"] is True and [f.split(":")[0] for f in got["findings"]] == ["server-errors"]
    assert tr.verdict(summary(ok=99, server_error=1))["findings"] == []  # exactly 1 %


def test_findings_come_in_the_documented_order():
    got = tr.verdict(summary(ok=30, replay=30, auth=10, rate_limited=10, overloaded=10, server_error=10))
    assert [f.split(":")[0] for f in got["findings"]] == ["script-error", "replays", "rate-limited", "overloaded",
                                                         "server-errors"]
    assert got["valid"] is False


def test_live_one_fixed_key_is_a_run_of_replays():
    with serve(TargetConfig(latency_ms=1)) as url:
        rows = probe_rows(url, token(url), 40, "fixed")
    got = tr.verdict(tr.summarise(rows))
    assert tr.summarise(rows)["ok"] == 1 and tr.summarise(rows)["replay"] == 39
    assert got["valid"] is False and got["findings"][0].startswith("replays")


def test_live_fresh_keys_are_a_clean_run():
    with serve(TargetConfig(latency_ms=1)) as url:
        rows = probe_rows(url, token(url), 40, "fresh")
    assert tr.verdict(tr.summarise(rows)) == {"valid": True, "findings": []}


def test_live_a_login_per_iteration_from_one_client_meets_the_rate_limit():
    with serve(TargetConfig(latency_ms=1, rate_limit_rps=5)) as url:
        rows = []
        for _ in range(20):
            status, headers, _ = call(url, "POST", "/auth/token", {"client_id": "merchant-1", "client_secret": "secret-1"})
            rows.append({"status": status, "headers": headers})
    got = tr.verdict(tr.summarise(rows))
    assert tr.summarise(rows)["rate-limited"] >= 10
    assert got["valid"] is False and got["findings"][0].startswith("rate-limited")
