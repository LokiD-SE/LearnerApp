"""SOLUTION - Find secrets in responses and logs, and prove it without copying them (WSTG-CRYP-03/04, A02, A09).

Three jobs:

- ``find_secrets`` - scans text (a response body or log lines) for the shapes of secrets the SandPay portal can
  leak. EVIDENCE RULE: a finding never contains the whole secret - only its first 4 characters, an ellipsis and
  the length, for example ``sk_t...(23 chars)`` - so the report itself does not become a leak.
- ``excess_fields`` - compares a JSON response with the fields its contract allows (API3, excessive data exposure).
- ``scan_portal`` - fetches the merchant record and a forced error from a running portal and scans both, plus the
  log lines you were given by the owner.

Kinds ``find_secrets`` reports: ``api-key`` (``sk_`` + letters + ``_`` + token), ``password-in-log``
(``password=`` followed by a value), ``secret-assignment`` (``key=``, ``secret=`` or ``token=`` followed by a
value), ``stack-trace`` (a Python ``Traceback (most recent call last)``), ``iban`` (two letters, two digits, then
two to seven groups of four letters or digits, spaces optional).
"""

from __future__ import annotations

import re

import requests

LOOPBACK_PREFIXES = ("http://127.0.0.1:", "http://localhost:")


_PATTERNS = {
    "api-key": (re.compile(r"\bsk_[a-z]+_[A-Za-z0-9_]+"), 0),
    "password-in-log": (re.compile(r"\bpassword=(\S+)"), 1),
    "secret-assignment": (re.compile(r"\b(?:key|secret|token)=(\S+)"), 1),
    "stack-trace": (re.compile(r"Traceback \(most recent call last\)"), 0),
    "iban": (re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}\b"), 0),
}


def _redact(secret: str) -> str:
    return f"{secret[:4]}...({len(secret)} chars)"


def find_secrets(text: str) -> list[dict]:
    """Returns ``[{"kind": str, "sample": str}, ...]`` sorted by kind then sample, one entry per match."""
    found = [{"kind": kind, "sample": _redact(match.group(group))}
             for kind, (pattern, group) in _PATTERNS.items() for match in pattern.finditer(text)]
    return sorted(found, key=lambda item: (item["kind"], item["sample"]))


def excess_fields(body: dict, allowed: set[str]) -> list[str]:
    """Returns the sorted names of the top-level fields in ``body`` that are not in ``allowed``."""
    return sorted(set(body) - set(allowed))


def scan_portal(base_url: str, token: str, log_lines: list[str]) -> dict[str, list[dict]]:
    """Scans a running portal; returns ``{"merchant": [...], "error": [...], "log": [...]}``."""
    if not base_url.startswith(LOOPBACK_PREFIXES):
        raise ValueError("this scan only talks to the loopback interface")
    auth = {"Authorization": f"Bearer {token}"}
    me = requests.get(base_url + "/api/me", headers=auth, timeout=10)
    me.raise_for_status()
    merchant = requests.get(f"{base_url}/api/merchants/{me.json()['merchant_id']}", headers=auth, timeout=10)
    error = requests.get(base_url + "/boom", timeout=10)
    return {"merchant": find_secrets(merchant.text), "error": find_secrets(error.text),
            "log": find_secrets("\n".join(log_lines))}
