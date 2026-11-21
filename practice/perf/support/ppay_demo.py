"""Prints every number the lesson "Performance testing payment systems" shows (run on 21 November 2026).

    PERF_TARGET=solutions .venv/bin/python support/ppay_demo.py

Locust 2.47.0 and the loopback practice API; timings change with the machine, the structure does not.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "solutions" / "analysis")]
os.environ.setdefault("PERF_TARGET", "solutions")

import ppay_fixture as F  # noqa: E402
import ppay_reconcile as rc  # noqa: E402
import ppay_triage as tr  # noqa: E402
from load_tools import read_locust_stats, run_locust  # noqa: E402
from sandpay_target import TargetConfig, serve  # noqa: E402


def locust(locustfile, url, users, run_time, env=None):
    saved = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update({k: str(v) for k, v in (env or {}).items()})
    try:
        with tempfile.TemporaryDirectory() as d:
            return read_locust_stats(run_locust(HERE / locustfile, url, users, users, run_time, Path(d)))
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def line(name, e):
    secs = sorted(e["num_reqs_per_sec"])[1:-1] or sorted(e["num_reqs_per_sec"])  # drop the ragged first and last second
    steady = statistics.median(e["num_reqs_per_sec"][s] for s in secs)
    mean = e["total_response_time"] / e["num_requests"]
    return (f"{name:<26} requests {e['num_requests']:>5}  failures {e['num_failures']:>3}  "
            f"mean {mean:6.1f} ms  steady {steady:5.0f} req/s")


print("== 1. one fixed key per user, then a fresh key per payment (20 users, 4 s, 20 ms service time) ==")
for label, lf in (("fixed key", "ppay_naive_locustfile.py"), ("fresh key", "ppay_fresh_locustfile.py")):
    with serve(TargetConfig(latency_ms=20, capacity=8)) as url:
        stats = locust(lf, url, 20, "4s")
        m = F.metrics(url)
    print(line(label, stats["POST /v1/payments"]))
    print(f"   API counters: payments_created {m['payments_created']}  idempotent_replays {m['idempotent_replays']}  "
          f"replay share {rc.replay_share(m):.1%}  statuses {m['statuses']}")

print("\n== 2. triage of 40 sequential payments ==")
for mode in ("fixed", "fresh"):
    with serve(TargetConfig(latency_ms=1)) as url:
        rows = tr.summarise(F.probe_rows(url, F.token(url), 40, mode))
    print(f"{mode:<6} {({k: v for k, v in rows.items() if v})}  ->  {tr.verdict(rows)}")

print("\n== 3. a login per iteration from one client, against a limit of 5 per second ==")
with serve(TargetConfig(latency_ms=1, rate_limit_rps=5)) as url:
    one = []
    for _ in range(20):
        s, h, _ = F.call(url, "POST", "/auth/token", {"client_id": "merchant-1", "client_secret": "secret-1"})
        one.append({"status": s, "headers": h})
    many = []
    for n in range(21, 41):
        s, h, _ = F.call(url, "POST", "/auth/token", {"client_id": f"merchant-{n}", "client_secret": f"secret-{n}"})
        many.append({"status": s, "headers": h})
    print("20 logins as merchant-1      :", {k: v for k, v in tr.summarise(one).items() if v}, "retry-after:",
          next(r["headers"].get("Retry-After") for r in one if r["status"] == 429))
    print("1 login each, 20 other merchants:", {k: v for k, v in tr.summarise(many).items() if v})
    print("verdict, one client          :", tr.verdict(tr.summarise(one)))

print("\n== 4. the first request times out on the client; the retry comes at once or later ==")
print("(first request: client gives up after 40 ms, the API needs 200 ms to carry it out)")
for wait_s, same in ((0.0, True), (0.3, True), (0.0, False), (0.3, False)):
    ledger, m = F.timeout_scenario(wait_s, same)
    r = rc.reconcile(ledger, m)
    a = ledger[0]["attempts"]
    print(f"retry after {wait_s:.1f} s, {'same key' if same else 'new key '}: attempts "
          f"{[(x['status'], x['replayed']) for x in a]}  created {m['payments_created']} replays "
          f"{m['idempotent_replays']}  bounds {r['bounds']}  verdict {r['verdict']}")

print("\n== 5. the retry rules in a real Locust run (6 users, 5 s, capacity 2, queue 2, 20 % injected 500s) ==")
from collections import Counter  # noqa: E402

with serve(TargetConfig(latency_ms=20, capacity=2, queue_limit=2, error_rate=0.2)) as url, \
        tempfile.TemporaryDirectory() as out:
    ledger, stats = F.run_pay_locust(url, Path(out), users=6, run_time="5s")
    m = F.metrics(url)
s = rc.summarise(ledger)
print("Locust:", line("POST /v1/payments", stats["POST /v1/payments"]))
print("ledger:", s)
print("attempts per logical payment:", dict(sorted(Counter(len(r["attempts"]) for r in ledger).items())))
print("outcomes:", dict(Counter(r["outcome"] for r in ledger)))
print("API   :", {k: m[k] for k in ("payments_created", "idempotent_replays")}, "statuses", m["statuses"])
print("reconcile (6 users may have been mid-request at the stop):", rc.reconcile(ledger, m, in_flight=6))
print("reconcile with in_flight=0:", rc.reconcile(ledger, m)["verdict"])

print("\n== 6. the same API with and without a share of settlement reports (16 users, no think time, 5 s) ==")
print("model: capacity 4, payment 40 ms, report 200 ms -> ceiling = capacity / mean service time")
for weight in (0, 1):
    with serve(TargetConfig(latency_ms=20, capacity=4)) as url:
        stats = locust("ppay_mix_locustfile.py", url, 16, "5s", {"PPAY_REPORT_WEIGHT": weight})
    mean_ms = (19 * 40 + weight * 200) / (19 + weight)
    print(f"report weight {weight}: model ceiling {4 / (mean_ms / 1000):5.1f} req/s (mean service {mean_ms:.0f} ms)")
    for name in ("POST /v1/payments", "GET /v1/reports/settlement"):
        if name in stats:
            print("  " + line(name, stats[name]))
