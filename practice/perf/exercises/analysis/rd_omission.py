"""Coordinated omission: finding the requests a stalled run never sent, and correcting the percentiles (no imports).

A closed-loop load generator sends its next request only after the last answer arrived, so while the server
stalls it stops sending - and the slow moment is recorded as a few slow samples instead of the many that real,
independent users would have had. ``rows`` are JTL rows as ``csv.DictReader`` gives them (``timeStamp`` and
``elapsed`` in milliseconds, ``success`` as ``"true"`` / ``"false"``). Two intervals appear, and they are not the same number. ``interval_ms``
is the gap the whole test MEANT to leave between any two requests (1200 samples per minute from a Constant
Throughput Timer means 50). ``stream_interval_ms`` is the gap ONE thread meant to leave between its own requests
(4 threads sharing 1200 per minute: 4 x 50 = 200) - the correction models one stream of measurements.

1. ``percentile(values, pct)`` - nearest rank (rank ``ceil(n * pct / 100)``, 1-based); ``ValueError`` for no values.
2. ``fill_expected_interval(values, interval_ms)`` - HdrHistogram's ``recordValueWithExpectedInterval`` correction.
   For every value, keep it, and if it is larger than ``interval_ms`` also add the values it implies were never
   measured: ``value - interval``, ``value - 2 * interval`` ... for as long as the added value is at least
   ``interval``. Return the new list (originals first, in order, each followed by its added values).
   A value of 100 with interval 30 adds 70 and 40 (not 10).
3. ``find_gaps(rows, interval_ms, factor=5.0)`` - sort the rows by ``timeStamp`` and report every gap between two
   consecutive START times larger than ``factor * interval_ms`` as
   ``{"after_s": seconds from the first start to the start before the gap, "gap_ms": the gap,
   "missing": gap_ms // interval_ms - 1}`` (integers; ``after_s`` rounded to 1 decimal). No rows, no gaps.
4. ``corrected_percentiles(rows, stream_interval_ms)`` - p50, p95 and p99 of the SUCCESSFUL ``elapsed`` values twice:
   ``{"measured": {"p50", "p95", "p99"}, "corrected": {"p50", "p95", "p99"}}``, the second after
   ``fill_expected_interval`` with ``stream_interval_ms``.
"""

from __future__ import annotations


def percentile(values, pct):
    raise NotImplementedError("TODO: nearest rank")


def fill_expected_interval(values, interval_ms):
    raise NotImplementedError("TODO: add value - interval, value - 2 * interval ... while >= interval")


def find_gaps(rows, interval_ms, factor=5.0):
    raise NotImplementedError("TODO: gaps between consecutive start times that are too long")


def corrected_percentiles(rows, stream_interval_ms):
    raise NotImplementedError("TODO: percentiles of the measured and of the filled values")
