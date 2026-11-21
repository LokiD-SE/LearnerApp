"""Fixtures for the Locust load shapes lesson (tests/locust/test_lc_shape_*.py).

- ``load_exercise(relative)`` imports a Python exercise module from its file (the topic folder is called
  ``locust``, like the Locust package, so ``from locust.x import ...`` would find the real package).
- ``HISTORY_SPIKE`` and ``HISTORY_SLOW_RAMP`` are the ``<prefix>_stats_history.csv`` rows (one per second) of two
  real Locust 2.47.0 runs against the practice API, captured on 21 November 2026 with ``latency_ms=20`` and
  ``capacity=4``. Only the three columns the exercise reads are kept, as the strings Locust wrote.
  - the spike run: stages (3 s, 2 users), (7 s, 20 users), (11 s, 2 users);
  - the slow-ramp run: stages (3 s, 10 users at 1 user/s), (6 s, 4 users), (9 s, 2 users). The first stage
    wants 10 users but is replaced after 3 seconds - the count peaks at 4.
- ``read_history(path)`` reads a real ``_stats_history.csv`` into the same row shape.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from types import ModuleType

from load_tools import practice_file

COLUMNS = ("Timestamp", "User Count", "Total Request Count")


def load_exercise(relative: str) -> ModuleType:
    path = practice_file(relative)
    spec = importlib.util.spec_from_file_location(Path(relative).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(pairs: list[tuple[int, int]], first_timestamp: int) -> list[dict[str, str]]:
    return [{"Timestamp": str(first_timestamp + i), "User Count": str(users), "Total Request Count": str(total)}
            for i, (users, total) in enumerate(pairs)]


HISTORY_SPIKE = _rows(
    [(0, 0), (2, 28), (2, 54), (2, 80), (20, 266), (20, 462), (20, 657), (20, 850), (2, 877), (2, 903), (2, 931),
     (2, 957)], 1795234052)

HISTORY_SLOW_RAMP = _rows(
    [(0, 0), (1, 14), (2, 41), (3, 82), (4, 137), (4, 190), (4, 243), (2, 269), (2, 295), (2, 321)], 1795234064)


def read_history(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        return [{c: row[c] for c in COLUMNS} for row in csv.DictReader(f)]
