"""Ramp-up: when should each JMeter thread start, and did it?

The JMeter Component Reference (Thread Group, "Ramp-up Period"): "If there are 10 threads and a ramp-up time of
100 seconds, then each thread will begin 10 seconds after the previous thread started ... The first thread will
always start directly ... the tenth thread in the above example will actually be started after 90 seconds and
not 100 seconds."

A JTL (CSV) row has ``timeStamp`` (epoch milliseconds, the sample's start by default) and ``threadName``, which
for a normal Thread Group is ``"<group name> <group number>-<thread number>"``, e.g. ``"Merchants 1-3"``. The first
sample of each thread starts as soon as the thread does (when no timer delays it), so the first ``timeStamp`` per
thread is a good measure of the thread's start - once the JVM is warm. The very first HTTP request of a run pays
for class loading and the first connection, so a setUp Thread Group that sends one warm-up request keeps that
cost out of the measured group (filter the rows by ``group``).
"""

from __future__ import annotations

import re

_THREAD_NUMBER = re.compile(r"\s(\d+)-(\d+)$")


def start_offsets(threads: int, ramp_up_s: float) -> list[float]:
    """Seconds after the test start at which each thread starts: thread ``i`` (0-based) at ``i * ramp_up / threads``.

    >>> start_offsets(10, 100)[-1]
    90.0
    """
    if threads < 1:
        raise ValueError("threads must be at least 1")
    if ramp_up_s < 0:
        raise ValueError("ramp-up cannot be negative")
    step = ramp_up_s / threads
    return [round(i * step, 6) for i in range(threads)]


def thread_number(thread_name: str) -> int:
    """The 1-based thread number from a JTL ``threadName`` such as ``"Merchants 1-3"`` (-> 3)."""
    m = _THREAD_NUMBER.search(thread_name)
    if not m:
        raise ValueError(f"not a Thread Group thread name: {thread_name!r}")
    return int(m.group(2))


def observed_offsets(rows: list[dict[str, str]], group: str | None = None) -> dict[int, int]:
    """Milliseconds from the earliest sample to each thread's first sample, keyed by thread number.

    With ``group``, only rows whose ``threadName`` starts with ``"<group> "`` count (e.g. ``"Merchants"``), so
    samples from a setUp Thread Group or another group don't shift the origin."""
    if group is not None:
        rows = [r for r in rows if r["threadName"].startswith(group + " ")]
    if not rows:
        raise ValueError("no samples")
    first: dict[int, int] = {}
    for row in rows:
        n = thread_number(row["threadName"])
        ts = int(row["timeStamp"])
        if n not in first or ts < first[n]:
            first[n] = ts
    origin = min(first.values())
    return {n: first[n] - origin for n in sorted(first)}


def check_ramp(rows: list[dict[str, str]], threads: int, ramp_up_s: float, tolerance_ms: int = 100,
               group: str | None = None) -> list[str]:
    """Problems with a run's ramp-up, compared with the expected schedule; an empty list means it matched."""
    expected = start_offsets(threads, ramp_up_s)
    observed = observed_offsets(rows, group)
    problems: list[str] = []
    if sorted(observed) != list(range(1, threads + 1)):
        problems.append(f"expected threads 1..{threads}, saw {sorted(observed)}")
    for n, offset_ms in observed.items():
        if 1 <= n <= threads:
            want_ms = round(expected[n - 1] * 1000)
            if abs(offset_ms - want_ms) > tolerance_ms:
                problems.append(f"thread {n} started at +{offset_ms} ms, expected +{want_ms} ms")
    return problems
