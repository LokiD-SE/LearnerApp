import threading

import pytest
from mcp.multi_router import ServerHealth, check_response, fan_out, make_request, route_call

pytestmark = pytest.mark.exercise


def ok_server(result):
    def send(request):
        return {"jsonrpc": "2.0", "id": request["id"], "result": result}

    return send


def tools_call_server():
    def send(request):
        args = request["params"]["arguments"]
        text = f"{request['params']['name']} -> {args}"
        return {"jsonrpc": "2.0", "id": request["id"], "result": {"resultType": "complete", "content": [{"type": "text", "text": text}], "isError": False}}

    return send


def down_server(request):
    raise ConnectionRefusedError("connection refused")


def error_server(request):
    return {"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32602, "message": "Unknown tool: search"}}


def wrong_id_server(request):
    return {"jsonrpc": "2.0", "id": "other", "result": {}}


@pytest.fixture
def hung_server():
    release = threading.Event()

    def send(request):
        release.wait(5)
        return {"jsonrpc": "2.0", "id": request["id"], "result": {}}

    yield send
    release.set()


def test_make_request_carries_the_per_request_meta_and_fresh_ids():
    a = make_request("tools/list")
    b = make_request("tools/call", {"name": "search", "arguments": {}})
    assert a["jsonrpc"] == "2.0" and a["method"] == "tools/list"
    assert a["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
    assert a["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"] == {}
    assert b["params"]["name"] == "search"
    assert a["id"] != b["id"]


def test_check_response_returns_result_or_explains():
    req = make_request("tools/list")
    assert check_response(req, {"jsonrpc": "2.0", "id": req["id"], "result": {"tools": []}}) == {"tools": []}
    with pytest.raises(RuntimeError, match="-32602"):
        check_response(req, error_server(req))
    with pytest.raises(RuntimeError, match="bad response"):
        check_response(req, wrong_id_server(req))


def test_fan_out_returns_partial_results_when_servers_fail():
    out = fan_out(
        {"ledger": ok_server({"tools": ["a"]}), "support": down_server, "kb": error_server, "fx": wrong_id_server},
        "tools/list",
    )
    assert out.results == {"ledger": {"tools": ["a"]}}
    assert out.errors["support"] == "unavailable: ConnectionRefusedError: connection refused"
    assert out.errors["kb"] == "error -32602: Unknown tool: search"
    assert out.errors["fx"].startswith("bad response")


def test_fan_out_times_out_a_hung_server_without_waiting_for_it(hung_server):
    import time

    start = time.monotonic()
    out = fan_out({"ledger": ok_server({"tools": []}), "slow": hung_server}, "tools/list", timeout=0.1)
    assert time.monotonic() - start < 1.0
    assert out.results == {"ledger": {"tools": []}}
    assert out.errors == {"slow": "timeout after 0.1s"}


def test_health_skips_a_server_after_threshold_failures_and_recovers_on_success():
    health = ServerHealth(threshold=2)
    clients = {"ledger": ok_server({}), "support": down_server}
    fan_out(clients, "tools/list", health=health)
    fan_out(clients, "tools/list", health=health)
    assert health.is_down("support") and not health.is_down("ledger")
    out = fan_out(clients, "tools/list", health=health)
    assert out.errors["support"] == "skipped: down after 2 failures"
    health.record("support", True)
    assert not health.is_down("support")


def resolver(name):
    table = {"ledger__search": ("ledger", "search"), "support__search": ("support", "search")}
    return table[name]


def test_route_call_sends_the_original_tool_name_to_the_owning_server():
    result = route_call(resolver, {"ledger": tools_call_server(), "support": down_server}, "ledger__search", {"query": "po_1039"})
    assert result["isError"] is False
    assert result["content"][0]["text"] == "search -> {'query': 'po_1039'}"


def test_route_call_turns_every_failure_into_an_error_result():
    clients = {"ledger": tools_call_server(), "support": down_server}
    down = route_call(resolver, clients, "support__search", {"query": "x"})
    assert down["isError"] is True
    assert "support" in down["content"][0]["text"] and "ConnectionRefusedError" in down["content"][0]["text"]
    unknown = route_call(resolver, clients, "search", {"query": "x"})
    assert unknown["isError"] is True and "Unknown tool" in unknown["content"][0]["text"]
    missing = route_call(resolver, {"ledger": tools_call_server()}, "support__search", {})
    assert missing["isError"] is True and "not connected" in missing["content"][0]["text"]
