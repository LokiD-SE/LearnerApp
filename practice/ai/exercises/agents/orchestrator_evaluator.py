"""Orchestrator-workers and evaluator-optimizer, from Anthropic's "Building effective agents" (2024) - lesson
agent-loops-and-workflow-patterns.

- ``plan_subtasks`` / ``orchestrate``: an orchestrator call decides the subtasks (as JSON your code validates),
  worker calls do one subtask each, a synthesiser call combines the results. Unlike sectioning, the subtasks are not
  fixed in code - but the plan is still checked and capped by code.
- ``evaluate_optimize``: a generator writes a draft, an evaluator returns its problems, and the generator revises
  with that feedback until the evaluator returns no problems or the round limit is hit. The evaluator is any
  callable ``draft -> list[str]``: plain code where the criteria are checkable, or ``llm_evaluator`` where not.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from agents.workflow_patterns import ask, thread_map

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")


class PlanError(ValueError):
    """The orchestrator's plan is not usable."""


def plan_subtasks(client: Any, task: str, max_subtasks: int = 5) -> list[dict[str, str]]:
    """Ask the orchestrator for a plan and validate it.

    Prompt contains the task inside ``<task>`` / ``</task>`` lines and asks for JSON only:
    ``{"subtasks": [{"id": "...", "instruction": "..."}]}``. Parse the text from its first ``{`` to its last ``}``.
    Raise PlanError when: there is no JSON object or it does not parse; ``subtasks`` is missing, not a list, empty or
    longer than ``max_subtasks``; an item lacks a string ``instruction`` or an ``id`` matching ``ID_RE``; ids repeat.
    Return the list of ``{"id", "instruction"}`` dicts (extra keys dropped).
    """
    raise NotImplementedError


def orchestrate(
    client: Any, task: str, max_subtasks: int = 5, map_fn: Callable[..., list[Any]] = thread_map
) -> dict[str, Any]:
    """Plan, run one worker per subtask through ``map_fn``, then synthesise.

    Worker prompt: ``"Overall task: {task}\\nYour subtask ({id}): {instruction}"``.
    Synthesiser prompt: the task in ``<task>`` tags, then each result as ``<result id="{id}">\\n{text}\\n</result>``
    in plan order, then ``"Combine the results into one answer."``.
    Returns ``{"plan": plan, "results": {id: text}, "answer": text}``. PlanError propagates - no workers run.
    """
    raise NotImplementedError


def llm_evaluator(client: Any, criteria: list[str]) -> Callable[[str], list[str]]:
    """An evaluator backed by a model: the draft in ``<draft>`` tags, the numbered criteria, and the instruction to
    reply ``PASS`` or one line ``FAIL: <problem>`` per problem. Returns the problems (``[]`` for PASS); a reply with
    neither is reported as ``["evaluator reply not understood"]`` - never a pass."""

    raise NotImplementedError


def evaluate_optimize(
    client: Any, task: str, evaluate: Callable[[str], list[str]], max_rounds: int = 3
) -> dict[str, Any]:
    """Generate, evaluate, revise - at most ``max_rounds`` drafts.

    Round 1 prompt: the task. Round k > 1 prompt: the task, the previous draft in ``<draft>`` tags, and
    ``"Fix these problems:"`` followed by one ``- problem`` line each. Stop as soon as ``evaluate`` returns ``[]``.
    Returns ``{"accepted": bool, "draft": last draft, "rounds": drafts written,
    "history": [{"draft", "problems"}]}``.
    """
    # Starting draft - it loops and stops, but each round starts from scratch. What does round 2 never see?
    history = []
    for _ in range(max_rounds):
        draft = ask(client, task, max_tokens=400)
        problems = evaluate(draft)
        history.append({"draft": draft, "problems": problems})
        if not problems:
            break
    return {"accepted": not history[-1]["problems"], "draft": history[-1]["draft"], "rounds": len(history), "history": history}
