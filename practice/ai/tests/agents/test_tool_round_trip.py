import threading

import pytest
from agents.tool_executor import ExecutionPolicy
from agents.tool_registry import ToolRegistry
from agents.tool_round_trip import ToolLoopError, execute_all, run_tool_loop
from llm_fake import Reply, ScriptedLLM

pytestmark = pytest.mark.exercise

TX_SCHEMA = {
    "type": "object",
    "properties": {"transaction_id": {"type": "string", "pattern": "^tx_[0-9]+$", "description": "SandPay transaction id."}},
    "required": ["transaction_id"],
    "additionalProperties": False,
}
TRANSACTIONS = {"tx_1042": {"amount": 42.1, "currency": "EUR"}, "tx_1043": {"amount": 42.1, "currency": "EUR"}}
ASK = [{"role": "user", "content": "What is tx_1042?"}]


def make(fn=lambda transaction_id: TRANSACTIONS[transaction_id]):
    reg = ToolRegistry()
    reg.register("get_transaction", "Look up one SandPay card transaction by its id and return its amount and currency.", TX_SCHEMA, fn)
    reg.register("issue_refund", "Issue a refund for a settled transaction; this moves money and cannot be undone.", TX_SCHEMA, fn, read_only=False)
    return reg, ExecutionPolicy(allowed=frozenset({"get_transaction"}), timeout=2.0)


class ParallelLLM:
    """A step that is a list of (name, input) pairs returns one reply with several tool_use blocks."""

    def __init__(self, steps):
        self.steps, self.calls = steps, []

    def create(self, **request):
        self.calls.append(request)
        step = self.steps[len(self.calls) - 1]
        if isinstance(step, list):
            blocks = [{"type": "tool_use", "id": f"call_{i}", "name": n, "input": a} for i, (n, a) in enumerate(step)]
            return Reply(blocks, "tool_use", 10, 10)
        return Reply([{"type": "text", "text": step}], "end_turn", 10, 10)


def test_no_tool_needed_is_one_call():
    reg, policy = make()
    llm = ScriptedLLM(["Hello! How can I help?"])
    result = run_tool_loop(llm, reg, ASK, policy, system="SandPay support")
    assert (result.text, result.stop_reason, result.turns, result.tool_calls) == ("Hello! How can I help?", "end_turn", 1, [])
    assert llm.calls[0].system == "SandPay support"


def test_round_trip_appends_tool_use_and_tool_result():
    reg, policy = make()
    llm = ScriptedLLM([{"tool": "get_transaction", "input": {"transaction_id": "tx_1042"}}, "It is 42.10 EUR."])
    result = run_tool_loop(llm, reg, ASK, policy)
    assert result.text == "It is 42.10 EUR." and result.turns == 2 and result.tool_calls == ["get_transaction"]
    roles = [m["role"] for m in result.messages]
    assert roles == ["user", "assistant", "user", "assistant"]
    assert result.messages[1]["content"][0]["type"] == "tool_use"
    tool_msg = result.messages[2]["content"]
    assert len(tool_msg) == 1 and tool_msg[0]["type"] == "tool_result"
    assert tool_msg[0]["tool_use_id"] == result.messages[1]["content"][0]["id"]
    assert '"amount": 42.1' in tool_msg[0]["content"] and tool_msg[0]["is_error"] is False
    # the second request carried the whole round trip
    assert len(llm.calls[1].messages) == 3
    assert ASK == [{"role": "user", "content": "What is tx_1042?"}]  # caller's list untouched


def test_only_allowed_tools_are_offered():
    reg, policy = make()
    llm = ScriptedLLM(["ok"])
    run_tool_loop(llm, reg, ASK, policy)
    assert [t["name"] for t in llm.calls[0].tools] == ["get_transaction"]


def test_errors_go_back_to_the_model_and_it_can_recover():
    reg, policy = make()
    llm = ScriptedLLM(
        [
            {"tool": "issue_refund", "input": {"transaction_id": "tx_1042"}},
            {"tool": "get_transaction", "input": {"transaction_id": 1042}},
            {"tool": "get_transaction", "input": {"transaction_id": "tx_1042"}},
            "Found it: 42.10 EUR.",
        ]
    )
    result = run_tool_loop(llm, reg, ASK, policy)
    assert result.turns == 4 and result.text == "Found it: 42.10 EUR."
    results = [m["content"][0] for m in result.messages if m["role"] == "user" and isinstance(m["content"], list)]
    assert [r["is_error"] for r in results] == [True, True, False]
    assert "not allowed" in results[0]["content"] and "expected string" in results[1]["content"]


def test_runaway_loop_is_capped():
    reg, policy = make()
    llm = ScriptedLLM(lambda req: {"tool": "get_transaction", "input": {"transaction_id": "tx_1042"}})
    with pytest.raises(ToolLoopError):
        run_tool_loop(llm, reg, ASK, policy, max_turns=3)
    assert len(llm.calls) == 3


def test_parallel_calls_return_in_one_message_in_call_order():
    reg, policy = make()
    llm = ParallelLLM(
        [[("get_transaction", {"transaction_id": "tx_1042"}), ("get_transaction", {"transaction_id": "tx_1043"}), ("issue_refund", {"transaction_id": "tx_1042"})],
         "Same amount twice."]
    )
    result = run_tool_loop(llm, reg, ASK, policy)
    assert result.turns == 2 and len(result.messages) == 4
    results = result.messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["call_0", "call_1", "call_2"]
    assert [r["is_error"] for r in results] == [False, False, True]
    assert result.tool_calls == ["get_transaction", "get_transaction", "issue_refund"]


def test_parallel_calls_really_run_concurrently():
    barrier = threading.Barrier(2, timeout=2)

    def meet(transaction_id):
        barrier.wait()  # only returns if both calls are in flight at the same time
        return TRANSACTIONS[transaction_id]

    reg, policy = make(fn=meet)
    calls = [{"type": "tool_use", "id": f"c{i}", "name": "get_transaction", "input": {"transaction_id": t}} for i, t in enumerate(TRANSACTIONS)]
    results = execute_all(reg, calls, policy)
    assert [r["tool_use_id"] for r in results] == ["c0", "c1"]
    assert [r["is_error"] for r in results] == [False, False]
    assert execute_all(reg, [], policy) == []
