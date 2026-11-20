"""Exercise - read the results of a distributed JMeter run, or merge the results of independent runs.

What a real run on 20 November 2026 showed (JMeter 5.6.3, two servers on 127.0.0.1):

- The controller writes ONE results file with every server's samples.
- Each sample's ``threadName`` is prefixed with the server that ran it: ``"127.0.0.1:21092-Merchants 1-2"`` is
  thread 2 of thread group 1 on the server at ``127.0.0.1:21092``. A local run has no prefix: ``"Merchants 1-2"``.
- ``grpThreads`` and ``allThreads`` are counted by each server for itself: with 2 servers x 2 threads every row
  said ``allThreads`` 2 at most - never 4. Adding up each server's peak gives the most threads that can have
  been active at once - an upper bound: the controller starts the servers one after another (in that short run
  the first server had finished before the second started), so check the timestamps before you call it the
  real concurrency.

The alternative the manual mentions ("remote mode does use more resources than running the same number of CLI
mode tests independently") is to start a plain CLI run on each machine at the same time and merge the result
files afterwards. Those files have no server prefix, so the merge must add one.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

_PREFIX = re.compile(r"^([A-Za-z0-9.\-]+:\d+)-")


def server_of(thread_name: str) -> str | None:
    """``"127.0.0.1:21092-Merchants 1-2"`` -> ``"127.0.0.1:21092"``; ``"Merchants 1-2"`` -> None.
    The prefix is ``host:port`` followed by ``-``; host names and IPv4 addresses both count."""
    match = _PREFIX.match(thread_name)
    return match.group(1) if match else None


def samples_per_server(rows: list[dict[str, str]]) -> Counter:
    """How many samples each server sent, keyed by ``server_of(threadName)`` (None for rows with no prefix)."""
    return Counter(server_of(r["threadName"]) for r in rows)


def peak_threads(rows: list[dict[str, str]]) -> int:
    """The most threads that can have been active at once across the run: the sum, over servers, of each server's
    highest ``allThreads`` value (rows without a server prefix count as one 'server' of their own). It is an upper
    bound, because the servers do not start at the same instant."""
    peaks: dict[str | None, int] = {}
    for r in rows:
        server = server_of(r["threadName"])
        peaks[server] = max(peaks.get(server, 0), int(r["allThreads"]))
    return sum(peaks.values())


def merge_jtls(sources: dict[str, Path], out: Path) -> int:
    """Merge CSV JTLs from independent CLI runs into one file. ``sources`` maps a generator name (e.g.
    ``"gen-1"``) to its JTL. Every input must have the same header line, else ValueError. Each row's
    ``threadName`` gets the prefix ``"<name>-"`` (the same shape remote mode uses), rows are sorted by
    ``timeStamp`` as integers (stable for ties), and the header is written once. Returns the number of rows."""
    header: list[str] | None = None
    merged: list[dict[str, str]] = []
    for name, path in sources.items():
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            if header is None:
                header = list(reader.fieldnames or [])
            elif list(reader.fieldnames or []) != header:
                raise ValueError(f"{path} has a different header - save every run with the same settings")
            for row in reader:
                row["threadName"] = f"{name}-{row['threadName']}"
                merged.append(row)
    if header is None:
        raise ValueError("no results files given")
    merged.sort(key=lambda r: int(r["timeStamp"]))
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(merged)
    return len(merged)
