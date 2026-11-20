"""jm_dash_ exercise 3: a CI quality gate over the dashboard's statistics.json.

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
    """The statistics.json key for a metric: "error_pct" -> "errorPct", "mean_ms" -> "meanResTime",
    "p95_ms" -> "pct2ResTime" when 95 is the 2nd of the report's percentiles (90,95,99).

    TODO: GateInputError for an unknown metric, or a p<N>_ms whose N is not one of the three percentiles
    (compare as floats, so "p99.9_ms" works with 99.9).
    """
    raise NotImplementedError("TODO: map a metric name to its statistics.json key")


def evaluate(statistics: dict, slo: dict, percentiles: tuple[float, ...] = (90, 95, 99),
             min_samples: int = 1) -> list[Check]:
    """One Check per (label, metric) in the SLO, in the SLO's order.

    TODO: GateInputError when there are not exactly three percentiles, a label is not in the report, a label
    has fewer than min_samples samples (sampleCount), or the SLO yields no checks at all.
    """
    raise NotImplementedError("TODO: compare the report with the SLO")


def main(argv: list[str] | None = None) -> int:
    """TODO: parse ``statistics`` (path), ``--slo`` (path, required), ``--percentiles`` (default "90,95,99") and
    ``--min-samples`` (default 1) with argparse; run evaluate; print one line per check -
    ``PASS Total error_pct 0.50 (limit 1)`` / ``FAIL ...`` (actual with 2 decimals, limit with :g) - then
    ``<n> passed, <m> failed``; return 0 or 1. A missing or unreadable file, bad JSON or a GateInputError
    prints ``ERROR <reason>`` to stderr and returns 2.
    """
    raise NotImplementedError("TODO: the command-line gate")


if __name__ == "__main__":
    sys.exit(main())
