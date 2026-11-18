"""The hierarchical process in plain Python - lesson multi-agent-systems-crewai.

A manager model gets each task, delegates pieces of it to coworkers through a ``delegate_work`` tool, reads what
comes back and writes the task's final answer itself. This mirrors CrewAI's ``Process.hierarchical`` (a manager
that delegates, reviews and validates) and its "Delegate work to coworker(task, context, coworker)" tool, but it
is NOT CrewAI: the prompts, the tool schema and the tool-result message shape are this lesson's design.

Tool results go back as a user message with ``tool_result`` blocks - the shape of Anthropic's Messages API
(``tool_use_id``, ``content``, ``is_error``). OpenAI's Responses API uses a ``function_call_output`` item with a
``call_id`` instead; the idea is the same.

Coordination limits a single agent does not need: a delegation budget per task, a turn limit, an error (not a
crash) for an unknown coworker or a coworker whose call fails, and coworkers that cannot delegate further.
"""

from __future__ import annotations

from typing import Any

from agents.mini_crew import Agent, CrewOutput, GuardrailError, Task, TaskOutput
from llm_fake import LLMError

DELEGATE_TOOL = {
    "name": "delegate_work",
    "description": "Give one well-defined piece of work to a coworker and get their answer back.",
    "input_schema": {
        "type": "object",
        "properties": {
            "coworker": {"type": "string", "description": "The coworker's role, exactly as listed."},
            "task": {"type": "string", "description": "What the coworker must do, with the output you expect."},
            "context": {"type": "string", "description": "Everything the coworker needs to know; they see nothing else."},
        },
        "required": ["coworker", "task", "context"],
    },
}


def manager_system_prompt(coworkers: list[Agent]) -> str:
    """Given: the manager's system prompt, listing every coworker's role and goal."""
    lines = "\n".join(f"- {a.role}: {a.goal}" for a in coworkers)
    return (
        "You are Crew Manager.\nYour goal: split the task into pieces, delegate each piece to the right coworker "
        "with delegate_work, check what comes back, and write the final answer yourself.\n"
        f"Coworkers:\n{lines}"
    )


def worker_messages(task: str, context: str) -> list[dict[str, Any]]:
    """Given: the single user message a coworker receives for a delegated piece of work."""
    return [{"role": "user", "content": f"Task: {task}\n\nContext:\n{context}"}]


def manager_task_prompt(task: Task, context: list[TaskOutput]) -> str:
    """Given: the manager's first user message for a task (same layout as mini_crew.task_prompt)."""
    text = f"Task: {task.description}\n\nExpected output: {task.expected_output}"
    if context:
        blocks = "\n".join(f'<context task="{c.name}" agent="{c.agent}">\n{c.raw}\n</context>' for c in context)
        text += f"\n\nContext from earlier tasks:\n{blocks}"
    return text


def _add_usage(usage: dict[str, int], reply: Any) -> None:
    usage["prompt_tokens"] += reply.input_tokens
    usage["completion_tokens"] += reply.output_tokens
    usage["calls"] += 1


def delegate(call: dict[str, Any], coworkers: list[Agent], usage: dict[str, int]) -> tuple[str, bool, str | None]:
    """Run one delegate_work call. Returns (result text, is_error, coworker role or None).

    - The coworker is matched by role, ignoring case and surrounding spaces. No match: return
      ("unknown coworker '{name}'; choose one of: {role}, {role}", True, None) - the manager can correct itself.
    - A missing or empty "task" or "context": return ("delegate_work needs coworker, task and context", True, None).
    - Otherwise call the coworker's llm once at temperature 0 with its own system prompt
      "You are {role}.\\nYour goal: {goal}\\n{backstory}", the messages from ``worker_messages`` and its
      ``max_tokens``, and NO tools (coworkers cannot delegate further). Add the reply's tokens to ``usage``.
    - If that call raises LLMError: return ("coworker {role} failed: {error}", True, role).
    - Success: (reply text, False, role).
    """
    args = call.get("input", {})
    name = str(args.get("coworker", ""))
    match = [a for a in coworkers if a.role.strip().casefold() == name.strip().casefold()]
    if not match:
        roles = ", ".join(a.role for a in coworkers)
        return f"unknown coworker '{name}'; choose one of: {roles}", True, None
    worker = match[0]
    if not args.get("task") or not args.get("context"):
        return "delegate_work needs coworker, task and context", True, None
    try:
        reply = worker.llm.create(
            messages=worker_messages(args["task"], args["context"]),
            system=f"You are {worker.role}.\nYour goal: {worker.goal}\n{worker.backstory}",
            max_tokens=worker.max_tokens,
            temperature=0.0,
        )
    except LLMError as exc:
        return f"coworker {worker.role} failed: {exc}", True, worker.role
    _add_usage(usage, reply)
    return reply.text, False, worker.role


