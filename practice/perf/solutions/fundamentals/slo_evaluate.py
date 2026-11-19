"""Exercise slo_evaluate: judge a load test run against its requirements, per transaction.

Rules (the lesson explains each):

- Latency targets use the **nearest-rank percentile** of the elapsed times of **successful** samples of that
  transaction; failures are judged by the error-rate requirement instead.
- The error rate is failed samples / all samples of that transaction, in percent.
- A verdict is ``"inconclusive"`` - not ``"pass"`` - when the run cannot support it: fewer than ``min_samples``
  samples, or the load named in the requirement was not reached (achieved throughput below 90% of the stated
  ``req/s``, or fewer concurrent threads than the stated ``users``).
- The overall result is ``"fail"`` if any verdict fails, ``"pass"`` only if every verdict passes, and
  ``"inconclusive"`` otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fundamentals.slo_spec import Requirement

LOAD_TOLERANCE = 0.9


@dataclass(frozen=True)
class Sample:
    label: str
    timestamp_ms: int  # start of the sample
    elapsed_ms: int
    success: bool
    threads: int = 0  # active threads in the whole test when the sample ended (JMeter allThreads)


@dataclass(frozen=True)
class Verdict:
    transaction: str
    kind: str
    target: float  # threshold in ms, or max error percent
    observed: float | None
    status: str  # "pass", "fail" or "inconclusive"
    samples: int
    note: str = ""


def from_jtl(rows: list[dict[str, str]]) -> list[Sample]:
    """Converts JMeter CSV results (load_tools.read_jtl) into samples."""
    return [
        Sample(r["label"], int(r["timeStamp"]), int(r["elapsed"]), r["success"] == "true", int(r.get("allThreads") or 0))
        for r in rows
    ]


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of the values at or below it."""
    if not values:
        raise ValueError("no values")
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[rank - 1]


def latency_sli(samples: list[Sample], threshold_ms: float) -> float:
    """SRE-style SLI: good events / all events, where good = successful and no slower than the threshold."""
    if not samples:
        raise ValueError("no samples")
    good = sum(1 for s in samples if s.success and s.elapsed_ms <= threshold_ms)
    return good / len(samples)


def achieved_rate(samples: list[Sample]) -> float:
    """Samples per second over the span from the first start to the last end."""
    if not samples:
        return 0.0
    start = min(s.timestamp_ms for s in samples)
    end = max(s.timestamp_ms + s.elapsed_ms for s in samples)
    return len(samples) / max((end - start) / 1000, 0.001)


def evaluate(samples: list[Sample], requirements: list[Requirement], min_samples: int = 100) -> list[Verdict]:
    verdicts = []
    for req in requirements:
        mine = [s for s in samples if s.label == req.transaction]
        target = req.threshold_ms if req.kind == "latency" else req.max_error_percent
        if len(mine) < min_samples:
            verdicts.append(Verdict(req.transaction, req.kind, target, None, "inconclusive", len(mine),
                                    f"only {len(mine)} samples (need {min_samples})"))
            continue
        if req.load_unit == "req/s":
            rate = achieved_rate(mine)
            load_ok, load_note = rate >= LOAD_TOLERANCE * req.load, f"achieved {rate:.1f} req/s"
        else:
            peak = max(s.threads for s in mine)
            load_ok, load_note = peak >= req.load, f"peak {peak} threads"
        if req.kind == "latency":
            ok_times = [s.elapsed_ms for s in mine if s.success]
            observed = percentile(ok_times, req.percentile) if ok_times else None
            passed = observed is not None and observed <= req.threshold_ms
        else:
            observed = round(100 * sum(1 for s in mine if not s.success) / len(mine), 2)
            passed = observed <= req.max_error_percent
        if not load_ok:
            status, note = "inconclusive", f"load not reached: {load_note}, required {req.load:g} {req.load_unit}"
        else:
            status, note = ("pass" if passed else "fail"), load_note
        verdicts.append(Verdict(req.transaction, req.kind, target, observed, status, len(mine), note))
    return verdicts


def overall(verdicts: list[Verdict]) -> str:
    statuses = {v.status for v in verdicts}
    if "fail" in statuses:
        return "fail"
    if statuses == {"pass"}:
        return "pass"
    return "inconclusive"
