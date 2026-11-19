"""Runs exercises/fundamentals/workload_locustfile.py with real Locust (headless) against the practice API and
checks that the request mix it produces matches the workload model."""

import csv
import math
from pathlib import Path

import pytest
from load_tools import practice_file, run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

MODEL = {"GET /v1/payments": 55, "GET /v1/payments/{id}": 27, "POST /v1/payments": 15, "GET /v1/reports/settlement": 3}


@pytest.fixture(scope="module")
def stats(tmp_path_factory):
    out = tmp_path_factory.mktemp("locust")
    with serve(TargetConfig(latency_ms=0, capacity=64)) as base:
        prefix = run_locust(practice_file("fundamentals/workload_locustfile.py"), base, users=8, spawn_rate=8,
                            run_time="4s", out_dir=out)
    with open(f"{prefix}_stats.csv", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["Name"] != "Aggregated"]
    return {r["Name"]: r for r in rows}


def test_every_model_transaction_ran_under_its_model_name(stats):
    for name in MODEL:
        assert name in stats, f"no requests named {name!r}; names seen: {sorted(stats)}"


def test_payment_ids_are_grouped_into_one_row(stats):
    assert not [n for n in stats if "pay_" in n], "name the GET by id requests 'GET /v1/payments/{id}'"


def test_no_request_failed(stats):
    failed = {n: r["Failure Count"] for n, r in stats.items() if int(r["Failure Count"])}
    assert not failed


def test_login_happens_once_per_user_not_per_iteration(stats):
    assert int(stats["POST /auth/token"]["Request Count"]) == 8


def test_observed_mix_matches_the_model(stats):
    counts = {n: int(stats[n]["Request Count"]) for n in MODEL}
    total = sum(counts.values())
    assert total >= 300, f"only {total} model requests in 4 s - is wait_time pacing the users?"
    for name, weight in MODEL.items():
        expected = weight / 100
        share = counts[name] / total
        # Task choice is random, so the observed share has sampling error: allow 4 standard errors of a
        # binomial proportion (false alarm about 1 in 15 000 per check), plus one percentage point.
        tolerance = 4 * math.sqrt(expected * (1 - expected) / total) + 0.01
        assert share == pytest.approx(expected, abs=tolerance), (
            f"{name}: {counts[name]} of {total} = {share:.3f}, model {expected:.2f} +/- {tolerance:.3f}")
