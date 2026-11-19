"""EXERCISE - A first probe: find improper error handling (OWASP WSTG-ERRH-01) on the practice portal and keep evidence.

WSTG-ERRH-01 says improper error handling can let attackers "Identify filesystem paths, internal hostnames,
and secrets (e.g. connection strings, API keys, or prompts) embedded in error output". This probe requests
paths that may fail, and reports a finding only when an error response shows a stack trace or internal
details. A plain 500 with a generic message and a reference id is good practice, not a finding.

Evidence rules: record the request, the status and the lines that prove the leak, and redact secret values
before they go into the report - a report that copies a leaked key spreads the leak.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Callable

import requests

LOOPBACK = ("127.0.0.1", "localhost", "::1")

# Markers of a stack trace or internal detail in an error body (Python, Java, .NET, Node.js, PHP).
TRACE_MARKERS = (
    "Traceback (most recent call last)",
    'File "',
    "Exception in thread",
    "\tat ",
    "   at ",
    "at Object.<anonymous>",
    "Stack trace:",
)
# key=value pairs whose value is a secret; the value is replaced by [REDACTED] in evidence.
SECRET_PATTERN = re.compile(r"(?i)\b(key|secret|password|passwd|token|api_key)=([^\s;,&]+)")
MAX_EVIDENCE_LINES = 3


@dataclass(frozen=True)
class Finding:
    check: str  # "WSTG-ERRH-01"
    url: str
    status: int
    evidence: tuple[str, ...]  # redacted lines from the response body


def redact(line: str) -> str:
    """``key=abc`` -> ``key=[REDACTED]`` (case-insensitive names from SECRET_PATTERN)."""
    # TODO: implement redact - read the docstring above and the tests.
    raise NotImplementedError("redact")


def leak_lines(body: str) -> list[str]:
    """The evidence lines of ``body``, redacted and stripped of surrounding whitespace, at most
    MAX_EVIDENCE_LINES, in body order: the FIRST line that contains a TRACE_MARKER (proof of a stack trace),
    then every line that contains a secret key=value (proof of what leaked). Stack frames after the first add
    length, not proof, so they are left out. Empty list when the body leaks neither."""
    # TODO: implement leak_lines - read the docstring above and the tests.
    raise NotImplementedError("leak_lines")


def probe_error_handling(base_url: str, paths: tuple[str, ...] = ("/boom",),
                         get: Callable[..., requests.Response] = requests.get) -> list[Finding]:
    """GETs each path under ``base_url`` and returns a Finding for every response with status >= 500 whose
    body leaks a stack trace or secret (``leak_lines`` not empty).

    Refuses (ValueError) a ``base_url`` whose host is not loopback, before sending anything. Uses a timeout and
    does not follow redirects (a redirect could leave the scope).
    """
    # TODO: implement probe_error_handling - read the docstring above and the tests.
    raise NotImplementedError("probe_error_handling")
