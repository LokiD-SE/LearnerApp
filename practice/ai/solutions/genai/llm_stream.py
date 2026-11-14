"""Assembling a streamed LLM reply from events.

``events_from_reply`` (given, not part of the exercise) turns a ``ScriptedLLM`` reply into a list of event dicts
in a SIMPLIFIED format modelled on the event flow Anthropic documents for streaming Messages
(message_start, content deltas, ping, message_delta with cumulative usage, message_stop, error events). It is
not any provider's wire format - real SDKs parse server-sent events into typed objects for you.

    {"type": "message_start", "usage": {"input_tokens": 12, "output_tokens": 0}}
    {"type": "text_delta", "text": "Refu"}
    {"type": "ping"}
    {"type": "message_delta", "stop_reason": None, "usage": {"output_tokens": 3}}      # cumulative
    {"type": "message_delta", "stop_reason": "end_turn", "usage": {"output_tokens": 7}}
    {"type": "message_stop"}
    {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


def events_from_reply(reply: Any, chunk: int = 4, fail_after: int | None = None, pings: bool = True) -> list[dict]:
    """Given helper: the events a stream of ``reply`` would produce.

    ``fail_after=n`` stops after n text deltas with an ``overloaded_error`` event (an error after a 200 start).
    """
    text = reply.text
    pieces = [text[i : i + chunk] for i in range(0, len(text), chunk)]
    events: list[dict] = [{"type": "message_start", "usage": {"input_tokens": reply.input_tokens, "output_tokens": 0}}]
    half = max(1, len(pieces) // 2)
    for n, piece in enumerate(pieces, start=1):
        if fail_after is not None and n > fail_after:
            events.append({"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
            return events
        events.append({"type": "text_delta", "text": piece})
        if pings and n == 1:
            events.append({"type": "ping"})
        if n == half and len(pieces) > 1:
            so_far = round(reply.output_tokens * n / len(pieces))
            events.append({"type": "message_delta", "stop_reason": None, "usage": {"output_tokens": so_far}})
    events.append({"type": "message_delta", "stop_reason": reply.stop_reason, "usage": {"output_tokens": reply.output_tokens}})
    events.append({"type": "message_stop"})
    return events


class StreamError(Exception):
    """The stream failed or ended early. ``partial`` holds the text received before the failure."""

    def __init__(self, message: str, partial: str):
        super().__init__(message)
        self.partial = partial


@dataclass
class Assembled:
    text: str
    stop_reason: str | None
    input_tokens: int
    output_tokens: int


def assemble(events: Iterable[dict]) -> Assembled:
    """Rebuild the final reply from stream events.

    - Concatenate ``text_delta`` texts in order; ignore ``ping`` and unknown event types.
    - ``input_tokens`` comes from ``message_start``. Usage in ``message_delta`` is CUMULATIVE: keep the latest
      value, never add them up. ``stop_reason`` comes from the last ``message_delta`` that sets one.
    - An ``error`` event raises ``StreamError`` (with the partial text) - the HTTP status was already 200.
    - A stream that ends without ``message_stop`` raises ``StreamError`` too: the reply is incomplete.
    """
    parts: list[str] = []
    stop_reason = None
    input_tokens = output_tokens = 0
    finished = False
    for event in events:
        kind = event.get("type")
        if kind == "message_start":
            input_tokens = event["usage"]["input_tokens"]
            output_tokens = event["usage"].get("output_tokens", 0)
        elif kind == "text_delta":
            parts.append(event["text"])
        elif kind == "message_delta":
            output_tokens = event["usage"]["output_tokens"]
            if event.get("stop_reason") is not None:
                stop_reason = event["stop_reason"]
        elif kind == "message_stop":
            finished = True
        elif kind == "error":
            error = event["error"]
            raise StreamError(f"{error['type']}: {error['message']}", "".join(parts))
    if not finished:
        raise StreamError("stream ended without message_stop", "".join(parts))
    return Assembled("".join(parts), stop_reason, input_tokens, output_tokens)


def stream_text(llm: Any, on_text: Callable[[str], None], **request: Any) -> str:
    """Call ``llm.stream(**request)``, pass every chunk to ``on_text`` as it arrives, and return the whole text."""
    parts = []
    for piece in llm.stream(**request):
        on_text(piece)
        parts.append(piece)
    return "".join(parts)
