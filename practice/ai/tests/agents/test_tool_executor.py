import json
import threading

import pytest
from agents.tool_executor import ExecutionPolicy, ToolTimeout, execute_call, run_with_timeout, serialise, tool_result
from agents.tool_registry import ToolRegistry

pytestmark = pytest.mark.exercise

TX_SCHEMA = {
    "type": "object",
    "properties": {"transaction_id": {"type": "string", "pattern": "^tx_[0-9]+$", "description": "SandPay transaction id."}},
    "required": ["transaction_id"],
    "additionalProperties": False,
}
TRANSACTIONS = {"tx_1042": {"id": "tx_1042", "amount": 42.1, "currency": "EUR", "status": "settled"}}
DESC = "Look up one SandPay card transaction by its id and return its amount, currency and status."


def lookup(transaction_id):
    if transaction_id not in TRANSACTIONS:
        raise LookupError(f"no transaction {transaction_id}")
    return TRANSACTIONS[transaction_id]


def make(fn=lookup, allowed=("get_transaction",), **policy):
    reg = ToolRegistry()
    reg.register("get_transaction", DESC, TX_SCHEMA, fn)
    reg.register("issue_refund", "Issue a refund for a settled transaction; this moves money and cannot be undone.", TX_SCHEMA, fn, read_only=False)
    return reg, ExecutionPolicy(allowed=frozenset(allowed), **policy)


def call(name="get_transaction", **args):
    return {"type": "tool_use", "id": "call_7", "name": name, "input": args or {"transaction_id": "tx_1042"}}


def test_success_is_serialised_json_and_matches_the_call_id():
    reg, policy = make()
    result = execute_call(reg, call(), policy)
    assert result["type"] == "tool_result" and result["tool_use_id"] == "call_7"
    assert result["is_error"] is False
    assert json.loads(result["content"]) == TRANSACTIONS["tx_1042"]
    assert result["content"] == json.dumps(TRANSACTIONS["tx_1042"], sort_keys=True)


def test_tool_outside_the_allow_list_never_runs():
    ran = []
    reg, policy = make(fn=lambda **kw: ran.append(kw))
    result = execute_call(reg, call("issue_refund"), policy)
    assert result["is_error"] is True and ran == []
    assert "not allowed" in result["content"] and "get_transaction" in result["content"]


def test_unknown_tool_is_an_error_result():
    reg, policy = make(allowed=("get_transaction", "get_balance"))
    result = execute_call(reg, call("get_balance"), policy)
    assert result["is_error"] is True and "unknown tool 'get_balance'" in result["content"]


def test_invalid_input_lists_every_error_and_never_runs():
    ran = []
    reg, policy = make(fn=lambda **kw: ran.append(kw))
    result = execute_call(reg, {"type": "tool_use", "id": "c1", "name": "get_transaction", "input": {"transaction_id": "1042", "x": 1}}, policy)
    assert result["is_error"] is True and ran == []
    assert "invalid input" in result["content"]
    assert "unexpected field 'x'" in result["content"] and "transaction_id" in result["content"]


def test_exceptions_become_results_without_tracebacks():
    reg, policy = make()
    result = execute_call(reg, call(transaction_id="tx_9999"), policy)
    assert result["is_error"] is True
    assert "LookupError" in result["content"] and "tx_9999" in result["content"]
    assert "Traceback" not in result["content"]


def test_timeout_is_reported_and_the_loop_is_not_blocked():
    release = threading.Event()

    def hangs(transaction_id):
        release.wait(2)
        return {}

    reg, policy = make(fn=hangs, timeout=0.05)
    try:
        result = execute_call(reg, call(), policy)
    finally:
        release.set()
    assert result["is_error"] is True and "timed out" in result["content"]
    with pytest.raises(ToolTimeout):
        release.clear()
        try:
            run_with_timeout(hangs, {"transaction_id": "tx_1"}, 0.05)
        finally:
            release.set()
    assert run_with_timeout(lambda a, b: a + b, {"a": 2, "b": 3}, 1.0) == 5


def test_runner_is_injected_and_gets_the_policy_timeout():
    seen = []

    def fake_run(fn, kwargs, timeout):
        seen.append((kwargs, timeout))
        return "ok"

    reg, policy = make(timeout=2.5)
    assert execute_call(reg, call(), policy, run=fake_run)["content"] == "ok"
    assert seen == [({"transaction_id": "tx_1042"}, 2.5)]

    def fake_timeout(fn, kwargs, timeout):
        raise ToolTimeout("timed out after 2.5s")

    assert "timed out" in execute_call(reg, call(), policy, run=fake_timeout)["content"]


def test_long_results_are_truncated_with_a_marker():
    assert serialise("abc", 10) == "abc"
    assert serialise({"b": 1, "a": 2}, 100) == '{"a": 2, "b": 1}'
    assert serialise("x" * 25, 10) == "x" * 10 + " ... [truncated 15 chars]"
    reg, policy = make(fn=lambda transaction_id: "y" * 50, max_result_chars=20)
    assert execute_call(reg, call(), policy)["content"].endswith("[truncated 30 chars]")
    assert tool_result("c", "boom", True) == {"type": "tool_result", "tool_use_id": "c", "content": "boom", "is_error": True}
