"""A baseline store and a comparison that knows how noisy the baseline is. (needs only the standard library)

A **run summary** is a dict like ``{"build": "main-07", "p95_ms": 62, "samples": 130, ...}``; the history is a list of
them, oldest first, kept in a JSON file that the CI job restores and saves between runs.

1. ``load_history(path)`` - the list in the file; ``[]`` when the file does not exist yet. A file that is not valid
   JSON, or whose top level is not a list, raises ``ValueError`` (never silently start a new history: a lost baseline
   means every later run "passes").
2. ``save_run(path, run, keep=30)`` - append ``run``, keep only the newest ``keep`` runs, write the file atomically
   (write ``<name>.tmp`` next to it, then ``os.replace``) and return the new list.
3. ``baseline(history, metric="p95_ms", window=10)`` - look at the last ``window`` runs that have ``metric`` and return
   ``{"median": m, "mad": d, "n": n}`` where ``d`` is the median absolute deviation (the median of ``|x - m|``), or
   ``None`` when there are fewer than ``MIN_RUNS`` (3) such runs.
4. ``tolerance(base, floor=0.05, k=3.0)`` - the relative change that still counts as noise:
   ``max(floor, k * (mad / MAD_SCALE) / median)``. ``mad / 0.6745`` is the *scaled* MAD, which for normally distributed
   data is about the standard deviation (NIST Dataplot reference manual, "MEDIAN ABSOLUTE DEVIATION").
5. ``compare(base, value, floor=0.05, k=3.0)`` - ``change = (value - median) / median``; return
   ``{"change": round(change, 4), "tolerance": round(tolerance, 4), "status": s}`` with ``s`` ``"regression"`` when
   ``change > tolerance``, ``"improvement"`` when ``change < -tolerance`` and ``"within noise"`` otherwise (a change
   exactly equal to the tolerance is within noise). A baseline median that is not positive raises ``ValueError``.
"""

from __future__ import annotations

MIN_RUNS = 3
MAD_SCALE = 0.6745


def load_history(path):
    raise NotImplementedError("TODO: read the JSON list; [] when missing; ValueError when broken")


def save_run(path, run, keep=30):
    raise NotImplementedError("TODO: append, keep the newest runs, write atomically with os.replace")


def baseline(history, metric="p95_ms", window=10):
    raise NotImplementedError("TODO: median and MAD of the last runs, or None when there are too few")


def tolerance(base, floor=0.05, k=3.0):
    raise NotImplementedError("TODO: max(floor, k * scaled MAD / median)")


def compare(base, value, floor=0.05, k=3.0):
    raise NotImplementedError("TODO: relative change against the tolerance")
