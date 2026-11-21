"""Prints every number the performance testing mock interview lesson shows. Run from practice/perf:

    .venv/bin/python support/pmi_demo.py

It imports the reference solutions and runs two short real closed-model loads against the practice target
(loopback only). Timings depend on the machine; the verdicts do not.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "solutions"))
sys.path.insert(1, str(ROOT / "support"))

from capstone.pmi_sizing import arrival_rate, pacing_interval, throughput_for_users, users_for_throughput, workers_needed  # noqa: E402
from capstone.pmi_smells import next_step, smells, verdict  # noqa: E402
from capstone.pmi_validate import compare, explain  # noqa: E402
from pmi_fixture import load_runs, run_closed, serve_separately  # noqa: E402


def sizing() -> None:
    print("== sizing: 2,000,000 checkout requests a day, a 4x peak, 0.25 s to answer, 3 s of thinking")
    rate = arrival_rate(2_000_000, peak_factor=4)
    print(f"peak rate     : {rate:.1f} requests/s")
    print(f"users needed  : {users_for_throughput(rate, 0.25, 3.0)} (closed model, N = X * (R + Z))")
    print(f"workers       : {workers_needed(rate, 0.08)} at 0.08 s of service time and 70% utilisation")
    print(f"pacing        : one iteration every {pacing_interval(users_for_throughput(rate, 0.25, 3.0), rate):.2f} s per user")
    print(f"sanity check  : {throughput_for_users(users_for_throughput(rate, 0.25, 3.0), 0.25, 3.0):.1f} requests/s offered")


def validation() -> None:
    print("== validating the estimate: 8 users, 0.05 s think time, 20 ms service time")
    plan = throughput_for_users(8, 0.02, 0.05)
    print(f"the plan predicts {plan:.1f} requests/s")
    for label, workers in (("16 workers", 16), ("1 worker", 1)):
        with serve_separately(latency_ms=20, capacity=workers) as base:
            run = run_closed(base, 8, 2.5, think_s=0.05)
        by_plan = compare(plan, run["achieved_rps"], tolerance=0.2)
        by_run = compare(throughput_for_users(8, run["mean_ms"] / 1000, 0.05), run["achieved_rps"], tolerance=0.15)
        print(f"{label:10}: measured {run['achieved_rps']:5.1f}/s, mean {run['mean_ms']:5.1f} ms -> "
              f"plan {by_plan}, measured response {by_run}")
        print(f"            {explain(by_plan)}")


def smell_report() -> None:
    print("== result smells on five captured runs")
    for name, run in load_runs().items():
        found = smells(run)
        print(f"{name:15} samples={run['samples']:5} errors={run['errors']:5} rps={run['achieved_rps']:6.1f} "
              f"plan={run['planned_rps']} cpu={run['generator_cpu_pct']} -> {found or 'none'} {verdict(found)}")
    run = load_runs()["slow_generator"]
    print("advice for slow_generator:", next_step(smells(run)))
    print("advice for fast_failures :", next_step(smells(load_runs()["fast_failures"])))


if __name__ == "__main__":
    sizing()
    validation()
    smell_report()
