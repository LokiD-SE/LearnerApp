"""EXERCISE - an HTTP wrapper that enforces the rules of engagement on every request.

The scope document says what may be touched; this class makes sure it cannot be forgotten at 2 a.m. Every probe in
the assessment sends its requests through ``GuardedHttp.request``, so the checks run on every request and not on
the ones the tester remembered to check.

Implement ``GuardedHttp.request(method, target, **kw)``. In this order:

1. BUDGET. If ``self.used`` (requests already SENT) has reached ``self.scope.max_requests``, raise
   ``BudgetExhausted``. A refused request was never sent, so it does not use budget.
2. SCOPE. ``target`` is a path (it starts with ``/``; join it onto ``self.scope.base_url``) or an absolute URL.
   Ask ``check_scope(self.scope, method, url)``: a string means refused. Record ``(METHOD, url, reason)`` in
   ``self.refused`` and raise ``OutOfScope(reason)``. Do not touch the network.
3. SEND with ``self.session.request(METHOD, url, allow_redirects=False, ...)``. Redirects are never followed - a
   ``Location`` header is data, not an instruction - and the caller cannot override that: drop an
   ``allow_redirects`` the caller passed. Default the ``timeout`` keyword to ``TIMEOUT``.
4. LOG. Append ``LogEntry(METHOD, <path only>, status)`` to ``self.log``. The path only, never the query string:
   a query can carry tokens or search terms that must not be copied into evidence.

Return the response. Methods are upper-cased.
"""

from __future__ import annotations

import requests
from scap_fixture import BudgetExhausted, LogEntry, OutOfScope, Scope, check_scope  # noqa: F401

TIMEOUT = 5


class GuardedHttp:
    def __init__(self, scope: Scope, session: requests.Session | None = None):
        self.scope = scope
        self.session = session if session is not None else requests.Session()
        self.log: list[LogEntry] = []
        self.refused: list[tuple[str, str, str]] = []  # (method, url, reason)

    @property
    def used(self) -> int:
        return len(self.log)

    @property
    def remaining(self) -> int:
        return self.scope.max_requests - self.used

    def request(self, method: str, target: str, **kw) -> requests.Response:
        """TODO: budget, scope, send without following redirects, log."""
        raise NotImplementedError("GuardedHttp.request")
