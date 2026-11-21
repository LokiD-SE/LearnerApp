"""Is this load-test result trustworthy? - reference solution.

The debug question in a performance interview is "the result looks odd, what do you check?". Before anyone
argues about the application, check the RUN: was it long enough, was the generator healthy, did the load arrive
as planned, did failures flatter the latency, did a warm-up leak in?
"""

MIN_SAMPLES = 100
GENERATOR_CPU_PCT = 80.0
ERROR_RATE = 0.01
FLATTER_RATIO = 0.5
BELOW_PLAN = 0.9
WARMUP_RATIO = 1.5

#: Checked in this order. A generator that is out of CPU explains a rate below the plan, so it comes first;
#: a run too short to measure anything comes before everything, because every other number is noise.
PRIORITY = ("too_few_samples", "generator_saturated", "fast_failures_flatter_latency", "below_plan",
            "warmup_included")

ADVICE = {
    "too_few_samples": "Run longer or with more load: under %d samples a percentile is a guess." % MIN_SAMPLES,
    "generator_saturated": "The load generator is out of CPU: add generator machines or lighten the script, then rerun.",
    "fast_failures_flatter_latency": "Failures return fast and pull the median down: report latency for successes "
                                     "separately and fix the errors before reading any latency number.",
    "below_plan": "The system could not take the planned rate: look for saturation (queues, pools, CPU) "
                  "or an open/closed model mismatch.",
    "warmup_included": "The first third is much slower than the last: cut the warm-up from the measurement "
                       "window or lengthen the run.",
}

REQUIRED = ("samples", "errors", "duration_s", "achieved_rps", "p50_all_ms", "p50_ok_ms", "first_third_p95_ms",
            "last_third_p95_ms")


def smells(summary: dict) -> list[str]:
    """The smells found in one run summary, most important first. An empty list means no smell was found."""
    missing = [k for k in REQUIRED if k not in summary]
    if missing:
        raise ValueError(f"summary is missing: {', '.join(missing)}")
    found = set()
    n = summary["samples"]
    if n < MIN_SAMPLES:
        found.add("too_few_samples")
    cpu = summary.get("generator_cpu_pct")
    if cpu is not None and cpu >= GENERATOR_CPU_PCT:
        found.add("generator_saturated")
    if n and summary["errors"] / n > ERROR_RATE and summary["p50_all_ms"] < FLATTER_RATIO * summary["p50_ok_ms"]:
        found.add("fast_failures_flatter_latency")
    planned = summary.get("planned_rps")
    if planned and summary["achieved_rps"] < BELOW_PLAN * planned:
        found.add("below_plan")
    if summary["last_third_p95_ms"] > 0 and summary["first_third_p95_ms"] > WARMUP_RATIO * summary["last_third_p95_ms"]:
        found.add("warmup_included")
    return [s for s in PRIORITY if s in found]


def verdict(found: list[str]) -> str:
    """``trust`` when nothing smelled, otherwise ``rerun``: a run with a smell is evidence about the test."""
    return "rerun" if found else "trust"


def next_step(found: list[str]) -> str:
    """The advice for the first (highest-priority) smell."""
    if not found:
        return "No smell found: read the percentiles, then compare with the baseline."
    return ADVICE[found[0]]
