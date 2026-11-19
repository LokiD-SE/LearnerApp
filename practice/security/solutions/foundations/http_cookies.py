"""Audit ``Set-Cookie`` headers the way OWASP WSTG-SESS-02 (Testing for Cookies Attributes) describes.

Reference solution. The rules:

- ``Secure``: "tells the browser to only send the cookie if the request is being sent over a secure channel
  such as HTTPS" (WSTG-SESS-02). Every cookie on an HTTPS site needs it.
- ``HttpOnly``: does "not allow the cookie to be accessed via a client-side script such as JavaScript"
  (WSTG-SESS-02). Session cookies need it; a cookie JavaScript must read (a CSRF double-submit token, a UI
  preference) legitimately goes without, so the check applies only when ``session=True``.
- ``SameSite``: omitting it is browser-dependent (Chromium treats it as Lax, Firefox and Safari do not -
  WSTG-SESS-02), so a session cookie should state it. ``SameSite=None`` without ``Secure`` is rejected by
  Chromium and Firefox.
- ``Domain`` on a session cookie widens it to every subdomain; host-only (no Domain) is narrower.
- Prefixes (RFC 6265bis draft, section 4.1.3): ``__Secure-`` needs ``Secure``; ``__Host-`` needs ``Secure``,
  ``Path=/`` and no ``Domain``. The prefix match is case-sensitive.

Attribute names are case-insensitive (RFC 6265 section 5.2: "case-insensitively matches"), so ``secure``,
``SECURE`` and ``Secure`` are the same attribute.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Cookie:
    name: str
    value: str
    attributes: dict[str, str | bool] = field(default_factory=dict)  # lower-case name -> value, or True


def parse_set_cookie(header: str) -> Cookie:
    """Parse one ``Set-Cookie`` header value (without the ``Set-Cookie:`` name)."""
    parts = [p.strip() for p in header.split(";")]
    name, sep, value = parts[0].partition("=")
    if not sep or not name.strip():
        raise ValueError(f"not a cookie: {header!r}")
    attributes: dict[str, str | bool] = {}
    for part in parts[1:]:
        if not part:
            continue
        key, sep, val = part.partition("=")
        attributes[key.strip().lower()] = val.strip() if sep else True
    return Cookie(name.strip(), value.strip(), attributes)


def audit_cookie(header: str, *, session: bool = True, https: bool = True) -> list[str]:
    """Finding codes for one ``Set-Cookie`` header, sorted; ``[]`` means nothing to report.

    Codes: ``missing-secure`` (only when ``https``), ``missing-httponly`` and ``missing-samesite`` (only when
    ``session``), ``samesite-none-without-secure``, ``domain-widens-scope`` (session cookie with Domain),
    ``invalid-host-prefix``, ``invalid-secure-prefix``.
    """
    c = parse_set_cookie(header)
    a = c.attributes
    secure = "secure" in a
    findings: set[str] = set()
    if https and not secure:
        findings.add("missing-secure")
    if session and "httponly" not in a:
        findings.add("missing-httponly")
    samesite = a.get("samesite")
    if session and samesite in (None, True, ""):
        findings.add("missing-samesite")
    if isinstance(samesite, str) and samesite.lower() == "none" and not secure:
        findings.add("samesite-none-without-secure")
    if session and "domain" in a:
        findings.add("domain-widens-scope")
    if c.name.startswith("__Host-") and not (secure and a.get("path") == "/" and "domain" not in a):
        findings.add("invalid-host-prefix")
    if c.name.startswith("__Secure-") and not secure:
        findings.add("invalid-secure-prefix")
    return sorted(findings)
