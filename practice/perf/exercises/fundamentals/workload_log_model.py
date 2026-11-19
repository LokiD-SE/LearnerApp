"""Workload model from an access log - EXERCISE.

From one day of SandPay API access log lines (see support/workload_fixture.py for the format) derive what a
load test needs: the transaction mix, the peak arrival rate and peak factor, how skewed the traffic is across
merchants, integer task weights for Locust or JMeter, and the peak rate projected for growth.

A log line looks like this (client "-" means no authenticated client):

    203.0.113.24 - merchant-7 [17/Nov/2026:12:03:41 +0000] "GET /v1/payments?limit=20 HTTP/1.1" 200 812 0.034

Run: .venv/bin/python -m pytest tests/fundamentals/test_workload_log_model.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

NOT_USER_TRAFFIC = frozenset({"GET /health"})


def parse_line(line: str) -> dict | None:
    """One log line as a dict, or None if the line is malformed.

    Keys: ip, client (None when "-"), ts (aware datetime, UTC), method, target, status (int), bytes (int),
    duration (float seconds).

    TODO: match the line with a regular expression (anchor both ends), parse the timestamp with
    datetime.strptime(..., "%d/%b/%Y:%H:%M:%S %z") and convert it to UTC. Return None - never raise - for
    anything that does not match.
    """
    raise NotImplementedError("parse_line")


def endpoint(method: str, target: str) -> str:
    """The transaction name: method plus path, query string dropped, payment ids replaced by {id}.

    endpoint("GET", "/v1/payments/pay_100123?expand=x") == "GET /v1/payments/{id}"

    TODO: drop everything after "?", and replace any path segment that looks like pay_<digits> with {id}.
    """
    raise NotImplementedError("endpoint")


def transaction_mix(records: Iterable[dict], exclude: frozenset[str] = NOT_USER_TRAFFIC) -> dict[str, float]:
    """Share of each transaction among user requests (excluded endpoints removed), largest first.

    TODO: skip None records and records whose endpoint() is in ``exclude``; count by endpoint; divide by the
    total; return a dict ordered from the most to the least common.
    """
    raise NotImplementedError("transaction_mix")


def peak_window(records: Iterable[dict], window_s: int = 3600,
                exclude: frozenset[str] = NOT_USER_TRAFFIC) -> tuple[datetime, int, float]:
    """The busiest fixed window (aligned to multiples of window_s since the Unix epoch).

    Returns (window start as UTC datetime, requests in the window, requests per second). Ties go to the
    earliest window.

    TODO: bucket user requests by int(ts.timestamp()) // window_s and pick the fullest bucket.
    """
    raise NotImplementedError("peak_window")


def peak_factor(records: Iterable[dict], window_s: int = 3600,
                exclude: frozenset[str] = NOT_USER_TRAFFIC) -> float:
    """Peak window rate divided by the mean rate over the whole period the user requests span.

    The period runs from the first window to the last window that contains a request, so quiet windows in
    between count (as zero) and the mean is the true average.

    TODO: mean rate = user requests / (number of windows from first to last, inclusive * window_s).
    """
    raise NotImplementedError("peak_factor")


def client_share(records: Iterable[dict], top_fraction: float = 0.1,
                 exclude: frozenset[str] = NOT_USER_TRAFFIC) -> float:
    """Share of user requests sent by the busiest top_fraction of clients (rounded up, at least one client).

    Requests without a client id are ignored.

    TODO: count requests per client, take the ceil(clients * top_fraction) busiest, divide their total by the
    total of all clients.
    """
    raise NotImplementedError("client_share")


def task_weights(mix: dict[str, float], total: int = 100) -> dict[str, int]:
    """Integer weights that add up to ``total`` and keep the mix's proportions (largest remainder method).

    Every transaction in the mix keeps a weight of at least 1, so rare-but-real requests are not dropped.

    TODO: scale each share to ``total``, floor it (minimum 1), then hand out the remaining units one by one
    to the largest fractional remainders (ties: alphabetical). If the minimum of 1 pushed the sum over
    ``total``, take units back from the largest weights.
    """
    raise NotImplementedError("task_weights")


def project_peak(peak_rps: float, annual_growth: float, months: int, headroom: float = 0.0) -> float:
    """Peak rate after ``months`` of compound growth at ``annual_growth`` (0.4 = 40 % a year), plus headroom.

    TODO: peak * (1 + growth) ** (months / 12) * (1 + headroom). Raise ValueError for a negative peak,
    growth <= -1, negative months or negative headroom.
    """
    raise NotImplementedError("project_peak")
