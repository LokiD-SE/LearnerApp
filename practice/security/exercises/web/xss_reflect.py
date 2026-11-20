"""Reflected XSS probe (WSTG-INPV-01): find where input comes back, in which context, and what is left unencoded.

EXERCISE: implement every function marked TODO. Check with: .venv/bin/python -m pytest tests/web/test_xss_reflect.py

A server-side test cannot prove that script RUNS - only a browser executes it. What it can prove, with
evidence, is the precondition the WSTG asks testers to check: the input is reflected and "special characters
that were not properly encoded" break out of the context they land in. That is what this probe reports.

Method (harmless by design - no script, no event handler is ever sent):

1. ``make_canary`` - a unique, alphanumeric marker, so the probe finds ITS reflection and nothing else.
2. ``classify_context`` - where the canary landed: HTML text, a quoted/unquoted attribute, a script block or
   a comment. The characters that matter depend on the context (the WSTG: "The set of vulnerable unfiltered
   special characters will depend on the context").
3. ``probe_characters`` - one request per special character, each wrapped in the canary
   (``<canary><char><canary>``), so each character's fate is unambiguous: ``raw``, ``encoded`` or ``absent``.
4. ``find_reflected_xss`` - a finding when a character that breaks out of the detected context comes back
   raw; ``None`` otherwise (no false positive once the output is encoded).

The "breaks out" table is this exercise's rule of thumb, derived from the WSTG and the OWASP XSS Prevention
Cheat Sheet contexts; it is not an OWASP-published table.
"""

from __future__ import annotations

import html
import re
import secrets
from dataclasses import dataclass, field

import requests

# The WSTG's key HTML characters, plus the backslash for script contexts.
PROBE_CHARS = ("<", ">", '"', "'", "&", "\\")

# Which raw characters let input break out of each context (any one is enough).
BREAKOUT = {
    "html-text": {"<"},
    "attribute-double": {'"'},
    "attribute-single": {"'"},
    "attribute-unquoted": {">", '"', "'", "<"},
    "script": {"<", '"', "'", "\\"},
    "comment": {">"},
}


def make_canary(prefix: str = "xq") -> str:
    """A unique marker: a fixed lowercase prefix and 10 random hex characters (letters and digits only, so
    no encoder changes it)."""
    raise NotImplementedError("TODO: make_canary")


def classify_context(page: str, canary: str) -> str | None:
    """The context of the FIRST occurrence of ``canary`` in ``page``, or ``None`` if it is not there.

    Returns one of the ``BREAKOUT`` keys. A small scanner, not an HTML parser: it looks at what precedes the
    canary - an open comment, an open script element, or an open tag with an attribute value."""
    raise NotImplementedError("TODO: classify_context")


def _fate(page: str, canary: str, char: str) -> str:
    """What happened to ``char`` sent as ``<canary><char><canary>``: ``"raw"`` if the exact string is in the
    page, ``"encoded"`` if the canaries enclose an encoded form of it (an HTML entity such as ``&lt;`` or
    ``&#x27;``, a backslash escape or a ``%HH`` escape), otherwise ``"absent"`` (removed or filtered)."""
    raise NotImplementedError("TODO: _fate")


@dataclass
class ReflectionReport:
    url: str
    parameter: str
    context: str | None
    fates: dict[str, str] = field(default_factory=dict)  # char -> raw | encoded | absent

    @property
    def breakout_chars(self) -> list[str]:
        """The probe characters, in ``PROBE_CHARS`` order, that came back ``raw`` AND break out of the
        detected context (``BREAKOUT[context]``). Empty when the parameter was not reflected."""
        raise NotImplementedError("TODO: breakout_chars")


def probe_characters(base_url: str, path: str, parameter: str, session: requests.Session | None = None,
                     canary: str | None = None) -> ReflectionReport:
    """Sends the plain canary once (to find the context), then one request per special character."""
    raise NotImplementedError("TODO: probe_characters")


@dataclass
class Finding:
    url: str
    parameter: str
    context: str
    breakout_chars: list[str]
    evidence: str  # the response fragment around one raw reflection


def find_reflected_xss(base_url: str, path: str, parameter: str,
                       session: requests.Session | None = None) -> Finding | None:
    """A finding if a context-breaking character is reflected raw; ``None`` if the parameter is not
    reflected or every breaking character comes back encoded."""
    raise NotImplementedError("TODO: find_reflected_xss")
