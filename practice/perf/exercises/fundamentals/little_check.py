"""Check Little's law on measured requests.

An interval is (start, end) in seconds for one request, as a load generator records it. Over an observation
window [t0, t1]:

- L, the time-average number of requests in the system: the area under the "requests in system" curve over
  the window length - the sum of each request's time INSIDE the window (clip it), over t1 - t0;
- X, the throughput: requests that completed inside the window (t0 <= end <= t1), over t1 - t0;
- R, the mean residence time: the mean duration of the requests that completed inside the window.

Every function raises ValueError if t1 <= t0 or an interval ends before it starts.
Run: .venv/bin/python -m pytest tests/fundamentals/test_little_check.py
"""

from __future__ import annotations

Interval = tuple[float, float]


def time_average_in_system(intervals: list[Interval], t0: float, t1: float) -> float:
    raise NotImplementedError("time_average_in_system")


def throughput(intervals: list[Interval], t0: float, t1: float) -> float:
    raise NotImplementedError("throughput")


def mean_residence(intervals: list[Interval], t0: float, t1: float) -> float:
    """TODO: raise ValueError if no request completed inside the window."""
    raise NotImplementedError("mean_residence")


def littles_law_report(intervals: list[Interval], t0: float | None = None, t1: float | None = None) -> dict:
    """Return {"L", "X", "R", "XR", "relative_error"} where relative_error = |L - X*R| / L.
    TODO: without a window, use the whole run - from the first start to the last end. Raise ValueError if
    there are no intervals."""
    raise NotImplementedError("littles_law_report")
