import pytest
from mcp.arch_mrtr import InputLoopError, answer_input_requests, call_with_input
from mcp_arch_fixture import payments_server

pytestmark = pytest.mark.exercise

REFUND = {"name": "refund_payment", "arguments": {"payment_id": "pay_7001", "amount_minor": 1200}}


class ProtocolError(Exception):
    def __init__(self, error):
        super().__init__(error["message"])
        self.code, self.data = error["code"], error.get("data")


class TestClient:
    """A bare client for these tests: new id per request, the required _meta, errors raised."""

    __test__ = False

    def __init__(self, server, capabilities):
        self.server, self.capabilities, self.n = server, capabilities, 0

    def request(self, method, params):
        self.n += 1
        body = dict(params)
        body["_meta"] = {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": self.capabilities,
        }
        reply = self.server.handle({"jsonrpc": "2.0", "id": self.n, "method": method, "params": body})
        if "error" in reply:
            raise ProtocolError(reply["error"])
        return reply["result"]


def client(caps):
    return TestClient(payments_server(), caps)


def approve(params):
    return {"action": "accept", "content": {"approve": True}}


def test_answer_input_requests():
    reqs = {"confirm": {"method": "elicitation/create", "params": {"mode": "form", "message": "ok?"}}}
    seen = []
    out = answer_input_requests(reqs, {"elicitation": {}}, lambda p: seen.append(p) or {"action": "decline"})
    assert out == {"confirm": {"action": "decline"}} and seen == [{"mode": "form", "message": "ok?"}]
    with pytest.raises(ValueError):
        answer_input_requests(reqs, {}, approve)
    with pytest.raises(ValueError):
        answer_input_requests({"x": {"method": "roots/list"}}, {"elicitation": {}}, approve)


def test_retry_completes_with_new_id_and_echoed_state():
    c = client({"elicitation": {}})
    result = call_with_input(c, "tools/call", REFUND, approve)
    assert result["resultType"] == "complete" and result["isError"] is False
    assert '"refund_id": "rf_7001"' in result["content"][0]["text"]
    first, retry = c.server.received
    assert first["id"] != retry["id"]
    assert "inputResponses" not in first["params"]
    assert retry["params"]["inputResponses"] == {"confirm": {"action": "accept", "content": {"approve": True}}}
    assert retry["params"]["name"] == "refund_payment" and retry["params"]["arguments"] == REFUND["arguments"]
    assert retry["params"]["requestState"]


def test_declined_is_a_tool_error_not_an_exception():
    c = client({"elicitation": {}})
    result = call_with_input(c, "tools/call", REFUND, lambda p: {"action": "decline"})
    assert result["isError"] is True and "Not approved" in result["content"][0]["text"]


def test_params_not_mutated_and_complete_needs_one_round():
    c = client({"elicitation": {}})
    params = {"name": "get_payment", "arguments": {"payment_id": "pay_7002"}}
    copy = {"name": "get_payment", "arguments": {"payment_id": "pay_7002"}}
    result = call_with_input(c, "tools/call", params, approve)
    assert '"status": "failed"' in result["content"][0]["text"]
    assert params == copy and len(c.server.received) == 1


def test_missing_capability_is_a_protocol_error():
    c = client({})
    with pytest.raises(ProtocolError) as exc:
        call_with_input(c, "tools/call", REFUND, approve)
    assert exc.value.code == -32021 and exc.value.data == {"requiredCapabilities": {"elicitation": {}}}


class Nagging:
    capabilities = {"elicitation": {}}

    def __init__(self):
        self.calls = []

    def request(self, method, params):
        self.calls.append(params)
        return {"resultType": "input_required", "requestState": f"s{len(self.calls)}"}


def test_state_only_retry_and_loop_limit():
    n = Nagging()
    with pytest.raises(InputLoopError):
        call_with_input(n, "tools/call", {"name": "x"}, approve, max_rounds=3)
    assert len(n.calls) == 3
    assert n.calls[0] == {"name": "x"}
    assert n.calls[1] == {"name": "x", "requestState": "s1"}
    assert n.calls[2] == {"name": "x", "requestState": "s2"}  # the latest state, never inputResponses


def test_unknown_result_type():
    class Odd:
        capabilities = {}

        def request(self, method, params):
            return {"resultType": "partial"}

    with pytest.raises(ValueError):
        call_with_input(Odd(), "tools/call", {"name": "x"}, approve)
