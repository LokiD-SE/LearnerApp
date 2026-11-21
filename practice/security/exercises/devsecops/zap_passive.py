"""A tiny passive scanner in the spirit of ZAP's passive rules (DAST lesson).

Exercise - fill in the TODOs; ``tests/devsecops/test_zap_passive.py`` checks your work.

*Passive* means the scanner only READS responses; it sends no attack. ``passive_alerts`` judges ONE recorded
response (so it needs no network); ``passive_scan`` fetches the steps you list - ordinary requests, the way a
person uses the site - and judges every response. These are simplified versions of rules that ZAP documents, not
ZAP's own code. The rules, with the ids, names and risks of ZAP's alert documentation (``RULES``):

- ``10038-1`` CSP header not set: an HTML response (``Content-Type`` contains ``text/html``) with no
  ``Content-Security-Policy`` header.
- ``10020-1`` missing anti-clickjacking header: an HTML response with neither ``X-Frame-Options`` nor a CSP that
  contains ``frame-ancestors``.
- ``10021`` X-Content-Type-Options missing: the header is absent or does not contain ``nosniff``.
- ``10036-2`` server leaks version: the ``Server`` header contains a digit. Evidence: the header value.
- ``10035-4`` HSTS on a plain HTTP response: a ``Strict-Transport-Security`` header and a URL starting ``http://``.
- ``10010`` / ``10011`` / ``10054-1``: for each ``Set-Cookie``, no ``HttpOnly`` attribute / no ``Secure``
  attribute / no ``SameSite=`` attribute. Evidence: the cookie NAME only - the value is a session id, and a
  report must never carry one.
- ``90022`` application error disclosure: the body contains ``Traceback (most recent call last)`` or a Python
  ``File "...", line N`` frame. Evidence: the first matching text, at most 80 characters.

Header names are case-insensitive. ``Finding`` is shared (``support/zap_fixture.py``).
"""

from __future__ import annotations

import re
import urllib.parse

import requests
from zap_fixture import RISKS, Finding

RULES = {
    "10038-1": ("Content Security Policy (CSP) Header Not Set", "Medium"),
    "10020-1": ("Missing Anti-clickjacking Header", "Medium"),
    "10021": ("X-Content-Type-Options Header Missing", "Low"),
    "10036-2": ('Server Leaks Version Information via "Server" HTTP Response Header Field', "Low"),
    "10035-4": ("Strict-Transport-Security Header on Plain HTTP Response", "Informational"),
    "10010": ("Cookie No HttpOnly Flag", "Low"),
    "10011": ("Cookie Without Secure Flag", "Low"),
    "10054-1": ("Cookie without SameSite Attribute", "Low"),
    "90022": ("Application Error Disclosure", "Medium"),
}
LOOPBACK = ("127.0.0.1", "localhost", "::1")
ERROR_TEXT = re.compile(r'Traceback \(most recent call last\)|^\s*File ".+", line \d+', re.MULTILINE)


def is_loopback(url: str) -> bool:
    return urllib.parse.urlsplit(url).hostname in LOOPBACK


def passive_alerts(url: str, status: int, headers: list[tuple[str, str]], body: str) -> list[Finding]:
    """The findings for one response, in rule order of the module docstring.

    TODO: group ``headers`` by lower-cased name (a name can repeat, like ``Set-Cookie``), then apply every rule.
    Build each finding from ``RULES[rule_id]`` with ``Finding(rule_id, name, risk, url, evidence=...)``.
    """
    raise NotImplementedError("passive_alerts")


def passive_scan(base_url: str, steps: list[tuple[str, str, dict | None]], timeout: float = 5) -> list[Finding]:
    """Run ``steps`` - ``(method, path, json_body_or_None)`` - against ``base_url`` and judge every response.

    TODO: refuse a non-loopback ``base_url`` with ``ValueError`` BEFORE sending anything. Send each step with
    ``requests.request(..., json=payload, allow_redirects=False)``. Build the header list from ``resp.headers``
    without ``Set-Cookie`` plus one ``("Set-Cookie", c)`` per ``resp.raw.headers.getlist("Set-Cookie")``. Report
    each (rule, url, evidence) once, sorted by risk (highest first, ``RISKS`` gives the order), then rule id, then url.
    """
    raise NotImplementedError("passive_scan")
