"""Build load profiles as schedules - reference solution.

A schedule is what a load generator follows: how many virtual users should be running at second ``t``.
``Stages`` lists ``(end_s, users, spawn_rate)`` like the "time based stages" example in the Locust docs: from
the previous stage's end until ``end_s`` the target is ``users``; ``spawn_rate`` is how many users per second
Locust starts or stops on the way to that target.

- ``users_at(stages, t)`` - the target user count at ``t`` seconds, or ``None`` after the last stage (which is
  what ``LoadTestShape.tick`` returns to stop the test).
- ``ramp_hold(users, ramp_s, hold_s)`` - a load test: ramp linearly to ``users`` over ``ramp_s`` seconds (one
  stage per second, rounded up), then hold for ``hold_s`` seconds.
- ``steps(start, step, every_s, count)`` - a breakpoint/stress staircase: ``start`` users, then ``step`` more
  every ``every_s`` seconds, ``count`` stages in total.
- ``spike(base, peak, before_s, spike_s, after_s)`` - ``base`` users, a burst to ``peak`` for ``spike_s``
  seconds, then ``base`` again.
- ``expected_users_series(stages, seconds)`` - the target at t = 0, 1, ... seconds - 1 (for plotting/checking).
"""

from __future__ import annotations

import math

Stage = tuple[float, int, float]  # (end_s, users, spawn_rate)


def users_at(stages: list[Stage], t: float) -> int | None:
    if t < 0:
        raise ValueError("t must be >= 0")
    for end_s, users, _ in stages:
        if t < end_s:
            return users
    return None


def ramp_hold(users: int, ramp_s: int, hold_s: int) -> list[Stage]:
    if users <= 0 or ramp_s < 0 or hold_s <= 0:
        raise ValueError("users and hold_s must be positive, ramp_s >= 0")
    stages: list[Stage] = []
    for second in range(1, ramp_s + 1):
        stages.append((float(second), math.ceil(users * second / (ramp_s + 1)), float(users)))
    stages.append((float(ramp_s + hold_s), users, float(users)))
    return stages


def steps(start: int, step: int, every_s: float, count: int) -> list[Stage]:
    if start <= 0 or step <= 0 or every_s <= 0 or count <= 0:
        raise ValueError("start, step, every_s and count must be positive")
    return [(every_s * (i + 1), start + step * i, float(step)) for i in range(count)]


def spike(base: int, peak: int, before_s: float, spike_s: float, after_s: float) -> list[Stage]:
    if not 0 < base < peak:
        raise ValueError("need 0 < base < peak")
    if before_s <= 0 or spike_s <= 0 or after_s <= 0:
        raise ValueError("durations must be positive")
    burst = float(peak - base)  # reach the peak within one second: that is what makes it a spike
    return [(before_s, base, float(base)), (before_s + spike_s, peak, burst),
            (before_s + spike_s + after_s, base, burst)]


def expected_users_series(stages: list[Stage], seconds: int) -> list[int | None]:
    return [users_at(stages, t) for t in range(seconds)]
