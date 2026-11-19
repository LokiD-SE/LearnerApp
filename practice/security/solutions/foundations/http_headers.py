"""Check HTTP security response headers, and scan a running site for them.

Reference solution. What each check looks for, and where the rule comes from:

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
    """Finding codes for one response's headers (any name case), sorted; ``[]`` means none."""
    h = _lower(headers)
    findings: set[str] = set()
    csp = h.get("content-security-policy")
    if csp is None:
        findings.add("missing-csp")
    directives = {d.strip().split(" ", 1)[0].lower() for d in (csp or "").split(";") if d.strip()}
    if "frame-ancestors" not in directives and "x-frame-options" not in h:
        findings.add("missing-frame-ancestors")
    if h.get("x-content-type-options", "").strip().lower() != "nosniff":
        findings.add("missing-nosniff")
    if "referrer-policy" not in h:
        findings.add("missing-referrer-policy")
    if https:
        sts = h.get("strict-transport-security")
        if sts is None:
            findings.add("missing-hsts")
        else:
            m = re.search(r"(?i)(?:^|;)\s*max-age\s*=\s*\"?(\d+)\"?", sts)
            if not m or int(m.group(1)) == 0:
                findings.add("invalid-hsts")
    for name in ("server", "x-powered-by"):
        if re.search(r"\d+(\.\d+)*", h.get(name, "")):
            findings.add("version-disclosure")
    return sorted(findings)


def fetch_headers(url: str) -> dict[str, str]:
    """GET ``url`` and return its response headers, including for 4xx/5xx responses (they need headers too)."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - practice target on loopback
            return dict(resp.headers.items())
    except HTTPError as err:
        return dict(err.headers.items())


def scan(base_url: str, paths: list[str]) -> dict[str, list[str]]:
    """Check every path of a site: ``{path: findings}`` for paths with findings only. HTTPS is taken from
    the URL scheme, so HSTS is only demanded where browsers would honour it."""
    https = base_url.lower().startswith("https://")
    report: dict[str, list[str]] = {}
    for path in paths:
        findings = check_security_headers(fetch_headers(base_url + path), https=https)
        if findings:
            report[path] = findings
    return report
