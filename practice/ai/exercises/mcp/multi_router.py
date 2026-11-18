"""Send requests to many MCP servers so that one broken server cannot break the rest.

Each server sits behind its own client. Here a client is any callable ``send(request) -> response`` that takes
one JSON-RPC request dict and returns one JSON-RPC response dict (a real client would write it to stdio or POST
it over Streamable HTTP). ``send`` may raise (the process died, the connection was refused) or hang.

Two host-side patterns, not part of the MCP specification:

- ``fan_out`` asks every healthy server the same thing in parallel and returns **partial results**: the
  answers that came back plus one error string per server that did not.
- ``ServerHealth`` is a simple circuit breaker: after ``threshold`` consecutive failures a server is skipped
  until a success is recorded (for example by a later health check).

``route_call`` sends one ``tools/call`` to the server that owns a namespaced tool and turns every failure into a
tool result with ``isError: true``, so the model can read it and try something else.
"""

from __future__ import annotations

import itertools
from concurrent.futures import ThreadPoolExecutor  # noqa: F401 - you will need these
from concurrent.futures import TimeoutError as FutureTimeout  # noqa: F401
from dataclasses import dataclass, field
from typing import Any, Callable

PROTOCOL_VERSION = "2026-07-28"
Send = Callable[[dict[str, Any]], dict[str, Any]]
Resolve = Callable[[str], tuple[str, str]]  # e.g. ToolCatalog.resolve: exposed name -> (server_id, tool)
_ids = itertools.count(1)


def make_request(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """A JSON-RPC request with a fresh integer id and the per-request ``_meta`` fields MCP 2026-07-28 requires."""
    body = dict(params or {})
    meta = dict(body.get("_meta", {}))
    meta["io.modelcontextprotocol/protocolVersion"] = PROTOCOL_VERSION
    meta.setdefault("io.modelcontextprotocol/clientCapabilities", {})
    body["_meta"] = meta
    return {"jsonrpc": "2.0", "id": next(_ids), "method": method, "params": body}


def check_response(request: dict[str, Any], response: Any) -> dict[str, Any]:
    """Return the ``result`` of a matching response; raise RuntimeError with a short reason otherwise."""
    raise NotImplementedError("TODO: check_response")


@dataclass
class ServerHealth:
    threshold: int = 3
    failures: dict[str, int] = field(default_factory=dict)

    def record(self, server_id: str, ok: bool) -> None:
        """A success resets the server's consecutive-failure count to 0; a failure adds 1."""
        raise NotImplementedError("TODO: record")

    def is_down(self, server_id: str) -> bool:
        """True once the server has ``threshold`` or more consecutive failures."""
        raise NotImplementedError("TODO: is_down")


@dataclass
class FanOutResult:
    results: dict[str, dict[str, Any]]
    errors: dict[str, str]


def fan_out(
    clients: dict[str, Send],
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float = 1.0,
    health: ServerHealth | None = None,
) -> FanOutResult:
    """Send ``method`` to every client in parallel; collect results and per-server errors.

    Error strings: ``"skipped: down after N failures"``, ``"timeout after Xs"``,
    ``"unavailable: <ExceptionType>: <message>"``, or the ``check_response`` reason. A timed-out call keeps
    running in its thread (Python cannot kill it); the result is ignored.
    """
    raise NotImplementedError("TODO: fan_out")


def error_result(text: str) -> dict[str, Any]:
    return {"resultType": "complete", "content": [{"type": "text", "text": text}], "isError": True}


def route_call(
    resolve: Resolve,
    clients: dict[str, Send],
    exposed_name: str,
    arguments: dict[str, Any],
    timeout: float = 1.0,
    health: ServerHealth | None = None,
) -> dict[str, Any]:
    """Call one namespaced tool on its own server. Never raises: every failure is an ``isError`` result.

    ``resolve`` maps the name the model used to ``(server_id, tool)`` and raises KeyError for unknown names
    (pass ``catalog.resolve`` from ``multi_aggregator``).
    """
    raise NotImplementedError("TODO: route_call")
