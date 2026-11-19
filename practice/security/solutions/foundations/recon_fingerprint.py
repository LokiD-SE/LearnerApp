"""Fingerprinting and information-leak checks (WSTG-INFO-02, -05 and -08).

Reference solution. ``fingerprint`` reads one response (headers and body) and reports what it gives away:

- ``server-version``: a ``Server`` header naming a product AND a version (``Apache/2.4.43 (Unix)``) - WSTG-INFO-02
  banner grabbing. A product name alone (``SandPay``) is not reported: there is no version to look up.
- ``powered-by``: any ``X-Powered-By`` header - WSTG-INFO-08 "the most basic form of identifying a web framework".
- ``stack-trace``: a Python traceback in the body (``Traceback (most recent call last):``) - it names files,
  frameworks and sometimes secrets.
- ``html-comment``: an HTML comment in a page - WSTG-INFO-05 page content review.

``scan(base_url)`` grabs the banner from ``GET /health`` and provokes the portal's error page (``GET /boom``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

# product/version: a token, a slash, then a version starting with a digit (product syntax: RFC 9110 section 10.1.5)
VERSIONED_PRODUCT = re.compile(r"([A-Za-z][\w.-]*)/(\d[\w.-]*)")
COMMENT = re.compile(r"<!--(.*?)-->", re.S)
TRACEBACK = "Traceback (most recent call last):"


@dataclass(frozen=True)
class Finding:
    kind: str  # "server-version", "powered-by", "stack-trace" or "html-comment"
    evidence: str  # the exact text that gives it away


def fingerprint(headers: dict[str, str], body: str = "") -> list[Finding]:
    """Findings for one response. Header names are matched case-insensitively."""
    h = {k.lower(): v for k, v in headers.items()}
    findings: list[Finding] = []
    server = h.get("server", "")
    if VERSIONED_PRODUCT.search(server):
        findings.append(Finding("server-version", server))
    if "x-powered-by" in h:
        findings.append(Finding("powered-by", h["x-powered-by"]))
    if TRACEBACK in body:
        findings.append(Finding("stack-trace", body.strip().splitlines()[-1][:200]))
    if "html" in h.get("content-type", ""):
        for comment in COMMENT.findall(body):
            findings.append(Finding("html-comment", comment.strip()[:200]))
    return findings


def scan(base_url: str) -> list[Finding]:
    """Banner grab on /health plus the error page at /boom; findings de-duplicated, in order."""
    findings: list[Finding] = []
    for path in ("/health", "/boom"):
        resp = requests.get(base_url + path, timeout=5)
        for f in fingerprint(dict(resp.headers), resp.text):
            if f not in findings:
                findings.append(f)
    return findings
