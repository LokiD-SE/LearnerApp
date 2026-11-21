"""Checks exercises/locust/lc_dist_commands.py, then runs real Locust clusters (a master and workers, all on
127.0.0.1) with the command lines it builds."""

import json

import pytest
from lc_dist_fixture import LOCUST, free_port, load_exercise, run_cluster
from lc_fund_fixture import write_locustfile
from sandpay_target import TargetConfig, serve

pytestmark = pytest.mark.exercise

cmd = load_exercise("locust/lc_dist_commands.py")


def _pairs(argv):
    return {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1) if argv[i].startswith("-")}


def test_master_command_binds_to_loopback_and_waits_for_its_workers():
    argv = cmd.master_command("lf.py", "http://127.0.0.1:8090", 8, 4, "30s", 2, 5601, "out/run")
    assert argv[0] == "locust" and all(isinstance(a, str) for a in argv)
    p = _pairs(argv)
    assert "--master" in argv and "--headless" in argv and "--only-summary" in argv
    assert p["--master-bind-host"] == "127.0.0.1" and p["--master-bind-port"] == "5601"
    assert p["--expect-workers"] == "2"
    assert (p["-f"], p["-u"], p["-r"], p["-t"], p["--host"]) == ("lf.py", "8", "4", "30s", "http://127.0.0.1:8090")
    assert p["--csv"] == "out/run" and p["--json-file"] == "out/run"


def test_worker_command_connects_to_the_loopback_master():
    argv = cmd.worker_command("lf.py", 5601, locust="/x/locust")
    p = _pairs(argv)
    assert argv[0] == "/x/locust" and "--worker" in argv
    assert p["--master-host"] == "127.0.0.1" and p["--master-port"] == "5601" and p["-f"] == "lf.py"
    assert "--headless" not in argv  # a worker takes its orders from the master


def test_processes_command_repeats_the_port_for_the_forked_workers():
    argv = cmd.processes_command("lf.py", "http://h", 6, 3, "20s", 3, 5602, "r")
    p = _pairs(argv)
    assert p["--processes"] == "3" and "--master" not in argv and "--worker" not in argv
    assert p["--master-bind-host"] == "127.0.0.1"
    assert p["--master-bind-port"] == "5602" and p["--master-port"] == "5602"


@pytest.mark.parametrize("kwargs", [{"workers": 0}, {"users": 1, "workers": 2}, {"spawn_rate": 0},
                                    {"run_time": ""}, {"run_time": "0"}, {"port": 80}, {"port": 70000}])
def test_master_command_refuses_runs_that_cannot_work(kwargs):
    args = {"locustfile": "lf.py", "host": "http://h", "users": 4, "spawn_rate": 2, "run_time": "10s",
            "workers": 2, "port": 5601, "out_prefix": "r", **kwargs}
    with pytest.raises(ValueError):
        cmd.master_command(**args)


def test_processes_command_refuses_more_processes_than_users():
    with pytest.raises(ValueError):
        cmd.processes_command("lf.py", "http://h", 2, 2, "10s", 4, 5601, "r")


GOOD_MASTER = ["locust", "-f", "lf.py", "--master", "--master-bind-host", "127.0.0.1", "--headless",
               "--expect-workers", "2", "-t", "10s"]


@pytest.mark.parametrize("argv, expected", [
    (GOOD_MASTER, []),
    (["locust", "-f", "lf.py", "--worker", "--master-host", "127.0.0.1"], []),
    (["locust", "-f", "lf.py", "--worker"], []),  # no --master-host means localhost
    (["locust", "-f", "lf.py", "--master", "--headless", "--expect-workers", "2", "-t", "10s"],
     ["master-not-loopback"]),
    (["locust", "--master", "--master-bind-host", "0.0.0.0", "--headless", "--expect-workers", "2", "-t", "1m"],
     ["master-not-loopback"]),
    (["locust", "--master", "--master-bind-host", "localhost", "--headless", "-t", "1m"], ["no-expect-workers"]),
    (["locust", "--worker", "--master-host", "10.0.0.5"], ["worker-master-not-loopback"]),
    (["locust", "--master", "--master-bind-host", "::1", "--headless", "--expect-workers", "2"], ["no-run-time"]),
    (["locust", "--headless", "--processes", "2", "--master-bind-host", "127.0.0.1", "--master-bind-port", "5602",
      "-t", "10s"], ["port-mismatch"]),
    (["locust", "--headless", "--processes", "2", "--master-bind-host", "127.0.0.1", "--master-bind-port", "5602",
      "--master-port", "5602", "--run-time", "10s"], []),
    (["locust", "--headless", "--processes", "2"], ["master-not-loopback", "no-run-time"]),
    (["locust", "--master", "--headless"], ["master-not-loopback", "no-expect-workers", "no-run-time"]),
    (["locust", "-f", "lf.py", "--web-port", "8089"], []),
])
def test_audit_finds_exactly_the_listed_problems(argv, expected):
    assert cmd.audit(argv) == expected


def test_audit_accepts_what_the_builders_produce():
    assert cmd.audit(cmd.master_command("lf.py", "http://h", 4, 2, "10s", 2, 5601, "r")) == []
    assert cmd.audit(cmd.worker_command("lf.py", 5601)) == []
    assert cmd.audit(cmd.processes_command("lf.py", "http://h", 4, 2, "10s", 2, 5601, "r")) == []


def test_a_master_and_two_workers_run_a_test_together(tmp_path):
    locustfile = write_locustfile(tmp_path, "payer")
    port = free_port()
    with serve(TargetConfig(latency_ms=2)) as base:
        run = run_cluster(cmd.master_command(str(locustfile), base, 4, 4, "3s", 2, port, str(tmp_path / "run"),
                                             locust=LOCUST),
                          [cmd.worker_command(str(locustfile), port, locust=LOCUST)] * 2)
    assert run.master.returncode == 0, run.master.stderr[-2000:]
    assert [w.returncode for w in run.workers] == [0, 0], [w.stderr[-500:] for w in run.workers]
    stats = {e["name"]: e for e in json.loads((tmp_path / "run.json").read_text())}
    assert stats["/auth/token"]["num_requests"] == 4  # one login per user, whichever worker ran it
    assert stats["/v1/payments"]["num_requests"] > 10


def test_the_one_command_form_runs_the_same_test(tmp_path):
    locustfile = write_locustfile(tmp_path, "payer")
    port = free_port()
    with serve(TargetConfig(latency_ms=2)) as base:
        run = run_cluster(cmd.processes_command(str(locustfile), base, 4, 4, "3s", 2, port, str(tmp_path / "p"),
                                                locust=LOCUST), [])
    assert run.master.returncode == 0, run.master.stderr[-2000:]
    stats = {e["name"]: e for e in json.loads((tmp_path / "p.json").read_text())}
    assert stats["/auth/token"]["num_requests"] == 4 and stats["/v1/payments"]["num_requests"] > 10
