"""Exercise: tool discovery - pagination, conversion to model tools, and caching (lesson: Building an MCP client)."""

import sys
from pathlib import Path

import pytest
from mcp.client_rpc import ProtocolError, RpcClient, StdioTransport
from mcp.client_tools import ToolCatalog, list_all_tools, provider_name, to_provider_tools

pytestmark = pytest.mark.exercise


def shutdown(transport):
    """Test teardown that does not depend on the exercise: close stdin, then kill if needed."""
    try:
        transport.process.stdin.close()
    except OSError:
        pass
    try:
        transport.process.wait(timeout=1)
    except Exception:
        transport.process.kill()
        transport.process.wait()

FIXTURE = str(Path(__file__).resolve().parents[2] / "support" / "mcp_client_fixture.py")


class FakeServer:
    """Answers tools/list from a dict of cursor -> page and records the params of every request."""

    def __init__(self, pages):
        self.pages = pages
        self.params = []

    def request(self, method, params=None, **kwargs):
        assert method == "tools/list"
        params = params or {}
        self.params.append(params)
        return self.pages[params.get("cursor")]


def tool(name, schema=None):
    return {"name": name, "description": f"{name} tool", "inputSchema": schema if schema is not None else {"type": "object"}}


def test_follows_cursors_until_none():
    server = FakeServer({None: {"tools": [tool("a")], "nextCursor": "p2"}, "p2": {"tools": [tool("b")], "nextCursor": "p3"}, "p3": {"tools": [tool("c")]}})
    assert [t["name"] for t in list_all_tools(server)] == ["a", "b", "c"]
    assert server.params == [{}, {"cursor": "p2"}, {"cursor": "p3"}]


def test_empty_string_cursor_is_not_the_end():
    server = FakeServer({None: {"tools": [tool("a")], "nextCursor": ""}, "": {"tools": [tool("b")]}})
    assert [t["name"] for t in list_all_tools(server)] == ["a", "b"]
    assert server.params[1] == {"cursor": ""}


def test_repeated_cursor_is_a_protocol_error():
    server = FakeServer({None: {"tools": [tool("a")], "nextCursor": "x"}, "x": {"tools": [tool("b")], "nextCursor": "x"}})
    with pytest.raises(ProtocolError):
        list_all_tools(server)


def test_page_limit():
    pages = {None: {"tools": [], "nextCursor": "c1"}}
    for i in range(1, 10):
        pages[f"c{i}"] = {"tools": [], "nextCursor": f"c{i + 1}"}
    with pytest.raises(ProtocolError):
        list_all_tools(FakeServer(pages), max_pages=5)


def test_real_server_has_five_tools_over_three_pages():
    transport = StdioTransport([sys.executable, FIXTURE])
    try:
        client = RpcClient(transport, capabilities={})
        names = [t["name"] for t in list_all_tools(client)]
        assert names == ["get_payout", "list_payouts", "refunds.status", "confirm_refund", "slow_report"]
    finally:
        shutdown(transport)


def test_provider_name_prefixes_and_replaces_dots():
    assert provider_name("payouts", "get_payout") == "payouts__get_payout"
    assert provider_name("payouts", "refunds.status") == "payouts__refunds_status"
    with pytest.raises(ValueError):
        provider_name("payouts", "x" * 130)


def test_conversion_keeps_schema_and_routes_back_to_the_original_name():
    schema = {"type": "object", "properties": {"refund_id": {"type": "string"}}, "required": ["refund_id"]}
    tools, routes, skipped = to_provider_tools("payouts", [{"name": "refunds.status", "description": "Refund status.", "inputSchema": schema}])
    assert tools == [{"name": "payouts__refunds_status", "description": "Refund status.", "input_schema": schema}]
    assert routes == {"payouts__refunds_status": ("payouts", "refunds.status")}
    assert skipped == []


def test_bad_definitions_are_skipped_not_fatal():
    tools, routes, skipped = to_provider_tools(
        "payouts",
        [tool("good"), {"name": "no_schema", "description": "x"}, tool("not_object", {"type": "string"}), {"name": "null_schema", "description": "x", "inputSchema": None}],
    )
    assert [t["name"] for t in tools] == ["payouts__good"]
    assert len(skipped) == 3
    assert any("no_schema" in reason for reason in skipped)


def test_clashing_names_are_both_skipped():
    tools, routes, skipped = to_provider_tools("s", [tool("a.b"), tool("a_b"), tool("c")])
    assert [t["name"] for t in tools] == ["s__c"]
    assert "s__a_b" not in routes
    assert any("s__a_b" in reason for reason in skipped)


def test_description_falls_back_to_title_then_name():
    tools, _, _ = to_provider_tools("s", [{"name": "t1", "title": "Title one", "inputSchema": {"type": "object"}}, {"name": "t2", "inputSchema": {"type": "object"}}])
    assert [t["description"] for t in tools] == ["Title one", "t2"]


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_catalog_uses_the_ttl():
    server = FakeServer({None: {"tools": [tool("a")], "ttlMs": 30000}})
    clock = Clock()
    catalog = ToolCatalog(server, clock)
    catalog.tools()
    clock.now += 29.9
    catalog.tools()
    assert catalog.fetches == 1
    clock.now += 0.2
    catalog.tools()
    assert catalog.fetches == 2


def test_catalog_absent_or_negative_ttl_is_stale_at_once():
    for page in ({"tools": [tool("a")]}, {"tools": [tool("a")], "ttlMs": -5}):
        catalog = ToolCatalog(FakeServer({None: page}), Clock())
        catalog.tools()
        catalog.tools()
        assert catalog.fetches == 2


def test_list_changed_invalidates_a_fresh_cache():
    server = FakeServer({None: {"tools": [tool("a")], "ttlMs": 60000}})
    catalog = ToolCatalog(server, Clock())
    catalog.tools()
    catalog.on_notification({"jsonrpc": "2.0", "method": "notifications/progress", "params": {}})
    catalog.tools()
    assert catalog.fetches == 1
    catalog.on_notification({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
    catalog.tools()
    assert catalog.fetches == 2


def test_catalog_fetches_every_page():
    server = FakeServer({None: {"tools": [tool("a")], "nextCursor": "n", "ttlMs": 1000}, "n": {"tools": [tool("b")], "ttlMs": 1000}})
    assert [t["name"] for t in ToolCatalog(server, Clock()).tools()] == ["a", "b"]
