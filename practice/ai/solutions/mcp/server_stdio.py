"""The JSON-RPC envelope and the stdio transport of a stateless MCP server (revision 2026-07-28), by hand.

Run it as a program and it is a real stdio MCP server: it reads one JSON-RPC message per line from stdin,
writes one response per line to stdout, logs to stderr, and exits when stdin closes.

    python server_stdio.py < requests.jsonl

What the specification requires of the envelope (Base Protocol, Versioning, stdio transport):

- A request has ``jsonrpc: "2.0"``, a string or integer ``id`` (MCP: never ``null``) and a string ``method``.
  A message without ``id`` is a notification: the receiver MUST NOT respond.
- 2026-07-28 has no ``initialize`` handshake. Every request carries in ``params._meta``:
  ``io.modelcontextprotocol/protocolVersion`` and ``io.modelcontextprotocol/clientCapabilities``
  (required) and ``io.modelcontextprotocol/clientInfo`` (optional). A missing required field is ``-32602``;
  a version the server does not support is ``-32022`` with ``data: {"supported": [...], "requested": ...}``.
- Every result has ``resultType`` and (SHOULD) ``_meta["io.modelcontextprotocol/serverInfo"]``.
- ``server/discover`` MUST be implemented: supported versions, capabilities, identity, instructions.
- stdout carries only MCP messages, one per line, never with an embedded newline; logs go to stderr.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, TextIO

PROTOCOL_VERSION = "2026-07-28"
SUPPORTED_VERSIONS = [PROTOCOL_VERSION]
SERVER_INFO = {"name": "sandpay-ledger", "version": "0.3.0"}
INSTRUCTIONS = "SandPay ledger tools. Amounts are integers in minor units (cents); ids look like m_204."

PV = "io.modelcontextprotocol/protocolVersion"
CAPS = "io.modelcontextprotocol/clientCapabilities"
SERVER_INFO_KEY = "io.modelcontextprotocol/serverInfo"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNSUPPORTED_PROTOCOL_VERSION = -32022

BALANCES = {"m_204": {"available_minor": 312050, "currency": "EUR"}, "m_311": {"available_minor": 0, "currency": "GBP"}}


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


# --- methods (given) - each takes params and returns a result without resultType/_meta --------------------


def discover(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "supportedVersions": SUPPORTED_VERSIONS,
        "capabilities": {"tools": {}},
        "instructions": INSTRUCTIONS,
        "ttlMs": 3_600_000,
        "cacheScope": "public",
    }


BALANCE_TOOL = {
    "name": "get_balance",
    "description": "Available balance of one SandPay merchant, in minor units, with its currency.",
    "inputSchema": {
        "type": "object",
        "properties": {"merchant_id": {"type": "string", "pattern": "^m_[0-9]{3}$"}},
        "required": ["merchant_id"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True},
}


def tools_list(params: dict[str, Any]) -> dict[str, Any]:
    return {"tools": [BALANCE_TOOL], "ttlMs": 300_000, "cacheScope": "public"}


def tools_call(params: dict[str, Any]) -> dict[str, Any]:
    if params.get("name") != "get_balance":
        raise RpcError(INVALID_PARAMS, f"Unknown tool: {params.get('name')}")
    merchant = (params.get("arguments") or {}).get("merchant_id")
    if merchant not in BALANCES:
        return {"content": [{"type": "text", "text": f"No SandPay merchant {merchant!r}."}], "isError": True}
    balance = BALANCES[merchant]
    return {
        "content": [{"type": "text", "text": json.dumps(balance, sort_keys=True)}],
        "structuredContent": balance,
        "isError": False,
    }


METHODS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "server/discover": discover,
    "tools/list": tools_list,
    "tools/call": tools_call,
}


# --- the envelope -------------------------------------------------------------------------------------------


def error_response(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


def check_meta(params: dict[str, Any]) -> None:
    """Raise RpcError unless ``params._meta`` has a supported protocol version and client capabilities.
    Order of checks: ``_meta`` is an object, the version is present (a string), the capabilities are present
    (an object), then the version is supported."""
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        raise RpcError(INVALID_PARAMS, "Missing params._meta (2026-07-28 requests carry their protocol metadata)")
    version = meta.get(PV)
    if not isinstance(version, str):
        raise RpcError(INVALID_PARAMS, f"Missing required _meta field {PV}")
    if not isinstance(meta.get(CAPS), dict):
        raise RpcError(INVALID_PARAMS, f"Missing required _meta field {CAPS}")
    if version not in SUPPORTED_VERSIONS:
        raise RpcError(
            UNSUPPORTED_PROTOCOL_VERSION,
            "Unsupported protocol version",
            {"supported": SUPPORTED_VERSIONS, "requested": version},
        )


def handle(message: Any) -> dict[str, Any] | None:
    """Turn one decoded JSON-RPC message into its response, or ``None`` for a notification.

    1. Not an object, ``jsonrpc`` not "2.0", or ``method`` not a string -> ``-32600`` with the message's id
       when it is a string or integer, else ``null``.
    2. No ``id`` key -> a notification: return ``None`` (even for unknown methods).
    3. ``id`` that is null, a bool or not a string/integer -> ``-32600`` with id ``null``.
    4. ``params`` present but not an object -> ``-32602``.
    5. ``initialize`` -> ``-32602`` naming the supported versions in the message and ``data.supported``
       (a modern-only server SHOULD name them: legacy clients have no other diagnostic).
    6. ``check_meta``; unknown method -> ``-32601``; run the method; an RpcError becomes that error.
    7. Any other exception -> ``-32603`` "Internal error" and nothing about it (log it to stderr).
    8. Success -> ``{"jsonrpc", "id", "result"}`` where the result gets ``resultType: "complete"`` and
       ``_meta: {serverInfo}`` added.
    """
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        rid = message.get("id") if isinstance(message, dict) else None
        if isinstance(rid, bool) or not isinstance(rid, (str, int)):
            rid = None
        return error_response(rid, INVALID_REQUEST, "Invalid Request")
    if "id" not in message:
        return None
    rid = message["id"]
    if isinstance(rid, bool) or not isinstance(rid, (str, int)):
        return error_response(None, INVALID_REQUEST, "Invalid Request: id must be a string or an integer")
    params = message.get("params", {})
    if not isinstance(params, dict):
        return error_response(rid, INVALID_PARAMS, "params must be an object")
    method = message["method"]
    if method == "initialize":
        supported = ", ".join(SUPPORTED_VERSIONS)
        return error_response(
            rid,
            INVALID_PARAMS,
            f"This server speaks MCP {supported} only and has no initialize handshake",
            {"supported": SUPPORTED_VERSIONS},
        )
    try:
        check_meta(params)
        if method not in METHODS:
            raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
        result = METHODS[method](params)
    except RpcError as exc:
        return error_response(rid, exc.code, exc.message, exc.data)
    except Exception as exc:
        print(f"internal error in {method}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return error_response(rid, INTERNAL_ERROR, "Internal error")
    return {"jsonrpc": "2.0", "id": rid, "result": {"resultType": "complete", **result, "_meta": {SERVER_INFO_KEY: SERVER_INFO}}}


def serve(inp: TextIO, out: TextIO, err: TextIO) -> int:
    """Read newline-delimited JSON-RPC from ``inp`` until EOF; write each response as one compact JSON line
    to ``out`` and flush; skip blank lines; answer a line that is not JSON with ``-32700`` and id ``null``;
    log ``"<method> -> ok|error <code>"`` (or ``"parse error"``) per message to ``err``. Return the number of
    responses written."""
    written = 0
    for line in inp:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response: dict[str, Any] | None = error_response(None, PARSE_ERROR, "Parse error")
            print("parse error", file=err)
        else:
            response = handle(message)
            method = message.get("method") if isinstance(message, dict) else None
            if response is None:
                print(f"{method} (notification)", file=err)
            elif "error" in response:
                print(f"{method} -> error {response['error']['code']}", file=err)
            else:
                print(f"{method} -> ok", file=err)
        if response is not None:
            out.write(json.dumps(response, separators=(",", ":")) + "\n")
            out.flush()
            written += 1
    return written


if __name__ == "__main__":
    serve(sys.stdin, sys.stdout, sys.stderr)
