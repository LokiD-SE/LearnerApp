"""What does a script cost the load generator? Analyse a JTL of script-only samplers (jm_groovy_ exercise 3).

``tests/jmeter/fixtures/jm_groovy_cost.jtl`` was recorded by ``jm_groovy_cost.jmx``: one thread, 200 loops, the
same HMAC script as a cached Groovy JSR223 Sampler, an uncached one (cacheKey false) and a BeanShell Sampler.
The ``elapsed`` column (ms) of a JSR223 or BeanShell sampler is the time its script took.
"""

from __future__ import annotations

import math
import statistics


def nearest_rank(values: list[int], pct: float) -> int:
    """The nearest-rank percentile: the value at position ceil(pct/100 * n) of the sorted list (1-based)."""
    ordered = sorted(values)
    return ordered[max(1, math.ceil(pct / 100 * len(ordered))) - 1]


def summarise(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    """Per label: ``n``, ``first_ms`` (the first sample, which pays engine start-up and the first compile),
    ``median_ms`` and ``p95_ms`` of the REST of the samples (steady state), and ``total_ms`` of all of them."""
    elapsed: dict[str, list[int]] = {}
    for row in rows:
        elapsed.setdefault(row["label"], []).append(int(row["elapsed"]))
    out = {}
    for label, values in elapsed.items():
        rest = values[1:] or values
        out[label] = {"n": len(values), "first_ms": values[0], "median_ms": statistics.median(rest),
                      "p95_ms": nearest_rank(rest, 95), "total_ms": sum(values)}
    return out


def compile_overhead_ms(summary: dict[str, dict[str, float]], cached: str, uncached: str) -> float:
    """Steady-state cost of compiling on every run: the median of the uncached label minus the cached one."""
    return summary[uncached]["median_ms"] - summary[cached]["median_ms"]


def generator_cores(script_ms: float, samples_per_second: float) -> float:
    """CPU cores the load generator spends only on this script at the given rate, assuming the script time is
    CPU time: script_ms x samples per second / 1000, rounded to 2 places."""
    return round(script_ms * samples_per_second / 1000, 2)
