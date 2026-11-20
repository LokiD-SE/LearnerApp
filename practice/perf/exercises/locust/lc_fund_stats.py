"""Read Locust's final statistics (the ``--json-file`` output) and decide whether a run passes.

``locust --json-file run`` writes ``run.json`` once, when the run ends: a list with one entry per request name, each
holding raw counters (``num_requests``, ``num_failures``, ``total_response_time`` in ms, ``start_time`` and
``last_request_timestamp`` in epoch seconds) and a ``response_times`` histogram {rounded ms: count}. There is no
"Aggregated" entry - you build it, as Locust does for its own summary table.

Implement every function. tests/locust/test_lc_fund_stats.py checks them against a real captured run, against
Locust's own percentile numbers, and on a fresh run against the practice API.
"""

from __future__ import annotations

import json  # noqa: F401 - you will need it
from collections import Counter  # noqa: F401 - handy for aggregate
from pathlib import Path


def entry_key(entry: dict) -> str:
    """TODO: return "<method> <name>", e.g. "GET /v1/payments". Locust groups statistics by method AND name."""
    raise NotImplementedError


def load_stats(path: str | Path) -> dict[str, dict]:
    """TODO: read the JSON list at ``path`` and return its entries keyed by entry_key."""
    raise NotImplementedError


def percentile(response_times: dict, num_requests: int, percent: float) -> int:
    """TODO: the response time (ms) that ``percent`` (0.0-1.0) of the requests finished within, computed the way
    locust.stats.calculate_response_time_percentile does:

    - allowed_below = int(num_requests * percent)
    - walk the histogram keys from the slowest down, adding up their counts
    - return the first key where num_requests - counted <= allowed_below (return 0 if none)

    Keys from JSON are strings ("140"), keys you build may be ints - accept both. Raise ValueError if percent is
    outside 0.0-1.0."""
    raise NotImplementedError


def aggregate(entries: list[dict]) -> dict:
    """TODO: one entry that adds up all the others, like Locust's "Aggregated" row: name "Aggregated", method "",
    summed num_requests, num_none_requests, num_failures and total_response_time, the earliest start_time, the
    latest last_request_timestamp and the merged response_times histogram."""
    raise NotImplementedError


def summarise(entry: dict) -> dict:
    """TODO: return {"requests", "failures", "fail_ratio", "avg_ms", "p50", "p95", "p99", "rps"} for one entry.

    - avg_ms = total_response_time / (num_requests - num_none_requests), rounded to 1 decimal
    - rps = num_requests / (last_request_timestamp - start_time) - the active span, not the nominal run time
    - guard against zero requests and a zero span (return 0.0)"""
    raise NotImplementedError


def ci_verdict(summary: dict, max_fail_ratio: float = 0.01, max_avg_ms: float = 200,
               max_p95_ms: float = 800) -> list[str]:
    """TODO: the reasons a run fails, using the three checks from the Locust docs' CI example. Return one message
    per broken threshold (each message mentions "failure ratio", "average" or "p95"); an empty list means pass.
    A run with zero requests fails with the single reason "no requests were made"."""
    raise NotImplementedError
