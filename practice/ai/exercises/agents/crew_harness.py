"""Testing a crew deterministically - lesson multi-agent-systems-crewai.

A crew makes many model calls in an order that depends on the process and (in a hierarchical crew) on the
manager's choices. These helpers make crew tests deterministic and readable:

- ``role_router``: a ScriptedLLM script that answers by the calling agent's ROLE (read from the system prompt),
  so a test scripts each agent separately and does not depend on the call order between agents.
- ``calls_by_role``: who was called how often, with prompt sizes - the cost picture of a run.
- ``assert_handed_off``: proof that one agent's output reached another agent's prompt (context passing).
- ``chain_success`` / ``chain_success_with_checks``: the arithmetic of error compounding in a pipeline of agents,
  and how a check with retries changes it.
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable

from llm_fake import count_tokens

ROLE_RE = re.compile(r"^You are (.+?)\.$")


def role_of(system: str) -> str:
    """Given: the role named on the system prompt's first line "You are {role}." ('' if there is none)."""
    first = system.splitlines()[0] if system else ""
    m = ROLE_RE.match(first)
    return m.group(1) if m else ""


def role_router(replies: dict[str, list[Any]]) -> Callable[[Any], Any]:
    """Return a ScriptedLLM script function that answers each request from ``replies[role]`` in order.

    The role comes from ``role_of(request.system)``. Each role's list is consumed front to back (do not mutate
    the caller's lists). Raise AssertionError naming the role when the role has no entry or its replies are used
    up - an unexpected call is a test failure, not a silent default.
    """
    raise NotImplementedError


def _prompt_text(request: Any) -> str:
    parts = [request.system]
    for m in request.messages:
        content = m["content"]
        if isinstance(content, str):
            parts.append(content)
        else:
            parts.extend(str(b.get("text", b.get("content", ""))) for b in content)
    return "\n".join(parts)


def calls_by_role(calls: list[Any]) -> dict[str, dict[str, int]]:
    """Summarise recorded requests per role: {role: {"calls": n, "prompt_tokens": total}}.

    The role comes from ``role_of``; prompt tokens are ``count_tokens`` of the system prompt plus every message's
    text (string content, or the "text"/"content" of each block). Keys appear in first-call order.
    """
    raise NotImplementedError


def assert_handed_off(calls: list[Any], text: str, to_role: str) -> int:
    """Return the index of the first recorded call by ``to_role`` whose prompt (system + messages) contains
    ``text``. Raise AssertionError if there is none, saying whether ``to_role`` was called at all."""
    raise NotImplementedError


def chain_success(step_probs: list[float]) -> float:
    """Probability that every step of a pipeline is right, if steps fail independently: the product.
    Raise ValueError for an empty list or a probability outside [0, 1]."""
    raise NotImplementedError


def chain_success_with_checks(p: float, steps: int, catch_rate: float, retries: int) -> float:
    """Probability that all ``steps`` steps end right when each step is right with probability ``p`` and a check
    after it catches a wrong output with probability ``catch_rate`` and asks again, up to ``retries`` times.

    One step: q(0) = p; q(r) = p + (1 - p) * catch_rate * q(r - 1). The chain: q(retries) ** steps.
    Raise ValueError for probabilities outside [0, 1], steps < 1 or retries < 0.
    """
    raise NotImplementedError
