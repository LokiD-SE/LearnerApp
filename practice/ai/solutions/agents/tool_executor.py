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
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.tool_registry import ToolRegistry, validate_input


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
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn, **kwargs).result(timeout=timeout)
    except FutureTimeout:
        raise ToolTimeout(f"timed out after {timeout:g}s") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def serialise(value: Any, limit: int) -> str:
    """A tool's return value as the string the model reads: strings as-is, anything else as sorted JSON.

    Longer than ``limit`` characters: cut to ``limit`` and append ``" ... [truncated N chars]"``.
    """
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    if len(text) > limit:
        return text[:limit] + f" ... [truncated {len(text) - limit} chars]"
    return text


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
    call_id, name, args = call["id"], call["name"], call.get("input")
    available = ", ".join(sorted(policy.allowed))
    if name not in policy.allowed:
        return tool_result(call_id, f"Error: tool '{name}' is not allowed here. Available tools: {available}.", True)
    tool = registry.get(name)
    if tool is None:
        return tool_result(call_id, f"Error: unknown tool '{name}'. Available tools: {available}.", True)
    errors = validate_input(tool.input_schema, args)
    if errors:
        message = f"Error: invalid input for {name}: " + "; ".join(errors) + ". Fix the input and call the tool again."
        return tool_result(call_id, message, True)
    try:
        value = run(tool.fn, args, policy.timeout)
    except ToolTimeout as exc:
        return tool_result(call_id, f"Error: {name} {exc}. The service may be slow; try again later or tell the user.", True)
    except Exception as exc:  # noqa: BLE001 - every tool failure must reach the model, not crash the loop
        return tool_result(call_id, f"Error: {name} failed: {type(exc).__name__}: {exc}", True)
    return tool_result(call_id, serialise(value, policy.max_result_chars))
