"""Boolean-based differential detection of SQL injection in one parameter (OWASP WSTG-INPV-05).

The idea, from the WSTG's "SELECT Statement" and "Boolean Exploitation Technique" sections: send the normal
value, then the same value with an always-true condition appended, then with an always-false one. If the
true variant answers exactly like the normal value and the false variant answers differently, the input is
being read as SQL - the condition changed the query's logic. Nothing is extracted and nothing is changed:
the probe only adds ``AND '1'='1`` / ``AND '1'='2`` to a read.

``send`` is any function that sends one value of the parameter and returns ``(status, body_text)``, so the
same probe works on the practice portal (``portal_sender``) and on in-memory fakes in the tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import requests

Send = Callable[[str], tuple[int, str]]

# JSON keys whose values change on every response (an error reference, a request id); a difference in
# them is not a difference in the query's result.
VOLATILE_KEYS = frozenset({"reference", "request_id", "timestamp"})


class InconclusiveError(Exception):
    """The same request gave different answers, so true/false answers cannot be told apart."""


@dataclass(frozen=True)
class Finding:
    parameter: str
    technique: str  # always "boolean" here
    context: str  # "string" (value inside quotes) or "numeric" (bare number)
    true_value: str
    false_value: str
    evidence: tuple[str, ...]


def boolean_pairs(value: str) -> list[tuple[str, str, str]]:
    """``(context, true_value, false_value)`` pairs to try, string context first.

    String context closes the quote and leaves the query's own closing quote to balance the last ``'1``:
    ``captured' AND '1'='1``. Numeric context (only for an all-digit value) appends the condition bare.
    """
    raise NotImplementedError("TODO: boolean_pairs")


def fingerprint(status: int, body: str) -> tuple[int, str]:
    """What two responses must share to count as "the same answer": the status and the body, with volatile
    JSON keys removed (anywhere in the document) and key order ignored. Non-JSON bodies compare as text."""
    raise NotImplementedError("TODO: fingerprint")


def probe_boolean(send: Send, parameter: str, value: str) -> Finding | None:
    """Returns a Finding if a true/false condition pair changes the answer the way SQL logic would.

    1. Send the normal value twice. Different answers mean the page is unstable: raise InconclusiveError
       rather than guess (the WSTG notes this case; tools such as sqlmap then compare a stable part).
    2. For each pair: true must equal the baseline and false must differ from it.
    3. Replay the pair once to rule out a one-off change, then report.
    """
    raise NotImplementedError("TODO: probe_boolean")


def portal_sender(base_url: str, token: str, parameter: str = "status", path: str = "/api/payments",
                  timeout: float = 5.0) -> Send:
    """A ``send`` for the practice portal: GET ``path?parameter=value`` with a bearer token."""

    def send(value: str) -> tuple[int, str]:
        r = requests.get(base_url + path, params={parameter: value},
                         headers={"Authorization": f"Bearer {token}"}, timeout=timeout, allow_redirects=False)
        return r.status_code, r.text

    return send
