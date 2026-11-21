"""Fixture for the backend-and-database-performance lesson (prefix ``db_``): a small SQLite SandPay database,
a connection wrapper that counts queries, and a bounded connection pool. Everything is in-process and
synthetic; nothing leaves the machine.

SQLite stands in for a real database server: it is in the Python standard library, so the lesson runs
anywhere. What carries over to PostgreSQL or MySQL is the *shape* of the problems (queries per request, scans
versus index searches, a bounded pool with a queue in front of it); the absolute times and the exact plan text
do not.

- ``build_db(...)``: an in-memory database with ``merchants`` (``merchant-1`` ..) and ``payments`` (seeded, so
  every run builds the same rows). ``with_index=True`` adds ``idx_payments_merchant`` on ``payments(merchant_id)``.
- ``CountingConn``: wraps a connection; ``execute`` records the SQL text. ``round_trip_ms`` sleeps once per
  query to *simulate* the network round trip to a database server (an in-process SQLite call costs microseconds,
  a call to a server on another machine costs a network round trip each time).
- ``ConnectionPool``: ``acquire(timeout)`` / ``release(conn)`` over a bounded pool with a FIFO wait queue; a request that
  waits longer than ``timeout`` gets ``PoolTimeout``. ``run_closed_clients`` drives it with threads.
"""

from __future__ import annotations

import random
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field

CURRENCIES = ("EUR", "GBP", "USD")
STATUSES = ("captured", "captured", "captured", "refunded", "failed")
COUNTRIES = ("DE", "FR", "GB", "NL", "ES", "IT")

SCHEMA = """
CREATE TABLE merchants (id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL);
CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    merchant_id INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    created_day INTEGER NOT NULL
);
"""


def build_db(merchants: int = 50, payments: int = 20_000, seed: int = 7, with_index: bool = False) -> sqlite3.Connection:
    """An in-memory SandPay database; the same ``seed`` always gives the same rows."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.executescript(SCHEMA)
    rng = random.Random(seed)
    conn.executemany(
        "INSERT INTO merchants (id, name, country) VALUES (?, ?, ?)",
        [(n, f"merchant-{n}", rng.choice(COUNTRIES)) for n in range(1, merchants + 1)],
    )
    conn.executemany(
        "INSERT INTO payments (id, merchant_id, amount_cents, currency, status, created_day) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                n,
                rng.randint(1, merchants),
                rng.randint(100, 50_000),
                rng.choice(CURRENCIES),
                rng.choice(STATUSES),
                rng.randint(1, 365),
            )
            for n in range(1, payments + 1)
        ],
    )
    if with_index:
        conn.execute("CREATE INDEX idx_payments_merchant ON payments (merchant_id)")
    conn.commit()
    return conn


class CountingConn:
    """Counts the queries a piece of code sends. Only ``execute`` is offered, on purpose: one call, one round trip."""

    def __init__(self, conn: sqlite3.Connection, round_trip_ms: float = 0.0) -> None:
        self._conn = conn
        self._round_trip = round_trip_ms / 1000.0
        self.queries: list[str] = []

    def execute(self, sql: str, params=()):
        self.queries.append(sql)
        if self._round_trip:
            time.sleep(self._round_trip)
        return self._conn.execute(sql, params)

    @property
    def count(self) -> int:
        return len(self.queries)


class PoolTimeout(Exception):
    """No connection became free within the acquire timeout."""


class ConnectionPool:
    """A bounded pool: ``size`` connections and a FIFO queue of waiting requests in front of it.

    A released connection is handed straight to the longest-waiting request, so nobody can jump the queue
    (a plain ``queue.Queue`` lets the releasing thread grab the connection again before a waiter wakes up,
    which starves some clients and makes the tail look worse than a fair pool would).
    """

    def __init__(self, size: int) -> None:
        self.size = size
        self._lock = threading.Lock()
        self._free = size
        self._waiting: deque[threading.Event] = deque()

    def acquire(self, timeout: float | None = None) -> int:
        with self._lock:
            if self._free > 0 and not self._waiting:
                self._free -= 1
                return 0
            ticket = threading.Event()
            self._waiting.append(ticket)
        if ticket.wait(timeout):
            return 0
        with self._lock:
            if ticket.is_set():  # handed a connection just as the wait timed out
                return 0
            self._waiting.remove(ticket)
        raise PoolTimeout(f"no connection free within {timeout} s")

    def release(self, conn: int = 0) -> None:
        with self._lock:
            if self._waiting:
                self._waiting.popleft().set()
            else:
                self._free += 1


@dataclass
class ClientResult:
    served: int = 0
    timeouts: int = 0
    waits: list[float] = field(default_factory=list)  # seconds spent waiting for a connection
    totals: list[float] = field(default_factory=list)  # wait + hold, per served request
    elapsed: float = 0.0

    @property
    def throughput(self) -> float:
        return self.served / self.elapsed if self.elapsed else 0.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(pct / 100.0 * len(ordered)))]


def run_closed_clients(
    pool: ConnectionPool, clients: int, hold_ms: float, seconds: float, acquire_timeout: float | None = None
) -> ClientResult:
    """``clients`` threads, each in a loop: acquire a connection, hold it ``hold_ms`` (a query), release it.

    A closed model with no think time: every client sends its next request as soon as the last one is done.
    """
    result = ClientResult()
    lock = threading.Lock()
    stop_at = time.perf_counter() + seconds

    def client() -> None:
        while time.perf_counter() < stop_at:
            started = time.perf_counter()
            try:
                conn = pool.acquire(timeout=acquire_timeout)
            except PoolTimeout:
                with lock:
                    result.timeouts += 1
                continue
            waited = time.perf_counter() - started
            try:
                time.sleep(hold_ms / 1000.0)
            finally:
                pool.release(conn)
            with lock:
                result.served += 1
                result.waits.append(waited)
                result.totals.append(time.perf_counter() - started)

    begin = time.perf_counter()
    threads = [threading.Thread(target=client) for _ in range(clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    result.elapsed = time.perf_counter() - begin
    return result
