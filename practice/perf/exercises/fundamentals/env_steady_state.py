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
    # TODO: step 1 of the algorithm in the module docstring.
    raise NotImplementedError("load_samples")


def bucket(samples: list[tuple[int, int]], width_ms: int) -> list[Bucket]:
    # TODO: step 2.
    raise NotImplementedError("bucket")


def steady_start(buckets: list[Bucket], window: int = 3, tolerance: float = 0.5) -> int:
    # TODO: step 3.
    raise NotImplementedError("steady_start")


def summarise(buckets: list[Bucket], start: int) -> tuple[int, float]:
    # TODO: step 4.
    raise NotImplementedError("summarise")
