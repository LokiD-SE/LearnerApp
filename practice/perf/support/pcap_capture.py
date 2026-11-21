"""Captures the real runs behind the capstone and prints what the lesson shows.

    cd practice/perf && .venv/bin/python support/pcap_capture.py

Three runs, each against its own fresh practice API (``pcap_fixture.engagement_config()``, 8 workers):

- ``jmeter_target``  - JMeter, ``pcap_plan.jmx``: 21 threads, 300 ms think time, 50 s (target load, about 60 req/s)
- ``locust_target``  - Locust, ``solutions/capstone/pcap_locustfile.py``: 21 users, 0.3 s think, 50 s, ``--reset-stats``
- ``locust_stress``  - Locust, the same file: 60 users, no think time, 20 s (a closed loop that asks for more than
  the API can serve)

Files go to ``pcap_data/``: the JTL columns the analysers read (``timeStamp`` rebased to ms since the first
sample, so no 13-digit epoch value appears), the Locust ``--json-file`` entries (times rebased to seconds since
the run's start) and ``runs.json`` (settings, API counters, machine load). Takes about two minutes.
"""

from __future__ import annotations

import csv
import json
import os
import platform
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pcap_fixture as fx  # noqa: E402
from load_tools import read_jtl, read_locust_stats, run_jmeter, run_locust  # noqa: E402
from sandpay_target import serve  # noqa: E402

JTL_COLUMNS = ("timeStamp", "elapsed", "label", "responseCode", "success", "allThreads")
LOCUST_FIELDS = ("method", "name", "num_requests", "num_failures", "response_times", "start_time",
                 "last_request_timestamp")
LOCUSTFILE = fx.ROOT / "solutions" / "capstone" / "pcap_locustfile.py"


def api_counters(base: str) -> dict:
    with urllib.request.urlopen(f"{base}/metrics") as r:
        m = json.load(r)
    return {"requests": m["requests"], "max_in_flight": m["max_in_flight"], "statuses": m["statuses"],
            "payments_created": m["payments_created"]}


def save_jtl(name: str, rows: list[dict[str, str]]) -> None:
    first = min(int(r["timeStamp"]) for r in rows)
    with open(fx.DATA / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(JTL_COLUMNS)
        for r in rows:
            w.writerow([str(int(r["timeStamp"]) - first) if c == "timeStamp" else r[c] for c in JTL_COLUMNS])


def save_locust(name: str, stats: dict[str, dict]) -> None:
    entries = [e for e in stats.values() if e["name"] != "Aggregated"]
    t0 = min(e["start_time"] for e in entries)
    out = []
    for e in entries:
        item = {k: e[k] for k in LOCUST_FIELDS}
        item["start_time"] = round(e["start_time"] - t0, 3)
        item["last_request_timestamp"] = round(e["last_request_timestamp"] - t0, 3)
        out.append(item)
    (fx.DATA / f"{name}.json").write_text(json.dumps(out, indent=1) + "\n")


def run_jmeter_target(runs: dict) -> None:
    with serve(fx.engagement_config()) as base:
        jtl = run_jmeter(fx.PLAN, {"port": base.rsplit(":", 1)[1], "threads": 21, "ramp": 2, "duration": 50,
                                   "think": 300}, Path(tempfile.mkdtemp(prefix="pcap-jm-")), timeout=180)
        runs["jmeter_target"] = {"tool": "JMeter 5.6.3", "users": 21, "think_s": 0.3, "duration_s": 50, "ramp_s": 2,
                                 "api": api_counters(base), "loadavg_after": os.getloadavg()[0]}
    save_jtl("jmeter_target", read_jtl(jtl))


def run_locust_run(runs: dict, key: str, users: int, spawn: float, seconds: int, think: float) -> None:
    os.environ["PCAP_THINK"] = str(think)
    with serve(fx.engagement_config()) as base:
        prefix = run_locust(LOCUSTFILE, base, users=users, spawn_rate=spawn, run_time=f"{seconds}s",
                            out_dir=Path(tempfile.mkdtemp(prefix=f"pcap-{key}-")), extra=["--reset-stats"],
                            timeout=180)
        runs[key] = {"tool": "Locust 2.47.0", "users": users, "think_s": think, "duration_s": seconds,
                     "spawn_rate": spawn, "api": api_counters(base), "loadavg_after": os.getloadavg()[0]}
    save_locust(key, read_locust_stats(prefix))


def main() -> None:
    fx.DATA.mkdir(exist_ok=True)
    runs: dict = {"captured": "21 November 2026", "machine": {"cpus": os.cpu_count(), "system": platform.system(),
                                                             "python": platform.python_version()}}
    run_jmeter_target(runs)
    run_locust_run(runs, "locust_target", users=21, spawn=10, seconds=50, think=0.3)
    run_locust_run(runs, "locust_stress", users=60, spawn=30, seconds=20, think=0.0)
    (fx.DATA / "runs.json").write_text(json.dumps(runs, indent=1) + "\n")
    print(json.dumps(runs, indent=1))


if __name__ == "__main__":
    main()
