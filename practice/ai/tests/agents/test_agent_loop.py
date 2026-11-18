"""Checks exercises/agents/agent_loop.py - lesson agent-loops-and-workflow-patterns.

The model is the offline ScriptedLLM: a script step {"tool": name, "input": {...}} is a tool-use reply, a string is
a final answer, an exception is raised by the call. Tools are plain functions; the clock is a fake that advances
0.25 s per reading, so tool timings in the trace are exact.
"""

import pytest

from agents.agent_loop import AgentResult, call_key, run_agent, run_tool
from llm_fake import OverloadedError, ScriptedLLM

pytestmark = pytest.mark.exercise

PAYOUTS = {"po_1042": {"gross": "1250.00", "fees": "36.25", "refunds": "80.00", "net": "1133.75"}}


def get_payout(payout_id):
    if payout_id not in PAYOUTS:
        raise KeyError(f"no payout {payout_id}")
    return PAYOUTS[payout_id]


def list_refunds(payout_id):
    return [{"refund": "rf_7", "amount": "80.00"}]


TOOLS = {"get_payout": get_payout, "list_refunds": list_refunds}


def fake_clock():
    t = [0.0]

    def clock():
        t[0] += 0.25
        return t[0]

    return clock


def events(result, kind):
    return [e for e in result.trace if e["type"] == kind]


def test_run_tool_ok_unknown_and_raising():
    assert run_tool(TOOLS, "list_refunds", {"payout_id": "po_1042"}) == ("[{'refund': 'rf_7', 'amount': '80.00'}]", False)
    assert run_tool(TOOLS, "delete_payout", {}) == (
        "Unknown tool 'delete_payout'. Available tools: get_payout, list_refunds.",
        True,
    )
    assert run_tool(TOOLS, "get_payout", {"payout_id": "po_9"}) == ("KeyError: 'no payout po_9'", True)
    content, is_error = run_tool(TOOLS, "get_payout", {"wrong_arg": 1})
    assert is_error and content.startswith("TypeError:")


def test_call_key_ignores_key_order():
    assert call_key("t", {"a": 1, "b": 2}) == call_key("t", {"b": 2, "a": 1})
    assert call_key("t", {"a": 1}) != call_key("u", {"a": 1})


def test_answers_after_tool_round_trip_and_sends_results_back():
    llm = ScriptedLLM(
        [{"tool": "get_payout", "input": {"payout_id": "po_1042"}}, "Net 1133.75: 36.25 fees and an 80.00 refund."]
    )
    result = run_agent(llm, "Why is payout po_1042 short?", TOOLS, [{"name": "get_payout"}], clock=fake_clock())
    assert isinstance(result, AgentResult)
    assert (result.status, result.answer, result.steps) == ("done", "Net 1133.75: 36.25 fees and an 80.00 refund.", 2)
    assert llm.calls[0].tools == [{"name": "get_payout"}]
    second = llm.calls[1].messages
    assert [m["role"] for m in second] == ["user", "assistant", "user"]
    assert second[1]["content"][0]["type"] == "tool_use"
    block = second[2]["content"][0]
    assert block["type"] == "tool_result" and block["tool_use_id"] == "call_1" and block["is_error"] is False
    assert "1133.75" in block["content"]
    assert result.input_tokens == sum(e["input_tokens"] for e in events(result, "model"))
    assert result.output_tokens == sum(e["output_tokens"] for e in events(result, "model"))


def test_trace_records_every_step_in_order():
    llm = ScriptedLLM([{"tool": "get_payout", "input": {"payout_id": "po_1042"}}, "ok"])
    result = run_agent(llm, "task", TOOLS, clock=fake_clock())
    assert [e["type"] for e in result.trace] == ["model", "tool", "model", "stop"]
    m1, tool, m2, stop = result.trace
    assert m1["step"] == 1 and m1["stop_reason"] == "tool_use"
    assert m1["tool_calls"] == [{"id": "call_1", "name": "get_payout", "input": {"payout_id": "po_1042"}}]
    assert tool["step"] == 1 and tool["id"] == "call_1" and tool["name"] == "get_payout"
    assert tool["is_error"] is False and tool["ms"] == 250.0 and "1133.75" in tool["output"]
    assert m2["step"] == 2 and m2["stop_reason"] == "end_turn" and m2["text"] == "ok" and m2["tool_calls"] == []
    assert stop == {"type": "stop", "step": 2, "status": "done"}


