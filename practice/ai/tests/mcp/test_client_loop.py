"""Exercise: the host's model loop over MCP tools (lesson: Building an MCP client).

The model is ScriptedLLM (support/llm_fake.py); the tools run in a real MCP server subprocess
(support/mcp_client_fixture.py).
"""

import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from llm_fake import ScriptedLLM
from mcp.client_loop import call_tool_with_input, result_to_text, run_host_loop
from mcp.client_rpc import McpError, RequestTimeout

pytestmark = pytest.mark.exercise

FIXTURE = str(Path(__file__).resolve().parents[2] / "support" / "mcp_client_fixture.py")
META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
}


class MiniClient:
    """Just enough MCP client for these tests, so this exercise does not need the client_rpc exercise solved."""

    def __init__(self):
        self.process = subprocess.Popen([sys.executable, FIXTURE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.lines = queue.Queue()
        threading.Thread(target=lambda: [self.lines.put(line) for line in self.process.stdout], daemon=True).start()
        self.next_id = 0
        self.sent = []

    def request(self, method, params=None, timeout=5.0, meta=None):
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": {**(params or {}), "_meta": META}}
        self.sent.append(message)
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                reply = json.loads(self.lines.get(timeout=max(deadline - time.monotonic(), 0)))
            except queue.Empty:
                cancel = {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": self.next_id}}
                self.process.stdin.write(json.dumps(cancel) + "\n")
                self.process.stdin.flush()
                raise RequestTimeout(method) from None
            if reply.get("id") != self.next_id:
                continue
            if "error" in reply:
                raise McpError(reply["error"]["code"], reply["error"]["message"], reply["error"].get("data"))
            return reply["result"]

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


@pytest.fixture
def host():
    client = MiniClient()
    tools, routes, cursor = [], {}, None
    while True:
        page = client.request("tools/list", {} if cursor is None else {"cursor": cursor})
        for tool in page["tools"]:
            name = "payouts__" + tool["name"].replace(".", "_")
            tools.append({"name": name, "description": tool["description"], "input_schema": tool["inputSchema"]})
            routes[name] = (client, tool["name"])
        cursor = page.get("nextCursor")
        if cursor is None:
            break
    yield client, tools, routes
    client.close()


def allow(name, args):
    return True


def no_input(key, request):
    raise AssertionError(f"unexpected input request {key}")


def test_result_to_text_variants():
    assert result_to_text({"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}) == "a\nb"
    assert result_to_text({"content": [{"type": "image", "data": "AAA", "mimeType": "image/png"}]}) == "[image image/png]"
    assert result_to_text({"content": [{"type": "resource_link", "uri": "sandpay://payouts/po_1039", "name": "po_1039"}]}) == "[resource_link sandpay://payouts/po_1039]"
    assert result_to_text({"content": [], "structuredContent": [1, 2]}) == "[1, 2]"
    assert result_to_text({"content": []}) == "(no content)"


def test_answer_after_one_tool_call(host):
    client, tools, routes = host
    llm = ScriptedLLM([{"tool": "payouts__get_payout", "input": {"payout_id": "po_1042"}}, "Payout po_1042 is in transit."])
    out = run_host_loop(llm, "Where is payout po_1042?", tools, routes, allow, no_input)
    assert out.answer == "Payout po_1042 is in transit."
    assert out.model_calls == 2 and out.stopped == "end_turn"
    assert out.tool_log[0]["is_error"] is False and '"in_transit"' in out.tool_log[0]["text"]
    # the second request replays the assistant turn and answers it with one tool_result
    second = llm.calls[1].messages
    assert second[1]["role"] == "assistant" and second[1]["content"][0]["type"] == "tool_use"
    block = second[2]["content"][0]
    assert block == {"type": "tool_result", "tool_use_id": second[1]["content"][0]["id"], "content": out.tool_log[0]["text"], "is_error": False}
    # tools are offered on every call, with provider-safe names
    assert all(req.tools == tools for req in llm.calls)
    assert "payouts__refunds_status" in [t["name"] for t in tools]


def test_dotted_tool_name_is_routed_back(host):
    client, tools, routes = host
    llm = ScriptedLLM([{"tool": "payouts__refunds_status", "input": {"refund_id": "rf_7"}}, "Pending."])
    out = run_host_loop(llm, "Refund rf_7?", tools, routes, allow, no_input)
    assert out.tool_log[0]["text"] == "Refund rf_7 is pending."


def test_tool_execution_error_goes_back_to_the_model(host):
    client, tools, routes = host
    llm = ScriptedLLM([{"tool": "payouts__get_payout", "input": {"payout_id": "po_77"}}, {"tool": "payouts__get_payout", "input": {"payout_id": "po_1039"}}, "Paid."])
    out = run_host_loop(llm, "Status of payout 1039?", tools, routes, allow, no_input)
    assert [e["is_error"] for e in out.tool_log] == [True, False]
    assert "not found" in llm.calls[1].messages[-1]["content"][0]["content"]
    assert llm.calls[1].messages[-1]["content"][0]["is_error"] is True


def test_unknown_tool_and_denied_tool_never_reach_the_server(host):
    client, tools, routes = host
    llm = ScriptedLLM([{"tool": "payouts__wire_money", "input": {}}, {"tool": "payouts__get_payout", "input": {"payout_id": "po_1039"}}, "Done."])
    sent_before = len(client.sent)
    out = run_host_loop(llm, "x", tools, routes, lambda name, args: False, no_input)
    assert [e["is_error"] for e in out.tool_log] == [True, True]
    assert "Unknown tool" in out.tool_log[0]["text"]
    assert "did not approve" in out.tool_log[1]["text"]
    assert len(client.sent) == sent_before  # no tools/call was sent


def test_protocol_error_becomes_an_error_result():
    class Broken:
        def request(self, method, params=None, timeout=5.0, meta=None):
            raise McpError(-32602, "Unknown tool: get_payout")

    tools = [{"name": "p__get_payout", "description": "x", "input_schema": {"type": "object"}}]
    llm = ScriptedLLM([{"tool": "p__get_payout", "input": {}}, "Sorry."])
    out = run_host_loop(llm, "x", tools, {"p__get_payout": (Broken(), "get_payout")}, allow, no_input)
    assert out.tool_log[0]["is_error"] is True
    assert "-32602" in out.tool_log[0]["text"]


def test_timeout_becomes_an_error_result(host):
    client, tools, routes = host
    llm = ScriptedLLM([{"tool": "payouts__slow_report", "input": {"seconds": 0.2}}, "The report is slow."])
    out = run_host_loop(llm, "Report?", tools, routes, allow, no_input, timeout=0.05)
    assert out.tool_log[0]["is_error"] is True and "timed out" in out.tool_log[0]["text"]


def test_turn_cap(host):
    client, tools, routes = host
    llm = ScriptedLLM(lambda req: {"tool": "payouts__get_payout", "input": {"payout_id": "po_1039"}})
    out = run_host_loop(llm, "loop", tools, routes, allow, no_input, max_turns=3)
    assert out.stopped == "max_turns" and out.model_calls == 3 and len(out.tool_log) == 3


def test_mrtr_retry_echoes_request_state_with_a_new_id(host):
    client, tools, routes = host
    asked = []

    def answer(key, request):
        asked.append((key, request["method"], request["params"]["mode"]))
        return {"action": "accept", "content": {"approve": True}}

    result = call_tool_with_input(client, "confirm_refund", {"refund_id": "rf_7"}, answer)
    assert asked == [("confirm", "elicitation/create", "form")]
    assert result["isError"] is False and result["structuredContent"]["status"] == "approved"
    first, retry = client.sent[-2], client.sent[-1]
    assert retry["id"] != first["id"]
    assert "requestState" not in first["params"] and "inputResponses" not in first["params"]
    assert retry["params"]["inputResponses"] == {"confirm": {"action": "accept", "content": {"approve": True}}}
    assert isinstance(retry["params"]["requestState"], str)


def test_mrtr_decline_is_a_tool_error(host):
    client, tools, routes = host
    result = call_tool_with_input(client, "confirm_refund", {"refund_id": "rf_7"}, lambda key, req: {"action": "decline"})
    assert result["isError"] is True and "decline" in result["content"][0]["text"]


class Scripted:
    """A fake server: returns the queued results and records the params of each tools/call."""

    def __init__(self, results):
        self.results = list(results)
        self.params = []

    def request(self, method, params=None, timeout=5.0, meta=None):
        self.params.append(params)
        return self.results.pop(0)


def test_mrtr_without_request_state_sends_none():
    fake = Scripted([{"resultType": "input_required", "inputRequests": {"q": {"method": "elicitation/create", "params": {"mode": "form", "message": "?", "requestedSchema": {"type": "object"}}}}}, {"resultType": "complete", "content": []}])
    call_tool_with_input(fake, "t", {"a": 1}, lambda k, r: {"action": "cancel"})
    assert fake.params[1] == {"name": "t", "arguments": {"a": 1}, "inputResponses": {"q": {"action": "cancel"}}}


def test_mrtr_state_only_retries_at_once_and_round_limit():
    fake = Scripted([{"resultType": "input_required", "requestState": "opaque-1"}, {"resultType": "complete", "content": []}])
    call_tool_with_input(fake, "t", {}, no_input)
    assert fake.params[1]["requestState"] == "opaque-1" and fake.params[1]["inputResponses"] == {}
    endless = Scripted([{"resultType": "input_required", "requestState": "s"}] * 10)
    with pytest.raises(RuntimeError):
        call_tool_with_input(endless, "t", {}, no_input, max_rounds=2)
    assert len(endless.params) == 3
