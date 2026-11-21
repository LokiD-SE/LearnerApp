"""Runs exercises/locust/lc_flow_console_locustfile.py with real Locust: once to print the task ratio (the nested
structure and weights), once headless against the practice API (the user really leaves the Browse screen and comes
back). Checks the structure, the weights, the names and the interrupt - never response times."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from load_tools import practice_file, read_locust_stats, run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

LOCUSTFILE = practice_file("locust/lc_flow_console_locustfile.py")
LOCUST = shutil.which("locust", path=str(Path(sys.executable).parent)) or "locust"
USERS = 4


def test_nested_structure_and_weights():
    proc = subprocess.run([LOCUST, "-f", str(LOCUSTFILE), "--show-task-ratio-json"], capture_output=True, text=True,
                          timeout=60)
    assert proc.returncode == 0, proc.stderr[-2000:]
    user = json.loads(proc.stdout)["per_class"]["MerchantUser"]["tasks"]
    assert {k: v["ratio"] for k, v in user.items()} == {"Browse": 0.75, "run_settlement_report": 0.25}
    inner = {k: v["ratio"] for k, v in user["Browse"]["tasks"].items()}
    assert inner == {"list_payments": 0.5, "view_payment": 0.3, "leave": 0.2}


@pytest.fixture(scope="module")
def stats(tmp_path_factory):
    out = tmp_path_factory.mktemp("lc_flow_console")
    with serve(TargetConfig(latency_ms=5, capacity=64)) as base:
        prefix = run_locust(LOCUSTFILE, base, users=USERS, spawn_rate=USERS, run_time="4s", out_dir=out)
    return read_locust_stats(prefix)


def test_requests_use_exactly_these_names(stats):
    assert set(stats) == {"POST /auth/token", "GET /v1/payments (open)", "GET /v1/payments",
                          "GET /v1/payments/{id}", "GET /v1/reports/settlement"}, sorted(stats)


def test_one_login_per_user_and_no_failures(stats):
    assert stats["POST /auth/token"]["num_requests"] == USERS
    failed = {k: e["num_failures"] for k, e in stats.items() if e["num_failures"]}
    assert not failed, f"failures (token not sent from the TaskSet? wrong ids?): {failed}"


def test_the_user_leaves_browse_and_comes_back(stats):
    # Without self.interrupt() each user enters Browse once and never leaves: 4 opens and no settlement report.
    assert stats["GET /v1/payments (open)"]["num_requests"] > 2 * USERS, "Browse was entered about once per user"
    assert stats["GET /v1/reports/settlement"]["num_requests"] > 0, "nobody ever left Browse"


def test_inside_browse_the_weights_decide_the_mix(stats):
    lists = stats["GET /v1/payments"]["num_requests"]
    views = stats["GET /v1/payments/{id}"]["num_requests"]
    assert lists > views > 0, f"list {lists}, view {views}: weights 5 : 3 expected"