def test_tool_error_goes_back_to_the_model_which_recovers():
    llm = ScriptedLLM(
        [
            {"tool": "get_payout", "input": {"payout_id": "PO-1042"}},
            {"tool": "get_payout", "input": {"payout_id": "po_1042"}},
            "Found it.",
        ]
    )
    result = run_agent(llm, "task", TOOLS, clock=fake_clock())
    assert result.status == "done" and result.steps == 3
    error_block = llm.calls[1].messages[2]["content"][0]
    assert error_block["is_error"] is True and error_block["content"] == "KeyError: 'no payout PO-1042'"
    assert [e["is_error"] for e in events(result, "tool")] == [True, False]


def test_stops_when_the_same_call_repeats():
    same = {"tool": "list_refunds", "input": {"payout_id": "po_1042"}}
    llm = ScriptedLLM([same, same, same, "never reached"])
    result = run_agent(llm, "task", TOOLS, max_repeats=2, clock=fake_clock())
    assert (result.status, result.answer, result.steps) == ("no_progress", None, 3)
    assert len(events(result, "tool")) == 2  # the third identical call is not run
    assert result.trace[-1] == {"type": "stop", "step": 3, "status": "no_progress"}


def test_different_inputs_are_progress_not_repeats():
    llm = ScriptedLLM([{"tool": "list_refunds", "input": {"payout_id": f"po_{i}"}} for i in range(4)] + ["done"])
    result = run_agent(llm, "task", TOOLS, max_repeats=1, max_steps=10, clock=fake_clock())
    assert result.status == "done" and result.steps == 5


def test_max_steps_caps_model_calls():
    llm = ScriptedLLM(lambda req: {"tool": "list_refunds", "input": {"payout_id": f"po_{len(req.messages)}"}})
    result = run_agent(llm, "task", TOOLS, max_steps=4, max_repeats=99, clock=fake_clock())
    assert (result.status, result.answer, result.steps) == ("max_steps", None, 4)
    assert len(llm.calls) == 4
    assert result.trace[-1] == {"type": "stop", "step": 4, "status": "max_steps"}


def test_budget_stops_before_running_more_tools():
    llm = ScriptedLLM(lambda req: {"tool": "list_refunds", "input": {"payout_id": f"po_{len(req.messages)}"}})
    result = run_agent(llm, "Why is payout po_1042 short? " * 20, TOOLS, max_total_tokens=300, max_repeats=99, clock=fake_clock())
    assert result.status == "budget"
    assert result.input_tokens + result.output_tokens > 300
    # the reply that crossed the budget asked for a tool, and it was not run
    assert len(events(result, "tool")) == result.steps - 1


def test_final_answer_is_kept_even_when_it_crosses_the_budget():
    llm = ScriptedLLM(["A long but complete answer."])
    result = run_agent(llm, "x " * 50, TOOLS, max_total_tokens=10)
    assert result.status == "done" and result.answer == "A long but complete answer."


def test_consecutive_failing_steps_stop_the_run():
    llm = ScriptedLLM([{"tool": "get_payout", "input": {"payout_id": f"bad_{i}"}} for i in range(5)])
    result = run_agent(llm, "task", TOOLS, max_consecutive_errors=3, clock=fake_clock())
    assert (result.status, result.steps) == ("tool_errors", 3)


def test_one_success_resets_the_error_count():
    script = [
        {"tool": "get_payout", "input": {"payout_id": "bad_1"}},
        {"tool": "get_payout", "input": {"payout_id": "bad_2"}},
        {"tool": "get_payout", "input": {"payout_id": "po_1042"}},
        {"tool": "get_payout", "input": {"payout_id": "bad_3"}},
        {"tool": "get_payout", "input": {"payout_id": "bad_4"}},
        "answer",
    ]
    result = run_agent(ScriptedLLM(script), "task", TOOLS, max_consecutive_errors=3, clock=fake_clock())
    assert result.status == "done"


def test_non_tool_stop_reasons_end_without_an_answer():
    result = run_agent(ScriptedLLM(["word " * 40]), "task", TOOLS, max_tokens=5)
    assert (result.status, result.answer) == ("stopped", None)


def test_model_error_is_reported_with_the_trace():
    llm = ScriptedLLM([{"tool": "list_refunds", "input": {"payout_id": "po_1042"}}, OverloadedError("overloaded")])
    result = run_agent(llm, "task", TOOLS, clock=fake_clock())
    assert result.status == "model_error" and result.answer is None
    assert result.error == "OverloadedError: overloaded"
    assert [e["type"] for e in result.trace] == ["model", "tool", "error", "stop"]
