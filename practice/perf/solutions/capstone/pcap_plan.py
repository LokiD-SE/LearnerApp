"""Plan the load before you script it: rates, ceiling, users and run length (reference solution).

The capstone plan answers four questions from numbers you can state before any tool runs:

1. Which request rate does each transaction need, given the workload mix and the total target?
2. What is the highest throughput the API can serve at all (its ceiling), and how close is the target to it?
3. How many virtual users does a closed loop need to ask for that rate? (Little's law - reuse ``ref.users_needed``.)
4. How long must the run last for the rarest transaction to give enough samples to judge a percentile?

All times are in milliseconds unless the name says ``_s``.
"""

import math

from pcap_fixture import ref


def _check_mix(mix: dict[str, int]) -> int:
    if not mix:
        raise ValueError("the mix is empty")
    if any(w <= 0 for w in mix.values()):
        raise ValueError("every weight must be positive")
    return sum(mix.values())


def transaction_rates(mix: dict[str, int], total_rps: float) -> dict[str, float]:
    """Requests per second for each transaction: ``total_rps`` split by weight."""
    if total_rps <= 0:
        raise ValueError("total_rps must be positive")
    total = _check_mix(mix)
    return {tx: total_rps * w / total for tx, w in mix.items()}


def mean_service_ms(mix: dict[str, int], service_ms: dict[str, float]) -> float:
    """Average service time of one request in this mix (weighted by the mix, not a plain average)."""
    total = _check_mix(mix)
    missing = [tx for tx in mix if tx not in service_ms]
    if missing:
        raise ValueError(f"no service time for {missing}")
    return sum(service_ms[tx] * w for tx, w in mix.items()) / total


def ceiling_rps(workers: int, mean_ms: float) -> float:
    """Most requests per second ``workers`` parallel workers can serve: workers / mean service time."""
    if workers < 1 or mean_ms <= 0:
        raise ValueError("need at least one worker and a positive service time")
    return workers / (mean_ms / 1000)


def run_seconds(rate_rps: float, min_samples: int, warmup_s: float = 5.0) -> int:
    """Seconds to run so that, after dropping ``warmup_s``, a transaction at ``rate_rps`` gives ``min_samples``."""
    if rate_rps <= 0 or min_samples < 1 or warmup_s < 0:
        raise ValueError("rate and samples must be positive, warm-up not negative")
    return math.ceil(min_samples / rate_rps + warmup_s)


def engagement_plan(mix: dict[str, int], service_ms: dict[str, float], workers: int, target_rps: float,
                    think_s: float, min_samples: int = 100, warmup_s: float = 5.0,
                    max_utilisation: float = 0.7) -> dict:
    """The plan as one dictionary:

    ``rates``           per-transaction req/s (``transaction_rates``)
    ``mean_service_ms`` weighted mean service time
    ``ceiling_rps``     what the workers can serve at most
    ``utilisation``     ``target_rps / ceiling_rps``, rounded to 2 decimals
    ``users``           virtual users for a closed loop at ``target_rps`` (response time = mean service time)
    ``run_seconds``     the longest ``run_seconds`` over all transactions (the rarest one decides)
    ``rarest``          the transaction that decides it
    ``warnings``        strings: one ``"utilisation ..."`` entry when utilisation is above ``max_utilisation``
    ``ok``              True when there are no warnings
    """
    rates = transaction_rates(mix, target_rps)
    mean = mean_service_ms(mix, service_ms)
    ceiling = ceiling_rps(workers, mean)
    utilisation = round(target_rps / ceiling, 2)
    rarest = min(rates, key=rates.get)
    warnings = []
    if utilisation > max_utilisation:
        warnings.append(f"utilisation {utilisation:.0%} is above {max_utilisation:.0%}: the target sits too close to the "
                        f"ceiling of {ceiling:.0f} req/s for a clean pass/fail")
    return {"rates": rates, "mean_service_ms": mean, "ceiling_rps": ceiling, "utilisation": utilisation,
            "users": ref.users_needed(target_rps, mean / 1000, think_s),
            "run_seconds": run_seconds(rates[rarest], min_samples, warmup_s), "rarest": rarest,
            "warnings": warnings, "ok": not warnings}
