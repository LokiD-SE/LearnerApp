"""Exercise pcap_plan: plan the load before you script it - rates, ceiling, users and run length.

The capstone plan answers four questions from numbers you can state before any tool runs:

1. Which request rate does each transaction need, given the workload mix and the total target?
   ``transaction_rates(mix, total_rps)``: ``total_rps`` split by weight.
2. What is the highest throughput the API can serve at all (its ceiling), and how close is the target to it?
   ``mean_service_ms(mix, service_ms)`` is the mix-weighted mean service time (NOT a plain average of the
   transactions); ``ceiling_rps(workers, mean_ms)`` is ``workers / mean service time`` in req/s.
3. How many virtual users does a closed loop need to ask for that rate? Little's law - reuse ``ref.users_needed``
   (the reference code of the Little's law lesson; response time = the mean service time while the API is far from
   its ceiling).
4. How long must the run last for the rarest transaction to give enough samples to judge a percentile?
   ``run_seconds(rate_rps, min_samples, warmup_s)`` = ``ceil(min_samples / rate + warmup)``.

``engagement_plan`` puts them in one dictionary (keys: ``rates``, ``mean_service_ms``, ``ceiling_rps``,
``utilisation`` = target / ceiling rounded to 2 decimals, ``users``, ``run_seconds`` = the longest over all
transactions, ``rarest``, ``warnings``, ``ok``). When utilisation is above ``max_utilisation`` it adds ONE warning
string starting ``"utilisation "`` and ``ok`` is False.

Bad input (an empty mix, a weight of zero or less, a transaction with no service time, a non-positive rate,
zero workers) raises ``ValueError``. All times are in milliseconds unless the name says ``_s``.
"""

import math  # noqa: F401  (you will want math.ceil)

from pcap_fixture import ref  # noqa: F401  (ref.users_needed)


def transaction_rates(mix: dict[str, int], total_rps: float) -> dict[str, float]:
    """Requests per second for each transaction: ``total_rps`` split by weight."""
    raise NotImplementedError("split total_rps by weight")


def mean_service_ms(mix: dict[str, int], service_ms: dict[str, float]) -> float:
    """Average service time of one request in this mix (weighted by the mix)."""
    raise NotImplementedError("weighted mean")


def ceiling_rps(workers: int, mean_ms: float) -> float:
    """Most requests per second ``workers`` parallel workers can serve."""
    raise NotImplementedError("workers / mean service time")


def run_seconds(rate_rps: float, min_samples: int, warmup_s: float = 5.0) -> int:
    """Seconds to run so that, after dropping ``warmup_s``, a transaction at ``rate_rps`` gives ``min_samples``."""
    raise NotImplementedError("ceil(min_samples / rate + warmup)")


def engagement_plan(mix: dict[str, int], service_ms: dict[str, float], workers: int, target_rps: float,
                    think_s: float, min_samples: int = 100, warmup_s: float = 5.0,
                    max_utilisation: float = 0.7) -> dict:
    """The plan as one dictionary (keys in the module docstring)."""
    raise NotImplementedError("combine the four answers")
