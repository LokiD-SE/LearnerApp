"""Runs exercises/locust/lc_valid_flow_locustfile.py with real Locust against the shared practice API and
checks authentication (one token per user, sent on every request), correlation (each read and replay uses the
id its own create returned) and that the flow stops after a failed step."""

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
        prefix = run_locust(practice_file("locust/lc_valid_flow_locustfile.py"), base, users=USERS,
                            spawn_rate=USERS, run_time="3s", out_dir=tmp_path)
        with urllib.request.urlopen(f"{base}/metrics", timeout=5) as r:
            served = json.loads(r.read())
    return read_locust_stats(prefix), served


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("lc-valid-flow"), error_rate=0.0)


@pytest.fixture(scope="module")
def faulty(tmp_path_factory):
    return _run(tmp_path_factory.mktemp("lc-valid-flow-errors"), error_rate=0.25)


def test_requests_use_exactly_the_four_names(clean):
    stats, _ = clean
    assert set(stats) == NAMES, f"names seen: {sorted(stats)[:8]}"


def test_one_token_per_user_and_it_is_sent_on_every_request(clean):
    stats, served = clean
    assert stats["POST /auth/token"]["num_requests"] == USERS
    assert "401" not in served["statuses"], "requests without a bearer token"


def test_the_happy_flow_has_no_failures(clean):
    stats, _ = clean
    assert stats["POST /v1/payments"]["num_requests"] >= 30
    assert {n: e["num_failures"] for n, e in stats.items() if e["num_failures"]} == {}


def test_every_read_uses_an_id_this_merchant_created(clean):
    stats, served = clean
    # merchants 4+ have no seeded payments, so a 404 means the id was not taken from the create response
    assert "404" not in served["statuses"]
    reads = stats["GET /v1/payments/{id}"]["num_requests"]
    # a request in flight when the run stops reaches the API but never Locust's statistics: one per user at most
    assert reads <= served["routes"].get("GET /v1/payments/{id}", 0) <= reads + USERS


def test_the_replay_reuses_the_key_and_creates_nothing(clean):
    stats, served = clean
    replays = stats["POST /v1/payments (replay)"]["num_requests"]
    assert replays > 0
    assert replays <= served["idempotent_replays"] <= replays + USERS
    # one created payment per create request, never one per replay
    created = stats["POST /v1/payments"]["num_requests"]
    assert created <= served["payments_created"] <= created + USERS


def test_a_failed_create_is_marked_failed_and_stops_the_flow(faulty):
    stats, served = faulty
    creates = stats["POST /v1/payments"]
    assert creates["num_failures"] > 0, "the 500s from the API were not reported"
    assert "404" not in served["statuses"], "the flow read a payment id it never got"
    succeeded = creates["num_requests"] - creates["num_failures"]
    assert stats["GET /v1/payments/{id}"]["num_requests"] <= succeeded
    assert stats["GET /v1/payments/{id}"]["num_requests"] >= succeeded - USERS
