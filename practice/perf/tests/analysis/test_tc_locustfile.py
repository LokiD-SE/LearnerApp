"""Checks exercises/analysis/tc_checkout_locustfile.py: the Locust version of the checkout scenario that
support/tc_checkout.jmx runs in JMeter.

Each test runs the file in real Locust (a subprocess, 5 users, 3 seconds) against a fresh practice API and checks
behaviour: the request names and mix, one sign-in per user, a bearer token on every call, a new Idempotency-Key for
every payment, and a think time that the TC_WAIT variable controls. Nothing here depends on how fast the machine is."""

import json
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest
import tc_fixture as fx
from load_tools import practice_file

pytestmark = pytest.mark.exercise

USERS, SECONDS = 5, 3
NAMES = {"POST /auth/token", "GET /v1/payments", "POST /v1/payments", "GET /v1/payments/{id}"}


def run(wait_s):
    """One real Locust run of the file under test; returns (Locust totals by name, the API's /metrics)."""
    locustfile = practice_file("analysis/tc_checkout_locustfile.py")
    with tempfile.TemporaryDirectory() as tmp, fx.with_target() as base:
        _, path = fx.run_locust_scenario(Path(tmp), urlparse(base).port, USERS, SECONDS, wait_s, locustfile=locustfile)
        entries = {e["name"]: e for e in json.loads(path.read_text())}
        with urllib.request.urlopen(f"{base}/metrics") as r:
            metrics = json.load(r)
    return entries, metrics


@pytest.fixture(scope="module")
def fast_think():
    return run(0.2)


def test_the_four_requests_have_the_names_the_jmeter_plan_uses(fast_think):
    entries, _ = fast_think
    assert set(entries) - {"Aggregated"} == NAMES


def test_each_user_signs_in_once_and_every_call_is_authorised(fast_think):
    entries, _ = fast_think
    assert entries["POST /auth/token"]["num_requests"] == USERS
    assert sum(e["num_failures"] for e in entries.values()) == 0  # a missing bearer token would be 401s, counted as failures


def test_the_three_calls_of_an_iteration_run_in_step(fast_think):
    entries, _ = fast_think
    counts = [entries[n]["num_requests"] for n in ("GET /v1/payments", "POST /v1/payments", "GET /v1/payments/{id}")]
    assert min(counts) >= USERS * 2  # every user finished at least two iterations in 3 seconds, even on a busy machine
    assert max(counts) - min(counts) <= USERS  # a user may be part-way through an iteration when the run stops


def test_every_payment_has_its_own_idempotency_key(fast_think):
    entries, metrics = fast_think
    created = entries["POST /v1/payments"]["num_requests"]
    # the API may have created a payment whose answer Locust never recorded because the run was stopping
    assert created <= metrics["payments_created"] <= created + USERS
    assert metrics["idempotent_replays"] == 0  # a repeated key would have been answered as a replay


def test_the_think_time_is_used_and_comes_from_tc_wait(fast_think):
    entries, _ = fast_think
    created = entries["POST /v1/payments"]["num_requests"]
    assert created <= USERS * (SECONDS / 0.2 + 1)  # one iteration per user per 0.2 s at most, plus the first at once
    slow, _ = run(1.0)
    assert slow["POST /v1/payments"]["num_requests"] <= USERS * (SECONDS / 1.0 + 1)
    assert slow["POST /v1/payments"]["num_requests"] < created
