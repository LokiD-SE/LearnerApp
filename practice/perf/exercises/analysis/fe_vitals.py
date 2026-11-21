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

THRESHOLDS = {"lcp": (2500, 4000), "inp": (200, 500), "cls": (0.1, 0.25)}  # (good up to, poor above)
RATINGS = ("good", "needs improvement", "poor")


def rate(metric, value):
    raise NotImplementedError("TODO: compare with the two limits of THRESHOLDS[metric]")


def percentile(values, pct):
    raise NotImplementedError("TODO: nearest rank, element ceil(pct / 100 * n)")


def cls(shifts):
    raise NotImplementedError("TODO: session windows (gap < 1000 ms, window < 5000 ms), largest window total")


def assess(samples):
    raise NotImplementedError("TODO: p75 and rating per metric, passes only when all three are good")


def segment(samples, key="device"):
    raise NotImplementedError("TODO: group by key and assess each group")


def distribution(samples, metric):
    raise NotImplementedError("TODO: share of good, needs improvement and poor")
