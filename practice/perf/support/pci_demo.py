"""Prints every number the lesson "Performance testing in CI/CD" shows, from the reference solutions.

    cd practice/perf && .venv/bin/python support/pci_demo.py

It reads the captured runs (``pci_data/history.json``) and the repo's workflow (``pci_data/pages.workflow.json``); the
drift section is a simulation built from the captured baseline and says so. Nothing here starts a load test.
"""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "solutions"))

import pci_fixture as fx  # noqa: E402
from analysis import pci_baseline as pb  # noqa: E402
from analysis import pci_gate as gate  # noqa: E402
from analysis import pci_workflow as wf  # noqa: E402

RUNS = fx.history()
BASE = RUNS["main"][-10:]


def section(title: str) -> None:
    print(f"\n== {title}")


def main() -> None:
    section("the captured baseline: 12 runs of the same build, 4 s each")
    for key in ("p50_ms", "p95_ms", "p99_ms", "samples"):
        print(f"{key:<8}", [r[key] for r in RUNS["main"]])
    for key in ("p95_ms", "p99_ms"):
        b = pb.baseline(BASE, key)
        print(f"{key}: median {b['median']:g}, MAD {b['mad']:g}, n {b['n']}, tolerance "
              f"{pb.tolerance(b, floor=0):.4f} (floor off), {pb.tolerance(b):.4f} (5% floor)")

    section("a fixed percentage against the noise of one build (15 runs, each against the median of the other 14)")
    same = RUNS["main"] + RUNS["same"]
    p95 = [r["p95_ms"] for r in same]
    print("p95 of the 15 runs:", p95)
    for pct in (0.02, 0.05, 0.10):
        flagged = 0
        for i, v in enumerate(p95):
            others = p95[:i] + p95[i + 1:]
            if (v - statistics.median(others)) / statistics.median(others) > pct:
                flagged += 1
        print(f"fixed {pct:.0%} threshold: {flagged} of {len(p95)} identical-build runs flagged")

    section("the gate on the captured runs (history = the last 10 baseline runs)")
    picks = [("main", 0), ("same", 0), ("small", 0), ("small", 1), ("slower", 0), ("slower", 1), ("failing", 0)]
    for name, i in picks:
        run = RUNS[name][i]
        res = gate.evaluate(run, BASE)
        print(f"{run['build']:<10} samples {run['samples']:>3} errors {run['errors']:>2} p95 {run['p95_ms']} ms "
              f"cpu {run['generator_cpu_max']}% -> exit {res['code']} {res['status']} {res['reasons']}")
    busy = {**RUNS["same"][0], "generator_cpu_max": 95}
    print(f"{'busy':<10} (the same run with CPU 95%) -> {gate.evaluate(busy, BASE)}")
    print(f"{'budget':<10} same run, budget 50 ms, no history -> {gate.evaluate(RUNS['same'][0], [], budget_p95=50)}")
    print(f"{'new':<10} same run, empty history -> {gate.evaluate(RUNS['same'][0], [])}")

    section("the command line")
    tmp = Path(tempfile.mkdtemp(prefix="pci-demo-"))
    (tmp / "history.json").write_text(json.dumps(BASE))
    for name, i in (("same", 0), ("small", 1), ("failing", 0)):
        (tmp / "run.json").write_text(json.dumps(RUNS[name][i]))
        code = gate.main(["--run", str(tmp / "run.json"), "--history", str(tmp / "history.json"), "--record"])
        print(f"exit code {code}; history now holds {len(pb.load_history(tmp / 'history.json'))} runs")

    section("simulated drift: each passing run is recorded, every run slower than the last (not measured)")
    for rate in (0.01, 0.02, 0.03):
        hist, level, failed_at = list(BASE), 64.0, None
        for n in range(1, 61):
            level *= 1 + rate
            run = {**RUNS["main"][4], "build": f"sim-{n:02d}", "p95_ms": round(level, 1)}
            res = gate.evaluate(run, hist)
            if res["code"] != 0:
                failed_at = (n, run["p95_ms"])
                break
            hist.append(run)
        if failed_at is None:
            print(f"{rate:.0%} per run: never failed in 60 runs; p95 reached {level:.1f} ms = {level / 64 - 1:+.0%} on the "
                  f"original 64 ms")
            continue
        n, p95 = failed_at
        print(f"{rate:.0%} per run: first failure at run {n}, p95 {p95} ms = {p95 / 64 - 1:+.0%} on the original 64 ms; "
              f"{n - 1} runs passed first")
    budget = 64 * 1.15
    print(f"a fixed budget of {budget:.0f} ms (15% above the original 64 ms) would stop the 1% drift at run "
          f"{next(n for n in range(1, 99) if 64 * 1.01 ** n > budget)}")

    section("the repo's own workflow (.github/workflows/pages.yml, converted to JSON)")
    w = fx.load_workflow("pages.workflow")
    print("triggers:", sorted(wf.triggers(w)))
    print("performance jobs:", wf.perf_jobs(w))
    print("timeouts:", {j: v.get("timeout-minutes") for j, v in w["jobs"].items()})
    for f in wf.lint(w):
        print(f)
    print("with a 45-minute budget:", wf.lint(w, pr_budget_minutes=45))

    section("a nightly job written to pass the linter")
    good = {"on": {"schedule": [{"cron": "17 2 * * *"}], "workflow_dispatch": None},
            "concurrency": {"group": "perf-env"},
            "jobs": {"load": {"runs-on": "ubuntu-latest", "timeout-minutes": 30, "steps": [
                {"uses": "actions/checkout@v4"},
                {"run": "locust -f locustfile.py --headless -u 20 -r 5 -t 5m --json-file results"},
                {"uses": "actions/upload-artifact@v4", "if": "${{ always() }}", "with": {"path": "results*"}}]}}}
    print("findings:", wf.lint(good))
    bad = json.loads(json.dumps(good))
    bad["on"] = {"schedule": [{"cron": "0 2 * * *"}], "pull_request": None}
    del bad["concurrency"]
    bad["jobs"]["load"]["steps"][1]["continue-on-error"] = True
    del bad["jobs"]["load"]["steps"][2]["if"]
    bad["jobs"]["load"]["timeout-minutes"] = 45
    for f in wf.lint(bad):
        print(f"{f['rule']:<22} {f['job']:<5} {f['message']}")


if __name__ == "__main__":
    main()
