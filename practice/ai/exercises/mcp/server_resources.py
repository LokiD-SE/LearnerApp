"""Resources, resource templates, prompts and change notifications for SandPay's MCP server, by hand.

MCP specification, revision 2026-07-28: "Server Features > Resources" and "> Prompts", and "Message
Patterns > Subscriptions" (``subscriptions/listen``).

- **Resources** are application-controlled context identified by a URI. ``resources/list`` shows the fixed
  ones; ``resources/templates/list`` shows URI templates (RFC 6570) such as
  ``sandpay://merchants/{merchant_id}/payouts``; ``resources/read`` returns ``contents``.
  A missing resource is a JSON-RPC error ``-32602`` with the URI in ``data`` - never an empty ``contents``.
- **Prompts** are user-controlled templates (slash commands). Arguments are named *strings*; a missing
  required argument is ``-32602``.
- **Notifications**: a client opens ``subscriptions/listen`` with a filter; the server's first message is
  ``notifications/subscriptions/acknowledged`` with the subset it honours, and every notification on that
  stream carries ``io.modelcontextprotocol/subscriptionId`` (the listen request's JSON-RPC id) in ``_meta``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from mcp.server_tools import INVALID_PARAMS, ProtocolError

SUBSCRIPTION_ID = "io.modelcontextprotocol/subscriptionId"
PAYOUTS_TEMPLATE = "sandpay://merchants/{merchant_id}/payouts"
MERCHANT_ID = re.compile(r"^m_[0-9]{3}$")
DOC_NAME = re.compile(r"^[a-z0-9-]{1,40}$")

# What this server can deliver on a subscriptions/listen stream (it has no tools, so no toolsListChanged).
SUPPORTED_FILTERS = ("promptsListChanged", "resourcesListChanged", "resourceSubscriptions")


def match_template(template: str, uri: str) -> dict[str, str] | None:
    """Match ``uri`` against a level-1 RFC 6570 template (``{name}`` = one non-empty path segment without
    ``/``) and return the variables, or ``None`` when it does not match. Literal parts must match exactly -
    no regex characters from the template leak into the match."""
    raise NotImplementedError("TODO: implement match_template - see the docstring")


def not_found(uri: str) -> ProtocolError:
    return ProtocolError(INVALID_PARAMS, "Resource not found", {"uri": uri})


@dataclass
class Prompt:
    name: str
    description: str
    template: str  # str.format-style: "Summarise payouts for {merchant_id}"
    # [{"name", "description", "required"}], plus an optional "default" this server uses (not sent to clients)
    arguments: list[dict[str, Any]] = field(default_factory=list)
    title: str | None = None

    def definition(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name}
        if self.title is not None:
            out["title"] = self.title
        out["description"] = self.description
        out["arguments"] = [{k: v for k, v in a.items() if k != "default"} for a in self.arguments]
        return out


@dataclass
class ResourceServer:
    docs: dict[str, str]  # name -> Markdown, served as sandpay://docs/<name>
    payouts: dict[str, list[dict[str, Any]]]  # merchant id -> payouts, served through PAYOUTS_TEMPLATE
    prompts: dict[str, Prompt] = field(default_factory=dict)
    subscriptions: dict[Any, dict[str, Any]] = field(default_factory=dict)  # listen request id -> honoured filter

    # --- resources ---------------------------------------------------------------------------------------

    def list_resources(self) -> dict[str, Any]:
        """``resources/list``: one entry per doc, sorted by URI, ``text/markdown``, public for an hour."""
        resources = [
            {"uri": f"sandpay://docs/{name}", "name": name, "mimeType": "text/markdown"} for name in sorted(self.docs)
        ]
        return {"resultType": "complete", "resources": resources, "ttlMs": 3_600_000, "cacheScope": "public"}

    def list_templates(self) -> dict[str, Any]:
        """``resources/templates/list``: the payouts template."""
        return {
            "resultType": "complete",
            "resourceTemplates": [
                {
                    "uriTemplate": PAYOUTS_TEMPLATE,
                    "name": "merchant-payouts",
                    "title": "Merchant payouts",
                    "description": "Payouts of one SandPay merchant, newest first, as JSON.",
                    "mimeType": "application/json",
                }
            ],
            "ttlMs": 3_600_000,
            "cacheScope": "public",
        }

    def read(self, params: Any) -> dict[str, Any]:
        """``resources/read``. Docs are public for an hour; a merchant's payouts are private for a minute.
        Unknown URI, a doc name outside DOC_NAME, an unknown merchant or a merchant id outside MERCHANT_ID
        -> ``not_found(uri)``. A missing or non-string ``uri`` -> ``-32602`` "resources/read needs params.uri"."""
        raise NotImplementedError("TODO: implement read - see the docstring")

    # --- prompts -----------------------------------------------------------------------------------------

    def list_prompts(self) -> dict[str, Any]:
        """``prompts/list``: definitions sorted by name, public for ten minutes."""
        prompts = [self.prompts[n].definition() for n in sorted(self.prompts)]
        return {"resultType": "complete", "prompts": prompts, "ttlMs": 600_000, "cacheScope": "public"}

    def get_prompt(self, params: Any) -> dict[str, Any]:
        """``prompts/get``: render one user text message. Errors (all ``-32602``): no/non-string name,
        unknown prompt ("Unknown prompt: <name>"), an argument value that is not a string, and missing
        required arguments ("Missing required arguments", ``data`` = ``{"missing": [names in declared order]}``).
        An optional argument that is absent takes its ``default`` (or "")."""
        raise NotImplementedError("TODO: implement get_prompt - see the docstring")

    # --- subscriptions/listen ----------------------------------------------------------------------------

    def listen(self, request_id: Any, notifications: dict[str, Any]) -> dict[str, Any]:
        """Open a subscription for the ``subscriptions/listen`` request ``request_id`` and return the
        acknowledgement notification. Honour only SUPPORTED_FILTERS; drop flags that are not ``True``;
        keep ``resourceSubscriptions`` only for URIs this server can read, and drop the key if none remain."""
        raise NotImplementedError("TODO: implement listen - see the docstring")

    def cancel(self, request_id: Any) -> None:
        """The client sent notifications/cancelled for this listen request: stop sending on it."""
        self.subscriptions.pop(request_id, None)

    def add_prompt(self, prompt: Prompt) -> list[dict[str, Any]]:
        """Add (or replace) a prompt and return one ``notifications/prompts/list_changed`` per subscription
        that asked for ``promptsListChanged``, in subscription order."""
        raise NotImplementedError("TODO: implement add_prompt - see the docstring")

    def record_payout(self, merchant: str, payout: dict[str, Any]) -> list[dict[str, Any]]:
        """Prepend a payout for ``merchant`` and return one ``notifications/resources/updated`` (with the
        payouts URI) per subscription watching that URI. A merchant seen for the first time also changes the
        resource list - but payouts are template resources, not listed ones, so no list_changed is sent."""
        raise NotImplementedError("TODO: implement record_payout - see the docstring")

    def _readable(self, uri: Any) -> bool:
        try:
            self.read({"uri": uri})
        except ProtocolError:
            return False
        return True


def _notification(method: str, subscription_id: Any, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": {"_meta": {SUBSCRIPTION_ID: subscription_id}, **params}}


def demo_server() -> ResourceServer:
    return ResourceServer(
        docs={
            "refund-policy": "# Refund policy\n\nRefunds are allowed within 180 days of capture.",
            "payout-schedule": "# Payout schedule\n\nPayouts run daily at 06:00 UTC for the previous day.",
        },
        payouts={
            "m_204": [
                {"id": "po_1039", "amount_minor": 120500, "currency": "EUR", "status": "paid"},
                {"id": "po_1031", "amount_minor": 98000, "currency": "EUR", "status": "paid"},
            ]
        },
        prompts={
            "summarise_payouts": Prompt(
                name="summarise_payouts",
                title="Summarise payouts",
                description="Summarise one merchant's recent payouts for a support reply.",
                template="Summarise the recent payouts of SandPay merchant {merchant_id} in {tone} language. "
                "Use only the payouts resource for that merchant.",
                arguments=[
                    {"name": "merchant_id", "description": "Merchant id such as m_204", "required": True},
                    {"name": "tone", "description": "plain or formal", "required": False, "default": "plain"},
                ],
            )
        },
    )
