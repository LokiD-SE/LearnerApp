"""The tools half of an MCP server, written by hand: definitions, paginated tools/list and tools/call.

Running example: SandPay (a fictional payments company) exposes its payments ledger to AI assistants through
an MCP server. A tool is a *name*, a *description*, an ``inputSchema`` (JSON Schema) and, optionally, an
``outputSchema`` that its ``structuredContent`` must match.

Everything follows the MCP specification, revision 2026-07-28, "Server Features > Tools" and "Utilities >
Pagination" and "Utilities > Caching". The JSON-RPC envelope (``jsonrpc``, ``id``, ``_meta``) is handled by
``server_stdio.py``; here a request's ``params`` go in and a ``result`` dict comes out, or a
:class:`ProtocolError` is raised for the envelope code to turn into a JSON-RPC error.

The spec's two error paths:

- **Protocol errors** (unknown tool, malformed request, server bugs) are JSON-RPC errors. The model usually
  never sees them.
- **Tool execution errors** (input validation, API failures, business rules) are *results* with
  ``isError: true`` and a message the model can read and act on.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Spec, Tools > Tool Names: 1-128 characters; A-Z, a-z, 0-9, underscore, hyphen and dot SHOULD be the only ones.
TOOL_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class ProtocolError(Exception):
    """Becomes a JSON-RPC error response: ``{"code": ..., "message": ..., "data": ...}``."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def to_error(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return error


class ToolError(Exception):
    """Raised by a tool handler for a failure the model can fix: the message goes back in an isError result."""


# --- A small JSON Schema validator (given) ------------------------------------------------------------------
# The subset of JSON Schema 2020-12 that tool schemas here use: type, properties, required,
# additionalProperties: false, enum, pattern, minimum/maximum, minLength/maxLength and items.

_TYPES: dict[str, Callable[[Any], bool]] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer(),
}


