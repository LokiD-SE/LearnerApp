"""SOLUTION - An authorization matrix runner (WSTG-ATHZ-02, OWASP Authorization Testing Automation Cheat Sheet).

The cheat sheet's idea: write down, in a file a program can read, which **logical role** (or user) may use
which **feature**, then let integration tests replay every combination and fail on any that does not match.
Here a matrix line is ``<actor> <METHOD> <path> <allow|deny>``, for example::

    # actor     method  path                     expected
    alice       GET     /api/payments/pay_1001   allow
    alice       GET     /api/payments/pay_2001   deny     # bob's payment - horizontal
    anonymous   GET     /api/me                  deny

``anonymous`` sends no credentials. Every other actor needs a token in ``tokens``. The runner reads only
(GET and HEAD): a write rule also needs a payload, which the cheat sheet keeps in a separate
``services-testing`` section, and a write against shared data needs a reset afterwards.

Reading a response: 2xx means the actor was allowed; 401, 403 and 404 all mean denied (a well-built API may
answer 404 for "not yours" on purpose, so it does not reveal that the object exists); anything else is an
``error`` - the test proves nothing either way and must be looked at.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

ACTIONS = ("allow", "deny")
METHODS = ("GET", "HEAD")
DENIED = (401, 403, 404)


@dataclass(frozen=True)
class Rule:
    actor: str
    method: str
    path: str
    expected: str  # "allow" or "deny"


@dataclass(frozen=True)
class Result:
    rule: Rule
    status: int
    actual: str  # "allow", "deny" or "error"


def parse_matrix(text: str) -> list[Rule]:
    """Parse matrix lines into rules. Blank lines and ``#`` comments (whole-line or trailing) are ignored.

    Raise ``ValueError`` naming the 1-based line number when a line does not have exactly four fields, the
    method is not GET or HEAD, the path does not start with ``/``, or the expectation is not allow/deny.
    """
    rules: list[Rule] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"line {number}: expected 4 fields (actor method path allow|deny), got {len(fields)}")
        actor, method, path, expected = fields
        method = method.upper()
        if method not in METHODS:
            raise ValueError(f"line {number}: method {method} - this runner only replays {', '.join(METHODS)}")
        if not path.startswith("/"):
            raise ValueError(f"line {number}: path must start with /")
        if expected not in ACTIONS:
            raise ValueError(f"line {number}: expected must be allow or deny, not {expected!r}")
        rules.append(Rule(actor, method, path, expected))
    return rules


def decide(status: int) -> str:
    """Map a status code to what the server decided: ``allow``, ``deny`` or ``error``."""
    if 200 <= status < 300:
        return "allow"
    if status in DENIED:
        return "deny"
    return "error"


def run_matrix(base_url: str, rules: list[Rule], tokens: dict[str, str]) -> list[Result]:
    """Replay every rule against ``base_url`` as its actor and record what the server decided.

    ``anonymous`` is sent with no ``Authorization`` header; any other actor with ``Bearer <token>``. Raise
    ``KeyError`` for an actor that is neither anonymous nor in ``tokens`` - a typo must not silently become
    an anonymous request. Do not follow redirects: a 302 to a login page is an answer to classify, not a page
    to fetch.
    """
    results: list[Result] = []
    with requests.Session() as session:
        for rule in rules:
            headers = {}
            if rule.actor != "anonymous":
                headers["Authorization"] = f"Bearer {tokens[rule.actor]}"
            resp = session.request(rule.method, base_url + rule.path, headers=headers,
                                   allow_redirects=False, timeout=5)
            results.append(Result(rule, resp.status_code, decide(resp.status_code)))
    return results


def violations(results: list[Result]) -> list[Result]:
    """The results whose actual decision differs from the expected one, in matrix order (errors included)."""
    return [r for r in results if r.actual != r.rule.expected]


def report(results: list[Result]) -> str:
    """One line per violation: ``VIOLATION alice GET /api/payments/pay_2001 expected deny, got allow (200)``;
    ``ok: <n> rules match`` when there are none."""
    bad = violations(results)
    if not bad:
        return f"ok: {len(results)} rules match"
    return "\n".join(f"VIOLATION {r.rule.actor} {r.rule.method} {r.rule.path} expected {r.rule.expected}, "
                     f"got {r.actual} ({r.status})" for r in bad)
