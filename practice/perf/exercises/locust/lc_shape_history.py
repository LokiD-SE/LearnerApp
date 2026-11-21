"""Reading a Locust ``_stats_history.csv`` by phase (no Locust import).

``--csv <prefix>`` makes Locust append one row per second to ``<prefix>_stats_history.csv``. A row has
``"User Count"`` (the users running at that moment) and ``"Total Request Count"`` (every request so far, a running
total), both as strings. The ``"Requests/s"`` and percentile columns are windowed over about the last 10 seconds,
so for a short phase the difference of the running total is the honest rate. ``rows`` below is a list of dicts
with those columns, as ``csv.DictReader`` gives them.

1. ``phases(rows)`` - group *consecutive* rows with the same user count into phases and return, in order, dicts
   ``{"users": int, "seconds": int, "requests": int, "rps": float}``: ``seconds`` is the number of rows, ``requests``
   the growth of the running total over those rows (the first row grows from 0, every later row from the row
   before it), ``rps`` is ``requests / seconds`` rounded to 1 decimal.
2. ``peak_users(rows)`` - the highest user count seen (0 for no rows).
3. ``missed_targets(rows, targets)`` - the targets that were never the user count in any row, sorted. A stage
   whose target never shows up was replaced before its ramp finished.
"""

from __future__ import annotations


def phases(rows: list[dict[str, str]]) -> list[dict]:
    raise NotImplementedError("TODO: group consecutive rows with the same user count")


def peak_users(rows: list[dict[str, str]]) -> int:
    raise NotImplementedError("TODO: the highest user count")


def missed_targets(rows: list[dict[str, str]], targets: list[int]) -> list[int]:
    raise NotImplementedError("TODO: the targets that never appear as a user count")
