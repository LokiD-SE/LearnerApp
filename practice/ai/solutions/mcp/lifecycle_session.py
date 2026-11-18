"""A client's side of the MCP lifecycle: the legacy handshake state machine and in-flight requests.

Running example: SandPay's support-desk assistant talks to a merchant-lookup MCP server over stdio.

Part 1 - ``LegacyClientSession`` follows the 2025-11-25 Lifecycle page (the handshake era; the 2026-07-28
revision removed ``initialize``, but dual-era clients still need this to talk to older servers):

- "The initialization phase MUST be the first interaction between client and server." The client sends
  ``initialize`` with ``protocolVersion``, ``capabilities`` and ``clientInfo``.
- "The client SHOULD NOT send requests other than pings before the server has responded to the initialize
  request." After a successful response the client "MUST send an initialized notification".
- If the client does not support the version in the server's response, "it SHOULD disconnect".
- During operation both parties "MUST ... Only use capabilities that were successfully negotiated".

Part 2 - ``PendingRequests`` follows Cancellation (2026-07-28 Message Patterns; same rules in 2025-11-25):
requests get a timeout; on timeout the sender "SHOULD cancel the request and stop waiting" - on stdio by
sending ``notifications/cancelled`` with the ``requestId``; a progress notification MAY reset the clock but a
maximum timeout SHOULD always apply; cancellations "MUST only reference requests that ... Were previously
issued by the client [and] Are believed to still be in-progress"; and "The client SHOULD ignore any
response to the cancelled request that arrives afterward". The request ID "MUST NOT match the ID of any
other request the sender has issued and not yet received a response for."

The clock is injected (a function returning seconds) so tests never sleep.
"""

from __future__ import annotations

from typing import Any, Callable

# Which server capability each method family needs (2025-11-25 Lifecycle, Capability Negotiation).
METHOD_CAPABILITY = {
    "tools/": "tools",
    "resources/": "resources",
    "prompts/": "prompts",
    "logging/": "logging",
    "completion/": "completions",
}


class LifecycleError(RuntimeError):
    """The client tried to send something the lifecycle does not allow now."""


def required_capability(method: str) -> str | None:
    """The server capability ``method`` needs, or ``None`` (for example ``ping``)."""
    for prefix, capability in METHOD_CAPABILITY.items():
        if method.startswith(prefix):
            return capability
    return None


