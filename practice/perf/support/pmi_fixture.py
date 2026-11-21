"""Fixture for the performance testing mock interview lesson (tests/capstone/test_pmi_*.py).

A tiny CLOSED-model load generator for the SandPay practice API (loopback only, synthetic data), written with the
standard library so a run costs a few seconds and the lesson can show what a result summary looks like when the
run is trustworthy - and when it is not:

- ``serve_separately(...)`` starts the practice target in its own process, so what the generator burns is not
  taken from the target.
- ``run_closed(base_url, clients, seconds, think_s, burn_ms)`` runs ``clients`` threads for ``seconds``. Each
  waits for its reply, thinks for ``think_s``, and repeats (``burn_ms`` of CPU per iteration stands in for a load
  generator that is too slow). It returns one summary dict with the fields ``pmi_smells.smells`` reads.
- ``summarise(samples, ...)`` builds that dict from raw samples, so a test can feed it hand-made data.
- ``load_runs()`` returns the runs captured by ``pmi_capture.py`` (support/pmi_data/runs.json).

Everything binds to 127.0.0.1. Load numbers depend on the machine, so the tests check behaviour and verdicts.
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

DATA = Path(__file__).with_name("pmi_data") / "runs.json"


@contextlib.contextmanager
def serve_separately(latency_ms: float = 20.0, capacity: int = 16, queue_limit: int = 1000) -> Iterator[str]:
    """The practice target in its OWN process (loopback only). Yields the base URL."""
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


def _token(base_url: str) -> str:
    conn = _connect(base_url)
    conn.request("POST", "/auth/token", json.dumps({"client_id": "merchant-1", "client_secret": "secret-1"}),
                 {"Content-Type": "application/json"})
    token = json.loads(conn.getresponse().read())["access_token"]
    conn.close()
    return token


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, round(p / 100 * len(ordered)) - 1))
    return ordered[index]


def _burn(ms: float) -> None:
    """Spend ``ms`` of this thread's own CPU time (threads share one interpreter lock, so they queue for it)."""
    end = time.thread_time() + ms / 1000
    while time.thread_time() < end:
        pass


def summarise(samples: list[tuple[float, float, int]], duration_s: float, planned_rps: float | None = None,
              generator_cpu_pct: float | None = None) -> dict:
    """One result summary from raw samples ``(seconds since start, latency in ms, HTTP status)``.

    ``first_third_p95_ms`` and ``last_third_p95_ms`` are the p95 of the samples that started in the first and in
    the last third of the run; a warm-up shows as a first third much slower than the last.
    """
    ok = [s for s in samples if s[2] < 500]
    third = duration_s / 3
    first = [lat for t, lat, _ in samples if t < third]
    last = [lat for t, lat, _ in samples if t >= 2 * third]
    all_ms = [lat for _, lat, _ in samples]
    ok_ms = [lat for _, lat, _ in ok]
    return {
        "samples": len(samples),
        "errors": len(samples) - len(ok),
        "duration_s": round(duration_s, 2),
        "achieved_rps": round(len(samples) / duration_s, 1) if duration_s else 0.0,
        "planned_rps": planned_rps,
        "mean_ms": round(sum(all_ms) / len(all_ms), 1) if all_ms else 0.0,
        "p50_all_ms": round(percentile(all_ms, 50), 1),
        "p50_ok_ms": round(percentile(ok_ms, 50), 1),
        "p95_all_ms": round(percentile(all_ms, 95), 1),
        "p95_ok_ms": round(percentile(ok_ms, 95), 1),
        "first_third_p95_ms": round(percentile(first, 95), 1),
        "last_third_p95_ms": round(percentile(last, 95), 1),
        "generator_cpu_pct": generator_cpu_pct,
    }


def run_closed(base_url: str, clients: int, seconds: float, think_s: float = 0.0, burn_ms: float = 0.0,
               planned_rps: float | None = None) -> dict:
    """``clients`` closed-model users for ``seconds``: request, wait for the reply, think, repeat."""
    token = _token(base_url)
    samples: list[tuple[float, float, int]] = []
    lock = threading.Lock()
    barrier = threading.Barrier(clients + 1)
    stop_at = [0.0]
    t0 = [0.0]

    def client() -> None:
        conn = _connect(base_url)
        mine: list[tuple[float, float, int]] = []
        barrier.wait()
        while time.perf_counter() < stop_at[0]:
            if burn_ms:
                _burn(burn_ms)
            start = time.perf_counter()
            conn.request("GET", "/v1/payments?limit=1", headers={"Authorization": f"Bearer {token}"})
            response = conn.getresponse()
            response.read()
            mine.append((start - t0[0], (time.perf_counter() - start) * 1000, response.status))
            if think_s:
                time.sleep(think_s)
        conn.close()
        with lock:
            samples.extend(mine)

    threads = [threading.Thread(target=client) for _ in range(clients)]
    for t in threads:
        t.start()
    cpu0 = time.process_time()
    t0[0] = time.perf_counter()
    stop_at[0] = t0[0] + seconds
    barrier.wait()
    for t in threads:
        t.join()
    wall = time.perf_counter() - t0[0]
    cpu_pct = round((time.process_time() - cpu0) / wall * 100, 0)
    return summarise(samples, wall, planned_rps, cpu_pct)


def load_runs() -> dict:
    """The runs captured by ``support/pmi_capture.py``, keyed by scenario name."""
    with open(DATA) as f:
        return json.load(f)
