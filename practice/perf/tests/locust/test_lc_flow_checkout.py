"""Runs exercises/locust/lc_flow_checkout_locustfile.py with real Locust against the shared practice API, once
clean and once with 25% of creates failing. Checks the order of the steps (a read never runs before the create it
needs), the shared payment id, the replay, and that a failed step ends the sequence."""

import json
import urllib.request

import pytest
from load_tools import practice_file, read_locust_stats, run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

USERS = 4
NAMES = {"POST /auth/token", "POST /v1/payments", "GET /v1/payments/{id}", "POST /v1/payments (replay)"}


def _run(tmp_path, error_rate: float):
    with serve(TargetConfig(latency_ms=0, capacity=32, error_rate=error_rate, payments=5)) as base:
        prefix = run_locust(practice_file("locust/lc_flow_checkout_locustfile.py"), base, users=USERS,
                            spawn_rate=USERS, run_time="3s", out_dir=tmp_path)
        with urllib.request.urlopen(f"{base}/metrics", timeout=5) as r:
            served = json.loads(r.read())
    return read_locust_stats(prefix), served


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("lc-flow-checkout"), error_rate=0.0)


@pytest.fixture(scope="module")
def faulty(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("lc-flow-checkout-errors"), error_rate=0.25)


def test_requests_use_exactly_the_four_names(clean):
    stats, _ = clean
    assert set(stats) == NAMES, f"names seen: {sorted(stats)[:8]}"


def test_the_steps_run_in_order_and_complete_cycles(clean):
    stats, served = clean
    creates = stats["POST /v1/payments"]["num_requests"]
    reads = stats["GET /v1/payments/{id}"]["num_requests"]
    replays = stats["POST /v1/payments (replay)"]["num_requests"]
    assert creates >= 30, f"only {creates} creates"
    # each user is somewhere in create -> read -> replay, so the counts stay within one cycle per user
    assert creates >= reads >= replays
    assert creates - replays <= 2 * USERS, f"{creates} creates, {reads} reads, {replays} replays: not a repeating sequence"
    assert "404" not in served["statuses"], "a read ran with an id that was never created (steps out of order?)"


def test_every_step_uses_the_payment_the_create_returned(clean):
    stats, served = clean
    assert stats["GET /v1/payments/{id}"]["num_failures"] == 0
    replays = stats["POST /v1/payments (replay)"]
    assert replays["num_failures"] == 0, "the replay did not reuse the key and body"
    created = stats["POST /v1/payments"]["num_requests"]
    assert created <= served["payments_created"] <= created + USERS, "a replay created a second payment"
    assert replays["num_requests"] <= served["idempotent_replays"] <= replays["num_requests"] + USERS


def test_one_token_per_user(clean):
    stats, served = clean
    assert stats["POST /auth/token"]["num_requests"] == USERS
    assert "401" not in served["statuses"]


def test_a_failed_create_is_reported_and_ends_the_sequence(faulty):
    stats, served = faulty
    creates = stats["POST /v1/payments"]
    assert creates["num_failures"] > 0, "the 500s from the API were not reported"
    assert "404" not in served["statuses"], "a read ran after a failed create"
    succeeded = creates["num_requests"] - creates["num_failures"]
    reads = stats["GET /v1/payments/{id}"]["num_requests"]
    assert succeeded - USERS <= reads <= succeeded
