import pytest
from mcp.lifecycle_negotiation import (
    CLIENT_CAPABILITIES_KEY,
    PROTOCOL_VERSION_KEY,
    check_request_meta,
    choose_version,
    classify_probe_reply,
    client_accepts_legacy,
    negotiate_legacy,
)

pytestmark = pytest.mark.exercise

SUPPORTED = ["2026-07-28", "2025-11-25"]


def call(meta, request_id=4):
    params = {"name": "find_merchant", "arguments": {"query": "m-204"}}
    if meta is not None:
        params["_meta"] = meta
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": params}


def test_a_complete_modern_request_passes():
    meta = {PROTOCOL_VERSION_KEY: "2026-07-28", CLIENT_CAPABILITIES_KEY: {}}
    assert check_request_meta(call(meta), SUPPORTED) is None


def test_missing_meta_is_invalid_params_listing_both_keys():
    assert check_request_meta(call(None), SUPPORTED) == {
        "jsonrpc": "2.0",
        "id": 4,
        "error": {
            "code": -32602,
            "message": "Invalid params",
            "data": {"missing": [PROTOCOL_VERSION_KEY, CLIENT_CAPABILITIES_KEY]},
        },
    }


def test_capabilities_are_required_even_when_empty():
    reply = check_request_meta(call({PROTOCOL_VERSION_KEY: "2026-07-28"}), SUPPORTED)
    assert reply["error"]["code"] == -32602
    assert reply["error"]["data"] == {"missing": [CLIENT_CAPABILITIES_KEY]}


def test_wrong_types_count_as_missing():
    reply = check_request_meta(call({PROTOCOL_VERSION_KEY: 20260728, CLIENT_CAPABILITIES_KEY: []}), SUPPORTED)
    assert reply["error"]["data"] == {"missing": [PROTOCOL_VERSION_KEY, CLIENT_CAPABILITIES_KEY]}


def test_a_request_without_params_is_invalid():
    reply = check_request_meta({"jsonrpc": "2.0", "id": "x", "method": "tools/list"}, SUPPORTED)
    assert reply["id"] == "x"
    assert reply["error"]["code"] == -32602


def test_unknown_version_is_unsupported_with_the_list():
    reply = check_request_meta(call({PROTOCOL_VERSION_KEY: "1900-01-01", CLIENT_CAPABILITIES_KEY: {}}), SUPPORTED)
    assert reply == {
        "jsonrpc": "2.0",
        "id": 4,
        "error": {
            "code": -32022,
            "message": "Unsupported protocol version",
            "data": {"supported": SUPPORTED, "requested": "1900-01-01"},
        },
    }


@pytest.mark.parametrize(
    "client, server, expected",
    [
        (["2026-07-28", "2025-11-25"], ["2025-11-25", "2025-06-18"], "2025-11-25"),
        (["2025-06-18", "2026-07-28"], ["2026-07-28", "2025-06-18"], "2026-07-28"),
        (["2026-07-28"], ["2025-11-25"], None),
    ],
)
def test_choose_version_picks_the_newest_common(client, server, expected):
    assert choose_version(client, server) == expected


@pytest.mark.parametrize(
    "reply, era",
    [
        ({"jsonrpc": "2.0", "id": 1, "result": {"resultType": "complete", "supportedVersions": ["2026-07-28"], "capabilities": {}}}, "modern"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": -32022, "message": "Unsupported protocol version", "data": {"supported": ["2026-07-28"]}}}, "modern-retry"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": -32020, "message": "Header mismatch"}}, "modern-retry"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Method not found"}}, "legacy"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "Server not initialized"}}, "legacy"),
        ({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "Bad Request: Server not initialized"}}, "legacy"),
        ({"jsonrpc": "2.0", "id": 1, "result": {}}, "legacy"),
        (None, "legacy"),
    ],
)
def test_probe_reply_classification(reply, era):
    assert classify_probe_reply(reply) == era


def test_legacy_server_echoes_a_supported_version():
    assert negotiate_legacy("2025-06-18", ["2025-11-25", "2025-06-18", "2025-03-26"]) == "2025-06-18"


def test_legacy_server_answers_its_latest_otherwise():
    assert negotiate_legacy("2026-07-28", ["2025-03-26", "2025-11-25", "2025-06-18"]) == "2025-11-25"


def test_legacy_client_disconnects_on_a_version_it_does_not_speak():
    assert client_accepts_legacy("2025-11-25", ["2025-11-25", "2025-06-18"]) is True
    assert client_accepts_legacy("2024-11-05", ["2025-11-25", "2025-06-18"]) is False
