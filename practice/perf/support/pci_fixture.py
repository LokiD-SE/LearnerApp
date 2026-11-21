"""Fixtures for the lesson "Performance testing in CI/CD" (exercises under analysis/pci_*).

A **run summary** is the one-line record a CI job keeps for each load test run - a dict such as::

    {"build": "main-07", "samples": 612, "errors": 0, "p50_ms": 31, "p95_ms": 52, "p99_ms": 61,
     "rps": 153.0, "generator_cpu_max": 41}

- ``run_summary(...)`` makes one by running real Locust (subprocess, 8 users, a few seconds) against the practice API
  and reading Locust's own totals for the payment-creation requests (the ones that can fail); ``generator_cpu_max`` is the highest whole-machine CPU use sampled every half
  second during the run (a stand-in for "was the generator or the machine saturated?").
- ``history()`` returns the captured runs behind the lesson (``pci_data/history.json``, made by ``pci_capture.py`` on
  21 November 2026): ``main`` (12 runs of the baseline build), ``same`` (3 more runs of the same build), ``small``
  (3 runs of a build that is slightly slower), ``slower`` (3 runs of a clearly slower build) and ``failing`` (3 runs
  of a build that returns 500 on a fifth of the payment creations but answers as fast as the baseline).
- ``load_workflow(name)`` reads a GitHub Actions workflow converted to JSON (``pci_data/<name>.json``). JSON is valid
  YAML, but the converted files exist because the practice project has no YAML library; the conversion of the repo's
  own ``.github/workflows/pages.yml`` was done with the ``yaml`` npm package.
Never import ``locust`` in the pytest process (gevent patches everything): ``run_summary`` uses a subprocess.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import psutil
from load_tools import read_locust_stats, run_locust
from sandpay_target import TargetConfig, serve

HERE = Path(__file__).resolve().parent
DATA = HERE / "pci_data"


def history() -> dict[str, list[dict]]:
    return json.loads((DATA / "history.json").read_text())


def load_workflow(name: str) -> dict:
    return json.loads((DATA / f"{name}.json").read_text())


def locust_percentiles(total: dict, pcts: tuple[float, ...]) -> list[int]:
    """Locust's own percentile function over a run's bucketed response times, in a child process."""
    code = ("import json, sys; from locust.stats import calculate_response_time_percentile as c; "
            "d = json.load(sys.stdin); n = d['num_requests'] - d['num_none_requests']; "
            "print(json.dumps([c({int(k): v for k, v in d['response_times'].items()}, n, p) "
            f"for p in {list(pcts)!r}]))")
    done = subprocess.run([sys.executable, "-c", code], input=json.dumps(total), capture_output=True, text=True,
                          check=True)
    return [int(v) for v in json.loads(done.stdout)]


class CpuSampler:
    """Samples whole-machine CPU use every 0.5 s on a thread until stopped; ``max`` is the highest sample."""

    def __init__(self) -> None:
        self.max = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        psutil.cpu_percent(None)
        while not self._stop.is_set():
            self.max = max(self.max, psutil.cpu_percent(interval=0.5))

    def __enter__(self) -> "CpuSampler":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()


def run_summary(build: str, latency_ms: float = 20, capacity: int = 4, error_rate: float = 0.0, users: int = 8,
                seconds: int = 4) -> dict:
    """One real Locust run against the practice API, reduced to a run summary."""
    with serve(TargetConfig(latency_ms=latency_ms, capacity=capacity, error_rate=error_rate)) as base:
        tmp = Path(tempfile.mkdtemp(prefix="pci-run-"))
        with CpuSampler() as cpu:
            prefix = run_locust(HERE / "pci_locustfile.py", base, users=users, spawn_rate=users,
                                run_time=f"{seconds}s", out_dir=tmp)
    total = read_locust_stats(prefix)["/v1/payments (create)"]
    p50, p95, p99 = locust_percentiles(total, (0.5, 0.95, 0.99))
    return {"build": build, "samples": total["num_requests"], "errors": total["num_failures"],
            "p50_ms": p50, "p95_ms": p95, "p99_ms": p99,
            "rps": round(total["num_requests"] / seconds, 1), "generator_cpu_max": round(cpu.max)}
