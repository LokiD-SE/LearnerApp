import pytest
from mcp.arch_host import Host, McpError, controller
from mcp_arch_fixture import FakeServer, docs_server, payments_server

pytestmark = pytest.mark.exercise

META = "io.modelcontextprotocol/"


def make_host(approve=lambda s, t, a: True, capabilities=None):
    host = Host(approve, capabilities)
    pay, docs = payments_server(), docs_server()
    host.connect("payments", pay)
    host.connect("docs", docs)
    return host, pay, docs


def test_controller():
    assert controller("tools") == "model"
    assert controller("resources") == "application"
    assert controller("prompts") == "user"
    with pytest.raises(ValueError):
        controller("elicitation")


def test_one_client_per_server_and_discover_first():
    host, pay, docs = make_host()
    assert set(host.clients) == {"payments", "docs"}
    assert host.clients["payments"].server is pay and host.clients["docs"].server is docs
    assert pay.received[0]["method"] == "server/discover"
    assert host.clients["docs"].server_capabilities == {"tools": {}, "resources": {}, "prompts": {}}


def test_every_request_carries_meta():
    host, pay, docs = make_host(capabilities={"elicitation": {}})
    host.all_tools()
    for msg in pay.received + docs.received:
        meta = msg["params"]["_meta"]
        assert meta[META + "protocolVersion"] == "2026-07-28"
        assert meta[META + "clientCapabilities"] == {"elicitation": {}}
        assert meta[META + "clientInfo"]["name"]


def test_request_ids_unique_per_client():
    host, pay, _ = make_host()
    host.all_tools()
    host.all_tools()
    ids = [m["id"] for m in pay.received]
    assert len(ids) == len(set(ids)) == 3


def test_all_tools_is_namespaced_and_skips_servers_without_tools():
    host, _, _ = make_host()
    quiet = FakeServer("sandpay-static", resources={"sandpay://x": {"name": "x", "mimeType": "text/plain", "text": "x"}})
    host.connect("static", quiet)
    names = [t["name"] for t in host.all_tools()]
    assert names == ["payments__get_payment", "payments__refund_payment", "docs__search_docs"]
    assert [m["method"] for m in quiet.received] == ["server/discover"]


def test_call_routes_to_the_right_server_only():
    host, pay, docs = make_host()
    before = len(docs.received)
    result = host.call_tool("payments__get_payment", {"payment_id": "pay_7001"})
    assert result["resultType"] == "complete" and result["isError"] is False
    assert '"status": "settled"' in result["content"][0]["text"]
    assert len(docs.received) == before
    call = pay.received[-1]
    assert call["method"] == "tools/call"
    assert call["params"]["name"] == "get_payment"  # the server sees its own tool name
    assert set(call["params"]) == {"name", "arguments", "_meta"}  # and nothing of the conversation


def test_denied_call_never_reaches_the_server():
    host, pay, _ = make_host(approve=lambda s, t, a: t != "get_payment")
    before = len(pay.received)
    result = host.call_tool("payments__get_payment", {"payment_id": "pay_7001"})
    assert result["isError"] is True and "denied" in result["content"][0]["text"]
    assert len(pay.received) == before


def test_unknown_server_and_protocol_errors():
    host, _, _ = make_host()
    with pytest.raises(KeyError):
        host.call_tool("ledger__get_balance", {})
    with pytest.raises(KeyError):
        host.call_tool("get_payment", {})
    with pytest.raises(McpError) as exc:
        host.call_tool("payments__get_payment", {})
    assert exc.value.code == -32602


def test_connect_rejects_bad_names_and_versions():
    host, _, _ = make_host()
    with pytest.raises(ValueError):
        host.connect("payments", payments_server())
    with pytest.raises(ValueError):
        host.connect("pay__ments", payments_server())
    old = FakeServer("old", supported_versions=("2025-11-25",))
    with pytest.raises(McpError) as exc:
        host.connect("old", old)
    assert exc.value.code == -32022 and exc.value.data["supported"] == ["2025-11-25"]
    assert "old" not in host.clients
