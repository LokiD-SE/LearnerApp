"""Origins, CORS decisions and CORS misconfiguration probes.

Exercise - fill in the TODOs; ``tests/foundations/test_http_cors.py`` checks your work.

- An origin is the (scheme, host, port) tuple (RFC 6454; MDN "Same-origin policy"). A URL without a port uses
  the scheme's default: 80 for http, 443 for https.
- ``browser_allows_read`` models the browser's CORS check on a response, from MDN's CORS guide: the response is
  readable by script from ``origin`` if ``Access-Control-Allow-Origin`` is ``*`` (but never for a credentialed
  request: the server "must not specify the * wildcard") or exactly ``origin``; a credentialed request also
  needs ``Access-Control-Allow-Credentials: true``.
- ``probe_cors`` is what a tester does (WSTG-CLNT-07): send requests with origins the site should NOT trust
  and see whether it lets them read. ``policy`` stands in for the server: ``policy(origin) -> headers``.
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlsplit

DEFAULT_PORTS = {"http": 80, "https": 443}


def origin_of(url: str) -> tuple[str, str, int]:
    """The (scheme, host, port) tuple of an absolute http(s) URL, lower-cased, with the default port filled in.

    TODO: use ``urlsplit``; raise ValueError for other schemes or a missing host. ``DEFAULT_PORTS`` has 80
    and 443.
    """
    raise NotImplementedError("origin_of")


def same_origin(a: str, b: str) -> bool:
    """TODO: two URLs are same-origin when their origin tuples are equal."""
    raise NotImplementedError("same_origin")


def browser_allows_read(origin: str, headers: dict[str, str], *, credentialed: bool) -> bool:
    """Would the browser let script running on ``origin`` read this cross-origin response?

    TODO: header names are case-insensitive. No ``Access-Control-Allow-Origin`` -> False. Credentialed:
    the value must equal ``origin`` exactly AND ``Access-Control-Allow-Credentials`` must be ``true``
    (``*`` never works with credentials). Not credentialed: ``*`` or exactly ``origin``.
    """
    raise NotImplementedError("browser_allows_read")


def probe_cors(policy: Callable[[str], dict[str, str]], untrusted: list[str]) -> list[str]:
    """Finding codes, sorted, from sending each untrusted origin (and ``null``) to ``policy``.

    TODO: call ``policy(origin)`` for every origin in ``untrusted`` and for ``"null"``, and report:
    ``wildcard-origin`` (the response allows ``*``); for an origin the response allows by name:
    ``allows-null-origin`` (it was ``null``), ``reflects-untrusted-origin-with-credentials`` (the browser
    would allow a credentialed read) or ``reflects-untrusted-origin``; and ``missing-vary-origin`` when an
    origin is allowed by name but ``Vary`` does not list ``Origin``. See the module docstring for why each
    matters.
    """
    raise NotImplementedError("probe_cors")
