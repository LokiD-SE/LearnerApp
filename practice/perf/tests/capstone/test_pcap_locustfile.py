"""Runs exercises/capstone/pcap_locustfile.py with real Locust (headless, in a subprocess) against the practice API."""

import pytest
from load_tools import practice_file, read_locust_stats, run_locust
from pcap_fixture import engagement_config
from sandpay_target import serve

pytestmark = pytest.mark.exercise

NAMES = {"POST /auth/token", "setup: GET /v1/payments", "POST /v1/payments", "GET /v1/payments",
         "GET /v1/payments/{id}", "GET /v1/reports/settlement"}
USERS = 12


@pytest.fixture(scope="module")
def stats(tmp_path_factory):
    out = tmp_path_factory.mktemp("pcap-locust")
    import os

    os.environ["PCAP_THINK"] = "0.05"
    try:
        with serve(engagement_config()) as base:
            prefix = run_locust(practice_file("capstone/pcap_locustfile.py"), base, users=USERS, spawn_rate=USERS,
                                run_time="6s", out_dir=out)
    finally:
        del os.environ["PCAP_THINK"]
    return read_locust_stats(prefix)


def test_exactly_the_six_request_names_appear(stats):
    assert set(stats) - {"Aggregated"} == NAMES


def test_every_user_signs_in_once_and_reads_the_setup_page_once(stats):
    assert stats["POST /auth/token"]["num_requests"] == USERS
    assert stats["setup: GET /v1/payments"]["num_requests"] == USERS


def test_nothing_fails_so_tokens_ids_and_idempotency_keys_are_right(stats):
    assert {name: s["num_failures"] for name, s in stats.items()} == {name: 0 for name in stats}


def test_the_mix_follows_the_weights(stats):
    mix = ["POST /v1/payments", "GET /v1/payments", "GET /v1/payments/{id}", "GET /v1/reports/settlement"]
    total = sum(stats[n]["num_requests"] for n in mix)
    assert total > 300
    share = {n: stats[n]["num_requests"] / total for n in mix}
    assert 0.30 <= share["POST /v1/payments"] <= 0.50
    assert 0.20 <= share["GET /v1/payments"] <= 0.40
    assert 0.15 <= share["GET /v1/payments/{id}"] <= 0.35
    assert 0.01 <= share["GET /v1/reports/settlement"] <= 0.12
