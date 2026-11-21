"""From a workload model to Locust weights and back - EXERCISE.

Locust picks tasks by weight, and a weight is a share of *picks*, not of requests. Implement three helpers that
turn a workload model (shares of user actions) into small integer weights, work out the request mix those weights
produce, and compare a run's observed mix with the model. tests/locust/test_lc_flow_mix.py checks them.
"""

from __future__ import annotations


def mix_to_weights(mix: dict[str, float], tolerance: float = 0.01, max_total: int = 100) -> dict[str, int]:
    """Smallest integer weights that reproduce ``mix`` (name -> share; the shares add up to 1 within 0.001).

    Try totals n = len(mix), len(mix) + 1, ... up to ``max_total``. For each n, a weight is ``round(share * n)``
    but never less than 1. The first n whose weights give EVERY action a share (weight / sum of weights) within
    ``tolerance`` (absolute) of its model share wins.

    ``mix_to_weights({"browse": 0.6, "pay": 0.3, "report": 0.1})`` -> ``{"browse": 6, "pay": 3, "report": 1}``.

    Raise ValueError if a share is not positive, the shares do not add up to 1 (within 0.001), or no n up to
    ``max_total`` fits.
    """
    # TODO
    raise NotImplementedError


def request_shares(weights: dict[str, int], requests_per_pick: dict[str, int]) -> dict[str, float]:
    """The share of REQUESTS each action produces: ``weight x requests per pick``, as a fraction of the total.

    A "pay" action that sends 3 requests each time it is picked, with the same weight as a 1-request "browse",
    produces three times the requests.
    """
    # TODO
    raise NotImplementedError


def mix_deviations(observed: dict[str, int], model: dict[str, float]) -> dict[str, float]:
    """Observed share minus model share for every name that is in either one, sorted by name.

    ``observed`` is counts (for example Locust's ``num_requests`` per name); a name that was never seen has an
    observed share of 0, a name that is not in the model has a model share of 0. An empty run (no counts) has an
    observed share of 0 for everything.
    """
    # TODO
    raise NotImplementedError
