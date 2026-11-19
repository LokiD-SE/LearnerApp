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
    # TODO: check the bounds, then build ("merchant-<n>", "secret-<n>") for n = 1..virtual_users.
    raise NotImplementedError("assign_credentials")


def idempotency_key(run_id: str, user: int, iteration: int) -> str:
    """A key unique per run, virtual user and iteration: ``<run_id>-u<user>-i<iteration>``.

    Raises ValueError for an empty run id, negative numbers, or a key longer than 255 characters."""
    # TODO: validate the inputs, build the key, check its length.
    raise NotImplementedError("idempotency_key")


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
    # TODO: for each user and credentials (enumerate assign_credentials), POST /auth/token with _post, then POST
    # /v1/payments once per iteration with the Bearer token and an Idempotency-Key header; count replays
    # (header Idempotent-Replayed == "true"), non-replays and distinct payment ids.
    raise NotImplementedError("create_payments")
