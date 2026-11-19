"""Origins, CORS decisions and CORS misconfiguration probes.

Reference solution.

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
    """The (scheme, host, port) tuple of an absolute http(s) URL, lower-cased, with the default port filled in."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS or not parts.hostname:
        raise ValueError(f"not an absolute http(s) URL: {url!r}")
    return scheme, parts.hostname.lower(), parts.port or DEFAULT_PORTS[scheme]


def same_origin(a: str, b: str) -> bool:
    return origin_of(a) == origin_of(b)


def browser_allows_read(origin: str, headers: dict[str, str], *, credentialed: bool) -> bool:
    """Would the browser let script running on ``origin`` read this cross-origin response?"""
    h = {k.lower(): v.strip() for k, v in headers.items()}
    acao = h.get("access-control-allow-origin")
    if acao is None:
        return False
    if credentialed:
        return acao == origin and h.get("access-control-allow-credentials", "").lower() == "true"
    return acao == "*" or acao == origin


def probe_cors(policy: Callable[[str], dict[str, str]], untrusted: list[str]) -> list[str]:
    """Finding codes, sorted, from sending each untrusted origin (and ``null``) to ``policy``:

    - ``reflects-untrusted-origin-with-credentials``: an untrusted origin can read credentialed responses -
      the serious one (the attacker's page reads the victim's data with the victim's cookies);
    - ``reflects-untrusted-origin``: an untrusted origin can read responses without credentials;
    - ``allows-null-origin``: ``null`` is allowed (WSTG-CLNT-07: a sandboxed iframe sends ``Origin: null``);
    - ``wildcard-origin``: ``Access-Control-Allow-Origin: *`` - fine for a public API, a finding otherwise;
    - ``missing-vary-origin``: the allowed origin varies with the request but ``Vary`` lacks ``Origin`` (MDN:
      the server "should also include Origin in the Vary response header"), so a shared cache can serve one
      origin's permission to another.
    """
    findings: set[str] = set()
    for origin in [*untrusted, "null"]:
        headers = policy(origin)
        h = {k.lower(): v for k, v in headers.items()}
        acao = h.get("access-control-allow-origin", "").strip()
        if acao == "*":
            findings.add("wildcard-origin")
            continue
        if acao != origin:
            continue
        if origin == "null":
            findings.add("allows-null-origin")
        elif browser_allows_read(origin, headers, credentialed=True):
            findings.add("reflects-untrusted-origin-with-credentials")
        else:
            findings.add("reflects-untrusted-origin")
        vary = {v.strip().lower() for v in h.get("vary", "").split(",")}
        if "origin" not in vary:
            findings.add("missing-vary-origin")
    return sorted(findings)
