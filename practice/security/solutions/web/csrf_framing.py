"""May another origin frame this page? Clickjacking protection as browsers decide it (WSTG-CLNT-09).

Reference solution. Two headers can forbid framing, and the order of the rules matters:

- **CSP ``frame-ancestors``** wins when present. CSP Level 3 section 6.4.2.2: "If a resource is delivered
  with a policy that includes a directive named frame-ancestors and whose disposition is "enforce", then the
  X-Frame-Options header will be ignored". Only ``Content-Security-Policy`` is enforced;
  ``Content-Security-Policy-Report-Only`` reports and never blocks. Every enforced policy must allow the
  framing (several CSP headers are several policies, and all apply). ``frame-ancestors`` is checked against
  every ancestor, not only the direct parent.
- **``X-Frame-Options``** otherwise, processed as the HTML standard section 7.7 "The X-Frame-Options header"
  says (it supersedes RFC 7034): values are split on commas (one header or several), lower-cased and
  de-duplicated; more than one distinct value including ``deny``, ``sameorigin`` or ``allowall`` blocks;
  more than one distinct value otherwise allows; ``deny`` blocks; ``sameorigin`` needs every ancestor to be
  same origin with the page; anything else - ``ALLOW-FROM`` included - is ignored as if absent.
- **Neither header**: framing is allowed.

``frame-ancestors`` source matching here is a SIMPLIFIED subset of CSP Level 3 section 6.7.2 - enough for
the usual policies: ``'none'``, ``'self'``, ``*`` (any http/https origin), scheme sources (``https:``) and host
sources with an optional scheme, a leading ``*.`` wildcard for subdomains, and an optional port (default port
of the scheme when omitted). Paths in host sources are ignored, as CSP ignores them for ancestors.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True)
class Origin:
    scheme: str
    host: str
    port: int

    @staticmethod
    def parse(url: str) -> "Origin":
        u = urlsplit(url)
        scheme = u.scheme.lower()
        return Origin(scheme, (u.hostname or "").lower(), u.port or DEFAULT_PORTS.get(scheme, 0))


@dataclass
class Decision:
    allowed: bool
    by: str  # "frame-ancestors", "x-frame-options" or "none"
    reason: str


def enforced_frame_ancestors(headers: list[tuple[str, str]]) -> list[list[str]]:
    """The ``frame-ancestors`` source lists of every ENFORCED policy (``Content-Security-Policy`` headers,
    each comma-separated policy counted separately; Report-Only ignored). A policy without the directive
    adds nothing. Directive names are case-insensitive; the first occurrence in a policy counts."""
    lists = []
    for name, value in headers:
        if name.lower() != "content-security-policy":
            continue
        for policy in value.split(","):
            for directive in policy.split(";"):
                tokens = directive.split()
                if tokens and tokens[0].lower() == "frame-ancestors":
                    lists.append(tokens[1:])
                    break
    return lists


def source_matches(source: str, ancestor: Origin, page: Origin) -> bool:
    """Does one ``frame-ancestors`` source expression match ``ancestor`` (the page itself is ``page``)?"""
    s = source.lower()
    if s == "'none'":
        return False
    if s == "'self'":
        return ancestor == page
    if s == "*":
        return ancestor.scheme in ("http", "https")
    if s.endswith(":") and "/" not in s:  # scheme source, e.g. https: (http: also allows https)
        return ancestor.scheme == s[:-1] or (s == "http:" and ancestor.scheme == "https")
    scheme = None
    if "://" in s:
        scheme, s = s.split("://", 1)
    s = s.split("/", 1)[0]  # paths are ignored for ancestors
    host, port = s, None
    if ":" in s:
        host, p = s.rsplit(":", 1)
        port = None if p == "*" else int(p)
        any_port = p == "*"
    else:
        any_port = False
    if scheme is not None and ancestor.scheme != scheme:
        return False
    if scheme is None and ancestor.scheme not in ("http", "https"):
        return False
    if host.startswith("*."):
        if not ancestor.host.endswith(host[1:]):
            return False
    elif ancestor.host != host:
        return False
    if any_port:
        return True
    expected = port if port is not None else DEFAULT_PORTS.get(scheme or ancestor.scheme)
    return ancestor.port == expected


def xfo_values(headers: list[tuple[str, str]]) -> list[str]:
    """``X-Frame-Options`` values from every such header: split on commas, trimmed, lower-cased, de-duplicated
    in order of first appearance (an empty value after a trailing comma counts as a value)."""
    out: list[str] = []
    for name, value in headers:
        if name.lower() == "x-frame-options":
            for v in value.split(","):
                v = v.strip().lower()
                if v not in out:
                    out.append(v)
    return out


def may_frame(headers: list[tuple[str, str]], page_url: str, ancestor_urls: list[str]) -> Decision:
    """Would a browser render the page served with ``headers`` at ``page_url`` inside frames whose
    ancestors (direct parent first, top-level page last) are ``ancestor_urls``?"""
    page = Origin.parse(page_url)
    ancestors = [Origin.parse(u) for u in ancestor_urls]
    lists = enforced_frame_ancestors(headers)
    if lists:
        for sources in lists:
            for a in ancestors:
                if not any(source_matches(s, a, page) for s in sources):
                    shown = " ".join(sources) or "(empty list)"
                    return Decision(False, "frame-ancestors",
                                    f"{a.scheme}://{a.host}:{a.port} is not in frame-ancestors {shown}")
        return Decision(True, "frame-ancestors", "every ancestor matches every enforced frame-ancestors list")

    values = xfo_values(headers)
    if not values:
        return Decision(True, "none", "no frame-ancestors and no X-Frame-Options")
    if len(values) > 1:
        if {"deny", "sameorigin", "allowall"} & set(values):
            return Decision(False, "x-frame-options", f"conflicting values {values} - blocked")
        return Decision(True, "x-frame-options", f"only invalid values {values} - treated as absent")
    if values[0] == "deny":
        return Decision(False, "x-frame-options", "DENY")
    if values[0] == "sameorigin":
        for a in ancestors:
            if a != page:
                return Decision(False, "x-frame-options", f"SAMEORIGIN and ancestor {a.host} is cross-origin")
        return Decision(True, "x-frame-options", "SAMEORIGIN and every ancestor is same origin")
    return Decision(True, "x-frame-options", f"invalid value {values[0]!r} - treated as absent")


def framable_pages(base_url: str, paths: list[str], attacker: str = "https://evil.example",
                   cookie: str | None = None) -> list[str]:
    """The ``paths`` of a running site that ``attacker`` could frame (clickjacking findings), in order.
    Every response counts - error pages too."""
    found = []
    for path in paths:
        headers = {"Cookie": cookie} if cookie else {}
        r = requests.get(base_url + path, headers=headers, timeout=5, allow_redirects=False)
        # requests joins repeated headers with ", " - both parsers above split on commas, so nothing is lost
        if may_frame(list(r.headers.items()), base_url + path, [attacker]).allowed:
            found.append(path)
    return found
