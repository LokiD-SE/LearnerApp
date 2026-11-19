"""Little's law and the response time law, as a load tester uses them (reference solution).

Little's law: L = lambda * W - the average number of requests in a system equals the throughput times the
average time each request spends there. For a closed workload with think time Z, applied to the whole loop
(users plus system), it becomes N = X * (R + Z), and solved for R it is the response time law R = N / X - Z
(Lazowska et al., Quantitative System Performance, 1984, chapter 3).

Units: throughput in requests (or iterations) per second, times in seconds.
"""

from __future__ import annotations

import math


def _check_non_negative(**values: float) -> None:
    for name, value in values.items():
        if value < 0:
            raise ValueError(f"{name} must not be negative, got {value}")


def concurrency(throughput_per_s: float, residence_s: float) -> float:
    """L = lambda * W: the average number of requests in the system."""
    _check_non_negative(throughput_per_s=throughput_per_s, residence_s=residence_s)
    return throughput_per_s * residence_s


def users_needed(target_rps: float, response_time_s: float, think_time_s: float = 0.0,
                 requests_per_iteration: int = 1) -> int:
    """Virtual users a closed-loop test needs to reach ``target_rps`` requests per second.

    One iteration sends ``requests_per_iteration`` requests one after another (each taking ``response_time_s``)
    and then thinks for ``think_time_s``. Iterations per second X = target_rps / k, and each user needs
    k * R + Z seconds per iteration, so N = X * (k * R + Z), rounded up - a fraction of a user can't run.
    """
    _check_non_negative(target_rps=target_rps, response_time_s=response_time_s, think_time_s=think_time_s)
    if requests_per_iteration < 1:
        raise ValueError("requests_per_iteration must be at least 1")
    k = requests_per_iteration
    exact = target_rps / k * (k * response_time_s + think_time_s)
    return math.ceil(exact - 1e-9)


def response_time_from(users: int, throughput_per_s: float, think_time_s: float = 0.0) -> float:
    """The response time law R = N / X - Z. A negative result means the three measurements contradict each
    other (for example throughput measured over a different window), so it raises instead of returning it."""
    _check_non_negative(users=users, think_time_s=think_time_s)
    if throughput_per_s <= 0:
        raise ValueError("throughput must be positive")
    r = users / throughput_per_s - think_time_s
    if r < 0:
        raise ValueError(f"inconsistent measurements: N/X - Z = {r:.3f} s is negative")
    return r


def pacing_seconds(target_rps: float, users: int, requests_per_iteration: int = 1) -> float:
    """Seconds from the start of one iteration to the start of the next, per user, so that ``users`` users
    together send ``target_rps`` requests per second (what JMeter's timers and Locust's constant_pacing aim for)."""
    if target_rps <= 0 or users <= 0 or requests_per_iteration < 1:
        raise ValueError("target_rps and users must be positive, requests_per_iteration at least 1")
    return users * requests_per_iteration / target_rps


def locust_constant_throughput(target_rps: float, users: int, requests_per_iteration: int = 1) -> float:
    """The argument for Locust's ``wait_time = constant_throughput(x)``: task runs per second per user."""
    return 1 / pacing_seconds(target_rps, users, requests_per_iteration)


def max_closed_throughput(users: int, iteration_s: float, pacing_s: float = 0.0,
                          requests_per_iteration: int = 1) -> float:
    """The most requests per second a closed loop can produce. A paced user starts an iteration every
    max(pacing, iteration time) seconds - pacing cannot make a slow iteration faster, it only waits less."""
    _check_non_negative(users=users, iteration_s=iteration_s, pacing_s=pacing_s)
    cycle = max(iteration_s, pacing_s)
    if cycle == 0:
        raise ValueError("iteration time and pacing are both zero - throughput is unbounded")
    return users * requests_per_iteration / cycle
