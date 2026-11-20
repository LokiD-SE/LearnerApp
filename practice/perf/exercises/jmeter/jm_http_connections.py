"""How did JMeter use connections? Read it from the server's side - EXERCISE.

The practice server in ``support/jm_http_fixture.py`` records, for every request, the client end of the TCP
connection that carried it (``Hit.connection``, e.g. "127.0.0.1:54012") and the request headers. From that log:

- ``requests_per_connection(log)`` - how many requests each connection carried.
- ``connection_header_values(log)`` - how often each ``Connection`` request header value was sent
  (lower-case; a request without the header counts as "(none)").
- ``reuse_pattern(log, threads, loops)`` - which reuse pattern the run shows:
  "per-request"   every request opened its own connection;
  "per-iteration" each thread opened one connection per iteration (threads * loops connections);
  "per-thread"    each thread kept one connection for the whole run (threads connections);
  "mixed"         anything else (a closed connection mid-iteration, a retry, ...).
  When several patterns fit (one thread and one loop), the first in that order wins.

Run: .venv/bin/python -m pytest tests/jmeter/test_jm_http_connections.py
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Protocol


class HitLike(Protocol):
    connection: str
    headers: dict[str, str]


def requests_per_connection(log: Iterable[HitLike]) -> Counter[str]:
    # TODO: count requests by hit.connection
    raise NotImplementedError("requests_per_connection")


def connection_header_values(log: Iterable[HitLike]) -> Counter[str]:
    # TODO: header names are case-insensitive; lower-case the value; "(none)" when the header is missing
    raise NotImplementedError("connection_header_values")


def reuse_pattern(log: Iterable[HitLike], threads: int, loops: int) -> str:
    # TODO: compare the number of distinct connections with len(log), threads * loops and threads - in that
    # order - and raise ValueError for an empty log.
    raise NotImplementedError("reuse_pattern")
