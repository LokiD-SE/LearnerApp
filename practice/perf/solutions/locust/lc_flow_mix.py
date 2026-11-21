"""From a workload model to Locust weights and back - reference solution.

Locust picks tasks by weight, and a weight is a share of *picks*, not of requests. These three helpers turn a
workload model (shares of user actions) into small integer weights, work out the request mix those weights produce,
and compare a run's observed mix with the model.
"""

from __future__ import annotations


def mix_to_weights(mix: dict[str, float], tolerance: float = 0.01, max_total: int = 100) -> dict[str, int]:
    """Smallest integer weights that reproduce ``mix`` (name -> share, shares add up to 1 within 0.001).

    Try totals n = len(mix), len(mix) + 1, ... up to ``max_total``: each weight is ``round(share * n)`` but at
    least 1, and the first n whose weights give every action a share within ``tolerance`` (absolute) of the model
    wins. Raises ValueError if the shares do not add up to 1, a share is not positive, or no n up to ``max_total``
    fits.
    """
    if not mix or any(v <= 0 for v in mix.values()):
        raise ValueError("every share must be positive")
    if abs(sum(mix.values()) - 1) > 0.001:
        raise ValueError(f"shares add up to {sum(mix.values()):.3f}, not 1")
    for n in range(len(mix), max_total + 1):
        weights = {k: max(1, round(v * n)) for k, v in mix.items()}
        total = sum(weights.values())
        if all(abs(weights[k] / total - mix[k]) <= tolerance for k in mix):
            return weights
    raise ValueError(f"no weights with total <= {max_total} are within {tolerance} of the model")


def request_shares(weights: dict[str, int], requests_per_pick: dict[str, int]) -> dict[str, float]:
    """The share of REQUESTS each action produces: weight x requests per pick, as a fraction of the total."""
    load = {k: w * requests_per_pick[k] for k, w in weights.items()}
    total = sum(load.values())
    return {k: v / total for k, v in load.items()}


def mix_deviations(observed: dict[str, int], model: dict[str, float]) -> dict[str, float]:
    """Observed share minus model share for every name in either (a name never seen has share 0)."""
    total = sum(observed.values())
    return {k: (observed.get(k, 0) / total if total else 0.0) - model.get(k, 0.0) for k in sorted(set(observed) | set(model))}
