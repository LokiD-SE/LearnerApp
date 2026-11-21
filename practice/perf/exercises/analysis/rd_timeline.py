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


def percentile(values, pct):
    raise NotImplementedError("TODO: nearest rank - sort, then take rank ceil(n * pct / 100)")


def windows(rows, seconds=1.0):
    raise NotImplementedError("TODO: one dict per window, empty windows included")


def steady_start(wins, tolerance=0.25, run=3):
    raise NotImplementedError("TODO: the start of the first run of windows near the late-run median")


def steady_summary(rows, start_seconds):
    raise NotImplementedError("TODO: summarise only the samples after the warm-up")
