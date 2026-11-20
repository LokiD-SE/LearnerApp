"""Read Locust's final statistics (the ``--json-file`` output) and decide whether a run passes - reference solution.

``locust --json-file run`` writes ``run.json`` once, when the run ends: a list with one entry per request name, each
holding raw counters (``num_requests``, ``num_failures``, ``total_response_time`` in ms, ``start_time`` and
``last_request_timestamp`` in epoch seconds) and a ``response_times`` histogram {rounded ms: count}. There is no
"Aggregated" entry - you build it, as Locust does for its own summary table.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def entry_key(entry: dict) -> str:
    """Locust groups statistics by (method, name); "GET /v1/payments" and "POST /v1/payments" are two rows."""
    return f"{entry['method']} {entry['name']}"


def load_stats(path: str | Path) -> dict[str, dict]:
    """The entries of a --json-file output, keyed by entry_key."""
    with open(path) as f:
        entries = json.load(f)
    return {entry_key(e): e for e in entries}


def percentile(response_times: dict, num_requests: int, percent: float) -> int:
    """The response time (ms) that ``percent`` (0.0-1.0) of the requests finished within, computed the way
    locust.stats.calculate_response_time_percentile does: walk the histogram from the slowest bucket down until
    no more than ``num_requests * percent`` requests (rounded down) are left. JSON keys are strings."""
    if not 0.0 <= percent <= 1.0:
        raise ValueError("percent must be between 0.0 and 1.0")
    allowed_below = int(num_requests * percent)
    processed = 0
    for rt in sorted((int(k) for k in response_times), reverse=True):
        processed += response_times[str(rt)] if str(rt) in response_times else response_times[rt]
        if num_requests - processed <= allowed_below:
            return rt
    return 0


def aggregate(entries: list[dict]) -> dict:
    """One entry that adds up all the others, like Locust's "Aggregated" row."""
    times: Counter = Counter()
    for e in entries:
        for k, v in e["response_times"].items():
            times[int(k)] += v
    return {
        "method": "",
        "name": "Aggregated",
        "num_requests": sum(e["num_requests"] for e in entries),
        "num_none_requests": sum(e.get("num_none_requests", 0) for e in entries),
        "num_failures": sum(e["num_failures"] for e in entries),
        "total_response_time": sum(e["total_response_time"] for e in entries),
        "start_time": min(e["start_time"] for e in entries),
        "last_request_timestamp": max(e["last_request_timestamp"] for e in entries),
        "response_times": dict(times),
    }


def summarise(entry: dict) -> dict:
    """requests, failures, fail_ratio, avg_ms (1 decimal), p50, p95, p99 and rps for one entry. rps is requests
    over the entry's own active span (first request start to last request), not the nominal run time."""
    n = entry["num_requests"]
    timed = n - entry.get("num_none_requests", 0)
    span = entry["last_request_timestamp"] - entry["start_time"]
    return {
        "requests": n,
        "failures": entry["num_failures"],
        "fail_ratio": entry["num_failures"] / n if n else 0.0,
        "avg_ms": round(entry["total_response_time"] / timed, 1) if timed else 0.0,
        "p50": percentile(entry["response_times"], n, 0.50),
        "p95": percentile(entry["response_times"], n, 0.95),
        "p99": percentile(entry["response_times"], n, 0.99),
        "rps": n / span if span > 0 else 0.0,
    }


def ci_verdict(summary: dict, max_fail_ratio: float = 0.01, max_avg_ms: float = 200,
               max_p95_ms: float = 800) -> list[str]:
    """The reasons a run fails - the three checks from the Locust docs' CI example (failure ratio over 1 %,
    average over 200 ms, p95 over 800 ms). An empty list means the run passes. Unlike the docs' if/elif chain,
    every broken threshold is reported, so one run shows all of its problems."""
    reasons = []
    if summary["requests"] == 0:
        return ["no requests were made"]
    if summary["fail_ratio"] > max_fail_ratio:
        reasons.append(f"failure ratio {summary['fail_ratio']:.2%} > {max_fail_ratio:.2%}")
    if summary["avg_ms"] > max_avg_ms:
        reasons.append(f"average {summary['avg_ms']} ms > {max_avg_ms} ms")
    if summary["p95"] > max_p95_ms:
        reasons.append(f"p95 {summary['p95']} ms > {max_p95_ms} ms")
    return reasons
