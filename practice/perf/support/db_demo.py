"""Prints every measurement shown in the backend-and-database-performance lesson.

Run from practice/perf:  .venv/bin/python support/db_demo.py [n_plus_one|plans|pool|cache|all]
Timings depend on the machine; query counts, plan text and hit ratios do not.
"""

from __future__ import annotations

import random
import sys
import time
from collections import OrderedDict

from db_fixture import ConnectionPool, CountingConn, build_db, percentile, run_closed_clients


def n_plus_one() -> None:
    conn = build_db()
    for label, fn in (("N+1", latest_n_plus_one), ("JOIN", latest_join)):
        counted = CountingConn(conn, round_trip_ms=1.0)
        started = time.perf_counter()
        rows = fn(counted, 100)
        elapsed = (time.perf_counter() - started) * 1000
        print(f"{label:5} rows={len(rows)} queries={counted.count:3} time={elapsed:6.1f} ms (1 ms simulated per query)")
    print(f"same rows: {latest_n_plus_one(CountingConn(conn), 100) == latest_join(CountingConn(conn), 100)}")
    counted = CountingConn(conn)
    latest_n_plus_one(counted, 3)
    for sql in counted.queries:
        print("  ", sql)


def latest_n_plus_one(conn, limit):
    payments = conn.execute(
        "SELECT id, merchant_id, amount_cents FROM payments ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    rows = []
    for pid, merchant_id, amount in payments:
        name = conn.execute("SELECT name FROM merchants WHERE id = ?", (merchant_id,)).fetchone()[0]
        rows.append((pid, name, amount))
    return rows


def latest_join(conn, limit):
    return conn.execute(
        "SELECT p.id, m.name, p.amount_cents FROM payments p JOIN merchants m ON m.id = p.merchant_id "
        "ORDER BY p.id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def plans() -> None:
    conn = build_db(merchants=2000, payments=200_000)
    query = "SELECT id, amount_cents FROM payments WHERE merchant_id = ?"
    print("rows in payments:", conn.execute("SELECT count(*) FROM payments").fetchone()[0])

    def plan(sql, params=()):
        return [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params)]

    def time_it(sql, runs=200):
        started = time.perf_counter()
        for n in range(runs):
            conn.execute(sql, (1 + n % 2000,)).fetchall()
        return (time.perf_counter() - started) / runs * 1000

    print("plan without index:", plan(query, (7,)))
    print(f"mean per query without index: {time_it(query):.3f} ms")
    conn.execute("CREATE INDEX idx_payments_merchant ON payments (merchant_id)")
    print("plan with index:   ", plan(query, (7,)))
    print(f"mean per query with index:    {time_it(query):.3f} ms")

    range_query = "SELECT id FROM payments WHERE merchant_id = ? AND created_day >= ?"
    conn.execute("DROP INDEX idx_payments_merchant")
    conn.execute("CREATE INDEX idx_a ON payments (created_day, merchant_id)")
    print("range query, index (created_day, merchant_id):", plan(range_query, (7, 300)))
    conn.execute("DROP INDEX idx_a")
    conn.execute("CREATE INDEX idx_b ON payments (merchant_id, created_day)")
    print("range query, index (merchant_id, created_day):", plan(range_query, (7, 300)))
    covering = "SELECT merchant_id, created_day FROM payments WHERE merchant_id = ?"
    print("covering query:", plan(covering, (7,)))
    print("function on the column:", plan("SELECT id FROM payments WHERE merchant_id + 0 = ?", (7,)))
    print("cast on the column:", plan("SELECT id FROM payments WHERE CAST(merchant_id AS TEXT) = ?", ("7",)))

    # the price of an index: writes
    for label, indexes in (("no index", []), ("1 index", ["merchant_id"]), ("3 indexes", ["merchant_id", "created_day", "status"])):
        c = build_db(payments=10)
        for col in indexes:
            c.execute(f"CREATE INDEX idx_{col} ON payments ({col})")
        rng = random.Random(1)
        rows = [(1000 + n, rng.randint(1, 50), 500, "EUR", "captured", rng.randint(1, 365)) for n in range(100_000)]
        started = time.perf_counter()
        c.executemany("INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)", rows)
        c.commit()
        print(f"insert 100000 rows, {label:9}: {(time.perf_counter() - started) * 1000:7.0f} ms")


def pool() -> None:
    clients, hold_ms = 32, 20.0
    print(f"{clients} clients, each holds a connection {hold_ms:.0f} ms per request, no think time, 1.5 s per row")
    print("pool  served  req/s  wait mean ms  wait p95 ms  total p95 ms  upper bound req/s")
    for size in (1, 2, 4, 8, 16, 32, 64):
        r = run_closed_clients(ConnectionPool(size), clients, hold_ms, 1.5)
        bound = min(size, clients) / (hold_ms / 1000)
        print(
            f"{size:4}  {r.served:6}  {r.throughput:5.0f}  {sum(r.waits) / len(r.waits) * 1000:12.1f}  "
            f"{percentile(r.waits, 95) * 1000:11.1f}  {percentile(r.totals, 95) * 1000:12.1f}  {bound:12.0f}"
        )
    r = run_closed_clients(ConnectionPool(4), 40, hold_ms, 1.5, acquire_timeout=0.1)
    print(
        f"pool 4, 40 clients, acquire timeout 100 ms: served={r.served} timeouts={r.timeouts} "
        f"({r.timeouts / (r.served + r.timeouts):.0%} of requests)"
    )


def lru_hit_ratio(keys, capacity):
    cache: OrderedDict = OrderedDict()
    hits = 0
    for key in keys:
        if key in cache:
            hits += 1
            cache.move_to_end(key)
        else:
            cache[key] = True
            if len(cache) > capacity:
                cache.popitem(last=False)
    return hits / len(keys)


def cache() -> None:
    rng = random.Random(11)
    ids = list(range(1, 1001))
    weights = [1 / rank for rank in range(1, 1001)]  # a few merchants get most of the traffic
    keys = rng.choices(ids, weights=weights, k=50_000)
    uniform = [rng.choice(ids) for _ in range(50_000)]
    print("capacity  hit ratio (skewed)  hit ratio (uniform)")
    for cap in (10, 50, 100, 250, 1000):
        print(f"{cap:8}  {lru_hit_ratio(keys, cap):18.1%}  {lru_hit_ratio(uniform, cap):19.1%}")
    # what the hit ratio does to the load on the database (arithmetic on the measured ratio)
    ratio = lru_hit_ratio(keys, 100)
    print(f"100 entries: {ratio:.1%} hits, so the database sees {1 - ratio:.1%} of the lookups: 1000 requests/s -> {1000 * (1 - ratio):.0f} queries/s")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("n_plus_one", n_plus_one), ("plans", plans), ("pool", pool), ("cache", cache)):
        if which in (name, "all"):
            print(f"--- {name}")
            fn()
