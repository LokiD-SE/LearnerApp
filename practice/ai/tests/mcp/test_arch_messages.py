import pytest
from mcp.arch_messages import InvalidMessage, classify_message, may_send, result_type

pytestmark = pytest.mark.exercise

META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}


def test_request():
    assert classify_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": META}}) == "request"


def test_request_with_string_id_and_no_params():
    assert classify_message({"jsonrpc": "2.0", "id": "discover-1", "method": "server/discover"}) == "request"


def test_notification_has_no_id():
    msg = {"jsonrpc": "2.0", "method": "notifications/tools/list_changed", "params": {}}
    assert classify_message(msg) == "notification"


def test_result_and_error():
    assert classify_message({"jsonrpc": "2.0", "id": 1, "result": {"resultType": "complete"}}) == "result"
    assert classify_message({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}) == "error"


def test_error_with_null_id_is_allowed():
    # JSON-RPC 2.0 section 5: the id is null when it could not be read (parse error, invalid request).
    assert classify_message({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}) == "error"


@pytest.mark.parametrize(
    "msg, reason",
    [
        ([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}], "batch"),
        ({"jsonrpc": "1.0", "id": 1, "method": "tools/list"}, "2.0"),
        ({"id": 1, "method": "tools/list"}, "2.0"),
        ({"jsonrpc": "2.0", "id": None, "method": "tools/list"}, "null"),
        ({"jsonrpc": "2.0", "id": 1.5, "method": "tools/list"}, "string or an integer"),
        ({"jsonrpc": "2.0", "id": True, "method": "tools/list"}, "string or an integer"),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": ["get_payment"]}, "object"),
        ({"jsonrpc": "2.0", "id": 1, "method": 7}, "string"),
        ({"jsonrpc": "2.0", "id": 1, "result": {}, "error": {"code": 1, "message": "x"}}, "never both"),
        ({"jsonrpc": "2.0", "result": {}}, "id"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"message": "no code"}}, "code"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": "-32601", "message": "x"}}, "integer"),
        ({"jsonrpc": "2.0", "id": 1}, "no method"),
        ("tools/list", "object"),
    ],
)
def test_invalid_messages(msg, reason):
    with pytest.raises(InvalidMessage, match=reason):
        classify_message(msg)


def test_result_type():
    assert result_type({"jsonrpc": "2.0", "id": 1, "result": {"resultType": "input_required"}}) == "input_required"
    # Earlier protocol versions do not send resultType: treat as complete.
    assert result_type({"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}) == "complete"
    with pytest.raises(InvalidMessage, match="resultType"):
        result_type({"jsonrpc": "2.0", "id": 1, "result": {"resultType": "partial"}})
    with pytest.raises(InvalidMessage):
        result_type({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "x"}})


def test_directions():
    assert may_send("client", "request") and may_send("client", "notification")
    assert not may_send("client", "result") and not may_send("client", "error")
    assert may_send("server", "result") and may_send("server", "error") and may_send("server", "notification")
    assert not may_send("server", "request")
    with pytest.raises(ValueError):
        may_send("host", "request")
