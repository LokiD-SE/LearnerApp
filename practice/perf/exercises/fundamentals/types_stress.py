"""Find where a stepped stress test starts to fail - exercise.

TODO: implement per_step() and breaking_point() so the tests in tests/fundamentals/test_types_stress.py pass.

Input: rows of Locust's ``<prefix>_stats_history.csv`` (written with ``--csv-full-history``), as dicts from
``csv.DictReader``. Locust appends one row per second per request name plus an ``Aggregated`` row; the columns
used here are ``User Count``, ``Name``, ``Total Request Count``, ``Total Failure Count`` and ``95%``
(milliseconds, ``N/A`` until there is data). Counts are cumulative since the start of the test.

- ``per_step(rows)`` - split the ``Aggregated`` rows into steps: consecutive rows with the same ``User Count``
  (rows with 0 users - before the first user starts or after the last stops - are not a step). For each step
  return a ``StepResult`` with the requests and failures made DURING the step - the cumulative count on the
  step's last row minus the cumulative count on the row just before the step (0 if there is none) - and the
  highest 95th percentile on the step's rows (``None`` if they are all ``N/A``).
- ``breaking_point(steps, max_error_rate, max_p95_ms)`` - the first step whose error rate (failures/requests)
  is above ``max_error_rate`` or whose p95 is above ``max_p95_ms``; ``None`` if every step passes. A step with
  no requests is skipped (it says nothing).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepResult:
    users: int
    requests: int
    failures: int
    p95_ms: float | None

    @property
    def error_rate(self) -> float:
        return self.failures / self.requests if self.requests else 0.0


def _num(text: str) -> float | None:
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def per_step(rows: list[dict[str, str]]) -> list[StepResult]:
    """One StepResult per run of consecutive Aggregated rows with the same User Count (see the module doc)."""
    raise NotImplementedError("TODO: per_step")


def breaking_point(steps: list[StepResult], max_error_rate: float, max_p95_ms: float) -> StepResult | None:
    """The first step above either threshold, skipping steps with no requests; None if all pass."""
    raise NotImplementedError("TODO: breaking_point")
