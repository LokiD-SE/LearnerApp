"""Client side of a multi round-trip request (MCP 2026-07-28, basic/patterns/mrtr).

A server that needs the user's input answers with ``resultType: "input_required"``. The client gathers the
answers, then retries the ORIGINAL request with a NEW id, the ``inputResponses`` and the exact
``requestState`` - and never sends inputRequests the client did not declare a capability for.
"""

from __future__ import annotations

from typing import Callable

SUPPORTED_INPUTS = {"elicitation/create": "elicitation"}


class InputLoopError(RuntimeError):
    """The server kept asking for input past the retry limit."""


def answer_input_requests(input_requests: dict, capabilities: dict, ask_user: Callable[[dict], dict]) -> dict:
    """Build the inputResponses map: one answer per key, from ask_user(params)."""
    responses = {}
    for key, req in input_requests.items():
        method = req.get("method")
        needed = SUPPORTED_INPUTS.get(method)
        if needed is None or needed not in capabilities:
            raise ValueError(f"server asked for {method!r}, which this client did not declare")
        responses[key] = ask_user(req.get("params", {}))
    return responses


def call_with_input(client, method: str, params: dict, ask_user: Callable[[dict], dict], max_rounds: int = 3) -> dict:
    """Send the request; while the result is input_required, answer and retry. Return the complete result."""
    current = dict(params)
    for _ in range(max_rounds):
        result = client.request(method, current)
        kind = result.get("resultType", "complete")
        if kind == "complete":
            return result
        if kind != "input_required":
            raise ValueError(f"unknown resultType {kind!r}")
        retry = dict(params)  # the original params, not the previous retry's
        if "inputRequests" in result:
            retry["inputResponses"] = answer_input_requests(result["inputRequests"], client.capabilities, ask_user)
        if "requestState" in result:
            retry["requestState"] = result["requestState"]
        current = retry
    raise InputLoopError(f"{method} still needs input after {max_rounds} rounds")
