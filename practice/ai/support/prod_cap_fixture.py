"""Fixtures for the capstone lesson ai-capstone-support-agent: SandPay's help-centre policies, a small payments
ledger and a fake MCP server the agent tests talk to.

Everything here is fictional. SandPay is not a real company; its policies, merchants and payments were invented
for the lesson. Amounts are integers in minor units (12500 = 125.00 EUR).

``FakeSupportServer`` is NOT the server you build in ``production/cap_server.py``. It is a small stand-in with the
same two tools, so the agent exercise can be solved before (or without) the server exercise. It speaks the shape
of MCP revision 2026-07-28 (per-request ``_meta``, ``resultType``, input-required results for approval) but checks
very little - it trusts its own ``requestState`` and does no schema validation.
"""

from __future__ import annotations

import copy
import json
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
PV = "io.modelcontextprotocol/protocolVersion"
CAPS = "io.modelcontextprotocol/clientCapabilities"

POLICIES: dict[str, str] = {
    "refunds": """# Refunds

## Time limit
A merchant can refund a captured payment within 180 days of the capture date. After 180 days the refund
button is disabled and the merchant must pay the customer back outside SandPay.

## Partial refunds
A merchant can refund part of a payment, and can do so several times. The total refunded can never be more
than the captured amount.

## Refund fees
SandPay keeps the processing fee of the original payment when a merchant refunds it. A refund itself has no
extra fee.

## Uncaptured payments
An authorised payment that was never captured cannot be refunded. Cancel the authorisation instead, which
releases the hold on the customer's card.
""",
    "payouts": """# Payouts

## Payout schedule
SandPay sends a payout every business day. Each payout contains the funds that settled two business days
earlier.

## Payout holds
SandPay can hold a payout while a dispute on the merchant's account is open, or while the merchant's
identity checks are incomplete.
""",
    "disputes": """# Disputes

## Responding to a dispute
A merchant has 7 calendar days from the dispute notification to submit evidence in the dashboard.

## Dispute fee
SandPay charges a dispute fee of 15.00 EUR for each dispute. The fee is returned if the merchant wins.
""",
}

PAYMENTS: dict[str, dict[str, Any]] = {
    "pay_1042": {"merchant_id": "m_204", "amount_minor": 12500, "refunded_minor": 0, "currency": "EUR", "status": "captured"},
    "pay_1043": {"merchant_id": "m_204", "amount_minor": 4000, "refunded_minor": 2500, "currency": "EUR", "status": "captured"},
    "pay_1044": {"merchant_id": "m_311", "amount_minor": 9900, "refunded_minor": 0, "currency": "GBP", "status": "authorized"},
}


def request_meta(capabilities: dict[str, Any] | None = None) -> dict[str, Any]:
    """The ``_meta`` every 2026-07-28 request carries."""
    return {PV: PROTOCOL_VERSION, CAPS: {} if capabilities is None else capabilities}


GET_PAYMENT_TOOL = {
    "name": "get_payment",
    "description": "Look up one SandPay payment by id: merchant, amount and refunded amount in minor units, currency and status.",
    "inputSchema": {
        "type": "object",
        "properties": {"payment_id": {"type": "string", "pattern": "^pay_[0-9]{4}$"}},
        "required": ["payment_id"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True},
}

REFUND_TOOL = {
    "name": "refund_payment",
    "description": "Refund part or all of a captured SandPay payment. Moves money; the user approves every refund.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "payment_id": {"type": "string", "pattern": "^pay_[0-9]{4}$"},
            "amount_minor": {"type": "integer", "minimum": 1},
            "reason": {"type": "string", "minLength": 3, "maxLength": 200},
        },
        "required": ["payment_id", "amount_minor", "reason"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
}


def _text_result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    result: dict[str, Any] = {"resultType": "complete", "content": [{"type": "text", "text": text}], "isError": is_error}
    if not isinstance(payload, str):
        result["structuredContent"] = payload
    return result


class FakeSupportServer:
    """In-process stand-in for the SandPay support MCP server. ``handle(message)`` returns the response dict.

    ``requests`` records every request received; ``refunds`` records every refund actually issued.
    ``down=True`` makes every request fail with -32603, to test how the agent copes with an outage."""

    def __init__(self, payments: dict[str, dict[str, Any]] | None = None, down: bool = False):
        self.payments = copy.deepcopy(PAYMENTS if payments is None else payments)
        self.requests: list[dict[str, Any]] = []
        self.refunds: list[dict[str, Any]] = []
        self.down = down
        self._states = 0

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(copy.deepcopy(message))
        rid = message.get("id")
        if self.down:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": "Internal error"}}
        params = message.get("params", {})
        meta = params.get("_meta", {})
        if meta.get(PV) != PROTOCOL_VERSION or not isinstance(meta.get(CAPS), dict):
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "Missing or unsupported _meta"}}
        method = message.get("method")
        if method == "tools/list":
            result: dict[str, Any] = {"resultType": "complete", "tools": [GET_PAYMENT_TOOL, REFUND_TOOL]}
        elif method == "tools/call":
            result = self._call(params, meta[CAPS])
        else:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def _call(self, params: dict[str, Any], caps: dict[str, Any]) -> dict[str, Any]:
        name, args = params.get("name"), params.get("arguments") or {}
        payment = self.payments.get(args.get("payment_id"))
        if name == "get_payment":
            if payment is None:
                return _text_result(f"No SandPay payment {args.get('payment_id')!r}.", is_error=True)
            return _text_result({"payment_id": args["payment_id"], **payment})
        if name != "refund_payment":
            return _text_result(f"Unknown tool {name!r}.", is_error=True)
        if payment is None:
            return _text_result(f"No SandPay payment {args.get('payment_id')!r}.", is_error=True)
        if "inputResponses" not in params:
            if "elicitation" not in caps:
                return _text_result("refund_payment needs a client that can ask the user to approve.", is_error=True)
            self._states += 1
            amount = args["amount_minor"] / 100
            return {
                "resultType": "input_required",
                "inputRequests": {
                    "approve_refund": {
                        "method": "elicitation/create",
                        "params": {
                            "mode": "form",
                            "message": f"Refund {amount:.2f} {payment['currency']} of {args['payment_id']}? Reason: {args['reason']}",
                            "requestedSchema": {
                                "type": "object",
                                "properties": {"approve": {"type": "boolean"}},
                                "required": ["approve"],
                            },
                        },
                    }
                },
                "requestState": f"fake-state-{self._states}",
            }
        answer = params["inputResponses"].get("approve_refund", {})
        if answer.get("action") != "accept" or not (answer.get("content") or {}).get("approve"):
            return _text_result({"status": "not_approved", "payment_id": args["payment_id"], "action": answer.get("action")})
        payment["refunded_minor"] += args["amount_minor"]
        refund = {"refund_id": f"rf_{len(self.refunds) + 1}", "payment_id": args["payment_id"], "amount_minor": args["amount_minor"], "status": "refunded"}
        self.refunds.append(refund)
        return _text_result(refund)
