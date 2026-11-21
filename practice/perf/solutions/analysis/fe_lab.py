"""Lab measurements: the four parts of LCP, total blocking time, and lab against field (standard library only).

1. ``lcp_parts(ttfb, request_start, response_end, lcp)`` - web.dev splits LCP, for a page whose LCP element is an
   image, into four parts that add up to the whole: ``ttfb`` (page start to the first byte of the HTML),
   ``load_delay`` (first byte to the moment the browser starts the image request), ``load_duration`` (that request,
   start to end) and ``render_delay`` (image finished to LCP). All arguments are milliseconds from the page start.
   Return ``{"ttfb", "load_delay", "load_duration", "render_delay"}`` rounded to one decimal. Raise ``ValueError``
   unless ``0 <= ttfb <= request_start <= response_end <= lcp``.
2. ``dominant(parts)`` - the name of the largest part (the first one in the order above on a tie).
3. ``total_blocking_time(tasks, fcp, until=None)`` - ``tasks`` are main-thread tasks ``{"startTime", "duration"}``.
   Total blocking time is the sum of ``duration - 50`` over the LONG tasks (duration above 50 ms) that start at or after
   ``fcp`` and, when ``until`` is given, before ``until``. Return milliseconds as a float.
4. ``lab_vs_field(lab_values, field_p75, tolerance=0.25)`` - compare repeated lab runs with the field 75th
   percentile. Return ``{"lab_median", "lab_spread", "field_p75", "ratio", "verdict"}``: ``lab_spread`` is
   ``(max - min) / median`` of the lab runs rounded to three decimals, ``ratio`` is ``lab_median / field_p75`` rounded to two decimals, and the
   verdict is ``"lab slower"`` when the ratio is above ``1 + tolerance``, ``"lab faster"`` when it is below
   ``1 - tolerance``, otherwise ``"similar"``. ``ValueError`` for no lab values or a field value of 0 or less.
"""

from __future__ import annotations

import statistics


def lcp_parts(ttfb, request_start, response_end, lcp):
    if not (0 <= ttfb <= request_start <= response_end <= lcp):
        raise ValueError("expected 0 <= ttfb <= request_start <= response_end <= lcp")
    return {
        "ttfb": round(ttfb, 1),
        "load_delay": round(request_start - ttfb, 1),
        "load_duration": round(response_end - request_start, 1),
        "render_delay": round(lcp - response_end, 1),
    }


def dominant(parts):
    order = ("ttfb", "load_delay", "load_duration", "render_delay")
    return max(order, key=lambda name: parts[name])


def total_blocking_time(tasks, fcp, until=None):
    total = 0.0
    for t in tasks:
        if t["startTime"] < fcp or (until is not None and t["startTime"] >= until):
            continue
        if t["duration"] > 50:
            total += t["duration"] - 50
    return total


def lab_vs_field(lab_values, field_p75, tolerance=0.25):
    if not lab_values:
        raise ValueError("no lab values")
    if field_p75 <= 0:
        raise ValueError("the field value must be positive")
    median = statistics.median(lab_values)
    ratio = median / field_p75
    verdict = "lab slower" if ratio > 1 + tolerance else "lab faster" if ratio < 1 - tolerance else "similar"
    return {
        "lab_median": median,
        "lab_spread": round((max(lab_values) - min(lab_values)) / median, 3) if median else 0.0,
        "field_p75": field_p75,
        "ratio": round(ratio, 2),
        "verdict": verdict,
    }
