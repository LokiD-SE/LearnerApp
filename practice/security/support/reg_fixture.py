"""Shared types and synthetic data for the security-regression lesson (``security-regression-automation``).

Everything here is SYNTHETIC. SandPay is fictional, the findings below were never reported by anyone, and the
registry and the ``pytest --collect-only -q`` output are written by hand in the shape those things have.

- ``PairResult``, ``Entry``, ``Problem``, ``GuardResult``: the result types the exercises build.
- ``STATUSES`` / ``SEVERITIES``: the values a registry entry may use. Anything else is an error, not a default.
- ``SAMPLE_REGISTRY``: a finding-to-test registry (JSON text) with one healthy entry of each kind and one entry
  of each registry problem the registry exercise has to report.
- ``COLLECT_OUTPUT``: what ``pytest --collect-only -q`` prints for the regression folder, summary line included.
- Probes for the guard exercise: ``always_true``, ``always_false``, ``broken_control``, ``make_flaky(pattern)``
  (counter-driven, so the same calls give the same answers on every machine) and ``redirect_probe`` (a small
  real probe of the portal's ``open-redirect`` flaw that does not depend on any exercise).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import requests

STATUSES = ("open", "fixed", "accepted")
SEVERITIES = ("Critical", "High", "Medium", "Low")


@dataclass(frozen=True)
class PairResult:
    flaw: str
    found_on_vulnerable: bool
    found_on_fixed: bool
    verdict: str  # "red-green", "blind" or "noisy"


@dataclass(frozen=True)
class Entry:
    id: str
    flaw: str
    severity: str
    status: str
    test: str | None = None  # a pytest node id, e.g. tests/regression/test_x.py::test_name
    fixed_in: str | None = None
    accepted_until: str | None = None  # ISO date
    reason: str | None = None


@dataclass(frozen=True)
class Problem:
    kind: str
    finding_id: str | None  # None for a test that no finding points at
    detail: str


@dataclass(frozen=True)
class GuardResult:
    flaw: str
    vulnerable_runs: tuple[bool, ...]
    fixed_runs: tuple[bool, ...]
    verdict: str  # "trustworthy", "flaky", "blind", "noisy" or "broken"


SAMPLE_REGISTRY = """[
  {"id": "SP-101", "flaw": "idor", "severity": "High", "status": "fixed", "fixed_in": "build-412",
   "test": "tests/regression/test_sp101_idor.py::test_alice_cannot_read_bobs_payment"},
  {"id": "SP-102", "flaw": "open-redirect", "severity": "Medium", "status": "fixed", "fixed_in": "build-415",
   "test": "tests/regression/test_sp102_redirect.py::test_login_next_stays_on_site"},
  {"id": "SP-103", "flaw": "path-traversal", "severity": "High", "status": "fixed", "fixed_in": "build-418",
   "test": null},
  {"id": "SP-104", "flaw": "sqli", "severity": "Critical", "status": "fixed", "fixed_in": "build-420",
   "test": "tests/regression/test_sp104_sqli.py::test_status_filter_is_not_injectable"},
  {"id": "SP-105", "flaw": "xss-reflected", "severity": "Medium", "status": "open",
   "test": "tests/regression/test_sp105_xss.py::test_search_encodes_output"},
  {"id": "SP-106", "flaw": "weak-hash", "severity": "Low", "status": "accepted",
   "accepted_until": "2026-10-31", "reason": "password rehash planned for the next release"},
  {"id": "SP-107", "flaw": "verbose-errors", "severity": "Low", "status": "accepted"}
]"""

COLLECT_OUTPUT = """tests/regression/test_sp101_idor.py::test_alice_cannot_read_bobs_payment
tests/regression/test_sp102_redirect.py::test_login_next_stays_on_site
tests/regression/test_sp105_xss.py::test_search_encodes_output
tests/regression/test_old_cors.py::test_cors_wildcard

4 tests collected in 0.02s
"""


def always_true(base_url: str) -> bool:
    """A probe that reports the flaw everywhere - on a fixed build it is a false positive."""
    return True


def always_false(base_url: str) -> bool:
    """A probe that never reports the flaw - on a vulnerable build it is blind."""
    return False


def broken_control(base_url: str) -> bool:
    """A probe whose positive control fails, as the real probes do when login or the request shape is wrong."""
    raise RuntimeError("control failed: the request shape is wrong")


def make_flaky(pattern: str) -> Callable[[str], bool]:
    """A probe whose answers cycle through ``pattern`` (``T`` = flaw reported, ``F`` = not), one per call.

    Counter-driven, never random: ``make_flaky("TTF")`` answers True, True, False, True, True, False, ...
    """
    calls = {"n": 0}

    def probe(base_url: str) -> bool:
        answer = pattern[calls["n"] % len(pattern)] == "T"
        calls["n"] += 1
        return answer

    return probe


def redirect_probe(base_url: str) -> bool:
    """Real probe of ``open-redirect``: True when ``/login?next=`` sends the browser to another site."""
    ok = requests.get(base_url + "/login", params={"next": "/settings"}, allow_redirects=False, timeout=5)
    if ok.status_code != 302 or ok.headers.get("Location") != "/settings":
        raise RuntimeError("control failed: a local next= is not redirected as expected")
    bad = requests.get(base_url + "/login", params={"next": "https://evil.example/"}, allow_redirects=False, timeout=5)
    return bad.status_code == 302 and bad.headers.get("Location", "").startswith("https://evil.example")
