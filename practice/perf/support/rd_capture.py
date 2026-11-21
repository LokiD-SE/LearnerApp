"""Captures the real runs behind the lesson "Reading load test results honestly" and prints what the lesson shows.

    cd practice/perf && .venv/bin/python support/rd_capture.py

It writes ``rd_data/warmup.csv`` and ``rd_data/stall.csv`` (JTL columns of real JMeter runs against
``rd_fixture.serve_service``) and ``rd_data/noise.json`` (final p95 and requests per second of repeated Locust
runs against the practice API), then prints the analysis with the reference solutions. Runs take about two minutes.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "solutions"))

import rd_fixture as fx  # noqa: E402
from load_tools import read_locust_stats, run_locust  # noqa: E402
from sandpay_target import TargetConfig, serve  # noqa: E402

COLUMNS = ("timeStamp", "elapsed", "label", "responseCode", "success")
BASELINE_RUNS = 5
SECONDS_PER_RUN = 4


def save(name: str, rows: list[dict[str, str]]) -> None:
    """Writes the JTL columns the analysers read; ``timeStamp`` is rebased to milliseconds since the first sample
    (a 13-digit epoch value would trip the 13-19 digit card-number check the content tests apply)."""
    fx.DATA.mkdir(exist_ok=True)
    first = min(int(r["timeStamp"]) for r in rows)
    rows = [{**r, "timeStamp": str(int(r["timeStamp"]) - first)} for r in rows]
    with open(fx.DATA / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([r[c] for c in COLUMNS])


def locust_p95(total: dict) -> int:
    """Locust's own percentile function over the run's bucketed response times, in a child process (importing
    locust here would apply gevent's monkey-patching to this process)."""
    code = ("import json, sys; from locust.stats import calculate_response_time_percentile as c; "
            "d = json.load(sys.stdin); print(c({int(k): v for k, v in d['response_times'].items()}, "
            "d['num_requests'] - d['num_none_requests'], 0.95))")
    done = subprocess.run([sys.executable, "-c", code], input=json.dumps(total), capture_output=True, text=True,
                          check=True)
    return int(done.stdout)


def locust_runs(latency_ms: float, runs: int) -> list[dict[str, float]]:
    out = []
    for _ in range(runs):
        with serve(TargetConfig(latency_ms=latency_ms, capacity=4)) as base:
            tmp = Path(tempfile.mkdtemp(prefix="rd-noise-"))
            prefix = run_locust(HERE / "rd_locustfile.py", base, users=8, spawn_rate=8,
                                run_time=f"{SECONDS_PER_RUN}s", out_dir=tmp)
        total = read_locust_stats(prefix)["/v1/payments"]
        out.append({"requests": total["num_requests"], "failures": total["num_failures"],
                    "p95_ms": locust_p95(total),
                    "rps": round(total["num_requests"] / SECONDS_PER_RUN, 1)})
    return out


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="rd-capture-"))
    warm = fx.run_closed(work / "warm", fx.ServiceConfig(base_ms=30, warmup_requests=60, warmup_extra_ms=300), 4, 8)
    save("warmup.csv", warm)
    stall = fx.run_paced(work / "stall", fx.ServiceConfig(base_ms=10, stall_at=80, stall_s=1.5), 1200, 4, 10)
    save("stall.csv", stall)
    noise = {"baseline_ms": 20, "candidate_ms": 26,
             "baseline": locust_runs(20, BASELINE_RUNS), "same_again": locust_runs(20, BASELINE_RUNS),
             "candidate": locust_runs(26, BASELINE_RUNS)}
    (fx.DATA / "noise.json").write_text(json.dumps(noise, indent=1) + "\n")
    print("captured", len(warm), "warm-up rows,", len(stall), "stall rows; noise:")
    for name in ("baseline", "same_again", "candidate"):
        print(name, [(r["p95_ms"], r["rps"]) for r in noise[name]])


if __name__ == "__main__":
    main()
