"""Whiteboard sizing for a load test - your turn.

The interview question is "how many virtual users do you need?". Implement the arithmetic you would do aloud.
Run: .venv/bin/python -m pytest tests/capstone/test_pmi_sizing.py
"""

import math  # noqa: F401 - you will need it

SECONDS_PER_DAY = 86_400


def arrival_rate(requests_per_day: float, peak_factor: float = 1.0) -> float:
    """Requests per second at the peak: the daily average times ``peak_factor``.

    TODO: raise ValueError for negative requests or a peak_factor below 1 (the peak is never below the average).
    """
    raise NotImplementedError("TODO: requests_per_day / SECONDS_PER_DAY * peak_factor")


def users_for_throughput(target_rps: float, response_s: float, think_s: float) -> int:
    """Virtual users a CLOSED model needs to offer ``target_rps``: Little's law, N = X * (R + Z), rounded UP.

    TODO: raise ValueError for a negative argument.
    """
    raise NotImplementedError("TODO")


def throughput_for_users(users: int, response_s: float, think_s: float) -> float:
    """What N users offer when each waits for its reply and then thinks: X = N / (R + Z).

    TODO: raise ValueError for a negative argument, and when response_s + think_s is 0 (the rate is unbounded).
    """
    raise NotImplementedError("TODO")


def workers_needed(rate_rps: float, service_s: float, max_utilisation: float = 0.7) -> int:
    """Workers so that rate * service_time stays at or below ``max_utilisation`` of capacity, rounded UP.

    TODO: raise ValueError for negative inputs and for max_utilisation outside (0, 1].
    """
    raise NotImplementedError("TODO")


def pacing_interval(users: int, target_rps: float) -> float:
    """Seconds between the starts of one user's iterations so ``users`` users together offer ``target_rps``.

    TODO: raise ValueError unless both arguments are > 0.
    """
    raise NotImplementedError("TODO")
