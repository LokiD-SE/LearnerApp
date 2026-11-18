"""Progress, cancellation and timeouts for requests in flight to several MCP servers.

From MCP 2026-07-28, Progress: a requester asks for updates by putting a ``progressToken`` in the request's
``_meta``; tokens "MUST be unique across all active requests"; ``progress`` "MUST increase with each
notification"; notifications "MUST only reference tokens that" were provided in an active request and "MUST
stop after completion".

From Cancellation: on stdio the client "MUST send a ``notifications/cancelled`` notification referencing the
request ID"; on Streamable HTTP "Closing the SSE response stream is the cancellation signal". Timeouts: an
implementation "MAY choose to reset the timeout clock" on progress but "SHOULD always enforce a maximum
timeout".

Times are passed in as numbers (seconds) so the logic is testable without a clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Op:
    server_id: str
    request_id: int | str
    progress: float | None = None
    total: float | None = None
    message: str = ""
    active: bool = True


@dataclass
class ProgressTracker:
    ops: dict[str, _Op] = field(default_factory=dict)
    ignored: list[str] = field(default_factory=list)
    _next: int = 1

    def new_token(self, server_id: str, request_id: int | str) -> str:
        """A token unique across every active request to every server: ``"<server_id>-<n>"``."""
        token = f"{server_id}-{self._next}"
        self._next += 1
        self.ops[token] = _Op(server_id, request_id)
        return token

    def on_notification(self, server_id: str, params: dict[str, Any]) -> bool:
        """Apply one ``notifications/progress`` params dict from ``server_id``; return True if accepted.

        Ignored (with a reason appended to ``ignored``): unknown token, a token of another server, a completed
        operation, a missing or non-increasing ``progress``.
        """
        token = params.get("progressToken")
        op = self.ops.get(token) if isinstance(token, (str, int)) else None
        if op is None:
            self.ignored.append(f"{server_id}: unknown token {token!r}")
            return False
        if op.server_id != server_id:
            self.ignored.append(f"{server_id}: token {token!r} belongs to {op.server_id}")
            return False
        if not op.active:
            self.ignored.append(f"{server_id}: token {token!r} already completed")
            return False
        progress = params.get("progress")
        if not isinstance(progress, (int, float)) or isinstance(progress, bool):
            self.ignored.append(f"{server_id}: token {token!r} has no numeric progress")
            return False
        if op.progress is not None and progress <= op.progress:
            self.ignored.append(f"{server_id}: token {token!r} progress {progress} does not increase on {op.progress}")
            return False
        op.progress = progress
        total = params.get("total")
        op.total = total if isinstance(total, (int, float)) and not isinstance(total, bool) else None
        op.message = str(params.get("message", ""))
        return True

    def complete(self, token: str) -> None:
        """The final response arrived (or the request was cancelled): later notifications are ignored."""
        if token in self.ops:
            self.ops[token].active = False

    def overall(self) -> tuple[float | None, int]:
        """``(mean fraction done over active operations that report a total, count of active ones without)``.

        The fraction is None when no active operation reports a total. Each fraction is capped at 1.0.
        """
        fractions = []
        unknown = 0
        for op in self.ops.values():
            if not op.active:
                continue
            if op.total:
                fractions.append(min(1.0, (op.progress or 0) / op.total))
            else:
                unknown += 1
        return (round(sum(fractions) / len(fractions), 4) if fractions else None), unknown


def cancellation_for(transport: str, request_id: int | str, reason: str) -> dict[str, Any]:
    """What a client does to cancel ``request_id``.

    ``"stdio"``: the ``notifications/cancelled`` message to write. ``"http"``: ``{"action": "close_stream",
    "requestId": ...}`` - closing the request's response stream is the signal; no message is sent.
    Anything else: ValueError.
    """
    if transport == "stdio":
        return {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": request_id, "reason": reason},
        }
    if transport == "http":
        return {"action": "close_stream", "requestId": request_id}
    raise ValueError(f"unknown transport {transport!r}")


def timed_out(started: float, last_progress: float | None, now: float, idle: float, maximum: float) -> str | None:
    """Why a request should be cancelled now, or None.

    ``"max"`` once ``now - started >= maximum`` (enforced whatever the progress); ``"idle"`` once ``idle`` seconds
    passed since the last progress notification (or since the start if there was none).
    """
    if now - started >= maximum:
        return "max"
    since = last_progress if last_progress is not None else started
    if now - since >= idle:
        return "idle"
    return None
