"""Comparing runs honestly: how much do repeated runs differ, and is a change bigger than that? (no imports)

Each run gives ONE number (say its p95 in milliseconds). ``baseline`` and ``candidate`` are lists of those numbers
from repeated runs of the old and the new build.

1. ``spread(values)`` - the relative range ``(max - min) / median``. Raise ``ValueError`` for no values.
2. ``verdict(baseline, candidate, margin=0.10)`` - one of:
   - ``"inconclusive"`` if either list has fewer than 3 runs;
   - ``"regression"`` if every candidate run is slower than every baseline run (``min(candidate) > max(baseline)``)
     AND the medians differ by more than ``margin`` (``(median(candidate) - median(baseline)) / median(baseline) >
     margin``);
   - ``"improvement"`` if every candidate run is faster than every baseline run AND the median fell by more
     than ``margin``;
   - ``"no difference"`` if the medians differ by ``margin`` or less (either direction);
   - otherwise ``"inconclusive"`` (a big shift in the median, but the runs overlap).
3. ``generator_overloaded(cpu_percent, threshold=90)`` - ``True`` if any sample of the load generator's CPU usage is
   ABOVE ``threshold`` (Locust warns "CPU usage above 90%" on that rule). ``False`` for no samples.
"""

from __future__ import annotations


def spread(values):
    raise NotImplementedError("TODO: (max - min) / median")


def verdict(baseline, candidate, margin=0.10):
    raise NotImplementedError("TODO: regression, improvement, no difference or inconclusive")


def generator_overloaded(cpu_percent, threshold=90):
    raise NotImplementedError("TODO: any CPU sample above the threshold")
