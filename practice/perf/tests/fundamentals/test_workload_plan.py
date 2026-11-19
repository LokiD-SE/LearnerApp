"""Runs exercises/fundamentals/workload_plan.jmx with real JMeter (non-GUI) against the practice API and checks
that the plan produces the workload model's mix, logs in once per merchant and creates payments cleanly."""

from collections import Counter

import pytest
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = [pytest.mark.exercise,
              pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")]

MODEL = {"GET /v1/payments": 55, "GET /v1/payments/{id}": 27, "POST /v1/payments": 15, "GET /v1/reports/settlement": 3}
THREADS, LOOPS = 2, 200


@pytest.fixture(scope="module")
def samples(tmp_path_factory):
    with serve(TargetConfig(latency_ms=0, capacity=64)) as base:
        jtl = run_jmeter(practice_file("fundamentals/workload_plan.jmx"),
                         {"port": base.rsplit(":", 1)[1], "threads": THREADS, "loops": LOOPS},
                         tmp_path_factory.mktemp("jmeter"))
    return read_jtl(jtl)


def test_login_once_per_merchant(samples):
    labels = Counter(s["label"] for s in samples)
    assert labels["POST /auth/token"] == THREADS


def test_every_transaction_ran(samples):
    labels = Counter(s["label"] for s in samples)
    missing = [name for name in MODEL if labels[name] == 0]
    assert not missing, f"no samples for {missing} - check the Throughput Controller percentages"


def test_mix_follows_the_model(samples):
    labels = Counter(s["label"] for s in samples)
    iterations = THREADS * LOOPS
    for name, percent in MODEL.items():
        # Percent executions runs a controller in that share of the iterations; allow one percentage point.
        assert labels[name] / iterations == pytest.approx(percent / 100, abs=0.01), (
            f"{name}: {labels[name]} of {iterations} iterations, model {percent}%")


def test_payments_are_created_not_rejected(samples):
    codes = Counter(s["responseCode"] for s in samples if s["label"] == "POST /v1/payments")
    assert codes and set(codes) == {"201"}, f"POST /v1/payments answered {dict(codes)} - Idempotency-Key header?"


def test_no_failed_samples(samples):
    failed = [(s["label"], s["responseCode"]) for s in samples if s["success"] != "true"]
    assert not failed, failed[:5]
