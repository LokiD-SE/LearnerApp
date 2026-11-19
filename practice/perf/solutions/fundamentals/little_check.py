"""Check Little's law on measured requests (reference solution).

An interval is (start, end) in seconds for one request, as a load generator records it. Over an observation
window [t0, t1]:

- L, the time-average number of requests in the system, is the area under the "requests in system" curve
  divided by the window length - the sum of each request's time inside the window, over t1 - t0;
- X, the throughput, is the number of requests that completed inside the window over t1 - t0;
- R, the mean residence time, is the mean duration of the requests that completed inside the window.

When the window starts and ends with the system empty, L = X * R exactly (Lazowska et al. 1984, section 3.3:
"if the observation interval begins and ends at instants when system is empty, then this correspondence is
exact"). Cut the window through running requests and the "end effects" make them differ slightly.
"""

from __future__ import annotations

Interval = tuple[float, float]


def _check(intervals: list[Interval], t0: float, t1: float) -> None:
    if t1 <= t0:
        raise ValueError("the window must have a positive length")
    for start, end in intervals:
        if end < start:
            raise ValueError(f"interval ends before it starts: {(start, end)}")


def time_average_in_system(intervals: list[Interval], t0: float, t1: float) -> float:
    _check(intervals, t0, t1)
    area = sum(max(0.0, min(end, t1) - max(start, t0)) for start, end in intervals)
    return area / (t1 - t0)


def throughput(intervals: list[Interval], t0: float, t1: float) -> float:
    _check(intervals, t0, t1)
    return sum(1 for _, end in intervals if t0 <= end <= t1) / (t1 - t0)


def mean_residence(intervals: list[Interval], t0: float, t1: float) -> float:
    _check(intervals, t0, t1)
    done = [end - start for start, end in intervals if t0 <= end <= t1]
    if not done:
        raise ValueError("no request completed inside the window")
    return sum(done) / len(done)


def littles_law_report(intervals: list[Interval], t0: float | None = None, t1: float | None = None) -> dict:
    """L, X, R, X * R and the relative error |L - X*R| / L. Without a window, uses the whole run: from the first
    start to the last end, where the system is empty at both ends."""
    if not intervals:
        raise ValueError("no intervals")
    t0 = min(s for s, _ in intervals) if t0 is None else t0
    t1 = max(e for _, e in intervals) if t1 is None else t1
    big_l = time_average_in_system(intervals, t0, t1)
    x = throughput(intervals, t0, t1)
    r = mean_residence(intervals, t0, t1)
    return {"L": big_l, "X": x, "R": r, "XR": x * r, "relative_error": abs(big_l - x * r) / big_l}
