"""Fixtures for the lesson "Reading load test results honestly" (exercises under analysis/rd_*).

- ``serve_service(config)`` is a tiny SandPay "quote" service whose slow moments are driven by a REQUEST COUNTER, so
  a run shows the same story on any machine:
  - a cold start: the first ``warmup_requests`` requests carry extra time that shrinks linearly to zero (an empty
    cache filling, a JIT warming up);
  - a stall: when request number ``stall_at`` arrives, the whole service freezes for ``stall_s`` seconds (a garbage
    collection pause, a lock, a failover) and every request that arrives meanwhile waits for the thaw.
  Loopback only; Nagle's algorithm is off, as in the other fixtures.
- ``load_exercise(relative)`` imports an exercise module from its file.
- ``run_closed(out_dir, ...)`` and ``run_paced(out_dir, ...)`` run the two JMeter plans next to this file and return
  the JTL rows: ``rd_closed.jmx`` (threads send the next request as soon as the last answer arrives) and
  ``rd_paced.jmx`` (the same threads behind a Constant Throughput Timer).
- ``read_rows(name)`` reads one of the captured ``rd_data/*.csv`` files (real JTL columns, ``timeStamp`` rebased to ms
  since the first sample) back as JTL rows.
- ``NOISE_P95`` - the p95 (ms) and requests per second of repeated real Locust runs, captured by
  ``rd_capture.py`` on 21 November 2026.
"""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import itertools
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

HERE = Path(__file__).resolve().parent
DATA = HERE / "rd_data"
LOOPBACK = ("127.0.0.1", "localhost", "::1")


@dataclass
class ServiceConfig:
    base_ms: float = 10.0
    warmup_requests: int = 0  # the first N requests are slow, shrinking linearly to the base time
    warmup_extra_ms: float = 0.0  # extra time on request 0
    stall_at: int = 0  # request number (1-based) that freezes the service; 0 = never
    stall_s: float = 0.0


@contextlib.contextmanager
def serve_service(config: ServiceConfig | None = None, host: str = "127.0.0.1") -> Iterator[str]:
    """Serves ``GET /quote`` on loopback and yields the base URL."""
    if host not in LOOPBACK:
        raise ValueError("loopback only")
    cfg = config or ServiceConfig()
    lock = threading.Lock()
    counter = itertools.count(0)
    state = {"frozen_until": 0.0}

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = True

        def do_GET(self) -> None:
            with lock:
                n = next(counter)
                if cfg.stall_at and n + 1 == cfg.stall_at:
                    state["frozen_until"] = time.monotonic() + cfg.stall_s
            extra = 0.0
            if cfg.warmup_requests and n < cfg.warmup_requests:
                extra = cfg.warmup_extra_ms * (1 - n / cfg.warmup_requests)
            time.sleep((cfg.base_ms + extra) / 1000)
            frozen = state["frozen_until"] - time.monotonic()
            if frozen > 0:
                time.sleep(frozen)
            body = f'{{"quote_id": "q_{n + 1}", "fee_minor": 25}}'.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request: Any, client_address: Any) -> None:
            pass

    server = Server((host, 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def load_exercise(relative: str) -> ModuleType:
    from load_tools import practice_file

    path = practice_file(relative)
    spec = importlib.util.spec_from_file_location(Path(relative).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_closed(out_dir: Path, config: ServiceConfig, threads: int = 4, seconds: int = 8) -> list[dict[str, str]]:
    from load_tools import read_jtl, run_jmeter

    with serve_service(config) as base:
        jtl = run_jmeter(HERE / "rd_closed.jmx", {"port": base.rsplit(":", 1)[1], "threads": threads,
                                                  "duration": seconds}, out_dir)
    return read_jtl(jtl)


def run_paced(out_dir: Path, config: ServiceConfig, per_minute: int, threads: int = 4,
              seconds: int = 10) -> list[dict[str, str]]:
    from load_tools import read_jtl, run_jmeter

    with serve_service(config) as base:
        jtl = run_jmeter(HERE / "rd_paced.jmx", {"port": base.rsplit(":", 1)[1], "threads": threads,
                                                 "duration": seconds, "rpm": per_minute}, out_dir)
    return read_jtl(jtl)


def read_rows(name: str) -> list[dict[str, str]]:
    with open(DATA / name, newline="") as f:
        return list(csv.DictReader(f))
