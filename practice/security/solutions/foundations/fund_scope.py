"""A scope checker: decide BEFORE any request whether a target is in the written scope of the engagement.

NIST SP 800-115 defines Rules of Engagement as "Detailed guidelines and constraints regarding the execution of
information security testing", established "before the start of a security test". This module turns the
technical part of a scope - which hosts, ports, paths and methods - into a check that runs before every
request, so a typo, a redirect or a link to someone else's site can never become an unauthorised test.

Practice rule on top of the written scope: the practice projects only ever test the local SandPay portal, so
a host must be a loopback address (127.0.0.1, localhost, ::1) even if the scope document lists another host.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from typing import Callable

LOOPBACK = ("127.0.0.1", "localhost", "::1")
READ_ONLY_METHODS = ("GET", "HEAD", "OPTIONS")


class OutOfScope(Exception):
    """Raised instead of sending a request that the scope does not allow."""


@dataclass(frozen=True)
class Scope:
    hosts: frozenset[str]
    ports: frozenset[int] = frozenset()  # empty = any port on an in-scope host
    excluded_paths: tuple[str, ...] = ()  # path prefixes that must never be touched
    methods: frozenset[str] = frozenset(READ_ONLY_METHODS)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def parse_scope(doc: dict) -> Scope:
    """Builds a Scope from a dict like the technical part of a rules-of-engagement document:
    ``{"hosts": ["127.0.0.1"], "ports": [8765], "excluded_paths": ["/internal/"], "methods": ["GET", "POST"]}``.

    - ``hosts`` is required and must not be empty; hosts are lower-cased.
    - ``methods`` defaults to read-only (GET, HEAD, OPTIONS); methods are upper-cased.
    - Raises ValueError for a missing or empty host list, or a port outside 1-65535.
    """
    hosts = doc.get("hosts")
    if not hosts:
        raise ValueError("scope must list at least one host")
    ports = frozenset(int(p) for p in doc.get("ports", []))
    if any(not 1 <= p <= 65535 for p in ports):
        raise ValueError("ports must be between 1 and 65535")
    methods = frozenset(m.upper() for m in doc.get("methods", READ_ONLY_METHODS))
    return Scope(frozenset(h.lower() for h in hosts), ports, tuple(doc.get("excluded_paths", ())), methods)


def check(scope: Scope, url: str, method: str = "GET") -> Decision:
    """Decides whether ``method url`` may be sent. Checks, in order:

    1. scheme is http or https;
    2. no user info in the URL (``http://127.0.0.1@evil.example/`` targets evil.example);
    3. the host is in ``scope.hosts`` - an exact match, so ``127.0.0.1.evil.example`` is not 127.0.0.1;
    4. the host is a loopback address (practice rule);
    5. the port (default 80 / 443) is in ``scope.ports`` when ports are listed;
    6. the path does not start with an excluded prefix (after percent-decoding, so ``/%69nternal/`` is caught);
    7. the method is allowed.

    Returns ``Decision(True, "in scope")`` or ``Decision(False, <reason naming the failed rule>)``.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return Decision(False, f"scheme {parts.scheme or '(none)'!r} is not http or https")
    if parts.username is not None or "@" in parts.netloc:
        return Decision(False, "user info in the URL hides the real host")
    host = (parts.hostname or "").lower()
    if host not in scope.hosts:
        return Decision(False, f"host {host!r} is not in scope")
    if host not in LOOPBACK:
        return Decision(False, f"host {host!r} is not a loopback address (practice rule)")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError:
        return Decision(False, "invalid port")
    if scope.ports and port not in scope.ports:
        return Decision(False, f"port {port} is not in scope")
    path = urllib.parse.unquote(parts.path or "/")
    for prefix in scope.excluded_paths:
        if path.startswith(prefix):
            return Decision(False, f"path {path!r} is excluded ({prefix})")
    if method.upper() not in scope.methods:
        return Decision(False, f"method {method.upper()} is not allowed")
    return Decision(True, "in scope")


@dataclass
class GuardedClient:
    """Sends requests only after ``check`` allows them, and logs every decision (the evidence that the test
    stayed in scope). ``send`` is the function that really sends - ``requests.request`` in practice, a fake in
    tests - and is never called for a refused request."""

    scope: Scope
    send: Callable[..., object]
    log: list[tuple[str, str, Decision]] = field(default_factory=list)

    def request(self, method: str, url: str, **kwargs: object) -> object:
        decision = check(self.scope, url, method)
        self.log.append((method.upper(), url, decision))
        if not decision.allowed:
            raise OutOfScope(f"{method.upper()} {url}: {decision.reason}")
        return self.send(method, url, **kwargs)
