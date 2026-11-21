"""Runs exercises/locust/lc_dist_gate_locustfile.py in real distributed clusters (a master and two workers on
127.0.0.1) and checks that the MASTER's exit code is the pipeline's verdict."""

import pytest
from lc_dist_fixture import LOCUST, free_port, load_exercise, run_cluster
from load_tools import practice_file
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

gate = load_exercise("locust/lc_dist_gate_locustfile.py")


def test_verdict_passes_inside_the_limits():
    assert gate.verdict(0.0, 50, 0.01, 800) == (0, [])
    assert gate.verdict(0.01, 800, 0.01, 800) == (0, [])  # limits are inclusive


def test_verdict_names_each_broken_limit():
    code, reasons = gate.verdict(0.25, 50, 0.01, 800)
    assert code == 1 and reasons == ["failure ratio 0.2500 > 0.01"]
    code, reasons = gate.verdict(0.0, 120, 0.01, 100)
    assert code == 1 and reasons == ["95th percentile 120 ms > 100 ms"]
    code, reasons = gate.verdict(0.5, 900, 0.01, 800)
    assert code == 1 and len(reasons) == 2


def _run(tmp_path, error_rate, env):
    locustfile = str(practice_file("locust/lc_dist_gate_locustfile.py"))
    port = free_port()
    with serve(TargetConfig(latency_ms=10, capacity=32, error_rate=error_rate)) as base:
        master = [LOCUST, "-f", locustfile, "--master", "--master-bind-host", "127.0.0.1", "--master-bind-port",
                  str(port), "--headless", "--expect-workers", "2", "-u", "6", "-r", "6", "-t", "4s", "--host",
                  base, "--only-summary", "--loglevel", "WARNING", "--exit-code-on-error", "0"]
        worker = [LOCUST, "-f", locustfile, "--worker", "--master-host", "127.0.0.1", "--master-port", str(port),
                  "--loglevel", "WARNING"]
        return run_cluster(master, [worker, worker], env=env)


def test_a_clean_run_inside_the_limits_exits_0(tmp_path):
    run = _run(tmp_path, 0.0, {"LC_GATE_MAX_FAIL_RATIO": "0.01", "LC_GATE_P95_MS": "5000"})
    assert run.master.returncode == 0, run.master.stderr[-2000:]
    assert [w.returncode for w in run.workers] == [0, 0]


def test_a_slow_95th_percentile_fails_the_master(tmp_path):
    # the settlement report is a tenth of the requests and takes about 100 ms against 10 ms for the rest,
    # so the 95th percentile is a report time - far above a 20 ms limit
    run = _run(tmp_path, 0.0, {"LC_GATE_MAX_FAIL_RATIO": "0.01", "LC_GATE_P95_MS": "20"})
    assert run.master.returncode == 1, run.master.stderr[-2000:]
    assert "95th percentile" in run.master.stderr and "gate failed" in run.master.stderr


def test_too_many_failures_fail_the_master_even_when_locust_is_told_to_ignore_them(tmp_path):
    # the cluster's master is started with --exit-code-on-error 0, so only the gate can produce exit code 1
    run = _run(tmp_path, 0.5, {"LC_GATE_MAX_FAIL_RATIO": "0.05", "LC_GATE_P95_MS": "5000"})
    assert run.master.returncode == 1, run.master.stderr[-2000:]
    assert "failure ratio" in run.master.stderr


def test_the_workers_do_not_gate_their_own_slice(tmp_path):
    run = _run(tmp_path, 0.5, {"LC_GATE_MAX_FAIL_RATIO": "0.05", "LC_GATE_P95_MS": "20"})
    assert run.master.returncode == 1
    assert [w.returncode for w in run.workers] == [0, 0], [w.stderr[-300:] for w in run.workers]
    assert all("gate failed" not in w.stderr for w in run.workers)
