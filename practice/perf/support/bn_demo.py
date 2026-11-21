"""Prints every number the bottleneck analysis lesson shows (run from practice/perf):

    PERF_TARGET=solutions .venv/bin/python support/bn_demo.py

It uses the reference solutions of the three exercises and the fixture in support/bn_fixture.py. The target runs in
its own process on loopback; all data is synthetic.
"""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "solutions" / "analysis"), str(ROOT / "support")]

from bn_fixture import Sampler, get_metrics, run_level, run_steps, serve_separately  # noqa: E402
from bn_knee import find_knee, implied_slots, wait_share  # noqa: E402
from bn_laws import bottleneck, demand, max_throughput, what_if  # noqa: E402
from bn_use import limiting, saturation, use_findings, utilization  # noqa: E402
from load_tools import read_locust_stats, run_locust  # noqa: E402

SERVICE_MS, CAPACITY = 20, 4


def use_row(url, clients, requests_each=20, **kw):
    with Sampler(url) as sampler:
        result = run_level(url, clients, requests_each, **kw)
    u, s = utilization(sampler.samples, CAPACITY), saturation(sampler.samples)
    return result, u, s, use_findings(u, s, result["errors"])


def main() -> None:
    print("== 1. step load: closed loop, no think time, 20 requests per client")
    with serve_separately(latency_ms=SERVICE_MS, capacity=CAPACITY) as url:
        steps = run_steps(url, [1, 2, 4, 8, 16], requests_each=20)
        print(f"{'clients':>7} {'req/s':>7} {'mean ms':>8} {'p95 ms':>7} {'wait share':>11}")
        for s in steps:
            print(f"{s['clients']:>7} {s['throughput']:>7} {s['mean_ms']:>8} {s['p95_ms']:>7} {wait_share(s, SERVICE_MS):>11}")
        print("knee:", find_knee(steps), "| slots implied by the ceiling:", implied_slots(steps, SERVICE_MS))
        m = get_metrics(url)
        print("target /metrics after the run:", {k: m[k] for k in ("in_flight", "max_in_flight", "waiting")})

        print("\n== 2. USE of the worker pool, sampled from /metrics every 50 ms during each level")
        print(f"{'clients':>7} {'util':>6} {'queue':>6} {'errors':>6}  findings")
        for clients in (2, 4, 8, 16):
            r, u, s, f = use_row(url, clients)
            print(f"{clients:>7} {u:>6} {s:>6} {r['errors']:>6}  {f}")

        print("\n== 3. the same 16 clients, but each burns 30 ms of CPU between requests")
        r, u, s, f = use_row(url, 16, requests_each=6, burn_ms=30)
        print(f"throughput {r['throughput']} req/s, mean {r['mean_ms']} ms | target util {u}, queue {s}, errors {r['errors']} -> {f}")

    print("\n== 4. a bounded queue: queue_limit=4, 24 clients")
    with serve_separately(latency_ms=SERVICE_MS, capacity=CAPACITY, queue_limit=4) as url:
        r, u, s, f = use_row(url, 24, requests_each=15)
        print(f"statuses {r['statuses']} | mean {r['mean_ms']} ms, p95 {r['p95_ms']} ms | util {u}, queue {s} -> {f}")

    print("\n== 5. operational laws on the measured ceiling")
    top = max(steps, key=lambda s: s["throughput"])
    d = demand(1.0, top["throughput"])
    print(f"D = U / X = 1.0 / {top['throughput']} = {d * 1000:.2f} ms per request (20 ms / 4 workers = 5 ms)")
    print(f"ceiling 1 / D = {max_throughput({'pool': d}):.0f} req/s")

    print("\n== 6. a hypothetical path (made-up demands in seconds)")
    path = {"web": 0.004, "app": 0.012, "db": 0.025}
    print("bottleneck:", bottleneck(path), "| ceiling:", round(max_throughput(path), 1), "req/s")
    for name, factor in (("web", 0.5), ("db", 0.4), ("app", 0.5)):
        b, x = what_if(path, name, factor)
        print(f"  demand of {name} x {factor}: bottleneck {b}, ceiling {x:.1f} req/s")
    print("limiting():", limiting({
        "web workers": {"utilization": 0.35, "saturation": 0, "errors": 0},
        "app threads": {"utilization": 0.82, "saturation": 0, "errors": 0},
        "db connections": {"utilization": 1.0, "saturation": 11.5, "errors": 0}}))

    print("\n== 7. the same two loads in Locust 2.47.0 (6 s each)")
    with serve_separately(latency_ms=SERVICE_MS, capacity=CAPACITY) as url, tempfile.TemporaryDirectory() as tmp:
        print(f"{'users':>5} {'requests':>8} {'req/s':>7} {'avg ms':>7} {'p95 ms':>7} {'failures':>8}")
        for users in (2, 16):
            prefix = run_locust(ROOT / "support" / "bn_locustfile.py", url, users, 16, "6s", Path(tmp) / f"u{users}")
            row = read_locust_stats(prefix)["/v1/payments"]
            n = row["num_requests"]
            span = row["last_request_timestamp"] - row["start_time"]
            seen, p95 = 0, 0
            for ms, count in sorted((int(k), v) for k, v in row["response_times"].items()):
                seen += count
                if seen >= 0.95 * n:
                    p95 = ms
                    break
            print(f"{users:>5} {n:>8} {(n - users) / span:>7.1f} {row['total_response_time'] / n:>7.1f} {p95:>7} {row['num_failures']:>8}")


if __name__ == "__main__":
    main()
