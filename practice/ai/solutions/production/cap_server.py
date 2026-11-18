"""Capstone part 2 - SandPay's support MCP server (revision 2026-07-28): two tools, and a refund that needs the
user's approval through an input-required result with an integrity-protected ``requestState``.

Reference solution. Plain Python, no SDK: ``SupportServer.handle(message)`` takes one decoded JSON-RPC request and
returns the response dict (the stdio loop is the one from the lesson building-mcp-servers).

What the specification says, and where this file follows it (MCP 2026-07-28):

- Every request carries ``_meta`` with ``io.modelcontextprotocol/protocolVersion`` and
  ``io.modelcontextprotocol/clientCapabilities``; every result has a ``resultType`` (Base Protocol).
- Tools: business failures are tool results with ``isError: true`` the model can read; unknown tools and malformed
  requests are JSON-RPC errors (Server - Tools, error handling).
- Multi round-trip requests: ``tools/call`` MAY return ``resultType: "input_required"`` with ``inputRequests``
  and ``requestState``; servers "MUST NOT send an inputRequests that the client has not declared support for";
  ``requestState`` is "attacker-controlled input" - if it influences business logic the server "MUST protect its
  integrity (e.g. HMAC or AEAD) and MUST reject state that fails verification"; servers SHOULD bind it to the
  originating request; state that must be "consumed at most once ... MUST" be enforced server-side.
- Elicitation results have ``action`` "accept", "decline" or "cancel"; servers "MUST handle cases where the user
  declines or cancels".

The error code for a requestState that fails verification is not fixed by the specification; this server uses
-32602 (invalid params). SandPay and its data are fictional.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import re
from typing import Any

from prod_cap_fixture import CAPS, GET_PAYMENT_TOOL, PAYMENTS, PROTOCOL_VERSION, PV, REFUND_TOOL

INVALID_PARAMS = -32602
METHOD_NOT_FOUND = -32601
UNSUPPORTED_PROTOCOL_VERSION = -32022
SERVER_INFO = {"name": "sandpay-support", "version": "1.0.0"}
APPROVAL_KEY = "approve_refund"


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def tool_result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    """A complete tools/call result: one text block (JSON for dicts) plus structuredContent for dicts."""
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    result: dict[str, Any] = {"resultType": "complete", "content": [{"type": "text", "text": text}], "isError": is_error}
    if isinstance(payload, dict):
        result["structuredContent"] = payload
    return result


# --- part A: arguments ---------------------------------------------------------------------------------------


def validate_refund_args(args: Any) -> list[str]:
    """Problems with refund_payment arguments against REFUND_TOOL's inputSchema; [] when valid. In this order:
    not an object -> ["arguments must be an object"] (stop); then, for each problem found:
    "missing payment_id" / "missing amount_minor" / "missing reason" (schema order),
    "payment_id must look like pay_1234", "amount_minor must be a whole number of minor units >= 1"
    (bool is not a number here), "reason must be 3 to 200 characters", "unexpected field <name>" (sorted)."""
    if not isinstance(args, dict):
        return ["arguments must be an object"]
    problems = [f"missing {name}" for name in ("payment_id", "amount_minor", "reason") if name not in args]
    if "payment_id" in args and not (isinstance(args["payment_id"], str) and re.fullmatch(r"pay_[0-9]{4}", args["payment_id"])):
        problems.append("payment_id must look like pay_1234")
    amount = args.get("amount_minor")
    if "amount_minor" in args and (isinstance(amount, bool) or not isinstance(amount, int) or amount < 1):
        problems.append("amount_minor must be a whole number of minor units >= 1")
    reason = args.get("reason")
    if "reason" in args and not (isinstance(reason, str) and 3 <= len(reason) <= 200):
        problems.append("reason must be 3 to 200 characters")
    problems += [f"unexpected field {name}" for name in sorted(set(args) - {"payment_id", "amount_minor", "reason"})]
    return problems


# --- part B: requestState ------------------------------------------------------------------------------------


def args_digest(args: dict[str, Any]) -> str:
    """SHA-256 hex of the arguments as canonical JSON (sorted keys, no spaces)."""
    return hashlib.sha256(json.dumps(args, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sign_state(secret: bytes, payload: dict[str, Any]) -> str:
    """``<body>.<mac>``: body = URL-safe base64 (no padding) of canonical JSON; mac = URL-safe base64 (no padding)
    of HMAC-SHA256(secret, body)."""
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).rstrip(b"=")
    mac = base64.urlsafe_b64encode(hmac.new(secret, body, hashlib.sha256).digest()).rstrip(b"=")
    return (body + b"." + mac).decode()


def verify_state(secret: bytes, state: Any) -> dict[str, Any]:
    """The payload of a state made by ``sign_state``; RpcError(-32602, "Invalid requestState") if it is not a
    string of that shape or the MAC does not match (compare with ``hmac.compare_digest``)."""
    try:
        body, mac = state.encode().split(b".")
        expected = base64.urlsafe_b64encode(hmac.new(secret, body, hashlib.sha256).digest()).rstrip(b"=")
        if not hmac.compare_digest(mac, expected):
            raise ValueError("bad mac")
        return json.loads(base64.urlsafe_b64decode(body + b"=" * (-len(body) % 4)))
    except Exception:
        raise RpcError(INVALID_PARAMS, "Invalid requestState") from None


# --- part C: the server --------------------------------------------------------------------------------------


class SupportServer:
    """``payments`` is copied; ``refunds`` lists every refund issued; ``secret`` signs requestState."""

    def __init__(self, secret: bytes, payments: dict[str, dict[str, Any]] | None = None):
        self.secret = secret
        self.payments = copy.deepcopy(PAYMENTS if payments is None else payments)
        self.refunds: list[dict[str, Any]] = []
        self.used_nonces: set[str] = set()
        self._next_nonce = 0

    # the envelope (given in the exercise) ------------------------------------------------------------------

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        rid = message.get("id")
        try:
            params = message.get("params") or {}
            meta = params.get("_meta")
            if not isinstance(meta, dict) or not isinstance(meta.get(PV), str) or not isinstance(meta.get(CAPS), dict):
                raise RpcError(INVALID_PARAMS, "Missing params._meta protocol version or client capabilities")
            if meta[PV] != PROTOCOL_VERSION:
                raise RpcError(UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version", {"supported": [PROTOCOL_VERSION], "requested": meta[PV]})
            method = message.get("method")
            if method == "server/discover":
                result = {"resultType": "complete", "supportedVersions": [PROTOCOL_VERSION], "capabilities": {"tools": {}}}
            elif method == "tools/list":
                result = {"resultType": "complete", "tools": [GET_PAYMENT_TOOL, REFUND_TOOL]}
            elif method == "tools/call":
                result = self.call_tool(params, meta[CAPS])
            else:
                raise RpcError(METHOD_NOT_FOUND, f"Method not found: {method}")
        except RpcError as exc:
            error: dict[str, Any] = {"code": exc.code, "message": exc.message}
            if exc.data is not None:
                error["data"] = exc.data
            return {"jsonrpc": "2.0", "id": rid, "error": error}
        result["_meta"] = {"io.modelcontextprotocol/serverInfo": SERVER_INFO}
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def call_tool(self, params: dict[str, Any], caps: dict[str, Any]) -> dict[str, Any]:
        name, args = params.get("name"), params.get("arguments")
        if name == "get_payment":
            pid = (args or {}).get("payment_id") if isinstance(args, dict) else None
            if pid not in self.payments:
                return tool_result(f"No SandPay payment {pid!r}.", is_error=True)
            return tool_result({"payment_id": pid, **self.payments[pid]})
        if name == "refund_payment":
            return self.refund_payment(params, caps)
        raise RpcError(INVALID_PARAMS, f"Unknown tool: {name}")

    # the refund (the exercise) ---------------------------------------------------------------------------------

    def refund_payment(self, params: dict[str, Any], caps: dict[str, Any]) -> dict[str, Any]:
        """1. Invalid arguments -> isError result "Invalid arguments: " + problems joined with "; ".
        2. Business rules (isError results): unknown payment "No SandPay payment 'pay_9999'."; status not
           captured "pay_1044 is authorized, not captured - cancel the authorisation instead of refunding.";
           amount over the remaining "Refund of 2000 is more than the 1500 left to refund on pay_1043.".
        3. First call (no ``requestState``): without the ``elicitation`` capability -> isError "refund_payment
           needs a client that can ask the user to approve (elicitation)."; otherwise an input_required result
           with one form elicitation under APPROVAL_KEY and a signed state {"m": "tools/call:refund_payment",
           "d": args_digest(args), "n": "<nonce>"} (nonces "n1", "n2", ...).
        4. Retry: verify the state; its "m" and "d" must match this request, else RpcError(-32602,
           "requestState does not match this request"); a nonce already used -> RpcError(-32602, "requestState
           already used"). Mark the nonce used, then read inputResponses[APPROVAL_KEY]: action "accept" with
           content.approve true -> issue the refund ({"refund_id": "rf_<nonce>", "payment_id", "amount_minor",
           "currency", "status": "refunded"}), add it to ``refunds`` and to the payment's refunded_minor; anything
           else -> {"status": "not_approved", "payment_id", "action": <action or None>} (not an error)."""
        args = params.get("arguments")
        problems = validate_refund_args(args)
        if problems:
            return tool_result("Invalid arguments: " + "; ".join(problems), is_error=True)
        pid, amount = args["payment_id"], args["amount_minor"]
        payment = self.payments.get(pid)
        if payment is None:
            return tool_result(f"No SandPay payment {pid!r}.", is_error=True)
        if payment["status"] != "captured":
            return tool_result(f"{pid} is {payment['status']}, not captured - cancel the authorisation instead of refunding.", is_error=True)
        left = payment["amount_minor"] - payment["refunded_minor"]
        if amount > left:
            return tool_result(f"Refund of {amount} is more than the {left} left to refund on {pid}.", is_error=True)

        if "requestState" not in params:
            if "elicitation" not in caps:
                return tool_result("refund_payment needs a client that can ask the user to approve (elicitation).", is_error=True)
            self._next_nonce += 1
            state = sign_state(self.secret, {"m": "tools/call:refund_payment", "d": args_digest(args), "n": f"n{self._next_nonce}"})
            return {
                "resultType": "input_required",
                "inputRequests": {
                    APPROVAL_KEY: {
                        "method": "elicitation/create",
                        "params": {
                            "mode": "form",
                            "message": f"Refund {amount / 100:.2f} {payment['currency']} of {pid} to the customer? Reason: {args['reason']}",
                            "requestedSchema": {
                                "type": "object",
                                "properties": {"approve": {"type": "boolean", "description": "Approve this refund"}},
                                "required": ["approve"],
                            },
                        },
                    }
                },
                "requestState": state,
            }

        payload = verify_state(self.secret, params["requestState"])
        if payload.get("m") != "tools/call:refund_payment" or payload.get("d") != args_digest(args):
            raise RpcError(INVALID_PARAMS, "requestState does not match this request")
        nonce = payload.get("n")
        if nonce in self.used_nonces:
            raise RpcError(INVALID_PARAMS, "requestState already used")
        self.used_nonces.add(nonce)
        answer = (params.get("inputResponses") or {}).get(APPROVAL_KEY) or {}
        if answer.get("action") == "accept" and (answer.get("content") or {}).get("approve") is True:
            refund = {"refund_id": f"rf_{nonce}", "payment_id": pid, "amount_minor": amount, "currency": payment["currency"], "status": "refunded"}
            payment["refunded_minor"] += amount
            self.refunds.append(refund)
            return tool_result(refund)
        return tool_result({"status": "not_approved", "payment_id": pid, "action": answer.get("action")})
