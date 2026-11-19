"""Find where a stepped stress test starts to fail - reference solution.

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
    agg = [r for r in rows if r.get("Name") == "Aggregated"]
    results: list[StepResult] = []
    prev_req = prev_fail = 0
    i = 0
    while i < len(agg):
        users = int(agg[i]["User Count"])
        j = i
        while j + 1 < len(agg) and int(agg[j + 1]["User Count"]) == users:
            j += 1
        end_req, end_fail = int(agg[j]["Total Request Count"]), int(agg[j]["Total Failure Count"])
        if users > 0:
            p95s = [v for v in (_num(r["95%"]) for r in agg[i:j + 1]) if v is not None]
            results.append(StepResult(users, end_req - prev_req, end_fail - prev_fail, max(p95s) if p95s else None))
        prev_req, prev_fail = end_req, end_fail
        i = j + 1
    return results


def breaking_point(steps: list[StepResult], max_error_rate: float, max_p95_ms: float) -> StepResult | None:
    for s in steps:
        if s.requests == 0:
            continue
        if s.error_rate > max_error_rate or (s.p95_ms is not None and s.p95_ms > max_p95_ms):
            return s
    return None
