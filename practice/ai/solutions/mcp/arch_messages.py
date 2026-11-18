"""Classify JSON-RPC 2.0 messages the way an MCP (protocol version 2026-07-28) peer must.

JSON-RPC 2.0 (jsonrpc.org/specification) defines requests, notifications and responses; MCP narrows it:
request ids must not be null, params must be an object, batches are not supported (removed in 2025-06-18),
results carry a ``resultType``, and in 2026-07-28 only clients send requests and only servers send responses.
"""

from __future__ import annotations

KNOWN_RESULT_TYPES = ("complete", "input_required")


class InvalidMessage(ValueError):
    """The message breaks JSON-RPC 2.0 or the MCP rules on top of it."""


def classify_message(msg) -> str:
    """Return "request", "notification", "result" or "error"; raise InvalidMessage otherwise."""
    if isinstance(msg, list):
        raise InvalidMessage("batch: MCP does not support JSON-RPC batches")
    if not isinstance(msg, dict):
        raise InvalidMessage("not an object")
    if msg.get("jsonrpc") != "2.0":
        raise InvalidMessage('jsonrpc must be exactly "2.0"')
    has_method = "method" in msg
    has_result = "result" in msg
    has_error = "error" in msg
    if has_method:
        if has_result or has_error:
            raise InvalidMessage("a message cannot be both a request and a response")
        if not isinstance(msg["method"], str):
            raise InvalidMessage("method must be a string")
        if "params" in msg and not isinstance(msg["params"], dict):
            raise InvalidMessage("params must be an object in MCP")
        if "id" not in msg:
            return "notification"
        if msg["id"] is None:
            raise InvalidMessage("request id must not be null in MCP")
        if isinstance(msg["id"], bool) or not isinstance(msg["id"], (str, int)):
            raise InvalidMessage("request id must be a string or an integer")
        return "request"
    if has_result and has_error:
        raise InvalidMessage("a response has result or error, never both")
    if has_result:
        if "id" not in msg or msg["id"] is None:
            raise InvalidMessage("a result must carry the id of its request")
        return "result"
    if has_error:
        err = msg["error"]
        if not isinstance(err, dict) or "code" not in err or "message" not in err:
            raise InvalidMessage("error needs a code and a message")
        if isinstance(err["code"], bool) or not isinstance(err["code"], int):
            raise InvalidMessage("error code must be an integer")
        return "error"
    raise InvalidMessage("no method, result or error")


def result_type(response: dict) -> str:
    """The resultType of a result response: absent means "complete" (earlier servers); unknown is invalid."""
    if classify_message(response) != "result":
        raise InvalidMessage("not a result response")
    value = response["result"].get("resultType", "complete")
    if value not in KNOWN_RESULT_TYPES:
        raise InvalidMessage(f"unknown resultType {value!r}")
    return value


def may_send(sender: str, kind: str) -> bool:
    """In 2026-07-28 clients send requests and notifications; servers send responses and notifications."""
    allowed = {
        "client": {"request", "notification"},
        "server": {"result", "error", "notification"},
    }
    if sender not in allowed:
        raise ValueError(f"unknown sender {sender!r}")
    return kind in allowed[sender]
