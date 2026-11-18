"""Checks exercises/agents/crew_manager.py - lesson multi-agent-systems-crewai.

The manager is a ScriptedLLM whose script mixes delegate_work tool calls and a final answer; each coworker has
its own ScriptedLLM. The SandPay chargeback case is fictional.
"""

import pytest

from agents.crew_manager import DELEGATE_TOOL, delegate, kickoff_hierarchical, manager_system_prompt, run_manager_task
from agents.mini_crew import Agent, GuardrailError, Task
from llm_fake import OverloadedError, ScriptedLLM

pytestmark = pytest.mark.exercise


def coworkers(collector_script=(), analyst_script=()):
    collector = Agent("Evidence Collector", "List the evidence with ids", "Never guess.", ScriptedLLM(list(collector_script)))
    analyst = Agent("Fraud Analyst", "Decide contest or accept", "Weigh the evidence.", ScriptedLLM(list(analyst_script)))
    return [collector, analyst]


def call(coworker, task="Do it", context="Case CB-2041"):
    return {"tool": "delegate_work", "input": {"coworker": coworker, "task": task, "context": context}}


def new_usage():
    return {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}


TASK = Task("investigate", "Investigate {case}", "contest or accept, with evidence ids")


def test_delegate_runs_the_coworker_with_its_own_prompt_and_no_tools():
    team = coworkers(["EV-1 delivery scan"])
    usage = new_usage()
    block = {"type": "tool_use", "id": "call_1", "name": "delegate_work",
             "input": {"coworker": " evidence collector ", "task": "List evidence", "context": "CB-2041, 84.00 EUR"}}
    assert delegate(block, team, usage) == ("EV-1 delivery scan", False, "Evidence Collector")
    req = team[0].llm.calls[0]
    assert req.system == "You are Evidence Collector.\nYour goal: List the evidence with ids\nNever guess."
    assert req.messages == [{"role": "user", "content": "Task: List evidence\n\nContext:\nCB-2041, 84.00 EUR"}]
    assert req.tools == [] and req.temperature == 0.0
    assert usage["calls"] == 1 and usage["completion_tokens"] > 0


def test_delegate_reports_unknown_coworker_bad_input_and_failures_as_errors():
    team = coworkers([OverloadedError("busy")])
    usage = new_usage()
    text, is_error, role = delegate({"input": {"coworker": "Lawyer", "task": "x", "context": "y"}}, team, usage)
    assert (text, is_error, role) == ("unknown coworker 'Lawyer'; choose one of: Evidence Collector, Fraud Analyst", True, None)
    text, is_error, _ = delegate({"input": {"coworker": "Fraud Analyst", "task": "x"}}, team, usage)
    assert is_error and text == "delegate_work needs coworker, task and context"
    text, is_error, role = delegate({"input": {"coworker": "Evidence Collector", "task": "x", "context": "y"}}, team, usage)
    assert is_error and role == "Evidence Collector" and text.startswith("coworker Evidence Collector failed:")
    assert usage["calls"] == 0


def test_manager_delegates_reads_results_and_answers():
    team = coworkers(["EV-1 delivery scan; EV-2 3DS passed"], ["contest: EV-1, EV-2"])
    manager = ScriptedLLM([call("Evidence Collector"), call("Fraud Analyst", context="EV-1, EV-2"), "contest: EV-1, EV-2"])
    out, trace = kickoff_hierarchical(team, [TASK], manager, {"case": "CB-2041"})
    assert out.raw == "contest: EV-1, EV-2"
    assert out.tasks_output[0].agent == "Crew Manager"
    assert trace == [
        {"task": "investigate", "coworker": "Evidence Collector", "is_error": False},
        {"task": "investigate", "coworker": "Fraud Analyst", "is_error": False},
    ]
    first = manager.calls[0]
    assert first.system == manager_system_prompt(team)
    assert first.tools == [DELEGATE_TOOL]
    assert first.messages[0]["content"].startswith("Task: Investigate CB-2041\n\nExpected output:")
    second = manager.calls[1].messages
    assert second[1]["role"] == "assistant" and second[1]["content"][0]["type"] == "tool_use"
    assert second[2] == {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "EV-1 delivery scan; EV-2 3DS passed", "is_error": False}
    ]}
    assert out.token_usage["calls"] == 5
    assert out.token_usage["total_tokens"] == out.token_usage["prompt_tokens"] + out.token_usage["completion_tokens"]


