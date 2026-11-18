"""Exercise: the JSON-RPC layer of an MCP client (lesson: Building an MCP client).

Runs against a real subprocess, support/mcp_client_fixture.py, which speaks MCP 2026-07-28 over stdio.
"""

import json
import sys
from pathlib import Path

import pytest
from mcp.client_rpc import (
    McpError,
    ProtocolError,
    RequestTimeout,
    RpcClient,
    StdioTransport,
    request_meta,
)

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
INFO = {"name": "sandpay-support-host", "version": "1.0.0"}


class Recorder:
    """Wraps a transport and remembers every line the client sends."""

    def __init__(self, transport):
        self.transport = transport
        self.sent = []

    def send(self, line):
        self.sent.append(line)
        self.transport.send(line)

    def receive(self, timeout):
        return self.transport.receive(timeout)


@pytest.fixture
def server():
    transport = StdioTransport([sys.executable, FIXTURE])
    yield transport
    shutdown(transport)


def make_client(transport, **kwargs):
    rec = Recorder(transport)
    return RpcClient(rec, client_info=INFO, capabilities=kwargs.pop("capabilities", {}), **kwargs), rec


def test_request_meta_has_the_required_fields():
    meta = request_meta(INFO, {"elicitation": {}})
    assert meta == {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientInfo": INFO,
        "io.modelcontextprotocol/clientCapabilities": {"elicitation": {}},
    }


def test_discover_returns_the_complete_result(server):
    client, rec = make_client(server)
    result = client.request("server/discover")
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == ["2026-07-28"]
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "sandpay-payouts"
    sent = json.loads(rec.sent[0])
    assert sent["jsonrpc"] == "2.0" and sent["method"] == "server/discover"
    assert sent["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] == "2026-07-28"
    assert sent["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"] == {}


def test_every_request_gets_a_new_integer_id(server):
    client, rec = make_client(server)
    client.request("server/discover")
    client.request("tools/list")
    client.request("tools/list")
    ids = [json.loads(line)["id"] for line in rec.sent]
    assert len(set(ids)) == 3
    assert all(isinstance(i, int) for i in ids)


def test_messages_are_single_lines(server):
    client, rec = make_client(server)
    client.request("tools/call", {"name": "get_payout", "arguments": {"payout_id": "po_1039\nx"}})
    assert all("\n" not in line for line in rec.sent)


def test_tool_result_and_tool_error_are_results(server):
    client, _ = make_client(server)
    ok = client.request("tools/call", {"name": "get_payout", "arguments": {"payout_id": "po_1039"}})
    assert ok["isError"] is False and ok["structuredContent"]["status"] == "paid"
    bad = client.request("tools/call", {"name": "get_payout", "arguments": {"payout_id": "po_9"}})
    assert bad["isError"] is True and "not found" in bad["content"][0]["text"]


def test_protocol_error_raises_mcp_error(server):
    client, _ = make_client(server)
    with pytest.raises(McpError) as info:
        client.request("tools/call", {"name": "delete_everything", "arguments": {}})
    assert info.value.code == -32602
    assert "Unknown tool" in info.value.message


def test_unsupported_version_error_carries_the_supported_list(server):
    client, _ = make_client(server, protocol_version="2099-01-01")
    with pytest.raises(McpError) as info:
        client.request("server/discover")
    assert info.value.code == -32022
    assert info.value.data["supported"] == ["2026-07-28"]


def test_notifications_before_the_response_are_handed_over(server):
    seen = []
    client, _ = make_client(server, on_notification=seen.append)
    result = client.request("tools/call", {"name": "slow_report", "arguments": {"seconds": 0}}, meta={"progressToken": "rep-1"})
    assert result["content"][0]["text"].startswith("Reconciliation report")
    assert seen and seen[0]["method"] == "notifications/progress"
    assert seen[0]["params"]["progressToken"] == "rep-1"


def test_timeout_sends_cancelled_and_raises(server):
    client, rec = make_client(server)
    with pytest.raises(RequestTimeout):
        client.request("tools/call", {"name": "slow_report", "arguments": {"seconds": 0.2}}, timeout=0.05)
    cancel = json.loads(rec.sent[-1])
    assert cancel["method"] == "notifications/cancelled"
    assert "id" not in cancel
    assert cancel["params"]["requestId"] == json.loads(rec.sent[0])["id"]
    # the server honours the cancellation, so the next request gets its own answer
    assert client.request("server/discover")["supportedVersions"] == ["2026-07-28"]
    assert client.ignored == []


def test_late_reply_to_a_cancelled_request_is_ignored():
    transport = StdioTransport([sys.executable, FIXTURE, "--ignore-cancel"])
    try:
        client, rec = make_client(transport)
        with pytest.raises(RequestTimeout):
            client.request("tools/call", {"name": "slow_report", "arguments": {"seconds": 0.15}}, timeout=0.05)
        first_id = json.loads(rec.sent[0])["id"]
        result = client.request("server/discover", timeout=2)
        assert result["supportedVersions"] == ["2026-07-28"]
        assert [m["id"] for m in client.ignored] == [first_id]
    finally:
        shutdown(transport)


class FakeTransport:
    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def send(self, line):
        self.sent.append(line)

    def receive(self, timeout):
        return self.replies.pop(0) if self.replies else None


def test_missing_result_type_counts_as_complete():
    fake = FakeTransport(['{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}'])
    client = RpcClient(fake, client_info=INFO, capabilities={})
    assert client.request("tools/list")["resultType"] == "complete"


def test_unknown_result_type_is_a_protocol_error():
    fake = FakeTransport(['{"jsonrpc":"2.0","id":1,"result":{"resultType":"partial"}}'])
    client = RpcClient(fake, client_info=INFO, capabilities={})
    with pytest.raises(ProtocolError):
        client.request("tools/list")


def test_notify_has_no_id():
    fake = FakeTransport([])
    client = RpcClient(fake, client_info=INFO, capabilities={})
    client.notify("notifications/cancelled", {"requestId": 7})
    assert json.loads(fake.sent[0]) == {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 7}}


def test_close_lets_a_good_server_exit_on_eof():
    transport = StdioTransport([sys.executable, FIXTURE])
    try:
        assert transport.close() == 0
    finally:
        shutdown(transport)


def test_close_terminates_a_server_that_ignores_eof():
    transport = StdioTransport([sys.executable, FIXTURE, "--ignore-eof"])
    try:
        code = transport.close(grace=0.2)
        assert code != 0  # terminated by a signal, not a clean exit
        assert transport.process.poll() is not None
    finally:
        if transport.process.poll() is None:
            transport.process.kill()
            transport.process.wait()
