"""A tiny SandPay "quote" service with a long-tailed, seeded service time - the fixture for the lesson
"Performance metrics and percentiles" (exercises under fundamentals/metrics_*).

Every request to ``GET /quote`` sleeps for the next value of a seeded latency sequence: most requests are
fast, a few are slow, a very few are very slow - the shape real services have and the one that makes averages
mislead. ``GET /quote?fail=1`` answers ``500``. Loopback only.

``disable_nagle_algorithm`` matters: without it, Python's HTTP server writes the headers and the body in two
TCP segments, and on a keep-alive connection Nagle's algorithm plus the client's delayed ACK can add about
40 ms to every response - a measurement artefact a load test would happily report as "latency".
"""

from __future__ import annotations

import contextlib
import itertools
import random
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterator


def tail_latencies_ms(seed: int = 3) -> Iterator[float]:
    """Endless seeded sequence: ~90 % 10-30 ms, ~9 % 80-150 ms, ~1 % 400-600 ms."""
    rng = random.Random(seed)
    while True:
        r = rng.random()
        if r < 0.90:
            yield rng.uniform(10, 30)
        elif r < 0.99:
            yield rng.uniform(80, 150)
        else:
            yield rng.uniform(400, 600)


@contextlib.contextmanager
def serve_quotes(seed: int = 3, host: str = "127.0.0.1", disable_nagle: bool = True) -> Iterator[str]:
    """Serves GET /quote on loopback; ``disable_nagle=False`` shows the keep-alive artefact (see module doc)."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("loopback only")
    seq = tail_latencies_ms(seed)
    lock = threading.Lock()
    counter = itertools.count(1)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        disable_nagle_algorithm = disable_nagle

        def do_GET(self) -> None:
            split = urllib.parse.urlsplit(self.path)
            if split.path != "/quote":
                body, status = b'{"error": "not found"}', 404
            elif "fail=1" in split.query:
                body, status = b'{"error": "pricing engine unavailable (simulated)"}', 500
            else:
                with lock:
                    ms = next(seq)
                    n = next(counter)
                time.sleep(ms / 1000)
                body, status = f'{{"quote_id": "q_{n}", "fee_minor": 25}}'.encode(), 200
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    class Server(ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request: Any, client_address: Any) -> None:
            pass  # a load generator that stops mid-request closes its sockets; that is not a server fault

    server = Server((host, 0), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://{host}:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


# ---- real runs, shared by the metrics_* tests (one JMeter run and one Locust run per pytest session) ------

import functools
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JMX = HERE.parent / "tests" / "fundamentals" / "fixtures" / "metrics_quotes.jmx"
LOCUSTFILE = HERE.parent / "tests" / "fundamentals" / "fixtures" / "metrics_locustfile.py"
APDEX_T_MS = 25  # thresholds low enough that this fast fixture produces all three Apdex zones
APDEX_F_MS = 100


@functools.lru_cache(maxsize=1)
def jmeter_quotes_run() -> dict:
    """Runs the quotes plan in JMeter (4 threads x 50 loops), then JMeter's own dashboard generator over the
    JTL with Apdex T=25 ms, F=100 ms. Returns the JTL rows, ``statistics.json`` and the dashboard's Apdex."""
    from load_tools import java_home, jmeter_home, read_jtl, run_jmeter

    out = Path(tempfile.mkdtemp(prefix="learnerapp-metrics-jmeter-"))
    with serve_quotes() as base:
        jtl = run_jmeter(JMX, {"port": base.rsplit(":", 1)[1], "threads": 4, "loops": 50}, out)
    dash = out / "dashboard"
    env = {**os.environ, "HEAP": "-Xms256m -Xmx512m"}
    if java_home():
        env["JAVA_HOME"] = java_home()
    subprocess.run(
        [str(jmeter_home() / "bin" / "jmeter"), "-g", str(jtl), "-o", str(dash), "-j", str(out / "generate.log"),
         f"-Jjmeter.reportgenerator.apdex_satisfied_threshold={APDEX_T_MS}",
         f"-Jjmeter.reportgenerator.apdex_tolerated_threshold={APDEX_F_MS}"],
        check=True, capture_output=True, text=True, env=env, timeout=120)
    js = (dash / "content" / "js" / "dashboard.js").read_text()
    apdex = json.loads(re.search(r'createTable\(\$\("#apdexTable"\), (\{.*?\})\s*, function', js, re.S).group(1))
    return {"rows": read_jtl(jtl), "statistics": json.loads((dash / "statistics.json").read_text()),
            "apdex": {item["data"][3]: item["data"][0] for item in [apdex["overall"], *apdex["items"]]}}


@functools.lru_cache(maxsize=1)
def locust_quotes_run() -> dict:
    """Runs a 3-second headless Locust test (4 users) against the quotes service. Returns the raw response
    times the locustfile logged (full precision), the rows of ``_stats.csv`` (rewritten once a second during
    the run, so it can lag the end) and the final statistics from ``--json-file`` (written at shutdown)."""
    import csv

    from load_tools import run_locust

    out = Path(tempfile.mkdtemp(prefix="learnerapp-metrics-locust-"))
    raw = out / "raw.csv"
    os.environ["METRICS_RAW_LOG"] = str(raw)
    with serve_quotes() as base:
        prefix = run_locust(LOCUSTFILE, base, users=4, spawn_rate=4, run_time="3s", out_dir=out,
                            extra=["--json-file", str(out / "final")])
    with open(raw) as f:
        times = [(row[0], float(row[1])) for row in csv.reader(f)]
    with open(f"{prefix}_stats.csv", newline="") as f:
        stats = list(csv.DictReader(f))
    final = json.loads((out / "final.json").read_text())
    # Locust's own percentile function, run in a child process: importing locust here would apply gevent's
    # monkey patching to the whole pytest process.
    oracle = subprocess.run(
        [sys.executable, "-c",
         "import json, sys\n"
         "from locust.stats import calculate_response_time_percentile as f\n"
         "e = json.load(open(sys.argv[1]))[0]\n"
         "h = {int(k): v for k, v in e['response_times'].items()}\n"
         "print(json.dumps({p: f(h, e['num_requests'], p / 100) for p in (50, 66, 75, 90, 95, 99, 100)}))",
         str(out / "final.json")],
        check=True, capture_output=True, text=True, timeout=60)
    percentiles = {int(k): v for k, v in json.loads(oracle.stdout).items()}
    return {"raw": times, "stats": stats, "final": final, "percentiles": percentiles}
