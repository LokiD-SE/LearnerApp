"""Prints every number the lesson "JMeter, Locust and other tools compared" shows, from the captured runs.

    cd practice/perf && PERF_TARGET=solutions .venv/bin/python support/tc_demo.py

Reads ``tc_data/`` (captured by ``tc_capture.py`` on 21 November 2026) and the reference solutions; it starts no tool.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "solutions" / "analysis"))
sys.path.insert(0, str(HERE))

import tc_fixture as fx  # noqa: E402
import tc_sizing as sz  # noqa: E402
import tc_summary as sm  # noqa: E402

SETUPS = ["jmeter-default", "jmeter-512m", "locust-http", "locust-fast"]


def typical(runs, key):
    """The run whose ``key`` is the median of the repeats (three repeats: the middle one)."""
    ordered = sorted(runs, key=lambda r: key(r) if callable(key) else r[key])
    return ordered[len(ordered) // 2]


def by(scenario, setup):
    return [r for r in fx.captured()["runs"] if r["scenario"] == scenario and r["setup"] == setup]


def main():
    data = fx.captured()
    print(f"captured {data['captured']} on {data['machine']['cpus']} CPUs, Python {data['machine']['python']}")
    jmx, py = fx.PLAN.read_text(), fx.LOCUSTFILE.read_text()
    print(f"script size: tc_checkout.jmx {len(jmx.splitlines())} lines, {len(jmx)} bytes; "
          f"tc_checkout_locustfile.py {len(py.splitlines())} lines, {len(py)} bytes")

    print("\n== the same scenario in both tools (steady: 10 users, 200 ms think, 10 s)")
    j, l = sm.summarise_jtl(fx.jtl_rows()), sm.summarise_locust(fx.locust_entries())
    print(f"{'request':24}{'JMeter n':>9}{'p50':>5}{'p95':>5}{'Locust n':>10}{'p50':>5}{'p95':>5}")
    for label in j["labels"]:
        a, b = j["labels"][label], l["labels"][label]
        print(f"{label:24}{a['requests']:>9}{a['p50']:>5}{a['p95']:>5}{b['requests']:>10}{b['p50']:>5}{b['p95']:>5}")
    print(f"{'total':24}{j['requests']:>9}{'':>10}{l['requests']:>10}   rps {j['rps']} vs {l['rps']}")
    print("same_scenario:", sm.same_scenario(j, l) or "no differences", "| mix JMeter", sm.mix(j))
    broken = {k: v for k, v in fx.locust_entries().items() if k != "POST /auth/token"}
    print("without the sign-in:", sm.same_scenario(j, sm.summarise_locust(broken)))

    print("\n== two percentile rules on the same ten requests (10 ms x5, 20 ms x3, 150 ms x2)")
    times = [10] * 5 + [20] * 3 + [150] * 2
    hist = {10: 5, 20: 3, 150: 2}
    for f in (0.5, 0.95):
        print(f"p{int(f * 100)}: nearest rank {sm.percentile(times, f)}, Locust rule {sm.locust_percentile(hist, 10, f)}")
    print("bucket:", [(v, sm.bucket(v)) for v in (7, 99.6, 147, 999, 3432, 58760)])

    print("\n== what each tool cost (median of three runs; CPU seconds are user + system, all threads)")
    print(f"{'scenario':9}{'setup':16}{'wall s':>7}{'CPU s':>7}{'cores':>6}{'peak MB':>8}{'requests':>9}{'CPU s/1000':>11}")
    for sc in ("startup", "steady", "many"):
        for su in SETUPS:
            r = typical(by(sc, su), sz.cpu_seconds)
            print(f"{sc:9}{su:16}{r['wall_s']:>7.1f}{sz.cpu_seconds(r):>7.2f}{sz.cores_busy(r):>6.2f}"
                  f"{r['rss_peak_mb']:>8.0f}{r['requests']:>9}{sz.cpu_per_1000(r):>11.2f}")
    print("\nspread over the three runs (CPU s, peak MB):")
    for sc in ("startup", "steady", "many"):
        for su in SETUPS:
            rs = by(sc, su)
            cpu = [sz.cpu_seconds(r) for r in rs]
            mb = [r["rss_peak_mb"] for r in rs]
            print(f"{sc:9}{su:16}CPU {min(cpu):.2f}-{max(cpu):.2f}   MB {min(mb):.0f}-{max(mb):.0f}   "
                  f"load before {[r['load_before'] for r in rs]}")

    print("\n== with the start-up cost taken out")
    for su in SETUPS:
        s0, s1, s2 = (typical(by(sc, su), sz.cpu_seconds) for sc in ("startup", "steady", "many"))
        marg = sz.marginal_cpu_per_1000(s1, s0)
        per_core = 1000 / marg
        print(f"{su:16}start-up CPU {sz.cpu_seconds(s0):.2f} s, marginal {marg:.2f} CPU s per 1000 requests "
              f"= {per_core:.0f} requests per core-second; extra memory per user "
              f"{sz.mb_per_user(s1, s2):.3f} MB ({s1['users']} -> {s2['users']} users); "
              f"generators for 2000 rps at 70% busy: {sz.generators_needed(2000, per_core)}")
    print("cheapest by CPU per 1000 requests:",
          {sc: sz.cheapest({su: by(sc, su) for su in SETUPS}, sz.cpu_per_1000) for sc in ("startup", "steady", "many")})


if __name__ == "__main__":
    main()
