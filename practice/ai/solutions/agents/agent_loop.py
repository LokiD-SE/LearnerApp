"""A ReAct-style agent loop with stop conditions, tool-error recovery and a step trace - lesson
agent-loops-and-workflow-patterns.

The loop: call the model with the conversation and the tool specs; if it asks for tools, run them, send the results
back and call it again; stop when it answers - or when a guard fires first.

Message shapes used in this project (modelled on Anthropic's documented tool_use / tool_result blocks; see the
lesson for how OpenAI's shapes differ):
- the model's turn is appended as ``{"role": "assistant", "content": reply.content}`` (its text and tool_use blocks);
- the results go back in ONE user message, one block per tool call, in call order:
  ``{"role": "user", "content": [{"type": "tool_result", "tool_use_id": id, "content": str, "is_error": bool}]}``.

Stop conditions, checked in this order:
- ``"model_error"``  - the client raised (wrap it in a retrying client first; see the LLM APIs lesson);
- ``"done"``         - stop reason ``end_turn``: the reply text is the answer;
- ``"stopped"``      - any other non-tool stop reason (``max_tokens``, ``refusal``...): no answer;
- ``"budget"``       - input + output tokens so far exceed ``max_total_tokens`` (checked before running tools);
- ``"no_progress"``  - the same tool with the same input requested more than ``max_repeats`` times;
- ``"tool_errors"``  - ``max_consecutive_errors`` steps in a row where every tool call failed;
- ``"max_steps"``    - ``max_steps`` model calls made without an answer.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentResult:
    status: str
    answer: str | None
    steps: int  # model calls made
    input_tokens: int
    output_tokens: int
    trace: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def call_key(name: str, tool_input: dict[str, Any]) -> str:
    """A canonical key for one tool call: the name plus its input as JSON with sorted keys."""
    return name + " " + json.dumps(tool_input, sort_keys=True)


def run_tool(tools: dict[str, Callable[..., Any]], name: str, tool_input: dict[str, Any]) -> tuple[str, bool]:
    """Run one tool call and return ``(content, is_error)``. Never raises.

    - Unknown tool: ``("Unknown tool 'x'. Available tools: a, b.", True)`` with the names sorted.
    - The tool raises: ``("<ExceptionClass>: <message>", True)`` - the model reads it and can correct itself.
    - Otherwise: ``(str(return value), False)``.
    """
    if name not in tools:
        return f"Unknown tool {name!r}. Available tools: {', '.join(sorted(tools))}.", True
    try:
        return str(tools[name](**tool_input)), False
    except Exception as error:  # noqa: BLE001 - any tool failure becomes data for the model
        return f"{type(error).__name__}: {error}", True


def run_agent(
    client: Any,
    task: str,
    tools: dict[str, Callable[..., Any]],
    tool_specs: list[dict[str, Any]] | None = None,
    *,
    system: str = "",
    max_steps: int = 8,
    max_total_tokens: int = 4000,
    max_repeats: int = 2,
    max_consecutive_errors: int = 3,
    max_tokens: int = 512,
    clock: Callable[[], float] = time.monotonic,
) -> AgentResult:
    """Run the agent loop for ``task`` and return an AgentResult (never raises for model or tool failures).

    Trace events (dicts, in order):
    - ``{"type": "model", "step": n, "stop_reason", "input_tokens", "output_tokens", "text",
      "tool_calls": [{"id", "name", "input"}]}`` after each model call (n counts from 1);
    - ``{"type": "tool", "step": n, "id", "name", "input", "is_error", "output", "ms"}`` per tool run, where
      ``output`` is the first 200 characters and ``ms`` is the clock difference in milliseconds, rounded to 1 place;
    - ``{"type": "error", "step": n, "error": message}`` when the client raises;
    - ``{"type": "stop", "step": steps, "status": status}`` always last.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    trace: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    steps = input_tokens = output_tokens = failing_steps = 0

    def finish(status: str, answer: str | None = None, error: str | None = None) -> AgentResult:
        trace.append({"type": "stop", "step": steps, "status": status})
        return AgentResult(status, answer, steps, input_tokens, output_tokens, trace, messages, error)

    while True:
        if steps >= max_steps:
            return finish("max_steps")
        steps += 1
        try:
            reply = client.create(
                messages=messages, system=system, max_tokens=max_tokens, tools=list(tool_specs or [])
            )
        except Exception as error:  # noqa: BLE001
            message = f"{type(error).__name__}: {error}"
            trace.append({"type": "error", "step": steps, "error": message})
            return finish("model_error", error=message)
        input_tokens += reply.input_tokens
        output_tokens += reply.output_tokens
        calls = reply.tool_calls
        trace.append(
            {
                "type": "model",
                "step": steps,
                "stop_reason": reply.stop_reason,
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
                "text": reply.text,
                "tool_calls": [{"id": c["id"], "name": c["name"], "input": c["input"]} for c in calls],
            }
        )
        messages.append({"role": "assistant", "content": reply.content})
        if reply.stop_reason != "tool_use":
            if reply.stop_reason == "end_turn":
                return finish("done", reply.text)
            return finish("stopped")
        if input_tokens + output_tokens > max_total_tokens:
            return finish("budget")

        results, errors = [], 0
        for call in calls:
            key = call_key(call["name"], call["input"])
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > max_repeats:
                return finish("no_progress")
            start = clock()
            content, is_error = run_tool(tools, call["name"], call["input"])
            trace.append(
                {
                    "type": "tool",
                    "step": steps,
                    "id": call["id"],
                    "name": call["name"],
                    "input": call["input"],
                    "is_error": is_error,
                    "output": content[:200],
                    "ms": round((clock() - start) * 1000, 1),
                }
            )
            errors += is_error
            results.append({"type": "tool_result", "tool_use_id": call["id"], "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})
        failing_steps = failing_steps + 1 if errors == len(calls) else 0
        if failing_steps >= max_consecutive_errors:
            return finish("tool_errors")


def format_trace(trace: list[dict[str, Any]]) -> str:
    """One line per trace event - what a tester reads (and diffs) after a run."""
    lines = []
    for e in trace:
        if e["type"] == "model":
            calls = ", ".join(f"{c['name']}({json.dumps(c['input'], sort_keys=True)})" for c in e["tool_calls"])
            what = f"-> {calls}" if calls else f"-> {e['text']!r}"
            lines.append(f"step {e['step']} model {e['stop_reason']:<8} in={e['input_tokens']:<4} out={e['output_tokens']:<3} {what}")
        elif e["type"] == "tool":
            flag = "ERROR" if e["is_error"] else "ok"
            lines.append(f"step {e['step']} tool  {e['name']:<12} {flag:<5} {e['ms']:>5} ms  {e['output'][:60]!r}")
        elif e["type"] == "error":
            lines.append(f"step {e['step']} error {e['error']}")
        else:
            lines.append(f"stop: {e['status']} after {e['step']} model calls")
    return "\n".join(lines)
