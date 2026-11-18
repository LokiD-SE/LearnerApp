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
    """Return "request", "notification", "result" or "error"; raise InvalidMessage otherwise.

    TODO - check in this order, raising InvalidMessage with a message containing the quoted word:
    - a list is a batch: "batch"; anything else that is not a dict: "object"
    - ``jsonrpc`` must be exactly "2.0": '"2.0"'
    - with ``method``: not also result/error ("never both" style message is fine), method a str ("string"),
      params, if present, a dict ("object"); no ``id`` -> "notification"; id None -> "null";
      id must be str or int but not bool ("string or an integer") -> "request"
    - result and error together: "never both"
    - result: needs a non-null id ("id") -> "result"
    - error: an object with "code" and "message" ("code"), code an int and not bool ("integer") -> "error"
      (an error MAY have a null id: JSON-RPC 2.0 section 5)
    - none of method/result/error: "no method"
    """
    raise NotImplementedError("classify_message")


def result_type(response: dict) -> str:
    """The resultType of a result response.

    TODO: raise InvalidMessage if ``response`` is not a result; an absent resultType means "complete"
    (servers on earlier protocol versions); a value not in KNOWN_RESULT_TYPES is invalid ("resultType").
    """
    raise NotImplementedError("result_type")


def may_send(sender: str, kind: str) -> bool:
    """May ``sender`` ("client" or "server") send a message of ``kind``?

    TODO: in 2026-07-28 clients send requests and notifications; servers send results, errors and
    notifications. Any other sender raises ValueError.
    """
    raise NotImplementedError("may_send")
