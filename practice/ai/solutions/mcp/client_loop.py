"""The host's model loop over MCP tools: the model proposes, the host checks, the MCP server executes.

Reference solution. ``llm`` is anything with ``create(messages=..., system=..., max_tokens=..., tools=...)``
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
    parts: list[str] = []
    for block in result.get("content") or []:
        kind = block.get("type")
        if kind == "text":
            parts.append(block.get("text", ""))
        elif kind in ("image", "audio"):
            parts.append(f"[{kind} {block.get('mimeType', 'unknown')}]")
        elif kind == "resource_link":
            parts.append(f"[resource_link {block.get('uri')}]")
        elif kind == "resource":
            parts.append(f"[resource {block.get('resource', {}).get('uri')}]")
        else:
            parts.append(f"[{kind}]")
    if parts:
        return "\n".join(parts)
    if "structuredContent" in result:
        return json.dumps(result["structuredContent"])
    return "(no content)"


def call_tool_with_input(client, name: str, arguments: dict, answer_input: AnswerInput, max_rounds: int = 3, timeout: float = 5.0) -> dict:
    """``tools/call`` with multi round-trip requests (MRTR).

    While the result is ``input_required``: answer every input request with ``answer_input(key, request)``,
    then retry the same call with ``inputResponses`` and, only if the server sent one, the exact
    ``requestState``. Each retry is a new request (``client.request`` gives it a new id). More than
    ``max_rounds`` retries raise RuntimeError."""
    params: dict[str, Any] = {"name": name, "arguments": arguments}
    for _ in range(max_rounds + 1):
        result = client.request("tools/call", params, timeout=timeout)
        if result.get("resultType", "complete") != "input_required":
            return result
        responses = {key: answer_input(key, req) for key, req in (result.get("inputRequests") or {}).items()}
        params = {"name": name, "arguments": arguments, "inputResponses": responses}
        if "requestState" in result:
            params["requestState"] = result["requestState"]
    raise RuntimeError(f"{name}: still input_required after {max_rounds} retries")


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
    messages: list[dict] = [{"role": "user", "content": question}]
    log: list[dict] = []
    calls = 0
    reply = None
    while calls < max_turns:
        reply = llm.create(messages=messages, system=system, max_tokens=512, tools=tools)
        calls += 1
        if not reply.tool_calls:
            return LoopResult(reply.text, calls, log)
        messages.append({"role": "assistant", "content": reply.content})
        results = []
        for call in reply.tool_calls:
            text, is_error = _run_one(call["name"], call["input"], routes, approve, answer_input, timeout)
            log.append({"name": call["name"], "arguments": call["input"], "is_error": is_error, "text": text})
            results.append({"type": "tool_result", "tool_use_id": call["id"], "content": text, "is_error": is_error})
        messages.append({"role": "user", "content": results})
    return LoopResult(reply.text if reply else "", calls, log, stopped="max_turns")


def _run_one(name: str, arguments: dict, routes, approve: Approve, answer_input: AnswerInput, timeout: float) -> tuple[str, bool]:
    route = routes.get(name)
    if route is None:
        return f"Unknown tool {name!r}. Use one of: {', '.join(sorted(routes))}.", True
    client, mcp_name = route
    if not approve(name, arguments):
        return f"The user did not approve {name}; do not retry it.", True
    try:
        result = call_tool_with_input(client, mcp_name, arguments, answer_input, timeout=timeout)
    except McpError as exc:
        return f"Protocol error {exc.code}: {exc.message}", True
    except RequestTimeout:
        return f"{name} timed out after {timeout}s and was cancelled.", True
    return result_to_text(result), bool(result.get("isError", False))
