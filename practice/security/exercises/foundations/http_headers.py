"""Check HTTP security response headers, and scan a running site for them.

Exercise - fill in the TODOs; ``tests/foundations/test_http_headers.py`` checks your work. What each check looks for, and where the rule comes from:

- ``missing-csp``: no ``Content-Security-Policy`` header.
- ``missing-frame-ancestors``: neither CSP ``frame-ancestors`` nor ``X-Frame-Options`` - the page can be
  framed (clickjacking, WSTG-CLNT-09). ``frame-ancestors`` "does not fall back to the default-src setting"
  (MDN), so ``default-src 'none'`` alone is not enough.
- ``missing-nosniff``: ``X-Content-Type-Options`` is not ``nosniff``.
- ``missing-referrer-policy``: no ``Referrer-Policy``. Browsers default to ``strict-origin-when-cross-origin``
  (MDN), so this is low severity - a site that leaks tokens in URLs needs a stricter policy.
- ``missing-hsts`` / ``invalid-hsts``: only for HTTPS. RFC 6797 section 8.1: "If an HTTP response is received
  over insecure transport, the UA MUST ignore any present STS header field(s)", so HSTS on plain HTTP is
  neither required nor useful. ``max-age`` is REQUIRED (section 6.1.1); ``max-age=0`` tells the browser to
  forget the host.
- ``version-disclosure``: a ``Server`` or ``X-Powered-By`` value that contains a version number.
"""

from __future__ import annotations

import re
import urllib.request
from urllib.error import HTTPError


def _lower(headers: dict[str, str]) -> dict[str, str]:
    return {k.lower(): v for k, v in headers.items()}


def check_security_headers(headers: dict[str, str], *, https: bool) -> list[str]:
    """Finding codes for one response's headers (any name case), sorted; ``[]`` means none.

    TODO: lower-case the header names, then apply the checks in the module docstring:
    ``missing-csp``, ``missing-frame-ancestors`` (no CSP ``frame-ancestors`` directive and no
    ``X-Frame-Options``), ``missing-nosniff``, ``missing-referrer-policy``, and - only when ``https`` -
    ``missing-hsts`` or ``invalid-hsts`` (no numeric ``max-age``, or ``max-age=0``). ``version-disclosure``
    when ``Server`` or ``X-Powered-By`` contains a number.
    """
    raise NotImplementedError("check_security_headers")


def fetch_headers(url: str) -> dict[str, str]:
    """GET ``url`` and return its response headers, including for 4xx/5xx responses (they need headers too).

    TODO: use ``urllib.request.urlopen(url, timeout=5)``; for an error status it raises ``HTTPError``, which
    still carries the response headers in ``err.headers``.
    """
    raise NotImplementedError("fetch_headers")


def scan(base_url: str, paths: list[str]) -> dict[str, list[str]]:
    """Check every path of a site: ``{path: findings}`` for paths with findings only. HTTPS is taken from
    the URL scheme, so HSTS is only demanded where browsers would honour it.

    TODO: for each path, fetch the headers of ``base_url + path`` and check them.
    """
    raise NotImplementedError("scan")
