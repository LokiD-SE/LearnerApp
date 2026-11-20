"""EXERCISE - Find secrets in responses and logs, and prove it without copying them (WSTG-CRYP-03/04, A02, A09).

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


def find_secrets(text: str) -> list[dict]:
    """Returns ``[{"kind": str, "sample": str}, ...]`` sorted by kind then sample, one entry per match.

    ``sample`` is the redacted evidence: the first 4 characters of the matched secret, ``...`` and
    ``(<length> chars)``. For ``password-in-log`` and ``secret-assignment`` the secret is the VALUE after the
    ``=``; for the other kinds it is the whole match. A ``stack-trace`` sample is ``Trace...(<length> chars)``
    with the length of the phrase ``Traceback (most recent call last)``.
    """
    # TODO: one compiled pattern per kind; redact with first 4 chars + "..." + "(N chars)"; sort the result.
    raise NotImplementedError("find_secrets")


def excess_fields(body: dict, allowed: set[str]) -> list[str]:
    """Returns the sorted names of the top-level fields in ``body`` that are not in ``allowed``."""
    # TODO
    raise NotImplementedError("excess_fields")


def scan_portal(base_url: str, token: str, log_lines: list[str]) -> dict[str, list[dict]]:
    """Scans a running portal; returns ``{"merchant": [...], "error": [...], "log": [...]}`` (``find_secrets`` results).

    Refuses any ``base_url`` that is not loopback before sending a request. ``merchant`` scans
    ``GET /api/merchants/<own id>`` (the id from ``GET /api/me``, using the bearer ``token``); ``error`` scans the
    body of ``GET /boom``; ``log`` scans ``log_lines`` joined by newlines.
    """
    # TODO: loopback guard first; then /api/me, /api/merchants/<id>, /boom (any status); scan each text.
    raise NotImplementedError("scan_portal")
