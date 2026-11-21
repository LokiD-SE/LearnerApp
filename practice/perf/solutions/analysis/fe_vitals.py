"""Core Web Vitals in code: rate one value, take the 75th percentile, assess a page (standard library only).

The thresholds are the ones on web.dev (read 21 November 2026): LCP good at 2500 ms or less and poor above 4000 ms;
INP good at 200 ms or less and poor above 500 ms; CLS good at 0.1 or less and poor above 0.25. Anything in between
is "needs improvement". A page PASSES when all three metrics are good at the 75th percentile of its page loads.

1. ``rate(metric, value)`` - ``"good"``, ``"needs improvement"`` or ``"poor"`` for ``"lcp"``, ``"inp"`` or ``"cls"``
   (``ValueError`` for another metric name or a negative value). Exactly on a limit counts as the better rating.
2. ``percentile(values, pct)`` - nearest rank: sort, take element ``ceil(pct / 100 * n)`` (1-based). ``ValueError``
   for no values.
3. ``cls(shifts)`` - the page's Cumulative Layout Shift from layout-shift entries ``{"startTime", "value",
   "hadRecentInput"}``. Ignore entries with ``hadRecentInput`` true. Group the rest, in time order, into SESSION WINDOWS:
   a shift joins the current window when it starts LESS than 1000 ms after the previous shift and LESS than 5000 ms
   after the first shift of the window; otherwise it opens a new window. CLS is the largest window total (0 for no
   shifts).
4. ``assess(samples)`` - ``samples`` are page loads ``{"device", "lcp", "inp", "cls"}``; ``inp`` may be ``None`` (no
   interaction on that visit) and ``None`` values are skipped. Return ``{"lcp": {"p75", "rating", "n"}, "inp": ...,
   "cls": ..., "passes": bool}``. A metric with no values has ``p75`` and ``rating`` of ``None`` and ``n`` 0, and the
   page does not pass.
5. ``segment(samples, key="device")`` - ``{value: assess(group)}``, for example one assessment per device type.
6. ``distribution(samples, metric)`` - the share of the non-``None`` values that rate good, needs improvement and
   poor: ``{"good": 0.88, "needs improvement": 0.08, "poor": 0.04}`` (fractions that sum to 1; all zero for no values).
"""

from __future__ import annotations

import math

THRESHOLDS = {"lcp": (2500, 4000), "inp": (200, 500), "cls": (0.1, 0.25)}
RATINGS = ("good", "needs improvement", "poor")


def rate(metric, value):
    if metric not in THRESHOLDS:
        raise ValueError(f"unknown metric {metric!r}")
    if value < 0:
        raise ValueError("a metric value cannot be negative")
    good, poor = THRESHOLDS[metric]
    if value <= good:
        return "good"
    if value > poor:
        return "poor"
    return "needs improvement"


def percentile(values, pct):
    if not values:
        raise ValueError("no values")
    data = sorted(values)
    return data[math.ceil(pct / 100 * len(data)) - 1]


def cls(shifts):
    kept = sorted((s for s in shifts if not s["hadRecentInput"]), key=lambda s: s["startTime"])
    best = total = 0.0
    first = last = None
    for s in kept:
        t = s["startTime"]
        if first is not None and t - last < 1000 and t - first < 5000:
            total += s["value"]
        else:
            total, first = s["value"], t
        last = t
        best = max(best, total)
    return best


def assess(samples):
    out = {}
    for metric in THRESHOLDS:
        values = [s[metric] for s in samples if s.get(metric) is not None]
        if values:
            p75 = percentile(values, 75)
            out[metric] = {"p75": p75, "rating": rate(metric, p75), "n": len(values)}
        else:
            out[metric] = {"p75": None, "rating": None, "n": 0}
    out["passes"] = all(out[m]["rating"] == "good" for m in THRESHOLDS)
    return out


def segment(samples, key="device"):
    groups = {}
    for s in samples:
        groups.setdefault(s[key], []).append(s)
    return {k: assess(v) for k, v in groups.items()}


def distribution(samples, metric):
    values = [s[metric] for s in samples if s.get(metric) is not None]
    counts = {r: 0 for r in RATINGS}
    for v in values:
        counts[rate(metric, v)] += 1
    return {r: (counts[r] / len(values) if values else 0.0) for r in RATINGS}
