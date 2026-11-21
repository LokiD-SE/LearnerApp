"""Whiteboard sizing for a load test - reference solution.

The interview question is "how many virtual users do you need?". The answer is arithmetic you can do aloud:
the rate at the peak, Little's law for the closed model, and a utilisation target for the servers.
"""

import math

SECONDS_PER_DAY = 86_400


def arrival_rate(requests_per_day: float, peak_factor: float = 1.0) -> float:
    """Requests per second at the peak: the daily average times ``peak_factor`` (>= 1)."""
    if requests_per_day < 0:
        raise ValueError("requests_per_day must be >= 0")
    if peak_factor < 1:
        raise ValueError("peak_factor must be >= 1: the peak is never below the average")
    return requests_per_day / SECONDS_PER_DAY * peak_factor


def users_for_throughput(target_rps: float, response_s: float, think_s: float) -> int:
    """Virtual users a CLOSED load model needs to offer ``target_rps``: Little's law, N = X * (R + Z),
    rounded up (you cannot run 12.2 users, and rounding down under-delivers)."""
    if target_rps < 0 or response_s < 0 or think_s < 0:
        raise ValueError("target_rps, response_s and think_s must be >= 0")
    return math.ceil(target_rps * (response_s + think_s))


def throughput_for_users(users: int, response_s: float, think_s: float) -> float:
    """What N users offer when each waits for its reply and then thinks: X = N / (R + Z)."""
    if users < 0 or response_s < 0 or think_s < 0:
        raise ValueError("users, response_s and think_s must be >= 0")
    if response_s + think_s == 0:
        raise ValueError("response_s + think_s must be > 0: with no waiting at all the rate is unbounded")
    return users / (response_s + think_s)


def workers_needed(rate_rps: float, service_s: float, max_utilisation: float = 0.7) -> int:
    """Workers (threads, pool slots, servers) so the offered load ``rate * service_time`` stays at or below
    ``max_utilisation`` of capacity, rounded up."""
    if rate_rps < 0 or service_s < 0:
        raise ValueError("rate_rps and service_s must be >= 0")
    if not 0 < max_utilisation <= 1:
        raise ValueError("max_utilisation must be in (0, 1]")
    return math.ceil(rate_rps * service_s / max_utilisation)


def pacing_interval(users: int, target_rps: float) -> float:
    """Seconds between the starts of one user's iterations so ``users`` users together offer ``target_rps``."""
    if users <= 0 or target_rps <= 0:
        raise ValueError("users and target_rps must be > 0")
    return users / target_rps
