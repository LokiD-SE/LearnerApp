"""Prints every number and block the capstone lesson shows, from the reference solutions and the captured runs.

    cd practice/perf && .venv/bin/python support/pcap_demo.py
"""

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "solutions" / "capstone"))

import pcap_fixture as fx  # noqa: E402
import pcap_plan  # noqa: E402
import pcap_report as rep  # noqa: E402

ref = fx.ref
TEXT = [
    "p95 of POST /v1/payments < 120 ms at 24 req/s",
    "p95 of GET /v1/payments < 80 ms at 18 req/s",
    "p95 of GET /v1/payments/{id} < 80 ms at 15 req/s",
    "p95 of GET /v1/reports/settlement < 400 ms at 3 req/s",
    "error rate of POST /v1/payments below 1% at 24 req/s",
]
REQUIREMENTS = [ref.parse_requirement(t) for t in TEXT]


def show(verdicts, title):
    print(f"--- {title}")
    for v in verdicts:
        observed = "-" if v.observed is None else f"{v.observed:g}"
        print(f"{v.transaction:28} {v.kind:8} target {v.target:>5g}  observed {observed:>5}  n={v.samples:<5} {v.status:12} {v.note}")


def main() -> None:
    service = {tx: fx.BASE_SERVICE_MS * f for tx, f in fx.SERVICE_FACTOR.items()}
    print("--- plan")
    for target, think in ((60, 0.3), (180, 0.3)):
        plan = pcap_plan.engagement_plan(fx.MIX, service, fx.WORKERS, target, think)
        print(target, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in plan.items() if k != "rates"})
        print("   rates", {k: round(v, 2) for k, v in plan["rates"].items()})
    service_ceiling = pcap_plan.ceiling_rps(fx.WORKERS, pcap_plan.mean_service_ms(fx.MIX, service))
    plain = sum(service.values()) / len(service)
    print("plain mean of the four service times:", plain)

    samples = ref.from_jtl(fx.read_rows("jmeter_target"))
    steady = rep.steady_samples(samples, 5)
    print(f"--- JMeter: {len(samples)} samples, {len(steady)} after dropping 5 s of warm-up")
    jm = ref.evaluate(steady, REQUIREMENTS)
    show(jm, "JMeter, target load, steady state")
    lc = rep.locust_verdicts(fx.read_stats("locust_target"), REQUIREMENTS)
    show(lc, "Locust, target load")
    agreement = rep.compare_tools(jm, lc)
    print("agreement:", agreement)
    stress = rep.locust_verdicts(fx.read_stats("locust_stress"), REQUIREMENTS)
    show(stress, "Locust, stress (60 users, no think time)")
    print("agreement JMeter target vs Locust stress:", rep.compare_tools(jm, stress))
    print("final calls:", rep.final_call({"JMeter": jm, "Locust": lc}, agreement),
          rep.final_call({"Locust stress": stress}),
          rep.final_call({"JMeter": jm, "Locust": rep.locust_verdicts(fx.read_stats("locust_target"), REQUIREMENTS, min_samples=200)}))
    plan = pcap_plan.engagement_plan(fx.MIX, service, fx.WORKERS, 60, 0.3)
    caveats = ["One machine runs the API, the load generator and the analysis (14 CPUs); absolute times are optimistic.",
               "Locust rounds response times to two significant digits; JMeter times are exact.",
               "Closed-loop users with a think time: a slow API lowers the request rate instead of queueing arrivals.",
               "The API is a practice target on loopback; its service times are configured, not measured."]
    print(rep.render_report("SandPay API - settlement-day load test", plan, {"JMeter": jm, "Locust": lc}, agreement, caveats))
    print(rep.render_report("SandPay API - 60 users, no think time", plan, {"Locust stress": stress}, None, caveats[:2]))
    import collections
    jm_count = collections.Counter(s.label for s in steady if s.label in fx.MIX)
    lc_count = {e["name"]: e["num_requests"] for e in fx.read_stats("locust_target") if e["name"] in fx.MIX}
    for label, counts in (("JMeter steady", jm_count), ("Locust", lc_count)):
        total = sum(counts.values())
        print(f"mix shares {label}:", {k: f"{100 * counts[k] / total:.1f}%" for k in fx.MIX}, "of", total)
    entries = [e for e in fx.read_stats("locust_stress") if e["name"] not in fx.NOT_USER_TRAFFIC]
    x = sum(e["num_requests"] / (e["last_request_timestamp"] - e["start_time"]) for e in entries)
    print(f"stress: total {x:.1f} req/s from 60 users with no think time -> N/X = {60 / x * 1000:.0f} ms per request"
          f" (ceiling {service_ceiling:.1f} req/s, {x / service_ceiling:.0%} of it)")
    runs = fx.RUNS
    for k in ("jmeter_target", "locust_target", "locust_stress"):
        r = runs[k]
        print(k, r["users"], r["think_s"], r["duration_s"], r["api"]["requests"], r["api"]["max_in_flight"],
              r["api"]["payments_created"], round(r["loadavg_after"], 1))
    print("machine", runs["machine"])
    spans = {e["name"]: round(e["last_request_timestamp"] - e["start_time"], 1) for e in fx.read_stats("locust_target")}
    print("locust target spans", spans)
    first = min(s.timestamp_ms for s in samples)
    print("jmeter span s", (max(s.timestamp_ms + s.elapsed_ms for s in samples) - first) / 1000)


if __name__ == "__main__":
    main()
