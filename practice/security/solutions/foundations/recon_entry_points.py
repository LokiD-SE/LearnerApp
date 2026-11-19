"""An entry-point inventory for the SandPay practice portal (WSTG-INFO-06, Identify Application Entry Points).

Reference solution. For every candidate endpoint it records the method, the parameters it takes and whether
it answers without credentials - the spreadsheet WSTG-INFO-06 describes, built by probing.

Safety rule (the point of the exercise): reconnaissance must not change data. Safe methods (GET, HEAD) are
probed twice - without and with credentials. Unsafe methods (POST, PUT, PATCH, DELETE) are probed only
WITHOUT credentials and with an empty body, so an endpoint that checks authentication first rejects them
before doing anything. If an unsafe endpoint answers an anonymous probe with something other than 401/403,
that itself is a finding ("answers anonymously") - and the probe stops there.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

SAFE_METHODS = ("GET", "HEAD")


@dataclass(frozen=True)
class Candidate:
    method: str
    path: str  # may include a query string, e.g. "/search?q=test"
    params: tuple[str, ...] = ()  # parameter names the tester saw (query, form or JSON body)


@dataclass(frozen=True)
class EntryPoint:
    method: str
    path: str
    params: tuple[str, ...]
    anonymous: int  # status without credentials
    authenticated: int | None  # status with credentials; None when not probed (unsafe method)
    access: str  # "public", "authenticated", "missing", "method-not-allowed", "error"


def classify(anonymous: int, authenticated: int | None) -> str:
    """Turns the two probe results into an access label.

    - 404 without credentials, and (if probed) 404 with them -> "missing"
    - 405 -> "method-not-allowed"
    - 401 or 403 without credentials -> "authenticated"
    - 500 or above without credentials -> "error" (worth a look: WSTG-INFO-06 says to note 500s)
    - anything else without credentials -> "public"
    """
    if anonymous == 405:
        return "method-not-allowed"
    if anonymous == 404 and authenticated in (None, 404):
        return "missing"
    if anonymous in (401, 403):
        return "authenticated"
    if anonymous >= 500:
        return "error"
    return "public"


def login_token(base_url: str, email: str, password: str) -> str:
    """Signs in through POST /api/login and returns the bearer token."""
    resp = requests.post(f"{base_url}/api/login", json={"email": email, "password": password}, timeout=5)
    resp.raise_for_status()
    return resp.json()["token"]


def probe(base_url: str, candidate: Candidate, token: str) -> EntryPoint:
    method = candidate.method.upper()
    url = base_url + candidate.path
    anonymous = requests.request(method, url, allow_redirects=False, timeout=5,
                                 json={} if method not in SAFE_METHODS else None).status_code
    authenticated = None
    if method in SAFE_METHODS:
        authenticated = requests.request(method, url, allow_redirects=False, timeout=5,
                                         headers={"Authorization": f"Bearer {token}"}).status_code
    return EntryPoint(method, candidate.path, candidate.params, anonymous, authenticated,
                      classify(anonymous, authenticated))


def inventory(base_url: str, candidates: list[Candidate], token: str) -> list[EntryPoint]:
    """Probes every candidate; returns entry points sorted by path, then method."""
    return sorted((probe(base_url, c, token) for c in candidates), key=lambda e: (e.path, e.method))