def validate(schema: dict[str, Any], value: Any, path: str = "arguments") -> list[str]:
    """Return every way ``value`` breaks ``schema`` as ``"<path>: <problem>"`` (empty list = valid)."""
    problems: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_TYPES[t](value) for t in types):
            return [f"{path}: expected {' or '.join(types)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: must be one of {schema['enum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            problems.append(f"{path}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{path}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{path}: less than {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{path}: greater than {schema['maximum']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                problems.append(f"{path}.{name}: is required")
        for name, item in value.items():
            if name in props:
                problems.extend(validate(props[name], item, f"{path}.{name}"))
            elif schema.get("additionalProperties") is False:
                problems.append(f"{path}.{name}: is not allowed")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            problems.extend(validate(schema["items"], item, f"{path}[{i}]"))
    return problems


# --- Tools --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]
    title: str | None = None
    output_schema: dict[str, Any] | None = None
    annotations: dict[str, Any] | None = None

    def definition(self) -> dict[str, Any]:
        """The tool as tools/list shows it: camelCase keys, optional fields only when set, never the handler."""
        out: dict[str, Any] = {"name": self.name}
        if self.title is not None:
            out["title"] = self.title
        out["description"] = self.description
        out["inputSchema"] = self.input_schema
        if self.output_schema is not None:
            out["outputSchema"] = self.output_schema
        if self.annotations is not None:
            out["annotations"] = self.annotations
        return out


def encode_cursor(offset: int) -> str:
    """An opaque cursor for the client: base64url of ``"tools:<offset>"`` (clients MUST NOT parse it)."""
    raise NotImplementedError("TODO: implement encode_cursor - see the docstring")


def decode_cursor(cursor: Any) -> int:
    """The offset inside a cursor this server issued; anything else is an Invalid params ProtocolError."""
    raise NotImplementedError("TODO: implement decode_cursor - see the docstring")


@dataclass
class ToolServer:
    page_size: int = 2
    ttl_ms: int = 300_000
    tools: dict[str, Tool] = field(default_factory=dict)
    crashes: list[str] = field(default_factory=list)  # what the operator sees; never sent to the client

    def add_tool(self, tool: Tool) -> None:
        """Register a tool. Raise ``ValueError`` for a name outside TOOL_NAME, a duplicate name, or an
        ``inputSchema`` that is not a JSON object schema (``"type": "object"``)."""
        raise NotImplementedError("TODO: implement add_tool - see the docstring")

    def list_tools(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """The ``tools/list`` result: tools sorted by name, ``page_size`` per page, ``nextCursor`` only when
        more remain, plus ``resultType``, ``ttlMs`` and ``cacheScope: "public"``."""
        raise NotImplementedError("TODO: implement list_tools - see the docstring")

    def call_tool(self, params: Any) -> dict[str, Any]:
        """The ``tools/call`` result - see the module docstring for which failure goes down which path."""
        raise NotImplementedError("TODO: implement call_tool - see the docstring")


def _error_result(message: str) -> dict[str, Any]:
    return {"resultType": "complete", "content": [{"type": "text", "text": message}], "isError": True}


# --- SandPay's tools (the running example) ------------------------------------------------------------------

PAYMENT_ID = {"type": "string", "pattern": "^pay_[0-9]{4,8}$", "description": "SandPay payment id, e.g. pay_1042."}

PAYMENT_OUTPUT = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "merchant_id": {"type": "string"},
        "amount_minor": {"type": "integer", "minimum": 0},
        "currency": {"type": "string", "enum": ["EUR", "GBP", "USD"]},
        "status": {"type": "string", "enum": ["authorised", "captured", "refunded", "partially_refunded"]},
        "refunded_minor": {"type": "integer", "minimum": 0},
    },
    "required": ["id", "merchant_id", "amount_minor", "currency", "status", "refunded_minor"],
    "additionalProperties": False,
}


def sandpay_tools(ledger: dict[str, dict[str, Any]]) -> list[Tool]:
    """Three tools over an in-memory ledger: one read-only lookup, one refund, one listing."""

    def get_payment(payment_id: str) -> dict[str, Any]:
        if payment_id not in ledger:
            raise ToolError(f"No payment {payment_id} in the SandPay ledger. Check the id with the merchant.")
        return dict(ledger[payment_id])

    def refund_payment(payment_id: str, amount_minor: int) -> str:
        payment = ledger.get(payment_id)
        if payment is None:
            raise ToolError(f"No payment {payment_id} in the SandPay ledger.")
        if payment["status"] not in ("captured", "partially_refunded"):
            raise ToolError(f"Payment {payment_id} is {payment['status']}; only captured payments can be refunded.")
        left = payment["amount_minor"] - payment["refunded_minor"]
        if amount_minor > left:
            raise ToolError(
                f"Refund of {amount_minor} exceeds the refundable {left} ({payment['currency']} minor units) "
                f"on {payment_id}."
            )
        payment["refunded_minor"] += amount_minor
        payment["status"] = "refunded" if payment["refunded_minor"] == payment["amount_minor"] else "partially_refunded"
        return f"Refunded {amount_minor} {payment['currency']} minor units on {payment_id}; status {payment['status']}."

    def list_merchant_payments(merchant_id: str) -> str:
        ids = sorted(p for p, row in ledger.items() if row["merchant_id"] == merchant_id)
        return ", ".join(ids) if ids else f"No payments for {merchant_id}."

    return [
        Tool(
            name="get_payment",
            title="Look up a payment",
            description="Look up one SandPay payment by id: merchant, amount in minor units, currency, status "
            "and how much has been refunded.",
            input_schema={
                "type": "object",
                "properties": {"payment_id": PAYMENT_ID},
                "required": ["payment_id"],
                "additionalProperties": False,
            },
            output_schema=PAYMENT_OUTPUT,
            handler=get_payment,
            annotations={"readOnlyHint": True, "openWorldHint": False},
        ),
        Tool(
            name="refund_payment",
            title="Refund a payment",
            description="Refund part or all of a captured SandPay payment. Moves money and cannot be undone; "
            "amount_minor is in minor units (cents).",
            input_schema={
                "type": "object",
                "properties": {
                    "payment_id": PAYMENT_ID,
                    "amount_minor": {"type": "integer", "minimum": 1, "description": "Amount in minor units."},
                },
                "required": ["payment_id", "amount_minor"],
                "additionalProperties": False,
            },
            handler=refund_payment,
            annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
        ),
        Tool(
            name="list_merchant_payments",
            description="List the ids of every SandPay payment of one merchant, in id order.",
            input_schema={
                "type": "object",
                "properties": {"merchant_id": {"type": "string", "pattern": "^m_[0-9]{3}$"}},
                "required": ["merchant_id"],
                "additionalProperties": False,
            },
            handler=list_merchant_payments,
            annotations={"readOnlyHint": True},
        ),
    ]


def demo_ledger() -> dict[str, dict[str, Any]]:
    return {
        "pay_1042": {"id": "pay_1042", "merchant_id": "m_204", "amount_minor": 8400, "currency": "EUR",
                     "status": "captured", "refunded_minor": 0},
        "pay_1043": {"id": "pay_1043", "merchant_id": "m_204", "amount_minor": 1250, "currency": "EUR",
                     "status": "authorised", "refunded_minor": 0},
        "pay_2001": {"id": "pay_2001", "merchant_id": "m_311", "amount_minor": 5000, "currency": "GBP",
                     "status": "captured", "refunded_minor": 0},
    }
