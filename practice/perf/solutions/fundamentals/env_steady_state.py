"""Exercise: find the warm-up and the steady-state window in a run (lesson "Test environments and test data").

A fresh deployment is slow at first (cold caches, opening pools, JIT compilation). Results that include that
warm-up describe a system nobody runs in production. This exercise reads raw samples from a JMeter results
file (JTL, CSV), buckets them by time, and finds where the run settles.

Algorithm (do exactly this, so the tests can check it):

1. ``load_samples(jtl_rows)``: keep successful samples (``success == "true"``) as
   ``(timeStamp_ms, elapsed_ms)`` integer pairs, sorted by time.
2. ``bucket(samples, width_ms)``: group by ``(timeStamp - first timeStamp) // width_ms``. For each non-empty
   bucket return ``Bucket(index, count, median_ms)``, where median is ``statistics.median`` of the elapsed
   times, in bucket order. Empty buckets are skipped.
3. ``steady_start(buckets, window, tolerance)``: the reference is the median of the medians of the LAST
   ``window`` buckets (the run's settled level). Return the position (in the list, not the bucket index) of
   the first bucket from which ``window`` consecutive buckets all have a median within ``tolerance`` (a
   fraction) of that reference. Raise ValueError if there are fewer than ``window`` buckets, or if no such
   run of buckets exists (the run never settled - not even its last buckets agree).
4. ``summarise(buckets, start)``: from position ``start`` on, return ``(samples, median_of_medians)``.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class Bucket:
    index: int
    count: int
    median_ms: float


def load_samples(jtl_rows: list[dict[str, str]]) -> list[tuple[int, int]]:
    samples = [(int(r["timeStamp"]), int(r["elapsed"])) for r in jtl_rows if r["success"] == "true"]
    return sorted(samples)


def bucket(samples: list[tuple[int, int]], width_ms: int) -> list[Bucket]:
    if not samples:
        return []
    first = samples[0][0]
    groups: dict[int, list[int]] = {}
    for ts, elapsed in samples:
        groups.setdefault((ts - first) // width_ms, []).append(elapsed)
    return [Bucket(i, len(v), float(statistics.median(v))) for i, v in sorted(groups.items())]


def steady_start(buckets: list[Bucket], window: int = 3, tolerance: float = 0.5) -> int:
    if len(buckets) < window:
        raise ValueError(f"need at least {window} buckets, got {len(buckets)}")
    reference = statistics.median(b.median_ms for b in buckets[-window:])
    for pos in range(len(buckets) - window + 1):
        if all(abs(b.median_ms - reference) <= tolerance * reference for b in buckets[pos:pos + window]):
            return pos
    raise ValueError("the run never settled: no window of buckets agrees with the final level")


def summarise(buckets: list[Bucket], start: int) -> tuple[int, float]:
    steady = buckets[start:]
    return sum(b.count for b in steady), float(statistics.median(b.median_ms for b in steady))
