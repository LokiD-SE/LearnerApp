"""Audit ``Set-Cookie`` headers the way OWASP WSTG-SESS-02 (Testing for Cookies Attributes) describes.

Exercise - fill in the TODOs; ``tests/foundations/test_http_cookies.py`` checks your work. The rules:

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
    """Parse one ``Set-Cookie`` header value (without the ``Set-Cookie:`` name).

    TODO: split on ``;``. The first part is ``name=value`` (raise ValueError if there is no ``=`` or no name).
    Every other part is an attribute: ``Key=Value`` -> ``attributes["key"] = "Value"`` (strip spaces), or a
    bare flag such as ``Secure`` -> ``attributes["secure"] = True``. Attribute names are lower-cased
    (RFC 6265 compares them case-insensitively); keep values as written.
    """
    raise NotImplementedError("parse_set_cookie")


def audit_cookie(header: str, *, session: bool = True, https: bool = True) -> list[str]:
    """Finding codes for one ``Set-Cookie`` header, sorted; ``[]`` means nothing to report.

    Codes: ``missing-secure`` (only when ``https``), ``missing-httponly`` and ``missing-samesite`` (only when
    ``session``), ``samesite-none-without-secure``, ``domain-widens-scope`` (session cookie with Domain),
    ``invalid-host-prefix``, ``invalid-secure-prefix``.

    TODO: parse with ``parse_set_cookie`` and apply the rules in the module docstring. A ``SameSite``
    attribute with no value counts as missing. The prefixes are case-sensitive: ``__Host-`` needs Secure,
    ``Path=/`` and no Domain; ``__Secure-`` needs Secure.
    """
    raise NotImplementedError("audit_cookie")
