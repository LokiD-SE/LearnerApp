"""The host's model loop over MCP tools: the model proposes, the host checks, the MCP server executes.

Exercise: fill in every function that raises NotImplementedError; the tests
in tests/mcp/test_client_loop.py say what each must do. Reference solution: solutions/mcp/client_loop.py. ``llm`` is anything with ``create(messages=..., system=..., max_tokens=..., tools=...)``
returning a reply with ``content``, ``stop_reason``, ``text`` and ``tool_calls`` (``ScriptedLLM`` in tests).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from mcp.client_rpc import McpError, RequestTimeout

Approve = Callable[[str, dict], bool]
AnswerInput = Callable[[str, dict], dict]


@dataclass
class LoopResult:
    answer: str
    model_calls: int
    tool_log: list[dict] = field(default_factory=list)  # one entry per tool call: name, arguments, is_error, text
    stopped: str = "end_turn"  # "end_turn" | "max_turns"


def result_to_text(result: dict) -> str:
    """The text a model sees for one ``tools/call`` result.

    Text blocks are joined with newlines. Other blocks become a short marker: ``[image image/png]``,
    ``[audio audio/wav]``, ``[resource_link <uri>]``, ``[resource <uri>]``. With no content at all,
    ``structuredContent`` (any JSON value) is serialised with ``json.dumps``; with neither, ``(no content)``."""
    raise NotImplementedError("TODO: turn the content blocks (or structuredContent) into one string for the model.")


def call_tool_with_input(client, name: str, arguments: dict, answer_input: AnswerInput, max_rounds: int = 3, timeout: float = 5.0) -> dict:
    """``tools/call`` with multi round-trip requests (MRTR).

    While the result is ``input_required``: answer every input request with ``answer_input(key, request)``,
    then retry the same call with ``inputResponses`` and, only if the server sent one, the exact
    ``requestState``. Each retry is a new request (``client.request`` gives it a new id). More than
    ``max_rounds`` retries raise RuntimeError."""
    raise NotImplementedError("TODO: call tools/call; while input_required, answer the inputRequests and retry.")


def run_host_loop(
    llm,
    question: str,
    tools: list[dict],
    routes: dict[str, tuple[Any, str]],
    approve: Approve,
    answer_input: AnswerInput,
    system: str = "",
    max_turns: int = 5,
    timeout: float = 5.0,
) -> LoopResult:
    """Runs the model with MCP tools until it answers or ``max_turns`` model calls are used.

    ``routes`` maps the provider tool name the model sees to ``(client, MCP tool name)``. For each tool call:
    an unknown name, a refused approval, a protocol error (McpError), a timeout or a result with
    ``isError: true`` all go back to the model as a ``tool_result`` with ``is_error: true`` and a short reason;
    a good result goes back with ``is_error: false``. The assistant turn is appended unchanged, followed by one
    user message holding every tool result."""
    raise NotImplementedError("TODO: call the model, run each tool call through _run_one, append the turns, repeat.")


def _run_one(name: str, arguments: dict, routes, approve: Approve, answer_input: AnswerInput, timeout: float) -> tuple[str, bool]:
    raise NotImplementedError("TODO: route, approve, call the tool and map every failure to (reason, True).")
