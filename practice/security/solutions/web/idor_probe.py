"""SOLUTION - The two-account IDOR probe (WSTG-ATHZ-04 and WSTG-APIT-02, OWASP API1:2023 BOLA).

The WSTG's method: "having at least two (often more) users to cover different owned objects", then "obtain
the identifier of an invoice belonging to a different test user" and "check whether it is possible to access
objects without authorization". This probe automates it for the portal's payments:

1. Each account lists its **own** payments (``GET /api/payments``) - real identifiers, no guessing.
2. A **control**: account A reads one of its own payments. If that fails, the request shape or the token is
   wrong, and every "denied" below would be meaningless - so the probe stops instead of reporting "secure".
3. Account A reads every payment of account B. A 2xx whose owner field is B's is a leak.

Two accounts with the same role test **horizontal** access. Use an account of a different role (an admin)
as A or B for vertical checks - but an admin reading everything is usually the intended policy, so the
probe only reports leaks between the two accounts you give it.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class Leak:
    object_id: str
    status: int
    owner: str
    fields: tuple[str, ...]  # the keys A was shown, sorted - what leaked


def _get(base_url: str, path: str, token: str) -> requests.Response:
    return requests.get(base_url + path, headers={"Authorization": f"Bearer {token}"},
                        allow_redirects=False, timeout=5)


def list_own_ids(base_url: str, token: str) -> list[str]:
    """The ids of the caller's own payments from ``GET /api/payments`` (``{"data": [{"id": ...}, ...]}``).

    Raise ``RuntimeError`` if the listing is not a 200 - without it the probe has no objects to try.
    """
    resp = _get(base_url, "/api/payments", token)
    if resp.status_code != 200:
        raise RuntimeError(f"could not list own payments: {resp.status_code}")
    return [p["id"] for p in resp.json()["data"]]


def two_account_probe(base_url: str, token_a: str, token_b: str, owner_field: str = "merchant_id") -> list[Leak]:
    """Try every payment of account B as account A; return the leaks in B's listing order.

    Raise ``ValueError`` when either account owns no payments, or when the two listings share an id (then
    the accounts are not independent, so a "leak" could be a shared object). Raise ``RuntimeError`` when the
    control fails - A cannot read its own first payment with a 2xx and its own owner value.
    """
    ids_a = list_own_ids(base_url, token_a)
    ids_b = list_own_ids(base_url, token_b)
    if not ids_a or not ids_b:
        raise ValueError("each account needs payments of its own - create some before probing")
    if set(ids_a) & set(ids_b):
        raise ValueError("the accounts share objects, so they cannot show a cross-account leak")

    control = _get(base_url, f"/api/payments/{ids_a[0]}", token_a)
    if not 200 <= control.status_code < 300:
        raise RuntimeError(f"control failed: A cannot read its own {ids_a[0]} ({control.status_code})")
    owner_a = control.json().get(owner_field)
    owner_b = _get(base_url, f"/api/payments/{ids_b[0]}", token_b).json().get(owner_field)
    if owner_a is None or owner_a == owner_b:
        raise RuntimeError(f"control failed: no distinct {owner_field} for the two accounts")

    leaks: list[Leak] = []
    for oid in ids_b:
        resp = _get(base_url, f"/api/payments/{oid}", token_a)
        if 200 <= resp.status_code < 300:
            body = resp.json()
            if isinstance(body, dict) and body.get(owner_field) == owner_b:
                leaks.append(Leak(oid, resp.status_code, owner_b, tuple(sorted(body))))
    return leaks
