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
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
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
    if not isinstance(response, dict) or response.get("jsonrpc") != "2.0" or response.get("id") != request["id"]:
        raise RuntimeError("bad response: not a JSON-RPC 2.0 reply to this request id")
    if "error" in response:
        err = response["error"]
        raise RuntimeError(f"error {err.get('code')}: {err.get('message')}")
    if "result" not in response:
        raise RuntimeError("bad response: no result")
    return response["result"]


@dataclass
class ServerHealth:
    threshold: int = 3
    failures: dict[str, int] = field(default_factory=dict)

    def record(self, server_id: str, ok: bool) -> None:
        self.failures[server_id] = 0 if ok else self.failures.get(server_id, 0) + 1

    def is_down(self, server_id: str) -> bool:
        return self.failures.get(server_id, 0) >= self.threshold


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
    results: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    live = {}
    for server_id, send in clients.items():
        if health is not None and health.is_down(server_id):
            errors[server_id] = f"skipped: down after {health.failures[server_id]} failures"
        else:
            live[server_id] = send
    if live:
        pool = ThreadPoolExecutor(max_workers=len(live))
        try:
            pending = {}
            for server_id, send in live.items():
                request = make_request(method, params)
                pending[server_id] = (request, pool.submit(send, request))
            for server_id, (request, future) in pending.items():
                try:
                    results[server_id] = check_response(request, future.result(timeout=timeout))
                except FutureTimeout:
                    errors[server_id] = f"timeout after {timeout}s"
                except RuntimeError as err:
                    errors[server_id] = str(err)
                except Exception as err:  # noqa: BLE001 - any client failure is isolated to its server
                    errors[server_id] = f"unavailable: {type(err).__name__}: {err}"
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    if health is not None:
        for server_id in live:
            health.record(server_id, server_id in results)
    return FanOutResult(results=dict(sorted(results.items())), errors=dict(sorted(errors.items())))


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
    try:
        server_id, tool = resolve(exposed_name)
    except KeyError:
        return error_result(f"Unknown tool {exposed_name!r}.")
    if server_id not in clients:
        return error_result(f"Server {server_id!r} is not connected.")
    outcome = fan_out(
        {server_id: clients[server_id]}, "tools/call", {"name": tool, "arguments": arguments}, timeout, health
    )
    if server_id in outcome.results:
        return outcome.results[server_id]
    return error_result(f"Server {server_id!r} could not run {tool!r}: {outcome.errors[server_id]}")
