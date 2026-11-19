import csv
from pathlib import Path

import pytest
from fundamentals.types_stress import StepResult, breaking_point, per_step
from load_tools import practice_file, run_locust
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

COLUMNS = ["Timestamp", "User Count", "Type", "Name", "95%", "Total Request Count", "Total Failure Count"]


def row(users, name, p95, total, failed, ts=0):
    return dict(zip(COLUMNS, [str(ts), str(users), "", name, p95, str(total), str(failed)]))


def test_per_step_uses_cumulative_counts():
    rows = [
        row(0, "Aggregated", "N/A", 0, 0),
        row(2, "GET", "90", 18, 0),  # per-request rows are ignored
        row(2, "Aggregated", "N/A", 20, 0),
        row(2, "Aggregated", "95", 42, 0),
        row(5, "Aggregated", "97", 116, 0),
        row(5, "Aggregated", "99", 169, 3),
        row(8, "Aggregated", "140", 240, 30),
        row(0, "Aggregated", "140", 240, 30),  # the test stopped
    ]
    assert per_step(rows) == [StepResult(2, 42, 0, 95.0), StepResult(5, 127, 3, 99.0), StepResult(8, 71, 27, 140.0)]


def test_per_step_keeps_repeated_user_counts_apart():
    rows = [row(2, "Aggregated", "50", 10, 0), row(16, "Aggregated", "200", 60, 30), row(2, "Aggregated", "60", 70, 31)]
    assert [s.users for s in per_step(rows)] == [2, 16, 2]
    assert per_step(rows)[2] == StepResult(2, 10, 1, 60.0)


def test_breaking_point():
    steps = [StepResult(2, 100, 0, 90.0), StepResult(4, 0, 0, None), StepResult(6, 200, 1, 400.0),
             StepResult(8, 300, 9, 120.0)]
    assert breaking_point(steps, 0.01, 1000) == StepResult(8, 300, 9, 120.0)  # 3% > 1%
    assert breaking_point(steps, 0.05, 300) == StepResult(6, 200, 1, 400.0)  # p95 400 > 300
    assert breaking_point(steps, 0.05, 1000) is None
    assert StepResult(1, 0, 0, None).error_rate == 0.0


def test_stepped_stress_run_finds_the_shedding_point(tmp_path, monkeypatch):
    # capacity 4 + queue 4: at most 8 requests in the system, so with one request in flight per user,
    # 8 users never see a 503 and 11 users always do
    monkeypatch.setenv("STEP_START", "2")
    monkeypatch.setenv("STEP_SIZE", "3")
    monkeypatch.setenv("STEP_SECONDS", "2")
    monkeypatch.setenv("STEP_COUNT", "4")
    with serve(TargetConfig(latency_ms=50, capacity=4, queue_limit=4)) as base:
        prefix = run_locust(practice_file("fundamentals/types_stress_locustfile.py"), base, users=1, spawn_rate=1,
                            run_time="20s", out_dir=tmp_path, extra=["--csv-full-history"])
    with open(f"{prefix}_stats_history.csv", newline="") as f:
        steps = per_step(list(csv.DictReader(f)))
    assert [s.users for s in steps] == [2, 5, 8, 11]
    assert all(s.failures == 0 for s in steps[:3])
    found = breaking_point(steps, 0.01, 1_000_000)
    assert found is not None and found.users == 11
    assert Path(f"{prefix}_stats.csv").exists()
