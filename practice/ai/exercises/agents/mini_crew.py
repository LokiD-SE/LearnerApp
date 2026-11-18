"""A mini crew in plain Python - lesson multi-agent-systems-crewai.

The names follow CrewAI's (``Agent``, ``Task``, ``Crew``, ``Process``, ``TaskOutput``, ``CrewOutput``,
``kickoff``) so the mapping to the real library is easy to see, but this is NOT CrewAI and copies none of its
code. Each agent is one model call per attempt (CrewAI agents run a tool loop of up to ``max_iter`` steps).

- ``Agent``: a role, a goal and a backstory that become the system prompt, plus the client (``llm``) it calls.
- ``Task``: a description, the expected output, the agent, optional ``context`` tasks and optional guardrails.
- ``Crew.kickoff(inputs)``: fills ``{placeholders}``, runs the tasks in order (``Process.sequential``), passes
  context, runs each task's guardrails (retrying with the error fed back to the agent) and adds up token usage.

The prompt layout (system text, ``<context>`` blocks, the retry message) is this lesson's design, not CrewAI's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

Guardrail = Callable[["TaskOutput"], tuple[bool, Any]]


class Process(Enum):
    sequential = "sequential"
    hierarchical = "hierarchical"


class GuardrailError(Exception):
    """A task's output still failed a guardrail after ``guardrail_max_retries`` retries."""

    def __init__(self, task_name: str, error: str, attempts: int):
        super().__init__(f"task {task_name!r} failed its guardrail after {attempts} attempts: {error}")
        self.task_name = task_name
        self.error = error
        self.attempts = attempts


@dataclass
class Agent:
    role: str
    goal: str
    backstory: str
    llm: Any = None  # anything with .create(messages=..., system=..., max_tokens=..., temperature=...)
    allow_delegation: bool = False
    max_tokens: int = 300


@dataclass
class Task:
    name: str
    description: str
    expected_output: str
    agent: Agent | None = None
    context: list["Task"] | None = None  # None: the previous task's output; []: no context
    guardrails: list[Guardrail] = field(default_factory=list)
    guardrail_max_retries: int = 3


@dataclass
class TaskOutput:
    name: str
    agent: str  # the role of the agent that produced it
    raw: str
    value: Any = None  # what the last guardrail returned on success (raw when there are no guardrails)
    attempts: int = 1


@dataclass
class CrewOutput:
    raw: str
    tasks_output: list[TaskOutput]
    token_usage: dict[str, int]


def agent_system_prompt(agent: Agent) -> str:
    """The agent's system prompt: exactly "You are {role}.\\nYour goal: {goal}\\n{backstory}"."""
    raise NotImplementedError


def task_prompt(task: Task, context: list[TaskOutput]) -> str:
    """The user message for a task.

    "Task: {description}\\n\\nExpected output: {expected_output}", then - only when there is context - a blank
    line, the line "Context from earlier tasks:" and one block per context output:
    '<context task="{name}" agent="{agent}">\\n{raw}\\n</context>', blocks separated by a newline.
    """
    raise NotImplementedError


def fill_inputs(text: str, inputs: dict[str, Any]) -> str:
    """Replace each {name} with inputs[name]; raise KeyError naming a placeholder that has no input."""
    raise NotImplementedError


def run_task(task: Task, context: list[TaskOutput], usage: dict[str, int]) -> TaskOutput:
    """Run one task with its agent's llm at temperature 0, then its guardrails.

    Guardrails run in order; each receives a TaskOutput whose ``value`` is what the previous one returned. If one
    returns (False, error), append the rejected answer as an assistant message and a user message
    "Your answer failed a check: {error}\\nReturn a corrected answer." and call the agent again. Allow
    ``guardrail_max_retries`` retries, then raise GuardrailError. Add each reply's input/output tokens to ``usage``
    ("prompt_tokens", "completion_tokens", "calls").
    """
    raise NotImplementedError


@dataclass
class Crew:
    agents: list[Agent]
    tasks: list[Task]
    process: Process = Process.sequential

    def validate(self) -> None:
        """Raise ValueError if: there are no tasks; a task has no agent or an agent not in ``agents``; two tasks
        share a name; or a task's context names a task that is not EARLIER in the list (no forward references).
        Only Process.sequential is supported here (see crew_manager for the hierarchical process)."""
        raise NotImplementedError

    def kickoff(self, inputs: dict[str, Any] | None = None) -> CrewOutput:
        """Validate, then run every task in order and return a CrewOutput.

        Each task's description and expected output are filled from ``inputs``. Context: ``None`` means the
        previous task's output (none for the first task); a list means exactly those tasks' outputs, in list order.
        ``raw`` is the last task's raw output; ``token_usage`` has prompt_tokens, completion_tokens, total_tokens
        (their sum) and calls.
        """
        raise NotImplementedError
