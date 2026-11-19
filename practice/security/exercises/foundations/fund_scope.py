"""EXERCISE - A scope checker: decide BEFORE any request whether a target is in the written scope of the engagement.

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
    # TODO: implement parse_scope - read the docstring above and the tests.
    raise NotImplementedError("parse_scope")


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
    # TODO: implement check - read the docstring above and the tests.
    raise NotImplementedError("check")


@dataclass
class GuardedClient:
    """Sends requests only after ``check`` allows them, and logs every decision (the evidence that the test
    stayed in scope). ``send`` is the function that really sends - ``requests.request`` in practice, a fake in
    tests - and is never called for a refused request."""

    scope: Scope
    send: Callable[..., object]
    log: list[tuple[str, str, Decision]] = field(default_factory=list)

    def request(self, method: str, url: str, **kwargs: object) -> object:
        # TODO: implement request - read the docstring above and the tests.
        raise NotImplementedError("request")
