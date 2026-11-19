"""Percentiles four ways - the definitions behind the numbers load tools print.

Exercise for the lesson "Performance metrics and percentiles" (Track K).
Test: .venv/bin/python -m pytest tests/fundamentals/test_metrics_percentiles.py

Every function takes response times in milliseconds (any iterable, any order) and a percentile ``pct`` in
percent. Raise ``ValueError`` when there are no values or when ``pct`` is not in the range ``0 < pct <= 100``.
"""

from __future__ import annotations

import math  # noqa: F401 - you will need it
from collections import Counter  # noqa: F401 - you will need it
from collections.abc import Iterable


def nearest_rank(values: Iterable[float], pct: float) -> float:
    """TODO: the nearest-rank percentile - sort, rank = ceil(pct / 100 * n) (at least 1), return the value at
    that 1-based rank. It is always one of the observed values."""
    raise NotImplementedError("nearest_rank")


def dashboard_percentile(values: Iterable[float], pct: float) -> float:
    """TODO: what JMeter's HTML dashboard reports - Apache Commons Math Percentile, LEGACY estimation.

    pos = (n + 1) * pct / 100 on the 1-based sorted values:
    - pos < 1: the minimum; pos >= n: the maximum;
    - otherwise interpolate: x[floor(pos)] + (pos - floor(pos)) * (x[floor(pos) + 1] - x[floor(pos)]).
    """
    raise NotImplementedError("dashboard_percentile")


def aggregate_report_percentile(values: Iterable[float], pct: float) -> float:
    """TODO: what JMeter's Aggregate Report listener shows (jorphan StatCalculator.getPercentPoint).

    pct >= 100 returns the maximum. Otherwise target = Java's Math.round(n * pct / 100), which is
    floor(x + 0.5) - not Python's round(). Walk the distinct values in ascending order, subtracting each
    value's count from target; return the first value where target <= 0.
    """
    raise NotImplementedError("aggregate_report_percentile")


def locust_bucket(response_time_ms: float) -> int:
    """TODO: Locust 2.47's bucket for one response time (locust.stats.bucket_response_time):
    below 100 ms round to 1 ms, below 1000 to 10 ms, below 10000 to 100 ms, else to 1000 ms.
    Use Python's round() (round(147, -1) == 150, round(145, -1) == 140) and return an int."""
    raise NotImplementedError("locust_bucket")


def locust_percentile(values: Iterable[float], pct: float) -> int:
    """TODO: Locust's percentile (locust.stats.calculate_response_time_percentile) over bucketed times.

    Count values per locust_bucket. n = number of values; wanted = int(n * (pct / 100)) - divide first, as
    Locust stores 0.95, not 95. Walk the buckets from the slowest down, adding each bucket's count to a
    running total; return the first bucket where n - total <= wanted.
    """
    raise NotImplementedError("locust_percentile")
