"""In-process fake MCP servers for the mcp-architecture exercises (protocol version 2026-07-28).

``FakeServer.handle(message)`` takes one JSON-RPC message (a dict) and returns the response dict, or
``None`` for a notification. It follows the data layer of the MCP specification 2026-07-28 closely
enough for the exercises - per-request ``_meta``, ``server/discover``, the three server primitives,
``resultType`` and multi round-trip requests - but it is a teaching fixture, not a full implementation:
no transport, no pagination, no subscriptions, no caching rules beyond the two required fields.

Every request the server receives is appended to ``server.received`` so tests can check what a server
was (and was not) shown.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Callable

PROTOCOL_VERSION = "2026-07-28"
META = "io.modelcontextprotocol/"

# JSON-RPC 2.0 codes and the MCP 2026-07-28 codes in the reserved -32020..-32099 range.
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
MISSING_REQUIRED_CLIENT_CAPABILITY = -32021
UNSUPPORTED_PROTOCOL_VERSION = -32022


def make_tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties, "required": required},
    }


@dataclass
class FakeServer:
    name: str
    tools: dict[str, tuple[dict, Callable[[dict], Any]]] = field(default_factory=dict)
    resources: dict[str, dict] = field(default_factory=dict)  # uri -> {"name", "mimeType", "text"}
    prompts: dict[str, dict] = field(default_factory=dict)  # name -> {"description", "text"}
    # tools that need the user's confirmation through elicitation (multi round-trip request)
    confirm_tools: set[str] = field(default_factory=set)
    supported_versions: tuple[str, ...] = (PROTOCOL_VERSION,)
    received: list[dict] = field(default_factory=list)

    # ---- helpers -------------------------------------------------------------------------
    def add_tool(self, definition: dict, fn: Callable[[dict], Any], confirm: bool = False) -> None:
        self.tools[definition["name"]] = (definition, fn)
        if confirm:
            self.confirm_tools.add(definition["name"])

    def capabilities(self) -> dict:
        caps: dict = {}
        if self.tools:
            caps["tools"] = {}
        if self.resources:
            caps["resources"] = {}
        if self.prompts:
            caps["prompts"] = {}
        return caps

    def _ok(self, msg_id, result: dict, cacheable: bool = False) -> dict:
        body = {"resultType": "complete", **result}
        if cacheable:
            body.update({"ttlMs": 60000, "cacheScope": "public"})
        body["_meta"] = {META + "serverInfo": {"name": self.name, "version": "1.0.0"}}
        return {"jsonrpc": "2.0", "id": msg_id, "result": body}

    @staticmethod
    def _err(msg_id, code: int, message: str, data: Any = None) -> dict:
        error: dict = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": msg_id, "error": error}

    # ---- the entry point -----------------------------------------------------------------
    def handle(self, message: dict) -> dict | None:
        self.received.append(json.loads(json.dumps(message)))  # a deep copy
        if "id" not in message:
            return None  # a notification: never answered
        msg_id = message["id"]
        params = message.get("params") or {}
        meta = params.get("_meta") or {}
        version = meta.get(META + "protocolVersion")
        caps = meta.get(META + "clientCapabilities")
        if version is None or caps is None:
            return self._err(msg_id, INVALID_PARAMS, "Missing required _meta fields")
        if version not in self.supported_versions:
            return self._err(
                msg_id,
                UNSUPPORTED_PROTOCOL_VERSION,
                "Unsupported protocol version",
                {"supported": list(self.supported_versions), "requested": version},
            )
        method = message.get("method")
        if method == "server/discover":
            return self._ok(
                msg_id,
                {"supportedVersions": list(self.supported_versions), "capabilities": self.capabilities()},
                cacheable=True,
            )
        if method == "tools/list" and self.tools:
            return self._ok(msg_id, {"tools": [d for d, _ in self.tools.values()]}, cacheable=True)
        if method == "tools/call" and self.tools:
            return self._call_tool(msg_id, params, caps)
        if method == "resources/list" and self.resources:
            items = [{"uri": u, "name": r["name"], "mimeType": r["mimeType"]} for u, r in self.resources.items()]
            return self._ok(msg_id, {"resources": items}, cacheable=True)
        if method == "resources/read" and self.resources:
            uri = params.get("uri")
            if uri not in self.resources:
                return self._err(msg_id, INVALID_PARAMS, "Resource not found", {"uri": uri})
            r = self.resources[uri]
            return self._ok(msg_id, {"contents": [{"uri": uri, "mimeType": r["mimeType"], "text": r["text"]}]}, cacheable=True)
        if method == "prompts/list" and self.prompts:
            items = [{"name": n, "description": p["description"]} for n, p in self.prompts.items()]
            return self._ok(msg_id, {"prompts": items}, cacheable=True)
        if method == "prompts/get" and self.prompts:
            name = params.get("name")
            if name not in self.prompts:
                return self._err(msg_id, INVALID_PARAMS, "Unknown prompt", {"name": name})
            text = self.prompts[name]["text"].format(**(params.get("arguments") or {}))
            return self._ok(msg_id, {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]})
        return self._err(msg_id, METHOD_NOT_FOUND, "Method not found", {"method": method})

    def _call_tool(self, msg_id, params: dict, caps: dict) -> dict:
        name = params.get("name")
        if name not in self.tools:
            return self._err(msg_id, INVALID_PARAMS, f"Unknown tool: {name}")
        definition, fn = self.tools[name]
        args = params.get("arguments") or {}
        missing = [k for k in definition["inputSchema"].get("required", []) if k not in args]
        if missing:
            return self._err(msg_id, INVALID_PARAMS, f"Missing arguments: {missing}")
        if name in self.confirm_tools:
            if "elicitation" not in caps:
                return self._err(
                    msg_id,
                    MISSING_REQUIRED_CLIENT_CAPABILITY,
                    "Missing required client capability",
                    {"requiredCapabilities": {"elicitation": {}}},
                )
            answer = (params.get("inputResponses") or {}).get("confirm")
            state = base64.b64encode(json.dumps({"tool": name, "args": args}, sort_keys=True).encode()).decode()
            if answer is None:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "resultType": "input_required",
                        "inputRequests": {
                            "confirm": {
                                "method": "elicitation/create",
                                "params": {
                                    "mode": "form",
                                    "message": f"{self.name} wants to run {name} with {json.dumps(args, sort_keys=True)}. Approve?",
                                    "requestedSchema": {
                                        "type": "object",
                                        "properties": {"approve": {"type": "boolean"}},
                                        "required": ["approve"],
                                    },
                                },
                            }
                        },
                        "requestState": state,
                    },
                }
            if params.get("requestState") != state:
                return self._err(msg_id, INVALID_PARAMS, "requestState does not match this request")
            if answer.get("action") != "accept" or not (answer.get("content") or {}).get("approve"):
                return self._ok(msg_id, {"content": [{"type": "text", "text": "Not approved; nothing was done."}], "isError": True})
        try:
            value = fn(args)
        except Exception as exc:  # tool failures are results the model can read, not protocol errors
            return self._ok(msg_id, {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True})
        return self._ok(msg_id, {"content": [{"type": "text", "text": json.dumps(value, sort_keys=True)}], "isError": False})


# ---- the SandPay servers used in the lesson ------------------------------------------------

PAYMENTS = {
    "pay_7001": {"id": "pay_7001", "amount_minor": 4200, "currency": "EUR", "status": "settled", "merchant": "m-204"},
    "pay_7002": {"id": "pay_7002", "amount_minor": 1599, "currency": "GBP", "status": "failed", "merchant": "m-311"},
}


def payments_server() -> FakeServer:
    s = FakeServer("sandpay-payments")

    def get_payment(args):
        if args["payment_id"] not in PAYMENTS:
            raise KeyError(f"no payment {args['payment_id']}")
        return PAYMENTS[args["payment_id"]]

    s.add_tool(
        make_tool(
            "get_payment",
            "Look up one SandPay payment by id (read-only).",
            {"payment_id": {"type": "string"}},
            ["payment_id"],
        ),
        get_payment,
    )
    s.add_tool(
        make_tool(
            "refund_payment",
            "Refund a settled SandPay payment. Moves money; needs the user's approval.",
            {"payment_id": {"type": "string"}, "amount_minor": {"type": "integer"}},
            ["payment_id", "amount_minor"],
        ),
        lambda a: {"refund_id": "rf_" + a["payment_id"][4:], "amount_minor": a["amount_minor"], "status": "pending"},
        confirm=True,
    )
    s.resources["sandpay://merchants/m-204/profile"] = {
        "name": "Merchant m-204 profile",
        "mimeType": "application/json",
        "text": json.dumps({"merchant": "m-204", "name": "Lumen Books", "payout_schedule": "daily"}),
    }
    return s


def docs_server() -> FakeServer:
    s = FakeServer("sandpay-docs")
    s.resources["sandpay://docs/refund-policy"] = {
        "name": "Refund policy",
        "mimeType": "text/markdown",
        "text": "Refunds are allowed within 120 days of settlement, up to the captured amount.",
    }
    s.prompts["summarise_dispute"] = {
        "description": "Summarise a dispute for a support agent.",
        "text": "Summarise dispute {dispute_id} in three bullet points for a support agent.",
    }
    s.add_tool(
        make_tool("search_docs", "Search SandPay's public docs.", {"query": {"type": "string"}}, ["query"]),
        lambda a: {"hits": ["refund-policy"] if "refund" in a["query"].lower() else []},
    )
    return s
