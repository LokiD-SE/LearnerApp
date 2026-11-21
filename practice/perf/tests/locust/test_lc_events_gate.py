"""Checks exercises/locust/lc_events_gate.py: the decision on stand-in statistics, then the exit code of real
Locust runs (headless, in a subprocess) against the legacy gateway fixture, where about a third of the charges
fail - so the same run passes a lenient gate and fails a strict one."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from lc_events_fixture import load_exercise, serve_gateway, write_locustfile
from load_tools import practice_file

pytestmark = pytest.mark.exercise

gate = load_exercise("locust/lc_events_gate.py")
LOCUST = shutil.which("locust", path=str(Path(sys.executable).parent)) or "locust"


def stats(requests=100, fail_ratio=0.0, p95=100.0):
    total = SimpleNamespace(num_requests=requests, fail_ratio=fail_ratio, get_response_time_percentile=lambda p: p95)
    return SimpleNamespace(total=total)


def test_a_clean_run_passes():
    assert gate.violations(stats(), 0.01, 800) == []


def test_limits_are_inclusive():
    assert gate.violations(stats(fail_ratio=0.01, p95=800), 0.01, 800) == []


def test_each_broken_limit_gets_its_own_reason():
    assert [r.split()[0:2] for r in gate.violations(stats(fail_ratio=0.2), 0.01, 800)] == [["fail", "ratio"]]
    assert [r.split()[0] for r in gate.violations(stats(p95=900), 0.01, 800)] == ["p95"]
    both = gate.violations(stats(fail_ratio=0.2, p95=900), 0.01, 800)
    assert len(both) == 2


def test_the_percentile_asked_for_is_the_95th():
    asked = []
    total = SimpleNamespace(num_requests=10, fail_ratio=0.0,
                            get_response_time_percentile=lambda p: asked.append(p) or 1.0)
    gate.violations(SimpleNamespace(total=total), 0.01, 800)
    assert asked == [0.95]


def test_a_run_with_no_requests_fails_with_one_reason():
    reasons = gate.violations(stats(requests=0, fail_ratio=0.0, p95=0.0), 0.01, 800)
    assert len(reasons) == 1 and "no requests" in reasons[0]


def fire_quitting(stats_obj, max_fail_ratio=0.01, p95_ms=800):
    class Hook:
        def __init__(self):
            self.listeners = []

        def add_listener(self, fn):
            self.listeners.append(fn)

    events = SimpleNamespace(quitting=Hook())
    gate.install(events, max_fail_ratio, p95_ms)
    assert len(events.quitting.listeners) == 1
    environment = SimpleNamespace(stats=stats_obj, process_exit_code=None)
    events.quitting.listeners[0](environment=environment, future_argument=True)
    return environment.process_exit_code


def test_install_sets_exit_code_1_on_violations_and_0_otherwise(caplog):
    assert fire_quitting(stats()) == 0
    with caplog.at_level("ERROR"):
        assert fire_quitting(stats(fail_ratio=0.5)) == 1
    assert "fail ratio" in caplog.text
    assert fire_quitting(stats(requests=0)) == 1


def run_locust_exit_code(tmp_path, max_fail):
    locustfile = write_locustfile(tmp_path, "gate", practice_file("locust"))
    with serve_gateway() as base:
        proc = subprocess.run(
            [LOCUST, "-f", str(locustfile), "--headless", "-u", "3", "-r", "3", "-t", "3s", "--host", base,
             "--only-summary", "--loglevel", "WARNING"],
            capture_output=True, text=True, timeout=60, env={**os.environ, "LC_EVENTS_MAX_FAIL": str(max_fail)})
    return proc


def test_a_lenient_gate_passes_a_run_that_has_failures(tmp_path):
    proc = run_locust_exit_code(tmp_path, 0.9)
    assert "declined" in proc.stdout + proc.stderr  # the run really had failures - Locust's own rule would have exited with 1
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-1500:]


def test_a_strict_gate_fails_the_same_run_and_says_why(tmp_path):
    proc = run_locust_exit_code(tmp_path, 0.05)
    assert proc.returncode == 1, proc.stdout[-1500:] + proc.stderr[-1500:]
    assert "GATE FAILED: fail ratio" in proc.stdout + proc.stderr
