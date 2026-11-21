"""SOLUTION - an HTTP wrapper that enforces the rules of engagement on every request.

The scope document says what may be touched; this class makes sure it cannot be forgotten at 2 a.m. Every probe in
the assessment sends its requests through ``GuardedHttp.request``, so the checks run on every request and not on
the ones the tester remembered to check:

1. the budget: once ``scope.max_requests`` requests have been SENT, the next one raises ``BudgetExhausted``
   (a runaway loop must stop itself) - refused requests do not use budget, they were never sent;
2. the scope rule (``check_scope``): a refused request raises ``OutOfScope`` with the reason, is recorded in
   ``refused`` and is never sent;
3. redirects are never followed (a ``Location`` header is data, not an instruction), whatever the caller asks;
4. every sent request is recorded in ``log`` with its method, path and status - the path only, because a query string
   can carry values (tokens, search terms) that must not be copied into evidence.
"""

from __future__ import annotations

import urllib.parse

import requests
from scap_fixture import BudgetExhausted, LogEntry, OutOfScope, Scope, check_scope

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
        """Send ``method target`` if the engagement allows it. ``target`` is a path (``/api/me``, joined onto
        ``scope.base_url``) or an absolute URL. Returns the response; raises ``BudgetExhausted`` or ``OutOfScope``."""
        method = method.upper()
        url = self.scope.base_url + target if target.startswith("/") else target
        if self.used >= self.scope.max_requests:
            raise BudgetExhausted(f"request budget of {self.scope.max_requests} is used up")
        reason = check_scope(self.scope, method, url)
        if reason is not None:
            self.refused.append((method, url, reason))
            raise OutOfScope(reason)
        kw.pop("allow_redirects", None)
        kw.setdefault("timeout", TIMEOUT)
        resp = self.session.request(method, url, allow_redirects=False, **kw)
        self.log.append(LogEntry(method, urllib.parse.urlsplit(url).path, resp.status_code))
        return resp
