"""Turn a captured request into a CSRF proof-of-concept page for a finding report (WSTG-SESS-05).

Exercise - fill in the TODOs; ``tests/web/test_csrf_poc.py`` checks your work. A PoC is evidence for developers: an HTML page that, opened by a signed-in victim,
makes their browser send the state-changing request. It is generated as TEXT for the report - this code
never serves or opens it. Rules that keep it honest:

- A cross-site HTML form can only send what a form can send: method GET or POST, and a body encoded as
  ``application/x-www-form-urlencoded``, ``multipart/form-data`` or ``text/plain`` (the three "simple"
  content types in the OWASP CSRF Prevention Cheat Sheet). It cannot set headers: ``Authorization``,
  ``X-CSRF-Token`` and other custom headers are dropped, and ``Cookie`` is added by the browser itself.
- So a request that depends on a custom header or a JSON content type is NOT exploitable by a form; the PoC
  says so in ``notes`` instead of pretending.
- Every value is HTML-escaped, because captured values may contain quotes or markup.
- ``Origin`` and ``Referer`` cannot be set by the page either; a server that checks them will refuse the PoC.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlsplit

FORM_CONTENT_TYPES = ("application/x-www-form-urlencoded", "multipart/form-data", "text/plain")
CREDENTIAL_HEADERS = {"authorization", "x-csrf-token", "x-xsrf-token", "csrf-token", "x-csrftoken",
                      "x-requested-with"}
BROWSER_HEADERS = {"host", "content-length", "content-type", "cookie", "user-agent", "accept",
                   "accept-encoding", "accept-language", "connection", "origin", "referer"}


@dataclass
class Captured:
    method: str
    url: str  # absolute
    headers: list[tuple[str, str]]
    body: str


@dataclass
class Poc:
    exploitable_by_form: bool
    html: str  # "" when not exploitable by a form
    notes: list[str] = field(default_factory=list)


def parse_captured(raw: str, scheme: str = "http") -> Captured:
    """Parse a raw HTTP/1.1 request as a proxy history shows it. The URL is rebuilt from ``Host``."""
    head, _, body = raw.replace("\r\n", "\n").partition("\n\n")
    lines = head.split("\n")
    method, target, _version = lines[0].split(" ", 2)
    headers = []
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers.append((name.strip(), value.strip()))
    host = next((v for k, v in headers if k.lower() == "host"), "")
    url = target if target.startswith(("http://", "https://")) else f"{scheme}://{host}{target}"
    return Captured(method.upper(), url, headers, body)


def _header(req: Captured, name: str) -> str:
    return next((v for k, v in req.headers if k.lower() == name), "")


def build_poc(req: Captured) -> Poc:
    """A self-submitting form for ``req``, or ``exploitable_by_form=False`` with the reasons in ``notes``.

    Not exploitable by a form when: the method is not GET or POST; a POST body is not one of the three form
    content types; or the request carries a credential or anti-CSRF header (``CREDENTIAL_HEADERS``) - the
    browser will not add it to a forged request. Other non-browser headers only earn a note.

    TODO: blockers first - method not GET/POST; a POST content type not in FORM_CONTENT_TYPES; any
    header in CREDENTIAL_HEADERS. With blockers, return Poc(False, "", blockers + notes). Other non-browser
    headers only add a note. Then build the form: GET fields from the query string; urlencoded POST fields
    from the body (keep the query on the action); text/plain uses the WSTG trick (split the body at the first
    "=", enctype="text/plain", note the CRLF); multipart returns Poc(True, "", note). Escape every name,
    value and the action with html.escape(..., quote=True); the form has id="poc" and the page submits it.
    """
    raise NotImplementedError("build_poc")
