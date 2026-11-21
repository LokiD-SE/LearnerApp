"""Fixtures for the distributed Locust lesson (tests/locust/test_lc_dist_*.py).

- ``load_exercise(relative)`` imports a Python exercise by path (the topic folder is called ``locust``, like the
  Locust package; see lc_fund_fixture.py).
- ``free_port()`` asks the operating system for an unused loopback TCP port. Never use Locust's default 5557 in
  a test: two runs at once (or a run you forgot about) would share it.
- ``run_cluster(master_argv, worker_argvs)`` starts the master first, then each worker, as subprocesses with a
  timeout, and returns every process's exit code and output. Everything runs on 127.0.0.1.
- ``SAMPLE_WORKER_DUMPS`` and ``SAMPLE_MASTER_STATS`` are real: one run of ``MIXED_LOCUSTFILE`` with a master
  and two workers (8 users, 6 seconds, the practice API with 10 ms service time), captured on 21 November 2026
  by ``python support/lc_dist_fixture.py --capture``. The workers' dumps come from a private ``RequestStats``
  copy kept by each worker (a worker resets its own stats after every report to the master, so its live stats
  are empty at the end); the master's stats are its ``--json-file`` output. Only the fields the exercises read
  are kept, floats rounded to 3 decimals.
- ``MIXED_LOCUSTFILE`` is the locustfile used for that capture: three ``Reader`` users for every ``ReportUser``.
  The report is ten times slower than a health check, so which worker gets the report users decides its numbers.
"""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from load_tools import practice_file

LOCUST = str(Path(sys.executable).parent / "locust")


def load_exercise(relative: str) -> ModuleType:
    path = practice_file(relative)
    spec = importlib.util.spec_from_file_location(Path(relative).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class Cluster:
    master: subprocess.CompletedProcess
    workers: list[subprocess.CompletedProcess] = field(default_factory=list)


def run_cluster(master_argv: list[str], worker_argvs: list[list[str]], env: dict[str, str] | None = None,
                timeout: float = 90, worker_env: list[dict[str, str]] | None = None) -> Cluster:
    """Master first, workers a moment later (workers retry until the master is up). Waits for every process;
    kills the lot if the master has not finished within ``timeout`` seconds."""
    base = {**os.environ, **(env or {})}
    procs: list[subprocess.Popen] = []
    master = subprocess.Popen(master_argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=base)
    procs.append(master)
    time.sleep(0.5)
    workers = []
    for i, argv in enumerate(worker_argvs):
        extra = (worker_env or [{}] * len(worker_argvs))[i]
        workers.append(subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                        env={**base, **extra}))
    procs += workers
    results = []
    try:
        for p in procs:
            out, err = p.communicate(timeout=timeout)
            results.append(subprocess.CompletedProcess(p.args, p.returncode, out, err))
    except subprocess.TimeoutExpired:
        raise
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
                p.wait()
    return Cluster(results[0], results[1:])


MIXED_LOCUSTFILE = '''
import json
import os
from pathlib import Path

from locust import HttpUser, constant, events, task
from locust.runners import WorkerRunner
from locust.stats import RequestStats

own = RequestStats()  # a private copy: a worker resets its real stats after every report to the master


class Reader(HttpUser):
    weight = 3
    wait_time = constant(0.05)

    @task
    def health(self):
        self.client.get("/health", name="/health")


class ReportUser(HttpUser):
    weight = 1
    wait_time = constant(0.05)

    def on_start(self):
        r = self.client.post("/auth/token", json={"client_id": "merchant-1", "client_secret": "secret-1"})
        self.client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    @task
    def settlement(self):
        self.client.get("/v1/reports/settlement", name="/v1/reports/settlement")


@events.request.add_listener
def keep_a_copy(request_type, name, response_time, response_length, exception=None, **_):
    own.log_request(request_type, name, response_time, response_length)
    if exception:
        own.log_error(request_type, name, exception)


@events.quitting.add_listener
def dump_worker_stats(environment, **_):
    folder = os.environ.get("LC_DIST_DUMP_DIR")
    if folder and isinstance(environment.runner, WorkerRunner):
        Path(folder, f"worker-{environment.runner.worker_index}.json").write_text(json.dumps(own.serialize_stats()))
'''

