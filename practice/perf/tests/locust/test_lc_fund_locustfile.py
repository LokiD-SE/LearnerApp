"""Runs exercises/locust/lc_fund_locustfile.py with real Locust: once to print its task ratio, once headless against
the practice API. Checks the request names, the once-per-user login, the 3 : 1 task weights and the paced rate -
never response times."""

import json
import subprocess
import shutil
import sys
from pathlib import Path

import pytest
from load_tools import practice_file, run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

LOCUSTFILE = practice_file("locust/lc_fund_locustfile.py")
LOCUST = shutil.which("locust", path=str(Path(sys.executable).parent)) or "locust"
USERS = 4


def test_task_ratio_is_three_to_one():
    proc = subprocess.run([LOCUST, "-f", str(LOCUSTFILE), "--show-task-ratio-json"], capture_output=True, text=True,
                          timeout=60)
    assert proc.returncode == 0, proc.stderr[-2000:]
    ratio = json.loads(proc.stdout)["total"]
    assert list(ratio) == ["MerchantUser"], "one user class called MerchantUser"
    tasks = {name: t["ratio"] for name, t in ratio["MerchantUser"]["tasks"].items()}
    assert tasks == {"list_payments": 0.75, "view_payment": 0.25}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("lc_fund")
    with serve(TargetConfig(latency_ms=5, capacity=64)) as base:
        prefix = run_locust(LOCUSTFILE, base, users=USERS, spawn_rate=USERS, run_time="4s", out_dir=out)
    with open(f"{prefix}.json") as f:
        entries = json.load(f)
    return {f"{e['method']} {e['name']}": e for e in entries}


def test_requests_are_reported_under_three_names(run):
    entries = run
    assert set(entries) == {"POST /auth/token", "GET /v1/payments", "GET /v1/payments/[id]"}, sorted(entries)


def test_every_user_logs_in_exactly_once(run):
    entries = run
    assert entries["POST /auth/token"]["num_requests"] == USERS


def test_no_request_failed(run):
    entries = run
    failed = {k: e["num_failures"] for k, e in entries.items() if e["num_failures"]}
    assert not failed, f"failures (missing token? wrong ids?): {failed}"


def test_users_are_paced_to_two_tasks_per_second(run):
    entries = run
    tasks = [entries["GET /v1/payments"], entries["GET /v1/payments/[id]"]]
    count = sum(e["num_requests"] for e in tasks)
    span = max(e["last_request_timestamp"] for e in tasks) - min(e["start_time"] for e in tasks)
    # Each user's first task runs at once, then one every 0.5 s: about USERS * (1 + 2 * span) tasks. Measure the
    # rate over the active span (start-up time on a busy machine is not part of it).
    rate = (count - USERS) / span
    assert 0.7 * 2 * USERS <= rate <= 1.15 * 2 * USERS, (
        f"{count} tasks in {span:.2f} s = {rate:.1f} per second; expected about {2 * USERS} - is wait_time set?")
