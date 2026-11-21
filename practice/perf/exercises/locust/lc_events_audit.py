"""A request audit built on Locust's ``request`` event - EXERCISE.

Locust's own statistics keep one row per request name. Build what a team also asks for after a run: how many
requests were slow, why each failure happened, and which merchant (from the request context) it happened to.
This module never imports Locust, so tests can call it directly; ``install`` receives Locust's ``events``.

``RequestAudit(slow_ms)``
- ``on_request(request_type, name, response_time, response_length, exception=None, context=None, **kwargs)``
  is the listener for ``events.request``. Keep one row per ``f"{request_type} {name}"`` with
    requests  - how many requests finished,
    slow      - how many took MORE than ``slow_ms`` milliseconds (exactly equal is not slow),
    failures  - how many came with an ``exception`` (not None),
    reasons   - failures counted by ``str(exception)``,
    merchants - failures counted by ``context["merchant"]`` (``context`` may be None or lack the key).
  Accept ``**kwargs``: Locust adds event arguments over time, and a listener that does not break on them keeps
  working.
- ``summary()`` returns ``{key: {"requests", "failures", "slow", "reasons": {...}, "merchants": {...}}}``
  with plain dicts (they must be JSON-serialisable), keys sorted.
- ``write(path)`` writes ``summary()`` as JSON.

``install(events, audit, path)`` registers ``audit.on_request`` on ``events.request`` and, on
``events.quitting``, writes the summary to ``path``. (The quitting listener is called with
``environment=...`` and may get more keyword arguments.)

Test: .venv/bin/python -m pytest tests/locust/test_lc_events_audit.py
"""


class RequestAudit:
    def __init__(self, slow_ms: float = 500.0) -> None:
        self.slow_ms = slow_ms
        # TODO: where you keep one row per "<request_type> <name>"

    def on_request(self, request_type, name, response_time, response_length, exception=None, context=None, **kwargs):
        raise NotImplementedError

    def summary(self) -> dict:
        raise NotImplementedError

    def write(self, path) -> None:
        raise NotImplementedError


def install(events, audit: RequestAudit, path) -> None:
    raise NotImplementedError
