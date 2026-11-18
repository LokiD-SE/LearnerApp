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
    """Build the inputResponses map: one answer per key, from ask_user(request params).

    TODO: a method not in SUPPORTED_INPUTS, or whose capability is not in ``capabilities``, raises ValueError.
    """
    raise NotImplementedError("answer_input_requests")


def call_with_input(client, method: str, params: dict, ask_user: Callable[[dict], dict], max_rounds: int = 3) -> dict:
    """Send the request; while the result is input_required, answer and retry. Return the complete result.

    TODO:
    - ``client.request(method, params)`` returns the result (it adds _meta and a new id itself)
    - absent resultType counts as "complete"; an unknown one raises ValueError
    - each retry starts from a copy of the ORIGINAL params, plus inputResponses (only if the server sent
      inputRequests) and the latest requestState (only if the server sent one)
    - never change the caller's params; after max_rounds requests raise InputLoopError
    """
    raise NotImplementedError("call_with_input")
