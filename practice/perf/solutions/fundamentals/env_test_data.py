"""Exercise: unique test data for a load test (lesson "Test environments and test data").

Payment APIs replay the stored response when they see an ``Idempotency-Key`` again (see the lesson
idempotency-keys). A load test that reuses keys therefore measures the replay cache, not payment creation:
it is faster than reality and writes almost nothing. Test data must be unique per virtual user and per
iteration, and per run, because the server remembers keys between runs.

The practice target (support/sandpay_target.py) has 50 synthetic clients, ``merchant-1`` .. ``merchant-50`` with
secret ``secret-<n>``, and marks a replayed response with the header ``Idempotent-Replayed: true``.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass

POOL_SIZE = 50
MAX_KEY_LENGTH = 255


def assign_credentials(virtual_users: int, pool_size: int = POOL_SIZE) -> list[tuple[str, str]]:
    """One distinct (client_id, client_secret) per virtual user, in order: user 0 gets merchant-1.

    Raises ValueError if ``virtual_users`` is less than 1 or more than ``pool_size`` - sharing accounts between
    virtual users changes the workload (shared sessions, locks, rate limits), so it must be a decision, not an
    accident."""
    if virtual_users < 1:
        raise ValueError("virtual_users must be at least 1")
    if virtual_users > pool_size:
        raise ValueError(f"{virtual_users} virtual users but only {pool_size} unique accounts")
    return [(f"merchant-{n}", f"secret-{n}") for n in range(1, virtual_users + 1)]


def idempotency_key(run_id: str, user: int, iteration: int) -> str:
    """A key unique per run, virtual user and iteration: ``<run_id>-u<user>-i<iteration>``.

    Raises ValueError for an empty run id, negative numbers, or a key longer than 255 characters."""
    if not run_id:
        raise ValueError("run_id must not be empty")
    if user < 0 or iteration < 0:
        raise ValueError("user and iteration must not be negative")
    key = f"{run_id}-u{user}-i{iteration}"
    if len(key) > MAX_KEY_LENGTH:
        raise ValueError("idempotency key longer than 255 characters")
    return key


@dataclass
class CreateResult:
    created: int  # responses that were not replays
    replayed: int  # responses with Idempotent-Replayed: true
    distinct_ids: int  # distinct payment ids returned


def _post(url: str, body: dict, headers: dict) -> tuple[int, dict, dict]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, dict(resp.headers), json.loads(resp.read())


def create_payments(base_url: str, virtual_users: int, iterations: int, run_id: str) -> CreateResult:
    """For each virtual user (its own credentials), get a token, then create ``iterations`` payments of 1000
    EUR minor units, each with ``idempotency_key(run_id, user, iteration)``. Count what came back."""
    created = replayed = 0
    ids: set[str] = set()
    for user, (client_id, secret) in enumerate(assign_credentials(virtual_users)):
        _, _, tok = _post(f"{base_url}/auth/token", {"client_id": client_id, "client_secret": secret}, {})
        auth = {"Authorization": f"Bearer {tok['access_token']}"}
        for i in range(iterations):
            _, headers, payment = _post(f"{base_url}/v1/payments", {"amount_minor": 1000, "currency": "EUR"},
                                        {**auth, "Idempotency-Key": idempotency_key(run_id, user, i)})
            if headers.get("Idempotent-Replayed") == "true":
                replayed += 1
            else:
                created += 1
            ids.add(payment["id"])
    return CreateResult(created, replayed, len(ids))
