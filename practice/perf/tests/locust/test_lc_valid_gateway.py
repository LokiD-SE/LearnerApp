"""Runs exercises/locust/lc_valid_gateway_locustfile.py with real Locust against the legacy gateway fixture
(support/lc_valid_fixture.py), which answers 200 even for declines and HTML error pages, and checks that the
locustfile's catch_response validation turns those into failures - and that an expected 404 is a success."""

import csv
from pathlib import Path

import pytest
from lc_valid_fixture import metrics, serve
from load_tools import practice_file, read_locust_stats, run_locust

pytestmark = pytest.mark.exercise

USERS = 4
NAMES = {"POST /gateway/login", "POST /gateway/charges", "POST /gateway/charges/{id}/void",
         "GET /gateway/charges/{id} (voided)"}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("lc-valid-gateway")
    with serve() as base:
        prefix = run_locust(practice_file("locust/lc_valid_gateway_locustfile.py"), base, users=USERS,
                            spawn_rate=USERS, run_time="3s", out_dir=out)
        served = metrics(base)
    with open(f"{prefix}_failures.csv", newline="") as f:
        failures = list(csv.DictReader(f))
    return read_locust_stats(prefix), served, failures


def test_requests_use_exactly_the_four_grouped_names(run):
    stats, _, _ = run
    assert set(stats) == NAMES, f"names seen: {sorted(stats)[:8]}"


def test_each_user_logs_in_once_and_the_cookie_is_reused(run):
    stats, served, _ = run
    assert stats["POST /gateway/login"]["num_requests"] == USERS
    assert stats["POST /gateway/login"]["num_failures"] == 0
    assert served["unauthenticated"] == 0, "requests without the session cookie got 401"


def test_soft_failures_on_200_are_reported_as_failures(run):
    stats, served, _ = run
    charges = stats["POST /gateway/charges"]
    bad = served["declined"] + served["html_errors"]
    assert charges["num_requests"] >= 50, "too few charges - is wait_time 0 and the task running?"
    # A request still in flight when the run stops is counted by the gateway but never by Locust: allow one per user.
    assert bad - USERS <= charges["num_failures"] <= bad, (
        f"Locust failures {charges['num_failures']}, gateway sent {served['declined']} declines + "
        f"{served['html_errors']} HTML pages")


def test_failure_messages_name_the_reason(run):
    _, _, failures = run
    errors = " | ".join(row["Error"] for row in failures if row["Name"] == "POST /gateway/charges")
    assert "declined: insufficient_funds" in errors, errors
    assert "not JSON" in errors, errors


def test_the_expected_404_after_a_void_counts_as_success(run):
    stats, served, _ = run
    lookups = stats["GET /gateway/charges/{id} (voided)"]
    assert lookups["num_requests"] > 0
    assert lookups["num_failures"] == 0, "a 404 is the right answer for a voided charge - mark it success()"
    assert served["lookups_found"] == 0, "a charge was looked up before it was voided"
    assert served["voids"] >= lookups["num_requests"]


def test_only_approved_charges_are_voided(run):
    stats, served, _ = run
    # every void must follow an approved charge; declined and HTML responses have no charge to void
    assert served["voids"] <= served["approved"]
    assert stats["POST /gateway/charges/{id}/void"]["num_failures"] == 0
