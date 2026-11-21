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
    raise NotImplementedError("TODO: the (users, spawn_rate) of the stage that is running at run_time, or None")


def from_steps(first_users: int, step_users: int, steps: int, step_seconds: float, spawn_rate: float) -> list[dict]:
    raise NotImplementedError("TODO: build `steps` stages with cumulative end times")


def ramp_seconds(from_users: int, to_users: int, spawn_rate: float) -> float:
    raise NotImplementedError("TODO: users to start or stop divided by users per second")


def stage_problems(stages: list[dict]) -> list[tuple[int, str]]:
    raise NotImplementedError("TODO: find the stages that cannot work")
