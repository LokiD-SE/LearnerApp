"""Run one tool call safely and turn *every* outcome into a tool_result the model can read.

The model's tool call is untrusted input: the name may be unknown or not allowed in this session, the input
may break the schema, the function may raise or hang. None of these may crash the agent loop or leak a stack
trace; each becomes a ``tool_result`` block with ``is_error: true`` and a message that says what to fix.

Block shapes (modelled on Anthropic's documented ``tool_use`` / ``tool_result`` blocks):

    call   = {"type": "tool_use", "id": "call_1", "name": "get_transaction", "input": {...}}
    result = {"type": "tool_result", "tool_use_id": "call_1", "content": "<string>", "is_error": False}
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor  # noqa: F401 - you will need these
from concurrent.futures import TimeoutError as FutureTimeout  # noqa: F401
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.tool_registry import ToolRegistry, validate_input  # noqa: F401


class ToolTimeout(Exception):
    """The tool did not finish within the policy's timeout."""


@dataclass(frozen=True)
class ExecutionPolicy:
    """What this session may run. ``allowed`` is an allow-list of tool names - nothing else runs."""

    allowed: frozenset[str] = field(default_factory=frozenset)
    timeout: float = 5.0
    max_result_chars: int = 2000


def tool_result(call_id: str, content: str, is_error: bool = False) -> dict[str, Any]:
    return {"type": "tool_result", "tool_use_id": call_id, "content": content, "is_error": is_error}


def run_with_timeout(fn: Callable[..., Any], kwargs: dict[str, Any], timeout: float) -> Any:
    """Call ``fn(**kwargs)`` in a worker thread; raise ``ToolTimeout`` if it takes longer than ``timeout``.

    Python cannot kill a thread: a timed-out tool keeps running in the background. So the tool itself should
    also bound its own I/O (an HTTP timeout, a database statement timeout) - this is the outer guard.
    """
    raise NotImplementedError


def serialise(value: Any, limit: int) -> str:
    """A tool's return value as the string the model reads: strings as-is, anything else as sorted JSON.

    Longer than ``limit`` characters: cut to ``limit`` and append ``" ... [truncated N chars]"``.
    """
    return json.dumps(value)  # starting draft: re-encodes strings, unsorted keys, no length limit


def execute_call(
    registry: ToolRegistry,
    call: dict[str, Any],
    policy: ExecutionPolicy,
    run: Callable[[Callable[..., Any], dict[str, Any], float], Any] = run_with_timeout,
) -> dict[str, Any]:
    """Execute one ``tool_use`` block and return its ``tool_result`` block. Never raises for tool problems.

    In order: the name must be in ``policy.allowed`` (otherwise "not allowed", naming the allowed tools),
    must be registered ("unknown tool"), the input must pass ``validate_input`` (all errors listed), then
    ``run(tool.fn, input, policy.timeout)``. A ``ToolTimeout`` or any other exception becomes an error result
    with the exception type and message - never a traceback. Success: ``serialise(value, max_result_chars)``.
    """
    # Starting draft: trusts the model completely - no allow-list, no validation, no timeout, and any
    # exception (or an unknown name) crashes the whole agent loop.
    tool = registry.get(call["name"])
    return tool_result(call["id"], serialise(tool.fn(**call["input"]), policy.max_result_chars))
