"""Stage plans for a Locust load shape, as plain data and plain functions (no Locust import).

A plan is a list of stages in the layout of the Locust documentation's stage examples:

    {"duration": 30, "users": 10, "spawn_rate": 5}

``duration`` is the **end** of the stage in seconds since the test started (30 means "until second 30"), not its
length. Locust's ``tick()`` runs about once a second; ``tick(stages, run_time)`` below is the decision it makes.

1. ``tick(stages, run_time)`` - the (users, spawn_rate) of the first stage whose end is after ``run_time``, or
   ``None`` when every stage is over (which is what stops a Locust shape test).
2. ``from_steps(first_users, step_users, steps, step_seconds, spawn_rate)`` - a step-load plan: ``steps`` stages of
   ``step_seconds`` each, the first with ``first_users`` and every next one ``step_users`` more.
3. ``ramp_seconds(from_users, to_users, spawn_rate)`` - how long Locust needs to go from one user count to the
   other at ``spawn_rate`` users per second (it starts and stops users at that rate). ``spawn_rate`` must be > 0.
4. ``stage_problems(stages)`` - a plan review. Walk the stages from 0 users at time 0 and return
   ``(index, problem)`` for each stage that cannot work, in stage order:
   - ``"not-increasing"``: the stage ends at or before the end of an earlier stage, so ``tick`` can never reach it
     (the usual cause: lengths written where end times belong). Skip such a stage when judging later stages.
   - ``"ramp-too-slow"``: getting from the previous stage's users to this stage's users takes longer than the
     stage lasts (a ramp of exactly the stage length is fine), so the stage is replaced before its target is reached.
"""

from __future__ import annotations


def tick(stages: list[dict], run_time: float) -> tuple[int, float] | None:
    for stage in stages:
        if run_time < stage["duration"]:
            return stage["users"], stage["spawn_rate"]
    return None


def from_steps(first_users: int, step_users: int, steps: int, step_seconds: float, spawn_rate: float) -> list[dict]:
    return [
        {"duration": (i + 1) * step_seconds, "users": first_users + i * step_users, "spawn_rate": spawn_rate}
        for i in range(steps)
    ]


def ramp_seconds(from_users: int, to_users: int, spawn_rate: float) -> float:
    if spawn_rate <= 0:
        raise ValueError("spawn_rate must be positive")
    return abs(to_users - from_users) / spawn_rate


def stage_problems(stages: list[dict]) -> list[tuple[int, str]]:
    problems: list[tuple[int, str]] = []
    previous_end = 0.0
    previous_users = 0
    for index, stage in enumerate(stages):
        length = stage["duration"] - previous_end
        if length <= 0:
            problems.append((index, "not-increasing"))
            continue
        if ramp_seconds(previous_users, stage["users"], stage["spawn_rate"]) > length:
            problems.append((index, "ramp-too-slow"))
        previous_end = stage["duration"]
        previous_users = stage["users"]
    return problems