class LegacyClientSession:
    """States: ``"new"`` -> ``"initializing"`` -> ``"ready"`` -> ``"closed"``."""

    def __init__(self, client_supported: list[str], capabilities: dict[str, Any], client_info: dict[str, Any]):
        self.client_supported = list(client_supported)
        self.capabilities = capabilities
        self.client_info = client_info
        self.state = "new"
        self.protocol_version: str | None = None
        self.server_capabilities: dict[str, Any] = {}
        self._next_id = 1

    def _take_id(self) -> int:
        request_id = self._next_id
        self._next_id += 1
        return request_id

    def start(self) -> dict[str, Any]:
        """Return the ``initialize`` request (id 1, the client's latest version) and enter ``"initializing"``.

        Raise ``LifecycleError`` unless the state is ``"new"``.
        """
        if self.state != "new":
            raise LifecycleError(f"initialize is only sent once, from state 'new' (state is '{self.state}')")
        self.state = "initializing"
        return {
            "jsonrpc": "2.0",
            "id": self._take_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": max(self.client_supported),
                "capabilities": self.capabilities,
                "clientInfo": self.client_info,
            },
        }

    def on_initialize_response(self, response: dict[str, Any]) -> dict[str, Any] | None:
        """Handle the server's answer to ``initialize``.

        - error response, or a version the client does not support -> state ``"closed"``, return ``None``
          (the caller disconnects)
        - otherwise store ``protocol_version`` and ``server_capabilities``, enter ``"ready"`` and return the
          ``notifications/initialized`` notification to send
        Raise ``LifecycleError`` unless the state is ``"initializing"``.
        """
        if self.state != "initializing":
            raise LifecycleError(f"no initialize request is outstanding (state is '{self.state}')")
        result = response.get("result")
        if not isinstance(result, dict) or result.get("protocolVersion") not in self.client_supported:
            self.state = "closed"
            return None
        self.protocol_version = result["protocolVersion"]
        self.server_capabilities = result.get("capabilities") or {}
        self.state = "ready"
        return {"jsonrpc": "2.0", "method": "notifications/initialized"}

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return a request message with the next id, if the lifecycle allows it now.

        - ``"new"``: nothing - ``initialize`` must come first
        - ``"initializing"``: only ``ping``
        - ``"ready"``: ``ping``, or a method whose required capability the server declared;
          ``initialize`` again is an error
        - ``"closed"``: nothing
        Raise ``LifecycleError`` with a message naming the state (or the missing capability) otherwise.
        """
        if self.state in ("new", "closed"):
            raise LifecycleError(f"cannot send '{method}' in state '{self.state}'")
        if method == "initialize":
            raise LifecycleError("initialize is only sent once")
        if self.state == "initializing" and method != "ping":
            raise LifecycleError(f"only ping may be sent before the initialize response (got '{method}')")
        capability = required_capability(method)
        if capability is not None and capability not in self.server_capabilities:
            raise LifecycleError(f"'{method}' needs the server capability '{capability}', which was not negotiated")
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": self._take_id(), "method": method}
        if params is not None:
            message["params"] = params
        return message

    def close(self) -> None:
        """Enter ``"closed"`` (on stdio: close the server's stdin, wait, then terminate)."""
        self.state = "closed"


def cancelled_notification(request_id: str | int, reason: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": request_id, "reason": reason}}


class PendingRequests:
    """Tracks the client's in-flight requests, their deadlines and cancellations."""

    def __init__(self, timeout: float, max_timeout: float, clock: Callable[[], float]):
        if not 0 < timeout <= max_timeout:
            raise ValueError("need 0 < timeout <= max_timeout")
        self.timeout = timeout
        self.max_timeout = max_timeout
        self.clock = clock
        self._started: dict[str | int, float] = {}
        self._deadline: dict[str | int, float] = {}
        self.cancelled: set[str | int] = set()

    def track(self, request_id: str | int) -> None:
        """Start the clock for a request just sent. Raise ``ValueError`` if that id is still in flight."""
        if request_id in self._deadline:
            raise ValueError(f"request id {request_id!r} is still in flight")
        now = self.clock()
        self._started[request_id] = now
        self._deadline[request_id] = now + self.timeout

    def in_flight(self) -> list[str | int]:
        return list(self._deadline)

    def on_progress(self, request_id: str | int) -> None:
        """Progress for an in-flight request: deadline = now + timeout, capped at start + max_timeout."""
        if request_id not in self._deadline:
            return
        cap = self._started[request_id] + self.max_timeout
        self._deadline[request_id] = min(self.clock() + self.timeout, cap)

    def on_response(self, response: dict[str, Any]) -> str:
        """``"deliver"`` for a response to an in-flight request (and stop tracking it); ``"ignore"`` for a
        late response to a cancelled request or a response with an unknown id."""
        request_id = response.get("id")
        if request_id in self._deadline:
            del self._deadline[request_id]
            del self._started[request_id]
            return "deliver"
        return "ignore"

    def cancel(self, request_id: str | int, reason: str) -> dict[str, Any] | None:
        """The ``notifications/cancelled`` to send, or ``None`` when the id is not in flight."""
        if request_id not in self._deadline:
            return None
        del self._deadline[request_id]
        del self._started[request_id]
        self.cancelled.add(request_id)
        return cancelled_notification(request_id, reason)

    def expire(self) -> list[dict[str, Any]]:
        """Cancel every request whose deadline has passed (``now >= deadline``), with reason
        ``"timeout after <seconds since start>s"`` (``:g`` format); return the notifications in id order
        of tracking."""
        now = self.clock()
        overdue = [rid for rid, deadline in self._deadline.items() if now >= deadline]
        notes = []
        for rid in overdue:
            elapsed = now - self._started[rid]
            notes.append(self.cancel(rid, f"timeout after {elapsed:g}s"))
        return notes
