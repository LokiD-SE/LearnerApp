"""Exercise: jm_data_credentials.py + jm_data_login.jmx - one merchant per iteration, from a CSV file."""

import csv
from collections import Counter

import pytest
from jmeter.jm_data_credentials import data_problems, logins_by_client, write_credentials
from load_tools import jmeter_home, practice_file, read_jtl, run_jmeter
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

needs_jmeter = pytest.mark.skipif(jmeter_home() is None, reason="JMeter not installed (scripts/get-jmeter.sh)")


def row(label, code="200", success="true"):
    return {"label": label, "responseCode": code, "success": success}


def test_write_credentials_header_then_one_row_per_merchant(tmp_path):
    path = write_credentials(tmp_path / "m.csv", 3, first=4)
    with open(path, newline="") as f:
        lines = list(csv.reader(f))
    assert lines == [["client_id", "client_secret"], ["merchant-4", "secret-4"], ["merchant-5", "secret-5"],
                     ["merchant-6", "secret-6"]]


@pytest.mark.parametrize("count,first", [(0, 1), (2, 50), (1, 0), (51, 1)])
def test_write_credentials_refuses_merchants_the_api_does_not_know(tmp_path, count, first):
    with pytest.raises(ValueError):
        write_credentials(tmp_path / "m.csv", count, first)


def test_logins_by_client_counts_only_successful_sign_ins():
    rows = [row("POST /auth/token merchant-1"), row("GET /v1/payments merchant-1"),
            row("POST /auth/token merchant-1"), row("POST /auth/token merchant-2", "401", "false")]
    assert logins_by_client(rows) == Counter({"merchant-1": 2})


def test_data_problems_names_each_kind_of_problem():
    rows = [row("POST /auth/token ${client_id}", "401", "false"), row("POST /auth/token <EOF>", "401", "false"),
            row("POST /auth/token merchant-3"), row("POST /auth/token merchant-3"),
            row("GET /v1/payments merchant-2", "401", "false")]
    assert data_problems(rows) == [
        "undefined variable in 'POST /auth/token ${client_id}'",
        "end of file reached in 'POST /auth/token <EOF>'",
        "failed sample 'GET /v1/payments merchant-2' (401)",
        "reused merchant-3 (2 sign-ins)",
    ]
    assert data_problems([row("POST /auth/token merchant-1"), row("GET /v1/payments merchant-1")]) == []


@pytest.fixture(scope="module")
def login_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("jm_data_login")
    # The test writes the file itself, so the plan is checked even before write_credentials is solved.
    data = out / "merchants.csv"
    data.write_text("client_id,client_secret\n" + "".join(f"merchant-{n},secret-{n}\n" for n in range(1, 7)))
    with serve(TargetConfig(latency_ms=1)) as base:
        port = base.rsplit(":", 1)[1]
        jtl = run_jmeter(practice_file("jmeter/jm_data_login.jmx"),
                         {"port": port, "csv": data, "threads": 5, "loops": 2}, out)
    return read_jtl(jtl)


@needs_jmeter
def test_every_merchant_signs_in_exactly_once(login_run):
    labels = [r["label"] for r in login_run]
    assert not [lb for lb in labels if "${" in lb], "a variable is undefined - is the CSV Data Set Config there?"
    logins = Counter(lb.removeprefix("POST /auth/token ") for lb in labels if lb.startswith("POST /auth/token "))
    assert logins == Counter({f"merchant-{n}": 1 for n in range(1, 7)})


@needs_jmeter
def test_threads_stop_at_end_of_file_instead_of_sending_eof(login_run):
    # 5 threads x 2 iterations want 10 rows; the file has 6. Stop thread on EOF ends the run after 6.
    assert not [r for r in login_run if "<EOF>" in r["label"]], "recycle must be off and stop thread on"
    assert len(login_run) == 12  # 6 sign-ins + 6 payment lists
    assert {r["responseCode"] for r in login_run} == {"200"}


@needs_jmeter
def test_each_list_call_uses_its_own_merchants_token(login_run):
    lists = Counter(r["label"].removeprefix("GET /v1/payments ") for r in login_run
                    if r["label"].startswith("GET /v1/payments "))
    assert lists == Counter({f"merchant-{n}": 1 for n in range(1, 7)})
