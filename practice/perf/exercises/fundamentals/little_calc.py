"""Little's law and the response time law, as a load tester uses them.

Little's law: L = lambda * W - the average number of requests in a system equals the throughput times the
average time each request spends there. For a closed workload with think time Z, applied to the whole loop
(users plus system), it becomes N = X * (R + Z), and solved for R it is the response time law R = N / X - Z
(Lazowska et al., Quantitative System Performance, 1984, chapter 3).

Units: throughput in requests (or iterations) per second, times in seconds.
Run: .venv/bin/python -m pytest tests/fundamentals/test_little_calc.py
"""

from __future__ import annotations

import math  # noqa: F401 - you will need math.ceil


def concurrency(throughput_per_s: float, residence_s: float) -> float:
    """L = lambda * W: the average number of requests in the system.
    TODO: raise ValueError if either input is negative."""
    raise NotImplementedError("concurrency")


def users_needed(target_rps: float, response_time_s: float, think_time_s: float = 0.0,
                 requests_per_iteration: int = 1) -> int:
    """Virtual users a closed-loop test needs to reach ``target_rps`` requests per second.

    One iteration sends ``requests_per_iteration`` (k) requests one after another, each taking
    ``response_time_s`` (R), then thinks for ``think_time_s`` (Z).
    TODO: iterations per second X = target_rps / k; each user needs k*R + Z seconds per iteration, so
    N = X * (k*R + Z) - rounded UP (beware float noise: 36.000000001 must still be 36).
    Raise ValueError for negative inputs or k < 1.
    """
    raise NotImplementedError("users_needed")


def response_time_from(users: int, throughput_per_s: float, think_time_s: float = 0.0) -> float:
    """The response time law R = N / X - Z.
    TODO: raise ValueError if throughput <= 0, and raise ValueError mentioning "inconsistent" if the result
    is negative - three measurements that give a negative response time contradict each other."""
    raise NotImplementedError("response_time_from")


def pacing_seconds(target_rps: float, users: int, requests_per_iteration: int = 1) -> float:
    """Seconds from the start of one iteration to the start of the next, per user, so that ``users`` users
    together send ``target_rps`` requests per second.
    TODO: raise ValueError unless target_rps > 0, users > 0 and requests_per_iteration >= 1."""
    raise NotImplementedError("pacing_seconds")


def locust_constant_throughput(target_rps: float, users: int, requests_per_iteration: int = 1) -> float:
    """The argument for Locust's ``wait_time = constant_throughput(x)``: task runs per second per user.
    TODO: it is the inverse of the pacing."""
    raise NotImplementedError("locust_constant_throughput")


def max_closed_throughput(users: int, iteration_s: float, pacing_s: float = 0.0,
                          requests_per_iteration: int = 1) -> float:
    """The most requests per second a closed loop can produce.
    TODO: a paced user starts an iteration every max(pacing, iteration time) seconds - pacing can't make a
    slow iteration faster. Raise ValueError if both are zero (unbounded) or anything is negative."""
    raise NotImplementedError("max_closed_throughput")
