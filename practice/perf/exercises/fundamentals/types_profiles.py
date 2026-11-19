"""Build load profiles as schedules - exercise.

TODO: implement the functions below so every test in tests/fundamentals/test_types_profiles.py passes.

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
    """The target users at t seconds; None after the last stage. ValueError if t < 0."""
    raise NotImplementedError("TODO: users_at")


def ramp_hold(users: int, ramp_s: int, hold_s: int) -> list[Stage]:
    """One stage per ramp second (end_s = 1, 2, ... ramp_s) with users = ceil(users * second / (ramp_s + 1)),
    then one hold stage ending at ramp_s + hold_s with all users. spawn_rate = users on every stage.
    ValueError unless users > 0, ramp_s >= 0 and hold_s > 0."""
    raise NotImplementedError("TODO: ramp_hold")


def steps(start: int, step: int, every_s: float, count: int) -> list[Stage]:
    """count stages; stage i (from 0) ends at every_s * (i + 1) with start + step * i users and spawn_rate = step.
    ValueError unless every argument is positive."""
    raise NotImplementedError("TODO: steps")


def spike(base: int, peak: int, before_s: float, spike_s: float, after_s: float) -> list[Stage]:
    """Three stages: base until before_s (spawn_rate = base), peak until before_s + spike_s, then base until
    the end; the last two use spawn_rate = peak - base so the burst happens within a second.
    ValueError unless 0 < base < peak and every duration is positive."""
    raise NotImplementedError("TODO: spike")


def expected_users_series(stages: list[Stage], seconds: int) -> list[int | None]:
    """users_at(stages, t) for t = 0, 1, ..., seconds - 1."""
    raise NotImplementedError("TODO: expected_users_series")
