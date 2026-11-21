"""Regenerates support/pmi_data/runs.json: five real closed-model runs against the practice target, each summarised
the way ``pmi_smells.smells`` reads them. Run it from practice/perf:

    .venv/bin/python support/pmi_capture.py

The numbers depend on the machine; the scenarios are chosen so that the verdicts do not.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pmi_fixture import DATA, run_closed, serve_separately  # noqa: E402

SERVICE_MS = 20.0


def planned(clients: int, think_s: float) -> float:
    """What the test plan promised: N / (planned response + think), with the planned response = the service time."""
    return round(clients / (SERVICE_MS / 1000 + think_s), 1)


def main() -> None:
    runs: dict[str, dict] = {}
    with serve_separately(latency_ms=SERVICE_MS, capacity=16) as base:
        runs["healthy"] = run_closed(base, 8, 4.0, think_s=0.05, planned_rps=planned(8, 0.05))
        runs["too_short"] = run_closed(base, 2, 0.4, think_s=0.05, planned_rps=planned(2, 0.05))
        runs["slow_generator"] = run_closed(base, 8, 4.0, think_s=0.05, burn_ms=15.0, planned_rps=planned(8, 0.05))
    with serve_separately(latency_ms=SERVICE_MS, capacity=2) as base:
        runs["below_plan"] = run_closed(base, 8, 4.0, think_s=0.02, planned_rps=planned(8, 0.02))
    with serve_separately(latency_ms=SERVICE_MS, capacity=2, queue_limit=0) as base:
        runs["fast_failures"] = run_closed(base, 6, 3.0, think_s=0.01)
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(runs, indent=2) + "\n")
    for name, r in runs.items():
        print(name, {k: r[k] for k in ("samples", "errors", "achieved_rps", "planned_rps", "p50_all_ms", "p50_ok_ms",
                                       "p95_ok_ms", "generator_cpu_pct")})


if __name__ == "__main__":
    main()
