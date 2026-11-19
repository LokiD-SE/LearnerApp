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
    # TODO: one Sample per row - label, timeStamp, elapsed, success == "true", allThreads (0 if missing).
    raise NotImplementedError("from_jtl")


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of the values at or below it."""
    # TODO: sort, rank = ceil(p / 100 * n), return the value at rank - 1. Raise ValueError for no values
    # or p outside (0, 100].
    raise NotImplementedError("percentile")


def latency_sli(samples: list[Sample], threshold_ms: float) -> float:
    """SRE-style SLI: good events / all events, where good = successful and no slower than the threshold."""
    # TODO: good / total; ValueError when there are no samples.
    raise NotImplementedError("latency_sli")


def achieved_rate(samples: list[Sample]) -> float:
    """Samples per second over the span from the first start to the last end."""
    # TODO: len(samples) / seconds from the earliest timestamp to the latest timestamp + elapsed; 0.0 if empty.
    raise NotImplementedError("achieved_rate")


def evaluate(samples: list[Sample], requirements: list[Requirement], min_samples: int = 100) -> list[Verdict]:
    """One Verdict per requirement, in order, following the rules in the module docstring.

    TODO, per requirement:
    - take the samples whose label equals the requirement's transaction;
    - too few -> "inconclusive", observed None, a note naming the count ("only 20 samples (need 100)");
    - check the load: req/s -> achieved_rate >= LOAD_TOLERANCE * load; users -> peak threads >= load;
      not reached -> "inconclusive" with a note starting "load not reached";
    - latency: nearest-rank percentile of successful samples' elapsed_ms vs threshold_ms;
    - errors: failed / all * 100, rounded to 2 places, vs max_error_percent.
    """
    raise NotImplementedError("evaluate")


def overall(verdicts: list[Verdict]) -> str:
    """TODO: "fail" if any verdict fails, "pass" only if all pass, otherwise "inconclusive"."""
    raise NotImplementedError("overall")
