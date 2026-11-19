"""Run checks tagged with a WSTG test and an ASVS requirement, and fill in the WSTG checklist (exercise).

Write every function that raises NotImplementedError; the docstrings say what each must do. Run the
tests with: .venv/bin/python -m pytest tests/foundations/test_wstg_runner.py

A check answers one verification question - ASVS 5.0.0: "the verification must result in a 'fail' or 'pass'
decision" - and records evidence. The runner adds a third outcome the standard does not have but a test run
does: **Error**, when the check itself crashed. A crashed check proved nothing, so it must never count as a
pass.

Two checks are included, both against the practice portal (support/sandpay_vuln.py, loopback only):

- ``check_error_handling`` - WSTG-ERRH-01, ASVS v5.0.0-16.5.1: "a generic message is returned to the consumer
  when an unexpected or security-sensitive error occurs, ensuring no exposure of sensitive internal system data
  such as stack traces, queries, secret keys, and tokens."
- ``check_csp_asvs`` - ASVS v5.0.0-3.4.3 (WSTG v4.2 has no CSP test): "As a minimum, a global policy must be used
  which includes the directives object-src 'none' and base-uri 'none' and defines either an allowlist or uses
  nonces or hashes."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import requests

TIMEOUT = 5
TRACE_MARKERS = ("Traceback (most recent call last)", 'File "', "\tat ", "Exception in thread")


@dataclass(frozen=True)
class Check:
    wstg_id: str  # e.g. "WSTG-ERRH-01"
    test_name: str  # the WSTG test name, e.g. "Testing for Improper Error Handling"
    asvs_ref: str  # e.g. "v5.0.0-16.5.1"
    run: Callable[[str], tuple[bool, str]]  # base URL -> (passed, evidence)


@dataclass(frozen=True)
class Result:
    check: Check
    status: str  # "Pass", "Fail" or "Error"
    evidence: str


def run_checks(base_url: str, checks: list[Check]) -> list[Result]:
    """Run every check once, in order. A check that raises becomes an ``Error`` result whose evidence names the
    exception type and message; the remaining checks still run."""
    raise NotImplementedError("TODO: write run_checks")


def combined_status(statuses: list[str]) -> str:
    """One checklist status for a WSTG test that several checks cover: Fail if any failed, else Error if any
    errored, else Pass."""
    raise NotImplementedError("TODO: write combined_status")


def to_checklist_markdown(results: list[Result]) -> str:
    """A WSTG-style checklist table (``| Test ID | Test Name | Status | Notes |``), one row per WSTG test id,
    sorted by id. Notes are ``<asvs_ref>: <evidence>`` for each check of that test, joined with ``; ``. Checks
    with an empty ``wstg_id`` are listed under the id ``(no WSTG test)`` after the others."""
    raise NotImplementedError("TODO: write to_checklist_markdown")


def csp_problems(policy: str | None) -> list[str]:
    """What a Content-Security-Policy value lacks against the ASVS v5.0.0-3.4.3 minimum, in this order:

    - ``"no policy"`` when the header is missing or empty (and nothing else);
    - ``"object-src 'none' missing"`` unless an ``object-src`` directive is exactly ``'none'``;
    - ``"base-uri 'none' missing"`` unless a ``base-uri`` directive is exactly ``'none'``;
    - ``"no allowlist, nonce or hash"`` unless ``script-src`` or ``default-src`` has at least one source.

    Directive names are case-insensitive; an empty list means the minimum is met.
    """
    raise NotImplementedError("TODO: write csp_problems")


def check_error_handling(base_url: str) -> tuple[bool, str]:
    """Provoke the portal's error (``GET /boom``) and pass only if the reply is a 5xx with no stack trace."""
    raise NotImplementedError("TODO: write check_error_handling")


def check_csp_asvs(base_url: str) -> tuple[bool, str]:
    """Read the CSP of ``GET /health`` and pass only if it meets the ASVS 3.4.3 minimum."""
    raise NotImplementedError("TODO: write check_csp_asvs")


DEFAULT_CHECKS = [
    Check("WSTG-ERRH-01", "Testing for Improper Error Handling", "v5.0.0-16.5.1", check_error_handling),
    Check("", "Content-Security-Policy minimum", "v5.0.0-3.4.3", check_csp_asvs),
]
