"""Is this load-test result trustworthy? - your turn.

The debug question in a performance interview is "the result looks odd, what do you check?". Check the RUN before
you blame the application. Implement ``smells``, ``verdict`` and ``next_step``.
Run: .venv/bin/python -m pytest tests/capstone/test_pmi_smells.py

A summary is a dict with (at least) these keys: ``samples``, ``errors``, ``duration_s``, ``achieved_rps``,
``p50_all_ms``, ``p50_ok_ms``, ``first_third_p95_ms``, ``last_third_p95_ms``; and optionally ``planned_rps`` and
``generator_cpu_pct`` (either may be None).
"""

MIN_SAMPLES = 100
GENERATOR_CPU_PCT = 80.0
ERROR_RATE = 0.01
FLATTER_RATIO = 0.5
BELOW_PLAN = 0.9
WARMUP_RATIO = 1.5

#: The order matters: this is the order a smell is reported and advised in.
PRIORITY = ("too_few_samples", "generator_saturated", "fast_failures_flatter_latency", "below_plan",
            "warmup_included")


def smells(summary: dict) -> list[str]:
    """The smells found in one run summary, in PRIORITY order. An empty list means none was found.

    - too_few_samples: fewer than MIN_SAMPLES samples.
    - generator_saturated: generator_cpu_pct is known and at least GENERATOR_CPU_PCT.
    - fast_failures_flatter_latency: more than ERROR_RATE of the samples failed AND the median of all samples
      is below FLATTER_RATIO times the median of the successes.
    - below_plan: planned_rps is given and achieved_rps is below BELOW_PLAN times it.
    - warmup_included: the first third's p95 is more than WARMUP_RATIO times the last third's p95.

    TODO: raise ValueError (naming the keys) when a required key is missing.
    """
    raise NotImplementedError("TODO")


def verdict(found: list[str]) -> str:
    """"trust" when nothing smelled, otherwise "rerun"."""
    raise NotImplementedError("TODO")


def next_step(found: list[str]) -> str:
    """One sentence of advice for the FIRST smell; a different sentence for each smell, and one for no smell."""
    raise NotImplementedError("TODO")
