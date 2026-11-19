"""Percentiles four ways - the definitions behind the numbers load tools print.

Reference solution for the lesson "Performance metrics and percentiles" (Track K). Every function takes
response times in milliseconds and a percentile ``pct`` in percent (``0 < pct <= 100``) and raises
``ValueError`` for no values or a ``pct`` outside that range.

- ``nearest_rank``: the textbook nearest-rank definition - the smallest value with at least ``pct`` % of
  the values at or below it (rank = ceil(pct/100 * n)). Always an observed value.
- ``dashboard_percentile``: what JMeter's HTML dashboard reports (``statistics.json``: medianResTime,
  pct1ResTime ...). The report generator uses Apache Commons Math ``Percentile`` with the LEGACY estimation
  type: position (n + 1) * pct / 100, interpolate linearly between neighbours, clamp to min / max.
- ``aggregate_report_percentile``: what JMeter's Aggregate Report listener shows (``StatCalculator``):
  walk the sorted values until ``Math.round(n * pct/100)`` of them are counted; ``pct >= 100`` is the max.
- ``locust_bucket`` / ``locust_percentile``: what Locust 2.47 reports. It stores each response time rounded
  to about two significant digits, then walks the buckets from the slowest down.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable


def _check(values: Iterable[float], pct: float) -> list[float]:
    data = sorted(values)
    if not data:
        raise ValueError("no response times")
    if not 0 < pct <= 100:
        raise ValueError(f"pct must be in (0, 100], got {pct}")
    return data


def nearest_rank(values: Iterable[float], pct: float) -> float:
    data = _check(values, pct)
    rank = math.ceil(pct / 100 * len(data))
    return data[max(rank, 1) - 1]


def dashboard_percentile(values: Iterable[float], pct: float) -> float:
    data = _check(values, pct)
    n = len(data)
    pos = (n + 1) * pct / 100
    if pos < 1:
        return float(data[0])
    if pos >= n:
        return float(data[-1])
    lower = math.floor(pos)
    fraction = pos - lower
    return data[lower - 1] + fraction * (data[lower] - data[lower - 1])


def aggregate_report_percentile(values: Iterable[float], pct: float) -> float:
    data = _check(values, pct)
    if pct >= 100:
        return data[-1]
    target = math.floor(len(data) * pct / 100 + 0.5)  # Java Math.round
    for value, count in sorted(Counter(data).items()):
        target -= count
        if target <= 0:
            return value
    return data[-1]


def locust_bucket(response_time_ms: float) -> int:
    if response_time_ms < 100:
        return round(response_time_ms)
    if response_time_ms < 1000:
        return int(round(response_time_ms, -1))
    if response_time_ms < 10000:
        return int(round(response_time_ms, -2))
    return int(round(response_time_ms, -3))


def locust_percentile(values: Iterable[float], pct: float) -> int:
    data = _check(values, pct)
    buckets = Counter(locust_bucket(v) for v in data)
    n = len(data)
    wanted = int(n * (pct / 100))
    processed = 0
    for bucket in sorted(buckets, reverse=True):
        processed += buckets[bucket]
        if n - processed <= wanted:
            return bucket
    return 0  # not reached: the loop always returns by the smallest bucket
