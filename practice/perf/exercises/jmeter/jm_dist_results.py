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
from collections import Counter
from pathlib import Path


def server_of(thread_name: str) -> str | None:
    """``"127.0.0.1:21092-Merchants 1-2"`` -> ``"127.0.0.1:21092"``; ``"Merchants 1-2"`` -> None.
    The prefix is ``host:port`` followed by ``-``; host names and IPv4 addresses both count."""
    raise NotImplementedError("TODO: server_of")


def samples_per_server(rows: list[dict[str, str]]) -> Counter:
    """How many samples each server sent, keyed by ``server_of(threadName)`` (None for rows with no prefix)."""
    raise NotImplementedError("TODO: samples_per_server")


def peak_threads(rows: list[dict[str, str]]) -> int:
    """The most threads that can have been active at once across the run: the sum, over servers, of each server's
    highest ``allThreads`` value (rows without a server prefix count as one 'server' of their own). It is an upper
    bound, because the servers do not start at the same instant."""
    raise NotImplementedError("TODO: peak_threads")


def merge_jtls(sources: dict[str, Path], out: Path) -> int:
    """Merge CSV JTLs from independent CLI runs into one file. ``sources`` maps a generator name (e.g.
    ``"gen-1"``) to its JTL. Every input must have the same header line, else ValueError. Each row's
    ``threadName`` gets the prefix ``"<name>-"`` (the same shape remote mode uses), rows are sorted by
    ``timeStamp`` as integers (stable for ties), and the header is written once. Returns the number of rows."""
    raise NotImplementedError("TODO: merge_jtls")
