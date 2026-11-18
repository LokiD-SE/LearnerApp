"""JSON-RPC 2.0 messages and the MCP stdio framing - one message per line.

Running example: SandPay (a fictional payments company) runs a local MCP server that a support desk
assistant starts as a subprocess. The two talk over the server's stdin and stdout.

What the MCP specification (revision 2026-07-28) says, and this file enforces:

- Basic, Messages: every message is JSON-RPC 2.0. A request has ``jsonrpc: "2.0"``, an ``id`` that is a
  string or an integer and "MUST NOT be null", and a ``method``. A notification has a ``method`` and
  "MUST NOT include an ID". A response has the request's ``id`` and either ``result`` or ``error``
  (``code`` an integer, ``message`` a string).
- Transports, stdio: "Messages are delimited by newlines, and MUST NOT contain embedded newlines", and the
  server "MUST NOT write anything to its stdout that is not a valid MCP message".
- Transports, Messages: "JSON-RPC messages MUST be UTF-8 encoded."

Bytes arrive from a pipe in arbitrary chunks: a chunk can end in the middle of a message - or in the middle
of a multi-byte UTF-8 character - so the decoder must buffer until it sees a newline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# JSON-RPC 2.0, section 5.1 (the codes MCP uses for general protocol failures).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600


class FramingError(ValueError):
    """A message cannot be written on the stdio transport."""


def encode_message(message: dict[str, Any]) -> bytes:
    """Return ``message`` as one stdio frame: compact UTF-8 JSON followed by exactly one ``b"\\n"``.

    ``json.dumps`` escapes newlines inside strings as ``\\n``, so the frame never contains a raw newline.
    Non-ASCII text is kept as UTF-8 (``ensure_ascii=False``), not escaped. Raise ``FramingError`` for
    anything that is not a JSON object.
    """
    if not isinstance(message, dict):
        raise FramingError(f"a JSON-RPC message is a JSON object, not {type(message).__name__}")
    text = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    return text.encode("utf-8") + b"\n"


def _is_valid_id(value: Any) -> bool:
    # bool is a subclass of int in Python, but JSON true/false is not an id.
    return isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool))


def classify(message: Any) -> tuple[str, str]:
    """Return ``(kind, reason)`` for a decoded JSON value.

    ``kind`` is ``"request"``, ``"notification"``, ``"result"``, ``"error"`` or ``"invalid"``; ``reason``
    is ``""`` unless the kind is ``"invalid"``. Check in this order and report the first problem:

    1. not an object -> ``"not an object"``
    2. ``jsonrpc`` is not ``"2.0"`` -> ``"jsonrpc must be '2.0'"``
    3. has ``method``: it must be a string (``"method must be a string"``). Without an ``id`` key it is a
       notification; with one, the id must be a string or integer (``"id must be a string or integer"`` -
       this also rejects ``null``) and it is a request.
    4. has ``result`` or ``error`` (not both - ``"result and error are exclusive"``): the id must be valid,
       except that an error response may omit the id or have it null (the id could not be read). An error
       needs an integer ``code`` and a string ``message`` (``"error needs integer code and string message"``).
    5. anything else -> ``"no method, result or error"``
    """
    if not isinstance(message, dict):
        return "invalid", "not an object"
    if message.get("jsonrpc") != "2.0":
        return "invalid", "jsonrpc must be '2.0'"
    if "method" in message:
        if not isinstance(message["method"], str):
            return "invalid", "method must be a string"
        if "id" not in message:
            return "notification", ""
        if not _is_valid_id(message["id"]):
            return "invalid", "id must be a string or integer"
        return "request", ""
    has_result, has_error = "result" in message, "error" in message
    if has_result and has_error:
        return "invalid", "result and error are exclusive"
    if has_result:
        if not _is_valid_id(message.get("id")):
            return "invalid", "id must be a string or integer"
        return "result", ""
    if has_error:
        if message.get("id") is not None and not _is_valid_id(message["id"]):
            return "invalid", "id must be a string or integer"
        err = message["error"]
        if (
            not isinstance(err, dict)
            or not isinstance(err.get("code"), int)
            or isinstance(err.get("code"), bool)
            or not isinstance(err.get("message"), str)
        ):
            return "invalid", "error needs integer code and string message"
        return "error", ""
    return "invalid", "no method, result or error"


@dataclass
class Frame:
    """One line read from the stream: the decoded message, or the error a peer should be told about."""

    message: dict[str, Any] | None
    kind: str
    error: dict[str, Any] | None = None


@dataclass
class LineDecoder:
    """Turns arbitrary byte chunks from a pipe into frames, one per newline-terminated line."""

    _buffer: bytearray = field(default_factory=bytearray)

    def feed(self, chunk: bytes) -> list[Frame]:
        """Add ``chunk`` and return a ``Frame`` for every complete line it finished.

        - Keep the bytes after the last ``b"\\n"`` for the next call; decode only complete lines, so a UTF-8
          character split across chunks is never decoded half-way.
        - Strip one trailing ``b"\\r"`` from a line (a peer on Windows may write CRLF).
        - Invalid UTF-8 or invalid JSON -> ``Frame(None, "invalid", error)`` with a JSON-RPC error response
          ``{"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "Parse error"}}``.
        - Valid JSON that ``classify`` calls invalid -> ``Frame(value, "invalid", error)`` with code
          ``INVALID_REQUEST``, message ``"Invalid Request"``, ``data`` = the reason, and ``id`` = the
          message's id when it is a valid id, else ``None``.
        - Otherwise ``Frame(message, kind)``.
        """
        self._buffer.extend(chunk)
        frames: list[Frame] = []
        while True:
            newline = self._buffer.find(b"\n")
            if newline < 0:
                return frames
            line = bytes(self._buffer[:newline])
            del self._buffer[: newline + 1]
            if line.endswith(b"\r"):
                line = line[:-1]
            frames.append(self._decode_line(line))

    @property
    def pending(self) -> int:
        """Bytes received but not yet terminated by a newline."""
        return len(self._buffer)

    @staticmethod
    def _decode_line(line: bytes) -> Frame:
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            error = {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "Parse error"}}
            return Frame(None, "invalid", error)
        kind, reason = classify(value)
        if kind == "invalid":
            msg_id = value.get("id") if isinstance(value, dict) and _is_valid_id(value.get("id")) else None
            error = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": INVALID_REQUEST, "message": "Invalid Request", "data": reason},
            }
            return Frame(value, "invalid", error)
        return Frame(value, kind)
