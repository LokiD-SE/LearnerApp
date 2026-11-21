"""Captures the real runs behind the lesson "JMeter, Locust and other tools compared".

    cd practice/perf && .venv/bin/python support/tc_capture.py

For each of three scenarios the same checkout journey (``tc_checkout.jmx`` / ``tc_checkout_locustfile.py``) runs
three times on each of four setups, against a fresh practice API (10 ms service time):

- ``jmeter-default``: JMeter 5.6.3 CLI with its own default heap (``-Xms1g -Xmx1g``),
- ``jmeter-512m``: the same with ``HEAP=-Xms256m -Xmx512m`` (what ``load_tools.run_jmeter`` sets),
- ``locust-http``: Locust 2.47.0 ``HttpUser`` (python-requests),
- ``locust-fast``: Locust 2.47.0 ``FastHttpUser`` (geventhttpclient).

Scenarios: ``startup`` (1 user, 1 second: mostly the fixed cost of starting the tool), ``steady`` (10 users, 200 ms
think time, 10 seconds) and ``many`` (500 users, 12 s think time, 5 s ramp, 25 seconds: a similar number of
iterations per second from fifty times the virtual users).

Writes ``tc_data/runs.json`` (one record per run: wall time, CPU seconds, peak memory, request and failure counts)
and one saved result file per tool for the ``steady`` scenario (``jmeter_checkout.csv`` - a JTL with only six
columns and start times counted from the first sample - and ``locust_checkout.json`` - Locust's own totals with
``start_time`` counted from zero). Takes about ten minutes.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tc_fixture as fx  # noqa: E402

SCENARIOS = {
    "startup": dict(users=1, seconds=1, wait_s=0.2, ramp_s=0),
    "steady": dict(users=10, seconds=10, wait_s=0.2, ramp_s=0),
    "many": dict(users=500, seconds=25, wait_s=12.0, ramp_s=5),
}
SETUPS = ["jmeter-default", "jmeter-512m", "locust-http", "locust-fast"]
REPEATS = 3
KEEP = {"jmeter-default", "locust-http"}


def jtl_counts(jtl: Path) -> tuple[int, int]:
    with open(jtl, newline="") as f:
        rows = list(csv.DictReader(f))
    return len(rows), sum(1 for r in rows if r["success"] != "true")


def locust_counts(path: Path) -> tuple[int, int]:
    entries = [e for e in json.loads(path.read_text()) if e["name"] != "Aggregated"]
    return sum(e["num_requests"] for e in entries), sum(e["num_failures"] for e in entries)


def save_jtl(jtl: Path) -> None:
    with open(jtl, newline="") as f:
        rows = list(csv.DictReader(f))
    first = min(int(r["timeStamp"]) for r in rows)
    with open(fx.DATA / "jmeter_checkout.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["timeStamp", "elapsed", "label", "responseCode", "success", "threadName"])
        for r in sorted(rows, key=lambda r: int(r["timeStamp"])):
            w.writerow([int(r["timeStamp"]) - first, r["elapsed"], r["label"], r["responseCode"], r["success"],
                        r["threadName"]])


def _rounded(o):
    """Floats to three decimals, so no value in the saved file carries a long run of digits."""
    if isinstance(o, float):
        return round(o, 3)
    if isinstance(o, dict):
        return {k: _rounded(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_rounded(v) for v in o]
    return o


def save_locust(path: Path) -> None:
    entries = json.loads(path.read_text())
    for e in entries:
        t0 = e["start_time"]
        e["start_time"] = 0.0
        e["last_request_timestamp"] = round(e["last_request_timestamp"] - t0, 3)
    (fx.DATA / "locust_checkout.json").write_text(json.dumps(_rounded(entries), indent=1) + "\n")


def one_run(scenario: str, setup: str, tmp: Path) -> tuple[dict, Path]:
    cfg = SCENARIOS[scenario]
    load_before = round(os.getloadavg()[0], 2)  # one-minute load average on the machine just before the run
    with fx.with_target() as base:
        port = urlparse(base).port
        out = tmp / f"{scenario}-{setup}"
        if setup.startswith("jmeter"):
            heap = None if setup == "jmeter-default" else "-Xms256m -Xmx512m"
            m, path = fx.run_jmeter_scenario(out, port, cfg["users"], cfg["seconds"], int(cfg["wait_s"] * 1000),
                                             cfg["ramp_s"], heap)
            requests, failures = jtl_counts(path)
        else:
            m, path = fx.run_locust_scenario(out, port, cfg["users"], cfg["seconds"], cfg["wait_s"], cfg["ramp_s"],
                                             "fast" if setup == "locust-fast" else "http")
            requests, failures = locust_counts(path)
    record = {"scenario": scenario, "setup": setup, "users": cfg["users"], "seconds": cfg["seconds"],
              "wait_s": cfg["wait_s"], **{k: round(v, 3) for k, v in m.items() if k != "returncode"},
              "requests": requests, "failures": failures, "load_before": load_before}
    print(json.dumps(record), flush=True)
    return record, path


def main() -> None:
    fx.DATA.mkdir(exist_ok=True)
    jver = subprocess.run([str(fx.jmeter_home() / "bin" / "jmeter"), "--version"], capture_output=True, text=True,
                          env={**os.environ, "JAVA_HOME": fx.java_home() or ""}).stdout
    runs: list[dict] = []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for repeat in range(1, REPEATS + 1):
            for scenario in SCENARIOS:
                for setup in SETUPS:
                    record, path = one_run(scenario, setup, tmp)
                    record["repeat"] = repeat
                    runs.append(record)
                    if repeat == REPEATS and scenario == "steady" and setup in KEEP:
                        (save_jtl if setup.startswith("jmeter") else save_locust)(path)
    data = {
        "captured": date.today().isoformat(),
        "machine": {"cpus": os.cpu_count(), "python": platform.python_version(), "os": platform.platform()},
        "scenarios": SCENARIOS,
        "repeats": REPEATS,
        "jmeter_version_line": [ln for ln in jver.splitlines() if "5." in ln][:1],
        "runs": runs,
    }
    (fx.DATA / "runs.json").write_text(json.dumps(data, indent=1) + "\n")
    print("wrote", fx.DATA / "runs.json")


if __name__ == "__main__":
    main()
