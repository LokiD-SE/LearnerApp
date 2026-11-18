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
    raise NotImplementedError


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
    raise NotImplementedError


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
