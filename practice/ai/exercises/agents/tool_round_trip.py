"""The tool-use round trip: request with tools -> tool_use -> run the tools -> tool_result -> final answer.

Message shapes used here (modelled on Anthropic's Messages API, documented 14 November 2026):

- the model's turn is appended unchanged as ``{"role": "assistant", "content": reply.content}`` - its
  ``tool_use`` blocks must stay in the history so each result can point back at its call;
- every result of that turn goes back in ONE user message, results first and in call order:
  ``{"role": "user", "content": [tool_result, tool_result, ...]}``.

OpenAI's Responses API carries the same information as ``function_call`` items (``call_id``, ``name``,
JSON-string ``arguments``) and ``function_call_output`` items (``call_id``, ``output``).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor  # noqa: F401 - you will need it
from dataclasses import dataclass
from typing import Any, Callable

from agents.tool_executor import ExecutionPolicy, execute_call
from agents.tool_registry import ToolRegistry


class ToolLoopError(RuntimeError):
    """The model kept calling tools past ``max_turns`` without a final answer."""


@dataclass
class LoopResult:
    text: str
    stop_reason: str
    turns: int  # model calls made
    tool_calls: list[str]  # names of every tool called, in order
    messages: list[dict[str, Any]]  # the full transcript, including tool_use and tool_result turns


def execute_all(
    registry: ToolRegistry,
    calls: list[dict[str, Any]],
    policy: ExecutionPolicy,
    max_workers: int = 4,
    executor: Callable[..., dict[str, Any]] = execute_call,
) -> list[dict[str, Any]]:
    """Run all ``tool_use`` blocks of one turn concurrently; return their results in the calls' order."""
    # Starting draft: one call after another - a turn with three slow lookups takes three times as long.
    return [executor(registry, call, policy) for call in calls]


def run_tool_loop(
    llm: Any,
    registry: ToolRegistry,
    messages: list[dict[str, Any]],
    policy: ExecutionPolicy,
    system: str = "",
    max_turns: int = 5,
    max_tokens: int = 512,
) -> LoopResult:
    """Drive the round trip until the model stops asking for tools.

    Each turn: ``llm.create(system=..., messages=..., tools=<allowed definitions>, max_tokens=...)``; append the
    assistant turn; if ``stop_reason != "tool_use"`` return a ``LoopResult``; otherwise run every call with
    ``execute_all`` and append one user message holding all the results. Raise ``ToolLoopError`` after
    ``max_turns`` model calls that all asked for tools. The caller's ``messages`` list is not modified.
    """
    # Starting draft: appends to the caller's list, offers every tool, runs only the FIRST tool call,
    # never stops a model that keeps asking for tools (it gives up silently after 10 calls).
    history = messages
    called: list[str] = []
    for turn in range(1, 11):
        reply = llm.create(system=system, messages=history, tools=registry.definitions(), max_tokens=max_tokens)
        if reply.stop_reason != "tool_use":
            history.append({"role": "assistant", "content": reply.content})
            return LoopResult(reply.text, reply.stop_reason, turn, called, history)
        call = reply.tool_calls[0]
        called.append(call["name"])
        history.append({"role": "assistant", "content": [call]})
        history.append({"role": "user", "content": [execute_call(registry, call, policy)]})
    return LoopResult("", "tool_use", 10, called, history)
