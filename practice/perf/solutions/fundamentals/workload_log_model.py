"""Workload model from an access log - reference solution.

From one day of SandPay API access log lines (see support/workload_fixture.py for the format) derive what a
load test needs: the transaction mix, the peak arrival rate and peak factor, how skewed the traffic is across
merchants, integer task weights for Locust or JMeter, and the peak rate projected for growth.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable

LINE = re.compile(
    r'^(?P<ip>\S+) - (?P<client>\S+) \[(?P<ts>[^\]]+)\] "(?P<method>[A-Z]+) (?P<target>\S+) HTTP/[0-9.]+" '
    r"(?P<status>\d{3}) (?P<bytes>\d+) (?P<duration>\d+\.\d+)$"
)
ID_SEGMENT = re.compile(r"^pay_\d+$")
NOT_USER_TRAFFIC = frozenset({"GET /health"})


def parse_line(line: str) -> dict | None:
    """One log line as a dict, or None if the line is malformed.

    Keys: ip, client (None when "-"), ts (aware datetime, UTC), method, target, status (int), bytes (int),
    duration (float seconds).
    """
    m = LINE.match(line.strip())
    if not m:
        return None
    try:
        ts = datetime.strptime(m["ts"], "%d/%b/%Y:%H:%M:%S %z").astimezone(timezone.utc)
    except ValueError:
        return None
    return {
        "ip": m["ip"],
        "client": None if m["client"] == "-" else m["client"],
        "ts": ts,
        "method": m["method"],
        "target": m["target"],
        "status": int(m["status"]),
        "bytes": int(m["bytes"]),
        "duration": float(m["duration"]),
    }


def endpoint(method: str, target: str) -> str:
    """The transaction name: method plus path, query string dropped, payment ids replaced by {id}.

    endpoint("GET", "/v1/payments/pay_100123?expand=x") == "GET /v1/payments/{id}"
    """
    path = target.split("?", 1)[0]
    parts = ["{id}" if ID_SEGMENT.match(p) else p for p in path.split("/")]
    return f"{method} {'/'.join(parts)}"


def _user_records(records: Iterable[dict], exclude: frozenset[str]) -> list[dict]:
    return [r for r in records if r is not None and endpoint(r["method"], r["target"]) not in exclude]


def transaction_mix(records: Iterable[dict], exclude: frozenset[str] = NOT_USER_TRAFFIC) -> dict[str, float]:
    """Share of each transaction among user requests (excluded endpoints removed), largest first."""
    counts = Counter(endpoint(r["method"], r["target"]) for r in _user_records(records, exclude))
    total = sum(counts.values())
    return {name: n / total for name, n in counts.most_common()}


def peak_window(records: Iterable[dict], window_s: int = 3600,
                exclude: frozenset[str] = NOT_USER_TRAFFIC) -> tuple[datetime, int, float]:
    """The busiest fixed window (aligned to multiples of window_s since the Unix epoch).

    Returns (window start as UTC datetime, requests in the window, requests per second). Ties go to the
    earliest window.
    """
    counts = Counter(int(r["ts"].timestamp()) // window_s for r in _user_records(records, exclude))
    if not counts:
        raise ValueError("no user requests")
    best = min(counts, key=lambda w: (-counts[w], w))
    return datetime.fromtimestamp(best * window_s, timezone.utc), counts[best], counts[best] / window_s


def peak_factor(records: Iterable[dict], window_s: int = 3600,
                exclude: frozenset[str] = NOT_USER_TRAFFIC) -> float:
    """Peak window rate divided by the mean rate over the whole period the user requests span.

    The period runs from the first window to the last window that contains a request, so quiet windows in
    between count (as zero) and the mean is the true average.
    """
    users = _user_records(records, exclude)
    windows = [int(r["ts"].timestamp()) // window_s for r in users]
    span = max(windows) - min(windows) + 1
    mean_rate = len(users) / (span * window_s)
    return peak_window(users, window_s, frozenset())[2] / mean_rate


def client_share(records: Iterable[dict], top_fraction: float = 0.1,
                 exclude: frozenset[str] = NOT_USER_TRAFFIC) -> float:
    """Share of user requests sent by the busiest top_fraction of clients (rounded up, at least one client).

    Requests without a client id are ignored.
    """
    counts = Counter(r["client"] for r in _user_records(records, exclude) if r["client"])
    top_n = max(1, math.ceil(len(counts) * top_fraction))
    return sum(n for _, n in counts.most_common(top_n)) / sum(counts.values())


def task_weights(mix: dict[str, float], total: int = 100) -> dict[str, int]:
    """Integer weights that add up to ``total`` and keep the mix's proportions (largest remainder method).

    Every transaction in the mix keeps a weight of at least 1, so rare-but-real requests are not dropped.
    """
    if not mix:
        return {}
    share_sum = sum(mix.values())
    exact = {k: v / share_sum * total for k, v in mix.items()}
    weights = {k: max(1, math.floor(x)) for k, x in exact.items()}
    remainder = total - sum(weights.values())
    by_remainder = sorted(mix, key=lambda k: (-(exact[k] - math.floor(exact[k])), k))
    i = 0
    while remainder > 0:
        weights[by_remainder[i % len(by_remainder)]] += 1
        remainder -= 1
        i += 1
    while remainder < 0:  # minimum weights pushed the sum over: take from the largest
        largest = max(weights, key=lambda k: (weights[k], k))
        weights[largest] -= 1
        remainder += 1
    return weights


def project_peak(peak_rps: float, annual_growth: float, months: int, headroom: float = 0.0) -> float:
    """Peak rate after ``months`` of compound growth at ``annual_growth`` (0.4 = 40 % a year), plus headroom."""
    if peak_rps < 0 or annual_growth <= -1 or months < 0 or headroom < 0:
        raise ValueError("invalid projection input")
    return peak_rps * (1 + annual_growth) ** (months / 12) * (1 + headroom)
