import io
import json
import subprocess
import sys

import pytest
from mcp import server_stdio
from mcp.server_stdio import PROTOCOL_VERSION, SERVER_INFO, handle, serve

pytestmark = pytest.mark.exercise

META = {
    "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "pytest-client", "version": "1.0"},
}


def req(rid, method, **params):
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": {"_meta": META, **params}}


# --- handle -------------------------------------------------------------------------------------------------


def test_discover_result_has_versions_capabilities_identity_and_cache_hints():
    resp = handle(req("d-1", "server/discover"))
    assert resp["jsonrpc"] == "2.0" and resp["id"] == "d-1"
    result = resp["result"]
    assert result["resultType"] == "complete"
    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["capabilities"] == {"tools": {}}
    assert result["_meta"] == {"io.modelcontextprotocol/serverInfo": SERVER_INFO}
    assert result["ttlMs"] > 0 and result["cacheScope"] == "public"


def test_tools_call_success_and_tool_error():
    ok = handle(req(2, "tools/call", name="get_balance", arguments={"merchant_id": "m_204"}))
    assert ok["result"]["structuredContent"] == {"available_minor": 312050, "currency": "EUR"}
    assert ok["result"]["isError"] is False and ok["result"]["resultType"] == "complete"
    bad = handle(req(3, "tools/call", name="get_balance", arguments={"merchant_id": "m_000"}))
    assert bad["result"]["isError"] is True


def test_unknown_tool_is_a_jsonrpc_error():
    resp = handle(req(4, "tools/call", name="drop_ledger", arguments={}))
    assert resp == {"jsonrpc": "2.0", "id": 4, "error": {"code": -32602, "message": "Unknown tool: drop_ledger"}}


def test_notifications_get_no_response():
    assert handle({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 3}}) is None
    assert handle({"jsonrpc": "2.0", "method": "anything/at/all"}) is None


@pytest.mark.parametrize(
    "message, rid",
    [
        ([1, 2], None),
        ({"jsonrpc": "1.0", "id": 5, "method": "tools/list"}, 5),
        ({"jsonrpc": "2.0", "id": "x", "method": 7}, "x"),
        ({"jsonrpc": "2.0", "id": True, "method": 7}, None),
    ],
)
def test_invalid_requests(message, rid):
    resp = handle(message)
    assert resp["id"] == rid and resp["error"]["code"] == -32600


@pytest.mark.parametrize("bad_id", [None, True, 1.5, {"n": 1}])
def test_ids_must_be_strings_or_integers(bad_id):
    message = req(0, "tools/list")
    message["id"] = bad_id
    resp = handle(message)
    assert resp["id"] is None and resp["error"]["code"] == -32600


def test_params_must_be_an_object():
    resp = handle({"jsonrpc": "2.0", "id": 9, "method": "tools/list", "params": [1]})
    assert resp["error"]["code"] == -32602 and resp["id"] == 9


@pytest.mark.parametrize("drop", ["_meta", "io.modelcontextprotocol/protocolVersion", "io.modelcontextprotocol/clientCapabilities"])
def test_missing_required_meta_is_invalid_params(drop):
    message = req(10, "tools/list")
    if drop == "_meta":
        del message["params"]["_meta"]
    else:
        message["params"]["_meta"] = {k: v for k, v in META.items() if k != drop}
    resp = handle(message)
    assert resp["error"]["code"] == -32602 and resp["id"] == 10


def test_client_info_is_optional():
    message = req(11, "tools/list")
    message["params"]["_meta"] = {k: v for k, v in META.items() if not k.endswith("clientInfo")}
    assert "result" in handle(message)


def test_unsupported_version_lists_the_supported_ones():
    message = req(12, "tools/list")
    message["params"]["_meta"] = {**META, "io.modelcontextprotocol/protocolVersion": "1900-01-01"}
    assert handle(message)["error"] == {
        "code": -32022,
        "message": "Unsupported protocol version",
        "data": {"supported": [PROTOCOL_VERSION], "requested": "1900-01-01"},
    }


def test_legacy_initialize_names_the_supported_versions():
    resp = handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}})
    assert resp["error"]["code"] == -32602
    assert PROTOCOL_VERSION in resp["error"]["message"]
    assert resp["error"]["data"] == {"supported": [PROTOCOL_VERSION]}


def test_unknown_method_is_method_not_found():
    assert handle(req(13, "resources/list"))["error"]["code"] == -32601


def test_a_crash_becomes_an_internal_error_without_details(monkeypatch):
    def boom(params):
        raise RuntimeError("password=hunter2 in the config")

    monkeypatch.setitem(server_stdio.METHODS, "tools/list", boom)
    resp = handle(req(14, "tools/list"))
    assert resp == {"jsonrpc": "2.0", "id": 14, "error": {"code": -32603, "message": "Internal error"}}


# --- serve, in memory ---------------------------------------------------------------------------------------


def run_serve(lines):
    out, err = io.StringIO(), io.StringIO()
    count = serve(io.StringIO("".join(lines)), out, err)
    return count, out.getvalue(), err.getvalue()


def test_serve_writes_one_compact_line_per_response_and_logs_to_stderr():
    lines = [
        json.dumps(req(1, "server/discover")) + "\n",
        "\n",
        json.dumps({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}}) + "\n",
        "{not json\n",
        json.dumps(req(2, "tools/list")) + "\n",
    ]
    count, out, err = run_serve(lines)
    responses = [json.loads(line) for line in out.splitlines()]
    assert count == 3 and len(responses) == 3
    assert [r.get("id") for r in responses] == [1, None, 2]
    assert responses[1]["error"]["code"] == -32700
    assert all(": " not in line and ", " not in line for line in out.splitlines()[:1])
    assert "server/discover -> ok" in err and "parse error" in err


# --- serve, as a real subprocess ----------------------------------------------------------------------------


def test_runs_as_a_stdio_server_process_and_exits_on_eof():
    lines = [
        json.dumps(req("a", "server/discover")),
        json.dumps(req("b", "tools/call", name="get_balance", arguments={"merchant_id": "m_311"})),
        json.dumps({"jsonrpc": "2.0", "id": "c", "method": "initialize", "params": {}}),
    ]
    proc = subprocess.run(
        [sys.executable, server_stdio.__file__],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0
    out_lines = proc.stdout.splitlines()
    assert len(out_lines) == 3
    responses = [json.loads(line) for line in out_lines]  # every stdout line is a JSON-RPC message
    assert [r["id"] for r in responses] == ["a", "b", "c"]
    assert responses[1]["result"]["structuredContent"]["currency"] == "GBP"
    assert "error" in responses[2]
    assert "tools/call -> ok" in proc.stderr
