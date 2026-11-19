"""Run checks tagged with a WSTG test and an ASVS requirement, and fill in the WSTG checklist (reference solution).

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
    results = []
    for check in checks:
        try:
            passed, evidence = check.run(base_url)
        except Exception as exc:  # noqa: BLE001 - any crash is an Error result, never a Pass
            results.append(Result(check, "Error", f"{type(exc).__name__}: {exc}"))
            continue
        results.append(Result(check, "Pass" if passed else "Fail", evidence))
    return results


def combined_status(statuses: list[str]) -> str:
    """One checklist status for a WSTG test that several checks cover: Fail if any failed, else Error if any
    errored, else Pass."""
    if "Fail" in statuses:
        return "Fail"
    if "Error" in statuses:
        return "Error"
    return "Pass"


def to_checklist_markdown(results: list[Result]) -> str:
    """A WSTG-style checklist table (``| Test ID | Test Name | Status | Notes |``), one row per WSTG test id,
    sorted by id. Notes are ``<asvs_ref>: <evidence>`` for each check of that test, joined with ``; ``. Checks
    with an empty ``wstg_id`` are listed under the id ``(no WSTG test)`` after the others."""
    groups: dict[str, list[Result]] = {}
    for r in results:
        groups.setdefault(r.check.wstg_id or "(no WSTG test)", []).append(r)
    keys = sorted(k for k in groups if k != "(no WSTG test)")
    if "(no WSTG test)" in groups:
        keys.append("(no WSTG test)")
    lines = ["| Test ID | Test Name | Status | Notes |", "|---|---|---|---|"]
    for key in keys:
        group = groups[key]
        notes = "; ".join(f"{r.check.asvs_ref}: {r.evidence}" for r in group)
        status = combined_status([r.status for r in group])
        lines.append(f"| {key} | {group[0].check.test_name} | {status} | {notes} |")
    return "\n".join(lines) + "\n"


def csp_problems(policy: str | None) -> list[str]:
    """What a Content-Security-Policy value lacks against the ASVS v5.0.0-3.4.3 minimum, in this order:

    - ``"no policy"`` when the header is missing or empty (and nothing else);
    - ``"object-src 'none' missing"`` unless an ``object-src`` directive is exactly ``'none'``;
    - ``"base-uri 'none' missing"`` unless a ``base-uri`` directive is exactly ``'none'``;
    - ``"no allowlist, nonce or hash"`` unless ``script-src`` or ``default-src`` has at least one source.

    Directive names are case-insensitive; an empty list means the minimum is met.
    """
    if not policy or not policy.strip():
        return ["no policy"]
    directives: dict[str, list[str]] = {}
    for part in policy.split(";"):
        tokens = part.split()
        if tokens:
            directives.setdefault(tokens[0].lower(), tokens[1:])
    problems = []
    if directives.get("object-src") != ["'none'"]:
        problems.append("object-src 'none' missing")
    if directives.get("base-uri") != ["'none'"]:
        problems.append("base-uri 'none' missing")
    if not (directives.get("script-src") or directives.get("default-src")):
        problems.append("no allowlist, nonce or hash")
    return problems


def check_error_handling(base_url: str) -> tuple[bool, str]:
    """Provoke the portal's error (``GET /boom``) and pass only if the reply is a 5xx with no stack trace."""
    r = requests.get(f"{base_url}/boom", timeout=TIMEOUT)
    leaked = [m for m in TRACE_MARKERS if m in r.text]
    if r.status_code < 500:
        return False, f"GET /boom returned {r.status_code}, expected a server error"
    if leaked:
        return False, f"GET /boom {r.status_code} body shows {leaked[0]!r}"
    return True, f"GET /boom {r.status_code} generic body ({len(r.text)} bytes)"


def check_csp_asvs(base_url: str) -> tuple[bool, str]:
    """Read the CSP of ``GET /health`` and pass only if it meets the ASVS 3.4.3 minimum."""
    r = requests.get(f"{base_url}/health", timeout=TIMEOUT)
    policy = r.headers.get("Content-Security-Policy")
    problems = csp_problems(policy)
    if problems:
        return False, ", ".join(problems)
    return True, f"policy meets the minimum: {policy}"


DEFAULT_CHECKS = [
    Check("WSTG-ERRH-01", "Testing for Improper Error Handling", "v5.0.0-16.5.1", check_error_handling),
    Check("", "Content-Security-Policy minimum", "v5.0.0-3.4.3", check_csp_asvs),
]
