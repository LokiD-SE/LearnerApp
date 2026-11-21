"""Fixture for the bottleneck analysis lesson (tests/analysis/test_bn_*.py).

A tiny closed-loop load generator for the SandPay practice API (loopback only, synthetic data), written with the
standard library so a run costs about a second and a test can look at the target from both sides at once:

- ``run_level(base_url, clients, requests_each)`` - ``clients`` threads, each with one keep-alive connection,
  each sending ``requests_each`` GET /v1/payments?limit=1 requests back to back (no think time). It returns
  what the load generator saw: throughput, mean and p95 latency, status counts.
- ``burn_ms`` makes every client spend that much CPU between requests (a busy loop), the stand-in for a load
  generator that is too slow. All the clients share one Python process, so they share one core.
- ``Sampler`` polls GET /metrics while a level runs, so the same run also gives the target's side:
  ``in_flight`` (requests being served) and ``waiting`` (requests queued for a worker).
- ``run_steps(base_url, levels, requests_each)`` runs the levels one after the other (a step load).
- ``serve_separately(...)`` starts the target in its own process, so what the generator burns is not taken from
  the target.

Everything binds to 127.0.0.1. The helpers are not a replacement for Locust or JMeter - they are small enough to
read in one sitting, which is the point of the lesson's example.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

from sandpay_target import TargetConfig, serve  # noqa: F401 - re-exported for the tests


@contextlib.contextmanager
def serve_separately(latency_ms: float = 20.0, capacity: int = 4, queue_limit: int = 1000) -> Iterator[str]:
    """The practice target in its OWN process (loopback only), so the load generator's CPU and the target's
    work do not share one interpreter lock. Yields the base URL."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    script = Path(__file__).with_name("sandpay_target.py")
    proc = subprocess.Popen([sys.executable, str(script), "--port", str(port), "--latency-ms", str(latency_ms),
                             "--capacity", str(capacity), "--queue-limit", str(queue_limit)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                conn = _connect(url)
                conn.request("GET", "/health")
                conn.getresponse().read()
                conn.close()
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("the practice target did not start")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _connect(base_url: str) -> http.client.HTTPConnection:
    parts = urlsplit(base_url)
    return http.client.HTTPConnection(parts.hostname, parts.port, timeout=30)


def get_token(base_url: str) -> str:
    conn = _connect(base_url)
    conn.request("POST", "/auth/token", json.dumps({"client_id": "merchant-1", "client_secret": "secret-1"}),
                 {"Content-Type": "application/json"})
    token = json.loads(conn.getresponse().read())["access_token"]
    conn.close()
    return token


def get_metrics(base_url: str) -> dict:
    conn = _connect(base_url)
    conn.request("GET", "/metrics")
    data = json.loads(conn.getresponse().read())
    conn.close()
    return data


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, round(p / 100 * len(ordered)) - 1))
    return ordered[index]


class Sampler:
    """Polls /metrics every ``interval`` seconds on a background thread (a USE reading of the target)."""

    def __init__(self, base_url: str, interval: float = 0.05):
        self.base_url, self.interval = base_url, interval
        self.samples: list[dict] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        conn = _connect(self.base_url)
        while not self._stop.is_set():
            conn.request("GET", "/metrics")
            m = json.loads(conn.getresponse().read())
            self.samples.append({"in_flight": m["in_flight"], "waiting": m["waiting"]})
            self._stop.wait(self.interval)
        conn.close()

    def __enter__(self) -> "Sampler":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()


def _burn(ms: float) -> None:
    """Spend ``ms`` of this thread's own CPU time. Wall-clock time would let threads burn in parallel; CPU time
    does not, because the threads share one interpreter lock."""
    end = time.thread_time() + ms / 1000
    while time.thread_time() < end:
        pass


def run_level(base_url: str, clients: int, requests_each: int, token: str | None = None, burn_ms: float = 0.0) -> dict:
    token = token or get_token(base_url)
    latencies: list[float] = []
    statuses: dict[str, int] = {}
    lock = threading.Lock()
    barrier = threading.Barrier(clients + 1)

    def client() -> None:
        conn = _connect(base_url)
        mine: list[float] = []
        codes: dict[str, int] = {}
        barrier.wait()
        for _ in range(requests_each):
            if burn_ms:
                _burn(burn_ms)
            start = time.perf_counter()
            conn.request("GET", "/v1/payments?limit=1", headers={"Authorization": f"Bearer {token}"})
            response = conn.getresponse()
            response.read()
            mine.append((time.perf_counter() - start) * 1000)
            codes[str(response.status)] = codes.get(str(response.status), 0) + 1
        conn.close()
        with lock:
            latencies.extend(mine)
            for code, n in codes.items():
                statuses[code] = statuses.get(code, 0) + n

    threads = [threading.Thread(target=client) for _ in range(clients)]
    for t in threads:
        t.start()
    barrier.wait()
    started = time.perf_counter()
    for t in threads:
        t.join()
    seconds = time.perf_counter() - started
    total = clients * requests_each
    errors = sum(n for code, n in statuses.items() if code.startswith("5"))
    return {"clients": clients, "requests": total, "seconds": round(seconds, 3),
            "throughput": round(total / seconds, 1), "mean_ms": round(sum(latencies) / len(latencies), 1),
            "p95_ms": round(percentile(latencies, 95), 1), "errors": errors, "statuses": dict(sorted(statuses.items()))}


def run_steps(base_url: str, levels: list[int], requests_each: int = 20, burn_ms: float = 0.0) -> list[dict]:
    token = get_token(base_url)
    return [run_level(base_url, n, requests_each, token, burn_ms) for n in levels]