_KEEP = ("method", "name", "num_requests", "num_failures", "total_response_time", "min_response_time",
         "max_response_time", "response_times")


def capture() -> None:  # pragma: no cover - run by hand to refresh the samples below
    from sandpay_target import TargetConfig, serve

    with tempfile.TemporaryDirectory() as tmp, serve(TargetConfig(latency_ms=10, capacity=16)) as base:
        tmp = Path(tmp)
        locustfile = tmp / "mixed_locustfile.py"
        locustfile.write_text(MIXED_LOCUSTFILE.lstrip())
        port = free_port()
        common = ["-f", str(locustfile), "--loglevel", "WARNING"]
        master = [LOCUST, *common, "--master", "--master-bind-host", "127.0.0.1", "--master-bind-port", str(port),
                  "--headless", "--expect-workers", "2", "-u", "8", "-r", "8", "-t", "6s", "--host", base,
                  "--json-file", str(tmp / "m"), "--only-summary"]
        worker = [LOCUST, *common, "--worker", "--master-host", "127.0.0.1", "--master-port", str(port)]
        run_cluster(master, [worker, worker], env={"LC_DIST_DUMP_DIR": str(tmp)})
        dumps = [json.loads((tmp / f"worker-{i}.json").read_text()) for i in range(2)]
        master_stats = json.loads((tmp / "m.json").read_text())

    def trim(entries):
        return [{k: (round(e[k], 3) if isinstance(e[k], float) else e[k]) for k in _KEEP} for e in entries]

    print("SAMPLE_WORKER_DUMPS =", [trim(d) for d in dumps])
    print("SAMPLE_MASTER_STATS =", trim(master_stats))


SAMPLE_WORKER_DUMPS: list[list[dict]] = [[{'method': 'GET', 'name': '/health', 'num_requests': 206, 'num_failures': 0, 'total_response_time': 740.946, 'min_response_time': 1.844, 'max_response_time': 6.947, 'response_times': {'7': 3, '3': 98, '2': 3, '4': 89, '5': 12, '6': 1}}, {'method': 'POST', 'name': '/auth/token', 'num_requests': 2, 'num_failures': 0, 'total_response_time': 31.546, 'min_response_time': 14.427, 'max_response_time': 17.119, 'response_times': {'14': 1, '17': 1}}, {'method': 'GET', 'name': '/v1/reports/settlement', 'num_requests': 72, 'num_failures': 0, 'total_response_time': 7494.87, 'min_response_time': 102.033, 'max_response_time': 106.692, 'response_times': {'100': 61, '110': 11}}], [{'method': 'GET', 'name': '/health', 'num_requests': 404, 'num_failures': 0, 'total_response_time': 1783.216, 'min_response_time': 2.57, 'max_response_time': 8.132, 'response_times': {'5': 114, '8': 3, '7': 7, '4': 190, '6': 39, '3': 51}}]]
SAMPLE_MASTER_STATS: list[dict] = [{'method': 'GET', 'name': '/health', 'num_requests': 610, 'num_failures': 0, 'total_response_time': 2524.161, 'min_response_time': 1.844, 'max_response_time': 8.132, 'response_times': {'7': 10, '3': 149, '2': 3, '4': 279, '5': 126, '6': 40, '8': 3}}, {'method': 'POST', 'name': '/auth/token', 'num_requests': 2, 'num_failures': 0, 'total_response_time': 31.546, 'min_response_time': 14.427, 'max_response_time': 17.119, 'response_times': {'14': 1, '17': 1}}, {'method': 'GET', 'name': '/v1/reports/settlement', 'num_requests': 72, 'num_failures': 0, 'total_response_time': 7494.87, 'min_response_time': 102.033, 'max_response_time': 106.692, 'response_times': {'100': 61, '110': 11}}]

if __name__ == "__main__" and "--capture" in sys.argv:  # pragma: no cover
    capture()
