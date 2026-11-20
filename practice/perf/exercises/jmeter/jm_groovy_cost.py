"""What does a script cost the load generator? Analyse a JTL of script-only samplers (jm_groovy_ exercise 3).

``tests/jmeter/fixtures/jm_groovy_cost.jtl`` was recorded by ``jm_groovy_cost.jmx``: one thread, 200 loops, the
same HMAC script as a cached Groovy JSR223 Sampler, an uncached one (cacheKey false) and a BeanShell Sampler.
The ``elapsed`` column (ms) of a JSR223 or BeanShell sampler is the time its script took.
"""

from __future__ import annotations


def nearest_rank(values: list[int], pct: float) -> int:
    """The nearest-rank percentile: the value at position ceil(pct/100 * n) of the sorted list (1-based).

    TODO: sort, compute the 1-based rank with math.ceil, never go below rank 1.
    """
    raise NotImplementedError("TODO: nearest_rank")


def summarise(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    """Per label: ``n``, ``first_ms`` (the first sample, which pays engine start-up and the first compile),
    ``median_ms`` and ``p95_ms`` of the REST of the samples (steady state), and ``total_ms`` of all of them.

    TODO: group int(row["elapsed"]) by row["label"] in file order; statistics.median for the median.
    """
    raise NotImplementedError("TODO: summarise")


def compile_overhead_ms(summary: dict[str, dict[str, float]], cached: str, uncached: str) -> float:
    """Steady-state cost of compiling on every run: the median of the uncached label minus the cached one.

    TODO
    """
    raise NotImplementedError("TODO: compile_overhead_ms")


def generator_cores(script_ms: float, samples_per_second: float) -> float:
    """CPU cores the load generator spends only on this script at the given rate, assuming the script time is
    CPU time: script_ms x samples per second / 1000, rounded to 2 places.

    TODO
    """
    raise NotImplementedError("TODO: generator_cores")