def run_manager_task(
    manager_llm: Any,
    task: Task,
    coworkers: list[Agent],
    context: list[TaskOutput],
    usage: dict[str, int],
    trace: list[dict[str, Any]],
    max_delegations: int = 4,
    max_turns: int = 8,
) -> TaskOutput:
    """The manager loop for one task.

    Each turn calls ``manager_llm.create`` (system = manager_system_prompt, tools = [DELEGATE_TOOL],
    temperature 0, max_tokens 400) and adds the tokens to ``usage``.

    - stop_reason "tool_use": append {"role": "assistant", "content": reply.content}; answer EVERY tool call in
      one user message of blocks {"type": "tool_result", "tool_use_id": id, "content": text, "is_error": bool}.
      A call to any other tool name is an error result "unknown tool '{name}'". Each delegate_work call counts
      toward ``max_delegations`` (failed ones too); once the budget is used, answer further calls with the error
      "delegation budget of {n} used up; give your final answer now" without running them. Append one trace entry
      per call: {"task": task.name, "coworker": role or the requested name, "is_error": bool}.
    - Otherwise the reply text is the task's answer: run the task's guardrails as mini_crew does (feedback
      message "Your answer failed a check: {error}\\nReturn a corrected answer.", ``guardrail_max_retries``
      retries, then GuardrailError). The TaskOutput's agent is "Crew Manager".
    - More than ``max_turns`` manager calls for one task: raise RuntimeError.
    """
    messages: list[dict[str, Any]] = [{"role": "user", "content": manager_task_prompt(task, context)}]
    system = manager_system_prompt(coworkers)
    delegations = 0
    attempts = 0
    for _turn in range(max_turns):
        reply = manager_llm.create(
            messages=messages, system=system, max_tokens=400, temperature=0.0, tools=[DELEGATE_TOOL]
        )
        _add_usage(usage, reply)
        if reply.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": reply.content})
            results = []
            for call in reply.tool_calls:
                requested = str(call.get("input", {}).get("coworker", ""))
                if call["name"] != DELEGATE_TOOL["name"]:
                    text, is_error, role = f"unknown tool '{call['name']}'", True, None
                elif delegations >= max_delegations:
                    text, is_error, role = (
                        f"delegation budget of {max_delegations} used up; give your final answer now",
                        True,
                        None,
                    )
                else:
                    delegations += 1
                    text, is_error, role = delegate(call, coworkers, usage)
                trace.append({"task": task.name, "coworker": role or requested, "is_error": is_error})
                results.append({"type": "tool_result", "tool_use_id": call["id"], "content": text, "is_error": is_error})
            messages.append({"role": "user", "content": results})
            continue
        attempts += 1
        output = TaskOutput(task.name, "Crew Manager", reply.text, reply.text, attempts)
        error = None
        for guardrail in task.guardrails:
            ok, result = guardrail(output)
            if not ok:
                error = str(result)
                break
            output.value = result
        if error is None:
            return output
        if attempts > task.guardrail_max_retries:
            raise GuardrailError(task.name, error, attempts)
        messages += [
            {"role": "assistant", "content": reply.text},
            {"role": "user", "content": f"Your answer failed a check: {error}\nReturn a corrected answer."},
        ]
    raise RuntimeError(f"manager did not finish task {task.name!r} in {max_turns} turns")


def kickoff_hierarchical(
    agents: list[Agent],
    tasks: list[Task],
    manager_llm: Any,
    inputs: dict[str, Any] | None = None,
    max_delegations: int = 4,
    max_turns: int = 8,
) -> tuple[CrewOutput, list[dict[str, Any]]]:
    """Run every task through the manager, in order. Returns (CrewOutput, trace).

    Raise ValueError if ``manager_llm`` is None (a hierarchical crew needs a manager) or there are no tasks. A
    task's own ``agent`` is ignored - the manager decides who works on what. Inputs fill {placeholders} in each
    description and expected output; context follows the mini_crew rule (None: previous output; list: those
    tasks). token_usage has prompt_tokens, completion_tokens, total_tokens and calls (manager AND coworkers).
    """
    if manager_llm is None:
        raise ValueError("a hierarchical crew needs a manager llm")
    if not tasks:
        raise ValueError("a crew needs at least one task")
    inputs = inputs or {}
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    trace: list[dict[str, Any]] = []
    outputs: dict[str, TaskOutput] = {}
    done: list[TaskOutput] = []
    for task in tasks:
        filled = Task(
            task.name,
            task.description.format_map(inputs),
            task.expected_output.format_map(inputs),
            None,
            task.context,
            task.guardrails,
            task.guardrail_max_retries,
        )
        context = done[-1:] if task.context is None else [outputs[t.name] for t in task.context]
        out = run_manager_task(manager_llm, filled, agents, context, usage, trace, max_delegations, max_turns)
        outputs[task.name] = out
        done.append(out)
    usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
    return CrewOutput(done[-1].raw, done, usage), trace
