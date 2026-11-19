"""Shared types for the intercepting-proxies exercises (Track L, lesson ``intercepting-proxies``).

``Exchange`` is one recorded request/response pair - what a proxy's history row holds. The recording proxy
(``foundations/proxy_recorder.py``) produces them and the evidence exporter (``foundations/proxy_evidence.py``)
turns them into a HAR 1.2 log. Keeping the type here lets each exercise be solved and tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Exchange:
    started: datetime  # when the proxy began forwarding the request (timezone-aware, UTC)
    method: str
    url: str  # absolute URL, as the client asked for it
    http_version: str  # e.g. "HTTP/1.1"
    request_headers: list[tuple[str, str]]  # as forwarded upstream, in order
    request_body: bytes
    status: int
    reason: str
    response_headers: list[tuple[str, str]]  # as received from the server, in order
    response_body: bytes
    send_ms: float = 0.0  # writing the request upstream
    wait_ms: float = 0.0  # until the status line and headers arrived
    receive_ms: float = 0.0  # reading the body
    notes: list[str] = field(default_factory=list)