def test_unknown_coworker_comes_back_as_an_error_the_manager_can_fix():
    team = coworkers(["EV-1"])
    manager = ScriptedLLM([call("Researcher"), call("Evidence Collector"), "accept"])
    out, trace = kickoff_hierarchical(team, [TASK], manager, {"case": "CB-2041"})
    assert [t["is_error"] for t in trace] == [True, False]
    assert trace[0]["coworker"] == "Researcher"
    result = manager.calls[1].messages[-1]["content"][0]
    assert result["is_error"] is True and "choose one of: Evidence Collector, Fraud Analyst" in result["content"]


def test_delegation_budget_stops_runaway_delegation():
    team = coworkers(["a", "b"])
    manager = ScriptedLLM([call("Evidence Collector")] * 4 + ["accept"])
    usage, trace = new_usage(), []
    out = run_manager_task(manager, TASK, team, [], usage, trace, max_delegations=2, max_turns=8)
    assert out.raw == "accept"
    assert len(team[0].llm.calls) == 2  # the 3rd and 4th requests never reach the coworker
    assert [t["is_error"] for t in trace] == [False, False, True, True]
    last = manager.calls[3].messages[-1]["content"][0]["content"]
    assert last == "delegation budget of 2 used up; give your final answer now"


def test_turn_limit_raises():
    team = coworkers(["x"] * 10)
    manager = ScriptedLLM([call("Evidence Collector")] * 10)
    with pytest.raises(RuntimeError):
        run_manager_task(manager, TASK, team, [], new_usage(), [], max_delegations=10, max_turns=3)
    assert len(manager.calls) == 3


def test_other_tool_names_are_errors_and_not_counted_as_delegations():
    team = coworkers(["EV-1"])
    manager = ScriptedLLM([{"tool": "issue_refund", "input": {"amount": "84.00"}}, call("Evidence Collector"), "accept"])
    trace = []
    run_manager_task(manager, TASK, team, [], new_usage(), trace, max_delegations=1)
    assert trace[0]["is_error"] is True and trace[1]["is_error"] is False
    assert manager.calls[1].messages[-1]["content"][0]["content"] == "unknown tool 'issue_refund'"


def test_guardrail_on_the_managers_answer():
    def must_cite(output):
        return ("EV-" in output.raw, "cite at least one evidence id")

    team = coworkers()
    task = Task("investigate", "Investigate", "decision", guardrails=[must_cite], guardrail_max_retries=1)
    manager = ScriptedLLM(["contest", "contest: EV-1"])
    out = run_manager_task(manager, task, team, [], new_usage(), [])
    assert out.raw == "contest: EV-1" and out.attempts == 2
    assert manager.calls[1].messages[-1]["content"] == "Your answer failed a check: cite at least one evidence id\nReturn a corrected answer."
    with pytest.raises(GuardrailError):
        run_manager_task(ScriptedLLM(["contest", "contest"]), task, team, [], new_usage(), [])


def test_hierarchical_needs_a_manager_and_passes_context_between_tasks():
    team = coworkers()
    with pytest.raises(ValueError):
        kickoff_hierarchical(team, [TASK], None)
    first = Task("collect", "Collect", "evidence")
    second = Task("decide", "Decide", "decision")
    manager = ScriptedLLM(["EV-1, EV-2", "contest"])
    out, _ = kickoff_hierarchical(team, [first, second], manager)
    assert '<context task="collect" agent="Crew Manager">\nEV-1, EV-2\n</context>' in manager.calls[1].messages[0]["content"]
    assert out.raw == "contest"
