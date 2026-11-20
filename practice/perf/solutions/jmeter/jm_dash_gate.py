"""jm_dash_ exercise 3 (reference solution): a CI quality gate over the dashboard's statistics.json.

JMeter's CLI mode exits 0 when the test ran, however many samples failed - in this lesson's run 11 of 62
samples (17.74 %) failed and ``echo $?`` printed 0. A pipeline therefore needs its own gate: read the numbers,
compare them with the SLOs and choose the exit code.

SLO file (JSON), per label (or "Total"), each a maximum:

    {"Total": {"error_pct": 1.0, "p95_ms": 300},
     "GET /v1/payments": {"p99_ms": 200, "mean_ms": 50}}

Metrics: ``error_pct``, ``mean_ms`` and ``p<N>_ms`` where N is one of the report's three percentiles.

Exit codes of ``main``: 0 every check passed; 1 at least one check failed; 2 the gate could not judge (missing
or unreadable file, an SLO with no checks, unknown label or metric, a percentile the report does not have, too few samples). "Could
not judge" must never look like a pass.

Run: ``python -m jmeter.jm_dash_gate report/statistics.json --slo slo.json --percentiles 90,95,99``
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

PCT_KEYS = ("pct1ResTime", "pct2ResTime", "pct3ResTime")
PLAIN = {"error_pct": "errorPct", "mean_ms": "meanResTime"}


class GateInputError(ValueError):
    """The gate cannot judge this report against these SLOs."""


@dataclass(frozen=True)
class Check:
    label: str
    metric: str
    limit: float
    actual: float

    @property
    def ok(self) -> bool:
        return self.actual <= self.limit


def metric_key(metric: str, percentiles: tuple[float, ...]) -> str:
    """The statistics.json key for a metric: "error_pct" -> "errorPct", "p95_ms" -> "pct2ResTime" (95 is the
    2nd of 90,95,99)."""
    if metric in PLAIN:
        return PLAIN[metric]
    if metric.startswith("p") and metric.endswith("_ms"):
        try:
            p = float(metric[1:-3])
        except ValueError:
            raise GateInputError(f"unknown metric {metric!r}") from None
        for key, have in zip(PCT_KEYS, percentiles):
            if float(have) == p:
                return key
        raise GateInputError(f"{metric}: the report has percentiles {', '.join(f'{x:g}' for x in percentiles)}")
    raise GateInputError(f"unknown metric {metric!r}")


def evaluate(statistics: dict, slo: dict, percentiles: tuple[float, ...] = (90, 95, 99),
             min_samples: int = 1) -> list[Check]:
    """One Check per (label, metric) in the SLO, in the SLO's order."""
    if len(percentiles) != 3:
        raise GateInputError("a JMeter dashboard has exactly three percentiles")
    checks = []
    for label, limits in slo.items():
        if label not in statistics:
            raise GateInputError(f"label {label!r} is not in the report (labels: {', '.join(sorted(statistics))})")
        entry = statistics[label]
        if entry["sampleCount"] < min_samples:
            raise GateInputError(f"{label}: {entry['sampleCount']} samples, the gate needs at least {min_samples}")
        for metric, limit in limits.items():
            checks.append(Check(label, metric, float(limit), float(entry[metric_key(metric, percentiles)])))
    if not checks:
        raise GateInputError("the SLO has no checks - an empty gate would pass everything")
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail a CI job when a JMeter dashboard breaks its SLOs.")
    parser.add_argument("statistics", type=Path)
    parser.add_argument("--slo", type=Path, required=True)
    parser.add_argument("--percentiles", default="90,95,99")
    parser.add_argument("--min-samples", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        percentiles = tuple(float(p) for p in args.percentiles.split(","))
        statistics = json.loads(args.statistics.read_text())
        slo = json.loads(args.slo.read_text())
        checks = evaluate(statistics, slo, percentiles, args.min_samples)
    except (OSError, ValueError) as exc:  # json.JSONDecodeError and GateInputError are ValueErrors
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    for c in checks:
        print(f"{'PASS' if c.ok else 'FAIL'} {c.label} {c.metric} {c.actual:.2f} (limit {c.limit:g})")
    failed = sum(not c.ok for c in checks)
    print(f"{len(checks) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
