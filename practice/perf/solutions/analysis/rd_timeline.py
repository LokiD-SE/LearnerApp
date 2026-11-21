"""Reading a load test over time: windows, warm-up and the steady state (no tool imports).

``rows`` are JTL rows as ``csv.DictReader`` gives them: ``timeStamp`` (milliseconds since 1970, when the sample
started), ``elapsed`` (milliseconds) and ``success`` (the strings ``"true"`` / ``"false"``).

1. ``percentile(values, pct)`` - nearest rank: sort, then take the value at rank ``ceil(n * pct / 100)`` (1-based).
   Raise ``ValueError`` for no values.
2. ``windows(rows, seconds=1.0)`` - cut the run into consecutive windows of ``seconds`` starting at the earliest
   ``timeStamp``; a sample belongs to window ``floor((timeStamp - first) / (seconds * 1000))``. Return one dict per
   window from 0 to the last one that has samples, EMPTY WINDOWS INCLUDED, with
   ``{"start": k * seconds, "samples": n, "errors": failed, "p50": ..., "p95": ..., "rps": n / seconds}``.
   ``p50`` and ``p95`` use the successful samples only and are ``None`` when there are none.
3. ``steady_start(wins, tolerance=0.25, run=3)`` - where the steady state begins. The reference is the median of the
   ``p50`` values (skipping ``None``) of the LAST half of the windows (``wins[len(wins) // 2:]``). Return the
   ``start`` of the first window that begins ``run`` consecutive windows whose ``p50`` is within ``tolerance`` of the
   reference (``abs(p50 - ref) <= tolerance * ref``). Return ``None`` if there is no such run or no reference.
4. ``steady_summary(rows, start_seconds)`` - summarise only the samples that STARTED at or after
   ``first + start_seconds``: ``{"samples", "errors", "p50", "p95", "p99"}`` of the successful ones (``None`` for
   the percentiles if there are none).
"""

from __future__ import annotations

import math
import statistics


def percentile(values, pct):
    data = sorted(values)
    if not data:
        raise ValueError("no values")
    return data[max(1, math.ceil(len(data) * pct / 100)) - 1]


def _ok(rows):
    return [int(r["elapsed"]) for r in rows if r["success"] == "true"]


def windows(rows, seconds=1.0):
    if not rows:
        return []
    first = min(int(r["timeStamp"]) for r in rows)
    width = seconds * 1000
    buckets: dict[int, list] = {}
    for r in rows:
        buckets.setdefault(int((int(r["timeStamp"]) - first) // width), []).append(r)
    out = []
    for k in range(max(buckets) + 1):
        group = buckets.get(k, [])
        good = _ok(group)
        out.append({"start": k * seconds, "samples": len(group), "errors": len(group) - len(good),
                    "p50": percentile(good, 50) if good else None, "p95": percentile(good, 95) if good else None,
                    "rps": len(group) / seconds})
    return out


def steady_start(wins, tolerance=0.25, run=3):
    tail = [w["p50"] for w in wins[len(wins) // 2:] if w["p50"] is not None]
    if not tail:
        return None
    ref = statistics.median(tail)
    ok = [w["p50"] is not None and abs(w["p50"] - ref) <= tolerance * ref for w in wins]
    for i in range(len(wins) - run + 1):
        if all(ok[i:i + run]):
            return wins[i]["start"]
    return None


def steady_summary(rows, start_seconds):
    if not rows:
        return {"samples": 0, "errors": 0, "p50": None, "p95": None, "p99": None}
    first = min(int(r["timeStamp"]) for r in rows)
    kept = [r for r in rows if int(r["timeStamp"]) >= first + start_seconds * 1000]
    good = _ok(kept)
    return {"samples": len(kept), "errors": len(kept) - len(good),
            "p50": percentile(good, 50) if good else None, "p95": percentile(good, 95) if good else None,
            "p99": percentile(good, 99) if good else None}
