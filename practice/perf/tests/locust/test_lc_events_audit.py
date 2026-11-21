"""Checks exercises/locust/lc_events_audit.py: first by calling the listener directly (no Locust needed), then
with real Locust (headless, in a subprocess) against the legacy gateway fixture, where the audit's totals must
equal Locust's own statistics and its failure reasons must match what the gateway sent."""

import json
import os

import pytest
from lc_events_fixture import gateway_metrics, load_exercise, serve_gateway, write_locustfile
from load_tools import practice_file, read_locust_stats, run_locust

pytestmark = pytest.mark.exercise

audit_module = load_exercise("locust/lc_events_audit.py")


def fed(slow_ms=100.0):
    audit = audit_module.RequestAudit(slow_ms=slow_ms)
    audit.on_request("POST", "charge", 80.0, 120, None, {"merchant": "merchant-1"})
    audit.on_request("POST", "charge", 100.0, 120, None, {"merchant": "merchant-1"})  # equal to the limit: not slow
    audit.on_request("POST", "charge", 100.5, 90, Exception("declined: insufficient_funds"), {"merchant": "merchant-2"})
    audit.on_request("POST", "charge", 300.0, 90, Exception("declined: insufficient_funds"), {"merchant": "merchant-2"})
    audit.on_request("POST", "charge", 20.0, 0, Exception("not JSON"), None)  # no context at all
    audit.on_request("GET", "balance", 5.0, 40, None, {})
    return audit


def test_one_row_per_request_type_and_name():
    assert list(fed().summary()) == ["GET balance", "POST charge"]


def test_counts_requests_failures_and_slow_ones():
    row = fed().summary()["POST charge"]
    assert (row["requests"], row["failures"], row["slow"]) == (5, 3, 2)  # 100.5 and 300.0 are over 100


def test_failures_are_grouped_by_reason_and_by_merchant():
    row = fed().summary()["POST charge"]
    assert row["reasons"] == {"declined: insufficient_funds": 2, "not JSON": 1}
    assert row["merchants"] == {"merchant-2": 2}  # the failure with no context is counted, but not per merchant


def test_a_request_without_failures_has_empty_breakdowns():
    assert fed().summary()["GET balance"] == {"requests": 1, "failures": 0, "slow": 0, "reasons": {}, "merchants": {}}


def test_the_listener_accepts_arguments_added_by_future_locust_versions():
    audit = audit_module.RequestAudit()
    audit.on_request(request_type="GET", name="x", response_time=1.0, response_length=0, response=None,
                     context=None, exception=None, start_time=1.0, url="http://h/x", future_argument=True)
    assert audit.summary()["GET x"]["requests"] == 1


def test_the_summary_is_json_and_write_saves_it(tmp_path):
    audit = fed()
    json.dumps(audit.summary())
    audit.write(tmp_path / "audit.json")
    assert json.loads((tmp_path / "audit.json").read_text()) == audit.summary()


def test_install_registers_both_listeners():
    class Hook:
        def __init__(self):
            self.listeners = []

        def add_listener(self, fn):
            self.listeners.append(fn)

    class Events:
        request, quitting = Hook(), Hook()

    audit = audit_module.RequestAudit()
    events = Events()
    audit_module.install(events, audit, "unused.json")
    assert events.request.listeners == [audit.on_request]
    assert len(events.quitting.listeners) == 1


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("lc-events-audit")
    locustfile = write_locustfile(out, "audit", practice_file("locust"))
    old = {k: os.environ.get(k) for k in ("LC_EVENTS_OUT", "LC_EVENTS_SLOW_MS")}
    os.environ["LC_EVENTS_OUT"] = str(out / "audit.json")
    os.environ["LC_EVENTS_SLOW_MS"] = "0"  # every request is "slow": the count must still equal the total
    try:
        with serve_gateway() as base:
            prefix = run_locust(locustfile, base, users=3, spawn_rate=3, run_time="3s", out_dir=out)
            served = gateway_metrics(base)
    finally:
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    return json.loads((out / "audit.json").read_text()), read_locust_stats(prefix), served


def test_the_audit_totals_equal_locusts_statistics(run):
    audit, stats, _ = run
    assert set(audit) == {"POST login", "POST charge"}
    for key, row in audit.items():
        locust_row = stats[key.split(" ", 1)[1]]
        assert row["requests"] == locust_row["num_requests"], key
        assert row["failures"] == locust_row["num_failures"], key
    assert audit["POST charge"]["requests"] >= 30


def test_failure_reasons_match_what_the_gateway_sent(run):
    audit, _, served = run
    reasons = audit["POST charge"]["reasons"]
    assert set(reasons) == {"declined: insufficient_funds", "not JSON: HTTP 200 text/html"}, reasons
    assert sum(reasons.values()) == audit["POST charge"]["failures"]
    assert served["declined"] - 3 <= reasons["declined: insufficient_funds"] <= served["declined"]  # one in flight per user at most


def test_context_carries_the_merchant_to_the_listener(run):
    audit, _, _ = run
    merchants = audit["POST charge"]["merchants"]
    assert set(merchants) <= {"merchant-1", "merchant-2", "merchant-3"} and merchants
    assert sum(merchants.values()) == audit["POST charge"]["failures"]


def test_the_slow_threshold_was_applied(run):
    audit, _, _ = run
    assert audit["POST charge"]["slow"] == audit["POST charge"]["requests"]  # slow_ms=0
